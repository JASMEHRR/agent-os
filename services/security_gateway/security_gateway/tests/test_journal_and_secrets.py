"""Security Event Journal tamper-evidence, Secret Governor, and Security Context.

Covers the Stage S1 test list items "tamper-evidence test on the Security
Event Journal (attempted retroactive edit must fail cryptographic chain
verification)" plus the secret non-exposure guarantee of 21B §22.15 item 5.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta

import pytest

from core.exceptions import ValidationError
from kernel.journal import JournalTamperError
from security_gateway import PrincipalType, SecurityGateway
from security_gateway.context import SecurityContextDroppedError, SecurityContextInvalidError
from security_gateway.enums import SecurityEventType
from security_gateway.secrets_governor import SecretExposureError
from security_gateway.tokens import AuthenticationError

from .conftest import AGENT, AGENT_VERIFIER, HUMAN, SERVICE, TENANT

# --------------------------------------------------------------------- journal


def test_retroactive_edit_fails_chain_verification(gateway: SecurityGateway) -> None:
    """14.13 / rule 13 — no journal modification after formation."""
    gateway.journal.record(SecurityEventType.BOUNDARY_CROSSING, AGENT, TENANT, "crossed", {"to": "ws-2"})
    assert gateway.journal.verify()

    # Reach past the public API and rewrite a committed entry, exactly as an
    # attacker with database access would.
    victim = gateway.journal._journal._entries[1]
    forged = replace(victim, payload={**victim.payload, "outcome": "never happened"})
    gateway.journal._journal._entries[1] = forged

    with pytest.raises(JournalTamperError):
        gateway.journal.verify()


def test_journal_is_append_only_and_ordered(gateway: SecurityGateway) -> None:
    before = len(gateway.journal)
    gateway.journal.record(SecurityEventType.BOUNDARY_CROSSING, AGENT, TENANT, "crossed")
    gateway.journal.record(SecurityEventType.BOUNDARY_CROSSING, AGENT, TENANT, "crossed")
    assert len(gateway.journal) == before + 2
    seqs = [e.seq for e in gateway.query_journal(principal_id=AGENT)]
    assert seqs == sorted(seqs)


def test_journal_query_filters_by_principal_type_and_time(gateway: SecurityGateway) -> None:
    gateway.journal.record(SecurityEventType.BOUNDARY_CROSSING, AGENT, TENANT, "crossed")
    assert gateway.query_journal(event_type=SecurityEventType.BOUNDARY_CROSSING)
    assert not gateway.query_journal(principal_id="nobody")
    assert not gateway.query_journal(tenant_id="tenant-beta")


def test_retention_is_seven_years(gateway: SecurityGateway) -> None:
    event = gateway.journal.record(SecurityEventType.BOUNDARY_CROSSING, AGENT, TENANT, "crossed")
    assert (event.retain_until - event.recorded_at).days >= 365 * 7


def test_journal_writes_reach_persistence_not_an_event_bus(gateway: SecurityGateway) -> None:
    """14.26.1 — the journal is written directly to persistence."""
    gateway.journal.record(SecurityEventType.BOUNDARY_CROSSING, AGENT, TENANT, "crossed")
    stored = gateway.journal._repo.list_all()
    assert len(stored) == len(gateway.journal)


# --------------------------------------------------------------------- secrets


def test_gateway_exposes_no_method_returning_a_secret_value(gateway: SecurityGateway) -> None:
    """21B §22.10 — there is no interface by which any consumer retrieves a value."""
    forbidden = {"get_secret", "read_secret", "secret_value", "resolve_secret_value", "reveal"}
    assert forbidden.isdisjoint(dir(gateway))
    assert forbidden.isdisjoint(dir(gateway.secrets))


def test_injection_grant_carries_a_reference_never_a_value(gateway: SecurityGateway, store) -> None:
    gateway.secrets.register("api/openai", "sk-not-a-real-key", TENANT, HUMAN)
    grant = gateway.resolve_secret_reference("api/openai", "sandbox-1", "inv-1", SERVICE)
    assert grant.reference == "api/openai"
    assert "sk-not-a-real-key" not in repr(grant)


def test_an_agent_may_never_receive_a_grant(gateway: SecurityGateway) -> None:
    """Rule 12 — no secret value exposed to an agent or workflow."""
    from security_gateway.enforcer import ConstitutionalViolationError

    gateway.secrets.register("api/openai", "sk-not-a-real-key", TENANT, HUMAN)
    with pytest.raises(ConstitutionalViolationError):
        gateway.resolve_secret_reference("api/openai", "sandbox-1", "inv-1", AGENT)


def test_injection_hands_the_value_to_the_sandbox_and_nowhere_else(gateway: SecurityGateway) -> None:
    gateway.secrets.register("api/openai", "sk-not-a-real-key", TENANT, HUMAN)
    grant = gateway.resolve_secret_reference("api/openai", "sandbox-1", "inv-1", SERVICE)
    injected: dict[str, str] = {}
    gateway.secrets.inject(grant, lambda sandbox, value: injected.__setitem__(sandbox, value))
    assert injected == {"sandbox-1": "sk-not-a-real-key"}
    # And the value is nowhere in the journal.
    assert all("sk-not-a-real-key" not in str(e.detail) for e in gateway.query_journal())


def test_a_grant_is_single_use(gateway: SecurityGateway) -> None:
    gateway.secrets.register("api/openai", "sk-not-a-real-key", TENANT, HUMAN)
    grant = gateway.resolve_secret_reference("api/openai", "sandbox-1", "inv-1", SERVICE)
    gateway.secrets.inject(grant, lambda _s, _v: None)
    with pytest.raises(SecretExposureError, match="already been redeemed"):
        gateway.secrets.inject(grant, lambda _s, _v: None)


def test_expired_grant_is_refused(gateway: SecurityGateway, clock) -> None:
    gateway.secrets.register("api/openai", "sk-not-a-real-key", TENANT, HUMAN)
    grant = gateway.resolve_secret_reference("api/openai", "sandbox-1", "inv-1", SERVICE)
    clock.advance(timedelta(minutes=10))
    with pytest.raises(ValidationError, match="expired"):
        gateway.secrets.inject(grant, lambda _s, _v: None)


def test_rotation_registers_the_new_value_before_retiring_the_old(gateway: SecurityGateway, clock) -> None:
    gateway.secrets.register("api/openai", "old-value", TENANT, HUMAN, rotates_after=timedelta(days=1))
    clock.advance(timedelta(days=2))
    assert gateway.secrets.rotation_due()
    gateway.secrets.rotate("api/openai", "new-value")
    assert not gateway.secrets.rotation_due()
    grant = gateway.resolve_secret_reference("api/openai", "sandbox-2", "inv-2", SERVICE)
    seen: list[str] = []
    gateway.secrets.inject(grant, lambda _s, value: seen.append(value))
    assert seen == ["new-value"]


def test_rotation_invalidates_outstanding_grants(gateway: SecurityGateway) -> None:
    gateway.secrets.register("api/openai", "old-value", TENANT, HUMAN)
    stale = gateway.resolve_secret_reference("api/openai", "sandbox-1", "inv-1", SERVICE)
    gateway.secrets.rotate("api/openai", "new-value")
    with pytest.raises(ValidationError, match="not issued by this Gateway"):
        gateway.secrets.inject(stale, lambda _s, _v: None)


def test_retired_secret_cannot_be_injected(gateway: SecurityGateway) -> None:
    gateway.secrets.register("api/openai", "value", TENANT, HUMAN)
    gateway.secrets.retire("api/openai")
    with pytest.raises(ValidationError, match="retired"):
        gateway.resolve_secret_reference("api/openai", "sandbox-1", "inv-1", SERVICE)


# --------------------------------------------------------------------- context


def test_context_may_never_be_dropped(gateway: SecurityGateway) -> None:
    with pytest.raises(SecurityContextDroppedError):
        gateway.validate_security_context(None, "tool.invoke")


def test_context_is_immutable_for_one_action(gateway: SecurityGateway, agent_token: str) -> None:
    claims = gateway.tokens.validate(agent_token)
    context = gateway.create_security_context(claims, trace_id="trace-1")
    tampered = replace(context, principal_id="someone-else")
    with pytest.raises(SecurityContextInvalidError):
        gateway.validate_security_context(tampered, "tool.invoke")


def test_unissued_context_is_an_anonymous_action(gateway: SecurityGateway) -> None:
    from datetime import UTC, datetime

    from security_gateway.context import SecurityContext

    forged = SecurityContext(
        action_id="act-forged",
        principal_id=AGENT,
        principal_type=PrincipalType.AGENT,
        tenant_id=TENANT,
        token_id="tok",
        workspace_id=None,
        delegation_chain=(),
        trace_id="t",
        created_at=datetime.now(UTC),
    )
    with pytest.raises(SecurityContextInvalidError, match="anonymous"):
        gateway.validate_security_context(forged, "tool.invoke")


def test_derived_context_preserves_attribution_without_widening(gateway: SecurityGateway, agent_token: str) -> None:
    claims = gateway.tokens.validate(agent_token)
    parent = gateway.create_security_context(claims, trace_id="trace-1")
    child = gateway.contexts.register_derived(parent.derive("act-child"))
    assert child.parent_action_id == parent.action_id
    assert child.principal_id == parent.principal_id
    assert child.tenant_id == parent.tenant_id
    assert child.delegation_chain == parent.delegation_chain
    gateway.validate_security_context(child, "tool.invoke")


def test_authentication_still_journals_when_credential_is_unknown(gateway: SecurityGateway) -> None:
    with pytest.raises(AuthenticationError):
        gateway.authenticate(AGENT, "cred-nonexistent", AGENT_VERIFIER, PrincipalType.AGENT)
    assert gateway.health()["authentication"]["failed"] == 1
