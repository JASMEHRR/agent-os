"""The scheduler, tested without waiting for real time to pass.

Almost everything here drives `tick(at=...)` with an explicit clock, because a
test that sleeps to observe a cadence is slow and flaky at once. Two tests do
start a real thread - they are the only way to check that starting and
stopping work - and both assert on an event rather than on a duration.
"""

from __future__ import annotations

import threading
from datetime import UTC, datetime, timedelta

import pytest

from persistence.in_memory import InMemoryRepository
from scheduler.jobs import MAX_BACKOFF, Job, JobState, Outcome
from scheduler.runner import Scheduler, every, schedule

NOW = datetime(2026, 9, 13, 9, 0, tzinfo=UTC)


def counting(name: str = "poll", minutes: float = 5, fails: bool = False) -> tuple[Job, list[int]]:
    """A job that records every call, so the tests can count runs."""
    calls: list[int] = []

    def run() -> str:
        calls.append(1)
        if fails:
            raise RuntimeError("mailbox refused the connection")
        return f"ran {len(calls)}"

    return Job(job_id=name, label=name.title(), every=every(minutes), run=run), calls


class Clock:
    """A hand the tests can move. Every cadence assertion turns on the
    scheduler reading this rather than the wall, so it is the one piece of
    scaffolding worth a name."""

    def __init__(self, at: datetime = NOW) -> None:
        self.at = at

    def __call__(self) -> datetime:
        return self.at


def built(job: Job) -> tuple[Scheduler, Clock]:
    clock = Clock()
    return Scheduler(jobs=(job,), states=InMemoryRepository(), now=clock), clock


# --------------------------------------------------------------- being due


def test_a_job_that_has_never_run_is_due_at_once() -> None:
    """Opening the app should poll, not wait five minutes to start."""
    job, calls = counting()
    scheduler, clock = built(job)
    scheduler.tick()
    assert calls == [1]


def test_a_job_is_not_due_again_until_its_cadence_has_passed() -> None:
    job, calls = counting(minutes=5)
    scheduler, clock = built(job)
    scheduler.tick()
    clock.at = NOW + timedelta(minutes=4)
    scheduler.tick()
    assert calls == [1], "ran again four minutes into a five-minute cadence"


def test_a_job_is_due_again_once_its_cadence_has_passed() -> None:
    job, calls = counting(minutes=5)
    scheduler, clock = built(job)
    scheduler.tick()
    clock.at = NOW + timedelta(minutes=6)
    scheduler.tick()
    assert len(calls) == 2


def test_the_cadence_survives_a_restart() -> None:
    """The point of persisting state: reopening the app must not re-poll.

    A fresh `Scheduler` over the same repository is exactly what the second
    run of the process builds, and it should pick the cadence up mid-stride.
    """
    states: InMemoryRepository[JobState] = InMemoryRepository()
    first, first_calls = counting(minutes=30)
    Scheduler(jobs=(first,), states=states, now=lambda: NOW).tick()
    assert first_calls == [1]

    second, second_calls = counting(minutes=30)
    two_minutes_later = NOW + timedelta(minutes=2)
    Scheduler(jobs=(second,), states=states, now=lambda: two_minutes_later).tick()
    assert second_calls == [], "polled again two minutes into a half-hour cadence"


# ------------------------------------------------------------------ failure


def test_a_failing_job_is_recorded_rather_than_raised() -> None:
    job, calls = counting(fails=True)
    scheduler, clock = built(job)
    scheduler.tick()
    state = scheduler.state_of("poll")
    assert calls == [1]
    assert state.outcome is Outcome.FAILED
    assert "RuntimeError" in state.detail and "refused" in state.detail


def test_one_failing_job_does_not_stop_the_others() -> None:
    """The property the whole design turns on: a bad mailbox must not switch
    off the deadline reminders."""
    bad, bad_calls = counting("mail", fails=True)
    good, good_calls = counting("deadlines")
    scheduler = Scheduler(jobs=(bad, good), states=InMemoryRepository(), now=lambda: NOW)
    scheduler.tick()
    assert bad_calls == [1] and good_calls == [1]


def test_failures_back_off_and_a_success_clears_them() -> None:
    state = JobState(job_id="poll")
    assert state.wait(every(5)) == every(5)
    assert JobState(job_id="poll", failures=1).wait(every(5)) == every(10)
    assert JobState(job_id="poll", failures=2).wait(every(5)) == every(20)


def test_backing_off_never_makes_a_job_more_frequent() -> None:
    """A daily scan that fails must not become hourly.

    `min(grown, MAX_BACKOFF)` alone would do exactly that, which is why the
    cap is applied with `max(every, ...)` around it.
    """
    daily = timedelta(days=1)
    assert JobState(job_id="scan", failures=3).wait(daily) >= daily


def test_backoff_is_capped() -> None:
    assert JobState(job_id="poll", failures=99).wait(every(1)) == MAX_BACKOFF


def test_a_failing_job_waits_longer_before_its_next_attempt() -> None:
    job, calls = counting(minutes=5, fails=True)
    scheduler, clock = built(job)
    scheduler.tick()
    clock.at = NOW + timedelta(minutes=6)
    scheduler.tick()
    assert calls == [1], "retried on the plain cadence instead of backing off"
    clock.at = NOW + timedelta(minutes=11)
    scheduler.tick()
    assert len(calls) == 2


# -------------------------------------------------------------------- owner


def test_a_paused_job_never_becomes_due() -> None:
    job, calls = counting()
    scheduler, clock = built(job)
    scheduler.pause("poll")
    scheduler.tick()
    assert calls == []
    assert scheduler.state_of("poll").next_run(job.every, scheduler.floor) is None


def test_run_now_ignores_the_cadence() -> None:
    job, calls = counting(minutes=60)
    scheduler, clock = built(job)
    scheduler.tick()
    scheduler.run_job("poll")
    assert len(calls) == 2


def test_run_now_does_not_override_a_pause() -> None:
    """The button that runs a paused job is the resume button."""
    job, calls = counting()
    scheduler, clock = built(job)
    scheduler.pause("poll")
    scheduler.run_job("poll")
    assert calls == []


def test_resuming_clears_the_backoff() -> None:
    job, _ = counting(fails=True)
    scheduler, clock = built(job)
    scheduler.tick()
    scheduler.pause("poll")
    assert scheduler.state_of("poll").failures == 1
    assert scheduler.resume("poll").failures == 0


def test_an_unknown_job_is_an_error_rather_than_a_silent_no_op() -> None:
    scheduler = Scheduler(jobs=(), states=InMemoryRepository(), now=lambda: NOW)
    with pytest.raises(KeyError):
        scheduler.job("nothing")


# ------------------------------------------------------------------- thread


def test_start_runs_a_job_without_waiting_for_the_heartbeat() -> None:
    """Opening the app should do something immediately, not in thirty seconds."""
    ran = threading.Event()

    def mark() -> str:
        ran.set()
        return "done"

    job = Job(job_id="poll", label="Poll", every=every(5), run=mark)
    scheduler = Scheduler(jobs=(job,), states=InMemoryRepository(), heartbeat=timedelta(seconds=30))
    scheduler.start()
    try:
        assert ran.wait(timeout=5), "the first tick did not happen"
        assert scheduler.running
    finally:
        scheduler.stop()
    assert not scheduler.running


def test_stopping_is_prompt() -> None:
    """A loop that slept would take its full heartbeat to notice; this waits."""
    job = Job(job_id="poll", label="Poll", every=every(5), run=lambda: "done")
    scheduler = Scheduler(jobs=(job,), states=InMemoryRepository(), heartbeat=timedelta(seconds=30))
    scheduler.start()
    started_at = datetime.now(UTC)
    scheduler.stop()
    assert (datetime.now(UTC) - started_at).total_seconds() < 5


def test_a_scheduler_with_no_jobs_does_not_start_a_thread() -> None:
    scheduler = Scheduler(jobs=(), states=InMemoryRepository())
    scheduler.start()
    assert not scheduler.running


def test_the_loop_survives_a_broken_repository() -> None:
    """`run_job` catches what jobs raise, so reaching the loop's own handler
    means the machinery failed - most likely the database. It must log and
    carry on rather than switching every agent off."""
    said: list[str] = []

    class Broken(InMemoryRepository[JobState]):
        def get(self, entity_id: str) -> JobState:
            raise OSError("database is locked")

    job, _ = counting()
    scheduler = Scheduler(jobs=(job,), states=Broken(), now=lambda: NOW, log=said.append)
    scheduler._safely_tick()
    assert said and "database is locked" in said[0]


# ---------------------------------------------------------------- composing


def test_schedule_drops_the_jobs_an_unconfigured_agent_did_not_produce() -> None:
    job, _ = counting()
    assert schedule([job, None, None]).jobs == (job,)
