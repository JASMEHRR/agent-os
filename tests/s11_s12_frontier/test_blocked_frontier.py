"""Stages S11 and S12 — the exit criteria, scoped to what is unblocked.

21_PLAN §4.1:

* **S11 — Territory:** "Environments registered, validated, promoted, isolated
  by fault domain and locality; continuity and recovery procedures exercised;
  bootstrap reproducible."
* **S12 — Transformation & Extension:** "Amendments packaged and ratified;
  experiments bounded and reversible; plugins discovered, sandboxed, and
  lifecycle-managed."

The Build Specification scopes both to "whatever is unblocked" (S11 exit
criteria; S12 validation criteria). This suite states precisely what that
scoping leaves, and refuses to manufacture the rest.

**What cannot be satisfied, and is said so by name:**

* S11's "environments registered, validated, promoted" — registration and
  promotion are construction, blocked by CIR-001. Validation *is* satisfied:
  the manifest schema is complete and enforced.
* S11's "continuity and recovery procedures exercised" and "bootstrap
  reproducible" — both require a live environment.
* S12's "amendments packaged and ratified" — packaging is construction, and
  ratification was never Evolution's to perform (19.3).
* S12's "experiments bounded and reversible" — running an experiment is
  construction.

**What is satisfied in full:** S12's "plugins discovered, sandboxed, and
lifecycle-managed", which is not blocked and is built for real.

This file exists because a stage marked complete with no test naming what it
could not do would be the silent conversion to Done that Build Spec Section 24
forbids.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from deployment_gateway import DeploymentGateway, unbacked_environments
from deployment_registry import (
    ConstructionBlocked as DeploymentBlocked,
)
from deployment_registry import (
    DeploymentRegistry,
    EnvironmentInvariants,
    EnvironmentManifest,
    Purpose,
    ResilienceProfile,
    RiskTier,
    Scope,
    SovereigntyTier,
)
from evolution_gateway import ConstructionBlocked as EvolutionBlocked
from evolution_gateway import EvolutionGateway
from integration_gateway import IntegrationGateway
from integration_registry import ConstructionBlocked as IntegrationBlocked
from integration_registry import IntegrationRegistry
from plugin_manager import PluginManager, PluginManifest, PluginState, ResourceLimits, SandboxTier

TENANT = "tenant-alpha"
HUMAN = "human-sovereign"


def is_human(principal_id: str) -> bool:
    return principal_id.startswith("human-")


def environment() -> EnvironmentManifest:
    return EnvironmentManifest(
        deployment_id="env-primary",
        name="pricing-primary",
        version="1.0.0",
        tenant_id=TENANT,
        scope=Scope.BUSINESS,
        owner_id=HUMAN,
        risk_tier=RiskTier.D3_CRITICAL,
        sovereignty_tier=SovereigntyTier.OWNED,
        purpose=Purpose.PRIMARY,
        geographic_locality="jurisdiction-a",
        data_residency="jurisdiction-a only",
        fault_domain="fd-1",
        capacity_commitment="sufficient for twenty concurrent runtime entities",
        invariants=EnvironmentInvariants(
            isolation="no runtime entity reaches outside the domain without Gateway mediation",
            sovereignty="substrate remains under direct organizational control",
            resilience="operational continuity within a single fault domain failure",
            auditability="all operations attributable for the statutory retention period",
        ),
        resilience=ResilienceProfile(
            recovery_time_objective=timedelta(minutes=15),
            recovery_point_objective=timedelta(minutes=5),
        ),
        security_posture="network isolation plus per-entity credentials",
        declared_at=datetime(2026, 8, 1, tzinfo=UTC),
    )


# ------------------------------------- S11: what is satisfied, and what is not


def test_s11_environment_validation_is_satisfied() -> None:
    """The one clause of S11's exit criterion that does not require construction.

    A manifest can be checked for conformance without anything coming into
    being, so the schema half of "registered, validated" is genuinely met.
    """
    DeploymentRegistry().validate(environment())


def test_s11_registration_and_promotion_cannot_be_satisfied() -> None:
    """Named as unsatisfiable rather than stubbed to make the suite green.

    18.6.1 makes the Registry "the sole authoritative source of truth for all
    operational environments"; registering one is bringing an environment into
    existence, which is construction.
    """
    registry = DeploymentRegistry()
    with pytest.raises(DeploymentBlocked):
        registry.register(environment())
    with pytest.raises(DeploymentBlocked):
        registry.promote("env-primary", RiskTier.D4_SOVEREIGN)


def test_s11_continuity_drills_and_bootstrap_cannot_be_exercised() -> None:
    """Both clauses require a live environment, and there is none."""
    gateway = DeploymentGateway()
    with pytest.raises(DeploymentBlocked):
        gateway.bootstrap()
    with pytest.raises(DeploymentBlocked):
        gateway.verify_rollback_readiness("env-primary")
    assert environment().resilience.continuity_drill_passed is False, (
        "no drill has been run, and the manifest says so rather than defaulting to passed"
    )


def test_s11_isolation_by_fault_domain_and_locality_is_declared_not_enforced() -> None:
    """The declaration is complete; the enforcement needs a substrate.

    A manifest that could not even express a fault domain would be a
    specification failure. One that expresses it but cannot enforce it is a
    construction gap, and the difference is worth keeping visible.
    """
    manifest = environment()
    assert manifest.fault_domain
    assert manifest.geographic_locality
    with pytest.raises(DeploymentBlocked):
        DeploymentGateway().mediate_access("env-primary", "agent-analyst")


# ------------------------------------- S12: what is satisfied, and what is not


def test_s12_amendment_packaging_cannot_be_satisfied() -> None:
    """And ratification was never Evolution's to perform (19.3)."""
    evolution = EvolutionGateway()
    with pytest.raises(EvolutionBlocked):
        evolution.package("proposal-1")
    with pytest.raises(EvolutionBlocked):
        evolution.hand_off("proposal-1")
    assert not hasattr(evolution, "ratify")


def test_s12_experiments_cannot_be_run() -> None:
    """19's bounded, reversible experiments require construction to run at all."""
    with pytest.raises(EvolutionBlocked):
        EvolutionGateway().run_experiment("exp-1")


def test_s12_plugins_are_discovered_sandboxed_and_lifecycle_managed() -> None:
    """The clause that **is** fully satisfied, exercised end to end.

    02.3.10 and 01.18.2 name no technology that CIR-001 puts in doubt for the
    manifest, permission and lifecycle model, so this half of S12 is built for
    real rather than specified.
    """
    manager = PluginManager(is_human=is_human)
    manifest = PluginManifest(
        plugin_id="plug-shop",
        name="Shop Integration",
        version="1.0.0",
        publisher="third-party-labs",
        capabilities=frozenset({"catalogue.sync"}),
        event_subscriptions=frozenset({"order.created"}),
        requested_permissions=frozenset({"catalogue.read", "catalogue.write"}),
        resource_limits=ResourceLimits(
            max_memory_mb=512,
            max_cpu_millicores=500,
            max_wall_seconds=30,
            egress_allowlist=frozenset({"api.example-shop.test"}),
        ),
        sandbox_tier=SandboxTier.CONTAINER,
        api_version="v1",
    )

    # Discovered.
    manager.discover(manifest)
    assert manager.get("plug-shop").state == PluginState.DISCOVERED

    # Lifecycle-managed, with a human at every gate.
    manager.install("plug-shop", HUMAN)
    manager.grant("plug-shop", HUMAN, frozenset({"catalogue.read"}))
    manager.enable("plug-shop", HUMAN)

    # Sandboxed: bounded resources, bounded egress, bounded permissions, and
    # never in core process space.
    record = manager.get("plug-shop")
    assert record.manifest.sandbox_tier is not None
    assert record.manifest.resource_limits.max_memory_mb > 0
    assert record.effective_permissions == {"catalogue.read"}
    assert not manager.permits("plug-shop", "catalogue.write")
    assert manager.health()["in_process_plugins"] == 0

    # Lifecycle continues through disable and uninstall.
    manager.disable("plug-shop", HUMAN, reason="vendor issued a patch")
    assert not manager.permits("plug-shop", "catalogue.read")
    manager.uninstall("plug-shop", HUMAN)
    assert manager.get("plug-shop").state == PluginState.UNINSTALLED


# ------------------------------------------- The blocked frontier, as a whole


def test_exactly_three_subsystems_are_construction_blocked() -> None:
    """21A §3 names Integration, Deployment and Evolution.

    Asserted together so the frontier is one checkable fact rather than three
    scattered ones. If a fourth subsystem ever becomes blocked, or one of these
    unblocks, this is the test that says so.
    """
    blocked: list[Any] = [
        IntegrationRegistry(),
        DeploymentRegistry(),
        IntegrationGateway(),
        DeploymentGateway(),
        EvolutionGateway(),
    ]
    for module in blocked:
        assert module.is_blocked()
        assert "CIR-001" in module.blocker()
        assert module.health()["construction_authorized"] is False

    # And the one S12 module that is not blocked.
    manager = PluginManager(is_human=is_human)
    assert not hasattr(manager, "is_blocked")
    assert "construction_authorized" not in manager.health()


@pytest.mark.parametrize(
    ("factory", "operation", "error"),
    [
        (IntegrationRegistry, "register", IntegrationBlocked),
        (IntegrationGateway, "consume", IntegrationBlocked),
        (DeploymentRegistry, "register", DeploymentBlocked),
        (DeploymentGateway, "authorize", DeploymentBlocked),
        (EvolutionGateway, "package", EvolutionBlocked),
    ],
)
def test_every_blocked_subsystem_raises_rather_than_no_ops(
    factory: Any, operation: str, error: type[Exception]
) -> None:
    """Build Spec Section 24, across all three blocked subsystems at once.

    The uniformity matters: three modules that each handled the block slightly
    differently would be three chances for one of them to drift into a quiet
    no-op.
    """
    with pytest.raises(error, match="not authorized"):
        getattr(factory(), operation)()


def test_the_system_knows_it_has_no_environment_and_no_external_reach() -> None:
    """The two honest consequences of the frontier, stated together.

    18.6.2 makes the Deployment Gateway the sole path to environmental
    existence, and 17 makes the Integration Gateway the sole path outside. With
    both blocked, everything built in S0 through S10 runs nowhere in particular
    and reaches nothing external. That is the true state of the system and it
    is better said plainly than discovered later.
    """
    assert unbacked_environments() == ()

    from tool_gateway import UnbackedIntegrationSource

    assert UnbackedIntegrationSource().is_backed("any.capability.abstraction", TENANT) is False


def test_the_blockers_all_name_the_same_governance_ruling() -> None:
    """One resolution unblocks all three, which is why it is one register entry."""
    blocked: list[Any] = [IntegrationRegistry(), DeploymentRegistry(), EvolutionGateway()]
    for module in blocked:
        blocker = module.blocker()
        assert "G3 or G4" in blocker
        assert "unilateral interpretation" in blocker
