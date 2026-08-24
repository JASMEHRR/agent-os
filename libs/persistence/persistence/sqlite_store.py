"""Durable `Repository` adapter on SQLite.

The in-memory adapter loses everything at process exit, which makes the system
unable to hold a fact overnight. This one closes that, and does it with
`sqlite3` from the standard library: no server to run, no dependency to add,
and a single file that can be copied, inspected and backed up.

Design notes worth reading before changing anything here:

* **One table, namespaced rows.** Every repository shares `entities` and is
  separated by a `namespace` column rather than a table per type. Repositories
  are created dynamically by modules that do not know about each other, and a
  table-per-type scheme would mean DDL at construction time from arbitrary
  callers.
* **WAL mode.** A reader does not block a writer, which matters because the
  Observability Gateway reads while everything else writes.
* **`updated_at` is stored and never read by this class.** It exists for the
  human holding the file open in a viewer at three in the morning, which is
  the only tool guaranteed to be available then.
* **The type is supplied by the reader**, never carried in the row. See the
  codec module: a payload that could name its own class would be an execution
  primitive.
"""

from __future__ import annotations

import json
import pathlib
import sqlite3
import threading
from datetime import UTC, datetime
from typing import Generic, TypeVar

from persistence.codec import decode_dataclass, encode
from persistence.repository import NotFound

T = TypeVar("T")

SCHEMA = """
CREATE TABLE IF NOT EXISTS entities (
    namespace  TEXT NOT NULL,
    entity_id  TEXT NOT NULL,
    payload    TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (namespace, entity_id)
);
CREATE INDEX IF NOT EXISTS entities_by_namespace ON entities (namespace);
"""


def open_database(path: str | pathlib.Path) -> sqlite3.Connection:
    """Opens (creating if needed) the store and applies the schema.

    `check_same_thread=False` because one connection is shared across the
    repositories a process builds, and the lock below is what actually makes
    that safe. SQLite's own thread check would refuse the sharing without
    providing the serialization that makes it correct.
    """
    path = pathlib.Path(path)
    if path.parent != pathlib.Path():
        path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(path), check_same_thread=False)
    # WAL survives a crash and lets reads proceed during a write. NORMAL
    # synchronous is WAL's documented safe pairing: durable across a process
    # crash, which is the failure this adapter exists to survive.
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA synchronous=NORMAL")
    connection.executescript(SCHEMA)
    connection.commit()
    return connection


class SQLiteRepository(Generic[T]):
    """Implements `persistence.repository.Repository` durably.

    Constructed with the entity type, which is what the codec rebuilds rows
    into. Passing the wrong type does not corrupt anything; it raises at read
    time, because the annotations will not match the stored shape.
    """

    def __init__(self, connection: sqlite3.Connection, namespace: str, entity_type: type[T]) -> None:
        self._connection = connection
        self._namespace = namespace
        self._type = entity_type
        # sqlite3 serializes at the C level, but a read-modify-write across two
        # statements is not atomic without this. Held for the shortest span
        # that keeps each public method a single unit.
        self._lock = threading.Lock()

    # ------------------------------------------------------------- Repository

    def get(self, entity_id: str) -> T:
        with self._lock:
            row = self._connection.execute(
                "SELECT payload FROM entities WHERE namespace = ? AND entity_id = ?",
                (self._namespace, entity_id),
            ).fetchone()
        if row is None:
            raise NotFound(entity_id)
        return decode_dataclass(self._type, json.loads(row[0]))

    def save(self, entity_id: str, entity: T) -> None:
        # Encoded before the lock: serialization is the slow part and it does
        # not touch the connection.
        payload = json.dumps(encode(entity))
        now = datetime.now(UTC).isoformat()
        with self._lock:
            self._connection.execute(
                "INSERT INTO entities (namespace, entity_id, payload, updated_at) VALUES (?, ?, ?, ?) "
                "ON CONFLICT (namespace, entity_id) DO UPDATE SET payload = excluded.payload, "
                "updated_at = excluded.updated_at",
                (self._namespace, entity_id, payload, now),
            )
            self._connection.commit()

    def delete(self, entity_id: str) -> None:
        with self._lock:
            cursor = self._connection.execute(
                "DELETE FROM entities WHERE namespace = ? AND entity_id = ?",
                (self._namespace, entity_id),
            )
            self._connection.commit()
        if cursor.rowcount == 0:
            # Deleting something absent is reported rather than ignored, so a
            # caller working from a stale view is told, and matching the
            # in-memory adapter's behaviour keeps the two substitutable.
            raise NotFound(entity_id)

    def list_all(self) -> list[T]:
        with self._lock:
            rows = self._connection.execute(
                "SELECT payload FROM entities WHERE namespace = ? ORDER BY entity_id",
                (self._namespace,),
            ).fetchall()
        return [decode_dataclass(self._type, json.loads(row[0])) for row in rows]

    # ------------------------------------------------------------------ Extra

    def count(self) -> int:
        """Not part of the port. Used by the health surface, which wants a size
        without paying to rebuild every row into a domain object."""
        with self._lock:
            row = self._connection.execute(
                "SELECT COUNT(*) FROM entities WHERE namespace = ?",
                (self._namespace,),
            ).fetchone()
        return int(row[0])
