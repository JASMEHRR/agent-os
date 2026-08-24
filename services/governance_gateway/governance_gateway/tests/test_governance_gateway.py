"""Governance Gateway conformance tests (15, per 21B §23).

`15.6.1`: "No subsystem may self-certify its own constitutional compliance."

Governance is the subsystem whose failure is hardest to notice, because a
compromised overseer reports that everything is fine. So the rules tested
hardest are the ones that keep it honest about itself:

* no self-certification, and no reviewing or auditing a scope you are
  accountable for (15.6.1, 15.25.4, 15.27.4);
* timeout never ratifies (15.8.2, 15.28.4);
* meta-oversight observes and never intervenes (15.22.3);
* no artifact contradicts a non-violable rule, screened at formation (15.6.3).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from core.exceptions import AgentOSError, NotFoundError, ValidationError
from governance_gateway import (
    DRIFT_VELOCITY_THRESHOLD,
    EMERGENCY_REVIEW_WINDOW,
    GOVERNANCE_OVERHEAD_CEILING,
    ArtifactState,
    ComplianceState,
    EvidenceItem,
    EvidencePackage,
    GClass,
    GovernanceException,
    GovernanceGateway,
    IndependenceViolation,
    Interpretation,
    NonViolableViolation,
    OrphanedPolicy,
    Policy,
    PolicyContradiction,
    PolicyLayer,
    PolicyState,
    ReviewKind,
    SelfCertification,
    Stewardship,
)
from governance_gateway.artifacts import GovernanceArtifact
from kernel.signals import SignalEmitter

TENANT = "tenant-alpha"
HUMAN = "human-sovereign"
STEWARD = "agent-steward"
AUDITOR = "agent-auditor"
SCOPE = "portfolio/pricing"


class Clock:
    def __init__(self) -> None:
        self.now = datetime(2026, 8, 1, 12, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.now

    def advance(self, delta: timedelta) -> None:
        self.now += delta


class FakeAuthorizer:
    def __init__(self) -> None:
        self.tokens = {
            "tok-human": (HUMAN, TENANT),
            "tok-steward": (STEWARD, TENANT),
            "tok-auditor": (AUDITOR, TENANT),
            "tok-other": ("agent-x", "tenant-beta"),
        }

    def principal_of(self, token: str) -> tuple[str, str]:
        return self.tokens[token]

    def is_human(self, principal_id: str) -> bool:
        return principal_id.startswith("human-")


class FakeJournal:
    """A subsystem journal, read directly per 15.7.2."""

    def __init__(self, payloads: list[dict[str, Any]]) -> None:
        self.payloads = payloads

    def entries(self, scope: str) -> list[dict[str, Any]]:
        return [p for p in self.payloads if p.get("scope") == scope]


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def alerts() -> list[str]:
    return []


@pytest.fixture
def escalations() -> list[tuple[Any, str]]:
    return []


@pytest.fixture
def gateway(clock: Clock, alerts: list[str], escalations: list[tuple[Any, str]]) -> GovernanceGateway:
    gw = GovernanceGateway(
        authorizer=FakeAuthorizer(),
        signals=SignalEmitter(source_identity="governance_gateway"),
        escalate=lambda trigger, detail: escalations.append((trigger, detail)),
        alert_human=alerts.append,
        now=clock,
    )
    gw.assign_stewardship(
        "tok-human",
        Stewardship(
            stewardship_id="st-1",
            tenant_id=TENANT,
            principal_id=STEWARD,
            scope=SCOPE,
            g_class=GClass.G2,
            assigned_at=clock(),
            expires_at=clock() + timedelta(days=90),
        ),
    )
    return gw


def evidence(gaps: tuple[str, ...] = ()) -> EvidencePackage:
    return EvidencePackage(
        items=(
            EvidenceItem(
                reference="dec-1",
                source_journal="decision_gateway",
                observed_at=datetime(2026, 7, 20, tzinfo=UTC),
                summary="a Class C decision was approved by a human",
            ),
        ),
        gaps=gaps,
    )


def artifact(artifact_id: str = "ga-1", **overrides: Any) -> GovernanceArtifact:
    defaults: dict[str, Any] = {
        "artifact_id": artifact_id,
        "tenant_id": TENANT,
        "steward_id": STEWARD,
        "g_class": GClass.G2,
        "scope": SCOPE,
        "subject": "approval gate coverage in the pricing portfolio",
        "rationale": "three consecutive reviews found complete approval coverage",
        "evidence": evidence(),
        "formed_at": datetime(2026, 8, 1, tzinfo=UTC),
    }
    defaults.update(overrides)
    return GovernanceArtifact(**defaults)


def policy(policy_id: str = "pol-1", **overrides: Any) -> Policy:
    defaults: dict[str, Any] = {
        "policy_id": policy_id,
        "tenant_id": TENANT,
        "layer": PolicyLayer.BUSINESS,
        "scope": SCOPE,
        "statement": "publications above ten thousand require a second reviewer",
        "constitutional_lineage": "11.14.3",
        "steward_id": STEWARD,
        "sunset_condition": "when the automated reviewer reaches ninety percent agreement",
        "risk_assessment": "medium: adds latency to routine publications",
        "expected_outcome": "publication error rate falls below one percent",
        "formed_at": datetime(2026, 8, 1, tzinfo=UTC),
    }
    defaults.update(overrides)
    return Policy(**defaults)


# ------------------------------------------------------------ Evidence (15.7.2)


def test_evidence_is_assembled_directly_from_subsystem_journals(gateway: GovernanceGateway) -> None:
    """15.7.2 — what breaks the Governance to Observability circular dependency.

    Governance does not wait for the full Observability profile before it can
    see anything; it reads the journals themselves.
    """
    gateway.register_journal("decision_gateway", FakeJournal([{"scope": SCOPE, "action": "committed"}]))
    package = gateway.assemble_evidence(SCOPE, ["decision_gateway"])
    assert len(package.items) == 1
    assert package.items[0].source_journal == "decision_gateway"
    assert not package.has_gaps


def test_a_missing_journal_is_reported_as_a_gap_not_omitted(gateway: GovernanceGateway) -> None:
    """15 rule 1 — documented evidence **or a gap flag**.

    Silence about a missing journal makes an assessment look better founded
    than it is, which is how an oversight subsystem lies without anyone
    intending it to.
    """
    package = gateway.assemble_evidence(SCOPE, ["decision_gateway", "tool_gateway"])
    assert package.items == ()
    assert len(package.gaps) == 2
    assert "no journal registered for 'decision_gateway'" in package.gaps


def test_an_empty_journal_is_also_a_gap(gateway: GovernanceGateway) -> None:
    gateway.register_journal("tool_gateway", FakeJournal([]))
    package = gateway.assemble_evidence(SCOPE, ["tool_gateway"])
    assert "has no journal entries" in package.gaps[0]


# ------------------------------------------------------------------ Formation


def test_an_artifact_requires_evidence_or_a_declared_gap(gateway: GovernanceGateway) -> None:
    with pytest.raises(ValidationError, match="neither evidence nor a gap"):
        gateway.form("tok-steward", artifact(evidence=EvidencePackage(items=(), gaps=())))


def test_an_artifact_requires_an_accountable_steward_covering_its_scope(
    gateway: GovernanceGateway,
) -> None:
    """15.23.3 — "No governance artifact exists without an accountable steward.\""""
    with pytest.raises(AgentOSError, match="holds no active stewardship"):
        gateway.form("tok-steward", artifact(steward_id=AUDITOR))
    with pytest.raises(AgentOSError, match="holds no active stewardship"):
        gateway.form("tok-steward", artifact(artifact_id="ga-2", scope="portfolio/other"))


def test_a_steward_cannot_form_above_their_g_class(gateway: GovernanceGateway) -> None:
    """15 rule 5 — no steward ratifies beyond their autonomy level."""
    with pytest.raises(AgentOSError, match="holds no active stewardship at G3"):
        gateway.form("tok-steward", artifact(g_class=GClass.G3))


@pytest.mark.parametrize(
    "subject",
    [
        "reduce human sovereignty in routine publications",
        "waive the panic protocol during maintenance",
        "bypass the approval gate for low-value decisions",
        "suspend tenant isolation between the two pricing businesses",
        "amend a non-violable rule to permit faster iteration",
        "remove the audit trail requirement for internal tools",
    ],
)
def test_an_artifact_contradicting_a_non_violable_rule_is_refused_at_formation(
    gateway: GovernanceGateway, subject: str
) -> None:
    """15.6.3 with 15.20.5, screened before review.

    An artifact that reached review would already have a constituency, and
    withdrawing it then costs more than refusing it now.
    """
    with pytest.raises(NonViolableViolation):
        gateway.form("tok-steward", artifact(subject=subject))


def test_g4_authority_cannot_be_held_by_a_machine(gateway: GovernanceGateway, clock: Clock) -> None:
    """15.9.1 and 15.33.2 — G4 is human-only and cannot be delegated."""
    gateway.assign_stewardship(
        "tok-human",
        Stewardship(
            stewardship_id="st-g4",
            tenant_id=TENANT,
            principal_id=HUMAN,
            scope=SCOPE,
            g_class=GClass.G4,
            assigned_at=clock(),
            expires_at=clock() + timedelta(days=90),
        ),
    )
    with pytest.raises(AgentOSError, match="G4 authority is human-only"):
        gateway.form("tok-steward", artifact(g_class=GClass.G4, steward_id=STEWARD))


def test_a_g4_stewardship_cannot_be_assigned_to_a_machine(gateway: GovernanceGateway, clock: Clock) -> None:
    with pytest.raises(AgentOSError, match="G4 stewardship cannot be delegated"):
        gateway.assign_stewardship(
            "tok-human",
            Stewardship(
                stewardship_id="st-bad",
                tenant_id=TENANT,
                principal_id=STEWARD,
                scope=SCOPE,
                g_class=GClass.G4,
                assigned_at=clock(),
                expires_at=clock() + timedelta(days=1),
            ),
        )


def test_a_duplicate_artifact_id_is_refused(gateway: GovernanceGateway) -> None:
    gateway.form("tok-steward", artifact())
    with pytest.raises(AgentOSError, match="already exists"):
        gateway.form("tok-steward", artifact())


def test_the_artifact_core_is_frozen(gateway: GovernanceGateway) -> None:
    """15.8.3 — corrections append new artifacts; they do not mutate records."""
    record = gateway.form("tok-steward", artifact())
    with pytest.raises(Exception):  # noqa: B017 - FrozenInstanceError
        record.artifact.rationale = "something else"  # type: ignore[misc]


# ------------------------------------------------- Assessment (15.6.1, 15.18)


def test_no_principal_may_certify_a_scope_they_are_accountable_for(
    gateway: GovernanceGateway,
) -> None:
    """15.6.1, the subsystem's defining rule.

    The steward accountable for the pricing portfolio grading the pricing
    portfolio is precisely the self-certification the clause forbids.
    """
    gateway.form("tok-steward", artifact())
    with pytest.raises(SelfCertification, match="may not certify its compliance"):
        gateway.assess("tok-steward", "ga-1", ComplianceState.COMPLIANT, 0.9)


def test_an_independent_principal_may_assess(gateway: GovernanceGateway) -> None:
    gateway.form("tok-steward", artifact())
    record = gateway.assess("tok-auditor", "ga-1", ComplianceState.COMPLIANT, 0.85, "coverage is complete")
    assert record.state == ArtifactState.RULED
    assert record.compliance == ComplianceState.COMPLIANT
    assert gateway.compliance_of(SCOPE) == ComplianceState.COMPLIANT


@pytest.mark.parametrize(
    ("g_class", "confidence", "permitted"),
    [
        (GClass.G1, 0.70, True),
        (GClass.G1, 0.69, False),
        (GClass.G2, 0.80, True),
        (GClass.G2, 0.79, False),
        (GClass.G3, 0.90, True),
        (GClass.G3, 0.89, False),
    ],
)
def test_confidence_thresholds_by_authority_are_enforced(
    gateway: GovernanceGateway, clock: Clock, g_class: GClass, confidence: float, permitted: bool
) -> None:
    """15.9.2, applied as a gate rather than as advice."""
    gateway.assign_stewardship(
        "tok-human",
        Stewardship(
            stewardship_id=f"st-{g_class.name}",
            tenant_id=TENANT,
            principal_id=STEWARD,
            scope=SCOPE,
            g_class=GClass.G3,
            assigned_at=clock(),
            expires_at=clock() + timedelta(days=90),
        ),
    )
    gateway.form("tok-steward", artifact(artifact_id=f"ga-{g_class.name}", g_class=g_class))
    if permitted:
        assert gateway.assess("tok-auditor", f"ga-{g_class.name}", ComplianceState.COMPLIANT, confidence)
    else:
        with pytest.raises(ValidationError, match="requires confidence"):
            gateway.assess("tok-auditor", f"ga-{g_class.name}", ComplianceState.COMPLIANT, confidence)


def test_evidence_gaps_produce_an_uncertainty_rider(gateway: GovernanceGateway) -> None:
    """21B §23.9 — permitted with a rider and enhanced monitoring, not silently."""
    gateway.form("tok-steward", artifact(evidence=evidence(gaps=("tool_gateway journal unavailable",))))
    record = gateway.assess("tok-auditor", "ga-1", ComplianceState.COMPLIANT, 0.85)
    assert "evidence gaps" in record.uncertainty_rider
    assert "enhanced monitoring" in record.uncertainty_rider


def test_a_non_compliant_ruling_records_remediation_rather_than_performing_it(
    gateway: GovernanceGateway, alerts: list[str]
) -> None:
    """15.18.4 — "The Gateway monitors remediation execution but does not execute it.\""""
    gateway.form("tok-steward", artifact())
    record = gateway.assess(
        "tok-auditor", "ga-1", ComplianceState.NON_COMPLIANT, 0.9, "two publications bypassed the gate"
    )
    assert record.remediation
    assert alerts, "a non-compliant finding reached a human"


def test_meta_oversight_holds_no_execution_path_into_any_subsystem() -> None:
    """15.22.3 — Governance "may not directly modify subsystem internals".

    Structural. A Gateway that could suspend an agent or retire a tool would be
    driving the vehicle, which 15.2.1 says it does not do.
    """
    forbidden = {
        "suspend_agent",
        "reassign",
        "modify_subsystem",
        "execute",
        "remediate",
        "enforce",
        "halt",
        "reconfigure",
    }
    present = {name for name in dir(GovernanceGateway) if not name.startswith("_")}
    assert not (forbidden & present), f"Governance acquired an execution path: {forbidden & present}"


# --------------------------------------------------- Ratification (15.8.2)


def test_a_review_timeout_rejects_and_never_ratifies(gateway: GovernanceGateway, clock: Clock) -> None:
    """15.8.2 — "timeout without response (does NOT auto-ratify)"."""
    gateway.form("tok-steward", artifact())
    gateway.request_review("ga-1", timedelta(days=7))
    clock.advance(timedelta(days=8))
    expired = gateway.expire_reviews()
    assert [r.state for r in expired] == [ArtifactState.REJECTED]
    assert gateway.get("ga-1").state != ArtifactState.RATIFIED


def test_a_g3_review_timeout_escalates_further_and_never_ratifies(
    gateway: GovernanceGateway, clock: Clock, alerts: list[str]
) -> None:
    """15.28.4 — escalation timeout escalates further rather than ratifying."""
    gateway.assign_stewardship(
        "tok-human",
        Stewardship(
            stewardship_id="st-g3",
            tenant_id=TENANT,
            principal_id=STEWARD,
            scope=SCOPE,
            g_class=GClass.G3,
            assigned_at=clock(),
            expires_at=clock() + timedelta(days=90),
        ),
    )
    gateway.form("tok-steward", artifact(artifact_id="ga-g3", g_class=GClass.G3))
    gateway.request_review("ga-g3", timedelta(days=7))
    clock.advance(timedelta(days=8))
    expired = gateway.expire_reviews()
    assert [r.state for r in expired] == [ArtifactState.ESCALATED]
    assert expired[0].escalations == 1
    assert any("has not been ratified" in alert for alert in alerts)


def test_there_is_no_state_machine_edge_that_ratifies_on_timeout() -> None:
    """The structural form of 15.8.2, checked against the transition table.

    A behavioural test proves the current code does not ratify on timeout. This
    proves no future edit can add that path without changing the table a
    reviewer would read.
    """
    from governance_gateway import GOVERNANCE_TRANSITIONS

    assert ArtifactState.RATIFIED in GOVERNANCE_TRANSITIONS[ArtifactState.UNDER_REVIEW], (
        "an explicit human grant must still be able to ratify"
    )
    # And the only method that acts on an elapsed deadline cannot produce it.
    import inspect

    source = inspect.getsource(GovernanceGateway.expire_reviews)
    assert "RATIFIED" not in source, "expire_reviews must have no path to Ratified"


def test_g3_and_above_ratification_requires_a_human(gateway: GovernanceGateway, clock: Clock) -> None:
    """15 rule 2, and 15.33.2's cryptographic binding to human credentials."""
    gateway.assign_stewardship(
        "tok-human",
        Stewardship(
            stewardship_id="st-g3",
            tenant_id=TENANT,
            principal_id=STEWARD,
            scope=SCOPE,
            g_class=GClass.G3,
            assigned_at=clock(),
            expires_at=clock() + timedelta(days=90),
        ),
    )
    gateway.form("tok-steward", artifact(artifact_id="ga-g3", g_class=GClass.G3))
    gateway.request_review("ga-g3", timedelta(days=7))
    with pytest.raises(AgentOSError, match="requires human confirmation"):
        gateway.ratify("tok-auditor", "ga-g3")
    assert gateway.ratify("tok-human", "ga-g3").state == ArtifactState.RATIFIED


def test_the_forming_steward_may_not_also_ratify(gateway: GovernanceGateway) -> None:
    """15.25.4's separation of duties, applied to ratification."""
    gateway.form("tok-steward", artifact())
    gateway.request_review("ga-1", timedelta(days=7))
    with pytest.raises(IndependenceViolation, match="may not also ratify"):
        gateway.ratify("tok-steward", "ga-1")


def test_a_ratified_artifact_activates(gateway: GovernanceGateway) -> None:
    gateway.form("tok-steward", artifact())
    gateway.request_review("ga-1", timedelta(days=7))
    gateway.ratify("tok-human", "ga-1")
    assert gateway.activate("ga-1").state == ArtifactState.ACTIVE


# ------------------------------------------------- Interpretation (15.19)


def test_an_interpretation_that_would_alter_meaning_is_refused(gateway: GovernanceGateway) -> None:
    """15.19.2 — it exceeds interpretation authority and must be an amendment."""
    with pytest.raises(ValidationError, match="must proceed as a G4 amendment"):
        gateway.interpret(
            "tok-human",
            Interpretation(
                interpretation_id="int-1",
                tenant_id=TENANT,
                question="does 14.12.4 permit union under emergency?",
                provision="14.12.4",
                resolution="yes, during declared emergencies",
                grounded_in=("14.12.4",),
                g_class=GClass.G3,
                scope=SCOPE,
                interpreted_by=HUMAN,
                interpreted_at=datetime(2026, 8, 1, tzinfo=UTC),
                alters_meaning=True,
            ),
        )


def test_an_ungrounded_interpretation_is_refused(gateway: GovernanceGateway) -> None:
    """15.19.1 — an ungrounded interpretation is an invention."""
    with pytest.raises(ValidationError, match="grounded in"):
        gateway.interpret(
            "tok-human",
            Interpretation(
                interpretation_id="int-2",
                tenant_id=TENANT,
                question="what does 'timely' mean?",
                provision="16.14",
                resolution="within one hour",
                grounded_in=(),
                g_class=GClass.G2,
                scope=SCOPE,
                interpreted_by=HUMAN,
                interpreted_at=datetime(2026, 8, 1, tzinfo=UTC),
            ),
        )


def test_a_g3_interpretation_requires_human_authority(gateway: GovernanceGateway) -> None:
    with pytest.raises(AgentOSError, match="requires human authority"):
        gateway.interpret(
            "tok-steward",
            Interpretation(
                interpretation_id="int-3",
                tenant_id=TENANT,
                question="is a tool invocation a decision?",
                provision="11.2.1",
                resolution="only when it commits an external effect",
                grounded_in=("11.2.1", "12.17"),
                g_class=GClass.G3,
                scope=SCOPE,
                interpreted_by=STEWARD,
                interpreted_at=datetime(2026, 8, 1, tzinfo=UTC),
            ),
        )


def test_an_interpretation_is_retrievable_by_provision(gateway: GovernanceGateway) -> None:
    """The mechanism through which 21A §3's Interpretation Register is resolved."""
    gateway.interpret(
        "tok-human",
        Interpretation(
            interpretation_id="int-4",
            tenant_id=TENANT,
            question="does 03 naming technologies bind construction?",
            provision="CIR-001",
            resolution="deferred; this is an example, not a ruling on CIR-001",
            grounded_in=("17.4", "18.5", "19.6"),
            g_class=GClass.G2,
            scope=SCOPE,
            interpreted_by=HUMAN,
            interpreted_at=datetime(2026, 8, 1, tzinfo=UTC),
        ),
    )
    assert [i.interpretation_id for i in gateway.interpretations_for("CIR-001")] == ["int-4"]


# ------------------------------------------------ Policy hierarchy (15.16)


def test_a_policy_without_constitutional_lineage_is_rejected(gateway: GovernanceGateway) -> None:
    """15.16.2 — "A policy without constitutional lineage is illegitimate.\""""
    with pytest.raises(OrphanedPolicy, match="traces to no constitutional provision"):
        gateway.form_policy("tok-steward", policy(constitutional_lineage="  "))


def test_a_policy_without_a_sunset_condition_is_rejected(gateway: GovernanceGateway) -> None:
    """15.17.1 — a policy nobody planned to retire is a policy nobody will."""
    with pytest.raises(ValidationError, match="sunset condition"):
        gateway.form_policy("tok-steward", policy(sunset_condition=""))


def test_a_lower_layer_may_not_permit_what_a_higher_layer_prohibits(
    gateway: GovernanceGateway,
) -> None:
    """15.16.3 — such a policy is void, and is blocked at formation."""
    gateway.form_policy(
        "tok-steward",
        policy(
            policy_id="pol-portfolio",
            layer=PolicyLayer.PORTFOLIO,
            scope="portfolio",
            prohibits=frozenset({"single_reviewer_publication"}),
        ),
    )
    with pytest.raises(PolicyContradiction, match="is void"):
        gateway.form_policy(
            "tok-steward",
            policy(
                policy_id="pol-business",
                layer=PolicyLayer.BUSINESS,
                permits=frozenset({"single_reviewer_publication"}),
            ),
        )


def test_a_higher_layer_is_not_bound_by_a_lower_one(gateway: GovernanceGateway) -> None:
    """The hierarchy runs one way. A subsystem policy cannot constrain a portfolio."""
    gateway.form_policy(
        "tok-steward",
        policy(policy_id="pol-sub", layer=PolicyLayer.SUBSYSTEM, prohibits=frozenset({"batch_publication"})),
    )
    assert gateway.form_policy(
        "tok-steward",
        policy(
            policy_id="pol-port",
            layer=PolicyLayer.PORTFOLIO,
            scope="portfolio",
            permits=frozenset({"batch_publication"}),
        ),
    )


def test_a_contradiction_emerging_after_activation_suspends_the_lower_policy(
    gateway: GovernanceGateway, clock: Clock
) -> None:
    """15.16.3 — "automatically suspended pending review".

    Automatic, because the alternative is a window in which two contradictory
    policies are both active and subsystems are choosing between them.
    """
    gateway.form_policy(
        "tok-steward",
        policy(policy_id="pol-low", layer=PolicyLayer.BUSINESS, permits=frozenset({"skip_second_review"})),
    )
    gateway.activate_policy("pol-low")
    gateway.form_policy(
        "tok-steward",
        policy(
            policy_id="pol-high",
            layer=PolicyLayer.PORTFOLIO,
            scope="portfolio",
            prohibits=frozenset({"skip_second_review"}),
        ),
    )
    gateway.activate_policy("pol-high")

    suspended = gateway.detect_contradictions()
    assert [p.policy_id for p in suspended] == ["pol-low"]
    assert gateway.policy("pol-low").state == PolicyState.SUSPENDED
    assert gateway.policy("pol-low").review_due_at == clock() + EMERGENCY_REVIEW_WINDOW


def test_an_emergency_suspension_requires_g3_review_within_24_hours(
    gateway: GovernanceGateway, clock: Clock, alerts: list[str]
) -> None:
    """15.17.6."""
    gateway.form_policy("tok-steward", policy())
    gateway.activate_policy("pol-1")
    gateway.emergency_suspend_policy("pol-1", "active constitutional contradiction detected")
    assert any("24 hours" in alert for alert in alerts)
    assert gateway.overdue_emergency_reviews() == []
    clock.advance(EMERGENCY_REVIEW_WINDOW + timedelta(minutes=1))
    assert [p.policy_id for p in gateway.overdue_emergency_reviews()] == ["pol-1"]


def test_supersession_preserves_lineage_rather_than_erasing_it(gateway: GovernanceGateway) -> None:
    """15.17.4 — "Supersession does not erase history.\""""
    gateway.form_policy("tok-steward", policy())
    gateway.form_policy("tok-steward", policy(policy_id="pol-2"))
    superseded = gateway.supersede_policy("pol-1", "pol-2")
    assert superseded.state == PolicyState.SUPERSEDED
    assert superseded.superseded_by == "pol-2"
    assert gateway.policy("pol-1") is superseded, "the superseded policy is still readable"


def test_a_lower_layer_policy_may_not_supersede_a_higher_one(gateway: GovernanceGateway) -> None:
    gateway.form_policy("tok-steward", policy(policy_id="pol-high", layer=PolicyLayer.PORTFOLIO, scope="portfolio"))
    gateway.form_policy("tok-steward", policy(policy_id="pol-low", layer=PolicyLayer.SUBSYSTEM))
    with pytest.raises(ValidationError, match="may not supersede"):
        gateway.supersede_policy("pol-high", "pol-low")


def test_applicable_policies_are_returned_highest_authority_first(gateway: GovernanceGateway) -> None:
    gateway.form_policy("tok-steward", policy(policy_id="pol-sub", layer=PolicyLayer.SUBSYSTEM))
    gateway.form_policy("tok-steward", policy(policy_id="pol-port", layer=PolicyLayer.PORTFOLIO, scope="portfolio"))
    for pid in ("pol-sub", "pol-port"):
        gateway.activate_policy(pid)
    applicable = gateway.applicable_policies(TENANT, f"{SCOPE}/publication")
    assert [p.policy_id for p in applicable] == ["pol-port", "pol-sub"]


def test_an_unknown_policy_is_a_not_found(gateway: GovernanceGateway) -> None:
    with pytest.raises(NotFoundError):
        gateway.policy("pol-nobody")


# ------------------------------------------------------ Stewardship (15.23)


def test_a_stewardship_is_time_bounded(gateway: GovernanceGateway, clock: Clock) -> None:
    with pytest.raises(ValidationError, match="time-bounded"):
        gateway.assign_stewardship(
            "tok-human",
            Stewardship(
                stewardship_id="st-past",
                tenant_id=TENANT,
                principal_id=STEWARD,
                scope=SCOPE,
                g_class=GClass.G1,
                assigned_at=clock(),
                expires_at=clock() - timedelta(days=1),
            ),
        )


def test_an_expired_stewardship_stops_covering_its_scope(gateway: GovernanceGateway, clock: Clock) -> None:
    assert gateway.accountability_chain(SCOPE)
    clock.advance(timedelta(days=91))
    assert gateway.accountability_chain(SCOPE) == []
    assert gateway.stewardship_vacuums([SCOPE]) == [SCOPE]


def test_revocation_without_a_successor_names_the_vacuum(gateway: GovernanceGateway, alerts: list[str]) -> None:
    """21B §23.9 — a stewardship vacuum is Operational, and named rather than silent."""
    gateway.revoke_stewardship("st-1")
    assert any("stewardship vacuum" in alert for alert in alerts)
    assert gateway.accountability_chain(SCOPE) == []


def test_revocation_transfers_accountability_to_a_successor(gateway: GovernanceGateway) -> None:
    """15.23.4."""
    revoked = gateway.revoke_stewardship("st-1", successor_id="st-2")
    assert revoked.successor_id == "st-2"


def test_the_accountability_chain_covers_nested_scopes(gateway: GovernanceGateway) -> None:
    """15.23.3 — the chain traces from artifact to steward to human sovereign."""
    chain = gateway.accountability_chain(f"{SCOPE}/publication/q3")
    assert [s.stewardship_id for s in chain] == ["st-1"]


# ------------------------------------------- Independence (15.25.4, 15.27.4)


def test_a_principal_may_not_audit_a_scope_they_are_accountable_for(
    gateway: GovernanceGateway,
) -> None:
    """15.27.4, refused at assignment because a compromised audit is worth nothing."""
    with pytest.raises(IndependenceViolation, match="may not review or audit it"):
        gateway.conduct_review(
            "tok-steward",
            "find-1",
            SCOPE,
            ReviewKind.SCHEDULED,
            ComplianceState.COMPLIANT,
            "all clear",
            evidence(),
        )


def test_an_independent_auditor_may_review(gateway: GovernanceGateway) -> None:
    finding = gateway.conduct_review(
        "tok-auditor",
        "find-1",
        SCOPE,
        ReviewKind.SCHEDULED,
        ComplianceState.DRIFTING,
        "approval latency has doubled",
        evidence(),
        recommendation="add a second reviewer",
    )
    assert finding.auditor_id == AUDITOR
    assert gateway.findings(SCOPE) == [finding]


@pytest.mark.parametrize("kind", list(ReviewKind))
def test_every_documented_review_kind_is_available(gateway: GovernanceGateway, kind: ReviewKind) -> None:
    """15.25.1's four types."""
    finding = gateway.conduct_review(
        "tok-auditor", f"find-{kind.value}", SCOPE, kind, ComplianceState.COMPLIANT, "", evidence()
    )
    assert finding.kind == kind


# ----------------------------------------------------- Exceptions (15.29)


def test_an_exception_must_carry_all_four_constraints(gateway: GovernanceGateway, clock: Clock) -> None:
    """15 rule 17 — time-bounded, scope-limited, risk-assessed, post-hoc reviewed."""
    base: dict[str, Any] = {
        "exception_id": "ex-1",
        "tenant_id": TENANT,
        "granted_by": HUMAN,
        "g_class": GClass.G2,
        "recipient_scope": SCOPE,
        "deviation": "skip the second reviewer during the migration window",
        "risk_acknowledgment": "publication error rate may rise for two weeks",
        "granted_at": clock(),
        "expires_at": clock() + timedelta(days=14),
        "post_hoc_review_due": clock() + timedelta(days=21),
    }
    assert gateway.grant_exception("tok-human", GovernanceException(**base))

    for field_name, bad_value, message in (
        ("expires_at", clock(), "time-bounded"),
        ("recipient_scope", "  ", "scope-limited"),
        ("risk_acknowledgment", "", "risk acknowledgment"),
        ("post_hoc_review_due", clock(), "post-hoc review"),
    ):
        bad = dict(base)
        bad["exception_id"] = f"ex-{field_name}"
        bad[field_name] = bad_value
        with pytest.raises(ValidationError, match=message):
            gateway.grant_exception("tok-human", GovernanceException(**bad))


def test_a_g4_exception_requires_human_authority(gateway: GovernanceGateway, clock: Clock) -> None:
    """15.29.2 — G4 for exceptions touching constitutional provisions."""
    with pytest.raises(AgentOSError, match="requires G4"):
        gateway.grant_exception(
            "tok-steward",
            GovernanceException(
                exception_id="ex-g4",
                tenant_id=TENANT,
                granted_by=STEWARD,
                g_class=GClass.G4,
                recipient_scope=SCOPE,
                deviation="deviate from a constitutional provision",
                risk_acknowledgment="high",
                granted_at=clock(),
                expires_at=clock() + timedelta(days=1),
                post_hoc_review_due=clock() + timedelta(days=2),
            ),
        )


def test_an_exception_expires_automatically(gateway: GovernanceGateway, clock: Clock) -> None:
    """15.29.3 — "Exceptions expire automatically and require explicit renewal.\""""
    gateway.grant_exception(
        "tok-human",
        GovernanceException(
            exception_id="ex-1",
            tenant_id=TENANT,
            granted_by=HUMAN,
            g_class=GClass.G2,
            recipient_scope=SCOPE,
            deviation="skip the second reviewer",
            risk_acknowledgment="error rate may rise",
            granted_at=clock(),
            expires_at=clock() + timedelta(days=14),
            post_hoc_review_due=clock() + timedelta(days=21),
        ),
    )
    assert len(gateway.active_exceptions()) == 1
    clock.advance(timedelta(days=15))
    assert gateway.active_exceptions() == []


def test_a_missed_post_hoc_review_is_surfaced(gateway: GovernanceGateway, clock: Clock) -> None:
    """An expired exception whose review never happened is how a provisional
    deviation quietly becomes a permanent one."""
    gateway.grant_exception(
        "tok-human",
        GovernanceException(
            exception_id="ex-1",
            tenant_id=TENANT,
            granted_by=HUMAN,
            g_class=GClass.G2,
            recipient_scope=SCOPE,
            deviation="skip the second reviewer",
            risk_acknowledgment="error rate may rise",
            granted_at=clock(),
            expires_at=clock() + timedelta(days=14),
            post_hoc_review_due=clock() + timedelta(days=21),
        ),
    )
    clock.advance(timedelta(days=22))
    assert [e.exception_id for e in gateway.overdue_exception_reviews()] == ["ex-1"]
    gateway.review_exception("tok-auditor", "ex-1")
    assert gateway.overdue_exception_reviews() == []


def test_the_granting_authority_may_not_conduct_the_post_hoc_review(gateway: GovernanceGateway, clock: Clock) -> None:
    gateway.grant_exception(
        "tok-human",
        GovernanceException(
            exception_id="ex-1",
            tenant_id=TENANT,
            granted_by=HUMAN,
            g_class=GClass.G2,
            recipient_scope=SCOPE,
            deviation="skip the second reviewer",
            risk_acknowledgment="error rate may rise",
            granted_at=clock(),
            expires_at=clock() + timedelta(days=14),
            post_hoc_review_due=clock() + timedelta(days=21),
        ),
    )
    with pytest.raises(IndependenceViolation, match="may not conduct its post-hoc review"):
        gateway.review_exception("tok-human", "ex-1")


# ---------------------------------------------------------- Drift (15.21)


def test_drift_velocity_escalates_past_the_threshold(
    gateway: GovernanceGateway, alerts: list[str], escalations: list[tuple[Any, str]]
) -> None:
    """15.2.6 — Governance exists to "detect, arrest, and reverse constitutional
    drift before organizational legitimacy collapses"."""
    gateway.record_drift(SCOPE, 0.05)
    assert gateway.compliance_of(SCOPE) != ComplianceState.DRIFTING
    velocity = gateway.record_drift(SCOPE, 0.05 + DRIFT_VELOCITY_THRESHOLD + 0.01)
    assert velocity > DRIFT_VELOCITY_THRESHOLD
    assert gateway.compliance_of(SCOPE) == ComplianceState.DRIFTING
    assert alerts and escalations


def test_a_single_measurement_has_no_velocity(gateway: GovernanceGateway) -> None:
    """Position is not direction; one reading cannot say whether things worsen."""
    assert gateway.record_drift(SCOPE, 0.9) == 0.0


# -------------------------------------------------------- Overhead / health


def test_governance_exposes_its_own_cost(gateway: GovernanceGateway) -> None:
    """21B §23.11 — the Gateway "must expose its own cost to permit the question
    to be answered empirically" (CIR-008)."""
    gateway.record_cost(governance=5.0, operational=95.0)
    assert gateway.overhead_ratio() == 0.05
    assert not gateway.health()["overhead"]["circuit_breaker_breached"]

    gateway.record_cost(governance=20.0)
    assert gateway.overhead_ratio() > GOVERNANCE_OVERHEAD_CEILING
    assert gateway.health()["overhead"]["circuit_breaker_breached"]


def test_health_reports_the_four_metric_families(gateway: GovernanceGateway) -> None:
    """15.26 / 21B §23.11."""
    gateway.form("tok-steward", artifact())
    gateway.assess("tok-auditor", "ga-1", ComplianceState.COMPLIANT, 0.85)
    gateway.form_policy("tok-steward", policy())
    gateway.activate_policy("pol-1")

    health = gateway.health()
    assert set(health) >= {"constitutional_health", "policy_vitality", "legitimacy", "overhead"}
    assert health["constitutional_health"]["compliance_rate"] == 1.0
    assert health["policy_vitality"]["active"] == 1
    assert health["policy_vitality"]["orphan_rate"] == 0.0
    assert health["legitimacy"]["stewardships"] == 1
    assert health["legitimacy"]["ratified_on_timeout"] == 0
    assert health["journal_intact"]


def test_the_journal_records_the_governance_trail(gateway: GovernanceGateway) -> None:
    gateway.form("tok-steward", artifact())
    gateway.assess("tok-auditor", "ga-1", ComplianceState.COMPLIANT, 0.85)
    actions = [str(p.get("action")) for p in gateway.query_journal("ga-1")]
    assert actions == ["formed", "ruled"]


def test_an_unknown_artifact_is_a_not_found(gateway: GovernanceGateway) -> None:
    with pytest.raises(NotFoundError):
        gateway.get("ga-nobody")


def test_cross_subsystem_imports_are_confined_to_the_adapter() -> None:
    import pathlib

    package = pathlib.Path(__file__).resolve().parents[1]
    foreign = ("security_gateway", "observability_gateway", "learning_gateway", "decision_gateway")
    for source in package.glob("*.py"):
        if source.name == "adapters.py":
            continue
        for line in source.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped.startswith(("import ", "from ")):
                continue
            assert not any(name in stripped for name in foreign), (
                f"{source.name} imports another subsystem directly; route it through adapters.py"
            )
