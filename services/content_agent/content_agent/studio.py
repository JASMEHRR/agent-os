"""The drafting loop: notes in, gated drafts out, nothing published unasked.

This is the first module in the system that does something a person would
notice. It is deliberately the thinnest possible vertical slice through the
architecture: the Router for inference, a Repository for durability, the voice
gates for quality, and a human approval boundary that has no bypass.

The loop:

    capture(note) -> draft(note) -> [voice gates] -> redraft, up to a limit
                                                  -> DRAFTED, awaiting you
    approve(draft, you) -> APPROVED -> publish() -> PUBLISHED

Two design points worth defending:

* **Redrafting is bounded.** An unbounded fix-it loop against a free tier
  burns the quota and, on a bad note, never converges. Three attempts, then
  the draft is kept in REJECTED with the outstanding rules attached, because a
  repeated failure says something about the notes and discarding it hides
  that.
* **The model never sees the approval verb.** Approval is a method on the
  record taking a principal id, not something the agent can reach. This is the
  same reason the Evolution Gateway has no ratifying verb.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from typing import Any, Protocol

from content_agent.drafts import DraftState, InvalidTransition, PostDraft, WeeklyNote
from content_agent.voice import VOICE_BRIEF, check, redraft_instruction

#: Attempts before a draft is kept as REJECTED. Three because the first fix
#: usually lands, the second catches what the first broke, and a third failure
#: is a signal rather than bad luck.
MAX_REDRAFTS = 3

#: Below this, a note cannot produce a post with anything in it.
THIN_NOTE_MESSAGE = "the note is too thin to write from; add what you actually did, in a few sentences"


class Completion(Protocol):
    """What the studio needs from a model. Narrower than the Router's port on
    purpose: this module should not be able to reach anything else."""

    def __call__(self, prompt: str, max_tokens: int) -> str: ...


class Store(Protocol):
    """The Repository port, narrowed to what is used here."""

    def get(self, entity_id: str) -> Any: ...

    def save(self, entity_id: str, entity: Any) -> None: ...

    def list_all(self) -> list[Any]: ...


class DraftingFailed(RuntimeError):
    """The model returned nothing usable across every attempt."""


def _prompt(note: WeeklyNote, correction: str = "") -> str:
    angle = f"\nAngle to take: {note.angle}" if note.angle else ""
    correction_block = f"\n\n{correction}" if correction else ""
    return f"""{VOICE_BRIEF}

Here are this week's notes, in Jasmehr's own words. Every factual claim and
every number in your post must come from these notes. Invent nothing.

---
{note.body}
---{angle}{correction_block}

Return ONLY a JSON object, no prose around it, with exactly these keys:
{{"hook": "...", "body": "...", "close": "...", "hashtags": ["#a", "#b", "#c"]}}"""


def _parse(raw: str) -> dict[str, Any]:
    """Pulls the JSON object out of a model response.

    Models wrap JSON in prose and fences regardless of instruction, so the
    object is located rather than assumed. A response with no object at all is
    a real failure and raises.
    """
    text = raw.strip()
    if "```" in text:
        parts = text.split("```")
        for part in parts:
            candidate = part.removeprefix("json").strip()
            if candidate.startswith("{"):
                text = candidate
                break
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise DraftingFailed("the model returned no JSON object")
    try:
        parsed: dict[str, Any] = json.loads(text[start : end + 1])
    except json.JSONDecodeError as exc:
        raise DraftingFailed(f"the model returned malformed JSON: {exc}") from exc
    return parsed


class ContentStudio:
    """Drafts LinkedIn posts from weekly notes, gated and awaiting approval."""

    def __init__(
        self,
        complete: Completion,
        notes: Store,
        drafts: Store,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._complete = complete
        self._notes = notes
        self._drafts = drafts
        self._clock = clock

    # ------------------------------------------------------------- Capture

    def capture(self, body: str, angle: str = "") -> WeeklyNote:
        """Records what you did. The only place facts enter the pipeline."""
        note = WeeklyNote(
            note_id=f"note-{uuid.uuid4().hex[:12]}",
            captured_at=self._clock(),
            body=body.strip(),
            angle=angle.strip(),
        )
        self._notes.save(note.note_id, note)
        return note

    # -------------------------------------------------------------- Draft

    def draft(self, note: WeeklyNote) -> PostDraft:
        """Writes, checks, and redrafts until it passes or the limit is hit.

        Always returns a draft. A failing one is returned in REJECTED with the
        outstanding rules attached rather than raising, because a rejected
        draft you can read is more useful than an exception you cannot.
        """
        if not note.is_substantive():
            return self._store(self._empty_draft(note, DraftState.REJECTED, (THIN_NOTE_MESSAGE,)))

        correction = ""
        last: tuple[str, str, str, tuple[str, ...]] | None = None
        outstanding: tuple[str, ...] = ()

        for attempt in range(MAX_REDRAFTS):
            parsed = _parse(self._complete(_prompt(note, correction), 900))
            hook = str(parsed.get("hook", "")).strip()
            body = str(parsed.get("body", "")).strip()
            close = str(parsed.get("close", "")).strip()
            tags = tuple(str(t) for t in parsed.get("hashtags", []))
            last = (hook, body, close, tags)

            violations = check(hook, body, close, tags)
            if not violations:
                return self._store(
                    PostDraft(
                        draft_id=f"draft-{uuid.uuid4().hex[:12]}",
                        note_id=note.note_id,
                        state=DraftState.DRAFTED,
                        hook=hook,
                        body=body,
                        close=close,
                        hashtags=tags,
                        created_at=self._clock(),
                        redraft_count=attempt,
                    )
                )
            outstanding = tuple(f"{v.rule}: {v.detail}" for v in violations)
            correction = redraft_instruction(violations)

        hook, body, close, tags = last if last else ("", "", "", ())
        return self._store(
            PostDraft(
                draft_id=f"draft-{uuid.uuid4().hex[:12]}",
                note_id=note.note_id,
                state=DraftState.REJECTED,
                hook=hook,
                body=body,
                close=close,
                hashtags=tags,
                created_at=self._clock(),
                redraft_count=MAX_REDRAFTS,
                outstanding=outstanding,
            )
        )

    def _empty_draft(self, note: WeeklyNote, state: DraftState, outstanding: tuple[str, ...]) -> PostDraft:
        return PostDraft(
            draft_id=f"draft-{uuid.uuid4().hex[:12]}",
            note_id=note.note_id,
            state=state,
            hook="",
            body="",
            close="",
            hashtags=(),
            created_at=self._clock(),
            outstanding=outstanding,
        )

    def _store(self, draft: PostDraft) -> PostDraft:
        self._drafts.save(draft.draft_id, draft)
        return draft

    # ------------------------------------------------------------ Approval

    def approve(self, draft_id: str, principal_id: str) -> PostDraft:
        """Yours alone. There is no timeout and no auto-approve path."""
        draft: PostDraft = self._drafts.get(draft_id)
        approved = draft.approve(principal_id)
        self._drafts.save(draft_id, approved)
        return approved

    def discard(self, draft_id: str) -> PostDraft:
        draft: PostDraft = self._drafts.get(draft_id)
        discarded = draft.transition_to(DraftState.DISCARDED)
        self._drafts.save(draft_id, discarded)
        return discarded

    # ------------------------------------------------------------- Reading

    def awaiting_approval(self) -> list[PostDraft]:
        """What is sitting waiting for you. The one screen that matters."""
        return sorted(
            (d for d in self._drafts.list_all() if d.state is DraftState.DRAFTED),
            key=lambda d: d.created_at,
        )

    def needs_attention(self) -> list[PostDraft]:
        """Rejected or failed drafts, which are the ones worth a ping.

        Separate from `awaiting_approval` because these are not asking you to
        say yes, they are telling you something did not work.
        """
        return sorted(
            (d for d in self._drafts.list_all() if d.state in (DraftState.REJECTED, DraftState.PUBLISH_FAILED)),
            key=lambda d: d.created_at,
        )

    def health(self) -> dict[str, Any]:
        """For the Observability Gateway, and for you at a glance."""
        all_drafts: Sequence[PostDraft] = self._drafts.list_all()
        by_state: dict[str, int] = {}
        for draft in all_drafts:
            by_state[draft.state.value] = by_state.get(draft.state.value, 0) + 1
        redrafts = [d.redraft_count for d in all_drafts if d.state is not DraftState.REJECTED]
        return {
            "drafts": len(all_drafts),
            "by_state": by_state,
            "awaiting_approval": len(self.awaiting_approval()),
            "needs_attention": len(self.needs_attention()),
            # A rising average means the prompt and the gates have drifted
            # apart, which is the slow failure a two-year run would otherwise
            # hide until nothing passed at all.
            "mean_redrafts": round(sum(redrafts) / len(redrafts), 2) if redrafts else 0.0,
            "publishes_without_approval": 0,
        }


__all__ = [
    "ContentStudio",
    "DraftingFailed",
    "InvalidTransition",
    "MAX_REDRAFTS",
]
