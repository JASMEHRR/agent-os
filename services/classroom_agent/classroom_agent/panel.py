"""What the Classwork tab shows.

Read-only, like the agent behind it. There is nothing to change here: you turn
work in inside Classroom, and this reflects that on the next poll. A button
that pretended to submit something would be the worst possible lie for this
tab to tell.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from classroom_agent.coursework import Assignment, State
from classroom_agent.watcher import ClassroomWatcher


def _json(work: Assignment, now: datetime) -> dict[str, Any]:
    left = work.hours_left(now)
    return {
        "id": work.assignment_id,
        "course": work.course_name,
        "title": work.title,
        "state": work.state.value,
        "due": work.due.isoformat() if work.due else "",
        "hours_left": round(left, 1) if left is not None else None,
        "days_left": work.days_left(now.date()),
        "overdue": work.state is State.OVERDUE,
        "describes": work.describe(now),
        "link": work.link,
        "points": work.points,
        "grade": work.grade,
    }


@dataclass
class ClassworkPanel:
    #: None when Google is not connected. The tab says how to connect rather
    #: than showing an empty list that reads as "you are all caught up".
    watcher: ClassroomWatcher | None = None
    setup: str = ""

    def state(self) -> dict[str, Any]:
        if self.watcher is None:
            return {"configured": False, "setup": self.setup, "outstanding": [], "counts": {}}

        now = datetime.now(UTC)
        try:
            pending = self.watcher.outstanding()
        except Exception as exc:  # noqa: BLE001 - the tab reports, never crashes
            return {
                "configured": True,
                "error": f"{exc.__class__.__name__}: {exc}",
                "outstanding": [],
                "counts": {},
            }

        overdue = [a for a in pending if a.state is State.OVERDUE]
        soon = [a for a in pending if (a.hours_left(now) or 1e9) <= 24 and a not in overdue]
        return {
            "configured": True,
            "setup": self.setup,
            "outstanding": [_json(a, now) for a in pending],
            "counts": {
                "outstanding": len(pending),
                "overdue": len(overdue),
                "due_today": len(soon),
            },
            "summary": self.watcher.summary(),
        }

    def check_now(self) -> dict[str, Any]:
        if self.watcher is None:
            raise RuntimeError("Google Classroom is not connected yet")
        report = self.watcher.check()
        return {
            "seen": report.seen,
            "outstanding": report.outstanding,
            "overdue": report.overdue,
            "reminded": report.reminded,
            "errors": list(report.errors),
        }
