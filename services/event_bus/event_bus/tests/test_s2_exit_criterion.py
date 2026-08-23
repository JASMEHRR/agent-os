"""Stage S2 exit criterion, plus replay and Panic participation.

Build Specification, Stage S2, Exit Criteria — quoted:

    "authenticated producers emit schema-validated events; at-least-once
    consumer groups function; causality holds; replay works; dead-lettering
    alerts fire."

The scenario below runs all five in one narrative against a real Security
Gateway, then asserts the Bus's own architectural constraints hold.
"""

from __future__ import annotations

from datetime import timedelta

import pydantic
import pytest

from event_bus import ProducerNotAuthorized, ReplayMode, RetryPolicy
from event_bus.bus import BusHaltedError

from .conftest import CONSUMER, PRODUCER, TENANT


def test_s2_exit_criterion(bus, gateway, producer_token, consumer_token, clock, alerts) -> None:
    # 1. Authenticated producers emit schema-validated events.
    ranked = bus.emit(
        producer_token,
        event_type="business.idea.ranked",
        payload={"idea_id": "idea-1", "rank": 1},
        tenant_id=TENANT,
        source=PRODUCER,
        trace_id="trace-s2",
    )
    assert ranked.provenance.source_identity == PRODUCER
    assert bus.store.repository.get(ranked.event_id) == ranked  # durable before delivery

    # 2. At-least-once consumer groups function.
    bus.register_consumer_group(
        consumer_token,
        group_id="ranking-consumers",
        tenant_id=TENANT,
        patterns=("business.idea", "business.product"),
        members=("worker-1", "worker-2"),
    )
    deliveries = bus.consume("ranking-consumers")
    assert len(deliveries) == 1
    assert deliveries[0].published.event_id == ranked.event_id
    bus.acknowledge("ranking-consumers", ranked.event_id)
    assert bus.deliveries.is_acknowledged("ranking-consumers", ranked.event_id)

    # 3. Causality holds: an effect names its cause and carries its correlation.
    launched = bus.emit(
        producer_token,
        event_type="business.product.launched",
        payload={"product_id": "product-1"},
        tenant_id=TENANT,
        source=PRODUCER,
        trace_id="trace-s2",
        causation_id=ranked.event_id,
    )
    assert bus.causality.happens_before(ranked.event_id, launched.event_id)
    assert launched.provenance.correlation_id == "trace-s2"

    # 4. Replay works, in a sandbox, without mutating business state.
    sandbox = bus.request_replay(
        consumer_token,
        mode=ReplayMode.FORENSIC,
        requested_by=CONSUMER,
        tenant_id=TENANT,
        correlation_id="trace-s2",
    )
    assert len(sandbox) == 2
    assert sandbox.all_tagged
    assert all(event.event.metadata["replay"] is True for event in sandbox.events)
    # The live events are untouched, and no delivery bookkeeping moved.
    assert bus.store.get(ranked.event_id).replay is False
    assert bus.deliveries.in_flight() == []

    # 5. Dead-lettering alerts fire.
    bus.register_consumer_group(
        consumer_token,
        group_id="fragile-consumers",
        tenant_id=TENANT,
        patterns=("business.product",),
        members=("worker-x",),
        retry_policy=RetryPolicy(max_attempts=2),
    )
    bus.consume("fragile-consumers")
    bus.signal_failure("fragile-consumers", launched.event_id, "handler exploded")
    clock.advance(timedelta(minutes=1))
    bus.consume("fragile-consumers")
    dead = bus.signal_failure("fragile-consumers", launched.event_id, "handler exploded again")
    assert dead.attempts == 2
    assert alerts.of_kind("dead_letter")
    assert bus.query_dead_letters(group_id="fragile-consumers")

    # The whole run is visible in Stream Health, with no sequence gaps.
    health = bus.health()
    assert health["admission"]["admitted"] == 2
    assert health["delivery"]["acknowledged"] == 1
    assert health["dead_letters"]["depth"] == 1
    assert health["gaps"] == []


def test_replay_never_reaches_a_live_consumer_group(bus, producer_token, consumer_token) -> None:
    """08 rule 11 — replay does not mutate live business state."""
    published = bus.emit(
        producer_token,
        event_type="business.idea.ranked",
        payload={"idea_id": "i", "rank": 1},
        tenant_id=TENANT,
        source=PRODUCER,
        trace_id="t",
    )
    bus.register_consumer_group(
        consumer_token,
        group_id="live",
        tenant_id=TENANT,
        patterns=("business.idea",),
        members=("w",),
    )
    bus.consume("live")
    bus.acknowledge("live", published.event_id)
    before = bus.health()["delivery"]
    bus.request_replay(
        consumer_token,
        mode=ReplayMode.RECOVERY,
        requested_by=CONSUMER,
        tenant_id=TENANT,
        stream=published.stream,
    )
    assert bus.health()["delivery"] == before


def test_replay_requires_authorization(bus, gateway, producer_token) -> None:
    token, _ = gateway.authenticate(
        PRODUCER,
        f"cred-{PRODUCER}",
        "hash-producer",
        __import__("security_gateway", fromlist=["PrincipalType"]).PrincipalType.SERVICE,
    )
    with pytest.raises(ProducerNotAuthorized):
        bus.request_replay(token, mode=ReplayMode.FORENSIC, requested_by=PRODUCER, tenant_id=TENANT, stream="x")


def test_replay_is_scoped_to_one_tenant(bus, producer_token, consumer_token) -> None:
    """Tenant isolation applies to replay exactly as it applies to delivery.

    Two independent barriers stand in the way, and the outer one fires first:
    the Trust Plane denies a cross-tenant replay outright, and even if it were
    permitted the engine only returns events belonging to the requested
    tenant.
    """
    published = bus.emit(
        producer_token,
        event_type="business.idea.ranked",
        payload={"idea_id": "i", "rank": 1},
        tenant_id=TENANT,
        source=PRODUCER,
        trace_id="t",
    )
    with pytest.raises(ProducerNotAuthorized):
        bus.request_replay(
            consumer_token,
            mode=ReplayMode.LEARNING,
            requested_by=CONSUMER,
            tenant_id="tenant-beta",
            stream=published.stream,
        )
    # The engine's own filter, exercised past the authorization barrier.
    sandbox = bus.replays.replay(
        mode=ReplayMode.LEARNING,
        requested_by=CONSUMER,
        tenant_id="tenant-beta",
        stream=published.stream,
    )
    assert len(sandbox) == 0


def test_replay_must_be_scoped(bus, consumer_token) -> None:
    from core.exceptions import ValidationError

    with pytest.raises(ValidationError, match="scoped by stream or correlation_id"):
        bus.request_replay(consumer_token, mode=ReplayMode.FORENSIC, requested_by=CONSUMER, tenant_id=TENANT)


def test_panic_halts_admission_and_delivery(bus, producer_token, consumer_token) -> None:
    bus.register_consumer_group(
        consumer_token, group_id="g", tenant_id=TENANT, patterns=("business.idea",), members=("w",)
    )
    elapsed = bus.panic.trigger()
    assert elapsed < 5.0
    with pytest.raises(BusHaltedError):
        bus.emit(
            producer_token,
            event_type="business.idea.ranked",
            payload={"idea_id": "i", "rank": 1},
            tenant_id=TENANT,
            source=PRODUCER,
            trace_id="t",
        )
    with pytest.raises(BusHaltedError):
        bus.consume("g")


def test_published_events_are_immutable(bus, producer_token) -> None:
    """08.14.2 — correction is by new event, never by mutation."""
    import dataclasses

    published = bus.emit(
        producer_token,
        event_type="business.idea.ranked",
        payload={"idea_id": "i", "rank": 1},
        tenant_id=TENANT,
        source=PRODUCER,
        trace_id="t",
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        published.sequence = 99
    with pytest.raises(pydantic.ValidationError):
        published.event.payload = {}


def test_bus_authorizes_nothing_of_its_own(bus) -> None:
    """21A §5.4.2 — the Bus is not a Gateway; it grants nothing.

    Every authorization decision is delegated to the Trust Plane. If the Bus
    grew its own permission model, this test would find the method.
    """
    forbidden = {"grant", "grant_permission", "authorize", "permit", "allow"}
    assert forbidden.isdisjoint(dir(bus))


def test_bus_depends_only_on_layer_0_trust_and_schemas() -> None:
    """21B §15.13 / §15.6 — no dependency edge outside the permitted set."""
    import pkgutil

    import event_bus

    permitted = {"kernel", "core", "persistence", "schema_registry", "security_gateway", "event_bus", "__future__"}
    offenders: list[tuple[str, str]] = []
    for module_info in pkgutil.iter_modules(event_bus.__path__):
        if module_info.name == "tests":
            continue
        module = __import__(f"event_bus.{module_info.name}", fromlist=["_"])
        source = module.__file__
        assert source is not None
        with open(source, encoding="utf-8") as handle:
            for line in handle:
                stripped = line.strip()
                if not stripped.startswith(("import ", "from ")):
                    continue
                target = stripped.split()[1].split(".")[0]
                if target in ("agent_runtime", "workflow_engine", "tool_gateway", "memory_gateway"):
                    offenders.append((module_info.name, target))
                assert target in permitted or not target.endswith("_gateway")
    assert offenders == []


def test_security_gateway_is_imported_in_exactly_one_module() -> None:
    """The S1 dependency edge stays visible in the adapter, not scattered."""
    import pathlib

    import event_bus

    root = pathlib.Path(event_bus.__path__[0])
    importers = [
        path.name
        for path in root.glob("*.py")
        if "security_gateway" in path.read_text(encoding="utf-8") and path.name != "__init__.py"
    ]
    assert importers == ["security_adapter.py"]
