"""Adapters binding the Gateway's ports to the real Security and Memory Gateways.

The only module in `knowledge_gateway` that imports either, keeping the two
permitted dependency edges of 21B §17.6 visible in one file. The Memory edge
is the directional intra-layer dependency 21B §16.13 permits because the
pipeline Events → Memory → Knowledge is unidirectional and acyclic.

`10.6.4` is the constraint this adapter must not violate: knowledge does not
mutate memory. The port exposes exactly one method, and it reads.
"""

from __future__ import annotations

from dataclasses import dataclass

from memory_gateway import MemoryGateway, MemoryState
from security_gateway import AuthorizationRequest, Decision, PrincipalType, SecurityGateway

QUERY_PREFIX = "knowledge.query"
SUBMIT_PREFIX = "knowledge.submit"


@dataclass
class SecurityGatewayKnowledgeAuthorizer:
    """Implements `knowledge_gateway.gateway.KnowledgeAuthorizer`."""

    gateway: SecurityGateway

    def principal_of(self, token: str) -> tuple[str, str]:
        claims = self.gateway.tokens.validate(token)
        return claims.principal_id, claims.tenant_id

    def is_human(self, principal_id: str) -> bool:
        if not self.gateway.registry.exists(principal_id):
            return False
        return self.gateway.registry.get(principal_id).principal_type == PrincipalType.HUMAN

    def may_query(self, token: str, tenant_id: str, sensitivity: str) -> bool:
        return self._allowed(token, f"{QUERY_PREFIX}.{sensitivity}", tenant_id)

    def may_submit(self, token: str, tenant_id: str, belief_type: str) -> bool:
        return self._allowed(token, f"{SUBMIT_PREFIX}.{belief_type}", tenant_id)

    def _allowed(self, token: str, action: str, tenant_id: str) -> bool:
        result = self.gateway.authorize(
            token,
            AuthorizationRequest(action=action, resource_id=f"knowledge:{tenant_id}", resource_tenant_id=tenant_id),
        )
        return result.decision == Decision.ALLOW


@dataclass
class MemoryGatewayEvidenceSource:
    """Implements `knowledge_gateway.gateway.MemorySource`.

    Read-only by construction: the port has one method and it returns a
    confidence score. There is no path from here into memory formation, which
    is what keeps the pipeline unidirectional (10.6.4).
    """

    gateway: MemoryGateway

    def confidence_of(self, token: str, memory_id: str) -> float | None:
        """The cited memory's confidence, or None when it does not exist.

        A purged entry reports None rather than its residual zero confidence:
        its payload is gone, so it can no longer support a belief even though
        its identity survives in the audit log.
        """
        try:
            record = self.gateway.get(memory_id)
        except Exception:
            return None
        if record.state == MemoryState.PURGED:
            return None
        return record.confidence
