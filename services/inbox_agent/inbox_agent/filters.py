"""Rules you write yourself, which beat everything the scoring would decide.

The scoring in `triage` is a guess about a generic college inbox. It will be
wrong about your inbox in ways only you can see: the society mailing list you
actually care about, the "IMPORTANT: canteen menu" circular that arrives every
Monday. A filter is how you correct it once instead of being annoyed weekly.

Filters are checked **before** scoring and end the decision immediately. That
is the point — a rule you wrote and can see in a list is worth more than a
rule you have to reverse-engineer from a number. It also means a filter cannot
be outvoted by a pile of incidental signals, which is exactly the complaint
that makes people abandon a mail rule system.

Precedence, when more than one matches: `never` beats `always`. Silence is the
recoverable mistake; a buzz you did not want is the one that costs trust.
"""

from __future__ import annotations

import enum
import re
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

from inbox_agent.messages import Email
from inbox_agent.triage import Importance


class Match(enum.StrEnum):
    """What part of the message the filter looks at."""

    SENDER = "sender"
    DOMAIN = "domain"
    SUBJECT = "subject"


class Rule(enum.StrEnum):
    ALWAYS = "always"
    NEVER = "never"


@dataclass(frozen=True)
class Filter:
    """One instruction, in your words, about your mail."""

    filter_id: str
    rule: Rule
    match: Match
    value: str
    added_at: datetime
    #: Counted so a filter that never fires can be found and deleted, and one
    #: firing constantly can be recognised as doing the real work.
    hits: int = 0

    def describe(self) -> str:
        verb = "Always tell me" if self.rule is Rule.ALWAYS else "Never tell me"
        where = {Match.SENDER: "from", Match.DOMAIN: "from anyone at", Match.SUBJECT: "about"}[self.match]
        return f"{verb} {where} {self.value}"

    def matches(self, email: Email) -> bool:
        value = self.value.lower().strip()
        if not value:
            return False
        if self.match is Match.SENDER:
            return email.sender.lower() == value
        if self.match is Match.DOMAIN:
            return email.sender_domain == value.lstrip("@")
        # Subject matching is a whole-word search rather than a substring, so
        # a filter on "ai" does not silence everything containing "email".
        return re.search(rf"(?<![a-z]){re.escape(value)}(?![a-z])", email.subject.lower()) is not None


def new_filter(rule: str, match: str, value: str, when: datetime | None = None) -> Filter:
    """Builds a filter, raising on anything it cannot honour.

    Validation lives here rather than at the UI, so a filter arriving from a
    script cannot create a rule the matcher will silently never fire.
    """
    value = value.strip()
    if not value:
        raise ValueError("a filter needs something to match on")
    try:
        parsed_rule, parsed_match = Rule(rule.lower().strip()), Match(match.lower().strip())
    except ValueError as exc:
        raise ValueError(f"unknown filter: {rule}/{match}") from exc
    if parsed_match is Match.SENDER and "@" not in value:
        raise ValueError(f"'{value}' is not an email address - use the domain or subject filter instead")
    return Filter(
        filter_id=uuid.uuid4().hex[:12],
        rule=parsed_rule,
        match=parsed_match,
        value=value.lower().lstrip("@") if parsed_match is Match.DOMAIN else value.lower(),
        added_at=when or datetime.now(UTC),
    )


@dataclass
class FilterBook:
    """The filters, and the one question triage asks of them."""

    filters: list[Filter] = field(default_factory=list)

    def decide(self, email: Email) -> tuple[Importance | None, Filter | None]:
        """The importance a filter forces, or `(None, None)` to go on scoring."""
        matched = [f for f in self.filters if f.matches(email)]
        if not matched:
            return None, None
        # `never` wins. An unwanted buzz costs more than a missed one.
        for wanted in (Rule.NEVER, Rule.ALWAYS):
            for rule in matched:
                if rule.rule is wanted:
                    return (Importance.NOISE if wanted is Rule.NEVER else Importance.IMPORTANT), rule
        return None, None
