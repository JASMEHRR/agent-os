"""Fixtures for the Memory Gateway suite, wired against a real Security Gateway."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from kernel.signals import SignalEmitter
from memory_gateway import (
    MemoryEntry,
    MemoryGateway,
    Ownership,
    Provenance,
    SecurityGatewayMemoryAuthorizer,
    SemanticRole,
    Sensitivity,
    StructuralForm,
)
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
OTHER_AGENT = "agent-reader"
AGENT_VERIFIER = "hash-writer"
OTHER_VERIFIER = "hash-reader"
BUSINESS = "business-one"

MEMORY_PERMISSIONS = {
    "memory.form.episodic",
    "memory.form.semantic",
    "memory.form.failure",
    "memory.retrieve.public",
    "memory.retrieve.tenant_scoped",
}


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


def register_agent(
    security: SecurityGateway,
    principal_id: str,
    verifier: str,
    permissions: set[str] = MEMORY_PERMISSIONS,
) -> None:
    security.register_identity(
        RegistrationRequest(
            principal_id=principal_id,
            principal_type=PrincipalType.AGENT,
            name=principal_id,
            version="1.0.0",
            tenant_id=TENANT,
            autonomy_level=2,
            approved_by=HUMAN,
        )
    )
    security.change_principal_status(principal_id, PrincipalStatus.ACTIVE, actor_id=HUMAN)
    security.capabilities.define(Capability(name=f"cap-{principal_id}", permits=frozenset(permissions)))
    security.capabilities.grant(principal_id, f"cap-{principal_id}")
    security.roles.define(
        Role(
            name=f"role-{principal_id}",
            permissions=frozenset(permissions),
            eligible_types=frozenset({PrincipalType.AGENT}),
        )
    )
    security.roles.assign(f"role-{principal_id}", principal_id, PrincipalType.AGENT, assigned_by=HUMAN)
    security.recompute_permissions(principal_id)
    security.credentials.issue(f"cred-{principal_id}", principal_id, PrincipalType.AGENT, verifier)


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def security(clock: Clock) -> SecurityGateway:
    gw = SecurityGateway(signing_key=b"memory-test-key", secret_store=NullSecretStore(), now=clock)
    gw.bootstrap_human_sovereign(HUMAN, "Sovereign", TENANT)
    register_agent(gw, AGENT, AGENT_VERIFIER)
    register_agent(gw, OTHER_AGENT, OTHER_VERIFIER)
    return gw


@pytest.fixture
def signals() -> list[object]:
    return []


@pytest.fixture
def memory(security: SecurityGateway, clock: Clock, signals: list[object]) -> MemoryGateway:
    return MemoryGateway(
        authorizer=SecurityGatewayMemoryAuthorizer(gateway=security),
        signals=SignalEmitter(source_identity="memory_gateway", sink=signals.append),
        now=clock,
    )


@pytest.fixture
def agent_token(security: SecurityGateway) -> str:
    token, _ = security.authenticate(AGENT, f"cred-{AGENT}", AGENT_VERIFIER, PrincipalType.AGENT)
    return token


@pytest.fixture
def other_token(security: SecurityGateway) -> str:
    token, _ = security.authenticate(OTHER_AGENT, f"cred-{OTHER_AGENT}", OTHER_VERIFIER, PrincipalType.AGENT)
    return token


def make_entry(
    memory_type: str = "episodic.execution",
    role: SemanticRole = SemanticRole.EPISODIC,
    payload: dict[str, object] | None = None,
    tenant_id: str = TENANT,
    owner: str = AGENT,
    ownership: Ownership = Ownership.TEAM,
    sensitivity: Sensitivity = Sensitivity.TENANT_SCOPED,
    business_id: str | None = BUSINESS,
    source: str = AGENT,
    lineage_ref: str = "event-001",
    occurred_at: datetime | None = None,
) -> MemoryEntry:
    return MemoryEntry(
        memory_type=memory_type,
        role=role,
        form=StructuralForm.ATOMIC,
        payload=payload if payload is not None else {"outcome": "succeeded", "duration_ms": 120},
        tenant_id=tenant_id,
        business_id=business_id,
        workspace_id=None,
        owner_principal_id=owner,
        ownership=ownership,
        sensitivity=sensitivity,
        provenance=Provenance(
            source_identity=source,
            lineage_ref=lineage_ref,
            occurred_at=occurred_at or datetime(2026, 8, 1, 11, 0, tzinfo=UTC),
        ),
    )
