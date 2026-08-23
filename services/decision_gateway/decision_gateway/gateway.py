"""Decision Gateway — the eight Public Interfaces of 21B §18.5.

| 21B §18.5 interface        | Method                       |
|----------------------------|------------------------------|
| Decision Proposal          | `propose`                    |
| Decision Verification      | `verify`                     |
| Approval Response          | `respond`                    |
| Standing Order Management  | `manage_standing_order`      |
| Reversal Request           | `reverse`                    |
| Outcome Report             | `report_outcome`             |
| Decision Journal Query     | `query_journal`              |
| Decision Health            | `health`                     |

`11.2.4`: "An agent proposes; the Decision subsystem evaluates... Agency is
capacity; Decision is permission."

`11.2.5` makes this the constitutional checkpoint between human will and
machine execution, which is why `verify` exists at all: the Tool, Integration
and Deployment Gateways each require a committed decision record before any
external effect, and this is the interface they ask through.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

from core.exceptions import AgentOSError, NotFoundError
from decision_gateway.decisions import (
    DECISION_TRANSITIONS,
    PANIC_ACTIVE_STATES,
    ApprovalRequest,
    Decision,
    DecisionClass,
    DecisionRecord,
    DecisionState,
    EvidentiaryBurden,
    Proposal,
    StandingOrder,
    new_id,
)
from decision_gateway.pipeline import (
    ApprovalOrchestrator,
    Classifier,
    CompensationVerifier,
    ConfidenceEngine,
    EvaluationEngine,
    EvidenceAssembler,
    OptionValidator,
    PortfolioCircuitBreaker,
    ProposalRejected,
    RiskAssessor,
    StandingOrderManager,
    StandingOrderViolation,
)
from kernel.authority import AuthorityLevel, Outcome, RiskClass, resolve
from kernel.escalation import EscalationChannel, EscalationTrigger
from kernel.journal import ImmutableJournal
from kernel.lifecycle import LifecycleStateMachine
from kernel.signals import SignalEmitter, SignalType

#: [Engineering Decision] 11.5.1 makes Class B "reversible within 24h"; the
#: reversal window follows that figure for every reversible commitment.
REVERSAL_WINDOW = timedelta(hours=24)


class SelfApprovalError(AgentOSError):
    """Approver and requester must be distinct (14.17.5, 21B §18.10)."""


class AuthorityExceeded(AgentOSError):
    """11 rule 5 — no agent commits beyond its autonomy level."""


class DecisionAuthorizer(Protocol):
    """What the Gateway needs from the Security Gateway (21B §18.6)."""

    def principal_of(self, token: str) -> tuple[str, str]: ...

    def is_human(self, principal_id: str) -> bool: ...

    def autonomy_level(self, principal_id: str) -> AuthorityLevel: ...


class KnowledgeSource(Protocol):
    """Contradiction status for cited beliefs (21B §18.6)."""

    def is_contradicted(self, belief_id: str) -> bool: ...


class BudgetSource(Protocol):
    """Budget verification and circuit breaker state (21B §18.6)."""

    def has_headroom(self, tenant_id: str, cost: float) -> bool: ...


@dataclass
class DecisionGateway:
    """Layer 3. The constitutional checkpoint between deliberation and action."""

    authorizer: DecisionAuthorizer
    knowledge: KnowledgeSource
    budget: BudgetSource
    signals: SignalEmitter
    now: Callable[[], datetime] = field(default=lambda: datetime.now(UTC))
    #: Routes escalations and approval requests. Human Interface arrives at S8;
    #: until then the deployment wires whatever channel it has.
    route_to_human: Callable[[str, dict[str, Any]], None] = field(default=lambda _kind, _detail: None)

    def __post_init__(self) -> None:
        self.compensation = CompensationVerifier()
        # The Classifier shares the verifier's judgement so classification and
        # commitment agree on what "reversible" means.
        self.classifier = Classifier(compensation_exists=lambda ref: self.compensation.compensation_exists(ref))
        self.options = OptionValidator()
        self.evidence = EvidenceAssembler(contradiction_check=self.knowledge.is_contradicted)
        self.evaluation = EvaluationEngine()
        self.confidence = ConfidenceEngine()
        self.risk = RiskAssessor()
        self.approvals = ApprovalOrchestrator(now=self.now)
        self.standing_orders = StandingOrderManager(now=self.now)
        self.breaker = PortfolioCircuitBreaker()
        self.journal = ImmutableJournal()
        self.escalations = EscalationChannel(
            subsystem="decision_gateway", is_human=self.authorizer.is_human, now=self.now
        )
        self._records: dict[str, DecisionRecord] = {}
        self._halted = False
        self._rejections = 0
        self._escalations = 0

    # -------------------------------------------------------------- Proposal

    def propose(self, token: str, proposal: Proposal) -> DecisionRecord:
        """**Decision Proposal** (21B §18.5): submit a proposal with options and evidence.

        Runs the funnel of 21B §18.4 in order: classify, validate options,
        assemble evidence, evaluate, resolve authority, verify compensation,
        check the circuit breaker. Each gate can reject; none can be skipped.
        """
        self._require_running()
        principal_id, principal_tenant = self.authorizer.principal_of(token)
        if principal_tenant != proposal.tenant_id:
            raise AgentOSError(f"principal '{principal_id}' may not propose into tenant '{proposal.tenant_id}'")

        # 1. Classification first — it determines every subsequent gate.
        decision_class = self.classifier.classify(proposal)

        # 2. Options, including the null option.
        try:
            self.options.validate(proposal, decision_class)
            # 3. Evidence, with gaps and contradictions flagged explicitly.
            burden = self.evidence.assess(proposal, decision_class)
        except ProposalRejected as rejection:
            self._rejections += 1
            self.journal.append(
                {
                    "kind": "proposal_rejected",
                    "proposal_id": proposal.proposal_id,
                    "class": decision_class.value,
                    "gate": rejection.gate,
                    "reason": rejection.reason,
                }
            )
            self.signals.emit(
                SignalType.EVENT,
                "decision.proposal.rejected",
                proposal.tenant_id,
                gate=rejection.gate,
                decision_class=decision_class.value,
            )
            raise

        # 4. Evaluation. Concentration is a portfolio input, not a local one.
        concentrated = self.breaker.would_breach(0.0, proposal.business_id) is not None
        chosen, score = self.evaluation.choose(proposal, concentrated)
        quality = self.evaluation.option_quality(proposal, score)
        confidence = self.confidence.derive(proposal.evidence, option_quality=quality, risk=proposal.risk.overall)

        # 5. Authority, risk-adjusted, via the kernel's shared resolver.
        actor_level = self.authorizer.autonomy_level(principal_id)
        verdict = resolve(
            class_level=decision_class.authority,
            actor_level=actor_level,
            confidence=confidence,
            risk=proposal.risk.overall,
            evidence_contradictory=burden == EvidentiaryBurden.CONTRADICTORY,
        )

        # 6. Compensation before commitment, never after failure.
        reversible, reversibility_reason = self.compensation.effective_reversibility(
            chosen, proposal.human_designated_irreversible
        )

        decision = Decision(
            decision_id=new_id("dec"),
            proposal=proposal,
            decision_class=decision_class,
            burden=burden,
            confidence=confidence,
            required_authority=verdict.required_level,
            chosen_option=chosen,
            rationale=(
                f"chose '{chosen.option_id}' at score {score} over "
                f"{len(proposal.options) - 1} alternatives; {reversibility_reason}"
            ),
            expected_outcome=f"{chosen.description} yields approximately {chosen.expected_value}",
            reversible=reversible,
            formed_at=self.now(),
        )
        record = DecisionRecord(decision=decision)
        self._records[decision.decision_id] = record
        self._journal(record, "proposed", confidence=confidence, burden=burden.value)

        # A standing order can pre-authorize a scoped Class C decision.
        if proposal.standing_order_ref is not None:
            return self._apply_standing_order(record, proposal, decision_class, principal_id)

        return self._route(record, verdict.outcome, principal_id, actor_level, burden)

    def _route(
        self,
        record: DecisionRecord,
        outcome: Outcome,
        principal_id: str,
        actor_level: AuthorityLevel,
        burden: EvidentiaryBurden,
    ) -> DecisionRecord:
        """Sends the proposal down exactly one of the paths 11.8.2 permits."""
        if burden == EvidentiaryBurden.CONTRADICTORY:
            # 11 rule 8 — no autonomous path past unresolved contradiction.
            return self._escalate(record, "evidence is contradictory; human arbitration required (11 rule 8)")

        if outcome == Outcome.INSUFFICIENT_CONFIDENCE:
            # 21B §18.9 — agents may not suppress the warning.
            return self._defer(
                record,
                f"confidence {record.decision.confidence} is below the floor for authority level "
                f"{int(record.decision.required_authority)} (11.9.2)",
            )

        # 11.14.3 — "a Class B decision at High risk is treated as Class C for
        # authority purposes". Treated as Class C means it takes the Class C
        # *path*: a packaged human approval request. Routing it to Escalated
        # instead would raise the bar and then provide no way to clear it.
        if record.decision.required_authority.requires_human:
            return self._request_approval(record)

        if outcome == Outcome.ESCALATE:
            return self._escalate(
                record,
                f"actor at level {int(actor_level)} cannot authorize a level "
                f"{int(record.decision.required_authority)} action",
            )

        # Class A or B, authority matches, evidence sufficient: Proposed -> Approved.
        self._transition(record, DecisionState.APPROVED)
        record.authorized_by = principal_id
        record.authorized_at = self.now()
        self._journal(record, "approved", authorized_by=principal_id)
        return record

    def _apply_standing_order(
        self,
        record: DecisionRecord,
        proposal: Proposal,
        decision_class: DecisionClass,
        principal_id: str,
    ) -> DecisionRecord:
        """Validates a standing-order invocation against every constraint (11.19)."""
        order_ref = proposal.standing_order_ref
        if order_ref is None:  # unreachable: the caller checks before routing here
            return self._escalate(record, "standing order invocation carried no order reference")
        try:
            order = self.standing_orders.validate_invocation(order_ref, proposal, decision_class)
        except StandingOrderViolation as violation:
            self._journal(record, "standing_order_violation", reason=str(violation))
            self.signals.emit(
                SignalType.EVENT,
                "decision.standing_order.violation",
                proposal.tenant_id,
                order=order_ref,
                reason=str(violation),
            )
            return self._escalate(record, f"standing order invocation refused: {violation}")

        self._transition(record, DecisionState.APPROVED)
        record.authorized_by = order.issued_by
        record.authorized_at = self.now()
        self._journal(record, "approved", authorized_by=order.issued_by, via_standing_order=order.order_id)
        return record

    # -------------------------------------------------------------- Approval

    def _request_approval(self, record: DecisionRecord) -> DecisionRecord:
        """Packages a Class C or D decision for explicit human action (11.18)."""
        self._transition(record, DecisionState.UNDER_REVIEW)
        # A decision escalated to Level 4 by risk gets the Class D window even
        # if its nominal class is lower — the window follows the authority the
        # decision actually requires.
        effective_class = (
            DecisionClass.D_EXISTENTIAL
            if record.decision.required_authority == AuthorityLevel.HUMAN_SOVEREIGN
            else max(record.decision_class, DecisionClass.C_STRATEGIC, key=lambda c: c.rank)
        )
        request = self.approvals.package(
            decision_id=record.decision_id,
            decision_class=effective_class,
            routed_to="human_sovereign",
            context={
                "summary": record.decision.proposal.summary,
                "class": record.decision_class.value,
                "confidence": record.decision.confidence,
                "risk": record.decision.proposal.risk.overall.value,
                "chosen_option": record.decision.chosen_option.option_id,
                "alternatives": [o.option_id for o in record.decision.proposal.options],
                "expected_outcome": record.decision.expected_outcome,
                "reversible": record.decision.reversible,
            },
        )
        self._journal(record, "approval_requested", request_id=request.request_id)
        self.route_to_human("approval_request", {"request_id": request.request_id, **request.context})
        return record

    def respond(self, request_id: str, responder_id: str, response: str) -> DecisionRecord:
        """**Approval Response** (21B §18.5). Consumer: Human Interface.

        Only a human may answer a Class C or D request, and never the same
        principal that proposed it — 14.17.5's self-approval prohibition,
        enforced here at the point it would otherwise be bypassed.
        """
        request = self.approvals.get(request_id)
        record = self.get(request.decision_id)

        if not self.authorizer.is_human(responder_id):
            self.escalations.raise_incident(
                EscalationTrigger.AUTHORITY_BYPASS,
                responder_id,
                record.decision.proposal.tenant_id,
                "non-human attempted to answer a Class C/D approval request",
                {"request_id": request_id, "decision_id": record.decision_id},
            )
            raise AuthorityExceeded(
                f"'{responder_id}' is not a Human principal; Class {record.decision_class.value} requires "
                "explicit human approval (11 rule 2)"
            )
        if responder_id == record.decision.proposal.proposer_id:
            self.escalations.raise_incident(
                EscalationTrigger.AUTHORITY_BYPASS,
                responder_id,
                record.decision.proposal.tenant_id,
                "principal attempted to approve its own proposal",
                {"request_id": request_id, "decision_id": record.decision_id},
            )
            raise SelfApprovalError(f"'{responder_id}' proposed this decision and may not approve it (14.17.5)")

        self.approvals.respond(request_id, responder_id, response)
        if response == "approve":
            self._transition(record, DecisionState.APPROVED)
            record.authorized_by = responder_id
            record.authorized_at = self.now()
            self._journal(record, "approved", authorized_by=responder_id)
        elif response == "reject":
            self._reject(record, f"rejected by {responder_id}")
        elif response == "defer":
            self._defer(record, f"deferred by {responder_id}")
        else:  # modify
            self._defer(record, f"modification demanded by {responder_id}")
        return record

    def sweep_timeouts(self) -> list[DecisionRecord]:
        """Applies timeout semantics. **Never approves** (11 rule 3, 11.18.3).

        Class C is deferred; Class D is rejected. There is no branch here that
        produces an approval, and `test_no_timeout_path_approves` asserts it.
        """
        affected: list[DecisionRecord] = []
        for request in self.approvals.timed_out():
            record = self.get(request.decision_id)
            if record.state != DecisionState.UNDER_REVIEW:
                continue
            if request.decision_class == DecisionClass.D_EXISTENTIAL:
                self._reject(record, "Class D approval window elapsed without explicit human action (11 rule 3)")
            else:
                self._defer(record, "Class C approval window elapsed without explicit human action (11 rule 3)")
            self.signals.emit(
                SignalType.EVENT,
                "decision.approval.timeout",
                record.decision.proposal.tenant_id,
                decision_class=request.decision_class.value,
                outcome=record.state.value,
            )
            affected.append(record)
        return affected

    # ------------------------------------------------------------ Commitment

    def commit(self, decision_id: str, committer_id: str) -> DecisionRecord:
        """Approved -> Committed. The last gate before an effect exists.

        Checks the portfolio circuit breaker here rather than at proposal,
        because capital at risk changes between the two and 21B §18.15
        guarantee 6 makes the breaker override local merit at the moment of
        commitment.
        """
        self._require_running()
        record = self.get(decision_id)
        if record.state != DecisionState.APPROVED:
            raise AgentOSError(f"decision '{decision_id}' is {record.state.value}, not Approved")

        cost = record.decision.chosen_option.estimated_cost
        tenant = record.decision.proposal.tenant_id
        # 21B §18.9 makes a circuit-breaker breach "Rejected or escalated
        # regardless of local merit". From Approved, 11.8.2 permits only
        # Approved -> Rejected, so the breach rejects rather than escalates —
        # the ratified transition table is not extended to suit the response.
        breach = self.breaker.would_breach(cost, record.decision.proposal.business_id)
        if breach is not None:
            self.signals.emit(SignalType.EVENT, "decision.circuit_breaker.breach", tenant, reason=breach)
            return self._reject(record, f"portfolio circuit breaker: {breach} (11.14.4)")
        if not self.budget.has_headroom(tenant, cost):
            return self._reject(record, "cost manager reports no budget headroom for this commitment")

        self._transition(record, DecisionState.COMMITTED)
        record.committed_at = self.now()
        if record.decision.reversible:
            record.reversal_deadline = record.committed_at + REVERSAL_WINDOW
        self.breaker.commit(cost, record.decision.proposal.business_id)
        self._journal(record, "committed", committer=committer_id, reversible=record.decision.reversible)
        self.signals.emit(
            SignalType.METRIC,
            "decision.committed",
            tenant,
            value=cost,
            decision_class=record.decision_class.value,
            confidence=record.decision.confidence,
        )
        return record

    def verify(self, decision_id: str, required_class: DecisionClass) -> DecisionRecord:
        """**Decision Verification** (21B §18.5). Consumers: Tool, Integration, Deployment.

        Answers one question: does a committed decision exist whose authority
        matches or exceeds what this effect requires. 12 rule 2, 17 rule 2 and
        18 rule 2 each demand this before any external effect.
        """
        record = self.get(decision_id)
        if not record.is_committed:
            raise AgentOSError(
                f"decision '{decision_id}' is {record.state.value}, not committed; no effect may proceed (11 rule 6)"
            )
        if record.decision_class.rank < required_class.rank:
            raise AuthorityExceeded(
                f"decision '{decision_id}' is Class {record.decision_class.value} but the effect requires "
                f"Class {required_class.value}"
            )
        return record

    # ------------------------------------------------------ Execution & outcome

    def mark_executing(self, decision_id: str) -> DecisionRecord:
        """Runtime acknowledges receipt and begins execution (11.8.2)."""
        record = self.get(decision_id)
        self._transition(record, DecisionState.EXECUTING)
        self._journal(record, "executing")
        return record

    def report_outcome(self, decision_id: str, actual_outcome: str) -> DecisionRecord:
        """**Outcome Report** (21B §18.5). Consumers: Workflow Engine, Agent Runtime.

        Immutable once recorded (21B §18.8). Divergence from the expected
        outcome triggers learning — 21B §18.3's Outcome Recorder exists for
        exactly this, and it is why 11 rule 16 requires the prediction.
        """
        record = self.get(decision_id)
        if record.actual_outcome is not None:
            raise AgentOSError(f"decision '{decision_id}' already recorded an outcome; corrections append")
        if record.state == DecisionState.EXECUTING:
            self._transition(record, DecisionState.COMPLETED)
        record.actual_outcome = actual_outcome
        record.outcome_recorded_at = self.now()
        self.breaker.release(record.decision.chosen_option.estimated_cost, record.decision.proposal.business_id)
        self._journal(record, "outcome_recorded", actual=actual_outcome, diverged=record.outcome_diverged)
        if record.outcome_diverged:
            self.signals.emit(
                SignalType.EVENT,
                "decision.outcome.diverged",
                record.decision.proposal.tenant_id,
                decision_id=decision_id,
                expected=record.decision.expected_outcome,
                actual=actual_outcome,
            )
        return record

    # ------------------------------------------------- Reversal & supersession

    def reverse(self, decision_id: str, requester_id: str, reason: str) -> DecisionRecord:
        """**Reversal Request** (21B §18.5), within the reversibility window.

        A reversal is itself a new decision entry linked by lineage (21B
        §18.4); it does not erase what it reverses.
        """
        record = self.get(decision_id)
        if not record.decision.reversible:
            raise AgentOSError(
                f"decision '{decision_id}' is irreversible; there is no compensation path to execute (11.21.2)"
            )
        if not record.within_reversal_window(self.now()):
            raise AgentOSError(f"the reversibility window for '{decision_id}' closed at {record.reversal_deadline}")
        self._transition(record, DecisionState.REVERSED)
        record.reversed_by = requester_id
        self.breaker.release(record.decision.chosen_option.estimated_cost, record.decision.proposal.business_id)
        self._journal(
            record,
            "reversed",
            requester=requester_id,
            reason=reason,
            compensation=record.decision.chosen_option.compensation_ref,
        )
        return record

    def supersede(self, decision_id: str, successor_id: str, authorized_by: str) -> DecisionRecord:
        """Replaces a decision, preserving lineage (11.22)."""
        record = self.get(decision_id)
        successor = self.get(successor_id)
        self._transition(record, DecisionState.SUPERSEDED)
        record.superseded_by = successor_id
        successor.supersedes = decision_id
        self.breaker.release(record.decision.chosen_option.estimated_cost, record.decision.proposal.business_id)
        self._journal(record, "superseded", by=successor_id, authorized_by=authorized_by)
        return record

    # ----------------------------------------------------- Standing orders

    def manage_standing_order(
        self,
        operation: str,
        order_id: str,
        actor_id: str,
        tenant_id: str | None = None,
        scope: set[str] | None = None,
        budget_ceiling: float = 0.0,
        max_risk: RiskClass = RiskClass.MODERATE,
        duration: timedelta | None = None,
    ) -> StandingOrder:
        """**Standing Order Management** (21B §18.5). Consumer: Human Interface.

        Only a human may issue or renew one: a standing order delegates human
        approval authority for scoped Class C decisions (11.14.2), and a
        machine granting itself that authority is precisely the
        privilege-escalation surface 21B §18.10 warns about.
        """
        if operation in ("issue", "renew") and not self.authorizer.is_human(actor_id):
            raise AuthorityExceeded(
                f"'{actor_id}' is not a Human principal; standing orders delegate human approval "
                "authority and may only be issued by a human (11.14.2)"
            )
        if operation == "issue":
            if tenant_id is None or scope is None or duration is None:
                raise AgentOSError("issue requires tenant_id, scope and duration")
            order = self.standing_orders.issue(order_id, actor_id, tenant_id, scope, budget_ceiling, max_risk, duration)
            self.journal.append(
                {"kind": "standing_order_issued", "order_id": order_id, "by": actor_id, "scope": sorted(scope)}
            )
            return order
        if operation == "renew":
            if duration is None:
                raise AgentOSError("renew requires a duration")
            order = self.standing_orders.renew(order_id, actor_id, duration)
            self.journal.append({"kind": "standing_order_renewed", "order_id": order_id, "by": actor_id})
            return order
        if operation == "revoke":
            order = self.standing_orders.revoke(order_id)
            self.journal.append({"kind": "standing_order_revoked", "order_id": order_id, "by": actor_id})
            return order
        raise AgentOSError(f"unknown standing order operation '{operation}'")

    # ------------------------------------------------------------- Overrides

    def override(self, decision_id: str, human_id: str, target: DecisionState, reason: str) -> DecisionRecord:
        """Human override at any state, logged as a Class D action (11.9.3).

        Overrides are immediate and irreversible by the runtime. They bypass
        the ordinary transition table, which is why they are recorded as
        constitutional exceptions (11.8.4).
        """
        if not self.authorizer.is_human(human_id):
            raise AuthorityExceeded(f"'{human_id}' is not a Human principal; overrides are Class D acts (11.9.3)")
        record = self.get(decision_id)
        previous = record.state
        record.state = target  # deliberate bypass of the guarded transition
        self._journal(
            record,
            "override",
            by=human_id,
            from_state=previous.value,
            to_state=target.value,
            reason=reason,
            authority="class_d",
            constitutional_exception=True,
        )
        return record

    def panic(self) -> list[DecisionRecord]:
        """Panic Protocol integration (11.9.4).

        Every active decision goes to Deferred, or Reversed if it is still
        reversible. New proposals halt until a human resumes. Panic is itself
        a Class D act executed directly by the human operator.
        """
        self._halted = True
        affected: list[DecisionRecord] = []
        now = self.now()
        for record in self._records.values():
            if record.state not in PANIC_ACTIVE_STATES:
                continue
            if record.decision.reversible and record.within_reversal_window(now):
                record.state = DecisionState.REVERSED
                record.reversed_by = "panic_protocol"
            else:
                record.state = DecisionState.DEFERRED
                record.deferral_reason = "Panic Protocol invoked"
            self._journal(record, "panic", outcome=record.state.value, constitutional_exception=True)
            affected.append(record)
        return affected

    def resume(self, human_id: str) -> None:
        """Only a human resumes after a panic (11.9.4)."""
        if not self.authorizer.is_human(human_id):
            raise AuthorityExceeded(f"'{human_id}' is not a Human principal; resuming requires human intervention")
        self._halted = False
        self.journal.append({"kind": "panic_resumed", "by": human_id})

    # ----------------------------------------------------------------- Query

    def query_journal(
        self,
        decision_id: str | None = None,
        tenant_id: str | None = None,
        action: str | None = None,
    ) -> list[Mapping[str, Any]]:
        """**Decision Journal Query** (21B §18.5). Consumers: Governance, Learning, Observability."""
        entries: list[Mapping[str, Any]] = []
        for seq in range(len(self.journal)):
            payload = self.journal[seq].payload
            if decision_id is not None and payload.get("decision_id") != decision_id:
                continue
            if tenant_id is not None and payload.get("tenant_id") != tenant_id:
                continue
            if action is not None and payload.get("action") != action:
                continue
            entries.append(payload)
        return entries

    def health(self) -> Mapping[str, Any]:
        """**Decision Health** (21B §18.5) — the five metric families of 11.26.1."""
        records = list(self._records.values())
        by_state: dict[str, int] = {}
        by_class: dict[str, int] = {}
        for record in records:
            by_state[record.state.value] = by_state.get(record.state.value, 0) + 1
            by_class[record.decision_class.value] = by_class.get(record.decision_class.value, 0) + 1
        committed = [r for r in records if r.is_committed or r.state == DecisionState.REVERSED]
        reversed_count = sum(1 for r in records if r.state == DecisionState.REVERSED)
        resolved = [r for r in records if r.actual_outcome is not None]
        diverged = [r for r in resolved if r.outcome_diverged]
        return {
            "velocity": {"proposals": len(records), "by_class": by_class},
            "latency": {"pending_approvals": len(self.approvals.pending())},
            "quality": {
                "reversal_rate": round(reversed_count / len(committed), 4) if committed else 0.0,
                "supersession_rate": round(
                    sum(1 for r in records if r.state == DecisionState.SUPERSEDED) / len(records), 4
                )
                if records
                else 0.0,
                "outcome_divergence_rate": round(len(diverged) / len(resolved), 4) if resolved else 0.0,
                "confidence_calibration": self._calibration(resolved),
            },
            "governance": {
                "escalation_rate": round(self._escalations / len(records), 4) if records else 0.0,
                "rejections": self._rejections,
                "standing_orders": len(self.standing_orders.all_orders()),
                "standing_order_invocations": sum(o.invocations for o in self.standing_orders.all_orders()),
            },
            "health": {
                "by_state": by_state,
                "halted": self._halted,
                "circuit_breaker_proximity": self.breaker.proximity(),
                "capital_at_risk": self.breaker.capital_at_risk,
                "unacknowledged_incidents": len(self.escalations.unacknowledged()),
            },
            "journal_entries": len(self.journal),
            "journal_intact": self.journal.verify_chain(),
        }

    def _calibration(self, resolved: list[DecisionRecord]) -> float | None:
        """Predicted-versus-actual confidence performance (21B §18.11).

        CIR-007 names miscalibration propagating through four subsystems as an
        open risk, so 21B §18.11 requires this to be *exposed*, not merely
        computed internally. Returns None rather than a misleading zero when
        nothing has resolved yet.
        """
        if not resolved:
            return None
        accurate = [r for r in resolved if not r.outcome_diverged]
        mean_confidence = sum(r.decision.confidence for r in resolved) / len(resolved)
        actual_rate = len(accurate) / len(resolved)
        return round(actual_rate - mean_confidence, 4)

    # ------------------------------------------------------------- Internals

    def get(self, decision_id: str) -> DecisionRecord:
        record = self._records.get(decision_id)
        if record is None:
            raise NotFoundError(f"decision '{decision_id}' does not exist")
        return record

    def pending_approval(self) -> list[ApprovalRequest]:
        return self.approvals.pending()

    def _escalate(self, record: DecisionRecord, reason: str) -> DecisionRecord:
        self._transition(record, DecisionState.ESCALATED)
        record.escalated_to = "human_sovereign"
        self._escalations += 1
        self._journal(record, "escalated", reason=reason)
        self.route_to_human(
            "escalation", {"decision_id": record.decision_id, "reason": reason, "class": record.decision_class.value}
        )
        return record

    def _defer(self, record: DecisionRecord, reason: str) -> DecisionRecord:
        self._transition(record, DecisionState.DEFERRED)
        record.deferral_reason = reason
        self._journal(record, "deferred", reason=reason)
        return record

    def _reject(self, record: DecisionRecord, reason: str) -> DecisionRecord:
        self._transition(record, DecisionState.REJECTED)
        record.rejection_reason = reason
        self._rejections += 1
        self._journal(record, "rejected", reason=reason)
        return record

    def _transition(self, record: DecisionRecord, target: DecisionState) -> None:
        machine = LifecycleStateMachine(transitions=dict(DECISION_TRANSITIONS), state=record.state)
        machine.transition(target)
        record.state = target

    def _journal(self, record: DecisionRecord, action: str, **detail: Any) -> None:
        self.journal.append(
            {
                "kind": "decision",
                "action": action,
                "decision_id": record.decision_id,
                "proposal_id": record.decision.proposal.proposal_id,
                "tenant_id": record.decision.proposal.tenant_id,
                "class": record.decision_class.value,
                "state": record.state.value,
                "proposer": record.decision.proposal.proposer_id,
                **detail,
            }
        )

    def _require_running(self) -> None:
        if self._halted:
            raise AgentOSError("Panic Protocol is active; new proposals are halted pending human intervention (11.9.4)")
