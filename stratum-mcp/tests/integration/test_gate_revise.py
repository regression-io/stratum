"""Specification tests for gate/revise round-archiving and timeout routing (IR v0.2).

Covers:
  - rounds is always present in stratum_audit output (empty or populated)
  - Revise archives active records into rounds[] before clearing active state
  - round counter increments on each revise
  - Timeout with on_kill: <step_id> routes to that step (not status: killed),
    following the same branch semantics as an explicit kill outcome

These tests will fail until the stratum-mcp IR v0.2 refactor implements:
  - mode: gate in spec.py
  - on_approve / on_revise / on_kill routing in executor.py
  - stratum_gate_resolve and stratum_check_timeouts in server.py
  - rounds[], round counter, round_start_step_id on FlowState / StepRecord
  - timeout field on gate functions

Normative contracts: docs/plans/2026-03-05-stratum-ir-v0.2-spec.md §8–9
Transition table:   docs/plans/2026-03-05-stratum-gate-transitions.md
"""
import time
import pytest
from unittest.mock import MagicMock

from stratum_mcp.server import (
    stratum_plan,
    stratum_step_done,
    stratum_audit,
    stratum_gate_resolve,    # IR v0.2 — does not exist until refactor
    stratum_check_timeouts,  # IR v0.2 — does not exist until refactor
)
from stratum_mcp import executor as executor_mod


# ---------------------------------------------------------------------------
# Shared specs
# ---------------------------------------------------------------------------

GATED_FLOW_IR = """
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
    max_rounds: 5
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

# Gate with a 1-second timeout and on_kill pointing to a named terminal step
# (not null). Used to verify that timeout follows the same on_kill branch
# semantics as an explicit kill call — it must not always return status: killed.
TIMEOUT_NAMED_KILL_IR = """
version: "0.2"
contracts:
  WorkOutput:
    result: {type: string}
  CleanupOutput:
    done: {type: boolean}
functions:
  do_work:
    mode: infer
    intent: "Produce a result"
    input: {text: {type: string}}
    output: WorkOutput
  approval_gate:
    mode: gate
    timeout: 1
  do_cleanup:
    mode: infer
    intent: "Cleanup step reached after timeout kill"
    input: {}
    output: CleanupOutput
flows:
  timeout_flow:
    input: {text: {type: string}}
    steps:
      - id: work
        function: do_work
        inputs: {text: "$.input.text"}
      - id: gate
        function: approval_gate
        on_approve: ~
        on_revise: work
        on_kill: terminal
      - id: terminal
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
# Helper
# ---------------------------------------------------------------------------

async def advance_to_gate(flow_id: str) -> None:
    """Complete the work step so the gate becomes the current step."""
    await stratum_step_done(flow_id, "work", {"result": "done"}, ctx)


# ---------------------------------------------------------------------------
# Contract: rounds is always present in stratum_audit (spec §9)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_rounds_always_present_when_no_revise_occurred():
    """
    rounds must be present and an empty list when the flow completes with no revise.
    Clients must never check for field presence — rounds is unconditionally included.
    Spec: §9 — "stratum_audit always includes a rounds field"
    """
    plan = await stratum_plan(GATED_FLOW_IR, "gated_flow", {"text": "hello"}, ctx)
    flow_id = plan["flow_id"]
    await advance_to_gate(flow_id)
    await stratum_gate_resolve(flow_id, "gate", "approve", "ok", "human", ctx)

    audit = await stratum_audit(flow_id, ctx)
    assert "rounds" in audit, "rounds must always be present in stratum_audit output"
    assert audit["rounds"] == [], "rounds must be empty when no revise has occurred"


@pytest.mark.asyncio
async def test_rounds_always_present_after_kill_no_revise():
    """rounds is unconditionally present even when the flow ends via kill."""
    plan = await stratum_plan(GATED_FLOW_IR, "gated_flow", {"text": "hello"}, ctx)
    flow_id = plan["flow_id"]
    await advance_to_gate(flow_id)
    await stratum_gate_resolve(flow_id, "gate", "kill", "not viable", "human", ctx)

    audit = await stratum_audit(flow_id, ctx)
    assert "rounds" in audit, "rounds must always be present in stratum_audit output"
    assert audit["rounds"] == [], "rounds must be empty when no revise occurred before kill"


@pytest.mark.asyncio
async def test_rounds_present_and_populated_after_revise():
    """After a revise, rounds contains the archived round; field is still unconditionally present."""
    plan = await stratum_plan(GATED_FLOW_IR, "gated_flow", {"text": "hello"}, ctx)
    flow_id = plan["flow_id"]

    await advance_to_gate(flow_id)
    await stratum_gate_resolve(flow_id, "gate", "revise", "redo", "human", ctx)
    await advance_to_gate(flow_id)
    await stratum_gate_resolve(flow_id, "gate", "approve", "good", "human", ctx)

    audit = await stratum_audit(flow_id, ctx)
    assert "rounds" in audit, "rounds must always be present in stratum_audit output"
    assert len(audit["rounds"]) == 1, "rounds must contain one archived round after one revise"
    round_0_ids = [r["step_id"] for r in audit["rounds"][0]["steps"]]
    assert "work" in round_0_ids, "round 0 archive must contain the work StepRecord"
    assert "gate" in round_0_ids, "round 0 archive must contain the revise GateRecord"


# ---------------------------------------------------------------------------
# Revise rollback correctness
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_revise_archives_records_before_clearing_active_state():
    """
    On revise: the GateRecord is appended to state.records, then the full records
    list is archived into rounds[0] before active state is cleared.
    Neither the work StepRecord nor the revise GateRecord may be lost.
    Spec: §8.4 step order — archive (step 4) precedes clear (steps 5–7)
    """
    plan = await stratum_plan(GATED_FLOW_IR, "gated_flow", {"text": "hello"}, ctx)
    flow_id = plan["flow_id"]
    await advance_to_gate(flow_id)
    await stratum_gate_resolve(flow_id, "gate", "revise", "needs rework", "human", ctx)

    state = executor_mod._flows[flow_id]

    # Archive must exist for round 0
    assert len(state.rounds) == 1, "rounds[0] must be written after first revise"
    archived_ids = {r["step_id"] for r in state.rounds[0]}
    assert "work" in archived_ids, "work StepRecord must be archived in rounds[0]"
    assert "gate" in archived_ids, "revise GateRecord must be archived in rounds[0]"

    # Active state must be cleared from on_revise target (work) onward
    assert "work" not in state.step_outputs, "work output must be cleared after revise"
    assert state.attempts.get("work", 0) == 0, "work attempt counter must be reset"
    assert not any(r.step_id == "work" for r in state.records), \
        "active records must not contain work after revise"


@pytest.mark.asyncio
async def test_revise_increments_round_counter():
    """flow.round starts at 0 and increments by 1 on each revise."""
    plan = await stratum_plan(GATED_FLOW_IR, "gated_flow", {"text": "hello"}, ctx)
    flow_id = plan["flow_id"]
    state = executor_mod._flows[flow_id]

    assert state.round == 0

    await advance_to_gate(flow_id)
    await stratum_gate_resolve(flow_id, "gate", "revise", "again", "human", ctx)
    assert state.round == 1

    await advance_to_gate(flow_id)
    await stratum_gate_resolve(flow_id, "gate", "revise", "again", "human", ctx)
    assert state.round == 2


# ---------------------------------------------------------------------------
# Timeout routing: follows on_kill branch semantics (not always killed)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_timeout_with_named_on_kill_routes_to_terminal_step():
    """
    When a gate times out and on_kill points to a named step (not null), the executor
    must return execute_step for that step — not status: killed.

    This is the same branching rule as an explicit stratum_gate_resolve(kill) call
    with a named on_kill target. Timeout must not short-circuit to a hardcoded
    killed status; it must follow the configured on_kill routing.

    The auto-kill GateRecord must record resolved_by: system and outcome: kill.

    Transition: docs/plans/2026-03-05-stratum-gate-transitions.md — timeout rows
    Spec: §8.5 kill routing (timeout follows same logic)
    """
    plan = await stratum_plan(TIMEOUT_NAMED_KILL_IR, "timeout_flow", {"text": "hello"}, ctx)
    flow_id = plan["flow_id"]
    await stratum_step_done(flow_id, "work", {"result": "done"}, ctx)

    # Simulate timeout expiry: backdate the gate's dispatch timestamp past the 1-second timeout.
    state = executor_mod._flows[flow_id]
    state.dispatched_at["gate"] = time.time() - 10  # 10 s ago; timeout is 1 s

    # stratum_check_timeouts scans pending gates and fires auto-kill for expired ones.
    result = await stratum_check_timeouts(flow_id, ctx)

    assert result["status"] == "execute_step", (
        "timeout with on_kill: <step_id> must return execute_step, not killed — "
        "timeout follows the same on_kill branch as an explicit kill outcome"
    )
    assert result["step_id"] == "terminal", \
        "timeout must route to the on_kill target step id"

    audit = await stratum_audit(flow_id, ctx)
    assert "rounds" in audit, "rounds must always be present in stratum_audit output"

    gate_entry = next(
        (r for r in audit.get("trace", []) if r.get("step_id") == "gate"), None
    )
    assert gate_entry is not None, "gate GateRecord must appear in the audit trace"
    assert gate_entry["outcome"] == "kill", "timeout auto-kill must record outcome: kill"
    assert gate_entry["resolved_by"] == "system", \
        "timeout auto-kill must record resolved_by: system"
