"""Binds the Gateway's `MemoryAuthorizer` protocol to the real Security Gateway.

The only module in `memory_gateway` that imports `security_gateway`, keeping
the permitted dependency edge of 21B §16.6 visible in one file.

09.6.3 puts memory scope enforcement on the Gateway, "not by the agent": read
scope, write scope and filters are declared in the agent manifest and checked
here through the ordinary Authorization interface, so the Permission
Intersection Rule governs memory access exactly as it governs everything else.
"""

from __future__ import annotations

from dataclasses import dataclass

from security_gateway import AuthorizationRequest, Decision, SecurityGateway

FORM_PREFIX = "memory.form"
RETRIEVE_PREFIX = "memory.retrieve"


@dataclass
class SecurityGatewayMemoryAuthorizer:
    """Implements `memory_gateway.gateway.MemoryAuthorizer`."""

    gateway: SecurityGateway

    def principal_of(self, token: str) -> tuple[str, str]:
        claims = self.gateway.tokens.validate(token)
        return claims.principal_id, claims.tenant_id

    def may_form(self, token: str, tenant_id: str, memory_type: str) -> bool:
        return self._allowed(token, f"{FORM_PREFIX}.{memory_type}", f"memory:{memory_type}", tenant_id)

    def may_retrieve(self, token: str, tenant_id: str, sensitivity: str) -> bool:
        return self._allowed(token, f"{RETRIEVE_PREFIX}.{sensitivity}", f"memory:{tenant_id}", tenant_id)

    def _allowed(self, token: str, action: str, resource_id: str, tenant_id: str) -> bool:
        result = self.gateway.authorize(
            token,
            AuthorizationRequest(action=action, resource_id=resource_id, resource_tenant_id=tenant_id),
        )
        return result.decision == Decision.ALLOW
