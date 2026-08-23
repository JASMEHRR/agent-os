"""Binds the Gateway's `QueryAuthorizer` protocol to the real Security Gateway.

The only module in `observability_gateway` that imports `security_gateway`,
mirroring the Event Bus's adapter convention so the permitted dependency edge
of 21B §24.6 stays visible in one file.

21B §24.10 is the point of this module: "Query API access is authorized by the
Security Gateway using the same intersect-permissions rule established in
§22.4 above; there is no privileged 'observability bypass' of Security
authorization, including for Governance's own queries." So queries route
through the ordinary Authorization interface, and the permission is an
ordinary hierarchical one — a principal permitted `observability.query.internal`
may read internal signals and nothing more sensitive.
"""

from __future__ import annotations

from dataclasses import dataclass

from security_gateway import AuthorizationRequest, Decision, SecurityGateway

QUERY_PREFIX = "observability.query"


@dataclass
class SecurityGatewayQueryAuthorizer:
    """Implements `observability_gateway.gateway.QueryAuthorizer`."""

    gateway: SecurityGateway

    def may_query(self, token: str, tenant_id: str, sensitivity: str) -> bool:
        result = self.gateway.authorize(
            token,
            AuthorizationRequest(
                action=f"{QUERY_PREFIX}.{sensitivity}",
                resource_id=f"telemetry:{tenant_id}",
                resource_tenant_id=tenant_id,
            ),
        )
        return result.decision == Decision.ALLOW
