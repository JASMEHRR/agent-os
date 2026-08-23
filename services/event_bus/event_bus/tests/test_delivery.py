"""Delivery, consumer groups, routing, retry and dead-lettering (08.10, 08.17)."""

from __future__ import annotations

from datetime import timedelta

import pytest

from core.exceptions import NotFoundError, ValidationError
from event_bus import ProducerNotAuthorized, RetryPolicy
from event_bus.envelope import EventState

from .conftest import OTHER_TENANT, PRODUCER, TENANT


def _emit(bus, token, event_type="business.idea.ranked", payload=None, **kw):
    return bus.emit(
        token,
        event_type=event_type,
        payload=payload if payload is not None else {"idea_id": "idea-1", "rank": 3},
        tenant_id=kw.pop("tenant_id", TENANT),
        source=PRODUCER,
        trace_id=kw.pop("trace_id", "trace-1"),
        **kw,
    )


def _group(bus, consumer_token, group_id="group-a", patterns=("business.idea",), **kw):
    return bus.register_consumer_group(
        consumer_token,
        group_id=group_id,
        tenant_id=kw.pop("tenant_id", TENANT),
        patterns=patterns,
        members=kw.pop("members", ("worker-1", "worker-2")),
        **kw,
    )


# ------------------------------------------------------------- registration


def test_group_registration_requires_subscription_authorization(bus, consumer_token) -> None:
    with pytest.raises(ProducerNotAuthorized):
        _group(bus, consumer_token, patterns=("agent.execution",))


def test_group_must_declare_members_and_patterns(bus, consumer_token) -> None:
    with pytest.raises(ValidationError):
        _group(bus, consumer_token, members=())


def test_duplicate_group_registration_is_rejected(bus, consumer_token) -> None:
    _group(bus, consumer_token)
    with pytest.raises(ValidationError, match="already registered"):
        _group(bus, consumer_token)


# ------------------------------------------------------------------ routing


def test_routing_is_deterministic_and_prefix_based(bus, consumer_token, producer_token) -> None:
    group = _group(bus, consumer_token)
    published = _emit(bus, producer_token)
    assert bus.router.route(published) == [group]
    assert bus.router.route(published) == [group]


def test_non_matching_event_type_is_not_routed(bus, consumer_token, producer_token) -> None:
    _group(bus, consumer_token, patterns=("business.product",))
    published = _emit(bus, producer_token)
    assert bus.router.route(published) == []


def test_tenant_isolation_is_enforced_at_the_routing_layer(bus, consumer_token, producer_token) -> None:
    """21B §15.4 — enforcing at the consumer would mean the event already crossed."""
    group = _group(bus, consumer_token, group_id="beta-group")
    group.tenant_id = OTHER_TENANT  # simulate a group belonging to another tenant
    published = _emit(bus, producer_token)
    assert bus.router.route(published) == []


def test_routing_never_reads_the_payload(bus, consumer_token, producer_token) -> None:
    """08.17.1 — content-based routing is prohibited."""
    _group(bus, consumer_token)
    first = _emit(bus, producer_token, payload={"idea_id": "a", "rank": 1})
    second = _emit(bus, producer_token, payload={"idea_id": "b", "rank": 99})
    assert bus.router.route(first) == bus.router.route(second)


# ----------------------------------------------------------------- delivery


def test_each_event_goes_to_exactly_one_member_per_group(bus, consumer_token, producer_token) -> None:
    _group(bus, consumer_token)
    _emit(bus, producer_token)
    _emit(bus, producer_token)
    deliveries = bus.consume("group-a")
    assert len(deliveries) == 2
    assert {d.member_id for d in deliveries} == {"worker-1", "worker-2"}


def test_independent_groups_each_receive_their_own_copy(bus, consumer_token, producer_token) -> None:
    _group(bus, consumer_token, group_id="group-a")
    _group(bus, consumer_token, group_id="group-b")
    _emit(bus, producer_token)
    assert len(bus.consume("group-a")) == 1
    assert len(bus.consume("group-b")) == 1


def test_consumption_does_not_destroy_the_log(bus, consumer_token, producer_token) -> None:
    """08.6.2 — streams are durable logs, not queues."""
    _group(bus, consumer_token)
    published = _emit(bus, producer_token)
    bus.consume("group-a")
    assert bus.store.depth(published.stream) == 1
    assert bus.store.get(published.event_id) is not None


def test_positions_advance_so_events_are_not_redelivered_on_poll(bus, consumer_token, producer_token) -> None:
    _group(bus, consumer_token)
    _emit(bus, producer_token)
    assert len(bus.consume("group-a")) == 1
    assert bus.consume("group-a") == []


def test_acknowledgment_follows_processing(bus, consumer_token, producer_token) -> None:
    _group(bus, consumer_token)
    published = _emit(bus, producer_token)
    bus.consume("group-a")
    state = bus.acknowledge("group-a", published.event_id)
    assert state.state == EventState.ACKNOWLEDGED
    assert bus.deliveries.is_acknowledged("group-a", published.event_id)


def test_acknowledging_an_undelivered_event_is_an_error(bus, consumer_token, producer_token) -> None:
    _group(bus, consumer_token)
    published = _emit(bus, producer_token)
    with pytest.raises(NotFoundError):
        bus.acknowledge("group-a", published.event_id)


# -------------------------------------------------------- retry and dead-letter


def test_failure_schedules_a_backoff_retry(bus, consumer_token, producer_token, clock) -> None:
    _group(bus, consumer_token)
    published = _emit(bus, producer_token)
    bus.consume("group-a")
    state = bus.signal_failure("group-a", published.event_id, "handler raised")
    assert state.state == EventState.PENDING_RETRY
    assert state.next_attempt_at == clock.now + timedelta(seconds=1)
    assert bus.consume("group-a") == []  # backoff has not elapsed
    clock.advance(timedelta(seconds=2))
    assert len(bus.consume("group-a")) == 1


def test_backoff_is_exponential_and_capped(bus, consumer_token) -> None:
    policy = RetryPolicy(base_delay=timedelta(seconds=1), max_delay=timedelta(seconds=8))
    assert policy.delay_for(1) == timedelta(seconds=1)
    assert policy.delay_for(2) == timedelta(seconds=2)
    assert policy.delay_for(4) == timedelta(seconds=8)
    assert policy.delay_for(10) == timedelta(seconds=8)


def test_ten_failed_attempts_dead_letters_and_alerts(bus, consumer_token, producer_token, clock, alerts) -> None:
    """Stage S2 test list: after 10 failed attempts the event is dead-lettered and alerts."""
    _group(bus, consumer_token)
    published = _emit(bus, producer_token)
    bus.consume("group-a")
    for attempt in range(1, 10):
        outcome = bus.signal_failure("group-a", published.event_id, f"failure {attempt}")
        assert outcome.state == EventState.PENDING_RETRY
        clock.advance(timedelta(minutes=10))
        bus.consume("group-a")

    dead = bus.signal_failure("group-a", published.event_id, "failure 10")
    assert dead.attempts == 10
    assert dead.reason == "failure 10"
    assert bus.dead_letters.depth == 1
    assert alerts.of_kind("dead_letter")  # 08 rule 18 — never without an alert


def test_dead_letters_are_queryable_for_human_review(bus, consumer_token, producer_token, clock) -> None:
    _group(bus, consumer_token, retry_policy=RetryPolicy(max_attempts=1))
    published = _emit(bus, producer_token)
    bus.consume("group-a")
    bus.signal_failure("group-a", published.event_id, "poison payload")
    entries = bus.query_dead_letters(group_id="group-a")
    assert len(entries) == 1
    assert entries[0].published.event_id == published.event_id
    assert entries[0].reason == "poison payload"


def test_a_dead_lettered_event_stays_in_the_stream(bus, consumer_token, producer_token) -> None:
    """Quarantine removes it from delivery, never from the log (08.14.2)."""
    _group(bus, consumer_token, retry_policy=RetryPolicy(max_attempts=1))
    published = _emit(bus, producer_token)
    bus.consume("group-a")
    bus.signal_failure("group-a", published.event_id, "poison")
    assert bus.store.get(published.event_id) is not None
    assert bus.deliveries.in_flight("group-a") == []


def test_no_event_is_silently_lost(bus, consumer_token, producer_token) -> None:
    """21B §15.15 item 8 — every event is acknowledged, dead-lettered, or alerted."""
    _group(bus, consumer_token, retry_policy=RetryPolicy(max_attempts=1))
    acked = _emit(bus, producer_token, payload={"idea_id": "a", "rank": 1})
    doomed = _emit(bus, producer_token, payload={"idea_id": "b", "rank": 2})
    bus.consume("group-a")
    bus.acknowledge("group-a", acked.event_id)
    bus.signal_failure("group-a", doomed.event_id, "poison")
    assert bus.deliveries.is_acknowledged("group-a", acked.event_id)
    assert bus.query_dead_letters()[0].published.event_id == doomed.event_id
    assert bus.deliveries.in_flight() == []
