"""Tool Registry - governs tool existence (realizes 12.6.1, 21B 19).

The first of the Tool Platform's three modules. `12.6.1` is explicit that the
Registry never dispatches: it answers what tools exist, what they promise, how
trusted they are, and whether they are healthy. Discoverability is not
authorization - that is the Gateway's job, and the separation is absolute.
"""

from tool_registry.manifests import (
    AUTONOMOUS_TRUST_THRESHOLD,
    INVOCATION_RETENTION,
    TOOL_TRANSITIONS,
    TRUST_DECAY_FRACTION,
    TRUST_DECAY_IDLE,
    Availability,
    Compensation,
    Contract,
    SandboxTier,
    ToolEffect,
    ToolManifest,
    ToolRecord,
    ToolState,
)
from tool_registry.registry import (
    RegistrationRejected,
    RegistrationValidator,
    RegistryAuthorizer,
    ToolRegistry,
    TrustEngine,
)
from tool_registry.security_adapter import SecurityGatewayRegistryAuthorizer

__all__ = [
    "ToolRegistry",
    "RegistryAuthorizer",
    "RegistrationValidator",
    "RegistrationRejected",
    "TrustEngine",
    "ToolManifest",
    "ToolRecord",
    "ToolState",
    "TOOL_TRANSITIONS",
    "ToolEffect",
    "SandboxTier",
    "Contract",
    "Compensation",
    "Availability",
    "AUTONOMOUS_TRUST_THRESHOLD",
    "TRUST_DECAY_IDLE",
    "TRUST_DECAY_FRACTION",
    "INVOCATION_RETENTION",
    "SecurityGatewayRegistryAuthorizer",
]
