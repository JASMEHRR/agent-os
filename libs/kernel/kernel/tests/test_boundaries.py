from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from kernel.boundaries import (
    BoundaryContext,
    BoundaryEnforcementEngine,
    BoundaryType,
    BoundaryViolationError,
    RequestContext,
)

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def _ctx(**overrides: Any) -> BoundaryContext:
    base: dict[str, Any] = dict(
        tenant_id="t1", scope={"read", "write"}, authority_level=3, confidence=0.9, budget_remaining=100.0, now=NOW
    )
    base.update(overrides)
    return BoundaryContext(**base)


def _req(**overrides: Any) -> RequestContext:
    base: dict[str, Any] = dict(
        tenant_id="t1", required_scope={"read"}, required_authority_level=2, min_confidence=0.6, cost=10.0
    )
    base.update(overrides)
    return RequestContext(**base)


@pytest.mark.parametrize(
    "ctx_overrides,req_overrides,expected_boundary",
    [
        ({"tenant_id": "t2"}, {}, BoundaryType.TENANT),
        ({}, {"required_scope": {"admin"}}, BoundaryType.SCOPE),
        ({"authority_level": 1}, {}, BoundaryType.AUTHORITY),
        ({"confidence": 0.1}, {}, BoundaryType.CONFIDENCE),
        ({"budget_remaining": 1.0}, {}, BoundaryType.BUDGET),
        ({}, {"not_after": NOW - timedelta(days=1)}, BoundaryType.TEMPORAL),
    ],
)
def test_each_boundary_type_enforced(
    ctx_overrides: dict[str, Any], req_overrides: dict[str, Any], expected_boundary: BoundaryType
) -> None:
    engine = BoundaryEnforcementEngine()
    with pytest.raises(BoundaryViolationError) as exc_info:
        engine.enforce(_ctx(**ctx_overrides), _req(**req_overrides))
    assert exc_info.value.boundary == expected_boundary


def test_all_boundaries_pass() -> None:
    engine = BoundaryEnforcementEngine()
    engine.enforce(_ctx(), _req())  # must not raise
