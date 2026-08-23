"""Shared Event schema (schema-first, per Stage S2 note / 21C §29.4).

Every producer and consumer validates against this shape before any handler
code runs. Field set: event_id, trace_id, timestamp, schema_version,
event_type, source, tenant_id, payload, metadata.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field


class Event(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    trace_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    schema_version: str = "1.0.0"
    event_type: str
    source: str
    tenant_id: str
    payload: dict[str, Any]
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = {"frozen": True}
