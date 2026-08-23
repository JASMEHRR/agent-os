"""Event envelope, classification, and lifecycle states (realizes 08.4, 08.5, 08.8).

The Bus owns the envelope, the ordering, and the delivery guarantee — never
the payload's meaning (21B §15.7). Everything in this module is metadata the
Bus is entitled to read; nothing here interprets `payload`.

State transitions apply to delivery and lifecycle metadata only. Once an
event is Published its content and identity are frozen (08.8.3), which is why
`PublishedEvent` is immutable and delivery bookkeeping lives in a separate
mutable record (`delivery.DeliveryState`).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any

from core.events import Event


class DomainCategory(StrEnum):
    """The six constitutional domain categories of 08.5.1."""

    BUSINESS = "business"
    AGENT = "agent"
    WORKFLOW = "workflow"
    SYSTEM = "system"
    COMMAND = "command"
    AUDIT = "audit"

    @staticmethod
    def of(event_type: str) -> DomainCategory:
        """Derives the category from the event type's leading segment.

        Event types are hierarchical dot-notation (08.4.1), and the first
        segment is the domain. A type outside the six categories cannot be
        admitted — there is no stream to put it in.
        """
        head = event_type.split(".", 1)[0]
        try:
            return DomainCategory(head)
        except ValueError:
            raise ValueError(
                f"event type '{event_type}' is not in one of the six domain categories of 08.5.1: "
                f"{[c.value for c in DomainCategory]}"
            ) from None


#: 08 rule 7 — command, audit, and business state transition events are never
#: shed under any load. Shedding applies only to telemetry and analytics.
CRITICAL_CATEGORIES: frozenset[DomainCategory] = frozenset(
    {DomainCategory.COMMAND, DomainCategory.AUDIT, DomainCategory.BUSINESS}
)


class EventState(StrEnum):
    """Canonical delivery states of 08.8.1."""

    PUBLISHED = "published"
    DELIVERED = "delivered"
    ACKNOWLEDGED = "acknowledged"
    PENDING_RETRY = "pending_retry"
    DEAD_LETTERED = "dead_lettered"
    ARCHIVED = "archived"
    EXPIRED = "expired"


#: 08.8.2 Transition Guards, as a table the kernel's lifecycle engine enforces.
EVENT_TRANSITIONS: dict[str, set[str]] = {
    EventState.PUBLISHED: {EventState.DELIVERED},
    EventState.DELIVERED: {EventState.ACKNOWLEDGED, EventState.PENDING_RETRY},
    EventState.PENDING_RETRY: {EventState.DELIVERED, EventState.DEAD_LETTERED},
    EventState.ACKNOWLEDGED: {EventState.ARCHIVED},
    EventState.DEAD_LETTERED: set(),
    EventState.ARCHIVED: {EventState.EXPIRED},
    EventState.EXPIRED: set(),
}


@dataclass(frozen=True)
class Retention:
    """One row of the 08.15.4 retention schedule."""

    operational: timedelta
    analytical: timedelta
    audit: timedelta


#: 08.15.4 Retention Policy, verbatim.
RETENTION_SCHEDULE: dict[DomainCategory, Retention] = {
    DomainCategory.BUSINESS: Retention(timedelta(days=30), timedelta(days=730), timedelta(days=2555)),
    DomainCategory.AGENT: Retention(timedelta(days=30), timedelta(days=730), timedelta(days=2555)),
    DomainCategory.WORKFLOW: Retention(timedelta(days=90), timedelta(days=730), timedelta(days=2555)),
    DomainCategory.SYSTEM: Retention(timedelta(days=7), timedelta(days=90), timedelta(days=2555)),
    DomainCategory.COMMAND: Retention(timedelta(days=90), timedelta(days=730), timedelta(days=2555)),
    DomainCategory.AUDIT: Retention(timedelta(days=2555), timedelta(days=2555), timedelta(days=2555)),
}


@dataclass(frozen=True)
class Provenance:
    """Causal context of 08.12.2 — the metadata surrounding the fact, not the fact."""

    #: Event ID of the event that directly caused this one; None for a root cause.
    causation_id: str | None
    #: Trace ID linking this event to the broader business operation.
    correlation_id: str
    source_identity: str
    origin_timestamp: datetime
    emission_timestamp: datetime
    business_context: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class PublishedEvent:
    """An event after publication: immutable, sequenced, observable (08.7.3).

    `sequence` is assigned per stream and gives the total ordering of 08.13.2.
    """

    event: Event
    stream: str
    category: DomainCategory
    sequence: int
    provenance: Provenance
    published_at: datetime
    #: Set on replayed copies so consumers can tell replay from live (08.15.3).
    replay: bool = False

    @property
    def event_id(self) -> str:
        return self.event.event_id

    @property
    def event_type(self) -> str:
        return self.event.event_type

    @property
    def tenant_id(self) -> str:
        return self.event.tenant_id

    @property
    def is_critical(self) -> bool:
        return self.category in CRITICAL_CATEGORIES

    @property
    def retention(self) -> Retention:
        return RETENTION_SCHEDULE[self.category]

    def as_replay(self) -> PublishedEvent:
        """Returns a replay-tagged copy. The original is never mutated (08.14.2)."""
        tagged = Event(
            event_id=self.event.event_id,
            trace_id=self.event.trace_id,
            timestamp=self.event.timestamp,
            schema_version=self.event.schema_version,
            event_type=self.event.event_type,
            source=self.event.source,
            tenant_id=self.event.tenant_id,
            payload=dict(self.event.payload),
            metadata={**self.event.metadata, "replay": True},
        )
        return PublishedEvent(
            event=tagged,
            stream=self.stream,
            category=self.category,
            sequence=self.sequence,
            provenance=self.provenance,
            published_at=self.published_at,
            replay=True,
        )


def stream_name(category: DomainCategory, tenant_id: str) -> str:
    """Stream partition key (21B §15.4 Implementation Decision).

    Partitioned by domain category and sub-partitioned by tenant, which makes
    routing-layer tenant isolation a structural property rather than a filter
    applied after the fact.
    """
    return f"{category.value}.{tenant_id}"


def build_event(
    event_type: str,
    payload: dict[str, Any],
    tenant_id: str,
    source: str,
    trace_id: str,
    schema_version: str = "1.0.0",
    metadata: dict[str, Any] | None = None,
    occurred_at: datetime | None = None,
) -> Event:
    """Constructs the core Event a producer submits for admission (08.7.2).

    `occurred_at` is the authoritative time the fact occurred, which 08.4.1
    keeps distinct from processing or observation time.
    """
    return Event(
        trace_id=trace_id,
        timestamp=occurred_at or datetime.now(UTC),
        schema_version=schema_version,
        event_type=event_type,
        source=source,
        tenant_id=tenant_id,
        payload=payload,
        metadata=metadata or {},
    )
