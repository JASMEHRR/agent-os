"""Batched digests, and the critical events that bypass them (18.35.4, 19.36.5,
16.25.2, 16.25.3).

18.35.4 and 19.36.5 state the same rule: routine events are batched into
scheduled digests to minimize cognitive load, while critical events trigger
**immediate** notification.

The Build Specification's S8 test list phrases the requirement as operators
receiving "batched (not spammed) digests". Both halves are failures:

* spamming every routine event trains the operator to ignore notifications,
  and the alert that matters arrives into that trained inattention;
* batching a critical event delays the one notification that could not wait.

So severity decides the channel, and the classification is made at submission
rather than at delivery. A digest that could be forced to carry a critical
event, or an immediate channel that could be flooded with routine ones, would
put the decision in the hands of whoever calls the deliverer.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any

from core.exceptions import ValidationError


class Severity(StrEnum):
    """Routine batches; critical does not.

    The critical set is named by the documents: sovereignty breach, geographic
    drift and catastrophic failure (18.35.4); non-violable breach attempt,
    identity erosion and experimental scope violation (19.36.5); plus any
    Category 1 incident.
    """

    ROUTINE = "routine"
    ELEVATED = "elevated"
    CRITICAL = "critical"


#: [Engineering Decision] 16.25.3 lets humans configure digest cadence and
#: names no default. Six hours keeps a routine item from waiting a full day
#: while still collapsing a burst into one delivery.
DEFAULT_CADENCE = timedelta(hours=6)


@dataclass(frozen=True)
class Notification:
    """One thing an operator may need to know."""

    notification_id: str
    tenant_id: str
    severity: Severity
    subsystem: str
    summary: str
    detail: Mapping[str, Any]
    raised_at: datetime


@dataclass(frozen=True)
class Digest:
    """A scheduled batch. Never contains a critical item."""

    digest_id: str
    tenant_id: str
    items: tuple[Notification, ...]
    assembled_at: datetime
    covering_since: datetime

    @property
    def size(self) -> int:
        return len(self.items)


@dataclass
class DigestService:
    """Routes by severity: batch the routine, deliver the critical at once."""

    #: Where an immediate notification goes. Called synchronously, because a
    #: critical event queued behind anything is no longer immediate.
    deliver_now: Callable[[Notification], None]
    now: Callable[[], datetime] = field(default=lambda: datetime.now(UTC))
    cadence: timedelta = DEFAULT_CADENCE

    def __post_init__(self) -> None:
        self._pending: dict[str, list[Notification]] = {}
        self._delivered_immediately: list[Notification] = []
        self._digests: list[Digest] = []
        self._last_digest_at: dict[str, datetime] = {}
        self._cadence_overrides: dict[str, timedelta] = {}

    def configure_cadence(self, tenant_id: str, cadence: timedelta) -> None:
        """16.25.3 — humans configure digest cadence through a standing order."""
        if cadence <= timedelta(0):
            raise ValidationError("a digest cadence must be positive")
        self._cadence_overrides[tenant_id] = cadence

    def submit(self, notification: Notification) -> str:
        """Returns the channel used: `immediate` or `digest`.

        Severity decides, and nothing downstream can override it.
        """
        if notification.severity == Severity.CRITICAL:
            self.deliver_now(notification)
            self._delivered_immediately.append(notification)
            return "immediate"
        self._pending.setdefault(notification.tenant_id, []).append(notification)
        return "digest"

    def due(self, tenant_id: str) -> bool:
        pending = self._pending.get(tenant_id)
        if not pending:
            return False
        last = self._last_digest_at.get(tenant_id)
        if last is None:
            last = min(n.raised_at for n in pending)
        return self.now() - last >= self._cadence_for(tenant_id)

    def assemble(self, tenant_id: str, digest_id: str) -> Digest:
        """Drains the tenant's pending queue into one delivery."""
        pending = self._pending.pop(tenant_id, [])
        if not pending:
            raise ValidationError(f"nothing pending for '{tenant_id}'; an empty digest is noise")
        covering_since = min(n.raised_at for n in pending)
        digest = Digest(
            digest_id=digest_id,
            tenant_id=tenant_id,
            items=tuple(sorted(pending, key=lambda n: (n.severity != Severity.ELEVATED, n.raised_at))),
            assembled_at=self.now(),
            covering_since=covering_since,
        )
        self._digests.append(digest)
        self._last_digest_at[tenant_id] = digest.assembled_at
        return digest

    def pending_count(self, tenant_id: str) -> int:
        return len(self._pending.get(tenant_id, ()))

    def flush_all(self, prefix: str = "digest") -> list[Digest]:
        """Used by the Panic Protocol: nothing routine stays queued during panic.

        16.25.4 requires panic to disclose completely and explicitly
        "prioritizes completeness over cognitive load minimization", which is
        the one circumstance where batching yields.
        """
        return [
            self.assemble(tenant_id, f"{prefix}-{tenant_id}")
            for tenant_id in list(self._pending)
            if self._pending[tenant_id]
        ]

    def _cadence_for(self, tenant_id: str) -> timedelta:
        return self._cadence_overrides.get(tenant_id, self.cadence)

    def health(self) -> Mapping[str, Any]:
        return {
            "digests_delivered": len(self._digests),
            "immediate_deliveries": len(self._delivered_immediately),
            "pending": {tenant: len(items) for tenant, items in self._pending.items() if items},
            "mean_digest_size": (
                round(sum(d.size for d in self._digests) / len(self._digests), 4) if self._digests else 0.0
            ),
            "cadence_hours": round(self.cadence.total_seconds() / 3600, 2),
        }
