# Event Bus

**Stage:** S2 — Truth
**Realizes:** document 08 (`08_EVENT_OPERATING_MODEL`) in full plus 02.3.4, per 21B §15
**Depends on:** `kernel`, `core`, `persistence`, `schema_registry`, `security_gateway` (21B §15.13)

## Why it exists

`08.2.6`: "Events are the nervous system; everything else is muscle."
Components do not poll, do not assume, and do not synchronously invoke one
another for coordination. Truth follows Trust in the build order (21_PLAN
§4.2 Rule 2) because every subsystem above Layer 1 derives its state from what
the Bus publishes.

**The Bus is not a Gateway** (21A §5.4.2). It routes on metadata and never on
content, authorizes nothing itself, grades nothing, adjudicates nothing. What
it guarantees is delivery, ordering, durability, and causality. Every
authorization decision is delegated to the Trust Plane — a test asserts the
Bus grows no permission model of its own.

## Public interfaces (21B §15.5)

| Interface | Method | Consumers |
|---|---|---|
| Event Emission | `emit` | All modules |
| Consumer Group Registration | `register_consumer_group` | All consuming modules |
| Event Consumption | `consume` / `acknowledge` / `signal_failure` | Registered groups |
| Replay Request | `request_replay` | Observability, Learning, Human Interface |
| Dead Letter Query | `query_dead_letters` | Human Interface, Governance |
| Stream Health | `health` | Observability Gateway |

## Internal components (21B §15.3)

```
envelope.py         Categories, states, retention schedule, PublishedEvent
admission.py        Admission Controller; TrustPlane and SchemaSource ports
streams.py          Stream Store, Stream Writer, Gap Detector
consumers.py        Consumer Group Registry, Router, RetryPolicy
delivery.py         Delivery Manager, Retry Scheduler, Dead Letter Manager
causality.py        Causality Tracker
backpressure.py     Backpressure Controller, Archive Manager
replay.py           Replay Engine
security_adapter.py Binds TrustPlane to the real Security Gateway
schema_adapter.py   Binds SchemaSource to the real Schema Registry
bus.py              Composition of the six public interfaces
```

## The rules that shape the code

**Durability precedes delivery** (`08.14.1`). `StreamWriter.publish` persists
before it returns, so nothing downstream can observe an event that is not
already stored. An event delivered but not durable would be a fact that could
be un-made.

**Routing is metadata-only** (`08.17.1`). The Router reads stream membership
and event-type prefix. It never opens `payload` — content routing would couple
producers to consumer logic and defeat the decoupling the Bus exists to
provide.

**Tenant isolation lives at the routing layer** (21B §15.4). A group in one
tenant is never a candidate for another tenant's events, subscription pattern
notwithstanding. Enforcing this at the consumer would mean the event had
already crossed the boundary.

**Critical streams are never shed** (`08` rule 7). `shed` refuses on category,
not on configuration: there is no setting that makes a command, audit, or
business event droppable.

**Replay never mutates live state** (`08` rule 11). A replay returns a
`ReplaySandbox` of replay-tagged copies rather than dispatching through the
Delivery Manager, so no replayed event can reach a live group's
acknowledgment bookkeeping.

**Nothing is silently lost** (21B §15.15 item 8). Every event ends
acknowledged, dead-lettered, or alerted, and `08` rule 18 means dead-lettering
always fires the alert.

## Design decisions worth knowing

**Pull-based consumption.** Streams are logs, not queues (`08.6.2`), so
`consume` is a poll against the group's own read position rather than a push.
Redelivery of anything due for retry comes first, so a failed event is never
starved by newer traffic.

**Out-of-band alerting.** The `alert` callable is a plain function, not an
event emission. 21B §15.11 is explicit: a subsystem cannot report its own
unavailability through the mechanism that is unavailable.

**Two adapter modules.** `security_adapter.py` is the only file importing
`security_gateway`, keeping the S1→S2 dependency edge visible in one place
(a test enforces this). `schema_adapter.py` exists because the two subsystems
spell schema versions differently — see the open item below.

## Derived engineering targets

`21B §15.12` publishes the full latency table from `08.22.1`: emission to
publication p50 10ms / p99 50ms, publication to delivery p50 5ms / p99 20ms,
50,000 events/second sustained ingestion. These are constitutional figures,
not derived ones, and are not yet validated — the in-memory adapter is not the
subject those numbers describe.

Retry attempts default to 10, fixed by the Build Spec's S2 test list. Base and
maximum backoff delay, the dead-letter depth threshold, and the lag/throttle
thresholds are `[Engineering Decision]` starting values; `08.17.3` and
`08.17.4` mandate the mechanisms without publishing figures.

## Open items

- **Schema version spelling differs between subsystems.** `08.4.1` calls
  `schema_version` a semantic version and `core.Event` defaults it to `1.0.0`;
  the Schema Registry keys entries by `major.minor`. `schema_adapter.py`
  narrows on the way in rather than redesigning a Done module's interface
  (Part IV, 17). The Schema Registry should settle this properly.
- **Performance is unvalidated.** The store is the in-memory adapter; the
  Redis Streams binding of the canonical stack does not exist yet, so the
  §15.12 table has not been measured against anything meaningful.
- **CIR-002 (transport binding) is unresolved.** Delivery semantics are
  implemented; the inter-service transport mechanism is not chosen here.
- **Encryption in transit and at rest** (`08.18.3`) is a deployment concern
  that arrives with the real transport and storage adapters.

## Test map

| Stage S2 required test | File |
|---|---|
| Authenticated producer emits schema-validated event | `tests/test_admission.py` |
| Unregistered event type rejected at emission | `tests/test_admission.py` |
| At-least-once delivery to a consumer group | `tests/test_delivery.py` |
| Causal ordering within a stream | `tests/test_causality_and_streams.py` |
| Replay without mutating business state | `tests/test_s2_exit_criterion.py` |
| Dead-lettering after 10 attempts, with alert | `tests/test_delivery.py` |
| Stage exit criterion, end to end | `tests/test_s2_exit_criterion.py` |
