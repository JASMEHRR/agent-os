"""Repository port. Generic over an entity type; adapters implement this
Protocol without domain code depending on the adapter's storage technology."""

from __future__ import annotations

from typing import Generic, Protocol, TypeVar

T = TypeVar("T")


class NotFound(Exception):
    def __init__(self, entity_id: str):
        super().__init__(f"entity '{entity_id}' not found")
        self.entity_id = entity_id


class Repository(Protocol, Generic[T]):
    def get(self, entity_id: str) -> T: ...

    def save(self, entity_id: str, entity: T) -> None: ...

    def delete(self, entity_id: str) -> None: ...

    def list_all(self) -> list[T]: ...
