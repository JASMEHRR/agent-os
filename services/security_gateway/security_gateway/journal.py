"""Security Event Journal (21B §22.3, realizes 14.13 / 14.26).

Kernel-supplied: this wraps `kernel.ImmutableJournal` rather than
reimplementing hash-chaining. Two properties matter beyond what the kernel
provides — the journal is written **directly to persistence, not through the
Event Bus** (14.26.1, which is what makes building Security before the Event
Bus possible at all, per 21B §22.6), and it is queryable for forensic
reconstruction by Governance and by humans holding the Auditor role.

Retention is Sovereign-class, seven years (21B §22.8). Retention *policy* is
recorded on every entry; retention *enforcement* is a storage-tier concern of
the Postgres adapter, which does not exist yet — see the Journal entry.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from kernel.journal import ImmutableJournal, JournalEntry
from persistence.repository import Repository
from security_gateway.enums import Classification, SecurityEventType

#: 21B §22.8 — Security Event Journal retention is seven years.
RETENTION = timedelta(days=365 * 7)


@dataclass(frozen=True)
class SecurityEvent:
    """One journalled security event, as recorded and as returned by query."""

    event_type: SecurityEventType
    principal_id: str
    tenant_id: str
    outcome: str
    classification: Classification
    detail: Mapping[str, Any]
    recorded_at: datetime
    seq: int
    entry_hash: str

    @property
    def retain_until(self) -> datetime:
        return self.recorded_at + RETENTION


class SecurityEventJournal:
    """Append-only, tamper-evident record of every security-relevant action.

    Every write also lands in `persistence` so the journal survives process
    restart independently of any event transport (14.26.1).
    """

    def __init__(self, repository: Repository[JournalEntry]) -> None:
        self._journal = ImmutableJournal()
        self._repo = repository

    def record(
        self,
        event_type: SecurityEventType,
        principal_id: str,
        tenant_id: str,
        outcome: str,
        detail: Mapping[str, Any] | None = None,
        classification: Classification = Classification.RESTRICTED,
    ) -> SecurityEvent:
        payload: dict[str, Any] = {
            "event_type": event_type.value,
            "principal_id": principal_id,
            "tenant_id": tenant_id,
            "outcome": outcome,
            "classification": classification.value,
            "detail": dict(detail or {}),
        }
        entry = self._journal.append(payload)
        self._repo.save(str(entry.seq), entry)
        return _to_event(entry)

    def verify(self) -> bool:
        """Recomputes the whole chain; raises `JournalTamperError` on any edit (14.13)."""
        return self._journal.verify_chain()

    def query(
        self,
        principal_id: str | None = None,
        tenant_id: str | None = None,
        event_type: SecurityEventType | None = None,
        since: datetime | None = None,
    ) -> list[SecurityEvent]:
        """Security Event Journal Query interface — Governance and Auditor forensics (21B §22.5)."""
        results = []
        for seq in range(len(self._journal)):
            event = _to_event(self._journal[seq])
            if principal_id is not None and event.principal_id != principal_id:
                continue
            if tenant_id is not None and event.tenant_id != tenant_id:
                continue
            if event_type is not None and event.event_type != event_type:
                continue
            if since is not None and event.recorded_at < since:
                continue
            results.append(event)
        return results

    def counts_by_type(self) -> dict[str, int]:
        """Feeds the Security Health interface (21B §22.5) and 14.29.2 thresholds."""
        counts: dict[str, int] = {}
        for seq in range(len(self._journal)):
            key = str(self._journal[seq].payload["event_type"])
            counts[key] = counts.get(key, 0) + 1
        return counts

    def __len__(self) -> int:
        return len(self._journal)


def _to_event(entry: JournalEntry) -> SecurityEvent:
    payload = entry.payload
    return SecurityEvent(
        event_type=SecurityEventType(payload["event_type"]),
        principal_id=str(payload["principal_id"]),
        tenant_id=str(payload["tenant_id"]),
        outcome=str(payload["outcome"]),
        classification=Classification(payload["classification"]),
        detail=dict(payload["detail"]),
        recorded_at=entry.recorded_at.astimezone(UTC),
        seq=entry.seq,
        entry_hash=entry.entry_hash,
    )
