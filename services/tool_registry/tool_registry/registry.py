"""Tool Registry — governs existence, never operation (12.6.1, 21B §19).

`12.6.1`: the Registry answers what tools exist, what they promise, how
trusted they are, and whether they are healthy. **It never dispatches.** A
tool present in the Registry is discoverable, and discoverability is not
authorization — a test asserts no `invoke`/`execute`/`dispatch` method has
appeared on this surface.

| 21B §19.5 interface | Method       |
|---------------------|--------------|
| Tool Discovery      | `discover`   |
| Tool Registration   | `register`   |
| Tool Health Query   | `health_of`  |
| Tool Health Signals | `health`     |
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

from core.exceptions import AgentOSError, NotFoundError, ValidationError
from kernel.journal import ImmutableJournal
from kernel.lifecycle import LifecycleStateMachine
from kernel.signals import SignalEmitter, SignalType
from tool_registry.manifests import (
    AUTONOMOUS_TRUST_THRESHOLD,
    TOOL_TRANSITIONS,
    TRUST_DECAY_FRACTION,
    TRUST_DECAY_IDLE,
    Availability,
    SandboxTier,
    ToolManifest,
    ToolRecord,
    ToolState,
)


class RegistrationRejected(ValidationError):
    """The manifest failed validation. No Tool ID is issued (21B §19.9)."""


class RegistryAuthorizer(Protocol):
    """What the Registry needs from the Security Gateway (21B §19.6)."""

    def principal_of(self, token: str) -> tuple[str, str]: ...

    def is_human(self, principal_id: str) -> bool: ...


@dataclass
class RegistrationValidator:
    """Schema, contract consistency, sandbox feasibility, compensation, provenance.

    Every check here refuses rather than warns. 21B §19.9 classifies a
    registration validation failure as Contained with the response "Rejected;
    no Tool ID issued" — there is no partially-registered state.
    """

    def validate(self, manifest: ToolManifest) -> None:
        if not manifest.owner_principal_id:
            raise RegistrationRejected("anonymous tool registration is prohibited (12 rule 7)")
        if not manifest.capability or "." not in manifest.capability:
            raise RegistrationRejected(
                f"capability '{manifest.capability}' must be a hierarchical signature, e.g. 'external.http.fetch'"
            )
        if not manifest.input_contract.fields and not manifest.output_contract.fields:
            raise RegistrationRejected("a tool must declare an input or output contract")
        if manifest.is_mutating and manifest.compensation is None:
            raise RegistrationRejected(
                f"tool '{manifest.tool_id}' is mutating and declares no compensation logic (12 rule 9)"
            )
        if manifest.compensation is not None and not manifest.compensation.idempotent:
            raise RegistrationRejected(
                "compensation logic must be idempotent; a rollback that cannot be safely retried is "
                "unusable in a saga (21B §19.15 guarantee 6)"
            )
        if manifest.timeout <= timedelta(0):
            raise RegistrationRejected("a tool must declare a positive timeout")
        if manifest.cost_per_invocation < 0:
            raise RegistrationRejected("cost per invocation must not be negative")
        # Sandbox feasibility: a tool that reaches the network cannot run
        # unsandboxed, whatever its manifest claims.
        if manifest.egress_allowlist and manifest.sandbox_tier == SandboxTier.NONE:
            raise RegistrationRejected(
                f"tool '{manifest.tool_id}' declares network egress at sandbox tier NONE; egress "
                "requires at least Container isolation"
            )
        if manifest.secret_refs and manifest.sandbox_tier == SandboxTier.NONE:
            raise RegistrationRejected(
                f"tool '{manifest.tool_id}' receives secret injection at sandbox tier NONE; injection "
                "requires an isolated environment (12 rule 5)"
            )


@dataclass
class TrustEngine:
    """Composite trust score, decay, and threshold enforcement (12.16)."""

    now: Callable[[], datetime] = field(default=lambda: datetime.now(UTC))

    def recompute(self, record: ToolRecord) -> float:
        """Trust from observed reliability, seeded at 0.5 for an unproven tool."""
        if record.invocations == 0:
            return record.trust_score
        return round(min(1.0, 0.3 + 0.7 * record.success_rate), 4)

    def decay(self, record: ToolRecord) -> float:
        """12.16 — 60 days unused costs five percent, preventing stale privilege.

        "Preventing dormant high-trust tools from receiving critical
        assignments without revalidation" is the point: decay applies to
        idleness, not to failure, which `recompute` already handles.
        """
        last = record.last_invoked_at or record.manifest.registered_at
        if self.now() - last < TRUST_DECAY_IDLE:
            return record.trust_score
        return round(max(0.0, record.trust_score * (1.0 - TRUST_DECAY_FRACTION)), 4)


@dataclass
class ToolRegistry:
    """Canonical inventory of every tool. Layer 4 (21B §19.13)."""

    authorizer: RegistryAuthorizer
    signals: SignalEmitter
    now: Callable[[], datetime] = field(default=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        self.validator = RegistrationValidator()
        self.trust = TrustEngine(now=self.now)
        self.journal = ImmutableJournal()
        self._tools: dict[str, ToolRecord] = {}

    # ----------------------------------------------------------- Registration

    def register(self, token: str, manifest: ToolManifest) -> ToolRecord:
        """**Tool Registration** (21B §19.5). Consumers: Human Interface, Plugin Manager."""
        principal_id, tenant_id = self.authorizer.principal_of(token)
        if tenant_id != manifest.tenant_id:
            raise RegistrationRejected(
                f"principal '{principal_id}' may not register into tenant '{manifest.tenant_id}'"
            )
        if manifest.tool_id in self._tools:
            raise RegistrationRejected(f"tool '{manifest.tool_id}' is already registered")
        if manifest.predecessor_tool_id is not None and manifest.predecessor_tool_id not in self._tools:
            raise RegistrationRejected(
                f"predecessor '{manifest.predecessor_tool_id}' is not registered; lineage must resolve"
            )
        self.validator.validate(manifest)

        record = ToolRecord(manifest=manifest, state=ToolState.REGISTERED)
        self._tools[manifest.tool_id] = record
        self._journal(record, "registered", by=principal_id, capability=manifest.capability)
        self.signals.emit(
            SignalType.EVENT,
            "tool.registered",
            manifest.tenant_id,
            tool_id=manifest.tool_id,
            capability=manifest.capability,
            sandbox_tier=manifest.sandbox_tier.name,
        )
        return record

    def transition(self, tool_id: str, target: ToolState, reason: str = "") -> ToolRecord:
        """Guarded lifecycle transition (21B §19.3)."""
        record = self.get(tool_id)
        machine = LifecycleStateMachine(transitions=dict(TOOL_TRANSITIONS), state=record.state)
        machine.transition(target)
        record.state = target
        if target == ToolState.SUSPENDED:
            record.suspended_reason = reason
        self._journal(record, target.value, reason=reason)
        return record

    def deprecate(self, tool_id: str, successor_tool_id: str | None, notice: timedelta) -> ToolRecord:
        """Deprecation with a notice period and successor (12.29, 21B §19.3)."""
        record = self.transition(tool_id, ToolState.DEPRECATED, reason="deprecated")
        record.deprecated_at = self.now()
        record.successor_tool_id = successor_tool_id
        record.migration_deadline = self.now() + notice
        self._journal(record, "deprecation_scheduled", successor=successor_tool_id)
        return record

    # -------------------------------------------------------------- Discovery

    def discover(
        self,
        token: str,
        capability: str | None = None,
        max_cost: float | None = None,
        min_trust: float = 0.0,
        include_unhealthy: bool = False,
    ) -> list[ToolRecord]:
        """**Tool Discovery** (21B §19.5): capability, cost and reputation filtered.

        Hierarchical resolution: a query for `external.http` matches
        `external.http.fetch`, because 12.11.1 makes capability signatures
        hierarchical.
        """
        _principal_id, principal_tenant = self.authorizer.principal_of(token)
        return [
            record
            for record in self._tools.values()
            if record.manifest.tenant_id == principal_tenant
            and record.is_invocable
            and record.trust_score >= min_trust
            and (capability is None or _covers(capability, record.manifest.capability))
            and (max_cost is None or record.manifest.cost_per_invocation <= max_cost)
            and (include_unhealthy or record.availability != Availability.UNAVAILABLE)
        ]

    def get(self, tool_id: str) -> ToolRecord:
        record = self._tools.get(tool_id)
        if record is None:
            raise NotFoundError(f"tool '{tool_id}' is not registered")
        return record

    def lineage(self, tool_id: str) -> list[str]:
        """Version lineage back to the root tool (21B §19.3)."""
        chain = [tool_id]
        current = self.get(tool_id)
        while current.manifest.predecessor_tool_id is not None:
            chain.append(current.manifest.predecessor_tool_id)
            current = self.get(current.manifest.predecessor_tool_id)
        return chain

    # ----------------------------------------------------------------- Health

    def report_health(self, tool_id: str, availability: Availability) -> ToolRecord:
        """Health Monitor input: dependency liveness and endpoint responsiveness."""
        record = self.get(tool_id)
        record.availability = availability
        self._journal(record, "health", availability=availability.value)
        return record

    def health_of(self, tool_id: str) -> Mapping[str, Any]:
        """**Tool Health Query** (21B §19.5). Consumers: Workflow Engine, Observability."""
        record = self.get(tool_id)
        return {
            "tool_id": tool_id,
            "state": record.state.value,
            "availability": record.availability.value,
            "trust_score": record.trust_score,
            "autonomously_invocable": record.autonomously_invocable,
            "invocations": record.invocations,
            "success_rate": record.success_rate,
            "deprecated": record.state == ToolState.DEPRECATED,
            "successor": record.successor_tool_id,
            "migration_deadline": record.migration_deadline,
        }

    # ------------------------------------------------------------------ Trust

    def record_outcome(self, tool_id: str, succeeded: bool) -> ToolRecord:
        """Feeds the Trust Engine from observed invocation outcomes."""
        record = self.get(tool_id)
        record.invocations += 1
        if not succeeded:
            record.failures += 1
        record.last_invoked_at = self.now()
        previous = record.trust_score
        record.trust_score = self.trust.recompute(record)
        if previous >= AUTONOMOUS_TRUST_THRESHOLD > record.trust_score:
            # 21B §19.9 — suspended from autonomous use; human invocation permitted.
            self.signals.emit(
                SignalType.EVENT,
                "tool.trust.below_threshold",
                record.manifest.tenant_id,
                tool_id=tool_id,
                trust_score=record.trust_score,
            )
            self._journal(record, "trust_below_threshold", trust_score=record.trust_score)
        return record

    def decay_trust(self) -> list[ToolRecord]:
        """Applies idle decay across the inventory (12.16)."""
        decayed: list[ToolRecord] = []
        for record in self._tools.values():
            reduced = self.trust.decay(record)
            if reduced != record.trust_score:
                record.trust_score = reduced
                self._journal(record, "trust_decayed", trust_score=reduced)
                decayed.append(record)
        return decayed

    def health(self) -> Mapping[str, Any]:
        """**Tool Health Signals** (21B §19.5) — the Trust family of 12.27.1."""
        records = list(self._tools.values())
        by_state: dict[str, int] = {}
        for record in records:
            by_state[record.state.value] = by_state.get(record.state.value, 0) + 1
        return {
            "tools": len(records),
            "by_state": by_state,
            "trust": {
                "mean": round(sum(r.trust_score for r in records) / len(records), 4) if records else 0.0,
                "below_threshold": sum(1 for r in records if r.trust_score < AUTONOMOUS_TRUST_THRESHOLD),
                "suspensions": sum(1 for r in records if r.state == ToolState.SUSPENDED),
            },
            "availability": {a.value: sum(1 for r in records if r.availability == a) for a in Availability},
            "journal_entries": len(self.journal),
            "journal_intact": self.journal.verify_chain(),
        }

    def all_tools(self) -> list[ToolRecord]:
        return list(self._tools.values())

    def _journal(self, record: ToolRecord, action: str, **detail: Any) -> None:
        self.journal.append(
            {
                "kind": "tool",
                "action": action,
                "tool_id": record.tool_id,
                "tenant_id": record.manifest.tenant_id,
                "state": record.state.value,
                **detail,
            }
        )


def _covers(query: str, capability: str) -> bool:
    """Hierarchical capability match (12.11.1)."""
    return capability == query or capability.startswith(f"{query}.")


__all__ = [
    "ToolRegistry",
    "RegistryAuthorizer",
    "RegistrationValidator",
    "RegistrationRejected",
    "TrustEngine",
    "AgentOSError",
]
