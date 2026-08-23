"""Integration Registry — **CONSTRUCTION BLOCKED by CIR-001** (21B §20).

21B §20 opens with the block, verbatim:

> Construction blocked by CIR-001. `19` non-violable rule 22, `17` rule 21,
> and `18` rule 18 prohibit constitutional documents from naming specific
> technologies or providers, while `03_TECH_STACK` names approximately fifty.
> The portability guarantees of `17.23` and the provider-neutrality
> obligations of `17.23.6` depend on how that prohibition is scoped.
> Construction of this platform does not begin until CIR-001 is resolved at
> G3 or G4. **This section specifies the architecture; it does not authorize
> its construction.**

Build Specification Part V holds CIR-001-blocked modules "to specification-level
tests (schema/contract validation) only, until construction unblocks", and
Section 6 forbids marking them Done.

**What this module therefore is.** The manifest schema, the capability
abstraction model, the lifecycle states and the validation rules are all
expressed and testable — that is the "specification-conformant" half. Every
operation that would bring a live integration into existence raises
`ConstructionBlocked` — that is the "construction-blocked" half.

**What it deliberately is not.** There is no provider client, no credential
exchange, no live health probe, no abstraction resolution against a running
provider. Those are construction, and construction is not authorized.

Resolving CIR-001 requires a Governance ruling at G3 or G4. Build Spec Section
6 rule 9 forbids Claude Code from resolving it by choosing an interpretation
unilaterally, so this module escalates rather than guessing.
"""

from integration_registry.manifests import (
    CIR_001,
    CapabilityAbstraction,
    ConstructionBlocked,
    DataClassification,
    IntegrationManifest,
    IntegrationRegistry,
    IntegrationState,
    PortabilityDeclaration,
    RiskTier,
    validate_manifest,
)

__all__ = [
    "IntegrationRegistry",
    "IntegrationManifest",
    "CapabilityAbstraction",
    "PortabilityDeclaration",
    "IntegrationState",
    "RiskTier",
    "DataClassification",
    "ConstructionBlocked",
    "validate_manifest",
    "CIR_001",
]
