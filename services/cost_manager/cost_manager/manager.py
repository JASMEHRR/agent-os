"""Cost Manager (realizes 02.3.9).

"Prevents runaway costs. Enforces the 'Free API First' and 'Cost Transparency'
principles." Four budget levels, each with a mandated action:

| Level  | Action                              | Trigger        |
|--------|-------------------------------------|----------------|
| Green  | Normal operation                    | below 50%      |
| Yellow | Warning logged, alert sent          | 50-80%         |
| Orange | Model downgrading enforced          | 80-95%         |
| Red    | Operations halted, human escalation | above 95%      |

Two properties are structural rather than configurable. **Red halts** — there
is no flag that lets an operation proceed past 95% without a human, because
02.3.9 says operations are halted and escalated, and a budget ceiling that
can be waived by the thing hitting it is not a ceiling. And **Orange forces a
downgrade** rather than suggesting one: the check returns the downgrade as
part of its verdict, so a caller that ignores it is visibly ignoring a
decision rather than quietly skipping an optional hint.

Pre-flight and post-flight are separate calls on purpose. Pre-flight reserves
against an *estimate* and can refuse; post-flight records what was actually
spent, which is usually different. Recording only actuals would let an
unbounded operation start; refusing only on estimates would let the ledger
drift from reality.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from core.constants import BudgetLevel
from core.exceptions import AgentOSError
from cost_manager.breakers import CircuitBreakerRegistry, CircuitOpenError
from cost_manager.ledger import BudgetScope, CostLedger, LedgerEntry, ScopeKind
from kernel.signals import SignalEmitter, SignalType

#: Actions mandated per level by the 02.3.9 Budget Levels table.
ACTION_BY_LEVEL: Mapping[BudgetLevel, str] = {
    BudgetLevel.GREEN: "proceed",
    BudgetLevel.YELLOW: "proceed_with_warning",
    BudgetLevel.ORANGE: "proceed_downgraded",
    BudgetLevel.RED: "halt_and_escalate",
}


class BudgetExceeded(AgentOSError):
    """Red level, or an operation whose estimate exceeds what remains."""

    def __init__(self, scope: BudgetScope, detail: str):
        super().__init__(f"budget enforcement blocked {scope}: {detail}")
        self.scope = scope


@dataclass(frozen=True)
class BudgetVerdict:
    """The result of a pre-flight or post-flight check."""

    scope: BudgetScope
    level: BudgetLevel
    action: str
    utilization: float
    remaining: float
    estimated_cost: float
    #: True at Orange and above — the caller must use a cheaper model.
    downgrade_required: bool
    #: True at Red — the operation does not proceed and a human is escalated to.
    halted: bool
    reason: str

    @property
    def may_proceed(self) -> bool:
        return not self.halted


@dataclass
class CostManager:
    """Budget enforcement, cost attribution, alerting, circuit breakers.

    `escalate` is the human-escalation path Red requires. It is injected
    rather than assumed: at Stage S3 no Human Interface exists (that is S8),
    so the deployment wires it to whatever alerting channel it has, and the
    Cost Manager does not pretend to know how a human is reached.
    """

    signals: SignalEmitter
    escalate: Callable[[str, dict[str, Any]], None]
    now: Callable[[], datetime] = field(default=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        self.ledger = CostLedger(now=self.now)
        self.breakers = CircuitBreakerRegistry(now=self.now)
        self._alerted_levels: dict[str, BudgetLevel] = {}
        self._halts = 0
        self._downgrades = 0

    # ------------------------------------------------------------ Allocation

    def allocate(self, scope: BudgetScope, tenant_id: str, limit: float) -> None:
        """Allocates a budget. Emits a signal so allocations are observable."""
        budget = self.ledger.allocate(scope, tenant_id, limit)
        self._alerted_levels.pop(str(scope), None)
        self.signals.emit(
            SignalType.EVENT,
            "cost.budget.allocated",
            tenant_id,
            value=limit,
            scope=str(scope),
            period_start=budget.period_start.isoformat(),
        )

    # ------------------------------------------------------------ Pre-flight

    def check(
        self,
        scope: BudgetScope,
        tenant_id: str,
        estimated_cost: float = 0.0,
        dependency: str | None = None,
    ) -> BudgetVerdict:
        """**Budget Check** — pre-flight gate, consumed by LLM Router and Tool Executor.

        Raises `CircuitOpenError` before any budget arithmetic when the named
        dependency's breaker is open: refusing early is the whole point of a
        cost-based breaker.
        """
        if dependency is not None:
            self.breakers.breaker(dependency).check()

        if not self.ledger.has_budget(scope):
            # An unbudgeted scope is unmetered, not unlimited-by-policy. The
            # Cost Manager will not invent a limit it was never given, but it
            # does say so out loud rather than returning a confident Green.
            self.signals.emit(
                SignalType.EVENT,
                "cost.budget.unallocated",
                tenant_id,
                scope=str(scope),
                estimated_cost=estimated_cost,
            )
            return BudgetVerdict(
                scope=scope,
                level=BudgetLevel.GREEN,
                action=ACTION_BY_LEVEL[BudgetLevel.GREEN],
                utilization=0.0,
                remaining=float("inf"),
                estimated_cost=estimated_cost,
                downgrade_required=False,
                halted=False,
                reason="no budget allocated for this scope; spend is unmetered and recorded only",
            )

        budget = self.ledger.budget_for(scope)
        projected = budget.spent + estimated_cost
        projected_level = BudgetLevel.from_utilization(projected / budget.limit if budget.limit > 0 else 1.0)
        verdict = self._verdict(scope, budget.utilization, budget.remaining, estimated_cost, projected_level)
        self._observe(verdict, tenant_id)
        return verdict

    def enforce(
        self,
        scope: BudgetScope,
        tenant_id: str,
        estimated_cost: float = 0.0,
        dependency: str | None = None,
    ) -> BudgetVerdict:
        """**Budget Enforcement** — like `check`, but Red raises instead of reporting.

        Callers that must not proceed past a ceiling use this; callers that
        want to make their own decision from the verdict use `check`.
        """
        verdict = self.check(scope, tenant_id, estimated_cost, dependency)
        if verdict.halted:
            raise BudgetExceeded(scope, verdict.reason)
        return verdict

    # ----------------------------------------------------------- Post-flight

    def record(
        self,
        scope: BudgetScope,
        tenant_id: str,
        actual_cost: float,
        operation: str,
        principal_id: str,
        dependency: str | None = None,
        succeeded: bool = True,
    ) -> BudgetVerdict:
        """**Post-flight** — records actual spend and re-evaluates the level.

        Also drives the circuit breaker: a failed external call is what a
        cost-based breaker counts, and counting it here means the breaker sees
        every call that actually happened rather than every call that was
        planned.
        """
        entry = self.ledger.record(scope, tenant_id, actual_cost, operation, principal_id)
        if dependency is not None:
            breaker = self.breakers.breaker(dependency)
            state = breaker.record_success() if succeeded else breaker.record_failure()
            if breaker.is_open:
                self.signals.emit(
                    SignalType.EVENT,
                    "cost.circuit_breaker.tripped",
                    tenant_id,
                    dependency=dependency,
                    consecutive_failures=breaker.consecutive_failures,
                    trip_count=breaker.trip_count,
                )
                self.escalate(
                    "circuit_breaker_tripped",
                    {"dependency": dependency, "scope": str(scope), "state": state.value},
                )

        self.signals.emit(
            SignalType.METRIC,
            "cost.operation.spend",
            tenant_id,
            value=actual_cost,
            scope=str(scope),
            operation=operation,
            principal_id=principal_id,
            sequence=entry.sequence,
        )
        return self.check(scope, tenant_id, estimated_cost=0.0)

    def correct(
        self,
        entry: LedgerEntry,
        amount: float,
        reason: str,
    ) -> LedgerEntry:
        """Unwinds an over-estimate or a refund without deleting the original."""
        return self.ledger.record(
            scope=entry.scope,
            tenant_id=entry.tenant_id,
            amount=amount,
            operation=f"correction:{reason}",
            principal_id=entry.principal_id,
            corrects=entry.sequence,
        )

    # ------------------------------------------------------ Circuit breakers

    def trip(self, dependency: str, tenant_id: str, reason: str) -> None:
        """Manual trip, for an operator or an anomaly detector."""
        breaker = self.breakers.breaker(dependency)
        for _ in range(breaker.failure_threshold - breaker.consecutive_failures):
            breaker.record_failure()
        self.signals.emit(
            SignalType.EVENT, "cost.circuit_breaker.tripped", tenant_id, dependency=dependency, reason=reason
        )
        self.escalate("circuit_breaker_tripped", {"dependency": dependency, "reason": reason})

    def reset(self, dependency: str, tenant_id: str) -> None:
        """Manual close, once the underlying fault is fixed."""
        self.breakers.breaker(dependency).reset()
        self.signals.emit(SignalType.EVENT, "cost.circuit_breaker.reset", tenant_id, dependency=dependency)

    # ------------------------------------------------------------- Reporting

    def attribution(
        self,
        scope: BudgetScope | None = None,
        principal_id: str | None = None,
        tenant_id: str | None = None,
    ) -> Mapping[str, Any]:
        """Cost attribution per operation, agent, business, tenant (02.3.9)."""
        entries = self.ledger.entries(scope=scope, principal_id=principal_id, tenant_id=tenant_id)
        by_operation: dict[str, float] = {}
        for entry in entries:
            by_operation[entry.operation] = by_operation.get(entry.operation, 0.0) + entry.amount
        return {
            "entries": len(entries),
            "total": sum(entry.amount for entry in entries),
            "by_operation": by_operation,
        }

    def health(self) -> Mapping[str, Any]:
        """Cost Manager health, for the Observability Gateway."""
        budgets = self.ledger.all_budgets()
        return {
            "budgets": len(budgets),
            "by_level": _count_by(b.level.value for b in budgets),
            "ledger_entries": self.ledger.entry_count,
            "total_spend": self.ledger.total(),
            "open_breakers": self.breakers.open_breakers(),
            "halts": self._halts,
            "downgrades": self._downgrades,
        }

    # ------------------------------------------------------------- Internals

    def _verdict(
        self,
        scope: BudgetScope,
        utilization: float,
        remaining: float,
        estimated_cost: float,
        level: BudgetLevel,
    ) -> BudgetVerdict:
        halted = level == BudgetLevel.RED
        downgrade = level in (BudgetLevel.ORANGE, BudgetLevel.RED)
        reasons = {
            BudgetLevel.GREEN: "below 50% of budget",
            BudgetLevel.YELLOW: "50-80% of budget; warning logged and alert sent",
            BudgetLevel.ORANGE: "80-95% of budget; model downgrading enforced",
            BudgetLevel.RED: "above 95% of budget; operations halted and escalated to a human",
        }
        return BudgetVerdict(
            scope=scope,
            level=level,
            action=ACTION_BY_LEVEL[level],
            utilization=utilization,
            remaining=remaining,
            estimated_cost=estimated_cost,
            downgrade_required=downgrade,
            halted=halted,
            reason=reasons[level],
        )

    def _observe(self, verdict: BudgetVerdict, tenant_id: str) -> None:
        """Emits the signal and, at Yellow and above, alerts once per level change."""
        self.signals.emit(
            SignalType.METRIC,
            "cost.budget.utilization",
            tenant_id,
            value=verdict.utilization,
            scope=str(verdict.scope),
            level=verdict.level.value,
        )
        if verdict.downgrade_required:
            self._downgrades += 1
        if verdict.halted:
            self._halts += 1

        key = str(verdict.scope)
        if verdict.level == BudgetLevel.GREEN:
            self._alerted_levels.pop(key, None)
            return
        if self._alerted_levels.get(key) == verdict.level:
            return  # already alerted at this level; do not spam
        self._alerted_levels[key] = verdict.level
        self.signals.emit(
            SignalType.EVENT,
            "cost.budget.threshold_breached",
            tenant_id,
            value=verdict.utilization,
            scope=key,
            level=verdict.level.value,
            action=verdict.action,
        )
        if verdict.halted:
            # Red escalates to a human. 02.3.9 does not make this optional.
            self.escalate(
                "budget_red",
                {
                    "scope": key,
                    "tenant_id": tenant_id,
                    "utilization": verdict.utilization,
                    "reason": verdict.reason,
                },
            )


def _count_by(values: Any) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return counts


__all__ = [
    "CostManager",
    "BudgetVerdict",
    "BudgetExceeded",
    "BudgetScope",
    "ScopeKind",
    "CircuitOpenError",
    "ACTION_BY_LEVEL",
]
