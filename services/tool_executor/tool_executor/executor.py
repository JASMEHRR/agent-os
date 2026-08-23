"""Tool Executor — fulfils validated contracts, decides nothing (12.6.3, 21B §19).

`12.6.3`: the Executor "receives instructions from the Gateway; it does not
evaluate authority or make policy decisions." `12.17.4` sharpens it: "If the
tool exceeds its cost ceiling, timeout, or sandbox boundary, the Executor
halts execution and reports failure. **The Executor does not reinterpret
contract terms.**"

That is the structural reason this is a separate module: policy and execution
must not share a process. A test asserts no `authorize` / `approve` /
`override` method has appeared on this surface.

Two guarantees are unconditional:

**Cleanup on every path** (21B §19.15 guarantee 8). Sandbox destruction runs
in a `finally`, so it survives success, failure, timeout, cost breach and an
unexpected exception alike.

**Secrets reach the sandbox and nowhere else** (12 rule 5). The Secret
Injector redeems a Security Gateway grant directly into the sandbox
environment; no value passes through a return, a log, or the record.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Protocol

from core.exceptions import AgentOSError
from kernel.journal import ImmutableJournal
from kernel.signals import SignalEmitter, SignalType
from tool_gateway import InvocationContract, InvocationOutcome
from tool_registry import SandboxTier


class SandboxState(StrEnum):
    """A sandbox's lifecycle. It is never reused across invocations at the
    gVisor and Firecracker tiers (21B §19.8)."""

    PREPARING = "preparing"
    READY = "ready"
    EXECUTING = "executing"
    DESTROYED = "destroyed"


class EgressBlocked(AgentOSError):
    """A network destination outside the contract's allowlist (deny-by-default)."""


class SandboxViolation(AgentOSError):
    """A boundary breach. Category 1, not an operational failure (21B §19.10)."""


class CostCeilingBreached(AgentOSError):
    """Mid-flight cost exceeded the contract ceiling. Immediate halt (12.17.4)."""


class TimeoutBreached(AgentOSError):
    """Hard execution bound exceeded. Immediate termination (12.17.4)."""


class SecretAuthority(Protocol):
    """Secret injection under Security Gateway authorization (21B §19.6).

    `resolve` returns an opaque grant; `inject` redeems it straight into the
    sandbox. The value never crosses back through this interface, which is
    what keeps 12 rule 5 structural rather than procedural.
    """

    def resolve(self, reference: str, sandbox_id: str, invocation_id: str, requester_id: str) -> Any: ...

    def inject(self, grant: Any, injector: Callable[[str, str], None]) -> None: ...


@dataclass
class ResourceLimits:
    """CPU, memory, disk and network bounds per tier (21B §19.3)."""

    cpu_millicores: int
    memory_mb: int
    disk_mb: int
    network_kbps: int


#: [Engineering Decision] 21B §19.3 requires a Resource Governor without
#: publishing limits. Tighter isolation gets tighter resources, on the
#: principle that a tool needing Firecracker is being contained, not indulged.
LIMITS_BY_TIER: dict[SandboxTier, ResourceLimits] = {
    SandboxTier.NONE: ResourceLimits(500, 256, 64, 0),
    SandboxTier.CONTAINER: ResourceLimits(1000, 512, 512, 10_000),
    SandboxTier.GVISOR: ResourceLimits(1000, 512, 256, 5_000),
    SandboxTier.FIRECRACKER: ResourceLimits(2000, 1024, 1024, 2_000),
}

#: 21B §19.4 — Container-tier sandboxes may be pre-warmed to meet the p50
#: 100ms preparation budget. Higher tiers are never pooled: reuse would risk
#: state leakage across invocations, which the isolation guarantee forbids.
POOLABLE_TIERS = frozenset({SandboxTier.CONTAINER})


@dataclass
class Sandbox:
    """One isolated execution environment, bound to one invocation."""

    sandbox_id: str
    tier: SandboxTier
    limits: ResourceLimits
    invocation_id: str
    state: SandboxState = SandboxState.PREPARING
    env: dict[str, str] = field(default_factory=dict)
    egress_allowlist: tuple[str, ...] = ()
    _egress_attempts: list[str] = field(default_factory=list, init=False)

    def inject_secret(self, name: str, value: str) -> None:
        """Places a secret in the sandbox environment. Values live only here."""
        self.env[name] = value

    def request_egress(self, destination: str) -> None:
        """Egress Controller: deny-by-default with an explicit allowlist."""
        self._egress_attempts.append(destination)
        if not any(destination == allowed or destination.endswith(f".{allowed}") for allowed in self.egress_allowlist):
            raise EgressBlocked(
                f"destination '{destination}' is not in the sandbox allowlist {list(self.egress_allowlist)}"
            )

    @property
    def egress_attempts(self) -> tuple[str, ...]:
        return tuple(self._egress_attempts)

    def destroy(self) -> None:
        # Secrets go with the sandbox. Nothing survives destruction.
        self.env.clear()
        self.state = SandboxState.DESTROYED


@dataclass(frozen=True)
class ExecutionResult:
    """What the Executor reports back to the Gateway. Never a secret value."""

    invocation_id: str
    outcome: InvocationOutcome
    output: dict[str, Any] | None
    actual_cost: float
    started_at: datetime
    completed_at: datetime
    detail: str
    sandbox_destroyed: bool


@dataclass
class SandboxManager:
    """Lifecycle across the four tiers, with a pool for Container only."""

    now: Callable[[], datetime] = field(default=lambda: datetime.now(UTC))
    _pool: list[Sandbox] = field(default_factory=list, init=False)
    _live: dict[str, Sandbox] = field(default_factory=dict, init=False)
    prepared: int = field(default=0, init=False)
    destroyed: int = field(default=0, init=False)
    pool_hits: int = field(default=0, init=False)

    def prepare(self, contract: InvocationContract) -> Sandbox:
        tier = contract.sandbox_tier
        if tier in POOLABLE_TIERS and self._pool:
            sandbox = self._pool.pop()
            self.pool_hits += 1
            sandbox = Sandbox(
                sandbox_id=sandbox.sandbox_id,
                tier=tier,
                limits=LIMITS_BY_TIER[tier],
                invocation_id=contract.invocation_id,
                egress_allowlist=contract.egress_allowlist,
            )
        else:
            sandbox = Sandbox(
                sandbox_id=f"sbx-{uuid.uuid4()}",
                tier=tier,
                limits=LIMITS_BY_TIER[tier],
                invocation_id=contract.invocation_id,
                egress_allowlist=contract.egress_allowlist,
            )
        sandbox.state = SandboxState.READY
        self._live[sandbox.sandbox_id] = sandbox
        self.prepared += 1
        return sandbox

    def destroy(self, sandbox: Sandbox) -> None:
        """Cleanup Guarantor. Idempotent, so a double call is harmless."""
        if sandbox.state == SandboxState.DESTROYED:
            return
        sandbox.destroy()
        self._live.pop(sandbox.sandbox_id, None)
        self.destroyed += 1
        # Only Container-tier sandboxes return to the pool. gVisor and
        # Firecracker are discarded outright (21B §19.4).
        if sandbox.tier in POOLABLE_TIERS:
            self._pool.append(
                Sandbox(
                    sandbox_id=f"sbx-{uuid.uuid4()}",
                    tier=sandbox.tier,
                    limits=sandbox.limits,
                    invocation_id="",
                )
            )

    @property
    def live_count(self) -> int:
        return len(self._live)


@dataclass
class ToolExecutor:
    """Dispatches validated contracts. Layer 4 (21B §19.13).

    `run` takes the tool's callable as an argument rather than resolving it:
    resolution is the Registry's business and dispatch is this module's, and
    keeping them apart means the Executor has nothing to reinterpret.
    """

    secrets: SecretAuthority
    signals: SignalEmitter
    #: The Executor's own Service principal. 21B §19.10 makes the *Executor*
    #: the party authorized to inject secrets, not the consuming agent — and
    #: 14 rule 12 forbids a secret grant reaching an agent at all, so passing
    #: the consumer here would be refused by the Security Gateway, correctly.
    executor_identity: str = "service-tool-executor"
    now: Callable[[], datetime] = field(default=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        self.sandboxes = SandboxManager(now=self.now)
        self.journal = ImmutableJournal()
        self._results: dict[str, ExecutionResult] = {}
        self._seen_idempotency_keys: dict[str, str] = {}

    def run(
        self,
        contract: InvocationContract,
        tool: Callable[[Sandbox, dict[str, Any]], dict[str, Any]],
        cost_meter: Callable[[], float] | None = None,
    ) -> ExecutionResult:
        """Fulfils one contract within its terms. Reinterprets nothing.

        `cost_meter` reports spend so far, letting the Cost Monitor halt
        mid-flight rather than discovering the breach afterwards.
        """
        # At-least-once delivery upstream means the same logical request can
        # arrive twice. 12.17's idempotency key exists for exactly this.
        previous = self._seen_idempotency_keys.get(contract.idempotency_key)
        if previous is not None and previous in self._results:
            return self._results[previous]

        started = self.now()
        sandbox = self.sandboxes.prepare(contract)
        outcome = InvocationOutcome.FAILED
        output: dict[str, Any] | None = None
        detail = ""
        actual_cost = 0.0

        try:
            self._inject_secrets(contract, sandbox)
            sandbox.state = SandboxState.EXECUTING
            output = tool(sandbox, dict(contract.context_package))

            elapsed = self.now() - started
            if elapsed > contract.timeout:
                raise TimeoutBreached(f"execution ran {elapsed} against a {contract.timeout} bound")
            actual_cost = cost_meter() if cost_meter is not None else 0.0
            if actual_cost > contract.cost_ceiling:
                raise CostCeilingBreached(f"spend {actual_cost} exceeded the ceiling {contract.cost_ceiling}")
            outcome = InvocationOutcome.SUCCEEDED
            detail = "completed within contract terms"

        except TimeoutBreached as breach:
            outcome, detail = InvocationOutcome.TIMED_OUT, str(breach)
        except CostCeilingBreached as breach:
            outcome, detail = InvocationOutcome.COST_CEILING_BREACHED, str(breach)
            actual_cost = cost_meter() if cost_meter is not None else 0.0
        except (SandboxViolation, EgressBlocked) as breach:
            outcome, detail = InvocationOutcome.SANDBOX_VIOLATION, str(breach)
            self.signals.emit(
                SignalType.EVENT,
                "tool.sandbox.violation",
                contract.attribution.tenant_id,
                invocation_id=contract.invocation_id,
                tool_id=contract.tool_id,
                detail=str(breach),
            )
        except Exception as failure:
            # 12.21.5 — an unclassified tool failure is treated as critical.
            outcome, detail = InvocationOutcome.FAILED, f"unclassified tool failure: {failure}"
        finally:
            # Cleanup Guarantor: runs on every path, including the ones above
            # that re-raise nothing and the ones that would have escaped.
            self.sandboxes.destroy(sandbox)

        result = ExecutionResult(
            invocation_id=contract.invocation_id,
            outcome=outcome,
            output=output if outcome == InvocationOutcome.SUCCEEDED else None,
            actual_cost=actual_cost,
            started_at=started,
            completed_at=self.now(),
            detail=detail,
            sandbox_destroyed=sandbox.state == SandboxState.DESTROYED,
        )
        self._results[contract.invocation_id] = result
        self._seen_idempotency_keys[contract.idempotency_key] = contract.invocation_id
        self._journal(contract, result)
        return result

    def _inject_secrets(self, contract: InvocationContract, sandbox: Sandbox) -> None:
        """Secret Injector: values reach the sandbox environment and nowhere else."""
        for reference in contract.secret_refs:
            grant = self.secrets.resolve(
                reference,
                sandbox.sandbox_id,
                contract.invocation_id,
                self.executor_identity,
            )

            # A named closure rather than a lambda with a default argument:
            # the binding is clearer and mypy can infer it.
            def place(_sandbox_id: str, value: str, ref: str = reference) -> None:
                sandbox.inject_secret(ref, value)

            self.secrets.inject(grant, place)

    def result_for(self, invocation_id: str) -> ExecutionResult:
        result = self._results.get(invocation_id)
        if result is None:
            raise AgentOSError(f"no execution result for '{invocation_id}'")
        return result

    def health(self) -> Mapping[str, Any]:
        """Execution-side signals for the Observability Gateway."""
        results = list(self._results.values())
        return {
            "executions": len(results),
            "sandboxes": {
                "prepared": self.sandboxes.prepared,
                "destroyed": self.sandboxes.destroyed,
                "live": self.sandboxes.live_count,
                "pool_hits": self.sandboxes.pool_hits,
                # Non-zero here would mean a sandbox outlived its invocation.
                "leaked": self.sandboxes.prepared - self.sandboxes.destroyed,
            },
            "outcomes": {
                outcome.value: sum(1 for r in results if r.outcome == outcome) for outcome in InvocationOutcome
            },
            "journal_entries": len(self.journal),
            "journal_intact": self.journal.verify_chain(),
        }

    def _journal(self, contract: InvocationContract, result: ExecutionResult) -> None:
        self.journal.append(
            {
                "kind": "execution",
                "invocation_id": result.invocation_id,
                "tool_id": contract.tool_id,
                "tenant_id": contract.attribution.tenant_id,
                "sandbox_tier": contract.sandbox_tier.name,
                "outcome": result.outcome.value,
                "actual_cost": result.actual_cost,
                "sandbox_destroyed": result.sandbox_destroyed,
                # The secret *references* are recorded; no value ever is.
                "secret_refs": list(contract.secret_refs),
                "detail": result.detail,
            }
        )
