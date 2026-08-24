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
    #: The rule belongs to a subsystem CIR-001 blocked. Empty since the 2026-08-24
    #: ruling; retained because the guard that forbids claiming such a rule proven
    #: only means something while the category still exists.
    BLOCKED = "blocked"
    #: The rule is binding on implementation work and this build does not satisfy
    #: it. Distinct from uncovered in the direction that matters: uncovered means
    #: nobody has checked, this means we checked and we are not compliant. It is
    #: the least comfortable category and the one most worth having.
    DEVIATION = "deviation"
    #: The rule is a real obligation that an automated test in this repository
    #: cannot prove — an organizational commitment, a release-process rule, or
    #: a property of infrastructure that does not exist here. Every entry
    #: carries a reason, and a test asserts it does.
    NOT_CODE_CHECKABLE = "not_code_checkable"
    #: No automated test proves it yet, and one could. The honest default, and
    #: the only bucket that represents work someone should do.
    UNCOVERED = "uncovered"


#: Documents whose subsystems were construction-blocked by CIR-001.
#:
#: **Empty since 2026-08-24.** The G4 ruling released the Integration,
#: Deployment and Evolution platforms, so their rules became provable the
#: moment the modules were built. Their status is now the ordinary one: proven
#: where a test names them, uncovered where none does.
#:
#: Kept as an empty set rather than deleted, because `test_no_blocked_document_
#: rule_is_claimed_as_proven` is what stopped the matrix ever asserting that a
#: rule about a subsystem which did not run was nevertheless enforced. An empty
#: set is what makes that guard's continued passing mean something.
BLOCKED_DOCUMENTS: frozenset[str] = frozenset()

#: rule_id -> the test functions that prove it.
#:
#: A rule maps to one or more test *names*, not to node ids with paths, so that
#: moving a test between files does not falsely break the matrix while renaming
#: or deleting one correctly does.
MATRIX: dict[str, tuple[str, ...]] = {
    # ------------------------------------------ 01 Principles (architecture)
    # The architectural rules, now proved by tests/conformance/test_module_graph.py.
    "01.inline.5": ("test_the_ledger_exposes_no_verb_that_undoes_an_override",),
    "01.inline.6": ("test_secret_injection_requires_a_sandbox",),
    "01.inline.7": ("test_a_proposal_touching_a_non_violable_rule_is_rejected_at_validation",),
    "01.inline.8": ("test_there_are_no_circular_dependencies_between_modules",),
    "01.inline.9": ("test_no_gateway_reaches_into_another_gateways_internals",),
    "01.inline.16": ("test_context_assembly_truncates_rather_than_overflowing_the_budget",),
    "01.inline.17": ("test_ungrounded_inference_marks_the_outcome_degraded",),
    "01.inline.21": (
        "test_an_unregistered_tool_cannot_be_invoked",
        "test_registration_is_not_authorization",
    ),
    "01.inline.25": ("test_no_gateway_reaches_into_another_gateways_internals",),
    "01.inline.3": ("test_an_activity_beyond_the_declared_cost_budget_is_refused",),
    "01.inline.4": ("test_empty_context_marks_the_outcome_degraded",),
    # ------------------------------------------------- Third mapping pass
    # The 60-second failure-classification rules, which several documents
    # state independently and one kernel mechanism satisfies for all of them.
    "04.34.25": ("test_failure_classification_completes_within_bound_and_journals",),
    "05.29.6": ("test_failure_classification_completes_within_bound_and_journals",),
    "07.27.18": ("test_failure_classification_completes_within_bound_and_journals",),
    "11.31.19": ("test_failure_classification_completes_within_bound_and_journals",),
    "14.35.18": ("test_failure_classification_completes_within_bound_and_journals",),
    # Human denial is not overridable — stated by four documents, one property.
    "04.34.11": ("test_the_ledger_exposes_no_verb_that_undoes_an_override",),
    "06.23.7": ("test_the_ledger_exposes_no_verb_that_undoes_an_override",),
    "07.27.8": ("test_the_ledger_exposes_no_verb_that_undoes_an_override",),
    "13.36.12": ("test_a_human_override_of_a_learning_proposal_is_recorded",),
    # Immutability after formation, stated per subsystem.
    "08.25.19": ("test_a_broken_sink_does_not_swallow_the_incident",),
    "13.36.10": ("test_a_hypothesis_is_frozen_once_formed",),
    "13.36.18": ("test_the_journal_records_the_whole_loop_and_stays_intact",),
    "13.36.19": ("test_a_blocked_attempt_alerts_a_human_immediately_and_escalates",),
    "13.36.20": ("test_panic_completes_within_the_five_second_bound",),
    "14.35.13": ("test_journal_is_tamper_evident",),
    "14.35.19": ("test_security_subsystem_change_requires_human_ratification",),
    # Event Bus delivery and scope.
    "08.25.5": ("test_non_matching_event_type_is_not_routed",),
    "08.25.8": ("test_positions_advance_so_events_are_not_redelivered_on_poll",),
    "08.25.10": ("test_composed_output_is_never_anonymous_input",),
    "08.25.20": ("test_a_proposal_touching_a_non_violable_rule_is_rejected_at_validation",),
    # Decision and workflow residue.
    "11.31.13": ("test_anonymous_action_is_a_violation",),
    "11.31.15": ("test_quarantined_or_speculative_evidence_cannot_stand_alone",),
    "11.31.18": ("test_a_proposal_touching_a_non_violable_rule_is_rejected_at_validation",),
    "07.27.5": ("test_an_enabled_plugin_may_not_jump_straight_to_uninstalled",),
    "07.27.13": ("test_a_standing_order_cannot_pre_authorize_class_d",),
    "07.27.20": ("test_a_proposal_touching_a_non_violable_rule_is_rejected_at_validation",),
    "04.34.19": ("test_a_definition_that_cannot_produce_a_valid_dag_is_not_registrable",),
    "04.34.28": ("test_a_tripped_breaker_blocks_every_commitment",),
    "04.34.27": ("test_the_circuit_breaker_trips_on_its_own_threshold",),
    "04.34.26": ("test_repeated_denials_raise_an_authorization_violation_incident",),
    "04.34.33": ("test_only_a_human_may_invoke_panic",),
    "05.29.1": ("test_a_proposal_touching_a_non_violable_rule_is_rejected_at_validation",),
    "05.29.7": ("test_a_belief_without_evidence_is_speculation",),
    "05.29.12": ("test_routine_notifications_are_batched_not_delivered_one_by_one",),
    "06.23.11": ("test_input_failing_its_contract_is_rejected_before_the_sandbox",),
    "06.23.19": ("test_an_adopted_entry_is_measured_to_confirmation",),
    "04.34.30": ("test_an_adopted_entry_is_measured_to_confirmation",),
    "14.35.11": ("test_an_unauthenticated_request_is_401",),
    "12.34.12": ("test_journal_is_tamper_evident",),
    "12.34.6": ("test_self_escalation_is_a_violation",),
    "12.34.8": ("test_cross_tenant_action_is_denied",),
    "10.26.14": ("test_audit_events_are_not_purgeable_before_seven_years",),
    "10.26.19": ("test_a_broken_sink_does_not_swallow_the_incident",),
    "15.36.8": ("test_contradictory_evidence_escalates_and_never_commits",),
    "15.36.19": ("test_failure_classification_completes_within_bound_and_journals",),
    "15.36.20": ("test_panic_completes_within_the_five_second_bound",),
    "16.35.7": ("test_failure_classification_completes_within_bound_and_journals",),
    "16.35.12": ("test_failure_classification_completes_within_bound_and_journals",),
    # ------------------------------------------- 10 Knowledge (second pass)
    "10.26.7": ("test_cross_tenant_formation_is_denied",),
    "10.26.8": ("test_query_will_not_return_signals_above_the_authorized_sensitivity",),
    "10.26.10": ("test_a_hypothesis_is_invisible_to_reasoners",),
    "10.26.11": ("test_a_belief_resting_on_weak_memory_is_refused",),
    "10.26.13": ("test_the_ontology_is_not_self_modifying",),
    "10.26.15": ("test_anonymous_memory_is_inadmissible",),
    "10.26.17": ("test_an_entry_without_lineage_is_rejected",),
    "10.26.18": ("test_deprecation_never_deletes",),
    "10.26.20": ("test_a_proposal_touching_a_non_violable_rule_is_rejected_at_validation",),
    # ------------------------------------------------ 12 Tool (second pass)
    "12.34.1": (
        "test_an_unregistered_tool_cannot_be_invoked",
        "test_registration_is_not_authorization",
    ),
    "12.34.3": ("test_an_invocation_outside_scope_escalates",),
    "12.34.4": ("test_secret_injection_requires_a_sandbox",),
    "12.34.7": ("test_anonymous_registration_is_prohibited",),
    "12.34.9": ("test_a_mutating_tool_needs_compensation",),
    "12.34.10": ("test_a_cost_ceiling_breach_halts_mid_flight",),
    "12.34.13": ("test_input_failing_its_contract_is_rejected_before_the_sandbox",),
    "12.34.14": (
        "test_a_class_c_timeout_defers_and_never_approves",
        "test_a_class_d_timeout_rejects_and_never_approves",
    ),
    "12.34.19": ("test_panic_completes_within_the_five_second_bound",),
    "12.34.20": ("test_a_proposal_touching_a_non_violable_rule_is_rejected_at_validation",),
    # ------------------------------------------ 15 Governance (second pass)
    "15.36.9": ("test_class_b_rejects_a_single_option_proposal",),
    "15.36.10": ("test_confidence_thresholds_by_authority_are_enforced",),
    "15.36.12": ("test_governance_reports_its_own_overhead",),
    "15.36.13": ("test_an_artifact_requires_an_accountable_steward_covering_its_scope",),
    "15.36.15": ("test_evidence_gaps_produce_an_uncertainty_rider",),
    "15.36.18": ("test_an_artifact_contradicting_a_non_violable_rule_is_refused_at_formation",),
    # ---------------------------------------- 16 Observability (second pass)
    "16.35.4": ("test_secret_may_not_be_written_to_a_journal_or_log",),
    "16.35.5": ("test_the_health_report_says_it_is_not_a_compliance_ruling",),
    "16.35.9": ("test_routine_notifications_are_batched_not_delivered_one_by_one",),
    "16.35.10": ("test_signals_are_journalled_with_their_classification",),
    "16.35.13": ("test_panic_discloses_what_each_subsystem_knows",),
    "16.35.14": ("test_only_human_intervention_resumes_after_panic",),
    "16.35.15": ("test_the_gateway_still_exposes_no_mutating_verb",),
    # ------------------------------------------------------- 03 Tech Stack
    # The rules 03 states that this build satisfies without touching the
    # technology question CIR-001 turns on.
    "03.appendix.17": (
        "test_a_class_c_timeout_defers_and_never_approves",
        "test_a_class_d_timeout_rejects_and_never_approves",
    ),
    "03.appendix.23": (
        "test_offset_pagination_is_refused_not_ignored",
        "test_every_offset_spelling_is_refused",
    ),
    "03.appendix.24": ("test_a_mutating_request_without_a_key_is_refused",),
    "03.inline.3": (
        "test_the_generated_file_matches_the_generator",
        "test_the_python_first_light_mirrors_the_typescript_definition",
    ),
    "03.inline.8": ("test_input_failing_its_contract_is_rejected_before_the_sandbox",),
    "03.inline.20": ("test_an_abstraction_may_not_name_its_provider",),
    "03.inline.30": (
        "test_offset_pagination_is_refused_not_ignored",
        "test_every_offset_spelling_is_refused",
    ),
    "03.inline.33": (
        "test_no_sandbox_tier_runs_a_plugin_in_core_process_space",
        "test_the_manager_holds_no_verb_that_executes_plugin_code",
    ),
    # ------------------------------------------ 04 Business Operating Model
    "04.34.5": ("test_the_boundaries_intersect_rather_than_union",),
    "04.34.6": ("test_an_agent_cannot_commit_beyond_its_autonomy_level",),
    "04.34.7": (
        "test_an_unregistered_tool_cannot_be_invoked",
        "test_registration_is_not_authorization",
    ),
    "04.34.8": ("test_egress_requires_a_sandbox",),
    "04.34.9": ("test_a_standing_order_cannot_pre_authorize_class_d",),
    "04.34.10": (
        "test_a_class_c_timeout_defers_and_never_approves",
        "test_a_class_d_timeout_rejects_and_never_approves",
    ),
    "04.34.12": ("test_every_decision_is_journalled",),
    "04.34.14": ("test_cross_tenant_action_is_denied",),
    "04.34.16": ("test_private_memory_is_invisible_to_another_agent",),
    "04.34.17": ("test_a_linear_workflow_completes_and_releases_its_resources",),
    "04.34.18": ("test_a_mutating_tool_needs_compensation",),
    "04.34.20": ("test_a_definition_that_cannot_produce_a_valid_dag_is_not_registrable",),
    "04.34.21": (
        "test_sanitization_precedes_rendering",
        "test_prompt_injection_is_redacted",
    ),
    "04.34.22": ("test_injection_grant_carries_a_reference_never_a_value",),
    "04.34.24": ("test_the_boundaries_intersect_rather_than_union",),
    "04.34.29": ("test_a_proposal_touching_a_non_violable_rule_is_rejected_at_validation",),
    "04.34.32": ("test_failure_learning_needs_less_evidence_than_success_learning",),
    "04.34.34": ("test_panic_completes_within_the_five_second_bound",),
    "04.34.35": ("test_routine_notifications_are_batched_not_delivered_one_by_one",),
    # ---------------------------------------------------------- 02 Architecture
    "02.appendix.3": (
        "test_an_unregistered_tool_cannot_be_invoked",
        "test_registration_is_not_authorization",
    ),
    "02.appendix.5": ("test_gateway_exposes_no_method_returning_a_secret_value",),
    "02.appendix.6": (
        "test_class_d_decision_cannot_be_auto_approved_on_timeout",
        "test_adversarial_no_timeout_path_can_approve_a_class_d_decision",
    ),
    "02.appendix.10": ("test_the_boundaries_intersect_rather_than_union",),
    # ------------------------------------------------ 05 Agent Runtime Framework
    "05.29.3": ("test_an_activity_beyond_the_declared_cost_budget_is_refused",),
    "05.29.4": (
        "test_a_class_c_timeout_defers_and_never_approves",
        "test_a_class_d_timeout_rejects_and_never_approves",
    ),
    "05.29.8": ("test_an_irreversible_option_is_class_d_whatever_it_costs",),
    "05.29.10": ("test_panic_completes_within_the_five_second_bound",),
    # ------------------------------------------------- 06 Agent Operating Model
    "06.23.1": (
        "test_the_boundaries_intersect_rather_than_union",
        "test_a_capability_prefix_is_permitted_but_a_sibling_is_not",
    ),
    "06.23.2": ("test_a_tool_outside_the_registered_inventory_is_refused",),
    "06.23.3": (
        "test_an_agent_cannot_commit_beyond_its_autonomy_level",
        "test_insufficient_autonomy_is_denied",
    ),
    "06.23.5": ("test_a_standing_order_cannot_pre_authorize_class_d",),
    "06.23.6": (
        "test_a_class_c_timeout_defers_and_never_approves",
        "test_a_class_d_timeout_rejects_and_never_approves",
    ),
    "06.23.8": ("test_private_memory_is_invisible_to_another_agent",),
    "06.23.10": ("test_self_escalation_is_a_violation",),
    "06.23.12": ("test_every_decision_is_journalled",),
    "06.23.14": (
        "test_a_hypothesis_is_invisible_to_reasoners",
        "test_nothing_below_the_floor_is_presented_as_canonical",
    ),
    "06.23.15": ("test_an_activity_beyond_the_declared_cost_budget_is_refused",),
    "06.23.18": ("test_a_proposal_touching_a_non_violable_rule_is_rejected_at_validation",),
    # ---------------------------------------------- 07 Workflow Operating Model
    "07.27.3": ("test_a_mutating_tool_needs_compensation",),
    "07.27.4": ("test_planning_failure_goes_straight_to_failed_having_consumed_nothing",),
    "07.27.6": ("test_the_pre_allocated_budget_is_the_worst_case_not_the_optimistic_one",),
    "07.27.7": ("test_a_denied_gate_compensates_rather_than_proceeding",),
    "07.27.10": ("test_a_failing_terminal_activity_does_not_leave_the_workflow_running",),
    "07.27.11": ("test_a_definition_that_cannot_produce_a_valid_dag_is_not_registrable",),
    "07.27.17": ("test_egress_requires_a_sandbox",),
    "07.27.19": ("test_compensation_must_be_idempotent",),
    "07.27.21": ("test_the_journal_chain_is_intact_across_a_compensating_run",),
    "07.27.22": ("test_injection_hands_the_value_to_the_sandbox_and_nowhere_else",),
    "07.27.23": ("test_planning_fails_when_no_agent_holds_the_required_capability",),
    # ------------------------------------------------- 08 Event Operating Model
    "08.25.1": ("test_authenticated_producer_emits_a_schema_validated_event",),
    "08.25.2": ("test_published_events_are_immutable",),
    "08.25.3": ("test_producer_may_not_emit_into_another_tenant",),
    "08.25.4": ("test_producer_lacking_the_emission_permission_is_denied",),
    "08.25.6": ("test_no_event_is_silently_lost",),
    "08.25.7": ("test_non_critical_events_may_be_shed",),
    "08.25.9": ("test_acknowledgment_follows_processing",),
    "08.25.11": ("test_replay_never_reaches_a_live_consumer_group",),
    "08.25.14": ("test_a_revoked_producer_cannot_emit",),
    "08.25.15": ("test_audit_events_are_not_purgeable_before_seven_years",),
    "08.25.17": ("test_events_in_different_streams_are_causally_independent",),
    "08.25.18": ("test_dead_letters_are_queryable_for_human_review",),
    # --------------------------------------------- 10 Knowledge Operating Model
    "10.26.1": ("test_an_unregistered_belief_type_is_quarantined",),
    "10.26.2": ("test_contradiction_records_are_immutable_and_resolution_appends",),
    "10.26.3": ("test_a_promoted_belief_is_queryable",),
    "10.26.4": ("test_detection_demotes_both_canonical_beliefs",),
    "10.26.5": (
        "test_an_unfalsifiable_belief_is_dogma_and_is_quarantined",
        "test_falsifiability_must_be_bounded_in_the_future",
    ),
    "10.26.6": ("test_cross_tenant_formation_is_denied",),
    "10.26.9": ("test_nothing_below_the_floor_is_presented_as_canonical",),
    # ----------------------------------------------------- 11 Decision Operating Model
    "11.31.1": ("test_every_decision_is_journalled",),
    "11.31.3": ("test_adversarial_class_d_cannot_be_auto_approved",),
    "11.31.4": ("test_an_irreversible_option_is_class_d_whatever_it_costs",),
    "11.31.5": ("test_an_agent_cannot_commit_beyond_its_autonomy_level",),
    "11.31.8": ("test_contradictory_evidence_escalates_and_never_commits",),
    "11.31.9": ("test_class_b_rejects_a_single_option_proposal",),
    "11.31.11": ("test_a_standing_order_may_not_exceed_thirty_days",),
    "11.31.12": ("test_a_circuit_breaker_breach_stops_commitment_regardless_of_merit",),
    "11.31.14": ("test_cross_tenant_formation_is_denied",),
    "11.31.16": ("test_every_committed_decision_carries_an_expected_outcome",),
    "11.31.17": ("test_a_reversible_option_without_compensation_is_treated_as_irreversible",),
    "11.31.20": ("test_panic_defers_or_reverses_every_active_decision",),
    # ----------------------------------------------------- 12 Tool Operating Model
    "12.34.5": ("test_a_sandbox_is_destroyed_even_when_the_tool_explodes",),
    "12.34.17": ("test_idempotency_key_deduplicates_a_replayed_request",),
    # ------------------------------------------------ 14 Security Operating Model
    "14.35.3": (
        "test_self_escalation_is_a_violation",
        "test_self_status_change_is_rejected_as_self_escalation",
    ),
    "14.35.5": ("test_egress_requires_a_sandbox",),
    "14.35.9": ("test_private_memory_is_invisible_to_another_agent",),
    "14.35.12": ("test_gateway_exposes_no_method_returning_a_secret_value",),
    "14.35.14": ("test_anonymous_memory_is_inadmissible",),
    "14.35.15": ("test_cross_tenant_grant_requires_two_distinct_humans",),
    "14.35.16": ("test_cache_never_outlives_the_token",),
    "14.35.17": ("test_revocation_cascades_to_tokens_delegations_and_credentials",),
    "14.35.20": ("test_panic_completes_within_the_five_second_bound",),
    # ---------------------------------------------- 15 Governance Operating Model
    "15.36.4": ("test_only_a_human_may_invoke_panic",),
    "15.36.6": ("test_no_principal_may_certify_a_scope_they_are_accountable_for",),
    "15.36.7": ("test_the_journal_records_the_governance_trail",),
    # -------------------------------------------- 16 Observability Operating Model
    "16.35.3": ("test_halt_confirmations_are_reported_against_the_five_second_bound",),
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
    # ------------------------------ 17 Integration, released by the CIR-001 ruling
    "17.34.1": ("test_registration_is_not_approval_and_approval_is_not_activation",),
    "17.34.2": (
        "test_insufficient_approval_authority_is_refused",
        "test_class_d_approval_requires_a_human",
    ),
    "17.34.3": ("test_an_integration_must_fulfil_a_declared_abstraction",),
    "17.34.4": (
        "test_data_above_the_ceiling_is_refused_before_egress",
        "test_a_manifest_may_not_exceed_its_tiers_classification_ceiling",
    ),
    "17.34.6": ("test_approval_is_per_instance_not_per_class",),
    "17.34.7": ("test_anonymous_registration_is_prohibited",),
    "17.34.8": ("test_consumption_never_crosses_the_tenant_boundary",),
    "17.34.16": (
        "test_deprecation_names_a_successor_where_one_exists",
        "test_a_successor_must_exist",
    ),
    "17.34.19": ("test_panic_suspends_every_active_integration",),
    "17.34.20": ("test_substituting_the_provider_leaves_the_abstraction_constant",),
    "17.34.21": ("test_an_abstraction_may_not_name_its_provider",),
    "17.34.22": ("test_termination_is_a_human_act",),
    # ------------------------------- 18 Deployment, released by the CIR-001 ruling
    "18.36.1": ("test_declaration_validation_approval_and_activation_are_four_gates",),
    "18.36.2": (
        "test_risk_tier_maps_to_authority",
        "test_insufficient_authority_is_refused",
    ),
    "18.36.3": ("test_promotion_advances_authority_and_a_non_advance_is_refused",),
    "18.36.5": ("test_sovereign_infrastructure_may_not_sit_on_a_shared_substrate",),
    "18.36.6": ("test_anonymous_declaration_is_prohibited",),
    "18.36.7": ("test_discovery_never_crosses_the_tenant_boundary",),
    "18.36.8": ("test_no_runtime_exists_in_an_environment_without_mediation",),
    "18.36.11": ("test_sovereign_infrastructure_may_not_sit_on_a_shared_substrate",),
    "18.36.16": ("test_termination_is_an_e4_human_act",),
    "18.36.19": ("test_panic_quarantines_every_active_environment",),
    # -------------------------------- 19 Evolution, released by the CIR-001 ruling
    "19.38.1": (
        "test_an_anonymous_proposal_is_refused",
        "test_a_proposal_without_a_rationale_is_refused",
    ),
    "19.38.2": (
        "test_handoff_delivers_to_governance_and_relinquishes",
        "test_handoff_without_a_registered_governance_is_refused",
    ),
    "19.38.4": (
        "test_evolution_has_no_ratifying_verb",
        "test_the_ruling_authorized_construction_and_not_authority",
    ),
    "19.38.5": ("test_a_proposal_targeting_evolution_is_quarantined_and_escalated",),
    "19.38.7": ("test_a_proposal_on_unconfirmed_evidence_is_refused",),
    "19.38.8": ("test_an_anonymous_proposal_is_refused",),
    "19.38.10": ("test_governance_decides_and_evolution_records",),
    "19.38.13": ("test_no_state_transition_reaches_ratified_except_from_handed_off",),
    "19.38.15": ("test_only_confirmed_learning_is_consumable",),
    "19.38.18": ("test_the_recursion_guard_precedes_packaging",),
}

#: rule_id -> why no automated test in this repository can prove it.
#:
#: This category exists to stop `UNCOVERED` conflating two different things:
#: a rule nobody has tested yet, and a rule this repository is the wrong place
#: to test. Both are real obligations; only the first is work someone here can
#: do, and lumping them together makes the actionable number look larger than
#: it is while making it feel less actionable.
#:
#: It is deliberately not a dumping ground. Every entry states a specific
#: reason, a test asserts the reason is non-empty, and a rule may not appear
#: both here and in MATRIX — a rule cannot be simultaneously proven and
#: unprovable.
#: rule_id -> the technology the rule mandates.
#:
#: These 35 rules held an unusual position until 2026-08-24: satisfying them
#: *was* the CIR-001 question rather than work blocked behind it, because
#: adopting FastAPI to satisfy "All HTTP services must use FastAPI" would have
#: resolved by unilateral interpretation the exact conflict Section 6 rule 9
#: reserved for Governance.
#:
#: **The G4 ruling settled it, and settled it in their favour.** 03 is an
#: Implementation Specification, and the naming prohibition of 17/18/19 governs
#: capability abstractions and governance artifacts rather than 03. So these
#: rules are now **binding on implementation work** — and this build does not
#: satisfy them. It uses no FastAPI, no PostgreSQL, no Temporal; it is
#: in-process throughout, as all 27 of its modules are.
#:
#: That makes them a **recorded deviation from a binding rule**, which is a
#: different and more uncomfortable status than the block they replaced. A
#: block is someone else's decision to make. A deviation is ours, and adopting
#: the named stack is a deployment activity the ruling permits and does not
#: itself perform.
CIR_001_TECHNOLOGY_MANDATES: dict[str, str] = {
    "03.appendix.4": "Poetry",
    "03.appendix.5": "FastAPI",
    "03.appendix.6": "async HTTP client selection",
    "03.appendix.7": "SQLAlchemy 2.0",
    "03.appendix.8": "Alembic",
    "03.appendix.9": "Redis Streams",
    "03.appendix.10": "Temporal",
    "03.appendix.11": "LiteLLM Proxy",
    "03.appendix.12": "pgvector",
    "03.appendix.13": "Docker image tagging",
    "03.appendix.14": "container resource limits",
    "03.appendix.18": "a structured logging stack",
    "03.appendix.19": "OpenTelemetry",
    "03.appendix.20": "Prometheus",
    "03.appendix.21": "a prohibited-technology list",
    "03.inline.2": "Python for core services, Terraform for glue",
    "03.inline.4": "Terraform / HCL",
    "03.inline.6": "Poetry lockfiles and Docker",
    "03.inline.7": "FastAPI",
    "03.inline.9": "SQLAlchemy over raw SQL",
    "03.inline.10": "Alembic",
    "03.inline.11": "async HTTP client selection",
    "03.inline.12": "ASGI server selection",
    "03.inline.14": "PostgreSQL",
    "03.inline.15": "pgvector",
    "03.inline.16": "Apache AGE",
    "03.inline.17": "Redis persistence",
    "03.inline.18": "the Event Bus transport",
    "03.inline.19": "Temporal",
    "03.inline.21": "Docker image pinning",
    "03.inline.22": "docker compose",
    "03.inline.28": "deployment version tagging",
    "03.inline.31": "gRPC internally, REST externally",
    "03.inline.32": "OpenAPI-generated SDK models",
    "03.inline.34": "container memory limits",
}

NOT_CODE_CHECKABLE: dict[str, str] = {
    # 03's gate-enforced rules. Each is real and each is enforced, but by the
    # toolchain rather than by a test — and a test that shelled out to re-run
    # the type checker or the linter would be asserting that the gate it just
    # ran is the gate CI runs, which it cannot know.
    "03.appendix.2": "enforced by the mypy --strict gate in CI and pre-commit, not by a test that re-runs it",
    "03.inline.25": "enforced by the mypy --strict gate in CI and pre-commit, not by a test that re-runs it",
    "03.inline.24": "enforced by the ruff check and ruff format --check gates, not by a test that re-runs them",
    "03.appendix.15": "enforced by pre-commit itself; a test cannot assert that a hook ran before it did",
    "03.inline.23": "enforced by pre-commit and CI configuration, not by anything the code can assert",
    "03.appendix.3": (
        "enforced by the bandit gate and by code review; a test cannot prove the absence of a secret it was not shown"
    ),
    "03.inline.26": (
        "enforced by the bandit gate and by review; absence of a secret is not a property a test can establish"
    ),
    "03.appendix.16": "CI has never executed (Section 39 criterion 2); the gate exists and is unproven",
    "03.appendix.22": "a licence-review obligation discharged by ADR, not by code",
    "03.inline.29": "a licence-review obligation discharged by legal review and ADR",
    "03.appendix.25": "a release-process obligation: rollback is exercised against a deployment, and none exists",
    "03.inline.37": "a release-process obligation: rollback is exercised against a deployment, and none exists",
    "03.inline.38": "a runbook obligation, discharged by documentation rather than by code",
    "03.inline.27": "a branch-policy obligation enforced by repository settings, not by the code in the repository",
    "03.inline.13": "an obligation on a frontend this build does not contain",
    "03.inline.35": "a docstring-coverage gate; ruff's pydocstyle rules are not enabled in this configuration",
    "03.inline.36": "a configuration-management obligation; no deployment configuration exists to check",
    "03.appendix.1": (
        "a runtime-version obligation; the toolchain is 3.11.9 and a test asserting it would "
        "only restate its own interpreter"
    ),
    "03.inline.5": (
        "a runtime-version obligation; verified by the pinned toolchain rather than by a self-referential test"
    ),
    "03.inline.1": "a constitutional-amendment procedure, discharged by Governance rather than by code",
    # The Business Operating Model describes business, project, goal and task
    # objects. No module in this system realizes them: 04 is an operating
    # model for the organization the system serves, not for the system.
    "04.34.1": "no business/project/goal/task object model exists in this system to check against",
    "04.34.2": "an obligation on a business, not on this system; no business object exists here",
    "04.34.3": "a chartering process obligation; no project object exists here",
    "04.34.4": "a goal-setting process obligation; no goal object exists here",
    # Resource-share rules need production resource measurement.
    "04.34.31": "requires measurement of total production resource consumption, which does not exist",
    "05.29.11": "requires measurement of total production resource consumption, which does not exist",
    # Release-process obligations, enforced by how changes are shipped rather
    # than by anything the shipped code can assert about itself.
    "02.appendix.7": (
        "a release-process obligation: migration paths are reviewed at change time, not asserted at runtime"
    ),
    "08.25.13": "a release-process obligation on schema changes, enforced at review rather than at runtime",
    # Infrastructure this build does not have, for reasons recorded elsewhere.
    "02.appendix.2": (
        "names specific storage technologies; the substrate is CIR-001 blocked and no "
        "service holds business state to externalize"
    ),
    "02.appendix.8": "CI has never executed (Section 39 criterion 2); the gate exists and is unproven",
    "02.appendix.9": (
        "requires an HTTP transport to expose endpoints on; the API Gateway is transport-free pending CIR-001"
    ),
    "08.25.12": "requires a storage substrate with retention policy, which CIR-001 blocks",
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
        elif rule.rule_id in NOT_CODE_CHECKABLE:
            rows.append(
                Row(
                    rule=rule,
                    coverage=Coverage.NOT_CODE_CHECKABLE,
                    tests=(),
                    note=NOT_CODE_CHECKABLE[rule.rule_id],
                )
            )
        elif rule.rule_id in CIR_001_TECHNOLOGY_MANDATES:
            rows.append(
                Row(
                    rule=rule,
                    coverage=Coverage.DEVIATION,
                    tests=(),
                    note=(
                        f"mandates {CIR_001_TECHNOLOGY_MANDATES[rule.rule_id]}; binding on "
                        "implementation work since the 2026-08-24 ruling, and this in-process build "
                        "does not satisfy it — a recorded deviation, not a block"
                    ),
                )
            )
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
        # Zero since the 2026-08-24 ruling. Reported anyway: a number that used
        # to be 67 and is now 0 says more than its absence would.
        "blocked_subsystem": len(
            [r for r in rows if r.coverage == Coverage.BLOCKED and r.rule.document in BLOCKED_DOCUMENTS]
        ),
        "technology_mandates": len([r for r in rows if r.rule.rule_id in CIR_001_TECHNOLOGY_MANDATES]),
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
        f"- Blocked by CIR-001: **{stats['blocked']}** (was 102 before the ruling)",
        f"- **Deviations** — binding and not satisfied: **{stats['deviation']}**",
        f"- Not code-checkable here (each with a stated reason): **{stats['not_code_checkable']}**",
        f"- Uncovered: **{stats['uncovered']}**",
        f"- Coverage of currently testable rules: **{stats['coverage_of_testable']:.1%}**",
        "",
        "The uncovered count is the honest state of this matrix, not a rounding",
        "error. It is published so the gap is a number someone can act on.",
        "",
        "**On the deviations.** CIR-001 was resolved on 2026-08-24 by G4 human",
        "sovereign ruling: 03 is an Implementation Specification, and the naming",
        "prohibition of 17/18/19 governs capability abstractions and governance",
        "artifacts rather than 03. That released five modules for construction —",
        "and it made 03's 35 technology mandates *binding*. This build does not",
        "satisfy them: it uses no FastAPI, no PostgreSQL, no Temporal, and is",
        "in-process throughout. Those rules are therefore recorded as deviations",
        "rather than blocks, which is a less comfortable status and the correct",
        "one: a block was someone else's decision to make, a deviation is ours.",
        "",
        "The ruling could have gone the other way and struck those 35 rules, since",
        "17, 18 and 19 do forbid constitutional documents naming technologies. It",
        "did not: it distinguished 03 as an Implementation Specification instead.",
        "Recorded here because a matrix that showed only the outcome would hide",
        "that the outcome was a choice.",
        "",
        "`not_code_checkable` is not a softer word for uncovered. Those rules are",
        "real obligations that an automated test in *this repository* cannot prove:",
        "organizational commitments, release-process rules, or properties of",
        "infrastructure that does not exist here. Each carries a stated reason.",
        "",
        "| Rule | Coverage | Proven by | Statement |",
        "|---|---|---|---|",
    ]
    for row in rows:
        # A row that is not proven still owes the reader a reason. Falling
        # back to a dash would publish 318 rows saying nothing.
        tests = ", ".join(f"`{name}`" for name in row.tests) or (row.note or "—")
        lines.append(f"| `{row.rule.rule_id}` | {row.coverage.value} | {tests} | {row.rule.short} |")
    if stats["corpus_gaps"]:
        lines += ["", "## Corpus gaps", ""]
        for document, note in stats["corpus_gaps"].items():
            lines.append(f"- **{document}**: {note}")
    return "\n".join(lines) + "\n"
