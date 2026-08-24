"""The Human Interface — one surface for human sovereignty (Build Spec S8).

The Build Specification's rationale for this module: it "consolidates
human-plane requirements scattered across 05.18, 11.18, 13.33, 16.25, 17.31,
18.35, 19.36 into a single interface layer."

Consolidation is the whole value. Seven documents each grant humans the right
to approve, override, be informed, and halt. Implemented separately in seven
Gateways, those rights would be seven slightly different implementations, and
the differences would be where sovereignty leaks. Here there is one approval
registry, one override ledger, one digest service, and one panic switch.

`05.18.1`: **"Human operators are not users; they are sovereign delegates."**
The asymmetry runs through every method: a human may override the system, and
the system may not override a human.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from core.exceptions import AgentOSError
from human_interface.approvals import (
    ApprovalRecord,
    ApprovalRegistry,
    ApprovalRequest,
    ApprovalState,
    Batch,
)
from human_interface.digests import Digest, DigestService, Notification, Severity
from human_interface.overrides import (
    Override,
    OverrideLedger,
    OverrideScope,
    StandingOrder,
    StandingOrderRegistry,
)
from human_interface.panic import PanicReport, PanicSwitch, Participant
from kernel.signals import SignalEmitter, SignalType


class HaltedError(AgentOSError):
    """Refused because the Panic Protocol is active and a human has not resumed."""


@dataclass
class HumanInterface:
    """Layer 13. The human plane's single surface."""

    is_human: Callable[[str], bool]
    signals: SignalEmitter
    #: Where a critical notification goes immediately (18.35.4, 19.36.5).
    notify: Callable[[Notification], None] = field(default=lambda notification: None)
    escalate: Callable[[Any, str], None] = field(default=lambda trigger, detail: None)
    now: Callable[[], datetime] = field(default=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        self.approvals = ApprovalRegistry(is_human=self.is_human, now=self.now)
        self.overrides = OverrideLedger(is_human=self.is_human, now=self.now)
        self.standing_orders = StandingOrderRegistry(is_human=self.is_human, now=self.now)
        self.digests = DigestService(deliver_now=self.notify, now=self.now)
        self.panic = PanicSwitch(
            is_human=self.is_human,
            escalate=self.escalate,
            flush_digests=lambda: len(self.digests.flush_all()),
            now=self.now,
        )

    # ------------------------------------------------------------ Approvals

    def submit_approval(self, request: ApprovalRequest) -> ApprovalRecord:
        """Accepts a request for human judgement.

        Permitted during panic: a halted system may still ask, and queuing the
        question loses nothing. What it may not do is act on the answer, and
        the acting side is gated elsewhere.
        """
        record = self.approvals.submit(request)
        self.digests.submit(
            Notification(
                notification_id=f"approval-{request.request_id}",
                tenant_id=request.tenant_id,
                severity=Severity.CRITICAL if request.urgency.value == "critical" else Severity.ROUTINE,
                subsystem="decision_gateway",
                summary=f"approval requested: {request.proposal}",
                detail={"request_id": request.request_id, "class": request.decision_class},
                raised_at=self.now(),
            )
        )
        return record

    def pending_approvals(self, tenant_id: str | None = None) -> list[ApprovalRecord]:
        return self.approvals.pending(tenant_id)

    def approve(self, request_id: str, principal_id: str, note: str = "") -> ApprovalRecord:
        return self._respond(request_id, principal_id, ApprovalState.APPROVED, note)

    def reject(self, request_id: str, principal_id: str, note: str = "") -> ApprovalRecord:
        return self._respond(request_id, principal_id, ApprovalState.REJECTED, note)

    def demand_modification(self, request_id: str, principal_id: str, note: str) -> ApprovalRecord:
        return self._respond(request_id, principal_id, ApprovalState.MODIFICATION_DEMANDED, note)

    def _respond(self, request_id: str, principal_id: str, state: ApprovalState, note: str) -> ApprovalRecord:
        record = self.approvals.respond(request_id, principal_id, state, note)
        self.signals.emit(
            SignalType.EVENT,
            "human.approval.answered",
            record.request.tenant_id,
            request_id=request_id,
            state=state.value,
            by=principal_id,
        )
        return record

    def expire_approvals(self) -> list[ApprovalRecord]:
        """11.18.3. Defers or rejects; never approves."""
        expired = self.approvals.expire()
        for record in expired:
            self.signals.emit(
                SignalType.EVENT,
                "human.approval.expired",
                record.request.tenant_id,
                request_id=record.request_id,
                state=record.state.value,
            )
        return expired

    def batch_approvals(self, batch_id: str, tenant_id: str, request_ids: Sequence[str], reason: str) -> Batch:
        """11.18.4 — presented together, still answered one at a time."""
        return self.approvals.assemble_batch(batch_id, tenant_id, request_ids, reason)

    # ------------------------------------------------------------ Overrides

    def override(
        self,
        override_id: str,
        tenant_id: str,
        scope: OverrideScope,
        target_id: str,
        directive: str,
        reason: str,
        issued_by: str,
    ) -> Override:
        """Immediate, irreversible by the system, logged as Class D.

        Available while halted: an override is often *how* an operator
        resolves the condition that caused the panic.
        """
        record = self.overrides.issue(override_id, tenant_id, scope, target_id, directive, reason, issued_by)
        self.signals.emit(
            SignalType.EVENT,
            "human.override.issued",
            tenant_id,
            override_id=override_id,
            scope=scope.value,
            target_id=target_id,
            by=issued_by,
        )
        self.digests.submit(
            Notification(
                notification_id=f"override-{override_id}",
                tenant_id=tenant_id,
                severity=Severity.ELEVATED,
                subsystem="human_interface",
                summary=f"human override on {scope.value} '{target_id}'",
                detail={"directive": directive, "reason": reason},
                raised_at=self.now(),
            )
        )
        return record

    # ------------------------------------------------------- Standing orders

    def delegate(
        self,
        order_id: str,
        tenant_id: str,
        issued_by: str,
        scope: frozenset[str],
        directive: str,
        ttl: timedelta | None = None,
    ) -> StandingOrder:
        """05.18.5 — scoped, time-bounded, revocable."""
        return self.standing_orders.issue(order_id, tenant_id, issued_by, scope, directive, ttl)

    # ---------------------------------------------------------- Notification

    def raise_notification(self, notification: Notification) -> str:
        """Routes by severity. Returns the channel used."""
        return self.digests.submit(notification)

    def digest_due(self, tenant_id: str) -> bool:
        return self.digests.due(tenant_id)

    def deliver_digest(self, tenant_id: str, digest_id: str) -> Digest:
        digest = self.digests.assemble(tenant_id, digest_id)
        self.signals.emit(
            SignalType.EVENT,
            "human.digest.delivered",
            tenant_id,
            digest_id=digest_id,
            items=digest.size,
        )
        return digest

    # ---------------------------------------------------------------- Panic

    def register_panic_participant(self, participant: Participant) -> Participant:
        return self.panic.register(participant)

    def invoke_panic(self, principal_id: str, reason: str) -> PanicReport:
        """05.18.4's single command, bounded at five seconds by 17.31.4."""
        report = self.panic.invoke(principal_id, reason)
        self.signals.emit(
            SignalType.EVENT,
            "human.panic.invoked",
            "all",
            by=principal_id,
            elapsed_seconds=report.elapsed_seconds,
            halted=list(report.halted),
        )
        return report

    def resume(self, principal_id: str, note: str = "") -> None:
        self.panic.resume(principal_id, note)
        self.signals.emit(SignalType.EVENT, "human.panic.resumed", "all", by=principal_id)

    def assert_not_halted(self, operation: str) -> None:
        """The guard autonomous callers use. Humans are never subject to it."""
        if self.panic.halted:
            raise HaltedError(
                f"'{operation}' is refused: the Panic Protocol is active and only human "
                "intervention resumes autonomous activity (05.18.4)"
            )

    # --------------------------------------------------------------- Health

    def health(self) -> Mapping[str, Any]:
        return {
            "approvals": self.approvals.health(),
            "overrides": len(self.overrides),
            "standing_orders": self.standing_orders.health(),
            "digests": self.digests.health(),
            "panic": self.panic.health(),
        }
