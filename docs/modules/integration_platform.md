# Integration Platform — CONSTRUCTION BLOCKED (CIR-001)

**Stage:** S6 — Effect
**Status:** **Specification-conformant, construction-blocked.** Not Done, and
may not be marked Done (Build Spec Section 6, Section 24).
**Modules:** `integration_registry`, `integration_gateway` (blocked);
`llm_router` (built — see below)

## The blocker

21B §20 opens with it, verbatim:

> Construction blocked by CIR-001. `19` non-violable rule 22, `17` rule 21,
> and `18` rule 18 prohibit constitutional documents from naming specific
> technologies or providers, while `03_TECH_STACK` names approximately fifty.
> The portability guarantees of `17.23` and the provider-neutrality
> obligations of `17.23.6` depend on how that prohibition is scoped.
> Construction of this platform does not begin until CIR-001 is resolved at
> G3 or G4. **This section specifies the architecture; it does not authorize
> its construction.**

Build Spec Section 6 rule 9 forbids resolving a CIR-series conflict by
choosing an interpretation unilaterally. Resolving CIR-001 needs a Governance
ruling. Nothing here guesses at one.

## What was built, and why that is the right line

Build Spec Part V holds CIR-001-blocked modules "to specification-level tests
(schema/contract validation) only". So:

**Specification-conformant (built and genuinely enforced):**

- The integration manifest schema, with real validation.
- The capability abstraction model of 17.6.3 — including a check that an
  abstraction does not name its provider, which is the whole point of the
  abstraction layer.
- Risk tiers and the data-classification ceiling of 21B §20.4: a T1
  integration cannot receive Confidential or Restricted data, and a manifest
  cannot declare its way past its tier's limit.
- The per-instance approval rule of 17.14.1: a standing order may pre-authorize
  a *class*, but each instance still requires specific approval.
- Portability declarations (17.20, 17.23), and the rule that low portability
  demands Class D approval.
- Provider concentration, computable from specification alone.

**Construction-blocked (every one raises `ConstructionBlocked`):**

`register`, `approve`, `activate`, `connect`, `probe_health`, `resolve` on the
Registry; `resolve_abstraction`, `consume`, `provider_health`,
`record_consumption`, `retire` on the Gateway.

They raise rather than no-op deliberately. Build Spec Section 24 requires this
debt to be tracked explicitly and "never silently converted to Done status" —
an operation that quietly did nothing would be exactly that silent conversion,
and a caller would believe an integration had been activated.

A parametrized test asserts **every** construction verb raises, so the block
cannot rot into a no-op as the modules are edited.

## The downstream consequence, stated plainly

The Tool Gateway consumes Integration Gateway verification (21B §19.6): a
tool declaring a capability abstraction must have it backed by an active,
approved integration. Nothing can legitimately back an abstraction while
construction is blocked, so `UnbackedIntegrationSource` reports every
abstraction unbacked and **the Tool Gateway refuses such tools**.

This means the S6 test-list clause "a registered tool **backed by an approved
integration**" cannot be satisfied. `tests/s6_integration/` says so in a named
test rather than stubbing a fake integration to make the suite green. Tools
that reach nothing external are unaffected and exercise the rest of the clause
in full.

## The LLM Router is not blocked

21B §20 groups the LLM Router into the Integration Platform, but it is **not**
CIR-001 blocked and is built to full Done-equivalent status. 21B §20.4
explains why: the Router is "an internal abstraction over model tiering, not a
governed external relationship". It sits *above* the Integration Gateway
rather than beside it.

That layering is what lets `01.3.1` Local First hold — Nano and Standard tiers
may be served by locally-hosted capability with no external integration at
all, and Premium degrades to unavailable rather than to failure.

See `docs/modules/llm_router.md`.

## What resolving CIR-001 would unblock

Construction of both modules, and with it the Tool Gateway's ability to
authorize any tool that reaches outside the system. Until then the system can
reason, decide, remember and run internal tools — but cannot reach the
external ecosystem, which is a substantial and deliberate limitation.
