"""Tests for whose studio this is.

The failure this prevents is not a crash. It is a friend opening the app,
pressing "Write my drafts", and getting a post written as somebody else - in
their voice, about their week. Nothing errors; the output is just quietly
about the wrong person.
"""

from __future__ import annotations

from content_agent.owner import ANONYMOUS, Owner
from content_agent.persona import EXTRACT_BRIEF, extract_prompt
from content_agent.voice import VOICE_BRIEF

JASMEHR = Owner(name="Jasmehr", about="21, a marketer and builder")


def test_nobody_is_named_until_somebody_says_who_they_are() -> None:
    """Inventing a name produces posts signed by a stranger."""
    assert Owner().who == ANONYMOUS
    assert not Owner().named


def test_a_name_and_a_description_read_as_one_phrase() -> None:
    assert JASMEHR.who == "Jasmehr, 21, a marketer and builder"


def test_a_name_on_its_own_is_enough() -> None:
    assert Owner(name="Priya").who == "Priya"


def test_a_description_without_a_name_still_beats_anonymous() -> None:
    assert Owner(about="a final-year law student").who == "someone who is a final-year law student"


def test_whitespace_and_a_trailing_comma_do_not_reach_the_prompt() -> None:
    assert Owner(name="  Priya  ", about=" 22, a designer, ").who == "Priya, 22, a designer"


# ================================================================ the briefs


def test_no_brief_still_names_the_person_it_was_written_for() -> None:
    """The whole point: the briefs must carry a slot, not a name."""
    for brief in (VOICE_BRIEF, EXTRACT_BRIEF):
        assert "Jasmehr" not in brief
        assert "{who}" in brief


def test_the_configured_name_actually_reaches_the_voice_brief() -> None:
    assert "Jasmehr, 21, a marketer and builder" in JASMEHR.fill(VOICE_BRIEF)


def test_an_unconfigured_studio_says_the_person_using_this() -> None:
    assert ANONYMOUS in Owner().fill(VOICE_BRIEF)


def test_filling_a_brief_containing_json_braces_does_not_raise() -> None:
    """`str.format` would raise on the `{"area": ...}` example in the brief."""
    filled = JASMEHR.fill(EXTRACT_BRIEF)
    assert '{"area"' in filled
    assert "Jasmehr" in filled


def test_the_persona_prompt_carries_the_name_through() -> None:
    prompt = extract_prompt("I shipped the billboard this week.", "", JASMEHR)
    assert "Jasmehr" in prompt
    assert "billboard" in prompt


def test_the_persona_prompt_without_an_owner_names_nobody() -> None:
    assert "Jasmehr" not in extract_prompt("I shipped something.", "")


def test_the_briefs_never_assume_a_gender() -> None:
    """A pronoun in a brief is a guess about whoever ends up running it."""
    for brief in (VOICE_BRIEF, EXTRACT_BRIEF):
        words = brief.lower().replace(".", " ").replace(",", " ").split()
        assert "he" not in words
        assert "his" not in words
        assert "him" not in words
        assert "she" not in words
        assert "her" not in words
