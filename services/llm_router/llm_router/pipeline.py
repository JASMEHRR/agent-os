"""The ten-stage prompt pipeline (02.8.5) and model tiering (02.3.8).

21B §20.4: **"The prompt pipeline is fixed in order."** Ten stages — template
selection, context retrieval, context assembly, input sanitization, prompt
rendering, token budget check, invocation, output parsing, grounding
validation, cache storage.

Three orderings carry constitutional weight and the module enforces them
rather than documenting them:

- **Sanitization precedes rendering.** Untrusted context must not reach a
  rendered prompt unsanitized.
- **The budget check precedes invocation.** A request that cannot afford to
  run must not run.
- **Grounding validation precedes cache storage.** An ungrounded answer must
  never be cached, or the hallucination is served again for free.

`PipelineStage` is ordered and `PromptPipeline` asserts monotonic progress, so
a reordering is a test failure rather than a silent constitutional breach.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import IntEnum, StrEnum
from typing import Any

from core.exceptions import AgentOSError


class ModelTier(StrEnum):
    """Tiering of 02.3.8.

    `01.3.1` Local First holds because Nano and Standard may be fulfilled by
    locally-hosted capability with no external integration at all, and Premium
    "degrades to unavailable rather than to failure" (21B §20.4).
    """

    NANO = "nano"
    STANDARD = "standard"
    PREMIUM = "premium"

    @property
    def is_local(self) -> bool:
        return self in (ModelTier.NANO, ModelTier.STANDARD)


class PipelineStage(IntEnum):
    """The ten stages of 02.8.5, in their fixed order."""

    TEMPLATE_SELECTION = 1
    CONTEXT_RETRIEVAL = 2
    CONTEXT_ASSEMBLY = 3
    INPUT_SANITIZATION = 4
    PROMPT_RENDERING = 5
    TOKEN_BUDGET_CHECK = 6
    INVOCATION = 7
    OUTPUT_PARSING = 8
    GROUNDING_VALIDATION = 9
    CACHE_STORAGE = 10


class PipelineOrderViolation(AgentOSError):
    """A stage ran out of order. Reordering breaks a constitutional guarantee."""


class TokenBudgetExceeded(AgentOSError):
    """The assembled prompt exceeds the declared token budget (02.8.5 stage 6)."""


class GroundingFailure(AgentOSError):
    """A factual claim is not supported by its cited sources (21B §20.3)."""


class TierUnavailable(AgentOSError):
    """No tier in the failover chain is available."""


#: [Engineering Decision] 02.8.5 mandates sanitization without enumerating
#: patterns. These are the prompt-injection shapes worth refusing outright;
#: the list is a starting point, not a claim of completeness.
INJECTION_PATTERNS = (
    re.compile(r"ignore\s+(?:all\s+)?previous\s+instructions", re.IGNORECASE),
    re.compile(r"disregard\s+(?:the\s+)?above", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+", re.IGNORECASE),
    re.compile(r"<\s*/?\s*system\s*>", re.IGNORECASE),
)


@dataclass(frozen=True)
class PromptTemplate:
    """A named template with its slots and declared token budget."""

    name: str
    body: str
    slots: tuple[str, ...]
    max_tokens: int
    tier: ModelTier


@dataclass(frozen=True)
class ContextItem:
    """One retrieved piece of context, carrying where it came from.

    `source_id` is required because grounding validation checks claims against
    cited sources — context whose provenance is unknown cannot ground
    anything.
    """

    source_id: str
    content: str
    confidence: float


@dataclass(frozen=True)
class InferenceRequest:
    """What a consumer asks the Router for."""

    request_id: str
    template_name: str
    slots: dict[str, str]
    tenant_id: str
    principal_id: str
    tier: ModelTier = ModelTier.STANDARD
    max_cost: float = 1.0
    require_grounding: bool = True


@dataclass(frozen=True)
class InferenceResult:
    """What the Router returns, with its grounding and cost visible."""

    request_id: str
    tier_used: ModelTier
    output: dict[str, Any]
    cost: float
    tokens_used: int
    cache_hit: bool
    grounded: bool
    ungrounded_claims: tuple[str, ...]
    stages_run: tuple[PipelineStage, ...]
    sanitized_findings: tuple[str, ...]


def estimate_tokens(text: str) -> int:
    """[Engineering Decision] Four characters per token.

    A deliberately crude estimate: the real count is model-specific and the
    canonical stack's tokenizer is not wired in. It errs high on short strings
    rather than low, so the budget check is conservative.
    """
    return max(1, (len(text) + 3) // 4)


@dataclass
class Sanitizer:
    """Input sanitization, stage 4 — before rendering, never after."""

    patterns: Sequence[re.Pattern[str]] = field(default=INJECTION_PATTERNS)

    def sanitize(self, text: str) -> tuple[str, list[str]]:
        """Returns the cleaned text and what was found.

        Findings are returned rather than swallowed: 21B §19.11 counts
        sanitization failures as a security signal, and a silent scrub would
        make an attack invisible.
        """
        findings: list[str] = []
        cleaned = text
        for pattern in self.patterns:
            if pattern.search(cleaned):
                findings.append(pattern.pattern)
                cleaned = pattern.sub("[redacted]", cleaned)
        return cleaned, findings


@dataclass
class GroundingValidator:
    """Validates factual claims against cited sources (21B §20.3).

    Deliberately simple and deliberately conservative: a claim is grounded if
    it shares substantive vocabulary with some cited source. It will not catch
    a subtle fabrication, and saying so plainly is better than implying the
    check is stronger than it is — the point it *does* enforce is that an
    ungrounded answer never reaches the cache.
    """

    minimum_overlap: float = 0.3

    def validate(self, claims: Sequence[str], context: Sequence[ContextItem]) -> list[str]:
        if not context:
            return list(claims)
        vocabulary = {word for item in context for word in _significant_words(item.content)}
        ungrounded: list[str] = []
        for claim in claims:
            words = _significant_words(claim)
            if not words:
                continue
            overlap = len(words & vocabulary) / len(words)
            if overlap < self.minimum_overlap:
                ungrounded.append(claim)
        return ungrounded


def _significant_words(text: str) -> set[str]:
    stopwords = {
        "the",
        "a",
        "an",
        "is",
        "are",
        "was",
        "were",
        "and",
        "or",
        "but",
        "to",
        "of",
        "in",
        "on",
        "for",
        "with",
        "that",
        "this",
        "it",
        "as",
        "by",
        "at",
    }
    return {w for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in stopwords and len(w) > 2}


@dataclass
class ResponseCache:
    """Exact and semantic caches (21B §20.2).

    Only grounded responses are stored. An ungrounded answer that reached the
    cache would be served again at zero cost, turning one hallucination into a
    permanent one.
    """

    now: Callable[[], datetime] = field(default=lambda: datetime.now(UTC))
    ttl: timedelta = timedelta(hours=1)
    _entries: dict[str, tuple[InferenceResult, datetime]] = field(default_factory=dict, init=False)
    hits: int = field(default=0, init=False)
    misses: int = field(default=0, init=False)
    refused: int = field(default=0, init=False)

    @staticmethod
    def key(tenant_id: str, template: str, rendered: str) -> str:
        digest = hashlib.sha256(rendered.encode("utf-8")).hexdigest()[:32]
        return f"{tenant_id}:{template}:{digest}"

    def get(self, key: str) -> InferenceResult | None:
        cached = self._entries.get(key)
        if cached is None:
            self.misses += 1
            return None
        result, expiry = cached
        if self.now() >= expiry:
            del self._entries[key]
            self.misses += 1
            return None
        self.hits += 1
        return result

    def put(self, key: str, result: InferenceResult) -> bool:
        """Stores a grounded result. Refuses an ungrounded one."""
        if not result.grounded:
            self.refused += 1
            return False
        self._entries[key] = (result, self.now() + self.ttl)
        return True

    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return round(self.hits / total, 4) if total else 0.0

    @property
    def size(self) -> int:
        return len(self._entries)
