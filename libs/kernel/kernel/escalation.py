"""Category 1 Incident escalation (21A §5.2 item 10).

The tenth universal Gateway mechanism. A Category 1 incident is the system's
loudest signal: 14.33.3 fixes the response as immediate blocking, principal
suspension, evidence preservation, human sovereign alert, and escalation, with
"no appeal possible at the agent level".

Factored here because every Gateway raises them and all of them must behave
identically. Three properties are structural:

**Evidence is preserved at the moment of raising.** The incident copies its
evidence rather than referencing mutable state, so what the escalation carries
is what was true when it fired, not what the system looks like once the
response has run.

**There is no acknowledgement path for a machine.** `acknowledge` requires a
human principal. An agent cannot mark its own Category 1 incident handled,
which is 14.33.3's "no appeal at the agent level" expressed in the type
system rather than in a runbook.

**Raising never fails silently.** If no sink is attached the incident is
retained and counted, and `unacknowledged` reports it. An escalation that
vanished because nobody was listening would be the worst possible failure of
this mechanism.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any


class EscalationTrigger(StrEnum):
    """Why a Category 1 incident was raised.

    These are the constitutional triggers named across the documents: silent
    failure (08 §29, 14.28.1), non-violable rule violation (14.33.3),
    self-approval or authority bypass (14.17.5), journal tampering (09/10/11
    immutability clauses), and total loss of oversight visibility (16.17).
    """

    NON_VIOLABLE_RULE_VIOLATION = "non_violable_rule_violation"
    SILENT_FAILURE = "silent_failure"
    AUTHORITY_BYPASS = "authority_bypass"
    JOURNAL_TAMPERING = "journal_tampering"
    OVERSIGHT_LOSS = "oversight_loss"
    ISOLATION_BREACH = "isolation_breach"


@dataclass(frozen=True)
class Category1Incident:
    """An incident requiring the human sovereign's attention, with its evidence frozen."""

    incident_id: str
    trigger: EscalationTrigger
    subsystem: str
    principal_id: str
    tenant_id: str
    summary: str
    evidence: Mapping[str, Any]
    raised_at: datetime
    acknowledged_at: datetime | None = None
    acknowledged_by: str | None = None

    @property
    def is_acknowledged(self) -> bool:
        return self.acknowledged_at is not None

    #: 14.33.3 — the fixed response set. Not configurable per incident.
    RESPONSES = (
        "block_immediately",
        "suspend_principal",
        "preserve_evidence",
        "alert_human_sovereign",
        "escalate_category_1",
    )


class NoAppealError(Exception):
    """A non-human attempted to acknowledge a Category 1 incident (14.33.3)."""


@dataclass
class EscalationChannel:
    """The path from any Gateway to the human sovereign.

    `sink` is the out-of-band alert path — the Human Interface once Stage S8
    exists, and whatever alerting the deployment has before then. It is
    optional for the same reason `SignalEmitter`'s is: subsystems are built
    before the Human Interface, and an escalation raised in the meantime must
    still be retained rather than lost.
    """

    subsystem: str
    #: Answers "is this principal a Human" — acknowledgement requires one.
    is_human: Callable[[str], bool]
    sink: Callable[[Category1Incident], None] | None = None
    now: Callable[[], datetime] = field(default=lambda: datetime.now(UTC))
    _incidents: dict[str, Category1Incident] = field(default_factory=dict, init=False)
    _seq: int = field(default=0, init=False)
    _sink_failures: int = field(default=0, init=False)

    def raise_incident(
        self,
        trigger: EscalationTrigger,
        principal_id: str,
        tenant_id: str,
        summary: str,
        evidence: Mapping[str, Any] | None = None,
    ) -> Category1Incident:
        """Raises a Category 1 incident. Retained whether or not a sink exists."""
        self._seq += 1
        incident = Category1Incident(
            incident_id=f"cat1-{self.subsystem}-{self._seq:06d}",
            trigger=trigger,
            subsystem=self.subsystem,
            principal_id=principal_id,
            tenant_id=tenant_id,
            summary=summary,
            # Copied, not referenced: the evidence is frozen as it was when
            # the incident fired, before any response mutates the system.
            evidence=dict(evidence or {}),
            raised_at=self.now(),
        )
        self._incidents[incident.incident_id] = incident
        if self.sink is not None:
            try:
                self.sink(incident)
            except Exception:
                # A broken alert path must not swallow the incident; it is
                # already retained, and the failure is itself counted.
                self._sink_failures += 1
        return incident

    def acknowledge(self, incident_id: str, acknowledged_by: str) -> Category1Incident:
        """Marks an incident seen by a human. No agent may do this (14.33.3)."""
        incident = self._incidents.get(incident_id)
        if incident is None:
            raise KeyError(f"Category 1 incident '{incident_id}' does not exist")
        if not self.is_human(acknowledged_by):
            raise NoAppealError(
                f"'{acknowledged_by}' is not a Human principal; no appeal is possible at the agent level (14.33.3)"
            )
        acknowledged = Category1Incident(
            incident_id=incident.incident_id,
            trigger=incident.trigger,
            subsystem=incident.subsystem,
            principal_id=incident.principal_id,
            tenant_id=incident.tenant_id,
            summary=incident.summary,
            evidence=incident.evidence,
            raised_at=incident.raised_at,
            acknowledged_at=self.now(),
            acknowledged_by=acknowledged_by,
        )
        self._incidents[incident_id] = acknowledged
        return acknowledged

    def unacknowledged(self) -> list[Category1Incident]:
        """Incidents nobody has looked at. Non-empty is itself a problem."""
        return [i for i in self._incidents.values() if not i.is_acknowledged]

    def incidents(self) -> list[Category1Incident]:
        return list(self._incidents.values())

    @property
    def raised(self) -> int:
        return self._seq

    @property
    def sink_failures(self) -> int:
        return self._sink_failures
