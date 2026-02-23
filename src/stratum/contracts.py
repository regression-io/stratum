"""Contract registry, JSON Schema, content hash, and opaque[T]."""

from __future__ import annotations

import hashlib
import json
import typing
from typing import Any, Annotated, get_args, get_origin, get_type_hints

from .exceptions import StratumCompileError


# ---------------------------------------------------------------------------
# opaque[T]
# ---------------------------------------------------------------------------

class _OpaqueMarker:
    """Sentinel placed in Annotated metadata to mark opaque fields."""


class opaque:
    """
    Parameterized type alias: opaque[T] == Annotated[T, _OpaqueMarker()].

    Type checkers treat opaque[str] as str. The prompt compiler detects
    _OpaqueMarker in annotation metadata and routes the field to the
    structured JSON attachment rather than the inline prompt text.
    """

    def __class_getitem__(cls, item: type) -> Any:
        return Annotated[item, _OpaqueMarker()]


def is_opaque(annotation: Any) -> bool:
    """Return True if the annotation is opaque[T] (i.e. has _OpaqueMarker metadata)."""
    if get_origin(annotation) is not Annotated:
        return False
    for meta in get_args(annotation)[1:]:
        if isinstance(meta, _OpaqueMarker):
            return True
    return False


def get_base_type(annotation: Any) -> Any:
    """Strip Annotated wrapper (including opaque) to get the underlying type."""
    if get_origin(annotation) is Annotated:
        return get_args(annotation)[0]
    return annotation


# ---------------------------------------------------------------------------
# Content hash
# ---------------------------------------------------------------------------

def contract_hash(json_schema: dict) -> str:
    """SHA-256 of canonical JSON (sort_keys, no whitespace), returns hex[:12]."""
    canonical = json.dumps(json_schema, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()[:12]


# ---------------------------------------------------------------------------
# JSON Schema compilation — for primitive / inline return types only.
# @contract classes use Pydantic's model_json_schema() instead.
# ---------------------------------------------------------------------------

def _annotation_to_schema(annotation: Any) -> dict:
    """
    Convert a Python type annotation to JSON Schema.

    Used for non-@contract return types (primitives, Literal, list, etc.).
    @contract classes are handled via get_schema() / model_json_schema().
    """
    # Unwrap Annotated — apply field constraints if present
    if get_origin(annotation) is Annotated:
        args = get_args(annotation)
        base = args[0]
        metadata = args[1:]
        schema = _annotation_to_schema(base)
        for meta in metadata:
            if isinstance(meta, _OpaqueMarker):
                continue
            _apply_field_constraints(schema, meta)
        return schema

    origin = get_origin(annotation)

    # Union / Optional
    if origin is typing.Union:
        args = get_args(annotation)
        non_none = [a for a in args if a is not type(None)]
        has_none = type(None) in args
        if has_none and len(non_none) == 1:
            return {"anyOf": [_annotation_to_schema(non_none[0]), {"type": "null"}]}
        return {"anyOf": [_annotation_to_schema(a) for a in args]}

    # Python 3.10+ union syntax: X | Y
    try:
        import types as _types
        if isinstance(annotation, _types.UnionType):
            args = get_args(annotation)
            non_none = [a for a in args if a is not type(None)]
            has_none = type(None) in args
            if has_none and len(non_none) == 1:
                return {"anyOf": [_annotation_to_schema(non_none[0]), {"type": "null"}]}
            return {"anyOf": [_annotation_to_schema(a) for a in args]}
    except AttributeError:
        pass

    # list[T]
    if origin is list:
        args = get_args(annotation)
        items_schema = _annotation_to_schema(args[0]) if args else {}
        return {"type": "array", "items": items_schema}

    # Literal[...]
    if origin is typing.Literal:
        return {"enum": list(get_args(annotation))}

    # Primitives
    if annotation is str:
        return {"type": "string"}
    if annotation is int:
        return {"type": "integer"}
    if annotation is float:
        return {"type": "number"}
    if annotation is bool:
        return {"type": "boolean"}
    if annotation is bytes:
        return {"type": "string", "contentEncoding": "base64"}
    if annotation is type(None):
        return {"type": "null"}

    try:
        import datetime
        if annotation is datetime.date:
            return {"type": "string", "format": "date"}
        if annotation is datetime.datetime:
            return {"type": "string", "format": "date-time"}
    except ImportError:
        pass

    # Fallback — permissive schema rather than crashing
    return {}


def _apply_field_constraints(schema: dict, meta: Any) -> None:
    """Apply ge/le/gt/lt/min_length/max_length constraints from a metadata object."""
    try:
        from pydantic.fields import FieldInfo
        if isinstance(meta, FieldInfo):
            for sub in getattr(meta, "metadata", []):
                _apply_field_constraints(schema, sub)
            return
    except ImportError:
        pass

    mapping = {
        "ge": "minimum",
        "le": "maximum",
        "gt": "exclusiveMinimum",
        "lt": "exclusiveMaximum",
        "min_length": "minLength",
        "max_length": "maxLength",
    }
    for attr, json_key in mapping.items():
        val = getattr(meta, attr, None)
        if val is not None:
            schema[json_key] = val


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

_registry: dict[type, dict] = {}   # cls -> json_schema
_hashes: dict[type, str] = {}      # cls -> content_hash


# ---------------------------------------------------------------------------
# @contract decorator
# ---------------------------------------------------------------------------

def contract(cls: type) -> type:
    """
    Register a pydantic.BaseModel subclass as a Stratum contract.

    Uses Pydantic's model_json_schema() for accurate JSON Schema generation
    including field constraints, validators, and nested model $defs.
    Raises StratumCompileError if cls is not a pydantic.BaseModel subclass.
    """
    from pydantic import BaseModel
    if not (isinstance(cls, type) and issubclass(cls, BaseModel)):
        raise StratumCompileError(
            f"@contract requires a pydantic.BaseModel subclass. "
            f"'{cls.__name__}' is not a BaseModel. "
            f"Declare it as: class {cls.__name__}(BaseModel): ..."
        )

    schema = cls.model_json_schema()
    h = contract_hash(schema)
    _registry[cls] = schema
    _hashes[cls] = h
    return cls


def get_schema(cls: type) -> dict:
    """Return the JSON Schema for a registered contract class."""
    return _registry[cls]


def get_hash(cls: type) -> str:
    """Return the content hash for a registered contract class."""
    return _hashes[cls]


def is_registered(cls: Any) -> bool:
    """Return True if cls is a registered @contract class."""
    return isinstance(cls, type) and cls in _registry


def get_opaque_fields(cls: type) -> list[str]:
    """Return field names whose type annotation is opaque[T]."""
    try:
        hints = get_type_hints(cls, include_extras=True)
    except Exception:
        return []
    return [name for name, ann in hints.items() if is_opaque(ann)]


def instantiate(cls: type, data: dict) -> Any:
    """Create a validated pydantic instance of cls from a dict."""
    return cls(**data)
