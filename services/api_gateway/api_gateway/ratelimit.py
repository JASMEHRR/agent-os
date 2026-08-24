"""Rate limiting per tenant, per user, per API key (02.3.1, 03 §32.5).

Three dimensions, and the limit is the **most restrictive** of the three that
apply — the same intersection discipline 14.12.4 imposes on permissions. A
per-user allowance cannot lift a tenant that has exhausted its quota, because
the tenant limit exists precisely to bound the sum of its users.

Token bucket, as 03 §32.5 specifies: a steady refill rate with a burst
ceiling, so a client that has been quiet may spend its saved allowance at once
without being able to sustain more than its rate.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum


class Tier(StrEnum):
    """03 §32.5's tiers."""

    ANONYMOUS = "anonymous"
    AUTHENTICATED = "authenticated"
    SERVICE_ACCOUNT = "service_account"
    INTERNAL = "internal"


#: 03 §32.5, verbatim: requests per minute and burst ceiling.
TIER_LIMITS: dict[Tier, tuple[int, int]] = {
    Tier.ANONYMOUS: (10, 10),
    Tier.AUTHENTICATED: (100, 150),
    Tier.SERVICE_ACCOUNT: (1000, 2000),
    Tier.INTERNAL: (10000, 15000),
}

WINDOW = timedelta(minutes=1)


@dataclass
class Bucket:
    """One token bucket. Refills continuously, never above its burst ceiling."""

    rate_per_minute: int
    burst: int
    tokens: float
    updated_at: datetime

    def _refill(self, now: datetime) -> None:
        elapsed = (now - self.updated_at).total_seconds()
        if elapsed <= 0:
            return
        self.tokens = min(float(self.burst), self.tokens + elapsed * self.rate_per_minute / 60.0)
        self.updated_at = now

    def take(self, now: datetime) -> bool:
        self._refill(now)
        if self.tokens < 1.0:
            return False
        self.tokens -= 1.0
        return True

    def peek(self, now: datetime) -> int:
        self._refill(now)
        return int(self.tokens)

    def resets_at(self, now: datetime) -> datetime:
        """When a fully-drained bucket would hold one token again."""
        if self.tokens >= 1.0:
            return now
        needed = 1.0 - self.tokens
        return now + timedelta(seconds=needed * 60.0 / self.rate_per_minute)


@dataclass(frozen=True)
class Decision:
    """The outcome, plus the headers of 03 §32.5."""

    allowed: bool
    limit: int
    remaining: int
    reset_at: datetime
    #: Which dimension bound the request. Named so a throttled client can be
    #: told *what* it exhausted rather than merely that it was throttled.
    binding_dimension: str

    def headers(self) -> dict[str, str]:
        return {
            "RateLimit-Limit": str(self.limit),
            "RateLimit-Remaining": str(self.remaining),
            "RateLimit-Reset": str(int(self.reset_at.timestamp())),
        }


@dataclass
class RateLimiter:
    """Token buckets across the three dimensions of 02.3.1."""

    now: Callable[[], datetime] = field(default=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        self._buckets: dict[tuple[str, str], Bucket] = {}
        self._overrides: dict[tuple[str, str], tuple[int, int]] = {}

    def configure(self, dimension: str, identifier: str, rate_per_minute: int, burst: int) -> None:
        """A per-identity limit, for a tenant on a negotiated plan."""
        self._overrides[(dimension, identifier)] = (rate_per_minute, burst)
        self._buckets.pop((dimension, identifier), None)

    def _bucket(self, dimension: str, identifier: str, tier: Tier) -> Bucket:
        key = (dimension, identifier)
        existing = self._buckets.get(key)
        if existing is not None:
            return existing
        rate, burst = self._overrides.get(key, TIER_LIMITS[tier])
        bucket = Bucket(rate_per_minute=rate, burst=burst, tokens=float(burst), updated_at=self.now())
        self._buckets[key] = bucket
        return bucket

    def check(
        self,
        tier: Tier,
        tenant_id: str | None = None,
        user_id: str | None = None,
        api_key: str | None = None,
    ) -> Decision:
        """Consumes one token from every applicable dimension, or none at all.

        Consuming from some dimensions and then refusing on another would
        charge a client for a request it never got to make, so the buckets are
        inspected first and only debited once every one of them can pay.
        """
        now = self.now()
        dimensions = [
            (name, identifier)
            for name, identifier in (("tenant", tenant_id), ("user", user_id), ("api_key", api_key))
            if identifier
        ]
        if not dimensions:
            dimensions = [("anonymous", "anonymous")]

        buckets = [(name, self._bucket(name, identifier, tier)) for name, identifier in dimensions]
        for name, bucket in buckets:
            if bucket.peek(now) < 1:
                return Decision(
                    allowed=False,
                    limit=bucket.rate_per_minute,
                    remaining=0,
                    reset_at=bucket.resets_at(now),
                    binding_dimension=name,
                )

        for _name, bucket in buckets:
            bucket.take(now)

        binding_name, binding_bucket = min(buckets, key=lambda pair: pair[1].peek(now))
        return Decision(
            allowed=True,
            limit=binding_bucket.rate_per_minute,
            remaining=binding_bucket.peek(now),
            reset_at=binding_bucket.resets_at(now),
            binding_dimension=binding_name,
        )
