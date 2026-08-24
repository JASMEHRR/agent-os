# Learning Gateway

**Stage:** S9 — Adaptation
**Realizes:** document 13 (`13_LEARNING_OPERATING_MODEL`) in full, per 21B §21
**Depends on:** Layer 0 through Layer 5, the Trust Plane, the Economic Plane, the Oversight Plane

## Why it exists

`13.2.1`: **"Learning is the only subsystem whose output is change to the other
subsystems."**

Memory asks what happened; Knowledge asks what is true; Decision asks what
shall be done; Tool asks how to act. Learning asks how to become better at all
of these — which makes it the only meta-layer in the system, and the only one
whose failure mode is degrading the thing it exists to improve.

`13.2.3` draws its boundary: "Knowledge Gateway owns validation; Learning
Gateway owns proposal. Learning feeds the Knowledge pipeline; it does not
bypass it."

## The closed loop (13.18.1)

**Observe → Propose → Adopt → Measure → Confirm/Refute → Consolidate.**

No adopted improvement escapes measurement (13 rule 9), and no feedback loop
stays open past its window (13 rule 16). `overdue()` reports windows that have
overrun rather than closing them, because closing one by fiat would manufacture
a confirmation nobody measured.

## Public interfaces (21B §21.5)

| Interface | Method |
|---|---|
| Observation Submission | `observe` |
| Human Feedback Entry | `submit_human_feedback` |
| Proposal Delivery | `propagate` |
| Adoption Report | `report_adoption` |
| Learning Journal Query | `query_journal` |
| Failure Library Query | `consult_failures` |
| Learning Health | `health` |

## Propagation is handoff, never adoption

`13.16.1`: "The target subsystem retains full constitutional authority to
reject, modify, or escalate the proposal."

`propagate` delivers to the target's registered intake and relinquishes
control. The target reports its decision back through `report_adoption`.
**There is no `adopt`, `commit`, `apply` or `enforce` verb on this Gateway**,
asserted by test — a verb that let Learning commit a change to a subsystem it
does not own is the one thing the meta-layer must never be able to do.

Rejection abandons the entry with its justification logged and, per 13.16.1,
"does not invalidate the evidence": the hypothesis and its evidence stay intact
in the journal.

## The non-violable screen runs at validation

21B §21.10: "a proposal that would touch a non-violable rule is rejected at
validation, not at the target Gateway."

That placement is the point. Relying on the target to refuse would mean every
one of seven target Gateways must implement the same screen correctly, and the
first one that did not would be the way in. 13 rule 3 (constitutional
constraints, security boundaries, human approval gates) and 13 rule 15
(autonomy escalation) are both screened here.

## Correlation is never causation

13 rule 6, enforced three ways rather than once:

* a causal claim with uncontrolled confounders is an attribution anomaly;
* a correlation pattern's derived confidence is capped **below** the 0.60
  floor, so no combination of strong evidence and strong attribution can lift
  it into propagation;
* every propagated package carries `is_causal_claim` and the null hypothesis,
  so the target cannot mistake one for the other after the handoff.

## Attribution is the hardest problem and the principal risk

13.12.3's safeguards are all enforced: minimum observation counts by target
class (13.12.4), a **mandatory non-blank** null hypothesis, temporal ordering,
and human review for Business and Portfolio attributions.

`attribution_error_rate` is the subsystem's most consequential signal. 13.4.3
defines Attribution Error as "an incorrect correlation between cause and
outcome, leading to harmful proposals" — the mechanism by which a learning
subsystem degrades the system it exists to improve. Here it is computed as
refutations over adoptions, so a Learning Gateway that is confidently wrong
shows up as a rising number rather than as silence.

## Asymmetric processing (13.34.3)

"Failure patterns require fewer confirming instances but stronger root cause
attribution. Success patterns require more confirming instances but permit
broader generalization."

Two instances plus a root cause for a failure; three for a success. Failure
entries also outrank success entries of equal strength in `prioritize`. When
capital is at risk, being slow to stop repeating a failure costs more than
being slow to replicate a success.

The same asymmetry shapes measurement: refutation resolves at the same point
confirmation does rather than running to the window ceiling, because leaving a
change the evidence already contradicts adopted for twice as long is the
expensive direction to be slow in.

## The Recursion Guard

`13.21.3` classifies a learning entry targeting Learning itself as a
**Recursion Anomaly** requiring "immediate human alert and suspension"; 21B
§21.9 makes it Category 1; 13 rule 17 forbids recursive cycle triggering
without human authorization.

It is a first-class component, not a validation rule, and it fires **before**
anything else can normalize the input. It blocks five distinct attack shapes:

1. a declared self-target;
2. a disguised name — matching is on the normalized form, so `Learning-Gateway`,
   `l e a r n i n g` and `learning/gateway` are all the same thing;
3. indirection through evidence — an entry deriving a conclusion from the
   Learning Journal reasons about itself whatever it declares as its target;
4. self-modification described in another subsystem's language — 13.35.1's
   "own validation rules, confidence thresholds, or measurement windows". This
   is the one a guard checking only the target field misses entirely;
5. a cycle triggered by a learning event (13 rule 17).

**There is no bypass argument.** 13 rule 4 permits a self-targeting entry only
under Class D human authority, which is a separate, explicit, audited act —
never a flag on the submission. `check` takes no `force`, `allow` or `override`
parameter, and a test asserts none ever appears.

Per 21C §38.5, the guard has a **dedicated adversarial suite**
(`tests/test_recursion_guard.py`), because its fail-closed posture "is only
meaningful if exercised against genuine self-reference attempts, not merely
ordinary-path tests."

## Human feedback

13.33.1 treats human feedback as high-confidence evidence that "bypasses
certain automated validation gates while retaining full audit", and 13.7.5 adds
that it "is never overridden by autonomous observation."

It bypasses the **evidence count** and nothing else: not the audit, not the
Recursion Guard, and not the non-violable screen. A human may teach the system,
and may not use the learning pipeline to move a constitutional boundary.

## Engineering Decisions recorded here

| Constant | Value | What the docs require |
|---|---|---|
| `DECAY_HALF_LIFE` | 90 days | 13.19 requires freshness decay, names no rate |
| `DEPRECATION_FLOOR` | 0.40 | 13.19 requires deprecation of stale entries, names no floor |
| `cycle_cost` | 1.0 | 13 rule 11 requires a budget check, names no per-cycle figure |

Everything else — evidence counts, confidence bands, measurement windows,
pattern minimums — is quoted from 13.12.4, 13.13.3, 13.18.2 and 13.34.3 rather
than chosen.

## Open items

* Measurement windows for Business and Portfolio learning run one to three
  business cycles, which 21B §21.8 calls the longest-lived progressive state in
  the system. In-process storage does not survive a restart, so that state is
  not yet as durable as the specification requires.
* The Extraction Engine is a caller responsibility: evidence is cited, not
  retrieved. Wiring it to pull from Memory, Decision, Knowledge and Tool
  records directly is deferred.
* Contradiction detection compares proposals on the same subject; it does not
  perform semantic comparison, so a differently-worded contradiction can pass.
* Seven-year journal retention (13 rule 18) is declared as a constant and not
  enforced by storage.
* `event_bus` is not wired in, so observation triggers arrive by direct call
  rather than by reacting to the event stream as 13.7.6 describes.
