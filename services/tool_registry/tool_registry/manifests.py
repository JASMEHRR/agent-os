"""Tool manifests, capability signatures, and lifecycle states (12.5, 12.9).

`12.2.1`: **"The tool is the constitutional airlock."** A manifest is the
declaration a tool makes about what it will do, how isolated it must be, and
how its effects can be undone.

Three properties are structural:

**Sandbox tier is declared, and is a floor.** 12 rule 4 forbids execution
outside the declared tier, and 21B §19.4 permits escalation but never
de-escalation. `SandboxTier` is ordered so `max` is the composition rule.

**A mutating tool without compensation cannot be registered.** 12 rule 9
admits no exception, so `compensation` is not optional on a mutating manifest
— the validator refuses it rather than warning.

**A manifest freezes at Active** (12.9.3). Behavioural change requires a new
Tool ID with lineage, never an edit, which is why the manifest is frozen and
the mutable lifecycle metadata lives beside it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import IntEnum, StrEnum
from typing import Any

#: 21B §19.8 — Invocation Records are retained seven years minimum.
INVOCATION_RETENTION = timedelta(days=365 * 7)

#: 12.16 — a tool unused for 60 days loses five percent of its trust score.
TRUST_DECAY_IDLE = timedelta(days=60)
TRUST_DECAY_FRACTION = 0.05

#: [Engineering Decision] 12.16 requires threshold enforcement without
#: publishing the figure. Below this a tool is suspended from autonomous use
#: and may be invoked only by a human (21B §19.9).
AUTONOMOUS_TRUST_THRESHOLD = 0.5


class SandboxTier(IntEnum):
    """The four isolation tiers of 12.5.1, ordered weakest to strongest.

    Ordering is load-bearing: 12.18.3 requires a composed chain to execute at
    the highest tier any component requires, which is `max` over this enum.
    """

    NONE = 0
    CONTAINER = 1
    GVISOR = 2
    FIRECRACKER = 3


class ToolEffect(StrEnum):
    """Whether a tool changes the world or only observes it."""

    OBSERVATIONAL = "observational"
    MUTATING = "mutating"


class ToolState(StrEnum):
    """Lifecycle states of 21B §19.3 (Registry Lifecycle Controller)."""

    DESIGNED = "designed"
    REGISTERED = "registered"
    VALIDATED = "validated"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    DEPRECATED = "deprecated"
    RETIRED = "retired"
    ARCHIVED = "archived"


TOOL_TRANSITIONS: dict[str, set[str]] = {
    ToolState.DESIGNED: {ToolState.REGISTERED},
    ToolState.REGISTERED: {ToolState.VALIDATED, ToolState.RETIRED},
    ToolState.VALIDATED: {ToolState.ACTIVE, ToolState.RETIRED},
    ToolState.ACTIVE: {ToolState.SUSPENDED, ToolState.DEPRECATED, ToolState.RETIRED},
    ToolState.SUSPENDED: {ToolState.ACTIVE, ToolState.RETIRED},
    ToolState.DEPRECATED: {ToolState.RETIRED},
    ToolState.RETIRED: {ToolState.ARCHIVED},
    ToolState.ARCHIVED: set(),
}


class Availability(StrEnum):
    """Health Monitor states (21B §19.3)."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class Contract:
    """An input or output contract: field name to expected Python type.

    Both directions are validated. 12.25.4 treats external return data as
    untrusted until validated — output is often assumed safe because the tool
    was authorized, which is exactly the mistake this prevents.
    """

    fields: dict[str, type]

    def validate(self, payload: dict[str, Any]) -> list[str]:
        errors: list[str] = []
        for name, expected in self.fields.items():
            if name not in payload:
                errors.append(f"missing required field '{name}'")
            elif not isinstance(payload[name], expected):
                errors.append(f"field '{name}' expected {expected.__name__}, got {type(payload[name]).__name__}")
        return errors


@dataclass(frozen=True)
class Compensation:
    """Pre-positioned logic that undoes a mutating tool's effect (12 rule 9).

    `idempotent` is required rather than assumed: 21B §19.15 guarantee 6 calls
    for "validated, idempotent compensation logic", and a compensation that
    cannot be safely retried is not usable during a saga rollback.
    """

    reference: str
    idempotent: bool
    description: str


@dataclass(frozen=True)
class ToolManifest:
    """A tool's frozen declaration (12.9.3, immutable from Active)."""

    tool_id: str
    name: str
    version: str
    #: Hierarchical capability signature, e.g. "external.http.fetch".
    capability: str
    effect: ToolEffect
    sandbox_tier: SandboxTier
    input_contract: Contract
    output_contract: Contract
    owner_principal_id: str
    tenant_id: str
    #: Estimated cost per invocation, for the Gateway's pre-flight check.
    cost_per_invocation: float
    #: Maximum wall-clock the Executor permits before hard termination.
    timeout: timedelta
    compensation: Compensation | None = None
    #: The capability abstraction this tool consumes, if it reaches outside
    #: (17.6.3). The Gateway verifies it is backed by an active integration.
    integration_abstraction: str | None = None
    #: Network destinations the Executor allowlists. Deny-by-default (21B §19.3).
    egress_allowlist: tuple[str, ...] = ()
    #: Secret references the Executor may inject. Values never appear here.
    secret_refs: tuple[str, ...] = ()
    predecessor_tool_id: str | None = None
    registered_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def is_mutating(self) -> bool:
        return self.effect == ToolEffect.MUTATING


@dataclass
class ToolRecord:
    """Mutable lifecycle metadata for a registered tool."""

    manifest: ToolManifest
    state: ToolState = ToolState.REGISTERED
    trust_score: float = 0.5
    availability: Availability = Availability.UNKNOWN
    invocations: int = 0
    failures: int = 0
    last_invoked_at: datetime | None = None
    suspended_reason: str | None = None
    deprecated_at: datetime | None = None
    successor_tool_id: str | None = None
    migration_deadline: datetime | None = None

    @property
    def tool_id(self) -> str:
        return self.manifest.tool_id

    @property
    def is_invocable(self) -> bool:
        """Only an Active tool may be invoked. Discoverability is not authorization."""
        return self.state == ToolState.ACTIVE

    @property
    def autonomously_invocable(self) -> bool:
        """21B §19.9 — below the trust threshold, human-only invocation."""
        return self.is_invocable and self.trust_score >= AUTONOMOUS_TRUST_THRESHOLD

    @property
    def success_rate(self) -> float:
        if self.invocations == 0:
            return 0.0
        return round((self.invocations - self.failures) / self.invocations, 4)
