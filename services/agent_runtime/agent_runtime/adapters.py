"""Adapters binding the Runtime's ports to the real S1-S6 subsystems.

The only module in `agent_runtime` importing them, keeping the permitted edges
of 21B 13.6 visible in one file.

21B 13.4: "The worker holds no credential, contacts no provider, and touches
no substrate." Each adapter here goes through the owning Gateway - Memory for
state, LLM Router for inference, Tool Gateway for tools - and none of them
reaches past it.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from llm_router import InferenceRequest, LLMRouter, ModelTier
from memory_gateway import MemoryGateway
from security_gateway import PrincipalType, SecurityGateway
from tool_executor import Sandbox, ToolExecutor
from tool_gateway import InvocationOutcome, ToolGateway


@dataclass
class SecurityGatewayRuntimeAuthorizer:
    """Implements `agent_runtime.runtime.RuntimeAuthorizer`."""

    gateway: SecurityGateway

    def principal_of(self, token: str) -> tuple[str, str]:
        claims = self.gateway.tokens.validate(token)
        return claims.principal_id, claims.tenant_id

    def is_human(self, principal_id: str) -> bool:
        if not self.gateway.registry.exists(principal_id):
            return False
        return self.gateway.registry.get(principal_id).principal_type == PrincipalType.HUMAN


@dataclass
class MemoryGatewayHydrator:
    """Implements `agent_runtime.runtime.MemorySource`.

    09.6.1 admits no direct memory access, so hydration asks the Memory
    Gateway like any other consumer. A degraded memory tier returns nothing
    rather than raising: 21B 16.9 puts graceful degradation of retrieval
    quality ahead of availability, and the Runtime flags the degradation.
    """

    gateway: MemoryGateway

    def hydrate(self, token: str, tenant_id: str, scope: frozenset[str]) -> Sequence[Mapping[str, Any]]:
        try:
            hits = self.gateway.retrieve(token, tenant_id, limit=10)
        except Exception:
            return ()
        return [dict(hit.record.entry.payload) for hit in hits]


@dataclass
class LLMRouterInference:
    """Implements `agent_runtime.runtime.InferenceSource`.

    03 rule 11 and 02.3.8 route all inference through the Router. The Runtime
    never contacts a model provider, which is why this adapter has no notion
    of one.
    """

    router: LLMRouter
    tier: ModelTier = ModelTier.STANDARD

    def infer(
        self, template: str, slots: dict[str, str], tenant_id: str, principal_id: str, max_cost: float
    ) -> tuple[dict[str, Any], float, bool]:
        result = self.router.infer(
            InferenceRequest(
                request_id=f"agent:{principal_id}:{template}",
                template_name=template,
                slots=slots,
                tenant_id=tenant_id,
                principal_id=principal_id,
                tier=self.tier,
                max_cost=max_cost,
            )
        )
        return result.output, result.cost, result.grounded


@dataclass
class ToolGatewayDispatcher:
    """Implements `agent_runtime.runtime.ToolSource`.

    12 rule 11 forbids consumer-to-executor invocation, so the Runtime asks
    the Tool Gateway to authorize and only then hands the contract to the
    Executor. The Runtime never contacts the Executor directly with anything
    the Gateway has not validated.
    """

    gateway: ToolGateway
    executor: ToolExecutor
    tool_impl: Any

    def invoke(
        self,
        token: str,
        tool_id: str,
        decision_id: str,
        parameters: dict[str, Any],
        cost_ceiling: float,
        idempotency_key: str,
    ) -> tuple[bool, dict[str, Any] | None, float]:
        contract = self.gateway.authorize(token, tool_id, decision_id, parameters, cost_ceiling, idempotency_key)
        result = self.executor.run(contract, self.tool_impl, cost_meter=lambda: 0.0)
        record = self.gateway.complete(
            contract.invocation_id,
            result.outcome,
            result.output,
            result.actual_cost,
            result.started_at,
            result.detail,
        )
        return record.outcome == InvocationOutcome.SUCCEEDED, result.output, record.actual_cost


__all__ = [
    "SecurityGatewayRuntimeAuthorizer",
    "MemoryGatewayHydrator",
    "LLMRouterInference",
    "ToolGatewayDispatcher",
    "Sandbox",
]
