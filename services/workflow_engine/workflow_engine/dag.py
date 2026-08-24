"""Execution DAG, workflow states, and the Planning subsystem (21B §14).

`07.13.1`: **"The orchestrator does not perform work; it governs work."**

21B §14.4: **"Planning is cheap and Running is expensive."** 07.12.1 spells
out why — "A workflow that fails during Planning has not yet consumed agent
labor, LLM tokens, or external API calls." So every failure mode detectable
before execution is detected in Planning, and a workflow that cannot succeed
never enters Running.

**Determinism discipline** (07.13.5) is the single most easily violated
constraint here. Non-deterministic inputs — current time, random values,
external readings — are injected as explicit workflow variables and never
derived inside orchestration logic. `WorkflowContext.variables` is where they
live, and `Activity` carries no clock.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any

from core.exceptions import ValidationError


class WorkflowState(StrEnum):
    """Canonical workflow states (07.14)."""

    TRIGGERED = "triggered"
    PLANNING = "planning"
    RUNNING = "running"
    PAUSED = "paused"
    COMPENSATING = "compensating"
    COMPLETED = "completed"
    FAILED = "failed"
    STALLED = "stalled"
    CANCELLED = "cancelled"


WORKFLOW_TRANSITIONS: dict[str, set[str]] = {
    WorkflowState.TRIGGERED: {WorkflowState.PLANNING, WorkflowState.FAILED},
    # Planning failure goes straight to Failed: nothing was consumed, so
    # there is nothing to compensate (21B §14.9).
    WorkflowState.PLANNING: {WorkflowState.RUNNING, WorkflowState.FAILED},
    WorkflowState.RUNNING: {
        WorkflowState.PAUSED,
        WorkflowState.COMPENSATING,
        WorkflowState.COMPLETED,
        WorkflowState.FAILED,
        WorkflowState.CANCELLED,
    },
    WorkflowState.PAUSED: {WorkflowState.RUNNING, WorkflowState.CANCELLED, WorkflowState.COMPENSATING},
    WorkflowState.COMPENSATING: {WorkflowState.FAILED, WorkflowState.STALLED},
    WorkflowState.COMPLETED: set(),
    WorkflowState.FAILED: set(),
    # A stalled compensation requires human intervention — never silent
    # abandonment (21B §14.4).
    WorkflowState.STALLED: {WorkflowState.COMPENSATING, WorkflowState.FAILED},
    WorkflowState.CANCELLED: set(),
}


class ActivityKind(StrEnum):
    """What an activity does. The kind determines who fulfils it."""

    AGENT = "agent"
    TOOL = "tool"
    #: A human approval gate is a first-class DAG activity (21B §14.2), not a
    #: side channel — which is what lets a workflow pause durably on one.
    HUMAN_GATE = "human_gate"
    CHECKPOINT = "checkpoint"


class ActivityState(StrEnum):
    PENDING = "pending"
    DISPATCHED = "dispatched"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    COMPENSATED = "compensated"
    SKIPPED = "skipped"


@dataclass(frozen=True)
class Activity:
    """One node in the Execution DAG.

    Carries no clock and no randomness. Anything non-deterministic arrives
    through `WorkflowContext.variables`, which is what makes replay
    reconstruct the same traversal (07.13.5).
    """

    activity_id: str
    kind: ActivityKind
    #: Capability the bound agent must hold, for an AGENT activity.
    capability: str | None = None
    tool_id: str | None = None
    depends_on: tuple[str, ...] = ()
    #: Whether this activity changes the world. Mutating activities are what
    #: compensation exists for.
    mutating: bool = False
    estimated_cost: float = 0.0
    max_retries: int = 2
    timeout: timedelta = timedelta(minutes=5)
    #: Set on a HUMAN_GATE: the decision class the approval carries.
    decision_class: str = "C"
    inputs: dict[str, str] = field(default_factory=dict)


@dataclass
class ActivityRecord:
    """Mutable execution state for one activity."""

    activity: Activity
    state: ActivityState = ActivityState.PENDING
    attempts: int = 0
    bound_agent_id: str | None = None
    outcome: Any = None
    cost: float = 0.0
    invocation_id: str | None = None
    failure: str | None = None
    completed_at: datetime | None = None

    @property
    def activity_id(self) -> str:
        return self.activity.activity_id


@dataclass(frozen=True)
class WorkflowContext:
    """Everything the workflow was given, including its non-determinism.

    07.13.5's determinism requirement lives here: `variables` holds the
    current time, random seeds and external readings the workflow needs, so
    orchestration logic can be a pure function of trigger plus context plus
    event sequence.
    """

    workflow_id: str
    tenant_id: str
    trigger: str
    triggered_by: str
    variables: dict[str, str] = field(default_factory=dict)
    version: int = 1


@dataclass(frozen=True)
class WorkflowDefinition:
    """A versioned workflow definition (21B §14.3).

    A running workflow is pinned to the version it started under, so a
    definition change never rewrites a workflow already in flight.
    """

    name: str
    version: str
    activities: tuple[Activity, ...]
    global_timeout: timedelta = timedelta(hours=24)


class PlanningFailure(ValidationError):
    """Detected before execution, so nothing has been consumed (07.12.1)."""


@dataclass
class ExecutionDAG:
    """The validated plan. Constructed and checked entirely during Planning."""

    definition: WorkflowDefinition
    records: dict[str, ActivityRecord]

    @staticmethod
    def build(definition: WorkflowDefinition) -> ExecutionDAG:
        """DAG Constructor plus Validator (21B §14.3).

        Validates acyclicity and dependency resolution here rather than
        discovering a cycle mid-run, when agent labour has already been spent.
        """
        if not definition.activities:
            raise PlanningFailure(f"workflow '{definition.name}' declares no activities")
        ids = [a.activity_id for a in definition.activities]
        if len(set(ids)) != len(ids):
            raise PlanningFailure("activity identifiers must be distinct")
        known = set(ids)
        for activity in definition.activities:
            for dependency in activity.depends_on:
                if dependency not in known:
                    raise PlanningFailure(
                        f"activity '{activity.activity_id}' depends on '{dependency}', which is not in the DAG"
                    )
            if activity.kind == ActivityKind.AGENT and not activity.capability:
                raise PlanningFailure(f"agent activity '{activity.activity_id}' declares no capability")
            if activity.kind == ActivityKind.TOOL and not activity.tool_id:
                raise PlanningFailure(f"tool activity '{activity.activity_id}' names no tool")
        _assert_acyclic(definition.activities)
        return ExecutionDAG(
            definition=definition,
            records={a.activity_id: ActivityRecord(activity=a) for a in definition.activities},
        )

    def ready(self) -> list[ActivityRecord]:
        """Activities whose dependencies are all satisfied (21B §14.4)."""
        return [
            record
            for record in self.records.values()
            if record.state == ActivityState.PENDING
            and all(self.records[d].state == ActivityState.SUCCEEDED for d in record.activity.depends_on)
        ]

    def blocked_by_failure(self) -> list[ActivityRecord]:
        """Pending activities whose dependencies cannot now succeed."""
        return [
            record
            for record in self.records.values()
            if record.state == ActivityState.PENDING
            and any(self.records[d].state == ActivityState.FAILED for d in record.activity.depends_on)
        ]

    def completed_mutating(self) -> list[ActivityRecord]:
        """Successful mutating activities, newest first — compensation order.

        21B §14.4: compensations run in **reverse chronological order**, so an
        earlier activity is never undone before a later one that depended on
        it.
        """
        done = [
            r
            for r in self.records.values()
            if r.state == ActivityState.SUCCEEDED and r.activity.mutating and r.completed_at is not None
        ]
        return sorted(done, key=lambda r: r.completed_at or datetime.min.replace(tzinfo=UTC), reverse=True)

    def has_failure(self) -> bool:
        """Whether any activity has exhausted its retries.

        Distinct from `blocked_by_failure`, which only finds *dependents* of a
        failure. A terminal activity that fails has no dependents, so without
        this the workflow would sit in Running with nothing left to dispatch.
        """
        return any(r.state == ActivityState.FAILED for r in self.records.values())

    def all_succeeded(self) -> bool:
        return all(r.state in (ActivityState.SUCCEEDED, ActivityState.SKIPPED) for r in self.records.values())

    def worst_case_cost(self) -> float:
        """Budget Pre-Allocator: worst case including retries and compensation.

        21B §14.3 asks for exactly this. Pre-allocating the optimistic cost
        would let a workflow enter Running that cannot afford to finish, which
        is the failure Planning exists to prevent.
        """
        total = 0.0
        for activity in self.definition.activities:
            attempts = 1 + activity.max_retries
            total += activity.estimated_cost * attempts
            if activity.mutating:
                total += activity.estimated_cost  # the compensation itself
        return round(total, 6)

    def human_gates(self) -> list[Activity]:
        return [a for a in self.definition.activities if a.kind == ActivityKind.HUMAN_GATE]


def _assert_acyclic(activities: tuple[Activity, ...]) -> None:
    """Depth-first cycle detection. A cycle is a Planning failure, always."""
    edges = {a.activity_id: set(a.depends_on) for a in activities}
    visiting: set[str] = set()
    visited: set[str] = set()

    def walk(node: str, path: tuple[str, ...]) -> None:
        if node in visiting:
            cycle = " -> ".join([*path, node])
            raise PlanningFailure(f"the Execution DAG is cyclic: {cycle}")
        if node in visited:
            return
        visiting.add(node)
        for dependency in edges.get(node, set()):
            walk(dependency, (*path, node))
        visiting.discard(node)
        visited.add(node)

    for activity_id in edges:
        walk(activity_id, ())
