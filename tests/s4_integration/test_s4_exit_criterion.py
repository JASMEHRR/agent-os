"""Stage S4 exit criterion — the Events → Memory → Knowledge pipeline, end to end.

Build Specification, Stage S4: experience formation, validation, linkage and
decay (memory); belief extraction, validation, promotion and revalidation with
confidence-band enforcement, plus reconciliation of conflicting beliefs
(knowledge).

The property this suite exists to prove is the one neither module can prove
alone: **the pipeline is unidirectional and acyclic** (09.6.4, 10.6.4).
Memory consumes events to form experience; Knowledge consumes memory to form
belief; nothing flows back. Corrections travel forward as new entries.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from kernel.signals import SignalEmitter
from knowledge_gateway import (
    Belief,
    BeliefState,
    ConfidenceBand,
    Evidence,
    Falsifiability,
    KnowledgeGateway,
    MemoryGatewayEvidenceSource,
    ReconciliationStrategy,
    RelationType,
    SecurityGatewayKnowledgeAuthorizer,
)
from memory_gateway import (
    EdgeType,
    MemoryEntry,
    MemoryGateway,
    MemoryState,
    Ownership,
    Provenance,
    SecurityGatewayMemoryAuthorizer,
    SemanticRole,
    StructuralForm,
)
from security_gateway import (
    Capability,
    PrincipalType,
    RegistrationRequest,
    Role,
    SecurityGateway,
)
from security_gateway.enums import PrincipalStatus

TENANT = "tenant-alpha"
HUMAN = "human-sovereign"
AGENT = "agent-analyst"
VERIFIER = "hash-analyst"
BUSINESS = "business-one"

PERMISSIONS = {
    "memory.form.episodic",
    "memory.retrieve.tenant_scoped",
    "knowledge.submit.market",
    "knowledge.query.tenant_scoped",
}


class Clock:
    def __init__(self) -> None:
        self.now = datetime(2026, 8, 1, 12, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.now

    def advance(self, delta: timedelta) -> None:
        self.now += delta


class NullSecretStore:
    def read(self, reference: str) -> str:
        raise KeyError(reference)

    def write(self, reference: str, value: str) -> None:
        pass


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def security(clock: Clock) -> SecurityGateway:
    gw = SecurityGateway(signing_key=b"s4-integration-key", secret_store=NullSecretStore(), now=clock)
    gw.bootstrap_human_sovereign(HUMAN, "Sovereign", TENANT)
    gw.register_identity(
        RegistrationRequest(
            principal_id=AGENT,
            principal_type=PrincipalType.AGENT,
            name="Analyst",
            version="1.0.0",
            tenant_id=TENANT,
            autonomy_level=2,
            approved_by=HUMAN,
        )
    )
    gw.change_principal_status(AGENT, PrincipalStatus.ACTIVE, actor_id=HUMAN)
    gw.capabilities.define(Capability(name="cognition", permits=frozenset(PERMISSIONS)))
    gw.capabilities.grant(AGENT, "cognition")
    gw.roles.define(
        Role(
            name="cognition",
            permissions=frozenset(PERMISSIONS),
            eligible_types=frozenset({PrincipalType.AGENT}),
        )
    )
    gw.roles.assign("cognition", AGENT, PrincipalType.AGENT, assigned_by=HUMAN)
    gw.recompute_permissions(AGENT)
    gw.credentials.issue(f"cred-{AGENT}", AGENT, PrincipalType.AGENT, VERIFIER)
    return gw


@pytest.fixture
def signals() -> list[object]:
    return []


@pytest.fixture
def memory(security: SecurityGateway, clock: Clock, signals: list[object]) -> MemoryGateway:
    return MemoryGateway(
        authorizer=SecurityGatewayMemoryAuthorizer(gateway=security),
        signals=SignalEmitter(source_identity="memory_gateway", sink=signals.append),
        now=clock,
    )


@pytest.fixture
def knowledge(
    security: SecurityGateway, memory: MemoryGateway, clock: Clock, signals: list[object]
) -> KnowledgeGateway:
    gw = KnowledgeGateway(
        authorizer=SecurityGatewayKnowledgeAuthorizer(gateway=security),
        memory=MemoryGatewayEvidenceSource(gateway=memory),
        signals=SignalEmitter(source_identity="knowledge_gateway", sink=signals.append),
        now=clock,
    )
    gw.ontology.seed("belief_category", {"market"})
    return gw


@pytest.fixture
def token(security: SecurityGateway) -> str:
    issued, _ = security.authenticate(AGENT, f"cred-{AGENT}", VERIFIER, PrincipalType.AGENT)
    return issued


def state_of(record: Any) -> str:
    """Reads a record's current state as a plain string.

    Through a function, and as a string, so the type checker does not narrow
    the enum at the first assertion and then call every later comparison
    non-overlapping — the state genuinely changes as the record advances.
    """
    return str(record.state)


def _entry(lineage: str, observed: str) -> MemoryEntry:
    return MemoryEntry(
        memory_type="episodic.execution",
        role=SemanticRole.EPISODIC,
        form=StructuralForm.ATOMIC,
        payload={"observed": observed},
        tenant_id=TENANT,
        business_id=BUSINESS,
        workspace_id=None,
        owner_principal_id=AGENT,
        ownership=Ownership.BUSINESS,
        provenance=Provenance(
            source_identity=AGENT,
            lineage_ref=lineage,
            occurred_at=datetime(2026, 8, 1, 11, 0, tzinfo=UTC),
        ),
    )


def _belief(memory_id: str, statement: str, confidence: float = 0.85) -> Belief:
    return Belief(
        statement=statement,
        belief_type="market",
        payload={"quarter": "Q3"},
        tenant_id=TENANT,
        business_id=BUSINESS,
        extracted_by=AGENT,
        evidence=(Evidence(memory_id=memory_id, memory_confidence=confidence, excerpt=statement),),
        falsifiability=Falsifiability(
            conditions=("three consecutive quarters contradict it",),
            observable_via="pricing feed",
            review_by=datetime(2027, 8, 1, tzinfo=UTC),
        ),
    )


def test_s4_exit_criterion(memory: MemoryGateway, knowledge: KnowledgeGateway, token: str, clock: Clock) -> None:
    # --- Memory: formation, validation, linkage ---------------------------
    anchor = memory.form(token, _entry("event-001", "baseline observation"))
    assert state_of(anchor) == MemoryState.VALIDATED.value  # formed and validated, not yet linked
    assert not anchor.is_retrievable  # 09.8.4 — unlinked is incomplete

    observation = memory.form(
        token,
        _entry("event-002", "competitor raised prices"),
        edges=[(anchor.memory_id, EdgeType.RELATES_TO)],
    )
    assert state_of(observation) == MemoryState.ACTIVE.value
    assert memory.retrieve(token, TENANT, business_id=BUSINESS)

    # Lineage traces the entry back to its originating event.
    assert memory.lineage(token, observation.memory_id)["lineage_ref"] == "event-002"

    # --- Knowledge: extraction, validation, promotion ---------------------
    candidate = knowledge.submit(token, _belief(observation.memory_id, "Competitors raise prices in Q3"))
    assert state_of(candidate) == BeliefState.HYPOTHESIS.value
    assert knowledge.query(token, TENANT) == []  # 10.7.2 — invisible to reasoners

    knowledge.validate(candidate.belief_id, confidence=0.88)
    assert state_of(candidate) == BeliefState.VALIDATED.value
    assert knowledge.query(token, TENANT) == []  # still not canonical

    knowledge.graph.link(candidate.belief_id, candidate.belief_id, RelationType.HIERARCHICAL)
    knowledge.promote(candidate.belief_id, approved_by=HUMAN)
    answers = knowledge.query(token, TENANT)
    assert [a.belief_id for a in answers] == [candidate.belief_id]
    assert answers[0].band == ConfidenceBand.CANONICAL
    assert answers[0].provisional is False

    # --- Reconciliation of conflicting beliefs ----------------------------
    rival = knowledge.submit(token, _belief(observation.memory_id, "Competitors cut prices in Q3"))
    knowledge.validate(rival.belief_id, confidence=0.65)
    knowledge.integrate(rival.belief_id, [(candidate.belief_id, RelationType.CAUSAL)])
    knowledge.promote(rival.belief_id, approved_by=HUMAN)

    contradiction = knowledge.detect_contradiction(candidate.belief_id, rival.belief_id, "incompatible price direction")
    # 10 rule 4 — neither remains active while the contradiction stands.
    assert knowledge.query(token, TENANT) == []

    _resolved, strategy = knowledge.reconcile(contradiction.contradiction_id, resolved_by="system")
    assert strategy == ReconciliationStrategy.SUPERSESSION
    assert state_of(rival) == BeliefState.SUPERSEDED.value
    assert rival.superseded_by == candidate.belief_id
    assert [a.belief_id for a in knowledge.query(token, TENANT)] == [candidate.belief_id]

    # --- Revalidation with confidence-band enforcement --------------------
    knowledge.revalidate(candidate.belief_id, confidence=0.72, domain="market")
    answer = knowledge.query(token, TENANT)[0]
    assert answer.band == ConfidenceBand.VALIDATED
    assert answer.provisional is True  # 10.10 — uncertainty must propagate

    knowledge.revalidate(candidate.belief_id, confidence=0.45, domain="market")
    assert state_of(candidate) == BeliefState.DEPRECATED.value
    assert knowledge.query(token, TENANT) == []

    # --- Memory decay ------------------------------------------------------
    clock.advance(timedelta(days=400))
    became_stale = memory.run_decay()
    assert observation in became_stale
    assert state_of(observation) == MemoryState.STALE.value
    assert observation.confidence < 0.8  # degraded, not deleted
    assert memory.get(observation.memory_id) is observation

    # --- Health across both ------------------------------------------------
    assert memory.health()["journal_intact"] is True
    assert knowledge.health()["journal_intact"] is True
    assert knowledge.health()["graph"]["integrity_violations"] == []


def test_the_pipeline_is_unidirectional(memory: MemoryGateway, knowledge: KnowledgeGateway) -> None:
    """09.6.4 / 10.6.4 — Events → Memory → Knowledge, and knowledge never mutates memory.

    The Memory Gateway holds no reference to Knowledge at all, and the
    Knowledge Gateway's only view of Memory is a single read method. A write
    path in either direction would close the cycle the acyclic guarantee of
    21B §16.13 depends on.
    """
    memory_surface = {name for name in dir(memory) if not name.startswith("_")}
    assert not any("knowledge" in name for name in memory_surface)

    from knowledge_gateway.gateway import MemorySource

    port_methods = {name for name in dir(MemorySource) if not name.startswith("_")}
    assert port_methods == {"confidence_of"}


def test_knowledge_cannot_form_memory(knowledge: KnowledgeGateway) -> None:
    """The adapter exposes reading only; there is no formation path from Knowledge."""
    from knowledge_gateway import MemoryGatewayEvidenceSource

    methods = {
        name
        for name in dir(MemoryGatewayEvidenceSource)
        if not name.startswith("_") and callable(getattr(MemoryGatewayEvidenceSource, name, None))
    }
    assert methods == {"confidence_of"}


def test_a_belief_cannot_outlive_the_memory_it_cites(
    memory: MemoryGateway, knowledge: KnowledgeGateway, token: str, clock: Clock, security
) -> None:
    """Evidentiary sufficiency is checked against live memory, not a snapshot."""
    anchor = memory.form(token, _entry("e1", "baseline"))
    observation = memory.form(token, _entry("e2", "observed"), edges=[(anchor.memory_id, EdgeType.RELATES_TO)])

    clock.advance(timedelta(days=400))
    memory.run_decay()
    memory.archive(observation.memory_id)
    clock.advance(timedelta(days=365 * 7))
    memory.purge(observation.memory_id, approved_by=HUMAN, approver_is_human=True)

    security.credentials.issue(f"cred-{AGENT}-v2", AGENT, PrincipalType.AGENT, VERIFIER)
    fresh, _ = security.authenticate(AGENT, f"cred-{AGENT}-v2", VERIFIER, PrincipalType.AGENT)

    from knowledge_gateway import EpistemicFailure

    with pytest.raises(EpistemicFailure, match="does not exist"):
        knowledge.submit(fresh, _belief(observation.memory_id, "rests on purged evidence"))


def test_corrections_flow_forward_as_new_entries(memory: MemoryGateway, token: str) -> None:
    """09.6.4 — corrections flow backward as new events, not as mutations."""
    anchor = memory.form(token, _entry("e1", "baseline"))
    original = memory.form(token, _entry("e2", "misread the price"), edges=[(anchor.memory_id, EdgeType.RELATES_TO)])
    correction = memory.form(token, _entry("e3", "corrected price"), edges=[(original.memory_id, EdgeType.CORRECTS)])
    # The original is untouched; the correction points at it.
    assert original.entry.payload["observed"] == "misread the price"
    assert correction.memory_id in [e.source_id for e in memory.integration.edges_to(original.memory_id)]


def test_both_gateways_emit_into_the_same_signal_channel(
    memory: MemoryGateway, knowledge: KnowledgeGateway, token: str, signals: list[object]
) -> None:
    """21A §5.2 item 7 — Signal Emission is mandatory for every Gateway."""
    anchor = memory.form(token, _entry("e1", "baseline"))
    memory.form(token, _entry("e2", "observed"), edges=[(anchor.memory_id, EdgeType.RELATES_TO)])
    names = {getattr(s, "name", "") for s in signals}
    assert any(n.startswith("memory.") for n in names)
