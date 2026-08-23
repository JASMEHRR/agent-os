"""Failure Classification (21A §5.2 item 6).

Five categories, each with a mandated response (04's Failure Handling
Philosophy): Transient (retry with backoff), Degradable (degrade), Critical
(halt-and-escalate), Security (isolate), Financial (freeze budget).
Classification must complete within 60 seconds of failure detection.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum

CLASSIFICATION_BOUND_SECONDS = 60.0


class FailureCategory(StrEnum):
    TRANSIENT = "transient"
    DEGRADABLE = "degradable"
    CRITICAL = "critical"
    SECURITY = "security"
    FINANCIAL = "financial"


RESPONSE_BY_CATEGORY = {
    FailureCategory.TRANSIENT: "retry_with_backoff",
    FailureCategory.DEGRADABLE: "degrade",
    FailureCategory.CRITICAL: "halt_and_escalate",
    FailureCategory.SECURITY: "isolate",
    FailureCategory.FINANCIAL: "freeze_budget",
}


class ClassificationTimeoutError(Exception):
    pass


@dataclass(frozen=True)
class Classification:
    category: FailureCategory
    response: str
    elapsed_seconds: float


class FailureClassifier:
    """Classifies a failure via a supplied rule function, enforcing the 60s bound."""

    def classify(self, failure: Exception, rule: Callable[[Exception], FailureCategory]) -> Classification:
        started = time.monotonic()
        category = rule(failure)
        elapsed = time.monotonic() - started
        if elapsed > CLASSIFICATION_BOUND_SECONDS:
            raise ClassificationTimeoutError(
                f"classification took {elapsed:.1f}s, exceeds {CLASSIFICATION_BOUND_SECONDS}s bound"
            )
        return Classification(category=category, response=RESPONSE_BY_CATEGORY[category], elapsed_seconds=elapsed)
