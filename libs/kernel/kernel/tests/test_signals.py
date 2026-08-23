"""Signal Emission contract — unit tests (21A §5.2 item 7, 16.4, 16.7)."""

from __future__ import annotations

import pytest

from kernel.signals import (
    ConsumerAuthority,
    Sensitivity,
    Signal,
    SignalEmitter,
    SignalType,
)


def test_signal_carries_the_identity_primitives_of_16_4_1() -> None:
    signal = Signal(
        signal_type=SignalType.METRIC,
        name="authorization.latency_ms",
        source_identity="security_gateway",
        tenant_id="tenant-alpha",
        value=4.2,
    )
    assert signal.signal_id
    assert signal.timestamp.tzinfo is not None
    assert signal.confidence == 1.0
    assert signal.sensitivity == Sensitivity.INTERNAL
    assert signal.authority == ConsumerAuthority.O2_CROSS_SUBSYSTEM


def test_a_signal_cannot_be_anonymous() -> None:
    """16.4.2 — no anonymous observability artifacts are permitted."""
    with pytest.raises(TypeError):
        Signal(signal_type=SignalType.METRIC, name="x")  # type: ignore[call-arg]


def test_emission_reaches_an_attached_sink() -> None:
    received: list[Signal] = []
    emitter = SignalEmitter(source_identity="event_bus", sink=received.append)
    emitter.emit(SignalType.METRIC, "publication.latency_ms", "tenant-alpha", value=8.0)
    assert len(received) == 1
    assert received[0].source_identity == "event_bus"
    assert emitter.buffered == 0


def test_emission_buffers_when_no_sink_exists_yet() -> None:
    """A subsystem built before Observability still emits (S1/S2 precede S3)."""
    emitter = SignalEmitter(source_identity="security_gateway")
    emitter.emit(SignalType.EVENT, "authentication.failed", "tenant-alpha")
    assert emitter.buffered == 1
    assert emitter.emitted == 1


def test_attaching_a_sink_drains_the_backlog() -> None:
    emitter = SignalEmitter(source_identity="security_gateway")
    for index in range(3):
        emitter.emit(SignalType.METRIC, f"metric-{index}", "tenant-alpha", value=float(index))
    received: list[Signal] = []
    assert emitter.attach(received.append) == 3
    assert emitter.buffered == 0
    assert [s.name for s in received] == ["metric-0", "metric-1", "metric-2"]


def test_a_failing_sink_never_surfaces_in_the_operational_path() -> None:
    """16.4 — observability reads the system; it does not steer it."""

    def explode(_signal: Signal) -> None:
        raise RuntimeError("observability is down")

    emitter = SignalEmitter(source_identity="tool_gateway", sink=explode)
    emitter.emit(SignalType.METRIC, "invocation.latency_ms", "tenant-alpha", value=12.0)
    assert emitter.sink_failures == 1
    assert emitter.buffered == 1  # retained for a later drain, not lost


def test_buffer_drops_oldest_first_past_its_limit() -> None:
    """A prolonged Observability outage must not exhaust the emitter's memory."""
    emitter = SignalEmitter(source_identity="cost_manager", buffer_limit=3)
    for index in range(5):
        emitter.emit(SignalType.METRIC, f"m-{index}", "tenant-alpha", value=float(index))
    assert emitter.buffered == 3
    assert emitter.dropped == 2
    received: list[Signal] = []
    emitter.attach(received.append)
    assert [s.name for s in received] == ["m-2", "m-3", "m-4"]


def test_drain_without_a_sink_is_a_no_op() -> None:
    emitter = SignalEmitter(source_identity="x")
    emitter.emit(SignalType.METRIC, "m", "t")
    assert emitter.drain() == 0
    assert emitter.buffered == 1


def test_submit_accepts_a_fully_formed_signal() -> None:
    received: list[Signal] = []
    emitter = SignalEmitter(source_identity="governance_gateway", sink=received.append)
    signal = Signal(
        signal_type=SignalType.JOURNAL,
        name="policy.assessed",
        source_identity="governance_gateway",
        tenant_id="tenant-alpha",
        sensitivity=Sensitivity.RESTRICTED,
        authority=ConsumerAuthority.O4_AUDIT_SCOPED,
        lineage=("signal-parent",),
        confidence=0.8,
    )
    emitter.submit(signal)
    assert received[0].sensitivity == Sensitivity.RESTRICTED
    assert received[0].lineage == ("signal-parent",)
