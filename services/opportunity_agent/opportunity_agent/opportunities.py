"""Things you could apply to, and where you are with each one.

Covers both of the things people usually treat as separate — competitions and
internships on a listing site, and certifications worth taking — because they
are the same object. Each has a deadline, an eligibility test you either pass
or do not, and a sequence of stages you move through after applying. Modelling
them twice would mean writing the deadline arithmetic twice and getting it
subtly different the second time.

The stage machine is the part worth being strict about. An application that
silently stays in `INTERESTED` until the deadline passes is the exact failure
this agent exists to prevent, so a stage change is a method with rules rather
than a field anyone can overwrite.
"""

from __future__ import annotations

import dataclasses
import enum
from dataclasses import dataclass
from datetime import UTC, date, datetime


class Kind(enum.StrEnum):
    """What sort of thing this is. Only affects how it is described."""

    COMPETITION = "competition"
    INTERNSHIP = "internship"
    HACKATHON = "hackathon"
    SCHOLARSHIP = "scholarship"
    CERTIFICATION = "certification"
    JOB = "job"


class Stage(enum.StrEnum):
    """Where you are with it."""

    #: Found and matched, nothing done yet.
    INTERESTED = "interested"
    APPLIED = "applied"
    #: Past the first cut: shortlisted, invited to a round, whatever it is.
    ADVANCED = "advanced"
    #: Reached the end and it went your way.
    WON = "won"
    REJECTED = "rejected"
    #: You decided against it. Distinct from rejected, and the distinction
    #: matters: one is a decision you made, the other is one made about you.
    SKIPPED = "skipped"
    #: The deadline went by while it was still INTERESTED. Recorded rather
    #: than deleted, because a pile of these is the feedback that the agent
    #: is finding things you never act on.
    MISSED = "missed"


#: Which stages can follow which. Deliberately not a free-for-all: an
#: application cannot go from INTERESTED to WON without having been APPLIED,
#: and a terminal stage is terminal.
TRANSITIONS: dict[Stage, frozenset[Stage]] = {
    Stage.INTERESTED: frozenset({Stage.APPLIED, Stage.SKIPPED, Stage.MISSED}),
    Stage.APPLIED: frozenset({Stage.ADVANCED, Stage.REJECTED, Stage.SKIPPED}),
    Stage.ADVANCED: frozenset({Stage.ADVANCED, Stage.WON, Stage.REJECTED, Stage.SKIPPED}),
    Stage.WON: frozenset(),
    Stage.REJECTED: frozenset(),
    Stage.SKIPPED: frozenset({Stage.INTERESTED}),
    Stage.MISSED: frozenset(),
}

OPEN_STAGES = frozenset({Stage.INTERESTED, Stage.APPLIED, Stage.ADVANCED})


class StageError(Exception):
    """A stage change the machine does not allow."""


@dataclass(frozen=True)
class Opportunity:
    """One thing you could apply to."""

    opportunity_id: str
    title: str
    organiser: str
    url: str
    kind: Kind
    deadline: date | None
    found_at: datetime
    stage: Stage = Stage.INTERESTED
    #: What the listing said about who may apply, kept verbatim so a match can
    #: be checked by a human afterwards.
    eligibility: str = ""
    #: Free text from the listing, truncated at the source.
    summary: str = ""
    #: Why the matcher thought this was for you, for the same reason a triage
    #: verdict carries its signals.
    matched_on: tuple[str, ...] = ()
    stage_changed_at: datetime | None = None
    note: str = ""

    @property
    def open(self) -> bool:
        return self.stage in OPEN_STAGES

    def days_left(self, today: date | None = None) -> int | None:
        """Whole days until the deadline. Negative once it has passed."""
        if self.deadline is None:
            return None
        return (self.deadline - (today or datetime.now(UTC).date())).days

    def closing(self, within: int, today: date | None = None) -> bool:
        """Whether the deadline is that close *and still yours to act on*.

        `INTERESTED` rather than `open`: once you have applied, the closing
        date stops being a thing you can do anything about, and listing it
        under "closing soon" would be noise. This is the same condition the
        reminder ladder uses, kept in one place so the two cannot disagree.
        """
        left = self.days_left(today)
        return self.stage is Stage.INTERESTED and left is not None and 0 <= left <= within

    def move_to(self, stage: Stage, when: datetime | None = None, note: str = "") -> Opportunity:
        """Advances the stage, or refuses and says what was allowed instead."""
        if stage not in TRANSITIONS[self.stage]:
            allowed = ", ".join(sorted(s.value for s in TRANSITIONS[self.stage])) or "nothing - it is finished"
            raise StageError(f"cannot go from {self.stage.value} to {stage.value}; allowed: {allowed}")
        return dataclasses.replace(
            self,
            stage=stage,
            stage_changed_at=when or datetime.now(UTC),
            note=note or self.note,
        )

    def describe(self, today: date | None = None) -> str:
        left = self.days_left(today)
        if left is None:
            when = "no deadline listed"
        elif left < 0:
            when = f"closed {abs(left)}d ago"
        elif left == 0:
            when = "closes TODAY"
        else:
            when = f"{left}d left"
        return f"{self.title} - {self.organiser} ({when})"
