"""Formation, validation, integration and decay (21B §16.3, realizes 09.8).

The lifecycle is Conception → Formation → Validation → Integration →
Activation → Decay → Disposition, and three separations in it are load-bearing
enough to be structural here rather than conventional:

**Formation is not validation** (09.8.2). The Formation Engine imposes
structure; the Validation Engine assesses reliability. An entry may be
well-formed and unreliable, so the two are separate objects with separate
failure modes — formation rejects at admission, validation quarantines.

**Integration is mandatory before activation** (09.8.4). "An unlinked memory
entry is incomplete." Activation is gated on at least one edge existing, so an
entry nobody linked is invisible to retrieval by construction, not by policy.

**Decay is degradation, not deletion** (09.8.6). The Decay Engine reduces
confidence and moves entries toward Cold. It has no delete path at all.
Deletion is Disposition, and Disposition to Purged needs both statutory expiry
and explicit approval (09.9.2).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from core.exceptions import ValidationError
from memory_gateway.entries import (
    MINIMUM_FORMATION_CONFIDENCE,
    EdgeType,
    MemoryEdge,
    MemoryEntry,
    MemoryRecord,
    MemoryState,
    Sensitivity,
    Tier,
)

#: [Engineering Decision] 09's decay section is present but publishes no rate.
#: Confidence decays by this fraction per elapsed validity period, so an entry
#: that outlives its validity window loses reliability rather than silently
#: retaining the confidence it was formed with.
DECAY_FACTOR_PER_PERIOD = 0.25

#: [Engineering Decision] 09.9.2 makes "no retrieval for defined duration" a
#: Stale trigger without defining the duration. Ninety days is a starting
#: value, overridable per Gateway.
DEFAULT_IDLE_BEFORE_STALE = timedelta(days=90)

#: [Engineering Decision] Default validity window at formation. 09 assigns a
#: validity period at validation but publishes no default.
DEFAULT_VALIDITY = timedelta(days=365)


class AdmissionRejected(ValidationError):
    """Formation request failed schema, attribution or scope checks (09.8.2)."""


class Quarantined(Exception):
    """Validation failed. The entry is held for review, never destroyed (09.8.3)."""

    def __init__(self, memory_id: str, reason: str):
        super().__init__(f"memory '{memory_id}' quarantined: {reason}")
        self.memory_id = memory_id
        self.reason = reason


@dataclass
class AdmissionController:
    """Validates formation requests against schema, attribution and scope.

    Rejects rather than quarantines: an unstructured or unattributed capture
    never becomes an entry at all, so there is nothing to hold for review.
    """

    def admit(self, entry: MemoryEntry) -> None:
        if not entry.provenance.source_identity:
            raise AdmissionRejected("anonymous memory is inadmissible (09.4.3)")
        if not entry.provenance.lineage_ref:
            raise AdmissionRejected(
                "every entry must trace to its originating event or decision (09.4.1, lineage reference)"
            )
        if not entry.tenant_id:
            raise AdmissionRejected("memory must declare its tenant isolation boundary (09.6.3)")
        if not entry.payload:
            raise AdmissionRejected("raw data is not memory until formed; an empty payload has no structure (09.2.2)")
        if not entry.memory_type or "." not in entry.memory_type:
            raise AdmissionRejected(
                f"memory type '{entry.memory_type}' must be hierarchical, e.g. 'episodic.execution' (09.4.1)"
            )


@dataclass
class FormationEngine:
    """Constructs structured entries with full identity and provenance (09.8.2)."""

    admission: AdmissionController
    now: Callable[[], datetime] = field(default=lambda: datetime.now(UTC))

    def form(self, entry: MemoryEntry) -> MemoryRecord:
        self.admission.admit(entry)
        return MemoryRecord(entry=entry, formed_at=self.now(), state=MemoryState.DRAFT, tier=Tier.WORKING)


@dataclass
class QuarantineStore:
    """Holds entries failing validation for review; invisible to retrieval.

    21B §16.8: quarantine holdings are "retained pending review; never silently
    discarded". There is no method here that drops an entry — release requires
    a corrected resubmission, and rejection is an explicit, reasoned act.
    """

    _held: dict[str, MemoryRecord] = field(default_factory=dict, init=False)
    _rejected: dict[str, str] = field(default_factory=dict, init=False)

    def hold(self, record: MemoryRecord, reason: str) -> MemoryRecord:
        record.quarantine_reason = reason
        self._held[record.memory_id] = record
        return record

    def release(self, memory_id: str) -> MemoryRecord:
        """Releases a corrected entry back into the pipeline."""
        record = self._held.pop(memory_id, None)
        if record is None:
            raise ValidationError(f"memory '{memory_id}' is not in quarantine")
        record.quarantine_reason = None
        return record

    def reject(self, memory_id: str, justification: str) -> None:
        """Permanent rejection, with the justification logged (09.8.3 by analogy to 10.14.4)."""
        self._held.pop(memory_id, None)
        self._rejected[memory_id] = justification

    def held(self) -> list[MemoryRecord]:
        return list(self._held.values())

    @property
    def depth(self) -> int:
        return len(self._held)

    def rejection_reason(self, memory_id: str) -> str | None:
        return self._rejected.get(memory_id)


@dataclass
class ValidationEngine:
    """Assesses reliability and assigns confidence and validity (09.8.3).

    Four dimensions, per 09.8.3: source reliability, cross-reference
    consistency, schema conformance, temporal relevance.
    """

    quarantine: QuarantineStore
    now: Callable[[], datetime] = field(default=lambda: datetime.now(UTC))
    #: Resolves how far a source's assertions can be trusted, 0.0-1.0.
    #: Injected because source reliability is an organizational judgement the
    #: Memory Gateway does not own — the Learning Gateway (S9) refines it.
    source_reliability: Callable[[str], float] = field(default=lambda _source: 0.8)
    default_validity: timedelta = DEFAULT_VALIDITY

    def validate(self, record: MemoryRecord, known_types: set[str] | None = None) -> MemoryRecord:
        """Assigns confidence and validity, or quarantines. Never destroys."""
        entry = record.entry
        reasons: list[str] = []

        reliability = self.source_reliability(entry.provenance.source_identity)
        if not 0.0 <= reliability <= 1.0:
            reasons.append(f"source reliability {reliability} is outside 0.0-1.0")

        if known_types is not None and entry.memory_type not in known_types:
            reasons.append(f"memory type '{entry.memory_type}' is not a registered schema")

        now = self.now()
        if entry.provenance.occurred_at > now:
            reasons.append("the occurrence is in the future; temporal relevance cannot be assessed")

        confidence = round(reliability, 4)
        if confidence < MINIMUM_FORMATION_CONFIDENCE:
            reasons.append(
                f"confidence {confidence} is below the {MINIMUM_FORMATION_CONFIDENCE} required "
                "for Draft -> Validated (09.9.2)"
            )

        if reasons:
            self.quarantine.hold(record, "; ".join(reasons))
            raise Quarantined(record.memory_id, "; ".join(reasons))

        record.confidence = confidence
        record.confidence_history.append((now, confidence))
        record.valid_until = now + self.default_validity
        record.state = MemoryState.VALIDATED
        record.tier = Tier.DURABLE  # 09.7.5 — promoted to Durable when validated
        return record


@dataclass
class IntegrationEngine:
    """Establishes causal chains, detects contradiction, creates edges (09.8.4)."""

    now: Callable[[], datetime] = field(default=lambda: datetime.now(UTC))
    _edges: list[MemoryEdge] = field(default_factory=list, init=False)
    _by_source: dict[str, list[MemoryEdge]] = field(default_factory=dict, init=False)
    _by_target: dict[str, list[MemoryEdge]] = field(default_factory=dict, init=False)

    def link(self, source_id: str, target_id: str, edge_type: EdgeType, created_by: str) -> MemoryEdge:
        if source_id == target_id:
            raise ValidationError("a memory entry may not link to itself")
        edge = MemoryEdge(
            source_id=source_id,
            target_id=target_id,
            edge_type=edge_type,
            created_at=self.now(),
            created_by=created_by,
        )
        self._edges.append(edge)
        self._by_source.setdefault(source_id, []).append(edge)
        self._by_target.setdefault(target_id, []).append(edge)
        return edge

    def integrate(self, record: MemoryRecord, edges: list[tuple[str, EdgeType]], created_by: str) -> MemoryRecord:
        """Links an entry and advances it to Linked. At least one edge is required."""
        if record.state != MemoryState.VALIDATED:
            raise ValidationError(
                f"memory '{record.memory_id}' is {record.state.value}; only a Validated entry may be integrated"
            )
        if not edges:
            raise ValidationError(f"memory '{record.memory_id}' has no edges; an unlinked entry is incomplete (09.8.4)")
        for target_id, edge_type in edges:
            self.link(record.memory_id, target_id, edge_type, created_by)
        record.state = MemoryState.LINKED
        record.tier = Tier.SEMANTIC  # 09.7.5 — promoted to Semantic when linked
        return record

    def edges_from(self, memory_id: str) -> list[MemoryEdge]:
        return list(self._by_source.get(memory_id, []))

    def edges_to(self, memory_id: str) -> list[MemoryEdge]:
        return list(self._by_target.get(memory_id, []))

    def neighbours(self, memory_id: str) -> list[str]:
        outgoing = [e.target_id for e in self.edges_from(memory_id)]
        incoming = [e.source_id for e in self.edges_to(memory_id)]
        return sorted(set(outgoing + incoming))

    def contradictions(self, memory_id: str) -> list[str]:
        """Entries this one is recorded as contradicting, in either direction."""
        return sorted(
            {e.target_id for e in self.edges_from(memory_id) if e.edge_type == EdgeType.CONTRADICTS}
            | {e.source_id for e in self.edges_to(memory_id) if e.edge_type == EdgeType.CONTRADICTS}
        )

    def is_linked(self, memory_id: str) -> bool:
        return bool(self._by_source.get(memory_id) or self._by_target.get(memory_id))

    @property
    def edge_count(self) -> int:
        return len(self._edges)


@dataclass
class DecayEngine:
    """Progressive reduction of relevance, confidence and accessibility (09.8.6).

    There is deliberately no delete method on this class. Decay degrades;
    deletion is Disposition, which lives on the Gateway and requires statutory
    expiry plus explicit approval.
    """

    now: Callable[[], datetime] = field(default=lambda: datetime.now(UTC))
    idle_before_stale: timedelta = DEFAULT_IDLE_BEFORE_STALE
    decay_factor: float = DECAY_FACTOR_PER_PERIOD
    #: Below this, an Active entry is flagged Stale for review (09.9.2).
    stale_confidence_threshold: float = MINIMUM_FORMATION_CONFIDENCE
    decayed_count: int = field(default=0, init=False)

    def should_stale(self, record: MemoryRecord) -> str | None:
        """The three Active -> Stale triggers of 09.9.2, or None."""
        now = self.now()
        if record.is_expired(now):
            return "validity period expired"
        if record.confidence < self.stale_confidence_threshold:
            return f"confidence decayed below {self.stale_confidence_threshold}"
        last_seen = record.last_retrieved_at or record.formed_at
        if now - last_seen >= self.idle_before_stale:
            return f"no retrieval for {self.idle_before_stale.days} days"
        return None

    def decay(self, record: MemoryRecord) -> MemoryRecord:
        """Reduces confidence for an entry past its validity window."""
        now = self.now()
        if record.valid_until is None or now < record.valid_until:
            return record
        reduced = round(max(0.0, record.confidence * (1.0 - self.decay_factor)), 4)
        if reduced != record.confidence:
            record.confidence = reduced
            record.confidence_history.append((now, reduced))
            self.decayed_count += 1
        return record

    def sweep(self, records: list[MemoryRecord]) -> list[MemoryRecord]:
        """Decays and flags. Returns the records that became Stale.

        Restricted entries decay like any other — sensitivity governs who may
        read an entry, never whether it ages.
        """
        became_stale: list[MemoryRecord] = []
        for record in records:
            if record.state not in (MemoryState.ACTIVE, MemoryState.LINKED):
                continue
            self.decay(record)
            if record.state == MemoryState.ACTIVE and self.should_stale(record) is not None:
                record.state = MemoryState.STALE
                became_stale.append(record)
        return became_stale


def sensitivity_ceiling(sensitivity: Sensitivity) -> int:
    """Ordering for the sensitivity filter applied at retrieval (09.5.3)."""
    return {Sensitivity.PUBLIC: 0, Sensitivity.TENANT_SCOPED: 1, Sensitivity.RESTRICTED: 2}[sensitivity]
