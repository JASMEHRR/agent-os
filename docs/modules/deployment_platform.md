# Deployment Platform — Deployment Registry, Deployment Gateway

**Stage:** S11 — Territory
**Status:** **Built.** Construction authorized by the G4 ruling of 2026-08-24
recorded in `docs/rulings/CIR-001.md`.
**Specifies:** document 18 (`18_DEPLOYMENT_OPERATING_MODEL`), per 21B §25

## The block, and how it ended

21B §25 carried the banner: "Construction of this platform does not begin until
CIR-001 is resolved at G3 or G4." 21A §3 named Deployment as one of the three
subsystems the ambiguity blocked. The G4 ruling resolved it; construction
followed.

The ruling did not touch 18.36.11. A D4 deployment still may not sit on a
shared substrate, and a test says so.

## Deployment Registry

Four gates, in order, none satisfiable retroactively: **declare**, **validate
environment**, **approve**, **activate**. A gate the environment's risk tier
does not require is refused rather than accepted and ignored, because an
accepted-and-ignored gate teaches callers the gate sequence is advisory.

Risk tier maps to approval authority. E4 is human-only and cannot be delegated.
E1 requires no human; E2 does.

All four domain invariants are required at declaration, and lineage must
resolve. Anonymous declaration is prohibited.

**`promote` creates a successor environment carrying lineage rather than
mutating the existing one**, because 18.8.3 freezes an Active environment's
invariants. A promotion that mutated in place would violate the rule it was
implementing.

`record_observation` quarantines an environment after repeated incidents; a
healthy environment keeps full trust. `decommission` and `discover` complete
the surface, and discovery returns environments by property rather than by
name, and never crosses a tenant boundary.

## Deployment Gateway

`request_promotion` walks `PROMOTION_SEQUENCE` appending to `stages_completed`,
so a refusal names the stage that stopped it rather than reporting a bare
failure. Rollback readiness is verified before promotion is authorized, for
every risk tier.

`mediate_access` — no runtime exists in an environment without mediation, and a
quarantined environment accepts none. `migrate` is a fresh mediation, not a
carried grant. `terminate` is an E4 human act and drops every grant in the
terminated environment. `rollback` is refused without verified readiness.
`halt` quarantines every active environment.

Neither component executes infrastructure. Both mediate.

Tests: 40 in `services/deployment_registry/deployment_registry/tests/test_deployment_platform.py`.
