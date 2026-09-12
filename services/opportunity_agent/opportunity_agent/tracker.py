"""Finds things worth applying to, then makes sure you do not forget them.

Two jobs, and the second is the one that matters. Finding opportunities is
easy and most tools stop there; what loses you the opportunity is the three
weeks between finding it and the deadline, during which nobody reminds you.

So the tracker keeps state per opportunity and nags on a schedule that gets
tighter as the deadline approaches, rather than once when it is found:

* found, and it matches you
* a week out, if you have not applied
* three days out
* the day before, which is the last point where applying is still realistic
* the day it closes, if it is still open

Each of those fires at most once per opportunity, which is the difference
between a reminder and a nuisance. Anything still `INTERESTED` when the
deadline passes is marked `MISSED` and counted, because a growing pile of
those is the honest signal that the matcher is finding things you do not
actually want.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime

from opportunity_agent.matching import Fit, Matcher
from opportunity_agent.opportunities import Opportunity, Stage
from opportunity_agent.sources import ListingSource, SourceError
from persistence.repository import NotFound, Repository

#: Days before a deadline at which a reminder fires, widest first. Each fires
#: once: crossing 7 and 3 in a single run sends the 3-day one only.
REMINDER_DAYS = (7, 3, 1, 0)


@dataclass(frozen=True)
class Reminder:
    """A nudge already sent, so it is never sent twice."""

    reminder_id: str
    opportunity_id: str
    days_out: int
    sent_at: datetime


@dataclass(frozen=True)
class ScanReport:
    found: int = 0
    added: int = 0
    matched: int = 0
    maybe: int = 0
    rejected: int = 0
    reminded: int = 0
    missed: int = 0
    errors: tuple[str, ...] = ()


def _reminder_id(opportunity_id: str, days_out: int) -> str:
    return f"{opportunity_id}:{days_out}"


@dataclass
class OpportunityTracker:
    """Scans sources, keeps what fits, and reminds you before it closes."""

    sources: list[ListingSource]
    matcher: Matcher
    store: Repository[Opportunity]
    reminders: Repository[Reminder]
    #: Called with (opportunity, why) for anything worth telling you about.
    #: Injected so the tracker does not care whether that is WhatsApp, the
    #: console, or a test collecting tuples.
    announce: Callable[[Opportunity, str], None] = field(default=lambda o, why: None)
    now: Callable[[], datetime] = field(default=lambda: datetime.now(UTC))

    # ----------------------------------------------------------------- reading

    def open_ones(self) -> list[Opportunity]:
        """Everything still live, soonest deadline first.

        Undated opportunities sort last: something with a real date competes
        for attention on that date, and something without one never should.
        """
        live = [o for o in self.store.list_all() if o.open]
        return sorted(live, key=lambda o: (o.deadline is None, o.deadline or date.max, o.title))

    def closing_within(self, days: int, today: date | None = None) -> list[Opportunity]:
        today = today or self.now().date()
        return [o for o in self.open_ones() if o.closing(days, today)]

    def by_stage(self) -> dict[Stage, int]:
        counts: dict[Stage, int] = {}
        for opportunity in self.store.list_all():
            counts[opportunity.stage] = counts.get(opportunity.stage, 0) + 1
        return counts

    # ----------------------------------------------------------------- writing

    def move(self, opportunity_id: str, stage: Stage, note: str = "") -> Opportunity:
        """Records that you applied, advanced, or decided against it."""
        moved = self.store.get(opportunity_id).move_to(stage, self.now(), note)
        self.store.save(opportunity_id, moved)
        return moved

    def _already_reminded(self, opportunity_id: str, days_out: int) -> bool:
        try:
            self.reminders.get(_reminder_id(opportunity_id, days_out))
        except NotFound:
            return False
        return True

    def _remind(self, opportunity: Opportunity, days_out: int, when: datetime) -> bool:
        marker = _reminder_id(opportunity.opportunity_id, days_out)
        self.reminders.save(marker, Reminder(marker, opportunity.opportunity_id, days_out, when))
        urgency = {
            0: "closes TODAY and you have not applied",
            1: "closes tomorrow and you have not applied",
        }.get(days_out, f"closes in {days_out} days and you have not applied")
        self.announce(opportunity, urgency)
        return True

    # -------------------------------------------------------------------- scan

    def scan(self) -> ScanReport:
        """One pass: read the sources, keep what fits, nudge what is closing."""
        when = self.now()
        today = when.date()
        found = added = matched = maybe = rejected = reminded = missed = 0
        errors: list[str] = []

        for source in self.sources:
            try:
                listings = source.listings()
            except (SourceError, ValueError) as exc:
                # A broken source must not stop the others, and must not look
                # like a quiet day either.
                errors.append(f"{source.__class__.__name__}: {exc}")
                continue

            for listing in listings:
                found += 1
                try:
                    self.store.get(listing.opportunity_id)
                    continue  # Seen on an earlier run; never re-announced.
                except NotFound:
                    pass

                verdict = self.matcher.assess(listing, today)
                if verdict.fit is Fit.NO:
                    rejected += 1
                    continue

                kept = dataclasses.replace(listing, matched_on=verdict.reasons)
                self.store.save(kept.opportunity_id, kept)
                added += 1
                if verdict.fit is Fit.YES:
                    matched += 1
                    self.announce(kept, "new match: " + ", ".join(verdict.reasons))
                else:
                    maybe += 1

        # Deadlines, over everything held rather than only what arrived today.
        for opportunity in self.open_ones():
            left = opportunity.days_left(today)
            if left is None:
                continue
            if left < 0:
                if opportunity.stage is Stage.INTERESTED:
                    self.store.save(
                        opportunity.opportunity_id,
                        opportunity.move_to(Stage.MISSED, when, "the deadline passed"),
                    )
                    missed += 1
                continue
            if opportunity.stage is not Stage.INTERESTED:
                continue  # Already applied; the deadline is no longer yours.
            # The tightest rung that applies, and only if it has not already
            # fired. Two things this must not do: announce something closing
            # today as closing tomorrow (which widest-first would, matching
            # `0 <= 1` before `0 <= 0`), and walk outward to the next unfired
            # rung, which would re-announce the same listing every scan.
            applicable = [mark for mark in REMINDER_DAYS if left <= mark]
            if applicable:
                tightest = min(applicable)
                if not self._already_reminded(opportunity.opportunity_id, tightest):
                    reminded += self._remind(opportunity, tightest, when)

        return ScanReport(found, added, matched, maybe, rejected, reminded, missed, tuple(errors))
