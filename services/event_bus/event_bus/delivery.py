"""Delivery Manager, Retry Scheduler, Dead Letter Manager (21B §15.3, realizes 08.17).

Delivery is **at-least-once** (08.17.2): the Bus redelivers until acknowledged
and does not offer exactly-once — idempotency belongs to the consumer, keyed on
the Event ID, which 08.4.1 designates "the idempotency key for all time".

Acknowledgment follows durable processing and never precedes it (08 rule 9),
so `acknowledge` is a call the consumer makes *after* its own work is durable;
the Bus has no way to acknowledge on a consumer's behalf.

Nothing here is ever silently lost. Every event ends acknowledged,
dead-lettered, or alerted (21B §15.15 item 8), and dead-lettering always fires
the alert callback — 08 rule 18 forbids dead-lettering without alerting.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime

from core.exceptions import NotFoundError
from event_bus.consumers import ConsumerGroup
from event_bus.envelope import EVENT_TRANSITIONS, EventState, PublishedEvent
from kernel.lifecycle import LifecycleStateMachine


@dataclass
class DeliveryState:
    """Per (group, event) delivery bookkeeping.

    Deliberately separate from `PublishedEvent`: the fact is immutable, the
    delivery attempt history is not (08.8.3).
    """

    group_id: str
    member_id: str
    published: PublishedEvent
    attempts: int = 1
    state: EventState = EventState.DELIVERED
    delivered_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    next_attempt_at: datetime | None = None
    last_failure: str | None = None

    def machine(self) -> LifecycleStateMachine:
        return LifecycleStateMachine(transitions=dict(EVENT_TRANSITIONS), state=self.state)

    def transition(self, target: EventState) -> None:
        machine = self.machine()
        machine.transition(target)
        self.state = target


@dataclass(frozen=True)
class DeadLetter:
    """A quarantined event, retained for human review and potential replay (08.17.5)."""

    group_id: str
    published: PublishedEvent
    attempts: int
    reason: str
    quarantined_at: datetime


@dataclass
class DeadLetterManager:
    """Quarantines exhausted deliveries and alerts on depth thresholds."""

    #: Out-of-band alert sink. The Bus cannot report its own failures through
    #: itself (21B §15.11 Implementation Decision), so this is a plain callable
    #: the deployment wires to the alerting channel.
    alert: Callable[[str, dict[str, object]], None]
    #: [Engineering Decision] 08.17.5 requires depth monitoring and alerting
    #: without publishing a threshold; 100 is a starting value.
    depth_threshold: int = 100
    _entries: list[DeadLetter] = field(default_factory=list, init=False)

    def quarantine(self, state: DeliveryState, reason: str) -> DeadLetter:
        entry = DeadLetter(
            group_id=state.group_id,
            published=state.published,
            attempts=state.attempts,
            reason=reason,
            quarantined_at=datetime.now(UTC),
        )
        self._entries.append(entry)
        # 08 rule 18 — no event is dead-lettered without an alert.
        self.alert(
            "dead_letter",
            {
                "event_id": entry.published.event_id,
                "event_type": entry.published.event_type,
                "group_id": entry.group_id,
                "attempts": entry.attempts,
                "reason": reason,
                "depth": len(self._entries),
            },
        )
        if len(self._entries) >= self.depth_threshold:
            self.alert("dead_letter_depth", {"depth": len(self._entries), "threshold": self.depth_threshold})
        return entry

    def query(self, group_id: str | None = None, event_type: str | None = None) -> list[DeadLetter]:
        """Dead Letter Query interface (21B §15.5). Consumers: Human Interface, Governance."""
        return [
            entry
            for entry in self._entries
            if (group_id is None or entry.group_id == group_id)
            and (event_type is None or entry.published.event_type == event_type)
        ]

    @property
    def depth(self) -> int:
        return len(self._entries)


@dataclass
class DeliveryManager:
    """Dispatches to group members, tracks acknowledgment, manages redelivery."""

    dead_letters: DeadLetterManager
    now: Callable[[], datetime] = field(default=lambda: datetime.now(UTC))
    _in_flight: dict[tuple[str, str], DeliveryState] = field(default_factory=dict, init=False)
    _acknowledged: dict[tuple[str, str], DeliveryState] = field(default_factory=dict, init=False)
    _delivered_total: int = field(default=0, init=False)
    _retry_total: int = field(default=0, init=False)

    def dispatch(self, group: ConsumerGroup, published: PublishedEvent) -> DeliveryState:
        """Delivers one event to exactly one member of the group (21B §15.4)."""
        key = (group.group_id, published.event_id)
        existing = self._in_flight.get(key)
        if existing is not None:
            existing.attempts += 1
            existing.member_id = group.next_member()
            existing.delivered_at = self.now()
            existing.next_attempt_at = None
            if existing.state == EventState.PENDING_RETRY:
                existing.transition(EventState.DELIVERED)
            self._delivered_total += 1
            return existing

        state = DeliveryState(
            group_id=group.group_id,
            member_id=group.next_member(),
            published=published,
            delivered_at=self.now(),
        )
        self._in_flight[key] = state
        self._delivered_total += 1
        return state

    def acknowledge(self, group_id: str, event_id: str) -> DeliveryState:
        """Consumer's promise that the fact has been durably handled (08.7.7)."""
        key = (group_id, event_id)
        state = self._in_flight.get(key)
        if state is None:
            raise NotFoundError(f"no in-flight delivery of '{event_id}' to group '{group_id}'")
        state.transition(EventState.ACKNOWLEDGED)
        self._acknowledged[key] = state
        del self._in_flight[key]
        return state

    def signal_failure(self, group: ConsumerGroup, event_id: str, reason: str) -> DeliveryState | DeadLetter:
        """Explicit failure signalling (08.10.2), scheduling retry or dead-lettering."""
        key = (group.group_id, event_id)
        state = self._in_flight.get(key)
        if state is None:
            raise NotFoundError(f"no in-flight delivery of '{event_id}' to group '{group.group_id}'")
        state.last_failure = reason
        if state.attempts >= group.retry_policy.max_attempts:
            state.transition(EventState.PENDING_RETRY)
            state.transition(EventState.DEAD_LETTERED)
            del self._in_flight[key]
            return self.dead_letters.quarantine(state, reason)
        state.transition(EventState.PENDING_RETRY)
        state.next_attempt_at = self.now() + group.retry_policy.delay_for(state.attempts)
        self._retry_total += 1
        return state

    def due_for_retry(self, group_id: str | None = None) -> list[DeliveryState]:
        """Retry Scheduler: deliveries whose backoff interval has elapsed (08.8.2)."""
        now = self.now()
        return [
            state
            for (gid, _), state in self._in_flight.items()
            if state.state == EventState.PENDING_RETRY
            and state.next_attempt_at is not None
            and now >= state.next_attempt_at
            and (group_id is None or gid == group_id)
        ]

    def in_flight(self, group_id: str | None = None) -> list[DeliveryState]:
        return [s for (gid, _), s in self._in_flight.items() if group_id is None or gid == group_id]

    def is_acknowledged(self, group_id: str, event_id: str) -> bool:
        return (group_id, event_id) in self._acknowledged

    @property
    def delivered_total(self) -> int:
        return self._delivered_total

    @property
    def retry_total(self) -> int:
        return self._retry_total

    @property
    def acknowledged_total(self) -> int:
        return len(self._acknowledged)
