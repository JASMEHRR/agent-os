"""The durable adapter, and the property that makes it worth having.

The central test is `test_data_survives_closing_and_reopening_the_database`.
Everything else in this file supports it: an adapter that round-trips within a
process but loses the file on reopen would pass a naive suite and fail at the
only thing it exists to do.
"""

from __future__ import annotations

import dataclasses
import enum
from datetime import UTC, datetime

import pytest

from persistence.codec import CodecError, decode_dataclass, encode
from persistence.repository import NotFound
from persistence.sqlite_store import SQLiteRepository, open_database


class Tier(enum.Enum):
    LOW = "low"
    HIGH = "high"


@dataclasses.dataclass(frozen=True)
class Inner:
    label: str
    score: float


@dataclasses.dataclass(frozen=True)
class Record:
    record_id: str
    tier: Tier
    created_at: datetime
    tags: tuple[str, ...]
    inner: Inner
    note: str | None = None
    counts: dict[str, int] = dataclasses.field(default_factory=dict)


def _record(record_id: str = "r1") -> Record:
    return Record(
        record_id=record_id,
        tier=Tier.HIGH,
        created_at=datetime(2026, 8, 25, 12, 0, tzinfo=UTC),
        tags=("alpha", "beta"),
        inner=Inner(label="nested", score=0.5),
        counts={"a": 1},
    )


@pytest.fixture
def repo(tmp_path):
    connection = open_database(tmp_path / "store.db")
    return SQLiteRepository(connection, "records", Record)


# ------------------------------------------------------- The point of it all


def test_data_survives_closing_and_reopening_the_database(tmp_path) -> None:
    """The whole reason this adapter exists.

    The in-memory adapter passes every other test in this file. It fails this
    one, which is the difference between a system that can hold a fact
    overnight and one that cannot.
    """
    path = tmp_path / "store.db"

    first = SQLiteRepository(open_database(path), "records", Record)
    first.save("r1", _record())

    reopened = SQLiteRepository(open_database(path), "records", Record)

    assert reopened.get("r1") == _record()


def test_every_domain_shape_round_trips(repo) -> None:
    """Enums, aware datetimes, tuples, nested dataclasses, optionals and dicts.

    Listed together because a codec usually breaks on one of them, and finding
    out which at read time in production is expensive.
    """
    repo.save("r1", _record())
    loaded = repo.get("r1")

    assert loaded == _record()
    assert loaded.tier is Tier.HIGH
    assert loaded.created_at.tzinfo is not None, "an aware datetime must not come back naive"
    assert isinstance(loaded.tags, tuple)
    assert loaded.inner == Inner(label="nested", score=0.5)
    assert loaded.note is None
    assert loaded.counts == {"a": 1}


# ------------------------------------------------------------ Port behaviour


def test_a_missing_entity_raises_not_found(repo) -> None:
    with pytest.raises(NotFound):
        repo.get("absent")


def test_deleting_something_absent_raises_rather_than_passing_quietly(repo) -> None:
    """Matches the in-memory adapter, which is what makes them substitutable.

    A silent no-op would let a caller working from a stale view believe it had
    removed something.
    """
    with pytest.raises(NotFound):
        repo.delete("absent")


def test_saving_the_same_id_replaces_rather_than_duplicates(repo) -> None:
    repo.save("r1", _record())
    repo.save("r1", dataclasses.replace(_record(), note="second"))

    assert repo.get("r1").note == "second"
    assert len(repo.list_all()) == 1


def test_namespaces_do_not_see_each_other(tmp_path) -> None:
    """Every repository shares one table, so this is the isolation that keeps
    two modules storing the same entity id from overwriting each other."""
    connection = open_database(tmp_path / "store.db")
    left = SQLiteRepository(connection, "left", Record)
    right = SQLiteRepository(connection, "right", Record)

    left.save("shared-id", _record("from-left"))
    right.save("shared-id", _record("from-right"))

    assert left.get("shared-id").record_id == "from-left"
    assert right.get("shared-id").record_id == "from-right"
    assert left.count() == 1


def test_list_all_is_ordered_so_results_are_reproducible(repo) -> None:
    for name in ("c", "a", "b"):
        repo.save(name, _record(name))

    assert [r.record_id for r in repo.list_all()] == ["a", "b", "c"]


# ------------------------------------------------------------------- Codec


def test_pickle_is_not_used_anywhere_in_the_store() -> None:
    """The decision worth protecting from a future convenience.

    Pickle would round-trip everything here with no code at all, and would
    turn every stored row into something the process executes on read.
    """
    import pathlib

    module_dir = pathlib.Path(__file__).resolve().parents[1]
    for source in module_dir.glob("*.py"):
        assert "import pickle" not in source.read_text(encoding="utf-8"), f"{source.name} imports pickle"


def test_a_field_added_since_the_row_was_written_is_reported_not_guessed() -> None:
    """A migration is the caller's decision, not this layer's.

    Filling in a plausible value would let the system carry on with data it
    invented, which is worse than stopping.
    """

    @dataclasses.dataclass(frozen=True)
    class Widened:
        record_id: str
        newly_required: str

    with pytest.raises(CodecError, match="needs a migration"):
        decode_dataclass(Widened, {"record_id": "r1"})


def test_a_field_with_a_default_is_filled_from_it() -> None:
    """The other half: adding an optional field must not break existing rows."""

    @dataclasses.dataclass(frozen=True)
    class Widened:
        record_id: str
        added_later: str = "default"

    assert decode_dataclass(Widened, {"record_id": "r1"}).added_later == "default"


def test_a_none_in_a_non_optional_field_is_refused() -> None:
    """The row and the code disagree about the shape, and accepting it quietly
    would hide a migration nobody wrote."""

    @dataclasses.dataclass(frozen=True)
    class Strict:
        value: str

    with pytest.raises(CodecError, match="non-optional"):
        decode_dataclass(Strict, {"value": None})


def test_an_unencodable_type_is_refused_at_write_time() -> None:
    """Better to fail on the way in than to store something unreadable."""
    with pytest.raises(CodecError, match="cannot encode"):
        encode(object())


def test_the_datetime_marker_cannot_be_forged_by_a_plain_string() -> None:
    """The marker distinguishes a stored datetime from a string that looks like
    one. A value carrying it would decode as the wrong type, so it is refused
    rather than silently mangled."""
    with pytest.raises(CodecError, match="collides"):
        encode("\x00iso:not-really-a-datetime")
