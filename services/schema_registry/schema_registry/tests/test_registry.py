import pytest

from schema_registry.registry import SchemaNotRegisteredError, SchemaRegistry, SchemaValidationError


def test_register_and_validate_success():
    registry = SchemaRegistry()
    registry.register("agent.created", "1.0", {"agent_id": str, "tenant_id": str})
    registry.validate("agent.created", {"agent_id": "a1", "tenant_id": "t1"})  # no raise


def test_validate_unregistered_type_rejected():
    registry = SchemaRegistry()
    with pytest.raises(SchemaNotRegisteredError):
        registry.validate("unknown.event", {})


def test_validate_missing_field_rejected():
    registry = SchemaRegistry()
    registry.register("agent.created", "1.0", {"agent_id": str})
    with pytest.raises(SchemaValidationError):
        registry.validate("agent.created", {})


def test_minor_version_additive_only():
    registry = SchemaRegistry()
    registry.register("agent.created", "1.0", {"agent_id": str})
    registry.register("agent.created", "1.1", {"agent_id": str, "tenant_id": str})  # additive, ok
    registry.validate("agent.created", {"agent_id": "a1", "tenant_id": "t1"})  # latest = 1.1


def test_minor_version_cannot_remove_field():
    registry = SchemaRegistry()
    registry.register("agent.created", "1.0", {"agent_id": str, "tenant_id": str})
    with pytest.raises(SchemaValidationError):
        registry.register("agent.created", "1.1", {"agent_id": str})


def test_major_version_independent_schema():
    registry = SchemaRegistry()
    registry.register("agent.created", "1.0", {"agent_id": str, "tenant_id": str})
    registry.register("agent.created", "2.0", {"agent_id": str})  # breaking change allowed on major bump
    registry.validate("agent.created", {"agent_id": "a1"}, version="2.0")
    registry.validate("agent.created", {"agent_id": "a1", "tenant_id": "t1"}, version="1.0")
