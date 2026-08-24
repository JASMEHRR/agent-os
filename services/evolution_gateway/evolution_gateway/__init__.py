"""Evolution Gateway - specification-conformant, construction-blocked (21B 26).

The subsystem through which Agent OS changes itself deliberately rather than
accidentally. `19.2` draws the line against Learning: Learning adapts behaviour
**within** standing bounds; Evolution proposes changes **to** those bounds.

`19.3`: Evolution "packages; it does not ratify." The absence of any ratifying
verb here is what makes 19.16.2's unidirectional handoff structural, and it is
what resolves the Evolution/Governance circular dependency.

Construction is blocked by CIR-001, the third of the three subsystems 21A 3
names.
"""

from evolution_gateway.gateway import (
    CIR_001,
    CONSUMABLE_LEARNING_STATES,
    EVOLUTION_PIPELINE,
    ArtifactClass,
    ConstructionBlocked,
    EvolutionGateway,
    ProposalState,
    blocked,
    ratification_verbs,
)

__all__ = [
    "EvolutionGateway",
    "ArtifactClass",
    "ProposalState",
    "EVOLUTION_PIPELINE",
    "CONSUMABLE_LEARNING_STATES",
    "ConstructionBlocked",
    "CIR_001",
    "blocked",
    "ratification_verbs",
]
