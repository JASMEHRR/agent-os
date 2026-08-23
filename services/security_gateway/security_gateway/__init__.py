"""Security Gateway — the trust substrate (realizes document 14, 21B §22).

Built at Stage S1 because Trust precedes everything (21_PLAN §4.2 Rule 2):
no principal can be authenticated, authorized or delegated to until this
exists, and every later Gateway's Boundary Enforcement depends on the
authority resolution here.

Depends only on `kernel`, `core` and `persistence` (21B §22.13). Its journal
is written straight to persistence rather than through the Event Bus
(14.26.1), which is what makes building Security before the Event Bus
possible at all.
"""

from security_gateway.authorization import (
    AuthorizationCache,
    AuthorizationEngine,
    AuthorizationRequest,
    AuthorizationResult,
)
from security_gateway.context import (
    SecurityContext,
    SecurityContextDroppedError,
    SecurityContextFactory,
)
from security_gateway.delegation import BrokenChainError, Delegation, DelegationManager
from security_gateway.enforcer import ConstitutionalEnforcer, ConstitutionalViolationError
from security_gateway.enums import (
    Classification,
    Decision,
    DelegationType,
    IncidentCategory,
    PrincipalStatus,
    PrincipalType,
    RevocationTrigger,
    SecurityEventType,
)
from security_gateway.gateway import GatewayHaltedError, SecurityGateway
from security_gateway.identity import (
    IdentityRegistry,
    Principal,
    RegistrationController,
    RegistrationRequest,
)
from security_gateway.incidents import Incident, IncidentClassifier
from security_gateway.isolation import IsolationBreachError, IsolationEnforcer
from security_gateway.journal import SecurityEvent, SecurityEventJournal
from security_gateway.permissions import PermissionGraph, PermissionGraphEngine, intersect
from security_gateway.revocation import PartialRevocationError, RevocationEngine
from security_gateway.roles import Capability, CapabilityEnforcer, Role, RoleController
from security_gateway.secrets_governor import (
    CredentialGovernor,
    InjectionGrant,
    SecretGovernor,
    SecretStore,
)
from security_gateway.tokens import AuthenticationError, TokenClaims, TokenService

__all__ = [
    "SecurityGateway",
    "GatewayHaltedError",
    "Principal",
    "PrincipalType",
    "PrincipalStatus",
    "RegistrationRequest",
    "RegistrationController",
    "IdentityRegistry",
    "TokenService",
    "TokenClaims",
    "AuthenticationError",
    "PermissionGraph",
    "PermissionGraphEngine",
    "intersect",
    "AuthorizationEngine",
    "AuthorizationCache",
    "AuthorizationRequest",
    "AuthorizationResult",
    "Decision",
    "Capability",
    "CapabilityEnforcer",
    "Role",
    "RoleController",
    "Delegation",
    "DelegationManager",
    "DelegationType",
    "BrokenChainError",
    "RevocationEngine",
    "RevocationTrigger",
    "PartialRevocationError",
    "IsolationEnforcer",
    "IsolationBreachError",
    "SecretGovernor",
    "SecretStore",
    "InjectionGrant",
    "CredentialGovernor",
    "SecurityContext",
    "SecurityContextFactory",
    "SecurityContextDroppedError",
    "SecurityEventJournal",
    "SecurityEvent",
    "SecurityEventType",
    "Classification",
    "IncidentClassifier",
    "Incident",
    "IncidentCategory",
    "ConstitutionalEnforcer",
    "ConstitutionalViolationError",
]
