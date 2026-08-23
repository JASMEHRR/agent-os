"""Role Controller and Capability Enforcer (21B §22.3, realizes 14.11 / 14.13).

A capability declares *what outcomes a principal can deliver*; a permission
declares *what actions it may attempt* (14.12.1). The Capability Enforcer
polices the boundary between the two: an action must fall inside a registered
capability signature before permissions are even consulted.

The Role Controller adds assignment, type constraints, expiry, and
separation-of-duties conflict detection (14.13, 14.17).
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from core.exceptions import NotFoundError, ValidationError
from security_gateway.enums import PrincipalType
from security_gateway.permissions import covers


class CapabilityViolationError(ValidationError):
    """Requested action falls outside every registered capability signature (14.11.1)."""


class RoleConflictError(ValidationError):
    """Assignment would create a separation-of-duties conflict (14.17)."""


@dataclass(frozen=True)
class Capability:
    """A structured declaration of a business function (Agent OM 7.1, referenced by 14.11.1)."""

    name: str
    #: Action prefixes this capability authorizes attempting.
    permits: frozenset[str]


@dataclass(frozen=True)
class Role:
    name: str
    permissions: frozenset[str]
    #: Principal types eligible to hold this role (14.13 type constraints).
    eligible_types: frozenset[PrincipalType]
    #: Roles that may not be held simultaneously — separation of duties.
    conflicts_with: frozenset[str] = frozenset()


@dataclass(frozen=True)
class RoleAssignment:
    role: str
    principal_id: str
    assigned_by: str
    assigned_at: datetime
    expires_at: datetime | None


@dataclass
class CapabilityEnforcer:
    """Validates requested actions against registered capability signatures."""

    _capabilities: dict[str, Capability] = field(default_factory=dict, init=False)
    _by_principal: dict[str, set[str]] = field(default_factory=dict, init=False)

    def define(self, capability: Capability) -> Capability:
        self._capabilities[capability.name] = capability
        return capability

    def grant(self, principal_id: str, capability_name: str) -> frozenset[str]:
        """Grants a capability and returns the principal's full capability-derived permissions."""
        if capability_name not in self._capabilities:
            raise NotFoundError(f"capability '{capability_name}' is not defined")
        self._by_principal.setdefault(principal_id, set()).add(capability_name)
        return self.permissions_for(principal_id)

    def revoke(self, principal_id: str, capability_name: str) -> frozenset[str]:
        self._by_principal.setdefault(principal_id, set()).discard(capability_name)
        return self.permissions_for(principal_id)

    def permissions_for(self, principal_id: str) -> frozenset[str]:
        granted: set[str] = set()
        for name in self._by_principal.get(principal_id, set()):
            granted |= self._capabilities[name].permits
        return frozenset(granted)

    def check(self, principal_id: str, action: str) -> None:
        """Raises unless `action` sits inside some capability the principal holds."""
        if not any(covers(permit, action) for permit in self.permissions_for(principal_id)):
            raise CapabilityViolationError(
                f"action '{action}' is outside every capability signature registered for '{principal_id}' (14.11.1)"
            )


@dataclass
class RoleController:
    """Role assignment, type constraint validation, expiry, conflict detection."""

    now: Callable[[], datetime] = field(default=lambda: datetime.now(UTC))
    _roles: dict[str, Role] = field(default_factory=dict, init=False)
    _assignments: dict[str, list[RoleAssignment]] = field(default_factory=dict, init=False)

    def define(self, role: Role) -> Role:
        self._roles[role.name] = role
        return role

    def get(self, name: str) -> Role:
        try:
            return self._roles[name]
        except KeyError:
            raise NotFoundError(f"role '{name}' is not defined") from None

    def assign(
        self,
        role_name: str,
        principal_id: str,
        principal_type: PrincipalType,
        assigned_by: str,
        duration: timedelta | None = None,
    ) -> RoleAssignment:
        role = self.get(role_name)
        if principal_type not in role.eligible_types:
            raise ValidationError(
                f"role '{role_name}' is not assignable to a {principal_type.value} principal (14.13 type constraints)"
            )
        if assigned_by == principal_id:
            raise ValidationError("a principal may not assign itself a role (14 rule 3, no self-escalation)")
        held = {a.role for a in self.active_assignments(principal_id)}
        for existing in held:
            other = self.get(existing)
            if role_name in other.conflicts_with or existing in role.conflicts_with:
                raise RoleConflictError(
                    f"role '{role_name}' conflicts with held role '{existing}' — separation of duties (14.17)"
                )
        now = self.now()
        assignment = RoleAssignment(
            role=role_name,
            principal_id=principal_id,
            assigned_by=assigned_by,
            assigned_at=now,
            expires_at=now + duration if duration is not None else None,
        )
        self._assignments.setdefault(principal_id, []).append(assignment)
        return assignment

    def unassign(self, role_name: str, principal_id: str) -> None:
        remaining = [a for a in self._assignments.get(principal_id, []) if a.role != role_name]
        self._assignments[principal_id] = remaining

    def active_assignments(self, principal_id: str) -> list[RoleAssignment]:
        now = self.now()
        return [a for a in self._assignments.get(principal_id, []) if a.expires_at is None or now < a.expires_at]

    def role_names(self, principal_id: str) -> tuple[str, ...]:
        return tuple(a.role for a in self.active_assignments(principal_id))

    def permissions_for(self, principal_id: str) -> frozenset[str]:
        """Union across a principal's own roles.

        Roles are alternative grants to one principal, so they combine here;
        the intersection rule of 14.12.4 applies *between* graph sources, not
        within one, which the Permission Graph Engine handles.
        """
        granted: set[str] = set()
        for assignment in self.active_assignments(principal_id):
            granted |= self.get(assignment.role).permissions
        return frozenset(granted)

    def clear(self, principal_id: str) -> None:
        self._assignments.pop(principal_id, None)

    def defined_roles(self) -> Iterable[Role]:
        return self._roles.values()
