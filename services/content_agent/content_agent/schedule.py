"""The gap between "yes, send this" and the moment it actually goes out.

Approving used to be the end of the line: the studio marked a draft ready and
showed you the text to paste. That is one manual step too many for something
you have already decided on, and it puts publishing at the mercy of whether
you happen to be at a keyboard at the hour a post should land.

So a draft you approved can carry a time, and something running unattended
sends it then. The thing to be careful about is obvious: an unattended
publisher is exactly the machinery this system otherwise refuses to build. It
is safe here for one structural reason, not for a careful one.

**The scheduler cannot publish anything you did not approve.** It does not
decide what is publishable; it asks the draft, and `PostDraft.mark_published`
raises `NotApproved` for any state a human did not put it in. A bug that
selects the wrong rows still cannot select an unapproved one. That is the same
shape as the rest of the system: not a check that a future edit might drop,
but a transition that does not exist.

**Nothing here knows what LinkedIn is.** `Publisher` is a port. The caller
supplies the adapter (`scripts/publish_due.py` supplies the real one, built on
`scripts/linkedin_post.py`), so this module stays testable without a network
and the service package keeps no dependency on a repo-root script.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, Protocol

from content_agent.drafts import DraftState, NotApproved, PostDraft


class Publisher(Protocol):
    """What the scheduler needs from the outside world to send a post.

    Narrow on purpose, the same way `Completion` is: this module should be
    able to publish text and to learn where it landed, and to do nothing else.
    """

    def __call__(self, text: str) -> dict[str, Any]: ...


class Store(Protocol):
    """The Repository port, narrowed to what is used here."""

    def get(self, entity_id: str) -> Any: ...

    def save(self, entity_id: str, entity: Any) -> None: ...

    def list_all(self) -> list[Any]: ...


@dataclasses.dataclass(frozen=True)
class PublishResult:
    """What happened to one draft on one run of the queue."""

    draft_id: str
    published: bool
    url: str = ""
    #: Empty on success. Kept as text rather than an exception because a run
    #: over several drafts has to carry several outcomes back at once.
    error: str = ""


def _url_from(response: dict[str, Any]) -> str:
    """The permalink, out of whichever shape the publisher returned.

    Publishers disagree about this: LinkedIn's own call yields a `url` built
    from the returned URN, and a fallback route may only know the URN. An
    empty string is an acceptable answer, and better than inventing a link.
    """
    for key in ("url", "urn"):
        value = response.get(key)
        if isinstance(value, str) and value:
            return value
    return ""


class Scheduler:
    """Holds the queue of approved drafts and sends the ones that are due."""

    def __init__(self, drafts: Store, clock: Callable[[], datetime] = lambda: datetime.now(UTC)) -> None:
        self._drafts = drafts
        self._clock = clock

    # ------------------------------------------------------------- Scheduling

    def schedule(self, draft_id: str, when: datetime) -> PostDraft:
        """Queues an approved draft for a time. Refuses an unapproved one."""
        draft: PostDraft = self._drafts.get(draft_id)
        scheduled = draft.schedule(when)
        self._drafts.save(draft_id, scheduled)
        return scheduled

    def unschedule(self, draft_id: str) -> PostDraft:
        draft: PostDraft = self._drafts.get(draft_id)
        cleared = draft.unschedule()
        self._drafts.save(draft_id, cleared)
        return cleared

    # ---------------------------------------------------------------- Reading

    def approved(self) -> list[PostDraft]:
        """Everything you said yes to that has not gone out yet.

        Scheduled or not. Without this an approved draft would vanish from
        every screen the moment it stopped being DRAFTED, which is how the
        studio behaved when approving meant "copy it to the clipboard" and is
        wrong now that approving can mean "send it at nine".
        """
        publishable = [
            d for d in self._drafts.list_all() if d.state in (DraftState.APPROVED, DraftState.PUBLISH_FAILED)
        ]
        # Scheduled first and soonest first; the unscheduled trail behind in
        # approval order, because they are waiting on a decision rather than
        # on a clock.
        return sorted(
            publishable,
            key=lambda d: (
                d.scheduled_for is None,
                d.scheduled_for or d.approved_at or d.created_at,
            ),
        )

    def published(self) -> list[PostDraft]:
        """What has already gone out, newest first.

        Includes posts this never sent. A draft you approved and then pasted
        into LinkedIn yourself is still published, and an archive that only
        knew about its own sends would show an empty list to somebody who has
        been posting all week.
        """
        gone: list[PostDraft] = [d for d in self._drafts.list_all() if d.state is DraftState.PUBLISHED]
        return sorted(gone, key=lambda d: d.published_at or d.created_at, reverse=True)

    def mark_posted(self, draft_id: str, url: str = "") -> PostDraft:
        """Records that you posted an approved draft yourself.

        The tagging path: mentions cannot go through the API, so a post that
        needs them is pasted into LinkedIn by hand, and without this the tool
        would keep offering to send something already on the feed.

        It goes through `mark_published`, so it refuses a draft nobody
        approved for exactly the same reason sending one does.
        """
        draft: PostDraft = self._drafts.get(draft_id)
        posted = draft.mark_published(url.strip())
        self._drafts.save(draft_id, posted)
        return posted

    def queue(self) -> list[PostDraft]:
        """Everything waiting to go out, soonest first."""
        waiting = [
            d
            for d in self._drafts.list_all()
            if d.scheduled_for is not None and d.state in (DraftState.APPROVED, DraftState.PUBLISH_FAILED)
        ]
        return sorted(waiting, key=lambda d: d.scheduled_for or datetime.max.replace(tzinfo=UTC))

    def due(self, now: datetime | None = None) -> list[PostDraft]:
        moment = now or self._clock()
        return [d for d in self.queue() if d.is_due(moment)]

    # ------------------------------------------------------------- Publishing

    def publish_due(self, publisher: Publisher, now: datetime | None = None) -> list[PublishResult]:
        """Sends everything due. One failure does not stop the rest.

        A draft whose publish fails lands in PUBLISH_FAILED carrying the
        reason, which is a state you are shown rather than a log line nobody
        reads. It keeps its scheduled time, so a run that failed on a dead
        network sends on the next run rather than needing to be re-approved.
        """
        return [self.publish_now(draft.draft_id, publisher) for draft in self.due(now)]

    def publishable(self, draft_id: str) -> PostDraft:
        """The draft, if a human approved it. Raises `NotApproved` if not.

        Public so a caller can ask *before* it worries about whether it has a
        publisher at all. That ordering matters: a route that checks its
        credentials first would answer "posting is not set up" for an
        unapproved draft, which makes the approval boundary look like a
        consequence of configuration rather than the fixed thing it is.
        """
        draft: PostDraft = self._drafts.get(draft_id)
        if draft.state not in (DraftState.APPROVED, DraftState.PUBLISH_FAILED):
            raise NotApproved(f"a draft in state {draft.state.value} has no human approval to publish on")
        return draft

    def publish_now(self, draft_id: str, publisher: Publisher) -> PublishResult:
        """Sends one approved draft immediately, scheduled or not.

        The button behind "post this now". It goes through the same approval
        check as the queue, because a manual trigger is still not an approval.
        """
        draft = self.publishable(draft_id)

        try:
            response = publisher(draft.full_text())
        except Exception as exc:  # noqa: BLE001 - every publisher failure is the same decision
            # Anything the adapter raises is recorded against the draft rather
            # than propagated: a queue run covering four posts must not lose
            # the other three to one expired token.
            failed = draft.mark_publish_failed(f"{type(exc).__name__}: {exc}")
            self._drafts.save(draft_id, failed)
            return PublishResult(draft_id, published=False, error=failed.failure_reason)

        published = draft.mark_published(_url_from(response))
        self._drafts.save(draft_id, published)
        return PublishResult(draft_id, published=True, url=published.published_url)

    def health(self) -> dict[str, Any]:
        waiting = self.queue()
        return {
            "queued": len(waiting),
            "due_now": len(self.due()),
            "next_at": waiting[0].scheduled_for.isoformat() if waiting and waiting[0].scheduled_for else "",
        }


__all__ = ["Publisher", "PublishResult", "Scheduler"]
