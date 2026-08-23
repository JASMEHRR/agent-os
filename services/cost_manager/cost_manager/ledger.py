"""Cost ledger and budget allocations (realizes 02.3.9, 21A §10 `aos_analytics`).

"Real-time cost tracking per operation, agent, business, tenant" (02.3.9).
The ledger is append-only for the same reason every other record in Agent OS
is: a spend that could be un-recorded is a spend that cannot be attributed,
and 04's Cost Transparency principle makes attribution the point.

Budgets are allocated per scope and consumed against that allocation. The four
levels of 02.3.9 — Green, Yellow, Orange, Red — come from `core.BudgetLevel`,
which S0 already derived from utilization; nothing here re-implements the
thresholds.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum

from core.constants import BudgetLevel
from core.exceptions import NotFoundError, ValidationError


class ScopeKind(StrEnum):
    """The attribution levels 02.3.9 names: operation, agent, business, tenant."""

    OPERATION = "operation"
    AGENT = "agent"
    BUSINESS = "business"
    TENANT = "tenant"


@dataclass(frozen=True)
class BudgetScope:
    """One budget-bearing identity, e.g. (agent, agent-writer)."""

    kind: ScopeKind
    identifier: str

    def __str__(self) -> str:
        return f"{self.kind.value}:{self.identifier}"


@dataclass(frozen=True)
class LedgerEntry:
    """One recorded spend. Append-only; corrections are new entries (04)."""

    scope: BudgetScope
    tenant_id: str
    amount: float
    operation: str
    principal_id: str
    recorded_at: datetime
    sequence: int
    #: Set when this entry reverses an earlier one, so a correction is
    #: traceable to what it corrects rather than overwriting it.
    corrects: int | None = None


@dataclass
class Budget:
    """An allocation and what has been spent against it."""

    scope: BudgetScope
    tenant_id: str
    limit: float
    spent: float = 0.0
    #: Period the allocation covers; a new period means a new allocation
    #: rather than a mutated one, so history stays reconstructable.
    period_start: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def remaining(self) -> float:
        return max(0.0, self.limit - self.spent)

    @property
    def utilization(self) -> float:
        if self.limit <= 0:
            return 1.0
        return self.spent / self.limit

    @property
    def level(self) -> BudgetLevel:
        """The four levels of 02.3.9, computed by `core.BudgetLevel` (S0)."""
        return BudgetLevel.from_utilization(self.utilization)


@dataclass
class CostLedger:
    """Append-only spend record with per-scope budget allocations."""

    now: Callable[[], datetime] = field(default=lambda: datetime.now(UTC))
    _entries: list[LedgerEntry] = field(default_factory=list, init=False)
    _budgets: dict[str, Budget] = field(default_factory=dict, init=False)

    def allocate(self, scope: BudgetScope, tenant_id: str, limit: float) -> Budget:
        """Allocates or re-allocates a budget for a scope."""
        if limit < 0:
            raise ValidationError(f"budget limit for {scope} must not be negative")
        budget = Budget(scope=scope, tenant_id=tenant_id, limit=limit, period_start=self.now())
        self._budgets[str(scope)] = budget
        return budget

    def budget_for(self, scope: BudgetScope) -> Budget:
        try:
            return self._budgets[str(scope)]
        except KeyError:
            raise NotFoundError(f"no budget allocated for {scope}") from None

    def has_budget(self, scope: BudgetScope) -> bool:
        return str(scope) in self._budgets

    def record(
        self,
        scope: BudgetScope,
        tenant_id: str,
        amount: float,
        operation: str,
        principal_id: str,
        corrects: int | None = None,
    ) -> LedgerEntry:
        """Records a spend and applies it to the scope's budget.

        A negative amount is permitted only as a correction, which is how a
        refund or an over-estimate is unwound without deleting the original
        entry.
        """
        if amount < 0 and corrects is None:
            raise ValidationError("a negative amount must reference the entry it corrects")
        entry = LedgerEntry(
            scope=scope,
            tenant_id=tenant_id,
            amount=amount,
            operation=operation,
            principal_id=principal_id,
            recorded_at=self.now(),
            sequence=len(self._entries),
            corrects=corrects,
        )
        self._entries.append(entry)
        if self.has_budget(scope):
            budget = self.budget_for(scope)
            budget.spent = max(0.0, budget.spent + amount)
        return entry

    def entries(
        self,
        scope: BudgetScope | None = None,
        principal_id: str | None = None,
        tenant_id: str | None = None,
    ) -> list[LedgerEntry]:
        """Cost attribution query — per operation, agent, business, or tenant."""
        return [
            entry
            for entry in self._entries
            if (scope is None or entry.scope == scope)
            and (principal_id is None or entry.principal_id == principal_id)
            and (tenant_id is None or entry.tenant_id == tenant_id)
        ]

    def total(self, scope: BudgetScope | None = None, tenant_id: str | None = None) -> float:
        return sum(entry.amount for entry in self.entries(scope=scope, tenant_id=tenant_id))

    def all_budgets(self) -> list[Budget]:
        return list(self._budgets.values())

    @property
    def entry_count(self) -> int:
        return len(self._entries)
