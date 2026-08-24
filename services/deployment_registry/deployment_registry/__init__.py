"""Deployment Registry - specification-conformant, construction-blocked (21B 25).

`18.2` frames what this module gates: deployment is "the last constitutional
checkpoint before code becomes behavior". Every guarantee the other subsystems
specify is only as real as the deployment path that puts it into production.

That is exactly why the CIR-001 block is honoured rather than worked around. A
Deployment Platform built on a guessed answer would place every other
guarantee onto a substrate chosen by inference.
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
    blocked,
    default_class_policies,
    promotion_authority,
    validate_manifest,
)
from deployment_registry.registry import DeploymentRegistry

__all__ = [
    "DeploymentRegistry",
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
    "ConstructionBlocked",
    "CIR_001",
    "blocked",
    "validate_manifest",
    "default_class_policies",
    "promotion_authority",
]
