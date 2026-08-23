# Agent OS

Agent OS is a constitutionally-governed multi-agent runtime: a system of 26
modules (11 of them "Gateways") that let autonomous agents plan, decide, act
through tools/integrations, and learn — under enforced boundaries (tenant,
scope, authority, confidence, budget, temporal), human-authority decision
gating (Class A-D), an immutable audit journal, and a 5-second Panic Protocol
kill switch.

## Repository structure

```
ARCHITECTURE_BASELINE/   Ratified architecture (immutable, see below)
libs/                     Shared libraries (Layer 0 substrate)
  kernel/                 Universal Gateway mechanisms (identity, lifecycle,
                           boundaries, journal, failure classification, panic)
  core/                   Shared domain models, event schemas, exceptions
  persistence/            Hexagonal ports-and-adapters data access layer
services/                 One directory per deployable module (26 total,
                           built incrementally per Stages S0-S12)
docs/                     MkDocs documentation
infra/                    Terraform/OpenTofu, deployment config
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

## Build prerequisites

- Python 3.11.9+ (3.12.x permitted), Poetry 1.8+
- Node.js 20 LTS, npm 10+ (TypeScript, for Temporal workflow definitions only)
- Docker 25.0+ and Docker Compose
- PostgreSQL 16.3+, Redis 7.2+ (provided via `docker compose up` locally)

## Development workflow

1. `docker compose up` from a clean clone produces a healthy local
   environment.
2. Trunk-based development: short-lived branches per work item, no direct
   pushes to `main`.
3. `pre-commit install` before your first commit.
4. Every module ships with unit, integration, and end-to-end tests before it
   is considered done — untested code is never committed.

## How implementation is organized

Implementation proceeds stage by stage (S0-S12) per
`ARCHITECTURE_BASELINE/# 22_CLAUDE_CODE_BUILD_SPECIFICATION.md`, depth-first:
a module is either fully Done (all five criteria in the build spec's Section
39) or not started — there is no partial-credit state. Progress is recorded
in `IMPLEMENTATION_JOURNAL.md`.
