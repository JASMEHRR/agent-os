"""Tests for the Classroom Agent.

Worth protecting: Google's three-part due date, the difference between started
and turned in, the reminder ladder firing once at the right tightness, and an
extended deadline re-arming reminders instead of being suppressed by the old
ones.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from classroom_agent.coursework import Assignment, State
from classroom_agent.source import SCOPES, ClassroomError, GoogleClassroom, parse_assignment, parse_due
from classroom_agent.watcher import OVERDUE_MARK, ClassroomWatcher
from persistence.in_memory import InMemoryRepository

NOW = datetime(2026, 9, 12, 9, 0, tzinfo=UTC)


def work(
    title: str = "Lab 3",
    *,
    hours: float | None = 48,
    state: State = State.NEW,
    assignment_id: str = "a1",
) -> Assignment:
    return Assignment(
        assignment_id=assignment_id,
        course_id="c1",
        course_name="Operating Systems",
        title=title,
        state=state,
        due=None if hours is None else NOW + timedelta(hours=hours),
    )


class Source:
    def __init__(self, *items: Assignment) -> None:
        self.items = list(items)

    def assignments(self) -> list[Assignment]:
        return list(self.items)


def build(*items: Assignment, now: datetime = NOW) -> tuple[ClassroomWatcher, list[tuple[str, str]]]:
    said: list[tuple[str, str]] = []
    watcher = ClassroomWatcher(
        source=Source(*items),
        nudges=InMemoryRepository(),
        announce=lambda a, why: said.append((a.title, why)),
        now=lambda: now,
    )
    return watcher, said


# ================================================================== the model


def test_outstanding_covers_everything_still_needing_work() -> None:
    assert work(state=State.NEW).outstanding
    assert work(state=State.IN_PROGRESS).outstanding
    assert not work(state=State.TURNED_IN).outstanding
    assert not work(state=State.RETURNED).outstanding


def test_overdue_is_derived_rather_than_stored() -> None:
    """Google never says overdue; it says CREATED with a past due date."""
    late = work(hours=-5)
    assert late.is_overdue(NOW)
    assert late.settled(NOW).state is State.OVERDUE


def test_something_turned_in_late_is_not_overdue() -> None:
    assert not work(hours=-5, state=State.TURNED_IN).is_overdue(NOW)


def test_work_without_a_due_date_is_never_overdue() -> None:
    assert not work(hours=None).is_overdue(NOW)
    assert work(hours=None).days_left() is None


def test_describe_switches_to_hours_inside_a_day() -> None:
    assert "due in 5h" in work(hours=5).describe(NOW)
    assert "due in 2d" in work(hours=48).describe(NOW)
    assert "OVERDUE" in work(hours=-30).describe(NOW)
    assert "no due date" in work(hours=None).describe(NOW)


# ================================================================== the parser


def test_googles_three_part_due_date() -> None:
    parsed = parse_due({"dueDate": {"year": 2026, "month": 9, "day": 30}, "dueTime": {"hours": 18, "minutes": 30}})
    assert parsed == datetime(2026, 9, 30, 18, 30, tzinfo=UTC)


def test_a_missing_due_time_means_end_of_day() -> None:
    """Classroom's own behaviour. Midnight would mark a whole day late."""
    parsed = parse_due({"dueDate": {"year": 2026, "month": 9, "day": 30}})
    assert parsed == datetime(2026, 9, 30, 23, 59, tzinfo=UTC)


def test_due_time_with_only_hours_still_parses() -> None:
    parsed = parse_due({"dueDate": {"year": 2026, "month": 9, "day": 30}, "dueTime": {"hours": 9}})
    assert parsed == datetime(2026, 9, 30, 9, 0, tzinfo=UTC)


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"dueDate": {}},
        {"dueDate": {"year": 2026, "month": 9}},
        {"dueDate": {"year": 2026, "month": 13, "day": 40}},
    ],
)
def test_an_unusable_due_date_is_none(payload: dict[str, object]) -> None:
    assert parse_due(payload) is None


def test_a_draft_with_attachments_counts_as_started() -> None:
    """ "Not opened" and "not handed in" need different reminders."""
    parsed = parse_assignment(
        {"id": "w1", "title": "Essay"},
        "c1",
        "English",
        {"state": "CREATED", "assignmentSubmission": {"attachments": [{"driveFile": {}}]}},
    )
    assert parsed.state is State.IN_PROGRESS


def test_created_with_nothing_attached_is_untouched() -> None:
    parsed = parse_assignment({"id": "w1", "title": "Essay"}, "c1", "English", {"state": "CREATED"})
    assert parsed.state is State.NEW


def test_a_graded_return_carries_the_mark() -> None:
    parsed = parse_assignment(
        {"id": "w1", "title": "Essay", "maxPoints": 20},
        "c1",
        "English",
        {"state": "RETURNED", "assignedGrade": 17},
    )
    assert parsed.state is State.RETURNED
    assert (parsed.grade, parsed.points) == (17.0, 20.0)


def test_a_missing_submission_record_is_treated_as_new() -> None:
    assert parse_assignment({"id": "w1", "title": "Essay"}, "c1", "English", None).state is State.NEW


def test_the_scopes_are_read_only_and_only_your_own_work() -> None:
    """The `.me` suffix is what stops this reading other students' work."""
    assert all(s.endswith(".readonly") for s in SCOPES)
    assert any("coursework.me" in s for s in SCOPES)
    assert any("student-submissions.me" in s for s in SCOPES)
    assert not any("students" in s and ".me" not in s for s in SCOPES)


# ================================================================= the watcher


def test_nothing_due_soon_says_nothing() -> None:
    watcher, said = build(work(hours=200))
    report = watcher.check()
    assert report.reminded == 0
    assert said == []


def test_a_nudge_fires_once_per_rung() -> None:
    watcher, said = build(work(hours=2))
    assert watcher.check().reminded == 1
    said.clear()
    assert watcher.check().reminded == 0
    assert said == []


def test_the_tightest_rung_wins() -> None:
    """Something due in two hours must not be announced as due in three days."""
    watcher, said = build(work(hours=2))
    watcher.check()
    assert "due in 2h" in said[0][1]


def test_overdue_work_is_announced_once() -> None:
    watcher, said = build(work(hours=-10))
    report = watcher.check()
    assert report.overdue == 1
    assert "OVERDUE" in said[0][1]
    said.clear()
    watcher.check()
    assert said == []


def test_turning_something_in_stops_the_reminders() -> None:
    watcher, said = build(work(hours=2))
    watcher.check()
    said.clear()
    watcher.source = Source(work(hours=2, state=State.TURNED_IN))  # type: ignore[attr-defined]
    report = watcher.check()
    assert report.outstanding == 0
    assert said == []


def test_an_extended_deadline_re_arms_the_ladder() -> None:
    """A new due date is a new deadline; old nudges must not suppress it."""
    watcher, said = build(work(hours=2))
    watcher.check()
    said.clear()
    watcher.source = Source(work(hours=70))  # type: ignore[attr-defined]
    watcher.check()
    assert said, "the extended deadline should nudge again"


def test_outstanding_sorts_soonest_first_with_undated_last() -> None:
    watcher, _ = build(
        work("Later", hours=100, assignment_id="a2"),
        work("Undated", hours=None, assignment_id="a3"),
        work("Sooner", hours=5, assignment_id="a1"),
    )
    assert [a.title for a in watcher.outstanding()] == ["Sooner", "Later", "Undated"]


def test_the_summary_counts_and_lists() -> None:
    watcher, _ = build(work("Lab 3", hours=5), work("Essay", hours=-2, assignment_id="a2"))
    summary = watcher.summary()
    assert "2 outstanding" in summary and "1 overdue" in summary
    assert "Lab 3" in summary


def test_the_summary_says_so_when_you_are_clear() -> None:
    watcher, _ = build(work(state=State.TURNED_IN))
    assert "Nothing outstanding" in watcher.summary()


def test_a_long_summary_is_truncated_with_a_count() -> None:
    watcher, _ = build(*[work(f"Task {n}", hours=n + 1, assignment_id=f"a{n}") for n in range(14)])
    assert "and 4 more" in watcher.summary()


def test_a_classroom_outage_is_reported_not_raised() -> None:
    class Broken:
        def assignments(self) -> list[Assignment]:
            raise ClassroomError("HTTP 503")

    watcher, _ = build()
    watcher.source = Broken()  # type: ignore[attr-defined]
    report = watcher.check()
    assert report.errors and "503" in report.errors[0]


def test_a_nudge_is_recorded_against_its_rung() -> None:
    watcher, _ = build(work(hours=-1))
    watcher.check()
    assert [n.hours_out for n in watcher.nudges.list_all()] == [OVERDUE_MARK]


# ============================================================== the API adapter


def test_courses_and_coursework_are_stitched_together() -> None:
    pages = {
        "courses": {"courses": [{"id": "c1", "name": "Operating Systems"}]},
        "courseWork": {
            "courseWork": [{"id": "w1", "title": "Lab 3", "dueDate": {"year": 2026, "month": 9, "day": 30}}]
        },
        "studentSubmissions": {"studentSubmissions": [{"courseWorkId": "w1", "state": "TURNED_IN"}]},
    }

    def fetch(url: str, token: str) -> dict[str, object]:
        # Most specific first: every Classroom URL contains "courses", so a
        # loose match would answer the courseWork call with the course list.
        for key in ("studentSubmissions", "courseWork", "courses"):
            if key in url:
                return pages[key]
        return {}

    client = GoogleClassroom("id", "secret", "refresh", fetch=fetch)
    client.access_token = lambda: "token"  # type: ignore[method-assign]
    found = client.assignments()
    assert len(found) == 1
    assert found[0].course_name == "Operating Systems"
    assert found[0].state is State.TURNED_IN


def test_paging_follows_the_next_token() -> None:
    calls: list[str] = []

    def fetch(url: str, token: str) -> dict[str, object]:
        calls.append(url)
        if "courses" in url and "courseWork" not in url:
            if "pageToken" in url:
                return {"courses": [{"id": "c2", "name": "Two"}]}
            return {"courses": [{"id": "c1", "name": "One"}], "nextPageToken": "more"}
        return {}

    client = GoogleClassroom("id", "secret", "refresh", fetch=fetch)
    client.access_token = lambda: "token"  # type: ignore[method-assign]
    client.assignments()
    assert any("pageToken=more" in c for c in calls)


def test_a_course_without_an_id_is_skipped() -> None:
    client = GoogleClassroom("id", "secret", "refresh", fetch=lambda url, token: {"courses": [{"name": "Broken"}]})
    client.access_token = lambda: "token"  # type: ignore[method-assign]
    assert client.assignments() == []
