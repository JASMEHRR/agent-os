"""In-memory Repository adapter.

# ponytail: process-local dict store, no persistence across restarts. Used
# for the Synthetic Gateway conformance tests and unit tests; a Postgres
# adapter (SQLAlchemy 2.0 + Alembic, per the canonical stack) is a separate
# module-level work item, not built here.
"""

from __future__ import annotations

from typing import Generic, TypeVar

from persistence.repository import NotFound

T = TypeVar("T")


class InMemoryRepository(Generic[T]):
    def __init__(self) -> None:
        self._store: dict[str, T] = {}

    def get(self, entity_id: str) -> T:
        try:
            return self._store[entity_id]
        except KeyError:
            raise NotFound(entity_id) from None

    def save(self, entity_id: str, entity: T) -> None:
        self._store[entity_id] = entity

    def delete(self, entity_id: str) -> None:
        try:
            del self._store[entity_id]
        except KeyError:
            raise NotFound(entity_id) from None

    def list_all(self) -> list[T]:
        return list(self._store.values())
