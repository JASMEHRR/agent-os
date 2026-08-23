# Implementation Architecture — Planning Package

**Agent OS — Pre-Authoring Artifact for `21_IMPLEMENTATION_ARCHITECTURE.md`**
**Prepared by:** Chief Implementation Architect
**Status:** Awaiting Approval — Document Not Yet Written
**Constitutional Posture:** Constitution frozen (01–19). Manifests 20A–20C are the working reference. This package proposes no constitutional change.

---

## 1. Implementation Architecture Analysis

### 1.1 What the Constitution Actually Asks Us to Build

Reading 20A–20C as an engineering specification rather than a governance document, five structural facts dominate every implementation decision.

**Fact 1 — The constitution defines eleven Gateways, and they are all the same shape.**

Documents 09 through 19 each define a subsystem mediated by a Gateway: Memory, Knowledge, Decision, Tool, Learning, Security, Governance, Observability, Integration, Deployment, Evolution. Read side by side, every one of them declares the identical structural skeleton:

| Structural element | Present in |
|---|---|
| Identity primitives (ID, Type, Schema Version, Timestamp, Source Identity, Tenant/Business/Workspace IDs, Lineage Reference, Confidence Score, Disposition) | All 11 |
| Classification taxonomy (by role, form, sensitivity, scope, authority) | All 11 |
| Gateway as sole mediation layer; producers cannot self-certify; consumers cannot bypass | All 11 |
| Boundary enforcement (Tenant, Scope, Authority, Confidence) | All 11 |
| Lifecycle with canonical states and explicit transition guards | All 11 |
| State immutability after a commitment point; correction by append only | All 11 |
| Immutable journal, append-only, seven-year retention | All 11 |
| Confidence thresholds gating authority classes | 10 of 11 |
| Failure classification within 60 seconds; no silent failures | All 11 |
| Self-audit, drift detection, anomaly response | All 11 |
| Panic Protocol compliance within 5 seconds | All 11 |
| Bounded learning / bounded evolution clause | All 11 |
| Human sovereignty terminal authority | All 11 |

This is not a coincidence of drafting style. It is the single most important implementation signal in the entire constitution: **the Gateway is a reusable architectural primitive, and the eleven subsystems are specializations of it.** An implementation that builds eleven bespoke Gateways will produce eleven divergent interpretations of "boundary enforcement," "transition guard," and "immutable journal," and will violate the constitution in eleven different ways. An implementation that builds the Gateway *once* as a kernel and specializes it eleven times gets uniform constitutional conformance as a structural property rather than a review outcome.

This insight drives the entire proposed architecture.

**Fact 2 — 02 and 09–19 describe the same system at two different resolutions, and they must be reconciled without redesign.**

`02_ARCHITECTURE` Section 1.3 enumerates eleven subsystems (API Gateway, Agent Runtime, Workflow Engine, Event Bus, Memory Gateway, Tool Registry, Tool Executor, LLM Router, Cost Manager, Plugin Manager, Monitoring). Documents 09–19 enumerate eleven Gateways. These sets overlap but are not identical.

| 02 Subsystem | Corresponding constitutional Gateway | Relationship |
|---|---|---|
| Memory Gateway | Memory Gateway (09) | Identical |
| Tool Registry + Tool Executor | Tool Registry + Tool Gateway + Tool Executor (12) | 12 adds the Gateway between them |
| Monitoring | Observability Gateway (16) | 16 supersedes in scope; 02 named it Monitoring |
| API Gateway | — | External ingress only; not a constitutional Gateway |
| Agent Runtime | — | Governed by 05/06; not itself a Gateway |
| Workflow Engine | — | Governed by 07; the "Orchestrator" |
| Event Bus | — | Governed by 08; a hub, not a Gateway |
| LLM Router | — | Internal abstraction; consumes Integrations (17) |
| Cost Manager | — | Economic control plane; consumed by 11, 12, 13, 17, 18 |
| Plugin Manager | — | Extension mechanism (01.18.2) |
| — | Knowledge (10), Decision (11), Learning (13), Security (14), Governance (15), Integration (17), Deployment (18), Evolution (19) | Introduced after 02 |

The implementation must realize the union of both sets — roughly **twenty deployable components** — while honoring 02's ratified component responsibilities exactly. No responsibility moves. Eight Gateways introduced in 14–19 simply did not exist when 02's component list was written, and 02 was never amended. That is a gap to be *filled*, not a contradiction to be resolved.

**Fact 3 — The mandatory mediation chain is deep, and every hop has a latency budget.**

The constitution requires that a single agent tool invocation traverse, at minimum: Security Gateway (authenticate + authorize), Decision Gateway (verify committed decision record), Cost Manager (budget pre-check), Tool Gateway (contract validation, authority verification), Integration Gateway (capability abstraction resolution, provider health), Tool Executor (sandbox preparation), and back through output validation — while emitting mandatory signals to the Observability Gateway and writing to four or more immutable journals at every step.

Each hop carries its own ratified budget. Security Gateway authorization is not separately budgeted but Tool Gateway authorization is p50 20ms / p99 100ms; sandbox preparation p50 100ms / p99 500ms; capability abstraction resolution p50 10ms / p99 50ms; integration Gateway authorization p50 20ms / p99 100ms. Meanwhile the Agent Runtime must deliver simple agent tasks at p99 under 10 seconds and the API Gateway must serve human-facing requests at p99 under 200ms.

**The per-hop budgets are individually generous and collectively tight.** The implementation must treat the mediation chain as a single composite latency budget, not a sequence of independent ones. This forces three design commitments: authorization caching within token TTL (explicitly permitted by 14.10.4), co-location of the hot mediation path, and asynchronous journal writes with synchronous durability acknowledgment only where the constitution demands it. This is an implementation problem the constitution anticipates but does not solve.

**Fact 4 — Journal write amplification is the dominant persistence cost.**

Every constitutional subsystem maintains an append-only, immutable, tamper-evident journal retained a minimum of seven years: Security Event Journal, Decision Journal, Tool Invocation Record, Integration Consumption Record, Governance Journal, Learning Journal, Evolutionary Journal, Memory lineage, Knowledge provenance, plus the Event Bus audit stream and Observability evidence packages.

A single Class B decision executing one mutating tool through one integration writes to, conservatively, seven distinct immutable journals plus the event archive. At the ratified throughput targets — 1,000 Class A/B decision proposals per second, 10,000 tool invocations per minute, 50,000 events per second, 100,000 observability signals per second — journal writes, not agent reasoning, become the system's dominant write path.

The implementation must therefore treat the journal as a **first-class shared kernel capability** with a single write path, a single tamper-evidence scheme, a single retention engine, and a single archival tier — not as eleven independently implemented audit tables.

**Fact 5 — The bootstrap order is constitutionally specified and differs from the build order.**

`18_DEPLOYMENT` Section 33.2 specifies the constitutional genesis sequence: validated environment manifest → E4 human approval → Security Gateway initialization with identity registry and root credentials → Governance Gateway initialization with policy hierarchy and steward assignments → Deployment Gateway self-registration as the first environment → validation that all constitutional subsystems can operate.

This is the **runtime** bootstrap. It is not the **build** order — Deployment Gateway is bootstrapped third but is among the last components a team should build, because it governs environments and its absence does not block development. Conflating these two orderings is the most likely early planning error. The proposed Build Order in Section 4 is explicitly distinguished from the Bootstrap Sequence.

### 1.2 Circular Dependencies and Their Constitutional Resolutions

Four genuine cycles exist. Each has a resolution already present in the constitutional text.

| Cycle | Resolution in the constitution |
|---|---|
| **Security ↔ Event Bus.** Events require authenticated producers (08 rule 1, 14). Security emits events. | Security Gateway writes its journal directly to persistence; event emission is a downstream, non-blocking obligation. Security is buildable and operable before the Event Bus exists. |
| **Governance ↔ Observability.** Governance consumes compliance metrics from Observability (16.33.2); Observability consumes constitutional compliance criteria from Governance (16.6.4). | 15.7.2 permits Governance to assemble evidence directly from subsystem journals. Journal-based Governance is the MVP; Observability-enriched Governance is the enhancement. |
| **Deployment ↔ Security/Governance.** Deployment must exist for anything to run; Deployment depends on Security and Governance. | 18.33.2 resolves it explicitly: Security first, Governance second, Deployment self-registers third. The substrate exists before the Deployment Gateway governs it. |
| **Evolution ↔ Governance.** Evolution packages amendments; Governance ratifies them; Governance changes require ratification (15.32.2). | 19.16.2: "The Evolution Gateway packages but does not present; Governance presents." The handoff is unidirectional per artifact. No runtime cycle exists. |

### 1.3 What Must Be Built Once and Shared

The analysis yields a clear set of capabilities that must be implemented exactly once in a shared kernel and consumed by every subsystem. Building any of these more than once guarantees constitutional divergence.

1. **Constitutional Artifact primitive** — the common identity shape (ID, Type, Schema Version, Timestamp, Source Identity, isolation IDs, Lineage, Confidence, Disposition) that all eleven Gateways declare.
2. **Lifecycle State Machine engine** — deterministic, observable, guarded, compensatable transitions with append-only transition events (04.22.1).
3. **Boundary Enforcement engine** — Tenant, Scope, Authority, Confidence, Budget, Temporal checks, evaluated identically everywhere.
4. **Immutable Journal** — append-only, tamper-evident, seven-year retention, tiered archival.
5. **Confidence and Authority resolution** — the graded threshold logic that recurs with different band values in 10 subsystems.
6. **Failure Classification** — the 60-second, five-category (Transient / Degradable / Critical / Security / Financial) taxonomy that recurs verbatim in 05, 06, 07, 12, 14, 17.
7. **Panic Protocol participation** — the 5-second halt contract every subsystem must satisfy.
8. **Signal emission contract** — the mandatory Observability emission obligation (16 rule 1).
9. **Category 1 Incident escalation** — the uniform pipeline every non-violable rule violation must enter.
10. **Isolation context propagation** — tenant/business/workspace scoping carried through every call, event, and journal entry.

This shared kernel is an **implementation artifact**, not a constitutional subsystem. It introduces no new concepts; it is the factored common denominator of concepts the constitution already states eleven times. This distinction is stated explicitly wherever the kernel appears.

---

## 2. Proposed Module Hierarchy

Modules are grouped into planes and layers. **Planes** are cross-cutting and consumed by everything. **Layers** are ordered by dependency depth. Every module name is drawn from ratified constitutional terminology except where noted.

### 2.1 Layer 0 — Constitutional Kernel and Substrate

| Module | Realizes | Notes |
|---|---|---|
| `kernel` | Shared primitives (§1.3) | **Implementation artifact.** Not a constitutional subsystem. |
| `core` | Shared domain models, event schemas, exceptions, constants | Ratified in 02.14 |
| `persistence` | Hexagonal adapters for structured, semantic, graph, cache, object tiers | Adapters only; no domain logic (01.7.1) |
| `schema_registry` | Event and artifact schema registration and versioning | 08.16, 10.16.2, 12.7 |

### 2.2 Trust Plane

| Module | Realizes |
|---|---|
| `security_gateway` | 14 — identity registry, authentication, authorization, permission graph, delegation, revocation, secret and credential governance, security context propagation |

### 2.3 Layer 1 — Truth Substrate

| Module | Realizes |
|---|---|
| `event_bus` | 08 — hub, streams, consumer groups, at-least-once delivery, causality, replay, retention, dead-lettering |

### 2.4 Economic Plane

| Module | Realizes |
|---|---|
| `cost_manager` | 02.3.9 — budget enforcement, cost attribution, cost-based circuit breakers, portfolio circuit breakers consumed by 11, 12, 13, 17, 18 |

### 2.5 Layer 2 — Cognition Substrate

| Module | Realizes |
|---|---|
| `memory_gateway` | 09 — tier hierarchy (Working, Durable, Semantic, Cold), lifecycle, ownership, provenance, decay |
| `knowledge_gateway` | 10 — validated belief, ontology, knowledge graph, contradiction and reconciliation, revalidation |

### 2.6 Layer 3 — Authority

| Module | Realizes |
|---|---|
| `decision_gateway` | 11 — commitment lifecycle, decision classes A–D, authority spectrum, options, approval, standing orders, escalation, reversal, supersession, decision journals |

### 2.7 Layer 4 — Effect

| Module | Realizes |
|---|---|
| `tool_registry` | 12 — canonical tool inventory, manifests, trust scores |
| `tool_gateway` | 12 — authorization boundary, invocation contract, composition mediation |
| `tool_executor` | 12 — sandbox dispatch, secret injection, timeout and cost ceiling enforcement |
| `integration_registry` | 17 — canonical external relationship inventory |
| `integration_gateway` | 17 — sovereign mediation, contract validation, capability abstraction resolution, provider health |
| `llm_router` | 02.3.8 — model tiering (Nano/Standard/Premium), prompt pipeline, semantic cache, failover |

### 2.8 Layer 5 — Execution

| Module | Realizes |
|---|---|
| `agent_runtime` | 05, 06 — worker pool, agent registry, state hydration, context assembly, output validation, heartbeat, reputation |
| `workflow_engine` | 07 — orchestrator, execution DAG, planning, checkpoints, saga compensation, signals, queries |

### 2.9 Layer 6 — Adaptation

| Module | Realizes |
|---|---|
| `learning_gateway` | 13 — observation, attribution, pattern abstraction, consolidation, propagation, measurement, bounded self-modification |
| `evolution_gateway` | 19 — amendment packaging, experimentation, compatibility model, lineage, deprecation, constitutional stability shielding |

### 2.10 Oversight Plane

| Module | Realizes |
|---|---|
| `observability_gateway` | 16 — signal ingestion, health models, causal analysis, prediction, anomaly and drift detection, evidence packaging, coverage validation |
| `governance_gateway` | 15 — policy hierarchy, compliance assessment, interpretation, amendment ratification, stewardship, meta-oversight, exceptions |

### 2.11 Territory Plane

| Module | Realizes |
|---|---|
| `deployment_registry` | 18 — canonical environment inventory |
| `deployment_gateway` | 18 — environment validation, promotion, isolation, sovereignty tiers, continuity, fault domains, bootstrap |

### 2.12 Edge Layer

| Module | Realizes |
|---|---|
| `api_gateway` | 02.3.1 — external ingress, authentication delegation, rate limiting, routing, versioning, OpenAPI serving |
| `human_interface` | Distributed requirement across 05.18, 11.18, 13.33, 16.25, 17.31, 18.35, 19.36 — approval queues, batched digests, override, Panic invocation. **Implementation component realizing constitutional requirements; not a new constitutional subsystem.** |
| `plugin_manager` | 02.3.10, 01.18.2 — plugin discovery, sandbox deployment, lifecycle |

### 2.13 Cross-Cutting Mechanisms (kernel-resident, no separate deployable)

| Mechanism | Realizes |
|---|---|
| Panic Protocol control channel | 05.18.4 and ten further documents — 5-second halt guarantee |
| Category 1 Incident pipeline | All subsystems |
| Journal service | All subsystems — see §1.1 Fact 4 |
| Failure classification | 05.27, 06.21, 07.20, 12.21, 14.28, 17.20 |
| Isolation context propagation | 14.24 |

**Total: 24 modules — 20 deployable components plus 4 shared libraries.**

---

## 3. Dependency Graph

Read downward. A module may depend only on modules above it. No upward or lateral hard dependencies exist; lateral coordination occurs exclusively through the Event Bus.

```
LEVEL 0   kernel · core · persistence · schema_registry
              │
LEVEL 1   security_gateway
              │
LEVEL 2   event_bus
              │
LEVEL 3   cost_manager · observability_gateway (ingestion-only profile)
              │
LEVEL 4   memory_gateway
              │
LEVEL 5   knowledge_gateway
              │
LEVEL 6   decision_gateway
              │
LEVEL 7   integration_registry → integration_gateway
          tool_registry → tool_gateway → tool_executor
          llm_router
              │
LEVEL 8   agent_runtime
              │
LEVEL 9   workflow_engine
              │
LEVEL 10  api_gateway · human_interface
              │
LEVEL 11  learning_gateway
              │
LEVEL 12  governance_gateway · observability_gateway (full profile)
              │
LEVEL 13  deployment_registry → deployment_gateway
              │
LEVEL 14  evolution_gateway · plugin_manager
```

### 3.1 Dependency Rationale for Non-Obvious Edges

- **`event_bus` depends on `security_gateway`** because 08 non-violable rules 1 and 14 prohibit anonymous or unauthenticated emission and consumption. The bus cannot legally accept a message before identity exists.
- **`observability_gateway` appears twice** at Levels 3 and 12. 16 non-violable rule 1 forbids any subsystem from opting out of signal emission, so a minimal ingestion-and-journal profile must exist before any subsystem ships. The full interpretive profile — health models, causal graphs, prediction, drift — depends on signals from subsystems that do not yet exist at Level 3.
- **`decision_gateway` depends on `knowledge_gateway`** because 11.12.1 requires commitments to be grounded in canonical beliefs, and 11 non-violable rule 8 forbids proceeding on contradictory evidence.
- **`tool_gateway` depends on `decision_gateway`** because 12 non-violable rule 2 forbids tool execution without a valid decision record of matching authority.
- **`integration_gateway` precedes `llm_router`** because 17 governs external providers and every model provider is an external capability provider; the router resolves capability abstractions the Integration Gateway owns.
- **`governance_gateway` depends on all journals but not on the subsystems themselves**, per 15.7.2 evidence assembly. This is what breaks the Governance/Observability cycle.
- **`evolution_gateway` is last** because 19 depends on confirmed learning entries (13), Governance ratification (15), experimental environments (18.8), and capability abstractions (17.11). It is structurally the deepest module in the system.

### 3.2 Prohibited Edges

| Prohibited | Constitutional basis |
|---|---|
| Any module → another module's database | 01.7.2, 02 Appendix A rule 1 |
| Agent → Agent (direct) | 06 rule 9, 06 rule 20 |
| Producer → Consumer (direct, for events) | 08 rule 16 |
| Consumer → Tool Executor (bypassing Tool Gateway) | 12 rule 11 |
| Consumer → external provider (bypassing Integration Gateway) | 17 rule 11 |
| Runtime → substrate (bypassing Deployment Gateway) | 18 rule 8 |
| Any principal → any resource (bypassing Security Gateway) | 14 rule 11 |
| Learning → target subsystem (bypassing target Gateway) | 13 rule 2 |
| Evolution → constitution (bypassing Governance) | 19 rule 2 |

---

## 4. Build Order

Build order is organized into **Stages**. Each Stage ends at a demonstrable, testable capability. Stages are not time-boxed; they are dependency-closed.

**Build order is distinct from the Bootstrap Sequence** specified in 18.33.2. Bootstrap is a runtime genesis procedure; build order is a construction sequence. They are stated separately below.

### 4.1 Build Stages

| Stage | Modules | Exit Criterion |
|---|---|---|
| **S0 — Kernel & Contracts** | `kernel`, `core`, `persistence`, `schema_registry` | The Gateway primitive is instantiable. A synthetic Gateway passes conformance tests for identity, lifecycle guards, journal immutability, boundary enforcement, failure classification, and Panic participation. |
| **S1 — Trust** | `security_gateway` | A principal can register, authenticate, receive a scoped token, be authorized, be delegated to, and be revoked with cascade. Security Event Journal is tamper-evident. |
| **S2 — Truth** | `event_bus` | Authenticated producers emit schema-validated events; consumer groups process at-least-once with idempotency; causality chains hold; replay works in sandbox; dead-lettering alerts. |
| **S3 — Instrumentation & Economics** | `observability_gateway` (ingestion profile), `cost_manager` | Every emitted signal is ingested, enriched, journaled. Budgets are enforced pre-flight and post-flight; circuit breakers trip. |
| **S4 — Cognition** | `memory_gateway`, `knowledge_gateway` | Experience is formed, validated, linked, activated, decayed. Beliefs are extracted, validated, integrated, promoted to canonical, revalidated, contradicted, reconciled. |
| **S5 — Authority** | `decision_gateway` | Class A–D commitments with options, evidence grounding, authority resolution, approval gates that never auto-approve, reversal with compensation, supersession with lineage. |
| **S6 — Effect** | `integration_registry`, `integration_gateway`, `tool_registry`, `tool_gateway`, `tool_executor`, `llm_router` | A registered tool, backed by an approved integration, executes in its declared sandbox under a committed decision, within cost ceiling, with validated output and compensation logic. |
| **S7 — FIRST LIGHT** | `agent_runtime`, `workflow_engine` | **Milestone.** One registered agent executes one task inside one durable workflow, invoking one tool through the full mediation chain, with one human approval gate, one saga compensation path, and complete lineage from human authority to external effect. |
| **S8 — Human Plane** | `api_gateway`, `human_interface` | Operators approve, override, receive batched digests, and invoke the Panic Protocol within the 5-second bound. |
| **S9 — Adaptation** | `learning_gateway` | Outcomes are attributed, patterns abstracted, proposals validated, consolidated, propagated to target Gateways, adopted, and measured to confirmation or refutation. |
| **S10 — Oversight** | `governance_gateway`, `observability_gateway` (full profile) | Policy hierarchy enforced, compliance assessed, drift detected and quantified, interpretations ratified, meta-oversight operating. |
| **S11 — Territory** | `deployment_registry`, `deployment_gateway` | Environments registered, validated, promoted, isolated by fault domain and locality; continuity and recovery procedures exercised; bootstrap reproducible. |
| **S12 — Transformation & Extension** | `evolution_gateway`, `plugin_manager` | Amendments packaged and ratified; experiments bounded and reversible; plugins discovered, sandboxed, and lifecycle-managed. |

### 4.2 Why This Order

The order follows three rules applied strictly.

1. **Depth first, not breadth first.** Each Stage closes its dependency set completely. No Stage is entered with a stub dependency, because a stubbed Gateway cannot enforce a boundary, and an unenforced boundary is a constitutional violation that becomes load-bearing.
2. **Trust and Truth before everything.** Security and the Event Bus are the only two modules that literally everything else requires. Building them first means every subsequent module is born constitutionally compliant rather than retrofitted.
3. **First Light as early as the dependency graph permits.** S7 is the earliest point at which the system does what it exists to do. Everything before S7 is scaffolding; everything after is thickening. Placing First Light at S7 rather than S12 is the single most important sequencing decision, because it converts an eighteen-month act of faith into a demonstrable system that then grows.

### 4.3 Bootstrap Sequence (Runtime, per 18.33.2 — not build order)

1. Validated environment manifest with declared sovereignty tier and geographic locality
2. E4 human sovereign approval
3. Security Gateway initialization — identity registry and root credentials
4. Governance Gateway initialization — policy hierarchy and steward assignments
5. Deployment Gateway self-registration as the first environment
6. Validation that all constitutional subsystems can operate within the bootstrapped territory

---

## 5. Repository Structure Proposal

`02_ARCHITECTURE` Section 14 ratifies a repository structure. That structure predates Documents 09–19 and therefore contains no directories for the eight Gateways introduced afterward. **The proposal below extends the ratified structure within its own conventions. It relocates nothing and renames nothing.**

### 5.1 Ratified Elements Preserved Exactly

Top level: `README.md`, `LICENSE`, `docker-compose.yml`, `docker-compose.prod.yml`, `Makefile`, `.github/`, `docs/`, `infrastructure/`, `src/`, `agents/`, `tools/`, `plugins/`, `migrations/`, `scripts/`, `tests/`.

Within `src/`: `gateway/`, `agent_runtime/`, `workflow_engine/`, `event_bus/`, `memory_gateway/`, `tool_registry/`, `tool_executor/`, `llm_router/`, `cost_manager/`, `plugin_manager/`, `core/`, `security/`, `observability/`.

Per-service internal convention preserved: `pyproject.toml`, `src/`, `tests/`.

### 5.2 Proposed Additions to `src/`

| New directory | Realizes | Rationale |
|---|---|---|
| `kernel/` | Shared Gateway primitive | The single highest-leverage addition (§1.3) |
| `knowledge_gateway/` | 10 | No ratified home exists |
| `decision_gateway/` | 11 | No ratified home exists |
| `tool_gateway/` | 12 | 02.14 has registry and executor but not the Gateway 12 introduces between them |
| `learning_gateway/` | 13 | No ratified home exists |
| `governance_gateway/` | 15 | No ratified home exists |
| `integration_registry/`, `integration_gateway/` | 17 | No ratified home exists |
| `deployment_registry/`, `deployment_gateway/` | 18 | No ratified home exists |
| `evolution_gateway/` | 19 | No ratified home exists |
| `human_interface/` | Distributed human-plane requirements | No ratified home exists |
| `persistence/` | Hexagonal adapters | Enforces 01.7.1 domain isolation |

### 5.3 Two Structural Questions Requiring Governance Interpretation

These are flagged, not decided. Both are recorded in the Risk Register and routed to 15.19.

**Q1 — `security/` and `observability/` are ratified in 02.14 as shared libraries under `src/`. Documents 14 and 16 define them as Gateways with registries, journals, and mediation authority.** A shared library cannot be a mediation boundary. The likely resolution is that `security/` and `observability/` remain shared client libraries and are joined by `security_gateway/` and `observability_gateway/` service directories — but this is a constitutional structure question, not an engineering preference.

**Q2 — `migrations/` in 02.14 lists three Alembic environments (`aos_core`, `aos_memory`, `aos_events`) against the six databases enumerated in 02.7.1, and Documents 09–19 introduce roughly eight further data-owning subsystems.** Data ownership allocation is addressed in Risk R4.

### 5.4 Per-Service Internal Structure (Hexagonal, per 01.7.1)

Every service directory follows one convention so that engineers moving between services find the same shape:

- `domain/` — entities, value objects, state machines, guards. Imports no framework, no ORM, no client library.
- `ports/` — interfaces the domain requires.
- `adapters/` — concrete implementations of ports.
- `api/` — transport surface.
- `journal/` — the service's immutable journal specialization.
- `signals/` — the service's mandatory Observability emission contract.
- `tests/` — unit, integration, contract, property.

---

## 6. Risks

Ordered by severity. Each risk states the constitutional basis, the consequence, and the proposed disposition. **Risks R1–R3 are constitutional ambiguities that the Chief Implementation Architect has no authority to resolve; they are routed to the Governance Gateway's interpretation process (15.19).**

### R1 — Critical: Technology naming conflict between 03 and 17/18/19

`19_EVOLUTION` non-violable rule 22 states: *"No constitutional document, policy, or governance artifact may reference a specific implementation technology, provider, or substrate operator."* `17_INTEGRATION` rule 21 and `18_DEPLOYMENT` rule 18 state materially the same prohibition.

`03_TECH_STACK` is a ratified constitutional document that names PostgreSQL, Redis, Temporal, LiteLLM, Ollama, vLLM, FastAPI, Docker, gVisor, Firecracker, Traefik, Prometheus, Grafana, and approximately fifty further specific technologies, and enumerates prohibited named products.

**Consequence:** Under a literal reading, 03 violates three non-violable rules. Every implementation decision that cites 03 inherits the ambiguity. Left unresolved, engineering teams will resolve it by fiat in inconsistent directions.

**Disposition:** Route to 15.19 Constitutional Interpretation, G3 or G4 authority. The plausible interpretation — that the prohibition targets provider lock-in embedded in *capability abstractions and governance artifacts*, while 03 is classified as an *Implementation Specification* enumerating an approved toolkit — is available but is not mine to declare. **Implementation must not begin on Integration, Deployment, or Evolution until this is ruled on**, because all three subsystems' portability guarantees depend on the answer.

### R2 — High: Direct service call prohibition versus specified synchronous interfaces

`02` Appendix A rule 1 prohibits direct service calls; `03` lists "Direct service-to-service HTTP calls" as a prohibited pattern. Yet `02.3.2` specifies Agent Runtime outbound interfaces as "Memory Gateway (gRPC), LLM Router (HTTP), Tool Registry (HTTP)," and `02.1.1` permits direct calls "except for health probes."

**Consequence:** Either every Gateway call is synchronous — contradicting Appendix A — or every Gateway call is event-mediated, which cannot satisfy the p50 20ms authorization budgets in 12.22.1 and 17.21.1.

**Disposition:** Route to 15.19. The reading that reconciles the text is that the prohibition governs *inter-module event notification and business coupling*, while Gateway mediation is a permitted synchronous control-plane call. This must be ruled on before S1, because it determines the entire inter-service transport architecture.

### R3 — High: Composite latency budget is unallocated

Per-hop budgets are ratified; the composite budget for a full mediation chain is not. Summing conservative p99 figures across Security, Decision, Cost, Tool Gateway, Integration Gateway, sandbox preparation, and output validation approaches or exceeds the 10-second p99 for a simple agent task before any inference occurs.

**Consequence:** A conformant implementation may be a slow implementation, and teams will be tempted to skip mediation hops — each skip a Category 1 incident.

**Disposition:** Engineering, not constitutional. Mitigations available within the constitution: authorization caching bounded by token TTL with revocation broadcast (14.10.4), co-location of the hot mediation path, asynchronous journal writes where durability is not synchronously required, and pre-cleared approval gates during workflow Planning (07.12.6). The implementation document must publish an explicit composite budget allocation.

### R4 — High: Data ownership allocation is incomplete

`02.7.1` enumerates six databases. `01.7.2` mandates database-per-module with no cross-module queries. Documents 09–19 introduce approximately eight further data-owning subsystems with no allocated storage.

**Consequence:** Absent an explicit allocation, teams will co-locate new subsystems into existing databases and create the exact hidden coupling 01.7.2 forbids.

**Disposition:** ADR required before S4. Two candidate models — database-per-Gateway, or schema-per-Gateway within tier-aligned databases. The implementation document must publish a complete Data Ownership Matrix covering all twenty-four modules.

### R5 — High: Journal write amplification

Detailed in §1.1 Fact 4. Seven-plus immutable seven-year journals written per non-trivial action, at ratified throughput targets.

**Consequence:** Write path saturation and storage growth that outpaces the portfolio's economic circuit breakers, potentially breaching the 15% resource cap on improvement and oversight activity (04.32, 05.24.3).

**Disposition:** Unified journal service in `kernel` with a single write path, shared tamper-evidence scheme, tiered retention, and asynchronous archival. Capacity model published in the implementation document.

### R6 — Medium: Panic Protocol 5-second hard bound across a distributed system

Eleven documents mandate that Panic halts all autonomous activity within 5 seconds. This is a distributed hard-real-time guarantee spanning twenty components, in-flight tool sandboxes, external provider calls, and durable workflows.

**Consequence:** The guarantee is easy to state and hard to prove. An unproven Panic Protocol undermines the entire human sovereignty model.

**Disposition:** Dedicated design section in the implementation document. Out-of-band control channel, pre-armed halt state in every Gateway, acknowledgment protocol with fail-closed semantics, and — per 05.18.4 — monthly tested drills as a standing conformance gate.

### R7 — Medium: Bilingual workflow boundary

`03.3.2` non-violable: all Temporal workflow definitions must be TypeScript. `03.3.1` non-violable: all business logic in core services must be Python. Activities are Python; orchestration is TypeScript.

**Consequence:** Every workflow context schema, activity input, activity output, and compensation contract crosses a language boundary where neither `mypy --strict` nor `tsc --strict` sees both sides. Contract drift is silent.

**Disposition:** Single-source schema generation from the shared `core` event and artifact schemas into both languages, plus mandatory contract tests across the boundary. Named explicitly as a conformance gate.

### R8 — Medium: Confidence semantics compound across four subsystems

Knowledge confidence (10.14.2) feeds Decision confidence (11.13.2), which feeds Governance confidence (15.13.2) and Learning confidence (13.13.1). Each is "distinct but derived." Each has different bands.

**Consequence:** A miscalibration in Knowledge propagates silently into commitment, oversight, and adaptation. The system may become confidently wrong in a way no single subsystem detects.

**Disposition:** Confidence propagation must be an explicit, tested kernel capability with published derivation rules, not four independent implementations. Observability must monitor calibration drift as a first-class metric (16.16.1 confidence calibration accuracy).

### R9 — Medium: Oversight overhead versus the 15% cap

`04.32` and `05.24.3` cap continuous improvement at 15% of system resources. Governance, Observability, Learning, and Evolution all consume resources continuously and all have their own circuit breakers.

**Consequence:** The machinery that keeps the system constitutional may itself breach the constitutional resource cap.

**Disposition:** Explicit resource accounting for the Oversight and Adaptation planes, published as a budget in the implementation document, with Cost Manager attribution per plane.

### R10 — Medium: Multi-tenancy designed-in, single-tenant deployed

`02.17.4` states multi-tenancy is "already designed in" via `tenant_id` on all tables, while current deployment is single-tenant.

**Consequence:** Tenant scoping that is present in schema but unexercised in practice degrades into an ignored column, and the absolute tenant isolation guarantees of 14.18, 17.10.2, and 18.11 become untested claims.

**Disposition:** Tenant scoping enforced in the kernel, not by convention. Multi-tenant isolation tests in the conformance suite from S1 onward, even while deployed single-tenant.

### R11 — Low: Local-first operability of the Premium tier

`01` non-violable rule 2 requires core functions to operate without internet connectivity. The Premium model tier and all external integrations are internet-dependent.

**Consequence:** If any core path hard-depends on Premium tier or an external integration, the system violates a non-violable rule.

**Disposition:** Explicit degraded-mode specification per subsystem; conformance test that exercises the full First Light path with all external integrations disabled.

### R12 — Low: Documentation structure divergence

`02.14` lists `docs/architecture/` contents as `01_PRINCIPLES` through `07_DEPLOYMENT` — a seven-document series that does not match the ratified nineteen-document series.

**Disposition:** Minor. Reconcile `docs/architecture/` to the actual 01–19 series plus 20A–20C. Note in the implementation document; no interpretation required.

### R13 — Low: Scope and completion risk

Twenty-four modules, eleven Gateways, nineteen constitutional documents, and roughly two hundred non-violable rules.

**Disposition:** The Stage discipline in Section 4, and specifically the placement of First Light at S7, is the primary mitigation. A secondary mitigation is that the Gateway kernel makes Stages S4 through S12 substantially repetitive rather than each being a novel design exercise.

---

## 7. Complete Table of Contents

Proposed structure for `21_IMPLEMENTATION_ARCHITECTURE.md`. Each entry states why the section exists.

### Part I — Foundations

**1. Preamble & Constitutional Fidelity Statement**
Establishes that this document is subordinate to the frozen constitution, that it introduces no constitutional concepts, and that where it and the constitution differ the constitution governs. Necessary because every downstream engineering decision will cite this document, and its authority boundary must be unambiguous.

**2. Implementation Philosophy**
States the governing engineering convictions: the Gateway as universal primitive, conformance-by-construction rather than conformance-by-review, depth-first dependency closure, and First Light as the organizing milestone. Exists because a twenty-four-module system built without a stated philosophy becomes twenty-four philosophies.

**3. Constitutional Interpretation Register**
Enumerates every ambiguity in the ratified text that must be resolved through 15.19 before or during implementation, with severity, blocking stage, and required authority class. Exists because the alternative is engineers resolving constitutional ambiguity by fiat, inconsistently, at scale.

**4. Architectural Layers & Planes**
Defines the layer and plane model from Section 2 of this package, and the rule that dependencies flow downward and lateral coordination flows through the Event Bus. Exists to make illegal dependencies structurally visible.

**5. The Gateway Pattern**
The central section. Specifies the universal Gateway primitive: mediation contract, identity, lifecycle FSM, boundary enforcement, journal, signal emission, self-audit, Panic participation. Exists because it is the mechanism by which eleven subsystems achieve uniform constitutional conformance.

**6. The Constitutional Kernel**
Specifies the shared library realizing the ten capabilities in §1.3, and states explicitly that it is an implementation artifact rather than a constitutional subsystem. Exists to prevent eleven divergent implementations of the same ten mechanisms.

### Part II — Structure

**7. Module Hierarchy & Boundaries**
The complete module register with constitutional provenance and ownership. Exists to make the twenty-four-module surface explicit and assignable.

**8. Repository Architecture**
The extension of the ratified 02.14 structure, per Section 5. Exists because engineers need one canonical answer to "where does this code live."

**9. Interface Contracts & Communication Model**
Defines the three permitted communication modes — Gateway mediation, event emission, and API Gateway ingress — and the contract discipline for each. Exists because the prohibited-edge list in §3.2 is only enforceable if the permitted edges are precisely specified.

**10. Data Ownership & Persistence Architecture**
The complete Data Ownership Matrix, tier allocation, and migration ownership, resolving R4. Exists because database-per-module is a non-violable principle currently lacking a complete allocation.

**11. State Management**
Specifies where state lives, what is durable versus ephemeral, rehydration, and the append-only correction model. Exists because "no business-critical state exclusively in local memory" is a non-violable rule across four documents.

**12. Configuration Architecture**
Hierarchy, validation, environment scoping, and secret referencing. Exists because configuration is where local-first, sovereignty, and secret non-exposure guarantees are most often quietly broken.

### Part III — Subsystem Implementation Architectures

Sections 13 through 29 each follow one template: constitutional mandate, module decomposition, internal architecture, interfaces exposed and consumed, data owned, state model, journal specialization, signal contract, failure modes, and conformance gates. The uniform template exists so that each subsystem can be built by a different team without architectural divergence.

**13. Security Layer** — realizes 14. Built first after the kernel; everything depends on it.
**14. Event Bus** — realizes 08. The second-deepest dependency.
**15. Memory Subsystem** — realizes 09, including the sections absent from the source artifact, built from the ratified Table of Contents scope.
**16. Knowledge Subsystem** — realizes 10, including ontology governance and the knowledge graph.
**17. Decision Engine** — realizes 11. The commitment checkpoint every non-trivial action traverses.
**18. Tool Framework** — realizes 12: Registry, Gateway, Executor, and sandbox tiering.
**19. Integration Layer** — realizes 17: capability abstractions, provider contracts, portability.
**20. LLM Router & Model Tiering** — realizes 02.3.8 and the 02.8 prompt pipeline. Separate from 19 because the router is internal and integrations are external.
**21. Cost Manager** — realizes 02.3.9 and the circuit breakers of 11, 12, 13, 17, 18. Separate section because five subsystems depend on it.
**22. Agent Framework & Runtime** — realizes 05 and 06.
**23. Workflow Engine** — realizes 07, including the bilingual boundary of R7.
**24. Learning Subsystem** — realizes 13.
**25. Governance Layer** — realizes 15.
**26. Observability Layer** — realizes 16, including both the ingestion and full interpretive profiles.
**27. Deployment Architecture** — realizes 18, including environments, fault domains, sovereignty tiers, and bootstrap.
**28. Evolution Subsystem** — realizes 19.
**29. Human Interface & Approval Plane** — realizes the human-plane requirements distributed across 05, 11, 13, 16, 17, 18, 19. Exists as a section because those requirements are stated in seven documents and implemented in one place.

### Part IV — Cross-Cutting Mechanisms

**30. Panic Protocol & Emergency Control**
The 5-second halt architecture, resolving R6. Exists as its own section because it is the mechanical guarantee behind human sovereignty and is mandated identically in eleven documents.

**31. Journal & Audit Architecture**
Unified append-only, tamper-evident, seven-year retention architecture, resolving R5. Exists because it is the dominant write path and the substrate of every accountability guarantee.

**32. Failure Domains & Incident Pipeline**
The 60-second classification taxonomy, Category 1 incident escalation, and failure containment. Exists because the classification rule recurs in six documents and must be implemented once.

**33. Extension & Plugin Architecture**
Plugin Manager, Tool Marketplace, and the integration of both with sandboxing and trust scoring. Exists because 01.18.2 requires extension without core modification.

**34. Scalability Strategy**
Horizontal scaling per module, partitioning keys, fair-share enforcement, backpressure, and the ratified throughput targets. Exists because the targets are ratified and must be traced to a scaling design.

### Part V — Delivery

**35. Testing Strategy**
The 70/20/10 pyramid, contract testing across module and language boundaries, property-based testing for security and financial paths, chaos engineering, and a **Constitutional Conformance Suite** that tests non-violable rules directly. Exists because "no production without tests" is non-violable and because non-violable rules are only real if they are tested.

**36. Dependency Graph**
The authoritative fourteen-level graph and prohibited-edge register from Section 3. Exists so that dependency violations are detectable in CI rather than in review.

**37. Build Sequencing & Stages**
The S0–S12 stage model with exit criteria, and the distinction between build order and bootstrap sequence. Exists to convert a large architecture into an ordered construction plan.

**38. Incremental Implementation Roadmap**
Per-stage deliverables, demonstrable capabilities, team allocation shape, and the First Light milestone definition. Exists because Section 37 states the order and this section states the work.

**39. Definition of Done & Constitutional Conformance Gates**
The gate every module passes before it is considered complete: typed, tested, journaled, signal-emitting, Panic-compliant, boundary-enforcing, ADR-backed, runbook-covered. Exists because the constitution defines completion criteria across many documents and engineers need one checklist.

**40. Appendices**
A. Module Register · B. Interface Register · C. Data Ownership Matrix · D. Journal Register · E. Signal Contract Register · F. Non-Violable Rule → Conformance Test Traceability Matrix · G. Constitutional Interpretation Register (live) · H. Risk Register (live).

Appendix F is the most important: it maps every non-violable rule in Documents 01–19 to the specific automated test that proves it. Exists because approximately two hundred absolute rules are otherwise unenforceable.

---

## Awaiting Approval

This package proposes twenty-four modules across nine layers and two planes, fourteen dependency levels, thirteen build stages, and a forty-section implementation architecture.

Three items require decisions that are not mine to make. **R1** (technology naming conflict) and **R2** (direct service call prohibition) are constitutional ambiguities that should be routed to the Governance Gateway's interpretation process before implementation begins on the affected subsystems. **R4** (data ownership allocation) requires an ADR before Stage S4.

On approval, `21_IMPLEMENTATION_ARCHITECTURE.md` will be written section by section in the order above.

*End of Planning Package*
