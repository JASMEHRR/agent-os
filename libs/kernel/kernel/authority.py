"""Confidence/Authority Resolution (21A §5.2 item 5).

The fifth universal Gateway mechanism. Every Gateway that lets a principal act
must answer the same two-part question: what authority does this action
require, and is the actor's confidence high enough to exercise it. Factoring
it here means one answer, not eleven.

The authority spectrum (11.9.1) and the confidence floors (11.9.2) are
constitutional and appear verbatim. Two properties are structural:

**Authority is risk-adjusted, not level-fixed** (11.14.3). A Class B decision
at High risk requires Class C authority; a Class C decision at Existential
risk requires Class D. The resolver returns the *maximum* of the
class-derived and risk-derived requirements, so risk can only ever raise the
bar, never lower it.

**Level 4 is bound to a human.** `resolve` reports it; it cannot grant it.
14.23.4 binds Level 4 to human credentials, so no computation in this module
can produce an outcome where a non-human exercises it.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum, StrEnum


class AuthorityLevel(IntEnum):
    """The authority spectrum of 11.9.1. Ordered, so `max` is meaningful."""

    AGENT_AUTONOMOUS = 1
    AGENT_DELEGATED = 2
    HUMAN_APPROVAL = 3
    HUMAN_SOVEREIGN = 4

    @property
    def requires_human(self) -> bool:
        """Levels 3 and 4 need a human in the loop; 4 is human-only (11.9.1)."""
        return self >= AuthorityLevel.HUMAN_APPROVAL

    @property
    def is_human_only(self) -> bool:
        """Level 4: the runtime may propose but never commit (11.9.1)."""
        return self == AuthorityLevel.HUMAN_SOVEREIGN


#: [Engineering Decision] How much of the evidentiary base survives when option
#: quality and temporal relevance are at their worst. At 0.7, perfectly
#: evidenced reasoning over a marginal option still retains 70% of its
#: confidence — weakened, but not disqualified.
MODULATION_FLOOR = 0.7

#: 11.9.2 Confidence Requirements by Authority, verbatim.
MIN_CONFIDENCE_BY_LEVEL: dict[AuthorityLevel, float] = {
    AuthorityLevel.AGENT_AUTONOMOUS: 0.60,
    AuthorityLevel.AGENT_DELEGATED: 0.70,
    AuthorityLevel.HUMAN_APPROVAL: 0.80,
    AuthorityLevel.HUMAN_SOVEREIGN: 0.90,
}


class RiskClass(StrEnum):
    """Risk classes that drive the escalation of 11.14.3."""

    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    SEVERE = "severe"
    EXISTENTIAL = "existential"


#: 11.14.3 risk-adjusted escalation. High risk demands at least Level 3;
#: Existential risk demands Level 4, whatever the nominal class.
MIN_LEVEL_BY_RISK: dict[RiskClass, AuthorityLevel] = {
    RiskClass.LOW: AuthorityLevel.AGENT_AUTONOMOUS,
    RiskClass.MODERATE: AuthorityLevel.AGENT_DELEGATED,
    RiskClass.HIGH: AuthorityLevel.HUMAN_APPROVAL,
    RiskClass.SEVERE: AuthorityLevel.HUMAN_APPROVAL,
    RiskClass.EXISTENTIAL: AuthorityLevel.HUMAN_SOVEREIGN,
}


class Outcome(StrEnum):
    """What the resolver concluded."""

    PERMITTED = "permitted"
    ESCALATE = "escalate"
    INSUFFICIENT_CONFIDENCE = "insufficient_confidence"


@dataclass(frozen=True)
class AuthorityResolution:
    """The resolver's verdict, carrying its own reasoning.

    `reason` is populated on every outcome, including PERMITTED, because
    11.26.1 requires confidence calibration to be auditable — a verdict whose
    basis cannot be reconstructed cannot be calibrated against.
    """

    required_level: AuthorityLevel
    actor_level: AuthorityLevel
    confidence: float
    minimum_confidence: float
    outcome: Outcome
    reason: str

    @property
    def permitted(self) -> bool:
        return self.outcome == Outcome.PERMITTED

    @property
    def needs_human(self) -> bool:
        return self.required_level.requires_human


def resolve(
    class_level: AuthorityLevel,
    actor_level: AuthorityLevel,
    confidence: float,
    risk: RiskClass = RiskClass.LOW,
    evidence_contradictory: bool = False,
) -> AuthorityResolution:
    """Resolves required authority and checks confidence against its floor.

    Order matters. The effective requirement is computed first, from the
    maximum of class and risk, because the confidence floor depends on it — a
    proposal escalated from Level 2 to Level 3 by risk must clear Level 3's
    0.80 floor, not Level 2's 0.70.

    `evidence_contradictory` forces escalation regardless of nominal
    confidence (11.9.2, Level 4 clause; 11 rule 8 generalizes it). A
    contradiction is not something a high confidence score may talk its way
    past.
    """
    if not 0.0 <= confidence <= 1.0:
        raise ValueError(f"confidence {confidence} is outside 0.0-1.0")

    required = max(class_level, MIN_LEVEL_BY_RISK[risk])
    minimum = MIN_CONFIDENCE_BY_LEVEL[required]

    if evidence_contradictory:
        return AuthorityResolution(
            required_level=max(required, AuthorityLevel.HUMAN_APPROVAL),
            actor_level=actor_level,
            confidence=confidence,
            minimum_confidence=minimum,
            outcome=Outcome.ESCALATE,
            reason="evidence is contradictory; escalated regardless of nominal confidence (11.9.2)",
        )

    if confidence < minimum:
        return AuthorityResolution(
            required_level=required,
            actor_level=actor_level,
            confidence=confidence,
            minimum_confidence=minimum,
            outcome=Outcome.INSUFFICIENT_CONFIDENCE,
            reason=(
                f"confidence {confidence} is below the {minimum} floor for authority level {int(required)} (11.9.2)"
            ),
        )

    if actor_level < required:
        return AuthorityResolution(
            required_level=required,
            actor_level=actor_level,
            confidence=confidence,
            minimum_confidence=minimum,
            outcome=Outcome.ESCALATE,
            reason=(
                f"actor holds level {int(actor_level)} but the action requires level {int(required)}"
                + (f", escalated from {int(class_level)} by {risk.value} risk" if required > class_level else "")
            ),
        )

    return AuthorityResolution(
        required_level=required,
        actor_level=actor_level,
        confidence=confidence,
        minimum_confidence=minimum,
        outcome=Outcome.PERMITTED,
        reason=f"level {int(actor_level)} satisfies level {int(required)} at confidence {confidence}",
    )


def derive_confidence(
    evidence_confidences: tuple[float, ...],
    option_quality: float,
    risk: RiskClass,
    temporal_relevance: float = 1.0,
) -> float:
    """Derives a decision's confidence from its inputs (21B §18.3, Confidence Engine).

    CIR-006 records that the confidence-derivation function is ambiguous across
    four subsystems, and CIR-007 records miscalibration propagating through
    them as an open risk. This is therefore an **[Engineering Decision]**, not
    a constitutional formula, and it is deliberately conservative: the weakest
    piece of evidence caps the result, because a chain of reasoning is no more
    reliable than its weakest link, and higher risk pulls confidence down
    rather than leaving it flat.

    It lives in the kernel so all four subsystems derive confidence the same
    way — one function to recalibrate when CIR-006 is resolved, not four.
    """
    if not evidence_confidences:
        return 0.0
    for value in (*evidence_confidences, option_quality, temporal_relevance):
        if not 0.0 <= value <= 1.0:
            raise ValueError(f"confidence input {value} is outside 0.0-1.0")

    weakest = min(evidence_confidences)
    mean = sum(evidence_confidences) / len(evidence_confidences)
    evidentiary = (weakest + mean) / 2.0
    risk_penalty = {
        RiskClass.LOW: 1.0,
        RiskClass.MODERATE: 0.95,
        RiskClass.HIGH: 0.9,
        RiskClass.SEVERE: 0.85,
        RiskClass.EXISTENTIAL: 0.8,
    }[risk]

    # Option quality and temporal relevance *modulate* the evidentiary base;
    # they do not multiply straight through it. Confidence in a decision is
    # primarily a question of how good its evidence is — how decisively the
    # chosen option beat the runner-up adjusts that judgement rather than
    # replacing it. Multiplying four sub-unit factors together collapsed the
    # result so far that Level 3 (0.80) and Level 4 (0.90) became structurally
    # unreachable, which would have left every Class C and D decision
    # permanently deferred instead of decided under human approval.
    modulation = MODULATION_FLOOR + (1.0 - MODULATION_FLOOR) * (option_quality * temporal_relevance)
    derived = evidentiary * modulation * risk_penalty
    return round(min(weakest, derived), 4)
