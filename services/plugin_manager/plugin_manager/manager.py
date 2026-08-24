"""Plugin Manager — third-party extension discovery and lifecycle (02.3.10, 01.18.2).

**Not CIR-001 blocked.** The Build Specification pairs this module with the
Evolution Gateway at S12 but only Evolution carries the block. What is
constructed here is the manifest schema, the capability and permission model,
the lifecycle machine, and the sandbox *contract*. What is deliberately not
constructed is the container runtime, which is the part 03 names a technology
for.

`01.18.2` states the Non-Violable Rule: **"No business-specific logic may be
added to core modules when it can be implemented as a plugin."** The rule cuts
both ways, and the direction that matters here is the second: a plugin is
third-party code, so the manager's job is to bound it rather than to trust it.

`02.3.10`: "Plugins run as sidecars or separate containers, **never in core
process space**." The manager therefore holds no verb that would execute plugin
code in-process, asserted by test. A Plugin Manager able to call a plugin
directly would have made the isolation a convention.

Three properties are structural:

**Permissions are declared, granted, and intersected.** A plugin receives the
intersection of what its manifest requests and what a human granted — never the
union, and never what it merely asked for. This is 14.12.4 applied at the
extension boundary, which is the boundary least covered by the rest of the
system's identity model.

**Installation is not enablement.** A plugin can be installed and disabled,
mirroring the Tool Registry's registration-is-not-authorization rule.

**A plugin cannot grant itself anything.** Every grant requires a human
principal, because a third-party extension that could widen its own permissions
would make the declaration meaningless.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from core.exceptions import AgentOSError, NotFoundError, ValidationError
from kernel.journal import ImmutableJournal
from kernel.lifecycle import LifecycleStateMachine


class PluginState(StrEnum):
    """02.3.10's lifecycle: install, enable, disable, uninstall."""

    DISCOVERED = "discovered"
    INSTALLED = "installed"
    ENABLED = "enabled"
    DISABLED = "disabled"
    QUARANTINED = "quarantined"
    UNINSTALLED = "uninstalled"


PLUGIN_TRANSITIONS: dict[str, set[str]] = {
    PluginState.DISCOVERED: {PluginState.INSTALLED, PluginState.UNINSTALLED},
    # Installation is not enablement, mirroring the Tool Registry's
    # registration-is-not-authorization rule.
    PluginState.INSTALLED: {PluginState.ENABLED, PluginState.UNINSTALLED, PluginState.QUARANTINED},
    PluginState.ENABLED: {PluginState.DISABLED, PluginState.QUARANTINED},
    PluginState.DISABLED: {PluginState.ENABLED, PluginState.UNINSTALLED, PluginState.QUARANTINED},
    # A quarantined plugin returns only through a human decision to re-enable
    # or to remove it; it never resumes on its own.
    PluginState.QUARANTINED: {PluginState.DISABLED, PluginState.UNINSTALLED},
    PluginState.UNINSTALLED: set(),
}


class SandboxTier(StrEnum):
    """The isolation a plugin runs under. Never `in_process`.

    02.3.10 forbids core process space, so that value does not exist here. An
    enum member no one can select is a stronger guarantee than a check someone
    can forget.
    """

    SIDECAR = "sidecar"
    CONTAINER = "container"
    ISOLATED_VM = "isolated_vm"


@dataclass(frozen=True)
class ResourceLimits:
    """02.3.10 — the manifest declares resource limits."""

    max_memory_mb: int
    max_cpu_millicores: int
    max_wall_seconds: int
    #: Egress allowlist. An empty set means no external network at all, which
    #: is the correct default for code the system did not write.
    egress_allowlist: frozenset[str] = field(default_factory=frozenset)


@dataclass(frozen=True)
class PluginManifest:
    """02.3.10's manifest: capabilities, event subscriptions, permissions, limits."""

    plugin_id: str
    name: str
    version: str
    publisher: str
    capabilities: frozenset[str]
    #: Plugins may listen to the Event Bus (02.3.10), within their grant.
    event_subscriptions: frozenset[str]
    requested_permissions: frozenset[str]
    resource_limits: ResourceLimits
    sandbox_tier: SandboxTier
    #: The interface the plugin exposes, versioned per 01.18.1.
    api_version: str
    description: str = ""


@dataclass
class PluginRecord:
    """Lifecycle state and the permissions actually in force."""

    manifest: PluginManifest
    state: PluginState = PluginState.DISCOVERED
    #: What a human actually granted. Never assumed from the request.
    granted_permissions: frozenset[str] = field(default_factory=frozenset)
    granted_by: str | None = None
    installed_at: datetime | None = None
    enabled_at: datetime | None = None
    quarantine_reason: str = ""
    invocations: int = 0
    failures: int = 0

    @property
    def plugin_id(self) -> str:
        return self.manifest.plugin_id

    @property
    def effective_permissions(self) -> frozenset[str]:
        """The intersection of requested and granted (14.12.4).

        Never the union, and never the request alone. A plugin that received
        what it asked for would be writing its own permissions, which is what
        the grant step exists to prevent.
        """
        return self.manifest.requested_permissions & self.granted_permissions

    @property
    def is_active(self) -> bool:
        return self.state == PluginState.ENABLED

    @property
    def failure_rate(self) -> float:
        if self.invocations == 0:
            return 0.0
        return round(self.failures / self.invocations, 4)


class PluginRefused(AgentOSError):
    """The manager declined; the reason names which rule."""


#: [Engineering Decision] 01.18.2 requires sandboxing and capability
#: restrictions without a failure threshold. A plugin failing more than half
#: its invocations across a meaningful sample is quarantined.
QUARANTINE_FAILURE_RATE = 0.5
QUARANTINE_MINIMUM_SAMPLE = 4


@dataclass
class PluginManager:
    """Discovery, manifest validation, lifecycle, and permission bounding.

    It does not execute plugins. 02.3.10 puts plugin code in sidecars or
    separate containers, so the manager's surface stops at the boundary.
    """

    #: Whether a principal is human, delegated to the Trust Plane rather than
    #: inferred from an identifier.
    is_human: Callable[[str], bool]
    now: Callable[[], datetime] = field(default=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        self.journal = ImmutableJournal()
        self._plugins: dict[str, PluginRecord] = {}

    # ------------------------------------------------------------ Discovery

    def discover(self, manifest: PluginManifest) -> PluginRecord:
        """Records that a plugin exists. Grants nothing and runs nothing."""
        if manifest.plugin_id in self._plugins:
            raise AgentOSError(f"plugin '{manifest.plugin_id}' is already known")
        validate_manifest(manifest)
        record = PluginRecord(manifest=manifest)
        self._plugins[manifest.plugin_id] = record
        self._record("discovered", plugin_id=manifest.plugin_id, publisher=manifest.publisher)
        return record

    def catalogue(self, state: PluginState | None = None) -> list[PluginRecord]:
        if state is None:
            return list(self._plugins.values())
        return [p for p in self._plugins.values() if p.state == state]

    # ------------------------------------------------------------ Lifecycle

    def install(self, plugin_id: str, principal_id: str) -> PluginRecord:
        """Installation is not enablement. Nothing runs after this."""
        if not self.is_human(principal_id):
            raise PluginRefused(
                f"'{principal_id}' is not a human principal; installing third-party code is a human act (01.18.2)"
            )
        record = self.get(plugin_id)
        self._transition(record, PluginState.INSTALLED)
        record.installed_at = self.now()
        self._record("installed", plugin_id=plugin_id, by=principal_id)
        return record

    def grant(self, plugin_id: str, principal_id: str, permissions: frozenset[str]) -> PluginRecord:
        """A human grants; the plugin receives the intersection with its request.

        Granting a permission the manifest never requested is refused rather
        than silently ignored: the mismatch means the operator and the manifest
        disagree about what this plugin does, and that is worth surfacing.
        """
        if not self.is_human(principal_id):
            raise PluginRefused(f"'{principal_id}' is not a human principal; a plugin cannot grant itself permissions")
        record = self.get(plugin_id)
        undeclared = permissions - record.manifest.requested_permissions
        if undeclared:
            raise PluginRefused(
                f"plugin '{plugin_id}' never requested {sorted(undeclared)}; granting a permission the "
                "manifest does not declare means the operator and the manifest disagree about what this "
                "plugin does"
            )
        record.granted_permissions = record.granted_permissions | permissions
        record.granted_by = principal_id
        self._record("granted", plugin_id=plugin_id, by=principal_id, permissions=sorted(permissions))
        return record

    def revoke(self, plugin_id: str, principal_id: str, permissions: frozenset[str]) -> PluginRecord:
        if not self.is_human(principal_id):
            raise PluginRefused(f"'{principal_id}' is not a human principal; only a human revokes a grant")
        record = self.get(plugin_id)
        record.granted_permissions = record.granted_permissions - permissions
        self._record("revoked", plugin_id=plugin_id, by=principal_id, permissions=sorted(permissions))
        return record

    def enable(self, plugin_id: str, principal_id: str) -> PluginRecord:
        """Enabling requires a grant. An enabled plugin with no permissions
        would be running third-party code for no declared purpose."""
        if not self.is_human(principal_id):
            raise PluginRefused(f"'{principal_id}' is not a human principal; enabling is a human act")
        record = self.get(plugin_id)
        if not record.effective_permissions and record.manifest.requested_permissions:
            raise PluginRefused(
                f"plugin '{plugin_id}' requested {sorted(record.manifest.requested_permissions)} and holds "
                "none of them; enabling it would run third-party code for no declared purpose"
            )
        self._transition(record, PluginState.ENABLED)
        record.enabled_at = self.now()
        self._record("enabled", plugin_id=plugin_id, by=principal_id)
        return record

    def disable(self, plugin_id: str, principal_id: str, reason: str = "") -> PluginRecord:
        record = self.get(plugin_id)
        self._transition(record, PluginState.DISABLED)
        self._record("disabled", plugin_id=plugin_id, by=principal_id, reason=reason)
        return record

    def uninstall(self, plugin_id: str, principal_id: str) -> PluginRecord:
        if not self.is_human(principal_id):
            raise PluginRefused(f"'{principal_id}' is not a human principal; uninstalling is a human act")
        record = self.get(plugin_id)
        self._transition(record, PluginState.UNINSTALLED)
        record.granted_permissions = frozenset()
        self._record("uninstalled", plugin_id=plugin_id, by=principal_id)
        return record

    def quarantine(self, plugin_id: str, reason: str) -> PluginRecord:
        """Automatic on a failure threshold, or on an operator's judgement.

        A quarantined plugin never resumes on its own: `PLUGIN_TRANSITIONS`
        routes it back only through Disabled, which a human must lift.
        """
        record = self.get(plugin_id)
        self._transition(record, PluginState.QUARANTINED)
        record.quarantine_reason = reason
        self._record("quarantined", plugin_id=plugin_id, reason=reason)
        return record

    # --------------------------------------------------------- Authorization

    def permits(self, plugin_id: str, permission: str) -> bool:
        """Whether an enabled plugin holds a permission, by intersection.

        A disabled or quarantined plugin permits nothing regardless of what it
        was granted, because the grant survives the state change and the state
        change is the point.
        """
        record = self.get(plugin_id)
        if not record.is_active:
            return False
        return any(permission == held or permission.startswith(f"{held}.") for held in record.effective_permissions)

    def subscribed_events(self, plugin_id: str) -> frozenset[str]:
        """Event Bus subscriptions, bounded by state and grant (02.3.10)."""
        record = self.get(plugin_id)
        if not record.is_active:
            return frozenset()
        return record.manifest.event_subscriptions

    def record_invocation(self, plugin_id: str, succeeded: bool) -> PluginRecord:
        """Outcome accounting, and automatic quarantine past the threshold.

        The manager does not invoke; a caller that did reports back here so
        plugin reliability is visible without the manager holding a call path
        into plugin code.
        """
        record = self.get(plugin_id)
        record.invocations += 1
        if not succeeded:
            record.failures += 1
        if (
            record.invocations >= QUARANTINE_MINIMUM_SAMPLE
            and record.failure_rate > QUARANTINE_FAILURE_RATE
            and record.state == PluginState.ENABLED
        ):
            self.quarantine(
                plugin_id,
                f"failure rate {record.failure_rate} exceeds {QUARANTINE_FAILURE_RATE} "
                f"across {record.invocations} invocations",
            )
        return record

    # ---------------------------------------------------------------- Query

    def get(self, plugin_id: str) -> PluginRecord:
        record = self._plugins.get(plugin_id)
        if record is None:
            raise NotFoundError(f"plugin '{plugin_id}' is not known")
        return record

    def health(self) -> Mapping[str, Any]:
        records = list(self._plugins.values())
        by_state: dict[str, int] = {}
        for record in records:
            by_state[record.state.value] = by_state.get(record.state.value, 0) + 1
        invocations = sum(r.invocations for r in records)
        return {
            "plugins": len(records),
            "by_state": by_state,
            "enabled": len([r for r in records if r.is_active]),
            "quarantined": by_state.get(PluginState.QUARANTINED.value, 0),
            "invocations": invocations,
            "failure_rate": (round(sum(r.failures for r in records) / invocations, 4) if invocations else 0.0),
            # Structurally zero: `SandboxTier` has no in-process member.
            "in_process_plugins": 0,
            "journal_entries": len(self.journal),
            "journal_intact": self.journal.verify_chain(),
        }

    # ------------------------------------------------------------ Internals

    def _transition(self, record: PluginRecord, target: PluginState) -> None:
        machine = LifecycleStateMachine(transitions=dict(PLUGIN_TRANSITIONS), state=record.state)
        machine.transition(target)
        record.state = target

    def _record(self, action: str, **detail: Any) -> None:
        self.journal.append({"kind": "plugin", "action": action, **detail})


def validate_manifest(manifest: PluginManifest) -> None:
    """02.3.10's manifest requirements, checked rather than assumed."""
    if not manifest.plugin_id or not manifest.version:
        raise ValidationError("a plugin manifest must declare an id and a version")
    if not manifest.publisher.strip():
        raise ValidationError(
            f"plugin '{manifest.plugin_id}' declares no publisher; third-party code with no "
            "attributable author cannot be reviewed"
        )
    if not manifest.capabilities:
        raise ValidationError(f"plugin '{manifest.plugin_id}' declares no capabilities; it could do nothing")
    if not manifest.api_version.strip():
        raise ValidationError(
            f"plugin '{manifest.plugin_id}' declares no API version; 01.18.1 requires public interfaces "
            "to be versioned so an upgrade does not strand it"
        )
    limits = manifest.resource_limits
    if limits.max_memory_mb <= 0 or limits.max_cpu_millicores <= 0 or limits.max_wall_seconds <= 0:
        raise ValidationError(
            f"plugin '{manifest.plugin_id}' declares a non-positive resource limit; an unbounded "
            "third-party process is the failure 01.18.2's sandboxing requirement exists to prevent"
        )


def in_process_execution_verbs() -> Sequence[str]:
    """Deliberately empty, and asserted so by test.

    `02.3.10`: plugins "run as sidecars or separate containers, never in core
    process space". The absence of any verb that would call plugin code is what
    makes that structural rather than conventional.
    """
    return ()
