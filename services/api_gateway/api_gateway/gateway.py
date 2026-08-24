"""The API Gateway — all external ingress (02.3.1).

`02.3.1`: "All external ingress. No external client communicates directly with
any internal service." Everything the constitution asks this module to
centralize lives here: authentication, authorization, rate limiting, URI-path
versioning, cursor pagination, idempotency, request identity and trace
context, and the error envelope.

**The Gateway holds no business logic.** It routes; the handler decides. A
test asserts no domain verb (`approve`, `execute`, `decide`, `override`) has
appeared on `APIGateway`, because a Gateway that starts deciding is a second
place where authority lives, and 02.3.1's centralization argument then works
against the system rather than for it.

**Authentication and authorization are delegated to the Trust Plane.** The
Gateway asks the Security Gateway and enforces the answer; it does not
maintain its own view of who may do what. 14's Permission Intersection Rule
only holds if there is one authority computing it.

Ordered pipeline, and the order is load-bearing:

1. request identity and trace context (so a refusal is traceable);
2. version resolution (an unknown version is refused before anything else);
3. authentication;
4. rate limiting (after identity, because the tier depends on who is asking);
5. authorization for the route;
6. offset-pagination refusal;
7. idempotency lookup or reservation;
8. dispatch to the handler;
9. response emission and idempotent storage.

Rate limiting sits after authentication deliberately: an anonymous tier
applied to an authenticated client would throttle a paying tenant at the
anonymous rate, and a tier inferred before the token was validated could be
claimed by the client itself.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol

from api_gateway.idempotency import IdempotencyStore, KeyReused, fingerprint
from api_gateway.ingress import (
    BAD_REQUEST,
    CONFLICT,
    FORBIDDEN,
    INTERNAL_ERROR,
    NOT_FOUND,
    TOO_MANY_REQUESTS,
    UNAUTHORIZED,
    UNPROCESSABLE,
    ErrorCode,
    IngressRefused,
    Method,
    Request,
    Response,
    error_body,
)
from api_gateway.pagination import OffsetPaginationRefused, assert_no_offset
from api_gateway.ratelimit import RateLimiter, Tier
from core.exceptions import AgentOSError, NotFoundError, ValidationError
from kernel.journal import ImmutableJournal
from kernel.signals import SignalEmitter, SignalType

#: 02.3.1 — URI-path versioning. The set is closed: an unrecognised version is
#: refused rather than routed to the newest, which would silently change a
#: client's contract underneath it.
SUPPORTED_VERSIONS = ("v1",)


class IngressAuthority(Protocol):
    """Authentication and authorization, delegated to the Trust Plane."""

    def authenticate(self, token: str) -> tuple[str, str]: ...

    def tier_of(self, principal_id: str) -> Tier: ...

    def permits(self, token: str, principal_id: str, permission: str, tenant_id: str) -> bool: ...


@dataclass(frozen=True)
class Route:
    """One registered route. The handler is the only thing that decides."""

    method: Method
    #: Version-less path, e.g. `/decisions/pending`. The version prefix is
    #: stripped before matching so one handler serves every version that
    #: exposes it.
    path: str
    permission: str
    handler: Callable[[Request, str, str], Response]
    #: False for endpoints deliberately reachable without a token.
    requires_authentication: bool = True


@dataclass
class APIGateway:
    """Layer 13. Stateless per 02.3.1; scaling is horizontal behind a balancer."""

    authority: IngressAuthority
    signals: SignalEmitter
    now: Callable[[], datetime] = field(default=lambda: datetime.now(UTC))
    request_ids: Callable[[], str] = field(default=lambda: f"req-{uuid.uuid4().hex[:12]}")

    def __post_init__(self) -> None:
        self.limiter = RateLimiter(now=self.now)
        self.idempotency = IdempotencyStore(now=self.now)
        self.journal = ImmutableJournal()
        self._routes: dict[tuple[Method, str], Route] = {}
        self._handled = 0
        self._refused = 0

    # --------------------------------------------------------------- Routing

    def register_route(self, route: Route) -> Route:
        key = (route.method, route.path)
        if key in self._routes:
            raise AgentOSError(f"{route.method.value} {route.path} is already routed")
        self._routes[key] = route
        return route

    # --------------------------------------------------------------- Ingress

    def handle(self, request: Request) -> Response:
        """The single entry point. Every external request passes through here."""
        request_id = self.request_ids()
        trace_id = request.headers.get("X-Trace-Id") or f"trace-{uuid.uuid4().hex[:12]}"
        self.signals.emit(
            SignalType.EVENT,
            "gateway.request_received",
            request.headers.get("X-Tenant-Id", "unknown"),
            request_id=request_id,
            method=request.method.value,
            path=request.path,
        )
        try:
            response = self._pipeline(request, request_id, trace_id)
        except IngressRefused as refusal:
            response = self._refusal(refusal, request_id, trace_id)
        except (ValidationError, NotFoundError, AgentOSError) as failure:
            response = self._refusal(_classify(failure), request_id, trace_id)
        except Exception as failure:  # pragma: no cover - defensive
            response = Response(
                status=INTERNAL_ERROR,
                body=error_body(ErrorCode.INTERNAL_ERROR, str(failure), request_id, trace_id, self.now()),
            )

        headers = dict(response.headers)
        headers.setdefault("X-Request-Id", request_id)
        headers.setdefault("X-Trace-Id", trace_id)
        final = Response(status=response.status, body=response.body, headers=headers, replayed=response.replayed)
        self._handled += 1
        if not final.ok:
            self._refused += 1
        self.signals.emit(
            SignalType.EVENT,
            "gateway.response_sent",
            request.headers.get("X-Tenant-Id", "unknown"),
            request_id=request_id,
            status=final.status,
        )
        return final

    def _pipeline(self, request: Request, request_id: str, trace_id: str) -> Response:
        version, path = _split_version(request.path)
        if version not in SUPPORTED_VERSIONS:
            raise IngressRefused(
                ErrorCode.UNSUPPORTED_VERSION,
                NOT_FOUND,
                f"'{version}' is not a supported API version",
                supported=list(SUPPORTED_VERSIONS),
            )

        route = self._routes.get((request.method, path))
        if route is None:
            raise IngressRefused(ErrorCode.ROUTE_NOT_FOUND, NOT_FOUND, f"no route for {request.method.value} {path}")

        principal_id, tenant_id, tier = self._identify(request, route)

        limit = self.limiter.check(
            tier, tenant_id=tenant_id or None, user_id=principal_id or None, api_key=request.api_key
        )
        if not limit.allowed:
            refusal = IngressRefused(
                ErrorCode.RATE_LIMITED,
                TOO_MANY_REQUESTS,
                f"rate limit exhausted on the {limit.binding_dimension} quota",
                dimension=limit.binding_dimension,
            )
            response = self._refusal(refusal, request_id, trace_id)
            return Response(status=response.status, body=response.body, headers=limit.headers())

        if route.requires_authentication and not self.authority.permits(
            request.token or "", principal_id, route.permission, tenant_id
        ):
            raise IngressRefused(
                ErrorCode.UNAUTHORIZED,
                FORBIDDEN,
                f"'{principal_id}' does not hold '{route.permission}'",
                permission=route.permission,
            )

        try:
            assert_no_offset(request.query)
        except OffsetPaginationRefused as refusal:
            raise IngressRefused(ErrorCode.OFFSET_PAGINATION_REFUSED, BAD_REQUEST, str(refusal)) from refusal

        digest = ""
        if request.method.is_mutating:
            key = request.idempotency_key
            if not key:
                raise IngressRefused(
                    ErrorCode.IDEMPOTENCY_KEY_REQUIRED,
                    BAD_REQUEST,
                    f"{request.method.value} requires an Idempotency-Key header (03 §32.2)",
                )
            digest = fingerprint(request.method.value, path, request.body)
            try:
                stored = self.idempotency.lookup(principal_id, key, digest)
            except KeyReused as reuse:
                raise IngressRefused(ErrorCode.IDEMPOTENCY_KEY_REUSED, CONFLICT, str(reuse)) from reuse
            if stored is not None:
                self._journal(request_id, "replayed", path=path, principal_id=principal_id)
                return Response(
                    status=stored.status,
                    body=stored.body,
                    headers={"X-Idempotent-Replay": "true", **limit.headers()},
                    replayed=True,
                )

        response = route.handler(request, principal_id, tenant_id)

        if request.method.is_mutating and request.idempotency_key:
            self.idempotency.remember(
                principal_id, request.idempotency_key, digest, response.status, response.body, request_id
            )
        self._journal(
            request_id,
            "handled",
            path=path,
            method=request.method.value,
            principal_id=principal_id,
            status=response.status,
        )
        return Response(
            status=response.status,
            body=response.body,
            headers={**limit.headers(), **response.headers},
        )

    def _identify(self, request: Request, route: Route) -> tuple[str, str, Tier]:
        if not request.token:
            if route.requires_authentication:
                raise IngressRefused(ErrorCode.UNAUTHENTICATED, UNAUTHORIZED, "this endpoint requires a bearer token")
            return ("", request.headers.get("X-Tenant-Id", ""), Tier.ANONYMOUS)
        try:
            principal_id, tenant_id = self.authority.authenticate(request.token)
        except Exception as failure:
            raise IngressRefused(
                ErrorCode.UNAUTHENTICATED, UNAUTHORIZED, f"authentication failed: {failure}"
            ) from failure
        return (principal_id, tenant_id, self.authority.tier_of(principal_id))

    def _refusal(self, refusal: IngressRefused, request_id: str, trace_id: str) -> Response:
        self._journal(request_id, "refused", code=refusal.code.value, status=refusal.status)
        return Response(
            status=refusal.status,
            body=error_body(refusal.code, str(refusal), request_id, trace_id, self.now(), **refusal.details),
        )

    # ---------------------------------------------------------------- Health

    def health(self) -> Mapping[str, Any]:
        return {
            "routes": len(self._routes),
            "versions": list(SUPPORTED_VERSIONS),
            "requests_handled": self._handled,
            "requests_refused": self._refused,
            "refusal_rate": round(self._refused / self._handled, 4) if self._handled else 0.0,
            "idempotency_keys_held": len(self.idempotency),
            "journal_entries": len(self.journal),
            "journal_intact": self.journal.verify_chain(),
        }

    def _journal(self, request_id: str, action: str, **detail: Any) -> None:
        self.journal.append({"kind": "ingress", "action": action, "request_id": request_id, **detail})


def _split_version(path: str) -> tuple[str, str]:
    parts = path.strip("/").split("/", 1)
    version = parts[0] if parts else ""
    remainder = "/" + parts[1] if len(parts) > 1 else "/"
    return version, remainder


def _classify(failure: Exception) -> IngressRefused:
    """Maps a domain exception to the closed error registry of 03 §32.3."""
    if isinstance(failure, NotFoundError):
        return IngressRefused(ErrorCode.NOT_FOUND, NOT_FOUND, str(failure))
    if isinstance(failure, ValidationError):
        return IngressRefused(ErrorCode.VALIDATION_FAILED, BAD_REQUEST, str(failure))
    return IngressRefused(ErrorCode.BUSINESS_RULE_VIOLATION, UNPROCESSABLE, str(failure))
