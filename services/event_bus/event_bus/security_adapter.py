"""Adapter binding the Bus's `TrustPlane` protocol to the real Security Gateway.

This is the only module in `event_bus` that imports `security_gateway`. Keeping
it isolated means the Bus's core depends on the *shape* of producer
authentication rather than the Gateway's internals, and the dependency edge
21B §15.6 permits (Event Bus → Security Gateway) is visible in exactly one file
rather than scattered through the subsystem.

Emission and subscription both authorize through the Gateway's normal
Authorization interface, so the Permission Intersection Rule and the live
permission graph apply to event traffic exactly as they apply to everything
else — the Bus grants nothing of its own (21A §5.4.2).
"""

from __future__ import annotations

from dataclasses import dataclass

from event_bus.admission import ProducerIdentity
from security_gateway import AuthorizationRequest, Decision, SecurityGateway

#: Permission prefixes an emission and a subscription are authorized against.
#: Both are ordinary hierarchical permissions (14.11.1), so a principal
#: permitted `event.emit.business` may emit any business event and nothing else.
EMIT_PREFIX = "event.emit"
SUBSCRIBE_PREFIX = "event.subscribe"


@dataclass
class SecurityGatewayTrustPlane:
    """Implements `event_bus.admission.TrustPlane` over a live Security Gateway."""

    gateway: SecurityGateway

    def authenticate_producer(self, token: str) -> ProducerIdentity:
        claims = self.gateway.tokens.validate(token)
        return ProducerIdentity(
            principal_id=claims.principal_id,
            tenant_id=claims.tenant_id,
            principal_type=claims.principal_type.value,
        )

    def authorize_emission(self, token: str, event_type: str, tenant_id: str) -> bool:
        result = self.gateway.authorize(
            token,
            AuthorizationRequest(
                action=f"{EMIT_PREFIX}.{event_type}",
                resource_id=f"stream:{event_type}",
                resource_tenant_id=tenant_id,
            ),
        )
        return result.decision == Decision.ALLOW

    def authorize_subscription(self, token: str, patterns: tuple[str, ...], tenant_id: str) -> bool:
        """Every requested pattern must be permitted; one failure denies the whole subscription.

        Partial subscription would silently give a consumer less than it asked
        for, and 08.10.2 puts the consumer in charge of knowing what it
        receives — a quietly narrowed subscription is a correctness trap.
        """
        return all(
            self.gateway.authorize(
                token,
                AuthorizationRequest(
                    action=f"{SUBSCRIBE_PREFIX}.{pattern}",
                    resource_id=f"stream:{pattern}",
                    resource_tenant_id=tenant_id,
                ),
            ).decision
            == Decision.ALLOW
            for pattern in patterns
        )
