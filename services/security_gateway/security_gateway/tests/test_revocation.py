"""Revocation Engine — unit and failure-domain tests (14.15)."""

from __future__ import annotations

from datetime import timedelta

import pytest

from security_gateway import PrincipalType, RegistrationRequest, SecurityGateway
from security_gateway.enums import DelegationType, PrincipalStatus, RevocationTrigger
from security_gateway.revocation import PartialRevocationError
from security_gateway.tokens import TokenRevokedError

from .conftest import AGENT, AGENT_VERIFIER, HUMAN, TENANT


def _delegatee(gateway: SecurityGateway, principal_id: str = "agent-b") -> str:
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
    gateway.recompute_permissions(principal_id)
    return principal_id


def test_revocation_cascades_to_tokens_delegations_and_credentials(gateway: SecurityGateway) -> None:
    delegatee = _delegatee(gateway)
    token, _ = gateway.authenticate(AGENT, f"cred-{AGENT}", AGENT_VERIFIER, PrincipalType.AGENT)
    gateway.manage_delegation(
        operation="create",
        delegation_id="d1",
        actor_id=AGENT,
        delegation_type=DelegationType.TASK,
        delegatee_id=delegatee,
        permissions=("tool.invoke",),
        duration=timedelta(hours=2),
    )

    record = gateway.revoke(
        principal_id=AGENT,
        revoker_id=HUMAN,
        trigger=RevocationTrigger.HUMAN_COMMAND,
        reason="operator command",
    )

    assert "d1" in record.delegations_revoked
    assert gateway.delegations.get("d1").revoked_at is not None
    assert gateway.revocations.is_revoked(AGENT)
    with pytest.raises(TokenRevokedError):
        gateway.tokens.validate(token)
    assert gateway.credentials._credentials[f"cred-{AGENT}"].revoked_at is not None
    assert gateway.graph_engine.graph_for(AGENT).effective == frozenset()


def test_every_registered_subsystem_must_acknowledge(gateway: SecurityGateway) -> None:
    acknowledged: list[str] = []
    for name in ("runtime", "agent", "tool", "memory", "decision"):

        def _ack(_principal_id: str, subsystem: str = name) -> bool:
            acknowledged.append(subsystem)
            return True

        gateway.revocations.register_target(name, _ack)
    record = gateway.revoke(AGENT, HUMAN, RevocationTrigger.SUSPENSION, "anomaly")
    assert sorted(record.cascaded_to) == ["agent", "decision", "memory", "runtime", "tool"]
    assert sorted(acknowledged) == ["agent", "decision", "memory", "runtime", "tool"]


def test_partial_revocation_is_a_system_failure(gateway: SecurityGateway) -> None:
    """14.15.3 — partial revocation is treated as a system failure and alerted."""
    gateway.revocations.register_target("runtime", lambda _pid: True)
    gateway.revocations.register_target("tool", lambda _pid: False)
    with pytest.raises(PartialRevocationError, match="system failure"):
        gateway.revoke(AGENT, HUMAN, RevocationTrigger.ANOMALY_DETECTION, "drift")
    # The failure is alerted, not swallowed.
    assert gateway.health()["revocation"]["partial"] == 1
    assert gateway.health()["incidents"]["total"] >= 1


def test_a_raising_target_counts_as_unacknowledged(gateway: SecurityGateway) -> None:
    def explode(_principal_id: str) -> bool:
        raise RuntimeError("subsystem unreachable")

    gateway.revocations.register_target("memory", explode)
    with pytest.raises(PartialRevocationError):
        gateway.revoke(AGENT, HUMAN, RevocationTrigger.HUMAN_COMMAND, "test")


def test_local_effects_apply_even_when_propagation_fails(gateway: SecurityGateway) -> None:
    """The Gateway must never keep honouring authority it has been told to revoke."""
    token, _ = gateway.authenticate(AGENT, f"cred-{AGENT}", AGENT_VERIFIER, PrincipalType.AGENT)
    gateway.revocations.register_target("tool", lambda _pid: False)
    with pytest.raises(PartialRevocationError):
        gateway.revoke(AGENT, HUMAN, RevocationTrigger.HUMAN_COMMAND, "test")
    with pytest.raises(TokenRevokedError):
        gateway.tokens.validate(token)


def test_revocation_list_is_broadcast_for_cache_validation(gateway: SecurityGateway) -> None:
    gateway.revoke(AGENT, HUMAN, RevocationTrigger.RETIREMENT, "retired")
    assert AGENT in gateway.revocations.revocation_list


def test_reinstatement_clears_the_revocation_list_entry(gateway: SecurityGateway) -> None:
    gateway.revoke(AGENT, HUMAN, RevocationTrigger.SUSPENSION, "review")
    gateway.change_principal_status(AGENT, PrincipalStatus.SUSPENDED, actor_id=HUMAN)
    gateway.change_principal_status(AGENT, PrincipalStatus.ACTIVE, actor_id=HUMAN)
    assert not gateway.revocations.is_revoked(AGENT)


def test_revocation_is_logged_with_everything_14_15_5_requires(gateway: SecurityGateway) -> None:
    record = gateway.revoke(AGENT, HUMAN, RevocationTrigger.CONSTITUTIONAL_VIOLATION, "rule breach")
    entries = gateway.query_journal(principal_id=AGENT)
    logged = [e for e in entries if e.event_type.value == "revocation.executed"]
    assert len(logged) == 1
    detail = logged[0].detail
    assert detail["revoker_id"] == HUMAN
    assert detail["trigger"] == RevocationTrigger.CONSTITUTIONAL_VIOLATION.value
    assert detail["reason"] == "rule breach"
    assert detail["scope"]
    assert record.revoked_at is not None
