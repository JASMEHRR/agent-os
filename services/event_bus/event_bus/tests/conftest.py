"""Shared fixtures for the Event Bus suite.

The Bus is wired against a **real Security Gateway** rather than a stub, so
these are genuine integration tests across the S1→S2 dependency edge: a
producer really authenticates, a real permission graph really authorizes the
emission, and a denial really comes from the Permission Intersection Rule.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from event_bus import EventBus, SchemaRegistrySource, SecurityGatewayTrustPlane
from schema_registry import SchemaRegistry
from security_gateway import (
    Capability,
    PrincipalType,
    RegistrationRequest,
    Role,
    SecurityGateway,
)
from security_gateway.enums import PrincipalStatus

TENANT = "tenant-alpha"
OTHER_TENANT = "tenant-beta"
HUMAN = "human-sovereign"
PRODUCER = "service-producer"
CONSUMER = "service-consumer"
PRODUCER_VERIFIER = "hash-producer"
CONSUMER_VERIFIER = "hash-consumer"


class Clock:
    def __init__(self, start: datetime | None = None) -> None:
        self.now = start or datetime(2026, 8, 1, 12, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.now

    def advance(self, delta: timedelta) -> None:
        self.now += delta


class AlertSink:
    """Out-of-band alert channel (21B §15.11) — a list, in tests."""

    def __init__(self) -> None:
        self.alerts: list[tuple[str, dict[str, object]]] = []

    def __call__(self, kind: str, detail: dict[str, object]) -> None:
        self.alerts.append((kind, detail))

    def of_kind(self, kind: str) -> list[dict[str, object]]:
        return [detail for k, detail in self.alerts if k == kind]


def _register_service(
    gateway: SecurityGateway,
    principal_id: str,
    verifier: str,
    permissions: set[str],
    tenant_id: str = TENANT,
) -> None:
    gateway.register_identity(
        RegistrationRequest(
            principal_id=principal_id,
            principal_type=PrincipalType.SERVICE,
            name=principal_id,
            version="1.0.0",
            tenant_id=tenant_id,
            approved_by=HUMAN,
        )
    )
    gateway.change_principal_status(principal_id, PrincipalStatus.ACTIVE, actor_id=HUMAN)
    gateway.capabilities.define(Capability(name=f"cap-{principal_id}", permits=frozenset(permissions)))
    gateway.capabilities.grant(principal_id, f"cap-{principal_id}")
    gateway.roles.define(
        Role(
            name=f"role-{principal_id}",
            permissions=frozenset(permissions),
            eligible_types=frozenset({PrincipalType.SERVICE}),
        )
    )
    gateway.roles.assign(f"role-{principal_id}", principal_id, PrincipalType.SERVICE, assigned_by=HUMAN)
    gateway.recompute_permissions(principal_id)
    gateway.credentials.issue(f"cred-{principal_id}", principal_id, PrincipalType.SERVICE, verifier)


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def alerts() -> AlertSink:
    return AlertSink()


@pytest.fixture
def gateway(clock: Clock) -> SecurityGateway:
    class NullSecretStore:
        def read(self, reference: str) -> str:
            raise KeyError(reference)

        def write(self, reference: str, value: str) -> None:
            pass

    gw = SecurityGateway(signing_key=b"event-bus-test-key", secret_store=NullSecretStore(), now=clock)
    gw.bootstrap_human_sovereign(HUMAN, "Sovereign", TENANT)
    _register_service(
        gw,
        PRODUCER,
        PRODUCER_VERIFIER,
        {"event.emit.business", "event.emit.system", "event.emit.audit", "event.emit.command"},
    )
    _register_service(
        gw,
        CONSUMER,
        CONSUMER_VERIFIER,
        {"event.subscribe.business", "event.subscribe.system", "event.subscribe.replay", "event.subscribe.audit"},
    )
    return gw


@pytest.fixture
def schemas() -> SchemaRegistry:
    registry = SchemaRegistry()
    registry.register("business.idea.ranked", "1.0", {"idea_id": str, "rank": int})
    registry.register("business.product.launched", "1.0", {"product_id": str})
    registry.register("system.service.healthy", "1.0", {"service": str})
    registry.register("audit.tool.executed", "1.0", {"tool": str})
    registry.register("command.panic.invoked", "1.0", {"invoked_by": str})
    return registry


@pytest.fixture
def bus(gateway: SecurityGateway, schemas: SchemaRegistry, alerts: AlertSink, clock: Clock) -> EventBus:
    return EventBus(
        trust=SecurityGatewayTrustPlane(gateway=gateway),
        schemas=SchemaRegistrySource(registry=schemas),
        alert=alerts,
        now=clock,
    )


@pytest.fixture
def producer_token(gateway: SecurityGateway) -> str:
    token, _ = gateway.authenticate(PRODUCER, f"cred-{PRODUCER}", PRODUCER_VERIFIER, PrincipalType.SERVICE)
    return token


@pytest.fixture
def consumer_token(gateway: SecurityGateway) -> str:
    token, _ = gateway.authenticate(CONSUMER, f"cred-{CONSUMER}", CONSUMER_VERIFIER, PrincipalType.SERVICE)
    return token
