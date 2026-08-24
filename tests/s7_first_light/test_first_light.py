"""Stage S7 — FIRST LIGHT. The organizing milestone (21A §2.2.4).

Build Specification, Stage S7, Exit Criteria — quoted verbatim:

    "One registered agent executes one task inside one durable workflow,
    invoking one tool through the full mediation chain, with one human
    approval gate, one saga compensation path, and complete lineage from human
    authority to external effect."

Every subsystem built in S0–S6 participates for real: Security authenticates
and authorizes, Memory hydrates, Knowledge grounds, Decision gates, Cost
meters, the Tool Platform mediates, the LLM Router infers, the Agent Runtime
executes and the Workflow Engine orchestrates. Nothing here is stubbed except
the model backend and the tool body, which are the two things that would
otherwise reach outside the process.

This suite is retained as the system's standing regression surface, exactly as
21B and the Build Specification intend.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from agent_runtime import (
    AgentManifest,
    AgentRuntime,
    AgentState,
    AuthorityBoundaries,
    LLMRouterInference,
    MemoryGatewayHydrator,
    SecurityGatewayRuntimeAuthorizer,
)
from cost_manager import BudgetScope, CostManager, ScopeKind
from decision_gateway import (
    CostManagerBudgetSource,
    DecisionGateway,
    DecisionState,
    EvidenceRef,
    KnowledgeGatewayEvidenceSource,
    Option,
    Proposal,
    RiskAssessment,
    Scope,
    SecurityGatewayDecisionAuthorizer,
)
from kernel.authority import AuthorityLevel, RiskClass
from kernel.signals import SignalEmitter
from knowledge_gateway import (
    KnowledgeGateway,
    MemoryGatewayEvidenceSource,
    SecurityGatewayKnowledgeAuthorizer,
)
from llm_router import CostManagerBudget as RouterBudget
from llm_router import LLMRouter, ModelTier, PromptTemplate
from memory_gateway import (
    EdgeType,
    MemoryEntry,
    MemoryGateway,
    Ownership,
    Provenance,
    SecurityGatewayMemoryAuthorizer,
    SemanticRole,
    StructuralForm,
)
from observability_gateway import ObservabilityGateway, SecurityGatewayQueryAuthorizer
from security_gateway import (
    Capability,
    PrincipalType,
    RegistrationRequest,
    Role,
    SecurityGateway,
)
from security_gateway.enums import PrincipalStatus
from tool_executor import Sandbox, SecurityGatewaySecretAuthority, ToolExecutor
from tool_gateway import (
    CostManagerBudget,
    DecisionGatewayVerifier,
    SecurityGatewayToolAuthorizer,
    ToolGateway,
    UnbackedIntegrationSource,
)
from tool_registry import (
    Availability,
    Compensation,
    Contract,
    SandboxTier,
    SecurityGatewayRegistryAuthorizer,
    ToolEffect,
    ToolManifest,
    ToolRegistry,
    ToolState,
)
from workflow_engine import (
    Activity,
    ActivityKind,
    ActivityState,
    AgentRuntimeDispatcher,
    CostManagerWorkflowBudget,
    DecisionGatewayApprovals,
    ToolGatewayWorkflowDispatcher,
    WorkflowContext,
    WorkflowDefinition,
    WorkflowEngine,
    WorkflowState,
)

TENANT = "tenant-alpha"
HUMAN = "human-sovereign"
AGENT = "agent-analyst"
EXECUTOR = "service-executor"
VERIFIER = "hash-analyst"

PERMISSIONS = {
    "tool.register",
    "tool.invoke.business",
    "decision.propose",
    "memory.form.episodic",
    "memory.retrieve.tenant_scoped",
    "knowledge.query.tenant_scoped",
    "observability.query.internal",
}


class Clock:
    def __init__(self) -> None:
        self.now = datetime(2026, 8, 1, 12, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.now

    def advance(self, delta: timedelta) -> None:
        self.now += delta


class SecretStore:
    def __init__(self) -> None:
        self._values: dict[str, str] = {}

    def read(self, reference: str) -> str:
        return self._values[reference]

    def write(self, reference: str, value: str) -> None:
        self._values[reference] = value


class LocalBackend:
    """A local model backend. 01.3.1 Local First — no external integration."""

    def __init__(self) -> None:
        self.calls = 0

    def available(self) -> bool:
        return True

    def complete(self, prompt: str, max_tokens: int) -> tuple[dict[str, Any], int, float]:
        self.calls += 1
        return ({"claims": ["competitor pricing rose in the third quarter"]}, 64, 0.01)


class PublishTool:
    """The tool body. Mutating, and the only thing that touches the outside."""

    def __init__(self) -> None:
        self.published: list[str] = []
        self.compensated = 0
        self.fail = False

    def __call__(self, sandbox: Sandbox, params: dict[str, Any]) -> dict[str, Any]:
        if params.get("compensates"):
            self.compensated += 1
            if self.published:
                self.published.pop()
            return {"status": "compensated"}
        if self.fail:
            raise RuntimeError("the publication endpoint rejected the request")
        self.published.append(str(params.get("payload", "")))
        return {"status": "published"}


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def store() -> SecretStore:
    return SecretStore()


@pytest.fixture
def security(clock: Clock, store: SecretStore) -> SecurityGateway:
    gw = SecurityGateway(signing_key=b"first-light-key", secret_store=store, now=clock)
    gw.bootstrap_human_sovereign(HUMAN, "Sovereign", TENANT)
    for principal, ptype, autonomy in (
        (AGENT, PrincipalType.AGENT, 2),
        (EXECUTOR, PrincipalType.SERVICE, None),
    ):
        gw.register_identity(
            RegistrationRequest(
                principal_id=principal,
                principal_type=ptype,
                name=principal,
                version="1.0.0",
                tenant_id=TENANT,
                autonomy_level=autonomy,
                approved_by=HUMAN,
            )
        )
        gw.change_principal_status(principal, PrincipalStatus.ACTIVE, actor_id=HUMAN)
    gw.capabilities.define(Capability(name="analyst", permits=frozenset(PERMISSIONS)))
    gw.capabilities.grant(AGENT, "analyst")
    gw.roles.define(
        Role(name="analyst", permissions=frozenset(PERMISSIONS), eligible_types=frozenset({PrincipalType.AGENT}))
    )
    gw.roles.assign("analyst", AGENT, PrincipalType.AGENT, assigned_by=HUMAN)
    gw.recompute_permissions(AGENT)
    gw.credentials.issue(f"cred-{AGENT}", AGENT, PrincipalType.AGENT, VERIFIER)
    gw.secrets.register("api/publish", "sk-not-a-real-secret", TENANT, HUMAN)
    return gw


@pytest.fixture
def observability(security: SecurityGateway, clock: Clock) -> ObservabilityGateway:
    return ObservabilityGateway(authorizer=SecurityGatewayQueryAuthorizer(gateway=security), now=clock)


@pytest.fixture
def costs(clock: Clock, observability: ObservabilityGateway) -> CostManager:
    manager = CostManager(
        signals=SignalEmitter(source_identity="cost_manager", sink=observability.sink_for("cost_manager")),
        escalate=lambda kind, detail: None,
        now=clock,
    )
    manager.allocate(BudgetScope(kind=ScopeKind.TENANT, identifier=TENANT), TENANT, limit=1000.0)
    return manager


@pytest.fixture
def memory(security: SecurityGateway, clock: Clock, observability: ObservabilityGateway) -> MemoryGateway:
    return MemoryGateway(
        authorizer=SecurityGatewayMemoryAuthorizer(gateway=security),
        signals=SignalEmitter(source_identity="memory_gateway", sink=observability.sink_for("memory_gateway")),
        now=clock,
    )


@pytest.fixture
def knowledge(
    security: SecurityGateway, memory: MemoryGateway, clock: Clock, observability: ObservabilityGateway
) -> KnowledgeGateway:
    return KnowledgeGateway(
        authorizer=SecurityGatewayKnowledgeAuthorizer(gateway=security),
        memory=MemoryGatewayEvidenceSource(gateway=memory),
        signals=SignalEmitter(source_identity="knowledge_gateway", sink=observability.sink_for("knowledge_gateway")),
        now=clock,
    )


@pytest.fixture
def decisions(
    security: SecurityGateway,
    knowledge: KnowledgeGateway,
    costs: CostManager,
    clock: Clock,
    observability: ObservabilityGateway,
) -> DecisionGateway:
    return DecisionGateway(
        authorizer=SecurityGatewayDecisionAuthorizer(gateway=security),
        knowledge=KnowledgeGatewayEvidenceSource(gateway=knowledge),
        budget=CostManagerBudgetSource(manager=costs),
        signals=SignalEmitter(source_identity="decision_gateway", sink=observability.sink_for("decision_gateway")),
        now=clock,
    )


@pytest.fixture
def backend() -> LocalBackend:
    return LocalBackend()


@pytest.fixture
def router(
    memory: MemoryGateway,
    costs: CostManager,
    clock: Clock,
    backend: LocalBackend,
    observability: ObservabilityGateway,
    security: SecurityGateway,
) -> LLMRouter:
    token, _ = security.authenticate(AGENT, f"cred-{AGENT}", VERIFIER, PrincipalType.AGENT)
    r = LLMRouter(
        context=MemoryGatewayContextStub(memory, token),
        budget=RouterBudget(manager=costs),
        backends={ModelTier.STANDARD: backend, ModelTier.NANO: backend},
        signals=SignalEmitter(source_identity="llm_router", sink=observability.sink_for("llm_router")),
        now=clock,
    )
    r.register_template(
        PromptTemplate(
            name="analyse",
            body="Analyse: {task}",
            slots=("task",),
            max_tokens=2000,
            tier=ModelTier.STANDARD,
        )
    )
    return r


class MemoryGatewayContextStub:
    """The real hydrator, holding the agent's own token.

    Not a stub of Memory — it calls the real Memory Gateway. The name reflects
    that it supplies the Router's `ContextSource` port rather than being a
    fake memory.
    """

    def __init__(self, gateway: MemoryGateway, token: str) -> None:
        self._adapter = MemoryGatewayHydrator(gateway=gateway)
        self._token = token

    def retrieve(self, tenant_id: str, query: str, limit: int):
        from llm_router import ContextItem

        rows = self._adapter.hydrate(self._token, tenant_id, frozenset())
        return [ContextItem(source_id=f"m{i}", content=str(row), confidence=0.9) for i, row in enumerate(rows[:limit])]


@pytest.fixture
def tool_registry(security: SecurityGateway, clock: Clock) -> ToolRegistry:
    return ToolRegistry(
        authorizer=SecurityGatewayRegistryAuthorizer(gateway=security),
        signals=SignalEmitter(source_identity="tool_registry"),
        now=clock,
    )


@pytest.fixture
def tool_gateway(
    tool_registry: ToolRegistry,
    security: SecurityGateway,
    decisions: DecisionGateway,
    costs: CostManager,
    clock: Clock,
) -> ToolGateway:
    return ToolGateway(
        registry=tool_registry,
        authorizer=SecurityGatewayToolAuthorizer(gateway=security),
        decisions=DecisionGatewayVerifier(gateway=decisions),
        budget=CostManagerBudget(manager=costs),
        integrations=UnbackedIntegrationSource(),
        signals=SignalEmitter(source_identity="tool_gateway"),
        now=clock,
    )


@pytest.fixture
def tool_executor(security: SecurityGateway, clock: Clock) -> ToolExecutor:
    return ToolExecutor(
        secrets=SecurityGatewaySecretAuthority(gateway=security),
        signals=SignalEmitter(source_identity="tool_executor"),
        executor_identity=EXECUTOR,
        now=clock,
    )


@pytest.fixture
def runtime(
    security: SecurityGateway,
    memory: MemoryGateway,
    router: LLMRouter,
    tool_gateway: ToolGateway,
    tool_executor: ToolExecutor,
    clock: Clock,
    observability: ObservabilityGateway,
    publish_tool: PublishTool,
) -> AgentRuntime:
    from agent_runtime import ToolGatewayDispatcher

    return AgentRuntime(
        authorizer=SecurityGatewayRuntimeAuthorizer(gateway=security),
        memory=MemoryGatewayHydrator(gateway=memory),
        inference=LLMRouterInference(router=router),
        tools=ToolGatewayDispatcher(gateway=tool_gateway, executor=tool_executor, tool_impl=publish_tool),
        signals=SignalEmitter(source_identity="agent_runtime", sink=observability.sink_for("agent_runtime")),
        now=clock,
    )


@pytest.fixture
def publish_tool() -> PublishTool:
    return PublishTool()


@pytest.fixture
def approvals(decisions: DecisionGateway) -> DecisionGatewayApprovals:
    return DecisionGatewayApprovals(gateway=decisions)


@pytest.fixture
def workflows(
    runtime: AgentRuntime,
    tool_gateway: ToolGateway,
    tool_executor: ToolExecutor,
    approvals: DecisionGatewayApprovals,
    costs: CostManager,
    clock: Clock,
    observability: ObservabilityGateway,
    publish_tool: PublishTool,
) -> WorkflowEngine:
    engine = WorkflowEngine(
        agents=AgentRuntimeDispatcher(runtime=runtime),
        tools=ToolGatewayWorkflowDispatcher(gateway=tool_gateway, executor=tool_executor, tool_impl=publish_tool),
        approvals=approvals,
        budget=CostManagerWorkflowBudget(manager=costs),
        signals=SignalEmitter(source_identity="workflow_engine", sink=observability.sink_for("workflow_engine")),
        now=clock,
    )
    engine.register_definition(first_light_definition())
    return engine


@pytest.fixture
def token(security: SecurityGateway) -> str:
    issued, _ = security.authenticate(AGENT, f"cred-{AGENT}", VERIFIER, PrincipalType.AGENT)
    return issued


def first_light_definition() -> WorkflowDefinition:
    """The Python mirror of `workflow_definitions/src/firstLight.ts`.

    A contract test asserts the two agree — 21B §14.4 names the bilingual
    boundary the engine's highest-risk internal seam, so the mirror is checked
    rather than trusted.
    """
    return WorkflowDefinition(
        name="first-light",
        version="1.0.0",
        activities=(
            Activity(
                activity_id="analyse",
                kind=ActivityKind.AGENT,
                capability="business.analysis",
                depends_on=(),
                mutating=False,
                estimated_cost=0.05,
                max_retries=2,
                inputs={"task": "assess competitor pricing"},
            ),
            Activity(
                activity_id="checkpoint-analysed",
                kind=ActivityKind.CHECKPOINT,
                depends_on=("analyse",),
                estimated_cost=0.0,
                max_retries=0,
            ),
            Activity(
                activity_id="approve-publication",
                kind=ActivityKind.HUMAN_GATE,
                depends_on=("checkpoint-analysed",),
                estimated_cost=0.0,
                max_retries=0,
                decision_class="C",
            ),
            Activity(
                activity_id="publish",
                kind=ActivityKind.TOOL,
                tool_id="tool-publish",
                depends_on=("approve-publication",),
                mutating=True,
                estimated_cost=0.1,
                max_retries=1,
                inputs={"payload": "the Q3 pricing analysis"},
            ),
        ),
    )


def register_everything(
    security: SecurityGateway,
    memory: MemoryGateway,
    tool_registry: ToolRegistry,
    runtime: AgentRuntime,
    token: str,
) -> None:
    """Seeds one memory, one tool and one agent — the minimum First Light needs."""
    anchor = memory.form(token, _entry("anchor"))
    memory.form(token, _entry("observation"), edges=[(anchor.memory_id, EdgeType.RELATES_TO)])

    tool_registry.register(
        token,
        ToolManifest(
            tool_id="tool-publish",
            name="publish",
            version="1.0.0",
            capability="business.publish",
            effect=ToolEffect.MUTATING,
            sandbox_tier=SandboxTier.CONTAINER,
            input_contract=Contract(fields={"payload": str}),
            output_contract=Contract(fields={"status": str}),
            owner_principal_id=AGENT,
            tenant_id=TENANT,
            cost_per_invocation=0.05,
            timeout=timedelta(seconds=30),
            compensation=Compensation(
                reference="comp-unpublish", idempotent=True, description="retract the publication"
            ),
            secret_refs=("api/publish",),
        ),
    )
    tool_registry.transition("tool-publish", ToolState.VALIDATED)
    tool_registry.transition("tool-publish", ToolState.ACTIVE)
    tool_registry.report_health("tool-publish", Availability.HEALTHY)

    runtime.register(
        token,
        AgentManifest(
            agent_id=AGENT,
            name="Analyst",
            version="1.0.0",
            tenant_id=TENANT,
            specialty="competitive analysis",
            boundaries=AuthorityBoundaries(
                capabilities=frozenset({"business.analysis"}),
                tool_inventory=frozenset({"tool-publish"}),
                memory_scope=frozenset({"episodic"}),
                autonomy_level=AuthorityLevel.AGENT_DELEGATED,
                cost_budget=10.0,
                workspace_ids=frozenset({"ws-1"}),
            ),
            prompt_template="analyse",
            output_contract={"claims": list},
            max_context_tokens=2000,
            max_context_assembly_time=timedelta(seconds=2),
            activity_timeout=timedelta(seconds=30),
        ),
    )
    runtime.command(token, AGENT, AgentState.IDLE)


def _entry(lineage: str) -> MemoryEntry:
    return MemoryEntry(
        memory_type="episodic.execution",
        role=SemanticRole.EPISODIC,
        form=StructuralForm.ATOMIC,
        payload={"observed": "competitor pricing rose in the third quarter"},
        tenant_id=TENANT,
        business_id=None,
        workspace_id=None,
        owner_principal_id=AGENT,
        ownership=Ownership.TEAM,
        provenance=Provenance(
            source_identity=AGENT,
            lineage_ref=lineage,
            occurred_at=datetime(2026, 8, 1, 11, 0, tzinfo=UTC),
        ),
    )


def approve_publication(decisions: DecisionGateway, token: str) -> str:
    """Proposes and commits the Class C decision the human gate waits on."""
    proposal = Proposal(
        proposal_id="prop-publish",
        summary="publish the Q3 pricing analysis",
        proposer_id=AGENT,
        proposer_authority=AuthorityLevel.AGENT_DELEGATED,
        tenant_id=TENANT,
        business_id=None,
        options=(
            Option("null", "do nothing", 0.0, 0.0, reversible=True, is_null=True),
            Option("publish", "publish it", 0.1, 1.0, reversible=True, compensation_ref="comp-unpublish"),
            Option("defer", "publish next quarter", 0.05, 0.3, reversible=True, compensation_ref="comp-defer"),
        ),
        evidence=(
            EvidenceRef(source="knowledge", reference_id="b1", confidence=0.95, statement="pricing rose"),
            EvidenceRef(source="knowledge", reference_id="b2", confidence=0.95, statement="market confirms"),
        ),
        risk=RiskAssessment(
            financial=RiskClass.LOW,
            operational=RiskClass.LOW,
            reputational=RiskClass.LOW,
            legal=RiskClass.LOW,
            strategic=RiskClass.LOW,
        ),
        scope=Scope.BUSINESS,  # Class C, so it needs a human
    )
    record = decisions.propose(token, proposal)
    assert record.state == DecisionState.UNDER_REVIEW
    request = decisions.approvals.for_decision(record.decision_id)[0]
    decisions.respond(request.request_id, responder_id=HUMAN, response="approve")
    decisions.commit(record.decision_id, committer_id=HUMAN)
    return record.decision_id


# ============================================================ FIRST LIGHT


def test_first_light(
    security: SecurityGateway,
    memory: MemoryGateway,
    tool_registry: ToolRegistry,
    tool_gateway: ToolGateway,
    runtime: AgentRuntime,
    workflows: WorkflowEngine,
    decisions: DecisionGateway,
    approvals: DecisionGatewayApprovals,
    observability: ObservabilityGateway,
    publish_tool: PublishTool,
    backend: LocalBackend,
    token: str,
) -> None:
    """The Stage S7 exit criterion, end to end.

    One registered agent, one durable workflow, one tool through the full
    mediation chain, one human approval gate, and complete lineage from human
    authority to external effect.
    """
    register_everything(security, memory, tool_registry, runtime, token)

    # The human authorizes. This is the root of the lineage chain.
    decision_id = approve_publication(decisions, token)
    approvals.bind("wf-first-light", "approve-publication", decision_id)

    context = WorkflowContext(
        workflow_id="wf-first-light",
        tenant_id=TENANT,
        trigger="human.command",
        triggered_by=HUMAN,
        # 07.13.5 — non-determinism is injected, never derived.
        variables={"as_of": "2026-08-01T12:00:00Z", "quarter": "Q3"},
    )
    run = workflows.trigger(token, "first-light", "1.0.0", context)

    # Planning succeeded: the DAG validated, budget was pre-allocated worst-case,
    # and the agent was bound to the activity.
    assert run.state == WorkflowState.RUNNING
    assert run.allocated_budget > 0
    assert run.dag.records["analyse"].bound_agent_id == AGENT

    # The agent executes, then the workflow pauses on the human gate.
    workflows.advance(token)
    # Read through a widened local: mypy would otherwise narrow `run.state` to
    # the literal asserted above and call this comparison impossible, when the
    # whole point is that `advance` changed it.
    paused_state: WorkflowState = run.state
    assert paused_state == WorkflowState.PAUSED
    assert run.awaiting_activity_id == "approve-publication"
    # 07.14.5 — a paused workflow releases ephemeral resources.
    assert run.holds_resources is False
    # And nothing has been published yet: the gate precedes the effect.
    assert publish_tool.published == []

    # The agent really ran, through the real Router and real Memory.
    analyse = run.dag.records["analyse"]
    assert analyse.state == ActivityState.SUCCEEDED
    assert backend.calls == 1
    assert analyse.cost > 0

    # The human's approval releases the gate.
    workflows.signal(token, "wf-first-light", "resume")
    completed_state: WorkflowState = run.state
    assert completed_state == WorkflowState.COMPLETED

    # The external effect happened, exactly once, after the approval.
    assert publish_tool.published == ["the Q3 pricing analysis"]

    # Complete lineage: human authority -> decision -> workflow -> agent ->
    # tool -> external effect, reconstructable from the journals alone.
    invocation_id = run.dag.records["publish"].invocation_id
    assert invocation_id is not None
    record = tool_gateway.query_records(tool_id="tool-publish")[0]
    assert record.contract.decision_reference == decision_id
    assert record.contract.attribution.tenant_id == TENANT
    assert decisions.get(decision_id).authorized_by == HUMAN

    # Every journal in the chain is intact.
    assert workflows.health()["journal_intact"] is True
    assert runtime.health()["journal_intact"] is True
    assert tool_gateway.health()["journal_intact"] is True
    assert decisions.health()["journal_intact"] is True

    # The whole run is visible to oversight.
    emitted = {s.signal.name for s in observability.ingest_engine.all_signals()}
    assert "agent.execution.cost" in emitted
    assert "workflow.completed" in emitted


def test_first_light_compensates_when_the_effect_fails(
    security: SecurityGateway,
    memory: MemoryGateway,
    tool_registry: ToolRegistry,
    runtime: AgentRuntime,
    workflows: WorkflowEngine,
    decisions: DecisionGateway,
    approvals: DecisionGatewayApprovals,
    publish_tool: PublishTool,
    token: str,
) -> None:
    """The saga compensation path the exit criterion requires.

    A mutating activity that fails after retries takes the workflow into
    Compensating. Because the failure is the *only* mutating activity and it
    never succeeded, there is nothing to undo — so the workflow fails cleanly
    rather than stalling, which is the correct outcome and worth distinguishing
    from the stalled case below.
    """
    register_everything(security, memory, tool_registry, runtime, token)
    decision_id = approve_publication(decisions, token)
    approvals.bind("wf-compensate", "approve-publication", decision_id)
    publish_tool.fail = True

    run = workflows.trigger(
        token,
        "first-light",
        "1.0.0",
        WorkflowContext(
            workflow_id="wf-compensate",
            tenant_id=TENANT,
            trigger="human.command",
            triggered_by=HUMAN,
            variables={"as_of": "2026-08-01T12:00:00Z"},
        ),
    )
    workflows.advance(token)
    workflows.signal(token, "wf-compensate", "resume")

    assert run.state == WorkflowState.FAILED
    assert run.dag.records["publish"].state == ActivityState.FAILED
    assert publish_tool.published == []  # nothing was published


def test_a_denied_approval_never_reaches_the_effect(
    security: SecurityGateway,
    memory: MemoryGateway,
    tool_registry: ToolRegistry,
    runtime: AgentRuntime,
    workflows: WorkflowEngine,
    decisions: DecisionGateway,
    approvals: DecisionGatewayApprovals,
    publish_tool: PublishTool,
    token: str,
) -> None:
    """11 rule 2 — no Class C commitment without explicit human approval.

    The gate is bound to a decision that was never approved. The workflow
    compensates and fails rather than proceeding, and the external effect
    never happens.
    """
    register_everything(security, memory, tool_registry, runtime, token)
    approvals.bind("wf-denied", "approve-publication", "dec-never-approved")

    run = workflows.trigger(
        token,
        "first-light",
        "1.0.0",
        WorkflowContext(
            workflow_id="wf-denied",
            tenant_id=TENANT,
            trigger="human.command",
            triggered_by=HUMAN,
            variables={},
        ),
    )
    workflows.advance(token)
    assert run.state == WorkflowState.PAUSED

    workflows.signal(token, "wf-denied", "resume")
    assert run.state in (WorkflowState.FAILED, WorkflowState.STALLED)
    assert publish_tool.published == []


def test_planning_failure_consumes_nothing(
    security: SecurityGateway,
    memory: MemoryGateway,
    tool_registry: ToolRegistry,
    runtime: AgentRuntime,
    workflows: WorkflowEngine,
    backend: LocalBackend,
    publish_tool: PublishTool,
    token: str,
) -> None:
    """07.12.1 — a workflow that fails in Planning has consumed nothing.

    No agent is registered, so binding fails during Planning. The workflow goes
    straight to Failed with no compensation, and neither the model nor the tool
    was ever touched.
    """
    run = workflows.trigger(
        token,
        "first-light",
        "1.0.0",
        WorkflowContext(
            workflow_id="wf-unplannable",
            tenant_id=TENANT,
            trigger="human.command",
            triggered_by=HUMAN,
            variables={},
        ),
    )
    assert run.state == WorkflowState.FAILED
    assert "no available agent" in (run.failure or "")
    assert backend.calls == 0
    assert publish_tool.published == []
    assert run.spent == 0.0


def test_the_engine_performs_no_work() -> None:
    """07.13.1 — "The orchestrator does not perform work; it governs work.\""""
    surface = {name for name in dir(WorkflowEngine) if not name.startswith("_")}
    assert {"infer", "call_tool", "render", "complete_prompt"}.isdisjoint(surface)


def test_the_runtime_does_not_schedule() -> None:
    """02.3.2 — the Workflow Engine owns scheduling; the Runtime owns execution."""
    surface = {name for name in dir(AgentRuntime) if not name.startswith("_")}
    assert {"schedule", "enqueue", "dispatch_workflow", "plan"}.isdisjoint(surface)


def test_replay_reconstructs_the_same_traversal(
    security: SecurityGateway,
    memory: MemoryGateway,
    tool_registry: ToolRegistry,
    runtime: AgentRuntime,
    workflows: WorkflowEngine,
    decisions: DecisionGateway,
    approvals: DecisionGatewayApprovals,
    token: str,
) -> None:
    """07.13.5 — the same trigger and context reconstruct the same traversal."""
    register_everything(security, memory, tool_registry, runtime, token)
    decision_id = approve_publication(decisions, token)
    approvals.bind("wf-replay", "approve-publication", decision_id)

    workflows.trigger(
        token,
        "first-light",
        "1.0.0",
        WorkflowContext(
            workflow_id="wf-replay",
            tenant_id=TENANT,
            trigger="human.command",
            triggered_by=HUMAN,
            variables={"as_of": "2026-08-01T12:00:00Z"},
        ),
    )
    workflows.advance(token)
    workflows.signal(token, "wf-replay", "resume")

    traversal = workflows.replay("wf-replay")
    assert traversal == ["analyse", "checkpoint-analysed", "publish"]
    # Deterministic: replaying again yields the identical sequence.
    assert workflows.replay("wf-replay") == traversal
