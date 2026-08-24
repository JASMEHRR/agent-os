"""Integration Platform conformance (17, per 21B §20).

**Construction authorized 2026-08-24** by G4 ruling on CIR-001. This suite
replaces `test_construction_block.py`, which asserted that every construction
verb raised. That suite was correct for eleven stages and is wrong now, so it
was deleted rather than left passing against a block that no longer exists.

What the ruling did *not* change is what this suite tests hardest. The naming
prohibition still governs capability abstractions, so an abstraction may not
name a provider — and that constraint is what makes every other guarantee in
document 17 mean something. The ruling scoped the prohibition; it did not
weaken it.

The rules tested hardest here:

* an abstraction may not name a provider (17.6.3, 17 rule 21, still in force);
* data classification is enforced at the boundary, not trusted to the provider
  (21B §20.4);
* approval is per-instance and a class-level standing order never satisfies it
  (17.14.1);
* low portability demands Class D authority whatever the risk tier (17.20.1).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from core.exceptions import AgentOSError, NotFoundError, ValidationError
from integration_gateway import (
    ApprovalRequired,
    ClassificationRefused,
    IntegrationGateway,
)
from integration_registry import (
    HEALTH_MINIMUM_SAMPLE,
    ApprovalAuthorityInsufficient,
    CapabilityAbstraction,
    DataClassification,
    IntegrationManifest,
    IntegrationRegistry,
    IntegrationState,
    PortabilityDeclaration,
    RiskTier,
    required_decision_class,
    validate_manifest,
)

TENANT = "tenant-alpha"
HUMAN = "human-sovereign"
AGENT = "agent-analyst"


class Clock:
    def __init__(self) -> None:
        self.now = datetime(2026, 8, 24, 12, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        self.now += timedelta(milliseconds=5)
        return self.now


def portability(**overrides: Any) -> PortabilityDeclaration:
    defaults: dict[str, Any] = {
        "data_extractable": True,
        "schema_standardized": True,
        "abstraction_complete": True,
        "migration_cost_estimate": 500.0,
    }
    defaults.update(overrides)
    return PortabilityDeclaration(**defaults)


def manifest(integration_id: str = "int-shop", **overrides: Any) -> IntegrationManifest:
    defaults: dict[str, Any] = {
        "integration_id": integration_id,
        "provider_name": "example-shop",
        "abstraction": "catalogue.sync",
        "tenant_id": TENANT,
        "risk_tier": RiskTier.T2,
        "max_data_classification": DataClassification.INTERNAL,
        "portability": portability(),
        "owner_principal_id": HUMAN,
        "cost_model": "per-call",
    }
    defaults.update(overrides)
    return IntegrationManifest(**defaults)


def abstraction(name: str = "catalogue.sync") -> CapabilityAbstraction:
    return CapabilityAbstraction(
        name=name,
        description="synchronise a product catalogue with an external store",
        contract={"items": list},
    )


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def registry(clock: Clock) -> IntegrationRegistry:
    reg = IntegrationRegistry(now=clock)
    reg.specify_abstraction(abstraction())
    return reg


@pytest.fixture
def gateway(registry: IntegrationRegistry, clock: Clock) -> IntegrationGateway:
    return IntegrationGateway(registry=registry, now=clock)


def activated(
    registry: IntegrationRegistry, gateway: IntegrationGateway, integration_id: str = "int-shop", **overrides: Any
) -> Any:
    record = registry.register(manifest(integration_id, **overrides), actor_id=HUMAN)
    registry.validate(integration_id)
    registry.approve(integration_id, HUMAN, is_human=True, decision_class="D")
    registry.activate(integration_id)
    gateway.record_instance_approval(integration_id, HUMAN, is_human=True)
    return record


# ------------------------------------ The constraint the ruling did NOT lift


def test_an_abstraction_may_not_name_its_provider(registry: IntegrationRegistry) -> None:
    """17.6.3 with 17 rule 21 — untouched by the CIR-001 ruling.

    The ruling scoped the naming prohibition to abstractions and governance
    artifacts. That means this constraint did not merely survive: it is the
    half the ruling *kept*, and it is what makes substitution real rather than
    aspirational. A tool bound to an abstraction that named a provider would be
    bound to the provider.
    """
    registry.register(manifest(), actor_id=HUMAN)
    named = registry.abstractions()[0]
    assert "example-shop" not in named.name
    assert "example-shop" not in named.description
    # And the manifest, which *may* name one, does.
    assert registry.get("int-shop").manifest.provider_name == "example-shop"


def test_substituting_the_provider_leaves_the_abstraction_constant(
    registry: IntegrationRegistry, gateway: IntegrationGateway
) -> None:
    """17.6.3's guarantee, exercised rather than asserted.

    Two providers fulfil one capability. The first is suspended; the caller
    asks for the same capability and is served by the second, having named no
    provider at any point.
    """
    activated(registry, gateway, "int-shop")
    activated(registry, gateway, "int-other", provider_name="other-shop")

    first = gateway.resolve_abstraction("catalogue.sync", TENANT)
    registry.suspend(first.integration_id, "provider outage")

    second = gateway.resolve_abstraction("catalogue.sync", TENANT)
    assert second.integration_id != first.integration_id
    assert second.manifest.abstraction == first.manifest.abstraction


def test_an_integration_must_fulfil_a_declared_abstraction(registry: IntegrationRegistry) -> None:
    with pytest.raises(ValidationError, match="not specified"):
        registry.register(manifest(abstraction="nothing.declared"), actor_id=HUMAN)


# ------------------------------------------------------ Registration (17.8)


def test_registration_is_not_approval_and_approval_is_not_activation(
    registry: IntegrationRegistry,
) -> None:
    """17.14.1 — three distinct gates, and none may be skipped."""
    record = registry.register(manifest(), actor_id=HUMAN)
    assert record.state == IntegrationState.REGISTERED
    assert not record.is_consumable

    with pytest.raises(AgentOSError, match="expected one of"):
        registry.activate("int-shop")

    registry.validate("int-shop")
    with pytest.raises(AgentOSError, match="expected one of"):
        registry.activate("int-shop")

    registry.approve("int-shop", HUMAN, is_human=True, decision_class="D")
    assert registry.activate("int-shop").is_consumable


def test_anonymous_registration_is_prohibited(registry: IntegrationRegistry) -> None:
    """17 rule 7."""
    with pytest.raises(ValidationError, match="anonymous registration"):
        registry.register(manifest(), actor_id="")


def test_a_duplicate_integration_id_is_refused(registry: IntegrationRegistry) -> None:
    registry.register(manifest(), actor_id=HUMAN)
    with pytest.raises(AgentOSError, match="already registered"):
        registry.register(manifest(), actor_id=HUMAN)


def test_an_unknown_integration_is_a_not_found(registry: IntegrationRegistry) -> None:
    with pytest.raises(NotFoundError):
        registry.get("int-nobody")


# ------------------------------------------------ Approval authority (17.14)


@pytest.mark.parametrize(
    ("tier", "expected"),
    [(RiskTier.T1, "B"), (RiskTier.T2, "B"), (RiskTier.T3, "C"), (RiskTier.T4, "D")],
)
def test_approval_class_rises_with_risk_tier(tier: RiskTier, expected: str) -> None:
    assert required_decision_class(manifest(risk_tier=tier)) == expected


def test_low_portability_demands_class_d_whatever_the_risk_tier() -> None:
    """17.20.1 — lock-in is a failure category in its own right.

    An integration that cannot be left is a commitment rather than a choice,
    and the authority required should reflect that even when the risk tier is
    low.
    """
    trapped = manifest(
        risk_tier=RiskTier.T1,
        portability=portability(data_extractable=False, abstraction_complete=False),
    )
    assert trapped.portability.is_low_portability
    assert required_decision_class(trapped) == "D"


def test_insufficient_approval_authority_is_refused(registry: IntegrationRegistry) -> None:
    registry.register(manifest(risk_tier=RiskTier.T4), actor_id=HUMAN)
    registry.validate("int-shop")
    with pytest.raises(ApprovalAuthorityInsufficient, match="requires Class D"):
        registry.approve("int-shop", AGENT, is_human=False, decision_class="C")


def test_class_d_approval_requires_a_human(registry: IntegrationRegistry) -> None:
    """17.31.1 — Class D integration approvals are human acts."""
    registry.register(manifest(risk_tier=RiskTier.T4), actor_id=HUMAN)
    registry.validate("int-shop")
    with pytest.raises(ApprovalAuthorityInsufficient, match="human principal"):
        registry.approve("int-shop", AGENT, is_human=False, decision_class="D")
    assert registry.approve("int-shop", HUMAN, is_human=True, decision_class="D").approved_by == HUMAN


# ------------------------------------ Boundary enforcement (21B §20.4)


def test_data_above_the_ceiling_is_refused_before_egress(
    registry: IntegrationRegistry, gateway: IntegrationGateway
) -> None:
    """21B §20.4 — "a provider's assurance that it will not retain data is not
    a control". The check runs here, on the tier, before anything leaves."""
    activated(registry, gateway, risk_tier=RiskTier.T1)
    called: list[str] = []

    def provider(payload: Any) -> dict[str, Any]:
        called.append("reached")
        return {}

    with pytest.raises(ClassificationRefused, match="blocked before it leaves"):
        gateway.consume(
            "catalogue.sync",
            TENANT,
            {"items": []},
            DataClassification.RESTRICTED,
            call=provider,
        )
    assert called == [], "the provider was never reached"


def test_data_within_the_ceiling_passes(registry: IntegrationRegistry, gateway: IntegrationGateway) -> None:
    activated(registry, gateway)
    result = gateway.consume(
        "catalogue.sync",
        TENANT,
        {"items": [1, 2]},
        DataClassification.INTERNAL,
        call=lambda payload: {"synced": len(payload["items"])},
    )
    assert result.succeeded
    assert result.payload == {"synced": 2}


def test_approval_is_per_instance_not_per_class(registry: IntegrationRegistry, gateway: IntegrationGateway) -> None:
    """17.14.1 — a standing order may pre-authorize a class and never an instance."""
    registry.register(manifest(), actor_id=HUMAN)
    registry.validate("int-shop")
    registry.approve("int-shop", HUMAN, is_human=True, decision_class="D")
    registry.activate("int-shop")
    # Registered, approved and active — and still not consumable, because the
    # per-instance approval on the consumption side has not been given.
    with pytest.raises(ApprovalRequired, match="instance-specific approval"):
        gateway.consume("catalogue.sync", TENANT, {"items": []}, DataClassification.INTERNAL, call=lambda p: {})

    gateway.record_instance_approval("int-shop", HUMAN, is_human=True)
    assert gateway.consume(
        "catalogue.sync", TENANT, {"items": []}, DataClassification.INTERNAL, call=lambda p: {}
    ).succeeded


def test_a_suspended_integration_cannot_be_consumed(registry: IntegrationRegistry, gateway: IntegrationGateway) -> None:
    activated(registry, gateway)
    registry.suspend("int-shop", "provider outage")
    with pytest.raises(NotFoundError, match="no active integration"):
        gateway.consume("catalogue.sync", TENANT, {}, DataClassification.INTERNAL, call=lambda p: {})


def test_consumption_never_crosses_the_tenant_boundary(
    registry: IntegrationRegistry, gateway: IntegrationGateway
) -> None:
    activated(registry, gateway)
    with pytest.raises(NotFoundError):
        gateway.resolve_abstraction("catalogue.sync", "tenant-beta")


# --------------------------------------------------- Provider health (17.18)


def test_a_failing_provider_is_scored_and_eventually_suspended(
    registry: IntegrationRegistry, gateway: IntegrationGateway
) -> None:
    """17.18 — repeated failure suspends, and the Gateway reports rather than probes."""
    activated(registry, gateway)

    def explode(payload: Any) -> Any:
        raise RuntimeError("the provider is down")

    for _ in range(HEALTH_MINIMUM_SAMPLE):
        result = gateway.consume("catalogue.sync", TENANT, {}, DataClassification.INTERNAL, call=explode)
        if not registry.get("int-shop").is_consumable:
            break
    assert not result.succeeded
    assert registry.get("int-shop").state == IntegrationState.SUSPENDED


def test_a_healthy_provider_is_not_suspended(registry: IntegrationRegistry, gateway: IntegrationGateway) -> None:
    activated(registry, gateway)
    for _ in range(6):
        gateway.consume("catalogue.sync", TENANT, {}, DataClassification.INTERNAL, call=lambda p: {})
    record = registry.get("int-shop")
    assert record.state == IntegrationState.ACTIVE
    assert record.health_score == 1.0


def test_provider_health_is_observed_not_probed(registry: IntegrationRegistry, gateway: IntegrationGateway) -> None:
    """17.8 — the Registry governs existence and holds no connection.

    Structural: a Registry with a `probe` verb would be dialling a provider,
    which is the Gateway's half of the split.
    """
    forbidden = {"probe", "call", "connect", "dial", "fetch"}
    present = {name for name in dir(IntegrationRegistry) if not name.startswith("_")}
    assert not (forbidden & present), f"the Registry acquired a connection verb: {forbidden & present}"

    activated(registry, gateway)
    gateway.consume("catalogue.sync", TENANT, {}, DataClassification.INTERNAL, call=lambda p: {})
    assert gateway.provider_health("int-shop")["consumptions"] == 1


# ------------------------------------------ Human override and panic (17.31)


def test_termination_is_a_human_act(registry: IntegrationRegistry, gateway: IntegrationGateway) -> None:
    """17.31.2 — immediate, irreversible by the system, logged."""
    activated(registry, gateway)
    with pytest.raises(ApprovalRequired, match="human override"):
        gateway.terminate("int-shop", "unsafe", is_human=False)
    record = gateway.terminate("int-shop", "provider breached its contract", is_human=True)
    assert record.state == IntegrationState.SUSPENDED


def test_panic_suspends_every_active_integration(registry: IntegrationRegistry, gateway: IntegrationGateway) -> None:
    """17.31.4 — panic halts all consumption within five seconds.

    Consumption stops because the instances lose their approval, not because a
    flag was set. A flag is something a later code path can forget to check.
    """
    activated(registry, gateway, "int-shop")
    activated(registry, gateway, "int-other", provider_name="other-shop")

    assert gateway.halt() == 2
    assert registry.active() == []
    with pytest.raises(NotFoundError):
        gateway.consume("catalogue.sync", TENANT, {}, DataClassification.INTERNAL, call=lambda p: {})


# ----------------------------------------------- Deprecation and portability


def test_deprecation_names_a_successor_where_one_exists(
    registry: IntegrationRegistry, gateway: IntegrationGateway
) -> None:
    """17.22 — a consumer is told where to go, not merely that it may not stay."""
    activated(registry, gateway, "int-shop")
    activated(registry, gateway, "int-other", provider_name="other-shop")
    record = registry.deprecate("int-shop", successor_id="int-other")
    assert record.successor_id == "int-other"
    assert record.state == IntegrationState.DEPRECATED


def test_a_successor_must_exist(registry: IntegrationRegistry, gateway: IntegrationGateway) -> None:
    activated(registry, gateway)
    with pytest.raises(NotFoundError, match="successor"):
        registry.deprecate("int-shop", successor_id="int-ghost")


def test_alternatives_are_known_before_they_are_needed(
    registry: IntegrationRegistry, gateway: IntegrationGateway
) -> None:
    """17.23's portability guarantee is only real if the alternatives are visible."""
    activated(registry, gateway, "int-shop")
    activated(registry, gateway, "int-other", provider_name="other-shop")
    assert set(gateway.alternatives("catalogue.sync", TENANT)) == {"int-shop", "int-other"}


def test_provider_concentration_is_visible(registry: IntegrationRegistry) -> None:
    """21B §20.2 — concentration is a portfolio risk the Registry monitors."""
    registry.specify(manifest("int-a"))
    registry.specify(manifest("int-b"))
    registry.specify(manifest("int-c", provider_name="other-shop"))
    concentration = registry.concentration()
    assert concentration["example-shop"] == pytest.approx(0.6667, abs=0.001)


# --------------------------------------------------- Manifest schema (17.20)


def test_a_manifest_must_declare_its_exit_cost() -> None:
    """17.20.1 — an integration that will not say how it can be left is not registrable."""
    with pytest.raises(ValidationError):
        validate_manifest(manifest(portability=portability(migration_cost_estimate=-1.0)))


def test_a_manifest_may_not_exceed_its_tiers_classification_ceiling() -> None:
    with pytest.raises(ValidationError, match="ceiling"):
        validate_manifest(manifest(risk_tier=RiskTier.T1, max_data_classification=DataClassification.RESTRICTED))


# -------------------------------------------------------- The ruling itself


def test_construction_is_authorized_and_the_module_says_so(
    registry: IntegrationRegistry, gateway: IntegrationGateway
) -> None:
    """The status the registers and Appendix F now read.

    Before 2026-08-24 both modules reported `construction_authorized: False`
    and every construction verb raised. The ruling changed that, and the health
    surface is where a caller finds out.
    """
    for surface in (registry.health(), gateway.health()):
        assert surface["construction_authorized"] is True
        assert "resolved" in surface["cir_001"]


def test_no_construction_verb_raises_construction_blocked(
    registry: IntegrationRegistry, gateway: IntegrationGateway
) -> None:
    """The inverse of the suite this file replaced.

    That suite asserted every construction verb raised. This asserts none does,
    which is the same discipline pointed the other way: a block that lingered
    in one forgotten method would be as invisible as one that decayed.
    """
    from integration_registry import ConstructionBlocked

    activated(registry, gateway)
    try:
        gateway.consume("catalogue.sync", TENANT, {}, DataClassification.INTERNAL, call=lambda p: {})
        registry.record_health("int-shop", healthy=True)
        registry.deprecate("int-shop")
        registry.retire("int-shop")
    except ConstructionBlocked as blocked:  # pragma: no cover - the point is that it does not happen
        pytest.fail(f"a construction verb still raises after the CIR-001 ruling: {blocked}")


def test_the_journal_records_the_lifecycle(registry: IntegrationRegistry, gateway: IntegrationGateway) -> None:
    activated(registry, gateway)
    actions = [entry["action"] for entry in registry.journal_entries()]
    assert actions == ["registered", "validated", "approved", "activated"]
    assert registry.health()["journal_intact"]
