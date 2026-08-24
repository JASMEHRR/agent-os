# Agent OS — Implementation Journal

## Project Status

- **Current Stage:** S7 — FIRST LIGHT (complete; the organizing milestone of 21A §2.2.4 is met)
- **Current Module:** none in progress — next executable work item is Stage S8, the Human Plane (`api_gateway`, `human_interface`)
- **Repository Status:** Layer 0 complete, plus the Trust, Truth, Instrumentation, Economic, Cognition, Authority, Effect, Execution and Orchestration planes. One registered agent executes one task inside one durable workflow, invoking one tool through the full mediation chain, with one human approval gate, one saga compensation path, and complete lineage from human authority to external effect. The system still cannot reach the external ecosystem while CIR-001 blocks the Integration Platform, and has no human-facing surface until S8
- **Overall Progress:** 19 / 26 modules addressed — 17 implemented to their stage exit criteria (`kernel`, `core`, `persistence`, `schema_registry`, `security_gateway`, `event_bus`, `observability_gateway` at its ingestion-only profile, `cost_manager`, `memory_gateway`, `knowledge_gateway`, `decision_gateway`, `tool_registry`, `tool_gateway`, `tool_executor`, `llm_router`, `agent_runtime`, `workflow_engine`) and 2 at specification-conformant, construction-blocked status (`integration_registry`, `integration_gateway`, both CIR-001). 0 / 26 at full Definition-of-Done — Section 39 criterion 2 still requires the CI pipeline to actually execute, and Poetry-managed reproducible builds and `docker compose up` do not exist yet

---

## Entries

### 2026-08-01 — Repository Bootstrap

- **Stage:** S0 (pre-module)
- **Module:** repository root
- **Work Item:** Initialize monorepo per Build Spec Part II, Section 7
- **Files Created:** README.md, .gitignore, IMPLEMENTATION_JOURNAL.md, directory skeleton (libs/, services/, docs/, infra/)
- **Files Modified:** —
- **Tests Added:** —
- **Validation Performed:** —
- **Build Status:** N/A (no code yet)
- **Issues Encountered:** None
- **Resolution:** N/A
- **Commit Hash:** (pending)
- **Notes:** Trunk-based dev on `main`/`master`; CI pipeline skeleton and pre-commit hooks deferred to first code-bearing commit.

### 2026-08-01 — Stage S0: Layer 0 Substrate

- **Stage:** S0 — Kernel & Contracts
- **Module:** `libs/kernel`, `libs/core`, `libs/persistence`, `services/schema_registry`
- **Work Item:** Implement the nine universal Gateway mechanisms in `kernel` (Artifact Identity, Lifecycle State Machine, Boundary Enforcement across all six boundary types, Immutable Journal, Failure Classification, Panic Protocol participation); shared domain models/events/exceptions/constants in `core`; hexagonal Repository port + in-memory adapter in `persistence`; schema validation/versioning in `schema_registry`; the Synthetic Gateway conformance suite proving the substrate sound (Build Spec §12, S0 exit criterion).
- **Files Created:**
  - `libs/kernel/` — `pyproject.toml`, `kernel/{identity,lifecycle,boundaries,journal,failure,panic}.py`, `kernel/tests/test_*.py` (18 tests)
  - `libs/core/` — `pyproject.toml`, `core/{events,exceptions,constants}.py`, `core/tests/test_*.py` (3 tests)
  - `libs/persistence/` — `pyproject.toml`, `persistence/{repository,in_memory}.py`, `persistence/tests/test_in_memory.py` (3 tests)
  - `services/schema_registry/` — `pyproject.toml`, `schema_registry/registry.py`, `schema_registry/tests/test_registry.py` (6 tests)
  - `tests/synthetic_gateway/` — `synthetic_gateway.py` (fixture), `test_synthetic_gateway.py` (15 tests)
  - `conftest.py` (root), `.github/workflows/ci.yml` (lint/type-check/test/security-scan skeleton)
- **Files Modified:** —
- **Tests Added:** 45 total (18 kernel unit, 3 core unit, 3 persistence unit, 6 schema_registry unit, 15 Synthetic Gateway conformance)
- **Validation Performed:** `python -m pytest libs/ services/ tests/ -q` → 45 passed. CI workflow defines lint/mypy/security-scan jobs but they have not been run in this environment (no `ruff`/`bandit`/`pip-audit` execution performed locally yet).
- **Build Status:** Passing locally (pytest). Not yet run through Poetry-managed environments — dependencies were installed directly via pip for this pass, not `poetry install`.
- **Issues Encountered:**
  - No UUIDv7 in Python 3.11 stdlib; `ArtifactIdentity`/`Event` use `uuid4` as a placeholder — marked with a `ponytail:` comment in `kernel/identity.py`.
  - `libs/persistence` ships only the in-memory adapter; the Postgres/SQLAlchemy adapter mandated by the canonical stack is explicitly deferred (noted in `persistence/in_memory.py`), not silently substituted.
  - Poetry is not installed in this environment; `pyproject.toml` files are written to the correct spec but dependency resolution/lockfiles have not been generated (`poetry lock` not run).
- **Resolution:** Deferred items above are open, tracked here — not claimed as Done. Per Build Spec Section 39, `kernel`/`core`/`persistence`/`schema_registry` are **not** marked Done: CI-enforced gates (coverage threshold, mypy --strict, security scans, architecture conformance automation) have not actually executed, only local pytest.
- **Commit Hash:** (pending)
- **Notes:** This satisfies the Stage S0 exit criterion (Synthetic Gateway conformance tests pass) at the local-test level. Full Definition-of-Done per Section 39 requires the CI pipeline to actually run and pass, plus `poetry install`/`poetry lock` for reproducible builds and `docker compose up` for a full local environment — none of which exist yet. Recommend treating S0 as "implementation complete, gates pending" rather than "Done" until those run. Next stage (S1, `security_gateway`) requires explicit go-ahead per the agreed working mode (bootstrap + S0, then stop for review).

### 2026-08-23 — Stage S1: Trust (`security_gateway`)

- **Stage:** S1 — Trust
- **Module:** `services/security_gateway`
- **Work Item:** Realize document 14 in full per 21B §22 — the nine Public Interfaces of §22.5 over the eighteen Internal Components of §22.3.
- **Files Created:**
  - `services/security_gateway/pyproject.toml`
  - `security_gateway/enums.py` — principal types/states, decision outcomes, delegation types, revocation triggers, the six-category incident taxonomy (14.29.1), sensitivity classification (14.5.1), security event types
  - `security_gateway/identity.py` — Identity Registry, Registration Controller, 14.8.3 transition guards on `kernel.LifecycleStateMachine`
  - `security_gateway/tokens.py` — Authentication Engine, Token Service (HMAC-signed, one-hour TTL ceiling, rotation, revocation)
  - `security_gateway/permissions.py` — Permission Graph Engine with hierarchy-aware intersection (14.12.4), precompute-on-change, archived history (14.12.5), child inheritance (14.12.3)
  - `security_gateway/roles.py` — Role Controller (type constraints, expiry, separation-of-duties conflicts), Capability Enforcer
  - `security_gateway/authorization.py` — the eight-step decision flow of 14.10.2, Authorization Cache bounded by token TTL and validated against the revocation list (14.10.4)
  - `security_gateway/delegation.py` — Delegation Manager, chain validation at the point of action (14.14.4), 30-day standing-order ceiling
  - `security_gateway/revocation.py` — Revocation Engine, cascading with explicit propagation acknowledgement (14.15.3)
  - `security_gateway/isolation.py` — Isolation Enforcer, deny-by-default with bilateral human-approved crossing grants (rule 15)
  - `security_gateway/secrets_governor.py` — Secret Governor (injection grants, never values), Credential Governor (14.23.4 human-credential binding)
  - `security_gateway/context.py` — Security Context Factory, immutable per action, non-droppable (14.24.5)
  - `security_gateway/incidents.py` — Incident Classifier with the 14.29.1 response sets and 14.29.2 threshold counters
  - `security_gateway/enforcer.py` — Constitutional Enforcer, point-of-action enforcement of twelve non-violable rules (14.33)
  - `security_gateway/journal.py` — Security Event Journal over `kernel.ImmutableJournal`, written directly to persistence (14.26.1)
  - `security_gateway/gateway.py` — composition of the nine §22.5 interfaces plus Panic Protocol participation
  - `security_gateway/tests/` — `conftest.py` plus eight test modules (110 tests)
  - `docs/modules/security_gateway.md` — architecture note and interface map
- **Files Modified:** `pyproject.toml` (ruff isort first-party list, mypy path), `.github/workflows/ci.yml` (coverage threshold gate), `IMPLEMENTATION_JOURNAL.md`
- **Tests Added:** 110 (identity 10, permissions 11, tokens 13, delegation 9, authorization 18, revocation 8, journal/secrets/context 21, constitutional/isolation/panic 15, S1 exit criterion 5). Repository total: 155.
- **Validation Performed:**
  - `python -m pytest -q` → 155 passed
  - `python -m ruff check libs services tests` → clean; `ruff format` applied
  - `python -m mypy services/security_gateway libs/` (`--strict`) → no issues in 53 source files
  - `python -m bandit -r libs services --exclude "*/tests/*"` → exit 0, zero findings
  - Coverage 97.59% overall, 97% for `security_gateway`, against the new 90% CI gate
- **Build Status:** Passing locally on every gate above. Not run through CI, Poetry environments, or `docker compose`.
- **Issues Encountered:**
  1. **A revoked upstream delegation silently vanished from the chain.** `chain_for` initially walked only live delegations, so revoking A→B left C's chain as just B→C and downstream authority survived — exactly what 14.14.4 forbids. Fixed by walking dead interior links so `validate_chain` raises on the break, while an expired grant at the *head* still simply means "not acting under delegation".
  2. **Cascading revocation bypassed the delegation log.** The cascade revoked delegations directly, skipping the journal write, so 14.14.5's "every delegation revocation is logged immutably" held for operator revocations but not cascaded ones. Fixed by journalling each cascaded revocation with `cause: cascade`.
  3. **Bandit B105 false positives** on `TOKEN_ISSUED`, `SECRET_ROTATED` and similar. The names are constitutional terminology and may not be renamed (Part IV, 26), so they carry `# nosec B105` with the reason recorded above the class.
  4. **`manage_delegation` returned a union type**, forcing a cast at every call site. Chain validation was split into `validate_delegation_chain`; both remain the single 21B §22.5 "Delegation Management" interface.
- **Resolution:** All four resolved in-branch; each has a regression test.
- **Open Items (deferred, not silently absorbed):**
  - `cost_manager` (Stage S3) does not exist. `budget_resolver` is injectable and defaults to unmetered — the Gateway does not fabricate a budget it cannot know.
  - Escalation routing by decision class (14.10.3) needs the org model that Agent Runtime owns (Stage S7). Escalation currently targets the human sovereign rather than guessing an intermediate authority.
  - Persistence is still the in-memory adapter; seven-year Sovereign-class retention is recorded per entry but not storage-enforced.
  - CIR-002 (transport binding) remains unresolved and blocks final transport binding at this stage, per Section 6. Interface *semantics* are implemented; the inter-service transport mechanism is not chosen here.
  - `poetry lock` / `poetry install` still not run; no lockfiles exist.
- **Commit Hash:** (pending)
- **Notes:** Section 39 status is **implementation complete, gates pending** — not Done. Criteria 1, 3, 4 and 5 hold; criterion 2 (all Conformance Gate categories pass) requires the CI pipeline to actually execute, which it has not. The Stage S1 exit criterion itself is demonstrated end to end in `tests/test_s1_exit_criterion.py` and retained as a standing regression test, together with an assertion that the module imports nothing outside `kernel`/`core`/`persistence` (Section 25(a) prohibited-edge check). Part VI "Kernel Ready" is also satisfied: `security_gateway` reuses the kernel's lifecycle engine, six-boundary enforcement engine, immutable journal and panic hook without a single modification to the substrate.

### 2026-08-23 — Stage S2: Truth (`event_bus`)

- **Stage:** S2 — Truth
- **Module:** `services/event_bus`
- **Work Item:** Realize document 08 in full plus 02.3.4, per 21B §15 — the six Public Interfaces of §15.5 over the thirteen Internal Components of §15.3.
- **Files Created:**
  - `services/event_bus/pyproject.toml`
  - `event_bus/envelope.py` — the six domain categories (08.5.1), canonical delivery states and transition guards (08.8), the 08.15.4 retention schedule verbatim, `Provenance` (08.12.2), immutable `PublishedEvent`
  - `event_bus/admission.py` — Admission Controller with the four ordered checks; `TrustPlane` and `SchemaSource` ports
  - `event_bus/streams.py` — Stream Store (append-only, category/tenant partitioned), Stream Writer, Gap Detector
  - `event_bus/consumers.py` — Consumer Group Registry, Router (metadata-only, tenant-isolating), per-group `RetryPolicy`
  - `event_bus/delivery.py` — Delivery Manager, Retry Scheduler, Dead Letter Manager
  - `event_bus/causality.py` — Causality Tracker implementing the three happens-before clauses of 08.13.4
  - `event_bus/backpressure.py` — Backpressure Controller, Archive Manager
  - `event_bus/replay.py` — Replay Engine with sandboxed, replay-tagged output
  - `event_bus/security_adapter.py` — the only module importing `security_gateway`
  - `event_bus/schema_adapter.py` — version narrowing for the Schema Registry
  - `event_bus/bus.py` — composition of the six §15.5 interfaces plus Panic Protocol participation
  - `event_bus/tests/` — `conftest.py` plus four test modules (61 tests)
  - `docs/modules/event_bus.md` — architecture note and interface map
- **Files Modified:** `conftest.py` (S1/S2 packages on the test path), `pyproject.toml` (isort first-party, mypy path), `IMPLEMENTATION_JOURNAL.md`
- **Tests Added:** 61 (admission 12, delivery/routing/retry/dead-letter 19, causality/streams/backpressure/retention 20, S2 exit criterion and constraints 10). Repository total: 216.
- **Validation Performed:**
  - `python -m pytest -q` → 216 passed
  - `python -m ruff check libs services tests` → clean; `ruff format` applied
  - `python -m mypy .` (`--strict`) → no issues in 80 source files
  - `python -m bandit -r libs services --exclude "*/tests/*"` → exit 0, zero findings
  - Coverage 97.86% overall against the 90% CI gate
- **Build Status:** Passing locally on every gate. Not run through CI, Poetry environments, or `docker compose`.
- **Integration note:** The S2 suite wires the Bus against a **real Security Gateway and a real Schema Registry**, not stubs. A producer genuinely authenticates, the live permission graph genuinely authorizes the emission, and an authorization denial genuinely comes from the Permission Intersection Rule. These are integration tests across the S1→S2 dependency edge rather than unit tests with a mock in the seam.
- **Issues Encountered:**
  1. **Schema version spelling differs between S0 and S2.** `08.4.1` calls `schema_version` a semantic version and `core.Event` defaults it to `1.0.0`; the Schema Registry keys entries by `major.minor`, because 08's evolution rules only distinguish additive minors from breaking majors. Rather than redesign a Done module's interface (Part IV, 17), `schema_adapter.py` narrows the version on the way in and the discrepancy is carried as an open item below.
  2. **`assert` in the replay scoping branch** would vanish under `python -O`, which Bandit flagged (B101). Rewritten as an ordinary branch.
- **Resolution:** Both resolved in-branch.
- **Open Items (deferred, not silently absorbed):**
  - The schema version discrepancy above needs a real decision by the Schema Registry's owner; the adapter is a bridge, not a resolution.
  - **Performance is entirely unvalidated.** 21B §15.12 publishes a full constitutional latency table (emission→publication p50 10ms, 50,000 events/second sustained) but the store is the in-memory adapter. The Redis Streams binding of the canonical stack does not exist, so nothing meaningful has been measured. This is the largest gap in the module.
  - Encryption in transit and at rest (08.18.3) arrives with the real transport and storage adapters.
  - CIR-002 (transport binding) is still unresolved; delivery *semantics* are implemented, the transport mechanism is not chosen.
  - Consumer delivery-timeout redelivery is driven by explicit failure signalling and the retry scheduler; a wall-clock timeout sweep for consumers that go silent without signalling is not implemented.
- **Commit Hash:** (pending)
- **Notes:** Section 39 status is **implementation complete, gates pending** — criterion 2 still requires the CI pipeline to actually run. The Stage S2 exit criterion is demonstrated end to end in `tests/test_s2_exit_criterion.py`, which runs all five clauses in one narrative. Two architectural-conformance tests are retained as standing guards: one asserts the Bus exposes no authorization method of its own (21A §5.4.2 — it is not a Gateway), and one asserts `security_gateway` is imported in exactly one module, so the permitted S1→S2 dependency edge stays visible in the adapter instead of spreading through the subsystem.

### 2026-08-23 — Stage S3: Instrumentation & Economics (`observability_gateway`, `cost_manager`)

- **Stage:** S3 — Instrumentation & Economics
- **Modules:** `services/observability_gateway` (ingestion-only profile), `services/cost_manager`
- **Work Item:** Give every subsequent module's Signal Emission somewhere to land, and its budget enforcement something to enforce against.
- **Files Created:**
  - `libs/kernel/kernel/signals.py` — **the Signal Emission contract (21A §5.2 item 7)**, the seventh universal Gateway mechanism, which Stage S0 did not build. See "S0 gap closed" below.
  - `libs/kernel/kernel/tests/test_signals.py` — 9 tests
  - `services/observability_gateway/` — `pyproject.toml`, `ingest.py` (Telemetry Ingest, enrichment, quality anomalies), `gateway.py` (ingestion endpoint, read-only Query API, Panic Confirmation Listener, self-health), `security_adapter.py`, `tests/` (32 tests)
  - `services/cost_manager/` — `pyproject.toml`, `ledger.py` (append-only cost ledger, budget allocations), `breakers.py` (cost-based circuit breakers), `manager.py` (four-level enforcement, attribution, alerting), `tests/` (35 tests)
  - `tests/s3_integration/test_s3_exit_criterion.py` — the stage exit criterion end to end against a synthetic caller, spanning both modules plus the kernel channel (5 tests)
  - `docs/modules/observability_gateway.md`, `docs/modules/cost_manager.md`
- **Files Modified:** `libs/kernel/kernel/__init__.py` (export the new mechanism), `conftest.py`, `pyproject.toml`, `IMPLEMENTATION_JOURNAL.md`
- **Tests Added:** 81 (kernel signals 9, observability 32, cost manager 35, S3 integration 5). Repository total: 297.
- **Validation Performed:**
  - `python -m pytest -q` → 297 passed
  - `python -m ruff check libs services tests` → clean; `ruff format` applied
  - `python -m mypy .` (`--strict`) → no issues in 98 source files
  - `python -m bandit -r libs services --exclude "*/tests/*"` → exit 0, zero findings
  - Coverage 98.13% overall against the 90% CI gate
- **Build Status:** Passing locally on every gate. Not run through CI, Poetry environments, or `docker compose`.

- **S0 gap closed:** 21A §5.2 enumerates nine universal Gateway mechanisms and Build Spec Section 12 assigns them to `kernel`. Stage S0 implemented six (identity, lifecycle, boundaries, journal, failure classification, panic) and left **Signal Emission** unbuilt — it went unnoticed because no consumer existed until now. It is implemented in `kernel/signals.py` rather than inside the Observability Gateway, because Section 12 is explicit that these mechanisms are "factored here once rather than reimplemented per-Gateway". This completes S0's mandate rather than redesigning it, so Part IV Section 17's refactoring restriction is not engaged. **`kernel`'s prior stage-completion claim was therefore incomplete when made** — recorded here rather than quietly corrected. The remaining two mechanisms of §5.2 (Confidence/Authority Resolution, Category 1 Incident escalation) are still unbuilt in `kernel`; they have no consumer before S5 and are tracked as an open item below.

- **Issues Encountered:**
  1. **Ingestion could raise back into an emitting subsystem.** The first cut let `SignalRejected` escape `ingest`. That is Observability steering an operational path, which 16.4 forbids. Fixed on both sides of the seam: `ingest` returns the `QualityAnomaly`, and `SignalEmitter.submit` catches sink failures and buffers rather than propagating.
  2. **Two tests asserted `QueryNotAuthorized` where an invalid token legitimately raises `AuthenticationError`.** The tests were wrong, not the code — authentication fails before authorization is reached. Split into separate tests for the two barriers.
  3. **A source-text scan for a prohibited dependency matched prose in a docstring.** Replaced with an import-line scan.
  4. Two `assert` statements would vanish under `python -O` (Bandit B101); rewritten as ordinary branches.

- **Resolution:** All four resolved in-branch, each with a regression test.

- **Open Items (deferred, not silently absorbed):**
  - **Two kernel mechanisms of 21A §5.2 remain unbuilt**: Confidence/Authority Resolution and Category 1 Incident escalation. Neither has a consumer before Stage S5 (`decision_gateway`); both must land before that stage claims completion.
  - Observability's **retention, decay and archival (16.7.7)** are not implemented; the Archived and Expired signal states exist in the lifecycle but tiering is a storage-tier concern awaiting the real telemetry store.
  - **Coverage anomalies for absent signals (16.7.8)** need the expectation model that arrives with the interpretive profile at S10.
  - Cost Manager's **cost projection and optimization recommendations** (both named in 02.3.9) are not built: projection needs historical spend curves, and recommendations need the LLM Router (S6). **LLM Router pre-flight integration**, also named in 02.3.9, likewise awaits S6.
  - Budget period rollover is not automatic; a new period is a new allocation.
  - Both modules use the in-memory adapter; the high-volume telemetry tier (21B §24.7) and the `aos_analytics` ledger store (21A §10) do not exist.
  - CIR-003 (data ownership allocation) remains unratified, and 21A §10's allocation is what both modules' stores are named against — still a proposal, not fact.

- **Commit Hash:** (pending)
- **Notes:** Section 39 status for both modules is **implementation complete, gates pending** — criterion 2 still requires the CI pipeline to actually run. `observability_gateway` is explicitly at its **ingestion-only profile** per the build plan; the interpretive components are absent rather than stubbed, and a test asserts their method names do not exist on the surface so nothing downstream can depend on a hollow implementation. Standing conformance guards added this stage: Observability exposes no mutating verb (21B §24.14 — no hidden control channel), the Cost Manager exposes no budget override, and `cost_manager` imports no observability module (21B §24.13 — the dependency is one-directional). The S3 integration suite also proves the failure posture that makes Observability safe to depend on: with a deliberately broken sink, budget enforcement still halts at Red and still escalates, and the telemetry buffers for a later drain rather than being lost.

### 2026-08-23 — Stage S4: Cognition (`memory_gateway`, `knowledge_gateway`)

- **Stage:** S4 — Cognition
- **Modules:** `services/memory_gateway`, `services/knowledge_gateway`
- **Work Item:** Realize document 09 as far as its artifact extends (plus 02.3.5) per 21B §16, and document 10 in full per 21B §17.
- **Files Created:**
  - `services/memory_gateway/` — `entries.py` (identity primitives 09.4.1, the four classifications of 09.5, the four tiers of 09.7, states and transition guards of 09.9), `pipeline.py` (Admission Controller, Formation Engine, Quarantine Store, Validation Engine, Integration Engine, Decay Engine), `gateway.py` (the five §16.5 interfaces, four boundaries, disposition), `security_adapter.py`, `tests/` (44 tests)
  - `services/knowledge_gateway/` — `beliefs.py` (confidence bands of 10.14.2, states and guards of 10.8, Evidence, Falsifiability, Contradiction), `pipeline.py` (Extraction, Hypothesis Store, Validation, Contradiction Detector, Reconciliation Engine), `graph.py` (Graph Engine with the three integrity constraints of 10.17.4, Ontology Manager), `gateway.py` (the seven §17.5 interfaces), `adapters.py`, `tests/` (55 tests)
  - `tests/s4_integration/test_s4_exit_criterion.py` — the stage exit criterion end to end plus the unidirectional-pipeline guards (6 tests)
  - `docs/modules/memory_gateway.md`, `docs/modules/knowledge_gateway.md`
- **Files Modified:** `conftest.py`, `pyproject.toml`, `IMPLEMENTATION_JOURNAL.md`
- **Tests Added:** 105. Repository total: 402.
- **Validation Performed:**
  - `python -m pytest -q` → 402 passed
  - `python -m ruff check libs services tests` → clean; `ruff format` applied
  - `python -m mypy .` (`--strict`) → no issues in 117 source files
  - `python -m bandit -r libs services --exclude "*/tests/*"` → exit 0, zero findings
  - Coverage 97.63% overall against the 90% CI gate
- **Build Status:** Passing locally on every gate. Not run through CI, Poetry environments, or `docker compose`.

- **The Document 09 gap, per Build Spec Section 6 and Rule 5:** the artifact terminates mid-Section 10. Sections 10.1–30 are absent, including the Non-Violable Memory Rules, the Glossary and the Performance Characteristics. **No content was fabricated for them.** Sections 4–9 are complete and carry the module: identity primitives, classification, the four tiers, the lifecycle and the state machine with its transition guards are all constitutional here, not inferred. Two consequences stand recorded rather than resolved: memory performance figures are provisional, derived from the Knowledge Gateway's budgets per 21B §16.12 and superseded the moment the source is recovered; and **`memory_gateway`'s conformance suite cannot claim completeness**, because the missing Non-Violable Rules are precisely what such a suite would test against. Per the Stage S4 Definition of Done, this caveat does not block Done status but is carried here as an open item.

- **Issues Encountered:**
  1. **Decay and retention measured from the wrong clock.** `MemoryEntry.formed_at` defaulted to wall-clock at object construction — the *producer's* instant — while the Gateway runs on an injected clock. Idle-decay and the seven-year retention window were therefore computed against a timestamp the Gateway does not control, which a producer with a skewed clock could have shifted arbitrarily. Fixed at the root: the entry now carries `captured_at` (the producer's stamp, retained for provenance) and `MemoryRecord.formed_at` is assigned by the Formation Engine from the Gateway's clock. Retention and decay read the record.
  2. **The same bug in `knowledge_gateway`**, found by the same class of test: revalidation cadence measured from `Belief.formed_at`. Fixed identically — `Belief.captured_at` plus `BeliefRecord.formed_at` assigned by the Extraction Engine.
  3. **`KnowledgeGateway.ontology()` shadowed the `self.ontology` attribute**, so the Ontology Query interface would have overwritten the Ontology Manager at first call. Caught before any test ran; the method is `query_ontology`.
  4. Two tests asserted behaviour that was actually correct system behaviour rather than a defect: a token expiring after a simulated year (one-hour TTL, 14.9.2) and a credential expiring after 90 days. The tests now rotate the credential and re-authenticate, which is what a long-lived principal must genuinely do.
  5. A stale `from typing import Any` placed at the bottom of `graph.py` under a false cycle comment; moved to the top.

- **Resolution:** All five resolved in-branch. Issues 1 and 2 are the same root cause in two modules and each has a regression test.

- **Open Items (deferred, not silently absorbed):**
  - **Two kernel mechanisms of 21A §5.2 are still unbuilt**: Confidence/Authority Resolution and Category 1 Incident escalation. **Stage S5 (`decision_gateway`) is the first consumer of both**; they must land before S5 claims completion. This is now the highest-priority carried item.
  - Memory: source reliability is an injected callable with a flat 0.8 default; the Learning Gateway (S9) refines it. Working-tier durability against process loss (09.7.1) needs a real store. Consolidation (09.19) and anonymized cross-boundary sharing (09.20) appear in the surviving table of contents but not in the surviving body.
  - Knowledge: the automated extraction cycle triggered from the Event Bus is not wired; archival tiering needs a real store; load-shedding order (21B §17.12) is unimplemented because there is no load to shed.
  - **Performance is unvalidated in both modules.** 10.24.1 publishes a full latency table (canonical belief query p50 50ms, 10,000 queries/second, three-hop traversal p50 100ms) measured here against in-memory dicts. Nothing meaningful has been measured.
  - CIR-003 (data ownership allocation) remains unratified, and both modules' stores are named against 21A §10's *proposed* allocation. Build Spec Section 6 requires ADR ratification "before Stage S4 proceeds on firm ground" — S4 has proceeded on the explicitly provisional basis, and the ratification is still outstanding.

- **Commit Hash:** (pending)
- **Notes:** Section 39 status for both modules is **implementation complete, gates pending** — criterion 2 still requires the CI pipeline to actually run, and `memory_gateway` additionally carries the Document 09 caveat above. The S4 integration suite proves the property neither module can prove alone: the **Events → Memory → Knowledge pipeline is unidirectional and acyclic** (09.6.4, 10.6.4). Standing conformance guards added this stage: the Memory Gateway's surface contains no reference to Knowledge, the Knowledge Gateway's view of Memory is a single read method on a Protocol, the Decay Engine exposes no delete path, and each module's cross-module imports are confined to one adapter file. A further test proves corrections flow forward as new linked entries rather than mutating the original.

### 2026-08-24 — Stage S5: Authority (`decision_gateway`)

- **Stage:** S5 — Authority
- **Module:** `services/decision_gateway`, plus the two outstanding kernel mechanisms
- **Work Item:** Realize document 11 in full per 21B §18 — the eight Public Interfaces of §18.5 over the twenty Internal Components of §18.3.
- **Files Created:**
  - `libs/kernel/kernel/authority.py` — **Confidence/Authority Resolution (21A §5.2 item 5)**, with the 11.9.1 authority spectrum, the 11.9.2 confidence floors, 11.14.3 risk-adjusted escalation, and the shared `derive_confidence` CIR-006 calibration surface
  - `libs/kernel/kernel/escalation.py` — **Category 1 Incident escalation (21A §5.2 item 10)**, with the fixed 14.33.3 response set and no machine acknowledgement path
  - `libs/kernel/kernel/tests/test_authority_and_escalation.py` — 27 tests
  - `services/decision_gateway/` — `pyproject.toml`, `decisions.py` (identity, the four classes, 11.8 states and guards, standing orders, approval requests), `pipeline.py` (Classifier, OptionValidator, EvidenceAssembler, EvaluationEngine, ConfidenceEngine, RiskAssessor, ApprovalOrchestrator, StandingOrderManager, CompensationVerifier, PortfolioCircuitBreaker), `gateway.py` (the eight §18.5 interfaces, overrides, panic), `adapters.py`, `tests/` (62 tests)
  - `tests/s5_integration/test_s5_exit_criterion.py` — the stage exit criterion end to end plus the mandated adversarial suite (6 tests)
  - `docs/modules/decision_gateway.md`
- **Files Modified:** `libs/kernel/kernel/__init__.py`, `conftest.py`, `pyproject.toml`, `IMPLEMENTATION_JOURNAL.md`
- **Tests Added:** 95 (kernel 27, decision gateway 62, S5 integration 6). Repository total: 497.
- **Validation Performed:**
  - `python -m pytest -q` → 497 passed
  - `python -m ruff check libs services tests` → clean; `ruff format` applied
  - `python -m mypy .` (`--strict`) → no issues in 130 source files
  - `python -m bandit -r libs services --exclude "*/tests/*"` → exit 0, zero findings
  - Coverage 97.36% overall against the 90% CI gate
- **Build Status:** Passing locally on every gate. Not run through CI, Poetry environments, or `docker compose`.

- **S0 gap closed (second and final tranche):** 21A §5.2's nine universal Gateway mechanisms are now all present in `kernel`. S3 added Signal Emission; this stage adds **Confidence/Authority Resolution** and **Category 1 Incident escalation**, which were the two the S3 Journal entry recorded as outstanding and required before S5 could claim completion. `kernel` now genuinely implements what Build Spec Section 12 assigns it.

- **Issues Encountered (four real defects, all found by tests):**
  1. **`derive_confidence` made Class C and D structurally unreachable.** The first cut multiplied evidentiary confidence, option quality, temporal relevance and a risk penalty straight through. Four sub-unit factors collapse fast: evidence at 0.95 with a good-but-not-crushing option margin landed at 0.71, below the 0.80 floor for Level 3. Every Class C and D decision would have deferred forever rather than being decided under human approval — the opposite of what the constitution intends. Option quality and temporal relevance now modulate the evidentiary base above a floor rather than replacing it.
  2. **Risk-escalated decisions were escalated but never routed for approval.** 11.14.3 says a Class B decision at High risk is "treated as Class C for authority purposes". The first cut raised the required authority and then sent the decision to Escalated, which raised the bar and provided no way to clear it. Routing now follows the *effective* authority, so such a decision takes the Class C path and gets a packaged human approval request.
  3. **Classification used declared rather than effective reversibility.** An agent could mark an option `reversible=True`, supply no compensation reference, and receive Class A treatment for an action nothing can undo — precisely the threshold-gaming 11.24.2 names as a drift pattern. The Classifier and the Compensation Verifier now share one judgement.
  4. **The portfolio concentration limit fired on an empty portfolio.** The first commitment to any business is 100% concentrated by arithmetic, so the breaker rejected every first commitment. A concentration floor now gates the check.
  Also: `Approved -> Escalated` is not an edge in 11.8.2. A circuit-breaker breach from Approved now takes `Approved -> Rejected`, which the ratified table does permit, rather than widening the table to suit the response.

- **Resolution:** All resolved in-branch; each has a regression test.

- **Open Items (deferred, not silently absorbed):**
  - **`event_bus` is not wired into this Gateway.** 21B §18.6 lists it for trigger consumption and decision lifecycle emission. Signals and journalling are in place; lifecycle event publication is not. Small work item, recorded rather than done quietly.
  - **Human Interface (S8) does not exist**, so `route_to_human` defaults to a no-op: approval requests and escalations are packaged and journalled but delivered nowhere yet.
  - **Memory Gateway is not consulted** for the sparse-evidence context 21B §18.6 lists it for; only Knowledge is queried, for contradiction status.
  - Performance is unvalidated against the 21B §18.12 latency table; the store is in-memory.
  - CIR-004 (composite mediation-chain latency) and CIR-007 (confidence miscalibration propagating through four subsystems) both remain open and both bear directly on this module. `kernel.derive_confidence` is deliberately the single place CIR-006/CIR-007 recalibration will land.

- **Commit Hash:** (pending)
- **Notes:** Section 39 status is **implementation complete, gates pending** — criterion 2 still requires the CI pipeline to actually execute. The Stage S5 exit criterion is demonstrated end to end in `tests/s5_integration/`, including the adversarial test the Validation Criteria explicitly demand: four distinct attacks on the Class D approval gate (outlast the window repeatedly, self-approve as proposer, answer as a non-human service, commit without an approval at all), every one of which must fail — and does. Standing conformance guards added this stage: the Approval Orchestrator exposes no auto-approval method, and the Decision Gateway exposes no `execute`/`dispatch` method, since 21B §18.7 is explicit that it records commitments and does not execute them.

### 2026-08-24 — Stage S6: Effect (Tool Platform, LLM Router, Integration Platform)

- **Stage:** S6 — Effect
- **Modules:** `tool_registry`, `tool_gateway`, `tool_executor`, `llm_router` (full); `integration_registry`, `integration_gateway` (**specification-conformant, construction-blocked**)
- **Work Item:** Realize document 12 in full with its mandatory three-way separation, document 17 and 02.3.8 plus the ten-stage prompt pipeline of 02.8.5.
- **Files Created:**
  - `services/tool_registry/` — `manifests.py` (sandbox tiers, contracts, compensation, lifecycle), `registry.py` (registration validation, Trust Engine, discovery, health), `security_adapter.py`, `tests/` (29 tests)
  - `services/tool_gateway/` — `contracts.py` (the eight-component invocation contract of 12.17, attribution chain, invocation record), `gateway.py` (ordered verification sequence, sandbox assignment, composition, circuit breaker, output validation, compensation), `adapters.py`
  - `services/tool_executor/` — `executor.py` (Sandbox Manager across four tiers, Resource Governor, Secret Injector, Egress Controller, Cost Monitor, Cleanup Guarantor), `security_adapter.py`
  - `services/llm_router/` — `pipeline.py` (the ten stages, Sanitizer, Grounding Validator, Response Cache), `router.py` (tier routing with failover), `adapters.py`, `tests/` (28 tests)
  - `services/integration_registry/` — `manifests.py` (manifest schema, capability abstractions, risk tiers, data-classification ceilings, portability, and the `ConstructionBlocked` guard), `tests/` (29 tests)
  - `services/integration_gateway/` — `gateway.py` (boundary classification enforcement, per-instance approval rule, construction block)
  - `tests/s6_integration/test_s6_exit_criterion.py` — 18 tests
  - `docs/modules/tool_platform.md`, `docs/modules/integration_platform.md`, `docs/modules/llm_router.md`
- **Files Modified:** `conftest.py`, `pyproject.toml`, `IMPLEMENTATION_JOURNAL.md`
- **Tests Added:** 104. Repository total: 601.
- **Validation Performed:**
  - `python -m pytest -q` → 601 passed
  - `python -m ruff check libs services tests` → clean; `ruff format` applied
  - `python -m mypy .` (`--strict`) → no issues in 160 source files
  - `python -m bandit -r libs services --exclude "*/tests/*"` → exit 0, zero findings
  - Coverage 97.03% against the 90% CI gate
- **Build Status:** Passing locally on every gate. Not run through CI, Poetry environments, or `docker compose`.

- **CIR-001 handling (the defining constraint of this stage):** `integration_registry` and `integration_gateway` are built to **specification-conformant, construction-blocked** status exactly as Build Spec Section 6 and Part V require, and no further. The manifest schema, capability abstraction model, risk tiers, data-classification ceilings, portability declarations and the per-instance approval rule of 17.14.1 are all implemented and genuinely enforced — that is the specification half, and the validation is real rather than decorative. Every operation constituting construction (`register`, `approve`, `activate`, `connect`, `probe_health`, `resolve` on the Registry; `resolve_abstraction`, `consume`, `provider_health`, `record_consumption`, `retire` on the Gateway) raises `ConstructionBlocked` carrying the blocker text. They raise rather than no-op deliberately: Section 24 requires this debt never to be "silently converted to Done status", and a quiet no-op would let a caller believe an integration had been activated. A parametrized test asserts every construction verb raises, so the block cannot decay as the modules are edited. **Neither module is Done and neither may be marked Done** until a Governance ruling at G3 or G4 resolves CIR-001; Section 6 rule 9 forbids resolving it by unilateral interpretation, and nothing here guesses.

- **The downstream consequence, not hidden:** 21B §19.6 has the Tool Gateway verify that a tool's declared capability abstraction is backed by an active, approved integration. Nothing can legitimately back an abstraction while construction is blocked, so `UnbackedIntegrationSource` reports every abstraction unbacked and the Tool Gateway **refuses** such tools. This means the S6 test-list clause "a registered tool **backed by an approved integration** executes..." cannot be satisfied. `tests/s6_integration/` states this in a named test (`test_a_tool_needing_an_integration_is_refused_while_cir_001_blocks`) rather than stubbing a fake integration to make the suite green. Tools that reach nothing external are unaffected and exercise the rest of the clause in full. The stage exit criterion is scoped to the unblocked modules per the Build Specification, and this is where that scoping bites.

- **Issues Encountered (four real defects, all found by tests):**
  1. **The Executor passed the consuming agent as the secret requester.** The Security Gateway correctly refused it — 14 rule 12 forbids a secret grant reaching an agent at all. 21B §19.10 makes the *Executor* the party authorized to inject, so the Executor now holds its own Service identity and injects under that. The original code would have made secret-using tools impossible to run, and for the right reason.
  2. **`InferenceResult` reported nine of ten pipeline stages.** The result was constructed before stage 10 was entered, so a response misreported its own pipeline. Stage 10 is now recorded before the result is built.
  3. **A cache hit returned the stored result verbatim**, so it carried the original request's id and claimed `cache_hit=False` — a consumer could not distinguish a cached answer from a fresh one. It now returns a copy labelled for the current request.
  4. **A test assumed the circuit breaker would gate repeated failure**; in fact trust decay bites first, because three failures out of three drop a tool below the autonomous threshold before the breaker reaches its fifth. Both protections are correct and the earlier one wins. Rather than weaken either, the test now pins the actual ordering as defence in depth, and the breaker is exercised separately in isolation where trust cannot pre-empt it.

- **Resolution:** All four resolved in-branch; each has a regression test.

- **Open Items (deferred, not silently absorbed):**
  - **No real sandbox runtime.** `Sandbox` models the four tiers and enforces the egress allowlist and the cleanup contract, but Docker, gVisor and Firecracker are not wired in. Sandbox *semantics* are implemented; sandbox *isolation* is not, and that gap is the single largest one in this stage. A sandbox escape is modelled and escalated correctly, but nothing yet prevents one.
  - **Timeout enforcement is post-hoc**, checked after the tool returns rather than interrupting it mid-flight. Real pre-emption needs the process isolation the runtime would provide.
  - **No real model backend.** `ModelBackend` is a Protocol; Ollama, vLLM and LiteLLM are not wired in. Token estimation is four-characters-per-token, not a tokenizer.
  - **Grounding validation is vocabulary overlap**, deliberately simple, and will not catch a subtle fabrication. What it enforces reliably is that an ungrounded answer never reaches the cache. The semantic cache is exact-match only.
  - `event_bus` is not wired into any S6 module for lifecycle emission (21B §19.6, §20.6).
  - Performance is unvalidated against the 21B §19.12 and §20 latency tables.
  - CIR-004 remains open and the Tool Gateway's p50 20ms authorization budget is named in 21B §19.12 as a principal input to it.

- **Commit Hash:** (pending)
- **Notes:** Section 39 status for the four unblocked modules is **implementation complete, gates pending**; for the two blocked modules it is **specification-conformant, construction-blocked**, which is a distinct status and not a step toward Done. Standing conformance guards added this stage: the Registry exposes no dispatch verb (12.6.1), the Executor exposes no authority verb (12.6.3, 12.17.4), every Integration construction verb raises, and each module's cross-subsystem imports are confined to a single adapter file. The three-way Registry/Gateway/Executor separation that 12.6 mandates is therefore enforced by test rather than by convention.

### 2026-08-24 — Stage S7: FIRST LIGHT

- **Stage:** S7 — First Light (the organizing milestone, 21A §2.2.4)
- **Modules:** `agent_runtime`, `workflow_engine`, plus the TypeScript `workflow_definitions` package
- **Work Item:** Realize documents 05, 06 and 07 per 21B §13 and §14, and satisfy the S7 exit criterion verbatim: "One registered agent executes one task inside one durable workflow, invoking one tool through the full mediation chain, with one human approval gate, one saga compensation path, and complete lineage from human authority to external effect."
- **Files Created:**
  - `services/agent_runtime/` — `identity.py` (the durable Identity Plane: lifecycle machine, the six authority boundaries of 06.9.6, manifest loader, reputation engine, drift monitor), `runtime.py` (the stateless Execution Plane), `adapters.py`, `tests/test_agent_runtime.py` (45 tests)
  - `services/workflow_engine/` — `dag.py` (workflow states, Execution DAG, Planning validation, worst-case budget), `engine.py` (trigger, plan, advance, human gates, saga compensation, replay, health), `schema.py` (single source of truth for the bilingual boundary), `adapters.py`, `tests/test_workflow_engine.py` (34 tests), `tests/test_bilingual_boundary.py` (16 tests)
  - `services/workflow_engine/workflow_definitions/` — TypeScript package: `src/contracts.ts` (generated), `src/firstLight.ts` (the authored DAG), `src/determinism.ts`, `test/firstLight.test.js` (9 tests), `package.json`, `tsconfig.json` (`strict`)
  - `tests/s7_first_light/test_first_light.py` — 7 tests, retained as the system's standing regression surface
  - `docs/modules/agent_runtime.md`, `docs/modules/workflow_engine.md`
- **Files Modified:** `conftest.py`, `pyproject.toml`, `IMPLEMENTATION_JOURNAL.md`
- **Tests Added:** 102 Python (repository total 703) plus 9 TypeScript.
- **Validation Performed:**
  - `python -m pytest -q` -> 703 passed
  - `python -m ruff check libs services tests` -> clean; `ruff format` applied
  - `python -m mypy .` (`--strict`) -> no issues in 176 source files
  - `python -m bandit -r libs services --exclude "*/tests/*"` -> zero findings
  - Coverage 97.26% against the 90% CI gate
  - `node --test test/*.test.js` -> 9 passed; `npx tsc --noEmit` clean under `strict`

- **First Light, wired for real.** The exit-criterion test stubs only two things: the model backend and the tool body, which are the two things that would otherwise reach outside the process. Everything else participates genuinely — Security authenticates and authorizes, Memory hydrates, Knowledge grounds, Decision gates, Cost meters and pre-allocates, the Tool Platform mediates with real secret injection, the LLM Router runs its ten-stage pipeline, the Runtime executes and the Engine orchestrates. The test drives: a human authorizes a Class C decision; the workflow triggers; Planning binds the agent and pre-allocates the worst-case budget; the agent executes; the workflow pauses on the human gate releasing its resources with nothing yet published; approval resumes it; the tool executes through the full mediation chain; and lineage is verified end to end from human authority to external effect.

- **The bilingual boundary.** 21B §14.4 calls this "the engine's highest-risk internal seam", because neither language's type system observes both sides. It is handled with single-source generation (`workflow_engine/schema.py` renders `contracts.ts`) plus contract tests in **both** directions. The load-bearing one is `test_the_generated_file_matches_the_generator`: without it, a hand-edit to the generated file diverges the two sides silently and the failure surfaces at runtime in a language neither type checker was watching.

- **Issues Encountered:**
  1. **A workflow whose terminal activity failed was left Running forever.** `blocked_by_failure` only finds *dependents* of a failure, and a terminal activity has none, so the run sat in Running with nothing left to dispatch and no path out. Fixed with `ExecutionDAG.has_failure()` and a post-loop check in `_advance_one`; `test_a_failing_terminal_activity_does_not_leave_the_workflow_running` pins it.
  2. **Three `assert` statements in the engine would have vanished under `python -O`** — two narrowing checks that `ExecutionDAG.build` already guarantees, and one on agent binding. All three rewritten as explicit branches raising `PlanningFailure`, so the guarantee survives optimisation.
  3. **`engine.py` imported `agent_runtime` directly** to construct an `ActivityRequest`, breaking the adapter convention. The `AgentDispatcher` protocol now takes plain fields and `adapters.py` builds the request, so the engine never names the other subsystem. Asserted by test.
  4. **The TypeScript determinism checker tripped its own rule**, because listing the forbidden patterns put them in the file being checked. Moved to `src/determinism.ts`.

- **Resolution:** All four resolved in-branch; each has a regression test.

- **Open Items (deferred, not silently absorbed):**
  - **No real Temporal server.** Durability is in-process: the journal and run records survive within the process, not across a restart. 03.3.1's named engine cannot be adopted while CIR-001 is unresolved, so `holds_resources` is a flag the engine maintains rather than a quota a substrate enforces.
  - No real model backend and no real sandbox runtime, both carried forward from S6 unchanged.
  - `event_bus` is not wired into either S7 module; signals reach Observability directly through the emitter.
  - The TypeScript definition is the authored artifact per 03.3.2, but Python holds a mirror of it to exercise the activity side. A test checks the mirror against the source; a real engine would remove the need for one.
  - Performance is unvalidated against the 21B §13.12 and §14.12 latency tables.

- **Commit Hash:** (pending)
- **Notes:** Standing conformance guards added this stage: the Runtime exposes no scheduling verb (02.3.2), the Engine exposes no execution verb (07.13.1), an agent may not review its own output (06 rules 16, 17), the six authority boundaries intersect rather than union (06.9.6 with 14.12.4), a paused workflow never appears as holding resources (07.14.5), a failed compensation Stalls rather than Failing, and each module's cross-subsystem imports are confined to a single adapter file. `tests/s7_first_light/` is retained permanently as the standing regression surface, exactly as 21B and the Build Specification intend.
