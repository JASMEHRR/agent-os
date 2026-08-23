"""Decision identity, classification, and lifecycle states (11.4, 11.5, 11.8).

`11.2.1`: "A decision is a governed commitment to a course of action. It is
the moment the organization transitions from deliberation to obligation."

Two invariants shape the types:

**A decision is immutable from Committed** (11.8.3). Core identity, evidence
and rationale freeze there, so the committed content lives in a frozen
`Decision` and only lifecycle metadata sits on the mutable `DecisionRecord`.

**Every commitment documents an expected outcome** (11 rule 16). It is a
required field on commitment, not an optional annotation, because a
commitment nobody predicted the result of cannot be compared against reality
and so cannot be learned from.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any

from kernel.authority import AuthorityLevel, RiskClass

#: 11.4.2 / 21B §18.8 — Decision Journal retention is seven years minimum.
JOURNAL_RETENTION = timedelta(days=365 * 7)

#: 11.19 / 11 rule 11 — no standing order exceeds 30 days without renewal.
STANDING_ORDER_MAX_DURATION = timedelta(days=30)


class DecisionClass(StrEnum):
    """Classification by impact and reversibility (11.5.1)."""

    A_TRIVIAL = "A"
    B_OPERATIONAL = "B"
    C_STRATEGIC = "C"
    D_EXISTENTIAL = "D"

    @property
    def authority(self) -> AuthorityLevel:
        """The authority each class demands (11.5.1, 11.9.1)."""
        return {
            DecisionClass.A_TRIVIAL: AuthorityLevel.AGENT_AUTONOMOUS,
            DecisionClass.B_OPERATIONAL: AuthorityLevel.AGENT_DELEGATED,
            DecisionClass.C_STRATEGIC: AuthorityLevel.HUMAN_APPROVAL,
            DecisionClass.D_EXISTENTIAL: AuthorityLevel.HUMAN_SOVEREIGN,
        }[self]

    @property
    def requires_human_approval(self) -> bool:
        """11 rule 2 — no Class C or D commitment without explicit human approval."""
        return self in (DecisionClass.C_STRATEGIC, DecisionClass.D_EXISTENTIAL)

    @property
    def requires_multiple_options(self) -> bool:
        """11 rule 9 — no Class B or higher commitment with a single option."""
        return self != DecisionClass.A_TRIVIAL

    @property
    def rank(self) -> int:
        return "ABCD".index(self.value)


#: 11.5.1 cost thresholds, verbatim. A class is the *highest* whose criteria
#: the proposal meets, so a cheap but irreversible action is still Class D.
CLASS_COST_CEILING: dict[DecisionClass, float] = {
    DecisionClass.A_TRIVIAL: 0.01,
    DecisionClass.B_OPERATIONAL: 10.0,
    DecisionClass.C_STRATEGIC: 500.0,
}


class Scope(StrEnum):
    """Classification by scope (11.5.2)."""

    PORTFOLIO = "portfolio"
    BUSINESS = "business"
    PROJECT = "project"
    TASK = "task"
    AGENT = "agent"


class EvidentiaryBurden(StrEnum):
    """Classification by evidentiary burden (11.5.3)."""

    RICH = "evidence_rich"
    SPARSE = "evidence_sparse"
    CONTRADICTORY = "evidence_contradictory"


class Urgency(StrEnum):
    """Classification by temporal urgency (11.5.4)."""

    ROUTINE = "routine"
    EXPEDITED = "expedited"
    EMERGENCY = "emergency"
    PANIC = "panic"


class DecisionState(StrEnum):
    """Canonical states of 11.8.1."""

    PROPOSED = "proposed"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    COMMITTED = "committed"
    EXECUTING = "executing"
    COMPLETED = "completed"
    REVERSED = "reversed"
    SUPERSEDED = "superseded"
    REJECTED = "rejected"
    DEFERRED = "deferred"
    ESCALATED = "escalated"


#: 11.8.2 Transition Guards, as a table the kernel's lifecycle engine enforces.
DECISION_TRANSITIONS: dict[str, set[str]] = {
    DecisionState.PROPOSED: {
        DecisionState.UNDER_REVIEW,
        DecisionState.APPROVED,
        DecisionState.REJECTED,
        DecisionState.DEFERRED,
        DecisionState.ESCALATED,
    },
    DecisionState.UNDER_REVIEW: {
        DecisionState.APPROVED,
        DecisionState.REJECTED,
        DecisionState.ESCALATED,
        DecisionState.DEFERRED,
    },
    DecisionState.APPROVED: {DecisionState.COMMITTED, DecisionState.REJECTED},
    DecisionState.COMMITTED: {DecisionState.EXECUTING, DecisionState.REVERSED},
    DecisionState.EXECUTING: {
        DecisionState.COMPLETED,
        DecisionState.REVERSED,
        DecisionState.SUPERSEDED,
    },
    DecisionState.COMPLETED: {DecisionState.REVERSED, DecisionState.SUPERSEDED},
    # 11.8.2 permits an escalated or deferred proposal to resume review.
    DecisionState.ESCALATED: {
        DecisionState.UNDER_REVIEW,
        DecisionState.APPROVED,
        DecisionState.REJECTED,
    },
    DecisionState.DEFERRED: {DecisionState.UNDER_REVIEW, DecisionState.REJECTED},
    DecisionState.REJECTED: set(),
    DecisionState.REVERSED: set(),
    DecisionState.SUPERSEDED: set(),
}

#: States in which a decision is live enough that the Panic Protocol must act
#: on it (11.9.4): active decisions go to Deferred, or Reversed if reversible.
PANIC_ACTIVE_STATES = frozenset(
    {
        DecisionState.PROPOSED,
        DecisionState.UNDER_REVIEW,
        DecisionState.APPROVED,
        DecisionState.COMMITTED,
        DecisionState.EXECUTING,
    }
)


@dataclass(frozen=True)
class Option:
    """One course of action under consideration (11.16).

    The null option — doing nothing — is an ordinary Option with
    `is_null=True`. It is the baseline every acting option must beat
    (11.16.3), so it is modelled rather than assumed.
    """

    option_id: str
    description: str
    estimated_cost: float
    expected_value: float
    reversible: bool
    is_null: bool = False
    #: Reference to pre-positioned compensation logic (11.21.2). Without it a
    #: reversible designation is refused.
    compensation_ref: str | None = None


@dataclass(frozen=True)
class EvidenceRef:
    """A citation into canonical knowledge or supplementary memory (11.12)."""

    source: str  # "knowledge" | "memory"
    reference_id: str
    confidence: float
    statement: str


@dataclass(frozen=True)
class RiskAssessment:
    """Risk across the five dimensions of 21B §18.3, and the resulting class."""

    financial: RiskClass
    operational: RiskClass
    reputational: RiskClass
    legal: RiskClass
    strategic: RiskClass

    @property
    def overall(self) -> RiskClass:
        """The highest dimension wins — risk does not average away."""
        order = list(RiskClass)
        return max(
            (self.financial, self.operational, self.reputational, self.legal, self.strategic),
            key=order.index,
        )


@dataclass(frozen=True)
class Proposal:
    """A submitted proposal, before classification and evaluation (11.7.1)."""

    proposal_id: str
    summary: str
    proposer_id: str
    proposer_authority: AuthorityLevel
    tenant_id: str
    options: tuple[Option, ...]
    evidence: tuple[EvidenceRef, ...]
    risk: RiskAssessment
    scope: Scope = Scope.TASK
    urgency: Urgency = Urgency.ROUTINE
    business_id: str | None = None
    #: An explicitly declared evidentiary gap (11 rule 1). A proposal may have
    #: sparse evidence, but the gap must be named rather than left implicit.
    declared_gap: str | None = None
    #: Set only by a human, and only deliberately (11 rule 4).
    human_designated_irreversible: bool = False
    standing_order_ref: str | None = None


@dataclass(frozen=True)
class Decision:
    """The frozen content of a decision (11.8.3, immutable from Committed)."""

    decision_id: str
    proposal: Proposal
    decision_class: DecisionClass
    burden: EvidentiaryBurden
    confidence: float
    required_authority: AuthorityLevel
    chosen_option: Option
    rationale: str
    #: 11 rule 16 — no commitment without a documented expected outcome.
    expected_outcome: str
    reversible: bool
    formed_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def retain_until(self) -> datetime:
        return self.formed_at + JOURNAL_RETENTION


@dataclass
class DecisionRecord:
    """Mutable lifecycle metadata for one decision."""

    decision: Decision
    state: DecisionState = DecisionState.PROPOSED
    authorized_by: str | None = None
    authorized_at: datetime | None = None
    committed_at: datetime | None = None
    #: Nullable until resolved, immutable once recorded (21B §18.8).
    actual_outcome: str | None = None
    outcome_recorded_at: datetime | None = None
    reversal_deadline: datetime | None = None
    reversed_by: str | None = None
    supersedes: str | None = None
    superseded_by: str | None = None
    escalated_to: str | None = None
    rejection_reason: str | None = None
    deferral_reason: str | None = None

    @property
    def decision_id(self) -> str:
        return self.decision.decision_id

    @property
    def decision_class(self) -> DecisionClass:
        return self.decision.decision_class

    @property
    def is_committed(self) -> bool:
        return self.state in (
            DecisionState.COMMITTED,
            DecisionState.EXECUTING,
            DecisionState.COMPLETED,
        )

    def within_reversal_window(self, now: datetime) -> bool:
        return self.reversal_deadline is not None and now < self.reversal_deadline

    @property
    def outcome_diverged(self) -> bool:
        """Whether reality differed from the prediction (21B §18.11, Quality)."""
        if self.actual_outcome is None:
            return False
        return self.actual_outcome.strip().lower() != self.decision.expected_outcome.strip().lower()


@dataclass(frozen=True)
class StandingOrder:
    """Pre-authorized scoped authority for Class C decisions (11.14.2, 11.19).

    21B §18.10 names standing orders "the principal privilege-escalation
    surface in this subsystem", which is why every constraint is a required
    field and every invocation is validated against all of them.
    """

    order_id: str
    issued_by: str
    tenant_id: str
    #: Action prefixes this order pre-authorizes.
    scope: frozenset[str]
    budget_ceiling: float
    max_risk: RiskClass
    issued_at: datetime
    expires_at: datetime
    revoked_at: datetime | None = None
    invocations: int = 0

    def is_live(self, now: datetime) -> bool:
        return self.revoked_at is None and now < self.expires_at


@dataclass(frozen=True)
class ApprovalRequest:
    """A packaged request awaiting explicit human action (11.18)."""

    request_id: str
    decision_id: str
    decision_class: DecisionClass
    routed_to: str
    packaged_at: datetime
    expires_at: datetime
    context: dict[str, Any]
    responded_at: datetime | None = None
    responded_by: str | None = None
    response: str | None = None

    @property
    def is_pending(self) -> bool:
        return self.responded_at is None

    def has_timed_out(self, now: datetime) -> bool:
        return self.is_pending and now >= self.expires_at


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4()}"
