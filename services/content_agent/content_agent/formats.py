"""One week of notes, several channels, one set of facts.

The leverage in this whole system is here. Writing the note is the only work
that cannot be automated, because only you know what you did. Everything
downstream is reformatting, and reformatting is exactly what a model is good
at. So a note written once becomes a LinkedIn post, a newsletter section and a
Dev.to article, and none of them can contain a fact the note did not.

Each format carries its own brief and its own gates. That separation matters:
the rules that make a LinkedIn hook work (survive the 140-character
truncation) actively harm a newsletter, where the subject line is the hook and
the opening paragraph should breathe. A single shared gate set would have to
be the loosest of the three, which means the strictest channel goes ungated.
"""

from __future__ import annotations

import dataclasses
import enum
import re

from content_agent.voice import (
    BROAD_HASHTAGS,
    CLICHES,
    FORBIDDEN_CHARS,
    HOOK_TRUNCATION_CHARS,
    MAX_HASHTAGS,
    MIN_HASHTAGS,
    NUMBER_PATTERN,
    VoiceViolation,
)


class Channel(enum.Enum):
    LINKEDIN = "linkedin"
    NEWSLETTER = "newsletter"
    DEVTO = "devto"


#: Shared across every channel: things that are wrong regardless of where they
#: are published. Kept separate from the per-channel rules so a new channel
#: inherits them by default rather than by remembering to.
def universal_violations(text: str) -> list[VoiceViolation]:
    found: list[VoiceViolation] = []

    for char, name in FORBIDDEN_CHARS.items():
        if char in text:
            found.append(
                VoiceViolation(
                    "forbidden-punctuation",
                    f"contains {name}",
                    f"Remove every {name}. Use a comma, a colon, a full stop, or split the sentence.",
                )
            )

    lowered = text.lower()
    cliches = [phrase for phrase in CLICHES if phrase in lowered]
    if cliches:
        found.append(
            VoiceViolation(
                "cliche",
                f"contains {', '.join(cliches)}",
                f"Remove these phrases entirely: {', '.join(cliches)}. Say the specific thing instead.",
            )
        )

    if not NUMBER_PATTERN.search(text):
        found.append(
            VoiceViolation(
                "no-concrete-detail",
                "no number anywhere",
                "Include one real number or specific detail from the notes. Do not invent a metric.",
            )
        )

    return found


@dataclasses.dataclass(frozen=True)
class FormatSpec:
    """What one channel wants, and what it refuses."""

    channel: Channel
    #: Appended to the shared voice brief.
    brief: str
    #: JSON keys the model must return.
    fields: tuple[str, ...]
    #: Rough target, given to the model rather than enforced. Length is a
    #: judgement and a hard gate on it would reject good work for being 40
    #: words long.
    target_words: int


LINKEDIN = FormatSpec(
    channel=Channel.LINKEDIN,
    brief=f"""Write a LinkedIn post.

- The hook must work as a complete thought in under {HOOK_TRUNCATION_CHARS}
  characters, because LinkedIn hides everything after that behind "see more".
- Short lines. Blank line between thoughts. One idea for the whole post.
- Close with a real question or a takeaway. Never "agree?".
- {MIN_HASHTAGS} to {MAX_HASHTAGS} hashtags, niche rather than broad.""",
    fields=("hook", "body", "close", "hashtags"),
    target_words=150,
)

NEWSLETTER = FormatSpec(
    channel=Channel.NEWSLETTER,
    brief="""Write a short newsletter issue.

- The subject line is the whole hook. Under 60 characters, specific, no
  clickbait, and it must make sense in an inbox next to 40 other emails.
- Open with the thing itself. No "hope you're well", no throat-clearing.
- 3 to 5 short paragraphs. You have more room than LinkedIn, so use it for
  the detail LinkedIn cannot fit: the actual problem, what you tried, what
  broke.
- Close with one line that invites a reply. A newsletter that gets replies is
  worth ten that get opens.
- No hashtags. This is email.""",
    fields=("subject", "body", "close"),
    target_words=350,
)

DEVTO = FormatSpec(
    channel=Channel.DEVTO,
    brief="""Write a Dev.to article.

- Title should promise a specific technical thing learned. Developers scan
  titles for problems they currently have.
- Open with the problem, not with who you are.
- Include the concrete detail: error codes, numbers, what the failure actually
  looked like. This is the audience that wants it.
- Use markdown headings. Use a fenced code block only if the notes contain
  something real to put in it; do not invent code.
- Close with what you would do differently.
- 4 tags, lowercase, no # prefix. Dev.to convention.""",
    fields=("title", "body", "tags"),
    target_words=600,
)

SPECS: dict[Channel, FormatSpec] = {
    Channel.LINKEDIN: LINKEDIN,
    Channel.NEWSLETTER: NEWSLETTER,
    Channel.DEVTO: DEVTO,
}

SUBJECT_MAX = 60
DEVTO_TAG_COUNT = 4
CODE_FENCE = re.compile(r"```")


def check_newsletter(subject: str, body: str, close: str) -> tuple[VoiceViolation, ...]:
    found = universal_violations(f"{subject}\n{body}\n{close}")

    if not subject.strip():
        found.append(VoiceViolation("subject", "empty", "Write a subject line under 60 characters."))
    elif len(subject) > SUBJECT_MAX:
        found.append(
            VoiceViolation(
                "subject-length",
                f"{len(subject)} characters",
                f"Cut the subject to under {SUBJECT_MAX} characters. Mail clients truncate past that.",
            )
        )

    opener = body.strip().lower()
    # The specific failure this catches is a model reaching for email
    # conventions it has seen a million times, which reads as a template.
    for phrase in ("hope you", "hope this finds", "happy friday", "hey friends", "hi everyone"):
        if opener.startswith(phrase):
            found.append(
                VoiceViolation(
                    "throat-clearing",
                    f"opens with {phrase!r}",
                    "Delete the greeting. Start with the thing itself.",
                )
            )
            break

    if "#" in f"{subject}{close}":
        found.append(
            VoiceViolation("hashtag-in-email", "hashtags in a newsletter", "Remove all hashtags. This is email.")
        )

    if not close.strip():
        found.append(VoiceViolation("close", "empty", "Close with one line that invites a reply."))

    return tuple(found)


def check_devto(title: str, body: str, tags: tuple[str, ...]) -> tuple[VoiceViolation, ...]:
    found = universal_violations(f"{title}\n{body}")

    if not title.strip():
        found.append(VoiceViolation("title", "empty", "Write a title naming the specific thing learned."))

    if len(tags) != DEVTO_TAG_COUNT:
        found.append(
            VoiceViolation(
                "tag-count",
                f"{len(tags)} tags",
                f"Dev.to takes exactly {DEVTO_TAG_COUNT} tags. Lowercase, no # prefix.",
            )
        )
    bad = [t for t in tags if t.startswith("#") or t != t.lower()]
    if bad:
        found.append(
            VoiceViolation(
                "tag-format",
                f"{', '.join(bad)} are wrongly formatted",
                "Dev.to tags are lowercase with no # prefix.",
            )
        )
    broad = [t for t in tags if f"#{t.lower()}" in BROAD_HASHTAGS]
    if broad:
        found.append(
            VoiceViolation(
                "broad-tag",
                f"{', '.join(broad)} are too broad",
                f"Replace {', '.join(broad)} with narrower tags specific to the article.",
            )
        )

    if "##" not in body and "\n#" not in body:
        found.append(
            VoiceViolation(
                "no-headings",
                "no markdown headings",
                "Break the article up with markdown headings. Dev.to readers scan before they read.",
            )
        )

    # An unclosed fence swallows the rest of the article into a code block on
    # publish, which is invisible in the draft and obvious to every reader.
    if len(CODE_FENCE.findall(body)) % 2 != 0:
        found.append(
            VoiceViolation(
                "unclosed-code-fence",
                "odd number of ``` fences",
                "Close every code fence. An unclosed one swallows the rest of the article.",
            )
        )

    return tuple(found)
