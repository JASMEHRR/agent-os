"""The Learning Gateway — the closed loop of 13.18.1 (per 21B §21).

`13.2.1`: **"Learning is the only subsystem whose output is change to the other
subsystems."**

`13.2.3` draws the boundary: "Knowledge Gateway owns validation; Learning
Gateway owns proposal. Learning feeds the Knowledge pipeline; it does not
bypass it."

The loop: **Observe -> Propose -> Adopt -> Measure -> Confirm/Refute ->
Consolidate.** No adopted improvement escapes measurement (13 rule 9), and no
feedback loop stays open past its window (13 rule 16).

Four things are structural rather than policy:

**Propagation is handoff, never adoption.** `13.16.1`: "The target subsystem
retains full constitutional authority to reject, modify, or escalate the
proposal." So `propagate` delivers and relinquishes; the target reports back
through `report_adoption`. There is no `adopt` verb on this Gateway at all,
and a test asserts it never appears.

**The non-violable screen runs at validation, not at the target.** 21B §21.10:
"a proposal that would touch a non-violable rule is rejected at validation, not
at the target Gateway." Relying on the target to refuse would mean every target
must implement the same screen correctly, and the first one that did not would
be the way in.

**Attribution is graded, and correlation is never causation.** 13 rule 6, with
13.34.3's asymmetry: failure patterns need two instances plus a root cause,
success patterns need three.

**The Recursion Guard fires first.** Before evidence, before attribution,
before anything can normalize the input. See `recursion.py`.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol

from core.exceptions import AgentOSError, NotFoundError, ValidationError
from kernel.escalation import EscalationTrigger
from kernel.journal import ImmutableJournal
from kernel.lifecycle import LifecycleStateMachine
from kernel.signals import SignalEmitter, SignalType
from learning_gateway.entries import (
    CONFIDENCE_FLOOR,
    DECAY_HALF_LIFE,
    DEPRECATION_FLOOR,
    FAILURE_PATTERN_MINIMUM,
    LEARNING_TRANSITIONS,
    PROVISIONAL_CEILING,
    REQUIRES_HUMAN_RATIFICATION,
    SUCCESS_PATTERN_MINIMUM,
    EvidenceRef,
    Hypothesis,
    LearningEntry,
    LearningState,
    Observation,
    Pattern,
    PatternKind,
    TargetClass,
    assert_valid_confidence,
    required_observations,
    threshold_for,
    window_for,
)
from learning_gateway.recursion import RecursionGuard

#: 13 rule 3 / 21B §21.10. A proposal touching any of these is rejected at
#: validation. The list is the constitution's own vocabulary for the things
#: learning may never move.
NON_VIOLABLE_SUBJECTS = (
    "constitutional constraint",
    "non-violable",
    "security boundary",
    "approval gate",
    "human approval",
    "autonomy level",
    "human sovereign",
    "standing order",
    "panic protocol",
)


class LearningAuthorizer(Protocol):
    """Observer authentication and propagation boundary enforcement (21B §21.6)."""

    def principal_of(self, token: str) -> tuple[str, str]: ...

    def is_human(self, principal_id: str) -> bool: ...


class BudgetSource(Protocol):
    """Learning cycle budget checks (21B §21.6, 13 rule 11)."""

    def has_headroom(self, tenant_id: str, cost: float) -> bool: ...


class ProposalSink(Protocol):
    """One target Gateway's proposal intake.

    Deliberately narrow: the Learning Gateway can deliver, and can do nothing
    else to the target. The return value is the target's own acknowledgement,
    not its decision — the decision arrives later through `report_adoption`.
    """

    def receive(self, entry_id: str, target_subsystem: str, proposal: Mapping[str, Any]) -> str: ...


@dataclass(frozen=True)
class ConsolidationPackage:
    """Coherent, non-contradictory proposals ready for handoff (13.8.6)."""

    package_id: str
    tenant_id: str
    target_subsystem: str
    entry_ids: tuple[str, ...]
    assembled_at: datetime
    #: Entries dropped because they contradicted a stronger sibling.
    superseded_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class FailureLibraryEntry:
    """13's Failure Library, consulted before similar operations (21B §21.5)."""

    subject_id: str
    target_class: TargetClass
    root_cause: str
    occurrences: int
    last_seen: datetime
    entry_id: str


class InsufficientEvidence(ValidationError):
    """13.12.4's counts, or 13 rule 14's canonicity requirement."""


class AttributionAnomaly(ValidationError):
    """21B §21.9 — Critical. Quarantine and human review."""


class NonViolableProposal(ValidationError):
    """13 rule 3 / 13 rule 15. Rejected at validation, never at the target."""


@dataclass
class LearningGateway:
    """Layer 6. Proposes changes to things it does not own."""

    authorizer: LearningAuthorizer
    budget: BudgetSource
    signals: SignalEmitter
    escalate: Callable[[EscalationTrigger, str], None] = field(default=lambda trigger, detail: None)
    alert_human: Callable[[str], None] = field(default=lambda detail: None)
    now: Callable[[], datetime] = field(default=lambda: datetime.now(UTC))
    #: [Engineering Decision] 13 rule 11 requires circuit-breaker respect
    #: without naming a per-cycle figure. One unit per cycle keeps the check
    #: real while the Cost Manager owns the actual limit.
    cycle_cost: float = 1.0

    def __post_init__(self) -> None:
        self.guard = RecursionGuard(escalate=self.escalate, alert_human=self.alert_human, now=self.now)
        self.journal = ImmutableJournal()
        self._observations: dict[str, Observation] = {}
        self._entries: dict[str, LearningEntry] = {}
        self._packages: dict[str, ConsolidationPackage] = {}
        self._failures: dict[str, FailureLibraryEntry] = {}
        self._sinks: dict[str, ProposalSink] = {}
        self._reversals: list[str] = []
        self._cycles = 0

    # ------------------------------------------------------------ Registration

    def register_target(self, target_subsystem: str, sink: ProposalSink) -> None:
        """A target Gateway's intake. Handoff has somewhere to go, or none."""
        self._sinks[target_subsystem] = sink

    # ------------------------------------------------------------- Observe

    def observe(self, token: str, observation: Observation) -> Observation:
        """**Observation Submission** (21B §21.5).

        13 rule 1: no formation without an authenticated observer and complete
        evidence citation. 13 rule 7 forbids anonymous formation outright, so
        the token is required rather than optional.
        """
        principal_id, tenant_id = self.authorizer.principal_of(token)
        if tenant_id != observation.tenant_id:
            raise AgentOSError(
                f"'{principal_id}' may not submit observations for tenant '{observation.tenant_id}' "
                "(13 rule 8, no cross-tenant learning without anonymization and human approval)"
            )
        if not observation.evidence:
            raise InsufficientEvidence(f"observation '{observation.observation_id}' cites no evidence (13 rule 1)")
        self.guard.check(
            observation.target_class,
            observation.subject_id,
            observation.subject_id,
            evidence_kinds=tuple(e.kind for e in observation.evidence),
            observer_id=principal_id,
        )
        if not self.budget.has_headroom(tenant_id, self.cycle_cost):
            # 13 rule 11 — a learning cycle may not breach a circuit breaker.
            # Deferred, not degraded: the observation is kept for later.
            raise AgentOSError(f"learning cycle deferred: tenant '{tenant_id}' has no budget headroom (13 rule 11)")
        self._observations[observation.observation_id] = observation
        self._cycles += 1
        self._record("observed", observation_id=observation.observation_id, observer=principal_id)
        return observation

    def submit_human_feedback(self, token: str, observation: Observation) -> Observation:
        """**Human Feedback Entry** (21B §21.5, 13.33.1).

        High-confidence evidence that "bypasses certain automated validation
        gates while retaining full audit". It bypasses the evidence *count*,
        not the audit, not the recursion guard, and not the non-violable
        screen — a human may teach the system, and may not use the learning
        pipeline to move a constitutional boundary.
        """
        principal_id, _tenant_id = self.authorizer.principal_of(token)
        if not self.authorizer.is_human(principal_id):
            raise AgentOSError(
                f"'{principal_id}' is not a human principal; only a human submits human feedback (13.33.1)"
            )
        marked = Observation(
            observation_id=observation.observation_id,
            tenant_id=observation.tenant_id,
            observer_id=principal_id,
            target_class=observation.target_class,
            subject_id=observation.subject_id,
            summary=observation.summary,
            evidence=tuple(
                EvidenceRef(
                    reference=e.reference,
                    kind=e.kind,
                    observed_at=e.observed_at,
                    confidence=e.confidence,
                    human=True,
                )
                for e in observation.evidence
            ),
            observed_at=observation.observed_at,
            human_feedback=True,
        )
        return self.observe(token, marked)

    # ------------------------------------------------- Pattern and hypothesis

    def recognize(self, pattern: Pattern) -> Pattern:
        """Pattern Recognizer with 13.34.3's asymmetric thresholds.

        "Failure patterns require fewer confirming instances but stronger root
        cause attribution. Success patterns require more confirming instances
        but permit broader generalization." The asymmetry is deliberate: when
        capital is at risk, being slow to stop repeating a failure costs more
        than being slow to replicate a success.
        """
        if pattern.kind == PatternKind.FAILURE:
            if pattern.instance_count < FAILURE_PATTERN_MINIMUM:
                raise InsufficientEvidence(
                    f"a failure pattern needs {FAILURE_PATTERN_MINIMUM} instances, got {pattern.instance_count}"
                )
            if not pattern.root_cause.strip():
                raise InsufficientEvidence(
                    "a failure pattern trades instance count for root cause attribution (13.34.3); "
                    "it may not have neither"
                )
        elif pattern.kind == PatternKind.SUCCESS and pattern.instance_count < SUCCESS_PATTERN_MINIMUM:
            raise InsufficientEvidence(
                f"a success pattern needs {SUCCESS_PATTERN_MINIMUM} instances, got {pattern.instance_count}"
            )
        return pattern

    def hypothesize(self, token: str, hypothesis: Hypothesis) -> LearningEntry:
        """Hypothesis Former (13.8.4). Provisional until validated."""
        principal_id, tenant_id = self.authorizer.principal_of(token)
        if hypothesis.entry_id in self._entries:
            raise AgentOSError(f"learning entry '{hypothesis.entry_id}' already exists")
        if tenant_id != hypothesis.tenant_id:
            raise AgentOSError(f"'{principal_id}' may not form entries for tenant '{hypothesis.tenant_id}'")
        self.guard.check(
            hypothesis.target_class,
            hypothesis.target_subsystem,
            hypothesis.subject_id,
            proposal=hypothesis.proposal,
            evidence_kinds=tuple(e.kind for e in hypothesis.evidence),
            observer_id=principal_id,
        )
        self.recognize(hypothesis.pattern)
        entry = LearningEntry(hypothesis=hypothesis, state=LearningState.HYPOTHESIZED)
        self._entries[hypothesis.entry_id] = entry
        self._record("hypothesized", entry_id=entry.entry_id, target=hypothesis.target_subsystem)
        return entry

    # -------------------------------------------------------------- Validate

    def validate(self, entry_id: str) -> LearningEntry:
        """Validation Engine: four dimensions, then the authoritative confidence.

        13.13.2's dimensions are evidence quality, attribution strength, scope
        conformance and contradiction. Each can reject; none can be skipped.
        """
        entry = self.get(entry_id)
        hypothesis = entry.hypothesis
        self._require_state(entry, LearningState.HYPOTHESIZED, LearningState.QUARANTINED)

        self._screen_non_violable(hypothesis)
        self._check_evidence(entry)
        self._check_attribution(entry)
        contradiction = self._find_contradiction(entry)
        if contradiction is not None:
            self._transition(entry, LearningState.QUARANTINED)
            entry.quarantine_reason = (
                f"contradicts '{contradiction}'; 13 rule 13 forbids proceeding on unresolved "
                "contradictory evidence without human arbitration"
            )
            self._record("quarantined", entry_id=entry_id, reason=entry.quarantine_reason)
            self.signals.emit(
                SignalType.EVENT,
                "learning.contradiction.quarantined",
                hypothesis.tenant_id,
                entry_id=entry_id,
                contradicts=contradiction,
            )
            return entry

        confidence = self._derive_confidence(entry)
        threshold = threshold_for(hypothesis.target_class)
        entry.confidence = confidence

        if confidence < CONFIDENCE_FLOOR:
            self._abandon(entry, f"confidence {confidence} is below the {CONFIDENCE_FLOOR} floor (13.13.3)")
            return entry
        if confidence < threshold:
            # 13 rule 5 — below the target class's threshold, propagation is
            # forbidden. Abandoned rather than silently downgraded: proposing
            # to a lesser target would be a different proposal.
            self._abandon(
                entry,
                f"confidence {confidence} is below the {threshold} threshold for "
                f"{hypothesis.target_class.value} learning (13 rule 5)",
            )
            return entry

        entry.provisional = confidence <= PROVISIONAL_CEILING
        entry.validated_at = self.now()
        self._transition(entry, LearningState.VALIDATED)
        self._record("validated", entry_id=entry_id, confidence=confidence, provisional=entry.provisional)
        if hypothesis.pattern.kind == PatternKind.FAILURE:
            self._catalogue_failure(entry)
        return entry

    def _screen_non_violable(self, hypothesis: Hypothesis) -> None:
        """13 rule 3 and 13 rule 15, screened here rather than at the target."""
        text = f"{hypothesis.proposal} {hypothesis.expected_outcome}".lower()
        for subject in NON_VIOLABLE_SUBJECTS:
            if subject in text:
                raise NonViolableProposal(
                    f"the proposal would touch '{subject}', which learning may never modify "
                    "(13 rules 3 and 15); rejected at validation, not at the target Gateway"
                )

    def _check_evidence(self, entry: LearningEntry) -> None:
        hypothesis = entry.hypothesis
        for reference in hypothesis.evidence:
            if not reference.is_canonical:
                # 13 rule 14 — quarantined memory and speculation may not be
                # the sole evidence, and here they are not evidence at all
                # unless something canonical stands beside them.
                canonical = [e for e in hypothesis.evidence if e.is_canonical]
                if not canonical:
                    raise InsufficientEvidence(
                        f"entry '{entry.entry_id}' rests only on quarantined or speculative evidence (13 rule 14)"
                    )
        if hypothesis.human_feedback:
            # 13.33.1 — human feedback bypasses the count, not the audit.
            return
        needed = required_observations(hypothesis.target_class)
        canonical = [e for e in hypothesis.evidence if e.is_canonical]
        if len(canonical) < needed:
            raise InsufficientEvidence(
                f"{hypothesis.target_class.value} learning needs {needed} canonical observations, "
                f"got {len(canonical)} (13.12.4)"
            )

    def _check_attribution(self, entry: LearningEntry) -> None:
        attribution = entry.hypothesis.attribution
        if not attribution.null_hypothesis.strip():
            raise AttributionAnomaly(
                "13.12.3 requires mandatory consideration of the null hypothesis; a blank one is not consideration"
            )
        if not attribution.temporal_order_holds:
            raise AttributionAnomaly(f"entry '{entry.entry_id}' claims a cause that did not precede its effect")
        if entry.hypothesis.is_causal_claim and not attribution.confounding_controlled:
            raise AttributionAnomaly(
                "a causal claim with uncontrolled confounders is correlation presented as causation (13 rule 6)"
            )

    def _derive_confidence(self, entry: LearningEntry) -> float:
        """Authoritative confidence (13.8.5). The proposer's guess is not used.

        A correlation pattern is capped below every causal threshold. That is
        13 rule 6 in arithmetic: a correlation can inform, and can never
        propagate as though it explained.
        """
        hypothesis = entry.hypothesis
        evidence_quality = sum(e.confidence for e in hypothesis.evidence if e.is_canonical) / max(
            1, len([e for e in hypothesis.evidence if e.is_canonical])
        )
        attribution_strength = hypothesis.attribution.strength
        derived = (evidence_quality + attribution_strength) / 2.0
        if hypothesis.human_feedback:
            # 13.33.1 / 13.7.5 — human feedback is high-confidence evidence and
            # "is never overridden by autonomous observation".
            derived = max(derived, 0.95)
        if hypothesis.pattern.kind == PatternKind.CORRELATION:
            derived = min(derived, CONFIDENCE_FLOOR - 0.01)
        return assert_valid_confidence(derived)

    def _find_contradiction(self, entry: LearningEntry) -> str | None:
        """A confirmed entry proposing the opposite about the same subject."""
        for other in self._entries.values():
            if other.entry_id == entry.entry_id:
                continue
            if other.state not in (LearningState.CONFIRMED, LearningState.ADOPTED):
                continue
            if other.hypothesis.subject_id != entry.hypothesis.subject_id:
                continue
            if other.hypothesis.proposal.strip().lower() != entry.hypothesis.proposal.strip().lower():
                if other.hypothesis.target_subsystem == entry.hypothesis.target_subsystem and (
                    other.hypothesis.pattern.kind != entry.hypothesis.pattern.kind
                ):
                    return other.entry_id
        return None

    # ----------------------------------------------------------- Consolidate

    def consolidate(self, package_id: str, tenant_id: str, target_subsystem: str) -> ConsolidationPackage:
        """Consolidation Engine (13.8.6).

        Prevents fragmented or conflicting improvements propagating at once.
        Where two validated entries touch the same subject, the stronger
        supersedes the weaker rather than both going forward and leaving the
        target to arbitrate.
        """
        candidates = [
            e
            for e in self._entries.values()
            if e.state == LearningState.VALIDATED
            and e.hypothesis.tenant_id == tenant_id
            and e.hypothesis.target_subsystem == target_subsystem
        ]
        if not candidates:
            raise ValidationError(f"nothing validated is awaiting consolidation for '{target_subsystem}'")

        by_subject: dict[str, LearningEntry] = {}
        superseded: list[str] = []
        for entry in sorted(candidates, key=lambda e: e.confidence, reverse=True):
            subject = entry.hypothesis.subject_id
            if subject in by_subject:
                entry.superseded_by = by_subject[subject].entry_id
                self._transition(entry, LearningState.QUARANTINED)
                entry.quarantine_reason = f"superseded during consolidation by '{by_subject[subject].entry_id}'"
                superseded.append(entry.entry_id)
                continue
            by_subject[subject] = entry

        package = ConsolidationPackage(
            package_id=package_id,
            tenant_id=tenant_id,
            target_subsystem=target_subsystem,
            entry_ids=tuple(e.entry_id for e in by_subject.values()),
            assembled_at=self.now(),
            superseded_ids=tuple(superseded),
        )
        for entry in by_subject.values():
            self._transition(entry, LearningState.CONSOLIDATED)
            # Journalled per entry, not only per package: 21B §21.5 asks for
            # forensic reconstruction of an entry, and a stage that appears
            # only under a package id is invisible to that query.
            self._record("consolidated", entry_id=entry.entry_id, package_id=package_id)
        self._packages[package_id] = package
        self._record("package_assembled", package_id=package_id, entries=len(package.entry_ids))
        return package

    # ------------------------------------------------------------- Propagate

    def propagate(self, package_id: str) -> list[str]:
        """Propagation Router. **Handoff, not adoption** (13.16.1).

        Delivers to the target Gateway and relinquishes control. The target
        "retains full constitutional authority to reject, modify, or escalate",
        and this Gateway has no verb that would take that authority back.
        """
        package = self._packages.get(package_id)
        if package is None:
            raise NotFoundError(f"consolidation package '{package_id}' does not exist")
        sink = self._sinks.get(package.target_subsystem)
        if sink is None:
            raise NotFoundError(
                f"no registered intake for '{package.target_subsystem}'; "
                "13 rule 2 forbids bypassing the target subsystem's Gateway"
            )

        delivered: list[str] = []
        for entry_id in package.entry_ids:
            entry = self.get(entry_id)
            if entry.target_class in REQUIRES_HUMAN_RATIFICATION and not entry.hypothesis.human_feedback:
                # 13.13.3 reserves the 0.95+ band for Business and Portfolio
                # learning "with human ratification". Escalated rather than
                # propagated: the ratification is a human act elsewhere.
                self.alert_human(
                    f"{entry.target_class.value} learning entry '{entry_id}' requires human ratification "
                    "before propagation (13.13.3)"
                )
                self._record("awaiting_ratification", entry_id=entry_id)
                continue
            sink.receive(entry_id, package.target_subsystem, self._package_body(entry))
            entry.propagated_at = self.now()
            self._transition(entry, LearningState.PROPAGATED)
            delivered.append(entry_id)
            self._record("propagated", entry_id=entry_id, target=package.target_subsystem)
            self.signals.emit(
                SignalType.EVENT,
                "learning.proposal.propagated",
                entry.hypothesis.tenant_id,
                entry_id=entry_id,
                target=package.target_subsystem,
                confidence=entry.confidence,
            )
        return delivered

    def _package_body(self, entry: LearningEntry) -> dict[str, Any]:
        hypothesis = entry.hypothesis
        return {
            "entry_id": entry.entry_id,
            "proposal": hypothesis.proposal,
            "expected_outcome": hypothesis.expected_outcome,
            "confidence": entry.confidence,
            "provisional": entry.provisional,
            "pattern_kind": hypothesis.pattern.kind.value,
            # 13 rule 6 — the target sees whether this is a cause or a
            # correlation, so it cannot mistake one for the other.
            "is_causal_claim": hypothesis.is_causal_claim,
            "evidence": [e.reference for e in hypothesis.evidence],
            "attribution_strength": hypothesis.attribution.strength,
            "null_hypothesis": hypothesis.attribution.null_hypothesis,
            "scope": hypothesis.scope,
        }

    # ----------------------------------------------------- Adopt and measure

    def report_adoption(self, entry_id: str, adopted: bool, justification: str = "") -> LearningEntry:
        """**Adoption Report** (21B §21.5). The target's decision, arriving back.

        Rejection abandons the entry with the justification logged; 13.16.1 is
        clear that it "does not invalidate the evidence", so the hypothesis and
        its evidence stay in the journal intact.
        """
        entry = self.get(entry_id)
        self._require_state(entry, LearningState.PROPAGATED)
        if not adopted:
            self._abandon(entry, justification or "the target subsystem rejected the proposal")
            return entry
        entry.adopted_at = self.now()
        self._transition(entry, LearningState.ADOPTED)
        self._record("adopted", entry_id=entry_id, justification=justification)
        return entry

    def record_measurement(self, entry_id: str, improved: bool) -> LearningEntry:
        """Measurement Engine (13.18). Closes the loop, or keeps it open.

        13 rule 9 forbids adoption without measurement, so an adopted entry
        accumulates observations until its window fills and then resolves. The
        window comes from the target class (13.18.2), not from the caller.
        """
        entry = self.get(entry_id)
        self._require_state(entry, LearningState.ADOPTED)
        entry.measurements.append(improved)
        minimum, maximum = window_for(entry.target_class)
        if len(entry.measurements) < minimum:
            return entry

        confirmations = sum(1 for m in entry.measurements if m)
        ratio = confirmations / len(entry.measurements)
        entry.actual_improvement = round(ratio, 4)
        if ratio > 0.5:
            self._transition(entry, LearningState.CONFIRMED)
            self._record("confirmed", entry_id=entry_id, ratio=ratio)
            self.signals.emit(
                SignalType.METRIC,
                "learning.entry.confirmed",
                entry.hypothesis.tenant_id,
                value=ratio,
                entry_id=entry_id,
            )
            return entry
        if ratio < 0.5:
            # Refutation resolves at the same point confirmation does, rather
            # than running to the ceiling. Waiting would leave a change the
            # evidence already contradicts adopted for longer, which is the
            # expensive direction to be slow in (13.34.3).
            self._refute(entry, ratio)
            return entry
        if len(entry.measurements) >= maximum:
            # An exact tie at the ceiling. The expected improvement did not
            # occur, so the entry is refuted rather than left open (13 rule 16).
            self._refute(entry, ratio)
        return entry

    def _refute(self, entry: LearningEntry, ratio: float) -> None:
        """13.18.4 — refutation emits a reversal proposal and is itself learning."""
        self._transition(entry, LearningState.REFUTED)
        self._reversals.append(entry.entry_id)
        self._record("refuted", entry_id=entry.entry_id, ratio=ratio)
        sink = self._sinks.get(entry.hypothesis.target_subsystem)
        if sink is not None:
            sink.receive(
                entry.entry_id,
                entry.hypothesis.target_subsystem,
                {"entry_id": entry.entry_id, "reversal": True, "reason": "measurement refuted the expectation"},
            )
        self.signals.emit(
            SignalType.EVENT,
            "learning.entry.refuted",
            entry.hypothesis.tenant_id,
            entry_id=entry.entry_id,
            ratio=ratio,
        )

    def overdue(self) -> list[LearningEntry]:
        """13 rule 16 — no feedback loop stays open past its window.

        Reports adopted entries whose window has filled without resolving.
        Visibility rather than silent closure: closing one by fiat would
        manufacture a confirmation nobody measured.
        """
        overdue: list[LearningEntry] = []
        for entry in self._entries.values():
            if entry.state != LearningState.ADOPTED:
                continue
            _minimum, maximum = window_for(entry.target_class)
            if len(entry.measurements) >= maximum:
                overdue.append(entry)
        return overdue

    # ---------------------------------------------------------------- Decay

    def decay(self) -> list[LearningEntry]:
        """Decay Engine (13.19). Freshness falls; confirmed truth goes stale.

        Deprecation supersedes rather than deletes, because 13 rule 10 forbids
        modifying or deleting an entry after validation.
        """
        deprecated: list[LearningEntry] = []
        now = self.now()
        for entry in self._entries.values():
            if entry.state != LearningState.CONFIRMED or entry.validated_at is None:
                continue
            elapsed = (now - entry.validated_at).total_seconds()
            half_lives = elapsed / DECAY_HALF_LIFE.total_seconds()
            entry.freshness = round(0.5**half_lives, 4)
            if entry.effective_confidence < DEPRECATION_FLOOR:
                self._transition(entry, LearningState.SUPERSEDED)
                self._record("deprecated", entry_id=entry.entry_id, freshness=entry.freshness)
                deprecated.append(entry)
        return deprecated

    # ------------------------------------------------------- Failure Library

    def _catalogue_failure(self, entry: LearningEntry) -> None:
        subject = entry.hypothesis.subject_id
        existing = self._failures.get(subject)
        self._failures[subject] = FailureLibraryEntry(
            subject_id=subject,
            target_class=entry.target_class,
            root_cause=entry.hypothesis.pattern.root_cause,
            occurrences=(existing.occurrences if existing else 0) + entry.hypothesis.pattern.instance_count,
            last_seen=self.now(),
            entry_id=entry.entry_id,
        )

    def consult_failures(self, subject_id: str) -> FailureLibraryEntry | None:
        """**Failure Library Query** (21B §21.5), consulted before similar work."""
        return self._failures.get(subject_id)

    def failure_library(self) -> list[FailureLibraryEntry]:
        return sorted(self._failures.values(), key=lambda f: f.occurrences, reverse=True)

    # ------------------------------------------------------- Prioritization

    def prioritize(self, tenant_id: str) -> list[LearningEntry]:
        """Prioritization Engine, with 13.34.3's asymmetry applied.

        "Failure learning is prioritized over success learning when capital is
        at risk", so a failure entry outranks a success entry of equal
        strength rather than tying with it.
        """
        pending = [
            e
            for e in self._entries.values()
            if e.hypothesis.tenant_id == tenant_id and e.state in (LearningState.VALIDATED, LearningState.CONSOLIDATED)
        ]
        return sorted(
            pending,
            key=lambda e: (
                e.hypothesis.pattern.kind == PatternKind.FAILURE,
                e.effective_confidence,
                e.hypothesis.attribution.strength,
            ),
            reverse=True,
        )

    # ---------------------------------------------------------------- Query

    def get(self, entry_id: str) -> LearningEntry:
        entry = self._entries.get(entry_id)
        if entry is None:
            raise NotFoundError(f"learning entry '{entry_id}' does not exist")
        return entry

    def query_journal(self, entry_id: str | None = None) -> list[Mapping[str, Any]]:
        """**Learning Journal Query** (21B §21.5). Read-only, forensic."""
        payloads = [self.journal[i].payload for i in range(len(self.journal))]
        if entry_id is None:
            return list(payloads)
        return [p for p in payloads if p.get("entry_id") == entry_id]

    def entries(self, state: LearningState | None = None) -> list[LearningEntry]:
        if state is None:
            return list(self._entries.values())
        return [e for e in self._entries.values() if e.state == state]

    # --------------------------------------------------------------- Health

    def health(self) -> Mapping[str, Any]:
        """The five metric families of 13.23.1 (21B §21.11)."""
        entries = list(self._entries.values())
        by_state: dict[str, int] = {}
        for entry in entries:
            by_state[entry.state.value] = by_state.get(entry.state.value, 0) + 1
        measured = [e for e in entries if e.state in (LearningState.CONFIRMED, LearningState.REFUTED)]
        confirmed = [e for e in measured if e.state == LearningState.CONFIRMED]
        propagated = [e for e in entries if e.propagated_at is not None]
        adopted = [e for e in entries if e.adopted_at is not None]
        return {
            "velocity": {
                "observations": len(self._observations),
                "hypotheses": len(entries),
                "validations": len([e for e in entries if e.validated_at is not None]),
                "propagations": len(propagated),
                "cycles": self._cycles,
            },
            "quality": {
                "confirmation_rate": round(len(confirmed) / len(measured), 4) if measured else 0.0,
                "refutation_rate": round((len(measured) - len(confirmed)) / len(measured), 4) if measured else 0.0,
                # 13.4.3 / 21B §21.11 — the subsystem's most consequential
                # signal: the mechanism by which learning degrades the system
                # it exists to improve.
                "attribution_error_rate": (round(len(self._reversals) / len(adopted), 4) if adopted else 0.0),
            },
            "governance": {
                "adoption_rate": round(len(adopted) / len(propagated), 4) if propagated else 0.0,
                "awaiting_ratification": len(
                    [
                        e
                        for e in entries
                        if e.state == LearningState.CONSOLIDATED and e.target_class in REQUIRES_HUMAN_RATIFICATION
                    ]
                ),
                "quarantined": by_state.get(LearningState.QUARANTINED.value, 0),
            },
            "health": {
                "by_state": by_state,
                "backlog": len([e for e in entries if not e.is_terminal]),
                "overdue_windows": len(self.overdue()),
                "recursion": self.guard.health(),
                "failure_library": len(self._failures),
            },
            "economic": {
                "cycles": self._cycles,
                "cost_per_cycle": self.cycle_cost,
                "total_cost": round(self._cycles * self.cycle_cost, 6),
            },
            "journal_entries": len(self.journal),
            "journal_intact": self.journal.verify_chain(),
        }

    # ------------------------------------------------------------ Internals

    def _abandon(self, entry: LearningEntry, reason: str) -> None:
        entry.abandonment_reason = reason
        self._transition(entry, LearningState.ABANDONED)
        self._record("abandoned", entry_id=entry.entry_id, reason=reason)

    def _transition(self, entry: LearningEntry, target: LearningState) -> None:
        machine = LifecycleStateMachine(transitions=dict(LEARNING_TRANSITIONS), state=entry.state)
        machine.transition(target)
        entry.state = target

    def _require_state(self, entry: LearningEntry, *allowed: LearningState) -> None:
        if entry.state not in allowed:
            raise AgentOSError(
                f"entry '{entry.entry_id}' is {entry.state.value}; expected one of {[state.value for state in allowed]}"
            )

    def _record(self, action: str, **detail: Any) -> None:
        self.journal.append({"kind": "learning", "action": action, **detail})


def loop_stages() -> Sequence[str]:
    """13.18.1's loop, named so a test can assert the module implements it."""
    return ("observe", "propose", "adopt", "measure", "confirm_refute", "consolidate")
