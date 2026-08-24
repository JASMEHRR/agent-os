"""Deployment Registry — construction blocked by CIR-001 (21B §25).

`18.6.1`: "The Deployment Registry is the sole authoritative source of truth
for all operational environments... It does not execute deployments; it governs
their existence and validity."

Every verb here that would govern an environment's existence raises
`ConstructionBlocked`. The schema, the classification and the validation rules
in `manifests.py` are complete and tested, because those are specification.
Bringing an environment into existence is construction, and 21B §25's banner
does not authorize it.

Two verbs remain available deliberately: `validate` answers whether a
declaration conforms, and `is_blocked` reports the block itself. Neither
creates anything. A caller can therefore check its manifests today and will
find them already conformant when the block lifts.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, NoReturn

from deployment_registry.manifests import (
    CIR_001,
    EnvironmentManifest,
    RiskTier,
    blocked,
    default_class_policies,
    validate_manifest,
)


@dataclass
class DeploymentRegistry:
    """Specification-conformant, construction-blocked.

    This is a distinct status from Done and is not a step toward it. Build Spec
    Section 24 requires the debt be tracked explicitly and never silently
    converted.
    """

    # ------------------------------------------------- Specification (open)

    def validate(self, manifest: EnvironmentManifest) -> None:
        """Schema conformance. Creates nothing, so it is not construction."""
        validate_manifest(manifest)

    def class_policy(self, risk_tier: RiskTier) -> Any:
        """The Environment Class Policy Store's declared content (18.9.2)."""
        return default_class_policies()[risk_tier]

    def is_blocked(self) -> bool:
        return True

    def blocker(self) -> str:
        return CIR_001

    # ------------------------------------------------ Construction (blocked)

    def register(self, *_args: Any, **_kwargs: Any) -> NoReturn:
        blocked("register")

    def approve(self, *_args: Any, **_kwargs: Any) -> NoReturn:
        blocked("approve")

    def activate(self, *_args: Any, **_kwargs: Any) -> NoReturn:
        blocked("activate")

    def promote(self, *_args: Any, **_kwargs: Any) -> NoReturn:
        blocked("promote")

    def discover(self, *_args: Any, **_kwargs: Any) -> NoReturn:
        blocked("discover")

    def resolve(self, *_args: Any, **_kwargs: Any) -> NoReturn:
        blocked("resolve")

    def decommission(self, *_args: Any, **_kwargs: Any) -> NoReturn:
        blocked("decommission")

    def record_trust(self, *_args: Any, **_kwargs: Any) -> NoReturn:
        blocked("record_trust")

    def health(self) -> Mapping[str, Any]:
        """Reports the block. Deliberately available: a health surface that
        raised would make the blocked status itself unobservable."""
        return {
            "status": "specification-conformant, construction-blocked",
            "blocker": "CIR-001",
            "environments": 0,
            "construction_authorized": False,
            "resolution_required_at": "G3 or G4 Governance ruling",
        }
