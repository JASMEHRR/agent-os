"""Tool Gateway - authorizes every invocation (realizes 12.6.2, 21B 19).

The second of the Tool Platform's three modules, and the airlock itself:
`12.2.1` makes the tool "the constitutional airlock", and this is the boundary
a consumer cannot cross unmediated.

It authorizes and records; it does not execute. Policy and execution do not
share a process, which is the structural reason the Executor is separate.
"""

from tool_gateway.adapters import (
    CostManagerBudget,
    DecisionGatewayVerifier,
    RegistryIntegrationSource,
    SecurityGatewayToolAuthorizer,
    UnbackedIntegrationSource,
)
from tool_gateway.contracts import (
    AttributionChain,
    InvocationContract,
    InvocationOutcome,
    InvocationRecord,
    new_invocation_id,
)
from tool_gateway.gateway import (
    BREAKER_COOLDOWN,
    BREAKER_FAILURE_THRESHOLD,
    BudgetSource,
    CircuitBreaker,
    DecisionSource,
    IntegrationSource,
    InvocationRefused,
    SandboxDeEscalation,
    ToolAuthorizer,
    ToolGateway,
)

__all__ = [
    "ToolGateway",
    "ToolAuthorizer",
    "DecisionSource",
    "BudgetSource",
    "IntegrationSource",
    "InvocationRefused",
    "SandboxDeEscalation",
    "CircuitBreaker",
    "BREAKER_FAILURE_THRESHOLD",
    "BREAKER_COOLDOWN",
    "InvocationContract",
    "InvocationRecord",
    "InvocationOutcome",
    "AttributionChain",
    "new_invocation_id",
    "SecurityGatewayToolAuthorizer",
    "DecisionGatewayVerifier",
    "CostManagerBudget",
    "RegistryIntegrationSource",
    "UnbackedIntegrationSource",
]
