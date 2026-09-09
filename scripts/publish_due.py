"""Sends the posts you approved and scheduled, when their time comes.

    python scripts/publish_due.py           # send anything due now
    python scripts/publish_due.py --list    # show the queue, send nothing
    python scripts/publish_due.py --dry-run # say what would go, send nothing

This is the one piece of the system that acts without you present, so it is
worth being exact about what it can and cannot do.

It can send a draft you approved, at the time you chose. It cannot send
anything else. Not because this file is careful, but because it asks
`PostDraft.mark_published`, which raises for any state a human did not put the
draft into. Point it at a database full of unapproved drafts and it publishes
nothing at all.

Run it from Windows Task Scheduler every fifteen minutes or so. Precision is
not the point: a post going out at 9:07 rather than 9:00 costs nothing, and a
schedule that fires often enough to feel instant would spend the whole day
opening a database to find nothing in it. Nothing is lost when the machine is
asleep either, because a due post stays due, so the first run after it wakes
sends what was missed rather than skipping it.
"""

from __future__ import annotations

import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

import conftest  # noqa: E402, F401 - imported for the sys.path setup it performs
from content_agent import PostDraft, WeeklyNote  # noqa: E402
from content_agent.schedule import Scheduler  # noqa: E402
from persistence import SQLiteRepository, open_database  # noqa: E402
from scripts.env_file import load as load_env  # noqa: E402
from scripts.linkedin_post import post_text  # noqa: E402
from scripts.serve import DB_PATH  # noqa: E402


def build_scheduler() -> Scheduler:
    """The queue, over the same database the studio writes to.

    Only the drafts table is opened. The runner has no use for notes, samples
    or the persona, and a process that runs unattended should be able to touch
    as little as possible.
    """
    connection = open_database(DB_PATH)
    # Registered so the table exists even on a database whose studio has not
    # written a note yet; the repository creates its table on construction.
    SQLiteRepository(connection, "linkedin_notes", WeeklyNote)
    return Scheduler(SQLiteRepository(connection, "linkedin_drafts", PostDraft))


def show(scheduler: Scheduler) -> int:
    queued = scheduler.queue()
    if not queued:
        print("\n  Nothing scheduled.\n")
        return 0
    due = {d.draft_id for d in scheduler.due()}
    print(f"\n  {len(queued)} scheduled, {len(due)} due now\n")
    for draft in queued:
        when = draft.scheduled_for.isoformat(timespec="minutes") if draft.scheduled_for else "?"
        marker = "DUE " if draft.draft_id in due else "    "
        first_line = draft.hook.splitlines()[0] if draft.hook else "(no hook)"
        print(f"  {marker}{when}  {draft.channel.value:<10} {first_line[:60]}")
    print("")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    load_env()
    scheduler = build_scheduler()

    if "--list" in args:
        return show(scheduler)

    due = scheduler.due()
    if not due:
        # Silent-ish on purpose: this runs every fifteen minutes and a line of
        # output each time turns the Task Scheduler history into noise.
        print("nothing due")
        return 0

    if "--dry-run" in args:
        for draft in due:
            print(f"  would post {draft.draft_id} ({draft.channel.value}): {draft.hook[:60]}")
        return 0

    failures = 0
    for result in scheduler.publish_due(post_text):
        if result.published:
            print(f"  posted {result.draft_id} {result.url}")
        else:
            failures += 1
            # The draft is already in PUBLISH_FAILED carrying this reason, so
            # the studio shows it next time it is opened. Printing it too is
            # for whoever is reading the Task Scheduler log.
            print(f"  FAILED {result.draft_id}: {result.error}", file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
