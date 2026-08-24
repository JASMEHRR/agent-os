# Tool Platform — Registry, Gateway, Executor

**Stage:** S6 — Effect
**Realizes:** document 12 in full, plus 02.3.6 and 02.3.7, per 21B §19
**Depends on:** Layer 0, Trust, Event Bus, Decision, Cost Manager, Integration Gateway

## Why it exists

`12.2.1`: **"The tool is the constitutional airlock."** Agents reason,
workflows coordinate, decisions authorize, and tools execute. No agent,
workflow or decision may interact with the external world except through a
registered tool.

This is the system's primary attack surface, because it is the only path to
external effect.

## The three-module separation (12.6)

The separation is preserved absolutely, and each module has a test asserting
it has not eroded:

| Module | Governs | Never does |
|---|---|---|
| **Registry** | Existence | Dispatch (`invoke`/`execute` absent) |
| **Gateway** | Authorization | Execution |
| **Executor** | Fulfilment | Authority (`authorize`/`approve` absent) |

`12.6.3`: the Executor "receives instructions from the Gateway; it does not
evaluate authority or make policy decisions." That is why it is a separate
module — **policy and execution must not share a process**.

## Public interfaces (21B §19.5)

| Interface | Provider | Method |
|---|---|---|
| Tool Discovery | Registry | `discover` |
| Tool Registration | Registry | `register` |
| Tool Health Query | Registry | `health_of` |
| Tool Invocation | Gateway | `authorize` + `complete` |
| Compensation Invocation | Gateway | `compensate` |
| Invocation Record Query | Gateway | `query_records` |
| Tool Health Signals | All three | `health` |

## What is enforced structurally

**Registration is not authorization.** A tool in the Registry is discoverable;
only an Active tool is invocable. The Registry has no dispatch path at all.

**The verification sequence runs cheapest-first** (21B §19.4). Authenticity,
tenant, registration, autonomy, circuit breaker, decision, integration,
budget, input contract, sandbox. A request failing an early check consumes no
downstream resource, and the refusal names its gate.

**No execution without a committed decision** (12 rule 2). The Gateway calls
the Decision Gateway's `verify`, which is the interface 12 rule 2, 17 rule 2
and 18 rule 2 all point at.

**Sandbox escalation, never de-escalation** (12 rule 4). A request for a lower
tier than the manifest declares raises. In composition, 12.18.3 puts the whole
chain at the highest tier any member needs.

**The contract is recorded before dispatch** (21B §19.4), so an external
effect can never occur without a prior immutable record of its authorization.

**Both directions are untrusted.** Input is validated before the sandbox;
output before it returns. 12.25.4 is easy to miss — output is often assumed
safe because the tool was authorized — so unvalidated output is never
returned.

**Cleanup on every path** (guarantee 8). Sandbox destruction is in a
`finally`; `health()["sandboxes"]["leaked"]` is the standing check.

**Secrets reach the sandbox and nowhere else** (12 rule 5). The Executor
redeems a single-use Security Gateway grant into the sandbox environment. It
does so under **its own** Service identity — 14 rule 12 forbids a grant
reaching an agent at all, so passing the consuming agent would be refused,
correctly.

## Derived engineering targets

21B §19.12 publishes the full latency table from 12.22.1 (Registry query p50
50ms, Gateway authorization p50 20ms, sandbox preparation p50 100ms). Not
validated — everything is in-memory and no real sandbox runtime is wired in.

`[Engineering Decision]` figures: circuit breaker threshold and cooldown, the
autonomous trust threshold (0.5), and the per-tier resource limits.

## Open items

- **No real sandbox runtime.** `Sandbox` models the four tiers and enforces
  the egress allowlist and cleanup contract, but Docker, gVisor and
  Firecracker are not wired in. Sandbox *semantics* are implemented; sandbox
  *isolation* awaits the container runtime.
- **Integration backing resolves against the real Registry** since the CIR-001
  ruling. `RegistryIntegrationSource` authorizes a tool whose abstraction is
  backed by an active approved integration. `UnbackedIntegrationSource` is
  retained for the case it actually describes: a deployment with no registered
  integrations. See `docs/modules/integration_platform.md`.
- Timeout enforcement is checked after the tool returns rather than
  interrupting it mid-flight; real pre-emption needs the process isolation the
  runtime would provide.
- `event_bus` is not wired in for lifecycle emission (21B §19.6).
- Performance is unvalidated against §19.12.

## Test map

| Stage S6 required test | File |
|---|---|
| Registered tool executes in its declared tier | `tests/s6_integration/` |
| Under a committed decision, within its cost ceiling | `tests/s6_integration/` |
| Validated output, working compensation path | `tests/s6_integration/` |
| Gateway rejects attempts that bypass the Registry | `tests/s6_integration/` |
| Direct tool-to-tool invocation rejected | `tests/s6_integration/` |
| Registration, trust decay, lifecycle | `tool_registry/tests/` |
