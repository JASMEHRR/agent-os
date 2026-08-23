# 20B_EXECUTION_MANIFEST.md

**Agent OS — Constitutional Manifest, Part B: Execution Layer**
**Version:** 1.0.0
**Status:** Ratified — Compression Artifact
**Classification:** Architectural Reference Manual — Non-Normative Restatement of Ratified Documents

---

## Scope of This Manifest

This manifest compresses nine ratified constitutional documents into a single architectural reference:

| Document | Title | Classification |
|----------|-------|----------------|
| 05 | `05_AGENT_RUNTIME_FRAMEWORK.md` | Architecture Constitution — Binding on All Runtime Behavior |
| 06 | `06_AGENT_OPERATING_MODEL.md` | Architecture Constitution — Binding on All Agent Behavior |
| 07 | `07_WORKFLOW_OPERATING_MODEL.md` | Architecture Constitution — Binding on All Workflow Behavior |
| 08 | `08_EVENT_OPERATING_MODEL.md` | Architecture Constitution — Binding on All Event Behavior |
| 09 | `09_MEMORY_OPERATING_MODEL.md` | Architecture Constitution — Binding on All Memory Behavior |
| 10 | `10_KNOWLEDGE_OPERATING_MODEL.md` | Architecture Constitution — Binding on All Knowledge Behavior |
| 11 | `11_DECISION_OPERATING_MODEL.md` | Architecture Constitution — Binding on All Decision Behavior |
| 12 | `12_TOOL_OPERATING_MODEL.md` | Architecture Constitution — Binding on All Tool Behavior |
| 13 | `13_LEARNING_OPERATING_MODEL.md` | Architecture Constitution — Binding on All Learning Behavior |

This manifest is a compression of ratified text. It introduces no new concepts, alters no guarantees, and supersedes nothing. Where this manifest and a source document differ, the source document governs.

Documents 01 through 04 are compressed in `20A_FOUNDATION_MANIFEST.md`. Documents 14 through 19 are outside the scope of 20B.

**Source integrity note.** The uploaded artifact for `09_MEMORY_OPERATING_MODEL.md` terminates mid–Section 10 (Memory Ownership & Boundaries). Sections 10.1 through 30, including the enumerated Non-Violable Memory Rules, are not present in the artifact. The 09 entry below compresses only what the artifact contains, and marks the boundary explicitly. No content has been invented to fill the gap.

---
---

# 05 — AGENT RUNTIME FRAMEWORK

## Purpose

To specify how Agent OS behaves while alive: how it thinks, decides, allocates, learns, and evolves as an autonomous venture studio. It is the behavioral contract that all runtime subsystems must fulfill.

## Mission

The runtime exists to maximize the **long-term risk-adjusted value of the business portfolio** while minimizing the human labor required to operate it, subject to absolute constraints of safety, legality, and human sovereignty.

**Permanent Objectives**, ordered by priority: Portfolio Value Growth; Knowledge Compounding; Human Sovereignty Preservation; Capital Efficiency; Operational Resilience; Autonomous Discovery.

**Objective Conflict Resolution Order:** Human Sovereignty > Operational Resilience > Capital Efficiency > Knowledge Compounding > Portfolio Value Growth > Autonomous Discovery. The runtime may not sacrifice safety or sovereignty for growth.

## Responsibilities

The runtime has eleven canonical responsibilities. No subsystem may claim these as its own; they are emergent properties of the system as a whole.

- **Opportunity Discovery** — continuously scan external and internal signals for market gaps, competitor weaknesses, technological shifts, underserved segments.
- **Opportunity Evaluation** — rank opportunities using a portfolio-aware scoring model.
- **Business Incubation** — convert validated opportunities into chartered businesses.
- **Business Operation** — execute the ongoing workflows required to run each business.
- **Capital Deployment** — allocate and reallocate capital based on performance, stage-gate criteria, and risk-adjusted return.
- **Resource Scheduling** — assign agents, tools, compute, and LLM quota by priority, deadline, affinity, and fair-share policy.
- **Knowledge Management** — extract, validate, structure, store, retrieve, and decay knowledge.
- **Asset Reuse** — maintain the Asset Library as a living, versioned, quality-gated repository.
- **Risk Governance** — monitor operational, financial, reputational, and security risk; enforce circuit breakers, budget limits, approval gates.
- **Human Interface** — batch and contextualize all requests for human attention.
- **Self-Improvement** — measure its own performance and initiate improvement workflows.

## Non-Responsibilities

- Does not specify implementation. It is a behavioral contract, not an implementation specification.
- Does not define how individual agents are constituted — that is 06.
- Does not define workflow structure, state machines, or compensation mechanics — that is 07.
- Does not define event, memory, knowledge, decision, tool, or learning subsystem behavior — those are 08 through 13.
- Does not override the constitution. Where 05 is silent, the constitution governs.

## Core Concepts

**Runtime Philosophy.** Agent OS is an **autonomous venture studio**. The runtime is not merely a scheduler or an executor; it is the strategic, tactical, and operational consciousness of the system. It treats every business as a **process** consuming capital, knowledge, and agent labor to produce value, and the portfolio as a **meta-process** optimizing long-term value creation. It does not optimize for activity; it optimizes for **outcomes**. It is event-driven and reactive, but also proactive and curious. It never forgets that it is a delegate, not a sovereign.

**Runtime Entities** — the ontological primitives of the operating system: Portfolio (root entity, the optimization boundary), Opportunity (discovered but unvalidated), Business (the atomic unit of portfolio value), Capital Pool, Knowledge Base (the runtime's memory and competitive moat), Asset Library, Agent Workforce, Human Operator (the sovereign entity).

**Runtime Principles.** Value Creation First; Portfolio Thinking; Compounding Knowledge; Bounded Autonomy; Reversible by Default; Event-Driven Reactivity; Graceful Degradation; Cost Transparency; Local-First Inference; Anti-Fragility.

**Runtime Constraints — "not preferences; they are walls."** Constitutional Supremacy; Human Veto Power; Budget Ceilings; Approval Gate Immutability; Tenant Isolation; Tool Governance; Deterministic Boundaries; No Silent Failures.

**Runtime Lifecycle.** Boot Sequence (initialize core services, validate configuration, load agent registry, hydrate active workflows, health-check; accepts no external commands until all critical dependencies report healthy) → Operational Steady-State → Graceful Shutdown → Disaster Recovery.

**Runtime Behavior Model.** Event-Driven Reactivity; Proactive Opportunity Scanning; Periodic Portfolio Review (daily triage, weekly health checks, monthly retrospectives, quarterly strategy); Interrupt Handling; Batched Human Interaction — "It does not spam; it synthesizes."

**Opportunity Lifecycle.** Discovery → Scoring → Validation → Promotion or Retirement, with a ranked Opportunity Backlog. Invalidated opportunities are retired: insights extracted to the Knowledge Base, resources released.

**Business Lifecycle Governance.** Stage-Gate Enforcement across Discovery → Validation → Development → Launch → Growth → Maintenance → Sunset. Autonomy Profiles by Stage: Discovery/Validation high autonomy; Development/Launch moderate; Growth/Maintenance tight financial controls; Sunset zero autonomy for new initiatives. Intervention Triggers: health score below threshold for 7 consecutive days; burn rate exceeding 120% of plan; critical dependency failure; human override.

**Portfolio Management.** Diversification; Correlation Monitoring (highly correlated businesses treated as a single risk factor); Strategic Optionality; Rebalancing; Portfolio-Level Risk Limits.

**Capital Allocation Framework.** Budget Topology (Portfolio → Business → Project → Task); Investment Criteria; ROI Tracking (measured in revenue, knowledge gained, and strategic optionality); Risk-Adjusted Returns; Capital Reallocation; Emergency Reserves (minimum 10% of total capital).

**Resource Allocation & Scheduling.** Priority Classes: Critical (preempts all), High, Normal, Low, Background. Fair Share (no business >60% of shared resources during contention). Agent Affinity. LLM Quota Management. Preemption.

**Decision Making & Autonomy.** Decision Classes A (Trivial) / B (Operational) / C (Strategic) / D (Existential) with corresponding authority Level 1–4. Confidence Requirements. Standing Orders (expire after 30 days unless renewed). Decision Journals (immutable).

**Governance & Oversight.** Boundary Enforcement; Drift Detection; Anomaly Response (operational → retry/fallback/degrade; financial → freeze budget, halt workflows, alert; security → isolate agent, revoke tokens, preserve evidence, page); Constitutional Compliance self-audit escalating as a Category 1 incident.

**Human Sovereignty Integration.** The Human as Sovereign; Approval Interface; Override Mechanisms; **Panic Protocol** (a single command halts all autonomous activity, always available, tested monthly); Delegation with Guardrails.

**Knowledge Compounding.** Extraction → Validation → Integration → Retrieval → Decay → Cross-Business Pollination.

**Cross-Business Asset Reuse.** Asset Identification; Asset Curation; Licensing and Attribution; Recombination.

**Agent Collaboration at Runtime.** Patterns — Pipeline, Ensemble, Hierarchy, Market, Review. Team Formation; Context Transfer; Conflict Resolution.

**Learning & Adaptation.** Outcome Attribution (distinguishing skill from luck); Prompt Refinement; Model Selection Adaptation; Failure Library; Bounded Learning.

**Runtime Evolution & Continuous Improvement.** Capability Expansion; Experimental Modules; Constitutional Amendment; Backward Compatibility. Improvement cycles: Daily, Weekly, Monthly, Quarterly, Annually. Measurement Before Change. Resource Cap of 15%.

**Performance Characteristics.** Latency budgets: human-facing API p99 <200ms; simple agent tasks p99 <10s; complex agent tasks p99 <60s; human approval requests generated within 30s of trigger. Throughput: 50,000 events/second; 1,000+ concurrent agent executions; 100 workflow initiations/minute sustained. Availability target 99.9% for critical paths.

**Failure Handling Philosophy.** Fail-Safe Defaults — "When uncertain, the runtime halts. When overwhelmed, it sheds load. When corrupted, it isolates. Ambiguity is never resolved in favor of action." Classification Within 60 Seconds; No Silent Failures; Financial Freeze.

**Observability & Transparency.** Decision Journals (human-readable); Cost Attribution (real-time, per tenant/business/project/agent/task); Health Metrics; Traceability.

## Constitutional Guarantees

**Runtime Guarantees** — the promises the runtime makes to human operators and to the businesses it manages:

1. **No Unbounded Spend** — no autonomous process can incur unlimited costs; every spend stream has a hard ceiling and a circuit breaker.
2. **Complete Auditability** — every decision, action, state transition, and financial transaction is recorded in an immutable audit trail retained a minimum of seven years.
3. **State Recoverability** — if the runtime is halted and restarted, all in-flight workflows resume from their last durable state without data loss.
4. **Reversibility Window** — all Level 1 and Level 2 actions are reversible within a defined window (default: 24 hours); compensation logic is maintained for all mutating workflows.
5. **Human Accessibility** — a human operator can understand current state, recent decisions, and active workflows through a unified interface without engineering expertise.
6. **Knowledge Durability** — knowledge written to the system is never lost due to agent retirement, business sunset, or workflow failure.
7. **Fair Resource Sharing** — no single business or agent can starve others of shared resources.

**Non-Violable Runtime Rules:**

1. No runtime action may violate the constitution.
2. No agent may exceed its autonomy level.
3. No budget may be exceeded without explicit human approval.
4. No Level 3 or Level 4 action may be auto-approved on timeout.
5. No data may leak across tenant boundaries.
6. No failure may remain unclassified for more than 60 seconds.
7. No knowledge may be presented without source attribution and confidence scoring.
8. No irreversible action may be taken without explicit human designation.
9. No experimental module may access production business data.
10. The panic protocol must halt all autonomy within 5 seconds of invocation.
11. Continuous improvement may not exceed 15% of system resources.
12. Human attention is a protected resource; the runtime must minimize cognitive load, not maximize engagement.

## Depends On

- **01_PRINCIPLES.md**, **02_ARCHITECTURE.md**, **03_TECH_STACK.md**, **04_BUSINESS_OPERATING_MODEL.md** — 05 is explicitly derived from all four. Where 05 is silent, the constitution governs.

## Provides To

- **06_AGENT_OPERATING_MODEL.md** — the runtime as delegator, scheduler, and boundary enforcer within which the workforce operates.
- **07_WORKFLOW_OPERATING_MODEL.md** — the scheduling philosophy, priority classes, fair-share rules, and failure philosophy workflows inherit.
- **08 through 13** — the runtime entities, permanent objectives, decision classes, panic protocol, and bounded-learning constraint upon which each subsystem model builds.

## Key Definitions

| Term | Definition |
|------|------------|
| **Portfolio** | The complete set of businesses, assets, and knowledge owned by a tenant. |
| **Opportunity** | A discovered but unvalidated market gap or business idea. |
| **Capital Pool** | The aggregate financial resource available for portfolio deployment. |
| **Asset Library** | The curated collection of reusable digital artifacts. |
| **Agent Workforce** | The population of specialized autonomous workers. |
| **Decision Class** | The categorization of a decision by impact and reversibility (A, B, C, D). |
| **Standing Order** | A pre-approved rule allowing limited autonomous decision-making. |
| **Decision Journal** | An immutable record of a decision and its rationale. |
| **Health Score** | A composite metric of business or portfolio well-being. |
| **Strategic Optionality** | The value of a business as a future opportunity, beyond current cash flow. |
| **Knowledge Compounding** | The accumulation and cross-pollination of validated insights over time. |
| **Panic Protocol** | The mechanism by which a human operator halts all autonomous activity. |
| **Fail-Safe Default** | The principle that ambiguity resolves to safety, not action. |

## Architectural Boundaries

- **Delegate, not sovereign:** the runtime multiplies human judgment; it does not replace it. Humans set the mission, own the capital, and retain veto power.
- **Constitutional supremacy boundary:** if a principle and an objective conflict, the principle wins.
- **Emergence boundary:** runtime responsibilities are properties of the system as a whole; no single subsystem may claim them.
- **Autonomy boundary:** agents operate within strict autonomy levels enforced universally, regardless of confidence or urgency.
- **Reversibility boundary:** autonomous actions are reversible by default; irreversibility requires explicit human designation.
- **Learning boundary:** the runtime may not learn its way out of constitutional constraints. Learning optimizes within boundaries; it does not erase them.
- **Experimental boundary:** experimental modules operate in isolated namespaces with synthetic data and limited budgets; they may not access production business data.
- **Improvement boundary:** continuous improvement may not consume more than 15% of total system resources.

## Implementation Statement

05_AGENT_RUNTIME_FRAMEWORK.md specifies behavior, entities, objectives, guarantees, and constraints for the living system. It states explicitly that it is not an implementation specification but a behavioral contract.

This document intentionally defines no implementation details.

---
---

# 06 — AGENT OPERATING MODEL

## Purpose

To specify how the autonomous workforce behaves inside Agent OS: how agents are constituted, how they earn trust, how they collaborate, how they learn, and how they are governed.

## Mission

To establish the agent as a **persistent digital worker** with identity, specialty, reputation, and a career trajectory within the studio — registered for a capability, measured on success rate, granted autonomy for proven judgment, and suspended for violations — and to make that workforce metaphor structurally binding on all agents and all runtime subsystems interacting with agents.

## Responsibilities

- Define **Agent Philosophy** and the distinctions Agent vs. Workflow, Agent vs. Tool, Agent vs. Project, and the Specialization Thesis.
- Define **Agent Identity**: identity primitives, persistence, lineage and versioning, identity as accountability anchor.
- Define **Agent Classification** by capability domain, autonomy level, persistence model, and operational tier.
- Define **Agent Anatomy**: manifest, capability signature, memory scope and bindings, tool inventory, autonomy profile, cost budget, output contracts, business logic modules.
- Define the **Agent Lifecycle** states, transition guards, and lifecycle side effects.
- Define **Agent Capabilities**: declaration, discovery, evolution, boundaries and enforcement.
- Define **Agent Roles**: taxonomy, assignment, delegation, role conflicts and separation of duties.
- Define **Agent Authority and Autonomy**: authority as delegated power, autonomy levels, earning autonomy, losing autonomy, standing orders, authority boundaries.
- Define **Agent Decision Making**, **Agent Memory**, **Agent Knowledge**, **Agent Communication**, **Agent Collaboration**, **Agent Teams**, **Agent Tool Usage**.
- Define **Agent Performance and Reputation**, **Agent Learning and Evolution**, **Agent Governance and Oversight**, **Agent Security**, **Agent Failure and Recovery**, **Human-Agent Relationships**.

## Non-Responsibilities

- Does not specify implementation; it is a behavioral contract.
- Does not define the durable orchestration that assigns agents work — that is 07.
- Does not define the event backbone, memory substrate, knowledge base, decision gateway, tool registry, or learning meta-layer — those are 08 through 13.
- Does not grant agents authority; authority is delegated by human operators through the runtime, and 06 only describes its bounds.
- Does not permit agents to own their own lifecycle, permissions, or capability manifest.

## Core Concepts

**The Workforce Metaphor.** "An agent is not a prompt, not a function, not a workflow step." Workflows decide *what* happens and in what order; agents decide *how* to perform assigned work. Workflows are state machines; agents are workers. The agent wields the tool; the tool does not wield the agent. Projects are containers of intent; agents are containers of capability.

**Agent Identity Primitives.** Agent ID (never reused, never reassigned), Name, Version, Capability Signature, Autonomy Level, Reputation Score. Identity persists beyond any single task, workflow, or project, maintained in the Agent Registry as durable system state. Version lineage prevents mid-flight behavioral changes from corrupting active processes. Attribution is non-repudiable: anonymous or pseudonymous agent actions are not permitted.

**Agent Classification.** By capability domain: Research, Analysis, Creation, Execution, Review, Strategy Agents. By autonomy level: Level 1 (Full Autonomy) / 2 (Logged Autonomy) / 3 (Human Approval) / 4 (Human Escalation). By persistence model: Standing, Project-Bound, Experimental. By operational tier: Core Agents, Sandbox Agents.

**Agent Anatomy.** The **Agent Manifest** is the canonical declaration, immutable once registered; changes require a new version. The **Capability Signature** is a list of outcomes, not tools. **Memory Scope and Bindings** declare read scope, write scope, and filters. **Tool Inventory** is enforced at runtime by the Tool Registry and Tool Executor. **Autonomy Profile**, **Cost Budget and Constraints**, **Output Contracts**, and **Business Logic Modules** (deterministic typed functions executed as code, not generated as text) complete the anatomy.

**Agent Lifecycle.** Designed → Registered → Idle → Executing → Suspended → Retired → Archived, each with explicit transition guards. Lifecycle side effects: on registration, private memory namespace initialized; on suspension, active tokens revoked and in-flight task state preserved for forensic review; on retirement, pending tasks reassigned and private memory archived to business memory (anonymized where required); on archive, identity and history retained for the statutory retention period (minimum seven years).

**Agent Roles.** Business Owner (human-only), Project Lead, Agent Worker (agent-only), Reviewer, Operator (human-only), Auditor (human-only). Roles are assigned at the workspace level; temporary assignments expire automatically.

**Authority and Autonomy.** Authority is not inherent; it is delegated. **Earning autonomy**: sustained >95% success rate over 30 days supports Level 2 elevation; reputation score >0.9 supports Level 3 consideration; elevation requires human approval and an ADR for Level 3. **Losing autonomy**: success rate below 80% for 7 consecutive days, security violation or schema drift, human downgrade command, or budget/tool violation; downgrades are immediate for Levels 3 and 4.

**Authority Boundaries.** An agent's authority is bounded by its capability signature (what it can do), tool inventory (how it can act), memory scope (what it can know), autonomy level (what it may decide), cost budget (what it can spend), and workspace (where it can operate). No agent may act outside the intersection of these boundaries.

**Agent Memory Ownership Tiers.** Private (agent lifetime + 30 days archive), Team (project duration + 90 days), Business (business lifetime + 2 years), Global (indefinite, anonymized, subject to policy).

**Knowledge vs. Data vs. Memory.** Data is raw and unprocessed; Memory is a log of what happened; Knowledge is validated, structured, contextualized understanding. "Memory provides provenance; knowledge provides insight." Assertions below 0.7 confidence are flagged as speculative.

**Agent Communication.** Exclusively through the Event Bus. Patterns: Command, Event, Query. Message contracts are typed and schema-versioned; consumers ignore unknown fields; producers do not remove fields without deprecation. Direct invocation of another agent's internal functions, memory, or tools is prohibited and logged as a security incident.

**Agent Collaboration Patterns.** Pipeline, Ensemble, Hierarchy, Market, Review, plus Context Transfer (typed, validated, logged — ad-hoc natural-language context passing is prohibited), Conflict Resolution, Collaboration Timeouts.

**Agent Teams.** Standing, Project, Ad-hoc, Review teams; team charters; shared memory namespaces; formation with briefing workflow; leadership; dissolution triggering knowledge extraction and retrospective.

**Agent Tool Usage.** Tool as Capability Contract. Invocation flow: agent requests → Tool Registry verifies permission → Cost Manager verifies budget → Tool Executor dispatches within sandbox → output validated against schema → validated output returned. Sandbox boundaries: None, Container, gVisor, Firecracker.

**Performance and Reputation.** Success Rate (rolling 30-day). **Reputation Score** composite: success rate 40%, review-agent output quality 25%, goal contribution 20%, human ratings 10%, cost efficiency 5%. Reputation Decay (30 days idle → 10% loss). Drift Detection. Assignment Eligibility: agents below 80% success ineligible for Level 3 tasks; below 60% automatically suspended.

**Learning and Evolution.** Learning levels: Task, Agent, Workflow, Business, System. Feedback signals: Outcome Match, Cost Efficiency, Human Rating, Schema Validity, Temporal Stability. Bounded Learning Constraints: may not modify constitutional principles, security boundaries, human approval gates, or agent identity/ownership. A/B validation of learned changes. Version lineage and succession. Failure Library.

**Agent Security.** Short-lived tokens (maximum 1-hour TTL) with scoped claims, automatically rotated. Permission checks at point of action. Least privilege — child tasks inherit only the intersection of parent permissions and child requirements. Secret handling: agents receive only references to secrets, never values; secrets never appear in agent memory, logs, or traces. Sandboxing requirements.

**Failure and Recovery.** Classification within 60 seconds into Transient, Degradable, Critical, Security, Financial, each with a defined response. Recovery mechanisms: Retry, Reassignment, Rehydration, Fallback. Compensation and Saga Participation. Failure Library.

**Human-Agent Relationships.** Human as Sovereign; Approval Interface; Override Mechanisms; Panic Protocol (always available, tested monthly, completes within 5 seconds); Delegation with Guardrails; Batched Human Interaction — "Human attention is treated as the scarcest resource in the system."

## Constitutional Guarantees

**Non-Violable Agent Rules.** Violation constitutes a Category 1 incident:

1. No agent may act outside its declared capability signature.
2. No agent may access tools not in its registered inventory.
3. No agent may exceed its autonomy level, regardless of confidence or urgency.
4. No agent may execute arbitrary code outside a sandboxed environment.
5. No agent may make a Class D decision autonomously.
6. No approval request may be auto-approved on timeout for Level 3 or 4 actions.
7. No human denial may be overridden by an agent.
8. No agent may access another agent's Private memory without explicit delegation.
9. No agent may communicate with another agent except through the Event Bus.
10. No agent may escalate its own permissions.
11. No agent may proceed if a critical precondition check fails or returns ambiguous results.
12. All agent decisions with external impact must be recorded in an immutable decision journal.
13. No agent may store business-critical state exclusively in local memory.
14. No agent may present unvalidated data as knowledge.
15. No agent may exceed its documented cost budget without triggering immediate halt.
16. No agent may review its own output.
17. No agent may hold both Creator and Reviewer roles for the same output.
18. The Learning Model may not modify constitutional principles or security boundaries.
19. All learned changes must be versioned, reversible, and A/B tested before deployment.
20. No agent may bypass the Event Bus for inter-agent communication under any circumstance.

Additional guarantees held in the body of 06: the manifest is immutable once registered; an agent may not autonomously add capabilities to its manifest; agent retirement requires all in-flight tasks to complete or be reassigned; execution and review must be separable for all customer-facing and financially impactful work; the runtime rejects decisions where confidence is below the threshold defined for the decision class; decision journals are retained for seven years; agents never handle secrets directly.

## Depends On

- **01_PRINCIPLES.md**, **02_ARCHITECTURE.md**, **03_TECH_STACK.md**, **04_BUSINESS_OPERATING_MODEL.md**, **05_AGENT_RUNTIME_FRAMEWORK.md** — 06 is explicitly derived from all five.
- Autonomy levels are cited to `01_PRINCIPLES.md` Section 15 and `04_BUSINESS_OPERATING_MODEL.md` Section 20.

## Provides To

- **07_WORKFLOW_OPERATING_MODEL.md** — the agent identity, capability signature, autonomy level, and reputation score that workflows bind to activities.
- **08 through 13** — the agent as authenticated producer, consumer, proposer, and invoker across every subsequent subsystem model.

## Key Definitions

| Term | Definition |
|------|------------|
| **Agent** | A persistent digital worker with identity, capabilities, memory, and accountability. |
| **Agent Manifest** | The canonical declaration of an agent's identity, capabilities, tools, and constraints. |
| **Autonomy Level** | The tier of delegated authority an agent holds (1–4). |
| **Capability Signature** | The structured declaration of business functions an agent can perform. |
| **Decision Journal** | An immutable record of a decision, its rationale, and its outcome. |
| **Ensemble** | A collaboration pattern where multiple agents produce outputs and an aggregator selects the best. |
| **Fail-Safe Default** | The principle that ambiguity resolves to safety, not action. |
| **Failure Library** | A catalog of failures used to prevent repeated mistakes. |
| **Pipeline** | A collaboration pattern where agents hand off outputs sequentially. |
| **Private Memory** | Memory owned by a single agent, invisible to others. |
| **Reputation Score** | A composite metric of agent trustworthiness and performance. |
| **Role** | A functional identity defining responsibilities and permissions. |
| **Sandbox** | An isolated execution environment for tools. |
| **Standing Order** | A pre-approved rule allowing limited autonomous decision-making. |
| **Success Rate** | The percentage of tasks completed successfully over a rolling window. |
| **Team** | A collaborative unit of agents and humans with shared memory and goals. |
| **Tool Inventory** | The set of tools an agent is authorized to invoke. |

## Architectural Boundaries

- **Agent/Workflow boundary:** the workflow decides *what* and *when*; the agent decides *how*. Agents are stateless between tasks; workflows are stateful across their lifespan.
- **Agent/Tool boundary:** tools provide boundaries; agents provide judgment.
- **Agent/Project boundary:** projects are containers of intent; agents are containers of capability.
- **Manifest boundary:** the manifest is immutable once registered. Capability changes require a new version and, where autonomy boundaries are crossed, human approval.
- **Communication boundary:** the Event Bus is absolute. No direct invocation, no shared memory, no side channels.
- **Memory boundary:** Private memory is inaccessible to other agents; cross-tier access requires explicit permission grants, not implicit inheritance.
- **Separation of duties boundary:** no agent may hold Creator and Reviewer roles for the same output, nor approve its own decisions.
- **Security boundary:** agents cannot escalate their own permissions and never touch secret values.
- **Learning boundary:** learning optimizes within boundaries; it does not erase them.

## Implementation Statement

06_AGENT_OPERATING_MODEL.md defines the constitution of the autonomous workforce: identity, anatomy, lifecycle, authority, collaboration, and governance. It states explicitly that it is not an implementation specification but a behavioral contract.

This document intentionally defines no implementation details.

---
---

# 07 — WORKFLOW OPERATING MODEL

## Purpose

To specify how work itself behaves inside Agent OS: how business processes are constituted, how they coordinate autonomous agents and human operators, how they preserve state across failure, and how they guarantee that every business outcome is traceable, reversible, and measurable.

## Mission

The workflow subsystem exists to **reliably transform business intent into business outcomes** by orchestrating autonomous agents, human judgment, and deterministic tools within a governed, reversible, and observable process.

**Permanent Objectives**, ordered by priority: Outcome Fidelity; Human Sovereignty Preservation; Operational Resilience; Capital Efficiency; Knowledge Compounding; Consistency Guarantees.

**Objective Conflict Resolution Order:** Human Sovereignty > Operational Resilience > Capital Efficiency > Knowledge Compounding > Outcome Fidelity > Consistency Guarantees. The workflow may not sacrifice safety or sovereignty for speed or cost.

## Responsibilities

- Define **Workflow Philosophy** and the distinctions Workflow vs. Agent, vs. Project, vs. Task, plus Durable Execution, Event-Driven Reactivity, Value Creation First.
- Define **Workflow Identity**, **Classification**, and **Architecture & Topology** (hierarchical composition, DAG, event topology, boundary enforcement).
- Define **Workflow Anatomy**: purpose statement, entry criteria, exit criteria, activity inventory, decision points, checkpoints, context schema, output contract, cost budget, timeout policy.
- Define the **Workflow Lifecycle**, **States & Transitions**, and **Context**.
- Define **Ownership & Boundaries**, **Planning**, **Orchestration & Coordination**, and **Execution Patterns**.
- Define **Agent Participation**, **Human Interaction**, **Decision Points & Authority**, **Event Integration**, **Checkpoints & Validation**.
- Define **Compensation, Recovery & Failure Handling**; **Scheduling & Resource Allocation**; **Performance Characteristics**; **Auditability & Lineage**.
- Define **Workflow Learning & Evolution**, **Governance & Oversight**, and **Workflow Security**.

## Non-Responsibilities

- Does not specify implementation; it is a behavioral contract.
- Does not perform work. "The orchestrator does not perform work; it governs work."
- Does not decide *how* a task is executed — that is the agent's judgment (06).
- Does not define the event backbone itself (08), the memory substrate (09), the belief set (10), the commitment gateway (11), the tool contracts (12), or the learning meta-layer (13).
- Does not execute arbitrary code; it dispatches activities to sandboxed environments.

## Core Concepts

**The Process Metaphor.** A workflow is a **durable business process** that transforms one validated business state into another. "It is not a script, not a sequence of prompts, not a chain of API calls, and not an agent." The workflow is the production line; agents are the workers at stations along it. Value Creation First: "A workflow that executes flawlessly but fails to move a business metric is a failed workflow."

**Workflow Identity Primitives.** Workflow ID, Name, Version, Purpose Statement, Charter Reference, Autonomy Profile, Success Criteria, Compensation Strategy, Audit Trail ID. Identity persists a minimum of seven years regardless of outcome. Version lineage prevents mid-flight behavioral changes from corrupting active processes.

**Classification.** By business purpose: Discovery, Build, Operate, Improve, Governance. By structural pattern: Sequential, Parallel, Conditional, Iterative, Human-in-the-Loop, Saga. By autonomy level: 1–4. By persistence model: One-Shot, Standing, Recurring. By scope: Business-Level, Project-Level, System-Level.

**Architecture & Topology.** Hierarchical Composition (parents may spawn and cancel children; children never communicate directly with each other). **Directed Acyclic Graph** — nodes are activities, edges are dependencies; cycles are prohibited, iteration is modeled as a loop construct with an explicit termination guard. Event Topology. Boundary Enforcement — "Tenant isolation is absolute."

**Workflow Anatomy.** Purpose Statement (the litmus test for scope creep); Entry Criteria; Exit Criteria; Activity Inventory; Decision Points (classified A–D with declared authority, confidence threshold, and fallback path); Checkpoints; Context Schema; Output Contract; Cost Budget (80% triggers warning, 95% triggers halt); Timeout Policy.

**Workflow Lifecycle.** Trigger → Planning → Validation → Execution → Completion → Reflection → Archival, with Exception Paths (Pause, Cancel, Compensate, Fail) and defined Lifecycle Side Effects. "Planning is the cheap failure point."

**Canonical States.** Pending, Planning, Ready, Running, Awaiting_Human_Input, Paused, Compensating, Completed, Failed, Archived — each with explicit transition guards. Emergency transitions permitted only for Class D authority and logged as constitutional exceptions. **State Immutability:** transition events are append-only; a correcting transition is appended, never a replacement.

**Workflow Context.** The complete, structured, typed, scoped information environment: Business State, Project Charter, Goal Metrics, Memory Bindings, Agent Assignments, Tool Inventory, Budget Remaining, Human Standing Orders, Workflow Variables. Context is versioned to enable deterministic replay and forensic analysis. Context Budget declares `max_context_tokens` and `max_context_assembly_time`.

**Ownership & Boundaries.** Every workflow is owned by exactly one Business and one Project, executing within exactly one Workspace. Permission Inheritance: the intersection of parent project permissions and assigned agent permissions, enforced at every activity dispatch. Resource Boundaries. Temporal Boundaries.

**Planning.** Pre-flight validation — DAG construction, agent discovery and binding (agents are bound to activities, not to workflows), resource verification, budget pre-allocation (worst-case cost including retry and compensation budgets), approval pre-clearance.

**Orchestration & Coordination.** Centralized orchestration, distributed execution. Activity Dispatch with a unique idempotency key. Synchronization Barriers. Causal Consistency. **Deterministic Replay** — non-deterministic inputs must be injected as explicit workflow variables, not derived inside orchestration logic.

**Execution Patterns.** Sequential, Parallel, Conditional (conditions must be deterministic functions of workflow context, not hidden inside agent prompts), Iterative (bounded iteration counters; unbounded loops prohibited), Human-in-the-Loop (paused workflows release ephemeral resources and consume no compute quota), Saga (mandatory for workflows modifying external state), Ensemble.

**Agent Participation.** Agent Binding; Agent Execution Model (agent holds no memory of the workflow between activities); Agent Authority Within a Workflow — the intersection of workflow autonomy profile, activity decision class, agent autonomy level, and standing orders; an agent may not exceed its own autonomy level even if the workflow profile permits higher. Agent Failure and Reassignment (logged as a workflow deviation). Agent Output Validation.

**Human Interaction.** Batched, Context-Rich Interaction; Approval Gates as first-class DAG activities ("They are not afterthoughts"); Standing Orders (expire after 30 days unless renewed); Override Mechanisms; Panic Protocol Integration (completes within 5 seconds).

**Event Integration.** Event-Driven Execution; Event Consumption by declared subscription; Event Emission atomic with state transition — "an event is not emitted unless the transition is durably recorded"; Event Idempotency; Event Replay (does not mutate business state; reconstructs decision history in a sandboxed context).

**Checkpoints & Validation.** Checkpoints are "mandatory governance primitives," not optional optimizations. Pre-Activity Validation; Post-Activity Validation ("Invalid outputs do not propagate downstream"); Mid-Workflow Health Checks; Checkpoint Durability.

**Compensation, Recovery & Failure Handling.** Compensation is "a business-safe reversal of effect," idempotent, deterministic, ordered, executed in reverse order. Failed compensation produces a stalled state requiring human intervention. Retry Strategy; Timeout Strategy; Cancellation (a cooperative process, logged as a Class C decision); Failure Classification within 60 seconds into Transient, Degradable, Critical, Security, Financial; Recovery Mechanisms (Rehydration, Replay, Reassignment, Fallback); No Silent Failures.

**Scheduling & Resource Allocation.** Priority Classes: Critical, High, Normal, Low, Background. Fair Share (60% cap). Preemption. Resource Quotas. Queue-Based Load Leveling with backpressure.

**Performance Characteristics.** Latency budgets — Planning phase p50 5s / p99 30s / max 120s; simple activity p50 2s / p99 10s / max 30s; complex activity p50 10s / p99 60s / max 300s; human approval request generation p50 1s / p99 30s / max 60s; checkpoint validation p50 10ms / p99 50ms / max 100ms; workflow state transition p50 50ms / p99 200ms / max 500ms. Throughput: 100 initiations/minute sustained; 1,000+ concurrent executions.

**Auditability & Lineage.** Complete Audit Trail (append-only, minimum seven years); Traceability; Decision Journals as first-class audit objects; Cost Attribution; Privacy in Audit Logs.

**Learning & Evolution.** Outcome Attribution; Pattern Recognition (successful structures promoted to versioned, quality-gated templates); Workflow Versioning; A/B Validation; Bounded Learning.

**Workflow Security.** Permission Inheritance; Input Sanitization; Isolation (sub-workflows inherit the parent's isolation boundaries and may not exceed them); Secret Handling; Sandboxing.

## Constitutional Guarantees

**Non-Violable Workflow Rules.** Violation constitutes a Category 1 incident:

1. No workflow may execute without an associated Business, Project, and Workspace.
2. No workflow may operate without a declared purpose statement and success criteria.
3. No mutating workflow may execute without defined compensation activities for every mutating step.
4. No workflow may enter the Running state without passing Planning validation.
5. No workflow may be destroyed while in Running or Paused state; it must transition to Completed, Failed, or Compensating first.
6. No workflow may exceed its chartered budget without triggering immediate halt and human escalation.
7. No approval gate for Level 3 or 4 actions may auto-approve on timeout.
8. No human denial may be overridden by a workflow or agent.
9. No workflow may cross tenant boundaries or access another tenant's memory, assets, or events.
10. No workflow may exist in an undefined or null state.
11. No state transition may bypass defined guards and validation.
12. No workflow may proceed with an activity if a critical precondition check fails or returns ambiguous results.
13. No workflow may make a Class D decision autonomously.
14. No workflow may bypass the event bus for inter-activity or inter-workflow communication.
15. No workflow may store business-critical state exclusively in local memory; all state must be recoverable after orchestrator failure.
16. No workflow may present unvalidated agent output as final output without schema and business rule validation.
17. No workflow may execute arbitrary code or commands outside sandboxed tool environments.
18. All workflow failures must be classified within 60 seconds; silent failures are prohibited.
19. Compensation activities must be idempotent; executing a compensation twice must be safe.
20. The workflow learning model may not modify constitutional principles, security boundaries, or human approval gates.
21. All workflow state transitions, decisions, and approvals must be recorded in an immutable audit trail.
22. No secrets, credentials, or PII may appear in workflow context, logs, events, or audit trails.
23. No workflow may schedule activities that violate an agent's declared capability signature or autonomy level.
24. Workflow archival must retain the complete audit trail and decision journals for the statutory retention period.

## Depends On

- **01_PRINCIPLES.md**, **02_ARCHITECTURE.md**, **03_TECH_STACK.md**, **04_BUSINESS_OPERATING_MODEL.md**, **05_AGENT_RUNTIME_FRAMEWORK.md**, **06_AGENT_OPERATING_MODEL.md** — 07 is explicitly derived from all six.

## Provides To

- **08_EVENT_OPERATING_MODEL.md** — the workflow as a first-class event producer and consumer whose state transitions are atomic with emission.
- **09 through 13** — the workflow context, checkpoint, decision point, activity, and compensation primitives on which memory, knowledge, decision, tool, and learning models operate.

## Key Definitions

| Term | Definition |
|------|------------|
| **Activity** | A unit of work within a workflow, executed by an agent, tool, or human gate. |
| **Checkpoint** | A validation and commit point where workflow state is verified and externalized. |
| **Compensation** | A rollback activity that reverses the effect of a completed mutating activity. |
| **Decision Journal** | An immutable record of a decision, its rationale, alternatives, and outcome. |
| **Execution DAG** | The directed acyclic graph of activities and dependencies that defines a workflow's structure. |
| **Human Gate** | A workflow activity that pauses execution for human input or approval. |
| **Orchestrator** | The runtime authority that manages workflow state, dispatches activities, and enforces the DAG. |
| **Saga** | A sequence of transactions where each has a compensating transaction for rollback. |
| **Standing Order** | A pre-approved rule allowing limited autonomous passage of human gates. |
| **Sub-Workflow** | A child workflow spawned by a parent workflow, encapsulating a distinct business capability. |
| **Workflow** | A durable, orchestrated business process that transforms business state through coordinated activities. |
| **Workflow Context** | The structured information environment passed to every activity within a workflow. |

## Architectural Boundaries

- **Orchestration/execution boundary:** centralized orchestration, distributed execution. The orchestrator governs work; it does not perform it.
- **Acyclicity boundary:** the DAG prohibits cycles. Iteration is a loop construct with an explicit, bounded termination guard.
- **Composition boundary:** children do not communicate directly; all coordination flows through the parent or the event bus.
- **Business/tenant boundary:** absolute. A workflow scoped to Business A may not read Business B's memory, invoke its agents, or emit into its namespaces.
- **Permission boundary:** the intersection of workflow permissions and assigned agent permissions, enforced at every activity dispatch. Sub-workflows may not exceed parent isolation boundaries.
- **Authority boundary:** an agent may not exceed its own autonomy level even where the workflow profile permits higher.
- **Determinism boundary:** conditions must be deterministic functions of workflow context, not hidden inside agent prompts; non-deterministic inputs are injected as explicit workflow variables.
- **Mutation boundary:** no mutating step without declared, idempotent compensation.
- **Sandbox boundary:** the orchestrator does not execute arbitrary code; it dispatches to sandboxed environments.

## Implementation Statement

07_WORKFLOW_OPERATING_MODEL.md defines the durable execution model of the venture studio: identity, anatomy, states, planning, orchestration, compensation, and governance. It states explicitly that it is not an implementation specification but a behavioral contract.

This document intentionally defines no implementation details.

---
---

# 08 — EVENT OPERATING MODEL

## Purpose

To specify how events behave inside Agent OS: how they are constituted, how they coordinate autonomous agents and human operators, how they preserve history, and how they guarantee that every business fact is traceable, immutable, and governable.

## Mission

The event subsystem exists to **make the autonomous venture studio observable, accountable, and recoverable** by ensuring that every meaningful occurrence is captured as an immutable, attributable, and retrievable fact, available to authorized consumers without coupling producers to consumers.

**Permanent Objectives**, ordered by priority: Truth Preservation; Decoupled Coordination; Complete Auditability; Causal Fidelity; Governability; Knowledge Compounding.

**Objective Conflict Resolution Order:** Truth Preservation > Causal Fidelity > Complete Auditability > Decoupled Coordination > Governability > Knowledge Compounding. The event subsystem may not sacrifice accuracy or ordering for convenience.

## Responsibilities

- Define **Event Philosophy** and the distinctions Event vs. Command, vs. Message, vs. Workflow, vs. State, plus Event-Driven Coordination.
- Define **Event Identity**, **Classification**, and **Architecture & Topology** (hub-and-spoke, stream, consumer group, system topology, boundary enforcement).
- Define the **Event Lifecycle** and **States & Transitions**.
- Define **Event Producers** and **Event Consumers**: identity, responsibilities, boundaries, failure handling.
- Define **Ownership & Boundaries**, **Context & Provenance**, **Causality & Ordering**.
- Define **Durability & Immutability**, **Replay & Retention**, **Validation & Schema Evolution**, **Routing & Delivery**.
- Define **Event Security**, **Governance & Oversight**, **Observability**, **Reliability & Fault Tolerance**, **Performance Characteristics**, **Recovery**, and **Learning & Knowledge Compounding**.

## Non-Responsibilities

- Does not specify implementation; it is a behavioral contract.
- Does not govern ordinary messages. "All events are messages, but not all messages are events... The Event Operating Model governs only events."
- Does not issue commands. The runtime does not command agents to act; it emits events agents may choose to react to.
- Does not route based on payload content — content-based routing would couple producers to consumer logic and is prohibited.
- Does not guarantee exactly-once delivery; idempotency is the consumer's responsibility.
- Does not guarantee global wall-clock ordering across streams.

## Core Concepts

**The Fact Metaphor.** An event is "an immutable record that something meaningful has occurred." It is not a message sent *to* someone, not a command, not a request expecting a response. "The event describes what happened; the consumer decides what to do about it." **Event vs. State:** state can be derived from events, but events cannot be derived from state. The event log is the source of truth; state is a derived projection. "State corruption can be repaired by replaying events, but event corruption is irreparable. Therefore, events are guarded more strictly than state." Events are the nervous system; everything else is muscle.

**Event Identity Primitives.** Event ID (universally unique, lexicographically sortable, "serves as the idempotency key for all time"), Event Type (hierarchical dot-notation), Schema Version, Timestamp (occurrence time, distinct from processing or observation time), Trace ID, Tenant ID, Source. Identity persists a minimum of seven years regardless of consumer processing status.

**Classification.** By business domain: Business, Agent, Workflow, System, Command (facts *about* commands, not commands themselves), Audit Events. By structural pattern: Domain, Integration, Notification, Telemetry. By sensitivity: Public, Tenant-Scoped, Restricted. By persistence model: Operational, Analytical, Audit, Ephemeral.

**Architecture & Topology.** Hub-and-Spoke (the Event Bus is the hub; no producer emits directly to a consumer; no consumer polls a producer). Stream Topology — "Streams are not queues; they are durable logs." Consumer Group Topology (each event processed by exactly one member of a group; different groups receive independent copies). Event-Driven System Topology (logical, not physical). Boundary Enforcement — events may not cross tenant boundaries.

**Event Lifecycle.** Occurrence → Emission → Publication (at which moment the event becomes immutable and observable) → Routing (deterministic) → Delivery (at-least-once) → Processing → Acknowledgment → Archival → Expiration.

**Canonical States.** Published, Delivered, Acknowledged, Pending Retry, Dead-Lettered, Archived, Expired, each with defined transition guards. **State Immutability:** transitions apply only to delivery and lifecycle metadata, never to the fact itself. "A correcting event is a new event, not a mutation of an existing one."

**Producers.** Producer Identity (anonymous emission prohibited); Responsibilities — Schema Compliance, Context Completeness, Timestamp Accuracy, Tenant Scoping, Idempotency Awareness; Producer Boundaries; Producer Failure ("Producers must not silently swallow emission failures").

**Consumers.** Consumer Identity; Responsibilities — Idempotent Processing, Ordered Processing, Acknowledgment Integrity ("Acknowledgment before processing is prohibited"), Schema Tolerance, Failure Signaling; Subscription Patterns; Consumer Isolation; Consumer Drift.

**Ownership & Boundaries.** Every event owned by exactly one tenant. Tenant Isolation enforced at the routing layer. Cross-Business Boundaries require shared workspace with bilateral permission grants. Global Events (anonymized, system-owned, readable by all tenants). Event Delegation (time-bounded, scope-limited, logged; does not transfer ownership).

**Context & Provenance.** Causation ID (the Event ID that directly caused this event); Correlation ID; Source Identity; Origin, Emission, and Processing Timestamps; Business Context. **Context Propagation** — consumers must propagate the Correlation ID and set the Causation ID, "creating an unbroken causal graph from the original trigger to all downstream effects." Context Budget.

**Causality & Ordering.** Causal Consistency established by Causation IDs, not wall-clock timestamps. Stream Ordering (total order within a stream). Cross-Stream Ordering (no global wall-clock guarantee). Happens-Before Relationships (same-stream sequence; causation link; transitive). Out-of-Order Handling.

**Durability & Immutability.** Durability achieved before delivery begins. "A Published event may never be modified, overwritten, or deleted." Append-Only Log. Durability Tiers: Hot, Warm, Cold.

**Replay & Retention.** Replay Modes: Forensic, Learning, Recovery. Replay Constraints — does not mutate business state, processed in a sandboxed context, tagged `replay: true`. Retention Policy by category:

| Event Category | Operational | Analytical | Audit |
|----------------|-------------|-----------|-------|
| Business | 30 days | 2 years | 7 years |
| Agent | 30 days | 2 years | 7 years |
| Workflow | 90 days | 2 years | 7 years |
| System | 7 days | 90 days | 7 years |
| Command | 90 days | 2 years | 7 years |
| Audit | 7 years | 7 years | 7 years |

**Validation & Schema Evolution.** Schema Registry (unregistered event types rejected at emission). Semantic versioning: minor = additive only; major = breaking, requiring migration plan and a deprecation period of at least one release cycle. Validation Rules: Emission Validation, Consumption Validation, Forward Compatibility, Backward Compatibility.

**Routing & Delivery.** Metadata-based routing only. **At-least-once delivery** guaranteed; exactly-once is not. Retry Policy with exponential backoff. Backpressure — producer throttling, consumer lag alerts, ephemeral event shedding; "Critical streams (commands, audits) never shed events." Dead-Lettering.

**Event Security.** Authentication; Authorization at emission and consumption; Encryption in transit (mutual TLS) and at rest (tenant-scoped keys); Input Sanitization; Audit of Event Access (immutable, seven years).

**Governance, Observability, Reliability, Performance, Recovery.** Boundary Enforcement; Drift Detection; Anomaly Response (Volume, Schema, Routing, Lag). **Events as Observability Substrate** — metrics, logs, and traces are all derived from or correlated with events; "an alert is not a separate mechanism; it is a consumer." Producer/Bus/Consumer failure handling; Network Partition; No Silent Failures. Latency: emission→publication p50 10ms / p99 50ms / max 100ms; publication→delivery p50 5ms / p99 20ms / max 50ms. Throughput: 50,000 events/second ingestion; 100+ concurrent consumer groups per stream; 10,000 events/second replay. Gap Detection; Reconciliation; Recovery Replay; Corruption Handling (quarantine, `corrupted` flag, compensating event — never deletion).

**Learning & Knowledge Compounding.** Event Pattern Mining; Feedback Loops; Knowledge Extraction; Cross-Business Learning; Bounded Learning.

## Constitutional Guarantees

**Non-Violable Event Rules.** Violation constitutes a Category 1 incident:

1. No event may be emitted without a registered schema and authenticated producer identity.
2. No event may be modified, overwritten, or deleted after publication.
3. No event may cross tenant boundaries without explicit anonymization and human approval.
4. No producer may emit events outside its declared scope and permission boundaries.
5. No consumer may access events outside its subscribed scope and permission boundaries.
6. No event may be silently dropped, swallowed, or ignored without classification and logging.
7. No critical event (command, audit, business state transition) may be shed under load.
8. No event may be delivered without at-least-once semantics.
9. No consumer may acknowledge an event before durable processing is complete.
10. No event may contain unvalidated external data or unsanitized payloads.
11. No event may be replayed in a way that mutates live business state.
12. No event stream may operate without defined retention and archival policies.
13. No breaking schema change may be deployed without backward compatibility and migration planning.
14. No anonymous or pseudonymous event emission or consumption is permitted.
15. The event audit trail must be append-only and retained for a minimum of seven years.
16. No event may bypass the Event Bus for direct producer-to-consumer communication.
17. Event causality chains must be preserved across all emissions and consumptions.
18. No event may be dead-lettered without alerting and human review capability.
19. Event governance anomalies must be escalated as Category 1 incidents.
20. The Learning Model may not use event data to modify constitutional principles or security boundaries.

## Depends On

- **01_PRINCIPLES.md**, **02_ARCHITECTURE.md**, **03_TECH_STACK.md**, **04_BUSINESS_OPERATING_MODEL.md**, **05_AGENT_RUNTIME_FRAMEWORK.md**, **06_AGENT_OPERATING_MODEL.md**, **07_WORKFLOW_OPERATING_MODEL.md** — 08 is explicitly derived from all seven.

## Provides To

- **09_MEMORY_OPERATING_MODEL.md** — the source of truth for occurrence from which memory is formed as a curated, enriched, indexed projection.
- **10_KNOWLEDGE_OPERATING_MODEL.md** — the events that ultimately justify supporting memory and trigger revalidation, extraction, and deprecation.
- **11, 12, 13** — the lifecycle event substrate through which decisions, tool invocations, and learning cycles are triggered, announced, and audited.

## Key Definitions

| Term | Definition |
|------|------------|
| **Event** | An immutable record that something meaningful has occurred in the venture studio. |
| **Event Bus** | The central hub through which all events flow, mediating producers and consumers. |
| **Stream** | An ordered, append-only sequence of events within a domain category. |
| **Consumer Group** | A logical processing application that subscribes to a stream and distributes events among its members. |
| **Event ID** | The universally unique identifier of an event, serving as its idempotency key. |
| **Causation ID** | The Event ID of the event that directly caused this event. |
| **Correlation ID** | The Trace ID linking an event to the broader business operation. |
| **Schema Version** | The semantic version of the payload structure contract. |
| **Dead Letter** | An event that failed delivery or processing after maximum retries, quarantined for review. |
| **Replay** | The deliberate reconstruction of past behavior by reprocessing historical events. |
| **Backpressure** | The mechanism by which the event subsystem throttles producers when consumers cannot keep pace. |
| **At-Least-Once Delivery** | The guarantee that an event will be delivered to a consumer one or more times until acknowledged. |
| **Global Event** | An anonymized event promoted to system-wide visibility across all tenants. |

## Architectural Boundaries

- **Hub boundary:** the Event Bus mediates all event flow. No direct producer-to-consumer path exists.
- **Fact/command boundary:** events declare; they do not instruct. Command events are facts *about* commands.
- **Event/message boundary:** the model governs events only, not ordinary messages such as health probes or metric scrapes.
- **Truth boundary:** the event log is the source of truth; state is a derived projection. Events are guarded more strictly than state.
- **Immutability boundary:** publication freezes content and identity permanently. Correction is by new event only.
- **Routing boundary:** metadata only. Content-based routing is prohibited.
- **Delivery boundary:** at-least-once is guaranteed; exactly-once is not, and idempotency is the consumer's responsibility.
- **Ordering boundary:** total order within a stream; no global wall-clock order across streams.
- **Tenant boundary:** enforced at the routing layer; cross-tenant sharing requires anonymization and human approval.
- **Shedding boundary:** critical streams — commands, audits, business state transitions — are never shed.

## Implementation Statement

08_EVENT_OPERATING_MODEL.md defines the constitution of facts: identity, lifecycle, causality, durability, delivery, and governance. It states explicitly that it is not an implementation specification but a behavioral contract.

This document intentionally defines no implementation details.

---
---

# 09 — MEMORY OPERATING MODEL

> **Source integrity note.** The uploaded artifact for 09 terminates mid–Section 10 (Memory Ownership & Boundaries). The compression below reflects the artifact's complete ratified Table of Contents (whose section annotations are canonical text) and the full body text present through Section 9. Sections 10.1 through 30 — including the enumerated Non-Violable Memory Rules and the Memory Glossary — are not present in the artifact and are therefore represented by their declared Table of Contents scope only. No content has been invented.

## Purpose

To specify how memory behaves inside Agent OS: how organizational experience is captured, validated, linked, decayed, and retrieved to enable continuous learning across autonomous businesses.

## Mission

The memory subsystem exists to **preserve, validate, and make retrievable the complete organizational experience of the venture studio** so that every agent, workflow, and business operates with the accumulated wisdom of all prior execution, subject to absolute constraints of ownership, privacy, and human sovereignty.

**Permanent Objectives**, ordered by priority: Continuity; Contextual Fidelity; Validated Recall; Ownership Enforcement; Decay Discipline; Cross-Business Pollination.

**Objective Conflict Resolution Order:** Human Sovereignty > Ownership Enforcement > Validated Recall > Continuity > Decay Discipline > Cross-Business Pollination. The memory subsystem may not sacrifice privacy or truth for availability.

## Responsibilities

Per the document's ratified Table of Contents, the memory subsystem is responsible for:

- **Memory Philosophy** — defining what memory is and why it is distinct from storage, knowledge, events, and state.
- **Memory Identity** — the immutable identity primitives and attribution requirements that make memory auditable and non-repudiable.
- **Memory Classification** — categorizing by semantic role, structural form, sensitivity, and persistence model to enable differentiated governance and retrieval.
- **Memory Architecture & Topology** and **Memory Hierarchy** — the stratified tiers from ephemeral working context to permanent organizational record and the rules governing movement between them.
- **Memory Lifecycle** and **States & Transitions** — the complete lifespan of a memory entry and the finite state machine that guards against illegal or ambiguous states.
- **Memory Ownership & Boundaries** — who may possess memory, how ownership is inherited and transferred, and the absolute isolation boundaries between tenants, businesses, and agents.
- **Memory Context & Provenance**, **Relationships & Linking**, **Causality & Lineage** — traceability from any entry back to its originating event, workflow, agent, and decision, and the web of semantic and causal relationships enabling associative reasoning.
- **Memory Durability & Immutability**, **Creation & Acquisition**, **Validation & Confidence**.
- **Memory Freshness, Aging & Decay**; **Promotion, Archiving & Forgetting**; **Consolidation**; **Sharing & Isolation**.
- **Memory Governance & Oversight**, **Security**, **Observability**, **Reliability & Fault Tolerance**, **Performance Characteristics**, **Recovery**.
- **Memory Learning & Knowledge Compounding** and **Memory Evolution** — adaptation through schema maturation and emergent relationship types without retroactively altering historical records.

## Non-Responsibilities

- Does not specify implementation; it is a behavioral contract.
- Does not govern raw data. "Raw data may be stored, but it does not become memory until it has been formed, validated, and attributed."
- Does not contain knowledge. Knowledge extraction is governed by the Learning Model and the Knowledge Base; "Memory may be raw, contradictory, or uncertain; knowledge must be validated and confident."
- Does not replace the event log. Events are the source of truth; memory is "a curated, indexed, and contextualized projection of events optimized for agent consumption."
- Does not permit direct access. "No agent, workflow, or service accesses memory directly."

## Core Concepts

**The Organizational Experience Metaphor.** Memory is persistent organizational experience — "the living tissue of the organization." Without memory, every agent execution begins as a blank slate and every business loses its identity the moment its current tasks complete.

**Memory vs. Storage.** "Storage preserves bytes; memory preserves meaning."

**Memory vs. Knowledge.** Memory is the substrate; knowledge is the refined product. Memory records that "Agent A observed outcome B on Tuesday"; knowledge asserts that "Approach C reliably produces outcome B."

**Memory vs. Events / vs. State.** "If the event log is the nervous system's electrical signal, memory is the brain's lasting impression of that signal." State can be derived from memory, but memory cannot be derived from state. "Memory corruption is irreparable. Therefore, memory is guarded more strictly than state."

**Memory as Competitive Moat.** "Memory compounds. The system must treat memory as its most valuable asset, prioritizing its preservation, validation, and availability above operational convenience."

**Memory Identity Primitives.** Memory ID, Memory Type (hierarchical, e.g. `episodic.execution`, `semantic.fact`, `procedural.pattern`), Schema Version, Timestamp (occurrence time, distinct from formation or retrieval time), Source Identity, Tenant/Business/Workspace IDs, Confidence Score (0.0–1.0), Validity Period, Lineage Reference. Identity persists a minimum of seven years. "A memory entry is never anonymous."

**Classification by Semantic Role.** Episodic ("What happened"), Semantic ("What is true"), Procedural ("How to succeed"), Relational ("What relates to what"), Strategic ("Why we chose this path"), Failure ("What to avoid"). By structural form: Atomic, Composite, Narrative, Graph Edge. By sensitivity: Public, Tenant-Scoped, Restricted. By persistence model: Working, Durable, Semantic, Cold.

**Architecture & Topology.** **Gateway-Mediated Access** — the Memory Gateway is "the sole boundary between the runtime and the memory substrate," enforcing schema validation, ownership checks, tier routing, and audit logging. Producer-Consumer Topology. Boundary Enforcement across Tenant, Business, Agent, and Tier boundaries. **Relationship to Event Bus and Knowledge Base:** the pipeline is strictly unidirectional — **Events → Memory → Knowledge**. "Corrections flow backward as new events, not as mutations."

**Memory Hierarchy.** Tier 1 Working Memory (active execution context; ephemeral in service but durable against crashes); Tier 2 Durable Memory (validated, committed organizational experience; survives business sunsets and agent retirements); Tier 3 Semantic Memory (the associative retrieval tier enabling non-obvious discovery); Tier 4 Cold Memory (archival, never destroyed before the statutory retention period). **Tier Movement Governance:** movement is governed by lifecycle rules, not merely by time, and tier movement is itself a logged, auditable memory operation.

**Memory Lifecycle.** Conception → Formation (structure, not validation) → Validation (assigning initial confidence score and validity period; failures quarantined, not committed) → Integration ("An unlinked memory entry is incomplete") → Activation → Decay ("Decay is not deletion; it is degradation") → Disposition.

**Canonical States.** Draft, Validated, Linked, Active, Stale, Archived, Purged, with explicit transition guards (Draft → Validated requires schema compliance, complete source attribution, and initial confidence ≥0.5; Stale → Active is permitted where revalidation confirms renewed relevance). **State Immutability:** once an entry enters Validated, its core identity and payload are immutable; "A correcting entry is a new memory entry linked to the original, not a mutation." **Emergency Transitions** (e.g. Active → Purged for legal takedown) require Class D authority and are logged as constitutional exceptions; the original entry identity remains in the audit trail.

**Memory Ownership & Boundaries.** *(Section 10 heading is present in the artifact; its body is not.)*

## Constitutional Guarantees

The following guarantees are stated in the body text present in the artifact:

1. **Gateway Exclusivity** — no agent, workflow, or service accesses memory directly; all operations flow through the Memory Gateway.
2. **Unidirectional Pipeline** — Events → Memory → Knowledge. Knowledge does not mutate memory; corrections flow backward as new events, not as mutations.
3. **Non-Anonymity** — the runtime does not permit anonymous or pseudonymous memory. Identity is the foundation of trust in the memory system.
4. **Identity Persistence** — memory identity persists for the statutory retention period, minimum seven years, regardless of active status.
5. **Committed Immutability** — once an entry enters Validated, its core identity and payload are immutable; correction is by new, linked entry only.
6. **Formation Discipline** — unstructured or schema-violating captures are rejected at the Gateway; entries failing validation are quarantined, not committed to Durable memory.
7. **Integration Requirement** — an unlinked memory entry is incomplete; activation follows integration.
8. **Boundary Enforcement** — the Gateway rejects cross-tenant access without explicit anonymization and human approval, filters retrieval to the requesting business absent a shared workspace grant, and prevents agents from accessing Private memory of other agents.
9. **Emergency Transition Control** — bypassing normal lifecycle flow requires Class D authority and is logged as a constitutional exception with identity retained in the audit trail.
10. **Purge Governance** — Archived → Purged requires that the statutory retention period has elapsed **and** that human or policy approval for destruction exists.

> The document's ratified Table of Contents declares **Section 29, Non-Violable Memory Rules** — "the absolute rules governing memory behavior, violation of which constitutes a Category 1 incident." That enumerated list is not present in the uploaded artifact and is therefore not reproduced here. The guarantees above are drawn solely from body text that is present.

## Depends On

- **01_PRINCIPLES.md** through **08_EVENT_OPERATING_MODEL.md** — 09 is explicitly derived from all eight, per its Preamble.

## Provides To

- **10_KNOWLEDGE_OPERATING_MODEL.md** — the evidentiary substrate. "Knowledge consumes memory through governed extraction pipelines."
- **11_DECISION_OPERATING_MODEL.md** — episodic context and prior decision history queried when evidence is sparse.
- **13_LEARNING_OPERATING_MODEL.md** — the raw experience from which patterns are extracted, queried through the Memory Gateway with scoped, time-bounded, context-rich retrieval.

## Key Definitions

> The document's Table of Contents declares **Section 30, Appendix: Memory Glossary** — "canonical definitions for all memory-specific terminology used throughout the Agent OS architecture." That glossary table is not present in the uploaded artifact. The definitions below are drawn from the body text that is present.

| Term | Definition |
|------|------------|
| **Memory** | Persistent organizational experience: the accumulated record of what the venture studio has done, observed, and decided. |
| **Memory Gateway** | The sole boundary between the runtime and the memory substrate, enforcing schema validation, ownership checks, tier routing, and audit logging. |
| **Working Memory** | Tier 1 — the active execution context of agents and workflows; highest-velocity, lowest-latency. |
| **Durable Memory** | Tier 2 — validated, committed organizational experience; the primary repository of organizational history. |
| **Semantic Memory** | Tier 3 — the associative retrieval tier enabling non-obvious experiential discovery. |
| **Cold Memory** | Tier 4 — the archival tier retained for compliance, forensic investigation, and long-term learning. |
| **Episodic / Semantic / Procedural / Relational / Strategic / Failure Memory** | The six semantic roles memory plays in organizational cognition. |
| **Confidence Score** | A quantitative measure (0.0–1.0) of a memory entry's reliability at time of formation. |
| **Validity Period** | The temporal window during which a memory entry is considered potentially relevant. |
| **Lineage Reference** | The immutable identifier linking a memory entry to its originating event or decision journal. |
| **Decay** | The progressive reduction of an entry's relevance, confidence, and accessibility over time — degradation, not deletion. |
| **Tier Movement** | The governed promotion or demotion of an entry between hierarchy tiers; itself a logged memory operation. |

## Architectural Boundaries

- **Gateway boundary:** the Memory Gateway is the sole access path. No direct substrate access by any agent, workflow, or service.
- **Pipeline boundary:** strictly unidirectional — Events → Memory → Knowledge. Memory does not contain knowledge; knowledge does not mutate memory.
- **Storage boundary:** storage is passive retention of bits; memory is active, interpretable experience. Raw data is not memory until formed, validated, and attributed.
- **Truth boundary:** events are the source of truth; memory is a curated projection. Memory is guarded more strictly than state.
- **Tenant boundary:** cross-tenant access is rejected absent explicit anonymization and human approval.
- **Business boundary:** retrieval is filtered to the requesting business absent a shared workspace grant.
- **Agent boundary:** Private memory of one agent is inaccessible to another.
- **Tier boundary:** consumer access to persistence tiers is controlled by role and task classification.
- **Immutability boundary:** Validated entries are frozen; correction is by new linked entry only.

## Implementation Statement

09_MEMORY_OPERATING_MODEL.md defines the constitution of organizational experience: philosophy, identity, classification, topology, hierarchy, lifecycle, and state governance. It states explicitly that it is not an implementation specification but a behavioral contract.

This document intentionally defines no implementation details.

---
---

# 10 — KNOWLEDGE OPERATING MODEL

## Purpose

To specify how knowledge behaves inside Agent OS: how validated belief is extracted from experience, how organizational reasoning is enabled, how contradictions are resolved, and how the venture studio compounds wisdom without sacrificing truth.

## Mission

The knowledge subsystem exists to **maintain a coherent, validated, and accessible body of organizational belief** that enables agents and humans to reason effectively, decide soundly, and compound learning across the portfolio, subject to absolute constraints of evidence, ownership, privacy, and human sovereignty.

**Permanent Objectives**, ordered by priority: Epistemic Coherence; Validated Authority; Organizational Reasoning; Falsifiability Maintenance; Bounded Growth; Cross-Business Generalization.

**Objective Conflict Resolution Order:** Human Sovereignty > Epistemic Coherence > Validated Authority > Organizational Reasoning > Falsifiability Maintenance > Bounded Growth > Cross-Business Generalization. The knowledge subsystem may not sacrifice truth or coherence for convenience.

## Responsibilities

- Define **Knowledge Philosophy** and the distinctions Knowledge vs. Memory, vs. Events, vs. State, vs. Data, plus Knowledge as Organizational Reasoning Substrate.
- Define **Knowledge Identity**, **Classification**, and **Architecture & Topology**.
- Define the **Knowledge Lifecycle** and **States & Transitions**.
- Define **Knowledge Producers** and **Consumers**: identity, responsibilities, boundaries, failure handling, query patterns, isolation.
- Define **Ownership & Boundaries**, **Context & Provenance**, **Causality & Lineage**.
- Define **Validation & Confidence** and **Contradiction & Reconciliation**.
- Define **Ontology & Schema** and the **Knowledge Graph**.
- Define **Durability & Immutability**, **Retention & Deprecation**.
- Define **Governance & Oversight**, **Security**, **Observability**, **Reliability & Fault Tolerance**, **Performance Characteristics**, and **Learning & Compounding**.

## Non-Responsibilities

- Does not specify implementation; it is a behavioral contract.
- Does not govern memory. "The Memory Operating Model governs memory. The Knowledge Operating Model governs knowledge. They are not interchangeable."
- Does not govern raw data. "Data must pass through extraction, validation, and integration before it enters the Knowledge Base."
- Does not mutate memory or events. "Knowledge does not mutate memory."
- Does not accept beliefs from the Learning Model directly — "it may not insert beliefs directly into the Knowledge Base."
- Does not self-modify its ontology. "The ontology is not self-modifying."

## Core Concepts

**The Validated Belief Metaphor.** "A belief without evidence is speculation. A belief without confidence is noise. A belief that cannot be falsified is dogma. Knowledge rejects all three."

**Knowledge vs. Memory.** Memory asks *What happened?*; Knowledge asks *What is true?* "An agent operating on memory alone is a historian; an agent operating on knowledge is a strategist."

**Knowledge vs. Events.** "The event is indisputable; the knowledge is falsifiable."

**Knowledge Identity Primitives.** Knowledge ID (lexicographically sortable), Knowledge Type (hierarchical dot-notation, e.g. `belief.market.trend`, `heuristic.deployment.retry`), Schema Version, Timestamp (validation time), Source Memory IDs, Source Event IDs, Extractor Identity, Tenant/Business/Workspace IDs, Confidence Score, Validity Period, **Falsifiability Conditions**, Lineage Reference. Persists minimum seven years.

**Classification by Semantic Role.** Factual, Causal, Normative, Predictive, Definitional. By structural form: Atomic, Composite, Relational, Narrative. By sensitivity: Public, Tenant-Scoped, Restricted. By persistence model: Active, Durable, Archival, Ephemeral.

**Architecture & Topology.** **Knowledge Gateway** as the sole boundary between the runtime and the knowledge substrate, enforcing schema validation, ownership checks, confidence thresholds, and audit logging. Boundary Enforcement across Tenant, Business, Agent, and **Confidence** boundaries. Relationship to Memory (strictly unidirectional Events → Memory → Knowledge), to Events (consumed only to trigger revalidation, extraction, or deprecation; emits `knowledge.belief.validated`, `knowledge.contradiction.detected`, `knowledge.belief.deprecated`), and to Learning.

**Knowledge Lifecycle.** Extraction ("an epistemic act that selects, interprets, and frames experience") → Hypothesis Formation (ephemeral; unavailable for agent reasoning) → Validation → Integration → Promotion (not automatic upon validation) → Active Use → Revalidation → Deprecation ("not deletion; it is epistemic correction") → Archival → Disposition.

**Canonical States.** Hypothesis, Validated, Canonical, Contradicted, Deprecated, Superseded, Archived, Purged, with explicit transition guards (Hypothesis → Validated requires evidence sufficiency, schema compliance, confidence ≥0.6, and defined falsifiability conditions; Validated → Canonical requires integration complete, no unresolved contradictions, and human approval if Restricted sensitivity). **State Immutability** and **Emergency Transitions** requiring Class D authority.

**Producers and Consumers.** Producer responsibilities: Schema Compliance, Evidence Citation, Confidence Justification, Falsifiability Specification, Tenant Scoping, Contradiction Awareness. Consumer responsibilities: Confidence Threshold Respect, Uncertainty Acknowledgment ("A belief with confidence 0.75 must be treated as provisional, not certain"), Scope Adherence, Failure Signaling, Idempotent Consumption.

**Ownership & Boundaries.** Tenant ownership; Tenant Isolation enforced at the query layer; Cross-Business Boundaries requiring shared workspace with bilateral grants; Global Knowledge (anonymized, validated, human-approved, system-owned); Knowledge Delegation (time-bounded, scope-limited, logged; does not transfer ownership).

**Context & Provenance.** Extractor Identity, Validator Identity, Source Memory IDs, Source Event IDs, Extraction Timestamp, Validation Timestamp, Business Context, Falsifiability Conditions. "Context is not the payload; it is the interpretive frame without which a belief is meaningless." Context Propagation creates "an unbroken epistemic graph from raw observation to derived inference." Context Budget.

**Causality & Lineage.** Causal Chains established by explicit lineage references, not inference. **Forensic Reconstruction** — the subsystem must be able to answer, for any canonical belief: *Why do we believe this?* **Correction Without Erasure** — "The old entry remains in the Knowledge Base as a record of what was once believed."

**Validation & Confidence.** Four validation dimensions: Evidentiary Sufficiency, Cross-Reference Consistency, Schema Conformance, Falsifiability Test. Confidence bands:

| Range | Status | Usage |
|-------|--------|-------|
| 0.00–0.59 | Hypothesis | Not available for reasoning; under evaluation. |
| 0.60–0.79 | Validated | Available for reasoning; must be flagged as provisional. |
| 0.80–0.94 | Canonical | Standard basis for reasoning and decision-making. |
| 0.95–1.00 | Axiomatic | Strategic or definitional; requires human ratification. |

Continuous Revalidation (domain-dependent frequency). Validation Failure Handling — quarantined for review, not destroyed.

**Contradiction & Reconciliation.** Contradiction Detection triggers a reconciliation workflow. Strategies: Supersession, Scope Narrowing, Confidence Adjustment, Human Arbitration. **Arbitration is required** when both beliefs have confidence ≥0.85, when Restricted knowledge is involved, when the contradiction spans business boundaries within a tenant, or when automated reconciliation has failed. Arbitration produces a binding resolution logged as a new knowledge entry with Class D authority. Reconciliation Logging is immutable.

**Ontology & Schema.** The ontology is "the grammar of organizational reasoning," comprising entity classes, relationship types, and belief categories. Schema Registry; semantic versioning (minor additive; major breaking, requiring migration plan, deprecation of at least one release cycle, and human approval if strategic or safety-critical). **Ontology Governance:** changes require human approval; the Learning Model may propose extensions but adoption requires validation and ratification.

**Knowledge Graph.** Nodes are knowledge entries; edges are typed relationships — Causal, Hierarchical, Contradictory, Analogical, Temporal, Associative, Supersedes. Traversal is governed by scope. **Graph Integrity** constraints: no orphaned canonical nodes, no unresolved contradictory cycles, no dangling supersession references.

**Durability & Immutability.** Durability achieved before promotion to Canonical begins. "A Validated belief may never be modified, overwritten, or deleted." Append-Only Correction Model. Durability tiers: Active, Durable, Archival.

**Retention & Deprecation.** Retention policy by category (Factual/Causal/Normative: until deprecated or superseded, 2 years durable, 7 years archival; Predictive: until validity period expires; Definitional: indefinite ontology retention). Deprecation; Forgetting ("Axiomatic and definitional knowledge is never purged; it is versioned"); Right to Be Forgotten Compliance (audit trail retains identity and justification but not payload).

**Governance, Security, Observability, Reliability, Performance, Compounding.** Self-Audit; Drift Detection; Anomaly Response (Volume, Schema, Contradiction, Confidence). Authentication, Authorization at formation and consumption, Encryption, Input Sanitization, Audit of Knowledge Access. Metrics: Epistemic Health, Graph Health, Operational Health, Consumer Health. Graceful Degradation — fallback to Memory with explicit uncertainty flags; "No workflow may fail solely because knowledge is unreachable, though it may pause if the missing knowledge is safety-critical." Failure classification includes a distinct **Epistemic** category (quarantine affected beliefs, suspend extractor, immediate alert). Latency: canonical belief query p50 50ms / p99 200ms / max 500ms; 3-hop graph traversal p50 100ms / p99 500ms / max 2s. Throughput: 1,000 hypotheses/second formation; 10,000 canonical queries/second; 5,000 graph traversals/second. Learning as Compounding — "Learning over raw memory is noisy; learning over knowledge is signal."

## Constitutional Guarantees

**Non-Violable Knowledge Rules.** Violation constitutes a Category 1 incident:

1. No knowledge entry may be formed without a registered schema, authenticated producer identity, and complete evidentiary citation.
2. No validated belief may be modified, overwritten, or deleted after formation.
3. No hypothesis may be promoted to Canonical without passing validation and integration.
4. No canonical belief may remain in the active set while an unresolved contradiction exists against it.
5. No belief may be formed or consumed without a defined confidence score and falsifiability conditions.
6. No knowledge may cross tenant boundaries without explicit anonymization and human approval.
7. No producer may form knowledge outside its declared scope and permission boundaries.
8. No consumer may access knowledge outside its subscribed scope, sensitivity level, and confidence threshold.
9. No belief may be presented as canonical if its confidence score is below 0.60.
10. No speculative or hypothetical assertion may be presented as validated knowledge to any consumer.
11. No knowledge may be formed from unvalidated external data or unsanitized memory.
12. No ontology or schema change may be deployed without backward compatibility, migration planning, and human approval if strategic or safety-critical.
13. No autonomous system may modify the organizational ontology without human ratification.
14. No knowledge may be purged before its statutory retention period without Class D human authority and complete audit logging.
15. No anonymous or pseudonymous knowledge formation or consumption is permitted.
16. No knowledge may bypass the Knowledge Gateway for direct producer-to-consumer communication.
17. Knowledge lineage and causality chains must be preserved across all formations, derivations, and deprecations.
18. No belief may be deprecated without a justification entry linked via lineage.
19. Knowledge governance anomalies must be escalated as Category 1 incidents.
20. The Learning Model may not use knowledge formation to modify constitutional principles, security boundaries, or human approval gates.

## Depends On

- **01_PRINCIPLES.md** through **09_MEMORY_OPERATING_MODEL.md** — 10 is explicitly derived from all nine.
- **09** in particular supplies the evidentiary substrate; the pipeline Events → Memory → Knowledge is strictly unidirectional.

## Provides To

- **11_DECISION_OPERATING_MODEL.md** — canonical beliefs, confidence scores, and contradiction status as the primary evidence for commitment. "Decisions must be grounded in canonical beliefs from the Knowledge Gateway."
- **13_LEARNING_OPERATING_MODEL.md** — the reasoning substrate over which the Learning Model identifies patterns, refines heuristics, and improves agent behavior.
- **All reasoning consumers** — agents, workflow engines, and human strategists.

## Key Definitions

| Term | Definition |
|------|------------|
| **Knowledge** | A validated, structured, canonical belief held by the organization, supported by evidence and bounded by confidence. |
| **Knowledge Base** | The complete set of knowledge entries governed by the Knowledge Operating Model. |
| **Knowledge Gateway** | The unified access layer through which all knowledge operations are mediated, validated, and audited. |
| **Belief** | An organizational assertion about reality, framed within a registered schema and assigned a confidence score. |
| **Hypothesis** | A provisional belief extracted from memory but not yet validated; unavailable for reasoning. |
| **Canonical** | The state of a belief validated, integrated into the ontology and knowledge graph, and available for reasoning. |
| **Deprecated** | The state of a belief falsified, invalidated, or rendered obsolete; retained but excluded from active reasoning. |
| **Superseded** | The state of a belief replaced by a newer belief; linked via lineage to its successor. |
| **Confidence Score** | A quantitative measure (0.0–1.0) of a belief's reliability, assigned at validation and updated during revalidation. |
| **Falsifiability** | The property specifying explicit, observable conditions under which a belief would be proven false. |
| **Ontology** | The organizational taxonomy of entities, relationships, and belief types that structures the knowledge graph. |
| **Knowledge Graph** | The web of validated beliefs and their typed relationships, enabling inferential reasoning. |
| **Extraction** | The process of distilling candidate beliefs from organizational memory. |
| **Validation** | The process of assessing a hypothesis against evidence, consistency, schema, and falsifiability. |
| **Revalidation** | The continuous review of canonical beliefs against new evidence and elapsed time. |
| **Contradiction** | A state in which two or more canonical beliefs assert incompatible truths. |
| **Reconciliation** | The process of resolving contradictions through supersession, scope narrowing, confidence adjustment, or human arbitration. |
| **Lineage** | The unbroken chain of references from a knowledge entry back to its originating memory, events, and predecessor beliefs. |
| **Epistemic Coherence** | The property of the knowledge base being internally consistent, with no unresolved contradictions in the canonical set. |
| **Evidentiary Basis** | The complete set of source memory entries and events that justify a belief. |
| **Provenance** | The complete record of a belief's origin, including extractor, validator, timestamps, and business context. |
| **Context Budget** | The maximum allowable size of provenance and contextual metadata attached to a knowledge entry. |
| **Global Knowledge** | Anonymized, validated beliefs promoted to system-wide visibility across all tenants. |
| **Knowledge Compounding** | The process by which validated beliefs are mined for patterns, refined through feedback loops, and transformed into organizational intelligence. |

## Architectural Boundaries

- **Gateway boundary:** the Knowledge Gateway is the sole path. No direct producer-to-consumer communication.
- **Pipeline boundary:** Events → Memory → Knowledge, strictly unidirectional. Knowledge does not mutate memory.
- **Substrate boundary:** memory is the substrate, knowledge the refined product. They are not interchangeable.
- **Confidence boundary:** the Gateway blocks consumption of beliefs below the consumer's declared confidence threshold; nothing below 0.60 may be presented as canonical.
- **Coherence boundary:** no canonical belief may remain active while an unresolved contradiction exists against it.
- **Falsifiability boundary:** a belief that cannot be falsified is not knowledge.
- **Ontology boundary:** the ontology is not self-modifying. The Learning Model may propose; only human ratification adopts.
- **Learning boundary:** learning-derived hypotheses pass through the same validation pipeline as manually extracted knowledge; no direct insertion.
- **Tenant boundary:** enforced at the query layer; cross-tenant sharing requires anonymization and human approval.
- **Immutability boundary:** Validated beliefs are frozen. Correction is by new, linked entry only.

## Implementation Statement

10_KNOWLEDGE_OPERATING_MODEL.md defines the constitution of organizational belief: identity, classification, lifecycle, validation, contradiction resolution, ontology, graph structure, and governance. It states explicitly that it is not an implementation specification but a behavioral contract.

This document intentionally defines no implementation details.

---
---

# 11 — DECISION OPERATING MODEL

## Purpose

To specify how commitments to action are formed, authorized, executed, reversed, and learned from inside Agent OS.

## Mission

The decision subsystem exists to ensure every commitment to action is **evidence-based, authority-bound, risk-aware, reversible by default, and accountable to human sovereignty**, while preserving the autonomous velocity required for portfolio growth.

**Permanent Objectives:** Commitment Integrity; Authority Enforcement; Evidence Grounding; Reversibility by Default; Portfolio Coherence; Human Sovereignty Preservation; Decision Velocity; Learning from Commitment.

**Objective Conflict Resolution Order:** Human Sovereignty > Authority Enforcement > Commitment Integrity > Evidence Grounding > Reversibility by Default > Portfolio Coherence > Decision Velocity > Learning from Commitment.

## Responsibilities

- Define **Decision Philosophy** and the distinctions Decision vs. Knowledge, vs. Runtime, vs. Agency, plus Decision as Sovereignty Preservation.
- Define **Decision Identity**, **Classification**, and **Architecture & Topology**.
- Define the **Decision Lifecycle** and **States & Transitions**.
- Define **Authority & Autonomy**, **Ownership & Boundaries**, **Context & Provenance**.
- Define **Evidence & Knowledge Consumption**, **Confidence & Uncertainty**, **Risk & Consequence**, **Objectives & Alignment**.
- Define **Options & Generation**, **Evaluation & Prioritization**, **Approval & Authorization**, **Delegation & Standing Orders**, **Escalation**.
- Define **Reversal & Compensation**, **Supersession**, **Auditability & Journals**.
- Define **Governance & Oversight**, **Security**, **Observability**, **Reliability & Fault Tolerance**, **Performance Characteristics**, **Learning & Improvement**, and **Portfolio, Business, Agent & Human Decision Integration**.

## Non-Responsibilities

- Does not specify implementation; it is a behavioral contract.
- Does not execute. "Runtime governs execution—the *how*. Decision governs whether work should be undertaken at all—the *whether*."
- Does not interfere with Runtime's execution mechanics. "Decision tracks execution status but does not interfere."
- Does not modify knowledge. "Decision consumes canonical beliefs, confidence scores, and contradiction status. It does not modify knowledge."
- Does not evaluate human decisions. "Human decisions are not evaluated by the Gateway; they are the terminal authority."
- Does not validate beliefs; that authority belongs to the Knowledge Gateway.

## Core Concepts

**The Commitment Metaphor.** "A decision is a governed commitment to a course of action. It is the moment the organization transitions from deliberation to obligation. Memory asks what happened; Knowledge asks what is true; Decision asks what shall be done." **Decision vs. Agency:** "An agent proposes; the Decision subsystem evaluates... Agency is capacity; Decision is permission." **Decision as Sovereignty Preservation:** "Decision is the constitutional checkpoint between human will and machine execution."

**Decision Identity Primitives.** Decision ID, Decision Type, Schema Version, Timestamp, Source Identity (proposer), **Authority Identity** (authorizer — human for Level 3/4), Tenant/Business/Workspace IDs, Decision Class, Autonomy Level, Confidence Score, Risk Score, **Reversibility Flag**, Lineage Reference, **Expected Outcome**, **Actual Outcome** (nullable until resolved). Persists minimum seven years.

**Classification.** By impact and reversibility — Class A Trivial (Level 1), B Operational (Level 2), C Strategic (Level 3), D Existential (Level 4). By scope: Portfolio, Business, Project, Task, Agent. By evidentiary burden: Evidence-Rich, Evidence-Sparse, Evidence-Contradictory. By temporal urgency: Routine, Expedited, Emergency, Panic.

**Architecture & Topology.** The **Decision Gateway** is "the sole boundary between deliberation and commitment," enforcing classification, authority verification, evidence validation, optionality checks, and audit logging. "Producers cannot commit directly to Runtime, and Runtime cannot execute non-trivial actions without a committed decision." Boundaries: Tenant, Business, Authority, Confidence. Relationships to Knowledge Gateway, Memory Gateway, Event Bus (`decision.proposed`, `decision.committed`, `decision.reversed`, `decision.superseded`), Runtime, and Human Interface.

**Decision Lifecycle.** Trigger → Option Generation → Evidence Assembly → Evaluation → Authority Resolution → Approval/Authorization → Commitment → Execution Tracking → Outcome Resolution → Disposition (Completed, Reversed, Superseded, or Rejected).

**Canonical States.** Proposed, Under Review, Approved, Committed, Executing, Completed, Reversed, Superseded, Rejected, Deferred, Escalated, each with an explicit transition guard table. Notably, *Under Review → Rejected* on "timeout without response (does NOT auto-approve for C/D)." **State Immutability** upon Committed. **Emergency Transitions** permitted only with Class D authority or Panic Protocol invocation, logged as constitutional exceptions.

**Authority Spectrum.**

| Level | Title | Scope | Boundaries |
|-------|-------|-------|------------|
| 1 | Agent Autonomous | Class A only; trivial, reversible, <$0.01 | No external impact; reversible within seconds. |
| 2 | Agent Delegated | Class A and B; reversible within 24h, <$10 | Internal impact only; no customer-facing changes; no capital deployment. |
| 3 | Human Approval | Class C; strategic, customer-facing, $10–$500 | Explicit human approval per decision; no batch auto-approval. |
| 4 | Human Sovereign | Class D; existential, irreversible, >$500 | Human only; runtime may propose but never commit; absolute veto preserved. |

**Confidence Requirements by Authority.** Level 1 ≥0.60; Level 2 ≥0.70; Level 3 ≥0.80 (low-confidence proposals must include explicit uncertainty acknowledgment); Level 4 ≥0.90 (evidence-contradictory proposals escalated regardless of nominal confidence). Confidence bands: <0.60 rejected or quarantined; 0.60–0.79 Class A/B only with uncertainty rider; 0.80–0.94 standard for C and most D; 0.95–1.00 reserved for axiomatic or definitional backing.

**Evidence.** Canonical Knowledge as Primary Evidence — "Hypotheses, quarantined beliefs, and unvalidated memory may not serve as sole evidence for Class B and above." Evidentiary Gap Handling (reject, escalate, or permit with an **uncertainty rider** and enhanced monitoring). Contradictory Evidence halts commitment. Evidence Sufficiency by Class: A none required; B at least one canonical belief or explicit gap flag; C multiple canonical beliefs or a strong single belief with falsifiability conditions met and no unresolved contradictions; D comprehensive evidentiary basis with cross-reference consistency, risk analysis, and documented alternatives.

**Risk & Consequence.** Risk dimensions: Financial, Operational, Reputational, Legal, Strategic. Risk classes: Negligible, Low, Moderate, High, Existential. **Risk-Adjusted Authority** — "A Class B decision with High risk is treated as Class C for authority purposes. A Class C decision with Existential risk is escalated to Class D." **Circuit Breakers** at portfolio level.

**Objectives & Alignment.** Portfolio Thinking; Mission Alignment; Strategic Optionality (decisions destroying optionality receive heightened scrutiny); Anti-Cannibalization.

**Options & Generation.** **Mandatory Multi-Option Requirement** — for Class B and above, at least two distinct options plus the null option; single-option proposals are rejected. Option Documentation. **Null Option** (maintain status quo) always evaluated as the baseline. Optionality Preservation.

**Evaluation & Prioritization.** Criteria: Objective Fit, Risk-Adjusted Return, Strategic Value, Resource Efficiency, Reversibility. Portfolio-Aware Scoring (concentration penalty, correlation-reduction bonus). Ranking and Recommendation — advisory for Class C and D; the authority makes the final commitment.

**Approval & Authorization.** Request contents; **Gate Enforcement** absolutely; Timeout Handling — Class C deferred, not approved; Class D rejected pending explicit human action; "never implicit consent." Batch Approval — batched items remain individually actionable and are never auto-approved as a group.

**Delegation & Standing Orders.** Scoped by tenant, business, decision type, and maximum cumulative impact; expire after 30 days unless renewed; revocable at any time, with revocation not affecting decisions already committed under the order; validated per invocation.

**Escalation.** Triggers: Authority Insufficiency, Low Confidence, High Risk, Contradictory Evidence, Boundary Breach, Anomaly Detection. Path: Agent → Team Lead → Business Manager → Portfolio Architect → Human Sovereign. Escalation Packaging. **Escalation Timeout** — "the decision is escalated further, not approved by default."

**Reversal & Compensation.** Reversibility by Default (Class A and B within 24 hours unless designated otherwise). **Compensation Logic** must be verified to exist before a reversible decision is committed — "Without compensation logic, the decision is treated as irreversible." Irreversibility Designation requires explicit human designation and acknowledged consequence review. Reversal is itself a new decision entry linked via lineage.

**Supersession.** Supersession is "epistemic and operational succession," not erasure. Lineage Preservation. Resource Reallocation (above threshold requires human approval).

**Auditability & Journals.** Journal contents; append-only immutability; minimum seven-year retention with superseded, reversed, and rejected decisions retained indefinitely; forensic reconstruction of why any commitment was made.

**Governance, Security, Observability, Reliability, Performance, Learning.** Self-Audit; **Drift Detection** for autonomy drift — "agents proposing decisions just below escalation thresholds, confidence inflation to bypass human approval, or standing orders being stretched beyond intent." Anomaly Response (Volume, Authority, Confidence, Reversal). Integrity Protection — "No decision may be repudiated by its authorizer." Graceful Degradation — Runtime continues previously committed decisions but halts new non-trivial commitments. Latency: Class A proposal→commitment p50 100ms / p99 500ms / max 2s; Class D package assembly p50 2s / p99 10s / max 60s. Throughput: 1,000 Class A/B proposals per second; 100 Class C/D packages per minute; 10,000+ concurrent active decisions. Outcome Attribution; Feedback Loops into Knowledge, Authority, Standing Orders, and Portfolio; Bounded Learning.

**Layer Integration.** Portfolio Strategic Decisions (Class D); Business Tactical Decisions (typically Class C); Agent Operational Decisions (Class A or B); Human Sovereign Decisions. **Layer Interaction:** "Lower layers propose; higher layers commit or escalate."

## Constitutional Guarantees

**Non-Violable Decision Rules.** Violation constitutes a Category 1 incident:

1. No decision may be formed without a unique identity, authenticated source, and documented evidence or explicit gap flag.
2. No Class C or Class D decision may be committed without explicit human approval.
3. No approval gate may be auto-approved on timeout, inferred consent, or creative interpretation.
4. No irreversible action may be committed without explicit human designation and acknowledged consequence review.
5. No agent may commit a decision beyond its constitutional autonomy level.
6. No decision may bypass the Decision Gateway for direct producer-to-Runtime commitment.
7. No decision journal may be modified, overwritten, or deleted after formation.
8. No decision may proceed on unresolved contradictory evidence without human arbitration.
9. No Class B or higher decision may be committed with only a single option documented.
10. No decision may be formed without a confidence score and, for Class B+, a risk assessment.
11. No standing order may exceed 30 days without explicit renewal.
12. No decision may violate portfolio-level circuit breakers or concentration limits.
13. No anonymous or pseudonymous decision formation or authorization is permitted.
14. No decision may cross tenant boundaries without explicit human approval and isolation review.
15. No decision may suppress uncertainty or present speculative evidence as canonical knowledge.
16. No decision may be committed without a documented expected outcome.
17. No reversible decision may be committed without pre-positioned compensation logic.
18. No decision may override constitutional principles, security boundaries, or human sovereignty.
19. No decision failure may remain unclassified or unalerted for more than 60 seconds.
20. The Panic Protocol must halt all active decision commitment within 5 seconds of invocation.

## Depends On

- **01_PRINCIPLES.md** through **10_KNOWLEDGE_OPERATING_MODEL.md** — 11 is explicitly derived from all ten.
- **10** in particular supplies the canonical beliefs, confidence scores, and contradiction status that constitute primary evidence.

## Provides To

- **12_TOOL_OPERATING_MODEL.md** — the committed decision record whose authority every tool invocation must verify. "Runtime cannot execute non-trivial actions without a committed decision."
- **13_LEARNING_OPERATING_MODEL.md** — decision journals as "the canonical record of expected vs. actual outcomes" for attribution.
- **Runtime** — committed decisions emitted for execution.

## Key Definitions

| Term | Definition |
|------|------------|
| **Decision** | A governed, accountable commitment to a course of action based on canonical knowledge, confidence, and constitutional authority. |
| **Decision Gateway** | The unified access layer through which all decision operations are mediated, validated, and audited. |
| **Decision Class** | The categorization of a decision by impact and reversibility (A, B, C, D). |
| **Autonomy Level** | The authority tier (1–4) determining which decision classes an entity may commit. |
| **Commitment** | The binding emission of a decision to Runtime for execution. |
| **Reversibility** | The property of a decision permitting undoing within a defined window via compensation logic. |
| **Compensation Logic** | The pre-defined procedure to undo a reversible decision and restore prior state. |
| **Standing Order** | A pre-approved rule allowing limited autonomous commitment to Class C decisions within defined boundaries. |
| **Decision Journal** | An immutable record of a decision's full lifecycle, including evidence, rationale, and outcome. |
| **Escalation** | The upward routing of a decision to higher authority due to risk, confidence, or boundary conditions. |
| **Supersession** | The replacement of an active or completed decision by a newer decision, with lineage preserved. |
| **Expected Outcome** | The predicted result of a decision, documented before execution. |
| **Actual Outcome** | The observed result of a decision, recorded after execution completion. |
| **Evidence Gap** | An explicit acknowledgment that canonical knowledge is insufficient to fully support a proposal. |
| **Uncertainty Rider** | A declaration of known unknowns and sensitivity conditions attached to a low-confidence decision. |
| **Circuit Breaker** | A portfolio-level limit that halts commitments when risk concentration or capital exposure exceeds threshold. |
| **Panic Protocol** | The mechanism by which a human operator halts all autonomous commitment and defers active decisions. |

## Architectural Boundaries

- **Deliberation/commitment boundary:** the Decision Gateway is the sole passage. Producers cannot commit directly to Runtime.
- **Whether/how boundary:** Decision governs *whether*; Runtime governs *how*. Decision tracks execution status but does not interfere with execution mechanics.
- **Capacity/permission boundary:** agency is capacity; Decision is permission.
- **Evidence boundary:** hypotheses, quarantined beliefs, and unvalidated memory may not serve as sole evidence for Class B and above.
- **Authority boundary:** risk-adjusted — a Class B decision at High risk is treated as Class C; a Class C decision at Existential risk escalates to Class D.
- **Optionality boundary:** Class B and above require at least two distinct options plus the null option.
- **Reversibility boundary:** without pre-positioned compensation logic, a decision is treated as irreversible; irreversibility requires explicit human designation.
- **Timeout boundary:** timeout defers or rejects; it never approves.
- **Terminal authority boundary:** human decisions are not evaluated by the Gateway.
- **Learning boundary:** the subsystem may not auto-elevate agent autonomy, bypass approval gates, or shorten reversibility windows.

## Implementation Statement

11_DECISION_OPERATING_MODEL.md defines the constitution of commitment: identity, classification, lifecycle, authority, evidence, risk, options, approval, reversal, supersession, and governance. It states explicitly that where it is silent the constitution governs, and where it speaks it is binding.

This document intentionally defines no implementation details.

---
---

# 12 — TOOL OPERATING MODEL

## Purpose

To specify how Agent OS interacts with the external world through governed, identifiable, and accountable capabilities.

## Mission

The tool subsystem exists to ensure every interaction between Agent OS and the external world is **authorized by a valid decision, bounded by a declared capability contract, isolated within an appropriate sandbox, attributable to its consumer and authorizer, and economically controlled**.

**Permanent Objectives:** Boundary Integrity; Authority Verification; Economic Control; Sandbox Enforcement; Attribution Completeness; Reversibility Support; Trust Preservation; Tenant Isolation; Capability Fidelity; Knowledge Production.

**Objective Conflict Resolution Order:** Boundary Integrity > Authority Verification > Sandbox Enforcement > Tenant Isolation > Economic Control > Attribution Completeness > Reversibility Support > Trust Preservation > Capability Fidelity > Knowledge Production.

## Responsibilities

- Define **Tool Philosophy** and the distinctions Tool vs. Agent, vs. Workflow, vs. Decision, vs. Runtime, plus Tool as Organizational Asset.
- Define **Tool Identity**, **Classification**, **Architecture & Topology**, and **Tool Anatomy**.
- Define the **Tool Lifecycle** and **States & Transitions**.
- Define **Ownership & Boundaries**, the **Capability Model**, **Registration**, **Discovery**, and **Selection**.
- Define **Permissions & Authorization**, **Trust & Reputation**, and the **Invocation Contract**.
- Define **Composition**, **Context & Constraints**, **Availability & Health**, **Reliability & Resilience**, **Performance Characteristics**.
- Define **Cost & Economics** and the **Tool Marketplace**.
- Define **Security**, **Auditability & Lineage**, **Observability**, **Evolution & Versioning**, **Deprecation & Replacement**, **Learning & Improvement**.
- Define **Human**, **Agent**, and **Workflow Tool Integration**.

## Non-Responsibilities

- Does not specify implementation; it is a behavioral contract.
- Does not evaluate risk or alternatives. "The tool does not evaluate risk or alternatives; it verifies that the decision record exists, matches the tool's risk class, and carries valid authority before executing."
- Does not define runtime infrastructure. "The Runtime Framework defines how the highway operates"; 12 defines what vehicles may enter it.
- Does not make policy at the Executor. "The Executor receives instructions from the Gateway; it does not evaluate authority or make policy decisions."
- Does not permit tool-to-tool invocation, self-escalation, direct secret handling, or reinterpretation of contract terms.
- Does not transfer ownership through the Marketplace; it grants invocation rights only.

## Core Concepts

**The Boundary Metaphor.** "A tool is the sole authorized boundary between internal deliberation and external effect... The tool is the constitutional airlock." **Tool as Organizational Asset:** "A tool is not a code snippet, not an API wrapper, and not a configuration file... Tools are inventoried, depreciated, insured against failure, and retired when obsolete."

**Tool Identity Primitives.** Tool ID, Name, Version, Capability Signature, Sandbox Level, **Mutability Flag**, **Trust Score**, Cost Model, Owner Identity, **Provenance Record**, Schema Version, Lineage Reference. Persists minimum seven years. "No anonymous tools are permitted."

**Classification.** By sandbox risk: None, Container, gVisor, Firecracker. By mutability: Observational, Mutating, Hybrid (governed at the capability level, not the tool level). By scope: Tenant-Scoped, Business-Scoped, Portfolio-Scoped, Global. By authority requirement: Levels 1–4. By capability domain: Communication, Financial, Infrastructure, Research, Creation, Integration.

**Architecture & Topology.** **Tool Registry** — "the sole authoritative source of truth for all tools... It does not execute tools; it governs their existence." **Tool Gateway** — "the sole path between internal consumers and external effect," enforcing identity verification, authority resolution against decision records, budget pre-checks, sandbox assignment, tenant boundary validation, and audit logging. **Tool Executor** — dispatches validated requests to sandboxes, managing sandbox lifecycle, resource allocation, timeout enforcement, and secret injection. **Tool Marketplace** — a permissioned exchange, "not an open bazaar." Relationships to Decision Gateway, Agent Registry, Workflow Orchestrator, Cost Manager, Event Bus.

**Tool Anatomy.** Manifest (immutable once registered); Capability Signature (hierarchical and typed, with declared side effects and reversibility estimates per capability); Input and Output Contracts; Sandbox Requirements ("never executed below its declared tier, even if the consumer requests a lower tier for performance reasons"); Cost Model; Timeout and Retry Policy; **Compensation Logic** (validated at registration for determinism and idempotency); Dependency Declaration.

**Tool Lifecycle and States.** Designed → Registered → Validated → Active → Deprecated → Retired → Archived, plus **Suspended** (trust anomaly, security concern, or health failure), each with explicit transition guards. **State Immutability:** once Active, core manifest, contracts, and sandbox requirements are immutable; behavioral changes require a new version with a distinct Tool ID lineage.

**Ownership & Boundaries.** Ownership hierarchy: System, Portfolio, Business, Workspace, External Provider. Tenant Isolation. Cross-Boundary Impact declaration. **Permission Inheritance** — the intersection of owner scope and consumer scope, enforced at every invocation.

**Capability Model.** Capabilities are "a promise of outcome," not an API endpoint. Discovery methods: Capability Match, Domain Search, Reputation Filter, Cost Filter. Boundaries enforced at invocation time; effects outside declared capabilities are blocked by the Executor and logged as violations. Capability Evolution confined to the declared domain.

**Registration.** "Registration is the process by which a tool enters the Agent OS constitution... the establishment of trust, the assignment of identity, and the binding of economic and legal accountability." Validation checks: Schema Compliance, Contract Consistency, Sandbox Feasibility, Compensation Validation, Provenance Verification, Economic Review. **Trust Seeding** — new tools from unknown producers receive conservative trust scores. **No Anonymous Tools** — external tools require an internal sponsor who assumes accountability.

**Discovery and Selection.** Registry Queries; Capability Matching by hierarchical resolution; Reputation-Weighted Discovery; Cost-Aware Discovery. Selection Criteria: Capability Fit, Trust Score, Cost Efficiency, Latency Profile, Availability, Sandbox Appropriateness. Portfolio-Aware Selection. **Selection Binding** — immutable, recording consumer identity, tool identity, capability invoked, decision reference, and timestamp.

**Permissions & Authorization.** **Least Privilege** — the intersection of tool capabilities, consumer permissions, decision authorized scope, and budget remaining. Authority Verification before dispatch: Consumer Authenticity, **Decision Validity** (a committed decision record with authority matching or exceeding the tool's requirement), Autonomy Boundary, Tenant Boundary, Budget Sufficiency. Permission checks at three points — before invocation, before secret injection, before output return. Standing Orders.

**Trust & Reputation.** **Trust Score** composite: Provenance Quality 25%, Execution Success Rate 30%, Contract Adherence 20%, Sandbox Compliance 15%, Economic Predictability 10%. Trust Decay (60 days unused → 5% loss). Drift Detection. Thresholds: <0.40 suspended from autonomous use; 0.40–0.69 restricted to Level 1–2 consumers; 0.70–0.89 standard autonomous use; 0.90–1.00 eligible for critical path and standing orders.

**Invocation Contract.** "A constitutional contract between three parties: the consumer (who requests), the Gateway (who authorizes), and the Executor (who fulfills)," recorded immutably before dispatch. Components: **Idempotency Key**, Decision Reference, Capability Request, Context Package, **Cost Ceiling**, Timeout, Compensation Reference, **Attribution Chain** ("the complete lineage from human authority through decision, workflow, agent, and tool"). "The Executor does not reinterpret contract terms."

**Composition.** Composition occurs through the Gateway, not through direct tool-to-tool invocation. Accountability Preservation. **Sandbox Escalation Prohibition** — "A pipeline containing a Firecracker-tier tool must execute entirely within Firecracker isolation." Reversibility in Composition (saga rollback traverses in reverse).

**Context & Constraints.** Context components: Decision, Consumer, Business, Budget, Sandbox, Temporal. Context Budget. Constraints: Capability, Sandbox, Cost, Temporal, Tenant.

**Availability & Health.** Health Declaration; Health Checks scaled by criticality and volume; Availability States — Available, Degraded, Unavailable, Unknown; effect on discovery and selection.

**Reliability & Resilience.** Failure classification within 60 seconds into Transient, Degraded, Critical, Security, Financial, each with defined response. **Circuit Breakers** per tool and at portfolio level. Compensation and Saga Participation. No Silent Failures — "An unclassified tool failure is treated as critical."

**Performance.** Latency: Registry query p50 50ms / p99 200ms / max 1s; Gateway authorization p50 20ms / p99 100ms / max 500ms; sandbox preparation p50 100ms / p99 500ms / max 2s; observational execution p50 2s / p99 10s / max 30s; mutating execution p50 5s / p99 30s / max 120s. Throughput: 10,000 invocations/minute sustained; 5,000+ concurrent executions; 1,000 Registry queries/second.

**Cost & Economics.** Cost Model Types: Fixed, Metered, Tiered, External Passthrough (with markup disclosure). Budget Enforcement — pre-flight worst-case check, mid-flight halt on ceiling breach, post-flight attribution. Cost Attribution to tenant, business, project, workflow, activity, agent, and tool. Portfolio Circuit Breakers. Economic Impact Assessment.

**Marketplace.** Sharing Modes: Internal, Portfolio, Global (each with escalating approval authority). Sharing Requirements — maintain provenance, preserve tenant isolation, declare cross-boundary impact, retain original owner for accountability. Monetization. **Trust Verification** — enhanced supply chain audit, sandbox stress testing, dependency isolation review.

**Security.** Sandbox Enforcement — "Sandbox escapes are treated as Category 1 security incidents." Secret Handling — "Tools receive only references to secrets, not their values." Input and Output Sanitization. Permission Escalation Prohibition.

**Auditability & Lineage.** Immutable Invocation Record; Lineage Preservation ("which decision authorized it, which workflow orchestrated it, which agent requested it, which human approved it, and which business owned the budget"); Immutability; seven-year retention; Privacy.

**Evolution, Deprecation, Learning.** Version Lineage; A/B Validation; Succession Planning. Deprecation as "a constitutional act, not an informal notice," requiring notice period, identified successor, migration plan, and human approval for Level 3+ tools. Consumer Notification; Migration Enforcement; Replacement Lineage. **Bounded Learning** — tool learning may modify capability declarations, cost models, timeout settings, retry policies, and selection heuristics; it may not modify sandbox requirements, security boundaries, tenant isolation rules, or constitutional authority structures.

**Integration.** Human — direct invocation subject to identical Gateway authorization, recorded as Class D decisions if mutating; human governance decisions are terminal authority. Agent — **Inventory Intersection** of Registry, capability signature, assigned inventory, and autonomy level; agents do not interact with the Executor, the sandbox, or secrets. Workflow — Tool as Workflow Activity; Planning Integration; Orchestration Integration; Compensation Integration; Workflow Boundaries.

## Constitutional Guarantees

**Non-Violable Tool Rules.** Violation constitutes a Category 1 incident:

1. No tool may be invoked without prior registration and validation in the Tool Registry.
2. No tool may execute without a valid decision record with authority matching the tool's risk class.
3. No tool may perform external effects outside its declared capability signature.
4. No tool may execute outside its declared sandbox tier.
5. No tool may handle secrets directly; secrets are injected by the Executor only.
6. No tool may escalate its own permissions or access resources outside its assigned scope.
7. No anonymous or pseudonymous tool registration is permitted.
8. No tool may cross tenant boundaries without explicit human approval and isolation review.
9. No mutating tool may be registered without declared compensation logic.
10. No tool invocation may exceed its cost ceiling or the consumer's remaining budget.
11. No tool may bypass the Tool Gateway for direct consumer-to-executor invocation.
12. No tool audit record may be modified, overwritten, or deleted after formation.
13. No tool may present unvalidated external data as output without schema and sanitization checks.
14. No approval gate for Level 3 or 4 tool invocations may auto-approve on timeout.
15. No tool may suppress failure or cost overrun information from the Gateway.
16. No deprecated tool may be bound to new workflow activities after its migration deadline.
17. No tool may invoke another tool directly; all composition flows through the Gateway.
18. No tool may store business-critical state exclusively in external systems without durability guarantees.
19. The Panic Protocol must halt all in-flight tool invocations within 5 seconds.
20. No tool learning may modify sandbox requirements, security boundaries, or constitutional authority structures.

## Depends On

- **01_PRINCIPLES.md** through **11_DECISION_OPERATING_MODEL.md** — 12 is explicitly derived from all eleven.
- **11** in particular supplies the committed decision record whose authority the Tool Gateway verifies before every invocation.

## Provides To

- **13_LEARNING_OPERATING_MODEL.md** — tool invocation records, failure classifications, cost overruns, and trust score movements as evidence of execution quality.
- **07_WORKFLOW_OPERATING_MODEL.md** (reciprocally) — tool availability, health status, and cost estimates consumed during workflow planning; execution events consumed for state advancement.
- **The external world** — the sole authorized boundary through which Agent OS produces external effect.

## Key Definitions

| Term | Definition |
|------|------------|
| **Tool** | A governed, identifiable capability that performs external work under constitutional authorization and sandbox constraints. |
| **Tool Registry** | The canonical inventory of all tools, their identities, manifests, and trust scores. |
| **Tool Gateway** | The unified authorization and dispatch layer for all tool invocations. |
| **Tool Executor** | The runtime component that dispatches validated invocations to sandboxed environments. |
| **Tool Manifest** | The canonical declaration of a tool's identity, capabilities, contracts, and constraints. |
| **Capability Signature** | The structured declaration of external effects a tool can produce. |
| **Sandbox Tier** | The isolation level (None, Container, gVisor, Firecracker) required for safe tool execution. |
| **Trust Score** | A composite metric of tool provenance, reliability, and behavioral stability. |
| **Compensation Logic** | The pre-defined procedure to reverse the effect of a mutating tool invocation. |
| **Invocation Contract** | The binding constitutional agreement specifying the terms of a single tool execution. |
| **Tool Marketplace** | The permissioned exchange for cross-business and portfolio-level tool sharing. |
| **Idempotency Key** | A unique identifier ensuring duplicate requests do not produce duplicate external effects. |
| **Cost Ceiling** | The maximum allowable cost for a single tool invocation. |
| **Circuit Breaker** | A threshold that halts tool invocations when failure rates or costs exceed safe limits. |

## Architectural Boundaries

- **The airlock boundary:** the tool is the sole authorized passage between internal deliberation and external effect.
- **Registry/Gateway/Executor separation:** the Registry governs existence, the Gateway authorizes, the Executor fulfills. The Executor makes no policy decisions and does not reinterpret contract terms.
- **Decision boundary:** no tool executes without a committed decision record whose authority matches the tool's risk class.
- **Sandbox boundary:** a tool is never executed below its declared tier; composition executes at the highest tier any component requires; escapes are Category 1 security incidents.
- **Capability boundary:** tools perform only what they declare; effects outside the signature are blocked and logged.
- **Composition boundary:** no tool-to-tool invocation. All composition flows through the Gateway.
- **Secret boundary:** tools receive references, never values. Secrets are injected by the Executor into the sandbox at invocation time.
- **Permission boundary:** the intersection of tool capabilities, consumer permissions, decision scope, and remaining budget. No self-escalation.
- **Economic boundary:** cost ceiling, consumer budget, and portfolio circuit breakers, enforced pre-flight, mid-flight, and post-flight.
- **Ownership boundary:** the Marketplace grants invocation rights; it does not transfer ownership or accountability.
- **Learning boundary:** tool learning may not touch sandbox requirements, security boundaries, tenant isolation, or authority structures.

## Implementation Statement

12_TOOL_OPERATING_MODEL.md defines the constitution of external effect: identity, classification, anatomy, lifecycle, registration, discovery, selection, authorization, trust, invocation contracts, composition, economics, security, and governance. It states explicitly that where it is silent the constitution governs, and where it speaks it is binding.

This document intentionally defines no implementation details.

---
---

# 13 — LEARNING OPERATING MODEL

## Purpose

To specify how Agent OS improves itself from evidence: how outcomes are attributed, how patterns are abstracted, how improvements are validated, and how organizational capability compounds across time.

## Mission

The learning subsystem exists to ensure that every outcome — success or failure — is transformed into **validated, attributable, and propagated improvement** across the organization, subject to absolute constraints of evidence quality, authority boundaries, and human sovereignty.

**Permanent Objectives:** Attribution Integrity; Pattern Abstraction; Validation Before Propagation; Bounded Self-Modification; Asymmetric Improvement; Portfolio Coherence; Human Sovereignty Preservation; Economic Control; Feedback Loop Closure; Anti-Drift.

**Objective Conflict Resolution Order:** Human Sovereignty > Bounded Self-Modification > Attribution Integrity > Validation Before Propagation > Asymmetric Improvement > Portfolio Coherence > Economic Control > Feedback Loop Closure > Anti-Drift > Pattern Abstraction.

## Responsibilities

- Define **Learning Philosophy** and the distinctions Learning vs. Memory, vs. Knowledge, vs. Decision, vs. Tool, plus Learning as Compounding Moat.
- Define **Learning Identity**, **Classification**, **Architecture & Topology**, and **Sources & Inputs**.
- Define the **Learning Lifecycle** and **States & Transitions**.
- Define **Ownership & Boundaries**, **Context & Provenance**, **Evidence & Attribution**, **Validation & Confidence**.
- Define **Patterns & Abstraction**, **Consolidation**, **Propagation & Adoption**, **Prioritization**, **Feedback Loops**, **Decay & Deprecation**.
- Define **Economics & Cost Control**, **Governance & Oversight**, **Security**, **Observability**, **Reliability & Fault Tolerance**, **Performance Characteristics**.
- Define **Organizational**, **Portfolio**, **Business**, **Agent**, **Workflow**, **Tool**, and **Decision Learning**; **Human Learning Integration**; **Failure Transformation & Success Replication**; **Continuous Improvement & Adaptation**.

## Non-Responsibilities

- Does not specify implementation; it is a behavioral contract.
- Does not validate beliefs. "Knowledge Gateway owns validation; Learning Gateway owns proposal. Learning feeds the Knowledge pipeline; it does not bypass it."
- Does not make decisions. "Learning improves the decision process; it does not make decisions."
- Does not execute. "Learning improves execution; it does not execute."
- Does not adopt. "Propagation is not adoption; it is the handoff to the target subsystem's governance process." The target subsystem retains full constitutional authority to reject, modify, or escalate.
- Does not self-modify constitutionally. "The system may not auto-modify its own constitutional constraints."

## Core Concepts

**The Adaptation Metaphor.** "Learning is permanent organizational adaptation... Memory asks what happened; Knowledge asks what is true; Decision asks what shall be done; Tool asks how to act; Learning asks how to become better at all of these. **Learning is the only subsystem whose output is change to the other subsystems.**"

**Learning as Compounding Moat.** "The rate of learning is the primary determinant of long-term value... Learning compounds exponentially when feedback loops are tight and attribution is accurate."

**Learning Identity Primitives.** Learning ID, Learning Type (hierarchical, e.g. `learning.agent.capability`, `learning.decision.heuristic`), Schema Version, Timestamp, Source Identity (observer), **Target Subsystem**, Tenant/Business/Workspace IDs, Evidence References, Confidence Score, **Scope** (Private, Team, Business, Portfolio, Global), Lineage Reference, **Expected Improvement**, **Actual Improvement** (nullable until measured). Persists minimum seven years.

**Classification.** By semantic role: Attribution, Pattern, Hypothesis, Consolidation, Feedback, Drift Detection. By structural form: Atomic, Composite, Narrative, Graph Edge. By scope: Private, Team, Business, Portfolio, Global. By target subsystem: Memory, Knowledge, Decision, Tool, Agent, Workflow, Business, Portfolio Learning.

**Architecture & Topology.** **Learning Gateway as Meta-Layer** — the unified access layer enforcing evidence sufficiency, attribution completeness, scope validation, and authority checks before permitting propagation. "Producers cannot push improvements directly into Memory, Knowledge, Decision, or Tool subsystems." Boundaries: Tenant, Business, Authority, Confidence.

**Sources & Inputs.** Decision Outcomes (decision journals as "the canonical record of expected vs. actual outcomes"); Memory Episodes; Knowledge Changes; Tool Execution Records; **Human Feedback** ("treated as high-confidence evidence and is never overridden by autonomous observation"); Event Stream ("Learning does not poll; it reacts to events").

**Learning Lifecycle.** Observation → Extraction → Pattern Recognition (bounded by scope) → Hypothesis Formation → Validation → Consolidation → Propagation → Adoption → Measurement → Disposition (Confirmed, Refuted, Superseded, or Abandoned).

**Canonical States.** Observed, Hypothesized, Validated, Consolidated, Propagated, Adopted, Confirmed, Refuted, Superseded, Abandoned, **Quarantined**, each with explicit transition guards. **State Immutability** upon Validated.

**Ownership & Boundaries.** Agent, Team, Business, Portfolio, Human Sovereign ownership tiers. Inheritance and Succession. Cross-Boundary Impact declaration. Tenant Isolation.

**Context & Provenance.** Trigger Context, Evidence Context, Mission Context, Temporal Context. "A proposal to 'reduce ad spend' without the context that it follows a failed holiday campaign is dangerous." Context Budget.

**Evidence & Attribution.** Evidentiary Basis in canonical records only. **Attribution Dimensions:** Causal Proximity, Confounding Control, Temporal Order, Replication. **Attribution Error Mitigation:** minimum observation counts, mandatory consideration of null hypotheses, escalation of high-impact attributions to human review. Evidence Sufficiency by Target Class: Agent/Tool ≥3 observations or one high-confidence human feedback; Workflow ≥2 complete executions; Decision ≥5 decision outcomes; Business/Portfolio comprehensive basis with human review.

**Validation & Confidence.** Validation dimensions: Evidence Quality, Attribution Strength, Scope Conformance, Contradiction Check. Thresholds: <0.60 quarantined or abandoned; 0.60–0.79 Agent/Tool learning, flagged provisional; 0.80–0.94 Workflow/Decision learning; 0.95–1.00 Business/Portfolio learning with human ratification. Continuous Revalidation; refuted entries trigger reversal proposals.

**Patterns & Abstraction.** Pattern taxonomy: Success, Failure, Anomaly, Correlation (explicitly labeled non-causal). Abstraction levels: Instance, Episode, Heuristic, Principle. **Pattern Formation Rules:** never from single observations; success patterns require ≥3 confirming instances; failure patterns require ≥2 with root cause attribution.

**Consolidation.** Synthesis resolving contradictions, merging overlapping proposals, and packaging for propagation. Triggers. Products: Unified Proposal, Conflict Report, Scope Narrowing. Resource Caps to prevent analysis paralysis.

**Propagation & Adoption.** Propagation as formal handoff. Adoption Governance routed through each target subsystem's own constitutional mechanism. Adoption Rejection → Abandoned with justification logged ("Rejection does not invalidate the evidence"). **Emergency Propagation** permitted only for safety-critical failure patterns with Class D authority, logged as a constitutional exception.

**Prioritization.** Criteria: Impact Magnitude, Risk Reduction, Replication Value, Evidence Strength, Adoption Cost. Portfolio-Aware Scoring. Ranking and Scheduling respecting subsystem capacity, human approval bandwidth, and economic constraints.

**Feedback Loops.** Closed-Loop Structure: **Observe → Propose → Adopt → Measure → Confirm/Refute → Consolidate.** Measurement Windows: Agent/Tool 5–10 subsequent executions; Workflow 3–5 complete instances; Decision 10–20 subsequent decisions; Business/Portfolio 1–3 business cycles or quarters. Confirmation; Refutation and Reversal ("Refutation is itself a learning entry"); Compounding.

**Decay & Deprecation.** Freshness as Relevance Probability; domain-dependent Aging Dynamics ("tool trust patterns age slowly; market tactic patterns age quickly"); Decay Process; Deprecation preventing obsolete heuristics from polluting future proposals.

**Economics & Cost Control.** Cost Model spanning observation cycles, evidence extraction, validation processing, consolidation computation, propagation overhead, and measurement windows. Budget Enforcement; Cost Attribution; Portfolio Circuit Breakers (maximum learning spend per business per period, maximum observation-to-adoption latency, minimum operational budget preservation).

**Governance & Oversight.** Self-Audit; **Drift Detection** for "systematic attribution errors, confidence inflation to bypass validation, excessive scope expansion, or recursive self-modification attempts." Anomaly Response including **Recursion Anomaly** — "Learning entries that target the Learning subsystem itself trigger immediate human alert and suspension." Constitutional Compliance escalated as Category 1.

**Security, Observability, Reliability, Performance.** Authentication and Authorization; Integrity Protection (proposals cryptographically bound to evidence and observer identity); Input Sanitization; Audit Security (bulk export requires Class D authority). Metrics: Velocity, Quality, Governance, Health, Economic. Graceful Degradation — "no workflow fails due to Learning unavailability." No Silent Failures. Latency: observation→extraction p50 1s / p99 5s / max 30s; hypothesis validation p50 2s / p99 10s / max 60s; consolidation p50 5s / p99 30s / max 120s. Throughput: 1,000 observations/second; 100 validations/second; 50 propagations/minute.

**Layer-Specific Learning.** Organizational (meta-capabilities, cultural persistence, meta-learning). Portfolio (capital allocation improvement, strategic positioning, cross-business pollination). Business (strategy, product, operational). Agent (capability refinement, autonomy calibration, context utilization). Workflow (DAG optimization, checkpoint placement, error handling). Tool (trust calibration, selection optimization, capability refinement). Decision (heuristic improvement, confidence calibration, standing order refinement).

**Human Learning Integration.** Feedback Entry (high-confidence, bypassing certain automated gates while retaining full audit); Strategic Override; Governance Participation; Panic Protocol.

**Failure Transformation & Success Replication.** **Asymmetric Processing** — "failure patterns require fewer confirming instances but stronger root cause attribution. Success patterns require more confirming instances but permit broader generalization." Failure learning is prioritized over success learning when capital is at risk.

**Continuous Improvement & Adaptation.** Meta-Learning; **Bounded Evolution** — "Learning may not evolve its way out of constitutional constraints. It may not auto-elevate its own authority, bypass approval gates, or modify non-violable rules." Improvement Validation.

## Constitutional Guarantees

**Non-Violable Learning Rules.** Violation constitutes a Category 1 incident:

1. No learning entry may be formed without authenticated observer identity and complete evidence citation.
2. No learning proposal may bypass the target subsystem's Gateway or approval mechanisms.
3. No learning entry may modify constitutional constraints, security boundaries, or human approval gates.
4. No learning entry may target the Learning subsystem itself without Class D human authority.
5. No learning proposal may be propagated with confidence below the threshold for its target class.
6. No learning entry may suppress uncertainty or present correlation as causation.
7. No anonymous or pseudonymous learning formation or propagation is permitted.
8. No learning may cross tenant boundaries without explicit anonymization and human approval.
9. No learning proposal may be adopted without measurement of its actual outcome.
10. No learning entry may be modified, overwritten, or deleted after validation.
11. No learning cycle may consume resources that breach portfolio-level circuit breakers.
12. No learning proposal may override a human sovereign decision or standing order.
13. No learning entry may proceed on unresolved contradictory evidence without human arbitration.
14. No learning may be formed from quarantined memory, unvalidated knowledge, or speculative observation as sole evidence.
15. No learning proposal may escalate the autonomy level of any agent or subsystem without human approval.
16. No learning feedback loop may remain unclosed for more than its defined measurement window.
17. No learning may recursively trigger learning cycles without explicit human authorization.
18. No learning audit record may be modified, overwritten, or deleted after formation.
19. Learning governance anomalies must be escalated as Category 1 incidents.
20. The Panic Protocol must halt all active learning cycles within 5 seconds of invocation.

## Depends On

- **01_PRINCIPLES.md** through **12_TOOL_OPERATING_MODEL.md** — 13 is explicitly derived from all twelve.
- **09** for memory episodes, **10** for knowledge changes, **11** for decision journals, **12** for tool execution records, **08** for the event stream that triggers observation cycles.

## Provides To

- **09_MEMORY_OPERATING_MODEL.md** — proposals for consolidation, decay rate, or relevance adjustments.
- **10_KNOWLEDGE_OPERATING_MODEL.md** — hypotheses, revalidation triggers, and ontology extension proposals, all subject to the Knowledge Gateway's validation pipeline.
- **11_DECISION_OPERATING_MODEL.md** — heuristic, option-generation, and standing-order refinement proposals.
- **12_TOOL_OPERATING_MODEL.md** — trust, selection, and capability adjustment proposals.
- **06, 07, and the business and portfolio layers** — capability, DAG, strategy, and capital allocation proposals through their respective governance mechanisms.

## Key Definitions

| Term | Definition |
|------|------------|
| **Learning** | The constitutional process of transforming organizational outcomes into validated, attributable, and propagated improvements. |
| **Learning Gateway** | The unified meta-layer through which all learning operations are mediated, validated, and audited. |
| **Observation** | The initial identification that an outcome is available for learning analysis. |
| **Attribution** | The process of correlating outcomes with causes through evidence and causal reasoning. |
| **Pattern** | A recurring structure abstracted from multiple observations. |
| **Hypothesis** | A provisional candidate improvement awaiting validation. |
| **Consolidation** | The synthesis of fragmented hypotheses into coherent, non-contradictory proposals. |
| **Propagation** | The formal handoff of a validated learning proposal to a target subsystem's Gateway. |
| **Adoption** | The commitment of a target subsystem to implement a learning proposal. |
| **Measurement** | The closed-loop evaluation of whether an adopted improvement produced expected outcomes. |
| **Confirmation** | The state of a learning entry whose expected improvement was validated by measurement. |
| **Refutation** | The state of a learning entry whose expected improvement was contradicted by measurement. |
| **Bounded Self-Modification** | The principle that learning may improve operational subsystems but never constitutional constraints. |
| **Feedback Loop** | The closed cycle connecting observation, proposal, adoption, and outcome measurement. |
| **Learning Journal** | The immutable record of a learning entry's full lifecycle. |
| **Attribution Error** | An incorrect correlation between cause and outcome, leading to harmful proposals. |
| **Scope** | The boundary of applicability for a learning entry (Private, Team, Business, Portfolio, Global). |
| **Recursion Anomaly** | A learning entry that targets the Learning subsystem itself, requiring immediate human alert. |

## Architectural Boundaries

- **Meta-layer boundary:** learning is the only subsystem whose output is change to the other subsystems, and every such change passes through the target subsystem's own Gateway.
- **Proposal/validation boundary:** the Knowledge Gateway owns validation; the Learning Gateway owns proposal. Learning feeds the Knowledge pipeline; it does not bypass it.
- **Propagation/adoption boundary:** propagation is handoff, not adoption. The target subsystem retains full constitutional authority to reject, modify, or escalate.
- **Constitutional boundary:** learning may not modify constitutional constraints, security boundaries, human approval gates, or non-violable rules, and may not auto-elevate its own or any agent's authority.
- **Recursion boundary:** learning entries targeting the Learning subsystem itself require Class D human authority and trigger immediate alert and suspension.
- **Evidence boundary:** quarantined memory, unvalidated knowledge, and speculative observation may not serve as sole evidence.
- **Causation boundary:** correlation patterns must be explicitly labeled non-causal; no proposal may present correlation as causation.
- **Asymmetry boundary:** failure patterns require fewer confirming instances but stronger root cause attribution; success patterns require more instances but permit broader generalization.
- **Closure boundary:** no adopted improvement may go unmeasured; no feedback loop may remain unclosed beyond its measurement window.
- **Economic boundary:** the cost of learning must not exceed the value it produces, enforced by budget checks and portfolio circuit breakers.

## Implementation Statement

13_LEARNING_OPERATING_MODEL.md defines the constitution of organizational adaptation: identity, classification, sources, lifecycle, attribution, validation, consolidation, propagation, feedback, decay, economics, and governance. It states explicitly that where it is silent the constitution governs, and where it speaks it is binding.

This document intentionally defines no implementation details.

---
---

## Manifest Closure

20B compresses documents 05 through 13 — the Execution Layer of the Agent OS constitution: how the system behaves while alive (05), who performs the work (06), how work is orchestrated (07), how facts are recorded (08), how experience is retained (09), how belief is validated (10), how commitment is authorized (11), how external effect is produced (12), and how the whole apparatus improves itself (13).

Documents 01 through 04 are compressed in `20A_FOUNDATION_MANIFEST.md`. Documents 14 through 19 are not summarized here and are reserved for a subsequent manifest.

*End of Document*
