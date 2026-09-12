"""Opportunity Agent - finds things worth applying to and tracks the deadlines (stage A3).

Covers competitions, internships, hackathons, scholarships and certifications
with one model, because they are one shape: a deadline, an eligibility test,
and a sequence of stages after you apply.
"""

from opportunity_agent.matching import Fit, Match, Matcher, Profile
from opportunity_agent.opportunities import (
    OPEN_STAGES,
    TRANSITIONS,
    Kind,
    Opportunity,
    Stage,
    StageError,
)
from opportunity_agent.sources import JsonFeed, ListingSource, Manual, SourceError, make, parse_date
from opportunity_agent.tracker import REMINDER_DAYS, OpportunityTracker, Reminder, ScanReport

__all__ = [
    "OPEN_STAGES",
    "REMINDER_DAYS",
    "TRANSITIONS",
    "Fit",
    "JsonFeed",
    "Kind",
    "ListingSource",
    "Manual",
    "Match",
    "Matcher",
    "Opportunity",
    "OpportunityTracker",
    "Profile",
    "Reminder",
    "ScanReport",
    "SourceError",
    "Stage",
    "StageError",
    "make",
    "parse_date",
]
