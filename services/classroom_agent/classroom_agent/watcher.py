"""Tells you what is due before it is late, and once only.

The reminder ladder is tighter than the opportunity tracker's because
coursework runs on hours rather than weeks: something due at 11:59pm tonight
is a different problem at 9am than at 9pm.

* three days out
* the day before
* the morning it is due
* three hours before it closes
* once when it has gone overdue and is still not turned in

A reminder is keyed by assignment *and* due date, so a teacher extending a
deadline correctly re-arms the ladder — that is a new deadline, and the old
reminders should not suppress the new ones. Turning something in stops every
future reminder for it, which is the only reward this agent can offer.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime

from classroom_agent.coursework import Assignment, State
from classroom_agent.source import CourseworkSource
from persistence.repository import NotFound, Repository

#: Hours before the due time at which a nudge fires, tightest first.
REMINDER_HOURS = (3, 12, 24, 72)

#: The nudge sent after the due time has passed, once.
OVERDUE_MARK = -1


@dataclass(frozen=True)
class Nudge:
    """A reminder already sent. Keyed by assignment *and* deadline."""

    nudge_id: str
    assignment_id: str
    hours_out: int
    sent_at: datetime


@dataclass(frozen=True)
class WatchReport:
    seen: int = 0
    outstanding: int = 0
    overdue: int = 0
    reminded: int = 0
    errors: tuple[str, ...] = ()


def _nudge_id(work: Assignment, hours_out: int) -> str:
    """Includes the due date, so an extended deadline re-arms the ladder."""
    stamp = work.due.isoformat() if work.due else "no-due-date"
    return f"{work.assignment_id}:{stamp}:{hours_out}"


@dataclass
class ClassroomWatcher:
    """Polls Classroom and nudges about what is still outstanding."""

    source: CourseworkSource
    nudges: Repository[Nudge]
    announce: Callable[[Assignment, str], None] = field(default=lambda a, why: None)
    now: Callable[[], datetime] = field(default=lambda: datetime.now(UTC))

    def _already(self, work: Assignment, hours_out: int) -> bool:
        try:
            self.nudges.get(_nudge_id(work, hours_out))
        except NotFound:
            return False
        return True

    def _send(self, work: Assignment, hours_out: int, when: datetime, why: str) -> None:
        marker = _nudge_id(work, hours_out)
        self.nudges.save(marker, Nudge(marker, work.assignment_id, hours_out, when))
        self.announce(work, why)

    def outstanding(self) -> list[Assignment]:
        """What still needs doing, soonest first. Undated work sorts last."""
        work = [a.settled(self.now()) for a in self.source.assignments()]
        pending = [a for a in work if a.outstanding]
        return sorted(pending, key=lambda a: (a.due is None, a.due or datetime.max.replace(tzinfo=UTC)))

    def check(self) -> WatchReport:
        when = self.now()
        try:
            everything = [a.settled(when) for a in self.source.assignments()]
        except Exception as exc:  # noqa: BLE001 - a watcher must outlive one bad poll
            return WatchReport(errors=(f"{exc.__class__.__name__}: {exc}",))

        reminded = overdue = 0
        pending = [a for a in everything if a.outstanding]

        for work in pending:
            left = work.hours_left(when)
            if left is None:
                continue

            if left < 0:
                overdue += 1
                if not self._already(work, OVERDUE_MARK):
                    self._send(work, OVERDUE_MARK, when, "is OVERDUE and still not turned in")
                    reminded += 1
                continue

            # Only the tightest rung that applies, and only if it has not
            # already fired. Walking outward to the next unfired rung would
            # re-announce the same assignment on every poll, climbing the
            # ladder one rung at a time until it ran out.
            applicable = [mark for mark in REMINDER_HOURS if left <= mark]
            if not applicable:
                continue
            tightest = min(applicable)
            if not self._already(work, tightest):
                hours = int(left)
                why = f"due in {hours}h" if hours < 24 else f"due in {hours // 24}d"
                self._send(work, tightest, when, why)
                reminded += 1

        return WatchReport(len(everything), len(pending), overdue, reminded)

    def summary(self) -> str:
        """One message listing everything outstanding. For a daily digest."""
        pending = self.outstanding()
        if not pending:
            return "Nothing outstanding in Classroom."
        now = self.now()
        late = [a for a in pending if a.state is State.OVERDUE]
        lines = [a.describe(now) for a in pending[:10]]
        head = f"{len(pending)} outstanding" + (f", {len(late)} overdue" if late else "")
        more = f"\n...and {len(pending) - 10} more." if len(pending) > 10 else ""
        return f"{head}:\n\n" + "\n".join(lines) + more
