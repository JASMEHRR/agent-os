"""Stage S8 — Human Plane. The exit criterion, exercised end to end.

21_PLAN §4.1, S8, verbatim:

    "Operators approve, override, receive batched digests, and invoke the
    Panic Protocol within the 5-second bound."

Nothing here is stubbed on the trust path: the API Gateway authenticates and
authorizes through the real Security Gateway, and the Panic Protocol halts a
real Agent Runtime and a real Workflow Engine, both carrying live state from
Stage S7.

The timed assertion the Build Specification's S8 validation criteria require
lives in `test_the_panic_protocol_completes_within_five_seconds`.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from agent_runtime import (
    AgentManifest,
    AgentRuntime,
    AgentState,
    AuthorityBoundaries,
    SecurityGatewayRuntimeAuthorizer,
)
from api_gateway import (
    CREATED,
    FORBIDDEN,
    OK,
    TOO_MANY_REQUESTS,
    UNAUTHORIZED,
    APIGateway,
    Method,
    Request,
    Response,
    Route,
    SecurityGatewayIngressAuthority,
    paginate,
)
from human_interface import (
    ApprovalRequest,
    ApprovalState,
    HumanInterface,
    Notification,
    OverrideScope,
    Participant,
    Severity,
    Urgency,
)
from kernel.authority import AuthorityLevel
from kernel.panic import PANIC_BOUND_SECONDS
from kernel.signals import SignalEmitter
from security_gateway import Capability, PrincipalType, RegistrationRequest, Role, SecurityGateway
from security_gateway.enums import PrincipalStatus
from workflow_engine import (
    Activity,
    ActivityKind,
    WorkflowContext,
    WorkflowDefinition,
    WorkflowEngine,
    WorkflowState,
)

TENANT = "tenant-alpha"
HUMAN = "human-sovereign"
ADMIN = "human-admin"
AGENT = "agent-analyst"
VERIFIER = "hash-analyst"

OPERATOR_PERMISSIONS = {
    "approvals.read",
    "approvals.respond",
    "overrides.issue",
    "panic.invoke",
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


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def security(clock: Clock) -> SecurityGateway:
    gw = SecurityGateway(signing_key=b"s8-human-plane", secret_store=SecretStore(), now=clock)
    gw.bootstrap_human_sovereign(HUMAN, "Sovereign", TENANT)
    # A second human, because 14 rule 3 forbids self-escalation: the sovereign
    # may not assign itself the operator role.
    gw.register_identity(
        RegistrationRequest(
            principal_id=ADMIN,
            principal_type=PrincipalType.HUMAN,
            name=ADMIN,
            version="1.0.0",
            tenant_id=TENANT,
            approved_by=HUMAN,
        )
    )
    gw.change_principal_status(ADMIN, PrincipalStatus.ACTIVE, actor_id=HUMAN)
    gw.register_identity(
        RegistrationRequest(
            principal_id=AGENT,
            principal_type=PrincipalType.AGENT,
            name=AGENT,
            version="1.0.0",
            tenant_id=TENANT,
            autonomy_level=2,
            approved_by=HUMAN,
        )
    )
    gw.change_principal_status(AGENT, PrincipalStatus.ACTIVE, actor_id=HUMAN)

    gw.capabilities.define(Capability(name="operator", permits=frozenset(OPERATOR_PERMISSIONS)))
    gw.capabilities.grant(HUMAN, "operator")
    gw.roles.define(
        Role(
            name="operator",
            permissions=frozenset(OPERATOR_PERMISSIONS),
            eligible_types=frozenset({PrincipalType.HUMAN}),
        )
    )
    gw.roles.assign("operator", HUMAN, PrincipalType.HUMAN, assigned_by=ADMIN)
    gw.recompute_permissions(HUMAN)

    gw.capabilities.define(Capability(name="analyst", permits=frozenset({"approvals.read"})))
    gw.capabilities.grant(AGENT, "analyst")
    gw.roles.define(
        Role(
            name="analyst",
            permissions=frozenset({"approvals.read"}),
            eligible_types=frozenset({PrincipalType.AGENT}),
        )
    )
    gw.roles.assign("analyst", AGENT, PrincipalType.AGENT, assigned_by=HUMAN)
    gw.recompute_permissions(AGENT)

    gw.credentials.issue(f"cred-{HUMAN}", HUMAN, PrincipalType.HUMAN, VERIFIER)
    gw.credentials.issue(f"cred-{AGENT}", AGENT, PrincipalType.AGENT, VERIFIER)
    return gw


@pytest.fixture
def human_token(security: SecurityGateway) -> str:
    token, _claims = security.authenticate(HUMAN, f"cred-{HUMAN}", VERIFIER, PrincipalType.HUMAN)
    return str(token)


@pytest.fixture
def agent_token(security: SecurityGateway) -> str:
    token, _claims = security.authenticate(AGENT, f"cred-{AGENT}", VERIFIER, PrincipalType.AGENT)
    return str(token)


@pytest.fixture
def delivered() -> list[Notification]:
    return []


@pytest.fixture
def human(security: SecurityGateway, clock: Clock, delivered: list[Notification]) -> HumanInterface:
    def is_human(principal_id: str) -> bool:
        if not security.registry.exists(principal_id):
            return False
        return security.registry.get(principal_id).principal_type == PrincipalType.HUMAN

    return HumanInterface(
        is_human=is_human,
        signals=SignalEmitter(source_identity="human_interface"),
        notify=delivered.append,
        now=clock,
    )


@pytest.fixture
def api(security: SecurityGateway, human: HumanInterface, clock: Clock) -> APIGateway:
    """The real ingress, wired to the real Trust Plane and the real human plane."""
    gateway = APIGateway(
        authority=SecurityGatewayIngressAuthority(gateway=security),
        signals=SignalEmitter(source_identity="api_gateway"),
        now=clock,
    )

    def list_pending(request: Request, principal_id: str, tenant_id: str) -> Response:
        records = human.pending_approvals(tenant_id)
        page = paginate(
            [{"id": r.request_id, "proposal": r.request.proposal, "class": r.request.decision_class} for r in records],
            cursor=request.query.get("cursor"),
            limit=int(request.query.get("limit", 50)),
        )
        return Response(status=OK, body=page.to_body())

    def respond(request: Request, principal_id: str, tenant_id: str) -> Response:
        record = human.approve(request.body["request_id"], principal_id, request.body.get("note", ""))
        return Response(status=CREATED, body={"request_id": record.request_id, "state": record.state.value})

    def issue_override(request: Request, principal_id: str, tenant_id: str) -> Response:
        override = human.override(
            request.body["override_id"],
            tenant_id,
            OverrideScope(request.body["scope"]),
            request.body["target_id"],
            request.body["directive"],
            request.body["reason"],
            principal_id,
        )
        return Response(status=CREATED, body={"override_id": override.override_id, "class": override.decision_class})

    def invoke_panic(request: Request, principal_id: str, tenant_id: str) -> Response:
        report = human.invoke_panic(principal_id, request.body.get("reason", "operator invoked"))
        return Response(
            status=CREATED,
            body={
                "halted": list(report.halted),
                "elapsed_seconds": report.elapsed_seconds,
                "within_bound": report.within_bound,
            },
        )

    gateway.register_route(Route(Method.GET, "/approvals", "approvals.read", list_pending))
    gateway.register_route(Route(Method.POST, "/approvals/respond", "approvals.respond", respond))
    gateway.register_route(Route(Method.POST, "/overrides", "overrides.issue", issue_override))
    gateway.register_route(Route(Method.POST, "/panic", "panic.invoke", invoke_panic))
    return gateway


@pytest.fixture
def runtime(security: SecurityGateway, clock: Clock) -> AgentRuntime:
    """A real Agent Runtime, so panic halts something that actually holds state."""

    class NoMemory:
        def hydrate(self, token: str, tenant_id: str, scope: frozenset[str]) -> list[dict[str, Any]]:
            return []

    class NoInference:
        def infer(
            self, template: str, slots: dict[str, str], tenant_id: str, principal_id: str, max_cost: float
        ) -> tuple[dict[str, Any], float, bool]:
            return ({"summary": "unused"}, 0.0, True)

    class NoTools:
        def invoke(
            self,
            token: str,
            tool_id: str,
            decision_id: str,
            parameters: dict[str, Any],
            cost_ceiling: float,
            idempotency_key: str,
        ) -> tuple[bool, dict[str, Any] | None, float]:
            return (True, {}, 0.0)

    rt = AgentRuntime(
        authorizer=SecurityGatewayRuntimeAuthorizer(gateway=security),
        memory=NoMemory(),
        inference=NoInference(),
        tools=NoTools(),
        signals=SignalEmitter(source_identity="agent_runtime"),
        now=clock,
    )
    return rt


def approval_request(request_id: str = "ar-1", decision_class: str = "C") -> ApprovalRequest:
    return ApprovalRequest(
        request_id=request_id,
        tenant_id=TENANT,
        decision_id=f"dec-{request_id}",
        decision_class=decision_class,
        proposal="publish the Q3 pricing analysis",
        rationale="competitor pricing rose across three independent sources",
        evidence=("mem-1", "mem-2", "mem-3"),
        estimated_cost=12.5,
        risk="medium: externally visible",
        rollback_plan="retract through the compensating tool",
        alternatives=("do nothing", "publish internally only"),
        confidence=0.82,
        urgency=Urgency.ROUTINE,
        deadline=datetime(2026, 8, 2, 12, 0, tzinfo=UTC),
        requested_by=AGENT,
    )


def bearer(method: Method, path: str, token: str, body: dict[str, Any] | None = None, key: str = "idem-1") -> Request:
    headers = {"Idempotency-Key": key} if method.is_mutating else {}
    return Request(method=method, path=path, token=token, body=body or {}, headers=headers)


# ------------------------------------------------- the four operator rights


def test_an_operator_approves_a_pending_decision_through_the_api(
    api: APIGateway, human: HumanInterface, human_token: str
) -> None:
    """Right one: approve. Through real ingress, real auth, real registry."""
    human.submit_approval(approval_request())

    listing = api.handle(bearer(Method.GET, "/v1/approvals", human_token))
    assert listing.status == OK
    assert [item["id"] for item in listing.body["data"]] == ["ar-1"]

    answered = api.handle(
        bearer(Method.POST, "/v1/approvals/respond", human_token, {"request_id": "ar-1", "note": "evidence holds"})
    )
    assert answered.status == CREATED
    assert answered.body["state"] == ApprovalState.APPROVED.value
    assert human.approvals.get("ar-1").responded_by == HUMAN


def test_an_agent_cannot_answer_an_approval_through_the_api(
    api: APIGateway, human: HumanInterface, agent_token: str
) -> None:
    """Two independent barriers, and the outer one fires first.

    The API Gateway refuses on the missing permission; had it not, the
    Human Interface would still refuse on the principal not being human. Both
    are asserted, because a system with one barrier has none once it is moved.
    """
    human.submit_approval(approval_request())
    refused = api.handle(bearer(Method.POST, "/v1/approvals/respond", agent_token, {"request_id": "ar-1"}))
    assert refused.status == FORBIDDEN

    from human_interface import NotHuman

    with pytest.raises(NotHuman):
        human.approve("ar-1", AGENT)


def test_an_operator_overrides_an_agent_action_through_the_api(
    api: APIGateway, human: HumanInterface, human_token: str
) -> None:
    """Right two: override. Immediate, Class D, irreversible by the system."""
    response = api.handle(
        bearer(
            Method.POST,
            "/v1/overrides",
            human_token,
            {
                "override_id": "ov-1",
                "scope": OverrideScope.AGENT_ACTION.value,
                "target_id": AGENT,
                "directive": "stop publishing",
                "reason": "the underlying analysis is stale",
            },
        )
    )
    assert response.status == CREATED
    assert response.body["class"] == "D"
    assert human.overrides.latest_for(AGENT) is not None
    assert "revoke" not in dir(human.overrides)


def test_an_operator_receives_batched_digests_not_a_stream_of_alerts(
    human: HumanInterface, delivered: list[Notification], clock: Clock
) -> None:
    """Right three: batched, not spammed (18.35.4, 19.36.5)."""
    for n in range(8):
        human.raise_notification(
            Notification(
                notification_id=f"routine-{n}",
                tenant_id=TENANT,
                severity=Severity.ROUTINE,
                subsystem="cost_manager",
                summary="a routine cost datapoint",
                detail={},
                raised_at=clock(),
            )
        )
    assert delivered == [], "eight routine events interrupted the operator zero times"

    human.raise_notification(
        Notification(
            notification_id="sovereignty-breach",
            tenant_id=TENANT,
            severity=Severity.CRITICAL,
            subsystem="deployment_gateway",
            summary="geographic drift detected",
            detail={},
            raised_at=clock(),
        )
    )
    assert [n.notification_id for n in delivered] == ["sovereignty-breach"], "the critical event did not wait"

    clock.advance(timedelta(hours=7))
    assert human.digest_due(TENANT)
    digest = human.deliver_digest(TENANT, "digest-1")
    assert digest.size == 8


def test_the_panic_protocol_completes_within_five_seconds(
    api: APIGateway,
    human: HumanInterface,
    runtime: AgentRuntime,
    human_token: str,
    security: SecurityGateway,
    clock: Clock,
) -> None:
    """Right four, and the Build Specification's named timed assertion.

    `17.31.4`: "Panic completion must occur within 5 seconds."

    The participants are real: a registered Agent Runtime holding an idle
    agent, and a Workflow Engine holding a running workflow. Both are halted,
    and the elapsed time is measured against the constitutional bound rather
    than asserted to be within it.
    """
    manifest = AgentManifest(
        agent_id=AGENT,
        name=AGENT,
        version="1.0.0",
        tenant_id=TENANT,
        specialty="market analysis",
        boundaries=AuthorityBoundaries(
            capabilities=frozenset({"analysis"}),
            tool_inventory=frozenset(),
            memory_scope=frozenset({"tenant"}),
            autonomy_level=AuthorityLevel.AGENT_DELEGATED,
            cost_budget=1.0,
            workspace_ids=frozenset({"ws-1"}),
        ),
        prompt_template="analyse {context}",
        output_contract={"summary": str},
        max_context_tokens=1000,
        max_context_assembly_time=timedelta(seconds=5),
        activity_timeout=timedelta(minutes=5),
    )
    agent_token, _ = security.authenticate(AGENT, f"cred-{AGENT}", VERIFIER, PrincipalType.AGENT)
    runtime.register(str(agent_token), manifest)
    runtime.command(str(agent_token), AGENT, AgentState.IDLE)

    halted: list[str] = []

    def halt_runtime() -> None:
        runtime.command(str(agent_token), AGENT, AgentState.SUSPENDED, reason="panic protocol")
        halted.append("agent_runtime")

    human.register_panic_participant(
        Participant(
            name="agent_runtime",
            halt=halt_runtime,
            disclose=lambda: {"agents": runtime.health()["agents"], "in_use": runtime.health()["worker_pool"]},
        )
    )

    engine = _running_engine(clock)
    human.register_panic_participant(
        Participant(
            name="workflow_engine",
            halt=lambda: _cancel(engine),
            disclose=lambda: {"in_flight": engine.health()["by_state"]},
        )
    )
    human.register_panic_participant(
        Participant(name="security_gateway", halt=lambda: halted.append("security_gateway"))
    )

    started = time.monotonic()
    response = api.handle(
        bearer(Method.POST, "/v1/panic", human_token, {"reason": "operator observed unsafe behaviour"})
    )
    measured = time.monotonic() - started

    assert response.status == CREATED
    assert response.body["within_bound"]
    assert response.body["elapsed_seconds"] <= PANIC_BOUND_SECONDS
    assert measured <= PANIC_BOUND_SECONDS, f"panic took {measured:.3f}s, exceeding the {PANIC_BOUND_SECONDS}s bound"

    # It really halted: the agent is suspended and the workflow cancelled.
    assert runtime.get(AGENT).state == AgentState.SUSPENDED
    assert engine.get("wf-panic").state == WorkflowState.CANCELLED
    assert set(response.body["halted"]) == {"agent_runtime", "workflow_engine", "security_gateway"}
    assert human.panic.halted


def test_only_human_intervention_resumes_after_panic(
    api: APIGateway, human: HumanInterface, human_token: str, agent_token: str, clock: Clock
) -> None:
    """05.18.4's closing clause, which a resume-on-timer would negate entirely."""
    api.handle(bearer(Method.POST, "/v1/panic", human_token, {"reason": "drill"}))
    assert human.panic.halted

    clock.advance(timedelta(days=7))
    assert human.panic.halted, "a week of elapsed time did not lift the halt"

    from human_interface import NotHuman

    with pytest.raises(NotHuman):
        human.resume(AGENT)
    human.resume(HUMAN, note="condition cleared")
    assert not human.panic.halted


# --------------------------------------------- ingress guarantees, wired real


def test_ingress_refuses_an_unauthenticated_caller(api: APIGateway) -> None:
    assert api.handle(Request(method=Method.GET, path="/v1/approvals")).status == UNAUTHORIZED


def test_a_replayed_approval_does_not_answer_twice(api: APIGateway, human: HumanInterface, human_token: str) -> None:
    """03 §32.2 protecting a human action: a retried click must not double-answer."""
    human.submit_approval(approval_request())
    request = bearer(Method.POST, "/v1/approvals/respond", human_token, {"request_id": "ar-1"}, key="click-1")
    first = api.handle(request)
    second = api.handle(request)
    assert first.body == second.body
    assert second.replayed
    assert human.approvals.get("ar-1").state == ApprovalState.APPROVED


def test_the_operator_console_paginates_by_cursor(api: APIGateway, human: HumanInterface, human_token: str) -> None:
    for n in range(5):
        human.submit_approval(approval_request(request_id=f"ar-{n}"))
    first = api.handle(Request(method=Method.GET, path="/v1/approvals", token=human_token, query={"limit": "2"}))
    assert len(first.body["data"]) == 2
    cursor = first.body["pagination"]["next_cursor"]
    second = api.handle(
        Request(method=Method.GET, path="/v1/approvals", token=human_token, query={"limit": "2", "cursor": cursor})
    )
    assert [item["id"] for item in second.body["data"]] == ["ar-2", "ar-3"]


def test_an_operator_flooding_the_console_is_throttled_not_served(
    api: APIGateway, human: HumanInterface, human_token: str
) -> None:
    """Rate limiting applies to humans too: a runaway console is still a flood."""
    api.limiter.configure("user", HUMAN, rate_per_minute=2, burst=2)
    statuses = [api.handle(bearer(Method.GET, "/v1/approvals", human_token)).status for _ in range(4)]
    assert statuses.count(TOO_MANY_REQUESTS) == 2


def test_the_human_plane_reports_its_own_health(api: APIGateway, human: HumanInterface, human_token: str) -> None:
    human.submit_approval(approval_request())
    api.handle(bearer(Method.GET, "/v1/approvals", human_token))
    assert api.health()["requests_handled"] == 1
    assert human.health()["approvals"]["open"] == 1
    assert human.health()["panic"]["bound_seconds"] == PANIC_BOUND_SECONDS


def _cancel(engine: WorkflowEngine) -> None:
    """A halt hook returns nothing; the run it cancelled is read back afterwards."""
    engine.signal("token", "wf-panic", "cancel")


def _running_engine(clock: Clock) -> WorkflowEngine:
    """A Workflow Engine with one workflow actually in flight."""

    class Agents:
        def discover(self, token: str, capability: str, min_reputation: float) -> list[Any]:
            class Bound:
                agent_id = AGENT

            return [Bound()]

        def execute(self, token: str, **fields: Any) -> Any:  # pragma: no cover - panic halts first
            raise AssertionError("the workflow was cancelled before dispatch")

    class Tools:
        def invoke(
            self, token: str, tool_id: str, decision_id: str, parameters: dict[str, Any], cost_ceiling: float, key: str
        ) -> tuple[bool, dict[str, Any] | None, float, str]:  # pragma: no cover
            raise AssertionError("no tool runs in this fixture")

        def compensate(self, token: str, invocation_id: str, decision_id: str) -> bool:  # pragma: no cover
            return True

    class Approvals:
        def request_approval(self, workflow_id: str, activity_id: str, decision_class: str) -> str:
            return "dec-gate"

        def is_approved(self, decision_id: str) -> bool:
            return False

    class Budget:
        def has_headroom(self, tenant_id: str, cost: float) -> bool:
            return True

    engine = WorkflowEngine(
        agents=Agents(),
        tools=Tools(),
        approvals=Approvals(),
        budget=Budget(),
        signals=SignalEmitter(source_identity="workflow_engine"),
        now=clock,
    )
    engine.register_definition(
        WorkflowDefinition(
            name="in-flight",
            version="1.0.0",
            activities=(
                Activity(activity_id="analyse", kind=ActivityKind.AGENT, capability="analysis", estimated_cost=0.1),
            ),
        )
    )
    engine.trigger(
        "token",
        "in-flight",
        "1.0.0",
        WorkflowContext(workflow_id="wf-panic", tenant_id=TENANT, trigger="manual", triggered_by=HUMAN, variables={}),
    )
    return engine
