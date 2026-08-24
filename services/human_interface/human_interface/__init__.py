"""Human Interface — the human plane's single surface (Build Spec Stage S8).

Consolidates the human-sovereignty requirements of 05.18, 11.18, 13.33, 16.25,
17.31, 18.35 and 19.36. Seven documents grant humans the same four rights:
approve, override, be informed, and halt. Implementing them once means there is
one place where sovereignty can be verified, rather than seven places where it
can quietly differ.

`05.18.1`: "Human operators are not users; they are sovereign delegates."
"""

from human_interface.approvals import (
    ApprovalRecord,
    ApprovalRegistry,
    ApprovalRequest,
    ApprovalState,
    Batch,
    NotHuman,
    Urgency,
)
from human_interface.digests import DEFAULT_CADENCE, Digest, DigestService, Notification, Severity
from human_interface.interface import HaltedError, HumanInterface
from human_interface.overrides import (
    STANDING_ORDER_TTL,
    Override,
    OverrideLedger,
    OverrideScope,
    StandingOrder,
    StandingOrderRegistry,
)
from human_interface.panic import (
    DRILL_INTERVAL_DAYS,
    PanicReport,
    PanicSwitch,
    Participant,
)

__all__ = [
    "HumanInterface",
    "HaltedError",
    "ApprovalRegistry",
    "ApprovalRequest",
    "ApprovalRecord",
    "ApprovalState",
    "Urgency",
    "Batch",
    "NotHuman",
    "OverrideLedger",
    "Override",
    "OverrideScope",
    "StandingOrderRegistry",
    "StandingOrder",
    "STANDING_ORDER_TTL",
    "DigestService",
    "Digest",
    "Notification",
    "Severity",
    "DEFAULT_CADENCE",
    "PanicSwitch",
    "PanicReport",
    "Participant",
    "DRILL_INTERVAL_DAYS",
]
