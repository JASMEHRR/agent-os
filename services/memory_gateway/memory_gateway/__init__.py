"""Memory Gateway — sole access layer for organizational experience (21B §16).

Realizes document 09 as far as its ratified artifact extends, plus 02.3.5.

**Source gap.** The artifact for 09 terminates mid-Section 10. Sections 10.1
through 30 are absent, including the Non-Violable Memory Rules and the
Performance Characteristics. Sections 4-9 — identity, classification, the four
tiers, the lifecycle and the state machine — are complete, and this module is
built on them. Performance figures are provisional, derived from the Knowledge
Gateway's published budgets per 21B §16.12, and are superseded the moment the
source is recovered. The missing Non-Violable Rules mean this module's
conformance suite cannot claim completeness; that is recorded in the Journal
as an open item rather than papered over.

`09.6.1`: no agent, workflow, or service accesses memory directly.
"""

from memory_gateway.entries import (
    IDENTITY_RETENTION,
    MEMORY_TRANSITIONS,
    MINIMUM_FORMATION_CONFIDENCE,
    EdgeType,
    MemoryEdge,
    MemoryEntry,
    MemoryRecord,
    MemoryState,
    Ownership,
    Provenance,
    SemanticRole,
    Sensitivity,
    StructuralForm,
    Tier,
)
from memory_gateway.gateway import (
    DispositionRefused,
    MemoryAccessDenied,
    MemoryAuthorizer,
    MemoryGateway,
    RetrievalResult,
)
from memory_gateway.pipeline import (
    AdmissionController,
    AdmissionRejected,
    DecayEngine,
    FormationEngine,
    IntegrationEngine,
    Quarantined,
    QuarantineStore,
    ValidationEngine,
)
from memory_gateway.security_adapter import SecurityGatewayMemoryAuthorizer

__all__ = [
    "MemoryGateway",
    "MemoryAuthorizer",
    "MemoryAccessDenied",
    "DispositionRefused",
    "RetrievalResult",
    "MemoryEntry",
    "MemoryRecord",
    "MemoryEdge",
    "MemoryState",
    "MEMORY_TRANSITIONS",
    "Provenance",
    "SemanticRole",
    "StructuralForm",
    "Sensitivity",
    "Tier",
    "Ownership",
    "EdgeType",
    "IDENTITY_RETENTION",
    "MINIMUM_FORMATION_CONFIDENCE",
    "AdmissionController",
    "AdmissionRejected",
    "FormationEngine",
    "ValidationEngine",
    "QuarantineStore",
    "Quarantined",
    "IntegrationEngine",
    "DecayEngine",
    "SecurityGatewayMemoryAuthorizer",
]
