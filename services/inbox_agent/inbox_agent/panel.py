"""What the Inbox tab shows, and the three things it can change.

A view, not a second copy of the logic. Everything here reads or calls the
agent; nothing re-decides what is important. The web layer consumes this
through a Protocol, so `content_agent` never imports this package and the two
can be changed independently.

Dicts rather than dataclasses on the way out, because the only consumer is
`json.dumps` and a dataclass that exists solely to be flattened is a layer
that costs a file and buys nothing.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from inbox_agent.agent import Alert, InboxAgent
from inbox_agent.filters import Filter, FilterBook, new_filter
from persistence.repository import NotFound, Repository

#: Most recent decisions kept on screen. Enough to see whether the rules are
#: behaving, short enough to read.
RECENT = 40


def _alert_json(alert: Alert) -> dict[str, Any]:
    return {
        "message_id": alert.message_id,
        "subject": alert.subject,
        "sender": alert.sender,
        "importance": alert.importance.value,
        "reason": alert.reason,
        "decided_at": alert.decided_at.isoformat(),
        "sent_at": alert.sent_at.isoformat() if alert.sent_at else "",
        "held_because": alert.held_because,
        "pending": alert.pending,
    }


def _filter_json(rule: Filter) -> dict[str, Any]:
    return {
        "filter_id": rule.filter_id,
        "rule": rule.rule.value,
        "match": rule.match.value,
        "value": rule.value,
        "describes": rule.describe(),
        "hits": rule.hits,
    }


@dataclass
class InboxPanel:
    """Reads the inbox agent's state and edits its filters."""

    filters: Repository[Filter]
    alerts: Repository[Alert]
    #: None when the mailbox is not configured. The tab then explains what is
    #: missing rather than showing an empty list that looks like good news.
    agent: InboxAgent | None = None
    #: What `--check` would have said, passed in so the tab can show it.
    setup: str = ""

    def book(self) -> FilterBook:
        return FilterBook(list(self.filters.list_all()))

    def state(self) -> dict[str, Any]:
        decided = sorted(self.alerts.list_all(), key=lambda a: a.decided_at, reverse=True)
        waiting = [a for a in decided if a.pending]
        return {
            "configured": self.agent is not None,
            "setup": self.setup,
            "recent": [_alert_json(a) for a in decided[:RECENT]],
            "waiting": [_alert_json(a) for a in waiting],
            "filters": [_filter_json(f) for f in sorted(self.filters.list_all(), key=lambda f: f.added_at)],
            "counts": {
                "decided": len(decided),
                "waiting": len(waiting),
                "texted": sum(1 for a in decided if not a.pending),
            },
        }

    # ------------------------------------------------------------------ edits

    def add_filter(self, rule: str, match: str, value: str) -> dict[str, Any]:
        made = new_filter(rule, match, value)
        self.filters.save(made.filter_id, made)
        return _filter_json(made)

    def remove_filter(self, filter_id: str) -> None:
        try:
            self.filters.delete(filter_id)
        except NotFound:
            # Deleting something already gone is the outcome the caller
            # wanted, so it is not an error worth surfacing to a button.
            return

    def check_now(self) -> dict[str, Any]:
        """Runs one poll on demand, for the "check now" button."""
        if self.agent is None:
            raise RuntimeError("the mailbox is not connected yet")
        report = self.agent.run_once()
        return {
            "seen": report.seen,
            "alerted": report.alerted,
            "held": report.held,
            "routine": report.routine,
            "noise": report.noise,
            "digest_sent": report.digest_sent,
            "failures": list(report.failures),
        }

    def send_digest(self) -> bool:
        if self.agent is None:
            raise RuntimeError("the mailbox is not connected yet")
        return self.agent.send_digest()
