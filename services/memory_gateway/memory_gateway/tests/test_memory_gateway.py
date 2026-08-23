"""Memory Gateway — lifecycle, boundaries, decay and disposition (09.4–09.9).

Stage S4 test list for memory: "Experience formation, validation, linkage, and
decay."
"""

from __future__ import annotations

from datetime import timedelta

import pytest

from core.exceptions import NotFoundError
from kernel.lifecycle import InvalidTransitionError
from memory_gateway import (
    AdmissionRejected,
    DispositionRefused,
    EdgeType,
    MemoryAccessDenied,
    MemoryGateway,
    MemoryState,
    Ownership,
    SemanticRole,
    Sensitivity,
    Tier,
)

from .conftest import AGENT, BUSINESS, HUMAN, TENANT, make_entry

# ----------------------------------------------------------------- formation


def test_formation_produces_a_validated_entry(memory: MemoryGateway, agent_token: str) -> None:
    record = memory.form(agent_token, make_entry())
    assert record.state == MemoryState.VALIDATED
    assert record.tier == Tier.DURABLE  # 09.7.5 — promoted to Durable when validated
    assert record.confidence >= 0.5
    assert record.valid_until is not None


def test_anonymous_memory_is_inadmissible(memory: MemoryGateway, agent_token: str) -> None:
    """09.4.3 — the runtime does not permit anonymous memory."""
    with pytest.raises(AdmissionRejected, match="anonymous"):
        memory.form(agent_token, make_entry(source=""))


def test_an_entry_without_lineage_is_rejected(memory: MemoryGateway, agent_token: str) -> None:
    with pytest.raises(AdmissionRejected, match="originating event"):
        memory.form(agent_token, make_entry(lineage_ref=""))


def test_raw_data_is_not_memory_until_formed(memory: MemoryGateway, agent_token: str) -> None:
    """09.2.2 — an empty payload has no structure."""
    with pytest.raises(AdmissionRejected, match="empty payload"):
        memory.form(agent_token, make_entry(payload={}))


def test_memory_type_must_be_hierarchical(memory: MemoryGateway, agent_token: str) -> None:
    with pytest.raises(AdmissionRejected, match="hierarchical"):
        memory.form(agent_token, make_entry(memory_type="episodic"))


def test_formation_rejections_are_counted_and_journalled(memory: MemoryGateway, agent_token: str) -> None:
    with pytest.raises(AdmissionRejected):
        memory.form(agent_token, make_entry(payload={}))
    assert memory.health()["formation_rejections"] == 1
    assert len(memory.journal) == 1


def test_formation_is_not_validation(memory: MemoryGateway, agent_token: str) -> None:
    """09.8.2 — an entry may be well-formed and unreliable."""
    memory.validation.source_reliability = lambda _source: 0.2
    record = memory.form(agent_token, make_entry())
    # Well-formed enough to exist, unreliable enough to be quarantined.
    assert record.state == MemoryState.DRAFT
    assert record.quarantine_reason is not None
    assert memory.quarantine.depth == 1


# ---------------------------------------------------------------- validation


def test_a_quarantined_entry_is_held_not_destroyed(memory: MemoryGateway, agent_token: str) -> None:
    """09.8.3 — entries failing validation are quarantined for review."""
    memory.validation.source_reliability = lambda _source: 0.1
    record = memory.form(agent_token, make_entry())
    assert memory.quarantine.held() == [record]
    assert memory.get(record.memory_id) is record


def test_a_quarantined_entry_can_be_corrected_and_released(memory: MemoryGateway, agent_token: str) -> None:
    memory.validation.source_reliability = lambda _source: 0.1
    record = memory.form(agent_token, make_entry())
    released = memory.quarantine.release(record.memory_id)
    assert released.quarantine_reason is None
    assert memory.quarantine.depth == 0


def test_rejection_logs_a_justification(memory: MemoryGateway, agent_token: str) -> None:
    memory.validation.source_reliability = lambda _source: 0.1
    record = memory.form(agent_token, make_entry())
    memory.quarantine.reject(record.memory_id, "source proven unreliable")
    assert memory.quarantine.rejection_reason(record.memory_id) == "source proven unreliable"


def test_an_unregistered_memory_type_is_quarantined(security, clock, signals, agent_token: str) -> None:
    from kernel.signals import SignalEmitter
    from memory_gateway import SecurityGatewayMemoryAuthorizer

    gateway = MemoryGateway(
        authorizer=SecurityGatewayMemoryAuthorizer(gateway=security),
        signals=SignalEmitter(source_identity="memory_gateway", sink=signals.append),
        now=clock,
        known_types={"semantic.fact"},
    )
    record = gateway.form(agent_token, make_entry(memory_type="episodic.execution"))
    assert record.state == MemoryState.DRAFT
    assert "not a registered schema" in (record.quarantine_reason or "")


def test_a_future_occurrence_is_quarantined(memory: MemoryGateway, agent_token: str, clock) -> None:
    future = clock.now + timedelta(days=1)
    record = memory.form(agent_token, make_entry(occurred_at=future))
    assert record.state == MemoryState.DRAFT
    assert "future" in (record.quarantine_reason or "")


# --------------------------------------------------------------- integration


def test_an_unlinked_entry_is_never_activated(memory: MemoryGateway, agent_token: str) -> None:
    """09.8.4 — an unlinked memory entry is incomplete."""
    record = memory.form(agent_token, make_entry())
    assert record.state == MemoryState.VALIDATED
    assert not record.is_retrievable


def test_an_unlinked_entry_is_invisible_to_retrieval(memory: MemoryGateway, agent_token: str) -> None:
    """09.8.5 — until activation the entry exists but is invisible to agents."""
    memory.form(agent_token, make_entry())
    assert memory.retrieve(agent_token, TENANT) == []


def test_integration_activates_and_promotes_to_semantic(memory: MemoryGateway, agent_token: str) -> None:
    anchor = memory.form(agent_token, make_entry(lineage_ref="event-anchor"))
    record = memory.form(
        agent_token, make_entry(lineage_ref="event-002"), edges=[(anchor.memory_id, EdgeType.RELATES_TO)]
    )
    assert record.state == MemoryState.ACTIVE
    assert record.tier == Tier.SEMANTIC
    assert record.is_retrievable


def test_integration_requires_at_least_one_edge(memory: MemoryGateway, agent_token: str) -> None:
    from core.exceptions import ValidationError

    record = memory.form(agent_token, make_entry())
    with pytest.raises(ValidationError, match="unlinked entry is incomplete"):
        memory.integrate(agent_token, record.memory_id, [])


def test_an_entry_cannot_link_to_itself(memory: MemoryGateway, agent_token: str) -> None:
    from core.exceptions import ValidationError

    record = memory.form(agent_token, make_entry())
    with pytest.raises(ValidationError, match="may not link to itself"):
        memory.integrate(agent_token, record.memory_id, [(record.memory_id, EdgeType.RELATES_TO)])


def test_contradiction_edges_are_traceable(memory: MemoryGateway, agent_token: str) -> None:
    first = memory.form(agent_token, make_entry(lineage_ref="e1"))
    second = memory.form(agent_token, make_entry(lineage_ref="e2"), edges=[(first.memory_id, EdgeType.CONTRADICTS)])
    assert memory.integration.contradictions(second.memory_id) == [first.memory_id]
    assert memory.integration.contradictions(first.memory_id) == [second.memory_id]


# ----------------------------------------------------------------- retrieval


def _active(memory: MemoryGateway, token: str, **kwargs: object):
    anchor = memory.form(token, make_entry(lineage_ref="anchor"))
    return memory.form(token, make_entry(**kwargs), edges=[(anchor.memory_id, EdgeType.RELATES_TO)])  # type: ignore[arg-type]


def test_retrieval_returns_ranked_results_with_confidence(memory: MemoryGateway, agent_token: str) -> None:
    _active(memory, agent_token, lineage_ref="e1")
    hits = memory.retrieve(agent_token, TENANT, business_id=BUSINESS)
    assert hits
    assert all(hit.confidence > 0 for hit in hits)
    assert hits == sorted(hits, key=lambda h: h.relevance, reverse=True)


def test_retrieval_filters_by_role_and_type(memory: MemoryGateway, agent_token: str) -> None:
    _active(memory, agent_token, lineage_ref="e1", memory_type="semantic.fact", role=SemanticRole.SEMANTIC)
    assert memory.retrieve(agent_token, TENANT, business_id=BUSINESS, role=SemanticRole.SEMANTIC)
    assert memory.retrieve(agent_token, TENANT, business_id=BUSINESS, role=SemanticRole.FAILURE) == []
    assert memory.retrieve(agent_token, TENANT, business_id=BUSINESS, memory_type="semantic.fact")


def test_retrieval_applies_a_confidence_floor(memory: MemoryGateway, agent_token: str) -> None:
    _active(memory, agent_token, lineage_ref="e1")
    assert memory.retrieve(agent_token, TENANT, business_id=BUSINESS, min_confidence=0.99) == []


def test_cross_tenant_retrieval_is_denied(memory: MemoryGateway, agent_token: str) -> None:
    """09.6.3, tenant boundary."""
    with pytest.raises(MemoryAccessDenied, match="tenant boundary"):
        memory.retrieve(agent_token, "tenant-beta")


def test_cross_tenant_formation_is_denied(memory: MemoryGateway, agent_token: str) -> None:
    with pytest.raises(MemoryAccessDenied, match="tenant boundary"):
        memory.form(agent_token, make_entry(tenant_id="tenant-beta"))


def test_private_memory_is_invisible_to_another_agent(
    memory: MemoryGateway, agent_token: str, other_token: str
) -> None:
    """09.6.3, agent boundary."""
    _active(memory, agent_token, lineage_ref="e1", ownership=Ownership.PRIVATE, owner=AGENT)
    assert memory.retrieve(agent_token, TENANT, business_id=BUSINESS)
    mine = [
        h
        for h in memory.retrieve(other_token, TENANT, business_id=BUSINESS)
        if h.record.entry.ownership == Ownership.PRIVATE
    ]
    assert mine == []


def test_business_boundary_filters_retrieval(memory: MemoryGateway, agent_token: str) -> None:
    """09.6.3, business boundary."""
    _active(memory, agent_token, lineage_ref="e1", business_id="business-two")
    assert memory.retrieve(agent_token, TENANT, business_id=BUSINESS) == []
    assert memory.retrieve(agent_token, TENANT, business_id="business-two")


def test_global_memory_crosses_the_business_boundary(memory: MemoryGateway, agent_token: str) -> None:
    _active(memory, agent_token, lineage_ref="e1", business_id="business-two", ownership=Ownership.GLOBAL)
    assert memory.retrieve(agent_token, TENANT, business_id=BUSINESS)


def test_restricted_memory_needs_elevated_permission(memory: MemoryGateway, agent_token: str) -> None:
    """09.5.3 — Restricted-class memory requires elevated permission."""
    _active(memory, agent_token, lineage_ref="e1", sensitivity=Sensitivity.RESTRICTED)
    assert memory.retrieve(agent_token, TENANT, business_id=BUSINESS) == []
    with pytest.raises(MemoryAccessDenied):
        memory.retrieve(agent_token, TENANT, max_sensitivity=Sensitivity.RESTRICTED)


def test_boundary_violations_are_journalled_and_signalled(
    memory: MemoryGateway, agent_token: str, signals: list[object]
) -> None:
    with pytest.raises(MemoryAccessDenied):
        memory.retrieve(agent_token, "tenant-beta")
    assert any(getattr(s, "name", "") == "memory.boundary.violation" for s in signals)


# ------------------------------------------------------- lineage & traversal


def test_lineage_traces_to_the_originating_event(memory: MemoryGateway, agent_token: str) -> None:
    record = memory.form(agent_token, make_entry(lineage_ref="event-042"))
    trace = memory.lineage(agent_token, record.memory_id)
    assert trace["lineage_ref"] == "event-042"
    assert trace["source_identity"] == AGENT
    assert trace["gap"] is False


def test_traversal_walks_the_relational_web(memory: MemoryGateway, agent_token: str) -> None:
    a = memory.form(agent_token, make_entry(lineage_ref="a"))
    b = memory.form(agent_token, make_entry(lineage_ref="b"), edges=[(a.memory_id, EdgeType.CAUSED_BY)])
    c = memory.form(agent_token, make_entry(lineage_ref="c"), edges=[(b.memory_id, EdgeType.CAUSED_BY)])
    assert memory.traverse(agent_token, c.memory_id, depth=1) == [b.memory_id]
    assert sorted(memory.traverse(agent_token, c.memory_id, depth=2)) == sorted([a.memory_id, b.memory_id])


def test_traversal_respects_the_agent_boundary(memory: MemoryGateway, agent_token: str, other_token: str) -> None:
    anchor = memory.form(agent_token, make_entry(lineage_ref="anchor"))
    private = memory.form(
        agent_token,
        make_entry(lineage_ref="p", ownership=Ownership.PRIVATE, owner=AGENT),
        edges=[(anchor.memory_id, EdgeType.RELATES_TO)],
    )
    assert private.memory_id in memory.traverse(agent_token, anchor.memory_id)
    assert private.memory_id not in memory.traverse(other_token, anchor.memory_id)


# --------------------------------------------------------------------- decay


def test_decay_degrades_confidence_without_deleting(memory: MemoryGateway, agent_token: str, clock) -> None:
    """09.8.6 — decay is degradation, not deletion."""
    record = _active(memory, agent_token, lineage_ref="e1")
    before = record.confidence
    clock.advance(timedelta(days=400))
    memory.run_decay()
    assert record.confidence < before
    assert memory.get(record.memory_id) is record  # still present


def test_expired_validity_marks_an_entry_stale(memory: MemoryGateway, agent_token: str, clock) -> None:
    record = _active(memory, agent_token, lineage_ref="e1")
    clock.advance(timedelta(days=400))
    became_stale = memory.run_decay()
    assert record in became_stale
    assert record.state == MemoryState.STALE
    assert not record.is_retrievable


def test_idle_entries_go_stale(memory: MemoryGateway, agent_token: str, clock) -> None:
    record = _active(memory, agent_token, lineage_ref="e1")
    clock.advance(timedelta(days=91))
    assert memory.decay.should_stale(record) is not None


def test_revalidation_restores_a_stale_entry(memory: MemoryGateway, agent_token: str, clock, security) -> None:
    """09.9.2 — Stale -> Active when revalidation confirms renewed relevance."""
    from security_gateway import PrincipalType

    from .conftest import AGENT_VERIFIER

    record = _active(memory, agent_token, lineage_ref="e1")
    clock.advance(timedelta(days=400))
    memory.run_decay()
    memory.revalidate(record.memory_id, confidence=0.9)
    assert record.state == MemoryState.ACTIVE
    assert record.confidence == 0.9
    # A year on, both the token (one-hour TTL, 14.9.2) and the credential
    # (90-day lifetime) have expired. The agent rotates its credential and
    # re-authenticates, exactly as a long-lived principal must.
    security.credentials.issue(f"cred-{AGENT}-v2", AGENT, PrincipalType.AGENT, AGENT_VERIFIER)
    fresh, _ = security.authenticate(AGENT, f"cred-{AGENT}-v2", AGENT_VERIFIER, PrincipalType.AGENT)
    assert memory.retrieve(fresh, TENANT, business_id=BUSINESS)


def test_the_decay_engine_has_no_delete_path() -> None:
    from memory_gateway import DecayEngine

    surface = {name for name in dir(DecayEngine) if not name.startswith("_")}
    assert {"delete", "purge", "destroy", "remove"}.isdisjoint(surface)


def test_confidence_history_is_retained(memory: MemoryGateway, agent_token: str, clock) -> None:
    record = _active(memory, agent_token, lineage_ref="e1")
    clock.advance(timedelta(days=400))
    memory.run_decay()
    assert len(record.confidence_history) >= 2


# --------------------------------------------------------------- disposition


def test_purge_requires_statutory_expiry(memory: MemoryGateway, agent_token: str, clock) -> None:
    """09.9.2 — Archived -> Purged needs statutory expiry AND approval."""
    record = _active(memory, agent_token, lineage_ref="e1")
    clock.advance(timedelta(days=400))
    memory.run_decay()
    memory.archive(record.memory_id)
    with pytest.raises(DispositionRefused, match="statutory expiry"):
        memory.purge(record.memory_id, approved_by=HUMAN, approver_is_human=True)


def test_purge_requires_human_approval(memory: MemoryGateway, agent_token: str, clock) -> None:
    record = _active(memory, agent_token, lineage_ref="e1")
    clock.advance(timedelta(days=400))
    memory.run_decay()
    memory.archive(record.memory_id)
    clock.advance(timedelta(days=365 * 7))
    with pytest.raises(DispositionRefused, match="human approval"):
        memory.purge(record.memory_id, approved_by=None, approver_is_human=False)
    with pytest.raises(DispositionRefused, match="human approval"):
        memory.purge(record.memory_id, approved_by=AGENT, approver_is_human=False)


def test_purge_retains_identity_in_the_audit_log(memory: MemoryGateway, agent_token: str, clock) -> None:
    record = _active(memory, agent_token, lineage_ref="e1")
    clock.advance(timedelta(days=400))
    memory.run_decay()
    memory.archive(record.memory_id)
    clock.advance(timedelta(days=365 * 7))
    purged = memory.purge(record.memory_id, approved_by=HUMAN, approver_is_human=True)
    assert purged.state == MemoryState.PURGED
    assert memory.get(record.memory_id).entry.memory_id == record.memory_id  # identity survives
    assert any(e.payload.get("action") == "purged" for e in [memory.journal[i] for i in range(len(memory.journal))])


def test_lifecycle_guards_reject_illegal_transitions(memory: MemoryGateway, agent_token: str) -> None:
    record = memory.form(agent_token, make_entry())
    with pytest.raises(InvalidTransitionError):
        memory.archive(record.memory_id)  # Validated -> Archived is not an edge


def test_unknown_memory_lookup_raises(memory: MemoryGateway) -> None:
    with pytest.raises(NotFoundError):
        memory.get("no-such-memory")


# -------------------------------------------------------------------- health


def test_health_exposes_both_sides_of_the_growth_ledger(memory: MemoryGateway, agent_token: str, clock) -> None:
    """09.3.2 — unbounded growth is a failure mode Observability must detect."""
    _active(memory, agent_token, lineage_ref="e1")
    clock.advance(timedelta(days=400))
    memory.run_decay()
    health = memory.health()
    assert health["growth"] >= 2
    assert health["decayed"] >= 1
    assert health["journal_intact"] is True
    assert "by_state" in health and "by_tier" in health


def test_security_gateway_is_imported_in_exactly_one_module() -> None:
    import pathlib

    import memory_gateway

    root = pathlib.Path(memory_gateway.__path__[0])
    importers = [
        path.name
        for path in root.glob("*.py")
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip().startswith(("import ", "from ")) and "security_gateway" in line
    ]
    assert importers == ["security_adapter.py"]
