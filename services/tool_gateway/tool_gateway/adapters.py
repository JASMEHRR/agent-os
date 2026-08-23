"""Adapters binding the Gateway's ports to the real S1-S5 subsystems.

The only module in `tool_gateway` importing them, keeping the permitted edges
of 21B 19.6 visible in one file.

`UnbackedIntegrationSource` is the honest default while the Integration
Platform is CIR-001 construction-blocked: it reports every abstraction
unbacked, so a tool declaring one is refused rather than silently permitted to
reach outside through a platform that does not exist.
"""

from __future__ import annotations

from dataclasses import dataclass

from cost_manager import BudgetScope, CostManager, ScopeKind
from decision_gateway import DecisionClass, DecisionGateway
from security_gateway import AuthorizationRequest, Decision, PrincipalType, SecurityGateway

INVOKE_PREFIX = "tool.invoke"


@dataclass
class SecurityGatewayToolAuthorizer:
    """Implements `tool_gateway.gateway.ToolAuthorizer`."""

    gateway: SecurityGateway

    def principal_of(self, token: str) -> tuple[str, str]:
        claims = self.gateway.tokens.validate(token)
        return claims.principal_id, claims.tenant_id

    def is_human(self, principal_id: str) -> bool:
        if not self.gateway.registry.exists(principal_id):
            return False
        return self.gateway.registry.get(principal_id).principal_type == PrincipalType.HUMAN

    def autonomy_level(self, principal_id: str) -> int:
        if not self.gateway.registry.exists(principal_id):
            return 1
        principal = self.gateway.registry.get(principal_id)
        if principal.principal_type == PrincipalType.HUMAN:
            return 4
        return principal.autonomy_level or 1

    def may_invoke(self, token: str, tenant_id: str, capability: str) -> bool:
        result = self.gateway.authorize(
            token,
            AuthorizationRequest(
                action=f"{INVOKE_PREFIX}.{capability}",
                resource_id=f"tool:{capability}",
                resource_tenant_id=tenant_id,
            ),
        )
        return result.decision == Decision.ALLOW


@dataclass
class DecisionGatewayVerifier:
    """Implements `tool_gateway.gateway.DecisionSource`.

    12 rule 2 - no execution without a valid decision record of matching
    authority. This is the caller side of the Decision Gateway's `verify`.
    """

    gateway: DecisionGateway

    def verify(self, decision_id: str, required_class: str) -> bool:
        try:
            self.gateway.verify(decision_id, DecisionClass(required_class))
        except Exception:
            return False
        return True


@dataclass
class CostManagerBudget:
    """Implements `tool_gateway.gateway.BudgetSource`."""

    manager: CostManager

    def has_headroom(self, tenant_id: str, cost: float) -> bool:
        scope = BudgetScope(kind=ScopeKind.TENANT, identifier=tenant_id)
        return self.manager.check(scope, tenant_id, estimated_cost=cost).may_proceed

    def record_spend(self, tenant_id: str, scope: str, cost: float, operation: str, principal_id: str) -> None:
        budget_scope = BudgetScope(kind=ScopeKind.TENANT, identifier=tenant_id)
        self.manager.record(budget_scope, tenant_id, cost, operation, principal_id)


@dataclass
class UnbackedIntegrationSource:
    """Implements `tool_gateway.gateway.IntegrationSource` while CIR-001 blocks.

    Reports every capability abstraction as unbacked. A tool that declares one
    is therefore refused at the integration gate, which is the correct
    behaviour: the Integration Platform cannot be constructed until CIR-001 is
    resolved, so nothing can legitimately back an abstraction yet. Tools that
    reach nothing external are unaffected.
    """

    def is_backed(self, abstraction: str, tenant_id: str) -> bool:
        return False
