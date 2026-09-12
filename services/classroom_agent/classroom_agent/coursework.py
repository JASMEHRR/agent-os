"""Google Classroom assignments, and whether you have actually done them.

Classroom already shows you a list. What it does not do is tell you, without
you opening it, that three things are due in the next two days and you have
submitted none of them. That gap is the whole agent.

The important distinction, and the one Classroom's own UI blurs: **assigned is
not the same as unsubmitted, and turned-in is not the same as graded.** A piece
of work can be turned in late, returned for changes, or marked done by the
student without anything being handed over. Those are different states with
different consequences, so they are different states here.
"""

from __future__ import annotations

import dataclasses
import enum
from dataclasses import dataclass
from datetime import UTC, date, datetime


class State(enum.StrEnum):
    """Where a piece of work stands, from the student's side.

    These mirror Google's `SubmissionState` plus the two derived cases that
    actually matter to a person: overdue, and due imminently.
    """

    #: Classroom has it but the student has not opened or created anything.
    NEW = "new"
    #: Started, not handed in. The dangerous state: it feels done.
    IN_PROGRESS = "in_progress"
    TURNED_IN = "turned_in"
    #: Marked by the teacher and handed back.
    RETURNED = "returned"
    #: Past the due date and still not turned in.
    OVERDUE = "overdue"


#: Anything in these states still needs work from you.
OUTSTANDING = frozenset({State.NEW, State.IN_PROGRESS, State.OVERDUE})


@dataclass(frozen=True)
class Assignment:
    """One piece of coursework in one course."""

    assignment_id: str
    course_id: str
    course_name: str
    title: str
    state: State
    due: datetime | None
    link: str = ""
    description: str = ""
    points: float | None = None
    grade: float | None = None
    #: Google's own last-modified stamp, used to notice a re-issued deadline.
    updated_at: datetime | None = None

    @property
    def outstanding(self) -> bool:
        return self.state in OUTSTANDING

    def hours_left(self, now: datetime | None = None) -> float | None:
        if self.due is None:
            return None
        return (self.due - (now or datetime.now(UTC))).total_seconds() / 3600

    def days_left(self, today: date | None = None) -> int | None:
        if self.due is None:
            return None
        return (self.due.date() - (today or datetime.now(UTC).date())).days

    def is_overdue(self, now: datetime | None = None) -> bool:
        left = self.hours_left(now)
        return self.outstanding and left is not None and left < 0

    def settled(self, now: datetime | None = None) -> Assignment:
        """The same assignment with OVERDUE applied if the date has gone.

        Derived rather than stored: Google never says "overdue", it says
        `CREATED` with a due date in the past, and computing it at read time
        means a clock change cannot leave a stale flag behind.
        """
        if self.is_overdue(now) and self.state is not State.OVERDUE:
            return dataclasses.replace(self, state=State.OVERDUE)
        return self

    def describe(self, now: datetime | None = None) -> str:
        left = self.hours_left(now)
        if left is None:
            when = "no due date"
        elif left < 0:
            when = f"OVERDUE by {abs(int(left // 24))}d"
        elif left < 24:
            when = f"due in {int(left)}h"
        else:
            when = f"due in {int(left // 24)}d"
        return f"{self.course_name}: {self.title} ({when})"
