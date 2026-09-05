"""Three channels, one set of facts, three sets of gates.

The property under test throughout: each channel's rules are enforced on that
channel and not on the others. A single shared gate set would have to be the
loosest of the three, which leaves the strictest channel ungated, and that is
the failure this file exists to prevent.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

from content_agent import ContentStudio
from content_agent.drafts import DraftState
from content_agent.formats import (
    SPECS,
    Channel,
    check_devto,
    check_newsletter,
    universal_violations,
)
from content_agent.studio import TOKEN_BUDGET
from content_agent.voice import check
from persistence import InMemoryRepository

NOTE = (
    "This week I wired Groq behind the model router. It took 3 attempts because the free "
    "tier rate limits at 429 rather than billing, so I built a cooldown that degrades to a "
    "smaller model. The suite is at 1815 passing tests."
)

PAYLOADS: dict[Channel, dict[str, object]] = {
    Channel.LINKEDIN: {
        "hook": "I spent 3 attempts learning a free API tier fails differently than a paid one.",
        "body": "A paid tier bills you.\n\nA free tier stops answering.",
        "close": "What small failure taught you most this week?",
        "hashtags": ["#agentarchitecture", "#buildinpublic", "#pythontesting"],
    },
    Channel.NEWSLETTER: {
        "subject": "The 429 that taught me to stop retrying",
        "body": (
            "Groq's free tier does not bill you when you go over. It stops answering.\n\n"
            "That took 3 attempts to work out, because a 429 looks like a transient error "
            "and the obvious response to a transient error is a retry.\n\n"
            "The fix was a cooldown that degrades to a smaller model instead."
        ),
        "close": "Have you hit a failure that looked transient and was not? Reply and tell me.",
    },
    Channel.DEVTO: {
        "title": "A free LLM tier fails differently, and retrying makes it worse",
        "body": (
            "## The problem\n\nGroq returns 429 when the per-minute window is spent.\n\n"
            "## What I tried\n\n3 attempts, each retrying sooner.\n\n"
            "## What worked\n\nA cooldown, and degrading to a smaller model."
        ),
        "tags": ["python", "llm", "apidesign", "testing"],
    },
}


def _studio(channel: Channel, overrides: dict[str, object] | None = None) -> ContentStudio:
    payload: dict[str, object] = dict(PAYLOADS[channel])
    payload.update(overrides or {})
    return ContentStudio(
        complete=lambda prompt, max_tokens: json.dumps(payload),
        notes=InMemoryRepository(),
        drafts=InMemoryRepository(),
        clock=lambda: datetime(2026, 8, 25, tzinfo=UTC),
    )


# ------------------------------------------------------------- Every channel


def test_each_channel_drafts_and_passes_its_own_gates() -> None:
    """The gates have to be satisfiable on every channel or nothing converges."""
    for channel in Channel:
        studio = _studio(channel)
        draft = studio.draft(studio.capture(NOTE), channel)
        assert draft.state is DraftState.DRAFTED, f"{channel.value}: {draft.outstanding}"
        assert draft.channel is channel


def test_one_note_produces_a_draft_for_every_channel() -> None:
    """The leverage: writing the note is the only unautomatable part."""
    studio = _studio(Channel.LINKEDIN)
    # A single canned payload cannot satisfy all three, so the other two land
    # in REJECTED. What matters here is that all three were attempted and none
    # went missing.
    produced = studio.draft_everywhere(studio.capture(NOTE))

    assert {d.channel for d in produced} == set(Channel)
    assert len(produced) == 3


def test_a_failing_channel_does_not_stop_the_others() -> None:
    """Losing a good LinkedIn post because Dev.to would not converge is a bad
    trade. Failures come back as REJECTED drafts rather than exceptions."""
    studio = ContentStudio(
        complete=lambda prompt, max_tokens: json.dumps(PAYLOADS[Channel.LINKEDIN]),
        notes=InMemoryRepository(),
        drafts=InMemoryRepository(),
    )
    produced = studio.draft_everywhere(studio.capture(NOTE))

    linkedin = next(d for d in produced if d.channel is Channel.LINKEDIN)
    assert linkedin.state is DraftState.DRAFTED
    assert len(produced) == 3


def test_every_channel_has_a_spec_and_a_token_budget() -> None:
    """A channel added without a budget would silently truncate long output,
    then burn two redrafts fixing something the model did not do wrong."""
    for channel in Channel:
        assert channel in SPECS
        assert channel in TOKEN_BUDGET
        assert SPECS[channel].fields, f"{channel.value} declares no fields"


def test_the_token_budget_rises_with_the_target_length() -> None:
    assert TOKEN_BUDGET[Channel.LINKEDIN] < TOKEN_BUDGET[Channel.NEWSLETTER] < TOKEN_BUDGET[Channel.DEVTO]


# ------------------------------------------------------------- Shared rules


def test_the_universal_rules_apply_to_every_channel() -> None:
    """A new channel inherits these by default rather than by remembering to."""
    for text in ("an em dash — here with 1 number", "humbled to announce, 1 thing"):
        assert universal_violations(text), f"{text!r} passed the universal gates"


def test_a_missing_number_fails_on_every_channel() -> None:
    assert any(v.rule == "no-concrete-detail" for v in universal_violations("no digits at all here"))


# ---------------------------------------------------------------- Newsletter


def test_a_long_subject_is_rejected() -> None:
    """Mail clients truncate, and a truncated subject is a wasted one."""
    violations = check_newsletter("x" * 90, "Body with 1 number.", "Reply and tell me.")

    assert any(v.rule == "subject-length" for v in violations)


def test_throat_clearing_is_rejected() -> None:
    """The tell of a model reaching for email conventions it has seen a
    million times, which reads as a template rather than a person."""
    violations = check_newsletter("A real subject", "Hope you are well. I did 1 thing.", "Reply?")

    assert any(v.rule == "throat-clearing" for v in violations)


def test_hashtags_are_rejected_in_a_newsletter() -> None:
    violations = check_newsletter("Subject", "Body with 1 number.", "Reply #thoughts")

    assert any(v.rule == "hashtag-in-email" for v in violations)


def test_a_newsletter_renders_with_its_subject_visible() -> None:
    """Reviewing a newsletter without its subject means reviewing the half
    that does not decide whether it gets opened."""
    studio = _studio(Channel.NEWSLETTER)
    draft = studio.draft(studio.capture(NOTE), Channel.NEWSLETTER)

    assert draft.full_text().startswith("Subject: ")


# -------------------------------------------------------------------- Dev.to


def test_devto_requires_exactly_four_lowercase_tags() -> None:
    assert any(v.rule == "tag-count" for v in check_devto("Title", "## H\n1 thing", ("a", "b")))
    assert any(v.rule == "tag-format" for v in check_devto("Title", "## H\n1 thing", ("Python", "b", "c", "d")))


def test_devto_requires_headings() -> None:
    """Dev.to readers scan before they read, and a wall of text is skipped."""
    violations = check_devto("Title", "One long paragraph with 1 number and no structure.", ("a", "b", "c", "d"))

    assert any(v.rule == "no-headings" for v in violations)


def test_an_unclosed_code_fence_is_caught() -> None:
    """Invisible in a draft, obvious to every reader: an unclosed fence
    swallows the rest of the article into a code block on publish."""
    violations = check_devto(
        "Title",
        "## Heading\n\n```python\nx = 1\n\n## Next heading",
        ("python", "llm", "testing", "apidesign"),
    )

    assert any(v.rule == "unclosed-code-fence" for v in violations)


def test_a_balanced_code_fence_passes() -> None:
    violations = check_devto(
        "Title",
        "## Heading\n\n```python\nx = 1\n```\n\n## Next",
        ("python", "llm", "testing", "apidesign"),
    )

    assert not any(v.rule == "unclosed-code-fence" for v in violations)


# --------------------------------------------------- Rules stay on their own


def test_the_linkedin_hook_rule_does_not_apply_to_a_newsletter() -> None:
    """The separation that justifies three gate sets.

    A 140-character limit is right for a LinkedIn hook and wrong for a
    newsletter body, where the room is the point.
    """
    long_body = "A newsletter paragraph that runs well past 140 characters, " * 4 + "with 1 number."

    assert not check_newsletter("Short subject", long_body, "Reply?")


def test_the_newsletter_hashtag_ban_does_not_apply_to_linkedin() -> None:
    assert not check(
        "A hook with 1 real number in it.",
        "Body.",
        "Close?",
        ("#agentarchitecture", "#buildinpublic", "#pythontesting"),
    )


def test_a_draft_stored_before_channel_existed_still_loads() -> None:
    """Found by running the demo server against yesterday's database.

    The codec correctly refused a row missing a required field, which took the
    whole page down. The default is right here specifically because every
    draft written before this field was a LinkedIn draft: it records a fact
    that was implicit, rather than inventing one that never existed.
    """
    from content_agent.drafts import PostDraft
    from persistence import decode_dataclass

    row = {
        "draft_id": "d1",
        "note_id": "n1",
        "state": "drafted",
        "hook": "Hook.",
        "body": "Body.",
        "close": "Close?",
        "hashtags": ["#a"],
        "created_at": "\x00iso:2026-08-25T00:00:00+00:00",
    }

    assert decode_dataclass(PostDraft, row).channel is Channel.LINKEDIN


# ------------------------------------------------- AI vocabulary as a gate


def test_the_ai_vocabulary_is_rejected_not_merely_discouraged() -> None:
    """The humanizer skill lists these as prose. Prose in a prompt is advice a
    model drifts past on a bad generation, which is the whole reason these
    rules live in code."""
    from content_agent.voice import check

    for word in ("delve", "leverage", "seamless", "paradigm", "deep dive"):
        violations = check(
            "A hook with 1 real number in it.",
            f"This is where I {word} into the thing.",
            "A close.",
            ("#a", "#b", "#c"),
        )
        assert any(v.rule == "cliche" for v in violations), f"{word!r} should be caught"


def test_words_he_actually_uses_are_not_caught() -> None:
    """A gate that fires on a legitimate sentence teaches you to ignore it.
    "robust" is in his own commit log; "navigate" and "journey" are ordinary
    in marketing writing."""
    from content_agent.voice import check

    violations = check(
        "I made the flaky test robust, which took 2 attempts.",
        "Buyers navigate to the shop. The customer journey starts at the root URL.",
        "That is the whole change.",
        ("#a", "#b", "#c"),
    )

    assert [v.rule for v in violations if v.rule == "cliche"] == []
