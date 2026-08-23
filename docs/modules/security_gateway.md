# Security Gateway

**Stage:** S1 — Trust
**Realizes:** document 14 (`14_SECURITY_OPERATING_MODEL`) in full, per 21B §22
**Depends on:** `kernel`, `core`, `persistence` — nothing else (21B §22.13)

## Why it exists

`14.2.1` rejects the perimeter framing: security is the trust substrate every
other subsystem rests on. `14.6.1` makes the Gateway the sole source of truth
for "who may act" and "within what boundaries". It is built first because
21_PLAN §4.2 Rule 2 puts Trust before everything — no principal can be
authenticated, authorized or delegated to until this module exists.

It is operable **before the Event Bus exists**. `14.26.1` permits the Security
Event Journal to be written straight to persistence, which is what breaks the
Security ↔ Event Bus circular dependency and makes S1-before-S2 possible.

## Public interfaces (21B §22.5)

| Interface | Method | Consumers |
|---|---|---|
| Authentication | `authenticate` | All modules |
| Authorization | `authorize` | All modules |
| Identity Registration | `register_identity` | Human Interface, Agent Runtime, Governance |
| Delegation Management | `manage_delegation`, `validate_delegation_chain` | Human Interface, Decision Gateway |
| Revocation Command | `revoke` | Human Interface, Governance, anomaly detectors |
| Secret Reference Resolution | `resolve_secret_reference` | Tool Executor |
| Security Context | `create_security_context`, `validate_security_context` | All modules |
| Security Event Journal Query | `query_journal` | Governance, Human Interface (Auditor) |
| Security Health | `health` | Observability Gateway |

## Internal components (21B §22.3)

```
identity.py           Identity Registry, Registration Controller
tokens.py             Authentication Engine, Token Service
permissions.py        Permission Graph Engine
roles.py              Role Controller, Capability Enforcer
authorization.py      Authorization Engine, Authorization Cache
delegation.py         Delegation Manager
revocation.py         Revocation Engine
isolation.py          Isolation Enforcer
secrets_governor.py   Secret Governor, Credential Governor
context.py            Security Context Factory
incidents.py          Incident Classifier
enforcer.py           Constitutional Enforcer
journal.py            Security Event Journal
gateway.py            Composition of the nine public interfaces
```

## The four rules that shape the code

**Permissions intersect, never union** (`14.12.4`). `permissions.intersect`
folds every applicable source down, and hierarchical grants narrow to the more
specific side. A standing order cannot widen a role; a role cannot widen a
capability signature. An empty source list yields no permission, never all.

**Authorization is computed at the point of action** (21B §22.4). The engine
reads the live permission graph. The token's claim snapshot is used for scope
pre-filtering and attribution only — `14.9.5` is explicit that
re-authentication does not imply re-authorization.

**Cascading revocation is atomic or it is a failure** (`14.15.3`). Propagation
targets acknowledge explicitly; anything unacknowledged raises
`PartialRevocationError` and is alerted as a system failure rather than
returned as a degraded success. Gateway-local effects apply first, so a
propagation failure can never leave the Gateway itself honouring revoked
authority.

**There is no path from the Gateway to a secret value** (21B §22.10). The
Secret Governor returns an `InjectionGrant`, single-use and sandbox-bound. The
value passes to a sandbox injector and is never returned, logged or
journalled. A test asserts that no method with a value-returning name exists.

## Derived engineering targets

`14` publishes no latency table, so 21B §22.12 derives budgets from the
dependent subsystems': **p50 5ms / p99 20ms cached, p50 20ms / p99 80ms cold**
authorization. These are derived engineering targets, not constitutional
values, and feed the CIR-004 composite allocation.

`PROPAGATION_BOUND_SECONDS = 5.0` is an engineering choice aligned with the
Panic Protocol bound; `14.15.4` mandates a budget without publishing a figure
and 21B §22.12 records the window as an open ADR item.

## Open items

- **Cost Manager (Stage S3) does not exist.** `budget_resolver` is injectable
  and defaults to unmetered rather than fabricating a limit that would
  silently deny.
- **Escalation routing is partial.** `14.10.3` routes by decision class to
  team lead, business manager, portfolio architect or human sovereign; the org
  model lives in Agent Runtime (Stage S7). Until then escalation goes to the
  human sovereign rather than guessing an intermediate authority.
- **Persistence is the in-memory adapter.** Seven-year Sovereign-class
  retention is recorded per journal entry but enforced by a storage tier that
  arrives with the Postgres adapter.

## Test map

| Stage S1 required test | File |
|---|---|
| Principal registration | `tests/test_identity.py` |
| Authentication issuing a scoped token | `tests/test_tokens.py` |
| Permission Intersection Rule | `tests/test_permissions.py`, `tests/test_authorization.py` |
| Delegation grant and expiry | `tests/test_delegation.py` |
| Revocation with cascade | `tests/test_revocation.py` |
| Journal tamper-evidence | `tests/test_journal_and_secrets.py` |
| Failure domains, adversarial, Panic | `tests/test_constitutional_and_isolation.py` |
| Stage exit criterion, end to end | `tests/test_s1_exit_criterion.py` |
