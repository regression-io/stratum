"""Integration tests for per-step iteration (STRAT-ENG-4).

Covers:
  - Start iteration, report results, exit on criterion met
  - Exit on max_iterations reached
  - Abort active iteration
  - Iteration data in stratum_audit output
  - Iteration history archived on gate revise
  - Persistence and checkpoint restore of iteration state
  - iteration_outcome lifecycle
  - Error paths: no max_iterations, double start, no active loop, gate step, post-exit report
"""
import asyncio
import textwrap

import pytest

from stratum_mcp.errors import MCPExecutionError
from stratum_mcp.executor import (
    _flows,
    create_flow_state,
    get_current_step_info,
    process_step_result,
    start_iteration,
    report_iteration,
    abort_iteration,
    resolve_gate,
    persist_flow,
    restore_flow,
    delete_persisted_flow,
    commit_checkpoint,
    revert_checkpoint,
)
from stratum_mcp.server import (
    stratum_plan,
    stratum_step_done,
    stratum_iteration_start,
    stratum_iteration_report,
    stratum_iteration_abort,
    stratum_gate_resolve,
    stratum_audit,
)
from stratum_mcp.spec import parse_and_validate


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


# ---------------------------------------------------------------------------
# Spec fixtures
# ---------------------------------------------------------------------------

_ITER_SPEC = textwrap.dedent("""\
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
      gate_fn:
        mode: gate
    flows:
      main:
        max_rounds: 5
        input: {}
        output: Out
        steps:
          - id: s1
            function: work
            inputs: {}
            max_iterations: 3
            exit_criterion: "result.v == 'done'"
          - id: g1
            function: gate_fn
            on_approve: ~
            on_revise: s1
            on_kill: ~
""")

_INLINE_ITER_SPEC = textwrap.dedent("""\
    version: "0.2"
    flows:
      main:
        input: {}
        steps:
          - id: review
            agent: codex
            intent: "Review. Return {clean: boolean}."
            max_iterations: 5
            exit_criterion: "result.clean == True"
            ensure:
              - "result.clean is not None"
""")


@pytest.fixture(autouse=True)
def _cleanup():
    _flows.clear()
    yield
    _flows.clear()


# ---------------------------------------------------------------------------
# Happy path: start → report → exit_success
# ---------------------------------------------------------------------------

def test_iteration_start_and_exit_success():
    spec = parse_and_validate(_ITER_SPEC)
    state = create_flow_state(spec, "main", {}, raw_spec=_ITER_SPEC)
    _flows[state.flow_id] = state

    step_info = get_current_step_info(state)
    assert step_info["step_id"] == "s1"

    # Start iteration
    result = start_iteration(state, "s1")
    assert result["status"] == "iteration_started"
    assert result["max_iterations"] == 3
    assert state.active_iteration is not None
    assert state.active_iteration["count"] == 0

    # Report 1: criterion not met
    r1 = report_iteration(state, "s1", {"v": "wip"})
    assert r1["status"] == "iteration_continue"
    assert r1["outcome"] == "continue"
    assert r1["iteration"] == 1
    assert not r1["exit_criterion_met"]

    # Report 2: criterion met
    r2 = report_iteration(state, "s1", {"v": "done"})
    assert r2["status"] == "iteration_exit"
    assert r2["outcome"] == "exit_success"
    assert r2["exit_criterion_met"]
    assert state.active_iteration is None
    assert state.iteration_outcome["s1"] == "exit_success"

    # History recorded
    assert len(state.iterations["s1"]) == 2


def test_iteration_exit_max():
    spec = parse_and_validate(_ITER_SPEC)
    state = create_flow_state(spec, "main", {}, raw_spec=_ITER_SPEC)
    _flows[state.flow_id] = state
    get_current_step_info(state)

    start_iteration(state, "s1")
    for i in range(2):
        r = report_iteration(state, "s1", {"v": "wip"})
        assert r["outcome"] == "continue"

    # 3rd report hits max
    r3 = report_iteration(state, "s1", {"v": "still_wip"})
    assert r3["outcome"] == "exit_max"
    assert r3["status"] == "iteration_exit"
    assert state.active_iteration is None
    assert state.iteration_outcome["s1"] == "exit_max"
    assert len(state.iterations["s1"]) == 3


def test_iteration_abort():
    spec = parse_and_validate(_ITER_SPEC)
    state = create_flow_state(spec, "main", {}, raw_spec=_ITER_SPEC)
    _flows[state.flow_id] = state
    get_current_step_info(state)

    start_iteration(state, "s1")
    report_iteration(state, "s1", {"v": "wip"})

    result = abort_iteration(state, "s1", "giving up")
    assert result["status"] == "iteration_aborted"
    assert state.active_iteration is None
    assert state.iteration_outcome["s1"] == "exit_abort"
    assert len(state.iterations["s1"]) == 2  # 1 report + 1 abort

def test_iteration_abort_at_count_zero():
    """Abort immediately after start, before any report."""
    spec = parse_and_validate(_ITER_SPEC)
    state = create_flow_state(spec, "main", {}, raw_spec=_ITER_SPEC)
    _flows[state.flow_id] = state
    get_current_step_info(state)

    start_iteration(state, "s1")
    result = abort_iteration(state, "s1", "changed mind")
    assert result["status"] == "iteration_aborted"
    assert result["iteration"] == 0
    assert state.active_iteration is None
    assert state.iteration_outcome["s1"] == "exit_abort"
    assert len(state.iterations["s1"]) == 1  # just the abort entry


# ---------------------------------------------------------------------------
# Audit output
# ---------------------------------------------------------------------------

def test_iteration_audit_output():
    spec = parse_and_validate(_ITER_SPEC)
    state = create_flow_state(spec, "main", {}, raw_spec=_ITER_SPEC)
    _flows[state.flow_id] = state
    get_current_step_info(state)

    start_iteration(state, "s1")
    report_iteration(state, "s1", {"v": "done"})

    audit = _run(stratum_audit(state.flow_id, None))
    assert "iterations" in audit
    assert "s1" in audit["iterations"]
    assert len(audit["iterations"]["s1"]) == 1
    assert audit["iterations"]["s1"][0]["outcome"] == "exit_success"
    assert "archived_iterations" in audit
    assert audit["archived_iterations"] == []


def test_iteration_audit_strips_result_payloads():
    """Audit output must not contain full result dicts (compact contract)."""
    spec = parse_and_validate(_ITER_SPEC)
    state = create_flow_state(spec, "main", {}, raw_spec=_ITER_SPEC)
    _flows[state.flow_id] = state
    get_current_step_info(state)

    start_iteration(state, "s1")
    report_iteration(state, "s1", {"v": "sensitive_data"})
    report_iteration(state, "s1", {"v": "done"})

    audit = _run(stratum_audit(state.flow_id, None))
    for entry in audit["iterations"]["s1"]:
        assert "result" not in entry

    # Verify result is still in internal state (not destroyed)
    assert state.iterations["s1"][0]["result"] == {"v": "sensitive_data"}


# ---------------------------------------------------------------------------
# Revise: iteration history archived
# ---------------------------------------------------------------------------

def test_iteration_archived_on_revise():
    spec = parse_and_validate(_ITER_SPEC)
    state = create_flow_state(spec, "main", {}, raw_spec=_ITER_SPEC)
    _flows[state.flow_id] = state

    # Execute s1 with iteration
    get_current_step_info(state)
    start_iteration(state, "s1")
    report_iteration(state, "s1", {"v": "done"})
    process_step_result(state, "s1", {"v": "done"})

    # Now at gate g1 — revise back to s1
    step_info = get_current_step_info(state)
    assert step_info["status"] == "await_gate"
    status, _ = resolve_gate(state, "g1", "revise", "needs work", "human")
    assert status == "execute_step"

    # Verify iteration data archived
    assert len(state.archived_iterations) == 1
    assert "s1" in state.archived_iterations[0]
    assert len(state.archived_iterations[0]["s1"]) == 1

    # Active iterations cleared
    assert state.iterations == {}
    assert state.active_iteration is None


def test_iteration_audit_shows_archived():
    spec = parse_and_validate(_ITER_SPEC)
    state = create_flow_state(spec, "main", {}, raw_spec=_ITER_SPEC)
    _flows[state.flow_id] = state

    # Round 0: execute with iteration, then revise
    get_current_step_info(state)
    start_iteration(state, "s1")
    report_iteration(state, "s1", {"v": "done"})
    process_step_result(state, "s1", {"v": "done"})
    get_current_step_info(state)
    resolve_gate(state, "g1", "revise", "redo", "human")

    audit = _run(stratum_audit(state.flow_id, None))
    assert len(audit["archived_iterations"]) == 1
    assert "s1" in audit["archived_iterations"][0]


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def test_iteration_persistence():
    spec = parse_and_validate(_ITER_SPEC)
    state = create_flow_state(spec, "main", {}, raw_spec=_ITER_SPEC)
    _flows[state.flow_id] = state
    get_current_step_info(state)

    start_iteration(state, "s1")
    report_iteration(state, "s1", {"v": "wip"})

    # Persist and restore
    flow_id = state.flow_id
    persist_flow(state)
    del _flows[flow_id]

    restored = restore_flow(flow_id)
    assert restored is not None
    assert restored.active_iteration is not None
    assert restored.active_iteration["step_id"] == "s1"
    assert restored.active_iteration["count"] == 1
    assert len(restored.iterations["s1"]) == 1

    # Can continue iteration after restore
    r = report_iteration(restored, "s1", {"v": "done"})
    assert r["outcome"] == "exit_success"

    delete_persisted_flow(flow_id)


def test_iteration_checkpoint_revert():
    spec = parse_and_validate(_ITER_SPEC)
    state = create_flow_state(spec, "main", {}, raw_spec=_ITER_SPEC)
    _flows[state.flow_id] = state
    get_current_step_info(state)

    start_iteration(state, "s1")
    report_iteration(state, "s1", {"v": "wip"})

    # Checkpoint after 1 iteration
    commit_checkpoint(state, "after_iter_1")

    # Do another iteration
    report_iteration(state, "s1", {"v": "done"})
    assert state.active_iteration is None
    assert len(state.iterations["s1"]) == 2

    # Revert to checkpoint
    assert revert_checkpoint(state, "after_iter_1")
    assert state.active_iteration is not None
    assert state.active_iteration["count"] == 1
    assert len(state.iterations["s1"]) == 1

    delete_persisted_flow(state.flow_id)


# ---------------------------------------------------------------------------
# iteration_outcome lifecycle
# ---------------------------------------------------------------------------

def test_iteration_outcome_persists_until_step_done():
    spec = parse_and_validate(_ITER_SPEC)
    state = create_flow_state(spec, "main", {}, raw_spec=_ITER_SPEC)
    _flows[state.flow_id] = state
    get_current_step_info(state)

    start_iteration(state, "s1")
    report_iteration(state, "s1", {"v": "done"})

    # Outcome is set
    assert state.iteration_outcome["s1"] == "exit_success"

    # step_done consumes it
    result = _run(stratum_step_done(state.flow_id, "s1", {"v": "done"}, None))
    assert result["status"] != "error"
    assert "s1" not in state.iteration_outcome


def test_iteration_outcome_cleared_on_revise():
    spec = parse_and_validate(_ITER_SPEC)
    state = create_flow_state(spec, "main", {}, raw_spec=_ITER_SPEC)
    _flows[state.flow_id] = state

    get_current_step_info(state)
    start_iteration(state, "s1")
    report_iteration(state, "s1", {"v": "done"})
    assert "s1" in state.iteration_outcome

    process_step_result(state, "s1", {"v": "done"})
    # Don't consume via step_done — manually set outcome to test revise clearing
    state.iteration_outcome["s1"] = "exit_success"

    get_current_step_info(state)
    resolve_gate(state, "g1", "revise", "redo", "human")

    assert "s1" not in state.iteration_outcome


# ---------------------------------------------------------------------------
# MCP tool integration
# ---------------------------------------------------------------------------

def test_mcp_iteration_tools_roundtrip():
    """Full MCP tool roundtrip: plan → iteration_start → report → step_done."""
    plan_result = _run(stratum_plan(_ITER_SPEC, "main", {}, None))
    flow_id = plan_result["flow_id"]

    start = _run(stratum_iteration_start(flow_id, "s1", None))
    assert start["status"] == "iteration_started"

    r1 = _run(stratum_iteration_report(flow_id, "s1", {"v": "wip"}, None))
    assert r1["outcome"] == "continue"

    r2 = _run(stratum_iteration_report(flow_id, "s1", {"v": "done"}, None))
    assert r2["outcome"] == "exit_success"

    done = _run(stratum_step_done(flow_id, "s1", {"v": "done"}, None))
    assert done["status"] == "await_gate"


def test_mcp_iteration_abort_tool():
    plan_result = _run(stratum_plan(_ITER_SPEC, "main", {}, None))
    flow_id = plan_result["flow_id"]

    _run(stratum_iteration_start(flow_id, "s1", None))
    result = _run(stratum_iteration_abort(flow_id, "s1", "user cancelled", None))
    assert result["status"] == "iteration_aborted"


# ---------------------------------------------------------------------------
# Error paths
# ---------------------------------------------------------------------------

def test_iteration_start_no_max_iterations():
    """Step without max_iterations — cannot start iteration."""
    spec_no_iter = textwrap.dedent("""\
        version: "0.2"
        contracts:
          Out:
            v: {type: string}
        functions:
          work:
            mode: infer
            intent: "Do it"
            input: {}
            output: Out
        flows:
          main:
            input: {}
            output: Out
            steps:
              - id: s1
                function: work
                inputs: {}
    """)
    spec = parse_and_validate(spec_no_iter)
    state = create_flow_state(spec, "main", {}, raw_spec=spec_no_iter)
    get_current_step_info(state)

    with pytest.raises(MCPExecutionError, match="max_iterations"):
        start_iteration(state, "s1")


def test_iteration_start_already_active():
    spec = parse_and_validate(_ITER_SPEC)
    state = create_flow_state(spec, "main", {}, raw_spec=_ITER_SPEC)
    get_current_step_info(state)

    start_iteration(state, "s1")
    with pytest.raises(MCPExecutionError, match="already active"):
        start_iteration(state, "s1")


def test_iteration_report_no_active():
    spec = parse_and_validate(_ITER_SPEC)
    state = create_flow_state(spec, "main", {}, raw_spec=_ITER_SPEC)
    get_current_step_info(state)

    with pytest.raises(MCPExecutionError, match="No active iteration"):
        report_iteration(state, "s1", {"v": "wip"})


def test_iteration_start_gate_step():
    spec = parse_and_validate(_ITER_SPEC)
    state = create_flow_state(spec, "main", {}, raw_spec=_ITER_SPEC)
    get_current_step_info(state)

    # Advance past s1 to gate step g1
    process_step_result(state, "s1", {"v": "done"})
    step_info = get_current_step_info(state)
    assert step_info["step_id"] == "g1"

    with pytest.raises(MCPExecutionError, match="gate step"):
        start_iteration(state, "g1")


def test_iteration_report_after_exit():
    spec = parse_and_validate(_ITER_SPEC)
    state = create_flow_state(spec, "main", {}, raw_spec=_ITER_SPEC)
    get_current_step_info(state)

    start_iteration(state, "s1")
    report_iteration(state, "s1", {"v": "done"})  # exits

    with pytest.raises(MCPExecutionError, match="No active iteration"):
        report_iteration(state, "s1", {"v": "more"})


def test_iteration_restart_blocked_before_step_done():
    """Cannot start a new iteration loop while iteration_outcome is pending."""
    spec = parse_and_validate(_ITER_SPEC)
    state = create_flow_state(spec, "main", {}, raw_spec=_ITER_SPEC)
    get_current_step_info(state)

    start_iteration(state, "s1")
    report_iteration(state, "s1", {"v": "done"})  # exits with exit_success
    assert state.iteration_outcome["s1"] == "exit_success"

    with pytest.raises(MCPExecutionError, match="pending iteration outcome"):
        start_iteration(state, "s1")


def test_iteration_restart_blocked_after_exit_max():
    """Same guard applies after exit_max."""
    spec = parse_and_validate(_ITER_SPEC)
    state = create_flow_state(spec, "main", {}, raw_spec=_ITER_SPEC)
    get_current_step_info(state)

    start_iteration(state, "s1")
    for _ in range(3):
        report_iteration(state, "s1", {"v": "wip"})
    assert state.iteration_outcome["s1"] == "exit_max"

    with pytest.raises(MCPExecutionError, match="pending iteration outcome"):
        start_iteration(state, "s1")


def test_iteration_report_wrong_step_id():
    """Report for a different step_id than the active iteration."""
    spec = parse_and_validate(_ITER_SPEC)
    state = create_flow_state(spec, "main", {}, raw_spec=_ITER_SPEC)
    get_current_step_info(state)

    start_iteration(state, "s1")
    with pytest.raises(MCPExecutionError, match="Active iteration is on step"):
        report_iteration(state, "s1_wrong", {"v": "wip"})


def test_iteration_abort_wrong_step_id():
    """Abort for a different step_id than the active iteration."""
    spec = parse_and_validate(_ITER_SPEC)
    state = create_flow_state(spec, "main", {}, raw_spec=_ITER_SPEC)
    get_current_step_info(state)

    start_iteration(state, "s1")
    with pytest.raises(MCPExecutionError, match="Active iteration is on step"):
        abort_iteration(state, "s1_wrong", "wrong target")


def test_iteration_start_on_completed_flow():
    """Cannot start iteration after flow has completed."""
    spec = parse_and_validate(_ITER_SPEC)
    state = create_flow_state(spec, "main", {}, raw_spec=_ITER_SPEC)
    _flows[state.flow_id] = state

    # Complete the flow
    get_current_step_info(state)
    process_step_result(state, "s1", {"v": "done"})
    get_current_step_info(state)
    resolve_gate(state, "g1", "approve", None, "human")

    with pytest.raises(MCPExecutionError, match="already complete"):
        start_iteration(state, "s1")


def test_iteration_no_exit_criterion():
    """Step with max_iterations but no exit_criterion — always runs to max."""
    no_crit_spec = textwrap.dedent("""\
        version: "0.2"
        contracts:
          Out:
            v: {type: string}
        functions:
          work:
            mode: infer
            intent: "Do it"
            input: {}
            output: Out
        flows:
          main:
            input: {}
            output: Out
            steps:
              - id: s1
                function: work
                inputs: {}
                max_iterations: 2
    """)
    spec = parse_and_validate(no_crit_spec)
    state = create_flow_state(spec, "main", {}, raw_spec=no_crit_spec)
    get_current_step_info(state)

    start_iteration(state, "s1")
    r1 = report_iteration(state, "s1", {"v": "anything"})
    assert r1["outcome"] == "continue"
    assert not r1["exit_criterion_met"]

    r2 = report_iteration(state, "s1", {"v": "anything"})
    assert r2["outcome"] == "exit_max"


def test_iteration_exit_criterion_compile_error():
    """Bad exit_criterion expression surfaces error but doesn't crash."""
    # Dunder is blocked at parse time — test with a runtime error instead
    runtime_err_spec = textwrap.dedent("""\
        version: "0.2"
        contracts:
          Out:
            v: {type: string}
        functions:
          work:
            mode: infer
            intent: "Do it"
            input: {}
            output: Out
        flows:
          main:
            input: {}
            output: Out
            steps:
              - id: s1
                function: work
                inputs: {}
                max_iterations: 3
                exit_criterion: "result.nonexistent.deeply.nested == true"
    """)
    spec = parse_and_validate(runtime_err_spec)
    state = create_flow_state(spec, "main", {}, raw_spec=runtime_err_spec)
    get_current_step_info(state)

    start_iteration(state, "s1")
    # Should not crash — exit_criterion_met should be False
    r = report_iteration(state, "s1", {"v": "hello"})
    assert r["outcome"] == "continue"
    assert not r["exit_criterion_met"]


def test_inline_spec_iteration():
    """Inline step spec (agent field, no function) supports iteration."""
    spec = parse_and_validate(_INLINE_ITER_SPEC)
    state = create_flow_state(spec, "main", {}, raw_spec=_INLINE_ITER_SPEC)
    get_current_step_info(state)

    start_iteration(state, "review")
    r1 = report_iteration(state, "review", {"clean": False})
    assert r1["outcome"] == "continue"

    r2 = report_iteration(state, "review", {"clean": True})
    assert r2["outcome"] == "exit_success"
