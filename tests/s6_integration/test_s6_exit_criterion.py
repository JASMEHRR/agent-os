"""Stage S6 exit criterion, demonstrated end to end.

Build Specification, Stage S6, Tests to Write — quoted:

    "A registered tool backed by an approved integration executes in its
    declared sandbox tier (None/Container/gVisor/Firecracker) under a
    committed decision, within its cost ceiling, with validated output and a
    working compensation path; Tool Gateway rejects invocation attempts that
    bypass the Registry; direct tool-to-tool invocation is rejected
    (prohibited edge #6)."

**One clause cannot be satisfied and this suite says so rather than faking
it.** "Backed by an approved integration" requires the Integration Platform,
which is CIR-001 construction-blocked. `UnbackedIntegrationSource` therefore
reports every abstraction unbacked, and the tests below prove the Gateway
*refuses* such a tool. A tool that reaches nothing external needs no
integration and exercises the rest of the clause in full.

The stage exit criterion is scoped to the unblocked modules per the Build
Specification, and this is where that scoping bites.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from cost_manager import BudgetScope, CostManager, ScopeKind
from decision_gateway import (
    CostManagerBudgetSource,
    DecisionGateway,
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
from security_gateway import (
    Capability,
    PrincipalType,
    RegistrationRequest,
    Role,
    SecurityGateway,
)
from security_gateway.enums import PrincipalStatus
from tool_executor import Sandbox, SecurityGatewaySecretAuthority, ToolExecutor
from tool_gateway import (
    CostManagerBudget,
    DecisionGatewayVerifier,
    InvocationOutcome,
    InvocationRefused,
    SandboxDeEscalation,
    SecurityGatewayToolAuthorizer,
    ToolGateway,
    UnbackedIntegrationSource,
)
from tool_registry import (
    Availability,
    Compensation,
    Contract,
    SandboxTier,
    SecurityGatewayRegistryAuthorizer,
    ToolEffect,
    ToolManifest,
    ToolRegistry,
    ToolState,
)

TENANT = "tenant-alpha"
HUMAN = "human-sovereign"
AGENT = "agent-worker"
VERIFIER = "hash-worker"

PERMISSIONS = {
    "tool.register",
    "tool.invoke.internal",
    "tool.invoke.external",
    "decision.propose",
    "memory.retrieve.tenant_scoped",
}


class Clock:
    def __init__(self) -> None:
        self.now = datetime(2026, 8, 1, 12, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.now

    def advance(self, delta: timedelta) -> None:
        self.now += delta


class InMemorySecretStore:
    def __init__(self) -> None:
        self._values: dict[str, str] = {}

    def read(self, reference: str) -> str:
        return self._values[reference]

    def write(self, reference: str, value: str) -> None:
        self._values[reference] = value


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def store() -> InMemorySecretStore:
    return InMemorySecretStore()


@pytest.fixture
def security(clock: Clock, store: InMemorySecretStore) -> SecurityGateway:
    gw = SecurityGateway(signing_key=b"s6-integration-key", secret_store=store, now=clock)
    gw.bootstrap_human_sovereign(HUMAN, "Sovereign", TENANT)
    for principal, ptype, autonomy in (
        (AGENT, PrincipalType.AGENT, 2),
        ("service-executor", PrincipalType.SERVICE, None),
    ):
        gw.register_identity(
            RegistrationRequest(
                principal_id=principal,
                principal_type=ptype,
                name=principal,
                version="1.0.0",
                tenant_id=TENANT,
                autonomy_level=autonomy,
                approved_by=HUMAN,
            )
        )
        gw.change_principal_status(principal, PrincipalStatus.ACTIVE, actor_id=HUMAN)
    gw.capabilities.define(Capability(name="worker", permits=frozenset(PERMISSIONS)))
    gw.capabilities.grant(AGENT, "worker")
    gw.roles.define(
        Role(name="worker", permissions=frozenset(PERMISSIONS), eligible_types=frozenset({PrincipalType.AGENT}))
    )
    gw.roles.assign("worker", AGENT, PrincipalType.AGENT, assigned_by=HUMAN)
    gw.recompute_permissions(AGENT)
    gw.credentials.issue(f"cred-{AGENT}", AGENT, PrincipalType.AGENT, VERIFIER)
    gw.secrets.register("api/token", "sk-not-a-real-secret", TENANT, HUMAN)
    return gw


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
def decisions(security: SecurityGateway, costs: CostManager, clock: Clock) -> DecisionGateway:
    memory = MemoryGateway(
        authorizer=SecurityGatewayMemoryAuthorizer(gateway=security),
        signals=SignalEmitter(source_identity="memory_gateway"),
        now=clock,
    )
    knowledge = KnowledgeGateway(
        authorizer=SecurityGatewayKnowledgeAuthorizer(gateway=security),
        memory=MemoryGatewayEvidenceSource(gateway=memory),
        signals=SignalEmitter(source_identity="knowledge_gateway"),
        now=clock,
    )
    return DecisionGateway(
        authorizer=SecurityGatewayDecisionAuthorizer(gateway=security),
        knowledge=KnowledgeGatewayEvidenceSource(gateway=knowledge),
        budget=CostManagerBudgetSource(manager=costs),
        signals=SignalEmitter(source_identity="decision_gateway"),
        now=clock,
    )


@pytest.fixture
def registry(security: SecurityGateway, clock: Clock) -> ToolRegistry:
    return ToolRegistry(
        authorizer=SecurityGatewayRegistryAuthorizer(gateway=security),
        signals=SignalEmitter(source_identity="tool_registry"),
        now=clock,
    )


@pytest.fixture
def gateway(
    registry: ToolRegistry,
    security: SecurityGateway,
    decisions: DecisionGateway,
    costs: CostManager,
    clock: Clock,
) -> ToolGateway:
    return ToolGateway(
        registry=registry,
        authorizer=SecurityGatewayToolAuthorizer(gateway=security),
        decisions=DecisionGatewayVerifier(gateway=decisions),
        budget=CostManagerBudget(manager=costs),
        integrations=UnbackedIntegrationSource(),
        signals=SignalEmitter(source_identity="tool_gateway"),
        now=clock,
    )


@pytest.fixture
def executor(security: SecurityGateway, clock: Clock) -> ToolExecutor:
    return ToolExecutor(
        secrets=SecurityGatewaySecretAuthority(gateway=security),
        signals=SignalEmitter(source_identity="tool_executor"),
        executor_identity="service-executor",
        now=clock,
    )


@pytest.fixture
def token(security: SecurityGateway) -> str:
    issued, _ = security.authenticate(AGENT, f"cred-{AGENT}", VERIFIER, PrincipalType.AGENT)
    return issued


def _manifest(
    tool_id: str = "tool-transform",
    capability: str = "internal.data.transform",
    tier: SandboxTier = SandboxTier.CONTAINER,
    effect: ToolEffect = ToolEffect.MUTATING,
    abstraction: str | None = None,
    secrets: tuple[str, ...] = (),
    cost: float = 0.10,
) -> ToolManifest:
    return ToolManifest(
        tool_id=tool_id,
        name=tool_id,
        version="1.0.0",
        capability=capability,
        effect=effect,
        sandbox_tier=tier,
        input_contract=Contract(fields={"payload": str}),
        output_contract=Contract(fields={"result": str}),
        owner_principal_id=AGENT,
        tenant_id=TENANT,
        cost_per_invocation=cost,
        timeout=timedelta(seconds=30),
        compensation=(
            Compensation(reference="comp-transform", idempotent=True, description="revert")
            if effect == ToolEffect.MUTATING
            else None
        ),
        integration_abstraction=abstraction,
        egress_allowlist=(),
        secret_refs=secrets,
    )


def _activate(registry: ToolRegistry, token: str, manifest: ToolManifest) -> str:
    registry.register(token, manifest)
    registry.transition(manifest.tool_id, ToolState.VALIDATED)
    registry.transition(manifest.tool_id, ToolState.ACTIVE)
    registry.report_health(manifest.tool_id, Availability.HEALTHY)
    return manifest.tool_id


def _committed_decision(decisions: DecisionGateway, token: str, summary: str = "invoke a tool") -> str:
    proposal = Proposal(
        proposal_id=f"prop-{summary[:8].replace(' ', '-')}",
        summary=summary,
        proposer_id=AGENT,
        proposer_authority=AuthorityLevel.AGENT_DELEGATED,
        tenant_id=TENANT,
        business_id=None,
        options=(
            Option("null", "do nothing", 0.0, 0.0, reversible=True, is_null=True),
            Option("act", "invoke", 0.005, 1.0, reversible=True, compensation_ref="comp-transform"),
            Option("alt", "alternative", 0.004, 0.4, reversible=True, compensation_ref="comp-alt"),
        ),
        evidence=(
            EvidenceRef(source="knowledge", reference_id="b1", confidence=0.95, statement="s1"),
            EvidenceRef(source="knowledge", reference_id="b2", confidence=0.95, statement="s2"),
        ),
        risk=RiskAssessment(
            financial=RiskClass.LOW,
            operational=RiskClass.LOW,
            reputational=RiskClass.LOW,
            legal=RiskClass.LOW,
            strategic=RiskClass.LOW,
        ),
        scope=Scope.TASK,
    )
    record = decisions.propose(token, proposal)
    assert record.state == DecisionState.APPROVED
    decisions.commit(record.decision_id, committer_id=AGENT)
    return record.decision_id


def _tool(sandbox: Sandbox, params: dict[str, Any]) -> dict[str, Any]:
    return {"result": f"transformed:{params['payload']}"}


def test_s6_exit_criterion(
    registry: ToolRegistry,
    gateway: ToolGateway,
    executor: ToolExecutor,
    decisions: DecisionGateway,
    token: str,
    clock: Clock,
) -> None:
    # A registered tool, in its declared sandbox tier, under a committed
    # decision, within its cost ceiling, with validated output.
    tool_id = _activate(registry, token, _manifest(secrets=("api/token",)))
    decision_id = _committed_decision(decisions, token)

    contract = gateway.authorize(
        token,
        tool_id=tool_id,
        decision_id=decision_id,
        parameters={"payload": "hello"},
        cost_ceiling=1.0,
        idempotency_key="idem-1",
    )
    # The contract is complete and recorded *before* dispatch.
    assert contract.sandbox_tier == SandboxTier.CONTAINER
    assert contract.decision_reference == decision_id
    assert contract.compensation_reference == "comp-transform"
    assert contract.idempotency_key == "idem-1"
    assert contract.attribution.consumer_id == AGENT

    captured: dict[str, str] = {}

    def tool_with_secret(sandbox: Sandbox, params: dict[str, Any]) -> dict[str, Any]:
        captured.update(sandbox.env)  # the secret is present inside the sandbox
        return {"result": f"transformed:{params['payload']}"}

    result = executor.run(contract, tool_with_secret, cost_meter=lambda: 0.10)
    assert result.outcome == InvocationOutcome.SUCCEEDED
    assert result.sandbox_destroyed
    assert captured["api/token"] == "sk-not-a-real-secret"

    record = gateway.complete(
        contract.invocation_id,
        result.outcome,
        result.output,
        result.actual_cost,
        result.started_at,
    )
    assert record.succeeded
    assert record.output_valid

    # A working compensation path.
    compensation = gateway.compensate(token, contract.invocation_id, decision_id)
    assert compensation.is_compensation
    assert compensation.attribution.upstream_invocation_id == contract.invocation_id

    # Sandboxes are destroyed on every path, and no secret survives.
    assert executor.health()["sandboxes"]["leaked"] == 0
    journal_text = str([executor.journal[i].payload for i in range(len(executor.journal))])
    assert "sk-not-a-real-secret" not in journal_text


def test_an_unregistered_tool_cannot_be_invoked(gateway: ToolGateway, token: str) -> None:
    """12 rule 1 — no invocation without prior registration."""
    from core.exceptions import NotFoundError

    with pytest.raises(NotFoundError):
        gateway.authorize(
            token,
            tool_id="never-registered",
            decision_id="dec-x",
            parameters={"payload": "x"},
            cost_ceiling=1.0,
            idempotency_key="idem",
        )


def test_a_registered_but_inactive_tool_cannot_be_invoked(
    registry: ToolRegistry, gateway: ToolGateway, decisions: DecisionGateway, token: str
) -> None:
    """Registration is not authorization: the Registry governs existence only."""
    registry.register(token, _manifest())
    decision_id = _committed_decision(decisions, token)
    with pytest.raises(InvocationRefused) as refusal:
        gateway.authorize(
            token,
            tool_id="tool-transform",
            decision_id=decision_id,
            parameters={"payload": "x"},
            cost_ceiling=1.0,
            idempotency_key="idem",
        )
    assert refusal.value.gate == "registration"


def test_invocation_without_a_committed_decision_is_refused(
    registry: ToolRegistry, gateway: ToolGateway, token: str
) -> None:
    """12 rule 2 — no execution without a valid decision record."""
    tool_id = _activate(registry, token, _manifest())
    with pytest.raises(InvocationRefused) as refusal:
        gateway.authorize(
            token,
            tool_id=tool_id,
            decision_id="dec-never-committed",
            parameters={"payload": "x"},
            cost_ceiling=1.0,
            idempotency_key="idem",
        )
    assert refusal.value.gate == "decision"


def test_a_tool_needing_an_integration_is_refused_while_cir_001_blocks(
    registry: ToolRegistry, gateway: ToolGateway, decisions: DecisionGateway, token: str
) -> None:
    """The clause of the S6 test list that cannot be satisfied, stated honestly.

    "Backed by an approved integration" needs the Integration Platform, which
    is CIR-001 construction-blocked. Nothing can legitimately back an
    abstraction yet, so a tool declaring one is refused — which is the correct
    behaviour, not a workaround.
    """
    tool_id = _activate(
        registry,
        token,
        _manifest(tool_id="tool-external", capability="external.api.call", abstraction="capability.email.send"),
    )
    decision_id = _committed_decision(decisions, token)
    with pytest.raises(InvocationRefused) as refusal:
        gateway.authorize(
            token,
            tool_id=tool_id,
            decision_id=decision_id,
            parameters={"payload": "x"},
            cost_ceiling=1.0,
            idempotency_key="idem",
        )
    assert refusal.value.gate == "integration"
    assert "not backed by an active, approved integration" in refusal.value.reason


def test_sandbox_de_escalation_is_refused(
    registry: ToolRegistry, gateway: ToolGateway, decisions: DecisionGateway, token: str
) -> None:
    """12 rule 4 — the Gateway escalates isolation but never lowers it."""
    tool_id = _activate(registry, token, _manifest(tier=SandboxTier.FIRECRACKER))
    decision_id = _committed_decision(decisions, token)
    with pytest.raises(SandboxDeEscalation):
        gateway.authorize(
            token,
            tool_id=tool_id,
            decision_id=decision_id,
            parameters={"payload": "x"},
            cost_ceiling=1.0,
            idempotency_key="idem",
            requested_tier=SandboxTier.CONTAINER,
        )


def test_composition_runs_at_the_highest_tier_any_member_requires(
    registry: ToolRegistry, gateway: ToolGateway, token: str
) -> None:
    """12.18.3 — a pipeline containing a Firecracker tool runs entirely in Firecracker."""
    _activate(registry, token, _manifest(tool_id="tool-a", tier=SandboxTier.CONTAINER))
    _activate(registry, token, _manifest(tool_id="tool-b", tier=SandboxTier.FIRECRACKER))
    _activate(registry, token, _manifest(tool_id="tool-c", tier=SandboxTier.GVISOR))
    assert gateway.compose_tier(("tool-a", "tool-b", "tool-c")) == SandboxTier.FIRECRACKER


def test_composed_output_is_never_anonymous_input(
    registry: ToolRegistry, gateway: ToolGateway, decisions: DecisionGateway, token: str
) -> None:
    """21B §19.4 — output carries provenance linking it to the producing invocation.

    12 rule 17 prohibits direct tool-to-tool invocation absolutely. Chaining
    happens through repeated Gateway mediation, and the second contract names
    the first, so the chain is traceable rather than laundered.
    """
    first_id = _activate(registry, token, _manifest(tool_id="tool-first"))
    second_id = _activate(registry, token, _manifest(tool_id="tool-second"))
    decision_id = _committed_decision(decisions, token)

    first = gateway.authorize(token, first_id, decision_id, {"payload": "a"}, 1.0, "idem-first")
    second = gateway.authorize(
        token,
        second_id,
        decision_id,
        {"payload": "b"},
        1.0,
        "idem-second",
        upstream_invocation_id=first.invocation_id,
    )
    assert second.attribution.upstream_invocation_id == first.invocation_id


def test_the_executor_evaluates_no_authority() -> None:
    """12.6.3 / 12.17.4 — it fulfils; it does not decide."""
    surface = {name for name in dir(ToolExecutor) if not name.startswith("_")}
    assert {"authorize", "approve", "verify", "override", "permit"}.isdisjoint(surface)


def test_output_failing_its_contract_is_never_returned(
    registry: ToolRegistry, gateway: ToolGateway, executor: ToolExecutor, decisions: DecisionGateway, token: str
) -> None:
    """12.25.4 — external return data is untrusted until validated."""
    tool_id = _activate(registry, token, _manifest())
    decision_id = _committed_decision(decisions, token)
    contract = gateway.authorize(token, tool_id, decision_id, {"payload": "x"}, 1.0, "idem")

    def bad_tool(sandbox: Sandbox, params: dict[str, Any]) -> dict[str, Any]:
        return {"wrong_field": 123}

    result = executor.run(contract, bad_tool, cost_meter=lambda: 0.10)
    record = gateway.complete(
        contract.invocation_id, result.outcome, result.output, result.actual_cost, result.started_at
    )
    assert record.outcome == InvocationOutcome.OUTPUT_REJECTED
    assert not record.output_valid


def test_a_cost_ceiling_breach_halts_mid_flight(
    registry: ToolRegistry, gateway: ToolGateway, executor: ToolExecutor, decisions: DecisionGateway, token: str
) -> None:
    """12.17.4 — the Executor halts and reports; it does not reinterpret."""
    tool_id = _activate(registry, token, _manifest())
    decision_id = _committed_decision(decisions, token)
    contract = gateway.authorize(token, tool_id, decision_id, {"payload": "x"}, 0.5, "idem")
    result = executor.run(contract, _tool, cost_meter=lambda: 5.0)
    assert result.outcome == InvocationOutcome.COST_CEILING_BREACHED
    assert result.sandbox_destroyed


def test_a_sandbox_is_destroyed_even_when_the_tool_explodes(
    registry: ToolRegistry, gateway: ToolGateway, executor: ToolExecutor, decisions: DecisionGateway, token: str
) -> None:
    """21B §19.15 guarantee 8 — sandboxes are destroyed on every path."""
    tool_id = _activate(registry, token, _manifest())
    decision_id = _committed_decision(decisions, token)
    contract = gateway.authorize(token, tool_id, decision_id, {"payload": "x"}, 1.0, "idem")

    def exploding(sandbox: Sandbox, params: dict[str, Any]) -> dict[str, Any]:
        raise RuntimeError("the tool crashed")

    result = executor.run(contract, exploding)
    assert result.outcome == InvocationOutcome.FAILED
    assert result.sandbox_destroyed
    assert executor.health()["sandboxes"]["leaked"] == 0


def test_a_sandbox_violation_suspends_the_tool_and_escalates(
    registry: ToolRegistry, gateway: ToolGateway, executor: ToolExecutor, decisions: DecisionGateway, token: str
) -> None:
    """21B §19.10 — a sandbox escape is Category 1, not an operational failure."""
    from tool_executor import EgressBlocked

    tool_id = _activate(registry, token, _manifest())
    decision_id = _committed_decision(decisions, token)
    contract = gateway.authorize(token, tool_id, decision_id, {"payload": "x"}, 1.0, "idem")

    def escaping(sandbox: Sandbox, params: dict[str, Any]) -> dict[str, Any]:
        sandbox.request_egress("evil.example.com")  # not in the allowlist
        raise AssertionError("egress should have been blocked")

    result = executor.run(contract, escaping)
    assert result.outcome == InvocationOutcome.SANDBOX_VIOLATION
    gateway.complete(contract.invocation_id, result.outcome, None, result.actual_cost, result.started_at, result.detail)
    assert registry.get(tool_id).state == ToolState.SUSPENDED
    assert len(gateway.escalations.unacknowledged()) == 1
    assert issubclass(EgressBlocked, Exception)


def test_idempotency_key_deduplicates_a_replayed_request(
    registry: ToolRegistry, gateway: ToolGateway, executor: ToolExecutor, decisions: DecisionGateway, token: str
) -> None:
    """12.17 — the idempotency key exists because delivery is at-least-once."""
    tool_id = _activate(registry, token, _manifest())
    decision_id = _committed_decision(decisions, token)
    first = gateway.authorize(token, tool_id, decision_id, {"payload": "x"}, 1.0, "idem-same")
    second = gateway.authorize(token, tool_id, decision_id, {"payload": "x"}, 1.0, "idem-same")

    calls: list[int] = []

    def counting(sandbox: Sandbox, params: dict[str, Any]) -> dict[str, Any]:
        calls.append(1)
        return {"result": "ok"}

    executor.run(first, counting, cost_meter=lambda: 0.1)
    executor.run(second, counting, cost_meter=lambda: 0.1)
    assert len(calls) == 1  # the replay did not execute twice


def test_repeated_failure_closes_a_tool_off_by_trust_before_the_breaker(
    registry: ToolRegistry, gateway: ToolGateway, executor: ToolExecutor, decisions: DecisionGateway, token: str
) -> None:
    """Two independent protections, and the earlier one wins.

    Trust decay (12.16) and the circuit breaker (21B §19.3) both respond to
    repeated failure. Trust bites first here: three failures out of three drop
    the score below the autonomous threshold, so the autonomy gate refuses
    before the breaker has seen its fifth failure. That ordering is defence in
    depth working as intended, and it is worth pinning down rather than
    assuming the breaker is the only guard.
    """
    tool_id = _activate(registry, token, _manifest())
    decision_id = _committed_decision(decisions, token)

    def failing(sandbox: Sandbox, params: dict[str, Any]) -> dict[str, Any]:
        raise RuntimeError("boom")

    refused_at: str | None = None
    for i in range(6):
        try:
            contract = gateway.authorize(token, tool_id, decision_id, {"payload": "x"}, 1.0, f"idem-{i}")
        except InvocationRefused as refusal:
            refused_at = refusal.gate
            break
        result = executor.run(contract, failing)
        gateway.complete(contract.invocation_id, result.outcome, None, 0.0, result.started_at)

    assert refused_at == "autonomy"
    assert not registry.get(tool_id).autonomously_invocable
    assert registry.get(tool_id).state == ToolState.ACTIVE  # still exists, just not autonomous


def test_the_circuit_breaker_trips_on_its_own_threshold(clock: Clock) -> None:
    """The breaker in isolation, where trust cannot pre-empt it (21B §19.3)."""
    from tool_gateway import CircuitBreaker

    breaker = CircuitBreaker(now=clock)
    for _ in range(4):
        breaker.record("tool-x", succeeded=False)
    assert not breaker.is_open("tool-x")
    breaker.record("tool-x", succeeded=False)
    assert breaker.is_open("tool-x")

    with pytest.raises(InvocationRefused) as refusal:
        breaker.check("tool-x")
    assert refusal.value.gate == "circuit_breaker"

    # After the cooldown one probe is admitted, and success closes it.
    clock.advance(timedelta(minutes=6))
    breaker.check("tool-x")
    breaker.record("tool-x", succeeded=True)
    assert not breaker.is_open("tool-x")


def test_input_failing_its_contract_is_rejected_before_the_sandbox(
    registry: ToolRegistry, gateway: ToolGateway, decisions: DecisionGateway, token: str
) -> None:
    """21B §19.9 — rejected before sandbox entry, so no resource is consumed."""
    tool_id = _activate(registry, token, _manifest())
    decision_id = _committed_decision(decisions, token)
    with pytest.raises(InvocationRefused) as refusal:
        gateway.authorize(token, tool_id, decision_id, {"wrong": "shape"}, 1.0, "idem")
    assert refusal.value.gate == "input_contract"


def test_every_invocation_traces_to_its_full_attribution_chain(
    registry: ToolRegistry, gateway: ToolGateway, decisions: DecisionGateway, token: str
) -> None:
    """21B §19.15 guarantee 7 — tool, consumer, decision, agent, budget."""
    tool_id = _activate(registry, token, _manifest())
    decision_id = _committed_decision(decisions, token)
    contract = gateway.authorize(token, tool_id, decision_id, {"payload": "x"}, 1.0, "idem")
    chain = contract.attribution
    assert chain.consumer_id == AGENT
    assert chain.decision_id == decision_id
    assert chain.agent_id == AGENT
    assert chain.budget_scope == f"tenant:{TENANT}"
    assert chain.tenant_id == TENANT
