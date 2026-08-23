"""Tool Gateway — the only path from intent to effect (12.6.2, 21B §19).

| 21B §19.5 interface        | Method                    |
|----------------------------|---------------------------|
| Tool Invocation            | `invoke`                  |
| Compensation Invocation    | `compensate`              |
| Invocation Record Query    | `query_records`           |
| Tool Health Signals        | `health`                  |

**The verification sequence is ordered so the cheapest disqualifying check
runs first** (21B §19.4): consumer authenticity, autonomy boundary, tenant
boundary, decision validity, budget sufficiency, input contract, sandbox
assignment. A request failing an early check consumes no downstream resource.

**Sandbox escalation, never de-escalation.** The Gateway refuses any request
to execute below a tool's declared tier, even where a consumer asks for a
lower one. In composition, 12.18.3 requires the whole chain at the highest
tier any component needs.

The Gateway authorizes and records; it does not execute. Dispatch is the
Executor's job, and the separation is why policy and execution do not share a
process (21B §19.4).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

from core.exceptions import AgentOSError
from kernel.escalation import EscalationChannel, EscalationTrigger
from kernel.journal import ImmutableJournal
from kernel.signals import SignalEmitter, SignalType
from tool_gateway.contracts import (
    AttributionChain,
    InvocationContract,
    InvocationOutcome,
    InvocationRecord,
    new_invocation_id,
)
from tool_registry import SandboxTier, ToolRecord, ToolRegistry, ToolState

#: [Engineering Decision] 12.21 requires per-tool circuit breakers without
#: publishing thresholds.
BREAKER_FAILURE_THRESHOLD = 5
BREAKER_COOLDOWN = timedelta(minutes=5)


class InvocationRefused(AgentOSError):
    """Blocked before any external effect. Carries which gate refused it."""

    def __init__(self, gate: str, reason: str):
        super().__init__(f"invocation refused at {gate}: {reason}")
        self.gate = gate
        self.reason = reason


class SandboxDeEscalation(AgentOSError):
    """A request to execute below a tool's declared tier (12 rule 4)."""


class ToolAuthorizer(Protocol):
    """Consumer authentication and permission (21B §19.6)."""

    def principal_of(self, token: str) -> tuple[str, str]: ...

    def autonomy_level(self, principal_id: str) -> int: ...

    def is_human(self, principal_id: str) -> bool: ...

    def may_invoke(self, token: str, tenant_id: str, capability: str) -> bool: ...


class DecisionSource(Protocol):
    """Committed decision verification (21B §19.6, 12 rule 2)."""

    def verify(self, decision_id: str, required_class: str) -> bool: ...


class BudgetSource(Protocol):
    """Pre-flight budget check and post-flight attribution (21B §19.6)."""

    def has_headroom(self, tenant_id: str, cost: float) -> bool: ...

    def record_spend(self, tenant_id: str, scope: str, cost: float, operation: str, principal_id: str) -> None: ...


class IntegrationSource(Protocol):
    """Verifies a tool's declared abstraction is backed by an active integration.

    21B §19.6 lists this edge. The Integration Platform is CIR-001
    construction-blocked, so the default implementation reports every
    abstraction unbacked and the Gateway refuses tools that depend on one —
    which is the honest behaviour while that platform cannot be constructed.
    """

    def is_backed(self, abstraction: str, tenant_id: str) -> bool: ...


@dataclass
class CircuitBreaker:
    """Per-tool failure and cost thresholds (21B §19.3)."""

    now: Callable[[], datetime] = field(default=lambda: datetime.now(UTC))
    failure_threshold: int = BREAKER_FAILURE_THRESHOLD
    cooldown: timedelta = BREAKER_COOLDOWN
    _failures: dict[str, int] = field(default_factory=dict, init=False)
    _opened_at: dict[str, datetime] = field(default_factory=dict, init=False)

    def check(self, tool_id: str) -> None:
        opened = self._opened_at.get(tool_id)
        if opened is None:
            return
        if self.now() < opened + self.cooldown:
            raise InvocationRefused(
                "circuit_breaker",
                f"tool '{tool_id}' is circuit-broken until {(opened + self.cooldown).isoformat()}",
            )
        # Cooldown elapsed: allow one probe through and reset the count.
        del self._opened_at[tool_id]
        self._failures[tool_id] = 0

    def record(self, tool_id: str, succeeded: bool) -> None:
        if succeeded:
            self._failures[tool_id] = 0
            self._opened_at.pop(tool_id, None)
            return
        self._failures[tool_id] = self._failures.get(tool_id, 0) + 1
        if self._failures[tool_id] >= self.failure_threshold:
            self._opened_at[tool_id] = self.now()

    def is_open(self, tool_id: str) -> bool:
        return tool_id in self._opened_at

    def open_tools(self) -> list[str]:
        return sorted(self._opened_at)


@dataclass
class ToolGateway:
    """Authorizes every invocation. Layer 4 (21B §19.13)."""

    registry: ToolRegistry
    authorizer: ToolAuthorizer
    decisions: DecisionSource
    budget: BudgetSource
    integrations: IntegrationSource
    signals: SignalEmitter
    now: Callable[[], datetime] = field(default=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        self.breaker = CircuitBreaker(now=self.now)
        self.journal = ImmutableJournal()
        self.escalations = EscalationChannel(subsystem="tool_gateway", is_human=self.authorizer.is_human, now=self.now)
        self._contracts: dict[str, InvocationContract] = {}
        self._records: dict[str, InvocationRecord] = {}
        self._refusals: dict[str, int] = {}

    # ------------------------------------------------------------ Invocation

    def authorize(
        self,
        token: str,
        tool_id: str,
        decision_id: str,
        parameters: dict[str, Any],
        cost_ceiling: float,
        idempotency_key: str,
        required_decision_class: str = "A",
        workflow_id: str | None = None,
        upstream_invocation_id: str | None = None,
        requested_tier: SandboxTier | None = None,
    ) -> InvocationContract:
        """**Tool Invocation** (21B §19.5), authorization half.

        Returns a validated contract, recorded immutably before the Executor
        sees it. Every refusal path raises before an effect is possible.
        """
        principal_id, principal_tenant = self.authorizer.principal_of(token)
        record = self.registry.get(tool_id)
        manifest = record.manifest

        # 1. Consumer authenticity and permission — cheapest disqualifier.
        if not self.authorizer.may_invoke(token, principal_tenant, manifest.capability):
            self._refuse("authenticity", f"'{principal_id}' may not invoke '{manifest.capability}'")

        # 2. Tenant boundary.
        if manifest.tenant_id != principal_tenant:
            self._refuse("tenant", f"tool '{tool_id}' belongs to another tenant")

        # 3. Tool must be Active. Registration is not authorization (12 rule 1).
        if not record.is_invocable:
            self._refuse("registration", f"tool '{tool_id}' is {record.state.value}, not Active")

        # 4. Autonomy boundary and trust.
        if not record.autonomously_invocable and not self.authorizer.is_human(principal_id):
            self._refuse(
                "autonomy",
                f"tool '{tool_id}' is below the trust threshold and is human-invocation only (21B §19.9)",
            )

        # 5. Circuit breaker, before any decision or budget work.
        self.breaker.check(tool_id)

        # 6. Decision validity — 12 rule 2, no execution without one.
        if not self.decisions.verify(decision_id, required_decision_class):
            self._refuse(
                "decision",
                f"decision '{decision_id}' is missing or of insufficient authority for tool '{tool_id}'",
            )

        # 7. Integration backing, where the tool reaches outside.
        if manifest.integration_abstraction is not None and not self.integrations.is_backed(
            manifest.integration_abstraction, principal_tenant
        ):
            self._refuse(
                "integration",
                f"capability abstraction '{manifest.integration_abstraction}' is not backed by an active, "
                "approved integration",
            )

        # 8. Budget sufficiency.
        if not self.budget.has_headroom(principal_tenant, cost_ceiling):
            self._refuse("budget", f"no budget headroom for a ceiling of {cost_ceiling}")
        if cost_ceiling < manifest.cost_per_invocation:
            self._refuse(
                "budget",
                f"cost ceiling {cost_ceiling} is below the tool's declared cost {manifest.cost_per_invocation}",
            )

        # 9. Input contract.
        errors = manifest.input_contract.validate(parameters)
        if errors:
            self._refuse("input_contract", "; ".join(errors))

        # 10. Sandbox assignment — escalation only.
        tier = self._assign_tier(manifest.sandbox_tier, requested_tier)

        contract = InvocationContract(
            invocation_id=new_invocation_id(),
            idempotency_key=idempotency_key,
            decision_reference=decision_id,
            capability_request=manifest.capability,
            tool_id=tool_id,
            context_package=dict(parameters),
            cost_ceiling=cost_ceiling,
            timeout=manifest.timeout,
            compensation_reference=(manifest.compensation.reference if manifest.compensation is not None else None),
            attribution=AttributionChain(
                consumer_id=principal_id,
                decision_id=decision_id,
                budget_scope=f"tenant:{principal_tenant}",
                tenant_id=principal_tenant,
                workflow_id=workflow_id,
                agent_id=principal_id if not self.authorizer.is_human(principal_id) else None,
                human_id=principal_id if self.authorizer.is_human(principal_id) else None,
                upstream_invocation_id=upstream_invocation_id,
            ),
            sandbox_tier=tier,
            egress_allowlist=manifest.egress_allowlist,
            secret_refs=manifest.secret_refs,
            formed_at=self.now(),
        )
        self._validate_contract(contract, record)
        self._contracts[contract.invocation_id] = contract
        # Recorded before dispatch: no effect without a prior record (21B §19.4).
        self._journal_contract(contract)
        return contract

    def _assign_tier(self, declared: SandboxTier, requested: SandboxTier | None) -> SandboxTier:
        """Sandbox Assigner: refuses any tier below the declared minimum (12 rule 4)."""
        if requested is None:
            return declared
        if requested < declared:
            raise SandboxDeEscalation(
                f"requested tier {requested.name} is below the tool's declared {declared.name}; "
                "the Gateway escalates isolation but never lowers it (12 rule 4)"
            )
        return requested

    def compose_tier(self, tool_ids: tuple[str, ...]) -> SandboxTier:
        """12.18.3 — a composed chain runs at the highest tier any member requires."""
        return max(
            (self.registry.get(tool_id).manifest.sandbox_tier for tool_id in tool_ids),
            default=SandboxTier.NONE,
        )

    def _validate_contract(self, contract: InvocationContract, record: ToolRecord) -> None:
        """Contract Validator: all components present and consistent (21B §19.3)."""
        problems: list[str] = []
        if not contract.idempotency_key:
            problems.append("idempotency key is empty")
        if not contract.decision_reference:
            problems.append("decision reference is empty")
        if contract.timeout <= timedelta(0):
            problems.append("timeout must be positive")
        if contract.cost_ceiling <= 0:
            problems.append("cost ceiling must be positive")
        if record.manifest.is_mutating and contract.compensation_reference is None:
            problems.append("a mutating tool's contract must carry a compensation reference (12 rule 9)")
        if contract.sandbox_tier < record.manifest.sandbox_tier:
            problems.append("assigned sandbox tier is below the declared minimum")
        if problems:
            self._refuse("contract", "; ".join(problems))

    # ---------------------------------------------------------- Completion

    def complete(
        self,
        invocation_id: str,
        outcome: InvocationOutcome,
        output: dict[str, Any] | None,
        actual_cost: float,
        started_at: datetime,
        detail: str = "",
    ) -> InvocationRecord:
        """Validates output and records the invocation immutably.

        12.25.4 treats external return data as untrusted until validated, so
        output-contract validation happens here, on the way back — and
        unvalidated output is never returned to the consumer.
        """
        contract = self._contracts.get(invocation_id)
        if contract is None:
            raise AgentOSError(f"no contract for invocation '{invocation_id}'")
        record = self.registry.get(contract.tool_id)

        output_valid = True
        if outcome == InvocationOutcome.SUCCEEDED:
            errors = record.manifest.output_contract.validate(output or {})
            if errors:
                output_valid = False
                outcome = InvocationOutcome.OUTPUT_REJECTED
                detail = f"output contract violation: {'; '.join(errors)}"

        completed = InvocationRecord(
            contract=contract,
            outcome=outcome,
            started_at=started_at,
            completed_at=self.now(),
            actual_cost=actual_cost,
            output_valid=output_valid,
            detail=detail,
            degradation_flag=outcome == InvocationOutcome.DEGRADED,
        )
        self._records[invocation_id] = completed

        succeeded = outcome in (InvocationOutcome.SUCCEEDED, InvocationOutcome.DEGRADED)
        self.breaker.record(contract.tool_id, succeeded)
        self.registry.record_outcome(contract.tool_id, succeeded)
        self.budget.record_spend(
            contract.attribution.tenant_id,
            contract.attribution.budget_scope,
            actual_cost,
            f"tool:{contract.tool_id}",
            contract.attribution.consumer_id,
        )

        if outcome == InvocationOutcome.SANDBOX_VIOLATION:
            # 21B §19.10 — a sandbox escape is a Category 1 security incident,
            # not an operational failure.
            self.escalations.raise_incident(
                EscalationTrigger.AUTHORITY_BYPASS,
                contract.attribution.consumer_id,
                contract.attribution.tenant_id,
                f"sandbox violation during invocation of '{contract.tool_id}'",
                {"invocation_id": invocation_id, "tool_id": contract.tool_id, "detail": detail},
            )
            self.registry.transition(contract.tool_id, ToolState.SUSPENDED, reason="sandbox violation")

        self._journal_record(completed)
        self.signals.emit(
            SignalType.METRIC,
            "tool.invocation.cost",
            contract.attribution.tenant_id,
            value=actual_cost,
            tool_id=contract.tool_id,
            outcome=outcome.value,
        )
        return completed

    def compensate(
        self,
        token: str,
        invocation_id: str,
        decision_id: str,
    ) -> InvocationContract:
        """**Compensation Invocation** (21B §19.5). Consumer: Workflow Engine.

        Invokes a tool's compensation during saga rollback. The compensation
        contract references the invocation it undoes, so a rollback is
        traceable to what it reverses.
        """
        original = self._records.get(invocation_id)
        if original is None:
            raise AgentOSError(f"invocation '{invocation_id}' has no record to compensate")
        if original.contract.compensation_reference is None:
            raise AgentOSError(f"invocation '{invocation_id}' carries no compensation reference; it is not reversible")
        principal_id, principal_tenant = self.authorizer.principal_of(token)
        contract = InvocationContract(
            invocation_id=new_invocation_id(),
            idempotency_key=f"compensate:{invocation_id}",
            decision_reference=decision_id,
            capability_request=original.contract.capability_request,
            tool_id=original.contract.tool_id,
            context_package={"compensates": invocation_id},
            cost_ceiling=original.contract.cost_ceiling,
            timeout=original.contract.timeout,
            compensation_reference=original.contract.compensation_reference,
            attribution=AttributionChain(
                consumer_id=principal_id,
                decision_id=decision_id,
                budget_scope=f"tenant:{principal_tenant}",
                tenant_id=principal_tenant,
                upstream_invocation_id=invocation_id,
            ),
            sandbox_tier=original.contract.sandbox_tier,
            egress_allowlist=original.contract.egress_allowlist,
            secret_refs=original.contract.secret_refs,
            formed_at=self.now(),
            is_compensation=True,
        )
        self._contracts[contract.invocation_id] = contract
        self._journal_contract(contract)
        return contract

    # ---------------------------------------------------------------- Query

    def query_records(
        self,
        tool_id: str | None = None,
        consumer_id: str | None = None,
        decision_id: str | None = None,
    ) -> list[InvocationRecord]:
        """**Invocation Record Query** (21B §19.5). Consumers: Governance, Learning."""
        return [
            record
            for record in self._records.values()
            if (tool_id is None or record.contract.tool_id == tool_id)
            and (consumer_id is None or record.contract.attribution.consumer_id == consumer_id)
            and (decision_id is None or record.contract.decision_reference == decision_id)
        ]

    def contract_for(self, invocation_id: str) -> InvocationContract:
        contract = self._contracts.get(invocation_id)
        if contract is None:
            raise AgentOSError(f"no contract for invocation '{invocation_id}'")
        return contract

    def health(self) -> Mapping[str, Any]:
        """**Tool Health Signals** (21B §19.5) — the six families of 12.27.1."""
        records = list(self._records.values())
        by_outcome: dict[str, int] = {}
        for record in records:
            by_outcome[record.outcome.value] = by_outcome.get(record.outcome.value, 0) + 1
        succeeded = sum(1 for r in records if r.succeeded)
        return {
            "usage": {"invocations": len(records), "contracts_formed": len(self._contracts)},
            "reliability": {
                "success_rate": round(succeeded / len(records), 4) if records else 0.0,
                "by_outcome": by_outcome,
            },
            "economic": {
                "total_cost": round(sum(r.actual_cost for r in records), 6),
                "open_breakers": self.breaker.open_tools(),
            },
            "security": {
                "sandbox_violations": by_outcome.get(InvocationOutcome.SANDBOX_VIOLATION.value, 0),
                "refusals_by_gate": dict(self._refusals),
                "unacknowledged_incidents": len(self.escalations.unacknowledged()),
            },
            "journal_entries": len(self.journal),
            "journal_intact": self.journal.verify_chain(),
        }

    # ------------------------------------------------------------ Internals

    def _refuse(self, gate: str, reason: str) -> None:
        self._refusals[gate] = self._refusals.get(gate, 0) + 1
        self.journal.append({"kind": "refusal", "gate": gate, "reason": reason})
        raise InvocationRefused(gate, reason)

    def _journal_contract(self, contract: InvocationContract) -> None:
        self.journal.append(
            {
                "kind": "contract",
                "invocation_id": contract.invocation_id,
                "tool_id": contract.tool_id,
                "tenant_id": contract.attribution.tenant_id,
                "consumer": contract.attribution.consumer_id,
                "decision": contract.decision_reference,
                "idempotency_key": contract.idempotency_key,
                "sandbox_tier": contract.sandbox_tier.name,
                "cost_ceiling": contract.cost_ceiling,
                "is_compensation": contract.is_compensation,
            }
        )

    def _journal_record(self, record: InvocationRecord) -> None:
        self.journal.append(
            {
                "kind": "invocation",
                "invocation_id": record.invocation_id,
                "tool_id": record.contract.tool_id,
                "tenant_id": record.contract.attribution.tenant_id,
                "outcome": record.outcome.value,
                "actual_cost": record.actual_cost,
                "output_valid": record.output_valid,
                "detail": record.detail,
            }
        )
