# 22_CLAUDE_CODE_BUILD_SPECIFICATION.md

**Agent OS — Claude Code Build Specification**
**Version:** 1.0.0
**Status:** Engineering Execution Handbook — Derived Exclusively From Ratified Architecture
**Classification:** Non-Architectural — Deterministic Engineering Execution Plan
**Authority:** 20A, 20B, 20C (Constitutional Manifests) · 21A, 21B, 21C (Implementation Architecture) — the six ratified inputs. This document introduces no architecture, no module, no API, and no code. Every clause traces to one of the six inputs or is explicitly marked `[Engineering Decision]`.

---

## Part I — Engineering Execution Philosophy

### 1. Purpose

This document converts the ratified Agent OS architecture (documents 01–19, compressed into 20A/20B/20C, and elaborated into implementation architecture in 21A/21B/21C) into a deterministic sequence of engineering work that Claude Code can execute without redesigning, reinterpreting, or extending the architecture. It answers exactly one recurring question at every point in the build: **what should Claude Code build next, against what interface, verified by what test, gated by what criterion.**

### 2. Scope

In scope: repository bootstrap, the 26-module build sequence (S0–S12), working rules for how Claude Code performs the work, engineering gates per stage, and final build-readiness criteria. Out of scope: any change to module responsibility, dependency direction, data ownership, or constitutional rule. Where the six input documents are silent, incomplete, or internally contested, this document says so explicitly (Section 6) rather than inventing a resolution.

### 3. Engineering Principles

- **Traceability over invention.** Every module, interface, and test built must cite the 21B section (or 20A/20B/20C rule) it realizes. If no citation exists, the work item does not belong in this plan.
- **Depth-first construction.** No stage begins with a stub dependency. A module is either Done (Part V, Section 39 criteria) or not started; there is no partial-credit state that unblocks dependents.
- **First Light early.** The system reaches an end-to-end, human-authorized, tool-executing, auditable request path (Stage S7) as soon as the dependency graph permits — not as a late integration afterthought.
- **Constitution over convenience.** Where a working rule in Part IV would conflict with a Non-Violable Rule in 20A/20B/20C, the Non-Violable Rule wins, unconditionally.
- **Explicit gaps over silent gap-filling.** Where the ratified architecture is incomplete (the truncated `09_MEMORY_OPERATING_MODEL`) or self-contradictory (the CIR-series conflicts identified in 21A/21C), Claude Code stops and escalates rather than resolving the conflict by implementation fiat.
- **Binary Definition of Done.** Per 21C §39, a module is Done only when all five criteria in Section 39 of this document hold simultaneously. "Mostly working" is not a build state.

### 4. Relationship to the Constitution

Documents 01–19 (compressed in 20A/20B/20C) are binding on all runtime and agent behavior. This build specification does not alter, weaken, or reinterpret any Non-Violable Rule enumerated in those documents. Every stage gate in Part V includes a constitutional-traceability check for this reason. Where this document describes a working process (e.g., commit strategy, branch strategy) that the constitution does not address, that process is engineering scaffolding, not constitutional content, and may be revised without constitutional amendment.

### 5. Relationship to the Implementation Architecture

Documents 21A (Core), 21B (Subsystems), and 21C (Delivery) are the ratified implementation architecture: the 26-module structure, the 14-level dependency graph, the Gateway Pattern, the per-subsystem interface contracts, and the S0–S12 build stage sequence all originate there. This document does not add modules, does not reorder the dependency graph, and does not redefine any interface. It sequences engineering activity — repository scaffolding, test-writing order, review checkpoints — around the structure 21A/21B/21C already ratified.

### 6. Rules Claude Code Must Never Violate

1. Must not introduce a module, service, or component not named in 21A/21B/21C.
2. Must not move a responsibility, data store, or interface from the module 21B assigns it to.
3. Must not create a direct dependency edge prohibited by the 14-edge catalogue (21A §9.4.4; reproduced in Section 10.4 below).
4. Must not build Integration Registry/Gateway, Deployment Registry/Gateway, or Evolution Gateway beyond specification-conformant, construction-blocked status while CIR-001 is unresolved (Section 6, Part VI).
5. Must not fabricate content for the truncated `09_MEMORY_OPERATING_MODEL` sections (10.1–30, including its Non-Violable Rules and Glossary). Any Memory Gateway work touching those sections must cite the gap and proceed only on the provisional, explicitly-marked-provisional basis 21B §16.12 already establishes.
6. Must not mark a module "Done" on partial completion of the Section 39 checklist.
7. Must not deploy code without tests, per Non-Violable Rule 16 (01_PRINCIPLES) and Appendix A Rule 8 (02_ARCHITECTURE) — no exceptions, ever.
8. Must not hardcode secrets, bypass the Tool Registry/Gateway/Executor separation, bypass the Event Bus for inter-service communication, or introduce any technology on the Prohibited Technologies list (Section 11).
9. Must not resolve a CIR-series conflict (Section 6) by choosing an interpretation unilaterally; must escalate for a Governance ruling or human decision instead.
10. Must not build breadth-first across dependency levels; must complete a level's modules before advancing (21_PLAN §4.2 Rule 1).

---

## Part II — Repository Bootstrap

### 7. Stage 0 — Repository Initialization

Stage 0 produces an empty-but-scaffolded monorepo capable of running `docker compose up` to a healthy state with zero services beyond the Layer 0 substrate. Work items:

1. Initialize a single monorepo (03_TECH_STACK mandates a monorepo; no polyrepo split for core services).
2. Establish trunk-based development: `main` branch, no long-lived feature branches, no direct pushes to `main` (03 Non-Violable Rule, body text).
3. Install and verify pre-commit hooks (`pre-commit install` mandatory for all contributors, per 03 body text).
4. Establish the CI pipeline skeleton (GitHub Actions) with placeholder jobs for lint, type-check, unit test, and security scan — populated as modules land, not before.
5. Establish the Makefile / task-runner entrypoints for common developer operations (build, test, lint, up, down).

**[Engineering Decision]** Repository directory layout under the monorepo root (`services/`, `libs/`, `infra/`, `docs/`) is not specified verbatim in 21A/21B/21C beyond module names; this build specification adopts one `services/<module_name>/` directory per deployable module and one `libs/<lib_name>/` directory per shared library (kernel, core, persistence), matching the 26-module inventory in Section 9 exactly. This is a directory-naming convenience, not an architectural claim.

### 8. Development Environment

- `docker compose up` from a clean clone must produce a fully functional local environment (03 body text, binding).
- Local development uses Ollama for inference; production uses vLLM (03 canonical stack) — both must be selectable via the LLM Router's configuration, never hardcoded per-environment in application code.
- Environment configuration is pull-based with push-notified invalidation `[Implementation Decision, 21C §30.4]`.

### 9. Toolchain

Bind exactly to the canonical stack table in 20A (03_TECH_STACK), reproduced here for engineering reference:

| Layer | Technology | Layer | Technology |
|---|---|---|---|
| Primary Language | Python 3.11.9+ (3.12.x permitted) | Vector / Graph | pgvector 0.7.0+ / Apache AGE 1.5.0+ |
| Workflow Definition Language | TypeScript 5.4+ / Node.js 20 LTS | Cache/Events/Locks | Redis 7.2+ (Streams as Event Bus) |
| Infrastructure Language | HCL — Terraform 1.7+ / OpenTofu 1.6+ | Workflow Engine | Temporal Server 1.22.x (PostgreSQL persistence) |
| Web Framework | FastAPI 0.111.0+ | LLM Abstraction | LiteLLM Proxy 1.40.0+ |
| Validation | Pydantic v2 2.7.0+ | Inference | Ollama 0.1.38+ (dev) / vLLM 0.5.0+ (prod) |
| ORM / Migrations | SQLAlchemy 2.0.30+ / Alembic 1.13.0+ | Structured LLM Output | Instructor 1.3.0+ |
| HTTP Client/Server | HTTPX 0.27.0+ / Uvicorn 0.30.0+ | Embeddings | sentence-transformers 3.0.0+, `nomic-embed-text` |
| Frontend | React 18.3.1+, Vite 5.2+, Tailwind 3.4+, TanStack Query 5.0+, Radix UI, Zustand | Containerization/Sandboxing | Docker 25.0+, gVisor runsc, Firecracker 1.7.0+, Trivy, seccomp |
| Primary Database | PostgreSQL 16.3+ with PgBouncer 1.22+ | Production Default | Docker Swarm (Kubernetes optional), Traefik 3.0+ |

Testing: pytest 8.2+, TestContainers 4.5+, Pact 2.2+ (contract), Hypothesis 6.100+ (property-based), Playwright 1.44+ (E2E). Code quality: Ruff 0.4.0+, mypy 1.10.0+ (`--strict`, zero errors, non-negotiable per 03 Appendix B Rule 2). Security: Bandit, Semgrep, pip-audit, Trivy, git-secrets. Secrets: Docker Secrets (Swarm) or Vault + External Secrets Operator (K8s). Observability: structlog 24.1+, Prometheus 2.52+, Grafana 11.0+, Loki 3.0+, Tempo 2.4+, Alertmanager 0.27+, OpenTelemetry 1.25+. Packaging: Poetry 1.8.0+ (Python; no `requirements.txt` in production services), npm 10+ / tsup 8.0+ (TypeScript).

No technology outside this table may be introduced into core services without a Technology Amendment Proposal (03, 10-step process). This includes the Prohibited Technologies list in Section 11.

### 10. Monorepo Structure

Structure follows the 26-module inventory (Section 9 of Part III) directly. No module directory may import another module's internal (non-interface) code, per the Module Ownership Rules (21A §7.3–7.4): exclusive ownership of domain model, data store, journal, interfaces, signal contract, migrations, and runbook per module; no cross-module database or domain-internals access.

### 11. Dependency Management

- Python: Poetry, one `pyproject.toml` per deployable module plus shared libs; lockfiles committed.
- TypeScript (workflow definitions only, per 03's bilingual split — Python for activities, TypeScript for Temporal workflow definitions): npm with committed lockfiles.
- Dependency versions pinned to the canonical stack table (Section 9); no `latest` tags anywhere, including Docker base images (pinned to digest or specific version, 03 Non-Violable Rule 13).
- **Prohibited technologies** (03, binding on core; narrow plugin/utility exceptions noted): LangChain (orchestration — utility functions only), LlamaIndex (core — reference only), Django, Flask, Celery (workflows — simple background tasks only), MongoDB, Pinecone/Weaviate/Qdrant (core — plugin only), Neo4j (core — plugin only), AWS Lambda/GCP Cloud Functions, Firebase/Supabase (core).
- **Prohibited licenses** in core: GPL-3.0, AGPL-3.0, SSPL, proprietary/commercial without a written exception and ADR.
- Dependency scanning (pip-audit, Trivy) runs in CI on every change; a vulnerable or license-incompatible dependency blocks merge.

### 12. Shared Libraries Bootstrap

Three shared libraries form Layer 0 alongside the `schema_registry` deployable and must be built first, in this order, before any deployable module:

1. **`kernel`** — an implementation artifact with no constitutional standing in its own right, but the load-bearing substrate for every Gateway's nine universal mechanisms (21A §5.2): Artifact Identity, Lifecycle State Machine engine, Boundary Enforcement engine (six boundaries: Tenant, Scope, Authority, Confidence, Budget, Temporal), Immutable Journal, Confidence/Authority Resolution, Failure Classification (5-category, 60-second bound), Panic Protocol participation, Signal Emission contract, Category 1 Incident escalation, Isolation context propagation.
2. **`core`** — shared domain models, event schemas, exceptions, and constants (realizes 02.14).
3. **`persistence`** — hexagonal ports-and-adapters layer for all data access (realizes 01.7.1, 02.7).
4. **`schema_registry`** (deployable, but Layer 0) — the schema validation and versioning service every event producer and Gateway consults before emission (realizes 08.16.1, 10.16.2, 12.7.3).

Exit criterion for Stage 0 / Layer 0: a "Synthetic Gateway" built purely on top of `kernel`, `core`, and `persistence` passes conformance tests for identity shape, lifecycle guard enforcement, journal immutability, boundary enforcement, failure classification, and Panic Protocol participation — proving the substrate is sound before any real Gateway is built on it (21_PLAN §4.1, Stage S0 exit criterion).

### 13. Constitutional Kernel Bootstrap

"Constitutional kernel" here refers to the Trust and Truth planes — `security_gateway` (Stage S1) and `event_bus` (Stage S2) — which every other module depends on either directly or transitively. These are built immediately after Layer 0 and before any business-logic subsystem (memory, knowledge, decision, tool, agent, workflow). This ordering is explicit and non-negotiable in 21_PLAN §4.2 Rule 2: "Trust (Security) and Truth (Event Bus) before everything."

---

## Part III — Incremental Build Plan

The build plan below is the 21_PLAN/21C Stage sequence (S0–S12), unmodified. Each stage lists Goal, Why It Exists, Prerequisites, Modules, Files to Create (directory-level, per the Section 10 layout), Interfaces to Expose, Tests to Write, Validation Criteria, Definition of Done, Exit Criteria, and What Becomes Unblocked. Interface field lists are reproduced only where 21A/21B state them explicitly; anything not stated is left unspecified rather than invented.

### Stage S0 — Kernel & Contracts

- **Goal:** Stand up the substrate (`kernel`, `core`, `persistence`, `schema_registry`) that every one of the 11 Gateways will build on.
- **Why it exists:** All nine universal Gateway mechanisms (identity, lifecycle, boundary enforcement, journal, confidence/authority resolution, signal emission, self-audit, Panic participation, mediation contract) are factored here once rather than reimplemented per-Gateway (21A §5.2, §7).
- **Prerequisites:** None — this is the root of the build.
- **Modules:** `kernel`, `core`, `persistence`, `schema_registry`.
- **Files to create:** `libs/kernel/`, `libs/core/`, `libs/persistence/`, `services/schema_registry/` — each with its own `pyproject.toml`, domain module, and test directory per Section 10.
- **Interfaces to expose:** The Artifact Identity shape, Lifecycle State Machine engine API, Boundary Enforcement engine API, Immutable Journal write/append API — consumed internally by every subsequent Gateway; no external interface yet since no Gateway exists to call one.
- **Tests to write:** Unit tests for identity shape validation, lifecycle guard transitions, journal append-only enforcement (attempted mutation must fail), boundary-check enforcement for each of the six boundary types, failure classification timing (must classify within 60 seconds), Panic Protocol participation hook.
- **Validation criteria:** A "Synthetic Gateway" — a minimal test harness built only on `kernel`/`core`/`persistence` — exercises every mechanism above and passes.
- **Definition of Done:** Section 39 checklist, all five criteria, applied to `kernel`, `core`, `persistence`, `schema_registry` individually.
- **Exit criteria:** Synthetic Gateway conformance tests pass (21_PLAN §4.1, S0).
- **What becomes unblocked:** Stage S1 (`security_gateway`), and transitively every subsequent module, since all inherit the Layer 0 substrate.

### Stage S1 — Trust

- **Goal:** Build `security_gateway`, realizing constitutional document 14 in full.
- **Why it exists:** Per 21_PLAN §4.2 Rule 2, Trust precedes everything else — no principal can be authenticated, authorized, or delegated to until this exists, and every later Gateway's Boundary Enforcement depends on Security Gateway's authority resolution.
- **Prerequisites:** Stage S0 complete (Layer 0 substrate).
- **Modules:** `security_gateway`.
- **Files to create:** `services/security_gateway/` with identity registry, credential issuance, authorization engine, delegation manager, revocation handler, and Security Event Journal submodules.
- **Interfaces to expose (21B, Security Gateway Public Interfaces):** Authentication, Authorization, Identity Registration, Delegation Management, Revocation Command, Secret Reference Resolution, Security Context, Security Event Journal Query, Security Health.
- **Tests to write:** Principal registration, authentication issuing a scoped token, authorization checks enforcing the **Permission Intersection Rule** (14.12.4 — effective permission is the intersection, not the union, of all applicable sources), delegation grant and expiry, revocation with cascade (all downstream delegated grants revoked), tamper-evidence test on the Security Event Journal (attempted retroactive edit must fail cryptographic chain verification).
- **Validation criteria:** A principal can register, authenticate, receive a scoped token, be authorized against a resource, be delegated to, and be revoked with cascading effect; the Security Event Journal resists tampering.
- **Definition of Done:** Section 39 checklist for `security_gateway`.
- **Exit criteria:** All items in the prior bullet demonstrated end-to-end (21_PLAN §4.1, S1 exit criterion).
- **What becomes unblocked:** Stage S2 (`event_bus`), which depends only on Trust Plane + Layer 0.

**Note on transport binding:** Security Gateway writes its journal directly to `persistence`, not through the Event Bus (resolving the Security ↔ Event Bus circular dependency per 21_PLAN §1.2) — this ordering is what makes building Security before the Event Bus possible at all.

### Stage S2 — Truth

- **Goal:** Build `event_bus`, realizing constitutional document 08 in full plus 02.3.4.
- **Why it exists:** Truth (the Event Bus) is the second load-bearing plane per 21_PLAN §4.2 Rule 2 — all later inter-service coordination is event-mediated, never direct.
- **Prerequisites:** Stage S1 complete.
- **Modules:** `event_bus`.
- **Files to create:** `services/event_bus/` with stream management, consumer group registry, schema validation hook (calling `schema_registry`), replay engine, and dead-letter handling.
- **Interfaces to expose (21B):** Event Emission, Consumer Group Registration, Event Consumption, Replay Request, Dead Letter Query, Stream Health.
- **Tests to write:** Authenticated producer emits a schema-validated event; unregistered event type is rejected at emission; at-least-once delivery to a consumer group; causal ordering within a stream holds (Causation ID / Correlation ID propagation); replay reconstructs history without mutating business state; after 10 failed delivery attempts, an event moves to the Dead-Letter Stream and triggers an alert.
- **Validation criteria:** All of the above hold under integration test with `security_gateway` providing authentication.
- **Definition of Done:** Section 39 checklist for `event_bus`.
- **Exit criteria:** 21_PLAN §4.1 S2 exit criterion — authenticated producers emit schema-validated events; at-least-once consumer groups function; causality holds; replay works; dead-lettering alerts fire.
- **What becomes unblocked:** Stage S3 (`observability_gateway` ingestion profile, `cost_manager`) — Level 3 in the dependency graph.

**Note:** `[Engineering Decision, 21C §29.4]` interfaces are schema-first: the Event structure (event_id UUIDv7, trace_id, timestamp, schema_version, event_type, source, tenant_id, payload, metadata) is defined in a shared schema format and validated at build time on both producer and consumer sides before any handler code is written.

### Stage S3 — Instrumentation & Economics

- **Goal:** Build `observability_gateway` (ingestion-only profile) and `cost_manager`.
- **Why it exists:** Every subsequent module's Signal Emission (a mandatory Gateway mechanism, 21A §5.2 item 7) needs somewhere to land; every subsequent module's budget enforcement needs `cost_manager` operational first.
- **Prerequisites:** Stage S2 complete.
- **Modules:** `observability_gateway` (ingestion-only profile — full interpretive profile deferred to S10), `cost_manager`.
- **Files to create:** `services/observability_gateway/` (ingestion submodule only at this stage), `services/cost_manager/`.
- **Interfaces to expose:** Signal ingestion endpoint (consumed by all Gateways per the universal Signal Emission mechanism); Budget Check, Budget Enforcement, Circuit Breaker trip/reset (cost_manager, realizing 02.3.9).
- **Tests to write:** Every signal type is ingested, enriched, and journaled; budget checks correctly gate pre-flight and post-flight operations at the four levels (Green <50%, Yellow 50–80%, Orange 80–95% forces model downgrade, Red >95% halts operations and escalates to human); circuit breakers trip on repeated external-call failure.
- **Validation criteria:** As above, demonstrated end-to-end against a synthetic caller.
- **Definition of Done:** Section 39 checklist for both modules.
- **Exit criteria:** 21_PLAN §4.1 S3 exit criterion.
- **What becomes unblocked:** Stage S4 (`memory_gateway`, `knowledge_gateway`).

### Stage S4 — Cognition

- **Goal:** Build `memory_gateway` and `knowledge_gateway`.
- **Why it exists:** Realizes document 09 (Memory — **note: source is truncated, see Section 6 gap G1**) plus 02.3.5, and document 10 (Knowledge) in full.
- **Prerequisites:** Stage S3 complete.
- **Modules:** `memory_gateway`, `knowledge_gateway`.
- **Files to create:** `services/memory_gateway/`, `services/knowledge_gateway/`.
- **Interfaces to expose:** Memory tier access (Working/Long-Term/Vector/Knowledge Graph/Cold, per the tier hierarchy in 02); Knowledge extraction, validation, promotion, decay, and cross-business pollination interfaces per document 10.
- **Tests to write:** Experience formation, validation, linkage, and decay (memory); belief extraction, validation, promotion, and revalidation with confidence-band enforcement (Knowledge Gateway's stated 0.60/0.80/0.95 thresholds); reconciliation of conflicting beliefs.
- **Validation criteria:** As above.
- **Definition of Done:** Section 39 checklist — **with an explicit caveat for `memory_gateway`**: its Performance Characteristics are provisional, derived from Knowledge Gateway's published budgets per `[Implementation Decision, 21B §16.12]`, pending recovery of the truncated Document 09 source. This caveat does not block Done status but must be recorded in the module's Journal entry as an open item.
- **Exit criteria:** 21_PLAN §4.1 S4 exit criterion.
- **What becomes unblocked:** Stage S5 (`decision_gateway`).

### Stage S5 — Authority

- **Goal:** Build `decision_gateway`, realizing document 11 in full.
- **Why it exists:** No Class A–D commitment (the decision-authority mechanism binding every subsequent action) can be recorded, verified, or reversed until this exists.
- **Prerequisites:** Stage S4 complete.
- **Modules:** `decision_gateway`.
- **Files to create:** `services/decision_gateway/`.
- **Interfaces to expose (21B):** Decision Proposal, Decision Verification, Approval Response, Standing Order Management, Reversal Request, Outcome Report, Decision Journal Query, Decision Health.
- **Tests to write:** Class A–D commitments with options and evidence grounding; authority resolution by decision class and autonomy level; **structural** enforcement that Level 3/4 (Class C/D) approval gates never auto-approve on timeout (built by construction, not configuration); reversal with compensation; supersession with lineage tracking.
- **Validation criteria:** As above, including an adversarial test attempting to force an auto-approval on a Class D decision — must fail.
- **Definition of Done:** Section 39 checklist for `decision_gateway`.
- **Exit criteria:** 21_PLAN §4.1 S5 exit criterion.
- **What becomes unblocked:** Stage S6 (Integration/Tool/LLM Router triad).

### Stage S6 — Effect

- **Goal:** Build `integration_registry`/`integration_gateway`, `tool_registry`/`tool_gateway`/`tool_executor`, and `llm_router`.
- **Why it exists:** Realizes document 12 (Tool) in full with its mandatory three-way Registry/Gateway/Executor separation, document 17 (Integration), and 02.3.8 plus the 10-stage prompt pipeline (02.8.5) for `llm_router`.
- **Prerequisites:** Stage S5 complete.
- **Modules:** `integration_registry`, `integration_gateway`, `tool_registry`, `tool_gateway`, `tool_executor`, `llm_router`.
- **Files to create:** One `services/` directory per module, six total.
- **Interfaces to expose (21B):** Tool Discovery/Registration/Health Query (Registry); Tool Invocation/Compensation Invocation/Invocation Record Query (Gateway); Integration Discovery/Registration (Registry); Abstraction Resolution/Capability Consumption (Gateway); Inference Request/Model Tier Health (LLM Router). The three-party **Invocation Contract** (12.17, 21B §19.4) — Idempotency Key, Decision Reference, Capability Request, Context Package, Cost Ceiling, Timeout, Compensation Reference, Attribution Chain — recorded immutably before dispatch.
- **Tests to write:** A registered tool backed by an approved integration executes in its declared sandbox tier (None/Container/gVisor/Firecracker) under a committed decision, within its cost ceiling, with validated output and a working compensation path; Tool Gateway rejects invocation attempts that bypass the Registry; direct tool-to-tool invocation is rejected (prohibited edge #6, Section 10.4).
- **Validation criteria:** As above, end-to-end.
- **Definition of Done:** Section 39 checklist per module — **with the explicit exception in Section 6 / Part VI**: `integration_registry`/`integration_gateway` reach only "specification-conformant, construction-blocked" status while CIR-001 (technology-naming conflict) is unresolved; do not mark them fully Done. `tool_registry`/`tool_gateway`/`tool_executor` and `llm_router` are not CIR-001-blocked and proceed to full Done status normally.
- **Exit criteria:** 21_PLAN §4.1 S6 exit criterion, scoped to the unblocked modules.
- **What becomes unblocked:** Stage S7 (First Light).

### Stage S7 — FIRST LIGHT (Milestone)

- **Goal:** Build `agent_runtime` and `workflow_engine`, and demonstrate the first true end-to-end request path.
- **Why it exists:** This is "the organizing milestone" (21A §2.2.4): the earliest point at which a request can traverse Agent Runtime → Workflow Engine → Event Bus → a minimal Gateway chain without every subsystem being complete. Per 21_PLAN §4.2 Rule 3, First Light is deliberately sequenced early (S7, not S12).
- **Prerequisites:** Stage S6 complete (at minimum the non-CIR-001-blocked modules).
- **Modules:** `agent_runtime` (realizes 05, 06, 02.3.2), `workflow_engine` (realizes 07 in full, 02.3.3).
- **Files to create:** `services/agent_runtime/`, `services/workflow_engine/` — the latter split per the bilingual mandate (03.3.1/03.3.2): TypeScript for Temporal workflow definitions, Python for activity implementations, with contract tests exercising every activity contract from the orchestration side.
- **Interfaces to expose (21B):** Activity Execution, Agent Discovery, Agent Registration, Lifecycle Command, Agent Health Query (Agent Runtime); Workflow Trigger, Workflow Signal, Workflow Query, Workflow Health, Definition Registration (Workflow Engine).
- **Tests to write:** One registered agent executes one task inside one durable workflow, invoking one tool through the full mediation chain (Decision → Tool Gateway → Tool Executor), gated by one human approval, with one working saga compensation path, producing complete lineage from human authority to external effect and back into the Journal.
- **Validation criteria:** The above scenario runs successfully and is independently traceable end-to-end through the Journal.
- **Definition of Done:** Section 39 checklist for both modules, plus the First Light scenario test passing.
- **Exit criteria:** 21_PLAN §4.1 S7 exit criterion — quoted: "One registered agent executes one task inside one durable workflow, invoking one tool through the full mediation chain, with one human approval gate, one saga compensation path, and complete lineage from human authority to external effect."
- **What becomes unblocked:** Stage S8 (Human Plane). Also serves as the system's first genuine integration-test surface for all downstream regression testing.

### Stage S8 — Human Plane

- **Goal:** Build `api_gateway` and `human_interface`.
- **Why it exists:** Realizes 02.3.1 (API Gateway) and consolidates human-plane requirements scattered across 05.18, 11.18, 13.33, 16.25, 17.31, 18.35, 19.36 into a single interface layer.
- **Prerequisites:** Stage S7 complete.
- **Modules:** `api_gateway`, `human_interface`.
- **Files to create:** `services/api_gateway/`, `services/human_interface/`.
- **Interfaces to expose:** External ingress with auth/authz delegated to Trust Plane, rate limiting per tenant/user/key, URI-path versioning, cursor-based pagination (offset pagination prohibited, 03 Rule 23), mandatory `Idempotency-Key` header on mutating endpoints (03 Rule 24).
- **Tests to write:** Operators can approve pending decisions, override agent actions, receive batched (not spammed) digests, and invoke the Panic Protocol; Panic Protocol halts all autonomous activity within the constitutionally mandated 5-second bound.
- **Validation criteria:** As above, including a timed test asserting the 5-second Panic Protocol bound.
- **Definition of Done:** Section 39 checklist for both modules.
- **Exit criteria:** 21_PLAN §4.1 S8 exit criterion.
- **What becomes unblocked:** Stage S9 (`learning_gateway`).

### Stage S9 — Adaptation

- **Goal:** Build `learning_gateway`, realizing document 13 in full.
- **Prerequisites:** Stage S8 complete.
- **Modules:** `learning_gateway`.
- **Files to create:** `services/learning_gateway/`.
- **Tests to write:** Outcomes attributed correctly; patterns abstracted into proposals; proposals validated, consolidated, propagated, adopted, and measured through to confirmation or refutation; a dedicated **adversarial** test for the Recursion Guard (21B §21.3) attempting genuine self-referential learning input, verifying fail-closed behavior is actually exercised, not merely asserted (21C §38.5).
- **Validation criteria:** As above.
- **Definition of Done:** Section 39 checklist for `learning_gateway`.
- **Exit criteria:** 21_PLAN §4.1 S9 exit criterion.
- **What becomes unblocked:** Stage S10 (`governance_gateway`, `observability_gateway` full profile).

### Stage S10 — Oversight

- **Goal:** Build `governance_gateway` and upgrade `observability_gateway` to its full interpretive profile.
- **Why it exists:** Realizes document 15 (Governance) in full and completes document 16 (Observability), which appears twice in the dependency graph by design — ingestion-only at Level 3, full interpretive profile here at Level 12.
- **Prerequisites:** Stage S9 complete.
- **Modules:** `governance_gateway`, `observability_gateway` (full profile upgrade).
- **Tests to write:** Policy hierarchy enforcement; compliance assessment; drift detection and quantification; interpretation ratification; meta-oversight operating correctly — including the rule that no subsystem may self-certify its own compliance (15.6.1) and that Governance can assemble evidence directly from subsystem journals (15.7.2, resolving the Governance ↔ Observability circular dependency).
- **Validation criteria:** As above.
- **Definition of Done:** Section 39 checklist for both modules.
- **Exit criteria:** 21_PLAN §4.1 S10 exit criterion.
- **What becomes unblocked:** Stage S11 (Deployment).

### Stage S11 — Territory

- **Goal:** Build `deployment_registry`/`deployment_gateway`.
- **Why it exists:** Realizes document 18. Sequenced late deliberately — per `[Implementation Decision, 21C §35.4]`, CIR-001-blocked subsystems are placed at the latest stages regardless of pure dependency-graph position, to minimize schedule risk from the unresolved blocker. This is also why Deployment's runtime bootstrap position (third, per 18.33.2) does not match its build position (last-but-one) — see the explicit warning in Section 6 / Part VI.
- **Prerequisites:** Stage S10 complete.
- **Modules:** `deployment_registry`, `deployment_gateway`.
- **Tests to write:** Environment registration, validation, promotion; isolation by fault domain and locality; continuity/recovery drills; reproducible bootstrap.
- **Validation criteria:** As above, to the extent construction is unblocked (Section 6 / Part VI governs whether full construction may proceed).
- **Definition of Done:** "Specification-conformant, construction-blocked" unless/until CIR-001 is resolved by Governance ruling; full Done status otherwise.
- **Exit criteria:** 21_PLAN §4.1 S11 exit criterion, scoped to whatever is unblocked.
- **What becomes unblocked:** Stage S12.

### Stage S12 — Transformation & Extension

- **Goal:** Build `evolution_gateway` and `plugin_manager`.
- **Why it exists:** Realizes document 19 (Evolution — CIR-001-blocked, and the deepest/last-built module by design) and 02.3.10/01.18.2 (Plugin Manager).
- **Prerequisites:** Stage S11 complete.
- **Modules:** `evolution_gateway`, `plugin_manager`.
- **Tests to write:** Amendments packaged and ratified (Evolution packages but does not present — a unidirectional handoff to Governance per 19.16.2, resolving the Evolution ↔ Governance circular dependency); experiments bounded and reversible; plugins discovered, sandboxed, and lifecycle-managed correctly.
- **Validation criteria:** As above, to the extent construction is unblocked.
- **Definition of Done:** "Specification-conformant, construction-blocked" for `evolution_gateway` unless/until CIR-001 resolves; full Done status for `plugin_manager`, which is not CIR-001-blocked.
- **Exit criteria:** 21_PLAN §4.1 S12 exit criterion, scoped accordingly.
- **What becomes unblocked:** Nothing further in the dependency graph — S12 is the terminal stage. Completion of all non-blocked modules across S0–S12 constitutes the complete ratified implementation, modulo the CIR-series exceptions catalogued in Section 6.

---

## Part IV — Claude Code Working Rules

### 14. Maximum Implementation Size Per Iteration

**[Engineering Decision]** One module-level work item per iteration (e.g., one Gateway's Public Interface implementation, or one interface's contract test suite) — not an entire Stage, and not an entire module's full internal architecture in a single pass. This keeps each iteration reviewable against a single 21B section and a single Section 39 checklist.

### 15. Commit Strategy

Small, atomic commits scoped to one interface, one test suite, or one bug fix each. Commit messages cite the constitutional/implementation-architecture section realized (e.g., "Implement Decision Proposal interface, realizes 21B §18.5 / document 11"). No commit may introduce code without a corresponding test in the same or an immediately following commit — per Non-Violable Rule 16, untested code is never an acceptable interim state, even mid-branch.

### 16. Branch Strategy

Trunk-based development (03 body text, binding): short-lived branches per work item, merged to `main` frequently. No long-lived feature branches spanning multiple Stages. No direct pushes to `main`.

### 17. Refactoring Policy

Refactoring within a module's already-Done implementation is permitted only to fix a defect or satisfy a newly discovered test gap — never to redesign the module's responsibility or interface, which would require revisiting 21B (out of scope for Claude Code per the governing instructions). Cross-module refactors that would change a dependency edge are prohibited outright.

### 18. Testing Policy

Every module implements all three mandatory testing levels before being marked Done (21C §38.3): unit tests (internal architecture, 21B §X.4), integration tests (per dependency edge, verifying the Public/Consumed Interface contracts of 21B §X.5–§X.6), and end-to-end tests (across the First Light chain and beyond). Failure-domain tests are mandatory for every module (21C §38.4) — a Failure Domains table asserted in 21B without a corresponding test is treated as an unacceptable gap, not an acceptable omission. Recursion Guards (Learning, Evolution) require adversarial tests specifically (21C §38.5), not just happy-path coverage.

### 19. Review Policy

**[Engineering Decision]** Every module's Done submission is reviewed against the Conformance Gates in Section 37/Part V before merge to `main`: constitutional traceability, cross-cutting pattern conformance, interface contract validation, authorization enforcement, and instrumentation conformance. Constitutional-traceability accuracy and architectural fidelity are reviewed manually; schema validation, authorization scaffolding, and instrumentation scaffolding are automated in CI (21C §37, matching its stated split of mechanically-checkable vs. manually-reviewed gates).

### 20. Documentation Policy

Every module ships MkDocs-compatible documentation (03 canonical stack) including its OpenAPI/interface spec (Redoc-rendered) and an architecture note citing the 21B section it realizes. Diagrams use ASCII or Mermaid per 03.

### 21. Migration Policy

All schema changes go through Alembic migrations (03 Non-Violable Rule 8) — no direct schema changes. Event schema evolution follows the versioning rules in document 08: minor versions are additive-only; major versions are breaking and require a migration plan plus a minimum one-release-cycle deprecation period.

### 22. Error Correction Workflow

On test failure or defect discovery: classify the failure within 60 seconds per the universal Failure Classification mechanism (Transient, Degradable, Critical, Security, Financial); apply the corresponding response (retry with backoff, degrade, halt-and-escalate, isolate, or freeze budget respectively — per 04's Failure Handling Philosophy); log the classification and resolution to the module's Journal; do not silently retry past the classification without recording it (silent failures are prohibited system-wide).

### 23. Rollback Workflow

No deployment proceeds without a tested rollback procedure (03 Non-Violable Rule 25). Compensation activities (for workflows) and reversal requests (for decisions) must be exercised in test before a module reaches Done status — not assumed to work because the interface exists.

### 24. Technical Debt Policy

**[Engineering Decision]** Technical debt introduced under the "specification-conformant, construction-blocked" status (Integration, Deployment, Evolution modules under CIR-001) is tracked explicitly as open items in each module's Journal entry, distinct from ordinary technical debt, and must never be silently converted to Done status without a recorded Governance ruling resolving CIR-001. All other technical debt is tracked and must be resolved before the owning module is marked Done — Done is binary (Section 39), so debt cannot be deferred past that point for a module claiming Done status.

### 25. Architectural Compliance Verification

Before any module is marked Done, verify: (a) no prohibited dependency edge (Section 10.4) has been introduced; (b) no module reads or writes another module's data store; (c) the Registry-Gateway separation is intact wherever the constitution requires it (Tool, Integration, Deployment); (d) all nine universal Gateway mechanisms are implemented where the module is a Gateway; (e) the module's interface matches its 21B Public/Consumed Interface table exactly, with no undocumented additions.

### 26. Autonomous Limits

**[Engineering Decision]** In executing this build specification autonomously (see Appendix — Claude Code Autonomous Execution Loop), Claude Code must never:

- Skip validation.
- Skip tests.
- Skip documentation.
- Skip commits.
- Implement work outside the current executable Stage (Part III).
- Modify architecture documents (01–19, 20A/20B/20C, 21A/21B/21C).
- Change constitutional terminology.
- Introduce undocumented dependencies (Section 11).
- Advance to the next Stage while the current Stage is incomplete, per the Autonomous Engineering Verification Gate (Part V, Approval Requirements).

---

## Part V — Engineering Gates

The following gates apply uniformly to every module at every stage (21C §37, §38, §39). A module does not advance past its stage until all gates pass.

### Required Deliverables (per module)
Working implementation of the module's Public Interfaces and Internal Architecture as specified in 21B §X.4–§X.6; full unit/integration/E2E test suites; failure-domain tests; instrumentation conforming to the minimum set in 21C §34.3; documentation; Journal entry recording stage completion.

### Acceptance Criteria
All items in the module's stage description (Part III) demonstrated functioning end-to-end against the stated Validation Criteria for that stage.

### Required Tests
Per Part IV Section 18: unit, integration, end-to-end, failure-domain, and (where applicable) adversarial Recursion Guard tests. CIR-001-blocked modules are held to specification-level tests (schema/contract validation) only, until construction unblocks.

### Performance Validation
Where 21B publishes a latency/throughput table for the module, that table's targets are the validation bar. Where 21B explicitly states no target exists (Memory Gateway pending the Document 09 gap; Deployment pending CIR-001; Observability and Governance using derived `[Implementation Decision]` figures), validate against the derived figure and flag it as provisional in the Journal entry rather than treating it as a ratified requirement.

### Security Validation
Bandit, Semgrep, pip-audit, Trivy, and git-secrets scans pass in CI; no hardcoded secrets; Tool Executor sandboxing verified at the module's declared sandbox tier; authorization enforcement verified via the Permission Intersection Rule where Security Gateway is involved.

### Architecture Validation
Section 25 (Part IV) compliance verification, plus the module-specific Conformance Gate categories from 21C §37: constitutional traceability, cross-cutting pattern conformance, interface contract validation, authorization enforcement, instrumentation conformance.

### Documentation Validation
MkDocs build succeeds; OpenAPI/interface spec present and Redoc-renders; architecture note cites the correct 21B section.

### Approval Requirements — Autonomous Engineering Verification Gate
**[Engineering Decision]** A module transitions from "implementation complete" to "Done" status in the Journal automatically, and only, when every one of the following succeeds: repository build, static analysis, type checking, unit tests, integration tests, contract tests, security scans, architecture conformance validation, documentation generation, required coverage threshold, zero remaining Critical or High severity defects, and the module's stated Stage Exit Criteria (Part III). No manual sign-off is required or substituted for this gate. The system must never advance a module to Done, or a Stage to its next Stage, while any one of these checks has not passed. This gate is engineering-process scaffolding only (Part I §4) and does not alter, weaken, or bypass any constitutional Non-Violable Rule — in particular, it does not touch the constitution's own human-approval requirements for Class C/D decisions, Level 3/4 autonomy actions, or the Panic Protocol, all of which remain exactly as specified in 20A/20B/20C and are runtime governance content, not engineering-process content.

---

## Part VI — Final Build Readiness

### Repository Ready
Stage S0 complete: Layer 0 substrate (`kernel`, `core`, `persistence`, `schema_registry`) passes Synthetic Gateway conformance tests; CI pipeline operational; `docker compose up` produces a healthy local environment from a clean clone.

### Kernel Ready
The nine universal Gateway mechanisms (21A §5.2) are implemented once in `kernel`/`core`/`persistence` and proven reusable by at least one real Gateway (`security_gateway`, Stage S1) without modification to the substrate.

### Subsystem Ready
Each of the 26 modules independently reaches its Definition of Done (Section 39 below) or, for the three CIR-001-affected modules, reaches "specification-conformant, construction-blocked" status with the blocker explicitly recorded.

### Platform Ready
Stage S7 (First Light) exit criterion demonstrated: full end-to-end request path from human authorization through agent execution, workflow orchestration, tool invocation, and back to an auditable Journal record.

### Integration Ready
Stages S8 through S10 complete: Human Plane, Adaptation, and Oversight operating, meaning the system is observable, governable, and human-steerable in addition to functionally complete.

### Production Ready
Stages S11–S12 complete (or construction-blocked and explicitly recorded as such pending CIR-001 resolution); rollback procedures tested for every module; all Non-Violable Rules from 20A/20B/20C verified via their corresponding tests (ideally via the Non-Violable Rule → Conformance Test Traceability Matrix called for in 21_PLAN §7 Appendix F, which should be compiled as a first-class deliverable of this build if it does not already exist).

### 39. Completion Checklist (Definition of Done — binary, per 21C §39)

A module is Done when **all five** of the following hold simultaneously — never progressively:

1. Its 21B specification section is unchanged from ratified form (no undocumented drift between spec and implementation).
2. All Conformance Gate categories pass (Part V, Architecture Validation).
3. All applicable test levels pass (unit, integration, E2E, failure-domain, adversarial where applicable).
4. Telemetry conforms to the minimum instrumentation set in 21C §34.3.
5. The module's stage-completion artifact is recorded in the Journal.

### Overall Program Completion Checklist

- [ ] All 26 modules built in dependency-graph order (Levels 0–14 / Stages S0–S12), depth-first, per 21_PLAN §4.2.
- [ ] No prohibited dependency edge (Section 10.4, 21A §9.4.4) exists anywhere in the codebase.
- [ ] First Light (S7) demonstrated and retained as a standing regression test.
- [ ] Panic Protocol halts all autonomy within 5 seconds, verified by timed test.
- [ ] CIR-001, if still unresolved at program end, has every affected module (Integration, Deployment, Evolution) explicitly recorded as "specification-conformant, construction-blocked" — never silently marked Done.
- [ ] The Document 09 (Memory) truncation gap is either resolved (source recovered, sections 10.1–30 ratified) or explicitly carried forward as a permanent open item in Memory Gateway's Journal.
- [ ] Every Non-Violable Rule enumerated in 20A, 20B, and 20C has at least one corresponding automated test (the Traceability Matrix, 21_PLAN §7 Appendix F).
- [ ] No production deployment has occurred, or will occur, without tests — verified as a CI gate, not a policy statement.

---

## Section 6 (Referenced Above) — Open Constitutional-Interpretation Items

These items are carried forward from 21A/21C exactly as flagged there. Claude Code must not resolve them unilaterally; each requires either a Governance ruling, a human decision, or recovery of missing source material.

| ID | Severity | Description | Effect on Build |
|---|---|---|---|
| CIR-001 | Critical | `03_TECH_STACK` names ~50 specific technologies; this conflicts with non-violable rules in documents 17, 18, 19 prohibiting constitutional documents from naming specific technologies/providers. | Blocks full construction of Integration Platform, Deployment Platform, Evolution Gateway. These may reach specification-conformant, construction-blocked status only, until a Governance (G3/G4) ruling resolves the conflict. |
| CIR-002 | High | The "No Direct Service Calls" rule (02 App. A Rule 1) appears to conflict with specified synchronous Gateway interfaces and tight per-hop authorization latency budgets. | Determines the inter-service transport architecture; blocks final transport binding at Stage S1. Semantics are specified; transport mechanism is not, pending resolution. |
| CIR-003 | High | Data ownership is incompletely allocated in the ratified constitution — 02.7.1 names six databases; documents 09–19 introduce ~8 more data-owning subsystems with no allocated storage. | 21A §10's proposed allocation requires ADR ratification before Stage S4 proceeds on firm ground; treat as proposal, not fact, until ratified. |
| CIR-004 | High (engineering-bounded) | No composite end-to-end mediation-chain latency budget is stated anywhere in the constitution — only per-hop budgets exist. | 21C §32.3 resolves this as an engineering allocation exercise, itself downstream of the Document 09 gap; treat composite budgets as provisional. |
| CIR-005–009 | Medium/Low | Repository placement ambiguity (security/observability as lib vs. service), Panic Protocol halt-scope ambiguity, confidence-derivation-function ambiguity across four subsystems, 15% resource-cap scope ambiguity, and a clerical docs/ naming mismatch. | Track individually; none blocks a Stage on its own, but each should be resolved before Production Ready declaration. |
| — | Structural | `09_MEMORY_OPERATING_MODEL` source is truncated mid-Section 10; Sections 10.1–30 (including its Non-Violable Rules and Glossary) are absent from the ratified artifact. | Memory Gateway's Non-Violable Rules, Glossary, and Performance Characteristics cannot be claimed complete. 21B §16.12 already marks its performance figures as provisional pending source recovery — this build specification preserves that caveat rather than resolving it. |

**Runtime bootstrap vs. build order — explicit warning (21_PLAN §1.1 Fact 5, preserved here):** The runtime Bootstrap Sequence (Security → Governance → Deployment self-registration → validation, per 18.33.2) is not the same as the build order in Part III. Deployment Gateway bootstraps third at runtime but is built last (Stage S11) in this plan. Conflating the two is called out as "the most likely early planning error" and must not recur during execution of this build specification.

---

## Appendix — Claude Code Autonomous Execution Loop

This appendix defines the deterministic execution cycle Claude Code follows while carrying out Part III. It is engineering-process scaffolding (Part I §4) and introduces no architecture, module, or dependency change.

**The cycle:**

1. Select the next executable work item (the next undone item within the current Stage, per Part III; never an item from a later Stage while the current Stage is incomplete).
2. Implement only that work item.
3. Compile.
4. Run formatting.
5. Run linting.
6. Run static analysis.
7. Run unit tests.
8. Run integration tests.
9. Run contract tests.
10. Run architecture conformance validation.
11. Run security validation.
12. Run performance validation (when applicable to the work item).
13. Generate/update documentation.
14. Commit changes.
15. Update the implementation Journal.
16. Determine the next executable work item.

**On any validation failure (steps 3–12):**

1. Diagnose the failure.
2. Implement the fix.
3. Re-run ALL validation gates (steps 3–12) from the start — not only the gate that failed.
4. Repeat until every gate succeeds.

Only once every gate in the cycle succeeds may the system commit, update the Journal, and advance to the next executable work item. A work item, module, or Stage is never advanced on a partial pass, consistent with the binary Definition of Done (Part V, Section 39) and the Autonomous Engineering Verification Gate (Part V, Approval Requirements).

---

*End of Document. No further documents are generated per the governing instructions.*
