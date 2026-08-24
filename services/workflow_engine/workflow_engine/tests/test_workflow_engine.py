"""Workflow Engine conformance tests (07, 02.3.2, per 21B §14).

`07.13.1`: **"The orchestrator does not perform work; it governs work."**

The costly paths are the ones tested hardest here, because they are the ones
that fail in production rather than in review:

* Planning catches every cheap failure before Running is entered (07.12.1);
* a denied gate compensates rather than proceeding on silence (21B §14.9);
* a failed compensation Stalls rather than quietly Failing, so a half-undone
  world is never abandoned;
* a paused workflow releases ephemeral resources (07.14.5).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from core.exceptions import AgentOSError, NotFoundError
from kernel.signals import SignalEmitter
from workflow_engine.dag import (
    Activity,
    ActivityKind,
    ActivityState,
    ExecutionDAG,
    PlanningFailure,
    WorkflowContext,
    WorkflowDefinition,
    WorkflowState,
)
from workflow_engine.engine import WorkflowEngine, WorkflowRun

TENANT = "tenant-alpha"
TOKEN = "tok"


class Clock:
    def __init__(self) -> None:
        self.now = datetime(2026, 8, 1, 12, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        self.now += timedelta(seconds=1)
        return self.now


@dataclass
class FakeAgent:
    agent_id: str = "agent-analyst"


class FakeAgents:
    """The Agent Runtime's dispatch surface only."""

    def __init__(self, *, available: bool = True, succeed: bool = True) -> None:
        self.available = available
        self.succeed = succeed
        self.executions = 0

    def discover(self, token: str, capability: str, min_reputation: float) -> list[Any]:
        return [FakeAgent()] if self.available else []

    def execute(self, token: str, **fields: Any) -> Any:
        self.executions += 1

        @dataclass(frozen=True)
        class Outcome:
            succeeded: bool
            cost: float
            detail: str

        return Outcome(succeeded=self.succeed, cost=0.02, detail="" if self.succeed else "the agent failed")


class FakeTools:
    def __init__(self, *, succeed: bool = True, compensates: bool = True) -> None:
        self.succeed = succeed
        self.compensates = compensates
        self.invocations = 0
        self.compensations: list[str] = []

    def invoke(
        self, token: str, tool_id: str, decision_id: str, parameters: dict[str, Any], cost_ceiling: float, key: str
    ) -> tuple[bool, dict[str, Any] | None, float, str]:
        self.invocations += 1
        return (self.succeed, {"ok": True}, 0.05, f"inv-{self.invocations}")

    def compensate(self, token: str, invocation_id: str, decision_id: str) -> bool:
        self.compensations.append(invocation_id)
        return self.compensates


class FakeApprovals:
    def __init__(self, *, approved: bool = True) -> None:
        self.approved = approved
        self.requests: list[tuple[str, str, str]] = []

    def request_approval(self, workflow_id: str, activity_id: str, decision_class: str) -> str:
        self.requests.append((workflow_id, activity_id, decision_class))
        return f"dec-{activity_id}"

    def is_approved(self, decision_id: str) -> bool:
        return self.approved


class FakeBudget:
    def __init__(self, *, headroom: bool = True) -> None:
        self.headroom = headroom
        self.asked: list[float] = []

    def has_headroom(self, tenant_id: str, cost: float) -> bool:
        self.asked.append(cost)
        return self.headroom


def engine(
    agents: FakeAgents | None = None,
    tools: FakeTools | None = None,
    approvals: FakeApprovals | None = None,
    budget: FakeBudget | None = None,
) -> WorkflowEngine:
    return WorkflowEngine(
        agents=agents or FakeAgents(),
        tools=tools or FakeTools(),
        approvals=approvals or FakeApprovals(),
        budget=budget or FakeBudget(),
        signals=SignalEmitter(source_identity="workflow_engine"),
        now=Clock(),
    )


def context(workflow_id: str = "wf-1") -> WorkflowContext:
    return WorkflowContext(
        workflow_id=workflow_id,
        tenant_id=TENANT,
        trigger="manual",
        triggered_by="human-sovereign",
        variables={"now": "2026-08-01T12:00:00Z"},
    )


LINEAR = WorkflowDefinition(
    name="linear",
    version="1.0.0",
    activities=(
        Activity(activity_id="analyse", kind=ActivityKind.AGENT, capability="analysis", estimated_cost=0.1),
        Activity(
            activity_id="publish",
            kind=ActivityKind.TOOL,
            tool_id="tool.publish",
            depends_on=("analyse",),
            mutating=True,
            estimated_cost=0.2,
        ),
    ),
)

GATED = WorkflowDefinition(
    name="gated",
    version="1.0.0",
    activities=(
        Activity(activity_id="analyse", kind=ActivityKind.AGENT, capability="analysis", estimated_cost=0.1),
        Activity(activity_id="mark", kind=ActivityKind.CHECKPOINT, depends_on=("analyse",)),
        Activity(
            activity_id="approve",
            kind=ActivityKind.HUMAN_GATE,
            depends_on=("mark",),
            decision_class="C",
        ),
        Activity(
            activity_id="publish",
            kind=ActivityKind.TOOL,
            tool_id="tool.publish",
            depends_on=("approve",),
            mutating=True,
            estimated_cost=0.2,
        ),
    ),
)


def run_to_completion(e: WorkflowEngine, definition: WorkflowDefinition = LINEAR) -> WorkflowRun:
    e.register_definition(definition)
    run = e.trigger(TOKEN, definition.name, definition.version, context())
    e.advance(TOKEN)
    return run


# ------------------------------------------------------------- Definitions


def test_a_definition_that_cannot_produce_a_valid_dag_is_not_registrable() -> None:
    """Validate at registration, not at trigger."""
    cyclic = WorkflowDefinition(
        name="cyclic",
        version="1.0.0",
        activities=(
            Activity(activity_id="a", kind=ActivityKind.CHECKPOINT, depends_on=("b",)),
            Activity(activity_id="b", kind=ActivityKind.CHECKPOINT, depends_on=("a",)),
        ),
    )
    with pytest.raises(PlanningFailure, match="cyclic"):
        engine().register_definition(cyclic)


def test_the_same_definition_version_may_not_be_registered_twice() -> None:
    e = engine()
    e.register_definition(LINEAR)
    with pytest.raises(AgentOSError, match="already registered"):
        e.register_definition(LINEAR)


def test_triggering_an_unregistered_definition_is_a_not_found() -> None:
    with pytest.raises(NotFoundError, match="is not registered"):
        engine().trigger(TOKEN, "linear", "1.0.0", context())


def test_a_duplicate_trigger_is_rejected() -> None:
    """21B §14.3 Trigger Receiver. Two runs of one workflow id would double the effect."""
    e = engine()
    e.register_definition(LINEAR)
    e.trigger(TOKEN, "linear", "1.0.0", context())
    with pytest.raises(AgentOSError, match="already been triggered"):
        e.trigger(TOKEN, "linear", "1.0.0", context())


def test_the_dag_rejects_structurally_invalid_definitions() -> None:
    with pytest.raises(PlanningFailure, match="no activities"):
        ExecutionDAG.build(WorkflowDefinition(name="empty", version="1", activities=()))
    with pytest.raises(PlanningFailure, match="distinct"):
        ExecutionDAG.build(
            WorkflowDefinition(
                name="dupes",
                version="1",
                activities=(
                    Activity(activity_id="a", kind=ActivityKind.CHECKPOINT),
                    Activity(activity_id="a", kind=ActivityKind.CHECKPOINT),
                ),
            )
        )
    with pytest.raises(PlanningFailure, match="not in the DAG"):
        ExecutionDAG.build(
            WorkflowDefinition(
                name="dangling",
                version="1",
                activities=(Activity(activity_id="a", kind=ActivityKind.CHECKPOINT, depends_on=("ghost",)),),
            )
        )
    with pytest.raises(PlanningFailure, match="no capability"):
        ExecutionDAG.build(
            WorkflowDefinition(
                name="uncapable", version="1", activities=(Activity(activity_id="a", kind=ActivityKind.AGENT),)
            )
        )
    with pytest.raises(PlanningFailure, match="names no tool"):
        ExecutionDAG.build(
            WorkflowDefinition(
                name="toolless", version="1", activities=(Activity(activity_id="a", kind=ActivityKind.TOOL),)
            )
        )


# ---------------------------------------------------------------- Planning


def test_planning_failure_goes_straight_to_failed_having_consumed_nothing() -> None:
    """21B §14.9 — "Critical, cheap", no compensation needed."""
    tools = FakeTools()
    agents = FakeAgents()
    e = engine(agents=agents, tools=tools, budget=FakeBudget(headroom=False))
    e.register_definition(LINEAR)
    run = e.trigger(TOKEN, "linear", "1.0.0", context())
    assert run.state == WorkflowState.FAILED
    assert "exceeds available budget" in (run.failure or "")
    assert agents.executions == 0
    assert tools.invocations == 0


def test_planning_fails_when_no_agent_holds_the_required_capability() -> None:
    e = engine(agents=FakeAgents(available=False))
    e.register_definition(LINEAR)
    run = e.trigger(TOKEN, "linear", "1.0.0", context())
    assert run.state == WorkflowState.FAILED
    assert "no available agent holds capability" in (run.failure or "")


def test_the_pre_allocated_budget_is_the_worst_case_not_the_optimistic_one() -> None:
    """21B §14.3. Pre-allocating the optimistic cost would admit a workflow that
    cannot afford to finish, which is the failure Planning exists to prevent."""
    budget = FakeBudget()
    e = engine(budget=budget)
    run = run_to_completion(e)
    # analyse: 0.1 x 3 attempts. publish: 0.2 x 3 attempts + 0.2 compensation.
    assert run.allocated_budget == pytest.approx(1.1)
    assert budget.asked == [pytest.approx(1.1)]


def test_agents_are_bound_during_planning_not_at_dispatch() -> None:
    e = engine()
    e.register_definition(LINEAR)
    run = e.trigger(TOKEN, "linear", "1.0.0", context())
    assert run.state == WorkflowState.RUNNING
    assert run.dag.records["analyse"].bound_agent_id == "agent-analyst"


# ----------------------------------------------------------------- Running


def test_a_linear_workflow_completes_and_releases_its_resources() -> None:
    e = engine()
    run = run_to_completion(e)
    assert run.state == WorkflowState.COMPLETED
    assert run.holds_resources is False
    assert run.spent == pytest.approx(0.07)


def test_advance_only_touches_running_workflows() -> None:
    e = engine()
    run = run_to_completion(e)
    assert e.advance(TOKEN) == [], f"{run.state} is terminal and must not be advanced again"


def test_a_checkpoint_is_recorded_so_a_crashed_orchestrator_resumes() -> None:
    """07.19.5."""
    e = engine()
    e.register_definition(GATED)
    run = e.trigger(TOKEN, "gated", "1.0.0", context())
    e.advance(TOKEN)
    assert run.checkpoints == ["mark"]


# ------------------------------------------------------------- Human gates


def test_a_workflow_pauses_on_a_gate_and_releases_ephemeral_resources() -> None:
    """07.14.5 — a paused workflow consumes no compute quota while retaining state."""
    approvals = FakeApprovals()
    tools = FakeTools()
    e = engine(approvals=approvals, tools=tools)
    e.register_definition(GATED)
    run = e.trigger(TOKEN, "gated", "1.0.0", context())
    e.advance(TOKEN)
    assert run.state == WorkflowState.PAUSED
    assert run.awaiting_activity_id == "approve"
    assert run.holds_resources is False
    assert approvals.requests == [("wf-1", "approve", "C")]
    assert tools.invocations == 0, "the gate precedes the effect"


def test_approval_resumes_the_workflow_and_the_effect_follows() -> None:
    tools = FakeTools()
    e = engine(tools=tools)
    e.register_definition(GATED)
    run = e.trigger(TOKEN, "gated", "1.0.0", context())
    e.advance(TOKEN)
    e.signal(TOKEN, "wf-1", "resume")
    assert run.state == WorkflowState.COMPLETED
    assert tools.invocations == 1
    assert run.holds_resources is False


def test_a_denied_gate_compensates_rather_than_proceeding() -> None:
    """21B §14.9. Never proceed on silence, and never leave the effect standing."""
    tools = FakeTools()
    e = engine(tools=tools, approvals=FakeApprovals(approved=False))
    e.register_definition(GATED)
    run = e.trigger(TOKEN, "gated", "1.0.0", context())
    e.advance(TOKEN)
    e.signal(TOKEN, "wf-1", "resume")
    assert run.state == WorkflowState.FAILED
    assert tools.invocations == 0, "the gated effect never ran"


def test_resume_is_refused_on_a_workflow_that_is_not_paused() -> None:
    e = engine()
    run_to_completion(e)
    with pytest.raises(AgentOSError, match="not Paused"):
        e.signal(TOKEN, "wf-1", "resume")


def test_an_unknown_signal_is_refused_rather_than_ignored() -> None:
    e = engine()
    e.register_definition(GATED)
    e.trigger(TOKEN, "gated", "1.0.0", context())
    e.advance(TOKEN)
    with pytest.raises(AgentOSError, match="unknown workflow signal"):
        e.signal(TOKEN, "wf-1", "approve-please")


def test_cancelling_a_paused_workflow_releases_its_resources() -> None:
    e = engine()
    e.register_definition(GATED)
    run = e.trigger(TOKEN, "gated", "1.0.0", context())
    e.advance(TOKEN)
    e.signal(TOKEN, "wf-1", "cancel")
    assert run.state == WorkflowState.CANCELLED
    assert run.holds_resources is False


def test_signalling_an_unknown_workflow_is_a_not_found() -> None:
    with pytest.raises(NotFoundError, match="does not exist"):
        engine().signal(TOKEN, "wf-nobody", "cancel")


# ------------------------------------------------- retries and compensation


def test_an_activity_is_retried_within_its_declared_policy_then_fails() -> None:
    """21B §14.9. Three attempts for max_retries=2, then Failed, not a fourth."""
    agents = FakeAgents(succeed=False)
    e = engine(agents=agents)
    e.register_definition(LINEAR)
    run = e.trigger(TOKEN, "linear", "1.0.0", context())
    e.advance(TOKEN)
    assert agents.executions == 3
    assert run.dag.records["analyse"].state == ActivityState.FAILED
    assert run.state == WorkflowState.FAILED


def test_a_failure_compensates_completed_mutating_activities_in_reverse_order() -> None:
    """21B §14.4 — an earlier activity is never undone before a later dependent."""
    definition = WorkflowDefinition(
        name="two-effects",
        version="1.0.0",
        activities=(
            Activity(activity_id="first", kind=ActivityKind.TOOL, tool_id="tool.a", mutating=True, estimated_cost=0.1),
            Activity(
                activity_id="second",
                kind=ActivityKind.TOOL,
                tool_id="tool.b",
                depends_on=("first",),
                mutating=True,
                estimated_cost=0.1,
            ),
            Activity(
                activity_id="last",
                kind=ActivityKind.AGENT,
                capability="analysis",
                depends_on=("second",),
                estimated_cost=0.1,
            ),
        ),
    )
    tools = FakeTools()
    e = engine(agents=FakeAgents(succeed=False), tools=tools)
    e.register_definition(definition)
    run = e.trigger(TOKEN, "two-effects", "1.0.0", context())
    e.advance(TOKEN)
    assert run.state == WorkflowState.FAILED
    assert tools.compensations == ["inv-2", "inv-1"], "reverse chronological"
    assert run.dag.records["first"].state == ActivityState.COMPENSATED
    assert run.dag.records["second"].state == ActivityState.COMPENSATED


def test_a_failed_compensation_stalls_rather_than_quietly_failing() -> None:
    """21B §14.9 — "Critical, unrecoverable", requiring human intervention.

    Marking this Failed would abandon a half-undone world without telling
    anyone, which is the outcome the Stalled state exists to prevent.
    """
    tools = FakeTools(compensates=False)
    e = engine(agents=FakeAgents(succeed=False), tools=tools)
    e.register_definition(
        WorkflowDefinition(
            name="stalling",
            version="1.0.0",
            activities=(
                Activity(
                    activity_id="effect", kind=ActivityKind.TOOL, tool_id="tool.a", mutating=True, estimated_cost=0.1
                ),
                Activity(
                    activity_id="after",
                    kind=ActivityKind.AGENT,
                    capability="analysis",
                    depends_on=("effect",),
                    estimated_cost=0.1,
                ),
            ),
        )
    )
    run = e.trigger(TOKEN, "stalling", "1.0.0", context())
    e.advance(TOKEN)
    assert run.state == WorkflowState.STALLED
    assert "compensation stalled on ['effect']" in (run.failure or "")
    assert e.health()["stalled"] == ["wf-1"]


def test_a_compensation_that_raises_is_recorded_and_stalls() -> None:
    class ExplodingTools(FakeTools):
        def compensate(self, token: str, invocation_id: str, decision_id: str) -> bool:
            raise RuntimeError("the compensating endpoint is unreachable")

    e = engine(agents=FakeAgents(succeed=False), tools=ExplodingTools())
    e.register_definition(
        WorkflowDefinition(
            name="exploding",
            version="1.0.0",
            activities=(
                Activity(
                    activity_id="effect", kind=ActivityKind.TOOL, tool_id="tool.a", mutating=True, estimated_cost=0.1
                ),
                Activity(
                    activity_id="after",
                    kind=ActivityKind.AGENT,
                    capability="analysis",
                    depends_on=("effect",),
                    estimated_cost=0.1,
                ),
            ),
        )
    )
    run = e.trigger(TOKEN, "exploding", "1.0.0", context())
    e.advance(TOKEN)
    assert run.state == WorkflowState.STALLED
    assert _actions(e, "wf-1").count("compensation_error") == 1


def test_a_mutating_activity_with_no_invocation_stalls_rather_than_being_skipped() -> None:
    """An agent activity marked mutating has nothing to compensate. Recorded, not ignored."""
    e = engine(agents=FakeAgents())
    e.register_definition(
        WorkflowDefinition(
            name="unbacked",
            version="1.0.0",
            activities=(
                Activity(
                    activity_id="mutate",
                    kind=ActivityKind.AGENT,
                    capability="analysis",
                    mutating=True,
                    estimated_cost=0.1,
                ),
                Activity(
                    activity_id="fails",
                    kind=ActivityKind.TOOL,
                    tool_id="tool.a",
                    depends_on=("mutate",),
                    estimated_cost=0.1,
                ),
            ),
        )
    )
    e.tools = FakeTools(succeed=False)
    run = e.trigger(TOKEN, "unbacked", "1.0.0", context())
    e.advance(TOKEN)
    assert run.state == WorkflowState.STALLED
    assert "compensation_unavailable" in _actions(e, "wf-1")


def test_a_failing_terminal_activity_does_not_leave_the_workflow_running() -> None:
    """The regression this suite exists to hold.

    `blocked_by_failure` only finds *dependents* of a failure. A terminal
    activity has none, so before `has_failure` the workflow sat in Running
    forever with nothing left to dispatch.
    """
    e = engine(tools=FakeTools(succeed=False))
    run = run_to_completion(e)
    assert run.state != WorkflowState.RUNNING
    # Nothing mutating ever succeeded, so there is nothing to undo: Failed, not
    # Stalled. What matters is that it reached a terminal state at all.
    assert run.state == WorkflowState.FAILED


# ------------------------------------------------------ query, replay, health


def test_query_is_read_only_and_reports_the_full_run() -> None:
    e = engine()
    run = run_to_completion(e)
    before = run.state
    report = e.query("wf-1")
    assert run.state == before, "Workflow Query must not mutate"
    assert report["state"] == "completed"
    assert report["definition"] == "linear"
    assert report["activities"]["analyse"]["agent"] == "agent-analyst"
    assert len(report["transitions"]) == len(run.transitions)


def test_replay_reconstructs_the_traversal_from_the_journal() -> None:
    """07.13.5. Activities carry no clock, so the same context replays the same order."""
    e = engine()
    e.register_definition(GATED)
    e.trigger(TOKEN, "gated", "1.0.0", context())
    e.advance(TOKEN)
    e.signal(TOKEN, "wf-1", "resume")
    assert e.replay("wf-1") == ["analyse", "mark", "publish"]


def test_replay_of_an_unrelated_workflow_returns_nothing() -> None:
    e = engine()
    run_to_completion(e)
    assert e.replay("wf-other") == []


def test_health_reports_the_orchestration_signals() -> None:
    e = engine()
    run_to_completion(e)
    health = e.health()
    assert health["workflows"] == 1
    assert health["by_state"] == {"completed": 1}
    assert health["completion_rate"] == 1.0
    assert health["failure_rate"] == 0.0
    assert health["definitions"] == 1
    assert health["journal_intact"]
    assert health["paused_holding_resources"] == []


def test_health_of_an_engine_that_has_run_nothing_reports_zeroes() -> None:
    health = engine().health()
    assert health["workflows"] == 0
    assert health["completion_rate"] == 0.0
    assert health["compensation_frequency"] == 0.0


def test_a_paused_workflow_is_never_listed_as_holding_resources() -> None:
    e = engine()
    e.register_definition(GATED)
    e.trigger(TOKEN, "gated", "1.0.0", context())
    e.advance(TOKEN)
    assert e.health()["paused_holding_resources"] == []
    assert e.health()["by_state"] == {"paused": 1}


# -------------------------------------------------- structural constraints


def test_the_engine_performs_no_work_itself() -> None:
    """07.13.1 — "The orchestrator does not perform work; it governs work."

    Structural: an inference, tool-running, or memory verb appearing on the
    engine would mean orchestration had absorbed execution.
    """
    forbidden = {"infer", "run_tool", "execute_tool", "hydrate", "call_model", "invoke_tool"}
    present = {name for name in dir(WorkflowEngine) if not name.startswith("_")}
    assert not (forbidden & present), f"the engine has absorbed execution: {forbidden & present}"


def test_cross_subsystem_imports_are_confined_to_the_adapter() -> None:
    import pathlib

    package = pathlib.Path(__file__).resolve().parents[1]
    foreign = ("agent_runtime", "tool_gateway", "tool_executor", "decision_gateway", "cost_manager")
    for source in package.glob("*.py"):
        if source.name == "adapters.py":
            continue
        for line in source.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped.startswith(("import ", "from ")):
                continue
            assert not any(
                name in stripped for name in foreign
            ), f"{source.name} imports another subsystem directly; route it through adapters.py"


def test_the_journal_chain_is_intact_across_a_compensating_run() -> None:
    e = engine(agents=FakeAgents(succeed=False))
    run_to_completion(e)
    assert e.journal.verify_chain()


def _actions(e: WorkflowEngine, workflow_id: str) -> list[str]:
    return [
        str(e.journal[i].payload.get("action"))
        for i in range(len(e.journal))
        if e.journal[i].payload.get("workflow_id") == workflow_id
    ]
