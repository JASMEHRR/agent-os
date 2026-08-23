"""Shared enumerations for the Security Gateway.

Kept in one module so identity, authorization, revocation and incident code
share exactly one spelling of each constitutional term (Part IV Section 26 —
constitutional terminology must not drift).
"""

from __future__ import annotations

from enum import StrEnum


class PrincipalType(StrEnum):
    """The five principal categories of 14.8.1."""

    AGENT = "agent"
    HUMAN = "human"
    SERVICE = "service"
    WORKFLOW = "workflow"
    GATEWAY = "gateway"


class PrincipalStatus(StrEnum):
    """Identity lifecycle states of 14.8.2."""

    DESIGNED = "designed"
    REGISTERED = "registered"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    RETIRED = "retired"
    ARCHIVED = "archived"


class Decision(StrEnum):
    """Authorization outcomes of 14.10.2 step 7."""

    ALLOW = "allow"
    DENY = "deny"
    ESCALATE = "escalate"


class DelegationType(StrEnum):
    """Delegation types of 14.14.2."""

    STANDING_ORDER = "standing_order"
    TEMPORARY_ROLE = "temporary_role_assignment"
    TASK = "task_delegation"
    EMERGENCY = "emergency"


class RevocationTrigger(StrEnum):
    """Revocation triggers of 14.15.2."""

    HUMAN_COMMAND = "human_command"
    SUSPENSION = "suspension"
    RETIREMENT = "retirement"
    EXPIRY = "expiry"
    ANOMALY_DETECTION = "anomaly_detection"
    CONSTITUTIONAL_VIOLATION = "constitutional_violation"


class IncidentCategory(StrEnum):
    """The six-category security incident taxonomy of 14.29.1.

    Distinct from the Kernel's five-category *failure* taxonomy — 21B §22.9
    is explicit that both apply simultaneously.
    """

    OPERATIONAL_ANOMALY = "operational_anomaly"
    AUTHENTICATION_BREACH = "authentication_breach"
    AUTHORIZATION_VIOLATION = "authorization_violation"
    ISOLATION_BREACH = "isolation_breach"
    SECRET_EXPOSURE = "secret_exposure"  # nosec B105
    CONSTITUTIONAL_VIOLATION = "constitutional_violation"


class Classification(StrEnum):
    """Sensitivity classification of 14.5.1."""

    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"
    SOVEREIGN = "sovereign"


# Members marked below carry names Bandit's B105 check reads as hardcoded
# credentials. They are event-type labels; the names are constitutional
# terminology and may not be renamed to appease a linter (Part IV, 26).
class SecurityEventType(StrEnum):
    """Event types written to the Security Event Journal.

    Covers the emission set 14.27.1 requires: authentication attempts by
    outcome, authorization decisions by outcome, delegation creation and
    revocation, permission graph changes, boundary crossings, token issuance
    and expiry, and secret reference usage.
    """

    IDENTITY_REGISTERED = "identity.registered"
    IDENTITY_TRANSITIONED = "identity.transitioned"
    AUTHENTICATION_SUCCEEDED = "authentication.succeeded"
    AUTHENTICATION_FAILED = "authentication.failed"
    TOKEN_ISSUED = "token.issued"  # nosec B105
    TOKEN_REJECTED = "token.rejected"  # nosec B105
    AUTHORIZATION_ALLOWED = "authorization.allowed"
    AUTHORIZATION_DENIED = "authorization.denied"
    AUTHORIZATION_ESCALATED = "authorization.escalated"
    PERMISSION_GRAPH_CHANGED = "permission_graph.changed"
    DELEGATION_CREATED = "delegation.created"
    DELEGATION_REVOKED = "delegation.revoked"
    BOUNDARY_CROSSING = "boundary.crossing"
    REVOCATION_EXECUTED = "revocation.executed"
    REVOCATION_PARTIAL = "revocation.partial"
    SECRET_REFERENCE_USED = "secret.reference_used"  # nosec B105
    SECRET_ROTATED = "secret.rotated"  # nosec B105
    INCIDENT_RAISED = "incident.raised"
