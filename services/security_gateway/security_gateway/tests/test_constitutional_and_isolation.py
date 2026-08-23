"""Constitutional Enforcer, Isolation Enforcer, Panic participation.

These are the adversarial tests: each one attempts the thing a non-violable
rule forbids and asserts the attempt fails closed rather than degrading.
"""

from __future__ import annotations

from datetime import timedelta

import pytest

from core.exceptions import AgentOSError
from security_gateway import PrincipalType, RegistrationRequest, SecurityGateway
from security_gateway.enforcer import ConstitutionalEnforcer, ConstitutionalViolationError
from security_gateway.enums import IncidentCategory, PrincipalStatus
from security_gateway.gateway import GatewayHaltedError
from security_gateway.isolation import IsolationBreachError, IsolationEnforcer
from security_gateway.tokens import TokenRevokedError

from .conftest import AGENT, HUMAN, SERVICE, TENANT

OTHER_TENANT = "tenant-beta"


# ------------------------------------------------------------ constitutional


def test_anonymous_action_is_a_violation() -> None:
    enforcer = ConstitutionalEnforcer()
    with pytest.raises(ConstitutionalViolationError) as exc:
        enforcer.require_registered_identity(None, False, False)
    assert exc.value.rule == "R14"


def test_unregistered_principal_may_not_act() -> None:
    enforcer = ConstitutionalEnforcer()
    with pytest.raises(ConstitutionalViolationError) as exc:
        enforcer.require_registered_identity("ghost", False, False)
    assert exc.value.rule == "R1"


def test_self_escalation_is_a_violation() -> None:
    enforcer = ConstitutionalEnforcer()
    with pytest.raises(ConstitutionalViolationError) as exc:
        enforcer.reject_self_escalation(AGENT, AGENT, "autonomy level")
    assert exc.value.rule == "R3"


def test_class_d_decision_cannot_be_auto_approved_on_timeout() -> None:
    """Structural, not configurable — there is no route from timeout to approval."""
    enforcer = ConstitutionalEnforcer()
    with pytest.raises(ConstitutionalViolationError) as exc:
        enforcer.reject_auto_approval(AGENT, "D", "dec-1")
    assert exc.value.rule == "R_AUTOAPPROVE"


def test_security_subsystem_change_requires_human_ratification() -> None:
    enforcer = ConstitutionalEnforcer()
    with pytest.raises(ConstitutionalViolationError) as exc:
        enforcer.require_human_ratification("permission model", ratified_by=SERVICE, ratifier_is_human=False)
    assert exc.value.rule == "R19"
    enforcer.require_human_ratification("permission model", ratified_by=HUMAN, ratifier_is_human=True)


def test_secret_may_not_be_written_to_a_journal_or_log() -> None:
    enforcer = ConstitutionalEnforcer()
    for sink in ("journal", "log", "trace", "decision_journal"):
        with pytest.raises(ConstitutionalViolationError) as exc:
            enforcer.reject_secret_exposure(PrincipalType.SERVICE, sink, SERVICE)
        assert exc.value.rule == "R12"


def test_violation_response_suspends_preserves_evidence_and_escalates(gateway: SecurityGateway) -> None:
    """14.33.3 — block, suspend, preserve evidence, alert, Category 1; no appeal."""
    error = ConstitutionalViolationError("R3", AGENT, "attempted to raise its own autonomy", {"from": 2, "to": 4})
    incident = gateway.report_constitutional_violation(error, TENANT)

    assert incident.category == IncidentCategory.CONSTITUTIONAL_VIOLATION
    assert incident.is_category_1
    assert incident.requires_suspension
    assert incident.evidence["rule"] == "R3"
    assert incident.evidence["from"] == 2
    assert gateway.registry.get(AGENT).status == PrincipalStatus.SUSPENDED
    assert "escalate_category_1" in incident.responses


def test_suspended_principal_cannot_authorize_anything(gateway: SecurityGateway, agent_token: str) -> None:
    from security_gateway.authorization import AuthorizationRequest

    gateway.change_principal_status(AGENT, PrincipalStatus.SUSPENDED, actor_id=HUMAN)
    with pytest.raises(TokenRevokedError):
        gateway.authorize(
            agent_token,
            AuthorizationRequest(action="tool.invoke", resource_id="r", resource_tenant_id=TENANT),
        )


# ------------------------------------------------------------------ isolation


def test_cross_tenant_access_is_denied_by_default(gateway: SecurityGateway) -> None:
    with pytest.raises(IsolationBreachError):
        gateway.isolation.check("tenant", TENANT, OTHER_TENANT)


def test_cross_tenant_grant_requires_two_distinct_humans(gateway: SecurityGateway) -> None:
    with pytest.raises(AgentOSError, match="two distinct humans"):
        gateway.isolation.grant("tenant", TENANT, OTHER_TENANT, HUMAN, HUMAN, timedelta(hours=1))


def test_cross_tenant_grant_approvers_must_be_human(gateway: SecurityGateway) -> None:
    with pytest.raises(AgentOSError, match="not a Human"):
        gateway.isolation.grant("tenant", TENANT, OTHER_TENANT, HUMAN, AGENT, timedelta(hours=1))


def test_bilateral_grant_permits_the_crossing_until_it_expires(gateway: SecurityGateway, clock) -> None:
    gateway.register_identity(
        RegistrationRequest(
            principal_id="human-beta",
            principal_type=PrincipalType.HUMAN,
            name="Beta Sovereign",
            version="1.0.0",
            tenant_id=OTHER_TENANT,
            approved_by=HUMAN,
        )
    )
    gateway.isolation.grant("tenant", TENANT, OTHER_TENANT, HUMAN, "human-beta", timedelta(hours=1))
    assert gateway.isolation.is_permitted("tenant", TENANT, OTHER_TENANT)
    clock.advance(timedelta(hours=2))
    assert not gateway.isolation.is_permitted("tenant", TENANT, OTHER_TENANT)


def test_same_boundary_access_needs_no_grant() -> None:
    enforcer = IsolationEnforcer(is_human=lambda _p: True)
    enforcer.check("workspace", "ws-1", "ws-1")


# ---------------------------------------------------------------------- panic


def test_panic_halts_issuance_and_authorization(gateway: SecurityGateway, agent_token: str) -> None:
    from security_gateway.authorization import AuthorizationRequest

    elapsed = gateway.panic.trigger()
    assert elapsed < 5.0  # the constitutionally mandated bound
    assert gateway.panic.tripped
    with pytest.raises(GatewayHaltedError):
        gateway.authorize(
            agent_token,
            AuthorizationRequest(action="tool.invoke", resource_id="r", resource_tenant_id=TENANT),
        )
    with pytest.raises(GatewayHaltedError):
        gateway.authenticate(AGENT, f"cred-{AGENT}", "hash-agent", PrincipalType.AGENT)


def test_panic_clears_the_authorization_cache(gateway: SecurityGateway, agent_token: str) -> None:
    from security_gateway.authorization import AuthorizationRequest

    gateway.authorize(
        agent_token,
        AuthorizationRequest(action="business.content.generate", resource_id="doc-1", resource_tenant_id=TENANT),
    )
    assert gateway.cache.size == 1
    gateway.panic.trigger()
    assert gateway.cache.size == 0
