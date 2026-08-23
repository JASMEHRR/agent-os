# 21B_IMPLEMENTATION_ARCHITECTURE_SUBSYSTEMS.md

**Agent OS — Implementation Architecture, Part B: Core Subsystem Architecture**
**Version:** 1.0.0
**Status:** Ratified for Implementation
**Classification:** Implementation Specification — Binding on All Construction Work
**Subordinate To:** `01`–`19` (Constitution), `20A`–`20C` (Manifests), `21A` (Foundations & Structure)

---

## Preliminary Note on This Document

This document specifies the internal implementation architecture of every constitutional subsystem. It presumes and does not restate the foundations established in `21A`: the Gateway Pattern (§5), the Constitutional Kernel (§6), the layer and plane model (§4), the communication model (§9), the data ownership allocation (§10), the state model (§11), and the configuration architecture (§12).

**Every subsystem in this document is constructed on the Gateway Pattern.** Where a section does not restate a mechanism — boundary enforcement, guarded transition, immutable journal, signal emission, failure classification, Panic participation — that mechanism is inherited from the Kernel and is present. Sections describe **specialization**, not reimplementation.

**Section order is presentation order, not build order.** Build sequencing is specified in Part V. The presentation order here follows the operational narrative — execution, then substrate, then oversight — while the dependency graph of `21A` §4 governs construction.

**Implementation decisions are marked.** Where this document makes a choice the constitution does not compel, the choice is labelled `[Implementation Decision]` and carries its rationale. Everything unmarked traces to constitutional provision or to the approved Planning Package.

**Three Constitutional Interpretation Register entries remain open and block portions of this document.** CIR-001 blocks construction of Integration, Deployment, and Evolution. CIR-002 blocks transport binding across every subsystem. CIR-003 blocks data allocation ratification. Sections affected carry an explicit blocking notice.

---

## Table of Contents

**Part III — Core Subsystem Architecture**

13. Agent Runtime
14. Workflow Engine
15. Event Bus
16. Memory Gateway
17. Knowledge Gateway
18. Decision Gateway
19. Tool Platform — Registry, Gateway, Executor
20. Integration Platform — Registry, Gateway, LLM Router
21. Learning Gateway
22. Security Gateway
23. Governance Gateway
24. Observability Gateway
25. Deployment Platform — Registry, Gateway
26. Evolution Gateway

---
---

# PART III — CORE SUBSYSTEM ARCHITECTURE

---

## 13. Agent Runtime

### 13.1 Purpose

The Agent Runtime is the execution environment for the autonomous workforce. It realizes `05_AGENT_RUNTIME_FRAMEWORK` and `06_AGENT_OPERATING_MODEL` in software.

It exists because agents are not processes. `06.2.1` establishes the agent as "a persistent digital worker with an identity, a specialty, a reputation, and a career trajectory," while `02.3.2` establishes that agents "are not long-running processes. They are stateless workers that wake up in response to workflow tasks." The Agent Runtime is the component that reconciles these two facts: it holds the durable identity while executing the ephemeral process.

The Runtime does not own agent scheduling. `02.3.2` is explicit: "The Workflow Engine owns scheduling; the Runtime owns execution." This separation is load-bearing and is preserved throughout.

### 13.2 Architectural Responsibilities

- Maintain the Agent Registry as durable system state, per `06.3.2`.
- Manage the agent worker pool and its horizontal scaling.
- Hydrate agent state from the Memory Gateway before execution, per `02.3.2`.
- Assemble execution context within the agent's declared context budget.
- Render prompts and invoke inference through the LLM Router.
- Dispatch tool calls through the Tool Gateway.
- Validate agent output against the agent's declared output contract.
- Emit lifecycle and completion events to the Event Bus.
- Report heartbeat to the Workflow Engine, per `02.4.8`.
- Compute and maintain reputation scores, success rates, and drift indicators.
- Enforce the agent lifecycle state machine and its transition guards, per `06.6`.
- Enforce agent authority boundaries as the intersection of capability signature, tool inventory, memory scope, autonomy level, cost budget, and workspace, per `06.9.6`.

### 13.3 Internal Components

| Component | Responsibility |
|---|---|
| **Agent Registry** | Durable store of agent identity, version lineage, capability signature, autonomy profile, memory bindings, tool inventory, reputation, and lifecycle state |
| **Manifest Loader** | Parses and validates agent manifests from `agents/`; rejects manifests failing schema, capability, or permission validation |
| **Worker Pool Manager** | Manages stateless execution workers; scales against task queue depth |
| **State Hydrator** | Retrieves agent private memory, team memory, and business memory through the Memory Gateway within declared scope |
| **Context Assembler** | Composes execution context under `max_context_tokens`; performs relevance ranking and truncation |
| **Prompt Renderer** | Renders declared prompt templates against assembled context |
| **Inference Client** | Submits rendered prompts to the LLM Router; never contacts a model provider |
| **Tool Dispatcher** | Submits tool invocation requests to the Tool Gateway; never contacts the Tool Executor |
| **Output Validator** | Validates structured output against the agent's declared output contract |
| **Reputation Engine** | Computes success rate, reputation score, decay, and assignment eligibility |
| **Drift Monitor** | Detects deviation in tool usage, output distribution, latency profile, and schema adherence |
| **Lifecycle Controller** | Enforces agent state transitions and their guards; executes lifecycle side effects |
| **Heartbeat Reporter** | Emits progress heartbeats during execution |

### 13.4 Internal Architecture

The Runtime is organized as two cooperating planes.

**The Identity Plane** is durable and long-lived. It holds the Agent Registry, the Reputation Engine, the Drift Monitor, and the Lifecycle Controller. It persists independently of any execution. An agent that is Idle, Suspended, Retired, or Archived exists entirely within this plane. `06.3.2` requires exactly this: "When an agent is not executing, its identity remains active in the registry."

**The Execution Plane** is stateless and ephemeral. Workers hold no business-critical state between tasks. On receiving an activity dispatch, a worker acquires the agent's identity record from the Identity Plane, hydrates state through the Memory Gateway, assembles context, renders, infers, dispatches tools, validates output, emits result, and returns to the pool holding nothing.

The separation is what permits `01.12.1` horizontal scaling while satisfying `06.3.2` identity persistence. Workers are addable and disposable; identity is neither.

**Execution sequence within a worker.** Activity received with workflow context and idempotency key → identity and manifest resolved → authority intersection computed → state hydrated within memory scope → context assembled within budget → external input sanitized → prompt rendered → token budget pre-checked → inference invoked → output parsed → tool calls dispatched and validated → grounding validated → output contract validated → result emitted → worker released.

Every step that crosses a module boundary passes through the owning Gateway. The worker holds no credential, contacts no provider, and touches no substrate.

**[Implementation Decision] Worker specialization by capability domain.** Workers may be pooled by capability domain rather than drawn from a single undifferentiated pool. Rationale: `02.12.2` describes agent runtime workers "sharded by capability" at production scale, and capability-affine pooling reduces manifest and template cache churn. This is a scaling strategy, not a constitutional requirement.

### 13.5 Public Interfaces

| Interface | Consumers | Purpose |
|---|---|---|
| Activity Execution | Workflow Engine | Accept an activity dispatch and return a structured outcome |
| Agent Discovery | Workflow Engine | Resolve agents by capability match, event subscription, or direct reference (`06.7.2`) |
| Agent Registration | Human Interface, Evolution Gateway | Register a new agent version following validation and approval |
| Lifecycle Command | Human Interface, Governance Gateway | Suspend, retire, or reactivate an agent |
| Agent Health Query | Observability Gateway, Workflow Engine | Report success rate, reputation, drift status, availability |

### 13.6 Consumed Interfaces

| Provider | Consumed for | Constitutional basis |
|---|---|---|
| Security Gateway | Authentication, authorization, security context, token issuance | `14.6.1` |
| Memory Gateway | State hydration, memory writes within declared scope | `09.6.1`, `06.5.3` |
| Knowledge Gateway | Canonical belief retrieval for reasoning | `10.6.2` |
| LLM Router | All inference | `02.3.8`, `03` rule 11 |
| Tool Gateway | All tool invocation | `12` rule 11 |
| Decision Gateway | Decision commitment for Class A and B; escalation above | `11.6.2` |
| Cost Manager | Budget verification and cost attribution | `02.3.9` |
| Event Bus | Event emission and subscription | `08.6.1` |
| Observability Gateway | Mandatory signal emission | `16` rule 1 |

### 13.7 Data Ownership

Per `21A` §10.4.2, the Agent Runtime owns exclusively: the Agent Registry (identity, version lineage, capability signature, autonomy profile, memory bindings, tool inventory, manifest reference), reputation and success-rate records, execution records, drift baselines, and heartbeat state. It occupies the Structured and Working tiers.

It owns no memory content, no knowledge, no decision record, no tool manifest, and no journal other than its own execution journal.

### 13.8 State Management

| State | Class | Recovery |
|---|---|---|
| Agent identity and manifest | Durable-Mutable | Registry store |
| Reputation, success rate | Durable-Mutable | Registry store; recomputable from execution records |
| Lifecycle state | Durable-Mutable | Registry store; transitions append-only |
| Execution record | Durable-Committed | Immutable once written |
| Worker execution context | Ephemeral-Recoverable | Rehydrated from Memory Gateway and workflow context |
| Assembled prompt, parsed output | Ephemeral-Discardable | Recomputed |
| Drift baseline | Derived | Recomputed from execution history |

No business-critical state resides in a worker. On worker loss, the Workflow Engine reschedules and the successor rehydrates from durable sources, per `02.16.1`.

### 13.9 Failure Domains

| Failure | Classification | Response |
|---|---|---|
| Worker process termination | Critical to the activity, contained to it | Heartbeat timeout detected by Workflow Engine; activity rescheduled; state rehydrated |
| Agent stall | Critical to the activity | Progress timeout; activity times out; retry with backoff |
| Output contract violation | Degradable | Retry with corrected prompt, maximum two attempts; then human review |
| Repeated schema violation | Security-adjacent | Automatic suspension at the threshold defined in `06.9.4` |
| Cost budget breach | Financial | Immediate halt, task suspension, escalation |
| Excessive tool call count | Critical | Hard limit enforced by Workflow Engine; workflow fails with diagnostic |
| Drift detection | Operational | Review workflow; possible suspension or autonomy downgrade |
| Memory Gateway unavailable | Degradable | Degraded context assembly with explicit flag; halt if context is safety-critical |
| LLM Router unavailable | Degradable then Critical | Router failover exhausted; activity deferred or escalated per `02.16.4` |

Failure containment is at the activity. `06` and `01.6.4` both require that no single agent failure cascade. A failing agent affects its activity, then its workflow's retry policy, and no further.

### 13.10 Security Considerations

Agents authenticate with short-lived tokens of maximum one-hour time-to-live, issued and rotated by the Security Gateway, carrying scoped claims for identity, authority, resource, constraint, and temporal validity. Permission checks occur at the point of action, not at token issuance alone.

Agents never handle secret values. The Tool Executor receives injected secrets inside its sandbox; the agent receives only references. No secret enters agent memory, prompt, log, trace, or output.

External data entering an agent's context passes through sanitization before prompt rendering, per `01.10.3` and `02.8.5` stage four. Unsanitized external data reaching a prompt is a non-violable violation.

Agents cannot escalate their own permissions, cannot invoke tools outside their inventory, cannot access another agent's private memory, and cannot communicate with another agent except through the Event Bus. These are enforced by the Security Gateway and the Tool Gateway, not by agent-side discipline.

Separation of duties is enforced at assignment: the Runtime refuses to assign the Reviewer role for an output to the agent that created it.

### 13.11 Observability Requirements

The Runtime emits: agent lifecycle transitions, execution start and completion, heartbeats at the declared cadence, tool invocation counts, token consumption, cost per execution, output validation outcomes, retry counts, reputation movement, drift indicators, and worker pool depth.

`16.18` requires the Observability Gateway to compose Agent Workforce Health from these signals across eight dimensions: task success rate, output schema conformance, tool invocation accuracy, budget adherence, latency consistency, reputation trajectory, autonomy boundary compliance, and behavioral drift. The Runtime's signal contract is specified to satisfy that composition without further derivation.

### 13.12 Performance Characteristics

| Operation | Target | Source |
|---|---|---|
| Simple agent task, end to end | p99 under 10 seconds | `05.25.1` |
| Complex agent task, end to end | p99 under 60 seconds | `05.25.1` |
| Concurrent agent executions | 1,000+ | `05.25.2` |
| Heartbeat cadence | 30 seconds during execution | `02.4.8` |
| Stall detection | 2× activity timeout | `02.4.8` |

The end-to-end task budgets encompass the full mediation chain and are the constraint from which CIR-004's composite allocation is derived. Scaling is horizontal against task queue depth.

### 13.13 Dependency Relationships

Layer 5. Depends downward on the Trust Plane, Event Bus, Economic Plane, Memory Gateway, Knowledge Gateway, Decision Gateway, Tool Platform, Integration Platform, and LLM Router. Depended upon by the Workflow Engine at Layer 5 — the sole permitted intra-layer relationship, and permitted because the Workflow Engine dispatches to the Runtime rather than coordinating laterally with it.

### 13.14 Architectural Constraints

- The Runtime does not schedule. Scheduling belongs to the Workflow Engine (`02.3.2`).
- The Runtime does not select tools beyond the agent's registered inventory intersection (`12.32.1`).
- The Runtime does not contact model providers, external providers, or substrate directly.
- The Runtime does not hold business-critical state in a worker.
- The Runtime does not grant, elevate, or infer authority.
- The agent manifest is immutable once registered; change requires a new version (`06.5.1`).
- An agent may not review its own output, and may not hold Creator and Reviewer roles for the same output (`06` rules 16, 17).

### 13.15 Guarantees

1. **Identity durability.** Agent identity, lineage, reputation, and history survive worker loss, service restart, and business sunset.
2. **Execution statelessness.** No business-critical state exists solely in a worker; every execution is rehydratable.
3. **Authority containment.** No agent acts outside the intersection of its six declared boundaries.
4. **Attribution completeness.** Every execution, cost, output, and failure is attributed to an Agent ID.
5. **Validated output.** No unvalidated agent output propagates.
6. **Failure containment.** No agent failure escapes its activity.
7. **Horizontal scalability.** Worker capacity scales without coordination.

### 13.16 Interaction with the Constitution

The Runtime realizes `05` and `06` and the component responsibility assigned by `02.3.2`. The Identity Plane realizes `06.3` Agent Identity and `06.6` Agent Lifecycle. The Execution Plane realizes `06.2.2` agent statelessness and `02.3.2` state hydration. The Reputation Engine realizes `06.17`. The Drift Monitor realizes `06.17.5` and `06.19.2`.

The scheduling separation preserved throughout is `02.3.2`'s design rationale verbatim: agents must not own their lifecycle, because separating scheduling from execution "enables independent scaling and prevents agent state corruption from affecting orchestration."

---

## 14. Workflow Engine

### 14.1 Purpose

The Workflow Engine is the orchestrator of durable business processes. It realizes `07_WORKFLOW_OPERATING_MODEL` and the component responsibility of `02.3.3`.

It exists because business processes in an autonomous venture studio span minutes to days and must survive agent crashes, network partitions, model unavailability, and human delay. `07.2.5` states the requirement: a workflow "does not trust any single component to remain alive; it trusts only the durable record of what has been done and what remains to do."

`07.13.1` establishes the engine's defining constraint: **"The orchestrator does not perform work; it governs work."**

### 14.2 Architectural Responsibilities

- Accept workflow triggers from events, timers, and human commands.
- Construct and validate the Execution DAG during Planning.
- Bind agents to activities by capability match, reputation, and availability.
- Verify resources, pre-allocate budget, and pre-clear approvals during Planning.
- Dispatch activities with workflow context, agent binding, and idempotency key.
- Enforce synchronization barriers and causal consistency.
- Manage decision points and their authority resolution.
- Enforce checkpoints as mandatory governance primitives.
- Execute saga compensation in reverse order on failure.
- Manage human approval gates as first-class DAG activities.
- Enforce workflow state transitions and their guards.
- Maintain deterministic replay capability.
- Emit events atomically with state transitions.

### 14.3 Internal Components

| Component | Responsibility |
|---|---|
| **Trigger Receiver** | Accepts business events, system events, scheduled timers, and human commands; validates trigger and rejects duplicates |
| **DAG Constructor** | Decomposes workflow purpose into activities, maps dependencies, identifies parallelization, inserts checkpoints, annotates retry and timeout policy |
| **DAG Validator** | Validates acyclicity, agent capability match, permission coherence, budget feasibility, approval chain completeness |
| **Agent Binder** | Queries Agent Registry; binds agents to activities, not to workflows |
| **Resource Verifier** | Confirms tool health, memory availability, budget sufficiency, approver availability |
| **Budget Pre-Allocator** | Computes worst-case cost including retry and compensation budgets |
| **Approval Pre-Clearance** | Requests pre-approval for known Level 3 gates during Planning |
| **Activity Dispatcher** | Dispatches to Agent Runtime and Tool Gateway with context and idempotency key |
| **Barrier Manager** | Enforces synchronization barriers; validates branch outputs before release |
| **Checkpoint Manager** | Performs pre-activity and post-activity validation; externalizes state |
| **Decision Point Resolver** | Classifies decision points; routes to Decision Gateway; enforces confidence thresholds |
| **Human Gate Manager** | Emits durable approval requests; releases ephemeral resources while paused |
| **Compensation Orchestrator** | Executes saga compensations in reverse order; detects stalled compensation |
| **State Controller** | Enforces the canonical state set and transition guards; emits transitions atomically |
| **Replay Engine** | Reconstructs DAG traversal from trigger, context, and event sequence |
| **Workflow Definition Registry** | Versioned workflow definitions; pins running workflows to their originating version |

### 14.4 Internal Architecture

The engine is organized around the principle that **Planning is cheap and Running is expensive**. `07.12.1` is explicit: "A workflow that fails during Planning has not yet consumed agent labor, LLM tokens, or external API calls."

**Planning subsystem.** On trigger acceptance, the engine constructs the DAG, validates it exhaustively, binds agents, verifies resources, pre-allocates budget, and pre-clears approvals. Every failure mode detectable before execution is detected here. A workflow that cannot succeed does not enter Running.

**Execution subsystem.** Activities whose dependencies are satisfied are dispatched. The engine awaits completion events; it does not poll and does not assume synchronous response. On each completion it advances DAG state, evaluates checkpoints, and releases newly-eligible activities.

**Durability subsystem.** Workflow state is externalized continuously. Checkpoints commit state durably such that orchestrator failure immediately after a checkpoint resumes without loss. `07.19.5` requires exactly this property.

**Compensation subsystem.** On failure of a mutating activity, the engine transitions to Compensating and executes compensations in reverse chronological order. Compensations are idempotent by constitutional requirement. Failed compensation produces a stalled state requiring human intervention — never silent abandonment.

**Determinism discipline.** `07.13.5` requires replayability: the same trigger, context, and event sequence must reconstruct the same DAG traversal. Non-deterministic inputs — current time, random values, external readings — are injected as explicit workflow variables and never derived inside orchestration logic. This is the single most easily violated constraint in the engine and is enforced by construction and by replay testing.

**The bilingual boundary.** Per `03.3.2`, workflow definitions are authored in the mandated workflow language; per `03.3.1`, activity implementations are authored in the mandated service language. The engine therefore spans two runtimes. Contract integrity across the boundary is maintained by single-source schema generation from `core` and mandatory contract tests, per `21A` §9.4.5. Neither language's type system observes both sides, so the boundary is the engine's highest-risk internal seam.

### 14.5 Public Interfaces

| Interface | Consumers | Purpose |
|---|---|---|
| Workflow Trigger | Event Bus, Human Interface, scheduler | Initiate a workflow with charter reference and initial context |
| Workflow Signal | Human Interface, Decision Gateway | Deliver approval, rejection, pause, resume, or cancel |
| Workflow Query | Human Interface, Observability Gateway | Read-only inspection of workflow state without mutation |
| Workflow Health | Observability Gateway | Completion rate, failure rate, compensation frequency, gate latency, checkpoint pass rate |
| Definition Registration | Evolution Gateway, Human Interface | Register a new workflow definition version |

### 14.6 Consumed Interfaces

| Provider | Consumed for |
|---|---|
| Security Gateway | Authorization, permission intersection, context propagation |
| Agent Runtime | Activity dispatch and agent discovery |
| Tool Gateway | Tool activity dispatch and compensation invocation |
| Decision Gateway | Decision point resolution and approval gate authority |
| Cost Manager | Budget pre-allocation and mid-flight monitoring |
| Memory Gateway | Context binding and knowledge extraction on completion |
| Integration Gateway | Integration availability and health during Planning |
| Event Bus | Trigger consumption and state transition emission |
| Observability Gateway | Mandatory signal emission |

### 14.7 Data Ownership

The engine owns exclusively: workflow state, Execution DAGs, checkpoint records, activity records, agent binding records, compensation state, workflow definition registry, and the workflow audit trail. It occupies the Structured, Working, and Cold tiers, mapped to `aos_workflows` per `02.7.1`.

It owns no agent identity, no decision record, no tool manifest, and no memory content.

### 14.8 State Management

| State | Class | Recovery |
|---|---|---|
| Workflow state and DAG position | Durable-Progressive | Rehydrated from last checkpoint |
| Activity records | Durable-Committed | Immutable once written |
| State transition history | Durable-Committed | Append-only; correcting transitions appended, never substituted |
| Compensation position | Durable-Progressive | Rehydrated; compensations idempotent |
| Workflow context versions | Durable-Progressive | Versioned; previous versions retained for replay |
| Ephemeral execution resources | Ephemeral-Discardable | Released on pause; reacquired on resume |

Paused workflows release ephemeral resources and consume no compute quota while retaining durable state, per `07.14.5`. This is what makes human-in-the-loop workflows economically viable across multi-day approval latency.

### 14.9 Failure Domains

| Failure | Classification | Response |
|---|---|---|
| Planning validation failure | Critical, cheap | Diagnostic event; direct transition to Failed; no compensation needed |
| Activity failure, transient | Transient | Exponential backoff retry within declared policy |
| Activity failure, persistent | Critical | Compensation or escalation |
| Agent unavailable | Degradable | Reassignment to alternative agent with matching capability; logged as workflow deviation |
| Output schema violation | Degradable | Retry with corrected prompt; then human review |
| Approval denied | Critical | Compensation of completed mutating activities; transition to Failed |
| Budget breach | Financial | Immediate halt and human escalation |
| Global timeout exceeded | Critical | Forced transition to Failed; compensation initiated |
| Compensation failure | Critical, unrecoverable | Stalled state requiring human intervention |
| Orchestrator failure | Critical, contained | Rehydration from checkpoint; no workflow loss |

The stalled state deserves emphasis. `07.20.2` and `07.8.8` both specify that failed compensation does not resolve itself. The engine must be able to hold a workflow indefinitely in a state that only a human can clear, and must never silently abandon partially compensated external effects.

### 14.10 Security Considerations

A workflow inherits permissions from its parent project intersected with the permissions of its assigned agents, computed at Planning and validated at every activity dispatch. Sub-workflows inherit parent isolation boundaries and may not exceed them.

External data entering workflow context passes through sanitization before reaching agent prompts or tool inputs. Workflows never handle secrets; secrets are injected by the Executor into sandboxes at invocation time and never appear in workflow context, logs, events, or audit trails.

Approval gates are structurally incapable of auto-approval. The Human Gate Manager offers no timeout-approves path for Level 3 or 4; timeout produces cancellation or escalation only. This is enforced by construction rather than configuration, because `07` rule 7 admits no exception.

Workflows may not cross tenant boundaries. The engine validates tenant scope at Planning and at every dispatch.

### 14.11 Observability Requirements

The engine emits: trigger acceptance, every state transition, activity dispatch and completion, checkpoint validation outcomes, decision point resolutions, approval gate entry and exit, compensation execution, timeout events, budget consumption, and workflow completion with outcome.

Emission is atomic with state transition per `07.18.3`: an event is not emitted unless the transition is durably recorded. This atomicity is a hard requirement — a transition without its event produces an unobservable state change, and an event without its transition produces a phantom.

`16.15.2` composes Workflow Health from completion rate, failure rate, compensation frequency, human gate latency, checkpoint pass rate, DAG validation success, and outcome-to-intent fidelity.

### 14.12 Performance Characteristics

| Operation | p50 | p99 | Maximum | Source |
|---|---|---|---|---|
| Planning phase | 5s | 30s | 120s | `07.22.1` |
| Simple activity execution | 2s | 10s | 30s | `07.22.1` |
| Complex activity execution | 10s | 60s | 300s | `07.22.1` |
| Approval request generation | 1s | 30s | 60s | `07.22.1` |
| Checkpoint validation | 10ms | 50ms | 100ms | `07.22.1` |
| Workflow state transition | 50ms | 200ms | 500ms | `07.22.1` |

Throughput: 100 workflow initiations per minute sustained; 1,000+ concurrent workflow executions. Scaling is horizontal by adding orchestrator instances and activity workers; workflows are stateless in the orchestrator with all state externalized.

Checkpoint validation at p99 50ms is the tightest budget in the engine and constrains checkpoint design directly: validation must be a bounded local computation, not a distributed query.

### 14.13 Dependency Relationships

Layer 5. Depends downward on all layers below and on the Trust, Economic, and Oversight planes. Depends on the Agent Runtime for activity execution — the sole permitted intra-layer dependency, directional and non-reciprocal.

Depended upon by no module. The Workflow Engine is a terminal consumer within the execution stack; Learning and Evolution observe its outputs through the Event Bus and journals rather than depending on it.

### 14.14 Architectural Constraints

- The orchestrator governs work; it does not perform work (`07.13.1`).
- No workflow enters Running without passing Planning validation (`07` rule 4).
- No mutating activity executes without declared compensation (`07` rule 3).
- Cycles are prohibited; iteration is a bounded loop construct with an explicit termination guard (`07.6.2`, `07.14.4`).
- Conditions are deterministic functions of workflow context, never hidden in agent prompts (`07.14.3`).
- Non-deterministic inputs are injected as explicit workflow variables (`07.13.5`).
- Compensations are idempotent (`07` rule 19).
- Running or Paused workflows may not be destroyed (`07` rule 5).
- Approval gates for Level 3 and 4 never auto-approve (`07` rule 7).
- Workflow definitions are versioned; running instances pin to their originating version (`07.24.3`).

### 14.15 Guarantees

1. **Durable execution.** Workflow progress survives orchestrator failure, worker loss, network partition, and multi-day human delay.
2. **Cheap failure.** Every pre-execution detectable failure is detected in Planning before resource consumption.
3. **Business-safe reversal.** Every mutating workflow can be reversed to a safe business state, or halts visibly in a stalled state requiring human action.
4. **Deterministic replay.** The same trigger, context, and event sequence reconstruct the same traversal.
5. **Atomic observability.** No state transition occurs without its event; no event exists without its transition.
6. **Approval integrity.** No Level 3 or 4 gate can pass without explicit human action.
7. **Isolation preservation.** No workflow crosses tenant, business, or workspace boundaries without explicit grant.

### 14.16 Interaction with the Constitution

The engine realizes `07` in full and the component responsibility of `02.3.3`. The Planning-first architecture realizes `07.12.1`. The compensation subsystem realizes `07.20` and the Saga pattern of `07.14.6`. The Human Gate Manager realizes `07.16.2` approval gates as first-class DAG activities. The Replay Engine realizes `07.13.5`. The definition registry realizes `07.4.3` version lineage.

`02.3.3`'s design rationale is preserved verbatim in the architecture: durable workflow state and saga compensation are the reasons the engine exists as a distinct subsystem rather than as scheduling logic inside the Runtime.

---

## 15. Event Bus

### 15.1 Purpose

The Event Bus is the system's nervous system. It realizes `08_EVENT_OPERATING_MODEL` and the component responsibility of `02.3.4`.

It exists because Agent OS components do not poll, do not assume, and do not synchronously invoke one another for coordination. `08.2.6` states the position: "Events are the nervous system; everything else is muscle."

The Bus is **not a Gateway**, per `21A` §5.4.2. It routes on metadata and never on content, authorizes nothing, grades nothing, and adjudicates nothing. It is a hub that guarantees delivery, ordering, durability, and causality.

### 15.2 Architectural Responsibilities

- Accept events from authenticated producers and validate against registered schemas.
- Append events durably to their streams and assign sequence identifiers.
- Route to subscribed consumer groups deterministically on metadata.
- Deliver with at-least-once semantics until acknowledged.
- Preserve total ordering within a stream and causal ordering across streams.
- Enforce tenant isolation at the routing layer.
- Manage retry, backpressure, and dead-lettering.
- Archive events to cold storage and enforce the retention schedule.
- Support forensic, learning, and recovery replay in sandboxed context.
- Detect sequence gaps and trigger reconciliation.

### 15.3 Internal Components

| Component | Responsibility |
|---|---|
| **Admission Controller** | Authenticates producer, validates schema, validates scope, assigns publication identity |
| **Stream Writer** | Appends to the durable log; assigns sequence; guarantees durability before delivery begins |
| **Stream Store** | Ordered, append-only durable logs partitioned by domain category |
| **Router** | Resolves subscribed consumer groups from stream and event type metadata |
| **Delivery Manager** | Dispatches to consumer group members; tracks acknowledgment; manages redelivery |
| **Consumer Group Registry** | Registered consumer groups, subscription patterns, read positions, lag |
| **Retry Scheduler** | Exponential backoff scheduling for failed deliveries |
| **Dead Letter Manager** | Quarantines exhausted deliveries; alerts on depth thresholds |
| **Backpressure Controller** | Producer throttling, lag alerting, ephemeral shedding for non-critical streams |
| **Causality Tracker** | Validates causation and correlation propagation; maintains happens-before relationships |
| **Archive Manager** | Tiers events from hot to warm to cold per the retention schedule |
| **Replay Engine** | Reconstructs event sequences into sandboxed context with replay metadata |
| **Gap Detector** | Monitors sequence continuity; triggers reconciliation on discontinuity |

### 15.4 Internal Architecture

The Bus is organized as a hub with strict admission and strict delivery, and nothing in between that examines content.

**Admission.** A producer submits an event with full identity and payload. The Admission Controller authenticates the producer against the Trust Plane, validates the payload against its registered schema version, validates that the producer's declared scope permits emission of that event type in that tenant, and rejects on any failure. Unregistered event types are rejected outright per `08.16.1`. Rejection is explicit and logged; producers may not silently swallow emission failure.

**Publication.** The Stream Writer appends to the durable log, assigns a sequence identifier within the stream, and achieves durability. `08.14.1` requires durability *before* delivery begins — an event that has been delivered but not durably stored would be a fact that could be un-made, which the immutability guarantee forbids. At publication, the event becomes immutable and observable.

**Routing.** The Router resolves consumer groups from stream membership and event type prefix. Routing is a metadata operation and is deterministic: the same event always routes to the same groups. `08.17.1` prohibits content-based routing explicitly, because content routing would couple producers to consumer logic and defeat the decoupling the Bus exists to provide.

**Delivery.** Events are dispatched to individual members within each subscribed group such that each event is processed by exactly one member of that group, while different groups receive independent copies. Delivery is at-least-once; the Bus redelivers until acknowledged. Exactly-once is not offered — `08.17.2` places idempotency on the consumer.

**Isolation.** Tenant isolation is enforced at the routing layer, not at the consumer. An event tagged to one tenant is never dispatched to another tenant's consumer, regardless of subscription. This placement matters: enforcing isolation at the consumer would mean the event had already crossed the boundary.

**Streams as logs, not queues.** `08.6.2` is explicit: "Streams are not queues; they are durable logs." Consumers read at their own pace and maintain their own positions. Multiple consumer groups read the same stream independently. Consumption does not destroy.

**[Implementation Decision] Stream partitioning by domain category with tenant sub-partitioning.** Streams are partitioned by the six constitutional domain categories — business, agent, workflow, system, command, audit — and sub-partitioned by tenant. Rationale: `02.3.4` specifies partitioning by event category, and tenant sub-partitioning makes routing-layer isolation a structural property rather than a filter. This is a partitioning strategy, not a constitutional requirement.

### 15.5 Public Interfaces

| Interface | Consumers | Purpose |
|---|---|---|
| Event Emission | All modules | Submit an event for admission and publication |
| Consumer Group Registration | All consuming modules | Register a group with subscription pattern and permission scope |
| Event Consumption | Registered consumer groups | Receive delivery; acknowledge or signal failure |
| Replay Request | Observability Gateway, Learning Gateway, Human Interface | Request forensic, learning, or recovery replay in sandbox |
| Dead Letter Query | Human Interface, Governance Gateway | Inspect quarantined events for review and potential replay |
| Stream Health | Observability Gateway | Depth, lag, throughput, dead-letter depth, gap indicators |

### 15.6 Consumed Interfaces

| Provider | Consumed for |
|---|---|
| Security Gateway | Producer authentication, consumer authorization, tenant validation |
| Schema Registry | Schema resolution and version validation at admission |
| Observability Gateway | Mandatory signal emission about the Bus itself |

The Bus consumes remarkably little. This is deliberate: as the deepest coordination dependency in the system, every consumed interface is a potential cycle. Its only hard dependencies are the Trust Plane and the Schema Registry, both of which sit below it.

### 15.7 Data Ownership

The Bus owns exclusively: the stream logs, consumer group registrations and read positions, the dead-letter stream, the event archive index, and delivery state. It occupies the Stream and Cold tiers, mapped to `aos_events` per `02.7.1`.

It owns no event *content* semantics. The payload belongs to the producing domain; the Bus owns the envelope, the ordering, and the delivery guarantee.

### 15.8 State Management

| State | Class | Recovery |
|---|---|---|
| Published events | Durable-Committed | Never lost; never modified; the source of truth |
| Sequence assignments | Durable-Committed | Immutable |
| Consumer read positions | Durable-Progressive | Restored on consumer recovery |
| Delivery and acknowledgment state | Durable-Progressive | Unacknowledged events redelivered |
| Dead letter entries | Durable-Committed | Retained 30 days hot, indefinitely in archive |
| Backpressure state | Ephemeral-Discardable | Recomputed |

The Bus is the one subsystem whose state is the source of truth rather than a projection. `08.2.5` establishes the asymmetry: state corruption is repairable by replay, event corruption is irreparable. This is why the Bus is guarded more strictly than any other store.

### 15.9 Failure Domains

| Failure | Classification | Response |
|---|---|---|
| Producer emission failure | Critical to the occurrence | Occurrence unrecorded; gap detection and reconciliation workflow |
| Schema validation failure | Security-adjacent | Reject; suspend producer on repeat; alert |
| Bus unavailability | Critical, system-wide | Producers buffer locally with declared TTL; critical producers queue to fallback durable storage |
| Consumer processing failure | Transient or Critical | Unacknowledged; redelivered to another group member |
| Consumer group total failure | Degradable | Events retained in stream until recovery or dead-lettering |
| Consumer lag threshold breach | Operational | Alert; escalate if critical consumer; shed ephemeral events if non-critical |
| Network partition | Degradable | Both sides continue; buffered events reconciled on heal; causal order preserved by sequence reconciliation |
| Sequence gap | Critical | Gap detection workflow; reconciliation from producer state and durable workflow state |
| Event corruption | Security | Quarantine; flag as corrupted; emit compensating event; never delete |

The Bus never sheds critical streams. `08` rule 7 forbids shedding command, audit, and business state transition events under any load. Shedding applies only to telemetry and analytics.

### 15.10 Security Considerations

Every producer and consumer authenticates. Anonymous and pseudonymous emission and consumption are prohibited without exception. Authorization is enforced at two points: emission, where the producer must be permitted to emit the declared type within its tenant and scope; and subscription, where the consumer must be permitted to read the streams and types it requests.

Tenant isolation is enforced at the routing layer. Cross-tenant delivery is structurally impossible without an explicit bilateral grant, and grants are validated per delivery rather than cached indefinitely.

External data in payloads passes sanitization before emission. Events carry no secrets, credentials, or personally identifying information; sensitive context is referenced by correlation identifier.

All access to streams — emission, consumption, replay, administrative query — is logged in the audit stream, which is itself immutable and retained seven years.

Replay never mutates business state. Replayed events are tagged with replay metadata and processed in sandboxed context, so consumers can distinguish replay from live delivery.

### 15.11 Observability Requirements

The Bus emits: admission rate and rejection rate by cause, publication latency, delivery latency, acknowledgment latency, consumer lag per group, retry rate, dead-letter depth, backpressure activation, shedding events, archive lag, and gap detections.

The Bus occupies a distinctive position in observability: per `16.20.1`, events are the primary substrate from which metrics, logs, and traces are derived. The Bus is therefore both the transport for observability data and a subject of it. Its self-emission must not depend on its own healthy operation, or a Bus failure would be unobservable.

**[Implementation Decision] Out-of-band health emission.** Bus self-health signals are emitted through a channel independent of the Bus itself. Rationale: a subsystem cannot report its own unavailability through the mechanism that is unavailable. This mirrors the out-of-band requirement of the Panic Protocol control channel.

### 15.12 Performance Characteristics

| Operation | p50 | p99 | Maximum | Source |
|---|---|---|---|---|
| Emission to publication | 10ms | 50ms | 100ms | `08.22.1` |
| Publication to delivery | 5ms | 20ms | 50ms | `08.22.1` |
| Consumer processing, simple | 100ms | 500ms | 1s | `08.22.1` |
| Consumer processing, complex | 1s | 5s | 30s | `08.22.1` |
| Acknowledgment to archive | 1min | 5min | 15min | `08.22.1` |

Throughput: 50,000 events per second sustained ingestion; 100+ concurrent consumer groups per stream; 10,000 events per second replay for forensic reconstruction.

Scaling is horizontal by partitioning streams and distributing consumer groups across workers, without event schema changes or producer modification.

### 15.13 Dependency Relationships

Layer 1. Depends downward on Layer 0 (`kernel`, `core`, `persistence`, `schema_registry`) and on the Trust Plane.

Depended upon by every module above Layer 1 without exception. It is, with the Security Gateway, one of the two modules on which the entire system rests, and the second module constructed.

### 15.14 Architectural Constraints

- The Bus routes on metadata only; content-based routing is prohibited (`08.17.1`).
- Published events are immutable; correction is by new event (`08` rule 2, `08.14.2`).
- Durability precedes delivery (`08.14.1`).
- Delivery is at-least-once; idempotency belongs to the consumer (`08.17.2`).
- Acknowledgment follows durable processing, never precedes it (`08` rule 9).
- Critical streams are never shed (`08` rule 7).
- No direct producer-to-consumer path exists (`08` rule 16).
- Causality chains are preserved across all emissions and consumptions (`08` rule 17).
- Replay does not mutate live business state (`08` rule 11).
- No event crosses a tenant boundary without bilateral human approval (`08` rule 3).

### 15.15 Guarantees

1. **Truth preservation.** A published event is durable, immutable, and complete for its retention period.
2. **Decoupled coordination.** Producers do not know consumers; consumers do not know producers.
3. **At-least-once delivery.** No event is lost between publication and acknowledgment.
4. **Causal fidelity.** If A caused B, every consumer observes A before B.
5. **Stream ordering.** Total order within a stream, making derived state deterministic.
6. **Tenant isolation at routing.** Cross-tenant delivery is structurally impossible absent bilateral grant.
7. **Replayability.** The complete history is reconstructible in sandboxed context without side effect.
8. **No silent loss.** Every event is acknowledged, dead-lettered, or alerted within a defined window.

### 15.16 Interaction with the Constitution

The Bus realizes `08` in full and the component responsibility of `02.3.4`. The hub-and-spoke topology realizes `08.6.1`. Streams-as-logs realizes `08.6.2`. Consumer groups realize `08.6.3`. The causality tracker realizes `08.12.3` and `08.13`. The replay engine realizes `08.15`. The retention schedule realizes `08.15.4`.

Its position as source of truth rather than projection realizes `08.2.5`, and is the reason the Bus is constructed second, immediately after the Trust Plane and before every subsystem that derives state from it.

---

## 16. Memory Gateway

### 16.1 Purpose

The Memory Gateway is the sole access layer for all organizational experience. It realizes `09_MEMORY_OPERATING_MODEL` and the component responsibility of `02.3.5`.

It exists because agents without memory are stateless functions rather than intelligent systems. `09.2.1` establishes memory as "persistent organizational experience — the living tissue of the organization," and `09.2.6` establishes it as the system's primary competitive asset: "Memory compounds. The system must treat memory as its most valuable asset, prioritizing its preservation, validation, and availability above operational convenience."

`09.6.1` establishes the Gateway's defining constraint: **no agent, workflow, or service accesses memory directly.**

**Source note.** The uploaded artifact for `09` terminates mid-Section 10. Sections 10.1 through 30 are not present, including the enumerated Non-Violable Memory Rules and the Memory Glossary. This section is constructed from the body text present through Section 9, from the document's complete annotated Table of Contents (which is canonical), and from `09` provisions restated in `20B`. Where the source is silent, this section states the gap rather than inventing content.

### 16.2 Architectural Responsibilities

- Mediate all memory formation, retrieval, and disposition. No direct substrate access exists.
- Enforce the memory lifecycle: Conception, Formation, Validation, Integration, Activation, Decay, Disposition.
- Enforce the tier hierarchy and govern movement between tiers.
- Assign and maintain memory identity, confidence scores, and validity periods.
- Enforce ownership tiers: Private, Team, Business, Global.
- Enforce tenant, business, agent, and tier boundaries at every operation.
- Maintain lineage from every memory entry to its originating event or decision journal.
- Establish and traverse relational and semantic links.
- Execute decay: progressive reduction of relevance, confidence, and accessibility.
- Consume events to form memory; emit memory lifecycle events.

### 16.3 Internal Components

| Component | Responsibility |
|---|---|
| **Admission Controller** | Validates formation requests against schema, source attribution, and scope; rejects unstructured or schema-violating captures |
| **Formation Engine** | Constructs structured memory entries with full identity, provenance, and initial payload |
| **Validation Engine** | Assesses source reliability, cross-reference consistency, schema conformance, temporal relevance; assigns confidence and validity period |
| **Quarantine Store** | Holds entries failing validation for review; invisible to retrieval |
| **Integration Engine** | Establishes causal chains, detects contradiction, creates relational edges |
| **Tier Router** | Routes operations to Working, Durable, Semantic, or Cold tier per lifecycle state and access pattern |
| **Retrieval Engine** | Executes scoped queries across tiers; applies ownership, tenant, and role filters |
| **Relevance Ranker** | Ranks retrieval results for context assembly under declared budget |
| **Decay Engine** | Continuously evaluates entries for staleness; downgrades confidence; flags for review |
| **Tier Movement Controller** | Governs promotion and demotion between tiers; logs each movement as a memory operation |
| **Lineage Tracker** | Maintains and validates the unbroken chain to originating events and decisions |
| **Boundary Enforcer** | Kernel-supplied; enforces tenant, business, agent, and tier boundaries |
| **Memory Journal** | Kernel-supplied; append-only record of every formation, transition, and disposition |

### 16.4 Internal Architecture

The Gateway is organized around a strictly unidirectional pipeline and a four-tier substrate.

**The pipeline.** `09.6.4` is explicit: **Events → Memory → Knowledge**, and "corrections flow backward as new events, not as mutations." Memory consumes events to form experience; Knowledge consumes memory to form belief. The Gateway never writes to the Event Bus as a correction path and never writes into the Knowledge Base.

**The four tiers.** Working memory holds active execution context — highest velocity, lowest latency, ephemeral in service but durable against process loss. Durable memory holds validated, committed organizational experience and survives business sunset and agent retirement. Semantic memory is the associative retrieval tier enabling non-obvious experiential discovery. Cold memory is archival, never destroyed before the statutory retention period.

**Tier movement is lifecycle-driven, not time-driven.** `09.7.5` is specific: an entry is promoted from Working to Durable when validated, to Semantic when linked, and demoted to Cold when retrieval frequency falls below threshold and validity expires. Movement is itself a logged, auditable memory operation, not a background storage optimization.

**Formation is not validation.** `09.8.2` separates the two deliberately. Formation imposes structure; validation assesses reliability. An entry may be well-formed and unreliable. Entries failing validation are quarantined for review, not committed to Durable memory and not destroyed.

**Integration is mandatory before activation.** `09.8.4` states that "an unlinked memory entry is incomplete." Activation — the point at which an entry becomes visible to retrieval — follows integration. An entry that exists but has not been linked is invisible to agents by construction.

**Decay is degradation, not deletion.** `09.8.6` distinguishes them absolutely. The Decay Engine reduces confidence, flags staleness, and moves entries toward Cold. It does not delete. Deletion is Disposition, and Disposition to Purged requires both statutory expiry and explicit approval.

### 16.5 Public Interfaces

| Interface | Consumers | Purpose |
|---|---|---|
| Memory Formation | Agent Runtime, Workflow Engine, Event consumers, Human Interface | Submit an occurrence for formation |
| Memory Retrieval | Agent Runtime, Knowledge Gateway, Learning Gateway, Governance Gateway | Scoped, filtered, ranked query across tiers |
| Lineage Query | Governance Gateway, Observability Gateway, Human Interface | Trace an entry to its originating event, workflow, agent, decision |
| Relationship Traversal | Knowledge Gateway, Learning Gateway | Traverse relational and semantic links within permission scope |
| Memory Health | Observability Gateway | Retrieval latency, hit quality, growth rate, decay rate, validation backlog |

### 16.6 Consumed Interfaces

| Provider | Consumed for |
|---|---|
| Security Gateway | Authentication, authorization, memory scope validation, tenant enforcement |
| Event Bus | Event consumption for formation; memory lifecycle event emission |
| Schema Registry | Memory type schema resolution and version validation |
| Cost Manager | Retrieval and formation cost attribution |
| Observability Gateway | Mandatory signal emission |

### 16.7 Data Ownership

The Memory Gateway owns exclusively: memory entries across all four tiers, memory identity records, confidence and validity metadata, relational and semantic edges, lineage references, tier placement records, quarantine holdings, and the Memory Journal. It consumes all five persistence tiers and is mapped to `aos_memory` per `02.7.1`.

It owns no knowledge, no decision record, no event, and no agent identity. It holds memory *about* those things; it does not own them.

### 16.8 State Management

| State | Class | Recovery |
|---|---|---|
| Validated memory entries | Durable-Committed | Immutable once Validated; correction appends a linked entry |
| Entry lifecycle state | Durable-Mutable | Transitions append-only; state metadata mutable, payload frozen |
| Working memory | Ephemeral-Recoverable | Durable against process loss per `09.7.1`; rehydrated from Durable tier and workflow context |
| Relational edges | Durable-Mutable | New edges appended; existing edges not rewritten |
| Confidence scores | Durable-Mutable | Adjusted by Decay Engine and revalidation; history retained |
| Tier placement | Durable-Progressive | Each movement logged as an operation |
| Quarantine holdings | Durable-Progressive | Retained pending review; never silently discarded |

`09.9.3` establishes the immutability boundary precisely: once an entry enters Validated, "its core identity and payload are immutable. State transitions apply to the entry's lifecycle metadata and tier placement, never to the historical record itself."

### 16.9 Failure Domains

| Failure | Classification | Response |
|---|---|---|
| Formation schema violation | Transient or Critical | Rejected at Admission; producer notified; repeated violation escalates |
| Validation failure | Degradable | Quarantine for review; not committed; not destroyed |
| Integration failure | Degradable | Entry remains Validated but unactivated; retry integration |
| Semantic tier unavailable | Degradable | Fall back to structured retrieval with explicit degradation flag |
| Structured tier unavailable | Critical | Fall back to Working tier session context; halt if context is safety-critical |
| Cold tier unavailable | Degradable | Archival retrieval deferred; operational retrieval unaffected |
| Lineage break | Critical | Gap detection; reconciliation from event log |
| Decay engine failure | Operational | Memory bloat accumulates; alerted; retrieval quality degrades before correctness does |
| Boundary violation attempt | Security | Blocked; logged; Category 1 escalation |

The constitutional posture is graceful degradation of retrieval quality before failure of retrieval availability. No workflow fails solely because memory is degraded, though a workflow may pause if the missing memory is safety-critical.

### 16.10 Security Considerations

Every memory operation is authenticated and authorized against the requesting principal's declared memory scope. Read scope, write scope, and filters are declared in the agent manifest and enforced by the Gateway, not by the agent.

Four boundaries are enforced at every operation: tenant (rejects cross-tenant access absent anonymization and human approval), business (filters retrieval to the requesting business absent a shared workspace grant), agent (prevents access to another agent's Private memory), and tier (controls which consumers reach which persistence tiers by role and task classification).

Memory formed from external data passes sanitization before commitment. Memory carries no secrets, credentials, or personally identifying information beyond what its classification permits, and Restricted-class memory requires elevated permission.

Private memory transfer on agent retirement requires anonymization, per `06.11.3`. Business memory promotion to Global requires anonymization and human approval.

### 16.11 Observability Requirements

The Gateway emits: formation rate and rejection rate by cause, validation outcomes and confidence distribution, quarantine depth, integration success rate, activation latency, retrieval latency by tier, retrieval relevance indicators, decay throughput, tier movement volume, memory growth rate, and boundary enforcement outcomes.

Memory growth rate and decay throughput deserve particular emphasis. `09.3.2` names Decay Discipline as a permanent objective and states that "unbounded memory growth is a failure mode." The Observability Gateway must be able to detect the failure mode, which requires the Memory Gateway to expose both sides of the ledger.

### 16.12 Performance Characteristics

The source artifact for `09` terminates before its Performance Characteristics section (declared as Section 25 in its Table of Contents). Latency and throughput targets for memory operations are therefore **not available from the constitutional source**.

Two bounds are available indirectly and constrain memory operations regardless:

- Context assembly occurs within the agent's declared `max_context_tokens` and `max_context_assembly_time`, per `07.10.4`.
- Memory retrieval occurs inside the Agent Runtime's end-to-end task budgets of `05.25.1`.

**[Implementation Decision] Memory operation budgets are derived from the Knowledge Gateway's published budgets pending source recovery.** Rationale: `10.24.1` publishes canonical belief query at p50 50ms / p99 200ms / max 500ms, and memory retrieval sits below knowledge query in the same pipeline. Adopting equal or tighter budgets for structured memory retrieval is consistent and conservative. This is a derived engineering target, not a constitutional value, and is superseded the moment the `09` source is recovered.

### 16.13 Dependency Relationships

Layer 2. Depends downward on Layer 0, the Trust Plane, the Event Bus, and the Economic Plane.

Depended upon by the Knowledge Gateway at Layer 2 — a directional intra-layer dependency permitted because the pipeline Events → Memory → Knowledge is unidirectional and acyclic. Also depended upon by Decision, Agent Runtime, Workflow Engine, Learning, and Governance.

### 16.14 Architectural Constraints

- No direct memory access by any principal; the Gateway is the sole boundary (`09.6.1`).
- The pipeline is unidirectional: Events → Memory → Knowledge (`09.6.4`).
- Raw data is not memory until formed, validated, and attributed (`09.2.2`).
- Validated entries are immutable in identity and payload (`09.9.3`).
- An unlinked entry is incomplete and is not activated (`09.8.4`).
- Decay degrades; it does not delete (`09.8.6`).
- Purge requires both statutory expiry and explicit approval (`09.9.2`).
- Emergency transitions require Class D authority and remain in the audit trail (`09.9.4`).
- Memory identity persists a minimum of seven years regardless of status (`09.4.2`).
- Anonymous memory is inadmissible (`09.4.3`).

### 16.15 Guarantees

1. **Continuity.** No agent begins a task without access to relevant prior experience within its declared scope.
2. **Contextual fidelity.** Every entry carries why it occurred, under what conditions, and with what intent.
3. **Validated recall.** Observed experience and verified reliability are distinguishable at every retrieval.
4. **Ownership enforcement.** No principal accesses memory beyond its authorized boundary.
5. **Decay discipline.** Stale, irrelevant, and legally expired memory is degraded, archived, or purged rather than accumulating.
6. **Durability.** Memory written to the system survives agent retirement, business sunset, and workflow failure.
7. **Traceability.** Every entry traces to its originating event, workflow, agent, and decision.

### 16.16 Interaction with the Constitution

The Gateway realizes `09` as far as the source artifact extends, together with the component responsibility of `02.3.5` and the memory ownership tiers of `06.11.1`.

Gateway-mediated access realizes `09.6.1`. The four tiers realize `09.7`. The lifecycle realizes `09.8`. The state machine and its guards realize `09.9`. The unidirectional pipeline realizes `09.6.4`.

Where the source artifact is absent, this section marks the absence explicitly rather than filling it. The Section 12 performance gap and the missing Non-Violable Memory Rules are both recorded, and the latter should be treated as an open item for source recovery before the Memory Gateway's conformance suite can claim completeness.

---

## 17. Knowledge Gateway

### 17.1 Purpose

The Knowledge Gateway maintains the organization's body of validated belief. It realizes `10_KNOWLEDGE_OPERATING_MODEL`.

It exists because agents must reason over something more disciplined than raw experience. `10.2.6` states the position: agents "do not reason over unstructured memory dumps or raw event streams. They reason over a body of validated belief that has been checked for contradiction, linked into an ontology, and assigned confidence."

`10.2.1` sets the epistemic bar: "A belief without evidence is speculation. A belief without confidence is noise. A belief that cannot be falsified is dogma. Knowledge rejects all three."

### 17.2 Architectural Responsibilities

- Mediate all belief formation, validation, promotion, query, and deprecation.
- Extract candidate beliefs from memory through governed pipelines.
- Validate hypotheses across four dimensions and assign authoritative confidence.
- Integrate validated beliefs into the ontology and knowledge graph.
- Detect contradiction and execute reconciliation.
- Continuously revalidate canonical beliefs against new evidence and elapsed time.
- Enforce falsifiability: every belief carries explicit invalidation conditions.
- Maintain the organizational ontology under human ratification.
- Maintain graph integrity constraints.
- Deprecate and supersede without erasure.

### 17.3 Internal Components

| Component | Responsibility |
|---|---|
| **Extraction Engine** | Distils candidate beliefs from memory; applies relevance filter to prevent knowledge bloat |
| **Hypothesis Store** | Holds provisional beliefs during evaluation; invisible to reasoner consumers |
| **Validation Engine** | Assesses evidentiary sufficiency, cross-reference consistency, schema conformance, falsifiability |
| **Confidence Engine** | Assigns and updates confidence within the four constitutional bands |
| **Integration Engine** | Links validated beliefs into ontology and graph; establishes typed relationships |
| **Promotion Controller** | Elevates from Validated to Canonical; blocks on unresolved contradiction |
| **Contradiction Detector** | Continuously scans the canonical set for incompatible assertions |
| **Reconciliation Engine** | Applies supersession, scope narrowing, confidence adjustment, or routes to human arbitration |
| **Revalidation Scheduler** | Domain-dependent continuous re-evaluation of canonical beliefs |
| **Ontology Manager** | Maintains entity classes, relationship types, belief categories; enforces human ratification for change |
| **Graph Engine** | Node and typed-edge storage; traversal within permission scope; integrity constraint enforcement |
| **Query Engine** | Scoped, confidence-filtered belief retrieval |
| **Deprecation Controller** | Marks beliefs false or obsolete; links justification via lineage; never deletes |
| **Knowledge Journal** | Kernel-supplied; append-only record of formation, validation, promotion, contradiction, deprecation |

### 17.4 Internal Architecture

The Gateway is organized as a validation pipeline feeding a graph.

**The pipeline.** Extraction → Hypothesis Formation → Validation → Integration → Promotion → Active Use → Revalidation → Deprecation → Archival → Disposition. Hypotheses are ephemeral and exist only inside the pipeline; they are never visible to reasoner agents. This is a hard boundary: `10` rule 10 prohibits presenting speculative assertion as validated knowledge to any consumer.

**Promotion is not automatic upon validation.** `10.7.5` requires that integration be complete and no unresolved contradiction exist. A validated belief that contradicts a canonical belief is held, not promoted. `10` rule 4 states the invariant: no canonical belief may remain in the active set while an unresolved contradiction exists against it.

**Contradiction is a first-class state, not an error.** The canonical states include Contradicted, and reconciliation offers four strategies — supersession, scope narrowing, confidence adjustment, human arbitration. Arbitration is mandatory where both beliefs exceed 0.85 confidence, where Restricted knowledge is involved, where the contradiction spans business boundaries within a tenant, or where automated reconciliation has failed. Arbitration produces a binding resolution logged as a new knowledge entry with Class D authority.

**The graph enforces integrity.** `10.17.4` specifies three constraints the Graph Engine maintains continuously: no orphaned canonical nodes (every canonical belief participates in at least one relationship), no unresolved contradictory cycles (a belief may not contradict itself through a chain), and no dangling supersession references (a superseded belief links to its successor).

**Revalidation is continuous and domain-dependent.** Market knowledge is revalidated frequently; definitional knowledge rarely. Revalidation can raise confidence, lower it, or trigger deprecation when falsifiability conditions are met.

**The ontology is not self-modifying.** `10.16.4` is explicit. The Learning Gateway may propose extensions; adoption requires validation and human ratification. The Ontology Manager therefore holds no autonomous mutation path — a structural expression of `10` rule 13.

### 17.5 Public Interfaces

| Interface | Consumers | Purpose |
|---|---|---|
| Belief Query | Agent Runtime, Decision Gateway, Workflow Engine, Human Interface | Scoped, confidence-filtered canonical belief retrieval |
| Graph Traversal | Agent Runtime, Learning Gateway | Relationship traversal within permission scope |
| Hypothesis Submission | Learning Gateway, extractor agents, Human Interface | Submit a candidate belief for validation |
| Contradiction Query | Decision Gateway, Governance Gateway | Report contradiction status for a belief or belief set |
| Ontology Query | All reasoning consumers | Entity classes, relationship types, belief categories |
| Ontology Change Proposal | Learning Gateway, Evolution Gateway | Propose taxonomy extension; requires human ratification |
| Knowledge Health | Observability Gateway | Contradiction rate, confidence distribution, validation backlog, graph integrity |

### 17.6 Consumed Interfaces

| Provider | Consumed for |
|---|---|
| Security Gateway | Authentication, authorization, scope and sensitivity enforcement |
| Memory Gateway | Evidentiary substrate for extraction |
| Event Bus | Revalidation triggers, extraction cycle triggers, deprecation workflow triggers; belief lifecycle emission |
| Schema Registry | Knowledge type schema resolution |
| Cost Manager | Extraction and validation cost attribution |
| Observability Gateway | Mandatory signal emission |

### 17.7 Data Ownership

The Knowledge Gateway owns exclusively: knowledge entries, hypothesis holdings, the organizational ontology, the knowledge graph (nodes and typed edges), contradiction records, reconciliation records, confidence and falsifiability metadata, provenance records, and the Knowledge Journal. It occupies the Structured, Semantic, Graph, and Cold tiers.

It owns no memory. `10.6.4` is precise: "Memory may persist knowledge entries in its durable tiers for backup and audit purposes, but memory does not contain knowledge in any semantic sense; it contains the records from which knowledge was extracted."

### 17.8 State Management

| State | Class | Recovery |
|---|---|---|
| Validated and canonical beliefs | Durable-Committed | Immutable in content, evidence, and identity |
| Hypotheses | Ephemeral-Recoverable | Reconstructible from source memory; not authoritative |
| Confidence scores | Durable-Mutable | Updated by revalidation; history retained |
| Lifecycle state | Durable-Mutable | Transitions append-only |
| Ontology | Durable-Mutable | Versioned; changes require ratification |
| Graph edges | Durable-Mutable | Appended; supersession preserves predecessor |
| Contradiction records | Durable-Committed | Immutable; resolution appends |
| Quarantined hypotheses | Durable-Progressive | Retained for review; visible to extractors and humans only |

`10.18.2` states the immutability guarantee: a Validated belief "may never be modified, overwritten, or deleted. Its payload, identity, provenance, and evidentiary basis are frozen for all time."

### 17.9 Failure Domains

| Failure | Classification | Response |
|---|---|---|
| Extraction failure | Degradable | Hypothesis abandoned or quarantined; validation queue monitoring detects |
| Validation failure | Degradable | Quarantine for review; correction and resubmission permitted; never destroyed |
| Contradiction detected | **Epistemic** | Halt promotion; trigger reconciliation; escalate to arbitration where mandated |
| Contradiction backlog growth | Epistemic | Alert; governance escalation; canonical set integrity at risk |
| Graph integrity violation | Critical | Orphan, cycle, or dangling reference detected; repair workflow; alert |
| Confidence inflation anomaly | Epistemic | Audit; potential recalibration; extractor suspension |
| Knowledge Base unavailable | Degradable | Consumers fall back to Memory with explicit uncertainty flags; workflows pause only if the missing knowledge is safety-critical |
| Schema violation | Security-adjacent | Extractor suspension and alert |

`10.23.3` introduces a failure category unique to this subsystem: **Epistemic**, whose response is to quarantine affected beliefs and suspend the extractor, with immediate alert. The Kernel's five-category taxonomy is extended here by constitutional provision, not by implementation choice.

### 17.10 Security Considerations

Every producer and consumer authenticates. Anonymous formation and consumption are prohibited.

Four boundaries are enforced: tenant (cross-tenant rejected absent anonymization and human approval), business (filtered absent shared workspace grant), agent (restricted to declared capability scope and autonomy level), and **confidence** — a boundary unique to this Gateway, which blocks consumption of beliefs below the consumer's declared threshold.

Knowledge formed from external data passes sanitization. Restricted-sensitivity beliefs — financial, legal, security-critical, strategically critical — require elevated permission. Global knowledge promotion requires anonymization, validation, and human approval.

Consumers must propagate uncertainty. A belief at 0.75 confidence is provisional and must be treated as such downstream; suppression of that qualification is a conformance violation.

### 17.11 Observability Requirements

The Gateway emits four metric families per `10.22.1`: **Epistemic Health** (contradiction rate, average confidence by domain, validation backlog depth), **Graph Health** (orphan rate, cycle count, relationship distribution, traversal latency), **Operational Health** (formation rate, query rate, deprecation rate, revalidation cycle time), and **Consumer Health** (query latency, error rate).

Logs carry no Restricted payload content. Traces follow lineage references and correlation identifiers through the graph back to originating events.

Contradiction rate is the single most important signal this subsystem produces. `10.3.2` places Epistemic Coherence first among permanent objectives, and a rising contradiction rate is the leading indicator of its erosion.

### 17.12 Performance Characteristics

| Operation | p50 | p99 | Maximum | Source |
|---|---|---|---|---|
| Hypothesis formation to validation | 1s | 10s | 60s | `10.24.1` |
| Canonical belief query | 50ms | 200ms | 500ms | `10.24.1` |
| Graph traversal, three-hop | 100ms | 500ms | 2s | `10.24.1` |
| Revalidation cycle, single belief | 100ms | 500ms | 2s | `10.24.1` |
| Contradiction detection | 200ms | 1s | 5s | `10.24.1` |

Throughput: 1,000 hypothesis formations per second; 10,000 canonical belief queries per second; 5,000 graph traversals per second. Scaling is horizontal by partitioning the belief set by domain and distributing query load, without ontology change or producer modification.

Under load, non-critical operations — epistemic analytics, archival queries — are shed before canonical belief retrieval and contradiction detection. Safety-critical reasoning queries are never dropped.

### 17.13 Dependency Relationships

Layer 2. Depends downward on Layer 0, the Trust Plane, the Event Bus, the Economic Plane, and the Memory Gateway.

Depended upon by the Decision Gateway (Layer 3), which requires canonical beliefs as primary evidence, and by Learning, Governance, and the Agent Runtime.

### 17.14 Architectural Constraints

- No direct Knowledge Base access; the Gateway is the sole boundary (`10.6.1`).
- The pipeline is unidirectional; knowledge does not mutate memory (`10.6.4`).
- Hypotheses are never visible to reasoner consumers (`10.7.2`).
- No promotion to Canonical without validation and integration (`10` rule 3).
- No canonical belief remains active against an unresolved contradiction (`10` rule 4).
- Every belief carries a confidence score and falsifiability conditions (`10` rule 5).
- Nothing below 0.60 confidence is presented as canonical (`10` rule 9).
- Validated beliefs are immutable; correction appends (`10.18.2`).
- The ontology is not self-modifying; change requires human ratification (`10` rule 13).
- The Learning Model may not insert beliefs directly (`10.6.6`).
- Deprecation requires a justification entry linked via lineage (`10` rule 18).

### 17.15 Guarantees

1. **Epistemic coherence.** No unresolved contradiction persists in the canonical set.
2. **Validated authority.** Every belief traces to evidentiary support in memory, carries quantitative confidence, and is bounded by falsifiability.
3. **Reasoning substrate.** The belief set is structured for inferential reasoning across agents and workflows.
4. **Falsifiability maintenance.** Beliefs are proactively deprecated when their invalidation conditions are met.
5. **Bounded growth.** Stale, superseded, and irrelevant beliefs are deprecated and archived.
6. **Correction without erasure.** The record of what was once believed survives permanently.
7. **Forensic answerability.** For any canonical belief, the system answers: why do we believe this?

### 17.16 Interaction with the Constitution

The Gateway realizes `10` in full. Gateway mediation realizes `10.6.1`. The validation pipeline realizes `10.7` and `10.14`. Contradiction and reconciliation realize `10.15`. The ontology and its ratification requirement realize `10.16`. The graph and its integrity constraints realize `10.17`. Confidence bands realize `10.14.2`.

The confidence boundary — unique among the eleven Gateways — realizes `10.6.3` and is the mechanism by which uncertainty is prevented from propagating silently into commitment, which is the failure mode `11.13.3` and CIR-007 both address.

---

## 18. Decision Gateway

### 18.1 Purpose

The Decision Gateway is the constitutional checkpoint between deliberation and action. It realizes `11_DECISION_OPERATING_MODEL`.

It exists because every non-trivial action in Agent OS requires a governed commitment. `11.2.1` establishes the frame: "A decision is a governed commitment to a course of action. It is the moment the organization transitions from deliberation to obligation." `11.2.5` establishes its constitutional weight: "Decision is the constitutional checkpoint between human will and machine execution."

`11.2.4` establishes the boundary it enforces: **"An agent proposes; the Decision subsystem evaluates... Agency is capacity; Decision is permission."**

### 18.2 Architectural Responsibilities

- Mediate all commitment formation, evaluation, authorization, execution tracking, and disposition.
- Classify every decision by impact and reversibility into Classes A through D.
- Assemble evidence from canonical knowledge and supplementary memory.
- Enforce the mandatory multi-option requirement including the null option.
- Evaluate options with portfolio-aware scoring.
- Resolve required authority from class, risk, and confidence.
- Route Class C and D decisions for explicit human approval; never auto-approve on timeout.
- Verify compensation logic before committing any reversible decision.
- Manage standing orders, their scope, expiry, and per-invocation validation.
- Execute escalation with packaged context.
- Record every decision in an immutable Decision Journal with expected and actual outcome.
- Enforce portfolio circuit breakers.

### 18.3 Internal Components

| Component | Responsibility |
|---|---|
| **Proposal Receiver** | Accepts proposals from agents, workflows, scheduled reviews, business events, and humans |
| **Classifier** | Assigns Decision Class from impact, reversibility, and cost |
| **Option Validator** | Enforces the multi-option requirement; rejects single-option proposals for Class B and above |
| **Evidence Assembler** | Retrieves canonical beliefs and supplementary memory; flags evidentiary gaps and contradictions |
| **Evaluation Engine** | Scores options against objective fit, risk-adjusted return, strategic value, resource efficiency, reversibility |
| **Portfolio Scorer** | Applies portfolio-level weights; penalizes concentration; rewards correlation reduction |
| **Risk Assessor** | Assesses across financial, operational, reputational, legal, strategic dimensions; assigns risk class |
| **Authority Resolver** | Determines required authority from class, risk, and confidence; applies risk-adjusted escalation |
| **Confidence Engine** | Derives decision confidence from supporting belief confidence, option quality, risk, temporal relevance |
| **Approval Orchestrator** | Packages and routes human approval requests; enforces timeout semantics |
| **Standing Order Manager** | Validates invocations against scope, budget, time window, risk threshold; enforces 30-day expiry |
| **Escalation Router** | Packages and routes escalations upward through the authority chain |
| **Compensation Verifier** | Confirms compensation logic exists before committing a reversible decision |
| **Commitment Controller** | Finalizes identity, records expected outcome, designates reversibility, emits to Runtime |
| **Execution Tracker** | Tracks execution status without interfering in execution mechanics |
| **Outcome Recorder** | Records actual outcome against expected; triggers learning on divergence |
| **Reversal Controller** | Executes reversal within window; records reversal as a new linked decision |
| **Supersession Controller** | Manages replacement with lineage preservation and resource reallocation |
| **Circuit Breaker** | Enforces portfolio-level limits on capital at risk, correlation exposure, cash reserves |
| **Decision Journal** | Kernel-supplied; immutable, seven-year retention |

### 18.4 Internal Architecture

The Gateway is organized as a funnel with widening scrutiny.

**Classification first.** Every proposal is classified before anything else, because class determines every subsequent gate: evidence sufficiency, option count, confidence threshold, authority requirement, and approval path. Misclassification is the primary attack surface, and `11.24.2` names the corresponding drift pattern explicitly — "agents proposing decisions just below escalation thresholds."

**Evidence before evaluation.** Options cannot be evaluated against unassembled evidence. The Evidence Assembler retrieves canonical beliefs and flags gaps and contradictions explicitly. Contradictory evidence halts commitment and triggers reconciliation or escalation; `11` rule 8 admits no autonomous path past unresolved contradiction.

**Options are mandatory and include doing nothing.** For Class B and above, at least two distinct options plus the null option are required. `11.16.3` makes the null option the baseline: "A decision to act must demonstrate superiority to the null option." Single-option proposals are rejected at the Gateway, structurally, because commitment bias is a failure mode the constitution addresses by construction.

**Authority is risk-adjusted, not class-fixed.** `11.14.3` specifies the escalation: a Class B decision at High risk is treated as Class C for authority purposes; a Class C decision at Existential risk escalates to Class D. The Authority Resolver computes the effective authority requirement as the maximum of class-derived and risk-derived requirements.

**Approval gates are structurally incapable of auto-approval.** The Approval Orchestrator offers no timeout-approves path. On timeout, Class C decisions are deferred and Class D decisions are rejected pending explicit human action. Batched approval requests remain individually actionable and are never approved as a group. This is enforced by construction rather than configuration, because `11` rule 3 admits no exception and `11.18.3` forecloses "implicit consent."

**Compensation is verified before commitment, not after failure.** `11.21.2` states the rule: "Without compensation logic, the decision is treated as irreversible." A reversible designation with no pre-positioned compensation is not reversible, and the Gateway will not accept it as such.

**Reversal and supersession append.** Neither erases. A reversal is itself a new decision entry linked by lineage; the superseded decision's state is frozen and preserved.

### 18.5 Public Interfaces

| Interface | Consumers | Purpose |
|---|---|---|
| Decision Proposal | Agent Runtime, Workflow Engine, Human Interface, scheduled reviews | Submit a proposal with options and evidence |
| Decision Verification | Tool Gateway, Integration Gateway, Deployment Gateway | Verify a committed decision exists with authority matching a required class |
| Approval Response | Human Interface | Deliver approval, rejection, deferral, or modification demand |
| Standing Order Management | Human Interface | Issue, renew, or revoke a standing order |
| Reversal Request | Human Interface, Workflow Engine | Request reversal within the reversibility window |
| Outcome Report | Workflow Engine, Agent Runtime | Report actual outcome for journal completion |
| Decision Journal Query | Governance Gateway, Learning Gateway, Observability Gateway, Human Interface | Forensic reconstruction and outcome attribution |
| Decision Health | Observability Gateway | Velocity, latency, reversal rate, escalation rate, confidence calibration |

### 18.6 Consumed Interfaces

| Provider | Consumed for |
|---|---|
| Security Gateway | Identity and authority verification of proposer and authorizer |
| Knowledge Gateway | Canonical beliefs, confidence scores, contradiction status |
| Memory Gateway | Episodic context and prior decision history where evidence is sparse |
| Cost Manager | Budget verification and portfolio circuit breaker state |
| Event Bus | Trigger consumption; decision lifecycle emission |
| Human Interface | Approval request delivery and response |
| Observability Gateway | Mandatory signal emission |

### 18.7 Data Ownership

The Decision Gateway owns exclusively: decision records, option sets, evidence references, risk and confidence assessments, reversibility designations, compensation references, expected and actual outcomes, standing orders, escalation records, and the Decision Journal. It occupies the Structured and Cold tiers, mapped to `aos_approval` per `02.7.1`.

It owns no knowledge, no memory, no tool manifest, and no execution state. It records commitments; it does not execute them.

### 18.8 State Management

| State | Class | Recovery |
|---|---|---|
| Committed decision records | Durable-Committed | Immutable in identity, evidence, rationale |
| Pre-commitment proposals | Durable-Progressive | Recoverable; may be Rejected, Deferred, or Escalated |
| Approval requests | Durable-Progressive | Durable across multi-day human latency |
| Standing orders | Durable-Mutable | Expiry enforced; revocation immediate; committed decisions unaffected by revocation |
| Execution status | Durable-Progressive | Tracked from Runtime reports |
| Actual outcome | Durable-Committed | Nullable until resolved; immutable once recorded |
| Decision Journal | Durable-Committed | Append-only; seven-year minimum; terminal decisions retained indefinitely |

`11.8.3` places the immutability boundary at Committed: core identity, evidence, and rationale freeze there. Corrections append new decisions.

### 18.9 Failure Domains

| Failure | Classification | Response |
|---|---|---|
| Evidence insufficient | Degradable | Reject, escalate, or permit with uncertainty rider and enhanced monitoring |
| Contradictory evidence | Critical | Halt commitment; trigger reconciliation or human arbitration |
| Confidence below threshold | Degradable | Automatic escalation or deferral; agents may not suppress the warning |
| Single-option proposal, Class B+ | Critical to the proposal | Rejected at the Gateway |
| Authority insufficient | Critical to the proposal | Escalated upward; never approved by default |
| Approval timeout | Operational | Class C deferred; Class D rejected; never approved |
| Circuit breaker breach | Financial | Rejected or escalated regardless of local merit |
| Missing compensation logic | Critical to the proposal | Reversible designation refused; treated as irreversible |
| Gateway unavailable | Degradable | Runtime continues previously committed decisions; new non-trivial commitments halt |
| Malformed proposal | Contained | Rejected without affecting other proposals |

`11.27.1` specifies the degradation posture precisely: "No workflow fails solely due to Gateway unavailability, but non-trivial execution pauses." The system stops committing before it stops executing.

### 18.10 Security Considerations

Every producer and consumer authenticates. Anonymous formation and authorization are prohibited.

The Gateway enforces the authority boundary absolutely: no agent commits beyond its constitutional autonomy level, and Level 4 authority is cryptographically bound to human credentials and cannot be delegated. Approver and requester identities must be distinct, enforcing the self-approval prohibition of `14.17.5`.

Decision journals are tamper-evident, and commitment records are cryptographically bound to their evidence and authority such that no decision may be repudiated by its authorizer.

External data in proposals passes validation before acceptance. Bulk export of decision data requires Class D authority.

Standing orders are the principal privilege-escalation surface in this subsystem. Every invocation is validated against the order's declared scope, budget, time window, and risk threshold; drift detection monitors for orders "being stretched beyond intent" per `11.24.2`.

### 18.11 Observability Requirements

The Gateway emits five metric families per `11.26.1`: **Velocity** (proposals, commitments, completions per minute by class), **Latency** (proposal to commitment by class and authority), **Quality** (reversal rate, supersession rate, expected-versus-actual divergence), **Governance** (escalation rate, approval latency, standing order utilization), and **Health** (backlog depth, circuit breaker proximity, anomaly count).

Confidence calibration accuracy is a required signal. `16.16.1` composes Decision Health from it, and CIR-007 identifies miscalibration propagating through four subsystems as an open risk. The Gateway must expose predicted-versus-actual confidence performance, not merely confidence values.

### 18.12 Performance Characteristics

| Operation | p50 | p99 | Maximum | Source |
|---|---|---|---|---|
| Class A proposal to commitment | 100ms | 500ms | 2s | `11.28.1` |
| Class B proposal to commitment | 500ms | 2s | 10s | `11.28.1` |
| Class C approval request generation | 1s | 5s | 30s | `11.28.1` |
| Class D package assembly | 2s | 10s | 60s | `11.28.1` |
| Outcome recording | 100ms | 500ms | 2s | `11.28.1` |

Throughput: 1,000 Class A and B proposals per second; 100 Class C and D packages per minute; 10,000+ concurrent active decisions.

The Class A budget at p50 100ms, combined with a throughput of 1,000 per second and a mandatory immutable journal write per decision, is the principal driver of the journal write amplification identified as Risk R5 in the Planning Package. Class A decisions are trivial in impact and non-trivial in volume.

Under load, non-critical analytics and deferred reviews are shed before active commitments are delayed. Emergency and Panic decisions are never dropped.

### 18.13 Dependency Relationships

Layer 3. Depends downward on Layer 0, the Trust Plane, the Event Bus, the Economic Plane, the Memory Gateway, and the Knowledge Gateway.

Depended upon by every subsystem at Layer 4 and above. The Tool Gateway, Integration Gateway, and Deployment Gateway each require a committed decision record before permitting their respective effects, making the Decision Gateway the single most widely depended-upon subsystem above Layer 2.

### 18.14 Architectural Constraints

- No decision without unique identity, authenticated source, and documented evidence or explicit gap flag (`11` rule 1).
- No Class C or D commitment without explicit human approval (`11` rule 2).
- No auto-approval on timeout, inferred consent, or creative interpretation (`11` rule 3).
- No irreversible action without explicit human designation and acknowledged consequence review (`11` rule 4).
- No agent commits beyond its autonomy level (`11` rule 5).
- No bypass of the Gateway for direct producer-to-Runtime commitment (`11` rule 6).
- No proceeding on unresolved contradictory evidence without human arbitration (`11` rule 8).
- No Class B or higher commitment with a single documented option (`11` rule 9).
- No standing order exceeds 30 days without explicit renewal (`11` rule 11).
- No commitment without a documented expected outcome (`11` rule 16).
- No reversible commitment without pre-positioned compensation logic (`11` rule 17).
- Human decisions are not evaluated by the Gateway; they are terminal authority (`11.30.4`).

### 18.15 Guarantees

1. **Commitment integrity.** Every non-trivial action is preceded by a valid decision record.
2. **Authority enforcement.** No entity commits beyond its constitutional autonomy level.
3. **Evidence grounding.** Every decision traces to canonical knowledge or an explicit, declared evidentiary gap.
4. **Reversibility by default.** Autonomous commitments are reversible unless explicitly designated otherwise by a human.
5. **Approval gate integrity.** No Class C or D decision passes without explicit human action.
6. **Portfolio coherence.** Local optimality does not override portfolio concentration limits or circuit breakers.
7. **Outcome accountability.** Every commitment is tracked to actual outcome and compared against prediction.
8. **Forensic reconstruction.** For any commitment: what was decided, by whom, on what evidence, against what alternatives, with what result.

### 18.16 Interaction with the Constitution

The Gateway realizes `11` in full. The classification funnel realizes `11.5`. The authority spectrum realizes `11.9.1`. Confidence requirements realize `11.9.2` and `11.13.4`. Evidence sufficiency realizes `11.12.4`. The multi-option requirement realizes `11.16`. Approval gate enforcement realizes `11.18`. Standing orders realize `11.19`. Reversal and compensation realize `11.21`. Supersession realizes `11.22`. Circuit breakers realize `11.14.4`.

Its position as the permission checkpoint realizes `11.2.5`, and is why `12` rule 2, `17` rule 2, and `18` rule 2 each require a committed decision record before any external effect, environmental existence, or capability consumption may occur.

---

## 19. Tool Platform

### 19.1 Purpose

The Tool Platform is the sole authorized boundary between internal deliberation and external effect. It realizes `12_TOOL_OPERATING_MODEL` and the component responsibilities of `02.3.6` and `02.3.7`.

`12.2.1` states the metaphor that governs its construction: **"The tool is the constitutional airlock."** Agents reason, workflows coordinate, decisions authorize, and tools execute. No agent, workflow, or decision may interact with the external world except through a registered tool.

The platform comprises three modules with distinct constitutional responsibilities that the implementation preserves absolutely: the **Tool Registry** governs existence, the **Tool Gateway** authorizes, and the **Tool Executor** fulfils. `12.6.3` is explicit that the Executor "receives instructions from the Gateway; it does not evaluate authority or make policy decisions."

### 19.2 Architectural Responsibilities

**Tool Registry** — maintain the canonical inventory of all tools; store manifests, capability signatures, trust scores, ownership, provenance, and version lineage; serve discovery queries; monitor tool health and availability; enforce registration validation and trust seeding.

**Tool Gateway** — authorize every invocation; verify consumer authenticity, decision validity, autonomy boundary, tenant boundary, and budget sufficiency; validate the invocation contract; assign sandbox tier; mediate composition; record invocation; enforce circuit breakers and cost ceilings; manage deprecation and migration.

**Tool Executor** — dispatch validated invocations to sandboxed environments; manage sandbox lifecycle and resource limits; inject secrets; enforce timeouts and cost ceilings; capture and validate output; guarantee sandbox destruction.

### 19.3 Internal Components

**Tool Registry**

| Component | Responsibility |
|---|---|
| Manifest Store | Tool manifests, capability signatures, contracts, sandbox requirements, cost models, compensation logic |
| Registration Validator | Schema compliance, contract consistency, sandbox feasibility, compensation validation, provenance verification, economic review |
| Trust Engine | Composite trust score computation, decay, threshold enforcement |
| Discovery Engine | Capability match, domain search, reputation filter, cost filter; hierarchical resolution |
| Health Monitor | Dependency liveness, endpoint responsiveness, sandbox readiness; availability state |
| Lifecycle Controller | Designed → Registered → Validated → Active → Deprecated → Retired → Archived, plus Suspended |
| Version Lineage Store | Predecessor and successor linkage across tool versions |

**Tool Gateway**

| Component | Responsibility |
|---|---|
| Authority Verifier | Consumer authenticity, decision validity, autonomy boundary, tenant boundary, budget sufficiency |
| Contract Assembler | Constructs the invocation contract with idempotency key, decision reference, capability request, context package, cost ceiling, timeout, compensation reference, attribution chain |
| Contract Validator | Validates all components present and consistent before dispatch |
| Input Validator | Validates parameters against the declared input contract |
| Sandbox Assigner | Assigns the tier from the manifest; refuses any tier below the declared minimum |
| Selection Advisor | Applies portfolio-aware weighting to consumer selection |
| Composition Mediator | Mediates chained invocations; enforces sandbox escalation prohibition |
| Circuit Breaker | Per-tool and portfolio-level failure and cost thresholds |
| Output Validator | Validates output against the declared output contract before return |
| Deprecation Controller | Notice periods, successor identification, migration enforcement |
| Invocation Record | Kernel-supplied; immutable, seven-year retention |

**Tool Executor**

| Component | Responsibility |
|---|---|
| Sandbox Manager | Lifecycle across the four tiers: None, Container, gVisor, Firecracker |
| Resource Governor | CPU, memory, disk, network bandwidth limits |
| Secret Injector | Injects secret values into the sandbox at invocation time under Security Gateway authorization |
| Egress Controller | Network deny-by-default with explicit allowlist per tier |
| Timeout Enforcer | Hard execution bound with immediate termination on breach |
| Cost Monitor | Mid-flight cost ceiling monitoring with immediate halt |
| Output Capture | Captures and structures output for Gateway validation |
| Cleanup Guarantor | Guarantees sandbox destruction on every path, including failure and timeout |

### 19.4 Internal Architecture

The platform's architecture is governed by a strict separation of concerns across three modules, and by the principle that **authority is resolved before effect is possible**.

**The Registry governs existence, not operation.** It answers what tools exist, what they promise, how trusted they are, and whether they are healthy. It never dispatches. A tool present in the Registry is discoverable; discoverability is not authorization.

**The Gateway is the only path from intent to effect.** Every invocation traverses it. Its verification sequence is ordered so that the cheapest disqualifying check runs first: consumer authenticity, then autonomy boundary, then tenant boundary, then decision validity, then budget sufficiency, then input contract, then sandbox assignment. A request failing an early check consumes no downstream resource.

**The invocation contract is formed before dispatch and recorded immutably.** `12.17.1` frames it as "a constitutional contract between three parties: the consumer (who requests), the Gateway (who authorizes), and the Executor (who fulfils)." Its recording precedes execution, so that an external effect can never occur without a prior immutable record of its authorization.

**The Executor makes no policy decisions.** It receives a validated contract and fulfils it within its terms. `12.17.4` is explicit: "If the tool exceeds its cost ceiling, timeout, or sandbox boundary, the Executor halts execution and reports failure. The Executor does not reinterpret contract terms." This is the structural reason the Executor is a separate module: policy and execution must not share a process.

**Sandbox escalation, never de-escalation.** The Gateway refuses any request to execute below a tool's declared tier, even where a consumer requests a lower tier for performance. In composition, `12.18.3` requires the entire chain to execute at the highest tier any component requires — a pipeline containing a Firecracker-tier tool executes entirely within Firecracker isolation.

**Composition flows through the Gateway.** `12` rule 17 prohibits direct tool-to-tool invocation absolutely. Chained tools are chained by the consumer or orchestrator through repeated Gateway mediation, with each tool retaining its own identity, audit trail, and attribution chain. The output of one tool is never anonymous input to another; it carries provenance linking it to the producing invocation.

**[Implementation Decision] Sandbox pre-warming for the Container tier.** Container-tier sandboxes may be pre-warmed in a pool to meet the p50 100ms sandbox preparation budget of `12.22.1`. gVisor and Firecracker tiers are not pooled across invocations. Rationale: the preparation budget is tight for cold container start, while pooling higher-isolation tiers would risk state leakage across invocations, which the isolation guarantee forbids. This is a performance strategy bounded by the isolation constraint.

### 19.5 Public Interfaces

| Interface | Provider | Consumers | Purpose |
|---|---|---|---|
| Tool Discovery | Registry | Agent Runtime, Workflow Engine, Human Interface | Capability, domain, reputation, and cost-filtered search |
| Tool Registration | Registry | Human Interface, Plugin Manager, Evolution Gateway | Submit a manifest for validation |
| Tool Health Query | Registry | Workflow Engine, Observability Gateway | Availability state and dependency health |
| Tool Invocation | Gateway | Agent Runtime, Workflow Engine, Human Interface | Request a mediated tool invocation |
| Compensation Invocation | Gateway | Workflow Engine | Invoke a tool's compensation during saga rollback |
| Invocation Record Query | Gateway | Governance, Learning, Observability, Human Interface | Forensic reconstruction and lineage |
| Tool Health Signals | All three | Observability Gateway | Usage, performance, reliability, economic, trust, security metrics |

### 19.6 Consumed Interfaces

| Provider | Consumed by | Purpose |
|---|---|---|
| Security Gateway | Gateway, Executor | Consumer authentication, permission verification, secret authorization and injection policy |
| Decision Gateway | Gateway | Committed decision verification with authority matching the tool's risk class |
| Cost Manager | Gateway | Pre-flight budget check; post-flight cost attribution |
| Integration Gateway | Gateway | Verification that a tool's declared external capability is backed by an active, approved integration |
| Event Bus | All three | Lifecycle emission; health and decision event consumption |
| Observability Gateway | All three | Mandatory signal emission |

### 19.7 Data Ownership

**Tool Registry** owns tool manifests, capability signatures, trust scores, provenance records, ownership records, health history, and version lineage. Structured tier.

**Tool Gateway** owns invocation contracts, Invocation Records, selection bindings, circuit breaker state, and deprecation schedules. Structured and Cold tiers.

**Tool Executor** owns sandbox execution records and artifact references. Working and Cold tiers.

No module in the platform owns decision records, integration manifests, agent identity, or secret values.

### 19.8 State Management

| State | Class | Recovery |
|---|---|---|
| Tool manifests | Durable-Committed once Active | Core manifest, contracts, and sandbox requirements immutable; change requires new version |
| Trust scores | Durable-Mutable | Recomputable from invocation history |
| Tool lifecycle state | Durable-Mutable | Transitions append-only |
| Invocation contracts | Durable-Committed | Recorded immutably before dispatch |
| Invocation Records | Durable-Committed | Append-only; seven-year minimum |
| Sandbox state | Ephemeral-Discardable | Destroyed on every path; never reused across invocations at gVisor and Firecracker tiers |
| Circuit breaker state | Ephemeral-Recoverable | Recomputed from recent invocation history |

`12.9.3` places the immutability boundary at Active: manifest, contracts, and sandbox requirements freeze there, and behavioural change requires a new Tool ID with lineage.

### 19.9 Failure Domains

| Failure | Classification | Response |
|---|---|---|
| Registration validation failure | Contained | Rejected; no Tool ID issued |
| Trust score below threshold | Operational | Suspended from autonomous use; human-only invocation permitted |
| Authority verification failure | Critical to the invocation | Blocked before any external effect; logged |
| Missing or insufficient decision record | Critical to the invocation | Blocked; `12` rule 2 |
| Input contract violation | Contained | Rejected before sandbox entry |
| Transient tool failure | Transient | Exponential backoff within declared retry policy |
| Degraded tool output | Degradable | Partial output returned with degradation flag; consumer alerted |
| Critical tool failure | Critical | Halt, preserve state, trigger compensation if mutating, escalate |
| Sandbox escape attempt | **Security** | Category 1 incident; isolate, revoke pending requests, suspend tool, alert human |
| Cost ceiling breach | Financial | Immediate halt mid-flight; freeze consumer budget; alert |
| Timeout breach | Critical | Immediate termination; sandbox destroyed; failure reported |
| Circuit breaker trip | Operational | Subsequent invocations rejected until health restored |
| Output contract violation | Degradable | Rejected; retry or error propagation; unvalidated output never returned |

`12.21.5` states the posture: "An unclassified tool failure is treated as critical. The Gateway alerts immediately rather than assuming success."

### 19.10 Security Considerations

This platform is the system's primary attack surface, because it is the only path to external effect.

**Sandbox enforcement is absolute.** Every tool executes within its declared tier. The Executor verifies boundaries before dispatch. Sandbox escapes are Category 1 security incidents, not operational failures.

**Secrets never reach tools as values through any path visible to a consumer.** The Executor injects values into the sandbox environment at invocation time under Security Gateway authorization. Tools receive references. Secrets appear in no context, log, or audit trail.

**Input and output are both untrusted.** Data entering an invocation passes sanitization and input-contract validation. Data returning passes output-contract validation before reaching the consumer. `12.25.4` treats external return data as untrusted until validated — a distinction frequently missed, since output is often assumed safe because the tool was authorized.

**No self-escalation.** A tool may not escalate its own permissions, access resources outside its capability signature, or invoke other tools directly. All tool-to-external interaction is mediated by the Executor; all tool-to-consumer interaction by the Gateway.

**Trust decay prevents stale privilege.** A tool unused for 60 days loses five percent of its trust score, preventing dormant high-trust tools from receiving critical assignments without revalidation.

### 19.11 Observability Requirements

The platform emits six metric families per `12.27.1`: **Usage** (invocation rate, capability and consumer distribution), **Performance** (latency distribution, throughput, queue depth), **Reliability** (success rate, failure classification distribution, retry rate), **Economic** (cost burn rate, budget utilization, circuit breaker proximity), **Trust** (score distribution, drift anomaly count, suspension events), and **Security** (sandbox violation attempts, permission escalation attempts, sanitization failures).

The Security family is the highest-priority emission in the platform. Sandbox violation attempts and permission escalation attempts are Category 1 precursors and must reach the Observability Gateway and Security Gateway without delay or batching.

Traces follow an invocation from consumer request through Gateway authorization, Executor dispatch, sandbox execution, and output return.

### 19.12 Performance Characteristics

| Operation | p50 | p99 | Maximum | Source |
|---|---|---|---|---|
| Registry query | 50ms | 200ms | 1s | `12.22.1` |
| Gateway authorization | 20ms | 100ms | 500ms | `12.22.1` |
| Sandbox preparation | 100ms | 500ms | 2s | `12.22.1` |
| Tool execution, observational | 2s | 10s | 30s | `12.22.1` |
| Tool execution, mutating | 5s | 30s | 120s | `12.22.1` |
| Output validation and return | 10ms | 50ms | 200ms | `12.22.1` |

Throughput: 10,000 invocations per minute sustained; 5,000+ concurrent executions; 1,000 Registry queries per second. Scaling is horizontal by partitioning on tenant and capability domain.

The Gateway authorization budget of p50 20ms is among the tightest in the system and is a principal input to CIR-004. It presumes cached authorization within token time-to-live; a cold authorization traversing the full Security and Decision verification chain will not meet it.

### 19.13 Dependency Relationships

Layer 4. The Registry depends on the Trust Plane, Event Bus, and Layer 0. The Gateway depends additionally on the Decision Gateway, Cost Manager, Integration Gateway, and the Registry. The Executor depends on the Gateway and the Trust Plane for secret injection.

Depended upon by the Agent Runtime and Workflow Engine at Layer 5, and by the Learning Gateway for tool execution evidence.

### 19.14 Architectural Constraints

- No invocation without prior registration and validation (`12` rule 1).
- No execution without a valid decision record of matching authority (`12` rule 2).
- No effect outside the declared capability signature (`12` rule 3).
- No execution outside the declared sandbox tier (`12` rule 4).
- No direct secret handling by tools (`12` rule 5).
- No self-escalation (`12` rule 6).
- No anonymous registration (`12` rule 7).
- No mutating tool registered without compensation logic (`12` rule 9).
- No bypass of the Gateway for consumer-to-executor invocation (`12` rule 11).
- No tool-to-tool invocation (`12` rule 17).
- The Executor evaluates no authority and reinterprets no contract term (`12.6.3`, `12.17.4`).
- Registry governs existence; it does not execute (`12.6.1`).

### 19.15 Guarantees

1. **Boundary integrity.** No external effect occurs except through a registered, validated, authorized tool.
2. **Authority verification.** Every invocation traces to a decision record of sufficient authority.
3. **Sandbox enforcement.** No tool executes below its declared isolation tier, alone or in composition.
4. **Secret non-exposure.** No secret value reaches an agent, workflow, decision journal, or audit record.
5. **Economic control.** No invocation exceeds its cost ceiling or the consumer's remaining budget.
6. **Reversibility support.** Every mutating tool carries validated, idempotent compensation logic.
7. **Attribution completeness.** Every external effect traces to tool, consumer, decision, workflow, agent, human, and budget.
8. **Cleanup guarantee.** Sandboxes are destroyed on every path.

### 19.16 Interaction with the Constitution

The platform realizes `12` in full and the component responsibilities of `02.3.6` and `02.3.7`. The three-module separation realizes `12.6.1` through `12.6.3` exactly. The invocation contract realizes `12.17`. Sandbox tiering realizes `12.5.1` and `12.9`. Trust scoring realizes `12.16`. Composition mediation realizes `12.18`. Deprecation realizes `12.29`.

The airlock metaphor of `12.2.1` is preserved structurally: the Gateway is a boundary a consumer cannot cross unmediated, and the Executor is the only component in the system authorized to spawn arbitrary processes.

---

## 20. Integration Platform

> **Construction blocked by CIR-001.** `19` non-violable rule 22, `17` rule 21, and `18` rule 18 prohibit constitutional documents from naming specific technologies or providers, while `03_TECH_STACK` names approximately fifty. The portability guarantees of `17.23` and the provider-neutrality obligations of `17.23.6` depend on how that prohibition is scoped. Construction of this platform does not begin until CIR-001 is resolved at G3 or G4. This section specifies the architecture; it does not authorize its construction.

### 20.1 Purpose

The Integration Platform is the sovereign bridge between Agent OS and the external ecosystem. It realizes `17_INTEGRATION_OPERATING_MODEL` and, in the LLM Router, the component responsibility of `02.3.8`.

`17.2.1` states its governing metaphor: the bridge "does not drive the vehicle; it verifies that the road on the other side exists, is safe, is affordable, and can be exited without trapping the traveler." `17.2.7` states its constitutional purpose: "Just as a nation negotiates treaties without becoming subject to foreign law, Agent OS integrates with external systems without ceding constitutional authority."

The platform comprises the **Integration Registry**, the **Integration Gateway** (which contains the Abstraction Layer), and the **LLM Router**. The Router is distinct because it is an internal abstraction over model tiering, while integrations are governed external relationships. A model provider is an external capability provider; the Router consumes integrations rather than replacing them.

### 20.2 Architectural Responsibilities

**Integration Registry** — maintain the canonical inventory of external capability relationships; store manifests, capability abstractions, provider provenance, trust scores, contract terms, and portability declarations; serve discovery; maintain abstraction-to-integration mappings and alternative provider mappings; monitor provider concentration.

**Integration Gateway** — verify external provider identity; validate contracts against organizational policy; resolve approval authority; perform budget pre-checks; monitor provider health; enforce tenant boundaries; resolve capability abstractions to active integrations; record consumption; enforce circuit breakers; manage deprecation and retirement including data extraction verification.

**LLM Router** — route all inference; select model tier by task complexity, cost budget, and availability; manage local inference; execute the prompt pipeline; maintain semantic and exact caches; enforce token budgets; track cost per request, agent, and business; enforce failover chains.

### 20.3 Internal Components

**Integration Registry**

| Component | Responsibility |
|---|---|
| Manifest Store | Integration manifests, capability abstractions, provider contracts, data handling commitments, portability declarations, cost models, health expectations, dependency declarations |
| Registration Validator | Schema, provider provenance, contract policy alignment, data handling, portability assessment, risk tier confirmation, economic review |
| Trust Engine | Composite trust score across six weighted dimensions; decay; threshold enforcement |
| Abstraction Map | Capability abstraction to fulfilling integration mappings; alternative provider mappings |
| Concentration Monitor | Portfolio-level provider concentration ratios; flags concentration risk |
| Discovery Engine | Abstraction match, risk tier, cost, trust, scope, and data-handling filtered search |
| Lifecycle Controller | Proposed → Registered → Validated → Approved → Active → Deprecated → Retired → Archived, plus Suspended |

**Integration Gateway**

| Component | Responsibility |
|---|---|
| Abstraction Layer | Maps provider-specific external capabilities to provider-neutral internal signatures |
| Authority Verifier | Consumer authenticity, decision validity at required I-class, policy alignment, autonomy boundary, tenant boundary, budget sufficiency |
| Contract Validator | Ten-component contract validation before activation |
| Contract Monitor | Continuous execution monitoring; breach detection on cost, data handling, service expectations, unilateral term modification |
| Data Classification Enforcer | Blocks transmission of data above an integration's declared classification limit |
| Health Monitor | Provider dependency liveness, endpoint responsiveness, compliance attestation currency |
| Composition Mediator | Chained consumption; risk escalation prohibition |
| Circuit Breaker | Per-integration and portfolio-level failure and cost thresholds |
| Deprecation Controller | Notice periods, successor identification, migration enforcement |
| Retirement Controller | Data extraction verification, contract termination, archival |
| Consumption Record | Kernel-supplied; immutable, seven-year retention |

**LLM Router**

| Component | Responsibility |
|---|---|
| Complexity Classifier | Classifies task complexity to select tier |
| Tier Selector | Nano, Standard, Premium selection by complexity, budget, availability |
| Prompt Pipeline | The ten-stage pipeline of `02.8.5` |
| Context Assembler Client | Requests context from the Memory Gateway within declared budget |
| Sanitization Stage | Scrubs external data before prompt rendering |
| Token Budget Enforcer | Pre-flight token counting against agent and workflow budget |
| Exact Cache | Deterministic response cache keyed on model, prompt, and parameters |
| Semantic Cache | Similarity-based response cache |
| Structured Output Enforcer | Enforces schema-conformant output |
| Grounding Validator | Validates factual claims against cited sources; raises hallucination flags |
| Failover Controller | Circuit breakers per endpoint; tier and provider failover chains |
| Cost Tracker | Per request, per agent, per business attribution |

### 20.4 Internal Architecture

**The Abstraction Layer is the platform's constitutional core.** `17.6.3` specifies it precisely: "Tools reference the abstraction, not the provider. When a provider is substituted, the abstraction remains constant; only the integration manifest and contract change." Every design decision in the platform serves this property, because it is the mechanism by which vendor independence is structural rather than aspirational.

**Consumers bind to abstractions; the Gateway resolves.** A tool declares that it requires a capability abstraction. At invocation, the Gateway resolves that abstraction to an active integration subject to trust score, cost, health, and policy constraints. Multiple integrations may fulfil one abstraction. Substitution requires no change to the consuming tool.

**Approval is per-integration and human.** `17.14.1` classifies integration approval as a Class C or D decision recorded immutably in the Decision Gateway. Standing orders may pre-authorize integration classes, but "each integration instance requires specific approval." No integration becomes Active autonomously.

**Data classification is enforced at the boundary, not by the provider.** The Gateway blocks transmission of data above an integration's declared classification limit before it leaves the system. A T1 integration cannot receive Confidential or Restricted data. This is enforced by the Gateway because a provider's assurance that it will not retain data is not a control.

**Portability is verified at registration and monitored continuously.** Every integration declares data extractability, schema standardization, abstraction completeness, and migration cost. Low-portability integrations require heightened approval authority. `17.20.1` treats detected lock-in as a distinct failure category — **Portability** — whose response is governance review, restriction of new bindings, and migration planning.

**The LLM Router sits above the Integration Gateway, not beside it.** Model providers are external capability providers. The Router selects a tier and a model; the Gateway governs the relationship with whoever provides it. This layering is what permits `01.3.1` Local First to hold: the Nano and Standard tiers may be fulfilled by locally-hosted capability with no external integration at all, and the Premium tier degrades to unavailable rather than to failure.

**The prompt pipeline is fixed in order.** `02.8.5` specifies ten stages: template selection, context retrieval, context assembly, input sanitization, prompt rendering, token budget check, invocation, output parsing, grounding validation, cache storage. Sanitization precedes rendering; the budget check precedes invocation; grounding validation precedes cache storage. Reordering any stage breaks a constitutional guarantee.

**[Implementation Decision] Abstraction resolution is cached per workflow, not per invocation.** Once the Gateway resolves an abstraction to an integration for a given workflow, the binding is held for the workflow's duration unless the integration becomes unavailable. Rationale: the abstraction resolution budget of p50 10ms per `17.21.1` is tight, and mid-workflow provider switching would produce inconsistent behaviour across a single business process. This is a consistency and performance strategy; it does not alter the substitutability guarantee, which operates across workflows.

### 20.5 Public Interfaces

| Interface | Provider | Consumers | Purpose |
|---|---|---|---|
| Integration Discovery | Registry | Tool Gateway, Human Interface, Workflow Engine | Abstraction, risk, cost, trust, and scope-filtered search |
| Integration Registration | Registry | Human Interface | Submit a manifest for validation |
| Abstraction Resolution | Gateway | Tool Gateway | Resolve a capability abstraction to an active integration |
| Capability Consumption | Gateway | Tool Gateway | Mediated external capability consumption |
| Integration Health | Registry, Gateway | Workflow Engine, Observability Gateway | Availability, provider health, compliance currency |
| Consumption Record Query | Gateway | Governance, Learning, Observability, Human Interface | Forensic reconstruction and lineage |
| Inference Request | LLM Router | Agent Runtime | Tier-routed inference with structured output |
| Model Tier Health | LLM Router | Observability Gateway | Tier availability, cache hit rates, cost per hour, failover state |

### 20.6 Consumed Interfaces

| Provider | Consumed by | Purpose |
|---|---|---|
| Security Gateway | All three | Provider identity verification, tenant isolation, secret reference policy and injection |
| Decision Gateway | Gateway | Integration approval decision verification at required I-class |
| Cost Manager | Gateway, Router | External spend budget checks; cost attribution |
| Memory Gateway | Router | Context retrieval for the prompt pipeline |
| Event Bus | All three | Lifecycle emission; health and budget event consumption |
| Observability Gateway | All three | Mandatory signal emission |

### 20.7 Data Ownership

**Integration Registry** owns integration manifests, capability abstractions, provider provenance, trust scores, abstraction mappings, alternative provider mappings, and concentration metrics. Structured tier.

**Integration Gateway** owns provider contracts, Consumption Records, contract breach records, health history, and circuit breaker state. Structured and Cold tiers.

**LLM Router** owns model tier configuration, exact and semantic caches, token accounting, and failover state. Working and Semantic tiers.

No module owns tool manifests, decision records, or memory content.

### 20.8 State Management

| State | Class | Recovery |
|---|---|---|
| Integration manifests | Durable-Committed once Active | Manifest, abstraction, and data handling commitments immutable; change requires new version |
| Provider contracts | Durable-Committed | Recorded immutably before activation |
| Trust scores | Durable-Mutable | Recomputable from consumption history |
| Consumption Records | Durable-Committed | Append-only; seven-year minimum |
| Abstraction bindings | Ephemeral-Recoverable | Re-resolvable; workflow-scoped |
| Exact and semantic caches | Ephemeral-Discardable | Recomputed; loss costs only inference |
| Failover state | Ephemeral-Recoverable | Recomputed from endpoint health |

### 20.9 Failure Domains

| Failure | Classification | Response |
|---|---|---|
| Registration validation failure | Contained | Rejected; no Integration ID issued |
| Trust below threshold | Operational | Suspended from autonomous use |
| Transient provider error | Transient | Exponential backoff within declared retry policy |
| Degraded provider output | Degradable | Partial output with degradation flag |
| Critical provider failure | Critical | Halt, preserve state, trigger tool compensation if mutating, escalate |
| Data handling violation | **Security** | Isolate integration, revoke pending requests, suspend, alert human |
| Cost ceiling breach | Financial | Block spend, freeze consumer budget, alert |
| **Portability failure** | Portability | Flag for governance review, restrict new bindings, initiate migration planning |
| Contract breach by provider | Security or Critical | Breach flagged; possible suspension |
| Provider concentration breach | Operational | Flag; restrict new bindings until diversification |
| All model tiers unavailable | Critical | Non-critical tasks deferred; critical tasks escalated to human per `02.16.4` |
| Premium tier unavailable | Degradable | Degrade to Standard or Nano with explicit quality flag; core operation continues |

The final row is the constitutional test of `01` non-violable rule 2. Premium tier unavailability must be a degradation, never a failure, or the system cannot operate without internet connectivity.

### 20.10 Security Considerations

**Providers are counterparties, never principals.** They hold no identity in the Security Gateway, no authority in the Decision Gateway, and no stewardship in the Governance Gateway. Their relationship is governed exclusively by contract through this platform.

**Secrets are injected by the Security Gateway through the Tool Executor**, never handled by integrations. Manifests reference secrets by identifier. No secret appears in integration context, log, or audit trail.

**Data classification enforcement is pre-transmission.** The Gateway blocks over-classified data before it leaves the system rather than relying on provider commitments.

**Tenant isolation is absolute.** Integrations scoped to one tenant may not process another tenant's data. Cross-tenant sharing requires bilateral human approval, anonymization review, and isolation verification.

**External return data is untrusted.** Output passes validation against the capability abstraction's declared schema before reaching the consumer. `17` rule 13 additionally prohibits presenting unvalidated external data as internal knowledge without provenance and confidence metadata — the boundary between Integration and the Knowledge Gateway.

### 20.11 Observability Requirements

The platform emits seven metric families per `17.26.1`: Usage, Performance, Reliability, Economic, Trust, Security, and **Portability** (migration frequency, provider concentration ratios, abstraction completeness scores).

Portability metrics are unique to this platform and are the leading indicator of sovereignty erosion. `17.27.2` requires Governance to consume increasing provider concentration and declining portability scores as drift signals; the platform must expose both.

The LLM Router additionally emits tier distribution, cache hit rates against the constitutional targets of `02.8.7` (exact cache above 30 percent, semantic cache above 15 percent), token consumption, and cost per hour against the alerting threshold of `02.13.6`.

### 20.12 Performance Characteristics

| Operation | p50 | p99 | Maximum | Source |
|---|---|---|---|---|
| Registry query | 50ms | 200ms | 1s | `17.21.1` |
| Gateway authorization | 20ms | 100ms | 500ms | `17.21.1` |
| Provider health check | 500ms | 2s | 5s | `17.21.1` |
| Capability abstraction resolution | 10ms | 50ms | 200ms | `17.21.1` |
| Integration context assembly | 50ms | 200ms | 1s | `17.21.1` |
| External capability consumption | 2s | 10s | 30s | `17.21.1` |

Throughput: 10,000 consumptions per minute sustained; 5,000+ concurrent external interactions; 1,000 Registry queries per second. Scaling is horizontal by partitioning on tenant and capability domain.

Under load, non-critical consumptions are shed before critical business operations. Emergency and Panic consumptions are never dropped.

### 20.13 Dependency Relationships

Layer 4. The Registry depends on the Trust Plane, Event Bus, and Layer 0. The Gateway depends additionally on the Decision Gateway, Cost Manager, and the Registry. The LLM Router depends on the Integration Gateway, Cost Manager, Memory Gateway, and Trust Plane.

Depended upon by the Tool Gateway at Layer 4 (reciprocal, resolved by construction order: Integration Registry and Gateway precede Tool Gateway), and by the Agent Runtime at Layer 5 for all inference.

### 20.14 Architectural Constraints

- No consumption without prior registration and validation (`17` rule 1).
- No activation without a human-approved decision at the required I-class (`17` rule 2).
- No capability outside the declared abstraction (`17` rule 3).
- No data beyond declared classification limits or residency requirements (`17` rule 4).
- No direct secret handling (`17` rule 5).
- No self-escalation of permissions, risk tier, or scope (`17` rule 6).
- No anonymous registration (`17` rule 7).
- No bypass of the Gateway for consumer-to-provider interaction (`17` rule 11).
- No integration-to-integration interaction (`17` rule 17).
- No organizational data stored exclusively externally without extraction guarantees (`17` rule 18).
- No provider-specific logic preventing substitution (`17` rule 20).
- No constitutional artifact names a specific provider (`17` rule 21).
- The integration does not define compensation; the tool does (`17.20.4`).
- All inference flows through the LLM Router; no direct provider calls (`03` rule 11).

### 20.15 Guarantees

1. **Sovereignty preservation.** No external system acquires constitutional authority, governance rights, or decision-making power.
2. **Provider neutrality.** Every external capability is representable by multiple providers; tools bind to abstractions.
3. **Contractual governance.** Every relationship is governed by a validated contract with declared exit terms.
4. **Failure isolation.** External degradation or compromise does not propagate into constitutional boundaries or tool execution integrity.
5. **Portability.** Migration to an alternative provider requires no tool rewrite and loses no data sovereignty.
6. **Economic control.** External spend is budget-checked, attributed, and circuit-breaker bounded.
7. **Local-first survivability.** Core operation continues with all external integrations disabled.
8. **Attribution completeness.** Every external interaction traces to integration, decision, tool, workflow, business, and human authority.

### 20.16 Interaction with the Constitution

The platform realizes `17` in full and the component responsibility of `02.3.8`. The Registry realizes `17.6.1`. The Gateway realizes `17.6.2`. The Abstraction Layer realizes `17.6.3` and is the mechanism behind `17.23` portability. Trust scoring realizes `17.15`. The contract realizes `17.16`. Risk tiering realizes `17.5.1`. The LLM Router realizes `02.3.8` and the prompt pipeline of `02.8.5`.

The separation of Router from Gateway realizes the distinction `20C` draws: the Router is internal and consumes abstractions; the Gateway is the sovereign boundary and governs the relationships that fulfil them.

**Construction remains blocked by CIR-001.**

---

## 21. Learning Gateway

### 21.1 Purpose

The Learning Gateway transforms organizational outcomes into validated, attributable, propagated improvement. It realizes `13_LEARNING_OPERATING_MODEL`.

`13.2.1` states its defining property: **"Learning is the only subsystem whose output is change to the other subsystems."** Memory asks what happened; Knowledge asks what is true; Decision asks what shall be done; Tool asks how to act; Learning asks how to become better at all of these.

`13.2.3` states its boundary: "Knowledge Gateway owns validation; Learning Gateway owns proposal. Learning feeds the Knowledge pipeline; it does not bypass it."

### 21.2 Architectural Responsibilities

- Observe outcomes across decision journals, memory episodes, knowledge changes, tool execution records, human feedback, and the event stream.
- Extract evidence with scope and attribution preserved.
- Recognize patterns without generalizing beyond observed scope.
- Form hypotheses with explicit target subsystem, evidence, and expected outcome.
- Validate across evidence quality, attribution strength, scope conformance, and contradiction.
- Consolidate hypotheses into coherent, non-contradictory proposals.
- Propagate proposals to target subsystem Gateways — handoff only, never adoption.
- Measure adopted improvements to confirmation or refutation within declared windows.
- Decay confirmed learning as conditions change.
- Enforce bounded self-modification absolutely.

### 21.3 Internal Components

| Component | Responsibility |
|---|---|
| **Observation Trigger** | Consumes lifecycle events, scheduled reviews, and human feedback as observation triggers |
| **Extraction Engine** | Retrieves scoped, attribution-preserving evidence from Memory, Decision, Knowledge, and Tool records |
| **Pattern Recognizer** | Identifies recurring structures, anomalies, correlations; enforces minimum observation counts |
| **Attribution Engine** | Assesses causal proximity, confounding control, temporal order, replication |
| **Hypothesis Former** | Constructs candidate improvements with target subsystem and expected outcome |
| **Validation Engine** | Four-dimension validation; assigns authoritative confidence |
| **Consolidation Engine** | Resolves contradiction, merges overlap, packages proposals; enforces depth caps |
| **Propagation Router** | Delivers validated proposals to target subsystem Gateways |
| **Adoption Tracker** | Records adoption or rejection; initiates measurement |
| **Measurement Engine** | Tracks outcomes within declared windows to Confirmed or Refuted |
| **Reversal Proposer** | Emits reversal proposals for refuted entries |
| **Decay Engine** | Domain-dependent freshness decay and deprecation of stale entries |
| **Prioritization Engine** | Ranks by impact, risk reduction, replication value, evidence strength, adoption cost |
| **Recursion Guard** | Detects and blocks entries targeting the Learning subsystem; alerts human immediately |
| **Learning Journal** | Kernel-supplied; immutable, seven-year retention |

### 21.4 Internal Architecture

The Gateway is a closed loop with a hard outer boundary.

**The loop.** `13.18.1` specifies it: **Observe → Propose → Adopt → Measure → Confirm/Refute → Consolidate.** No adopted improvement escapes measurement; `13` rule 9 forbids adoption without outcome measurement, and `13` rule 16 forbids leaving a feedback loop unclosed beyond its declared window.

**Propagation is handoff, not adoption.** `13.16.1` is unambiguous: "The target subsystem retains full constitutional authority to reject, modify, or escalate the proposal." The Propagation Router delivers to the target Gateway and relinquishes control. Rejection transitions the entry to Abandoned with justification logged; it does not invalidate the evidence.

**Attribution is the subsystem's hardest problem and its principal risk.** `13.12.3` mandates safeguards: minimum observation counts, mandatory null-hypothesis consideration, and escalation of high-impact attributions to human review. Evidence sufficiency is graded by target class — three observations for Agent and Tool learning, two complete workflow executions for Workflow learning, five decision outcomes for Decision learning, comprehensive basis with human review for Business and Portfolio.

**Asymmetric processing is structural.** `13.34.3`: "failure patterns require fewer confirming instances but stronger root cause attribution. Success patterns require more confirming instances but permit broader generalization." Failure learning is prioritized over success learning when capital is at risk. The Pattern Recognizer therefore applies different thresholds by pattern type — two confirming instances with root cause for failure patterns, three for success patterns, and explicit non-causal labelling for correlation patterns.

**The Recursion Guard is a first-class component.** `13.21.3` classifies a learning entry targeting the Learning subsystem itself as a **Recursion Anomaly** requiring "immediate human alert and suspension." `13` rule 17 additionally forbids recursive triggering of learning cycles without explicit human authorization. This is the subsystem's self-modification containment, and it is enforced structurally rather than by policy.

**Human feedback bypasses automated gates but not audit.** `13.33.1` treats human feedback as high-confidence evidence that "bypasses certain automated validation gates while retaining full audit," and `13.7.5` states it "is never overridden by autonomous observation."

### 21.5 Public Interfaces

| Interface | Consumers | Purpose |
|---|---|---|
| Observation Submission | Agents, review workflows, governance subsystems, Human Interface | Submit an outcome for learning analysis |
| Human Feedback Entry | Human Interface | Submit high-confidence human learning evidence |
| Proposal Delivery | Memory, Knowledge, Decision, Tool, Agent, Workflow, Governance Gateways | Deliver a validated, consolidated proposal for adoption consideration |
| Adoption Report | Target Gateways | Report adoption or rejection with justification |
| Learning Journal Query | Governance, Observability, Evolution, Human Interface | Forensic reconstruction; evidence for evolutionary artifacts |
| Failure Library Query | Agent Runtime, Workflow Engine, Decision Gateway | Consult catalogued failures before similar operations |
| Learning Health | Observability Gateway | Velocity, quality, governance, health, economic metrics |

### 21.6 Consumed Interfaces

| Provider | Consumed for |
|---|---|
| Security Gateway | Observer authentication, scope and propagation boundary enforcement |
| Decision Gateway | Decision journals as canonical expected-versus-actual outcome record |
| Memory Gateway | Episodic and durable memory for pattern extraction |
| Knowledge Gateway | Deprecations, contradictions, confidence adjustments as signals of evolving belief |
| Tool Gateway | Invocation records, failure classifications, cost overruns, trust movements |
| Integration Gateway | Consumption records and provider behaviour evidence |
| Cost Manager | Learning cycle budget checks and cost attribution |
| Event Bus | Observation triggers; learning lifecycle emission |
| Observability Gateway | Baseline metrics and outcome validation data |

### 21.7 Data Ownership

The Learning Gateway owns exclusively: learning entries, patterns, hypotheses, consolidation packages, the Failure Library, measurement windows and their state, attribution records, decay state, and the Learning Journal. It occupies Structured, Semantic, and Cold tiers.

It owns no memory, no knowledge, no decision record, and no target-subsystem state. It proposes changes to things it does not own — the defining characteristic of a meta-layer.

### 21.8 State Management

| State | Class | Recovery |
|---|---|---|
| Validated learning entries | Durable-Committed | Immutable in identity, evidence, attribution |
| Hypotheses | Durable-Progressive | Recoverable; may be Abandoned or Quarantined |
| Measurement windows | Durable-Progressive | Must survive multi-quarter windows for Business and Portfolio learning |
| Adoption records | Durable-Committed | Immutable once recorded |
| Actual improvement | Durable-Committed | Nullable until measured; immutable once recorded |
| Failure Library | Durable-Mutable | Appended; entries not rewritten |
| Confidence and freshness | Durable-Mutable | Decayed continuously; history retained |

Measurement windows extending to one to three business cycles for Portfolio learning are the longest-lived progressive state in the system and must survive service restarts, version changes, and staff transitions.

### 21.9 Failure Domains

| Failure | Classification | Response |
|---|---|---|
| Evidence insufficient | Degradable | Abandoned or quarantined; evidence retained |
| Attribution anomaly | Critical | Quarantine; human review |
| Contradiction with existing learning | Degradable | Quarantine; consolidation or human arbitration |
| Confidence below target-class threshold | Degradable | Quarantined or abandoned |
| Target rejects proposal | Contained | Abandoned with justification; evidence preserved |
| Measurement refutes expectation | Operational | Reversal proposal emitted to target subsystem |
| **Recursion anomaly** | Security-adjacent, Category 1 | Immediate human alert and suspension |
| Scope expansion beyond history | Operational | Escalation to portfolio steward |
| Confidence inflation pattern | Operational | Audit; potential recalibration |
| Circuit breaker breach | Financial | Learning cycle deferred |
| Gateway unavailable | Degradable | Operational subsystems continue; learning cycles pause; no workflow fails |

### 21.10 Security Considerations

Every producer and consumer authenticates. Anonymous formation and propagation are prohibited.

Learning journals are tamper-evident, with proposals cryptographically bound to their evidence and observer identity. Bulk export requires Class D authority.

The subsystem's distinctive security concern is **authority escalation by proposal**. `13` rule 15 forbids any learning proposal from escalating the autonomy level of any agent or subsystem without human approval, and `13` rule 3 forbids any entry from modifying constitutional constraints, security boundaries, or human approval gates. The Validation Engine screens every proposal against these prohibitions before it can reach consolidation — a proposal that would touch a non-violable rule is rejected at validation, not at the target Gateway.

Cross-tenant learning requires explicit anonymization and human approval.

### 21.11 Observability Requirements

The Gateway emits five metric families per `13.23.1`: **Velocity** (observations, hypotheses, validations, adoptions per period), **Quality** (confirmation rate, refutation rate, attribution error rate), **Governance** (escalation rate, propagation latency, adoption rate), **Health** (backlog depth, circuit breaker proximity, anomaly count), and **Economic** (cost per cycle, budget utilization, return estimation).

Attribution error rate is the subsystem's most consequential signal. `13.4.3` and the glossary define Attribution Error as "an incorrect correlation between cause and outcome, leading to harmful proposals" — the mechanism by which a learning subsystem degrades the system it exists to improve.

### 21.12 Performance Characteristics

| Operation | p50 | p99 | Maximum | Source |
|---|---|---|---|---|
| Observation to extraction | 1s | 5s | 30s | `13.25.1` |
| Hypothesis validation | 2s | 10s | 60s | `13.25.1` |
| Consolidation | 5s | 30s | 120s | `13.25.1` |
| Propagation packaging | 1s | 5s | 30s | `13.25.1` |
| Measurement cycle initiation | 100ms | 500ms | 2s | `13.25.1` |

Throughput: 1,000 observations per second; 100 validations per second; 50 propagations per minute. Scaling is horizontal by partitioning on tenant and target subsystem.

The three-order-of-magnitude drop from observation to propagation is deliberate and constitutional: the subsystem observes broadly and proposes narrowly.

### 21.13 Dependency Relationships

Layer 6. Depends downward on Layer 0 through Layer 5, the Trust Plane, the Economic Plane, and the Oversight Plane.

Depended upon by the Evolution Gateway at Layer 6 — a directional intra-layer dependency, since `19.7.2` requires confirmed learning entries as evidence for evolutionary artifacts.

### 21.14 Architectural Constraints

- No formation without authenticated observer and complete evidence citation (`13` rule 1).
- No bypass of the target subsystem's Gateway or approval mechanism (`13` rule 2).
- No modification of constitutional constraints, security boundaries, or human approval gates (`13` rule 3).
- No entry targeting the Learning subsystem without Class D human authority (`13` rule 4).
- No propagation below the confidence threshold for the target class (`13` rule 5).
- No presentation of correlation as causation (`13` rule 6).
- No adoption without outcome measurement (`13` rule 9).
- No modification after validation (`13` rule 10).
- No override of a human sovereign decision or standing order (`13` rule 12).
- No formation from quarantined memory, unvalidated knowledge, or speculation as sole evidence (`13` rule 14).
- No autonomy escalation without human approval (`13` rule 15).
- No unclosed feedback loop beyond its window (`13` rule 16).
- No recursive cycle triggering without human authorization (`13` rule 17).

### 21.15 Guarantees

1. **Attribution integrity.** Every proposal traces to specific evidence and specific outcomes.
2. **Validation before propagation.** No improvement is adopted without passing the target subsystem's own governance.
3. **Bounded self-modification.** Learning may improve operational subsystems and never constitutional constraints.
4. **Asymmetric improvement.** Failure prevention is prioritized over success replication when capital is at risk.
5. **Feedback loop closure.** Every adoption is measured to Confirmed or Refuted.
6. **Recursion containment.** Self-targeting entries are detected, blocked, and escalated.
7. **Economic bounding.** Learning cost does not exceed the value it produces or breach circuit breakers.

### 21.16 Interaction with the Constitution

The Gateway realizes `13` in full. The meta-layer topology realizes `13.6.1`. The closed loop realizes `13.18.1`. Attribution safeguards realize `13.12.3`. Asymmetric processing realizes `13.34.3`. The Recursion Guard realizes `13.21.3` and `13` rules 4 and 17. Bounded self-modification realizes `13.3.2` objective 4 and `13.35.2`.

Its position as the only subsystem whose output is change to other subsystems is why every propagation is a handoff and never an adoption, and why the Evolution Gateway — not Learning — carries structural change beyond operational bounds.

---

## 22. Security Gateway

### 22.1 Purpose

The Security Gateway is the trust substrate upon which every other subsystem rests. It realizes `14_SECURITY_OPERATING_MODEL`.

`14.2.1` rejects the perimeter framing: "Security is not a defensive perimeter. It is the trust substrate upon which every other subsystem rests." `14.2.6` states its distinctive constitutional role: **"Security is the only subsystem whose primary output is the preservation of constraints across all other subsystems."**

`14.6.1` establishes its authority: it is "the sole source of truth for 'who may act' and 'within what boundaries.'"

### 22.2 Architectural Responsibilities

- Maintain the Identity Registry across five principal categories.
- Authenticate every principal at the boundary of every action.
- Issue, validate, rotate, and revoke short-lived scoped tokens.
- Compute and maintain permission graphs from capabilities, roles, delegations, standing orders, and workspace grants.
- Render authorization decisions at the point of action.
- Enforce capability boundaries, least privilege, and separation of duties.
- Manage delegation chains and their validation.
- Execute cascading revocation and verify its propagation.
- Enforce tenant, workspace, business, and portfolio isolation.
- Govern the complete secret and credential lifecycle.
- Create, propagate, and validate security context.
- Enforce non-violable rules at the point of action as the final line of defence.

### 22.3 Internal Components

| Component | Responsibility |
|---|---|
| **Identity Registry** | Durable store of principal identity, type, version, tenant, status, lineage across Agent, Human, Service, Workflow, Gateway categories |
| **Registration Controller** | Identity registration with human approval for agents and services; Auditor verification for humans |
| **Authentication Engine** | Token issuance, validation, rotation; credential verification |
| **Token Service** | Scoped claim assembly; one-hour maximum TTL; automatic rotation |
| **Permission Graph Engine** | Computes effective permissions as the intersection of capabilities, roles, delegations, standing orders, workspace grants |
| **Authorization Engine** | Eight-step decision flow producing Allow, Deny, or Escalate |
| **Authorization Cache** | Bounded caching within token TTL; validated against the revocation list |
| **Capability Enforcer** | Validates requested actions against registered capability signatures |
| **Role Controller** | Role assignment, type constraint validation, expiry, conflict detection |
| **Delegation Manager** | Delegation creation, chain validation, scope intersection, expiry |
| **Revocation Engine** | Cascading revocation with atomic bounded-window execution and propagation verification |
| **Isolation Enforcer** | Tenant, workspace, business, portfolio boundary enforcement |
| **Secret Governor** | Secret lifecycle: creation, registration, injection authorization, rotation, retirement, archival |
| **Credential Governor** | Credential lifecycle: issuance, binding, rotation, revocation, archival |
| **Security Context Factory** | Context creation, propagation contract, validation, drop prohibition |
| **Constitutional Enforcer** | Point-of-action enforcement of non-violable rules across all subsystems |
| **Incident Classifier** | Six-category security incident taxonomy and automatic response triggering |
| **Security Event Journal** | Kernel-supplied; append-only, tamper-evident, seven-year Sovereign-class retention |

### 22.4 Internal Architecture

The Gateway is organized around a strict separation between **identity**, which is durable and slow-changing, and **authorization**, which is computed and fast.

**Identity is registered, versioned, and long-lived.** The Identity Registry persists independently of any session. A principal that is Suspended, Retired, or Archived exists entirely within the registry. Version lineage prevents mid-flight identity changes from corrupting active authorization chains — the same discipline the Agent Runtime applies to agent versions.

**Authorization is computed at the point of action, not at token issuance.** Tokens carry claims derived from the permission graph at issuance time, but `14.9.5` is explicit that "re-authentication does not imply re-authorization; authorization is checked independently on every action." The Authorization Engine consults the live permission graph, not the token's snapshot.

**Permissions intersect; they never union.** `14.12.4` is the single most consequential rule in the subsystem: "When multiple permission sources apply to a principal, the effective permission is the intersection, not the union, of all sources." This prevents standing orders from expanding beyond role boundaries and roles from expanding beyond capability signatures. The Permission Graph Engine computes intersections before any authorization decision is rendered.

**Delegation chains validate end to end.** `14.7.4`: if A delegates to B and B to C, C's effective permissions are "the intersection of all three principals' scopes, not the union." Any broken or revoked link invalidates downstream authority. The Delegation Manager validates the entire chain at the point of action, not at delegation time.

**Caching is permitted and bounded.** `14.10.4` expressly permits consuming subsystems to cache authorization decisions for bounded time not exceeding token expiry, validated against a revocation list that the Gateway broadcasts. This provision is the primary mitigation available for CIR-004, and the Authorization Cache implements it as a first-class component rather than an optimization.

**Cascading revocation is atomic or it is a failure.** `14.15.3` requires revocation to cascade to active tokens, pending tasks, child tasks, issued delegations, and cached permission graphs within a bounded window, and states that "partial revocation is treated as a system failure and alerted."

**The Constitutional Enforcer is the system's last line.** `14.33.1` places enforcement of the non-violable rules of Agent, Decision, and Learning at this Gateway "at the point of action," and `14.33.2` enumerates twenty enforcement mechanisms. `14.33.3` states the response: immediate blocking, principal suspension, evidence preservation, human sovereign alert, and Category 1 escalation, with "no appeal possible at the agent level."

**[Implementation Decision] Permission graph precomputation with invalidation.** Permission graphs are precomputed on change to their inputs rather than derived per authorization request. Rationale: the Tool Gateway's p50 20ms authorization budget cannot accommodate graph derivation per request. Invalidation is triggered by capability change, role assignment, delegation creation or expiry, standing order change, and workspace grant change. This is a performance strategy; the intersection semantics are unaffected.

### 22.5 Public Interfaces

| Interface | Consumers | Purpose |
|---|---|---|
| Authentication | All modules | Verify identity claim; issue scoped token |
| Authorization | All modules | Render Allow, Deny, or Escalate for an action on a resource |
| Identity Registration | Human Interface, Agent Runtime, Governance Gateway | Register a principal following approval |
| Delegation Management | Human Interface, Decision Gateway | Create, validate, or revoke a delegation |
| Revocation Command | Human Interface, Governance Gateway, anomaly detectors | Revoke permissions, roles, delegations, or credentials |
| Secret Reference Resolution | Tool Executor | Authorize and inject a secret value into a sandbox |
| Security Context | All modules | Create and validate propagated context |
| Security Event Journal Query | Governance Gateway, Human Interface (Auditor role) | Forensic reconstruction |
| Security Health | Observability Gateway | Authentication, authorization, delegation, boundary, token, and secret metrics |

### 22.6 Consumed Interfaces

| Provider | Consumed for |
|---|---|
| Event Bus | Security event emission; anomaly and lifecycle event consumption |
| Observability Gateway | Mandatory signal emission |
| Governance Gateway | Policy definitions bearing on permission and isolation |

The Gateway consumes almost nothing, by construction. As the deepest dependency in the system it is built first and must be operable before the Event Bus exists. `14.26.1` permits its journal to be written directly to persistence, making event emission a downstream obligation rather than a prerequisite.

### 22.7 Data Ownership

The Security Gateway owns exclusively: the Identity Registry, permission graphs and their history, role assignments, delegations and chains, revocation lists, credential metadata, secret metadata and references, security contexts, incident records, and the Security Event Journal. It occupies Structured, Working, and Cold tiers, mapped to `aos_core` per `02.7.1`.

It owns **secret metadata and references, never secret values in a form any consumer can retrieve.** Values exist only in the secret store and are injected into sandboxes at invocation time.

### 22.8 State Management

| State | Class | Recovery |
|---|---|---|
| Principal identities | Durable-Mutable | Registry store; lineage preserved |
| Permission graphs | Durable-Mutable | Recomputed from inputs; historical graphs archived in the journal |
| Delegations | Durable-Progressive | Expiry enforced; revocation immediate |
| Revocation list | Durable-Progressive | Broadcast to caches; propagation verified |
| Tokens | Ephemeral-Recoverable | One-hour maximum; reissued on expiry |
| Security contexts | Ephemeral, non-droppable | Immutable for one action; loss halts the action |
| Secret and credential values | Durable, never exposed | Rotated atomically; new registered before old retired |
| Security Event Journal | Durable-Committed | Append-only, tamper-evident, seven years, Sovereign-class |

`14.12.5` requires historical permission graphs to be preserved in the audit journal, enabling reconstruction of what a principal was permitted to do at any past moment.

### 22.9 Failure Domains

| Failure | Classification | Response |
|---|---|---|
| Authentication failure | Operational or Breach | Reject; on pattern, revoke credentials and suspend principal |
| Authorization denial | Operational | Blocked and logged; on repeat, suspend principal |
| Isolation breach attempt | **Isolation Breach** | Block; alert human; investigate scope |
| Secret value exposure | **Secret Exposure** | Immediately revoke secret, rotate credentials, isolate affected systems, alert human |
| Constitutional violation | **Constitutional Violation** | Immediate suspension, evidence preservation, Category 1 escalation to human sovereign |
| Delegation chain break | Critical to the operation | Authorization invalidated |
| Permission graph corruption | Critical | Revalidation; human alert |
| Partial cascading revocation | Critical, system failure | Alerted as system failure per `14.15.3` |
| Gateway unavailable | Degradable then Critical | Previously authorized actions continue for a bounded grace period using cached assertions; new non-trivial actions pause; security-critical actions halt |
| Token validation failure | Contained | Rejected without affecting other principals |

`14.29.1` defines a six-category incident taxonomy distinct from the Kernel's five-category failure taxonomy. Both apply: the Kernel classifies failures; this taxonomy classifies security incidents.

### 22.10 Security Considerations

The subsystem's security considerations are its subject matter. Three properties deserve emphasis as construction constraints.

**The Gateway cannot authorize itself.** Self-approval is prohibited by `14.17.5` and applies to the Gateway as to any principal. Changes to the Gateway's own permission model require human ratification per `14.34.2`.

**The Gateway holds the only path to secret values, and consumers never traverse it.** The Secret Governor authorizes the Tool Executor to inject; it does not return values to requesters. There is no interface by which any consumer retrieves a secret value.

**Human credentials are non-delegable and non-automated.** `14.23.4` prohibits any agent, service, or workflow from authenticating with a human credential. Level 4 authority is cryptographically bound to human credentials and cannot be delegated — the structural basis of human sovereignty across every subsystem.

### 22.11 Observability Requirements

The Gateway emits per `14.27.1`: authentication attempts by outcome, authorization decisions by outcome, delegation creation and revocation, permission graph changes, boundary crossing events, token issuance and expiry, and secret reference usage.

Traces follow security context from authentication through authorization to action execution and audit logging, including Gateway decision latency and permission graph query time.

Alerts trigger on authentication failure spikes, authorization denial anomalies, delegation chain breaks, permission graph corruption, boundary crossing violations, secret reference abuse, token expiry anomalies, and cascading revocation failures.

Security signals are the highest-priority emission class in the system. `14.29.2` requires automatic incident response triggering on threshold breach, which requires the Observability Gateway to receive these signals without batching delay.

### 22.12 Performance Characteristics

`14` does not publish a Performance Characteristics section with latency tables. The Gateway's budgets are therefore derived from the budgets of the subsystems that depend on it.

**[Implementation Decision] Security Gateway budgets derived from dependent subsystem budgets.** Authorization must complete well within the Tool Gateway's p50 20ms and the Integration Gateway's p50 20ms authorization budgets, since those budgets encompass a Security verification. A working target of p50 5ms / p99 20ms for cached authorization and p50 20ms / p99 80ms for cold authorization is adopted. Rationale: these are the tightest budgets in the constitution that transitively include Security verification. This is a derived engineering target, not a constitutional value, and is the primary input to the CIR-004 composite allocation.

Revocation propagation operates within "defined latency budgets" per `14.15.4` without a published figure; the propagation window is an ADR item.

### 22.13 Dependency Relationships

Trust Plane, constructed immediately above Layer 0. Depends only on `kernel`, `core`, and `persistence`.

Depended upon by every module in the system without exception. It is the first module constructed and the first initialized in the bootstrap sequence of `18.33.2`.

### 22.14 Architectural Constraints

- No principal acts without a registered, authenticated identity (`14` rule 1).
- No principal acts beyond the intersection of its six declared boundaries (`14` rule 2).
- No self-escalation of permissions, roles, or autonomy (`14` rule 3).
- No bypass of the Gateway for authentication or authorization (`14` rule 11).
- No secret value exposed to an agent, workflow, or decision journal (`14` rule 12).
- No journal modification after formation (`14` rule 13).
- No anonymous or pseudonymous action (`14` rule 14).
- No cross-tenant access without bilateral human approval (`14` rule 15).
- No cached authorization surviving beyond its maximum TTL (`14` rule 16).
- No revocation unpropagated beyond its latency budget (`14` rule 17).
- No security subsystem change without human ratification (`14` rule 19).
- Permissions intersect, never union (`14.12.4`).
- Security context may never be dropped (`14.24.5`).

### 22.15 Guarantees

1. **Identity integrity.** Every principal has a unique, immutable, non-repudiable identity.
2. **Authority enforcement.** No principal acts beyond its declared boundaries.
3. **Least privilege.** Every principal operates with minimum permissions for its current task.
4. **Isolation by default.** Tenants, businesses, workspaces, and portfolios are isolated absent explicit bilateral authorization.
5. **Secret non-exposure.** No secret value reaches any principal, log, trace, or journal.
6. **Audit immutability.** Every security event is recorded append-only, tamper-evident, for seven years.
7. **Trust revocability.** Permissions and delegations are revocable immediately with verified propagation.
8. **Constitutional boundary protection.** Non-violable rules are enforced at the point of action, not merely documented.

### 22.16 Interaction with the Constitution

The Gateway realizes `14` in full. The Identity Registry realizes `14.4` and `14.8`. Authentication realizes `14.9`. Authorization realizes `14.10`. The permission graph and intersection rule realize `14.12`. Delegation realizes `14.14`. Revocation realizes `14.15`. Isolation realizes `14.18` through `14.21`. Secret and credential governance realize `14.22` and `14.23`. Security context realizes `14.24`. The Constitutional Enforcer realizes `14.33`.

Its position as trust substrate rather than perimeter is why it is constructed first, initialized first at bootstrap, and depended upon universally — and why `14.2.6`'s claim that its primary output is the preservation of constraints across all other subsystems is realized structurally through the Constitutional Enforcer rather than through documentation.

---

## 23. Governance Gateway

### 23.1 Purpose

The Governance Gateway is the constitutional steward. It realizes `15_GOVERNANCE_OPERATING_MODEL`.

`15.2.1` states its metaphor: "Governance is the guardian of the guardrails. It does not drive the vehicle; it verifies that the vehicle remains on legitimate roads." `15.2.6` states its purpose: "Governance is the organizational immune system," existing to detect, arrest, and reverse constitutional drift before organizational legitimacy collapses.

`15.6.1` establishes its exclusive authority: **"No subsystem may self-certify its own constitutional compliance."**

### 23.2 Architectural Responsibilities

- Mediate all policy formation, constitutional interpretation, compliance assessment, conflict resolution, and audit orchestration.
- Maintain the six-layer policy hierarchy and enforce non-contradiction across it.
- Assess constitutional compliance across all subsystems continuously.
- Issue authoritative interpretations of constitutional ambiguity, graded G1 through G4.
- Ratify constitutional amendments at G4 exclusively.
- Conduct meta-oversight of other subsystems' self-governance without usurping their operational autonomy.
- Assign, monitor, and revoke stewardships; maintain accountability chains.
- Monitor and validate delegated authority for drift.
- Grant, bound, and review governance exceptions.
- Detect constitutional drift and escalate.

### 23.3 Internal Components

| Component | Responsibility |
|---|---|
| **Artifact Controller** | Governance artifact formation, identity, lifecycle, disposition |
| **Evidence Assembler** | Assembles decision journals, security events, learning entries, knowledge, memory episodes; flags gaps |
| **Assessment Engine** | Evaluates evidence against constitutional provisions and active policies; determines compliance state |
| **Interpretation Engine** | Produces authoritative resolutions of ambiguity grounded in text, precedent, and mission |
| **Ruling Formation** | Declares constitutional status with mandatory remediation or validation requirements |
| **Authority Resolver** | Determines required G-class from artifact class, scope, and constitutional impact |
| **Ratification Controller** | Routes G3 and G4 artifacts for human confirmation; enforces exclusive G4 human authority |
| **Policy Hierarchy Store** | Six-layer policy structure with constitutional lineage |
| **Contradiction Detector** | Detects lower-layer contradiction of higher-layer policy; suspends automatically |
| **Compliance Monitor** | Continuous assessment across five compliance states |
| **Drift Detector** | Systematic divergence measurement; drift velocity |
| **Stewardship Registry** | Stewardship assignments, scope, expiry, accountability chains |
| **Delegation Auditor** | Validates delegation chains against constitutional autonomy and monitors scope creep |
| **Exception Controller** | Time-bounded, scope-limited, risk-assessed exceptions with mandatory post-hoc review |
| **Review Orchestrator** | Scheduled, triggered, post-incident, and sovereign reviews with independence enforcement |
| **Audit Engine** | Systematic evidence-based examination with auditor independence enforcement |
| **Governance Journal** | Kernel-supplied; immutable, Sovereign-class where ratification-related |

### 23.4 Internal Architecture

The Gateway is organized around a hierarchy of authority and a hierarchy of policy, and the interaction between them.

**Evidence before assessment, always.** `15.12.1` requires grounding in canonical records — decision journals, security audit trails, validated learning entries, committed knowledge, tool execution records. Speculation and unvalidated observation may not serve as sole evidence for G2 and above. Critically, `15.7.2` permits evidence assembly **directly from subsystem journals**, which is what breaks the Governance–Observability cycle and permits journal-based Governance to operate before the full Observability profile exists.

**The policy hierarchy is strictly layered and non-contradictory.** Six layers from Constitutional Provisions down to Subsystem Policies. `15.16.2` requires every policy to trace authority to a constitutional provision — "A policy without constitutional lineage is illegitimate," and orphaned policies are rejected. `15.16.3` makes contradiction structurally self-correcting: a lower-layer policy contradicting a higher layer is void, and if contradiction emerges post-ratification, the lower policy is **automatically suspended** pending review.

**Interpretation clarifies; it does not amend.** `15.19.1` draws the line. Interpretations are binding on their scope but remain subordinate to the constitutional text, and are superseded if the text is later amended to resolve the ambiguity. Interpretations that would functionally alter constitutional meaning exceed interpretation authority under `15.19.2` and must proceed as amendments.

**Meta-oversight observes but does not intervene.** `15.22.3` is precise: Governance "may declare a subsystem's self-governance non-compliant; it may not directly modify subsystem internals, reassign agents, or alter decision logic. Remediation is routed through the subsystem's own governance mechanisms or human authority." The Assessment Engine produces findings; it holds no execution path into any subsystem.

**Independence is structurally enforced.** `15.25.4` prohibits a steward from reviewing their own stewardship domain; `15.27.4` prohibits any principal from auditing a scope for which they hold operational or stewardship accountability. The Review Orchestrator and Audit Engine both refuse assignments violating these constraints — enforcement by construction, not by policy.

**Timeout never ratifies.** `15.8.2` specifies that Under Review to Rejected occurs on "timeout without response (does NOT auto-ratify)," and `15.28.4` specifies that escalation timeout escalates further rather than ratifying by default. The Ratification Controller offers no timeout-ratifies path.

### 23.5 Public Interfaces

| Interface | Consumers | Purpose |
|---|---|---|
| Compliance Query | All subsystems, Human Interface | Report constitutional compliance state for a scope |
| Policy Query | All subsystems | Retrieve applicable policy by layer and scope |
| Interpretation Request | All subsystems, Human Interface, Chief Implementation Architect | Submit a constitutional ambiguity for authoritative resolution |
| Ratification Request | Evolution Gateway | Submit a packaged amendment for constitutional ratification |
| Governance Ruling | All subsystems | Deliver a binding compliance declaration with remediation requirements |
| Exception Request | All subsystems, Human Interface | Request a time-bounded, scope-limited deviation |
| Stewardship Query | Human Interface, Observability Gateway | Accountability chain and stewardship coverage |
| Audit Finding | Human Interface, Observability Gateway | Documented assessment with evidence and remediation |
| Governance Health | Observability Gateway | Constitutional health, policy vitality, legitimacy, overhead metrics |

### 23.6 Consumed Interfaces

| Provider | Consumed for |
|---|---|
| Security Gateway | Identity verification, permission enforcement, audit access |
| Decision Gateway | Decision journals, authority chains, approval gate integrity |
| Learning Gateway | Learning entries and proposal constitutional screening |
| Knowledge Gateway | Canonical beliefs for compliance assessment |
| Memory Gateway | Audit provenance and historical pattern analysis |
| Observability Gateway | Compliance scores, drift velocity, policy contradiction indicators, legitimacy trends |
| Integration Gateway | Integration compliance scores, provider concentration, portability assessments |
| Deployment Gateway | Deployment compliance scores, substrate concentration, sovereignty adherence |
| Event Bus | Drift detection and compliance review triggers; governance lifecycle emission |

### 23.7 Data Ownership

The Governance Gateway owns exclusively: governance artifacts, the policy hierarchy, rulings, interpretations, stewardship assignments, accountability chains, exceptions and their review schedules, audit findings, compliance assessments, drift measurements, ratification records, and the Governance Journal. Structured and Cold tiers.

It owns no subsystem state. It assesses what it does not own — the defining characteristic of oversight.

### 23.8 State Management

| State | Class | Recovery |
|---|---|---|
| Ratified artifacts | Durable-Committed | Immutable in identity, evidence, rationale once Ratified or Active |
| Policy hierarchy | Durable-Mutable | Versioned; supersession preserves predecessor; contradiction triggers automatic suspension |
| Interpretations | Durable-Committed | Binding; superseded if underlying text is amended |
| Stewardship assignments | Durable-Mutable | Time-bounded; revocation transfers accountability |
| Exceptions | Durable-Progressive | Automatic expiry; post-hoc review mandatory |
| Compliance state | Durable-Mutable | Continuously reassessed |
| Drift measurements | Derived | Recomputed from journals and Observability signals |
| Ratification logs | Durable-Committed | Sovereign-class; retained indefinitely |

### 23.9 Failure Domains

| Failure | Classification | Response |
|---|---|---|
| Evidence insufficient | Degradable | Reject, escalate, or permit with uncertainty rider and enhanced monitoring |
| Contradictory evidence | Critical | Halt ratification; reconciliation or escalation |
| Confidence below G-class threshold | Degradable | Automatic escalation or deferral |
| Policy contradiction detected | Critical | Lower-layer policy automatically suspended pending review |
| Orphaned policy detected | Critical | Rejected or suspended; lacks constitutional lineage |
| Drift threshold breach | Critical | Escalation to human sovereign |
| Stewardship vacuum | Operational | Successor assignment; artifacts under failed stewardship revalidated |
| Independence violation at assignment | Contained | Assignment refused |
| Ratification timeout | Operational | Escalates further; never ratifies |
| Governance overhead circuit breach | Operational | Artifacts deferred or escalated |
| Constitutional breach detected | Category 1 | Evidence preserved, artifacts suspended, delegations revoked, human sovereign validation required before resumption |

### 23.10 Security Considerations

Governance holds no operational authority and therefore presents a narrow direct attack surface. Its indirect surface is significant: an actor who could form or ratify governance artifacts could legitimize constitutional violation.

Three protections apply. **G4 authority is cryptographically bound to human credentials and cannot be delegated** (`15.33.2`). **The Gateway blocks any non-human principal from forming G4 artifacts, ratifying amendments, or invoking Sovereign Override.** **No governance artifact may contradict a non-violable rule regardless of scope or authority** (`15.6.3`) — screened at formation, before an artifact can reach review.

Transparency is scoped, not universal. `15.31.4` requires that transparency never override Security classification, tenant isolation, or secret non-exposure; artifacts referencing secrets are sanitized before exposure.

Exception logs and ratification logs are Sovereign-class, accessible only to human Operators and Auditors.

### 23.11 Observability Requirements

The Gateway emits four metric families per `15.26`: **Constitutional Health** (compliance rate, ambiguity rate, contradiction rate, drift velocity), **Policy Vitality** (policy count, policy age, supersession rate, orphan rate), **Legitimacy** (stewardship coverage, escalation latency, ratification velocity, override frequency), and **Overhead** (review latency, artifact formation rate, subsystem governance load, circuit breaker proximity).

The Overhead family is constitutionally significant and connects directly to CIR-008: `15.14.4` establishes governance circuit breakers including a maximum governance overhead ratio, and the fifteen percent improvement cap of `04.32` may or may not bound the aggregate oversight burden. The Gateway must expose its own cost to permit the question to be answered empirically.

### 23.12 Performance Characteristics

`15` publishes no latency tables. Governance operates on review cadences rather than request budgets: daily triage, weekly review, monthly retrospective, quarterly strategy, annual vision, per `04.32.2` and `05.24.1`.

Two bounds are constitutional. `15.17.6` requires G3 review of an emergency policy suspension **within 24 hours**. `15` rule 19 requires governance failures to be classified and alerted **within 60 seconds**.

**[Implementation Decision] Governance operates asynchronously and is never on a request path.** No subsystem blocks on a Governance response during operational execution. Rationale: `15.2.5` establishes that Governance holds no execution authority and `15.22.3` forbids intervention in subsystem internals; a synchronous governance dependency would contradict both and would introduce a latency source the constitution does not budget. Compliance is assessed continuously and asynchronously against journals.

### 23.13 Dependency Relationships

Oversight Plane, constructed above Layer 6. Depends on the Trust Plane, the Event Bus, all subsystem journals, and the Observability Gateway for enriched signals.

Depended upon by the Evolution Gateway for ratification — the only hard dependency any subsystem has on Governance, and directional.

Its journal-based evidence assembly under `15.7.2` is what permits construction before the full Observability profile exists.

### 23.14 Architectural Constraints

- No artifact without unique identity, authenticated steward, and documented evidence or gap flag (`15` rule 1).
- No G4 amendment ratified without explicit human sovereign approval (`15` rule 2).
- No artifact contradicting a non-violable rule (`15` rule 3).
- No reduction of human sovereignty below absolute terminal authority (`15` rule 4).
- No steward ratifies beyond their autonomy level (`15` rule 5).
- No bypass of the Gateway for direct subsystem enforcement (`15` rule 6).
- No journal modification after ratification (`15` rule 7).
- No policy without valid constitutional lineage (`15` rule 11).
- No exception without time bounds, scope limits, and post-hoc review (`15` rule 17).
- Non-violable rules are themselves unamendable (`15.20.5`).
- Meta-oversight does not modify subsystem internals (`15.22.3`).
- Reviews and audits are independent of the scope under examination (`15.25.4`, `15.27.4`).

### 23.15 Guarantees

1. **Constitutional integrity.** The constitution is interpreted consistently, enforced uniformly, and amended only through legitimate process.
2. **Policy coherence.** The hierarchy is non-contradictory, scoped, and retired when obsolete.
3. **Subsystem legitimacy.** No subsystem self-certifies its constitutional compliance.
4. **Human sovereignty preservation.** Humans retain absolute terminal authority over amendment, override, and governance itself.
5. **Delegated authority validation.** All authority chains trace to human sovereign grants and are monitored for drift.
6. **Drift arrest.** Systematic divergence is detected and escalated before it compounds.
7. **Accountability.** Every artifact, policy, and ruling traces to an accountable steward and ultimately to a human sovereign.
8. **Bounded self-governance.** Governance mechanisms are themselves constitutionally constrained and human-ratified.

### 23.16 Interaction with the Constitution

The Gateway realizes `15` in full. The G1–G4 authority spectrum realizes `15.9.1`. The policy hierarchy realizes `15.16`. Compliance assessment realizes `15.18`. Interpretation realizes `15.19` — and is the mechanism through which the Constitutional Interpretation Register of `21A` §3 is resolved. Amendment and ratification realize `15.20` and `15.21`. Meta-oversight realizes `15.22`. Stewardship realizes `15.23`. Exceptions realize `15.29`.

Its exclusive ratification authority is why the Evolution Gateway packages but does not ratify, and why `19.16.2` states that "Evolution ensures the package is complete" while Governance presents it to sovereigns.

---

## 24. Observability Gateway

*Realizes: `16_OBSERVABILITY_OPERATING_MODEL.md`*

### 24.1 Purpose

The Observability Gateway is the subsystem through which Agent OS renders itself legible to human and constitutional oversight. It does not act on the system; it perceives, correlates, and reports. `16.2` establishes observability as "the constitutional right of oversight to see," not an operational convenience — a distinction this architecture preserves by giving the Gateway no mutation path into any other subsystem.

### 24.2 Architectural Responsibilities

The Gateway ingests telemetry (metrics, logs, traces, events) emitted by every other Gateway and the Kernel's signal-emission mechanism (`21A` §5.2); correlates telemetry into coherent incident and health narratives per `16.9`; maintains the dashboards and query surfaces through which Governance, Security, and human operators observe system state (`16.11`); computes and publishes the Service Level Indicators referenced by every other subsystem's Performance Characteristics sections in this document (`16.14`); and participates in the Panic Protocol as the subsystem responsible for confirming halt completion across all Agent Runtime workers (`16.19`, `21A` §5.2).

### 24.3 Internal Components

| Component | Responsibility |
|---|---|
| Telemetry Ingest | Receives metrics/logs/traces/events from the Kernel's out-of-band emission channel (`21A` §5.2; the same channel used by the Event Bus's self-health path, §15.4 above) |
| Correlation Engine | Joins telemetry across subsystem boundaries into incident timelines (`16.9`) |
| SLI/SLO Registry | Holds the published performance targets every subsystem in this document cites in its own §12 (`16.14`) |
| Dashboard & Query Surface | Read-only interface for Governance, Security, and human operators (`16.11`) |
| Alerting & Escalation | Routes threshold breaches to the Category 1 Incident pipeline or to Governance per severity (`16.16`, `16.17`) |
| Panic Confirmation Listener | Confirms Agent Runtime halt completion within the 5-second guarantee window (`16.19`) |

### 24.4 Internal Architecture

Telemetry flows in one direction: emitting subsystem → Kernel emission channel → Telemetry Ingest → Correlation Engine → (Dashboard surface | SLI/SLO Registry | Alerting). The Gateway holds no call path back into any emitting subsystem — `16.4` states observability "reads the system; it does not steer it," which this architecture enforces structurally by giving the Gateway's public interfaces read/query semantics only (§24.5). The Correlation Engine is stateless per query and reconstructs incident timelines from the immutable Journal rather than maintaining its own mutable incident state, consistent with the append-only correction model used uniformly across Gateways (`21A` §6.2).

`[Implementation Decision]` Telemetry ingestion is buffered and asynchronous relative to the emitting subsystem's request path — no subsystem's latency budget (§12 of any section above) includes time spent waiting on Observability ingest. This is necessary because `16.4`'s "reads, does not steer" principle would be violated if a slow observability path could back-pressure an operational subsystem.

### 24.5 Public Interfaces

| Interface | Consumers | Semantics |
|---|---|---|
| Query API (metrics/logs/traces) | Governance Gateway, Security Gateway, human operators via Dashboard | Read-only |
| Incident Timeline API | Governance Gateway, Category 1 Incident pipeline | Read-only |
| SLI/SLO Publication | All subsystems (informational; not enforced by Observability) | Read-only |
| Panic Confirmation Signal | Agent Runtime, Kernel | Emits confirmation only, no control return |

### 24.6 Consumed Interfaces

Telemetry emission from every Gateway and the Agent Runtime via the Kernel's signal-emission mechanism (`21A` §5.2); Journal read access for timeline reconstruction (`21A` §6.2); Security Gateway authorization for Dashboard/Query API access, since observability data itself carries confidentiality classification per `16.13`.

### 24.7 Data Ownership

Per the Data Ownership Matrix (`21A` §10), Observability owns its own telemetry store — a high-volume, append-only tier distinct from the Journal tier used by operational Gateways, reflecting `16.10`'s requirement that observability data retention and query patterns differ materially from operational record retention. The SLI/SLO Registry is a small, low-churn Structured-tier store.

### 24.8 State Management

Telemetry records are Durable-Committed once ingested (`21A` §11); the SLI/SLO Registry entries are Durable-Mutable, updated only through Governance-visible change events per `16.14.3`; correlated incident timelines are Derived state, reconstructed on query rather than stored as first-class mutable records.

### 24.9 Failure Domains

| Failure | Containment |
|---|---|
| Telemetry Ingest unavailable | Emitting subsystems buffer locally per Kernel emission channel semantics; operational paths are unaffected per §24.4 |
| Correlation Engine failure | Dashboard serves raw telemetry without correlation; degraded but not blind |
| SLI/SLO Registry unavailable | Subsystems continue operating against last-known targets; no subsystem's operational path depends on live registry reads |
| Total Observability outage | Constitutes a Category 1 Incident in itself per `16.17`, since oversight visibility is a non-violable guarantee (`16.2`) |

### 24.10 Security Considerations

Observability data is itself sensitive — traces and logs can leak the content the Security Gateway is charged with protecting (`16.13`, `14.12`). Query API access is authorized by the Security Gateway using the same intersect-permissions rule established in §22.4 above; there is no privileged "observability bypass" of Security authorization, including for Governance's own queries.

### 24.11 Observability Requirements

The Observability Gateway's requirement to observe itself is met by routing its own internal health telemetry through the same Kernel emission channel used by every other subsystem, avoiding a special-cased self-monitoring path that could silently diverge from what operators see for the rest of the system (`16.4`).

### 24.12 Performance Characteristics

`16.14` publishes SLI/SLO categories but the source document does not tabulate specific ingest-to-visibility latency figures. `[Implementation Decision]` Target ingest-to-dashboard latency of p50 2s / p99 10s for metrics, and p50 5s / p99 30s for logs and traces, reflecting the asynchronous, non-blocking posture established in §24.4. These targets are Observability's own internal SLOs and are not inputs to any other subsystem's latency budget, since §24.4 establishes that no operational path waits on Observability.

### 24.13 Dependency Relationships

Observability depends on the Kernel's emission channel and Journal (read-only) and on Security for query authorization. Every other Gateway and the Agent Runtime depend on Observability for visibility, but none depend on it for correctness — this asymmetry is what allows Observability to fail without cascading, per §24.9.

### 24.14 Architectural Constraints

Observability may not write to, configure, or otherwise steer any subsystem it observes (`16.4`). It may not serve as a hidden control channel — the Panic Confirmation Signal (§24.5) is a report of a halt that has already occurred, not a mechanism that causes the halt.

### 24.15 Guarantees

The Observability Gateway guarantees that all telemetry it ingests is retained per `16.10`'s minimum retention requirement; that query access is uniformly authorized rather than granted by subsystem identity; and that a total loss of Observability is itself reported as a Category 1 Incident rather than passing silently.

### 24.16 Interaction with the Constitution

Observability realizes `16` in full as read. It is the consumer of every other Gateway's signal-emission mechanism (`21A` §5.2) and the publisher every other section in this document cites when referencing "published SLOs." Its constrained, read-only posture is the architectural expression of `16.2`'s framing of observability as oversight's right to see rather than a control surface.

---

## 25. Deployment Platform — Deployment Registry, Deployment Gateway

*Realizes: `18_DEPLOYMENT_OPERATING_MODEL.md`*

> **Construction blocked by CIR-001.** `18`'s deployment topology provisions — environment classes, promotion pipelines, and infrastructure targets — presuppose specific technology and provider choices in the same way `03_TECH_STACK` does, while `19` rule 22, `17` rule 21, and `18` rule 18 prohibit constitutional documents from naming specific technologies or providers. `21A` §3 (CIR-001) identifies Deployment as one of the three subsystems this ambiguity blocks. Construction of this platform does not begin until CIR-001 is resolved at G3 or G4. This section specifies the architecture; it does not authorize its construction.

### 25.1 Purpose

The Deployment Platform is the constitutional gate between a constructed artifact and a running instance of it. `18.2` frames deployment as "the last constitutional checkpoint before code becomes behavior" — every guarantee this document has specified for every other subsystem is only as real as the deployment path that puts it into production.

### 25.2 Architectural Responsibilities

The Deployment Registry governs existence: which deployable artifacts exist, their versions, and their promotion history (`18.6`, mirroring the Registry role established for Tool and Integration in §§19–20). The Deployment Gateway authorizes: it evaluates promotion requests against environment-class policy, required approvals, and rollback readiness before permitting a deployment to proceed (`18.8`, `18.12`). Neither component executes infrastructure changes directly — per `21A` §5.2's Gateway Pattern, authorization and execution are separated, with execution delegated to environment-specific infrastructure outside the scope this document specifies (blocked by CIR-001 per the banner above).

### 25.3 Internal Components

| Component | Responsibility |
|---|---|
| Deployment Registry | Artifact and version catalog, promotion history (`18.6`) |
| Environment Class Policy Store | Encodes per-environment-class requirements (approvals, testing gates, rollback readiness) (`18.9`) |
| Deployment Gateway (Authorization) | Evaluates promotion requests against policy (`18.8`) |
| Rollback Coordinator | Verifies rollback readiness pre-deployment and executes rollback on failure (`18.13`) |
| Deployment Journal | Immutable record of every promotion decision and outcome (`21A` §6.2 pattern) |

### 25.4 Internal Architecture

A promotion request flows: Registry lookup (does the artifact/version exist and is it eligible) → Environment Class Policy evaluation → required-approval check (via Decision Gateway for Class-appropriate decisions, §18 above) → Rollback Coordinator readiness verification → authorization decision → Journal write. No stage may be skipped; `18.12` states environment-class policy "cannot be satisfied retroactively." The Rollback Coordinator's readiness check occurring *before* authorization — not after failure — is the architectural expression of `18.13`'s requirement that rollback capability be confirmed prior to commitment, mirroring the Decision Gateway's Compensation Verifier pattern (§18.6 above).

### 25.5 Public Interfaces

| Interface | Consumers | Semantics |
|---|---|---|
| Promotion Request | CI/CD orchestration (outside this document's scope) | Synchronous authorization decision |
| Deployment Status Query | Observability Gateway, Governance Gateway | Read-only |
| Rollback Trigger | Governance Gateway (Category 1 Incident response), Deployment Gateway (automatic on failure) | Synchronous |

### 25.6 Consumed Interfaces

Decision Gateway for approval-gated promotions (`18.8`); Security Gateway for deployment-actor authorization; Observability Gateway for post-deployment health confirmation gating full promotion completion (`18.14`); Governance Gateway for environment-class policy ratification (`18.9`).

### 25.7 Data Ownership

Per `21A` §10, the Deployment Registry and Deployment Journal are owned exclusively by the Deployment Platform module. Environment Class Policy is Structured-tier, Governance-ratified, and read-only to the Deployment Gateway at evaluation time.

### 25.8 State Management

Artifact and version records are Durable-Committed once registered (`21A` §11). Promotion state progresses Durable-Progressive (`21A` §11) through the stages in §25.4 and terminates in a Durable-Committed outcome (deployed, rejected, or rolled back), never mutated thereafter — corrections are appended per the uniform append-only model (`21A` §6.2).

### 25.9 Failure Domains

| Failure | Containment |
|---|---|
| Registry unavailable | No new promotions authorized; already-running deployments unaffected |
| Policy Store unavailable | Promotions fail closed — `18.12`'s "cannot be satisfied retroactively" implies no default-permit path |
| Rollback Coordinator failure during readiness check | Promotion blocked; treated as policy-check failure, not bypassed |
| Post-deployment health check failure | Automatic rollback trigger per `18.14`; escalates to Category 1 Incident if rollback itself fails |

### 25.10 Security Considerations

Deployment authorization is one of the highest-consequence decisions in the system — it is the mechanism by which every other subsystem's guarantees enter production. `18.11` requires deployment-actor identity to be verified through the Security Gateway's Identity Plane (§22.2 above) with no exception for automated CI/CD identities, which must be provisioned as first-class identities rather than shared credentials.

### 25.11 Observability Requirements

Every promotion decision, its policy evaluation trail, and its outcome are emitted to Observability per `18.15`; rollback events are additionally routed as high-severity alerts per §24.9's Category 1 Incident pathway.

### 25.12 Performance Characteristics

`18` does not publish a deployment-latency table, and per the CIR-001 blocking banner above, target latencies are architecture-dependent on infrastructure choices not yet resolved. `[Implementation Decision]` This section defers performance targets entirely rather than estimating them, since — unlike Security (§22.12) or Memory (§16.12) — no other subsystem's operational budget depends on deployment latency; deployment is off the request-serving path by construction.

### 25.13 Dependency Relationships

Deployment depends on Decision, Security, Observability, and Governance as listed in §25.6. Per `21A`'s dependency graph, Deployment sits late in build order precisely because it is the mechanism that deploys everything else — it cannot be validated until the subsystems it deploys exist.

### 25.14 Architectural Constraints

Deployment may not promote an artifact for which rollback readiness cannot be confirmed (`18.13`). It may not accept a self-issued approval — approval gates route through the Decision Gateway using the same structural incapacity for auto-approval established in §18.9 above. It may not bypass Environment Class Policy for any environment class, including those designated lower-risk.

### 25.15 Guarantees

Subject to CIR-001 resolution, the Deployment Platform guarantees that no promotion proceeds without a confirmed rollback path, that environment-class policy is evaluated in full for every promotion with no retroactive satisfaction, and that every promotion decision is journaled immutably.

### 25.16 Interaction with the Constitution

Deployment realizes `18` in full as specified, subject to the CIR-001 blocking condition stated at the top of this section. It is the terminal checkpoint referenced implicitly by every Gateway's Deployment dependency in `21A`'s module register — no module in the 26-module hierarchy reaches production except through this platform.

---

## 26. Evolution Gateway

*Realizes: `19_EVOLUTION_OPERATING_MODEL.md`*

> **Construction blocked by CIR-001.** Evolution packages architectural and constitutional amendment proposals that may themselves include technology or provider changes, placing it within the same naming-prohibition ambiguity identified for Integration (§20) and Deployment (§25). `21A` §3 confirms CIR-001 blocks Evolution as the third of the three named subsystems. Construction does not begin until CIR-001 is resolved at G3 or G4. This section specifies the architecture; it does not authorize its construction. Evolution additionally cannot be validated independent of the Governance Gateway (§23) and the Learning Gateway (§21), both of which must be constructed and operating first per `21A`'s dependency graph — Evolution sits at Layer 6, the deepest and last-constructed layer.

### 26.1 Purpose

The Evolution Gateway is the subsystem through which Agent OS changes itself deliberately rather than accidentally. `19.2` distinguishes evolution from ordinary learning consolidation (§21 above): Learning adapts behavior within standing constitutional and architectural bounds, while Evolution proposes changes to those bounds themselves. `19.3` is explicit that Evolution "packages; it does not ratify" — the authority to actually change the Constitution or architecture remains exclusively with Governance and, beyond it, the sovereigns Governance answers to (`15.20`, §23.11 above).

### 26.2 Architectural Responsibilities

Evolution monitors confirmed Learning Gateway entries and Observability trend data for patterns that suggest a standing bound — not just a within-bound behavior — should change (`19.5`); drafts formal amendment or architectural-change proposals with impact analysis (`19.9`); routes proposals through the same funnel-with-widening-scrutiny posture the Decision Gateway uses for Class A/B decisions (§18.3 above), since constitutional and architectural amendments are definitionally Class A; and packages a complete proposal — including compensation and rollback framing — for Governance's exclusive ratification authority (`19.16.2`, §23.11 above).

### 26.3 Internal Components

| Component | Responsibility |
|---|---|
| Signal Monitor | Watches confirmed Learning entries and Observability trends for evolution-worthy patterns (`19.5`) |
| Proposal Drafter | Produces formal amendment/architecture-change proposals with impact analysis (`19.9`) |
| Impact Analyzer | Traces a proposal's effects across the module and dependency graph established in `21A` §7–§8 |
| Compensation Framer | Ensures every proposal carries a rollback/reversion plan before packaging (`19.13`) |
| Packaging & Handoff | Assembles the complete proposal package and hands it to Governance; holds no ratification authority itself (`19.16.2`) |
| Recursion Guard (shared pattern with Learning, §21.3) | Blocks or escalates any proposal that targets Evolution's own bounds, requiring elevated Governance review (`19.14`, mirroring `13`'s self-referential learning guard) |

### 26.4 Internal Architecture

The pipeline is: Signal Monitor detects candidate pattern → Proposal Drafter produces initial draft → Impact Analyzer traces downstream effects across the dependency graph → Compensation Framer attaches a rollback plan → Recursion Guard checks whether the proposal is self-referential (targets Evolution itself) and escalates if so → Packaging & Handoff delivers to Governance. Evolution's own decision-widening posture (§26.2) means low-confidence or high-impact proposals accumulate additional review requirements before packaging, rather than being rejected outright — `19.10` frames this as "widening scrutiny, not gatekeeping," consistent with the Decision Gateway's non-rejecting funnel model (§18.4 above).

`[Implementation Decision]` The Impact Analyzer's dependency-graph trace reuses the same 26-module dependency graph maintained for build-order purposes in `21A` §8, rather than maintaining a separate impact-modeling graph, since both serve the same underlying question: what does a change to this component affect.

### 26.5 Public Interfaces

| Interface | Consumers | Semantics |
|---|---|---|
| Proposal Package | Governance Gateway | Handoff; Evolution retains no further authority over the proposal post-handoff |
| Proposal Status Query | Learning Gateway, Observability Gateway, human operators | Read-only |

### 26.6 Consumed Interfaces

Confirmed Learning Gateway entries (`19.5`, §21.8 above — Evolution consumes only Confirmed-state entries, never Proposed or Adopted-but-unconfirmed, per the confidence-gating logic in §21.4); Observability trend and SLI data (§24.5); Decision Gateway posture for Class A treatment of proposals in transit (`19.10`); Governance Gateway for the policy hierarchy a proposal must be checked against before packaging (`19.9`, §23.4 above).

### 26.7 Data Ownership

Per `21A` §10, Evolution owns its Proposal Registry and Proposal Journal exclusively. It has read-only access to the Learning Gateway's Confirmed-entry store and to Observability's SLI/SLO Registry (§24.3); it has no write access to either.

### 26.8 State Management

Proposals progress Durable-Progressive (`21A` §11) through the pipeline stages in §26.4, terminating in a Durable-Committed handoff record. A proposal that Governance rejects or that fails ratification is not deleted or mutated — per the uniform append-only correction model (`21A` §6.2), the outcome is appended to the same proposal record, preserving the full history for any future re-proposal.

### 26.9 Failure Domains

| Failure | Containment |
|---|---|
| Signal Monitor failure | Evolution proposals stop being generated; no impact on standing system behavior, since Evolution has no operational authority (`19.3`) |
| Impact Analyzer failure | Proposal drafting halts pending analyzer recovery; no partial-analysis proposal may be packaged (`19.9`'s impact-analysis requirement is not satisfiable partially) |
| Recursion Guard failure | Fails closed — any proposal is treated as potentially self-referential and escalated rather than risking an unguarded self-amendment (`19.14`) |
| Packaging/Handoff failure | Proposal remains in Evolution's queue; Governance never sees a partial or corrupted package |

### 26.10 Security Considerations

Because Evolution proposals can reach constitutional and architectural scope, proposal drafting and packaging require the highest authorization tier the Security Gateway grants (`19.11`), and the Recursion Guard (§26.3) is itself treated as a security-relevant control — its failure mode is fail-closed per §26.9, consistent with the Constitutional Enforcer's last-line posture (§22.9 above).

### 26.11 Observability Requirements

Every stage transition in §26.4 is emitted to Observability, and Signal Monitor detections are logged even when they do not result in a drafted proposal, so that pattern-detection sensitivity can itself be audited over time (`19.5`).

### 26.12 Performance Characteristics

`19` does not publish a latency table for the evolution pipeline, and none of this document's other subsystems budget for Evolution latency — proposal drafting and packaging are explicitly slow, deliberative processes by constitutional design (`19.10`'s "widening scrutiny"), not operations on any request-serving path. `[Implementation Decision]` No latency SLO is established for Evolution beyond the general Journal write-path budget (§25.12's deferral rationale applies equally here); throughput and thoroughness are prioritized over speed, consistent with `19.10`.

### 26.13 Dependency Relationships

Evolution depends on Learning (confirmed entries only), Observability (trend data), Decision (Class A posture), and Governance (policy hierarchy and exclusive ratification). Per `21A`'s dependency graph, Evolution is the deepest and last-constructed subsystem, since it is meaningless without a mature Learning Gateway to source signals from and a functioning Governance Gateway to ratify its output.

### 26.14 Architectural Constraints

Evolution may not ratify its own proposals (`19.16.2`) and may not bypass the Recursion Guard for self-referential proposals under any circumstance (`19.14`). It may not consume unconfirmed Learning entries (§26.6), preventing evolution proposals from being drafted on the basis of provisional or unvalidated learning.

### 26.15 Guarantees

Subject to CIR-001 resolution, the Evolution Gateway guarantees that no proposal reaches Governance without a complete impact analysis and compensation framing; that self-referential proposals always receive elevated review; and that rejected or failed proposals are preserved in full history rather than discarded.

### 26.16 Interaction with the Constitution

Evolution realizes `19` in full as specified, subject to the CIR-001 blocking condition and its dependency on Governance and Learning stated at the top of this section. Its "packages, does not ratify" posture (`19.16.2`) is the architectural mirror of Governance's exclusive ratification authority (`15.20`, §23.11), and together the two subsystems complete the constitutional amendment loop this document has traced from Learning (§21) through Evolution to Governance.

---

## Closure of Part B

This document has specified the implementation architecture of all fourteen constitutional subsystems named in the Table of Contents — Sections 13 through 26 — each to the full sixteen-block template, each traced to its constitutional source, and each consistent with the foundations ratified in `21A`. Three sections (Integration, Deployment, Evolution) carry explicit CIR-001 blocking notices and specify architecture without authorizing construction. All `[Implementation Decision]` markers throughout identify choices this document has made beyond what the Constitution and the approved Planning Package compel.

Part III is complete. Per the approved scope for this document, Parts IV and V are not included here.
