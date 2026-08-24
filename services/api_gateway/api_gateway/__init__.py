"""API Gateway — all external ingress (02.3.1, per Build Spec Stage S8).

`02.3.1`: "All external ingress. No external client communicates directly with
any internal service."

Cross-cutting concerns live here so that no internal service reimplements
them: authentication and authorization (delegated to the Trust Plane), rate
limiting across three dimensions, URI-path versioning, mandatory idempotency
keys on mutating endpoints, cursor-only pagination, request identity and trace
context injection, and one error envelope.

The module is transport-agnostic. Every ingress semantic the constitution
requires is implemented; the HTTP server is not, because 03's named framework
cannot be adopted while CIR-001 is unresolved.
"""

from api_gateway.gateway import SUPPORTED_VERSIONS, APIGateway, IngressAuthority, Route
from api_gateway.idempotency import RETENTION, IdempotencyStore, KeyReused, StoredResponse, fingerprint
from api_gateway.ingress import (
    ACCEPTED,
    BAD_REQUEST,
    CONFLICT,
    CREATED,
    FORBIDDEN,
    INTERNAL_ERROR,
    NO_CONTENT,
    NOT_FOUND,
    OK,
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
from api_gateway.pagination import (
    DEFAULT_LIMIT,
    MAX_LIMIT,
    OFFSET_PARAMETERS,
    OffsetPaginationRefused,
    Page,
    assert_no_offset,
    decode_cursor,
    encode_cursor,
    paginate,
)
from api_gateway.ratelimit import TIER_LIMITS, Bucket, Decision, RateLimiter, Tier
from api_gateway.security_adapter import SecurityGatewayIngressAuthority

__all__ = [
    "APIGateway",
    "IngressAuthority",
    "Route",
    "SUPPORTED_VERSIONS",
    "Request",
    "Response",
    "Method",
    "ErrorCode",
    "IngressRefused",
    "error_body",
    "OK",
    "CREATED",
    "ACCEPTED",
    "NO_CONTENT",
    "BAD_REQUEST",
    "UNAUTHORIZED",
    "FORBIDDEN",
    "NOT_FOUND",
    "CONFLICT",
    "UNPROCESSABLE",
    "TOO_MANY_REQUESTS",
    "INTERNAL_ERROR",
    "RateLimiter",
    "Tier",
    "TIER_LIMITS",
    "Bucket",
    "Decision",
    "IdempotencyStore",
    "StoredResponse",
    "KeyReused",
    "RETENTION",
    "fingerprint",
    "paginate",
    "Page",
    "encode_cursor",
    "decode_cursor",
    "assert_no_offset",
    "OffsetPaginationRefused",
    "OFFSET_PARAMETERS",
    "DEFAULT_LIMIT",
    "MAX_LIMIT",
    "SecurityGatewayIngressAuthority",
]
