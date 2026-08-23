"""Consumer Group Registry and Router (21B §15.3, realizes 08.6.3, 08.10, 08.17.1).

Two rules shape this module.

**Routing is metadata-only** (08.17.1). The Router resolves groups from the
stream and the event type prefix. It never opens `payload` — content-based
routing would couple producers to consumer logic and defeat the decoupling
the Bus exists to provide.

**Tenant isolation is enforced at the routing layer, not at the consumer**
(21B §15.4). If it were enforced at the consumer, the event would already have
crossed the boundary by the time anyone checked. A group registered in one
tenant is never a candidate for another tenant's events, subscription pattern
notwithstanding.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from core.exceptions import NotFoundError, ValidationError
from event_bus.envelope import PublishedEvent

#: [Engineering Decision] 08.17.3 requires a per-group retry policy without
#: publishing figures; the Build Spec's S2 test list fixes the attempt count at
#: ten ("after 10 failed delivery attempts, an event moves to the Dead-Letter
#: Stream"). Base and maximum delay are engineering defaults, overridable per
#: group as 08.17.3 intends.
DEFAULT_MAX_ATTEMPTS = 10
DEFAULT_BASE_DELAY = timedelta(seconds=1)
DEFAULT_MAX_DELAY = timedelta(minutes=5)


@dataclass(frozen=True)
class RetryPolicy:
    """Per-consumer-group retry policy (08.17.3)."""

    max_attempts: int = DEFAULT_MAX_ATTEMPTS
    base_delay: timedelta = DEFAULT_BASE_DELAY
    max_delay: timedelta = DEFAULT_MAX_DELAY

    def delay_for(self, attempt: int) -> timedelta:
        """Exponential backoff, capped at `max_delay`."""
        scaled: timedelta = self.base_delay * (2 ** max(0, attempt - 1))
        return min(scaled, self.max_delay)


@dataclass
class ConsumerGroup:
    """A registered group with its subscription pattern and read positions (08.10)."""

    group_id: str
    tenant_id: str
    #: Event-type prefixes this group subscribes to, e.g. ("business.idea",).
    patterns: tuple[str, ...]
    members: tuple[str, ...]
    retry_policy: RetryPolicy = field(default_factory=RetryPolicy)
    #: True for groups whose events may never be shed (08 rule 7 / 17.4).
    critical: bool = False
    registered_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    #: stream -> next unread sequence. Durable-Progressive (21B §15.8).
    positions: dict[str, int] = field(default_factory=dict)
    _next_member: int = field(default=0, init=False)

    def matches(self, event_type: str) -> bool:
        """Prefix match on the hierarchical type (08.10.3). Metadata only."""
        return any(event_type == p or event_type.startswith(f"{p}.") for p in self.patterns)

    def next_member(self) -> str:
        """Round-robins within the group so each event goes to exactly one member."""
        member = self.members[self._next_member % len(self.members)]
        self._next_member += 1
        return member

    def position(self, stream: str) -> int:
        return self.positions.get(stream, 0)

    def advance(self, stream: str, to_sequence: int) -> None:
        self.positions[stream] = max(self.positions.get(stream, 0), to_sequence)


@dataclass
class ConsumerGroupRegistry:
    """Registered groups, subscription patterns, read positions, lag."""

    _groups: dict[str, ConsumerGroup] = field(default_factory=dict, init=False)

    def register(self, group: ConsumerGroup) -> ConsumerGroup:
        if group.group_id in self._groups:
            raise ValidationError(f"consumer group '{group.group_id}' is already registered")
        if not group.members:
            raise ValidationError(f"consumer group '{group.group_id}' must declare at least one member")
        if not group.patterns:
            raise ValidationError(
                f"consumer group '{group.group_id}' must declare at least one subscription pattern; "
                "a group subscribing to nothing would silently receive nothing"
            )
        self._groups[group.group_id] = group
        return group

    def get(self, group_id: str) -> ConsumerGroup:
        try:
            return self._groups[group_id]
        except KeyError:
            raise NotFoundError(f"consumer group '{group_id}' is not registered") from None

    def deregister(self, group_id: str) -> None:
        self._groups.pop(group_id, None)

    def all_groups(self) -> list[ConsumerGroup]:
        return list(self._groups.values())


@dataclass
class Router:
    """Resolves subscribed consumer groups from stream and event-type metadata."""

    registry: ConsumerGroupRegistry

    def route(self, published: PublishedEvent) -> list[ConsumerGroup]:
        """Deterministic: the same event always resolves to the same groups.

        The tenant check happens here — before any dispatch — which is what
        makes cross-tenant delivery structurally impossible rather than merely
        filtered (21B §15.15 item 6).
        """
        return [
            group
            for group in self.registry.all_groups()
            if group.tenant_id == published.tenant_id and group.matches(published.event_type)
        ]
