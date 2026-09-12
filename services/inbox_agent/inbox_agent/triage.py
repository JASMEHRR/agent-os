"""Decides whether a message is worth interrupting someone for.

Two layers, in this order, and the order is the point.

**Rules run first and usually finish the job.** They are free, instantaneous,
identical every time, and explainable afterwards — the verdict carries the
signals that produced it, so "why did it text me about this" always has an
answer. Bulk headers, direct addressing, known senders and a college-specific
vocabulary get most mail right.

**The model sees only what the rules could not settle.** A message scoring
clearly high or clearly low never reaches it. That keeps the token bill
proportional to genuine ambiguity rather than to inbox volume, and it means an
outage in the model degrades the agent to rules rather than stopping it.

Nothing here performs I/O. `classify` is injected, so the whole engine is
testable without a network and the privacy rules in `sources` decide what the
model is ever shown.
"""

from __future__ import annotations

import enum
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol

from inbox_agent.messages import Email


class FilterSource(Protocol):
    """What `Triage` needs from a filter book, and nothing more.

    Declared here rather than imported from `filters` so the dependency runs
    one way: filters knows about triage, triage knows only this shape.
    """

    def decide(self, email: Email) -> tuple[Any, Any]: ...


class Importance(enum.StrEnum):
    """What the agent will do about a message, not how the sender felt."""

    #: Text now, regardless of the hour.
    URGENT = "urgent"
    #: Text now, unless it is the middle of the night.
    IMPORTANT = "important"
    #: Worth seeing eventually. Counted, never buzzed.
    ROUTINE = "routine"
    #: Bulk, promotional, automated. Not worth a line in the digest.
    NOISE = "noise"


ALERTING = frozenset({Importance.URGENT, Importance.IMPORTANT})


@dataclass(frozen=True)
class Signal:
    """One reason the score moved, kept so a verdict can be explained."""

    name: str
    weight: int
    detail: str = ""


@dataclass(frozen=True)
class Verdict:
    importance: Importance
    score: int
    signals: tuple[Signal, ...] = ()
    reason: str = ""
    #: "rules" or "model". Recorded because the two fail differently, and
    #: when the agent starts mis-firing the first question is which one did it.
    decided_by: str = "rules"

    @property
    def alerts(self) -> bool:
        return self.importance in ALERTING

    def explain(self) -> str:
        """The signals, heaviest first, as one line for a log or a digest."""
        ranked = sorted(self.signals, key=lambda s: abs(s.weight), reverse=True)
        return ", ".join(f"{s.name}{f' ({s.detail})' if s.detail else ''} {s.weight:+d}" for s in ranked)


# --------------------------------------------------------------- vocabulary

#: Words that, in a university inbox, tend to precede a consequence. Weighted
#: by what it costs to miss one: a missed placement shortlist is unrecoverable,
#: a missed seminar invitation is not.
SUBJECT_TERMS: tuple[tuple[int, str, tuple[str, ...]], ...] = (
    (
        5,
        "placement",
        ("placement", "shortlist", "shortlisted", "interview", "offer letter", "recruitment", "drive", "ppo"),
    ),
    (5, "money", ("fee", "fees", "payment due", "scholarship", "refund", "dues", "fine")),
    (4, "assessment", ("exam", "examination", "result", "grade", "marks", "revaluation", "supplementary", "viva")),
    (4, "deadline", ("deadline", "last date", "due date", "submit by", "closes on", "final call", "expires")),
    (
        3,
        "administration",
        ("hostel", "attendance", "registration", "enrollment", "admit card", "transcript", "id card"),
    ),
    (3, "academic", ("assignment", "project", "thesis", "dissertation", "internship", "lab", "practical")),
)

#: Time pressure. Weak alone, decisive on top of a subject that already matters.
URGENCY_TERMS: tuple[str, ...] = (
    "urgent",
    "immediately",
    "asap",
    "today",
    "tomorrow",
    "by tonight",
    "within 24",
    "action required",
    "mandatory",
    "compulsory",
    "reminder",
    "final reminder",
    "do not ignore",
)

#: Mail that is trying to be interesting rather than being important.
NOISE_TERMS: tuple[str, ...] = (
    "newsletter",
    "webinar",
    "unsubscribe",
    "promotion",
    "offer ends",
    "sale",
    "discount",
    "invitation to connect",
    "survey",
    "feedback form",
    "quiz",
    "contest",
    "hiring challenge",
)

#: Local parts that are almost never a person waiting on a reply.
AUTOMATED_SENDERS: tuple[str, ...] = (
    "no-reply",
    "noreply",
    "donotreply",
    "do-not-reply",
    "mailer-daemon",
    "notification",
)

#: Score at or above which the rules alone will interrupt someone.
URGENT_AT = 11
IMPORTANT_AT = 6
#: Score at or below which the rules alone will stay silent.
NOISE_AT = -2


def _contains(haystack: str, needles: Sequence[str]) -> list[str]:
    """Whole-word-ish matching, so "fee" does not fire on "coffee"."""
    found = []
    for needle in needles:
        if re.search(rf"(?<![a-z]){re.escape(needle)}(?![a-z])", haystack):
            found.append(needle)
    return found


@dataclass
class Triage:
    """Scores a message, and asks the model only when the score is unclear.

    `me` is the address that counts as "addressed to you". `vip_senders` and
    `vip_domains` are the people and offices whose mail should reach you on
    their own authority — a supervisor, the placement cell, the exam section.
    """

    me: str
    vip_senders: frozenset[str] = frozenset()
    vip_domains: frozenset[str] = frozenset()
    muted_senders: frozenset[str] = frozenset()
    #: Your own rules. Consulted before any scoring and final when they match.
    #: Typed as the Protocol below so `filters.FilterBook` can import from this
    #: module without this module importing it back.
    filters: FilterSource | None = None
    #: Injected. Given (subject, sender, snippet), returns one of the
    #: `Importance` values as a bare string. Absent means rules-only, which is
    #: a supported mode rather than a degraded one.
    classify: Callable[[str, str, str], str] | None = None
    _signals: list[Signal] = field(default_factory=list, init=False, repr=False)

    # ------------------------------------------------------------------ rules

    def signals_for(self, email: Email) -> tuple[Signal, ...]:
        """Every signal the rules can see, with no thresholds applied yet."""
        found: list[Signal] = []
        subject = email.subject.lower()
        sender = email.sender.lower()
        domain = email.sender_domain

        if sender in self.muted_senders:
            found.append(Signal("muted sender", -20, sender))
        if sender in self.vip_senders:
            found.append(Signal("known sender", 5, sender))
        elif domain and domain in self.vip_domains:
            # Small on purpose. In a college inbox the college domain is the
            # baseline, not a distinguishing signal: weighted like a named
            # sender it pushed every routine circular into URGENT, which is
            # how an alerting agent teaches someone to ignore it.
            found.append(Signal("known domain", 2, domain))

        for weight, name, terms in SUBJECT_TERMS:
            hits = _contains(subject, terms)
            if hits:
                found.append(Signal(name, weight, hits[0]))

        urgent_hits = _contains(subject, URGENCY_TERMS)
        if urgent_hits:
            found.append(Signal("time pressure", 3, urgent_hits[0]))

        noise_hits = _contains(subject, NOISE_TERMS)
        if noise_hits:
            found.append(Signal("promotional wording", -4, noise_hits[0]))

        # Bulk headers are the single most reliable signal available, and the
        # only one the sender cannot accidentally fake by writing "urgent".
        if email.is_bulk:
            found.append(Signal("bulk mail", -6))
        if any(sender.startswith(prefix) for prefix in AUTOMATED_SENDERS):
            found.append(Signal("automated sender", -3))

        if email.addressed_to(self.me):
            found.append(Signal("addressed to you", 3))
        elif not email.is_bulk:
            # Neither named nor announced as bulk: a bcc, or a list that does
            # not label itself. Mildly against, never decisive.
            found.append(Signal("not named as a recipient", -1))

        if email.in_reply_to:
            found.append(Signal("reply in a thread", 2))

        return tuple(found)

    def score(self, email: Email) -> tuple[int, tuple[Signal, ...]]:
        signals = self.signals_for(email)
        return sum(s.weight for s in signals), signals

    # ------------------------------------------------------------- the verdict

    def judge(self, email: Email) -> Verdict:
        """Rules, then the model only for what the rules left open.

        A score alone is not allowed to raise an alert. Being named in To:,
        arriving from the college domain and saying "tomorrow" add up to a
        respectable number while describing a library book, and a threshold
        crossed by generic signals is how this agent would start texting about
        everything. So an alert additionally requires a *substantive* signal —
        a subject category, or a sender on the named list — and the difference
        between the two alerting bands is time pressure rather than size.
        """
        if self.filters is not None:
            forced, rule = self.filters.decide(email)
            if forced is not None:
                total, signals = self.score(email)
                return Verdict(forced, total, signals, f"your rule: {rule.describe()}", "filter")

        total, signals = self.score(email)
        names = {s.name for s in signals}
        substantive = bool(names & {name for _, name, _ in SUBJECT_TERMS} or "known sender" in names)
        pressing = "time pressure" in names

        if total >= URGENT_AT and substantive and pressing:
            return Verdict(Importance.URGENT, total, signals, "high stakes and a deadline in sight")
        if total >= IMPORTANT_AT and substantive:
            return Verdict(Importance.IMPORTANT, total, signals, "the rules are confident this matters")
        if total <= NOISE_AT:
            return Verdict(Importance.NOISE, total, signals, "the rules are confident this is bulk")
        if total >= IMPORTANT_AT:
            # Score without substance. Worth reading, not worth a buzz.
            return Verdict(Importance.ROUTINE, total, signals, "no subject category and no named sender")

        if self.classify is None:
            return Verdict(Importance.ROUTINE, total, signals, "no clear signal, and no model configured")

        return self._ask_model(email, total, signals)

    def _ask_model(self, email: Email, total: int, signals: tuple[Signal, ...]) -> Verdict:
        try:
            answer = self.classify(email.subject, email.sender, email.body)  # type: ignore[misc]
        except Exception as exc:  # noqa: BLE001 - any model failure degrades to rules
            # A classifier that is down must not stop the run, and must not
            # silently promote either. Routine is the safe direction: the
            # message still reaches the digest, it just does not buzz.
            return Verdict(Importance.ROUTINE, total, signals, f"model unavailable ({exc.__class__.__name__})")

        wanted = str(answer).strip().lower()
        for level in Importance:
            if level.value == wanted:
                return Verdict(level, total, signals, "the rules were unclear, so the model decided", "model")
        return Verdict(Importance.ROUTINE, total, signals, f"model returned something unusable ({wanted!r})")
