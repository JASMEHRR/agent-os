"""Tool Executor - fulfils validated contracts (realizes 12.6.3, 21B 19).

The third of the Tool Platform's three modules, and the only component in the
system authorized to spawn arbitrary processes.

`12.17.4`: "The Executor does not reinterpret contract terms." It receives a
validated contract and fulfils it within its terms, halting on any breach of
cost ceiling, timeout or sandbox boundary. It evaluates no authority.
"""

from tool_executor.executor import (
    LIMITS_BY_TIER,
    POOLABLE_TIERS,
    CostCeilingBreached,
    EgressBlocked,
    ExecutionResult,
    ResourceLimits,
    Sandbox,
    SandboxManager,
    SandboxState,
    SandboxViolation,
    SecretAuthority,
    TimeoutBreached,
    ToolExecutor,
)
from tool_executor.security_adapter import SecurityGatewaySecretAuthority

__all__ = [
    "ToolExecutor",
    "SecretAuthority",
    "ExecutionResult",
    "Sandbox",
    "SandboxManager",
    "SandboxState",
    "ResourceLimits",
    "LIMITS_BY_TIER",
    "POOLABLE_TIERS",
    "EgressBlocked",
    "SandboxViolation",
    "CostCeilingBreached",
    "TimeoutBreached",
    "SecurityGatewaySecretAuthority",
]
