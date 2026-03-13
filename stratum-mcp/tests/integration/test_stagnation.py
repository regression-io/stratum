"""Integration tests for iteration stagnation detection.

When an iteration loop produces identical results N consecutive times
(default: 3), the loop exits early with outcome 'exit_stagnation' instead
of burning remaining iterations on identical failures.
"""
import textwrap

import pytest

from stratum_mcp.executor import (
    _flows,
    _STAGNATION_WINDOW,
    create_flow_state,
    get_current_step_info,
    start_iteration,
    report_iteration,
)
from stratum_mcp.spec import parse_and_validate


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
    flows:
      main:
        input: {}
        output: Out
        steps:
          - id: s1
            function: work
            inputs: {}
            max_iterations: 10
            exit_criterion: "result.v == 'done'"
""")


@pytest.fixture(autouse=True)
def _cleanup():
    _flows.clear()
    yield
    _flows.clear()


def _make_state():
    spec = parse_and_validate(_ITER_SPEC)
    state = create_flow_state(spec, "main", {}, raw_spec=_ITER_SPEC)
    get_current_step_info(state)
    start_iteration(state, "s1")
    return state


def test_stagnation_fires_after_consecutive_duplicates():
    """N identical results trigger exit_stagnation."""
    state = _make_state()

    # Send _STAGNATION_WINDOW identical results
    for i in range(_STAGNATION_WINDOW - 1):
        r = report_iteration(state, "s1", {"v": "stuck"})
        assert r["outcome"] == "continue", f"iteration {i+1} should continue"

    # The Nth identical result triggers stagnation
    r = report_iteration(state, "s1", {"v": "stuck"})
    assert r["outcome"] == "exit_stagnation"
    assert r["status"] == "iteration_exit"
    assert state.iteration_outcome["s1"] == "exit_stagnation"
    assert state.active_iteration is None


def test_stagnation_not_triggered_by_varying_results():
    """Different results each time should not trigger stagnation."""
    state = _make_state()

    for i in range(_STAGNATION_WINDOW + 2):
        r = report_iteration(state, "s1", {"v": f"attempt_{i}"})
        assert r["outcome"] == "continue"


def test_stagnation_resets_on_different_result():
    """A different result in the middle resets the stagnation counter."""
    state = _make_state()

    # Send (_STAGNATION_WINDOW - 1) identical results
    for _ in range(_STAGNATION_WINDOW - 1):
        r = report_iteration(state, "s1", {"v": "stuck"})
        assert r["outcome"] == "continue"

    # Break the streak with a different result
    r = report_iteration(state, "s1", {"v": "different"})
    assert r["outcome"] == "continue"

    # Start a new streak — need another full window
    for i in range(_STAGNATION_WINDOW - 1):
        r = report_iteration(state, "s1", {"v": "stuck_again"})
        assert r["outcome"] == "continue"

    r = report_iteration(state, "s1", {"v": "stuck_again"})
    assert r["outcome"] == "exit_stagnation"


def test_exit_success_takes_priority_over_stagnation():
    """exit_criterion is checked before stagnation — exit_success always wins."""
    state = _make_state()

    # The exit criterion is result.v == 'done'. Send 'done' on every iteration.
    # First call meets exit_criterion immediately → exit_success, not stagnation.
    r = report_iteration(state, "s1", {"v": "done"})
    assert r["outcome"] == "exit_success"


def test_stagnation_history_records_fingerprints():
    """Iteration history entries include result_fingerprint field."""
    state = _make_state()

    report_iteration(state, "s1", {"v": "test"})
    entry = state.iterations["s1"][0]
    assert "result_fingerprint" in entry
    assert len(entry["result_fingerprint"]) == 64  # SHA256 hex digest


def test_stagnation_with_complex_results():
    """Stagnation detection works with nested/complex result dicts."""
    state = _make_state()

    complex_result = {"v": "x", "nested": {"a": [1, 2, 3], "b": True}}
    for _ in range(_STAGNATION_WINDOW - 1):
        r = report_iteration(state, "s1", complex_result)
        assert r["outcome"] == "continue"

    r = report_iteration(state, "s1", complex_result)
    assert r["outcome"] == "exit_stagnation"


def test_stagnation_window_constant():
    """Verify the default stagnation window is a reasonable value."""
    assert _STAGNATION_WINDOW >= 2, "Window must be at least 2 to avoid false positives"
    assert _STAGNATION_WINDOW <= 10, "Window should not be too large to be useful"


def test_stagnation_survives_persist_restore():
    """Stagnation streak survives a persist/restore cycle."""
    from stratum_mcp.executor import persist_flow, restore_flow, delete_persisted_flow

    state = _make_state()

    # Build up a streak just below the threshold
    for _ in range(_STAGNATION_WINDOW - 1):
        r = report_iteration(state, "s1", {"v": "stuck"})
        assert r["outcome"] == "continue"

    # Persist and restore
    flow_id = state.flow_id
    persist_flow(state)
    _flows.pop(flow_id, None)

    restored = restore_flow(flow_id)
    assert restored is not None
    _flows[flow_id] = restored

    # The Nth duplicate after restore should trigger stagnation
    r = report_iteration(restored, "s1", {"v": "stuck"})
    assert r["outcome"] == "exit_stagnation"

    delete_persisted_flow(flow_id)


def test_stagnation_resets_after_gate_revise():
    """Stagnation streak resets when a gate revise archives iterations."""
    from stratum_mcp.executor import process_step_result, resolve_gate

    gate_spec = textwrap.dedent("""\
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
                max_iterations: 10
                exit_criterion: "result.v == 'done'"
              - id: g1
                function: gate_fn
                on_approve: ~
                on_revise: s1
                on_kill: ~
    """)
    spec = parse_and_validate(gate_spec)
    state = create_flow_state(spec, "main", {}, raw_spec=gate_spec)
    _flows[state.flow_id] = state
    get_current_step_info(state)

    # Build up a streak just below threshold
    start_iteration(state, "s1")
    for _ in range(_STAGNATION_WINDOW - 1):
        report_iteration(state, "s1", {"v": "stuck"})

    # Abort iteration, complete the step, hit the gate, and revise
    from stratum_mcp.executor import abort_iteration
    abort_iteration(state, "s1", "moving on")
    process_step_result(state, "s1", {"v": "interim"})
    get_current_step_info(state)
    resolve_gate(state, "g1", "revise", "redo", "human")

    # After revise, iterations are archived and cleared
    assert state.iterations == {}

    # Start fresh iteration in the new round — streak should be reset
    get_current_step_info(state)
    start_iteration(state, "s1")
    for _ in range(_STAGNATION_WINDOW - 1):
        r = report_iteration(state, "s1", {"v": "stuck"})
        assert r["outcome"] == "continue"

    # Now the Nth duplicate triggers stagnation (fresh window, not carried over)
    r = report_iteration(state, "s1", {"v": "stuck"})
    assert r["outcome"] == "exit_stagnation"
