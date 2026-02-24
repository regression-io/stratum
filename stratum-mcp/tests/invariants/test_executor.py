"""Tests for DAG executor invariants: ensure eval, ref resolution, topo sort."""
import pytest

from stratum_mcp.executor import (
    _ENSURE_BUILTINS,
    _FILE_CONTAINS_SIZE_LIMIT,
    _validate_output_schema,
    EnsureCompileError,
    RefResolutionError,
    compile_ensure,
    resolve_ref,
)
from stratum_mcp.errors import MCPExecutionError
from stratum_mcp.spec import IRFlowDef, IRStepDef, IRFunctionDef, IRBudgetDef


# ---------------------------------------------------------------------------
# compile_ensure (G9 fix)
# ---------------------------------------------------------------------------

def test_compile_ensure_attribute_style_on_dict():
    """G9 fix: ensure exprs work on dict outputs via SimpleNamespace wrap."""
    fn = compile_ensure("result.confidence > 0.7")
    assert fn({"confidence": 0.9}) is True
    assert fn({"confidence": 0.5}) is False


def test_compile_ensure_nested_attribute():
    fn = compile_ensure("result.label == 'positive'")
    assert fn({"label": "positive"}) is True
    assert fn({"label": "negative"}) is False


def test_compile_ensure_dunder_expressions_rejected():
    """Dunder attributes are blocked at compile time, not just at eval time.
    This closes the __class__.__subclasses__() sandbox escape for Claude-generated IR."""
    with pytest.raises(EnsureCompileError, match="dunder"):
        compile_ensure("result.__class__.__subclasses__()")


def test_compile_ensure_syntax_error_raises():
    with pytest.raises(EnsureCompileError):
        compile_ensure("result.x ===")


def test_compile_ensure_on_non_dict():
    """Non-dict result is passed through directly (e.g., string, number)."""
    fn = compile_ensure("result > 5")
    assert fn(10) is True
    assert fn(3) is False


# ---------------------------------------------------------------------------
# file-aware builtins
# ---------------------------------------------------------------------------

def test_file_exists_true(tmp_path):
    f = tmp_path / "output.md"
    f.write_text("hello")
    fn = compile_ensure("file_exists(result.path)")
    assert fn({"path": str(f)}) is True


def test_file_exists_false(tmp_path):
    fn = compile_ensure("file_exists(result.path)")
    assert fn({"path": str(tmp_path / "missing.md")}) is False


def test_file_contains_true(tmp_path):
    f = tmp_path / "output.md"
    f.write_text("# Design Doc\nsome content")
    fn = compile_ensure("file_contains(result.path, '# Design Doc')")
    assert fn({"path": str(f)}) is True


def test_file_contains_false(tmp_path):
    f = tmp_path / "output.md"
    f.write_text("some content")
    fn = compile_ensure("file_contains(result.path, '# Design Doc')")
    assert fn({"path": str(f)}) is False


def test_file_contains_missing_file(tmp_path):
    fn = compile_ensure("file_contains(result.path, 'anything')")
    assert fn({"path": str(tmp_path / "missing.md")}) is False


def test_file_contains_binary_file_returns_false(tmp_path):
    """Binary/non-UTF-8 content returns False rather than raising."""
    f = tmp_path / "binary.bin"
    f.write_bytes(b"\x80\x81\x82\xff\xfe")
    fn = compile_ensure("file_contains(result.path, 'marker')")
    assert fn({"path": str(f)}) is False


def test_file_contains_oversized_file_returns_false(tmp_path, monkeypatch):
    """File over the size limit returns False without reading it."""
    f = tmp_path / "big.txt"
    f.write_text("contains the marker")
    monkeypatch.setattr("stratum_mcp.executor._FILE_CONTAINS_SIZE_LIMIT", 5)
    fn = compile_ensure("file_contains(result.path, 'marker')")
    assert fn({"path": str(f)}) is False


# ---------------------------------------------------------------------------
# _validate_output_schema
# ---------------------------------------------------------------------------

def test_validate_output_schema_passes():
    schema = {"type": "object", "required": ["path"], "properties": {"path": {"type": "string"}}}
    assert _validate_output_schema({"path": "/tmp/out.md"}, schema) == []


def test_validate_output_schema_missing_required():
    schema = {"type": "object", "required": ["path"], "properties": {"path": {"type": "string"}}}
    errors = _validate_output_schema({}, schema)
    assert len(errors) == 1
    assert "output_schema violation" in errors[0]
    assert "path" in errors[0]


def test_validate_output_schema_wrong_type():
    schema = {"type": "object", "properties": {"count": {"type": "integer"}}}
    errors = _validate_output_schema({"count": "not-an-int"}, schema)
    assert len(errors) == 1
    assert "output_schema violation" in errors[0]


def test_validate_output_schema_multiple_violations():
    schema = {
        "type": "object",
        "required": ["a", "b"],
        "properties": {"a": {"type": "string"}, "b": {"type": "integer"}},
    }
    errors = _validate_output_schema({}, schema)
    assert len(errors) == 2


def test_validate_output_schema_unresolvable_ref_returns_violation():
    """Unresolvable $ref in output_schema returns a violation string, not an exception."""
    schema = {"$ref": "#/$defs/DoesNotExist"}
    errors = _validate_output_schema({"path": "/tmp/out.md"}, schema)
    assert len(errors) == 1
    assert "output_schema violation" in errors[0]


def test_validate_output_schema_empty_schema_accepts_anything():
    """Empty schema {} is valid JSON Schema — accepts any value."""
    assert _validate_output_schema({"anything": 123}, {}) == []
    assert _validate_output_schema({}, {}) == []
    assert _validate_output_schema({"nested": {"deep": True}}, {}) == []


def test_ensure_builtins_no_dangerous_names():
    """_ENSURE_BUILTINS must not expose exec, eval, import, or open at top level."""
    dangerous = {"exec", "eval", "__import__", "compile", "globals", "locals", "vars"}
    exposed = set(_ENSURE_BUILTINS.keys())
    assert not (dangerous & exposed)


# ---------------------------------------------------------------------------
# resolve_ref
# ---------------------------------------------------------------------------

def test_resolve_ref_input():
    assert resolve_ref("$.input.text", {"text": "hello"}, {}) == "hello"


def test_resolve_ref_step_output():
    result = resolve_ref("$.steps.s1.output", {}, {"s1": {"label": "positive"}})
    assert result == {"label": "positive"}


def test_resolve_ref_step_output_field():
    result = resolve_ref("$.steps.s1.output.label", {}, {"s1": {"label": "positive"}})
    assert result == "positive"


def test_resolve_ref_literal():
    assert resolve_ref("some literal", {}, {}) == "some literal"


def test_resolve_ref_missing_input_field_raises():
    with pytest.raises(RefResolutionError):
        resolve_ref("$.input.missing", {}, {})


def test_resolve_ref_step_not_executed_raises():
    with pytest.raises(RefResolutionError):
        resolve_ref("$.steps.s99.output", {}, {})


# ---------------------------------------------------------------------------
# _topological_sort
# ---------------------------------------------------------------------------

def _make_step(id: str, function: str = "f", inputs: dict = None, depends_on: list = None):
    return IRStepDef(
        id=id,
        function=function,
        inputs=inputs or {},
        depends_on=depends_on or [],
    )


def _make_flow(steps: list[IRStepDef]) -> IRFlowDef:
    return IRFlowDef(
        name="test_flow",
        input_schema={},
        output_contract="Out",
        budget=None,
        steps=steps,
    )


def test_topological_sort_linear():
    from stratum_mcp.executor import _topological_sort
    steps = [
        _make_step("s1"),
        _make_step("s2", depends_on=["s1"]),
        _make_step("s3", depends_on=["s2"]),
    ]
    flow = _make_flow(steps)
    ordered = _topological_sort(flow)
    ids = [s.id for s in ordered]
    assert ids.index("s1") < ids.index("s2") < ids.index("s3")


def test_topological_sort_parallel_independent():
    from stratum_mcp.executor import _topological_sort
    steps = [
        _make_step("s1"),
        _make_step("s2"),
        _make_step("s3", depends_on=["s1", "s2"]),
    ]
    flow = _make_flow(steps)
    ordered = _topological_sort(flow)
    ids = [s.id for s in ordered]
    assert ids.index("s1") < ids.index("s3")
    assert ids.index("s2") < ids.index("s3")


def test_topological_sort_implicit_ref_dependency():
    from stratum_mcp.executor import _topological_sort
    # s2 references s1's output via $ ref — should be ordered after s1
    steps = [
        _make_step("s1"),
        _make_step("s2", inputs={"x": "$.steps.s1.output"}),
    ]
    flow = _make_flow(steps)
    ordered = _topological_sort(flow)
    ids = [s.id for s in ordered]
    assert ids.index("s1") < ids.index("s2")


def test_topological_sort_cycle_raises():
    from stratum_mcp.executor import _topological_sort
    steps = [
        _make_step("s1", depends_on=["s2"]),
        _make_step("s2", depends_on=["s1"]),
    ]
    flow = _make_flow(steps)
    with pytest.raises(MCPExecutionError, match="Cycle detected"):
        _topological_sort(flow)
