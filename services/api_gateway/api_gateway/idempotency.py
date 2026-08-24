"""Idempotency keys on mutating endpoints (03 §32.2, Build Spec S8, 03 Rule 24).

03 §32.2: "All mutating endpoints (`POST`, `PUT`, `PATCH`, `DELETE`) must
accept an `Idempotency-Key` header. The API Gateway stores idempotency keys for
24 hours and returns the cached response for duplicate keys."

Two properties matter more than the caching:

**A key is bound to its request.** Replaying a stored response for a *different*
body under the same key would silently discard the second request. The store
fingerprints method, path and body, and a mismatch is a 409 rather than a
replay — the client has a bug and needs to be told.

**A failed attempt does not reserve the key.** Caching a 500 would make the
failure permanent for 24 hours and leave the client unable to retry the thing
that idempotency exists to let them retry safely.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

#: 03 §32.2, verbatim.
RETENTION = timedelta(hours=24)


def fingerprint(method: str, path: str, body: dict[str, Any]) -> str:
    """A stable digest of what the client asked for."""
    payload = json.dumps({"method": method, "path": path, "body": body}, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class KeyReused(Exception):
    """The same key arrived with a different request (409 Conflict)."""


@dataclass(frozen=True)
class StoredResponse:
    status: int
    body: dict[str, Any]
    fingerprint: str
    stored_at: datetime
    request_id: str


@dataclass
class IdempotencyStore:
    """24-hour keyed response store, scoped per principal.

    Scoping matters: two tenants that happen to choose the same key string
    must not see each other's responses, and nothing about a client-chosen
    key makes it globally unique.
    """

    now: Callable[[], datetime] = field(default=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        self._entries: dict[tuple[str, str], StoredResponse] = {}

    def lookup(self, principal_id: str, key: str, request_fingerprint: str) -> StoredResponse | None:
        entry = self._entries.get((principal_id, key))
        if entry is None:
            return None
        if self.now() - entry.stored_at > RETENTION:
            del self._entries[(principal_id, key)]
            return None
        if entry.fingerprint != request_fingerprint:
            raise KeyReused(
                f"idempotency key '{key}' was already used for a different request; "
                "reusing a key for different content would discard this one silently"
            )
        return entry

    def remember(
        self, principal_id: str, key: str, request_fingerprint: str, status: int, body: dict[str, Any], request_id: str
    ) -> None:
        """Stores a completed response. Only successes are retained.

        A cached failure would make a transient error permanent for the
        retention window, defeating the retry the key exists to enable.
        """
        if status >= 500:
            return
        self._entries[(principal_id, key)] = StoredResponse(
            status=status,
            body=body,
            fingerprint=request_fingerprint,
            stored_at=self.now(),
            request_id=request_id,
        )

    def purge_expired(self) -> int:
        cutoff = self.now() - RETENTION
        stale = [k for k, v in self._entries.items() if v.stored_at < cutoff]
        for key in stale:
            del self._entries[key]
        return len(stale)

    def __len__(self) -> int:
        return len(self._entries)
