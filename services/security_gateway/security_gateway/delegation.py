"""Delegation Manager (21B §22.3, realizes 14.14).

Delegation lends existing permissions; it never creates new ones. The rule
that makes that structural is 14.7.4: if A delegates to B and B to C, C's
effective permissions are "the intersection of all three principals' scopes,
not the union". Chains are validated **at the point of action**, not at
creation time (21B §22.4) — a link revoked after creation must invalidate
everything downstream of it the next time the chain is walked.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from core.exceptions import NotFoundError, ValidationError
from security_gateway.enums import DelegationType
from security_gateway.permissions import PermissionGraphEngine, intersect

#: 14.14.2 — "Standing orders expire after 30 days unless renewed."
STANDING_ORDER_MAX_DURATION = timedelta(days=30)


class DelegationError(ValidationError):
    pass


class BrokenChainError(DelegationError):
    """A link in the chain is expired, revoked, or its delegator is not actionable."""


@dataclass
class Delegation:
    delegation_id: str
    delegation_type: DelegationType
    delegator_id: str
    delegatee_id: str
    permissions: frozenset[str]
    tenant_id: str
    granted_at: datetime
    expires_at: datetime
    revoked_at: datetime | None = None
    #: Set for Emergency delegations, which 14.14.2 logs as constitutional exceptions.
    authorized_by: str | None = None

    def is_live(self, now: datetime) -> bool:
        return self.revoked_at is None and now < self.expires_at


@dataclass
class DelegationManager:
    """Creation, chain validation, scope intersection and expiry (21B §22.3)."""

    graph_engine: PermissionGraphEngine
    #: Answers "is this principal Active" — injected so the manager does not
    #: reach into the Identity Registry across a component boundary.
    is_actionable: Callable[[str], bool]
    now: Callable[[], datetime] = field(default=lambda: datetime.now(UTC))
    _delegations: dict[str, Delegation] = field(default_factory=dict, init=False)
    _by_delegatee: dict[str, list[str]] = field(default_factory=dict, init=False)
    _by_delegator: dict[str, list[str]] = field(default_factory=dict, init=False)

    def create(
        self,
        delegation_id: str,
        delegation_type: DelegationType,
        delegator_id: str,
        delegatee_id: str,
        permissions: Iterable[str],
        tenant_id: str,
        duration: timedelta,
        authorized_by: str | None = None,
    ) -> Delegation:
        """Creates a delegation, rejecting anything exceeding the delegator's own scope (14.14.3)."""
        if delegation_id in self._delegations:
            raise DelegationError(f"delegation '{delegation_id}' already exists")
        if delegator_id == delegatee_id:
            raise DelegationError("a principal may not delegate to itself (14.17.5, no self-escalation)")
        if duration <= timedelta(0):
            raise DelegationError("delegation duration must be positive (14.14.3, time window)")
        if delegation_type == DelegationType.STANDING_ORDER and duration > STANDING_ORDER_MAX_DURATION:
            raise DelegationError(f"standing orders expire after {STANDING_ORDER_MAX_DURATION.days} days (14.14.2)")
        if delegation_type == DelegationType.EMERGENCY and authorized_by is None:
            raise DelegationError("emergency delegation requires a human authorizer (14.14.2)")
        if not self.is_actionable(delegator_id):
            raise DelegationError(f"delegator '{delegator_id}' is not an Active principal")

        requested = frozenset(permissions)
        delegator_scope = self.effective_permissions(delegator_id)
        granted = intersect(delegator_scope, requested)
        if not granted:
            raise DelegationError(
                f"delegator '{delegator_id}' holds none of the requested permissions "
                f"{sorted(requested)}; a delegation may not exceed the delegator's own scope (14.14.3)"
            )

        now = self.now()
        delegation = Delegation(
            delegation_id=delegation_id,
            delegation_type=delegation_type,
            delegator_id=delegator_id,
            delegatee_id=delegatee_id,
            permissions=granted,
            tenant_id=tenant_id,
            granted_at=now,
            expires_at=now + duration,
            authorized_by=authorized_by,
        )
        self._delegations[delegation_id] = delegation
        self._by_delegatee.setdefault(delegatee_id, []).append(delegation_id)
        self._by_delegator.setdefault(delegator_id, []).append(delegation_id)
        self._refresh_graph_source(delegatee_id)
        return delegation

    def get(self, delegation_id: str) -> Delegation:
        try:
            return self._delegations[delegation_id]
        except KeyError:
            raise NotFoundError(f"delegation '{delegation_id}' not found") from None

    def revoke(self, delegation_id: str) -> Delegation:
        delegation = self.get(delegation_id)
        if delegation.revoked_at is None:
            delegation.revoked_at = self.now()
            self._refresh_graph_source(delegation.delegatee_id)
        return delegation

    def issued_by(self, delegator_id: str) -> list[Delegation]:
        return [self._delegations[d] for d in self._by_delegator.get(delegator_id, [])]

    def held_by(self, delegatee_id: str) -> list[Delegation]:
        return [self._delegations[d] for d in self._by_delegatee.get(delegatee_id, [])]

    def live_for(self, delegatee_id: str) -> list[Delegation]:
        now = self.now()
        return [d for d in self.held_by(delegatee_id) if d.is_live(now)]

    def chain_for(self, delegatee_id: str) -> list[Delegation]:
        """Walks the delegation chain from `delegatee_id` back toward its root.

        A principal holding several concurrent delegations has several chains;
        this returns the one rooted in the most recent grant, which is the
        chain a fresh action under that grant travels.

        Liveness is treated differently at the head and in the interior. If
        the *starting* principal holds nothing live, it simply is not acting
        under delegation — an expired grant leaves it with its own
        permissions and no chain. But once a chain has started, a dead
        interior link is still walked, so `validate_chain` sees the break and
        raises. Skipping it would let a revoked upstream link silently vanish
        and leave downstream authority intact, which 14.14.4 forbids.
        """
        chain: list[Delegation] = []
        seen: set[str] = set()
        current = delegatee_id
        now = self.now()
        while True:
            held = self.held_by(current)
            live = [d for d in held if d.is_live(now)]
            candidates = live if live else (held if chain else [])
            if not candidates:
                break
            hop = max(candidates, key=lambda d: d.granted_at)
            if hop.delegation_id in seen:
                break
            seen.add(hop.delegation_id)
            chain.append(hop)
            current = hop.delegator_id
        return chain

    def validate_chain(self, delegatee_id: str) -> frozenset[str]:
        """Validates the whole chain end to end and returns its intersected scope (14.14.4).

        Checks every link's delegatee identity, the delegator's authority to
        lend, scope, expiry, and absence of revocation. Any break raises —
        a broken chain invalidates the authorization outright, it does not
        silently degrade to the delegatee's own permissions.
        """
        chain = self.chain_for(delegatee_id)
        if not chain:
            return frozenset()
        now = self.now()
        scope: frozenset[str] | None = None
        for link in chain:
            if link.revoked_at is not None:
                raise BrokenChainError(f"delegation '{link.delegation_id}' was revoked at {link.revoked_at}")
            if now >= link.expires_at:
                raise BrokenChainError(f"delegation '{link.delegation_id}' expired at {link.expires_at}")
            if not self.is_actionable(link.delegator_id):
                raise BrokenChainError(
                    f"delegator '{link.delegator_id}' of '{link.delegation_id}' is not an Active principal"
                )
            scope = link.permissions if scope is None else intersect(scope, link.permissions)
        root = chain[-1].delegator_id
        if scope is None:  # unreachable: a non-empty chain always sets scope
            raise BrokenChainError(f"chain for '{delegatee_id}' produced no scope")
        return intersect(scope, self.effective_permissions(root))

    def effective_permissions(self, principal_id: str) -> frozenset[str]:
        return self.graph_engine.graph_for(principal_id).effective

    def expire_due(self) -> list[Delegation]:
        """Sweeps expired delegations, refreshing affected graphs (14.15.2, Expiry trigger)."""
        now = self.now()
        expired = [d for d in self._delegations.values() if d.revoked_at is None and now >= d.expires_at]
        for delegation in expired:
            self._refresh_graph_source(delegation.delegatee_id)
        return expired

    def _refresh_graph_source(self, delegatee_id: str) -> None:
        """Republishes the delegatee's `delegations` graph input (14.12.2 invalidation)."""
        live = self.live_for(delegatee_id)
        if not live:
            self.graph_engine.clear_source(delegatee_id, "delegations")
            return
        union_of_grants: set[str] = set()
        for delegation in live:
            union_of_grants |= delegation.permissions
        # Concurrent delegations are alternative grants to the same principal,
        # so they combine; the intersection rule of 14.12.4 then applies
        # between this *source* and every other source in the graph engine.
        self.graph_engine.set_source(delegatee_id, "delegations", union_of_grants)
