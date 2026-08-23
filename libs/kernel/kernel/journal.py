"""Immutable Journal (21A §5.2 item 4).

Append-only, hash-chained entry log. Any attempted mutation of a written
entry, or an append whose declared prev_hash doesn't match the actual chain
tip, fails — this is the tamper-evidence property every Gateway's Journal
relies on (see e.g. Security Event Journal, Stage S1).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any


class JournalTamperError(Exception):
    pass


@dataclass(frozen=True)
class JournalEntry:
    seq: int
    prev_hash: str
    payload: Mapping[str, Any]
    recorded_at: datetime
    entry_hash: str

    @staticmethod
    def compute_hash(seq: int, prev_hash: str, payload: Mapping[str, Any], recorded_at: datetime) -> str:
        material = json.dumps(
            {"seq": seq, "prev_hash": prev_hash, "payload": payload, "recorded_at": recorded_at.isoformat()},
            sort_keys=True,
            default=str,
        ).encode("utf-8")
        return hashlib.sha256(material).hexdigest()


class ImmutableJournal:
    GENESIS_HASH = "0" * 64

    def __init__(self) -> None:
        self._entries: list[JournalEntry] = []

    def append(self, payload: Mapping[str, Any]) -> JournalEntry:
        seq = len(self._entries)
        prev_hash = self._entries[-1].entry_hash if self._entries else self.GENESIS_HASH
        recorded_at = datetime.now(UTC)
        entry_hash = JournalEntry.compute_hash(seq, prev_hash, payload, recorded_at)
        entry = JournalEntry(
            seq=seq, prev_hash=prev_hash, payload=payload, recorded_at=recorded_at, entry_hash=entry_hash
        )
        self._entries.append(entry)
        return entry

    def __len__(self) -> int:
        return len(self._entries)

    def __getitem__(self, seq: int) -> JournalEntry:
        return self._entries[seq]

    def verify_chain(self) -> bool:
        """Recomputes every entry's hash and checks chain linkage; raises on tamper."""
        prev_hash = self.GENESIS_HASH
        for entry in self._entries:
            expected = JournalEntry.compute_hash(entry.seq, prev_hash, entry.payload, entry.recorded_at)
            if entry.prev_hash != prev_hash or entry.entry_hash != expected:
                raise JournalTamperError(f"chain broken at seq {entry.seq}")
            prev_hash = entry.entry_hash
        return True
