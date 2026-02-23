"""Contract registry, JSON Schema compilation, content hash, and opaque[T]."""

from __future__ import annotations

import dataclasses
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
# JSON Schema compilation
# ---------------------------------------------------------------------------

def _annotation_to_schema(annotation: Any, _seen: set[type] | None = None) -> dict:
    """
    Recursively convert a Python type annotation to JSON Schema draft 2020-12.
    """
    if _seen is None:
        _seen = set()

    # Unwrap Annotated to check for Field constraints and opaque marker
    if get_origin(annotation) is Annotated:
        args = get_args(annotation)
        base = args[0]
        metadata = args[1:]

        # opaque[T] — the marker is a prompt-compiler concern only; generate schema for T
        schema = _annotation_to_schema(base, _seen)

        # Apply constraint metadata from FieldInfo-like objects
        for meta in metadata:
            if isinstance(meta, _OpaqueMarker):
                continue
            # Support pydantic FieldInfo and any object with constraint attributes
            _apply_field_constraints(schema, meta)

        return schema

    # Union types: T | None  and  Optional[T]  (get_origin == types.UnionType or Union)
    origin = get_origin(annotation)
    if origin is typing.Union:
        args = get_args(annotation)
        non_none = [a for a in args if a is not type(None)]
        has_none = type(None) in args
        if has_none and len(non_none) == 1:
            return {"anyOf": [_annotation_to_schema(non_none[0], _seen), {"type": "null"}]}
        # General union — not explicitly in spec but handle gracefully
        return {"anyOf": [_annotation_to_schema(a, _seen) for a in args]}

    # Python 3.10+ union syntax: X | Y
    try:
        import types as _types
        if isinstance(annotation, _types.UnionType):
            args = get_args(annotation)
            non_none = [a for a in args if a is not type(None)]
            has_none = type(None) in args
            if has_none and len(non_none) == 1:
                return {"anyOf": [_annotation_to_schema(non_none[0], _seen), {"type": "null"}]}
            return {"anyOf": [_annotation_to_schema(a, _seen) for a in args]}
    except AttributeError:
        pass

    # list[T]
    if origin is list:
        args = get_args(annotation)
        items_schema = _annotation_to_schema(args[0], _seen) if args else {}
        return {"type": "array", "items": items_schema}

    # Literal[...]
    if origin is typing.Literal:
        return {"enum": list(get_args(annotation))}

    # Registered @contract class — inline the full object schema
    if isinstance(annotation, type) and annotation in _registry:
        if annotation in _seen:
            raise StratumCompileError(
                f"Circular contract reference detected for '{annotation.__name__}'"
            )
        seen2 = _seen | {annotation}
        return _compile_class_schema(annotation, seen2)

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

    # datetime.date and datetime.datetime
    try:
        import datetime
        if annotation is datetime.date:
            return {"type": "string", "format": "date"}
        if annotation is datetime.datetime:
            return {"type": "string", "format": "date-time"}
    except ImportError:
        pass

    # Fallback — emit a permissive schema rather than crashing
    return {}


def _apply_field_constraints(schema: dict, meta: Any) -> None:
    """Apply ge/le/gt/lt/min_length/max_length constraints from a metadata object.

    Handles both:
    - Pydantic v2 FieldInfo (constraints stored in .metadata as annotated_types objects)
    - Direct annotated_types objects (Ge, Le, Gt, Lt, MinLen, MaxLen)
    - Any object with ge/le/gt/lt/min_length/max_length attributes directly
    """
    # If this is a Pydantic v2 FieldInfo, recurse into its .metadata list
    try:
        from pydantic.fields import FieldInfo  # type: ignore[import-untyped]
        if isinstance(meta, FieldInfo):
            for sub in getattr(meta, "metadata", []):
                _apply_field_constraints(schema, sub)
            return
    except ImportError:
        pass

    # Direct attribute mapping — works for annotated_types.Ge/Le/Gt/Lt/MinLen/MaxLen
    # and any user-supplied object with these attributes
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


def _compile_class_schema(cls: type, _seen: set[type] | None = None) -> dict:
    """
    Generate {"type": "object", "properties": {...}, "required": [...]}
    from typing.get_type_hints(cls, include_extras=True).
    """
    if _seen is None:
        _seen = set()

    try:
        hints = get_type_hints(cls, include_extras=True)
    except Exception:
        hints = {}

    properties: dict[str, dict] = {}
    required: list[str] = []

    for field_name, annotation in hints.items():
        if field_name.startswith("_"):
            continue

        prop_schema = _annotation_to_schema(annotation, _seen)
        properties[field_name] = prop_schema

        # A field is required if None is not in its type
        if not _is_optional(annotation):
            required.append(field_name)

    schema: dict[str, Any] = {
        "type": "object",
        "properties": properties,
    }
    if required:
        schema["required"] = required

    return schema


def _is_optional(annotation: Any) -> bool:
    """Return True if type(None) appears anywhere in the top-level union."""
    origin = get_origin(annotation)
    if origin is typing.Union:
        return type(None) in get_args(annotation)
    try:
        import types as _types
        if isinstance(annotation, _types.UnionType):
            return type(None) in get_args(annotation)
    except AttributeError:
        pass
    if origin is Annotated:
        return _is_optional(get_args(annotation)[0])
    return False


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
    Register a class as a Stratum contract.

    Computes JSON Schema and content hash at decoration time. If the class
    inherits from pydantic.BaseModel, uses Pydantic's schema generation.
    Otherwise generates from typing.get_type_hints().
    """
    # Attempt pydantic schema first
    schema: dict | None = None
    try:
        from pydantic import BaseModel  # type: ignore[import-untyped]
        if issubclass(cls, BaseModel):
            raw = cls.model_json_schema()
            # Pydantic may produce $defs — keep as-is
            schema = raw
    except ImportError:
        pass

    if schema is None:
        schema = _compile_class_schema(cls)

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
    """
    Create an instance of cls from a dict.

    Priority:
    1. Pydantic BaseModel — cls(**data)
    2. dataclass — cls(**data)
    3. Plain class — object.__new__ + __dict__.update
    """
    try:
        from pydantic import BaseModel  # type: ignore[import-untyped]
        if issubclass(cls, BaseModel):
            return cls(**data)
    except ImportError:
        pass

    if dataclasses.is_dataclass(cls):
        return cls(**data)

    obj = object.__new__(cls)
    obj.__dict__.update(data)
    return obj
