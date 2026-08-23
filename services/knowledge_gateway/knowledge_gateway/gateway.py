"""Knowledge Gateway — the seven Public Interfaces of 21B §17.5.

| 21B §17.5 interface      | Method                    |
|--------------------------|---------------------------|
| Belief Query             | `query`                   |
| Graph Traversal          | `traverse`                |
| Hypothesis Submission    | `submit`                  |
| Contradiction Query      | `contradictions_for`      |
| Ontology Query           | `query_ontology`          |
| Ontology Change Proposal | `propose_ontology_change` |
| Knowledge Health         | `health`                  |

The **confidence boundary** is unique to this Gateway among the eleven
(21B §17.16). It blocks consumption of beliefs below the consumer's declared
threshold, and it is the mechanism by which uncertainty is prevented from
propagating silently into commitment.

`10.6.6`: the Learning Model may not insert beliefs directly. Every belief
enters through `submit` and travels the full pipeline; there is no back door,
and `promote` refuses anything that has not been validated and integrated.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol

from core.exceptions import AgentOSError, NotFoundError
from kernel.journal import ImmutableJournal
from kernel.lifecycle import LifecycleStateMachine
from kernel.signals import SignalEmitter, SignalType
from knowledge_gateway.beliefs import (
    BELIEF_TRANSITIONS,
    HYPOTHESIS_CEILING,
    Belief,
    BeliefRecord,
    BeliefSensitivity,
    BeliefState,
    ConfidenceBand,
    Contradiction,
    ReconciliationStrategy,
    RelationType,
)
from knowledge_gateway.graph import GraphEngine, OntologyManager, OntologyProposal
from knowledge_gateway.pipeline import (
    ContradictionDetector,
    EpistemicFailure,
    ExtractionEngine,
    HypothesisQuarantined,
    HypothesisStore,
    ReconciliationEngine,
    ValidationEngine,
    revalidation_interval,
)


class KnowledgeAccessDenied(AgentOSError):
    """A boundary of 10.10 blocked the operation."""


class PromotionBlocked(AgentOSError):
    """10 rule 4 — no promotion while an unresolved contradiction stands."""


class KnowledgeAuthorizer(Protocol):
    """What the Gateway needs from the Security Gateway (21B §17.6)."""

    def may_query(self, token: str, tenant_id: str, sensitivity: str) -> bool: ...

    def may_submit(self, token: str, tenant_id: str, belief_type: str) -> bool: ...

    def principal_of(self, token: str) -> tuple[str, str]: ...

    def is_human(self, principal_id: str) -> bool: ...


class MemorySource(Protocol):
    """The evidentiary substrate the Extraction Engine draws on (21B §17.6).

    A Protocol so the Knowledge Gateway depends on the *shape* of memory
    retrieval rather than the Memory Gateway's internals. The concrete adapter
    lives in `memory_adapter.py`, keeping the permitted Layer-2 intra-layer
    edge visible in one file.
    """

    def confidence_of(self, token: str, memory_id: str) -> float | None: ...


@dataclass(frozen=True)
class BeliefAnswer:
    """One queried belief, carrying its own uncertainty qualification.

    21B §17.10: "Consumers must propagate uncertainty. A belief at 0.75
    confidence is provisional and must be treated as such downstream;
    suppression of that qualification is a conformance violation." The
    qualification therefore travels *in* the answer rather than being
    something a consumer must remember to look up.
    """

    record: BeliefRecord
    band: ConfidenceBand
    provisional: bool

    @property
    def belief_id(self) -> str:
        return self.record.belief_id

    @property
    def statement(self) -> str:
        return self.record.belief.statement

    @property
    def confidence(self) -> float:
        return self.record.confidence


@dataclass
class KnowledgeGateway:
    """Layer 2. Maintains the organization's body of validated belief (21B §17.1)."""

    authorizer: KnowledgeAuthorizer
    memory: MemorySource
    signals: SignalEmitter
    now: Callable[[], datetime] = field(default=lambda: datetime.now(UTC))
    known_types: set[str] | None = None

    def __post_init__(self) -> None:
        self.hypotheses = HypothesisStore()
        self.extraction = ExtractionEngine(store=self.hypotheses, now=self.now)
        self.validation = ValidationEngine(store=self.hypotheses, now=self.now, known_types=self.known_types)
        self.graph = GraphEngine(now=self.now)
        self.ontology = OntologyManager(is_human=self.authorizer.is_human, now=self.now)
        self.detector = ContradictionDetector(graph=self.graph, now=self.now)
        self.reconciliation = ReconciliationEngine(detector=self.detector)
        self.journal = ImmutableJournal()
        self._beliefs: dict[str, BeliefRecord] = {}
        self._suspended_extractors: set[str] = set()

    # ------------------------------------------------------------ Submission

    def submit(self, token: str, belief: Belief) -> BeliefRecord:
        """**Hypothesis Submission** (21B §17.5). Consumers: Learning, extractors, humans.

        The only entrance to the belief set. 10.6.6 forbids the Learning Model
        inserting beliefs directly, so everything arrives here as a hypothesis
        and earns its way forward.
        """
        principal_id, principal_tenant = self.authorizer.principal_of(token)
        if principal_tenant != belief.tenant_id:
            self._deny(principal_id, belief.tenant_id, "tenant", "hypothesis submission across tenants")
        if not self.authorizer.may_submit(token, belief.tenant_id, belief.belief_type):
            self._deny(principal_id, belief.tenant_id, "scope", f"submission of '{belief.belief_type}'")
        if belief.extracted_by in self._suspended_extractors:
            raise EpistemicFailure(
                f"extractor '{belief.extracted_by}' is suspended pending review (10.23.3)",
                extractor=belief.extracted_by,
            )

        # Evidentiary sufficiency asks whether the cited memory is itself
        # validated and attributable (10.14.1), which only Memory can answer.
        for citation in belief.evidence:
            actual = self.memory.confidence_of(token, citation.memory_id)
            if actual is None:
                self._suspend_extractor(belief.extracted_by, f"cited memory '{citation.memory_id}' does not exist")
                raise EpistemicFailure(
                    f"cited memory '{citation.memory_id}' does not exist; the evidentiary basis is fabricated",
                    extractor=belief.extracted_by,
                )

        record = self.extraction.extract(belief)
        self._journal(record, "extracted", extractor=belief.extracted_by, evidence=len(belief.evidence))
        return record

    def validate(self, belief_id: str, confidence: float) -> BeliefRecord:
        """Runs the four validation dimensions and assigns authoritative confidence."""
        record = self._pending(belief_id)
        try:
            self.validation.validate(record, confidence)
        except HypothesisQuarantined as quarantined:
            self._journal(record, "quarantined", reason=quarantined.reason)
            self.signals.emit(
                SignalType.EVENT,
                "knowledge.hypothesis.quarantined",
                record.belief.tenant_id,
                belief_id=belief_id,
                reason=quarantined.reason,
            )
            raise
        self._journal(record, "validated", confidence=record.confidence, band=record.band.value)
        return record

    def integrate(self, belief_id: str, relations: list[tuple[str, RelationType]]) -> BeliefRecord:
        """Links a validated belief into the ontology and graph (10.7.4)."""
        record = self._pending(belief_id)
        if record.state != BeliefState.VALIDATED:
            raise AgentOSError(f"belief '{belief_id}' is {record.state.value}; only a Validated belief integrates")
        if not relations:
            raise AgentOSError(f"belief '{belief_id}' has no relations; an unlinked belief is isolated (10.7.4)")
        for target_id, relation in relations:
            if target_id not in self._beliefs:
                raise NotFoundError(f"relation target '{target_id}' is not a known belief")
            self.graph.link(belief_id, target_id, relation)
            if relation == RelationType.CONTRADICTORY:
                self.detector.record(belief_id, target_id, "declared at integration")
        self._journal(record, "integrated", relations=len(relations))
        return record

    def promote(self, belief_id: str, approved_by: str | None = None) -> BeliefRecord:
        """Validated → Canonical. Blocked by any unresolved contradiction (10.7.5).

        Restricted beliefs additionally require human approval (10.8.2), and
        Axiomatic confidence requires human ratification (10.14.2).
        """
        record = self._pending(belief_id)
        if record.state != BeliefState.VALIDATED:
            raise PromotionBlocked(f"belief '{belief_id}' is {record.state.value}, not Validated")
        if not self.graph.is_linked(belief_id):
            raise PromotionBlocked(f"belief '{belief_id}' is not integrated; promotion requires integration (10.7.5)")
        if self.detector.has_unresolved(belief_id):
            raise PromotionBlocked(
                f"belief '{belief_id}' has an unresolved contradiction; no canonical belief may remain "
                "active against one (10 rule 4)"
            )
        if record.belief.sensitivity == BeliefSensitivity.RESTRICTED and not self._human_approved(approved_by):
            raise PromotionBlocked(f"belief '{belief_id}' is Restricted; promotion requires human approval (10.8.2)")
        if record.band == ConfidenceBand.AXIOMATIC and not self._human_approved(approved_by):
            raise PromotionBlocked(
                f"belief '{belief_id}' is Axiomatic at {record.confidence}; that band requires human "
                "ratification (10.14.2)"
            )

        self.hypotheses.take(belief_id)
        self._transition(record, BeliefState.CANONICAL)
        self._beliefs[belief_id] = record
        self._journal(record, "promoted", approved_by=approved_by)
        self.signals.emit(
            SignalType.METRIC,
            "knowledge.belief.confidence",
            record.belief.tenant_id,
            value=record.confidence,
            belief_type=record.belief.belief_type,
            band=record.band.value,
        )
        return record

    # ----------------------------------------------------------------- Query

    def query(
        self,
        token: str,
        tenant_id: str,
        belief_type: str | None = None,
        min_confidence: float = HYPOTHESIS_CEILING,
        max_sensitivity: BeliefSensitivity = BeliefSensitivity.TENANT_SCOPED,
        limit: int | None = None,
    ) -> list[BeliefAnswer]:
        """**Belief Query** (21B §17.5): scoped, confidence-filtered canonical retrieval.

        `min_confidence` is the consumer's declared threshold — the confidence
        boundary of 10.6.3. It defaults to the 0.60 floor of 10 rule 9 rather
        than to zero, so a caller that forgets to declare one still cannot
        receive sub-threshold belief.
        """
        principal_id, principal_tenant = self.authorizer.principal_of(token)
        if principal_tenant != tenant_id:
            self._deny(principal_id, tenant_id, "tenant", "belief query across tenants")
        if not self.authorizer.may_query(token, tenant_id, max_sensitivity.value):
            self._deny(principal_id, tenant_id, "scope", f"query at sensitivity '{max_sensitivity.value}'")
        if min_confidence < HYPOTHESIS_CEILING:
            raise KnowledgeAccessDenied(
                f"requested threshold {min_confidence} is below {HYPOTHESIS_CEILING}; nothing below that "
                "is presented as canonical (10 rule 9)"
            )

        ceiling = _SENSITIVITY_ORDER[max_sensitivity]
        answers = [
            BeliefAnswer(record=record, band=record.band, provisional=record.is_provisional)
            for record in self._beliefs.values()
            if record.is_reasonable
            and record.belief.tenant_id == tenant_id
            and _SENSITIVITY_ORDER[record.belief.sensitivity] <= ceiling
            and record.confidence >= min_confidence
            and (belief_type is None or record.belief.belief_type == belief_type)
        ]
        answers.sort(key=lambda a: a.confidence, reverse=True)
        if limit is not None:
            answers = answers[:limit]
        for answer in answers:
            answer.record.query_count += 1
        return answers

    def traverse(self, token: str, belief_id: str, depth: int = 3) -> list[str]:
        """**Graph Traversal** (21B §17.5), within permission scope."""
        _principal_id, principal_tenant = self.authorizer.principal_of(token)

        def visible(candidate_id: str) -> bool:
            record = self._beliefs.get(candidate_id)
            return record is not None and record.belief.tenant_id == principal_tenant and record.is_reasonable

        return self.graph.traverse(belief_id, depth=depth, visible=visible)

    def contradictions_for(self, belief_id: str) -> list[Contradiction]:
        """**Contradiction Query** (21B §17.5). Consumers: Decision, Governance."""
        return self.detector.unresolved_for(belief_id)

    def query_ontology(self) -> Mapping[str, Any]:
        """**Ontology Query** (21B §17.5). Consumers: all reasoning consumers."""
        return self.ontology.query()

    def propose_ontology_change(
        self, proposal_id: str, kind: str, name: str, proposed_by: str, rationale: str
    ) -> OntologyProposal:
        """**Ontology Change Proposal** (21B §17.5). Ratification is a separate act."""
        proposal = self.ontology.propose(proposal_id, kind, name, proposed_by, rationale)
        self.journal.append({"kind": "ontology_proposed", "proposal_id": proposal_id, "name": name, "by": proposed_by})
        return proposal

    def ratify_ontology_change(self, proposal_id: str, ratified_by: str) -> OntologyProposal:
        """Adopts a proposal. Human-only (10.16.4)."""
        proposal = self.ontology.ratify(proposal_id, ratified_by)
        self.journal.append({"kind": "ontology_ratified", "proposal_id": proposal_id, "by": ratified_by})
        return proposal

    # ---------------------------------------------- Contradiction lifecycle

    def detect_contradiction(self, left_id: str, right_id: str, detail: str) -> Contradiction:
        """Records a contradiction and moves both canonical beliefs out of active use.

        10 rule 4 permits no canonical belief to remain active against an
        unresolved contradiction, so detection *demotes* — it does not merely
        annotate.
        """
        left, right = self.get(left_id), self.get(right_id)
        contradiction = self.detector.record(left_id, right_id, detail)
        for record in (left, right):
            if record.state == BeliefState.CANONICAL:
                self._transition(record, BeliefState.CONTRADICTED)
                self._journal(record, "contradicted", contradiction_id=contradiction.contradiction_id)
        self.signals.emit(
            SignalType.EVENT,
            "knowledge.contradiction.detected",
            left.belief.tenant_id,
            contradiction_id=contradiction.contradiction_id,
            left=left_id,
            right=right_id,
        )
        return contradiction

    def reconcile(
        self,
        contradiction_id: str,
        resolved_by: str,
        cross_business: bool = False,
    ) -> tuple[Contradiction, ReconciliationStrategy]:
        """Applies a reconciliation strategy, or routes to human arbitration (10.15.2).

        Arbitration is not applied here: the engine reports that a human must
        decide, and `arbitrate` records what they decided. Automating the
        arbitration would defeat the point of mandating it.
        """
        contradiction = self.detector.get(contradiction_id)
        left = self.get(contradiction.left_belief_id)
        right = self.get(contradiction.right_belief_id)
        strategy = self.reconciliation.strategy_for(contradiction, left, right, cross_business)

        if strategy == ReconciliationStrategy.HUMAN_ARBITRATION:
            self.signals.emit(
                SignalType.EVENT,
                "knowledge.arbitration.required",
                left.belief.tenant_id,
                contradiction_id=contradiction_id,
            )
            return contradiction, strategy

        if strategy == ReconciliationStrategy.SUPERSESSION:
            loser, winner = (left, right) if left.confidence < right.confidence else (right, left)
            self._supersede(loser, winner)
        elif strategy == ReconciliationStrategy.CONFIDENCE_ADJUSTMENT:
            for record in (left, right):
                self._adjust_confidence(record, round(record.confidence * 0.9, 4), "contradiction unresolved")
                self._restore(record)
        else:  # SCOPE_NARROWING — both true, different contexts
            for record in (left, right):
                self._restore(record)

        resolved = self.detector.resolve(contradiction_id, strategy, resolved_by)
        self.journal.append(
            {
                "kind": "reconciled",
                "contradiction_id": contradiction_id,
                "strategy": strategy.value,
                "resolved_by": resolved_by,
            }
        )
        return resolved, strategy

    def arbitrate(
        self,
        contradiction_id: str,
        arbiter_id: str,
        upheld_belief_id: str,
    ) -> Contradiction:
        """Records a binding human resolution with Class D authority (10.15.3).

        Only a human may arbitrate. The resolution is logged as a new
        knowledge entry rather than as an edit to either belief.
        """
        if not self.authorizer.is_human(arbiter_id):
            raise KnowledgeAccessDenied(
                f"'{arbiter_id}' is not a Human principal; arbitration is a Class D act (10.15.3)"
            )
        contradiction = self.detector.get(contradiction_id)
        left = self.get(contradiction.left_belief_id)
        right = self.get(contradiction.right_belief_id)
        if upheld_belief_id not in (left.belief_id, right.belief_id):
            raise AgentOSError(f"'{upheld_belief_id}' is not party to contradiction '{contradiction_id}'")

        upheld, overruled = (left, right) if upheld_belief_id == left.belief_id else (right, left)
        self._supersede(overruled, upheld)
        resolved = self.detector.resolve(contradiction_id, ReconciliationStrategy.HUMAN_ARBITRATION, arbiter_id)
        self.journal.append(
            {
                "kind": "arbitrated",
                "contradiction_id": contradiction_id,
                "arbiter": arbiter_id,
                "upheld": upheld.belief_id,
                "overruled": overruled.belief_id,
                "authority": "class_d",
            }
        )
        return resolved

    # -------------------------------------------- Revalidation & deprecation

    def revalidate(self, belief_id: str, confidence: float, domain: str = "operational") -> BeliefRecord:
        """Continuous re-evaluation against new evidence and elapsed time (10.14.3).

        Can raise confidence, lower it, or trigger deprecation when the
        falsifiability conditions are met.
        """
        record = self.get(belief_id)
        self._adjust_confidence(record, confidence, "revalidation")
        record.last_revalidated_at = self.now()
        record.valid_until = self.now() + revalidation_interval(domain)
        if confidence < HYPOTHESIS_CEILING and record.state == BeliefState.CANONICAL:
            self.deprecate(belief_id, f"revalidation dropped confidence to {confidence}, below {HYPOTHESIS_CEILING}")
        return record

    def due_for_revalidation(self, domain: str = "operational") -> list[BeliefRecord]:
        interval = revalidation_interval(domain)
        now = self.now()
        return [
            record
            for record in self._beliefs.values()
            if record.state == BeliefState.CANONICAL and record.is_due_for_revalidation(now, interval)
        ]

    def deprecate(self, belief_id: str, justification: str) -> BeliefRecord:
        """Marks a belief false or obsolete. Never deletes (10.7.8, 10 rule 18).

        A justification is required and is linked via lineage — 10 rule 18
        does not permit an unexplained deprecation.
        """
        if not justification.strip():
            raise AgentOSError("deprecation requires a justification entry linked via lineage (10 rule 18)")
        record = self.get(belief_id)
        record.deprecation_justification = justification
        self._transition(record, BeliefState.DEPRECATED)
        self._journal(record, "deprecated", justification=justification)
        return record

    def _supersede(self, loser: BeliefRecord, winner: BeliefRecord) -> None:
        """Links a superseded belief to its successor (10.17.4, no dangling refs)."""
        loser.superseded_by = winner.belief_id
        winner.supersedes = loser.belief_id
        self.graph.link(winner.belief_id, loser.belief_id, RelationType.SUPERSEDES)
        self._transition(loser, BeliefState.SUPERSEDED)
        self._restore(winner)
        self._journal(loser, "superseded", by=winner.belief_id)

    def _restore(self, record: BeliefRecord) -> None:
        """Contradicted → Canonical once reconciliation clears the conflict."""
        if record.state == BeliefState.CONTRADICTED:
            self._transition(record, BeliefState.CANONICAL)

    def _adjust_confidence(self, record: BeliefRecord, confidence: float, reason: str) -> None:
        record.confidence = round(confidence, 4)
        record.confidence_history.append((self.now(), record.confidence))
        self._journal(record, "confidence_adjusted", confidence=record.confidence, reason=reason)

    # ------------------------------------------------------------- Utilities

    def get(self, belief_id: str) -> BeliefRecord:
        record = self._beliefs.get(belief_id)
        if record is None:
            raise NotFoundError(f"belief '{belief_id}' is not in the belief set")
        return record

    def health(self) -> Mapping[str, Any]:
        """**Knowledge Health** (21B §17.5) — the four metric families of 10.22.1."""
        records = list(self._beliefs.values())
        canonical = [r for r in records if r.state == BeliefState.CANONICAL]
        by_state: dict[str, int] = {}
        for record in records:
            by_state[record.state.value] = by_state.get(record.state.value, 0) + 1
        integrity = self.graph.check_integrity(self._beliefs)
        return {
            "epistemic": {
                "contradiction_rate": round(self.detector.unresolved_count / len(records), 4) if records else 0.0,
                "unresolved_contradictions": self.detector.unresolved_count,
                "mean_confidence": (
                    round(sum(r.confidence for r in canonical) / len(canonical), 4) if canonical else 0.0
                ),
                "validation_backlog": self.hypotheses.backlog,
                "quarantined": len(self.hypotheses.quarantined()),
            },
            "graph": {
                "edges": self.graph.edge_count,
                "relationship_distribution": self.graph.relationship_distribution(),
                "integrity_violations": [v.constraint for v in integrity],
            },
            "operational": {
                "beliefs": len(records),
                "by_state": by_state,
                "extracted": self.extraction.extracted,
                "filtered": self.extraction.filtered,
                "suspended_extractors": sorted(self._suspended_extractors),
            },
            "consumer": {"queries": sum(r.query_count for r in records)},
            "journal_entries": len(self.journal),
            "journal_intact": self.journal.verify_chain(),
        }

    def _pending(self, belief_id: str) -> BeliefRecord:
        for record in self.hypotheses.pending():
            if record.belief_id == belief_id:
                return record
        raise NotFoundError(f"hypothesis '{belief_id}' is not pending validation")

    def _human_approved(self, approved_by: str | None) -> bool:
        return approved_by is not None and self.authorizer.is_human(approved_by)

    def _suspend_extractor(self, extractor: str, reason: str) -> None:
        """10.23.3 — an epistemic failure suspends the extractor with immediate alert."""
        self._suspended_extractors.add(extractor)
        self.journal.append({"kind": "extractor_suspended", "extractor": extractor, "reason": reason})

    def reinstate_extractor(self, extractor: str, reinstated_by: str) -> None:
        """Human-only reinstatement after review."""
        if not self.authorizer.is_human(reinstated_by):
            raise KnowledgeAccessDenied(f"'{reinstated_by}' is not a Human principal")
        self._suspended_extractors.discard(extractor)
        self.journal.append({"kind": "extractor_reinstated", "extractor": extractor, "by": reinstated_by})

    def _transition(self, record: BeliefRecord, target: BeliefState) -> None:
        machine = LifecycleStateMachine(transitions=dict(BELIEF_TRANSITIONS), state=record.state)
        machine.transition(target)
        record.state = target

    def _journal(self, record: BeliefRecord, action: str, **detail: Any) -> None:
        self.journal.append(
            {
                "kind": "belief",
                "action": action,
                "belief_id": record.belief_id,
                "belief_type": record.belief.belief_type,
                "tenant_id": record.belief.tenant_id,
                "state": record.state.value,
                "confidence": record.confidence,
                **detail,
            }
        )

    def _deny(self, principal_id: str, tenant_id: str, boundary: str, attempted: str) -> None:
        self.journal.append(
            {
                "kind": "boundary_violation",
                "boundary": boundary,
                "principal_id": principal_id,
                "attempted": attempted,
            }
        )
        raise KnowledgeAccessDenied(
            f"principal '{principal_id}' violated the {boundary} boundary attempting {attempted} (10.10)"
        )


_SENSITIVITY_ORDER: dict[BeliefSensitivity, int] = {
    BeliefSensitivity.PUBLIC: 0,
    BeliefSensitivity.TENANT_SCOPED: 1,
    BeliefSensitivity.RESTRICTED: 2,
}

__all__ = [
    "KnowledgeGateway",
    "KnowledgeAuthorizer",
    "KnowledgeAccessDenied",
    "PromotionBlocked",
    "MemorySource",
    "BeliefAnswer",
]
