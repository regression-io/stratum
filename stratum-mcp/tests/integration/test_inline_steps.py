"""Integration tests for inline step execution (STRAT-ENG-2)."""
import asyncio
import dataclasses
import textwrap

import pytest

from stratum_mcp.errors import MCPExecutionError
from stratum_mcp.executor import (
    StepRecord,
    _record_from_dict,
    _step_mode,
    create_flow_state,
    get_current_step_info,
    process_step_result,
    persist_flow,
    restore_flow,
    delete_persisted_flow,
    _flows,
)
from stratum_mcp.server import stratum_plan, stratum_step_done, stratum_audit
from stratum_mcp.spec import parse_and_validate, IRStepDef


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


# ---------------------------------------------------------------------------
# Spec fixtures
# ---------------------------------------------------------------------------

_INLINE_SPEC = textwrap.dedent("""\
    version: "0.2"
    flows:
      main:
        input: {}
        steps:
          - id: s1
            intent: "Do the thing"
            agent: claude
            ensure:
              - "result.done == True"
            retries: 2
""")

_INLINE_NO_RETRIES_SPEC = textwrap.dedent("""\
    version: "0.2"
    flows:
      main:
        input: {}
        steps:
          - id: s1
            intent: "Do the thing"
            agent: claude
            ensure:
              - "result.done == True"
""")

_MIXED_SPEC = textwrap.dedent("""\
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
        steps:
          - id: s1
            function: work
            inputs: {}
          - id: s2
            intent: "Review the output"
            agent: codex
            ensure:
              - "result.ok == True"
            retries: 1
            depends_on: [s1]
""")

_INLINE_SKIP_SPEC = textwrap.dedent("""\
    version: "0.2"
    flows:
      main:
        input: {}
        steps:
          - id: s1
            intent: "Do the thing"
            agent: claude
            skip_if: "True"
            skip_reason: "always skip"
          - id: s2
            intent: "Second step"
            agent: claude
""")

_FLOW_REF_SPEC = textwrap.dedent("""\
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
      sub:
        input: {}
        output: Out
        steps:
          - id: h1
            function: work
            inputs: {}
      main:
        input: {}
        steps:
          - id: s1
            flow: sub
""")


# ---------------------------------------------------------------------------
# Task 1: _step_mode helper
# ---------------------------------------------------------------------------

def test_step_mode_function():
    spec = parse_and_validate(_MIXED_SPEC)
    step = spec.flows["main"].steps[0]  # function step
    assert _step_mode(step) == "function"


def test_step_mode_inline():
    spec = parse_and_validate(_INLINE_SPEC)
    step = spec.flows["main"].steps[0]  # inline step
    assert _step_mode(step) == "inline"


def test_step_mode_flow_ref_raises():
    spec = parse_and_validate(_FLOW_REF_SPEC)
    step = spec.flows["main"].steps[0]  # flow_ref step
    with pytest.raises(MCPExecutionError, match="STRAT-ENG-5"):
        _step_mode(step)


def test_step_mode_no_mode_raises():
    # Construct a step with no mode set (bypass validator)
    step = IRStepDef(id="bad", function="", inputs={}, depends_on=[], declared_routing=set())
    with pytest.raises(MCPExecutionError, match="no execution mode"):
        _step_mode(step)


# ---------------------------------------------------------------------------
# Task 2: StepRecord fields + backward compat
# ---------------------------------------------------------------------------

def test_step_record_defaults():
    rec = StepRecord(step_id="s1", function_name="work", attempts=1, duration_ms=100)
    assert rec.agent is None
    assert rec.step_mode == "function"


def test_record_from_dict_backward_compat():
    d = {
        "type": "step",
        "step_id": "s1",
        "function_name": "work",
        "attempts": 1,
        "duration_ms": 100,
        "round": 0,
        "round_start_step_id": None,
        # no agent, no step_mode — old format
    }
    rec = _record_from_dict(d)
    assert isinstance(rec, StepRecord)
    assert rec.agent is None
    assert rec.step_mode == "function"


# ---------------------------------------------------------------------------
# Task 3: get_current_step_info
# ---------------------------------------------------------------------------

def test_inline_step_info_returns_intent():
    spec = parse_and_validate(_INLINE_SPEC)
    state = create_flow_state(spec, "main", {}, raw_spec=_INLINE_SPEC)
    info = get_current_step_info(state)
    assert info["step_mode"] == "inline"
    assert info["intent"] == "Do the thing"
    assert info["agent"] == "claude"
    assert info["status"] == "execute_step"


def test_inline_step_info_returns_step_ensure():
    spec = parse_and_validate(_INLINE_SPEC)
    state = create_flow_state(spec, "main", {}, raw_spec=_INLINE_SPEC)
    info = get_current_step_info(state)
    assert info["ensure"] == ["result.done == True"]


def test_inline_step_info_retries_default():
    spec = parse_and_validate(_INLINE_NO_RETRIES_SPEC)
    state = create_flow_state(spec, "main", {}, raw_spec=_INLINE_NO_RETRIES_SPEC)
    info = get_current_step_info(state)
    assert info["retries_remaining"] == 1


def test_function_step_info_includes_agent():
    spec = parse_and_validate(_MIXED_SPEC)
    state = create_flow_state(spec, "main", {}, raw_spec=_MIXED_SPEC)
    info = get_current_step_info(state)
    assert "agent" in info
    assert info["agent"] is None  # function steps typically have no agent


def test_function_step_info_includes_step_mode():
    spec = parse_and_validate(_MIXED_SPEC)
    state = create_flow_state(spec, "main", {}, raw_spec=_MIXED_SPEC)
    info = get_current_step_info(state)
    assert info["step_mode"] == "function"


def test_inline_step_skip_if_works():
    spec = parse_and_validate(_INLINE_SKIP_SPEC)
    state = create_flow_state(spec, "main", {}, raw_spec=_INLINE_SKIP_SPEC)
    info = get_current_step_info(state)
    # s1 should be skipped, info should be for s2
    assert info["step_id"] == "s2"
    assert info["step_mode"] == "inline"
    # Verify SkipRecord was written for s1
    assert len(state.records) == 1
    assert state.records[0].step_id == "s1"
    assert state.records[0].type == "skip"


# ---------------------------------------------------------------------------
# Task 4: process_step_result
# ---------------------------------------------------------------------------

def test_inline_step_done_success():
    spec = parse_and_validate(_INLINE_SPEC)
    state = create_flow_state(spec, "main", {}, raw_spec=_INLINE_SPEC)
    get_current_step_info(state)  # dispatch
    status, violations = process_step_result(state, "s1", {"done": True})
    assert status == "ok"
    assert violations == []
    rec = state.records[0]
    assert isinstance(rec, StepRecord)
    assert rec.step_mode == "inline"
    assert rec.agent == "claude"


def test_inline_step_ensure_failure_retries():
    spec = parse_and_validate(_INLINE_SPEC)
    state = create_flow_state(spec, "main", {}, raw_spec=_INLINE_SPEC)
    get_current_step_info(state)
    status, violations = process_step_result(state, "s1", {"done": False})
    assert status == "ensure_failed"
    assert len(violations) == 1
    # Should still be on s1, attempt incremented
    assert state.attempts["s1"] == 1
    assert state.current_idx == 0


def test_inline_step_retries_exhausted():
    spec = parse_and_validate(_INLINE_SPEC)
    state = create_flow_state(spec, "main", {}, raw_spec=_INLINE_SPEC)
    get_current_step_info(state)
    # retries=2, so 2 failures exhaust
    process_step_result(state, "s1", {"done": False})
    get_current_step_info(state)
    status, violations = process_step_result(state, "s1", {"done": False})
    assert status == "retries_exhausted"


def test_inline_step_no_retries_exhausts_on_first_fail():
    spec = parse_and_validate(_INLINE_NO_RETRIES_SPEC)
    state = create_flow_state(spec, "main", {}, raw_spec=_INLINE_NO_RETRIES_SPEC)
    get_current_step_info(state)
    status, violations = process_step_result(state, "s1", {"done": False})
    assert status == "retries_exhausted"


# ---------------------------------------------------------------------------
# Task 5: server.py gate guard
# ---------------------------------------------------------------------------

def test_step_done_inline_step_not_rejected_as_gate():
    result = _run(stratum_plan(spec=_INLINE_SPEC, flow="main", inputs={}, ctx=None))
    flow_id = result["flow_id"]
    try:
        result = _run(stratum_step_done(flow_id, "s1", {"done": True}, ctx=None))
        assert result["status"] == "complete"
    finally:
        _flows.pop(flow_id, None)
        delete_persisted_flow(flow_id)


# ---------------------------------------------------------------------------
# Task 6: Full roundtrip integration
# ---------------------------------------------------------------------------

def test_roundtrip_inline_step_single():
    result = _run(stratum_plan(spec=_INLINE_SPEC, flow="main", inputs={}, ctx=None))
    flow_id = result["flow_id"]
    assert result["step_mode"] == "inline"
    assert result["intent"] == "Do the thing"
    assert result["agent"] == "claude"
    try:
        result = _run(stratum_step_done(flow_id, "s1", {"done": True}, ctx=None))
        assert result["status"] == "complete"
    finally:
        _flows.pop(flow_id, None)
        delete_persisted_flow(flow_id)


def test_roundtrip_inline_step_ensure_retry():
    result = _run(stratum_plan(spec=_INLINE_SPEC, flow="main", inputs={}, ctx=None))
    flow_id = result["flow_id"]
    try:
        # First attempt fails ensure
        result = _run(stratum_step_done(flow_id, "s1", {"done": False}, ctx=None))
        assert result["status"] == "ensure_failed"
        assert result["retries_remaining"] == 1  # started with 2, used 1
        # Second attempt passes
        result = _run(stratum_step_done(flow_id, "s1", {"done": True}, ctx=None))
        assert result["status"] == "complete"
    finally:
        _flows.pop(flow_id, None)
        delete_persisted_flow(flow_id)


def test_roundtrip_inline_step_retries_exhausted():
    result = _run(stratum_plan(spec=_INLINE_SPEC, flow="main", inputs={}, ctx=None))
    flow_id = result["flow_id"]
    try:
        _run(stratum_step_done(flow_id, "s1", {"done": False}, ctx=None))
        result = _run(stratum_step_done(flow_id, "s1", {"done": False}, ctx=None))
        assert result["status"] == "error"
        assert result["error_type"] == "retries_exhausted"
    finally:
        _flows.pop(flow_id, None)
        delete_persisted_flow(flow_id)


def test_roundtrip_mixed_function_inline():
    result = _run(stratum_plan(spec=_MIXED_SPEC, flow="main", inputs={}, ctx=None))
    flow_id = result["flow_id"]
    assert result["step_mode"] == "function"
    try:
        # Complete function step
        result = _run(stratum_step_done(flow_id, "s1", {"v": "hello"}, ctx=None))
        assert result["step_mode"] == "inline"
        assert result["agent"] == "codex"
        # Complete inline step
        result = _run(stratum_step_done(flow_id, "s2", {"ok": True}, ctx=None))
        assert result["status"] == "complete"
    finally:
        _flows.pop(flow_id, None)
        delete_persisted_flow(flow_id)


def test_roundtrip_inline_step_audit_trace():
    result = _run(stratum_plan(spec=_INLINE_SPEC, flow="main", inputs={}, ctx=None))
    flow_id = result["flow_id"]
    try:
        _run(stratum_step_done(flow_id, "s1", {"done": True}, ctx=None))
        audit = _run(stratum_audit(flow_id, ctx=None))
        assert len(audit["trace"]) == 1
        rec = audit["trace"][0]
        assert rec["step_mode"] == "inline"
        assert rec["agent"] == "claude"
    finally:
        _flows.pop(flow_id, None)
        delete_persisted_flow(flow_id)


def test_roundtrip_inline_step_persistence():
    result = _run(stratum_plan(spec=_INLINE_SPEC, flow="main", inputs={}, ctx=None))
    flow_id = result["flow_id"]
    try:
        # Evict from cache to force restore
        _flows.pop(flow_id, None)
        result = _run(stratum_step_done(flow_id, "s1", {"done": True}, ctx=None))
        assert result["status"] == "complete"
    finally:
        _flows.pop(flow_id, None)
        delete_persisted_flow(flow_id)


# ---------------------------------------------------------------------------
# Task 3 extra: gate step includes new fields
# ---------------------------------------------------------------------------

_GATE_SPEC = textwrap.dedent("""\
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
      review:
        mode: gate
    flows:
      main:
        input: {}
        output: Out
        steps:
          - id: s1
            function: work
            inputs: {}
          - id: gate
            function: review
            on_approve: ~
            on_revise: s1
            on_kill: ~
            depends_on: [s1]
""")


def test_gate_step_info_includes_agent_and_step_mode():
    spec = parse_and_validate(_GATE_SPEC)
    state = create_flow_state(spec, "main", {}, raw_spec=_GATE_SPEC)
    # Complete s1 first
    get_current_step_info(state)
    process_step_result(state, "s1", {"v": "ok"})
    # Now get gate step info
    info = get_current_step_info(state)
    assert info["status"] == "await_gate"
    assert info["step_mode"] == "function"
    assert "agent" in info
