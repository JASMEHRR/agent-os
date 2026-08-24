"""Agent OS persistence: hexagonal ports-and-adapters data access layer.

Realizes 01.7.1, 02.7. `Repository` is the port every module's domain code
depends on; adapters implement it without domain code ever importing an
adapter directly.

Two adapters. `InMemoryRepository` is the fast one, used by the unit suites
and the Synthetic Gateway. `SQLiteRepository` is the durable one, and it is
the difference between a system that can hold a fact overnight and one that
cannot: the in-memory adapter passes every test the durable one does except
the one that reopens the file.
"""

from persistence.codec import CodecError, decode_dataclass, encode
from persistence.in_memory import InMemoryRepository
from persistence.repository import NotFound, Repository
from persistence.sqlite_store import SQLiteRepository, open_database

__all__ = [
    "Repository",
    "NotFound",
    "InMemoryRepository",
    "SQLiteRepository",
    "open_database",
    "CodecError",
    "encode",
    "decode_dataclass",
]
