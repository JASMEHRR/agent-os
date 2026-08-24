"""Deployment Gateway — the sole path to environmental existence (18.6.2, 21B §25).

**Construction authorized 2026-08-24** by G4 ruling on CIR-001
(`docs/rulings/CIR-001.md`).

`18.6.2`: "The Gateway is the sole constitutional path between operational
intent and environmental existence. No runtime instance may exist in an
environment without Gateway mediation."

`21B` §25.2 separates authorization from execution. This module authorizes a
promotion and mediates access; provisioning is done by environment-specific
infrastructure the caller supplies. A Gateway that provisioned would be both
the authority and the actor.
"""

from deployment_gateway.gateway import (
    CIR_001,
    PROMOTION_GATES,
    PROMOTION_SEQUENCE,
    ConstructionBlocked,
    DeploymentGateway,
    MediationRefused,
    PromotionOutcome,
    RollbackNotReady,
    unbacked_environments,
)

__all__ = [
    "DeploymentGateway",
    "PromotionOutcome",
    "MediationRefused",
    "RollbackNotReady",
    "PROMOTION_SEQUENCE",
    "PROMOTION_GATES",
    "unbacked_environments",
    "ConstructionBlocked",
    "CIR_001",
]
