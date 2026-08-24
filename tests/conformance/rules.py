"""Non-Violable Rule extraction (21_PLAN §7 Appendix F).

`21_PLAN` §7 on Appendix F:

> "Appendix F is the most important: it maps every non-violable rule in
> Documents 01–19 to the specific automated test that proves it. Exists because
> approximately two hundred absolute rules are otherwise unenforceable."

The rules are **extracted from the ratified documents**, not transcribed. A
transcribed list is a second copy that drifts: someone amends a document, the
copy stays, and the matrix reports coverage of a rule that no longer says what
it did. Reading the source means the denominator is always the real one.

Three shapes appear in the corpus and all three are handled:

* most documents close with a numbered "Non-Violable Rules" section;
* document 02 states its rules in an appendix with the same numbered shape;
* documents 01 and 03 state theirs inline, beneath the principle or the
  technology choice they bound.

**Document 09 is a known corpus gap.** Its Non-Violable Memory Rules section is
referenced in its own table of contents and is absent from the delivered text —
the file contains authoring notes where Section 29 should be. `KNOWN_GAPS`
records it, and a test asserts the gap is still there rather than letting it
pass as "document 09 simply has no absolute rules", which is the reading that
would quietly lose them.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

#: The ratified corpus. Read-only, and never edited by anything in this repo.
CORPUS = Path(__file__).resolve().parents[2] / "files"

#: Documents 01 through 19. 20A/20B/20C are manifests and 21/22 are
#: implementation architecture; none of them originate non-violable rules.
CONSTITUTIONAL_DOCUMENTS = tuple(f"{n:02d}" for n in range(1, 20))

_SECTION = re.compile(r"^##\s+(?:(\d+)\.|Appendix\s+[A-Z]:)\s+Non-Violable[^\n]*$", re.MULTILINE)
_NUMBERED = re.compile(r"^(\d+)\.\s+(.+)$")
#: Documents 01 and 03 both state rules inline; 01 bolds the label and 03 does
#: not, so the asterisks are optional.
_INLINE = re.compile(r"^(?:\*\*)?Non-Violable Rule:(?:\*\*)?\s*(.+)$", re.MULTILINE)

#: Documents whose rules cannot be extracted because the corpus does not
#: contain them. Recorded rather than inferred: a document with no rules and a
#: document whose rules are missing look identical to a counter, and the
#: difference is the whole point of a traceability matrix.
KNOWN_GAPS: dict[str, str] = {
    "09": (
        "09_MEMORY_OPERATING_MODEL's Non-Violable Memory Rules (its own Section 29) is "
        "referenced in the document's table of contents and absent from the delivered text; "
        "the file carries authoring notes where the section should be. Recorded as a "
        "permanent open item since Stage S4."
    ),
}


@dataclass(frozen=True)
class Rule:
    """One non-violable rule, as the document states it."""

    #: e.g. "14.35.2" for document 14's rule 2, or "01.18.2" for an inline one.
    rule_id: str
    document: str
    number: str
    text: str

    @property
    def short(self) -> str:
        return self.text if len(self.text) <= 90 else f"{self.text[:87]}..."


def _document_paths() -> dict[str, Path]:
    found: dict[str, Path] = {}
    for path in sorted(CORPUS.glob("*.txt")):
        match = re.match(r"#\s*(\d{2})", path.name)
        if match and match.group(1) in CONSTITUTIONAL_DOCUMENTS:
            found[match.group(1)] = path
    return found


def extract_rules() -> tuple[Rule, ...]:
    """Every non-violable rule in documents 01 through 19.

    Deliberately returns what it finds rather than a fixed count. If the
    corpus changes, the matrix's denominator changes with it, and a rule added
    to a document appears here as uncovered rather than going unnoticed.
    """
    rules: list[Rule] = []
    for document, path in _document_paths().items():
        text = path.read_text(encoding="utf-8", errors="replace")

        # Shape one: a closing numbered section.
        for section in _SECTION.finditer(text):
            body = text[section.end() :]
            end = body.find("\n---")
            body = body[: end if end != -1 else len(body)]
            prefix = section.group(1) or "appendix"
            for line in body.splitlines():
                numbered = _NUMBERED.match(line.strip())
                if numbered:
                    rules.append(
                        Rule(
                            rule_id=f"{document}.{prefix}.{numbered.group(1)}",
                            document=document,
                            number=numbered.group(1),
                            text=numbered.group(2).strip(),
                        )
                    )

        # Shape two: documents 01 and 03 state rules inline.
        for index, inline in enumerate(_INLINE.finditer(text), start=1):
            rules.append(
                Rule(
                    rule_id=f"{document}.inline.{index}",
                    document=document,
                    number=str(index),
                    text=inline.group(1).strip(),
                )
            )

    return tuple(rules)


def rules_by_document() -> dict[str, tuple[Rule, ...]]:
    grouped: dict[str, list[Rule]] = {}
    for rule in extract_rules():
        grouped.setdefault(rule.document, []).append(rule)
    return {document: tuple(items) for document, items in sorted(grouped.items())}
