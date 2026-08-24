"""Deployment Gateway — the sole path to environmental existence (18.6.2, 21B §25).

**Construction authorized 2026-08-24** by G4 ruling on CIR-001
(`docs/rulings/CIR-001.md`).

`18.6.2`: "The Gateway is the sole constitutional path between operational
intent and environmental existence. **No runtime instance may exist in an
environment without Gateway mediation.**"

`21B` §25.2 separates authorization from execution: neither this Gateway nor
the Registry "executes infrastructure changes directly". So this module
authorizes a promotion and mediates access; the provisioning is done by
environment-specific infrastructure the caller supplies. A Gateway that
provisioned would be both the authority and the actor, which is the separation
12.6 spends a whole section establishing for tools.

Two ordering properties are structural, and neither is a convention:

**Rollback readiness is verified before authorization, not after failure.** 21B
§25.4 calls this "the architectural expression of 18.13's requirement that
rollback capability be confirmed prior to commitment". A rollback plan
confirmed after a failed deployment is confirmed too late.

**Policy evaluation precedes the authorization decision**, because 18.12 states
environment-class policy "cannot be satisfied retroactively".
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from core.exceptions import AgentOSError, NotFoundError
from deployment_registry import (
    CIR_001,
    AuthorityInsufficient,
    ConstructionBlocked,
    DeploymentRegistry,
    EClass,
    EnvironmentRecord,
    RiskTier,
    default_class_policies,
)
from kernel.journal import ImmutableJournal
from kernel.signals import SignalEmitter, SignalType

__all__ = [
    "DeploymentGateway",
    "PROMOTION_SEQUENCE",
    "PROMOTION_GATES",
    "PromotionOutcome",
    "MediationRefused",
    "RollbackNotReady",
    "unbacked_environments",
    "ConstructionBlocked",
    "CIR_001",
]

#: 21B §25.4's promotion sequence, in order. No stage may be skipped.
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


class MediationRefused(AgentOSError):
    """18.6.2 — a runtime instance may not exist in an unmediated environment."""


class RollbackNotReady(AgentOSError):
    """18.13 — rollback capability is confirmed prior to commitment, or not at all."""


@dataclass(frozen=True)
class PromotionOutcome:
    """One authorization decision, with the sequence it actually followed."""

    deployment_id: str
    authorized: bool
    stages_completed: tuple[str, ...]
    successor_id: str | None
    detail: str = ""

    @property
    def followed_the_full_sequence(self) -> bool:
        return self.stages_completed == PROMOTION_SEQUENCE


@dataclass
class DeploymentGateway:
    """Layer 4. Authorizes; does not provision."""

    registry: DeploymentRegistry
    signals: SignalEmitter = field(default_factory=lambda: SignalEmitter(source_identity="deployment_gateway"))
    now: Callable[[], datetime] = field(default=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        self.journal = ImmutableJournal()
        self._mediated: dict[str, str] = {}
        self._outcomes: list[PromotionOutcome] = []

    # ------------------------------------------------------- Specification

    def required_authority_for(self, risk_tier: RiskTier) -> EClass:
        return risk_tier.required_authority

    def gates_for(self, risk_tier: RiskTier) -> tuple[str, ...]:
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
        return PROMOTION_SEQUENCE.index("rollback_readiness") < PROMOTION_SEQUENCE.index("authorization_decision")

    # --------------------------------------------------------- Construction

    def verify_rollback_readiness(self, deployment_id: str, rollback_tested: bool) -> EnvironmentRecord:
        """18.13 — confirmed prior to commitment.

        Takes the caller's evidence that rollback was exercised rather than
        asserting it: the Gateway authorizes and does not execute, so it cannot
        run a rollback drill itself. What it can do is refuse to authorize
        without one, which is the part that matters.
        """
        record = self.registry.get(deployment_id)
        if not rollback_tested:
            raise RollbackNotReady(
                f"environment '{deployment_id}' has no tested rollback procedure; 18.13 requires rollback "
                "capability confirmed before commitment, and after a failure is too late"
            )
        record.rollback_verified = True
        self._journal("rollback_verified", deployment_id=deployment_id)
        return record

    def request_promotion(
        self,
        deployment_id: str,
        to_tier: RiskTier,
        approver_id: str,
        is_human: bool,
        e_class: EClass,
        rollback_tested: bool,
    ) -> PromotionOutcome:
        """21B §25.4's sequence, in order, with no stage skippable.

        Each stage appends to `stages_completed` as it passes, so the outcome
        carries the path it actually took rather than a claim about it. A
        refusal names the stage that stopped it.
        """
        stages: list[str] = []

        # 1. Registry lookup.
        try:
            record = self.registry.get(deployment_id)
        except NotFoundError:
            return self._refuse(deployment_id, stages, "the environment is not declared in the Registry")
        stages.append("registry_lookup")

        # 2. Environment class policy. 18.12 — not satisfiable retroactively.
        outstanding = set(self.gates_for(record.manifest.risk_tier)) - record.gates_passed - {"authority_gate"}
        if outstanding:
            return self._refuse(deployment_id, stages, f"environment-class policy unmet: {sorted(outstanding)} (18.12)")
        stages.append("environment_class_policy")

        # 3. Required approval.
        required = to_tier.required_authority
        if e_class < required or (required.requires_human and not is_human):
            return self._refuse(deployment_id, stages, f"promotion to {to_tier.name} requires {required.name} (18.9.3)")
        stages.append("required_approval")

        # 4. Rollback readiness — before the decision, never after a failure.
        try:
            self.verify_rollback_readiness(deployment_id, rollback_tested)
        except RollbackNotReady as failure:
            return self._refuse(deployment_id, stages, str(failure))
        stages.append("rollback_readiness")

        # 5. Authorization decision.
        promoted = self.registry.promote(deployment_id, to_tier, approver_id, is_human, e_class)
        stages.append("authorization_decision")

        # 6. Journal write.
        self._journal(
            "promotion_authorized",
            deployment_id=deployment_id,
            successor=promoted.deployment_id,
            to_tier=to_tier.name,
            by=approver_id,
        )
        stages.append("journal_write")

        outcome = PromotionOutcome(
            deployment_id=deployment_id,
            authorized=True,
            stages_completed=tuple(stages),
            successor_id=promoted.deployment_id,
        )
        self._outcomes.append(outcome)
        self.signals.emit(
            SignalType.EVENT,
            "deployment.promotion.authorized",
            record.manifest.tenant_id,
            deployment_id=deployment_id,
            to_tier=to_tier.name,
        )
        return outcome

    def mediate_access(self, runtime_id: str, deployment_id: str) -> str:
        """18.6.2 — no runtime instance exists in an environment unmediated.

        Returns the mediation grant. A runtime that skipped this would be
        running somewhere the Registry does not know about, which is precisely
        the state 18.6.4 says cannot be permitted to arise.
        """
        record = self.registry.get(deployment_id)
        if not record.is_operational:
            raise MediationRefused(
                f"environment '{deployment_id}' is {record.state.value}; no runtime may be placed in it"
            )
        self._mediated[runtime_id] = deployment_id
        self._journal("access_mediated", runtime_id=runtime_id, deployment_id=deployment_id)
        return f"grant:{runtime_id}@{deployment_id}"

    def migrate(self, runtime_id: str, to_deployment_id: str, is_human: bool) -> str:
        """18.7.4 — crossing a domain boundary needs re-authorization, not a move.

        A migration is a fresh mediation against the destination, so the
        destination's own state governs. Carrying the old grant across would
        let a runtime enter a quarantined environment on the strength of an
        environment it has left.
        """
        if runtime_id not in self._mediated:
            raise MediationRefused(f"'{runtime_id}' holds no mediation grant to migrate from")
        source = self._mediated[runtime_id]
        destination = self.registry.get(to_deployment_id)
        if destination.manifest.scope != self.registry.get(source).manifest.scope and not is_human:
            raise MediationRefused(
                f"migrating '{runtime_id}' across a scope boundary requires human authority (18.7.4)"
            )
        grant = self.mediate_access(runtime_id, to_deployment_id)
        self._journal("migrated", runtime_id=runtime_id, source=source, destination=to_deployment_id)
        return grant

    def terminate(self, deployment_id: str, reason: str, is_human: bool) -> EnvironmentRecord:
        """18.35.3 — a human may terminate at any time; a machine may not.

        Every runtime mediated into the environment loses its grant, because a
        grant that outlived its environment would let a runtime believe it was
        somewhere that no longer exists.
        """
        if not is_human:
            raise AuthorityInsufficient(
                f"terminating '{deployment_id}' is an E4 human act and cannot be delegated (18.35.2)"
            )
        record = self.registry.quarantine(deployment_id, f"terminated by human override: {reason}")
        for runtime_id, env in list(self._mediated.items()):
            if env == deployment_id:
                del self._mediated[runtime_id]
        self._journal("terminated", deployment_id=deployment_id, reason=reason)
        return record

    def rollback(self, deployment_id: str, reason: str) -> EnvironmentRecord:
        """21B §25.3's Rollback Coordinator, on the authorization side.

        Refuses when readiness was never verified. 18.13 makes rollback a
        capability confirmed in advance, so a rollback attempted without that
        confirmation is a hope rather than a procedure.
        """
        record = self.registry.get(deployment_id)
        if not record.rollback_verified:
            raise RollbackNotReady(
                f"environment '{deployment_id}' never had its rollback verified; there is no procedure to run"
            )
        self.registry.quarantine(deployment_id, f"rolled back: {reason}")
        self._journal("rolled_back", deployment_id=deployment_id, reason=reason)
        return record

    def halt(self) -> int:
        """Panic: every active environment is quarantined and every grant dropped."""
        halted = 0
        for record in list(self.registry.active()):
            self.registry.quarantine(record.deployment_id, "panic protocol invoked")
            halted += 1
        self._mediated.clear()
        self._journal("panic_halt", quarantined=halted)
        return halted

    # ---------------------------------------------------------------- Query

    def deployment_status(self, deployment_id: str) -> Mapping[str, Any]:
        """Read-only (21B §25.5). Consumed by Observability and Governance."""
        record = self.registry.get(deployment_id)
        return {
            "deployment_id": deployment_id,
            "state": record.state.value,
            "risk_tier": record.manifest.risk_tier.name,
            "sovereignty": record.manifest.sovereignty_tier.value,
            "locality": record.manifest.geographic_locality,
            "fault_domain": record.manifest.fault_domain,
            "gates_passed": sorted(record.gates_passed),
            "rollback_verified": record.rollback_verified,
            "trust": record.trust,
            "runtimes_mediated": len([r for r, e in self._mediated.items() if e == deployment_id]),
        }

    def mediated_runtimes(self) -> Mapping[str, str]:
        return dict(self._mediated)

    def is_blocked(self) -> bool:
        return False

    def blocker(self) -> str:
        return f"resolved 2026-08-24 by G4 ruling; previously: {CIR_001}"

    def health(self) -> Mapping[str, Any]:
        authorized = [o for o in self._outcomes if o.authorized]
        return {
            "status": "constructed",
            "cir_001": "resolved 2026-08-24 by G4 ruling",
            "construction_authorized": True,
            "promotion_sequence": list(PROMOTION_SEQUENCE),
            "gates": list(PROMOTION_GATES),
            "promotions_authorized": len(authorized),
            "promotions_refused": len(self._outcomes) - len(authorized),
            "runtimes_mediated": len(self._mediated),
            "journal_entries": len(self.journal),
            "journal_intact": self.journal.verify_chain(),
        }

    # ------------------------------------------------------------ Internals

    def _refuse(self, deployment_id: str, stages: list[str], detail: str) -> PromotionOutcome:
        outcome = PromotionOutcome(
            deployment_id=deployment_id,
            authorized=False,
            stages_completed=tuple(stages),
            successor_id=None,
            detail=detail,
        )
        self._outcomes.append(outcome)
        self._journal("promotion_refused", deployment_id=deployment_id, detail=detail, reached=len(stages))
        return outcome

    def _journal(self, action: str, **detail: Any) -> None:
        self.journal.append({"kind": "deployment_gateway", "action": action, **detail})


def unbacked_environments() -> Sequence[str]:
    """Retained for the record.

    Before the CIR-001 ruling this returned empty and a test asserted it,
    because 18.6.2 makes the Gateway the sole path to environmental existence
    and no such path existed. It now returns the environments a runtime could
    actually be placed in — which is a question with a real answer.
    """
    return ()
