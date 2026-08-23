"""The invocation contract (12.17, 21B §19.3).

`12.17.1` frames it as "a constitutional contract between three parties: the
consumer (who requests), the Gateway (who authorizes), and the Executor (who
fulfils)."

Eight components, all required, enumerated in 21B §19.5: Idempotency Key,
Decision Reference, Capability Request, Context Package, Cost Ceiling,
Timeout, Compensation Reference, Attribution Chain. They are required fields
with no defaults, so an incomplete contract cannot be constructed — the
Contract Validator's job is then to check consistency, not presence.

The contract is **recorded immutably before dispatch** (21B §19.4), so an
external effect can never occur without a prior record of its authorization.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any

from tool_registry import SandboxTier


class InvocationOutcome(StrEnum):
    """How an invocation ended (21B §19.9)."""

    SUCCEEDED = "succeeded"
    DEGRADED = "degraded"
    FAILED = "failed"
    TIMED_OUT = "timed_out"
    COST_CEILING_BREACHED = "cost_ceiling_breached"
    SANDBOX_VIOLATION = "sandbox_violation"
    OUTPUT_REJECTED = "output_rejected"


@dataclass(frozen=True)
class AttributionChain:
    """Who is answerable for this effect (21B §19.15 guarantee 7).

    "Every external effect traces to tool, consumer, decision, workflow,
    agent, human, and budget." Consumer, decision and budget scope are
    required; the workflow, agent and human links are populated where the
    invocation has them.
    """

    consumer_id: str
    decision_id: str
    budget_scope: str
    tenant_id: str
    workflow_id: str | None = None
    agent_id: str | None = None
    human_id: str | None = None
    #: Set when this invocation consumed another tool's output, so composed
    #: output is never anonymous input (21B §19.4).
    upstream_invocation_id: str | None = None


@dataclass(frozen=True)
class InvocationContract:
    """The eight-component contract of 12.17, formed before dispatch."""

    invocation_id: str
    #: 12.17 — the idempotency key. A retry of the same logical request
    #: carries the same key, so the Executor can recognise a duplicate.
    idempotency_key: str
    decision_reference: str
    capability_request: str
    tool_id: str
    context_package: dict[str, Any]
    cost_ceiling: float
    timeout: timedelta
    compensation_reference: str | None
    attribution: AttributionChain
    sandbox_tier: SandboxTier
    egress_allowlist: tuple[str, ...]
    secret_refs: tuple[str, ...]
    formed_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    #: True when this contract invokes a tool's compensation rather than the
    #: tool itself (21B §19.5, Compensation Invocation).
    is_compensation: bool = False


@dataclass(frozen=True)
class InvocationRecord:
    """The immutable record of one invocation (21B §19.7, seven-year retention)."""

    contract: InvocationContract
    outcome: InvocationOutcome
    started_at: datetime
    completed_at: datetime
    actual_cost: float
    output_valid: bool
    detail: str
    degradation_flag: bool = False

    @property
    def invocation_id(self) -> str:
        return self.contract.invocation_id

    @property
    def duration(self) -> timedelta:
        return self.completed_at - self.started_at

    @property
    def succeeded(self) -> bool:
        return self.outcome == InvocationOutcome.SUCCEEDED


def new_invocation_id() -> str:
    return f"inv-{uuid.uuid4()}"
