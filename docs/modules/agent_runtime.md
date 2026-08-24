# Agent Runtime

**Stage:** S7 — First Light
**Realizes:** documents 05 and 06, and the component responsibility of 02.3.2, per 21B §13
**Depends on:** Layer 0, Trust Plane, Memory, Knowledge, LLM Router, Tool Platform, Cost Manager

## Why it exists

`06.2.1` calls an agent "a persistent digital worker with an identity, a
specialty, a reputation, and a career trajectory". `02.3.2` says agents "are
not long-running processes. They are stateless workers that wake up in
response to workflow tasks."

Both are true, and the Runtime is where they are reconciled. It is split into
two planes, and the split is the module's central structural claim.

## The two planes (21B §13.4)

**The Identity Plane is durable.** Registry, manifest, reputation, drift
baseline, lifecycle state. `06.3.2`: "When an agent is not executing, its
identity remains active in the registry." An Idle, Suspended, Retired or
Archived agent exists entirely here.

**The Execution Plane is stateless.** A worker acquires identity, hydrates
state, assembles context, renders, infers, dispatches tools, validates output,
emits the result, and **returns to the pool holding nothing**. Every durable
consequence is written to the Identity Plane or emitted as a signal; nothing
survives in the worker.

Every step that crosses a module boundary goes through the owning Gateway. The
worker holds no credential, contacts no provider, and touches no substrate.

## Public interfaces (21B §13.5)

| Interface | Method |
|---|---|
| Activity Execution | `execute` |
| Agent Discovery | `discover` |
| Agent Registration | `register` |
| Lifecycle Command | `command` |
| Agent Health Query | `health_of` |

## Structural constraints

**The Runtime does not schedule.** `02.3.2`: "The Workflow Engine owns
scheduling; the Runtime owns execution." A test asserts that no `schedule`,
`enqueue`, `plan`, `trigger`, `retry` or `queue` verb has appeared on
`AgentRuntime`. This is checked structurally rather than documented, because a
docstring keeps claiming the separation long after the code has lost it.

**Registration is not availability.** A Registered agent is not assignable;
only an Idle one is. This mirrors the Tool Registry, where registration is not
authorization.

**The manifest is immutable once registered** (06.5.1). Behavioural change
requires a new version with resolvable lineage, never an edit, so
`AgentManifest` is frozen and `predecessor_agent_id` must name a registered
agent.

## The six authority boundaries (06.9.6)

An agent acts within the **intersection** of capability signature, tool
inventory, memory scope, autonomy level, cost budget, and workspace.
Intersection, not union, exactly as 14.12.4 requires everywhere else. Any one
boundary alone refuses the activity:

* an activity ceiling above the declared budget is refused before anything runs;
* a tool outside the registered inventory is refused (12.32.1 — the Runtime
  does not select tools beyond the inventory);
* hydration is passed the declared memory scope and never widens it;
* a cross-tenant token is refused.

## Separation of duties

06 rules 16 and 17: an agent may not review its own output. `ActivityRequest`
carries `reviews_output_of`, and the Runtime refuses the assignment rather
than relying on the caller to have checked.

## Output validation and suspension

No unvalidated output propagates (21B §13.15 guarantee 5). The Output
Validator checks every field in the manifest's declared contract for presence
and type; a violation fails the activity and increments the agent's violation
count. At `SCHEMA_VIOLATION_SUSPENSION_THRESHOLD` (3, an Engineering Decision
— 06.9.4 requires the threshold without publishing a figure) the agent is
suspended automatically and disappears from discovery.

## Degradation is explicit

21B §13.9: empty hydrated context or ungrounded inference sets `degraded` on
the outcome rather than passing silently. A degraded result that looked
identical to a grounded one would make the distinction unenforceable
downstream.

## Context assembly truncates

07.10.4: assembly composes within `max_context_tokens` and **truncates rather
than overflowing**. A budget that can be silently exceeded is not a budget.

## Reputation and drift

Reputation is recomputed from success rate after every execution and decays
after `REPUTATION_DECAY_IDLE` (30 days, Engineering Decision — 06.17 requires
decay without a figure), so a dormant agent does not keep stale standing.

The Drift Monitor measures deviation from an agent's **own** baseline in tool
usage, latency, and schema adherence, not from a population. 06.19.2 is
concerned with an agent changing, not with an agent differing from its peers.
The baseline moves exponentially, so one outlier does not reset it. Detected
drift is journalled and emitted as a signal.

## Engineering Decisions recorded here

| Constant | Value | What the docs require |
|---|---|---|
| `SCHEMA_VIOLATION_SUSPENSION_THRESHOLD` | 3 | 06.9.4 requires a threshold, names no number |
| `REPUTATION_DECAY_IDLE` / `_FRACTION` | 30 days / 5% | 06.17 requires decay, names no figure |
| `DriftMonitor.deviation_threshold` | 0.5 | 06.17.5 requires drift detection, names no threshold |
| `HEARTBEAT_CADENCE` / `STALL_MULTIPLIER` | 30s / 2x | 02.4.8 names cadence and stall detection qualitatively |

## Open items

* No sandbox runtime: tool bodies execute through the Tool Executor's
  in-process sandbox, not an isolated one.
* No real model backend: inference goes through the LLM Router to whatever
  backend is registered.
* The Event Bus is not yet wired into the Runtime; signals reach Observability
  directly through the emitter.
