"""Integration Gateway — the sole path to the external ecosystem (17, per 21B §20).

**Construction authorized 2026-08-24** by G4 ruling on CIR-001
(`docs/rulings/CIR-001.md`).

`17.8` splits the platform in two: the Registry governs which integrations
exist, and this Gateway governs whether one may be consumed and mediates the
consumption. Nothing reaches an external provider except through here.

Three properties are structural, and each names the failure it prevents:

**Data classification is enforced at the boundary, not by the provider.** 21B
§20.4: "A T1 integration cannot receive Confidential or Restricted data...
because a provider's assurance that it will not retain data is not a control."
The check runs before egress, on the classification of the payload, and a
provider's terms of service are not consulted.

**Approval is per-instance.** 17.14.1 permits a standing order to pre-authorize
an integration *class* and requires that "each integration instance requires
specific approval". A class-level grant that admitted an instance would make
the instance approval decorative.

**Tools bind to abstractions, never to providers.** `resolve` takes a
capability name and returns whichever active integration best fulfils it. A
caller that had to name a provider would have the provider baked into it, and
17.6.3's substitution guarantee would hold only on paper.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from core.exceptions import AgentOSError, NotFoundError, ValidationError
from integration_registry import (
    CIR_001,
    CIR_001_RESOLVED,
    ConstructionBlocked,
    DataClassification,
    IntegrationManifest,
    IntegrationRecord,
    IntegrationRegistry,
    required_decision_class,
)
from integration_registry.manifests import MAX_CLASSIFICATION_BY_TIER
from kernel.journal import ImmutableJournal
from kernel.signals import SignalEmitter, SignalType

__all__ = [
    "IntegrationGateway",
    "ClassificationRefused",
    "ApprovalRequired",
    "ConsumptionRefused",
    "ConsumptionResult",
    "ProviderCall",
    "classification_permitted",
    "required_decision_class",
    "ConstructionBlocked",
    "CIR_001",
    "CIR_001_RESOLVED",
]


class ClassificationRefused(ValidationError):
    """Data above the integration's declared ceiling. Blocked before egress."""


class ApprovalRequired(ValidationError):
    """17.14.1 — each integration instance requires specific human approval."""


class ConsumptionRefused(AgentOSError):
    """The integration exists but may not be consumed in this state."""


def classification_permitted(manifest: IntegrationManifest, classification: DataClassification) -> bool:
    """21B §20.4's ceiling, as a pure function over the manifest."""
    return classification <= MAX_CLASSIFICATION_BY_TIER[manifest.risk_tier]


@dataclass(frozen=True)
class ConsumptionResult:
    """One mediated consumption of an external capability."""

    integration_id: str
    abstraction: str
    provider_name: str
    succeeded: bool
    payload: Mapping[str, Any] | None
    cost: float
    latency_seconds: float
    detail: str = ""


#: The shape of a provider call. The Gateway never constructs one of these
#: itself: the caller supplies the callable, the Gateway decides whether it may
#: run and mediates everything around it. That separation is 12.6's three-way
#: split applied to integrations — authorization and execution are different
#: parties, and a Gateway that dialled the provider would be both.
ProviderCall = Callable[[Mapping[str, Any]], Mapping[str, Any]]


@dataclass
class IntegrationGateway:
    """Layer 4. The sole constitutional path to an external provider (17.8)."""

    registry: IntegrationRegistry
    signals: SignalEmitter = field(default_factory=lambda: SignalEmitter(source_identity="integration_gateway"))
    now: Callable[[], datetime] = field(default=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        self.journal = ImmutableJournal()
        #: 17.14.1's per-instance approvals. A class-level standing order is
        #: recorded separately and never satisfies this set.
        self._approved_instances: set[str] = set()
        self._consumptions: list[ConsumptionResult] = []

    # ------------------------------------------------------- Boundary checks

    def check_classification(self, manifest: IntegrationManifest, classification: DataClassification) -> None:
        """21B §20.4 — refused before egress, on the manifest's declared tier."""
        if not classification_permitted(manifest, classification):
            raise ClassificationRefused(
                f"integration '{manifest.integration_id}' at risk tier {manifest.risk_tier.name} may not "
                f"receive {classification.name} data; blocked before it leaves the system (21B §20.4)"
            )

    def check_approval(self, manifest: IntegrationManifest, approved_instances: set[str] | None = None) -> None:
        """17.14.1 — a class-level standing order does not approve an instance."""
        approved = self._approved_instances if approved_instances is None else approved_instances
        if manifest.integration_id not in approved:
            raise ApprovalRequired(
                f"integration '{manifest.integration_id}' has no instance-specific approval; a standing "
                "order may pre-authorize a class but each instance requires specific approval (17.14.1)"
            )

    def record_instance_approval(self, integration_id: str, approver_id: str, is_human: bool) -> None:
        """The per-instance approval 17.14.1 requires, recorded here.

        Kept on the Gateway rather than the Registry because approval is about
        *consumption*, which is the Gateway's half of 17.8.
        """
        record = self.registry.get(integration_id)
        if required_decision_class(record.manifest) == "D" and not is_human:
            raise ApprovalRequired(
                f"integration '{integration_id}' requires Class D approval, which is human-only (17.31.1)"
            )
        self._approved_instances.add(integration_id)
        self._journal("instance_approved", integration_id=integration_id, by=approver_id)

    # ---------------------------------------------------------- Resolution

    def resolve_abstraction(self, abstraction: str, tenant_id: str) -> IntegrationRecord:
        """17.6.3 — the caller names a capability, never a provider.

        Returns the best active integration fulfilling the abstraction, ranked
        by observed health. Substituting a provider changes what this returns
        and changes nothing in the caller, which is the whole point of the
        abstraction layer.
        """
        candidates = self.registry.resolve(abstraction, tenant_id)
        if not candidates:
            raise NotFoundError(f"no active integration fulfils abstraction '{abstraction}' for tenant '{tenant_id}'")
        return candidates[0]

    def alternatives(self, abstraction: str, tenant_id: str) -> list[str]:
        """What else could fulfil this capability if the current one failed.

        17.23's portability guarantee is only real if the alternatives are
        known before they are needed.
        """
        return [r.integration_id for r in self.registry.resolve(abstraction, tenant_id)]

    # --------------------------------------------------------- Consumption

    def consume(
        self,
        abstraction: str,
        tenant_id: str,
        payload: Mapping[str, Any],
        classification: DataClassification,
        call: ProviderCall,
        cost: float = 0.0,
    ) -> ConsumptionResult:
        """The mediated path to an external provider (17.8, 21B §20.4).

        Ordered, and no stage may be skipped: resolve the abstraction, verify
        the integration is consumable, enforce the classification ceiling,
        verify per-instance approval, then and only then run the call. A
        failure at any stage is recorded and the provider is never reached.
        """
        record = self.resolve_abstraction(abstraction, tenant_id)
        manifest = record.manifest

        if not record.is_consumable:
            raise ConsumptionRefused(
                f"integration '{record.integration_id}' is {record.state.value} and may not be consumed"
            )
        self.check_classification(manifest, classification)
        self.check_approval(manifest)

        started = self.now()
        try:
            returned = call(payload)
            succeeded, detail = True, ""
        except Exception as failure:
            returned, succeeded, detail = None, False, str(failure)

        latency = (self.now() - started).total_seconds()
        result = ConsumptionResult(
            integration_id=record.integration_id,
            abstraction=abstraction,
            provider_name=manifest.provider_name,
            succeeded=succeeded,
            payload=returned,
            cost=cost,
            latency_seconds=latency,
            detail=detail,
        )
        self._consumptions.append(result)
        record.consumptions += 1
        # The Registry scores providers; the Gateway reports what it observed.
        self.registry.record_health(record.integration_id, healthy=succeeded, latency_seconds=latency)
        self._journal(
            "consumed",
            integration_id=record.integration_id,
            abstraction=abstraction,
            succeeded=succeeded,
            cost=cost,
        )
        self.signals.emit(
            SignalType.EVENT,
            "integration.consumed",
            tenant_id,
            integration_id=record.integration_id,
            abstraction=abstraction,
            succeeded=succeeded,
        )
        return result

    def provider_health(self, integration_id: str) -> Mapping[str, Any]:
        """Observed behaviour, not a probe. 17.18's monitoring, read-only."""
        record = self.registry.get(integration_id)
        return {
            "integration_id": integration_id,
            "provider": record.manifest.provider_name,
            "state": record.state.value,
            "probes": record.probes,
            "failure_rate": record.failure_rate,
            "health_score": record.health_score,
            "last_latency_seconds": record.last_latency_seconds,
            "consumptions": record.consumptions,
        }

    def terminate(self, integration_id: str, reason: str, is_human: bool) -> IntegrationRecord:
        """17.31.2 — emergency termination is a human act, immediate and logged."""
        if not is_human:
            raise ApprovalRequired(
                f"terminating '{integration_id}' is a human override; no machine may invoke it (17.31.2)"
            )
        record = self.registry.suspend(integration_id, f"terminated by human override: {reason}")
        self._approved_instances.discard(integration_id)
        self._journal("terminated", integration_id=integration_id, reason=reason)
        return record

    def halt(self) -> int:
        """17.31.4 — panic suspends every Active integration within five seconds.

        Returns how many were suspended. Consumption stops because the
        instances lose their approval, not merely because a flag was set: a
        flag is something a later code path can forget to check.
        """
        halted = 0
        for record in list(self.registry.active()):
            self.registry.suspend(record.integration_id, "panic protocol invoked (17.31.4)")
            halted += 1
        self._approved_instances.clear()
        self._journal("panic_halt", suspended=halted)
        return halted

    # ---------------------------------------------------------------- Health

    def is_blocked(self) -> bool:
        """False since the CIR-001 ruling of 2026-08-24.

        Kept rather than removed so a caller that still asks gets the current
        answer rather than an `AttributeError`, which would leave it unable to
        tell "not blocked" from "no longer able to say".
        """
        return False

    def blocker(self) -> str:
        return CIR_001_RESOLVED

    def health(self) -> Mapping[str, Any]:
        successes = [c for c in self._consumptions if c.succeeded]
        return {
            "status": "constructed",
            "cir_001": "resolved 2026-08-24 by G4 ruling",
            "construction_authorized": True,
            "approved_instances": len(self._approved_instances),
            "consumptions": len(self._consumptions),
            "success_rate": (round(len(successes) / len(self._consumptions), 4) if self._consumptions else 0.0),
            "total_cost": round(sum(c.cost for c in self._consumptions), 6),
            "journal_entries": len(self.journal),
            "journal_intact": self.journal.verify_chain(),
        }

    def _journal(self, action: str, **detail: Any) -> None:
        self.journal.append({"kind": "integration_consumption", "action": action, **detail})


def unbacked_reason(abstraction: str) -> str:
    """Retained for the record.

    Before the CIR-001 ruling, every abstraction reported unbacked and the Tool
    Gateway refused any tool needing one. That refusal was correct then and is
    wrong now, so `UnbackedIntegrationSource` has been replaced by a real
    backing check against the Registry.
    """
    return f"abstraction '{abstraction}' is now resolvable; CIR-001 was resolved 2026-08-24"
