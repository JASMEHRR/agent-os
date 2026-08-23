"""Agent OS kernel: universal Gateway mechanisms (21A §5.2).

No constitutional standing of its own — an implementation artifact every
Gateway builds on: Artifact Identity, Lifecycle State Machine, Boundary
Enforcement, Immutable Journal, Failure Classification, Panic Protocol
participation.
"""

from kernel.boundaries import (
    BoundaryEnforcementEngine,
    BoundaryType,
    BoundaryViolationError,
)
from kernel.failure import FailureCategory, FailureClassifier
from kernel.identity import ArtifactIdentity
from kernel.journal import ImmutableJournal, JournalTamperError
from kernel.lifecycle import InvalidTransitionError, LifecycleStateMachine
from kernel.panic import PanicProtocol

__all__ = [
    "ArtifactIdentity",
    "LifecycleStateMachine",
    "InvalidTransitionError",
    "BoundaryEnforcementEngine",
    "BoundaryType",
    "BoundaryViolationError",
    "ImmutableJournal",
    "JournalTamperError",
    "FailureClassifier",
    "FailureCategory",
    "PanicProtocol",
]
