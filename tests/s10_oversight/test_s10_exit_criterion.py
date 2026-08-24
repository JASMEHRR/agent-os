"""Stage S10 — Oversight. The exit criterion, exercised end to end.

21_PLAN §4.1, S10, verbatim:

    "Policy hierarchy enforced, compliance assessed, drift detected and
    quantified, interpretations ratified, meta-oversight operating."

The Build Specification adds two clauses this suite treats as first-class:
the rule that **no subsystem may self-certify its own compliance** (15.6.1),
and that **Governance can assemble evidence directly from subsystem journals**
(15.7.2) — which is what resolves the Governance to Observability circular
dependency.

The journals read here are real. Governance assesses the actual Agent Runtime,
Workflow Engine and Human Interface journals produced by earlier stages, not
fixtures shaped to pass.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from agent_runtime import (
    AgentManifest,
    AgentRuntime,
    AgentState,
    AuthorityBoundaries,
    SecurityGatewayRuntimeAuthorizer,
)
from governance_gateway import (
    ArtifactState,
    ComplianceState,
    EvidenceItem,
    EvidencePackage,
    GClass,
    GovernanceArtifact,
    GovernanceGateway,
    ImmutableJournalSource,
    IndependenceViolation,
    Interpretation,
    Policy,
    PolicyLayer,
    PolicyState,
    ReviewKind,
    SecurityGatewayGovernanceAuthorizer,
    SelfCertification,
    Stewardship,
)
from human_interface import HumanInterface, OverrideScope
from kernel.authority import AuthorityLevel
from kernel.signals import SignalEmitter
from observability_gateway import (
    ObservabilityGateway,
    SecurityGatewayQueryAuthorizer,
    Severity,
)
from security_gateway import Capability, PrincipalType, RegistrationRequest, Role, SecurityGateway
from security_gateway.enums import PrincipalStatus

TENANT = "tenant-alpha"
HUMAN = "human-sovereign"
ADMIN = "human-admin"
STEWARD = "agent-steward"
AUDITOR = "agent-auditor"
SUBJECT = "agent-analyst"
VERIFIER = "hash-analyst"
SCOPE = "portfolio/pricing"

PERMISSIONS = {"governance.form", "governance.assess", "observability.query"}


class Clock:
    def __init__(self) -> None:
        self.now = datetime(2026, 8, 1, 12, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.now

    def advance(self, delta: timedelta) -> None:
        self.now += delta


class SecretStore:
    def __init__(self) -> None:
        self._values: dict[str, str] = {}

    def read(self, reference: str) -> str:
        return self._values[reference]

    def write(self, reference: str, value: str) -> None:
        self._values[reference] = value


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def security(clock: Clock) -> SecurityGateway:
    gw = SecurityGateway(signing_key=b"s10-oversight", secret_store=SecretStore(), now=clock)
    gw.bootstrap_human_sovereign(HUMAN, "Sovereign", TENANT)
    for principal, ptype in (
        (ADMIN, PrincipalType.HUMAN),
        (STEWARD, PrincipalType.AGENT),
        (AUDITOR, PrincipalType.AGENT),
        (SUBJECT, PrincipalType.AGENT),
    ):
        gw.register_identity(
            RegistrationRequest(
                principal_id=principal,
                principal_type=ptype,
                name=principal,
                version="1.0.0",
                tenant_id=TENANT,
                autonomy_level=2 if ptype == PrincipalType.AGENT else None,
                approved_by=HUMAN,
            )
        )
        gw.change_principal_status(principal, PrincipalStatus.ACTIVE, actor_id=HUMAN)

    gw.capabilities.define(Capability(name="governor", permits=frozenset(PERMISSIONS)))
    # The sovereign reads incident timelines, which are Restricted (21B §24.10).
    gw.capabilities.define(Capability(name="observer", permits=frozenset({"observability.query"})))
    gw.capabilities.grant(HUMAN, "observer")
    gw.roles.define(
        Role(
            name="observer",
            permissions=frozenset({"observability.query"}),
            eligible_types=frozenset({PrincipalType.HUMAN}),
        )
    )
    gw.roles.assign("observer", HUMAN, PrincipalType.HUMAN, assigned_by=ADMIN)
    gw.recompute_permissions(HUMAN)
    gw.roles.define(
        Role(
            name="governor",
            permissions=frozenset(PERMISSIONS),
            eligible_types=frozenset({PrincipalType.AGENT, PrincipalType.HUMAN}),
        )
    )
    for principal, ptype in ((STEWARD, PrincipalType.AGENT), (AUDITOR, PrincipalType.AGENT)):
        gw.capabilities.grant(principal, "governor")
        gw.roles.assign("governor", principal, ptype, assigned_by=HUMAN)
        gw.recompute_permissions(principal)

    for principal, ptype in (
        (HUMAN, PrincipalType.HUMAN),
        (ADMIN, PrincipalType.HUMAN),
        (STEWARD, PrincipalType.AGENT),
        (AUDITOR, PrincipalType.AGENT),
        (SUBJECT, PrincipalType.AGENT),
    ):
        gw.credentials.issue(f"cred-{principal}", principal, ptype, VERIFIER)
    return gw


def token_for(security: SecurityGateway, principal: str, ptype: PrincipalType) -> str:
    token, _ = security.authenticate(principal, f"cred-{principal}", VERIFIER, ptype)
    return str(token)


@pytest.fixture
def human_token(security: SecurityGateway) -> str:
    return token_for(security, HUMAN, PrincipalType.HUMAN)


@pytest.fixture
def admin_token(security: SecurityGateway) -> str:
    return token_for(security, ADMIN, PrincipalType.HUMAN)


@pytest.fixture
def steward_token(security: SecurityGateway) -> str:
    return token_for(security, STEWARD, PrincipalType.AGENT)


@pytest.fixture
def auditor_token(security: SecurityGateway) -> str:
    return token_for(security, AUDITOR, PrincipalType.AGENT)


@pytest.fixture
def alerts() -> list[str]:
    return []


@pytest.fixture
def observability(security: SecurityGateway, clock: Clock) -> ObservabilityGateway:
    return ObservabilityGateway(authorizer=SecurityGatewayQueryAuthorizer(gateway=security), now=clock)


@pytest.fixture
def runtime(security: SecurityGateway, clock: Clock) -> AgentRuntime:
    """A real Agent Runtime, so Governance has a real journal to assess."""

    class NoMemory:
        def hydrate(self, token: str, tenant_id: str, scope: frozenset[str]) -> list[dict[str, Any]]:
            return []

    class NoInference:
        def infer(
            self, template: str, slots: dict[str, str], tenant_id: str, principal_id: str, max_cost: float
        ) -> tuple[dict[str, Any], float, bool]:
            return ({"summary": "analysed"}, 0.0, True)

    class NoTools:
        def invoke(
            self,
            token: str,
            tool_id: str,
            decision_id: str,
            parameters: dict[str, Any],
            cost_ceiling: float,
            idempotency_key: str,
        ) -> tuple[bool, dict[str, Any] | None, float]:
            return (True, {}, 0.0)

    rt = AgentRuntime(
        authorizer=SecurityGatewayRuntimeAuthorizer(gateway=security),
        memory=NoMemory(),
        inference=NoInference(),
        tools=NoTools(),
        signals=SignalEmitter(source_identity="agent_runtime"),
        now=clock,
    )
    subject_token = token_for(security, SUBJECT, PrincipalType.AGENT)
    rt.register(
        subject_token,
        AgentManifest(
            agent_id=SUBJECT,
            name=SUBJECT,
            version="1.0.0",
            tenant_id=TENANT,
            specialty="pricing analysis",
            boundaries=AuthorityBoundaries(
                capabilities=frozenset({"analysis"}),
                tool_inventory=frozenset(),
                memory_scope=frozenset({"tenant"}),
                autonomy_level=AuthorityLevel.AGENT_DELEGATED,
                cost_budget=1.0,
                workspace_ids=frozenset({"ws-1"}),
            ),
            prompt_template="analyse {context}",
            output_contract={"summary": str},
            max_context_tokens=1000,
            max_context_assembly_time=timedelta(seconds=5),
            activity_timeout=timedelta(minutes=5),
        ),
    )
    rt.command(subject_token, SUBJECT, AgentState.IDLE)
    return rt


@pytest.fixture
def human(security: SecurityGateway, clock: Clock) -> HumanInterface:
    def is_human(principal_id: str) -> bool:
        if not security.registry.exists(principal_id):
            return False
        return security.registry.get(principal_id).principal_type == PrincipalType.HUMAN

    return HumanInterface(is_human=is_human, signals=SignalEmitter(source_identity="human_interface"), now=clock)


@pytest.fixture
def governance(security: SecurityGateway, clock: Clock, alerts: list[str], human_token: str) -> GovernanceGateway:
    gw = GovernanceGateway(
        authorizer=SecurityGatewayGovernanceAuthorizer(gateway=security),
        signals=SignalEmitter(source_identity="governance_gateway"),
        alert_human=alerts.append,
        now=clock,
    )
    gw.assign_stewardship(
        human_token,
        Stewardship(
            stewardship_id="st-steward",
            tenant_id=TENANT,
            principal_id=STEWARD,
            scope=SCOPE,
            g_class=GClass.G2,
            assigned_at=clock(),
            expires_at=clock() + timedelta(days=90),
        ),
    )
    gw.assign_stewardship(
        human_token,
        Stewardship(
            stewardship_id="st-sovereign",
            tenant_id=TENANT,
            principal_id=HUMAN,
            scope="portfolio",
            g_class=GClass.G4,
            assigned_at=clock(),
            expires_at=clock() + timedelta(days=365),
        ),
    )
    return gw


def policy(policy_id: str, layer: PolicyLayer, scope: str, **overrides: Any) -> Policy:
    defaults: dict[str, Any] = {
        "policy_id": policy_id,
        "tenant_id": TENANT,
        "layer": layer,
        "scope": scope,
        "statement": "a rule",
        "constitutional_lineage": "11.14.3",
        "steward_id": STEWARD,
        "sunset_condition": "when the automated reviewer is trusted",
        "risk_assessment": "medium",
        "expected_outcome": "fewer publication errors",
        "formed_at": datetime(2026, 8, 1, tzinfo=UTC),
    }
    defaults.update(overrides)
    return Policy(**defaults)


# ------------------------------------------------------- the exit criterion


def test_the_policy_hierarchy_is_enforced_across_layers(governance: GovernanceGateway, steward_token: str) -> None:
    """15.16 — "Lower layers may elaborate but never contradict higher layers.\""""
    governance.form_policy(
        steward_token,
        policy(
            "pol-portfolio",
            PolicyLayer.PORTFOLIO,
            "portfolio",
            prohibits=frozenset({"unreviewed_publication"}),
        ),
    )
    governance.activate_policy("pol-portfolio")

    # A business policy elaborating within bounds is accepted.
    governance.form_policy(
        steward_token,
        policy("pol-ok", PolicyLayer.BUSINESS, SCOPE, prohibits=frozenset({"unreviewed_publication"})),
    )

    # One contradicting the portfolio layer is void and never forms.
    from governance_gateway import PolicyContradiction

    with pytest.raises(PolicyContradiction):
        governance.form_policy(
            steward_token,
            policy("pol-bad", PolicyLayer.BUSINESS, SCOPE, permits=frozenset({"unreviewed_publication"})),
        )

    applicable = governance.applicable_policies(TENANT, f"{SCOPE}/q3")
    assert [p.policy_id for p in applicable] == ["pol-portfolio"]


def test_compliance_is_assessed_from_real_subsystem_journals(
    governance: GovernanceGateway,
    runtime: AgentRuntime,
    steward_token: str,
    auditor_token: str,
    security: SecurityGateway,
) -> None:
    """15.7.2 — evidence assembled **directly from subsystem journals**.

    This is what resolves the Governance to Observability circular dependency:
    Governance reads the Agent Runtime's own journal and does not wait for
    Observability to interpret it first.
    """
    governance.register_journal(
        "agent_runtime", ImmutableJournalSource(journal=runtime.journal, scope_field="tenant_id")
    )
    package = governance.assemble_evidence(TENANT, ["agent_runtime"])
    assert package.items, "the real runtime journal produced real evidence"
    assert package.items[0].source_journal == "agent_runtime"

    governance.form(
        steward_token,
        GovernanceArtifact(
            artifact_id="ga-runtime",
            tenant_id=TENANT,
            steward_id=STEWARD,
            g_class=GClass.G2,
            scope=SCOPE,
            subject="agent lifecycle conformance in the pricing portfolio",
            rationale="every agent transition in the journal follows the declared machine",
            evidence=package,
            formed_at=datetime(2026, 8, 1, tzinfo=UTC),
        ),
    )
    record = governance.assess(auditor_token, "ga-runtime", ComplianceState.COMPLIANT, 0.85)
    assert record.compliance == ComplianceState.COMPLIANT
    assert governance.compliance_of(SCOPE) == ComplianceState.COMPLIANT


def test_no_subsystem_self_certifies_its_own_compliance(
    governance: GovernanceGateway, steward_token: str, runtime: AgentRuntime
) -> None:
    """15.6.1, the clause the Build Specification names for this stage.

    The steward accountable for the pricing portfolio may form an artifact
    about it and may not be the one who declares it compliant.
    """
    governance.register_journal("agent_runtime", ImmutableJournalSource(journal=runtime.journal))
    governance.form(
        steward_token,
        GovernanceArtifact(
            artifact_id="ga-self",
            tenant_id=TENANT,
            steward_id=STEWARD,
            g_class=GClass.G2,
            scope=SCOPE,
            subject="pricing portfolio conformance",
            rationale="self-assessment attempt",
            evidence=governance.assemble_evidence(TENANT, ["agent_runtime"]),
            formed_at=datetime(2026, 8, 1, tzinfo=UTC),
        ),
    )
    with pytest.raises(SelfCertification):
        governance.assess(steward_token, "ga-self", ComplianceState.COMPLIANT, 0.9)


def test_drift_is_detected_and_quantified(governance: GovernanceGateway, alerts: list[str]) -> None:
    """15.21 with 15.2.6 — detect, arrest and reverse drift before legitimacy collapses."""
    governance.record_drift(SCOPE, 0.05)
    governance.record_drift(SCOPE, 0.12)
    assert governance.drift_velocity(SCOPE) == pytest.approx(0.07)
    assert governance.compliance_of(SCOPE) != ComplianceState.DRIFTING

    governance.record_drift(SCOPE, 0.45)
    assert governance.compliance_of(SCOPE) == ComplianceState.DRIFTING
    assert any("drift velocity" in alert for alert in alerts)
    assert governance.health()["constitutional_health"]["drift_velocity"][SCOPE] == pytest.approx(0.40)


def test_an_interpretation_is_issued_and_ratified(
    governance: GovernanceGateway, human_token: str, admin_token: str
) -> None:
    """15.19 — the mechanism through which 21A §3's Interpretation Register resolves."""
    governance.interpret(
        human_token,
        Interpretation(
            interpretation_id="int-1",
            tenant_id=TENANT,
            question="does a compensating tool invocation count as a new decision?",
            provision="11.2.1",
            resolution="no; it inherits the authority of the decision it reverses",
            grounded_in=("11.2.1", "11.21.2", "12.17"),
            g_class=GClass.G3,
            scope=SCOPE,
            interpreted_by=HUMAN,
            interpreted_at=datetime(2026, 8, 1, tzinfo=UTC),
        ),
    )
    assert [i.interpretation_id for i in governance.interpretations_for("11.2.1")] == ["int-1"]

    governance.form(
        human_token,
        GovernanceArtifact(
            artifact_id="ga-int",
            tenant_id=TENANT,
            steward_id=HUMAN,
            g_class=GClass.G3,
            scope="portfolio",
            subject="ratification of interpretation int-1",
            rationale="the interpretation is grounded in three provisions and resolves a live ambiguity",
            # The evidence is the interpretation record itself. Cited rather
            # than left empty: an artifact resting on nothing cannot form.
            evidence=EvidencePackage(
                items=(
                    EvidenceItem(
                        reference="int-1",
                        source_journal="governance_gateway",
                        observed_at=datetime(2026, 8, 1, tzinfo=UTC),
                        summary="interpretation int-1, grounded in 11.2.1, 11.21.2 and 12.17",
                    ),
                )
            ),
            formed_at=datetime(2026, 8, 1, tzinfo=UTC),
        ),
    )
    governance.request_review("ga-int", timedelta(days=7))

    # The forming steward may not ratify their own artifact (15.25.4), even
    # holding G4. A second human does, which is 15 rule 2 satisfied by a
    # different person rather than by the same one wearing two hats.
    with pytest.raises(IndependenceViolation):
        governance.ratify(human_token, "ga-int")
    record = governance.ratify(admin_token, "ga-int")
    assert record.state == ArtifactState.RATIFIED
    assert record.ratified_by == ADMIN


def test_meta_oversight_declares_without_intervening(
    governance: GovernanceGateway,
    runtime: AgentRuntime,
    steward_token: str,
    auditor_token: str,
) -> None:
    """15.22.3 — Governance "may not directly modify subsystem internals".

    The finding lands; the agent's state does not move. That gap is the whole
    point: remediation is routed through the subsystem's own governance or
    through human authority, never executed here.
    """
    before = runtime.get(SUBJECT).state
    governance.register_journal("agent_runtime", ImmutableJournalSource(journal=runtime.journal))
    finding = governance.conduct_review(
        auditor_token,
        "find-1",
        SCOPE,
        ReviewKind.TRIGGERED,
        ComplianceState.NON_COMPLIANT,
        "the analyst executed outside its declared memory scope",
        governance.assemble_evidence(TENANT, ["agent_runtime"]),
        recommendation="narrow the manifest's memory scope",
    )
    assert finding.compliance == ComplianceState.NON_COMPLIANT
    assert runtime.get(SUBJECT).state == before, "Governance changed nothing in the subsystem"
    assert governance.compliance_of(SCOPE) == ComplianceState.NON_COMPLIANT


# --------------------------------------- Observability, full interpretive


def test_governance_and_observability_read_the_same_journals_without_a_cycle(
    governance: GovernanceGateway,
    observability: ObservabilityGateway,
    runtime: AgentRuntime,
    human: HumanInterface,
    human_token: str,
) -> None:
    """15.7.2 resolving the Governance to Observability circular dependency.

    Both read subsystem journals directly. Neither waits on the other, and the
    dependency 21A's graph flags as circular does not exist in the running
    system because the edge each would need is a *read of a third party*.
    """
    human.invoke_panic(HUMAN, "drill")
    human.resume(HUMAN)

    observability.register_journal("agent_runtime", runtime.journal)
    observability.register_journal("human_interface", human.panic.journal)
    governance.register_journal("agent_runtime", ImmutableJournalSource(journal=runtime.journal))

    timeline = observability.correlate(human_token, TENANT, "kind", "panic")
    assert [e.action for e in timeline.events] == ["invoked", "resumed"]

    package = governance.assemble_evidence(TENANT, ["agent_runtime"])
    assert package.items
    assert observability.health()["correlation"]["journals_registered"] == 2


def test_observability_publishes_slos_and_alerts_without_enforcing(
    observability: ObservabilityGateway,
) -> None:
    """21B §24.5 — SLI publication is "informational; not enforced by Observability"."""
    breach = observability.record_sli("panic.completion", observed=7.0)
    assert not breach.meets_target
    assert observability.alerts.alerts(Severity.WARNING)
    assert observability.slos.attainment("panic.completion") == 0.0


def test_constitutional_health_is_evidence_not_a_verdict(
    observability: ObservabilityGateway,
) -> None:
    """16.26 composed, with 15.6.1 respected: only Governance declares compliance."""
    observability.journal.append({"kind": "telemetry", "action": "ingested"})
    report = observability.constitutional_health(
        tenant_id=TENANT,
        approvals_required=4,
        approvals_obtained=4,
        subsystems_reporting=10,
        subsystems_total=12,
        escalations_raised=2,
        escalations_acknowledged=2,
    ).to_report()
    assert report["is_a_compliance_ruling"] is False
    assert report["human_approval_coverage"] == 1.0


def test_a_human_override_of_a_governance_artifact_is_recorded(
    human: HumanInterface, governance: GovernanceGateway, steward_token: str, runtime: AgentRuntime
) -> None:
    """15.9.3 — a human sovereign may override any governance artifact at any state."""
    governance.register_journal("agent_runtime", ImmutableJournalSource(journal=runtime.journal))
    governance.form(
        steward_token,
        GovernanceArtifact(
            artifact_id="ga-1",
            tenant_id=TENANT,
            steward_id=STEWARD,
            g_class=GClass.G2,
            scope=SCOPE,
            subject="publication review cadence",
            rationale="weekly review has been sufficient for two quarters",
            evidence=governance.assemble_evidence(TENANT, ["agent_runtime"]),
            formed_at=datetime(2026, 8, 1, tzinfo=UTC),
        ),
    )
    override = human.override(
        "ov-gov",
        TENANT,
        OverrideScope.DECISION,
        "ga-1",
        "retire this artifact",
        "the cadence assumption no longer holds after the provider change",
        HUMAN,
    )
    assert override.decision_class == "D"
    assert human.overrides.latest_for("ga-1") is override


def test_governance_reports_its_own_overhead(governance: GovernanceGateway) -> None:
    """21B §23.11 with CIR-008 — measured and reported, not assumed acceptable."""
    governance.record_cost(governance=3.0, operational=97.0)
    overhead = governance.health()["overhead"]
    assert overhead["overhead_ratio"] == 0.03
    assert overhead["ceiling"] == 0.15
    assert not overhead["circuit_breaker_breached"]


def test_an_emergency_suspension_is_visible_until_reviewed(
    governance: GovernanceGateway, steward_token: str, clock: Clock
) -> None:
    """15.17.6 — immediate, but requiring G3 review within 24 hours."""
    governance.form_policy(steward_token, policy("pol-1", PolicyLayer.BUSINESS, SCOPE))
    governance.activate_policy("pol-1")
    governance.emergency_suspend_policy("pol-1", "contradicts the new portfolio rule")
    assert governance.policy("pol-1").state == PolicyState.SUSPENDED
    clock.advance(timedelta(hours=25))
    assert [p.policy_id for p in governance.overdue_emergency_reviews()] == ["pol-1"]
