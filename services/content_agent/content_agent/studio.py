"""The drafting loop: notes in, gated drafts out, nothing published unasked.

The first module in the system that does something a person would notice, and
a thin vertical slice through the architecture: the Router for inference, a
Repository for durability, format gates for quality, and a human approval
boundary that has no bypass.

    capture(note) -> draft(note, channel) -> [gates] -> redraft, up to a limit
                                                     -> DRAFTED, awaiting you
    approve(draft, you) -> APPROVED

One note produces a LinkedIn post, a newsletter issue and a Dev.to article
from the same facts. That is where the leverage is: writing the note is the
only part that cannot be automated, because only you know what happened.

Two design points worth defending:

* **Redrafting is bounded.** An unbounded fix-it loop against a free tier
  burns the quota and, on a bad note, never converges. Three attempts, then
  the draft is kept in REJECTED with the outstanding rules attached, because a
  repeated failure says something about the notes and discarding it hides it.
* **The model never sees the approval verb.** Approval is a method on the
  record taking a principal id, not something the agent can reach. Same reason
  the Evolution Gateway has no ratifying verb.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from typing import Any, Protocol

from content_agent.drafts import DraftState, PostDraft, WeeklyNote
from content_agent.formats import (
    SPECS,
    Channel,
    FormatSpec,
    check_devto,
    check_newsletter,
)
from content_agent.outreach import (
    BRIEF as OUTREACH_BRIEF,
)
from content_agent.outreach import (
    OutreachChannel,
    OutreachDraft,
    Prospect,
    check_note,
)
from content_agent.persona import Persona, extract_prompt, parse_proposed
from content_agent.samples import VoiceLibrary, render_examples
from content_agent.voice import VOICE_BRIEF, VoiceViolation, check, redraft_instruction

#: Attempts before a draft is kept as REJECTED. Three because the first fix
#: usually lands, the second catches what the first broke, and a third failure
#: is a signal rather than bad luck.
MAX_REDRAFTS = 3

#: Below this, a note cannot produce anything with substance in it.
THIN_NOTE_MESSAGE = "the note is too thin to write from; add what you actually did, in a few sentences"

#: Roughly four characters per token, plus room for the model to be verbose.
#: A newsletter cut off mid-sentence fails the gates and burns two more
#: attempts fixing something that was never the model's fault.
TOKEN_BUDGET: dict[Channel, int] = {
    Channel.LINKEDIN: 900,
    Channel.NEWSLETTER: 1400,
    Channel.DEVTO: 2400,
}


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
    """The model returned nothing usable."""


def _prompt(
    note: WeeklyNote,
    spec: FormatSpec,
    correction: str = "",
    examples: str = "",
    persona: str = "",
) -> str:
    angle = f"\nAngle to take: {note.angle}" if note.angle else ""
    correction_block = f"\n\n{correction}" if correction else ""
    # Order matters. Rules, then who he is, then examples of how he writes,
    # then the notes. The persona is context the post may draw on; the notes
    # are the facts it must not stray from, so they come last and closest.
    persona_block = f"\n\n{persona}" if persona else ""
    examples_block = f"\n\n{examples}" if examples else ""
    keys = ", ".join(f'"{field}": "..."' for field in spec.fields)
    return f"""{VOICE_BRIEF}

{spec.brief}{persona_block}{examples_block}

Aim for roughly {spec.target_words} words.

Here are this week's notes, in Jasmehr's own words. Every factual claim and
every number must come from these notes. Invent nothing.

Write from the sharpest thing in the notes rather than about all of it. One
story, the most specific one, told with the detail that is already there: the
thing that broke, the number, the decision that was argued over. Where a note
has said something well, keep his words. A summary of his sentence is always
flatter than his sentence, and a post that surveys the week says nothing about
any of it.

---
{note.body}
---{angle}{correction_block}

Return ONLY a JSON object, no prose around it, with exactly these keys:
{{{keys}}}"""


def _note_prompt(prospect: Prospect, channel: OutreachChannel, correction: str = "") -> str:
    correction_block = ("\n\n" + correction) if correction else ""
    fields = '{"subject": "...", "body": "..."}' if channel is OutreachChannel.EMAIL else '{"body": "..."}'
    limit = (
        "Keep the body under 300 characters. It is a LinkedIn invitation note."
        if channel is OutreachChannel.LINKEDIN_NOTE
        else "Keep it to four short sentences. It is a cold email."
    )
    return f"""{OUTREACH_BRIEF}

{limit}

Person: {prospect.name}
They are: {prospect.headline}
Why them, specifically: {prospect.reason}
{f"Found via: {prospect.source}" if prospect.source else ""}{correction_block}

Return ONLY a JSON object, no prose around it: {fields}"""


def _parse(raw: str) -> dict[str, Any]:
    """Pulls the JSON object out of a model response.

    Models wrap JSON in prose and fences regardless of instruction, so the
    object is located rather than assumed. A response with no object at all is
    a real failure and raises.
    """
    text = raw.strip()
    if "```" in text:
        for part in text.split("```"):
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


def _extract(parsed: dict[str, Any], channel: Channel) -> tuple[str, str, str, tuple[str, ...]]:
    """Maps a channel's field names onto the shared slots.

    The three formats genuinely have the same shape: an attention line, a
    body, a close, and tags. Only the names differ, so the mapping lives here
    rather than in three near-identical branches downstream.
    """
    body = str(parsed.get("body", "")).strip()
    if channel is Channel.NEWSLETTER:
        return str(parsed.get("subject", "")).strip(), body, str(parsed.get("close", "")).strip(), ()
    if channel is Channel.DEVTO:
        tags = tuple(str(t).strip() for t in parsed.get("tags", []))
        return str(parsed.get("title", "")).strip(), body, "", tags
    tags = tuple(str(t).strip() for t in parsed.get("hashtags", []))
    return str(parsed.get("hook", "")).strip(), body, str(parsed.get("close", "")).strip(), tags


def _gate(channel: Channel, hook: str, body: str, close: str, tags: tuple[str, ...]) -> tuple[VoiceViolation, ...]:
    if channel is Channel.NEWSLETTER:
        return check_newsletter(hook, body, close)
    if channel is Channel.DEVTO:
        return check_devto(hook, body, tags)
    return check(hook, body, close, tags)


class _Memory:
    """Minimal in-process Store, for callers that did not supply one."""

    def __init__(self) -> None:
        self._items: dict[str, Any] = {}

    def get(self, entity_id: str) -> Any:
        return self._items[entity_id]

    def save(self, entity_id: str, entity: Any) -> None:
        self._items[entity_id] = entity

    def list_all(self) -> list[Any]:
        return list(self._items.values())


class ContentStudio:
    """Drafts posts from weekly notes, gated and awaiting your approval."""

    def __init__(
        self,
        complete: Completion,
        notes: Store,
        drafts: Store,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        prospects: Store | None = None,
        outreach: Store | None = None,
        library: VoiceLibrary | None = None,
        persona: Persona | None = None,
    ) -> None:
        self._complete = complete
        self._notes = notes
        self._drafts = drafts
        self._clock = clock
        # The voice library is what makes the output sound like you rather
        # than like a model following rules about you. Optional so existing
        # callers keep working; with none supplied it drafts from rules alone.
        self.library: VoiceLibrary = library if library is not None else VoiceLibrary(_Memory(), _Memory())
        # Who you are, confirmed by you. The commit log says what shipped; this
        # says what is going on, which is what a post worth reading is made of.
        self.persona: Persona = persona if persona is not None else Persona(_Memory(), _Memory())
        # Optional so every existing caller keeps working. An in-memory
        # fallback is right here: an outreach list that vanishes on restart is
        # a worse product but not a broken one, and forcing every caller to
        # supply two more stores to use the part they already had is worse.
        self._prospects: Store = prospects if prospects is not None else _Memory()
        self._notes_out: Store = outreach if outreach is not None else _Memory()

    # -------------------------------------------------------------- Capture

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

    def note(self, note_id: str) -> WeeklyNote:
        found: WeeklyNote = self._notes.get(note_id)
        return found

    def latest_note(self) -> WeeklyNote | None:
        notes: list[WeeklyNote] = self._notes.list_all()
        return max(notes, key=lambda n: n.captured_at) if notes else None

    # ---------------------------------------------------------------- Draft

    def draft(self, note: WeeklyNote, channel: Channel = Channel.LINKEDIN) -> PostDraft:
        """Writes, checks, and redrafts until it passes or the limit is hit.

        Always returns a draft. A failing one comes back in REJECTED with the
        outstanding rules attached rather than raising, because a rejected
        draft you can read is more useful than an exception you cannot.
        """
        if not note.is_substantive():
            return self._store(self._blank(note, channel, (THIN_NOTE_MESSAGE,)))

        spec = SPECS[channel]
        budget = TOKEN_BUDGET[channel]
        examples = render_examples(self.library.for_prompt(channel), channel)
        correction = ""
        last: tuple[str, str, str, tuple[str, ...]] = ("", "", "", ())
        outstanding: tuple[str, ...] = ()

        for attempt in range(MAX_REDRAFTS):
            parsed = _parse(self._complete(_prompt(note, spec, correction, examples, self.persona.render()), budget))
            hook, body, close, tags = _extract(parsed, channel)
            last = (hook, body, close, tags)

            violations = _gate(channel, hook, body, close, tags)
            if not violations:
                return self._store(self._make(note, channel, last, DraftState.DRAFTED, attempt, ()))
            outstanding = tuple(f"{v.rule}: {v.detail}" for v in violations)
            correction = redraft_instruction(violations)

        return self._store(self._make(note, channel, last, DraftState.REJECTED, MAX_REDRAFTS, outstanding))

    def draft_everywhere(self, note: WeeklyNote) -> list[PostDraft]:
        """One note, every channel. The whole point of the module.

        A channel that fails does not stop the others: they are independent
        pieces of work, and losing a good LinkedIn post because Dev.to would
        not converge is a bad trade. The failures come back as REJECTED drafts
        in the returned list, so nothing is silently missing.
        """
        produced: list[PostDraft] = []
        for channel in Channel:
            try:
                produced.append(self.draft(note, channel))
            except DraftingFailed as exc:
                produced.append(self._store(self._blank(note, channel, (f"model failure: {exc}",))))
        return produced

    # ---------------------------------------------------------- Construction

    def _make(
        self,
        note: WeeklyNote,
        channel: Channel,
        parts: tuple[str, str, str, tuple[str, ...]],
        state: DraftState,
        redrafts: int,
        outstanding: tuple[str, ...],
    ) -> PostDraft:
        hook, body, close, tags = parts
        return PostDraft(
            draft_id=f"draft-{uuid.uuid4().hex[:12]}",
            note_id=note.note_id,
            state=state,
            channel=channel,
            hook=hook,
            body=body,
            close=close,
            hashtags=tags,
            created_at=self._clock(),
            redraft_count=redrafts,
            outstanding=outstanding,
        )

    def _blank(self, note: WeeklyNote, channel: Channel, outstanding: tuple[str, ...]) -> PostDraft:
        return self._make(note, channel, ("", "", "", ()), DraftState.REJECTED, 0, outstanding)

    def _store(self, draft: PostDraft) -> PostDraft:
        self._drafts.save(draft.draft_id, draft)
        return draft

    # -------------------------------------------------------------- Approval

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

    # --------------------------------------------------------------- Reading

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

    # -------------------------------------------------------------- Check-in

    def check_in(self, said: str) -> tuple[str, list[dict[str, str]]]:
        """You talk about your week. It proposes what it learned about you.

        Returns the check-in id and the proposed facts. Nothing is confirmed
        here; that is `persona.confirm`, and it takes your explicit yes per
        fact. A model that could write facts about you straight into the
        record it then writes from would drift into a version of you it
        invented.
        """
        cleaned = said.strip()
        if len(cleaned.split()) < 20:
            raise ValueError("say a little more; a sentence or two is not enough to learn from")
        raw = self._complete(extract_prompt(cleaned, self.persona.render()), 700)
        proposed = parse_proposed(raw)
        checkin = self.persona.record_checkin(cleaned, proposed)
        return checkin.checkin_id, proposed

    # -------------------------------------------------------------- Outreach

    def add_prospect(self, prospect: Prospect) -> Prospect:
        """Records someone worth writing to. Facts enter here, not in the model."""
        self._prospects.save(prospect.prospect_id, prospect)
        return prospect

    def prospects(self) -> list[Prospect]:
        people: list[Prospect] = self._prospects.list_all()
        return sorted(people, key=lambda p: p.added_at)

    def draft_note(
        self,
        prospect: Prospect,
        channel: OutreachChannel = OutreachChannel.LINKEDIN_NOTE,
    ) -> OutreachDraft:
        """Writes one note for one person, gated harder than a post.

        A generic post is a wasted post. A generic outreach note is worse than
        sending nothing: it tells the reader you did not look at them, in a
        message whose whole claim is that you did.
        """
        if not prospect.is_specific():
            return self._store_note(
                self._blank_note(
                    prospect,
                    channel,
                    ("the reason is too vague to write from; name the specific thing about them",),
                )
            )

        correction = ""
        subject, body = "", ""
        outstanding: tuple[str, ...] = ()

        for attempt in range(MAX_REDRAFTS):
            parsed = _parse(self._complete(_note_prompt(prospect, channel, correction), 600))
            subject = str(parsed.get("subject", "")).strip()
            body = str(parsed.get("body", "")).strip()

            violations = check_note(prospect, body, channel)
            if not violations:
                return self._store_note(
                    OutreachDraft(
                        draft_id=f"note-{uuid.uuid4().hex[:12]}",
                        prospect_id=prospect.prospect_id,
                        channel=channel,
                        subject=subject,
                        body=body,
                        created_at=self._clock(),
                        redraft_count=attempt,
                    )
                )
            outstanding = tuple(f"{v.rule}: {v.detail}" for v in violations)
            correction = redraft_instruction(violations)

        return self._store_note(
            OutreachDraft(
                draft_id=f"note-{uuid.uuid4().hex[:12]}",
                prospect_id=prospect.prospect_id,
                channel=channel,
                subject=subject,
                body=body,
                created_at=self._clock(),
                redraft_count=MAX_REDRAFTS,
                outstanding=outstanding,
            )
        )

    def approve_note(self, draft_id: str, principal_id: str) -> OutreachDraft:
        draft: OutreachDraft = self._notes_out.get(draft_id)
        approved = draft.approve(principal_id)
        self._notes_out.save(draft_id, approved)
        return approved

    def outreach_drafts(self) -> list[OutreachDraft]:
        drafts: list[OutreachDraft] = self._notes_out.list_all()
        return sorted(drafts, key=lambda d: d.created_at)

    def _blank_note(self, prospect: Prospect, channel: OutreachChannel, outstanding: tuple[str, ...]) -> OutreachDraft:
        return OutreachDraft(
            draft_id=f"note-{uuid.uuid4().hex[:12]}",
            prospect_id=prospect.prospect_id,
            channel=channel,
            subject="",
            body="",
            created_at=self._clock(),
            outstanding=outstanding,
        )

    def _store_note(self, draft: OutreachDraft) -> OutreachDraft:
        self._notes_out.save(draft.draft_id, draft)
        return draft

    def health(self) -> dict[str, Any]:
        """For the Observability Gateway, and for you at a glance."""
        all_drafts: Sequence[PostDraft] = self._drafts.list_all()
        by_state: dict[str, int] = {}
        by_channel: dict[str, int] = {}
        for draft in all_drafts:
            by_state[draft.state.value] = by_state.get(draft.state.value, 0) + 1
            by_channel[draft.channel.value] = by_channel.get(draft.channel.value, 0) + 1
        redrafts = [d.redraft_count for d in all_drafts if d.state is not DraftState.REJECTED]
        return {
            "drafts": len(all_drafts),
            "by_state": by_state,
            "by_channel": by_channel,
            "awaiting_approval": len(self.awaiting_approval()),
            "needs_attention": len(self.needs_attention()),
            # A rising average means the prompt and the gates have drifted
            # apart, which is the slow failure a two-year run would otherwise
            # hide until nothing passed at all.
            "mean_redrafts": round(sum(redrafts) / len(redrafts), 2) if redrafts else 0.0,
            "publishes_without_approval": 0,
        }


__all__ = ["ContentStudio", "DraftingFailed", "MAX_REDRAFTS", "TOKEN_BUDGET"]
