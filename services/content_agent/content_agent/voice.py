"""Jasmehr's LinkedIn voice, as enforceable rules rather than a prompt.

The rules live in the `linkedin-content` skill as prose. Prose in a prompt is
advice: a model follows it most of the time, drifts on a bad generation, and
drifts more as models are swapped underneath. Over a two-year unattended run
that drift is the whole failure mode. Anything checkable is checked here, and
a draft that fails is rejected and redrafted rather than published.

What is deliberately *not* enforced: whether the post is any good. That is a
judgement, it belongs to the human at the approval gate, and a scoring
heuristic pretending otherwise would just be a worse judge with more
confidence.
"""

from __future__ import annotations

import dataclasses
import re

#: LinkedIn truncates the post body behind "see more" at roughly two lines.
#: A hook that reads as a complete thought before the cut is the single
#: highest-leverage rule in the skill, so it is the one measured most exactly.
HOOK_TRUNCATION_CHARS = 140

MIN_HASHTAGS = 3
MAX_HASHTAGS = 5

#: An em dash is the most reliable tell of unedited model output, and the
#: standing instruction across every document in this account forbids it.
FORBIDDEN_CHARS = {
    "—": "em dash",
    "–": "en dash",
}

#: Openers and phrases that mark a post as generic. Matched case-insensitively
#: against the whole text, because they are damaging wherever they appear.
CLICHES = (
    "humbled to announce",
    "thrilled to announce",
    "excited to announce",
    "i'm humbled",
    "game changer",
    "game-changer",
    "let that sink in",
    "agree?",
    "thoughts?",
    "the future is here",
    "rise and grind",
    "hustle harder",
    "needle mover",
    "circle back",
    "at the end of the day",
    "in today's fast-paced world",
    "little did i know",
)

#: A post carrying no concrete detail is the failure the skill names first.
#: A number is the cheapest reliable proxy: a real one is specific, and the
#: model cannot invent one without it being visible to the reader at approval.
NUMBER_PATTERN = re.compile(r"\d")

HASHTAG_PATTERN = re.compile(r"#\w+")

#: Broad tags reach nobody. The skill asks for niche over broad, and these are
#: the ones that would otherwise get reached for by default.
BROAD_HASHTAGS = {
    "#motivation",
    "#success",
    "#business",
    "#marketing",
    "#linkedin",
    "#work",
    "#career",
    "#inspiration",
    "#growth",
    "#leadership",
    "#innovation",
    "#technology",
    "#ai",
}


@dataclasses.dataclass(frozen=True)
class VoiceViolation:
    """One rule broken, named precisely enough to redraft against.

    The `remedy` is written to be handed back to the model verbatim. A
    violation the redraft cannot act on is a violation that repeats.
    """

    rule: str
    detail: str
    remedy: str


def check(hook: str, body: str, close: str, hashtags: tuple[str, ...]) -> tuple[VoiceViolation, ...]:
    """Every rule that can be checked, checked. Empty means it passes."""
    violations: list[VoiceViolation] = []
    whole = f"{hook}\n{body}\n{close}"

    # ---------------------------------------------------------------- Hook
    if not hook.strip():
        violations.append(VoiceViolation("hook", "empty", "Write a hook: two lines, concrete, no clickbait."))
    elif len(hook) > HOOK_TRUNCATION_CHARS:
        violations.append(
            VoiceViolation(
                "hook-truncation",
                f"hook is {len(hook)} chars, LinkedIn cuts at about {HOOK_TRUNCATION_CHARS}",
                f"Cut the hook to under {HOOK_TRUNCATION_CHARS} characters so it survives the "
                '"see more" truncation as a complete thought.',
            )
        )

    # ------------------------------------------------------------ Characters
    for char, name in FORBIDDEN_CHARS.items():
        if char in whole:
            violations.append(
                VoiceViolation(
                    "forbidden-punctuation",
                    f"contains {name}",
                    f"Remove every {name}. Use a comma, a colon, a full stop, or split the sentence.",
                )
            )

    # --------------------------------------------------------------- Cliches
    lowered = whole.lower()
    found = [phrase for phrase in CLICHES if phrase in lowered]
    if found:
        violations.append(
            VoiceViolation(
                "cliche",
                f"contains {', '.join(found)}",
                f"Remove these phrases entirely: {', '.join(found)}. Say the specific thing instead.",
            )
        )

    # -------------------------------------------------------------- Concrete
    if not NUMBER_PATTERN.search(whole):
        violations.append(
            VoiceViolation(
                "no-concrete-detail",
                "no number anywhere in the post",
                "Include one real number or one specific concrete detail from the week's notes. "
                "Do not invent a metric; if there is no number, name a specific thing that happened.",
            )
        )

    # -------------------------------------------------------------- Hashtags
    declared = tuple(t if t.startswith("#") else f"#{t}" for t in hashtags)
    if not MIN_HASHTAGS <= len(declared) <= MAX_HASHTAGS:
        violations.append(
            VoiceViolation(
                "hashtag-count",
                f"{len(declared)} hashtags",
                f"Use between {MIN_HASHTAGS} and {MAX_HASHTAGS} hashtags.",
            )
        )
    broad = [t for t in declared if t.lower() in BROAD_HASHTAGS]
    if broad:
        violations.append(
            VoiceViolation(
                "broad-hashtag",
                f"{', '.join(broad)} are too broad to reach anyone",
                f"Replace {', '.join(broad)} with narrower tags specific to the post's subject.",
            )
        )

    # ----------------------------------------------------------------- Close
    if not close.strip():
        violations.append(
            VoiceViolation("close", "empty", "Add a soft close: a question or a takeaway. Never 'agree?'.")
        )

    return tuple(violations)


def redraft_instruction(violations: tuple[VoiceViolation, ...]) -> str:
    """Turns violations into something a model can act on in one pass.

    Numbered rather than prose, because a model handed a paragraph of
    complaints reliably fixes the first and forgets the rest.
    """
    lines = ["The previous draft broke these rules. Fix every one of them:"]
    lines.extend(f"{i}. {v.remedy}" for i, v in enumerate(violations, start=1))
    return "\n".join(lines)


#: Handed to the model as the standing description of who is writing. Kept
#: here beside the checks so the two cannot drift: a prompt that described a
#: different voice than the gates enforce would loop forever.
VOICE_BRIEF = """You write LinkedIn posts as Jasmehr, a 21-year-old marketer and builder.

Voice:
- Honest and specific. Building in public, not performing success.
- Short lines. White space. One idea per post.
- Lightly conversational. Never guru-flavoured, never motivational-poster.
- Imperfect consistency is fine to admit openly. It reads as real.

Hard rules:
- No em dashes or en dashes. Ever.
- No fabricated metrics. Use only numbers present in the notes provided.
- No "humbled to announce" style openers. No hustle cliches. No "agree?".
- Hook must work as a complete thought in under 140 characters, because
  LinkedIn hides the rest behind "see more".
- 3 to 5 hashtags, niche rather than broad.

Every post should pass this test: would a hiring manager in Dubai or Tokyo
think better of him after reading it?"""
