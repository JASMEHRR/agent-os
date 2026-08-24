"""Evolution Gateway — how the system changes itself deliberately (19, per 21B §26).

**Construction authorized 2026-08-24** by G4 ruling on CIR-001
(`docs/rulings/CIR-001.md`).

`19.2` draws the line against Learning: Learning adapts behaviour **within**
standing constitutional and architectural bounds; Evolution proposes changes
**to** those bounds.

`19.3` is the sentence this whole module is shaped around, and the ruling
changed nothing about it:

> **Evolution packages; it does not ratify.**

The authority to change the Constitution belongs to Governance and, beyond it,
to the sovereigns Governance answers to. So there is **no ratifying verb here**,
a test asserts there never will be, and `hand_off` is the last thing this module
does with a proposal. That absence is what resolves the Evolution/Governance
circular dependency: the edge from Evolution back to ratification does not
exist, so 19.16.2's handoff is unidirectional by construction.

The pipeline of 21B §26.4, in order, with two orderings that are load-bearing:

* **the Recursion Guard runs before packaging** (19.14) — a self-referential
  proposal that reached Governance would arrive carrying Evolution's own
  endorsement of a change to Evolution's own bounds;
* **compensation is framed before packaging** (19.13) — a proposal packaged
  without a rollback plan is a proposal nobody can decline safely.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Protocol

from core.exceptions import AgentOSError, NotFoundError, ValidationError
from kernel.escalation import EscalationTrigger
from kernel.journal import ImmutableJournal
from kernel.lifecycle import LifecycleStateMachine
from kernel.signals import SignalEmitter, SignalType

#: Retained for the record; nothing raises it since the ruling.
CIR_001 = (
    "CIR-001 was resolved on 2026-08-24 by G4 human sovereign ruling. Construction of the "
    "Evolution Gateway is authorized. See docs/rulings/CIR-001.md."
)


class ConstructionBlocked(AgentOSError):
    """Retained for compatibility; nothing raises it since the CIR-001 ruling."""


class ArtifactClass(StrEnum):
    """What an evolutionary artifact proposes to change (19.9).

    A4 is constitutional amendment: human-only and undelegable (19.36.2), and
    the class at which Evolution's own inability to ratify matters most.
    """

    A1_OPERATIONAL = "a1_operational"
    A2_ARCHITECTURAL = "a2_architectural"
    A3_STRUCTURAL = "a3_structural"
    A4_CONSTITUTIONAL = "a4_constitutional"

    @property
    def is_human_only(self) -> bool:
        return self is ArtifactClass.A4_CONSTITUTIONAL


class ProposalState(StrEnum):
    """The pipeline of 21B §26.4, as states.

    A rejected proposal is not deleted: 21B §26.8 requires the outcome appended
    to the same record, preserving history for any future re-proposal.
    """

    DETECTED = "detected"
    DRAFTED = "drafted"
    IMPACT_ANALYSED = "impact_analysed"
    COMPENSATION_FRAMED = "compensation_framed"
    RECURSION_CHECKED = "recursion_checked"
    PACKAGED = "packaged"
    HANDED_OFF = "handed_off"
    #: Governance's to set. Evolution records the outcome and does not produce it.
    RATIFIED = "ratified"
    REJECTED = "rejected"
    DEFERRED = "deferred"
    ABANDONED = "abandoned"
    QUARANTINED = "quarantined"


PROPOSAL_TRANSITIONS: dict[str, set[str]] = {
    ProposalState.DETECTED: {ProposalState.DRAFTED, ProposalState.ABANDONED},
    ProposalState.DRAFTED: {ProposalState.IMPACT_ANALYSED, ProposalState.ABANDONED},
    ProposalState.IMPACT_ANALYSED: {ProposalState.COMPENSATION_FRAMED, ProposalState.ABANDONED},
    # Quarantine is reachable from here because the Recursion Guard runs at
    # this state. Without the edge the guard could detect a self-referential
    # proposal and not act on it, which is the worst of both.
    ProposalState.COMPENSATION_FRAMED: {
        ProposalState.RECURSION_CHECKED,
        ProposalState.QUARANTINED,
        ProposalState.ABANDONED,
    },
    ProposalState.RECURSION_CHECKED: {ProposalState.PACKAGED, ProposalState.QUARANTINED},
    # A deferred proposal returns to Governance; the table permitted it and
    # `hand_off` did not, so a deferral was terminal in practice.
    ProposalState.PACKAGED: {ProposalState.HANDED_OFF, ProposalState.ABANDONED},
    # Everything past handoff is Governance's decision, arriving back as a report.
    ProposalState.HANDED_OFF: {
        ProposalState.RATIFIED,
        ProposalState.REJECTED,
        ProposalState.DEFERRED,
    },
    ProposalState.RATIFIED: set(),
    ProposalState.REJECTED: {ProposalState.ABANDONED},
    ProposalState.DEFERRED: {ProposalState.HANDED_OFF, ProposalState.ABANDONED},
    ProposalState.ABANDONED: set(),
    ProposalState.QUARANTINED: {ProposalState.ABANDONED},
}

#: 21B §26.4's pipeline, in order.
EVOLUTION_PIPELINE: tuple[str, ...] = (
    "signal_monitor",
    "proposal_drafter",
    "impact_analyzer",
    "compensation_framer",
    "recursion_guard",
    "packaging_and_handoff",
)

#: 19.5 / 21B §26.6 — Evolution consumes **only** Confirmed learning entries,
#: "never Proposed or Adopted-but-unconfirmed". An unconfirmed entry has not
#: been measured, and amending a standing bound on evidence that might still be
#: refuted is the failure this gate prevents.
CONSUMABLE_LEARNING_STATES: frozenset[str] = frozenset({"confirmed"})

#: Names by which Evolution can be addressed. A proposal targeting any of them
#: is self-referential (19.14) and never reaches Governance carrying Evolution's
#: own endorsement.
SELF_IDENTIFIERS = frozenset(
    {"evolution", "evolutiongateway", "evolutionplane", "19", "doc19", "document19", "selfevolution"}
)


class RecursionAnomaly(AgentOSError):
    """19.14 — a proposal targeting Evolution's own bounds. Escalated, never packaged."""


class GovernanceIntake(Protocol):
    """Governance's proposal intake (21B §26.5).

    Deliberately one method. Evolution hands over and retains no authority: a
    wider interface would be a way back in.
    """

    def receive(self, proposal_id: str, package: Mapping[str, Any]) -> str: ...


@dataclass(frozen=True)
class LearningEvidence:
    """A Confirmed learning entry, cited as the basis for a proposal (19.5)."""

    entry_id: str
    state: str
    subject: str
    confirmed_improvement: float


@dataclass(frozen=True)
class ImpactAssessment:
    """21B §26.3's Impact Analyzer output, traced across the dependency graph."""

    modules_affected: tuple[str, ...]
    non_violable_rules_touched: tuple[str, ...]
    reversible: bool
    detail: str

    @property
    def touches_a_non_violable_rule(self) -> bool:
        return bool(self.non_violable_rules_touched)


@dataclass(frozen=True)
class CompensationPlan:
    """19.13 — every proposal carries a rollback before it is packaged."""

    reversal_steps: tuple[str, ...]
    tested: bool
    estimated_reversal_cost: float

    @property
    def is_credible(self) -> bool:
        return bool(self.reversal_steps) and self.tested


@dataclass
class Proposal:
    """One evolutionary artifact moving through the pipeline."""

    proposal_id: str
    tenant_id: str
    artifact_class: ArtifactClass
    target_subsystem: str
    statement: str
    rationale: str
    evidence: tuple[LearningEvidence, ...]
    drafted_by: str
    state: ProposalState = ProposalState.DETECTED
    impact: ImpactAssessment | None = None
    compensation: CompensationPlan | None = None
    packaged_at: datetime | None = None
    handed_off_at: datetime | None = None
    #: Governance's outcome, recorded when it reports back. Never set here.
    outcome: str = ""
    outcome_justification: str = ""
    quarantine_reason: str = ""


@dataclass
class EvolutionGateway:
    """Layer 6, the deepest module. Packages change; never enacts it."""

    signals: SignalEmitter = field(default_factory=lambda: SignalEmitter(source_identity="evolution_gateway"))
    escalate: Callable[[EscalationTrigger, str], None] = field(default=lambda trigger, detail: None)
    alert_human: Callable[[str], None] = field(default=lambda detail: None)
    now: Callable[[], datetime] = field(default=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        self.journal = ImmutableJournal()
        self._proposals: dict[str, Proposal] = {}
        self._intake: GovernanceIntake | None = None

    def register_governance(self, intake: GovernanceIntake) -> None:
        """The one place a proposal can go. 19.16.2's unidirectional handoff."""
        self._intake = intake

    # ------------------------------------------------------------- Pipeline

    def monitor_signals(self, entries: Sequence[LearningEvidence]) -> list[LearningEvidence]:
        """Signal Monitor (19.5) — Confirmed entries only.

        Filters rather than raises: an unconfirmed entry is not an error, it is
        simply not yet evidence. It may become evidence later, which is the
        whole reason measurement windows exist.
        """
        return [e for e in entries if e.state.lower() in CONSUMABLE_LEARNING_STATES]

    def draft(
        self,
        proposal_id: str,
        tenant_id: str,
        artifact_class: ArtifactClass,
        target_subsystem: str,
        statement: str,
        rationale: str,
        evidence: Sequence[LearningEvidence],
        drafted_by: str,
    ) -> Proposal:
        """Proposal Drafter (19.9). Refuses to draft on unconfirmed evidence."""
        if proposal_id in self._proposals:
            raise AgentOSError(f"proposal '{proposal_id}' already exists")
        if not drafted_by:
            raise ValidationError("a proposal requires an author; anonymous proposal formation is prohibited")
        usable = self.monitor_signals(evidence)
        if not usable:
            raise ValidationError(
                f"proposal '{proposal_id}' cites no Confirmed learning entry; 19.5 admits only Confirmed "
                "evidence, because an unconfirmed entry may still be refuted"
            )
        if not rationale.strip():
            raise ValidationError("a proposal to change a standing bound must say why")

        proposal = Proposal(
            proposal_id=proposal_id,
            tenant_id=tenant_id,
            artifact_class=artifact_class,
            target_subsystem=target_subsystem,
            statement=statement,
            rationale=rationale,
            evidence=tuple(usable),
            drafted_by=drafted_by,
            state=ProposalState.DETECTED,
        )
        self._proposals[proposal_id] = proposal
        self._transition(proposal, ProposalState.DRAFTED)
        self._record("drafted", proposal_id=proposal_id, artifact_class=artifact_class.value, by=drafted_by)
        return proposal

    def analyse_impact(self, proposal_id: str, assessment: ImpactAssessment) -> Proposal:
        """Impact Analyzer (21B §26.3), tracing across the dependency graph."""
        proposal = self.get(proposal_id)
        self._require(proposal, ProposalState.DRAFTED)
        proposal.impact = assessment
        self._transition(proposal, ProposalState.IMPACT_ANALYSED)
        self._record(
            "impact_analysed",
            proposal_id=proposal_id,
            modules=len(assessment.modules_affected),
            non_violable=len(assessment.non_violable_rules_touched),
        )
        return proposal

    def frame_compensation(self, proposal_id: str, plan: CompensationPlan) -> Proposal:
        """19.13 — before packaging, always.

        A plan that lists no steps or was never tested is refused. 19.13 asks
        for rollback capability, and an untested plan is a description of one.
        """
        proposal = self.get(proposal_id)
        self._require(proposal, ProposalState.IMPACT_ANALYSED)
        if not plan.is_credible:
            raise ValidationError(
                f"proposal '{proposal_id}' has no credible compensation: 19.13 requires a rollback plan "
                "that exists and has been exercised, and an untested plan is a description of one"
            )
        proposal.compensation = plan
        self._transition(proposal, ProposalState.COMPENSATION_FRAMED)
        self._record("compensation_framed", proposal_id=proposal_id, steps=len(plan.reversal_steps))
        return proposal

    def check_recursion(self, proposal_id: str) -> Proposal:
        """Recursion Guard (19.14), mirroring 13's self-referential learning guard.

        Fails closed. A proposal targeting Evolution's own bounds is quarantined
        and escalated, never packaged — because packaged is the state in which
        it would reach Governance carrying Evolution's endorsement of a change
        to Evolution.
        """
        proposal = self.get(proposal_id)
        self._require(proposal, ProposalState.COMPENSATION_FRAMED)
        normalized = "".join(c for c in proposal.target_subsystem.lower() if c.isalnum())
        text = f"{proposal.statement} {proposal.rationale}".lower()

        reason = ""
        if normalized in SELF_IDENTIFIERS:
            reason = f"target '{proposal.target_subsystem}' names the Evolution subsystem"
        elif "recursion guard" in text or "evolution gateway" in text:
            reason = "the proposal would change Evolution's own bounds (19.14)"

        if reason:
            self._transition(proposal, ProposalState.QUARANTINED)
            proposal.quarantine_reason = reason
            detail = f"Recursion Anomaly (19.14) on '{proposal_id}': {reason}"
            self._record("recursion_quarantined", proposal_id=proposal_id, reason=reason)
            self.alert_human(detail)
            self.escalate(EscalationTrigger.AUTHORITY_BYPASS, detail)
            raise RecursionAnomaly(detail)

        self._transition(proposal, ProposalState.RECURSION_CHECKED)
        self._record("recursion_checked", proposal_id=proposal_id)
        return proposal

    def package(self, proposal_id: str) -> Mapping[str, Any]:
        """Packaging (19.16.2) — "Evolution ensures the package is complete".

        Completeness is checked here rather than trusted: Governance receives a
        package it can rule on, or it receives nothing.
        """
        proposal = self.get(proposal_id)
        self._require(proposal, ProposalState.RECURSION_CHECKED)
        if proposal.impact is None or proposal.compensation is None:
            raise ValidationError(f"proposal '{proposal_id}' is incomplete; it cannot be packaged")

        package = {
            "proposal_id": proposal.proposal_id,
            "artifact_class": proposal.artifact_class.value,
            "target_subsystem": proposal.target_subsystem,
            "statement": proposal.statement,
            "rationale": proposal.rationale,
            "evidence": [e.entry_id for e in proposal.evidence],
            "modules_affected": list(proposal.impact.modules_affected),
            "non_violable_rules_touched": list(proposal.impact.non_violable_rules_touched),
            "reversible": proposal.impact.reversible,
            "compensation_steps": list(proposal.compensation.reversal_steps),
            "compensation_tested": proposal.compensation.tested,
            # 19.36.2 — A4 is human-only, and the package says so rather than
            # leaving Governance to work it out from the class.
            "requires_human_ratification": proposal.artifact_class.is_human_only,
            "ratification_authority": "governance_gateway",
        }
        proposal.packaged_at = self.now()
        self._transition(proposal, ProposalState.PACKAGED)
        self._record("packaged", proposal_id=proposal_id)
        return package

    def hand_off(self, proposal_id: str) -> str:
        """The last thing this module does with a proposal (19.16.2).

        Delivers to Governance and relinquishes. There is no verb after this
        one that touches the proposal's substance — only `record_outcome`,
        which writes down what Governance decided.
        """
        if self._intake is None:
            raise NotFoundError(
                "no Governance intake is registered; 19.3 gives ratification to Governance and there is "
                "nowhere to hand this to"
            )
        proposal = self.get(proposal_id)
        self._require(proposal, ProposalState.PACKAGED, ProposalState.DEFERRED)
        package = {
            "proposal_id": proposal_id,
            "artifact_class": proposal.artifact_class.value,
            "target_subsystem": proposal.target_subsystem,
            "statement": proposal.statement,
        }
        acknowledgement = self._intake.receive(proposal_id, package)
        proposal.handed_off_at = self.now()
        self._transition(proposal, ProposalState.HANDED_OFF)
        self._record("handed_off", proposal_id=proposal_id, acknowledgement=acknowledgement)
        self.signals.emit(
            SignalType.EVENT,
            "evolution.proposal.handed_off",
            proposal.tenant_id,
            proposal_id=proposal_id,
            artifact_class=proposal.artifact_class.value,
        )
        return acknowledgement

    def record_outcome(self, proposal_id: str, outcome: str, justification: str = "") -> Proposal:
        """Governance's decision, arriving back (21B §26.8).

        Appended, never substituted: a rejected proposal keeps its evidence and
        its rationale so a future re-proposal starts from what was learned
        rather than from nothing.
        """
        proposal = self.get(proposal_id)
        self._require(proposal, ProposalState.HANDED_OFF, ProposalState.DEFERRED)
        target = {
            "ratified": ProposalState.RATIFIED,
            "rejected": ProposalState.REJECTED,
            "deferred": ProposalState.DEFERRED,
        }.get(outcome.lower())
        if target is None:
            raise ValidationError(f"'{outcome}' is not a Governance outcome")
        proposal.outcome = outcome.lower()
        proposal.outcome_justification = justification
        self._transition(proposal, target)
        self._record("outcome_recorded", proposal_id=proposal_id, outcome=outcome.lower())
        return proposal

    # ---------------------------------------------------------------- Query

    def get(self, proposal_id: str) -> Proposal:
        proposal = self._proposals.get(proposal_id)
        if proposal is None:
            raise NotFoundError(f"proposal '{proposal_id}' does not exist")
        return proposal

    def proposals(self, state: ProposalState | None = None) -> list[Proposal]:
        if state is None:
            return list(self._proposals.values())
        return [p for p in self._proposals.values() if p.state == state]

    def pipeline(self) -> tuple[str, ...]:
        return EVOLUTION_PIPELINE

    def consumes_learning_state(self, state: str) -> bool:
        return state.lower() in CONSUMABLE_LEARNING_STATES

    def recursion_guard_precedes_packaging(self) -> bool:
        return EVOLUTION_PIPELINE.index("recursion_guard") < EVOLUTION_PIPELINE.index("packaging_and_handoff")

    def compensation_precedes_packaging(self) -> bool:
        return EVOLUTION_PIPELINE.index("compensation_framer") < EVOLUTION_PIPELINE.index("packaging_and_handoff")

    def is_blocked(self) -> bool:
        return False

    def blocker(self) -> str:
        return CIR_001

    def health(self) -> Mapping[str, Any]:
        proposals = list(self._proposals.values())
        by_state: dict[str, int] = {}
        for proposal in proposals:
            by_state[proposal.state.value] = by_state.get(proposal.state.value, 0) + 1
        handed = [p for p in proposals if p.handed_off_at is not None]
        return {
            "status": "constructed",
            "cir_001": "resolved 2026-08-24 by G4 ruling",
            "construction_authorized": True,
            "pipeline": list(EVOLUTION_PIPELINE),
            "proposals": len(proposals),
            "by_state": by_state,
            "handed_off": len(handed),
            "ratified": by_state.get(ProposalState.RATIFIED.value, 0),
            "recursion_quarantined": by_state.get(ProposalState.QUARANTINED.value, 0),
            # Structurally zero: this Gateway has no ratifying verb.
            "ratified_by_evolution": 0,
            "ratification_authority": "governance_gateway",
            "journal_entries": len(self.journal),
            "journal_intact": self.journal.verify_chain(),
        }

    # ------------------------------------------------------------ Internals

    def _require(self, proposal: Proposal, *allowed: ProposalState) -> None:
        if proposal.state not in allowed:
            raise AgentOSError(
                f"proposal '{proposal.proposal_id}' is {proposal.state.value}; expected one of "
                f"{[s.value for s in allowed]}"
            )

    def _transition(self, proposal: Proposal, target: ProposalState) -> None:
        machine = LifecycleStateMachine(transitions=dict(PROPOSAL_TRANSITIONS), state=proposal.state)
        machine.transition(target)
        proposal.state = target

    def _record(self, action: str, **detail: Any) -> None:
        self.journal.append({"kind": "evolution", "action": action, **detail})


def ratification_verbs() -> Sequence[str]:
    """Deliberately empty, and asserted so by test.

    `19.3`: Evolution "packages; it does not ratify." The absence of any
    ratifying verb is what makes 19.16.2's handoff unidirectional by
    construction, and it is what resolves the Evolution/Governance circular
    dependency: the edge back does not exist.

    The CIR-001 ruling authorized construction. It did not, and could not, give
    Evolution the authority 19.3 places elsewhere.
    """
    return ()
