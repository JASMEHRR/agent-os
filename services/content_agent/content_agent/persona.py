"""Who you are, as the thing every post is written from.

The git-based capture answers "what did I ship". Most of what makes a post
worth reading is not that. It is what you are trying, what is going on at
college, what you changed your mind about, who you are becoming. None of that
is in a commit log, and a model that only sees commits writes a changelog with
feelings bolted on.

So this module holds a persona: facts about you, in categories a post might
draw on, gathered by talking rather than by form-filling. You tell it about
your week in plain words. It proposes what it learned, as short facts, each
tagged. You confirm or discard. Only confirmed facts are kept.

Same principle as the voice samples, and for the same reason: a model that
writes its own facts about you into the record it then writes from will drift
into a version of you it invented. The confirmation step is where that stops.

Facts expire only by being superseded, not by time. "In third year" stays true
until you say "graduated", because the system cannot know which facts are
durable and which are not, and guessing wrong in either direction is worse
than asking.
"""

from __future__ import annotations

import dataclasses
import enum
import json
import uuid
from datetime import UTC, datetime
from typing import Any, Protocol


class Area(enum.Enum):
    """Where in your life a fact sits. Chosen so each maps to a kind of post."""

    LIFE = "life"  # what is going on, honestly
    COLLEGE = "college"  # course, projects, people, deadlines
    TRYING = "trying"  # new things attempted, working or not
    BUILDING = "building"  # products, ventures, code
    LEARNING = "learning"  # skills, courses, books, mistakes
    GOALS = "goals"  # where you are headed and why
    OPINIONS = "opinions"  # things you believe that others might not
    AUDIENCE = "audience"  # who you are writing for and what they care about


class Store(Protocol):
    def get(self, entity_id: str) -> Any: ...

    def save(self, entity_id: str, entity: Any) -> None: ...

    def list_all(self) -> list[Any]: ...


@dataclasses.dataclass(frozen=True)
class Fact:
    """One confirmed thing about you."""

    fact_id: str
    area: Area
    text: str
    confirmed_at: datetime
    #: The check-in it came from, so a fact can be traced to what you said.
    source_checkin: str = ""
    #: Set when a later fact replaces this one. Superseded facts stay stored
    #: and leave the prompt: the history of what you said is part of the
    #: record, and deleting it would hide how you changed.
    superseded_by: str = ""

    @property
    def active(self) -> bool:
        return not self.superseded_by


@dataclasses.dataclass(frozen=True)
class CheckIn:
    """What you said, verbatim, and what the model proposed from it."""

    checkin_id: str
    said: str
    at: datetime
    proposed: tuple[dict[str, str], ...] = ()


#: Enough to be worth extracting from. A one-line check-in produces one-line
#: facts that are usually already known.
CHECKIN_MIN_WORDS = 20

#: Facts in the prompt, per area. The persona is context, not the content.
FACTS_PER_AREA = 6


class Persona:
    """Confirmed facts about you, and the check-in loop that gathers them."""

    def __init__(self, facts: Store, checkins: Store) -> None:
        self._facts = facts
        self._checkins = checkins

    # --------------------------------------------------------------- Check-in

    def record_checkin(self, said: str, proposed: list[dict[str, str]]) -> CheckIn:
        checkin = CheckIn(
            checkin_id=f"checkin-{uuid.uuid4().hex[:12]}",
            said=said.strip(),
            at=datetime.now(UTC),
            proposed=tuple(proposed),
        )
        self._checkins.save(checkin.checkin_id, checkin)
        return checkin

    def confirm(self, area: Area, text: str, source_checkin: str = "", supersedes: str = "") -> Fact:
        """You said yes to a proposed fact. Now it is part of the record."""
        cleaned = " ".join(text.split())
        if len(cleaned) < 8:
            raise ValueError("a fact needs to say something")
        fact = Fact(
            fact_id=f"fact-{uuid.uuid4().hex[:12]}",
            area=area,
            text=cleaned,
            confirmed_at=datetime.now(UTC),
            source_checkin=source_checkin,
        )
        self._facts.save(fact.fact_id, fact)
        if supersedes:
            old: Fact = self._facts.get(supersedes)
            self._facts.save(old.fact_id, dataclasses.replace(old, superseded_by=fact.fact_id))
        return fact

    def retire(self, fact_id: str) -> Fact:
        """No longer true, with nothing replacing it."""
        old: Fact = self._facts.get(fact_id)
        retired = dataclasses.replace(old, superseded_by="retired")
        self._facts.save(fact_id, retired)
        return retired

    # ---------------------------------------------------------------- Reading

    def facts(self, area: Area | None = None, include_superseded: bool = False) -> list[Fact]:
        found: list[Fact] = self._facts.list_all()
        if not include_superseded:
            found = [f for f in found if f.active]
        if area is not None:
            found = [f for f in found if f.area is area]
        return sorted(found, key=lambda f: f.confirmed_at, reverse=True)

    def checkins(self) -> list[CheckIn]:
        found: list[CheckIn] = self._checkins.list_all()
        return sorted(found, key=lambda c: c.at, reverse=True)

    def render(self) -> str:
        """The block that goes into every drafting prompt."""
        lines: list[str] = []
        for area in Area:
            chosen = self.facts(area)[:FACTS_PER_AREA]
            if not chosen:
                continue
            lines.append(f"{area.value.capitalize()}:")
            lines.extend(f"- {f.text}" for f in chosen)
        if not lines:
            return ""
        return "What is true about Jasmehr right now, confirmed by him:\n" + "\n".join(lines)

    def render_markdown(self) -> str:
        """For publishing to the repo, so the weekly cloud run can read it."""
        body = self.render()
        if not body:
            return "# Persona\n\nNothing confirmed yet.\n"
        return "# Persona\n\n" + body.replace("What is true about Jasmehr right now, confirmed by him:\n", "") + "\n"

    def health(self) -> dict[str, Any]:
        active = self.facts()
        return {
            "facts": len(active),
            "by_area": {a.value: len(self.facts(a)) for a in Area if self.facts(a)},
            "checkins": len(self.checkins()),
            "last_checkin": self.checkins()[0].at.isoformat() if self.checkins() else "",
        }


# --------------------------------------------------------------- Extraction

EXTRACT_BRIEF = """You are listening to Jasmehr describe his week and his life. Your only
job is to notice what is worth remembering about him as a person, so that
posts written later can draw on it.

Extract short facts, each one sentence, each tagged with exactly one area from:
life, college, trying, building, learning, goals, opinions, audience.

Rules:
- Only what he actually said. Do not infer, flatter, or complete his thought.
- Specific beats general. "Started a 5am gym routine and hated it by Thursday"
  is worth keeping. "Is working on fitness" is not.
- Opinions matter: anything he believes that a reasonable person might not.
- Skip anything that is already obvious from the facts he has confirmed before.
- 3 to 8 facts. Fewer if he said less. Never pad.

Return ONLY a JSON array like: [{"area": "trying", "text": "..."}, ...]"""


def extract_prompt(said: str, already_known: str) -> str:
    known = f"\n\nAlready confirmed, do not repeat:\n{already_known}" if already_known else ""
    return f"""{EXTRACT_BRIEF}{known}

What he said:
---
{said}
---"""


def parse_proposed(raw: str) -> list[dict[str, str]]:
    """Pulls the array out of a model response and keeps only valid entries."""
    text = raw.strip()
    start, end = text.find("["), text.rfind("]")
    if start == -1 or end == -1:
        return []
    try:
        parsed = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return []
    valid_areas = {a.value for a in Area}
    proposed: list[dict[str, str]] = []
    for item in parsed if isinstance(parsed, list) else []:
        if not isinstance(item, dict):
            continue
        area = str(item.get("area", "")).strip().lower()
        fact_text = " ".join(str(item.get("text", "")).split())
        if area in valid_areas and len(fact_text) >= 8:
            proposed.append({"area": area, "text": fact_text})
    return proposed[:8]
