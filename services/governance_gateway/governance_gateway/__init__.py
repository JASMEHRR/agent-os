"""Governance Gateway - the constitutional steward (document 15, per 21B 23).

`15.2.1`: "Governance is the guardian of the guardrails. It does not drive the
vehicle; it verifies that the vehicle remains on legitimate roads."

`15.6.1` establishes its exclusive authority: "No subsystem may self-certify
its own constitutional compliance."

It assesses what it does not own. Meta-oversight observes and never
intervenes: 15.22.3 permits Governance to declare a subsystem non-compliant
and forbids it modifying subsystem internals, so remediation is a requirement
recorded rather than an action taken.
"""

from governance_gateway.adapters import (
    ImmutableJournalSource,
    SecurityGatewayGovernanceAuthorizer,
)
from governance_gateway.artifacts import (
    DRIFT_VELOCITY_THRESHOLD,
    EMERGENCY_REVIEW_WINDOW,
    FAILURE_ALERT_BOUND,
    GOVERNANCE_OVERHEAD_CEILING,
    GOVERNANCE_TRANSITIONS,
    ArtifactRecord,
    ArtifactState,
    ComplianceState,
    EvidenceItem,
    EvidencePackage,
    Finding,
    GClass,
    GovernanceArtifact,
    Interpretation,
    Policy,
    PolicyLayer,
    PolicyState,
    ReviewKind,
    Stewardship,
    assert_confidence_for,
)
from governance_gateway.artifacts import Exception_ as GovernanceException
from governance_gateway.gateway import (
    NON_VIOLABLE_SUBJECTS,
    GovernanceAuthorizer,
    GovernanceGateway,
    IndependenceViolation,
    JournalSource,
    NonViolableViolation,
    OrphanedPolicy,
    PolicyContradiction,
    SelfCertification,
)

__all__ = [
    "GovernanceGateway",
    "GovernanceAuthorizer",
    "JournalSource",
    "SelfCertification",
    "IndependenceViolation",
    "NonViolableViolation",
    "OrphanedPolicy",
    "PolicyContradiction",
    "NON_VIOLABLE_SUBJECTS",
    "GovernanceArtifact",
    "ArtifactRecord",
    "ArtifactState",
    "GOVERNANCE_TRANSITIONS",
    "GClass",
    "ComplianceState",
    "PolicyLayer",
    "PolicyState",
    "Policy",
    "Interpretation",
    "Stewardship",
    "GovernanceException",
    "Finding",
    "ReviewKind",
    "EvidenceItem",
    "EvidencePackage",
    "assert_confidence_for",
    "EMERGENCY_REVIEW_WINDOW",
    "FAILURE_ALERT_BOUND",
    "GOVERNANCE_OVERHEAD_CEILING",
    "DRIFT_VELOCITY_THRESHOLD",
    "SecurityGatewayGovernanceAuthorizer",
    "ImmutableJournalSource",
]
