"""Deployment Registry — governs which environments exist (18.6.1, per 21B §25).

**Construction authorized 2026-08-24** by G4 ruling on CIR-001
(`docs/rulings/CIR-001.md`). Before that ruling every verb here raised, for the
reason 18.2 makes plain: deployment is "the last constitutional checkpoint
before code becomes behavior", so building it on a guessed answer would have
placed every other guarantee in the system onto a substrate chosen by
inference.

`18.6.1`: "The Deployment Registry is the sole authoritative source of truth
for all operational environments... **It does not execute deployments; it
governs their existence and validity.**"

That last sentence is the module's shape. There is no verb here that
provisions, scales, or terminates infrastructure — 21B §25.2 separates
authorization from execution, and execution belongs to environment-specific
infrastructure outside this scope. The Registry decides what may exist;
something else makes it exist.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from core.exceptions import AgentOSError, NotFoundError, ValidationError
from deployment_registry.manifests import (
    CIR_001,
    DEPLOYMENT_TRANSITIONS,
    DeploymentState,
    EClass,
    EnvironmentManifest,
    RiskTier,
    default_class_policies,
    promotion_authority,
    validate_manifest,
)
from kernel.journal import ImmutableJournal
from kernel.lifecycle import LifecycleStateMachine

#: [Engineering Decision] 18.6.1 has the Registry hold trust scores and names no
#: starting value or decay. An environment is trusted until it fails, matching
#: the Tool Registry and the Integration Registry, which face the same question.
INITIAL_TRUST = 1.0
TRUST_SUSPENSION_FLOOR = 0.5


class AuthorityInsufficient(AgentOSError):
    """18.5.3 — the offered E-class does not meet what the tier requires."""


class GateNotPassed(AgentOSError):
    """18.12 — environment-class policy "cannot be satisfied retroactively"."""


@dataclass
class EnvironmentRecord:
    """Lifecycle state and accumulated behaviour for one environment."""

    manifest: EnvironmentManifest
    state: DeploymentState = DeploymentState.DECLARED
    gates_passed: set[str] = field(default_factory=set)
    approved_by: str | None = None
    approval_class: EClass | None = None
    activated_at: datetime | None = None
    quarantine_reason: str = ""
    successor_id: str | None = None
    incidents: int = 0
    observations: int = 0
    rollback_verified: bool = False

    @property
    def deployment_id(self) -> str:
        return self.manifest.deployment_id

    @property
    def trust(self) -> float:
        if self.observations == 0:
            return INITIAL_TRUST
        return round(max(0.0, 1.0 - self.incidents / self.observations), 4)

    @property
    def is_operational(self) -> bool:
        return self.state == DeploymentState.ACTIVE


@dataclass
class DeploymentRegistry:
    """Governs environmental existence and validity. Executes nothing."""

    now: Callable[[], datetime] = field(default=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        self.journal = ImmutableJournal()
        self._records: dict[str, EnvironmentRecord] = {}

    # ---------------------------------------------------- Specification

    def validate(self, manifest: EnvironmentManifest) -> None:
        """Schema conformance. Creates nothing, and is still worth doing first."""
        validate_manifest(manifest)

    def class_policy(self, risk_tier: RiskTier) -> Any:
        return default_class_policies()[risk_tier]

    # ----------------------------------------------------- Construction

    def declare(self, manifest: EnvironmentManifest, actor_id: str) -> EnvironmentRecord:
        """An environment enters the Registry (18.6.1).

        Declaration is not validation, validation is not approval, and approval
        is not activation. Four gates, and 18.12 forbids satisfying any of them
        after the fact.
        """
        if not actor_id:
            raise ValidationError("declaring an environment requires an actor; anonymous declaration is prohibited")
        if manifest.deployment_id in self._records:
            raise AgentOSError(f"environment '{manifest.deployment_id}' is already declared")
        if manifest.predecessor_deployment_id is not None:
            if manifest.predecessor_deployment_id not in self._records:
                raise NotFoundError(
                    f"predecessor '{manifest.predecessor_deployment_id}' is not declared; lineage must resolve (18.8.3)"
                )
        validate_manifest(manifest)
        record = EnvironmentRecord(manifest=manifest, state=DeploymentState.DECLARED)
        self._records[manifest.deployment_id] = record
        self._record("declared", deployment_id=manifest.deployment_id, by=actor_id, tier=manifest.risk_tier.name)
        return record

    def pass_gate(self, deployment_id: str, gate: str) -> EnvironmentRecord:
        """18.9.2's gates, recorded as they are passed.

        Recorded here rather than asserted at approval time because 18.12 makes
        the ordering the point: a gate passed after authorization is a gate that
        did not gate anything.
        """
        record = self.get(deployment_id)
        required = set(self._required_gates(record))
        if gate not in required:
            raise ValidationError(
                f"'{gate}' is not a gate {record.manifest.risk_tier.name} requires; expected {sorted(required)}"
            )
        record.gates_passed.add(gate)
        if gate == "resilience_gate":
            record.rollback_verified = True
        self._record("gate_passed", deployment_id=deployment_id, gate=gate)
        return record

    def validate_environment(self, deployment_id: str) -> EnvironmentRecord:
        """The Validation Gate of 18.9.2, as a state transition."""
        record = self.get(deployment_id)
        self._transition(record, DeploymentState.VALIDATED)
        record.gates_passed.add("validation_gate")
        self._record("validated", deployment_id=deployment_id)
        return record

    def approve(self, deployment_id: str, approver_id: str, is_human: bool, e_class: EClass) -> EnvironmentRecord:
        """The Authority Gate (18.9.2, 18.5.3).

        E4 is human-only and cannot be delegated (18.35.2). E2 and above require
        a human-approved decision. Every gate the tier requires must already
        have been passed: 18.12's "cannot be satisfied retroactively" is
        enforced here, which is the only place it can be.
        """
        record = self.get(deployment_id)
        self._require(record, DeploymentState.VALIDATED)
        required = record.manifest.required_authority

        if e_class < required:
            raise AuthorityInsufficient(
                f"environment '{deployment_id}' is {record.manifest.risk_tier.name} and requires "
                f"{required.name}; {e_class.name} was offered (18.5.3)"
            )
        if required.is_human_only and not is_human:
            raise AuthorityInsufficient(
                "E4 authority is cryptographically bound to human credentials and cannot be delegated (18.35.2)"
            )
        if required.requires_human and not is_human:
            raise AuthorityInsufficient(f"{required.name} requires a human-approved decision (18.5.3)")

        outstanding = set(self._required_gates(record)) - record.gates_passed - {"authority_gate"}
        if outstanding:
            raise GateNotPassed(
                f"environment '{deployment_id}' has not passed {sorted(outstanding)}; environment-class "
                "policy cannot be satisfied retroactively (18.12)"
            )

        record.approved_by = approver_id
        record.approval_class = e_class
        record.gates_passed.add("authority_gate")
        self._transition(record, DeploymentState.APPROVED)
        self._record("approved", deployment_id=deployment_id, by=approver_id, e_class=e_class.name)
        return record

    def activate(self, deployment_id: str) -> EnvironmentRecord:
        """Approval precedes activation. The Registry marks it; it does not provision."""
        record = self.get(deployment_id)
        self._require(record, DeploymentState.APPROVED)
        self._transition(record, DeploymentState.ACTIVE)
        record.activated_at = self.now()
        self._record("activated", deployment_id=deployment_id)
        return record

    def promote(
        self, deployment_id: str, to_tier: RiskTier, approver_id: str, is_human: bool, e_class: EClass
    ) -> EnvironmentRecord:
        """18.9 — promotion is constitutional certification, not a pipeline step.

        A promotion produces a **new environment with its own lineage** rather
        than mutating the existing one, because 18.8.3 makes an Active
        environment's sovereignty tier, locality and scope immutable. Promoting
        in place would edit exactly those fields.
        """
        record = self.get(deployment_id)
        self._require(record, DeploymentState.ACTIVE)
        required = promotion_authority(record.manifest.risk_tier, to_tier)
        if e_class < required:
            raise AuthorityInsufficient(
                f"promotion to {to_tier.name} requires {required.name}; {e_class.name} was offered (18.9.3)"
            )
        if required.requires_human and not is_human:
            raise AuthorityInsufficient(f"{required.name} promotion requires a human (18.9.2 Authority Gate)")

        successor_id = f"{deployment_id}+{to_tier.name.lower()}"
        successor = EnvironmentManifest(
            **{
                **{f.name: getattr(record.manifest, f.name) for f in record.manifest.__dataclass_fields__.values()},
                "deployment_id": successor_id,
                "risk_tier": to_tier,
                "predecessor_deployment_id": deployment_id,
                "declared_at": self.now(),
            }
        )
        validate_manifest(successor)
        promoted = EnvironmentRecord(manifest=successor, state=DeploymentState.DECLARED)
        self._records[successor_id] = promoted
        record.successor_id = successor_id
        self._record(
            "promoted", deployment_id=deployment_id, successor=successor_id, to_tier=to_tier.name, by=approver_id
        )
        return promoted

    def record_observation(self, deployment_id: str, incident: bool = False) -> EnvironmentRecord:
        """Environmental behaviour, accumulated. Repeated incidents quarantine.

        The Registry scores; it does not probe. An environment that failed
        repeatedly stops being resolvable at the same moment it stops being
        trustworthy.
        """
        record = self.get(deployment_id)
        record.observations += 1
        if incident:
            record.incidents += 1
        sample_is_meaningful = record.observations >= 4
        if record.state == DeploymentState.ACTIVE and sample_is_meaningful and record.trust < TRUST_SUSPENSION_FLOOR:
            self.quarantine(deployment_id, f"trust {record.trust} fell below {TRUST_SUSPENSION_FLOOR}")
        return record

    def quarantine(self, deployment_id: str, reason: str) -> EnvironmentRecord:
        record = self.get(deployment_id)
        self._transition(record, DeploymentState.QUARANTINED)
        record.quarantine_reason = reason
        self._record("quarantined", deployment_id=deployment_id, reason=reason)
        return record

    def decommission(self, deployment_id: str, actor_id: str) -> EnvironmentRecord:
        record = self.get(deployment_id)
        self._transition(record, DeploymentState.DECOMMISSIONED)
        self._record("decommissioned", deployment_id=deployment_id, by=actor_id)
        return record

    # ---------------------------------------------------------------- Query

    def get(self, deployment_id: str) -> EnvironmentRecord:
        record = self._records.get(deployment_id)
        if record is None:
            raise NotFoundError(f"environment '{deployment_id}' is not declared")
        return record

    def discover(
        self,
        tenant_id: str,
        min_tier: RiskTier | None = None,
        locality: str | None = None,
        fault_domain: str | None = None,
    ) -> list[EnvironmentRecord]:
        """18.8.4 — structured discovery, ranked by trust.

        A runtime asks for the properties it needs and receives environments
        that have them. It does not name one, for the same reason a tool does
        not name a provider.
        """
        candidates = [
            r
            for r in self._records.values()
            if r.manifest.tenant_id == tenant_id
            and r.is_operational
            and (min_tier is None or r.manifest.risk_tier >= min_tier)
            and (locality is None or r.manifest.geographic_locality == locality)
            and (fault_domain is None or r.manifest.fault_domain == fault_domain)
        ]
        return sorted(candidates, key=lambda r: -r.trust)

    def active(self, tenant_id: str | None = None) -> list[EnvironmentRecord]:
        return [
            r
            for r in self._records.values()
            if r.is_operational and (tenant_id is None or r.manifest.tenant_id == tenant_id)
        ]

    def is_blocked(self) -> bool:
        """Retained so a caller that still asks receives the current answer."""
        return False

    def blocker(self) -> str:
        return f"resolved 2026-08-24 by G4 ruling; previously: {CIR_001}"

    def health(self) -> Mapping[str, Any]:
        records = list(self._records.values())
        by_state: dict[str, int] = {}
        for record in records:
            by_state[record.state.value] = by_state.get(record.state.value, 0) + 1
        return {
            "status": "constructed",
            "cir_001": "resolved 2026-08-24 by G4 ruling",
            "construction_authorized": True,
            "environments": len(records),
            "by_state": by_state,
            "active": len([r for r in records if r.is_operational]),
            "fault_domains": len({r.manifest.fault_domain for r in records}),
            "localities": len({r.manifest.geographic_locality for r in records}),
            "mean_trust": (round(sum(r.trust for r in records) / len(records), 4) if records else 0.0),
            "journal_entries": len(self.journal),
            "journal_intact": self.journal.verify_chain(),
        }

    # ------------------------------------------------------------ Internals

    def _required_gates(self, record: EnvironmentRecord) -> tuple[str, ...]:
        policy = default_class_policies()[record.manifest.risk_tier]
        gates = ["validation_gate"] if policy.requires_validation_gate else []
        if policy.requires_compliance_gate:
            gates.append("compliance_gate")
        if policy.requires_resilience_gate:
            gates.append("resilience_gate")
        gates.append("authority_gate")
        return tuple(gates)

    def _require(self, record: EnvironmentRecord, *allowed: DeploymentState) -> None:
        if record.state not in allowed:
            raise AgentOSError(
                f"environment '{record.deployment_id}' is {record.state.value}; expected one of "
                f"{[s.value for s in allowed]}"
            )

    def _transition(self, record: EnvironmentRecord, target: DeploymentState) -> None:
        machine = LifecycleStateMachine(transitions=dict(DEPLOYMENT_TRANSITIONS), state=record.state)
        machine.transition(target)
        record.state = target

    def _record(self, action: str, **detail: Any) -> None:
        self.journal.append({"kind": "deployment", "action": action, **detail})
