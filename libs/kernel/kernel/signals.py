"""Signal Emission contract (21A §5.2 item 7).

The seventh universal Gateway mechanism, factored here once rather than
reimplemented per-Gateway. Every subsystem emits structured signals during
execution — metrics at intervals, events at state transitions, journals at
decision points, traces across activity boundaries — and 16.7.1 is explicit
that "emission is mandatory, not optional".

Two properties are load-bearing and are why this lives in the kernel rather
than in the Observability Gateway:

**The channel is out-of-band.** Signals do not travel over the Event Bus.
21B §15.11 requires the Bus's own health to reach Observability without
depending on the Bus, and 21B §24.3 names this the same channel. A subsystem
that could only report its failure through a mechanism that had failed would
be unobservable exactly when it mattered.

**Emission never blocks the caller.** 21B §24.4 establishes that no
subsystem's latency budget includes time spent waiting on Observability
ingest, because a slow observability path that could back-pressure an
operational subsystem would be steering it, violating 16.4. `emit` therefore
appends to a local buffer and returns; draining is somebody else's problem,
and a sink that raises is contained rather than propagated.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

#: [Engineering Decision] 16.7.8 requires local buffering when the Gateway is
#: unavailable but publishes no depth. Beyond this many unsent signals the
#: emitter drops oldest-first, so a prolonged outage cannot exhaust memory in
#: the emitting subsystem — losing telemetry is survivable, losing the
#: operational subsystem is not.
DEFAULT_BUFFER_LIMIT = 10_000


class SignalType(StrEnum):
    """The four signal kinds subsystems emit (16.7.1)."""

    METRIC = "metric"
    EVENT = "event"
    JOURNAL = "journal"
    TRACE = "trace"


class Sensitivity(StrEnum):
    """Sensitivity classification of 16.5.1."""

    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"
    SOVEREIGN = "sovereign"


class ConsumerAuthority(StrEnum):
    """Consumer authority classification of 16.5.3."""

    O1_SUBSYSTEM_INTERNAL = "O1"
    O2_CROSS_SUBSYSTEM = "O2"
    O3_HUMAN_SCOPED = "O3"
    O4_AUDIT_SCOPED = "O4"


@dataclass(frozen=True)
class Signal:
    """One emitted signal, carrying the identity primitives of 16.4.1.

    No anonymous observability artifacts are permitted (16.4.2), so
    `source_identity` and `tenant_id` have no defaults — a signal that cannot
    say who emitted it cannot be constructed.
    """

    signal_type: SignalType
    name: str
    source_identity: str
    tenant_id: str
    value: float | None = None
    attributes: dict[str, Any] = field(default_factory=dict)
    sensitivity: Sensitivity = Sensitivity.INTERNAL
    authority: ConsumerAuthority = ConsumerAuthority.O2_CROSS_SUBSYSTEM
    trace_id: str | None = None
    business_id: str | None = None
    workspace_id: str | None = None
    #: Immutable links to parent signals and constitutional provisions (16.4.1).
    lineage: tuple[str, ...] = ()
    confidence: float = 1.0
    schema_version: str = "1.0.0"
    signal_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class SignalEmitter:
    """The out-of-band emission channel every Gateway holds.

    `sink` is the Observability Gateway's ingestion endpoint in production and
    a list in tests. It is optional: a subsystem constructed before
    Observability exists still emits, buffering locally until a sink is
    attached, which is what lets Security (S1) and the Event Bus (S2) be built
    before Observability (S3) without either of them special-casing its
    absence.
    """

    source_identity: str
    sink: Callable[[Signal], None] | None = None
    buffer_limit: int = DEFAULT_BUFFER_LIMIT
    _buffer: list[Signal] = field(default_factory=list, init=False)
    _emitted: int = field(default=0, init=False)
    _dropped: int = field(default=0, init=False)
    _sink_failures: int = field(default=0, init=False)

    def emit(
        self,
        signal_type: SignalType,
        name: str,
        tenant_id: str,
        value: float | None = None,
        **attributes: Any,
    ) -> Signal:
        """Emits one signal. Never raises on the caller's behalf, never blocks."""
        signal = Signal(
            signal_type=signal_type,
            name=name,
            source_identity=self.source_identity,
            tenant_id=tenant_id,
            value=value,
            attributes=dict(attributes),
        )
        return self.submit(signal)

    def submit(self, signal: Signal) -> Signal:
        """Emits a fully-formed signal, for callers that need the richer fields."""
        self._emitted += 1
        if self.sink is None:
            self._buffer_signal(signal)
            return signal
        try:
            self.sink(signal)
        except Exception:
            # A failing Observability path must not surface in an operational
            # path (16.4 — observability reads, it does not steer). The signal
            # buffers for a later drain and the failure is counted, not raised.
            self._sink_failures += 1
            self._buffer_signal(signal)
        return signal

    def attach(self, sink: Callable[[Signal], None]) -> int:
        """Attaches a sink and drains whatever buffered while it was absent."""
        self.sink = sink
        return self.drain()

    def drain(self) -> int:
        """Flushes the local buffer to the sink, returning how many were sent."""
        if self.sink is None:
            return 0
        pending, self._buffer = self._buffer, []
        sent = 0
        for signal in pending:
            try:
                self.sink(signal)
                sent += 1
            except Exception:
                self._sink_failures += 1
                self._buffer_signal(signal)
        return sent

    def _buffer_signal(self, signal: Signal) -> None:
        self._buffer.append(signal)
        while len(self._buffer) > self.buffer_limit:
            self._buffer.pop(0)
            self._dropped += 1

    @property
    def buffered(self) -> int:
        return len(self._buffer)

    @property
    def emitted(self) -> int:
        return self._emitted

    @property
    def dropped(self) -> int:
        return self._dropped

    @property
    def sink_failures(self) -> int:
        return self._sink_failures
