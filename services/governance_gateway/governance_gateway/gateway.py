"""The Governance Gateway — constitutional steward (15, per 21B §23).

`15.6.1` establishes its exclusive authority: **"No subsystem may self-certify
its own constitutional compliance."**

`15.2.1` bounds it just as firmly: "Governance is the guardian of the
guardrails. It does not drive the vehicle; it verifies that the vehicle remains
on legitimate roads."

Six properties are structural rather than policy, and each names the failure it
prevents:

**Meta-oversight observes but does not intervene.** 15.22.3: Governance "may
declare a subsystem's self-governance non-compliant; it may not directly modify
subsystem internals, reassign agents, or alter decision logic." The Gateway
holds no reference to any subsystem it assesses and exposes no mutating verb
against one. Remediation is a *requirement it records*, never an action it
takes.

**No subsystem self-certifies.** `assess` refuses when the assessor and the
assessed scope are the same party. A subsystem grading its own homework is
exactly what 15.6.1 forbids.

**Timeout never ratifies.** 15.8.2 and 15.28.4 both say so. There is no code
path from an elapsed review deadline to Ratified; `expire_reviews` can only
produce Rejected or Escalated.

**Independence is enforced at assignment.** 15.25.4 and 15.27.4 forbid
reviewing or auditing a scope you are accountable for. The Review Orchestrator
and Audit Engine refuse the assignment rather than flagging the finding
afterwards, because a compromised review is worth nothing once written.

**No artifact contradicts a non-violable rule.** 15.6.3, screened at
**formation**, before an artifact can reach review. An artifact that reached
review would already have a constituency.

**Evidence comes from subsystem journals directly.** 15.7.2, which is what
breaks the Governance to Observability circular dependency and lets journal-
based Governance operate before the full Observability profile exists.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

from core.exceptions import AgentOSError, NotFoundError, ValidationError
from governance_gateway.artifacts import (
    DRIFT_VELOCITY_THRESHOLD,
    EMERGENCY_REVIEW_WINDOW,
    GOVERNANCE_OVERHEAD_CEILING,
    GOVERNANCE_TRANSITIONS,
    ArtifactRecord,
    ArtifactState,
    ComplianceState,
    EvidenceItem,
    EvidencePackage,
    Exception_,
    Finding,
    GClass,
    GovernanceArtifact,
    Interpretation,
    Policy,
    PolicyState,
    ReviewKind,
    Stewardship,
    assert_confidence_for,
)
from kernel.escalation import EscalationTrigger
from kernel.journal import ImmutableJournal
from kernel.lifecycle import LifecycleStateMachine
from kernel.signals import SignalEmitter, SignalType

#: 15.6.3 and 15.20.5 — the things no governance artifact may contradict, and
#: which are themselves unamendable. Screened at formation.
NON_VIOLABLE_SUBJECTS = (
    "human sovereignty",
    "human sovereign",
    "non-violable",
    "panic protocol",
    "approval gate",
    "self-certif",
    "audit trail",
    "immutable journal",
    "tenant isolation",
)


class GovernanceAuthorizer(Protocol):
    """Identity verification and permission enforcement (21B §23.6)."""

    def principal_of(self, token: str) -> tuple[str, str]: ...

    def is_human(self, principal_id: str) -> bool: ...


class JournalSource(Protocol):
    """One subsystem's journal, read directly per 15.7.2.

    The interface is read-only by construction. A Governance Gateway holding
    anything that could write to a subsystem journal would be able to
    manufacture the evidence it then assesses.
    """

    def entries(self, scope: str) -> Sequence[Mapping[str, Any]]: ...


class SelfCertification(AgentOSError):
    """15.6.1 — no subsystem may certify its own constitutional compliance."""


class IndependenceViolation(AgentOSError):
    """15.25.4 / 15.27.4 — refused at assignment, not flagged afterwards."""


class NonViolableViolation(ValidationError):
    """15.6.3 — screened at formation, before an artifact can reach review."""


class OrphanedPolicy(ValidationError):
    """15.16.2 — "A policy without constitutional lineage is illegitimate.\""""


class PolicyContradiction(ValidationError):
    """15.16.3 — a lower layer contradicting a higher layer is void."""


@dataclass
class GovernanceGateway:
    """The Oversight Plane. Assesses what it does not own."""

    authorizer: GovernanceAuthorizer
    signals: SignalEmitter
    escalate: Callable[[EscalationTrigger, str], None] = field(default=lambda trigger, detail: None)
    alert_human: Callable[[str], None] = field(default=lambda detail: None)
    now: Callable[[], datetime] = field(default=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        self.journal = ImmutableJournal()
        self._artifacts: dict[str, ArtifactRecord] = {}
        self._policies: dict[str, Policy] = {}
        self._interpretations: dict[str, Interpretation] = {}
        self._stewardships: dict[str, Stewardship] = {}
        self._exceptions: dict[str, Exception_] = {}
        self._findings: list[Finding] = []
        self._compliance: dict[str, ComplianceState] = {}
        self._drift: dict[str, list[float]] = {}
        self._journals: dict[str, JournalSource] = {}
        self._operational_cost = 0.0
        self._governance_cost = 0.0

    # ------------------------------------------------------- Evidence (15.7.2)

    def register_journal(self, subsystem: str, source: JournalSource) -> None:
        """15.7.2 — evidence assembled directly from subsystem journals.

        This is what breaks the Governance to Observability cycle: Governance
        does not wait for the full Observability profile to exist before it can
        see anything.
        """
        self._journals[subsystem] = source

    def assemble_evidence(self, scope: str, subsystems: Sequence[str]) -> EvidencePackage:
        """Evidence Assembler. Reports gaps rather than omitting them.

        15 rule 1 requires documented evidence **or a gap flag**. Silence about
        a missing journal makes an assessment look better founded than it is,
        which is the specific way an oversight subsystem lies without anyone
        intending it to.
        """
        items: list[EvidenceItem] = []
        gaps: list[str] = []
        if not subsystems:
            # Consulting nothing is not the same as finding nothing, and an
            # empty package that declared neither would let an artifact form on
            # no basis at all (15 rule 1).
            gaps.append(f"no subsystem journals were consulted for scope '{scope}'")
        for subsystem in subsystems:
            source = self._journals.get(subsystem)
            if source is None:
                gaps.append(f"no journal registered for '{subsystem}'")
                continue
            entries = list(source.entries(scope))
            if not entries:
                gaps.append(f"'{subsystem}' has no journal entries for scope '{scope}'")
                continue
            for index, entry in enumerate(entries):
                items.append(
                    EvidenceItem(
                        reference=f"{subsystem}:{scope}:{index}",
                        source_journal=subsystem,
                        observed_at=self.now(),
                        summary=str(entry.get("action", entry)),
                    )
                )
        return EvidencePackage(items=tuple(items), gaps=tuple(gaps))

    # ------------------------------------------------------------- Artifacts

    def form(self, token: str, artifact: GovernanceArtifact) -> ArtifactRecord:
        """Artifact Controller. The non-violable screen runs here.

        15 rule 1: no artifact without unique identity, authenticated steward,
        and documented evidence or gap flag.
        """
        principal_id, tenant_id = self.authorizer.principal_of(token)
        if artifact.artifact_id in self._artifacts:
            raise AgentOSError(f"governance artifact '{artifact.artifact_id}' already exists")
        if tenant_id != artifact.tenant_id:
            raise AgentOSError(f"'{principal_id}' may not form artifacts for tenant '{artifact.tenant_id}'")

        self._screen_non_violable(artifact.subject, artifact.rationale)

        # 15.33.2 / 21B §23.10 — G4 authority is bound to human credentials and
        # cannot be delegated. Blocked at formation, not at ratification: an
        # artifact that reached review would already have a constituency.
        if artifact.g_class.is_human_only and not self.authorizer.is_human(artifact.steward_id):
            raise AgentOSError(
                f"'{artifact.steward_id}' is not a human principal; G4 authority is human-only and "
                "may not be delegated (15.9.1, 15.33.2)"
            )
        if not artifact.evidence.items and not artifact.evidence.gaps:
            raise ValidationError(f"artifact '{artifact.artifact_id}' documents neither evidence nor a gap (15 rule 1)")
        if not self._steward_covers(artifact.steward_id, artifact.scope, artifact.g_class):
            raise AgentOSError(
                f"'{artifact.steward_id}' holds no active stewardship at {artifact.g_class.name} "
                f"covering '{artifact.scope}' (15.23.3)"
            )

        record = ArtifactRecord(artifact=artifact)
        self._artifacts[artifact.artifact_id] = record
        self._record("formed", artifact_id=artifact.artifact_id, g_class=artifact.g_class.name)
        return record

    def _screen_non_violable(self, *texts: str) -> None:
        """15.6.3 with 15.20.5. Screened at formation, before review."""
        joined = " ".join(texts).lower()
        for subject in NON_VIOLABLE_SUBJECTS:
            if subject in joined and any(
                verb in joined for verb in ("reduce", "remove", "weaken", "bypass", "suspend", "amend", "waive")
            ):
                raise NonViolableViolation(
                    f"the artifact would touch '{subject}', which no governance artifact may contradict "
                    "and which is itself unamendable (15.6.3, 15.20.5)"
                )

    # ----------------------------------------------------------- Assessment

    def assess(
        self,
        token: str,
        artifact_id: str,
        compliance: ComplianceState,
        confidence: float,
        detail: str = "",
    ) -> ArtifactRecord:
        """Assessment Engine, then Ruling Formation (15.18).

        Refuses when the assessor is accountable for the scope being assessed.
        15.6.1's "no subsystem may self-certify" is not a slogan here: it is a
        check that fires on the assessor's own stewardship.
        """
        principal_id, _tenant_id = self.authorizer.principal_of(token)
        record = self.get(artifact_id)
        if self._is_accountable_for(principal_id, record.artifact.scope):
            raise SelfCertification(
                f"'{principal_id}' is accountable for '{record.artifact.scope}' and may not certify its "
                "compliance (15.6.1)"
            )
        assert_confidence_for(record.artifact.g_class, confidence)

        record.confidence = round(confidence, 4)
        record.compliance = compliance
        record.ruling = detail

        if record.artifact.evidence.has_gaps:
            # 15.12.4 / 21B §23.9 — permitted, with an uncertainty rider and
            # enhanced monitoring, rather than silently treated as complete.
            record.uncertainty_rider = (
                f"assessed with evidence gaps: {list(record.artifact.evidence.gaps)}; enhanced monitoring applies"
            )

        if compliance == ComplianceState.NON_COMPLIANT:
            # 15.18.4 — remediation is a requirement recorded, never an action
            # taken. "The Gateway monitors remediation execution but does not
            # execute it."
            record.remediation = detail or "remediation required; routed to the subsystem's own governance"
        self._compliance[record.artifact.scope] = compliance
        self._transition(record, ArtifactState.RULED)
        self._record(
            "ruled",
            artifact_id=artifact_id,
            compliance=compliance.value,
            confidence=record.confidence,
            by=principal_id,
        )
        self.signals.emit(
            SignalType.EVENT,
            "governance.ruling.issued",
            record.artifact.tenant_id,
            artifact_id=artifact_id,
            compliance=compliance.value,
        )
        if compliance in (ComplianceState.NON_COMPLIANT, ComplianceState.CONTRADICTORY):
            self.alert_human(f"'{record.artifact.scope}' assessed {compliance.value}: {detail}")
        return record

    def compliance_of(self, scope: str) -> ComplianceState:
        """**Compliance Query** (21B §23.5). Read-only."""
        return self._compliance.get(scope, ComplianceState.AMBIGUOUS)

    # ---------------------------------------------------------- Ratification

    def request_review(self, artifact_id: str, deadline: timedelta) -> ArtifactRecord:
        record = self.get(artifact_id)
        record.review_requested_at = self.now()
        record.review_deadline = self.now() + deadline
        self._transition(record, ArtifactState.UNDER_REVIEW)
        self._record("review_requested", artifact_id=artifact_id)
        return record

    def ratify(self, token: str, artifact_id: str, note: str = "") -> ArtifactRecord:
        """Ratification Controller. G3 and G4 route to human confirmation.

        15 rule 2: no G4 amendment ratified without explicit human sovereign
        approval. G4 is human-only and cannot be delegated, so the check is on
        the ratifier's nature rather than on a permission they might hold.
        """
        principal_id, _tenant_id = self.authorizer.principal_of(token)
        record = self.get(artifact_id)
        if record.artifact.g_class >= GClass.G3 and not self.authorizer.is_human(principal_id):
            raise AgentOSError(
                f"'{principal_id}' is not a human principal; {record.artifact.g_class.name} ratification "
                "requires human confirmation (15 rule 2, 15.33.2)"
            )
        if principal_id == record.artifact.steward_id:
            raise IndependenceViolation(f"'{principal_id}' formed this artifact and may not also ratify it (15.25.4)")
        record.ratified_by = principal_id
        record.ratified_at = self.now()
        self._transition(record, ArtifactState.RATIFIED)
        self._record("ratified", artifact_id=artifact_id, by=principal_id, note=note)
        return record

    def activate(self, artifact_id: str) -> ArtifactRecord:
        record = self.get(artifact_id)
        self._transition(record, ArtifactState.ACTIVE)
        self._record("activated", artifact_id=artifact_id)
        return record

    def expire_reviews(self) -> list[ArtifactRecord]:
        """15.8.2 — "timeout without response (does NOT auto-ratify)".

        Structural: this method can produce Rejected or Escalated and nothing
        else. There is no argument, flag or condition that would make it
        produce Ratified.
        """
        expired: list[ArtifactRecord] = []
        now = self.now()
        for record in self._artifacts.values():
            deadline = record.review_deadline
            if record.state != ArtifactState.UNDER_REVIEW or deadline is None or deadline > now:
                continue
            if record.artifact.g_class >= GClass.G3:
                # 15.28.4 — escalation timeout escalates further, never ratifies.
                record.escalations += 1
                self._transition(record, ArtifactState.ESCALATED)
                self._record("escalated_on_timeout", artifact_id=record.artifact_id)
                self.alert_human(
                    f"{record.artifact.g_class.name} artifact '{record.artifact_id}' timed out in review "
                    "and has escalated; it has not been ratified (15.28.4)"
                )
            else:
                record.rejection_reason = "review deadline passed without response; timeout does not ratify (15.8.2)"
                self._transition(record, ArtifactState.REJECTED)
                self._record("rejected_on_timeout", artifact_id=record.artifact_id)
            expired.append(record)
        return expired

    # ---------------------------------------------------------- Interpretation

    def interpret(self, token: str, interpretation: Interpretation) -> Interpretation:
        """Interpretation Engine (15.19). Clarifies; does not amend.

        15.19.2 — an interpretation that would functionally alter constitutional
        meaning exceeds interpretation authority and must proceed as an
        amendment. Declared rather than inferred, and refused when declared.
        """
        principal_id, _tenant_id = self.authorizer.principal_of(token)
        if interpretation.interpretation_id in self._interpretations:
            raise AgentOSError(f"interpretation '{interpretation.interpretation_id}' already exists")
        if interpretation.alters_meaning:
            raise ValidationError(
                "an interpretation that would functionally alter constitutional meaning exceeds "
                "interpretation authority; it must proceed as a G4 amendment (15.19.2)"
            )
        if not interpretation.grounded_in:
            raise ValidationError(
                "an interpretation must be grounded in text, precedent, or mission (15.19.1); "
                "an ungrounded interpretation is an invention"
            )
        if interpretation.g_class >= GClass.G3 and not self.authorizer.is_human(principal_id):
            raise AgentOSError(f"{interpretation.g_class.name} interpretation requires human authority (15.9.1)")
        self._interpretations[interpretation.interpretation_id] = interpretation
        self._record(
            "interpreted",
            interpretation_id=interpretation.interpretation_id,
            provision=interpretation.provision,
        )
        return interpretation

    def interpretations_for(self, provision: str) -> list[Interpretation]:
        """**Interpretation Request** readback (21B §23.5)."""
        return [i for i in self._interpretations.values() if i.provision == provision]

    # ------------------------------------------------------ Policy hierarchy

    def form_policy(self, token: str, policy: Policy) -> Policy:
        """Policy Hierarchy Store plus Contradiction Detector (15.16, 15.17.1).

        Two rejections happen here rather than later: an orphaned policy
        (15.16.2) and one contradicting a higher layer (15.16.3). Both are
        cheaper to catch at formation than to unwind after emission.
        """
        principal_id, tenant_id = self.authorizer.principal_of(token)
        if policy.policy_id in self._policies:
            raise AgentOSError(f"policy '{policy.policy_id}' already exists")
        if tenant_id != policy.tenant_id:
            raise AgentOSError(f"'{principal_id}' may not form policies for tenant '{policy.tenant_id}'")
        if not policy.constitutional_lineage.strip():
            raise OrphanedPolicy(
                f"policy '{policy.policy_id}' traces to no constitutional provision; "
                "a policy without constitutional lineage is illegitimate (15.16.2)"
            )
        if not policy.sunset_condition.strip():
            raise ValidationError(
                f"policy '{policy.policy_id}' declares no sunset condition (15.17.1); "
                "a policy nobody planned to retire is a policy nobody will"
            )
        conflict = self._find_contradiction(policy)
        if conflict is not None:
            raise PolicyContradiction(
                f"policy '{policy.policy_id}' at layer {policy.layer.name} would permit what "
                f"'{conflict.policy_id}' at layer {conflict.layer.name} prohibits; "
                "a lower-layer policy contradicting a higher layer is void (15.16.3)"
            )
        self._policies[policy.policy_id] = policy
        self._record("policy_formed", policy_id=policy.policy_id, layer=policy.layer.name)
        return policy

    def activate_policy(self, policy_id: str) -> Policy:
        policy = self.policy(policy_id)
        policy.state = PolicyState.ACTIVE
        self._record("policy_activated", policy_id=policy_id)
        return policy

    def detect_contradictions(self) -> list[Policy]:
        """15.16.3 post-ratification: the lower policy is **automatically suspended**.

        Automatic, because the alternative is a period during which two
        contradictory policies are both active and subsystems are choosing
        between them.
        """
        suspended: list[Policy] = []
        for policy in list(self._policies.values()):
            if not policy.is_active:
                continue
            conflict = self._find_contradiction(policy)
            if conflict is None:
                continue
            policy.state = PolicyState.SUSPENDED
            policy.suspension_reason = (
                f"contradicts '{conflict.policy_id}' at higher layer {conflict.layer.name}; "
                "automatically suspended pending review (15.16.3)"
            )
            policy.review_due_at = self.now() + EMERGENCY_REVIEW_WINDOW
            suspended.append(policy)
            self._record("policy_suspended", policy_id=policy.policy_id, conflict=conflict.policy_id)
            self.signals.emit(
                SignalType.EVENT,
                "governance.policy.suspended",
                policy.tenant_id,
                policy_id=policy.policy_id,
                conflict=conflict.policy_id,
            )
        return suspended

    def _find_contradiction(self, policy: Policy) -> Policy | None:
        """A higher layer prohibiting what this policy permits."""
        for other in self._policies.values():
            if other.policy_id == policy.policy_id or other.state == PolicyState.RETIRED:
                continue
            if other.tenant_id != policy.tenant_id:
                continue
            if other.layer >= policy.layer:
                continue  # same or lower authority cannot bind this one
            if policy.permits & other.prohibits:
                return other
        return None

    def supersede_policy(self, policy_id: str, successor_id: str) -> Policy:
        """15.17.4 — "Supersession does not erase history"."""
        policy = self.policy(policy_id)
        successor = self.policy(successor_id)
        if successor.layer > policy.layer:
            raise ValidationError(
                f"'{successor_id}' at layer {successor.layer.name} may not supersede '{policy_id}' "
                f"at higher layer {policy.layer.name} (15.17.4)"
            )
        policy.state = PolicyState.SUPERSEDED
        policy.superseded_by = successor_id
        self._record("policy_superseded", policy_id=policy_id, by=successor_id)
        return policy

    def emergency_suspend_policy(self, policy_id: str, reason: str) -> Policy:
        """15.17.6 — immediate, but requires G3 review within 24 hours."""
        policy = self.policy(policy_id)
        policy.state = PolicyState.SUSPENDED
        policy.suspension_reason = reason
        policy.review_due_at = self.now() + EMERGENCY_REVIEW_WINDOW
        self._record("policy_emergency_suspended", policy_id=policy_id, reason=reason)
        self.alert_human(
            f"policy '{policy_id}' emergency-suspended: {reason}. G3 review is due within 24 hours (15.17.6)"
        )
        return policy

    def overdue_emergency_reviews(self) -> list[Policy]:
        now = self.now()
        return [
            p
            for p in self._policies.values()
            if p.state == PolicyState.SUSPENDED and p.review_due_at is not None and p.review_due_at < now
        ]

    def policy(self, policy_id: str) -> Policy:
        policy = self._policies.get(policy_id)
        if policy is None:
            raise NotFoundError(f"policy '{policy_id}' does not exist")
        return policy

    def applicable_policies(self, tenant_id: str, scope: str) -> list[Policy]:
        """**Policy Query** (21B §23.5), highest authority first."""
        return sorted(
            [
                p
                for p in self._policies.values()
                if p.tenant_id == tenant_id and p.is_active and (scope == p.scope or scope.startswith(f"{p.scope}/"))
            ],
            key=lambda p: p.layer,
        )

    # --------------------------------------------------------- Stewardship

    def assign_stewardship(self, token: str, stewardship: Stewardship) -> Stewardship:
        """15.23.2. Documented, time-bounded, revocable."""
        principal_id, _tenant_id = self.authorizer.principal_of(token)
        if stewardship.g_class.is_human_only and not self.authorizer.is_human(stewardship.principal_id):
            raise AgentOSError(
                f"'{stewardship.principal_id}' is not human; G4 stewardship cannot be delegated (15.9.1)"
            )
        if stewardship.expires_at <= self.now():
            raise ValidationError("a stewardship must be time-bounded into the future (15.23.2)")
        self._stewardships[stewardship.stewardship_id] = stewardship
        self._record(
            "stewardship_assigned",
            stewardship_id=stewardship.stewardship_id,
            principal=stewardship.principal_id,
            by=principal_id,
        )
        return stewardship

    def revoke_stewardship(self, stewardship_id: str, successor_id: str | None = None) -> Stewardship:
        """15.23.4 — revocation "triggers transfer of accountability"."""
        stewardship = self._stewardships.get(stewardship_id)
        if stewardship is None:
            raise NotFoundError(f"stewardship '{stewardship_id}' does not exist")
        stewardship.revoked_at = self.now()
        stewardship.successor_id = successor_id
        self._record("stewardship_revoked", stewardship_id=stewardship_id, successor=successor_id)
        if successor_id is None:
            # 21B §23.9 — a stewardship vacuum is Operational, and artifacts
            # under failed stewardship require revalidation. Named, not silent.
            self.alert_human(
                f"stewardship '{stewardship_id}' was revoked with no successor; "
                f"'{stewardship.scope}' now has a stewardship vacuum (15.23.4)"
            )
        return stewardship

    def accountability_chain(self, scope: str) -> list[Stewardship]:
        """**Stewardship Query** (21B §23.5). Every steward covering a scope."""
        now = self.now()
        return sorted(
            [s for s in self._stewardships.values() if s.is_active(now) and _covers(s.scope, scope)],
            key=lambda s: s.g_class,
            reverse=True,
        )

    def stewardship_vacuums(self, scopes: Sequence[str]) -> list[str]:
        return [scope for scope in scopes if not self.accountability_chain(scope)]

    def _steward_covers(self, principal_id: str, scope: str, g_class: GClass) -> bool:
        now = self.now()
        return any(
            s.principal_id == principal_id and s.is_active(now) and _covers(s.scope, scope) and s.g_class >= g_class
            for s in self._stewardships.values()
        )

    def _is_accountable_for(self, principal_id: str, scope: str) -> bool:
        now = self.now()
        return any(
            s.principal_id == principal_id and s.is_active(now) and _covers(s.scope, scope)
            for s in self._stewardships.values()
        )

    # ------------------------------------------------- Reviews and audits

    def conduct_review(
        self,
        token: str,
        finding_id: str,
        scope: str,
        kind: ReviewKind,
        compliance: ComplianceState,
        detail: str,
        evidence: EvidencePackage,
        recommendation: str = "",
    ) -> Finding:
        """Review Orchestrator and Audit Engine (15.25, 15.27).

        Independence is enforced **at assignment**: 15.25.4 forbids reviewing
        your own stewardship domain and 15.27.4 forbids auditing a scope you
        are accountable for. Refused here rather than flagged afterwards,
        because a compromised review is worth nothing once written.
        """
        principal_id, tenant_id = self.authorizer.principal_of(token)
        if self._is_accountable_for(principal_id, scope):
            raise IndependenceViolation(
                f"'{principal_id}' holds accountability for '{scope}' and may not review or audit it (15.25.4, 15.27.4)"
            )
        finding = Finding(
            finding_id=finding_id,
            tenant_id=tenant_id,
            scope=scope,
            kind=kind,
            compliance=compliance,
            detail=detail,
            evidence=evidence,
            auditor_id=principal_id,
            found_at=self.now(),
            recommendation=recommendation,
        )
        self._findings.append(finding)
        self._compliance[scope] = compliance
        self._record("finding", finding_id=finding_id, scope=scope, compliance=compliance.value)
        return finding

    def findings(self, scope: str | None = None) -> list[Finding]:
        """**Audit Finding** (21B §23.5)."""
        if scope is None:
            return list(self._findings)
        return [f for f in self._findings if f.scope == scope]

    # ------------------------------------------------------------ Exceptions

    def grant_exception(self, token: str, exception: Exception_) -> Exception_:
        """15.29. Time-bounded, scope-limited, risk-assessed, post-hoc reviewed.

        15 rule 17 makes all four mandatory, so all four are checked rather
        than assumed from the caller's diligence.
        """
        principal_id, _tenant_id = self.authorizer.principal_of(token)
        if exception.g_class.is_human_only and not self.authorizer.is_human(principal_id):
            raise AgentOSError(
                "an exception touching constitutional provisions or non-violable rules requires G4 "
                "human authority (15.29.2)"
            )
        if exception.expires_at <= exception.granted_at:
            raise ValidationError("an exception must be time-bounded (15 rule 17); it expires automatically")
        if not exception.recipient_scope.strip():
            raise ValidationError("an exception must be scope-limited (15 rule 17)")
        if not exception.risk_acknowledgment.strip():
            raise ValidationError("an exception must carry a risk acknowledgment (15.29.4)")
        if exception.post_hoc_review_due <= exception.granted_at:
            raise ValidationError("an exception must schedule its post-hoc review (15 rule 17)")
        self._exceptions[exception.exception_id] = exception
        self._record(
            "exception_granted",
            exception_id=exception.exception_id,
            scope=exception.recipient_scope,
            by=principal_id,
        )
        return exception

    def active_exceptions(self) -> list[Exception_]:
        now = self.now()
        return [e for e in self._exceptions.values() if e.is_active(now)]

    def overdue_exception_reviews(self) -> list[Exception_]:
        """15.29.3 — "Exceptions expire automatically and require explicit renewal."

        An expired exception whose post-hoc review never happened is the way a
        provisional deviation becomes a permanent one.
        """
        now = self.now()
        return [e for e in self._exceptions.values() if e.review_overdue(now)]

    def review_exception(self, token: str, exception_id: str) -> Exception_:
        principal_id, _tenant_id = self.authorizer.principal_of(token)
        exception = self._exceptions.get(exception_id)
        if exception is None:
            raise NotFoundError(f"exception '{exception_id}' does not exist")
        if principal_id == exception.granted_by:
            raise IndependenceViolation(
                f"'{principal_id}' granted this exception and may not conduct its post-hoc review (15.25.4)"
            )
        exception.reviewed_at = self.now()
        exception.reviewed_by = principal_id
        self._record("exception_reviewed", exception_id=exception_id, by=principal_id)
        return exception

    # ----------------------------------------------------------------- Drift

    def record_drift(self, scope: str, divergence: float) -> float:
        """Drift Detector (15.21). Velocity, not just position.

        15.2.6 calls Governance "the organizational immune system", existing to
        "detect, arrest, and reverse constitutional drift before organizational
        legitimacy collapses". A position measurement alone cannot tell you
        whether things are getting worse.
        """
        history = self._drift.setdefault(scope, [])
        history.append(round(divergence, 4))
        velocity = self.drift_velocity(scope)
        if velocity > DRIFT_VELOCITY_THRESHOLD:
            self._compliance[scope] = ComplianceState.DRIFTING
            self._record("drift_escalated", scope=scope, velocity=velocity)
            self.alert_human(f"'{scope}' drift velocity {velocity} exceeds {DRIFT_VELOCITY_THRESHOLD} (15.21)")
            self.escalate(
                EscalationTrigger.OVERSIGHT_LOSS,
                f"constitutional drift velocity {velocity} in '{scope}' exceeds the escalation threshold",
            )
        return velocity

    def drift_velocity(self, scope: str) -> float:
        history = self._drift.get(scope, [])
        if len(history) < 2:
            return 0.0
        return round(history[-1] - history[0], 4)

    # ------------------------------------------------------------- Overhead

    def record_cost(self, governance: float = 0.0, operational: float = 0.0) -> None:
        """21B §23.11 — "The Gateway must expose its own cost".

        CIR-008 asks whether 04.32's fifteen percent improvement cap bounds the
        aggregate oversight burden. It cannot be answered by assertion, so the
        cost is measured and reported rather than assumed acceptable.
        """
        self._governance_cost += governance
        self._operational_cost += operational

    def overhead_ratio(self) -> float:
        total = self._governance_cost + self._operational_cost
        if total <= 0:
            return 0.0
        return round(self._governance_cost / total, 4)

    # ---------------------------------------------------------------- Query

    def get(self, artifact_id: str) -> ArtifactRecord:
        record = self._artifacts.get(artifact_id)
        if record is None:
            raise NotFoundError(f"governance artifact '{artifact_id}' does not exist")
        return record

    def artifacts(self, state: ArtifactState | None = None) -> list[ArtifactRecord]:
        if state is None:
            return list(self._artifacts.values())
        return [r for r in self._artifacts.values() if r.state == state]

    def query_journal(self, artifact_id: str | None = None) -> list[Mapping[str, Any]]:
        payloads = [self.journal[i].payload for i in range(len(self.journal))]
        if artifact_id is None:
            return list(payloads)
        return [p for p in payloads if p.get("artifact_id") == artifact_id]

    # --------------------------------------------------------------- Health

    def health(self) -> Mapping[str, Any]:
        """The four metric families of 15.26 (21B §23.11)."""
        artifacts = list(self._artifacts.values())
        policies = list(self._policies.values())
        compliances = list(self._compliance.values())
        compliant = [c for c in compliances if c == ComplianceState.COMPLIANT]
        ratified = [r for r in artifacts if r.ratified_at is not None]
        overhead = self.overhead_ratio()
        return {
            "constitutional_health": {
                "compliance_rate": round(len(compliant) / len(compliances), 4) if compliances else 0.0,
                "ambiguity_rate": (
                    round(len([c for c in compliances if c == ComplianceState.AMBIGUOUS]) / len(compliances), 4)
                    if compliances
                    else 0.0
                ),
                "contradiction_rate": (
                    round(len([c for c in compliances if c == ComplianceState.CONTRADICTORY]) / len(compliances), 4)
                    if compliances
                    else 0.0
                ),
                "drift_velocity": {scope: self.drift_velocity(scope) for scope in self._drift},
            },
            "policy_vitality": {
                "policies": len(policies),
                "active": len([p for p in policies if p.is_active]),
                "suspended": len([p for p in policies if p.state == PolicyState.SUSPENDED]),
                "supersession_rate": (
                    round(len([p for p in policies if p.state == PolicyState.SUPERSEDED]) / len(policies), 4)
                    if policies
                    else 0.0
                ),
                # 15.16.2 — an orphan should be impossible; reported so the
                # claim is checkable rather than assumed.
                "orphan_rate": (
                    round(len([p for p in policies if not p.constitutional_lineage.strip()]) / len(policies), 4)
                    if policies
                    else 0.0
                ),
            },
            "legitimacy": {
                "stewardships": len([s for s in self._stewardships.values() if s.is_active(self.now())]),
                "ratifications": len(ratified),
                "escalations": sum(r.escalations for r in artifacts),
                "rejected_on_timeout": len([r for r in artifacts if "timeout" in r.rejection_reason]),
                # Structurally zero: no code path leads from a timeout to
                # Ratified (15.8.2).
                "ratified_on_timeout": 0,
                "findings": len(self._findings),
            },
            "overhead": {
                "governance_cost": round(self._governance_cost, 6),
                "operational_cost": round(self._operational_cost, 6),
                "overhead_ratio": overhead,
                "ceiling": GOVERNANCE_OVERHEAD_CEILING,
                # CIR-008 is open; the breach is reported, not resolved here.
                "circuit_breaker_breached": overhead > GOVERNANCE_OVERHEAD_CEILING,
            },
            "exceptions": {
                "active": len(self.active_exceptions()),
                "overdue_reviews": len(self.overdue_exception_reviews()),
            },
            "journal_entries": len(self.journal),
            "journal_intact": self.journal.verify_chain(),
        }

    # ------------------------------------------------------------ Internals

    def _transition(self, record: ArtifactRecord, target: ArtifactState) -> None:
        machine = LifecycleStateMachine(transitions=dict(GOVERNANCE_TRANSITIONS), state=record.state)
        machine.transition(target)
        record.state = target

    def _record(self, action: str, **detail: Any) -> None:
        self.journal.append({"kind": "governance", "action": action, **detail})


def _covers(steward_scope: str, scope: str) -> bool:
    """A steward's scope covers itself and everything beneath it."""
    return scope == steward_scope or scope.startswith(f"{steward_scope}/")
