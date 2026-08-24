"""Approval requests, batching, and timeout handling (05.18.2, 11.18).

`11.18.2`: "The runtime may not auto-approve on timeout, infer consent, or
bypass gates through creative interpretation."

That sentence is enforced structurally here, not documented. There is no code
path from an elapsed deadline to an approved state: `expire` can only produce
`DEFERRED` (Class C) or `REJECTED` (Class D), and `respond` requires a human
principal. A timeout is the absence of a decision, and the only thing the
system may do with an absence is refuse to proceed.

Batching (11.18.4) exists to reduce human context switching, and carries its
own hazard: a batch that could be approved as a unit would turn one click into
consent for things the operator never read. So `Batch.items` stay individually
actionable and `approve_batch` does not exist.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from core.exceptions import AgentOSError, ValidationError


class ApprovalState(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    #: Class C past its deadline. Not approved, not rejected: awaiting a human.
    DEFERRED = "deferred"
    MODIFICATION_DEMANDED = "modification_demanded"
    WITHDRAWN = "withdrawn"


class Urgency(StrEnum):
    """11.18.1's urgency classification."""

    ROUTINE = "routine"
    ELEVATED = "elevated"
    CRITICAL = "critical"


class NotHuman(AgentOSError):
    """Only a human may answer an approval gate (11.18.2, 14.17.5)."""


@dataclass(frozen=True)
class ApprovalRequest:
    """The contents 11.18.1 and 05.18.2 both enumerate.

    Every field is required because the list is the point: an operator asked to
    approve without the rollback plan, the alternatives, or the cost is being
    asked to rubber-stamp. `ApprovalRegistry.submit` validates completeness
    rather than trusting the caller.
    """

    request_id: str
    tenant_id: str
    decision_id: str
    decision_class: str
    #: What is proposed.
    proposal: str
    #: Why, with evidence.
    rationale: str
    evidence: tuple[str, ...]
    estimated_cost: float
    risk: str
    rollback_plan: str
    alternatives: tuple[str, ...]
    confidence: float
    urgency: Urgency
    deadline: datetime
    requested_by: str
    #: Set when this request belongs to a batch (11.18.4).
    batch_id: str | None = None


@dataclass
class ApprovalRecord:
    """Mutable state for one request."""

    request: ApprovalRequest
    state: ApprovalState = ApprovalState.PENDING
    responded_by: str | None = None
    responded_at: datetime | None = None
    note: str = ""

    @property
    def request_id(self) -> str:
        return self.request.request_id

    @property
    def is_open(self) -> bool:
        return self.state in (ApprovalState.PENDING, ApprovalState.DEFERRED)


@dataclass(frozen=True)
class Batch:
    """Related requests presented together (11.18.4).

    Presented together, decided separately. There is deliberately no method
    here that answers all of them at once.
    """

    batch_id: str
    tenant_id: str
    items: tuple[str, ...]
    assembled_at: datetime
    reason: str


@dataclass
class ApprovalRegistry:
    """Durable, actionable approval requests (05.18.2)."""

    #: Callable answering whether a principal is a human. Delegated to the
    #: Trust Plane rather than inferred from an id.
    is_human: Callable[[str], bool]
    now: Callable[[], datetime] = field(default=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        self._records: dict[str, ApprovalRecord] = {}
        self._batches: dict[str, Batch] = {}

    def submit(self, request: ApprovalRequest) -> ApprovalRecord:
        if request.request_id in self._records:
            raise AgentOSError(f"approval request '{request.request_id}' already exists")
        _assert_complete(request)
        record = ApprovalRecord(request=request)
        self._records[request.request_id] = record
        return record

    def get(self, request_id: str) -> ApprovalRecord:
        record = self._records.get(request_id)
        if record is None:
            raise AgentOSError(f"approval request '{request_id}' does not exist")
        return record

    def pending(self, tenant_id: str | None = None) -> list[ApprovalRecord]:
        return [
            r for r in self._records.values() if r.is_open and (tenant_id is None or r.request.tenant_id == tenant_id)
        ]

    def respond(
        self,
        request_id: str,
        principal_id: str,
        state: ApprovalState,
        note: str = "",
    ) -> ApprovalRecord:
        """Records a human's answer. There is no machine path into this method."""
        if not self.is_human(principal_id):
            raise NotHuman(
                f"'{principal_id}' is not a human principal; only a human may answer an approval gate (11.18.2)"
            )
        if state not in (
            ApprovalState.APPROVED,
            ApprovalState.REJECTED,
            ApprovalState.DEFERRED,
            ApprovalState.MODIFICATION_DEMANDED,
        ):
            raise ValidationError(f"'{state.value}' is not an approval response")
        record = self.get(request_id)
        if not record.is_open:
            raise AgentOSError(f"approval request '{request_id}' is already {record.state.value}")
        record.state = state
        record.responded_by = principal_id
        record.responded_at = self.now()
        record.note = note
        return record

    def expire(self) -> list[ApprovalRecord]:
        """Applies 11.18.3 to every request past its deadline.

        Class C defers, Class D rejects. Neither approves, and no argument to
        this method could make it approve, because the approved state is
        unreachable from here.
        """
        now = self.now()
        expired: list[ApprovalRecord] = []
        for record in self._records.values():
            if record.state != ApprovalState.PENDING or record.request.deadline > now:
                continue
            if record.request.decision_class.upper() == "D":
                record.state = ApprovalState.REJECTED
                record.note = "deadline passed; Class D rejects pending explicit human action (11.18.3)"
            else:
                record.state = ApprovalState.DEFERRED
                record.note = "deadline passed; deferred, not approved (11.18.3)"
            expired.append(record)
        return expired

    # ------------------------------------------------------------- Batching

    def assemble_batch(self, batch_id: str, tenant_id: str, request_ids: Sequence[str], reason: str) -> Batch:
        """Groups related requests to minimize context switching (11.18.4)."""
        if not request_ids:
            raise ValidationError("a batch with no items is not a batch")
        for request_id in request_ids:
            record = self.get(request_id)
            if record.request.tenant_id != tenant_id:
                raise ValidationError(
                    f"'{request_id}' belongs to another tenant; a batch must not cross the tenant boundary"
                )
        batch = Batch(
            batch_id=batch_id,
            tenant_id=tenant_id,
            items=tuple(request_ids),
            assembled_at=self.now(),
            reason=reason,
        )
        self._batches[batch_id] = batch
        return batch

    def batch(self, batch_id: str) -> Batch:
        batch = self._batches.get(batch_id)
        if batch is None:
            raise AgentOSError(f"batch '{batch_id}' does not exist")
        return batch

    def batch_items(self, batch_id: str) -> list[ApprovalRecord]:
        """Each item, individually actionable (11.18.4)."""
        return [self.get(request_id) for request_id in self.batch(batch_id).items]

    def health(self) -> dict[str, Any]:
        records = list(self._records.values())
        by_state: dict[str, int] = {}
        for record in records:
            by_state[record.state.value] = by_state.get(record.state.value, 0) + 1
        answered = [r for r in records if r.responded_at is not None]
        return {
            "requests": len(records),
            "by_state": by_state,
            "open": len([r for r in records if r.is_open]),
            "batches": len(self._batches),
            "answered": len(answered),
            # Reported so the number is visible rather than assumed. Nothing in
            # this module can increment it: the approved state is unreachable
            # without a human principal (11.18.2).
            "auto_approved": 0,
            "answered_after_deadline": len(
                [r for r in answered if r.responded_at and r.responded_at > r.request.deadline]
            ),
        }


def _assert_complete(request: ApprovalRequest) -> None:
    """11.18.1's list is a completeness requirement, not a suggestion."""
    missing = [
        name
        for name, value in (
            ("proposal", request.proposal),
            ("rationale", request.rationale),
            ("rollback_plan", request.rollback_plan),
            ("risk", request.risk),
        )
        if not str(value).strip()
    ]
    if not request.evidence:
        missing.append("evidence")
    if not request.alternatives:
        missing.append("alternatives")
    if missing:
        raise ValidationError(
            f"approval request '{request.request_id}' omits {missing}; 11.18.1 requires all of them, "
            "because an operator without them is being asked to rubber-stamp"
        )
    if not 0.0 <= request.confidence <= 1.0:
        raise ValidationError("confidence must be between 0 and 1")
    if request.estimated_cost < 0:
        raise ValidationError("estimated cost must not be negative")
