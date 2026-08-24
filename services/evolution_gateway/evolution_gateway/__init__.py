"""Evolution Gateway — how the system changes itself deliberately (19, per 21B §26).

**Construction authorized 2026-08-24** by G4 ruling on CIR-001
(`docs/rulings/CIR-001.md`).

`19.2` draws the line against Learning: Learning adapts behaviour **within**
standing bounds; Evolution proposes changes **to** those bounds.

`19.3` is unchanged by the ruling and is the module's shape: Evolution
"packages; it does not ratify." There is no ratifying verb here and a test
asserts there never will be. That absence resolves the Evolution/Governance
circular dependency — the edge back does not exist, so the handoff of 19.16.2
is unidirectional by construction rather than by agreement.
"""

from evolution_gateway.gateway import (
    CIR_001,
    CONSUMABLE_LEARNING_STATES,
    EVOLUTION_PIPELINE,
    PROPOSAL_TRANSITIONS,
    SELF_IDENTIFIERS,
    ArtifactClass,
    CompensationPlan,
    ConstructionBlocked,
    EvolutionGateway,
    GovernanceIntake,
    ImpactAssessment,
    LearningEvidence,
    Proposal,
    ProposalState,
    RecursionAnomaly,
    ratification_verbs,
)

__all__ = [
    "EvolutionGateway",
    "Proposal",
    "ProposalState",
    "PROPOSAL_TRANSITIONS",
    "ArtifactClass",
    "LearningEvidence",
    "ImpactAssessment",
    "CompensationPlan",
    "GovernanceIntake",
    "RecursionAnomaly",
    "EVOLUTION_PIPELINE",
    "CONSUMABLE_LEARNING_STATES",
    "SELF_IDENTIFIERS",
    "ratification_verbs",
    "ConstructionBlocked",
    "CIR_001",
]
