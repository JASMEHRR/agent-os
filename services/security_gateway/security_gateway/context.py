"""Security Context Factory (21B §22.3, realizes 14.24).

Two constitutional properties drive the design:

- Context is **immutable for one action** (21B §22.8). It is a frozen value
  bound to a single action_id; deriving a child context for a sub-action
  produces a new object rather than mutating the parent.
- Context **may never be dropped** (14.24.5). Loss halts the action. Callers
  therefore get `require()`, which raises rather than returning None — there
  is no accessor that silently yields "no context".
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from core.exceptions import AgentOSError
from security_gateway.enums import PrincipalType

#: [Engineering Decision] A context is valid for one action. This bounds how
#: long a context object may be presented before it must be recreated, so a
#: stale context cannot be replayed indefinitely. It is deliberately the same
#: ceiling as the maximum token TTL (14.9.2) — a context can never outlive
#: the token that authenticated it.
CONTEXT_MAX_AGE = timedelta(hours=1)


class SecurityContextDroppedError(AgentOSError):
    """14.24.5 — security context may never be dropped; loss halts the action."""

    def __init__(self, action: str):
        super().__init__(f"action '{action}' has no security context; the action is halted (14.24.5)")


class SecurityContextInvalidError(AgentOSError):
    pass


@dataclass(frozen=True)
class SecurityContext:
    """Immutable, propagated proof of who is acting and under what authority."""

    action_id: str
    principal_id: str
    principal_type: PrincipalType
    tenant_id: str
    token_id: str
    workspace_id: str | None
    delegation_chain: tuple[str, ...]
    trace_id: str
    created_at: datetime
    parent_action_id: str | None = None

    def derive(self, action_id: str) -> SecurityContext:
        """Propagates context to a sub-action, preserving the attribution chain.

        Nothing widens on derivation — the child carries exactly the parent's
        principal, tenant, token and delegation chain.
        """
        return SecurityContext(
            action_id=action_id,
            principal_id=self.principal_id,
            principal_type=self.principal_type,
            tenant_id=self.tenant_id,
            token_id=self.token_id,
            workspace_id=self.workspace_id,
            delegation_chain=self.delegation_chain,
            trace_id=self.trace_id,
            created_at=datetime.now(UTC),
            parent_action_id=self.action_id,
        )


@dataclass
class SecurityContextFactory:
    """Creates and validates propagated context (21B §22.3)."""

    _issued: dict[str, SecurityContext] = field(default_factory=dict, init=False)

    def create(
        self,
        principal_id: str,
        principal_type: PrincipalType,
        tenant_id: str,
        token_id: str,
        trace_id: str,
        workspace_id: str | None = None,
        delegation_chain: tuple[str, ...] = (),
        action_id: str | None = None,
    ) -> SecurityContext:
        context = SecurityContext(
            action_id=action_id or f"act-{secrets.token_urlsafe(12)}",
            principal_id=principal_id,
            principal_type=principal_type,
            tenant_id=tenant_id,
            token_id=token_id,
            workspace_id=workspace_id,
            delegation_chain=delegation_chain,
            trace_id=trace_id,
            created_at=datetime.now(UTC),
        )
        self._issued[context.action_id] = context
        return context

    def require(self, context: SecurityContext | None, action: str) -> SecurityContext:
        """The only supported way to read a context. Absence halts the action (14.24.5)."""
        if context is None:
            raise SecurityContextDroppedError(action)
        self.validate(context)
        return context

    def validate(self, context: SecurityContext) -> None:
        known = self._issued.get(context.action_id)
        if known is None:
            raise SecurityContextInvalidError(
                f"context '{context.action_id}' was not issued by this Gateway — anonymous action (14.4.4)"
            )
        if known != context:
            raise SecurityContextInvalidError(
                f"context '{context.action_id}' differs from the issued context; it is immutable for one action"
            )
        age = datetime.now(UTC) - context.created_at
        if age > CONTEXT_MAX_AGE:
            raise SecurityContextInvalidError(f"context '{context.action_id}' is {age} old and must be recreated")

    def register_derived(self, context: SecurityContext) -> SecurityContext:
        """Records a derived context so `validate` recognizes it downstream."""
        self._issued[context.action_id] = context
        return context

    def discard(self, action_id: str) -> None:
        """Retires a context once its action completes."""
        self._issued.pop(action_id, None)
