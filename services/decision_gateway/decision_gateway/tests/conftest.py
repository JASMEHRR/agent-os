"""Fixtures for the Decision Gateway suite.

Wired against real Security, Knowledge and Cost Manager instances, so
authority resolution, contradiction status and budget headroom are all
genuine rather than asserted by stubs.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from cost_manager import CostManager
from decision_gateway import (
    CostManagerBudgetSource,
    DecisionGateway,
    EvidenceRef,
    KnowledgeGatewayEvidenceSource,
    Option,
    Proposal,
    RiskAssessment,
    SecurityGatewayDecisionAuthorizer,
)
from kernel.authority import RiskClass
from kernel.signals import SignalEmitter
from knowledge_gateway import KnowledgeGateway, MemoryGatewayEvidenceSource, SecurityGatewayKnowledgeAuthorizer
from memory_gateway import MemoryGateway, SecurityGatewayMemoryAuthorizer
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
SECOND_HUMAN = "human-operator"
AGENT = "agent-planner"
AGENT_VERIFIER = "hash-planner"
BUSINESS = "business-one"

PERMISSIONS = {"decision.propose", "knowledge.query.tenant_scoped"}


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
    gw = SecurityGateway(signing_key=b"decision-test-key", secret_store=NullSecretStore(), now=clock)
    gw.bootstrap_human_sovereign(HUMAN, "Sovereign", TENANT)
    gw.register_identity(
        RegistrationRequest(
            principal_id=SECOND_HUMAN,
            principal_type=PrincipalType.HUMAN,
            name="Operator",
            version="1.0.0",
            tenant_id=TENANT,
            approved_by=HUMAN,
        )
    )
    gw.change_principal_status(SECOND_HUMAN, PrincipalStatus.ACTIVE, actor_id=HUMAN)
    gw.register_identity(
        RegistrationRequest(
            principal_id=AGENT,
            principal_type=PrincipalType.AGENT,
            name="Planner",
            version="1.0.0",
            tenant_id=TENANT,
            autonomy_level=2,
            approved_by=HUMAN,
        )
    )
    gw.change_principal_status(AGENT, PrincipalStatus.ACTIVE, actor_id=HUMAN)
    gw.capabilities.define(Capability(name="planning", permits=frozenset(PERMISSIONS)))
    gw.capabilities.grant(AGENT, "planning")
    gw.roles.define(
        Role(name="planner", permissions=frozenset(PERMISSIONS), eligible_types=frozenset({PrincipalType.AGENT}))
    )
    gw.roles.assign("planner", AGENT, PrincipalType.AGENT, assigned_by=HUMAN)
    gw.recompute_permissions(AGENT)
    gw.credentials.issue(f"cred-{AGENT}", AGENT, PrincipalType.AGENT, AGENT_VERIFIER)
    return gw


@pytest.fixture
def signals() -> list[Any]:
    return []


@pytest.fixture
def escalations() -> list[tuple[str, dict[str, Any]]]:
    return []


@pytest.fixture
def knowledge(security: SecurityGateway, clock: Clock, signals: list[Any]) -> KnowledgeGateway:
    memory = MemoryGateway(
        authorizer=SecurityGatewayMemoryAuthorizer(gateway=security),
        signals=SignalEmitter(source_identity="memory_gateway", sink=signals.append),
        now=clock,
    )
    return KnowledgeGateway(
        authorizer=SecurityGatewayKnowledgeAuthorizer(gateway=security),
        memory=MemoryGatewayEvidenceSource(gateway=memory),
        signals=SignalEmitter(source_identity="knowledge_gateway", sink=signals.append),
        now=clock,
    )


@pytest.fixture
def costs(clock: Clock, signals: list[Any]) -> CostManager:
    return CostManager(
        signals=SignalEmitter(source_identity="cost_manager", sink=signals.append),
        escalate=lambda kind, detail: None,
        now=clock,
    )


@pytest.fixture
def decisions(
    security: SecurityGateway,
    knowledge: KnowledgeGateway,
    costs: CostManager,
    clock: Clock,
    signals: list[Any],
    escalations: list[tuple[str, dict[str, Any]]],
) -> DecisionGateway:
    return DecisionGateway(
        authorizer=SecurityGatewayDecisionAuthorizer(gateway=security),
        knowledge=KnowledgeGatewayEvidenceSource(gateway=knowledge),
        budget=CostManagerBudgetSource(manager=costs),
        signals=SignalEmitter(source_identity="decision_gateway", sink=signals.append),
        now=clock,
        route_to_human=lambda kind, detail: escalations.append((kind, detail)),
    )


@pytest.fixture
def token(security: SecurityGateway) -> str:
    issued, _ = security.authenticate(AGENT, f"cred-{AGENT}", AGENT_VERIFIER, PrincipalType.AGENT)
    return issued


def low_risk() -> RiskAssessment:
    return RiskAssessment(
        financial=RiskClass.LOW,
        operational=RiskClass.LOW,
        reputational=RiskClass.LOW,
        legal=RiskClass.LOW,
        strategic=RiskClass.LOW,
    )


def risk_at(level: RiskClass) -> RiskAssessment:
    return RiskAssessment(
        financial=level,
        operational=RiskClass.LOW,
        reputational=RiskClass.LOW,
        legal=RiskClass.LOW,
        strategic=RiskClass.LOW,
    )


def null_option() -> Option:
    return Option(
        option_id="null",
        description="do nothing",
        estimated_cost=0.0,
        expected_value=0.0,
        reversible=True,
        is_null=True,
    )


def acting_option(
    option_id: str = "act",
    cost: float = 0.005,
    value: float = 1.0,
    reversible: bool = True,
    compensation: str | None = "comp-1",
) -> Option:
    return Option(
        option_id=option_id,
        description=f"execute {option_id}",
        estimated_cost=cost,
        expected_value=value,
        reversible=reversible,
        compensation_ref=compensation,
    )


def evidence(count: int = 2, confidence: float = 0.9, source: str = "knowledge") -> tuple[EvidenceRef, ...]:
    return tuple(
        EvidenceRef(
            source=source,
            reference_id=f"belief-{i}",
            confidence=confidence,
            statement=f"supporting belief {i}",
        )
        for i in range(count)
    )


def make_proposal(
    summary: str = "adjust the pricing table",
    options: tuple[Option, ...] | None = None,
    evidence_refs: tuple[EvidenceRef, ...] | None = None,
    risk: RiskAssessment | None = None,
    proposer_id: str = AGENT,
    tenant_id: str = TENANT,
    business_id: str | None = BUSINESS,
    declared_gap: str | None = None,
    irreversible: bool = False,
    standing_order_ref: str | None = None,
    scope: Any = None,
) -> Proposal:
    from decision_gateway import Scope
    from kernel.authority import AuthorityLevel

    return Proposal(
        proposal_id=f"prop-{summary[:12].replace(' ', '-')}",
        summary=summary,
        proposer_id=proposer_id,
        proposer_authority=AuthorityLevel.AGENT_DELEGATED,
        tenant_id=tenant_id,
        business_id=business_id,
        options=options if options is not None else (null_option(), acting_option(), acting_option("act-b", value=0.5)),
        evidence=evidence_refs if evidence_refs is not None else evidence(),
        risk=risk or low_risk(),
        scope=scope or Scope.TASK,
        declared_gap=declared_gap,
        human_designated_irreversible=irreversible,
        standing_order_ref=standing_order_ref,
    )
