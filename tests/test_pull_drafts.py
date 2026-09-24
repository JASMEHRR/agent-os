"""Receiving drafts from origin/master, against real git repositories.

The promise that matters is scope: a push to master can change what is in
Review, and nothing else on this machine. So the remote in these tests always
changes code alongside drafts, and the tests check the code did not arrive.
"""

from __future__ import annotations

import pathlib
import subprocess

import pytest

from content_agent import DraftState
from scripts import serve
from scripts.import_drafts import open_stores
from scripts.pull_drafts import PullError, fetch_drafts, pull

POST = """# Weekly drafts

## LinkedIn

**Hook**
{hook}

**Body**
A body with 3 in it.

**Close**
Which would you pick?

**Hashtags**
#buildinpublic #campusmarketplace #firestore
"""


def git(repo: pathlib.Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t", *args],
        capture_output=True,
        text=True,
        check=True,
    ).stdout


def commit(repo: pathlib.Path, files: dict[str, str], message: str = "change") -> None:
    for name, text in files.items():
        path = repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", message)
    git(repo, "push", "-q", "origin", "master")


@pytest.fixture
def repos(tmp_path: pathlib.Path) -> tuple[pathlib.Path, pathlib.Path]:
    """`(author, laptop)`: the author pushes, the laptop runs the studio."""
    origin = tmp_path / "origin.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "master", str(origin)], check=True)
    author = tmp_path / "author"
    subprocess.run(["git", "clone", "-q", str(origin), str(author)], check=True, capture_output=True)
    commit(author, {"code.py": "VERSION = 1\n", "drafts/old.md": POST.format(hook="The old post, 1 of them.")})
    laptop = tmp_path / "laptop"
    subprocess.run(["git", "clone", "-q", str(origin), str(laptop)], check=True)
    return author, laptop


def changed_paths(repo: pathlib.Path) -> set[str]:
    return {line[3:] for line in git(repo, "status", "--porcelain", "-uall").splitlines()}


def test_only_drafts_arrive_when_code_changes_alongside(repos: tuple[pathlib.Path, pathlib.Path]) -> None:
    author, laptop = repos
    head = git(laptop, "rev-parse", "HEAD")
    commit(
        author,
        {
            "code.py": "VERSION = 2\n",
            "scripts/evil.py": "raise SystemExit\n",
            "drafts/new.md": POST.format(hook="A new post, 2 of them."),
        },
    )

    fetch_drafts(laptop)

    assert (laptop / "drafts/new.md").exists()
    assert (laptop / "code.py").read_text(encoding="utf-8") == "VERSION = 1\n"
    assert not (laptop / "scripts").exists()
    assert git(laptop, "rev-parse", "HEAD") == head
    assert changed_paths(laptop) and all(p.startswith("drafts/") for p in changed_paths(laptop))


def test_a_local_edit_to_a_draft_is_not_overwritten(repos: tuple[pathlib.Path, pathlib.Path]) -> None:
    author, laptop = repos
    commit(author, {"drafts/old.md": POST.format(hook="Rewritten upstream, 3 times.")})
    (laptop / "drafts/old.md").write_text("my unsaved edit, 4\n", encoding="utf-8")

    with pytest.raises(PullError, match="old.md"):
        fetch_drafts(laptop)

    assert (laptop / "drafts/old.md").read_text(encoding="utf-8") == "my unsaved edit, 4\n"


def test_imported_posts_land_as_drafted(repos: tuple[pathlib.Path, pathlib.Path], tmp_path: pathlib.Path) -> None:
    author, laptop = repos
    commit(author, {"drafts/new.md": POST.format(hook="A new post, 2 of them.")})
    db = tmp_path / "agent.db"

    results = pull(laptop, db)

    assert sum(r.imported for r in results) == 2
    _, drafts = open_stores(db)
    assert {d.state for d in drafts.list_all()} == {DraftState.DRAFTED}


def test_running_it_again_imports_nothing_twice(
    repos: tuple[pathlib.Path, pathlib.Path], tmp_path: pathlib.Path
) -> None:
    author, laptop = repos
    db = tmp_path / "agent.db"
    pull(laptop, db)
    commit(author, {"drafts/new.md": POST.format(hook="A new post, 2 of them.")})

    second = pull(laptop, db)
    third = pull(laptop, db)

    assert [r.title for r in second if r.imported] == ["LinkedIn"]
    assert not any(r.imported for r in third)
    _, drafts = open_stores(db)
    hooks = [d.hook for d in drafts.list_all()]
    assert len(hooks) == len(set(hooks)) == 2


def test_a_failed_pull_does_not_stop_the_studio(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def offline() -> str:
        raise PullError("git fetch failed: could not resolve host")

    monkeypatch.setattr(serve, "pull_drafts_now", offline)

    serve.pull_drafts_at_startup()

    assert "not pulled" in capsys.readouterr().out
