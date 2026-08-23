"""Confidence/Authority Resolution and Category 1 escalation (21A §5.2 items 5, 10)."""

from __future__ import annotations

import pytest

from kernel.authority import (
    MIN_CONFIDENCE_BY_LEVEL,
    AuthorityLevel,
    Outcome,
    RiskClass,
    derive_confidence,
    resolve,
)
from kernel.escalation import (
    Category1Incident,
    EscalationChannel,
    EscalationTrigger,
    NoAppealError,
)

# ------------------------------------------------------------------ authority


def test_the_authority_spectrum_is_ordered() -> None:
    assert AuthorityLevel.AGENT_AUTONOMOUS < AuthorityLevel.HUMAN_SOVEREIGN
    assert max(AuthorityLevel.AGENT_DELEGATED, AuthorityLevel.HUMAN_APPROVAL) == AuthorityLevel.HUMAN_APPROVAL


def test_levels_three_and_four_require_a_human() -> None:
    assert not AuthorityLevel.AGENT_AUTONOMOUS.requires_human
    assert not AuthorityLevel.AGENT_DELEGATED.requires_human
    assert AuthorityLevel.HUMAN_APPROVAL.requires_human
    assert AuthorityLevel.HUMAN_SOVEREIGN.requires_human
    assert AuthorityLevel.HUMAN_SOVEREIGN.is_human_only
    assert not AuthorityLevel.HUMAN_APPROVAL.is_human_only


@pytest.mark.parametrize(
    ("level", "minimum"),
    [
        (AuthorityLevel.AGENT_AUTONOMOUS, 0.60),
        (AuthorityLevel.AGENT_DELEGATED, 0.70),
        (AuthorityLevel.HUMAN_APPROVAL, 0.80),
        (AuthorityLevel.HUMAN_SOVEREIGN, 0.90),
    ],
)
def test_confidence_floors_of_11_9_2(level: AuthorityLevel, minimum: float) -> None:
    assert MIN_CONFIDENCE_BY_LEVEL[level] == minimum


def test_a_matching_actor_at_sufficient_confidence_is_permitted() -> None:
    verdict = resolve(AuthorityLevel.AGENT_DELEGATED, AuthorityLevel.AGENT_DELEGATED, confidence=0.75)
    assert verdict.permitted
    assert verdict.required_level == AuthorityLevel.AGENT_DELEGATED


def test_insufficient_confidence_blocks_even_a_sufficient_actor() -> None:
    verdict = resolve(AuthorityLevel.AGENT_DELEGATED, AuthorityLevel.HUMAN_SOVEREIGN, confidence=0.65)
    assert verdict.outcome == Outcome.INSUFFICIENT_CONFIDENCE
    assert not verdict.permitted


def test_an_underpowered_actor_escalates() -> None:
    verdict = resolve(AuthorityLevel.HUMAN_APPROVAL, AuthorityLevel.AGENT_DELEGATED, confidence=0.85)
    assert verdict.outcome == Outcome.ESCALATE
    assert verdict.needs_human


def test_high_risk_escalates_a_class_b_decision_to_level_three() -> None:
    """11.14.3 — a Class B decision at High risk is treated as Class C."""
    verdict = resolve(
        AuthorityLevel.AGENT_DELEGATED, AuthorityLevel.AGENT_DELEGATED, confidence=0.95, risk=RiskClass.HIGH
    )
    assert verdict.required_level == AuthorityLevel.HUMAN_APPROVAL
    assert verdict.outcome == Outcome.ESCALATE


def test_existential_risk_escalates_to_level_four() -> None:
    verdict = resolve(
        AuthorityLevel.HUMAN_APPROVAL,
        AuthorityLevel.HUMAN_APPROVAL,
        confidence=0.99,
        risk=RiskClass.EXISTENTIAL,
    )
    assert verdict.required_level == AuthorityLevel.HUMAN_SOVEREIGN
    assert verdict.outcome == Outcome.ESCALATE


def test_risk_can_only_raise_the_bar() -> None:
    """Low risk never lowers a class-derived requirement."""
    verdict = resolve(
        AuthorityLevel.HUMAN_SOVEREIGN, AuthorityLevel.HUMAN_SOVEREIGN, confidence=0.95, risk=RiskClass.LOW
    )
    assert verdict.required_level == AuthorityLevel.HUMAN_SOVEREIGN


def test_escalated_requirements_raise_the_confidence_floor_too() -> None:
    """A proposal escalated to Level 3 must clear 0.80, not Level 2's 0.70."""
    verdict = resolve(
        AuthorityLevel.AGENT_DELEGATED, AuthorityLevel.HUMAN_SOVEREIGN, confidence=0.75, risk=RiskClass.HIGH
    )
    assert verdict.minimum_confidence == 0.80
    assert verdict.outcome == Outcome.INSUFFICIENT_CONFIDENCE


def test_contradictory_evidence_escalates_regardless_of_confidence() -> None:
    """11.9.2 / 11 rule 8 — a contradiction is not outrun by a high score."""
    verdict = resolve(
        AuthorityLevel.AGENT_AUTONOMOUS,
        AuthorityLevel.HUMAN_SOVEREIGN,
        confidence=1.0,
        evidence_contradictory=True,
    )
    assert verdict.outcome == Outcome.ESCALATE
    assert verdict.needs_human


def test_confidence_outside_the_unit_interval_is_refused() -> None:
    with pytest.raises(ValueError):
        resolve(AuthorityLevel.AGENT_AUTONOMOUS, AuthorityLevel.AGENT_AUTONOMOUS, confidence=1.5)


# ---------------------------------------------------------- confidence derivation


def test_derived_confidence_is_capped_by_the_weakest_evidence() -> None:
    derived = derive_confidence((0.95, 0.55, 0.9), option_quality=1.0, risk=RiskClass.LOW)
    assert derived <= 0.55


def test_higher_risk_lowers_derived_confidence() -> None:
    low = derive_confidence((0.9, 0.9), option_quality=0.9, risk=RiskClass.LOW)
    existential = derive_confidence((0.9, 0.9), option_quality=0.9, risk=RiskClass.EXISTENTIAL)
    assert existential < low


def test_no_evidence_derives_no_confidence() -> None:
    assert derive_confidence((), option_quality=1.0, risk=RiskClass.LOW) == 0.0


def test_derivation_refuses_out_of_range_inputs() -> None:
    with pytest.raises(ValueError):
        derive_confidence((0.9,), option_quality=2.0, risk=RiskClass.LOW)


# ----------------------------------------------------------------- escalation


def _channel(sink=None, human: str = "human-1") -> EscalationChannel:
    return EscalationChannel(subsystem="decision_gateway", is_human=lambda p: p == human, sink=sink)


def test_an_incident_carries_the_fixed_response_set_of_14_33_3() -> None:
    channel = _channel()
    incident = channel.raise_incident(
        EscalationTrigger.NON_VIOLABLE_RULE_VIOLATION, "agent-1", "tenant-a", "attempted self-approval"
    )
    assert "alert_human_sovereign" in Category1Incident.RESPONSES
    assert "preserve_evidence" in Category1Incident.RESPONSES
    assert incident.incident_id.startswith("cat1-decision_gateway-")


def test_evidence_is_frozen_at_the_moment_of_raising(monkeypatch: pytest.MonkeyPatch) -> None:
    channel = _channel()
    mutable = {"state": "before"}
    incident = channel.raise_incident(
        EscalationTrigger.AUTHORITY_BYPASS, "agent-1", "tenant-a", "bypass", evidence=mutable
    )
    mutable["state"] = "after"
    assert incident.evidence["state"] == "before"


def test_an_incident_is_retained_even_with_no_sink_attached() -> None:
    channel = _channel()
    channel.raise_incident(EscalationTrigger.SILENT_FAILURE, "agent-1", "tenant-a", "silent failure")
    assert len(channel.unacknowledged()) == 1
    assert channel.raised == 1


def test_a_broken_sink_does_not_swallow_the_incident() -> None:
    def explode(_incident: Category1Incident) -> None:
        raise RuntimeError("alerting is down")

    channel = _channel(sink=explode)
    channel.raise_incident(EscalationTrigger.OVERSIGHT_LOSS, "agent-1", "tenant-a", "blind")
    assert channel.sink_failures == 1
    assert len(channel.unacknowledged()) == 1


def test_the_sink_receives_the_incident() -> None:
    received: list[Category1Incident] = []
    channel = _channel(sink=received.append)
    channel.raise_incident(EscalationTrigger.ISOLATION_BREACH, "agent-1", "tenant-a", "cross-tenant read")
    assert len(received) == 1
    assert received[0].trigger == EscalationTrigger.ISOLATION_BREACH


def test_no_appeal_is_possible_at_the_agent_level() -> None:
    """14.33.3 — an agent cannot mark its own Category 1 incident handled."""
    channel = _channel()
    incident = channel.raise_incident(EscalationTrigger.JOURNAL_TAMPERING, "agent-1", "tenant-a", "attempted edit")
    with pytest.raises(NoAppealError):
        channel.acknowledge(incident.incident_id, acknowledged_by="agent-1")
    acknowledged = channel.acknowledge(incident.incident_id, acknowledged_by="human-1")
    assert acknowledged.is_acknowledged
    assert acknowledged.acknowledged_by == "human-1"
    assert channel.unacknowledged() == []


def test_acknowledging_an_unknown_incident_raises() -> None:
    channel = _channel()
    with pytest.raises(KeyError):
        channel.acknowledge("cat1-nope-000001", acknowledged_by="human-1")


def test_acknowledgement_preserves_the_original_facts() -> None:
    channel = _channel()
    incident = channel.raise_incident(
        EscalationTrigger.AUTHORITY_BYPASS, "agent-1", "tenant-a", "bypass", evidence={"k": "v"}
    )
    acknowledged = channel.acknowledge(incident.incident_id, acknowledged_by="human-1")
    assert acknowledged.raised_at == incident.raised_at
    assert acknowledged.evidence == incident.evidence
    assert acknowledged.summary == incident.summary
