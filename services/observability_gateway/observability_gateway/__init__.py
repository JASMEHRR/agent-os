"""Observability Gateway — ingestion-only profile (realizes document 16, 21B §24).

Built at Stage S3 because every subsequent module's Signal Emission — a
mandatory Gateway mechanism (21A §5.2 item 7) — needs somewhere to land.

The full interpretive profile is deferred to Stage S10: this module ingests,
enriches, journals, serves read-only queries, and confirms Panic Protocol
halts. It does not correlate, compose health models, interpret anomalies, or
publish SLOs. Those are absent rather than stubbed, so nothing downstream can
depend on a hollow implementation.

`16.4`: observability reads the system; it does not steer it. Every interface
here is read-only or receive-only, by construction.
"""

from observability_gateway.gateway import (
    LOG_TRACE_VISIBILITY_P50,
    LOG_TRACE_VISIBILITY_P99,
    METRIC_VISIBILITY_P50,
    METRIC_VISIBILITY_P99,
    HaltConfirmation,
    ObservabilityGateway,
    QueryAuthorizer,
    QueryNotAuthorized,
)
from observability_gateway.ingest import (
    CARDINALITY_LIMIT,
    EnrichedSignal,
    QualityAnomaly,
    QualityAnomalyKind,
    SignalRejected,
    SignalState,
    TelemetryIngest,
)
from observability_gateway.security_adapter import SecurityGatewayQueryAuthorizer

__all__ = [
    "ObservabilityGateway",
    "QueryAuthorizer",
    "QueryNotAuthorized",
    "HaltConfirmation",
    "TelemetryIngest",
    "EnrichedSignal",
    "QualityAnomaly",
    "QualityAnomalyKind",
    "SignalRejected",
    "SignalState",
    "CARDINALITY_LIMIT",
    "METRIC_VISIBILITY_P50",
    "METRIC_VISIBILITY_P99",
    "LOG_TRACE_VISIBILITY_P50",
    "LOG_TRACE_VISIBILITY_P99",
    "SecurityGatewayQueryAuthorizer",
]
