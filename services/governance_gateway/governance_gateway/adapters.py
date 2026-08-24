"""The single file in `governance_gateway` that imports other subsystems.

21B §23.6 lists nine consumed interfaces, and Governance reads more widely than
any other subsystem. Confining the imports here matters more here than
elsewhere, because the thing that must stay visible is that Governance reads
and never writes: 15.22.3 forbids it modifying subsystem internals, and an
import of a subsystem's mutating surface would be the first step toward doing
so by accident.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from security_gateway import PrincipalType, SecurityGateway


@dataclass
class SecurityGatewayGovernanceAuthorizer:
    """Implements `governance_gateway.gateway.GovernanceAuthorizer`."""

    gateway: SecurityGateway

    def principal_of(self, token: str) -> tuple[str, str]:
        claims = self.gateway.tokens.validate(token)
        return claims.principal_id, claims.tenant_id

    def is_human(self, principal_id: str) -> bool:
        if not self.gateway.registry.exists(principal_id):
            return False
        return self.gateway.registry.get(principal_id).principal_type == PrincipalType.HUMAN


@dataclass
class ImmutableJournalSource:
    """Implements `governance_gateway.gateway.JournalSource` over a kernel journal.

    15.7.2 permits evidence assembly directly from subsystem journals, which is
    what lets Governance operate before the full Observability profile exists.
    The adapter exposes reads only: it holds the journal but offers no append,
    so Governance cannot manufacture the evidence it then assesses.
    """

    journal: Any
    #: Which payload field names the scope an entry belongs to.
    scope_field: str = "tenant_id"

    def entries(self, scope: str) -> Sequence[Mapping[str, Any]]:
        found: list[Mapping[str, Any]] = []
        for index in range(len(self.journal)):
            payload = self.journal[index].payload
            value = str(payload.get(self.scope_field, ""))
            if value == scope or scope.startswith(f"{value}/") or value.startswith(f"{scope}/"):
                found.append(payload)
        return found
