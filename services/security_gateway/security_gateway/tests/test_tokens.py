"""Token Service — unit tests (14.9)."""

from __future__ import annotations

from datetime import timedelta

import pytest

from core.exceptions import ValidationError
from security_gateway import PrincipalType, SecurityGateway
from security_gateway.enums import PrincipalStatus
from security_gateway.tokens import (
    MAX_TOKEN_TTL,
    AuthenticationError,
    TokenExpiredError,
    TokenRevokedError,
    TokenService,
)

from .conftest import AGENT, AGENT_VERIFIER, HUMAN, HUMAN_VERIFIER, Clock


def _service(clock: Clock) -> TokenService:
    return TokenService(signing_key=b"unit-test-key", now=clock)


def _claims() -> dict[str, object]:
    return {
        "principal_id": "p1",
        "principal_version": "1.0.0",
        "principal_type": PrincipalType.AGENT,
        "tenant_id": "t1",
        "autonomy_level": 2,
        "roles": ("writer",),
        "standing_order_refs": (),
        "permissions": ("tool.invoke",),
        "workspace_ids": ("ws1",),
        "budget_remaining": 100.0,
        "task_timeout_seconds": 300,
        "max_retries": 3,
        "delegation_window_ends_at": None,
    }


def test_ttl_may_not_exceed_one_hour(clock: Clock) -> None:
    service = _service(clock)
    with pytest.raises(ValidationError, match="one-hour maximum"):
        service.issue(_claims(), ttl=timedelta(hours=1, seconds=1))


def test_token_round_trips_every_claim_group(clock: Clock) -> None:
    service = _service(clock)
    token, issued = service.issue(_claims())
    validated = service.validate(token)
    assert validated == issued
    assert validated.expires_at - validated.issued_at == MAX_TOKEN_TTL


def test_modified_token_fails_integrity_check(clock: Clock) -> None:
    service = _service(clock)
    token, _ = service.issue(_claims())
    body, signature = token.split(".", 1)
    tampered = f"{body[:-2]}XY.{signature}"
    with pytest.raises(AuthenticationError):
        service.validate(tampered)


def test_token_from_another_issuer_is_rejected(clock: Clock) -> None:
    mine = _service(clock)
    theirs = TokenService(signing_key=b"a-different-key", now=clock)
    forged, _ = theirs.issue(_claims())
    with pytest.raises(AuthenticationError, match="not issued by this Gateway"):
        mine.validate(forged)


def test_expired_token_is_rejected(clock: Clock) -> None:
    service = _service(clock)
    token, _ = service.issue(_claims(), ttl=timedelta(minutes=30))
    clock.advance(timedelta(minutes=31))
    with pytest.raises(TokenExpiredError):
        service.validate(token)


def test_revoking_a_principal_invalidates_its_outstanding_tokens(clock: Clock) -> None:
    service = _service(clock)
    token, _ = service.issue(_claims())
    service.revoke_principal("p1")
    with pytest.raises(TokenRevokedError):
        service.validate(token)


def test_rotation_issues_a_successor_and_retires_the_old_token(clock: Clock) -> None:
    service = _service(clock)
    token, original = service.issue(_claims())
    clock.advance(timedelta(minutes=5))
    rotated_token, rotated = service.rotate(token)
    assert rotated.token_id != original.token_id
    assert rotated.permissions == original.permissions
    assert service.validate(rotated_token).token_id == rotated.token_id
    with pytest.raises(TokenRevokedError):
        service.validate(token)


def test_empty_signing_key_is_refused() -> None:
    with pytest.raises(ValidationError):
        TokenService(signing_key=b"")


def test_authentication_requires_an_active_principal(gateway: SecurityGateway) -> None:
    from security_gateway.enforcer import ConstitutionalViolationError

    gateway.change_principal_status(AGENT, PrincipalStatus.SUSPENDED, actor_id=HUMAN)
    with pytest.raises(ConstitutionalViolationError):
        gateway.authenticate(AGENT, f"cred-{AGENT}", AGENT_VERIFIER, PrincipalType.AGENT)


def test_wrong_credential_is_rejected_and_journalled(gateway: SecurityGateway) -> None:
    with pytest.raises(AuthenticationError):
        gateway.authenticate(AGENT, f"cred-{AGENT}", "wrong-hash", PrincipalType.AGENT)
    assert gateway.health()["authentication"]["failed"] == 1


def test_issued_token_carries_the_scoped_claims_of_14_9_3(gateway: SecurityGateway) -> None:
    _, claims = gateway.authenticate(
        AGENT, f"cred-{AGENT}", AGENT_VERIFIER, PrincipalType.AGENT, workspace_ids=("ws-1",)
    )
    assert claims.principal_id == AGENT
    assert claims.autonomy_level == 2
    assert claims.roles == ("writer",)
    assert "tool.invoke" in claims.permissions
    assert claims.workspace_ids == ("ws-1",)


def test_a_service_may_not_authenticate_with_a_human_credential(gateway: SecurityGateway) -> None:
    from security_gateway.enforcer import ConstitutionalViolationError

    with pytest.raises(ConstitutionalViolationError, match="human credential"):
        gateway.authenticate(HUMAN, f"cred-{HUMAN}", HUMAN_VERIFIER, PrincipalType.SERVICE)
