"""Where listings come from. A port, an HTML adapter, and a file adapter.

**On scraping.** Unstop, Internshala and the rest publish no public API, so a
listing adapter reads their pages. That is fragile by nature: markup changes
and the parser returns nothing. It therefore fails *loudly and emptily* — a
source that cannot parse returns no listings and says so, rather than returning
half-parsed rows that would enter your tracker as real opportunities with
missing deadlines.

It is also polite by construction: one request per run, a real User-Agent, and
no crawling beyond the listing page. Check the site's terms before pointing it
anywhere; a personal, low-rate reader of pages you can already see in a browser
is a different thing from a bulk scraper, but that is your call to make and not
a decision this code should make silently for you.

`JsonFeed` is the adapter to prefer wherever a site offers a real feed, and
`Manual` exists so the whole tracker works with no scraping at all — you paste
in what you find, and everything downstream behaves identically.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from html import unescape
from typing import Any, Protocol

from opportunity_agent.opportunities import Kind, Opportunity

TIMEOUT_SECONDS = 25
SUMMARY_CHARS = 400

#: Identifying rather than pretending to be a browser. A site that wants to
#: refuse this should be able to.
USER_AGENT = "agent-os-opportunity-agent/1.0 (personal use; one request per run)"

#: Date shapes these sites actually use, in the order worth trying.
DATE_FORMATS = ("%Y-%m-%d", "%d %b %Y", "%d %B %Y", "%b %d, %Y", "%B %d, %Y", "%d/%m/%Y", "%d-%m-%Y")


class ListingSource(Protocol):
    def listings(self) -> list[Opportunity]: ...


class SourceError(Exception):
    """The source could not be read or could not be parsed."""


def parse_date(text: str) -> date | None:
    """A deadline from whatever the listing wrote. None when unreadable.

    None is a real answer, not a failure: plenty of listings genuinely do not
    state a closing date, and inventing one would put a false deadline in the
    tracker, which is worse than an absent one.
    """
    cleaned = re.sub(r"(?<=\d)(st|nd|rd|th)\b", "", unescape(text).strip(), flags=re.I)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,")
    for pattern in DATE_FORMATS:
        try:
            return datetime.strptime(cleaned, pattern).date()
        except ValueError:
            continue
    # An ISO timestamp with a time on it is common in embedded JSON.
    try:
        return datetime.fromisoformat(cleaned.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def make(
    title: str,
    organiser: str,
    url: str,
    kind: Kind = Kind.COMPETITION,
    deadline: date | None = None,
    eligibility: str = "",
    summary: str = "",
    when: datetime | None = None,
) -> Opportunity:
    """Builds a listing with a stable id derived from its URL.

    Derived rather than random, so the same listing seen on two runs is the
    same row and is not re-announced.
    """
    return Opportunity(
        opportunity_id=uuid.uuid5(uuid.NAMESPACE_URL, url or f"{title}|{organiser}").hex[:16],
        title=unescape(title).strip(),
        organiser=unescape(organiser).strip(),
        url=url.strip(),
        kind=kind,
        deadline=deadline,
        found_at=when or datetime.now(UTC),
        eligibility=unescape(eligibility).strip()[:SUMMARY_CHARS],
        summary=unescape(summary).strip()[:SUMMARY_CHARS],
    )


def _get(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "*/*"})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:  # nosec B310 # noqa: S310
            return str(response.read().decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as exc:
        raise SourceError(f"HTTP {exc.code} from {url}") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise SourceError(f"could not reach {url}: {exc}") from exc


@dataclass
class JsonFeed:
    """Reads listings from a JSON endpoint, given a mapping of field names.

    The right adapter wherever one exists. Sites that render listings from an
    internal JSON call can usually be read this way, which is both sturdier and
    lighter than parsing their HTML.
    """

    url: str
    kind: Kind = Kind.COMPETITION
    #: Where the list of rows lives, as dotted keys, e.g. "data.opportunities".
    rows_at: str = ""
    title_key: str = "title"
    organiser_key: str = "organisation"
    url_key: str = "url"
    deadline_key: str = "end_date"
    eligibility_key: str = "eligibility"
    summary_key: str = "description"
    fetch: Any = field(default=_get, repr=False)

    def listings(self) -> list[Opportunity]:
        payload = json.loads(self.fetch(self.url))
        rows: Any = payload
        for key in filter(None, self.rows_at.split(".")):
            rows = rows.get(key, []) if isinstance(rows, dict) else []
        if not isinstance(rows, list):
            raise SourceError(f"expected a list of listings at '{self.rows_at}', found {type(rows).__name__}")

        found: list[Opportunity] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            title = str(row.get(self.title_key, "")).strip()
            if not title:
                continue
            found.append(
                make(
                    title=title,
                    organiser=str(row.get(self.organiser_key, "") or ""),
                    url=str(row.get(self.url_key, "") or ""),
                    kind=self.kind,
                    deadline=parse_date(str(row.get(self.deadline_key, "") or "")),
                    eligibility=str(row.get(self.eligibility_key, "") or ""),
                    summary=str(row.get(self.summary_key, "") or ""),
                )
            )
        return found


@dataclass
class Manual:
    """Listings you paste in yourself.

    Not a fallback. Anything worth applying to that a friend forwards you, or
    that a site will not let a program read, still belongs in the tracker with
    the deadline arithmetic and the stage machine working on it.
    """

    entries: list[Opportunity] = field(default_factory=list)

    def add(self, title: str, organiser: str, url: str, deadline: str = "", **rest: Any) -> Opportunity:
        made = make(title, organiser, url, deadline=parse_date(deadline) if deadline else None, **rest)
        self.entries.append(made)
        return made

    def listings(self) -> list[Opportunity]:
        return list(self.entries)
