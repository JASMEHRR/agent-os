# Human Interface

**Stage:** S8 — Human Plane
**Consolidates:** 05.18, 11.18, 13.33, 16.25, 17.31, 18.35, 19.36
**Depends on:** Layer 0, Trust Plane, and every subsystem that registers a panic hook

## Why it exists

`05.18.1`: **"Human operators are not users; they are sovereign delegates."**

Seven documents each grant humans the same four rights over their own domain:
approve, override, be informed, and halt. Implemented separately in seven
Gateways, those rights would be seven slightly different implementations, and
the differences would be where sovereignty leaks. Consolidating them means
there is one place where sovereignty can be verified rather than seven places
where it can quietly differ.

The asymmetry runs through every method: a human may override the system, and
the system may not override a human.

## Approve (11.18, 05.18.2)

`11.18.2`: "The runtime may not auto-approve on timeout, infer consent, or
bypass gates through creative interpretation."

Enforced structurally, not documented:

* `respond` requires a human principal, checked against the Trust Plane rather
  than inferred from an identifier;
* `expire` can produce only `DEFERRED` (Class C, per 11.18.3) or `REJECTED`
  (Class D). The approved state is unreachable from an elapsed deadline, and no
  argument to the method could make it reachable. A timeout is the absence of a
  decision, and the only thing the system may do with an absence is refuse to
  proceed;
* `health()` reports `auto_approved`, which is structurally always zero.

**Request completeness is validated at submission.** 11.18.1's list — proposal,
rationale with evidence, cost, risk, rollback plan, alternatives, confidence,
urgency, deadline — is a requirement, because an operator asked to approve
without the rollback plan and the alternatives is being asked to rubber-stamp.

**Batching carries its own hazard.** 11.18.4 permits grouping related requests
to reduce context switching, and adds that batched items "are never
auto-approved as a group". So `Batch` holds identifiers, items stay
individually actionable, and there is deliberately no `approve_batch`: one
click consenting to things the operator never read is the failure that method
would create.

## Override (05.18.3, 13.33.2, 17.31.2, 18.35.3, 19.36.3)

"Immediate, irreversible by the runtime, and logged", recorded as a Class D
action.

**Irreversible by the runtime** is the half an implementation loses most
easily. A `revoke` reachable by a service would let the system undo the human's
correction, which is precisely the failure the clause names. So `Override` is
frozen, the ledger is append-only, and a test asserts no `revoke`, `delete`,
`reverse`, `undo` or `clear` verb exists on it. The only way to change an
override's effect is a *new* human action recorded beside the first.

## Delegate (05.18.5, 16.25.3)

Standing orders are the mirror image of override: humans may hand routine
decisions to the runtime, but the delegation is **scoped, time-bounded, and
revocable**. An unscoped order is refused, because it would be
indistinguishable from removing the gate entirely. 16.25.3 fixes the bound at
30 days unless renewed, and renewal is an explicit human act, so an order
nobody remembers lapses rather than persisting.

## Be informed (18.35.4, 19.36.5, 16.25.2)

Severity decides the channel, and the classification is made at submission
rather than at delivery. Routine and elevated events batch into a scheduled
digest; critical events deliver immediately.

Both halves are failures if reversed:

* spamming every routine event trains the operator to ignore notifications, and
  the alert that matters then arrives into that trained inattention;
* batching a critical event delays the one notification that could not wait.

Nothing downstream can override the routing, since no argument to `submit`
selects a channel.

## Halt (05.18.4, 17.31.4, 16.25.4, 13.33.4)

`05.18.4`: "A single command halts all autonomous activity, pauses in-flight
workflows, and requires human intervention to resume."
`17.31.4`: "Panic completion must occur within 5 seconds."

`kernel.panic` holds the participation hook every Gateway registers against;
this module is the human-facing switch. Four properties are structural:

* **Always available.** No lock, no quorum, no policy consulted. A panic switch
  that could itself be unavailable is not a panic switch, so it is the one
  operation with no authorization check beyond "is this a human".
* **The bound is measured, not assumed.** `invoke` times itself, raises
  `PanicBoundExceededError` on a breach, records the report, and escalates a
  Category 1 incident. A panic that silently took nine seconds is a
  constitutional violation nobody would otherwise learn about.
* **A failing participant cannot veto the halt.** Each hook is called
  defensively, its failure recorded and escalated, and the halt proceeds. A
  subsystem that could veto panic by raising would be a subsystem that could
  veto human sovereignty.
* **Resumption is human-only.** No timeout, no auto-resume, no service path
  into `resume`. A resume-on-timer would negate the clause entirely, and a test
  advances the clock thirty days to confirm elapsed time lifts nothing.

Panic also flushes queued routine digests, because 16.25.4 says panic
"prioritizes completeness over cognitive load minimization" — the one
circumstance where batching yields.

`drill()` implements 05.18.4's monthly test against the real hooks, and
`health()` reports `drill_overdue` so a lapsed drill is visible before a real
panic discovers it.

## Engineering Decisions recorded here

| Constant | Value | What the docs require |
|---|---|---|
| `DEFAULT_CADENCE` | 6 hours | 16.25.3 lets humans configure cadence, names no default |
| `DRILL_INTERVAL_DAYS` | 30 | 05.18.4 requires monthly testing, names no mechanism |

## Open items

* Panic halts participants that have registered. Nothing forces a subsystem to
  register, so a Gateway added later could be omitted; the Governance
  conformance matrix is where that gap should be closed.
* Approval requests are durable in-process only.
* No notification transport: `notify` is a callable, and email, chat and pager
  delivery are outside the process.
* The Event Bus is not wired in; signals reach Observability directly.
