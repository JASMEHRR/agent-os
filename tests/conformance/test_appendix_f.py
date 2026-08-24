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


def test_coverage_is_reported_honestly() -> None:
    """Uncovered rules are the majority, and the matrix says so.

    Deliberately not a floor. A floor would create pressure to map a rule to a
    test that does not really prove it, which is precisely the failure a
    traceability matrix exists to prevent.
    """
    stats = summary()
    assert stats["proven"] + stats["blocked"] + stats["uncovered"] == stats["rules_extracted"]
    assert stats["uncovered"] > 0, "if this ever reaches zero, celebrate and then verify it"
    assert 0.0 < stats["coverage_of_testable"] < 1.0


def test_every_row_has_a_coverage_state_and_proven_rows_name_tests() -> None:
    for row in build():
        assert row.coverage in set(Coverage)
        if row.coverage is Coverage.PROVEN:
            assert row.tests, f"'{row.rule.rule_id}' is proven by nothing named"
        else:
            assert not row.tests


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


def test_the_published_appendix_warns_against_hand_editing() -> None:
    assert "Do not edit by hand" in PUBLISHED.read_text(encoding="utf-8")
