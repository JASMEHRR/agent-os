"""Authorization Engine and Cache — unit tests (14.10, 14.12.4, 14.17)."""

from __future__ import annotations

from datetime import timedelta

import pytest

from security_gateway import (
    AuthorizationRequest,
    Decision,
    PrincipalType,
    RegistrationRequest,
    Role,
    SecurityGateway,
)
from security_gateway.enums import DelegationType, PrincipalStatus

from .conftest import AGENT, AGENT_VERIFIER, HUMAN, TENANT


def _request(**overrides: object) -> AuthorizationRequest:
    base: dict[str, object] = {
        "action": "business.content.generate",
        "resource_id": "doc-1",
        "resource_tenant_id": TENANT,
    }
    base.update(overrides)
    return AuthorizationRequest(**base)  # type: ignore[arg-type]


def test_permitted_action_is_allowed(gateway: SecurityGateway, agent_token: str) -> None:
    result = gateway.authorize(agent_token, _request())
    assert result.decision == Decision.ALLOW
    assert result.allowed


def test_action_outside_the_capability_signature_is_denied(gateway: SecurityGateway, agent_token: str) -> None:
    result = gateway.authorize(agent_token, _request(action="decision.commit"))
    assert result.decision == Decision.DENY
    assert "capability signature" in result.reason


def test_role_cannot_widen_past_the_capability_signature(gateway: SecurityGateway) -> None:
    """14.12.4 — a role grant outside the capability is intersected away, not unioned in."""
    gateway.roles.define(
        Role(
            name="over-broad",
            permissions=frozenset({"business.content.generate", "admin.everything"}),
            eligible_types=frozenset({PrincipalType.AGENT}),
        )
    )
    gateway.roles.unassign("writer", AGENT)
    gateway.roles.assign("over-broad", AGENT, PrincipalType.AGENT, assigned_by=HUMAN)
    gateway.recompute_permissions(AGENT)
    token, _ = gateway.authenticate(AGENT, f"cred-{AGENT}", AGENT_VERIFIER, PrincipalType.AGENT)
    assert "admin.everything" not in gateway.graph_engine.graph_for(AGENT).effective
    assert gateway.authorize(token, _request(action="admin.everything")).decision == Decision.DENY


def test_authorization_reads_the_live_graph_not_the_token_snapshot(gateway: SecurityGateway, agent_token: str) -> None:
    """14.9.5 — re-authentication does not imply re-authorization."""
    assert gateway.authorize(agent_token, _request()).allowed
    gateway.roles.unassign("writer", AGENT)
    gateway.capabilities.revoke(AGENT, "content.generation")
    gateway.recompute_permissions(AGENT)
    # The token still carries the old permission claim; the decision does not.
    assert gateway.authorize(agent_token, _request()).decision == Decision.DENY


def test_separation_of_duties_blocks_reviewing_own_output(gateway: SecurityGateway, agent_token: str) -> None:
    result = gateway.authorize(agent_token, _request(subject_principal_id=AGENT))
    assert result.decision == Decision.DENY
    assert "separation of duties" in result.reason


def test_cross_tenant_action_is_denied(gateway: SecurityGateway, agent_token: str) -> None:
    result = gateway.authorize(agent_token, _request(resource_tenant_id="tenant-beta"))
    assert result.decision == Decision.DENY
    assert "bilateral" in result.reason


def test_insufficient_autonomy_is_denied(gateway: SecurityGateway, agent_token: str) -> None:
    result = gateway.authorize(agent_token, _request(required_autonomy_level=4))
    assert result.decision == Decision.DENY


def test_low_confidence_escalates_rather_than_denies(gateway: SecurityGateway, agent_token: str) -> None:
    result = gateway.authorize(agent_token, _request(confidence=0.2, min_confidence=0.8))
    assert result.decision == Decision.ESCALATE
    assert result.escalate_to == "human_sovereign"


def test_anomaly_and_cross_scope_impact_escalate(gateway: SecurityGateway, agent_token: str) -> None:
    assert gateway.authorize(agent_token, _request(anomaly_flagged=True)).decision == Decision.ESCALATE
    assert gateway.authorize(agent_token, _request(cross_scope_impact=True)).decision == Decision.ESCALATE


def test_over_budget_request_is_denied(gateway: SecurityGateway) -> None:
    gateway.budget_resolver = lambda _principal: 10.0
    token, _ = gateway.authenticate(AGENT, f"cred-{AGENT}", AGENT_VERIFIER, PrincipalType.AGENT)
    assert gateway.authorize(token, _request(cost=50.0)).decision == Decision.DENY


def test_near_budget_boundary_escalates(gateway: SecurityGateway) -> None:
    gateway.budget_resolver = lambda _principal: 100.0
    token, _ = gateway.authenticate(AGENT, f"cred-{AGENT}", AGENT_VERIFIER, PrincipalType.AGENT)
    assert gateway.authorize(token, _request(cost=95.0)).decision == Decision.ESCALATE


def test_every_decision_is_journalled(gateway: SecurityGateway, agent_token: str) -> None:
    before = len(gateway.journal)
    gateway.authorize(agent_token, _request())
    gateway.authorize(agent_token, _request(action="decision.commit"))
    assert len(gateway.journal) == before + 2


def test_allow_decisions_are_cached_and_denials_are_not(gateway: SecurityGateway, agent_token: str) -> None:
    gateway.authorize(agent_token, _request())
    assert gateway.cache.size == 1
    gateway.authorize(agent_token, _request(action="decision.commit", resource_id="doc-2"))
    assert gateway.cache.size == 1


def test_cache_never_outlives_the_token(gateway: SecurityGateway, clock) -> None:
    token, claims = gateway.authenticate(
        AGENT, f"cred-{AGENT}", AGENT_VERIFIER, PrincipalType.AGENT, ttl=timedelta(minutes=10)
    )
    gateway.authorize(token, _request())
    assert gateway.cache.get(AGENT, "business.content.generate", "doc-1") is not None
    clock.advance(timedelta(minutes=11))
    assert gateway.cache.get(AGENT, "business.content.generate", "doc-1") is None


def test_revocation_invalidates_cached_decisions(gateway: SecurityGateway, agent_token: str) -> None:
    gateway.authorize(agent_token, _request())
    gateway.revocations._revocation_list.add(AGENT)
    assert gateway.cache.get(AGENT, "business.content.generate", "doc-1") is None


def test_delegated_action_outside_chain_scope_is_denied(gateway: SecurityGateway) -> None:
    gateway.register_identity(
        RegistrationRequest(
            principal_id="agent-b",
            principal_type=PrincipalType.AGENT,
            name="B",
            version="1.0.0",
            tenant_id=TENANT,
            autonomy_level=2,
            approved_by=HUMAN,
        )
    )
    gateway.change_principal_status("agent-b", PrincipalStatus.ACTIVE, actor_id=HUMAN)
    gateway.capabilities.grant("agent-b", "content.generation")
    gateway.roles.assign("writer", "agent-b", PrincipalType.AGENT, assigned_by=HUMAN)
    gateway.recompute_permissions("agent-b")
    gateway.credentials.issue("cred-agent-b", "agent-b", PrincipalType.AGENT, "hash-b")

    # A delegation lending only tool.invoke narrows what B may do under it.
    gateway.manage_delegation(
        operation="create",
        delegation_id="d1",
        actor_id=AGENT,
        delegation_type=DelegationType.TASK,
        delegatee_id="agent-b",
        permissions=("tool.invoke",),
        duration=timedelta(hours=1),
    )
    token, _ = gateway.authenticate("agent-b", "cred-agent-b", "hash-b", PrincipalType.AGENT)
    result = gateway.authorize(token, _request(action="business.content.generate"))
    # The delegation enters the permission graph as its own source, so the
    # intersection rule of 14.12.4 narrows B down to the lent scope before the
    # chain check is even reached. Either way the action does not proceed.
    assert result.decision == Decision.DENY
    assert "do not cover" in result.reason
    assert gateway.authorize(token, _request(action="tool.invoke")).allowed


def test_broken_interior_link_denies_downstream(gateway: SecurityGateway) -> None:
    """A revoked upstream link must invalidate downstream authority (14.14.4)."""
    for principal_id in ("agent-b", "agent-c"):
        gateway.register_identity(
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
        gateway.change_principal_status(principal_id, PrincipalStatus.ACTIVE, actor_id=HUMAN)
        gateway.capabilities.grant(principal_id, "content.generation")
        gateway.roles.assign("writer", principal_id, PrincipalType.AGENT, assigned_by=HUMAN)
        gateway.recompute_permissions(principal_id)
        gateway.credentials.issue(f"cred-{principal_id}", principal_id, PrincipalType.AGENT, f"hash-{principal_id}")

    gateway.manage_delegation(
        operation="create",
        delegation_id="a-to-b",
        actor_id=AGENT,
        delegation_type=DelegationType.TASK,
        delegatee_id="agent-b",
        permissions=("tool.invoke",),
        duration=timedelta(hours=4),
    )
    gateway.manage_delegation(
        operation="create",
        delegation_id="b-to-c",
        actor_id="agent-b",
        delegation_type=DelegationType.TASK,
        delegatee_id="agent-c",
        permissions=("tool.invoke",),
        duration=timedelta(hours=2),
    )
    token, _ = gateway.authenticate("agent-c", "cred-agent-c", "hash-agent-c", PrincipalType.AGENT)
    assert gateway.authorize(token, _request(action="tool.invoke")).allowed

    gateway.manage_delegation(operation="revoke", delegation_id="a-to-b", actor_id=HUMAN)
    result = gateway.authorize(token, _request(action="tool.invoke", resource_id="doc-9"))
    assert result.decision == Decision.DENY
    assert "revoked" in result.reason


def test_repeated_denials_raise_an_authorization_violation_incident(gateway: SecurityGateway, agent_token: str) -> None:
    for index in range(10):
        gateway.authorize(agent_token, _request(action="decision.commit", resource_id=f"doc-{index}"))
    assert gateway.health()["incidents"]["total"] >= 1


@pytest.mark.parametrize("action", ["business.content.generate.blog_post", "tool.invoke"])
def test_hierarchical_actions_are_covered_by_parent_grants(
    gateway: SecurityGateway, agent_token: str, action: str
) -> None:
    assert gateway.authorize(agent_token, _request(action=action)).allowed
