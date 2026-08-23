# Agent OS — Implementation Journal

## Project Status

- **Current Stage:** S2 — Truth (implementation complete, gates pass locally)
- **Current Module:** none in progress — S2 exit criterion met; next executable work item is Stage S3 (`observability_gateway` ingestion profile, `cost_manager`)
- **Repository Status:** Layer 0 substrate plus the Trust and Truth planes implemented and tested
- **Overall Progress:** 6 / 26 modules implemented to their stage exit criteria (`kernel`, `core`, `persistence`, `schema_registry`, `security_gateway`, `event_bus`); 0 / 26 at full Definition-of-Done — Section 39 criterion 2 (Conformance Gates) still requires the CI pipeline to actually execute, and Poetry-managed reproducible builds and `docker compose up` do not exist yet

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
