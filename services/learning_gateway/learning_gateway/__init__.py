"""Learning Gateway - outcomes into validated, attributable improvement.

Realizes 13_LEARNING_OPERATING_MODEL in full, per 21B 21.

`13.2.1`: "Learning is the only subsystem whose output is change to the other
subsystems." Memory asks what happened; Knowledge asks what is true; Decision
asks what shall be done; Tool asks how to act; Learning asks how to become
better at all of these.

`13.2.3` draws its boundary: "Knowledge Gateway owns validation; Learning
Gateway owns proposal. Learning feeds the Knowledge pipeline; it does not
bypass it." Every propagation is a handoff, never an adoption.
"""

from learning_gateway.adapters import (
    CostManagerLearningBudget,
    GatewayProposalSink,
    SecurityGatewayLearningAuthorizer,
)
from learning_gateway.entries import (
    CONFIDENCE_FLOOR,
    CONFIDENCE_THRESHOLDS,
    DECAY_HALF_LIFE,
    DEPRECATION_FLOOR,
    EVIDENCE_SUFFICIENCY,
    FAILURE_PATTERN_MINIMUM,
    JOURNAL_RETENTION,
    LEARNING_TRANSITIONS,
    MEASUREMENT_WINDOWS,
    PROVISIONAL_CEILING,
    REQUIRES_HUMAN_RATIFICATION,
    SUCCESS_PATTERN_MINIMUM,
    Attribution,
    EvidenceRef,
    Hypothesis,
    LearningEntry,
    LearningState,
    Observation,
    Pattern,
    PatternKind,
    TargetClass,
    required_observations,
    summarize,
    threshold_for,
    window_for,
)
from learning_gateway.gateway import (
    NON_VIOLABLE_SUBJECTS,
    AttributionAnomaly,
    BudgetSource,
    ConsolidationPackage,
    FailureLibraryEntry,
    InsufficientEvidence,
    LearningAuthorizer,
    LearningGateway,
    NonViolableProposal,
    ProposalSink,
    loop_stages,
)
from learning_gateway.recursion import (
    SELF_EVIDENCE_KINDS,
    SELF_IDENTIFIERS,
    SELF_MODIFYING_PHRASES,
    RecursionAnomaly,
    RecursionFinding,
    RecursionGuard,
    normalize,
)

__all__ = [
    "LearningGateway",
    "LearningAuthorizer",
    "BudgetSource",
    "ProposalSink",
    "ConsolidationPackage",
    "FailureLibraryEntry",
    "InsufficientEvidence",
    "AttributionAnomaly",
    "NonViolableProposal",
    "NON_VIOLABLE_SUBJECTS",
    "loop_stages",
    "LearningEntry",
    "LearningState",
    "LEARNING_TRANSITIONS",
    "Hypothesis",
    "Observation",
    "Pattern",
    "PatternKind",
    "TargetClass",
    "Attribution",
    "EvidenceRef",
    "EVIDENCE_SUFFICIENCY",
    "CONFIDENCE_THRESHOLDS",
    "CONFIDENCE_FLOOR",
    "PROVISIONAL_CEILING",
    "MEASUREMENT_WINDOWS",
    "REQUIRES_HUMAN_RATIFICATION",
    "FAILURE_PATTERN_MINIMUM",
    "SUCCESS_PATTERN_MINIMUM",
    "DECAY_HALF_LIFE",
    "DEPRECATION_FLOOR",
    "JOURNAL_RETENTION",
    "threshold_for",
    "window_for",
    "required_observations",
    "summarize",
    "RecursionGuard",
    "RecursionAnomaly",
    "RecursionFinding",
    "SELF_IDENTIFIERS",
    "SELF_EVIDENCE_KINDS",
    "SELF_MODIFYING_PHRASES",
    "normalize",
    "SecurityGatewayLearningAuthorizer",
    "CostManagerLearningBudget",
    "GatewayProposalSink",
]
