"""The single file in `learning_gateway` that imports other subsystems.

21B §21.6 lists nine consumed interfaces. Confining them here keeps the
meta-layer's reach visible in one place, which matters more for this module
than for most: Learning reads from almost everything, and a subsystem that
reads widely is one whose boundaries are easiest to lose track of.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from cost_manager import BudgetScope, CostManager, ScopeKind
from security_gateway import PrincipalType, SecurityGateway


@dataclass
class SecurityGatewayLearningAuthorizer:
    """Implements `learning_gateway.gateway.LearningAuthorizer`.

    13 rule 7 forbids anonymous learning formation, so every observer resolves
    through the Trust Plane rather than being taken at its word.
    """

    gateway: SecurityGateway

    def principal_of(self, token: str) -> tuple[str, str]:
        claims = self.gateway.tokens.validate(token)
        return claims.principal_id, claims.tenant_id

    def is_human(self, principal_id: str) -> bool:
        if not self.gateway.registry.exists(principal_id):
            return False
        return self.gateway.registry.get(principal_id).principal_type == PrincipalType.HUMAN


@dataclass
class CostManagerLearningBudget:
    """Implements `learning_gateway.gateway.BudgetSource`.

    13 rule 11: a learning cycle may not consume resources that breach a
    portfolio-level circuit breaker. Learning is the subsystem most able to
    justify spending indefinitely on itself, which is why the check is here
    and not optional.
    """

    manager: CostManager

    def has_headroom(self, tenant_id: str, cost: float) -> bool:
        scope = BudgetScope(kind=ScopeKind.TENANT, identifier=tenant_id)
        return bool(self.manager.check(scope, tenant_id, estimated_cost=cost).may_proceed)


@dataclass
class GatewayProposalSink:
    """Implements `learning_gateway.gateway.ProposalSink` for any target.

    Deliberately thin. 13.16.1 makes propagation a handoff, so the adapter can
    deliver and can do nothing else: it holds no reference that would let
    Learning adopt on the target's behalf.
    """

    target_subsystem: str

    def __post_init__(self) -> None:
        self.received: list[tuple[str, Mapping[str, Any]]] = []

    def receive(self, entry_id: str, target_subsystem: str, proposal: Mapping[str, Any]) -> str:
        self.received.append((entry_id, dict(proposal)))
        return f"ack-{entry_id}"
