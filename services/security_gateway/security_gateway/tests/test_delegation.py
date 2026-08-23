"""Delegation Manager — unit tests (14.14, 14.7.4)."""

from __future__ import annotations

from datetime import timedelta

import pytest

from security_gateway import PrincipalType, RegistrationRequest, SecurityGateway
from security_gateway.delegation import (
    STANDING_ORDER_MAX_DURATION,
    BrokenChainError,
    DelegationError,
)
from security_gateway.enums import DelegationType, PrincipalStatus

from .conftest import AGENT, HUMAN, TENANT


def _register_agent(gateway: SecurityGateway, principal_id: str, permissions: set[str]) -> None:
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
    gateway.graph_engine.set_source(principal_id, "capabilities", permissions)


def test_delegation_never_exceeds_the_delegators_own_scope(gateway: SecurityGateway) -> None:
    _register_agent(gateway, "agent-b", {"tool.invoke", "business.content.generate"})
    delegation = gateway.manage_delegation(
        operation="create",
        delegation_id="d1",
        actor_id=AGENT,
        delegation_type=DelegationType.TASK,
        delegatee_id="agent-b",
        permissions=("tool.invoke", "admin.everything"),
        duration=timedelta(hours=2),
    )
    assert delegation.permissions == frozenset({"tool.invoke"})


def test_delegation_of_nothing_the_delegator_holds_is_refused(gateway: SecurityGateway) -> None:
    _register_agent(gateway, "agent-b", {"tool.invoke"})
    with pytest.raises(DelegationError, match="holds none of the requested permissions"):
        gateway.manage_delegation(
            operation="create",
            delegation_id="d1",
            actor_id=AGENT,
            delegation_type=DelegationType.TASK,
            delegatee_id="agent-b",
            permissions=("admin.everything",),
            duration=timedelta(hours=2),
        )


def test_self_delegation_is_refused(gateway: SecurityGateway) -> None:
    with pytest.raises(DelegationError, match="may not delegate to itself"):
        gateway.manage_delegation(
            operation="create",
            delegation_id="d1",
            actor_id=AGENT,
            delegation_type=DelegationType.TASK,
            delegatee_id=AGENT,
            permissions=("tool.invoke",),
            duration=timedelta(hours=1),
        )


def test_standing_orders_expire_within_thirty_days(gateway: SecurityGateway) -> None:
    _register_agent(gateway, "agent-b", {"tool.invoke"})
    with pytest.raises(DelegationError, match="30 days"):
        gateway.manage_delegation(
            operation="create",
            delegation_id="d1",
            actor_id=AGENT,
            delegation_type=DelegationType.STANDING_ORDER,
            delegatee_id="agent-b",
            permissions=("tool.invoke",),
            duration=STANDING_ORDER_MAX_DURATION + timedelta(days=1),
        )


def test_emergency_delegation_requires_a_human_authorizer(gateway: SecurityGateway) -> None:
    _register_agent(gateway, "agent-b", {"tool.invoke"})
    with pytest.raises(DelegationError, match="human authorizer"):
        gateway.manage_delegation(
            operation="create",
            delegation_id="d1",
            actor_id=AGENT,
            delegation_type=DelegationType.EMERGENCY,
            delegatee_id="agent-b",
            permissions=("tool.invoke",),
            duration=timedelta(hours=1),
        )


def test_chain_scope_is_the_intersection_of_all_three_principals(gateway: SecurityGateway) -> None:
    """14.7.4 — A delegates to B, B to C: C holds the intersection, not the union."""
    _register_agent(gateway, "agent-b", {"tool.invoke", "business.content.generate"})
    _register_agent(gateway, "agent-c", {"tool.invoke", "business.content.generate"})
    gateway.manage_delegation(
        operation="create",
        delegation_id="a-to-b",
        actor_id=AGENT,
        delegation_type=DelegationType.TASK,
        delegatee_id="agent-b",
        permissions=("tool.invoke", "business.content.generate"),
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
    scope = gateway.delegations.validate_chain("agent-c")
    assert scope == frozenset({"tool.invoke"})


def test_revoking_a_link_breaks_everything_downstream(gateway: SecurityGateway) -> None:
    _register_agent(gateway, "agent-b", {"tool.invoke"})
    _register_agent(gateway, "agent-c", {"tool.invoke"})
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
    gateway.manage_delegation(operation="revoke", delegation_id="a-to-b", actor_id=HUMAN)
    with pytest.raises(BrokenChainError):
        gateway.delegations.validate_chain("agent-c")


def test_expired_delegation_drops_out_of_the_chain(gateway: SecurityGateway, clock) -> None:
    _register_agent(gateway, "agent-b", {"tool.invoke"})
    gateway.manage_delegation(
        operation="create",
        delegation_id="d1",
        actor_id=AGENT,
        delegation_type=DelegationType.TASK,
        delegatee_id="agent-b",
        permissions=("tool.invoke",),
        duration=timedelta(hours=1),
    )
    assert gateway.delegations.live_for("agent-b")
    clock.advance(timedelta(hours=2))
    assert not gateway.delegations.live_for("agent-b")
    assert gateway.delegations.validate_chain("agent-b") == frozenset()


def test_a_suspended_delegator_breaks_the_chain(gateway: SecurityGateway) -> None:
    _register_agent(gateway, "agent-b", {"tool.invoke"})
    gateway.manage_delegation(
        operation="create",
        delegation_id="d1",
        actor_id=AGENT,
        delegation_type=DelegationType.TASK,
        delegatee_id="agent-b",
        permissions=("tool.invoke",),
        duration=timedelta(hours=4),
    )
    gateway.change_principal_status(AGENT, PrincipalStatus.SUSPENDED, actor_id=HUMAN)
    with pytest.raises(BrokenChainError, match="not an Active principal"):
        gateway.delegations.validate_chain("agent-b")


def test_a_suspended_principal_cannot_delegate(gateway: SecurityGateway) -> None:
    _register_agent(gateway, "agent-b", {"tool.invoke"})
    gateway.change_principal_status(AGENT, PrincipalStatus.SUSPENDED, actor_id=HUMAN)
    with pytest.raises(DelegationError, match="not an Active principal"):
        gateway.manage_delegation(
            operation="create",
            delegation_id="d1",
            actor_id=AGENT,
            delegation_type=DelegationType.TASK,
            delegatee_id="agent-b",
            permissions=("tool.invoke",),
            duration=timedelta(hours=1),
        )
