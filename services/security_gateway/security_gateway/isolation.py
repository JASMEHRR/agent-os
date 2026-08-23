"""Isolation Enforcer (21B §22.3, realizes 14.18–14.21).

Isolation is by default (21B §22.15 item 4): tenants, businesses, workspaces
and portfolios are isolated absent explicit bilateral authorization. Rule 15
of document 14 is unambiguous — "No cross-tenant access without bilateral
human approval" — so a grant here requires an approving Human on *both*
sides, and it expires.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from core.exceptions import AgentOSError
from security_gateway.enums import Classification


class IsolationBreachError(AgentOSError):
    """Attempted cross-boundary access without authorization (14.29.1, Isolation Breach)."""

    def __init__(self, scope: str, source: str, target: str):
        super().__init__(f"{scope} isolation breach: '{source}' attempted access to '{target}' without authorization")
        self.scope = scope
        self.source = source
        self.target = target


@dataclass(frozen=True)
class CrossBoundaryGrant:
    """Bilateral, human-approved, time-bounded permission to cross one boundary."""

    scope: str  # "tenant" | "portfolio" | "business" | "workspace" (14.5.3)
    source: str
    target: str
    approved_by_source: str
    approved_by_target: str
    granted_at: datetime
    expires_at: datetime
    classification: Classification = Classification.SOVEREIGN

    def is_live(self, now: datetime) -> bool:
        return now < self.expires_at


@dataclass
class IsolationEnforcer:
    """Tenant, workspace, business and portfolio boundary enforcement."""

    #: Answers "is this principal a Human" — bilateral approval requires two.
    is_human: Callable[[str], bool]
    now: Callable[[], datetime] = field(default=lambda: datetime.now(UTC))
    _grants: dict[tuple[str, str, str], CrossBoundaryGrant] = field(default_factory=dict, init=False)

    def grant(
        self,
        scope: str,
        source: str,
        target: str,
        approved_by_source: str,
        approved_by_target: str,
        duration: timedelta,
    ) -> CrossBoundaryGrant:
        if approved_by_source == approved_by_target:
            raise AgentOSError("cross-boundary access requires bilateral approval by two distinct humans (14 rule 15)")
        for approver in (approved_by_source, approved_by_target):
            if not self.is_human(approver):
                raise AgentOSError(
                    f"approver '{approver}' is not a Human principal; 14 rule 15 requires human approval"
                )
        if duration <= timedelta(0):
            raise AgentOSError("cross-boundary grants must be time-bounded")
        now = self.now()
        grant = CrossBoundaryGrant(
            scope=scope,
            source=source,
            target=target,
            approved_by_source=approved_by_source,
            approved_by_target=approved_by_target,
            granted_at=now,
            expires_at=now + duration,
        )
        self._grants[(scope, source, target)] = grant
        return grant

    def revoke(self, scope: str, source: str, target: str) -> None:
        self._grants.pop((scope, source, target), None)

    def check(self, scope: str, source: str, target: str) -> None:
        """Deny-by-default: same boundary passes, anything else needs a live grant."""
        if source == target:
            return
        grant = self._grants.get((scope, source, target))
        if grant is None or not grant.is_live(self.now()):
            raise IsolationBreachError(scope, source, target)

    def is_permitted(self, scope: str, source: str, target: str) -> bool:
        try:
            self.check(scope, source, target)
        except IsolationBreachError:
            return False
        return True
