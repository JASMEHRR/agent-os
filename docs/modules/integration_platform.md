# Integration Platform — BUILT (CIR-001 resolved)

**Stage:** S6 — Effect
**Status:** **Built.** Construction authorized by the G4 ruling of 2026-08-24
recorded in `docs/rulings/CIR-001.md`.
**Modules:** `integration_registry`, `integration_gateway`, `llm_router`

## The blocker, and how it ended

21B §20 opened with a refusal to build:

> Construction blocked by CIR-001. `19` non-violable rule 22, `17` rule 21,
> and `18` rule 18 prohibit constitutional documents from naming specific
> technologies or providers, while `03_TECH_STACK` names approximately fifty.

Build Spec Section 6 rule 9 forbade resolving that unilaterally; it required a
G3 or G4 ruling. The ruling was made at G4 and adopts the reading that the
prohibition governs capability abstractions and governance artifacts, and that
`03`'s classification as an Implementation Specification distinguishes it from
the constitutional documents the rule addresses.

What the ruling did **not** relax is asserted by test, in
`tests/s11_s12_frontier/test_blocked_frontier.py`: an abstraction still may not
name its provider, and 17.6.3 substitution still must leave the abstraction
constant. A ruling that authorizes construction is easy to mistake for one that
relaxes constraints, so the distinction is enforced rather than described.

## What the platform does

**Registry** — manifest schema and validation; the capability abstraction model
of 17.6.3; risk tiers and the data-classification ceiling of 21B §20.4;
portability declarations (17.20, 17.23) with low portability demanding Class D
approval; provider concentration; `register`, `approve`, `activate`,
`deprecate`, `suspend`, `probe_health`, `resolve`.

Approval class rises with risk tier: T4 or low portability demands D, T3
demands C, everything else B. Class D requires a human, and insufficient
authority is refused rather than downgraded.

Provider health is **observed, not probed** — the Registry scores real
consumption outcomes and suspends a provider whose failure rate crosses 0.5
over a minimum sample of four, which avoids a health signal that is a different
call than the ones that matter.

**Gateway** — an ordered pipeline: resolve the abstraction, check the
integration is consumable, check the classification ceiling, check per-instance
approval (17.14.1: a standing order may pre-authorize a *class*, but each
instance still requires specific approval), then run the provider call.
Consumption never crosses a tenant boundary. `terminate` is a human act.
`halt` suspends every active integration for the Panic Protocol.

Tests: 33 in `services/integration_registry/integration_registry/tests/test_integration_platform.py`.

## The Tool Gateway consequence, reversed

The Tool Gateway consumes Integration Gateway verification (21B §19.6). While
construction was blocked, `UnbackedIntegrationSource` reported every
abstraction unbacked and the Tool Gateway refused such tools.

`RegistryIntegrationSource` now asks the real Registry, and a tool whose
abstraction is backed by an active approved integration is authorized.
`UnbackedIntegrationSource` is retained deliberately: a deployment with no
registered integrations is in exactly that position, and the behaviour under
that condition is worth keeping tested.

## The LLM Router was never blocked

21B §20 groups it here, but 21B §20.4 explains it is "an internal abstraction
over model tiering, not a governed external relationship". It sits *above* the
Integration Gateway rather than beside it, which is what lets `01.3.1` Local
First hold. See `docs/modules/llm_router.md`.
