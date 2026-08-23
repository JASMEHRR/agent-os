"""Authorization Engine and Authorization Cache (21B §22.3, realizes 14.10).

The engine implements the eight-step decision flow of 14.10.2 literally and
in order. Two properties are load-bearing:

- **Authorization is computed at the point of action, not at token issuance**
  (21B §22.4). Step 3 reads the *live* permission graph. The token's claim
  snapshot is used only to pre-filter and to attribute, never as authority.
- **Step 8 is not optional.** The engine journals every decision itself
  rather than trusting callers to, so there is no code path that renders a
  decision without a corresponding immutable record.

Boundary checks in step 6 delegate to `kernel.BoundaryEnforcementEngine` —
the same six-boundary engine every other Gateway uses, unmodified, which is
the Stage S1 proof that the Layer 0 substrate is genuinely reusable.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from kernel.boundaries import (
    BoundaryContext,
    BoundaryEnforcementEngine,
    BoundaryType,
    BoundaryViolationError,
    RequestContext,
)
from security_gateway.enums import Decision, PrincipalType, SecurityEventType
from security_gateway.journal import SecurityEventJournal
from security_gateway.permissions import PermissionGraphEngine, covers
from security_gateway.roles import CapabilityEnforcer, CapabilityViolationError
from security_gateway.tokens import TokenClaims

#: [Engineering Decision] 14.10.3 escalates when a request is "near a boundary
#: threshold" without publishing the margin. Ten percent of remaining budget
#: is the starting value; it is tunable and is not a constitutional constant.
NEAR_BOUNDARY_MARGIN = 0.10


@dataclass(frozen=True)
class AuthorizationRequest:
    """One action on one resource, by one authenticated principal."""

    action: str
    resource_id: str
    resource_tenant_id: str
    #: Present when the action reviews or approves another principal's output,
    #: which is what step 5 checks for separation-of-duties conflicts.
    subject_principal_id: str | None = None
    cost: float = 0.0
    min_confidence: float = 0.0
    confidence: float = 1.0
    required_autonomy_level: int = 0
    not_before: datetime | None = None
    not_after: datetime | None = None
    #: Set by anomaly detectors; forces escalation rather than denial (14.10.3).
    anomaly_flagged: bool = False
    cross_scope_impact: bool = False


@dataclass(frozen=True)
class AuthorizationResult:
    decision: Decision
    principal_id: str
    action: str
    resource_id: str
    reason: str
    graph_revision: int
    decided_at: datetime
    #: Set when the decision is ESCALATE — who it routes to (14.10.3).
    escalate_to: str | None = None

    @property
    def allowed(self) -> bool:
        return self.decision == Decision.ALLOW


@dataclass
class AuthorizationCache:
    """Bounded caching within token TTL, validated against the revocation list (14.10.4).

    A first-class component rather than an optimization: 21B §22.4 names it
    the primary mitigation available for CIR-004. Rule 16 of document 14 —
    "No cached authorization surviving beyond its maximum TTL" — is enforced
    structurally: entries carry an expiry that can never exceed the expiry of
    the token that produced them.
    """

    is_revoked: Callable[[str], bool]
    now: Callable[[], datetime] = field(default=lambda: datetime.now(UTC))
    _entries: dict[tuple[str, str, str], tuple[AuthorizationResult, datetime]] = field(default_factory=dict, init=False)
    hits: int = field(default=0, init=False)
    misses: int = field(default=0, init=False)

    def put(self, result: AuthorizationResult, token_expires_at: datetime, ttl: timedelta | None = None) -> None:
        if result.decision != Decision.ALLOW:
            return  # only Allow decisions are worth caching; denials must re-evaluate
        expiry = min(token_expires_at, self.now() + ttl) if ttl is not None else token_expires_at
        self._entries[(result.principal_id, result.action, result.resource_id)] = (result, expiry)

    def get(self, principal_id: str, action: str, resource_id: str) -> AuthorizationResult | None:
        key = (principal_id, action, resource_id)
        cached = self._entries.get(key)
        if cached is None:
            self.misses += 1
            return None
        result, expiry = cached
        if self.now() >= expiry or self.is_revoked(principal_id):
            del self._entries[key]
            self.misses += 1
            return None
        self.hits += 1
        return result

    def invalidate_principal(self, principal_id: str) -> int:
        """Broadcast invalidation on revocation or permission-graph change (14.10.4)."""
        stale = [k for k in self._entries if k[0] == principal_id]
        for key in stale:
            del self._entries[key]
        return len(stale)

    def clear(self) -> None:
        self._entries.clear()

    @property
    def size(self) -> int:
        return len(self._entries)


@dataclass
class AuthorizationEngine:
    """The eight-step decision flow of 14.10.2, producing Allow, Deny or Escalate."""

    graph_engine: PermissionGraphEngine
    capability_enforcer: CapabilityEnforcer
    journal: SecurityEventJournal
    #: Resolves a principal's current budget headroom, for step 6.
    budget_remaining: Callable[[str], float]
    #: Resolves the escalation target by decision risk, per 14.10.3.
    escalation_target: Callable[[AuthorizationRequest, TokenClaims], str]
    #: Validates the delegation chain when the principal acts under delegation,
    #: returning its intersected scope. Raises on a broken chain (14.14.4).
    delegated_scope: Callable[[str], frozenset[str]]
    now: Callable[[], datetime] = field(default=lambda: datetime.now(UTC))
    boundaries: BoundaryEnforcementEngine = field(default_factory=BoundaryEnforcementEngine)

    def authorize(self, claims: TokenClaims, request: AuthorizationRequest) -> AuthorizationResult:
        # Step 1-2: the caller has presented an authenticated token; extract
        # the principal and the resource/action pair.
        principal_id = claims.principal_id

        # Step 3: query the LIVE permission graph, not the token's snapshot.
        graph = self.graph_engine.graph_for(principal_id)

        # Step 4: evaluate against capability signature, roles, autonomy
        # level, and scope boundaries.
        try:
            self.capability_enforcer.check(principal_id, request.action)
        except CapabilityViolationError as exc:
            return self._render(Decision.DENY, claims, request, str(exc), graph.revision)

        if not graph.permits(request.action):
            return self._render(
                Decision.DENY,
                claims,
                request,
                f"effective permissions {sorted(graph.effective)} do not cover '{request.action}'",
                graph.revision,
            )

        if claims.delegation_window_ends_at is not None or self.delegated_scope(principal_id):
            delegated = self.delegated_scope(principal_id)
            if delegated and not any(covers(grant, request.action) for grant in delegated):
                return self._render(
                    Decision.DENY,
                    claims,
                    request,
                    f"delegation chain scope {sorted(delegated)} does not cover '{request.action}'",
                    graph.revision,
                )

        if claims.autonomy_level is not None and claims.autonomy_level < request.required_autonomy_level:
            return self._render(
                Decision.DENY,
                claims,
                request,
                f"autonomy level {claims.autonomy_level} is below the required {request.required_autonomy_level}",
                graph.revision,
            )

        if claims.tenant_id != request.resource_tenant_id:
            return self._render(
                Decision.DENY,
                claims,
                request,
                f"principal tenant '{claims.tenant_id}' may not act on tenant "
                f"'{request.resource_tenant_id}' resources without a bilateral grant (14 rule 15)",
                graph.revision,
            )

        # Step 5: separation-of-duties — a principal may not review, approve
        # or audit its own output (14.17).
        if request.subject_principal_id is not None and request.subject_principal_id == principal_id:
            return self._render(
                Decision.DENY,
                claims,
                request,
                "separation of duties: a principal may not act as reviewer of its own output (14.17.5)",
                graph.revision,
            )

        # Step 6: budget and temporal constraints, via the kernel's six-boundary engine.
        headroom = self.budget_remaining(principal_id)
        try:
            self.boundaries.enforce(
                BoundaryContext(
                    tenant_id=claims.tenant_id,
                    scope=set(graph.effective),
                    authority_level=claims.autonomy_level if claims.autonomy_level is not None else 4,
                    confidence=request.confidence,
                    budget_remaining=headroom,
                    now=self.now(),
                ),
                RequestContext(
                    tenant_id=request.resource_tenant_id,
                    required_scope=set(),  # covered by the graph check in step 4
                    required_authority_level=request.required_autonomy_level,
                    min_confidence=request.min_confidence,
                    cost=request.cost,
                    not_before=request.not_before,
                    not_after=request.not_after,
                ),
            )
        except BoundaryViolationError as exc:
            # A confidence shortfall is a judgement call, not a hard bar: 14.10.3
            # routes low confidence to escalation. Every other boundary denies.
            if exc.boundary == BoundaryType.CONFIDENCE:
                return self._render(Decision.ESCALATE, claims, request, f"escalated: {exc.reason}", graph.revision)
            return self._render(Decision.DENY, claims, request, str(exc), graph.revision)

        # Step 7: render. Escalation triggers of 14.10.3 that survived step 6.
        escalation_reason = self._escalation_reason(request, headroom)
        if escalation_reason is not None:
            return self._render(Decision.ESCALATE, claims, request, escalation_reason, graph.revision)

        return self._render(Decision.ALLOW, claims, request, "within effective permissions", graph.revision)

    def _escalation_reason(self, request: AuthorizationRequest, headroom: float) -> str | None:
        if request.anomaly_flagged:
            return "escalated: anomaly detection flagged an unusual pattern (14.10.3)"
        if request.cross_scope_impact:
            return "escalated: action has cross-scope impact (14.10.3)"
        if headroom > 0 and request.cost > 0 and (headroom - request.cost) < headroom * NEAR_BOUNDARY_MARGIN:
            return "escalated: request is near the budget boundary threshold (14.10.3)"
        return None

    def _render(
        self,
        decision: Decision,
        claims: TokenClaims,
        request: AuthorizationRequest,
        reason: str,
        graph_revision: int,
    ) -> AuthorizationResult:
        """Step 8: the decision is logged immutably. Action proceeds only on Allow."""
        result = AuthorizationResult(
            decision=decision,
            principal_id=claims.principal_id,
            action=request.action,
            resource_id=request.resource_id,
            reason=reason,
            graph_revision=graph_revision,
            decided_at=self.now(),
            escalate_to=self.escalation_target(request, claims) if decision == Decision.ESCALATE else None,
        )
        self.journal.record(
            event_type={
                Decision.ALLOW: SecurityEventType.AUTHORIZATION_ALLOWED,
                Decision.DENY: SecurityEventType.AUTHORIZATION_DENIED,
                Decision.ESCALATE: SecurityEventType.AUTHORIZATION_ESCALATED,
            }[decision],
            principal_id=claims.principal_id,
            tenant_id=claims.tenant_id,
            outcome=decision.value,
            detail={
                "action": request.action,
                "resource_id": request.resource_id,
                "reason": reason,
                "graph_revision": graph_revision,
                "escalate_to": result.escalate_to,
                "principal_type": claims.principal_type.value
                if isinstance(claims.principal_type, PrincipalType)
                else str(claims.principal_type),
            },
        )
        return result
