"""Receives drafts pushed to origin/master and puts them in the Review tab.

    python scripts/pull_drafts.py

Fetches, then checks out `drafts/` and nothing else from origin/master, then
runs the importer over it. Code is never updated this way: a pushed change to
anything outside `drafts/` stays on the remote until you pull it yourself.

Every imported post arrives DRAFTED, exactly as `import_drafts.py` makes it.
Nothing here can approve, schedule or publish; the Review tab is still the
only way forward for a post.

A draft file you have edited locally and not committed is never overwritten.
The pull stops and names it instead, because `git checkout <ref> -- <path>`
replaces a working-tree file without asking.
"""

from __future__ import annotations

import os
import pathlib
import shutil
import subprocess  # nosec B404 - fixed argv, no shell
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from scripts.import_drafts import ImportResult, import_files, open_stores  # noqa: E402
from scripts.serve import DB_PATH  # noqa: E402

REMOTE_REF = "origin/master"
DRAFTS = "drafts/"
TIMEOUT_SECONDS = 60


class PullError(RuntimeError):
    """The pull did not happen. The message is written for the person reading it."""


def _git(repo: pathlib.Path, *args: str) -> str:
    git = shutil.which("git")
    if git is None:
        raise PullError("git is not installed")
    # A remote that wants credentials must fail rather than wait on a prompt
    # nobody is there to answer.
    env = dict(os.environ, GIT_TERMINAL_PROMPT="0")
    try:
        done = subprocess.run(  # nosec B603 - absolute executable, fixed argv, no shell
            [git, "-C", str(repo), *args],
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SECONDS,
            check=False,
            env=env,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise PullError(f"git {args[0]} failed: {exc}") from exc
    if done.returncode != 0:
        raise PullError(f"git {args[0]} failed: {done.stderr.strip()[:200] or 'no message'}")
    return done.stdout


def _lines(text: str) -> set[str]:
    return {line for line in text.splitlines() if line}


def fetch_drafts(repo: pathlib.Path = REPO) -> None:
    """Brings `drafts/` in line with origin/master. Touches no other path."""
    _git(repo, "fetch", "origin")

    incoming = _lines(_git(repo, "ls-tree", "-r", "--name-only", REMOTE_REF, "--", DRAFTS))
    if not incoming:
        return
    # Unstaged edits and untracked files are the local work a checkout would
    # destroy. A file already matching the remote loses nothing.
    local = _lines(_git(repo, "diff", "--name-only", "--", DRAFTS)) | _lines(
        _git(repo, "ls-files", "--others", "--exclude-standard", "--", DRAFTS)
    )
    at_risk = [
        path
        for path in sorted(local & incoming)
        if _git(repo, "hash-object", "--", path).strip() != _git(repo, "rev-parse", f"{REMOTE_REF}:{path}").strip()
    ]
    if at_risk:
        raise PullError(
            f"not pulling drafts: {', '.join(at_risk)} changed locally and would be overwritten. "
            "Commit or move it, then it will pull."
        )

    _git(repo, "checkout", REMOTE_REF, "--", DRAFTS)


def pull(repo: pathlib.Path = REPO, db_path: pathlib.Path = DB_PATH) -> list[ImportResult]:
    fetch_drafts(repo)
    notes, drafts = open_stores(db_path)
    return import_files(sorted((repo / "drafts").glob("*.md")), notes, drafts)


def summary(results: list[ImportResult]) -> str:
    imported = [r.title for r in results if r.imported]
    if not imported:
        return "no new drafts"
    return f"{len(imported)} new draft(s) in Review: {', '.join(imported)}"


def run(repo: pathlib.Path = REPO, db_path: pathlib.Path = DB_PATH) -> str:
    """For the scheduler: a sentence on success, raises on failure."""
    return summary(pull(repo, db_path))


def main() -> int:
    try:
        print(f"\n  {run()}\n")
    except PullError as exc:
        print(f"\n  {exc}\n", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
