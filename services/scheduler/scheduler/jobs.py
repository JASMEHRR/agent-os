"""What a recurring job is, and what is remembered about it between runs.

Two types, deliberately separate.

`Job` is the *definition*: a name, a cadence, and the callable that does the
work. It holds a function, so it can never be written to a database; it is
supplied fresh every time the process starts, by whoever composes the agents.

`JobState` is what is *remembered*: when the job last ran, whether it worked,
and whether the owner has paused it. It is a frozen dataclass of plain values,
so it persists like every other record in this system.

Keeping them apart is what lets the cadence survive a restart. Close the app
at 10:00 with the mailbox polled a minute ago and reopen it at 10:02, and the
inbox job waits four more minutes rather than polling again on the way up -
because the state came back from disk while the definition was rebuilt.
"""

from __future__ import annotations

import enum
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta

#: A failing job is retried more slowly each time, but never slower than this.
#: An hour is long enough that a mailbox refusing connections all night costs
#: a handful of attempts, and short enough that fixing the cause at breakfast
#: does not mean waiting until lunch for the agent to notice.
MAX_BACKOFF = timedelta(hours=1)

#: Consecutive failures after which the backoff stops doubling. 2**6 is 64
#: times the cadence, which is past `MAX_BACKOFF` for any sane interval; the
#: cap exists so the arithmetic cannot overflow into a timedelta that raises.
BACKOFF_CEILING = 6

#: How much of a job's message is kept. Long enough for a real sentence,
#: short enough that a stack trace or an HTML error page cannot bloat the row.
DETAIL_LIMIT = 300


class Outcome(enum.Enum):
    """How a job's last attempt ended."""

    NEVER = "never"
    OK = "ok"
    FAILED = "failed"


@dataclass(frozen=True)
class Job:
    """One thing to run on a cadence.

    `run` returns a short human sentence describing what it did - "3 new, 1
    texted" - which is what the panel shows and what makes a scheduler that
    runs unattended legible after the fact. Raising is how a job reports
    failure; the return value is never an error code.
    """

    job_id: str
    label: str
    every: timedelta
    run: Callable[[], str]
    #: One line for the panel, explaining what this job is for.
    describes: str = ""


@dataclass(frozen=True)
class JobState:
    """What is remembered about a job between runs, and across restarts."""

    job_id: str
    last_started: datetime | None = None
    last_finished: datetime | None = None
    outcome: Outcome = Outcome.NEVER
    detail: str = ""
    #: Consecutive failures. Reset to zero by any success, because backoff
    #: should describe the current trouble rather than the year's total.
    failures: int = 0
    #: Switched off by the owner. A paused job keeps its history and its
    #: place; it simply never becomes due.
    paused: bool = False

    def wait(self, every: timedelta) -> timedelta:
        """The gap before the next attempt.

        Normally the job's own cadence. After consecutive failures it doubles
        each time, so a mailbox that is refusing connections is retried at a
        decreasing rate rather than hammered every minute.

        The cap is applied with `max(every, ...)` rather than `min(...)`
        alone, which matters more than it looks: a job whose cadence is
        already longer than `MAX_BACKOFF` - the daily opportunity scan, say -
        would otherwise be made *more* frequent by failing. Backing off must
        never speed anything up.
        """
        if self.failures <= 0:
            return every
        # `1 << n` rather than `2 ** n`: the same doubling, but an int rather
        # than the Any that `**` is typed as, which would leak into the return.
        grown = every * (1 << min(self.failures, BACKOFF_CEILING))
        return max(every, min(grown, MAX_BACKOFF))

    def next_run(self, every: timedelta, floor: datetime) -> datetime | None:
        """When this job is next due, or None while it is paused.

        `floor` is the moment the scheduler started. A job that has never run
        is due then - at once, on the first tick - rather than at some epoch
        date, which would be true but would also make "next run" unreadable
        on a fresh install.
        """
        if self.paused:
            return None
        if self.last_finished is None:
            return floor
        return self.last_finished + self.wait(every)

    def is_due(self, every: timedelta, at: datetime, floor: datetime) -> bool:
        due = self.next_run(every, floor)
        return due is not None and at >= due


def started(state: JobState, at: datetime) -> JobState:
    """The state to record before a job runs.

    Written first, so a process killed mid-run leaves evidence that something
    was in flight rather than looking like it never happened.
    """
    return JobState(
        job_id=state.job_id,
        last_started=at,
        last_finished=state.last_finished,
        outcome=state.outcome,
        detail=state.detail,
        failures=state.failures,
        paused=state.paused,
    )


def succeeded(state: JobState, at: datetime, detail: str) -> JobState:
    return JobState(
        job_id=state.job_id,
        last_started=state.last_started,
        last_finished=at,
        outcome=Outcome.OK,
        detail=detail[:DETAIL_LIMIT],
        failures=0,
        paused=state.paused,
    )


def failed(state: JobState, at: datetime, detail: str) -> JobState:
    return JobState(
        job_id=state.job_id,
        last_started=state.last_started,
        last_finished=at,
        outcome=Outcome.FAILED,
        detail=detail[:DETAIL_LIMIT],
        failures=state.failures + 1,
        paused=state.paused,
    )
