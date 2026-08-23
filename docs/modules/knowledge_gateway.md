# Knowledge Gateway

**Stage:** S4 — Cognition
**Realizes:** document 10 in full, per 21B §17
**Depends on:** Layer 0, `security_gateway`, `memory_gateway`

## Why it exists

`10.2.6`: agents "do not reason over unstructured memory dumps or raw event
streams. They reason over a body of validated belief that has been checked for
contradiction, linked into an ontology, and assigned confidence."

`10.2.1` sets the bar, and all three of its rejections are structural here:

| Rejected | How it is made impossible |
|---|---|
| Speculation (no evidence) | `evidence` is a required field; extraction refuses an empty citation list |
| Noise (no confidence) | Confidence is assigned by validation, never asserted by the producer |
| Dogma (unfalsifiable) | `falsifiability` is a required field with specific, observable, time-bounded conditions |

## Public interfaces (21B §17.5)

| Interface | Method |
|---|---|
| Belief Query | `query` |
| Graph Traversal | `traverse` |
| Hypothesis Submission | `submit` |
| Contradiction Query | `contradictions_for` |
| Ontology Query | `query_ontology` |
| Ontology Change Proposal | `propose_ontology_change` |
| Knowledge Health | `health` |

## Confidence bands (10.14.2, verbatim)

| Range | Status | Usage |
|---|---|---|
| 0.00–0.59 | Hypothesis | Not available for reasoning |
| 0.60–0.79 | Validated | Available, **must be flagged provisional** |
| 0.80–0.94 | Canonical | Standard basis for reasoning |
| 0.95–1.00 | Axiomatic | Requires human ratification |

Every `BeliefAnswer` carries its band and a `provisional` flag. 21B §17.10
makes suppressing that qualification a conformance violation, so it travels
*in* the answer rather than being something a consumer must remember to check.

## The rules made structural

**Hypotheses are never visible to reasoners** (10.7.2, rule 10). The Hypothesis
Store is a separate object from the belief set, and the query path never reads
it. There is no filter to misconfigure.

**Promotion is not automatic upon validation** (10.7.5). It requires
integration and the absence of any unresolved contradiction — rule 4.
Detection *demotes* both canonical beliefs rather than merely annotating them.

**Arbitration is mandatory, not a fallback** (10.15.3). Both beliefs ≥0.85,
Restricted knowledge, cross-business, or exhausted automated attempts — the
engine returns HUMAN_ARBITRATION regardless of what the caller would prefer,
and only a Human may then arbitrate, as a Class D act.

**The ontology is not self-modifying** (10.16.4, rule 13). `propose` and
`ratify` are separate calls; only a human ratifies, and a proposer may not
ratify its own change.

**The Learning Model may not insert beliefs** (10.6.6). Every belief enters
through `submit` and travels the full pipeline.

**Deprecation never deletes** (10.7.8, rule 18) and requires a justification.

## Graph integrity (10.17.4)

Three constraints, checked rather than assumed: no orphaned canonical nodes,
no contradictory cycles, no dangling supersession references.
`check_integrity` returns *every* violation rather than raising on the first,
because 21B §17.9 responds with a repair workflow that needs the whole picture.

## The Epistemic failure category

`10.23.3` extends the kernel's five-category failure taxonomy **by
constitutional provision, not implementation choice**. `EpistemicFailure`
quarantines the affected beliefs and suspends the extractor; only a human
reinstates. Fabricated evidence — a citation to a memory that does not exist —
triggers it, verified against the real Memory Gateway rather than a stub.

## Open items

- Extraction is driven by explicit submission; the automated extraction cycle
  triggered from the Event Bus (21B §17.6) awaits its wiring.
- Archival and disposition states exist in the lifecycle but the tiering to
  cold storage needs the real store.
- Performance is unvalidated: 10.24.1 publishes a full latency table
  (canonical query p50 50ms, 10,000 queries/second) against an in-memory graph.
- Load-shedding order (21B §17.12) is specified but not implemented; there is
  no load to shed yet.
