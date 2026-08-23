"""Knowledge Gateway — extraction, validation, promotion, contradiction (doc 10).

Stage S4 test list for knowledge: "belief extraction, validation, promotion,
and revalidation with confidence-band enforcement (Knowledge Gateway's stated
0.60/0.80/0.95 thresholds); reconciliation of conflicting beliefs."
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from core.exceptions import NotFoundError
from knowledge_gateway import (
    BeliefSensitivity,
    BeliefState,
    ConfidenceBand,
    EpistemicFailure,
    Evidence,
    HypothesisQuarantined,
    KnowledgeAccessDenied,
    KnowledgeGateway,
    PromotionBlocked,
    RatificationRequired,
    ReconciliationStrategy,
    RelationType,
)

from .conftest import EXTRACTOR, HUMAN, TENANT, make_belief

# ---------------------------------------------------------------- confidence


@pytest.mark.parametrize(
    ("confidence", "band"),
    [
        (0.0, ConfidenceBand.HYPOTHESIS),
        (0.59, ConfidenceBand.HYPOTHESIS),
        (0.60, ConfidenceBand.VALIDATED),
        (0.79, ConfidenceBand.VALIDATED),
        (0.80, ConfidenceBand.CANONICAL),
        (0.94, ConfidenceBand.CANONICAL),
        (0.95, ConfidenceBand.AXIOMATIC),
        (1.0, ConfidenceBand.AXIOMATIC),
    ],
)
def test_the_four_confidence_bands_of_10_14_2(confidence: float, band: ConfidenceBand) -> None:
    assert ConfidenceBand.of(confidence) == band


def test_only_the_validated_band_is_provisional() -> None:
    assert ConfidenceBand.VALIDATED.is_provisional
    assert not ConfidenceBand.CANONICAL.is_provisional


# ---------------------------------------------------------------- extraction


def test_a_belief_without_evidence_is_speculation(knowledge: KnowledgeGateway, token: str) -> None:
    """10.2.1 — Knowledge rejects speculation."""
    from knowledge_gateway import Belief, Falsifiability

    bare = Belief(
        statement="prices will rise",
        belief_type="market",
        payload={},
        tenant_id=TENANT,
        evidence=(),
        falsifiability=Falsifiability(
            conditions=("prices fall",), observable_via="feed", review_by=datetime(2027, 1, 1, tzinfo=UTC)
        ),
        extracted_by=EXTRACTOR,
    )
    with pytest.raises(EpistemicFailure, match="without evidence is speculation"):
        knowledge.submit(token, bare)


def test_a_belief_resting_on_weak_memory_is_refused(
    knowledge: KnowledgeGateway, token: str, evidence_memory: str
) -> None:
    weak = make_belief(evidence_memory, memory_confidence=0.2)
    with pytest.raises(EpistemicFailure, match="below 0.5 confidence"):
        knowledge.submit(token, weak)


def test_fabricated_evidence_suspends_the_extractor(knowledge: KnowledgeGateway, token: str) -> None:
    """10.23.3 — an epistemic failure suspends the extractor with immediate alert."""
    with pytest.raises(EpistemicFailure, match="fabricated"):
        knowledge.submit(token, make_belief("memory-that-never-existed"))
    assert EXTRACTOR in knowledge.health()["operational"]["suspended_extractors"]
    # And the suspension bites on the next attempt.
    with pytest.raises(EpistemicFailure, match="suspended"):
        knowledge.submit(token, make_belief("memory-that-never-existed"))


def test_only_a_human_may_reinstate_a_suspended_extractor(knowledge: KnowledgeGateway, token: str) -> None:
    with pytest.raises(EpistemicFailure):
        knowledge.submit(token, make_belief("nope"))
    with pytest.raises(KnowledgeAccessDenied):
        knowledge.reinstate_extractor(EXTRACTOR, reinstated_by=EXTRACTOR)
    knowledge.reinstate_extractor(EXTRACTOR, reinstated_by=HUMAN)
    assert knowledge.health()["operational"]["suspended_extractors"] == []


def test_a_purged_memory_can_no_longer_support_a_belief(
    knowledge: KnowledgeGateway, memory, token: str, clock, security, evidence_memory: str
) -> None:
    from security_gateway import PrincipalType

    from .conftest import EXTRACTOR_VERIFIER

    clock.advance(timedelta(days=400))
    memory.run_decay()
    memory.archive(evidence_memory)
    clock.advance(timedelta(days=365 * 7))
    memory.purge(evidence_memory, approved_by=HUMAN, approver_is_human=True)

    security.credentials.issue(f"cred-{EXTRACTOR}-v2", EXTRACTOR, PrincipalType.AGENT, EXTRACTOR_VERIFIER)
    fresh, _ = security.authenticate(EXTRACTOR, f"cred-{EXTRACTOR}-v2", EXTRACTOR_VERIFIER, PrincipalType.AGENT)
    with pytest.raises(EpistemicFailure, match="does not exist"):
        knowledge.submit(fresh, make_belief(evidence_memory))


# ---------------------------------------------------------------- validation


def test_a_hypothesis_is_invisible_to_reasoners(knowledge: KnowledgeGateway, token: str, evidence_memory: str) -> None:
    """10.7.2 / 10 rule 10 — hypotheses are never visible to reasoner consumers."""
    knowledge.submit(token, make_belief(evidence_memory))
    assert knowledge.query(token, TENANT) == []


def test_validation_below_the_floor_quarantines(knowledge: KnowledgeGateway, token: str, evidence_memory: str) -> None:
    record = knowledge.submit(token, make_belief(evidence_memory))
    with pytest.raises(HypothesisQuarantined, match="below the 0.6"):
        knowledge.validate(record.belief_id, confidence=0.4)
    assert len(knowledge.hypotheses.quarantined()) == 1


def test_an_unfalsifiable_belief_is_dogma_and_is_quarantined(
    knowledge: KnowledgeGateway, token: str, evidence_memory: str
) -> None:
    """10.2.1 — a belief that cannot be falsified is dogma."""
    record = knowledge.submit(token, make_belief(evidence_memory, conditions=(), observable_via=""))
    with pytest.raises(HypothesisQuarantined, match="dogma"):
        knowledge.validate(record.belief_id, confidence=0.9)


def test_falsifiability_must_be_bounded_in_the_future(
    knowledge: KnowledgeGateway, token: str, evidence_memory: str
) -> None:
    past = datetime(2020, 1, 1, tzinfo=UTC)
    record = knowledge.submit(token, make_belief(evidence_memory, review_by=past))
    with pytest.raises(HypothesisQuarantined, match="bounded in the future"):
        knowledge.validate(record.belief_id, confidence=0.9)


def test_a_quarantined_hypothesis_can_be_resubmitted(
    knowledge: KnowledgeGateway, token: str, evidence_memory: str
) -> None:
    """10.14.4 — quarantined hypotheses are corrected and resubmitted, never destroyed."""
    record = knowledge.submit(token, make_belief(evidence_memory))
    with pytest.raises(HypothesisQuarantined):
        knowledge.validate(record.belief_id, confidence=0.4)
    knowledge.hypotheses.resubmit(record.belief_id)
    validated = knowledge.validate(record.belief_id, confidence=0.85)
    assert validated.state == BeliefState.VALIDATED


def test_an_unregistered_belief_type_is_quarantined(
    security, memory, clock, signals, token: str, evidence_memory: str
) -> None:
    from kernel.signals import SignalEmitter
    from knowledge_gateway import MemoryGatewayEvidenceSource, SecurityGatewayKnowledgeAuthorizer

    gateway = KnowledgeGateway(
        authorizer=SecurityGatewayKnowledgeAuthorizer(gateway=security),
        memory=MemoryGatewayEvidenceSource(gateway=memory),
        signals=SignalEmitter(source_identity="knowledge_gateway", sink=signals.append),
        now=clock,
        known_types={"definitional"},
    )
    record = gateway.submit(token, make_belief(evidence_memory, belief_type="market"))
    with pytest.raises(HypothesisQuarantined, match="not a registered knowledge type"):
        gateway.validate(record.belief_id, confidence=0.9)


# ----------------------------------------------------------------- promotion


def _canonical(knowledge: KnowledgeGateway, token: str, memory_id: str, confidence: float = 0.85, **kw):
    """Drives one belief all the way to Canonical."""
    record = knowledge.submit(token, make_belief(memory_id, **kw))
    knowledge.validate(record.belief_id, confidence=confidence)
    anchor = knowledge._beliefs.get("anchor")
    if anchor is None:
        # The first belief has nothing to link to, so it anchors itself
        # against a seeded root established the same way the ontology is.
        knowledge.graph.link(record.belief_id, record.belief_id, RelationType.HIERARCHICAL)
    else:
        knowledge.integrate(record.belief_id, [(anchor.belief_id, RelationType.CAUSAL)])
    return knowledge.promote(record.belief_id, approved_by=HUMAN)


def test_promotion_requires_integration(knowledge: KnowledgeGateway, token: str, evidence_memory: str) -> None:
    """10.7.5 — promotion is not automatic upon validation."""
    record = knowledge.submit(token, make_belief(evidence_memory))
    knowledge.validate(record.belief_id, confidence=0.85)
    with pytest.raises(PromotionBlocked, match="not integrated"):
        knowledge.promote(record.belief_id)


def test_a_promoted_belief_is_queryable(knowledge: KnowledgeGateway, token: str, evidence_memory: str) -> None:
    record = _canonical(knowledge, token, evidence_memory)
    answers = knowledge.query(token, TENANT)
    assert [a.belief_id for a in answers] == [record.belief_id]
    assert answers[0].band == ConfidenceBand.CANONICAL
    assert answers[0].provisional is False


def test_a_validated_band_answer_is_flagged_provisional(
    knowledge: KnowledgeGateway, token: str, evidence_memory: str
) -> None:
    """10.10 — suppressing that qualification is a conformance violation."""
    _canonical(knowledge, token, evidence_memory, confidence=0.7)
    answer = knowledge.query(token, TENANT)[0]
    assert answer.band == ConfidenceBand.VALIDATED
    assert answer.provisional is True


def test_axiomatic_confidence_requires_human_ratification(
    knowledge: KnowledgeGateway, token: str, evidence_memory: str
) -> None:
    """10.14.2 — the Axiomatic band requires human ratification."""
    record = knowledge.submit(token, make_belief(evidence_memory))
    knowledge.validate(record.belief_id, confidence=0.97)
    knowledge.graph.link(record.belief_id, record.belief_id, RelationType.HIERARCHICAL)
    with pytest.raises(PromotionBlocked, match="human ratification"):
        knowledge.promote(record.belief_id, approved_by=EXTRACTOR)
    assert knowledge.promote(record.belief_id, approved_by=HUMAN).state == BeliefState.CANONICAL


def test_restricted_beliefs_need_human_approval_to_promote(
    knowledge: KnowledgeGateway, token: str, evidence_memory: str
) -> None:
    record = knowledge.submit(token, make_belief(evidence_memory, sensitivity=BeliefSensitivity.RESTRICTED))
    knowledge.validate(record.belief_id, confidence=0.85)
    knowledge.graph.link(record.belief_id, record.belief_id, RelationType.HIERARCHICAL)
    with pytest.raises(PromotionBlocked, match="Restricted"):
        knowledge.promote(record.belief_id)


def test_nothing_below_the_floor_is_presented_as_canonical(
    knowledge: KnowledgeGateway, token: str, evidence_memory: str
) -> None:
    """10 rule 9."""
    with pytest.raises(KnowledgeAccessDenied, match="nothing below that"):
        knowledge.query(token, TENANT, min_confidence=0.3)


def test_query_is_tenant_scoped(knowledge: KnowledgeGateway, token: str, evidence_memory: str) -> None:
    _canonical(knowledge, token, evidence_memory)
    with pytest.raises(KnowledgeAccessDenied, match="tenant boundary"):
        knowledge.query(token, "tenant-beta")


def test_restricted_beliefs_are_filtered_from_an_unprivileged_query(
    knowledge: KnowledgeGateway, token: str, evidence_memory: str
) -> None:
    with pytest.raises(KnowledgeAccessDenied):
        knowledge.query(token, TENANT, max_sensitivity=BeliefSensitivity.RESTRICTED)


# ------------------------------------------------------------ contradiction


def _two_canonical(knowledge: KnowledgeGateway, token: str, memory_id: str, left_c=0.9, right_c=0.7):
    left = _canonical(knowledge, token, memory_id, confidence=left_c, statement="prices rise in Q3")
    right = knowledge.submit(token, make_belief(memory_id, statement="prices fall in Q3"))
    knowledge.validate(right.belief_id, confidence=right_c)
    knowledge.integrate(right.belief_id, [(left.belief_id, RelationType.CAUSAL)])
    knowledge.promote(right.belief_id, approved_by=HUMAN)
    return left, right


def test_detection_demotes_both_canonical_beliefs(
    knowledge: KnowledgeGateway, token: str, evidence_memory: str
) -> None:
    """10 rule 4 — no canonical belief remains active against an unresolved contradiction."""
    left, right = _two_canonical(knowledge, token, evidence_memory)
    knowledge.detect_contradiction(left.belief_id, right.belief_id, "incompatible price direction")
    assert left.state == BeliefState.CONTRADICTED
    assert right.state == BeliefState.CONTRADICTED
    assert knowledge.query(token, TENANT) == []  # neither is reasonable now


def test_promotion_is_blocked_by_an_unresolved_contradiction(
    knowledge: KnowledgeGateway, token: str, evidence_memory: str
) -> None:
    left = _canonical(knowledge, token, evidence_memory)
    candidate = knowledge.submit(token, make_belief(evidence_memory, statement="prices fall"))
    knowledge.validate(candidate.belief_id, confidence=0.85)
    knowledge.integrate(candidate.belief_id, [(left.belief_id, RelationType.CONTRADICTORY)])
    with pytest.raises(PromotionBlocked, match="unresolved contradiction"):
        knowledge.promote(candidate.belief_id, approved_by=HUMAN)


def test_supersession_resolves_a_clear_confidence_gap(
    knowledge: KnowledgeGateway, token: str, evidence_memory: str
) -> None:
    left, right = _two_canonical(knowledge, token, evidence_memory, left_c=0.9, right_c=0.65)
    contradiction = knowledge.detect_contradiction(left.belief_id, right.belief_id, "conflict")
    resolved, strategy = knowledge.reconcile(contradiction.contradiction_id, resolved_by="system")
    assert strategy == ReconciliationStrategy.SUPERSESSION
    assert right.state == BeliefState.SUPERSEDED
    assert right.superseded_by == left.belief_id
    assert left.state == BeliefState.CANONICAL
    assert resolved.is_resolved


def test_both_high_confidence_beliefs_force_human_arbitration(
    knowledge: KnowledgeGateway, token: str, evidence_memory: str
) -> None:
    """10.15.3 — arbitration is mandatory when both exceed 0.85."""
    left, right = _two_canonical(knowledge, token, evidence_memory, left_c=0.9, right_c=0.88)
    contradiction = knowledge.detect_contradiction(left.belief_id, right.belief_id, "conflict")
    _resolved, strategy = knowledge.reconcile(contradiction.contradiction_id, resolved_by="system")
    assert strategy == ReconciliationStrategy.HUMAN_ARBITRATION
    # Nothing was auto-resolved.
    assert knowledge.detector.unresolved_count == 1


def test_restricted_knowledge_forces_arbitration(knowledge: KnowledgeGateway, token: str, evidence_memory: str) -> None:
    left = _canonical(knowledge, token, evidence_memory, confidence=0.9)
    right = knowledge.submit(
        token, make_belief(evidence_memory, statement="secret", sensitivity=BeliefSensitivity.RESTRICTED)
    )
    knowledge.validate(right.belief_id, confidence=0.65)
    knowledge.integrate(right.belief_id, [(left.belief_id, RelationType.CAUSAL)])
    knowledge.promote(right.belief_id, approved_by=HUMAN)
    contradiction = knowledge.detect_contradiction(left.belief_id, right.belief_id, "conflict")
    _r, strategy = knowledge.reconcile(contradiction.contradiction_id, resolved_by="system")
    assert strategy == ReconciliationStrategy.HUMAN_ARBITRATION


def test_arbitration_is_a_human_only_class_d_act(knowledge: KnowledgeGateway, token: str, evidence_memory: str) -> None:
    left, right = _two_canonical(knowledge, token, evidence_memory, left_c=0.9, right_c=0.9)
    contradiction = knowledge.detect_contradiction(left.belief_id, right.belief_id, "conflict")
    with pytest.raises(KnowledgeAccessDenied, match="Class D"):
        knowledge.arbitrate(contradiction.contradiction_id, arbiter_id=EXTRACTOR, upheld_belief_id=left.belief_id)
    resolved = knowledge.arbitrate(contradiction.contradiction_id, arbiter_id=HUMAN, upheld_belief_id=left.belief_id)
    assert resolved.is_resolved
    assert resolved.strategy == ReconciliationStrategy.HUMAN_ARBITRATION
    assert right.state == BeliefState.SUPERSEDED
    assert left.state == BeliefState.CANONICAL


def test_repeated_failed_reconciliation_escalates_to_arbitration(
    knowledge: KnowledgeGateway, token: str, evidence_memory: str
) -> None:
    left, right = _two_canonical(knowledge, token, evidence_memory, left_c=0.8, right_c=0.79)
    contradiction = knowledge.detect_contradiction(left.belief_id, right.belief_id, "conflict")
    for _ in range(3):
        knowledge.reconciliation.strategy_for(contradiction, left, right)
    assert knowledge.reconciliation.strategy_for(contradiction, left, right) == ReconciliationStrategy.HUMAN_ARBITRATION


def test_contradiction_records_are_immutable_and_resolution_appends(
    knowledge: KnowledgeGateway, token: str, evidence_memory: str
) -> None:
    left, right = _two_canonical(knowledge, token, evidence_memory, left_c=0.9, right_c=0.65)
    contradiction = knowledge.detect_contradiction(left.belief_id, right.belief_id, "conflict")
    detected_at = contradiction.detected_at
    knowledge.reconcile(contradiction.contradiction_id, resolved_by="system")
    after = knowledge.detector.get(contradiction.contradiction_id)
    assert after.detected_at == detected_at  # original facts preserved
    assert after.resolved_at is not None


# ---------------------------------------------------- revalidation & deprecation


def test_revalidation_can_lower_confidence(knowledge: KnowledgeGateway, token: str, evidence_memory: str) -> None:
    record = _canonical(knowledge, token, evidence_memory, confidence=0.9)
    knowledge.revalidate(record.belief_id, confidence=0.7)
    assert record.confidence == 0.7
    assert record.band == ConfidenceBand.VALIDATED


def test_revalidation_below_the_floor_deprecates(knowledge: KnowledgeGateway, token: str, evidence_memory: str) -> None:
    record = _canonical(knowledge, token, evidence_memory, confidence=0.9)
    knowledge.revalidate(record.belief_id, confidence=0.4)
    assert record.state == BeliefState.DEPRECATED
    assert knowledge.query(token, TENANT) == []


def test_deprecation_requires_a_justification(knowledge: KnowledgeGateway, token: str, evidence_memory: str) -> None:
    """10 rule 18 — deprecation requires a justification entry linked via lineage."""
    record = _canonical(knowledge, token, evidence_memory)
    with pytest.raises(Exception, match="justification"):
        knowledge.deprecate(record.belief_id, "   ")
    knowledge.deprecate(record.belief_id, "market conditions changed")
    assert record.deprecation_justification == "market conditions changed"


def test_deprecation_never_deletes(knowledge: KnowledgeGateway, token: str, evidence_memory: str) -> None:
    """10.7.8 — deprecation is epistemic correction, not deletion."""
    record = _canonical(knowledge, token, evidence_memory)
    knowledge.deprecate(record.belief_id, "obsolete")
    assert knowledge.get(record.belief_id).state == BeliefState.DEPRECATED


def test_revalidation_is_domain_dependent(knowledge: KnowledgeGateway, token: str, evidence_memory: str, clock) -> None:
    """10.14.3 — market knowledge is revalidated frequently, definitional rarely."""
    record = _canonical(knowledge, token, evidence_memory)
    clock.advance(timedelta(days=8))
    assert record in knowledge.due_for_revalidation("market")
    assert record not in knowledge.due_for_revalidation("definitional")


# -------------------------------------------------------------------- ontology


def test_the_ontology_is_not_self_modifying(knowledge: KnowledgeGateway) -> None:
    """10.16.4 / 10 rule 13 — adoption requires human ratification."""
    knowledge.propose_ontology_change("p1", "belief_category", "regulatory", EXTRACTOR, "new domain")
    assert "regulatory" not in knowledge.query_ontology()["belief_categories"]
    with pytest.raises(RatificationRequired, match="not a Human"):
        knowledge.ratify_ontology_change("p1", ratified_by=EXTRACTOR)
    knowledge.ratify_ontology_change("p1", ratified_by=HUMAN)
    assert "regulatory" in knowledge.query_ontology()["belief_categories"]


def test_a_proposer_may_not_ratify_its_own_change(knowledge: KnowledgeGateway) -> None:
    knowledge.propose_ontology_change("p1", "entity_class", "regulator", HUMAN, "needed")
    with pytest.raises(RatificationRequired, match="may not ratify its own"):
        knowledge.ratify_ontology_change("p1", ratified_by=HUMAN)


def test_a_proposal_requires_a_rationale(knowledge: KnowledgeGateway) -> None:
    from core.exceptions import ValidationError

    with pytest.raises(ValidationError, match="rationale"):
        knowledge.propose_ontology_change("p1", "entity_class", "x", EXTRACTOR, "  ")


def test_pending_proposals_are_visible(knowledge: KnowledgeGateway) -> None:
    knowledge.propose_ontology_change("p1", "entity_class", "regulator", EXTRACTOR, "needed")
    assert knowledge.query_ontology()["pending_proposals"] == ["p1"]


# ------------------------------------------------------- graph integrity


def test_a_belief_cannot_contradict_itself(knowledge: KnowledgeGateway) -> None:
    from knowledge_gateway import GraphIntegrityError

    with pytest.raises(GraphIntegrityError, match="cannot contradict itself"):
        knowledge.graph.link("b1", "b1", RelationType.CONTRADICTORY)


def test_a_contradictory_cycle_is_detected(knowledge: KnowledgeGateway) -> None:
    """10.17.4 — a belief may not contradict itself through a chain."""
    knowledge.graph.link("a", "b", RelationType.CONTRADICTORY)
    knowledge.graph.link("b", "a", RelationType.CONTRADICTORY)
    violations = knowledge.graph.check_integrity({"a": _stub(), "b": _stub()})
    assert any(v.constraint == "contradictory_cycle" for v in violations)


def test_an_orphaned_canonical_belief_is_detected(knowledge: KnowledgeGateway) -> None:
    record = _stub(BeliefState.CANONICAL)
    violations = knowledge.graph.check_integrity({"lonely": record})
    assert any(v.constraint == "orphaned_canonical" for v in violations)


def test_a_dangling_supersession_is_detected(knowledge: KnowledgeGateway) -> None:
    record = _stub(BeliefState.SUPERSEDED)
    record.superseded_by = "does-not-exist"
    knowledge.graph.link("orphan", "other", RelationType.SUPERSEDES)
    violations = knowledge.graph.check_integrity({"orphan": record})
    assert any(v.constraint == "dangling_supersession" for v in violations)


def test_a_healthy_graph_reports_no_violations(knowledge: KnowledgeGateway, token: str, evidence_memory: str) -> None:
    _canonical(knowledge, token, evidence_memory)
    assert knowledge.health()["graph"]["integrity_violations"] == []


def test_traversal_respects_the_tenant_boundary(knowledge: KnowledgeGateway, token: str, evidence_memory: str) -> None:
    left, right = _two_canonical(knowledge, token, evidence_memory, left_c=0.9, right_c=0.85)
    assert right.belief_id in knowledge.traverse(token, left.belief_id)


# ---------------------------------------------------------------------- health


def test_health_reports_the_four_metric_families(knowledge: KnowledgeGateway, token: str, evidence_memory: str) -> None:
    _canonical(knowledge, token, evidence_memory)
    health = knowledge.health()
    for family in ("epistemic", "graph", "operational", "consumer"):
        assert family in health
    assert health["epistemic"]["contradiction_rate"] == 0.0
    assert health["journal_intact"] is True


def test_contradiction_rate_rises_with_conflict(knowledge: KnowledgeGateway, token: str, evidence_memory: str) -> None:
    """10.3.2 — contradiction rate is the leading indicator of epistemic erosion."""
    left, right = _two_canonical(knowledge, token, evidence_memory)
    knowledge.detect_contradiction(left.belief_id, right.belief_id, "conflict")
    assert knowledge.health()["epistemic"]["contradiction_rate"] > 0


def test_unknown_belief_lookup_raises(knowledge: KnowledgeGateway) -> None:
    with pytest.raises(NotFoundError):
        knowledge.get("no-such-belief")


def test_dependencies_are_confined_to_the_adapter_module() -> None:
    """21B §17.6 — Security and Memory are the permitted edges, in one file."""
    import pathlib

    import knowledge_gateway

    root = pathlib.Path(knowledge_gateway.__path__[0])
    importers = sorted(
        {
            path.name
            for path in root.glob("*.py")
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip().startswith(("import ", "from "))
            and ("security_gateway" in line or "memory_gateway" in line)
            and path.name != "__init__.py"
        }
    )
    assert importers == ["adapters.py"]


def _stub(state: BeliefState = BeliefState.CANONICAL):
    """A minimal record for graph-integrity checks, which read only two fields."""
    from knowledge_gateway import Belief, BeliefRecord, Falsifiability

    belief = Belief(
        statement="s",
        belief_type="market",
        payload={},
        tenant_id=TENANT,
        evidence=(Evidence(memory_id="m", memory_confidence=0.9, excerpt="e"),),
        falsifiability=Falsifiability(
            conditions=("c",), observable_via="v", review_by=datetime(2027, 1, 1, tzinfo=UTC)
        ),
        extracted_by=EXTRACTOR,
    )
    return BeliefRecord(belief=belief, state=state, confidence=0.9)
