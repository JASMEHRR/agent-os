"""Plugin Manager - third-party extension discovery and lifecycle (02.3.10, 01.18.2).

Not CIR-001 blocked. The manifest schema, capability and permission model,
lifecycle machine and sandbox contract are constructed; the container runtime
is not, because that is the part 03 names a technology for.

`02.3.10`: plugins "run as sidecars or separate containers, never in core
process space". The manager holds no verb that would execute plugin code, which
is what makes the isolation structural rather than conventional.
"""

from plugin_manager.manager import (
    PLUGIN_TRANSITIONS,
    QUARANTINE_FAILURE_RATE,
    QUARANTINE_MINIMUM_SAMPLE,
    PluginManager,
    PluginManifest,
    PluginRecord,
    PluginRefused,
    PluginState,
    ResourceLimits,
    SandboxTier,
    in_process_execution_verbs,
    validate_manifest,
)

__all__ = [
    "PluginManager",
    "PluginManifest",
    "PluginRecord",
    "PluginState",
    "PLUGIN_TRANSITIONS",
    "SandboxTier",
    "ResourceLimits",
    "PluginRefused",
    "QUARANTINE_FAILURE_RATE",
    "QUARANTINE_MINIMUM_SAMPLE",
    "validate_manifest",
    "in_process_execution_verbs",
]
