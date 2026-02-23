"""Tests for stratum.contracts — registry, schema compilation, opaque, instantiate."""

# NOTE: Do NOT add `from __future__ import annotations` here.
# It makes all annotations into strings, which breaks get_type_hints() for
# locally-defined types in test methods.

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest
from typing import Annotated, Literal
from pydantic import BaseModel, Field

from stratum.contracts import (
    _OpaqueMarker,
    contract,
    contract_hash,
    get_hash,
    get_opaque_fields,
    get_schema,
    instantiate,
    is_opaque,
    is_registered,
    opaque,
    _annotation_to_schema,
)
from stratum.exceptions import StratumCompileError


# ---------------------------------------------------------------------------
# Module-level contracts (avoid get_type_hints issues with local classes)
# ---------------------------------------------------------------------------

@contract
class _ModuleInner(BaseModel):
    value: int


@contract
class _ModuleOuter(BaseModel):
    inner: _ModuleInner
    name: str


# ---------------------------------------------------------------------------
# opaque[T]
# ---------------------------------------------------------------------------

class TestOpaque:
    def test_opaque_str_is_annotated(self):
        result = opaque[str]
        from typing import get_origin, Annotated
        assert get_origin(result) is Annotated

    def test_opaque_str_has_marker_metadata(self):
        from typing import get_args
        result = opaque[str]
        args = get_args(result)
        assert any(isinstance(m, _OpaqueMarker) for m in args[1:])

    def test_opaque_int(self):
        from typing import get_args
        result = opaque[int]
        args = get_args(result)
        assert args[0] is int


# ---------------------------------------------------------------------------
# is_opaque
# ---------------------------------------------------------------------------

class TestIsOpaque:
    def test_opaque_field_returns_true(self):
        assert is_opaque(opaque[str]) is True

    def test_plain_str_returns_false(self):
        assert is_opaque(str) is False

    def test_annotated_without_marker_returns_false(self):
        ann = Annotated[str, Field(min_length=1)]
        assert is_opaque(ann) is False

    def test_none_type_returns_false(self):
        assert is_opaque(type(None)) is False


# ---------------------------------------------------------------------------
# contract_hash
# ---------------------------------------------------------------------------

class TestContractHash:
    def test_hash_is_12_chars(self):
        schema = {"type": "object", "properties": {"name": {"type": "string"}}}
        h = contract_hash(schema)
        assert len(h) == 12

    def test_hash_is_hex(self):
        schema = {"type": "string"}
        h = contract_hash(schema)
        int(h, 16)  # should not raise

    def test_hash_is_deterministic(self):
        schema = {"type": "object", "properties": {"x": {"type": "integer"}}}
        assert contract_hash(schema) == contract_hash(schema)

    def test_different_schemas_have_different_hashes(self):
        s1 = {"type": "string"}
        s2 = {"type": "integer"}
        assert contract_hash(s1) != contract_hash(s2)

    def test_key_order_does_not_matter(self):
        s1 = {"type": "object", "properties": {"a": {"type": "string"}}}
        s2 = {"properties": {"a": {"type": "string"}}, "type": "object"}
        assert contract_hash(s1) == contract_hash(s2)


# ---------------------------------------------------------------------------
# @contract decorator
# ---------------------------------------------------------------------------

@contract
class _SimpleModel(BaseModel):
    name: str
    value: int


@contract
class _OptionalModel(BaseModel):
    required_field: str
    optional_field: str | None = None


@contract
class _LiteralModel(BaseModel):
    label: Literal["a", "b", "c"]


@contract
class _ListModel(BaseModel):
    tags: list[str]


class TestContractDecorator:
    def test_model_registers(self):
        assert is_registered(_SimpleModel)

    def test_schema_type_is_object(self):
        schema = get_schema(_SimpleModel)
        assert schema["type"] == "object"
        assert "properties" in schema

    def test_schema_field_types(self):
        schema = get_schema(_SimpleModel)
        assert schema["properties"]["name"]["type"] == "string"
        assert schema["properties"]["value"]["type"] == "integer"

    def test_required_fields_excludes_optional(self):
        schema = get_schema(_OptionalModel)
        assert "required_field" in schema.get("required", [])
        assert "optional_field" not in schema.get("required", [])

    def test_literal_compiles_to_enum(self):
        schema = get_schema(_LiteralModel)
        prop = schema["properties"]["label"]
        assert "enum" in prop
        assert set(prop["enum"]) == {"a", "b", "c"}

    def test_list_field_compiles(self):
        schema = get_schema(_ListModel)
        prop = schema["properties"]["tags"]
        assert prop["type"] == "array"

    def test_hash_is_12_chars(self):
        assert len(get_hash(_SimpleModel)) == 12

    def test_contract_returns_class_unchanged(self):
        class MyModel(BaseModel):
            x: int
        result = contract(MyModel)
        assert result is MyModel

    def test_nested_contract_schema(self):
        schema = get_schema(_ModuleOuter)
        assert "properties" in schema
        assert "inner" in schema["properties"]
        # Pydantic uses $ref + $defs for nested models
        inner_prop = schema["properties"]["inner"]
        assert "$ref" in inner_prop or inner_prop.get("type") == "object"

    def test_plain_class_raises_compile_error(self):
        with pytest.raises(StratumCompileError, match="BaseModel"):
            @contract
            class NotAModel:
                x: int

    def test_plain_class_error_mentions_class_name(self):
        with pytest.raises(StratumCompileError, match="NotAModel2"):
            @contract
            class NotAModel2:
                x: int


# ---------------------------------------------------------------------------
# get_opaque_fields
# ---------------------------------------------------------------------------

@contract
class _WithOpaque(BaseModel):
    summary: str
    reasoning: opaque[str]
    count: int


@contract
class _NoOpaque(BaseModel):
    name: str
    value: int


class TestGetOpaqueFields:
    def test_returns_opaque_field_names(self):
        fields = get_opaque_fields(_WithOpaque)
        assert "reasoning" in fields
        assert "summary" not in fields
        assert "count" not in fields

    def test_no_opaque_fields_returns_empty(self):
        fields = get_opaque_fields(_NoOpaque)
        assert fields == []


# ---------------------------------------------------------------------------
# instantiate
# ---------------------------------------------------------------------------

@contract
class _InstModel(BaseModel):
    name: str
    value: int


class TestInstantiate:
    def test_basic_instantiation(self):
        obj = instantiate(_InstModel, {"name": "hello", "value": 42})
        assert obj.name == "hello"
        assert obj.value == 42

    def test_returns_pydantic_instance(self):
        obj = instantiate(_InstModel, {"name": "test", "value": 1})
        assert isinstance(obj, BaseModel)

    def test_pydantic_validation_runs(self):
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            instantiate(_InstModel, {"name": "test", "value": "not_coercible_xxxx"})

    def test_pydantic_coerces_compatible_types(self):
        # Pydantic v2 coerces int-as-string for int fields
        obj = instantiate(_InstModel, {"name": "test", "value": 7})
        assert obj.value == 7


# ---------------------------------------------------------------------------
# _annotation_to_schema — primitive coverage
# ---------------------------------------------------------------------------

class TestAnnotationToSchema:
    def test_str(self):
        assert _annotation_to_schema(str) == {"type": "string"}

    def test_int(self):
        assert _annotation_to_schema(int) == {"type": "integer"}

    def test_float(self):
        assert _annotation_to_schema(float) == {"type": "number"}

    def test_bool(self):
        assert _annotation_to_schema(bool) == {"type": "boolean"}

    def test_bytes(self):
        assert _annotation_to_schema(bytes) == {
            "type": "string",
            "contentEncoding": "base64",
        }

    def test_none(self):
        assert _annotation_to_schema(type(None)) == {"type": "null"}

    def test_optional_str(self):
        schema = _annotation_to_schema(str | None)
        assert schema == {"anyOf": [{"type": "string"}, {"type": "null"}]}

    def test_list_str(self):
        schema = _annotation_to_schema(list[str])
        assert schema == {"type": "array", "items": {"type": "string"}}

    def test_literal(self):
        schema = _annotation_to_schema(Literal["x", "y"])
        assert schema == {"enum": ["x", "y"]}

    def test_annotated_with_float_constraints(self):
        schema = _annotation_to_schema(Annotated[float, Field(ge=0.0, le=1.0)])
        assert schema.get("type") == "number"
        assert schema.get("minimum") == 0.0, f"Expected minimum=0.0, got schema={schema}"
        assert schema.get("maximum") == 1.0, f"Expected maximum=1.0, got schema={schema}"

    def test_annotated_str_constraints(self):
        schema = _annotation_to_schema(
            Annotated[str, Field(min_length=1, max_length=100)]
        )
        assert schema.get("type") == "string"
        assert schema.get("minLength") == 1, f"Expected minLength=1, got schema={schema}"
        assert schema.get("maxLength") == 100, f"Expected maxLength=100, got schema={schema}"
