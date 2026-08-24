"""Deployment Registry — governs environmental existence (18.6.1, per 21B §25).

**Construction authorized 2026-08-24** by G4 ruling on CIR-001
(`docs/rulings/CIR-001.md`).

`18.2` is why the block that preceded the ruling was worth honouring:
deployment is "the last constitutional checkpoint before code becomes
behavior", so every guarantee the other subsystems specify is only as real as
the path that puts it into production.

`18.6.1` gives this module existence and withholds execution — "It does not
execute deployments; it governs their existence and validity." There is
therefore no verb here that provisions, scales or terminates infrastructure.
"""

from deployment_registry.manifests import (
    CIR_001,
    DEPLOYMENT_TRANSITIONS,
    ConstructionBlocked,
    DeploymentState,
    EClass,
    EnvironmentClassPolicy,
    EnvironmentInvariants,
    EnvironmentManifest,
    Purpose,
    ResilienceProfile,
    RiskTier,
    Scope,
    SovereigntyTier,
    default_class_policies,
    promotion_authority,
    validate_manifest,
)
from deployment_registry.registry import (
    INITIAL_TRUST,
    TRUST_SUSPENSION_FLOOR,
    AuthorityInsufficient,
    DeploymentRegistry,
    EnvironmentRecord,
    GateNotPassed,
)

__all__ = [
    "DeploymentRegistry",
    "EnvironmentRecord",
    "EnvironmentManifest",
    "EnvironmentInvariants",
    "EnvironmentClassPolicy",
    "ResilienceProfile",
    "RiskTier",
    "EClass",
    "Scope",
    "SovereigntyTier",
    "Purpose",
    "DeploymentState",
    "DEPLOYMENT_TRANSITIONS",
    "AuthorityInsufficient",
    "GateNotPassed",
    "INITIAL_TRUST",
    "TRUST_SUSPENSION_FLOOR",
    "ConstructionBlocked",
    "CIR_001",
    "validate_manifest",
    "default_class_policies",
    "promotion_authority",
]
