"""Identity Registry and Registration Controller — unit tests (14.4, 14.8)."""

from __future__ import annotations

import pytest

from core.exceptions import NotFoundError
from kernel.lifecycle import InvalidTransitionError
from persistence.in_memory import InMemoryRepository
from security_gateway import PrincipalType, RegistrationRequest, SecurityGateway
from security_gateway.enums import PrincipalStatus
from security_gateway.identity import (
    ApprovalRequiredError,
    IdentityCollisionError,
    IdentityRegistry,
    RegistrationController,
)

from .conftest import AGENT, HUMAN, TENANT


def _fresh() -> RegistrationController:
    return RegistrationController(IdentityRegistry(InMemoryRepository()))


def test_registration_requires_an_approver(gateway: SecurityGateway) -> None:
    with pytest.raises(ApprovalRequiredError):
        gateway.register_identity(
            RegistrationRequest(
                principal_id="agent-unapproved",
                principal_type=PrincipalType.AGENT,
                name="Unapproved",
                version="1.0.0",
                tenant_id=TENANT,
            )
        )


def test_registration_rejects_self_approval(gateway: SecurityGateway) -> None:
    with pytest.raises(ApprovalRequiredError, match="self-approval"):
        gateway.register_identity(
            RegistrationRequest(
                principal_id="agent-self",
                principal_type=PrincipalType.AGENT,
                name="Self",
                version="1.0.0",
                tenant_id=TENANT,
                approved_by="agent-self",
            )
        )


def test_registration_approver_must_be_human(gateway: SecurityGateway) -> None:
    with pytest.raises(ApprovalRequiredError, match="requires a Human"):
        gateway.register_identity(
            RegistrationRequest(
                principal_id="agent-two",
                principal_type=PrincipalType.AGENT,
                name="Two",
                version="1.0.0",
                tenant_id=TENANT,
                approved_by=AGENT,
            )
        )


def test_principal_ids_are_never_reused(gateway: SecurityGateway) -> None:
    with pytest.raises(IdentityCollisionError):
        gateway.register_identity(
            RegistrationRequest(
                principal_id=AGENT,
                principal_type=PrincipalType.AGENT,
                name="Duplicate",
                version="2.0.0",
                tenant_id=TENANT,
                approved_by=HUMAN,
            )
        )


def test_bootstrap_human_only_works_on_an_empty_registry(gateway: SecurityGateway) -> None:
    with pytest.raises(ApprovalRequiredError, match="empty registry"):
        gateway.bootstrap_human_sovereign("human-second", "Second", TENANT)


def test_lifecycle_guards_reject_undefined_transitions(gateway: SecurityGateway) -> None:
    # Active -> Archived is not an edge in 14.8.3; only Retired -> Archived is.
    with pytest.raises(InvalidTransitionError):
        gateway.change_principal_status(AGENT, PrincipalStatus.ARCHIVED, actor_id=HUMAN)


def test_identity_persists_through_suspension_and_retirement(gateway: SecurityGateway) -> None:
    gateway.change_principal_status(AGENT, PrincipalStatus.SUSPENDED, actor_id=HUMAN)
    assert gateway.registry.get(AGENT).status == PrincipalStatus.SUSPENDED
    gateway.change_principal_status(AGENT, PrincipalStatus.RETIRED, actor_id=HUMAN)
    retired = gateway.registry.get(AGENT)
    assert retired.status == PrincipalStatus.RETIRED
    assert retired.retired_at is not None
    # 14.4.2 — the identity remains resident in the registry after retirement.
    assert gateway.registry.exists(AGENT)


def test_lineage_chains_back_to_the_root_identity(gateway: SecurityGateway) -> None:
    gateway.register_identity(
        RegistrationRequest(
            principal_id="agent-writer-v2",
            principal_type=PrincipalType.AGENT,
            name="Writer",
            version="2.0.0",
            tenant_id=TENANT,
            lineage_ref=AGENT,
            approved_by=HUMAN,
        )
    )
    assert gateway.registry.lineage("agent-writer-v2") == ["agent-writer-v2", AGENT]


def test_unknown_principal_lookup_raises_not_found() -> None:
    controller = _fresh()
    controller.bootstrap_human("h", "H", TENANT)
    with pytest.raises(NotFoundError):
        controller._registry.get("nobody")


def test_self_status_change_is_rejected_as_self_escalation(gateway: SecurityGateway) -> None:
    from security_gateway.enforcer import ConstitutionalViolationError

    with pytest.raises(ConstitutionalViolationError):
        gateway.change_principal_status(AGENT, PrincipalStatus.SUSPENDED, actor_id=AGENT)
