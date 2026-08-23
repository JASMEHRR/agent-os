"""Memory entry identity, classification, and lifecycle states (09.4, 09.5, 09.9).

**Source note.** The ratified artifact for document 09 terminates mid-Section
10. Sections 10.1–30 are absent, including the Non-Violable Memory Rules and
the Glossary. Everything in this module derives from Sections 4–9, which *are*
present and complete, so the identity primitives, classification, tier
hierarchy, lifecycle and state machine below are constitutional rather than
inferred. Where a later section would have governed behaviour, this module
says so rather than inventing content (21B §16.1, §16.16).

Two invariants shape the types here:

**Anonymous memory is inadmissible** (09.4.3). Source identity, tenant and
lineage have no defaults — an entry that cannot say who produced it and what
occurrence it came from cannot be constructed.

**Validated entries are immutable in identity and payload** (09.9.3). The
payload is frozen at formation; lifecycle metadata (state, tier, confidence)
lives in a separate mutable record, so a state transition can never be a
back-door edit of history.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any

#: 09.4.2 — memory identity persists a minimum of seven years regardless of status.
IDENTITY_RETENTION = timedelta(days=365 * 7)

#: 09.9.2 — Draft -> Validated requires initial confidence >= 0.5.
MINIMUM_FORMATION_CONFIDENCE = 0.5


class SemanticRole(StrEnum):
    """Classification by semantic role (09.5.1)."""

    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    PROCEDURAL = "procedural"
    RELATIONAL = "relational"
    STRATEGIC = "strategic"
    FAILURE = "failure"


class StructuralForm(StrEnum):
    """Classification by structural form (09.5.2)."""

    ATOMIC = "atomic"
    COMPOSITE = "composite"
    NARRATIVE = "narrative"
    GRAPH_EDGE = "graph_edge"


class Sensitivity(StrEnum):
    """Classification by sensitivity (09.5.3)."""

    PUBLIC = "public"
    TENANT_SCOPED = "tenant_scoped"
    RESTRICTED = "restricted"


class Tier(StrEnum):
    """The four tiers of 09.7, in promotion order."""

    WORKING = "working"
    DURABLE = "durable"
    SEMANTIC = "semantic"
    COLD = "cold"


class Ownership(StrEnum):
    """Memory ownership tiers (06.11.1, referenced by 21B §16.2)."""

    PRIVATE = "private"
    TEAM = "team"
    BUSINESS = "business"
    GLOBAL = "global"


class MemoryState(StrEnum):
    """Canonical states of 09.9.1."""

    DRAFT = "draft"
    VALIDATED = "validated"
    LINKED = "linked"
    ACTIVE = "active"
    STALE = "stale"
    ARCHIVED = "archived"
    PURGED = "purged"


#: 09.9.2 Transition Guards, as a table the kernel's lifecycle engine enforces.
#: Quarantine is not a state in 09.9.1: a failing entry stays Draft and is held
#: by the Quarantine Store (21B §16.3), which is why no Quarantined state
#: appears here.
MEMORY_TRANSITIONS: dict[str, set[str]] = {
    MemoryState.DRAFT: {MemoryState.VALIDATED},
    MemoryState.VALIDATED: {MemoryState.LINKED},
    MemoryState.LINKED: {MemoryState.ACTIVE},
    MemoryState.ACTIVE: {MemoryState.STALE},
    MemoryState.STALE: {MemoryState.ACTIVE, MemoryState.ARCHIVED},
    MemoryState.ARCHIVED: {MemoryState.PURGED},
    MemoryState.PURGED: set(),
}


class EdgeType(StrEnum):
    """Relationship kinds the Integration Engine establishes (09.8.4)."""

    CAUSED_BY = "caused_by"
    CONTRADICTS = "contradicts"
    CORRECTS = "corrects"
    RELATES_TO = "relates_to"
    DERIVED_FROM = "derived_from"


@dataclass(frozen=True)
class Provenance:
    """The causal chain to the originating event or decision (09.4.1, 09.13)."""

    source_identity: str
    #: Immutable identifier linking to the originating event or decision journal.
    lineage_ref: str
    occurred_at: datetime
    workflow_id: str | None = None
    decision_id: str | None = None


@dataclass(frozen=True)
class MemoryEntry:
    """A formed memory entry. Identity and payload are frozen at formation.

    Formation imposes structure; it does not imply validation (09.8.2). An
    entry can be perfectly well-formed and wholly unreliable, which is why
    confidence lives on the mutable record rather than here.
    """

    memory_type: str
    role: SemanticRole
    form: StructuralForm
    payload: dict[str, Any]
    tenant_id: str
    business_id: str | None
    workspace_id: str | None
    owner_principal_id: str
    ownership: Ownership
    provenance: Provenance
    sensitivity: Sensitivity = Sensitivity.TENANT_SCOPED
    schema_version: str = "1.0.0"
    memory_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    #: When the producer constructed the capture. Distinct from when the
    #: Gateway formed it — retention and decay measure from the Gateway's
    #: clock (`MemoryRecord.formed_at`), never from a producer's.
    captured_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class MemoryRecord:
    """Mutable lifecycle metadata for one entry.

    Separated from `MemoryEntry` because 09.9.3 permits state, tier and
    confidence to change while the identity and payload may not. Keeping them
    in one object would make the immutability guarantee a matter of
    discipline; keeping them apart makes it a matter of types.
    """

    entry: MemoryEntry
    #: Assigned by the Formation Engine from the Gateway's clock. This is the
    #: authoritative formation instant: retention (09.4.2) and idle-decay both
    #: measure from here, so neither can be skewed by a producer's clock.
    formed_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    state: MemoryState = MemoryState.DRAFT
    tier: Tier = Tier.WORKING
    confidence: float = 0.0
    valid_until: datetime | None = None
    last_retrieved_at: datetime | None = None
    retrieval_count: int = 0
    #: Every confidence change, oldest first — 21B §16.8 retains the history.
    confidence_history: list[tuple[datetime, float]] = field(default_factory=list)
    quarantine_reason: str | None = None

    @property
    def memory_id(self) -> str:
        return self.entry.memory_id

    @property
    def retain_until(self) -> datetime:
        """09.4.2 — identity persists a minimum of seven years regardless of status."""
        return self.formed_at + IDENTITY_RETENTION

    @property
    def is_retrievable(self) -> bool:
        """09.8.5 — until activation an entry exists but is invisible to agents."""
        return self.state == MemoryState.ACTIVE

    def is_expired(self, now: datetime) -> bool:
        return self.valid_until is not None and now >= self.valid_until


@dataclass(frozen=True)
class MemoryEdge:
    """A typed relational or semantic link between two entries (09.12)."""

    source_id: str
    target_id: str
    edge_type: EdgeType
    created_at: datetime
    created_by: str
