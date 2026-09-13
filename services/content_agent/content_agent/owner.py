"""Whose studio this is.

The briefs were written naming one person, which is right for the copy he
runs and wrong for every other copy. A friend testing this would have posts
drafted as a 21-year-old marketer called Jasmehr, in his voice, about his
week - which is not a bug you notice from the code, only from the output.

So the name is a setting, and every brief takes it. Two rules hold:

**No default name.** With nothing configured the briefs say "the person using
this" rather than inventing somebody. A wrong name in a prompt produces posts
signed by a stranger, which is worse than an unnamed one.

**They, not he.** Pronouns in a brief are a guess about whoever ends up
running it, and the neutral one is right for everybody. It also means adding a
name never requires editing the surrounding sentence.
"""

from __future__ import annotations

from dataclasses import dataclass

#: What the briefs call somebody who has not said who they are.
ANONYMOUS = "the person using this"

#: What the audit trail records when nobody has said who they are. A real
#: word rather than an empty string, because "approved by" followed by
#: nothing reads as a missing record rather than an unnamed one.
ANONYMOUS_PRINCIPAL = "owner"


@dataclass(frozen=True)
class Owner:
    """Who the drafts are written as."""

    name: str = ""
    #: A short self-description in the third person, e.g. "21, a marketer and
    #: builder" or "a final-year law student". Free text; it lands in the brief
    #: as written, so it reads best as a phrase rather than a sentence.
    about: str = ""

    @property
    def who(self) -> str:
        """How a brief should name them."""
        name = self.name.strip()
        about = self.about.strip().strip(",")
        if name and about:
            return f"{name}, {about}"
        if name:
            return name
        if about:
            return f"someone who is {about}"
        return ANONYMOUS

    @property
    def named(self) -> bool:
        return bool(self.name.strip() or self.about.strip())

    @property
    def principal(self) -> str:
        """Who an approval is recorded as having come from.

        A different thing from `who`, which is prose for a prompt. This goes
        into the audit trail on every approved draft, so it is a slug: lower
        case, no spaces, stable for as long as the name is.

        `ANONYMOUS_PRINCIPAL` rather than a name is the honest default. The
        record said "jasmehr" on every copy of this program, which meant a
        friend's approvals were attributed to somebody who had never seen the
        post - a quiet falsehood in the one record that exists to be true.
        """
        slug = "-".join(self.name.lower().split())
        kept = "".join(c for c in slug if c.isalnum() or c == "-").strip("-")
        return kept or ANONYMOUS_PRINCIPAL

    def fill(self, brief: str) -> str:
        """Substitutes `{who}` in a brief.

        `str.replace` rather than `str.format`, because the briefs contain JSON
        examples with literal braces and formatting them would raise on the
        first `{"area": ...}`.
        """
        return brief.replace("{who}", self.who)
