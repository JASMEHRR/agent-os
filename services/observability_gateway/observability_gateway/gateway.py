"""Observability Gateway — full interpretive profile (Stages S3 and S10, 21B §24).

Stage S3 built the ingestion half: Telemetry Ingest, signal enrichment, the
journal that makes ingested telemetry durable, a read-only query surface, and
the Panic Confirmation Listener.

**Stage S10 completes it.** The Correlation Engine, the SLI/SLO Registry,
alerting and escalation routing, and 16.26's constitutional health composition
live in `interpretive.py` and are exposed here. This module appears twice in
the dependency graph by design (Build Spec S10): ingestion-only at Level 3 so
every subsequent module's Signal Emission has somewhere to land, and the full
interpretive profile at Level 12 once there is enough system to interpret.

The architectural constraint that governs everything in this module: 16.4 —
"observability reads the system; it does not steer it." 21B §24.14 sharpens
it: Observability may not write to, configure, or otherwise steer any
subsystem it observes, and may not serve as a hidden control channel. Every
public method here is read-only or receive-only, and a test asserts no
mutating verb has crept into the surface.

| 21B §24.5 interface        | Method                      | Profile |
|----------------------------|-----------------------------|---------|
| Signal ingestion endpoint  | `ingest` / `sink_for`       | S3      |
| Query API                  | `query`                     | S3      |
| Panic Confirmation Signal  | `confirm_halt` / `panic_confirmation` | S3 |
| Incident Timeline API      | `correlate`                 | S10     |
| SLI/SLO Publication        | `publish_slo` / `record_sli`| S10     |
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

from core.exceptions import AgentOSError
from kernel.journal import ImmutableJournal
from kernel.panic import PANIC_BOUND_SECONDS
from kernel.signals import Sensitivity, Signal, SignalType
from observability_gateway.ingest import (
    EnrichedSignal,
    QualityAnomaly,
    SignalRejected,
    TelemetryIngest,
)
from observability_gateway.interpretive import (
    SLO,
    Alert,
    AlertRouter,
    ConstitutionalHealth,
    CorrelationEngine,
    IncidentTimeline,
    Severity,
    SLIReading,
    SLORegistry,
    compose_constitutional_health,
    default_slos,
)
from persistence.in_memory import InMemoryRepository

#: [Implementation Decision, 21B §24.12] Ingest-to-visibility targets. These
#: are Observability's own internal SLOs and are deliberately *not* inputs to
#: any other subsystem's latency budget — §24.4 establishes that no
#: operational path waits on Observability.
METRIC_VISIBILITY_P50 = timedelta(seconds=2)
METRIC_VISIBILITY_P99 = timedelta(seconds=10)
LOG_TRACE_VISIBILITY_P50 = timedelta(seconds=5)
LOG_TRACE_VISIBILITY_P99 = timedelta(seconds=30)


class QueryNotAuthorized(AgentOSError):
    """21B §24.10 — there is no privileged observability bypass of Security."""


class QueryAuthorizer(Protocol):
    """Security Gateway authorization for the Query API (21B §24.6).

    A Protocol, so the read path depends on the shape of authorization rather
    than on the Gateway's internals — and so the absence of a "grant" method
    on this surface is structural.
    """

    def may_query(self, token: str, tenant_id: str, sensitivity: str) -> bool: ...


@dataclass(frozen=True)
class HaltConfirmation:
    """One subsystem's report that it has already halted (16.19).

    21B §24.14 is explicit that this is "a report of a halt that has already
    occurred, not a mechanism that causes the halt". Nothing in this module
    can trigger a halt; it can only observe that one happened and time it.
    """

    subsystem: str
    confirmed_at: datetime
    elapsed_seconds: float

    @property
    def within_bound(self) -> bool:
        return self.elapsed_seconds <= PANIC_BOUND_SECONDS


@dataclass
class ObservabilityGateway:
    """Full interpretive profile. Layer 0 plus Security for query authorization."""

    authorizer: QueryAuthorizer
    now: Callable[[], datetime] = field(default=lambda: datetime.now(UTC))
    #: Category 1 escalation, for a breach severe enough to be an incident.
    escalate: Callable[[Any, str], None] = field(default=lambda trigger, detail: None)
    #: Where a critical alert reaches Governance. A notification, never a
    #: command: 16.4 gives this Gateway no return path into a subsystem.
    notify_governance: Callable[[Alert], None] = field(default=lambda alert: None)
    #: 16.14.3 — SLO registry changes are Governance-visible.
    on_slo_change: Callable[[str, SLO], None] = field(default=lambda action, slo: None)

    def __post_init__(self) -> None:
        self.ingest_engine = TelemetryIngest(now=self.now)
        self.journal = ImmutableJournal()
        self.repository: InMemoryRepository[EnrichedSignal] = InMemoryRepository()
        self._halt_confirmations: list[HaltConfirmation] = []
        self._panic_started_at: datetime | None = None
        # Stage S10 — the interpretive half.
        self.correlation = CorrelationEngine(now=self.now)
        self.slos = SLORegistry(on_change=self.on_slo_change)
        self.alerts = AlertRouter(escalate=self.escalate, notify_governance=self.notify_governance, now=self.now)
        for slo in default_slos():
            self.slos.publish(slo)

    # -------------------------------------------- Interpretive profile (S10)

    def register_journal(self, subsystem: str, journal: Any) -> None:
        """Journal read access for timeline reconstruction (21B §24.6).

        Read access only. A Gateway that could write to a subsystem's journal
        would be able to author the record it later reports on.
        """
        self.correlation.register_journal(subsystem, journal)

    def correlate(self, token: str, tenant_id: str, key: str, value: str) -> IncidentTimeline:
        """**Incident Timeline API** (21B §24.5). Read-only, reconstructed per query.

        Authorized like every other read: 21B §24.10 leaves no privileged
        observability bypass of Security, and an incident timeline is among the
        most revealing things the system can produce.
        """
        if not self.authorizer.may_query(token, tenant_id, Sensitivity.RESTRICTED.value):
            raise QueryNotAuthorized(f"the caller may not read incident timelines for tenant '{tenant_id}'")
        return self.correlation.correlate(key, value)

    def publish_slo(self, slo: SLO) -> SLO:
        """**SLI/SLO Publication** (21B §24.5). Informational; not enforced here."""
        return self.slos.publish(slo)

    def record_sli(self, name: str, observed: float) -> SLIReading:
        """Records a measurement and alerts on a breach. It does not intervene."""
        reading = self.slos.record(name, observed, self.now())
        if not reading.meets_target:
            self.alerts.raise_alert(
                f"slo-{name}-{len(self.slos.breaches())}",
                "all",
                Severity.WARNING,
                reading.slo.subsystem,
                f"{name} observed {observed}{reading.slo.unit} against a {reading.slo.target}{reading.slo.unit} target",
                ratio=reading.ratio,
            )
        return reading

    def raise_alert(
        self, alert_id: str, tenant_id: str, severity: Severity, subsystem: str, summary: str, **detail: Any
    ) -> Alert:
        """Alerting and Escalation (16.16, 16.17). Routes by severity."""
        return self.alerts.raise_alert(alert_id, tenant_id, severity, subsystem, summary, **detail)

    def constitutional_health(
        self,
        tenant_id: str,
        approvals_required: int,
        approvals_obtained: int,
        subsystems_reporting: int,
        subsystems_total: int,
        escalations_raised: int,
        escalations_acknowledged: int,
    ) -> ConstitutionalHealth:
        """16.26's constitutional health measurement.

        Evidence for Governance, not a verdict: 15.6.1 makes Governance the
        only subsystem that may declare compliance, and the returned report
        says so explicitly rather than leaving a consumer to infer it.
        """
        return compose_constitutional_health(
            tenant_id=tenant_id,
            at=self.now(),
            approvals_required=approvals_required,
            approvals_obtained=approvals_obtained,
            journal_entries=len(self.journal),
            journal_intact=self.journal.verify_chain(),
            subsystems_reporting=subsystems_reporting,
            subsystems_total=subsystems_total,
            escalations_raised=escalations_raised,
            escalations_acknowledged=escalations_acknowledged,
        )

    # ------------------------------------------------------- Signal ingestion

    def ingest(self, signal: Signal) -> EnrichedSignal | QualityAnomaly:
        """**Signal ingestion endpoint** (21B §24.5). Consumed by every Gateway.

        Returns the anomaly instead of raising when a signal fails validation:
        the caller is an emitting subsystem's out-of-band channel, and an
        exception crossing back into it would be Observability steering an
        operational path (16.4).
        """
        try:
            enriched = self.ingest_engine.ingest(signal)
        except SignalRejected as rejection:
            self.journal.append(
                {
                    "kind": "quality_anomaly",
                    "anomaly": rejection.anomaly.kind.value,
                    "signal_id": rejection.anomaly.signal_id,
                    "source": rejection.anomaly.source_identity,
                    "detail": rejection.anomaly.detail,
                }
            )
            return rejection.anomaly

        self.repository.save(enriched.signal_id, enriched)
        self.journal.append(
            {
                "kind": "signal",
                "signal_id": enriched.signal_id,
                "signal_type": enriched.signal.signal_type.value,
                "name": enriched.signal.name,
                "source": enriched.source_identity,
                "tenant_id": enriched.tenant_id,
                "value": enriched.signal.value,
                "sensitivity": enriched.signal.sensitivity.value,
                "authority": enriched.signal.authority.value,
                "scope": list(enriched.scope),
                "sequence": enriched.sequence,
            }
        )
        return enriched

    def sink_for(self, _source_identity: str) -> Callable[[Signal], None]:
        """Returns the callable a subsystem's `SignalEmitter` attaches to.

        The emitter already identifies itself on every signal, so the source
        argument is not used to key anything — it exists so the wiring reads
        as a per-subsystem attachment at the call site.
        """

        def sink(signal: Signal) -> None:
            self.ingest(signal)

        return sink

    # -------------------------------------------------------------- Query API

    def query(
        self,
        token: str,
        tenant_id: str,
        source_identity: str | None = None,
        signal_type: SignalType | None = None,
        name: str | None = None,
        since: datetime | None = None,
        max_sensitivity: Sensitivity = Sensitivity.INTERNAL,
    ) -> list[EnrichedSignal]:
        """**Query API** (21B §24.5). Read-only, authorized by the Security Gateway.

        21B §24.10: observability data is itself sensitive, and there is no
        privileged bypass — Governance's own queries authorize the same way.
        """
        if not self.authorizer.may_query(token, tenant_id, max_sensitivity.value):
            raise QueryNotAuthorized(
                f"query of tenant '{tenant_id}' at sensitivity '{max_sensitivity.value}' is not authorized "
                "(21B §24.10 — no observability bypass of Security authorization)"
            )
        ceiling = _SENSITIVITY_ORDER[max_sensitivity]
        return [
            enriched
            for enriched in self.ingest_engine.all_signals()
            if enriched.tenant_id == tenant_id
            and _SENSITIVITY_ORDER[enriched.signal.sensitivity] <= ceiling
            and (source_identity is None or enriched.source_identity == source_identity)
            and (signal_type is None or enriched.signal.signal_type == signal_type)
            and (name is None or enriched.signal.name == name)
            and (since is None or enriched.ingested_at >= since)
        ]

    # ---------------------------------------------------- Panic confirmation

    def panic_started(self) -> None:
        """Records that a halt was ordered, so confirmations can be timed.

        Called by whoever invoked the Panic Protocol. It starts a stopwatch
        and nothing else — this module cannot order a halt.
        """
        self._panic_started_at = self.now()
        self._halt_confirmations.clear()

    def confirm_halt(self, subsystem: str) -> HaltConfirmation:
        """**Panic Confirmation Signal** (21B §24.5, 16.19): a subsystem reports it has halted."""
        started = self._panic_started_at or self.now()
        confirmed_at = self.now()
        confirmation = HaltConfirmation(
            subsystem=subsystem,
            confirmed_at=confirmed_at,
            elapsed_seconds=(confirmed_at - started).total_seconds(),
        )
        self._halt_confirmations.append(confirmation)
        self.journal.append(
            {
                "kind": "halt_confirmation",
                "subsystem": subsystem,
                "elapsed_seconds": confirmation.elapsed_seconds,
                "within_bound": confirmation.within_bound,
            }
        )
        return confirmation

    def panic_confirmation(self, expected: tuple[str, ...]) -> Mapping[str, Any]:
        """Whether every expected subsystem confirmed within the 5-second bound (16.19)."""
        confirmed = {c.subsystem: c for c in self._halt_confirmations}
        missing = [name for name in expected if name not in confirmed]
        late = [c.subsystem for c in self._halt_confirmations if not c.within_bound]
        return {
            "expected": list(expected),
            "confirmed": sorted(confirmed),
            "missing": missing,
            "late": late,
            "complete": not missing and not late,
            "slowest_seconds": max((c.elapsed_seconds for c in self._halt_confirmations), default=0.0),
        }

    # ----------------------------------------------------------- Self-health

    def health(self) -> Mapping[str, Any]:
        """Self-observation, routed through the same shape as everything else (21B §24.11).

        Classified Sovereign per 16.5.1 — observability subsystem health is
        visible only to human operators.
        """
        signals = self.ingest_engine.all_signals()
        lags = sorted(s.ingest_lag_seconds for s in signals)
        return {
            "profile": "full-interpretive",
            "sensitivity": Sensitivity.SOVEREIGN.value,
            "ingested": self.ingest_engine.ingested_count,
            "anomalies": {
                "total": len(self.ingest_engine.anomalies),
                "by_kind": _count_by(a.kind.value for a in self.ingest_engine.anomalies),
            },
            "by_source": _count_by(s.source_identity for s in signals),
            "by_type": _count_by(s.signal.signal_type.value for s in signals),
            "ingest_lag_seconds": {
                "p50": _percentile(lags, 0.50),
                "p99": _percentile(lags, 0.99),
            },
            "journal_entries": len(self.journal),
            "journal_intact": self.journal.verify_chain(),
            "halt_confirmations": len(self._halt_confirmations),
            "correlation": {"journals_registered": len(self.correlation.registered())},
            "slos": self.slos.summary(),
            "alerting": self.alerts.summary(),
        }

    def meets_visibility_slo(self) -> Mapping[str, bool]:
        """Checks measured ingest lag against the §24.12 internal targets."""
        metrics = [
            s.ingest_lag_seconds for s in self.ingest_engine.all_signals() if s.signal.signal_type == SignalType.METRIC
        ]
        others = [
            s.ingest_lag_seconds for s in self.ingest_engine.all_signals() if s.signal.signal_type != SignalType.METRIC
        ]
        return {
            "metrics_p50": _percentile(sorted(metrics), 0.50) <= METRIC_VISIBILITY_P50.total_seconds(),
            "metrics_p99": _percentile(sorted(metrics), 0.99) <= METRIC_VISIBILITY_P99.total_seconds(),
            "logs_traces_p50": _percentile(sorted(others), 0.50) <= LOG_TRACE_VISIBILITY_P50.total_seconds(),
            "logs_traces_p99": _percentile(sorted(others), 0.99) <= LOG_TRACE_VISIBILITY_P99.total_seconds(),
        }


_SENSITIVITY_ORDER: dict[Sensitivity, int] = {
    Sensitivity.PUBLIC: 0,
    Sensitivity.INTERNAL: 1,
    Sensitivity.CONFIDENTIAL: 2,
    Sensitivity.RESTRICTED: 3,
    Sensitivity.SOVEREIGN: 4,
}


def _count_by(values: Any) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return counts


def _percentile(sorted_values: list[float], fraction: float) -> float:
    if not sorted_values:
        return 0.0
    index = min(len(sorted_values) - 1, int(fraction * len(sorted_values)))
    return sorted_values[index]
