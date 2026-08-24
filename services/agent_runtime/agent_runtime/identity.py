"""The Identity Plane — durable, long-lived (21B §13.4, realizes 06.3, 06.6).

21B §13.4 splits the Runtime into two planes, and the split is what reconciles
the system's two facts about agents. `06.2.1` calls an agent "a persistent
digital worker with an identity, a specialty, a reputation, and a career
trajectory"; `02.3.2` says agents "are not long-running processes. They are
stateless workers that wake up in response to workflow tasks."

This plane holds the durable half. `06.3.2`: "When an agent is not executing,
its identity remains active in the registry." An Idle, Suspended, Retired or
Archived agent exists entirely here.

The manifest is **immutable once registered** (06.5.1). Behavioural change
requires a new version with lineage, never an edit — so the manifest is frozen
and the mutable reputation and lifecycle metadata live beside it.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum

from core.exceptions import ValidationError
from kernel.authority import AuthorityLevel

#: [Engineering Decision] 06.9.4 requires a suspension threshold for repeated
#: schema violation without publishing the count.
SCHEMA_VIOLATION_SUSPENSION_THRESHOLD = 3

#: [Engineering Decision] 06.17 requires reputation decay without a figure.
REPUTATION_DECAY_IDLE = timedelta(days=30)
REPUTATION_DECAY_FRACTION = 0.05

#: 02.4.8 — heartbeat cadence during execution, and stall detection at 2x the
#: activity timeout.
HEARTBEAT_CADENCE = timedelta(seconds=30)
STALL_MULTIPLIER = 2


class AgentState(StrEnum):
    """Agent lifecycle states (06.6)."""

    DESIGNED = "designed"
    REGISTERED = "registered"
    IDLE = "idle"
    EXECUTING = "executing"
    SUSPENDED = "suspended"
    RETIRED = "retired"
    ARCHIVED = "archived"


AGENT_TRANSITIONS: dict[str, set[str]] = {
    AgentState.DESIGNED: {AgentState.REGISTERED},
    AgentState.REGISTERED: {AgentState.IDLE, AgentState.RETIRED},
    AgentState.IDLE: {AgentState.EXECUTING, AgentState.SUSPENDED, AgentState.RETIRED},
    AgentState.EXECUTING: {AgentState.IDLE, AgentState.SUSPENDED},
    AgentState.SUSPENDED: {AgentState.IDLE, AgentState.RETIRED},
    AgentState.RETIRED: {AgentState.ARCHIVED},
    AgentState.ARCHIVED: set(),
}


@dataclass(frozen=True)
class AuthorityBoundaries:
    """The six declared boundaries of 06.9.6.

    An agent acts within the **intersection** of all six — capability
    signature, tool inventory, memory scope, autonomy level, cost budget, and
    workspace. Intersection, not union, exactly as 14.12.4 requires
    everywhere else in the system.
    """

    capabilities: frozenset[str]
    tool_inventory: frozenset[str]
    memory_scope: frozenset[str]
    autonomy_level: AuthorityLevel
    cost_budget: float
    workspace_ids: frozenset[str]

    def permits_capability(self, capability: str) -> bool:
        return any(capability == c or capability.startswith(f"{c}.") for c in self.capabilities)

    def permits_tool(self, tool_id: str) -> bool:
        """12.32.1 — the Runtime does not select tools beyond the registered inventory."""
        return tool_id in self.tool_inventory


@dataclass(frozen=True)
class AgentManifest:
    """An agent's frozen declaration (06.5.1, immutable once registered)."""

    agent_id: str
    name: str
    version: str
    tenant_id: str
    specialty: str
    boundaries: AuthorityBoundaries
    #: Prompt template the Prompt Renderer uses.
    prompt_template: str
    #: Output contract: field name to expected type. Validated before anything
    #: propagates (21B §13.15 guarantee 5).
    output_contract: dict[str, type]
    max_context_tokens: int
    max_context_assembly_time: timedelta
    activity_timeout: timedelta
    predecessor_agent_id: str | None = None
    registered_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class AgentRecord:
    """Mutable identity-plane metadata for one agent."""

    manifest: AgentManifest
    state: AgentState = AgentState.REGISTERED
    reputation: float = 0.5
    executions: int = 0
    failures: int = 0
    schema_violations: int = 0
    last_executed_at: datetime | None = None
    suspended_reason: str | None = None
    #: Drift baseline: mean tool calls and mean latency, recomputed from history.
    baseline_tool_calls: float = 0.0
    baseline_latency_seconds: float = 0.0

    @property
    def agent_id(self) -> str:
        return self.manifest.agent_id

    @property
    def is_assignable(self) -> bool:
        """Only an Idle agent may be bound to an activity."""
        return self.state == AgentState.IDLE

    @property
    def success_rate(self) -> float:
        if self.executions == 0:
            return 0.0
        return round((self.executions - self.failures) / self.executions, 4)


@dataclass
class ReputationEngine:
    """Success rate, reputation, decay, assignment eligibility (06.17)."""

    now: Callable[[], datetime] = field(default=lambda: datetime.now(UTC))

    def recompute(self, record: AgentRecord) -> float:
        if record.executions == 0:
            return record.reputation
        return round(min(1.0, 0.3 + 0.7 * record.success_rate), 4)

    def decay(self, record: AgentRecord) -> float:
        """Idle reputation decay, so a dormant agent does not keep stale standing."""
        last = record.last_executed_at or record.manifest.registered_at
        if self.now() - last < REPUTATION_DECAY_IDLE:
            return record.reputation
        return round(max(0.0, record.reputation * (1.0 - REPUTATION_DECAY_FRACTION)), 4)


@dataclass(frozen=True)
class DriftReading:
    """One drift assessment across the dimensions 21B §13.3 names."""

    agent_id: str
    tool_call_deviation: float
    latency_deviation: float
    schema_adherence: float
    drifted: bool
    detail: str


@dataclass
class DriftMonitor:
    """Detects deviation in tool usage, latency, and schema adherence (06.17.5).

    Deliberately conservative: it reports deviation from an agent's own
    baseline rather than from a population, because 06.19.2 is concerned with
    an agent changing, not with an agent differing from its peers.
    """

    #: [Engineering Decision] 06.17.5 requires drift detection without a
    #: threshold. Half again the baseline is the starting value.
    deviation_threshold: float = 0.5

    def assess(self, record: AgentRecord, tool_calls: int, latency_seconds: float) -> DriftReading:
        tool_deviation = _relative(tool_calls, record.baseline_tool_calls)
        latency_deviation = _relative(latency_seconds, record.baseline_latency_seconds)
        adherence = round(1.0 - record.schema_violations / record.executions, 4) if record.executions else 1.0
        reasons: list[str] = []
        if tool_deviation > self.deviation_threshold:
            reasons.append(f"tool-call count deviates {tool_deviation:.0%} from baseline")
        if latency_deviation > self.deviation_threshold:
            reasons.append(f"latency deviates {latency_deviation:.0%} from baseline")
        if adherence < 0.8:
            reasons.append(f"schema adherence has fallen to {adherence:.0%}")
        return DriftReading(
            agent_id=record.agent_id,
            tool_call_deviation=round(tool_deviation, 4),
            latency_deviation=round(latency_deviation, 4),
            schema_adherence=adherence,
            drifted=bool(reasons),
            detail="; ".join(reasons) or "within baseline",
        )

    def update_baseline(self, record: AgentRecord, tool_calls: int, latency_seconds: float) -> None:
        """Exponential moving baseline, so a single outlier does not reset it."""
        if record.executions <= 1:
            record.baseline_tool_calls = float(tool_calls)
            record.baseline_latency_seconds = latency_seconds
            return
        record.baseline_tool_calls = round(0.8 * record.baseline_tool_calls + 0.2 * tool_calls, 4)
        record.baseline_latency_seconds = round(0.8 * record.baseline_latency_seconds + 0.2 * latency_seconds, 4)


def _relative(observed: float, baseline: float) -> float:
    if baseline <= 0:
        return 0.0
    return abs(observed - baseline) / baseline


@dataclass
class ManifestLoader:
    """Parses and validates agent manifests; rejects invalid ones (21B §13.3)."""

    def validate(self, manifest: AgentManifest) -> None:
        if not manifest.agent_id or not manifest.tenant_id:
            raise ValidationError("an agent manifest must declare an agent id and a tenant")
        if not manifest.boundaries.capabilities:
            raise ValidationError(f"agent '{manifest.agent_id}' declares no capability signature; it could do nothing")
        if not manifest.output_contract:
            raise ValidationError(
                f"agent '{manifest.agent_id}' declares no output contract; unvalidated output may not "
                "propagate (21B §13.15 guarantee 5)"
            )
        if manifest.max_context_tokens <= 0:
            raise ValidationError("max_context_tokens must be positive")
        if manifest.activity_timeout <= timedelta(0):
            raise ValidationError("activity_timeout must be positive")
        if manifest.boundaries.cost_budget < 0:
            raise ValidationError("cost budget must not be negative")
