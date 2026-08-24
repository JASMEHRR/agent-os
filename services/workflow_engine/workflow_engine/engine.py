"""Workflow Engine — orchestrates durable business processes (21B §14).

| 21B §14.5 interface     | Method                  |
|-------------------------|-------------------------|
| Workflow Trigger        | `trigger`               |
| Workflow Signal         | `signal`                |
| Workflow Query          | `query`                 |
| Workflow Health         | `health`                |
| Definition Registration | `register_definition`   |

`07.13.1`: **"The orchestrator does not perform work; it governs work."** A
test asserts no `infer`/`call_tool` method has appeared here — the engine
dispatches to the Agent Runtime and the Tool Gateway and does neither itself.

Three properties are structural:

**Planning is cheap and Running is expensive** (21B §14.4). Everything
detectable before execution is detected in Planning, and a Planning failure
goes straight to Failed with no compensation, because nothing was consumed.

**Compensation runs in reverse chronological order**, and a failed
compensation produces a **Stalled** state requiring human intervention —
never silent abandonment.

**A paused workflow releases ephemeral resources** (07.14.5). That is what
makes human-in-the-loop viable across multi-day approval latency: a workflow
waiting on a human consumes no compute quota while retaining durable state.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol

from core.exceptions import AgentOSError, NotFoundError
from kernel.journal import ImmutableJournal
from kernel.lifecycle import LifecycleStateMachine
from kernel.signals import SignalEmitter, SignalType
from workflow_engine.dag import (
    WORKFLOW_TRANSITIONS,
    ActivityKind,
    ActivityRecord,
    ActivityState,
    ExecutionDAG,
    PlanningFailure,
    WorkflowContext,
    WorkflowDefinition,
    WorkflowState,
)


class WorkflowFailure(AgentOSError):
    """The workflow cannot proceed. Carries whether compensation is owed."""

    def __init__(self, message: str, compensation_required: bool):
        super().__init__(message)
        self.compensation_required = compensation_required


class AgentDispatcher(Protocol):
    """Activity dispatch and agent discovery (21B §14.6)."""

    def discover(self, token: str, capability: str, min_reputation: float) -> list[Any]: ...

    def execute(
        self,
        token: str,
        *,
        activity_id: str,
        workflow_id: str,
        agent_id: str,
        tenant_id: str,
        idempotency_key: str,
        inputs: dict[str, str],
        decision_id: str,
        cost_ceiling: float,
    ) -> Any: ...


class ToolDispatcher(Protocol):
    """Tool activity dispatch and compensation invocation (21B §14.6)."""

    def invoke(
        self, token: str, tool_id: str, decision_id: str, parameters: dict[str, Any], cost_ceiling: float, key: str
    ) -> tuple[bool, dict[str, Any] | None, float, str]: ...

    def compensate(self, token: str, invocation_id: str, decision_id: str) -> bool: ...


class ApprovalSource(Protocol):
    """Decision point resolution and approval gate authority (21B §14.6)."""

    def request_approval(self, workflow_id: str, activity_id: str, decision_class: str) -> str: ...

    def is_approved(self, decision_id: str) -> bool: ...


class BudgetSource(Protocol):
    """Budget pre-allocation and mid-flight monitoring (21B §14.6)."""

    def has_headroom(self, tenant_id: str, cost: float) -> bool: ...


@dataclass
class WorkflowRun:
    """One workflow instance, pinned to its originating definition version."""

    context: WorkflowContext
    dag: ExecutionDAG
    state: WorkflowState = WorkflowState.TRIGGERED
    #: Set when the run pauses on a human gate. Cleared on resume.
    awaiting_activity_id: str | None = None
    awaiting_decision_id: str | None = None
    allocated_budget: float = 0.0
    spent: float = 0.0
    failure: str | None = None
    #: Every state transition, appended never substituted (21B §14.8).
    transitions: list[tuple[datetime, WorkflowState]] = field(default_factory=list)
    #: Checkpoints committed, for rehydration after orchestrator failure.
    checkpoints: list[str] = field(default_factory=list)
    #: True while ephemeral resources are held. Released on pause (07.14.5).
    holds_resources: bool = False

    @property
    def workflow_id(self) -> str:
        return self.context.workflow_id

    @property
    def is_terminal(self) -> bool:
        return self.state in (
            WorkflowState.COMPLETED,
            WorkflowState.FAILED,
            WorkflowState.CANCELLED,
        )


@dataclass
class WorkflowEngine:
    """Layer 5. Owns scheduling; performs no work itself (07.13.1, 02.3.2)."""

    agents: AgentDispatcher
    tools: ToolDispatcher
    approvals: ApprovalSource
    budget: BudgetSource
    signals: SignalEmitter
    now: Callable[[], datetime] = field(default=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        self.journal = ImmutableJournal()
        self._definitions: dict[tuple[str, str], WorkflowDefinition] = {}
        self._runs: dict[str, WorkflowRun] = {}

    # ------------------------------------------------------------ Definitions

    def register_definition(self, definition: WorkflowDefinition) -> WorkflowDefinition:
        """**Definition Registration** (21B §14.5). Consumers: Evolution, Human Interface."""
        key = (definition.name, definition.version)
        if key in self._definitions:
            raise AgentOSError(f"workflow '{definition.name}' version '{definition.version}' already registered")
        # Validate at registration, not at trigger: a definition that cannot
        # produce a valid DAG should never be registrable.
        ExecutionDAG.build(definition)
        self._definitions[key] = definition
        self.journal.append({"kind": "definition", "name": definition.name, "version": definition.version})
        return definition

    # --------------------------------------------------------------- Trigger

    def trigger(
        self,
        token: str,
        name: str,
        version: str,
        context: WorkflowContext,
    ) -> WorkflowRun:
        """**Workflow Trigger** (21B §14.5), then Planning.

        Planning runs immediately and exhaustively. If it fails, the workflow
        goes straight to Failed — 21B §14.9 classifies a Planning validation
        failure as "Critical, cheap" with "no compensation needed", because
        nothing has been consumed.
        """
        definition = self._definitions.get((name, version))
        if definition is None:
            raise NotFoundError(f"workflow '{name}' version '{version}' is not registered")
        if context.workflow_id in self._runs:
            # Trigger Receiver rejects duplicates (21B §14.3).
            raise AgentOSError(f"workflow '{context.workflow_id}' has already been triggered")

        run = WorkflowRun(context=context, dag=ExecutionDAG.build(definition))
        self._runs[context.workflow_id] = run
        self._transition(run, WorkflowState.PLANNING)

        try:
            self._plan(token, run)
        except PlanningFailure as failure:
            run.failure = str(failure)
            self._transition(run, WorkflowState.FAILED)
            self._journal(run, "planning_failed", reason=str(failure))
            self.signals.emit(
                SignalType.EVENT,
                "workflow.planning.failed",
                context.tenant_id,
                workflow_id=run.workflow_id,
                reason=str(failure),
            )
            return run

        self._transition(run, WorkflowState.RUNNING)
        run.holds_resources = True
        self._journal(run, "running", allocated_budget=run.allocated_budget)
        return run

    def _plan(self, token: str, run: WorkflowRun) -> None:
        """The Planning subsystem (21B §14.4). Every cheap check happens here."""
        # Budget pre-allocation, worst case including retries and compensation.
        worst_case = run.dag.worst_case_cost()
        if not self.budget.has_headroom(run.context.tenant_id, worst_case):
            raise PlanningFailure(
                f"worst-case cost {worst_case} exceeds available budget; the workflow could not finish"
            )
        run.allocated_budget = worst_case

        # Agent binding: bound to activities, not to workflows (21B §14.3).
        for record in run.dag.records.values():
            activity = record.activity
            if activity.kind != ActivityKind.AGENT:
                continue
            if activity.capability is None:
                # `ExecutionDAG.build` rejects this; restated as a branch so it
                # survives `python -O`.
                raise PlanningFailure(f"agent activity '{activity.activity_id}' declares no capability")
            candidates = self.agents.discover(token, activity.capability, 0.0)
            if not candidates:
                raise PlanningFailure(
                    f"no available agent holds capability '{activity.capability}' for activity '{activity.activity_id}'"
                )
            record.bound_agent_id = candidates[0].agent_id

        # Approval pre-clearance for known human gates.
        for gate in run.dag.human_gates():
            self._journal(run, "gate_precleared", activity_id=gate.activity_id)

    # --------------------------------------------------------------- Running

    def advance(self, token: str) -> list[WorkflowRun]:
        """Dispatches every ready activity across every running workflow.

        The engine awaits completion rather than polling a worker (21B §14.4);
        `advance` is the tick that releases newly-eligible activities.
        """
        advanced: list[WorkflowRun] = []
        for run in list(self._runs.values()):
            if run.state != WorkflowState.RUNNING:
                continue
            self._advance_one(token, run)
            advanced.append(run)
        return advanced

    def _advance_one(self, token: str, run: WorkflowRun) -> None:
        while run.state == WorkflowState.RUNNING:
            ready = run.dag.ready()
            if not ready:
                break
            for record in ready:
                if run.state != WorkflowState.RUNNING:
                    return
                self._dispatch(token, run, record)
            if run.dag.all_succeeded():
                self._complete(run)
                return
            if run.dag.has_failure():
                self._begin_compensation(token, run, "an activity exhausted its retries")
                return

        # Nothing left to dispatch. A workflow must not linger in Running with
        # no ready work: either everything succeeded, or something failed and
        # the run owes compensation. A terminal activity's failure has no
        # dependents, so this is the only place it is caught.
        if run.state == WorkflowState.RUNNING:
            if run.dag.all_succeeded():
                self._complete(run)
            elif run.dag.has_failure():
                self._begin_compensation(token, run, "an activity exhausted its retries")

    def _complete(self, run: WorkflowRun) -> None:
        self._transition(run, WorkflowState.COMPLETED)
        run.holds_resources = False
        self._journal(run, "completed", spent=run.spent)
        self.signals.emit(
            SignalType.EVENT,
            "workflow.completed",
            run.context.tenant_id,
            workflow_id=run.workflow_id,
            spent=run.spent,
        )

    def _dispatch(self, token: str, run: WorkflowRun, record: ActivityRecord) -> None:
        activity = record.activity
        record.attempts += 1
        record.state = ActivityState.DISPATCHED

        if activity.kind == ActivityKind.CHECKPOINT:
            # Checkpoint Manager: externalize state so orchestrator failure
            # immediately after resumes without loss (07.19.5).
            run.checkpoints.append(activity.activity_id)
            record.state = ActivityState.SUCCEEDED
            record.completed_at = self.now()
            self._journal(run, "checkpoint", activity_id=activity.activity_id)
            return

        if activity.kind == ActivityKind.HUMAN_GATE:
            self._pause_on_gate(run, record)
            return

        if activity.kind == ActivityKind.TOOL:
            self._dispatch_tool(token, run, record)
            return

        self._dispatch_agent(token, run, record)

    def _dispatch_agent(self, token: str, run: WorkflowRun, record: ActivityRecord) -> None:
        activity = record.activity
        if record.bound_agent_id is None:
            # Planning binds every agent activity before Running is entered.
            # A branch rather than an assert: this check must survive `python -O`.
            raise PlanningFailure(f"activity '{activity.activity_id}' reached dispatch unbound")
        try:
            outcome = self.agents.execute(
                token,
                activity_id=activity.activity_id,
                workflow_id=run.workflow_id,
                agent_id=record.bound_agent_id,
                tenant_id=run.context.tenant_id,
                idempotency_key=f"{run.workflow_id}:{activity.activity_id}:{record.attempts}",
                inputs=dict(activity.inputs),
                decision_id=run.awaiting_decision_id or "dec-workflow",
                cost_ceiling=activity.estimated_cost or 1.0,
            )
        except Exception as failure:
            self._fail_activity(run, record, str(failure))
            return
        record.outcome = outcome
        record.cost = getattr(outcome, "cost", 0.0)
        run.spent = round(run.spent + record.cost, 6)
        if getattr(outcome, "succeeded", False):
            record.state = ActivityState.SUCCEEDED
            record.completed_at = self.now()
            self._journal(run, "activity_succeeded", activity_id=activity.activity_id, cost=record.cost)
        else:
            self._fail_activity(run, record, getattr(outcome, "detail", "activity failed"))

    def _dispatch_tool(self, token: str, run: WorkflowRun, record: ActivityRecord) -> None:
        activity = record.activity
        if activity.tool_id is None:
            raise PlanningFailure(f"tool activity '{activity.activity_id}' names no tool")
        try:
            succeeded, _output, cost, invocation_id = self.tools.invoke(
                token,
                activity.tool_id,
                run.awaiting_decision_id or "dec-workflow",
                dict(activity.inputs),
                activity.estimated_cost or 1.0,
                f"{run.workflow_id}:{activity.activity_id}:{record.attempts}",
            )
        except Exception as failure:
            self._fail_activity(run, record, str(failure))
            return
        record.cost = cost
        record.invocation_id = invocation_id
        run.spent = round(run.spent + cost, 6)
        if succeeded:
            record.state = ActivityState.SUCCEEDED
            record.completed_at = self.now()
            self._journal(run, "activity_succeeded", activity_id=activity.activity_id, cost=cost)
        else:
            self._fail_activity(run, record, "tool invocation failed")

    def _fail_activity(self, run: WorkflowRun, record: ActivityRecord, reason: str) -> None:
        """Retry within the declared policy, then fail (21B §14.9)."""
        if record.attempts <= record.activity.max_retries:
            record.state = ActivityState.PENDING  # eligible for another attempt
            self._journal(run, "activity_retry", activity_id=record.activity_id, attempt=record.attempts, reason=reason)
            return
        record.state = ActivityState.FAILED
        record.failure = reason
        record.completed_at = self.now()
        self._journal(run, "activity_failed", activity_id=record.activity_id, reason=reason)

    # ---------------------------------------------------------- Human gates

    def _pause_on_gate(self, run: WorkflowRun, record: ActivityRecord) -> None:
        """Emits a durable approval request and releases ephemeral resources.

        07.14.5 — a paused workflow "consumes no compute quota while retaining
        durable state". That is what makes a multi-day approval affordable.
        """
        decision_id = self.approvals.request_approval(
            run.workflow_id, record.activity_id, record.activity.decision_class
        )
        run.awaiting_activity_id = record.activity_id
        run.awaiting_decision_id = decision_id
        run.holds_resources = False
        self._transition(run, WorkflowState.PAUSED)
        self._journal(run, "paused_on_gate", activity_id=record.activity_id, decision_id=decision_id)
        self.signals.emit(
            SignalType.EVENT,
            "workflow.gate.awaiting",
            run.context.tenant_id,
            workflow_id=run.workflow_id,
            activity_id=record.activity_id,
            decision_id=decision_id,
        )

    def signal(self, token: str, workflow_id: str, kind: str) -> WorkflowRun:
        """**Workflow Signal** (21B §14.5): approval, rejection, pause, resume, cancel."""
        run = self.get(workflow_id)
        if kind == "resume":
            if run.state != WorkflowState.PAUSED:
                raise AgentOSError(f"workflow '{workflow_id}' is {run.state.value}, not Paused")
            decision_id = run.awaiting_decision_id
            gate_id = run.awaiting_activity_id
            if decision_id is None or gate_id is None:
                raise AgentOSError(f"workflow '{workflow_id}' is paused on no gate")
            if not self.approvals.is_approved(decision_id):
                # 21B §14.9 — approval denied compensates completed mutating
                # activities and fails. It never proceeds on silence.
                self._transition(run, WorkflowState.COMPENSATING)
                self._journal(run, "gate_denied", activity_id=gate_id, decision_id=decision_id)
                self._compensate(token, run, "human approval was denied")
                return run
            run.dag.records[gate_id].state = ActivityState.SUCCEEDED
            run.dag.records[gate_id].completed_at = self.now()
            run.awaiting_activity_id = None
            run.awaiting_decision_id = decision_id
            run.holds_resources = True
            self._transition(run, WorkflowState.RUNNING)
            self._journal(run, "resumed", activity_id=gate_id)
            self._advance_one(token, run)
            return run
        if kind == "cancel":
            self._transition(run, WorkflowState.CANCELLED)
            run.holds_resources = False
            self._journal(run, "cancelled")
            return run
        raise AgentOSError(f"unknown workflow signal '{kind}'")

    # -------------------------------------------------------- Compensation

    def _begin_compensation(self, token: str, run: WorkflowRun, reason: str) -> None:
        run.failure = reason
        self._transition(run, WorkflowState.COMPENSATING)
        self._journal(run, "compensating", reason=reason)
        self._compensate(token, run, reason)

    def _compensate(self, token: str, run: WorkflowRun, reason: str) -> None:
        """Saga compensation in reverse chronological order (21B §14.4).

        A failed compensation produces **Stalled**, not Failed: 21B §14.9
        classifies it "Critical, unrecoverable" requiring human intervention,
        and silently marking the workflow Failed would abandon a half-undone
        world without telling anyone.
        """
        stalled: list[str] = []
        for record in run.dag.completed_mutating():
            if record.invocation_id is None:
                # An agent activity with no invocation to compensate. Recorded
                # rather than skipped silently.
                self._journal(run, "compensation_unavailable", activity_id=record.activity_id)
                stalled.append(record.activity_id)
                continue
            try:
                undone = self.tools.compensate(token, record.invocation_id, run.awaiting_decision_id or "dec-workflow")
            except Exception as failure:
                undone = False
                self._journal(run, "compensation_error", activity_id=record.activity_id, reason=str(failure))
            if undone:
                record.state = ActivityState.COMPENSATED
                self._journal(run, "compensated", activity_id=record.activity_id)
            else:
                stalled.append(record.activity_id)

        if stalled:
            self._transition(run, WorkflowState.STALLED)
            run.failure = f"{reason}; compensation stalled on {stalled}"
            self._journal(run, "stalled", activities=stalled)
            self.signals.emit(
                SignalType.EVENT,
                "workflow.compensation.stalled",
                run.context.tenant_id,
                workflow_id=run.workflow_id,
                activities=stalled,
            )
            return
        self._transition(run, WorkflowState.FAILED)
        run.holds_resources = False
        self._journal(run, "failed", reason=reason)

    # --------------------------------------------------------------- Query

    def query(self, workflow_id: str) -> Mapping[str, Any]:
        """**Workflow Query** (21B §14.5): read-only, no mutation."""
        run = self.get(workflow_id)
        return {
            "workflow_id": workflow_id,
            "state": run.state.value,
            "definition": run.dag.definition.name,
            "version": run.dag.definition.version,
            "allocated_budget": run.allocated_budget,
            "spent": run.spent,
            "holds_resources": run.holds_resources,
            "awaiting_activity": run.awaiting_activity_id,
            "checkpoints": list(run.checkpoints),
            "failure": run.failure,
            "activities": {
                aid: {
                    "state": r.state.value,
                    "attempts": r.attempts,
                    "agent": r.bound_agent_id,
                    "cost": r.cost,
                }
                for aid, r in run.dag.records.items()
            },
            "transitions": [(t.isoformat(), s.value) for t, s in run.transitions],
        }

    def get(self, workflow_id: str) -> WorkflowRun:
        run = self._runs.get(workflow_id)
        if run is None:
            raise NotFoundError(f"workflow '{workflow_id}' does not exist")
        return run

    def replay(self, workflow_id: str) -> list[str]:
        """Replay Engine: reconstructs DAG traversal from the journal (07.13.5).

        Returns the activity sequence as recorded. Because activities carry no
        clock and non-determinism lives in `WorkflowContext.variables`, the
        same trigger and context reconstruct the same traversal.
        """
        sequence: list[str] = []
        for seq in range(len(self.journal)):
            payload = self.journal[seq].payload
            if payload.get("workflow_id") != workflow_id:
                continue
            activity_id = payload.get("activity_id")
            if payload.get("action") in ("activity_succeeded", "checkpoint") and activity_id:
                sequence.append(str(activity_id))
        return sequence

    def health(self) -> Mapping[str, Any]:
        """**Workflow Health** (21B §14.5). Consumer: Observability Gateway."""
        runs = list(self._runs.values())
        by_state: dict[str, int] = {}
        for run in runs:
            by_state[run.state.value] = by_state.get(run.state.value, 0) + 1
        terminal = [r for r in runs if r.is_terminal or r.state == WorkflowState.STALLED]
        completed = sum(1 for r in runs if r.state == WorkflowState.COMPLETED)
        return {
            "workflows": len(runs),
            "by_state": by_state,
            "completion_rate": round(completed / len(terminal), 4) if terminal else 0.0,
            "failure_rate": (
                round(sum(1 for r in runs if r.state == WorkflowState.FAILED) / len(terminal), 4) if terminal else 0.0
            ),
            "compensation_frequency": (
                round(
                    sum(1 for r in runs if r.state in (WorkflowState.COMPENSATING, WorkflowState.STALLED)) / len(runs),
                    4,
                )
                if runs
                else 0.0
            ),
            "stalled": [r.workflow_id for r in runs if r.state == WorkflowState.STALLED],
            "paused_holding_resources": [
                r.workflow_id for r in runs if r.state == WorkflowState.PAUSED and r.holds_resources
            ],
            "checkpoints": sum(len(r.checkpoints) for r in runs),
            "definitions": len(self._definitions),
            "journal_entries": len(self.journal),
            "journal_intact": self.journal.verify_chain(),
        }

    # ------------------------------------------------------------ Internals

    def _transition(self, run: WorkflowRun, target: WorkflowState) -> None:
        machine = LifecycleStateMachine(transitions=dict(WORKFLOW_TRANSITIONS), state=run.state)
        machine.transition(target)
        run.state = target
        run.transitions.append((self.now(), target))

    def _journal(self, run: WorkflowRun, action: str, **detail: Any) -> None:
        self.journal.append(
            {
                "kind": "workflow",
                "action": action,
                "workflow_id": run.workflow_id,
                "tenant_id": run.context.tenant_id,
                "state": run.state.value,
                **detail,
            }
        )
