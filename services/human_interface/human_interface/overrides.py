"""Human override and standing orders (05.18.3, 05.18.5, 13.33.2, 16.25.3,
17.31.2, 18.35.3, 19.36.3).

Seven documents state the override rule in nearly identical words. 05.18.3:
"Humans may override any runtime action at any time. Overrides are immediate,
irreversible by the runtime, and logged."

**Irreversible by the runtime** is the load-bearing half, and it is the one an
implementation loses most easily. An override with a `revoke` method reachable
by a service would let the system undo the human's correction, which is
exactly the failure the clause names. So `Override` is frozen, the ledger is
append-only, and the only way to change an override's effect is a *new* human
action recorded beside it.

Standing orders (05.18.5) are the mirror image: humans may delegate routine
decisions, but delegation is **scoped, time-bounded, and revocable**. 16.25.3
fixes the bound at 30 days unless renewed, so an order that is forgotten
lapses rather than persisting indefinitely.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any

from core.exceptions import AgentOSError, ValidationError
from human_interface.approvals import NotHuman

#: 16.25.3, verbatim: "Standing orders expire after 30 days unless renewed."
STANDING_ORDER_TTL = timedelta(days=30)


class OverrideScope(StrEnum):
    """What a human overrode. Each is named by a document that grants the right."""

    AGENT_ACTION = "agent_action"
    WORKFLOW = "workflow"
    DECISION = "decision"
    LEARNING_PROPOSAL = "learning_proposal"
    INTEGRATION = "integration"
    DEPLOYMENT = "deployment"
    EVOLUTIONARY_ARTIFACT = "evolutionary_artifact"
    OBSERVABILITY = "observability"


@dataclass(frozen=True)
class Override:
    """One human override. Frozen, because the runtime may not undo it.

    Recorded as a Class D action (13.33.2), the highest decision class, which
    is what makes it visible to Governance without Governance having to infer
    it.
    """

    override_id: str
    tenant_id: str
    scope: OverrideScope
    target_id: str
    directive: str
    reason: str
    issued_by: str
    issued_at: datetime
    #: 13.33.2, 17.31.1, 18.35.3, 19.36.3 all classify an override as Class D.
    decision_class: str = "D"


@dataclass
class OverrideLedger:
    """Append-only. Nothing here removes or mutates an entry."""

    is_human: Callable[[str], bool]
    now: Callable[[], datetime] = field(default=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        self._overrides: list[Override] = []
        self._by_target: dict[str, list[Override]] = {}

    def issue(
        self,
        override_id: str,
        tenant_id: str,
        scope: OverrideScope,
        target_id: str,
        directive: str,
        reason: str,
        issued_by: str,
    ) -> Override:
        """Immediate on return: there is no pending state for an override."""
        if not self.is_human(issued_by):
            raise NotHuman(
                f"'{issued_by}' is not a human principal; an override is a human act by definition (05.18.3)"
            )
        if not reason.strip():
            raise ValidationError("an override must carry a reason; it is logged and will be reviewed")
        if any(o.override_id == override_id for o in self._overrides):
            raise AgentOSError(f"override '{override_id}' already exists")
        override = Override(
            override_id=override_id,
            tenant_id=tenant_id,
            scope=scope,
            target_id=target_id,
            directive=directive,
            reason=reason,
            issued_by=issued_by,
            issued_at=self.now(),
        )
        self._overrides.append(override)
        self._by_target.setdefault(target_id, []).append(override)
        return override

    def for_target(self, target_id: str) -> list[Override]:
        """Every override against one target, oldest first."""
        return list(self._by_target.get(target_id, ()))

    def latest_for(self, target_id: str) -> Override | None:
        overrides = self._by_target.get(target_id)
        return overrides[-1] if overrides else None

    def all(self) -> list[Override]:
        return list(self._overrides)

    def __len__(self) -> int:
        return len(self._overrides)


@dataclass
class StandingOrder:
    """Delegated routine authority: scoped, time-bounded, revocable (05.18.5)."""

    order_id: str
    tenant_id: str
    issued_by: str
    #: What the order covers. An unscoped standing order is refused.
    scope: frozenset[str]
    directive: str
    issued_at: datetime
    expires_at: datetime
    revoked_at: datetime | None = None
    revoked_by: str | None = None
    renewals: int = 0

    def is_active(self, at: datetime) -> bool:
        return self.revoked_at is None and at < self.expires_at

    def covers(self, subject: str) -> bool:
        return any(subject == s or subject.startswith(f"{s}.") for s in self.scope)


@dataclass
class StandingOrderRegistry:
    """05.18.5 with 16.25.3's expiry."""

    is_human: Callable[[str], bool]
    now: Callable[[], datetime] = field(default=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        self._orders: dict[str, StandingOrder] = {}

    def issue(
        self,
        order_id: str,
        tenant_id: str,
        issued_by: str,
        scope: frozenset[str],
        directive: str,
        ttl: timedelta | None = None,
    ) -> StandingOrder:
        if not self.is_human(issued_by):
            raise NotHuman(f"'{issued_by}' is not a human principal; only a human may delegate authority (05.18.5)")
        if not scope:
            raise ValidationError(
                "a standing order must be scoped; an unscoped delegation is indistinguishable from "
                "removing the gate entirely (05.18.5)"
            )
        if order_id in self._orders:
            raise AgentOSError(f"standing order '{order_id}' already exists")
        issued_at = self.now()
        order = StandingOrder(
            order_id=order_id,
            tenant_id=tenant_id,
            issued_by=issued_by,
            scope=scope,
            directive=directive,
            issued_at=issued_at,
            expires_at=issued_at + (ttl or STANDING_ORDER_TTL),
        )
        self._orders[order_id] = order
        return order

    def get(self, order_id: str) -> StandingOrder:
        order = self._orders.get(order_id)
        if order is None:
            raise AgentOSError(f"standing order '{order_id}' does not exist")
        return order

    def renew(self, order_id: str, principal_id: str, ttl: timedelta | None = None) -> StandingOrder:
        """16.25.3 — renewal is an explicit human act, not an automatic one."""
        if not self.is_human(principal_id):
            raise NotHuman(f"'{principal_id}' is not a human principal; renewal is a human act")
        order = self.get(order_id)
        if order.revoked_at is not None:
            raise AgentOSError(f"standing order '{order_id}' was revoked and cannot be renewed")
        order.expires_at = self.now() + (ttl or STANDING_ORDER_TTL)
        order.renewals += 1
        return order

    def revoke(self, order_id: str, principal_id: str) -> StandingOrder:
        if not self.is_human(principal_id):
            raise NotHuman(f"'{principal_id}' is not a human principal; only a human may revoke a delegation")
        order = self.get(order_id)
        order.revoked_at = self.now()
        order.revoked_by = principal_id
        return order

    def active(self, tenant_id: str | None = None) -> list[StandingOrder]:
        at = self.now()
        return [o for o in self._orders.values() if o.is_active(at) and (tenant_id is None or o.tenant_id == tenant_id)]

    def covering(self, tenant_id: str, subject: str) -> StandingOrder | None:
        """The active order delegating `subject`, if a human issued one."""
        for order in self.active(tenant_id):
            if order.covers(subject):
                return order
        return None

    def health(self) -> Mapping[str, Any]:
        at = self.now()
        orders = list(self._orders.values())
        return {
            "orders": len(orders),
            "active": len([o for o in orders if o.is_active(at)]),
            "expired": len([o for o in orders if o.revoked_at is None and at >= o.expires_at]),
            "revoked": len([o for o in orders if o.revoked_at is not None]),
            "ttl_days": STANDING_ORDER_TTL.days,
        }
