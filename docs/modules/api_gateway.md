# API Gateway

**Stage:** S8 — Human Plane
**Realizes:** 02.3.1, and the API standards of 03 §32 including Rules 23 and 24
**Depends on:** Layer 0, Trust Plane

## Why it exists

`02.3.1`: "All external ingress. No external client communicates directly with
any internal service."

The design rationale the document gives is the one that matters: centralizing
cross-cutting concerns "prevents every service from reimplementing auth and
rate limiting." Reimplemented in fourteen services, those concerns would differ
in fourteen ways, and the differences would be the vulnerabilities.

## What is implemented, and what is not

Every ingress **semantic** the constitution requires is implemented and
enforced. The HTTP server is not. `Request` and `Response` are plain records
rather than a web framework's types, because 03's named framework cannot be
adopted while CIR-001 is unresolved and Build Spec Section 6 rule 9 forbids
resolving it by unilateral interpretation.

This is a deliberate scoping, not a stub: the pipeline runs, refuses, throttles,
replays and paginates for real. What is missing is the socket.

## The pipeline, in order

1. request identity and trace context, so even a refusal is traceable;
2. version resolution;
3. authentication;
4. rate limiting;
5. authorization for the route;
6. offset-pagination refusal;
7. idempotency lookup or reservation;
8. dispatch to the handler;
9. response emission and idempotent storage.

**Rate limiting sits after authentication** deliberately. An anonymous tier
applied to an authenticated client would throttle a paying tenant at the
anonymous rate, and a tier inferred before the token was validated could be
claimed by the client itself.

## Structural constraints

**The Gateway holds no business logic.** It routes; the handler decides. A test
asserts no `approve`, `reject`, `decide`, `override`, `execute` or `halt` verb
has appeared on `APIGateway`. A Gateway that starts deciding is a second place
where authority lives, and 02.3.1's centralization argument then works against
the system rather than for it.

**Authentication and authorization are delegated to the Trust Plane.** The
adapter goes through `SecurityGateway.authorize`, not through the permission
set directly, so the delegation chain, revocation, isolation and anomaly checks
stay in the path. 14.12.4's Permission Intersection Rule only holds if a single
authority computes it.

**An unsupported version is refused, not routed to the newest.** Silently
serving v1 to a v2 client changes their contract underneath them.

## Rate limiting (03 §32.5)

Token buckets across three dimensions — tenant, user, API key — and the
effective limit is the **most restrictive** of those that apply. That is the
same intersection discipline 14.12.4 imposes on permissions: a generous
per-user allowance cannot lift a tenant that has exhausted its quota, because
the tenant limit exists precisely to bound the sum of its users.

A refused request debits nothing. Consuming from the dimensions that could pay
and then refusing on another would charge a client for a request they never got
to make.

## Idempotency (03 §32.2, Rule 24)

Mandatory `Idempotency-Key` on every mutating method, with 24-hour retention.
Two properties matter more than the caching:

* **A key is bound to its request.** Replaying a stored response for a
  different body would silently discard the second request, so a mismatch is a
  409 rather than a replay: the client has a bug and needs to be told.
* **A failed attempt does not reserve the key.** Caching a 500 would make a
  transient failure permanent for 24 hours and prevent exactly the retry
  idempotency exists to enable.

Keys are scoped per principal, since nothing about a client-chosen key string
makes it globally unique.

## Pagination (03 §32.6, Rule 23)

Cursor-only. 03 §32.6 states it as a **Non-Violable Rule**, and it is enforced
structurally: `paginate` takes no offset argument, so no code path could serve
one, and a request carrying `page`, `offset`, `skip` or `start` is **refused
rather than ignored**. Ignoring it would give the client a wrong page with no
indication why.

The cursor resolves position by item identity, not index, which is what keeps a
page stable when items are inserted or removed between requests — the reason
the rule exists.

## Errors (03 §32.3)

One envelope, carrying code, message, details, `trace_id`, `request_id` and
timestamp. The error code registry is a closed enum: 03 §32.3 says "No ad-hoc
error strings", so a new failure mode adds a member rather than a string, and
the set of things the API can say stays enumerable.

## Open items

* No HTTP/WebSocket transport, no OpenAPI document served, no JWKS validation
  or token rotation — all blocked behind CIR-001's technology question.
* Rate-limit buckets are in-process, so horizontal scaling would need the
  shared store 03 §32.5 describes.
* The idempotency store is in-process and therefore does not survive a restart.
