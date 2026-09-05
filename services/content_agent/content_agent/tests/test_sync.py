"""Clones for a hosted studio, exercised against a real local repository.

`file://` URLs, so the tests need no network and prove the same argv that
runs against GitHub.
"""

from __future__ import annotations

import os
import pathlib
import subprocess  # nosec B404 - fixtures build a throwaway repo

import pytest

from content_agent.capture import read_repo
from content_agent.sync import repo_name, sync_repo, sync_repos


def git(path: pathlib.Path, *args: str) -> None:
    subprocess.run(  # nosec B603 B607 - test fixture, fixed argv
        ["git", "-C", str(path), *args],
        check=True,
        capture_output=True,
        env={
            "GIT_AUTHOR_NAME": "t",
            "GIT_AUTHOR_EMAIL": "t@t",
            "GIT_COMMITTER_NAME": "t",
            "GIT_COMMITTER_EMAIL": "t@t",
            "PATH": os.environ["PATH"],
        },
    )


def commit(path: pathlib.Path, subject: str) -> None:
    (path / f"{len(list(path.iterdir()))}.txt").write_text("x", encoding="utf-8")
    git(path, "add", ".")
    git(path, "commit", "-q", "-m", subject)


@pytest.fixture
def origin(tmp_path: pathlib.Path) -> pathlib.Path:
    """The repository a hosted studio would be pointed at."""
    path = tmp_path / "ventureadda"
    path.mkdir()
    git(path, "init", "-q")
    commit(path, "Open the front page on the goods")
    commit(path, "Let a price be left out")
    return path


def test_repo_name_is_the_last_path_segment_without_git() -> None:
    assert repo_name("https://github.com/JASMEHRR/ventureadda") == "ventureadda"
    assert repo_name("https://github.com/JASMEHRR/ventureadda.git") == "ventureadda"
    assert repo_name("https://github.com/JASMEHRR/agent-os/") == "agent-os"


def test_first_sync_clones_and_capture_can_read_it(origin: pathlib.Path, tmp_path: pathlib.Path) -> None:
    root = tmp_path / "clones"

    result = sync_repo(origin.as_uri(), root)

    assert result.error == ""
    assert (root / "ventureadda" / ".git").exists()
    assert "Let a price be left out" in read_repo(root / "ventureadda", days=7).commits


def test_second_sync_pulls_what_was_pushed_since(origin: pathlib.Path, tmp_path: pathlib.Path) -> None:
    """The point of refreshing before every capture: a clone made on deploy
    day would otherwise report deploy day's week forever."""
    root = tmp_path / "clones"
    sync_repo(origin.as_uri(), root)
    commit(origin, "Show traffic on the moderator page")

    result = sync_repo(origin.as_uri(), root)

    assert result.error == ""
    assert "Show traffic on the moderator page" in read_repo(root / "ventureadda", days=7).commits


def test_an_unreachable_repository_is_reported_not_raised(tmp_path: pathlib.Path) -> None:
    missing = (tmp_path / "nowhere" / "thing").as_uri()

    result = sync_repo(missing, tmp_path / "clones")

    assert result.error
    assert not (tmp_path / "clones" / "thing" / ".git").exists()


def test_the_error_names_the_repository_not_the_url(tmp_path: pathlib.Path) -> None:
    """A URL can carry a token, and the error goes to the page."""
    url = (tmp_path / "nowhere" / "secretive").as_uri()

    result = sync_repo(url, tmp_path / "clones")

    assert url not in result.error


def test_a_url_with_no_name_is_refused_before_git_runs(tmp_path: pathlib.Path) -> None:
    assert sync_repo("", tmp_path / "clones").error
    assert sync_repo("https://example.com/..", tmp_path / "clones").error


def test_one_bad_url_does_not_stop_the_others(origin: pathlib.Path, tmp_path: pathlib.Path) -> None:
    results = sync_repos(((tmp_path / "nowhere" / "x").as_uri(), origin.as_uri()), tmp_path / "clones")

    assert [bool(r.error) for r in results] == [True, False]
