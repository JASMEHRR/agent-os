"""The Panic Protocol, end to end (05.18.4, 13.33.4, 16.25.4, 17.31.4).

`05.18.4`: "A single command halts all autonomous activity, pauses in-flight
workflows, and requires human intervention to resume. The panic protocol is
always available and tested monthly."

`17.31.4` fixes the bound: **"Panic completion must occur within 5 seconds."**

`kernel.panic` implements the participation hook every Gateway registers
against. This module is the other end: the human-facing switch that invokes
it, holds the halted state, and refuses to let anything but a human lift it.

Four properties are structural rather than documented:

**Always available.** The switch takes no lock, needs no quorum, and consults
no policy. A panic switch that could itself be unavailable is not a panic
switch, so it is the one operation in the system with no authorization check
beyond "is this a human".

**The bound is enforced, not hoped for.** `invoke` measures its own elapsed
time and raises `PanicBoundExceededError` if a participant made it miss five
seconds. Recording the breach is the point: a panic that silently took nine
seconds is a constitutional violation nobody would otherwise learn about.

**A slow or failing participant cannot prevent the halt.** Each participant is
called defensively and its failure recorded; the halt proceeds. A subsystem
that could veto panic by raising would be a subsystem that could veto human
sovereignty.

**Resumption is human-only.** There is no timeout, no auto-resume, and no
service path into `resume`. "Requires human intervention to resume" is the
whole clause, and a resume-on-timer would negate it entirely.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from core.exceptions import AgentOSError
from human_interface.approvals import NotHuman
from kernel.escalation import EscalationTrigger
from kernel.journal import ImmutableJournal
from kernel.panic import PANIC_BOUND_SECONDS, PanicBoundExceededError

#: [Engineering Decision] 05.18.4 requires the protocol be "tested monthly" and
#: names no mechanism. `days_since_drill` reports it so a lapsed drill is
#: visible in health rather than discovered during a real panic.
DRILL_INTERVAL_DAYS = 30


@dataclass
class Participant:
    """One subsystem's halt hook.

    `halt` must be idempotent and fast. `disclose` returns what 16.25.4
    requires the subsystem to surface during panic: its active anomalies,
    health degradations and in-flight decisions.
    """

    name: str
    halt: Callable[[], None]
    disclose: Callable[[], Mapping[str, Any]] | None = None


@dataclass(frozen=True)
class PanicReport:
    """What one invocation did, including anything that went wrong."""

    invoked_by: str
    invoked_at: datetime
    reason: str
    elapsed_seconds: float
    halted: tuple[str, ...]
    #: Participants whose halt hook raised. The halt still completed.
    failed: tuple[tuple[str, str], ...]
    disclosure: Mapping[str, Any]
    within_bound: bool
    digests_flushed: int


@dataclass
class PanicSwitch:
    """The single command of 05.18.4."""

    is_human: Callable[[str], bool]
    #: Called when the bound is missed, so the breach reaches the sovereign as
    #: a Category 1 incident rather than only a log line.
    escalate: Callable[[EscalationTrigger, str], None] = field(default=lambda trigger, detail: None)
    #: Flushes queued routine digests: 16.25.4 prioritizes completeness over
    #: cognitive load during panic.
    flush_digests: Callable[[], int] = field(default=lambda: 0)
    now: Callable[[], datetime] = field(default=lambda: datetime.now(UTC))
    #: Monotonic clock, injected so the timed test can drive it.
    monotonic: Callable[[], float] = field(default=time.monotonic)

    def __post_init__(self) -> None:
        self._participants: list[Participant] = []
        self._halted = False
        self._reports: list[PanicReport] = []
        self._last_drill_at: datetime | None = None
        self.journal = ImmutableJournal()

    # -------------------------------------------------------- Participation

    def register(self, participant: Participant) -> Participant:
        """Every Gateway registers here (21A §5.2 item 8)."""
        if any(p.name == participant.name for p in self._participants):
            raise AgentOSError(f"'{participant.name}' is already a panic participant")
        self._participants.append(participant)
        return participant

    @property
    def participants(self) -> tuple[str, ...]:
        return tuple(p.name for p in self._participants)

    @property
    def halted(self) -> bool:
        return self._halted

    # ---------------------------------------------------------------- Panic

    def invoke(self, principal_id: str, reason: str) -> PanicReport:
        """Halt everything. Class D, human-only, bounded at five seconds."""
        if not self.is_human(principal_id):
            raise NotHuman(
                f"'{principal_id}' is not a human principal; the Panic Protocol is a sovereign act "
                "and no machine may invoke it (05.18.4)"
            )
        started = self.monotonic()
        halted: list[str] = []
        failed: list[tuple[str, str]] = []
        disclosure: dict[str, Any] = {}

        for participant in self._participants:
            try:
                participant.halt()
                halted.append(participant.name)
            except Exception as failure:
                # A subsystem that could veto panic by raising would be a
                # subsystem that could veto human sovereignty. Record and move on.
                failed.append((participant.name, str(failure)))

        for participant in self._participants:
            if participant.disclose is None:
                continue
            try:
                disclosure[participant.name] = dict(participant.disclose())
            except Exception as failure:
                disclosure[participant.name] = {"disclosure_failed": str(failure)}

        flushed = 0
        try:
            flushed = self.flush_digests()
        except Exception as failure:  # pragma: no cover - defensive
            disclosure["digests"] = {"flush_failed": str(failure)}

        elapsed = self.monotonic() - started
        within_bound = elapsed <= PANIC_BOUND_SECONDS
        self._halted = True

        report = PanicReport(
            invoked_by=principal_id,
            invoked_at=self.now(),
            reason=reason,
            elapsed_seconds=round(elapsed, 6),
            halted=tuple(halted),
            failed=tuple(failed),
            disclosure=disclosure,
            within_bound=within_bound,
            digests_flushed=flushed,
        )
        self._reports.append(report)
        self.journal.append(
            {
                "kind": "panic",
                "action": "invoked",
                "by": principal_id,
                "reason": reason,
                "elapsed_seconds": report.elapsed_seconds,
                "halted": list(halted),
                "failed": [name for name, _ in failed],
                "within_bound": within_bound,
            }
        )
        if failed:
            self.escalate(
                EscalationTrigger.SILENT_FAILURE,
                f"panic halt hooks failed for {[name for name, _ in failed]}",
            )
        if not within_bound:
            self.escalate(
                EscalationTrigger.NON_VIOLABLE_RULE_VIOLATION,
                f"panic completion took {elapsed:.2f}s, exceeding the {PANIC_BOUND_SECONDS}s bound (17.31.4)",
            )
            raise PanicBoundExceededError(
                f"panic halt took {elapsed:.2f}s, exceeds the {PANIC_BOUND_SECONDS}s bound; "
                "the report is recorded and the system is halted"
            )
        return report

    def resume(self, principal_id: str, note: str = "") -> None:
        """Human intervention, and nothing else, lifts a panic (05.18.4)."""
        if not self.is_human(principal_id):
            raise NotHuman(
                f"'{principal_id}' is not a human principal; only human intervention resumes after panic (05.18.4)"
            )
        if not self._halted:
            raise AgentOSError("the system is not halted")
        self._halted = False
        self.journal.append({"kind": "panic", "action": "resumed", "by": principal_id, "note": note})

    # ---------------------------------------------------------------- Drill

    def drill(self, principal_id: str) -> PanicReport:
        """05.18.4's monthly test, run against the real hooks and then resumed."""
        report = self.invoke(principal_id, reason="scheduled drill (05.18.4)")
        self._last_drill_at = report.invoked_at
        self.resume(principal_id, note="drill complete")
        self.journal.append({"kind": "panic", "action": "drill", "by": principal_id})
        return report

    def days_since_drill(self) -> float | None:
        if self._last_drill_at is None:
            return None
        return round((self.now() - self._last_drill_at).total_seconds() / 86400, 4)

    # --------------------------------------------------------------- Health

    def health(self) -> Mapping[str, Any]:
        since = self.days_since_drill()
        return {
            "halted": self._halted,
            "participants": len(self._participants),
            "invocations": len(self._reports),
            "bound_seconds": PANIC_BOUND_SECONDS,
            "slowest_seconds": max((r.elapsed_seconds for r in self._reports), default=0.0),
            "bound_breaches": len([r for r in self._reports if not r.within_bound]),
            "days_since_drill": since,
            "drill_overdue": since is None or since > DRILL_INTERVAL_DAYS,
            "journal_entries": len(self.journal),
            "journal_intact": self.journal.verify_chain(),
        }

    def reports(self) -> Sequence[PanicReport]:
        return tuple(self._reports)
