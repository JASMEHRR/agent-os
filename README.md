# Agent OS

Agent OS is a constitutionally-governed multi-agent runtime: a system of 26
modules (11 of them "Gateways") that let autonomous agents plan, decide, act
through tools/integrations, and learn — under enforced boundaries (tenant,
scope, authority, confidence, budget, temporal), human-authority decision
gating (Class A-D), an immutable audit journal, and a 5-second Panic Protocol
kill switch.

## Repository structure

```
ARCHITECTURE_BASELINE/    Ratified architecture (immutable, see below)
libs/                     Shared libraries (Layer 0 substrate)
  kernel/                 Universal Gateway mechanisms (identity, lifecycle,
                           boundaries, journal, failure classification, panic)
  core/                   Shared domain models, event schemas, exceptions
  persistence/            Hexagonal ports-and-adapters data access layer
services/                 One directory per module (26 total, built
                           incrementally per Stages S0-S12)
tests/                    Cross-module integration suites per stage, plus
                           tests/conformance/ which generates Appendices A-H
scripts/                  Local entry points (Post Studio, LinkedIn, importers)
docs/                     Module design docs, generated registers, rulings
HANDOFF.md                What is built, what runs, where to start
START_HERE.md             Post Studio, for the person using it
IMPLEMENTATION_JOURNAL.md Running engineering log of build progress
```

## Architecture Baseline

`ARCHITECTURE_BASELINE/` contains the ratified engineering specification for
Agent OS:

- `20A/20B/20C` — Constitutional Manifests (Foundation, Execution, Platform)
- `21A/21B/21C` — Implementation Architecture (Core, Subsystems, Delivery)
- `22_CLAUDE_CODE_BUILD_SPECIFICATION.md` — the stage-by-stage (S0-S12) build
  plan derived from the above

**These documents are immutable.** Implementation work must trace every
module, interface, and test to a specific section of these documents. Where
the architecture is silent, incomplete, or self-contradictory (see the
CIR-series conflicts in the build specification, Section 6), engineering work
stops and escalates rather than resolving the gap by implementation fiat.

## What runs today

One thing: **Post Studio**, the content agent.

```bash
python scripts/serve.py          # http://127.0.0.1:7860
```

`START_HERE.md` is the end-user walkthrough. `docs/HOSTING.md` covers deploying
it.

The other twenty-five modules are libraries with tests. Nothing runs them —
there is no socket behind `api_gateway`, no broker behind `event_bus`, and no
database behind the repositories except SQLite and an in-memory adapter. This
is deliberate and the modules say so in their own docstrings. **`HANDOFF.md`
explains the gap, why it is there, and where to start closing it.**

## Build prerequisites

What this repository actually needs today:

- **Python 3.11** (last verified on 3.11.15)
- **`pydantic`** — the one runtime dependency, used by `libs/kernel` and
  `libs/core`. Post Studio on its own is standard library only.
- **Node.js 20, npm 10** — for `services/workflow_engine/workflow_definitions`
  only, which is type-checked and unit-tested but not yet orchestrated by a
  Temporal server.

There is no package install step: `conftest.py` at the repository root puts
every lib and service on `sys.path`.

```bash
pip install pytest pytest-cov pydantic ruff==0.16.1 mypy==1.10.0 bandit==1.7.9
```

What the ratified architecture *mandates* and this build does not yet use:
Poetry, Docker Compose, PostgreSQL, Redis, FastAPI, Temporal. Those 35
technology mandates are binding and unmet, and are recorded as deviations in
`docs/appendix_f_traceability.md` rather than quietly omitted.

## Development workflow

1. Trunk-based development: short-lived branches per work item, no direct
   pushes to `master`.
2. `pre-commit install` before your first commit. Tool versions in
   `.pre-commit-config.yaml` are pinned to match `.github/workflows/ci.yml`
   exactly, so the hook and the gate never disagree.
3. Every module ships with unit, integration, and end-to-end tests before it
   is considered done — untested code is never committed.

The gates, exactly as CI runs them (these are four of the five CI jobs; the
fifth builds and tests the TypeScript workflow definitions):

```bash
ruff check libs services tests
ruff format --check libs services tests
mypy .
python -m pytest libs/ services/ tests/ -q --cov=libs --cov=services --cov-fail-under=90
bandit -r libs services --exclude "*/tests/*"
```

Note that `ruff check .` and an unpinned local `mypy` both report failures that
CI does not gate. `HANDOFF.md` section 5 lists the traps.

## How implementation is organized

Implementation proceeds stage by stage (S0-S12) per
`ARCHITECTURE_BASELINE/# 22_CLAUDE_CODE_BUILD_SPECIFICATION.md`, depth-first:
a module is either fully Done (all five criteria in the build spec's Section
39) or not started — there is no partial-credit state. Progress is recorded
in `IMPLEMENTATION_JOURNAL.md`.
