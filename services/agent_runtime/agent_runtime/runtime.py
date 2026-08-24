"""Agent Runtime — Identity Plane plus Execution Plane (21B §13).

| 21B §13.5 interface | Method                |
|---------------------|-----------------------|
| Activity Execution  | `execute`             |
| Agent Discovery     | `discover`            |
| Agent Registration  | `register`            |
| Lifecycle Command   | `command`             |
| Agent Health Query  | `health_of`           |

**The Runtime does not schedule.** `02.3.2`: "The Workflow Engine owns
scheduling; the Runtime owns execution." A test asserts no `schedule`/`enqueue`
method has appeared here.

**The worker holds nothing.** 21B §13.4: on receiving an activity a worker
acquires identity, hydrates state, assembles context, renders, infers,
dispatches tools, validates output, emits result, and returns to the pool
holding nothing. Every step crossing a module boundary passes through the
owning Gateway — the worker holds no credential, contacts no provider, and
touches no substrate.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

from agent_runtime.identity import (
    AGENT_TRANSITIONS,
    HEARTBEAT_CADENCE,
    SCHEMA_VIOLATION_SUSPENSION_THRESHOLD,
    AgentManifest,
    AgentRecord,
    AgentState,
    DriftMonitor,
    ManifestLoader,
    ReputationEngine,
)
from core.exceptions import AgentOSError, NotFoundError
from kernel.journal import ImmutableJournal
from kernel.lifecycle import LifecycleStateMachine
from kernel.signals import SignalEmitter, SignalType


class AuthorityViolation(AgentOSError):
    """An agent acted outside the intersection of its six boundaries (06.9.6)."""


class SeparationOfDutiesViolation(AgentOSError):
    """06 rules 16 and 17 — an agent may not review its own output."""


class RuntimeAuthorizer(Protocol):
    """Authentication and security context (21B §13.6)."""

    def principal_of(self, token: str) -> tuple[str, str]: ...

    def is_human(self, principal_id: str) -> bool: ...


class MemorySource(Protocol):
    """State hydration within declared memory scope (09.6.1, 06.5.3)."""

    def hydrate(self, token: str, tenant_id: str, scope: frozenset[str]) -> Sequence[Mapping[str, Any]]: ...


class InferenceSource(Protocol):
    """All inference goes through the LLM Router (02.3.8, 03 rule 11)."""

    def infer(
        self, template: str, slots: dict[str, str], tenant_id: str, principal_id: str, max_cost: float
    ) -> tuple[dict[str, Any], float, bool]: ...


class ToolSource(Protocol):
    """All tool invocation goes through the Tool Gateway (12 rule 11)."""

    def invoke(
        self,
        token: str,
        tool_id: str,
        decision_id: str,
        parameters: dict[str, Any],
        cost_ceiling: float,
        idempotency_key: str,
    ) -> tuple[bool, dict[str, Any] | None, float]: ...


@dataclass(frozen=True)
class ActivityRequest:
    """One activity dispatched by the Workflow Engine (21B §13.5)."""

    activity_id: str
    workflow_id: str
    agent_id: str
    tenant_id: str
    #: 12.17's idempotency key, carried down from the workflow so a redispatch
    #: is recognisable as the same logical work.
    idempotency_key: str
    inputs: dict[str, str]
    decision_id: str
    cost_ceiling: float
    tool_calls: tuple[tuple[str, dict[str, Any]], ...] = ()
    #: Set when this activity reviews another agent's output. The Runtime
    #: refuses to assign it to that agent (06 rules 16, 17).
    reviews_output_of: str | None = None


@dataclass(frozen=True)
class Heartbeat:
    """Progress report during execution (02.4.8)."""

    activity_id: str
    agent_id: str
    at: datetime
    stage: str


@dataclass(frozen=True)
class ActivityOutcome:
    """The structured result the Workflow Engine receives back."""

    activity_id: str
    agent_id: str
    succeeded: bool
    output: dict[str, Any] | None
    cost: float
    tool_calls: int
    duration_seconds: float
    heartbeats: tuple[Heartbeat, ...]
    detail: str
    output_valid: bool
    degraded: bool = False


@dataclass
class AgentRuntime:
    """Layer 5. Holds durable identity while executing the ephemeral process."""

    authorizer: RuntimeAuthorizer
    memory: MemorySource
    inference: InferenceSource
    tools: ToolSource
    signals: SignalEmitter
    now: Callable[[], datetime] = field(default=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        self.loader = ManifestLoader()
        self.reputation = ReputationEngine(now=self.now)
        self.drift = DriftMonitor()
        self.journal = ImmutableJournal()
        self._agents: dict[str, AgentRecord] = {}
        self._outcomes: dict[str, ActivityOutcome] = {}
        self._workers_in_use = 0
        self._peak_workers = 0

    # ------------------------------------------------- Identity Plane

    def register(self, token: str, manifest: AgentManifest) -> AgentRecord:
        """**Agent Registration** (21B §13.5). Consumers: Human Interface, Evolution."""
        principal_id, tenant_id = self.authorizer.principal_of(token)
        if tenant_id != manifest.tenant_id:
            raise AgentOSError(f"'{principal_id}' may not register into tenant '{manifest.tenant_id}'")
        if manifest.agent_id in self._agents:
            raise AgentOSError(f"agent '{manifest.agent_id}' is already registered")
        if manifest.predecessor_agent_id is not None and manifest.predecessor_agent_id not in self._agents:
            raise AgentOSError(f"predecessor '{manifest.predecessor_agent_id}' is not registered; lineage must resolve")
        self.loader.validate(manifest)
        record = AgentRecord(manifest=manifest, state=AgentState.REGISTERED)
        self._agents[manifest.agent_id] = record
        self._journal(record, "registered", by=principal_id, specialty=manifest.specialty)
        return record

    def command(self, token: str, agent_id: str, target: AgentState, reason: str = "") -> AgentRecord:
        """**Lifecycle Command** (21B §13.5). Consumers: Human Interface, Governance."""
        principal_id, _ = self.authorizer.principal_of(token)
        record = self.get(agent_id)
        machine = LifecycleStateMachine(transitions=dict(AGENT_TRANSITIONS), state=record.state)
        machine.transition(target)
        record.state = target
        if target == AgentState.SUSPENDED:
            record.suspended_reason = reason
        self._journal(record, target.value, by=principal_id, reason=reason)
        return record

    def discover(self, token: str, capability: str | None = None, min_reputation: float = 0.0) -> list[AgentRecord]:
        """**Agent Discovery** (21B §13.5, 06.7.2). Consumer: Workflow Engine.

        Only assignable agents are returned. Registration is not availability,
        exactly as tool registration is not authorization.
        """
        _principal_id, tenant_id = self.authorizer.principal_of(token)
        return [
            record
            for record in self._agents.values()
            if record.manifest.tenant_id == tenant_id
            and record.is_assignable
            and record.reputation >= min_reputation
            and (capability is None or record.manifest.boundaries.permits_capability(capability))
        ]

    def get(self, agent_id: str) -> AgentRecord:
        record = self._agents.get(agent_id)
        if record is None:
            raise NotFoundError(f"agent '{agent_id}' is not registered")
        return record

    def health_of(self, agent_id: str) -> Mapping[str, Any]:
        """**Agent Health Query** (21B §13.5). Consumers: Observability, Workflow."""
        record = self.get(agent_id)
        return {
            "agent_id": agent_id,
            "state": record.state.value,
            "reputation": record.reputation,
            "success_rate": record.success_rate,
            "executions": record.executions,
            "schema_violations": record.schema_violations,
            "assignable": record.is_assignable,
            "suspended_reason": record.suspended_reason,
        }

    # ------------------------------------------------ Execution Plane

    def execute(self, token: str, request: ActivityRequest) -> ActivityOutcome:
        """**Activity Execution** (21B §13.5). Consumer: Workflow Engine.

        Runs the sequence of 21B §13.4 in order. The worker returns holding
        nothing: every durable consequence is written to the Identity Plane or
        emitted, never retained in the worker.
        """
        principal_id, tenant_id = self.authorizer.principal_of(token)
        record = self.get(request.agent_id)
        started = self.now()
        heartbeats: list[Heartbeat] = []

        def beat(stage: str) -> None:
            heartbeats.append(
                Heartbeat(activity_id=request.activity_id, agent_id=record.agent_id, at=self.now(), stage=stage)
            )

        # Separation of duties, enforced at assignment (21B §13.10).
        if request.reviews_output_of == request.agent_id:
            raise SeparationOfDutiesViolation(
                f"agent '{request.agent_id}' may not review its own output (06 rules 16, 17)"
            )
        if record.manifest.tenant_id != tenant_id:
            raise AuthorityViolation(f"agent '{request.agent_id}' belongs to another tenant")
        if not record.is_assignable:
            raise AgentOSError(f"agent '{request.agent_id}' is {record.state.value}, not assignable")
        if request.cost_ceiling > record.manifest.boundaries.cost_budget:
            raise AuthorityViolation(
                f"activity ceiling {request.cost_ceiling} exceeds the agent's declared budget "
                f"{record.manifest.boundaries.cost_budget} (06.9.6)"
            )
        for tool_id, _params in request.tool_calls:
            if not record.manifest.boundaries.permits_tool(tool_id):
                raise AuthorityViolation(
                    f"tool '{tool_id}' is outside agent '{request.agent_id}''s registered inventory (12.32.1)"
                )

        self._enter_execution(record)
        self._workers_in_use += 1
        self._peak_workers = max(self._peak_workers, self._workers_in_use)
        cost = 0.0
        tool_call_count = 0
        output: dict[str, Any] | None = None
        output_valid = False
        degraded = False
        detail = ""

        try:
            beat("hydrating")
            context = self.memory.hydrate(token, tenant_id, record.manifest.boundaries.memory_scope)
            if not context:
                # 21B §13.9 — degraded context assembly carries an explicit flag.
                degraded = True

            beat("assembling")
            slots = self._assemble(record, request, context)

            beat("inferring")
            inferred, inference_cost, grounded = self.inference.infer(
                record.manifest.prompt_template,
                slots,
                tenant_id,
                principal_id,
                max_cost=request.cost_ceiling,
            )
            cost += inference_cost
            if not grounded:
                degraded = True

            beat("dispatching_tools")
            for tool_id, parameters in request.tool_calls:
                succeeded, _tool_output, tool_cost = self.tools.invoke(
                    token,
                    tool_id,
                    request.decision_id,
                    parameters,
                    cost_ceiling=max(0.0, request.cost_ceiling - cost),
                    idempotency_key=f"{request.idempotency_key}:{tool_id}",
                )
                tool_call_count += 1
                cost += tool_cost
                if not succeeded:
                    raise AgentOSError(f"tool '{tool_id}' failed during activity '{request.activity_id}'")

            beat("validating")
            errors = self._validate_output(record, inferred)
            if errors:
                record.schema_violations += 1
                detail = "; ".join(errors)
                if record.schema_violations >= SCHEMA_VIOLATION_SUSPENSION_THRESHOLD:
                    # 06.9.4 — automatic suspension at the threshold.
                    record.state = AgentState.SUSPENDED
                    record.suspended_reason = "repeated output schema violation"
                    self._journal(record, "suspended", reason=record.suspended_reason)
                raise AgentOSError(f"output contract violation: {detail}")

            output, output_valid = inferred, True
            detail = "completed within declared boundaries"
            succeeded = True

        except Exception as failure:
            succeeded = False
            detail = detail or str(failure)
        finally:
            self._workers_in_use -= 1
            # The agent returns to Idle whatever happened, unless a threshold
            # suspended it. The worker itself retains nothing.
            if record.state == AgentState.EXECUTING:
                record.state = AgentState.IDLE

        duration = (self.now() - started).total_seconds()
        record.executions += 1
        if not succeeded:
            record.failures += 1
        record.last_executed_at = self.now()
        record.reputation = self.reputation.recompute(record)
        self.drift.update_baseline(record, tool_call_count, duration)

        outcome = ActivityOutcome(
            activity_id=request.activity_id,
            agent_id=record.agent_id,
            succeeded=succeeded,
            output=output if output_valid else None,
            cost=round(cost, 6),
            tool_calls=tool_call_count,
            duration_seconds=duration,
            heartbeats=tuple(heartbeats),
            detail=detail,
            output_valid=output_valid,
            degraded=degraded,
        )
        self._outcomes[request.activity_id] = outcome
        self._journal(
            record,
            "executed",
            activity_id=request.activity_id,
            workflow_id=request.workflow_id,
            succeeded=succeeded,
            cost=outcome.cost,
            tool_calls=tool_call_count,
            degraded=degraded,
        )
        self.signals.emit(
            SignalType.METRIC,
            "agent.execution.cost",
            tenant_id,
            value=outcome.cost,
            agent_id=record.agent_id,
            succeeded=succeeded,
            tool_calls=tool_call_count,
        )
        return outcome

    def _enter_execution(self, record: AgentRecord) -> None:
        machine = LifecycleStateMachine(transitions=dict(AGENT_TRANSITIONS), state=record.state)
        machine.transition(AgentState.EXECUTING)
        record.state = AgentState.EXECUTING

    def _assemble(
        self, record: AgentRecord, request: ActivityRequest, context: Sequence[Mapping[str, Any]]
    ) -> dict[str, str]:
        """Context Assembler: composes within `max_context_tokens` (07.10.4).

        Truncates rather than overflowing. An agent that silently exceeded its
        declared budget would make the budget meaningless.
        """
        assembled = dict(request.inputs)
        budget = record.manifest.max_context_tokens
        lines: list[str] = []
        used = 0
        for item in context:
            rendered = str(item)
            cost = max(1, (len(rendered) + 3) // 4)
            if used + cost > budget:
                break
            lines.append(rendered)
            used += cost
        assembled["context"] = "\n".join(lines)
        return assembled

    def _validate_output(self, record: AgentRecord, output: dict[str, Any]) -> list[str]:
        """Output Validator (21B §13.3). No unvalidated output propagates."""
        errors: list[str] = []
        for name, expected in record.manifest.output_contract.items():
            if name not in output:
                errors.append(f"missing required field '{name}'")
            elif not isinstance(output[name], expected):
                errors.append(f"field '{name}' expected {expected.__name__}, got {type(output[name]).__name__}")
        return errors

    # ------------------------------------------------------------- Drift

    def assess_drift(self, agent_id: str) -> Any:
        record = self.get(agent_id)
        outcome = next((o for o in reversed(list(self._outcomes.values())) if o.agent_id == agent_id), None)
        tool_calls = outcome.tool_calls if outcome else 0
        latency = outcome.duration_seconds if outcome else 0.0
        reading = self.drift.assess(record, tool_calls, latency)
        if reading.drifted:
            self.signals.emit(
                SignalType.EVENT,
                "agent.drift.detected",
                record.manifest.tenant_id,
                agent_id=agent_id,
                detail=reading.detail,
            )
            self._journal(record, "drift_detected", detail=reading.detail)
        return reading

    def decay_reputation(self) -> list[AgentRecord]:
        decayed: list[AgentRecord] = []
        for record in self._agents.values():
            reduced = self.reputation.decay(record)
            if reduced != record.reputation:
                record.reputation = reduced
                decayed.append(record)
        return decayed

    # ------------------------------------------------------------ Health

    def health(self) -> Mapping[str, Any]:
        """Signals for the Agent Workforce Health composition of 16.18."""
        records = list(self._agents.values())
        outcomes = list(self._outcomes.values())
        by_state: dict[str, int] = {}
        for record in records:
            by_state[record.state.value] = by_state.get(record.state.value, 0) + 1
        return {
            "agents": len(records),
            "by_state": by_state,
            "task_success_rate": (
                round(sum(1 for o in outcomes if o.succeeded) / len(outcomes), 4) if outcomes else 0.0
            ),
            "schema_conformance": (
                round(sum(1 for o in outcomes if o.output_valid) / len(outcomes), 4) if outcomes else 0.0
            ),
            "mean_reputation": (round(sum(r.reputation for r in records) / len(records), 4) if records else 0.0),
            "total_cost": round(sum(o.cost for o in outcomes), 6),
            "tool_invocations": sum(o.tool_calls for o in outcomes),
            "degraded_executions": sum(1 for o in outcomes if o.degraded),
            "worker_pool": {"in_use": self._workers_in_use, "peak": self._peak_workers},
            "heartbeat_cadence_seconds": HEARTBEAT_CADENCE.total_seconds(),
            "journal_entries": len(self.journal),
            "journal_intact": self.journal.verify_chain(),
        }

    def outcome_for(self, activity_id: str) -> ActivityOutcome:
        outcome = self._outcomes.get(activity_id)
        if outcome is None:
            raise NotFoundError(f"no outcome for activity '{activity_id}'")
        return outcome

    def _journal(self, record: AgentRecord, action: str, **detail: Any) -> None:
        self.journal.append(
            {
                "kind": "agent",
                "action": action,
                "agent_id": record.agent_id,
                "tenant_id": record.manifest.tenant_id,
                "state": record.state.value,
                **detail,
            }
        )


def stall_threshold(manifest: AgentManifest) -> timedelta:
    """02.4.8 — stall detection at twice the activity timeout."""
    from agent_runtime.identity import STALL_MULTIPLIER

    return manifest.activity_timeout * STALL_MULTIPLIER
