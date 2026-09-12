"""Whether a listing is actually for you.

A listing site will happily return two hundred results, most of which you
cannot enter — wrong degree, wrong year, wrong country, closed yesterday. An
agent that forwards all of them has moved the problem rather than solved it.

The profile is deliberately small and literal. Guessing eligibility from prose
is where this kind of tool becomes confidently wrong, so anything the rules
cannot settle is returned as `MAYBE` and shown to you rather than decided.
"""

from __future__ import annotations

import enum
import re
from dataclasses import dataclass
from datetime import date

from opportunity_agent.opportunities import Opportunity


class Fit(enum.StrEnum):
    YES = "yes"
    #: The rules found nothing disqualifying but could not confirm it either.
    #: Shown to you, never auto-skipped: a missed opportunity is worse than a
    #: line to read.
    MAYBE = "maybe"
    NO = "no"


@dataclass(frozen=True)
class Profile:
    """You, in the terms listing sites actually filter on."""

    #: Graduation year, which is what most listings mean by "batch".
    graduation_year: int
    degree: str = ""
    branch: str = ""
    country: str = "india"
    #: Words that make something worth your time. Matched against the title
    #: and summary.
    interests: tuple[str, ...] = ()
    #: Words that rule something out however well it otherwise matches.
    avoid: tuple[str, ...] = ()
    #: Skip anything closing sooner than this - there is no point being told
    #: about a hackathon that shuts in four hours.
    min_days_to_apply: int = 1


@dataclass(frozen=True)
class Match:
    fit: Fit
    reasons: tuple[str, ...] = ()

    @property
    def worth_showing(self) -> bool:
        return self.fit is not Fit.NO


YEAR = re.compile(r"\b(20\d{2})\b")


@dataclass
class Matcher:
    """Tests a listing against a profile. No I/O, no model."""

    profile: Profile

    def assess(self, listing: Opportunity, today: date | None = None) -> Match:
        text = f"{listing.title} {listing.summary} {listing.eligibility}".lower()
        reasons: list[str] = []

        left = listing.days_left(today)
        if left is not None and left < 0:
            return Match(Fit.NO, ("the deadline has passed",))
        if left is not None and left < self.profile.min_days_to_apply:
            return Match(Fit.NO, (f"closes in {left}d, too soon to be worth starting",))

        for word in self.profile.avoid:
            if word.lower() in text:
                return Match(Fit.NO, (f"you asked to avoid '{word}'",))

        # Years named in the eligibility text are a hard filter when present:
        # "2027 and 2028 batch only" means exactly that.
        years = {int(y) for y in YEAR.findall(listing.eligibility)}
        if years and self.profile.graduation_year not in years:
            return Match(Fit.NO, (f"for the {'/'.join(str(y) for y in sorted(years))} batch",))
        if years:
            reasons.append(f"your batch ({self.profile.graduation_year}) is listed")

        hits = [w for w in self.profile.interests if w.lower() in text]
        if hits:
            reasons.append("matches " + ", ".join(hits[:3]))

        if self.profile.branch and self.profile.branch.lower() in text:
            reasons.append(f"names {self.profile.branch}")

        if not reasons:
            # Nothing disqualifying, nothing confirming. Your call, not the
            # agent's: this is the band where a confident guess does damage.
            return Match(Fit.MAYBE, ("nothing ruled it out, but nothing matched either",))
        return Match(Fit.YES, tuple(reasons))
