# Workflow Engine

**Stage:** S7 — First Light
**Realizes:** document 07 (`07_WORKFLOW_ORCHESTRATION`), per 21B §14
**Depends on:** Layer 0, Trust Plane, Decision Gateway, Cost Manager, Agent Runtime, Tool Platform

## Why it exists

`07.13.1`: **"The orchestrator does not perform work; it governs work."**

The engine owns scheduling and nothing else. It dispatches to the Agent
Runtime and the Tool Gateway, holds durable state across days-long approval
gates, and undoes what it must when a run cannot finish. It never infers,
never calls a model, never touches a substrate. A test asserts no `infer`,
`run_tool`, `hydrate`, or `call_model` verb has appeared on `WorkflowEngine`.

## Public interfaces (21B §14.5)

| Interface | Method |
|---|---|
| Definition Registration | `register_definition` |
| Workflow Trigger | `trigger` |
| Workflow Signal | `signal` |
| Workflow Query | `query` |
| Workflow Health | `health` |

`advance` is the tick that releases newly-eligible activities; `replay`
reconstructs a run's traversal from the journal.

## Planning is cheap and Running is expensive (21B §14.4)

`07.12.1` gives the reason: "A workflow that fails during Planning has not yet
consumed agent labor, LLM tokens, or external API calls."

So every failure mode detectable before execution is detected in Planning, and
a workflow that cannot succeed never enters Running:

* the DAG is built and validated (acyclicity, resolvable dependencies, agent
  activities that name a capability, tool activities that name a tool) — at
  **registration**, not at trigger, so an unbuildable definition is never
  registrable;
* budget is pre-allocated at **worst case**, including retries and
  compensation. Pre-allocating the optimistic cost would admit a workflow that
  cannot afford to finish, which is precisely the failure Planning exists to
  prevent;
* agents are bound to activities (not to workflows, per 21B §14.3), and a
  capability nobody holds fails Planning rather than stranding a run mid-flight.

A Planning failure goes straight to Failed. 21B §14.9 classifies it "Critical,
cheap" with "no compensation needed", because nothing was consumed.

## Human gates are first-class DAG nodes (21B §14.2)

A gate is an activity, not a side channel. That is what lets a workflow pause
durably on one. On reaching a gate the engine requests approval through the
Decision Gateway, records the decision id, sets `holds_resources = False`, and
transitions to Paused.

`07.14.5`: a paused workflow "consumes no compute quota while retaining
durable state". That is what makes a multi-day approval affordable, and
`health()` reports `paused_holding_resources` so a leak is visible rather than
merely expensive.

**A denied gate compensates.** It never proceeds on silence and never leaves a
completed mutating effect standing.

## Saga compensation

Compensations run in **reverse chronological order**, so an earlier activity is
never undone before a later one that depended on it.

**A failed compensation produces Stalled, not Failed.** 21B §14.9 classifies
it "Critical, unrecoverable", requiring human intervention. Marking such a run
Failed would abandon a half-undone world without telling anyone, so Stalled is
a distinct state, is journalled, emits a signal, and appears in `health()`.

A mutating activity with no invocation to compensate (an agent activity marked
mutating) is recorded as `compensation_unavailable` and stalls, rather than
being skipped silently.

## Determinism discipline (07.13.5)

The most easily violated constraint here. Non-deterministic inputs — current
time, random values, external readings — are injected as explicit workflow
variables and never derived inside orchestration logic. `Activity` carries no
clock; `WorkflowContext.variables` is where non-determinism lives. That is
what lets `replay` reconstruct the same traversal from the journal.

## The bilingual boundary (21A §9.4.5, 03.3.1/03.3.2)

Workflow definitions are authored in TypeScript; activity implementations are
Python. 21B §14.4 calls this **"the engine's highest-risk internal seam"**,
because neither language's type system observes both sides.

The countermeasure is single-source generation plus mandatory contract tests
in both directions:

* `workflow_engine/schema.py` is the single source of truth. `CONTRACTS` and
  `ENUMS` are declared once and `render_typescript()` emits
  `workflow_definitions/src/contracts.ts`.
* The Python contract suite includes
  `test_the_generated_file_matches_the_generator`. Without it, someone edits
  the generated file by hand, the two sides diverge silently, and the failure
  surfaces at runtime in a language neither type checker was watching.
* `workflow_definitions/test/` holds the TypeScript half, which catches a
  truncated or stale generation from the other direction, and `tsc --noEmit`
  runs under `strict`.
* The determinism checker lives in its own module (`src/determinism.ts`) so
  that listing the forbidden patterns does not trip the rule it enforces.

## The adapter convention

Cross-subsystem imports are confined to `adapters.py`, asserted by test. In
particular the adapter, not the engine, constructs the Runtime's
`ActivityRequest` — so `agent_runtime` is a name the engine never mentions.

## Open items

* **No real Temporal server.** Durability is in-process: the journal and the
  run records survive within the process, not across a restart. 03.3.1's
  named engine is binding since the CIR-001 ruling and is not adopted here: a
  recorded deviation.
* The Event Bus is not yet wired into the engine; signals reach Observability
  directly through the emitter.
* `holds_resources` is a flag the engine maintains rather than a quota the
  substrate enforces, since there is no substrate yet to release to.
