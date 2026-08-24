"""Turning the domain's dataclasses into JSON and back.

A durable Repository has to write bytes, and every module in this system
stores frozen dataclasses holding enums, datetimes, tuples and nested
dataclasses. Something has to bridge those, and the choice of what has real
consequences.

**Not pickle.** Pickle would need no code at all and would round-trip
everything here perfectly. It also executes arbitrary code on load, which
turns the database from a store of records into a store of instructions: any
write path that a caller can influence becomes remote code execution at the
next read. A system whose whole design is structural refusal should not have
that at its foundation.

**JSON, reconstructed from type hints.** The encoder walks the dataclass; the
decoder walks the target type's annotations and rebuilds. That means the type
is supplied by the *reader* rather than carried in the payload, so a tampered
row cannot name the class it becomes.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import enum
import types
import typing
from typing import Any, TypeVar, cast, get_args, get_origin, get_type_hints

T = TypeVar("T")

#: Marks a value the encoder wrapped so the decoder can tell a datetime from a
#: string that happens to look like one. Only used where the target annotation
#: would otherwise be ambiguous.
_ISO_PREFIX = "\x00iso:"


class CodecError(TypeError):
    """A value the codec cannot represent, or a row it cannot rebuild."""


# ------------------------------------------------------------------ Encoding


def encode(value: Any) -> Any:
    """Recursively converts a domain value into JSON-safe primitives."""
    if value is None or isinstance(value, bool | int | float):
        return value
    if isinstance(value, str):
        # A string that already starts with the marker would decode as a
        # datetime. Vanishingly unlikely and silently wrong, so it is refused.
        if value.startswith(_ISO_PREFIX):
            raise CodecError("string value collides with the codec's datetime marker")
        return value
    if isinstance(value, enum.Enum):
        return encode(value.value)
    if isinstance(value, dt.datetime | dt.date):
        return _ISO_PREFIX + value.isoformat()
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {f.name: encode(getattr(value, f.name)) for f in dataclasses.fields(value)}
    if isinstance(value, dict):
        return {str(k): encode(v) for k, v in value.items()}
    if isinstance(value, list | tuple | set | frozenset):
        return [encode(item) for item in value]
    raise CodecError(f"cannot encode {type(value).__name__}")


# ------------------------------------------------------------------ Decoding


def _unwrap_optional(annotation: Any) -> tuple[Any, bool]:
    """Splits `X | None` into `(X, True)`. Leaves anything else alone."""
    origin = get_origin(annotation)
    if origin is typing.Union or origin is types.UnionType:
        args = [a for a in get_args(annotation) if a is not type(None)]
        if len(args) == 1:
            return args[0], True
    return annotation, False


def decode(annotation: Any, raw: Any) -> Any:
    """Rebuilds a value of type `annotation` from decoded JSON."""
    annotation, optional = _unwrap_optional(annotation)
    if raw is None:
        if not optional:
            # Not silently substituted. A None where the type says otherwise
            # means the row and the code disagree about the shape, and quietly
            # accepting it would hide a migration that was never written.
            raise CodecError(f"got None for non-optional {annotation!r}")
        return None

    if annotation is Any:
        return raw

    if isinstance(annotation, type) and issubclass(annotation, enum.Enum):
        return annotation(raw)

    if isinstance(annotation, type) and issubclass(annotation, dt.datetime):
        return dt.datetime.fromisoformat(_strip_marker(raw))
    if isinstance(annotation, type) and issubclass(annotation, dt.date):
        return dt.date.fromisoformat(_strip_marker(raw))

    if dataclasses.is_dataclass(annotation) and isinstance(annotation, type):
        return decode_dataclass(annotation, raw)

    origin = get_origin(annotation)
    if origin in (list, tuple, set, frozenset):
        args = get_args(annotation)
        if origin is tuple and len(args) == 2 and args[1] is Ellipsis:
            args = (args[0],)
        item_type = args[0] if args else Any
        items = [decode(item_type, item) for item in raw]
        if origin is list:
            return items
        if origin is tuple:
            return tuple(items)
        if origin is set:
            return set(items)
        return frozenset(items)

    if origin is dict:
        args = get_args(annotation)
        value_type = args[1] if len(args) == 2 else Any
        return {k: decode(value_type, v) for k, v in raw.items()}

    if isinstance(raw, str):
        return _strip_marker(raw)
    return raw


def _strip_marker(raw: Any) -> Any:
    if isinstance(raw, str) and raw.startswith(_ISO_PREFIX):
        return raw[len(_ISO_PREFIX) :]
    return raw


def decode_dataclass(cls: type[T], raw: Any) -> T:
    """Rebuilds `cls` from a decoded JSON object.

    Fields absent from the row fall back to their default. A field with no
    default and no stored value raises rather than being filled in: the row
    predates the field, which is a migration the caller has to decide about
    rather than something this layer should guess at.
    """
    if not isinstance(raw, dict):
        raise CodecError(f"expected an object to rebuild {cls.__name__}, got {type(raw).__name__}")
    if not dataclasses.is_dataclass(cls):
        raise CodecError(f"{cls.__name__} is not a dataclass and cannot be rebuilt from a row")

    hints = get_type_hints(cls)
    kwargs: dict[str, Any] = {}
    for field in dataclasses.fields(cls):
        if not field.init:
            continue
        if field.name in raw:
            kwargs[field.name] = decode(hints.get(field.name, Any), raw[field.name])
            continue
        has_default = field.default is not dataclasses.MISSING or field.default_factory is not dataclasses.MISSING
        if not has_default:
            raise CodecError(
                f"{cls.__name__}.{field.name} is missing from the stored row and has no default; "
                "the row predates the field and needs a migration"
            )
    # cast: `is_dataclass` narrows `cls` to DataclassInstance, which loses the
    # TypeVar. The constructor genuinely returns T.
    return cast(T, cls(**kwargs))
