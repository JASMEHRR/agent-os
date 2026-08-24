"""The full interpretive profile (Stage S10, 21B §24, doc 16).

Stage S3 built the ingestion half. This is the half the build plan deferred:
the Correlation Engine, the SLI/SLO Registry, alerting and escalation routing,
and the constitutional health composition of 16.26.

The constraint that governs the whole module is unchanged from S3 and matters
more here, because interpretation is where a read-only subsystem is most
tempted to act. `16.4`: **"observability reads the system; it does not steer
it."** So:

**The Correlation Engine is stateless per query.** 21B §24.4 requires it to
reconstruct incident timelines "from the immutable Journal rather than
maintaining its own mutable incident state". A stored timeline would be a
second version of what happened, editable, and eventually disagreeing with the
journal that is the actual record.

**Alerting routes; it does not remediate.** A breach becomes a Category 1
escalation or a Governance notification. Neither is an action against the
subsystem that breached, because 16.4 forbids the return path.

**The SLI/SLO Registry publishes; it does not enforce.** 21B §24.5 marks SLI
publication "informational; not enforced by Observability". A registry that
could block a subsystem for missing its target would be a control channel
wearing a reporting label.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any

from core.exceptions import NotFoundError, ValidationError
from kernel.escalation import EscalationTrigger


class Severity(StrEnum):
    """16.16's alert severities, which decide the routing."""

    INFO = "info"
    WARNING = "warning"
    #: Routed to Governance as a compliance signal.
    CRITICAL = "critical"
    #: Routed to the Category 1 Incident pipeline (16.17).
    CATEGORY_1 = "category_1"


@dataclass(frozen=True)
class SLO:
    """One published target (16.14).

    Informational by construction: the registry hands this out and has no way
    to act on a subsystem that misses it.
    """

    name: str
    subsystem: str
    #: The measured quantity, e.g. "authorization_latency_p50".
    indicator: str
    target: float
    unit: str
    #: 16.14.3 — registry changes are Governance-visible, so the reason a
    #: target moved is recorded with the target.
    rationale: str
    source: str


@dataclass(frozen=True)
class SLIReading:
    """One measurement against a published target."""

    slo: SLO
    observed: float
    at: datetime

    @property
    def meets_target(self) -> bool:
        return self.observed <= self.slo.target

    @property
    def ratio(self) -> float:
        if self.slo.target <= 0:
            return 0.0
        return round(self.observed / self.slo.target, 4)


@dataclass
class SLORegistry:
    """The published performance targets every subsystem cites (16.14).

    21B §24.5: "informational; not enforced by Observability". There is
    deliberately no `enforce`, `block` or `throttle` verb here, and a test
    asserts none appears.
    """

    #: 16.14.3 — changes are Governance-visible. Called on every change so the
    #: registry cannot be edited quietly.
    on_change: Callable[[str, SLO], None] = field(default=lambda action, slo: None)

    def __post_init__(self) -> None:
        self._slos: dict[str, SLO] = {}
        self._readings: list[SLIReading] = []

    def publish(self, slo: SLO) -> SLO:
        action = "updated" if slo.name in self._slos else "published"
        self._slos[slo.name] = slo
        self.on_change(action, slo)
        return slo

    def get(self, name: str) -> SLO:
        slo = self._slos.get(name)
        if slo is None:
            raise NotFoundError(f"no SLO named '{name}' is published")
        return slo

    def record(self, name: str, observed: float, at: datetime) -> SLIReading:
        reading = SLIReading(slo=self.get(name), observed=observed, at=at)
        self._readings.append(reading)
        return reading

    def breaches(self) -> list[SLIReading]:
        return [r for r in self._readings if not r.meets_target]

    def for_subsystem(self, subsystem: str) -> list[SLO]:
        return [slo for slo in self._slos.values() if slo.subsystem == subsystem]

    def attainment(self, name: str) -> float:
        """The fraction of readings that met the target."""
        readings = [r for r in self._readings if r.slo.name == name]
        if not readings:
            return 0.0
        return round(sum(1 for r in readings if r.meets_target) / len(readings), 4)

    def summary(self) -> Mapping[str, Any]:
        return {
            "published": len(self._slos),
            "readings": len(self._readings),
            "breaches": len(self.breaches()),
            "attainment": {name: self.attainment(name) for name in self._slos},
        }


@dataclass(frozen=True)
class TimelineEvent:
    """One moment in a reconstructed incident timeline."""

    at: datetime
    subsystem: str
    action: str
    detail: Mapping[str, Any]


@dataclass(frozen=True)
class IncidentTimeline:
    """A correlated narrative, reconstructed on query and never stored (21B §24.4)."""

    correlation_key: str
    events: tuple[TimelineEvent, ...]
    reconstructed_at: datetime

    @property
    def subsystems(self) -> tuple[str, ...]:
        seen: list[str] = []
        for event in self.events:
            if event.subsystem not in seen:
                seen.append(event.subsystem)
        return tuple(seen)

    @property
    def span(self) -> timedelta:
        if len(self.events) < 2:
            return timedelta(0)
        return self.events[-1].at - self.events[0].at


@dataclass
class CorrelationEngine:
    """Joins telemetry across subsystem boundaries into incident timelines (16.9).

    **Stateless per query.** It holds registered journals and nothing else; the
    timeline is built when asked and discarded. 21B §24.4 requires this, and
    the reason is that a stored timeline is a second version of what happened,
    which can be edited and will eventually disagree with the journal that is
    the actual record.
    """

    now: Callable[[], datetime] = field(default=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        self._journals: dict[str, Any] = {}

    def register_journal(self, subsystem: str, journal: Any) -> None:
        """Read access for timeline reconstruction (21B §24.6)."""
        self._journals[subsystem] = journal

    def correlate(self, key: str, value: str) -> IncidentTimeline:
        """Reconstructs the timeline for one correlation key across subsystems.

        The key is any journal field — `workflow_id`, `request_id`,
        `entry_id`, `agent_id`. Cross-subsystem joining on a shared identifier
        is what turns a pile of per-subsystem records into a narrative a human
        can follow, which is the whole purpose 16.9 gives this component.
        """
        ordered: list[tuple[datetime, int, TimelineEvent]] = []
        for subsystem, journal in self._journals.items():
            for index in range(len(journal)):
                entry = journal[index]
                payload = entry.payload
                if str(payload.get(key, "")) != value:
                    continue
                ordered.append(
                    (
                        entry.recorded_at,
                        entry.seq,
                        TimelineEvent(
                            at=entry.recorded_at,
                            subsystem=subsystem,
                            action=str(payload.get("action", "")),
                            detail=dict(payload),
                        ),
                    )
                )
        # Sorted by timestamp, then by journal sequence. The tiebreak matters:
        # journal clocks have finite resolution, so two entries can share a
        # timestamp, and a forensic timeline that reordered itself between two
        # identical queries would be useless for exactly the incident it exists
        # to explain. Within one journal, sequence is authoritative; across
        # journals a tie is genuinely unordered and is broken deterministically
        # rather than arbitrarily.
        ordered.sort(key=lambda row: (row[0], row[1], row[2].subsystem))
        events = [row[2] for row in ordered]
        return IncidentTimeline(
            correlation_key=f"{key}={value}",
            events=tuple(events),
            reconstructed_at=self.now(),
        )

    def registered(self) -> tuple[str, ...]:
        return tuple(self._journals)


@dataclass(frozen=True)
class Alert:
    """One routed threshold breach (16.16, 16.17)."""

    alert_id: str
    tenant_id: str
    severity: Severity
    subsystem: str
    summary: str
    detail: Mapping[str, Any]
    raised_at: datetime
    routed_to: str


@dataclass
class AlertRouter:
    """Routes by severity. Remediates nothing (16.4).

    A Category 1 breach goes to the incident pipeline; a critical one goes to
    Governance as a compliance signal; the rest are recorded for the dashboard.
    None of the three is an action against the subsystem that breached, because
    16.4 gives this Gateway no return path into one.
    """

    escalate: Callable[[EscalationTrigger, str], None] = field(default=lambda trigger, detail: None)
    notify_governance: Callable[[Alert], None] = field(default=lambda alert: None)
    now: Callable[[], datetime] = field(default=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        self._alerts: list[Alert] = []

    def raise_alert(
        self,
        alert_id: str,
        tenant_id: str,
        severity: Severity,
        subsystem: str,
        summary: str,
        **detail: Any,
    ) -> Alert:
        routed = {
            Severity.CATEGORY_1: "category_1_pipeline",
            Severity.CRITICAL: "governance",
            Severity.WARNING: "dashboard",
            Severity.INFO: "dashboard",
        }[severity]
        alert = Alert(
            alert_id=alert_id,
            tenant_id=tenant_id,
            severity=severity,
            subsystem=subsystem,
            summary=summary,
            detail=dict(detail),
            raised_at=self.now(),
            routed_to=routed,
        )
        self._alerts.append(alert)
        if severity == Severity.CATEGORY_1:
            self.escalate(EscalationTrigger.OVERSIGHT_LOSS, f"{subsystem}: {summary}")
        elif severity == Severity.CRITICAL:
            self.notify_governance(alert)
        return alert

    def alerts(self, severity: Severity | None = None) -> list[Alert]:
        if severity is None:
            return list(self._alerts)
        return [a for a in self._alerts if a.severity == severity]

    def summary(self) -> Mapping[str, Any]:
        counts: dict[str, int] = {}
        for alert in self._alerts:
            counts[alert.severity.value] = counts.get(alert.severity.value, 0) + 1
        return {
            "alerts": len(self._alerts),
            "by_severity": counts,
            "escalated": len([a for a in self._alerts if a.severity == Severity.CATEGORY_1]),
            "to_governance": len([a for a in self._alerts if a.severity == Severity.CRITICAL]),
        }


@dataclass(frozen=True)
class ConstitutionalHealth:
    """16.26's constitutional health measurement.

    Deliberately a *report*, not a verdict. 15.6.1 makes Governance the only
    subsystem that may declare compliance, so this composition is evidence
    Governance consumes rather than a judgement Observability issues.
    """

    tenant_id: str
    computed_at: datetime
    human_approval_coverage: float
    audit_trail_completeness: float
    oversight_visibility: float
    escalation_responsiveness: float

    @property
    def composite(self) -> float:
        return round(
            (
                self.human_approval_coverage
                + self.audit_trail_completeness
                + self.oversight_visibility
                + self.escalation_responsiveness
            )
            / 4.0,
            4,
        )

    def to_report(self) -> Mapping[str, Any]:
        return {
            "tenant_id": self.tenant_id,
            "computed_at": self.computed_at.isoformat(),
            "human_approval_coverage": self.human_approval_coverage,
            "audit_trail_completeness": self.audit_trail_completeness,
            "oversight_visibility": self.oversight_visibility,
            "escalation_responsiveness": self.escalation_responsiveness,
            "composite": self.composite,
            # Named, so a consumer cannot mistake this for a ruling.
            "is_a_compliance_ruling": False,
            "note": "evidence for Governance; only Governance declares compliance (15.6.1)",
        }


def compose_constitutional_health(
    tenant_id: str,
    at: datetime,
    approvals_required: int,
    approvals_obtained: int,
    journal_entries: int,
    journal_intact: bool,
    subsystems_reporting: int,
    subsystems_total: int,
    escalations_raised: int,
    escalations_acknowledged: int,
) -> ConstitutionalHealth:
    """16.26's four dimensions from countable facts.

    Each dimension is a ratio of something observed to something expected, so a
    subsystem that goes silent lowers the score rather than being omitted from
    it. Absence of evidence reads as a gap, not as health.
    """
    if subsystems_total <= 0:
        raise ValidationError("constitutional health needs a non-zero subsystem count")
    return ConstitutionalHealth(
        tenant_id=tenant_id,
        computed_at=at,
        human_approval_coverage=_ratio(approvals_obtained, approvals_required),
        # Deliberately binary. A broken chain scores zero regardless of volume,
        # because a tampered journal is not a partially complete audit trail;
        # and an empty one scores zero because no trail is not a clean trail.
        audit_trail_completeness=1.0 if journal_intact and journal_entries > 0 else 0.0,
        oversight_visibility=_ratio(subsystems_reporting, subsystems_total),
        escalation_responsiveness=_ratio(escalations_acknowledged, escalations_raised),
    )


def _ratio(observed: int, expected: int) -> float:
    if expected <= 0:
        # Nothing was required, so nothing is missing.
        return 1.0
    return round(min(1.0, observed / expected), 4)


def default_slos() -> Sequence[SLO]:
    """The targets 21B's per-subsystem §12 tables publish, as a starting set."""
    return (
        SLO(
            name="security.authorization.p50",
            subsystem="security_gateway",
            indicator="authorization_latency_seconds",
            target=0.02,
            unit="s",
            rationale="21B §22.12 authorization budget",
            source="21B §22.12",
        ),
        SLO(
            name="tool.authorization.p50",
            subsystem="tool_gateway",
            indicator="authorization_latency_seconds",
            target=0.02,
            unit="s",
            rationale="21B §19.12; a principal input to CIR-004",
            source="21B §19.12",
        ),
        SLO(
            name="learning.observation_to_extraction.p50",
            subsystem="learning_gateway",
            indicator="extraction_latency_seconds",
            target=1.0,
            unit="s",
            rationale="13.25.1",
            source="21B §21.12",
        ),
        SLO(
            name="panic.completion",
            subsystem="human_interface",
            indicator="panic_elapsed_seconds",
            target=5.0,
            unit="s",
            rationale="17.31.4 — constitutional bound, not a performance goal",
            source="17.31.4",
        ),
    )
