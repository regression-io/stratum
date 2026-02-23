"""Tests for stratum.contracts — registry, schema compilation, opaque, instantiate."""

# NOTE: Do NOT add `from __future__ import annotations` here.
# It makes all annotations into strings, which breaks get_type_hints() for
# locally-defined types in test methods.

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest
from typing import Annotated, Literal

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
    _compile_class_schema,
)


# ---------------------------------------------------------------------------
# Module-level contracts (avoid get_type_hints issues with local classes)
# ---------------------------------------------------------------------------

@contract
class _ModuleInner:
    value: int


@contract
class _ModuleOuter:
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
        # args[0] is str, args[1:] are metadata
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
        try:
            from pydantic import Field
            ann = Annotated[str, Field(min_length=1)]
            assert is_opaque(ann) is False
        except ImportError:
            pytest.skip("pydantic not installed")

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
# @contract on plain class
# ---------------------------------------------------------------------------

@contract
class _PlainClass:
    name: str
    value: int


@contract
class _PlainWithOptional:
    required_field: str
    optional_field: str | None


@contract
class _PlainWithLiteral:
    label: Literal["a", "b", "c"]


@contract
class _PlainWithList:
    tags: list[str]


class TestContractDecorator:
    def test_plain_class_registers(self):
        assert is_registered(_PlainClass)

    def test_plain_class_schema_has_correct_type(self):
        schema = get_schema(_PlainClass)
        assert schema["type"] == "object"
        assert "properties" in schema
        assert schema["properties"]["name"] == {"type": "string"}
        assert schema["properties"]["value"] == {"type": "integer"}

    def test_required_fields_excludes_optional(self):
        schema = get_schema(_PlainWithOptional)
        assert "required_field" in schema.get("required", [])
        assert "optional_field" not in schema.get("required", [])

    def test_literal_compiles_to_enum(self):
        schema = get_schema(_PlainWithLiteral)
        assert schema["properties"]["label"] == {"enum": ["a", "b", "c"]}

    def test_list_field_compiles_correctly(self):
        schema = get_schema(_PlainWithList)
        assert schema["properties"]["tags"] == {
            "type": "array",
            "items": {"type": "string"},
        }

    def test_hash_is_12_chars(self):
        h = get_hash(_PlainClass)
        assert len(h) == 12

    def test_contract_returns_class_unchanged(self):
        class Original:
            x: int

        result = contract(Original)
        assert result is Original

    def test_nested_contract(self):
        # Use module-level classes to avoid get_type_hints resolution issues
        # when from __future__ import annotations is active
        schema = get_schema(_ModuleOuter)
        assert "properties" in schema, f"No 'properties' key in schema: {schema}"
        assert "inner" in schema["properties"], (
            f"'inner' not in properties. schema={schema}"
        )
        inner_schema = schema["properties"]["inner"]
        assert inner_schema["type"] == "object"
        assert "value" in inner_schema["properties"]


# ---------------------------------------------------------------------------
# @contract with pydantic BaseModel
# ---------------------------------------------------------------------------

class TestContractPydantic:
    def test_pydantic_model_registered(self):
        try:
            from pydantic import BaseModel, Field
        except ImportError:
            pytest.skip("pydantic not installed")

        @contract
        class PydanticContract(BaseModel):
            name: str
            score: Annotated[float, Field(ge=0.0, le=1.0)]

        assert is_registered(PydanticContract)
        schema = get_schema(PydanticContract)
        assert "properties" in schema

    def test_pydantic_instantiate(self):
        try:
            from pydantic import BaseModel
        except ImportError:
            pytest.skip("pydantic not installed")

        @contract
        class SimpleModel(BaseModel):
            name: str
            count: int

        instance = instantiate(SimpleModel, {"name": "test", "count": 42})
        assert instance.name == "test"
        assert instance.count == 42


# ---------------------------------------------------------------------------
# get_opaque_fields
# ---------------------------------------------------------------------------

@contract
class _WithOpaque:
    summary: str
    reasoning: opaque[str]
    count: int


@contract
class _NoOpaque:
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
class _PlainInst:
    name: str
    value: int


class TestInstantiate:
    def test_plain_class_instantiation(self):
        obj = instantiate(_PlainInst, {"name": "hello", "value": 42})
        assert obj.name == "hello"
        assert obj.value == 42

    def test_dataclass_instantiation(self):
        import dataclasses

        @contract
        @dataclasses.dataclass
        class DC:
            name: str
            count: int

        obj = instantiate(DC, {"name": "test", "count": 7})
        assert obj.name == "test"
        assert obj.count == 7

    def test_plain_class_without_init(self):
        @contract
        class NoInit:
            x: int
            y: str

        obj = instantiate(NoInit, {"x": 1, "y": "hello"})
        assert obj.x == 1
        assert obj.y == "hello"


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
        try:
            from pydantic import Field
        except ImportError:
            pytest.skip("pydantic not installed")

        schema = _annotation_to_schema(Annotated[float, Field(ge=0.0, le=1.0)])
        assert schema.get("type") == "number"
        assert schema.get("minimum") == 0.0, f"Expected minimum=0.0, got schema={schema}"
        assert schema.get("maximum") == 1.0, f"Expected maximum=1.0, got schema={schema}"

    def test_annotated_str_constraints(self):
        try:
            from pydantic import Field
        except ImportError:
            pytest.skip("pydantic not installed")

        schema = _annotation_to_schema(
            Annotated[str, Field(min_length=1, max_length=100)]
        )
        assert schema.get("type") == "string"
        assert schema.get("minLength") == 1, f"Expected minLength=1, got schema={schema}"
        assert schema.get("maxLength") == 100, f"Expected maxLength=100, got schema={schema}"
