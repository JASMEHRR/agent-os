"""Runs the agents with no browser and no window.

    python scripts/watch.py             # keeps running; Ctrl-C to stop
    python scripts/watch.py --once      # one pass, then exits

The studio runs these same jobs while it is open. This is for the rest of the
day: set it to start at login and your mail is triaged and your deadlines are
watched whether or not you have the app up.

On Windows, Task Scheduler, "When I log on", action `pythonw scripts/watch.py`
(`pythonw`, not `python`, or you get a console window at every login). On a
Mac, a LaunchAgent. `--once` is the cron-shaped mode for anything that prefers
to do the scheduling itself.

Running this at the same time as the studio is fine and is the expected case.
Only one of them will actually poll: they share a lease through the database,
and the copy that does not hold it stands down and says so. Without that, both
would read the same mailbox and you would be texted twice about one email.
"""

from __future__ import annotations

import pathlib
import signal
import sys
import time
import types

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

import conftest  # noqa: E402, F401 - imported for the sys.path setup it performs
from persistence import SQLiteRepository, open_database  # noqa: E402
from scheduler import JobState, Lease, Leases, Scheduler, schedule  # noqa: E402
from scripts.env_file import load as load_env  # noqa: E402
from scripts.serve import DB_PATH, apply_panel, classwork_panel, inbox_panel, jobs  # noqa: E402

#: How long the main loop sleeps between checks that the scheduler is alive.
#: The scheduler has its own heartbeat; this one only has to be short enough
#: that Ctrl-C feels immediate.
IDLE_SECONDS = 1.0


def build() -> tuple[Scheduler, list[str]]:
    load_env()
    connection = open_database(DB_PATH)
    inbox, apply_tab, classwork = inbox_panel(), apply_panel(), classwork_panel()
    scheduler = schedule(
        jobs(inbox, apply_tab, classwork),
        SQLiteRepository(connection, "scheduler_runs", JobState),
        Leases(
            store=SQLiteRepository(connection, "scheduler_lease", Lease),
            describes="the background watcher",
        ),
    )
    return scheduler, [job.job_id for job in scheduler.jobs]


def main() -> int:
    scheduler, names = build()
    if not names:
        print("\n  Nothing is connected yet, so there is nothing to run.")
        print("  Start the studio once and use the Connect screen: python scripts/serve.py\n")
        return 1

    once = "--once" in sys.argv
    print(f"\n  Watching: {', '.join(names)}")

    if once:
        ran = scheduler.tick()
        if scheduler.stood_down_to:
            print(f"  {scheduler.stood_down_to} is already running these. Nothing to do.\n")
            return 0
        for state in ran:
            print(f"  {state.job_id}: {state.detail}")
        if not ran:
            print("  Nothing was due.")
        print("")
        return 0

    scheduler.start()
    if scheduler.stood_down_to:
        # Not an exit. The studio may be closed in a minute, and this copy
        # should take the work over then rather than having given up at start.
        print(f"  {scheduler.stood_down_to} has these for now. Waiting to take over.")
    print("  Running. Ctrl-C to stop.\n")

    # SIGTERM as well as Ctrl-C, because a thing set to start at login is
    # stopped by a service manager rather than by a keystroke, and a stop that
    # skips the shutdown leaves the lease held for its full stale window - a
    # minute and a half in which nothing at all is watching your mail.
    def bow_out(number: int, frame: types.FrameType | None) -> None:
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, bow_out)

    try:
        while scheduler.running:
            time.sleep(IDLE_SECONDS)
    except KeyboardInterrupt:
        print("\n  stopping...")
    finally:
        # Releases the lease, so the studio can pick the work up the moment
        # it opens rather than waiting out the stale window.
        scheduler.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
