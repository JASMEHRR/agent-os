"""Adapters binding the Gateway's ports to the real S1-S5 subsystems.

The only module in `tool_gateway` importing them, keeping the permitted edges
of 21B 19.6 visible in one file.

`RegistryIntegrationSource` answers 21B §19.6's question — is this tool's
declared capability abstraction backed by an active, approved integration — by
asking the Integration Registry.

Until the CIR-001 ruling of 2026-08-24 that question had only one honest
answer. `UnbackedIntegrationSource` gave it: every abstraction unbacked, so a
tool declaring one was refused rather than silently permitted to reach outside
through a platform that did not exist. It is kept below, because a deployment
that has not yet registered its integrations is in exactly that position and
should fail the same way.
"""

from __future__ import annotations

from dataclasses import dataclass

from cost_manager import BudgetScope, CostManager, ScopeKind
from decision_gateway import DecisionClass, DecisionGateway
from integration_registry import IntegrationRegistry
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
class RegistryIntegrationSource:
    """Implements `tool_gateway.gateway.IntegrationSource` against the real Registry.

    21B §19.6 has the Tool Gateway verify that a tool's declared capability
    abstraction is backed by an **active, approved** integration. That is a
    question only the Integration Registry can answer, and this adapter asks it
    rather than reimplementing the judgement.

    Registered is not enough and approved is not enough: `resolve` returns only
    Active integrations, so a tool whose provider is suspended for repeated
    failure stops being invocable at the same moment the provider stops being
    trusted. Coupling those two facts is the point — a tool that kept working
    against a suspended provider would be reaching outside through a
    relationship the Registry has already withdrawn.
    """

    registry: IntegrationRegistry

    def is_backed(self, abstraction: str, tenant_id: str) -> bool:
        return bool(self.registry.resolve(abstraction, tenant_id))


@dataclass
class UnbackedIntegrationSource:
    """Reports every abstraction unbacked.

    This was the only honest answer while CIR-001 blocked construction, and it
    remains the correct one for a deployment that has registered no
    integrations: in both cases nothing backs the abstraction, and a tool
    declaring one should be refused rather than permitted to reach outside
    through a relationship that does not exist.

    Retained deliberately rather than deleted. The failure it produces is the
    same failure, and a system that lost the ability to express it would have
    to discover it at the provider instead.
    """

    def is_backed(self, abstraction: str, tenant_id: str) -> bool:
        return False
