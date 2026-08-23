"""Incident Classifier (21B §22.3, realizes 14.29).

Six categories with mandated responses. This taxonomy is *separate* from the
kernel's five-category failure taxonomy and both apply at once (21B §22.9):
the kernel classifies what broke, this classifies what it means for trust.

14.29.2 requires automatic incident response on threshold breach, so the
classifier also owns the counters those thresholds read.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from security_gateway.enums import IncidentCategory

#: The mandated response per category, verbatim from 14.29.1.
RESPONSE_BY_CATEGORY: Mapping[IncidentCategory, tuple[str, ...]] = {
    IncidentCategory.OPERATIONAL_ANOMALY: ("alert", "retry", "degrade"),
    IncidentCategory.AUTHENTICATION_BREACH: ("revoke_credentials", "suspend_principal", "alert_human"),
    IncidentCategory.AUTHORIZATION_VIOLATION: ("block_action", "log_violation", "alert_human"),
    IncidentCategory.ISOLATION_BREACH: ("block_access", "alert_human", "investigate_scope"),
    IncidentCategory.SECRET_EXPOSURE: ("revoke_secret", "rotate_credentials", "isolate_systems", "alert_human"),
    IncidentCategory.CONSTITUTIONAL_VIOLATION: (
        "immediate_suspension",
        "preserve_evidence",
        "escalate_category_1",
    ),
}

#: Categories that escalate to the human sovereign as a Category 1 incident (14.33.3).
CATEGORY_1 = frozenset({IncidentCategory.CONSTITUTIONAL_VIOLATION})

#: 14.29.2 automatic-response thresholds. [Engineering Decision] — 14 mandates
#: the triggers but publishes no figures; these are starting values to be
#: tuned against real traffic, not constitutional constants.
DEFAULT_THRESHOLDS: Mapping[str, int] = {
    "authentication_failures": 5,
    "authorization_denials": 10,
}


@dataclass(frozen=True)
class Incident:
    incident_id: str
    category: IncidentCategory
    principal_id: str
    tenant_id: str
    summary: str
    #: Preserved verbatim for forensics; never mutated after formation.
    evidence: Mapping[str, Any]
    raised_at: datetime
    responses: tuple[str, ...]

    @property
    def is_category_1(self) -> bool:
        return self.category in CATEGORY_1

    @property
    def requires_suspension(self) -> bool:
        return any(r in ("suspend_principal", "immediate_suspension") for r in self.responses)


@dataclass
class IncidentClassifier:
    """Classifies incidents, applies the mandated response set, and counts triggers."""

    thresholds: Mapping[str, int] = field(default_factory=lambda: dict(DEFAULT_THRESHOLDS))
    _incidents: list[Incident] = field(default_factory=list, init=False)
    _counters: dict[tuple[str, str], int] = field(default_factory=dict, init=False)

    def raise_incident(
        self,
        category: IncidentCategory,
        principal_id: str,
        tenant_id: str,
        summary: str,
        evidence: Mapping[str, Any] | None = None,
    ) -> Incident:
        incident = Incident(
            incident_id=f"inc-{len(self._incidents) + 1:06d}",
            category=category,
            principal_id=principal_id,
            tenant_id=tenant_id,
            summary=summary,
            evidence=dict(evidence or {}),
            raised_at=datetime.now(UTC),
            responses=RESPONSE_BY_CATEGORY[category],
        )
        self._incidents.append(incident)
        return incident

    def count(self, counter: str, principal_id: str) -> int:
        """Increments a threshold counter and returns its new value."""
        key = (counter, principal_id)
        self._counters[key] = self._counters.get(key, 0) + 1
        return self._counters[key]

    def reset(self, counter: str, principal_id: str) -> None:
        self._counters.pop((counter, principal_id), None)

    def threshold_breached(self, counter: str, principal_id: str) -> bool:
        """14.29.2 — automatic response triggers once a counter passes its threshold."""
        limit = self.thresholds.get(counter)
        if limit is None:
            return False
        return self._counters.get((counter, principal_id), 0) >= limit

    @property
    def incidents(self) -> tuple[Incident, ...]:
        return tuple(self._incidents)

    def for_principal(self, principal_id: str) -> list[Incident]:
        return [i for i in self._incidents if i.principal_id == principal_id]
