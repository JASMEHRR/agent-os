# 21A_IMPLEMENTATION_ARCHITECTURE_CORE.md

**Agent OS — Implementation Architecture, Part A: Foundations & Structure**
**Version:** 1.0.0
**Status:** Ratified for Implementation
**Classification:** Implementation Specification — Binding on All Construction Work
**Subordinate To:** `01_PRINCIPLES.md` through `19_EVOLUTION_OPERATING_MODEL.md`

---

## Table of Contents

**Part I — Foundations**

1. Preamble & Constitutional Fidelity Statement
2. Implementation Philosophy
3. Constitutional Interpretation Register
4. Architectural Layers & Planes
5. The Gateway Pattern
6. The Constitutional Kernel

**Part II — Structure**

7. Module Hierarchy & Boundaries
8. Repository Architecture
9. Interface Contracts & Communication Model
10. Data Ownership & Persistence Architecture
11. State Management
12. Configuration Architecture

---
---

# PART I — FOUNDATIONS

---

## 1. Preamble & Constitutional Fidelity Statement

### 1.1 Purpose

This document translates the ratified constitutional architecture of Agent OS into a buildable implementation architecture. It specifies how the constitution becomes software: what modules exist, how they are bounded, how they communicate, what data they own, how they hold state, and how they are configured.

It exists because a constitution that cannot be constructed is a theory, and a construction that does not trace to a constitution is an accident. Documents 01 through 19 establish what Agent OS *is* and what it *guarantees*. This document establishes how those guarantees are realized in code without being diluted, reinterpreted, or quietly abandoned during construction.

The document is written for engineers who will build subsystems independently and whose work must nonetheless compose into a single constitutionally coherent operating system. It assumes those engineers will not read all nineteen constitutional documents before writing their first module. It therefore carries the constitutional obligations forward into structural form, so that conformance is a property of the architecture rather than a burden on individual judgment.

### 1.2 Architectural Responsibilities

This document is responsible for:

- Declaring the implementation philosophy that governs every construction decision.
- Maintaining the Constitutional Interpretation Register — the authoritative list of ambiguities in the ratified text that must be resolved through the Governance Gateway before or during construction.
- Defining the layer and plane model within which all modules reside.
- Specifying the Gateway Pattern as the universal implementation primitive by which the eleven constitutional Gateways achieve uniform conformance.
- Specifying the Constitutional Kernel — the shared implementation library realizing the mechanisms the constitution states repeatedly.
- Enumerating the complete module hierarchy with constitutional provenance for every module.
- Extending the ratified repository structure to accommodate subsystems introduced after that structure was ratified.
- Defining the permitted communication modes and the prohibited edges between modules.
- Allocating data ownership across all modules under the Database Per Module principle.
- Specifying the state model, including what is durable, what is recoverable, and what may be discarded.
- Specifying the configuration architecture, including hierarchy, validation, scoping, and secret referencing.

### 1.3 Architectural Constraints

**The constitution is frozen.** Documents 01 through 19 are ratified and may not be modified by this document, by any engineering decision, or by any construction expedient. Where construction encounters a constitutional obstacle, the obstacle is either designed around within constitutional bounds, or routed to the Governance Gateway's interpretation process, or escalated as a proposed amendment through the Evolution Gateway. It is never bypassed.

**This document introduces no constitutional concepts.** Every term used here is drawn from the ratified vocabulary. Two constructs — the Constitutional Kernel and the Human Interface — are implementation artifacts rather than constitutional subsystems, and both are explicitly labelled as such wherever they appear. No third exception exists.

**This document does not reallocate responsibility.** The responsibilities assigned to each subsystem by Documents 02 and 05 through 19 are carried forward unchanged. Where this document appears to assign a responsibility, it is specifying *where in software* a constitutionally assigned responsibility is realized, not *to whom* it belongs.

**This document does not resolve constitutional ambiguity.** Where the ratified text is internally inconsistent or silent on a matter with constitutional consequence, this document records the ambiguity in the Constitutional Interpretation Register (Section 3) and routes it to the authority competent to resolve it. It does not resolve such matters by engineering judgment.

### 1.4 Component Relationships

This document is Part A of a multi-part implementation architecture. It establishes the foundations and structure upon which the subsystem implementation architectures depend.

| Related artifact | Relationship |
|---|---|
| `01`–`19` | Constitutional source. Governs architectural meaning. Frozen. |
| `20A`–`20C` | Approved constitutional manifests. The working reference for constitutional content. |
| `21_IMPLEMENTATION_ARCHITECTURE_PLANNING` | Approved planning package. Governs implementation structure. Authoritative blueprint for this document. |
| `21B` and subsequent parts | Subsystem implementation architectures. Depend on Parts I and II established here. |
| Architecture Decision Records | Record implementation decisions made within the bounds established here. Subordinate to this document. |

### 1.5 Guarantees

This document guarantees:

1. **Constitutional Traceability.** Every module, boundary, interface, and data allocation specified here traces to a named provision of Documents 01 through 19. No structure exists without constitutional provenance.
2. **Non-Reinterpretation.** No constitutional term is redefined, narrowed, or broadened. Where the constitution is ambiguous, the ambiguity is preserved and registered rather than silently resolved.
3. **Responsibility Preservation.** No responsibility is moved between subsystems. The implementation realizes the constitutional allocation exactly.
4. **Precedence Clarity.** Where this document and the constitution differ on architectural meaning, the constitution governs. Where this document and any subordinate engineering artifact differ on implementation structure, this document governs.
5. **Completeness of Foundation.** Parts I and II are sufficient to begin construction of any module without further foundational specification.

### 1.6 Interaction with the Constitution

This document derives from and remains subordinate to the ratified constitutional architecture. It is classified as an Implementation Specification and is binding on all construction work.

Its relationship to the constitution mirrors the relationship `03_TECH_STACK` bears to `02_ARCHITECTURE`: where the constitution defines *what components exist and what they guarantee*, this document defines *how those components are constructed*. It occupies the same subordinate position and carries the same obligation of fidelity.

Changes to this document are governed by the ordinary Architecture Decision Record process where they concern implementation structure. Changes that would alter constitutional meaning, subsystem responsibility, or any non-violable rule are outside the ADR process entirely and must proceed through the Evolution Gateway's amendment process and the Governance Gateway's ratification authority.

Where this document is silent, the constitution governs. Where this document speaks on implementation structure, it is binding.

---

## 2. Implementation Philosophy

### 2.1 Purpose

This section states the engineering convictions that govern every construction decision in Agent OS. It exists because a system of twenty-four modules built by multiple teams without a stated philosophy produces twenty-four philosophies, and because the constitution's guarantees are only as durable as the structural habits of the engineers realizing them.

The philosophy is not aspirational. Each conviction below has a structural consequence specified elsewhere in this document, and each is enforceable through the conformance gates that govern module completion.

### 2.2 Architectural Responsibilities

The philosophy comprises nine convictions.

**2.2.1 The Gateway is the universal primitive.**

Documents 09 through 19 each define a subsystem mediated by a Gateway, and every one of those Gateways declares the identical structural skeleton: identity primitives, classification taxonomy, sole-mediation topology, boundary enforcement, guarded lifecycle, post-commitment immutability, immutable journal, confidence-graded authority, sixty-second failure classification, self-audit, Panic compliance, bounded self-modification, and human terminal authority.

This repetition is the constitution's clearest implementation signal. The eleven Gateways are specializations of one primitive. The implementation builds that primitive once, in the Constitutional Kernel, and specializes it eleven times. The alternative — eleven bespoke Gateways — produces eleven divergent interpretations of "boundary enforcement" and eleven distinct ways to violate the same rule.

**2.2.2 Conformance by construction, not conformance by review.**

Approximately two hundred non-violable rules span Documents 01 through 19. No review process can reliably enforce two hundred absolute rules across twenty-four modules and an indefinite construction horizon. Conformance must therefore be structural: illegal actions must be difficult or impossible to express, rather than possible to express and forbidden by policy.

This has three consequences. Boundary enforcement lives in the kernel, not in each subsystem's discretion. Prohibited dependency edges are detected by tooling, not by reviewers. Every non-violable rule maps to an automated conformance test, and a module is not complete until its rules are covered.

**2.2.3 Depth-first dependency closure.**

Each construction stage closes its dependency set completely before the next begins. No module is built against a stubbed Gateway, because a stubbed Gateway cannot enforce a boundary, and an unenforced boundary that ships becomes load-bearing. Breadth-first construction — many modules at partial depth — produces a system in which every boundary is provisional and none is trusted.

**2.2.4 First Light as the organizing milestone.**

The system's purpose is to operate businesses autonomously. Construction is organized so that the earliest point at which the dependency graph permits that purpose to be demonstrated is reached as early as possible, and everything before it is understood as scaffolding.

This converts a long construction programme from an act of faith into a working system that subsequently thickens. It also produces early empirical evidence about the composite latency of the mediation chain, the write amplification of the journal architecture, and the practicality of the Panic Protocol guarantee — three matters on which the constitution states requirements but provides no design.

**2.2.5 Hexagonal within, mediated between.**

Each module is internally organized as ports and adapters, per `01.7.1`: the domain layer knows nothing of transport, persistence, or model providers. Between modules, all interaction is mediated — by a Gateway, by the Event Bus, or by the API Gateway. No module reaches into another module's internals, database, or process.

The two disciplines are complementary. Hexagonal structure makes a module testable and its adapters replaceable. Mediated interaction makes the system's boundaries enforceable and its behaviour auditable.

**2.2.6 The journal is the substrate, not a side effect.**

Every constitutional subsystem maintains an append-only, tamper-evident journal retained a minimum of seven years. At the ratified throughput targets, journal writes are the system's dominant write path — not agent reasoning, not inference, not event delivery.

The implementation therefore treats the journal as a first-class kernel capability with a single write path, a single tamper-evidence scheme, a single retention engine, and a single archival tier. It is designed for first and budgeted for explicitly, not accreted as an audit obligation discovered late.

**2.2.7 Fail-safe defaults are inherited, not re-decided.**

The constitution's failure philosophy is uniform across every subsystem: when uncertain, halt; when overwhelmed, shed load; when corrupted, isolate; ambiguity is never resolved in favour of action. The five-category classification taxonomy and the sixty-second classification bound recur verbatim in six documents.

The implementation encodes this once in the kernel. Subsystems inherit fail-safe behaviour rather than each deciding what to do when uncertain. A subsystem that must deviate does so explicitly and with constitutional justification, never by omission.

**2.2.8 Local-first operability is a construction constraint, not a deployment option.**

`01` non-violable rule 2 requires core functions to operate without internet connectivity. Every external dependency — every integration, every Premium-tier model, every substrate operator service — must therefore have a degraded mode that preserves core operation.

This is a constraint on how modules are written, not a matter to be addressed at deployment. A module whose core path hard-depends on an external provider violates a non-violable rule regardless of how it is deployed.

**2.2.9 Implementation neutrality where the constitution is neutral.**

Where the constitution specifies a technology, the implementation uses it. Where the constitution specifies a guarantee without a technology, the implementation specifies the guarantee and treats the technology as replaceable. This preserves the portability and provider-neutrality obligations of `17.23` and `18.27` and keeps engineering decisions inside the Architecture Decision Record process rather than escalating them into constitutional matters.

### 2.3 Architectural Constraints

The philosophy operates under the following constraints.

- **It may not soften a constitutional requirement.** Where a conviction and a non-violable rule conflict, the rule governs and the conviction is amended.
- **It may not be invoked to justify deviation.** "Conformance by construction" is a method of achieving conformance, never a substitute for it. A module that is structurally elegant but violates a rule is non-conformant.
- **It applies uniformly.** No module, however small, urgent, or experimental, is exempt. Experimental modules operate under the isolation constraints of `01.18.4` and `19.22`, which are additional constraints, not relaxations.
- **Depth-first closure may not be traded for schedule.** Where schedule pressure and dependency closure conflict, scope is reduced rather than depth.

### 2.4 Component Relationships

| Conviction | Realized structurally in |
|---|---|
| Gateway as universal primitive | §5 The Gateway Pattern; §6 The Constitutional Kernel |
| Conformance by construction | §6 kernel capabilities; §9 prohibited edges; Part V conformance suite |
| Depth-first closure | Part V build sequencing; §7 module hierarchy |
| First Light | Part V build sequencing |
| Hexagonal within, mediated between | §8 per-service structure; §9 communication model |
| Journal as substrate | §6 kernel; §10 persistence architecture; Part IV journal architecture |
| Fail-safe defaults inherited | §6 kernel; Part IV failure domains |
| Local-first operability | §12 configuration; §9 degraded-mode contracts |
| Implementation neutrality | §10 persistence tiers; §9 transport binding |

### 2.5 Guarantees

The philosophy guarantees:

1. **Uniform conformance surface.** Every Gateway enforces boundaries, guards transitions, journals immutably, emits signals, and honours Panic identically, because all eleven consume the same kernel.
2. **Detectable violation.** Prohibited dependencies, missing journals, absent signal emission, and uncovered non-violable rules are detectable by tooling rather than dependent on review.
3. **Trustworthy boundaries.** Every boundary that exists in the shipped system has been enforced since the moment its module first ran, because no module was built against a stub.
4. **Early empirical evidence.** The three matters on which the constitution states requirements without design — composite latency, journal amplification, Panic timing — are measured at First Light rather than discovered at scale.
5. **Constitutional survivability under staff change.** Structural conformance persists across engineer turnover in a way that documented policy does not.

### 2.6 Interaction with the Constitution

The philosophy is derived, not invented. Each conviction restates a constitutional obligation in structural form:

- Conviction 1 derives from the repeated Gateway architecture of `09`–`19`.
- Conviction 2 derives from the non-violable rule sets of every constitutional document and from `14.33`, which places enforcement of non-violable rules at the Security Gateway "at the point of action."
- Conviction 3 derives from `01.4.1` modularity and `02` Appendix A rule 1.
- Conviction 4 derives from `01.17.1`, which measures success by autonomy ratio and business outcome rather than by construction progress.
- Conviction 5 derives from `01.7.1` hexagonal architecture and the sole-mediation topology of every Gateway.
- Conviction 6 derives from the journal and retention provisions common to all eleven Gateways.
- Conviction 7 derives from `04.30`, `05.27`, `06.21`, `07.20`, `12.21`, `14.28`, and `17.20`.
- Conviction 8 derives from `01.3.1` and `01` non-violable rule 2.
- Conviction 9 derives from `17.23`, `18.27`, and `19` non-violable rules 22 and 23.

---

## 3. Constitutional Interpretation Register

### 3.1 Purpose

The Constitutional Interpretation Register is the authoritative record of ambiguities, internal inconsistencies, and unallocated matters within the ratified constitutional text that carry construction consequence.

It exists because the alternative is worse. In the absence of a register, engineers encountering ambiguity resolve it by fiat, inconsistently, at scale, and without record. Six teams meeting the same ambiguity produce six incompatible readings, each embedded in shipped code, each defensible, and none authoritative. The register replaces distributed silent resolution with centralized explicit resolution.

The register is a construction artifact that exercises a constitutional mechanism. `15.19` establishes Constitutional Interpretation as "the authoritative resolution of ambiguity, contradiction, or gap within the constitutional text," graded G1 through G4 by scope. The register is the queue that feeds that mechanism from the construction side.

### 3.2 Architectural Responsibilities

The register is responsible for:

- Recording every identified constitutional ambiguity with sufficient precision that the Governance Gateway can rule on it.
- Classifying each entry by severity, by the construction stage it blocks, and by the authority class competent to resolve it.
- Preventing construction from proceeding past a blocking entry until resolution is obtained.
- Distinguishing matters requiring constitutional interpretation from matters requiring an Architecture Decision Record from matters requiring only engineering judgment.
- Preserving the resolution and its lineage once obtained, so that the resolution is not re-litigated.
- Remaining live for the duration of construction and beyond.

### 3.3 Architectural Constraints

- **The register records; it does not resolve.** No entry may be closed by the Chief Implementation Architect, by an engineering team, or by any Architecture Decision Record where the entry is classified as requiring constitutional interpretation. Only the authority class named in the entry may close it.
- **Blocking entries block.** Where an entry is marked as blocking a construction stage, that stage does not begin. Construction proceeds on non-blocked stages.
- **No entry may propose an amendment.** The register records ambiguity in existing text. Where resolution requires the text to change rather than be clarified, the matter leaves the register and enters the Evolution Gateway's amendment process under `19.13`.
- **Silence is not resolution.** An entry that receives no response escalates under `15.28.4`, which specifies that escalation timeout escalates further rather than ratifying by default.

### 3.4 Component Relationships

| Register classification | Resolving authority | Constitutional basis |
|---|---|---|
| Constitutional Interpretation | Governance Gateway, G1–G4 by scope | `15.19` |
| Constitutional Amendment | Evolution Gateway packaging, Governance Gateway A4 ratification | `19.13`, `15.20`–`15.21` |
| Architecture Decision Record | Lead Architect within constitutional bounds | `01.9.2` |
| Engineering Judgment | Implementing team | Ordinary construction |

### 3.5 The Register

Entries are ordered by severity. Severity reflects construction consequence, not constitutional gravity.

---

#### CIR-001 — Technology naming conflict between `03_TECH_STACK` and `17`, `18`, `19`

| Field | Value |
|---|---|
| **Classification** | Constitutional Interpretation |
| **Severity** | Critical |
| **Authority Required** | G3 or G4 |
| **Blocks** | Construction of Integration, Deployment, and Evolution subsystems |

**Statement of ambiguity.** `19` non-violable rule 22 provides: "No constitutional document, policy, or governance artifact may reference a specific implementation technology, provider, or substrate operator." `17` non-violable rule 21 and `18` non-violable rule 18 state materially equivalent prohibitions with respect to external providers and substrate operators respectively.

`03_TECH_STACK` is a ratified constitutional document, classified "Implementation Specification — Binding on All Implementation Work," which names approximately fifty specific technologies as mandatory and approximately ten as prohibited.

**Construction consequence.** Under a literal reading, a ratified constitutional document violates three non-violable rules. Every implementation decision citing `03` inherits the ambiguity. The portability guarantees of `17.23`, the substrate independence guarantees of `18.27`, and the provider-neutrality obligations of `19.24.5` all depend on how the prohibition is scoped.

**Candidate readings available to the resolving authority.** That the prohibition governs capability abstractions and governance artifacts rather than the approved-toolkit specification; that `03`'s classification as an Implementation Specification distinguishes it from the constitutional documents the rule addresses; that the prohibition is prospective and `03` is grandfathered; that the conflict is genuine and requires amendment. **This document expresses no preference among them.**

---

#### CIR-002 — Direct service call prohibition versus specified synchronous interfaces

| Field | Value |
|---|---|
| **Classification** | Constitutional Interpretation |
| **Severity** | High |
| **Authority Required** | G3 |
| **Blocks** | Stage S1 (Trust) — determines inter-service transport architecture |

**Statement of ambiguity.** `02` Appendix A rule 1 provides: "No Direct Service Calls: All inter-service communication via Event Bus or API Gateway." `03` lists "Direct service-to-service HTTP calls" among prohibited patterns with the corrective "Event Bus or API Gateway."

`02.3.2` specifies Agent Runtime outbound interfaces as "Memory Gateway (gRPC), LLM Router (HTTP), Tool Registry (HTTP), Event Bus (Redis Streams)." `02.1.1` provides that "direct service-to-service HTTP calls are prohibited except for health probes." `02.3.5` provides that the Memory Gateway's inbound interface is "gRPC (internal), HTTP (for debugging)."

**Construction consequence.** If all Gateway mediation must be event-mediated, the ratified authorization latency budgets of `12.22.1` (p50 20ms) and `17.21.1` (p50 20ms) are unattainable. If synchronous Gateway calls are permitted, Appendix A rule 1 requires a scope that the text does not state. The resolution determines the entire inter-service transport architecture and therefore cannot be deferred.

**Candidate readings available to the resolving authority.** That the prohibition governs inter-module business coupling and event notification while Gateway mediation is a permitted control-plane call; that Gateways are not "services" within the meaning of the rule; that the `02.3.x` interface specifications are the controlling text and Appendix A is a summary; that the conflict is genuine. **This document expresses no preference among them.**

---

#### CIR-003 — Data ownership allocation is incomplete

| Field | Value |
|---|---|
| **Classification** | Architecture Decision Record |
| **Severity** | High |
| **Authority Required** | Lead Architect |
| **Blocks** | Stage S4 (Cognition) |

**Statement of gap.** `02.7.1` enumerates six databases under a Database-Per-Module strategy. `01.7.2` establishes Database Per Module as a non-violable principle prohibiting cross-module queries. Documents `09` through `19` introduce approximately eight further data-owning subsystems for which no storage is allocated.

**Construction consequence.** Absent explicit allocation, teams will co-locate new subsystems within existing databases and create precisely the hidden coupling `01.7.2` forbids. Section 10 of this document proposes an allocation; that proposal requires ADR ratification before Stage S4.

---

#### CIR-004 — Composite latency budget is unallocated

| Field | Value |
|---|---|
| **Classification** | Engineering Judgment, bounded by constitutional budgets |
| **Severity** | High |
| **Authority Required** | Lead Architect |
| **Blocks** | None; must be published before Stage S7 |

**Statement of gap.** Per-hop latency budgets are ratified across `07.22.1`, `11.28.1`, `12.22.1`, `16.31.1`, and `17.21.1`. The composite budget for a full mediation chain — Security, Decision, Cost Manager, Tool Gateway, Integration Gateway, sandbox preparation, output validation, with mandatory signal emission and multi-journal writes at each step — is not stated anywhere in the constitution.

**Construction consequence.** Summed conservatively, the chain approaches the `05.25.1` p99 budget of ten seconds for a simple agent task before inference occurs. Teams encountering the budget will be tempted to skip mediation hops, and each skipped hop is a Category 1 incident.

**Available mitigations within constitutional bounds.** Authorization caching bounded by token time-to-live with revocation broadcast, expressly permitted by `14.10.4`; co-location of the hot mediation path; asynchronous journal writes where synchronous durability is not constitutionally required; approval pre-clearance during workflow Planning under `07.12.6`.

---

#### CIR-005 — `security/` and `observability/` as shared libraries versus Gateways

| Field | Value |
|---|---|
| **Classification** | Constitutional Interpretation |
| **Severity** | Medium |
| **Authority Required** | G2 |
| **Blocks** | Stage S1 repository layout |

**Statement of ambiguity.** `02.14` places `security/` and `observability/` under `src/` as shared libraries with utility submodules. `14` and `16` define the Security Gateway and Observability Gateway as mediation authorities with registries, journals, identity, and sole-mediation topology. A shared library linked into a caller's process cannot be a mediation boundary, because the caller can bypass it.

**Construction consequence.** Determines whether the Security and Observability Gateways are deployable services, and therefore whether the `02.14` repository entries are superseded, supplemented, or reinterpreted. Section 8 proposes supplementation.

---

#### CIR-006 — Panic Protocol five-second bound lacks a specified scope of "halt"

| Field | Value |
|---|---|
| **Classification** | Constitutional Interpretation |
| **Severity** | Medium |
| **Authority Required** | G3 |
| **Blocks** | None; must be resolved before Stage S8 |

**Statement of ambiguity.** Eleven documents require the Panic Protocol to halt all autonomous activity within five seconds of invocation. The constitution does not specify whether "halt" means cessation of new work admission, cessation of in-flight work, acknowledged cessation, or observed cessation; nor whether the five seconds bounds invocation-to-broadcast, invocation-to-acknowledgment, or invocation-to-quiescence.

**Construction consequence.** The distinction is the difference between a broadcast guarantee and a distributed hard-real-time guarantee spanning twenty components, active tool sandboxes, in-flight external provider calls, and durable workflows. The two have materially different architectures.

---

#### CIR-007 — Confidence derivation rules across four subsystems are unspecified

| Field | Value |
|---|---|
| **Classification** | Engineering Judgment, bounded by constitutional thresholds |
| **Severity** | Medium |
| **Authority Required** | Lead Architect |
| **Blocks** | None; must be published before Stage S5 |

**Statement of gap.** `11.13.2` provides that decision confidence "propagates from the confidence of supporting canonical beliefs, adjusted for option quality, risk exposure, and temporal relevance." `15.13.2` and `13.13.1` state analogous derivations. No document specifies the derivation function.

**Construction consequence.** Four subsystems apply different confidence bands to values derived from one another by unspecified means. A miscalibration in Knowledge propagates silently into commitment, oversight, and adaptation.

---

#### CIR-008 — Oversight and adaptation resource consumption versus the fifteen percent cap

| Field | Value |
|---|---|
| **Classification** | Constitutional Interpretation |
| **Severity** | Medium |
| **Authority Required** | G3 |
| **Blocks** | None; must be resolved before Stage S10 |

**Statement of ambiguity.** `04.32` and `05.24.3` cap continuous improvement at fifteen percent of system resources. `13.20`, `15.14.4`, `16.31`, and `19.35` each establish independent resource consumption and circuit breakers for Learning, Governance, Observability, and Evolution respectively. Whether the fifteen percent cap bounds the aggregate of these four planes, bounds only Learning and Evolution, or bounds only explicitly improvement-classified activity, is not stated.

---

#### CIR-009 — Documentation structure divergence

| Field | Value |
|---|---|
| **Classification** | Engineering Judgment |
| **Severity** | Low |
| **Authority Required** | Implementing team |
| **Blocks** | None |

**Statement of gap.** `02.14` lists `docs/architecture/` as containing a seven-document series (`01_PRINCIPLES` through `07_DEPLOYMENT`) that does not correspond to the ratified nineteen-document series. Reconciliation is clerical.

---

### 3.6 Guarantees

The register guarantees:

1. **No silent resolution.** Every identified ambiguity with construction consequence is recorded before it is encountered by an implementing team.
2. **Single authoritative reading.** Once resolved, an entry's resolution is binding on all modules, preventing divergent readings across teams.
3. **Enforced blocking.** Construction does not proceed past an unresolved blocking entry, so no shipped module embeds an unresolved constitutional question.
4. **Preserved lineage.** Each resolution carries its evidence, authority, and date, so that future stewards can reconstruct why the reading was adopted.
5. **Liveness.** The register remains open. Entries discovered during construction are added, not absorbed.

### 3.7 Interaction with the Constitution

The register exercises `15.19` Constitutional Interpretation from the construction side. It does not create a new governance mechanism; it feeds an existing one.

Entries classified as requiring interpretation enter the Governance Gateway lifecycle at `15.7.1` Trigger, specifically as "a detected policy contradiction" or "a human steward inquiry." They proceed through Evidence Assembly, Assessment, Interpretation, Authority Resolution, and Ratification, and their resolutions are recorded as governance artifacts with the immutability and lineage guarantees of `15.8.3` and `15.19.4`.

Entries whose resolution would functionally alter constitutional meaning rather than clarify its application exceed interpretation authority under `15.19.2` and must proceed as amendments through `19.13`.

---

## 4. Architectural Layers & Planes

### 4.1 Purpose

This section defines the structural coordinate system within which every module resides. It exists so that illegal dependencies are visible as structural violations rather than discoverable only by reading code, and so that any engineer can determine, from a module's position alone, what it may depend upon and what may depend upon it.

The model distinguishes **layers**, which are ordered by dependency depth, from **planes**, which are cross-cutting and consumed by modules at many depths. The distinction matters because four constitutional subsystems — Security, Cost, Oversight, Territory — are simultaneously deep dependencies and universal consumers, and a purely layered model cannot express that.

### 4.2 Architectural Responsibilities

The layer and plane model is responsible for:

- Assigning every module a unique structural position.
- Establishing the direction of permitted dependency.
- Establishing the mechanism of permitted lateral coordination.
- Making prohibited edges structurally identifiable and therefore tooling-detectable.
- Providing the ordering from which build sequencing is derived.

### 4.3 Architectural Constraints

**4.3.1 The Downward Dependency Rule.** A module may hold a hard dependency only on modules in layers below it, and on planes. It may not depend upward. It may not depend laterally within its own layer.

**4.3.2 The Lateral Coordination Rule.** Coordination between modules in the same layer occurs exclusively through the Event Bus. This is the structural expression of `02` Appendix A rule 1, `06` non-violable rules 9 and 20, and `08` non-violable rule 16.

**4.3.3 The Plane Access Rule.** Planes are consumable from any layer. Planes do not depend on layers above their own construction depth. A plane that consumed the layers it serves would invert the dependency and reintroduce the cycles Section 1.2 of the Planning Package resolves.

**4.3.4 The No-Bypass Rule.** Position does not confer bypass. A module at Layer 6 may consume the Trust Plane, but it consumes it through the Security Gateway's mediation, not by reaching into the Security Gateway's data or internals.

**4.3.5 Placement is constitutional, not convenient.** A module's layer is determined by its constitutional dependency set, not by team ownership, deployment topology, or construction preference.

### 4.4 Component Relationships

#### 4.4.1 The Layer Stack

```
LAYER 6   ADAPTATION        learning_gateway · evolution_gateway
LAYER 5   EXECUTION         agent_runtime · workflow_engine
LAYER 4   EFFECT            tool_registry · tool_gateway · tool_executor
                            integration_registry · integration_gateway · llm_router
LAYER 3   AUTHORITY         decision_gateway
LAYER 2   COGNITION         memory_gateway · knowledge_gateway
LAYER 1   TRUTH             event_bus
LAYER 0   SUBSTRATE         kernel · core · persistence · schema_registry
```

#### 4.4.2 The Planes

| Plane | Modules | Consumed by | Constitutional basis |
|---|---|---|---|
| **Trust Plane** | `security_gateway` | All layers, all planes | `14.6.1` — sole source of truth for who may act |
| **Economic Plane** | `cost_manager` | Layers 3–6, Integration, Deployment | `02.3.9`; consumed by `11.14.4`, `12.23`, `13.20`, `17.22`, `18.31` |
| **Oversight Plane** | `observability_gateway` · `governance_gateway` | All layers | `16` rule 1 mandatory emission; `15.22` meta-oversight |
| **Territory Plane** | `deployment_registry` · `deployment_gateway` | All layers at runtime | `18.6.2` — sole path between operational intent and environmental existence |

#### 4.4.3 The Edge Layer

The Edge Layer sits above Layer 6 and mediates all interaction between Agent OS and human operators or external clients.

| Module | Constitutional basis |
|---|---|
| `api_gateway` | `02.3.1` |
| `human_interface` | Distributed across `05.18`, `11.18`, `13.33`, `16.25`, `17.31`, `18.35`, `19.36`. **Implementation component realizing constitutional requirements; not a constitutional subsystem.** |
| `plugin_manager` | `02.3.10`, `01.18.2` |

#### 4.4.4 Plane Construction Depth

Planes are consumable from any layer but are themselves constructed at defined depths, because a plane cannot serve what it has not yet been built to serve.

| Plane | Construction depth | Reason |
|---|---|---|
| Trust | Immediately above Layer 0 | Event Bus requires authenticated producers per `08` rules 1 and 14 |
| Economic | Above Layer 1 | Requires identity and event emission; required by Layer 3 |
| Oversight — ingestion profile | Above Layer 1 | `16` rule 1 forbids any subsystem shipping without signal emission |
| Oversight — interpretive profile | Above Layer 6 | Health models require signals from subsystems that do not yet exist at lower depth |
| Territory | Above Layer 6 | Governs environments; its absence does not block construction. Bootstrapped third at runtime per `18.33.2` |

### 4.5 Guarantees

The model guarantees:

1. **Acyclic hard dependency.** The Downward Dependency Rule combined with the Plane Access Rule admits no cycle in the hard-dependency graph.
2. **Structural visibility of violation.** Any dependency that is upward, lateral, or bypassing is identifiable from module position alone and is therefore detectable by tooling.
3. **Derivable build order.** The layer ordering plus plane construction depths yield the construction sequence directly.
4. **Uniform mediation.** Every cross-module interaction is a Gateway call, an event, or an API Gateway ingress, with no fourth category.
5. **Stable placement.** A module's layer does not change with team structure, deployment topology, or schedule.

### 4.6 Interaction with the Constitution

The model is a structural restatement of constitutional provisions, not an addition to them.

The Downward Dependency Rule realizes `01.4.1` modularity ("no module may import private internals of another module") and its non-violable prohibition on circular dependencies. The Lateral Coordination Rule realizes the Event Bus exclusivity of `08.6.1` and `06.13.5`. The Plane Access Rule realizes the sole-mediation topology each Gateway declares. The No-Bypass Rule realizes the eleven prohibited-edge provisions catalogued in Section 9.

Layer assignments derive directly from constitutional dependency statements: `decision_gateway` sits at Layer 3 because `11.12.1` requires grounding in canonical beliefs; `tool_gateway` sits at Layer 4 because `12` rule 2 requires a valid decision record; `evolution_gateway` sits at Layer 6 because `19` depends on confirmed learning, Governance ratification, experimental environments, and capability abstractions.

---

## 5. The Gateway Pattern

### 5.1 Purpose

This section specifies the Gateway Pattern: the universal implementation primitive from which all eleven constitutional Gateways are constructed.

It exists because the constitution defines eleven subsystems that are structurally identical and semantically distinct. Each declares the same twelve architectural elements and differs only in what it mediates. Implementing them independently would produce eleven interpretations of each shared element, and the constitution's uniformity — its greatest conformance asset — would be lost in construction.

The Gateway Pattern converts that uniformity into a reusable primitive. It is the mechanism by which conformance-by-construction is achieved.

### 5.2 Architectural Responsibilities

The Gateway Pattern specifies nine mechanisms. Every constitutional Gateway implements all nine. No constitutional Gateway implements any of them independently.

**5.2.1 Mediation Contract.**

Every Gateway is the sole path between its producers and its consumers. Producers submit artifacts for formation; consumers submit queries for retrieval; the Gateway mediates both. Producers may not write to consumers directly. Consumers may not read the substrate directly. No participant may self-certify.

The mediation contract specifies: the admission interface by which producers submit, the retrieval interface by which consumers query, the rejection semantics for inadmissible submissions, and the prohibition on any path that circumvents either interface.

**5.2.2 Artifact Identity.**

Every Gateway assigns and maintains identity for the artifacts it mediates. The identity shape is uniform: a unique, non-reusable, non-reassignable identifier; a hierarchical type classification; a schema version; an authoritative timestamp distinct from processing time; an authenticated source identity; tenant, business, and workspace isolation identifiers; a lineage reference; and where the subsystem grades by evidence, a confidence score.

Identity persists for the statutory retention period regardless of the artifact's disposition. Anonymous and pseudonymous artifacts are inadmissible at every Gateway without exception.

**5.2.3 Lifecycle State Machine.**

Every Gateway governs its artifacts through a finite state machine with four properties drawn from `04.22.3`: deterministic, observable, guarded, and compensatable where compensation is possible.

Transitions are event-driven and guarded by preconditions. Guard failures do not silently drop; they emit a denial with reasons. Side effects are executed by downstream consumers of transition events, not inline with the transition, keeping the state machine pure. Transition events are append-only; a correcting transition is appended, never substituted.

Each Gateway supplies its own state set and guard predicates. The engine that evaluates them is common.

**5.2.4 Boundary Enforcement.**

Every Gateway enforces six boundaries at every operation:

| Boundary | Question enforced |
|---|---|
| Tenant | Does this operation cross an isolation boundary without bilateral human approval? |
| Scope | Does this operation exceed the business, workspace, or subsystem scope of its actor? |
| Authority | Does the actor's autonomy or authority class permit this operation? |
| Confidence | Does the artifact meet the confidence threshold for its class and its consumer? |
| Budget | Does the Economic Plane confirm sufficient allocation? |
| Temporal | Are validity windows, delegations, and tokens unexpired? |

Enforcement occurs at the point of action, not at admission only. A long-running operation re-verifies.

**5.2.5 Confidence and Authority Resolution.**

Where a Gateway grades artifacts by evidentiary strength, it resolves the required authority from the artifact's class, its risk, and its confidence, and it escalates rather than proceeding when confidence falls below the threshold for the class.

The band values differ per subsystem — Knowledge, Decision, Governance, Learning, and Evolution each publish their own. The resolution logic is common: classify, threshold, compare, and on failure escalate or quarantine. Suppression of a low-confidence warning is prohibited at every Gateway.

**5.2.6 Immutable Journal.**

Every Gateway maintains an append-only, tamper-evident journal of every artifact lifecycle and every mediated operation, retained a minimum of seven years, cryptographically bound to its predecessor entries.

No runtime entity modifies, deletes, or retroactively alters a journal entry. Corrections append. The journal is the substrate of forensic reconstruction: for any artifact, it answers what was done, by whom, under what authority, on what evidence, and with what result.

**5.2.7 Signal Emission.**

Every Gateway emits mandatory signals to the Oversight Plane: metrics at intervals, events at state transitions, journal entries at decision points, and traces across operation boundaries. Emission is an obligation, not an option. `16` non-violable rule 1 admits no exemption.

Each Gateway publishes a signal contract declaring what it emits, at what cadence, and with what classification. The Oversight Plane validates emission against that contract and treats absence as a coverage anomaly.

**5.2.8 Self-Audit.**

Every Gateway continuously audits its own operation: boundary enforcement accuracy, journal completeness, transition guard integrity, confidence distribution, and drift from its own historical behaviour. Self-audit results are themselves artifacts, journaled and emitted.

Self-audit does not substitute for Governance meta-oversight. `15.6.1` provides that no subsystem may self-certify its constitutional compliance. Self-audit produces evidence; Governance adjudicates it.

**5.2.9 Panic Participation.**

Every Gateway implements the Panic Protocol contract: on invocation, cease admission of new operations, quiesce or suspend in-flight operations according to its subsystem's constitutional disposition, acknowledge, and remain halted until a human operator resumes.

Panic participation is fail-closed. A Gateway that cannot confirm its halt state treats itself as unsafe and refuses admission.

### 5.3 Architectural Constraints

- **All nine mechanisms, always.** A Gateway that omits any of the nine is not a Gateway. There is no partial implementation and no exemption by subsystem size, risk, or maturity.
- **Specialization, not reimplementation.** A Gateway supplies its state set, guard predicates, classification taxonomy, confidence bands, boundary parameters, and signal contract. It does not supply its own state machine engine, boundary evaluator, journal writer, or Panic handler.
- **No Gateway grants itself authority.** Authority is resolved against the Trust Plane. A Gateway that could authorize its own operations would violate the self-approval prohibition of `14.17.5`.
- **No Gateway is a library.** A mediation boundary that a caller can link into its own process is a boundary the caller can bypass. Mediation requires a boundary the caller cannot cross unmediated. (The transport by which this is realized is bound by CIR-002.)
- **No Gateway mutates another Gateway's substrate.** Cross-Gateway interaction is mediated by the target Gateway, exactly as consumer interaction is.
- **Gateway self-modification is bounded.** Every constitutional Gateway carries a bounded-improvement clause prohibiting it from evolving out of its own guarantees. The pattern encodes this: a Gateway's mechanisms are not runtime-mutable by the Gateway.

### 5.4 Component Relationships

#### 5.4.1 The Eleven Specializations

| Gateway | Mediates | Constitutional source |
|---|---|---|
| Security Gateway | Identity, permission, isolation, secrets | `14` |
| Memory Gateway | Organizational experience across four tiers | `09` |
| Knowledge Gateway | Validated belief, ontology, contradiction | `10` |
| Decision Gateway | Commitment to action | `11` |
| Tool Gateway | External effect authorization | `12` |
| Learning Gateway | Improvement proposal and propagation | `13` |
| Governance Gateway | Constitutional legitimacy and policy | `15` |
| Observability Gateway | Signal interpretation and disclosure | `16` |
| Integration Gateway | External capability relationships | `17` |
| Deployment Gateway | Operational territory | `18` |
| Evolution Gateway | Structural and constitutional change | `19` |

#### 5.4.2 Components That Are Not Gateways

Four constitutional components are frequently mistaken for Gateways and are not.

| Component | What it is | Why not a Gateway |
|---|---|---|
| Event Bus | A hub | Producers and consumers are decoupled by it, but it does not authorize, grade, or adjudicate. It routes on metadata and never on content (`08.17.1`). |
| API Gateway | External ingress | Mediates the boundary between external clients and the system, not between producers and consumers of a constitutional artifact class. |
| Registries (Tool, Integration, Deployment) | Canonical inventories | `12.6.1`, `17.6.1`, and `18.6.1` each state the Registry "does not execute… it governs their existence." The Registry is the Gateway's inventory, not a second mediation boundary. |
| Tool Executor | Dispatch and sandbox management | `12.6.3` — "receives instructions from the Gateway; it does not evaluate authority or make policy decisions." |

#### 5.4.3 The Chained Mediation Path

A single agent tool invocation traverses multiple Gateways in sequence. Each applies its own nine mechanisms:

```
agent_runtime
  → Security Gateway        authenticate, authorize, issue context
  → Decision Gateway        verify committed decision of matching authority
  → Cost Manager            budget pre-check
  → Tool Gateway            contract validation, capability match, invocation contract
  → Integration Gateway     capability abstraction resolution, provider health
  → Tool Executor           sandbox preparation, secret injection, dispatch
  ← output validation, cost attribution, journal writes, signal emission at every step
```

This chain is the origin of CIR-004. Its composite budget is an engineering obligation of Part IV.

### 5.5 Guarantees

The Gateway Pattern guarantees:

1. **Uniform enforcement.** Boundary evaluation, guard evaluation, journal writing, signal emission, and Panic behaviour are identical across all eleven Gateways because all eleven share one implementation.
2. **Single point of correction.** A defect in boundary enforcement is fixed once and corrected everywhere, rather than being fixed in one Gateway and persisting in ten.
3. **Structural non-bypass.** Because mediation is a boundary rather than a library, bypass requires circumventing the transport rather than merely declining to call a function.
4. **Complete attribution.** Every mediated operation carries authenticated source identity, isolation context, lineage, and journal record, because the pattern admits no unattributed operation.
5. **Predictable extension.** A twelfth Gateway, should one ever be constitutionally ratified, is a specialization rather than a new architecture.
6. **Conformance testability.** The pattern's nine mechanisms are testable once as a conformance suite and applied to all eleven Gateways.

### 5.6 Interaction with the Constitution

The Gateway Pattern introduces nothing. It is the factored common denominator of architecture the constitution states eleven times.

Each of the nine mechanisms is drawn from provisions repeated in every Gateway document: mediation from each subsystem's Architecture & Topology section; identity from each Identity section; lifecycle from each States & Transitions section; boundary enforcement from each Boundary Enforcement subsection; confidence resolution from each Confidence & Uncertainty section; journal from each Auditability section; signal emission from `16` non-violable rule 1 read against every subsystem's Observability section; self-audit from each Governance & Oversight section; Panic participation from the eleven documents that mandate it.

The pattern is an implementation construct. It has no constitutional standing, creates no constitutional obligation, and confers no authority. Where the pattern and a constitutional provision differ, the provision governs and the pattern is corrected.

---

## 6. The Constitutional Kernel

### 6.1 Purpose

The Constitutional Kernel is the shared implementation library that realizes the Gateway Pattern and the mechanisms the constitution states repeatedly across subsystems.

**The Kernel is an implementation artifact. It is not a constitutional subsystem.** It holds no authority, mediates no artifact class, owns no constitutional responsibility, and appears nowhere in Documents 01 through 19. It exists solely so that the mechanisms the constitution requires eleven times are implemented once.

This distinction is load-bearing and is restated wherever the Kernel appears. A future reader must not mistake the Kernel for a twelfth Gateway or infer constitutional standing from its centrality.

### 6.2 Architectural Responsibilities

The Kernel provides ten capabilities.

**6.2.1 Constitutional Artifact Primitive.** The common identity shape declared by all eleven Gateways: identifier, type, schema version, authoritative timestamp, authenticated source identity, tenant/business/workspace isolation identifiers, lineage reference, confidence score, and disposition. Provides construction, validation, serialization, and the non-reuse and non-reassignment guarantees.

**6.2.2 Lifecycle State Machine Engine.** Deterministic, observable, guarded, compensatable transition evaluation. Consumes a Gateway-supplied state set and guard predicate set. Emits transition events. Enforces append-only transition history and the prohibition on retroactive alteration.

**6.2.3 Boundary Enforcement Engine.** Uniform evaluation of the six boundaries in §5.2.4 against a supplied operation and security context. Produces an allow, deny, or escalate outcome with reasons. Never produces a silent pass.

**6.2.4 Immutable Journal.** Single append-only write path with a single tamper-evidence scheme, predecessor binding, retention policy engine, and tiered archival. Serves every Gateway's journal specialization. This is the system's dominant write path and is designed and budgeted as such.

**6.2.5 Confidence and Authority Resolution.** Classification, thresholding, comparison, escalation, and quarantine, parameterized by Gateway-supplied bands. Includes the derivation and propagation rules governed by CIR-007 once resolved.

**6.2.6 Failure Classification.** The five-category taxonomy — Transient, Degradable, Critical, Security, Financial — with the sixty-second classification bound, the prohibition on silent failure, and the rule that an unclassified failure is treated as critical.

**6.2.7 Panic Protocol Participation.** The halt contract, out-of-band control channel client, pre-armed halt state, acknowledgment protocol, and fail-closed semantics. Every Gateway inherits Panic compliance rather than implementing it.

**6.2.8 Signal Emission Contract.** The mandatory emission obligation, contract declaration, cadence management, and classification inheritance. Ensures no module can ship without emission.

**6.2.9 Category 1 Incident Pipeline.** The uniform escalation path for non-violable rule violations: immediate blocking, evidence preservation, principal suspension where applicable, human sovereign alert, and incident record formation.

**6.2.10 Isolation Context Propagation.** Creation, propagation, validation, and drop-prohibition for the security context that accompanies every operation across every boundary, per `14.24`.

### 6.3 Architectural Constraints

**6.3.1 The Kernel holds no domain logic.** It provides mechanism, never meaning. It knows what a guarded transition is; it does not know what "Canonical" means in the Knowledge Gateway or what "Committed" means in the Decision Gateway.

**6.3.2 The Kernel holds no authority.** It evaluates boundaries against a context supplied by the Trust Plane. It does not decide who may act. A Kernel that decided authority would become a mediation boundary and therefore a Gateway, which it is not.

**6.3.3 The Kernel is not a bypass.** No module may use Kernel capabilities to reach another module's substrate. The Kernel provides the journal writer; it does not provide access to another Gateway's journal.

**6.3.4 The Kernel imports no framework.** Per `01.7.1`, the Kernel is domain-layer code. It defines ports; adapters live in `persistence` and in each service.

**6.3.5 Kernel changes are constitutional-adjacent.** Because all eleven Gateways inherit conformance from the Kernel, a Kernel defect is a system-wide conformance defect. Kernel changes require Architecture Decision Record approval, full conformance suite passage, and — where they affect a mechanism named in a non-violable rule — Governance review.

**6.3.6 The Kernel is versioned with lineage.** Running Gateways continue on the Kernel version they were built against; new construction uses the latest. This mirrors the version lineage discipline every constitutional subsystem applies to itself.

### 6.4 Component Relationships

| Kernel capability | Consumed by | Constitutional obligation realized |
|---|---|---|
| Artifact Primitive | All 11 Gateways | Identity sections of `09`–`19` |
| Lifecycle Engine | All 11 Gateways | `04.22`; States & Transitions of `09`–`19` |
| Boundary Enforcement | All 11 Gateways | Boundary Enforcement subsections of `09`–`19` |
| Immutable Journal | All 11 Gateways, Event Bus audit stream | Auditability sections of `09`–`19` |
| Confidence Resolution | Knowledge, Decision, Governance, Learning, Evolution | `10.14.2`, `11.13.4`, `15.13.4`, `13.13.3`, `19.15.3` |
| Failure Classification | All modules | `04.30`, `05.27`, `06.21`, `07.20`, `12.21`, `14.28`, `17.20` |
| Panic Participation | All modules | Eleven documents |
| Signal Emission | All modules | `16` rule 1 |
| Incident Pipeline | All modules | Category 1 provisions throughout |
| Context Propagation | All modules | `14.24` |

The Kernel depends only on `core` (shared models and schemas) and defines ports satisfied by `persistence`. It depends on no Gateway and no plane. It is the deepest module in the system.

### 6.5 Guarantees

The Kernel guarantees:

1. **Single implementation of shared mechanism.** Ten mechanisms the constitution states repeatedly exist once in code.
2. **Inherited conformance.** A Gateway constructed on the Kernel is boundary-enforcing, journaling, signal-emitting, failure-classifying, and Panic-compliant by construction.
3. **Uniform correction.** A conformance defect corrected in the Kernel is corrected in every Gateway simultaneously.
4. **Testable foundation.** The Kernel conformance suite tests the ten mechanisms once; Gateway suites test only specialization.
5. **No hidden authority.** The Kernel cannot authorize, cannot bypass, and cannot become a mediation boundary, because it holds no domain logic and no authority.
6. **Explicit non-constitutional standing.** The Kernel is labelled an implementation artifact at every appearance, foreclosing future misreading.

### 6.6 Interaction with the Constitution

The Kernel realizes constitutional obligations; it does not create them. Every capability traces to provisions stated in multiple constitutional documents, and the Kernel exists precisely because those provisions are stated multiply and identically.

The Kernel has no standing under `15` Governance: it is not a subsystem, holds no stewardship, and forms no governance artifacts. It has no standing under `19` Evolution: changes to it are structural refinements within existing constitutional constraints, not capability extensions or amendments — unless a proposed change would alter a mechanism named in a non-violable rule, in which case the change is not a Kernel change but an amendment, and proceeds accordingly.

Where the Kernel's implementation of a mechanism and the constitutional statement of that mechanism differ, the constitution governs and the Kernel is defective.

---
---

# PART II — STRUCTURE

---

## 7. Module Hierarchy & Boundaries

### 7.1 Purpose

This section enumerates every module in Agent OS with its constitutional provenance, its layer or plane, its ownership boundary, and its dependency set. It exists so that the system's full construction surface is explicit, assignable, and traceable, and so that no module is created without constitutional warrant.

### 7.2 Architectural Responsibilities

The module hierarchy is responsible for:

- Enumerating the complete set of modules with no omission and no addition.
- Attributing each module to the constitutional provision that requires it.
- Assigning each module a layer or plane position.
- Declaring each module's ownership boundary — what it owns exclusively and what it may not touch.
- Distinguishing deployable components from shared libraries.
- Identifying the two implementation artifacts that lack constitutional subsystem standing.

### 7.3 Architectural Constraints

- **No module without provenance.** Every module traces to a named constitutional provision. A module that cannot be traced does not exist.
- **No responsibility reallocation.** Module boundaries realize constitutional responsibility allocation exactly.
- **Exclusive ownership.** Each module owns its data, its journal, its state machine, and its interfaces exclusively. Nothing is co-owned.
- **Constitutional naming.** Module names use ratified constitutional terminology. The two exceptions — `kernel` and `human_interface` — are marked at every occurrence.
- **Registry-Gateway pairing preserved.** Where the constitution separates a Registry from a Gateway (`12`, `17`, `18`), the implementation preserves the separation. The Registry governs existence; the Gateway mediates operation.

### 7.4 Component Relationships

#### 7.4.1 The Module Register

**Layer 0 — Substrate**

| Module | Type | Constitutional provenance |
|---|---|---|
| `kernel` | Shared library | **Implementation artifact.** Realizes mechanisms of `09`–`19`. No constitutional standing. |
| `core` | Shared library | `02.14` — shared domain models, event schemas, exceptions, constants |
| `persistence` | Shared library | `01.7.1` hexagonal adapters; `02.7` data architecture |
| `schema_registry` | Deployable | `08.16.1`, `10.16.2`, `12.7.3` |

**Trust Plane**

| Module | Type | Constitutional provenance |
|---|---|---|
| `security_gateway` | Deployable | `14` in full |

**Layer 1 — Truth**

| Module | Type | Constitutional provenance |
|---|---|---|
| `event_bus` | Deployable + client library | `08` in full; `02.3.4` |

**Economic Plane**

| Module | Type | Constitutional provenance |
|---|---|---|
| `cost_manager` | Deployable | `02.3.9`; consumed by `11.14.4`, `12.23`, `13.20`, `17.22`, `18.31` |

**Layer 2 — Cognition**

| Module | Type | Constitutional provenance |
|---|---|---|
| `memory_gateway` | Deployable | `09` in full; `02.3.5` |
| `knowledge_gateway` | Deployable | `10` in full |

**Layer 3 — Authority**

| Module | Type | Constitutional provenance |
|---|---|---|
| `decision_gateway` | Deployable | `11` in full |

**Layer 4 — Effect**

| Module | Type | Constitutional provenance |
|---|---|---|
| `tool_registry` | Deployable | `12.6.1`; `02.3.6` |
| `tool_gateway` | Deployable | `12.6.2` |
| `tool_executor` | Deployable | `12.6.3`; `02.3.7` |
| `integration_registry` | Deployable | `17.6.1` |
| `integration_gateway` | Deployable | `17.6.2`; includes the Abstraction Layer of `17.6.3` |
| `llm_router` | Deployable | `02.3.8`; prompt pipeline of `02.8.5` |

**Layer 5 — Execution**

| Module | Type | Constitutional provenance |
|---|---|---|
| `agent_runtime` | Deployable | `05`, `06`; `02.3.2` |
| `workflow_engine` | Deployable | `07` in full; `02.3.3` |

**Layer 6 — Adaptation**

| Module | Type | Constitutional provenance |
|---|---|---|
| `learning_gateway` | Deployable | `13` in full |
| `evolution_gateway` | Deployable | `19` in full |

**Oversight Plane**

| Module | Type | Constitutional provenance |
|---|---|---|
| `observability_gateway` | Deployable | `16` in full; supersedes `02.3.11` Monitoring in scope |
| `governance_gateway` | Deployable | `15` in full |

**Territory Plane**

| Module | Type | Constitutional provenance |
|---|---|---|
| `deployment_registry` | Deployable | `18.6.1` |
| `deployment_gateway` | Deployable | `18.6.2`; includes the Environment Abstraction Layer of `18.6.3` |

**Edge Layer**

| Module | Type | Constitutional provenance |
|---|---|---|
| `api_gateway` | Deployable | `02.3.1` |
| `human_interface` | Deployable | **Implementation artifact.** Realizes `05.18`, `11.18`, `13.33`, `16.25`, `17.31`, `18.35`, `19.36`. No constitutional subsystem standing. |
| `plugin_manager` | Deployable | `02.3.10`; `01.18.2` |

**Total: 26 modules — 22 deployable components and 4 shared libraries.**

#### 7.4.2 Ownership Boundaries

Each module owns exclusively:

- Its **domain model** — entities, value objects, state set, guard predicates.
- Its **data** — the schemas or databases allocated in Section 10.
- Its **journal** — its specialization of the Kernel journal.
- Its **interfaces** — the contracts it exposes, versioned and documented.
- Its **signal contract** — what it emits to the Oversight Plane.
- Its **migrations** — its own Alembic environment.
- Its **runbook** — per `01.9.3`, mandatory before production.

No module may read or write another module's data store, import another module's domain layer, or invoke another module's internals.

#### 7.4.3 Boundary Enforcement Mechanisms

| Boundary | Enforced by |
|---|---|
| Import boundary | Static analysis in continuous integration; domain layers declare no cross-module imports |
| Data boundary | Distinct credentials per module; no module holds credentials for another's store |
| Interface boundary | Contract tests; consumers declare expectations, producers verify |
| Layer boundary | Dependency graph validation against §4 |
| Mediation boundary | Transport topology (bound by CIR-002) |

### 7.5 Guarantees

The module hierarchy guarantees:

1. **Complete enumeration.** Twenty-six modules constitute the entire construction surface. No unlisted module is authorized.
2. **Full traceability.** Every module cites the provision requiring it.
3. **Exclusive ownership.** Every element of the system has exactly one owning module.
4. **Assignability.** Each module is independently assignable to a team with a complete, bounded specification.
5. **Detectable violation.** Ownership and layer violations are detectable by tooling rather than by review.
6. **Preserved constitutional separation.** Registry-Gateway separations and Executor-Gateway separations survive construction.

### 7.6 Interaction with the Constitution

The hierarchy realizes the union of the component sets defined by `02.1.3` and by the Gateway architecture of `09` through `19`. Where `02` named a component, its name and responsibility are preserved. Where `09`–`19` introduced a Gateway after `02` was ratified, a module is added.

Two additions carry no constitutional subsystem standing and are marked throughout: `kernel`, which factors repeated mechanism, and `human_interface`, which consolidates human-plane requirements stated in seven documents without a single named home. Neither creates constitutional obligation, and neither may be cited as constitutional authority.

`02.3.11` Monitoring is realized by `observability_gateway`, which `16` defines with materially greater scope. The responsibility is not moved; it is expanded by a later constitutional document, and the implementation follows the later document.

---

## 8. Repository Architecture

### 8.1 Purpose

This section specifies the physical organization of Agent OS source, documentation, definitions, and infrastructure. It exists so that every engineer has one canonical answer to where code lives, and so that the repository structure itself communicates the layer, plane, and ownership model.

### 8.2 Architectural Responsibilities

The repository architecture is responsible for:

- Preserving the ratified repository structure of `02.14` without relocation or renaming.
- Extending that structure to accommodate the eleven modules introduced by Documents 09 through 19 and the two implementation artifacts.
- Specifying a single per-service internal convention realizing hexagonal architecture.
- Housing non-code constitutional artifacts: agent definitions, tool manifests, integration manifests, deployment manifests, workflow definitions.
- Maintaining the monorepo discipline required by `03.27.1`.

### 8.3 Architectural Constraints

**8.3.1 The ratified structure is preserved exactly.** `02.14` is constitutional. Every directory it names retains its name, its position, and its purpose. This document adds; it does not move, rename, or remove.

**8.3.2 Monorepo, independently packaged.** Per `03.27.1`, all services, agents, tools, documentation, and infrastructure reside in a single repository enabling atomic cross-component change. Per `03.5.1`, each service is an independent package with its own manifest and lock file.

**8.3.3 Hexagonal internal structure is uniform.** Every service directory follows one convention, so that an engineer moving between services encounters the same shape.

**8.3.4 Definitions are not code.** Agent manifests, tool manifests, integration manifests, and deployment manifests are constitutional artifacts residing outside `src/`, per the `02.14` treatment of `agents/` and `tools/`.

**8.3.5 The bilingual boundary is explicit.** Workflow definitions and activity implementations occupy distinct, clearly separated locations, because they are governed by distinct non-violable language rules.

### 8.4 Component Relationships

#### 8.4.1 Preserved from `02.14`

Top level: `README.md`, `LICENSE`, `docker-compose.yml`, `docker-compose.prod.yml`, `Makefile`, `.github/`, `docs/`, `infrastructure/`, `src/`, `agents/`, `tools/`, `plugins/`, `migrations/`, `scripts/`, `tests/`.

Within `src/`: `gateway/`, `agent_runtime/`, `workflow_engine/`, `event_bus/`, `memory_gateway/`, `tool_registry/`, `tool_executor/`, `llm_router/`, `cost_manager/`, `plugin_manager/`, `core/`, `security/`, `observability/`.

Per-service: package manifest, `src/`, `tests/`.

#### 8.4.2 Additions to `src/`

| Directory | Module | Basis for addition |
|---|---|---|
| `kernel/` | Constitutional Kernel | Implementation artifact; §6 |
| `persistence/` | Persistence adapters | `01.7.1` domain isolation |
| `schema_registry/` | Schema Registry | `08.16.1` |
| `security_gateway/` | Security Gateway | `14`; supplements `security/` per CIR-005 |
| `knowledge_gateway/` | Knowledge Gateway | `10` |
| `decision_gateway/` | Decision Gateway | `11` |
| `tool_gateway/` | Tool Gateway | `12.6.2` — the Gateway `12` introduces between Registry and Executor |
| `integration_registry/`, `integration_gateway/` | Integration subsystem | `17.6.1`, `17.6.2` |
| `learning_gateway/` | Learning Gateway | `13` |
| `governance_gateway/` | Governance Gateway | `15` |
| `observability_gateway/` | Observability Gateway | `16`; supplements `observability/` per CIR-005 |
| `deployment_registry/`, `deployment_gateway/` | Deployment subsystem | `18.6.1`, `18.6.2` |
| `evolution_gateway/` | Evolution Gateway | `19` |
| `human_interface/` | Human Interface | Implementation artifact; §7.4.1 |

`security/` and `observability/` are retained as ratified, as client libraries consumed by all modules. Their relationship to the corresponding Gateway services is bound by CIR-005.

#### 8.4.3 Per-Service Internal Convention

Every service directory contains, beneath its package root:

| Subdirectory | Contents | Constraint |
|---|---|---|
| `domain/` | Entities, value objects, state set, guard predicates, invariants | Imports no framework, no ORM, no client library, no transport (`01.7.1`) |
| `ports/` | Interfaces the domain requires of the outside world | Declares; never implements |
| `adapters/` | Concrete implementations of ports | The only place infrastructure libraries appear |
| `api/` | Transport surface and schema exposure | Thin; delegates to domain |
| `journal/` | The service's Kernel journal specialization | Append-only; no mutation path exists |
| `signals/` | The service's mandatory emission contract | Declared, versioned, validated by the Oversight Plane |
| `tests/` | Unit, integration, contract, property | Per `01.14` and `03.19` |

#### 8.4.4 Non-Code Constitutional Artifacts

| Directory | Contents | Basis |
|---|---|---|
| `agents/` | Agent manifests, prompt templates, output schemas, deterministic logic modules | `02.14`, `02.4.1`, `06.5` |
| `tools/` | Tool manifests, schemas, sandbox definitions | `02.14`, `12.7.1` |
| `integrations/` | Integration manifests, capability abstractions, provider contracts | `17.7.1` — **added** |
| `deployments/` | Environment manifests, sovereignty declarations, fault domain assignments | `18.8.2` — **added** |
| `workflows/` | Workflow definitions in the mandated workflow language | `03.3.2`, `07` — **added**; distinct from `src/workflow_engine/` which hosts activities and orchestration services |
| `policies/` | Policy hierarchy artifacts by layer | `15.16.1` — **added** |
| `plugins/` | Third-party plugins, installed not committed | `02.14` |

#### 8.4.5 Documentation and Operations

| Directory | Contents | Basis |
|---|---|---|
| `docs/architecture/` | Constitutional Documents 01–19, Manifests 20A–20C, this document and its parts, ADRs | `01.9.1`, `01.9.2`; reconciles CIR-009 |
| `docs/runbooks/` | One runbook per production service | `01.9.3` — mandatory before production |
| `docs/development/` | Setup, testing, contribution | `02.14` |
| `migrations/` | One environment per data-owning module | `03.6.4`; allocation per §10 |
| `tests/` | End-to-end, integration, contract, chaos, **conformance** | `01.14`, `03.19`; conformance suite added per §2.2.2 |

### 8.5 Guarantees

The repository architecture guarantees:

1. **Constitutional preservation.** Every `02.14` element retains name, position, and purpose.
2. **Complete housing.** All twenty-six modules and all constitutional artifact classes have a canonical location.
3. **Uniform navigation.** Any service can be navigated by an engineer familiar with any other service.
4. **Structural hexagonality.** The domain layer's isolation is enforced by directory structure and import analysis, not by convention.
5. **Atomic cross-component change.** Monorepo discipline permits a single change to span a schema, its producers, and its consumers.
6. **Definition-code separation.** Constitutional artifacts remain distinguishable from the code that consumes them.

### 8.6 Interaction with the Constitution

The architecture extends `02.14`, which is ratified and preserved. Additions are made where Documents 09 through 19 introduced subsystems after `02.14` was written and no directory exists for them — a gap to be filled, not an inconsistency to be resolved.

The `security/` and `observability/` question is registered as CIR-005 and is not decided here. Section 8.4.2 proposes supplementation rather than replacement, on the basis that `02.14` is ratified text; the proposal awaits G2 interpretation.

`docs/architecture/` is reconciled to the actual constitutional series under CIR-009, which is clerical and requires no interpretation.

---

## 9. Interface Contracts & Communication Model

### 9.1 Purpose

This section specifies how modules communicate. It exists because the prohibited-edge catalogue of the constitution is only enforceable if the permitted edges are precisely defined, and because the constitution states communication prohibitions in eleven places without consolidating them.

### 9.2 Architectural Responsibilities

The communication model is responsible for:

- Defining the permitted communication modes and admitting no fourth.
- Specifying the contract discipline governing each mode.
- Consolidating every prohibited edge stated across the constitution.
- Specifying versioning, compatibility, and deprecation for inter-module contracts.
- Specifying degraded-mode contracts satisfying local-first operability.
- Specifying the bilingual contract discipline across the workflow language boundary.

### 9.3 Architectural Constraints

**9.3.1 Three modes only.** All inter-module communication occurs through Gateway mediation, event emission, or API Gateway ingress. There is no fourth mode. Direct module-to-module invocation, shared memory, shared database access, and side channels are prohibited without exception.

**9.3.2 Transport binding is deferred.** The transport realizing Gateway mediation is bound by CIR-002 and is not specified here. What is specified — the mediation semantics, the contract discipline, the prohibition on bypass — holds regardless of how CIR-002 resolves.

**9.3.3 Contracts are versioned and typed.** Every interface carries a schema version. Every payload is validated at both boundaries. Consumers ignore unknown fields; producers do not remove fields without deprecation.

**9.3.4 Contracts are tested, not asserted.** Consumer-driven contract tests are required at every module boundary and at the workflow language boundary. An untested contract is an assumed contract.

**9.3.5 Degraded modes are contractual.** Every interface crossing an external boundary declares its degraded-mode behaviour. Absence of a declared degraded mode is a conformance failure under `01` non-violable rule 2.

### 9.4 Component Relationships

#### 9.4.1 Mode One — Gateway Mediation

The synchronous control-plane mode. A consumer submits an operation to a Gateway; the Gateway applies its nine mechanisms and returns an outcome.

| Property | Specification |
|---|---|
| Direction | Consumer to Gateway; Gateway returns outcome |
| Semantics | Request-outcome, not request-response of arbitrary data |
| Idempotency | Every mutating operation carries an idempotency key |
| Context | Security context accompanies every operation and may not be dropped (`14.24.5`) |
| Authorization | Evaluated at the Gateway, at the point of action |
| Journaling | Every operation journaled by the Gateway |
| Failure | Classified within sixty seconds; never silent |
| Latency | Per the ratified per-hop budgets; composite budget per CIR-004 |

Used for: authorization, memory access, knowledge query, decision commitment, tool invocation, integration consumption, learning propagation, governance ruling, environmental validation.

#### 9.4.2 Mode Two — Event Emission

The asynchronous decoupled mode. A producer emits a fact; consumers subscribing to the relevant stream receive it.

| Property | Specification |
|---|---|
| Direction | Producer to hub; hub to subscribed consumer groups |
| Semantics | Immutable fact publication; never a command to a named recipient (`08.2.2`) |
| Delivery | At-least-once; idempotency is the consumer's responsibility (`08.17.2`) |
| Ordering | Total within a stream; no global order across streams (`08.13`) |
| Causality | Correlation and causation identifiers propagated without break (`08.12.3`) |
| Schema | Registered before emission; unregistered types rejected (`08.16.1`) |
| Routing | Metadata only; content-based routing prohibited (`08.17.1`) |
| Atomicity | Emission atomic with state transition (`07.18.3`) |

Used for: all lateral coordination, all inter-agent communication, all state transition notification, all lifecycle announcement, all anomaly propagation.

#### 9.4.3 Mode Three — API Gateway Ingress

The external boundary mode. No external client communicates with any internal module except through the API Gateway.

| Property | Specification |
|---|---|
| Direction | External client to API Gateway to internal module |
| Authentication | Delegated to the Trust Plane |
| Authorization | Delegated to the Trust Plane |
| Rate limiting | Per tenant, per user, per key (`02.3.1`) |
| Versioning | URI path (`03.29.2`) |
| Documentation | Schema-generated; no endpoint without documentation and example (`01.9.4`) |
| Pagination | Cursor-based; offset-based prohibited (`03` rule 23) |
| Idempotency | Mutating endpoints accept an idempotency key (`03` rule 24) |

Used for: human operator interaction, external client integration, dashboard, command-line tooling, webhook reception.

#### 9.4.4 The Consolidated Prohibited-Edge Catalogue

| # | Prohibited edge | Constitutional basis |
|---|---|---|
| 1 | Module to another module's database | `01.7.2`, `02` App. A rule 1 |
| 2 | Module to another module's domain internals | `01.4.1` |
| 3 | Agent to agent, directly | `06` rules 9, 20; `04` rule (Communication Rules) |
| 4 | Producer to consumer, for events | `08` rule 16 |
| 5 | Consumer to Tool Executor, bypassing Tool Gateway | `12` rule 11 |
| 6 | Tool to tool, directly | `12` rule 17 |
| 7 | Consumer to external provider, bypassing Integration Gateway | `17` rule 11 |
| 8 | Integration to integration, directly | `17` rule 17 |
| 9 | Runtime to substrate, bypassing Deployment Gateway | `18` rule 8 |
| 10 | Principal to resource, bypassing Security Gateway | `14` rule 11 |
| 11 | Learning to target subsystem, bypassing target Gateway | `13` rule 2 |
| 12 | Evolution to constitution, bypassing Governance | `19` rule 2 |
| 13 | Any producer to any Gateway substrate, bypassing the Gateway | Mediation contract, `09`–`19` |
| 14 | Any subsystem self-certifying its compliance | `15.6.1` |

#### 9.4.5 The Bilingual Contract Boundary

`03.3.2` requires workflow definitions in the mandated workflow language; `03.3.1` requires business logic in the mandated service language. Activities are therefore implemented in one language and orchestrated in another.

Neither language's type checker observes both sides. The boundary is governed by:

- **Single-source schema.** Workflow context, activity input, activity output, and compensation contracts are generated from `core` schemas into both languages. Hand-authored duplicates are prohibited.
- **Mandatory contract tests.** Every activity contract is exercised from the orchestration side in continuous integration.
- **Version pinning.** A running workflow continues on the contract version it started with (`07.4.3`).
- **Conformance gate.** Boundary contract coverage is a completion criterion for `workflow_engine`.

#### 9.4.6 Contract Evolution

| Change | Requirement |
|---|---|
| Additive field | Minor version; consumers unaffected |
| Field removal | Major version; deprecation of at least one release cycle (`08.16.2`) |
| Semantic change | Major version; migration plan; ADR |
| Breaking change | Prohibited without migration path (`01` rule 20) |
| Contract retirement | Notice period, identified successor, migration plan |

### 9.5 Guarantees

The communication model guarantees:

1. **Three modes, no fourth.** Every interaction is classifiable, and unclassifiable interaction is detectable.
2. **Complete prohibition coverage.** Fourteen prohibited edges consolidated from eleven documents, each traced, each enforceable.
3. **Unbroken attribution.** Every mediated operation and every event carries authenticated identity, isolation context, and causal lineage.
4. **Contract integrity across languages.** The bilingual boundary is single-sourced and tested rather than assumed.
5. **Backward compatibility.** No consumer breaks without deprecation and migration.
6. **Local-first survivability.** Every external-boundary interface declares degraded behaviour, so core operation survives disconnection.

### 9.6 Interaction with the Constitution

The model consolidates communication provisions stated across eleven documents. It adds no prohibition and relaxes none.

Mode One realizes the sole-mediation topology every Gateway declares. Mode Two realizes `08` in full, including the fact metaphor, at-least-once delivery, causal fidelity, and metadata-only routing. Mode Three realizes `02.3.1` and `01.4.3` API-First Design.

The transport realizing Mode One is bound by CIR-002. Until that entry is resolved, Mode One's semantics are specified and its transport is not. No module may be constructed against an assumed resolution.

---

## 10. Data Ownership & Persistence Architecture

### 10.1 Purpose

This section allocates data ownership across all modules and specifies the persistence tiers, migration ownership, and retention architecture. It exists because Database Per Module is a non-violable principle for which the constitution provides an incomplete allocation, and because the journal architecture is the system's dominant write path and must be designed deliberately.

### 10.2 Architectural Responsibilities

This section is responsible for:

- Allocating exclusive data ownership to every data-owning module.
- Specifying the persistence tiers and which classes of data occupy each.
- Specifying migration ownership and isolation.
- Specifying the journal persistence architecture as a distinct concern.
- Specifying retention and archival tiering against the constitutional retention schedule.
- Specifying tenant scoping as a structural property of every stored record.

### 10.3 Architectural Constraints

**10.3.1 Database Per Module is absolute.** `01.7.2` and `02.7.1` prohibit cross-module queries. A module reads and writes only what it owns. Aggregation across modules occurs through events or Gateway mediation, never through a join.

**10.3.2 Ownership is exclusive and singular.** Every stored record has exactly one owning module. Co-ownership does not exist.

**10.3.3 Tenant scoping is structural.** Every record carries a tenant identifier. Scoping is enforced at the persistence adapter layer, not by query convention, so that an unscoped query is impossible rather than merely discouraged. This holds while deployed single-tenant.

**10.3.4 Journals are append-only at the storage layer.** The immutability guarantee is enforced by the storage contract, not by application discipline. No mutation path exists to a journal record.

**10.3.5 Allocation model awaits ADR.** The specific allocation below is proposed under CIR-003 and requires ADR ratification before Stage S4.

**10.3.6 Domain layers know no persistence.** Per `01.7.1`, storage technology appears only in adapters.

### 10.4 Component Relationships

#### 10.4.1 Persistence Tiers

The constitution describes five functional tiers. Modules consume tiers through ports; the technology satisfying each tier is an adapter concern.

| Tier | Function | Constitutional basis |
|---|---|---|
| Working | Active execution context; high velocity, low latency; durable against process loss | `09.7.1` |
| Structured | Validated, committed, queryable organizational record | `09.7.2`, `02.7.1` |
| Semantic | Associative and similarity retrieval | `09.7.3`, `02.6.4` |
| Graph | Relational traversal and inference | `10.17`, `02.6.5` |
| Cold | Archival, compliance, long-term analysis | `09.7.4`, `02.7.4` |
| Stream | Ordered, append-only, durable event log | `08.6.2` |

#### 10.4.2 Data Ownership Matrix

Allocation follows the constitutional enumeration of `02.7.1` where one exists, and extends it for subsystems introduced afterward. Each data-owning module receives an exclusive schema boundary.

| Module | Owns | Tiers consumed | Constitutional basis |
|---|---|---|---|
| `security_gateway` | Identity Registry, permission graphs, delegations, revocation lists, credential and secret metadata, Security Event Journal | Structured, Working, Cold | `14.4.2`, `14.12.2`, `14.26` |
| `event_bus` | Stream log, consumer group positions, dead-letter stream, event archive index | Stream, Cold | `08.6.2`, `08.14.3`, `08.15.4` |
| `schema_registry` | Event schemas, artifact schemas, version lineage | Structured | `08.16.1` |
| `cost_manager` | Cost ledger, budget allocations, circuit breaker state | Structured | `02.7.1` (`aos_analytics`), `02.3.9` |
| `memory_gateway` | Working memory, memory entries across four tiers, lineage, relationship edges | All | `09.7`, `02.7.1` (`aos_memory`) |
| `knowledge_gateway` | Knowledge entries, ontology, knowledge graph, contradiction records, provenance | Structured, Semantic, Graph, Cold | `10.17`, `10.18.4` |
| `decision_gateway` | Decision records, options, evidence references, standing orders, Decision Journal | Structured, Cold | `11.23`, `02.7.1` (`aos_approval`) |
| `tool_registry` | Tool manifests, capability signatures, trust scores, version lineage | Structured | `12.6.1`, `02.7.5` |
| `tool_gateway` | Invocation contracts, Invocation Records, selection bindings | Structured, Cold | `12.17`, `12.26.1` |
| `tool_executor` | Sandbox execution records, artifact references | Working, Cold | `12.6.3` |
| `integration_registry` | Integration manifests, capability abstractions, provider provenance, trust scores | Structured | `17.6.1` |
| `integration_gateway` | Provider contracts, Consumption Records, health history | Structured, Cold | `17.16`, `17.25.1` |
| `llm_router` | Model tier configuration, semantic and exact cache, token accounting | Working, Semantic | `02.8`, `02.8.7` |
| `agent_runtime` | Agent Registry, reputation scores, execution records, heartbeat state | Structured, Working | `06.3.2`, `02.7.1` (`aos_core`) |
| `workflow_engine` | Workflow state, execution DAGs, checkpoints, activity records, workflow definitions registry | Structured, Working, Cold | `07.9`, `02.7.1` (`aos_workflows`) |
| `learning_gateway` | Learning entries, patterns, Failure Library, measurement windows, Learning Journal | Structured, Semantic, Cold | `13.4`, `13.9` |
| `governance_gateway` | Policy hierarchy, governance artifacts, rulings, interpretations, stewardships, exceptions, Governance Journal | Structured, Cold | `15.16`, `15.27` |
| `observability_gateway` | Signals, health models, anomalies, evidence packages, coverage assessments, baselines | All | `16.28.2` |
| `deployment_registry` | Environment manifests, sovereignty declarations, fault domain assignments | Structured | `18.6.1` |
| `deployment_gateway` | Environment health, promotion records, continuity state, deployment audit trail | Structured, Cold | `18.30.1` |
| `evolution_gateway` | Evolutionary artifacts, amendments, experiments, lineage graph, Evolutionary Journal | Structured, Cold | `19.4`, `19.18` |
| `plugin_manager` | Plugin manifests, lifecycle state, capability declarations | Structured | `02.3.10` |
| `human_interface` | Approval queues, digest state, standing order configuration, disclosure preferences | Structured, Working | `11.18`, `16.25.3` |
| `api_gateway` | API keys, rate limit counters, request correlation | Working, Structured | `02.3.1` |

`kernel`, `core`, and `persistence` own no data. They provide mechanism.

#### 10.4.3 Journal Persistence

Journals are architecturally distinct from ordinary module data and are treated as such.

| Property | Specification |
|---|---|
| Write path | Single, provided by the Kernel |
| Mutability | None. Append-only enforced at the storage contract |
| Tamper evidence | Predecessor binding, uniform scheme across all journals |
| Retention | Minimum seven years for all journals; indefinite for constitutional compliance records (`16.28.2`) and rejected amendments (`19.17.4`) |
| Tiering | Hot for recent, warm for analytical, cold for compliance |
| Ownership | Each Gateway owns its journal exclusively; the Kernel owns the write mechanism |
| Query | Forensic reconstruction, Auditor role required for privileged queries (`14.26.4`) |
| Privacy | No secrets, credentials, or personally identifying information in any journal (`07` rule 22, `12.26.5`, `16` rule 4) |

The journal write path is the dominant write path in the system. Its capacity model, batching strategy, and durability semantics are specified in Part IV.

#### 10.4.4 Retention Schedule

Consolidated from the constitutional retention provisions.

| Class | Operational | Analytical | Compliance |
|---|---|---|---|
| Business, Agent events | 30 days | 2 years | 7 years |
| Workflow, Command events | 90 days | 2 years | 7 years |
| System events | 7 days | 90 days | 7 years |
| Audit events | 7 years | 7 years | 7 years |
| Atomic signals | 30 days granular | Summarized | — |
| Health models | 90 days full | Monthly snapshots | — |
| Anomaly records | — | 2 years | — |
| Evidence packages | — | — | 7 years |
| Constitutional compliance records | — | — | Indefinite |
| All Gateway journals | — | — | Minimum 7 years |

Sources: `08.15.4`, `16.28.2`, and the retention provisions of each Gateway document.

#### 10.4.5 Migration Ownership

Each data-owning module owns one migration environment. No migration crosses a module boundary. Migrations include forward and reverse operations. No schema change occurs without a migration; no manual schema modification occurs in any environment. Basis: `03.6.4`, `03` non-violable rule 8.

### 10.5 Guarantees

The persistence architecture guarantees:

1. **Complete allocation.** Every data-owning module has an exclusive boundary; no data is unowned or co-owned.
2. **Structural cross-module isolation.** Credential separation makes a cross-module query impossible rather than merely prohibited.
3. **Structural tenant scoping.** An unscoped query cannot be expressed through the adapter layer.
4. **Journal immutability at the storage layer.** No application defect can mutate a journal record, because no mutation path exists.
5. **Retention conformance.** Every record class has a declared retention aligned to the constitutional schedule.
6. **Migration isolation.** A migration defect is contained to one module.
7. **Technology replaceability.** Tiers are consumed through ports, preserving the substrate independence of `18.27`.

### 10.6 Interaction with the Constitution

The allocation realizes `01.7.2` Database Per Module and extends `02.7.1`, which enumerates six databases against a system that subsequently grew to twenty-four data-owning subsystems. The extension fills a gap; it alters no ratified allocation. `aos_core`, `aos_memory`, `aos_events`, `aos_workflows`, `aos_analytics`, and `aos_approval` retain their ratified purposes and are mapped to their owning modules above.

Tenant scoping realizes the isolation guarantees of `14.18`, `17.10.2`, and `18.11`, which are absolute and admit only bilateral human approval as exception. Enforcing them structurally while deployed single-tenant is required, because `02.17.4` states multi-tenancy is designed in and untested isolation is not isolation.

Journal architecture realizes the auditability provisions of all eleven Gateways plus `01.10.5`, which requires that audit logs never be modifiable by the system that generates them.

The specific allocation is registered as CIR-003 and requires ADR ratification before Stage S4.

---

## 11. State Management

### 11.1 Purpose

This section specifies where state lives, which state is durable, which is recoverable, which may be discarded, and how state is restored after failure. It exists because "no business-critical state exclusively in local memory" is a non-violable rule in four documents, and because state recoverability is the mechanism behind the constitution's continuity, rehydration, and replay guarantees.

### 11.2 Architectural Responsibilities

This section is responsible for:

- Classifying every category of state by durability obligation.
- Specifying rehydration for each class.
- Specifying the append-only correction model uniformly.
- Specifying security context propagation as a state discipline.
- Specifying the relationship between events as source of truth and state as derived projection.
- Specifying state boundaries at process, module, and environment level.

### 11.3 Architectural Constraints

**11.3.1 No business-critical state in local memory alone.** Stated as a non-violable rule in `01`, `06`, `07`, and `14`. Every business-critical value is recoverable after process termination.

**11.3.2 Agents are stateless between tasks.** `06.2.2` and `07.15.2`: an agent holds no memory of a workflow between activities; all state is externalized. Agent *identity* persists in the registry; agent *process* holds nothing.

**11.3.3 Events are the source of truth; state is a projection.** `08.2.5`: state can be derived from events but events cannot be derived from state. State corruption is repairable by replay; event corruption is not.

**11.3.4 Committed state is immutable.** Every Gateway declares a commitment point after which core identity, evidence, and payload are frozen. Correction appends a new artifact linked by lineage. No Gateway offers an update path past its commitment point.

**11.3.5 Security context is state that may not be dropped.** `14.24.5`: if context cannot be propagated, the operation halts until context is restored or re-authorized. Context loss is a failure, not a degradation.

**11.3.6 Workflow state is durable by definition.** `07.2.5`: a workflow's state is externalized, its progress recoverable, its logic deterministic. It trusts only the durable record.

### 11.4 Component Relationships

#### 11.4.1 State Classes

| Class | Definition | Durability | Rehydration | Examples |
|---|---|---|---|---|
| **Durable-Committed** | Constitutional artifacts past their commitment point | Permanent, immutable, journaled | Not applicable; never lost | Decision records, knowledge entries, security events, governance rulings |
| **Durable-Mutable** | Registry and configuration state that legitimately changes | Persistent, versioned, audited | From owning module's store | Agent Registry, permission graphs, tool manifests, policy hierarchy |
| **Durable-Progressive** | In-flight process state that must survive failure | Persistent, checkpointed | From durable checkpoint | Workflow state, saga position, measurement windows, learning cycles |
| **Ephemeral-Recoverable** | Working state whose loss degrades but does not destroy | Working tier; reconstructible | From durable sources | Agent execution context, assembled prompts, session state |
| **Ephemeral-Discardable** | Optimization state whose loss costs only recomputation | Working tier; no guarantee | Recomputed | Caches, rate limit counters, health check results |
| **Derived** | Projections computed from events or journals | Not authoritative | Replayed from events | Health models, cost dashboards, compliance scores, reputation scores |

#### 11.4.2 Rehydration Model

| Failure | Recovery mechanism | Constitutional basis |
|---|---|---|
| Agent process termination | Workflow reschedules; state rehydrated from Memory Gateway | `02.16.1`, `06.21.3` |
| Orchestrator failure | Workflow resumes from last checkpoint | `07.19.5`, `07.20.7` |
| Gateway restart | Durable state reloaded; ephemeral rebuilt; caches cold | Gateway reliability sections |
| Consumer failure | Unacknowledged events redelivered | `08.21.3` |
| Event Bus unavailability | Producers buffer with declared time-to-live; critical events to fallback durable queue | `02.16.2`, `08.21.2` |
| Derived state corruption | Replay from event log in sandboxed context | `08.15.2` |
| Environmental failure | Secondary environment activated; state restored from durable checkpoints | `18.20.2` |

#### 11.4.3 The Append-Only Correction Model

Uniform across every Gateway. When a committed artifact is found to be wrong:

1. The original is never modified, overwritten, or deleted.
2. A correcting artifact is formed with its own identity.
3. Lineage links the correction to the original.
4. The original transitions to a terminal disposition — Deprecated, Superseded, Reversed, or Refuted — according to its subsystem's state set.
5. Both remain in the journal permanently.

This model produces the constitution's forensic reconstruction guarantee: the system can always answer not only what it believes but what it used to believe and why that changed.

#### 11.4.4 State Boundaries

| Boundary | Rule |
|---|---|
| Process | No business-critical state survives only here |
| Module | State crosses module boundaries only through mediation or events, never through shared storage |
| Workspace, Business, Tenant | State does not cross without explicit grant; tenant crossing requires bilateral human approval |
| Environment | Runtime instance state does not migrate across deployment domains without Gateway-mediated re-authorization |

#### 11.4.5 Context Propagation as State

Security context accompanies every operation across every boundary: agent to tool, task to subtask, workflow step to step, event producer to consumer, memory query to response. It is created at authentication, immutable for the duration of a single operation, validated by every receiving component, and never modifiable by the principal it describes. Its loss halts the operation.

### 11.5 Guarantees

State management guarantees:

1. **No business-critical loss.** Every business-critical value survives process, service, and environmental failure.
2. **Deterministic rehydration.** Every state class has a specified recovery path.
3. **Repairable projections, irreparable facts.** Derived state is rebuildable from events; events and journals are never rebuilt because they are never lost.
4. **Immutable history.** No committed artifact is altered; correction appends.
5. **Uninterrupted attribution.** Security context accompanies every operation or the operation halts.
6. **Horizontal scalability.** Because agents and Gateways hold no business-critical local state, instances are addable and replaceable without coordination.

### 11.6 Interaction with the Constitution

The model realizes the state provisions distributed across the constitution. The prohibition on local-only business-critical state appears as a non-violable rule in `01`, `06`, `07`, and `14`. Agent statelessness with stateful memory is `01.6.2` and `06.2.2`. The event-as-truth relationship is `08.2.5`. Durable execution is `07.2.5`. Append-only correction is stated identically in `08.14.2`, `09.9.3`, `10.18.3`, `11.8.3`, `12.9.3`, `13.9.3`, `15.8.3`, and `19.8.3`. Context propagation and its drop prohibition are `14.24`.

The model adds no state class the constitution does not describe and relaxes no durability obligation it imposes.

---

## 12. Configuration Architecture

### 12.1 Purpose

This section specifies how Agent OS is configured: the hierarchy of configuration sources, their validation, their scoping, how secrets are referenced without being exposed, and how experimental capability is gated.

It exists because configuration is where the constitution's guarantees are most easily and most quietly broken. Local-first operability, secret non-exposure, tenant isolation, sovereignty tier, and geographic locality are all expressible as configuration, and all silently violable by a misconfigured value.

### 12.2 Architectural Responsibilities

This section is responsible for:

- Specifying the configuration hierarchy and precedence.
- Requiring validated, typed configuration with no untyped access.
- Specifying configuration scoping by tenant, business, workspace, and environment.
- Specifying secret referencing such that no secret value enters configuration.
- Specifying feature flag governance for experimental capability.
- Specifying the relationship between configuration and constitutionally significant declarations.

### 12.3 Architectural Constraints

**12.3.1 No secrets in configuration.** Configuration holds references, never values. Secret values are injected by the Trust Plane into execution environments at invocation time. Basis: `14.22.2`, `14` rule 12, `01` rule 12, `03` rule 3.

**12.3.2 No hardcoded environment-specific values.** No endpoint, path, credential, or environment-specific value appears in source. Basis: `01.8.6`.

**12.3.3 Configuration is typed and validated at startup.** No module reads untyped configuration. A module whose required configuration is absent or invalid fails to start rather than starting degraded. This is fail-safe default applied to configuration.

**12.3.4 Constitutionally significant configuration is not ordinary configuration.** Sovereignty tier, geographic locality, tenant identity, autonomy levels, risk tiers, and confidence thresholds are constitutional declarations that happen to be expressed as configuration. They are immutable once their owning artifact is Active and change only through the owning Gateway's amendment path — never through a configuration deployment.

**12.3.5 Feature flags default off.** No experimental feature reaches production without a flag, and no flag defaults on. Basis: `01.18.3`, `01` rule 21.

**12.3.6 Local-first configuration.** Every configuration set has a valid disconnected form. A configuration that cannot express a functioning disconnected system violates `01` non-violable rule 2.

### 12.4 Component Relationships

#### 12.4.1 Configuration Hierarchy

Later sources override earlier ones. All are validated together before a module accepts any.

| Precedence | Source | Contains | Mutability |
|---|---|---|---|
| 1 (lowest) | Module defaults | Safe, local-first, minimum-privilege defaults | Compile-time |
| 2 | Deployment environment manifest | Environmental invariants, sovereignty tier, geographic locality, fault domain, capacity | Immutable once Active (`18.8.3`) |
| 3 | Tenant configuration | Tenant identity, quotas, retention overrides within constitutional minima | Governed |
| 4 | Business configuration | Business identity, budgets, autonomy profile, mission reference | Governed |
| 5 | Workspace configuration | Workspace type, isolation level, agent population | Governed |
| 6 | Runtime configuration | Operational tuning within declared bounds | Operational |
| 7 (highest) | Feature flags | Experimental capability gating | Governed, default off |

#### 12.4.2 Configuration Classes

| Class | Character | Change path |
|---|---|---|
| **Constitutional Declaration** | Sovereignty tier, geographic locality, tenant identity, risk tier, autonomy level, confidence threshold | Owning Gateway's amendment or re-approval path only |
| **Governed Parameter** | Budgets, quotas, retention beyond constitutional minima, standing order bounds | Decision Gateway commitment at appropriate class |
| **Operational Parameter** | Pool sizes, timeouts within declared bounds, cadences, batch sizes | Operational change with audit |
| **Secret Reference** | Identifiers of credentials and keys | Trust Plane; reference only, never value |
| **Feature Flag** | Experimental gating | Evolution Gateway experimental framework (`19.22`) |

#### 12.4.3 Scoping

Configuration resolution proceeds from the most specific applicable scope outward. A workspace value overrides a business value, which overrides a tenant value, which overrides an environment default.

Scoping is enforced, not conventional: a module cannot read configuration outside its granted scope, and a tenant's configuration is not visible to another tenant under any resolution path.

#### 12.4.4 Secret Referencing

| Stage | Behaviour |
|---|---|
| Declaration | Configuration declares a secret by reference identifier |
| Resolution | The Trust Plane resolves the reference against scope, tool inventory, and permission |
| Injection | The value is injected into the execution environment at invocation time |
| Consumption | The consuming component receives the value only inside its sandbox |
| Exposure | The value never appears in configuration, logs, traces, journals, events, memory, or decision records |
| Rotation | Atomic: the new value is registered before the old is retired |

Modules receive references. Only the execution environment receives values. No module reads a secret value from configuration under any circumstance.

#### 12.4.5 Feature Flags and Experimental Capability

Feature flags gate capability that is not yet ratified for general operation. Under `19.22`, every experiment carries a hypothesis, scope boundary, time boundary, isolation guarantee, success criteria, failure thresholds, and rollback procedure.

Flags therefore carry an expiry. A flag past its time boundary is a governance finding, not a configuration artifact. Constitutional experiments are prohibited outright: no flag may disable a non-violable rule, a boundary, a journal, a signal contract, or Panic participation.

#### 12.4.6 Configuration Validation

At startup, every module validates: required values present, types and constraints satisfied, secret references resolvable within scope, environment manifest present and Active, scope grants sufficient, constitutional declarations internally consistent, and disconnected-mode configuration valid.

Any failure prevents startup. A module never starts in a partially configured state, because a partially configured Gateway cannot enforce a boundary, and an unenforced boundary that runs is a constitutional violation.

### 12.5 Guarantees

The configuration architecture guarantees:

1. **No secret exposure through configuration.** Configuration holds references only; values exist only inside execution environments.
2. **Startup-time conformance.** A module that could not enforce its boundaries does not start.
3. **Constitutional declaration protection.** Sovereignty tier, locality, tenant identity, autonomy, and risk tier cannot be altered by a configuration deployment.
4. **Scope isolation.** No module reads outside its scope; no tenant's configuration is visible to another.
5. **Experimental containment.** No experimental capability runs without a flag, a scope, a time boundary, and a rollback path; none may disable a constitutional guarantee.
6. **Disconnected validity.** Every configuration set expresses a functioning disconnected system.
7. **Environmental reproducibility.** Configuration is version-controlled, validated, and auditable, satisfying `01.4.6` Infrastructure as Code.

### 12.6 Interaction with the Constitution

The architecture realizes provisions distributed across the constitution. Secret non-exposure is `14.22.2` and non-violable in four documents. Prohibition on hardcoded environment-specific values is `01.8.6` and `03` rule 3. Environment manifest immutability is `18.8.3`. Feature flag discipline is `01.18.3` and `19.22`. Experimental isolation is `01.18.4`. Local-first configuration is `01.3.1` and `01` non-violable rule 2. Infrastructure as Code is `01.4.6` and `03.3.3`.

The distinction between Constitutional Declaration and ordinary configuration is not an addition. It restates, in configuration terms, the immutability that `18.8.3`, `17.9.3`, `12.9.3`, and the manifest provisions of `06.5.1` already impose. A value the constitution declares immutable does not become mutable by being expressed as configuration.

---
---

## Closure of Part A

Part A establishes the foundations and structure of the Agent OS implementation architecture: the fidelity posture under which construction proceeds, the philosophy governing it, the register of constitutional ambiguities awaiting authoritative resolution, the layer and plane coordinate system, the Gateway Pattern as universal primitive, the Constitutional Kernel realizing it, the complete module hierarchy, the repository architecture housing it, the communication model binding it, the data ownership allocating it, the state model preserving it, and the configuration architecture parameterizing it.

Three entries in the Constitutional Interpretation Register block construction and require resolution by authorities other than the Chief Implementation Architect. **CIR-001** blocks Integration, Deployment, and Evolution. **CIR-002** blocks Stage S1 and the inter-service transport architecture. **CIR-003** blocks Stage S4 and requires ADR ratification of the data ownership allocation proposed in Section 10.

Part III (Subsystem Implementation Architectures), Part IV (Cross-Cutting Mechanisms), and Part V (Delivery) are not contained in this document.

Where this document is silent, the constitution governs. Where this document speaks on implementation structure, it is binding.

*End of Document*
