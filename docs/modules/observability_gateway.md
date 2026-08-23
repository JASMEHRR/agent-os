# Observability Gateway — ingestion-only profile

**Stage:** S3 — Instrumentation & Economics (full interpretive profile: S10)
**Realizes:** document 16 (`16_OBSERVABILITY_OPERATING_MODEL`), per 21B §24
**Depends on:** `kernel`, `core`, `persistence`, `security_gateway` (21B §24.13)

## Why it exists now

Every module's Signal Emission — a mandatory Gateway mechanism (21A §5.2 item
7) — needs somewhere to land. Building this at S3 means S4 onward can emit
into a real sink instead of accumulating an instrumentation debt.

`16.2` frames observability as "the constitutional right of oversight to see",
not an operational convenience. `16.4` is the constraint that follows:
observability **reads** the system; it does not steer it.

## What this profile does and does not build

| Built at S3 | Deferred to S10 |
|---|---|
| Telemetry Ingest | Correlation Engine |
| Signal enrichment | Health composition |
| Journaling | Anomaly interpretation |
| Read-only Query API | Dashboard surface |
| Panic Confirmation Listener | SLI/SLO Registry, Alerting & Escalation |

Deferred components are **absent, not stubbed**. Nothing downstream can
accidentally depend on a hollow implementation, and a test asserts the
interpretive method names do not exist on the surface.

## Public interfaces (21B §24.5)

| Interface | Method | Semantics |
|---|---|---|
| Signal ingestion endpoint | `ingest`, `sink_for` | Receive-only |
| Query API | `query` | Read-only, Security-authorized |
| Panic Confirmation Signal | `confirm_halt`, `panic_confirmation` | Report-only |

## The constraints that shape the code

**No mutation path into any subsystem** (21B §24.14). Every public method is
read-only or receive-only. A test asserts that no mutating verb — `write`,
`configure`, `halt`, `trigger`, `revoke` — has appeared on the surface, because
such a method would be exactly the hidden control channel §24.14 forbids.

**Ingestion never raises into the emitter** (16.4). `ingest` returns a
`QualityAnomaly` rather than throwing: the caller is an operational
subsystem's out-of-band channel, and an exception crossing back into it would
be Observability steering an operational path. `kernel.SignalEmitter` also
catches sink failures, so both sides of the seam fail closed.

**No operational path waits on ingest** (21B §24.4). Emission appends to a
local buffer and returns. A subsystem stays fully operational when
Observability is down; its telemetry buffers and drains on reconnect.

**No observability bypass of Security** (21B §24.10). The Query API authorizes
through the ordinary Authorization interface, so the Permission Intersection
Rule applies — including to Governance's own queries. Signal sensitivity
(16.13) is enforced on read: a principal holding `observability.query.internal`
never sees a Restricted signal.

**Rejected signals are recorded, not discarded** (16.7.8). A silently dropped
signal makes its own coverage gap invisible, so every quality anomaly lands in
the journal.

## Derived engineering targets

`16.14` publishes SLI/SLO categories but no ingest-to-visibility figures.
`[Implementation Decision, 21B §24.12]`: p50 2s / p99 10s for metrics, p50 5s /
p99 30s for logs and traces. These are Observability's own internal SLOs and
are **not** inputs to any other subsystem's latency budget.

The cardinality limit (1,000 distinct signal names per source) is an
`[Engineering Decision]`; 16.7.2 mandates cardinality constraints without
publishing a figure.

## Open items

- **Retention and decay (16.7.7) are not implemented.** Signal states include
  Archived and Expired, but tiering and expiry are storage-tier concerns that
  arrive with the real telemetry store.
- **Coverage anomalies for absent signals (16.7.8) are not implemented** —
  detecting that an expected signal never arrived requires the expectation
  model that comes with the interpretive profile at S10.
- The telemetry store is the in-memory adapter, so the high-volume append-only
  tier of 21B §24.7 does not exist yet.

## Test map

| Stage S3 required test | File |
|---|---|
| Every signal type ingested, enriched, journaled | `tests/test_observability.py` |
| Query authorization and sensitivity | `tests/test_observability.py` |
| Panic confirmation within the 5-second bound | `tests/test_observability.py` |
| Read-only posture, deferred profile absent | `tests/test_observability.py` |
| End-to-end against a synthetic caller | `tests/s3_integration/test_s3_exit_criterion.py` |
