# 20A_FOUNDATION_MANIFEST.md

**Agent OS — Constitutional Manifest, Part A: Foundation Layer**
**Version:** 1.0.0
**Status:** Ratified — Compression Artifact
**Classification:** Architectural Reference Manual — Non-Normative Restatement of Ratified Documents

---

## Scope of This Manifest

This manifest compresses four ratified constitutional documents into a single architectural reference:

| Document | Title | Classification |
|----------|-------|----------------|
| 01 | `01_PRINCIPLES.md` | Architecture Constitution — Binding on All Subsystems |
| 02 | `02_ARCHITECTURE.md` | Architecture Specification — Binding on All Implementation Work |
| 03 | `03_TECH_STACK.md` | Implementation Specification — Binding on All Implementation Work |
| 04 | `04_BUSINESS_OPERATING_MODEL.md` | Canonical Business Model — Binding on Runtime Behavior |

This manifest is a compression of ratified text. It introduces no new concepts, alters no guarantees, and supersedes nothing. Where this manifest and a source document differ, the source document governs.

Documents 05 through 19 are outside the scope of 20A.

---
---

# 01 — PRINCIPLES

## Purpose

To establish the constitutional foundation binding on all subsystems of Agent OS, such that every line of code, every agent design, and every architectural choice traces back to a ratified principle rather than to local convenience.

## Mission

Agent OS exists to build, operate, and optimize digital businesses through a cooperative network of specialized autonomous agents, requiring only strategic human oversight while maximizing automation, safety, and economic value creation.

Its Vision: within five years, Agent OS shall operate a portfolio of self-sustaining digital businesses with minimal human intervention; a single human operator should be capable of overseeing ten or more concurrent business lines, with the system handling research, product development, marketing, deployment, maintenance, and iterative improvement. The system shall be the dominant open-source platform for autonomous business operation, running primarily on local infrastructure with transparent, auditable decision-making.

## Responsibilities

- Define the **Mission** and **Vision** and hold them as the litmus test for all proposed features and architectural changes.
- Define the **Core Philosophy**: Local First, Open Source First, Free API First, Memory First, Human Sovereignty, Tool Driven, Self-Improving.
- Define **Engineering Principles**: Modularity, Event-Driven Architecture, API-First Design, Async-First Execution, Schema Evolution, Infrastructure as Code.
- Define **AI Principles**: Model Agnosticism, Deterministic Boundaries, Context Engineering, Hallucination Mitigation, Tiered Model Strategy.
- Define **Agent Principles**: Single Responsibility, Stateless Operation / Stateful Memory, Explicit Tool Contracts, Graceful Degradation, Observability by Design.
- Define **Software Architecture Principles**: Hexagonal Architecture (Ports and Adapters), Database Per Module, Dependency Inversion, CQRS Where Justified, API Gateway Pattern.
- Define **Coding Standards**, **Documentation Standards**, **Security Principles**, **Cost Optimization Philosophy**, **Scalability Principles**, **Reliability Principles**, and **Testing Philosophy**.
- Define the **Human Approval Rules** — autonomy levels, approval interface, timeouts and defaults, approval audit trail.
- Define **Logging & Observability Principles** and the **Definition of Success**.
- Define **Rules for Future Expansion**, including the Constitutional Amendment Process.

## Non-Responsibilities

- Does not specify components, services, topologies, or data flows — that is 02.
- Does not select technologies, versions, or libraries — that is 03.
- Does not define runtime organizational entities, lifecycles, or state machines — that is 04.
- Does not define subsystem operating models — those are 05 through 19.
- Does not describe implementation.

## Core Concepts

**Core Philosophy (7 pillars).**

| Pillar | Constitutional Content |
|--------|------------------------|
| Local First | Sovereignty over data and compute. Every external dependency must have a local fallback or self-hosted equivalent documented in the ADR. |
| Open Source First | Transparency, community leverage, long-term maintainability. Prefer MIT/Apache-2.0. Proprietary dependencies require written exception with migration plan. |
| Free API First | Cost sustainability. Minimize token consumption, cache aggressively, batch requests, use tiered models. |
| Memory First | Agents without memory are stateless functions, not intelligent systems. Memories are structured (facts, decisions, outcomes), tiered hot/warm/cold. |
| Human Sovereignty | Humans remain the ultimate decision-makers for capital, legal liability, and ethical boundaries. Automation is a tool, not a master. |
| Tool Driven | Agents are defined by the tools they wield, not by monolithic prompts. Agents orchestrate tools; they do not embed business logic in prompts. |
| Self-Improving | The system measures its own performance and identifies improvement opportunities within constitutional bounds. |

**Autonomy Levels (Human Approval Rules).**

| Level | Name | Definition |
|-------|------|------------|
| Level 1 | Full Autonomy | Internal data processing, research, draft generation, monitoring. No approval required. |
| Level 2 | Logged Autonomy | Observable external effects, easily reversible. Logged, with alerting. |
| Level 3 | Human Approval | Financial, legal, or reputational impact, difficult to reverse. Requires explicit human approval. |
| Level 4 | Human Escalation | Outside the agent's training or authority. Agent must escalate and await human instruction. |

**Definition of Success — System Success Criteria.** Autonomy Ratio (>90% for Level 1–2 operations); MTBF (>720 hours for critical paths); MTTR (<30 minutes automated, <2 hours human-involved); Cost Per Business Operation (20% reduction per quarter); Revenue Per Human Hour (10× year-over-year); Agent Success Rate (>95%). **Business Success Criteria**: revenue, profit margin, NPS, churn rate, growth rate. **Continuous Improvement**: success is never declared final.

**Rules for Future Expansion.** Backward Compatibility (public APIs and event schemas versioned; old versions supported minimum two major releases; 90-day deprecation notice); Plugin Architecture; Feature Flags (default OFF); Experimental Modules (isolated namespaces, no production data or financial resources); Constitutional Amendments (written proposal, impact analysis on all existing subsystems, 7-day review period, approval by project architect and human operator).

## Constitutional Guarantees

The Appendix of 01 enumerates twenty-two absolute rules. They may not be overridden by subsystem design, operational convenience, or short-term pressure:

1. **Mission Alignment** — No subsystem may contradict the mission.
2. **Local Fallback** — Core functions must operate without internet connectivity.
3. **Open Source Core** — Core business logic must not depend on closed-source components without open alternatives.
4. **Cost Transparency** — Every agent must track and report operational costs.
5. **Deterministic Boundaries** — No financial, access control, or schema migration decisions by raw LLM output.
6. **Memory Persistence** — No business-critical state exclusively in local memory.
7. **Tool Governance** — No unregistered tools. No arbitrary code execution without sandboxing.
8. **Schema Stability** — No breaking schema changes without backward-compatible transition.
9. **Security Layering** — No implicit trust based on network location.
10. **Least Privilege** — No agent permissions beyond documented scope.
11. **Input Sanitization** — No external data directly passed to LLM prompts.
12. **Secret Hygiene** — No hardcoded secrets. Committed secrets trigger immediate rotation.
13. **Sandboxing** — No arbitrary code execution outside sandboxed environments.
14. **Idempotency** — All state-modifying operations must be safe to retry.
15. **Circuit Breakers** — All external HTTP calls must have circuit breakers.
16. **Testing Gate** — No production deployment without tests.
17. **Auto-Approval Prohibition** — No auto-approval on timeout for Level 3+ actions.
18. **Structured Observability** — No unstructured logs. No missing traces. No missing metrics.
19. **Privacy in Logs** — No PII, secrets, or credentials in logs/traces.
20. **Backward Compatibility** — No breaking changes without migration paths.
21. **Feature Flags** — No experimental features without flags.
22. **Constitutional Supremacy** — No bypassing principles without formal amendment.

Additional guarantees held within the body of 01 and binding equally: the mission may only be amended through a formal constitutional amendment process requiring human approval and written impact analysis; the system may never override an explicit human denial or block; self-improvement may never modify the core principles, security boundaries, or human approval gates; no circular dependencies between modules; no agent may make a business-critical decision without access to relevant historical context from the memory system; no architectural decision may permanently close the door to multi-business portfolio management; approval logs must be append-only and retained for a minimum of 7 years; code without tests may not be deployed to production under any circumstances, no exceptions.

## Depends On

Nothing. 01 is the root of the constitution. It depends only on itself and on the amendment process it defines.

## Provides To

- **02_ARCHITECTURE.md** — the principles each subsystem must comply with; Appendix A of 02 is explicitly derived from 01.
- **03_TECH_STACK.md** — the Design Philosophy priority hierarchy governing every technology decision.
- **04_BUSINESS_OPERATING_MODEL.md** — Human Sovereignty, autonomy levels, least privilege, and the Tool Driven principle that the runtime model operationalizes.
- **All subsequent documents (05–19)** — the supremacy clause under which every operating model is constrained.

## Key Definitions

| Term | Definition |
|------|------------|
| **Mission** | The constitutionally enshrined statement of why Agent OS exists; amendable only by formal process. |
| **Vision** | The five-year North Star justifying long-horizon architectural investment. |
| **Non-Violable Rule** | An absolute constraint that may not be overridden by subsystem design, operational convenience, or short-term pressure. |
| **Autonomy Level** | The degree of independence granted to an agent (1–4), per the Human Approval Rules. |
| **ADR (Architecture Decision Record)** | Nygard-format record of Context, Decision, Consequences; immutable once accepted, superseded but never deleted. |
| **Deterministic Boundary** | The line at which LLMs generate *intent* or *configuration* and deterministic code executes *action*. |
| **Tiered Model Strategy** | Routing tasks to the smallest model proven capable at acceptable quality. |
| **Constitutional Amendment** | The only legitimate mechanism for changing a principle: proposal, impact analysis, 7-day review, human approval, versioned publication. |

## Architectural Boundaries

- 01 binds **all** subsystems; no subsystem may claim exemption.
- 01 is upstream of 02, 03, and 04; it never reaches downward into their subject matter.
- The boundary between "LLM task" and "code task" is drawn here and must be honored, not redrawn, by downstream documents.
- Principles may not be bypassed pending amendment. If a principle is wrong, amend it; do not violate it.

## Implementation Statement

01_PRINCIPLES.md establishes constitutional intent, philosophy, standards, and absolute constraints. It names no components, prescribes no code, and mandates no concrete construction.

This document intentionally defines no implementation details.

---
---

# 02 — ARCHITECTURE

## Purpose

To define the technical architecture blueprint of Agent OS: what components exist, what each is responsible for, and how they interact — such that the principles of 01 become a coherent, buildable system topology.

## Mission

To specify Agent OS as a distributed, event-driven, multi-agent operating system built on a microservices foundation — not a monolithic application, not a single LLM with plugins — adhering to Hexagonal Architecture (Ports and Adapters) at the service level and Event-Driven Architecture at the system level, with every subsystem designed for horizontal scalability, local-first operation, and production resilience.

## Responsibilities

- Define the **High-Level System Overview**, architectural paradigm, and system boundaries.
- Define the **Complete Component Architecture** — responsibility, capabilities, interfaces, scaling, and design rationale for every subsystem.
- Define the **Multi-Agent Architecture**: agent definition, manifest specification, lifecycle, communication, discovery, isolation, permissions, health monitoring, recovery.
- Define the **Event-Driven Architecture**: bus topology, event structure, event lifecycle, versioning, retry strategy, dead-letter queue, event replay.
- Define the **Memory Architecture**: tier hierarchy, working memory, long-term memory, vector memory, knowledge graph, cache strategy, memory access control.
- Define the **Data Architecture**: PostgreSQL design, Redis design, pgvector design, file storage, metadata storage, logging storage.
- Define the **LLM Architecture**: router design, model selection logic, local inference stack, cloud fallback, prompt pipeline, context retrieval, cost optimization, failover strategy.
- Define the **Tool Architecture**: registry design, registration flow, permissions, discovery, execution flow, sandboxing, validation.
- Define the **Workflow Architecture**: workflow-as-code, lifecycle, planning, execution, validation, retry and recovery, reflection, saga compensation.
- Define the **Security Architecture**, **Scalability Architecture**, **Deployment Architecture**, **Repository Structure**, **Data Flow**, **Failure Recovery**, and **Future Expansion**.

## Non-Responsibilities

- Does not establish principles — those are inherited from 01.
- Does not select specific library versions or approved dependency lists — that is 03.
- Does not define business entities, organizational hierarchy, or runtime governance semantics — that is 04.
- Does not contain implementation code. Its yaml, sql, and json blocks are explicitly labeled architectural specification, not implementation.

## Core Concepts

**Major Subsystems.**

| Subsystem | Responsibility | Principle Compliance |
|-----------|----------------|----------------------|
| API Gateway | External ingress, authentication, rate limiting, routing | Security (10.1), API-First (4.3) |
| Agent Runtime | Executes agent logic, hydrates state, manages agent lifecycle | Agent Principles (6), Stateless Operation (6.2) |
| Workflow Engine | Durable orchestration of multi-step business processes | Event-Driven (4.2), Reliability (13) |
| Event Bus | All inter-service communication, event persistence, replay | Event-Driven (4.2), Schema Evolution (4.5) |
| Memory Gateway | Unified interface to all memory tiers | Memory First (3.4) |
| Tool Registry | Tool catalog, schema validation, permission enforcement | Tool Driven (3.6), Security (10) |
| Tool Executor | Sandboxed execution of tool code | Sandboxing (10.6), Least Privilege (10.2) |
| LLM Router | Model abstraction, routing, cost tracking, failover | Model Agnosticism (5.1), Cost Optimization (11) |
| Cost Manager | Budget enforcement, cost attribution, alerting | Cost Transparency (11.1) |
| Plugin Manager | Third-party extension discovery and lifecycle | Future Expansion (18) |
| Monitoring | Metrics collection, alerting, dashboards | Observability (16) |

**Agent as Deployable Artifact.** An Agent is not a process. It is a deployable artifact consisting of an Agent Manifest (`manifest.yaml`), Prompt Templates (`prompts/`), Tool Bindings (`tools.yaml`), Output Schemas (`schemas/`), and Business Logic (`src/`).

**Agent Isolation Layers.** Process (separate Temporal activity worker process), Network (no network access except through Tool Executor), Data (memory only through Memory Gateway with RBAC), Compute (CPU/memory limits via container constraints), Financial (Cost Manager enforces per-operation budgets).

**Event Structure.** Every event carries `event_id` (UUIDv7, idempotency key), `trace_id`, `timestamp`, `schema_version`, `event_type` (dot-notation), `source`, `tenant_id`, `payload`, `metadata`. Event categories: `business`, `agent`, `system`, `command`, `audit`. Delivery is at-least-once with idempotent consumers; after 10 failed attempts events move to the Dead-Letter Stream.

**Memory Tiers.** Working Memory (Redis, hot), Long-Term Memory (PostgreSQL: `memory_facts`, `memory_decisions`, `memory_outcomes`, `memory_episodes`), Vector Memory (pgvector, semantic), Knowledge Graph (Apache AGE), Cold Storage (MinIO). Cache is four-level: L1 in-process LRU, L2 Redis, L3 pgvector semantic, L4 MinIO append-only.

**Model Tiers.** Nano (local 3B–7B: routing, classification, filtering, simple extraction), Standard (local 13B–30B: summarization, drafting, code generation), Premium (Claude 3.5 Sonnet, GPT-4o: complex reasoning, strategy, creative generation, error recovery). Selection cascade: Budget Check → Complexity Classification → Availability Check → Fallback Chain → Cache Check.

**Prompt Pipeline (10 stages).** Template Selection → Context Retrieval → Context Assembly → Input Sanitization → Prompt Rendering → Token Budget Check → LLM Invocation → Output Parsing → Grounding Validation → Cache Storage.

**Sandbox Levels.** `none` (Python function, pure computation), `container` (Docker, network deny-by-default, read-only rootfs), `gvisor` (runsc + seccomp, untrusted code and user-provided plugins), `firecracker` (microVM, security-critical and financial operations). All sandboxes have a kill switch.

**Budget Levels (Cost Manager).** Green (<50%, normal), Yellow (50–80%, warning and alert), Orange (80–95%, model downgrading enforced), Red (>95%, operations halted, human escalation).

**Workflow Architecture.** Workflows are durable, stateful, fault-tolerant orchestrations composed of Workflow Function, Activities, Saga Compensations, Signals, and Queries. Planning constructs an Execution DAG validated for cycles, missing agent registrations, budget violations, and permission conflicts. Compensations execute in reverse order; failed compensation produces a stalled state requiring human intervention.

**Security Architecture.** Identity types: Human Users (OAuth2/OIDC + MFA), Service Accounts (JWT signed by internal CA), Agents (short-lived JWT, 1-hour TTL), API Clients (SHA-256 hashed API keys). Authorization is an RBAC + ABAC hybrid with four Policy Enforcement Points: API Gateway, Agent Runtime, Tool Executor, Memory Gateway. Audit records carry an `integrity_hash` and are retained 7 years.

**Scaling Dimensions.** Compute (horizontal container scaling), Memory (Redis Cluster expansion), Storage (read replicas + partitioning), Agents (Temporal worker pool expansion). Growth path: Single Node → Small Cluster (10–50 agents) → Production Cluster (100–500 agents) → Enterprise Scale (1000+ agents).

**Failure Recovery.** A complete failure matrix covers agent crash, agent stall, queue failure, DB primary failure, DB corruption, LLM all-tiers-down, tool failure, network partition, cost overrun, and security breach — each with detection method, automatic recovery, and human escalation condition. State rehydration is guaranteed because working memory is in Redis, long-term memory is in PostgreSQL, and workflow state is in Temporal.

## Constitutional Guarantees

Appendix A of 02 — Non-Violable Architectural Rules, derived from 01:

1. **No Direct Service Calls** — All inter-service communication via Event Bus or API Gateway.
2. **No Local State** — All business state externalized to PostgreSQL, Redis, or MinIO.
3. **No Unregistered Tools** — All capabilities flow through Tool Registry.
4. **No Raw LLM for Deterministic Logic** — Financial, security, and schema operations use deterministic code.
5. **No Secrets in Code** — All credentials via Docker Secrets or Vault.
6. **No Auto-Approve on Timeout** — Level 3+ actions require explicit human approval.
7. **No Breaking Changes Without Migration** — Schema evolution requires backward compatibility.
8. **No Production Without Tests** — CI enforces coverage and contract tests.
9. **No Missing Observability** — Every service exposes `/health`, `/ready`, `/metrics`, and structured logs.
10. **No Agent Over-Permission** — Agents receive minimum viable JWT scopes.

Further guarantees held in the body of 02: no external client communicates directly with any internal service; no agent accesses Redis or PostgreSQL directly; no agent calls an LLM directly; agents never communicate directly, all interaction is mediated by the Event Bus; producers must register schemas before emitting events and consumers must ignore unknown fields; field removal requires a major version with 90-day deprecation; agents cannot request token scopes beyond their manifest declaration; child workflows inherit only the intersection of parent permissions and child requirements; container images are scanned before registration; direct service-to-service HTTP calls are prohibited except for health probes.

## Depends On

- **01_PRINCIPLES.md** — every subsystem's design rationale is stated as compliance with a numbered principle; Appendix A is explicitly derived from 01.

## Provides To

- **03_TECH_STACK.md** — the component set and interaction contracts that 03 selects technologies to construct.
- **04_BUSINESS_OPERATING_MODEL.md** — the Event Bus, Memory Gateway, Tool Registry, Tool Executor, Workflow Engine, and Cost Manager that the runtime operating rules assume and enforce against.
- **All subsystem operating models (05–19)** — the subsystem boundaries within which each operating model is scoped.

## Key Definitions

Appendix B of 02 — Glossary:

| Term | Definition |
|------|------------|
| **Agent** | A deployable artifact (manifest + prompts + schemas + logic) executed by the Agent Runtime. |
| **Activity** | A unit of work within a Temporal workflow, typically corresponding to one agent execution. |
| **Autonomy Level** | The degree of independence an agent has (1–4), per Human Approval Rules. |
| **Compensation** | A rollback action in a saga pattern that undoes a previously completed activity. |
| **Event Bus** | The Redis Streams-based message backbone for all inter-service communication. |
| **Memory Gateway** | The unified access layer for all data storage (hot, warm, cold, semantic, graph). |
| **Saga** | A sequence of transactions where each has a compensating transaction for rollback. |
| **Sandbox** | An isolated execution environment for tools (container, gVisor, or Firecracker). |
| **Temporal** | The workflow engine providing durable execution and state management. |
| **Tool** | A discrete capability with a defined input/output schema, executed in a sandbox. |
| **Workflow** | A durable, orchestrated business process composed of activities and decisions. |

Additional definitional boundaries: **Agent Manifest** (id, name, version, autonomy_level, capabilities, required_tools, memory_access, max_cost_per_operation, timeout_seconds, retry_policy); **Tool Manifest** (tool_id, name, version, description, input_schema, output_schema, error_schema, sandbox_level, execution_mode, endpoint, required_permissions, cost_estimate_usd, timeout_seconds, retry_policy, dependencies, health_check_endpoint, example_inputs); **Dead-Letter Stream** (`stream:deadletter`, 30 days Redis, indefinite MinIO).

## Architectural Boundaries

- **The kernel boundary:** core services own scheduling, memory routing, tool brokerage, and cost enforcement. Agents are user-space and may not bypass them.
- **The orchestration/execution boundary:** the Workflow Engine owns scheduling; the Agent Runtime owns execution. Agents must not own their lifecycle.
- **The communication boundary:** Event Bus or API Gateway only. No cross-process invocation of internal functions.
- **The memory boundary:** Memory Gateway is the sole access path to all tiers.
- **The I/O boundary:** Tool Registry plus Tool Executor is the sole path to the external world. The Tool Executor is the only component allowed to spawn arbitrary processes.
- **The model boundary:** LLM Router is the sole path to any model, local or cloud.
- **The module boundary:** database-per-module; no module may query another module's tables.
- **The extension boundary:** plugins integrate through Event Bus, API Gateway, Memory Gateway namespaces, and Tool Registry — never in core process space. Adding a new agent requires zero core code changes; adding a new model provider requires only LLM Router changes.

## Implementation Statement

02_ARCHITECTURE.md specifies components, contracts, topologies, and boundaries. Its embedded manifests, schemas, and queries are explicitly marked as architectural specification and architectural pattern, not implementation code.

This document intentionally defines no implementation details.

---
---

# 03 — TECH STACK

## Purpose

To translate the architectural blueprint of 02 into binding technology decisions — eliminating decision fatigue, preventing technology drift, and ensuring that every engineer and every session operates from an identical, pre-approved toolkit.

## Mission

To specify exactly which technologies, versions, libraries, tools, and workflows shall be used to construct the components defined in 02, under a priority hierarchy derived directly from 01, and to make any deviation from that specification possible only through a formal Technology Amendment Process.

## Responsibilities

- Define the **Design Philosophy** priority hierarchy governing all technology adoption.
- Specify **Programming Languages**, **Runtime Versions**, and **Package Management**.
- Specify **Backend Frameworks**, **Frontend Stack**, **Database Technologies**, **Memory Technologies**, **Event Bus Technologies**, **Workflow Engine**, **LLM Infrastructure**, **AI Frameworks**, and **Tool Execution Stack**.
- Specify **Containerization**, **Local Development Environment**, **Production Infrastructure**, and **CI/CD Stack**.
- Specify **Testing Stack**, **Code Quality Tooling**, **Security Tooling**, and **Secrets Management**.
- Specify **Logging**, **Monitoring**, and **Tracing** stacks.
- Specify **Build System**, **Repository Standards**, **Branching Strategy**, **Versioning Strategy**, **Dependency Management**, and **Documentation Tooling**.
- Specify **API Standards**, **SDK Standards**, **Plugin Development Standards**, **Performance Standards**, **Coding Standards**, **Configuration Standards**, **Migration Standards**, and the **Release Process**.
- Define the **Technology Decision Matrix**, the list of **Approved Libraries**, the list of **Prohibited Technologies**, and the **Future Migration Strategy**.

## Non-Responsibilities

- Does not define principles (01), components (02), or runtime governance semantics (04).
- Does not authorize technology outside the approved set; introduction of new technology is out of scope for ordinary work and requires a Technology Amendment Proposal.
- Does not govern infrastructure glue languages beyond the stated exemption (Terraform, shell scripts are exempt from the Python-only business logic rule).
- Does not contain implementation code; its blocks are marked architectural pattern.

## Core Concepts

**Design Philosophy — Priority Hierarchy.**

| Priority | Principle | Technology Implication |
|:--------:|-----------|------------------------|
| 1 | Local First | Prefer self-hostable, on-premise capable technologies. Avoid SaaS-only solutions. |
| 2 | Open Source First | Prefer MIT/Apache-2.0/BSD. Every proprietary dependency requires a written exception. |
| 3 | Free API First | Prefer technologies with generous free tiers or zero marginal cost. |
| 4 | Production Ready | Prefer battle-tested technologies over bleeding-edge experiments. |
| 5 | Observable | Every technology must expose metrics, logs, or traces in open standards. |
| 6 | Cost Optimized | Total cost of ownership must be justified in writing. |

**Technology Decision Matrix.** Weighted scoring: Local First 25%, Open Source 20%, Production Maturity 15%, Operational Simplicity 15%, Performance 10%, Ecosystem Fit 10%, Cost Efficiency 5%. Minimum score 3.5/5 weighted average to be considered. Any score below 2 on Local First or Open Source requires constitutional amendment.

**Canonical Stack (Appendix A summary).**

| Layer | Technology |
|-------|-----------|
| Primary Language | Python 3.11.9+ (3.12.x permitted where compatible) |
| Workflow Definition Language | TypeScript 5.4+ / Node.js 20 LTS |
| Infrastructure Language | HCL — Terraform 1.7+ or OpenTofu 1.6+ |
| Web Framework | FastAPI 0.111.0+ |
| Validation | Pydantic v2 2.7.0+ |
| ORM / Migrations | SQLAlchemy 2.0.30+ / Alembic 1.13.0+ |
| HTTP Client / Server | HTTPX 0.27.0+ / Uvicorn 0.30.0+ |
| Frontend | React 18.3.1+, Vite 5.2+, Tailwind CSS 3.4+, TanStack Query 5.0+, Radix UI, Zustand |
| Primary Database | PostgreSQL 16.3+ with PgBouncer 1.22+ |
| Vector / Graph | pgvector 0.7.0+ / Apache AGE 1.5.0+ |
| Cache, Events, Locks | Redis 7.2+ (Streams as Event Bus) |
| Workflow Engine | Temporal Server 1.22.x (PostgreSQL persistence) |
| LLM Abstraction | LiteLLM Proxy 1.40.0+ |
| Inference | Ollama 0.1.38+ (development), vLLM 0.5.0+ (production) |
| Structured LLM Output | Instructor 1.3.0+ |
| Embeddings | sentence-transformers 3.0.0+, `nomic-embed-text` |
| Containerization & Sandboxing | Docker 25.0+, gVisor runsc, Firecracker 1.7.0+, Trivy, seccomp |
| Production Default | Docker Swarm (Kubernetes optional), Traefik 3.0+ ingress |
| CI/CD | GitHub Actions, Cosign image signing |
| Testing | pytest 8.2+, TestContainers 4.5+, Pact 2.2+, Hypothesis 6.100+, Playwright 1.44+ |
| Code Quality | Ruff 0.4.0+, mypy 1.10.0+ |
| Security | Bandit, Semgrep, pip-audit, Trivy, git-secrets |
| Secrets | Docker Secrets (Swarm), HashiCorp Vault + External Secrets Operator (K8s), SOPS (optional) |
| Observability | structlog 24.1+, Prometheus 2.52+, Grafana 11.0+, Loki 3.0+, Tempo 2.4+, Alertmanager 0.27+, OpenTelemetry 1.25+ |
| Packaging & Build | Poetry 1.8.0+, npm 10+, tsup 8.0+, Make |
| Documentation | MkDocs 1.6.0+ with Material theme, OpenAPI + Redoc, ASCII + Mermaid |

**Prohibited Technologies.** LangChain (orchestration — utility functions only), LlamaIndex (core — reference only), Django, Flask, Celery (workflows — simple background tasks only), MongoDB, Pinecone / Weaviate / Qdrant (core — plugin use only), Neo4j (core — plugin use only), AWS Lambda / GCP Cloud Functions, Firebase / Supabase (core).

**Prohibited Patterns.** Hardcoded secrets in code; raw SQL strings in business logic; synchronous HTTP clients in async services; direct service-to-service HTTP calls; mutable default arguments; bare `except:` / `except Exception:`; `print()` in production; auto-approval on timeout; offset-based pagination; `latest` Docker tags.

**Prohibited Licenses.** GPL-3.0, AGPL-3.0, SSPL, proprietary/commercial without exception, custom restrictive licenses — in core services, absent legal review and ADR.

**Technology Amendment Process (10 steps).** Proposal (TAP) → Evaluation via Decision Matrix → Impact Analysis → Prototype in experimental namespace with feature flags → 7-day Architecture Team review → Chaos Test in staging → Lead Architect + Human Operator approval → Migration Plan with rollback path → Gradual rollout → Documentation update.

**Stack Evolution Principles.** Backward Compatibility First; Incremental Adoption; every technology must have a documented exit strategy before adoption; migration costs justified by 10× improvement in at least one dimension. Deprecation maintains a superseded technology for a minimum of 2 minor releases or 6 months, whichever is longer.

## Constitutional Guarantees

Appendix B of 03 — Non-Violable Implementation Rules:

1. **Python Version** — All services run on Python 3.11.9+ or 3.12.x.
2. **Type Safety** — `mypy --strict` passes with zero errors.
3. **No Secrets in Code** — Hardcoded secrets result in immediate rotation and incident response.
4. **Poetry Only** — No `requirements.txt` in production services.
5. **FastAPI Only** — No Flask, Django, or raw ASGI for HTTP services.
6. **Async I/O** — No blocking HTTP calls (`requests`) in async contexts.
7. **SQLAlchemy 2.0** — No 1.x query API. No raw SQL in business logic.
8. **Alembic Migrations** — No schema changes without migration.
9. **Event Bus** — All inter-service events via Redis Streams. No direct HTTP for events.
10. **Temporal Workflows** — All multi-step business processes are Temporal workflows.
11. **LLM Router** — All LLM traffic through LiteLLM Proxy. No direct provider calls.
12. **pgvector** — All vector storage in PostgreSQL. No separate vector DB in core.
13. **Docker Tags** — No `latest` tags in production.
14. **Resource Limits** — Every container has explicit CPU and memory limits.
15. **Pre-Commit** — All commits pass pre-commit hooks.
16. **Tests Required** — No production deployment without tests.
17. **Auto-Approval Prohibited** — Level 3+ actions never auto-approve on timeout.
18. **Structured Logs** — No unstructured plain-text logs in production.
19. **OpenTelemetry** — All services export traces.
20. **Prometheus Metrics** — All services expose `/metrics`.
21. **No Prohibited Tech** — LangChain orchestration, LlamaIndex core, Celery workflows, MongoDB, and listed prohibited technologies are banned from core.
22. **License Compliance** — No GPL/AGPL/SSPL in core without ADR.
23. **Cursor Pagination** — No offset-based pagination in production APIs.
24. **Idempotency** — All mutating endpoints accept `Idempotency-Key`.
25. **Rollback Tested** — No deployment without tested rollback procedure.

Additional guarantees in the body of 03: no technology may be adopted that violates Priority 1 or 2 without a constitutional amendment to 01; all Temporal workflow definitions must be TypeScript (activity implementations may be Python); knowledge graphs must use Apache AGE; Redis must be configured with persistence enabled; `docker compose up` must produce a fully functional local environment from a clean clone; `pre-commit install` is mandatory for all contributors; no long-lived feature branches and no direct pushes to `main`; no `latest` tags in Dockerfiles, base images pinned to digest or specific version; no secrets in Git, no secrets in environment variables in production (files only), no secrets in logs; the frontend is a dashboard, not a product — no business logic in the frontend.

## Depends On

- **01_PRINCIPLES.md** — the Design Philosophy priority hierarchy and the Local First / Open Source First gates are derived directly from it.
- **02_ARCHITECTURE.md** — 03 exists to construct the components 02 defines; no implementation work may begin without consulting 03.

## Provides To

- **All implementation work** — the binding, pre-approved toolkit.
- **04_BUSINESS_OPERATING_MODEL.md** — the enforcement substrate (SQLAlchemy query filters, Temporal durability, Redis Streams, Cost Manager integration) by which runtime operating rules become mechanically enforceable rather than advisory.
- **All subsystem operating models (05–19)** — the technology envelope within which each subsystem may be realized.

## Key Definitions

| Term | Definition |
|------|------------|
| **Technology Amendment Proposal (TAP)** | The formal instrument by which a technology decision in 03 may be changed. |
| **Technology Decision Matrix** | The weighted 7-criterion scoring framework gating any technology adoption. |
| **Approved Library** | A dependency explicitly listed in Section 41 with version constraint and license. |
| **Prohibited Technology** | A technology banned from core, with a documented reason and exception path (or none). |
| **Prohibited Pattern** | A coding or operational practice banned by name, each mapped to the principle it violates and its correct alternative. |
| **Deprecation Policy** | Sunset date declaration, warnings, minimum 2 minor releases or 6 months support, migration tooling, removal only after all consumers migrate. |
| **Monorepo** | The single repository holding all services, agents, tools, docs, and infrastructure, enabling atomic cross-component change. |
| **Trunk-Based Development** | Short-lived branches merged to `main` frequently, aligned with CI/CD and feature flags. |

## Architectural Boundaries

- 03 is downstream of 02 and may not redefine what components exist or how they interact.
- 03 is downstream of 01 and may not adopt a technology that violates Local First or Open Source First; such adoption requires amending 01, not 03.
- The API contract, not the language, is the boundary: a service may be rewritten in Rust or Go behind a gRPC interface without violating the Python mandate.
- Prohibited technologies are barred from **core**; several retain a narrow plugin-only or utility-only exception path, and those paths are the boundary of their permitted use.
- Version ranges are boundaries: services may not depend on runtime versions outside the specified minimum/maximum without a Technology Amendment.

## Implementation Statement

03_TECH_STACK.md selects and constrains technologies, versions, standards, and processes. Its code-fenced blocks are explicitly labeled architectural pattern, and it prescribes no concrete system construction.

This document intentionally defines no implementation details.

---
---

# 04 — BUSINESS OPERATING MODEL

## Purpose

To define the conceptual runtime model of Agent OS: the organizational primitives, entity lifecycles, governance semantics, and operating rules that bind runtime behavior — the contract between humans, agents, and the system.

## Mission

To establish that Agent OS is an operating system for autonomous digital business operation, and to make that metaphor structurally binding: process management, memory management, I/O management, a file system, a security model, and a user interface — such that no agent executes work outside the process scheduling system, accesses memory outside its allocated address space, or invokes a tool outside the I/O subsystem.

## Responsibilities

- Define **Core Operating Concepts** and the operating system metaphor, including the kernel / user-space distinction.
- Define the **Organization Model** — the strict hierarchy Portfolio (Tenant) → Business → Workspace → Project → Goal → Task.
- Define the entity primitives: **Business**, **Workspace**, **Projects**, **Goals**, **Missions**, **Tasks**, **Workflows**, **Agents**, **Tools**, **Assets**, **Knowledge**, **Memory Ownership**.
- Define the human and authority primitives: **Human Users**, **Roles**, **Permissions**, **Teams**, **Agent Collaboration**, **Decision Making**, **Approval Chains**.
- Define **State Machines** as a governance primitive and the lifecycles of **Business**, **Project**, **Goal**, **Workflow**, and **Agent (Conceptual)**.
- Define **Data Ownership**, **Multi-tenancy Concepts**, and the **Failure Handling Philosophy**.
- Define the **Learning Model** and the **Continuous Improvement Model**.
- Define the **Operating Rules** — the runtime contract — and the enumerated **Non-Violable Rules**.

## Non-Responsibilities

- Does not define architectural constraints — those are in 02.
- Does not define implementation standards — those are in 03.
- Does not define principles — those are in 01.
- Does not define the physical agent artifact, service topology, or storage engine; it defines the *logical* agent, the *conceptual* lifecycle, and the *semantic* ownership relationship.
- Does not describe implementation.

## Core Concepts

**The Operating System Metaphor.** An operating system provides Process Management (workflows and tasks), Memory Management (context, facts, history), I/O Management (tools as drivers), File System (assets), Security Model (authentication, authorization, isolation), and User Interface (human observation and intervention). The metaphor is not decorative; it is the foundational lens. The kernel — the core services — must never be bypassed by user-space agents.

**Organizational Hierarchy.** Portfolio (Tenant) → Business → Workspace → Project → Goal → Task. Every entity has exactly one parent except the Portfolio, which is the root. Cost budgets flow downward; cost overruns propagate upward. Hierarchy depth is limited to 4 levels (Portfolio → Business → Project → Goal).

**Business.** The top-level value-generating entity — a digital business line, the atomic unit of the mission. Attributes: `business_id`, `name`, `domain`, `stage`, `revenue_model`, `health_score`, `autonomy_profile`, `budget`. Every Business has a P&L: revenue, costs (compute, API, human time), and margin.

**Workspace.** An isolated runtime environment within a Business defining agent population, tool availability, memory scope, and network boundaries — the Agent OS equivalent of namespaces or virtual machines. Types: Production, Staging, Development, Sandbox, each with distinct data isolation, network access, and human approval level.

**Mission / Goal / Task.** A **Mission** is a long-term strategic directive (1–3 year horizon) with `vision_statement`, `key_themes`, `anti_goals`, `success_indicators`, and mandatory quarterly human review. A **Goal** is a measurable, observable, quantifiable, time-bounded outcome following the SMART framework, assigned to Projects rather than individual agents. A **Task** is the smallest schedulable unit of work with defined input, expected output, assigned agent, deadline, and cost budget. Task taxonomy: Research, Analysis, Creation, Decision, Action, Review.

**Workflow.** A durable, orchestrated sequence of tasks and sub-workflows achieving a business outcome — the "programs" the OS executes. Patterns: Sequential, Parallel, Conditional, Loop, Human-in-the-Loop, Saga.

**Agent.** A logical autonomous worker with persistent identity, defined capability set, autonomy level, memory scope, and tool inventory. Not a Python script, not a Docker container, not an LLM prompt — the persona the OS schedules. Identity attributes: `agent_id`, `name`, `capability_signature`, `autonomy_level`, `memory_scope`, `tool_inventory`, `cost_budget_per_task`, `success_rate`, `reputation_score`.

**Tool.** A discrete, sandboxed capability — the only mechanism by which Agents interact with the external world or perform deterministic operations; the I/O driver of the operating system. Categories: Information, Creation, Communication, Execution, Analysis. Every tool is a contract: input schema, output schema, timeout, cost estimate, sandbox level, error schema.

**Asset / Knowledge.** An **Asset** is any digital artifact created, modified, or managed by Agent OS — the "files" of the operating system — with tracked provenance (`creator_agent`, `creation_task`, `creation_workflow`, `source_assets`, `approval_status`, `version`). **Knowledge** is refined information: Facts, Heuristics, Patterns, Relationships, Lessons.

**Memory Ownership Tiers.**

| Tier | Owner | Visibility | Lifecycle |
|------|-------|-----------|-----------|
| Private | Individual Agent | Agent only | Agent lifetime + 30 days archive |
| Team | Team (agents + humans) | Team members | Project duration + 90 days |
| Business | Business | All agents in Business workspaces | Business lifetime + 2 years |
| Global | System (anonymized) | All tenants | Indefinite, subject to policy |

**Human User Types.** Operator, Approver, Auditor, Architect. Humans are not "users" in the SaaS sense — they are sovereign operators who delegate authority to agents.

**Decision Classes.**

| Class | Criteria | Default Authority |
|-------|----------|-------------------|
| Class A: Trivial | Reversible, <$0.01 cost, no external impact | Agent (Level 1) |
| Class B: Operational | Reversible within 24h, <$10 cost, internal impact only | Agent (Level 2) |
| Class C: Strategic | Difficult to reverse, $10–$500 cost, customer-facing impact | Human Approval (Level 3) |
| Class D: Existential | Irreversible, >$500 cost, legal/reputational risk | Human Only (Level 4) |

**Approval Chains.** Structured multi-step, multi-party authorization state machines with Requester, Context Packet, Primary Approver, Secondary Approver, Escalation Path, Timeout, and Quorum. Escalation patterns: Timeout, Rejection, Urgency, Budget. Humans may issue **standing orders** — pre-approved rules within defined boundaries, expiring after 30 days unless renewed.

**State Machines as Governance Primitive.** Every major entity is governed by a finite state machine whose properties are Deterministic, Observable, Guarded, and Compensatable. Side effects are executed by downstream consumers of transition events, keeping the state machine pure.

**Lifecycles.** Business (Discovery → Validation → Development → Launch → Growth → Maintenance → Sunset). Project (Proposed → Chartered → Active → Paused → Completed → Archived → Cancelled). Goal (Draft → Active → Tracking → Achieved / Missed / Abandoned / Extended). Workflow (Pending → Planning → Running → Paused → Awaiting Approval → Compensating → Completed / Failed → Archived). Agent (Designed → Registered → Idle → Executing → Suspended → Retired → Archived).

**Data Ownership Hierarchy.** System Data (Agent OS, immutable, never transferred), Tenant Data, Business Data, Project Data, Agent Private Memory, Shared Team Memory, Asset — each with defined owner, inheritance, and transfer rule. Ownership is stamped at creation; objects without ownership are rejected.

**Multi-tenancy.** Soft multi-tenancy at the portfolio level. A Tenant is a complete isolation boundary. Isolation layers: Database (`tenant_id` on every table, enforced at the ORM level), Memory, Event Bus, Storage, Network, Agents, Compute. Tenant-shared by design: System Agents, Global Knowledge (anonymized, read-only), Base Models.

**Failure Handling Philosophy — Fail-Safe Defaults.** Failure is the normal condition, not the exception. When uncertain, halt; when overwhelmed, shed load; when corrupted, isolate. Categories and responses: Transient (retry with backoff), Degradable (continue reduced), Critical (halt, preserve state, escalate), Security (isolate, revoke tokens, preserve evidence), Financial (block spend, freeze budget, audit trail).

**Learning Model.** Learning levels: Task, Agent, Workflow, Business, System. Feedback signals: Outcome Match, Cost Efficiency, Human Rating, Schema Validity, Temporal Stability. Learning is bounded — it optimizes within constraints, not outside them. A "failure library" of anti-patterns is maintained.

**Continuous Improvement Model — Kaizen as Operating Rhythm.** Cycles: Daily Triage (Housekeeping Agent), Weekly Review (Strategy Agent + Human), Monthly Retrospective (Human + Analytics Agent), Quarterly Strategy (Human Architect + Strategy Agent), Annual Vision (Human Operator). Measurement before change; small batches; system health narratives; tracked retrospective action items.

**Operating Rules — the runtime contract.** Scheduling Rules (Priority Inversion Prohibition, Fair Share Guarantee, Human Time Minimization, Agent Affinity); Resource Contention Rules (Budget Pre-emption, LLM Quota Fairness, Database Connection Rationing); Communication Rules (Event-Only Inter-Agent Communication, Human Notification Batching, Escalation Clarity); Data Rules (Write-Through Validation, Read-After-Write Consistency, Audit Completeness).

## Constitutional Guarantees

Section 34 of 04 — Non-Violable Rules. Violation of any rule is a **Category 1 Incident** requiring immediate human escalation, automatic system halt where applicable, and post-incident review.

**Organizational Rules**
1. No task may exist without a parent goal, project, business, and workspace.
2. No business may operate without an active mission and a defined revenue model.
3. No project may become active without an approved charter and success criteria.
4. No goal may be ratified without a quantifiable metric and a deadline.

**Agent and Tool Rules**
5. No agent may act outside its declared capability signature or registered tool inventory.
6. No agent may exceed its autonomy level, regardless of technical capability or confidence.
7. No tool may be invoked without passing through the Tool Registry and Executor.
8. No agent may execute arbitrary code or commands outside a sandboxed environment.

**Decision and Approval Rules**
9. No Class D (existential) decision may be made autonomously by any agent.
10. No approval request may be auto-approved on timeout for Level 3 or 4 actions.
11. No human denial may be overridden by an agent or workflow.
12. All decisions with external impact must be recorded in an immutable decision journal.

**Memory and Data Rules**
13. No data object may exist without a defined owner.
14. No tenant may access another tenant's data, memory, or events.
15. No PII may be stored in Global memory or shared across tenant boundaries.
16. All memory access must respect ownership tiers (Private, Team, Business, Global).

**Workflow and State Rules**
17. No multi-step business process may execute outside a durable workflow.
18. No workflow may modify external state without a defined compensation activity.
19. No entity may exist in an undefined or null state.
20. No state transition may bypass defined guards and validation.

**Security and Safety Rules**
21. No external data may be passed to an LLM prompt without sanitization and validation.
22. No secret, credential, or PII may appear in application logs, traces, or events.
23. No service may trust another service implicitly based on network location alone.
24. No agent may possess permissions beyond its documented scope.

**Failure Handling Rules**
25. Failures must be classified within 60 seconds; silent failures are prohibited.
26. Security failures trigger automatic isolation before human review.
27. Financial anomalies trigger automatic budget freezing before human review.
28. "Fail open" is prohibited for all security, financial, and data-integrity boundaries.

**Learning and Improvement Rules**
29. The Learning Model may not modify constitutional principles, security architectures, or human approval gates.
30. All learned changes to agent behavior must be versioned, reversible, and A/B tested before system-wide deployment.
31. Continuous improvement may not consume more than 15% of total system resources.
32. Negative outcomes must be weighted more heavily than positive outcomes in learning loops.

**Human Sovereignty Rules**
33. Humans must remain the ultimate decision-makers for matters involving capital, legal liability, and ethical boundaries.
34. The system must provide a "panic button" that halts all autonomous activity and requires human intervention to resume.
35. Human attention is a protected resource; the system must optimize for minimizing human cognitive load.

**Section-level guarantees additionally binding.** No agent may execute work outside the process scheduling system; no agent may access memory outside its allocated address space; the kernel may never depend on user-space agent behavior for its own stability. No agent may be assigned to more than one workspace simultaneously. No workspace may access another workspace's memory directly; Production may not execute tools or agents unvalidated in Staging; Sandbox may never hold real customer data; workspace deletion triggers mandatory archival. No project may exceed its budget by more than 10% without automatic pause and escalation. Goals may not be modified after activation without human approval; no goal may be marked Achieved without passing through Tracking; missed goals require a diagnostic retrospective within 48 hours. Missions may only be changed by human operators; missed quarterly mission reviews trigger a system-wide pause on new project charters. No task may be scheduled without an assigned agent, defined output schema, and cost budget. Agents with a success rate below 80% over 30 days must be automatically suspended pending review; suspended agents must be reviewed within 48 hours. Self-review is prohibited: an agent may not review its own output, and no entity may hold both Creator and Reviewer roles for the same output. No agent may invoke another agent directly. Approval requests without rollback plans are auto-rejected; Class D decisions require at least two human approvers from different roles; approval delegation may not exceed 7 days without renewal; blank approvals are invalid. Decision journals are immutable and retained for 7 years. Emergency state transitions require Class D approval and full audit logging. Sunset workflows are irreversible. Tenant deletion must be irreversible and complete, with a certificate of destruction. A team must have at least one human member if it holds Level 3+ permissions. The system may not sacrifice human safety, legal compliance, or financial solvency for operational efficiency.

## Depends On

- **01_PRINCIPLES.md** — Human Sovereignty (3.5), Tool Driven (3.6), Least Privilege (10.2), and the Human Approval Rules autonomy levels are cited directly as the source of runtime authority semantics.
- **02_ARCHITECTURE.md** — the Event Bus, Tool Registry and Executor, Memory Gateway, Workflow Engine, and Cost Manager that the operating rules bind against; 04 explicitly defers architectural constraints to 02.
- **03_TECH_STACK.md** — the enforcement substrate; 04 explicitly defers implementation standards to 03.

## Provides To

- **All subsystem operating models (05–19)** — the entity vocabulary, lifecycle semantics, ownership tiers, decision classes, and approval structures upon which each subsequent operating model builds.
- **Runtime behavior** — 04 is classified Binding on Runtime Behavior; it is the operative contract for every scheduling, memory, I/O, and approval decision the system makes.

## Key Definitions

| Term | Definition |
|------|------------|
| **Portfolio (Tenant)** | The root of the organizational hierarchy and a complete isolation boundary. |
| **Business** | The top-level value-generating entity; a digital business line; the atomic unit of the mission. |
| **Workspace** | An isolated runtime environment within a Business defining agent population, tool availability, memory scope, and network boundaries. |
| **Project** | A time-bounded, resource-bounded initiative with a charter, scope, budget, and Goals; the primary unit of human oversight. |
| **Goal** | A measurable, observable, quantifiable, time-bounded outcome a Project aims to achieve. |
| **Mission** | A long-term strategic directive spanning multiple Projects and Goals, including explicit anti-goals. |
| **Task** | The smallest schedulable unit of work, with defined input, expected output, assigned agent, deadline, and cost budget. |
| **Workflow** | A durable, orchestrated sequence of tasks and sub-workflows achieving a business outcome. |
| **Agent** | A logical autonomous worker with persistent identity, capability signature, autonomy level, memory scope, and tool inventory. |
| **Tool** | A discrete, sandboxed capability; the only mechanism by which Agents touch the external world. |
| **Asset** | Any digital artifact created, modified, or managed by Agent OS, with tracked provenance. |
| **Knowledge** | Refined information: Facts, Heuristics, Patterns, Relationships, Lessons — each with source attribution and confidence score. |
| **Role** | A functional identity defining responsibilities, permissions, and interaction patterns; holdable by a human or an agent. |
| **Permission** | An authorization expressed across four dimensions: Action, Resource, Scope, Condition. |
| **Team** | A cross-functional grouping of agents and humans with shared goals, memory, tools, and accountability. |
| **Decision Class** | The A/B/C/D classification of a decision by impact, reversibility, and cost, determining default authority. |
| **Approval Chain** | A multi-step, multi-party authorization state machine with timeouts, escalation paths, and fallback logic. |
| **Standing Order** | A human-issued pre-approved rule permitting Class C decisions within defined boundaries; expires after 30 days. |
| **Category 1 Incident** | The classification of any Non-Violable Rule violation, requiring immediate human escalation and post-incident review. |
| **Panic Button** | The single command that halts all autonomous activity and requires human intervention to resume. |

## Architectural Boundaries

- **Kernel vs. user space:** core services are kernel; agents are user space. The kernel may never depend on user-space behavior for its own stability, and user space may never bypass the kernel.
- **Hierarchy boundary:** every entity has exactly one parent; nothing exists orphaned. Maximum depth is 4 levels.
- **Workspace boundary:** the memory, tool, and network isolation boundary within a Business. No cross-workspace direct memory access.
- **Tenant boundary:** the complete isolation boundary — logical and cryptographic — across data, memory, events, storage, agents, and compute.
- **Ownership boundary:** semantic, tied to the organizational hierarchy, not a Unix permission bit. Cross-ownership access requires an explicit `access_grant` with scope, duration, and purpose.
- **Authority boundary:** the decision class and autonomy level jointly determine who may act. Class D is never autonomous.
- **Learning boundary:** the Learning Model optimizes within constitutional constraints and may not reach the principles, security architecture, or approval gates.
- **Document boundary:** 04 governs runtime semantics only; architectural constraints belong to 02 and implementation standards to 03.

## Implementation Statement

04_BUSINESS_OPERATING_MODEL.md defines conceptual runtime entities, lifecycles, authority structures, and operating rules. It names no services, selects no technologies, and prescribes no code.

This document intentionally defines no implementation details.

---
---

## Manifest Closure

20A compresses documents 01 through 04 — the Foundation Layer of the Agent OS constitution: why the system exists (01), what it is made of (02), what it is built with (03), and how it behaves at runtime (04).

Documents 05 through 19 are not summarized here and are reserved for subsequent manifests.

*End of Document*
