"""LLM Router — tier-routed inference (02.3.8, 21B §20).

| 21B §20.5 interface | Method     |
|---------------------|------------|
| Inference Request   | `infer`    |
| Model Tier Health   | `health`   |

The Router sits **above** the Integration Gateway, not beside it (21B §20.4).
Model providers are external capability providers: the Router selects a tier
and a model, and the Integration Gateway governs the relationship with
whoever provides it. That layering is what lets `01.3.1` Local First hold —
Nano and Standard may be served by locally-hosted capability with no external
integration at all, and Premium **degrades to unavailable rather than to
failure**.

The Router is not part of the Tool Platform and does not execute tools. It is
grouped into Stage S6 because it is the third module of the Integration
Platform per 21B §20, and unlike its two siblings it is **not** CIR-001
blocked: it is an internal abstraction over model tiering, not a governed
external relationship.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from typing import Any, Protocol

from core.exceptions import AgentOSError, NotFoundError
from kernel.journal import ImmutableJournal
from kernel.signals import SignalEmitter, SignalType
from llm_router.pipeline import (
    ContextItem,
    GroundingValidator,
    InferenceRequest,
    InferenceResult,
    ModelTier,
    PipelineOrderViolation,
    PipelineStage,
    PromptTemplate,
    ResponseCache,
    Sanitizer,
    TierUnavailable,
    TokenBudgetExceeded,
    estimate_tokens,
)

#: 21B §20.4 — the failover chain degrades downward. Premium becoming
#: unavailable falls back to locally-servable tiers rather than failing.
FAILOVER_CHAIN: dict[ModelTier, tuple[ModelTier, ...]] = {
    ModelTier.PREMIUM: (ModelTier.PREMIUM, ModelTier.STANDARD, ModelTier.NANO),
    ModelTier.STANDARD: (ModelTier.STANDARD, ModelTier.NANO),
    ModelTier.NANO: (ModelTier.NANO,),
}


class ContextSource(Protocol):
    """Memory retrieval for pipeline stage 2 (21B §20.6)."""

    def retrieve(self, tenant_id: str, query: str, limit: int) -> Sequence[ContextItem]: ...


class BudgetSource(Protocol):
    """External spend budget checks and attribution (21B §20.6)."""

    def has_headroom(self, tenant_id: str, cost: float) -> bool: ...

    def record_spend(self, tenant_id: str, cost: float, principal_id: str, tier: str) -> None: ...


class ModelBackend(Protocol):
    """One model tier's inference capability.

    Local backends (Nano, Standard) need no integration. A Premium backend is
    an external capability, which is why `available` exists — the Router must
    be able to see a tier go dark and degrade rather than fail.
    """

    def available(self) -> bool: ...

    def complete(self, prompt: str, max_tokens: int) -> tuple[dict[str, Any], int, float]: ...


@dataclass
class PipelineTrace:
    """Records the stages a request ran, enforcing their fixed order.

    21B §20.4: "Reordering any stage breaks a constitutional guarantee." The
    trace refuses a stage that does not advance, so an out-of-order pipeline
    is an exception rather than a subtle correctness bug.
    """

    stages: list[PipelineStage] = field(default_factory=list)

    def enter(self, stage: PipelineStage) -> None:
        if self.stages and stage <= self.stages[-1]:
            raise PipelineOrderViolation(
                f"stage {stage.name} ran after {self.stages[-1].name}; the ten stages of 02.8.5 are fixed in order"
            )
        self.stages.append(stage)

    def ran(self, stage: PipelineStage) -> bool:
        return stage in self.stages

    def before(self, earlier: PipelineStage, later: PipelineStage) -> bool:
        if earlier not in self.stages or later not in self.stages:
            return False
        return self.stages.index(earlier) < self.stages.index(later)


@dataclass
class LLMRouter:
    """Routes all inference. Layer 4 (21B §20)."""

    context: ContextSource
    budget: BudgetSource
    backends: dict[ModelTier, ModelBackend]
    signals: SignalEmitter
    now: Callable[[], datetime] = field(default=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        self.sanitizer = Sanitizer()
        self.grounding = GroundingValidator()
        self.cache = ResponseCache(now=self.now)
        self.journal = ImmutableJournal()
        self._templates: dict[str, PromptTemplate] = {}
        self._tier_failures: dict[ModelTier, int] = {}
        self._spend_by_tier: dict[ModelTier, float] = {}
        self._requests = 0

    def register_template(self, template: PromptTemplate) -> PromptTemplate:
        self._templates[template.name] = template
        return template

    # ------------------------------------------------------------- Inference

    def infer(self, request: InferenceRequest) -> InferenceResult:
        """**Inference Request** (21B §20.5): the ten-stage pipeline, in order."""
        self._requests += 1
        trace = PipelineTrace()

        # 1. Template selection.
        trace.enter(PipelineStage.TEMPLATE_SELECTION)
        template = self._templates.get(request.template_name)
        if template is None:
            raise NotFoundError(f"prompt template '{request.template_name}' is not registered")

        # 2. Context retrieval.
        trace.enter(PipelineStage.CONTEXT_RETRIEVAL)
        context = list(self.context.retrieve(request.tenant_id, request.slots.get("query", ""), 5))

        # 3. Context assembly.
        trace.enter(PipelineStage.CONTEXT_ASSEMBLY)
        assembled = "\n".join(f"[{item.source_id}] {item.content}" for item in context)

        # 4. Input sanitization — before rendering, never after.
        trace.enter(PipelineStage.INPUT_SANITIZATION)
        findings: list[str] = []
        clean_slots: dict[str, str] = {}
        for name, value in request.slots.items():
            cleaned, found = self.sanitizer.sanitize(value)
            clean_slots[name] = cleaned
            findings.extend(found)
        clean_context, context_findings = self.sanitizer.sanitize(assembled)
        findings.extend(context_findings)
        if findings:
            self.signals.emit(
                SignalType.EVENT,
                "llm.sanitization.finding",
                request.tenant_id,
                request_id=request.request_id,
                findings=len(findings),
            )

        # 5. Prompt rendering.
        trace.enter(PipelineStage.PROMPT_RENDERING)
        rendered = self._render(template, clean_slots, clean_context)

        cache_key = ResponseCache.key(request.tenant_id, template.name, rendered)
        cached = self.cache.get(cache_key)
        if cached is not None:
            # Return a copy labelled for *this* request. Handing back the
            # stored object verbatim would report the original request's id
            # and claim cache_hit=False, so a consumer could not tell a cached
            # answer from a fresh one.
            hit = replace(cached, request_id=request.request_id, cache_hit=True)
            self._journal(request, hit, cache_hit=True)
            return hit

        # 6. Token budget check — before invocation, never after.
        trace.enter(PipelineStage.TOKEN_BUDGET_CHECK)
        tokens = estimate_tokens(rendered)
        if tokens > template.max_tokens:
            raise TokenBudgetExceeded(f"rendered prompt is ~{tokens} tokens against a {template.max_tokens} budget")
        if not self.budget.has_headroom(request.tenant_id, request.max_cost):
            raise AgentOSError(f"no budget headroom for inference at a ceiling of {request.max_cost}")

        # 7. Invocation, with failover down the chain.
        trace.enter(PipelineStage.INVOCATION)
        tier, output, tokens_used, cost = self._invoke_with_failover(request, rendered, template)

        # 8. Output parsing.
        trace.enter(PipelineStage.OUTPUT_PARSING)
        claims = _claims_of(output)

        # 9. Grounding validation — before cache storage, never after.
        trace.enter(PipelineStage.GROUNDING_VALIDATION)
        ungrounded = self.grounding.validate(claims, context) if request.require_grounding else []
        grounded = not ungrounded
        if ungrounded:
            self.signals.emit(
                SignalType.EVENT,
                "llm.grounding.failed",
                request.tenant_id,
                request_id=request.request_id,
                ungrounded=len(ungrounded),
            )

        # 10. Cache storage — only what is grounded. The stage is entered
        # before the result is built so `stages_run` reports the full ten;
        # a result claiming nine stages would misreport its own pipeline.
        trace.enter(PipelineStage.CACHE_STORAGE)
        result = InferenceResult(
            request_id=request.request_id,
            tier_used=tier,
            output=output,
            cost=cost,
            tokens_used=tokens_used,
            cache_hit=False,
            grounded=grounded,
            ungrounded_claims=tuple(ungrounded),
            stages_run=tuple(trace.stages),
            sanitized_findings=tuple(findings),
        )
        self.cache.put(cache_key, result)

        self.budget.record_spend(request.tenant_id, cost, request.principal_id, tier.value)
        self._spend_by_tier[tier] = self._spend_by_tier.get(tier, 0.0) + cost
        self._journal(request, result, cache_hit=False)
        self.signals.emit(
            SignalType.METRIC,
            "llm.inference.cost",
            request.tenant_id,
            value=cost,
            tier=tier.value,
            tokens=tokens_used,
            grounded=grounded,
        )
        return result

    def _render(self, template: PromptTemplate, slots: dict[str, str], context: str) -> str:
        missing = [slot for slot in template.slots if slot not in slots]
        if missing:
            raise AgentOSError(f"template '{template.name}' is missing slots {missing}")
        body = template.body
        for name, value in slots.items():
            body = body.replace(f"{{{name}}}", value)
        return f"{body}\n\nContext:\n{context}" if context else body

    def _invoke_with_failover(
        self, request: InferenceRequest, rendered: str, template: PromptTemplate
    ) -> tuple[ModelTier, dict[str, Any], int, float]:
        """Walks the failover chain. Premium degrades rather than failing."""
        for tier in FAILOVER_CHAIN[request.tier]:
            backend = self.backends.get(tier)
            if backend is None or not backend.available():
                self._tier_failures[tier] = self._tier_failures.get(tier, 0) + 1
                continue
            try:
                output, tokens_used, cost = backend.complete(rendered, template.max_tokens)
            except Exception:
                self._tier_failures[tier] = self._tier_failures.get(tier, 0) + 1
                continue
            if tier != request.tier:
                self.signals.emit(
                    SignalType.EVENT,
                    "llm.tier.failover",
                    request.tenant_id,
                    requested=request.tier.value,
                    served=tier.value,
                )
            return tier, output, tokens_used, cost
        raise TierUnavailable(f"no tier in the failover chain for {request.tier.value} is available")

    # ---------------------------------------------------------------- Health

    def health(self) -> Mapping[str, Any]:
        """**Model Tier Health** (21B §20.5). Consumer: Observability Gateway."""
        return {
            "requests": self._requests,
            "tiers": {
                tier.value: {
                    "available": tier in self.backends and self.backends[tier].available(),
                    "local": tier.is_local,
                    "failures": self._tier_failures.get(tier, 0),
                    "spend": round(self._spend_by_tier.get(tier, 0.0), 6),
                }
                for tier in ModelTier
            },
            "cache": {
                "hit_rate": self.cache.hit_rate,
                "size": self.cache.size,
                "hits": self.cache.hits,
                "misses": self.cache.misses,
                # Non-zero means ungrounded answers were kept out of the cache.
                "refused_ungrounded": self.cache.refused,
            },
            "templates": len(self._templates),
            "journal_entries": len(self.journal),
            "journal_intact": self.journal.verify_chain(),
        }

    def _journal(self, request: InferenceRequest, result: InferenceResult, cache_hit: bool) -> None:
        self.journal.append(
            {
                "kind": "inference",
                "request_id": request.request_id,
                "tenant_id": request.tenant_id,
                "principal_id": request.principal_id,
                "template": request.template_name,
                "tier_requested": request.tier.value,
                "tier_used": result.tier_used.value,
                "cost": result.cost,
                "tokens": result.tokens_used,
                "cache_hit": cache_hit,
                "grounded": result.grounded,
                "sanitized_findings": len(result.sanitized_findings),
            }
        )


def _claims_of(output: dict[str, Any]) -> list[str]:
    """Extracts factual claims from a structured response for grounding.

    A response declaring no claims is trivially grounded, which is correct:
    grounding validates assertions, and a response that asserts nothing has
    nothing to fabricate.
    """
    claims = output.get("claims")
    if isinstance(claims, list):
        return [str(c) for c in claims]
    text = output.get("text")
    if isinstance(text, str) and text.strip():
        return [text]
    return []
