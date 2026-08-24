"""The single file in `api_gateway` that imports another subsystem.

02.3.1 gives the Gateway authentication and authorization as responsibilities,
but the Trust Plane owns the answers. This adapter is where the Gateway asks
and nowhere else, so the Permission Intersection Rule (14.12.4) keeps a single
authority computing it.
"""

from __future__ import annotations

from dataclasses import dataclass

from api_gateway.ratelimit import Tier
from security_gateway import AuthorizationRequest, PrincipalType, SecurityGateway


@dataclass
class SecurityGatewayIngressAuthority:
    """Implements `api_gateway.gateway.IngressAuthority`."""

    gateway: SecurityGateway

    def authenticate(self, token: str) -> tuple[str, str]:
        claims = self.gateway.tokens.validate(token)
        return claims.principal_id, claims.tenant_id

    def tier_of(self, principal_id: str) -> Tier:
        """Maps principal type to the rate-limit tiers of 03 §32.5.

        A human or agent principal is an authenticated client; a service
        account gets the service tier. Nothing here reads a claim the client
        supplied, because a client-asserted tier is a client-chosen rate limit.
        """
        if not self.gateway.registry.exists(principal_id):
            return Tier.ANONYMOUS
        principal_type = self.gateway.registry.get(principal_id).principal_type
        if principal_type == PrincipalType.SERVICE:
            return Tier.SERVICE_ACCOUNT
        return Tier.AUTHENTICATED

    def permits(self, token: str, principal_id: str, permission: str, tenant_id: str) -> bool:
        """Asks the Security Gateway proper, not its internal engine.

        Going through `authorize` rather than reading permissions directly is
        what keeps the delegation chain, revocation, isolation and anomaly
        checks in the path. A Gateway that peeked at the permission set would
        skip five of the six things authorization actually does.
        """
        result = self.gateway.authorize(
            token,
            AuthorizationRequest(action=permission, resource_id=permission, resource_tenant_id=tenant_id),
        )
        return bool(result.allowed)
