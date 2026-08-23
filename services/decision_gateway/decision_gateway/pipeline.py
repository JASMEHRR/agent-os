"""Classification, option validation, evaluation and approval (21B §18.3).

21B §18.4 describes the Gateway as "a funnel with widening scrutiny", and the
order of that funnel is load-bearing:

**Classification first.** Class determines every subsequent gate — evidence
sufficiency, option count, confidence threshold, authority, approval path. It
is also the primary attack surface: 11.24.2 names "agents proposing decisions
just below escalation thresholds" as a drift pattern, so the Classifier takes
the *highest* class any criterion implies rather than the one the proposer
suggests. Proposers do not get a vote on their own class.

**Options are mandatory and include doing nothing.** 11.16.3: "A decision to
act must demonstrate superiority to the null option." Single-option proposals
for Class B and above are rejected structurally.

**Approval gates cannot auto-approve.** The Approval Orchestrator has no code
path from timeout to approval. On timeout, Class C defers and Class D
rejects — 11 rule 3 admits no exception, and 11.18.3 forecloses implicit
consent.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from core.exceptions import AgentOSError, ValidationError
from decision_gateway.decisions import (
    CLASS_COST_CEILING,
    STANDING_ORDER_MAX_DURATION,
    ApprovalRequest,
    DecisionClass,
    EvidenceRef,
    EvidentiaryBurden,
    Option,
    Proposal,
    RiskAssessment,
    StandingOrder,
    new_id,
)
from kernel.authority import AuthorityLevel, RiskClass, derive_confidence

#: [Engineering Decision] 11.18 requires timeout semantics without publishing
#: windows. These are starting values; the constitutional part is what happens
#: *at* the timeout, which is never approval.
CLASS_C_APPROVAL_WINDOW = timedelta(hours=24)
CLASS_D_APPROVAL_WINDOW = timedelta(days=3)


class ProposalRejected(AgentOSError):
    """The proposal does not survive the funnel. Rejection is always reasoned."""

    def __init__(self, reason: str, gate: str):
        super().__init__(f"proposal rejected at {gate}: {reason}")
        self.reason = reason
        self.gate = gate


class StandingOrderViolation(AgentOSError):
    """An invocation exceeded the order's declared scope, budget, window or risk."""


@dataclass
class Classifier:
    """Assigns Decision Class from impact, reversibility and cost (11.5.1).

    Takes the maximum of every criterion. A proposal that is cheap but
    irreversible is Class D on reversibility alone, whatever its cost implies,
    because 11.5.1 lists irreversibility as a Class D criterion in its own
    right.

    Reversibility here is **effective**, not declared. An option marked
    reversible but carrying no resolvable compensation reference cannot in
    fact be undone (11.21.2), and classifying it on the declaration would let
    a proposer claim Class A treatment for an action nothing can reverse —
    precisely the threshold-gaming 11.24.2 names as a drift pattern.
    """

    #: Resolves whether a compensation reference points at executable logic.
    compensation_exists: Callable[[str], bool] = field(default=lambda _ref: True)

    def _effectively_reversible(self, option: Option) -> bool:
        if not option.reversible:
            return False
        if option.compensation_ref is None:
            return False
        return self.compensation_exists(option.compensation_ref)

    def classify(self, proposal: Proposal) -> DecisionClass:
        candidates = [self._by_cost(proposal), self._by_reversibility(proposal), self._by_scope(proposal)]
        return max(candidates, key=lambda c: c.rank)

    def _by_cost(self, proposal: Proposal) -> DecisionClass:
        cost = max((o.estimated_cost for o in proposal.options), default=0.0)
        if cost < CLASS_COST_CEILING[DecisionClass.A_TRIVIAL]:
            return DecisionClass.A_TRIVIAL
        if cost < CLASS_COST_CEILING[DecisionClass.B_OPERATIONAL]:
            return DecisionClass.B_OPERATIONAL
        if cost <= CLASS_COST_CEILING[DecisionClass.C_STRATEGIC]:
            return DecisionClass.C_STRATEGIC
        return DecisionClass.D_EXISTENTIAL

    def _by_reversibility(self, proposal: Proposal) -> DecisionClass:
        """An irreversible action is Existential by 11.5.1, whatever it costs."""
        if proposal.human_designated_irreversible:
            return DecisionClass.D_EXISTENTIAL
        acting = [o for o in proposal.options if not o.is_null]
        if acting and not any(self._effectively_reversible(o) for o in acting):
            return DecisionClass.D_EXISTENTIAL
        return DecisionClass.A_TRIVIAL

    def _by_scope(self, proposal: Proposal) -> DecisionClass:
        """Portfolio-wide or customer-facing scope is Strategic at minimum (11.5.1)."""
        from decision_gateway.decisions import Scope

        if proposal.scope == Scope.PORTFOLIO:
            return DecisionClass.D_EXISTENTIAL
        if proposal.scope == Scope.BUSINESS:
            return DecisionClass.C_STRATEGIC
        return DecisionClass.A_TRIVIAL


@dataclass
class OptionValidator:
    """Enforces the multi-option requirement including the null option (11.16)."""

    def validate(self, proposal: Proposal, decision_class: DecisionClass) -> None:
        if not proposal.options:
            raise ProposalRejected("a proposal must carry at least one option", gate="option_validator")

        if not decision_class.requires_multiple_options:
            return

        if not any(o.is_null for o in proposal.options):
            raise ProposalRejected(
                f"Class {decision_class.value} requires the null option; a decision to act must demonstrate "
                "superiority to doing nothing (11.16.3)",
                gate="option_validator",
            )
        acting = [o for o in proposal.options if not o.is_null]
        if len(acting) < 2:
            raise ProposalRejected(
                f"Class {decision_class.value} requires at least two distinct options plus the null option; "
                f"got {len(acting)} (11 rule 9)",
                gate="option_validator",
            )
        if len({o.option_id for o in proposal.options}) != len(proposal.options):
            raise ProposalRejected("option identifiers must be distinct", gate="option_validator")


@dataclass
class EvidenceAssembler:
    """Retrieves evidence and flags gaps and contradictions explicitly (11.12).

    Contradictory evidence is not a score adjustment. 11 rule 8 admits no
    autonomous path past an unresolved contradiction, so the burden is
    reported as CONTRADICTORY and the Gateway halts commitment on it.
    """

    #: Reports contradiction status for a cited belief. Injected so the
    #: assembler depends on the shape of the answer, not on Knowledge.
    contradiction_check: Callable[[str], bool] = field(default=lambda _ref: False)

    def assess(self, proposal: Proposal, decision_class: DecisionClass) -> EvidentiaryBurden:
        contradictory = [
            e for e in proposal.evidence if e.source == "knowledge" and self.contradiction_check(e.reference_id)
        ]
        if contradictory:
            return EvidentiaryBurden.CONTRADICTORY

        canonical = [e for e in proposal.evidence if e.source == "knowledge"]
        self._check_sufficiency(proposal, decision_class, canonical)

        if len(canonical) >= 2 and all(e.confidence >= 0.8 for e in canonical):
            return EvidentiaryBurden.RICH
        return EvidentiaryBurden.SPARSE

    def _check_sufficiency(
        self, proposal: Proposal, decision_class: DecisionClass, canonical: list[EvidenceRef]
    ) -> None:
        """Evidentiary burden by class (11.12.4, doc 11 §12).

        Class A needs none; B needs one canonical belief or a declared gap; C
        needs multiple or one strong belief with falsifiability met; D needs a
        comprehensive basis.
        """
        if decision_class == DecisionClass.A_TRIVIAL:
            return
        if decision_class == DecisionClass.B_OPERATIONAL:
            if not canonical and proposal.declared_gap is None:
                raise ProposalRejected(
                    "Class B requires at least one canonical belief or an explicitly declared "
                    "evidentiary gap (11 rule 1)",
                    gate="evidence_assembler",
                )
            return
        if decision_class == DecisionClass.C_STRATEGIC:
            strong = [e for e in canonical if e.confidence >= 0.8]
            if len(canonical) < 2 and not strong:
                raise ProposalRejected(
                    "Class C requires multiple canonical beliefs, or one strong belief with its "
                    "falsifiability conditions met",
                    gate="evidence_assembler",
                )
            return
        if len(canonical) < 2:
            raise ProposalRejected(
                "Class D requires a comprehensive evidentiary basis with cross-reference consistency",
                gate="evidence_assembler",
            )


@dataclass
class EvaluationEngine:
    """Scores options and applies portfolio weighting (21B §18.3).

    Scoring is deliberately legible rather than clever: 21B §18.15 guarantee 8
    requires the system to answer "what was decided, against what
    alternatives" for any commitment, and an opaque score cannot answer the
    second half.
    """

    #: Penalty applied to an option that concentrates portfolio exposure.
    concentration_penalty: float = 0.2

    def score(self, option: Option, concentrated: bool = False) -> float:
        """Objective fit, risk-adjusted return, reversibility, efficiency."""
        if option.is_null:
            # The null option scores its opportunity cost: zero value, zero
            # spend. It is the baseline, not a competitor with a hidden bonus.
            return 0.0
        efficiency = (
            option.expected_value / option.estimated_cost if option.estimated_cost > 0 else option.expected_value
        )
        reversibility_bonus = 1.1 if option.reversible else 1.0
        penalty = 1.0 - self.concentration_penalty if concentrated else 1.0
        return round(efficiency * reversibility_bonus * penalty, 6)

    def choose(self, proposal: Proposal, concentrated: bool = False) -> tuple[Option, float]:
        """Picks the best option, or the null option if nothing beats it.

        11.16.3 is enforced here: an acting option must *demonstrate
        superiority* to the null option. Ties go to doing nothing.
        """
        scored = [(o, self.score(o, concentrated)) for o in proposal.options]
        null_score = next((s for o, s in scored if o.is_null), 0.0)
        acting = [(o, s) for o, s in scored if not o.is_null]
        if not acting:
            best = next(o for o in proposal.options if o.is_null)
            return best, 0.0
        best_option, best_score = max(acting, key=lambda pair: pair[1])
        if best_score <= null_score:
            null_option = next((o for o in proposal.options if o.is_null), None)
            if null_option is not None:
                return null_option, null_score
        return best_option, best_score

    def option_quality(self, proposal: Proposal, chosen_score: float) -> float:
        """How clearly the chosen option beat its alternatives, 0.0-1.0.

        A narrow win is weaker evidence that the right thing was chosen than a
        decisive one, and that feeds the confidence derivation.
        """
        scores = [self.score(o) for o in proposal.options if not o.is_null]
        if not scores or chosen_score <= 0:
            return 0.5
        runner_up = sorted(scores, reverse=True)[1] if len(scores) > 1 else 0.0
        margin = (chosen_score - runner_up) / chosen_score
        return round(min(1.0, 0.5 + margin / 2.0), 4)


@dataclass
class ConfidenceEngine:
    """Derives decision confidence from evidence, options, risk and time.

    Delegates the arithmetic to `kernel.derive_confidence` so all four
    subsystems CIR-006 names share one formula. This class supplies the
    decision-shaped inputs; it does not invent a second calibration.
    """

    def derive(
        self,
        evidence: tuple[EvidenceRef, ...],
        option_quality: float,
        risk: RiskClass,
        temporal_relevance: float = 1.0,
    ) -> float:
        return derive_confidence(
            tuple(e.confidence for e in evidence),
            option_quality=option_quality,
            risk=risk,
            temporal_relevance=temporal_relevance,
        )


@dataclass
class RiskAssessor:
    """Assigns a risk class across five dimensions (21B §18.3)."""

    def assess(self, proposal: Proposal) -> RiskAssessment:
        """Returns the proposal's own assessment.

        The proposer supplies the dimensional assessment; the Gateway does not
        re-derive it, because it has no domain knowledge the proposer lacks.
        What the Gateway *does* control is that risk can only escalate
        authority, never lower it — enforced in `kernel.resolve`.
        """
        return proposal.risk


@dataclass
class ApprovalOrchestrator:
    """Packages and routes human approval requests; enforces timeout semantics.

    There is no method on this class that approves anything on a timeout. The
    only way an approval exists is `respond`, which requires an explicit
    responder. That is 11 rule 3 expressed in the type surface rather than in
    configuration.
    """

    now: Callable[[], datetime] = field(default=lambda: datetime.now(UTC))
    class_c_window: timedelta = CLASS_C_APPROVAL_WINDOW
    class_d_window: timedelta = CLASS_D_APPROVAL_WINDOW
    _requests: dict[str, ApprovalRequest] = field(default_factory=dict, init=False)

    def package(
        self,
        decision_id: str,
        decision_class: DecisionClass,
        routed_to: str,
        context: dict[str, object],
    ) -> ApprovalRequest:
        window = self.class_d_window if decision_class == DecisionClass.D_EXISTENTIAL else self.class_c_window
        issued = self.now()
        request = ApprovalRequest(
            request_id=new_id("appr"),
            decision_id=decision_id,
            decision_class=decision_class,
            routed_to=routed_to,
            packaged_at=issued,
            expires_at=issued + window,
            context=dict(context),
        )
        self._requests[request.request_id] = request
        return request

    def respond(self, request_id: str, responder_id: str, response: str) -> ApprovalRequest:
        """Records an explicit human response. The only path to an approval."""
        request = self._requests.get(request_id)
        if request is None:
            raise ValidationError(f"approval request '{request_id}' does not exist")
        if not request.is_pending:
            raise ValidationError(f"approval request '{request_id}' already answered at {request.responded_at}")
        if response not in ("approve", "reject", "defer", "modify"):
            raise ValidationError(f"'{response}' is not an approval response")
        answered = ApprovalRequest(
            request_id=request.request_id,
            decision_id=request.decision_id,
            decision_class=request.decision_class,
            routed_to=request.routed_to,
            packaged_at=request.packaged_at,
            expires_at=request.expires_at,
            context=request.context,
            responded_at=self.now(),
            responded_by=responder_id,
            response=response,
        )
        self._requests[request_id] = answered
        return answered

    def timed_out(self) -> list[ApprovalRequest]:
        """Requests past their window. What happens next is never approval."""
        now = self.now()
        return [r for r in self._requests.values() if r.has_timed_out(now)]

    def pending(self) -> list[ApprovalRequest]:
        return [r for r in self._requests.values() if r.is_pending]

    def get(self, request_id: str) -> ApprovalRequest:
        request = self._requests.get(request_id)
        if request is None:
            raise ValidationError(f"approval request '{request_id}' does not exist")
        return request

    def for_decision(self, decision_id: str) -> list[ApprovalRequest]:
        return [r for r in self._requests.values() if r.decision_id == decision_id]


@dataclass
class StandingOrderManager:
    """Issues, renews, revokes and validates standing orders (11.19).

    Every invocation is validated against scope, budget, time window and risk
    threshold. 11.24.2 asks for drift detection on orders "being stretched
    beyond intent", so invocation counts are tracked and exposed.
    """

    now: Callable[[], datetime] = field(default=lambda: datetime.now(UTC))
    _orders: dict[str, StandingOrder] = field(default_factory=dict, init=False)

    def issue(
        self,
        order_id: str,
        issued_by: str,
        tenant_id: str,
        scope: set[str],
        budget_ceiling: float,
        max_risk: RiskClass,
        duration: timedelta,
    ) -> StandingOrder:
        if order_id in self._orders:
            raise ValidationError(f"standing order '{order_id}' already exists")
        if duration > STANDING_ORDER_MAX_DURATION:
            raise ValidationError(
                f"standing orders expire after {STANDING_ORDER_MAX_DURATION.days} days without explicit "
                "renewal (11 rule 11)"
            )
        if duration <= timedelta(0):
            raise ValidationError("a standing order must have a positive duration")
        if not scope:
            raise ValidationError("a standing order must declare its scope")
        issued = self.now()
        order = StandingOrder(
            order_id=order_id,
            issued_by=issued_by,
            tenant_id=tenant_id,
            scope=frozenset(scope),
            budget_ceiling=budget_ceiling,
            max_risk=max_risk,
            issued_at=issued,
            expires_at=issued + duration,
        )
        self._orders[order_id] = order
        return order

    def renew(self, order_id: str, renewed_by: str, duration: timedelta) -> StandingOrder:
        """Explicit renewal. 11 rule 11 permits no implicit extension."""
        order = self.get(order_id)
        if duration > STANDING_ORDER_MAX_DURATION:
            raise ValidationError(f"renewal may not exceed {STANDING_ORDER_MAX_DURATION.days} days (11 rule 11)")
        renewed = StandingOrder(
            order_id=order.order_id,
            issued_by=renewed_by,
            tenant_id=order.tenant_id,
            scope=order.scope,
            budget_ceiling=order.budget_ceiling,
            max_risk=order.max_risk,
            issued_at=self.now(),
            expires_at=self.now() + duration,
            invocations=order.invocations,
        )
        self._orders[order_id] = renewed
        return renewed

    def revoke(self, order_id: str) -> StandingOrder:
        """Immediate revocation. Committed decisions are unaffected (21B §18.8)."""
        order = self.get(order_id)
        revoked = StandingOrder(
            order_id=order.order_id,
            issued_by=order.issued_by,
            tenant_id=order.tenant_id,
            scope=order.scope,
            budget_ceiling=order.budget_ceiling,
            max_risk=order.max_risk,
            issued_at=order.issued_at,
            expires_at=order.expires_at,
            revoked_at=self.now(),
            invocations=order.invocations,
        )
        self._orders[order_id] = revoked
        return revoked

    def validate_invocation(self, order_id: str, proposal: Proposal, decision_class: DecisionClass) -> StandingOrder:
        """Checks an invocation against every declared constraint (11.19)."""
        order = self.get(order_id)
        now = self.now()
        if not order.is_live(now):
            raise StandingOrderViolation(
                f"standing order '{order_id}' is "
                + ("revoked" if order.revoked_at else f"expired (since {order.expires_at.isoformat()})")
            )
        if order.tenant_id != proposal.tenant_id:
            raise StandingOrderViolation(f"standing order '{order_id}' belongs to another tenant")
        if decision_class == DecisionClass.D_EXISTENTIAL:
            raise StandingOrderViolation(
                "standing orders pre-authorize scoped Class C decisions only; Class D is human-only (11.14.2)"
            )
        if not any(proposal.summary.startswith(prefix) for prefix in order.scope):
            raise StandingOrderViolation(f"'{proposal.summary}' is outside the declared scope {sorted(order.scope)}")
        cost = max((o.estimated_cost for o in proposal.options if not o.is_null), default=0.0)
        if cost > order.budget_ceiling:
            raise StandingOrderViolation(
                f"estimated cost {cost} exceeds the order's budget ceiling {order.budget_ceiling}"
            )
        order_of_risk = list(RiskClass)
        if order_of_risk.index(proposal.risk.overall) > order_of_risk.index(order.max_risk):
            raise StandingOrderViolation(
                f"risk '{proposal.risk.overall.value}' exceeds the order's threshold '{order.max_risk.value}'"
            )
        self._orders[order_id] = StandingOrder(
            order_id=order.order_id,
            issued_by=order.issued_by,
            tenant_id=order.tenant_id,
            scope=order.scope,
            budget_ceiling=order.budget_ceiling,
            max_risk=order.max_risk,
            issued_at=order.issued_at,
            expires_at=order.expires_at,
            revoked_at=order.revoked_at,
            invocations=order.invocations + 1,
        )
        return self._orders[order_id]

    def get(self, order_id: str) -> StandingOrder:
        order = self._orders.get(order_id)
        if order is None:
            raise ValidationError(f"standing order '{order_id}' does not exist")
        return order

    def all_orders(self) -> list[StandingOrder]:
        return list(self._orders.values())

    def expire_due(self) -> list[StandingOrder]:
        now = self.now()
        return [o for o in self._orders.values() if o.revoked_at is None and now >= o.expires_at]


@dataclass
class CompensationVerifier:
    """Confirms compensation logic exists before committing (11.21.2).

    "Without compensation logic, the decision is treated as irreversible."
    The verifier does not warn and proceed — it returns the *effective*
    reversibility, and a reversible designation with no compensation is
    downgraded rather than honoured.
    """

    #: Confirms a compensation reference actually resolves to executable logic.
    compensation_exists: Callable[[str], bool] = field(default=lambda _ref: True)

    def effective_reversibility(self, option: Option, human_designated_irreversible: bool) -> tuple[bool, str]:
        if human_designated_irreversible:
            return False, "explicitly designated irreversible by a human (11 rule 4)"
        if not option.reversible:
            return False, "the chosen option is not reversible"
        if option.compensation_ref is None:
            return False, "no pre-positioned compensation logic; treated as irreversible (11.21.2)"
        if not self.compensation_exists(option.compensation_ref):
            return False, f"compensation reference '{option.compensation_ref}' does not resolve (11.21.2)"
        return True, "reversible with verified compensation logic"


@dataclass
class PortfolioCircuitBreaker:
    """Portfolio-level limits on capital at risk and concentration (11.14.4).

    21B §18.15 guarantee 6: "Local optimality does not override portfolio
    concentration limits or circuit breakers." A breach rejects or escalates
    *regardless of local merit*, so the breaker is consulted after evaluation
    but before commitment, and its verdict is not weighed against the score.
    """

    capital_at_risk_ceiling: float = float("inf")
    concentration_ceiling: float = 0.4
    minimum_cash_reserve: float = 0.0
    #: [Engineering Decision] Concentration is meaningless on a near-empty
    #: portfolio: the first commitment to any business is 100% concentrated by
    #: arithmetic, not by risk. The limit is only evaluated once capital at
    #: risk clears this floor, so an empty portfolio is not permanently
    #: unable to make its first commitment.
    concentration_floor: float = 100.0
    _capital_at_risk: float = field(default=0.0, init=False)
    _by_business: dict[str, float] = field(default_factory=dict, init=False)
    _tripped: bool = field(default=False, init=False)

    def would_breach(self, cost: float, business_id: str | None) -> str | None:
        """Reports the breach a commitment would cause, or None."""
        if self._tripped:
            return "portfolio circuit breaker is tripped"
        projected = self._capital_at_risk + cost
        if projected > self.capital_at_risk_ceiling:
            return f"capital at risk would reach {projected}, above the ceiling {self.capital_at_risk_ceiling}"
        if business_id is not None and projected >= self.concentration_floor:
            business_total = self._by_business.get(business_id, 0.0) + cost
            concentration = business_total / projected
            if concentration > self.concentration_ceiling and projected > self.minimum_cash_reserve:
                return (
                    f"business '{business_id}' would hold {concentration:.0%} of capital at risk, "
                    f"above the {self.concentration_ceiling:.0%} concentration limit"
                )
        return None

    def commit(self, cost: float, business_id: str | None) -> None:
        self._capital_at_risk += cost
        if business_id is not None:
            self._by_business[business_id] = self._by_business.get(business_id, 0.0) + cost

    def release(self, cost: float, business_id: str | None) -> None:
        """Returns capital on reversal or completion."""
        self._capital_at_risk = max(0.0, self._capital_at_risk - cost)
        if business_id is not None:
            self._by_business[business_id] = max(0.0, self._by_business.get(business_id, 0.0) - cost)

    def trip(self) -> None:
        self._tripped = True

    def reset(self) -> None:
        self._tripped = False

    @property
    def capital_at_risk(self) -> float:
        return self._capital_at_risk

    @property
    def is_tripped(self) -> bool:
        return self._tripped

    def proximity(self) -> float:
        """How close the portfolio is to its ceiling, 0.0-1.0 (21B §18.11)."""
        if self.capital_at_risk_ceiling in (0, float("inf")):
            return 0.0
        return round(min(1.0, self._capital_at_risk / self.capital_at_risk_ceiling), 4)


def authority_for(decision_class: DecisionClass) -> AuthorityLevel:
    return decision_class.authority
