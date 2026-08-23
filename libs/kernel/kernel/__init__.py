"""Agent OS kernel: universal Gateway mechanisms (21A §5.2).

No constitutional standing of its own — an implementation artifact every
Gateway builds on: Artifact Identity, Lifecycle State Machine, Boundary
Enforcement, Immutable Journal, Confidence/Authority Resolution, Failure
Classification, Signal Emission, Panic Protocol participation, Category 1
Incident escalation.
"""

from kernel.authority import (
    MIN_CONFIDENCE_BY_LEVEL,
    AuthorityLevel,
    AuthorityResolution,
    Outcome,
    RiskClass,
    derive_confidence,
    resolve,
)
from kernel.boundaries import (
    BoundaryEnforcementEngine,
    BoundaryType,
    BoundaryViolationError,
)
from kernel.escalation import (
    Category1Incident,
    EscalationChannel,
    EscalationTrigger,
    NoAppealError,
)
from kernel.failure import FailureCategory, FailureClassifier
from kernel.identity import ArtifactIdentity
from kernel.journal import ImmutableJournal, JournalTamperError
from kernel.lifecycle import InvalidTransitionError, LifecycleStateMachine
from kernel.panic import PanicProtocol
from kernel.signals import (
    ConsumerAuthority,
    Sensitivity,
    Signal,
    SignalEmitter,
    SignalType,
)

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
    "Signal",
    "SignalEmitter",
    "SignalType",
    "Sensitivity",
    "ConsumerAuthority",
    "AuthorityLevel",
    "AuthorityResolution",
    "RiskClass",
    "Outcome",
    "MIN_CONFIDENCE_BY_LEVEL",
    "resolve",
    "derive_confidence",
    "EscalationChannel",
    "Category1Incident",
    "EscalationTrigger",
    "NoAppealError",
]
