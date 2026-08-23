"""Schema Registry: schema validation and versioning every event producer and
Gateway consults before emission (realizes 08.16.1, 10.16.2, 12.7.3)."""

from schema_registry.registry import (
    SchemaNotRegisteredError,
    SchemaRegistry,
    SchemaValidationError,
)

__all__ = ["SchemaRegistry", "SchemaNotRegisteredError", "SchemaValidationError"]
