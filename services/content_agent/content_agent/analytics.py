"""How a post actually did, and how that compares to the people you watch.

The drafting side of this system has never had a feedback signal. It learns
your voice from what you approve, which is taste, and nothing at all from what
the feed did with it. This module is the missing half: a number attached to a
post, taken again over time, next to the same numbers for people you chose to
measure yourself against.

**Why this scrapes rather than asks.** LinkedIn's own API does not return
post performance to an app like this one. Impressions and engagement live
behind the Marketing Developer Platform, which is an application process aimed
at companies, and no amount of correct OAuth gets a personal app there. So the
choice is not "official or unofficial", it is "these numbers or none". Reads
go through Apify's public actors, which fetch what a logged-out visitor can
already see: reactions, comments, reposts. It is against LinkedIn's terms and
it is worth being plain about that rather than burying it, which is why
`scripts/linkedin_post.py` still refuses to do anything of the kind: posting
carries your token and your account, and reading here does not.

**Snapshots, not a number.** A post's counts are meaningless without a time
attached; the interesting question is never "how many" but "how many by the
second day, compared to the last one". So every read is stored with its
timestamp and nothing is overwritten. That also means the comparison survives
the source going away: what has already been collected stays collected.

**The comparison is medians, never a mean.** One post that did fifty times
your usual moves a mean enough to make every other week look like a decline,
and the sample here is small by nature. Medians and the sample size are
reported together, because a median of three posts is a number that deserves
its caveat printed beside it.
"""

from __future__ import annotations

import dataclasses
import json
import os
import statistics
import urllib.error
import urllib.parse
import urllib.request
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, Protocol

#: Apify's actor for one post's detail: body, author, and the engagement
#: stats. The same actor the vendored linkedin-skills bundle uses, named here
#: rather than imported because `.claude/lib` is a vendored bundle on no
#: import path and this package does not take a `requests` dependency.
POST_DETAIL_ACTOR = "apimaestro~linkedin-post-detail"

APIFY_BASE = "https://api.apify.com/v2"

#: Apify runs the actor synchronously and answers when it is done, which for a
#: cold actor is tens of seconds. Shorter than this reads as "broken" while
#: the run is merely slow.
TIMEOUT_SECONDS = 180


class MetricsUnavailable(RuntimeError):
    """The numbers for a post could not be read.

    One error for every cause on purpose: a private post, a deleted post, a
    spent Apify balance and a dead network all mean the same thing to the
    person looking at the screen, which is "no number this time, try later".
    """


class Store(Protocol):
    """The Repository port, narrowed to what is used here."""

    def get(self, entity_id: str) -> Any: ...

    def save(self, entity_id: str, entity: Any) -> None: ...

    def list_all(self) -> list[Any]: ...


@dataclasses.dataclass(frozen=True)
class PostMetrics:
    """One reading of one post, as the source returned it."""

    likes: int
    comments: int
    shares: int
    author_name: str = ""
    author_followers: int = 0
    #: LinkedIn's own posted-at, kept as the text the source gave rather than
    #: parsed: the format varies by actor and a wrong parse is worse than a
    #: string nobody can sort on.
    posted_at: str = ""
    text: str = ""

    @property
    def engagement(self) -> int:
        """One number to rank on. Reactions plus comments plus reposts.

        Crude and deliberate. Weighting comments above likes would encode an
        opinion about the algorithm that changes every few months, and the
        per-kind counts are all kept anyway.
        """
        return self.likes + self.comments + self.shares


class MetricsSource(Protocol):
    """Where a reading comes from. Apify in production, a stub in the tests."""

    def __call__(self, post_url: str) -> PostMetrics: ...


@dataclasses.dataclass(frozen=True)
class TrackedPost:
    """A post being measured, yours or somebody else's."""

    post_id: str
    url: str
    label: str
    #: Yours or theirs. The whole comparison is this boolean.
    mine: bool
    added_at: datetime
    #: Set when you stop tracking. Kept rather than deleted so the snapshots
    #: already collected still have something to hang off.
    dropped: bool = False


@dataclasses.dataclass(frozen=True)
class Snapshot:
    """What a post's counts were at one moment."""

    snapshot_id: str
    post_id: str
    taken_at: datetime
    likes: int
    comments: int
    shares: int
    author_followers: int = 0
    posted_at: str = ""

    @property
    def engagement(self) -> int:
        return self.likes + self.comments + self.shares


@dataclasses.dataclass(frozen=True)
class SnapshotResult:
    """The outcome of trying to read one tracked post."""

    post_id: str
    label: str
    taken: bool
    engagement: int = 0
    error: str = ""


def normalise_url(url: str) -> str:
    """Drops the query string and trailing slash, so one post is one row.

    LinkedIn hands out the same post with `?utm_source=share`, with a tracking
    id, and bare. Tracking all three would compare a post against itself.
    """
    cleaned = url.strip()
    if not cleaned:
        return ""
    split = urllib.parse.urlsplit(cleaned)
    if not split.scheme:
        split = urllib.parse.urlsplit(f"https://{cleaned}")
    path = split.path.rstrip("/")
    return urllib.parse.urlunsplit((split.scheme, split.netloc, path, "", ""))


# ------------------------------------------------------------------- Apify


def _as_int(value: Any) -> int:
    """A count, or zero. Actors return `None` for a stat they did not find."""
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        digits = value.replace(",", "").strip()
        try:
            return int(digits)
        except ValueError:
            return 0
    return 0


def parse_post_detail(raw: dict[str, Any]) -> PostMetrics:
    """Flattens the actor's nested item into a reading.

    Kept separate from the HTTP call so the shape the actor returns can be
    tested against a recorded payload without a network or a token.
    """
    post = raw.get("post") or {}
    author = raw.get("author") or {}
    stats = raw.get("stats") or {}
    text = post.get("text")
    name = author.get("name")
    if not text and not name:
        # The actor answers with a nulled shell for a post that is private,
        # removed, or behind a login wall. An empty reading stored as zeroes
        # would look exactly like a post nobody engaged with.
        raise MetricsUnavailable("post not retrievable: private, removed, or login-walled")
    return PostMetrics(
        likes=_as_int(stats.get("total_reactions")),
        comments=_as_int(stats.get("comments")),
        shares=_as_int(stats.get("shares")),
        author_name=str(name or ""),
        author_followers=_as_int(author.get("followers")),
        posted_at=str(post.get("created_at") or ""),
        text=str(text or "")[:500],
    )


class ApifyMetrics:
    """Reads a post's public counts through Apify's post-detail actor.

    `urllib` rather than `requests`, which is the same choice the posting
    script made and for the same reason: this repository has no runtime
    dependencies and adding one for a single POST would be a poor trade.
    """

    def __init__(
        self,
        token: str = "",  # nosec B107 - empty means "read it from the environment", not a credential
        timeout: float = TIMEOUT_SECONDS,
    ) -> None:
        self._token = token or os.environ.get("APIFY_TOKEN", "")
        self._timeout = timeout

    def configured(self) -> bool:
        return bool(self._token)

    def __call__(self, post_url: str) -> PostMetrics:
        if not self._token:
            raise MetricsUnavailable("APIFY_TOKEN is not set; put it in .env to read numbers")

        url = f"{APIFY_BASE}/acts/{POST_DETAIL_ACTOR}/run-sync-get-dataset-items"
        body = json.dumps({"post_urls": [post_url]}).encode("utf-8")
        request = urllib.request.Request(  # nosec B310 - fixed https literal above
            url,
            data=body,
            method="POST",
            headers={
                # The token goes in a header, never the query string: a URL
                # carries into proxy logs, shell history and error traces.
                "Authorization": f"Bearer {self._token}",
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as response:  # nosec B310
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:200]
            raise MetricsUnavailable(f"Apify returned HTTP {exc.code}: {detail}") from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            raise MetricsUnavailable(f"could not reach Apify: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise MetricsUnavailable(f"Apify returned something that was not JSON: {exc}") from exc

        if not isinstance(payload, list) or not payload:
            raise MetricsUnavailable(f"no data returned for {post_url}")
        first = payload[0]
        if not isinstance(first, dict):
            raise MetricsUnavailable(f"unexpected item shape for {post_url}")
        return parse_post_detail(first)


# ---------------------------------------------------------------- Analytics


class Analytics:
    """Tracked posts, their readings over time, and the comparison."""

    def __init__(
        self,
        posts: Store,
        snapshots: Store,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._posts = posts
        self._snapshots = snapshots
        self._clock = clock

    # --------------------------------------------------------------- Tracking

    def track(self, url: str, label: str, mine: bool) -> TrackedPost:
        """Starts measuring a post. Re-tracking a dropped one revives it."""
        cleaned = normalise_url(url)
        if not cleaned:
            raise ValueError("a post URL is needed")
        if "linkedin.com" not in cleaned:
            # A wrong URL here is silent otherwise: the actor returns nothing
            # and it reads as "the post is private" a week later.
            raise ValueError("that does not look like a LinkedIn post URL")

        existing = self._by_url(cleaned)
        if existing is not None:
            revived = dataclasses.replace(
                existing,
                label=label.strip() or existing.label,
                mine=mine,
                dropped=False,
            )
            self._posts.save(revived.post_id, revived)
            return revived

        post = TrackedPost(
            post_id=f"post-{uuid.uuid4().hex[:12]}",
            url=cleaned,
            label=label.strip() or cleaned.rsplit("/", 1)[-1],
            mine=mine,
            added_at=self._clock(),
        )
        self._posts.save(post.post_id, post)
        return post

    def untrack(self, post_id: str) -> TrackedPost:
        post: TrackedPost = self._posts.get(post_id)
        dropped = dataclasses.replace(post, dropped=True)
        self._posts.save(post_id, dropped)
        return dropped

    def tracked(self, mine: bool | None = None) -> list[TrackedPost]:
        posts: list[TrackedPost] = [p for p in self._posts.list_all() if not p.dropped]
        if mine is not None:
            posts = [p for p in posts if p.mine is mine]
        return sorted(posts, key=lambda p: p.added_at, reverse=True)

    def _by_url(self, url: str) -> TrackedPost | None:
        for post in self._posts.list_all():
            if post.url == url:
                found: TrackedPost = post
                return found
        return None

    # -------------------------------------------------------------- Snapshots

    def snapshot(self, post: TrackedPost, source: MetricsSource) -> SnapshotResult:
        """Reads one post now and stores what came back."""
        try:
            metrics = source(post.url)
        except MetricsUnavailable as exc:
            return SnapshotResult(post.post_id, post.label, taken=False, error=str(exc))
        except Exception as exc:  # noqa: BLE001 - a source is somebody else's code
            return SnapshotResult(post.post_id, post.label, taken=False, error=f"{type(exc).__name__}: {exc}")

        taken = Snapshot(
            snapshot_id=f"snap-{uuid.uuid4().hex[:12]}",
            post_id=post.post_id,
            taken_at=self._clock(),
            likes=metrics.likes,
            comments=metrics.comments,
            shares=metrics.shares,
            author_followers=metrics.author_followers,
            posted_at=metrics.posted_at,
        )
        self._snapshots.save(taken.snapshot_id, taken)
        return SnapshotResult(post.post_id, post.label, taken=True, engagement=taken.engagement)

    def snapshot_all(self, source: MetricsSource) -> list[SnapshotResult]:
        """Reads every tracked post. One failure does not stop the others."""
        return [self.snapshot(post, source) for post in self.tracked()]

    def history(self, post_id: str) -> list[Snapshot]:
        found: list[Snapshot] = [s for s in self._snapshots.list_all() if s.post_id == post_id]
        return sorted(found, key=lambda s: s.taken_at)

    def latest(self, post_id: str) -> Snapshot | None:
        history = self.history(post_id)
        return history[-1] if history else None

    # ------------------------------------------------------------- Comparison

    def rows(self) -> list[dict[str, Any]]:
        """Every tracked post with its newest reading, best first."""
        built: list[dict[str, Any]] = []
        for post in self.tracked():
            latest = self.latest(post.post_id)
            built.append(
                {
                    "post_id": post.post_id,
                    "url": post.url,
                    "label": post.label,
                    "mine": post.mine,
                    "likes": latest.likes if latest else 0,
                    "comments": latest.comments if latest else 0,
                    "shares": latest.shares if latest else 0,
                    "engagement": latest.engagement if latest else 0,
                    "followers": latest.author_followers if latest else 0,
                    "taken_at": latest.taken_at.isoformat() if latest else "",
                    "readings": len(self.history(post.post_id)),
                }
            )
        return sorted(built, key=lambda r: int(r["engagement"]), reverse=True)

    def compare(self) -> dict[str, Any]:
        """Your typical post against theirs.

        Medians, with the sample size beside them, because three posts is a
        normal amount to have here and a median of three is a number that
        needs its n printed next to it to be read honestly.
        """
        rows = self.rows()
        mine = [r for r in rows if r["mine"] and r["taken_at"]]
        theirs = [r for r in rows if not r["mine"] and r["taken_at"]]

        def summarise(group: list[dict[str, Any]]) -> dict[str, Any]:
            if not group:
                return {"posts": 0, "median_engagement": 0, "median_likes": 0, "median_comments": 0, "best": 0}
            return {
                "posts": len(group),
                "median_engagement": round(statistics.median(int(r["engagement"]) for r in group)),
                "median_likes": round(statistics.median(int(r["likes"]) for r in group)),
                "median_comments": round(statistics.median(int(r["comments"]) for r in group)),
                "best": max(int(r["engagement"]) for r in group),
            }

        summary_mine = summarise(mine)
        summary_theirs = summarise(theirs)
        gap = 0
        if summary_theirs["posts"] and summary_mine["posts"]:
            gap = int(summary_mine["median_engagement"]) - int(summary_theirs["median_engagement"])
        return {
            "mine": summary_mine,
            "theirs": summary_theirs,
            # Signed, and only when both sides have something in them. A
            # comparison against nobody is the number most likely to be
            # misread as a result.
            "gap": gap,
            "comparable": bool(summary_mine["posts"] and summary_theirs["posts"]),
            "rows": rows,
        }

    def health(self) -> dict[str, Any]:
        posts = self.tracked()
        snapshots: list[Snapshot] = self._snapshots.list_all()
        last = max((s.taken_at for s in snapshots), default=None)
        return {
            "tracked": len(posts),
            "mine": sum(1 for p in posts if p.mine),
            "theirs": sum(1 for p in posts if not p.mine),
            "snapshots": len(snapshots),
            "last_read": last.isoformat() if last else "",
        }


__all__ = [
    "Analytics",
    "ApifyMetrics",
    "MetricsSource",
    "MetricsUnavailable",
    "PostMetrics",
    "Snapshot",
    "SnapshotResult",
    "TrackedPost",
    "normalise_url",
    "parse_post_detail",
]
