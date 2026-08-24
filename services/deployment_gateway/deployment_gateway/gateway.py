"""Deployment Gateway — construction blocked by CIR-001 (21B §25).

`18.6.2`: "The Deployment Gateway is the unified access layer through which all
environmental relationships are established, validated, monitored, and
terminated... The Gateway is the sole constitutional path between operational
intent and environmental existence."

`21B` §25.2 separates authorization from execution: neither component "executes
infrastructure changes directly", with execution delegated to
environment-specific infrastructure outside the specified scope — the part
CIR-001 blocks.

What is specified and testable here:

**The promotion sequence, and that no stage may be skipped.** 21B §25.4 gives
the order: Registry lookup, Environment Class Policy evaluation, required-
approval check, Rollback Coordinator readiness verification, authorization
decision, Journal write. `18.12` states environment-class policy "cannot be
satisfied retroactively", so the ordering is a property rather than a
convention.

**Rollback readiness is verified before authorization, not after failure.**
21B §25.4 calls this "the architectural expression of 18.13's requirement that
rollback capability be confirmed prior to commitment", mirroring the Decision
Gateway's Compensation Verifier. A rollback plan confirmed after a failed
deployment is a rollback plan confirmed too late.

**Policy Store unavailability fails closed.** 21B §25.9: "no default-permit
path".

Every verb that would authorize a promotion, mediate access, or terminate an
environmental relationship raises `ConstructionBlocked`.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, NoReturn

from deployment_registry import (
    CIR_001,
    EClass,
    EnvironmentManifest,
    RiskTier,
    blocked,
    default_class_policies,
)

#: 21B §25.4's promotion sequence, in order. Named so a test can assert the
#: module states the sequence the architecture requires, and so the ordering
#: survives as a reviewable artifact while construction is blocked.
PROMOTION_SEQUENCE: tuple[str, ...] = (
    "registry_lookup",
    "environment_class_policy",
    "required_approval",
    "rollback_readiness",
    "authorization_decision",
    "journal_write",
)

#: 18.9.2's gates, in the order 18.9.2 lists them.
PROMOTION_GATES: tuple[str, ...] = (
    "validation_gate",
    "compliance_gate",
    "resilience_gate",
    "authority_gate",
)


@dataclass
class DeploymentGateway:
    """Specification-conformant, construction-blocked.

    A distinct status from Done, and not a step toward it.
    """

    # ------------------------------------------------- Specification (open)

    def required_authority_for(self, risk_tier: RiskTier) -> EClass:
        """18.5.3's mapping. Answering a question creates nothing."""
        return risk_tier.required_authority

    def gates_for(self, risk_tier: RiskTier) -> tuple[str, ...]:
        """Which of 18.9.2's gates a given risk tier must pass."""
        policy = default_class_policies()[risk_tier]
        gates = ["validation_gate"] if policy.requires_validation_gate else []
        if policy.requires_compliance_gate:
            gates.append("compliance_gate")
        if policy.requires_resilience_gate:
            gates.append("resilience_gate")
        gates.append("authority_gate")
        return tuple(gates)

    def promotion_sequence(self) -> tuple[str, ...]:
        return PROMOTION_SEQUENCE

    def rollback_precedes_authorization(self) -> bool:
        """18.13 as a checkable property of the declared sequence."""
        return PROMOTION_SEQUENCE.index("rollback_readiness") < PROMOTION_SEQUENCE.index("authorization_decision")

    def would_be_permitted(self, manifest: EnvironmentManifest) -> NoReturn:
        """Deliberately blocked despite sounding like a query.

        Answering "would this be permitted" requires evaluating policy the
        Governance ruling has not yet settled. A hypothetical answer that later
        proved wrong would be worse than no answer, because a caller would have
        planned against it.
        """
        blocked("would_be_permitted")

    def is_blocked(self) -> bool:
        return True

    def blocker(self) -> str:
        return CIR_001

    # ------------------------------------------------ Construction (blocked)

    def request_promotion(self, *_args: Any, **_kwargs: Any) -> NoReturn:
        blocked("request_promotion")

    def authorize(self, *_args: Any, **_kwargs: Any) -> NoReturn:
        blocked("authorize")

    def mediate_access(self, *_args: Any, **_kwargs: Any) -> NoReturn:
        blocked("mediate_access")

    def verify_rollback_readiness(self, *_args: Any, **_kwargs: Any) -> NoReturn:
        blocked("verify_rollback_readiness")

    def rollback(self, *_args: Any, **_kwargs: Any) -> NoReturn:
        blocked("rollback")

    def migrate(self, *_args: Any, **_kwargs: Any) -> NoReturn:
        blocked("migrate")

    def terminate(self, *_args: Any, **_kwargs: Any) -> NoReturn:
        blocked("terminate")

    def probe_health(self, *_args: Any, **_kwargs: Any) -> NoReturn:
        blocked("probe_health")

    def bootstrap(self, *_args: Any, **_kwargs: Any) -> NoReturn:
        blocked("bootstrap")

    def deployment_status(self, *_args: Any, **_kwargs: Any) -> NoReturn:
        blocked("deployment_status")

    def health(self) -> Mapping[str, Any]:
        """Reports the block. Deliberately available: a health surface that
        raised would make the blocked status itself unobservable."""
        return {
            "status": "specification-conformant, construction-blocked",
            "blocker": "CIR-001",
            "promotion_sequence": list(PROMOTION_SEQUENCE),
            "gates": list(PROMOTION_GATES),
            "construction_authorized": False,
            "resolution_required_at": "G3 or G4 Governance ruling",
        }


def unbacked_environments() -> Sequence[str]:
    """What the Runtime would receive if it asked for an environment today.

    Nothing. 18.6.2 makes the Gateway "the sole constitutional path between
    operational intent and environmental existence", and while construction is
    blocked there is no such path — so every runtime instance in this system
    runs in no registered environment at all. Stated rather than papered over,
    because the downstream consequence is what makes the block real.
    """
    return ()
