# Governance Gateway

**Stage:** S10 — Oversight
**Realizes:** document 15 (`15_GOVERNANCE_OPERATING_MODEL`) in full, per 21B §23
**Depends on:** the Trust Plane, the Event Bus, all subsystem journals, the Observability Gateway

## Why it exists

`15.2.1`: "Governance is the guardian of the guardrails. **It does not drive the
vehicle; it verifies that the vehicle remains on legitimate roads.**"

`15.2.6`: "Governance is the organizational immune system," existing to detect,
arrest and reverse constitutional drift before organizational legitimacy
collapses.

`15.6.1` gives it the authority nothing else has: **"No subsystem may
self-certify its own constitutional compliance."**

It assesses what it does not own. That is the defining characteristic of
oversight, and the reason every constraint below is about what the Gateway
*cannot* do.

## Public interfaces (21B §23.5)

| Interface | Method |
|---|---|
| Compliance Query | `compliance_of` |
| Policy Query | `applicable_policies` |
| Interpretation Request | `interpret` |
| Governance Ruling | `assess` |
| Exception Request | `grant_exception` |
| Stewardship Query | `accountability_chain` |
| Audit Finding | `conduct_review` / `findings` |
| Governance Health | `health` |

## Meta-oversight observes and never intervenes

`15.22.3`: Governance "may declare a subsystem's self-governance non-compliant;
it may not directly modify subsystem internals, reassign agents, or alter
decision logic. Remediation is routed through the subsystem's own governance
mechanisms or human authority."

Structural: the Gateway holds no reference to any subsystem it assesses, and a
test asserts no `suspend_agent`, `reassign`, `remediate`, `enforce`, `halt` or
`reconfigure` verb has appeared. A non-compliant ruling **records** a
remediation requirement; nothing here executes one. The S10 exit test checks
that a non-compliant finding against an agent leaves the agent's state
unchanged, because that gap is the whole point.

## No subsystem self-certifies

`assess` refuses when the assessing principal holds accountability for the
scope being assessed. This is 15.6.1 as a check on the assessor's own
stewardship rather than as a slogan in a docstring: a steward grading their own
domain is precisely the case the clause exists to prevent.

The same rule appears twice more, as 15.25.4 (a steward may not review their own
stewardship domain) and 15.27.4 (no principal audits a scope they are
accountable for). Both are enforced **at assignment**, refusing the review
rather than flagging the finding afterwards, because a compromised review is
worth nothing once written.

## Timeout never ratifies

`15.8.2` specifies Under Review → Rejected on "timeout without response (does
NOT auto-ratify)". `15.28.4` adds that escalation timeout escalates further.

Enforced two ways. Behaviourally, `expire_reviews` produces Rejected (G1/G2) or
Escalated (G3/G4) and nothing else. Structurally, a test reads the method's own
source and asserts the string `RATIFIED` does not appear in it — so a future
edit cannot add that path without the test failing, even if the edit looks
innocuous in review.

## Evidence before assessment, and gaps are declared

`15.12.1` grounds assessment in canonical records. `15 rule 1` requires
documented evidence **or a gap flag**.

The Evidence Assembler reports what it could not find: a missing journal, an
empty journal, and a consultation of no subsystems at all each produce a gap
rather than an empty package. Silence about a gap makes an assessment look
better founded than it is, which is the specific way an oversight subsystem
lies without anyone intending it to. An assessment made over gaps carries an
**uncertainty rider** and enhanced monitoring (21B §23.9), rather than being
treated as complete.

## Breaking the Governance ↔ Observability cycle

`15.7.2` permits evidence assembly **directly from subsystem journals**. That
clause is what lets journal-based Governance operate before the full
Observability profile exists, and it is why both modules could be built in this
stage without either blocking the other: each reads a third party's journal, so
the edge that would make the dependency circular is never drawn.

The adapter exposes reads only. A Governance Gateway able to write to a
subsystem journal could manufacture the evidence it then assesses.

## The policy hierarchy

Six layers (15.16.1), strictly ordered, "lower layers may elaborate but never
contradict higher layers."

* **Orphans are rejected.** 15.16.2: "A policy without constitutional lineage is
  illegitimate."
* **A missing sunset condition is rejected** (15.17.1). A policy nobody planned
  to retire is a policy nobody will.
* **Contradiction is blocked at formation**, and where it emerges after
  activation the lower policy is **automatically suspended** pending review
  (15.16.3). Automatic, because the alternative is a window during which two
  contradictory policies are both active and subsystems are choosing between
  them.
* **Supersession preserves lineage** (15.17.4), and a lower layer may not
  supersede a higher one.
* An emergency suspension requires G3 review within 24 hours (15.17.6), and an
  overdue one is reported.

## Authority, and what cannot be delegated

G1 to G4 (15.9.1), with 15.9.2's confidence floors enforced as a gate: 0.70,
0.80, 0.90, and for G4 axiomatic backing plus human ratification, where
confidence cannot substitute.

**G4 is human-only and is checked at formation**, not at ratification. An
artifact that reached review would already have a constituency, and withdrawing
it then costs more than refusing it at the start. The same applies to G4
stewardship, which cannot be assigned to a machine at all.

## Interpretation clarifies; it does not amend

`15.19.1` makes interpretations binding on their scope and subordinate to the
constitutional text. `15.19.2` puts an interpretation that would functionally
alter constitutional meaning outside interpretation authority; it must proceed
as an amendment, and the Gateway refuses it. An ungrounded interpretation is
refused too, because an interpretation grounded in nothing is an invention.

This is the mechanism through which 21A §3's Constitutional Interpretation
Register is resolved — including, eventually, CIR-001.

## Exceptions are provisional by construction

15.29 and 15 rule 17 require all four of time bounds, scope limits, risk
assessment and post-hoc review, and all four are checked rather than assumed
from the caller's diligence. An expired exception whose post-hoc review never
happened is how a provisional deviation quietly becomes a permanent one, so
`overdue_exception_reviews()` surfaces it, and the granting authority may not
conduct the review.

## Drift, and the subsystem's own cost

Drift is measured as **velocity**, not position: 15.2.6 is about divergence
compounding, and a single reading cannot say whether things are getting worse.
Velocity past the threshold sets the scope to Drifting, alerts a human, and
raises a Category 1 escalation.

21B §23.11 requires the Gateway to **expose its own cost**, because CIR-008 asks
whether 04.32's fifteen percent improvement cap bounds the aggregate oversight
burden. `overhead_ratio()` measures it and `health()` reports whether the
circuit breaker is breached. The question is left open and made answerable
rather than assumed either way.

## Engineering Decisions recorded here

| Constant | Value | What the docs require |
|---|---|---|
| `GOVERNANCE_OVERHEAD_CEILING` | 0.15 | 15.14.4 requires a maximum overhead ratio, names no figure; CIR-008 is open |
| `DRIFT_VELOCITY_THRESHOLD` | 0.25 | 15.21 requires drift escalation, names no threshold |

## Open items

* **Compliance assessment is invoked, not continuous.** 15.18.2 requires
  continuous assessment; here a caller triggers it. Wiring it to the Event Bus
  as 21B §23.6 describes is deferred.
* Non-violable and contradiction screening is textual. A proposal phrased to
  avoid the vocabulary would pass, and semantic screening is the obvious next
  step.
* 15 rule 19 requires governance failures classified and alerted within 60
  seconds; `FAILURE_ALERT_BOUND` is declared and not yet measured against.
* Sovereign-class access control for exception and ratification logs (15.29.4)
  is not separately enforced beyond ordinary journal access.
* Sovereign Override (15.9.4) is exercised through the Human Interface's
  override ledger rather than as a distinct Governance transition.
