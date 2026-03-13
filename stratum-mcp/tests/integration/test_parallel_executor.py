"""Integration tests for parallel executor (T2-PAR-2 / T2-PAR-3)."""
import asyncio
import textwrap

import pytest

from stratum_mcp.executor import (
    _step_mode,
    create_flow_state,
    get_current_step_info,
    process_step_result,
    _flows,
)
from stratum_mcp.server import stratum_plan, stratum_step_done, stratum_parallel_done
from stratum_mcp.spec import parse_and_validate


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


# ---------------------------------------------------------------------------
# Spec fixtures
# ---------------------------------------------------------------------------

_V03_DECOMPOSE_PARALLEL = textwrap.dedent("""\
    version: "0.3"
    contracts:
      TaskGraph:
        tasks: {type: array}
      Result:
        outcome: {type: string}
    functions:
      prep:
        mode: infer
        intent: "Prepare input"
        input: {}
        output: Result
    flows:
      main:
        input: {plan: {type: string}}
        steps:
          - id: prepare
            function: prep
            inputs: {plan: "$.input.plan"}
          - id: analyze
            type: decompose
            agent: claude
            intent: "Break down into tasks"
            output_contract: TaskGraph
            ensure:
              - "no_file_conflicts(result.tasks)"
            retries: 3
            depends_on: [prepare]
          - id: execute
            type: parallel_dispatch
            source: "$.steps.analyze.output.tasks"
            agent: claude
            max_concurrent: 2
            isolation: worktree
            require: all
            merge: sequential_apply
            intent_template: "Do: {task.desc}"
            depends_on: [analyze]
""")

_V03_REQUIRE_ANY = textwrap.dedent("""\
    version: "0.3"
    contracts:
      TaskGraph:
        tasks: {type: array}
    flows:
      main:
        input: {}
        steps:
          - id: analyze
            type: decompose
            agent: claude
            intent: "Break down"
            output_contract: TaskGraph
          - id: execute
            type: parallel_dispatch
            source: "$.steps.analyze.output.tasks"
            agent: claude
            require: any
            intent_template: "Do: {task.desc}"
            depends_on: [analyze]
""")

_V03_REQUIRE_N = textwrap.dedent("""\
    version: "0.3"
    contracts:
      TaskGraph:
        tasks: {type: array}
    flows:
      main:
        input: {}
        steps:
          - id: analyze
            type: decompose
            agent: claude
            intent: "Break down"
            output_contract: TaskGraph
          - id: execute
            type: parallel_dispatch
            source: "$.steps.analyze.output.tasks"
            agent: claude
            require: 2
            intent_template: "Do: {task.desc}"
            depends_on: [analyze]
""")


# ---------------------------------------------------------------------------
# 1. decompose step dispatches as execute_step with mode "decompose"
# ---------------------------------------------------------------------------

def test_decompose_step_dispatches_as_execute_step():
    spec = parse_and_validate(_V03_DECOMPOSE_PARALLEL)
    state = create_flow_state(spec, "main", {"plan": "build it"}, _V03_DECOMPOSE_PARALLEL)

    # First step is a function step
    info = get_current_step_info(state)
    assert info["step_mode"] == "function"
    assert info["step_id"] == "prepare"

    # Complete the function step
    process_step_result(state, "prepare", {"outcome": "ready"})

    # Now the decompose step
    info = get_current_step_info(state)
    assert info["status"] == "execute_step"
    assert info["step_mode"] == "decompose"
    assert info["step_id"] == "analyze"
    assert info["intent"] == "Break down into tasks"
    assert info["agent"] == "claude"
    assert info["output_contract"] == "TaskGraph"
    assert "tasks" in info["output_fields"]
    assert info["ensure"] == ["no_file_conflicts(result.tasks)"]
    assert info["retries_remaining"] == 3
    assert info["inputs"] == {}  # decompose step has no explicit inputs


# ---------------------------------------------------------------------------
# 2. parallel_dispatch step returns parallel_dispatch status
# ---------------------------------------------------------------------------

def test_parallel_dispatch_returns_dispatch_status():
    spec = parse_and_validate(_V03_DECOMPOSE_PARALLEL)
    state = create_flow_state(spec, "main", {"plan": "build it"}, _V03_DECOMPOSE_PARALLEL)

    # Complete prepare
    get_current_step_info(state)
    process_step_result(state, "prepare", {"outcome": "ready"})

    # Complete analyze (decompose) with a task graph
    get_current_step_info(state)
    task_graph = {
        "tasks": [
            {"id": "t1", "desc": "task 1", "files_owned": ["a.py"], "depends_on": []},
            {"id": "t2", "desc": "task 2", "files_owned": ["b.py"], "depends_on": []},
        ]
    }
    process_step_result(state, "analyze", task_graph)

    # Now the parallel_dispatch step
    info = get_current_step_info(state)
    assert info["status"] == "parallel_dispatch"
    assert info["step_mode"] == "parallel_dispatch"
    assert info["step_id"] == "execute"
    assert info["tasks"] == task_graph["tasks"]
    assert info["agent"] == "claude"
    assert info["max_concurrent"] == 2
    assert info["isolation"] == "worktree"
    assert info["require"] == "all"
    assert info["merge"] == "sequential_apply"
    assert info["intent_template"] == "Do: {task.desc}"


# ---------------------------------------------------------------------------
# 3. decompose result flows through process_step_result
# ---------------------------------------------------------------------------

def test_decompose_result_through_process_step_result():
    spec = parse_and_validate(_V03_DECOMPOSE_PARALLEL)
    state = create_flow_state(spec, "main", {"plan": "build it"}, _V03_DECOMPOSE_PARALLEL)

    # Complete prepare
    get_current_step_info(state)
    process_step_result(state, "prepare", {"outcome": "ready"})

    # Decompose step with valid task graph (no file conflicts)
    get_current_step_info(state)
    task_graph = {
        "tasks": [
            {"id": "t1", "desc": "task 1", "files_owned": ["a.py"], "depends_on": []},
            {"id": "t2", "desc": "task 2", "files_owned": ["b.py"], "depends_on": []},
        ]
    }
    status, violations = process_step_result(state, "analyze", task_graph)
    assert status == "ok"
    assert violations == []
    assert state.step_outputs["analyze"] == task_graph


def test_decompose_ensure_failure_retries():
    """Decompose steps get 2 retries by default (not 1 like inline)."""
    spec = parse_and_validate(_V03_DECOMPOSE_PARALLEL)
    state = create_flow_state(spec, "main", {"plan": "build it"}, _V03_DECOMPOSE_PARALLEL)

    # Complete prepare
    get_current_step_info(state)
    process_step_result(state, "prepare", {"outcome": "ready"})

    # Decompose step with file conflicts — ensure fails
    get_current_step_info(state)
    bad_graph = {
        "tasks": [
            {"id": "t1", "files_owned": ["shared.py"], "depends_on": []},
            {"id": "t2", "files_owned": ["shared.py"], "depends_on": []},
        ]
    }
    status, violations = process_step_result(state, "analyze", bad_graph)
    assert status == "ensure_failed"
    assert len(violations) > 0

    # Should still have retries (3 total, 1 used)
    info = get_current_step_info(state)
    assert info["retries_remaining"] == 2


# ---------------------------------------------------------------------------
# 4. stratum_parallel_done advances flow on success
# ---------------------------------------------------------------------------

def test_parallel_done_advances_flow_on_success():
    result = _run(stratum_plan(
        spec=_V03_DECOMPOSE_PARALLEL, flow="main",
        inputs={"plan": "build it"}, ctx=None,
    ))
    flow_id = result["flow_id"]

    try:
        # Complete prepare (function step)
        result = _run(stratum_step_done(flow_id, "prepare", {"outcome": "ready"}, ctx=None))
        assert result["step_id"] == "analyze"

        # Complete analyze (decompose step)
        task_graph = {
            "tasks": [
                {"id": "t1", "desc": "task 1", "files_owned": ["a.py"], "depends_on": []},
                {"id": "t2", "desc": "task 2", "files_owned": ["b.py"], "depends_on": []},
            ]
        }
        result = _run(stratum_step_done(flow_id, "analyze", task_graph, ctx=None))
        assert result["step_id"] == "execute"
        assert result["status"] == "parallel_dispatch"

        # Complete parallel_dispatch via stratum_parallel_done
        task_results = [
            {"task_id": "t1", "result": {"ok": True}, "status": "complete"},
            {"task_id": "t2", "result": {"ok": True}, "status": "complete"},
        ]
        result = _run(stratum_parallel_done(
            flow_id=flow_id, step_id="execute",
            task_results=task_results, merge_status="clean", ctx=None,
        ))
        assert result["status"] == "complete"
    finally:
        _flows.pop(flow_id, None)


# ---------------------------------------------------------------------------
# 5. stratum_parallel_done fails on merge conflict
# ---------------------------------------------------------------------------

def test_parallel_done_fails_on_merge_conflict():
    result = _run(stratum_plan(
        spec=_V03_DECOMPOSE_PARALLEL, flow="main",
        inputs={"plan": "build it"}, ctx=None,
    ))
    flow_id = result["flow_id"]

    try:
        # Complete prepare and analyze
        _run(stratum_step_done(flow_id, "prepare", {"outcome": "ready"}, ctx=None))
        task_graph = {
            "tasks": [
                {"id": "t1", "files_owned": ["a.py"], "depends_on": []},
                {"id": "t2", "files_owned": ["b.py"], "depends_on": []},
            ]
        }
        _run(stratum_step_done(flow_id, "analyze", task_graph, ctx=None))

        # parallel_done with merge conflict
        task_results = [
            {"task_id": "t1", "result": {"ok": True}, "status": "complete"},
            {"task_id": "t2", "result": {"ok": True}, "status": "complete"},
        ]
        result = _run(stratum_parallel_done(
            flow_id=flow_id, step_id="execute",
            task_results=task_results, merge_status="conflict", ctx=None,
        ))
        # Should be an ensure_failed or error due to merge conflict
        assert result["status"] in ("ensure_failed", "error")
        assert any("conflict" in str(v).lower() for v in result.get("violations", []))
    finally:
        _flows.pop(flow_id, None)


# ---------------------------------------------------------------------------
# 6. stratum_parallel_done respects require="all"
# ---------------------------------------------------------------------------

def test_parallel_done_require_all_fails_on_incomplete():
    result = _run(stratum_plan(
        spec=_V03_DECOMPOSE_PARALLEL, flow="main",
        inputs={"plan": "build it"}, ctx=None,
    ))
    flow_id = result["flow_id"]

    try:
        _run(stratum_step_done(flow_id, "prepare", {"outcome": "ready"}, ctx=None))
        task_graph = {
            "tasks": [
                {"id": "t1", "files_owned": ["a.py"], "depends_on": []},
                {"id": "t2", "files_owned": ["b.py"], "depends_on": []},
            ]
        }
        _run(stratum_step_done(flow_id, "analyze", task_graph, ctx=None))

        # One task failed
        task_results = [
            {"task_id": "t1", "result": {"ok": True}, "status": "complete"},
            {"task_id": "t2", "result": {"error": "boom"}, "status": "failed"},
        ]
        result = _run(stratum_parallel_done(
            flow_id=flow_id, step_id="execute",
            task_results=task_results, merge_status="clean", ctx=None,
        ))
        assert result["status"] in ("ensure_failed", "error")
        assert any("require" in str(v).lower() or "satisfied" in str(v).lower()
                    for v in result.get("violations", []))
    finally:
        _flows.pop(flow_id, None)


# ---------------------------------------------------------------------------
# 7. stratum_parallel_done respects require="any"
# ---------------------------------------------------------------------------

def test_parallel_done_require_any_succeeds_with_one():
    result = _run(stratum_plan(
        spec=_V03_REQUIRE_ANY, flow="main", inputs={}, ctx=None,
    ))
    flow_id = result["flow_id"]

    try:
        # Complete analyze (decompose)
        task_graph = {
            "tasks": [
                {"id": "t1", "desc": "task 1", "files_owned": ["a.py"], "depends_on": []},
                {"id": "t2", "desc": "task 2", "files_owned": ["b.py"], "depends_on": []},
            ]
        }
        _run(stratum_step_done(flow_id, "analyze", task_graph, ctx=None))

        # One task passed, one failed — require=any should succeed
        task_results = [
            {"task_id": "t1", "result": {"ok": True}, "status": "complete"},
            {"task_id": "t2", "result": {"error": "boom"}, "status": "failed"},
        ]
        result = _run(stratum_parallel_done(
            flow_id=flow_id, step_id="execute",
            task_results=task_results, merge_status="clean", ctx=None,
        ))
        assert result["status"] == "complete"
    finally:
        _flows.pop(flow_id, None)


# ---------------------------------------------------------------------------
# 8. stratum_parallel_done respects require=N
# ---------------------------------------------------------------------------

def test_parallel_done_require_n_passes_when_met():
    result = _run(stratum_plan(
        spec=_V03_REQUIRE_N, flow="main", inputs={}, ctx=None,
    ))
    flow_id = result["flow_id"]

    try:
        task_graph = {
            "tasks": [
                {"id": "t1", "desc": "t1", "files_owned": ["a.py"], "depends_on": []},
                {"id": "t2", "desc": "t2", "files_owned": ["b.py"], "depends_on": []},
                {"id": "t3", "desc": "t3", "files_owned": ["c.py"], "depends_on": []},
            ]
        }
        _run(stratum_step_done(flow_id, "analyze", task_graph, ctx=None))

        # 2 passed, 1 failed — require=2 should succeed
        task_results = [
            {"task_id": "t1", "result": {"ok": True}, "status": "complete"},
            {"task_id": "t2", "result": {"ok": True}, "status": "complete"},
            {"task_id": "t3", "result": {"error": "boom"}, "status": "failed"},
        ]
        result = _run(stratum_parallel_done(
            flow_id=flow_id, step_id="execute",
            task_results=task_results, merge_status="clean", ctx=None,
        ))
        assert result["status"] == "complete"
    finally:
        _flows.pop(flow_id, None)


def test_parallel_done_require_n_fails_when_not_met():
    result = _run(stratum_plan(
        spec=_V03_REQUIRE_N, flow="main", inputs={}, ctx=None,
    ))
    flow_id = result["flow_id"]

    try:
        task_graph = {
            "tasks": [
                {"id": "t1", "desc": "t1", "files_owned": ["a.py"], "depends_on": []},
                {"id": "t2", "desc": "t2", "files_owned": ["b.py"], "depends_on": []},
                {"id": "t3", "desc": "t3", "files_owned": ["c.py"], "depends_on": []},
            ]
        }
        _run(stratum_step_done(flow_id, "analyze", task_graph, ctx=None))

        # Only 1 passed — require=2 should fail
        task_results = [
            {"task_id": "t1", "result": {"ok": True}, "status": "complete"},
            {"task_id": "t2", "result": {"error": "boom"}, "status": "failed"},
            {"task_id": "t3", "result": {"error": "boom"}, "status": "failed"},
        ]
        result = _run(stratum_parallel_done(
            flow_id=flow_id, step_id="execute",
            task_results=task_results, merge_status="clean", ctx=None,
        ))
        assert result["status"] in ("ensure_failed", "error")
    finally:
        _flows.pop(flow_id, None)
