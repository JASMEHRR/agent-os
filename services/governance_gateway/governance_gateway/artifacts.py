"""Governance artifacts, the G-class spectrum, and the policy hierarchy (15.8, 15.9, 15.16).

`15.2.1` gives the subsystem its metaphor: "Governance is the guardian of the
guardrails. It does not drive the vehicle; it verifies that the vehicle remains
on legitimate roads."

Two hierarchies live here and their interaction is the module's whole shape:
the **authority** hierarchy G1 to G4 (15.9.1), and the **policy** hierarchy of
six layers (15.16.1). An artifact's required authority comes from its class and
scope; a policy's legitimacy comes from its lineage up the layers.

**Timeout never ratifies.** 15.8.2 specifies Under Review to Rejected on
"timeout without response (does NOT auto-ratify)". There is no transition from
a timeout to Ratified anywhere in this file, and none can be added without
editing `GOVERNANCE_TRANSITIONS` in a way a test would catch.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import IntEnum, StrEnum

from core.exceptions import ValidationError


class GClass(IntEnum):
    """15.9.1's authority spectrum. Ordered, so comparison is meaningful."""

    G1 = 1
    G2 = 2
    G3 = 3
    G4 = 4

    @property
    def is_human_only(self) -> bool:
        """15.9.1 — G4 is "Human only; no delegation to agents or automated systems"."""
        return self is GClass.G4

    @property
    def minimum_confidence(self) -> float:
        """15.9.2's confidence requirements by authority, verbatim.

        G4 has no numeric threshold: it "requires axiomatic or definitional
        backing plus human ratification", and confidence cannot substitute.
        """
        return {GClass.G1: 0.70, GClass.G2: 0.80, GClass.G3: 0.90, GClass.G4: 1.0}[self]


class ArtifactState(StrEnum):
    """15.8.1's canonical states, verbatim."""

    FORMED = "formed"
    UNDER_REVIEW = "under_review"
    INTERPRETED = "interpreted"
    RULED = "ruled"
    RATIFIED = "ratified"
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    RETIRED = "retired"
    REJECTED = "rejected"
    DEFERRED = "deferred"
    ESCALATED = "escalated"


GOVERNANCE_TRANSITIONS: dict[str, set[str]] = {
    ArtifactState.FORMED: {
        ArtifactState.UNDER_REVIEW,
        ArtifactState.INTERPRETED,
        ArtifactState.RULED,
        ArtifactState.REJECTED,
        ArtifactState.DEFERRED,
        ArtifactState.ESCALATED,
    },
    # 15.8.2 — "timeout without response (does NOT auto-ratify)". Ratified is
    # reachable from here only through an explicit human grant.
    ArtifactState.UNDER_REVIEW: {
        ArtifactState.RATIFIED,
        ArtifactState.REJECTED,
        ArtifactState.ESCALATED,
    },
    ArtifactState.INTERPRETED: {ArtifactState.RATIFIED, ArtifactState.REJECTED, ArtifactState.ESCALATED},
    ArtifactState.RULED: {ArtifactState.ACTIVE, ArtifactState.ESCALATED, ArtifactState.REJECTED},
    ArtifactState.RATIFIED: {ArtifactState.ACTIVE, ArtifactState.RETIRED},
    ArtifactState.ACTIVE: {ArtifactState.SUPERSEDED, ArtifactState.RETIRED, ArtifactState.ESCALATED},
    # 15.28.4 — escalation timeout escalates further rather than ratifying.
    ArtifactState.ESCALATED: {
        ArtifactState.RATIFIED,
        ArtifactState.REJECTED,
        ArtifactState.DEFERRED,
        ArtifactState.ESCALATED,
    },
    ArtifactState.DEFERRED: {ArtifactState.FORMED, ArtifactState.REJECTED, ArtifactState.RETIRED},
    ArtifactState.SUPERSEDED: set(),
    ArtifactState.RETIRED: set(),
    ArtifactState.REJECTED: set(),
}


class ComplianceState(StrEnum):
    """15.18.3's five states, verbatim."""

    COMPLIANT = "compliant"
    AMBIGUOUS = "ambiguous"
    CONTRADICTORY = "contradictory"
    DRIFTING = "drifting"
    NON_COMPLIANT = "non_compliant"


class PolicyLayer(IntEnum):
    """15.16.1's six layers. Lower number is higher authority.

    "Lower layers may elaborate but never contradict higher layers."
    """

    CONSTITUTIONAL = 1
    ORGANIZATIONAL = 2
    PORTFOLIO = 3
    BUSINESS = 4
    WORKSPACE = 5
    SUBSYSTEM = 6

    @property
    def is_constitutional(self) -> bool:
        return self is PolicyLayer.CONSTITUTIONAL


class PolicyState(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    SUPERSEDED = "superseded"
    RETIRED = "retired"


class ReviewKind(StrEnum):
    """15.25.1's four review types."""

    SCHEDULED = "scheduled"
    TRIGGERED = "triggered"
    POST_INCIDENT = "post_incident"
    SOVEREIGN = "sovereign"


#: 15.17.6 — an emergency policy suspension "requires G3 review within 24 hours".
EMERGENCY_REVIEW_WINDOW = timedelta(hours=24)

#: 15 rule 19 — governance failures classified and alerted within 60 seconds.
FAILURE_ALERT_BOUND = timedelta(seconds=60)

#: [Engineering Decision] 15.14.4 establishes a maximum governance overhead
#: ratio without a figure, and CIR-008 asks whether 04.32's fifteen percent
#: improvement cap bounds the aggregate oversight burden. Fifteen percent is
#: adopted as the working value **and reported**, so the question can be
#: answered empirically rather than assumed either way (21B §23.11).
GOVERNANCE_OVERHEAD_CEILING = 0.15

#: [Engineering Decision] 15.21 requires drift detection and escalation without
#: a threshold. Drift velocity above this escalates to the human sovereign.
DRIFT_VELOCITY_THRESHOLD = 0.25


@dataclass(frozen=True)
class EvidenceItem:
    """Canonical evidence for an assessment (15.12.1).

    15.12.1 restricts the basis to decision journals, security audit trails,
    validated learning entries, committed knowledge and tool execution records.
    `speculative` is carried explicitly so the rule can be enforced on the
    evidence rather than on the assembler's promise about it.
    """

    reference: str
    #: The subsystem journal this came from. 15.7.2 permits assembly directly
    #: from subsystem journals, which is what breaks the Governance to
    #: Observability cycle.
    source_journal: str
    observed_at: datetime
    summary: str
    speculative: bool = False


@dataclass(frozen=True)
class EvidencePackage:
    """What the Evidence Assembler produced, including what it could not find."""

    items: tuple[EvidenceItem, ...]
    #: 15 rule 1 — an artifact carries documented evidence **or a gap flag**.
    #: Silence about a gap is what makes an assessment look better than it is.
    gaps: tuple[str, ...] = ()

    @property
    def canonical(self) -> tuple[EvidenceItem, ...]:
        return tuple(item for item in self.items if not item.speculative)

    @property
    def has_gaps(self) -> bool:
        return bool(self.gaps)


@dataclass(frozen=True)
class GovernanceArtifact:
    """The immutable core of an artifact (15.8.3).

    Once Ratified or Active, "core identity, evidence, and rationale are
    immutable... Corrections append new artifacts; they do not mutate ratified
    records." So the immutable half is frozen here and the lifecycle metadata
    lives in `ArtifactRecord`.
    """

    artifact_id: str
    tenant_id: str
    #: 15.23.3 — "No governance artifact exists without an accountable steward."
    steward_id: str
    g_class: GClass
    scope: str
    subject: str
    rationale: str
    evidence: EvidencePackage
    formed_at: datetime
    #: Set when this artifact supersedes another; lineage is never erased.
    supersedes: str | None = None


@dataclass
class ArtifactRecord:
    """Lifecycle metadata around a frozen artifact."""

    artifact: GovernanceArtifact
    state: ArtifactState = ArtifactState.FORMED
    confidence: float = 0.0
    compliance: ComplianceState | None = None
    ruling: str = ""
    remediation: str = ""
    ratified_by: str | None = None
    ratified_at: datetime | None = None
    rejection_reason: str = ""
    #: Set when review was requested, so a timeout is measurable.
    review_requested_at: datetime | None = None
    review_deadline: datetime | None = None
    escalations: int = 0
    #: 15.12.4 — an assessment permitted despite thin evidence carries a rider.
    uncertainty_rider: str = ""

    @property
    def artifact_id(self) -> str:
        return self.artifact.artifact_id

    @property
    def is_binding(self) -> bool:
        return self.state in (ArtifactState.RATIFIED, ArtifactState.ACTIVE)

    @property
    def is_terminal(self) -> bool:
        return self.state in (
            ArtifactState.SUPERSEDED,
            ArtifactState.RETIRED,
            ArtifactState.REJECTED,
        )


@dataclass
class Policy:
    """One policy in the six-layer hierarchy (15.16, 15.17)."""

    policy_id: str
    tenant_id: str
    layer: PolicyLayer
    scope: str
    statement: str
    #: 15.16.2 — "A policy without constitutional lineage is illegitimate."
    #: The provision this traces to, e.g. "14.12.4".
    constitutional_lineage: str
    steward_id: str
    #: 15.17.1 requires a sunset condition at formation.
    sunset_condition: str
    risk_assessment: str
    expected_outcome: str
    formed_at: datetime
    state: PolicyState = PolicyState.DRAFT
    #: What this policy forbids, used for contradiction detection.
    prohibits: frozenset[str] = field(default_factory=frozenset)
    #: What this policy permits. A lower layer permitting what a higher layer
    #: prohibits is the contradiction 15.16.3 makes void.
    permits: frozenset[str] = field(default_factory=frozenset)
    superseded_by: str | None = None
    suspension_reason: str = ""
    review_due_at: datetime | None = None

    @property
    def is_active(self) -> bool:
        return self.state == PolicyState.ACTIVE


@dataclass(frozen=True)
class Interpretation:
    """An authoritative resolution of constitutional ambiguity (15.19).

    `15.19.1`: interpretations are "binding on their scope but remain
    subordinate to the constitutional text, and are superseded if the text is
    later amended to resolve the ambiguity."
    """

    interpretation_id: str
    tenant_id: str
    question: str
    provision: str
    resolution: str
    grounded_in: tuple[str, ...]
    g_class: GClass
    scope: str
    interpreted_by: str
    interpreted_at: datetime
    #: 15.19.2 — an interpretation that would functionally alter constitutional
    #: meaning exceeds interpretation authority and must proceed as an amendment.
    alters_meaning: bool = False


@dataclass
class Stewardship:
    """A principal accountable for a scope's constitutional integrity (15.23)."""

    stewardship_id: str
    tenant_id: str
    principal_id: str
    scope: str
    g_class: GClass
    assigned_at: datetime
    expires_at: datetime
    revoked_at: datetime | None = None
    successor_id: str | None = None

    def is_active(self, at: datetime) -> bool:
        return self.revoked_at is None and at < self.expires_at


@dataclass
class Exception_:
    """A time-bounded, scope-limited deviation (15.29).

    Named with a trailing underscore because `Exception` is taken; exported as
    `GovernanceException`.
    """

    exception_id: str
    tenant_id: str
    granted_by: str
    g_class: GClass
    recipient_scope: str
    deviation: str
    risk_acknowledgment: str
    granted_at: datetime
    expires_at: datetime
    #: 15 rule 17 — post-hoc review is mandatory, so its deadline is a field
    #: rather than an intention.
    post_hoc_review_due: datetime
    reviewed_at: datetime | None = None
    reviewed_by: str | None = None

    def is_active(self, at: datetime) -> bool:
        return at < self.expires_at

    def review_overdue(self, at: datetime) -> bool:
        return self.reviewed_at is None and at > self.post_hoc_review_due


@dataclass(frozen=True)
class Finding:
    """One documented audit or review result (15.25.3, 15.27.3)."""

    finding_id: str
    tenant_id: str
    scope: str
    kind: ReviewKind
    compliance: ComplianceState
    detail: str
    evidence: EvidencePackage
    auditor_id: str
    found_at: datetime
    recommendation: str = ""


def assert_confidence_for(g_class: GClass, confidence: float) -> None:
    """15.9.2, applied as a gate rather than as advice."""
    if not 0.0 <= confidence <= 1.0:
        raise ValidationError(f"confidence must be between 0 and 1, got {confidence}")
    if confidence < g_class.minimum_confidence:
        raise ValidationError(
            f"{g_class.name} requires confidence {g_class.minimum_confidence}, got {confidence} (15.9.2)"
        )
