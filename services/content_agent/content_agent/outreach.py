"""Personalised outreach notes, drafted for you to send.

The half of "grow an audience" that is not publishing. You name people worth
knowing; this drafts a specific note for each one, gated so that none of them
reads like the same message with a name swapped in.

**It drafts. It does not send.** There is no sending verb here, and that is not
caution about the code, it is about the platform: LinkedIn exposes no API for
invitations or messages, so the only way to automate sending is to drive a
browser session while evading their bot detection. That reliably ends in a
restricted account, which is the exact asset the outreach exists to build.

So the boundary sits where it does for posts. The work that scales is the
research and the writing. The click is yours, and it takes a few seconds.

The gates here are stricter than the post gates for one reason: a generic post
is a wasted post, but a generic outreach note is worse than sending nothing.
It tells the reader you did not look at them, in a message whose entire claim
is that you did.
"""

from __future__ import annotations

import dataclasses
import enum
import re
import uuid
from datetime import UTC, datetime

from content_agent.voice import VoiceViolation

#: LinkedIn's invitation note limit. Also a good ceiling for a cold email
#: opener: past this, nobody reads it as a note, they read it as a pitch.
NOTE_MAX_CHARS = 300

#: Below this it is not personalised, it is a greeting.
NOTE_MIN_CHARS = 90


class OutreachChannel(enum.Enum):
    """Where the note is going. Changes the length and the register."""

    LINKEDIN_NOTE = "linkedin_note"
    EMAIL = "email"


#: Phrases that mark a note as a template. Harsher than the post cliché list
#: because the failure is worse: these are the exact strings that make a
#: recipient stop reading.
TEMPLATE_TELLS = (
    "i came across your profile",
    "i hope this message finds you",
    "i wanted to reach out",
    "i would love to connect",
    "let's connect",
    "lets connect",
    "expand my network",
    "grow my network",
    "picking your brain",
    "pick your brain",
    "quick question for you",
    "i'm reaching out because",
    "as a fellow",
    "synergy",
    "circle back",
    "touch base",
    "exciting opportunity",
)

#: A note that never names the person is a broadcast. Checked by looking for
#: the name rather than by trusting the model to have used it.
NAME_PATTERN = re.compile(r"[A-Za-z]{2,}")


@dataclasses.dataclass(frozen=True)
class Prospect:
    """Someone worth knowing, and the specific reason why.

    `reason` is required and load-bearing. A prospect with no stated reason
    produces a note with nothing in it, because there was nothing to say. The
    field exists so that the thinnest possible input still fails visibly
    rather than producing polite filler.
    """

    prospect_id: str
    name: str
    #: Their role, company, or how you would describe them in one line.
    headline: str
    #: Why this person specifically. A talk they gave, a thing they built, a
    #: post they wrote. This is the whole personalisation budget.
    reason: str
    added_at: datetime
    #: Where you found them, so a note can reference it honestly.
    source: str = ""

    def is_specific(self) -> bool:
        """Enough to write a note that is about them.

        A reason of "works in AI" produces "I see you work in AI", which is
        the thing this module exists to not send.
        """
        return len(self.reason.split()) >= 6


@dataclasses.dataclass(frozen=True)
class OutreachDraft:
    """One note, for one person, awaiting your send."""

    draft_id: str
    prospect_id: str
    channel: OutreachChannel
    #: Email only. Empty for a LinkedIn note.
    subject: str
    body: str
    created_at: datetime
    approved: bool = False
    approved_by: str = ""
    redraft_count: int = 0
    outstanding: tuple[str, ...] = ()

    def full_text(self) -> str:
        return f"Subject: {self.subject}\n\n{self.body}".strip() if self.subject else self.body

    def approve(self, principal_id: str) -> OutreachDraft:
        if not principal_id.strip():
            raise ValueError("approval requires a named principal")
        return dataclasses.replace(self, approved=True, approved_by=principal_id)


def check_note(prospect: Prospect, body: str, channel: OutreachChannel) -> tuple[VoiceViolation, ...]:
    """Every rule that can be checked without judgement.

    Not checked: whether the note is persuasive. That is the reader's call and
    a heuristic pretending to know would be confidently wrong.
    """
    found: list[VoiceViolation] = []
    lowered = body.lower()

    if channel is OutreachChannel.LINKEDIN_NOTE and len(body) > NOTE_MAX_CHARS:
        found.append(
            VoiceViolation(
                "note-length",
                f"{len(body)} characters, LinkedIn cuts at {NOTE_MAX_CHARS}",
                f"Cut it to under {NOTE_MAX_CHARS} characters. Say one thing.",
            )
        )
    if len(body) < NOTE_MIN_CHARS:
        found.append(
            VoiceViolation(
                "note-too-short",
                f"{len(body)} characters",
                "Too short to be personal. Say what specifically about their work prompted this.",
            )
        )

    if prospect.name and prospect.name.split()[0].lower() not in lowered:
        found.append(
            VoiceViolation(
                "no-name",
                "never addresses them by name",
                f"Address {prospect.name.split()[0]} by name. A note that does not is a broadcast.",
            )
        )

    tells = [phrase for phrase in TEMPLATE_TELLS if phrase in lowered]
    if tells:
        found.append(
            VoiceViolation(
                "template-language",
                f"contains {', '.join(tells)}",
                f"Remove these phrases: {', '.join(tells)}. They are what makes a note look mass-sent.",
            )
        )

    # The reason is the whole personalisation budget. If none of its
    # distinctive words survived into the note, the note is not about them.
    distinctive = {
        word.lower() for word in NAME_PATTERN.findall(prospect.reason) if len(word) > 4 and word.lower() not in _COMMON
    }
    if distinctive and not (distinctive & set(NAME_PATTERN.findall(lowered))):
        found.append(
            VoiceViolation(
                "generic",
                "none of the specific reason appears in the note",
                f"Reference the specific thing: {prospect.reason}",
            )
        )

    if "—" in body or "–" in body:
        found.append(
            VoiceViolation(
                "forbidden-punctuation",
                "contains a dash",
                "Remove every em dash and en dash. Use a comma or a full stop.",
            )
        )

    if channel is OutreachChannel.EMAIL and "?" not in body:
        found.append(
            VoiceViolation(
                "no-ask",
                "no question anywhere",
                "End with one specific, easy question. A note with no ask gets no reply.",
            )
        )

    return tuple(found)


#: Words too common to count as evidence the note referenced the reason.
_COMMON = frozenset(
    {
        "about",
        "after",
        "their",
        "there",
        "these",
        "those",
        "which",
        "where",
        "while",
        "would",
        "could",
        "should",
        "being",
        "doing",
        "using",
        "works",
        "working",
        "recently",
        "really",
        "very",
    }
)


BRIEF = """Write a short outreach note. You are Jasmehr, 21, a marketer and builder.

Rules, all of them hard:
- Address them by first name.
- Reference the specific thing given as the reason. That is the whole point of
  the note. If you cannot work it in, the note has failed.
- One idea. One easy question at the end, or a clear reason you are writing.
- No em dashes. No "I came across your profile". No "would love to connect".
  No "pick your brain". These are what make a note look mass-sent.
- Do not flatter. Do not claim to have read things you were not told about.
- Sound like a person typing quickly, not a template being filled."""


def prospect_from(name: str, headline: str, reason: str, source: str = "") -> Prospect:
    return Prospect(
        prospect_id=f"person-{uuid.uuid4().hex[:12]}",
        name=name.strip(),
        headline=headline.strip(),
        reason=reason.strip(),
        added_at=datetime.now(UTC),
        source=source.strip(),
    )
