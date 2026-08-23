"""Event Bus — the six Public Interfaces of 21B §15.5.

| 21B §15.5 interface         | Method                                    |
|-----------------------------|-------------------------------------------|
| Event Emission              | `emit`                                    |
| Consumer Group Registration | `register_consumer_group`                 |
| Event Consumption           | `consume` / `acknowledge` / `signal_failure` |
| Replay Request              | `request_replay`                          |
| Dead Letter Query           | `query_dead_letters`                      |
| Stream Health               | `health`                                  |

The Bus **is not a Gateway** (21A §5.4.2). It routes on metadata, authorizes
nothing itself, grades nothing, adjudicates nothing. Authentication and
authorization are delegated to the Trust Plane at admission; everything else
here is delivery, ordering, durability, and causality.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from core.events import Event
from core.exceptions import AgentOSError
from event_bus.admission import (
    AdmissionController,
    ProducerNotAuthorized,
    SchemaSource,
    TrustPlane,
)
from event_bus.backpressure import ArchiveManager, BackpressureController
from event_bus.causality import CausalityTracker
from event_bus.consumers import (
    ConsumerGroup,
    ConsumerGroupRegistry,
    RetryPolicy,
    Router,
)
from event_bus.delivery import DeadLetter, DeadLetterManager, DeliveryManager, DeliveryState
from event_bus.envelope import PublishedEvent, build_event
from event_bus.replay import ReplayEngine, ReplayMode, ReplaySandbox
from event_bus.streams import GapDetector, StreamStore, StreamWriter
from kernel.panic import PanicProtocol
from persistence.in_memory import InMemoryRepository


class BusHaltedError(AgentOSError):
    """The Panic Protocol has been triggered; the Bus admits nothing further."""


@dataclass
class EventBus:
    """Layer 1. Depends on Layer 0 plus the Trust Plane (21B §15.13)."""

    trust: TrustPlane
    schemas: SchemaSource
    #: Out-of-band alert sink. 21B §15.11 is explicit that Bus self-health must
    #: not travel through the Bus — a subsystem cannot report its own
    #: unavailability through the mechanism that is unavailable.
    alert: Callable[[str, dict[str, object]], None]
    now: Callable[[], datetime] = field(default=lambda: datetime.now(UTC))
    panic: PanicProtocol = field(default_factory=PanicProtocol)

    def __post_init__(self) -> None:
        self.store = StreamStore(repository=InMemoryRepository())
        self.writer = StreamWriter(store=self.store, now=self.now)
        self.gaps = GapDetector(store=self.store)
        self.admission = AdmissionController(trust=self.trust, schemas=self.schemas)
        self.registry = ConsumerGroupRegistry()
        self.router = Router(registry=self.registry)
        self.dead_letters = DeadLetterManager(alert=self.alert)
        self.deliveries = DeliveryManager(dead_letters=self.dead_letters, now=self.now)
        self.causality = CausalityTracker()
        self.backpressure = BackpressureController(alert=self.alert)
        self.archive = ArchiveManager(now=self.now)
        self.replays = ReplayEngine(store=self.store, causality=self.causality)
        self._halted = False
        self.panic.register(self._halt)

    # ------------------------------------------------------------- Emission

    def emit(
        self,
        token: str,
        event_type: str,
        payload: dict[str, Any],
        tenant_id: str,
        source: str,
        trace_id: str,
        causation_id: str | None = None,
        schema_version: str = "1.0.0",
        occurred_at: datetime | None = None,
        business_context: dict[str, str] | None = None,
    ) -> PublishedEvent:
        """**Event Emission** (21B §15.5): admit, then publish durably.

        Ordering matters and is not negotiable: admission, then durability,
        then the event becomes observable (08.14.1). Nothing downstream sees an
        event that is not already on disk.
        """
        self._require_running()
        event = build_event(
            event_type=event_type,
            payload=payload,
            tenant_id=tenant_id,
            source=source,
            trace_id=trace_id,
            schema_version=schema_version,
            occurred_at=occurred_at,
        )
        _identity, provenance = self.admission.admit(token, event, causation_id, business_context)
        self.causality.validate_propagation(causation_id, provenance.correlation_id)
        published = self.writer.publish(event, provenance)
        self.causality.record(published)
        return published

    # -------------------------------------------------- Consumer registration

    def register_consumer_group(
        self,
        token: str,
        group_id: str,
        tenant_id: str,
        patterns: tuple[str, ...],
        members: tuple[str, ...],
        retry_policy: RetryPolicy | None = None,
        critical: bool = False,
    ) -> ConsumerGroup:
        """**Consumer Group Registration** (21B §15.5).

        Authorization at subscription is the second of the two enforcement
        points in 08.18.2 — a consumer must be permitted to read the streams
        and types it asks for, checked here rather than at first delivery.
        """
        self._require_running()
        if not self.trust.authorize_subscription(token, patterns, tenant_id):
            raise ProducerNotAuthorized(
                f"consumer group '{group_id}' is not permitted to subscribe to {list(patterns)} "
                f"in tenant '{tenant_id}' (08.18.2)"
            )
        group = ConsumerGroup(
            group_id=group_id,
            tenant_id=tenant_id,
            patterns=patterns,
            members=members,
            retry_policy=retry_policy or RetryPolicy(),
            critical=critical,
        )
        return self.registry.register(group)

    # ---------------------------------------------------------- Consumption

    def consume(self, group_id: str, limit: int | None = None) -> list[DeliveryState]:
        """**Event Consumption** (21B §15.5): pull the group's unread events.

        A pull model, because streams are logs and not queues (08.6.2):
        consumers read at their own pace and hold their own positions.
        Redelivery of anything already due for retry comes first, so a failed
        event is never starved by newer traffic.
        """
        self._require_running()
        group = self.registry.get(group_id)
        deliveries: list[DeliveryState] = []

        for state in self.deliveries.due_for_retry(group_id):
            deliveries.append(self.deliveries.dispatch(group, state.published))
            if limit is not None and len(deliveries) >= limit:
                return deliveries

        for stream in sorted(self.store.streams()):
            for published in self.store.read(stream, from_sequence=group.position(stream)):
                if not self._routes_to(group, published):
                    group.advance(stream, published.sequence + 1)
                    continue
                deliveries.append(self.deliveries.dispatch(group, published))
                group.advance(stream, published.sequence + 1)
                if limit is not None and len(deliveries) >= limit:
                    return deliveries
        return deliveries

    def _routes_to(self, group: ConsumerGroup, published: PublishedEvent) -> bool:
        return group in self.router.route(published)

    def acknowledge(self, group_id: str, event_id: str) -> DeliveryState:
        """**Event Consumption**, acknowledgment half (08.7.7, 08 rule 9)."""
        state = self.deliveries.acknowledge(group_id, event_id)
        self.backpressure.relieve(group_id)
        return state

    def signal_failure(self, group_id: str, event_id: str, reason: str) -> DeliveryState | DeadLetter:
        """**Event Consumption**, failure half (08.10.2).

        Explicit failure signalling exists so retry or dead-lettering can
        happen at all; a consumer that simply goes quiet is handled by
        redelivery on timeout instead.
        """
        group = self.registry.get(group_id)
        return self.deliveries.signal_failure(group, event_id, reason)

    # --------------------------------------------------------------- Replay

    def request_replay(
        self,
        token: str,
        mode: ReplayMode,
        requested_by: str,
        tenant_id: str,
        stream: str | None = None,
        correlation_id: str | None = None,
        limit: int | None = None,
    ) -> ReplaySandbox:
        """**Replay Request** (21B §15.5). Consumers: Observability, Learning, Human Interface."""
        self._require_running()
        if not self.trust.authorize_subscription(token, ("replay",), tenant_id):
            raise ProducerNotAuthorized(f"'{requested_by}' is not permitted to replay tenant '{tenant_id}'")
        return self.replays.replay(
            mode=mode,
            requested_by=requested_by,
            tenant_id=tenant_id,
            stream=stream,
            correlation_id=correlation_id,
            limit=limit,
        )

    # ---------------------------------------------------- Dead letter query

    def query_dead_letters(self, group_id: str | None = None, event_type: str | None = None) -> list[DeadLetter]:
        """**Dead Letter Query** (21B §15.5). Consumers: Human Interface, Governance."""
        return self.dead_letters.query(group_id, event_type)

    # --------------------------------------------------------------- Health

    def health(self) -> Mapping[str, Any]:
        """**Stream Health** (21B §15.5). Consumer: Observability Gateway.

        Reports the signal set of 21B §15.11: admission and rejection by cause,
        delivery, lag per group, retries, dead-letter depth, backpressure,
        archive lag and gap indicators.
        """
        gaps = self.gaps.scan()
        return {
            "halted": self._halted,
            "streams": {name: self.store.depth(name) for name in sorted(self.store.streams())},
            "total_depth": self.store.total_depth(),
            "admission": {
                "admitted": self.admission.admitted,
                "rejected": self.admission.rejected,
                "rejections_by_cause": self.admission.rejections_by_cause,
            },
            "delivery": {
                "delivered": self.deliveries.delivered_total,
                "acknowledged": self.deliveries.acknowledged_total,
                "in_flight": len(self.deliveries.in_flight()),
                "retries": self.deliveries.retry_total,
            },
            "consumer_lag": {group.group_id: self.lag_for(group.group_id) for group in self.registry.all_groups()},
            "dead_letters": {"depth": self.dead_letters.depth},
            "backpressure": {
                "throttled_groups": sorted(self.backpressure.throttled_groups),
                "shed": self.backpressure.shed_count,
            },
            "archive": {"archived": self.archive.archived_count},
            "gaps": [{"stream": g.stream, "expected": g.expected, "found": g.found} for g in gaps],
        }

    def lag_for(self, group_id: str) -> int:
        """Unread events across every stream the group subscribes to."""
        group = self.registry.get(group_id)
        lag = 0
        for stream in self.store.streams():
            unread = self.store.read(stream, from_sequence=group.position(stream))
            lag += sum(1 for published in unread if self._routes_to(group, published))
        return lag

    def observe_backpressure(self) -> None:
        """Samples lag for every group and applies the 08.17.4 responses."""
        for group in self.registry.all_groups():
            self.backpressure.observe_lag(group.group_id, self.lag_for(group.group_id), group.critical)

    # ------------------------------------------------------------ Internals

    def _halt(self) -> None:
        """Panic Protocol participation (21A §5.2 item 8)."""
        self._halted = True

    def _require_running(self) -> None:
        if self._halted:
            raise BusHaltedError("Panic Protocol is active; the Event Bus admits and delivers nothing")


__all__ = ["EventBus", "BusHaltedError", "Event"]
