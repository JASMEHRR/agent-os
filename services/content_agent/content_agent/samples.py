"""Your voice, learned from what you actually approved.

Rules describe a voice. Examples *are* one. A model given five real posts
writes closer to the author than one given fifty rules about them, and it
keeps doing so after the model underneath is swapped, because the examples
travel with the prompt.

The samples come from one place: drafts you rated "sounds like me", optionally
after editing them. Nothing here is written by hand up front. That is the
design, not a gap. You said you would refine what it writes rather than supply
finished posts, so the loop is built around that: draft, edit, rate, and the
edited version becomes an example the next draft learns from.

Two properties keep this from drifting:

* **Only approved-by-you text becomes a sample.** A model-written draft that
  was never rated cannot feed the next draft. Otherwise the system would train
  on its own output and converge on its own habits rather than yours.
* **Samples are capped and recency-weighted.** The prompt carries the newest
  few, not all of them. Your voice this year is not your voice two years ago,
  and a two-year run that treated every sample as equal would pin the model
  to the earliest ones.
"""

from __future__ import annotations

import dataclasses
import uuid
from datetime import UTC, datetime
from typing import Any, Protocol

from content_agent.formats import Channel

#: How many examples reach the prompt. Few enough to leave room for the notes,
#: many enough to establish rhythm. Four is where the register locks in and a
#: fifth starts crowding the actual content.
SAMPLES_IN_PROMPT = 4

#: Below this a sample is a fragment, not an example of a post.
SAMPLE_MIN_WORDS = 25


class Store(Protocol):
    def get(self, entity_id: str) -> Any: ...

    def save(self, entity_id: str, entity: Any) -> None: ...

    def list_all(self) -> list[Any]: ...


@dataclasses.dataclass(frozen=True)
class VoiceSample:
    """One piece of writing you have said sounds like you."""

    sample_id: str
    channel: Channel
    text: str
    added_at: datetime
    #: The draft it came from, if any. Empty for text you supplied directly.
    from_draft_id: str = ""
    #: True when you changed the draft before approving it. Edited samples
    #: are the most valuable kind: the diff between draft and edit is exactly
    #: where the model was wrong about you.
    edited: bool = False


@dataclasses.dataclass(frozen=True)
class Rating:
    """Your verdict on a draft. Kept even when negative: a run of
    "does not sound like me" is the signal that the samples have drifted."""

    rating_id: str
    draft_id: str
    sounds_like_me: bool
    rated_at: datetime
    note: str = ""


class VoiceLibrary:
    """Stores samples and ratings, and hands the best examples to the prompt."""

    def __init__(self, samples: Store, ratings: Store) -> None:
        self._samples = samples
        self._ratings = ratings

    # --------------------------------------------------------------- Adding

    def add_sample(self, channel: Channel, text: str, from_draft_id: str = "", edited: bool = False) -> VoiceSample:
        cleaned = text.strip()
        if len(cleaned.split()) < SAMPLE_MIN_WORDS:
            raise ValueError(f"a sample needs at least {SAMPLE_MIN_WORDS} words to be an example of anything")
        sample = VoiceSample(
            sample_id=f"sample-{uuid.uuid4().hex[:12]}",
            channel=channel,
            text=cleaned,
            added_at=datetime.now(UTC),
            from_draft_id=from_draft_id,
            edited=edited,
        )
        self._samples.save(sample.sample_id, sample)
        return sample

    def rate(self, draft_id: str, sounds_like_me: bool, note: str = "") -> Rating:
        rating = Rating(
            rating_id=f"rating-{uuid.uuid4().hex[:12]}",
            draft_id=draft_id,
            sounds_like_me=sounds_like_me,
            rated_at=datetime.now(UTC),
            note=note.strip()[:300],
        )
        self._ratings.save(rating.rating_id, rating)
        return rating

    # -------------------------------------------------------------- Reading

    def samples(self, channel: Channel | None = None) -> list[VoiceSample]:
        found: list[VoiceSample] = self._samples.list_all()
        if channel is not None:
            found = [s for s in found if s.channel is channel]
        return sorted(found, key=lambda s: s.added_at, reverse=True)

    def for_prompt(self, channel: Channel) -> list[VoiceSample]:
        """The newest few for this channel, edited ones preferred.

        Falls back to other channels' samples when this one has none: a
        LinkedIn post is still a better example of your voice for a newsletter
        than no example at all. Marked so the prompt can say so.
        """
        own = self.samples(channel)
        chosen = sorted(own, key=lambda s: (not s.edited, -s.added_at.timestamp()))[:SAMPLES_IN_PROMPT]
        if chosen:
            return chosen
        return self.samples(None)[:SAMPLES_IN_PROMPT]

    def ratings(self) -> list[Rating]:
        found: list[Rating] = self._ratings.list_all()
        return sorted(found, key=lambda r: r.rated_at, reverse=True)

    def health(self) -> dict[str, Any]:
        rated = self.ratings()
        recent = rated[:10]
        positive = sum(1 for r in recent if r.sounds_like_me)
        return {
            "samples": len(self.samples()),
            "edited_samples": sum(1 for s in self.samples() if s.edited),
            "ratings": len(rated),
            # A falling number here is the earliest sign the voice has
            # drifted, and it shows before anyone would notice by reading.
            "recent_sounds_like_me": f"{positive}/{len(recent)}" if recent else "none yet",
        }


def render_examples(samples: list[VoiceSample], channel: Channel) -> str:
    """The block that goes into the prompt."""
    if not samples:
        return ""
    borrowed = any(s.channel is not channel for s in samples)
    header = "Here is writing Jasmehr has approved as sounding like him."
    if borrowed:
        header += " Some are from other channels; match the voice, not the format."
    header += " Match this register. Do not copy the content."
    blocks = "\n\n".join(f"--- example {i} ---\n{s.text}" for i, s in enumerate(samples, start=1))
    return f"{header}\n\n{blocks}\n--- end examples ---"
