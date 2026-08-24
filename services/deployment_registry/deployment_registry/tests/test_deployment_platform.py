"""Deployment Platform — specification tests under the CIR-001 block (21B §25).

21C §38.6 governs what a blocked module may be tested for: CIR-001-blocked
modules "maintain specification-level tests (schema and contract validation)
but cannot maintain full integration tests until construction unblocks."

So these tests do two things and nothing else:

1. verify the **specification** — the manifest schema, the D-class to E-class
   authority mapping, the promotion gates, the ordering constraints;
2. verify the **block itself** — that every construction verb raises, and that
   the block cannot decay quietly as the module is edited.

`18.2` is why the block is honoured rather than worked around: deployment is
"the last constitutional checkpoint before code becomes behavior", so a
platform built on a guessed answer to CIR-001 would place every other
guarantee in the system onto a substrate chosen by inference.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from core.exceptions import ValidationError
from deployment_gateway import PROMOTION_SEQUENCE, DeploymentGateway, unbacked_environments
from deployment_registry import (
    DEPLOYMENT_TRANSITIONS,
    ConstructionBlocked,
    DeploymentRegistry,
    DeploymentState,
    EClass,
    EnvironmentInvariants,
    EnvironmentManifest,
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
        "owner_id": "human-sovereign",
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
        "declared_at": datetime(2026, 8, 1, tzinfo=UTC),
    }
    defaults.update(overrides)
    return EnvironmentManifest(**defaults)


@pytest.fixture
def registry() -> DeploymentRegistry:
    return DeploymentRegistry()


@pytest.fixture
def gateway() -> DeploymentGateway:
    return DeploymentGateway()


# ------------------------------------------------------- The block itself


@pytest.mark.parametrize(
    "operation",
    ["register", "approve", "activate", "promote", "discover", "resolve", "decommission", "record_trust"],
)
def test_every_registry_construction_verb_raises(registry: DeploymentRegistry, operation: str) -> None:
    """Build Spec Section 24 — never silently converted to Done.

    Parametrized so the block cannot decay one method at a time: adding a verb
    without adding it here leaves it untested, and converting one to a no-op
    fails immediately.
    """
    with pytest.raises(ConstructionBlocked, match="not authorized"):
        getattr(registry, operation)()


@pytest.mark.parametrize(
    "operation",
    [
        "request_promotion",
        "authorize",
        "mediate_access",
        "verify_rollback_readiness",
        "rollback",
        "migrate",
        "terminate",
        "probe_health",
        "bootstrap",
        "deployment_status",
    ],
)
def test_every_gateway_construction_verb_raises(gateway: DeploymentGateway, operation: str) -> None:
    with pytest.raises(ConstructionBlocked, match="not authorized"):
        getattr(gateway, operation)()


def test_a_blocked_operation_raises_rather_than_no_ops(registry: DeploymentRegistry) -> None:
    """The distinction that matters most here.

    A no-op would let a caller believe an environment had been activated, and
    therefore believe a runtime instance was somewhere it is not.
    """
    with pytest.raises(ConstructionBlocked):
        registry.activate(manifest())


def test_the_blocker_is_quoted_not_merely_named(registry: DeploymentRegistry) -> None:
    """A caller sees why, not only that."""
    blocker = registry.blocker()
    assert "CIR-001" in blocker
    assert "G3 or G4" in blocker
    assert "unilateral interpretation" in blocker


def test_would_be_permitted_is_blocked_despite_sounding_like_a_query(
    gateway: DeploymentGateway,
) -> None:
    """A hypothetical answer that later proved wrong would be worse than none.

    Evaluating "would this be permitted" requires the policy the Governance
    ruling has not settled, and a caller who planned against a guess would be
    worse off than one who knew nothing.
    """
    with pytest.raises(ConstructionBlocked):
        gateway.would_be_permitted(manifest())


def test_health_reports_the_block_rather_than_raising(registry: DeploymentRegistry, gateway: DeploymentGateway) -> None:
    """A health surface that raised would make the blocked status unobservable."""
    for surface in (registry.health(), gateway.health()):
        assert surface["status"] == "specification-conformant, construction-blocked"
        assert surface["blocker"] == "CIR-001"
        assert surface["construction_authorized"] is False


def test_the_downstream_consequence_is_stated_not_papered_over() -> None:
    """18.6.2 — the Gateway is "the sole constitutional path between operational
    intent and environmental existence".

    While construction is blocked there is no such path, so every runtime
    instance in this system runs in no registered environment. Saying so is the
    honest position; returning a plausible-looking environment would not be.
    """
    assert unbacked_environments() == ()


# ------------------------------------------- Specification: manifest schema


def test_a_conformant_manifest_validates(registry: DeploymentRegistry) -> None:
    registry.validate(manifest())


def test_all_four_domain_invariants_are_required() -> None:
    """18.7.2 — an undeclared invariant cannot be enforced."""
    for missing in ("isolation", "sovereignty", "resilience", "auditability"):
        with pytest.raises(ValidationError, match=missing):
            validate_manifest(manifest(invariants=invariants(**{missing: "  "})))


def test_geographic_locality_and_data_residency_are_required() -> None:
    """18.8.2 — sovereignty cannot be verified without them."""
    with pytest.raises(ValidationError, match="geographic locality"):
        validate_manifest(manifest(geographic_locality=""))
    with pytest.raises(ValidationError, match="data residency"):
        validate_manifest(manifest(data_residency="  "))


def test_a_fault_domain_assignment_is_required() -> None:
    with pytest.raises(ValidationError, match="fault domain"):
        validate_manifest(manifest(fault_domain=""))


def test_a_recovery_time_objective_must_be_positive() -> None:
    with pytest.raises(ValidationError, match="recovery time objective"):
        validate_manifest(
            manifest(
                resilience=ResilienceProfile(
                    recovery_time_objective=timedelta(0), recovery_point_objective=timedelta(minutes=1)
                )
            )
        )


def test_an_environment_may_not_be_its_own_predecessor() -> None:
    """18.8.3 — lineage must advance."""
    with pytest.raises(ValidationError, match="own predecessor"):
        validate_manifest(manifest(predecessor_deployment_id="env-1"))


def test_the_manifest_is_frozen() -> None:
    """18.8.3 — core invariants are immutable once Active.

    A manifest editable afterwards would make that clause a promise rather than
    a property, so it is frozen from declaration.
    """
    declared = manifest()
    with pytest.raises(Exception):  # noqa: B017 - FrozenInstanceError
        declared.sovereignty_tier = SovereigntyTier.SHARED  # type: ignore[misc]


# --------------------------------------- Specification: classification


@pytest.mark.parametrize(
    ("tier", "authority"),
    [
        (RiskTier.D1_OBSERVATIONAL, EClass.E1),
        (RiskTier.D2_OPERATIONAL, EClass.E2),
        (RiskTier.D3_CRITICAL, EClass.E3),
        (RiskTier.D4_SOVEREIGN, EClass.E4),
    ],
)
def test_risk_tier_maps_to_authority_requirement(gateway: DeploymentGateway, tier: RiskTier, authority: EClass) -> None:
    """18.5.3, one-to-one."""
    assert tier.required_authority is authority
    assert gateway.required_authority_for(tier) is authority


def test_e4_is_human_only_and_e2_and_above_require_a_human() -> None:
    """18.5.3 with 18.35.2 — E4 cannot be delegated."""
    assert EClass.E4.is_human_only
    assert not EClass.E3.is_human_only
    assert EClass.E2.requires_human
    assert not EClass.E1.requires_human


def test_sovereign_infrastructure_may_not_sit_on_a_shared_substrate() -> None:
    """18.5.4 with 18.35.2.

    D4 hosts constitutional infrastructure — the Security and Governance
    Gateways themselves. A substrate shared across organizational boundaries
    would put the system's own identity anchors inside someone else's fault and
    governance domain.
    """
    with pytest.raises(ValidationError, match="may not sit on a sovereign_shared substrate"):
        validate_manifest(manifest(risk_tier=RiskTier.D4_SOVEREIGN, sovereignty_tier=SovereigntyTier.SHARED))
    validate_manifest(manifest(risk_tier=RiskTier.D4_SOVEREIGN, sovereignty_tier=SovereigntyTier.OWNED))


def test_critical_deployments_exclude_shared_substrates_too() -> None:
    with pytest.raises(ValidationError):
        validate_manifest(manifest(risk_tier=RiskTier.D3_CRITICAL, sovereignty_tier=SovereigntyTier.SHARED))


@pytest.mark.parametrize("tier", list(RiskTier))
def test_every_risk_tier_has_a_declared_class_policy(tier: RiskTier) -> None:
    policy = default_class_policies()[tier]
    assert policy.required_authority is tier.required_authority
    # 21B §25.9 — rollback readiness is required at every tier. There is no
    # class of deployment for which being unable to undo it is acceptable.
    assert policy.requires_rollback_readiness


def test_the_gates_tighten_with_risk_tier(gateway: DeploymentGateway) -> None:
    """18.9.2 — validation, compliance, resilience, authority."""
    assert gateway.gates_for(RiskTier.D1_OBSERVATIONAL) == ("validation_gate", "authority_gate")
    assert gateway.gates_for(RiskTier.D3_CRITICAL) == (
        "validation_gate",
        "compliance_gate",
        "resilience_gate",
        "authority_gate",
    )
    assert len(gateway.gates_for(RiskTier.D4_SOVEREIGN)) == 4


# ---------------------------------------- Specification: ordering properties


def test_promotion_advances_authority_and_a_non_advance_is_refused() -> None:
    """18.9.1 — promotion is "constitutional advancement"."""
    assert promotion_authority(RiskTier.D2_OPERATIONAL, RiskTier.D3_CRITICAL) is EClass.E3
    assert promotion_authority(RiskTier.D3_CRITICAL, RiskTier.D4_SOVEREIGN) is EClass.E4
    with pytest.raises(ValidationError, match="is not a promotion"):
        promotion_authority(RiskTier.D3_CRITICAL, RiskTier.D2_OPERATIONAL)
    with pytest.raises(ValidationError):
        promotion_authority(RiskTier.D2_OPERATIONAL, RiskTier.D2_OPERATIONAL)


def test_rollback_readiness_is_verified_before_authorization(gateway: DeploymentGateway) -> None:
    """21B §25.4 with 18.13 — confirmed prior to commitment.

    A rollback plan confirmed after a failed deployment is a rollback plan
    confirmed too late. The ordering is asserted against the declared sequence
    so it survives as a reviewable property while construction is blocked.
    """
    assert gateway.rollback_precedes_authorization()
    assert PROMOTION_SEQUENCE.index("rollback_readiness") < PROMOTION_SEQUENCE.index("journal_write")


def test_the_promotion_sequence_matches_the_architecture(gateway: DeploymentGateway) -> None:
    assert gateway.promotion_sequence() == (
        "registry_lookup",
        "environment_class_policy",
        "required_approval",
        "rollback_readiness",
        "authorization_decision",
        "journal_write",
    )


def test_policy_evaluation_precedes_the_authorization_decision() -> None:
    """18.12 — environment-class policy "cannot be satisfied retroactively"."""
    assert PROMOTION_SEQUENCE.index("environment_class_policy") < PROMOTION_SEQUENCE.index("authorization_decision")


# ------------------------------------------ Specification: lifecycle machine


def test_an_active_environment_cannot_return_to_declared() -> None:
    """18.8.3 — behavioural change requires a new environment with lineage,
    not a walk backwards through the lifecycle."""
    assert DeploymentState.DECLARED not in DEPLOYMENT_TRANSITIONS[DeploymentState.ACTIVE]
    assert DeploymentState.VALIDATED not in DEPLOYMENT_TRANSITIONS[DeploymentState.ACTIVE]


def test_decommissioned_is_terminal() -> None:
    assert DEPLOYMENT_TRANSITIONS[DeploymentState.DECOMMISSIONED] == set()


def test_approval_precedes_activation_in_the_machine() -> None:
    """No path from Declared or Validated straight to Active."""
    assert DeploymentState.ACTIVE not in DEPLOYMENT_TRANSITIONS[DeploymentState.DECLARED]
    assert DeploymentState.ACTIVE not in DEPLOYMENT_TRANSITIONS[DeploymentState.VALIDATED]
    assert DeploymentState.ACTIVE in DEPLOYMENT_TRANSITIONS[DeploymentState.APPROVED]


def test_a_quarantined_environment_does_not_resume_on_its_own() -> None:
    """It returns only through a state a human must move it out of."""
    assert DEPLOYMENT_TRANSITIONS[DeploymentState.QUARANTINED] == {
        DeploymentState.ACTIVE,
        DeploymentState.DECOMMISSIONED,
    }
