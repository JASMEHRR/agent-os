"""Integration Registry — governs which integrations exist (17.8, per 21B §20).

**Construction authorized 2026-08-24** by G4 human sovereign ruling on CIR-001
(`docs/rulings/CIR-001.md`). The ruling scoped the naming prohibition of 17
rule 21, 18 rule 18 and 19 rule 22 to **capability abstractions and governance
artifacts**, distinguishing 03's Implementation Specification from the
constitutional documents the rule addresses.

The consequence here is precise, and it is why the module's shape did not
change when the block lifted: an **abstraction** still may not name a provider,
because that is what makes 17.6.3's substitution guarantee real, and the test
asserting it is untouched. A **manifest** may name one, because naming the
provider is what a manifest is for.

`17.8` splits existence from consumption. The Registry governs existence and
holds no connection; the Gateway consumes. So there is no `consume` verb here,
and provider health arrives as reports rather than as probes the Registry makes
itself.
"""

from integration_registry.manifests import (
    CIR_001,
    CIR_001_RESOLVED,
    HEALTH_MINIMUM_SAMPLE,
    HEALTH_SUSPENSION_RATE,
    MAX_CLASSIFICATION_BY_TIER,
    ApprovalAuthorityInsufficient,
    CapabilityAbstraction,
    ConstructionBlocked,
    DataClassification,
    IntegrationManifest,
    IntegrationRecord,
    IntegrationRegistry,
    IntegrationState,
    PortabilityDeclaration,
    RiskTier,
    required_decision_class,
    validate_manifest,
)

__all__ = [
    "IntegrationRegistry",
    "IntegrationRecord",
    "IntegrationManifest",
    "IntegrationState",
    "CapabilityAbstraction",
    "PortabilityDeclaration",
    "RiskTier",
    "DataClassification",
    "MAX_CLASSIFICATION_BY_TIER",
    "ApprovalAuthorityInsufficient",
    "required_decision_class",
    "validate_manifest",
    "HEALTH_SUSPENSION_RATE",
    "HEALTH_MINIMUM_SAMPLE",
    "ConstructionBlocked",
    "CIR_001",
    "CIR_001_RESOLVED",
]
