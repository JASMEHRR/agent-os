"""Environment manifest schema and the CIR-001 construction block (21B §25).

Everything here is **specification**, not construction. The shapes, classes and
validation rules are expressed so they can be tested against the ratified
architecture; nothing here brings a live environment into being.

21B §25 carried a banner: "Construction of this platform does not begin until
CIR-001 is resolved at G3 or G4." **It was resolved on 2026-08-24** by G4 human
sovereign ruling (`docs/rulings/CIR-001.md`), and construction is authorized.

`18.2` frames what was being deferred, and why the deferral was right:
deployment is **"the last constitutional checkpoint before code becomes
behavior"** — every guarantee specified for every other subsystem is only as
real as the deployment path that puts it into production. A Deployment Platform
built on a guessed answer would have placed all of them onto a substrate chosen
by inference. With the answer given, that objection is spent.

`18.6.3` is the property the platform exists to provide, and it is stated in
the types: "Runtime, Security, and other subsystems reference the abstraction,
not the substrate. When a substrate is substituted, the abstraction remains
constant; only the deployment manifest changes."
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import IntEnum, StrEnum

from core.exceptions import AgentOSError, ValidationError

#: The blocker itself, quoted so a caller sees why rather than only that.
CIR_001 = (
    "CIR-001 (Critical): 03_TECH_STACK names approximately fifty specific technologies, which conflicts "
    "with non-violable rules in documents 17, 18 and 19 prohibiting constitutional documents from naming "
    "specific technologies or providers. 18's deployment topology provisions — environment classes, "
    "promotion pipelines, and infrastructure targets — presuppose specific technology and provider "
    "choices in the same way. 21A §3 identifies Deployment as one of the three subsystems this ambiguity "
    "blocks. Construction does not begin until CIR-001 is resolved by a Governance ruling at G3 or G4. "
    "Build Specification Section 6 rule 9 forbids resolving it by unilateral interpretation."
)


class ConstructionBlocked(AgentOSError):
    """Retained for compatibility; nothing raises it since the CIR-001 ruling.

    Kept rather than deleted so a caller that still catches it compiles, and so
    the block that stood for eleven stages stays legible rather than vanishing
    as though it had never applied.
    """

    def __init__(self, operation: str):
        super().__init__(f"'{operation}' was construction-blocked until the CIR-001 ruling of 2026-08-24.")
        self.operation = operation


class RiskTier(IntEnum):
    """18.5.1's deployment classification by risk."""

    D1_OBSERVATIONAL = 1
    D2_OPERATIONAL = 2
    D3_CRITICAL = 3
    D4_SOVEREIGN = 4

    @property
    def required_authority(self) -> EClass:
        """18.5.3 maps risk tier to authority requirement one-to-one."""
        return {
            RiskTier.D1_OBSERVATIONAL: EClass.E1,
            RiskTier.D2_OPERATIONAL: EClass.E2,
            RiskTier.D3_CRITICAL: EClass.E3,
            RiskTier.D4_SOVEREIGN: EClass.E4,
        }[self]


class EClass(IntEnum):
    """18.5.3's authority spectrum, E1 (Business Steward) to E4 (Human Sovereign)."""

    E1 = 1
    E2 = 2
    E3 = 3
    E4 = 4

    @property
    def requires_human(self) -> bool:
        """E2 and above require a human-approved decision (18.5.3)."""
        return self >= EClass.E2

    @property
    def is_human_only(self) -> bool:
        """18.35.2 — E4 authority is bound to human credentials and cannot be delegated."""
        return self is EClass.E4


class Scope(StrEnum):
    """18.5.2. Composition is hierarchical (18.7.3)."""

    TENANT = "tenant"
    PORTFOLIO = "portfolio"
    BUSINESS = "business"
    WORKSPACE = "workspace"


class SovereigntyTier(StrEnum):
    """18.5.4. The classification of substrate control."""

    OWNED = "sovereign_owned"
    LEASED = "sovereign_leased"
    #: 18.5.4 — requires "strict isolation guarantees and bilateral human approval".
    SHARED = "sovereign_shared"


class Purpose(StrEnum):
    """18.5.5."""

    PRIMARY = "primary"
    SECONDARY = "secondary"
    EXPERIMENTAL = "experimental"
    ARCHIVAL = "archival"


class DeploymentState(StrEnum):
    """The environment lifecycle 18.8 and 18.9 describe.

    `18.8.3`: once an environment enters Active, its sovereignty tier,
    geographic locality, scope boundaries and constitutional guarantees are
    **immutable**. Behavioural change requires a new environment with distinct
    Deployment ID lineage.
    """

    DECLARED = "declared"
    VALIDATED = "validated"
    APPROVED = "approved"
    ACTIVE = "active"
    DEGRADED = "degraded"
    QUARANTINED = "quarantined"
    SUPERSEDED = "superseded"
    DECOMMISSIONED = "decommissioned"


DEPLOYMENT_TRANSITIONS: dict[str, set[str]] = {
    DeploymentState.DECLARED: {DeploymentState.VALIDATED, DeploymentState.DECOMMISSIONED},
    DeploymentState.VALIDATED: {DeploymentState.APPROVED, DeploymentState.DECOMMISSIONED},
    DeploymentState.APPROVED: {DeploymentState.ACTIVE, DeploymentState.DECOMMISSIONED},
    DeploymentState.ACTIVE: {
        DeploymentState.DEGRADED,
        DeploymentState.QUARANTINED,
        DeploymentState.SUPERSEDED,
        DeploymentState.DECOMMISSIONED,
    },
    DeploymentState.DEGRADED: {DeploymentState.ACTIVE, DeploymentState.QUARANTINED, DeploymentState.DECOMMISSIONED},
    DeploymentState.QUARANTINED: {DeploymentState.ACTIVE, DeploymentState.DECOMMISSIONED},
    DeploymentState.SUPERSEDED: {DeploymentState.DECOMMISSIONED},
    DeploymentState.DECOMMISSIONED: set(),
}


@dataclass(frozen=True)
class ResilienceProfile:
    """18.8.2's recovery commitments."""

    recovery_time_objective: timedelta
    recovery_point_objective: timedelta
    #: 18.9.2's Resilience Gate requires these validated "through governed
    #: testing", so whether the drill happened is part of the profile.
    continuity_drill_passed: bool = False
    last_drill_at: datetime | None = None


@dataclass(frozen=True)
class EnvironmentInvariants:
    """18.7.2's four domain invariants, declared per environment."""

    isolation: str
    sovereignty: str
    resilience: str
    auditability: str

    def missing(self) -> tuple[str, ...]:
        return tuple(
            name
            for name, value in (
                ("isolation", self.isolation),
                ("sovereignty", self.sovereignty),
                ("resilience", self.resilience),
                ("auditability", self.auditability),
            )
            if not str(value).strip()
        )


@dataclass(frozen=True)
class EnvironmentManifest:
    """18.8.2's manifest, field for field.

    Frozen: 18.8.3 makes the core invariants immutable once Active, and a
    manifest that could be edited afterwards would make that clause a promise
    rather than a property.
    """

    deployment_id: str
    name: str
    version: str
    tenant_id: str
    scope: Scope
    owner_id: str
    risk_tier: RiskTier
    sovereignty_tier: SovereigntyTier
    purpose: Purpose
    #: 18.8.2 — jurisdictional domain and data residency commitments.
    geographic_locality: str
    data_residency: str
    fault_domain: str
    capacity_commitment: str
    invariants: EnvironmentInvariants
    resilience: ResilienceProfile
    security_posture: str
    declared_at: datetime
    #: 18.8.3 — behavioural change is a new environment with lineage.
    predecessor_deployment_id: str | None = None
    #: The substrate-neutral capabilities a consumer asks for (18.6.3).
    abstractions: frozenset[str] = field(default_factory=frozenset)

    @property
    def required_authority(self) -> EClass:
        return self.risk_tier.required_authority


@dataclass(frozen=True)
class EnvironmentClassPolicy:
    """21B §25.3's Environment Class Policy Store entry (18.9.2).

    `18.12` — environment-class policy "cannot be satisfied retroactively", so
    every requirement here is a precondition rather than a post-hoc check.
    """

    risk_tier: RiskTier
    required_authority: EClass
    requires_validation_gate: bool
    requires_compliance_gate: bool
    requires_resilience_gate: bool
    requires_rollback_readiness: bool
    permitted_sovereignty_tiers: frozenset[SovereigntyTier]


def default_class_policies() -> dict[RiskTier, EnvironmentClassPolicy]:
    """18.9.2's gates, tightening with risk tier.

    Specification only: these describe what the Gateway *would* evaluate. No
    promotion can be authorized while CIR-001 blocks construction.
    """
    every_tier: frozenset[SovereigntyTier] = frozenset(SovereigntyTier)
    return {
        RiskTier.D1_OBSERVATIONAL: EnvironmentClassPolicy(
            risk_tier=RiskTier.D1_OBSERVATIONAL,
            required_authority=EClass.E1,
            requires_validation_gate=True,
            requires_compliance_gate=False,
            requires_resilience_gate=False,
            requires_rollback_readiness=True,
            permitted_sovereignty_tiers=every_tier,
        ),
        RiskTier.D2_OPERATIONAL: EnvironmentClassPolicy(
            risk_tier=RiskTier.D2_OPERATIONAL,
            required_authority=EClass.E2,
            requires_validation_gate=True,
            requires_compliance_gate=True,
            requires_resilience_gate=False,
            requires_rollback_readiness=True,
            permitted_sovereignty_tiers=every_tier,
        ),
        RiskTier.D3_CRITICAL: EnvironmentClassPolicy(
            risk_tier=RiskTier.D3_CRITICAL,
            required_authority=EClass.E3,
            requires_validation_gate=True,
            requires_compliance_gate=True,
            requires_resilience_gate=True,
            requires_rollback_readiness=True,
            permitted_sovereignty_tiers=frozenset({SovereigntyTier.OWNED, SovereigntyTier.LEASED}),
        ),
        RiskTier.D4_SOVEREIGN: EnvironmentClassPolicy(
            risk_tier=RiskTier.D4_SOVEREIGN,
            required_authority=EClass.E4,
            requires_validation_gate=True,
            requires_compliance_gate=True,
            requires_resilience_gate=True,
            requires_rollback_readiness=True,
            # 18.5.4 with 18.35.2: constitutional infrastructure does not sit on
            # a substrate shared across organizational boundaries.
            permitted_sovereignty_tiers=frozenset({SovereigntyTier.OWNED}),
        ),
    }


def validate_manifest(manifest: EnvironmentManifest) -> None:
    """Schema validation, which is specification and therefore permitted.

    Validating a manifest brings nothing into being; it only answers whether a
    declaration conforms. Registering, approving or activating one would be
    construction, and those raise.
    """
    if not manifest.deployment_id or not manifest.tenant_id:
        raise ValidationError("an environment manifest must declare a deployment id and a tenant")
    missing = manifest.invariants.missing()
    if missing:
        raise ValidationError(
            f"environment '{manifest.deployment_id}' declares no {list(missing)} invariant; "
            "18.7.2 requires all four, and an undeclared invariant cannot be enforced"
        )
    if not manifest.geographic_locality.strip() or not manifest.data_residency.strip():
        raise ValidationError(
            f"environment '{manifest.deployment_id}' declares no geographic locality or data residency "
            "commitment (18.8.2); sovereignty cannot be verified without one"
        )
    if not manifest.fault_domain.strip():
        raise ValidationError("an environment must be assigned to a fault domain (18.8.2)")
    if manifest.resilience.recovery_time_objective <= timedelta(0):
        raise ValidationError("a recovery time objective must be positive")
    if manifest.predecessor_deployment_id == manifest.deployment_id:
        raise ValidationError("an environment may not be its own predecessor; lineage must advance (18.8.3)")

    policy = default_class_policies()[manifest.risk_tier]
    if manifest.sovereignty_tier not in policy.permitted_sovereignty_tiers:
        raise ValidationError(
            f"{manifest.risk_tier.name} may not sit on a {manifest.sovereignty_tier.value} substrate; "
            f"permitted tiers are {sorted(t.value for t in policy.permitted_sovereignty_tiers)} (18.5.4)"
        )


def promotion_authority(from_tier: RiskTier, to_tier: RiskTier) -> EClass:
    """18.9.3's promotion paths.

    Experimental to Operational needs E2; Operational to Critical needs E3;
    Critical to Sovereign needs E4. The target's authority governs, because
    promotion is "a constitutional certification that an environment is fit for
    higher-order operational responsibility" (18.9.1).
    """
    if to_tier <= from_tier:
        raise ValidationError(
            f"promotion advances authority; {from_tier.name} to {to_tier.name} is not a promotion (18.9.1)"
        )
    return to_tier.required_authority
