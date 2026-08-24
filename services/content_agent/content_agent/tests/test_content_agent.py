"""The content pipeline, with the approval boundary tested hardest.

This module will run unattended for long stretches. The tests that matter are
not the ones proving it drafts well, they are the ones proving it cannot
publish without being told to, and that it fails visibly rather than quietly
when the notes are thin or the model drifts.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from content_agent.drafts import (
    TRANSITIONS,
    DraftState,
    InvalidTransition,
    NotApproved,
    PostDraft,
    WeeklyNote,
)
from content_agent.studio import MAX_REDRAFTS, ContentStudio, DraftingFailed
from content_agent.voice import check, redraft_instruction
from persistence import InMemoryRepository

GOOD_NOTE = (
    "This week I finished wiring Groq behind the model router in my agent OS project. "
    "Took 3 attempts because the free tier rate limits at 429 and I had to build a "
    "cooldown so it degrades instead of failing. Also hit 1783 passing tests."
)


def _payload(**overrides: object) -> str:
    base: dict[str, object] = {
        "hook": "I spent 3 attempts learning that a free API tier fails differently than a paid one.",
        "body": "Rate limits do not bill you, they just stop answering.\n\nSo I built a cooldown.",
        "close": "What is the smallest failure that taught you the most this week?",
        "hashtags": ["#agentarchitecture", "#buildinpublic", "#pythontesting"],
    }
    base.update(overrides)
    return json.dumps(base)


def _studio(responses: list[str]) -> ContentStudio:
    """A studio whose model returns the given responses in order."""
    calls = iter(responses)

    def complete(prompt: str, max_tokens: int) -> str:
        return next(calls)

    return ContentStudio(
        complete=complete,
        notes=InMemoryRepository(),
        drafts=InMemoryRepository(),
        clock=lambda: datetime(2026, 8, 25, tzinfo=UTC),
    )


# ------------------------------------------------- The boundary that matters


def test_a_drafted_post_cannot_be_published_without_approval() -> None:
    """The single most important property in this module.

    Everything else here is quality. This is the one that stops an unattended
    process from posting to a real profile on its own.
    """
    studio = _studio([_payload()])
    draft = studio.draft(studio.capture(GOOD_NOTE))

    assert draft.state is DraftState.DRAFTED
    with pytest.raises(NotApproved):
        draft.mark_published("https://example.invalid/post")


def test_published_is_unreachable_from_every_state_except_approved() -> None:
    """Asserted against the transition table itself, not by trying paths.

    A test that walked a few routes would pass while a newly added transition
    opened a fifth one nobody checked.
    """
    reaches_published = {state for state, allowed in TRANSITIONS.items() if DraftState.PUBLISHED in allowed}
    assert reaches_published == {DraftState.APPROVED, DraftState.PUBLISH_FAILED}, (
        "something now reaches PUBLISHED without passing through human approval"
    )


def test_approval_requires_a_named_principal() -> None:
    """An anonymous approval is indistinguishable from no approval."""
    studio = _studio([_payload()])
    draft = studio.draft(studio.capture(GOOD_NOTE))

    with pytest.raises(NotApproved, match="named principal"):
        draft.approve("   ")

    approved = draft.approve("jasmehr")
    assert approved.approved_by == "jasmehr"
    assert approved.approved_at is not None


def test_the_studio_exposes_no_verb_that_publishes() -> None:
    """Structural, like the Evolution Gateway's absent ratify.

    Publishing lives outside this class entirely. A studio that could publish
    would eventually publish, no matter what the state machine said.
    """
    forbidden = {"publish", "post", "send", "share", "submit"}
    present = {name for name in dir(ContentStudio) if not name.startswith("_")}
    assert not (forbidden & present), f"the studio gained a publishing verb: {forbidden & present}"


def test_a_published_draft_is_terminal() -> None:
    studio = _studio([_payload()])
    draft = studio.draft(studio.capture(GOOD_NOTE))
    published = draft.approve("jasmehr").mark_published("https://example.invalid/1")

    with pytest.raises(InvalidTransition):
        published.transition_to(DraftState.DRAFTED)


# ------------------------------------------------------------- Voice gates


def test_an_em_dash_is_rejected_and_the_redraft_says_so() -> None:
    """The standing rule across every document in this account.

    A model asked nicely will drift on this over a two-year run, so it is
    checked rather than requested.
    """
    violations = check(
        "A hook with an em dash — right here.",
        "Body.",
        "Close?",
        ("#a", "#b", "#c"),
    )

    assert any(v.rule == "forbidden-punctuation" for v in violations)
    assert "em dash" in redraft_instruction(violations)


def test_a_hook_that_would_be_truncated_is_rejected() -> None:
    """The highest-leverage rule in the skill: the hook has to survive the cut."""
    violations = check("x" * 200, "Body with 1 number.", "Close?", ("#a", "#b", "#c"))

    assert any(v.rule == "hook-truncation" for v in violations)


def test_a_post_with_no_concrete_detail_is_rejected() -> None:
    """A post with no number is the generic-motivational failure the skill
    names first, and it is the failure an unattended run drifts toward."""
    violations = check(
        "Some thoughts on building things.",
        "It is important to keep going and stay consistent.",
        "What do you think?",
        ("#a", "#b", "#c"),
    )

    assert any(v.rule == "no-concrete-detail" for v in violations)


def test_cliches_are_caught() -> None:
    violations = check(
        "Humbled to announce something after 3 months.",
        "Body.",
        "Close.",
        ("#a", "#b", "#c"),
    )

    assert any(v.rule == "cliche" for v in violations)


def test_broad_hashtags_are_rejected_in_favour_of_niche_ones() -> None:
    violations = check("Hook with 1 detail.", "Body.", "Close?", ("#motivation", "#ai", "#success"))

    assert any(v.rule == "broad-hashtag" for v in violations)


def test_a_clean_post_passes_every_gate() -> None:
    """The gates have to be satisfiable, or the loop never converges."""
    assert (
        check(
            "I spent 3 attempts learning that a free API tier fails differently.",
            "Rate limits do not bill you. They stop answering.",
            "What small failure taught you most this week?",
            ("#agentarchitecture", "#buildinpublic", "#pythontesting"),
        )
        == ()
    )


# ------------------------------------------------------------ The draft loop


def test_a_failing_draft_is_redrafted_with_the_specific_rules_attached() -> None:
    """The correction is handed back, so the second attempt can act on it."""
    seen: list[str] = []

    def complete(prompt: str, max_tokens: int) -> str:
        seen.append(prompt)
        return _payload(hook="Bad hook with an em dash — here.") if len(seen) == 1 else _payload()

    studio = ContentStudio(complete, InMemoryRepository(), InMemoryRepository())
    draft = studio.draft(studio.capture(GOOD_NOTE))

    assert draft.state is DraftState.DRAFTED
    assert draft.redraft_count == 1
    assert "em dash" in seen[1], "the second prompt must name what was wrong with the first"


def test_redrafting_is_bounded_and_the_failure_is_kept() -> None:
    """An unbounded loop against a free tier burns the quota and, on a bad
    note, never converges. The rejected draft is kept because a repeated
    failure is information."""
    studio = _studio([_payload(hook="em dash — here")] * MAX_REDRAFTS)
    draft = studio.draft(studio.capture(GOOD_NOTE))

    assert draft.state is DraftState.REJECTED
    assert draft.redraft_count == MAX_REDRAFTS
    assert any("forbidden-punctuation" in rule for rule in draft.outstanding)
    assert studio.needs_attention() == [draft]


def test_a_thin_note_is_refused_rather_than_padded_into_filler() -> None:
    """The honest outcome. Generating a post from nothing produces invented
    achievements, which is the worst possible failure on a real profile."""
    studio = _studio([])
    draft = studio.draft(studio.capture("did some stuff"))

    assert draft.state is DraftState.REJECTED
    assert "too thin" in draft.outstanding[0]


def test_the_model_returning_prose_around_json_is_handled() -> None:
    """Models wrap JSON in fences and commentary regardless of instruction."""
    studio = _studio([f"Sure, here you go!\n```json\n{_payload()}\n```\nHope that helps."])

    assert studio.draft(studio.capture(GOOD_NOTE)).state is DraftState.DRAFTED


def test_the_model_returning_no_json_at_all_raises() -> None:
    studio = _studio(["I cannot help with that."])

    with pytest.raises(DraftingFailed):
        studio.draft(studio.capture(GOOD_NOTE))


# ---------------------------------------------------------------- Surfaces


def test_awaiting_approval_shows_only_what_is_asking_for_a_decision() -> None:
    studio = _studio([_payload(), _payload()])
    first = studio.draft(studio.capture(GOOD_NOTE))
    studio.draft(studio.capture(GOOD_NOTE))
    studio.approve(first.draft_id, "jasmehr")

    assert [d.draft_id for d in studio.awaiting_approval()] != [first.draft_id]
    assert len(studio.awaiting_approval()) == 1


def test_health_reports_zero_unapproved_publishes_and_tracks_redraft_drift() -> None:
    """`mean_redrafts` rising across weeks is how the slow failure shows up:
    the prompt and the gates drifting apart until nothing passes."""
    studio = _studio([_payload()])
    studio.draft(studio.capture(GOOD_NOTE))

    health = studio.health()
    assert health["publishes_without_approval"] == 0
    assert health["awaiting_approval"] == 1
    assert health["mean_redrafts"] == 0.0


def test_full_text_assembles_what_would_actually_be_posted() -> None:
    draft = PostDraft(
        draft_id="d1",
        note_id="n1",
        state=DraftState.DRAFTED,
        hook="Hook.",
        body="Body.",
        close="Close?",
        hashtags=("agentarchitecture", "#buildinpublic"),
        created_at=datetime(2026, 8, 25, tzinfo=UTC),
    )

    text = draft.full_text()
    assert text.startswith("Hook.")
    assert "#agentarchitecture #buildinpublic" in text, "bare tags must be normalised"


def test_a_note_records_when_it_was_captured() -> None:
    """Every factual claim traces to a note, and a note without a time cannot
    be matched to the week it describes."""
    studio = _studio([])
    note = studio.capture(GOOD_NOTE)

    assert isinstance(note, WeeklyNote)
    assert note.captured_at.tzinfo is not None
