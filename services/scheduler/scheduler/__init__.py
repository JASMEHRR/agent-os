"""Scheduler - runs the agents on their own cadences, unattended (stage A5).

The applied agents could each do their work and none of them ever started on
their own. This is the loop that starts them: a background thread that asks
each job whether it is due, runs the ones that are, remembers what happened,
and backs off the ones that are failing.
"""

from scheduler.jobs import (
    BACKOFF_CEILING,
    DETAIL_LIMIT,
    MAX_BACKOFF,
    Job,
    JobState,
    Outcome,
    failed,
    started,
    succeeded,
)
from scheduler.runner import HEARTBEAT, Scheduler, every, schedule

__all__ = [
    "BACKOFF_CEILING",
    "DETAIL_LIMIT",
    "HEARTBEAT",
    "MAX_BACKOFF",
    "Job",
    "JobState",
    "Outcome",
    "Scheduler",
    "every",
    "failed",
    "schedule",
    "started",
    "succeeded",
]
