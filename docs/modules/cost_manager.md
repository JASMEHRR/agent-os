# Cost Manager

**Stage:** S3 — Instrumentation & Economics
**Realizes:** 02.3.9; consumed by 11.14.4, 12.23, 13.20, 17.22, 18.31
**Depends on:** `kernel`, `core`, `persistence` (21A §9.4.4, Economic Plane)

## Why it exists now

Every subsequent module's budget enforcement needs this operational first.
Budget is one of the kernel's six boundaries, and a Gateway checking it
against nothing would be enforcing nothing.

02.3.9: "Prevents runaway costs. Enforces the 'Free API First' and 'Cost
Transparency' principles."

## Budget levels (02.3.9, verbatim)

| Level | Action | Trigger |
|---|---|---|
| Green | Normal operation | below 50% |
| Yellow | Warning logged, alert sent | 50–80% |
| Orange | Model downgrading enforced | 80–95% |
| Red | Operations halted, human escalation | above 95% |

The thresholds are not re-implemented here — `core.BudgetLevel.from_utilization`
already derives them, from S0.

## The properties that are structural, not configurable

**Red halts.** There is no flag, override, or waiver that lets an operation
proceed past 95% without a human. A budget ceiling that can be waived by the
thing hitting it is not a ceiling, and a test asserts no `override` / `waive` /
`force` / `bypass` method exists on the surface.

**Orange forces a downgrade.** The verdict carries `downgrade_required`, so a
caller that proceeds at full model cost is visibly ignoring a decision rather
than quietly skipping an optional hint.

**Pre-flight and post-flight are separate calls.** Pre-flight projects an
*estimate* and can refuse before anything is spent; post-flight records what
was actually spent, which is usually different. Recording only actuals would
let an unbounded operation start; refusing only on estimates would let the
ledger drift from reality.

**An unallocated scope is unmetered, and says so.** The Cost Manager will not
invent a limit it was never given, and will not return a confident Green that
hides the absence — the verdict states the scope is unbudgeted and a signal
records it.

**The ledger is append-only.** A refund or over-estimate is unwound by a
correcting entry that references what it corrects, never by editing history.
Cost attribution (02.3.9) depends on that history surviving.

## Circuit breakers

Closed → Open → Half-Open, guarded by `kernel.LifecycleStateMachine` so the
transition table is enforced rather than implied. A failing external
dependency does not stop costing money: retries against a broken integration
burn budget with no chance of success, which is exactly the runaway 02.3.9
exists to prevent. An open breaker refuses the call *before* any budget
arithmetic runs.

`[Engineering Decision]` five consecutive failures, 60-second cooldown —
02.3.9 mandates cost-based breakers without publishing thresholds.

## Injected dependencies

`escalate` is the human-escalation path Red requires. It is injected rather
than assumed, because no Human Interface exists until Stage S8 and the Cost
Manager does not pretend to know how a human is reached.

`signals` is a `kernel.SignalEmitter`. It works whether or not Observability
is attached: signals buffer locally and drain on connect, so a Cost Manager
wired before S3's Observability still records everything.

## Open items

- **Cost projection and optimization recommendations** (02.3.9 lists both) are
  not built. Projection needs historical spend curves; recommendations
  (cache-hit rates, model downgrade candidates) need the LLM Router, which is
  Stage S6.
- **LLM Router pre-flight integration** (02.3.9) awaits S6.
- Budget periods are recorded but not rolled: a new period is a new
  allocation, and automatic period rollover is not implemented.
- The ledger is in-memory; the `aos_analytics` Structured-tier store of
  21A §10 does not exist yet.

## Test map

| Stage S3 required test | File |
|---|---|
| Four budget levels, pre-flight and post-flight | `tests/test_cost_manager.py` |
| Orange forces downgrade, Red halts and escalates | `tests/test_cost_manager.py` |
| Circuit breakers trip on repeated failure | `tests/test_cost_manager.py` |
| Append-only ledger and attribution | `tests/test_cost_manager.py` |
| End-to-end against a synthetic caller | `tests/s3_integration/test_s3_exit_criterion.py` |
