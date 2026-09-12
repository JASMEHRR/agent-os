"""What the Apply tab shows, and the things it can change.

Same shape as the inbox panel: a view over the tracker, no second copy of the
stage rules. `move` calls `OpportunityTracker.move`, which calls
`Opportunity.move_to`, which is the one place that knows an application cannot
go from interested to won.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from opportunity_agent.opportunities import TRANSITIONS, Kind, Opportunity, Stage
from opportunity_agent.sources import make, parse_date
from opportunity_agent.tracker import OpportunityTracker

#: Anything closing inside this many days is flagged on the card.
SOON = 7


def _json(row: Opportunity, today: Any = None) -> dict[str, Any]:
    left = row.days_left(today)
    return {
        "id": row.opportunity_id,
        "title": row.title,
        "organiser": row.organiser,
        "url": row.url,
        "kind": row.kind.value,
        "stage": row.stage.value,
        "deadline": row.deadline.isoformat() if row.deadline else "",
        "days_left": left,
        "closing_soon": row.closing(SOON, today),
        "describes": row.describe(today),
        "matched_on": list(row.matched_on),
        "summary": row.summary,
        "eligibility": row.eligibility,
        "open": row.open,
        "next_stages": _next(row),
    }


#: Reachable, but never by pressing something. The scan sets MISSED when a
#: deadline passes untouched, and offering it as a button would invite you to
#: file your own failure by hand.
MACHINE_ONLY = frozenset({Stage.MISSED})


def _next(row: Opportunity) -> list[str]:
    """Which buttons the card offers, read from the transition table rather
    than hardcoded, so changing the machine moves the buttons with it."""
    return sorted(s.value for s in TRANSITIONS[row.stage] - MACHINE_ONLY)


@dataclass
class ApplyPanel:
    tracker: OpportunityTracker

    def state(self) -> dict[str, Any]:
        today = datetime.now(UTC).date()
        rows = self.tracker.open_ones()
        counts = {s.value: n for s, n in self.tracker.by_stage().items()}
        return {
            "open": [_json(r, today) for r in rows],
            "closing": [_json(r, today) for r in self.tracker.closing_within(SOON, today)],
            "counts": counts,
            "sources": len(self.tracker.sources),
        }

    def add(self, title: str, organiser: str, url: str, due: str = "", kind: str = "competition") -> dict[str, Any]:
        if not title.strip():
            raise ValueError("it needs a title")
        made = make(title, organiser, url, Kind(kind), parse_date(due) if due else None)
        self.tracker.store.save(made.opportunity_id, made)
        return _json(made)

    def move(self, opportunity_id: str, stage: str) -> dict[str, Any]:
        return _json(self.tracker.move(opportunity_id, Stage(stage)))

    def scan(self) -> dict[str, Any]:
        report = self.tracker.scan()
        return {
            "found": report.found,
            "added": report.added,
            "matched": report.matched,
            "maybe": report.maybe,
            "rejected": report.rejected,
            "reminded": report.reminded,
            "missed": report.missed,
            "errors": list(report.errors),
        }
