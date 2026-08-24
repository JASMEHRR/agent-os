"""Integration Gateway — the sole path to the external ecosystem (17, per 21B §20).

**Construction authorized 2026-08-24** by G4 ruling on CIR-001
(`docs/rulings/CIR-001.md`).

`17.8` splits the platform: the Registry governs which integrations exist, this
Gateway governs whether one may be consumed and mediates the consumption.

Three properties are structural. Data classification is enforced at the
boundary rather than trusted to the provider (21B §20.4). Approval is
per-instance, and a class-level standing order never satisfies it (17.14.1).
And callers name a capability abstraction, never a provider, which is what
makes 17.6.3's substitution guarantee real rather than aspirational.
"""

from integration_gateway.gateway import (
    CIR_001,
    CIR_001_RESOLVED,
    ApprovalRequired,
    ClassificationRefused,
    ConstructionBlocked,
    ConsumptionRefused,
    ConsumptionResult,
    IntegrationGateway,
    ProviderCall,
    classification_permitted,
    required_decision_class,
)

__all__ = [
    "IntegrationGateway",
    "ConsumptionResult",
    "ProviderCall",
    "ClassificationRefused",
    "ApprovalRequired",
    "ConsumptionRefused",
    "classification_permitted",
    "required_decision_class",
    "ConstructionBlocked",
    "CIR_001",
    "CIR_001_RESOLVED",
]
