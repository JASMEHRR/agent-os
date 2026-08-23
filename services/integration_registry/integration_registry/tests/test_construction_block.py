"""Integration Platform — specification-conformant, construction-blocked.

Build Specification Part V holds CIR-001-blocked modules "to specification-level
tests (schema/contract validation) only, until construction unblocks", and
Section 6 forbids marking them Done.

This suite is exactly that: it exercises the schema and the two boundary rules
that are checkable against a specification, and it asserts that **every**
construction verb raises. The second half matters as much as the first — Build
Spec Section 24 requires construction-blocked debt to be tracked explicitly and
"never silently converted to Done status", and a block that decayed into a
no-op would be precisely that silent conversion.
"""

from __future__ import annotations

import pytest

from core.exceptions import ValidationError
from integration_gateway import (
    ApprovalRequired,
    ClassificationRefused,
    IntegrationGateway,
    classification_permitted,
    required_decision_class,
)
from integration_registry import (
    CIR_001,
    CapabilityAbstraction,
    ConstructionBlocked,
    DataClassification,
    IntegrationManifest,
    IntegrationRegistry,
    PortabilityDeclaration,
    RiskTier,
    validate_manifest,
)

TENANT = "tenant-alpha"
OWNER = "human-sovereign"


def portable(score: str = "high") -> PortabilityDeclaration:
    if score == "high":
        return PortabilityDeclaration(True, True, True, 100.0)
    return PortabilityDeclaration(True, False, False, 50_000.0)


def manifest(
    integration_id: str = "int-mail",
    provider: str = "MailCo",
    abstraction: str = "capability.email.send",
    tier: RiskTier = RiskTier.T2,
    classification: DataClassification = DataClassification.INTERNAL,
    portability: PortabilityDeclaration | None = None,
) -> IntegrationManifest:
    return IntegrationManifest(
        integration_id=integration_id,
        provider_name=provider,
        abstraction=abstraction,
        tenant_id=TENANT,
        risk_tier=tier,
        max_data_classification=classification,
        portability=portability or portable(),
        owner_principal_id=OWNER,
        cost_model="per-message",
    )


@pytest.fixture
def registry() -> IntegrationRegistry:
    reg = IntegrationRegistry()
    reg.specify_abstraction(
        CapabilityAbstraction(
            name="capability.email.send",
            description="send a transactional message",
            contract={"to": str, "body": str},
        )
    )
    return reg


# ------------------------------------------------- the block itself


def test_the_blocker_is_stated_not_merely_referenced() -> None:
    """A caller should learn *why*, not just *that*."""
    assert "CIR-001" in CIR_001
    assert "Governance ruling at G3 or G4" in CIR_001


@pytest.mark.parametrize(
    "operation",
    ["register", "approve", "activate", "connect", "probe_health", "resolve"],
)
def test_every_registry_construction_verb_is_blocked(registry: IntegrationRegistry, operation: str) -> None:
    with pytest.raises(ConstructionBlocked) as blocked:
        getattr(registry, operation)()
    assert blocked.value.operation == operation
    assert "CIR-001" in str(blocked.value)


@pytest.mark.parametrize(
    "operation",
    ["resolve_abstraction", "consume", "provider_health", "record_consumption", "retire"],
)
def test_every_gateway_construction_verb_is_blocked(operation: str) -> None:
    gateway = IntegrationGateway()
    with pytest.raises(ConstructionBlocked):
        getattr(gateway, operation)()


def test_the_block_raises_rather_than_silently_doing_nothing(registry: IntegrationRegistry) -> None:
    """Build Spec Section 24 — never silently converted to Done status.

    A no-op would let a caller believe an integration was activated. Raising
    is what keeps the debt visible.
    """
    with pytest.raises(ConstructionBlocked):
        registry.activate("int-mail")


# ------------------------------------- specification-level validation (allowed)


def test_a_valid_manifest_can_be_specified(registry: IntegrationRegistry) -> None:
    """Specification is authorized; construction is not."""
    specified = registry.specify(manifest())
    assert specified.integration_id == "int-mail"
    assert registry.specified() == [specified]


def test_an_abstraction_must_be_declared_first(registry: IntegrationRegistry) -> None:
    with pytest.raises(ValidationError, match="not specified"):
        registry.specify(manifest(abstraction="capability.sms.send"))


def test_an_abstraction_may_not_name_its_provider(registry: IntegrationRegistry) -> None:
    """17.6.3 — tools reference the abstraction, not the provider."""
    registry.specify_abstraction(CapabilityAbstraction(name="capability.mailco.send", description="d", contract={}))
    with pytest.raises(ValidationError, match="names the provider"):
        registry.specify(manifest(abstraction="capability.mailco.send", provider="MailCo"))


def test_a_flat_abstraction_is_rejected() -> None:
    with pytest.raises(ValidationError, match="hierarchical"):
        validate_manifest(manifest(abstraction="email"))


def test_anonymous_registration_is_prohibited() -> None:
    bad = IntegrationManifest(
        integration_id="x",
        provider_name="P",
        abstraction="capability.email.send",
        tenant_id=TENANT,
        risk_tier=RiskTier.T2,
        max_data_classification=DataClassification.INTERNAL,
        portability=portable(),
        owner_principal_id="",
        cost_model="free",
    )
    with pytest.raises(ValidationError, match="anonymous"):
        validate_manifest(bad)


# ------------------------------------------ data classification at the boundary


def test_a_t1_integration_cannot_receive_confidential_data() -> None:
    """21B §20.4 — enforced at the boundary, because a provider's assurance is
    not a control."""
    with pytest.raises(ValidationError, match="may not receive"):
        validate_manifest(manifest(tier=RiskTier.T1, classification=DataClassification.CONFIDENTIAL))


def test_classification_is_capped_by_the_tier_not_the_declaration() -> None:
    """A manifest cannot declare its way past its tier's ceiling."""
    t1 = manifest(tier=RiskTier.T1, classification=DataClassification.INTERNAL)
    assert classification_permitted(t1, DataClassification.INTERNAL)
    assert not classification_permitted(t1, DataClassification.CONFIDENTIAL)
    assert not classification_permitted(t1, DataClassification.RESTRICTED)


def test_the_gateway_blocks_over_classified_data() -> None:
    gateway = IntegrationGateway()
    t1 = manifest(tier=RiskTier.T1)
    gateway.check_classification(t1, DataClassification.PUBLIC)
    with pytest.raises(ClassificationRefused, match="blocked before it leaves the system"):
        gateway.check_classification(t1, DataClassification.RESTRICTED)


def test_a_higher_tier_may_receive_restricted_data() -> None:
    t3 = manifest(tier=RiskTier.T3, classification=DataClassification.RESTRICTED)
    assert classification_permitted(t3, DataClassification.RESTRICTED)


# ------------------------------------------------------ approval and portability


def test_approval_is_per_instance_not_per_class() -> None:
    """17.14.1 — a standing order may pre-authorize a class; each instance
    still requires specific approval."""
    gateway = IntegrationGateway()
    instance = manifest(integration_id="int-mail")
    with pytest.raises(ApprovalRequired, match="each instance requires specific approval"):
        gateway.check_approval(instance, approved_instances=set())
    gateway.check_approval(instance, approved_instances={"int-mail"})


def test_low_portability_demands_class_d_approval() -> None:
    """21B §20.4 — low-portability integrations require heightened authority."""
    assert required_decision_class(manifest()) == "C"
    assert required_decision_class(manifest(portability=portable("low"))) == "D"


def test_high_risk_demands_class_d_approval() -> None:
    assert required_decision_class(manifest(tier=RiskTier.T3, classification=DataClassification.RESTRICTED)) == "D"


def test_portability_scores_its_three_declarations() -> None:
    """17.20 — an integration that will not say how it can be left is not
    registrable, so every field is required."""
    assert portable().score == 1.0
    assert portable("low").is_low_portability


# ---------------------------------------------- concentration, from specification


def test_provider_concentration_is_visible_before_construction(
    registry: IntegrationRegistry,
) -> None:
    """21B §20.3 — concentration is a portfolio risk worth seeing early."""
    registry.specify(manifest(integration_id="a", provider="MailCo"))
    registry.specify(manifest(integration_id="b", provider="MailCo"))
    registry.specify(manifest(integration_id="c", provider="OtherCo"))
    concentration = registry.concentration()
    # The Registry rounds to four places, so compare against the same.
    assert concentration["MailCo"] == pytest.approx(2 / 3, abs=1e-4)
    assert concentration["OtherCo"] == pytest.approx(1 / 3, abs=1e-4)


def test_alternatives_for_an_abstraction_are_listable(registry: IntegrationRegistry) -> None:
    """Substitutability is the point of the abstraction layer (17.6.3)."""
    registry.specify(manifest(integration_id="a", provider="MailCo"))
    registry.specify(manifest(integration_id="b", provider="OtherCo"))
    assert registry.alternatives_for("capability.email.send") == ["a", "b"]


def test_no_specified_integration_ever_becomes_active(registry: IntegrationRegistry) -> None:
    """The whole point of the block: specification never becomes operation."""
    registry.specify(manifest())
    # There is no state field to inspect because there is no lifecycle to run:
    # `activate` is blocked, so nothing can reach Active.
    with pytest.raises(ConstructionBlocked):
        registry.activate("int-mail")
