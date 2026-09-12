"""Reading Google Classroom. A port, a parser, and an HTTP adapter.

Classroom has a real REST API, so unlike the listing sites there is nothing to
scrape. What it needs is OAuth: a Google Cloud project with the Classroom API
enabled, a consent screen, and read-only scopes. That is a browser flow you do
once, and `scripts/classroom_watch.py --auth` walks through it.

Read-only scopes, and only these three:

* `classroom.courses.readonly`
* `classroom.coursework.me.readonly`
* `classroom.student-submissions.me.readonly`

The `.me` suffix matters. The equivalent scopes without it can read *other*
students' submissions where you have the role for it, and an assignment tracker
has no business holding that access. Asking for less is also what keeps the
consent screen honest about what this does.

`parse_assignment` is separated from the HTTP so the shape Google returns can
be tested exhaustively without a network or a token, which is where the real
complexity lives: due dates arrive as three separate integer fields, and the
submission state lives on a different object from the assignment.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol

from classroom_agent.coursework import Assignment, State

API = "https://classroom.googleapis.com/v1"
TOKEN_URL = "https://oauth2.googleapis.com/token"  # nosec B105 - an endpoint, not a secret
TIMEOUT_SECONDS = 30

SCOPES = (
    "https://www.googleapis.com/auth/classroom.courses.readonly",
    "https://www.googleapis.com/auth/classroom.coursework.me.readonly",
    "https://www.googleapis.com/auth/classroom.student-submissions.me.readonly",
)

#: Google's submission states, mapped to ours. `CREATED` is the one worth
#: noting: it means Classroom made the record, not that the student began.
SUBMISSION_STATES = {
    "NEW": State.NEW,
    "CREATED": State.NEW,
    "TURNED_IN": State.TURNED_IN,
    "RETURNED": State.RETURNED,
    "RECLAIMED_BY_STUDENT": State.IN_PROGRESS,
}

DESCRIPTION_CHARS = 300


class ClassroomError(Exception):
    """Classroom could not be read."""


class CourseworkSource(Protocol):
    def assignments(self) -> list[Assignment]: ...


def parse_due(work: dict[str, Any]) -> datetime | None:
    """Google's split date/time fields as one instant, or None.

    `dueDate` is {year, month, day} and `dueTime` is a separate partial time
    that may omit minutes entirely. A missing `dueTime` means end of day, which
    is Classroom's own behaviour, and getting that wrong would mark a whole
    day's work overdue at midnight.
    """
    due = work.get("dueDate")
    if not isinstance(due, dict) or not all(k in due for k in ("year", "month", "day")):
        return None
    given = work.get("dueTime")
    at: dict[str, Any] = given if isinstance(given, dict) else {}
    # End of day only when Classroom gave no time at all. A `dueTime` that
    # names an hour and omits minutes means the top of that hour, and
    # defaulting those minutes to 59 would push every such deadline an hour
    # late — enough to call something on time that was not.
    hours, minutes = (23, 59) if not at else (int(at.get("hours", 0)), int(at.get("minutes", 0)))
    try:
        return datetime(int(due["year"]), int(due["month"]), int(due["day"]), hours, minutes, tzinfo=UTC)
    except (ValueError, TypeError):
        return None


def parse_assignment(
    work: dict[str, Any], course_id: str, course_name: str, submission: dict[str, Any] | None
) -> Assignment:
    """One `courseWork` plus this student's submission for it."""
    submission = submission or {}
    state = SUBMISSION_STATES.get(str(submission.get("state", "")), State.NEW)
    # A draft with attachments is genuinely started, and saying so is the
    # difference between "you have not looked at this" and "you have not
    # handed it in", which need different reminders.
    if state is State.NEW and submission.get("assignmentSubmission", {}).get("attachments"):
        state = State.IN_PROGRESS

    grade = submission.get("assignedGrade")
    return Assignment(
        assignment_id=str(work.get("id", "")),
        course_id=course_id,
        course_name=course_name,
        title=str(work.get("title", "Untitled")),
        state=state,
        due=parse_due(work),
        link=str(work.get("alternateLink", "")),
        description=str(work.get("description", ""))[:DESCRIPTION_CHARS],
        points=float(work["maxPoints"]) if isinstance(work.get("maxPoints"), int | float) else None,
        grade=float(grade) if isinstance(grade, int | float) else None,
    )


@dataclass
class GoogleClassroom:
    """Reads coursework over the Classroom REST API.

    Holds a refresh token rather than a password, and exchanges it for a short
    access token per run. `fetch` is injected so every parsing path above can
    be tested without a network.
    """

    client_id: str
    client_secret: str
    refresh_token: str
    #: Course states worth reading. ARCHIVED courses still carry old work.
    only_active: bool = True
    fetch: Any = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if self.fetch is None:
            self.fetch = self._http

    # -------------------------------------------------------------------- http

    def _http(self, url: str, token: str) -> dict[str, Any]:
        request = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:  # nosec B310 # noqa: S310
                loaded: dict[str, Any] = json.loads(response.read().decode("utf-8", errors="replace"))
                return loaded
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:300]
            raise ClassroomError(f"HTTP {exc.code} from Classroom: {detail}") from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise ClassroomError(f"could not reach Classroom: {exc}") from exc

    def access_token(self) -> str:
        """Trades the refresh token for an access token good for an hour."""
        payload = urllib.parse.urlencode(
            {
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "refresh_token": self.refresh_token,
                "grant_type": "refresh_token",
            }
        ).encode()
        request = urllib.request.Request(TOKEN_URL, data=payload, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:  # nosec B310 # noqa: S310
                answer = json.loads(response.read().decode())
        except urllib.error.HTTPError as exc:
            raise ClassroomError(
                "Google refused the refresh token. Run: python scripts/classroom_watch.py --auth"
            ) from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise ClassroomError(f"could not reach Google: {exc}") from exc
        token = answer.get("access_token")
        if not token:
            raise ClassroomError(f"no access token in Google's reply: {answer}")
        return str(token)

    # ------------------------------------------------------------------ paging

    def _all_pages(self, path: str, key: str, token: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        page = ""
        while True:
            url = f"{API}/{path}{'&' if '?' in path else '?'}pageSize=100"
            if page:
                url += f"&pageToken={urllib.parse.quote(page)}"
            body = self.fetch(url, token)
            rows.extend(body.get(key, []) or [])
            page = str(body.get("nextPageToken", ""))
            if not page:
                return rows

    def assignments(self) -> list[Assignment]:
        token = self.access_token()
        courses = self._all_pages("courses?courseStates=ACTIVE" if self.only_active else "courses", "courses", token)

        found: list[Assignment] = []
        for course in courses:
            course_id = str(course.get("id", ""))
            if not course_id:
                continue
            name = str(course.get("name", "Untitled course"))
            work = self._all_pages(f"courses/{course_id}/courseWork", "courseWork", token)
            submissions = self._all_pages(
                f"courses/{course_id}/courseWork/-/studentSubmissions?userId=me",
                "studentSubmissions",
                token,
            )
            by_work: dict[str, dict[str, Any]] = {str(s.get("courseWorkId", "")): s for s in submissions}
            found.extend(parse_assignment(w, course_id, name, by_work.get(str(w.get("id", "")))) for w in work)
        return found
