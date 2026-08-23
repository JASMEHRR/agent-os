"""Fixtures for the Observability Gateway suite.

Wired against a real Security Gateway, so query authorization genuinely runs
through the Permission Intersection Rule — 21B §24.10 forbids an observability
bypass, and a stub authorizer would be exactly that bypass in test form.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from kernel.signals import Sensitivity, Signal, SignalType
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
OPERATOR = "service-governance"
OPERATOR_VERIFIER = "hash-governance"


class Clock:
    def __init__(self, start: datetime | None = None) -> None:
        self.now = start or datetime(2026, 8, 1, 12, 0, tzinfo=UTC)

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
    gw = SecurityGateway(signing_key=b"observability-test-key", secret_store=NullSecretStore(), now=clock)
    gw.bootstrap_human_sovereign(HUMAN, "Sovereign", TENANT)
    gw.register_identity(
        RegistrationRequest(
            principal_id=OPERATOR,
            principal_type=PrincipalType.SERVICE,
            name="Governance",
            version="1.0.0",
            tenant_id=TENANT,
            approved_by=HUMAN,
        )
    )
    gw.change_principal_status(OPERATOR, PrincipalStatus.ACTIVE, actor_id=HUMAN)
    permissions = {"observability.query.public", "observability.query.internal"}
    gw.capabilities.define(Capability(name="oversight", permits=frozenset(permissions)))
    gw.capabilities.grant(OPERATOR, "oversight")
    gw.roles.define(
        Role(
            name="oversight",
            permissions=frozenset(permissions),
            eligible_types=frozenset({PrincipalType.SERVICE}),
        )
    )
    gw.roles.assign("oversight", OPERATOR, PrincipalType.SERVICE, assigned_by=HUMAN)
    gw.recompute_permissions(OPERATOR)
    gw.credentials.issue(f"cred-{OPERATOR}", OPERATOR, PrincipalType.SERVICE, OPERATOR_VERIFIER)
    return gw


@pytest.fixture
def observability(security: SecurityGateway, clock: Clock) -> ObservabilityGateway:
    return ObservabilityGateway(
        authorizer=SecurityGatewayQueryAuthorizer(gateway=security),
        now=clock,
    )


@pytest.fixture
def operator_token(security: SecurityGateway) -> str:
    token, _ = security.authenticate(OPERATOR, f"cred-{OPERATOR}", OPERATOR_VERIFIER, PrincipalType.SERVICE)
    return token


def make_signal(
    name: str = "authorization.latency_ms",
    signal_type: SignalType = SignalType.METRIC,
    source: str = "security_gateway",
    tenant_id: str = TENANT,
    value: float | None = 4.0,
    sensitivity: Sensitivity = Sensitivity.INTERNAL,
    **kwargs: object,
) -> Signal:
    return Signal(
        signal_type=signal_type,
        name=name,
        source_identity=source,
        tenant_id=tenant_id,
        value=value,
        sensitivity=sensitivity,
        **kwargs,  # type: ignore[arg-type]
    )
