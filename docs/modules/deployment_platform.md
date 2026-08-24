# Deployment Platform — Deployment Registry, Deployment Gateway

**Stage:** S11 — Territory
**Status:** **specification-conformant, construction-blocked** (CIR-001)
**Specifies:** document 18 (`18_DEPLOYMENT_OPERATING_MODEL`), per 21B §25

## The block, first

21B §25 carries the banner: "Construction of this platform does not begin until
CIR-001 is resolved at G3 or G4. This section specifies the architecture; it
does not authorize its construction."

18's deployment topology provisions — environment classes, promotion pipelines,
infrastructure targets — presuppose specific technology and provider choices in
the same way `03_TECH_STACK` does, while 19 rule 22, 17 rule 21 and 18 rule 18
prohibit constitutional documents from naming specific technologies or
providers. 21A §3 names Deployment as one of the three subsystems the ambiguity
blocks.

**This is a distinct status from Done and is not a step toward it.**

## Why the block matters more here than anywhere else

`18.2`: deployment is **"the last constitutional checkpoint before code becomes
behavior."** Every guarantee this system specifies for every other subsystem is
only as real as the deployment path that puts it into production.

So a Deployment Platform built on a guessed answer to CIR-001 would place every
other guarantee — the six authority boundaries, the permission intersection, the
five-second panic bound — onto a substrate chosen by inference. That is the
specific reason the block is honoured rather than worked around.

## What is built

Everything that can be checked without bringing an environment into being:

* **The manifest schema** of 18.8.2, field for field, with validation that is
  real rather than decorative. All four domain invariants of 18.7.2 are
  required, because an undeclared invariant cannot be enforced. Geographic
  locality and data residency are required, because sovereignty cannot be
  verified without them.
* **The classification model.** D1–D4 risk tiers (18.5.1) mapped one-to-one to
  E1–E4 authority (18.5.3), with E4 human-only and undelegable per 18.35.2.
* **The sovereignty constraint.** D4 hosts constitutional infrastructure — the
  Security and Governance Gateways themselves — so it may not sit on a substrate
  shared across organizational boundaries. Enforced in validation.
* **The environment class policies** of 18.9.2, tightening with risk tier, with
  rollback readiness required at *every* tier: there is no class of deployment
  for which being unable to undo it is acceptable.
* **The ordering properties**, asserted against the declared sequence so they
  survive as reviewable artifacts while construction is blocked:
  * rollback readiness is verified **before** authorization, not after failure
    (21B §25.4 with 18.13). A rollback plan confirmed after a failed deployment
    is confirmed too late;
  * policy evaluation precedes the authorization decision, because 18.12 states
    environment-class policy "cannot be satisfied retroactively".
* **The lifecycle machine**, where an Active environment cannot walk backwards
  (18.8.3 requires a new environment with lineage instead), approval precedes
  activation, and a quarantined environment does not resume on its own.

## What raises

Every verb that would bring an environment into existence, mediate access to
one, or terminate one: `register`, `approve`, `activate`, `promote`, `discover`,
`resolve`, `decommission`, `record_trust` on the Registry;
`request_promotion`, `authorize`, `mediate_access`, `verify_rollback_readiness`,
`rollback`, `migrate`, `terminate`, `probe_health`, `bootstrap`,
`deployment_status` on the Gateway.

They **raise rather than no-op**. Build Spec Section 24 forbids silent
conversion to Done, and the failure mode here is specific: a no-op would let a
caller believe an environment had been activated, and therefore believe a
runtime instance was somewhere it is not.

`would_be_permitted` is blocked too, despite sounding like a query. Answering it
requires evaluating policy the Governance ruling has not settled, and a caller
who planned against a guess that later proved wrong would be worse off than one
who knew nothing.

`health()` and `blocker()` remain available. A health surface that raised would
make the blocked status itself unobservable, and the blocker text is quoted in
full so a caller sees *why*, not only *that*.

## The downstream consequence, stated

`18.6.2` makes the Gateway "the sole constitutional path between operational
intent and environmental existence. No runtime instance may exist in an
environment without Gateway mediation."

While construction is blocked there is no such path — so **every runtime
instance in this system runs in no registered environment at all**.
`unbacked_environments()` returns empty and a test asserts it. Returning a
plausible-looking environment would have made the suite greener and the system
less honest.

## What S11's exit criterion leaves unsatisfiable

21_PLAN §4.1 asks for "Environments registered, validated, promoted, isolated by
fault domain and locality; continuity and recovery procedures exercised;
bootstrap reproducible." Scoped to what is unblocked:

| Clause | Status |
|---|---|
| validated | **satisfied** — the schema is complete and enforced |
| registered, promoted | blocked; both are construction |
| isolated by fault domain and locality | declared, not enforced; enforcement needs a substrate |
| continuity and recovery exercised | blocked; requires a live environment |
| bootstrap reproducible | blocked |

`tests/s11_s12_frontier/` names each of these rather than leaving the gap to be
inferred from an absent test.

## Open items

* Everything above the specification line, pending a G3/G4 ruling on CIR-001.
* The Environment Abstraction Layer (18.6.3) is expressed as the `abstractions`
  field on a manifest; the mapping to substrate capabilities is the part CIR-001
  blocks.
* Trust scores (18.6.1) are specified as a Registry responsibility and not
  computed, since there is nothing operating to score.
