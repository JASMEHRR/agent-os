"""Boundary Enforcement engine (21A §5.2 item 3).

Six boundary types are constitutionally mandated: Tenant, Scope, Authority,
Confidence, Budget, Temporal. The engine here enforces a boundary context
against a request context; each boundary type is a pure check function so
Gateways compose only the boundaries relevant to their operation.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class BoundaryType(StrEnum):
    TENANT = "tenant"
    SCOPE = "scope"
    AUTHORITY = "authority"
    CONFIDENCE = "confidence"
    BUDGET = "budget"
    TEMPORAL = "temporal"


class BoundaryViolationError(Exception):
    def __init__(self, boundary: BoundaryType, reason: str):
        super().__init__(f"Boundary '{boundary.value}' violated: {reason}")
        self.boundary = boundary
        self.reason = reason


@dataclass
class BoundaryContext:
    tenant_id: str
    scope: set[str]
    authority_level: int
    confidence: float
    budget_remaining: float
    now: datetime


@dataclass
class RequestContext:
    tenant_id: str
    required_scope: set[str]
    required_authority_level: int
    min_confidence: float
    cost: float
    not_before: datetime | None = None
    not_after: datetime | None = None


class BoundaryEnforcementEngine:
    """Checks a RequestContext against a BoundaryContext for all six boundaries.

    Raises BoundaryViolationError on the first violation encountered, in the
    fixed order Tenant -> Scope -> Authority -> Confidence -> Budget -> Temporal.
    """

    def enforce(self, ctx: BoundaryContext, req: RequestContext) -> None:
        if ctx.tenant_id != req.tenant_id:
            raise BoundaryViolationError(
                BoundaryType.TENANT,
                f"context tenant '{ctx.tenant_id}' != request tenant '{req.tenant_id}'",
            )
        if not req.required_scope.issubset(ctx.scope):
            missing = req.required_scope - ctx.scope
            raise BoundaryViolationError(BoundaryType.SCOPE, f"missing scope(s): {sorted(missing)}")
        if ctx.authority_level < req.required_authority_level:
            raise BoundaryViolationError(
                BoundaryType.AUTHORITY,
                f"authority level {ctx.authority_level} < required {req.required_authority_level}",
            )
        if ctx.confidence < req.min_confidence:
            raise BoundaryViolationError(
                BoundaryType.CONFIDENCE,
                f"confidence {ctx.confidence} < required {req.min_confidence}",
            )
        if req.cost > ctx.budget_remaining:
            raise BoundaryViolationError(
                BoundaryType.BUDGET,
                f"cost {req.cost} exceeds remaining budget {ctx.budget_remaining}",
            )
        if req.not_before is not None and ctx.now < req.not_before:
            raise BoundaryViolationError(BoundaryType.TEMPORAL, f"{ctx.now} is before window start {req.not_before}")
        if req.not_after is not None and ctx.now > req.not_after:
            raise BoundaryViolationError(BoundaryType.TEMPORAL, f"{ctx.now} is after window end {req.not_after}")
