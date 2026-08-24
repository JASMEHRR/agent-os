# Evolution Gateway and Plugin Manager

**Stage:** S12 — Transformation & Extension
**Evolution Gateway:** **built**, per 21B §26 — construction authorized by the G4
ruling of 2026-08-24 recorded in `docs/rulings/CIR-001.md`
**Plugin Manager:** built, not blocked (02.3.10, 01.18.2)

The two modules are paired by the build plan and have different statuses. That
difference is worth stating plainly rather than letting a reader assume the
stage is uniformly one or the other.

---

## Evolution Gateway — built

### Why it exists

The subsystem "through which Agent OS changes itself deliberately rather than
accidentally" (21B §26.1). `19.2` draws the line against Learning: Learning
adapts behaviour **within** standing constitutional and architectural bounds;
Evolution proposes changes **to** those bounds.

### The sentence the module is shaped around

`19.3`: Evolution **"packages; it does not ratify."**

The authority to change the Constitution or the architecture remains exclusively
with Governance and, beyond it, the sovereigns Governance answers to. `19.16.2`
states the handoff as unidirectional — "Evolution ensures the package is
complete" while Governance presents it.

That is what resolves the Evolution ↔ Governance circular dependency, and it is
enforced structurally: **there is no ratifying verb on this Gateway**. A test
asserts `ratify`, `approve`, `amend`, `enact`, `adopt` and `commit_amendment`
are all absent. The edge from Evolution back to ratification does not exist, so
the handoff is unidirectional by construction rather than by agreement.

### The block, and how it ended

21B §26's banner placed Evolution inside the same naming-prohibition ambiguity;
21A §3 named it the third of the three subsystems CIR-001 blocked. The G4 ruling
resolved it, and the full pipeline is built:
`monitor_signals` → `draft` → `analyse_impact` → `frame_compensation` →
`check_recursion` → `package` → `hand_off` → `record_outcome`.

**The ruling authorized construction, not authority.** There is still no
ratifying verb, and `ratification_verbs()` returns an empty tuple. A ruling that
unblocks a subsystem is easy to mistake for one that widens its powers, so the
distinction is asserted by test rather than described.

Two defects surfaced while building the transition table and were fixed:
`COMPENSATION_FRAMED` could not reach `QUARANTINED`, though the Recursion Guard
runs at that state — the guard could detect and not act. And `hand_off` accepted
only `PACKAGED` while the table permitted `DEFERRED → HANDED_OFF`, which made
deferral terminal in practice.

### What is enforced and tested

* **The pipeline** of 21B §26.4, in order, ending at `packaging_and_handoff` —
  not at adoption.
* **The Recursion Guard precedes packaging** (19.14). A self-referential
  proposal that reached Governance would arrive carrying Evolution's own
  endorsement of a change to Evolution's own bounds.
* **Compensation is framed before packaging** (19.13). Every proposal carries a
  rollback plan before it is handed over, not after.
* **Only Confirmed learning entries are consumable** (19.5, 21B §26.6) — never
  Proposed or Adopted-but-unconfirmed. An unconfirmed entry has not been
  measured, and amending a constitutional bound on the strength of something
  that might still be refuted is exactly what this gate prevents.
* **A4 is human-only** (19.36.2).
* **A rejected proposal is not deleted** (21B §26.8); the outcome is appended,
  preserving history for any future re-proposal.

---

## Plugin Manager — built

### Why it is not blocked

The Build Specification pairs it with Evolution at S12, but only Evolution
carries the block. What is constructed here — the manifest schema, the
capability and permission model, the lifecycle machine, the sandbox *contract* —
names no technology CIR-001 puts in doubt. What is deliberately not constructed
is the container runtime, which is the part 03 does name.

### The rule that shapes it

`01.18.2` gives the Non-Violable Rule: "No business-specific logic may be added
to core modules when it can be implemented as a plugin." It cuts both ways, and
the direction that matters inside this module is the second: **a plugin is
third-party code, so the manager's job is to bound it rather than to trust it.**

### Isolation, structurally

`02.3.10`: plugins "run as sidecars or separate containers, **never in core
process space**."

Two properties, both asserted by test:

* `SandboxTier` has no in-process member. An enum value no one can select is a
  stronger guarantee than a check someone can forget.
* The manager holds **no verb that executes plugin code** — no `invoke`, `call`,
  `execute`, `run`, `dispatch`, `load_module` or `import_plugin`. A Plugin
  Manager able to call a plugin directly would have made the isolation a
  convention that the next change could quietly drop. A caller that did invoke a
  plugin reports the outcome back through `record_invocation`, so reliability is
  visible without the manager holding a call path.

### Permissions are an intersection

A plugin receives the intersection of what its manifest **requested** and what a
human **granted** — never the union, and never the request alone. This is
14.12.4 applied at the extension boundary, which is the boundary least covered
by the rest of the system's identity model.

Granting a permission the manifest never requested is **refused** rather than
silently ignored: the mismatch means the operator and the manifest disagree
about what this plugin does, and that is worth surfacing.

A plugin cannot grant itself anything. Every grant, install, enable and
uninstall requires a human principal.

### Installation is not enablement

Mirroring the Tool Registry's registration-is-not-authorization rule. An
installed plugin permits nothing. Enabling one that holds none of the
permissions it requested is refused, because that would be running third-party
code for no declared purpose.

A disabled plugin permits nothing and receives no events, while its grant
survives — the grant surviving is what makes re-enabling cheap; the state change
is what makes disabling meaningful.

### Quarantine

01.18.2 acknowledges that "plugin quality and security are outside core
control", so the bound is here: a plugin failing more than half its invocations
across a meaningful sample is quarantined automatically, and a quarantined
plugin does not resume on its own — it returns only through Disabled, which a
human must lift.

A sample too small to be evidence does not act like evidence:
`QUARANTINE_MINIMUM_SAMPLE` prevents a short run of failures from quarantining a
plugin.

### Engineering Decisions recorded here

| Constant | Value | What the docs require |
|---|---|---|
| `QUARANTINE_FAILURE_RATE` | 0.5 | 01.18.2 requires sandboxing and capability restriction, names no threshold |
| `QUARANTINE_MINIMUM_SAMPLE` | 4 | the smallest sample at which a rate is worth acting on |

---

## What S12's exit criterion leaves unsatisfiable

21_PLAN §4.1 asks for "Amendments packaged and ratified; experiments bounded and
reversible; plugins discovered, sandboxed, and lifecycle-managed."

| Clause | Status |
|---|---|
| amendments packaged | **satisfied**; `package` produces a complete package |
| amendments ratified | never Evolution's to perform (19.3); Governance's authority |
| experiments bounded and reversible | bounds enforced at framing; no experiment runtime exists to run one |
| plugins discovered, sandboxed, lifecycle-managed | **satisfied in full** |

## Open items

* No experiment runtime. Bounds, scope, success criteria and rollback plans are
  validated at framing, but nothing executes an experiment.
* The Plugin Manager validates a sandbox *contract* and does not enforce it:
  there is no container runtime, so resource limits and the egress allowlist are
  declared and unenforced. This is the same gap the Tool Executor carries from
  S6 and it is the largest one in this module.
* Plugin API exposure through the API Gateway (02.3.10) is not wired; a plugin's
  declared routes do not appear on the ingress surface.
* Event Bus subscription is bounded by state and grant, but no plugin is
  actually subscribed, since delivery would cross the process boundary the
  runtime does not yet provide.
