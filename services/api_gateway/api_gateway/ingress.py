"""Request, response, and the error envelope (02.3.1, 03 §32).

The Gateway is deliberately transport-agnostic. `Request` and `Response` are
plain records rather than a web framework's types, because 03's named
framework cannot be adopted while CIR-001 is unresolved (Build Spec Section 6
rule 9 forbids resolving it by unilateral interpretation). What is implemented
here is every ingress *semantic* the constitution requires; what is missing is
the socket.

`02.3.1`: "All external ingress. No external client communicates directly with
any internal service."
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from core.exceptions import AgentOSError


class Method(StrEnum):
    """The methods of 03 §32.2."""

    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    PATCH = "PATCH"
    DELETE = "DELETE"

    @property
    def is_mutating(self) -> bool:
        """03 §32.2 — mutating methods must carry an `Idempotency-Key`."""
        return self is not Method.GET


# The status codes of 03 §32.2, as named constants rather than an enum: they
# are integers on the wire and comparing them to one is the common operation.
OK = 200
CREATED = 201
ACCEPTED = 202
NO_CONTENT = 204
BAD_REQUEST = 400
UNAUTHORIZED = 401
FORBIDDEN = 403
NOT_FOUND = 404
CONFLICT = 409
UNPROCESSABLE = 422
TOO_MANY_REQUESTS = 429
INTERNAL_ERROR = 500


class ErrorCode(StrEnum):
    """03 §32.3: "No ad-hoc error strings."

    The registry is closed. A handler that wants a new failure mode adds a
    member here, which is what makes the set of things the API can say
    enumerable rather than emergent.
    """

    VALIDATION_FAILED = "VALIDATION_FAILED"
    NOT_FOUND = "NOT_FOUND"
    UNAUTHENTICATED = "UNAUTHENTICATED"
    UNAUTHORIZED = "UNAUTHORIZED"
    RATE_LIMITED = "RATE_LIMITED"
    IDEMPOTENCY_KEY_REQUIRED = "IDEMPOTENCY_KEY_REQUIRED"
    IDEMPOTENCY_KEY_REUSED = "IDEMPOTENCY_KEY_REUSED"
    UNSUPPORTED_VERSION = "UNSUPPORTED_VERSION"
    OFFSET_PAGINATION_REFUSED = "OFFSET_PAGINATION_REFUSED"
    ROUTE_NOT_FOUND = "ROUTE_NOT_FOUND"
    BUSINESS_RULE_VIOLATION = "BUSINESS_RULE_VIOLATION"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class IngressRefused(AgentOSError):
    """A request the Gateway refused before it reached any internal service.

    Carries the error code, so the envelope is built from the refusal rather
    than reconstructed by the caller.
    """

    def __init__(self, code: ErrorCode, status: int, message: str, **details: Any) -> None:
        super().__init__(message)
        self.code = code
        self.status = status
        self.details = details


@dataclass(frozen=True)
class Request:
    """One inbound request at the external boundary."""

    method: Method
    #: Full path including the version prefix, e.g. `/v1/decisions`.
    path: str
    #: `Authorization: Bearer <token>` reduced to the token itself.
    token: str | None = None
    query: dict[str, str] = field(default_factory=dict)
    body: dict[str, Any] = field(default_factory=dict)
    headers: dict[str, str] = field(default_factory=dict)
    #: Present for API-key clients; rate limiting is dimensioned on it too.
    api_key: str | None = None

    @property
    def idempotency_key(self) -> str | None:
        return self.headers.get("Idempotency-Key")


@dataclass(frozen=True)
class Response:
    """One outbound response, including the headers the standards require."""

    status: int
    body: dict[str, Any]
    headers: dict[str, str] = field(default_factory=dict)
    #: True when this response was replayed from the idempotency store rather
    #: than produced by re-running the handler (03 §32.2).
    replayed: bool = False

    @property
    def ok(self) -> bool:
        return 200 <= self.status < 300


def error_body(
    code: ErrorCode,
    message: str,
    request_id: str,
    trace_id: str,
    now: datetime | None = None,
    **details: Any,
) -> dict[str, Any]:
    """The error structure of 03 §32.3, verbatim in shape.

    Every error carries `trace_id` and `request_id`. An error a human cannot
    trace back to the request that caused it is an error they cannot act on.
    """
    return {
        "error": {
            "code": code.value,
            "message": message,
            "details": details,
            "trace_id": trace_id,
            "request_id": request_id,
            "timestamp": (now or datetime.now(UTC)).isoformat(),
        }
    }
