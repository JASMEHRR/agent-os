"""Cost-based circuit breakers (02.3.9).

"Cost-based circuit breakers" is one line in the constitution, and the Stage
S3 test list fixes what it has to do: trip on repeated external-call failure.
The breaker exists because a failing external dependency does not stop costing
money — retries against a broken integration burn budget with no chance of
success, which is precisely the runaway 02.3.9 exists to prevent.

Three states, the standard shape: Closed (calls pass), Open (calls refused),
Half-Open (one probe allowed, success closes, failure re-opens). Guarded by
`kernel.LifecycleStateMachine` so the transition table is enforced rather than
implied, the same way every other state machine in the system is.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum

from core.exceptions import AgentOSError
from kernel.lifecycle import LifecycleStateMachine

#: [Engineering Decision] 02.3.9 mandates cost-based circuit breakers without
#: publishing thresholds. Five consecutive failures and a 60-second cooldown
#: are starting values, overridable per breaker.
DEFAULT_FAILURE_THRESHOLD = 5
DEFAULT_COOLDOWN = timedelta(seconds=60)


class BreakerState(StrEnum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


BREAKER_TRANSITIONS: dict[str, set[str]] = {
    BreakerState.CLOSED: {BreakerState.OPEN},
    BreakerState.OPEN: {BreakerState.HALF_OPEN, BreakerState.CLOSED},
    BreakerState.HALF_OPEN: {BreakerState.CLOSED, BreakerState.OPEN},
}


class CircuitOpenError(AgentOSError):
    """The breaker is open; the call is refused before it can cost anything."""

    def __init__(self, name: str, opened_at: datetime, reopens_at: datetime):
        super().__init__(
            f"circuit '{name}' is open (tripped {opened_at.isoformat()}); "
            f"next probe permitted at {reopens_at.isoformat()}"
        )
        self.name = name


@dataclass
class CircuitBreaker:
    """One breaker, guarding one external dependency."""

    name: str
    now: Callable[[], datetime] = field(default=lambda: datetime.now(UTC))
    failure_threshold: int = DEFAULT_FAILURE_THRESHOLD
    cooldown: timedelta = DEFAULT_COOLDOWN
    state: BreakerState = BreakerState.CLOSED
    consecutive_failures: int = 0
    opened_at: datetime | None = None
    trip_count: int = 0

    def _machine(self) -> LifecycleStateMachine:
        return LifecycleStateMachine(transitions=dict(BREAKER_TRANSITIONS), state=self.state)

    def _transition(self, target: BreakerState) -> None:
        machine = self._machine()
        machine.transition(target)
        self.state = target

    def check(self) -> None:
        """Raises if the call must not proceed. Called before spending anything."""
        if self.state == BreakerState.OPEN:
            # `opened_at` is set on every transition into OPEN. Written as a
            # fallback rather than an assert so it survives `python -O`.
            opened_at = self.opened_at or self.now()
            reopens_at = opened_at + self.cooldown
            if self.now() < reopens_at:
                raise CircuitOpenError(self.name, opened_at, reopens_at)
            # Cooldown elapsed: allow exactly one probe through.
            self._transition(BreakerState.HALF_OPEN)

    def record_success(self) -> BreakerState:
        self.consecutive_failures = 0
        if self.state in (BreakerState.HALF_OPEN, BreakerState.OPEN):
            self._transition(BreakerState.CLOSED)
            self.opened_at = None
        return self.state

    def record_failure(self) -> BreakerState:
        self.consecutive_failures += 1
        if self.state == BreakerState.HALF_OPEN:
            # The probe failed; straight back to open with a fresh cooldown.
            self._transition(BreakerState.OPEN)
            self.opened_at = self.now()
            self.trip_count += 1
        elif self.state == BreakerState.CLOSED and self.consecutive_failures >= self.failure_threshold:
            self._transition(BreakerState.OPEN)
            self.opened_at = self.now()
            self.trip_count += 1
        return self.state

    def reset(self) -> BreakerState:
        """Manual close, for an operator who has fixed the underlying fault."""
        if self.state != BreakerState.CLOSED:
            self._transition(BreakerState.CLOSED)
        self.consecutive_failures = 0
        self.opened_at = None
        return self.state

    @property
    def is_open(self) -> bool:
        return self.state == BreakerState.OPEN


@dataclass
class CircuitBreakerRegistry:
    """The breaker set, keyed by the dependency each one guards."""

    now: Callable[[], datetime] = field(default=lambda: datetime.now(UTC))
    failure_threshold: int = DEFAULT_FAILURE_THRESHOLD
    cooldown: timedelta = DEFAULT_COOLDOWN
    _breakers: dict[str, CircuitBreaker] = field(default_factory=dict, init=False)

    def breaker(self, name: str) -> CircuitBreaker:
        """Returns the named breaker, creating it closed on first use."""
        if name not in self._breakers:
            self._breakers[name] = CircuitBreaker(
                name=name,
                now=self.now,
                failure_threshold=self.failure_threshold,
                cooldown=self.cooldown,
            )
        return self._breakers[name]

    def open_breakers(self) -> list[str]:
        return sorted(name for name, breaker in self._breakers.items() if breaker.is_open)

    def all_breakers(self) -> list[CircuitBreaker]:
        return list(self._breakers.values())
