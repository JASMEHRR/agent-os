"""Agent OS persistence: hexagonal ports-and-adapters data access layer.

Realizes 01.7.1, 02.7. `Repository` is the port every module's domain code
depends on; adapters (in-memory for tests/Synthetic Gateway now, Postgres
later) implement it without domain code ever importing an adapter directly.
"""

from persistence.in_memory import InMemoryRepository
from persistence.repository import NotFound, Repository

__all__ = ["Repository", "NotFound", "InMemoryRepository"]
