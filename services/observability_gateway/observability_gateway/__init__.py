"""Observability Gateway — full interpretive profile (document 16, 21B §24).

This module appears twice in the dependency graph by design. At Stage S3 it
was built ingestion-only, because every subsequent module's Signal Emission — a
mandatory Gateway mechanism (21A §5.2 item 7) — needs somewhere to land. At
Stage S10 the interpretive half completes it: Correlation Engine, SLI/SLO
Registry, alerting and escalation routing, and 16.26's constitutional health
composition.

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
    TimelineEvent,
    compose_constitutional_health,
    default_slos,
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
    "CorrelationEngine",
    "IncidentTimeline",
    "TimelineEvent",
    "SLORegistry",
    "SLO",
    "SLIReading",
    "AlertRouter",
    "Alert",
    "Severity",
    "ConstitutionalHealth",
    "compose_constitutional_health",
    "default_slos",
]
