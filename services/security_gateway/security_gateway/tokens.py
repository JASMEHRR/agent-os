"""Authentication Engine and Token Service (21B §22.3, realizes 14.9).

Tokens are short-lived, scoped, HMAC-signed bearer claims. Three rules from
14.9 shape the implementation:

- Maximum TTL is one hour (14.9.2). The service refuses to mint anything
  longer; the ceiling is not configurable upward.
- Claims are a *snapshot* of the permission graph at issuance (14.9.3), and
  authorization deliberately does **not** trust that snapshot (14.9.5) — the
  Authorization Engine re-reads the live graph. The claims exist for scope
  pre-filtering and for forensics, not as an authority of record.
- The Gateway is the sole issuer and validator (14.9.2). There is no
  verification path that does not go through this service.

Signing material is supplied by the caller and never defaulted to a literal.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
from base64 import urlsafe_b64decode, urlsafe_b64encode
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from core.exceptions import ValidationError
from security_gateway.enums import PrincipalType

#: 14.9.2 — "Tokens have a maximum time-to-live of one hour."
MAX_TOKEN_TTL = timedelta(hours=1)


class AuthenticationError(ValidationError):
    """Credential verification failed, or the presented token is not usable."""


class TokenExpiredError(AuthenticationError):
    pass


class TokenRevokedError(AuthenticationError):
    pass


@dataclass(frozen=True)
class TokenClaims:
    """The claim set of 14.9.3, grouped as that section groups it."""

    # Identity claims
    principal_id: str
    principal_version: str
    principal_type: PrincipalType
    tenant_id: str
    # Authority claims
    autonomy_level: int | None
    roles: tuple[str, ...]
    standing_order_refs: tuple[str, ...]
    # Resource claims
    permissions: tuple[str, ...]
    workspace_ids: tuple[str, ...]
    # Constraint claims
    budget_remaining: float
    task_timeout_seconds: int
    max_retries: int
    # Temporal claims
    issued_at: datetime
    expires_at: datetime
    delegation_window_ends_at: datetime | None
    token_id: str

    def to_payload(self) -> dict[str, Any]:
        return {
            "principal_id": self.principal_id,
            "principal_version": self.principal_version,
            "principal_type": self.principal_type.value,
            "tenant_id": self.tenant_id,
            "autonomy_level": self.autonomy_level,
            "roles": list(self.roles),
            "standing_order_refs": list(self.standing_order_refs),
            "permissions": list(self.permissions),
            "workspace_ids": list(self.workspace_ids),
            "budget_remaining": self.budget_remaining,
            "task_timeout_seconds": self.task_timeout_seconds,
            "max_retries": self.max_retries,
            "issued_at": self.issued_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "delegation_window_ends_at": (
                self.delegation_window_ends_at.isoformat() if self.delegation_window_ends_at else None
            ),
            "token_id": self.token_id,
        }

    @staticmethod
    def from_payload(payload: dict[str, Any]) -> TokenClaims:
        window = payload["delegation_window_ends_at"]
        return TokenClaims(
            principal_id=payload["principal_id"],
            principal_version=payload["principal_version"],
            principal_type=PrincipalType(payload["principal_type"]),
            tenant_id=payload["tenant_id"],
            autonomy_level=payload["autonomy_level"],
            roles=tuple(payload["roles"]),
            standing_order_refs=tuple(payload["standing_order_refs"]),
            permissions=tuple(payload["permissions"]),
            workspace_ids=tuple(payload["workspace_ids"]),
            budget_remaining=payload["budget_remaining"],
            task_timeout_seconds=payload["task_timeout_seconds"],
            max_retries=payload["max_retries"],
            issued_at=datetime.fromisoformat(payload["issued_at"]),
            expires_at=datetime.fromisoformat(payload["expires_at"]),
            delegation_window_ends_at=datetime.fromisoformat(window) if window else None,
            token_id=payload["token_id"],
        )


@dataclass
class TokenService:
    """Scoped claim assembly, signing, validation and rotation (21B §22.3).

    `signing_key` is injected — there is no default and no literal in source,
    so a git-secrets/Bandit scan has nothing to find and a deployment cannot
    accidentally ship a shared development key.
    """

    signing_key: bytes
    now: Callable[[], datetime] = field(default=lambda: datetime.now(UTC))
    _revoked_token_ids: set[str] = field(default_factory=set, init=False)
    _revoked_principals: set[str] = field(default_factory=set, init=False)

    def __post_init__(self) -> None:
        if not self.signing_key:
            raise ValidationError("TokenService requires a non-empty signing key")

    def issue(self, claims_without_temporal: dict[str, Any], ttl: timedelta = MAX_TOKEN_TTL) -> tuple[str, TokenClaims]:
        if ttl > MAX_TOKEN_TTL:
            raise ValidationError(f"requested TTL {ttl} exceeds the one-hour maximum of 14.9.2")
        if ttl <= timedelta(0):
            raise ValidationError("token TTL must be positive")
        issued_at = self.now()
        claims = TokenClaims(
            issued_at=issued_at,
            expires_at=issued_at + ttl,
            token_id=secrets.token_urlsafe(16),
            **claims_without_temporal,
        )
        return self._sign(claims), claims

    def validate(self, token: str) -> TokenClaims:
        """Runs all five checks of 14.9.4 in order; any failure rejects outright."""
        claims = self._verify_signature(token)  # authenticity + integrity
        now = self.now()
        if now >= claims.expires_at:
            raise TokenExpiredError(f"token expired at {claims.expires_at.isoformat()}")
        if claims.token_id in self._revoked_token_ids or claims.principal_id in self._revoked_principals:
            raise TokenRevokedError(f"token for principal '{claims.principal_id}' has been revoked")
        return claims

    def rotate(self, token: str, ttl: timedelta = MAX_TOKEN_TTL) -> tuple[str, TokenClaims]:
        """Automatic rotation (14.9.2): mints a successor and retires the presented token."""
        claims = self.validate(token)
        payload = claims.to_payload()
        for temporal in ("issued_at", "expires_at", "token_id"):
            payload.pop(temporal)
        payload["principal_type"] = PrincipalType(payload["principal_type"])
        payload["roles"] = tuple(payload["roles"])
        payload["standing_order_refs"] = tuple(payload["standing_order_refs"])
        payload["permissions"] = tuple(payload["permissions"])
        payload["workspace_ids"] = tuple(payload["workspace_ids"])
        window = payload["delegation_window_ends_at"]
        payload["delegation_window_ends_at"] = datetime.fromisoformat(window) if window else None
        new_token, new_claims = self.issue(payload, ttl=ttl)
        self._revoked_token_ids.add(claims.token_id)
        return new_token, new_claims

    def revoke_token(self, token_id: str) -> None:
        self._revoked_token_ids.add(token_id)

    def revoke_principal(self, principal_id: str) -> None:
        """Invalidates every outstanding token for a principal (14.9.2, 14.15.3)."""
        self._revoked_principals.add(principal_id)

    def reinstate_principal(self, principal_id: str) -> None:
        """Clears the principal-level block on reactivation (14.8.3 Suspended -> Active)."""
        self._revoked_principals.discard(principal_id)

    def is_revoked(self, claims: TokenClaims) -> bool:
        return claims.token_id in self._revoked_token_ids or claims.principal_id in self._revoked_principals

    def _sign(self, claims: TokenClaims) -> str:
        body = json.dumps(claims.to_payload(), sort_keys=True).encode("utf-8")
        encoded = urlsafe_b64encode(body).decode("ascii")
        signature = hmac.new(self.signing_key, encoded.encode("ascii"), hashlib.sha256).hexdigest()
        return f"{encoded}.{signature}"

    def _verify_signature(self, token: str) -> TokenClaims:
        try:
            encoded, signature = token.split(".", 1)
            body = urlsafe_b64decode(encoded.encode("ascii"))
        except (ValueError, UnicodeDecodeError) as exc:
            raise AuthenticationError("token is malformed") from exc
        expected = hmac.new(self.signing_key, encoded.encode("ascii"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, signature):
            raise AuthenticationError("token signature is invalid — not issued by this Gateway, or modified since")
        return TokenClaims.from_payload(json.loads(body))
