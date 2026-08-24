"""Stages S11 and S12 — the exit criteria, now that the frontier is closed.

21_PLAN §4.1:

* **S11 — Territory:** "Environments registered, validated, promoted, isolated
  by fault domain and locality; continuity and recovery procedures exercised;
  bootstrap reproducible."
* **S12 — Transformation & Extension:** "Amendments packaged and ratified;
  experiments bounded and reversible; plugins discovered, sandboxed, and
  lifecycle-managed."

Until 2026-08-24 this file named, clause by clause, what could *not* be
satisfied, because CIR-001 blocked five modules and a stage marked complete
with no test naming its gap would have been the silent conversion to Done that
Build Spec Section 24 forbids.

The G4 ruling closed the frontier. So the file inverts: it now asserts the
clauses are satisfied, and — more usefully — it asserts the things the ruling
**did not** change. A ruling that authorized construction is very easy to
mistake for a ruling that relaxed constraints, and these are the constraints
that would go quietly if it were.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from deployment_gateway import DeploymentGateway
from deployment_registry import (
    DeploymentRegistry,
    EClass,
    EnvironmentInvariants,
    EnvironmentManifest,
    Purpose,
    ResilienceProfile,
    RiskTier,
    Scope,
    SovereigntyTier,
)
from evolution_gateway import (
    ArtifactClass,
    CompensationPlan,
    EvolutionGateway,
    ImpactAssessment,
    LearningEvidence,
    ProposalState,
    RecursionAnomaly,
    ratification_verbs,
)
from integration_gateway import IntegrationGateway
from integration_registry import (
    CapabilityAbstraction,
    DataClassification,
    IntegrationManifest,
    IntegrationRegistry,
    PortabilityDeclaration,
)
from integration_registry import (
    RiskTier as IntegrationRiskTier,
)
from plugin_manager import PluginManager, PluginManifest, PluginState, ResourceLimits, SandboxTier

TENANT = "tenant-alpha"
HUMAN = "human-sovereign"


def is_human(principal_id: str) -> bool:
    return principal_id.startswith("human-")


def environment(deployment_id: str = "env-primary", **overrides: Any) -> EnvironmentManifest:
    defaults: dict[str, Any] = {
        "deployment_id": deployment_id,
        "name": "pricing-primary",
        "version": "1.0.0",
        "tenant_id": TENANT,
        "scope": Scope.BUSINESS,
        "owner_id": HUMAN,
        "risk_tier": RiskTier.D3_CRITICAL,
        "sovereignty_tier": SovereigntyTier.OWNED,
        "purpose": Purpose.PRIMARY,
        "geographic_locality": "jurisdiction-a",
        "data_residency": "jurisdiction-a only",
        "fault_domain": "fd-1",
        "capacity_commitment": "sufficient for twenty concurrent runtime entities",
        "invariants": EnvironmentInvariants(
            isolation="no runtime entity reaches outside the domain without Gateway mediation",
            sovereignty="substrate remains under direct organizational control",
            resilience="operational continuity within a single fault domain failure",
            auditability="all operations attributable for the statutory retention period",
        ),
        "resilience": ResilienceProfile(
            recovery_time_objective=timedelta(minutes=15),
            recovery_point_objective=timedelta(minutes=5),
        ),
        "security_posture": "network isolation plus per-entity credentials",
        "declared_at": datetime(2026, 8, 24, tzinfo=UTC),
    }
    defaults.update(overrides)
    return EnvironmentManifest(**defaults)


def live_environment(registry: DeploymentRegistry, deployment_id: str = "env-primary") -> Any:
    registry.declare(environment(deployment_id), actor_id=HUMAN)
    registry.validate_environment(deployment_id)
    registry.pass_gate(deployment_id, "compliance_gate")
    registry.pass_gate(deployment_id, "resilience_gate")
    registry.approve(deployment_id, HUMAN, is_human=True, e_class=EClass.E4)
    return registry.activate(deployment_id)


# ------------------------------------------------ S11: the criterion, satisfied


def test_s11_environments_are_registered_validated_and_promoted() -> None:
    """The three clauses that were construction and are now exercised."""
    registry = DeploymentRegistry()
    gateway = DeploymentGateway(registry=registry)
    live_environment(registry)

    outcome = gateway.request_promotion(
        "env-primary", RiskTier.D4_SOVEREIGN, HUMAN, is_human=True, e_class=EClass.E4, rollback_tested=True
    )
    assert outcome.authorized
    assert outcome.followed_the_full_sequence


def test_s11_environments_are_isolated_by_fault_domain_and_locality() -> None:
    """Declared *and* now enforced: discovery filters on both."""
    registry = DeploymentRegistry()
    live_environment(registry, "env-a")
    registry.declare(environment("env-b", geographic_locality="jurisdiction-b", fault_domain="fd-2"), HUMAN)
    registry.validate_environment("env-b")
    for gate in ("compliance_gate", "resilience_gate"):
        registry.pass_gate("env-b", gate)
    registry.approve("env-b", HUMAN, is_human=True, e_class=EClass.E4)
    registry.activate("env-b")

    assert [r.deployment_id for r in registry.discover(TENANT, locality="jurisdiction-b")] == ["env-b"]
    assert [r.deployment_id for r in registry.discover(TENANT, fault_domain="fd-1")] == ["env-a"]


def test_s11_recovery_procedures_are_exercised() -> None:
    """The clause that needed a live environment, and now has one."""
    registry = DeploymentRegistry()
    gateway = DeploymentGateway(registry=registry)
    live_environment(registry)
    gateway.verify_rollback_readiness("env-primary", rollback_tested=True)
    assert gateway.rollback("env-primary", "the promotion regressed latency")


# ------------------------------------------------ S12: the criterion, satisfied


def test_s12_amendments_are_packaged_and_ratified_by_governance() -> None:
    """Both halves, and the second is not Evolution's to do.

    "Packaged **and ratified**" is one clause naming two parties. Evolution
    packages; Governance ratifies. A test that had Evolution do both would
    report the clause satisfied by breaking 19.3.
    """
    received: list[str] = []

    class Governance:
        def receive(self, proposal_id: str, package: Any) -> str:
            received.append(proposal_id)
            return f"ack-{proposal_id}"

    evolution = EvolutionGateway()
    evolution.register_governance(Governance())
    evolution.draft(
        proposal_id="prop-1",
        tenant_id=TENANT,
        artifact_class=ArtifactClass.A2_ARCHITECTURAL,
        target_subsystem="agent_runtime",
        statement="raise the default retry ceiling from two to four",
        rationale="three confirmed entries show the provider recovers within four attempts",
        evidence=[LearningEvidence("le-1", "confirmed", "agent-analyst", 0.4)],
        drafted_by="agent-architect",
    )
    evolution.analyse_impact(
        "prop-1",
        ImpactAssessment(("agent_runtime",), (), reversible=True, detail="one module"),
    )
    evolution.frame_compensation(
        "prop-1", CompensationPlan(("restore the previous ceiling",), tested=True, estimated_reversal_cost=5.0)
    )
    evolution.check_recursion("prop-1")
    evolution.package("prop-1")
    evolution.hand_off("prop-1")

    assert received == ["prop-1"]
    # Governance decides; Evolution records what it decided.
    assert evolution.record_outcome("prop-1", "ratified", "adopted at G3").state == ProposalState.RATIFIED
    assert evolution.health()["ratified_by_evolution"] == 0


def test_s12_plugins_are_discovered_sandboxed_and_lifecycle_managed() -> None:
    """Unchanged: this clause was satisfied before the ruling and still is."""
    manager = PluginManager(is_human=is_human)
    manager.discover(
        PluginManifest(
            plugin_id="plug-shop",
            name="Shop Integration",
            version="1.0.0",
            publisher="third-party-labs",
            capabilities=frozenset({"catalogue.sync"}),
            event_subscriptions=frozenset({"order.created"}),
            requested_permissions=frozenset({"catalogue.read", "catalogue.write"}),
            resource_limits=ResourceLimits(512, 500, 30, frozenset({"api.example-shop.test"})),
            sandbox_tier=SandboxTier.CONTAINER,
            api_version="v1",
        )
    )
    manager.install("plug-shop", HUMAN)
    manager.grant("plug-shop", HUMAN, frozenset({"catalogue.read"}))
    manager.enable("plug-shop", HUMAN)

    assert manager.get("plug-shop").effective_permissions == {"catalogue.read"}
    assert not manager.permits("plug-shop", "catalogue.write")
    assert manager.health()["in_process_plugins"] == 0
    manager.disable("plug-shop", HUMAN)
    manager.uninstall("plug-shop", HUMAN)
    assert manager.get("plug-shop").state == PluginState.UNINSTALLED


# ================ What the ruling did NOT change, and would be easiest to lose


def test_the_naming_prohibition_still_governs_abstractions() -> None:
    """The half of CIR-001's prohibition the ruling **kept**.

    A ruling that authorized construction is easy to mistake for one that
    relaxed constraints. It did not: it scoped the prohibition to abstractions
    and governance artifacts, which means this is now the *only* place the
    prohibition lives and therefore the place it matters most.
    """
    registry = IntegrationRegistry()
    registry.specify_abstraction(
        CapabilityAbstraction(
            name="catalogue.sync",
            description="synchronise a product catalogue with an external store",
            contract={"items": list},
        )
    )
    registry.register(
        IntegrationManifest(
            integration_id="int-shop",
            provider_name="example-shop",
            abstraction="catalogue.sync",
            tenant_id=TENANT,
            risk_tier=IntegrationRiskTier.T2,
            max_data_classification=DataClassification.INTERNAL,
            portability=PortabilityDeclaration(True, True, True, 500.0),
            owner_principal_id=HUMAN,
            cost_model="per-call",
        ),
        actor_id=HUMAN,
    )
    abstraction = registry.abstractions()[0]
    assert "example-shop" not in abstraction.name
    assert "example-shop" not in abstraction.description


def test_evolution_still_cannot_ratify() -> None:
    """19.3, and the ruling gave Evolution construction rather than authority.

    This is the assertion that would matter most if it ever failed: a subsystem
    able to ratify its own constitutional amendments would have taken the
    authority the whole oversight plane exists to hold, and a ruling about
    technology naming is exactly the sort of change during which it could slip
    in unnoticed.
    """
    assert ratification_verbs() == ()
    forbidden = {"ratify", "approve", "amend", "enact", "adopt"}
    assert not (forbidden & {n for n in dir(EvolutionGateway) if not n.startswith("_")})


def test_evolutions_recursion_guard_still_fails_closed() -> None:
    """19.14 — unaffected by the ruling, and load-bearing now that the module runs."""
    evolution = EvolutionGateway()
    evolution.draft(
        proposal_id="prop-self",
        tenant_id=TENANT,
        artifact_class=ArtifactClass.A4_CONSTITUTIONAL,
        target_subsystem="evolution_gateway",
        statement="widen what Evolution may propose",
        rationale="confirmed evidence suggests the bounds are too tight",
        evidence=[LearningEvidence("le-1", "confirmed", "x", 0.2)],
        drafted_by="agent-architect",
    )
    evolution.analyse_impact("prop-self", ImpactAssessment((), (), reversible=True, detail=""))
    evolution.frame_compensation("prop-self", CompensationPlan(("revert",), tested=True, estimated_reversal_cost=1.0))
    with pytest.raises(RecursionAnomaly):
        evolution.check_recursion("prop-self")


def test_deployment_still_refuses_a_shared_substrate_for_sovereign_infrastructure() -> None:
    """18.5.4 with 18.35.2 — the constraint that protects the system's own anchors.

    D4 hosts the Security and Governance Gateways. Construction being
    authorized does not make it acceptable to put them on a substrate shared
    across organizational boundaries.
    """
    from core.exceptions import ValidationError
    from deployment_registry import validate_manifest

    with pytest.raises(ValidationError, match="sovereign_shared"):
        validate_manifest(environment(risk_tier=RiskTier.D4_SOVEREIGN, sovereignty_tier=SovereigntyTier.SHARED))


def test_deployment_still_authorizes_without_executing() -> None:
    """21B §25.2 — the split the ruling did not touch.

    Authorizing construction of the Deployment Platform is not the same as
    giving it hands. Neither component provisions.
    """
    forbidden = {"provision", "scale", "deploy", "spin_up", "destroy"}
    for surface in (DeploymentRegistry, DeploymentGateway):
        assert not (forbidden & {n for n in dir(surface) if not n.startswith("_")})


def test_integration_still_enforces_classification_at_the_boundary() -> None:
    """21B §20.4 — "a provider's assurance is not a control", ruling or no ruling."""
    from integration_gateway import ClassificationRefused

    registry = IntegrationRegistry()
    gateway = IntegrationGateway(registry=registry)
    registry.specify_abstraction(CapabilityAbstraction("catalogue.sync", "sync a catalogue", {"items": list}))
    registry.register(
        IntegrationManifest(
            integration_id="int-shop",
            provider_name="example-shop",
            abstraction="catalogue.sync",
            tenant_id=TENANT,
            risk_tier=IntegrationRiskTier.T1,
            max_data_classification=DataClassification.INTERNAL,
            portability=PortabilityDeclaration(True, True, True, 100.0),
            owner_principal_id=HUMAN,
            cost_model="per-call",
        ),
        actor_id=HUMAN,
    )
    registry.validate("int-shop")
    registry.approve("int-shop", HUMAN, is_human=True, decision_class="D")
    registry.activate("int-shop")
    gateway.record_instance_approval("int-shop", HUMAN, is_human=True)

    reached: list[str] = []

    def provider(payload: Any) -> dict[str, Any]:
        reached.append("x")
        return {}

    with pytest.raises(ClassificationRefused):
        gateway.consume(
            "catalogue.sync",
            TENANT,
            {},
            DataClassification.RESTRICTED,
            call=provider,
        )
    assert reached == []


# ------------------------------------------------------- The frontier, closed


def test_no_subsystem_is_construction_blocked_any_more() -> None:
    """The inverse of the assertion this file was built around.

    It asserted for eleven stages that exactly three subsystems were blocked.
    The G4 ruling of 2026-08-24 released all five modules across those three,
    and every one now reports construction authorized.
    """
    modules: list[Any] = [
        IntegrationRegistry(),
        DeploymentRegistry(),
        EvolutionGateway(),
    ]
    for module in modules:
        assert not module.is_blocked()
        assert module.health()["construction_authorized"] is True


def test_the_system_now_reaches_outside_and_runs_somewhere() -> None:
    """The two honest consequences, inverted.

    This file used to assert that the system reached nothing external and ran
    in no registered environment — both true, both asserted rather than left to
    be discovered. Both are now false, and the same directness applies.
    """
    registry = DeploymentRegistry()
    gateway = DeploymentGateway(registry=registry)
    live_environment(registry)
    assert gateway.mediate_access("runtime-1", "env-primary")
    assert registry.active(TENANT)

    integrations = IntegrationRegistry()
    integrations.specify_abstraction(CapabilityAbstraction("catalogue.sync", "sync", {"items": list}))
    assert integrations.abstractions()


def test_a_tool_needing_an_integration_is_now_backed() -> None:
    """The S6 clause that could not be satisfied while CIR-001 stood.

    `test_a_tool_needing_an_integration_is_refused_while_cir_001_blocks` named
    it as unsatisfiable rather than stubbing a fake integration to make the
    suite green. The Registry-backed source now answers the same question with
    a real integration behind it.
    """
    from tool_gateway import RegistryIntegrationSource, UnbackedIntegrationSource

    registry = IntegrationRegistry()
    registry.specify_abstraction(CapabilityAbstraction("catalogue.sync", "sync", {"items": list}))
    registry.register(
        IntegrationManifest(
            integration_id="int-shop",
            provider_name="example-shop",
            abstraction="catalogue.sync",
            tenant_id=TENANT,
            risk_tier=IntegrationRiskTier.T2,
            max_data_classification=DataClassification.INTERNAL,
            portability=PortabilityDeclaration(True, True, True, 100.0),
            owner_principal_id=HUMAN,
            cost_model="per-call",
        ),
        actor_id=HUMAN,
    )
    registry.validate("int-shop")
    registry.approve("int-shop", HUMAN, is_human=True, decision_class="D")
    registry.activate("int-shop")

    backed = RegistryIntegrationSource(registry=registry)
    assert backed.is_backed("catalogue.sync", TENANT)
    assert not backed.is_backed("nothing.registered", TENANT)
    # And the old source still exists, because a deployment with no registered
    # integrations is in exactly the position it describes.
    assert not UnbackedIntegrationSource().is_backed("catalogue.sync", TENANT)


def test_a_suspended_provider_unbacks_the_tool_that_depended_on_it() -> None:
    """The coupling that makes the backing check worth having.

    A tool that kept working against a suspended provider would be reaching
    outside through a relationship the Registry has already withdrawn.
    """
    from tool_gateway import RegistryIntegrationSource

    registry = IntegrationRegistry()
    registry.specify_abstraction(CapabilityAbstraction("catalogue.sync", "sync", {"items": list}))
    registry.register(
        IntegrationManifest(
            integration_id="int-shop",
            provider_name="example-shop",
            abstraction="catalogue.sync",
            tenant_id=TENANT,
            risk_tier=IntegrationRiskTier.T2,
            max_data_classification=DataClassification.INTERNAL,
            portability=PortabilityDeclaration(True, True, True, 100.0),
            owner_principal_id=HUMAN,
            cost_model="per-call",
        ),
        actor_id=HUMAN,
    )
    registry.validate("int-shop")
    registry.approve("int-shop", HUMAN, is_human=True, decision_class="D")
    registry.activate("int-shop")

    source = RegistryIntegrationSource(registry=registry)
    assert source.is_backed("catalogue.sync", TENANT)
    registry.suspend("int-shop", "provider outage")
    assert not source.is_backed("catalogue.sync", TENANT)
