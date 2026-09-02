"""The persona: facts about you, confirmed by you, written from by every draft.

The property that matters is provenance. A model that could write its own
facts about you into the record it then writes from would drift into a version
of you it invented. So the tests here are mostly about what cannot get in.
"""

from __future__ import annotations

import json

import pytest

from content_agent import ContentStudio
from content_agent.persona import Area, Persona, extract_prompt, parse_proposed
from persistence import InMemoryRepository

NOTE = (
    "This week I wired Groq behind the model router. It took 3 attempts because the free "
    "tier rate limits at 429 rather than billing, so I built a cooldown that degrades to a "
    "smaller model. The suite is at 1870 passing tests."
)

PAYLOAD = json.dumps(
    {
        "hook": "I spent 3 attempts learning a free API tier fails differently than a paid one.",
        "body": "A paid tier bills you. A free tier stops answering.",
        "close": "What small failure taught you most this week?",
        "hashtags": ["#agentarchitecture", "#buildinpublic", "#pythontesting"],
    }
)


def _persona() -> Persona:
    return Persona(InMemoryRepository(), InMemoryRepository())


# ------------------------------------------------------------- Provenance


def test_a_proposed_fact_is_not_a_fact_until_confirmed() -> None:
    """The check-in records what the model proposed. Nothing enters the
    persona until you say yes."""
    persona = _persona()
    persona.record_checkin(
        "I started a 5am gym routine this week and hated it by Thursday, " * 2,
        [{"area": "trying", "text": "Started a 5am gym routine and hated it by Thursday"}],
    )

    assert persona.facts() == []
    assert persona.health()["checkins"] == 1


def test_confirmed_facts_reach_every_drafting_prompt() -> None:
    seen: list[str] = []

    def complete(prompt: str, max_tokens: int) -> str:
        seen.append(prompt)
        return PAYLOAD

    persona = _persona()
    persona.confirm(Area.COLLEGE, "Final year BBA at Chitkara, thesis on AI in marketing")
    studio = ContentStudio(complete, InMemoryRepository(), InMemoryRepository(), persona=persona)

    studio.draft(studio.capture(NOTE))

    assert "confirmed by him" in seen[0]
    assert "thesis on AI in marketing" in seen[0]


def test_a_superseded_fact_leaves_the_prompt_but_stays_in_the_record() -> None:
    """Deleting history would hide how you changed."""
    persona = _persona()
    old = persona.confirm(Area.COLLEGE, "In third year")
    persona.confirm(Area.COLLEGE, "Graduated in May", supersedes=old.fact_id)

    assert [f.text for f in persona.facts(Area.COLLEGE)] == ["Graduated in May"]
    assert len(persona.facts(Area.COLLEGE, include_superseded=True)) == 2
    assert "third year" not in persona.render()


def test_retiring_a_fact_removes_it_without_a_replacement() -> None:
    persona = _persona()
    fact = persona.confirm(Area.TRYING, "Doing cold showers every morning")
    persona.retire(fact.fact_id)

    assert persona.facts() == []


def test_an_empty_fact_is_refused() -> None:
    with pytest.raises(ValueError):
        _persona().confirm(Area.LIFE, "ok")


# ------------------------------------------------------------- Extraction


def test_extraction_keeps_only_valid_areas_and_drops_junk() -> None:
    raw = json.dumps(
        [
            {"area": "trying", "text": "Started a 5am gym routine and hated it by Thursday"},
            {"area": "nonsense", "text": "should be dropped"},
            {"area": "goals", "text": "x"},
            "not a dict",
        ]
    )

    assert parse_proposed(raw) == [
        {"area": "trying", "text": "Started a 5am gym routine and hated it by Thursday"},
    ]


def test_extraction_survives_prose_around_the_array() -> None:
    raw = 'Sure! Here you go:\n[{"area": "life", "text": "Moved into a new flat near campus"}]\nHope that helps.'

    assert parse_proposed(raw)[0]["text"] == "Moved into a new flat near campus"


def test_extraction_is_capped() -> None:
    raw = json.dumps([{"area": "life", "text": f"Fact number {i} about the week"} for i in range(20)])

    assert len(parse_proposed(raw)) == 8


def test_the_extraction_prompt_tells_the_model_what_is_already_known() -> None:
    """So a check-in does not re-propose the same five facts every week."""
    prompt = extract_prompt("said things", "College: final year")

    assert "do not repeat" in prompt
    assert "final year" in prompt


# --------------------------------------------------------------- Rendering


def test_render_groups_by_area_and_caps_each() -> None:
    persona = _persona()
    for i in range(10):
        persona.confirm(Area.LEARNING, f"Learned thing number {i} this month")
    persona.confirm(Area.GOALS, "Wants a remote role paying in USD or AED")

    rendered = persona.render()

    assert rendered.count("Learned thing") == 6
    assert "Goals:" in rendered and "Learning:" in rendered


def test_render_markdown_is_publishable_when_empty() -> None:
    assert "Nothing confirmed yet" in _persona().render_markdown()


def test_health_reports_facts_by_area() -> None:
    persona = _persona()
    persona.confirm(Area.OPINIONS, "Most LinkedIn advice is written for people with an audience already")

    assert persona.health()["by_area"] == {"opinions": 1}
