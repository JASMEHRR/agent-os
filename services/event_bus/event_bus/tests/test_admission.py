"""Admission Controller — unit and integration tests (08.7.2, 08.16.1, 08.18)."""

from __future__ import annotations

import pytest

from event_bus import (
    DomainCategory,
    ProducerNotAuthenticated,
    ProducerNotAuthorized,
    SchemaRejected,
    TenantRejected,
)
from security_gateway import PrincipalType

from .conftest import OTHER_TENANT, PRODUCER, PRODUCER_VERIFIER, TENANT


def _emit(bus, token, **overrides):
    kwargs = {
        "event_type": "business.idea.ranked",
        "payload": {"idea_id": "idea-1", "rank": 3},
        "tenant_id": TENANT,
        "source": PRODUCER,
        "trace_id": "trace-1",
    }
    kwargs.update(overrides)
    return bus.emit(token, **kwargs)


def test_authenticated_producer_emits_a_schema_validated_event(bus, producer_token) -> None:
    published = _emit(bus, producer_token)
    assert published.event_type == "business.idea.ranked"
    assert published.category == DomainCategory.BUSINESS
    assert published.stream == f"business.{TENANT}"
    assert published.sequence == 0
    assert published.provenance.source_identity == PRODUCER


def test_unauthenticated_producer_is_rejected(bus) -> None:
    with pytest.raises(ProducerNotAuthenticated):
        _emit(bus, "not.a.token")
    assert bus.health()["admission"]["rejections_by_cause"]["authentication"] == 1


def test_unregistered_event_type_is_rejected_outright(bus, producer_token) -> None:
    """08.16.1 — an unregistered type has no schema and is refused."""
    with pytest.raises(SchemaRejected):
        _emit(bus, producer_token, event_type="business.idea.unheard_of")


def test_payload_violating_its_schema_is_rejected(bus, producer_token) -> None:
    with pytest.raises(SchemaRejected):
        _emit(bus, producer_token, payload={"idea_id": "idea-1", "rank": "third"})


def test_event_type_outside_the_six_categories_has_no_stream(bus, producer_token) -> None:
    with pytest.raises(SchemaRejected, match="six domain categories"):
        _emit(bus, producer_token, event_type="nonsense.thing.happened")


def test_producer_may_not_emit_into_another_tenant(bus, producer_token) -> None:
    """08 rule 3 — no event crosses a tenant boundary without bilateral approval."""
    with pytest.raises(TenantRejected):
        _emit(bus, producer_token, tenant_id=OTHER_TENANT)


def test_producer_lacking_the_emission_permission_is_denied(bus, gateway, producer_token) -> None:
    """08.18.2 — authorization at emission, enforced by the real Trust Plane."""
    gateway.roles.unassign(f"role-{PRODUCER}", PRODUCER)
    gateway.capabilities.revoke(PRODUCER, f"cap-{PRODUCER}")
    gateway.recompute_permissions(PRODUCER)
    with pytest.raises(ProducerNotAuthorized):
        _emit(bus, producer_token)


def test_emission_failure_is_never_silent(bus, producer_token) -> None:
    """21B §15.4 — producers may not silently swallow emission failure."""
    with pytest.raises(SchemaRejected):
        _emit(bus, producer_token, payload={})
    # Nothing was published, and the rejection is counted by cause.
    assert bus.health()["total_depth"] == 0
    assert bus.health()["admission"]["rejected"] == 1


def test_admission_precedes_publication(bus, producer_token) -> None:
    """A rejected event never reaches the durable log."""
    with pytest.raises(ProducerNotAuthenticated):
        _emit(bus, "bad-token")
    assert bus.store.total_depth() == 0


def test_rejections_are_counted_per_cause(bus, gateway, producer_token) -> None:
    with pytest.raises(ProducerNotAuthenticated):
        _emit(bus, "bad")
    with pytest.raises(SchemaRejected):
        _emit(bus, producer_token, payload={})
    with pytest.raises(TenantRejected):
        _emit(bus, producer_token, tenant_id=OTHER_TENANT)
    causes = bus.health()["admission"]["rejections_by_cause"]
    assert causes == {"authentication": 1, "schema": 1, "tenant": 1}


def test_a_revoked_producer_cannot_emit(bus, gateway, producer_token) -> None:
    from security_gateway.enums import RevocationTrigger

    from .conftest import HUMAN

    gateway.revoke(PRODUCER, HUMAN, RevocationTrigger.SUSPENSION, "anomaly")
    with pytest.raises(ProducerNotAuthenticated):
        _emit(bus, producer_token)


def test_reauthentication_yields_a_usable_token(bus, gateway) -> None:
    token, _ = gateway.authenticate(PRODUCER, f"cred-{PRODUCER}", PRODUCER_VERIFIER, PrincipalType.SERVICE)
    assert _emit(bus, token).sequence == 0
