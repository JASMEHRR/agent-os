"""Stream Store, Stream Writer, and Gap Detector (21B §15.3, realizes 08.6.2, 08.14).

"Streams are not queues; they are durable logs" (08.6.2). Consumers read at
their own pace and keep their own positions; consumption does not destroy.
Multiple consumer groups read the same stream independently.

08.14.1 requires durability *before* delivery begins — an event delivered but
not durably stored would be a fact that could be un-made. `StreamWriter.append`
therefore persists before it returns, and the Delivery Manager only ever sees
events that are already on disk.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime

from core.events import Event
from core.exceptions import AgentOSError
from event_bus.envelope import DomainCategory, Provenance, PublishedEvent, stream_name
from persistence.repository import Repository


class SequenceGapError(AgentOSError):
    """Sequence discontinuity detected (21B §15.9 — Critical, triggers reconciliation)."""

    def __init__(self, stream: str, expected: int, found: int):
        super().__init__(f"sequence gap in stream '{stream}': expected {expected}, found {found}")
        self.stream = stream
        self.expected = expected
        self.found = found


@dataclass
class StreamStore:
    """Ordered, append-only durable logs partitioned by domain category and tenant.

    Every append also lands in `persistence`, so the log survives a process
    restart. The in-memory index is a read accelerator over that store, never
    the system of record.
    """

    repository: Repository[PublishedEvent]
    _streams: dict[str, list[PublishedEvent]] = field(default_factory=dict, init=False)
    _by_event_id: dict[str, PublishedEvent] = field(default_factory=dict, init=False)

    def append(self, published: PublishedEvent) -> PublishedEvent:
        # Durability first (08.14.1), then the in-memory index.
        self.repository.save(published.event_id, published)
        self._streams.setdefault(published.stream, []).append(published)
        self._by_event_id[published.event_id] = published
        return published

    def next_sequence(self, stream: str) -> int:
        return len(self._streams.get(stream, []))

    def read(self, stream: str, from_sequence: int = 0, limit: int | None = None) -> list[PublishedEvent]:
        """Reads forward from a position. Non-destructive — this is a log, not a queue."""
        events = self._streams.get(stream, [])[from_sequence:]
        return events[:limit] if limit is not None else events

    def get(self, event_id: str) -> PublishedEvent | None:
        return self._by_event_id.get(event_id)

    def streams(self) -> list[str]:
        return list(self._streams)

    def depth(self, stream: str) -> int:
        return len(self._streams.get(stream, []))

    def total_depth(self) -> int:
        return sum(len(events) for events in self._streams.values())


@dataclass
class StreamWriter:
    """Appends to the durable log and assigns the sequence identifier (08.7.3)."""

    store: StreamStore
    now: Callable[[], datetime] = field(default=lambda: datetime.now(UTC))

    def publish(self, event: Event, provenance: Provenance) -> PublishedEvent:
        category = DomainCategory.of(event.event_type)
        stream = stream_name(category, event.tenant_id)
        published = PublishedEvent(
            event=event,
            stream=stream,
            category=category,
            sequence=self.store.next_sequence(stream),
            provenance=provenance,
            published_at=self.now(),
        )
        return self.store.append(published)


@dataclass
class GapDetector:
    """Monitors sequence continuity and reports discontinuity (21B §15.3).

    A gap means an occurrence went unrecorded or a write was lost, which
    21B §15.9 classifies Critical: the response is a reconciliation workflow
    from producer and durable workflow state, never a silent renumbering.
    """

    store: StreamStore

    def check(self, stream: str) -> None:
        expected = 0
        for published in self.store.read(stream):
            if published.sequence != expected:
                raise SequenceGapError(stream, expected, published.sequence)
            expected += 1

    def scan(self) -> list[SequenceGapError]:
        """Checks every stream, returning each gap rather than raising on the first."""
        gaps: list[SequenceGapError] = []
        for stream in self.store.streams():
            try:
                self.check(stream)
            except SequenceGapError as gap:
                gaps.append(gap)
        return gaps
