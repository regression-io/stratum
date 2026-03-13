"""Tests for IR v0.3 parallel task decomposition schema and validation."""
import pytest

from stratum_mcp.errors import IRSemanticError
from stratum_mcp.spec import parse_and_validate
from stratum_mcp.executor import _ENSURE_BUILTINS


# ---------------------------------------------------------------------------
# Fixtures: valid v0.3 spec with decompose + parallel_dispatch
# ---------------------------------------------------------------------------

_VALID_V03_SPEC = """
version: "0.3"
contracts:
  TaskGraph:
    tasks: {type: array}
  PhaseResult:
    outcome: {type: string}
functions:
  work:
    mode: infer
    intent: "Produce output"
    input: {}
    output: PhaseResult
flows:
  build:
    input: {plan: {type: string}}
    output: PhaseResult
    steps:
      - id: do_work
        function: work
        inputs: {plan: "$.input.plan"}
      - id: analyze
        type: decompose
        agent: claude
        intent: "Analyze the plan and produce a TaskGraph"
        output_contract: TaskGraph
        ensure:
          - "no_file_conflicts(result.tasks)"
        depends_on: [do_work]
      - id: execute
        type: parallel_dispatch
        source: "$.steps.analyze.output.tasks"
        agent: claude
        max_concurrent: 3
        isolation: worktree
        require: all
        merge: sequential_apply
        intent_template: "Implement: {task.description}"
        depends_on: [analyze]
"""

# Minimal v0.2 spec for backward compat testing
_VALID_V02_SPEC = """
version: "0.2"
contracts:
  Out:
    v: {type: string}
functions:
  work:
    mode: infer
    intent: "Produce output"
    input: {}
    output: Out
flows:
  f:
    input: {}
    output: Out
    steps:
      - id: s1
        function: work
        inputs: {}
"""


# ---------------------------------------------------------------------------
# 1. v0.3 schema validates decompose + parallel_dispatch steps
# ---------------------------------------------------------------------------

def test_v03_spec_parses():
    spec = parse_and_validate(_VALID_V03_SPEC)
    assert spec.version == "0.3"
    steps = {s.id: s for s in spec.flows["build"].steps}
    assert steps["analyze"].step_type == "decompose"
    assert steps["execute"].step_type == "parallel_dispatch"
    assert steps["execute"].max_concurrent == 3
    assert steps["execute"].isolation == "worktree"
    assert steps["execute"].require == "all"
    assert steps["execute"].merge == "sequential_apply"
    assert steps["execute"].source == "$.steps.analyze.output.tasks"


# ---------------------------------------------------------------------------
# 2. v0.2 specs still work (backward compatibility)
# ---------------------------------------------------------------------------

def test_v02_backward_compat():
    spec = parse_and_validate(_VALID_V02_SPEC)
    assert spec.version == "0.2"
    assert "work" in spec.functions


# ---------------------------------------------------------------------------
# 3-5. no_file_conflicts built-in ensure function
# ---------------------------------------------------------------------------

@pytest.fixture
def no_file_conflicts():
    return _ENSURE_BUILTINS["no_file_conflicts"]


def test_no_file_conflicts_disjoint_files(no_file_conflicts):
    """Passes when tasks have disjoint files_owned."""
    tasks = [
        {"id": "t1", "files_owned": ["a.py", "b.py"], "depends_on": []},
        {"id": "t2", "files_owned": ["c.py", "d.py"], "depends_on": []},
    ]
    assert no_file_conflicts(tasks) is True


def test_no_file_conflicts_overlap_fails(no_file_conflicts):
    """Fails when independent tasks share files_owned."""
    tasks = [
        {"id": "t1", "files_owned": ["shared.py", "a.py"], "depends_on": []},
        {"id": "t2", "files_owned": ["shared.py", "b.py"], "depends_on": []},
    ]
    with pytest.raises(ValueError, match="shared.py"):
        no_file_conflicts(tasks)


def test_no_file_conflicts_overlap_with_dependency(no_file_conflicts):
    """Passes when overlapping tasks have dependency edges."""
    tasks = [
        {"id": "t1", "files_owned": ["shared.py"], "depends_on": []},
        {"id": "t2", "files_owned": ["shared.py"], "depends_on": ["t1"]},
    ]
    assert no_file_conflicts(tasks) is True


def test_no_file_conflicts_read_overlap_allowed(no_file_conflicts):
    """Read-only overlap (files_read) is allowed between independent tasks."""
    tasks = [
        {"id": "t1", "files_owned": ["a.py"], "files_read": ["config.py"], "depends_on": []},
        {"id": "t2", "files_owned": ["b.py"], "files_read": ["config.py"], "depends_on": []},
    ]
    assert no_file_conflicts(tasks) is True


def test_no_file_conflicts_transitive_dependency(no_file_conflicts):
    """Passes when overlap exists but tasks are transitively dependent."""
    tasks = [
        {"id": "t1", "files_owned": ["shared.py"], "depends_on": []},
        {"id": "t2", "files_owned": ["other.py"], "depends_on": ["t1"]},
        {"id": "t3", "files_owned": ["shared.py"], "depends_on": ["t2"]},
    ]
    # t3 transitively depends on t1 via t2, so overlap is allowed
    assert no_file_conflicts(tasks) is True


# ---------------------------------------------------------------------------
# 6. Semantic validation: decompose requires output_contract
# ---------------------------------------------------------------------------

def test_decompose_requires_output_contract():
    ir = _VALID_V03_SPEC.replace(
        "        output_contract: TaskGraph\n",
        "",
    )
    with pytest.raises(IRSemanticError, match="output_contract"):
        parse_and_validate(ir)


def test_decompose_requires_agent():
    ir = _VALID_V03_SPEC.replace(
        "        agent: claude\n        intent: \"Analyze the plan and produce a TaskGraph\"\n",
        "        intent: \"Analyze the plan and produce a TaskGraph\"\n",
    )
    with pytest.raises(IRSemanticError, match="agent"):
        parse_and_validate(ir)


def test_decompose_requires_intent():
    ir = _VALID_V03_SPEC.replace(
        "        intent: \"Analyze the plan and produce a TaskGraph\"\n",
        "",
    )
    with pytest.raises(IRSemanticError, match="intent"):
        parse_and_validate(ir)


# ---------------------------------------------------------------------------
# 7. Semantic validation: parallel_dispatch requires source and intent_template
# ---------------------------------------------------------------------------

def test_parallel_dispatch_requires_source():
    ir = _VALID_V03_SPEC.replace(
        '        source: "$.steps.analyze.output.tasks"\n',
        "",
    )
    with pytest.raises(IRSemanticError, match="source"):
        parse_and_validate(ir)


def test_parallel_dispatch_requires_intent_template():
    ir = _VALID_V03_SPEC.replace(
        '        intent_template: "Implement: {task.description}"\n',
        "",
    )
    with pytest.raises(IRSemanticError, match="intent_template"):
        parse_and_validate(ir)


# ---------------------------------------------------------------------------
# 8. Semantic validation: parallel_dispatch fields forbidden on other step types
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("field,value", [
    ("source", '"$.steps.s1.output"'),
    ("isolation", "worktree"),
    ("require", "all"),
    ("merge", "sequential_apply"),
])
def test_parallel_dispatch_fields_forbidden_on_function_step(field, value):
    ir = f"""
version: "0.3"
contracts:
  Out:
    v: {{type: string}}
functions:
  work:
    mode: infer
    intent: "Produce output"
    input: {{}}
    output: Out
flows:
  f:
    input: {{}}
    output: Out
    steps:
      - id: s1
        function: work
        inputs: {{}}
        {field}: {value}
"""
    with pytest.raises(IRSemanticError, match=field):
        parse_and_validate(ir)


# ---------------------------------------------------------------------------
# 9. Semantic validation: intent_template forbidden on non-parallel_dispatch steps
# ---------------------------------------------------------------------------

def test_intent_template_forbidden_on_function_step():
    ir = """
version: "0.3"
contracts:
  Out:
    v: {type: string}
functions:
  work:
    mode: infer
    intent: "Produce output"
    input: {}
    output: Out
flows:
  f:
    input: {}
    output: Out
    steps:
      - id: s1
        function: work
        inputs: {}
        intent_template: "some template"
"""
    with pytest.raises(IRSemanticError, match="intent_template"):
        parse_and_validate(ir)


def test_intent_template_forbidden_on_decompose_step():
    ir = """
version: "0.3"
contracts:
  TaskGraph:
    tasks: {type: array}
flows:
  f:
    input: {}
    steps:
      - id: analyze
        type: decompose
        agent: claude
        intent: "Analyze"
        output_contract: TaskGraph
        intent_template: "some template"
"""
    with pytest.raises(IRSemanticError, match="intent_template"):
        parse_and_validate(ir)


# ---------------------------------------------------------------------------
# max_concurrent defaults to 3
# ---------------------------------------------------------------------------

def test_max_concurrent_defaults_to_3():
    ir = _VALID_V03_SPEC.replace(
        "        max_concurrent: 3\n",
        "",
    )
    spec = parse_and_validate(ir)
    execute_step = next(s for s in spec.flows["build"].steps if s.id == "execute")
    assert execute_step.max_concurrent == 3


# ---------------------------------------------------------------------------
# _step_mode handles new types
# ---------------------------------------------------------------------------

def test_step_mode_decompose():
    from stratum_mcp.executor import _step_mode
    spec = parse_and_validate(_VALID_V03_SPEC)
    steps = {s.id: s for s in spec.flows["build"].steps}
    assert _step_mode(steps["analyze"]) == "decompose"
    assert _step_mode(steps["execute"]) == "parallel_dispatch"
    assert _step_mode(steps["do_work"]) == "function"
