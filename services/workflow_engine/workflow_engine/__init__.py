"""Workflow Engine — orchestrator of durable business processes (21B §14).

Realizes 07 and the component responsibility of 02.3.3.

`07.13.1`: "The orchestrator does not perform work; it governs work."
`02.3.2`: the Engine owns scheduling; the Agent Runtime owns execution.

The engine spans two runtimes per the bilingual mandate of 03.3.1 and 03.3.2:
workflow definitions in TypeScript (`workflow_definitions/`), activity
implementations in Python. `schema.py` is the single source of truth for the
contracts crossing that boundary, and a contract test asserts the generated
TypeScript still matches it — 21B §14.4 calls the boundary "the engine's
highest-risk internal seam".
"""

from workflow_engine.adapters import (
    AgentRuntimeDispatcher,
    CostManagerWorkflowBudget,
    DecisionGatewayApprovals,
    ToolGatewayWorkflowDispatcher,
)
from workflow_engine.dag import (
    WORKFLOW_TRANSITIONS,
    Activity,
    ActivityKind,
    ActivityRecord,
    ActivityState,
    ExecutionDAG,
    PlanningFailure,
    WorkflowContext,
    WorkflowDefinition,
    WorkflowState,
)
from workflow_engine.engine import (
    AgentDispatcher,
    ApprovalSource,
    BudgetSource,
    ToolDispatcher,
    WorkflowEngine,
    WorkflowFailure,
    WorkflowRun,
)
from workflow_engine.schema import (
    CONTRACTS,
    ENUMS,
    contract_names,
    enum_members,
    render_typescript,
)

__all__ = [
    "WorkflowEngine",
    "WorkflowRun",
    "WorkflowFailure",
    "AgentDispatcher",
    "ToolDispatcher",
    "ApprovalSource",
    "BudgetSource",
    "Activity",
    "ActivityKind",
    "ActivityRecord",
    "ActivityState",
    "ExecutionDAG",
    "PlanningFailure",
    "WorkflowContext",
    "WorkflowDefinition",
    "WorkflowState",
    "WORKFLOW_TRANSITIONS",
    "render_typescript",
    "contract_names",
    "enum_members",
    "CONTRACTS",
    "ENUMS",
    "AgentRuntimeDispatcher",
    "ToolGatewayWorkflowDispatcher",
    "DecisionGatewayApprovals",
    "CostManagerWorkflowBudget",
]
