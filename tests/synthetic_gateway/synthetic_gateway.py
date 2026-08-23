"""The Synthetic Gateway (Stage S0 exit criterion, Build Spec §12/§21_PLAN §4.1).

A minimal Gateway built purely on kernel + core + persistence, exercising
every universal Gateway mechanism, to prove the Layer 0 substrate is sound
before any real Gateway (security_gateway, Stage S1) is built on it. This is
not a deployable module — it exists only as a conformance fixture.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from kernel.boundaries import BoundaryContext, BoundaryEnforcementEngine, RequestContext
from kernel.failure import Classification, FailureCategory, FailureClassifier
from kernel.identity import ArtifactIdentity
from kernel.journal import ImmutableJournal
from kernel.lifecycle import LifecycleStateMachine
from kernel.panic import PanicProtocol
from persistence.in_memory import InMemoryRepository

SYNTHETIC_TRANSITIONS = {
    "created": {"active"},
    "active": {"halted"},
    "halted": set(),
}


class SyntheticGateway:
    def __init__(self) -> None:
        self.journal = ImmutableJournal()
        self.boundary_engine = BoundaryEnforcementEngine()
        self.failure_classifier = FailureClassifier()
        self.panic = PanicProtocol()
        self.repository: InMemoryRepository[ArtifactIdentity] = InMemoryRepository()
        self.lifecycle = LifecycleStateMachine(transitions=SYNTHETIC_TRANSITIONS, state="created")
        self.panic.register(self._on_panic)

    def _on_panic(self) -> None:
        self.lifecycle.transition("halted") if self.lifecycle.can_transition("halted") else None

    def admit(self, identity: ArtifactIdentity, ctx: BoundaryContext, req: RequestContext) -> None:
        self.boundary_engine.enforce(ctx, req)
        self.repository.save(identity.artifact_id, identity)
        self.lifecycle.transition("active")
        self.journal.append({"event": "admitted", "artifact_id": identity.artifact_id})

    def classify_failure(self, failure: Exception, rule: Callable[[Exception], FailureCategory]) -> Classification:
        classification = self.failure_classifier.classify(failure, rule)
        self.journal.append({"event": "failure_classified", "category": classification.category.value})
        return classification


def synthetic_boundary_context(
    tenant_id: str = "synthetic-tenant",
    scope: set[str] | None = None,
    authority_level: int = 3,
    confidence: float = 0.9,
    budget_remaining: float = 100.0,
    now: datetime | None = None,
) -> BoundaryContext:
    return BoundaryContext(
        tenant_id=tenant_id,
        scope=scope if scope is not None else {"read", "write"},
        authority_level=authority_level,
        confidence=confidence,
        budget_remaining=budget_remaining,
        now=now if now is not None else datetime.now(UTC),
    )


def synthetic_request_context(
    tenant_id: str = "synthetic-tenant",
    required_scope: set[str] | None = None,
    required_authority_level: int = 1,
    min_confidence: float = 0.5,
    cost: float = 1.0,
    not_before: datetime | None = None,
    not_after: datetime | None = None,
) -> RequestContext:
    return RequestContext(
        tenant_id=tenant_id,
        required_scope=required_scope if required_scope is not None else {"read"},
        required_authority_level=required_authority_level,
        min_confidence=min_confidence,
        cost=cost,
        not_before=not_before,
        not_after=not_after,
    )
