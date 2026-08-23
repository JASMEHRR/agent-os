"""Replay Engine (21B §15.3, realizes 08.15).

"Replay is not recovery; it is the deliberate reconstruction of past behavior"
(08.15.1). Three modes exist — forensic, learning, recovery — and all three
share one constraint that the implementation makes structural rather than
procedural: **replay never mutates live business state** (08 rule 11).

Two mechanisms enforce that here. Replayed events are returned as
replay-tagged copies (`PublishedEvent.as_replay`), so a consumer can always
tell replay from live delivery. And a replay is delivered into a
`ReplaySandbox` — a separate result object — rather than through the Delivery
Manager, so there is no path by which a replayed event reaches a live consumer
group's acknowledgment bookkeeping.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum

from core.exceptions import ValidationError
from event_bus.causality import CausalityTracker
from event_bus.envelope import PublishedEvent
from event_bus.streams import StreamStore


class ReplayMode(StrEnum):
    """The three modes of 08.15.2."""

    FORENSIC = "forensic"
    LEARNING = "learning"
    RECOVERY = "recovery"


@dataclass(frozen=True)
class ReplaySandbox:
    """The isolated result of one replay request.

    Holding the events in a returned object rather than dispatching them is
    what makes "sandboxed context" a property of the code instead of a promise
    in a runbook.
    """

    replay_id: str
    mode: ReplayMode
    requested_by: str
    tenant_id: str
    events: tuple[PublishedEvent, ...]
    created_at: datetime

    def __len__(self) -> int:
        return len(self.events)

    @property
    def all_tagged(self) -> bool:
        return all(event.replay for event in self.events)


@dataclass
class ReplayEngine:
    """Reconstructs event sequences into sandboxed context with replay metadata."""

    store: StreamStore
    causality: CausalityTracker
    _replays: list[ReplaySandbox] = field(default_factory=list, init=False)

    def replay(
        self,
        mode: ReplayMode,
        requested_by: str,
        tenant_id: str,
        stream: str | None = None,
        correlation_id: str | None = None,
        from_sequence: int = 0,
        limit: int | None = None,
    ) -> ReplaySandbox:
        """Replay Request interface (21B §15.5).

        Either a stream or a correlation ID scopes the replay. A forensic
        replay of one business operation uses the correlation ID; a recovery
        replay rebuilding derived state uses the stream.
        """
        if stream is None and correlation_id is None:
            raise ValidationError("a replay must be scoped by stream or correlation_id")

        if correlation_id is not None:
            candidates = [
                published
                for event_id in self.causality.trace(correlation_id)
                if (published := self.store.get(event_id)) is not None
            ]
            candidates.sort(key=lambda p: (p.stream, p.sequence))
        else:
            # `stream` is not None here: the guard above rejects the case where
            # both scopes are absent. Written as a branch rather than an assert
            # so it survives `python -O`.
            candidates = self.store.read(stream or "", from_sequence=from_sequence)

        # Tenant isolation applies to replay exactly as it applies to delivery:
        # a replay may not reconstruct another tenant's history.
        scoped = [p for p in candidates if p.tenant_id == tenant_id]
        if limit is not None:
            scoped = scoped[:limit]

        sandbox = ReplaySandbox(
            replay_id=f"replay-{len(self._replays) + 1:06d}",
            mode=mode,
            requested_by=requested_by,
            tenant_id=tenant_id,
            events=tuple(p.as_replay() for p in scoped),
            created_at=datetime.now(UTC),
        )
        self._replays.append(sandbox)
        return sandbox

    @property
    def replays(self) -> tuple[ReplaySandbox, ...]:
        return tuple(self._replays)
