"""Your week, read from your commits, so you do not have to type it.

You already write a record of what you did every day. It is called the commit
log, and it is more specific than anything anyone writes from memory on a
Friday. This turns the last N days of commit messages across your repositories
into a note the studio can draft from.

Reads git history only. Never file contents. That distinction is enforced by
construction rather than by policy: the only subprocess this module runs is
`git log`, and it is given a fixed argument list with nothing user-supplied
in it except the repository path and the day count.

Why commit messages specifically, rather than diffs: a diff says what changed,
a commit message says what you were trying to do and often why. The second is
what a post is made of. It also means the quality of the note tracks the
quality of your commit messages, which is a good incentive to have.
"""

from __future__ import annotations

import dataclasses
import pathlib
import shutil
import subprocess  # nosec B404 - fixed argv, no shell, see module docstring
from datetime import UTC, datetime

#: Merge commits and automated noise say nothing about the week.
SKIP_PREFIXES = ("Merge ", "merge ", "Bump ", "bump ", "chore(release)", "Auto-", "[bot]")

#: A repository with fewer commits than this in the window is not a story.
MIN_COMMITS_TO_MENTION = 2


@dataclasses.dataclass(frozen=True)
class RepoActivity:
    name: str
    path: str
    commits: tuple[str, ...]
    #: When git could not be read, why. Reported rather than swallowed, so a
    #: repository that silently dropped out of the note is not mistaken for
    #: one where nothing happened.
    error: str = ""


def read_repo(path: pathlib.Path, days: int) -> RepoActivity:
    """Commit subjects from one repository over the window."""
    name = path.name
    if not (path / ".git").exists():
        return RepoActivity(name, str(path), (), "not a git repository")
    # Resolved to an absolute path rather than trusting PATH lookup. A partial
    # name would run whatever "git" happens to be first on the PATH of the
    # process that launched this, which on a shared machine is not always the
    # git you meant.
    git = shutil.which("git")
    if git is None:
        return RepoActivity(name, str(path), (), "git is not installed")
    try:
        completed = subprocess.run(  # nosec B603 - absolute executable, fixed argv, no shell
            [
                git,
                "-C",
                str(path),
                "log",
                f"--since={days} days ago",
                "--no-merges",
                "--format=%s",
            ],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return RepoActivity(name, str(path), (), f"git failed: {exc}")
    if completed.returncode != 0:
        return RepoActivity(name, str(path), (), completed.stderr.strip()[:200] or "git returned an error")

    subjects = tuple(
        line.strip()
        for line in completed.stdout.splitlines()
        if line.strip() and not line.strip().startswith(SKIP_PREFIXES)
    )
    return RepoActivity(name, str(path), subjects)


def read_repos(paths: list[pathlib.Path], days: int = 7) -> list[RepoActivity]:
    return [read_repo(p, days) for p in paths]


def to_note(activity: list[RepoActivity], days: int = 7) -> str:
    """Renders activity as a note in the shape the studio expects.

    Deliberately plain. The studio's job is to turn facts into a post; this
    module's job is only to get the facts onto the page. A note that already
    reads like a post would give the model something to paraphrase instead of
    something to write from.

    Counts are included because the voice gates demand a real number, and the
    number of commits is one the note can honestly supply.
    """
    lines: list[str] = [f"What I did in the last {days} days, from my commit history."]
    total = 0
    for repo in activity:
        if repo.error:
            continue
        if len(repo.commits) < MIN_COMMITS_TO_MENTION:
            continue
        total += len(repo.commits)
        lines.append("")
        lines.append(f"{repo.name}: {len(repo.commits)} commits.")
        # Newest first is how git reports them; the story reads better oldest
        # first, because that is the order the work happened in.
        for subject in reversed(repo.commits[:25]):
            lines.append(f"- {subject}")
    if total == 0:
        return ""
    lines.append("")
    lines.append(
        f"{total} commits across {sum(1 for r in activity if len(r.commits) >= MIN_COMMITS_TO_MENTION)} projects."
    )
    return "\n".join(lines)


def capture_week(paths: list[pathlib.Path], days: int = 7) -> tuple[str, list[RepoActivity]]:
    """The note and the activity it was made from, so the interface can show
    both: the note to draft from, and which repositories were quiet or broken."""
    activity = read_repos(paths, days)
    return to_note(activity, days), activity


def stamp() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d")
