"""Adapters binding the Engine's ports to the real S1-S7 subsystems.

The only module in `workflow_engine` importing them, keeping the permitted
edges of 21B §14.6 visible in one file.

`07.13.1`: "The orchestrator does not perform work; it governs work." Each
adapter here dispatches and returns; none of them performs the work itself.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from agent_runtime import ActivityRequest, AgentRuntime
from cost_manager import BudgetScope, CostManager, ScopeKind
from decision_gateway import DecisionGateway, DecisionState
from tool_executor import ToolExecutor
from tool_gateway import InvocationOutcome, ToolGateway


@dataclass
class AgentRuntimeDispatcher:
    """Implements `workflow_engine.engine.AgentDispatcher`.

    21B §13.13 permits this intra-layer edge because the Workflow Engine
    *dispatches to* the Runtime rather than coordinating laterally with it.
    """

    runtime: AgentRuntime

    def discover(self, token: str, capability: str, min_reputation: float) -> list[Any]:
        return self.runtime.discover(token, capability=capability, min_reputation=min_reputation)

    def execute(
        self,
        token: str,
        *,
        activity_id: str,
        workflow_id: str,
        agent_id: str,
        tenant_id: str,
        idempotency_key: str,
        inputs: dict[str, str],
        decision_id: str,
        cost_ceiling: float,
    ) -> Any:
        """Builds the Runtime's request here, so `ActivityRequest` is a type the
        engine never names. The adapter is the only file that crosses the seam."""
        return self.runtime.execute(
            token,
            ActivityRequest(
                activity_id=activity_id,
                workflow_id=workflow_id,
                agent_id=agent_id,
                tenant_id=tenant_id,
                idempotency_key=idempotency_key,
                inputs=inputs,
                decision_id=decision_id,
                cost_ceiling=cost_ceiling,
            ),
        )


@dataclass
class ToolGatewayWorkflowDispatcher:
    """Implements `workflow_engine.engine.ToolDispatcher`.

    Compensation invocation is the Workflow Engine's own interface on the Tool
    Gateway (21B §19.5), used during saga rollback.
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
        key: str,
    ) -> tuple[bool, dict[str, Any] | None, float, str]:
        contract = self.gateway.authorize(token, tool_id, decision_id, parameters, cost_ceiling, key)
        result = self.executor.run(contract, self.tool_impl, cost_meter=lambda: 0.0)
        record = self.gateway.complete(
            contract.invocation_id,
            result.outcome,
            result.output,
            result.actual_cost,
            result.started_at,
            result.detail,
        )
        return (
            record.outcome == InvocationOutcome.SUCCEEDED,
            result.output,
            record.actual_cost,
            contract.invocation_id,
        )

    def compensate(self, token: str, invocation_id: str, decision_id: str) -> bool:
        try:
            contract = self.gateway.compensate(token, invocation_id, decision_id)
        except Exception:
            return False
        result = self.executor.run(contract, self.tool_impl, cost_meter=lambda: 0.0)
        self.gateway.complete(
            contract.invocation_id,
            result.outcome,
            result.output,
            result.actual_cost,
            result.started_at,
            result.detail,
        )
        return result.outcome == InvocationOutcome.SUCCEEDED


@dataclass
class DecisionGatewayApprovals:
    """Implements `workflow_engine.engine.ApprovalSource`.

    A human gate is a first-class DAG activity (21B §14.2), and the approval it
    waits on is an ordinary Decision Gateway approval — so the gate inherits
    11 rule 3's timeout semantics for free: silence never approves.
    """

    gateway: DecisionGateway
    #: Maps a workflow gate to the decision it waits on.
    _requested: dict[str, str] = field(default_factory=dict, init=False)

    def bind(self, workflow_id: str, activity_id: str, decision_id: str) -> None:
        """Associates a gate with the decision that authorizes it.

        The workflow does not create the decision — the Decision Gateway owns
        that. The Engine only records which decision this gate is waiting on.
        """
        self._requested[f"{workflow_id}:{activity_id}"] = decision_id

    def request_approval(self, workflow_id: str, activity_id: str, decision_class: str) -> str:
        key = f"{workflow_id}:{activity_id}"
        return self._requested.get(key, key)

    def is_approved(self, decision_id: str) -> bool:
        """Whether a decision of sufficient authority has actually been approved.

        Asks the Decision Gateway rather than tracking approval locally: a
        workflow keeping its own approval state could drift from the record
        that actually authorizes the effect.
        """
        try:
            record = self.gateway.get(decision_id)
        except Exception:
            return False
        return record.state in (DecisionState.APPROVED, DecisionState.COMMITTED)


@dataclass
class CostManagerWorkflowBudget:
    """Implements `workflow_engine.engine.BudgetSource`."""

    manager: CostManager

    def has_headroom(self, tenant_id: str, cost: float) -> bool:
        scope = BudgetScope(kind=ScopeKind.TENANT, identifier=tenant_id)
        return self.manager.check(scope, tenant_id, estimated_cost=cost).may_proceed


__all__ = [
    "AgentRuntimeDispatcher",
    "ToolGatewayWorkflowDispatcher",
    "DecisionGatewayApprovals",
    "CostManagerWorkflowBudget",
]
