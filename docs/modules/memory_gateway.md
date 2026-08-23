# Memory Gateway

**Stage:** S4 — Cognition
**Realizes:** document 09 (as far as the artifact extends) plus 02.3.5, per 21B §16
**Depends on:** `kernel`, `core`, `persistence`, `security_gateway`

## The source gap, stated plainly

The ratified artifact for document 09 **terminates mid-Section 10**. Sections
10.1–30 are absent, including the Non-Violable Memory Rules, the Glossary, and
the Performance Characteristics.

Sections 4–9 *are* complete, and they carry the load: identity primitives
(09.4), classification (09.5), the four tiers (09.7), the lifecycle (09.8) and
the state machine with its transition guards (09.9). Everything in this module
derives from those. Nothing fills the gap.

Two consequences are recorded rather than resolved:

- **Performance figures are provisional.** 21B §16.12 derives them from the
  Knowledge Gateway's published budgets pending source recovery. They are
  superseded the moment 09 is recovered.
- **The conformance suite cannot claim completeness.** The missing
  Non-Violable Rules are exactly the clauses a conformance suite would test
  against.

## Public interfaces (21B §16.5)

| Interface | Method |
|---|---|
| Memory Formation | `form` |
| Memory Retrieval | `retrieve` |
| Lineage Query | `lineage` |
| Relationship Traversal | `traverse` |
| Memory Health | `health` |

## The rules made structural

**No direct access** (09.6.1). The Gateway is the sole boundary; there is no
substrate handle to obtain.

**Anonymous memory is inadmissible** (09.4.3). Source identity and lineage are
required fields with no defaults — an unattributed entry cannot be built.

**Formation is not validation** (09.8.2). Separate engines, separate failure
modes: formation *rejects* at admission, validation *quarantines*. An entry
may be perfectly well-formed and wholly unreliable.

**An unlinked entry is never activated** (09.8.4, 09.8.5). Retrieval returns
only Active entries, and activation is gated on at least one edge existing. An
entry nobody linked is invisible by construction, not by filter.

**Decay degrades; it never deletes** (09.8.6). `DecayEngine` has no delete
method at all — a test asserts that. Deletion is Disposition, and Purge needs
statutory expiry **and** explicit human approval (09.9.2). Both, not either.

**Four boundaries at every operation** (09.6.3): tenant, business, agent, tier.
Applied before ranking, so an invisible result is never a candidate.

## Design note: whose clock?

`MemoryEntry.captured_at` is when the producer built the capture.
`MemoryRecord.formed_at` is when the Gateway formed it, from the Gateway's
injected clock. Retention and idle-decay measure from the **record**, so
neither can be skewed by a producer's clock. This was a real bug caught in
test: decay originally measured from the producer's wall-clock timestamp.

## Open items

- The Non-Violable Memory Rules and Performance Characteristics remain
  unrecoverable from the source.
- Source reliability is an injected callable defaulting to a flat 0.8; the
  Learning Gateway (S9) is what refines it.
- Working-tier durability against process loss (09.7.1) needs the real store.
- Consolidation (09.19) and cross-boundary anonymized sharing (09.20) are in
  the surviving table of contents but not in the surviving body text.
