"""Human Interface conformance tests (05.18, 11.18, 13.33, 16.25, 17.31, 18.35,
19.36, per Build Spec Stage S8).

Four rights, each stated by several documents in nearly identical words, and
each tested here for the property that is easiest to lose:

* **approve** — no code path leads from an elapsed deadline to an approved
  state (11.18.2, 11.18.3);
* **override** — an override is irreversible *by the system* (05.18.3);
* **be informed** — routine batches, critical does not (18.35.4, 19.36.5);
* **halt** — the Panic Protocol completes within five seconds, and only a
  human resumes it (05.18.4, 17.31.4).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from core.exceptions import AgentOSError, ValidationError
from human_interface import (
    STANDING_ORDER_TTL,
    ApprovalRequest,
    ApprovalState,
    HaltedError,
    HumanInterface,
    NotHuman,
    Notification,
    OverrideScope,
    Participant,
    Severity,
    Urgency,
)
from human_interface.panic import DRILL_INTERVAL_DAYS
from kernel.panic import PANIC_BOUND_SECONDS, PanicBoundExceededError
from kernel.signals import SignalEmitter

TENANT = "tenant-alpha"
HUMAN = "human-sovereign"
AGENT = "agent-analyst"


class Clock:
    def __init__(self) -> None:
        self.now = datetime(2026, 8, 1, 12, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.now

    def advance(self, delta: timedelta) -> None:
        self.now += delta


def is_human(principal_id: str) -> bool:
    return principal_id.startswith("human-")


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def delivered() -> list[Notification]:
    return []


@pytest.fixture
def escalations() -> list[tuple[Any, str]]:
    return []


@pytest.fixture
def human(clock: Clock, delivered: list[Notification], escalations: list[tuple[Any, str]]) -> HumanInterface:
    return HumanInterface(
        is_human=is_human,
        signals=SignalEmitter(source_identity="human_interface"),
        notify=delivered.append,
        escalate=lambda trigger, detail: escalations.append((trigger, detail)),
        now=clock,
    )


def approval(
    request_id: str = "ar-1",
    decision_class: str = "C",
    deadline: datetime | None = None,
    urgency: Urgency = Urgency.ROUTINE,
    **overrides: Any,
) -> ApprovalRequest:
    defaults: dict[str, Any] = {
        "request_id": request_id,
        "tenant_id": TENANT,
        "decision_id": f"dec-{request_id}",
        "decision_class": decision_class,
        "proposal": "publish the Q3 pricing analysis",
        "rationale": "competitor pricing rose and the analysis is grounded in three sources",
        "evidence": ("mem-1", "mem-2", "mem-3"),
        "estimated_cost": 12.5,
        "risk": "medium: the publication is externally visible",
        "rollback_plan": "retract the publication through the compensating tool",
        "alternatives": ("do nothing", "publish an internal summary only"),
        "confidence": 0.82,
        "urgency": urgency,
        "deadline": deadline or datetime(2026, 8, 2, 12, 0, tzinfo=UTC),
        "requested_by": AGENT,
    }
    defaults.update(overrides)
    return ApprovalRequest(**defaults)


# ---------------------------------------------------------------- Approvals


def test_an_operator_approves_a_pending_decision(human: HumanInterface) -> None:
    human.submit_approval(approval())
    assert [r.request_id for r in human.pending_approvals(TENANT)] == ["ar-1"]
    record = human.approve("ar-1", HUMAN, note="the evidence holds")
    assert record.state == ApprovalState.APPROVED
    assert record.responded_by == HUMAN
    assert human.pending_approvals(TENANT) == []


def test_an_agent_may_not_answer_an_approval_gate(human: HumanInterface) -> None:
    """11.18.2 with 14.17.5 — self-approval is the failure this prevents."""
    human.submit_approval(approval())
    with pytest.raises(NotHuman, match="only a human may answer"):
        human.approve("ar-1", AGENT)


def test_an_incomplete_request_is_refused_at_submission(human: HumanInterface) -> None:
    """11.18.1's list is a completeness requirement.

    An operator asked to approve without the rollback plan or the alternatives
    is being asked to rubber-stamp.
    """
    with pytest.raises(ValidationError, match="rollback_plan"):
        human.submit_approval(approval(rollback_plan="  "))
    with pytest.raises(ValidationError, match="alternatives"):
        human.submit_approval(approval(request_id="ar-2", alternatives=()))
    with pytest.raises(ValidationError, match="evidence"):
        human.submit_approval(approval(request_id="ar-3", evidence=()))


def test_confidence_and_cost_are_validated(human: HumanInterface) -> None:
    with pytest.raises(ValidationError, match="confidence"):
        human.submit_approval(approval(confidence=1.4))
    with pytest.raises(ValidationError, match="cost"):
        human.submit_approval(approval(request_id="ar-2", estimated_cost=-1.0))


def test_a_class_c_deadline_defers_and_never_approves(human: HumanInterface, clock: Clock) -> None:
    """11.18.3 — "Decision is deferred, not approved. No default-to-approve.\" """
    human.submit_approval(approval(decision_class="C"))
    clock.advance(timedelta(days=2))
    expired = human.expire_approvals()
    assert [r.state for r in expired] == [ApprovalState.DEFERRED]
    assert human.approvals.get("ar-1").state != ApprovalState.APPROVED


def test_a_class_d_deadline_rejects(human: HumanInterface, clock: Clock) -> None:
    """11.18.3 — "Decision is rejected pending explicit human action.\" """
    human.submit_approval(approval(decision_class="D"))
    clock.advance(timedelta(days=2))
    assert [r.state for r in human.expire_approvals()] == [ApprovalState.REJECTED]


def test_a_deferred_request_is_still_answerable_by_a_human(human: HumanInterface, clock: Clock) -> None:
    """Deferral is not a terminal state: the operator may still decide."""
    human.submit_approval(approval())
    clock.advance(timedelta(days=2))
    human.expire_approvals()
    assert human.approve("ar-1", HUMAN).state == ApprovalState.APPROVED


def test_expiry_never_produces_an_approval_whatever_the_class(human: HumanInterface, clock: Clock) -> None:
    """The structural form of 11.18.2, checked across every class."""
    for index, decision_class in enumerate("ABCD"):
        human.submit_approval(approval(request_id=f"ar-{index}", decision_class=decision_class))
    clock.advance(timedelta(days=30))
    states = {r.state for r in human.expire_approvals()}
    assert ApprovalState.APPROVED not in states
    assert human.health()["approvals"]["auto_approved"] == 0


def test_an_answered_request_cannot_be_answered_twice(human: HumanInterface) -> None:
    human.submit_approval(approval())
    human.reject("ar-1", HUMAN)
    with pytest.raises(AgentOSError, match="already rejected"):
        human.approve("ar-1", HUMAN)


def test_an_operator_may_demand_modification_instead_of_deciding(human: HumanInterface) -> None:
    human.submit_approval(approval())
    record = human.demand_modification("ar-1", HUMAN, note="widen the alternatives")
    assert record.state == ApprovalState.MODIFICATION_DEMANDED


# ----------------------------------------------------------------- Batching


def test_a_batch_is_presented_together_and_answered_separately(human: HumanInterface) -> None:
    """11.18.4 — batched items "are never auto-approved as a group.\" """
    for n in range(3):
        human.submit_approval(approval(request_id=f"ar-{n}"))
    batch = human.batch_approvals("batch-1", TENANT, ["ar-0", "ar-1", "ar-2"], "same publication cycle")
    assert batch.items == ("ar-0", "ar-1", "ar-2")

    human.approve("ar-0", HUMAN)
    states = [r.state for r in human.approvals.batch_items("batch-1")]
    assert states == [ApprovalState.APPROVED, ApprovalState.PENDING, ApprovalState.PENDING]


def test_there_is_no_verb_that_answers_a_whole_batch(human: HumanInterface) -> None:
    """Structural: one click consenting to things the operator never read."""
    forbidden = {"approve_batch", "reject_batch", "approve_all", "bulk_approve"}
    present = {name for name in dir(human.approvals) if not name.startswith("_")}
    assert not (forbidden & present)
    assert not (forbidden & {name for name in dir(human) if not name.startswith("_")})


def test_a_batch_may_not_cross_the_tenant_boundary(human: HumanInterface) -> None:
    human.submit_approval(approval(request_id="ar-0"))
    human.submit_approval(approval(request_id="ar-1", tenant_id="tenant-beta"))
    with pytest.raises(ValidationError, match="another tenant"):
        human.batch_approvals("batch-1", TENANT, ["ar-0", "ar-1"], "mixed")


def test_an_empty_batch_is_refused(human: HumanInterface) -> None:
    with pytest.raises(ValidationError, match="not a batch"):
        human.batch_approvals("batch-1", TENANT, [], "nothing")


# ---------------------------------------------------------------- Overrides


def test_a_human_overrides_an_agent_action(human: HumanInterface) -> None:
    """05.18.3 — immediate, irreversible by the runtime, logged."""
    override = human.override(
        "ov-1", TENANT, OverrideScope.AGENT_ACTION, AGENT, "stop publishing", "the analysis is stale", HUMAN
    )
    assert override.decision_class == "D"
    assert human.overrides.latest_for(AGENT) is override


def test_an_agent_may_not_issue_an_override(human: HumanInterface) -> None:
    with pytest.raises(NotHuman):
        human.override("ov-1", TENANT, OverrideScope.AGENT_ACTION, AGENT, "resume", "because", AGENT)


def test_an_override_carries_a_reason(human: HumanInterface) -> None:
    """It is logged and will be reviewed; an unexplained override cannot be."""
    with pytest.raises(ValidationError, match="reason"):
        human.override("ov-1", TENANT, OverrideScope.WORKFLOW, "wf-1", "halt", "   ", HUMAN)


def test_the_ledger_exposes_no_verb_that_undoes_an_override(human: HumanInterface) -> None:
    """05.18.3's load-bearing half: "irreversible by the runtime".

    Structural, because a `revoke` reachable by a service would let the system
    undo the human's correction, which is exactly the failure the clause names.
    """
    forbidden = {"revoke", "delete", "remove", "reverse", "undo", "clear"}
    present = {name for name in dir(human.overrides) if not name.startswith("_")}
    assert not (forbidden & present), f"the override ledger became reversible: {forbidden & present}"


def test_an_override_is_frozen_once_issued(human: HumanInterface) -> None:
    override = human.override("ov-1", TENANT, OverrideScope.DECISION, "dec-1", "reject", "policy", HUMAN)
    with pytest.raises(Exception):  # noqa: B017 - FrozenInstanceError
        override.directive = "approve"  # type: ignore[misc]


def test_a_later_override_supersedes_without_erasing_the_earlier(human: HumanInterface) -> None:
    """The only way to change an override's effect is a new human action."""
    human.override("ov-1", TENANT, OverrideScope.WORKFLOW, "wf-1", "halt", "suspected drift", HUMAN)
    human.override("ov-2", TENANT, OverrideScope.WORKFLOW, "wf-1", "resume", "drift ruled out", HUMAN)
    history = human.overrides.for_target("wf-1")
    assert [o.override_id for o in history] == ["ov-1", "ov-2"]
    assert len(human.overrides) == 2


@pytest.mark.parametrize("scope", list(OverrideScope))
def test_every_documented_override_scope_is_available(human: HumanInterface, scope: OverrideScope) -> None:
    """Seven documents each grant the right over their own domain."""
    assert (
        human.override(f"ov-{scope.value}", TENANT, scope, "target-1", "halt", "operator judgement", HUMAN).scope
        == scope
    )


# ----------------------------------------------------------- Standing orders


def test_a_standing_order_is_scoped_time_bounded_and_revocable(human: HumanInterface, clock: Clock) -> None:
    """05.18.5 with 16.25.3's 30-day expiry."""
    order = human.delegate("so-1", TENANT, HUMAN, frozenset({"decisions.routine"}), "approve routine reposts")
    assert order.expires_at == clock() + STANDING_ORDER_TTL
    assert order.is_active(clock())

    clock.advance(STANDING_ORDER_TTL + timedelta(seconds=1))
    assert not order.is_active(clock())
    assert human.standing_orders.active(TENANT) == []


def test_an_unscoped_standing_order_is_refused(human: HumanInterface) -> None:
    """It would be indistinguishable from removing the gate entirely."""
    with pytest.raises(ValidationError, match="must be scoped"):
        human.delegate("so-1", TENANT, HUMAN, frozenset(), "approve anything")


def test_renewal_is_an_explicit_human_act(human: HumanInterface, clock: Clock) -> None:
    """16.25.3 — "expire after 30 days unless renewed", not "unless still used"."""
    human.delegate("so-1", TENANT, HUMAN, frozenset({"decisions.routine"}), "approve reposts")
    clock.advance(timedelta(days=29))
    with pytest.raises(NotHuman):
        human.standing_orders.renew("so-1", AGENT)
    renewed = human.standing_orders.renew("so-1", HUMAN)
    assert renewed.renewals == 1
    clock.advance(timedelta(days=29))
    assert renewed.is_active(clock())


def test_a_revoked_order_stops_covering_and_cannot_be_renewed(human: HumanInterface) -> None:
    human.delegate("so-1", TENANT, HUMAN, frozenset({"decisions.routine"}), "approve reposts")
    assert human.standing_orders.covering(TENANT, "decisions.routine.repost") is not None
    human.standing_orders.revoke("so-1", HUMAN)
    assert human.standing_orders.covering(TENANT, "decisions.routine.repost") is None
    with pytest.raises(AgentOSError, match="revoked"):
        human.standing_orders.renew("so-1", HUMAN)


def test_an_order_covers_its_scope_and_nothing_beyond_it(human: HumanInterface) -> None:
    human.delegate("so-1", TENANT, HUMAN, frozenset({"decisions.routine"}), "approve reposts")
    assert human.standing_orders.covering(TENANT, "decisions.routine") is not None
    assert human.standing_orders.covering(TENANT, "decisions.irreversible") is None
    assert human.standing_orders.covering("tenant-beta", "decisions.routine") is None


# ------------------------------------------------------------ Digests


def test_routine_notifications_are_batched_not_delivered_one_by_one(
    human: HumanInterface, delivered: list[Notification], clock: Clock
) -> None:
    """The Build Spec's "batched (not spammed)" requirement."""
    for n in range(5):
        human.raise_notification(_notification(f"n-{n}", Severity.ROUTINE, clock()))
    assert delivered == [], "nothing routine interrupted the operator"
    assert human.digests.pending_count(TENANT) == 5

    digest = human.deliver_digest(TENANT, "digest-1")
    assert digest.size == 5
    assert human.digests.pending_count(TENANT) == 0


def test_a_critical_notification_is_delivered_immediately(
    human: HumanInterface, delivered: list[Notification], clock: Clock
) -> None:
    """18.35.4, 19.36.5 — batching the one alert that could not wait is a failure."""
    channel = human.raise_notification(_notification("n-crit", Severity.CRITICAL, clock()))
    assert channel == "immediate"
    assert [n.notification_id for n in delivered] == ["n-crit"]
    assert human.digests.pending_count(TENANT) == 0


def test_severity_decides_the_channel_and_the_caller_cannot_override_it(human: HumanInterface, clock: Clock) -> None:
    """Structural: no argument to `submit` selects the channel."""
    assert human.raise_notification(_notification("a", Severity.ROUTINE, clock())) == "digest"
    assert human.raise_notification(_notification("b", Severity.ELEVATED, clock())) == "digest"
    assert human.raise_notification(_notification("c", Severity.CRITICAL, clock())) == "immediate"


def test_a_digest_becomes_due_after_the_configured_cadence(human: HumanInterface, clock: Clock) -> None:
    human.raise_notification(_notification("n-0", Severity.ROUTINE, clock()))
    assert not human.digest_due(TENANT)
    clock.advance(timedelta(hours=7))
    assert human.digest_due(TENANT)


def test_cadence_is_configurable_per_tenant(human: HumanInterface, clock: Clock) -> None:
    """16.25.3 — humans configure digest cadence."""
    human.digests.configure_cadence(TENANT, timedelta(minutes=30))
    human.raise_notification(_notification("n-0", Severity.ROUTINE, clock()))
    clock.advance(timedelta(minutes=31))
    assert human.digest_due(TENANT)


def test_an_empty_digest_is_refused(human: HumanInterface) -> None:
    with pytest.raises(ValidationError, match="noise"):
        human.deliver_digest(TENANT, "digest-1")


def test_elevated_items_sort_ahead_of_routine_within_a_digest(human: HumanInterface, clock: Clock) -> None:
    human.raise_notification(_notification("routine", Severity.ROUTINE, clock()))
    clock.advance(timedelta(minutes=1))
    human.raise_notification(_notification("elevated", Severity.ELEVATED, clock()))
    digest = human.deliver_digest(TENANT, "digest-1")
    assert [n.notification_id for n in digest.items] == ["elevated", "routine"]


# ------------------------------------------------------------ Panic Protocol


def test_panic_halts_every_registered_participant(human: HumanInterface) -> None:
    halted: list[str] = []
    for name in ("agent_runtime", "workflow_engine", "tool_gateway"):
        human.register_panic_participant(
            Participant(name=name, halt=lambda n=name: halted.append(n))  # type: ignore[misc]
        )
    report = human.invoke_panic(HUMAN, "suspected drift across the workforce")
    assert set(halted) == {"agent_runtime", "workflow_engine", "tool_gateway"}
    assert report.halted == ("agent_runtime", "workflow_engine", "tool_gateway")
    assert human.panic.halted


def test_panic_completes_within_the_five_second_bound(human: HumanInterface) -> None:
    """17.31.4 — "Panic completion must occur within 5 seconds."

    A real timed assertion, per the Build Specification's S8 validation
    criteria. The participants do real work; the bound is measured, not
    stipulated.
    """
    import time

    for n in range(25):
        human.register_panic_participant(
            Participant(name=f"subsystem-{n}", halt=lambda: time.sleep(0.001), disclose=lambda: {"anomalies": []})
        )
    started = time.monotonic()
    report = human.invoke_panic(HUMAN, "drill")
    measured = time.monotonic() - started

    assert report.within_bound
    assert report.elapsed_seconds <= PANIC_BOUND_SECONDS
    assert measured <= PANIC_BOUND_SECONDS, f"panic took {measured:.3f}s wall-clock"


def test_a_participant_that_overruns_the_bound_is_recorded_and_escalated(
    clock: Clock, escalations: list[tuple[Any, str]]
) -> None:
    """A panic that silently took nine seconds is a violation nobody would learn about."""
    ticks = iter([0.0, 9.0, 9.0, 9.0])
    interface = HumanInterface(
        is_human=is_human,
        signals=SignalEmitter(source_identity="human_interface"),
        escalate=lambda trigger, detail: escalations.append((trigger, detail)),
        now=clock,
    )
    interface.panic.monotonic = lambda: next(ticks)
    interface.register_panic_participant(Participant(name="slow", halt=lambda: None))

    with pytest.raises(PanicBoundExceededError):
        interface.invoke_panic(HUMAN, "drill")

    assert interface.panic.halted, "the halt still completed"
    report = interface.panic.reports()[-1]
    assert not report.within_bound
    assert report.elapsed_seconds == 9.0
    assert any("exceeding the 5.0s bound" in detail for _trigger, detail in escalations)


def test_a_failing_participant_cannot_veto_the_halt(human: HumanInterface, escalations: list[tuple[Any, str]]) -> None:
    """A subsystem that could veto panic could veto human sovereignty."""

    def explode() -> None:
        raise RuntimeError("the tool gateway is wedged")

    human.register_panic_participant(Participant(name="tool_gateway", halt=explode))
    human.register_panic_participant(Participant(name="agent_runtime", halt=lambda: None))

    report = human.invoke_panic(HUMAN, "wedged subsystem")
    assert human.panic.halted
    assert report.halted == ("agent_runtime",)
    assert report.failed[0][0] == "tool_gateway"
    assert escalations, "the failed hook was escalated rather than swallowed"


def test_only_a_human_may_invoke_panic(human: HumanInterface) -> None:
    with pytest.raises(NotHuman, match="sovereign act"):
        human.invoke_panic(AGENT, "the agent decided to halt itself")


def test_only_a_human_may_resume(human: HumanInterface) -> None:
    """05.18.4 — "requires human intervention to resume"."""
    human.invoke_panic(HUMAN, "drill")
    with pytest.raises(NotHuman):
        human.resume(AGENT)
    human.resume(HUMAN, note="condition cleared")
    assert not human.panic.halted


def test_there_is_no_automatic_path_out_of_a_halt(human: HumanInterface, clock: Clock) -> None:
    """Structural: no timer, no timeout, no auto-resume verb."""
    forbidden = {"auto_resume", "resume_after", "expire", "timeout", "unhalt"}
    present = {name for name in dir(human.panic) if not name.startswith("_")}
    assert not (forbidden & present)
    human.invoke_panic(HUMAN, "drill")
    clock.advance(timedelta(days=30))
    assert human.panic.halted, "elapsed time does not lift a panic"


def test_resuming_a_system_that_is_not_halted_is_refused(human: HumanInterface) -> None:
    with pytest.raises(AgentOSError, match="not halted"):
        human.resume(HUMAN)


def test_panic_discloses_what_each_subsystem_knows(human: HumanInterface) -> None:
    """16.25.4 — panic "prioritizes completeness over cognitive load minimization"."""
    human.register_panic_participant(
        Participant(
            name="observability",
            halt=lambda: None,
            disclose=lambda: {"active_anomalies": ["cost spike"], "in_flight_decisions": 2},
        )
    )
    report = human.invoke_panic(HUMAN, "cost spike")
    assert report.disclosure["observability"]["active_anomalies"] == ["cost spike"]


def test_a_failing_disclosure_does_not_break_the_panic(human: HumanInterface) -> None:
    def explode() -> dict[str, Any]:
        raise RuntimeError("the query path is down")

    human.register_panic_participant(Participant(name="observability", halt=lambda: None, disclose=explode))
    report = human.invoke_panic(HUMAN, "drill")
    assert "disclosure_failed" in report.disclosure["observability"]


def test_panic_flushes_queued_routine_digests(human: HumanInterface, clock: Clock) -> None:
    """During panic, completeness beats cognitive load (16.25.4)."""
    for n in range(3):
        human.raise_notification(_notification(f"n-{n}", Severity.ROUTINE, clock()))
    report = human.invoke_panic(HUMAN, "drill")
    assert report.digests_flushed == 1
    assert human.digests.pending_count(TENANT) == 0


def test_autonomous_work_is_refused_while_halted_and_humans_are_not(human: HumanInterface) -> None:
    human.invoke_panic(HUMAN, "drill")
    with pytest.raises(HaltedError, match="Panic Protocol is active"):
        human.assert_not_halted("workflow.advance")
    # The human plane keeps working: overriding is often how the operator
    # resolves the condition that caused the panic.
    assert human.override("ov-1", TENANT, OverrideScope.WORKFLOW, "wf-1", "cancel", "unsafe", HUMAN)
    human.resume(HUMAN)
    human.assert_not_halted("workflow.advance")


def test_a_drill_exercises_the_real_hooks_and_leaves_the_system_running(human: HumanInterface) -> None:
    """05.18.4 — "always available and tested monthly"."""
    calls: list[str] = []
    human.register_panic_participant(Participant(name="agent_runtime", halt=lambda: calls.append("halt")))
    report = human.panic.drill(HUMAN)
    assert calls == ["halt"], "the drill ran the real hook, not a mock of it"
    assert not human.panic.halted
    assert report.within_bound
    assert human.panic.health()["days_since_drill"] == 0.0


def test_an_overdue_drill_is_visible_in_health(human: HumanInterface, clock: Clock) -> None:
    assert human.panic.health()["drill_overdue"], "never drilled counts as overdue"
    human.panic.drill(HUMAN)
    assert not human.panic.health()["drill_overdue"]
    clock.advance(timedelta(days=DRILL_INTERVAL_DAYS + 1))
    assert human.panic.health()["drill_overdue"]


def test_a_participant_may_not_register_twice(human: HumanInterface) -> None:
    human.register_panic_participant(Participant(name="agent_runtime", halt=lambda: None))
    with pytest.raises(AgentOSError, match="already a panic participant"):
        human.register_panic_participant(Participant(name="agent_runtime", halt=lambda: None))


def test_the_panic_journal_records_every_invocation_and_stays_intact(human: HumanInterface) -> None:
    human.invoke_panic(HUMAN, "first")
    human.resume(HUMAN)
    human.invoke_panic(HUMAN, "second")
    health = human.panic.health()
    assert health["invocations"] == 2
    assert health["bound_breaches"] == 0
    assert health["journal_intact"]


# ------------------------------------------------------------------ Health


def test_health_consolidates_every_human_plane_signal(human: HumanInterface) -> None:
    human.submit_approval(approval())
    human.override("ov-1", TENANT, OverrideScope.DECISION, "dec-1", "reject", "policy", HUMAN)
    human.delegate("so-1", TENANT, HUMAN, frozenset({"decisions.routine"}), "approve reposts")
    health = human.health()
    assert health["approvals"]["open"] == 1
    assert health["overrides"] == 1
    assert health["standing_orders"]["active"] == 1
    assert health["standing_orders"]["ttl_days"] == 30
    assert health["panic"]["bound_seconds"] == PANIC_BOUND_SECONDS


def _notification(notification_id: str, severity: Severity, at: datetime) -> Notification:
    return Notification(
        notification_id=notification_id,
        tenant_id=TENANT,
        severity=severity,
        subsystem="observability_gateway",
        summary=f"{severity.value} event",
        detail={},
        raised_at=at,
    )
