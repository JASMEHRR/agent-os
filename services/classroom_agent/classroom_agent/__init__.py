"""Classroom Agent - tracks Google Classroom coursework and nudges before it is late (stage A4).

Read-only, `.me`-scoped OAuth: it can see your courses, your coursework and
your own submissions, and nothing belonging to anybody else.
"""

from classroom_agent.coursework import OUTSTANDING, Assignment, State
from classroom_agent.source import (
    SCOPES,
    ClassroomError,
    CourseworkSource,
    GoogleClassroom,
    parse_assignment,
    parse_due,
)
from classroom_agent.watcher import (
    OVERDUE_MARK,
    REMINDER_HOURS,
    ClassroomWatcher,
    Nudge,
    WatchReport,
)

__all__ = [
    "OUTSTANDING",
    "OVERDUE_MARK",
    "REMINDER_HOURS",
    "SCOPES",
    "Assignment",
    "ClassroomError",
    "ClassroomWatcher",
    "CourseworkSource",
    "GoogleClassroom",
    "Nudge",
    "State",
    "WatchReport",
    "parse_assignment",
    "parse_due",
]
