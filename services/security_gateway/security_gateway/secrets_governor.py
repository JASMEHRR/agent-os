"""Secret Governor and Credential Governor (21B §22.3, realizes 14.22 / 14.23).

The construction constraint from 21B §22.10 is the whole design: "The Gateway
holds the only path to secret values, and consumers never traverse it. The
Secret Governor authorizes the Tool Executor to inject; it does not return
values to requesters. **There is no interface by which any consumer retrieves
a secret value.**"

So this module deliberately exposes no method returning a secret value. It
holds metadata and references. Values live behind a `SecretStore` port whose
only consumer is the sandbox injector, which receives an injection grant —
never the value in a return position a caller could log.

Module is named `secrets_governor` rather than `secrets` so it cannot shadow
the stdlib `secrets` module the Token Service depends on.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Protocol

from core.exceptions import NotFoundError, ValidationError
from security_gateway.enums import Classification, PrincipalType


class SecretExposureError(ValidationError):
    """An operation would place a secret value where a principal could read it."""


class SecretStore(Protocol):
    """Port to the external secret store (Docker Secrets / Vault per the canonical stack).

    Implemented outside this module. The Gateway never calls `read` on behalf
    of a requester — only on behalf of a sandbox injection it has authorized.
    """

    def read(self, reference: str) -> str: ...

    def write(self, reference: str, value: str) -> None: ...


@dataclass(frozen=True)
class SecretMetadata:
    """Everything about a secret *except* its value (21B §22.7)."""

    reference: str
    tenant_id: str
    owner_principal_id: str
    classification: Classification
    created_at: datetime
    rotates_after: timedelta
    last_rotated_at: datetime
    retired_at: datetime | None = None

    @property
    def rotation_due_at(self) -> datetime:
        return self.last_rotated_at + self.rotates_after

    def is_rotation_due(self, now: datetime) -> bool:
        return now >= self.rotation_due_at


@dataclass(frozen=True)
class InjectionGrant:
    """Authorization for the Tool Executor to inject a secret into one sandbox.

    Carries a reference and a sandbox id — never a value. The grant is
    single-use and bound to one invocation.
    """

    grant_id: str
    reference: str
    sandbox_id: str
    invocation_id: str
    granted_to: str
    expires_at: datetime


@dataclass
class SecretGovernor:
    """Secret lifecycle: creation, registration, injection authorization, rotation, retirement."""

    store: SecretStore
    now: Callable[[], datetime] = field(default=lambda: datetime.now(UTC))
    _metadata: dict[str, SecretMetadata] = field(default_factory=dict, init=False)
    _grants: dict[str, InjectionGrant] = field(default_factory=dict, init=False)
    _consumed: set[str] = field(default_factory=set, init=False)
    _grant_seq: int = field(default=0, init=False)

    def register(
        self,
        reference: str,
        value: str,
        tenant_id: str,
        owner_principal_id: str,
        rotates_after: timedelta = timedelta(days=90),
        classification: Classification = Classification.RESTRICTED,
    ) -> SecretMetadata:
        """Writes the value straight through to the store and keeps only metadata."""
        if reference in self._metadata:
            raise ValidationError(f"secret '{reference}' is already registered; use rotate()")
        self.store.write(reference, value)
        del value  # nothing downstream in this process holds the value
        now = self.now()
        metadata = SecretMetadata(
            reference=reference,
            tenant_id=tenant_id,
            owner_principal_id=owner_principal_id,
            classification=classification,
            created_at=now,
            rotates_after=rotates_after,
            last_rotated_at=now,
        )
        self._metadata[reference] = metadata
        return metadata

    def describe(self, reference: str) -> SecretMetadata:
        """Metadata only. There is no counterpart returning the value."""
        try:
            return self._metadata[reference]
        except KeyError:
            raise NotFoundError(f"secret '{reference}' is not registered") from None

    def authorize_injection(
        self,
        reference: str,
        sandbox_id: str,
        invocation_id: str,
        requester_id: str,
        requester_type: PrincipalType,
        ttl: timedelta = timedelta(minutes=5),
    ) -> InjectionGrant:
        """Secret Reference Resolution interface (21B §22.5) — consumed by the Tool Executor.

        Returns a grant, not a value. Agents and workflows may never hold a
        grant: only the Tool Executor (a Service) injects into a sandbox.
        """
        metadata = self.describe(reference)
        if metadata.retired_at is not None:
            raise ValidationError(f"secret '{reference}' was retired at {metadata.retired_at}")
        if requester_type in (PrincipalType.AGENT, PrincipalType.WORKFLOW):
            raise SecretExposureError(
                f"principal '{requester_id}' is a {requester_type.value}; no secret value or grant may reach "
                "an agent or workflow (14 rule 12)"
            )
        self._grant_seq += 1
        grant = InjectionGrant(
            grant_id=f"grant-{self._grant_seq:06d}",
            reference=reference,
            sandbox_id=sandbox_id,
            invocation_id=invocation_id,
            granted_to=requester_id,
            expires_at=self.now() + ttl,
        )
        self._grants[grant.grant_id] = grant
        return grant

    def inject(self, grant: InjectionGrant, injector: Callable[[str, str], None]) -> None:
        """Redeems a grant by handing the value straight to a sandbox injector.

        The value passes to `injector` and is never returned, logged, or
        journalled. The grant is single-use, so a captured grant cannot be
        replayed into a second sandbox.
        """
        known = self._grants.get(grant.grant_id)
        if known is None or known != grant:
            raise ValidationError(f"injection grant '{grant.grant_id}' was not issued by this Gateway")
        if grant.grant_id in self._consumed:
            raise SecretExposureError(f"injection grant '{grant.grant_id}' has already been redeemed")
        if self.now() >= grant.expires_at:
            raise ValidationError(f"injection grant '{grant.grant_id}' expired at {grant.expires_at}")
        self._consumed.add(grant.grant_id)
        injector(grant.sandbox_id, self.store.read(grant.reference))

    def rotate(self, reference: str, new_value: str) -> SecretMetadata:
        """Atomic rotation: the new value is registered before the old is retired (21B §22.8)."""
        metadata = self.describe(reference)
        self.store.write(reference, new_value)
        del new_value
        rotated = SecretMetadata(
            reference=metadata.reference,
            tenant_id=metadata.tenant_id,
            owner_principal_id=metadata.owner_principal_id,
            classification=metadata.classification,
            created_at=metadata.created_at,
            rotates_after=metadata.rotates_after,
            last_rotated_at=self.now(),
        )
        self._metadata[reference] = rotated
        # Outstanding grants referenced the pre-rotation value; drop them.
        for grant_id in [g for g, grant in self._grants.items() if grant.reference == reference]:
            self._grants.pop(grant_id, None)
        return rotated

    def retire(self, reference: str) -> SecretMetadata:
        metadata = self.describe(reference)
        retired = SecretMetadata(
            reference=metadata.reference,
            tenant_id=metadata.tenant_id,
            owner_principal_id=metadata.owner_principal_id,
            classification=metadata.classification,
            created_at=metadata.created_at,
            rotates_after=metadata.rotates_after,
            last_rotated_at=metadata.last_rotated_at,
            retired_at=self.now(),
        )
        self._metadata[reference] = retired
        return retired

    def rotation_due(self) -> list[SecretMetadata]:
        now = self.now()
        return [m for m in self._metadata.values() if m.retired_at is None and m.is_rotation_due(now)]


@dataclass(frozen=True)
class CredentialMetadata:
    credential_id: str
    principal_id: str
    principal_type: PrincipalType
    issued_at: datetime
    expires_at: datetime
    revoked_at: datetime | None = None


@dataclass
class CredentialGovernor:
    """Credential lifecycle: issuance, binding, rotation, revocation, archival (14.23).

    Enforces 14.23.4 — human credentials are non-delegable and non-automated.
    A credential bound to a Human principal can only ever be verified for that
    same Human; no agent, service or workflow may authenticate with it.
    """

    now: Callable[[], datetime] = field(default=lambda: datetime.now(UTC))
    _credentials: dict[str, CredentialMetadata] = field(default_factory=dict, init=False)
    #: reference -> salted hash. Never the credential material itself.
    _verifiers: dict[str, str] = field(default_factory=dict, init=False)

    def issue(
        self,
        credential_id: str,
        principal_id: str,
        principal_type: PrincipalType,
        verifier_hash: str,
        lifetime: timedelta = timedelta(days=90),
    ) -> CredentialMetadata:
        if credential_id in self._credentials:
            raise ValidationError(f"credential '{credential_id}' already issued")
        now = self.now()
        metadata = CredentialMetadata(
            credential_id=credential_id,
            principal_id=principal_id,
            principal_type=principal_type,
            issued_at=now,
            expires_at=now + lifetime,
        )
        self._credentials[credential_id] = metadata
        self._verifiers[credential_id] = verifier_hash
        return metadata

    def verify(self, credential_id: str, presented_hash: str, claiming_principal_id: str) -> CredentialMetadata:
        metadata = self._credentials.get(credential_id)
        if metadata is None:
            raise NotFoundError(f"credential '{credential_id}' is not registered")
        if metadata.revoked_at is not None:
            raise ValidationError(f"credential '{credential_id}' was revoked at {metadata.revoked_at}")
        if self.now() >= metadata.expires_at:
            raise ValidationError(f"credential '{credential_id}' expired at {metadata.expires_at}")
        if self._verifiers[credential_id] != presented_hash:
            raise ValidationError(f"credential '{credential_id}' verification failed")
        if metadata.principal_id != claiming_principal_id:
            raise ValidationError(
                f"credential '{credential_id}' is bound to '{metadata.principal_id}', not "
                f"'{claiming_principal_id}'; human credentials are non-delegable (14.23.4)"
            )
        return metadata

    def revoke(self, credential_id: str) -> CredentialMetadata:
        metadata = self._credentials.get(credential_id)
        if metadata is None:
            raise NotFoundError(f"credential '{credential_id}' is not registered")
        revoked = CredentialMetadata(
            credential_id=metadata.credential_id,
            principal_id=metadata.principal_id,
            principal_type=metadata.principal_type,
            issued_at=metadata.issued_at,
            expires_at=metadata.expires_at,
            revoked_at=self.now(),
        )
        self._credentials[credential_id] = revoked
        return revoked

    def revoke_for_principal(self, principal_id: str) -> list[str]:
        """Cascading revocation reaches credentials too (14.15.3)."""
        affected = [c for c, m in self._credentials.items() if m.principal_id == principal_id and m.revoked_at is None]
        for credential_id in affected:
            self.revoke(credential_id)
        return affected
