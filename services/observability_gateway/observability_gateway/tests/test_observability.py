"""Observability Gateway, the ingestion half (16.7, 16.8, 21B §24).

The interpretive half built at Stage S10 is covered by
`test_interpretive_profile.py`; these tests remain the ingestion suite.

Stage S3 test list: "Every signal type is ingested, enriched, and journaled."
Plus the constraints that make this Gateway safe to depend on — it reads and
never steers, and its query surface authorizes like everything else.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from kernel.signals import Sensitivity, SignalEmitter, SignalType
from observability_gateway import (
    EnrichedSignal,
    ObservabilityGateway,
    QualityAnomaly,
    QualityAnomalyKind,
    QueryNotAuthorized,
    SignalState,
)
from security_gateway.enums import PrincipalStatus
from security_gateway.tokens import TokenRevokedError

from .conftest import HUMAN, OPERATOR, TENANT, make_signal

# ------------------------------------------------------------------ ingestion


@pytest.mark.parametrize("signal_type", list(SignalType))
def test_every_signal_type_is_ingested_enriched_and_journalled(
    observability: ObservabilityGateway, signal_type: SignalType
) -> None:
    """Stage S3 test list, verbatim."""
    signal = make_signal(
        name=f"{signal_type.value}.sample",
        signal_type=signal_type,
        value=1.0 if signal_type == SignalType.METRIC else None,
    )
    enriched = observability.ingest(signal)
    assert isinstance(enriched, EnrichedSignal)
    assert enriched.state == SignalState.ENRICHED
    assert enriched.scope == (f"tenant:{TENANT}",)
    assert observability.journal.verify_chain()
    assert len(observability.journal) == 1


def test_enrichment_adds_context_without_editing_the_signal(observability: ObservabilityGateway) -> None:
    signal = make_signal(business_id="biz-1", workspace_id="ws-1")
    enriched = observability.ingest(signal)
    assert isinstance(enriched, EnrichedSignal)
    assert enriched.signal is signal  # the emitter's assertion is preserved verbatim
    assert enriched.scope == (f"tenant:{TENANT}", "business:biz-1", "workspace:ws-1")
    assert enriched.sequence == 0


def test_ingest_lag_is_measured(observability: ObservabilityGateway, clock) -> None:
    signal = make_signal(timestamp=clock.now)
    clock.advance(timedelta(seconds=3))
    enriched = observability.ingest(signal)
    assert isinstance(enriched, EnrichedSignal)
    assert enriched.ingest_lag_seconds == pytest.approx(3.0)


def test_a_metric_without_a_value_is_a_quality_anomaly(observability: ObservabilityGateway) -> None:
    anomaly = observability.ingest(make_signal(signal_type=SignalType.METRIC, value=None))
    assert isinstance(anomaly, QualityAnomaly)
    assert anomaly.kind == QualityAnomalyKind.SCHEMA


def test_a_duplicate_signal_is_rejected(observability: ObservabilityGateway) -> None:
    signal = make_signal()
    observability.ingest(signal)
    anomaly = observability.ingest(signal)
    assert isinstance(anomaly, QualityAnomaly)
    assert anomaly.kind == QualityAnomalyKind.DUPLICATE


def test_out_of_range_confidence_is_rejected(observability: ObservabilityGateway) -> None:
    anomaly = observability.ingest(make_signal(confidence=1.5))
    assert isinstance(anomaly, QualityAnomaly)
    assert anomaly.kind == QualityAnomalyKind.SCHEMA


def test_cardinality_explosion_is_caught(observability: ObservabilityGateway) -> None:
    observability.ingest_engine.cardinality_limit = 3
    for index in range(3):
        observability.ingest(make_signal(name=f"metric.{index}"))
    anomaly = observability.ingest(make_signal(name="metric.unbounded-id-4"))
    assert isinstance(anomaly, QualityAnomaly)
    assert anomaly.kind == QualityAnomalyKind.CARDINALITY


def test_a_rejected_signal_is_recorded_not_discarded(observability: ObservabilityGateway) -> None:
    """16.7.8 — a silently dropped signal makes its own coverage gap invisible."""
    observability.ingest(make_signal(signal_type=SignalType.METRIC, value=None))
    assert len(observability.ingest_engine.anomalies) == 1
    assert len(observability.journal) == 1
    assert observability.health()["anomalies"]["total"] == 1


def test_rejection_never_raises_into_the_emitting_subsystem(observability: ObservabilityGateway) -> None:
    """16.4 — observability reads the system; it does not steer it."""
    emitter = SignalEmitter(source_identity="tool_gateway", sink=observability.sink_for("tool_gateway"))
    # A metric with no value fails validation; the emitter must not notice.
    emitter.submit(make_signal(source="tool_gateway", signal_type=SignalType.METRIC, value=None))
    assert emitter.sink_failures == 0
    assert emitter.buffered == 0


# ---------------------------------------------------------- emitter wiring


def test_a_subsystem_built_before_observability_drains_on_attach(observability: ObservabilityGateway) -> None:
    """S1 and S2 precede S3; their buffered signals must survive to arrive."""
    emitter = SignalEmitter(source_identity="security_gateway")
    for index in range(3):
        emitter.emit(SignalType.METRIC, f"authorization.decision.{index}", TENANT, value=float(index))
    assert emitter.buffered == 3
    assert emitter.attach(observability.sink_for("security_gateway")) == 3
    assert observability.ingest_engine.ingested_count == 3


# -------------------------------------------------------------------- query


def test_an_unauthenticated_query_is_rejected(observability: ObservabilityGateway) -> None:
    """21B §24.10 — there is no privileged observability bypass.

    An unusable token fails at authentication, before authorization is even
    reached; a valid token lacking the permission fails at authorization. Both
    barriers are exercised — see the sensitivity test below for the second.
    """
    from security_gateway.tokens import AuthenticationError

    observability.ingest(make_signal())
    with pytest.raises(AuthenticationError):
        observability.query("not.a.token", TENANT)


def test_authorized_query_returns_matching_signals(observability: ObservabilityGateway, operator_token: str) -> None:
    observability.ingest(make_signal(name="a", source="security_gateway"))
    observability.ingest(make_signal(name="b", source="event_bus"))
    assert len(observability.query(operator_token, TENANT)) == 2
    assert len(observability.query(operator_token, TENANT, source_identity="event_bus")) == 1
    assert len(observability.query(operator_token, TENANT, name="a")) == 1


def test_query_is_scoped_to_one_tenant(observability: ObservabilityGateway, operator_token: str) -> None:
    observability.ingest(make_signal(tenant_id=TENANT))
    observability.ingest(make_signal(tenant_id="tenant-beta"))
    assert len(observability.query(operator_token, TENANT)) == 1


def test_query_will_not_return_signals_above_the_authorized_sensitivity(
    observability: ObservabilityGateway, operator_token: str
) -> None:
    """16.13 — observability data carries its own confidentiality classification."""
    observability.ingest(make_signal(name="public", sensitivity=Sensitivity.PUBLIC))
    observability.ingest(make_signal(name="internal", sensitivity=Sensitivity.INTERNAL))
    observability.ingest(make_signal(name="restricted", sensitivity=Sensitivity.RESTRICTED))
    names = {s.signal.name for s in observability.query(operator_token, TENANT)}
    assert names == {"public", "internal"}


def test_a_more_sensitive_query_needs_a_more_specific_permission(
    observability: ObservabilityGateway, operator_token: str
) -> None:
    with pytest.raises(QueryNotAuthorized):
        observability.query(operator_token, TENANT, max_sensitivity=Sensitivity.SOVEREIGN)


def test_revoking_the_operator_closes_the_query_surface(
    observability: ObservabilityGateway, security, operator_token: str
) -> None:
    observability.ingest(make_signal())
    assert observability.query(operator_token, TENANT)
    security.change_principal_status(OPERATOR, PrincipalStatus.SUSPENDED, actor_id=HUMAN)
    with pytest.raises(TokenRevokedError):
        observability.query(operator_token, TENANT)


def test_query_filters_by_time(observability: ObservabilityGateway, operator_token: str, clock) -> None:
    observability.ingest(make_signal(name="early"))
    cutoff = clock.now + timedelta(seconds=1)
    clock.advance(timedelta(seconds=2))
    observability.ingest(make_signal(name="late"))
    names = {s.signal.name for s in observability.query(operator_token, TENANT, since=cutoff)}
    assert names == {"late"}


# ------------------------------------------------------- panic confirmation


def test_halt_confirmations_are_reported_against_the_five_second_bound(
    observability: ObservabilityGateway, clock
) -> None:
    """16.19 — Observability confirms halt completion; it does not cause it."""
    observability.panic_started()
    clock.advance(timedelta(seconds=1))
    observability.confirm_halt("agent_runtime")
    clock.advance(timedelta(seconds=2))
    observability.confirm_halt("workflow_engine")
    report = observability.panic_confirmation(("agent_runtime", "workflow_engine"))
    assert report["complete"] is True
    assert report["missing"] == []
    assert report["slowest_seconds"] == pytest.approx(3.0)


def test_a_late_confirmation_breaches_the_bound(observability: ObservabilityGateway, clock) -> None:
    observability.panic_started()
    clock.advance(timedelta(seconds=6))
    confirmation = observability.confirm_halt("agent_runtime")
    assert not confirmation.within_bound
    report = observability.panic_confirmation(("agent_runtime",))
    assert report["late"] == ["agent_runtime"]
    assert report["complete"] is False


def test_a_missing_confirmation_is_reported(observability: ObservabilityGateway) -> None:
    observability.panic_started()
    observability.confirm_halt("agent_runtime")
    report = observability.panic_confirmation(("agent_runtime", "tool_executor"))
    assert report["missing"] == ["tool_executor"]
    assert report["complete"] is False


# ---------------------------------------------------- constraints and health


def test_the_gateway_has_no_mutation_path_into_any_subsystem() -> None:
    """21B §24.14 — Observability may not write to, configure, or steer anything.

    A method with a mutating verb appearing on this surface would be exactly
    the hidden control channel §24.14 forbids.
    """
    forbidden = {
        "write",
        "configure",
        "set_config",
        "halt",
        "suspend",
        "revoke",
        "trigger",
        "stop",
        "restart",
        "steer",
    }
    surface = {name for name in dir(ObservabilityGateway) if not name.startswith("_")}
    assert forbidden.isdisjoint(surface)


def test_the_interpretive_profile_arrived_at_s10() -> None:
    """This module appears twice in the dependency graph by design.

    Until Stage S10 this test asserted the interpretive half was *absent* rather
    than stubbed, so nothing could depend on a hollow implementation. S10 built
    it, so the assertion inverts: the surface must now be present. Its own
    conformance tests live in `test_interpretive_profile.py`.
    """
    expected = {"correlate", "publish_slo", "record_sli", "raise_alert", "constitutional_health"}
    surface = {name for name in dir(ObservabilityGateway) if not name.startswith("_")}
    assert expected <= surface


def test_health_reports_ingestion_state_and_is_sovereign(observability: ObservabilityGateway) -> None:
    observability.ingest(make_signal(source="security_gateway"))
    observability.ingest(make_signal(source="event_bus", name="publication.latency_ms"))
    health = observability.health()
    assert health["profile"] == "full-interpretive"
    assert health["sensitivity"] == Sensitivity.SOVEREIGN.value
    assert health["ingested"] == 2
    assert health["by_source"] == {"security_gateway": 1, "event_bus": 1}
    assert health["journal_intact"] is True


def test_visibility_slo_is_met_for_promptly_ingested_signals(observability: ObservabilityGateway) -> None:
    for index in range(5):
        observability.ingest(make_signal(name=f"m{index}", value=float(index)))
    assert all(observability.meets_visibility_slo().values())


def test_visibility_slo_fails_when_ingest_lags(observability: ObservabilityGateway, clock) -> None:
    signal = make_signal(timestamp=clock.now)
    clock.advance(timedelta(seconds=30))
    observability.ingest(signal)
    assert observability.meets_visibility_slo()["metrics_p50"] is False


def test_security_gateway_is_imported_in_exactly_one_module() -> None:
    import pathlib

    import observability_gateway

    root = pathlib.Path(observability_gateway.__path__[0])
    # Scan import lines rather than raw text: `interpretive.py` names
    # `security_gateway` as the subject of a published SLO, which is data about
    # another subsystem rather than a dependency on one.
    importers = [
        path.name
        for path in root.glob("*.py")
        if path.name != "__init__.py"
        and any(
            line.strip().startswith(("import ", "from ")) and "security_gateway" in line
            for line in path.read_text(encoding="utf-8").splitlines()
        )
    ]
    assert importers == ["security_adapter.py"]


def test_signals_are_journalled_with_their_classification(observability: ObservabilityGateway) -> None:
    observability.ingest(make_signal(sensitivity=Sensitivity.CONFIDENTIAL))
    entry = observability.journal[0]
    assert entry.payload["sensitivity"] == Sensitivity.CONFIDENTIAL.value
    assert entry.payload["kind"] == "signal"


def test_journal_is_tamper_evident(observability: ObservabilityGateway) -> None:
    from dataclasses import replace

    from kernel.journal import JournalTamperError

    observability.ingest(make_signal())
    victim = observability.journal._entries[0]
    observability.journal._entries[0] = replace(victim, payload={**victim.payload, "value": 999})
    with pytest.raises(JournalTamperError):
        observability.journal.verify_chain()


def test_ingestion_does_not_block_on_a_slow_or_absent_consumer() -> None:
    """21B §24.4 — no operational path waits on Observability ingest."""
    emitter = SignalEmitter(source_identity="llm_router")
    started = datetime.now(UTC)
    for index in range(1000):
        emitter.emit(SignalType.METRIC, "inference.latency_ms", TENANT, value=float(index))
    assert (datetime.now(UTC) - started) < timedelta(seconds=1)
    assert emitter.emitted == 1000
