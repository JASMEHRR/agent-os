"""Agent Runtime - the execution environment for the autonomous workforce.

Realizes 05 and 06 and the component responsibility of 02.3.2, per 21B 13.

Two planes. The **Identity Plane** is durable: registry, reputation, drift,
lifecycle, persisting independently of any execution. The **Execution Plane**
is stateless: a worker acquires identity, hydrates, assembles, renders, infers,
dispatches tools, validates and returns to the pool holding nothing.

`02.3.2`: "The Workflow Engine owns scheduling; the Runtime owns execution."
That separation is load-bearing and is preserved throughout.
"""

from agent_runtime.adapters import (
    LLMRouterInference,
    MemoryGatewayHydrator,
    SecurityGatewayRuntimeAuthorizer,
    ToolGatewayDispatcher,
)
from agent_runtime.identity import (
    AGENT_TRANSITIONS,
    HEARTBEAT_CADENCE,
    REPUTATION_DECAY_FRACTION,
    REPUTATION_DECAY_IDLE,
    SCHEMA_VIOLATION_SUSPENSION_THRESHOLD,
    STALL_MULTIPLIER,
    AgentManifest,
    AgentRecord,
    AgentState,
    AuthorityBoundaries,
    DriftMonitor,
    DriftReading,
    ManifestLoader,
    ReputationEngine,
)
from agent_runtime.runtime import (
    ActivityOutcome,
    ActivityRequest,
    AgentRuntime,
    AuthorityViolation,
    Heartbeat,
    InferenceSource,
    MemorySource,
    RuntimeAuthorizer,
    SeparationOfDutiesViolation,
    ToolSource,
    stall_threshold,
)

__all__ = [
    "AgentRuntime",
    "RuntimeAuthorizer",
    "MemorySource",
    "InferenceSource",
    "ToolSource",
    "ActivityRequest",
    "ActivityOutcome",
    "Heartbeat",
    "AuthorityViolation",
    "SeparationOfDutiesViolation",
    "stall_threshold",
    "AgentManifest",
    "AgentRecord",
    "AgentState",
    "AGENT_TRANSITIONS",
    "AuthorityBoundaries",
    "ManifestLoader",
    "ReputationEngine",
    "DriftMonitor",
    "DriftReading",
    "HEARTBEAT_CADENCE",
    "STALL_MULTIPLIER",
    "SCHEMA_VIOLATION_SUSPENSION_THRESHOLD",
    "REPUTATION_DECAY_IDLE",
    "REPUTATION_DECAY_FRACTION",
    "SecurityGatewayRuntimeAuthorizer",
    "MemoryGatewayHydrator",
    "LLMRouterInference",
    "ToolGatewayDispatcher",
]
