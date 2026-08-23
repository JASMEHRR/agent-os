from core.constants import BudgetLevel


def test_budget_level_bands():
    assert BudgetLevel.from_utilization(0.10) == BudgetLevel.GREEN
    assert BudgetLevel.from_utilization(0.49) == BudgetLevel.GREEN
    assert BudgetLevel.from_utilization(0.50) == BudgetLevel.YELLOW
    assert BudgetLevel.from_utilization(0.79) == BudgetLevel.YELLOW
    assert BudgetLevel.from_utilization(0.80) == BudgetLevel.ORANGE
    assert BudgetLevel.from_utilization(0.94) == BudgetLevel.ORANGE
    assert BudgetLevel.from_utilization(0.95) == BudgetLevel.RED
    assert BudgetLevel.from_utilization(1.0) == BudgetLevel.RED
