"""Event Bus — the system's nervous system (realizes document 08, 21B §15).

Built at Stage S2 because Truth follows Trust (21_PLAN §4.2 Rule 2): all later
inter-service coordination is event-mediated, never direct.

The Bus is not a Gateway (21A §5.4.2). It routes on metadata and never on
content, authorizes nothing itself, grades nothing, adjudicates nothing. What
it guarantees is delivery, ordering, durability, and causality.
"""

from event_bus.admission import (
    AdmissionController,
    AdmissionRejected,
    ProducerIdentity,
    ProducerNotAuthenticated,
    ProducerNotAuthorized,
    SchemaRejected,
    SchemaSource,
    TenantRejected,
    TrustPlane,
)
from event_bus.backpressure import (
    ArchiveManager,
    BackpressureController,
    CriticalStreamShedError,
)
from event_bus.bus import BusHaltedError, EventBus
from event_bus.causality import CausalityTracker, CausalityViolation
from event_bus.consumers import (
    ConsumerGroup,
    ConsumerGroupRegistry,
    RetryPolicy,
    Router,
)
from event_bus.delivery import DeadLetter, DeadLetterManager, DeliveryManager, DeliveryState
from event_bus.envelope import (
    CRITICAL_CATEGORIES,
    RETENTION_SCHEDULE,
    DomainCategory,
    EventState,
    Provenance,
    PublishedEvent,
    build_event,
    stream_name,
)
from event_bus.replay import ReplayEngine, ReplayMode, ReplaySandbox
from event_bus.schema_adapter import SchemaRegistrySource
from event_bus.security_adapter import SecurityGatewayTrustPlane
from event_bus.streams import GapDetector, SequenceGapError, StreamStore, StreamWriter

__all__ = [
    "EventBus",
    "BusHaltedError",
    "DomainCategory",
    "EventState",
    "PublishedEvent",
    "Provenance",
    "build_event",
    "stream_name",
    "CRITICAL_CATEGORIES",
    "RETENTION_SCHEDULE",
    "AdmissionController",
    "AdmissionRejected",
    "ProducerIdentity",
    "ProducerNotAuthenticated",
    "ProducerNotAuthorized",
    "SchemaRejected",
    "TenantRejected",
    "TrustPlane",
    "SchemaSource",
    "StreamStore",
    "StreamWriter",
    "GapDetector",
    "SequenceGapError",
    "ConsumerGroup",
    "ConsumerGroupRegistry",
    "Router",
    "RetryPolicy",
    "DeliveryManager",
    "DeliveryState",
    "DeadLetterManager",
    "DeadLetter",
    "CausalityTracker",
    "CausalityViolation",
    "BackpressureController",
    "CriticalStreamShedError",
    "ArchiveManager",
    "ReplayEngine",
    "ReplayMode",
    "ReplaySandbox",
    "SecurityGatewayTrustPlane",
    "SchemaRegistrySource",
]
