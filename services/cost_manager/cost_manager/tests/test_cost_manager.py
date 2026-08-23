"""Cost Manager — budget levels, enforcement, attribution, circuit breakers.

Stage S3 test list: "budget checks correctly gate pre-flight and post-flight
operations at the four levels (Green <50%, Yellow 50-80%, Orange 80-95% forces
model downgrade, Red >95% halts operations and escalates to human); circuit
breakers trip on repeated external-call failure."
"""

from __future__ import annotations

from datetime import timedelta

import pytest

from core.constants import BudgetLevel
from core.exceptions import NotFoundError, ValidationError
from cost_manager import (
    ACTION_BY_LEVEL,
    BreakerState,
    BudgetExceeded,
    BudgetScope,
    CircuitOpenError,
    CostManager,
    ScopeKind,
)
from kernel.lifecycle import InvalidTransitionError

from .conftest import AGENT, AGENT_SCOPE, TENANT, names

# ------------------------------------------------------------- budget levels


def _spend(costs: CostManager, amount: float, operation: str = "inference") -> None:
    costs.record(AGENT_SCOPE, TENANT, amount, operation, AGENT)


@pytest.mark.parametrize(
    ("spent", "level"),
    [
        (0.0, BudgetLevel.GREEN),
        (49.0, BudgetLevel.GREEN),
        (50.0, BudgetLevel.YELLOW),
        (79.0, BudgetLevel.YELLOW),
        (80.0, BudgetLevel.ORANGE),
        (94.0, BudgetLevel.ORANGE),
        (95.0, BudgetLevel.RED),
        (120.0, BudgetLevel.RED),
    ],
)
def test_the_four_levels_of_02_3_9(costs: CostManager, spent: float, level: BudgetLevel) -> None:
    costs.allocate(AGENT_SCOPE, TENANT, limit=100.0)
    if spent:
        _spend(costs, spent)
    verdict = costs.check(AGENT_SCOPE, TENANT)
    assert verdict.level == level
    assert verdict.action == ACTION_BY_LEVEL[level]


def test_green_proceeds_untouched(costs: CostManager) -> None:
    costs.allocate(AGENT_SCOPE, TENANT, limit=100.0)
    verdict = costs.check(AGENT_SCOPE, TENANT, estimated_cost=1.0)
    assert verdict.may_proceed
    assert not verdict.downgrade_required
    assert not verdict.halted


def test_yellow_warns_and_alerts(costs: CostManager, signals) -> None:
    costs.allocate(AGENT_SCOPE, TENANT, limit=100.0)
    _spend(costs, 60.0)
    verdict = costs.check(AGENT_SCOPE, TENANT)
    assert verdict.level == BudgetLevel.YELLOW
    assert verdict.may_proceed
    assert "cost.budget.threshold_breached" in names(signals)


def test_orange_forces_a_model_downgrade(costs: CostManager) -> None:
    """02.3.9 — Orange enforces downgrading; it does not suggest it."""
    costs.allocate(AGENT_SCOPE, TENANT, limit=100.0)
    _spend(costs, 85.0)
    verdict = costs.check(AGENT_SCOPE, TENANT)
    assert verdict.level == BudgetLevel.ORANGE
    assert verdict.downgrade_required
    assert verdict.may_proceed  # downgraded, but it proceeds
    assert verdict.action == "proceed_downgraded"


def test_red_halts_and_escalates_to_a_human(costs: CostManager, escalations) -> None:
    costs.allocate(AGENT_SCOPE, TENANT, limit=100.0)
    _spend(costs, 96.0)
    verdict = costs.check(AGENT_SCOPE, TENANT)
    assert verdict.level == BudgetLevel.RED
    assert verdict.halted
    assert not verdict.may_proceed
    assert escalations.of_kind("budget_red")


def test_red_cannot_be_waived(costs: CostManager) -> None:
    """There is no flag that lets an operation past 95% without a human."""
    costs.allocate(AGENT_SCOPE, TENANT, limit=100.0)
    _spend(costs, 96.0)
    with pytest.raises(BudgetExceeded):
        costs.enforce(AGENT_SCOPE, TENANT, estimated_cost=0.01)
    surface = {name for name in dir(CostManager) if not name.startswith("_")}
    assert {"override", "waive", "force", "bypass"}.isdisjoint(surface)


# --------------------------------------------------------- pre and post flight


def test_preflight_projects_the_estimate_before_spending(costs: CostManager) -> None:
    """A large estimate can push a Green budget into Red before a cent is spent."""
    costs.allocate(AGENT_SCOPE, TENANT, limit=100.0)
    _spend(costs, 40.0)
    assert costs.check(AGENT_SCOPE, TENANT).level == BudgetLevel.GREEN
    verdict = costs.check(AGENT_SCOPE, TENANT, estimated_cost=60.0)
    assert verdict.level == BudgetLevel.RED
    assert verdict.halted


def test_postflight_records_the_actual_not_the_estimate(costs: CostManager) -> None:
    costs.allocate(AGENT_SCOPE, TENANT, limit=100.0)
    costs.check(AGENT_SCOPE, TENANT, estimated_cost=50.0)
    verdict = costs.record(AGENT_SCOPE, TENANT, 5.0, "inference", AGENT)
    assert costs.ledger.budget_for(AGENT_SCOPE).spent == 5.0
    assert verdict.level == BudgetLevel.GREEN


def test_an_unallocated_scope_is_unmetered_and_says_so(costs: CostManager, signals) -> None:
    """The Cost Manager will not invent a limit it was never given."""
    verdict = costs.check(AGENT_SCOPE, TENANT, estimated_cost=1_000_000.0)
    assert verdict.may_proceed
    assert verdict.remaining == float("inf")
    assert "no budget allocated" in verdict.reason
    assert "cost.budget.unallocated" in names(signals)


def test_spend_is_still_recorded_for_an_unallocated_scope(costs: CostManager) -> None:
    costs.record(AGENT_SCOPE, TENANT, 12.0, "inference", AGENT)
    assert costs.ledger.total(AGENT_SCOPE) == 12.0


def test_reallocating_resets_the_alert_state(costs: CostManager, signals) -> None:
    costs.allocate(AGENT_SCOPE, TENANT, limit=100.0)
    _spend(costs, 60.0)
    costs.check(AGENT_SCOPE, TENANT)
    costs.allocate(AGENT_SCOPE, TENANT, limit=1000.0)
    assert costs.check(AGENT_SCOPE, TENANT).level == BudgetLevel.GREEN


def test_alerts_are_not_repeated_at_the_same_level(costs: CostManager, signals) -> None:
    costs.allocate(AGENT_SCOPE, TENANT, limit=100.0)
    _spend(costs, 60.0)
    for _ in range(5):
        costs.check(AGENT_SCOPE, TENANT)
    assert names(signals).count("cost.budget.threshold_breached") == 1


# ------------------------------------------------------------------- ledger


def test_the_ledger_is_append_only_and_corrections_are_new_entries(costs: CostManager) -> None:
    costs.allocate(AGENT_SCOPE, TENANT, limit=100.0)
    entry = costs.ledger.record(AGENT_SCOPE, TENANT, 20.0, "inference", AGENT)
    correction = costs.correct(entry, -5.0, "overestimate")
    assert costs.ledger.entry_count == 2
    assert correction.corrects == entry.sequence
    assert costs.ledger.budget_for(AGENT_SCOPE).spent == 15.0


def test_a_negative_amount_must_reference_what_it_corrects(costs: CostManager) -> None:
    with pytest.raises(ValidationError, match="must reference the entry it corrects"):
        costs.ledger.record(AGENT_SCOPE, TENANT, -5.0, "refund", AGENT)


def test_attribution_by_operation_agent_and_tenant(costs: CostManager) -> None:
    costs.record(AGENT_SCOPE, TENANT, 3.0, "inference", AGENT)
    costs.record(AGENT_SCOPE, TENANT, 2.0, "inference", AGENT)
    costs.record(AGENT_SCOPE, TENANT, 1.0, "embedding", AGENT)
    attribution = costs.attribution(scope=AGENT_SCOPE)
    assert attribution["total"] == 6.0
    assert attribution["by_operation"] == {"inference": 5.0, "embedding": 1.0}
    assert costs.attribution(principal_id="somebody-else")["total"] == 0.0


def test_every_scope_kind_is_addressable(costs: CostManager) -> None:
    for kind in ScopeKind:
        scope = BudgetScope(kind=kind, identifier=f"{kind.value}-1")
        costs.allocate(scope, TENANT, limit=10.0)
        assert costs.ledger.budget_for(scope).limit == 10.0


def test_a_negative_limit_is_refused(costs: CostManager) -> None:
    with pytest.raises(ValidationError):
        costs.allocate(AGENT_SCOPE, TENANT, limit=-1.0)


def test_unknown_budget_lookup_raises(costs: CostManager) -> None:
    with pytest.raises(NotFoundError):
        costs.ledger.budget_for(BudgetScope(kind=ScopeKind.TENANT, identifier="nobody"))


# --------------------------------------------------------- circuit breakers


def test_breaker_trips_on_repeated_external_call_failure(costs: CostManager, escalations) -> None:
    """Stage S3 test list: circuit breakers trip on repeated external-call failure."""
    costs.allocate(AGENT_SCOPE, TENANT, limit=1000.0)
    for _ in range(5):
        costs.record(AGENT_SCOPE, TENANT, 1.0, "inference", AGENT, dependency="openai", succeeded=False)
    assert costs.breakers.breaker("openai").is_open
    assert costs.breakers.open_breakers() == ["openai"]
    assert escalations.of_kind("circuit_breaker_tripped")


def test_an_open_breaker_refuses_the_call_before_it_costs_anything(costs: CostManager) -> None:
    costs.trip("openai", TENANT, reason="upstream outage")
    with pytest.raises(CircuitOpenError):
        costs.check(AGENT_SCOPE, TENANT, estimated_cost=5.0, dependency="openai")


def test_success_resets_the_failure_count(costs: CostManager) -> None:
    for _ in range(4):
        costs.record(AGENT_SCOPE, TENANT, 1.0, "inference", AGENT, dependency="openai", succeeded=False)
    costs.record(AGENT_SCOPE, TENANT, 1.0, "inference", AGENT, dependency="openai", succeeded=True)
    assert costs.breakers.breaker("openai").consecutive_failures == 0
    assert not costs.breakers.breaker("openai").is_open


def test_cooldown_admits_one_probe_then_closes_on_success(costs: CostManager, clock) -> None:
    costs.trip("openai", TENANT, reason="outage")
    clock.advance(timedelta(seconds=61))
    costs.check(AGENT_SCOPE, TENANT, dependency="openai")  # cooldown elapsed: probe allowed
    assert costs.breakers.breaker("openai").state == BreakerState.HALF_OPEN
    costs.record(AGENT_SCOPE, TENANT, 1.0, "inference", AGENT, dependency="openai", succeeded=True)
    assert costs.breakers.breaker("openai").state == BreakerState.CLOSED


def test_a_failed_probe_reopens_with_a_fresh_cooldown(costs: CostManager, clock) -> None:
    costs.trip("openai", TENANT, reason="outage")
    clock.advance(timedelta(seconds=61))
    costs.check(AGENT_SCOPE, TENANT, dependency="openai")
    costs.record(AGENT_SCOPE, TENANT, 1.0, "inference", AGENT, dependency="openai", succeeded=False)
    breaker = costs.breakers.breaker("openai")
    assert breaker.state == BreakerState.OPEN
    assert breaker.trip_count == 2
    with pytest.raises(CircuitOpenError):
        costs.check(AGENT_SCOPE, TENANT, dependency="openai")


def test_manual_reset_closes_the_breaker(costs: CostManager) -> None:
    costs.trip("openai", TENANT, reason="outage")
    costs.reset("openai", TENANT)
    assert costs.breakers.breaker("openai").state == BreakerState.CLOSED
    costs.check(AGENT_SCOPE, TENANT, dependency="openai")  # no longer refused


def test_breaker_transitions_are_guarded(costs: CostManager) -> None:
    """Closed -> Half-Open is not an edge; only Open -> Half-Open is."""
    breaker = costs.breakers.breaker("openai")
    with pytest.raises(InvalidTransitionError):
        breaker._transition(BreakerState.HALF_OPEN)


# ------------------------------------------------------- signals and health


def test_every_check_emits_a_utilization_metric(costs: CostManager, signals) -> None:
    costs.allocate(AGENT_SCOPE, TENANT, limit=100.0)
    costs.check(AGENT_SCOPE, TENANT)
    assert "cost.budget.utilization" in names(signals)


def test_health_reports_budgets_breakers_and_spend(costs: CostManager) -> None:
    costs.allocate(AGENT_SCOPE, TENANT, limit=100.0)
    _spend(costs, 85.0)
    costs.check(AGENT_SCOPE, TENANT)
    costs.trip("openai", TENANT, reason="outage")
    health = costs.health()
    assert health["budgets"] == 1
    assert health["by_level"] == {BudgetLevel.ORANGE.value: 1}
    assert health["total_spend"] == 85.0
    assert health["open_breakers"] == ["openai"]
    assert health["downgrades"] >= 1


def test_signals_buffer_when_observability_is_absent(clock, escalations) -> None:
    """A Cost Manager wired before Observability still records everything."""
    from kernel.signals import SignalEmitter

    emitter = SignalEmitter(source_identity="cost_manager")
    manager = CostManager(signals=emitter, escalate=escalations, now=clock)
    manager.allocate(AGENT_SCOPE, TENANT, limit=100.0)
    manager.check(AGENT_SCOPE, TENANT)
    assert emitter.buffered >= 2
    assert emitter.sink_failures == 0
