"""The full interpretive profile (Stage S10, 21B §24, doc 16).

`16.4`: **"observability reads the system; it does not steer it."**

Interpretation is where a read-only subsystem is most tempted to act, so the
tests here are weighted toward the ways that could happen: a correlation engine
that stores its own version of events, an SLO registry that enforces, an alert
router that remediates.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from core.exceptions import NotFoundError, ValidationError
from kernel.escalation import EscalationTrigger
from kernel.journal import ImmutableJournal
from observability_gateway import (
    SLO,
    Alert,
    AlertRouter,
    CorrelationEngine,
    ObservabilityGateway,
    QueryNotAuthorized,
    Severity,
    SLORegistry,
    compose_constitutional_health,
    default_slos,
)

TENANT = "tenant-alpha"


class Clock:
    def __init__(self) -> None:
        self.now = datetime(2026, 8, 1, 12, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        self.now += timedelta(milliseconds=1)
        return self.now


class FakeAuthorizer:
    def __init__(self, allow: bool = True) -> None:
        self.allow = allow
        self.asked: list[tuple[str, str]] = []

    def may_query(self, token: str, tenant_id: str, sensitivity: str) -> bool:
        self.asked.append((tenant_id, sensitivity))
        return self.allow


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def escalations() -> list[tuple[EscalationTrigger, str]]:
    return []


@pytest.fixture
def to_governance() -> list[Alert]:
    return []


@pytest.fixture
def gateway(
    clock: Clock, escalations: list[tuple[EscalationTrigger, str]], to_governance: list[Alert]
) -> ObservabilityGateway:
    return ObservabilityGateway(
        authorizer=FakeAuthorizer(),
        now=clock,
        escalate=lambda trigger, detail: escalations.append((trigger, detail)),
        notify_governance=to_governance.append,
    )


# ------------------------------------------------------- Correlation Engine


def test_a_timeline_joins_journals_across_subsystem_boundaries(gateway: ObservabilityGateway) -> None:
    """16.9 — what turns per-subsystem records into a narrative a human can follow."""
    workflow = ImmutableJournal()
    workflow.append({"kind": "workflow", "action": "running", "workflow_id": "wf-1"})
    workflow.append({"kind": "workflow", "action": "completed", "workflow_id": "wf-1"})
    agent = ImmutableJournal()
    agent.append({"kind": "agent", "action": "executed", "workflow_id": "wf-1"})
    agent.append({"kind": "agent", "action": "executed", "workflow_id": "wf-other"})

    gateway.register_journal("workflow_engine", workflow)
    gateway.register_journal("agent_runtime", agent)

    timeline = gateway.correlate("tok", TENANT, "workflow_id", "wf-1")
    assert len(timeline.events) == 3
    assert set(timeline.subsystems) == {"workflow_engine", "agent_runtime"}
    assert timeline.correlation_key == "workflow_id=wf-1"


def test_timeline_events_are_ordered_by_time_not_by_subsystem(gateway: ObservabilityGateway) -> None:
    first = ImmutableJournal()
    second = ImmutableJournal()
    first.append({"action": "started", "trace": "t-1"})
    second.append({"action": "middle", "trace": "t-1"})
    first.append({"action": "finished", "trace": "t-1"})
    gateway.register_journal("a", first)
    gateway.register_journal("b", second)

    timeline = gateway.correlate("tok", TENANT, "trace", "t-1")
    assert [e.action for e in timeline.events] == ["started", "middle", "finished"]


def test_the_correlation_engine_stores_no_timeline(clock: Clock) -> None:
    """21B §24.4 — reconstructed on query, never held as mutable state.

    Structural: a stored timeline is a second version of what happened, which
    can be edited and will eventually disagree with the journal that is the
    actual record.
    """
    engine = CorrelationEngine(now=clock)
    forbidden = {"store", "save", "update_timeline", "amend", "persist", "delete"}
    present = {name for name in dir(CorrelationEngine) if not name.startswith("_")}
    assert not (forbidden & present)

    journal = ImmutableJournal()
    journal.append({"action": "a", "key": "k"})
    engine.register_journal("x", journal)
    first = engine.correlate("key", "k")
    journal.append({"action": "b", "key": "k"})
    second = engine.correlate("key", "k")
    assert len(first.events) == 1 and len(second.events) == 2, "each query re-reads the journal"


def test_correlating_an_unknown_key_returns_an_empty_timeline(gateway: ObservabilityGateway) -> None:
    assert gateway.correlate("tok", TENANT, "workflow_id", "wf-nobody").events == ()


def test_a_timeline_query_is_authorized_like_every_other_read(clock: Clock) -> None:
    """21B §24.10 — no privileged observability bypass of Security."""
    gw = ObservabilityGateway(authorizer=FakeAuthorizer(allow=False), now=clock)
    with pytest.raises(QueryNotAuthorized):
        gw.correlate("tok", TENANT, "workflow_id", "wf-1")


# ---------------------------------------------------------- SLI/SLO Registry


def test_the_registry_publishes_and_does_not_enforce() -> None:
    """21B §24.5 — "informational; not enforced by Observability".

    Structural: a registry that could block a subsystem for missing its target
    would be a control channel wearing a reporting label.
    """
    forbidden = {"enforce", "block", "throttle", "reject", "suspend", "penalize"}
    present = {name for name in dir(SLORegistry) if not name.startswith("_")}
    assert not (forbidden & present)


def test_default_slos_are_published_on_construction(gateway: ObservabilityGateway) -> None:
    assert gateway.slos.get("panic.completion").target == 5.0
    assert len(default_slos()) == len(gateway.health()["slos"]["attainment"])


def test_a_registry_change_is_governance_visible(clock: Clock) -> None:
    """16.14.3 — the registry cannot be edited quietly."""
    seen: list[tuple[str, str]] = []
    gw = ObservabilityGateway(
        authorizer=FakeAuthorizer(), now=clock, on_slo_change=lambda action, slo: seen.append((action, slo.name))
    )
    assert all(action == "published" for action, _ in seen)
    gw.publish_slo(
        SLO(
            name="panic.completion",
            subsystem="human_interface",
            indicator="panic_elapsed_seconds",
            target=4.0,
            unit="s",
            rationale="tightened after a drill",
            source="operator",
        )
    )
    assert ("updated", "panic.completion") in seen


def test_a_breach_raises_a_warning_alert_rather_than_intervening(
    gateway: ObservabilityGateway,
) -> None:
    reading = gateway.record_sli("panic.completion", observed=6.5)
    assert not reading.meets_target
    assert reading.ratio == 1.3
    alerts = gateway.alerts.alerts(Severity.WARNING)
    assert len(alerts) == 1
    assert alerts[0].routed_to == "dashboard"


def test_a_met_target_raises_nothing(gateway: ObservabilityGateway) -> None:
    assert gateway.record_sli("panic.completion", observed=1.2).meets_target
    assert gateway.alerts.alerts() == []


def test_attainment_is_the_fraction_of_readings_that_met_the_target(
    gateway: ObservabilityGateway,
) -> None:
    for observed in (1.0, 2.0, 9.0, 1.0):
        gateway.record_sli("panic.completion", observed)
    assert gateway.slos.attainment("panic.completion") == 0.75


def test_an_unpublished_slo_is_a_not_found(gateway: ObservabilityGateway) -> None:
    with pytest.raises(NotFoundError):
        gateway.record_sli("nothing.published", 1.0)


def test_slos_are_retrievable_by_subsystem(gateway: ObservabilityGateway) -> None:
    assert [s.name for s in gateway.slos.for_subsystem("human_interface")] == ["panic.completion"]


# ------------------------------------------------------- Alerting (16.16/17)


def test_severity_decides_the_route(
    gateway: ObservabilityGateway, escalations: list[tuple[EscalationTrigger, str]], to_governance: list[Alert]
) -> None:
    """16.16 and 16.17 — Category 1 to the incident pipeline, critical to Governance."""
    gateway.raise_alert("a-1", TENANT, Severity.CATEGORY_1, "security_gateway", "journal chain broken")
    gateway.raise_alert("a-2", TENANT, Severity.CRITICAL, "cost_manager", "budget breach")
    gateway.raise_alert("a-3", TENANT, Severity.WARNING, "llm_router", "latency rising")

    assert escalations and escalations[0][0] == EscalationTrigger.OVERSIGHT_LOSS
    assert [a.alert_id for a in to_governance] == ["a-2"]
    assert gateway.alerts.alerts(Severity.WARNING)[0].routed_to == "dashboard"


def test_the_router_remediates_nothing() -> None:
    """16.4 — the Gateway has no return path into a subsystem."""
    forbidden = {"remediate", "restart", "halt", "suspend", "reconfigure", "rollback"}
    present = {name for name in dir(AlertRouter) if not name.startswith("_")}
    assert not (forbidden & present)


def test_the_alert_summary_counts_by_severity_and_route(gateway: ObservabilityGateway) -> None:
    gateway.raise_alert("a-1", TENANT, Severity.CATEGORY_1, "x", "s")
    gateway.raise_alert("a-2", TENANT, Severity.CRITICAL, "y", "s")
    summary = gateway.alerts.summary()
    assert summary["alerts"] == 2
    assert summary["escalated"] == 1
    assert summary["to_governance"] == 1


# ------------------------------------- Constitutional health (16.26)


def test_constitutional_health_composes_four_dimensions(gateway: ObservabilityGateway) -> None:
    gateway.journal.append({"kind": "telemetry", "action": "ingested"})
    health = gateway.constitutional_health(
        tenant_id=TENANT,
        approvals_required=10,
        approvals_obtained=9,
        subsystems_reporting=12,
        subsystems_total=14,
        escalations_raised=4,
        escalations_acknowledged=4,
    )
    assert health.human_approval_coverage == 0.9
    assert health.audit_trail_completeness == 1.0
    assert health.oversight_visibility == pytest.approx(0.8571, abs=0.001)
    assert health.escalation_responsiveness == 1.0
    assert 0.0 < health.composite < 1.0


def test_the_health_report_says_it_is_not_a_compliance_ruling(gateway: ObservabilityGateway) -> None:
    """15.6.1 — only Governance declares compliance.

    Stated in the report rather than left for a consumer to infer, because the
    inference a busy consumer makes is that a number labelled "constitutional
    health" is a verdict.
    """
    gateway.journal.append({"kind": "telemetry", "action": "ingested"})
    report = gateway.constitutional_health(TENANT, 1, 1, 1, 1, 0, 0).to_report()
    assert report["is_a_compliance_ruling"] is False
    assert "only Governance declares compliance" in report["note"]


def test_a_broken_journal_scores_zero_audit_completeness() -> None:
    """A tampered journal is not a partially complete audit trail."""
    health = compose_constitutional_health(
        tenant_id=TENANT,
        at=datetime(2026, 8, 1, tzinfo=UTC),
        approvals_required=1,
        approvals_obtained=1,
        journal_entries=1000,
        journal_intact=False,
        subsystems_reporting=1,
        subsystems_total=1,
        escalations_raised=0,
        escalations_acknowledged=0,
    )
    assert health.audit_trail_completeness == 0.0


def test_an_empty_journal_also_scores_zero() -> None:
    """No trail is not a clean trail."""
    health = compose_constitutional_health(
        tenant_id=TENANT,
        at=datetime(2026, 8, 1, tzinfo=UTC),
        approvals_required=0,
        approvals_obtained=0,
        journal_entries=0,
        journal_intact=True,
        subsystems_reporting=1,
        subsystems_total=1,
        escalations_raised=0,
        escalations_acknowledged=0,
    )
    assert health.audit_trail_completeness == 0.0


def test_a_silent_subsystem_lowers_visibility_rather_than_being_omitted() -> None:
    """Absence of evidence reads as a gap, not as health.

    A subsystem that stopped reporting is the case observability most needs to
    surface, and averaging only over those that did report would hide it.
    """
    health = compose_constitutional_health(
        tenant_id=TENANT,
        at=datetime(2026, 8, 1, tzinfo=UTC),
        approvals_required=1,
        approvals_obtained=1,
        journal_entries=1,
        journal_intact=True,
        subsystems_reporting=7,
        subsystems_total=14,
        escalations_raised=1,
        escalations_acknowledged=1,
    )
    assert health.oversight_visibility == 0.5


def test_nothing_required_means_nothing_missing() -> None:
    health = compose_constitutional_health(
        tenant_id=TENANT,
        at=datetime(2026, 8, 1, tzinfo=UTC),
        approvals_required=0,
        approvals_obtained=0,
        journal_entries=1,
        journal_intact=True,
        subsystems_reporting=1,
        subsystems_total=1,
        escalations_raised=0,
        escalations_acknowledged=0,
    )
    assert health.human_approval_coverage == 1.0
    assert health.composite == 1.0


def test_a_zero_subsystem_count_is_refused() -> None:
    with pytest.raises(ValidationError):
        compose_constitutional_health(
            tenant_id=TENANT,
            at=datetime(2026, 8, 1, tzinfo=UTC),
            approvals_required=0,
            approvals_obtained=0,
            journal_entries=1,
            journal_intact=True,
            subsystems_reporting=0,
            subsystems_total=0,
            escalations_raised=0,
            escalations_acknowledged=0,
        )


# ------------------------------------------------------------------ Profile


def test_health_reports_the_full_interpretive_profile(gateway: ObservabilityGateway) -> None:
    gateway.register_journal("workflow_engine", ImmutableJournal())
    health = gateway.health()
    assert health["profile"] == "full-interpretive"
    assert health["correlation"]["journals_registered"] == 1
    assert health["slos"]["published"] == len(default_slos())
    assert "alerting" in health


def test_the_gateway_still_exposes_no_mutating_verb() -> None:
    """16.4, re-asserted after the profile grew.

    The S3 suite asserted this when the surface was small. The interpretive
    profile is exactly when a read-only subsystem acquires a write path, so the
    check is repeated against the larger surface.
    """
    forbidden = {
        "configure",
        "set_",
        "update_subsystem",
        "steer",
        "halt",
        "suspend",
        "remediate",
        "enforce",
        "throttle",
        "restart",
    }
    present = {name for name in dir(ObservabilityGateway) if not name.startswith("_")}
    offending = {name for name in present if any(name.startswith(verb) for verb in forbidden)}
    assert not offending, f"Observability acquired a control path: {offending}"
