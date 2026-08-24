"""Learning entries, states, patterns and thresholds (13.8, 13.9, 13.12-13.14).

`13.2.1` states the subsystem's defining property: **"Learning is the only
subsystem whose output is change to the other subsystems."**

Three things in this file are calibration surfaces the rest of the module
depends on, and all three are quoted from the constitution rather than chosen:

* `CONFIDENCE_BANDS` — 13.13.3's four bands;
* `EVIDENCE_SUFFICIENCY` — 13.12.4's counts by target class;
* `MEASUREMENT_WINDOWS` — 13.18.2's windows by target class.

**State immutability (13.9.3).** Once an entry reaches Validated, its identity,
evidence and attribution are immutable; only lifecycle metadata moves. So the
immutable half lives in a frozen `Hypothesis` and the mutable half in
`LearningEntry` beside it, rather than one mutable object that merely promises
not to change.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Any

from core.exceptions import ValidationError


class LearningState(StrEnum):
    """13.9.1's canonical states, verbatim."""

    OBSERVED = "observed"
    HYPOTHESIZED = "hypothesized"
    VALIDATED = "validated"
    CONSOLIDATED = "consolidated"
    PROPAGATED = "propagated"
    ADOPTED = "adopted"
    CONFIRMED = "confirmed"
    REFUTED = "refuted"
    SUPERSEDED = "superseded"
    ABANDONED = "abandoned"
    QUARANTINED = "quarantined"


LEARNING_TRANSITIONS: dict[str, set[str]] = {
    LearningState.OBSERVED: {LearningState.HYPOTHESIZED, LearningState.ABANDONED},
    LearningState.HYPOTHESIZED: {
        LearningState.VALIDATED,
        LearningState.ABANDONED,
        LearningState.QUARANTINED,
    },
    LearningState.VALIDATED: {LearningState.CONSOLIDATED, LearningState.QUARANTINED},
    LearningState.CONSOLIDATED: {LearningState.PROPAGATED, LearningState.QUARANTINED},
    # 13.16.1 — the target may reject, and rejection abandons the entry rather
    # than invalidating its evidence.
    LearningState.PROPAGATED: {LearningState.ADOPTED, LearningState.ABANDONED},
    LearningState.ADOPTED: {LearningState.CONFIRMED, LearningState.REFUTED, LearningState.SUPERSEDED},
    # 13.19 deprecates a stale confirmed entry by superseding it, so there is
    # no separate deprecated state to transition into.
    LearningState.CONFIRMED: {LearningState.SUPERSEDED},
    LearningState.REFUTED: {LearningState.SUPERSEDED},
    LearningState.SUPERSEDED: set(),
    LearningState.ABANDONED: set(),
    # A quarantined entry is under review, not dead: human arbitration can
    # release it or abandon it (13.21.3).
    LearningState.QUARANTINED: {LearningState.VALIDATED, LearningState.ABANDONED},
}


class TargetClass(StrEnum):
    """What a learning entry proposes to change. Governs every threshold."""

    AGENT = "agent"
    TOOL = "tool"
    WORKFLOW = "workflow"
    DECISION = "decision"
    BUSINESS = "business"
    PORTFOLIO = "portfolio"
    #: Self-targeting. Present so the Recursion Guard has something to name,
    #: never so an entry can legitimately carry it (13.21.3, 13 rule 4).
    LEARNING = "learning"


class PatternKind(StrEnum):
    """13.14.1's taxonomy.

    The distinction is load-bearing: 13 rule 6 forbids presenting correlation
    as causation, so a correlation pattern is a different kind of thing from a
    causal one and is labelled as such throughout.
    """

    SUCCESS = "success"
    FAILURE = "failure"
    CORRELATION = "correlation"
    ANOMALY = "anomaly"


#: 13.12.4, verbatim. Business and Portfolio additionally require human review,
#: which is enforced separately rather than expressed as a count.
EVIDENCE_SUFFICIENCY: dict[TargetClass, int] = {
    TargetClass.AGENT: 3,
    TargetClass.TOOL: 3,
    TargetClass.WORKFLOW: 2,
    TargetClass.DECISION: 5,
    TargetClass.BUSINESS: 5,
    TargetClass.PORTFOLIO: 5,
    TargetClass.LEARNING: 5,
}

#: 13.13.3's confidence bands, as the minimum for each target class.
#:   < 0.60 quarantined or abandoned
#:   0.60-0.79 permitted for Agent/Tool, flagged provisional
#:   0.80-0.94 standard for Workflow/Decision
#:   0.95-1.00 Business/Portfolio, with human ratification
CONFIDENCE_FLOOR = 0.60
PROVISIONAL_CEILING = 0.79
CONFIDENCE_THRESHOLDS: dict[TargetClass, float] = {
    TargetClass.AGENT: 0.60,
    TargetClass.TOOL: 0.60,
    TargetClass.WORKFLOW: 0.80,
    TargetClass.DECISION: 0.80,
    TargetClass.BUSINESS: 0.95,
    TargetClass.PORTFOLIO: 0.95,
    TargetClass.LEARNING: 1.01,  # unreachable by construction; see recursion.py
}

#: Target classes 13.13.3 reserves for human ratification.
REQUIRES_HUMAN_RATIFICATION = frozenset({TargetClass.BUSINESS, TargetClass.PORTFOLIO})

#: 13.18.2's measurement windows, as (minimum, maximum) subsequent observations.
#: Business and Portfolio are expressed in business cycles, carried here as the
#: count of cycle-completion reports the Measurement Engine expects.
MEASUREMENT_WINDOWS: dict[TargetClass, tuple[int, int]] = {
    TargetClass.AGENT: (5, 10),
    TargetClass.TOOL: (5, 10),
    TargetClass.WORKFLOW: (3, 5),
    TargetClass.DECISION: (10, 20),
    TargetClass.BUSINESS: (1, 3),
    TargetClass.PORTFOLIO: (1, 3),
    TargetClass.LEARNING: (1, 1),
}

#: 21B §21.4 — asymmetric processing (13.34.3). "Failure patterns require fewer
#: confirming instances but stronger root cause attribution. Success patterns
#: require more confirming instances but permit broader generalization."
FAILURE_PATTERN_MINIMUM = 2
SUCCESS_PATTERN_MINIMUM = 3

#: [Engineering Decision] 13.19 requires freshness decay without a rate.
#: 90 days halves nothing abruptly while making a year-old entry visibly stale.
DECAY_HALF_LIFE = timedelta(days=90)
DEPRECATION_FLOOR = 0.40

#: 13 rule 18 / 21B §21.3 — the Learning Journal's retention.
JOURNAL_RETENTION = timedelta(days=365 * 7)


@dataclass(frozen=True)
class EvidenceRef:
    """One canonical record backing an entry (13.12.1).

    `13.12.1` restricts the evidentiary basis to decision journals, validated
    memory, committed knowledge and tool execution records. `quarantined` and
    `speculative` are carried explicitly so 13 rule 14 can be enforced on the
    evidence itself rather than on the caller's promise about it.
    """

    reference: str
    kind: str
    observed_at: datetime
    confidence: float = 1.0
    quarantined: bool = False
    speculative: bool = False
    #: True for 13.33.1's human feedback, which is high-confidence evidence.
    human: bool = False

    @property
    def is_canonical(self) -> bool:
        return not self.quarantined and not self.speculative


@dataclass(frozen=True)
class Attribution:
    """13.12.2's four dimensions, plus the null hypothesis 13.12.3 mandates."""

    causal_proximity: float
    confounding_controlled: bool
    temporal_order_holds: bool
    replications: int
    #: 13.12.3 — "mandatory consideration of null hypotheses". A blank one is
    #: not consideration, and the Attribution Engine refuses it.
    null_hypothesis: str

    @property
    def strength(self) -> float:
        """A single number for ranking, never for bypassing the individual gates."""
        replication_credit = min(1.0, self.replications / 5.0)
        base = (self.causal_proximity + replication_credit) / 2.0
        if not self.confounding_controlled:
            base *= 0.5
        if not self.temporal_order_holds:
            base *= 0.25
        return round(base, 4)


@dataclass(frozen=True)
class Observation:
    """One outcome submitted for analysis (21B §21.5 Observation Submission)."""

    observation_id: str
    tenant_id: str
    observer_id: str
    target_class: TargetClass
    subject_id: str
    summary: str
    evidence: tuple[EvidenceRef, ...]
    observed_at: datetime
    #: True when submitted through the Human Feedback Entry interface (13.33.1).
    human_feedback: bool = False


@dataclass(frozen=True)
class Pattern:
    """A recognized structure, bounded by the scope it was observed in (13.8.3)."""

    pattern_id: str
    kind: PatternKind
    target_class: TargetClass
    scope: str
    instances: tuple[str, ...]
    description: str
    #: Required for a failure pattern; 13.34.3 trades instance count for it.
    root_cause: str = ""

    @property
    def instance_count(self) -> int:
        return len(self.instances)


@dataclass(frozen=True)
class Hypothesis:
    """The immutable core of a learning entry (13.9.3).

    Identity, evidence and attribution live here and are frozen. Everything
    that legitimately changes over an entry's life lives in `LearningEntry`.
    """

    entry_id: str
    tenant_id: str
    observer_id: str
    target_class: TargetClass
    target_subsystem: str
    subject_id: str
    proposal: str
    expected_outcome: str
    pattern: Pattern
    evidence: tuple[EvidenceRef, ...]
    attribution: Attribution
    scope: str
    formed_at: datetime
    human_feedback: bool = False

    @property
    def is_causal_claim(self) -> bool:
        """13 rule 6 — a correlation pattern may not be stated as a cause."""
        return self.pattern.kind in (PatternKind.SUCCESS, PatternKind.FAILURE)


@dataclass
class LearningEntry:
    """Lifecycle metadata around a frozen hypothesis."""

    hypothesis: Hypothesis
    state: LearningState = LearningState.HYPOTHESIZED
    confidence: float = 0.0
    provisional: bool = False
    quarantine_reason: str = ""
    abandonment_reason: str = ""
    validated_at: datetime | None = None
    propagated_at: datetime | None = None
    adopted_at: datetime | None = None
    #: Measurement observations recorded since adoption.
    measurements: list[bool] = field(default_factory=list)
    actual_improvement: float | None = None
    superseded_by: str | None = None
    #: Freshness, decayed by the Decay Engine (13.19).
    freshness: float = 1.0

    @property
    def entry_id(self) -> str:
        return self.hypothesis.entry_id

    @property
    def target_class(self) -> TargetClass:
        return self.hypothesis.target_class

    @property
    def is_terminal(self) -> bool:
        return self.state in (
            LearningState.CONFIRMED,
            LearningState.REFUTED,
            LearningState.SUPERSEDED,
            LearningState.ABANDONED,
        )

    @property
    def effective_confidence(self) -> float:
        """Confidence as it stands today, after freshness decay (13.19)."""
        return round(self.confidence * self.freshness, 4)


def threshold_for(target_class: TargetClass) -> float:
    return CONFIDENCE_THRESHOLDS[target_class]


def window_for(target_class: TargetClass) -> tuple[int, int]:
    return MEASUREMENT_WINDOWS[target_class]


def required_observations(target_class: TargetClass) -> int:
    return EVIDENCE_SUFFICIENCY[target_class]


def assert_valid_confidence(value: float) -> float:
    if not 0.0 <= value <= 1.0:
        raise ValidationError(f"confidence must be between 0 and 1, got {value}")
    return round(value, 4)


def summarize(entry: LearningEntry) -> dict[str, Any]:
    return {
        "entry_id": entry.entry_id,
        "state": entry.state.value,
        "target_class": entry.target_class.value,
        "target_subsystem": entry.hypothesis.target_subsystem,
        "confidence": entry.confidence,
        "effective_confidence": entry.effective_confidence,
        "provisional": entry.provisional,
        "pattern_kind": entry.hypothesis.pattern.kind.value,
        "measurements": len(entry.measurements),
    }
