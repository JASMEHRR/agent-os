"""Tracking, snapshots, and the comparison.

No network anywhere: the Apify adapter is exercised through
`parse_post_detail` against the shape the actor actually returns, and
everything above it takes a `MetricsSource` that is a function in this file.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from content_agent.analytics import (
    Analytics,
    ApifyMetrics,
    MetricsUnavailable,
    PostMetrics,
    normalise_url,
    parse_post_detail,
)

NOW = datetime(2026, 9, 9, 12, 0, tzinfo=UTC)
MINE = "https://www.linkedin.com/feed/update/urn:li:activity:7000000000000000001/"
THEIRS = "https://www.linkedin.com/feed/update/urn:li:activity:7000000000000000002/"


class Memory:
    def __init__(self) -> None:
        self.items: dict[str, Any] = {}

    def get(self, entity_id: str) -> Any:
        return self.items[entity_id]

    def save(self, entity_id: str, entity: Any) -> None:
        self.items[entity_id] = entity

    def list_all(self) -> list[Any]:
        return list(self.items.values())


def analytics_at(now: datetime = NOW) -> Analytics:
    return Analytics(Memory(), Memory(), clock=lambda: now)


def source_of(**by_url: PostMetrics) -> Any:
    """A metrics source that answers from a dict, keyed by normalised URL."""

    def fetch(post_url: str) -> PostMetrics:
        if post_url not in by_url:
            raise MetricsUnavailable(f"nothing for {post_url}")
        return by_url[post_url]

    return fetch


# ------------------------------------------------------------------------ URLs


def test_the_same_post_with_tracking_parameters_is_one_post() -> None:
    bare = normalise_url("https://www.linkedin.com/feed/update/urn:li:activity:7/")
    shared = normalise_url("https://www.linkedin.com/feed/update/urn:li:activity:7?utm_source=share")

    assert bare == shared


def test_tracking_the_same_url_twice_does_not_make_two_rows() -> None:
    numbers = analytics_at()
    first = numbers.track(MINE, "the billboard post", mine=True)
    second = numbers.track(MINE + "?utm_source=share", "same one", mine=True)

    assert first.post_id == second.post_id
    assert len(numbers.tracked()) == 1


def test_a_url_that_is_not_linkedin_is_refused_at_the_door() -> None:
    with pytest.raises(ValueError, match="LinkedIn"):
        analytics_at().track("https://example.com/blog/1", "not a post", mine=True)


def test_an_empty_url_is_refused() -> None:
    with pytest.raises(ValueError, match="URL"):
        analytics_at().track("   ", "", mine=True)


# -------------------------------------------------------------------- Snapshots


def test_a_snapshot_records_the_counts_with_the_time_it_was_taken() -> None:
    numbers = analytics_at()
    post = numbers.track(MINE, "the billboard post", mine=True)

    result = numbers.snapshot(post, source_of(**{post.url: PostMetrics(likes=12, comments=3, shares=1)}))

    assert result.taken
    assert result.engagement == 16
    latest = numbers.latest(post.post_id)
    assert latest is not None
    assert (latest.likes, latest.comments, latest.shares) == (12, 3, 1)
    assert latest.taken_at == NOW


def test_readings_accumulate_rather_than_overwriting() -> None:
    numbers = Analytics(Memory(), Memory(), clock=lambda: NOW)
    post = numbers.track(MINE, "the billboard post", mine=True)
    numbers.snapshot(post, source_of(**{post.url: PostMetrics(likes=4, comments=0, shares=0)}))

    later = Analytics(numbers._posts, numbers._snapshots, clock=lambda: NOW + timedelta(days=1))
    later.snapshot(post, source_of(**{post.url: PostMetrics(likes=30, comments=5, shares=2)}))

    history = later.history(post.post_id)
    assert [s.likes for s in history] == [4, 30]


def test_an_unreadable_post_reports_the_reason_and_stores_no_zeroes() -> None:
    """A private post must not look like a post nobody engaged with."""
    numbers = analytics_at()
    post = numbers.track(MINE, "gone private", mine=True)

    result = numbers.snapshot(post, source_of())

    assert not result.taken
    assert "nothing for" in result.error
    assert numbers.history(post.post_id) == []


def test_one_unreadable_post_does_not_stop_the_others() -> None:
    numbers = analytics_at()
    mine = numbers.track(MINE, "mine", mine=True)
    numbers.track(THEIRS, "theirs", mine=False)

    results = numbers.snapshot_all(source_of(**{mine.url: PostMetrics(likes=9, comments=1, shares=0)}))

    assert sorted((r.label, r.taken) for r in results) == [("mine", True), ("theirs", False)]


def test_an_untracked_post_is_skipped_but_keeps_its_history() -> None:
    numbers = analytics_at()
    post = numbers.track(MINE, "old post", mine=True)
    numbers.snapshot(post, source_of(**{post.url: PostMetrics(likes=5, comments=0, shares=0)}))

    numbers.untrack(post.post_id)

    assert numbers.tracked() == []
    assert len(numbers.history(post.post_id)) == 1


# ------------------------------------------------------------------ Comparison


def build_comparison() -> Analytics:
    numbers = analytics_at()
    mine_one = numbers.track(MINE, "mine one", mine=True)
    mine_two = numbers.track(MINE + "2", "mine two", mine=True)
    theirs = numbers.track(THEIRS, "theirs", mine=False)
    numbers.snapshot_all(
        source_of(
            **{
                mine_one.url: PostMetrics(likes=10, comments=2, shares=0),
                mine_two.url: PostMetrics(likes=20, comments=4, shares=0),
                theirs.url: PostMetrics(likes=100, comments=20, shares=5),
            }
        )
    )
    return numbers


def test_the_comparison_reports_medians_and_the_sample_size() -> None:
    comparison = build_comparison().compare()

    assert comparison["mine"]["posts"] == 2
    assert comparison["mine"]["median_engagement"] == 18
    assert comparison["theirs"]["posts"] == 1
    assert comparison["theirs"]["median_engagement"] == 125


def test_the_gap_is_signed_and_says_which_way_it_runs() -> None:
    comparison = build_comparison().compare()

    assert comparison["comparable"]
    assert comparison["gap"] == 18 - 125


def test_with_nobody_to_compare_against_the_gap_is_not_reported_as_a_result() -> None:
    numbers = analytics_at()
    post = numbers.track(MINE, "mine", mine=True)
    numbers.snapshot(post, source_of(**{post.url: PostMetrics(likes=10, comments=0, shares=0)}))

    comparison = numbers.compare()

    assert not comparison["comparable"]
    assert comparison["gap"] == 0


def test_rows_come_back_best_first() -> None:
    rows = build_comparison().rows()

    assert [r["label"] for r in rows] == ["theirs", "mine two", "mine one"]


def test_a_tracked_post_never_read_shows_zero_rather_than_disappearing() -> None:
    numbers = analytics_at()
    numbers.track(MINE, "never read", mine=True)

    rows = numbers.rows()

    assert len(rows) == 1
    assert rows[0]["engagement"] == 0
    assert rows[0]["taken_at"] == ""
    # And it is excluded from the medians, because a post with no reading is
    # not a post that did badly.
    assert numbers.compare()["mine"]["posts"] == 0


# ----------------------------------------------------------- The Apify shape


ACTOR_ITEM: dict[str, Any] = {
    "post": {
        "text": "My site used to put an item on the front page...",
        "url": MINE,
        "created_at": "2026-09-07 09:00:00",
        "urn": {"activity_urn": "7000000000000000001"},
    },
    "author": {"name": "Jasmehr", "followers": 5000},
    "stats": {"total_reactions": 42, "comments": 7, "shares": 2},
}


def test_the_actors_nested_item_flattens_to_a_reading() -> None:
    metrics = parse_post_detail(ACTOR_ITEM)

    assert (metrics.likes, metrics.comments, metrics.shares) == (42, 7, 2)
    assert metrics.engagement == 51
    assert metrics.author_followers == 5000
    assert metrics.author_name == "Jasmehr"


def test_a_nulled_shell_is_an_error_rather_than_a_reading_of_zero() -> None:
    with pytest.raises(MetricsUnavailable, match="not retrievable"):
        parse_post_detail({"post": {"text": None}, "author": {"name": None}, "stats": {}})


def test_missing_stats_read_as_zero_rather_than_crashing() -> None:
    metrics = parse_post_detail({"post": {"text": "something"}, "author": {"name": "x"}, "stats": {}})

    assert metrics.engagement == 0


def test_counts_that_arrive_as_strings_are_still_counts() -> None:
    item = {"post": {"text": "x"}, "author": {"name": "y"}, "stats": {"total_reactions": "1,024", "comments": "8"}}

    metrics = parse_post_detail(item)

    assert metrics.likes == 1024
    assert metrics.comments == 8


def test_without_a_token_the_adapter_says_so_instead_of_calling_out() -> None:
    source = ApifyMetrics(token="")

    assert not source.configured()
    with pytest.raises(MetricsUnavailable, match="APIFY_TOKEN"):
        source(MINE)
