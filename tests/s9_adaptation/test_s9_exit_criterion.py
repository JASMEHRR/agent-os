"""Stage S9 — Adaptation. The exit criterion, exercised end to end.

21_PLAN §4.1, S9, verbatim:

    "Outcomes are attributed, patterns abstracted, proposals validated,
    consolidated, propagated to target Gateways, adopted, and measured to
    confirmation or refutation."

The trust path is real: observers authenticate through the Security Gateway
and cycles are budget-checked through the Cost Manager. The target of the
proposal is a real Agent Runtime, and the adoption is a real change to it —
which is what makes "propagated to target Gateways, adopted" mean something
rather than being a bookkeeping transition.

The adversarial Recursion Guard suite that 21C §38.5 requires lives in
`services/learning_gateway/learning_gateway/tests/test_recursion_guard.py`;
one integration-level check that the guard is wired into the real Gateway is
included here.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from agent_runtime import (
    AgentManifest,
    AgentRuntime,
    AgentState,
    AuthorityBoundaries,
    SecurityGatewayRuntimeAuthorizer,
)
from cost_manager import BudgetScope, CostManager, ScopeKind
from human_interface import HumanInterface, OverrideScope
from kernel.authority import AuthorityLevel
from kernel.signals import SignalEmitter
from learning_gateway import (
    Attribution,
    CostManagerLearningBudget,
    EvidenceRef,
    Hypothesis,
    LearningGateway,
    LearningState,
    Observation,
    Pattern,
    PatternKind,
    RecursionAnomaly,
    SecurityGatewayLearningAuthorizer,
    TargetClass,
    window_for,
)
from security_gateway import Capability, PrincipalType, RegistrationRequest, Role, SecurityGateway
from security_gateway.enums import PrincipalStatus

TENANT = "tenant-alpha"
HUMAN = "human-sovereign"
ADMIN = "human-admin"
OBSERVER = "agent-observer"
SUBJECT = "agent-analyst"
VERIFIER = "hash-analyst"

PERMISSIONS = {"learning.observe", "learning.propose"}


class Clock:
    def __init__(self) -> None:
        self.now = datetime(2026, 8, 1, 12, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.now

    def advance(self, delta: timedelta) -> None:
        self.now += delta


class SecretStore:
    def __init__(self) -> None:
        self._values: dict[str, str] = {}

    def read(self, reference: str) -> str:
        return self._values[reference]

    def write(self, reference: str, value: str) -> None:
        self._values[reference] = value


class RuntimeProposalSink:
    """The Agent Runtime's proposal intake.

    Deliberately does **not** apply anything on receipt. 13.16.1 makes
    propagation a handoff: the target evaluates through its own governance and
    reports back. This sink records what it was handed and nothing more, which
    is what a real target Gateway's intake would do.
    """

    def __init__(self, runtime: AgentRuntime) -> None:
        self.runtime = runtime
        self.received: list[tuple[str, dict[str, Any]]] = []
        self.adopted: list[str] = []

    def receive(self, entry_id: str, target_subsystem: str, proposal: Any) -> str:
        self.received.append((entry_id, dict(proposal)))
        return f"ack-{entry_id}"

    def evaluate_and_adopt(self, entry_id: str, token: str) -> bool:
        """The target's own governance, run separately and afterwards.

        A real Agent Runtime would weigh the proposal against its manifest
        rules. Here it accepts a causal, non-provisional proposal and suspends
        the subject agent as the adopted change, so adoption is observable in
        the target's real state rather than only in Learning's bookkeeping.
        """
        body = next(b for eid, b in self.received if eid == entry_id)
        if not body["is_causal_claim"] or body["provisional"]:
            return False
        self.runtime.command(token, SUBJECT, AgentState.SUSPENDED, reason=f"adopted {entry_id}")
        self.adopted.append(entry_id)
        return True


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def security(clock: Clock) -> SecurityGateway:
    gw = SecurityGateway(signing_key=b"s9-adaptation", secret_store=SecretStore(), now=clock)
    gw.bootstrap_human_sovereign(HUMAN, "Sovereign", TENANT)
    for principal, ptype in (
        (ADMIN, PrincipalType.HUMAN),
        (OBSERVER, PrincipalType.AGENT),
        (SUBJECT, PrincipalType.AGENT),
    ):
        gw.register_identity(
            RegistrationRequest(
                principal_id=principal,
                principal_type=ptype,
                name=principal,
                version="1.0.0",
                tenant_id=TENANT,
                autonomy_level=2 if ptype == PrincipalType.AGENT else None,
                approved_by=HUMAN,
            )
        )
        gw.change_principal_status(principal, PrincipalStatus.ACTIVE, actor_id=HUMAN)

    gw.capabilities.define(Capability(name="observer", permits=frozenset(PERMISSIONS)))
    gw.capabilities.grant(OBSERVER, "observer")
    gw.roles.define(
        Role(name="observer", permissions=frozenset(PERMISSIONS), eligible_types=frozenset({PrincipalType.AGENT}))
    )
    gw.roles.assign("observer", OBSERVER, PrincipalType.AGENT, assigned_by=HUMAN)
    gw.recompute_permissions(OBSERVER)

    for principal, ptype in (
        (HUMAN, PrincipalType.HUMAN),
        (OBSERVER, PrincipalType.AGENT),
        (SUBJECT, PrincipalType.AGENT),
    ):
        gw.credentials.issue(f"cred-{principal}", principal, ptype, VERIFIER)
    return gw


@pytest.fixture
def observer_token(security: SecurityGateway) -> str:
    token, _ = security.authenticate(OBSERVER, f"cred-{OBSERVER}", VERIFIER, PrincipalType.AGENT)
    return str(token)


@pytest.fixture
def subject_token(security: SecurityGateway) -> str:
    token, _ = security.authenticate(SUBJECT, f"cred-{SUBJECT}", VERIFIER, PrincipalType.AGENT)
    return str(token)


@pytest.fixture
def human_token(security: SecurityGateway) -> str:
    token, _ = security.authenticate(HUMAN, f"cred-{HUMAN}", VERIFIER, PrincipalType.HUMAN)
    return str(token)


@pytest.fixture
def costs(clock: Clock) -> CostManager:
    manager = CostManager(
        signals=SignalEmitter(source_identity="cost_manager"),
        escalate=lambda kind, detail: None,
        now=clock,
    )
    manager.allocate(BudgetScope(kind=ScopeKind.TENANT, identifier=TENANT), TENANT, limit=1000.0)
    return manager


@pytest.fixture
def runtime(security: SecurityGateway, clock: Clock, subject_token: str) -> AgentRuntime:
    class NoMemory:
        def hydrate(self, token: str, tenant_id: str, scope: frozenset[str]) -> list[dict[str, Any]]:
            return []

    class NoInference:
        def infer(
            self, template: str, slots: dict[str, str], tenant_id: str, principal_id: str, max_cost: float
        ) -> tuple[dict[str, Any], float, bool]:
            return ({"summary": "unused"}, 0.0, True)

    class NoTools:
        def invoke(
            self,
            token: str,
            tool_id: str,
            decision_id: str,
            parameters: dict[str, Any],
            cost_ceiling: float,
            idempotency_key: str,
        ) -> tuple[bool, dict[str, Any] | None, float]:
            return (True, {}, 0.0)

    rt = AgentRuntime(
        authorizer=SecurityGatewayRuntimeAuthorizer(gateway=security),
        memory=NoMemory(),
        inference=NoInference(),
        tools=NoTools(),
        signals=SignalEmitter(source_identity="agent_runtime"),
        now=clock,
    )
    rt.register(
        subject_token,
        AgentManifest(
            agent_id=SUBJECT,
            name=SUBJECT,
            version="1.0.0",
            tenant_id=TENANT,
            specialty="market analysis",
            boundaries=AuthorityBoundaries(
                capabilities=frozenset({"analysis"}),
                tool_inventory=frozenset(),
                memory_scope=frozenset({"tenant"}),
                autonomy_level=AuthorityLevel.AGENT_DELEGATED,
                cost_budget=1.0,
                workspace_ids=frozenset({"ws-1"}),
            ),
            prompt_template="analyse {context}",
            output_contract={"summary": str},
            max_context_tokens=1000,
            max_context_assembly_time=timedelta(seconds=5),
            activity_timeout=timedelta(minutes=5),
        ),
    )
    rt.command(subject_token, SUBJECT, AgentState.IDLE)
    return rt


@pytest.fixture
def sink(runtime: AgentRuntime) -> RuntimeProposalSink:
    return RuntimeProposalSink(runtime)


@pytest.fixture
def alerts() -> list[str]:
    return []


@pytest.fixture
def learning(
    security: SecurityGateway,
    costs: CostManager,
    sink: RuntimeProposalSink,
    clock: Clock,
    alerts: list[str],
) -> LearningGateway:
    gateway = LearningGateway(
        authorizer=SecurityGatewayLearningAuthorizer(gateway=security),
        budget=CostManagerLearningBudget(manager=costs),
        signals=SignalEmitter(source_identity="learning_gateway"),
        alert_human=alerts.append,
        now=clock,
    )
    gateway.register_target("agent_runtime", sink)
    return gateway


def failure_evidence(count: int = 3) -> tuple[EvidenceRef, ...]:
    return tuple(
        EvidenceRef(
            reference=f"dec-{n}",
            kind="decision_journal",
            observed_at=datetime(2026, 7, 20 + n, tzinfo=UTC),
            confidence=0.92,
        )
        for n in range(count)
    )


def observed_failure(observation_id: str = "obs-1") -> Observation:
    return Observation(
        observation_id=observation_id,
        tenant_id=TENANT,
        observer_id=OBSERVER,
        target_class=TargetClass.AGENT,
        subject_id=SUBJECT,
        summary="the analyst exhausted its retries three times against one provider",
        evidence=failure_evidence(),
        observed_at=datetime(2026, 8, 1, tzinfo=UTC),
    )


def failure_hypothesis(entry_id: str = "le-1") -> Hypothesis:
    return Hypothesis(
        entry_id=entry_id,
        tenant_id=TENANT,
        observer_id=OBSERVER,
        target_class=TargetClass.AGENT,
        target_subsystem="agent_runtime",
        subject_id=SUBJECT,
        proposal="raise the retry ceiling for the pricing analyst from two to four",
        expected_outcome="activity failure rate against this provider falls below five percent",
        pattern=Pattern(
            pattern_id="pat-1",
            kind=PatternKind.FAILURE,
            target_class=TargetClass.AGENT,
            scope=f"{TENANT}/pricing",
            instances=("obs-1", "obs-2"),
            description="retries exhaust before the provider recovers",
            root_cause="the retry ceiling is below the provider's observed recovery time",
        ),
        evidence=failure_evidence(),
        attribution=Attribution(
            causal_proximity=0.9,
            confounding_controlled=True,
            temporal_order_holds=True,
            replications=4,
            null_hypothesis="the provider recovered on its own regardless of the retry ceiling",
        ),
        scope=f"{TENANT}/pricing",
        formed_at=datetime(2026, 8, 1, tzinfo=UTC),
    )


# ----------------------------------------------------------- the exit criterion


def test_an_outcome_travels_the_whole_loop_to_confirmation(
    learning: LearningGateway,
    sink: RuntimeProposalSink,
    runtime: AgentRuntime,
    observer_token: str,
    subject_token: str,
) -> None:
    """13.18.1's loop, end to end, against real subsystems.

    Observe -> Propose -> Adopt -> Measure -> Confirm, with attribution,
    abstraction, validation, consolidation and propagation each doing real
    work rather than being asserted.
    """
    # Observe: an authenticated agent submits an outcome, budget-checked.
    learning.observe(observer_token, observed_failure())

    # Propose: pattern abstracted, hypothesis formed, validated.
    entry = learning.hypothesize(observer_token, failure_hypothesis())
    validated = learning.validate(entry.entry_id)
    assert validated.state == LearningState.VALIDATED
    assert validated.confidence >= 0.8
    assert not validated.provisional

    # Consolidate, then hand off. Handoff, not adoption.
    package = learning.consolidate("pkg-1", TENANT, "agent_runtime")
    assert package.entry_ids == ("le-1",)
    assert learning.propagate("pkg-1") == ["le-1"]
    assert learning.get("le-1").state == LearningState.PROPAGATED
    assert runtime.get(SUBJECT).state == AgentState.IDLE, "propagation changed nothing in the target"

    # Adopt: the target's own governance decides, and its state really moves.
    assert sink.evaluate_and_adopt("le-1", subject_token)
    assert runtime.get(SUBJECT).state == AgentState.SUSPENDED
    learning.report_adoption("le-1", adopted=True, justification="within the manifest's bounds")
    assert learning.get("le-1").state == LearningState.ADOPTED

    # Measure to confirmation.
    minimum, _maximum = window_for(TargetClass.AGENT)
    for _ in range(minimum):
        measured = learning.record_measurement("le-1", improved=True)
    assert measured.state == LearningState.CONFIRMED
    assert measured.actual_improvement == 1.0

    # The whole loop is reconstructible from the journal.
    actions = [str(p.get("action")) for p in learning.query_journal("le-1")]
    assert actions == ["hypothesized", "validated", "consolidated", "propagated", "adopted", "confirmed"]
    assert learning.health()["journal_intact"]


def test_a_refuted_adoption_produces_a_reversal_proposal(
    learning: LearningGateway, sink: RuntimeProposalSink, observer_token: str, subject_token: str
) -> None:
    """13.18.4 — the other terminal branch, and the more important one.

    A learning subsystem that could only confirm would be a subsystem that
    accumulated harm silently.
    """
    learning.observe(observer_token, observed_failure())
    learning.hypothesize(observer_token, failure_hypothesis())
    learning.validate("le-1")
    learning.consolidate("pkg-1", TENANT, "agent_runtime")
    learning.propagate("pkg-1")
    sink.evaluate_and_adopt("le-1", subject_token)
    learning.report_adoption("le-1", adopted=True)

    for _ in range(window_for(TargetClass.AGENT)[0]):
        measured = learning.record_measurement("le-1", improved=False)

    assert measured.state == LearningState.REFUTED
    assert sink.received[-1][1]["reversal"] is True
    assert learning.health()["quality"]["attribution_error_rate"] == 1.0


def test_the_target_may_reject_and_the_evidence_survives(learning: LearningGateway, observer_token: str) -> None:
    """13.16.1 — the target "retains full constitutional authority to reject"."""
    learning.observe(observer_token, observed_failure())
    learning.hypothesize(observer_token, failure_hypothesis())
    learning.validate("le-1")
    learning.consolidate("pkg-1", TENANT, "agent_runtime")
    learning.propagate("pkg-1")

    entry = learning.report_adoption("le-1", adopted=False, justification="the ceiling is contractually fixed")
    assert entry.state == LearningState.ABANDONED
    assert len(entry.hypothesis.evidence) == 3
    assert entry.hypothesis.attribution.replications == 4


def test_the_recursion_guard_is_wired_into_the_real_gateway(learning: LearningGateway, observer_token: str) -> None:
    """The adversarial suite proves the guard; this proves it is installed.

    21C §38.5's tests exercise `RecursionGuard` directly. A guard that worked
    perfectly and was never called would pass every one of them.
    """
    with pytest.raises(RecursionAnomaly):
        learning.observe(
            observer_token,
            Observation(
                observation_id="obs-recursive",
                tenant_id=TENANT,
                observer_id=OBSERVER,
                target_class=TargetClass.LEARNING,
                subject_id="learning_gateway",
                summary="our own validation rules rejected too much last month",
                evidence=failure_evidence(),
                observed_at=datetime(2026, 8, 1, tzinfo=UTC),
            ),
        )
    assert learning.guard.suspended
    assert learning.health()["health"]["recursion"]["anomalies_blocked"] == 1


def test_an_unauthenticated_observer_cannot_form_learning(learning: LearningGateway) -> None:
    """13 rule 7 — no anonymous formation, checked against the real Trust Plane."""
    with pytest.raises(Exception):  # noqa: B017 - the Security Gateway's own error
        learning.observe("forged-token", observed_failure())


def test_a_human_override_of_a_learning_proposal_is_recorded(
    learning: LearningGateway, observer_token: str, security: SecurityGateway, clock: Clock
) -> None:
    """13.33.2 — humans may block a proposal's propagation, logged as Class D."""

    def is_human(principal_id: str) -> bool:
        if not security.registry.exists(principal_id):
            return False
        return security.registry.get(principal_id).principal_type == PrincipalType.HUMAN

    human = HumanInterface(is_human=is_human, signals=SignalEmitter(source_identity="human_interface"), now=clock)
    learning.observe(observer_token, observed_failure())
    learning.hypothesize(observer_token, failure_hypothesis())
    learning.validate("le-1")

    override = human.override(
        "ov-1",
        TENANT,
        OverrideScope.LEARNING_PROPOSAL,
        "le-1",
        "block propagation pending review",
        "the provider contract changed last week and the evidence predates it",
        HUMAN,
    )
    assert override.decision_class == "D"
    assert human.overrides.latest_for("le-1") is override


def test_learning_cycles_are_charged_against_the_real_budget(
    learning: LearningGateway, costs: CostManager, observer_token: str
) -> None:
    """13 rule 11 — the check runs against the Cost Manager, not a stub."""
    learning.observe(observer_token, observed_failure())
    assert learning.health()["economic"]["cycles"] == 1

    costs.allocate(BudgetScope(kind=ScopeKind.TENANT, identifier="tenant-broke"), "tenant-broke", limit=0.0)
    assert not CostManagerLearningBudget(manager=costs).has_headroom("tenant-broke", 1.0)
