import pytest

from persistence.in_memory import InMemoryRepository
from persistence.repository import NotFound


def test_save_and_get():
    repo: InMemoryRepository[dict[str, int]] = InMemoryRepository()
    repo.save("a", {"v": 1})
    assert repo.get("a") == {"v": 1}


def test_get_missing_raises_not_found():
    repo: InMemoryRepository[dict[str, int]] = InMemoryRepository()
    with pytest.raises(NotFound):
        repo.get("missing")


def test_delete_and_list_all():
    repo: InMemoryRepository[dict[str, int]] = InMemoryRepository()
    repo.save("a", {"v": 1})
    repo.save("b", {"v": 2})
    repo.delete("a")
    assert repo.list_all() == [{"v": 2}]
    with pytest.raises(NotFound):
        repo.delete("a")
