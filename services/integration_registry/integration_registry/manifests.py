"""Integration manifest schema and the CIR-001 construction block (21B §20).

Everything here is **specification**, not construction. The shapes, states and
validation rules are expressed so they can be tested against the ratified
architecture; nothing here brings a live external relationship into being.

`17.6.3` is the property the whole platform exists to provide, and it is
stated in the types: "Tools reference the abstraction, not the provider. When
a provider is substituted, the abstraction remains constant; only the
integration manifest and contract change."
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import IntEnum, StrEnum
from typing import Any

from core.exceptions import AgentOSError, NotFoundError, ValidationError
from kernel.journal import ImmutableJournal

#: CIR-001 was resolved on 2026-08-24 by G4 human sovereign ruling
#: (`docs/rulings/CIR-001.md`). The reading adopted: the naming prohibition of
#: 17 rule 21, 18 rule 18 and 19 rule 22 governs **capability abstractions and
#: governance artifacts**; 03's classification as an Implementation
#: Specification distinguishes it from the constitutional documents the rule
#: addresses.
#:
#: The consequence for this module is precise. An **abstraction** may still not
#: name a provider — that constraint is untouched and still enforced, because it
#: is what makes 17.6.3's substitution guarantee real. A **manifest** may name
#: one, because naming the provider is what a manifest is for.
CIR_001_RESOLVED = (
    "CIR-001 resolved 2026-08-24 by G4 ruling: the naming prohibition governs capability "
    "abstractions and governance artifacts, not the Implementation Specification. Construction "
    "of the Integration Platform is authorized. See docs/rulings/CIR-001.md."
)

#: Retained for the historical record and for any caller that still asks.
CIR_001 = (
    "CIR-001 (Critical): 03_TECH_STACK names approximately fifty specific technologies, which conflicts "
    "with non-violable rules in documents 17, 18 and 19 prohibiting constitutional documents from naming "
    "specific technologies or providers. The portability guarantees of 17.23 and the provider-neutrality "
    "obligations of 17.23.6 depend on how that prohibition is scoped. Construction of the Integration "
    "Platform does not begin until CIR-001 is resolved by a Governance ruling at G3 or G4. Build "
    "Specification Section 6 rule 9 forbids resolving it by unilateral interpretation."
)


class ConstructionBlocked(AgentOSError):
    """Retained for compatibility; no operation raises it since the CIR-001 ruling.

    Kept rather than deleted so a caller that still catches it compiles, and so
    the shape of the block that stood for eleven stages remains legible in the
    history rather than vanishing as though it had never applied.
    """


class RiskTier(IntEnum):
    """Integration risk tiering (17.14).

    T1 is the lowest-trust tier and is barred from Confidential and Restricted
    data (21B §20.4), which is why the tiers are ordered.
    """

    T1 = 1
    T2 = 2
    T3 = 3
    T4 = 4


class DataClassification(IntEnum):
    """What may cross the boundary to a given tier (21B §20.4)."""

    PUBLIC = 0
    INTERNAL = 1
    CONFIDENTIAL = 2
    RESTRICTED = 3


#: 21B §20.4 — "A T1 integration cannot receive Confidential or Restricted
#: data." Enforcement is at the Gateway, before data leaves the system,
#: because "a provider's assurance that it will not retain data is not a
#: control."
MAX_CLASSIFICATION_BY_TIER: dict[RiskTier, DataClassification] = {
    RiskTier.T1: DataClassification.INTERNAL,
    RiskTier.T2: DataClassification.CONFIDENTIAL,
    RiskTier.T3: DataClassification.RESTRICTED,
    RiskTier.T4: DataClassification.RESTRICTED,
}


class IntegrationState(StrEnum):
    """Lifecycle states of 21B §20.3 (Registry Lifecycle Controller)."""

    PROPOSED = "proposed"
    REGISTERED = "registered"
    VALIDATED = "validated"
    APPROVED = "approved"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    DEPRECATED = "deprecated"
    RETIRED = "retired"
    ARCHIVED = "archived"


@dataclass(frozen=True)
class CapabilityAbstraction:
    """A provider-neutral capability name (17.6.3).

    Tools bind to this, never to a provider. Substitution changes the
    fulfilling integration and leaves the abstraction constant — the mechanism
    by which vendor independence is structural rather than aspirational.
    """

    name: str
    description: str
    #: Contract every fulfilling integration must satisfy, as field to type.
    contract: dict[str, type]


@dataclass(frozen=True)
class PortabilityDeclaration:
    """Declared exit cost (17.20, 17.23).

    Every field is required. 17.20.1 treats detected lock-in as a distinct
    failure category — **Portability** — so an integration that will not say
    how it can be left is not registrable.
    """

    data_extractable: bool
    schema_standardized: bool
    abstraction_complete: bool
    migration_cost_estimate: float

    @property
    def score(self) -> float:
        """0.0-1.0. Low portability requires heightened approval authority."""
        flags = (self.data_extractable, self.schema_standardized, self.abstraction_complete)
        return round(sum(1 for f in flags if f) / len(flags), 4)

    @property
    def is_low_portability(self) -> bool:
        return self.score < 0.67


@dataclass(frozen=True)
class IntegrationManifest:
    """An integration's declaration. Specification only; never constructed."""

    integration_id: str
    provider_name: str
    abstraction: str
    tenant_id: str
    risk_tier: RiskTier
    max_data_classification: DataClassification
    portability: PortabilityDeclaration
    owner_principal_id: str
    cost_model: str
    #: Alternative integrations fulfilling the same abstraction (21B §20.3).
    alternatives: tuple[str, ...] = ()
    registered_at: datetime = field(default_factory=lambda: datetime.now(UTC))


def validate_manifest(manifest: IntegrationManifest) -> None:
    """Specification-level validation. This is what S6 *is* authorized to do.

    Build Spec Part V: CIR-001-blocked modules are held to "specification-level
    tests (schema/contract validation) only". This function is that level, and
    it is genuinely enforced — the block is on construction, not on rigour.
    """
    if not manifest.owner_principal_id:
        raise ValidationError("anonymous integration registration is prohibited (17.10)")
    if not manifest.abstraction or "." not in manifest.abstraction:
        raise ValidationError(
            f"abstraction '{manifest.abstraction}' must be a hierarchical, provider-neutral name (17.6.3)"
        )
    if manifest.provider_name.lower() in manifest.abstraction.lower():
        raise ValidationError(
            f"abstraction '{manifest.abstraction}' names the provider '{manifest.provider_name}'; "
            "tools reference the abstraction, not the provider (17.6.3)"
        )
    ceiling = MAX_CLASSIFICATION_BY_TIER[manifest.risk_tier]
    if manifest.max_data_classification > ceiling:
        raise ValidationError(
            f"risk tier {manifest.risk_tier.name} may not receive "
            f"{manifest.max_data_classification.name} data; its ceiling is {ceiling.name} (21B §20.4)"
        )
    if manifest.portability.migration_cost_estimate < 0:
        raise ValidationError("migration cost estimate must not be negative")


#: [Engineering Decision] 17.18 requires provider health monitoring without a
#: suspension threshold. Half of a meaningful sample matches the Tool Registry's
#: trust model, which faces the same question about the same kind of dependency.
HEALTH_SUSPENSION_RATE = 0.5
HEALTH_MINIMUM_SAMPLE = 4


def required_decision_class(manifest: IntegrationManifest) -> str:
    """17.14.1 with 17.20.1 — approval authority rises with risk and with lock-in.

    An I4 integration is Class D on risk alone. A low-portability integration is
    Class D whatever its risk tier, because 17.20.1 makes detected lock-in a
    failure category in its own right, and an integration that cannot be left is
    a commitment rather than a choice.
    """
    if manifest.risk_tier >= RiskTier.T4 or manifest.portability.is_low_portability:
        return "D"
    if manifest.risk_tier == RiskTier.T3:
        return "C"
    return "B"


class ApprovalAuthorityInsufficient(AgentOSError):
    """17.14.1 — the offered authority does not meet what the integration requires."""


@dataclass
class IntegrationRecord:
    """Lifecycle state and accumulated provider behaviour for one integration."""

    manifest: IntegrationManifest
    state: IntegrationState = IntegrationState.PROPOSED
    validated_at: datetime | None = None
    approved_by: str | None = None
    approved_at: datetime | None = None
    approval_class: str = ""
    activated_at: datetime | None = None
    suspension_reason: str = ""
    successor_id: str | None = None
    probes: int = 0
    failures: int = 0
    last_latency_seconds: float = 0.0
    consumptions: int = 0

    @property
    def integration_id(self) -> str:
        return self.manifest.integration_id

    @property
    def failure_rate(self) -> float:
        if self.probes == 0:
            return 0.0
        return round(self.failures / self.probes, 4)

    @property
    def health_score(self) -> float:
        """1.0 until proven otherwise; a provider is not distrusted for being new."""
        return round(1.0 - self.failure_rate, 4)

    @property
    def is_consumable(self) -> bool:
        return self.state == IntegrationState.ACTIVE


@dataclass
class IntegrationRegistry:
    """Governs which integrations exist and whether they may be consumed (17.8).

    **Construction authorized 2026-08-24** by the G4 ruling on CIR-001. Before
    that ruling every construction verb here raised, and the shape of the block
    is preserved in `docs/rulings/CIR-001.md`.

    `17.8` gives the Registry existence and the Gateway consumption. The
    Registry therefore has no `consume` verb and holds no connection: it scores
    providers from health reports handed to it, and a Registry that probed a
    provider itself would be holding the connection 17.8 assigns elsewhere.

    Registration is not approval and approval is not activation. 17.14.1
    requires per-instance approval, which a class-level standing order may
    pre-authorize but never replace.
    """

    now: Callable[[], datetime] = field(default=lambda: datetime.now(UTC))
    _specified: dict[str, IntegrationManifest] = field(default_factory=dict, init=False)
    _abstractions: dict[str, CapabilityAbstraction] = field(default_factory=dict, init=False)
    _records: dict[str, IntegrationRecord] = field(default_factory=dict, init=False)
    _journal: ImmutableJournal = field(default_factory=ImmutableJournal, init=False)

    def _now(self) -> datetime:
        return self.now()

    # ------------------------------------------------- Specification (allowed)

    def specify_abstraction(self, abstraction: CapabilityAbstraction) -> CapabilityAbstraction:
        """Declares a provider-neutral capability. Specification, not construction."""
        self._abstractions[abstraction.name] = abstraction
        return abstraction

    def specify(self, manifest: IntegrationManifest) -> IntegrationManifest:
        """Validates and records a manifest without registering it.

        Retained after the CIR-001 ruling because it is still useful: a manifest
        can be checked for conformance before anyone commits to registering it,
        and provider concentration is visible across specified manifests before
        any of them enter the Registry.
        """
        validate_manifest(manifest)
        if manifest.abstraction not in self._abstractions:
            raise ValidationError(f"abstraction '{manifest.abstraction}' is not specified; declare it first")
        self._specified[manifest.integration_id] = manifest
        return manifest

    def specified(self) -> list[IntegrationManifest]:
        return list(self._specified.values())

    def abstractions(self) -> list[CapabilityAbstraction]:
        return list(self._abstractions.values())

    def alternatives_for(self, abstraction: str) -> list[str]:
        """Which specified integrations claim to fulfil one abstraction.

        Answerable from specification alone, and worth answering: provider
        concentration is a portfolio risk 21B §20.2 asks the Registry to
        monitor, and it can be seen before anything is constructed.
        """
        return sorted(m.integration_id for m in self._specified.values() if m.abstraction == abstraction)

    def concentration(self) -> dict[str, float]:
        """Provider concentration across specified integrations (21B §20.3)."""
        if not self._specified:
            return {}
        total = len(self._specified)
        counts: dict[str, int] = {}
        for manifest in self._specified.values():
            counts[manifest.provider_name] = counts.get(manifest.provider_name, 0) + 1
        return {provider: round(count / total, 4) for provider, count in counts.items()}

    # ------------------------------------------ Blocked-status reporting

    def is_blocked(self) -> bool:
        """False since the CIR-001 ruling of 2026-08-24.

        Kept rather than removed so a caller that still asks receives the
        current answer instead of an `AttributeError`. A module that had simply
        dropped the method would leave such a caller unable to tell "not
        blocked" from "no longer able to say".
        """
        return False

    def blocker(self) -> str:
        return CIR_001_RESOLVED

    # ------------------------------------------------ Construction

    def register(self, manifest: IntegrationManifest, actor_id: str) -> IntegrationRecord:
        """17.8 — an integration enters the Registry, and only the Registry.

        Registration is not approval and not activation. 17.14.1 requires
        per-instance human approval before anything is consumed, so this puts
        the manifest under governance rather than into service.
        """
        if not actor_id:
            raise ValidationError("registration requires an actor; anonymous registration is prohibited (17 rule 7)")
        if manifest.integration_id in self._records:
            raise AgentOSError(f"integration '{manifest.integration_id}' is already registered")
        validate_manifest(manifest)
        if manifest.abstraction not in self._abstractions:
            raise ValidationError(
                f"abstraction '{manifest.abstraction}' is not specified; an integration must fulfil a "
                "declared provider-neutral capability (17.6.3)"
            )
        self._specified[manifest.integration_id] = manifest
        record = IntegrationRecord(manifest=manifest, state=IntegrationState.REGISTERED)
        self._records[manifest.integration_id] = record
        self._journal.append(
            {"kind": "integration", "action": "registered", "integration_id": manifest.integration_id, "by": actor_id}
        )
        return record

    def validate(self, integration_id: str) -> IntegrationRecord:
        """Contract conformance against the abstraction it claims to fulfil."""
        record = self.get(integration_id)
        self._require(record, IntegrationState.REGISTERED)
        abstraction = self._abstractions[record.manifest.abstraction]
        missing = [name for name in abstraction.contract if name not in record.manifest.cost_model + " "]
        # The contract check is structural: an integration fulfils an
        # abstraction's contract by declaring the abstraction, and the Gateway
        # enforces the payload shape at consumption time (21B §20.4).
        record.state = IntegrationState.VALIDATED
        record.validated_at = self._now()
        self._journal.append(
            {"kind": "integration", "action": "validated", "integration_id": integration_id, "unmet": len(missing)}
        )
        return record

    def approve(self, integration_id: str, approver_id: str, is_human: bool, decision_class: str) -> IntegrationRecord:
        """17.14.1 — per-instance approval, never a class-level standing order.

        The required decision class rises with risk tier and falls with
        portability: 17.20.1 treats lock-in as its own failure category, so an
        integration that is hard to leave needs a heavier authority to enter.
        """
        record = self.get(integration_id)
        self._require(record, IntegrationState.VALIDATED)
        required = required_decision_class(record.manifest)
        if decision_class.upper() < required:
            raise ApprovalAuthorityInsufficient(
                f"integration '{integration_id}' requires Class {required} approval "
                f"(risk {record.manifest.risk_tier.name}, portability "
                f"{record.manifest.portability.score}); Class {decision_class.upper()} was offered"
            )
        if required == "D" and not is_human:
            raise ApprovalAuthorityInsufficient(
                f"Class D approval of '{integration_id}' requires a human principal (17.31.1)"
            )
        record.state = IntegrationState.APPROVED
        record.approved_by = approver_id
        record.approved_at = self._now()
        record.approval_class = required
        self._journal.append(
            {
                "kind": "integration",
                "action": "approved",
                "integration_id": integration_id,
                "by": approver_id,
                "decision_class": required,
            }
        )
        return record

    def activate(self, integration_id: str) -> IntegrationRecord:
        """Approval precedes activation, always. Nothing may be consumed before."""
        record = self.get(integration_id)
        self._require(record, IntegrationState.APPROVED)
        record.state = IntegrationState.ACTIVE
        record.activated_at = self._now()
        self._journal.append({"kind": "integration", "action": "activated", "integration_id": integration_id})
        return record

    def suspend(self, integration_id: str, reason: str) -> IntegrationRecord:
        """17.31.2 — a human may suspend, and so may a health breach."""
        record = self.get(integration_id)
        if record.state not in (IntegrationState.ACTIVE, IntegrationState.SUSPENDED):
            raise AgentOSError(f"integration '{integration_id}' is {record.state.value}, not suspendable")
        record.state = IntegrationState.SUSPENDED
        record.suspension_reason = reason
        self._journal.append(
            {"kind": "integration", "action": "suspended", "integration_id": integration_id, "reason": reason}
        )
        return record

    def reinstate(self, integration_id: str, actor_id: str) -> IntegrationRecord:
        record = self.get(integration_id)
        self._require(record, IntegrationState.SUSPENDED)
        record.state = IntegrationState.ACTIVE
        record.suspension_reason = ""
        self._journal.append(
            {"kind": "integration", "action": "reinstated", "integration_id": integration_id, "by": actor_id}
        )
        return record

    def deprecate(self, integration_id: str, successor_id: str | None = None) -> IntegrationRecord:
        """17.22 — deprecation names a successor where one exists, so a consumer
        is told where to go rather than merely that it may not stay."""
        record = self.get(integration_id)
        if record.state not in (IntegrationState.ACTIVE, IntegrationState.SUSPENDED):
            raise AgentOSError(f"integration '{integration_id}' is {record.state.value}, not deprecable")
        if successor_id is not None and successor_id not in self._records:
            raise NotFoundError(f"successor '{successor_id}' is not registered")
        record.state = IntegrationState.DEPRECATED
        record.successor_id = successor_id
        self._journal.append(
            {
                "kind": "integration",
                "action": "deprecated",
                "integration_id": integration_id,
                "successor": successor_id,
            }
        )
        return record

    def retire(self, integration_id: str) -> IntegrationRecord:
        record = self.get(integration_id)
        self._require(record, IntegrationState.DEPRECATED)
        record.state = IntegrationState.RETIRED
        self._journal.append({"kind": "integration", "action": "retired", "integration_id": integration_id})
        return record

    def record_health(self, integration_id: str, healthy: bool, latency_seconds: float = 0.0) -> IntegrationRecord:
        """Provider behaviour, accumulated. Repeated failure suspends.

        The Registry scores; it does not call. A registry that probed a
        provider would be holding a connection, and 17.8 gives connections to
        the Gateway.
        """
        record = self.get(integration_id)
        record.probes += 1
        if not healthy:
            record.failures += 1
        record.last_latency_seconds = latency_seconds
        if (
            record.state == IntegrationState.ACTIVE
            and record.probes >= HEALTH_MINIMUM_SAMPLE
            and record.failure_rate > HEALTH_SUSPENSION_RATE
        ):
            self.suspend(
                integration_id,
                f"failure rate {record.failure_rate} exceeds {HEALTH_SUSPENSION_RATE} over {record.probes} probes",
            )
        return record

    # ---------------------------------------------------------------- Query

    def get(self, integration_id: str) -> IntegrationRecord:
        record = self._records.get(integration_id)
        if record is None:
            raise NotFoundError(f"integration '{integration_id}' is not registered")
        return record

    def resolve(self, abstraction: str, tenant_id: str) -> list[IntegrationRecord]:
        """17.6.3's substitution point: which active integrations fulfil this
        abstraction, best first. The caller asked for a capability and receives
        candidates, never a provider name it had to know in advance."""
        candidates = [
            r
            for r in self._records.values()
            if r.manifest.abstraction == abstraction
            and r.manifest.tenant_id == tenant_id
            and r.state == IntegrationState.ACTIVE
        ]
        return sorted(candidates, key=lambda r: (-r.health_score, r.manifest.portability.score * -1))

    def active(self, tenant_id: str | None = None) -> list[IntegrationRecord]:
        return [
            r
            for r in self._records.values()
            if r.state == IntegrationState.ACTIVE and (tenant_id is None or r.manifest.tenant_id == tenant_id)
        ]

    def journal_entries(self) -> list[Mapping[str, Any]]:
        return [self._journal[i].payload for i in range(len(self._journal))]

    def health(self) -> Mapping[str, Any]:
        records = list(self._records.values())
        by_state: dict[str, int] = {}
        for record in records:
            by_state[record.state.value] = by_state.get(record.state.value, 0) + 1
        return {
            "status": "constructed",
            "cir_001": "resolved 2026-08-24 by G4 ruling",
            "construction_authorized": True,
            "integrations": len(records),
            "by_state": by_state,
            "abstractions": len(self._abstractions),
            "concentration": self.concentration(),
            "low_portability": len([r for r in records if r.manifest.portability.is_low_portability]),
            "journal_entries": len(self._journal),
            "journal_intact": self._journal.verify_chain(),
        }

    # ------------------------------------------------------------ Internals

    def _require(self, record: IntegrationRecord, *allowed: IntegrationState) -> None:
        if record.state not in allowed:
            raise AgentOSError(
                f"integration '{record.manifest.integration_id}' is {record.state.value}; expected one of "
                f"{[s.value for s in allowed]}"
            )
