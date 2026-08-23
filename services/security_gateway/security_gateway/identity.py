"""Identity Registry and Registration Controller (21B §22.3, realizes 14.4 / 14.8).

Identity is durable and slow-changing; authorization is computed and fast
(21B §22.4). Nothing here consults permissions — this module answers only
"who is this principal, and what lifecycle state is it in".
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from core.exceptions import NotFoundError, ValidationError
from kernel.lifecycle import LifecycleStateMachine
from persistence.repository import NotFound, Repository
from security_gateway.enums import PrincipalStatus, PrincipalType

# 14.8.3 State Transition Guards. "Designed" has no registry entry, so a
# registered principal starts at REGISTERED and the Designed -> Registered
# edge is the act of registration itself.
IDENTITY_TRANSITIONS: dict[str, set[str]] = {
    PrincipalStatus.DESIGNED: {PrincipalStatus.REGISTERED},
    PrincipalStatus.REGISTERED: {PrincipalStatus.ACTIVE, PrincipalStatus.RETIRED},
    PrincipalStatus.ACTIVE: {PrincipalStatus.SUSPENDED, PrincipalStatus.RETIRED},
    PrincipalStatus.SUSPENDED: {PrincipalStatus.ACTIVE, PrincipalStatus.RETIRED},
    PrincipalStatus.RETIRED: {PrincipalStatus.ARCHIVED},
    PrincipalStatus.ARCHIVED: set(),
}


class IdentityCollisionError(ValidationError):
    def __init__(self, principal_id: str):
        super().__init__(f"principal '{principal_id}' already registered; IDs are never reused (14.4.1)")


class ApprovalRequiredError(ValidationError):
    """Registration attempted without the approval 14.8.3 mandates for the type."""


@dataclass
class Principal:
    """The immutable security identity of 14.4.1, plus its mutable lifecycle state."""

    principal_id: str
    principal_type: PrincipalType
    name: str
    version: str
    tenant_id: str
    status: PrincipalStatus = PrincipalStatus.REGISTERED
    lineage_ref: str | None = None
    registered_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    retired_at: datetime | None = None
    #: 14.8.1 — Services and Gateways have no autonomy level; Agents do.
    autonomy_level: int | None = None

    def machine(self) -> LifecycleStateMachine:
        return LifecycleStateMachine(transitions=dict(IDENTITY_TRANSITIONS), state=self.status)

    @property
    def is_actionable(self) -> bool:
        """14.8.2 — only Active identities may take new actions."""
        return self.status == PrincipalStatus.ACTIVE


@dataclass(frozen=True)
class RegistrationRequest:
    principal_id: str
    principal_type: PrincipalType
    name: str
    version: str
    tenant_id: str
    lineage_ref: str | None = None
    autonomy_level: int | None = None
    #: Principal ID of the approving human (agents/services/gateways) or the
    #: verifying Auditor (humans). 14.8.3 makes this non-optional in practice.
    approved_by: str | None = None


class IdentityRegistry:
    """Durable store of principal identity (21B §22.3, 14.4.2).

    Persists independently of any session: Suspended, Retired and Archived
    principals remain resident and queryable.
    """

    def __init__(self, repository: Repository[Principal]) -> None:
        self._repo = repository

    def put(self, principal: Principal) -> None:
        self._repo.save(principal.principal_id, principal)

    def get(self, principal_id: str) -> Principal:
        try:
            return self._repo.get(principal_id)
        except NotFound as exc:
            raise NotFoundError(f"principal '{principal_id}' is not registered") from exc

    def exists(self, principal_id: str) -> bool:
        try:
            self._repo.get(principal_id)
        except NotFound:
            return False
        return True

    def all_principals(self) -> list[Principal]:
        return self._repo.list_all()

    def lineage(self, principal_id: str) -> list[str]:
        """Walks lineage_ref back to the root identity (14.4.3)."""
        chain = [principal_id]
        current = self.get(principal_id)
        while current.lineage_ref is not None:
            chain.append(current.lineage_ref)
            current = self.get(current.lineage_ref)
        return chain


class RegistrationController:
    """Identity registration with the approvals 14.8.3 requires.

    Agents, Services and Gateways need human approval; Humans need Auditor
    verification. Either way `approved_by` must name a registered Human —
    self-approval is prohibited (14.17.5).
    """

    def __init__(self, registry: IdentityRegistry) -> None:
        self._registry = registry

    def register(self, request: RegistrationRequest) -> Principal:
        if self._registry.exists(request.principal_id):
            raise IdentityCollisionError(request.principal_id)
        if request.approved_by is None:
            raise ApprovalRequiredError(
                f"registration of '{request.principal_id}' ({request.principal_type.value}) requires "
                "human approval (agent/service/gateway) or Auditor verification (human), per 14.8.3"
            )
        if request.approved_by == request.principal_id:
            raise ApprovalRequiredError("self-approval of a registration is prohibited (14.17.5)")
        if not self._registry.exists(request.approved_by):
            raise ApprovalRequiredError(f"approver '{request.approved_by}' is not a registered principal")
        approver = self._registry.get(request.approved_by)
        if approver.principal_type != PrincipalType.HUMAN:
            raise ApprovalRequiredError(
                f"approver '{request.approved_by}' is a {approver.principal_type.value}; 14.8.3 requires a Human"
            )
        if request.lineage_ref is not None and not self._registry.exists(request.lineage_ref):
            raise ValidationError(f"lineage reference '{request.lineage_ref}' is not a registered principal")

        principal = Principal(
            principal_id=request.principal_id,
            principal_type=request.principal_type,
            name=request.name,
            version=request.version,
            tenant_id=request.tenant_id,
            status=PrincipalStatus.REGISTERED,
            lineage_ref=request.lineage_ref,
            autonomy_level=request.autonomy_level,
        )
        self._registry.put(principal)
        return principal

    def bootstrap_human(self, principal_id: str, name: str, tenant_id: str) -> Principal:
        """Registers the first human sovereign.

        The approval chain has to start somewhere: an empty registry contains
        no Human to verify the first Human. Permitted only while the registry
        holds no principal at all, so it cannot be used to slip an unapproved
        identity into a running system.
        """
        if self._registry.all_principals():
            raise ApprovalRequiredError(
                "bootstrap_human is permitted only on an empty registry; use register() with an approver"
            )
        principal = Principal(
            principal_id=principal_id,
            principal_type=PrincipalType.HUMAN,
            name=name,
            version="1.0.0",
            tenant_id=tenant_id,
            status=PrincipalStatus.ACTIVE,
        )
        self._registry.put(principal)
        return principal

    def transition(self, principal_id: str, target: PrincipalStatus) -> Principal:
        """Applies a guarded lifecycle transition (14.8.3).

        Side effects of 14.8.4 (token revocation on suspension, permission
        graph archival on retirement) are the Gateway's responsibility, not
        the controller's — see `SecurityGateway.change_principal_status`.
        """
        principal = self._registry.get(principal_id)
        machine = principal.machine()
        machine.transition(target)
        principal.status = target
        if target == PrincipalStatus.RETIRED:
            principal.retired_at = datetime.now(UTC)
        self._registry.put(principal)
        return principal
