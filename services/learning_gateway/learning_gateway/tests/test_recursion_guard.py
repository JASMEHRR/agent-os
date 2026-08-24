"""Adversarial tests for the Recursion Guard (21C §38.5, 13.21.3, 13 rules 4, 17).

`21C` §38.5 requires exactly this file:

> Recursion Guard components require dedicated adversarial tests that attempt
> self-referential inputs, since their fail-closed posture is only meaningful
> if exercised against genuine self-reference attempts, not merely
> ordinary-path tests.

So these are not ordinary-path tests. Each one is an attempt to get a
self-modifying learning entry past the guard, written as an attacker would
write it: disguised names, indirection through evidence, self-modification
described in the language of an unrelated target, and recursive triggering.

The guard must fail **closed** on every one. A guard that failed open on an
input it did not anticipate would be worse than no guard, because the system
would believe it had one.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from core.exceptions import AgentOSError
from kernel.escalation import EscalationTrigger
from learning_gateway import (
    SELF_IDENTIFIERS,
    RecursionAnomaly,
    RecursionGuard,
    TargetClass,
    normalize,
)


class Clock:
    def __init__(self) -> None:
        self.now = datetime(2026, 8, 1, 12, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.now

    def advance(self, delta: timedelta) -> None:
        self.now += delta


@pytest.fixture
def alerts() -> list[str]:
    return []


@pytest.fixture
def escalations() -> list[tuple[EscalationTrigger, str]]:
    return []


@pytest.fixture
def guard(alerts: list[str], escalations: list[tuple[EscalationTrigger, str]]) -> RecursionGuard:
    return RecursionGuard(
        escalate=lambda trigger, detail: escalations.append((trigger, detail)),
        alert_human=alerts.append,
        now=Clock(),
    )


# ------------------------------------------- the direct attempt, for baseline


def test_the_declared_self_target_is_blocked(guard: RecursionGuard) -> None:
    """The obvious attempt, which any guard would catch. Baseline, not the point."""
    with pytest.raises(RecursionAnomaly, match="Recursion Anomaly"):
        guard.check(TargetClass.LEARNING, "memory_gateway", "mem-1")


def test_an_ordinary_entry_passes(guard: RecursionGuard) -> None:
    """The guard must not block everything; a guard that did would be useless."""
    guard.check(
        TargetClass.AGENT,
        "agent_runtime",
        "agent-analyst",
        proposal="raise the retry ceiling for the pricing analyst",
        evidence_kinds=("decision_journal", "tool_invocation"),
    )
    assert not guard.suspended


# --------------------------------------- attempt 1: disguise the target name


@pytest.mark.parametrize(
    "disguise",
    [
        "learning",
        "Learning",
        "LEARNING",
        "learning_gateway",
        "learning-gateway",
        "Learning Gateway",
        "  learning  ",
        "learning.gateway",
        "l e a r n i n g",
        "LeArNiNg_GaTeWaY",
        "learning/gateway",
        "learning::gateway",
        "learningSubsystem",
        "learning_journal",
        "meta-learning",
        "self_learning",
        "13",
        "doc-13",
        "document 13",
    ],
)
def test_a_disguised_target_name_is_blocked(guard: RecursionGuard, disguise: str) -> None:
    """Normalization strips punctuation, case and spacing before matching.

    An attacker who only has to change `learning_gateway` to `Learning-Gateway`
    to get through has defeated the guard with a keystroke.
    """
    with pytest.raises(RecursionAnomaly):
        guard.check(TargetClass.AGENT, disguise, "subject-1")


def test_the_subject_is_checked_as_well_as_the_subsystem(guard: RecursionGuard) -> None:
    """Naming a plausible target and pointing the subject at Learning."""
    with pytest.raises(RecursionAnomaly, match="subject_id"):
        guard.check(TargetClass.AGENT, "agent_runtime", "learning_gateway")


def test_every_known_self_identifier_is_actually_blocked(guard: RecursionGuard) -> None:
    """The identifier set is not decoration: each member is exercised."""
    for identifier in SELF_IDENTIFIERS:
        finding = guard.inspect(TargetClass.AGENT, identifier, "subject-1")
        assert finding.blocked, f"'{identifier}' is listed as a self-identifier but does not block"


# ----------------------------------- attempt 2: indirection through evidence


def test_an_entry_reasoning_about_the_learning_journal_is_blocked(guard: RecursionGuard) -> None:
    """A legitimate-looking target, with the evidence coming from inside.

    This is the subtle version: the entry proposes something about the Agent
    Runtime, but derives it from the Learning Journal, which makes it a
    conclusion about Learning's own behaviour wearing another subsystem's
    label.
    """
    with pytest.raises(RecursionAnomaly, match="originates inside"):
        guard.check(
            TargetClass.AGENT,
            "agent_runtime",
            "agent-analyst",
            proposal="agents whose proposals we accepted performed better",
            evidence_kinds=("decision_journal", "learning_journal"),
        )


@pytest.mark.parametrize("kind", ["learning_journal", "Learning-Entry", "learning pattern", "FailureLibrary"])
def test_every_self_originating_evidence_kind_is_blocked(guard: RecursionGuard, kind: str) -> None:
    with pytest.raises(RecursionAnomaly):
        guard.check(TargetClass.TOOL, "tool_gateway", "tool.publish", evidence_kinds=(kind,))


# ------------------------- attempt 3: self-modification in another's clothing


@pytest.mark.parametrize(
    "proposal",
    [
        "relax the validation rule that rejects low-confidence proposals",
        "lower the confidence threshold for workflow-class entries",
        "shorten the measurement window so improvements confirm sooner",
        "allow a learning cycle to run without a budget check",
        "make the recursion guard tolerant of internal evidence",
        "retune the attribution engine to weight replication more heavily",
        "reduce the evidence sufficiency count for decision learning",
    ],
)
def test_self_modification_described_as_another_subsystems_change_is_blocked(
    guard: RecursionGuard, proposal: str
) -> None:
    """The most dangerous attempt, and the one a naive guard misses.

    Every one of these declares an innocent target. Every one of them would,
    if adopted, change how Learning validates its own future proposals — which
    is 13.35.1's "own validation rules, confidence thresholds, or measurement
    windows", requiring human approval and never autonomous propagation.

    A guard checking only the target field would pass all seven.
    """
    with pytest.raises(RecursionAnomaly, match="13.35.1"):
        guard.check(TargetClass.WORKFLOW, "workflow_engine", "wf-pricing", proposal=proposal)


# ------------------------------- attempt 4: recursive cycle triggering (r.17)


def test_a_cycle_triggered_by_a_learning_event_is_blocked(guard: RecursionGuard) -> None:
    """13 rule 17 — recursive triggering needs explicit human authorization.

    Left open, this is the runaway: each entry's own lifecycle event triggers
    the next cycle, and the subsystem generates learning about its learning
    without bound.
    """
    with pytest.raises(RecursionAnomaly, match="13 rule 17"):
        guard.check(
            TargetClass.AGENT,
            "agent_runtime",
            "agent-analyst",
            triggered_by_event="learning.entry.confirmed",
        )


def test_a_cycle_triggered_by_an_ordinary_event_passes(guard: RecursionGuard) -> None:
    guard.check(TargetClass.AGENT, "agent_runtime", "agent-analyst", triggered_by_event="workflow.completed")
    assert not guard.suspended


# ------------------------------------------- attempt 5: bypass by parameter


def test_the_guard_accepts_no_bypass_argument() -> None:
    """13 rule 4's authority is a separate human act, never a call parameter.

    Structural: if a `force`, `allow_self_reference` or `override` parameter
    ever appears, the guard becomes advisory, and the caller that most wants
    to bypass it is the code that just triggered it.
    """
    import inspect
    from collections.abc import Callable
    from typing import Any

    methods: list[tuple[str, Callable[..., Any]]] = [
        ("check", RecursionGuard.check),
        ("inspect", RecursionGuard.inspect),
    ]
    forbidden = {"force", "allow", "allow_self_reference", "override", "bypass", "skip", "trusted"}
    for name, method in methods:
        parameters = set(inspect.signature(method).parameters)
        assert not (parameters & forbidden), f"{name} grew a bypass parameter: {parameters & forbidden}"


def test_a_suspension_cannot_be_lifted_without_a_named_human(guard: RecursionGuard) -> None:
    """A suspension liftable by passing a truthy value is liftable by its cause."""
    with pytest.raises(RecursionAnomaly):
        guard.check(TargetClass.LEARNING, "learning_gateway", "self")
    assert guard.suspended
    with pytest.raises(AgentOSError, match="named human principal"):
        guard.release("")
    guard.release("human-sovereign", note="reviewed, benign")
    assert not guard.suspended


# ------------------------------------------------ the response, not just the block


def test_a_blocked_attempt_suspends_rather_than_merely_rejecting(guard: RecursionGuard) -> None:
    """13.21.3 requires "immediate human alert and suspension", not rejection."""
    with pytest.raises(RecursionAnomaly):
        guard.check(TargetClass.LEARNING, "learning_gateway", "self")
    assert guard.suspended
    assert guard.health()["anomalies_blocked"] == 1


def test_a_blocked_attempt_alerts_a_human_immediately_and_escalates(
    guard: RecursionGuard, alerts: list[str], escalations: list[tuple[EscalationTrigger, str]]
) -> None:
    """Both, not either. 13.21.3 requires the alert; 21B §21.9 makes it Category 1.

    An alert nobody escalated is not an incident record, and an escalation
    nobody saw is not an alert.
    """
    with pytest.raises(RecursionAnomaly):
        guard.check(TargetClass.LEARNING, "learning_gateway", "self", observer_id="agent-analyst")
    assert len(alerts) == 1
    assert "agent-analyst" in alerts[0]
    assert escalations[0][0] == EscalationTrigger.AUTHORITY_BYPASS


def test_the_finding_names_what_it_matched_on(guard: RecursionGuard) -> None:
    """A human reviewing a suspension needs to know which check fired."""
    assert guard.inspect(TargetClass.LEARNING, "agent_runtime", "a").matched_on == "target_class"
    assert guard.inspect(TargetClass.AGENT, "learning", "a").matched_on == "target_subsystem"
    assert guard.inspect(TargetClass.AGENT, "agent_runtime", "learning").matched_on == "subject_id"
    assert guard.inspect(TargetClass.AGENT, "a", "b", evidence_kinds=("learning_journal",)).matched_on == "evidence"
    assert guard.inspect(TargetClass.AGENT, "a", "b", proposal="tune the validation rule").matched_on == "proposal"
    assert guard.inspect(TargetClass.AGENT, "a", "b", triggered_by_event="learning.x").matched_on == "trigger"


def test_inspect_never_raises_so_detection_can_be_exercised_exhaustively(guard: RecursionGuard) -> None:
    """Detection and response are separate, so testing one does not trip the other."""
    for value in ("learning", "agent_runtime", "", "13", "🙂"):
        finding = guard.inspect(TargetClass.AGENT, value, value)
        assert isinstance(finding.blocked, bool)
    assert not guard.suspended, "inspection alone suspends nothing"


# ------------------------------------------------------ the normalizer itself


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Learning Gateway", "learninggateway"),
        ("learning_gateway", "learninggateway"),
        ("LEARNING-GATEWAY", "learninggateway"),
        ("  learning  ", "learning"),
        ("l.e.a.r.n.i.n.g", "learning"),
        ("agent_runtime", "agentruntime"),
    ],
)
def test_normalization_collapses_the_disguises(raw: str, expected: str) -> None:
    assert normalize(raw) == expected


def test_normalization_does_not_collapse_distinct_subsystems() -> None:
    """Over-aggressive normalization would block legitimate targets."""
    assert normalize("agent_runtime") != normalize("learning_gateway")
    assert normalize("knowledge_gateway") != normalize("learning_gateway")


def test_a_subsystem_whose_name_merely_contains_a_letter_run_is_not_blocked(
    guard: RecursionGuard,
) -> None:
    """Fail-closed must not mean fail-paranoid.

    `unlearning_monitor` is not the Learning Gateway. Matching on substring
    rather than on the whole normalized name would block it, and a guard that
    blocks legitimate targets gets disabled by whoever it inconveniences.
    """
    guard.check(TargetClass.AGENT, "unlearning_monitor", "agent-1")
    guard.check(TargetClass.AGENT, "elearning_platform", "agent-1")
    assert not guard.suspended
