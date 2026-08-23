"""Revocation Engine (21B §22.3, realizes 14.15).

14.15.3 sets the bar: when a principal is revoked, the revocation cascades to
all active tokens, pending tasks, child tasks, delegations issued by the
principal, and cached permission graphs — atomically, within a bounded
window. "Partial revocation is treated as a system failure and alerted."

That last sentence is why this module raises rather than returns on partial
failure, and why the propagation targets acknowledge explicitly instead of
being fire-and-forget calls.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime

from core.exceptions import AgentOSError
from security_gateway.enums import RevocationTrigger

#: [Engineering Decision] 14.15.4 mandates "defined latency budgets" for
#: propagation but publishes no figure; 21B §22.12 records the window as an
#: open ADR item. Five seconds aligns the bound with the Panic Protocol,
#: which is the tightest system-wide halt bound in the constitution.
PROPAGATION_BOUND_SECONDS = 5.0


class PartialRevocationError(AgentOSError):
    """Raised when any propagation target fails to acknowledge (14.15.3)."""

    def __init__(self, principal_id: str, unacknowledged: list[str]):
        super().__init__(
            f"cascading revocation of '{principal_id}' was partial — no acknowledgement from "
            f"{sorted(unacknowledged)}; 14.15.3 classifies this as a system failure"
        )
        self.principal_id = principal_id
        self.unacknowledged = unacknowledged


class PropagationTimeoutError(AgentOSError):
    def __init__(self, principal_id: str, elapsed: float):
        super().__init__(
            f"revocation of '{principal_id}' took {elapsed:.2f}s, exceeding the "
            f"{PROPAGATION_BOUND_SECONDS}s propagation bound"
        )


@dataclass(frozen=True)
class RevocationRecord:
    """The log record 14.15.5 requires — Sovereign-class, Operators and Auditors only."""

    principal_id: str
    revoker_id: str
    trigger: RevocationTrigger
    reason: str
    scope: tuple[str, ...]
    revoked_at: datetime
    cascaded_to: tuple[str, ...]
    delegations_revoked: tuple[str, ...]
    elapsed_seconds: float


@dataclass
class RevocationEngine:
    """Cascading revocation with atomic bounded-window execution and verified propagation.

    Propagation targets are named callables — one per dependent subsystem
    (Runtime, Agent, Tool, Memory, Decision per 14.15.4). Each returns True to
    acknowledge. A target that returns False, or raises, leaves the revocation
    partial, which is a system failure rather than a degraded success.
    """

    now: Callable[[], datetime] = field(default=lambda: datetime.now(UTC))
    _targets: dict[str, Callable[[str], bool]] = field(default_factory=dict, init=False)
    _revocation_list: set[str] = field(default_factory=set, init=False)
    _records: list[RevocationRecord] = field(default_factory=list, init=False)

    def register_target(self, name: str, halt: Callable[[str], bool]) -> None:
        """Registers a dependent subsystem that must acknowledge revocations (14.15.4)."""
        self._targets[name] = halt

    def revoke(
        self,
        principal_id: str,
        revoker_id: str,
        trigger: RevocationTrigger,
        reason: str,
        scope: tuple[str, ...],
        local_effects: Callable[[], tuple[str, ...]],
    ) -> RevocationRecord:
        """Executes the cascade.

        `local_effects` performs the Gateway-local half — token invalidation,
        delegation revocation, permission-graph invalidation — and returns the
        delegation IDs it revoked. It runs *before* remote propagation so a
        propagation failure can never leave the Gateway itself still honouring
        the revoked authority.
        """
        started = time.monotonic()
        delegations_revoked = local_effects()
        self._revocation_list.add(principal_id)

        acknowledged: list[str] = []
        unacknowledged: list[str] = []
        for name, halt in self._targets.items():
            try:
                ok = halt(principal_id)
            except Exception:  # a raising target is an unacknowledged target
                ok = False
            (acknowledged if ok else unacknowledged).append(name)

        elapsed = time.monotonic() - started
        record = RevocationRecord(
            principal_id=principal_id,
            revoker_id=revoker_id,
            trigger=trigger,
            reason=reason,
            scope=scope,
            revoked_at=self.now(),
            cascaded_to=tuple(acknowledged),
            delegations_revoked=tuple(delegations_revoked),
            elapsed_seconds=elapsed,
        )
        self._records.append(record)

        if unacknowledged:
            raise PartialRevocationError(principal_id, unacknowledged)
        if elapsed > PROPAGATION_BOUND_SECONDS:
            raise PropagationTimeoutError(principal_id, elapsed)
        return record

    def is_revoked(self, principal_id: str) -> bool:
        """The revocation list caches are validated against (14.10.4)."""
        return principal_id in self._revocation_list

    @property
    def revocation_list(self) -> frozenset[str]:
        """Broadcast to every consuming cache; membership invalidates cached decisions."""
        return frozenset(self._revocation_list)

    def reinstate(self, principal_id: str) -> None:
        """Removes a principal from the revocation list on Suspended -> Active (14.8.3)."""
        self._revocation_list.discard(principal_id)

    @property
    def records(self) -> tuple[RevocationRecord, ...]:
        return tuple(self._records)
