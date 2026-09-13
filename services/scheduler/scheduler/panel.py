"""What the Automatic tab shows.

The point of this screen is not control - it is evidence. A background loop
that works perfectly is indistinguishable from one that died at 3am, unless
something says when each job last ran and what it said. So every row carries
a last run, a next run and the job's own sentence about what it did, and a job
that has failed says so in the words the failure used.

A view, like the other panels: it reads the scheduler and calls it, and
re-decides nothing.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from scheduler.jobs import Job, JobState, Outcome
from scheduler.runner import Scheduler


def _minutes(seconds: float) -> float:
    return round(seconds / 60, 1)


@dataclass
class SchedulerPanel:
    """Reads the scheduler's state and lets the owner pause or run a job."""

    scheduler: Scheduler

    def _row(self, job: Job, state: JobState, now: datetime) -> dict[str, Any]:
        due = state.next_run(job.every, self.scheduler.floor)
        return {
            "job_id": job.job_id,
            "label": job.label,
            "describes": job.describes,
            "every_minutes": _minutes(job.every.total_seconds()),
            "last_run": state.last_finished.isoformat() if state.last_finished else "",
            "next_run": due.isoformat() if due else "",
            # Negative means overdue, which on a healthy scheduler happens only
            # in the seconds between becoming due and the next heartbeat.
            "in_minutes": _minutes((due - now).total_seconds()) if due else None,
            "outcome": state.outcome.value,
            "detail": state.detail,
            "failures": state.failures,
            "paused": state.paused,
            # A job backing off is not the same as a job on its cadence, and
            # the row should say which without the reader doing arithmetic.
            "backing_off": state.failures > 0 and not state.paused,
        }

    def state(self) -> dict[str, Any]:
        now = self.scheduler.now()
        rows = [self._row(job, self.scheduler.state_of(job.job_id), now) for job in self.scheduler.jobs]
        return {
            "running": self.scheduler.running,
            "heartbeat_seconds": int(self.scheduler.heartbeat.total_seconds()),
            "jobs": rows,
            "counts": {
                "jobs": len(rows),
                "paused": sum(1 for r in rows if r["paused"]),
                "failing": sum(1 for r in rows if r["outcome"] == Outcome.FAILED.value and not r["paused"]),
            },
        }

    # ------------------------------------------------------------------ edits

    def run_now(self, job_id: str) -> dict[str, Any]:
        state = self.scheduler.run_job(job_id)
        return self._row(self.scheduler.job(job_id), state, self.scheduler.now())

    def pause(self, job_id: str) -> dict[str, Any]:
        state = self.scheduler.pause(job_id)
        return self._row(self.scheduler.job(job_id), state, self.scheduler.now())

    def resume(self, job_id: str) -> dict[str, Any]:
        state = self.scheduler.resume(job_id)
        return self._row(self.scheduler.job(job_id), state, self.scheduler.now())
