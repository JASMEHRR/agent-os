"""Tests for the Opportunity Agent.

What is worth protecting: the stage machine refusing impossible moves, the
deadline arithmetic, reminders firing once at the right tightness, and a
listing never being announced twice.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from opportunity_agent.matching import Fit, Matcher, Profile
from opportunity_agent.opportunities import Kind, Opportunity, Stage, StageError
from opportunity_agent.sources import Manual, SourceError, make, parse_date
from opportunity_agent.tracker import OpportunityTracker, Reminder
from persistence.in_memory import InMemoryRepository

TODAY = date(2026, 9, 12)
NOW = datetime(2026, 9, 12, 9, 0, tzinfo=UTC)

ME = Profile(
    graduation_year=2028,
    degree="btech",
    branch="computer science",
    interests=("python", "ai", "web"),
    avoid=("unpaid", "mlm"),
)


def listing(
    title: str = "Build-a-thon 2026",
    *,
    days: int | None = 10,
    eligibility: str = "",
    summary: str = "",
    url: str = "",
    kind: Kind = Kind.COMPETITION,
) -> Opportunity:
    from datetime import timedelta

    return make(
        title=title,
        organiser="Some Org",
        url=url or f"https://example.test/{title.replace(' ', '-')}",
        kind=kind,
        deadline=None if days is None else TODAY + timedelta(days=days),
        eligibility=eligibility,
        summary=summary,
        when=NOW,
    )


# ================================================================ the deadline


def test_days_left_counts_down_and_goes_negative() -> None:
    assert listing(days=5).days_left(TODAY) == 5
    assert listing(days=0).days_left(TODAY) == 0
    assert listing(days=-2).days_left(TODAY) == -2
    assert listing(days=None).days_left(TODAY) is None


def test_closing_means_open_dated_and_near() -> None:
    assert listing(days=2).closing(3, TODAY)
    assert not listing(days=9).closing(3, TODAY)
    assert not listing(days=-1).closing(3, TODAY)
    assert not listing(days=None).closing(3, TODAY)


def test_a_closed_opportunity_is_not_closing() -> None:
    """Something already applied to has no deadline pressure left."""
    applied = listing(days=1).move_to(Stage.APPLIED, NOW)
    assert not applied.closing(3, TODAY)


def test_describe_says_today_rather_than_zero_days() -> None:
    assert "closes TODAY" in listing(days=0).describe(TODAY)
    assert "3d left" in listing(days=3).describe(TODAY)
    assert "closed 2d ago" in listing(days=-2).describe(TODAY)
    assert "no deadline listed" in listing(days=None).describe(TODAY)


# ============================================================= the stage machine


def test_the_normal_path_through_an_application() -> None:
    work = listing()
    for stage in (Stage.APPLIED, Stage.ADVANCED, Stage.WON):
        work = work.move_to(stage, NOW)
    assert work.stage is Stage.WON
    assert not work.open


def test_you_cannot_win_something_you_never_applied_to() -> None:
    with pytest.raises(StageError, match="cannot go from interested to won"):
        listing().move_to(Stage.WON, NOW)


def test_a_finished_application_is_finished() -> None:
    rejected = listing().move_to(Stage.APPLIED, NOW).move_to(Stage.REJECTED, NOW)
    with pytest.raises(StageError, match="it is finished"):
        rejected.move_to(Stage.APPLIED, NOW)


def test_advanced_can_repeat_because_rounds_do() -> None:
    work = listing().move_to(Stage.APPLIED, NOW).move_to(Stage.ADVANCED, NOW)
    assert work.move_to(Stage.ADVANCED, NOW).stage is Stage.ADVANCED


def test_something_you_skipped_can_be_picked_back_up() -> None:
    skipped = listing().move_to(Stage.SKIPPED, NOW)
    assert skipped.move_to(Stage.INTERESTED, NOW).open


def test_a_stage_change_is_stamped() -> None:
    assert listing().move_to(Stage.APPLIED, NOW).stage_changed_at == NOW


# =================================================================== matching


def test_a_listing_for_your_batch_matches() -> None:
    verdict = Matcher(ME).assess(listing(eligibility="Open to 2027 and 2028 batch"), TODAY)
    assert verdict.fit is Fit.YES
    assert any("2028" in r for r in verdict.reasons)


def test_a_listing_for_another_batch_is_refused() -> None:
    verdict = Matcher(ME).assess(listing(eligibility="2025 and 2026 batch only"), TODAY)
    assert verdict.fit is Fit.NO


def test_an_avoided_word_beats_every_other_match() -> None:
    verdict = Matcher(ME).assess(listing(summary="python ai web internship", eligibility="2028 batch"), TODAY)
    assert verdict.fit is Fit.YES
    unpaid = Matcher(ME).assess(listing(summary="unpaid python ai role", eligibility="2028 batch"), TODAY)
    assert unpaid.fit is Fit.NO
    assert "avoid" in unpaid.reasons[0]


def test_a_passed_deadline_is_refused() -> None:
    assert Matcher(ME).assess(listing(days=-1), TODAY).fit is Fit.NO


def test_something_closing_too_soon_to_start_is_refused() -> None:
    picky = Matcher(Profile(graduation_year=2028, min_days_to_apply=3))
    assert picky.assess(listing(days=1), TODAY).fit is Fit.NO


def test_nothing_matching_and_nothing_disqualifying_is_a_maybe() -> None:
    """The band where a confident guess does damage, so it is shown not judged."""
    verdict = Matcher(ME).assess(listing("Poetry recital evening", summary="verse"), TODAY)
    assert verdict.fit is Fit.MAYBE
    assert verdict.worth_showing


def test_an_interest_word_is_enough_on_its_own() -> None:
    assert Matcher(ME).assess(listing(summary="a python workshop"), TODAY).fit is Fit.YES


def test_your_branch_being_named_counts() -> None:
    assert Matcher(ME).assess(listing(eligibility="computer science students"), TODAY).fit is Fit.YES


# ==================================================================== sources


@pytest.mark.parametrize(
    "text,expected",
    [
        ("2026-09-30", date(2026, 9, 30)),
        ("30 Sep 2026", date(2026, 9, 30)),
        ("30 September 2026", date(2026, 9, 30)),
        ("Sep 30, 2026", date(2026, 9, 30)),
        ("30/09/2026", date(2026, 9, 30)),
        ("30th September 2026", date(2026, 9, 30)),
        ("2026-09-30T18:30:00Z", date(2026, 9, 30)),
    ],
)
def test_the_date_shapes_these_sites_actually_use(text: str, expected: date) -> None:
    assert parse_date(text) == expected


def test_an_unreadable_date_is_none_rather_than_a_guess() -> None:
    """A false deadline in the tracker is worse than an absent one."""
    assert parse_date("sometime next month") is None
    assert parse_date("") is None


def test_the_same_url_always_gets_the_same_id() -> None:
    first = make("A", "Org", "https://example.test/x")
    second = make("A renamed later", "Org", "https://example.test/x")
    assert first.opportunity_id == second.opportunity_id


def test_manual_entries_behave_like_scraped_ones() -> None:
    book = Manual()
    added = book.add("Smart India Hackathon", "MoE", "https://sih.test", deadline="30 Sep 2026")
    assert added.deadline == date(2026, 9, 30)
    assert book.listings() == [added]


def test_a_json_feed_maps_its_fields() -> None:
    from opportunity_agent.sources import JsonFeed

    payload = (
        '{"data": {"rows": [{"title": "AI Sprint", "organisation": "Acme", '
        '"url": "https://a.test/1", "end_date": "2026-10-05", '
        '"eligibility": "2028 batch", "description": "python"}]}}'
    )
    feed = JsonFeed(url="https://a.test", rows_at="data.rows", fetch=lambda url: payload)
    rows = feed.listings()
    assert len(rows) == 1
    assert rows[0].title == "AI Sprint"
    assert rows[0].deadline == date(2026, 10, 5)


def test_a_feed_shaped_wrong_says_so_rather_than_returning_junk() -> None:
    from opportunity_agent.sources import JsonFeed

    feed = JsonFeed(url="https://a.test", rows_at="data.rows", fetch=lambda url: '{"data": {"rows": 5}}')
    with pytest.raises(SourceError, match="expected a list"):
        feed.listings()


def test_rows_without_a_title_are_skipped_not_stored_blank() -> None:
    from opportunity_agent.sources import JsonFeed

    feed = JsonFeed(url="https://a.test", rows_at="r", fetch=lambda url: '{"r": [{"title": ""}, "junk"]}')
    assert feed.listings() == []


# ==================================================================== tracking


def build(*listings: Opportunity, now: datetime = NOW) -> tuple[OpportunityTracker, list[tuple[str, str]]]:
    said: list[tuple[str, str]] = []
    book = Manual(list(listings))
    tracker = OpportunityTracker(
        sources=[book],
        matcher=Matcher(ME),
        store=InMemoryRepository(),
        reminders=InMemoryRepository(),
        announce=lambda o, why: said.append((o.title, why)),
        now=lambda: now,
    )
    return tracker, said


def test_a_new_match_is_announced_once_and_never_again() -> None:
    tracker, said = build(listing(summary="python", days=20))
    first = tracker.scan()
    assert first.added == 1 and first.matched == 1
    assert len(said) == 1

    second = tracker.scan()
    assert second.added == 0
    assert len(said) == 1


def test_something_that_does_not_fit_is_never_stored() -> None:
    tracker, said = build(listing(eligibility="2025 batch only"))
    report = tracker.scan()
    assert report.rejected == 1
    assert report.added == 0
    assert tracker.store.list_all() == []
    assert said == []


def test_a_maybe_is_kept_but_not_announced() -> None:
    """Worth a look in the list; not worth a buzz."""
    tracker, said = build(listing("Poetry evening", summary="verse", days=20))
    report = tracker.scan()
    assert report.maybe == 1
    assert len(tracker.store.list_all()) == 1
    assert said == []


def test_reminders_fire_at_each_tightness_once() -> None:
    from datetime import timedelta

    tracker, said = build(listing(summary="python", days=20))
    tracker.scan()
    said.clear()

    for days_out, expected in ((7, "7 days"), (3, "3 days"), (1, "tomorrow"), (0, "TODAY")):
        tracker.now = lambda d=days_out: NOW + timedelta(days=20 - d)  # type: ignore[misc]
        tracker.scan()
        assert any(expected in why for _, why in said), f"no {days_out}-day reminder"
        said.clear()
        # A second scan the same day must stay silent.
        tracker.scan()
        assert said == []


def test_something_closing_today_is_not_told_it_closes_tomorrow() -> None:
    """Widest-first iteration matched `0 <= 1` before `0 <= 0`."""
    from datetime import timedelta

    tracker, said = build(listing(summary="python", days=20))
    tracker.scan()
    said.clear()
    tracker.now = lambda: NOW + timedelta(days=20)
    tracker.scan()
    assert any("TODAY" in why for _, why in said)
    assert not any("tomorrow" in why for _, why in said)


def test_applying_stops_the_nagging() -> None:
    from datetime import timedelta

    tracker, said = build(listing(summary="python", days=20))
    tracker.scan()
    stored = tracker.store.list_all()[0]
    tracker.move(stored.opportunity_id, Stage.APPLIED)
    said.clear()

    tracker.now = lambda: NOW + timedelta(days=19)
    tracker.scan()
    assert said == []


def test_a_deadline_that_passes_while_untouched_is_marked_missed() -> None:
    from datetime import timedelta

    tracker, _ = build(listing(summary="python", days=5))
    tracker.scan()
    tracker.now = lambda: NOW + timedelta(days=6)
    report = tracker.scan()
    assert report.missed == 1
    assert tracker.store.list_all()[0].stage is Stage.MISSED


def test_something_you_applied_to_is_not_marked_missed() -> None:
    from datetime import timedelta

    tracker, _ = build(listing(summary="python", days=5))
    tracker.scan()
    tracker.move(tracker.store.list_all()[0].opportunity_id, Stage.APPLIED)
    tracker.now = lambda: NOW + timedelta(days=6)
    assert tracker.scan().missed == 0


def test_open_ones_sort_by_deadline_with_undated_last() -> None:
    tracker, _ = build(
        listing("Later", summary="python", days=20),
        listing("Sooner", summary="python", days=2),
        listing("Whenever", summary="python", days=None),
    )
    tracker.scan()
    assert [o.title for o in tracker.open_ones()] == ["Sooner", "Later", "Whenever"]


def test_a_broken_source_does_not_stop_the_others() -> None:
    class Broken:
        def listings(self) -> list[Opportunity]:
            raise SourceError("markup changed")

    tracker, said = build(listing(summary="python", days=20))
    tracker.sources.insert(0, Broken())
    report = tracker.scan()
    assert report.errors and "markup changed" in report.errors[0]
    assert report.added == 1


def test_by_stage_counts_what_you_have() -> None:
    tracker, _ = build(listing("A", summary="python", days=9), listing("B", summary="python", days=9))
    tracker.scan()
    tracker.move(tracker.store.list_all()[0].opportunity_id, Stage.APPLIED)
    counts = tracker.by_stage()
    assert counts[Stage.APPLIED] == 1
    assert counts[Stage.INTERESTED] == 1


def test_closing_within_answers_the_question_you_actually_ask() -> None:
    tracker, _ = build(
        listing("Soon", summary="python", days=2),
        listing("Far", summary="python", days=40),
    )
    tracker.scan()
    assert [o.title for o in tracker.closing_within(7, TODAY)] == ["Soon"]


def test_a_reminder_row_records_which_rung_it_was() -> None:
    from datetime import timedelta

    tracker, _ = build(listing(summary="python", days=20))
    tracker.scan()
    tracker.now = lambda: NOW + timedelta(days=14)
    tracker.scan()
    rungs = [r.days_out for r in tracker.reminders.list_all()]
    assert rungs == [7]
    assert isinstance(tracker.reminders.list_all()[0], Reminder)
