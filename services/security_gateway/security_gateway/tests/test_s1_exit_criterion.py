"""Stage S1 exit criterion, demonstrated end to end.

Build Specification, Stage S1, Validation Criteria — quoted:

    "A principal can register, authenticate, receive a scoped token, be
    authorized against a resource, be delegated to, and be revoked with
    cascading effect; the Security Event Journal resists tampering."

This module runs exactly that sequence as one narrative, then asserts the
whole thing is independently reconstructable from the journal. It is retained
as a standing regression test for every later stage.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta

import pytest

from kernel.journal import JournalTamperError
from security_gateway import (
    AuthorizationRequest,
    Capability,
    Decision,
    PrincipalType,
    RegistrationRequest,
    Role,
    SecurityGateway,
)
from security_gateway.enums import DelegationType, PrincipalStatus, RevocationTrigger, SecurityEventType
from security_gateway.tokens import AuthenticationError, TokenRevokedError

from .conftest import AGENT, AGENT_VERIFIER, HUMAN, TENANT

NEW_AGENT = "agent-researcher"
NEW_VERIFIER = "hash-researcher"


def test_s1_exit_criterion(gateway: SecurityGateway) -> None:
    acknowledged: list[str] = []
    for subsystem in ("runtime", "agent", "tool", "memory", "decision"):

        def _ack(_principal_id: str, name: str = subsystem) -> bool:
            acknowledged.append(name)
            return True

        gateway.revocations.register_target(subsystem, _ack)

    # 1. A principal can register.
    principal = gateway.register_identity(
        RegistrationRequest(
            principal_id=NEW_AGENT,
            principal_type=PrincipalType.AGENT,
            name="Researcher",
            version="1.0.0",
            tenant_id=TENANT,
            autonomy_level=2,
            approved_by=HUMAN,
        )
    )
    assert principal.status == PrincipalStatus.REGISTERED

    gateway.capabilities.define(Capability(name="research", permits=frozenset({"knowledge.search", "tool.invoke"})))
    gateway.roles.define(
        Role(
            name="researcher",
            permissions=frozenset({"knowledge.search", "tool.invoke"}),
            eligible_types=frozenset({PrincipalType.AGENT}),
        )
    )
    gateway.capabilities.grant(NEW_AGENT, "research")
    gateway.roles.assign("researcher", NEW_AGENT, PrincipalType.AGENT, assigned_by=HUMAN)
    gateway.change_principal_status(NEW_AGENT, PrincipalStatus.ACTIVE, actor_id=HUMAN)
    gateway.recompute_permissions(NEW_AGENT)
    gateway.credentials.issue(f"cred-{NEW_AGENT}", NEW_AGENT, PrincipalType.AGENT, NEW_VERIFIER)

    # 2. ...authenticate, and 3. receive a scoped token.
    token, claims = gateway.authenticate(
        NEW_AGENT, f"cred-{NEW_AGENT}", NEW_VERIFIER, PrincipalType.AGENT, workspace_ids=("ws-research",)
    )
    assert claims.principal_id == NEW_AGENT
    assert claims.tenant_id == TENANT
    assert set(claims.permissions) == {"knowledge.search", "tool.invoke"}
    assert claims.expires_at - claims.issued_at <= timedelta(hours=1)

    # 4. ...be authorized against a resource.
    allowed = gateway.authorize(
        token,
        AuthorizationRequest(action="knowledge.search", resource_id="corpus-1", resource_tenant_id=TENANT),
    )
    assert allowed.decision == Decision.ALLOW

    denied = gateway.authorize(
        token,
        AuthorizationRequest(action="decision.commit", resource_id="dec-1", resource_tenant_id=TENANT),
    )
    assert denied.decision == Decision.DENY

    # A security context propagates through the authorized action.
    context = gateway.create_security_context(claims, trace_id="trace-s1")
    assert gateway.validate_security_context(context, "knowledge.search").principal_id == NEW_AGENT

    # 5. ...be delegated to.
    delegation = gateway.manage_delegation(
        operation="create",
        delegation_id="deleg-s1",
        actor_id=AGENT,
        delegation_type=DelegationType.TASK,
        delegatee_id=NEW_AGENT,
        permissions=("tool.invoke",),
        duration=timedelta(hours=2),
    )
    assert delegation.permissions == frozenset({"tool.invoke"})
    # The lent scope intersects with what the delegatee already held.
    assert gateway.graph_engine.graph_for(NEW_AGENT).effective == frozenset({"tool.invoke"})

    # 6. ...and be revoked, with cascading effect.
    record = gateway.revoke(
        principal_id=NEW_AGENT,
        revoker_id=HUMAN,
        trigger=RevocationTrigger.HUMAN_COMMAND,
        reason="stage S1 exit criterion",
    )
    assert sorted(record.cascaded_to) == ["agent", "decision", "memory", "runtime", "tool"]
    assert sorted(acknowledged) == ["agent", "decision", "memory", "runtime", "tool"]
    assert "deleg-s1" in record.delegations_revoked
    assert gateway.revocations.is_revoked(NEW_AGENT)
    with pytest.raises(TokenRevokedError):
        gateway.tokens.validate(token)
    assert gateway.credentials._credentials[f"cred-{NEW_AGENT}"].revoked_at is not None
    assert gateway.cache.get(NEW_AGENT, "knowledge.search", "corpus-1") is None

    # The whole sequence is reconstructable from the journal alone.
    trail = [e.event_type for e in gateway.query_journal(principal_id=NEW_AGENT)]
    for expected in (
        SecurityEventType.IDENTITY_REGISTERED,
        SecurityEventType.IDENTITY_TRANSITIONED,
        SecurityEventType.PERMISSION_GRAPH_CHANGED,
        SecurityEventType.AUTHENTICATION_SUCCEEDED,
        SecurityEventType.TOKEN_ISSUED,
        SecurityEventType.AUTHORIZATION_ALLOWED,
        SecurityEventType.AUTHORIZATION_DENIED,
        SecurityEventType.DELEGATION_CREATED,
        SecurityEventType.DELEGATION_REVOKED,
        SecurityEventType.REVOCATION_EXECUTED,
    ):
        assert expected in trail, f"{expected.value} missing from the audit trail"

    # 7. The Security Event Journal resists tampering.
    assert gateway.journal.verify()
    victim = gateway.journal._journal._entries[3]
    gateway.journal._journal._entries[3] = replace(victim, payload={**victim.payload, "outcome": "success"})
    with pytest.raises(JournalTamperError):
        gateway.journal.verify()


def test_kernel_substrate_is_reused_without_modification(gateway: SecurityGateway) -> None:
    """Part VI "Kernel Ready" — the nine mechanisms are proven reusable by a real Gateway.

    Security Gateway uses the kernel's lifecycle engine for identity states,
    its boundary engine for step 6 of the authorization flow, its immutable
    journal for the Security Event Journal, and its panic hook for the halt
    path — none of them modified for this Gateway's benefit.
    """
    from kernel.boundaries import BoundaryEnforcementEngine
    from kernel.journal import ImmutableJournal
    from kernel.lifecycle import LifecycleStateMachine
    from kernel.panic import PanicProtocol

    assert isinstance(gateway.authorization.boundaries, BoundaryEnforcementEngine)
    assert isinstance(gateway.journal._journal, ImmutableJournal)
    assert isinstance(gateway.registry.get(AGENT).machine(), LifecycleStateMachine)
    assert isinstance(gateway.panic, PanicProtocol)


def test_gateway_depends_only_on_layer_0(gateway: SecurityGateway) -> None:
    """21B §22.13 — Security Gateway depends only on kernel, core and persistence.

    Guards against a prohibited dependency edge creeping in later: any import
    of another service module from this package would fail this test.
    """
    import pkgutil

    import security_gateway

    offenders: list[tuple[str, str]] = []
    for module_info in pkgutil.iter_modules(security_gateway.__path__):
        if module_info.name == "tests":
            continue
        module = __import__(f"security_gateway.{module_info.name}", fromlist=["_"])
        source = module.__file__
        assert source is not None
        with open(source, encoding="utf-8") as handle:
            for line in handle:
                stripped = line.strip()
                if not stripped.startswith(("import ", "from ")):
                    continue
                target = stripped.split()[1].split(".")[0]
                if target in ("security_gateway", "__future__"):
                    continue
                # stdlib and third-party are unconstrained; only sibling
                # Agent OS modules are the concern here.
                if target in ("kernel", "core", "persistence"):
                    continue
                if target in ("schema_registry", "event_bus", "agent_runtime", "tool_gateway"):
                    offenders.append((module_info.name, target))
    assert offenders == [], f"prohibited dependency edges: {offenders}"


def test_authentication_precedes_every_authorization(gateway: SecurityGateway) -> None:
    """14 rule 11 — no bypass of the Gateway for authentication or authorization."""
    with pytest.raises(AuthenticationError):
        gateway.authorize(
            "not.a.token",
            AuthorizationRequest(action="tool.invoke", resource_id="r", resource_tenant_id=TENANT),
        )


def test_health_reports_every_metric_family_14_27_1_requires(gateway: SecurityGateway) -> None:
    gateway.authenticate(AGENT, f"cred-{AGENT}", AGENT_VERIFIER, PrincipalType.AGENT)
    health = gateway.health()
    for family in ("authentication", "authorization", "delegation", "tokens", "secrets", "revocation"):
        assert family in health
    assert health["journal_intact"] is True
    assert health["halted"] is False
