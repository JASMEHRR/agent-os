"""Schema validation and versioning.

A schema is a mapping of field name -> expected Python type. Event schema
evolution follows document 08's rules: minor versions are additive-only
(existing fields' types may never change within a major version); major
versions are breaking and get their own independent schema entry.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class SchemaNotRegisteredError(Exception):
    def __init__(self, event_type: str, version: str | None = None):
        suffix = f" version '{version}'" if version else ""
        super().__init__(f"no schema registered for event_type '{event_type}'{suffix}")


class SchemaValidationError(Exception):
    def __init__(self, event_type: str, errors: list[str]):
        super().__init__(f"payload for '{event_type}' failed validation: {errors}")
        self.errors = errors


@dataclass(frozen=True)
class SchemaEntry:
    event_type: str
    version: str  # "major.minor"
    fields: dict[str, type]


class SchemaRegistry:
    def __init__(self) -> None:
        self._schemas: dict[tuple[str, str], SchemaEntry] = {}
        self._latest_version: dict[str, str] = {}

    def register(self, event_type: str, version: str, fields: dict[str, type]) -> SchemaEntry:
        major = version.split(".")[0]
        self._reject_if_minor_removes_or_changes_fields(event_type, major, version, fields)
        entry = SchemaEntry(event_type=event_type, version=version, fields=fields)
        self._schemas[(event_type, version)] = entry
        current_latest = self._latest_version.get(event_type)
        if current_latest is None or _version_key(version) > _version_key(current_latest):
            self._latest_version[event_type] = version
        return entry

    def _reject_if_minor_removes_or_changes_fields(
        self, event_type: str, major: str, version: str, fields: dict[str, type]
    ) -> None:
        prior_versions = [v for (t, v) in self._schemas if t == event_type and v.split(".")[0] == major]
        if not prior_versions:
            return
        latest_same_major = max(prior_versions, key=_version_key)
        prior_fields = self._schemas[(event_type, latest_same_major)].fields
        for name, prior_type in prior_fields.items():
            if name not in fields:
                raise SchemaValidationError(event_type, [f"minor version {version} removed field '{name}'"])
            if fields[name] is not prior_type:
                raise SchemaValidationError(event_type, [f"minor version {version} changed type of field '{name}'"])

    def validate(self, event_type: str, payload: dict[str, Any], version: str | None = None) -> None:
        resolved_version = version or self._latest_version.get(event_type)
        if resolved_version is None or (event_type, resolved_version) not in self._schemas:
            raise SchemaNotRegisteredError(event_type, version)
        entry = self._schemas[(event_type, resolved_version)]
        errors = []
        for name, expected_type in entry.fields.items():
            if name not in payload:
                errors.append(f"missing required field '{name}'")
            elif not isinstance(payload[name], expected_type):
                errors.append(f"field '{name}' expected {expected_type.__name__}, got {type(payload[name]).__name__}")
        if errors:
            raise SchemaValidationError(event_type, errors)


def _version_key(version: str) -> tuple[int, int]:
    major, minor = version.split(".")
    return (int(major), int(minor))
