"""Adapters binding the Gateway's ports to the real S1-S4 subsystems.

The only module in `decision_gateway` that imports them, keeping the four
permitted dependency edges of 21B §18.6 visible in one file.

Each port is deliberately narrow. The Decision Gateway "owns no knowledge, no
memory, no tool manifest, and no execution state" (21B §18.7) — it records
commitments, it does not execute them — so each adapter exposes only the
question the funnel actually asks.
"""

from __future__ import annotations

from dataclasses import dataclass

from cost_manager import BudgetScope, CostManager, ScopeKind
from kernel.authority import AuthorityLevel
from knowledge_gateway import KnowledgeGateway
from security_gateway import PrincipalType, SecurityGateway


@dataclass
class SecurityGatewayDecisionAuthorizer:
    """Implements `decision_gateway.gateway.DecisionAuthorizer`."""

    gateway: SecurityGateway

    def principal_of(self, token: str) -> tuple[str, str]:
        claims = self.gateway.tokens.validate(token)
        return claims.principal_id, claims.tenant_id

    def is_human(self, principal_id: str) -> bool:
        if not self.gateway.registry.exists(principal_id):
            return False
        return self.gateway.registry.get(principal_id).principal_type == PrincipalType.HUMAN

    def autonomy_level(self, principal_id: str) -> AuthorityLevel:
        """A principal's constitutional autonomy level (11 rule 5).

        Humans are Level 4 by construction: 11.9.1 binds Human Sovereign
        authority to a human operator, so it is not something an agent's
        registered autonomy level can reach.
        """
        if not self.gateway.registry.exists(principal_id):
            return AuthorityLevel.AGENT_AUTONOMOUS
        principal = self.gateway.registry.get(principal_id)
        if principal.principal_type == PrincipalType.HUMAN:
            return AuthorityLevel.HUMAN_SOVEREIGN
        level = principal.autonomy_level
        if level is None:
            # Services and Gateways have no autonomy level (14.8.1); they
            # operate under fixed permission sets, so they get the floor.
            return AuthorityLevel.AGENT_AUTONOMOUS
        return AuthorityLevel(max(1, min(4, level)))


@dataclass
class KnowledgeGatewayEvidenceSource:
    """Implements `decision_gateway.gateway.KnowledgeSource`.

    11.12.4 grounds decisions in canonical beliefs, and 11 rule 8 blocks any
    autonomous path past an unresolved contradiction — so the one question the
    Decision Gateway asks Knowledge is whether a cited belief is contradicted.
    """

    gateway: KnowledgeGateway

    def is_contradicted(self, belief_id: str) -> bool:
        try:
            return bool(self.gateway.contradictions_for(belief_id))
        except Exception:
            # An unresolvable citation is treated as contradicted rather than
            # clean: the Gateway fails closed on evidence it cannot verify.
            return True


@dataclass
class CostManagerBudgetSource:
    """Implements `decision_gateway.gateway.BudgetSource`."""

    manager: CostManager

    def has_headroom(self, tenant_id: str, cost: float) -> bool:
        scope = BudgetScope(kind=ScopeKind.TENANT, identifier=tenant_id)
        verdict = self.manager.check(scope, tenant_id, estimated_cost=cost)
        return verdict.may_proceed
