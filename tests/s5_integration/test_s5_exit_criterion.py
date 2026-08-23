"""Stage S5 exit criterion, demonstrated end to end.

Build Specification, Stage S5, Validation Criteria — Class A–D commitments with
options and evidence grounding; authority resolution by decision class and
autonomy level; structural enforcement that Level 3/4 approval gates never
auto-approve on timeout; reversal with compensation; supersession with lineage
tracking — "including an adversarial test attempting to force an auto-approval
on a Class D decision, which must fail".

This suite drives the Decision Gateway against real Security, Knowledge,
Memory and Cost Manager instances, so authority, contradiction status and
budget headroom are all genuine.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from core.exceptions import AgentOSError
from cost_manager import BudgetScope, CostManager, ScopeKind
from decision_gateway import (
    CostManagerBudgetSource,
    DecisionClass,
    DecisionGateway,
    DecisionRecord,
    DecisionState,
    EvidenceRef,
    KnowledgeGatewayEvidenceSource,
    Option,
    Proposal,
    RiskAssessment,
    Scope,
    SecurityGatewayDecisionAuthorizer,
)
from kernel.authority import AuthorityLevel, RiskClass
from kernel.signals import SignalEmitter
from knowledge_gateway import (
    KnowledgeGateway,
    MemoryGatewayEvidenceSource,
    SecurityGatewayKnowledgeAuthorizer,
)
from memory_gateway import MemoryGateway, SecurityGatewayMemoryAuthorizer
from observability_gateway import ObservabilityGateway, SecurityGatewayQueryAuthorizer
from security_gateway import (
    Capability,
    PrincipalType,
    RegistrationRequest,
    Role,
    SecurityGateway,
)
from security_gateway.enums import PrincipalStatus

TENANT = "tenant-alpha"
HUMAN = "human-sovereign"
AGENT = "agent-planner"
VERIFIER = "hash-planner"
BUSINESS = "business-one"

PERMISSIONS = {"decision.propose", "observability.query.internal"}


class Clock:
    def __init__(self) -> None:
        self.now = datetime(2026, 8, 1, 12, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.now

    def advance(self, delta: timedelta) -> None:
        self.now += delta


class NullSecretStore:
    def read(self, reference: str) -> str:
        raise KeyError(reference)

    def write(self, reference: str, value: str) -> None:
        pass


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def security(clock: Clock) -> SecurityGateway:
    gw = SecurityGateway(signing_key=b"s5-integration-key", secret_store=NullSecretStore(), now=clock)
    gw.bootstrap_human_sovereign(HUMAN, "Sovereign", TENANT)
    gw.register_identity(
        RegistrationRequest(
            principal_id=AGENT,
            principal_type=PrincipalType.AGENT,
            name="Planner",
            version="1.0.0",
            tenant_id=TENANT,
            autonomy_level=2,
            approved_by=HUMAN,
        )
    )
    gw.change_principal_status(AGENT, PrincipalStatus.ACTIVE, actor_id=HUMAN)
    gw.capabilities.define(Capability(name="planning", permits=frozenset(PERMISSIONS)))
    gw.capabilities.grant(AGENT, "planning")
    gw.roles.define(
        Role(name="planner", permissions=frozenset(PERMISSIONS), eligible_types=frozenset({PrincipalType.AGENT}))
    )
    gw.roles.assign("planner", AGENT, PrincipalType.AGENT, assigned_by=HUMAN)
    gw.recompute_permissions(AGENT)
    gw.credentials.issue(f"cred-{AGENT}", AGENT, PrincipalType.AGENT, VERIFIER)
    return gw


@pytest.fixture
def observability(security: SecurityGateway, clock: Clock) -> ObservabilityGateway:
    return ObservabilityGateway(authorizer=SecurityGatewayQueryAuthorizer(gateway=security), now=clock)


@pytest.fixture
def decisions(security: SecurityGateway, observability: ObservabilityGateway, clock: Clock) -> DecisionGateway:
    memory = MemoryGateway(
        authorizer=SecurityGatewayMemoryAuthorizer(gateway=security),
        signals=SignalEmitter(source_identity="memory_gateway", sink=observability.sink_for("memory_gateway")),
        now=clock,
    )
    knowledge = KnowledgeGateway(
        authorizer=SecurityGatewayKnowledgeAuthorizer(gateway=security),
        memory=MemoryGatewayEvidenceSource(gateway=memory),
        signals=SignalEmitter(source_identity="knowledge_gateway", sink=observability.sink_for("knowledge_gateway")),
        now=clock,
    )
    costs = CostManager(
        signals=SignalEmitter(source_identity="cost_manager", sink=observability.sink_for("cost_manager")),
        escalate=lambda kind, detail: None,
        now=clock,
    )
    costs.allocate(BudgetScope(kind=ScopeKind.TENANT, identifier=TENANT), TENANT, limit=10_000.0)
    return DecisionGateway(
        authorizer=SecurityGatewayDecisionAuthorizer(gateway=security),
        knowledge=KnowledgeGatewayEvidenceSource(gateway=knowledge),
        budget=CostManagerBudgetSource(manager=costs),
        signals=SignalEmitter(source_identity="decision_gateway", sink=observability.sink_for("decision_gateway")),
        now=clock,
    )


@pytest.fixture
def token(security: SecurityGateway) -> str:
    issued, _ = security.authenticate(AGENT, f"cred-{AGENT}", VERIFIER, PrincipalType.AGENT)
    return issued


def state_of(decisions: DecisionGateway, record: DecisionRecord) -> DecisionState:
    """The Gateway's stored state for a record.

    Assertions read through this rather than off a local, so they check what
    the Gateway actually persisted and are not narrowed away by a type
    checker tracking the local's last known value.
    """
    return decisions.get(record.decision_id).state


def _risk(level: RiskClass = RiskClass.LOW) -> RiskAssessment:
    return RiskAssessment(
        financial=level,
        operational=RiskClass.LOW,
        reputational=RiskClass.LOW,
        legal=RiskClass.LOW,
        strategic=RiskClass.LOW,
    )


def _evidence(count: int = 2, confidence: float = 0.95) -> tuple[EvidenceRef, ...]:
    return tuple(
        EvidenceRef(source="knowledge", reference_id=f"belief-{i}", confidence=confidence, statement=f"b{i}")
        for i in range(count)
    )


def _options(cost: float = 0.005, compensation: str | None = "comp-1") -> tuple[Option, ...]:
    return (
        Option("null", "do nothing", 0.0, 0.0, reversible=True, is_null=True),
        Option("act", "the preferred action", cost, 1.0, reversible=True, compensation_ref=compensation),
        Option(
            "alt",
            "the alternative",
            cost * 0.8,
            0.4,
            reversible=True,
            compensation_ref="comp-2" if compensation is not None else None,
        ),
    )


def _proposal(
    summary: str,
    scope: Scope = Scope.TASK,
    cost: float = 0.005,
    confidence: float = 0.95,
    count: int = 2,
    risk: RiskClass = RiskClass.LOW,
    compensation: str | None = "comp-1",
) -> Proposal:
    return Proposal(
        proposal_id=f"prop-{summary[:10].replace(' ', '-')}",
        summary=summary,
        proposer_id=AGENT,
        proposer_authority=AuthorityLevel.AGENT_DELEGATED,
        tenant_id=TENANT,
        business_id=BUSINESS,
        options=_options(cost, compensation),
        evidence=_evidence(count, confidence),
        risk=_risk(risk),
        scope=scope,
    )


def test_s5_exit_criterion(
    decisions: DecisionGateway, observability: ObservabilityGateway, token: str, clock: Clock
) -> None:
    # 1. Class A: trivial, reversible, autonomously approved and committed.
    class_a = decisions.propose(token, _proposal("tune a retry interval"))
    assert class_a.decision_class == DecisionClass.A_TRIVIAL
    assert state_of(decisions, class_a) == DecisionState.APPROVED
    decisions.commit(class_a.decision_id, committer_id=AGENT)
    assert state_of(decisions, class_a) == DecisionState.COMMITTED

    # 2. Class B: operational, still within the agent's Level 2 autonomy.
    class_b = decisions.propose(token, _proposal("refresh the cache tier", cost=5.0))
    assert class_b.decision_class == DecisionClass.B_OPERATIONAL
    assert state_of(decisions, class_b) == DecisionState.APPROVED

    # 3. Class C: strategic, routed for explicit human approval and no further.
    class_c = decisions.propose(token, _proposal("change the pricing page", scope=Scope.BUSINESS))
    assert class_c.decision_class == DecisionClass.C_STRATEGIC
    assert state_of(decisions, class_c) == DecisionState.UNDER_REVIEW
    with pytest.raises(AgentOSError):
        decisions.commit(class_c.decision_id, committer_id=AGENT)

    request = decisions.approvals.for_decision(class_c.decision_id)[0]
    decisions.respond(request.request_id, responder_id=HUMAN, response="approve")
    assert state_of(decisions, class_c) == DecisionState.APPROVED
    assert class_c.authorized_by == HUMAN

    # 4. Class D: existential, human-only, and it does not move without one.
    class_d = decisions.propose(
        token, _proposal("wind down the business line", scope=Scope.PORTFOLIO, count=3, confidence=0.99)
    )
    assert class_d.decision_class == DecisionClass.D_EXISTENTIAL
    assert state_of(decisions, class_d) == DecisionState.UNDER_REVIEW

    # 5. Authority resolution by class and autonomy: the Level 2 agent could
    #    authorize A and B itself, and neither C nor D.
    assert class_a.authorized_by == AGENT
    assert class_b.authorized_by == AGENT
    assert class_d.authorized_by is None

    # 6. Reversal with compensation, inside the window.
    decisions.reverse(class_a.decision_id, requester_id=HUMAN, reason="metric regressed")
    assert state_of(decisions, class_a) == DecisionState.REVERSED
    reversal = decisions.query_journal(decision_id=class_a.decision_id, action="reversed")[0]
    assert reversal["compensation"] == "comp-1"

    # 7. Supersession with lineage tracking.
    decisions.commit(class_c.decision_id, committer_id=HUMAN)
    decisions.mark_executing(class_c.decision_id)
    successor = decisions.propose(token, _proposal("revise the pricing page again"))
    decisions.supersede(class_c.decision_id, successor.decision_id, authorized_by=HUMAN)
    assert state_of(decisions, class_c) == DecisionState.SUPERSEDED
    assert class_c.superseded_by == successor.decision_id
    assert successor.supersedes == class_c.decision_id

    # 8. The whole run is reconstructable, and the journal resists tampering.
    assert decisions.health()["journal_intact"] is True
    trail = {e["action"] for e in decisions.query_journal(decision_id=class_c.decision_id)}
    assert {"proposed", "approval_requested", "approved", "committed", "superseded"} <= trail

    # 9. The economics of the run reached Observability.
    emitted = {s.signal.name for s in observability.ingest_engine.all_signals()}
    assert "decision.committed" in emitted


def test_adversarial_class_d_cannot_be_auto_approved(decisions: DecisionGateway, token: str, clock: Clock) -> None:
    """Stage S5 Validation Criteria: the adversarial test, which must fail to approve.

    Four distinct attacks on the Class D gate, each of which a naive
    implementation would fall to:

    1. Wait out the approval window and hope silence reads as consent.
    2. Have the proposing agent answer its own request.
    3. Have a non-human service answer it.
    4. Skip the request entirely and commit directly.
    """
    record = decisions.propose(
        token, _proposal("liquidate the portfolio", scope=Scope.PORTFOLIO, count=3, confidence=0.99)
    )
    assert record.decision_class == DecisionClass.D_EXISTENTIAL
    assert state_of(decisions, record) == DecisionState.UNDER_REVIEW
    request = decisions.approvals.for_decision(record.decision_id)[0]

    # Attack 1: outlast the window, repeatedly.
    for days in (4, 30, 400):
        clock.advance(timedelta(days=days))
        decisions.sweep_timeouts()
        # Re-read the stored record each time rather than trusting a local:
        # the assertion is about what the Gateway persisted, not what this
        # frame happens to hold.
        current = decisions.get(record.decision_id).state
        assert current != DecisionState.APPROVED, f"auto-approved after {days} days"
        assert current != DecisionState.COMMITTED

    # Attack 2: self-approval by the proposer.
    from decision_gateway import AuthorityExceeded, SelfApprovalError

    with pytest.raises((SelfApprovalError, AuthorityExceeded)):
        decisions.respond(request.request_id, responder_id=AGENT, response="approve")

    # Attack 3: a non-human answering.
    with pytest.raises(AuthorityExceeded):
        decisions.respond(request.request_id, responder_id="service-scheduler", response="approve")

    # Attack 4: commit without an approval at all.
    with pytest.raises(AgentOSError):
        decisions.commit(record.decision_id, committer_id=AGENT)

    assert state_of(decisions, record) == DecisionState.REJECTED
    assert decisions.get(record.decision_id).authorized_by is None


def test_the_gateway_records_commitments_and_does_not_execute_them() -> None:
    """21B §18.7 — it owns no execution state; it records commitments.

    An `execute` method on this surface would mean the checkpoint had become
    the actor, collapsing the separation 11.2.4 draws between agency and
    permission.
    """
    surface = {name for name in dir(DecisionGateway) if not name.startswith("_")}
    assert {"execute", "run", "invoke", "perform", "dispatch"}.isdisjoint(surface)


def test_every_committed_decision_carries_an_expected_outcome(decisions: DecisionGateway, token: str) -> None:
    """11 rule 16, checked across every path that reaches Committed."""
    for summary, scope in (("trivial change", Scope.TASK), ("operational change", Scope.PROJECT)):
        record = decisions.propose(token, _proposal(summary, scope=scope))
        decisions.commit(record.decision_id, committer_id=AGENT)
        assert record.decision.expected_outcome
        assert state_of(decisions, record) == DecisionState.COMMITTED


def test_a_decision_gateway_outage_stops_committing_before_it_stops_executing(
    decisions: DecisionGateway, token: str
) -> None:
    """11.27.1 — "no workflow fails solely due to Gateway unavailability, but
    non-trivial execution pauses". The system stops committing first.

    Panic is the sharpest form of that posture: new proposals halt, but a
    decision already committed and executing is not retroactively unmade
    unless it is reversible.
    """
    from core.exceptions import AgentOSError

    irreversible = decisions.propose(
        token, _proposal("an irreversible step", compensation=None, count=3, confidence=0.99)
    )
    request = decisions.approvals.for_decision(irreversible.decision_id)[0]
    decisions.respond(request.request_id, responder_id=HUMAN, response="approve")
    decisions.commit(irreversible.decision_id, committer_id=HUMAN)
    decisions.mark_executing(irreversible.decision_id)

    decisions.panic()
    # It was already executing and cannot be compensated, so it is deferred
    # rather than silently reversed.
    assert state_of(decisions, irreversible) == DecisionState.DEFERRED
    with pytest.raises(AgentOSError, match="Panic Protocol"):
        decisions.propose(token, _proposal("anything new"))


def test_decision_verification_is_what_gates_every_downstream_effect(decisions: DecisionGateway, token: str) -> None:
    """12 rule 2 / 17 rule 2 / 18 rule 2, from the caller's side.

    The Tool, Integration and Deployment Gateways at S6 and S11 each call
    `verify` before permitting an effect. This is that contract, exercised
    from where they will stand.
    """
    from core.exceptions import AgentOSError

    record = decisions.propose(token, _proposal("invoke an external tool"))

    # Before commitment there is nothing to authorize an effect.
    with pytest.raises(AgentOSError, match="not committed"):
        decisions.verify(record.decision_id, DecisionClass.A_TRIVIAL)

    decisions.commit(record.decision_id, committer_id=AGENT)
    verified = decisions.verify(record.decision_id, DecisionClass.A_TRIVIAL)
    assert verified.is_committed
    assert verified.decision.chosen_option.option_id == "act"
