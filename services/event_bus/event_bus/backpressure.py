"""Backpressure Controller and Archive Manager (21B §15.3, realizes 08.17.4, 08.15.4).

The one rule that cannot bend: **critical streams are never shed** (08 rule 7).
Command, audit and business events are shed under no load, ever. Shedding
applies only to telemetry and analytics, which in the six-category scheme means
System events. `shed` therefore refuses on category, not on configuration —
there is no setting that makes an audit event droppable.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime

from core.exceptions import AgentOSError
from event_bus.envelope import DomainCategory, PublishedEvent

#: [Engineering Decision] 08.17.4 mandates lag alerting and throttling without
#: publishing thresholds. These are starting values, tuned against the 50,000
#: events/second sustained ingestion target of 21B §15.12.
LAG_ALERT_THRESHOLD = 1_000
THROTTLE_THRESHOLD = 10_000


class CriticalStreamShedError(AgentOSError):
    """An attempt to shed a command, audit, or business event (08 rule 7)."""

    def __init__(self, published: PublishedEvent):
        super().__init__(
            f"event '{published.event_id}' is in critical category '{published.category.value}' and is "
            "never shed under any load (08 rule 7)"
        )


@dataclass
class BackpressureController:
    """Producer throttling, lag alerting, ephemeral shedding for non-critical streams."""

    alert: Callable[[str, dict[str, object]], None]
    lag_alert_threshold: int = LAG_ALERT_THRESHOLD
    throttle_threshold: int = THROTTLE_THRESHOLD
    _throttled: set[str] = field(default_factory=set, init=False)
    _shed_count: int = field(default=0, init=False)

    def observe_lag(self, group_id: str, lag: int, critical_consumer: bool = False) -> None:
        """Alerts on lag; escalates when the lagging consumer is critical (21B §15.9)."""
        if lag >= self.throttle_threshold:
            self._throttled.add(group_id)
            self.alert("backpressure_throttle", {"group_id": group_id, "lag": lag})
        elif lag >= self.lag_alert_threshold:
            self.alert(
                "consumer_lag",
                {"group_id": group_id, "lag": lag, "critical": critical_consumer},
            )

    def relieve(self, group_id: str) -> None:
        self._throttled.discard(group_id)

    def is_throttled(self, group_id: str) -> bool:
        return group_id in self._throttled

    def shed(self, published: PublishedEvent) -> None:
        """Sheds one non-critical event. Raises on anything in a critical category."""
        if published.is_critical:
            raise CriticalStreamShedError(published)
        self._shed_count += 1
        self.alert(
            "event_shed",
            {"event_id": published.event_id, "event_type": published.event_type, "total_shed": self._shed_count},
        )

    @property
    def shed_count(self) -> int:
        return self._shed_count

    @property
    def throttled_groups(self) -> frozenset[str]:
        return frozenset(self._throttled)


@dataclass
class ArchiveManager:
    """Tiers events hot → warm → cold per the 08.15.4 retention schedule.

    Archival is append-only and immutable (08.7.8). Nothing here deletes: the
    Expired state exists in the lifecycle table, but purging is a data
    governance action against cold storage, and audit events are never purged
    before their seven-year minimum (08.7.9).
    """

    now: Callable[[], datetime] = field(default=lambda: datetime.now(UTC))
    _archived: dict[str, datetime] = field(default_factory=dict, init=False)

    def archive(self, published: PublishedEvent) -> datetime:
        archived_at = self.now()
        self._archived[published.event_id] = archived_at
        return archived_at

    def is_archived(self, event_id: str) -> bool:
        return event_id in self._archived

    def due_for_archival(self, acknowledged: list[PublishedEvent]) -> list[PublishedEvent]:
        """Acknowledged events whose operational retention window has elapsed."""
        now = self.now()
        return [
            published
            for published in acknowledged
            if published.event_id not in self._archived
            and now >= published.published_at + published.retention.operational
        ]

    def purgeable(self, published: PublishedEvent) -> bool:
        """08.7.9 — audit events are never purgeable before the seven-year minimum."""
        if published.category == DomainCategory.AUDIT:
            return self.now() >= published.published_at + published.retention.audit
        return self.now() >= published.published_at + published.retention.analytical

    @property
    def archived_count(self) -> int:
        return len(self._archived)
