"""Appendix F — Non-Violable Rule to Conformance Test Traceability Matrix.

`21_PLAN` §7: "Appendix F is the most important: it maps every non-violable rule
in Documents 01–19 to the specific automated test that proves it. Exists because
approximately two hundred absolute rules are otherwise unenforceable."

The mapping below is the matrix. It is deliberately **incomplete and honest
about it**: `report()` prints coverage and the uncovered rules by identifier, so
the gap is a measured number rather than an impression. A matrix that claimed
completeness it did not have would be worse than none, because it would retire
the question.

Three properties keep it from rotting:

* every rule is **extracted from the corpus** (see `rules.py`), so the
  denominator is the real one and a newly added rule appears as uncovered;
* every test named here is **checked to exist** in the collected suite, so a
  renamed or deleted test breaks the matrix rather than silently un-proving a
  rule;
* rules belonging to CIR-001-blocked subsystems are marked `BLOCKED` rather
  than `UNCOVERED`, because those two gaps have different causes and different
  remedies.

**On the count.** The plan estimated "approximately two hundred" absolute rules.
Extraction finds considerably more, largely because documents 01 and 03 state
rules inline throughout rather than in a closing section. The larger number is
reported as found; the estimate is not adjusted to match it.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from tests.conformance.rules import KNOWN_GAPS, Rule, extract_rules


class Coverage(StrEnum):
    PROVEN = "proven"
    #: The rule belongs to a subsystem CIR-001 blocks. Distinct from uncovered:
    #: the remedy is a Governance ruling, not another test.
    BLOCKED = "blocked"
    #: No automated test proves it yet. The honest default.
    UNCOVERED = "uncovered"


#: Documents whose subsystems are construction-blocked by CIR-001. Their rules
#: cannot be proven by an integration test until construction unblocks, per
#: 21C §38.6.
BLOCKED_DOCUMENTS = frozenset({"17", "18", "19"})

#: rule_id -> the test functions that prove it.
#:
#: A rule maps to one or more test *names*, not to node ids with paths, so that
#: moving a test between files does not falsely break the matrix while renaming
#: or deleting one correctly does.
MATRIX: dict[str, tuple[str, ...]] = {
    # ---------------------------------------------------------- 02 Architecture
    "02.appendix.4": ("test_the_gateway_holds_no_business_logic",),
    # ------------------------------------------------ 05 Agent Runtime Framework
    "05.29.2": ("test_an_activity_beyond_the_declared_cost_budget_is_refused",),
    "05.29.5": ("test_the_worker_returns_to_idle_holding_nothing",),
    # ------------------------------------------------- 06 Agent Operating Model
    "06.23.4": ("test_a_tool_outside_the_registered_inventory_is_refused",),
    "06.23.16": ("test_an_agent_may_not_review_its_own_output",),
    "06.23.17": ("test_an_agent_may_not_review_its_own_output",),
    # ---------------------------------------------- 07 Workflow Operating Model
    "07.27.9": ("test_an_adopted_entry_is_measured_to_confirmation",),
    "07.27.16": (
        "test_a_denied_gate_compensates_rather_than_proceeding",
        "test_a_failed_compensation_stalls_rather_than_quietly_failing",
    ),
    # ------------------------------------------------- 11 Decision Operating Model
    "11.31.2": ("test_class_d_decision_cannot_be_auto_approved_on_timeout",),
    "11.31.6": ("test_adversarial_no_timeout_path_can_approve_a_class_d_decision",),
    "11.31.7": (
        "test_a_class_c_timeout_defers_and_never_approves",
        "test_a_class_d_timeout_rejects_and_never_approves",
    ),
    "11.31.10": ("test_an_agent_may_not_answer_an_approval_gate",),
    # ----------------------------------------------------- 12 Tool Operating Model
    "12.34.2": ("test_a_tool_needing_an_integration_is_refused_while_cir_001_blocks",),
    "12.34.11": ("test_a_tool_outside_the_registered_inventory_is_refused",),
    # ------------------------------------------------- 13 Learning Operating Model
    "13.36.1": ("test_an_observation_requires_an_authenticated_observer",),
    "13.36.2": ("test_propagation_without_a_registered_intake_is_refused",),
    "13.36.3": ("test_a_proposal_touching_a_non_violable_rule_is_rejected_at_validation",),
    "13.36.4": (
        "test_the_declared_self_target_is_blocked",
        "test_a_disguised_target_name_is_blocked",
        "test_self_modification_described_as_another_subsystems_change_is_blocked",
    ),
    "13.36.5": ("test_confidence_below_the_class_threshold_is_abandoned_not_downgraded",),
    "13.36.6": ("test_a_correlation_pattern_can_never_reach_a_propagatable_confidence",),
    "13.36.7": ("test_an_observation_requires_an_authenticated_observer",),
    "13.36.8": ("test_an_observation_may_not_cross_the_tenant_boundary",),
    "13.36.9": ("test_an_adopted_entry_is_measured_to_confirmation",),
    "13.36.11": ("test_a_learning_cycle_defers_when_the_budget_has_no_headroom",),
    "13.36.13": ("test_a_contradicting_entry_is_quarantined_for_human_arbitration",),
    "13.36.14": ("test_quarantined_or_speculative_evidence_cannot_stand_alone",),
    "13.36.15": ("test_a_proposal_touching_a_non_violable_rule_is_rejected_at_validation",),
    "13.36.16": ("test_an_unclosed_window_is_reported_rather_than_closed_by_fiat",),
    "13.36.17": ("test_a_cycle_triggered_by_a_learning_event_is_blocked",),
    # ------------------------------------------------ 14 Security Operating Model
    "14.35.1": ("test_an_unauthenticated_request_is_401",),
    "14.35.2": ("test_the_boundaries_intersect_rather_than_union",),
    "14.35.4": ("test_a_tool_outside_the_registered_inventory_is_refused",),
    "14.35.6": ("test_class_d_decision_cannot_be_auto_approved_on_timeout",),
    "14.35.7": ("test_adversarial_no_timeout_path_can_approve_a_class_d_decision",),
    "14.35.8": ("test_an_agent_may_not_answer_an_approval_gate",),
    # ---------------------------------------------- 15 Governance Operating Model
    "15.36.1": ("test_an_artifact_requires_an_accountable_steward_covering_its_scope",),
    "15.36.2": ("test_g3_and_above_ratification_requires_a_human",),
    "15.36.3": ("test_an_artifact_contradicting_a_non_violable_rule_is_refused_at_formation",),
    "15.36.5": ("test_a_steward_cannot_form_above_their_g_class",),
    "15.36.11": ("test_a_policy_without_constitutional_lineage_is_rejected",),
    "15.36.17": ("test_an_exception_must_carry_all_four_constraints",),
    # -------------------------------------------- 16 Observability Operating Model
    "16.35.1": ("test_the_gateway_still_exposes_no_mutating_verb",),
    "16.35.2": ("test_a_timeline_query_is_authorized_like_every_other_read",),
}

#: Rules whose remedy is a Governance ruling rather than a test, listed so the
#: reason is attached to the rule rather than inferred from its document.
BLOCKED_NOTE = (
    "belongs to a subsystem CIR-001 blocks; provable only once construction is "
    "authorized by a G3 or G4 ruling (21C §38.6)"
)


@dataclass(frozen=True)
class Row:
    """One line of Appendix F."""

    rule: Rule
    coverage: Coverage
    tests: tuple[str, ...]
    note: str = ""


def build() -> tuple[Row, ...]:
    rows: list[Row] = []
    for rule in extract_rules():
        tests = MATRIX.get(rule.rule_id, ())
        if tests:
            rows.append(Row(rule=rule, coverage=Coverage.PROVEN, tests=tests))
        elif rule.document in BLOCKED_DOCUMENTS:
            rows.append(Row(rule=rule, coverage=Coverage.BLOCKED, tests=(), note=BLOCKED_NOTE))
        else:
            rows.append(Row(rule=rule, coverage=Coverage.UNCOVERED, tests=()))
    return tuple(rows)


def summary() -> dict[str, Any]:
    rows = build()
    counts = {state.value: len([r for r in rows if r.coverage == state]) for state in Coverage}
    testable = counts[Coverage.PROVEN.value] + counts[Coverage.UNCOVERED.value]
    return {
        "rules_extracted": len(rows),
        **counts,
        # Coverage of the rules that *could* be proven today. Reported beside
        # the raw total rather than instead of it, so neither number can be
        # quoted without the other.
        "coverage_of_testable": (round(counts[Coverage.PROVEN.value] / testable, 4) if testable else 0.0),
        "coverage_of_all": round(counts[Coverage.PROVEN.value] / len(rows), 4) if rows else 0.0,
        "corpus_gaps": dict(KNOWN_GAPS),
    }


def render() -> str:
    """Appendix F as text, for the docs directory and for a human to read."""
    rows = build()
    stats = summary()
    lines = [
        "# Appendix F — Non-Violable Rule to Conformance Test Traceability Matrix",
        "",
        "Generated from the ratified corpus by `tests/conformance/matrix.py`.",
        "Do not edit by hand: `test_appendix_f.py` regenerates and compares.",
        "",
        f"- Rules extracted from documents 01-19: **{stats['rules_extracted']}**",
        f"- Proven by an automated test: **{stats['proven']}**",
        f"- Blocked by CIR-001 (not provable yet): **{stats['blocked']}**",
        f"- Uncovered: **{stats['uncovered']}**",
        f"- Coverage of currently testable rules: **{stats['coverage_of_testable']:.1%}**",
        "",
        "The uncovered count is the honest state of this matrix, not a rounding",
        "error. It is published so the gap is a number someone can act on.",
        "",
        "| Rule | Coverage | Proven by | Statement |",
        "|---|---|---|---|",
    ]
    for row in rows:
        tests = ", ".join(f"`{name}`" for name in row.tests) or "—"
        lines.append(f"| `{row.rule.rule_id}` | {row.coverage.value} | {tests} | {row.rule.short} |")
    if stats["corpus_gaps"]:
        lines += ["", "## Corpus gaps", ""]
        for document, note in stats["corpus_gaps"].items():
            lines.append(f"- **{document}**: {note}")
    return "\n".join(lines) + "\n"
