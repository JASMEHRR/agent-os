"""Cost Manager — budget enforcement, cost attribution, alerting (realizes 02.3.9).

Built at Stage S3 because every subsequent module's budget enforcement needs
this operational first: the Budget boundary is one of the kernel's six, and a
Gateway checking it against nothing would be enforcing nothing.

Enforces the "Free API First" and "Cost Transparency" principles of 04. Red
halts and escalates to a human; that is not configurable.
"""

from cost_manager.breakers import (
    BreakerState,
    CircuitBreaker,
    CircuitBreakerRegistry,
    CircuitOpenError,
)
from cost_manager.ledger import Budget, BudgetScope, CostLedger, LedgerEntry, ScopeKind
from cost_manager.manager import (
    ACTION_BY_LEVEL,
    BudgetExceeded,
    BudgetVerdict,
    CostManager,
)

__all__ = [
    "CostManager",
    "BudgetVerdict",
    "BudgetExceeded",
    "ACTION_BY_LEVEL",
    "BudgetScope",
    "ScopeKind",
    "Budget",
    "CostLedger",
    "LedgerEntry",
    "CircuitBreaker",
    "CircuitBreakerRegistry",
    "CircuitOpenError",
    "BreakerState",
]
