"""Security Gateway — the nine Public Interfaces of 21B §22.5.

This module composes the internal components; it holds no policy of its own.
Each public method maps one-to-one onto a row of the 21B §22.5 interface
table, with no undocumented additions (Part IV Section 25(e)).

| 21B §22.5 interface           | Method                              |
|-------------------------------|-------------------------------------|
| Authentication                | `authenticate`                      |
| Authorization                 | `authorize`                         |
| Identity Registration         | `register_identity`                 |
| Delegation Management         | `manage_delegation`                 |
| Revocation Command            | `revoke`                            |
| Secret Reference Resolution   | `resolve_secret_reference`          |
| Security Context              | `create_security_context` / `validate_security_context` |
| Security Event Journal Query  | `query_journal`                     |
| Security Health               | `health`                            |

The Gateway also participates in the Panic Protocol via `kernel.PanicProtocol`
(21A §5.2 item 8) — a panic halts token issuance and authorization outright.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from core.exceptions import AgentOSError
from kernel.panic import PanicProtocol
from persistence.in_memory import InMemoryRepository
from security_gateway.authorization import (
    AuthorizationCache,
    AuthorizationEngine,
    AuthorizationRequest,
    AuthorizationResult,
)
from security_gateway.context import SecurityContext, SecurityContextFactory
from security_gateway.delegation import BrokenChainError, Delegation, DelegationManager
from security_gateway.enforcer import ConstitutionalEnforcer, ConstitutionalViolationError
from security_gateway.enums import (
    Decision,
    DelegationType,
    IncidentCategory,
    PrincipalStatus,
    PrincipalType,
    RevocationTrigger,
    SecurityEventType,
)
from security_gateway.identity import (
    IdentityRegistry,
    Principal,
    RegistrationController,
    RegistrationRequest,
)
from security_gateway.incidents import Incident, IncidentClassifier
from security_gateway.isolation import IsolationEnforcer
from security_gateway.journal import SecurityEvent, SecurityEventJournal
from security_gateway.permissions import PermissionGraphEngine
from security_gateway.revocation import RevocationEngine, RevocationRecord
from security_gateway.roles import CapabilityEnforcer, RoleController
from security_gateway.secrets_governor import (
    CredentialGovernor,
    InjectionGrant,
    SecretGovernor,
    SecretStore,
)
from security_gateway.tokens import AuthenticationError, TokenClaims, TokenService

#: [Engineering Decision] Default budget headroom when no Cost Manager exists.
#: `cost_manager` is a Stage S3 module; until it exists the Gateway must not
#: pretend to know a principal's budget, and must not fabricate a limit that
#: would silently deny. Callers inject a real resolver once S3 lands.
UNMETERED_BUDGET = float("inf")


class GatewayHaltedError(AgentOSError):
    """The Panic Protocol has been triggered; the Gateway issues and authorizes nothing."""


@dataclass
class SecurityGateway:
    """The trust substrate (21B §22.1). Depends only on `kernel`, `core`, `persistence`."""

    signing_key: bytes
    secret_store: SecretStore
    now: Callable[[], datetime] = field(default=lambda: datetime.now(UTC))
    #: Injected once `cost_manager` (Stage S3) exists; unmetered until then.
    budget_resolver: Callable[[str], float] | None = None
    panic: PanicProtocol = field(default_factory=PanicProtocol)

    def __post_init__(self) -> None:
        self.journal = SecurityEventJournal(InMemoryRepository())
        self.registry = IdentityRegistry(InMemoryRepository())
        self.registration = RegistrationController(self.registry)
        self.graph_engine = PermissionGraphEngine()
        self.capabilities = CapabilityEnforcer()
        self.roles = RoleController(now=self.now)
        self.tokens = TokenService(signing_key=self.signing_key, now=self.now)
        self.credentials = CredentialGovernor(now=self.now)
        self.secrets = SecretGovernor(store=self.secret_store, now=self.now)
        self.contexts = SecurityContextFactory()
        self.incidents = IncidentClassifier()
        self.enforcer = ConstitutionalEnforcer()
        self.revocations = RevocationEngine(now=self.now)
        self.isolation = IsolationEnforcer(is_human=self._is_human, now=self.now)
        self.delegations = DelegationManager(
            graph_engine=self.graph_engine,
            is_actionable=self._is_actionable,
            now=self.now,
        )
        self.cache = AuthorizationCache(is_revoked=self.revocations.is_revoked, now=self.now)
        self.authorization = AuthorizationEngine(
            graph_engine=self.graph_engine,
            capability_enforcer=self.capabilities,
            journal=self.journal,
            budget_remaining=self._budget_remaining,
            escalation_target=self._escalation_target,
            delegated_scope=self._delegated_scope,
            now=self.now,
        )
        self._halted = False
        self.panic.register(self._halt)

    # ---------------------------------------------------------------- Identity

    def bootstrap_human_sovereign(self, principal_id: str, name: str, tenant_id: str) -> Principal:
        """Seeds the first Human so the approval chain of 14.8.3 has a root."""
        principal = self.registration.bootstrap_human(principal_id, name, tenant_id)
        self.journal.record(
            SecurityEventType.IDENTITY_REGISTERED, principal_id, tenant_id, "bootstrap", {"type": "human"}
        )
        return principal

    def register_identity(self, request: RegistrationRequest) -> Principal:
        """**Identity Registration** (21B §22.5). Consumers: Human Interface, Agent Runtime, Governance."""
        self._require_running()
        principal = self.registration.register(request)
        # 14.8.4 on registration: initialize the permission graph and write the
        # initial audit journal entry.
        self.graph_engine.set_source(principal.principal_id, "capabilities", frozenset())
        self.journal.record(
            SecurityEventType.IDENTITY_REGISTERED,
            principal.principal_id,
            principal.tenant_id,
            "registered",
            {"type": principal.principal_type.value, "approved_by": request.approved_by, "version": principal.version},
        )
        return principal

    def change_principal_status(self, principal_id: str, target: PrincipalStatus, actor_id: str) -> Principal:
        """Applies a lifecycle transition with the side effects of 14.8.4."""
        self.enforcer.reject_self_escalation(actor_id, principal_id, "lifecycle status")
        principal = self.registration.transition(principal_id, target)
        if target == PrincipalStatus.SUSPENDED:
            self.tokens.revoke_principal(principal_id)
            self.cache.invalidate_principal(principal_id)
        elif target == PrincipalStatus.ACTIVE:
            self.tokens.reinstate_principal(principal_id)
            self.revocations.reinstate(principal_id)
        elif target == PrincipalStatus.RETIRED:
            self.tokens.revoke_principal(principal_id)
            self.cache.invalidate_principal(principal_id)
            self.credentials.revoke_for_principal(principal_id)
            self.graph_engine.drop(principal_id)
            self.roles.clear(principal_id)
        self.journal.record(
            SecurityEventType.IDENTITY_TRANSITIONED,
            principal_id,
            principal.tenant_id,
            target.value,
            {"actor": actor_id},
        )
        return principal

    def recompute_permissions(self, principal_id: str) -> None:
        """Republishes capability- and role-derived graph inputs and invalidates caches.

        Called whenever an input of 14.12.2 changes. Invalidation on change is
        the counterpart to precomputation (21B §22.4 Implementation Decision).
        """
        self.graph_engine.set_source(principal_id, "capabilities", self.capabilities.permissions_for(principal_id))
        self.graph_engine.set_source(principal_id, "roles", self.roles.permissions_for(principal_id))
        self.cache.invalidate_principal(principal_id)
        principal = self.registry.get(principal_id)
        graph = self.graph_engine.graph_for(principal_id)
        self.journal.record(
            SecurityEventType.PERMISSION_GRAPH_CHANGED,
            principal_id,
            principal.tenant_id,
            "recomputed",
            {"revision": graph.revision, "effective": sorted(graph.effective)},
        )

    # ---------------------------------------------------------- Authentication

    def authenticate(
        self,
        principal_id: str,
        credential_id: str,
        presented_hash: str,
        claiming_type: PrincipalType,
        ttl: timedelta | None = None,
        workspace_ids: tuple[str, ...] = (),
        task_timeout_seconds: int = 300,
        max_retries: int = 3,
    ) -> tuple[str, TokenClaims]:
        """**Authentication** (21B §22.5): verify identity claim, issue a scoped token."""
        self._require_running()
        try:
            principal = self.registry.get(principal_id)
        except AgentOSError:
            self._on_authentication_failure(principal_id, "unknown", "principal is not registered")
            raise

        self.enforcer.require_registered_identity(principal_id, True, principal.is_actionable)

        try:
            credential = self.credentials.verify(credential_id, presented_hash, principal_id)
        except AgentOSError as exc:
            self._on_authentication_failure(principal_id, principal.tenant_id, str(exc))
            raise AuthenticationError(str(exc)) from exc

        # 14.23.4 — a non-human may never authenticate with a human credential.
        self.enforcer.reject_human_credential_automation(credential.principal_type, claiming_type, principal_id)

        graph = self.graph_engine.graph_for(principal_id)
        chain = self.delegations.chain_for(principal_id)
        token, claims = self.tokens.issue(
            {
                "principal_id": principal.principal_id,
                "principal_version": principal.version,
                "principal_type": principal.principal_type,
                "tenant_id": principal.tenant_id,
                "autonomy_level": principal.autonomy_level,
                "roles": self.roles.role_names(principal_id),
                "standing_order_refs": tuple(
                    d.delegation_id for d in chain if d.delegation_type == DelegationType.STANDING_ORDER
                ),
                "permissions": tuple(sorted(graph.effective)),
                "workspace_ids": workspace_ids,
                "budget_remaining": self._budget_remaining(principal_id),
                "task_timeout_seconds": task_timeout_seconds,
                "max_retries": max_retries,
                "delegation_window_ends_at": min((d.expires_at for d in chain), default=None),
            },
            **({"ttl": ttl} if ttl is not None else {}),
        )
        self.incidents.reset("authentication_failures", principal_id)
        self.journal.record(
            SecurityEventType.AUTHENTICATION_SUCCEEDED, principal_id, principal.tenant_id, "success", {}
        )
        self.journal.record(
            SecurityEventType.TOKEN_ISSUED,
            principal_id,
            principal.tenant_id,
            "issued",
            {"token_id": claims.token_id, "expires_at": claims.expires_at.isoformat()},
        )
        return token, claims

    def _on_authentication_failure(self, principal_id: str, tenant_id: str, reason: str) -> None:
        self.journal.record(
            SecurityEventType.AUTHENTICATION_FAILED, principal_id, tenant_id, "failure", {"reason": reason}
        )
        self.incidents.count("authentication_failures", principal_id)
        if self.incidents.threshold_breached("authentication_failures", principal_id):
            # 14.29.2 automatic response: repeated failures are an
            # Authentication Breach — revoke credentials, suspend, alert.
            self._raise_incident(
                IncidentCategory.AUTHENTICATION_BREACH,
                principal_id,
                tenant_id,
                "authentication failure threshold breached",
                {"reason": reason},
            )

    # ----------------------------------------------------------- Authorization

    def authorize(self, token: str, request: AuthorizationRequest) -> AuthorizationResult:
        """**Authorization** (21B §22.5): render Allow, Deny or Escalate for an action."""
        self._require_running()
        claims = self.tokens.validate(token)

        cached = self.cache.get(claims.principal_id, request.action, request.resource_id)
        if cached is not None:
            return cached

        principal = self.registry.get(claims.principal_id)
        self.enforcer.require_registered_identity(claims.principal_id, True, principal.is_actionable)

        try:
            result = self.authorization.authorize(claims, request)
        except BrokenChainError as exc:
            # 21B §22.9 — a delegation chain break is Critical to the operation
            # and invalidates the authorization outright.
            self.journal.record(
                SecurityEventType.AUTHORIZATION_DENIED,
                claims.principal_id,
                claims.tenant_id,
                Decision.DENY.value,
                {"action": request.action, "resource_id": request.resource_id, "reason": str(exc)},
            )
            return AuthorizationResult(
                decision=Decision.DENY,
                principal_id=claims.principal_id,
                action=request.action,
                resource_id=request.resource_id,
                reason=str(exc),
                graph_revision=self.graph_engine.graph_for(claims.principal_id).revision,
                decided_at=self.now(),
            )

        if result.decision == Decision.ALLOW:
            self.cache.put(result, token_expires_at=claims.expires_at)
            self.incidents.reset("authorization_denials", claims.principal_id)
        elif result.decision == Decision.DENY:
            self.incidents.count("authorization_denials", claims.principal_id)
            if self.incidents.threshold_breached("authorization_denials", claims.principal_id):
                self._raise_incident(
                    IncidentCategory.AUTHORIZATION_VIOLATION,
                    claims.principal_id,
                    claims.tenant_id,
                    "authorization denial threshold breached",
                    {"action": request.action, "resource_id": request.resource_id},
                )
        return result

    # ------------------------------------------------------------- Delegation

    def manage_delegation(
        self,
        operation: str,
        delegation_id: str,
        actor_id: str,
        delegation_type: DelegationType | None = None,
        delegatee_id: str | None = None,
        permissions: tuple[str, ...] = (),
        duration: timedelta | None = None,
        authorized_by: str | None = None,
    ) -> Delegation:
        """**Delegation Management** (21B §22.5), create and revoke halves.

        Chain validation is the third operation of this interface and lives in
        `validate_delegation_chain` — it answers with a scope rather than a
        delegation, and collapsing both into one return type only forced every
        caller into a cast.
        """
        self._require_running()
        if operation == "create":
            if delegation_type is None or delegatee_id is None or duration is None:
                raise AgentOSError("create requires delegation_type, delegatee_id and duration")
            delegator = self.registry.get(actor_id)
            delegation = self.delegations.create(
                delegation_id=delegation_id,
                delegation_type=delegation_type,
                delegator_id=actor_id,
                delegatee_id=delegatee_id,
                permissions=permissions,
                tenant_id=delegator.tenant_id,
                duration=duration,
                authorized_by=authorized_by,
            )
            self.cache.invalidate_principal(delegatee_id)
            self.journal.record(
                SecurityEventType.DELEGATION_CREATED,
                delegatee_id,
                delegation.tenant_id,
                "created",
                {
                    "delegation_id": delegation_id,
                    "delegator_id": actor_id,
                    "type": delegation.delegation_type.value,
                    "permissions": sorted(delegation.permissions),
                    "expires_at": delegation.expires_at.isoformat(),
                },
            )
            return delegation
        if operation == "revoke":
            delegation = self.delegations.revoke(delegation_id)
            self.cache.invalidate_principal(delegation.delegatee_id)
            self.journal.record(
                SecurityEventType.DELEGATION_REVOKED,
                delegation.delegatee_id,
                delegation.tenant_id,
                "revoked",
                {"delegation_id": delegation_id, "actor": actor_id},
            )
            return delegation
        raise AgentOSError(f"unknown delegation operation '{operation}'; expected create or revoke")

    def validate_delegation_chain(self, delegatee_id: str) -> frozenset[str]:
        """**Delegation Management** (21B §22.5), validation half.

        Walks the chain end to end and returns its intersected scope. Raises
        `BrokenChainError` on any expired, revoked or inactive link (14.14.4).
        """
        return self.delegations.validate_chain(delegatee_id)

    # ------------------------------------------------------------- Revocation

    def revoke(
        self,
        principal_id: str,
        revoker_id: str,
        trigger: RevocationTrigger,
        reason: str,
        scope: tuple[str, ...] = ("permissions", "roles", "delegations", "credentials", "tokens"),
    ) -> RevocationRecord:
        """**Revocation Command** (21B §22.5): cascading revocation per 14.15.3.

        Partial propagation raises `PartialRevocationError` — 14.15.3 treats it
        as a system failure, so it is alerted as an incident rather than
        returned as a degraded success.
        """
        principal = self.registry.get(principal_id)

        def local_effects() -> tuple[str, ...]:
            self.tokens.revoke_principal(principal_id)
            self.cache.invalidate_principal(principal_id)
            self.credentials.revoke_for_principal(principal_id)
            # 14.15.3 cascades to delegations the principal issued *and* holds.
            candidates = self.delegations.issued_by(principal_id) + self.delegations.held_by(principal_id)
            revoked: list[str] = []
            for delegation in candidates:
                if delegation.revoked_at is not None or delegation.delegation_id in revoked:
                    continue
                self.delegations.revoke(delegation.delegation_id)
                self.cache.invalidate_principal(delegation.delegatee_id)
                revoked.append(delegation.delegation_id)
                # 14.14.5 — every delegation revocation is logged immutably,
                # including the ones a cascade performs rather than an operator.
                self.journal.record(
                    SecurityEventType.DELEGATION_REVOKED,
                    delegation.delegatee_id,
                    delegation.tenant_id,
                    "revoked",
                    {"delegation_id": delegation.delegation_id, "actor": revoker_id, "cause": "cascade"},
                )
            self.graph_engine.drop(principal_id)
            return tuple(revoked)

        try:
            record = self.revocations.revoke(
                principal_id=principal_id,
                revoker_id=revoker_id,
                trigger=trigger,
                reason=reason,
                scope=scope,
                local_effects=local_effects,
            )
        except AgentOSError as exc:
            self.journal.record(
                SecurityEventType.REVOCATION_PARTIAL,
                principal_id,
                principal.tenant_id,
                "system_failure",
                {"reason": str(exc), "trigger": trigger.value},
            )
            self._raise_incident(
                IncidentCategory.OPERATIONAL_ANOMALY,
                principal_id,
                principal.tenant_id,
                "cascading revocation did not fully propagate",
                {"reason": str(exc)},
            )
            raise

        self.journal.record(
            SecurityEventType.REVOCATION_EXECUTED,
            principal_id,
            principal.tenant_id,
            "revoked",
            {
                "revoker_id": revoker_id,
                "trigger": trigger.value,
                "reason": reason,
                "scope": list(scope),
                "cascaded_to": list(record.cascaded_to),
                "delegations_revoked": list(record.delegations_revoked),
                "elapsed_seconds": record.elapsed_seconds,
            },
        )
        return record

    # ------------------------------------------------- Secret Reference Resolution

    def resolve_secret_reference(
        self,
        reference: str,
        sandbox_id: str,
        invocation_id: str,
        requester_id: str,
    ) -> InjectionGrant:
        """**Secret Reference Resolution** (21B §22.5). Consumer: Tool Executor.

        Returns an injection grant. There is deliberately no method on this
        Gateway that returns a secret value (21B §22.10).
        """
        self._require_running()
        requester = self.registry.get(requester_id)
        self.enforcer.reject_secret_exposure(requester.principal_type, "requester", requester_id)
        grant = self.secrets.authorize_injection(
            reference=reference,
            sandbox_id=sandbox_id,
            invocation_id=invocation_id,
            requester_id=requester_id,
            requester_type=requester.principal_type,
        )
        self.journal.record(
            SecurityEventType.SECRET_REFERENCE_USED,
            requester_id,
            requester.tenant_id,
            "granted",
            # The reference and sandbox are journalled; the value never is.
            {"reference": reference, "sandbox_id": sandbox_id, "invocation_id": invocation_id},
        )
        return grant

    # -------------------------------------------------------- Security Context

    def create_security_context(
        self,
        claims: TokenClaims,
        trace_id: str,
        workspace_id: str | None = None,
        action_id: str | None = None,
    ) -> SecurityContext:
        """**Security Context** (21B §22.5), creation half."""
        self._require_running()
        chain = tuple(d.delegation_id for d in self.delegations.chain_for(claims.principal_id))
        return self.contexts.create(
            principal_id=claims.principal_id,
            principal_type=claims.principal_type,
            tenant_id=claims.tenant_id,
            token_id=claims.token_id,
            trace_id=trace_id,
            workspace_id=workspace_id,
            delegation_chain=chain,
            action_id=action_id,
        )

    def validate_security_context(self, context: SecurityContext | None, action: str) -> SecurityContext:
        """**Security Context** (21B §22.5), validation half. Absence halts the action (14.24.5)."""
        return self.contexts.require(context, action)

    # ---------------------------------------------------------- Journal Query

    def query_journal(
        self,
        principal_id: str | None = None,
        tenant_id: str | None = None,
        event_type: SecurityEventType | None = None,
        since: datetime | None = None,
    ) -> list[SecurityEvent]:
        """**Security Event Journal Query** (21B §22.5). Consumers: Governance, Auditors."""
        return self.journal.query(principal_id, tenant_id, event_type, since)

    # ----------------------------------------------------------------- Health

    def health(self) -> Mapping[str, Any]:
        """**Security Health** (21B §22.5). Consumer: Observability Gateway.

        Reports the metric families 14.27.1 requires: authentication,
        authorization, delegation, boundary, token and secret activity.
        """
        counts = self.journal.counts_by_type()
        return {
            "halted": self._halted,
            "principals": len(self.registry.all_principals()),
            "journal_entries": len(self.journal),
            "journal_intact": self.journal.verify(),
            "authentication": {
                "succeeded": counts.get(SecurityEventType.AUTHENTICATION_SUCCEEDED.value, 0),
                "failed": counts.get(SecurityEventType.AUTHENTICATION_FAILED.value, 0),
            },
            "authorization": {
                "allowed": counts.get(SecurityEventType.AUTHORIZATION_ALLOWED.value, 0),
                "denied": counts.get(SecurityEventType.AUTHORIZATION_DENIED.value, 0),
                "escalated": counts.get(SecurityEventType.AUTHORIZATION_ESCALATED.value, 0),
                "cache_hits": self.cache.hits,
                "cache_misses": self.cache.misses,
                "cache_size": self.cache.size,
            },
            "delegation": {
                "created": counts.get(SecurityEventType.DELEGATION_CREATED.value, 0),
                "revoked": counts.get(SecurityEventType.DELEGATION_REVOKED.value, 0),
            },
            "tokens": {"issued": counts.get(SecurityEventType.TOKEN_ISSUED.value, 0)},
            "secrets": {
                "references_used": counts.get(SecurityEventType.SECRET_REFERENCE_USED.value, 0),
                "rotation_due": len(self.secrets.rotation_due()),
            },
            "revocation": {
                "executed": counts.get(SecurityEventType.REVOCATION_EXECUTED.value, 0),
                "partial": counts.get(SecurityEventType.REVOCATION_PARTIAL.value, 0),
                "list_size": len(self.revocations.revocation_list),
            },
            "incidents": {
                "total": len(self.incidents.incidents),
                "category_1": sum(1 for i in self.incidents.incidents if i.is_category_1),
            },
        }

    # ------------------------------------------------- Constitutional enforcement

    def report_constitutional_violation(self, error: ConstitutionalViolationError, tenant_id: str) -> Incident:
        """Applies the 14.33.3 response: block, suspend, preserve evidence, escalate.

        The block already happened — the caller raised rather than proceeded.
        This records it and carries out the rest, with no appeal path.
        """
        incident = self._raise_incident(
            IncidentCategory.CONSTITUTIONAL_VIOLATION,
            error.principal_id,
            tenant_id,
            error.detail,
            {"rule": error.rule, **error.evidence},
        )
        if self.registry.exists(error.principal_id):
            principal = self.registry.get(error.principal_id)
            if principal.status == PrincipalStatus.ACTIVE:
                self.registration.transition(error.principal_id, PrincipalStatus.SUSPENDED)
                self.tokens.revoke_principal(error.principal_id)
                self.cache.invalidate_principal(error.principal_id)
        return incident

    # ---------------------------------------------------------------- Internals

    def _raise_incident(
        self,
        category: IncidentCategory,
        principal_id: str,
        tenant_id: str,
        summary: str,
        evidence: Mapping[str, Any],
    ) -> Incident:
        incident = self.incidents.raise_incident(category, principal_id, tenant_id, summary, evidence)
        self.journal.record(
            SecurityEventType.INCIDENT_RAISED,
            principal_id,
            tenant_id,
            category.value,
            {
                "incident_id": incident.incident_id,
                "summary": summary,
                "responses": list(incident.responses),
                "category_1": incident.is_category_1,
            },
        )
        return incident

    def _budget_remaining(self, principal_id: str) -> float:
        if self.budget_resolver is None:
            return UNMETERED_BUDGET
        return self.budget_resolver(principal_id)

    def _escalation_target(self, request: AuthorizationRequest, claims: TokenClaims) -> str:
        """14.10.3 routes by decision class and risk.

        Full routing (team lead / business manager / portfolio architect /
        human sovereign) depends on the org model the Agent Runtime owns
        (Stage S7). Until that exists the Gateway escalates to the human
        sovereign rather than guessing an intermediate authority.
        """
        return "human_sovereign"

    def _delegated_scope(self, principal_id: str) -> frozenset[str]:
        return self.delegations.validate_chain(principal_id)

    def _is_actionable(self, principal_id: str) -> bool:
        return self.registry.exists(principal_id) and self.registry.get(principal_id).is_actionable

    def _is_human(self, principal_id: str) -> bool:
        return self.registry.exists(principal_id) and (
            self.registry.get(principal_id).principal_type == PrincipalType.HUMAN
        )

    def _halt(self) -> None:
        """Panic Protocol participation hook (21A §5.2 item 8)."""
        self._halted = True
        self.cache.clear()

    def _require_running(self) -> None:
        if self._halted:
            raise GatewayHaltedError("Panic Protocol is active; the Security Gateway issues and authorizes nothing")
