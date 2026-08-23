"""Decision Gateway — classification, options, authority, approval (doc 11).

Stage S5 test list: "Class A-D commitments with options and evidence grounding;
authority resolution by decision class and autonomy level; **structural**
enforcement that Level 3/4 (Class C/D) approval gates never auto-approve on
timeout (built by construction, not configuration); reversal with compensation;
supersession with lineage tracking."

Plus the adversarial test the Validation Criteria demand: an attempt to force
an auto-approval on a Class D decision, which must fail.
"""

from __future__ import annotations

from datetime import timedelta

import pytest

from core.exceptions import AgentOSError, NotFoundError, ValidationError
from decision_gateway import (
    AuthorityExceeded,
    DecisionClass,
    DecisionGateway,
    DecisionState,
    Option,
    ProposalRejected,
    Scope,
    SelfApprovalError,
    StandingOrderViolation,
)
from kernel.authority import RiskClass

from .conftest import (
    AGENT,
    HUMAN,
    SECOND_HUMAN,
    TENANT,
    acting_option,
    evidence,
    make_proposal,
    null_option,
    risk_at,
)

# ------------------------------------------------------------- classification


def test_a_trivial_reversible_proposal_is_class_a(decisions: DecisionGateway, token: str) -> None:
    record = decisions.propose(token, make_proposal(scope=Scope.TASK))
    assert record.decision_class == DecisionClass.A_TRIVIAL


def test_cost_drives_the_class_upward(decisions: DecisionGateway, token: str) -> None:
    record = decisions.propose(
        token,
        make_proposal(options=(null_option(), acting_option(cost=5.0), acting_option("b", cost=4.0, value=0.5))),
    )
    assert record.decision_class == DecisionClass.B_OPERATIONAL


def test_an_irreversible_option_is_class_d_whatever_it_costs(decisions: DecisionGateway, token: str) -> None:
    """11.5.1 — irreversibility is a Class D criterion in its own right."""
    record = decisions.propose(
        token,
        make_proposal(
            options=(
                null_option(),
                acting_option(cost=0.001, reversible=False, compensation=None),
                acting_option("b", cost=0.001, value=0.5, reversible=False, compensation=None),
            ),
            evidence_refs=evidence(count=3, confidence=0.99),
        ),
    )
    assert record.decision_class == DecisionClass.D_EXISTENTIAL


def test_portfolio_scope_is_existential(decisions: DecisionGateway, token: str) -> None:
    record = decisions.propose(token, make_proposal(scope=Scope.PORTFOLIO, evidence_refs=evidence(count=3)))
    assert record.decision_class == DecisionClass.D_EXISTENTIAL


def test_classification_takes_the_highest_criterion(decisions: DecisionGateway, token: str) -> None:
    """11.24.2 — proposers do not get to sit just below an escalation threshold."""
    record = decisions.propose(
        token,
        make_proposal(
            scope=Scope.BUSINESS,
            options=(null_option(), acting_option(cost=0.001), acting_option("b", cost=0.001, value=0.5)),
        ),
    )
    # Cheap enough for Class A, but business scope makes it Strategic.
    assert record.decision_class == DecisionClass.C_STRATEGIC


# ------------------------------------------------------------------- options


def test_class_b_rejects_a_single_option_proposal(decisions: DecisionGateway, token: str) -> None:
    """11 rule 9 — no Class B or higher commitment with a single option."""
    with pytest.raises(ProposalRejected, match="two distinct options"):
        decisions.propose(token, make_proposal(options=(null_option(), acting_option(cost=5.0))))


def test_the_null_option_is_mandatory_above_class_a(decisions: DecisionGateway, token: str) -> None:
    """11.16.3 — a decision to act must demonstrate superiority to doing nothing."""
    with pytest.raises(ProposalRejected, match="null option"):
        decisions.propose(
            token,
            make_proposal(options=(acting_option(cost=5.0), acting_option("b", cost=4.0, value=0.5))),
        )


def test_duplicate_option_ids_are_rejected(decisions: DecisionGateway, token: str) -> None:
    with pytest.raises(ProposalRejected, match="distinct"):
        decisions.propose(
            token,
            make_proposal(options=(null_option(), acting_option("same", cost=5.0), acting_option("same", cost=4.0))),
        )


def test_an_option_that_cannot_beat_doing_nothing_loses(decisions: DecisionGateway, token: str) -> None:
    """The null option is the baseline, and ties go to inaction."""
    worthless = Option(
        option_id="worthless",
        description="spend for nothing",
        estimated_cost=5.0,
        expected_value=0.0,
        reversible=True,
        compensation_ref="comp-1",
    )
    record = decisions.propose(
        token,
        make_proposal(
            options=(
                null_option(),
                worthless,
                Option(
                    option_id="also-worthless",
                    description="likewise",
                    estimated_cost=4.0,
                    expected_value=0.0,
                    reversible=True,
                    compensation_ref="comp-2",
                ),
            ),
        ),
    )
    assert record.decision.chosen_option.is_null


# ------------------------------------------------------------------ evidence


def test_class_b_needs_a_belief_or_a_declared_gap(decisions: DecisionGateway, token: str) -> None:
    """11 rule 1 — evidence, or an explicitly declared gap. Never silence."""
    with pytest.raises(ProposalRejected, match="declared"):
        decisions.propose(
            token,
            make_proposal(
                options=(null_option(), acting_option(cost=5.0), acting_option("b", cost=4.0, value=0.5)),
                evidence_refs=(),
            ),
        )


def test_a_declared_gap_satisfies_class_b(decisions: DecisionGateway, token: str) -> None:
    record = decisions.propose(
        token,
        make_proposal(
            options=(null_option(), acting_option(cost=5.0), acting_option("b", cost=4.0, value=0.5)),
            evidence_refs=(),
            declared_gap="no canonical pricing belief exists yet; proceeding with monitoring",
        ),
    )
    assert record.decision.burden.value == "evidence_sparse"


def test_class_d_demands_a_comprehensive_basis(decisions: DecisionGateway, token: str) -> None:
    with pytest.raises(ProposalRejected, match="comprehensive"):
        decisions.propose(
            token,
            make_proposal(
                scope=Scope.PORTFOLIO,
                evidence_refs=evidence(count=1),
            ),
        )


def test_contradictory_evidence_escalates_and_never_commits(decisions: DecisionGateway, token: str, knowledge) -> None:
    """11 rule 8 — no autonomous path past an unresolved contradiction."""
    decisions.evidence.contradiction_check = lambda _ref: True
    record = decisions.propose(token, make_proposal())
    assert record.state == DecisionState.ESCALATED
    assert record.decision.burden.value == "evidence_contradictory"
    with pytest.raises(AgentOSError):
        decisions.commit(record.decision_id, committer_id=AGENT)


# ------------------------------------------------------------------ authority


def test_class_a_at_sufficient_confidence_is_approved(decisions: DecisionGateway, token: str) -> None:
    record = decisions.propose(token, make_proposal())
    assert record.state == DecisionState.APPROVED
    assert record.authorized_by == AGENT


def test_low_confidence_defers_rather_than_proceeding(decisions: DecisionGateway, token: str) -> None:
    """21B §18.9 — agents may not suppress the confidence warning."""
    record = decisions.propose(token, make_proposal(evidence_refs=evidence(confidence=0.4)))
    assert record.state == DecisionState.DEFERRED
    assert "below the floor" in (record.deferral_reason or "")


def test_high_risk_escalates_a_class_b_decision(decisions: DecisionGateway, token: str) -> None:
    """11.14.3 — risk-adjusted escalation, computed by the kernel resolver.

    High risk does two things at once: it raises the required authority to
    Level 3, and it lowers derived confidence. Evidence at 0.95 that would
    comfortably clear Level 2 lands at 0.77 under a high-risk penalty, below
    the 0.80 floor its new level demands — so the decision defers rather than
    proceeding. The escalation is visible in `required_authority`; the
    deferral is the honest consequence of it.
    """
    record = decisions.propose(
        token,
        make_proposal(
            options=(null_option(), acting_option(cost=5.0), acting_option("b", cost=4.0, value=0.5)),
            risk=risk_at(RiskClass.HIGH),
            evidence_refs=evidence(confidence=0.95),
        ),
    )
    assert record.decision.required_authority.requires_human
    assert decisions.get(record.decision_id).state == DecisionState.DEFERRED


def test_high_risk_with_stronger_evidence_reaches_human_review(decisions: DecisionGateway, token: str) -> None:
    """The same escalation, with evidence strong enough to clear the raised floor."""
    record = decisions.propose(
        token,
        make_proposal(
            options=(null_option(), acting_option(cost=5.0), acting_option("b", cost=4.0, value=0.5)),
            risk=risk_at(RiskClass.HIGH),
            evidence_refs=evidence(count=3, confidence=0.99),
        ),
    )
    assert record.decision.required_authority.requires_human
    assert record.state == DecisionState.UNDER_REVIEW


def test_an_agent_cannot_commit_beyond_its_autonomy_level(decisions: DecisionGateway, token: str) -> None:
    """11 rule 5. The agent is Level 2; a Class C decision needs Level 3."""
    record = decisions.propose(token, make_proposal(scope=Scope.BUSINESS, evidence_refs=evidence(confidence=0.95)))
    assert record.state == DecisionState.UNDER_REVIEW  # routed for human approval
    with pytest.raises(AgentOSError):
        decisions.commit(record.decision_id, committer_id=AGENT)


# ---------------------------------------------------- approval gate integrity


def _class_c(decisions: DecisionGateway, token: str):
    return decisions.propose(token, make_proposal(scope=Scope.BUSINESS, evidence_refs=evidence(confidence=0.95)))


def _class_d(decisions: DecisionGateway, token: str):
    return decisions.propose(
        token, make_proposal(scope=Scope.PORTFOLIO, evidence_refs=evidence(count=3, confidence=0.99))
    )


def test_a_class_c_decision_is_routed_for_human_approval(decisions: DecisionGateway, token: str) -> None:
    record = _class_c(decisions, token)
    assert record.state == DecisionState.UNDER_REVIEW
    assert len(decisions.pending_approval()) == 1


def test_only_a_human_may_answer_an_approval_request(decisions: DecisionGateway, token: str) -> None:
    """11 rule 2 — no Class C or D commitment without explicit human approval."""
    record = _class_c(decisions, token)
    request = decisions.pending_approval()[0]
    with pytest.raises(AuthorityExceeded, match="not a Human"):
        decisions.respond(request.request_id, responder_id=AGENT, response="approve")
    assert record.state == DecisionState.UNDER_REVIEW


def test_a_proposer_may_not_approve_its_own_proposal(decisions: DecisionGateway, token: str) -> None:
    """14.17.5 — approver and requester must be distinct."""
    record = decisions.propose(
        token,
        make_proposal(scope=Scope.BUSINESS, proposer_id=HUMAN, evidence_refs=evidence(confidence=0.95)),
    )
    request = decisions.pending_approval()[0]
    with pytest.raises(SelfApprovalError):
        decisions.respond(request.request_id, responder_id=HUMAN, response="approve")
    assert record.state == DecisionState.UNDER_REVIEW


def test_human_approval_advances_the_decision(decisions: DecisionGateway, token: str) -> None:
    record = _class_c(decisions, token)
    request = decisions.pending_approval()[0]
    decisions.respond(request.request_id, responder_id=HUMAN, response="approve")
    assert record.state == DecisionState.APPROVED
    assert record.authorized_by == HUMAN


def test_a_class_c_timeout_defers_and_never_approves(decisions: DecisionGateway, token: str, clock) -> None:
    """11 rule 3 — no auto-approval on timeout."""
    record = _class_c(decisions, token)
    clock.advance(timedelta(hours=25))
    decisions.sweep_timeouts()
    assert record.state == DecisionState.DEFERRED
    assert record.state != DecisionState.APPROVED


def test_a_class_d_timeout_rejects_and_never_approves(decisions: DecisionGateway, token: str, clock) -> None:
    record = _class_d(decisions, token)
    clock.advance(timedelta(days=4))
    decisions.sweep_timeouts()
    assert record.state == DecisionState.REJECTED


def test_adversarial_no_timeout_path_can_approve_a_class_d_decision(
    decisions: DecisionGateway, token: str, clock
) -> None:
    """Stage S5 Validation Criteria: an adversarial attempt to force auto-approval.

    The attack surface is time itself: wait out the window and hope the
    implementation treats silence as consent. It sweeps repeatedly, across
    escalating durations, and asserts the decision never reaches Approved and
    never becomes committable.
    """
    record = _class_d(decisions, token)
    assert record.state == DecisionState.UNDER_REVIEW

    for days in (4, 30, 365, 3650):
        clock.advance(timedelta(days=days))
        decisions.sweep_timeouts()
        assert record.state != DecisionState.APPROVED, f"auto-approved after {days} days"
        assert record.state != DecisionState.COMMITTED

    assert record.state == DecisionState.REJECTED
    with pytest.raises(AgentOSError):
        decisions.commit(record.decision_id, committer_id=HUMAN)


def test_the_orchestrator_exposes_no_auto_approval_path() -> None:
    """ "Built by construction, not configuration" — asserted on the surface."""
    from decision_gateway import ApprovalOrchestrator

    surface = {name for name in dir(ApprovalOrchestrator) if not name.startswith("_")}
    assert {"auto_approve", "approve_on_timeout", "default_approve", "implicit_consent"}.isdisjoint(surface)


def test_batched_requests_remain_individually_actionable(decisions: DecisionGateway, token: str) -> None:
    """11.18 — batched approval requests are never approved as a group."""
    first = _class_c(decisions, token)
    second = decisions.propose(
        token,
        make_proposal(
            summary="a second strategic change", scope=Scope.BUSINESS, evidence_refs=evidence(confidence=0.95)
        ),
    )
    assert len(decisions.pending_approval()) == 2
    request = decisions.approvals.for_decision(first.decision_id)[0]
    decisions.respond(request.request_id, responder_id=HUMAN, response="approve")
    assert first.state == DecisionState.APPROVED
    assert second.state == DecisionState.UNDER_REVIEW  # untouched


def test_rejection_and_deferral_are_recorded_with_reasons(decisions: DecisionGateway, token: str) -> None:
    record = _class_c(decisions, token)
    request = decisions.pending_approval()[0]
    decisions.respond(request.request_id, responder_id=HUMAN, response="reject")
    assert record.state == DecisionState.REJECTED
    assert HUMAN in (record.rejection_reason or "")


def test_a_request_cannot_be_answered_twice(decisions: DecisionGateway, token: str) -> None:
    _class_c(decisions, token)
    request = decisions.pending_approval()[0]
    decisions.respond(request.request_id, responder_id=HUMAN, response="approve")
    with pytest.raises(ValidationError, match="already answered"):
        decisions.respond(request.request_id, responder_id=SECOND_HUMAN, response="reject")


# --------------------------------------------------------------- commitment


def test_commitment_requires_approval_first(decisions: DecisionGateway, token: str) -> None:
    record = _class_c(decisions, token)
    with pytest.raises(AgentOSError, match="not Approved"):
        decisions.commit(record.decision_id, committer_id=HUMAN)


def test_a_committed_decision_records_its_expected_outcome(decisions: DecisionGateway, token: str) -> None:
    """11 rule 16 — no commitment without a documented expected outcome."""
    record = decisions.propose(token, make_proposal())
    decisions.commit(record.decision_id, committer_id=AGENT)
    assert record.state == DecisionState.COMMITTED
    assert record.decision.expected_outcome
    assert record.committed_at is not None


def test_verification_requires_a_committed_decision(decisions: DecisionGateway, token: str) -> None:
    """12 rule 2 / 17 rule 2 / 18 rule 2 — the interface every effect asks through."""
    record = decisions.propose(token, make_proposal())
    with pytest.raises(AgentOSError, match="not committed"):
        decisions.verify(record.decision_id, DecisionClass.A_TRIVIAL)
    decisions.commit(record.decision_id, committer_id=AGENT)
    assert decisions.verify(record.decision_id, DecisionClass.A_TRIVIAL).is_committed


def test_verification_refuses_an_underpowered_decision(decisions: DecisionGateway, token: str) -> None:
    record = decisions.propose(token, make_proposal())
    decisions.commit(record.decision_id, committer_id=AGENT)
    with pytest.raises(AuthorityExceeded):
        decisions.verify(record.decision_id, DecisionClass.C_STRATEGIC)


# ------------------------------------------------------------- compensation


def test_a_reversible_option_without_compensation_is_treated_as_irreversible(
    decisions: DecisionGateway, token: str
) -> None:
    """11.21.2 — without compensation logic, the decision is irreversible."""
    record = decisions.propose(
        token,
        make_proposal(
            options=(
                null_option(),
                acting_option(compensation=None),
                acting_option("b", value=0.5, compensation=None),
            )
        ),
    )
    assert record.decision.reversible is False
    assert "no pre-positioned compensation" in record.decision.rationale


def test_an_unresolvable_compensation_reference_is_refused(decisions: DecisionGateway, token: str) -> None:
    decisions.compensation.compensation_exists = lambda _ref: False
    record = decisions.propose(token, make_proposal())
    assert record.decision.reversible is False


def test_human_designated_irreversibility_is_honoured(decisions: DecisionGateway, token: str) -> None:
    """11 rule 4 — irreversibility requires explicit human designation."""
    record = decisions.propose(
        token, make_proposal(irreversible=True, evidence_refs=evidence(count=3, confidence=0.99))
    )
    assert record.decision.reversible is False
    assert record.decision_class == DecisionClass.D_EXISTENTIAL


# ---------------------------------------------------- reversal & supersession


def test_reversal_within_the_window_executes_compensation(decisions: DecisionGateway, token: str) -> None:
    record = decisions.propose(token, make_proposal())
    decisions.commit(record.decision_id, committer_id=AGENT)
    decisions.reverse(record.decision_id, requester_id=HUMAN, reason="changed circumstances")
    assert record.state == DecisionState.REVERSED
    assert record.reversed_by == HUMAN
    entries = decisions.query_journal(decision_id=record.decision_id, action="reversed")
    assert entries[0]["compensation"] == "comp-1"


def test_reversal_after_the_window_is_refused(decisions: DecisionGateway, token: str, clock) -> None:
    record = decisions.propose(token, make_proposal())
    decisions.commit(record.decision_id, committer_id=AGENT)
    clock.advance(timedelta(hours=25))
    with pytest.raises(AgentOSError, match="window"):
        decisions.reverse(record.decision_id, requester_id=HUMAN, reason="too late")


def test_an_irreversible_decision_cannot_be_reversed(decisions: DecisionGateway, token: str) -> None:
    """No compensation means no reversal — and, since 11.5.1 makes
    irreversibility a Class D criterion, it also means human approval first."""
    record = decisions.propose(
        token,
        make_proposal(
            options=(
                null_option(),
                acting_option(compensation=None),
                acting_option("b", value=0.5, compensation=None),
            ),
            evidence_refs=evidence(count=3, confidence=0.99),
        ),
    )
    assert record.decision_class == DecisionClass.D_EXISTENTIAL
    request = decisions.pending_approval()[0]
    decisions.respond(request.request_id, responder_id=HUMAN, response="approve")
    decisions.commit(record.decision_id, committer_id=HUMAN)
    with pytest.raises(AgentOSError, match="irreversible"):
        decisions.reverse(record.decision_id, requester_id=HUMAN, reason="nope")


def test_supersession_preserves_lineage(decisions: DecisionGateway, token: str) -> None:
    """11.22 — replacement with lineage preservation."""
    old = decisions.propose(token, make_proposal(summary="original plan"))
    decisions.commit(old.decision_id, committer_id=AGENT)
    decisions.mark_executing(old.decision_id)
    new = decisions.propose(token, make_proposal(summary="revised plan"))
    decisions.supersede(old.decision_id, new.decision_id, authorized_by=HUMAN)
    assert old.state == DecisionState.SUPERSEDED
    assert old.superseded_by == new.decision_id
    assert new.supersedes == old.decision_id


# ------------------------------------------------------------------ outcome


def test_outcome_recording_detects_divergence(decisions: DecisionGateway, token: str) -> None:
    record = decisions.propose(token, make_proposal())
    decisions.commit(record.decision_id, committer_id=AGENT)
    decisions.mark_executing(record.decision_id)
    decisions.report_outcome(record.decision_id, "the change had no measurable effect")
    assert record.state == DecisionState.COMPLETED
    assert record.outcome_diverged


def test_an_outcome_is_immutable_once_recorded(decisions: DecisionGateway, token: str) -> None:
    record = decisions.propose(token, make_proposal())
    decisions.commit(record.decision_id, committer_id=AGENT)
    decisions.mark_executing(record.decision_id)
    decisions.report_outcome(record.decision_id, "done")
    with pytest.raises(AgentOSError, match="already recorded"):
        decisions.report_outcome(record.decision_id, "actually, something else")


# ----------------------------------------------------------- standing orders


def test_only_a_human_may_issue_a_standing_order(decisions: DecisionGateway) -> None:
    with pytest.raises(AuthorityExceeded, match="not a Human"):
        decisions.manage_standing_order(
            "issue", "so-1", actor_id=AGENT, tenant_id=TENANT, scope={"adjust"}, duration=timedelta(days=7)
        )


def test_a_standing_order_may_not_exceed_thirty_days(decisions: DecisionGateway) -> None:
    """11 rule 11."""
    with pytest.raises(ValidationError, match="30 days"):
        decisions.manage_standing_order(
            "issue", "so-1", actor_id=HUMAN, tenant_id=TENANT, scope={"adjust"}, duration=timedelta(days=31)
        )


def test_a_standing_order_pre_authorizes_a_scoped_class_c_decision(decisions: DecisionGateway, token: str) -> None:
    decisions.manage_standing_order(
        "issue",
        "so-1",
        actor_id=HUMAN,
        tenant_id=TENANT,
        scope={"adjust the pricing"},
        budget_ceiling=100.0,
        max_risk=RiskClass.MODERATE,
        duration=timedelta(days=7),
    )
    record = decisions.propose(
        token,
        make_proposal(
            scope=Scope.BUSINESS,
            evidence_refs=evidence(confidence=0.95),
            standing_order_ref="so-1",
        ),
    )
    assert record.state == DecisionState.APPROVED
    assert record.authorized_by == HUMAN


def test_an_invocation_outside_scope_escalates(decisions: DecisionGateway, token: str) -> None:
    decisions.manage_standing_order(
        "issue",
        "so-1",
        actor_id=HUMAN,
        tenant_id=TENANT,
        scope={"something else entirely"},
        budget_ceiling=100.0,
        duration=timedelta(days=7),
    )
    record = decisions.propose(
        token,
        make_proposal(scope=Scope.BUSINESS, evidence_refs=evidence(confidence=0.95), standing_order_ref="so-1"),
    )
    assert record.state == DecisionState.ESCALATED


def test_an_invocation_over_budget_escalates(decisions: DecisionGateway, token: str) -> None:
    decisions.manage_standing_order(
        "issue",
        "so-1",
        actor_id=HUMAN,
        tenant_id=TENANT,
        scope={"adjust the pricing"},
        budget_ceiling=1.0,
        duration=timedelta(days=7),
    )
    record = decisions.propose(
        token,
        make_proposal(
            scope=Scope.BUSINESS,
            evidence_refs=evidence(confidence=0.95),
            standing_order_ref="so-1",
            options=(null_option(), acting_option(cost=50.0), acting_option("b", cost=40.0, value=0.5)),
        ),
    )
    assert record.state == DecisionState.ESCALATED


def test_a_standing_order_cannot_pre_authorize_class_d(decisions: DecisionGateway, token: str) -> None:
    """11.14.2 — standing orders cover scoped Class C only; Class D is human-only."""
    decisions.manage_standing_order(
        "issue",
        "so-1",
        actor_id=HUMAN,
        tenant_id=TENANT,
        scope={"adjust the pricing"},
        budget_ceiling=100000.0,
        max_risk=RiskClass.EXISTENTIAL,
        duration=timedelta(days=7),
    )
    record = decisions.propose(
        token,
        make_proposal(
            scope=Scope.PORTFOLIO,
            evidence_refs=evidence(count=3, confidence=0.99),
            standing_order_ref="so-1",
        ),
    )
    assert record.state == DecisionState.ESCALATED


def test_an_expired_standing_order_is_refused(decisions: DecisionGateway, token: str, clock) -> None:
    decisions.manage_standing_order(
        "issue",
        "so-1",
        actor_id=HUMAN,
        tenant_id=TENANT,
        scope={"adjust the pricing"},
        budget_ceiling=100.0,
        duration=timedelta(days=7),
    )
    clock.advance(timedelta(days=8))
    with pytest.raises(StandingOrderViolation, match="expired"):
        decisions.standing_orders.validate_invocation(
            "so-1", make_proposal(scope=Scope.BUSINESS), DecisionClass.C_STRATEGIC
        )


def test_revocation_is_immediate(decisions: DecisionGateway) -> None:
    decisions.manage_standing_order(
        "issue", "so-1", actor_id=HUMAN, tenant_id=TENANT, scope={"adjust"}, duration=timedelta(days=7)
    )
    decisions.manage_standing_order("revoke", "so-1", actor_id=HUMAN)
    with pytest.raises(StandingOrderViolation, match="revoked"):
        decisions.standing_orders.validate_invocation(
            "so-1", make_proposal(summary="adjust things", scope=Scope.BUSINESS), DecisionClass.C_STRATEGIC
        )


def test_invocations_are_counted_for_drift_detection(decisions: DecisionGateway, token: str) -> None:
    """11.24.2 — drift detection watches for orders stretched beyond intent."""
    decisions.manage_standing_order(
        "issue",
        "so-1",
        actor_id=HUMAN,
        tenant_id=TENANT,
        scope={"adjust the pricing"},
        budget_ceiling=100.0,
        duration=timedelta(days=7),
    )
    for i in range(3):
        decisions.propose(
            token,
            make_proposal(
                summary=f"adjust the pricing table {i}",
                scope=Scope.BUSINESS,
                evidence_refs=evidence(confidence=0.95),
                standing_order_ref="so-1",
            ),
        )
    assert decisions.health()["governance"]["standing_order_invocations"] == 3


# -------------------------------------------------------- circuit breakers


def test_a_circuit_breaker_breach_stops_commitment_regardless_of_merit(decisions: DecisionGateway, token: str) -> None:
    """21B §18.15 guarantee 6 — local optimality does not override the portfolio.

    21B §18.9 makes the response "Rejected or escalated". From Approved,
    11.8.2 permits only Approved -> Rejected, so that is the edge taken; the
    ratified transition table is not widened to suit the response.
    """
    decisions.breaker.capital_at_risk_ceiling = 1.0
    record = decisions.propose(
        token,
        make_proposal(options=(null_option(), acting_option(cost=5.0), acting_option("b", cost=4.0, value=0.5))),
    )
    if record.state == DecisionState.UNDER_REVIEW:
        request = decisions.pending_approval()[0]
        decisions.respond(request.request_id, responder_id=HUMAN, response="approve")
    decisions.commit(record.decision_id, committer_id=AGENT)
    assert record.state == DecisionState.REJECTED


def test_a_tripped_breaker_blocks_every_commitment(decisions: DecisionGateway, token: str) -> None:
    decisions.breaker.trip()
    record = decisions.propose(token, make_proposal())
    decisions.commit(record.decision_id, committer_id=AGENT)
    assert record.state == DecisionState.REJECTED


def test_capital_is_released_on_reversal(decisions: DecisionGateway, token: str) -> None:
    record = decisions.propose(token, make_proposal())
    decisions.commit(record.decision_id, committer_id=AGENT)
    committed = decisions.breaker.capital_at_risk
    decisions.reverse(record.decision_id, requester_id=HUMAN, reason="undo")
    assert decisions.breaker.capital_at_risk < committed


# ----------------------------------------------------- overrides and panic


def test_only_a_human_may_override(decisions: DecisionGateway, token: str) -> None:
    """11.9.3 — overrides are Class D actions."""
    record = decisions.propose(token, make_proposal())
    with pytest.raises(AuthorityExceeded):
        decisions.override(record.decision_id, AGENT, DecisionState.REJECTED, "no")


def test_an_override_is_logged_as_a_constitutional_exception(decisions: DecisionGateway, token: str) -> None:
    record = decisions.propose(token, make_proposal())
    decisions.override(record.decision_id, HUMAN, DecisionState.REJECTED, "operator judgement")
    entries = decisions.query_journal(decision_id=record.decision_id, action="override")
    assert entries[0]["constitutional_exception"] is True
    assert entries[0]["authority"] == "class_d"


def test_panic_defers_or_reverses_every_active_decision(decisions: DecisionGateway, token: str) -> None:
    """11.9.4 — Panic transitions all active decisions and halts new proposals."""
    reversible = decisions.propose(token, make_proposal(summary="reversible work"))
    decisions.commit(reversible.decision_id, committer_id=AGENT)
    proposed = decisions.propose(token, make_proposal(summary="still proposed"))

    affected = decisions.panic()
    assert reversible.state == DecisionState.REVERSED
    assert proposed.state == DecisionState.DEFERRED
    assert len(affected) == 2
    with pytest.raises(AgentOSError, match="Panic Protocol"):
        decisions.propose(token, make_proposal(summary="during panic"))


def test_only_a_human_resumes_after_panic(decisions: DecisionGateway, token: str) -> None:
    decisions.panic()
    with pytest.raises(AuthorityExceeded):
        decisions.resume(AGENT)
    decisions.resume(HUMAN)
    assert decisions.propose(token, make_proposal()).state == DecisionState.APPROVED


# ------------------------------------------------------------------- health


def test_health_reports_the_five_metric_families(decisions: DecisionGateway, token: str) -> None:
    record = decisions.propose(token, make_proposal())
    decisions.commit(record.decision_id, committer_id=AGENT)
    decisions.mark_executing(record.decision_id)
    decisions.report_outcome(record.decision_id, record.decision.expected_outcome)
    health = decisions.health()
    for family in ("velocity", "latency", "quality", "governance", "health"):
        assert family in health
    assert health["quality"]["outcome_divergence_rate"] == 0.0
    assert health["journal_intact"] is True


def test_confidence_calibration_is_exposed(decisions: DecisionGateway, token: str) -> None:
    """21B §18.11 / CIR-007 — predicted-versus-actual must be exposed, not just held."""
    assert decisions.health()["quality"]["confidence_calibration"] is None
    record = decisions.propose(token, make_proposal())
    decisions.commit(record.decision_id, committer_id=AGENT)
    decisions.mark_executing(record.decision_id)
    decisions.report_outcome(record.decision_id, "something entirely different")
    assert decisions.health()["quality"]["confidence_calibration"] is not None


def test_unknown_decision_lookup_raises(decisions: DecisionGateway) -> None:
    with pytest.raises(NotFoundError):
        decisions.get("dec-nope")


def test_dependencies_are_confined_to_the_adapter_module() -> None:
    """21B §18.6 — the permitted edges, in one file."""
    import pathlib

    import decision_gateway

    root = pathlib.Path(decision_gateway.__path__[0])
    importers = sorted(
        {
            path.name
            for path in root.glob("*.py")
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip().startswith(("import ", "from "))
            and any(m in line for m in ("security_gateway", "knowledge_gateway", "memory_gateway", "cost_manager"))
            and path.name != "__init__.py"
        }
    )
    assert importers == ["adapters.py"]
