"""Deployment Platform conformance (18, per 21B §25).

**Construction authorized 2026-08-24** by G4 ruling on CIR-001. This suite
replaces the specification-only one that asserted every construction verb
raised. That suite was right for eleven stages; it is wrong now, so it was
replaced rather than left passing against a block that no longer exists.

`18.2` is why the block was worth honouring while it stood, and why the
ordering rules below are the ones tested hardest: deployment is "the last
constitutional checkpoint before code becomes behavior", so a gate that can be
satisfied after the fact is not a gate at all.

* environment-class policy "cannot be satisfied retroactively" (18.12);
* rollback readiness is confirmed **before** authorization (18.13, 21B §25.4);
* E4 is human-only and cannot be delegated (18.35.2);
* no runtime exists in an environment without Gateway mediation (18.6.2).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from core.exceptions import AgentOSError, NotFoundError, ValidationError
from deployment_gateway import (
    PROMOTION_SEQUENCE,
    DeploymentGateway,
    MediationRefused,
    RollbackNotReady,
)
from deployment_registry import (
    DEPLOYMENT_TRANSITIONS,
    AuthorityInsufficient,
    DeploymentRegistry,
    DeploymentState,
    EClass,
    EnvironmentInvariants,
    EnvironmentManifest,
    GateNotPassed,
    Purpose,
    ResilienceProfile,
    RiskTier,
    Scope,
    SovereigntyTier,
    default_class_policies,
    promotion_authority,
    validate_manifest,
)

TENANT = "tenant-alpha"
HUMAN = "human-sovereign"
AGENT = "agent-operator"


class Clock:
    def __init__(self) -> None:
        self.now = datetime(2026, 8, 24, 12, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        self.now += timedelta(milliseconds=5)
        return self.now


def invariants(**overrides: Any) -> EnvironmentInvariants:
    defaults: dict[str, Any] = {
        "isolation": "no runtime entity reaches outside the domain without Gateway mediation",
        "sovereignty": "substrate remains under direct organizational control",
        "resilience": "operational continuity within a single fault domain failure",
        "auditability": "all operations attributable for the statutory retention period",
    }
    defaults.update(overrides)
    return EnvironmentInvariants(**defaults)


def manifest(deployment_id: str = "env-1", **overrides: Any) -> EnvironmentManifest:
    defaults: dict[str, Any] = {
        "deployment_id": deployment_id,
        "name": "pricing-primary",
        "version": "1.0.0",
        "tenant_id": TENANT,
        "scope": Scope.BUSINESS,
        "owner_id": HUMAN,
        "risk_tier": RiskTier.D2_OPERATIONAL,
        "sovereignty_tier": SovereigntyTier.OWNED,
        "purpose": Purpose.PRIMARY,
        "geographic_locality": "jurisdiction-a",
        "data_residency": "jurisdiction-a only",
        "fault_domain": "fd-1",
        "capacity_commitment": "sufficient for twenty concurrent runtime entities",
        "invariants": invariants(),
        "resilience": ResilienceProfile(
            recovery_time_objective=timedelta(minutes=15),
            recovery_point_objective=timedelta(minutes=5),
        ),
        "security_posture": "network isolation plus per-entity credentials",
        "declared_at": datetime(2026, 8, 24, tzinfo=UTC),
    }
    defaults.update(overrides)
    return EnvironmentManifest(**defaults)


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def registry(clock: Clock) -> DeploymentRegistry:
    return DeploymentRegistry(now=clock)


@pytest.fixture
def gateway(registry: DeploymentRegistry, clock: Clock) -> DeploymentGateway:
    return DeploymentGateway(registry=registry, now=clock)


def activated(registry: DeploymentRegistry, deployment_id: str = "env-1", **overrides: Any) -> Any:
    registry.declare(manifest(deployment_id, **overrides), actor_id=HUMAN)
    registry.validate_environment(deployment_id)
    record = registry.get(deployment_id)
    for gate in ("compliance_gate", "resilience_gate"):
        if gate in registry._required_gates(record):  # noqa: SLF001 - the suite drives the real gates
            registry.pass_gate(deployment_id, gate)
    registry.approve(deployment_id, HUMAN, is_human=True, e_class=EClass.E4)
    return registry.activate(deployment_id)


# --------------------------------------------------------- The four gates


def test_declaration_validation_approval_and_activation_are_four_gates(
    registry: DeploymentRegistry,
) -> None:
    """18.9.2 — and none may be reached out of order."""
    registry.declare(manifest(), actor_id=HUMAN)
    assert registry.get("env-1").state == DeploymentState.DECLARED

    with pytest.raises(AgentOSError, match="expected one of"):
        registry.activate("env-1")

    registry.validate_environment("env-1")
    registry.pass_gate("env-1", "compliance_gate")
    registry.approve("env-1", HUMAN, is_human=True, e_class=EClass.E2)
    assert registry.activate("env-1").is_operational


def test_policy_cannot_be_satisfied_retroactively(registry: DeploymentRegistry) -> None:
    """18.12, and the reason the gates are recorded as they pass.

    A D3 environment must pass the compliance and resilience gates. Approving
    it with either outstanding is refused, and passing them afterwards would be
    exactly the retroactive satisfaction the clause forbids.
    """
    registry.declare(manifest(risk_tier=RiskTier.D3_CRITICAL), actor_id=HUMAN)
    registry.validate_environment("env-1")
    with pytest.raises(GateNotPassed, match="retroactively"):
        registry.approve("env-1", HUMAN, is_human=True, e_class=EClass.E4)

    registry.pass_gate("env-1", "compliance_gate")
    registry.pass_gate("env-1", "resilience_gate")
    assert registry.approve("env-1", HUMAN, is_human=True, e_class=EClass.E3).approved_by == HUMAN


def test_a_gate_the_tier_does_not_require_is_refused(registry: DeploymentRegistry) -> None:
    """Passing a gate that does not apply would put noise in the record."""
    registry.declare(manifest(risk_tier=RiskTier.D1_OBSERVATIONAL), actor_id=HUMAN)
    with pytest.raises(ValidationError, match="not a gate"):
        registry.pass_gate("env-1", "resilience_gate")


def test_the_gates_tighten_with_risk_tier(gateway: DeploymentGateway) -> None:
    assert gateway.gates_for(RiskTier.D1_OBSERVATIONAL) == ("validation_gate", "authority_gate")
    assert gateway.gates_for(RiskTier.D3_CRITICAL) == (
        "validation_gate",
        "compliance_gate",
        "resilience_gate",
        "authority_gate",
    )


# ---------------------------------------------------- Authority (18.5, 18.35)


@pytest.mark.parametrize(
    ("tier", "authority"),
    [
        (RiskTier.D1_OBSERVATIONAL, EClass.E1),
        (RiskTier.D2_OPERATIONAL, EClass.E2),
        (RiskTier.D3_CRITICAL, EClass.E3),
        (RiskTier.D4_SOVEREIGN, EClass.E4),
    ],
)
def test_risk_tier_maps_to_authority(tier: RiskTier, authority: EClass) -> None:
    assert tier.required_authority is authority


def test_e4_is_human_only_and_cannot_be_delegated(registry: DeploymentRegistry) -> None:
    """18.35.2 — cryptographically bound to human credentials.

    D4 hosts constitutional infrastructure: the Security and Governance
    Gateways themselves. A machine authorizing one would be a machine
    authorizing the substrate of its own oversight.
    """
    registry.declare(manifest(risk_tier=RiskTier.D4_SOVEREIGN), actor_id=HUMAN)
    registry.validate_environment("env-1")
    for gate in ("compliance_gate", "resilience_gate"):
        registry.pass_gate("env-1", gate)
    with pytest.raises(AuthorityInsufficient, match="cannot be delegated"):
        registry.approve("env-1", AGENT, is_human=False, e_class=EClass.E4)
    assert registry.approve("env-1", HUMAN, is_human=True, e_class=EClass.E4).approval_class is EClass.E4


def test_insufficient_authority_is_refused(registry: DeploymentRegistry) -> None:
    registry.declare(manifest(risk_tier=RiskTier.D3_CRITICAL), actor_id=HUMAN)
    registry.validate_environment("env-1")
    for gate in ("compliance_gate", "resilience_gate"):
        registry.pass_gate("env-1", gate)
    with pytest.raises(AuthorityInsufficient, match="requires E3"):
        registry.approve("env-1", HUMAN, is_human=True, e_class=EClass.E2)


def test_e1_does_not_require_a_human_and_e2_does(registry: DeploymentRegistry) -> None:
    """18.5.3 — the line between steward approval and human decision."""
    registry.declare(manifest("env-obs", risk_tier=RiskTier.D1_OBSERVATIONAL), actor_id=HUMAN)
    registry.validate_environment("env-obs")
    assert registry.approve("env-obs", AGENT, is_human=False, e_class=EClass.E1)

    registry.declare(manifest("env-ops", risk_tier=RiskTier.D2_OPERATIONAL), actor_id=HUMAN)
    registry.validate_environment("env-ops")
    registry.pass_gate("env-ops", "compliance_gate")
    with pytest.raises(AuthorityInsufficient, match="human-approved"):
        registry.approve("env-ops", AGENT, is_human=False, e_class=EClass.E2)


# ---------------------------------------------- Manifest and sovereignty


def test_sovereign_infrastructure_may_not_sit_on_a_shared_substrate() -> None:
    """18.5.4 with 18.35.2 — unchanged by the CIR-001 ruling."""
    with pytest.raises(ValidationError, match="may not sit on a sovereign_shared substrate"):
        validate_manifest(manifest(risk_tier=RiskTier.D4_SOVEREIGN, sovereignty_tier=SovereigntyTier.SHARED))


def test_all_four_domain_invariants_are_required() -> None:
    for missing in ("isolation", "sovereignty", "resilience", "auditability"):
        with pytest.raises(ValidationError, match=missing):
            validate_manifest(manifest(invariants=invariants(**{missing: "  "})))


def test_lineage_must_resolve(registry: DeploymentRegistry) -> None:
    """18.8.3 — behavioural change is a new environment with lineage."""
    with pytest.raises(NotFoundError, match="lineage must resolve"):
        registry.declare(manifest("env-2", predecessor_deployment_id="env-ghost"), actor_id=HUMAN)


def test_anonymous_declaration_is_prohibited(registry: DeploymentRegistry) -> None:
    with pytest.raises(ValidationError, match="anonymous declaration"):
        registry.declare(manifest(), actor_id="")


# ------------------------------------------------------ Promotion (18.9)


def test_promotion_produces_a_new_environment_with_lineage(
    registry: DeploymentRegistry, gateway: DeploymentGateway
) -> None:
    """18.8.3 — an Active environment's invariants are immutable.

    Promoting in place would edit the sovereignty tier, locality and scope that
    18.8.3 freezes, so promotion produces a successor and records the lineage.
    """
    activated(registry)
    outcome = gateway.request_promotion(
        "env-1", RiskTier.D3_CRITICAL, HUMAN, is_human=True, e_class=EClass.E3, rollback_tested=True
    )
    assert outcome.authorized
    successor = registry.get(outcome.successor_id or "")
    assert successor.manifest.predecessor_deployment_id == "env-1"
    assert successor.manifest.risk_tier is RiskTier.D3_CRITICAL
    assert registry.get("env-1").manifest.risk_tier is RiskTier.D2_OPERATIONAL, "the original is unchanged"


def test_promotion_follows_the_full_sequence(registry: DeploymentRegistry, gateway: DeploymentGateway) -> None:
    """21B §25.4, and the outcome carries the path it actually took."""
    activated(registry)
    outcome = gateway.request_promotion(
        "env-1", RiskTier.D3_CRITICAL, HUMAN, is_human=True, e_class=EClass.E3, rollback_tested=True
    )
    assert outcome.stages_completed == PROMOTION_SEQUENCE
    assert outcome.followed_the_full_sequence


def test_rollback_readiness_is_verified_before_authorization(
    registry: DeploymentRegistry, gateway: DeploymentGateway
) -> None:
    """18.13 with 21B §25.4 — after a failure is too late.

    The refusal stops at `rollback_readiness`, which is before
    `authorization_decision`. The stage list is the evidence: nothing was
    authorized, because the sequence never reached the stage that authorizes.
    """
    activated(registry)
    outcome = gateway.request_promotion(
        "env-1", RiskTier.D3_CRITICAL, HUMAN, is_human=True, e_class=EClass.E3, rollback_tested=False
    )
    assert not outcome.authorized
    assert "rollback_readiness" not in outcome.stages_completed
    assert "authorization_decision" not in outcome.stages_completed
    assert gateway.rollback_precedes_authorization()


def test_a_promotion_refusal_names_the_stage_that_stopped_it(
    registry: DeploymentRegistry, gateway: DeploymentGateway
) -> None:
    outcome = gateway.request_promotion(
        "env-ghost", RiskTier.D3_CRITICAL, HUMAN, is_human=True, e_class=EClass.E3, rollback_tested=True
    )
    assert not outcome.authorized
    assert outcome.stages_completed == ()
    assert "not declared" in outcome.detail


def test_promotion_advances_authority_and_a_non_advance_is_refused() -> None:
    assert promotion_authority(RiskTier.D2_OPERATIONAL, RiskTier.D3_CRITICAL) is EClass.E3
    with pytest.raises(ValidationError, match="is not a promotion"):
        promotion_authority(RiskTier.D3_CRITICAL, RiskTier.D2_OPERATIONAL)


# ------------------------------------------------------- Mediation (18.6.2)


def test_no_runtime_exists_in_an_environment_without_mediation(
    registry: DeploymentRegistry, gateway: DeploymentGateway
) -> None:
    """18.6.2 — the Gateway is the sole path between intent and existence."""
    activated(registry)
    grant = gateway.mediate_access("runtime-1", "env-1")
    assert grant == "grant:runtime-1@env-1"
    assert gateway.mediated_runtimes() == {"runtime-1": "env-1"}


def test_a_quarantined_environment_accepts_no_runtime(registry: DeploymentRegistry, gateway: DeploymentGateway) -> None:
    activated(registry)
    registry.quarantine("env-1", "sovereignty breach")
    with pytest.raises(MediationRefused, match="no runtime may be placed"):
        gateway.mediate_access("runtime-1", "env-1")


def test_migration_is_a_fresh_mediation_not_a_carried_grant(
    registry: DeploymentRegistry, gateway: DeploymentGateway
) -> None:
    """18.7.4 — crossing a boundary needs re-authorization.

    Carrying the old grant across would let a runtime enter a quarantined
    environment on the strength of one it has left.
    """
    activated(registry, "env-1")
    activated(registry, "env-2")
    gateway.mediate_access("runtime-1", "env-1")
    registry.quarantine("env-2", "under investigation")
    with pytest.raises(MediationRefused):
        gateway.migrate("runtime-1", "env-2", is_human=True)


def test_termination_drops_every_grant_into_the_terminated_environment(
    registry: DeploymentRegistry, gateway: DeploymentGateway
) -> None:
    """A grant that outlived its environment would let a runtime believe it was
    somewhere that no longer exists."""
    activated(registry)
    gateway.mediate_access("runtime-1", "env-1")
    gateway.mediate_access("runtime-2", "env-1")
    gateway.terminate("env-1", "sovereignty breach", is_human=True)
    assert gateway.mediated_runtimes() == {}


def test_termination_is_an_e4_human_act(registry: DeploymentRegistry, gateway: DeploymentGateway) -> None:
    """18.35.2, 18.35.3."""
    activated(registry)
    with pytest.raises(AuthorityInsufficient, match="cannot be delegated"):
        gateway.terminate("env-1", "unsafe", is_human=False)


# ----------------------------------------------------- Discovery and trust


def test_discovery_returns_environments_by_property_not_by_name(
    registry: DeploymentRegistry, gateway: DeploymentGateway
) -> None:
    """18.8.4 — a runtime asks for what it needs, as a tool asks for a capability."""
    activated(registry, "env-a", geographic_locality="jurisdiction-a")
    activated(registry, "env-b", geographic_locality="jurisdiction-b")
    found = registry.discover(TENANT, locality="jurisdiction-b")
    assert [r.deployment_id for r in found] == ["env-b"]


def test_discovery_never_crosses_the_tenant_boundary(registry: DeploymentRegistry) -> None:
    activated(registry)
    assert registry.discover("tenant-beta") == []


def test_repeated_incidents_quarantine_an_environment(registry: DeploymentRegistry) -> None:
    """An environment stops being resolvable when it stops being trustworthy."""
    activated(registry)
    for _ in range(4):
        registry.record_observation("env-1", incident=True)
    record = registry.get("env-1")
    assert record.state == DeploymentState.QUARANTINED
    assert registry.discover(TENANT) == []


def test_a_healthy_environment_keeps_full_trust(registry: DeploymentRegistry) -> None:
    activated(registry)
    for _ in range(6):
        registry.record_observation("env-1", incident=False)
    assert registry.get("env-1").trust == 1.0


# -------------------------------------------------------------- Rollback


def test_rollback_without_verified_readiness_is_refused(
    registry: DeploymentRegistry, gateway: DeploymentGateway
) -> None:
    """18.13 — a rollback attempted without prior confirmation is a hope."""
    activated(registry)
    with pytest.raises(RollbackNotReady, match="no procedure to run"):
        gateway.rollback("env-1", "deployment failed")


def test_rollback_runs_once_readiness_was_verified(registry: DeploymentRegistry, gateway: DeploymentGateway) -> None:
    activated(registry)
    gateway.verify_rollback_readiness("env-1", rollback_tested=True)
    assert gateway.rollback("env-1", "deployment failed").state == DeploymentState.QUARANTINED


# ------------------------------------------------ Structure and the ruling


def test_neither_component_executes_infrastructure() -> None:
    """21B §25.2 — authorization and execution are separate parties.

    A Gateway that provisioned would be both the authority and the actor, which
    is the separation 12.6 spends a section establishing for tools and 18.6.1
    states outright: the Registry "does not execute deployments".
    """
    forbidden = {"provision", "scale", "deploy", "spin_up", "destroy", "apply_terraform"}
    for surface in (DeploymentRegistry, DeploymentGateway):
        present = {name for name in dir(surface) if not name.startswith("_")}
        assert not (forbidden & present), f"{surface.__name__} acquired an execution verb: {forbidden & present}"


def test_construction_is_authorized_and_both_modules_say_so(
    registry: DeploymentRegistry, gateway: DeploymentGateway
) -> None:
    for surface in (registry.health(), gateway.health()):
        assert surface["construction_authorized"] is True
        assert "resolved" in surface["cir_001"]
    assert not registry.is_blocked()
    assert not gateway.is_blocked()


def test_an_active_environment_cannot_walk_backwards() -> None:
    """18.8.3 — a new environment with lineage, not a reversal."""
    assert DeploymentState.DECLARED not in DEPLOYMENT_TRANSITIONS[DeploymentState.ACTIVE]
    assert DEPLOYMENT_TRANSITIONS[DeploymentState.DECOMMISSIONED] == set()


def test_panic_quarantines_every_active_environment(registry: DeploymentRegistry, gateway: DeploymentGateway) -> None:
    activated(registry, "env-1")
    activated(registry, "env-2")
    gateway.mediate_access("runtime-1", "env-1")
    assert gateway.halt() == 2
    assert registry.active() == []
    assert gateway.mediated_runtimes() == {}


def test_the_journal_records_the_lifecycle(registry: DeploymentRegistry) -> None:
    activated(registry)
    payloads = [registry.journal[i].payload for i in range(len(registry.journal))]
    actions = [str(p["action"]) for p in payloads]
    assert actions[0] == "declared"
    assert "approved" in actions and "activated" in actions
    assert registry.health()["journal_intact"]


@pytest.mark.parametrize("tier", list(RiskTier))
def test_every_risk_tier_requires_rollback_readiness(tier: RiskTier) -> None:
    """There is no class of deployment for which being unable to undo it is acceptable."""
    assert default_class_policies()[tier].requires_rollback_readiness
