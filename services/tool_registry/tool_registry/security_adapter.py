"""Binds the Registry's `RegistryAuthorizer` to the real Security Gateway.

The only module in `tool_registry` importing `security_gateway`, keeping the
permitted edge of 21B 19.6 visible in one file.
"""

from __future__ import annotations

from dataclasses import dataclass

from security_gateway import PrincipalType, SecurityGateway


@dataclass
class SecurityGatewayRegistryAuthorizer:
    """Implements `tool_registry.registry.RegistryAuthorizer`."""

    gateway: SecurityGateway

    def principal_of(self, token: str) -> tuple[str, str]:
        claims = self.gateway.tokens.validate(token)
        return claims.principal_id, claims.tenant_id

    def is_human(self, principal_id: str) -> bool:
        if not self.gateway.registry.exists(principal_id):
            return False
        return self.gateway.registry.get(principal_id).principal_type == PrincipalType.HUMAN
