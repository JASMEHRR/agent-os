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

#: Trailers say who helped and which session did it. Neither is the week.
TRAILER_PREFIXES = ("Co-Authored-By:", "Claude-Session:", "Signed-off-by:", "Co-authored-by:")

#: How much of one commit body reaches the note. Long enough for the reason
#: and the specific detail, which is usually the first two paragraphs, short
#: enough that twelve of them do not crowd out the prompt around them.
BODY_CHARS = 700

#: How many commits get their body included. The rest are listed as subjects.
#: A week of fifty commits with every body attached would be most of a prompt
#: and would bury the interesting ones among the typo fixes.
DETAILED_COMMITS = 12

#: A subject with a one-line body is a tidy commit, not an explained one. The
#: bodies worth reading are the ones where somebody argued with themselves.
SUBSTANTIAL_BODY_CHARS = 120


@dataclasses.dataclass(frozen=True)
class Commit:
    """One commit, as the note will use it.

    The body is here because it is where the writing is. A subject says what
    changed; the body says what was tried, what broke, and why it was done
    that way, and a post is made of the second one.
    """

    subject: str
    body: str = ""

    def is_explained(self) -> bool:
        return len(self.body) >= SUBSTANTIAL_BODY_CHARS


@dataclasses.dataclass(frozen=True)
class RepoActivity:
    name: str
    path: str
    entries: tuple[Commit, ...] = ()
    #: When git could not be read, why. Reported rather than swallowed, so a
    #: repository that silently dropped out of the note is not mistaken for
    #: one where nothing happened.
    error: str = ""

    @property
    def commits(self) -> tuple[str, ...]:
        """Subjects only. Kept because counting commits is what most callers
        came for, and they should not have to know a body exists."""
        return tuple(entry.subject for entry in self.entries)


def _clean_body(raw: str) -> str:
    """A commit body with the trailers and the blank runs taken out."""
    lines = [line.rstrip() for line in raw.strip().splitlines()]
    kept = [line for line in lines if not line.strip().startswith(TRAILER_PREFIXES)]
    body = "\n".join(kept).strip()
    if len(body) > BODY_CHARS:
        # Cut at a paragraph if there is one nearby, so the excerpt ends on a
        # thought rather than in the middle of a word.
        window = body[:BODY_CHARS]
        cut = window.rfind("\n\n")
        body = (window[:cut] if cut > BODY_CHARS // 2 else window).rstrip() + " [...]"
    return body


def read_repo(path: pathlib.Path, days: int) -> RepoActivity:
    """Commits from one repository over the window, subjects and bodies."""
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
                # Unit separator between subject and body, record separator
                # between commits. Both are control characters no commit
                # message contains, so the split cannot be confused by a body
                # that happens to have a blank line or a stray delimiter in it.
                "--format=%s%x1f%b%x1e",
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

    entries = []
    for record in completed.stdout.split("\x1e"):
        subject, _, body = record.strip().partition("\x1f")
        subject = subject.strip()
        if not subject or subject.startswith(SKIP_PREFIXES):
            continue
        entries.append(Commit(subject, _clean_body(body)))
    return RepoActivity(name, str(path), tuple(entries))


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

    THE BODIES ARE THE POINT, and for a long time they were missing. A list of
    subjects tells the model what changed and leaves it to invent the texture,
    which produces a post that reads like a changelog with adjectives. The
    body is where the reason is: what was tried, what broke, what was refused
    and why. Only the explained ones are included, most recent first, because
    a body worth reading is one where somebody argued with themselves, and
    fifty of them would crowd out everything else in the prompt.
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

        detailed = [entry for entry in repo.entries if entry.is_explained()][:DETAILED_COMMITS]
        if detailed:
            lines.append("")
            lines.append(f"In my own words, on {len(detailed)} of those:")
            for entry in reversed(detailed):
                lines.append("")
                lines.append(f"## {entry.subject}")
                lines.append(entry.body)
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
