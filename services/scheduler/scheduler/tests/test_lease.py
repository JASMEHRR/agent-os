"""One copy runs the jobs; the others stand down.

The failure this prevents is the worst one this program could have: two
processes polling the same mailbox and texting you twice about the same email.
So these tests are written as two copies over one store, which is exactly the
shape of a studio opened beside a background watcher.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from persistence.in_memory import InMemoryRepository
from scheduler.jobs import Job, JobState
from scheduler.lease import LEASE_ID, STALE_AFTER, Lease, Leases
from scheduler.runner import Scheduler, every

NOW = datetime(2026, 9, 13, 9, 0, tzinfo=UTC)


class Clock:
    def __init__(self, at: datetime = NOW) -> None:
        self.at = at

    def __call__(self) -> datetime:
        return self.at


def pair(clock: Clock) -> tuple[Leases, Leases, InMemoryRepository[Lease]]:
    """A studio and a watcher, sharing one database."""
    store: InMemoryRepository[Lease] = InMemoryRepository()
    studio = Leases(store=store, describes="Post Studio", holder="studio", now=clock)
    watcher = Leases(store=store, describes="the background watcher", holder="watcher", now=clock)
    return studio, watcher, store


def test_the_first_copy_to_ask_gets_it() -> None:
    studio, watcher, _ = pair(Clock())
    assert studio.claim() is True
    assert watcher.claim() is False


def test_the_copy_that_stood_down_can_say_what_it_stood_down_to() -> None:
    """Which is the whole reason `held_by_other` returns a name: the tab has
    to say "the background watcher is running these" rather than showing rows
    that never move and look broken."""
    studio, watcher, _ = pair(Clock())
    studio.claim()
    assert watcher.held_by_other() == "Post Studio"
    assert studio.held_by_other() == ""


def test_renewing_keeps_the_other_copy_out() -> None:
    clock = Clock()
    studio, watcher, _ = pair(clock)
    studio.claim()
    clock.at = NOW + STALE_AFTER * 3
    studio.beat()
    assert watcher.claim() is False


def test_a_lease_nobody_renews_expires() -> None:
    """The reason it is a lease and not a lock file: a copy killed with the
    plug releases nothing, and the next one must not wait forever."""
    clock = Clock()
    studio, watcher, _ = pair(clock)
    studio.claim()
    clock.at = NOW + STALE_AFTER
    assert watcher.claim() is True


def test_a_lease_just_short_of_stale_is_still_held() -> None:
    clock = Clock()
    studio, watcher, _ = pair(clock)
    studio.claim()
    clock.at = NOW + STALE_AFTER - timedelta(seconds=1)
    assert watcher.claim() is False


def test_releasing_hands_over_without_waiting_out_the_window() -> None:
    studio, watcher, _ = pair(Clock())
    studio.claim()
    studio.release()
    assert watcher.claim() is True


def test_a_copy_cannot_release_somebody_elses_lease() -> None:
    """Closing the studio must not free a lease the watcher is holding."""
    studio, watcher, store = pair(Clock())
    watcher.claim()
    studio.release()
    assert store.get(LEASE_ID).holder == "watcher"


def test_renewing_does_not_reset_how_long_this_copy_has_been_running() -> None:
    clock = Clock()
    studio, _, store = pair(clock)
    studio.claim()
    clock.at = NOW + timedelta(minutes=5)
    studio.beat()
    held = store.get(LEASE_ID)
    assert held.took_at == NOW and held.beat_at == NOW + timedelta(minutes=5)


def test_beating_a_lease_this_copy_has_lost_does_not_steal_it_back() -> None:
    """Losing a lease mid-run is possible - a laptop asleep past the window.
    The right response is to stand down, not to fight for it."""
    clock = Clock()
    studio, watcher, store = pair(clock)
    studio.claim()
    clock.at = NOW + STALE_AFTER
    watcher.claim()
    studio.beat()
    assert store.get(LEASE_ID).holder == "watcher"


# ------------------------------------------------- what the scheduler does


def ran(lease: Leases | None) -> tuple[Scheduler, list[int]]:
    """A scheduler over one job that records every call."""
    calls: list[int] = []

    def run() -> str:
        calls.append(1)
        return "polled"

    job = Job(job_id="mail", label="Mail", every=every(5), run=run)
    states: InMemoryRepository[JobState] = InMemoryRepository()
    # The lease's own clock, so moving time moves both together. A scheduler
    # on a different clock from its lease is two clocks again.
    clock: Callable[[], datetime] = Clock()
    if lease is not None:
        clock = lease.now
    return Scheduler(jobs=(job,), states=states, now=clock, lease=lease), calls


def test_a_second_scheduler_does_not_run_the_jobs() -> None:
    clock = Clock()
    studio_lease, watcher_lease, _ = pair(clock)
    first, first_calls = ran(studio_lease)
    second, second_calls = ran(watcher_lease)
    first.tick()
    second.tick()
    assert first_calls == [1]
    assert second_calls == [], "both copies polled; that is a duplicate text"


def test_the_standing_down_copy_names_the_one_that_is_running() -> None:
    clock = Clock()
    studio_lease, watcher_lease, _ = pair(clock)
    first, _ = ran(studio_lease)
    second, _ = ran(watcher_lease)
    first.tick()
    assert second.stood_down_to == "Post Studio"
    assert first.stood_down_to == ""


def test_a_scheduler_with_no_lease_assumes_it_is_the_only_copy() -> None:
    """Which is right for a test and for a single process, and is what keeps
    the lease optional rather than ceremony every caller has to perform."""
    scheduler, calls = ran(None)
    scheduler.tick()
    assert calls == [1]
    assert scheduler.stood_down_to == ""


def test_a_second_copy_still_starts_its_loop_and_simply_does_no_work() -> None:
    """The fix for a bug only two real processes showed.

    `start` used to refuse when another copy held the lease, which meant a
    studio opened beside the watcher decided *once*, at open, that somebody
    else had the work - and then sat there forever after the watcher stopped.
    Whether to run is a per-tick question, so the loop starts either way.
    """
    clock = Clock()
    studio_lease, watcher_lease, _ = pair(clock)
    first, first_calls = ran(studio_lease)
    second, second_calls = ran(watcher_lease)
    first.tick()
    assert second.start() is True
    try:
        assert second.running
    finally:
        second.stop()
    assert first_calls == [1] and second_calls == []


def test_the_second_copy_picks_the_jobs_up_when_the_first_lets_go() -> None:
    """What the tab promises: "close it and this window picks them up"."""
    clock = Clock()
    studio_lease, watcher_lease, _ = pair(clock)
    first, _ = ran(studio_lease)
    second, second_calls = ran(watcher_lease)
    first.tick()
    assert second.tick() == []
    assert first.lease is not None  # `ran` always builds one here
    first.lease.release()
    second.tick()
    assert second_calls == [1], "the surviving copy never took the work over"
