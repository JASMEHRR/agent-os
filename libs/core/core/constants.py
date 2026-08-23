"""System-wide constants ratified in the constitution.

BudgetLevel thresholds: cost_manager (Stage S3, 02.3.9).
ConfidenceThreshold bands: Knowledge Gateway (document 10), reused wherever
confidence-banded promotion/decay logic applies.
"""

from __future__ import annotations

from enum import Enum, StrEnum


class BudgetLevel(StrEnum):
    GREEN = "green"  # < 50% of budget consumed
    YELLOW = "yellow"  # 50-80%
    ORANGE = "orange"  # 80-95%, forces model downgrade
    RED = "red"  # > 95%, halts operations and escalates to human

    @staticmethod
    def from_utilization(utilization: float) -> BudgetLevel:
        if utilization < 0.50:
            return BudgetLevel.GREEN
        if utilization < 0.80:
            return BudgetLevel.YELLOW
        if utilization < 0.95:
            return BudgetLevel.ORANGE
        return BudgetLevel.RED


class ConfidenceThreshold(float, Enum):
    PROVISIONAL = 0.60
    VALIDATED = 0.80
    CANONICAL = 0.95
