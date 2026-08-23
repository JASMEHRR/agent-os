# Decision Gateway

**Stage:** S5 — Authority
**Realizes:** document 11 (`11_DECISION_OPERATING_MODEL`) in full, per 21B §18
**Depends on:** Layer 0, Trust Plane, Event Bus, Economic Plane, Memory, Knowledge (21B §18.13)

## Why it exists

`11.2.1`: "A decision is a governed commitment to a course of action. It is
the moment the organization transitions from deliberation to obligation."

`11.2.4` draws the boundary this module enforces: **"An agent proposes; the
Decision subsystem evaluates... Agency is capacity; Decision is permission."**

It is the single most widely depended-upon subsystem above Layer 2. The Tool,
Integration and Deployment Gateways each require a committed decision record
before any external effect (12 rule 2, 17 rule 2, 18 rule 2), and `verify` is
the interface they ask through.

## Public interfaces (21B §18.5)

| Interface | Method |
|---|---|
| Decision Proposal | `propose` |
| Decision Verification | `verify` |
| Approval Response | `respond` |
| Standing Order Management | `manage_standing_order` |
| Reversal Request | `reverse` |
| Outcome Report | `report_outcome` |
| Decision Journal Query | `query_journal` |
| Decision Health | `health` |

## The funnel (21B §18.4)

Classification → options → evidence → evaluation → authority → compensation →
circuit breaker. Each gate can reject; none can be skipped.

**Classification is first and is not the proposer's to influence.** Class
determines every subsequent gate, and 11.24.2 names "agents proposing
decisions just below escalation thresholds" as a drift pattern — so the
Classifier takes the **highest** class any criterion implies. Cheap but
irreversible is Class D on reversibility alone.

**Reversibility is effective, not declared.** An option marked reversible but
carrying no resolvable compensation reference cannot in fact be undone
(11.21.2). Classifying on the declaration would let a proposer claim Class A
treatment for an action nothing can reverse, so the Classifier and the
Compensation Verifier share one judgement.

**Options include doing nothing.** 11.16.3 makes the null option the
baseline: "A decision to act must demonstrate superiority to the null
option." Ties go to inaction, and single-option proposals for Class B and
above are rejected structurally.

**Authority is risk-adjusted.** 11.14.3: a Class B decision at High risk is
treated as Class C *for authority purposes* — which means it takes the Class C
**path**, a packaged human approval request. Escalating without providing a
route to clear the raised bar would leave the decision stuck.

**Approval gates cannot auto-approve.** The Approval Orchestrator has no code
path from timeout to approval. On timeout Class C defers and Class D rejects.
11 rule 3 admits no exception and 11.18.3 forecloses implicit consent, so this
is enforced by construction — a test asserts no `auto_approve` /
`approve_on_timeout` / `default_approve` method exists on the surface.

## Derived engineering targets

`11.28.1` publishes the full latency table (Class A p50 100ms through Class D
package assembly p50 2s) and it appears in 21B §18.12. Not yet validated —
the store is in-memory.

`[Engineering Decision]` figures: approval windows (24h Class C, 3 days Class
D), the reversal window (24h, following 11.5.1's "reversible within 24h"), the
confidence modulation floor in `kernel.derive_confidence`, and the portfolio
concentration floor.

## Two design decisions worth knowing

**Confidence modulation floor.** `kernel.derive_confidence` originally
multiplied evidentiary confidence, option quality, temporal relevance and a
risk penalty straight through. Four sub-unit factors collapsed the result so
far that Level 3 (0.80) and Level 4 (0.90) became structurally unreachable —
every Class C and D decision would have deferred forever instead of being
decided under human approval. Option quality and temporal relevance now
*modulate* the evidentiary base rather than replacing it. This is an
`[Engineering Decision]` and it is the CIR-006 calibration surface: one
function to recalibrate when that item resolves, not four.

**Portfolio concentration floor.** Concentration is meaningless on a
near-empty portfolio — the first commitment to any business is 100%
concentrated by arithmetic, not by risk. The limit is evaluated only above a
capital-at-risk floor, so an empty portfolio is not permanently unable to make
its first commitment.

## Open items

- **`event_bus` is not yet wired in.** 21B §18.6 lists the Event Bus among
  consumed interfaces for trigger consumption and decision lifecycle
  emission. The Gateway emits signals through the kernel channel and journals
  everything, but does not yet publish decision lifecycle events. Wiring it
  is a small work item; it is listed here rather than done silently.
- **Human Interface (S8) does not exist.** `route_to_human` is injected and
  defaults to a no-op, so approval requests and escalations are packaged and
  journalled but not delivered anywhere until S8.
- **Memory Gateway is not consulted for sparse-evidence context.** 21B §18.6
  lists it "where evidence is sparse"; currently only Knowledge is queried
  for contradiction status.
- Performance is unvalidated against the §18.12 table.
- CIR-004 (composite mediation-chain latency) and CIR-007 (confidence
  miscalibration) both remain open and both touch this module.

## Test map

| Stage S5 required test | File |
|---|---|
| Class A–D with options and evidence grounding | `tests/test_decision_gateway.py` |
| Authority resolution by class and autonomy | `tests/test_decision_gateway.py` |
| Approval gates never auto-approve | `tests/test_decision_gateway.py` |
| **Adversarial: force auto-approval on Class D** | `tests/s5_integration/test_s5_exit_criterion.py` |
| Reversal with compensation | `tests/test_decision_gateway.py` |
| Supersession with lineage | `tests/test_decision_gateway.py` |
| Stage exit criterion, end to end | `tests/s5_integration/test_s5_exit_criterion.py` |
