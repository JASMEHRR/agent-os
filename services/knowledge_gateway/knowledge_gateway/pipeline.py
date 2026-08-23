"""Extraction, validation, contradiction and reconciliation (21B §17.3).

The pipeline is Extraction → Hypothesis Formation → Validation → Integration →
Promotion → Active Use → Revalidation → Deprecation → Archival → Disposition.

Two boundaries in it are hard, and both are enforced by construction:

**Hypotheses are never visible to reasoner consumers** (10.7.2, 10 rule 10).
The Hypothesis Store is a separate object from the belief set, and the
Gateway's query path reads only the belief set. There is no filter to
misconfigure.

**Promotion is not automatic upon validation** (10.7.5). The Promotion
Controller blocks on unresolved contradiction — 10 rule 4 states that no
canonical belief may remain active against an unresolved contradiction, so a
validated belief that conflicts with a canonical one is held, not promoted.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from core.exceptions import AgentOSError, ValidationError
from knowledge_gateway.beliefs import (
    ARBITRATION_CONFIDENCE,
    HYPOTHESIS_CEILING,
    Belief,
    BeliefRecord,
    BeliefSensitivity,
    BeliefState,
    Contradiction,
    ReconciliationStrategy,
    RelationType,
)
from knowledge_gateway.graph import GraphEngine

#: [Engineering Decision] 10.14.3 makes revalidation frequency domain-dependent
#: without publishing intervals. Market knowledge is revalidated frequently,
#: definitional knowledge rarely; these are the starting cadences.
REVALIDATION_INTERVALS: dict[str, timedelta] = {
    "market": timedelta(days=7),
    "operational": timedelta(days=30),
    "strategic": timedelta(days=90),
    "definitional": timedelta(days=365),
}
DEFAULT_REVALIDATION_INTERVAL = timedelta(days=30)

#: [Engineering Decision] 10.15.3 requires arbitration after "defined attempts"
#: of automated reconciliation without defining the count.
MAX_AUTOMATED_RECONCILIATION_ATTEMPTS = 3


class EpistemicFailure(AgentOSError):
    """The failure category unique to this subsystem (10.23.3, 21B §17.9).

    The Kernel's five-category taxonomy is extended here **by constitutional
    provision, not by implementation choice**. The response is to quarantine
    the affected beliefs and suspend the extractor, with immediate alert.
    """

    def __init__(self, detail: str, extractor: str | None = None):
        super().__init__(f"epistemic failure: {detail}")
        self.extractor = extractor


class HypothesisQuarantined(Exception):
    """Validation failed. Held for review, never destroyed (10.14.4)."""

    def __init__(self, belief_id: str, reason: str):
        super().__init__(f"hypothesis '{belief_id}' quarantined: {reason}")
        self.belief_id = belief_id
        self.reason = reason


@dataclass
class HypothesisStore:
    """Holds provisional beliefs during evaluation. Invisible to reasoners.

    A separate store rather than a state flag on the belief set, so "a
    hypothesis leaked to a reasoner" is not a bug that a wrong filter could
    cause — the query path never reads this object at all.
    """

    _pending: dict[str, BeliefRecord] = field(default_factory=dict, init=False)
    _quarantined: dict[str, BeliefRecord] = field(default_factory=dict, init=False)
    _rejected: dict[str, str] = field(default_factory=dict, init=False)

    def hold(self, record: BeliefRecord) -> BeliefRecord:
        self._pending[record.belief_id] = record
        return record

    def quarantine(self, record: BeliefRecord, reason: str) -> BeliefRecord:
        record.quarantine_reason = reason
        self._pending.pop(record.belief_id, None)
        self._quarantined[record.belief_id] = record
        return record

    def take(self, belief_id: str) -> BeliefRecord:
        """Removes a hypothesis from the pipeline as it graduates to the belief set."""
        record = self._pending.pop(belief_id, None)
        if record is None:
            raise ValidationError(f"hypothesis '{belief_id}' is not pending")
        return record

    def resubmit(self, belief_id: str) -> BeliefRecord:
        """A corrected hypothesis returns to the queue (10.14.4)."""
        record = self._quarantined.pop(belief_id, None)
        if record is None:
            raise ValidationError(f"hypothesis '{belief_id}' is not quarantined")
        record.quarantine_reason = None
        return self.hold(record)

    def reject(self, belief_id: str, justification: str) -> None:
        """Permanent rejection with the justification logged (10.14.4)."""
        self._quarantined.pop(belief_id, None)
        self._pending.pop(belief_id, None)
        self._rejected[belief_id] = justification

    def pending(self) -> list[BeliefRecord]:
        return list(self._pending.values())

    def quarantined(self) -> list[BeliefRecord]:
        return list(self._quarantined.values())

    @property
    def backlog(self) -> int:
        """Validation backlog depth — an Epistemic Health metric (10.22.1)."""
        return len(self._pending)


@dataclass
class ExtractionEngine:
    """Distils candidate beliefs from memory, with a relevance filter (10.7.1).

    "Not all memory is worth extracting" — the filter exists to prevent
    knowledge bloat, which 10.15 names as a growth failure mode. Extraction is
    an epistemic act, so the minimum evidence bar is checked here rather than
    deferred to validation: a candidate with no support is not a hypothesis.
    """

    store: HypothesisStore
    now: Callable[[], datetime] = field(default=lambda: datetime.now(UTC))
    #: Minimum supporting memory entries before a candidate is worth evaluating.
    minimum_evidence: int = 1
    #: Minimum confidence of the *source memory* an extraction may rest on.
    minimum_memory_confidence: float = 0.5
    extracted: int = field(default=0, init=False)
    filtered: int = field(default=0, init=False)

    def extract(self, belief: Belief) -> BeliefRecord:
        """Forms a hypothesis, or refuses the candidate as not worth holding."""
        if len(belief.evidence) < self.minimum_evidence:
            self.filtered += 1
            raise EpistemicFailure(
                f"candidate '{belief.belief_id}' cites {len(belief.evidence)} memory entries; "
                f"at least {self.minimum_evidence} is required — a belief without evidence is speculation (10.2.1)",
                extractor=belief.extracted_by,
            )
        weak = [e for e in belief.evidence if e.memory_confidence < self.minimum_memory_confidence]
        if weak:
            self.filtered += 1
            raise EpistemicFailure(
                f"candidate '{belief.belief_id}' rests on memory below "
                f"{self.minimum_memory_confidence} confidence: {[e.memory_id for e in weak]}",
                extractor=belief.extracted_by,
            )
        self.extracted += 1
        return self.store.hold(BeliefRecord(belief=belief, formed_at=self.now(), state=BeliefState.HYPOTHESIS))


@dataclass
class ValidationEngine:
    """Assesses hypotheses across the four dimensions of 10.14.1."""

    store: HypothesisStore
    now: Callable[[], datetime] = field(default=lambda: datetime.now(UTC))
    #: Resolves whether a belief type has a registered schema.
    known_types: set[str] | None = None
    default_validity: timedelta = timedelta(days=180)

    def validate(self, record: BeliefRecord, confidence: float) -> BeliefRecord:
        """Assigns the authoritative confidence, or quarantines (10.14.3, 10.14.4)."""
        belief = record.belief
        reasons: list[str] = []

        # 1. Evidentiary sufficiency.
        if not belief.evidence:
            reasons.append("no evidentiary citation")

        # 2. Schema conformance.
        if self.known_types is not None and belief.belief_type not in self.known_types:
            reasons.append(f"belief type '{belief.belief_type}' is not a registered knowledge type")

        # 3. Falsifiability test.
        if not belief.falsifiability.is_specific():
            reasons.append("invalidation conditions are not specific and observable (10.2.1 — dogma)")
        if belief.falsifiability.review_by <= self.now():
            reasons.append("falsifiability conditions are not bounded in the future")

        # 4. Confidence floor for Hypothesis -> Validated (10.8.2).
        if not 0.0 <= confidence <= 1.0:
            reasons.append(f"confidence {confidence} is outside 0.0-1.0")
        elif confidence < HYPOTHESIS_CEILING:
            reasons.append(
                f"confidence {confidence} is below the {HYPOTHESIS_CEILING} required for validation (10.8.2)"
            )

        if reasons:
            self.store.quarantine(record, "; ".join(reasons))
            raise HypothesisQuarantined(record.belief_id, "; ".join(reasons))

        record.confidence = round(confidence, 4)
        record.confidence_history.append((self.now(), record.confidence))
        record.valid_until = self.now() + self.default_validity
        record.state = BeliefState.VALIDATED
        return record


@dataclass
class ContradictionDetector:
    """Continuously scans the canonical set for incompatible assertions (10.15.1)."""

    graph: GraphEngine
    now: Callable[[], datetime] = field(default=lambda: datetime.now(UTC))
    _contradictions: dict[str, Contradiction] = field(default_factory=dict, init=False)
    _seq: int = field(default=0, init=False)

    def record(self, left_id: str, right_id: str, detail: str) -> Contradiction:
        """Registers a contradiction and links it in the graph as a typed edge."""
        if left_id == right_id:
            raise ValidationError("a belief cannot contradict itself directly (10.17.4)")
        self._seq += 1
        contradiction = Contradiction(
            contradiction_id=f"contra-{self._seq:06d}",
            left_belief_id=left_id,
            right_belief_id=right_id,
            detected_at=self.now(),
            detail=detail,
        )
        self._contradictions[contradiction.contradiction_id] = contradiction
        self.graph.link(left_id, right_id, RelationType.CONTRADICTORY)
        return contradiction

    def unresolved_for(self, belief_id: str) -> list[Contradiction]:
        return [
            c
            for c in self._contradictions.values()
            if not c.is_resolved and belief_id in (c.left_belief_id, c.right_belief_id)
        ]

    def has_unresolved(self, belief_id: str) -> bool:
        return bool(self.unresolved_for(belief_id))

    def resolve(
        self,
        contradiction_id: str,
        strategy: ReconciliationStrategy,
        resolved_by: str,
    ) -> Contradiction:
        """Appends a resolution. The original record is immutable (21B §17.8)."""
        original = self._contradictions.get(contradiction_id)
        if original is None:
            raise ValidationError(f"contradiction '{contradiction_id}' does not exist")
        resolved = Contradiction(
            contradiction_id=original.contradiction_id,
            left_belief_id=original.left_belief_id,
            right_belief_id=original.right_belief_id,
            detected_at=original.detected_at,
            detail=original.detail,
            resolved_at=self.now(),
            strategy=strategy,
            resolved_by=resolved_by,
        )
        self._contradictions[contradiction_id] = resolved
        return resolved

    def get(self, contradiction_id: str) -> Contradiction:
        contradiction = self._contradictions.get(contradiction_id)
        if contradiction is None:
            raise ValidationError(f"contradiction '{contradiction_id}' does not exist")
        return contradiction

    def all_contradictions(self) -> list[Contradiction]:
        return list(self._contradictions.values())

    @property
    def unresolved_count(self) -> int:
        return sum(1 for c in self._contradictions.values() if not c.is_resolved)


@dataclass
class ReconciliationEngine:
    """Applies the four strategies of 10.15.2, or routes to arbitration.

    Arbitration is not a fallback the engine may skip. 10.15.3 makes it
    mandatory in four situations, and `strategy_for` returns HUMAN_ARBITRATION
    in every one of them regardless of what the caller would prefer.
    """

    detector: ContradictionDetector
    max_attempts: int = MAX_AUTOMATED_RECONCILIATION_ATTEMPTS
    _attempts: dict[str, int] = field(default_factory=dict, init=False)

    def strategy_for(
        self,
        contradiction: Contradiction,
        left: BeliefRecord,
        right: BeliefRecord,
        cross_business: bool = False,
    ) -> ReconciliationStrategy:
        """Chooses a strategy, honouring the mandatory-arbitration rules first."""
        attempts = self._attempts.get(contradiction.contradiction_id, 0)
        restricted = BeliefSensitivity.RESTRICTED in (left.belief.sensitivity, right.belief.sensitivity)

        if left.confidence >= ARBITRATION_CONFIDENCE and right.confidence >= ARBITRATION_CONFIDENCE:
            return ReconciliationStrategy.HUMAN_ARBITRATION
        if restricted:
            return ReconciliationStrategy.HUMAN_ARBITRATION
        if cross_business:
            return ReconciliationStrategy.HUMAN_ARBITRATION
        if attempts >= self.max_attempts:
            return ReconciliationStrategy.HUMAN_ARBITRATION

        self._attempts[contradiction.contradiction_id] = attempts + 1

        # Newer evidence clearly stronger: supersession. Comparable: adjust
        # confidence rather than pretending one side won.
        if abs(left.confidence - right.confidence) >= 0.15:
            return ReconciliationStrategy.SUPERSESSION
        if left.belief.business_id != right.belief.business_id:
            return ReconciliationStrategy.SCOPE_NARROWING
        return ReconciliationStrategy.CONFIDENCE_ADJUSTMENT

    def attempts_for(self, contradiction_id: str) -> int:
        return self._attempts.get(contradiction_id, 0)


def revalidation_interval(domain: str) -> timedelta:
    """Domain-dependent revalidation cadence (10.14.3)."""
    return REVALIDATION_INTERVALS.get(domain, DEFAULT_REVALIDATION_INTERVAL)
