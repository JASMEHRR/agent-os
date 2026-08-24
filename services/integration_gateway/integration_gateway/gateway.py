"""Integration Gateway - **CONSTRUCTION BLOCKED by CIR-001** (21B 20).

The same block that governs the Integration Registry governs this module, and
for the same reason. See `integration_registry.CIR_001` for the full text.

**Specification-conformant half.** The two boundary rules 21B 20.4 states are
expressed and enforced as pure functions over specified manifests:

- **Data classification is enforced at the boundary, not by the provider.**
  "A T1 integration cannot receive Confidential or Restricted data... because
  a provider's assurance that it will not retain data is not a control."
- **Approval is per-integration and human.** 17.14.1 makes integration
  approval a Class C or D decision. Standing orders may pre-authorize
  integration *classes*, but "each integration instance requires specific
  approval."

Both are checkable against a specification, so both are implemented and
tested. Neither requires contacting a provider.

**Construction-blocked half.** Abstraction resolution against a live
integration, capability consumption, provider health, and consumption
recording are all construction. Each raises `ConstructionBlocked`.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, NoReturn

from core.exceptions import ValidationError
from integration_registry import (
    CIR_001,
    ConstructionBlocked,
    DataClassification,
    IntegrationManifest,
    RiskTier,
)
from integration_registry.manifests import MAX_CLASSIFICATION_BY_TIER

__all__ = [
    "IntegrationGateway",
    "ClassificationRefused",
    "ApprovalRequired",
    "classification_permitted",
    "required_decision_class",
    "ConstructionBlocked",
    "CIR_001",
]


class ClassificationRefused(ValidationError):
    """Data above the integration's declared ceiling. Blocked before egress."""


class ApprovalRequired(ValidationError):
    """17.14.1 - each integration instance requires specific human approval."""


def classification_permitted(manifest: IntegrationManifest, classification: DataClassification) -> bool:
    """Whether this data may cross to this integration (21B 20.4).

    Checked against the manifest's *declared* ceiling and its risk tier's
    ceiling, whichever is lower - a manifest cannot declare its way past the
    tier limit.
    """
    tier_ceiling = MAX_CLASSIFICATION_BY_TIER[manifest.risk_tier]
    effective = min(manifest.max_data_classification, tier_ceiling)
    return classification <= effective


def required_decision_class(manifest: IntegrationManifest) -> str:
    """The Decision Class approving this integration must carry (17.14.1).

    Class C by default; Class D where the integration is high risk or has low
    portability, because 21B 20.4 requires low-portability integrations to
    take "heightened approval authority" and lock-in is hard to undo.
    """
    if manifest.risk_tier >= RiskTier.T3 or manifest.portability.is_low_portability:
        return "D"
    return "C"


@dataclass
class IntegrationGateway:
    """Specification-conformant, construction-blocked (Build Spec Section 6)."""

    def check_classification(self, manifest: IntegrationManifest, classification: DataClassification) -> None:
        """Boundary enforcement. Specification-level, and genuinely enforced."""
        if not classification_permitted(manifest, classification):
            raise ClassificationRefused(
                f"integration '{manifest.integration_id}' at risk tier {manifest.risk_tier.name} may not "
                f"receive {classification.name} data; blocked before it leaves the system (21B 20.4)"
            )

    def check_approval(self, manifest: IntegrationManifest, approved_instances: set[str]) -> None:
        """17.14.1 - a class-level standing order does not approve an instance."""
        if manifest.integration_id not in approved_instances:
            raise ApprovalRequired(
                f"integration '{manifest.integration_id}' has no instance-specific approval; a standing "
                "order may pre-authorize a class but each instance requires specific approval (17.14.1)"
            )

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

    def resolve_abstraction(self, *_args: Any, **_kwargs: Any) -> NoReturn:
        raise ConstructionBlocked("resolve_abstraction")

    def consume(self, *_args: Any, **_kwargs: Any) -> NoReturn:
        raise ConstructionBlocked("consume")

    def provider_health(self, *_args: Any, **_kwargs: Any) -> NoReturn:
        raise ConstructionBlocked("provider_health")

    def record_consumption(self, *_args: Any, **_kwargs: Any) -> NoReturn:
        raise ConstructionBlocked("record_consumption")

    def retire(self, *_args: Any, **_kwargs: Any) -> NoReturn:
        raise ConstructionBlocked("retire")
