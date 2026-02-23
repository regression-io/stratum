"""Tests for DAG executor invariants: ensure eval, ref resolution, topo sort."""
import pytest

from stratum_mcp.executor import (
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
