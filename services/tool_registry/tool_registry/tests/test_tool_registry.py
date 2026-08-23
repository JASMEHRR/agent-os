"""Tool Registry — registration, trust, discovery, lifecycle (12.6.1, 21B §19)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from core.exceptions import NotFoundError
from kernel.lifecycle import InvalidTransitionError
from kernel.signals import SignalEmitter
from security_gateway import (
    Capability,
    PrincipalType,
    RegistrationRequest,
    Role,
    SecurityGateway,
)
from security_gateway.enums import PrincipalStatus
from tool_registry import (
    AUTONOMOUS_TRUST_THRESHOLD,
    Availability,
    Compensation,
    Contract,
    RegistrationRejected,
    SandboxTier,
    SecurityGatewayRegistryAuthorizer,
    ToolEffect,
    ToolManifest,
    ToolRegistry,
    ToolState,
)

TENANT = "tenant-alpha"
HUMAN = "human-sovereign"
OWNER = "service-tooling"
VERIFIER = "hash-tooling"


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
    gw = SecurityGateway(signing_key=b"tool-registry-key", secret_store=NullSecretStore(), now=clock)
    gw.bootstrap_human_sovereign(HUMAN, "Sovereign", TENANT)
    gw.register_identity(
        RegistrationRequest(
            principal_id=OWNER,
            principal_type=PrincipalType.SERVICE,
            name="Tooling",
            version="1.0.0",
            tenant_id=TENANT,
            approved_by=HUMAN,
        )
    )
    gw.change_principal_status(OWNER, PrincipalStatus.ACTIVE, actor_id=HUMAN)
    perms = {"tool.register"}
    gw.capabilities.define(Capability(name="tooling", permits=frozenset(perms)))
    gw.capabilities.grant(OWNER, "tooling")
    gw.roles.define(
        Role(name="tooling", permissions=frozenset(perms), eligible_types=frozenset({PrincipalType.SERVICE}))
    )
    gw.roles.assign("tooling", OWNER, PrincipalType.SERVICE, assigned_by=HUMAN)
    gw.recompute_permissions(OWNER)
    gw.credentials.issue(f"cred-{OWNER}", OWNER, PrincipalType.SERVICE, VERIFIER)
    return gw


@pytest.fixture
def registry(security: SecurityGateway, clock: Clock) -> ToolRegistry:
    return ToolRegistry(
        authorizer=SecurityGatewayRegistryAuthorizer(gateway=security),
        signals=SignalEmitter(source_identity="tool_registry"),
        now=clock,
    )


@pytest.fixture
def token(security: SecurityGateway) -> str:
    issued, _ = security.authenticate(OWNER, f"cred-{OWNER}", VERIFIER, PrincipalType.SERVICE)
    return issued


def manifest(
    tool_id: str = "tool-fetch",
    capability: str = "external.http.fetch",
    effect: ToolEffect = ToolEffect.OBSERVATIONAL,
    tier: SandboxTier = SandboxTier.CONTAINER,
    compensation: Compensation | None = None,
    egress: tuple[str, ...] = ("api.example.com",),
    secrets: tuple[str, ...] = (),
    predecessor: str | None = None,
    cost: float = 0.01,
    timeout: timedelta = timedelta(seconds=30),
) -> ToolManifest:
    return ToolManifest(
        tool_id=tool_id,
        name=tool_id,
        version="1.0.0",
        capability=capability,
        effect=effect,
        sandbox_tier=tier,
        input_contract=Contract(fields={"url": str}),
        output_contract=Contract(fields={"body": str}),
        owner_principal_id=OWNER,
        tenant_id=TENANT,
        cost_per_invocation=cost,
        timeout=timeout,
        compensation=compensation,
        egress_allowlist=egress,
        secret_refs=secrets,
        predecessor_tool_id=predecessor,
    )


def _active(registry: ToolRegistry, token: str, **kw) -> str:
    record = registry.register(token, manifest(**kw))
    registry.transition(record.tool_id, ToolState.VALIDATED)
    registry.transition(record.tool_id, ToolState.ACTIVE)
    registry.report_health(record.tool_id, Availability.HEALTHY)
    return record.tool_id


# --------------------------------------------------------------- registration


def test_a_valid_manifest_registers(registry: ToolRegistry, token: str) -> None:
    record = registry.register(token, manifest())
    assert record.state == ToolState.REGISTERED
    assert record.trust_score == 0.5  # seeded, unproven


def test_anonymous_registration_is_prohibited(registry: ToolRegistry, token: str) -> None:
    """12 rule 7."""
    bad = ToolManifest(
        tool_id="anon",
        name="anon",
        version="1.0.0",
        capability="external.http.fetch",
        effect=ToolEffect.OBSERVATIONAL,
        sandbox_tier=SandboxTier.CONTAINER,
        input_contract=Contract(fields={"url": str}),
        output_contract=Contract(fields={"body": str}),
        owner_principal_id="",
        tenant_id=TENANT,
        cost_per_invocation=0.01,
        timeout=timedelta(seconds=10),
    )
    with pytest.raises(RegistrationRejected, match="anonymous"):
        registry.register(token, bad)


def test_a_mutating_tool_needs_compensation(registry: ToolRegistry, token: str) -> None:
    """12 rule 9 — no mutating tool registered without compensation logic."""
    with pytest.raises(RegistrationRejected, match="compensation"):
        registry.register(token, manifest(effect=ToolEffect.MUTATING, compensation=None))


def test_compensation_must_be_idempotent(registry: ToolRegistry, token: str) -> None:
    with pytest.raises(RegistrationRejected, match="idempotent"):
        registry.register(
            token,
            manifest(
                effect=ToolEffect.MUTATING,
                compensation=Compensation(reference="comp", idempotent=False, description="undo"),
            ),
        )


def test_a_mutating_tool_with_idempotent_compensation_registers(registry: ToolRegistry, token: str) -> None:
    record = registry.register(
        token,
        manifest(
            tool_id="tool-write",
            effect=ToolEffect.MUTATING,
            compensation=Compensation(reference="comp-write", idempotent=True, description="delete"),
        ),
    )
    assert record.manifest.is_mutating


def test_egress_requires_a_sandbox(registry: ToolRegistry, token: str) -> None:
    """A tool that reaches the network cannot run unsandboxed."""
    with pytest.raises(RegistrationRejected, match="egress requires"):
        registry.register(token, manifest(tier=SandboxTier.NONE))


def test_secret_injection_requires_a_sandbox(registry: ToolRegistry, token: str) -> None:
    """12 rule 5 — injection needs an isolated environment."""
    with pytest.raises(RegistrationRejected, match="injection"):
        registry.register(token, manifest(tier=SandboxTier.NONE, egress=(), secrets=("api/key",)))


def test_a_flat_capability_is_rejected(registry: ToolRegistry, token: str) -> None:
    with pytest.raises(RegistrationRejected, match="hierarchical"):
        registry.register(token, manifest(capability="fetch"))


def test_duplicate_registration_is_rejected(registry: ToolRegistry, token: str) -> None:
    registry.register(token, manifest())
    with pytest.raises(RegistrationRejected, match="already registered"):
        registry.register(token, manifest())


def test_lineage_must_resolve(registry: ToolRegistry, token: str) -> None:
    with pytest.raises(RegistrationRejected, match="lineage"):
        registry.register(token, manifest(tool_id="v2", predecessor="does-not-exist"))


def test_lineage_chains_to_the_root(registry: ToolRegistry, token: str) -> None:
    registry.register(token, manifest(tool_id="v1"))
    registry.register(token, manifest(tool_id="v2", predecessor="v1"))
    assert registry.lineage("v2") == ["v2", "v1"]


# ------------------------------------------------------------------ discovery


def test_registration_is_not_authorization(registry: ToolRegistry, token: str) -> None:
    """12.6.1 — discoverability is not authorization; only Active is invocable."""
    registry.register(token, manifest())
    assert registry.discover(token) == []


def test_discovery_finds_active_tools(registry: ToolRegistry, token: str) -> None:
    _active(registry, token)
    assert len(registry.discover(token)) == 1


def test_discovery_matches_capability_hierarchically(registry: ToolRegistry, token: str) -> None:
    """12.11.1 — capability signatures are hierarchical."""
    _active(registry, token)
    assert registry.discover(token, capability="external.http")
    assert registry.discover(token, capability="external.http.fetch")
    assert registry.discover(token, capability="external.smtp") == []


def test_discovery_filters_by_cost_and_trust(registry: ToolRegistry, token: str) -> None:
    _active(registry, token, cost=0.5)
    assert registry.discover(token, max_cost=0.1) == []
    assert registry.discover(token, max_cost=1.0)
    assert registry.discover(token, min_trust=0.9) == []


def test_unavailable_tools_are_hidden_by_default(registry: ToolRegistry, token: str) -> None:
    tool_id = _active(registry, token)
    registry.report_health(tool_id, Availability.UNAVAILABLE)
    assert registry.discover(token) == []
    assert registry.discover(token, include_unhealthy=True)


def test_the_registry_never_dispatches() -> None:
    """12.6.1 — the Registry governs existence; it does not execute."""
    surface = {name for name in dir(ToolRegistry) if not name.startswith("_")}
    assert {"invoke", "execute", "dispatch", "run", "call"}.isdisjoint(surface)


# ---------------------------------------------------------------------- trust


def test_trust_rises_with_success(registry: ToolRegistry, token: str) -> None:
    tool_id = _active(registry, token)
    for _ in range(10):
        registry.record_outcome(tool_id, succeeded=True)
    assert registry.get(tool_id).trust_score == 1.0


def test_trust_falls_with_failure(registry: ToolRegistry, token: str) -> None:
    tool_id = _active(registry, token)
    for _ in range(10):
        registry.record_outcome(tool_id, succeeded=False)
    assert registry.get(tool_id).trust_score < AUTONOMOUS_TRUST_THRESHOLD


def test_a_low_trust_tool_is_not_autonomously_invocable(registry: ToolRegistry, token: str) -> None:
    """21B §19.9 — suspended from autonomous use; human invocation permitted."""
    tool_id = _active(registry, token)
    for _ in range(10):
        registry.record_outcome(tool_id, succeeded=False)
    record = registry.get(tool_id)
    assert record.is_invocable  # still Active
    assert not record.autonomously_invocable


def test_idle_trust_decays_after_sixty_days(registry: ToolRegistry, token: str, clock: Clock) -> None:
    """12.16 — preventing dormant high-trust tools from taking critical work."""
    tool_id = _active(registry, token)
    for _ in range(10):
        registry.record_outcome(tool_id, succeeded=True)
    before = registry.get(tool_id).trust_score
    clock.advance(timedelta(days=61))
    registry.decay_trust()
    assert registry.get(tool_id).trust_score < before


def test_recent_use_prevents_decay(registry: ToolRegistry, token: str, clock: Clock) -> None:
    tool_id = _active(registry, token)
    registry.record_outcome(tool_id, succeeded=True)
    before = registry.get(tool_id).trust_score
    clock.advance(timedelta(days=30))
    registry.decay_trust()
    assert registry.get(tool_id).trust_score == before


# ------------------------------------------------------------------ lifecycle


def test_lifecycle_guards_reject_illegal_transitions(registry: ToolRegistry, token: str) -> None:
    record = registry.register(token, manifest())
    with pytest.raises(InvalidTransitionError):
        registry.transition(record.tool_id, ToolState.ACTIVE)  # must pass Validated first


def test_deprecation_records_a_successor_and_deadline(registry: ToolRegistry, token: str) -> None:
    """12.29 — notice periods, successor identification, migration."""
    old = _active(registry, token, tool_id="v1")
    registry.register(token, manifest(tool_id="v2", predecessor="v1"))
    record = registry.deprecate(old, successor_tool_id="v2", notice=timedelta(days=30))
    assert record.state == ToolState.DEPRECATED
    assert record.successor_tool_id == "v2"
    assert record.migration_deadline is not None
    assert registry.discover(token) == []  # deprecated is not invocable


def test_suspension_records_its_reason(registry: ToolRegistry, token: str) -> None:
    tool_id = _active(registry, token)
    record = registry.transition(tool_id, ToolState.SUSPENDED, reason="sandbox violation")
    assert record.suspended_reason == "sandbox violation"


def test_unknown_tool_lookup_raises(registry: ToolRegistry) -> None:
    with pytest.raises(NotFoundError):
        registry.get("no-such-tool")


# --------------------------------------------------------------------- health


def test_health_of_reports_availability_and_trust(registry: ToolRegistry, token: str) -> None:
    tool_id = _active(registry, token)
    health = registry.health_of(tool_id)
    assert health["state"] == "active"
    assert health["availability"] == "healthy"
    assert health["autonomously_invocable"] is True


def test_registry_health_reports_the_trust_family(registry: ToolRegistry, token: str) -> None:
    _active(registry, token)
    health = registry.health()
    assert health["tools"] == 1
    assert "trust" in health and "availability" in health
    assert health["journal_intact"] is True


def test_security_gateway_is_imported_in_exactly_one_module() -> None:
    import pathlib

    import tool_registry

    root = pathlib.Path(tool_registry.__path__[0])
    importers = sorted(
        {
            path.name
            for path in root.glob("*.py")
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip().startswith(("import ", "from "))
            and "security_gateway" in line
            and path.name != "__init__.py"
        }
    )
    assert importers == ["security_adapter.py"]
