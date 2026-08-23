"""Belief identity, confidence bands, and lifecycle states (10.8, 10.14.2).

`10.2.1` sets the epistemic bar this module encodes in types: "A belief
without evidence is speculation. A belief without confidence is noise. A
belief that cannot be falsified is dogma. Knowledge rejects all three."

So a `Belief` cannot be constructed without evidence citations and
falsifiability conditions — both are required fields with no defaults. A
belief that could not name what would prove it wrong is not representable.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any

#: 10.14.2 Confidence Scoring bands, verbatim.
HYPOTHESIS_CEILING = 0.60
VALIDATED_CEILING = 0.80
CANONICAL_CEILING = 0.95

#: 10.15.3 — human arbitration is mandatory when both beliefs are at or above this.
ARBITRATION_CONFIDENCE = 0.85


class ConfidenceBand(StrEnum):
    """The four bands of 10.14.2."""

    HYPOTHESIS = "hypothesis"  # 0.00-0.59: not available for reasoning
    VALIDATED = "validated"  # 0.60-0.79: available, must be flagged provisional
    CANONICAL = "canonical"  # 0.80-0.94: standard basis for reasoning
    AXIOMATIC = "axiomatic"  # 0.95-1.00: requires human ratification

    @staticmethod
    def of(confidence: float) -> ConfidenceBand:
        if confidence < HYPOTHESIS_CEILING:
            return ConfidenceBand.HYPOTHESIS
        if confidence < VALIDATED_CEILING:
            return ConfidenceBand.VALIDATED
        if confidence < CANONICAL_CEILING:
            return ConfidenceBand.CANONICAL
        return ConfidenceBand.AXIOMATIC

    @property
    def is_provisional(self) -> bool:
        """10.14.2 — a Validated belief must be flagged as provisional downstream."""
        return self is ConfidenceBand.VALIDATED


class BeliefState(StrEnum):
    """Canonical states of 10.8.1."""

    HYPOTHESIS = "hypothesis"
    VALIDATED = "validated"
    CANONICAL = "canonical"
    CONTRADICTED = "contradicted"
    DEPRECATED = "deprecated"
    SUPERSEDED = "superseded"
    ARCHIVED = "archived"
    PURGED = "purged"


#: 10.8.2 Transition Guards.
BELIEF_TRANSITIONS: dict[str, set[str]] = {
    BeliefState.HYPOTHESIS: {BeliefState.VALIDATED},
    BeliefState.VALIDATED: {BeliefState.CANONICAL},
    BeliefState.CANONICAL: {
        BeliefState.CONTRADICTED,
        BeliefState.DEPRECATED,
        BeliefState.SUPERSEDED,
    },
    BeliefState.CONTRADICTED: {
        BeliefState.CANONICAL,
        BeliefState.DEPRECATED,
        BeliefState.SUPERSEDED,
    },
    BeliefState.DEPRECATED: {BeliefState.ARCHIVED},
    BeliefState.SUPERSEDED: {BeliefState.ARCHIVED},
    BeliefState.ARCHIVED: {BeliefState.PURGED},
    BeliefState.PURGED: set(),
}


class BeliefSensitivity(StrEnum):
    """10.10 — Restricted beliefs require elevated permission."""

    PUBLIC = "public"
    TENANT_SCOPED = "tenant_scoped"
    RESTRICTED = "restricted"


class RelationType(StrEnum):
    """Typed edges the Integration Engine establishes (10.7.4)."""

    CAUSAL = "causal"
    HIERARCHICAL = "hierarchical"
    ANALOGICAL = "analogical"
    CONTRADICTORY = "contradictory"
    SUPERSEDES = "supersedes"


class ReconciliationStrategy(StrEnum):
    """The four strategies of 10.15.2."""

    SUPERSESSION = "supersession"
    SCOPE_NARROWING = "scope_narrowing"
    CONFIDENCE_ADJUSTMENT = "confidence_adjustment"
    HUMAN_ARBITRATION = "human_arbitration"


@dataclass(frozen=True)
class Evidence:
    """One citation into memory supporting a belief (10.14.1).

    Evidentiary sufficiency asks two things — does the memory support the
    belief, and is the memory itself validated and attributable — so the
    citation carries the source memory's confidence, not just its id.
    """

    memory_id: str
    memory_confidence: float
    excerpt: str


@dataclass(frozen=True)
class Falsifiability:
    """What would prove this belief wrong (10.14.1, falsifiability test).

    Conditions must be "specific, observable, and bounded in time". All three
    are required fields, because a belief that cannot be falsified is dogma
    and 10.2.1 rejects it outright.
    """

    conditions: tuple[str, ...]
    observable_via: str
    review_by: datetime

    def is_specific(self) -> bool:
        return bool(self.conditions) and all(c.strip() for c in self.conditions) and bool(self.observable_via)


@dataclass(frozen=True)
class Belief:
    """A belief's frozen content: what is asserted, on what evidence, and how it dies.

    10.18.2: a Validated belief "may never be modified, overwritten, or
    deleted. Its payload, identity, provenance, and evidentiary basis are
    frozen for all time." Mutable lifecycle metadata lives on `BeliefRecord`.
    """

    statement: str
    belief_type: str
    payload: dict[str, Any]
    tenant_id: str
    evidence: tuple[Evidence, ...]
    falsifiability: Falsifiability
    extracted_by: str
    business_id: str | None = None
    sensitivity: BeliefSensitivity = BeliefSensitivity.TENANT_SCOPED
    schema_version: str = "1.0.0"
    belief_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    #: When the extractor constructed the candidate. Distinct from when the
    #: Gateway accepted it — revalidation cadence measures from the Gateway's
    #: clock (`BeliefRecord.formed_at`), never from a producer's.
    captured_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class BeliefRecord:
    """Mutable lifecycle metadata for one belief."""

    belief: Belief
    #: Assigned by the Extraction Engine from the Gateway's clock; the
    #: authoritative instant revalidation cadence is measured from.
    formed_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    state: BeliefState = BeliefState.HYPOTHESIS
    confidence: float = 0.0
    valid_until: datetime | None = None
    confidence_history: list[tuple[datetime, float]] = field(default_factory=list)
    #: Set when this belief supersedes or is superseded by another (10.17.4).
    supersedes: str | None = None
    superseded_by: str | None = None
    #: Justification entry required by 10 rule 18 before deprecation.
    deprecation_justification: str | None = None
    quarantine_reason: str | None = None
    query_count: int = 0
    last_revalidated_at: datetime | None = None

    @property
    def belief_id(self) -> str:
        return self.belief.belief_id

    @property
    def band(self) -> ConfidenceBand:
        return ConfidenceBand.of(self.confidence)

    @property
    def is_reasonable(self) -> bool:
        """Whether a reasoner consumer may see this belief at all.

        10.7.2 — hypotheses are never visible to reasoner consumers. 10 rule 9
        — nothing below 0.60 is presented as canonical. Both collapse to the
        same test, and it is asked at query time, not assumed.
        """
        return self.state == BeliefState.CANONICAL and self.confidence >= HYPOTHESIS_CEILING

    @property
    def is_provisional(self) -> bool:
        """A 0.60-0.79 belief that consumers must qualify downstream (10.10)."""
        return self.band.is_provisional

    def is_due_for_revalidation(self, now: datetime, interval: timedelta) -> bool:
        last = self.last_revalidated_at or self.formed_at
        return now - last >= interval


@dataclass(frozen=True)
class Contradiction:
    """An immutable record of two incompatible canonical assertions (10.15.4)."""

    contradiction_id: str
    left_belief_id: str
    right_belief_id: str
    detected_at: datetime
    detail: str
    resolved_at: datetime | None = None
    strategy: ReconciliationStrategy | None = None
    resolved_by: str | None = None

    @property
    def is_resolved(self) -> bool:
        return self.resolved_at is not None

    def requires_arbitration(self, left_confidence: float, right_confidence: float, restricted: bool) -> bool:
        """The mandatory-arbitration conditions of 10.15.3."""
        return (left_confidence >= ARBITRATION_CONFIDENCE and right_confidence >= ARBITRATION_CONFIDENCE) or restricted
