"""Admission Controller (21B §15.3, realizes 08.7.2, 08.16.1, 08.18).

Admission is the Bus's only strict inbound gate. A producer submits an event
with full identity and payload; the controller authenticates it against the
Trust Plane, validates the payload against its registered schema version,
validates that the producer's scope permits emitting that type in that tenant,
and rejects on any failure.

Two rules are absolute here. Unregistered event types are rejected outright
(08.16.1). Rejection is explicit and logged — "producers may not silently
swallow emission failure" (21B §15.4), so every rejection path raises.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Protocol

from core.events import Event
from core.exceptions import AgentOSError
from event_bus.envelope import DomainCategory, Provenance


class AdmissionRejected(AgentOSError):
    """Base for every admission failure. Carries the cause for rejection metrics."""

    def __init__(self, cause: str, detail: str):
        super().__init__(f"admission rejected ({cause}): {detail}")
        self.cause = cause
        self.detail = detail


class ProducerNotAuthenticated(AdmissionRejected):
    def __init__(self, detail: str):
        super().__init__("authentication", detail)


class ProducerNotAuthorized(AdmissionRejected):
    def __init__(self, detail: str):
        super().__init__("authorization", detail)


class SchemaRejected(AdmissionRejected):
    def __init__(self, detail: str):
        super().__init__("schema", detail)


class TenantRejected(AdmissionRejected):
    def __init__(self, detail: str):
        super().__init__("tenant", detail)


class TrustPlane(Protocol):
    """What the Bus needs from the Security Gateway (21B §15.6).

    A Protocol rather than a direct import so the Bus depends on the *shape*
    of producer authentication, not on the Gateway's internals. The concrete
    adapter lives in `security_adapter.py`.
    """

    def authenticate_producer(self, token: str) -> ProducerIdentity: ...

    def authorize_emission(self, token: str, event_type: str, tenant_id: str) -> bool: ...

    def authorize_subscription(self, token: str, patterns: tuple[str, ...], tenant_id: str) -> bool: ...


class SchemaSource(Protocol):
    """What the Bus needs from the Schema Registry (21B §15.6)."""

    def validate(self, event_type: str, payload: dict[str, object], version: str | None = None) -> None: ...


@dataclass(frozen=True)
class ProducerIdentity:
    """Publication identity assigned at admission (21B §15.3)."""

    principal_id: str
    tenant_id: str
    principal_type: str


@dataclass
class AdmissionController:
    """Authenticates, schema-validates, scope-validates, and assigns publication identity."""

    trust: TrustPlane
    schemas: SchemaSource
    _rejections: dict[str, int] = field(default_factory=dict, init=False)
    _admitted: int = field(default=0, init=False)

    def admit(
        self,
        token: str,
        event: Event,
        causation_id: str | None = None,
        business_context: dict[str, str] | None = None,
    ) -> tuple[ProducerIdentity, Provenance]:
        """Runs the four admission checks in order and returns the publication identity."""
        try:
            identity = self.trust.authenticate_producer(token)
        except Exception as exc:
            self._reject("authentication")
            raise ProducerNotAuthenticated(str(exc)) from exc

        # The category check comes before authorization so an event with no
        # home stream is rejected as a schema problem, not a permission one.
        try:
            DomainCategory.of(event.event_type)
        except ValueError as exc:
            self._reject("schema")
            raise SchemaRejected(str(exc)) from exc

        if identity.tenant_id != event.tenant_id:
            self._reject("tenant")
            raise TenantRejected(
                f"producer '{identity.principal_id}' belongs to tenant '{identity.tenant_id}' and may not "
                f"emit into '{event.tenant_id}' (08 rule 3)"
            )

        if not self.trust.authorize_emission(token, event.event_type, event.tenant_id):
            self._reject("authorization")
            raise ProducerNotAuthorized(
                f"producer '{identity.principal_id}' is not permitted to emit '{event.event_type}' "
                f"in tenant '{event.tenant_id}' (08.18.2)"
            )

        try:
            self.schemas.validate(event.event_type, dict(event.payload), event.schema_version)
        except Exception as exc:
            self._reject("schema")
            raise SchemaRejected(str(exc)) from exc

        self._admitted += 1
        emitted_at = datetime.now(UTC)
        provenance = Provenance(
            causation_id=causation_id,
            correlation_id=event.trace_id,
            source_identity=identity.principal_id,
            origin_timestamp=event.timestamp,
            emission_timestamp=emitted_at,
            business_context=dict(business_context or {}),
        )
        return identity, provenance

    def _reject(self, cause: str) -> None:
        self._rejections[cause] = self._rejections.get(cause, 0) + 1

    @property
    def admitted(self) -> int:
        return self._admitted

    @property
    def rejections_by_cause(self) -> dict[str, int]:
        """Feeds the "admission rate and rejection rate by cause" signal of 21B §15.11."""
        return dict(self._rejections)

    @property
    def rejected(self) -> int:
        return sum(self._rejections.values())
