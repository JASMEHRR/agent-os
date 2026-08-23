"""Adapter binding the Bus's `SchemaSource` protocol to the Schema Registry.

Exists for one reason worth stating plainly: the two subsystems spell schema
versions differently. `08.4.1` calls the event's `schema_version` "a semantic
version" and `core.Event` defaults it to `1.0.0`; the Schema Registry keys its
entries by `major.minor`, because 08's evolution rules only ever distinguish
additive minors from breaking majors — there is no such thing as a patch-level
schema change.

Rather than change either side (Part IV, 17 forbids redesigning a Done
module's interface to suit a consumer), this adapter narrows the semantic
version to the registry's key on the way in. The discrepancy is recorded as an
open item in the Journal for the Schema Registry to settle properly.
"""

from __future__ import annotations

from dataclasses import dataclass

from schema_registry import SchemaRegistry


def registry_version(schema_version: str | None) -> str | None:
    """Narrows `major.minor.patch` to the registry's `major.minor` key."""
    if schema_version is None:
        return None
    parts = schema_version.split(".")
    if len(parts) < 2:
        return schema_version
    return f"{parts[0]}.{parts[1]}"


@dataclass
class SchemaRegistrySource:
    """Implements `event_bus.admission.SchemaSource` over a live Schema Registry."""

    registry: SchemaRegistry

    def validate(self, event_type: str, payload: dict[str, object], version: str | None = None) -> None:
        self.registry.validate(event_type, payload, registry_version(version))
