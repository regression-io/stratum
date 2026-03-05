"""Contract tests enforcing gate API separation (IR v0.2).

Contracts:
  1. stratum_step_done returns an error (not raises) when called on a gate-mode step.
     State is unchanged: no attempt increment, no record written.
  2. stratum_gate_resolve returns an error when called on a non-gate step.
     State is unchanged.
  3. stratum_gate_resolve routes correctly for each outcome:
     - approve + null on_approve  → status: complete
     - approve + named on_approve → execute_step for named step
     - revise                     → execute_step for on_revise target
     - kill + null on_kill        → status: killed
     - kill + named on_kill       → execute_step for named step
  4. resolved_by (human | agent | system) is recorded in the gate trace entry.
     All three produce identical execution outcomes.
  5. rounds is always present in stratum_audit output (empty or populated).

These tests will fail until stratum-mcp IR v0.2 implements:
  - mode: gate enforcement in stratum_step_done
  - stratum_gate_resolve tool in server.py
  - GateRecord in executor trace

Spec: docs/plans/2026-03-05-stratum-ir-v0.2-spec.md §8
"""
import pytest
from unittest.mock import MagicMock

from stratum_mcp.server import (
    stratum_plan,
    stratum_step_done,
    stratum_audit,
    stratum_gate_resolve,  # IR v0.2 — does not exist until refactor
)
from stratum_mcp import executor as executor_mod


# ---------------------------------------------------------------------------
# Shared specs
# ---------------------------------------------------------------------------

# Two-step flow: infer step then gate with null on_approve and null on_kill.
INFER_THEN_GATE_IR = """
version: "0.2"
contracts:
  WorkOutput:
    result: {type: string}
functions:
  do_work:
    mode: infer
    intent: "Produce a result"
    input: {text: {type: string}}
    output: WorkOutput
  approval_gate:
    mode: gate
flows:
  gated_flow:
    input: {text: {type: string}}
    steps:
      - id: work
        function: do_work
        inputs: {text: "$.input.text"}
      - id: gate
        function: approval_gate
        on_approve: ~
        on_revise: work
        on_kill: ~
"""

# Three-step flow: work → gate (on_approve: work2) → work2.
# Used to test that approve with a named on_approve routes to that step.
NAMED_APPROVE_IR = """
version: "0.2"
contracts:
  WorkOutput:
    result: {type: string}
functions:
  do_work:
    mode: infer
    intent: "Produce a result"
    input: {text: {type: string}}
    output: WorkOutput
  approval_gate:
    mode: gate
flows:
  named_approve_flow:
    input: {text: {type: string}}
    steps:
      - id: work
        function: do_work
        inputs: {text: "$.input.text"}
      - id: gate
        function: approval_gate
        on_approve: work2
        on_revise: work
        on_kill: ~
      - id: work2
        function: do_work
        inputs: {text: "$.input.text"}
"""

# Three-step flow: work → gate (on_kill: cleanup) → cleanup.
# Used to test that kill with a named on_kill routes to that step (not status: killed).
NAMED_KILL_IR = """
version: "0.2"
contracts:
  WorkOutput:
    result: {type: string}
  CleanupOutput:
    status: {type: string}
functions:
  do_work:
    mode: infer
    intent: "Produce a result"
    input: {text: {type: string}}
    output: WorkOutput
  approval_gate:
    mode: gate
  do_cleanup:
    mode: infer
    intent: "Cleanup on kill"
    input: {}
    output: CleanupOutput
flows:
  named_kill_flow:
    input: {text: {type: string}}
    steps:
      - id: work
        function: do_work
        inputs: {text: "$.input.text"}
      - id: gate
        function: approval_gate
        on_approve: ~
        on_revise: work
        on_kill: cleanup
      - id: cleanup
        function: do_cleanup
        inputs: {}
"""


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

ctx = MagicMock()


@pytest.fixture(autouse=True)
def patch_flows_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(executor_mod, "_FLOWS_DIR", tmp_path / "flows")
    yield tmp_path / "flows"


# ---------------------------------------------------------------------------
# Contract 1: stratum_step_done rejected for gate steps
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_step_done_returns_error_for_gate_step():
    """
    stratum_step_done on a gate-mode step must return an error dict without
    modifying flow state: no attempt increment, no record written, current_idx unchanged.
    Spec: §8.1
    """
    plan = await stratum_plan(INFER_THEN_GATE_IR, "gated_flow", {"text": "hi"}, ctx)
    flow_id = plan["flow_id"]
    await stratum_step_done(flow_id, "work", {"result": "done"}, ctx)

    state = executor_mod._flows[flow_id]
    records_before = len(state.records)
    attempts_before = state.attempts.get("gate", 0)

    result = await stratum_step_done(flow_id, "gate", {"outcome": "approve"}, ctx)

    assert result["status"] == "error"
    assert result["code"] == "gate_step_requires_gate_resolve"
    assert "stratum_gate_resolve" in result["message"]
    # State unchanged
    assert len(state.records) == records_before, "no record must be written"
    assert state.attempts.get("gate", 0) == attempts_before, "attempt counter must not increment"


@pytest.mark.asyncio
async def test_step_done_succeeds_for_infer_step():
    """Baseline: gate rejection must not break stratum_step_done for infer-mode steps."""
    plan = await stratum_plan(INFER_THEN_GATE_IR, "gated_flow", {"text": "hi"}, ctx)
    flow_id = plan["flow_id"]
    result = await stratum_step_done(flow_id, "work", {"result": "done"}, ctx)
    assert result["status"] != "error"


# ---------------------------------------------------------------------------
# Contract 2: stratum_gate_resolve rejected for non-gate steps
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_gate_resolve_returns_error_for_infer_step():
    """
    stratum_gate_resolve on a non-gate step must return an error without modifying
    flow state.
    Spec: §8.2
    """
    plan = await stratum_plan(INFER_THEN_GATE_IR, "gated_flow", {"text": "hi"}, ctx)
    flow_id = plan["flow_id"]

    state = executor_mod._flows[flow_id]
    records_before = len(state.records)

    result = await stratum_gate_resolve(flow_id, "work", "approve", "wrong api", "human", ctx)

    assert result["status"] == "error"
    assert result["code"] == "not_a_gate_step"
    assert len(state.records) == records_before, "no record must be written on rejected call"


# ---------------------------------------------------------------------------
# Contract 3: stratum_gate_resolve routes correctly for each outcome
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_gate_resolve_approve_null_completes_flow():
    """approve with on_approve: null must complete the flow. rounds present in audit."""
    plan = await stratum_plan(INFER_THEN_GATE_IR, "gated_flow", {"text": "hi"}, ctx)
    flow_id = plan["flow_id"]
    await stratum_step_done(flow_id, "work", {"result": "done"}, ctx)

    result = await stratum_gate_resolve(flow_id, "gate", "approve", "ok", "human", ctx)
    assert result["status"] == "complete"

    audit = await stratum_audit(flow_id, ctx)
    assert "rounds" in audit, "rounds must always be present in stratum_audit output"
    assert audit["rounds"] == []


@pytest.mark.asyncio
async def test_gate_resolve_approve_named_advances_to_step():
    """approve with on_approve: <step_id> must return execute_step for that step."""
    plan = await stratum_plan(NAMED_APPROVE_IR, "named_approve_flow", {"text": "hi"}, ctx)
    flow_id = plan["flow_id"]
    await stratum_step_done(flow_id, "work", {"result": "done"}, ctx)

    result = await stratum_gate_resolve(flow_id, "gate", "approve", "proceed", "human", ctx)

    assert result["status"] == "execute_step"
    assert result["step_id"] == "work2"


@pytest.mark.asyncio
async def test_gate_resolve_revise_returns_on_revise_target():
    """revise must return execute_step for the on_revise target, not the step after gate."""
    plan = await stratum_plan(INFER_THEN_GATE_IR, "gated_flow", {"text": "hi"}, ctx)
    flow_id = plan["flow_id"]
    await stratum_step_done(flow_id, "work", {"result": "done"}, ctx)

    result = await stratum_gate_resolve(flow_id, "gate", "revise", "not good enough", "human", ctx)

    assert result["status"] == "execute_step"
    assert result["step_id"] == "work"


@pytest.mark.asyncio
async def test_gate_resolve_kill_null_returns_killed_status():
    """kill with on_kill: null must terminate the flow. rounds present in audit."""
    plan = await stratum_plan(INFER_THEN_GATE_IR, "gated_flow", {"text": "hi"}, ctx)
    flow_id = plan["flow_id"]
    await stratum_step_done(flow_id, "work", {"result": "done"}, ctx)

    result = await stratum_gate_resolve(flow_id, "gate", "kill", "not viable", "human", ctx)
    assert result["status"] == "killed"

    audit = await stratum_audit(flow_id, ctx)
    assert "rounds" in audit, "rounds must always be present in stratum_audit output"
    assert audit["rounds"] == []


@pytest.mark.asyncio
async def test_gate_resolve_kill_named_routes_to_terminal_step():
    """
    kill with on_kill: <step_id> must return execute_step for the terminal step,
    not status: killed. This is the same branching rule that applies to timeout.
    Spec: §8.5; Transition table: kill rows
    """
    plan = await stratum_plan(NAMED_KILL_IR, "named_kill_flow", {"text": "hi"}, ctx)
    flow_id = plan["flow_id"]
    await stratum_step_done(flow_id, "work", {"result": "done"}, ctx)

    result = await stratum_gate_resolve(flow_id, "gate", "kill", "not viable", "human", ctx)

    assert result["status"] == "execute_step", (
        "kill with on_kill: <step_id> must return execute_step, not killed — "
        "same branch semantics as timeout with a named on_kill target"
    )
    assert result["step_id"] == "cleanup"


# ---------------------------------------------------------------------------
# Contract 4: resolved_by recorded in trace; no execution effect
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_gate_resolve_resolved_by_recorded_for_all_resolver_types():
    """
    resolved_by (human | agent | system) must appear in the gate's GateRecord.
    All three values must produce identical execution outcomes (status: complete).
    rounds is unconditionally present in every audit response.
    Spec: §7 GateRecord; §8.3 approve
    """
    for resolver in ("human", "agent", "system"):
        plan = await stratum_plan(INFER_THEN_GATE_IR, "gated_flow", {"text": "hi"}, ctx)
        flow_id = plan["flow_id"]
        await stratum_step_done(flow_id, "work", {"result": "done"}, ctx)
        await stratum_gate_resolve(flow_id, "gate", "approve", "ok", resolver, ctx)

        audit = await stratum_audit(flow_id, ctx)
        assert "rounds" in audit, "rounds must always be present in stratum_audit output"
        assert audit["status"] == "complete", \
            f"execution outcome must be complete regardless of resolver (resolver={resolver!r})"

        gate_entry = next(
            (r for r in audit.get("trace", []) if r.get("step_id") == "gate"), None
        )
        assert gate_entry is not None, f"gate trace entry missing for resolved_by={resolver!r}"
        assert gate_entry["resolved_by"] == resolver, \
            f"resolved_by must be recorded as {resolver!r} in gate trace entry"
