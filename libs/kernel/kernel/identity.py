"""Artifact Identity — the shape every kernel-backed artifact carries.

Realizes 21A §5.2 item 1 (Artifact Identity). Consumed by every Gateway's
internal artifacts (decisions, tool invocations, journal entries, etc.) so
identity, tenancy, and provenance are uniform across the system.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from pydantic import BaseModel, Field


def _uuid7_like() -> str:
    # ponytail: stdlib has no UUIDv7; uuid4 is a placeholder until Python
    # ships uuid7 (3.14+) or a vetted backport is added to the stack table.
    return str(uuid.uuid4())


class ArtifactIdentity(BaseModel):
    artifact_id: str = Field(default_factory=_uuid7_like)
    artifact_type: str
    tenant_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    created_by: str
    trace_id: str = Field(default_factory=_uuid7_like)

    model_config = {"frozen": True}
