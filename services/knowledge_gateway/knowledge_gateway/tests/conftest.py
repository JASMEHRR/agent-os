"""Fixtures for the Knowledge Gateway suite.

Wired against a real Security Gateway **and a real Memory Gateway**, so the
evidentiary substrate is genuine: a belief citing a memory that does not exist
is caught because Memory actually says so, not because a stub was told to.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from kernel.signals import SignalEmitter
from knowledge_gateway import (
    Belief,
    BeliefSensitivity,
    Evidence,
    Falsifiability,
    KnowledgeGateway,
    MemoryGatewayEvidenceSource,
    SecurityGatewayKnowledgeAuthorizer,
)
from memory_gateway import (
    EdgeType,
    MemoryEntry,
    MemoryGateway,
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
EXTRACTOR = "agent-extractor"
EXTRACTOR_VERIFIER = "hash-extractor"
BUSINESS = "business-one"

PERMISSIONS = {
    "memory.form.episodic",
    "memory.retrieve.tenant_scoped",
    "knowledge.submit.market",
    "knowledge.submit.definitional",
    "knowledge.query.public",
    "knowledge.query.tenant_scoped",
}


class Clock:
    def __init__(self, start: datetime | None = None) -> None:
        self.now = start or datetime(2026, 8, 1, 12, 0, tzinfo=UTC)

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
    gw = SecurityGateway(signing_key=b"knowledge-test-key", secret_store=NullSecretStore(), now=clock)
    gw.bootstrap_human_sovereign(HUMAN, "Sovereign", TENANT)
    gw.register_identity(
        RegistrationRequest(
            principal_id=EXTRACTOR,
            principal_type=PrincipalType.AGENT,
            name="Extractor",
            version="1.0.0",
            tenant_id=TENANT,
            autonomy_level=2,
            approved_by=HUMAN,
        )
    )
    gw.change_principal_status(EXTRACTOR, PrincipalStatus.ACTIVE, actor_id=HUMAN)
    gw.capabilities.define(Capability(name="epistemics", permits=frozenset(PERMISSIONS)))
    gw.capabilities.grant(EXTRACTOR, "epistemics")
    gw.roles.define(
        Role(
            name="epistemics",
            permissions=frozenset(PERMISSIONS),
            eligible_types=frozenset({PrincipalType.AGENT}),
        )
    )
    gw.roles.assign("epistemics", EXTRACTOR, PrincipalType.AGENT, assigned_by=HUMAN)
    gw.recompute_permissions(EXTRACTOR)
    gw.credentials.issue(f"cred-{EXTRACTOR}", EXTRACTOR, PrincipalType.AGENT, EXTRACTOR_VERIFIER)
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
    gw.ontology.seed("belief_category", {"market", "definitional"})
    gw.ontology.seed("entity_class", {"business", "competitor"})
    gw.ontology.seed("relationship_type", {"causal", "hierarchical"})
    return gw


@pytest.fixture
def token(security: SecurityGateway) -> str:
    issued, _ = security.authenticate(EXTRACTOR, f"cred-{EXTRACTOR}", EXTRACTOR_VERIFIER, PrincipalType.AGENT)
    return issued


@pytest.fixture
def evidence_memory(memory: MemoryGateway, token: str, clock: Clock) -> str:
    """A real, validated, linked memory entry for beliefs to cite."""
    anchor = memory.form(token, _entry("anchor"))
    record = memory.form(token, _entry("observation"), edges=[(anchor.memory_id, EdgeType.RELATES_TO)])
    return record.memory_id


def _entry(lineage: str) -> MemoryEntry:
    return MemoryEntry(
        memory_type="episodic.execution",
        role=SemanticRole.EPISODIC,
        form=StructuralForm.ATOMIC,
        payload={"observed": "competitor raised prices"},
        tenant_id=TENANT,
        business_id=BUSINESS,
        workspace_id=None,
        owner_principal_id=EXTRACTOR,
        ownership=Ownership.BUSINESS,
        provenance=Provenance(
            source_identity=EXTRACTOR,
            lineage_ref=lineage,
            occurred_at=datetime(2026, 8, 1, 11, 0, tzinfo=UTC),
        ),
    )


def make_belief(
    memory_id: str,
    statement: str = "Competitors raise prices in Q3",
    belief_type: str = "market",
    memory_confidence: float = 0.8,
    sensitivity: BeliefSensitivity = BeliefSensitivity.TENANT_SCOPED,
    business_id: str | None = BUSINESS,
    tenant_id: str = TENANT,
    review_by: datetime | None = None,
    conditions: tuple[str, ...] = ("observed Q3 price decrease across three competitors",),
    observable_via: str = "competitor pricing feed",
    extracted_by: str = EXTRACTOR,
) -> Belief:
    return Belief(
        statement=statement,
        belief_type=belief_type,
        payload={"quarter": "Q3"},
        tenant_id=tenant_id,
        business_id=business_id,
        sensitivity=sensitivity,
        extracted_by=extracted_by,
        evidence=(
            Evidence(memory_id=memory_id, memory_confidence=memory_confidence, excerpt="competitor raised prices"),
        ),
        falsifiability=Falsifiability(
            conditions=conditions,
            observable_via=observable_via,
            review_by=review_by or datetime(2027, 8, 1, tzinfo=UTC),
        ),
    )
