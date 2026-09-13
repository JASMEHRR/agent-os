"""The Automatic tab.

Its job is evidence, so these check that the evidence is there and honest: a
job that has never run says so rather than showing a blank that reads like
success, and a job that failed carries the failure's own words.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from persistence.in_memory import InMemoryRepository
from scheduler.jobs import Job
from scheduler.panel import SchedulerPanel
from scheduler.runner import Scheduler, every

NOW = datetime(2026, 9, 13, 9, 0, tzinfo=UTC)


def panel(run: Callable[[], str] | None = None, minutes: float = 5) -> tuple[SchedulerPanel, dict[str, datetime]]:
    clock = {"now": NOW}
    job = Job(
        job_id="mail",
        label="Check my email",
        every=every(minutes),
        run=run or (lambda: "3 new, 1 texted"),
        describes="Reads new mail and texts the important ones",
    )
    scheduler = Scheduler(jobs=(job,), states=InMemoryRepository(), now=lambda: clock["now"])
    return SchedulerPanel(scheduler), clock


def test_a_job_that_has_never_run_says_so() -> None:
    row = panel()[0].state()["jobs"][0]
    assert row["outcome"] == "never"
    assert row["last_run"] == ""
    assert row["in_minutes"] == 0, "a job never run is due now, not at some future time"


def test_a_successful_run_shows_the_jobs_own_sentence() -> None:
    screen, _ = panel()
    screen.scheduler.tick()
    row = screen.state()["jobs"][0]
    assert row["outcome"] == "ok"
    assert row["detail"] == "3 new, 1 texted"
    assert row["in_minutes"] == 5.0


def test_a_failed_run_carries_the_failures_own_words() -> None:
    def explode() -> str:
        raise ConnectionError("connection refused by imap.college.edu")

    screen, _ = panel(explode)
    screen.scheduler.tick()
    row = screen.state()["jobs"][0]
    assert row["outcome"] == "failed"
    assert "imap.college.edu" in row["detail"]
    assert row["backing_off"] is True
    assert screen.state()["counts"]["failing"] == 1


def test_the_panel_reads_the_schedulers_clock() -> None:
    """The two-clocks defect the other panels had: a row must not compute
    "due in" from a different `now` than the scheduler decides due-ness with."""
    screen, clock = panel(minutes=60)
    screen.scheduler.tick()
    clock["now"] = NOW + timedelta(minutes=45)
    assert screen.state()["jobs"][0]["in_minutes"] == 15.0


def test_pausing_and_resuming_go_through_the_scheduler() -> None:
    screen, _ = panel()
    assert screen.pause("mail")["paused"] is True
    assert screen.state()["jobs"][0]["next_run"] == ""
    assert screen.state()["counts"]["paused"] == 1
    assert screen.resume("mail")["paused"] is False


def test_run_now_returns_the_row_it_just_refreshed() -> None:
    screen, _ = panel()
    row = screen.run_now("mail")
    assert row["outcome"] == "ok" and row["detail"] == "3 new, 1 texted"


def test_a_paused_job_is_not_counted_as_failing() -> None:
    """Switching something off after it broke should clear the alarm, not
    leave the tab reporting a failure nobody is going to act on."""

    def explode() -> str:
        raise RuntimeError("nope")

    screen, _ = panel(explode)
    screen.scheduler.tick()
    screen.pause("mail")
    assert screen.state()["counts"]["failing"] == 0


def test_a_job_never_turned_on_reads_differently_from_one_you_paused() -> None:
    """ "paused" implies the owner did something. On a job that has never been
    switched on they did not, and the row has to offer the switch instead."""
    clock = {"now": NOW}
    job = Job(
        job_id="mail",
        label="Check my email",
        every=every(5),
        run=lambda: "3 new",
        starts_paused=True,
    )
    scheduler = Scheduler(jobs=(job,), states=InMemoryRepository(), now=lambda: clock["now"])
    screen = SchedulerPanel(scheduler)

    row = screen.state()["jobs"][0]
    assert row["never_on"] is True and row["paused"] is True

    screen.resume("mail")
    scheduler.tick()
    on = screen.state()["jobs"][0]
    assert on["never_on"] is False and on["paused"] is False

    screen.pause("mail")
    off = screen.state()["jobs"][0]
    assert off["paused"] is True
    assert off["never_on"] is False, "it has run; this is a pause, not an un-started job"
