"""Knowledge Gateway — the organization's body of validated belief (21B §17).

Realizes document 10 in full.

`10.2.1` sets the bar: "A belief without evidence is speculation. A belief
without confidence is noise. A belief that cannot be falsified is dogma.
Knowledge rejects all three." All three rejections are structural here —
evidence and falsifiability conditions are required fields, and confidence is
assigned by validation rather than asserted by the producer.
"""

from knowledge_gateway.adapters import (
    MemoryGatewayEvidenceSource,
    SecurityGatewayKnowledgeAuthorizer,
)
from knowledge_gateway.beliefs import (
    ARBITRATION_CONFIDENCE,
    BELIEF_TRANSITIONS,
    CANONICAL_CEILING,
    HYPOTHESIS_CEILING,
    VALIDATED_CEILING,
    Belief,
    BeliefRecord,
    BeliefSensitivity,
    BeliefState,
    ConfidenceBand,
    Contradiction,
    Evidence,
    Falsifiability,
    ReconciliationStrategy,
    RelationType,
)
from knowledge_gateway.gateway import (
    BeliefAnswer,
    KnowledgeAccessDenied,
    KnowledgeAuthorizer,
    KnowledgeGateway,
    MemorySource,
    PromotionBlocked,
)
from knowledge_gateway.graph import (
    BeliefEdge,
    GraphEngine,
    GraphIntegrityError,
    OntologyManager,
    OntologyProposal,
    RatificationRequired,
)
from knowledge_gateway.pipeline import (
    ContradictionDetector,
    EpistemicFailure,
    ExtractionEngine,
    HypothesisQuarantined,
    HypothesisStore,
    ReconciliationEngine,
    ValidationEngine,
    revalidation_interval,
)

__all__ = [
    "KnowledgeGateway",
    "KnowledgeAuthorizer",
    "KnowledgeAccessDenied",
    "PromotionBlocked",
    "MemorySource",
    "BeliefAnswer",
    "Belief",
    "BeliefRecord",
    "BeliefState",
    "BELIEF_TRANSITIONS",
    "BeliefSensitivity",
    "ConfidenceBand",
    "Evidence",
    "Falsifiability",
    "Contradiction",
    "ReconciliationStrategy",
    "RelationType",
    "HYPOTHESIS_CEILING",
    "VALIDATED_CEILING",
    "CANONICAL_CEILING",
    "ARBITRATION_CONFIDENCE",
    "GraphEngine",
    "GraphIntegrityError",
    "BeliefEdge",
    "OntologyManager",
    "OntologyProposal",
    "RatificationRequired",
    "ExtractionEngine",
    "ValidationEngine",
    "HypothesisStore",
    "HypothesisQuarantined",
    "EpistemicFailure",
    "ContradictionDetector",
    "ReconciliationEngine",
    "revalidation_interval",
    "SecurityGatewayKnowledgeAuthorizer",
    "MemoryGatewayEvidenceSource",
]
