"""API Gateway conformance tests (02.3.1, 03 §32, Build Spec Stage S8).

The rules tested hardest are the two the Build Specification names as
Non-Violable and the one that is easiest to get subtly wrong:

* offset pagination is refused, not ignored (03 §32.6, 03 Rule 23);
* mutating endpoints require an `Idempotency-Key` (03 §32.2, 03 Rule 24);
* the rate limiter takes the *intersection* of its three dimensions, so a
  generous per-user allowance cannot lift an exhausted tenant.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from api_gateway import (
    BAD_REQUEST,
    CONFLICT,
    CREATED,
    FORBIDDEN,
    NOT_FOUND,
    OK,
    TOO_MANY_REQUESTS,
    UNAUTHORIZED,
    APIGateway,
    ErrorCode,
    IdempotencyStore,
    Method,
    OffsetPaginationRefused,
    RateLimiter,
    Request,
    Response,
    Route,
    Tier,
    assert_no_offset,
    decode_cursor,
    encode_cursor,
    paginate,
)
from api_gateway.idempotency import RETENTION, KeyReused, fingerprint
from core.exceptions import NotFoundError, ValidationError
from kernel.signals import SignalEmitter

TENANT = "tenant-alpha"
HUMAN = "human-sovereign"


class Clock:
    def __init__(self) -> None:
        self.now = datetime(2026, 8, 1, 12, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.now

    def advance(self, delta: timedelta) -> None:
        self.now += delta


class FakeAuthority:
    """The Trust Plane's ingress surface only."""

    def __init__(self) -> None:
        self.tokens = {"tok": (HUMAN, TENANT), "tok-service": ("service-worker", TENANT)}
        self.permissions = {HUMAN: {"decisions.read", "decisions.approve"}, "service-worker": {"decisions.read"}}
        self.authorizations: list[tuple[str, str]] = []

    def authenticate(self, token: str) -> tuple[str, str]:
        if token not in self.tokens:
            raise ValueError(f"token '{token}' is not valid")
        return self.tokens[token]

    def tier_of(self, principal_id: str) -> Tier:
        return Tier.SERVICE_ACCOUNT if principal_id.startswith("service-") else Tier.AUTHENTICATED

    def permits(self, token: str, principal_id: str, permission: str, tenant_id: str) -> bool:
        self.authorizations.append((principal_id, permission))
        return permission in self.permissions.get(principal_id, set())


ITEMS = [{"id": f"item-{n:02d}", "value": n} for n in range(10)]


def read_handler(request: Request, principal_id: str, tenant_id: str) -> Response:
    page = paginate(ITEMS, cursor=request.query.get("cursor"), limit=int(request.query.get("limit", 3)))
    return Response(status=OK, body=page.to_body())


def approve_handler(request: Request, principal_id: str, tenant_id: str) -> Response:
    return Response(status=CREATED, body={"approved": request.body.get("decision_id"), "by": principal_id})


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def authority() -> FakeAuthority:
    return FakeAuthority()


@pytest.fixture
def gateway(clock: Clock, authority: FakeAuthority) -> APIGateway:
    counter = {"n": 0}

    def next_id() -> str:
        counter["n"] += 1
        return f"req-{counter['n']:04d}"

    gw = APIGateway(
        authority=authority,
        signals=SignalEmitter(source_identity="api_gateway"),
        now=clock,
        request_ids=next_id,
    )
    gw.register_route(Route(Method.GET, "/decisions", "decisions.read", read_handler))
    gw.register_route(Route(Method.POST, "/decisions/approve", "decisions.approve", approve_handler))
    return gw


def get(path: str = "/v1/decisions", token: str | None = "tok", **query: str) -> Request:
    return Request(method=Method.GET, path=path, token=token, query=dict(query))


def post(body: dict[str, Any] | None = None, key: str | None = "idem-1", token: str | None = "tok") -> Request:
    headers = {"Idempotency-Key": key} if key else {}
    return Request(
        method=Method.POST,
        path="/v1/decisions/approve",
        token=token,
        body=body or {"decision_id": "dec-1"},
        headers=headers,
    )


# ------------------------------------------------------------- Ingress basics


def test_a_request_reaches_its_handler(gateway: APIGateway) -> None:
    response = gateway.handle(get())
    assert response.status == OK
    assert len(response.body["data"]) == 3


def test_every_response_carries_request_and_trace_identity(gateway: APIGateway) -> None:
    """02.3.1 — request ID generation and trace context injection."""
    response = gateway.handle(get())
    assert response.headers["X-Request-Id"] == "req-0001"
    assert response.headers["X-Trace-Id"].startswith("trace-")


def test_a_supplied_trace_id_is_preserved(gateway: APIGateway) -> None:
    """A trace that restarted at the boundary would not span the client's call."""
    request = Request(method=Method.GET, path="/v1/decisions", token="tok", headers={"X-Trace-Id": "trace-upstream"})
    assert gateway.handle(request).headers["X-Trace-Id"] == "trace-upstream"


def test_an_unknown_route_is_a_404(gateway: APIGateway) -> None:
    response = gateway.handle(get(path="/v1/nothing"))
    assert response.status == NOT_FOUND
    assert response.body["error"]["code"] == ErrorCode.ROUTE_NOT_FOUND.value


def test_a_route_may_not_be_registered_twice(gateway: APIGateway) -> None:
    with pytest.raises(Exception, match="already routed"):
        gateway.register_route(Route(Method.GET, "/decisions", "decisions.read", read_handler))


# --------------------------------------------------------------- Versioning


def test_an_unsupported_version_is_refused_not_routed_to_the_newest(gateway: APIGateway) -> None:
    """Routing v2 to v1 would change a client's contract underneath it."""
    response = gateway.handle(get(path="/v2/decisions"))
    assert response.status == NOT_FOUND
    assert response.body["error"]["code"] == ErrorCode.UNSUPPORTED_VERSION.value
    assert response.body["error"]["details"]["supported"] == ["v1"]


def test_an_unversioned_path_is_refused(gateway: APIGateway) -> None:
    assert gateway.handle(get(path="/decisions")).status == NOT_FOUND


# ---------------------------------------------------- Authentication / authz


def test_an_unauthenticated_request_is_401(gateway: APIGateway) -> None:
    response = gateway.handle(get(token=None))
    assert response.status == UNAUTHORIZED
    assert response.body["error"]["code"] == ErrorCode.UNAUTHENTICATED.value


def test_an_invalid_token_is_401_not_500(gateway: APIGateway) -> None:
    response = gateway.handle(get(token="forged"))
    assert response.status == UNAUTHORIZED


def test_a_principal_without_the_permission_is_403(gateway: APIGateway) -> None:
    response = gateway.handle(post(token="tok-service"))
    assert response.status == FORBIDDEN
    assert response.body["error"]["details"]["permission"] == "decisions.approve"


def test_authorization_is_delegated_rather_than_recomputed(gateway: APIGateway, authority: FakeAuthority) -> None:
    """14.12.4's intersection only holds if one authority computes it."""
    gateway.handle(get())
    assert authority.authorizations == [(HUMAN, "decisions.read")]


def test_the_gateway_holds_no_business_logic() -> None:
    """02.3.1 centralizes cross-cutting concerns, not decisions.

    Structural: a Gateway that starts deciding becomes a second place where
    authority lives, and the centralization argument then works against the
    system rather than for it.
    """
    forbidden = {"approve", "reject", "decide", "override", "execute", "invoke_tool", "halt"}
    present = {name for name in dir(APIGateway) if not name.startswith("_")}
    assert not (forbidden & present), f"the Gateway has absorbed a decision: {forbidden & present}"


# ------------------------------------------------------------ Rate limiting


def test_an_exhausted_quota_is_429_with_the_standard_headers(clock: Clock) -> None:
    limiter = RateLimiter(now=clock)
    limiter.configure("tenant", TENANT, rate_per_minute=2, burst=2)
    assert limiter.check(Tier.AUTHENTICATED, tenant_id=TENANT).allowed
    assert limiter.check(Tier.AUTHENTICATED, tenant_id=TENANT).allowed
    decision = limiter.check(Tier.AUTHENTICATED, tenant_id=TENANT)
    assert not decision.allowed
    headers = decision.headers()
    assert headers["RateLimit-Limit"] == "2"
    assert headers["RateLimit-Remaining"] == "0"
    assert int(headers["RateLimit-Reset"]) > 0


def test_the_gateway_returns_429_when_the_limiter_refuses(gateway: APIGateway) -> None:
    gateway.limiter.configure("tenant", TENANT, rate_per_minute=1, burst=1)
    assert gateway.handle(get()).status == OK
    throttled = gateway.handle(get())
    assert throttled.status == TOO_MANY_REQUESTS
    assert throttled.headers["RateLimit-Remaining"] == "0"


def test_a_generous_user_allowance_cannot_lift_an_exhausted_tenant(clock: Clock) -> None:
    """The intersection discipline of 14.12.4, applied to quota.

    A tenant limit exists precisely to bound the sum of its users, so a user
    who still has tokens must still be refused once the tenant is dry.
    """
    limiter = RateLimiter(now=clock)
    limiter.configure("tenant", TENANT, rate_per_minute=1, burst=1)
    limiter.configure("user", HUMAN, rate_per_minute=1000, burst=1000)
    assert limiter.check(Tier.AUTHENTICATED, tenant_id=TENANT, user_id=HUMAN).allowed
    decision = limiter.check(Tier.AUTHENTICATED, tenant_id=TENANT, user_id=HUMAN)
    assert not decision.allowed
    assert decision.binding_dimension == "tenant"


def test_a_refused_request_does_not_debit_the_dimensions_that_could_pay(clock: Clock) -> None:
    """Charging for a request that was refused would bill a client for nothing."""
    limiter = RateLimiter(now=clock)
    limiter.configure("tenant", TENANT, rate_per_minute=1, burst=1)
    limiter.configure("user", HUMAN, rate_per_minute=10, burst=10)
    limiter.check(Tier.AUTHENTICATED, tenant_id=TENANT, user_id=HUMAN)
    for _ in range(3):
        limiter.check(Tier.AUTHENTICATED, tenant_id=TENANT, user_id=HUMAN)
    user_bucket = limiter.check(Tier.AUTHENTICATED, user_id=HUMAN)
    assert user_bucket.remaining == 8, "only the one successful request debited the user bucket"


def test_the_bucket_refills_over_time(clock: Clock) -> None:
    limiter = RateLimiter(now=clock)
    limiter.configure("tenant", TENANT, rate_per_minute=60, burst=1)
    assert limiter.check(Tier.AUTHENTICATED, tenant_id=TENANT).allowed
    assert not limiter.check(Tier.AUTHENTICATED, tenant_id=TENANT).allowed
    clock.advance(timedelta(seconds=2))
    assert limiter.check(Tier.AUTHENTICATED, tenant_id=TENANT).allowed


def test_a_burst_never_exceeds_its_ceiling(clock: Clock) -> None:
    limiter = RateLimiter(now=clock)
    limiter.configure("tenant", TENANT, rate_per_minute=60, burst=3)
    clock.advance(timedelta(hours=1))
    allowed = sum(1 for _ in range(10) if limiter.check(Tier.AUTHENTICATED, tenant_id=TENANT).allowed)
    assert allowed == 3


def test_a_service_account_gets_its_own_tier(clock: Clock) -> None:
    limiter = RateLimiter(now=clock)
    decision = limiter.check(Tier.SERVICE_ACCOUNT, user_id="service-worker")
    assert decision.limit == 1000


# ------------------------------------------------------------- Idempotency


def test_a_mutating_request_without_a_key_is_refused(gateway: APIGateway) -> None:
    """03 §32.2 / 03 Rule 24."""
    response = gateway.handle(post(key=None))
    assert response.status == BAD_REQUEST
    assert response.body["error"]["code"] == ErrorCode.IDEMPOTENCY_KEY_REQUIRED.value


def test_a_get_needs_no_key(gateway: APIGateway) -> None:
    assert gateway.handle(get()).status == OK


def test_a_duplicate_key_replays_rather_than_re_running(gateway: APIGateway) -> None:
    calls: list[str] = []

    def counting(request: Request, principal_id: str, tenant_id: str) -> Response:
        calls.append(request.body["decision_id"])
        return Response(status=CREATED, body={"n": len(calls)})

    gateway.register_route(Route(Method.POST, "/counted", "decisions.approve", counting))
    request = Request(
        method=Method.POST,
        path="/v1/counted",
        token="tok",
        body={"decision_id": "dec-9"},
        headers={"Idempotency-Key": "key-9"},
    )
    first = gateway.handle(request)
    second = gateway.handle(request)
    assert calls == ["dec-9"], "the handler ran exactly once"
    assert second.body == first.body
    assert second.replayed
    assert second.headers["X-Idempotent-Replay"] == "true"


def test_the_same_key_with_a_different_body_is_a_409(gateway: APIGateway) -> None:
    """Replaying here would silently discard the second request."""
    gateway.handle(post(body={"decision_id": "dec-1"}, key="key-x"))
    conflict = gateway.handle(post(body={"decision_id": "dec-2"}, key="key-x"))
    assert conflict.status == CONFLICT
    assert conflict.body["error"]["code"] == ErrorCode.IDEMPOTENCY_KEY_REUSED.value


def test_two_principals_may_use_the_same_key_string(clock: Clock) -> None:
    """Nothing about a client-chosen key makes it globally unique."""
    store = IdempotencyStore(now=clock)
    digest = fingerprint("POST", "/x", {"a": 1})
    store.remember("principal-a", "key", digest, 201, {"who": "a"}, "req-1")
    assert store.lookup("principal-b", "key", digest) is None


def test_a_failed_attempt_does_not_reserve_the_key(clock: Clock) -> None:
    """Caching a 500 would make a transient failure permanent for 24 hours."""
    store = IdempotencyStore(now=clock)
    digest = fingerprint("POST", "/x", {})
    store.remember("p", "key", digest, 500, {"error": {}}, "req-1")
    assert store.lookup("p", "key", digest) is None


def test_a_stored_response_expires_after_the_retention_window(clock: Clock) -> None:
    store = IdempotencyStore(now=clock)
    digest = fingerprint("POST", "/x", {})
    store.remember("p", "key", digest, 201, {"ok": True}, "req-1")
    clock.advance(RETENTION - timedelta(minutes=1))
    assert store.lookup("p", "key", digest) is not None
    clock.advance(timedelta(minutes=2))
    assert store.lookup("p", "key", digest) is None


def test_reuse_detection_survives_key_ordering_in_the_body(clock: Clock) -> None:
    store = IdempotencyStore(now=clock)
    first = fingerprint("POST", "/x", {"a": 1, "b": 2})
    second = fingerprint("POST", "/x", {"b": 2, "a": 1})
    assert first == second
    store.remember("p", "key", first, 201, {}, "req-1")
    assert store.lookup("p", "key", second) is not None


def test_the_store_reports_and_purges_expired_entries(clock: Clock) -> None:
    store = IdempotencyStore(now=clock)
    store.remember("p", "key", fingerprint("POST", "/x", {}), 201, {}, "req-1")
    assert len(store) == 1
    clock.advance(RETENTION + timedelta(minutes=1))
    assert store.purge_expired() == 1
    assert len(store) == 0


def test_key_reuse_raises_from_the_store_itself(clock: Clock) -> None:
    store = IdempotencyStore(now=clock)
    store.remember("p", "key", fingerprint("POST", "/x", {"a": 1}), 201, {}, "req-1")
    with pytest.raises(KeyReused):
        store.lookup("p", "key", fingerprint("POST", "/x", {"a": 2}))


# -------------------------------------------------------------- Pagination


def test_offset_pagination_is_refused_not_ignored(gateway: APIGateway) -> None:
    """03 §32.6 states this as a Non-Violable Rule.

    Ignoring the parameter would serve the client a wrong page with no
    indication of why, which is worse than refusing.
    """
    response = gateway.handle(get(page="2", limit="50"))
    assert response.status == BAD_REQUEST
    assert response.body["error"]["code"] == ErrorCode.OFFSET_PAGINATION_REFUSED.value


@pytest.mark.parametrize("parameter", ["page", "offset", "skip", "start"])
def test_every_offset_spelling_is_refused(parameter: str) -> None:
    with pytest.raises(OffsetPaginationRefused):
        assert_no_offset({parameter: "2"})


def test_cursor_pagination_walks_the_whole_collection() -> None:
    seen: list[str] = []
    cursor: str | None = None
    while True:
        page = paginate(ITEMS, cursor=cursor, limit=3)
        seen.extend(item["id"] for item in page.data)
        cursor = page.next_cursor
        if cursor is None:
            break
    assert seen == [item["id"] for item in ITEMS]


def test_the_cursor_is_stable_when_earlier_items_are_removed() -> None:
    """Why 03 §32.6 forbids offsets: the page must not shift under the client."""
    page_one = paginate(ITEMS, limit=3)
    remaining = [item for item in ITEMS if item["id"] != "item-00"]
    page_two = paginate(remaining, cursor=page_one.next_cursor, limit=3)
    assert [item["id"] for item in page_two.data] == ["item-03", "item-04", "item-05"]


def test_the_pagination_envelope_matches_the_documented_shape() -> None:
    body = paginate(ITEMS, limit=3).to_body()
    assert set(body) == {"data", "pagination"}
    assert set(body["pagination"]) == {"next_cursor", "prev_cursor", "limit", "total_count"}
    assert body["pagination"]["total_count"] == 10


def test_the_last_page_has_no_next_cursor() -> None:
    page = paginate(ITEMS, limit=50)
    assert page.next_cursor is None
    assert page.prev_cursor is None
    assert len(page.data) == 10


def test_a_cursor_round_trips() -> None:
    encoded = encode_cursor({"id": "item-04"})
    assert decode_cursor(encoded) == {"id": "item-04"}


def test_a_forged_cursor_is_a_validation_error() -> None:
    with pytest.raises(ValidationError):
        decode_cursor("not-a-cursor-this-api-issued")


def test_the_limit_is_capped_and_must_be_positive() -> None:
    assert paginate(ITEMS, limit=10_000).limit == 200
    with pytest.raises(ValidationError):
        paginate(ITEMS, limit=0)


# ------------------------------------------------------- Errors and health


def test_a_domain_not_found_becomes_the_registered_error_code(gateway: APIGateway) -> None:
    """03 §32.3: "No ad-hoc error strings.\" """

    def missing(request: Request, principal_id: str, tenant_id: str) -> Response:
        raise NotFoundError("decision 'dec-nope' does not exist")

    gateway.register_route(Route(Method.GET, "/missing", "decisions.read", missing))
    response = gateway.handle(get(path="/v1/missing"))
    assert response.status == NOT_FOUND
    assert response.body["error"]["code"] == ErrorCode.NOT_FOUND.value


def test_a_domain_validation_error_becomes_a_400(gateway: APIGateway) -> None:
    def invalid(request: Request, principal_id: str, tenant_id: str) -> Response:
        raise ValidationError("price must be greater than 0")

    gateway.register_route(Route(Method.GET, "/invalid", "decisions.read", invalid))
    response = gateway.handle(get(path="/v1/invalid"))
    assert response.status == BAD_REQUEST
    assert response.body["error"]["code"] == ErrorCode.VALIDATION_FAILED.value


def test_the_error_envelope_carries_every_documented_field(gateway: APIGateway) -> None:
    body = gateway.handle(get(path="/v1/nothing")).body
    assert set(body["error"]) == {"code", "message", "details", "trace_id", "request_id", "timestamp"}


def test_every_error_code_is_a_member_of_the_closed_registry(gateway: APIGateway) -> None:
    codes = {code.value for code in ErrorCode}
    for request in (get(path="/v1/nothing"), get(token=None), post(key=None), get(page="1")):
        body = gateway.handle(request).body
        assert body["error"]["code"] in codes


def test_health_reports_ingress_signals(gateway: APIGateway) -> None:
    gateway.handle(get())
    gateway.handle(get(path="/v1/nothing"))
    health = gateway.health()
    assert health["routes"] == 2
    assert health["requests_handled"] == 2
    assert health["requests_refused"] == 1
    assert health["refusal_rate"] == 0.5
    assert health["journal_intact"]


def test_cross_subsystem_imports_are_confined_to_the_adapter() -> None:
    import pathlib

    package = pathlib.Path(__file__).resolve().parents[1]
    foreign = ("security_gateway", "decision_gateway", "workflow_engine", "agent_runtime")
    for source in package.glob("*.py"):
        if source.name == "security_adapter.py":
            continue
        for line in source.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped.startswith(("import ", "from ")):
                continue
            assert not any(
                name in stripped for name in foreign
            ), f"{source.name} imports another subsystem directly; route it through security_adapter.py"
