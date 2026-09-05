"""Clones of your other repositories, for a copy of the studio that does not
live on your laptop.

On your machine the "pull from git" button reads the checkouts beside this
one. A hosted copy has no such neighbours, so it is given URLs instead and
keeps its own clones, refreshed before every capture so the week it reads is
the current one rather than the one from deploy day.

Two git invocations, `clone` and `pull --ff-only`, each with a fixed argument
list and no shell. `--` ends option parsing before the URL, so a URL that
starts with a dash is a URL and not a flag. Nothing here reads file contents;
capture reads the log, and only the log.
"""

from __future__ import annotations

import dataclasses
import os
import pathlib
import shutil
import subprocess  # nosec B404 - fixed argv, no shell, see module docstring

#: A person is waiting behind the capture request, so a remote that does not
#: answer is given up on rather than waited for.
TIMEOUT_SECONDS = 120


@dataclasses.dataclass(frozen=True)
class SyncResult:
    url: str
    path: str
    #: Empty on success. A failure is reported, not raised: one unreachable
    #: remote must not take the capture of the others down with it.
    error: str = ""


def repo_name(url: str) -> str:
    """`https://github.com/you/thing.git` becomes `thing`."""
    tail = url.strip().rstrip("/").rsplit("/", 1)[-1]
    return tail[:-4] if tail.endswith(".git") else tail


def sync_repo(url: str, root: pathlib.Path) -> SyncResult:
    """Clones `url` under `root` if it is not there, pulls it if it is."""
    name = repo_name(url)
    dest = root / name
    if not name or name in (".", "..") or "\\" in name:
        return SyncResult(url, str(dest), "cannot derive a repository name from the URL")
    git = shutil.which("git")
    if git is None:
        return SyncResult(url, str(dest), "git is not installed")

    if (dest / ".git").exists():
        argv = [git, "-C", str(dest), "pull", "--ff-only", "--quiet"]
    else:
        root.mkdir(parents=True, exist_ok=True)
        argv = [git, "clone", "--quiet", "--", url, str(dest)]

    # A private repository without credentials must fail, not wait forever
    # on a username prompt that nobody is there to answer.
    env = dict(os.environ, GIT_TERMINAL_PROMPT="0")
    try:
        completed = subprocess.run(  # nosec B603 - absolute executable, fixed argv, no shell
            argv,
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SECONDS,
            check=False,
            env=env,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return SyncResult(url, str(dest), f"git failed: {exc}")
    if completed.returncode != 0:
        # git echoes the URL in its errors. A URL can carry a token, and the
        # error goes to the page, so the name stands in for it.
        message = completed.stderr.strip().replace(url, name)[:200]
        return SyncResult(url, str(dest), message or "git returned an error")
    return SyncResult(url, str(dest))


def sync_repos(urls: tuple[str, ...], root: pathlib.Path) -> list[SyncResult]:
    return [sync_repo(url, root) for url in urls]


__all__ = ["SyncResult", "repo_name", "sync_repo", "sync_repos"]
