"""The queue, and the property that makes an unattended publisher safe.

The tests that matter here are the refusals. A scheduler that sends the right
post at the right minute is worth one test; a scheduler that cannot be talked
into sending an unapproved one is worth several, because that is the whole
reason this is allowed to run while nobody is watching.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from content_agent.drafts import DraftState, InvalidTransition, NotApproved, PostDraft
from content_agent.formats import Channel
from content_agent.schedule import Scheduler

NOW = datetime(2026, 9, 9, 12, 0, tzinfo=UTC)


class Memory:
    def __init__(self) -> None:
        self.items: dict[str, Any] = {}

    def get(self, entity_id: str) -> Any:
        return self.items[entity_id]

    def save(self, entity_id: str, entity: Any) -> None:
        self.items[entity_id] = entity

    def list_all(self) -> list[Any]:
        return list(self.items.values())


class Recorder:
    """A publisher that remembers what it was asked to send."""

    def __init__(self, response: dict[str, Any] | None = None) -> None:
        self.sent: list[str] = []
        self._response = response if response is not None else {"url": "https://linkedin.com/feed/update/1"}

    def __call__(self, text: str) -> dict[str, Any]:
        self.sent.append(text)
        return self._response


def draft(state: DraftState = DraftState.DRAFTED, draft_id: str = "d1") -> PostDraft:
    return PostDraft(
        draft_id=draft_id,
        note_id="n1",
        state=state,
        channel=Channel.LINKEDIN,
        # Carries the id so two drafts in one test are distinguishable by
        # their text alone, which is all a publisher is handed.
        hook=f"A hook that says something ({draft_id})",
        body="A body with 3 real numbers in it.",
        close="A close.",
        hashtags=("#one", "#two", "#three"),
        created_at=NOW,
    )


def store_with(*drafts: PostDraft) -> Memory:
    memory = Memory()
    for item in drafts:
        memory.save(item.draft_id, item)
    return memory


def scheduler_at(now: datetime, *drafts: PostDraft) -> tuple[Scheduler, Memory]:
    memory = store_with(*drafts)
    return Scheduler(memory, clock=lambda: now), memory


# ------------------------------------------------------------------ Refusals


def test_an_unapproved_draft_cannot_be_scheduled() -> None:
    scheduler, _ = scheduler_at(NOW, draft(DraftState.DRAFTED))
    with pytest.raises(NotApproved):
        scheduler.schedule("d1", NOW + timedelta(hours=1))


def test_an_unapproved_draft_cannot_be_published_by_the_button() -> None:
    scheduler, _ = scheduler_at(NOW, draft(DraftState.DRAFTED))
    publisher = Recorder()
    with pytest.raises(NotApproved):
        scheduler.publish_now("d1", publisher)
    assert publisher.sent == []


def test_a_rejected_draft_cannot_be_scheduled() -> None:
    scheduler, _ = scheduler_at(NOW, draft(DraftState.REJECTED))
    with pytest.raises(NotApproved):
        scheduler.schedule("d1", NOW + timedelta(hours=1))


def test_a_naive_time_is_refused_rather_than_assumed_to_be_utc() -> None:
    approved = draft().approve("jasmehr")
    scheduler, _ = scheduler_at(NOW, approved)
    with pytest.raises(ValueError, match="timezone"):
        scheduler.schedule("d1", datetime(2026, 9, 9, 13, 0))  # noqa: DTZ001 - the point of the test


def test_a_queue_of_unapproved_drafts_publishes_nothing() -> None:
    scheduler, _ = scheduler_at(NOW, draft(DraftState.DRAFTED, "d1"), draft(DraftState.REJECTED, "d2"))
    publisher = Recorder()

    assert scheduler.publish_due(publisher) == []
    assert publisher.sent == []


# --------------------------------------------------------------- The happy path


def test_an_approved_draft_scheduled_in_the_past_is_due_and_goes_out() -> None:
    approved = draft().approve("jasmehr")
    scheduler, memory = scheduler_at(NOW, approved)
    scheduler.schedule("d1", NOW - timedelta(minutes=5))
    publisher = Recorder()

    results = scheduler.publish_due(publisher)

    assert [r.published for r in results] == [True]
    assert publisher.sent == [approved.full_text()]
    assert memory.get("d1").state is DraftState.PUBLISHED
    assert memory.get("d1").published_url == "https://linkedin.com/feed/update/1"


def test_a_draft_scheduled_for_later_is_left_alone() -> None:
    approved = draft().approve("jasmehr")
    scheduler, memory = scheduler_at(NOW, approved)
    scheduler.schedule("d1", NOW + timedelta(hours=2))
    publisher = Recorder()

    assert scheduler.publish_due(publisher) == []
    assert publisher.sent == []
    assert memory.get("d1").state is DraftState.APPROVED


def test_an_approved_draft_with_no_time_never_becomes_due() -> None:
    """Approved-but-unscheduled is "I will post this myself", and stays that."""
    scheduler, _ = scheduler_at(NOW, draft().approve("jasmehr"))
    publisher = Recorder()

    assert scheduler.queue() == []
    assert scheduler.publish_due(publisher) == []
    assert publisher.sent == []


def test_publish_now_sends_an_approved_draft_that_was_never_scheduled() -> None:
    approved = draft().approve("jasmehr")
    scheduler, memory = scheduler_at(NOW, approved)
    publisher = Recorder()

    result = scheduler.publish_now("d1", publisher)

    assert result.published
    assert memory.get("d1").state is DraftState.PUBLISHED


def test_the_queue_is_soonest_first() -> None:
    first = draft(draft_id="d1").approve("jasmehr")
    second = draft(draft_id="d2").approve("jasmehr")
    scheduler, _ = scheduler_at(NOW, first, second)
    scheduler.schedule("d1", NOW + timedelta(hours=5))
    scheduler.schedule("d2", NOW + timedelta(hours=1))

    assert [d.draft_id for d in scheduler.queue()] == ["d2", "d1"]


def test_unscheduling_takes_it_out_of_the_queue_without_unapproving_it() -> None:
    scheduler, memory = scheduler_at(NOW, draft().approve("jasmehr"))
    scheduler.schedule("d1", NOW + timedelta(hours=1))

    scheduler.unschedule("d1")

    assert scheduler.queue() == []
    assert memory.get("d1").state is DraftState.APPROVED


# ------------------------------------------------------------------- Failures


def test_a_publisher_that_raises_lands_the_draft_in_publish_failed() -> None:
    approved = draft().approve("jasmehr")
    scheduler, memory = scheduler_at(NOW, approved)
    scheduler.schedule("d1", NOW - timedelta(minutes=1))

    def broken(text: str) -> dict[str, Any]:
        raise RuntimeError("the saved token has expired")

    results = scheduler.publish_due(broken)

    assert [r.published for r in results] == [False]
    assert "expired" in results[0].error
    assert memory.get("d1").state is DraftState.PUBLISH_FAILED


def test_one_failure_does_not_stop_the_rest_of_the_queue() -> None:
    good = draft(draft_id="good").approve("jasmehr")
    bad = draft(draft_id="bad").approve("jasmehr")
    scheduler, memory = scheduler_at(NOW, good, bad)
    scheduler.schedule("bad", NOW - timedelta(minutes=10))
    scheduler.schedule("good", NOW - timedelta(minutes=5))

    def selective(text: str) -> dict[str, Any]:
        if memory.get("bad").full_text() == text:
            raise RuntimeError("nope")
        return {"url": "https://linkedin.com/feed/update/2"}

    results = scheduler.publish_due(selective)

    assert {r.draft_id: r.published for r in results} == {"bad": False, "good": True}
    assert memory.get("good").state is DraftState.PUBLISHED


def test_a_failed_publish_stays_queued_and_goes_out_on_the_next_run() -> None:
    """A dead network must not cost an approval."""
    scheduler, memory = scheduler_at(NOW, draft().approve("jasmehr"))
    scheduler.schedule("d1", NOW - timedelta(minutes=1))

    def broken(text: str) -> dict[str, Any]:
        raise RuntimeError("no network")

    scheduler.publish_due(broken)
    assert memory.get("d1").state is DraftState.PUBLISH_FAILED
    assert scheduler.due() != []

    results = scheduler.publish_due(Recorder())

    assert [r.published for r in results] == [True]
    assert memory.get("d1").state is DraftState.PUBLISHED


def test_a_publisher_that_returns_only_an_urn_still_records_something() -> None:
    scheduler, memory = scheduler_at(NOW, draft().approve("jasmehr"))
    scheduler.schedule("d1", NOW - timedelta(minutes=1))

    scheduler.publish_due(Recorder({"urn": "urn:li:share:7", "backend": "publora"}))

    assert memory.get("d1").published_url == "urn:li:share:7"


def test_a_publisher_that_returns_nothing_useful_publishes_without_a_link() -> None:
    scheduler, memory = scheduler_at(NOW, draft().approve("jasmehr"))
    scheduler.schedule("d1", NOW - timedelta(minutes=1))

    scheduler.publish_due(Recorder({"ok": True}))

    assert memory.get("d1").state is DraftState.PUBLISHED
    assert memory.get("d1").published_url == ""


# -------------------------------------------------------------------- Archive


def test_a_post_you_sent_by_hand_can_be_recorded_as_posted() -> None:
    """The tagging path: mentions cannot go through the API, so those posts
    are pasted into LinkedIn by hand and the tool has to be told."""
    scheduler, memory = scheduler_at(NOW, draft().approve("jasmehr"))

    posted = scheduler.mark_posted("d1", "https://www.linkedin.com/feed/update/urn:li:activity:5")

    assert posted.state is DraftState.PUBLISHED
    assert memory.get("d1").published_url.endswith("activity:5")
    assert [d.draft_id for d in scheduler.published()] == ["d1"]


def test_recording_a_hand_posted_draft_needs_no_link() -> None:
    """Asking for a URL you have to go and find is how a two-second action
    becomes one nobody does."""
    scheduler, _ = scheduler_at(NOW, draft().approve("jasmehr"))

    posted = scheduler.mark_posted("d1")

    assert posted.state is DraftState.PUBLISHED
    assert posted.published_url == ""


def test_an_unapproved_draft_cannot_be_recorded_as_posted() -> None:
    """Same boundary as sending: this is a different door to the same room."""
    scheduler, memory = scheduler_at(NOW, draft(DraftState.DRAFTED))

    with pytest.raises(NotApproved):
        scheduler.mark_posted("d1")
    assert memory.get("d1").state is DraftState.DRAFTED


def test_a_posted_draft_leaves_the_approved_list_and_joins_the_archive() -> None:
    scheduler, _ = scheduler_at(NOW, draft().approve("jasmehr"))
    assert [d.draft_id for d in scheduler.approved()] == ["d1"]

    scheduler.mark_posted("d1")

    assert scheduler.approved() == []
    assert [d.draft_id for d in scheduler.published()] == ["d1"]


def test_the_archive_is_newest_first_and_holds_both_routes() -> None:
    """One sent by the scheduler, one pasted by hand. Both are posted."""
    sent = draft(draft_id="sent").approve("jasmehr")
    by_hand = draft(draft_id="by-hand").approve("jasmehr")
    scheduler, _ = scheduler_at(NOW, sent, by_hand)

    scheduler.mark_posted("by-hand")
    scheduler.schedule("sent", NOW - timedelta(minutes=1))
    scheduler.publish_due(Recorder())

    archived = [d.draft_id for d in scheduler.published()]
    assert sorted(archived) == ["by-hand", "sent"]
    assert len(archived) == 2


# ------------------------------------------------------------ Un-archiving


def test_an_archived_draft_can_be_put_back_among_the_approved() -> None:
    """The one-click "already posted" is easy to press on the wrong card, and
    an archive nobody can correct drifts from the truth just as surely as one
    that forgets."""
    scheduler, memory = scheduler_at(NOW, draft().approve("jasmehr"))
    scheduler.mark_posted("d1", "https://example.com/1")

    restored = scheduler.unpublish("d1")

    assert restored.state is DraftState.APPROVED
    assert restored.published_at is None
    assert restored.published_url == ""
    assert scheduler.published() == []
    assert [d.draft_id for d in scheduler.approved()] == ["d1"]
    assert memory.get("d1").state is DraftState.APPROVED


def test_putting_one_back_clears_its_time_so_it_cannot_post_twice() -> None:
    """The trap this feature would otherwise set.

    A draft restored to APPROVED while still carrying a time in the past is
    due the instant it lands, so the next unattended run would send it to
    LinkedIn a second time. Correcting a mistake in the archive must not be a
    way to publish something twice.
    """
    scheduler, _ = scheduler_at(NOW, draft().approve("jasmehr"))
    scheduler.schedule("d1", NOW - timedelta(minutes=5))
    publisher = Recorder()
    scheduler.publish_due(publisher)
    assert len(publisher.sent) == 1

    scheduler.unpublish("d1")

    assert scheduler.due() == [], "a restored draft must not be instantly due again"
    assert scheduler.publish_due(publisher) == []
    assert len(publisher.sent) == 1, "it would have gone out to LinkedIn twice"


def test_a_draft_that_was_never_published_cannot_be_put_back() -> None:
    scheduler, _ = scheduler_at(NOW, draft().approve("jasmehr"))

    with pytest.raises(InvalidTransition):
        scheduler.unpublish("d1")


def test_a_restored_draft_can_be_scheduled_and_sent_again_deliberately() -> None:
    """Putting it back is a correction, not a lock: it is an ordinary approved
    draft again, and the ordinary route out of that still works."""
    scheduler, memory = scheduler_at(NOW, draft().approve("jasmehr"))
    scheduler.mark_posted("d1")
    scheduler.unpublish("d1")

    scheduler.schedule("d1", NOW - timedelta(minutes=1))
    results = scheduler.publish_due(Recorder())

    assert [r.published for r in results] == [True]
    assert memory.get("d1").state is DraftState.PUBLISHED


def test_health_counts_the_queue_and_names_the_next_time() -> None:
    scheduler, _ = scheduler_at(NOW, draft(draft_id="d1").approve("jasmehr"))
    scheduler.schedule("d1", NOW + timedelta(hours=3))

    health = scheduler.health()

    assert health["queued"] == 1
    assert health["due_now"] == 0
    assert health["next_at"].startswith("2026-09-09T15:00")
