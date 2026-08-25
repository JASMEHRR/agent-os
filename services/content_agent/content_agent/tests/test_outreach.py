"""Outreach notes, gated harder than posts.

A generic post is a wasted post. A generic outreach note is worse than sending
nothing: it tells the reader you did not look at them, in a message whose
entire claim is that you did. Every gate here exists for that.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

from content_agent import ContentStudio
from content_agent.outreach import (
    NOTE_MAX_CHARS,
    OutreachChannel,
    check_note,
    prospect_from,
)
from persistence import InMemoryRepository

PERSON = prospect_from(
    "Priya Sharma",
    "Engineering lead, works on inference cost",
    "She gave a talk about moving small requests to a locally hosted model to cut cost.",
)

GOOD = (
    "Priya, your talk on moving small requests to a locally hosted model is the thing I keep "
    "coming back to. I built a router that degrades the same way. Where did you draw the line?"
)


def _studio(body: str) -> ContentStudio:
    return ContentStudio(
        complete=lambda prompt, max_tokens: json.dumps({"body": body}),
        notes=InMemoryRepository(),
        drafts=InMemoryRepository(),
        clock=lambda: datetime(2026, 8, 25, tzinfo=UTC),
    )


# --------------------------------------------------------------- No sending


def test_the_studio_exposes_no_verb_that_sends() -> None:
    """The boundary that matters most here, and it is about the platform
    rather than about caution: LinkedIn exposes no API for invitations, so
    automating the send means driving a browser while evading bot detection,
    which reliably ends in the restricted account the outreach exists to
    avoid."""
    forbidden = {"send", "send_note", "connect", "invite", "message", "dm"}
    present = {name for name in dir(ContentStudio) if not name.startswith("_")}

    assert not (forbidden & present), f"the studio gained a sending verb: {forbidden & present}"


def test_an_outreach_draft_has_no_sent_state() -> None:
    """Nothing records a send, because nothing sends."""
    studio = _studio(GOOD)
    draft = studio.draft_note(studio.add_prospect(PERSON))

    assert not hasattr(draft, "sent")
    assert not hasattr(draft, "sent_at")


# ------------------------------------------------------------------- Gates


def test_a_vague_reason_is_refused_before_a_model_call() -> None:
    """ "works in AI" produces "I see you work in AI", which is the exact note
    this module exists to not send."""
    studio = _studio(GOOD)
    vague = prospect_from("Priya Sharma", "Engineer", "works in AI")

    draft = studio.draft_note(studio.add_prospect(vague))

    assert draft.body == ""
    assert "too vague" in draft.outstanding[0]


def test_a_note_that_never_names_them_is_rejected() -> None:
    """A note without their name is a broadcast."""
    violations = check_note(
        PERSON,
        "Your talk on moving small requests to a locally hosted model was great. "
        "I built a router that degrades the same way. Where did you draw the line?",
        OutreachChannel.LINKEDIN_NOTE,
    )

    assert any(v.rule == "no-name" for v in violations)


def test_template_language_is_rejected() -> None:
    """These are the exact strings that make a recipient stop reading."""
    violations = check_note(
        PERSON,
        "Priya, I came across your profile and would love to connect about your "
        "locally hosted model talk. Keen to pick your brain sometime soon.",
        OutreachChannel.LINKEDIN_NOTE,
    )

    assert any(v.rule == "template-language" for v in violations)


def test_a_note_that_ignores_the_stated_reason_is_rejected() -> None:
    """The reason is the whole personalisation budget. If none of it survived
    into the note, the note is not about them."""
    violations = check_note(
        PERSON,
        "Priya, I really admire what you are building and thought it would be good "
        "to be in touch. Always glad to know more people doing serious work.",
        OutreachChannel.LINKEDIN_NOTE,
    )

    assert any(v.rule == "generic" for v in violations)


def test_a_note_over_the_linkedin_limit_is_rejected() -> None:
    violations = check_note(PERSON, "Priya, " + "locally hosted model. " * 40, OutreachChannel.LINKEDIN_NOTE)

    assert any(v.rule == "note-length" for v in violations)
    assert len("Priya, " + "locally hosted model. " * 40) > NOTE_MAX_CHARS


def test_a_note_too_short_to_be_personal_is_rejected() -> None:
    violations = check_note(PERSON, "Priya, locally hosted model. Nice.", OutreachChannel.LINKEDIN_NOTE)

    assert any(v.rule == "note-too-short" for v in violations)


def test_an_email_with_no_question_is_rejected() -> None:
    """A note with no ask gets no reply."""
    violations = check_note(
        PERSON,
        "Priya, your talk on the locally hosted model changed how I think about tiering. "
        "I built a router that degrades the same way and it held up well.",
        OutreachChannel.EMAIL,
    )

    assert any(v.rule == "no-ask" for v in violations)


def test_a_good_note_passes() -> None:
    """The gates have to be satisfiable or the loop never converges."""
    assert check_note(PERSON, GOOD, OutreachChannel.LINKEDIN_NOTE) == ()


# ------------------------------------------------------------------- Flow


def test_a_drafted_note_can_be_approved_by_a_named_person() -> None:
    studio = _studio(GOOD)
    draft = studio.draft_note(studio.add_prospect(PERSON))

    approved = studio.approve_note(draft.draft_id, "jasmehr")

    assert approved.approved is True
    assert approved.approved_by == "jasmehr"


def test_prospects_and_notes_are_listed_for_the_interface() -> None:
    studio = _studio(GOOD)
    studio.draft_note(studio.add_prospect(PERSON))

    assert len(studio.prospects()) == 1
    assert len(studio.outreach_drafts()) == 1
