"""Telemetry Ingest and Signal Enrichment (21B §24.3, realizes 16.7.2, 16.7.3).

Ingestion is "the boundary where raw operational data enters the interpretive
domain" (16.7.2). The Gateway validates incoming signals against schema,
completeness and cardinality constraints; invalid or incomplete signals
trigger a quality anomaly rather than being dropped quietly.

Enrichment then adds what the emitter could not know: ingestion time, the
sequence position, and the constitutional scope the signal falls under
(16.7.3). Enrichment never edits what the emitter asserted — the enriched
record wraps the original signal rather than rewriting it, so a disagreement
between emitted and ingested values stays visible.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum

from kernel.signals import Signal, SignalType

#: [Engineering Decision] 16.7.2 mandates cardinality constraints without
#: publishing a limit. Distinct signal names per source are capped so a
#: misbehaving emitter using unbounded names (an ID in the metric name, the
#: classic cardinality explosion) is caught rather than silently absorbed.
CARDINALITY_LIMIT = 1_000


class SignalState(StrEnum):
    """Signal states of 16.8.1 reachable in the ingestion-only profile.

    Composed, Referenced and Summarized belong to the interpretive profile
    deferred to Stage S10, and are deliberately absent here rather than
    present-but-unreachable.
    """

    EMITTED = "emitted"
    INGESTED = "ingested"
    ENRICHED = "enriched"
    ARCHIVED = "archived"
    EXPIRED = "expired"


class QualityAnomalyKind(StrEnum):
    """Why a signal failed the ingestion boundary (16.7.2)."""

    SCHEMA = "schema"
    INCOMPLETE = "incomplete"
    CARDINALITY = "cardinality"
    DUPLICATE = "duplicate"


@dataclass(frozen=True)
class QualityAnomaly:
    """A rejected signal, recorded rather than discarded.

    16.7.8 treats signal problems as observable facts in their own right; a
    silently dropped signal would make the coverage gap itself invisible.
    """

    kind: QualityAnomalyKind
    signal_id: str
    source_identity: str
    detail: str
    detected_at: datetime


@dataclass(frozen=True)
class EnrichedSignal:
    """An ingested signal plus the context ingestion adds (16.7.3)."""

    signal: Signal
    sequence: int
    ingested_at: datetime
    state: SignalState
    #: Constitutional scope this signal falls under — tenant, business,
    #: workspace — resolved at ingestion rather than asserted by the emitter.
    scope: tuple[str, ...]
    #: Wall-clock gap between emission and ingestion, the raw input to the
    #: ingest-to-visibility SLO of 21B §24.12.
    ingest_lag_seconds: float

    @property
    def signal_id(self) -> str:
        return self.signal.signal_id

    @property
    def source_identity(self) -> str:
        return self.signal.source_identity

    @property
    def tenant_id(self) -> str:
        return self.signal.tenant_id


class SignalRejected(Exception):
    """Raised only to the ingest path itself; emitters never see it (16.4)."""

    def __init__(self, anomaly: QualityAnomaly):
        super().__init__(f"signal rejected ({anomaly.kind.value}): {anomaly.detail}")
        self.anomaly = anomaly


@dataclass
class TelemetryIngest:
    """Receives signals from the Kernel's out-of-band emission channel.

    Buffered and asynchronous relative to the emitter's request path
    (21B §24.4 Implementation Decision) — `ingest` does the validation and
    enrichment work but the emitter's `SignalEmitter.submit` already returned
    before any of it could matter, and a raise here is caught there.
    """

    now: Callable[[], datetime] = field(default=lambda: datetime.now(UTC))
    cardinality_limit: int = CARDINALITY_LIMIT
    _signals: list[EnrichedSignal] = field(default_factory=list, init=False)
    _seen_ids: set[str] = field(default_factory=set, init=False)
    _names_by_source: dict[str, set[str]] = field(default_factory=dict, init=False)
    _anomalies: list[QualityAnomaly] = field(default_factory=list, init=False)

    def ingest(self, signal: Signal) -> EnrichedSignal:
        """Validates, enriches and records one signal (16.7.2, 16.7.3)."""
        self._validate(signal)
        ingested_at = self.now()
        enriched = EnrichedSignal(
            signal=signal,
            sequence=len(self._signals),
            ingested_at=ingested_at,
            state=SignalState.ENRICHED,
            scope=self._scope_of(signal),
            ingest_lag_seconds=max(0.0, (ingested_at - signal.timestamp).total_seconds()),
        )
        self._signals.append(enriched)
        self._seen_ids.add(signal.signal_id)
        self._names_by_source.setdefault(signal.source_identity, set()).add(signal.name)
        return enriched

    def _validate(self, signal: Signal) -> None:
        if signal.signal_id in self._seen_ids:
            self._reject(QualityAnomalyKind.DUPLICATE, signal, "signal_id already ingested")
        if not signal.name or not signal.tenant_id or not signal.source_identity:
            self._reject(QualityAnomalyKind.INCOMPLETE, signal, "name, tenant_id and source_identity are required")
        if signal.signal_type == SignalType.METRIC and signal.value is None:
            self._reject(QualityAnomalyKind.SCHEMA, signal, "a metric signal must carry a value")
        if not 0.0 <= signal.confidence <= 1.0:
            self._reject(QualityAnomalyKind.SCHEMA, signal, f"confidence {signal.confidence} is outside 0.0-1.0")
        known = self._names_by_source.get(signal.source_identity, set())
        if signal.name not in known and len(known) >= self.cardinality_limit:
            self._reject(
                QualityAnomalyKind.CARDINALITY,
                signal,
                f"source '{signal.source_identity}' exceeded {self.cardinality_limit} distinct signal names",
            )

    def _reject(self, kind: QualityAnomalyKind, signal: Signal, detail: str) -> None:
        anomaly = QualityAnomaly(
            kind=kind,
            signal_id=signal.signal_id,
            source_identity=signal.source_identity,
            detail=detail,
            detected_at=self.now(),
        )
        self._anomalies.append(anomaly)
        raise SignalRejected(anomaly)

    def _scope_of(self, signal: Signal) -> tuple[str, ...]:
        scope = [f"tenant:{signal.tenant_id}"]
        if signal.business_id:
            scope.append(f"business:{signal.business_id}")
        if signal.workspace_id:
            scope.append(f"workspace:{signal.workspace_id}")
        return tuple(scope)

    def all_signals(self) -> list[EnrichedSignal]:
        return list(self._signals)

    @property
    def anomalies(self) -> tuple[QualityAnomaly, ...]:
        return tuple(self._anomalies)

    @property
    def ingested_count(self) -> int:
        return len(self._signals)

    def cardinality(self, source_identity: str) -> int:
        return len(self._names_by_source.get(source_identity, set()))
