"""Shared fixtures for the Security Gateway suite.

Builds the smallest realistic trust world: one human sovereign, one agent,
one service, and the capability/role definitions the agent needs to do
anything at all. Time is injectable everywhere so expiry and TTL behaviour is
tested deterministically rather than with sleeps.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

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
AGENT = "agent-writer"
SERVICE = "service-tool-executor"

#: Verifier hashes stand in for the salted credential digests a real
#: deployment stores. No plaintext credential exists anywhere in the suite.
HUMAN_VERIFIER = "hash-human"
AGENT_VERIFIER = "hash-agent"
SERVICE_VERIFIER = "hash-service"


class Clock:
    """Manually advanced clock, so token TTL and delegation expiry are exact."""

    def __init__(self, start: datetime | None = None) -> None:
        self.now = start or datetime(2026, 8, 1, 12, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.now

    def advance(self, delta: timedelta) -> None:
        self.now += delta


class FakeSecretStore:
    """In-test secret store. Values live here and nowhere else."""

    def __init__(self) -> None:
        self._values: dict[str, str] = {}

    def read(self, reference: str) -> str:
        return self._values[reference]

    def write(self, reference: str, value: str) -> None:
        self._values[reference] = value


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def store() -> FakeSecretStore:
    return FakeSecretStore()


@pytest.fixture
def gateway(clock: Clock, store: FakeSecretStore) -> SecurityGateway:
    gw = SecurityGateway(signing_key=b"test-signing-key-not-a-real-secret", secret_store=store, now=clock)

    gw.bootstrap_human_sovereign(HUMAN, "Sovereign", TENANT)
    gw.credentials.issue(f"cred-{HUMAN}", HUMAN, PrincipalType.HUMAN, HUMAN_VERIFIER)

    gw.register_identity(
        RegistrationRequest(
            principal_id=AGENT,
            principal_type=PrincipalType.AGENT,
            name="Writer",
            version="1.0.0",
            tenant_id=TENANT,
            autonomy_level=2,
            approved_by=HUMAN,
        )
    )
    gw.register_identity(
        RegistrationRequest(
            principal_id=SERVICE,
            principal_type=PrincipalType.SERVICE,
            name="Tool Executor",
            version="1.0.0",
            tenant_id=TENANT,
            approved_by=HUMAN,
        )
    )
    gw.credentials.issue(f"cred-{AGENT}", AGENT, PrincipalType.AGENT, AGENT_VERIFIER)
    gw.credentials.issue(f"cred-{SERVICE}", SERVICE, PrincipalType.SERVICE, SERVICE_VERIFIER)

    gw.capabilities.define(
        Capability(name="content.generation", permits=frozenset({"business.content.generate", "tool.invoke"}))
    )
    gw.roles.define(
        Role(
            name="writer",
            permissions=frozenset({"business.content.generate", "tool.invoke"}),
            eligible_types=frozenset({PrincipalType.AGENT}),
        )
    )
    gw.roles.define(
        Role(
            name="reviewer",
            permissions=frozenset({"business.content.review"}),
            eligible_types=frozenset({PrincipalType.AGENT}),
            conflicts_with=frozenset({"writer"}),
        )
    )

    gw.capabilities.grant(AGENT, "content.generation")
    gw.roles.assign("writer", AGENT, PrincipalType.AGENT, assigned_by=HUMAN)
    gw.change_principal_status(AGENT, PrincipalStatus.ACTIVE, actor_id=HUMAN)
    gw.change_principal_status(SERVICE, PrincipalStatus.ACTIVE, actor_id=HUMAN)
    gw.recompute_permissions(AGENT)
    return gw


@pytest.fixture
def agent_token(gateway: SecurityGateway) -> str:
    token, _ = gateway.authenticate(AGENT, f"cred-{AGENT}", AGENT_VERIFIER, PrincipalType.AGENT)
    return token
