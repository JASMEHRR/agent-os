# 21C_IMPLEMENTATION_ARCHITECTURE_DELIVERY.md

**Agent OS — Implementation Architecture, Part C: Cross-Cutting Engineering Architecture & Engineering Delivery**
**Version:** 1.0.0
**Status:** Ratified for Implementation
**Classification:** Implementation Specification — Binding on All Construction Work
**Subordinate To:** `01`–`19` (Constitution), `20A`–`20C` (Manifests), `21A` (Foundations & Structure), `21B` (Core Subsystem Architecture)

---

## Preliminary Note on This Document

This document completes the Implementation Architecture of Agent OS. It presumes and does not restate `21A`'s foundations (Gateway Pattern, Constitutional Kernel, Layer/Plane model, communication model, data ownership, state management, configuration architecture) or `21B`'s fourteen subsystem specifications. Where this document references a subsystem mechanism established in `21B`, it cites the section rather than reproducing it.

**This document is cross-cutting, not subsystem-specific.** Part IV (§27–34) specifies engineering patterns and concerns that apply uniformly across every module in the 26-module hierarchy (`21A` §7). Part V (§35–40) specifies how construction proceeds and how conformance is verified.

**Implementation decisions are marked** using the same `[Implementation Decision]` convention established in `21A` and `21B`. **CIR-001 blocking applies transitively**: any cross-cutting concern touching Integration, Deployment, or Evolution inherits that section's blocked status where noted.

---

## Table of Contents

**Part IV — Cross-Cutting Engineering Architecture**

27. Cross-Cutting Implementation Patterns
28. Security & Trust Enforcement Across All Modules
29. Inter-Module Communication Standards
30. Configuration, Feature Flags & Runtime Policy Management
31. Error Handling, Fault Isolation & Recovery Strategy
32. Scalability, Performance & Capacity Architecture
33. Disaster Recovery, Backup & Business Continuity
34. Observability, Monitoring & Operational Excellence

**Part V — Engineering Delivery**

35. Repository Build Order
36. Incremental Implementation Roadmap
37. Engineering Standards, Conformance Gates & Quality Assurance
38. Testing Architecture
39. Definition of Done
40. Implementation Appendices

---

# Part IV — Cross-Cutting Engineering Architecture

## 27. Cross-Cutting Implementation Patterns

### 27.1 Purpose

This section catalogs the implementation patterns that recur across every module in the 26-module hierarchy, consolidating what `21B` demonstrated repeatedly (Registry/Gateway/Executor separation, append-only correction, funnel-with-widening-scrutiny, fail-closed defaults) into a single normative reference so that construction teams working on different modules converge on identical solutions to identical problems.

### 27.2 Scope

Applies to every module registered in `21A` §7, including the four shared libraries. Does not apply within a module's domain-specific logic, which remains governed by that module's `21B` section.

### 27.3 Architectural Responsibilities

This section is responsible for naming and normatively fixing: the Registry/Gateway/Executor separation pattern (`21B` §19, §20, §25); the append-only correction model (`21A` §6.2, used uniformly in every Gateway's State Management block); the funnel-with-widening-scrutiny pattern (`21B` §18.4, §26.4); the fail-closed default (`21B` §25.9, §26.9); and the Recursion Guard pattern (`21B` §21.3, §26.3).

### 27.4 Design Principles

Each pattern above is implemented once, as a shared library component (`21A` §7's four shared libraries), and consumed by reference rather than reimplemented per module. `[Implementation Decision]` The append-only correction model is implemented as a single shared Journal-write library function that every Gateway's persistence layer calls, rather than fourteen independent implementations, so that the append-only guarantee is enforced at one code boundary rather than by convention across fourteen teams.

### 27.5 Engineering Constraints

No module may implement a mutating write path against a Durable-Committed record (`21A` §11) through any route other than the shared append-only library. No module may implement its own Recursion Guard logic independent of the shared pattern established in `21B` §21.3 — Learning and Evolution's guards must use the same detection mechanism, differing only in configured scope.

### 27.6 Implementation Requirements

A module claiming conformance to a cross-cutting pattern must consume the shared library implementation, not a local reimplementation. Deviations require an `[Implementation Decision]` note in that module's own documentation and Governance visibility per `21B` §23.

### 27.7 Interactions With Other Components

Every Gateway specified in `21B` §16–§26 depends on this section's patterns for its State Management (§X.8) and Failure Domains (§X.9) blocks. The Constitutional Kernel (`21A` §6) is the architectural anchor point; this section is the engineering elaboration of how Kernel-provided capabilities are actually consumed in code.

### 27.8 Dependencies

Depends on the Constitutional Kernel (`21A` §6.2) for the ten shared capabilities these patterns build on. Depended on by all 26 modules.

### 27.9 Failure Considerations

A defect in a shared pattern implementation is a defect in every module that consumes it — this is the trade-off `[Implementation Decision]` in §27.4 accepts deliberately, in exchange for the guarantee that the pattern behaves identically everywhere. Shared library changes therefore require full regression testing across all consuming modules (§38).

### 27.10 Operational Considerations

Shared library versioning follows the same 7-level configuration precedence discipline established in `21A` §12; a shared library upgrade is itself a Class B or higher decision routed through the Decision Gateway (`21B` §18) when it affects a module handling Durable-Committed state.

### 27.11 Constitutional Traceability

This section introduces no new constitutional responsibility. It is a pure engineering consolidation of patterns already present, individually, in `21A` §6 and throughout `21B`.

### 27.12 Architectural Guarantees

Every module's use of the append-only correction model, funnel-with-widening-scrutiny, fail-closed defaults, and Recursion Guard is guaranteed to trace to exactly one shared implementation, eliminating drift between modules that would otherwise implement "the same" pattern subtly differently.

---

## 28. Security & Trust Enforcement Across All Modules

### 28.1 Purpose

Specifies how the Security Gateway's authorization model (`21B` §22) is engineered to apply uniformly across all 26 modules, so that no module can implement an ad hoc or bypassed authorization path.

### 28.2 Scope

Applies to every inbound call across every module boundary defined in the Communication Model (`21A` §9), including the three permitted modes (Gateway Mediation, Event Emission, API Gateway Ingress).

### 28.3 Architectural Responsibilities

Enforces that every one of the 14 consolidated prohibited edges (`21A` §9) is structurally unrepresentable in the module dependency graph, not merely policy-forbidden. Enforces that the "permissions intersect, never union" rule (`21B` §22.4, citing `14.12.4`) is implemented as a single authorization-evaluation function shared by every module's request-handling path.

### 28.4 Design Principles

Authorization checks occur at module ingress, not internally — a module never trusts a caller's self-declared identity or permission set; it always re-resolves authorization against the Security Gateway's computed Authorization (`21B` §22.2). `[Implementation Decision]` Every module's ingress layer is generated from a shared interface-contract template that wires authorization checking automatically, so individual module authors cannot omit it.

### 28.5 Engineering Constraints

No module may cache an authorization decision beyond the bound specified by the Security Gateway's own cache-invalidation contract (`21B` §22.12's cited cached/cold targets). Cascading revocation (`21B` §22.7) must propagate to every module's authorization cache atomically or the revocation is treated as failed, per the same section's framing of atomicity as mandatory.

### 28.6 Implementation Requirements

Every module's ingress code must call the shared authorization-evaluation function from §28.3 before executing any handler logic. Modules handling Durable-Committed or Durable-Mutable state (`21A` §11) must additionally verify authorization freshness against the Security Gateway's revocation stream before committing a write.

### 28.7 Interactions With Other Components

Directly extends `21B` §22 (Security Gateway) and `21B` §23 (Governance Gateway, for policy hierarchy). Interacts with §29 (Communication Standards) since authorization enforcement is implemented at the same ingress point as protocol handling.

### 28.8 Dependencies

Depends on the Security Gateway's Identity Plane and computed Authorization (`21B` §22.2). Depended on by all 26 modules without exception — there is no module exempted from authorization enforcement.

### 28.9 Failure Considerations

Authorization-evaluation unavailability is fail-closed system-wide (`21B` §22.9's pattern generalized): a module that cannot reach the Security Gateway's authorization function rejects the request rather than proceeding. This is a stricter posture than individual subsystem availability failures elsewhere in `21B`, because authorization failure has system-wide trust implications.

### 28.10 Operational Considerations

Authorization-evaluation latency is on every module's synchronous request path; its performance budget is the primary input to the CIR-004 composite latency allocation (`21B` §22.12), and this section reaffirms that every module — not only those specified in `21B` — inherits that budget constraint.

### 28.11 Constitutional Traceability

Realizes `14.12.4`'s intersect-never-union rule as a cross-cutting engineering guarantee rather than a per-subsystem one. Introduces no new constitutional responsibility beyond what `21B` §22 already establishes.

### 28.12 Architectural Guarantees

No module can be constructed with an authorization bypass, because the shared ingress template (§28.4) makes authorization checking structural rather than optional. Cascading revocation is guaranteed atomic across all 26 modules or is itself escalated as a Category 1 Incident.

---

## 29. Inter-Module Communication Standards

### 29.1 Purpose

Specifies the engineering realization of the three permitted communication modes established in `21A` §9 (Gateway Mediation, Event Emission, API Gateway Ingress) as concrete protocol, serialization, and versioning standards.

### 29.2 Scope

Applies to every inter-module call and event emission across all 26 modules. Does not govern intra-module internal calls, which are module-local implementation detail.

### 29.3 Architectural Responsibilities

Fixes a single serialization contract format used identically by all three communication modes, so that a module's Public Interfaces (as specified per-section throughout `21B`) are describable in one shared schema language. Enforces the 14 prohibited edges from `21A` §9 at the transport layer, not only at review time.

### 29.4 Design Principles

`[Implementation Decision]` Interface contracts are schema-first: a module's Public Interfaces (`21B` §X.5 for each subsystem) are defined in a shared schema format before implementation, and both caller and callee code are validated against that schema at build time. This is an engineering choice — the Constitution and `21A` specify the three permitted modes and the prohibited edges but do not mandate a specific schema technology, which is why this is marked as an implementation decision rather than constitutional meaning.

### 29.5 Engineering Constraints

No module may introduce a fourth communication mode. No module may call another module via a mode not declared in that target module's Consumed/Public Interfaces tables in `21B`. Schema changes to a Public Interface are versioned; breaking changes require a major version increment and a deprecation window (§30.6).

### 29.6 Implementation Requirements

Every module must publish its Public Interfaces (per `21B` §X.5) in the shared schema format. Every caller must validate against the callee's published schema, not an internally assumed shape. CIR-002 (`21A` §3, `21B` Preliminary Note) blocks final selection of the transport binding technology; this section specifies the contract layer above that binding, which is not blocked, while the wire-level binding awaits CIR-002 resolution.

### 29.7 Interactions With Other Components

Every module's Public Interfaces and Consumed Interfaces blocks throughout `21B` §13–§26 are the substantive content this section's schema standard formalizes. Interacts with §28 (Security) since authorization context is carried as part of every contract's envelope.

### 29.8 Dependencies

Depends on `21A` §9's three-mode model and 14-edge prohibition list. Blocked in part by CIR-002 for wire-level transport binding (per `21B` Preliminary Note).

### 29.9 Failure Considerations

A schema-incompatible call is rejected at the contract-validation boundary before reaching module logic, converting what would otherwise be a runtime failure deep inside a module into a clean, attributable ingress rejection.

### 29.10 Operational Considerations

Schema registries are versioned and Observability-visible (`21B` §24.5) so that contract drift across modules is detectable before it causes incidents.

### 29.11 Constitutional Traceability

Realizes `21A` §9 (Communication Model) as concrete engineering standard. Introduces no new communication mode beyond the three constitutionally and architecturally permitted ones.

### 29.12 Architectural Guarantees

Every inter-module call is guaranteed schema-validated at both ends. The 14 prohibited edges are guaranteed unrepresentable in the schema registry, not merely absent from current code.

---

## 30. Configuration, Feature Flags & Runtime Policy Management

### 30.1 Purpose

Specifies the engineering realization of the 7-level configuration precedence hierarchy established in `21A` §12, including feature flag management and runtime policy distribution.

### 30.2 Scope

Applies to all ordinary configuration across all 26 modules. Constitutional Declarations (`21A` §12's distinguished category) are read-only at this layer — this section governs their distribution mechanism, not their content or authority.

### 30.3 Architectural Responsibilities

Implements the 7-level precedence hierarchy as a single configuration-resolution service consumed by all modules, so precedence order cannot be reimplemented inconsistently. Implements feature-flag evaluation as a specialization of ordinary configuration (a boolean or enum-valued configuration key), not as a separate subsystem.

### 30.4 Design Principles

`[Implementation Decision]` Configuration is pull-based with push-notified invalidation: modules resolve configuration on demand from the shared resolution service and are notified to re-resolve on change, rather than each module maintaining an independently polled cache. This bounds staleness without imposing per-request resolution cost.

### 30.5 Engineering Constraints

No module may hard-code a value that the 7-level hierarchy would otherwise resolve. Secret values are never carried in configuration; only secret references are (`21A` §12), and this section's resolution service enforces that a value matching a secret-reference pattern is never resolved to a literal secret in transit.

### 30.6 Implementation Requirements

Every module consumes configuration exclusively through the shared resolution service. Feature-flag changes affecting Durable-Committed decision paths (e.g., a flag that changes Decision Gateway class thresholds, `21B` §18) are themselves routed through Governance visibility (`21B` §23) before activation, consistent with `21A` §12's treatment of Constitutional Declarations as a distinguished, higher-authority class.

### 30.7 Interactions With Other Components

Every module's Configuration Architecture inheritance from `21A` §12 is the direct dependency. Interacts with §29 (Communication Standards) for the invalidation-notification transport, which uses Event Emission mode.

### 30.8 Dependencies

Depends on `21A` §12 in full. Depended on by all 26 modules.

### 30.9 Failure Considerations

Resolution-service unavailability falls back to each module's last-successfully-resolved configuration snapshot rather than failing closed, since configuration (unlike authorization, §28.9) does not carry a trust boundary — a stale-but-previously-valid configuration is preferable to a hard stop for most modules, with the explicit exception of Constitutional Declarations, which fail closed if unresolvable.

### 30.10 Operational Considerations

Configuration resolution and invalidation events are emitted to Observability (`21B` §24.5) so that configuration drift across module instances is visible.

### 30.11 Constitutional Traceability

Realizes `21A` §12 as concrete engineering mechanism. Introduces no new precedence level and does not alter the distinguished status of Constitutional Declarations.

### 30.12 Architectural Guarantees

The 7-level precedence order is guaranteed identical across all 26 modules because it is resolved by one shared service. Secret values are guaranteed never to appear as configuration literals.

---

## 31. Error Handling, Fault Isolation & Recovery Strategy

### 31.1 Purpose

Specifies the uniform error taxonomy and fault-isolation engineering that underlies every module's Failure Domains block throughout `21B`.

### 31.2 Scope

Applies to all 26 modules' internal error handling and to the failure-domain boundaries specified per-subsystem in `21B` §X.9.

### 31.3 Architectural Responsibilities

Fixes a shared error taxonomy (transient/retryable, permanent/non-retryable, authorization, policy-violation, epistemic — the last drawn from the Knowledge Gateway's unique failure category, `21B` §17) used identically across all modules, so that error handling code does not reinvent classification per module. Implements fault isolation boundaries at exactly the module boundaries defined in `21A` §7, consistent with Database-Per-Module (`21A` §10) preventing a storage-layer fault from crossing modules.

### 31.4 Design Principles

`[Implementation Decision]` Retries are bounded and jittered, and retry budgets are itself a configuration value resolved through §30's precedence hierarchy rather than hard-coded per module, so retry policy can be tuned without code changes during incident response.

### 31.5 Engineering Constraints

No module may retry a Class A or Class B Decision Gateway operation without idempotency guarantees verified through the Compensation Verifier pattern (`21B` §18.3). No module's fault-isolation boundary may span two modules' Databases, per the Database-Per-Module principle (`21A` §10).

### 31.6 Implementation Requirements

Every module classifies every error condition into the shared taxonomy (§31.3) before it is emitted to Observability (§34) or the Category 1 Incident pipeline (`21B` §22.9, §24.9). Modules implementing the Panic Protocol (`21A` §5.2) must complete halt within the 5-second guarantee regardless of the error taxonomy classification of the triggering condition.

### 31.7 Interactions With Other Components

Directly consumes the Failure Domains block of every `21B` §13–§26 section. Interacts with §33 (Disaster Recovery) for the boundary between ordinary fault recovery (this section) and catastrophic recovery (§33).

### 31.8 Dependencies

Depends on `21A` §7 (module boundaries) and §10 (Database-Per-Module). Depended on by all 26 modules.

### 31.9 Failure Considerations

This section is itself the specification of failure considerations for the rest of the document; its own failure mode is a taxonomy gap — an error condition that does not cleanly classify — which is treated conservatively as permanent/non-retryable pending manual triage, never silently retried indefinitely.

### 31.10 Operational Considerations

Error taxonomy distribution across time and module is a first-class Observability signal (`21B` §24.3's Correlation Engine) used to detect systemic degradation before it reaches Category 1 severity.

### 31.11 Constitutional Traceability

Introduces no new constitutional responsibility. Consolidates the Failure Domains pattern already present in every `21B` subsystem section into one shared taxonomy and isolation boundary.

### 31.12 Architectural Guarantees

Every error across all 26 modules is guaranteed classified into exactly one of the shared taxonomy categories. Fault isolation boundaries are guaranteed coincident with module and Database boundaries, never crossing them.

---

## 32. Scalability, Performance & Capacity Architecture

### 32.1 Purpose

Specifies how the per-subsystem Performance Characteristics established throughout `21B` §X.12 compose into a system-wide capacity model, including resolution of the CIR-004 composite latency budget problem (`21A` §3, `21B` §22.12).

### 32.2 Scope

Applies to all 26 modules' scaling and capacity behavior. Governs horizontal scaling strategy, not the CIR-001-blocked infrastructure technology selection itself.

### 32.3 Architectural Responsibilities

Allocates the composite end-to-end latency budget across the full mediation chain identified as CIR-004 (`21A` §3), using the per-hop budgets already published in `21B` (e.g., Security §22.12, Memory §16.12) as fixed inputs and deriving the remaining chain-level headroom. Specifies capacity scaling as independent per module, consistent with Database-Per-Module (`21A` §10) permitting independent horizontal scaling without cross-module coordination.

### 32.4 Design Principles

`[Implementation Decision]` Capacity planning targets the p99 figures published in each `21B` §X.12 table, not p50, as the basis for provisioning — provisioning to p50 would leave the published p99 guarantees unmet under load. Stateless Execution Plane workers (Agent Runtime, `21B` §13) scale horizontally without coordination; stateful Identity Plane and Gateway-owned stores scale according to their persistence tier's native scaling model (`21A` §10).

### 32.5 Engineering Constraints

No module's capacity plan may assume unbounded horizontal scaling for a Durable-Committed store without accounting for that store's specific persistence tier scaling characteristics (`21A` §10's five tiers plus Stream). The composite CIR-004 budget allocation in §32.3 is binding — no subsystem may unilaterally revise its published per-hop budget without triggering re-allocation across the full chain.

### 32.6 Implementation Requirements

Each module publishes its capacity model (expected load, scaling trigger, scaling ceiling) alongside its `21B` §X.12 performance table. The composite CIR-004 allocation (§32.3) is maintained as a single shared document cross-referencing every subsystem's per-hop figures, updated whenever any subsystem's published targets change.

### 32.7 Interactions With Other Components

Directly depends on every `21B` §X.12 Performance Characteristics block. Interacts with §34 (Observability) for capacity-signal collection and §33 (Disaster Recovery) for capacity behavior under degraded conditions.

### 32.8 Dependencies

Depends on `21A` §10 (persistence tiers) and every `21B` subsystem's published performance figures. CIR-004 resolution depends on all per-hop budgets being finalized, including the `[Implementation Decision]`-derived figures noted as provisional in `21B` §16.12 and §22.12.

### 32.9 Failure Considerations

Under sustained overload, modules degrade per their individual Failure Domains (`21B` §X.9) rather than the system attempting a global backpressure mechanism, since no such mechanism is constitutionally specified and inventing one would exceed this document's scope of completing, not redesigning, the architecture.

### 32.10 Operational Considerations

Capacity utilization against the CIR-004 composite budget is a first-class Observability dashboard (`21B` §24.5) so that headroom erosion is visible before any individual subsystem breaches its published p99.

### 32.11 Constitutional Traceability

Introduces no new constitutional responsibility. Resolves CIR-004 as an engineering allocation exercise over figures already published or provisionally derived in `21B`.

### 32.12 Architectural Guarantees

The composite mediation-chain latency is guaranteed accounted for across every hop with no unallocated headroom gap, closing CIR-004 as an open architectural question at the engineering-planning level, subject to the provisional figures in `21B` §16.12 and §22.12 being finalized once their source constitutional gaps (Document 09's truncation) are resolved.

---

## 33. Disaster Recovery, Backup & Business Continuity

### 33.1 Purpose

Specifies backup, restoration, and continuity architecture for the Durable-Committed and Durable-Mutable state classes (`21A` §11) across all persistence tiers (`21A` §10).

### 33.2 Scope

Applies to every module's Data Ownership allocation (`21B` §X.7) for Durable state classes. Ephemeral-Recoverable and Ephemeral-Discardable state (`21A` §11) are explicitly out of scope, as their state classification already signals they need no backup.

### 33.3 Architectural Responsibilities

Specifies backup cadence and retention per persistence tier (`21A` §10's five tiers plus Stream), consistent with the Journal architecture's own 7-year minimum retention requirement (established across `21B`'s Gateway sections). Specifies restoration procedure ordering that respects the module dependency graph (`21A` §8), so that restoring a downstream module before its upstream dependency does not restore into an inconsistent state.

### 33.4 Design Principles

`[Implementation Decision]` Backup granularity is per-module, mirroring Database-Per-Module (`21A` §10), so that a single module's restoration never requires touching another module's store. Journal-tier data (append-only, tamper-evident) is backed up via the same append-only replication mechanism it is written with, rather than a separate periodic snapshot, preserving tamper-evidence through the backup itself.

### 33.5 Engineering Constraints

No restoration procedure may restore a module to a state that violates a currently-active Decision Gateway commitment (`21B` §18) — restoration must either restore the compensating record alongside the original or block until Decision Gateway state is reconciled. Restoration of Security Gateway Identity Plane state (`21B` §22.2) takes precedence in the dependency-respecting order of §33.3, since every other module's authorization checks depend on it.

### 33.6 Implementation Requirements

Every module owning Durable-Committed or Durable-Mutable state (`21A` §11) must specify a Recovery Point Objective and Recovery Time Objective consistent with its `21B` §X.9 Failure Domains severity classification. Category 1 Incident-triggering failures (`21B` §22.9, §24.9) invoke this section's restoration procedure as part of incident response.

### 33.7 Interactions With Other Components

Depends on every module's Data Ownership (`21B` §X.7) and State Management (`21B` §X.8) blocks. Interacts with §31 (Error Handling) for the boundary between ordinary fault recovery and disaster-level restoration.

### 33.8 Dependencies

Depends on `21A` §8 (dependency graph) for restoration ordering and §10–§11 (persistence tiers, state classes) for backup scope.

### 33.9 Failure Considerations

A failed restoration is itself escalated as a Category 1 Incident (`21B` §22.9's pattern), since a system that cannot restore its own Durable state has failed one of the constitution's most basic continuity expectations.

### 33.10 Operational Considerations

Restoration drills are scheduled operational exercises, not incident-triggered-only events; drill results are Observability-visible (`21B` §24.5) and reported to Governance (`21B` §23) as part of standing oversight.

### 33.11 Constitutional Traceability

Introduces no new constitutional responsibility. Operationalizes the Journal retention requirements and Durable state guarantees already established across `21A` §11 and `21B`'s Gateway sections.

### 33.12 Architectural Guarantees

Every module owning Durable state is guaranteed a specified RPO/RTO. Restoration ordering is guaranteed to respect the dependency graph, preventing inconsistent cross-module restoration.

---

## 34. Observability, Monitoring & Operational Excellence

### 34.1 Purpose

Specifies the engineering standards for how every module integrates with the Observability Gateway (`21B` §24), completing that section's architecture with concrete instrumentation requirements.

### 34.2 Scope

Applies to all 26 modules' telemetry emission. Does not alter the Observability Gateway's own architecture, which is frozen and ratified in `21B` §24.

### 34.3 Architectural Responsibilities

Fixes the minimum instrumentation every module must emit: request-level tracing spans at every Public Interface (`21B` §X.5 tables), state-transition events at every Durable-Progressive stage change (`21A` §11), and the four telemetry types (metrics, logs, traces, events) all routed through the Kernel's out-of-band emission channel (`21A` §5.2, `21B` §24.3).

### 34.4 Design Principles

`[Implementation Decision]` Instrumentation is applied via the same shared ingress template used for authorization (§28.4), so that a module cannot be constructed without both authorization enforcement and telemetry emission — both are structural, not opt-in, consequences of using the shared module scaffold.

### 34.5 Engineering Constraints

No module may emit telemetry through a channel other than the Kernel's shared emission mechanism (`21A` §5.2), consistent with `21B` §24.4's requirement that no operational path depend on Observability ingest latency — a module-specific telemetry channel would risk exactly that coupling.

### 34.6 Implementation Requirements

Every module publishes its SLI/SLO targets (from its `21B` §X.12 Performance Characteristics block) to the Observability Gateway's SLI/SLO Registry (`21B` §24.3) at deployment time (§25). Alerting thresholds are configured per module against its own published targets, not a system-wide default.

### 34.7 Interactions With Other Components

Directly implements the consumer side of `21B` §24 (Observability Gateway). Interacts with §31 (Error Handling) for error-taxonomy-to-telemetry mapping and §32 (Scalability) for capacity-signal collection.

### 34.8 Dependencies

Depends on `21B` §24 in full and `21A` §5.2 (Kernel emission channel). Depended on by all 26 modules.

### 34.9 Failure Considerations

A module that fails to emit required telemetry is itself a conformance failure detectable at the shared scaffold level (§34.4), not merely an operational gap discovered later — the Definition of Done (§39) includes instrumentation conformance as a gate.

### 34.10 Operational Considerations

Operational excellence is measured against each module's own published SLI/SLO, aggregated by the Observability Gateway's Correlation Engine (`21B` §24.3) into system-wide health narratives consumed by Governance (`21B` §23).

### 34.11 Constitutional Traceability

Introduces no new constitutional responsibility. Operationalizes `16`'s observability rights (`21B` §24.16) as concrete per-module instrumentation requirements.

### 34.12 Architectural Guarantees

Every module is guaranteed to emit the minimum instrumentation set (§34.3) as a structural property of the shared scaffold, not a per-module implementation choice that could be omitted.

---

# Part V — Engineering Delivery

## 35. Repository Build Order

### 35.1 Purpose

Specifies the concrete construction sequence for the 26-module hierarchy, resolving the Build Order first proposed in `21_IMPLEMENTATION_ARCHITECTURE_PLAN.md` into a final, binding sequence consistent with the dependency graph in `21A` §8.

### 35.2 Scope

Applies to the full 26-module hierarchy and the Repository Architecture established in `21A` §8, extending the ratified `02.14` structure.

### 35.3 Architectural Responsibilities

Fixes build stages S0–S12 as specified in the approved Planning Package, with the "FIRST LIGHT" milestone at S7 as the first point at which an end-to-end request can traverse Agent Runtime → Workflow Engine → Event Bus → a minimal Gateway chain without every subsystem being complete. Sequences the Constitutional Kernel (`21A` §6) and shared libraries (§27.4) at S0, before any Gateway, since every subsequent module depends on them.

### 35.4 Design Principles

`[Implementation Decision]` CIR-001-blocked subsystems (Integration, Deployment, Evolution — `21B` §20, §25, §26) are sequenced at the latest stages (S11–S12) regardless of their position in the dependency graph's depth ordering, since their construction cannot begin until CIR-001 resolves; sequencing them last minimizes schedule risk from an unresolved constitutional-interpretation blocker.

### 35.5 Engineering Constraints

No module may begin construction before every module it depends on (per `21A` §8's dependency graph) has passed its Definition of Done (§39). The Security Gateway (`21B` §22) and Observability Gateway (`21B` §24) must both be construction-complete before any Gateway that depends on them for authorization or telemetry begins integration testing, since §28 and §34 make both structural dependencies of the shared module scaffold.

### 35.6 Implementation Requirements

Each build stage S0–S12 produces a stage-completion artifact verified against the Conformance Gates (§37) before the next stage begins. Stage S7 ("FIRST LIGHT") requires a passing end-to-end integration test (§38) across the minimal chain before being declared complete.

### 35.7 Interactions With Other Components

Directly extends the Build Order first specified in `21_IMPLEMENTATION_ARCHITECTURE_PLAN.md` and the dependency graph in `21A` §8. Interacts with §36 (Roadmap) which sequences this build order against calendar time.

### 35.8 Dependencies

Depends on `21A` §7 (module hierarchy) and §8 (dependency graph) in full.

### 35.9 Failure Considerations

A stage that fails its completion gate (§37) blocks all subsequent stages depending on it; partial stage completion is not permitted to unblock dependent stages, since `21A` §8's dependency graph is load-bearing for correctness, not merely advisory sequencing.

### 35.10 Operational Considerations

Build stage progress is Observability-visible (`21B` §24.5) and reported to Governance (`21B` §23) at each stage boundary.

### 35.11 Constitutional Traceability

Introduces no new constitutional responsibility. Finalizes the Build Order proposed and approved in the Planning Package (`21_IMPLEMENTATION_ARCHITECTURE_PLAN.md`).

### 35.12 Architectural Guarantees

No module is guaranteed constructible before its dependencies are complete. Stage S7 is guaranteed to represent the first point of genuine end-to-end system behavior.

---

## 36. Incremental Implementation Roadmap

### 36.1 Purpose

Sequences the Build Order (§35) against practical delivery increments, identifying which stages can proceed in parallel and which are strictly serial.

### 36.2 Scope

Applies to the twelve build stages S0–S12 defined in §35.3.

### 36.3 Architectural Responsibilities

Identifies parallelizable stages: modules at the same depth in the dependency graph (`21A` §8) with no direct dependency between them may be constructed concurrently by separate teams. Identifies strictly serial stages: S0 (Kernel and shared libraries) must complete before any other stage begins; S7 ("FIRST LIGHT") must complete before S8 begins, since S8 onward assumes a working minimal end-to-end path exists to test against.

### 36.4 Design Principles

`[Implementation Decision]` Within each depth level of the dependency graph, modules are further ordered by risk: the highest-risk subsystems identified in the Planning Package's risk register (R1–R13) are constructed earliest within their eligible stage, so that the riskiest unknowns surface while there is still schedule headroom to address them, rather than at the end of the roadmap.

### 36.5 Engineering Constraints

Parallel construction within a stage may not introduce a dependency between the parallel modules that was not present in `21A` §8's graph — if such a dependency is discovered during construction, it is treated as a graph-correction event requiring Governance visibility (`21B` §23), not a silent local accommodation.

### 36.6 Implementation Requirements

Each roadmap increment produces a demonstrable capability increase, not merely code volume — the increment's completion criteria are drawn directly from the Definition of Done (§39) for the modules it covers.

### 36.7 Interactions With Other Components

Directly sequences §35's Build Order. Interacts with §37 (Conformance Gates), whose gates are the checkpoints between roadmap increments.

### 36.8 Dependencies

Depends on §35 (Build Order) and the Planning Package's risk register (R1–R13).

### 36.9 Failure Considerations

A roadmap increment that reveals a previously unidentified dependency or risk is escalated to Governance (`21B` §23) for graph correction before the roadmap proceeds, rather than being absorbed silently into schedule slip.

### 36.10 Operational Considerations

Roadmap progress against increments is tracked and Observability-visible (`21B` §24.5) alongside build-stage progress (§35.10).

### 36.11 Constitutional Traceability

Introduces no new constitutional responsibility. Pure engineering sequencing of already-ratified build order.

### 36.12 Architectural Guarantees

Parallelization is guaranteed not to introduce dependencies absent from `21A` §8's graph without explicit Governance-visible correction.

---

## 37. Engineering Standards, Conformance Gates & Quality Assurance

### 37.1 Purpose

Specifies the concrete gates every module must pass before being declared complete, consolidating the conformance requirements implied throughout `21A` and `21B` into a single checklist mechanism.

### 37.2 Scope

Applies to every module in the 26-module hierarchy at every build stage boundary (§35.6).

### 37.3 Architectural Responsibilities

Defines the conformance gate categories: constitutional traceability (every claim in the module's `21B` section cites a constitutional provision or is marked `[Implementation Decision]`), cross-cutting pattern conformance (§27–§34 requirements met), interface contract validation (§29.6), authorization enforcement (§28.6), and instrumentation conformance (§34.9).

### 37.4 Design Principles

`[Implementation Decision]` Conformance gates are automated where the underlying property is mechanically checkable (schema validation, authorization-scaffold presence, instrumentation-scaffold presence) and manually reviewed where it is not (constitutional traceability accuracy, architectural fidelity to `21B`'s prose specification).

### 37.5 Engineering Constraints

No module passes a conformance gate on partial completion — the gate categories in §37.3 are individually pass/fail, not scored. A module blocked by CIR-001 (Integration, Deployment, Evolution) cannot pass construction-completion gates until CIR-001 resolves, but may pass specification-conformance gates (its `21B` section's internal consistency) independently.

### 37.6 Implementation Requirements

Every module's conformance gate results are recorded against the Journal architecture pattern (§27.3) for audit permanence. Gate failures block stage progression per §35.9.

### 37.7 Interactions With Other Components

Directly gates §35 (Build Order) stage transitions and §36 (Roadmap) increments. Consumes §38 (Testing Architecture) results as part of the automated gate category.

### 37.8 Dependencies

Depends on all of §27–§34 (cross-cutting concerns being conformed to) and `21B`'s per-module specifications (the target being conformed against).

### 37.9 Failure Considerations

A module that repeatedly fails the same conformance gate category is escalated to Governance (`21B` §23) as a construction risk, consistent with Governance's meta-oversight role (`21B` §23.4) rather than being permitted indefinite re-attempts without visibility.

### 37.10 Operational Considerations

Conformance gate pass rates across the 26-module hierarchy are an Observability-tracked (`21B` §24.5) engineering health signal.

### 37.11 Constitutional Traceability

Introduces no new constitutional responsibility. Operationalizes the constitutional-fidelity discipline already exercised throughout `21A` and `21B`'s drafting (citation-per-claim, `[Implementation Decision]` labeling) as a formal, checkable gate.

### 37.12 Architectural Guarantees

No module is guaranteed complete without passing every applicable conformance gate category. Gate results are guaranteed permanently recorded.

---

## 38. Testing Architecture

### 38.1 Purpose

Specifies the testing strategy across unit, integration, and end-to-end levels required to substantiate the conformance gates in §37.

### 38.2 Scope

Applies to every module and to the cross-cutting patterns in §27–§34.

### 38.3 Architectural Responsibilities

Defines three testing levels: unit tests (per-module, verifying that section's Internal Architecture, `21B` §X.4), integration tests (per-dependency-edge, verifying Public/Consumed Interface contracts, `21B` §X.5–§X.6), and end-to-end tests (across the minimal FIRST LIGHT chain and beyond, verifying composite behavior including the CIR-004 latency budget from §32.3).

### 38.4 Design Principles

`[Implementation Decision]` Failure-domain tests (verifying each `21B` §X.9 table's containment claims) are mandatory for every module, since a Failure Domains table that is asserted but never tested is an untested architectural guarantee — this document treats that as an unacceptable gap given the constitutional weight placed on failure containment throughout `21B`.

### 38.5 Engineering Constraints

Recursion Guard components (§27.3, `21B` §21.3, §26.3) require dedicated adversarial tests that attempt self-referential inputs, since their fail-closed posture (`21B` §26.9) is only meaningful if exercised against genuine self-reference attempts, not merely ordinary-path tests.

### 38.6 Implementation Requirements

Every module's test suite includes coverage for each of its 16 `21B` template blocks where applicable (a Data Ownership claim is tested via a cross-module isolation test; a Guarantees claim is tested via a scenario that would violate it if the guarantee did not hold). CIR-001-blocked modules (Integration, Deployment, Evolution) maintain specification-level tests (schema and contract validation) but cannot maintain full integration tests until construction unblocks.

### 38.7 Interactions With Other Components

Directly substantiates §37 (Conformance Gates). Consumes §31's error taxonomy (§31.3) for failure-domain test case design.

### 38.8 Dependencies

Depends on every `21B` section's specification content as the test oracle, and on §27–§34's cross-cutting requirements.

### 38.9 Failure Considerations

A test gap discovered post-construction is treated as a conformance-gate regression (§37.9), triggering the same Governance-visible escalation path as a live gate failure.

### 38.10 Operational Considerations

Test coverage and pass-rate trends are Observability-tracked (`21B` §24.5) alongside conformance gate metrics (§37.10).

### 38.11 Constitutional Traceability

Introduces no new constitutional responsibility. Operationalizes verification of guarantees already specified throughout `21A` and `21B`.

### 38.12 Architectural Guarantees

Every module's Failure Domains and Guarantees claims are guaranteed to have corresponding adversarial or scenario test coverage before that module passes its conformance gate.

---

## 39. Definition of Done

### 39.1 Purpose

Consolidates §35–§38 into a single binding checklist a module must satisfy to be declared complete.

### 39.2 Scope

Applies uniformly to all 26 modules, with the CIR-001 qualification noted in §37.5 and §38.6 for the three blocked subsystems.

### 39.3 Architectural Responsibilities

A module is Done when: its `21B` specification section is unchanged from ratified form (no drift between spec and implementation); all §37.3 conformance gate categories pass; all §38.3 test levels applicable to its build stage pass; its telemetry conforms to §34.3's minimum instrumentation set; and its stage-completion artifact (§35.6) is recorded in the Journal.

### 39.4 Design Principles

`[Implementation Decision]` Definition of Done is binary per module, not partial — a module is either Done or not, with no intermediate "mostly done" state permitted to unblock dependent modules, mirroring the pass/fail posture established for conformance gates in §37.5.

### 39.5 Engineering Constraints

A CIR-001-blocked module (Integration, Deployment, Evolution) cannot reach full Done status until CIR-001 resolves; it may reach "specification-conformant, construction-blocked" status, which is a distinct, explicitly labeled state that must not be conflated with Done in any reporting surface (§39.10).

### 39.6 Implementation Requirements

Done status is recorded as an immutable Journal entry (§27.3's append-only pattern) at the moment all §39.3 criteria are simultaneously satisfied, not asserted progressively as individual criteria pass.

### 39.7 Interactions With Other Components

Directly consumes §37 (Conformance Gates) and §38 (Testing) as its evaluation inputs. Gates §35's Build Order stage transitions (§35.6).

### 39.8 Dependencies

Depends on §35–§38 in full.

### 39.9 Failure Considerations

A module that regresses from Done status (a later change breaks a previously-passing criterion) is treated as a conformance-gate failure (§37.9) and re-enters the non-Done state until re-verified.

### 39.10 Operational Considerations

Done status per module is Observability-visible (`21B` §24.5) and Governance-visible (`21B` §23) as a distinct dashboard from ordinary build-stage progress, explicitly distinguishing "Done," "In Progress," and "Specification-Conformant, Construction-Blocked" (§39.5) states.

### 39.11 Constitutional Traceability

Introduces no new constitutional responsibility. Formalizes completion criteria implicit throughout `21A` and `21B`'s architectural rigor.

### 39.12 Architectural Guarantees

No module is reported Done unless all §39.3 criteria are simultaneously and currently satisfied. The CIR-001-blocked state is guaranteed distinguishable from genuine Done status in every reporting surface.

---

## 40. Implementation Appendices

### 40.1 Purpose

Provides a consolidated cross-reference index across `21A`, `21B`, and `21C`, and a single registry of all open Constitutional Interpretation Register entries and `[Implementation Decision]` markers for construction-time reference.

### 40.2 Scope

Applies as a reference layer over `21A`, `21B`, and this document; introduces no new architectural content.

### 40.3 Architectural Responsibilities

Indexes: the 26-module hierarchy with `21B` section cross-references; the full CIR-001 through CIR-009 register (`21A` §3) with current status and the sections each blocks (`21B` §20, §25, §26; this document's §35.4, §37.5, §38.6, §39.5 for CIR-001; transport binding sections for CIR-002 per §29.6); and every `[Implementation Decision]` marker across `21A`, `21B`, and `21C` in one table, so that a future engineering team can locate every point at which this architecture made an engineering choice not compelled by the Constitution.

### 40.4 Design Principles

This appendix is a derived index, not a source of truth — where it and the body sections of `21A`/`21B`/`21C` conflict, the body sections govern, consistent with the general principle that summaries do not supersede the material they summarize.

### 40.5 Engineering Constraints

The appendix must be regenerated whenever a CIR entry resolves or a new `[Implementation Decision]` is introduced through change control; it is not maintained as static content once construction begins.

### 40.6 Implementation Requirements

CIR resolution status is sourced from Governance's ratification record (`21B` §23.4), not independently tracked. `[Implementation Decision]` entries are sourced by scanning `21A`, `21B`, and `21C` for the marker, not manually re-curated.

### 40.7 Interactions With Other Components

Cross-references every section of `21A`, `21B`, and this document.

### 40.8 Dependencies

Depends on the full, frozen text of `21A` and `21B`, and on this document's own §27–§39.

### 40.9 Failure Considerations

An out-of-date appendix is a documentation defect, not an architectural one; it does not block construction but is flagged as a conformance-gate finding (§37.9) if discovered stale during a gate review.

### 40.10 Operational Considerations

The appendix is maintained as a living reference document outside the frozen/ratified body of `21A`/`21B`/`21C`, consistent with its role as a derived index rather than authoritative content.

### 40.11 Constitutional Traceability

Introduces no new constitutional responsibility; is purely a navigational aid over already-ratified content.

### 40.12 Architectural Guarantees

Every CIR entry and every `[Implementation Decision]` across the full Implementation Architecture is guaranteed locatable through this single index.

---

# Implementation Architecture Completion Statement

Documents `21A_IMPLEMENTATION_ARCHITECTURE_CORE.md`, `21B_IMPLEMENTATION_ARCHITECTURE_SUBSYSTEMS.md`, and `21C_IMPLEMENTATION_ARCHITECTURE_DELIVERY.md` together constitute the complete Implementation Architecture of Agent OS. `21A` established the foundations and structure (Parts I–II, sections 1–12): the Constitutional Interpretation Register, the Layer/Plane model, the Gateway Pattern, the Constitutional Kernel, the module hierarchy, the repository architecture, the communication model, data ownership, state management, and configuration architecture. `21B` specified the internal implementation architecture of all fourteen core constitutional subsystems (Part III, sections 13–26), each to a uniform sixteen-block template, each traced to its constitutional source. `21C` completes the architecture with cross-cutting engineering patterns applicable uniformly across all twenty-six modules (Part IV, sections 27–34) and the engineering delivery mechanics by which the architecture is built, verified, and declared complete (Part V, sections 35–40).

## Relationship to the Constitutional Documents

Documents `01` through `19` remain the ultimate authority over Agent OS. Nothing in `21A`, `21B`, or `21C` amends, reinterprets, or supersedes any constitutional provision. Every architectural and engineering decision in the Implementation Architecture either traces directly to a constitutional citation or is explicitly labeled `[Implementation Decision]` to distinguish engineering choice from constitutional meaning. Where constitutional ambiguity exists — the nine entries of the Constitutional Interpretation Register — construction is explicitly blocked pending Governance resolution rather than resolved unilaterally by this architecture.

## Relationship to the Manifest Documents

Documents `20A`, `20B`, and `20C` remain the implementation reference — the compressed, structured summary of the Constitution's purpose, responsibilities, guarantees, and boundaries per source document. The Implementation Architecture (`21A`–`21C`) is built on and consistent with the Manifests, but the Manifests are not superseded; they remain the fastest path to recovering constitutional intent for any subsystem, while `21A`–`21C` specify how that intent is realized in buildable form.

## Relationship to Future Engineering Documents

All future engineering work on Agent OS — code, infrastructure, operational runbooks, team-level design documents — must conform to the architectural specifications in `21A`, `21B`, and `21C`. Future documents may elaborate implementation detail within the boundaries this Implementation Architecture establishes, but may not move responsibilities between subsystems, introduce new constitutional concepts, change ownership boundaries, or remove any architectural guarantee specified herein without that change first passing through Governance ratification, consistent with the amendment path specified in `21B` §23 and §26.

## Formal Ratification Statement

The Implementation Architecture of Agent OS, comprising `21A_IMPLEMENTATION_ARCHITECTURE_CORE.md`, `21B_IMPLEMENTATION_ARCHITECTURE_SUBSYSTEMS.md`, and `21C_IMPLEMENTATION_ARCHITECTURE_DELIVERY.md`, is hereby complete as specified. Construction may proceed against this architecture for all modules not blocked by an open Constitutional Interpretation Register entry. Modules blocked by CIR-001 (Integration Platform, Deployment Platform, Evolution Gateway) are fully specified and await Governance resolution before construction begins. This Implementation Architecture is subordinate to the Constitution in full and does not itself carry constitutional authority.
