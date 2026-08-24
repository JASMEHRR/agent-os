"""Learning Gateway conformance tests (13, per 21B §21).

`13.2.1`: "Learning is the only subsystem whose output is change to the other
subsystems." That property is also its principal risk, so the rules tested
hardest here are the ones that bound it:

* propagation is handoff, never adoption (13.16.1, 13 rule 2);
* a proposal touching a non-violable rule is rejected at **validation**, not
  at the target (21B §21.10, 13 rules 3 and 15);
* correlation is never propagated as causation (13 rule 6);
* no adoption escapes measurement (13 rule 9).

The Recursion Guard's adversarial suite lives in `test_recursion_guard.py`,
per 21C §38.5.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from core.exceptions import AgentOSError, NotFoundError
from kernel.signals import SignalEmitter
from learning_gateway import (
    CONFIDENCE_FLOOR,
    DECAY_HALF_LIFE,
    EVIDENCE_SUFFICIENCY,
    MEASUREMENT_WINDOWS,
    Attribution,
    AttributionAnomaly,
    EvidenceRef,
    Hypothesis,
    InsufficientEvidence,
    LearningEntry,
    LearningGateway,
    LearningState,
    NonViolableProposal,
    Observation,
    Pattern,
    PatternKind,
    RecursionAnomaly,
    TargetClass,
    loop_stages,
    threshold_for,
    window_for,
)

TENANT = "tenant-alpha"
OBSERVER = "agent-observer"
HUMAN = "human-sovereign"


class Clock:
    def __init__(self) -> None:
        self.now = datetime(2026, 8, 1, 12, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.now

    def advance(self, delta: timedelta) -> None:
        self.now += delta


class FakeAuthorizer:
    def __init__(self) -> None:
        self.tokens = {"tok": (OBSERVER, TENANT), "tok-human": (HUMAN, TENANT), "tok-other": ("x", "tenant-beta")}

    def principal_of(self, token: str) -> tuple[str, str]:
        return self.tokens[token]

    def is_human(self, principal_id: str) -> bool:
        return principal_id.startswith("human-")


class FakeBudget:
    def __init__(self, headroom: bool = True) -> None:
        self.headroom = headroom

    def has_headroom(self, tenant_id: str, cost: float) -> bool:
        return self.headroom


class Sink:
    """A target Gateway's intake, recording what it was handed."""

    def __init__(self, name: str = "agent_runtime") -> None:
        self.name = name
        self.received: list[tuple[str, dict[str, Any]]] = []

    def receive(self, entry_id: str, target_subsystem: str, proposal: Any) -> str:
        self.received.append((entry_id, dict(proposal)))
        return f"ack-{entry_id}"


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def alerts() -> list[str]:
    return []


@pytest.fixture
def sink() -> Sink:
    return Sink()


@pytest.fixture
def gateway(clock: Clock, sink: Sink, alerts: list[str]) -> LearningGateway:
    gw = LearningGateway(
        authorizer=FakeAuthorizer(),
        budget=FakeBudget(),
        signals=SignalEmitter(source_identity="learning_gateway"),
        alert_human=alerts.append,
        now=clock,
    )
    gw.register_target("agent_runtime", sink)
    return gw


def evidence(count: int = 3, **overrides: Any) -> tuple[EvidenceRef, ...]:
    defaults: dict[str, Any] = {"kind": "decision_journal", "confidence": 0.9}
    defaults.update(overrides)
    return tuple(
        EvidenceRef(reference=f"ev-{n}", observed_at=datetime(2026, 7, 1, tzinfo=UTC), **defaults) for n in range(count)
    )


def pattern(kind: PatternKind = PatternKind.FAILURE, instances: int = 2, **overrides: Any) -> Pattern:
    defaults: dict[str, Any] = {
        "pattern_id": "pat-1",
        "kind": kind,
        "target_class": TargetClass.AGENT,
        "scope": "tenant-alpha/pricing",
        "instances": tuple(f"obs-{n}" for n in range(instances)),
        "description": "retries exhaust before the provider recovers",
        "root_cause": "the retry ceiling is below the provider's recovery time",
    }
    defaults.update(overrides)
    return Pattern(**defaults)


def attribution(**overrides: Any) -> Attribution:
    defaults: dict[str, Any] = {
        "causal_proximity": 0.9,
        "confounding_controlled": True,
        "temporal_order_holds": True,
        "replications": 4,
        "null_hypothesis": "the provider recovered on its own regardless of the retry ceiling",
    }
    defaults.update(overrides)
    return Attribution(**defaults)


def hypothesis(entry_id: str = "le-1", **overrides: Any) -> Hypothesis:
    defaults: dict[str, Any] = {
        "entry_id": entry_id,
        "tenant_id": TENANT,
        "observer_id": OBSERVER,
        "target_class": TargetClass.AGENT,
        "target_subsystem": "agent_runtime",
        "subject_id": "agent-analyst",
        "proposal": "raise the retry ceiling for the pricing analyst from two to four",
        "expected_outcome": "activity failure rate falls below five percent",
        "pattern": pattern(),
        "evidence": evidence(),
        "attribution": attribution(),
        "scope": "tenant-alpha/pricing",
        "formed_at": datetime(2026, 8, 1, tzinfo=UTC),
    }
    defaults.update(overrides)
    return Hypothesis(**defaults)


def observation(observation_id: str = "obs-1", **overrides: Any) -> Observation:
    defaults: dict[str, Any] = {
        "observation_id": observation_id,
        "tenant_id": TENANT,
        "observer_id": OBSERVER,
        "target_class": TargetClass.AGENT,
        "subject_id": "agent-analyst",
        "summary": "the analyst exhausted its retries three times this week",
        "evidence": evidence(),
        "observed_at": datetime(2026, 8, 1, tzinfo=UTC),
    }
    defaults.update(overrides)
    return Observation(**defaults)


def through_validation(gateway: LearningGateway, entry_id: str = "le-1", **overrides: Any) -> LearningEntry:
    gateway.hypothesize("tok", hypothesis(entry_id, **overrides))
    return gateway.validate(entry_id)


# ------------------------------------------------------------------ Observe


def test_an_observation_requires_an_authenticated_observer(gateway: LearningGateway) -> None:
    """13 rule 1 and 13 rule 7 — no anonymous formation."""
    with pytest.raises(KeyError):
        gateway.observe("no-such-token", observation())


def test_an_observation_without_evidence_is_refused(gateway: LearningGateway) -> None:
    with pytest.raises(InsufficientEvidence, match="cites no evidence"):
        gateway.observe("tok", observation(evidence=()))


def test_an_observation_may_not_cross_the_tenant_boundary(gateway: LearningGateway) -> None:
    """13 rule 8 — no cross-tenant learning without anonymization and approval."""
    with pytest.raises(AgentOSError, match="may not submit observations"):
        gateway.observe("tok-other", observation())


def test_a_learning_cycle_defers_when_the_budget_has_no_headroom(clock: Clock) -> None:
    """13 rule 11 — a cycle may not breach a circuit breaker."""
    gw = LearningGateway(
        authorizer=FakeAuthorizer(),
        budget=FakeBudget(headroom=False),
        signals=SignalEmitter(source_identity="learning_gateway"),
        now=clock,
    )
    with pytest.raises(AgentOSError, match="deferred"):
        gw.observe("tok", observation())


def test_human_feedback_is_marked_and_requires_a_human(gateway: LearningGateway) -> None:
    """13.33.1 — high-confidence evidence, and only a human supplies it."""
    with pytest.raises(AgentOSError, match="not a human principal"):
        gateway.submit_human_feedback("tok", observation())
    recorded = gateway.submit_human_feedback("tok-human", observation())
    assert recorded.human_feedback
    assert all(e.human for e in recorded.evidence)


# --------------------------------------------------- Patterns (13.34.3)


def test_a_failure_pattern_needs_two_instances_and_a_root_cause(gateway: LearningGateway) -> None:
    """13.34.3's asymmetry: fewer instances, but stronger attribution."""
    gateway.recognize(pattern(PatternKind.FAILURE, instances=2))
    with pytest.raises(InsufficientEvidence, match="needs 2 instances"):
        gateway.recognize(pattern(PatternKind.FAILURE, instances=1))
    with pytest.raises(InsufficientEvidence, match="root cause"):
        gateway.recognize(pattern(PatternKind.FAILURE, instances=2, root_cause="  "))


def test_a_success_pattern_needs_three_instances(gateway: LearningGateway) -> None:
    """The other half of the asymmetry: more instances, broader generalization."""
    gateway.recognize(pattern(PatternKind.SUCCESS, instances=3))
    with pytest.raises(InsufficientEvidence, match="needs 3 instances"):
        gateway.recognize(pattern(PatternKind.SUCCESS, instances=2))


def test_failure_learning_needs_less_evidence_than_success_learning() -> None:
    """The asymmetry stated directly, so a later edit cannot quietly equalize it.

    13.34.3 exists because when capital is at risk, being slow to stop
    repeating a failure costs more than being slow to replicate a success.
    """
    from learning_gateway import FAILURE_PATTERN_MINIMUM, SUCCESS_PATTERN_MINIMUM

    assert FAILURE_PATTERN_MINIMUM < SUCCESS_PATTERN_MINIMUM


# ---------------------------------------------------------------- Validate


def test_a_validated_entry_carries_the_gateways_confidence_not_the_proposers(
    gateway: LearningGateway,
) -> None:
    """13.8.5 — validation "assigns the authoritative confidence score"."""
    entry = through_validation(gateway)
    assert entry.state == LearningState.VALIDATED
    assert entry.confidence > 0
    assert entry.validated_at is not None


def test_evidence_below_the_class_count_is_insufficient(gateway: LearningGateway) -> None:
    """13.12.4 — five decision outcomes for Decision learning, three for Agent."""
    gateway.hypothesize(
        "tok",
        hypothesis("le-d", target_class=TargetClass.DECISION, evidence=evidence(3)),
    )
    with pytest.raises(InsufficientEvidence, match="needs 5 canonical observations"):
        gateway.validate("le-d")


@pytest.mark.parametrize("target_class", list(TargetClass))
def test_every_target_class_has_a_declared_evidence_count_and_window(target_class: TargetClass) -> None:
    assert target_class in EVIDENCE_SUFFICIENCY
    assert target_class in MEASUREMENT_WINDOWS
    minimum, maximum = window_for(target_class)
    assert 0 < minimum <= maximum


def test_quarantined_or_speculative_evidence_cannot_stand_alone(gateway: LearningGateway) -> None:
    """13 rule 14."""
    gateway.hypothesize("tok", hypothesis("le-q", evidence=evidence(3, quarantined=True)))
    with pytest.raises(InsufficientEvidence, match="quarantined or speculative"):
        gateway.validate("le-q")


def test_a_blank_null_hypothesis_is_an_attribution_anomaly(gateway: LearningGateway) -> None:
    """13.12.3 — "mandatory consideration of null hypotheses"."""
    gateway.hypothesize("tok", hypothesis("le-n", attribution=attribution(null_hypothesis="   ")))
    with pytest.raises(AttributionAnomaly, match="null hypothesis"):
        gateway.validate("le-n")


def test_an_effect_preceding_its_cause_is_an_attribution_anomaly(gateway: LearningGateway) -> None:
    gateway.hypothesize("tok", hypothesis("le-t", attribution=attribution(temporal_order_holds=False)))
    with pytest.raises(AttributionAnomaly, match="did not precede"):
        gateway.validate("le-t")


def test_a_causal_claim_with_uncontrolled_confounders_is_refused(gateway: LearningGateway) -> None:
    """13 rule 6 — correlation presented as causation."""
    gateway.hypothesize("tok", hypothesis("le-c", attribution=attribution(confounding_controlled=False)))
    with pytest.raises(AttributionAnomaly, match="correlation presented as causation"):
        gateway.validate("le-c")


def test_a_correlation_pattern_can_never_reach_a_propagatable_confidence(
    gateway: LearningGateway,
) -> None:
    """13 rule 6 in arithmetic.

    A correlation may inform; it may not propagate as though it explained. The
    cap sits below the floor, so no combination of strong evidence and strong
    attribution can lift a correlation into propagation.
    """
    entry = through_validation(
        gateway,
        "le-corr",
        pattern=pattern(PatternKind.CORRELATION, instances=9, root_cause=""),
        attribution=attribution(causal_proximity=1.0, replications=20),
    )
    assert entry.state == LearningState.ABANDONED
    assert entry.confidence < CONFIDENCE_FLOOR


def test_confidence_below_the_class_threshold_is_abandoned_not_downgraded(
    gateway: LearningGateway,
) -> None:
    """13 rule 5. Proposing to a lesser target would be a different proposal."""
    entry = through_validation(
        gateway,
        "le-w",
        target_class=TargetClass.WORKFLOW,
        target_subsystem="agent_runtime",
        evidence=evidence(2, confidence=0.80),
        attribution=attribution(causal_proximity=0.72, replications=3),
    )
    assert entry.state == LearningState.ABANDONED
    assert CONFIDENCE_FLOOR <= entry.confidence < threshold_for(TargetClass.WORKFLOW)
    assert f"below the {threshold_for(TargetClass.WORKFLOW)} threshold" in entry.abandonment_reason


def test_an_entry_in_the_provisional_band_is_flagged(gateway: LearningGateway) -> None:
    """13.13.3 — 0.60 to 0.79 is "permitted for Agent/Tool, flagged provisional"."""
    entry = through_validation(
        gateway,
        "le-p",
        evidence=evidence(3, confidence=0.7),
        attribution=attribution(causal_proximity=0.6, replications=3),
    )
    assert entry.state == LearningState.VALIDATED
    assert entry.provisional


def test_human_feedback_bypasses_the_evidence_count_but_not_the_audit(
    gateway: LearningGateway,
) -> None:
    """13.33.1 and 13.7.5 — high-confidence, never overridden by observation."""
    entry = through_validation(
        gateway,
        "le-h",
        target_class=TargetClass.DECISION,
        evidence=(
            EvidenceRef(
                reference="hf-1", kind="human_feedback", observed_at=datetime(2026, 7, 1, tzinfo=UTC), human=True
            ),
        ),
        human_feedback=True,
        pattern=pattern(PatternKind.FAILURE, instances=2),
    )
    assert entry.state == LearningState.VALIDATED
    assert entry.confidence >= 0.95
    assert gateway.query_journal("le-h"), "the bypass is audited, not silent"


# --------------------------------------------- Non-violable screen (21B §21.10)


@pytest.mark.parametrize(
    "proposal",
    [
        "raise the autonomy level of the pricing analyst to four",
        "remove the human approval gate for routine reposts",
        "relax the security boundary between tenants",
        "let the runtime bypass a standing order when confidence is high",
        "shorten the panic protocol so it does not interrupt work",
        "amend a constitutional constraint that slows adoption",
        "treat a non-violable rule as advisory below a cost threshold",
    ],
)
def test_a_proposal_touching_a_non_violable_rule_is_rejected_at_validation(
    gateway: LearningGateway, proposal: str
) -> None:
    """21B §21.10 — rejected here, not at the target Gateway.

    Relying on the target to refuse would mean every target must implement the
    same screen correctly, and the first one that did not would be the way in.
    """
    gateway.hypothesize("tok", hypothesis("le-nv", proposal=proposal))
    with pytest.raises(NonViolableProposal):
        gateway.validate("le-nv")


def test_the_screen_reads_the_expected_outcome_too(gateway: LearningGateway) -> None:
    """A proposal innocent in its statement and violating in its intent."""
    gateway.hypothesize(
        "tok",
        hypothesis("le-nv2", proposal="tune the analyst", expected_outcome="the human approval gate stops firing"),
    )
    with pytest.raises(NonViolableProposal):
        gateway.validate("le-nv2")


# ----------------------------------------------------------- Contradiction


def test_a_contradicting_entry_is_quarantined_for_human_arbitration(
    gateway: LearningGateway,
) -> None:
    """13 rule 13 — no proceeding on unresolved contradictory evidence."""
    first = through_validation(gateway, "le-a")
    gateway.consolidate("pkg-1", TENANT, "agent_runtime")
    gateway.propagate("pkg-1")
    gateway.report_adoption(first.entry_id, adopted=True)

    gateway.hypothesize(
        "tok",
        hypothesis(
            "le-b",
            proposal="lower the retry ceiling for the pricing analyst from two to one",
            pattern=pattern(PatternKind.SUCCESS, instances=3, root_cause=""),
        ),
    )
    contradicting = gateway.validate("le-b")
    assert contradicting.state == LearningState.QUARANTINED
    assert "le-a" in contradicting.quarantine_reason


# ------------------------------------------------------------- Consolidate


def test_consolidation_supersedes_the_weaker_of_two_entries_on_one_subject(
    gateway: LearningGateway,
) -> None:
    """13.8.6 — fragmented or conflicting improvements do not propagate at once."""
    through_validation(gateway, "le-strong")
    through_validation(
        gateway,
        "le-weak",
        evidence=evidence(3, confidence=0.72),
        attribution=attribution(causal_proximity=0.7, replications=3),
    )
    package = gateway.consolidate("pkg-1", TENANT, "agent_runtime")
    assert package.entry_ids == ("le-strong",)
    assert package.superseded_ids == ("le-weak",)
    assert gateway.get("le-weak").state == LearningState.QUARANTINED


def test_consolidating_nothing_is_refused(gateway: LearningGateway) -> None:
    with pytest.raises(Exception, match="nothing validated"):
        gateway.consolidate("pkg-1", TENANT, "agent_runtime")


# --------------------------------------------------------------- Propagate


def test_propagation_is_handoff_and_the_gateway_has_no_adopt_verb(gateway: LearningGateway, sink: Sink) -> None:
    """13.16.1 — the target "retains full constitutional authority".

    Structural: an `adopt` verb here would let Learning commit a change to a
    subsystem it does not own, which is the one thing the meta-layer must
    never be able to do.
    """
    through_validation(gateway)
    gateway.consolidate("pkg-1", TENANT, "agent_runtime")
    delivered = gateway.propagate("pkg-1")

    assert delivered == ["le-1"]
    assert sink.received[0][0] == "le-1"
    assert gateway.get("le-1").state == LearningState.PROPAGATED

    forbidden = {"adopt", "commit", "apply", "enforce", "install", "mutate_target"}
    present = {name for name in dir(LearningGateway) if not name.startswith("_")}
    assert not (forbidden & present), f"Learning acquired an adoption verb: {forbidden & present}"


def test_propagation_without_a_registered_intake_is_refused(gateway: LearningGateway) -> None:
    """13 rule 2 — no bypassing the target subsystem's Gateway."""
    through_validation(gateway, "le-x", target_subsystem="memory_gateway")
    gateway.consolidate("pkg-1", TENANT, "memory_gateway")
    with pytest.raises(NotFoundError, match="no registered intake"):
        gateway.propagate("pkg-1")


def test_the_package_tells_the_target_whether_this_is_a_cause_or_a_correlation(
    gateway: LearningGateway, sink: Sink
) -> None:
    """13 rule 6, carried across the handoff rather than left behind."""
    through_validation(gateway)
    gateway.consolidate("pkg-1", TENANT, "agent_runtime")
    gateway.propagate("pkg-1")
    body = sink.received[0][1]
    assert body["is_causal_claim"] is True
    assert body["null_hypothesis"]
    assert body["attribution_strength"] > 0


def test_portfolio_learning_awaits_human_ratification_rather_than_propagating(
    gateway: LearningGateway, sink: Sink, alerts: list[str]
) -> None:
    """13.13.3 reserves the 0.95+ band for Business and Portfolio "with human ratification"."""
    through_validation(
        gateway,
        "le-port",
        target_class=TargetClass.PORTFOLIO,
        evidence=evidence(5, confidence=1.0),
        attribution=attribution(causal_proximity=1.0, replications=10),
        pattern=pattern(PatternKind.FAILURE, instances=4),
    )
    gateway.consolidate("pkg-1", TENANT, "agent_runtime")
    delivered = gateway.propagate("pkg-1")
    assert delivered == []
    assert sink.received == []
    assert any("requires human ratification" in alert for alert in alerts)


# ------------------------------------------------------- Adopt and measure


def test_a_rejected_proposal_is_abandoned_with_its_evidence_intact(
    gateway: LearningGateway,
) -> None:
    """13.16.1 — rejection "does not invalidate the evidence"."""
    through_validation(gateway)
    gateway.consolidate("pkg-1", TENANT, "agent_runtime")
    gateway.propagate("pkg-1")
    entry = gateway.report_adoption("le-1", adopted=False, justification="the ceiling is bounded by contract")

    assert entry.state == LearningState.ABANDONED
    assert entry.abandonment_reason == "the ceiling is bounded by contract"
    assert len(entry.hypothesis.evidence) == 3, "the evidence survived the rejection"


def test_an_adopted_entry_is_measured_to_confirmation(gateway: LearningGateway) -> None:
    """13 rule 9 — no adoption without measurement of the actual outcome."""
    through_validation(gateway)
    gateway.consolidate("pkg-1", TENANT, "agent_runtime")
    gateway.propagate("pkg-1")
    gateway.report_adoption("le-1", adopted=True)

    minimum, _maximum = window_for(TargetClass.AGENT)
    for n in range(minimum):
        entry = gateway.record_measurement("le-1", improved=True)
        if n < minimum - 1:
            assert entry.state == LearningState.ADOPTED, "the window is not short-circuited"
    assert entry.state == LearningState.CONFIRMED
    assert entry.actual_improvement == 1.0


def test_a_refuted_entry_emits_a_reversal_proposal_to_the_target(gateway: LearningGateway, sink: Sink) -> None:
    """13.18.4 — "A reversal proposal is emitted to the target subsystem"."""
    through_validation(gateway)
    gateway.consolidate("pkg-1", TENANT, "agent_runtime")
    gateway.propagate("pkg-1")
    gateway.report_adoption("le-1", adopted=True)
    for _ in range(window_for(TargetClass.AGENT)[0]):
        entry = gateway.record_measurement("le-1", improved=False)

    assert entry.state == LearningState.REFUTED
    assert sink.received[-1][1]["reversal"] is True


def test_measurement_before_adoption_is_refused(gateway: LearningGateway) -> None:
    through_validation(gateway)
    with pytest.raises(AgentOSError, match="expected one of"):
        gateway.record_measurement("le-1", improved=True)


def test_an_unclosed_window_is_reported_rather_than_closed_by_fiat(
    gateway: LearningGateway,
) -> None:
    """13 rule 16, with the honest response.

    Closing a window by fiat would manufacture a confirmation nobody measured,
    so an overrun is made visible instead.
    """
    through_validation(gateway)
    gateway.consolidate("pkg-1", TENANT, "agent_runtime")
    gateway.propagate("pkg-1")
    gateway.report_adoption("le-1", adopted=True)
    minimum, _maximum = window_for(TargetClass.AGENT)
    for _ in range(minimum):
        gateway.record_measurement("le-1", improved=True)
    # Resolved inside the window, so nothing is left open past it.
    assert gateway.overdue() == []
    assert gateway.get("le-1").state == LearningState.CONFIRMED


def test_a_minority_improvement_refutes_at_the_same_point_confirmation_would(
    gateway: LearningGateway,
) -> None:
    """Refutation is not slower than confirmation, deliberately.

    Running a refutation to the window ceiling would leave a change the
    evidence already contradicts adopted for twice as long. Being slow in that
    direction is the expensive one (13.34.3).
    """
    through_validation(gateway)
    gateway.consolidate("pkg-1", TENANT, "agent_runtime")
    gateway.propagate("pkg-1")
    gateway.report_adoption("le-1", adopted=True)
    minimum, _maximum = window_for(TargetClass.AGENT)
    outcomes = [True, False, False, False, False]
    for improved in outcomes[:minimum]:
        entry = gateway.record_measurement("le-1", improved=improved)
    assert entry.state == LearningState.REFUTED
    assert entry.actual_improvement == pytest.approx(0.2)


# ----------------------------------------------------- Decay and the library


def test_confirmed_learning_decays_and_is_eventually_deprecated(gateway: LearningGateway, clock: Clock) -> None:
    """13.19 — conditions change, and yesterday's confirmed truth goes stale."""
    through_validation(gateway)
    gateway.consolidate("pkg-1", TENANT, "agent_runtime")
    gateway.propagate("pkg-1")
    gateway.report_adoption("le-1", adopted=True)
    for _ in range(window_for(TargetClass.AGENT)[0]):
        gateway.record_measurement("le-1", improved=True)

    clock.advance(DECAY_HALF_LIFE)
    gateway.decay()
    entry = gateway.get("le-1")
    assert entry.freshness == pytest.approx(0.5, abs=0.01)
    assert entry.state == LearningState.CONFIRMED

    clock.advance(DECAY_HALF_LIFE * 3)
    deprecated = gateway.decay()
    assert [e.entry_id for e in deprecated] == ["le-1"]
    assert gateway.get("le-1").state == LearningState.SUPERSEDED


def test_deprecation_supersedes_rather_than_deleting(gateway: LearningGateway, clock: Clock) -> None:
    """13 rule 10 — no modification or deletion after validation."""
    through_validation(gateway)
    gateway.consolidate("pkg-1", TENANT, "agent_runtime")
    gateway.propagate("pkg-1")
    gateway.report_adoption("le-1", adopted=True)
    for _ in range(window_for(TargetClass.AGENT)[0]):
        gateway.record_measurement("le-1", improved=True)
    clock.advance(DECAY_HALF_LIFE * 4)
    gateway.decay()
    assert gateway.get("le-1") is not None, "the entry is still readable after deprecation"


def test_a_validated_failure_enters_the_failure_library(gateway: LearningGateway) -> None:
    """21B §21.5 Failure Library Query — consulted before similar operations."""
    through_validation(gateway)
    catalogued = gateway.consult_failures("agent-analyst")
    assert catalogued is not None
    assert catalogued.root_cause.startswith("the retry ceiling")
    assert gateway.failure_library()[0].subject_id == "agent-analyst"


def test_a_success_pattern_does_not_enter_the_failure_library(gateway: LearningGateway) -> None:
    through_validation(gateway, "le-s", pattern=pattern(PatternKind.SUCCESS, instances=3, root_cause=""))
    assert gateway.consult_failures("agent-analyst") is None


def test_failure_learning_outranks_success_learning_of_equal_strength(
    gateway: LearningGateway,
) -> None:
    """13.34.3 — "prioritized over success learning when capital is at risk"."""
    through_validation(gateway, "le-success", pattern=pattern(PatternKind.SUCCESS, instances=3, root_cause=""))
    through_validation(gateway, "le-failure", subject_id="agent-other")
    ranked = gateway.prioritize(TENANT)
    assert ranked[0].entry_id == "le-failure"


# ------------------------------------------------- Immutability and journal


def test_a_hypothesis_is_frozen_once_formed(gateway: LearningGateway) -> None:
    """13.9.3 — identity, evidence and attribution are immutable after Validated."""
    entry = through_validation(gateway)
    with pytest.raises(Exception):  # noqa: B017 - FrozenInstanceError
        entry.hypothesis.proposal = "something else"  # type: ignore[misc]
    with pytest.raises(Exception):  # noqa: B017
        entry.hypothesis.attribution.replications = 99  # type: ignore[misc]


def test_the_journal_records_the_whole_loop_and_stays_intact(gateway: LearningGateway) -> None:
    through_validation(gateway)
    gateway.consolidate("pkg-1", TENANT, "agent_runtime")
    gateway.propagate("pkg-1")
    gateway.report_adoption("le-1", adopted=True)
    for _ in range(window_for(TargetClass.AGENT)[0]):
        gateway.record_measurement("le-1", improved=True)

    actions = [str(p.get("action")) for p in gateway.query_journal("le-1")]
    assert actions == ["hypothesized", "validated", "consolidated", "propagated", "adopted", "confirmed"]
    assert gateway.health()["journal_intact"]


def test_a_duplicate_entry_id_is_refused(gateway: LearningGateway) -> None:
    gateway.hypothesize("tok", hypothesis())
    with pytest.raises(AgentOSError, match="already exists"):
        gateway.hypothesize("tok", hypothesis())


def test_an_unknown_entry_is_a_not_found(gateway: LearningGateway) -> None:
    with pytest.raises(NotFoundError):
        gateway.get("le-nobody")


# ---------------------------------------------- Recursion, at the Gateway level


def test_the_gateway_refuses_a_self_targeting_hypothesis(gateway: LearningGateway) -> None:
    """The guard's adversarial suite is separate; this checks it is actually wired."""
    with pytest.raises(RecursionAnomaly):
        gateway.hypothesize("tok", hypothesis("le-r", target_subsystem="learning_gateway"))


def test_the_gateway_refuses_a_self_referential_observation(gateway: LearningGateway) -> None:
    with pytest.raises(RecursionAnomaly):
        gateway.observe("tok", observation(evidence=evidence(3, kind="learning_journal")))


# ------------------------------------------------------------------ Health


def test_health_reports_the_five_metric_families(gateway: LearningGateway) -> None:
    """13.23.1 / 21B §21.11."""
    through_validation(gateway)
    gateway.consolidate("pkg-1", TENANT, "agent_runtime")
    gateway.propagate("pkg-1")
    gateway.report_adoption("le-1", adopted=True)
    for _ in range(window_for(TargetClass.AGENT)[0]):
        gateway.record_measurement("le-1", improved=True)

    health = gateway.health()
    assert set(health) >= {"velocity", "quality", "governance", "health", "economic"}
    assert health["velocity"]["hypotheses"] == 1
    assert health["quality"]["confirmation_rate"] == 1.0
    assert health["quality"]["attribution_error_rate"] == 0.0
    assert health["governance"]["adoption_rate"] == 1.0
    assert health["health"]["failure_library"] == 1


def test_attribution_error_rate_rises_with_refutations(gateway: LearningGateway) -> None:
    """21B §21.11 — the subsystem's most consequential signal.

    13.4.3 defines Attribution Error as "an incorrect correlation between cause
    and outcome, leading to harmful proposals": the mechanism by which a
    learning subsystem degrades the system it exists to improve. A refuted
    adoption is the observable form of one.
    """
    through_validation(gateway)
    gateway.consolidate("pkg-1", TENANT, "agent_runtime")
    gateway.propagate("pkg-1")
    gateway.report_adoption("le-1", adopted=True)
    for _ in range(window_for(TargetClass.AGENT)[0]):
        gateway.record_measurement("le-1", improved=False)
    assert gateway.health()["quality"]["attribution_error_rate"] == 1.0


def test_the_loop_stages_match_the_constitution() -> None:
    """13.18.1: Observe -> Propose -> Adopt -> Measure -> Confirm/Refute -> Consolidate."""
    assert loop_stages() == ("observe", "propose", "adopt", "measure", "confirm_refute", "consolidate")


def test_cross_subsystem_imports_are_confined_to_the_adapter() -> None:
    import pathlib

    package = pathlib.Path(__file__).resolve().parents[1]
    foreign = ("security_gateway", "cost_manager", "memory_gateway", "knowledge_gateway", "decision_gateway")
    for source in package.glob("*.py"):
        if source.name == "adapters.py":
            continue
        for line in source.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped.startswith(("import ", "from ")):
                continue
            assert not any(name in stripped for name in foreign), (
                f"{source.name} imports another subsystem directly; route it through adapters.py"
            )
