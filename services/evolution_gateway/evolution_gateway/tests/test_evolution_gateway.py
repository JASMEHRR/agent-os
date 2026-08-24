"""Evolution Gateway conformance (19, per 21B §26).

**Construction authorized 2026-08-24** by G4 ruling on CIR-001.

The ruling authorized building this module. It did not, and could not, give
Evolution the authority `19.3` places elsewhere:

> **Evolution packages; it does not ratify.**

So the rule tested hardest here is an *absence*. There is no ratifying verb,
and the test asserting so is the one that would catch the most consequential
possible regression: a subsystem that could ratify its own proposals to change
the Constitution would have taken the authority the whole oversight plane
exists to hold.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from core.exceptions import AgentOSError, NotFoundError, ValidationError
from evolution_gateway import (
    CONSUMABLE_LEARNING_STATES,
    EVOLUTION_PIPELINE,
    PROPOSAL_TRANSITIONS,
    ArtifactClass,
    CompensationPlan,
    EvolutionGateway,
    ImpactAssessment,
    LearningEvidence,
    ProposalState,
    RecursionAnomaly,
    ratification_verbs,
)
from kernel.escalation import EscalationTrigger

TENANT = "tenant-alpha"
HUMAN = "human-sovereign"
ARCHITECT = "agent-architect"


class Clock:
    def __init__(self) -> None:
        self.now = datetime(2026, 8, 24, 12, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        self.now += timedelta(milliseconds=5)
        return self.now


class Governance:
    """Governance's intake. Receives, acknowledges, and decides elsewhere."""

    def __init__(self) -> None:
        self.received: list[tuple[str, dict[str, Any]]] = []

    def receive(self, proposal_id: str, package: Any) -> str:
        self.received.append((proposal_id, dict(package)))
        return f"gov-ack-{proposal_id}"


@pytest.fixture
def alerts() -> list[str]:
    return []


@pytest.fixture
def escalations() -> list[tuple[EscalationTrigger, str]]:
    return []


@pytest.fixture
def governance() -> Governance:
    return Governance()


@pytest.fixture
def evolution(
    governance: Governance, alerts: list[str], escalations: list[tuple[EscalationTrigger, str]]
) -> EvolutionGateway:
    gateway = EvolutionGateway(
        escalate=lambda trigger, detail: escalations.append((trigger, detail)),
        alert_human=alerts.append,
        now=Clock(),
    )
    gateway.register_governance(governance)
    return gateway


def confirmed(entry_id: str = "le-1") -> LearningEvidence:
    return LearningEvidence(entry_id=entry_id, state="confirmed", subject="agent-analyst", confirmed_improvement=0.4)


def impact(**overrides: Any) -> ImpactAssessment:
    defaults: dict[str, Any] = {
        "modules_affected": ("agent_runtime", "workflow_engine"),
        "non_violable_rules_touched": (),
        "reversible": True,
        "detail": "raises the default retry ceiling across two modules",
    }
    defaults.update(overrides)
    return ImpactAssessment(**defaults)


def compensation(**overrides: Any) -> CompensationPlan:
    defaults: dict[str, Any] = {
        "reversal_steps": ("restore the previous retry ceiling", "re-run the affected workflows"),
        "tested": True,
        "estimated_reversal_cost": 12.0,
    }
    defaults.update(overrides)
    return CompensationPlan(**defaults)


def drafted(evolution: EvolutionGateway, proposal_id: str = "prop-1", **overrides: Any) -> Any:
    defaults: dict[str, Any] = {
        "proposal_id": proposal_id,
        "tenant_id": TENANT,
        "artifact_class": ArtifactClass.A2_ARCHITECTURAL,
        "target_subsystem": "agent_runtime",
        "statement": "raise the default retry ceiling from two to four",
        "rationale": "three confirmed learning entries show the provider recovers within four attempts",
        "evidence": [confirmed()],
        "drafted_by": ARCHITECT,
    }
    defaults.update(overrides)
    return evolution.draft(**defaults)


def packaged(evolution: EvolutionGateway, proposal_id: str = "prop-1", **overrides: Any) -> Any:
    drafted(evolution, proposal_id, **overrides)
    evolution.analyse_impact(proposal_id, impact())
    evolution.frame_compensation(proposal_id, compensation())
    evolution.check_recursion(proposal_id)
    return evolution.package(proposal_id)


# ------------------------------------------------ The absence that defines it


def test_evolution_has_no_ratifying_verb() -> None:
    """19.3 — "Evolution packages; it does not ratify."

    The most consequential regression this repository could suffer would be a
    subsystem that could ratify its own proposals to change the Constitution.
    It would have taken the authority the entire oversight plane exists to
    hold, and it would look like a convenience method.
    """
    assert ratification_verbs() == ()
    forbidden = {"ratify", "approve", "amend", "enact", "adopt", "commit_amendment", "enforce"}
    present = {name for name in dir(EvolutionGateway) if not name.startswith("_")}
    assert not (forbidden & present), f"Evolution acquired ratification authority: {forbidden & present}"


def test_the_ruling_authorized_construction_and_not_authority(
    evolution: EvolutionGateway,
) -> None:
    """CIR-001's ruling unblocked building this module. It changed nothing about
    who may ratify, and the health surface says so."""
    health = evolution.health()
    assert health["construction_authorized"] is True
    assert health["ratification_authority"] == "governance_gateway"
    assert health["ratified_by_evolution"] == 0


def test_the_pipeline_ends_at_handoff(evolution: EvolutionGateway) -> None:
    assert evolution.pipeline() == EVOLUTION_PIPELINE
    assert EVOLUTION_PIPELINE[-1] == "packaging_and_handoff"


def test_no_state_transition_reaches_ratified_except_from_handed_off() -> None:
    """Structural: Ratified is reachable only after Governance has the proposal.

    A path from Packaged straight to Ratified would let a proposal be ratified
    without ever leaving Evolution.
    """
    reaching = [state for state, targets in PROPOSAL_TRANSITIONS.items() if ProposalState.RATIFIED in targets]
    assert reaching == [ProposalState.HANDED_OFF]


# ----------------------------------------------------- Evidence gate (19.5)


def test_only_confirmed_learning_is_consumable(evolution: EvolutionGateway) -> None:
    """19.5 / 21B §26.6 — never Proposed or Adopted-but-unconfirmed.

    An unconfirmed entry has not been measured. Amending a standing bound on
    evidence that might still be refuted is exactly the failure this prevents.
    """
    assert evolution.consumes_learning_state("confirmed")
    for state in ("adopted", "propagated", "validated", "refuted"):
        assert not evolution.consumes_learning_state(state)
    assert CONSUMABLE_LEARNING_STATES == frozenset({"confirmed"})


def test_a_proposal_on_unconfirmed_evidence_is_refused(evolution: EvolutionGateway) -> None:
    unconfirmed = LearningEvidence(entry_id="le-2", state="adopted", subject="agent-analyst", confirmed_improvement=0.0)
    with pytest.raises(ValidationError, match="no Confirmed learning entry"):
        drafted(evolution, evidence=[unconfirmed])


def test_the_monitor_filters_rather_than_raises(evolution: EvolutionGateway) -> None:
    """An unconfirmed entry is not an error; it is not yet evidence.

    It may become evidence later, which is the whole reason measurement windows
    exist, so filtering is the honest response and raising would not be.
    """
    mixed = [confirmed("le-1"), LearningEvidence("le-2", "adopted", "x", 0.0)]
    assert [e.entry_id for e in evolution.monitor_signals(mixed)] == ["le-1"]


def test_an_anonymous_proposal_is_refused(evolution: EvolutionGateway) -> None:
    with pytest.raises(ValidationError, match="anonymous proposal"):
        drafted(evolution, drafted_by="")


def test_a_proposal_without_a_rationale_is_refused(evolution: EvolutionGateway) -> None:
    with pytest.raises(ValidationError, match="must say why"):
        drafted(evolution, rationale="   ")


# ------------------------------------------------ Compensation gate (19.13)


def test_compensation_is_framed_before_packaging(evolution: EvolutionGateway) -> None:
    assert evolution.compensation_precedes_packaging()


def test_an_untested_rollback_plan_is_refused(evolution: EvolutionGateway) -> None:
    """19.13 asks for rollback capability; an untested plan is a description of one."""
    drafted(evolution)
    evolution.analyse_impact("prop-1", impact())
    with pytest.raises(ValidationError, match="exercised"):
        evolution.frame_compensation("prop-1", compensation(tested=False))


def test_an_empty_rollback_plan_is_refused(evolution: EvolutionGateway) -> None:
    drafted(evolution)
    evolution.analyse_impact("prop-1", impact())
    with pytest.raises(ValidationError, match="credible compensation"):
        evolution.frame_compensation("prop-1", compensation(reversal_steps=()))


def test_a_proposal_cannot_skip_impact_analysis(evolution: EvolutionGateway) -> None:
    drafted(evolution)
    with pytest.raises(AgentOSError, match="expected one of"):
        evolution.frame_compensation("prop-1", compensation())


# --------------------------------------------------- Recursion Guard (19.14)


def test_a_proposal_targeting_evolution_is_quarantined_and_escalated(
    evolution: EvolutionGateway, alerts: list[str], escalations: list[tuple[EscalationTrigger, str]]
) -> None:
    """19.14 — a self-referential proposal never reaches Governance.

    If it did, it would arrive carrying Evolution's own endorsement of a change
    to Evolution's own bounds, which is an endorsement Governance has no way to
    discount.
    """
    drafted(evolution, target_subsystem="evolution_gateway")
    evolution.analyse_impact("prop-1", impact())
    evolution.frame_compensation("prop-1", compensation())
    with pytest.raises(RecursionAnomaly, match="Recursion Anomaly"):
        evolution.check_recursion("prop-1")

    assert evolution.get("prop-1").state == ProposalState.QUARANTINED
    assert alerts and escalations
    assert escalations[0][0] == EscalationTrigger.AUTHORITY_BYPASS


def test_a_proposal_that_changes_evolutions_bounds_in_prose_is_caught(
    evolution: EvolutionGateway,
) -> None:
    """The subtle version: an innocent target, self-modification in the text."""
    drafted(
        evolution,
        target_subsystem="workflow_engine",
        statement="relax the recursion guard so proposals move faster",
    )
    evolution.analyse_impact("prop-1", impact())
    evolution.frame_compensation("prop-1", compensation())
    with pytest.raises(RecursionAnomaly):
        evolution.check_recursion("prop-1")


def test_a_quarantined_proposal_cannot_be_packaged(evolution: EvolutionGateway) -> None:
    drafted(evolution, target_subsystem="evolution")
    evolution.analyse_impact("prop-1", impact())
    evolution.frame_compensation("prop-1", compensation())
    with pytest.raises(RecursionAnomaly):
        evolution.check_recursion("prop-1")
    with pytest.raises(AgentOSError, match="expected one of"):
        evolution.package("prop-1")


def test_the_recursion_guard_precedes_packaging(evolution: EvolutionGateway) -> None:
    assert evolution.recursion_guard_precedes_packaging()


def test_an_ordinary_proposal_passes_the_guard(evolution: EvolutionGateway) -> None:
    drafted(evolution)
    evolution.analyse_impact("prop-1", impact())
    evolution.frame_compensation("prop-1", compensation())
    assert evolution.check_recursion("prop-1").state == ProposalState.RECURSION_CHECKED


# ------------------------------------------------------ Packaging (19.16.2)


def test_the_package_is_complete(evolution: EvolutionGateway) -> None:
    """19.16.2 — "Evolution ensures the package is complete".

    Governance receives something it can rule on, or it receives nothing.
    """
    package = packaged(evolution)
    assert set(package) >= {
        "proposal_id",
        "statement",
        "rationale",
        "evidence",
        "modules_affected",
        "non_violable_rules_touched",
        "compensation_steps",
        "compensation_tested",
        "requires_human_ratification",
        "ratification_authority",
    }
    assert package["ratification_authority"] == "governance_gateway"


def test_an_a4_package_says_it_needs_human_ratification(evolution: EvolutionGateway) -> None:
    """19.36.2 — stated in the package rather than left for Governance to infer."""
    package = packaged(evolution, artifact_class=ArtifactClass.A4_CONSTITUTIONAL)
    assert package["requires_human_ratification"] is True
    assert ArtifactClass.A4_CONSTITUTIONAL.is_human_only


def test_a_lower_class_package_does_not_claim_to_need_a_sovereign(
    evolution: EvolutionGateway,
) -> None:
    assert packaged(evolution)["requires_human_ratification"] is False


# --------------------------------------------------------- Handoff (19.16.2)


def test_handoff_delivers_to_governance_and_relinquishes(evolution: EvolutionGateway, governance: Governance) -> None:
    packaged(evolution)
    acknowledgement = evolution.hand_off("prop-1")
    assert acknowledgement == "gov-ack-prop-1"
    assert governance.received[0][0] == "prop-1"
    assert evolution.get("prop-1").state == ProposalState.HANDED_OFF


def test_handoff_without_a_registered_governance_is_refused() -> None:
    """19.3 gives ratification to Governance; with no intake there is nowhere to go."""
    orphan = EvolutionGateway(now=Clock())
    assert hasattr(orphan, "register_governance"), "the intake exists and was deliberately not registered"
    with pytest.raises(NotFoundError, match="nowhere to hand this to"):
        orphan.hand_off("prop-1")


def test_governance_decides_and_evolution_records(evolution: EvolutionGateway, governance: Governance) -> None:
    """The outcome arrives back. Evolution writes it down and produces nothing."""
    packaged(evolution)
    evolution.hand_off("prop-1")
    record = evolution.record_outcome("prop-1", "ratified", "adopted at G3")
    assert record.state == ProposalState.RATIFIED
    assert record.outcome == "ratified"
    assert evolution.health()["ratified_by_evolution"] == 0


def test_a_rejected_proposal_keeps_its_evidence(evolution: EvolutionGateway, governance: Governance) -> None:
    """21B §26.8 — the outcome is appended, preserving history for a re-proposal."""
    packaged(evolution)
    evolution.hand_off("prop-1")
    record = evolution.record_outcome("prop-1", "rejected", "the evidence predates the provider change")
    assert record.state == ProposalState.REJECTED
    assert len(record.evidence) == 1
    assert record.rationale
    assert record.outcome_justification


def test_a_deferred_proposal_can_be_handed_off_again(evolution: EvolutionGateway, governance: Governance) -> None:
    packaged(evolution)
    evolution.hand_off("prop-1")
    evolution.record_outcome("prop-1", "deferred", "awaiting the next review cycle")
    assert evolution.get("prop-1").state == ProposalState.DEFERRED
    assert evolution.hand_off("prop-1")


def test_an_unknown_outcome_is_refused(evolution: EvolutionGateway) -> None:
    packaged(evolution)
    evolution.hand_off("prop-1")
    with pytest.raises(ValidationError, match="not a Governance outcome"):
        evolution.record_outcome("prop-1", "approved-ish")


# -------------------------------------------------------------- Housekeeping


def test_a_duplicate_proposal_id_is_refused(evolution: EvolutionGateway) -> None:
    drafted(evolution)
    with pytest.raises(AgentOSError, match="already exists"):
        drafted(evolution)


def test_an_unknown_proposal_is_a_not_found(evolution: EvolutionGateway) -> None:
    with pytest.raises(NotFoundError):
        evolution.get("prop-nobody")


def test_the_journal_records_the_whole_pipeline(evolution: EvolutionGateway, governance: Governance) -> None:
    packaged(evolution)
    evolution.hand_off("prop-1")
    evolution.record_outcome("prop-1", "ratified")
    payloads = [evolution.journal[i].payload for i in range(len(evolution.journal))]
    assert [str(p["action"]) for p in payloads] == [
        "drafted",
        "impact_analysed",
        "compensation_framed",
        "recursion_checked",
        "packaged",
        "handed_off",
        "outcome_recorded",
    ]
    assert evolution.health()["journal_intact"]


def test_health_reports_the_pipeline_and_the_ruling(evolution: EvolutionGateway) -> None:
    packaged(evolution)
    health = evolution.health()
    assert health["proposals"] == 1
    assert health["pipeline"] == list(EVOLUTION_PIPELINE)
    assert "resolved" in health["cir_001"]
    assert not evolution.is_blocked()
