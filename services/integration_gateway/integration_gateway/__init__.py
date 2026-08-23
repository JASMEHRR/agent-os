"""Integration Gateway - **CONSTRUCTION BLOCKED by CIR-001** (21B 20).

Specification-conformant: data-classification boundary enforcement and the
per-instance human approval rule are expressed and enforced against specified
manifests. Construction-blocked: abstraction resolution, capability
consumption, provider health and consumption recording all raise.

See `integration_registry.CIR_001` for the blocker text and what resolving it
requires.
"""

from integration_gateway.gateway import (
    CIR_001,
    ApprovalRequired,
    ClassificationRefused,
    ConstructionBlocked,
    IntegrationGateway,
    classification_permitted,
    required_decision_class,
)

__all__ = [
    "IntegrationGateway",
    "ClassificationRefused",
    "ApprovalRequired",
    "classification_permitted",
    "required_decision_class",
    "ConstructionBlocked",
    "CIR_001",
]
