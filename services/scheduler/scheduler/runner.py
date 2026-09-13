"""The loop that makes the agents autonomous.

Before this, every agent could do its work and none of them ever started. The
inbox was checked when somebody pressed "check now"; the deadline reminders
fired when somebody opened the tab. An agent that only runs while you are
watching it is a tool, not an agent, and closing the window turned the whole
thing off.

This is the missing half: a background thread that asks each job whether it is
due and runs the ones that are.

Five properties it has to have, each of which cost something to get right:

**A failing job cannot stop the others.** Every run is wrapped; an exception
is recorded against that job and the loop continues. A scheduler that dies on
one bad mailbox would silently switch off deadline reminders too, which is a
far worse failure than the one it was reacting to.

**A failing job backs off.** See `JobState.wait`. Retrying a refused
connection every minute all night achieves nothing except a log nobody can
read and, for some providers, a rate limit.

**Stopping is prompt.** The loop waits on an `Event` rather than sleeping, so
closing the app returns immediately instead of after the remaining heartbeat.
A daemon thread would exit anyway, but not before finishing a half-written
database row.

**Nothing runs twice at once.** One lock guards execution, so the "run now"
button pressed while the loop is mid-tick waits its turn rather than sending
the same alert from two threads. The cost is that a slow job delays the
others by its own duration, which is the right trade for jobs measured in
seconds and a heartbeat measured in tens of them.

**Nor twice in two processes.** The studio you have open and the watcher you
set to start at login are both copies of this, and both would poll the same
mailbox. One holds a lease and the others stand down; see `lease.py` for why
it is a lease rather than a lock file.
"""

from __future__ import annotations

import threading
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from persistence.repository import NotFound, Repository
from scheduler.jobs import Job, JobState, failed, started, succeeded
from scheduler.lease import Leases

#: How often the loop wakes to ask what is due. Not a job's cadence - the
#: finest granularity the scheduler can resolve. Thirty seconds keeps a
#: five-minute mailbox poll honest while costing essentially nothing.
HEARTBEAT = timedelta(seconds=30)


def _utcnow() -> datetime:
    return datetime.now(UTC)


@dataclass
class Scheduler:
    """Runs jobs on their cadences, in a background thread."""

    jobs: tuple[Job, ...] = ()
    #: Where run history lives. Persisted, so cadences survive a restart;
    #: an in-memory repository is a perfectly good scheduler that forgets.
    states: Repository[JobState] | None = None
    now: Callable[[], datetime] = _utcnow
    heartbeat: timedelta = HEARTBEAT
    #: Where the loop's own trouble goes. Print by default; the studio passes
    #: something that reaches the page.
    log: Callable[[str], None] = print
    #: Which copy is allowed to run these jobs. None means "assume this is the
    #: only one", which is right for a test and for a single process; with one
    #: supplied, a second copy stands down instead of texting you twice.
    lease: Leases | None = None

    _thread: threading.Thread | None = field(default=None, init=False, repr=False)
    _stop: threading.Event = field(default_factory=threading.Event, init=False, repr=False)
    _lock: threading.RLock = field(default_factory=threading.RLock, init=False, repr=False)
    #: When this scheduler came into existence. A job that has never run is
    #: due from here, not from the epoch.
    _floor: datetime | None = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        # Set here rather than lazily on first read, which was a trap worth
        # recording: `due()` computed `when = self.now()` and *then* touched
        # `self.floor`, so on a fresh scheduler the floor landed a few
        # microseconds after the moment it was being compared against and
        # nothing was ever due on the first call. `start()` happened to hide
        # it by setting the floor first; `tick()` called directly - which is
        # exactly what `watch.py --once` does - did not.
        self._floor = self.now()

    # ------------------------------------------------------------------ state

    @property
    def floor(self) -> datetime:
        if self._floor is None:  # pragma: no cover - __post_init__ always sets it
            self._floor = self.now()
        return self._floor

    def job(self, job_id: str) -> Job:
        for job in self.jobs:
            if job.job_id == job_id:
                return job
        raise KeyError(f"no job called '{job_id}'")

    def state_of(self, job_id: str) -> JobState:
        """The remembered state, or a blank one for a job never yet run.

        The blank one honours `starts_paused`, and only the blank one: once a
        row exists it is the answer, so a job the owner switched on stays on
        through every restart.
        """
        blank = JobState(job_id=job_id, paused=self._starts_paused(job_id))
        if self.states is None:
            return blank
        try:
            return self.states.get(job_id)
        except NotFound:
            return blank

    def _starts_paused(self, job_id: str) -> bool:
        return any(j.starts_paused for j in self.jobs if j.job_id == job_id)

    def _remember(self, state: JobState) -> JobState:
        if self.states is not None:
            self.states.save(state.job_id, state)
        return state

    def due(self, at: datetime | None = None) -> list[Job]:
        when = at or self.now()
        return [j for j in self.jobs if self.state_of(j.job_id).is_due(j.every, when, self.floor)]

    # ----------------------------------------------------------------- running

    def run_job(self, job_id: str) -> JobState:
        """Runs one job now, whatever its cadence says.

        Ignores the cadence but *not* the pause: a paused job is one the owner
        switched off, and the button that runs it is the resume button.
        """
        with self._lock:
            job = self.job(job_id)
            state = self.state_of(job_id)
            if state.paused:
                return state
            self._remember(started(state, self.now()))
            try:
                detail = job.run()
            except Exception as exc:  # noqa: BLE001 - see the module docstring
                # The type name is included because "connection refused" alone
                # does not say which of a dozen things refused it.
                return self._remember(failed(state, self.now(), f"{type(exc).__name__}: {exc}"))
            return self._remember(succeeded(state, self.now(), detail or "done"))

    def tick(self, at: datetime | None = None) -> list[JobState]:
        """Runs everything due once. The whole loop, minus the thread.

        Checked on every tick rather than once at startup: a copy can lose the
        lease mid-run - a laptop asleep past the stale window, another copy
        taking over - and the right response is to stop running the jobs, not
        to keep going on a claim that has moved on.
        """
        if self.lease is not None:
            if self.lease.held_by_other():
                return []
            self.lease.beat()
        when = at or self.now()
        return [self.run_job(job.job_id) for job in self.due(when)]

    @property
    def stood_down_to(self) -> str:
        """What other copy is running these jobs, or "" if this one is."""
        return self.lease.held_by_other() if self.lease is not None else ""

    # ------------------------------------------------------------------ owner

    def pause(self, job_id: str) -> JobState:
        state = self.state_of(job_id)
        return self._remember(
            JobState(
                job_id=state.job_id,
                last_started=state.last_started,
                last_finished=state.last_finished,
                outcome=state.outcome,
                detail=state.detail,
                failures=state.failures,
                paused=True,
            )
        )

    def resume(self, job_id: str) -> JobState:
        """Unpauses, and clears the failure count with it.

        Resuming is the owner saying they have dealt with whatever was wrong.
        Keeping the backoff would mean a fixed mailbox sat untouched for
        another hour with no way to say so.
        """
        state = self.state_of(job_id)
        return self._remember(
            JobState(
                job_id=state.job_id,
                last_started=state.last_started,
                last_finished=state.last_finished,
                outcome=state.outcome,
                detail=state.detail,
                failures=0,
                paused=False,
            )
        )

    # ----------------------------------------------------------------- thread

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> bool:
        """Starts the loop. Ticks once immediately, then on the heartbeat.

        The loop starts even when another copy holds the lease, and this is
        the fix for a bug that was invisible until two processes were run for
        real: refusing to start meant that closing the watcher left the studio
        sitting there forever, having decided once, at open, that somebody
        else had the work. Whether to run is a per-tick question, so `tick`
        asks it and this does not. An idle loop costs a wakeup every thirty
        seconds, and buys a studio that picks the jobs up within one of them.
        """
        if self.running or not self.jobs:
            return False
        self._floor = self.now()
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="agent-os-scheduler", daemon=True)
        self._thread.start()
        return True

    def stop(self, timeout: float = 5.0) -> None:
        self._stop.set()
        thread, self._thread = self._thread, None
        if thread is not None:
            thread.join(timeout=timeout)
        # After the thread is down, never before: releasing while it could
        # still tick would let another copy start on top of this one.
        if self.lease is not None:
            self.lease.release()

    def _loop(self) -> None:
        self._safely_tick()
        # `wait` returns True only when stop was set, so this exits promptly
        # on shutdown and loops on every timeout.
        while not self._stop.wait(self.heartbeat.total_seconds()):
            self._safely_tick()

    def _safely_tick(self) -> None:
        try:
            self.tick()
        except Exception as exc:  # noqa: BLE001 - the loop must outlive anything a job does
            # `run_job` already catches what jobs raise, so reaching here means
            # the scheduler's own machinery failed - most likely the database.
            # Logging and continuing is right: the next tick may well work,
            # and a dead scheduler switches off every agent at once.
            self.log(f"scheduler: {type(exc).__name__}: {exc}")


def every(minutes: float) -> timedelta:
    """Reads better at the call site than `timedelta(minutes=...)` in a list."""
    return timedelta(minutes=minutes)


def schedule(
    jobs: Iterable[Job | None],
    states: Repository[JobState] | None = None,
    lease: Leases | None = None,
) -> Scheduler:
    """Builds a scheduler from jobs, dropping the ones that are None.

    Composition hands this whatever the configured agents produced, and an
    agent that is not set up contributes `None` rather than a job that would
    fail on every tick. Accepting the Nones here keeps that decision at the
    one place that knows which agents exist.
    """
    return Scheduler(jobs=tuple(job for job in jobs if job is not None), states=states, lease=lease)
