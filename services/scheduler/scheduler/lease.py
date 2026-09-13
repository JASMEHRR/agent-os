"""Which copy is allowed to run the jobs.

The moment anything runs in the background, two copies of it can exist: the
studio you have open, and the watcher you set to start at login. Both would
poll the same mailbox, and while the watermark stops the second one seeing
anything new, a genuine race between them would text you twice about the same
email. Duplicate alerts are the most annoying failure this program could have,
since the whole point of it is to be worth trusting when it buzzes.

So one copy holds a lease and the others stand down.

It is a **lease, not a lock**, and that word is the design. A lock file has to
be released, and a process killed with the plug does not release anything - the
next start then finds a lock held by nobody and either refuses forever or
ignores it, and neither is right. A lease expires on its own: the holder
renews it on every tick, and if the renewals stop for long enough, somebody
else may take it. Kill the studio however you like and the watcher picks the
work up within a minute.

It lives in the database rather than the filesystem because that is the thing
both copies already share, and because `os.kill(pid, 0)` - the usual way to
ask whether a lock's owner is alive - actually terminates the process on
Windows. A liveness check that kills what it is checking is not one.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from persistence.repository import NotFound, Repository

#: One row, one lease. There is only ever one set of jobs to run.
LEASE_ID = "scheduler"

#: How long a lease survives without a renewal. Three missed heartbeats:
#: long enough that a slow tick or a laptop briefly asleep does not hand the
#: work to another copy, short enough that a killed studio frees it within a
#: minute and a half.
STALE_AFTER = timedelta(seconds=90)


def _utcnow() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class Lease:
    """Who is running the jobs, and when they last said so."""

    holder: str
    took_at: datetime
    beat_at: datetime
    #: For the panel: "Post Studio" or "the background watcher". A copy that
    #: has stood down should be able to say what it stood down *to*.
    describes: str = ""


@dataclass
class Leases:
    """This copy's claim on the jobs."""

    store: Repository[Lease]
    #: What this copy calls itself on screen.
    describes: str = ""
    #: Unique per process. A restarted copy is a different holder, which is
    #: correct: it has its own scheduler and its own idea of what has run.
    holder: str = ""
    now: Callable[[], datetime] = _utcnow
    stale_after: timedelta = STALE_AFTER

    def __post_init__(self) -> None:
        self.holder = self.holder or uuid.uuid4().hex

    def _current(self) -> Lease | None:
        try:
            return self.store.get(LEASE_ID)
        except NotFound:
            return None

    def held_by_other(self) -> str:
        """What another live copy calls itself, or "" if the work is free.

        Returns the description rather than a boolean because the only caller
        is a screen that has to say who, and a boolean would send it back for
        the row it just read.
        """
        current = self._current()
        if current is None or current.holder == self.holder:
            return ""
        if self.now() - current.beat_at >= self.stale_after:
            return ""
        return current.describes or "another copy"

    def claim(self) -> bool:
        """Takes the lease if it is free or expired. True if this copy holds it."""
        if self.held_by_other():
            return False
        when = self.now()
        current = self._current()
        # `took_at` is kept across a renewal so the panel can say how long this
        # copy has been running rather than how long ago it last ticked.
        took = current.took_at if current is not None and current.holder == self.holder else when
        self.store.save(LEASE_ID, Lease(self.holder, took, when, self.describes))
        return True

    def beat(self) -> None:
        """Renews the lease. Silently does nothing if this copy lost it.

        Losing a lease mid-run is possible - a laptop asleep past the stale
        window, another copy taking over - and the right response is to stop
        claiming rather than to fight for it back. `Scheduler` checks
        `held_by_other` on each tick, so the loser stands down on its own.
        """
        if self.held_by_other():
            return
        self.claim()

    def release(self) -> None:
        """Gives the lease up on a clean shutdown, so the next copy need not
        wait out the stale window."""
        current = self._current()
        if current is not None and current.holder == self.holder:
            self.store.delete(LEASE_ID)
