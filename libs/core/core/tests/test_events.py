import pytest
from pydantic import ValidationError as PydanticValidationError

from core.events import Event


def test_event_defaults_populate():
    event = Event(
        trace_id="trace-1",
        event_type="agent.created",
        source="agent_runtime",
        tenant_id="t1",
        payload={"x": 1},
    )
    assert event.event_id
    assert event.schema_version == "1.0.0"
    assert event.metadata == {}


def test_event_is_immutable():
    event = Event(trace_id="trace-1", event_type="agent.created", source="agent_runtime", tenant_id="t1", payload={})
    with pytest.raises(PydanticValidationError):
        event.tenant_id = "t2"
