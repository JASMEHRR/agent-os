"""Adapters binding the Router's ports to the real Memory and Cost subsystems.

The only module in `llm_router` importing them, keeping the permitted edges of
21B 20.6 visible in one file.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from cost_manager import BudgetScope, CostManager, ScopeKind
from llm_router.pipeline import ContextItem
from memory_gateway import MemoryGateway


@dataclass
class MemoryGatewayContext:
    """Implements `llm_router.router.ContextSource`.

    Context retrieval is pipeline stage 2. The token this adapter holds is the
    Router's own service identity: 09.6.1 admits no direct memory access, so
    the Router asks through the Memory Gateway like every other consumer.
    """

    gateway: MemoryGateway
    token: str

    def retrieve(self, tenant_id: str, query: str, limit: int) -> Sequence[ContextItem]:
        try:
            hits = self.gateway.retrieve(self.token, tenant_id, limit=limit)
        except Exception:
            # A degraded memory tier must not fail an inference: 21B 16.9 puts
            # graceful degradation of retrieval quality ahead of availability.
            return ()
        return [
            ContextItem(
                source_id=hit.memory_id,
                content=str(hit.record.entry.payload),
                confidence=hit.confidence,
            )
            for hit in hits
        ]


@dataclass
class CostManagerBudget:
    """Implements `llm_router.router.BudgetSource`."""

    manager: CostManager

    def has_headroom(self, tenant_id: str, cost: float) -> bool:
        scope = BudgetScope(kind=ScopeKind.TENANT, identifier=tenant_id)
        return self.manager.check(scope, tenant_id, estimated_cost=cost).may_proceed

    def record_spend(self, tenant_id: str, cost: float, principal_id: str, tier: str) -> None:
        scope = BudgetScope(kind=ScopeKind.TENANT, identifier=tenant_id)
        self.manager.record(scope, tenant_id, cost, f"inference:{tier}", principal_id)
