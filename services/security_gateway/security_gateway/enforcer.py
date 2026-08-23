"""Constitutional Enforcer (21B §22.3, realizes 14.33).

21B §22.4 calls this "the system's last line". 14.33.1 places enforcement of
the non-violable rules of Agent, Decision and Learning at this Gateway *at
the point of action* — not in documentation, not in review, not at design
time. 14.33.3 fixes the response: immediate blocking, principal suspension,
evidence preservation, human sovereign alert, and Category 1 escalation, with
"no appeal possible at the agent level".

Each check below is a structural guard: it cannot be configured off, and its
failure path raises rather than returning a status a caller could ignore.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from core.exceptions import AgentOSError
from security_gateway.enums import PrincipalType

#: The non-violable rules of document 14 this enforcer checks at the point of
#: action, keyed by the identifier used in violation records.
ENFORCED_RULES: Mapping[str, str] = {
    "R1": "No principal acts without a registered, authenticated identity",
    "R2": "No principal acts beyond the intersection of its six declared boundaries",
    "R3": "No self-escalation of permissions, roles, or autonomy",
    "R11": "No bypass of the Gateway for authentication or authorization",
    "R12": "No secret value exposed to an agent, workflow, or decision journal",
    "R13": "No journal modification after formation",
    "R14": "No anonymous or pseudonymous action",
    "R15": "No cross-tenant access without bilateral human approval",
    "R16": "No cached authorization surviving beyond its maximum TTL",
    "R17": "No revocation unpropagated beyond its latency budget",
    "R19": "No security subsystem change without human ratification",
    "R_AUTOAPPROVE": "No auto-approval on timeout (14.29.1, Constitutional Violation)",
}


class ConstitutionalViolationError(AgentOSError):
    """A non-violable rule was violated at the point of action.

    Carries the rule and the preserved evidence so the Gateway can journal a
    Category 1 incident without reconstructing context after the fact.
    """

    def __init__(self, rule: str, principal_id: str, detail: str, evidence: Mapping[str, Any] | None = None):
        super().__init__(f"[{rule}] {ENFORCED_RULES.get(rule, 'non-violable rule')}: {detail}")
        self.rule = rule
        self.principal_id = principal_id
        self.detail = detail
        self.evidence: Mapping[str, Any] = dict(evidence or {})


@dataclass
class ConstitutionalEnforcer:
    """Point-of-action enforcement of non-violable rules across all subsystems."""

    def require_registered_identity(self, principal_id: str | None, registered: bool, actionable: bool) -> None:
        """Rules 1 and 14 — no anonymous action, no action by an unregistered principal."""
        if not principal_id:
            raise ConstitutionalViolationError("R14", "<anonymous>", "action presented no principal identity")
        if not registered:
            raise ConstitutionalViolationError("R1", principal_id, "principal is not in the Identity Registry")
        if not actionable:
            raise ConstitutionalViolationError(
                "R1", principal_id, "principal is not Active; only Active identities may take new actions (14.8.2)"
            )

    def reject_self_escalation(self, actor_id: str, subject_id: str, change: str) -> None:
        """Rule 3 — a principal may never widen its own permissions, roles, or autonomy."""
        if actor_id == subject_id:
            raise ConstitutionalViolationError(
                "R3", actor_id, f"attempted to change its own {change}", {"change": change}
            )

    def reject_secret_exposure(self, principal_type: PrincipalType, sink: str, principal_id: str) -> None:
        """Rule 12 — no secret value reaches an agent, workflow, log, trace or journal."""
        if principal_type in (PrincipalType.AGENT, PrincipalType.WORKFLOW):
            raise ConstitutionalViolationError(
                "R12",
                principal_id,
                f"a {principal_type.value} may not receive a secret value (sink: {sink})",
                {"sink": sink},
            )
        if sink in ("journal", "log", "trace", "decision_journal"):
            raise ConstitutionalViolationError(
                "R12", principal_id, f"a secret value may never be written to the {sink}", {"sink": sink}
            )

    def reject_journal_modification(self, principal_id: str, journal: str) -> None:
        """Rule 13 — journals are append-only after formation; there is no edit path."""
        raise ConstitutionalViolationError(
            "R13", principal_id, f"attempted modification of the {journal} after formation", {"journal": journal}
        )

    def reject_auto_approval(self, principal_id: str, decision_class: str, decision_id: str) -> None:
        """Class C/D decisions never auto-approve on timeout (14.29.1).

        Structural, not configurable: the Decision Gateway (Stage S5) calls
        this on every timeout path, so there is no code route from "approval
        window elapsed" to "approved".
        """
        raise ConstitutionalViolationError(
            "R_AUTOAPPROVE",
            principal_id,
            f"Class {decision_class} decision '{decision_id}' cannot be approved by timeout",
            {"decision_class": decision_class, "decision_id": decision_id},
        )

    def require_human_ratification(self, change: str, ratified_by: str | None, ratifier_is_human: bool) -> None:
        """Rule 19 — no change to the security subsystem without human ratification (14.34.2)."""
        if ratified_by is None or not ratifier_is_human:
            raise ConstitutionalViolationError(
                "R19",
                ratified_by or "<none>",
                f"change '{change}' to the security subsystem requires human ratification",
                {"change": change},
            )

    def reject_human_credential_automation(
        self, credential_principal_type: PrincipalType, claiming_type: PrincipalType, principal_id: str
    ) -> None:
        """14.23.4 — human credentials are non-delegable and non-automated.

        This is the structural basis of human sovereignty: Level 4 authority is
        bound to a human credential and cannot be lent to anything else.
        """
        if credential_principal_type == PrincipalType.HUMAN and claiming_type != PrincipalType.HUMAN:
            raise ConstitutionalViolationError(
                "R11",
                principal_id,
                f"a {claiming_type.value} may not authenticate with a human credential (14.23.4)",
                {"claiming_type": claiming_type.value},
            )
