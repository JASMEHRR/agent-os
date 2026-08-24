"""Stage S3 exit criterion, demonstrated end to end against a synthetic caller.

Build Specification, Stage S3, Validation Criteria — every signal type is
ingested, enriched and journaled; budget checks gate pre-flight and post-flight
operations at the four levels; circuit breakers trip on repeated external-call
failure.

This suite spans both S3 modules plus the kernel's Signal Emission mechanism,
so it lives at the repository root rather than inside either module — neither
one owns the interaction it exercises.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from core.constants import BudgetLevel
from cost_manager import BudgetScope, CostManager, ScopeKind
from kernel.signals import Sensitivity, SignalEmitter, SignalType
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
CALLER = "service-synthetic-caller"
CALLER_VERIFIER = "hash-synthetic"
AGENT_SCOPE = BudgetScope(kind=ScopeKind.AGENT, identifier="agent-writer")


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
    gw = SecurityGateway(signing_key=b"s3-integration-key", secret_store=NullSecretStore(), now=clock)
    gw.bootstrap_human_sovereign(HUMAN, "Sovereign", TENANT)
    gw.register_identity(
        RegistrationRequest(
            principal_id=CALLER,
            principal_type=PrincipalType.SERVICE,
            name="Synthetic Caller",
            version="1.0.0",
            tenant_id=TENANT,
            approved_by=HUMAN,
        )
    )
    gw.change_principal_status(CALLER, PrincipalStatus.ACTIVE, actor_id=HUMAN)
    permissions = {"observability.query.internal"}
    gw.capabilities.define(Capability(name="oversight", permits=frozenset(permissions)))
    gw.capabilities.grant(CALLER, "oversight")
    gw.roles.define(
        Role(
            name="oversight",
            permissions=frozenset(permissions),
            eligible_types=frozenset({PrincipalType.SERVICE}),
        )
    )
    gw.roles.assign("oversight", CALLER, PrincipalType.SERVICE, assigned_by=HUMAN)
    gw.recompute_permissions(CALLER)
    gw.credentials.issue(f"cred-{CALLER}", CALLER, PrincipalType.SERVICE, CALLER_VERIFIER)
    return gw


@pytest.fixture
def observability(security: SecurityGateway, clock: Clock) -> ObservabilityGateway:
    return ObservabilityGateway(authorizer=SecurityGatewayQueryAuthorizer(gateway=security), now=clock)


#: The human-escalation path. No Human Interface exists until Stage S8.
Escalations = list[tuple[str, dict[str, Any]]]


@pytest.fixture
def escalations() -> Escalations:
    return []


@pytest.fixture
def costs(observability: ObservabilityGateway, clock: Clock, escalations: Escalations) -> CostManager:
    # The Cost Manager emits through the kernel's out-of-band channel straight
    # into Observability's ingestion endpoint — the real S3 wiring.
    emitter = SignalEmitter(source_identity="cost_manager", sink=observability.sink_for("cost_manager"))
    return CostManager(
        signals=emitter,
        escalate=lambda kind, detail: escalations.append((kind, detail)),
        now=clock,
    )


def test_s3_exit_criterion(
    observability: ObservabilityGateway,
    costs: CostManager,
    security: SecurityGateway,
    escalations: Escalations,
    clock: Clock,
) -> None:
    caller_token, _ = security.authenticate(CALLER, f"cred-{CALLER}", CALLER_VERIFIER, PrincipalType.SERVICE)

    # 1. Every signal type is ingested, enriched, and journaled — emitted by a
    #    synthetic Gateway through the kernel's out-of-band channel.
    gateway_emitter = SignalEmitter(
        source_identity="synthetic_gateway", sink=observability.sink_for("synthetic_gateway")
    )
    gateway_emitter.emit(SignalType.METRIC, "operation.latency_ms", TENANT, value=12.0)
    gateway_emitter.emit(SignalType.EVENT, "operation.started", TENANT)
    gateway_emitter.emit(SignalType.JOURNAL, "decision.recorded", TENANT)
    gateway_emitter.emit(SignalType.TRACE, "operation.span", TENANT)

    ingested = observability.query(caller_token, TENANT, source_identity="synthetic_gateway")
    assert {s.signal.signal_type for s in ingested} == set(SignalType)
    assert all(s.scope == (f"tenant:{TENANT}",) for s in ingested)  # enriched
    assert observability.journal.verify_chain()  # journaled, tamper-evident

    # 2. Budget checks gate pre-flight and post-flight at all four levels, and
    #    every check lands in Observability as a signal.
    costs.allocate(AGENT_SCOPE, TENANT, limit=100.0)
    assert costs.check(AGENT_SCOPE, TENANT).level == BudgetLevel.GREEN

    costs.record(AGENT_SCOPE, TENANT, 55.0, "inference", "agent-writer")
    assert costs.check(AGENT_SCOPE, TENANT).level == BudgetLevel.YELLOW

    costs.record(AGENT_SCOPE, TENANT, 30.0, "inference", "agent-writer")
    orange = costs.check(AGENT_SCOPE, TENANT)
    assert orange.level == BudgetLevel.ORANGE
    assert orange.downgrade_required  # model downgrading enforced

    costs.record(AGENT_SCOPE, TENANT, 11.0, "inference", "agent-writer")
    red = costs.check(AGENT_SCOPE, TENANT)
    assert red.level == BudgetLevel.RED
    assert red.halted  # operations halted
    assert [kind for kind, _ in escalations].count("budget_red") == 1  # human escalation

    # 3. Circuit breakers trip on repeated external-call failure.
    for _ in range(5):
        costs.record(AGENT_SCOPE, TENANT, 0.0, "inference", "agent-writer", dependency="openai", succeeded=False)
    assert costs.breakers.breaker("openai").is_open
    assert any(kind == "circuit_breaker_tripped" for kind, _ in escalations)

    # The Cost Manager's own signals arrived at Observability, so the economics
    # of the whole run are visible to oversight rather than only to itself.
    cost_signals = observability.query(caller_token, TENANT, source_identity="cost_manager")
    emitted = {s.signal.name for s in cost_signals}
    assert "cost.budget.utilization" in emitted
    assert "cost.budget.threshold_breached" in emitted
    assert "cost.circuit_breaker.tripped" in emitted

    health = observability.health()
    # The profile reads "full-interpretive" since Stage S10 upgraded this
    # module. What S3 asserts is unchanged: ingestion works, and the S3 exit
    # criterion is about telemetry landing, not about interpreting it.
    assert health["profile"] == "full-interpretive"
    assert health["by_source"]["cost_manager"] > 0
    assert health["by_source"]["synthetic_gateway"] == 4
    assert health["anomalies"]["total"] == 0


def test_observability_failure_does_not_break_the_cost_path(clock: Clock, escalations: Escalations) -> None:
    """21B §24.9 / 16.4 — a subsystem stays operational when Observability is down."""

    def broken_sink(_signal: object) -> None:
        raise RuntimeError("observability is unavailable")

    emitter = SignalEmitter(source_identity="cost_manager", sink=broken_sink)
    costs = CostManager(signals=emitter, escalate=lambda kind, detail: escalations.append((kind, detail)), now=clock)
    costs.allocate(AGENT_SCOPE, TENANT, limit=100.0)
    costs.record(AGENT_SCOPE, TENANT, 96.0, "inference", "agent-writer")
    verdict = costs.check(AGENT_SCOPE, TENANT)

    # Budget enforcement is unaffected, and the Red escalation still fires.
    assert verdict.level == BudgetLevel.RED
    assert verdict.halted
    assert any(kind == "budget_red" for kind, _ in escalations)
    # The telemetry is buffered for a later drain, not lost.
    assert emitter.sink_failures > 0
    assert emitter.buffered > 0


def test_late_attached_observability_recovers_the_backlog(
    observability: ObservabilityGateway, security: SecurityGateway, clock: Clock, escalations: Escalations
) -> None:
    """S1 and S2 predate S3; their buffered telemetry must still arrive."""
    emitter = SignalEmitter(source_identity="cost_manager")
    costs = CostManager(signals=emitter, escalate=lambda kind, detail: escalations.append((kind, detail)), now=clock)
    costs.allocate(AGENT_SCOPE, TENANT, limit=100.0)
    costs.record(AGENT_SCOPE, TENANT, 10.0, "inference", "agent-writer")
    buffered = emitter.buffered
    assert buffered > 0

    drained = emitter.attach(observability.sink_for("cost_manager"))
    assert drained == buffered

    caller_token, _ = security.authenticate(CALLER, f"cred-{CALLER}", CALLER_VERIFIER, PrincipalType.SERVICE)
    assert len(observability.query(caller_token, TENANT, source_identity="cost_manager")) == drained


def test_cost_manager_never_reads_telemetry_back_from_observability() -> None:
    """The dependency is one-directional: Cost emits, Observability receives.

    A read path from Cost Manager back into Observability would make an
    operational subsystem depend on the observability path for correctness,
    which 21B §24.13 explicitly rules out.
    """
    import pathlib

    import cost_manager

    root = pathlib.Path(cost_manager.__path__[0])
    importers = [
        path.name
        for path in root.glob("*.py")
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip().startswith(("import ", "from ")) and "observability_gateway" in line
    ]
    assert importers == []


def test_signals_carry_their_sensitivity_through_to_query(
    observability: ObservabilityGateway, security: SecurityGateway
) -> None:
    """16.13 — the classification an emitter asserts governs who may read it."""
    from kernel.signals import Signal

    emitter = SignalEmitter(source_identity="security_gateway", sink=observability.sink_for("security_gateway"))
    emitter.submit(
        Signal(
            signal_type=SignalType.JOURNAL,
            name="authorization.denied",
            source_identity="security_gateway",
            tenant_id=TENANT,
            sensitivity=Sensitivity.RESTRICTED,
        )
    )
    caller_token, _ = security.authenticate(CALLER, f"cred-{CALLER}", CALLER_VERIFIER, PrincipalType.SERVICE)
    # The caller holds observability.query.internal, so a Restricted signal is
    # not returned even though it was ingested.
    assert observability.query(caller_token, TENANT) == []
    assert observability.ingest_engine.ingested_count == 1
