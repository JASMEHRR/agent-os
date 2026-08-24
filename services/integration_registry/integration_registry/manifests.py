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

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import IntEnum, StrEnum
from typing import Any, NoReturn

from core.exceptions import AgentOSError, ValidationError

#: The blocker itself, quoted so a caller sees why rather than just that.
CIR_001 = (
    "CIR-001 (Critical): 03_TECH_STACK names approximately fifty specific technologies, which conflicts "
    "with non-violable rules in documents 17, 18 and 19 prohibiting constitutional documents from naming "
    "specific technologies or providers. The portability guarantees of 17.23 and the provider-neutrality "
    "obligations of 17.23.6 depend on how that prohibition is scoped. Construction of the Integration "
    "Platform does not begin until CIR-001 is resolved by a Governance ruling at G3 or G4. Build "
    "Specification Section 6 rule 9 forbids resolving it by unilateral interpretation."
)


class ConstructionBlocked(AgentOSError):
    """Raised by any operation that would constitute construction.

    Deliberately not a warning and not a no-op. Build Spec Section 24 requires
    construction-blocked debt to be "tracked explicitly as open items" and
    "never silently converted to Done status", and an operation that quietly
    did nothing would be exactly that silent conversion.
    """

    def __init__(self, operation: str):
        super().__init__(
            f"'{operation}' is construction of the Integration Platform, which is not authorized.\n{CIR_001}"
        )
        self.operation = operation


def _blocked(operation: str) -> NoReturn:
    raise ConstructionBlocked(operation)


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


@dataclass
class IntegrationRegistry:
    """Specification-conformant, construction-blocked (Build Spec Section 6).

    Manifests may be *specified* and validated — that is what makes this
    module specification-conformant, and the validation is real. Anything that
    would create a live external relationship raises `ConstructionBlocked`.

    A test asserts every construction verb on this surface raises, so the
    block cannot rot into a no-op as the module is edited.
    """

    _specified: dict[str, IntegrationManifest] = field(default_factory=dict, init=False)
    _abstractions: dict[str, CapabilityAbstraction] = field(default_factory=dict, init=False)

    # ------------------------------------------------- Specification (allowed)

    def specify_abstraction(self, abstraction: CapabilityAbstraction) -> CapabilityAbstraction:
        """Declares a provider-neutral capability. Specification, not construction."""
        self._abstractions[abstraction.name] = abstraction
        return abstraction

    def specify(self, manifest: IntegrationManifest) -> IntegrationManifest:
        """Validates and records a manifest **as a specification**.

        The manifest never reaches Active and no provider is contacted. It
        exists so the schema can be exercised and so the platform's shape is
        reviewable before CIR-001 resolves.
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
        """Uniform across all three CIR-001-blocked subsystems.

        Three modules each reporting their block differently would be three
        chances for one to drift; one shape is one thing to check.
        """
        return True

    def blocker(self) -> str:
        return CIR_001

    def health(self) -> Mapping[str, Any]:
        """Reports the block rather than raising. A health surface that raised
        would make the blocked status itself unobservable."""
        return {
            "status": "specification-conformant, construction-blocked",
            "blocker": "CIR-001",
            "construction_authorized": False,
            "resolution_required_at": "G3 or G4 Governance ruling",
        }

    # ------------------------------------------------ Construction (blocked)

    def register(self, *_args: Any, **_kwargs: Any) -> NoReturn:
        _blocked("register")

    def approve(self, *_args: Any, **_kwargs: Any) -> NoReturn:
        _blocked("approve")

    def activate(self, *_args: Any, **_kwargs: Any) -> NoReturn:
        _blocked("activate")

    def connect(self, *_args: Any, **_kwargs: Any) -> NoReturn:
        _blocked("connect")

    def probe_health(self, *_args: Any, **_kwargs: Any) -> NoReturn:
        _blocked("probe_health")

    def resolve(self, *_args: Any, **_kwargs: Any) -> NoReturn:
        _blocked("resolve")
