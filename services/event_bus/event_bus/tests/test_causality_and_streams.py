"""Causality, ordering, durability, gaps, backpressure and archival.

Covers 08.13 (causality and ordering), 08.14 (durability and immutability),
08.15.4 (retention), 08.17.4 (backpressure) and the Gap Detector of 21B §15.3.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta

import pytest

from event_bus import CausalityViolation, CriticalStreamShedError, DomainCategory
from event_bus.streams import SequenceGapError

from .conftest import PRODUCER, TENANT


def _emit(bus, token, event_type="business.idea.ranked", payload=None, **kw):
    return bus.emit(
        token,
        event_type=event_type,
        payload=payload if payload is not None else {"idea_id": "idea-1", "rank": 3},
        tenant_id=TENANT,
        source=PRODUCER,
        trace_id=kw.pop("trace_id", "trace-1"),
        **kw,
    )


# ---------------------------------------------------------------- causality


def test_causation_and_correlation_propagate(bus, producer_token) -> None:
    cause = _emit(bus, producer_token)
    effect = _emit(
        bus,
        producer_token,
        event_type="business.product.launched",
        payload={"product_id": "p-1"},
        causation_id=cause.event_id,
    )
    assert effect.provenance.causation_id == cause.event_id
    assert effect.provenance.correlation_id == cause.provenance.correlation_id
    assert bus.causality.happens_before(cause.event_id, effect.event_id)


def test_causation_naming_an_unknown_event_is_rejected(bus, producer_token) -> None:
    with pytest.raises(CausalityViolation, match="names no published event"):
        _emit(bus, producer_token, causation_id="event-that-never-was")


def test_a_dropped_correlation_id_breaks_the_chain_and_is_refused(bus, producer_token) -> None:
    """08.12.3 — the causal graph must be unbroken from trigger to effect."""
    cause = _emit(bus, producer_token)
    with pytest.raises(CausalityViolation, match="propagate the correlation ID"):
        _emit(bus, producer_token, causation_id=cause.event_id, trace_id="a-different-trace")


def test_happens_before_is_transitive(bus, producer_token) -> None:
    a = _emit(bus, producer_token)
    b = _emit(
        bus,
        producer_token,
        event_type="business.product.launched",
        payload={"product_id": "p"},
        causation_id=a.event_id,
    )
    c = _emit(
        bus, producer_token, event_type="system.service.healthy", payload={"service": "svc"}, causation_id=b.event_id
    )
    assert bus.causality.happens_before(a.event_id, c.event_id)
    assert bus.causality.ancestors(c.event_id) == [b.event_id, a.event_id]


def test_total_ordering_holds_within_a_stream(bus, producer_token) -> None:
    first = _emit(bus, producer_token)
    second = _emit(bus, producer_token, payload={"idea_id": "idea-2", "rank": 1})
    assert first.stream == second.stream
    assert (first.sequence, second.sequence) == (0, 1)
    assert bus.causality.happens_before(first.event_id, second.event_id)


def test_events_in_different_streams_are_causally_independent(bus, producer_token) -> None:
    """08.13.3 — no wall-clock ordering across streams without a causal link."""
    business = _emit(bus, producer_token)
    system = _emit(bus, producer_token, event_type="system.service.healthy", payload={"service": "svc"})
    assert business.stream != system.stream
    assert not bus.causality.happens_before(business.event_id, system.event_id)
    assert not bus.causality.happens_before(system.event_id, business.event_id)


def test_correlation_gathers_one_business_operation(bus, producer_token) -> None:
    a = _emit(bus, producer_token)
    _emit(
        bus,
        producer_token,
        event_type="business.product.launched",
        payload={"product_id": "p"},
        causation_id=a.event_id,
    )
    _emit(bus, producer_token, trace_id="unrelated-trace", payload={"idea_id": "x", "rank": 1})
    assert len(bus.causality.trace("trace-1")) == 2


# --------------------------------------------------------------- partitioning


def test_streams_partition_by_category_and_tenant(bus, producer_token) -> None:
    _emit(bus, producer_token)
    _emit(bus, producer_token, event_type="system.service.healthy", payload={"service": "svc"})
    assert sorted(bus.store.streams()) == [f"business.{TENANT}", f"system.{TENANT}"]


def test_sequence_is_per_stream_not_global(bus, producer_token) -> None:
    _emit(bus, producer_token)
    system = _emit(bus, producer_token, event_type="system.service.healthy", payload={"service": "svc"})
    assert system.sequence == 0


# ------------------------------------------------------- durability and gaps


def test_durability_precedes_delivery(bus, producer_token) -> None:
    """08.14.1 — an event is on disk before anything can consume it."""
    published = _emit(bus, producer_token)
    assert bus.store.repository.get(published.event_id) == published


def test_gap_detector_finds_a_sequence_discontinuity(bus, producer_token) -> None:
    _emit(bus, producer_token)
    second = _emit(bus, producer_token, payload={"idea_id": "idea-2", "rank": 2})
    # Simulate a lost write by renumbering the second entry in place.
    bus.store._streams[second.stream][1] = replace(second, sequence=5)
    with pytest.raises(SequenceGapError):
        bus.gaps.check(second.stream)
    assert bus.health()["gaps"]


def test_no_gaps_on_a_healthy_stream(bus, producer_token) -> None:
    for index in range(5):
        _emit(bus, producer_token, payload={"idea_id": f"idea-{index}", "rank": index})
    assert bus.gaps.scan() == []


# --------------------------------------------------------------- backpressure


def test_critical_categories_are_never_shed(bus, producer_token) -> None:
    """08 rule 7 — command, audit and business events are never shed."""
    for event_type, payload in (
        ("command.panic.invoked", {"invoked_by": "human"}),
        ("audit.tool.executed", {"tool": "t"}),
        ("business.idea.ranked", {"idea_id": "i", "rank": 1}),
    ):
        published = _emit(bus, producer_token, event_type=event_type, payload=payload)
        assert published.is_critical
        with pytest.raises(CriticalStreamShedError):
            bus.backpressure.shed(published)


def test_non_critical_events_may_be_shed(bus, producer_token, alerts) -> None:
    published = _emit(bus, producer_token, event_type="system.service.healthy", payload={"service": "svc"})
    assert not published.is_critical
    bus.backpressure.shed(published)
    assert bus.backpressure.shed_count == 1
    assert alerts.of_kind("event_shed")


def test_lag_alerts_and_throttles_at_their_thresholds(bus, alerts) -> None:
    bus.backpressure.observe_lag("group-a", lag=bus.backpressure.lag_alert_threshold)
    assert alerts.of_kind("consumer_lag")
    bus.backpressure.observe_lag("group-a", lag=bus.backpressure.throttle_threshold)
    assert bus.backpressure.is_throttled("group-a")


def test_lag_is_reported_per_group(bus, consumer_token, producer_token) -> None:
    bus.register_consumer_group(
        consumer_token,
        group_id="group-a",
        tenant_id=TENANT,
        patterns=("business.idea",),
        members=("worker-1",),
    )
    _emit(bus, producer_token)
    _emit(bus, producer_token, payload={"idea_id": "i2", "rank": 2})
    assert bus.lag_for("group-a") == 2
    bus.consume("group-a")
    assert bus.lag_for("group-a") == 0


# -------------------------------------------------------- retention schedule


def test_retention_schedule_matches_08_15_4(bus, producer_token) -> None:
    business = _emit(bus, producer_token)
    assert business.retention.operational == timedelta(days=30)
    assert business.retention.audit == timedelta(days=2555)
    system = _emit(bus, producer_token, event_type="system.service.healthy", payload={"service": "svc"})
    assert system.retention.operational == timedelta(days=7)
    audit = _emit(bus, producer_token, event_type="audit.tool.executed", payload={"tool": "t"})
    assert audit.retention.operational == timedelta(days=2555)


def test_audit_events_are_not_purgeable_before_seven_years(bus, producer_token, clock) -> None:
    audit = _emit(bus, producer_token, event_type="audit.tool.executed", payload={"tool": "t"})
    clock.advance(timedelta(days=2554))
    assert not bus.archive.purgeable(audit)
    clock.advance(timedelta(days=2))
    assert bus.archive.purgeable(audit)


def test_archival_is_due_only_after_operational_retention(bus, producer_token, clock) -> None:
    published = _emit(bus, producer_token)
    assert bus.archive.due_for_archival([published]) == []
    clock.advance(timedelta(days=31))
    assert bus.archive.due_for_archival([published]) == [published]
    bus.archive.archive(published)
    assert bus.archive.is_archived(published.event_id)
    assert bus.archive.due_for_archival([published]) == []


def test_category_derivation_covers_all_six(bus) -> None:
    for category in DomainCategory:
        assert DomainCategory.of(f"{category.value}.thing.happened") == category
