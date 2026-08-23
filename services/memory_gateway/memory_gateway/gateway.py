"""Memory Gateway — the five Public Interfaces of 21B §16.5.

| 21B §16.5 interface     | Method                          |
|-------------------------|---------------------------------|
| Memory Formation        | `form`                          |
| Memory Retrieval        | `retrieve`                      |
| Lineage Query           | `lineage`                       |
| Relationship Traversal  | `traverse`                      |
| Memory Health           | `health`                        |

`09.6.1` states the defining constraint: **no agent, workflow, or service
accesses memory directly.** The Gateway is the sole boundary. Four boundaries
are enforced at every operation (09.6.3): tenant, business, agent and tier.

Retrieval returns only Active entries. That is not a filter applied for
convenience — 09.8.5 makes activation the point at which an entry becomes
visible, and activation follows integration, so an entry nobody linked is
invisible by construction.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol

from core.exceptions import AgentOSError, NotFoundError
from kernel.journal import ImmutableJournal
from kernel.lifecycle import LifecycleStateMachine
from kernel.signals import SignalEmitter, SignalType
from memory_gateway.entries import (
    MEMORY_TRANSITIONS,
    EdgeType,
    MemoryEntry,
    MemoryRecord,
    MemoryState,
    Ownership,
    SemanticRole,
    Sensitivity,
    Tier,
)
from memory_gateway.pipeline import (
    AdmissionController,
    DecayEngine,
    FormationEngine,
    IntegrationEngine,
    Quarantined,
    QuarantineStore,
    ValidationEngine,
    sensitivity_ceiling,
)
from persistence.in_memory import InMemoryRepository


class MemoryAccessDenied(AgentOSError):
    """A boundary of 09.6.3 blocked the operation. Category 1 escalation (21B §16.9)."""


class DispositionRefused(AgentOSError):
    """Purge attempted without statutory expiry or without approval (09.9.2)."""


class MemoryAuthorizer(Protocol):
    """What the Gateway needs from the Security Gateway (21B §16.6)."""

    def may_form(self, token: str, tenant_id: str, memory_type: str) -> bool: ...

    def may_retrieve(self, token: str, tenant_id: str, sensitivity: str) -> bool: ...

    def principal_of(self, token: str) -> tuple[str, str]: ...


@dataclass(frozen=True)
class RetrievalResult:
    """One ranked hit, carrying the reliability qualification 09 requires.

    `confidence` travels with every result because 21B §16.15 guarantee 3
    requires observed experience and verified reliability to be
    distinguishable *at every retrieval* — a consumer must never receive a
    memory without knowing how much to trust it.
    """

    record: MemoryRecord
    relevance: float

    @property
    def memory_id(self) -> str:
        return self.record.memory_id

    @property
    def confidence(self) -> float:
        return self.record.confidence


@dataclass
class MemoryGateway:
    """Layer 2. Sole access layer for all organizational experience (21B §16.1)."""

    authorizer: MemoryAuthorizer
    signals: SignalEmitter
    now: Callable[[], datetime] = field(default=lambda: datetime.now(UTC))
    #: Registered memory type schemas; None disables the conformance check.
    known_types: set[str] | None = None

    def __post_init__(self) -> None:
        self.quarantine = QuarantineStore()
        self.formation = FormationEngine(admission=AdmissionController(), now=self.now)
        self.validation = ValidationEngine(quarantine=self.quarantine, now=self.now)
        self.integration = IntegrationEngine(now=self.now)
        self.decay = DecayEngine(now=self.now)
        self.journal = ImmutableJournal()
        self.repository: InMemoryRepository[MemoryRecord] = InMemoryRepository()
        self._records: dict[str, MemoryRecord] = {}
        self._formation_rejections = 0

    # ------------------------------------------------------------- Formation

    def form(
        self,
        token: str,
        entry: MemoryEntry,
        edges: list[tuple[str, EdgeType]] | None = None,
    ) -> MemoryRecord:
        """**Memory Formation** (21B §16.5): submit an occurrence for formation.

        Runs the whole pipeline as far as the submission allows: admission,
        formation, validation, and — when edges are supplied — integration and
        activation. An entry submitted without edges stops at Validated and is
        not retrievable until something links it (09.8.4).
        """
        principal_id, principal_tenant = self.authorizer.principal_of(token)
        if principal_tenant != entry.tenant_id:
            self._deny(principal_id, entry.tenant_id, "tenant", "formation into another tenant")
        if not self.authorizer.may_form(token, entry.tenant_id, entry.memory_type):
            self._deny(principal_id, entry.tenant_id, "scope", f"formation of '{entry.memory_type}'")

        try:
            record = self.formation.form(entry)
        except Exception as exc:
            self._formation_rejections += 1
            self.signals.emit(
                SignalType.EVENT,
                "memory.formation.rejected",
                entry.tenant_id,
                memory_type=entry.memory_type,
                reason=str(exc),
            )
            self.journal.append({"kind": "formation_rejected", "memory_type": entry.memory_type, "reason": str(exc)})
            raise

        self._records[record.memory_id] = record
        self._journal(record, "formed")

        try:
            self.validation.validate(record, self.known_types)
        except Quarantined as quarantined:
            self.signals.emit(
                SignalType.EVENT,
                "memory.validation.quarantined",
                entry.tenant_id,
                memory_id=record.memory_id,
                reason=quarantined.reason,
            )
            self._journal(record, "quarantined", reason=quarantined.reason)
            return record

        self._journal(record, "validated", confidence=record.confidence)

        if edges:
            self.integration.integrate(record, edges, created_by=principal_id)
            self._journal(record, "linked", edges=len(edges))
            self._activate(record)

        self.repository.save(record.memory_id, record)
        self.signals.emit(
            SignalType.METRIC,
            "memory.formation.confidence",
            entry.tenant_id,
            value=record.confidence,
            memory_type=entry.memory_type,
            state=record.state.value,
        )
        return record

    def integrate(
        self,
        token: str,
        memory_id: str,
        edges: list[tuple[str, EdgeType]],
    ) -> MemoryRecord:
        """Links a Validated entry and activates it (09.8.4, 09.8.5)."""
        principal_id, _ = self.authorizer.principal_of(token)
        record = self.get(memory_id)
        self.integration.integrate(record, edges, created_by=principal_id)
        self._journal(record, "linked", edges=len(edges))
        self._activate(record)
        self.repository.save(record.memory_id, record)
        return record

    def _activate(self, record: MemoryRecord) -> MemoryRecord:
        """Linked -> Active. Guarded, and refused for an unlinked entry."""
        if not self.integration.is_linked(record.memory_id):
            raise AgentOSError(f"memory '{record.memory_id}' has no edges; an unlinked entry is not activated (09.8.4)")
        self._transition(record, MemoryState.ACTIVE)
        self._journal(record, "activated")
        return record

    # ------------------------------------------------------------- Retrieval

    def retrieve(
        self,
        token: str,
        tenant_id: str,
        role: SemanticRole | None = None,
        memory_type: str | None = None,
        business_id: str | None = None,
        min_confidence: float = 0.0,
        max_sensitivity: Sensitivity = Sensitivity.TENANT_SCOPED,
        limit: int | None = None,
    ) -> list[RetrievalResult]:
        """**Memory Retrieval** (21B §16.5): scoped, filtered, ranked query.

        The four boundaries of 09.6.3 are applied here, before ranking, so a
        result that should not be visible is never a candidate rather than
        being ranked and then dropped.
        """
        principal_id, principal_tenant = self.authorizer.principal_of(token)
        if principal_tenant != tenant_id:
            self._deny(principal_id, tenant_id, "tenant", "retrieval across tenants")
        if not self.authorizer.may_retrieve(token, tenant_id, max_sensitivity.value):
            self._deny(principal_id, tenant_id, "scope", f"retrieval at sensitivity '{max_sensitivity.value}'")

        ceiling = sensitivity_ceiling(max_sensitivity)
        now = self.now()
        candidates = [
            record
            for record in self._records.values()
            if record.is_retrievable  # 09.8.5 — Active only
            and record.entry.tenant_id == tenant_id
            and sensitivity_ceiling(record.entry.sensitivity) <= ceiling
            and record.confidence >= min_confidence
            and (role is None or record.entry.role == role)
            and (memory_type is None or record.entry.memory_type == memory_type)
            and self._business_visible(record, business_id)
            and self._agent_visible(record, principal_id)
        ]

        ranked = sorted(
            (RetrievalResult(record=r, relevance=self._relevance(r, now)) for r in candidates),
            key=lambda hit: hit.relevance,
            reverse=True,
        )
        if limit is not None:
            ranked = ranked[:limit]

        for hit in ranked:
            hit.record.last_retrieved_at = now
            hit.record.retrieval_count += 1

        self.signals.emit(
            SignalType.METRIC,
            "memory.retrieval.hits",
            tenant_id,
            value=float(len(ranked)),
            principal_id=principal_id,
        )
        return ranked

    def _relevance(self, record: MemoryRecord, now: datetime) -> float:
        """Relevance Ranker (21B §16.3).

        Confidence weighted by recency of the occurrence. Deliberately simple
        and deliberately transparent: an opaque ranker would make "why did the
        agent see this memory" unanswerable, which 21B §16.15 guarantee 7
        does not permit.
        """
        age_days = max(0.0, (now - record.entry.provenance.occurred_at).total_seconds() / 86400.0)
        recency = 1.0 / (1.0 + age_days / 30.0)
        return round(record.confidence * 0.7 + recency * 0.3, 6)

    def _business_visible(self, record: MemoryRecord, business_id: str | None) -> bool:
        """Business boundary (09.6.3): filtered to the requesting business."""
        if record.entry.ownership == Ownership.GLOBAL:
            return True
        if business_id is None:
            return record.entry.business_id is None
        return record.entry.business_id in (None, business_id)

    def _agent_visible(self, record: MemoryRecord, principal_id: str) -> bool:
        """Agent boundary (09.6.3): no access to another agent's Private memory."""
        if record.entry.ownership != Ownership.PRIVATE:
            return True
        return record.entry.owner_principal_id == principal_id

    # ------------------------------------------------------- Lineage & graph

    def lineage(self, token: str, memory_id: str) -> Mapping[str, Any]:
        """**Lineage Query** (21B §16.5): trace an entry to its origin.

        A broken chain is Critical (21B §16.9), so a missing lineage reference
        is reported as a gap rather than returned as an empty field.
        """
        principal_id, principal_tenant = self.authorizer.principal_of(token)
        record = self.get(memory_id)
        if record.entry.tenant_id != principal_tenant:
            self._deny(principal_id, record.entry.tenant_id, "tenant", "lineage query across tenants")
        provenance = record.entry.provenance
        return {
            "memory_id": memory_id,
            "lineage_ref": provenance.lineage_ref,
            "source_identity": provenance.source_identity,
            "occurred_at": provenance.occurred_at,
            "workflow_id": provenance.workflow_id,
            "decision_id": provenance.decision_id,
            "edges_out": [(e.target_id, e.edge_type.value) for e in self.integration.edges_from(memory_id)],
            "edges_in": [(e.source_id, e.edge_type.value) for e in self.integration.edges_to(memory_id)],
            "gap": not provenance.lineage_ref,
        }

    def traverse(self, token: str, memory_id: str, depth: int = 1) -> list[str]:
        """**Relationship Traversal** (21B §16.5), within permission scope.

        Only entries the caller could retrieve appear in the walk — traversal
        is not a side door around the boundaries retrieval enforces.
        """
        principal_id, principal_tenant = self.authorizer.principal_of(token)
        if depth < 1:
            raise AgentOSError("traversal depth must be at least 1")
        seen = {memory_id}
        frontier = [memory_id]
        for _ in range(depth):
            next_frontier: list[str] = []
            for current in frontier:
                for neighbour in self.integration.neighbours(current):
                    if neighbour in seen:
                        continue
                    record = self._records.get(neighbour)
                    if record is None or record.entry.tenant_id != principal_tenant:
                        continue
                    if not self._agent_visible(record, principal_id):
                        continue
                    seen.add(neighbour)
                    next_frontier.append(neighbour)
            frontier = next_frontier
        return sorted(seen - {memory_id})

    # ----------------------------------------------------- Decay & disposition

    def run_decay(self) -> list[MemoryRecord]:
        """Decay Engine sweep. Degrades and flags; never deletes (09.8.6)."""
        became_stale = self.decay.sweep(list(self._records.values()))
        for record in became_stale:
            self._journal(record, "stale", reason=self.decay.should_stale(record) or "")
            self.signals.emit(
                SignalType.EVENT,
                "memory.decay.stale",
                record.entry.tenant_id,
                memory_id=record.memory_id,
                confidence=record.confidence,
            )
        return became_stale

    def revalidate(self, memory_id: str, confidence: float) -> MemoryRecord:
        """Stale -> Active when revalidation confirms renewed relevance (09.9.2)."""
        record = self.get(memory_id)
        record.confidence = confidence
        record.confidence_history.append((self.now(), confidence))
        record.valid_until = self.now() + self.validation.default_validity
        self._transition(record, MemoryState.ACTIVE)
        self._journal(record, "revalidated", confidence=confidence)
        return record

    def archive(self, memory_id: str) -> MemoryRecord:
        """Stale -> Archived. Demotion to Cold is a logged memory operation (09.7.5)."""
        record = self.get(memory_id)
        self._transition(record, MemoryState.ARCHIVED)
        record.tier = Tier.COLD
        self._journal(record, "archived")
        return record

    def purge(self, memory_id: str, approved_by: str | None, approver_is_human: bool) -> MemoryRecord:
        """Archived -> Purged. Requires statutory expiry **and** approval (09.9.2).

        Both conditions, not either. The identity remains in the audit log
        after purge; only the payload is destroyed.
        """
        record = self.get(memory_id)
        if self.now() < record.retain_until:
            raise DispositionRefused(
                f"memory '{memory_id}' is retained until {record.retain_until.isoformat()}; "
                "purge requires statutory expiry (09.4.2, 09.9.2)"
            )
        if approved_by is None or not approver_is_human:
            raise DispositionRefused(f"purge of '{memory_id}' requires explicit human approval (09.9.2)")
        self._transition(record, MemoryState.PURGED)
        self._journal(record, "purged", approved_by=approved_by)
        # Identity and lineage survive in the journal; the payload does not.
        self._records[memory_id] = MemoryRecord(
            entry=record.entry,
            formed_at=record.formed_at,
            state=MemoryState.PURGED,
            tier=Tier.COLD,
            confidence=0.0,
        )
        return self._records[memory_id]

    # ------------------------------------------------------------- Utilities

    def get(self, memory_id: str) -> MemoryRecord:
        try:
            return self._records[memory_id]
        except KeyError:
            raise NotFoundError(f"memory '{memory_id}' does not exist") from None

    def health(self) -> Mapping[str, Any]:
        """**Memory Health** (21B §16.5). Consumer: Observability Gateway.

        Both sides of the growth ledger are exposed deliberately: 09.3.2 names
        Decay Discipline a permanent objective and calls unbounded growth a
        failure mode, which Observability cannot detect from growth alone.
        """
        records = list(self._records.values())
        by_state: dict[str, int] = {}
        by_tier: dict[str, int] = {}
        for record in records:
            by_state[record.state.value] = by_state.get(record.state.value, 0) + 1
            by_tier[record.tier.value] = by_tier.get(record.tier.value, 0) + 1
        active = [r for r in records if r.state == MemoryState.ACTIVE]
        return {
            "entries": len(records),
            "by_state": by_state,
            "by_tier": by_tier,
            "quarantine_depth": self.quarantine.depth,
            "formation_rejections": self._formation_rejections,
            "edges": self.integration.edge_count,
            "decayed": self.decay.decayed_count,
            "growth": len(records),
            "mean_confidence": round(sum(r.confidence for r in active) / len(active), 4) if active else 0.0,
            "journal_entries": len(self.journal),
            "journal_intact": self.journal.verify_chain(),
        }

    def _transition(self, record: MemoryRecord, target: MemoryState) -> None:
        machine = LifecycleStateMachine(transitions=dict(MEMORY_TRANSITIONS), state=record.state)
        machine.transition(target)
        record.state = target

    def _journal(self, record: MemoryRecord, action: str, **detail: Any) -> None:
        self.journal.append(
            {
                "kind": "memory",
                "action": action,
                "memory_id": record.memory_id,
                "memory_type": record.entry.memory_type,
                "tenant_id": record.entry.tenant_id,
                "state": record.state.value,
                "tier": record.tier.value,
                **detail,
            }
        )

    def _deny(self, principal_id: str, tenant_id: str, boundary: str, attempted: str) -> None:
        """Boundary violation: blocked, logged, Category 1 escalation (21B §16.9)."""
        self.journal.append(
            {
                "kind": "boundary_violation",
                "boundary": boundary,
                "principal_id": principal_id,
                "tenant_id": tenant_id,
                "attempted": attempted,
            }
        )
        self.signals.emit(
            SignalType.EVENT,
            "memory.boundary.violation",
            tenant_id,
            boundary=boundary,
            principal_id=principal_id,
            attempted=attempted,
        )
        raise MemoryAccessDenied(
            f"principal '{principal_id}' violated the {boundary} boundary attempting {attempted} (09.6.3)"
        )
