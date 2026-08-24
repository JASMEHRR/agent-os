"""Agent Runtime conformance tests (05, 06, 02.3.2, per 21B §13).

These exercise the Runtime against fakes so each rule is tested in isolation.
The wired-for-real exercise lives in `tests/s7_first_light/`.

The load-bearing assertions here are the ones that would be easy to lose in a
later refactor and expensive to lose in production:

* the six authority boundaries of 06.9.6 are an intersection, so any one of
  them alone refuses the activity;
* an agent may not review its own output (06 rules 16, 17);
* repeated schema violation suspends automatically (06.9.4);
* the Runtime exposes no scheduling verb (02.3.2).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from agent_runtime import (
    SCHEMA_VIOLATION_SUSPENSION_THRESHOLD,
    ActivityRequest,
    AgentManifest,
    AgentRuntime,
    AgentState,
    AuthorityBoundaries,
    AuthorityViolation,
    DriftMonitor,
    ManifestLoader,
    ReputationEngine,
    SeparationOfDutiesViolation,
    stall_threshold,
)
from agent_runtime.identity import (
    REPUTATION_DECAY_FRACTION,
    REPUTATION_DECAY_IDLE,
    AgentRecord,
)
from core.exceptions import AgentOSError, NotFoundError, ValidationError
from kernel.authority import AuthorityLevel
from kernel.signals import SignalEmitter

TENANT = "tenant-alpha"
OTHER_TENANT = "tenant-beta"
AGENT = "agent-analyst"


class Clock:
    def __init__(self) -> None:
        self.now = datetime(2026, 8, 1, 12, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.now

    def advance(self, delta: timedelta) -> None:
        self.now += delta


class FakeAuthorizer:
    """Maps a token to (principal, tenant). The Security Gateway's shape only."""

    def __init__(self) -> None:
        self.tokens = {"tok": (AGENT, TENANT), "tok-other": ("agent-foreign", OTHER_TENANT)}

    def principal_of(self, token: str) -> tuple[str, str]:
        return self.tokens[token]

    def is_human(self, principal_id: str) -> bool:
        return principal_id.startswith("human-")


class FakeMemory:
    def __init__(self, entries: list[dict[str, Any]] | None = None) -> None:
        self.entries = entries if entries is not None else [{"claim": "prices rose"}]
        self.scopes: list[frozenset[str]] = []

    def hydrate(self, token: str, tenant_id: str, scope: frozenset[str]) -> list[dict[str, Any]]:
        self.scopes.append(scope)
        return list(self.entries)


class FakeInference:
    def __init__(self, output: dict[str, Any] | None = None, cost: float = 0.02, grounded: bool = True) -> None:
        self.output = output if output is not None else {"summary": "prices rose", "confidence": 0.8}
        self.cost = cost
        self.grounded = grounded
        self.calls: list[tuple[str, dict[str, str], float]] = []

    def infer(
        self, template: str, slots: dict[str, str], tenant_id: str, principal_id: str, max_cost: float
    ) -> tuple[dict[str, Any], float, bool]:
        self.calls.append((template, dict(slots), max_cost))
        return (dict(self.output), self.cost, self.grounded)


class FakeTools:
    def __init__(self, succeed: bool = True, cost: float = 0.05) -> None:
        self.succeed = succeed
        self.cost = cost
        self.invocations: list[tuple[str, str, float]] = []

    def invoke(
        self,
        token: str,
        tool_id: str,
        decision_id: str,
        parameters: dict[str, Any],
        cost_ceiling: float,
        idempotency_key: str,
    ) -> tuple[bool, dict[str, Any] | None, float]:
        self.invocations.append((tool_id, idempotency_key, cost_ceiling))
        return (self.succeed, {"ok": True} if self.succeed else None, self.cost)


def boundaries(**overrides: Any) -> AuthorityBoundaries:
    defaults: dict[str, Any] = {
        "capabilities": frozenset({"analysis"}),
        "tool_inventory": frozenset({"tool.publish"}),
        "memory_scope": frozenset({"tenant"}),
        "autonomy_level": AuthorityLevel.AGENT_DELEGATED,
        "cost_budget": 1.0,
        "workspace_ids": frozenset({"ws-1"}),
    }
    defaults.update(overrides)
    return AuthorityBoundaries(**defaults)


def manifest(agent_id: str = AGENT, **overrides: Any) -> AgentManifest:
    defaults: dict[str, Any] = {
        "agent_id": agent_id,
        "name": agent_id,
        "version": "1.0.0",
        "tenant_id": TENANT,
        "specialty": "market analysis",
        "boundaries": boundaries(),
        "prompt_template": "analyse {context}",
        "output_contract": {"summary": str},
        "max_context_tokens": 1000,
        "max_context_assembly_time": timedelta(seconds=5),
        "activity_timeout": timedelta(minutes=5),
    }
    defaults.update(overrides)
    return AgentManifest(**defaults)


def request(**overrides: Any) -> ActivityRequest:
    defaults: dict[str, Any] = {
        "activity_id": "act-1",
        "workflow_id": "wf-1",
        "agent_id": AGENT,
        "tenant_id": TENANT,
        "idempotency_key": "idem-1",
        "inputs": {"question": "what happened to prices?"},
        "decision_id": "dec-1",
        "cost_ceiling": 0.5,
    }
    defaults.update(overrides)
    return ActivityRequest(**defaults)


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def memory() -> FakeMemory:
    return FakeMemory()


@pytest.fixture
def inference() -> FakeInference:
    return FakeInference()


@pytest.fixture
def tools() -> FakeTools:
    return FakeTools()


@pytest.fixture
def runtime(clock: Clock, memory: FakeMemory, inference: FakeInference, tools: FakeTools) -> AgentRuntime:
    return AgentRuntime(
        authorizer=FakeAuthorizer(),
        memory=memory,
        inference=inference,
        tools=tools,
        signals=SignalEmitter(source_identity="agent_runtime"),
        now=clock,
    )


def idle_agent(runtime: AgentRuntime, **overrides: Any) -> AgentRecord:
    record = runtime.register("tok", manifest(**overrides))
    runtime.command("tok", record.agent_id, AgentState.IDLE)
    return record


# ----------------------------------------------------------- Identity Plane


def test_a_registered_agent_is_not_yet_assignable(runtime: AgentRuntime) -> None:
    """Registration is not availability, exactly as tool registration is not authorization."""
    record = runtime.register("tok", manifest())
    assert record.state == AgentState.REGISTERED
    assert not record.is_assignable
    assert runtime.discover("tok") == []


def test_an_agent_may_not_be_registered_into_another_tenant(runtime: AgentRuntime) -> None:
    with pytest.raises(AgentOSError, match="may not register into tenant"):
        runtime.register("tok-other", manifest())


def test_registering_the_same_agent_twice_is_refused(runtime: AgentRuntime) -> None:
    runtime.register("tok", manifest())
    with pytest.raises(AgentOSError, match="already registered"):
        runtime.register("tok", manifest())


def test_lineage_must_resolve_when_a_predecessor_is_declared(runtime: AgentRuntime) -> None:
    """06.5.1 — behavioural change is a new version with lineage, never an edit."""
    with pytest.raises(AgentOSError, match="lineage must resolve"):
        runtime.register("tok", manifest(agent_id="agent-v2", predecessor_agent_id="agent-v1"))

    runtime.register("tok", manifest(agent_id="agent-v1"))
    successor = runtime.register("tok", manifest(agent_id="agent-v2", predecessor_agent_id="agent-v1"))
    assert successor.manifest.predecessor_agent_id == "agent-v1"


def test_the_manifest_is_frozen_once_registered(runtime: AgentRuntime) -> None:
    record = runtime.register("tok", manifest())
    with pytest.raises(Exception):  # noqa: B017 - dataclasses raise FrozenInstanceError
        record.manifest.specialty = "something else"  # type: ignore[misc]


def test_an_unknown_agent_is_a_not_found(runtime: AgentRuntime) -> None:
    with pytest.raises(NotFoundError):
        runtime.get("agent-nobody")


def test_discovery_returns_only_idle_agents_in_the_caller_tenant(runtime: AgentRuntime) -> None:
    idle_agent(runtime)
    runtime.register("tok", manifest(agent_id="agent-registered-only"))
    found = runtime.discover("tok")
    assert [r.agent_id for r in found] == [AGENT]


def test_discovery_filters_on_capability_and_reputation(runtime: AgentRuntime) -> None:
    idle_agent(runtime)
    assert runtime.discover("tok", capability="analysis")
    assert runtime.discover("tok", capability="analysis.pricing"), "capability prefixes are permitted"
    assert runtime.discover("tok", capability="publishing") == []
    assert runtime.discover("tok", min_reputation=0.9) == []


def test_lifecycle_transitions_follow_the_declared_machine(runtime: AgentRuntime) -> None:
    """06.6. Registered may not jump straight to Executing."""
    runtime.register("tok", manifest())
    with pytest.raises(Exception):  # noqa: B017 - the kernel machine's own error type
        runtime.command("tok", AGENT, AgentState.EXECUTING)
    runtime.command("tok", AGENT, AgentState.IDLE)
    runtime.command("tok", AGENT, AgentState.SUSPENDED, reason="under review")
    assert runtime.get(AGENT).suspended_reason == "under review"


def test_the_manifest_loader_refuses_an_agent_that_could_do_nothing() -> None:
    loader = ManifestLoader()
    with pytest.raises(ValidationError, match="no capability signature"):
        loader.validate(manifest(boundaries=boundaries(capabilities=frozenset())))
    with pytest.raises(ValidationError, match="no output contract"):
        loader.validate(manifest(output_contract={}))
    with pytest.raises(ValidationError, match="max_context_tokens"):
        loader.validate(manifest(max_context_tokens=0))
    with pytest.raises(ValidationError, match="activity_timeout"):
        loader.validate(manifest(activity_timeout=timedelta(0)))
    with pytest.raises(ValidationError, match="cost budget"):
        loader.validate(manifest(boundaries=boundaries(cost_budget=-1.0)))


# ------------------------------------------- the six boundaries of 06.9.6


def test_an_activity_beyond_the_declared_cost_budget_is_refused(runtime: AgentRuntime) -> None:
    """Boundary 5 of six. The intersection means any single boundary suffices to refuse."""
    idle_agent(runtime)
    with pytest.raises(AuthorityViolation, match="exceeds the agent's declared budget"):
        runtime.execute("tok", request(cost_ceiling=5.0))


def test_a_tool_outside_the_registered_inventory_is_refused(runtime: AgentRuntime) -> None:
    """Boundary 2 of six, and 12.32.1 — the Runtime does not select beyond inventory."""
    idle_agent(runtime)
    with pytest.raises(AuthorityViolation, match="outside agent .* registered inventory"):
        runtime.execute("tok", request(tool_calls=(("tool.transfer-funds", {}),)))


def test_an_agent_belonging_to_another_tenant_is_refused(runtime: AgentRuntime) -> None:
    idle_agent(runtime)
    with pytest.raises(AuthorityViolation, match="belongs to another tenant"):
        runtime.execute("tok-other", request())


def test_hydration_is_confined_to_the_declared_memory_scope(runtime: AgentRuntime, memory: FakeMemory) -> None:
    """Boundary 3 of six. The Runtime passes the scope; it does not widen it."""
    idle_agent(runtime)
    runtime.execute("tok", request())
    assert memory.scopes == [frozenset({"tenant"})]


def test_the_boundaries_intersect_rather_than_union() -> None:
    """14.12.4 everywhere: effective permission is the intersection.

    A capability the agent holds does not import a tool it does not, and vice
    versa. Asserted directly on the boundary object so the property is pinned
    independently of the execution path.
    """
    b = boundaries(capabilities=frozenset({"analysis"}), tool_inventory=frozenset({"tool.publish"}))
    assert b.permits_capability("analysis")
    assert not b.permits_capability("tool.publish")
    assert b.permits_tool("tool.publish")
    assert not b.permits_tool("analysis")


def test_a_capability_prefix_is_permitted_but_a_sibling_is_not() -> None:
    b = boundaries(capabilities=frozenset({"analysis"}))
    assert b.permits_capability("analysis.pricing")
    assert not b.permits_capability("analysis-adjacent")


# ---------------------------------------------- separation of duties (06.16/17)


def test_an_agent_may_not_review_its_own_output(runtime: AgentRuntime) -> None:
    idle_agent(runtime)
    with pytest.raises(SeparationOfDutiesViolation, match="may not review its own output"):
        runtime.execute("tok", request(reviews_output_of=AGENT))


def test_an_agent_may_review_another_agents_output(runtime: AgentRuntime) -> None:
    idle_agent(runtime)
    outcome = runtime.execute("tok", request(reviews_output_of="agent-other"))
    assert outcome.succeeded


# --------------------------------------------------------- Execution Plane


def test_a_successful_execution_returns_validated_output_and_metered_cost(
    runtime: AgentRuntime, inference: FakeInference
) -> None:
    idle_agent(runtime)
    outcome = runtime.execute("tok", request())
    assert outcome.succeeded
    assert outcome.output_valid
    assert outcome.output == {"summary": "prices rose", "confidence": 0.8}
    assert outcome.cost == inference.cost
    assert not outcome.degraded


def test_the_worker_returns_to_idle_holding_nothing(runtime: AgentRuntime) -> None:
    """21B §13.4 — the ephemeral half retains nothing after the activity."""
    record = idle_agent(runtime)
    runtime.execute("tok", request())
    assert record.state == AgentState.IDLE
    assert runtime.health()["worker_pool"]["in_use"] == 0
    assert runtime.health()["worker_pool"]["peak"] == 1


def test_a_suspended_agent_cannot_be_executed(runtime: AgentRuntime) -> None:
    idle_agent(runtime)
    runtime.command("tok", AGENT, AgentState.SUSPENDED, reason="under review")
    with pytest.raises(AgentOSError, match="not assignable"):
        runtime.execute("tok", request())


def test_heartbeats_are_emitted_for_every_stage(runtime: AgentRuntime) -> None:
    """02.4.8 — a silent worker is indistinguishable from a stalled one."""
    idle_agent(runtime)
    outcome = runtime.execute("tok", request())
    assert [h.stage for h in outcome.heartbeats] == [
        "hydrating",
        "assembling",
        "inferring",
        "dispatching_tools",
        "validating",
    ]


def test_empty_context_marks_the_outcome_degraded(clock: Clock, inference: FakeInference) -> None:
    """21B §13.9 — degraded assembly carries an explicit flag rather than passing silently."""
    runtime = AgentRuntime(
        authorizer=FakeAuthorizer(),
        memory=FakeMemory(entries=[]),
        inference=inference,
        tools=FakeTools(),
        signals=SignalEmitter(source_identity="agent_runtime"),
        now=clock,
    )
    idle_agent(runtime)
    outcome = runtime.execute("tok", request())
    assert outcome.succeeded
    assert outcome.degraded


def test_ungrounded_inference_marks_the_outcome_degraded(clock: Clock) -> None:
    runtime = AgentRuntime(
        authorizer=FakeAuthorizer(),
        memory=FakeMemory(),
        inference=FakeInference(grounded=False),
        tools=FakeTools(),
        signals=SignalEmitter(source_identity="agent_runtime"),
        now=clock,
    )
    idle_agent(runtime)
    assert runtime.execute("tok", request()).degraded


def test_context_assembly_truncates_rather_than_overflowing_the_budget(clock: Clock, inference: FakeInference) -> None:
    """07.10.4. A budget silently exceeded is not a budget."""
    entries = [{"claim": "x" * 400} for _ in range(20)]
    runtime = AgentRuntime(
        authorizer=FakeAuthorizer(),
        memory=FakeMemory(entries=entries),
        inference=inference,
        tools=FakeTools(),
        signals=SignalEmitter(source_identity="agent_runtime"),
        now=clock,
    )
    idle_agent(runtime, max_context_tokens=200)
    runtime.execute("tok", request())
    _template, slots, _ceiling = inference.calls[-1]
    assert len(slots["context"]) // 4 <= 200


def test_a_tool_failure_fails_the_activity(clock: Clock, inference: FakeInference) -> None:
    runtime = AgentRuntime(
        authorizer=FakeAuthorizer(),
        memory=FakeMemory(),
        inference=inference,
        tools=FakeTools(succeed=False),
        signals=SignalEmitter(source_identity="agent_runtime"),
        now=clock,
    )
    record = idle_agent(runtime)
    outcome = runtime.execute("tok", request(tool_calls=(("tool.publish", {}),)))
    assert not outcome.succeeded
    assert outcome.output is None
    assert record.state == AgentState.IDLE, "failure still returns the worker to the pool"
    assert record.failures == 1


def test_the_tool_ceiling_shrinks_by_the_cost_already_spent(
    runtime: AgentRuntime, tools: FakeTools, inference: FakeInference
) -> None:
    """A ceiling that ignored inference cost would let one activity spend twice."""
    idle_agent(runtime)
    runtime.execute("tok", request(cost_ceiling=0.5, tool_calls=(("tool.publish", {}),)))
    _tool_id, _key, ceiling = tools.invocations[-1]
    assert ceiling == pytest.approx(0.5 - inference.cost)


def test_the_idempotency_key_carries_down_to_the_tool(runtime: AgentRuntime, tools: FakeTools) -> None:
    """12.17 — a redispatch must be recognisable as the same logical work."""
    idle_agent(runtime)
    runtime.execute("tok", request(tool_calls=(("tool.publish", {}),)))
    assert tools.invocations[-1][1] == "idem-1:tool.publish"


# ------------------------------------------------ output contract (06.9.4)


def test_output_missing_a_contracted_field_fails_the_activity(clock: Clock) -> None:
    """21B §13.15 guarantee 5 — no unvalidated output propagates."""
    runtime = AgentRuntime(
        authorizer=FakeAuthorizer(),
        memory=FakeMemory(),
        inference=FakeInference(output={"confidence": 0.8}),
        tools=FakeTools(),
        signals=SignalEmitter(source_identity="agent_runtime"),
        now=clock,
    )
    idle_agent(runtime)
    outcome = runtime.execute("tok", request())
    assert not outcome.succeeded
    assert not outcome.output_valid
    assert "missing required field 'summary'" in outcome.detail


def test_output_of_the_wrong_type_fails_the_activity(clock: Clock) -> None:
    runtime = AgentRuntime(
        authorizer=FakeAuthorizer(),
        memory=FakeMemory(),
        inference=FakeInference(output={"summary": 42}),
        tools=FakeTools(),
        signals=SignalEmitter(source_identity="agent_runtime"),
        now=clock,
    )
    idle_agent(runtime)
    outcome = runtime.execute("tok", request())
    assert "expected str, got int" in outcome.detail


def test_repeated_schema_violation_suspends_the_agent_at_the_threshold(clock: Clock) -> None:
    """06.9.4. An agent that keeps producing unusable output stops being assigned."""
    runtime = AgentRuntime(
        authorizer=FakeAuthorizer(),
        memory=FakeMemory(),
        inference=FakeInference(output={"confidence": 0.8}),
        tools=FakeTools(),
        signals=SignalEmitter(source_identity="agent_runtime"),
        now=clock,
    )
    record = idle_agent(runtime)
    for _ in range(SCHEMA_VIOLATION_SUSPENSION_THRESHOLD):
        if record.state == AgentState.IDLE:
            runtime.execute("tok", request())
    assert record.schema_violations == SCHEMA_VIOLATION_SUSPENSION_THRESHOLD
    assert record.state == AgentState.SUSPENDED
    assert record.suspended_reason == "repeated output schema violation"
    assert runtime.discover("tok") == [], "a suspended agent is not discoverable"


# ------------------------------------------------------ reputation and drift


def test_reputation_rises_with_success_and_falls_with_failure(runtime: AgentRuntime) -> None:
    record = idle_agent(runtime)
    runtime.execute("tok", request())
    after_success = record.reputation
    assert after_success == pytest.approx(1.0)

    runtime.tools = FakeTools(succeed=False)
    runtime.execute("tok", request(activity_id="act-2", tool_calls=(("tool.publish", {}),)))
    assert record.reputation < after_success
    assert record.success_rate == 0.5


def test_reputation_of_a_never_executed_agent_is_unchanged() -> None:
    engine = ReputationEngine()
    record = AgentRecord(manifest=manifest())
    assert engine.recompute(record) == 0.5
    assert record.success_rate == 0.0


def test_reputation_decays_only_after_the_idle_period(runtime: AgentRuntime, clock: Clock) -> None:
    record = idle_agent(runtime)
    runtime.execute("tok", request())
    before = record.reputation

    clock.advance(REPUTATION_DECAY_IDLE - timedelta(days=1))
    assert runtime.decay_reputation() == []
    assert record.reputation == before

    clock.advance(timedelta(days=2))
    assert runtime.decay_reputation() == [record]
    assert record.reputation == pytest.approx(round(before * (1.0 - REPUTATION_DECAY_FRACTION), 4))


def test_drift_is_measured_against_the_agents_own_baseline() -> None:
    """06.19.2 is about an agent changing, not about it differing from peers."""
    monitor = DriftMonitor()
    record = AgentRecord(manifest=manifest(), executions=10, baseline_tool_calls=2.0, baseline_latency_seconds=1.0)

    assert not monitor.assess(record, tool_calls=2, latency_seconds=1.1).drifted
    reading = monitor.assess(record, tool_calls=8, latency_seconds=1.0)
    assert reading.drifted
    assert "tool-call count deviates" in reading.detail


def test_falling_schema_adherence_counts_as_drift() -> None:
    monitor = DriftMonitor()
    record = AgentRecord(manifest=manifest(), executions=10, schema_violations=4)
    reading = monitor.assess(record, tool_calls=0, latency_seconds=0.0)
    assert reading.schema_adherence == pytest.approx(0.6)
    assert reading.drifted


def test_the_baseline_moves_gradually_rather_than_resetting_on_one_outlier() -> None:
    monitor = DriftMonitor()
    record = AgentRecord(manifest=manifest(), executions=10, baseline_tool_calls=2.0)
    monitor.update_baseline(record, tool_calls=12, latency_seconds=1.0)
    assert record.baseline_tool_calls == pytest.approx(4.0)


def test_detected_drift_is_journalled(runtime: AgentRuntime) -> None:
    record = idle_agent(runtime)
    runtime.execute("tok", request(tool_calls=(("tool.publish", {}),)))
    record.baseline_tool_calls = 10.0
    reading = runtime.assess_drift(AGENT)
    assert reading.drifted
    entries = [runtime.journal[i].payload for i in range(len(runtime.journal))]
    assert any(e["action"] == "drift_detected" for e in entries)


# -------------------------------------------------- structural constraints


def test_the_runtime_exposes_no_scheduling_verb() -> None:
    """02.3.2 — "The Workflow Engine owns scheduling; the Runtime owns execution."

    Structural, not documentary: if a scheduling verb ever appears here, the
    separation has been lost regardless of what the docstring still claims.
    """
    forbidden = {"schedule", "enqueue", "dispatch_workflow", "plan", "trigger", "retry", "queue"}
    present = {name for name in dir(AgentRuntime) if not name.startswith("_")}
    assert not (forbidden & present), f"the Runtime has acquired a scheduling verb: {forbidden & present}"


def test_cross_subsystem_imports_are_confined_to_the_adapter() -> None:
    """The adapter-module convention: exactly one file crosses subsystems."""
    import pathlib

    package = pathlib.Path(__file__).resolve().parents[1]
    foreign = ("security_gateway", "memory_gateway", "llm_router", "tool_gateway", "knowledge_gateway")
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


def test_the_journal_chain_is_intact_after_a_full_lifecycle(runtime: AgentRuntime) -> None:
    idle_agent(runtime)
    runtime.execute("tok", request())
    runtime.command("tok", AGENT, AgentState.RETIRED)
    assert runtime.journal.verify_chain()
    assert runtime.health()["journal_intact"]


def test_stall_detection_is_twice_the_activity_timeout() -> None:
    """02.4.8."""
    assert stall_threshold(manifest(activity_timeout=timedelta(minutes=5))) == timedelta(minutes=10)


def test_health_reports_the_workforce_signals_of_16_18(runtime: AgentRuntime) -> None:
    idle_agent(runtime)
    runtime.execute("tok", request())
    health = runtime.health()
    assert health["agents"] == 1
    assert health["task_success_rate"] == 1.0
    assert health["schema_conformance"] == 1.0
    assert health["by_state"] == {"idle": 1}
    assert health["heartbeat_cadence_seconds"] == 30.0


def test_health_of_a_single_agent_reports_its_standing(runtime: AgentRuntime) -> None:
    idle_agent(runtime)
    runtime.execute("tok", request())
    report = runtime.health_of(AGENT)
    assert report["agent_id"] == AGENT
    assert report["assignable"]
    assert report["executions"] == 1


def test_an_outcome_is_retrievable_by_activity_and_missing_ones_are_not_invented(
    runtime: AgentRuntime,
) -> None:
    idle_agent(runtime)
    runtime.execute("tok", request())
    assert runtime.outcome_for("act-1").succeeded
    with pytest.raises(NotFoundError):
        runtime.outcome_for("act-nonexistent")
