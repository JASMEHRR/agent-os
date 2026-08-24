"""Appendix F, kept honest (21_PLAN §7).

A traceability matrix is only worth having if it cannot quietly become wrong.
Three ways it could, and the test that closes each:

* **a rule is amended or added** and the matrix does not notice — closed by
  extracting rules from the corpus rather than transcribing them, and by
  asserting every mapped identifier still resolves to a real rule;
* **a test is renamed or deleted** and the rule it proved silently becomes
  unproven — closed by checking every named test exists in the collected suite;
* **the published matrix drifts from the generator** — closed by regenerating
  and comparing, the same discipline the bilingual boundary uses at S7.

The suite deliberately does **not** assert a coverage floor. A floor would
create pressure to map a rule to a test that does not really prove it, which is
the failure mode a traceability matrix exists to prevent. Coverage is reported
and left visible instead.
"""

from __future__ import annotations

import pathlib

import pytest

from tests.conformance.matrix import (
    BLOCKED_DOCUMENTS,
    MATRIX,
    NOT_CODE_CHECKABLE,
    Coverage,
    build,
    render,
    summary,
)
from tests.conformance.rules import KNOWN_GAPS, extract_rules, rules_by_document

REPO = pathlib.Path(__file__).resolve().parents[2]
PUBLISHED = REPO / "docs" / "appendix_f_traceability.md"


def collected_test_names() -> set[str]:
    """Every test function name in the repository.

    Read from the source tree rather than from pytest's collection, so this
    test does not depend on being run as part of a full collection and cannot
    be fooled by a selective run.
    """
    names: set[str] = set()
    for path in (*REPO.glob("libs/**/*.py"), *REPO.glob("services/**/*.py"), *REPO.glob("tests/**/*.py")):
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            stripped = line.strip()
            if stripped.startswith("def test_"):
                names.add(stripped[4:].split("(")[0].strip())
    return names


# ---------------------------------------------------------------- Extraction


def test_rules_are_extracted_from_the_ratified_corpus() -> None:
    """The denominator is real, not asserted.

    21_PLAN estimates "approximately two hundred". Extraction finds
    substantially more, largely because documents 01 and 03 state rules inline
    throughout rather than in a closing section. The finding is reported rather
    than reconciled to the estimate.
    """
    rules = extract_rules()
    assert len(rules) > 200, "the corpus should yield at least the plan's estimate"
    assert all(rule.text for rule in rules)
    assert all(rule.rule_id.count(".") == 2 for rule in rules)


def test_every_constitutional_document_contributes_rules_or_is_a_declared_gap() -> None:
    """A document with no rules and a document whose rules are missing look
    identical to a counter. The difference is the point of this matrix."""
    grouped = rules_by_document()
    for document in (f"{n:02d}" for n in range(1, 20)):
        if document in grouped:
            assert grouped[document], f"document {document} yielded an empty rule set"
        else:
            assert document in KNOWN_GAPS, (
                f"document {document} contributed no non-violable rules and is not a declared "
                "corpus gap; either the extractor missed a shape or a gap went unrecorded"
            )


def test_the_document_09_gap_is_still_a_gap() -> None:
    """Recorded since Stage S4, and asserted so it cannot be forgotten.

    If document 09's Non-Violable Memory Rules section is ever supplied, this
    test fails and the gap entry should be removed — which is the correct way
    for a recorded gap to end.
    """
    assert "09" in KNOWN_GAPS
    assert "09" not in rules_by_document(), "document 09 now yields rules; remove its KNOWN_GAPS entry and map them"


# ------------------------------------------------------- The matrix's integrity


@pytest.mark.parametrize("rule_id", sorted(MATRIX))
def test_every_mapped_rule_identifier_resolves_to_a_real_rule(rule_id: str) -> None:
    """A mapping to a rule that no longer exists claims coverage of nothing."""
    known = {rule.rule_id for rule in extract_rules()}
    assert rule_id in known, f"'{rule_id}' is mapped in Appendix F but is not in the corpus"


@pytest.mark.parametrize("test_name", sorted({name for names in MATRIX.values() for name in names}))
def test_every_named_test_exists(test_name: str) -> None:
    """The property that stops the matrix rotting.

    Without this, renaming a test silently un-proves whatever rule it was
    mapped to, and the matrix goes on reporting the rule as covered.
    """
    assert test_name in collected_test_names(), (
        f"Appendix F names '{test_name}', which no longer exists; the rule it proved is "
        "now unproven and the matrix must be updated rather than left claiming coverage"
    )


def test_no_blocked_document_rule_is_claimed_as_proven() -> None:
    """21C §38.6 — blocked modules carry specification tests, not conformance ones.

    Claiming a CIR-001-blocked rule as proven would be the most damaging entry
    this matrix could contain: it would assert that a rule about a subsystem
    that does not run is nevertheless enforced.
    """
    for row in build():
        if row.rule.document in BLOCKED_DOCUMENTS:
            assert row.coverage is not Coverage.PROVEN, (
                f"'{row.rule.rule_id}' belongs to a CIR-001-blocked subsystem and cannot be proven"
            )


@pytest.mark.parametrize("rule_id", sorted(NOT_CODE_CHECKABLE))
def test_every_not_code_checkable_rule_states_a_specific_reason(rule_id: str) -> None:
    """The category exists to be honest, not to be convenient.

    Without a stated reason per entry, `not_code_checkable` becomes a place to
    put anything inconvenient, and the coverage figure it improves stops
    meaning anything. A reason a reader can disagree with is the point.
    """
    reason = NOT_CODE_CHECKABLE[rule_id]
    assert len(reason) > 30, f"'{rule_id}' needs a specific reason, not a label"
    assert rule_id in {rule.rule_id for rule in extract_rules()}


def test_no_rule_is_both_proven_and_unprovable() -> None:
    """A rule cannot be simultaneously proven and impossible to prove.

    If one ever appears in both, the mapping is wrong in one of the two places
    and the matrix is asserting a contradiction about itself.
    """
    overlap = sorted(set(MATRIX) & set(NOT_CODE_CHECKABLE))
    assert not overlap, f"these rules are both mapped to a test and declared unprovable: {overlap}"


def test_the_not_code_checkable_category_stays_small_against_uncovered() -> None:
    """A structural brake on the easiest way to fake progress.

    Coverage can be improved either by writing tests or by reclassifying rules
    as unprovable. Only the first is real. This does not forbid the category
    growing — some rules genuinely belong in it — but it fails if it ever
    becomes the larger explanation for what is not proven, which is the point
    at which someone should be asked why.
    """
    stats = summary()
    assert stats["not_code_checkable"] < stats["uncovered"], (
        "more rules are declared unprovable than are simply untested; "
        "coverage is being improved by reclassification rather than by testing"
    )


def test_coverage_is_reported_honestly() -> None:
    """Uncovered rules are the majority, and the matrix says so.

    Deliberately not a floor. A floor would create pressure to map a rule to a
    test that does not really prove it, which is precisely the failure a
    traceability matrix exists to prevent.
    """
    stats = summary()
    assert (
        stats["proven"] + stats["blocked"] + stats["deviation"] + stats["not_code_checkable"] + stats["uncovered"]
        == stats["rules_extracted"]
    )
    assert stats["uncovered"] > 0, "if this ever reaches zero, celebrate and then verify it"
    assert 0.0 < stats["coverage_of_testable"] < 1.0


def test_every_row_has_a_coverage_state_and_proven_rows_name_tests() -> None:
    for row in build():
        assert row.coverage in set(Coverage)
        if row.coverage is Coverage.PROVEN:
            assert row.tests, f"'{row.rule.rule_id}' is proven by nothing named"
        else:
            assert not row.tests
        if row.coverage in (Coverage.BLOCKED, Coverage.NOT_CODE_CHECKABLE):
            assert row.note, f"'{row.rule.rule_id}' is excused without saying why"


# -------------------------------------------------------- The published file


def test_the_published_appendix_matches_the_generator() -> None:
    """The same single-source discipline the bilingual boundary uses at S7.

    Without this, someone edits the published table by hand, it diverges from
    what the code would generate, and the divergence is invisible until someone
    trusts the wrong copy.
    """
    assert PUBLISHED.exists(), "Appendix F has not been generated; run tests/conformance/generate.py"
    assert PUBLISHED.read_text(encoding="utf-8") == render(), (
        "docs/appendix_f_traceability.md differs from what matrix.py generates. "
        "Regenerate it rather than editing it by hand."
    )


def test_every_excused_row_justifies_itself_in_the_published_file() -> None:
    """The guard the previous pass found missing by reading rather than testing.

    `test_every_row_has_a_coverage_state_and_proven_rows_name_tests` checks the
    in-memory row carries a note. Nothing checked the note survived into the
    published table — and it had not: the renderer fell back to a dash. The row
    object was correct and the document was useless, which is exactly what a
    test on the object alone cannot see.

    Scoped to **excused** rows, not all non-proven ones. A rule marked blocked
    or not-code-checkable is claiming an exemption and owes a justification a
    reader can dispute. A rule marked uncovered is admitting nobody tested it,
    and the state is the whole story — demanding prose there would produce 184
    restatements of the word "uncovered".
    """
    excused = {Coverage.BLOCKED.value, Coverage.NOT_CODE_CHECKABLE.value}
    published = PUBLISHED.read_text(encoding="utf-8").splitlines()
    rows = [line for line in published if line.startswith("| `")]
    assert rows, "the published appendix has no rows"

    silent: list[str] = []
    for line in rows:
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        rule_id, coverage, reason = cells[0].strip("`"), cells[1], cells[2]
        if coverage in excused and (reason in ("", "—") or len(reason) < 30):
            silent.append(rule_id)
    assert not silent, (
        f"{len(silent)} rows claim an exemption without publishing a justification, starting with "
        f"{silent[:5]}; an exemption a reader cannot dispute is not an exemption"
    )


def test_every_proven_row_names_its_tests_in_the_published_file() -> None:
    """The same check in the other direction.

    A proven row whose test column rendered empty would claim coverage without
    saying by what, which is the shape of an unfalsifiable claim.
    """
    for line in PUBLISHED.read_text(encoding="utf-8").splitlines():
        if not line.startswith("| `"):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if cells[1] == Coverage.PROVEN.value:
            assert "`test_" in cells[2], f"{cells[0]} is published as proven but names no test"


def test_the_published_appendix_warns_against_hand_editing() -> None:
    assert "Do not edit by hand" in PUBLISHED.read_text(encoding="utf-8")
