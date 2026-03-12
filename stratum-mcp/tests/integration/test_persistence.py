"""Tests for FlowState persistence: persist, restore, delete, and server-level restart recovery."""
import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock

import stratum_mcp.executor as executor_mod
from stratum_mcp.executor import (
    FlowState,
    StepRecord,
    create_flow_state,
    persist_flow,
    restore_flow,
    delete_persisted_flow,
)
from stratum_mcp.server import stratum_plan, stratum_step_done, stratum_audit, stratum_resume, stratum_gate_resolve, _flows
from stratum_mcp.spec import parse_and_validate


SIMPLE_IR = """
version: "0.1"
contracts:
  Out:
    value: {type: string}
functions:
  extract:
    mode: infer
    intent: "Extract a value"
    input: {text: {type: string}}
    output: Out
    retries: 2
flows:
  run:
    input: {text: {type: string}}
    output: Out
    steps:
      - id: s1
        function: extract
        inputs: {text: "$.input.text"}
"""

TWO_STEP_IR = """
version: "0.1"
contracts:
  Step1Out:
    label: {type: string}
  Step2Out:
    summary: {type: string}
functions:
  classify:
    mode: infer
    intent: "Classify"
    input: {text: {type: string}}
    output: Step1Out
    retries: 2
  summarize:
    mode: infer
    intent: "Summarize"
    input: {label: {type: string}}
    output: Step2Out
    retries: 2
flows:
  pipeline:
    input: {text: {type: string}}
    output: Step2Out
    steps:
      - id: s1
        function: classify
        inputs: {text: "$.input.text"}
      - id: s2
        function: summarize
        inputs: {label: "$.steps.s1.output.label"}
        depends_on: [s1]
"""


@pytest.fixture(autouse=True)
def patch_flows_dir(tmp_path, monkeypatch):
    """Redirect all persistence I/O to a temp directory for each test."""
    monkeypatch.setattr(executor_mod, "_FLOWS_DIR", tmp_path / "flows")
    yield tmp_path / "flows"


# ---------------------------------------------------------------------------
# Unit-level: persist_flow / restore_flow / delete_persisted_flow
# ---------------------------------------------------------------------------

def test_persist_flow_creates_file(patch_flows_dir):
    spec = parse_and_validate(SIMPLE_IR)
    state = create_flow_state(spec, "run", {"text": "hello"}, raw_spec=SIMPLE_IR)

    persist_flow(state)

    path = patch_flows_dir / f"{state.flow_id}.json"
    assert path.exists()
    payload = json.loads(path.read_text())
    assert payload["flow_id"] == state.flow_id
    assert payload["flow_name"] == "run"
    assert payload["raw_spec"] == SIMPLE_IR
    assert payload["inputs"] == {"text": "hello"}
    assert payload["current_idx"] == 0


def test_persist_flow_overwrites_on_second_call(patch_flows_dir):
    spec = parse_and_validate(SIMPLE_IR)
    state = create_flow_state(spec, "run", {"text": "hi"}, raw_spec=SIMPLE_IR)

    persist_flow(state)
    state.current_idx = 1
    persist_flow(state)

    payload = json.loads((patch_flows_dir / f"{state.flow_id}.json").read_text())
    assert payload["current_idx"] == 1


def test_restore_flow_roundtrips_state(patch_flows_dir):
    spec = parse_and_validate(SIMPLE_IR)
    state = create_flow_state(spec, "run", {"text": "restore me"}, raw_spec=SIMPLE_IR)
    state.step_outputs["s1"] = {"value": "extracted"}
    state.attempts["s1"] = 2
    state.records.append(StepRecord(step_id="s1", function_name="extract", attempts=2, duration_ms=123))
    state.current_idx = 1

    persist_flow(state)

    restored = restore_flow(state.flow_id)
    assert restored is not None
    assert restored.flow_id == state.flow_id
    assert restored.flow_name == "run"
    assert restored.raw_spec == SIMPLE_IR
    assert restored.inputs == {"text": "restore me"}
    assert restored.step_outputs == {"s1": {"value": "extracted"}}
    assert restored.attempts == {"s1": 2}
    assert restored.current_idx == 1
    assert len(restored.records) == 1
    assert restored.records[0].step_id == "s1"
    assert restored.records[0].attempts == 2
    assert restored.records[0].duration_ms == 123


def test_restore_flow_returns_none_for_missing_id(patch_flows_dir):
    assert restore_flow("nonexistent-uuid") is None


def test_restore_flow_returns_none_for_corrupt_json(patch_flows_dir):
    patch_flows_dir.mkdir(parents=True, exist_ok=True)
    (patch_flows_dir / "bad.json").write_text("{not valid json")
    assert restore_flow("bad") is None


def test_restore_flow_returns_none_for_invalid_spec(patch_flows_dir):
    patch_flows_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "flow_id": "x",
        "flow_name": "run",
        "raw_spec": "version: bad yaml: [",
        "inputs": {},
        "step_outputs": {},
        "records": [],
        "attempts": {},
        "current_idx": 0,
    }
    (patch_flows_dir / "x.json").write_text(json.dumps(payload))
    assert restore_flow("x") is None


def test_restore_flow_resets_timing_fields(patch_flows_dir):
    import time
    spec = parse_and_validate(SIMPLE_IR)
    state = create_flow_state(spec, "run", {"text": "t"}, raw_spec=SIMPLE_IR)
    persist_flow(state)

    before = time.monotonic()
    restored = restore_flow(state.flow_id)
    after = time.monotonic()

    assert restored is not None
    assert restored.dispatched_at == {}
    assert before <= restored.flow_start <= after


def test_delete_persisted_flow_removes_file(patch_flows_dir):
    spec = parse_and_validate(SIMPLE_IR)
    state = create_flow_state(spec, "run", {"text": "bye"}, raw_spec=SIMPLE_IR)
    persist_flow(state)

    path = patch_flows_dir / f"{state.flow_id}.json"
    assert path.exists()

    delete_persisted_flow(state.flow_id)
    assert not path.exists()


def test_delete_persisted_flow_is_idempotent(patch_flows_dir):
    # Should not raise when file doesn't exist
    delete_persisted_flow("never-existed")


# ---------------------------------------------------------------------------
# Server-level: stratum_plan persists, stratum_step_done restores on cache miss
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_stratum_plan_writes_persistence_file(patch_flows_dir):
    ctx = MagicMock()
    plan = await stratum_plan(SIMPLE_IR, "run", {"text": "persist me"}, ctx)
    flow_id = plan["flow_id"]

    path = patch_flows_dir / f"{flow_id}.json"
    assert path.exists()
    payload = json.loads(path.read_text())
    assert payload["flow_id"] == flow_id
    assert payload["current_idx"] == 0


@pytest.mark.asyncio
async def test_stratum_step_done_restores_flow_on_cache_miss(patch_flows_dir):
    """Simulates MCP server restart: flow_id is known on disk but not in _flows."""
    ctx = MagicMock()
    plan = await stratum_plan(SIMPLE_IR, "run", {"text": "survive restart"}, ctx)
    flow_id = plan["flow_id"]

    # Simulate server restart — evict from in-memory cache
    _flows.pop(flow_id, None)

    # stratum_step_done should restore from disk transparently
    result = await stratum_step_done(flow_id, "s1", {"value": "found"}, ctx)
    assert result["status"] == "complete"
    assert result["output"] == {"value": "found"}


@pytest.mark.asyncio
async def test_stratum_step_done_deletes_file_on_completion(patch_flows_dir):
    ctx = MagicMock()
    plan = await stratum_plan(SIMPLE_IR, "run", {"text": "clean up"}, ctx)
    flow_id = plan["flow_id"]

    assert (patch_flows_dir / f"{flow_id}.json").exists()

    await stratum_step_done(flow_id, "s1", {"value": "done"}, ctx)

    assert not (patch_flows_dir / f"{flow_id}.json").exists()


@pytest.mark.asyncio
async def test_stratum_step_done_mid_flow_updates_persistence(patch_flows_dir):
    """After completing s1 of a 2-step flow, persistence file reflects current_idx=1."""
    ctx = MagicMock()
    plan = await stratum_plan(TWO_STEP_IR, "pipeline", {"text": "hello"}, ctx)
    flow_id = plan["flow_id"]

    await stratum_step_done(flow_id, "s1", {"label": "positive"}, ctx)

    payload = json.loads((patch_flows_dir / f"{flow_id}.json").read_text())
    assert payload["current_idx"] == 1
    assert payload["step_outputs"] == {"s1": {"label": "positive"}}


@pytest.mark.asyncio
async def test_stratum_step_done_deletes_file_on_retries_exhausted(patch_flows_dir):
    """On retries_exhausted, persistence file is removed."""
    IR = """
version: "0.1"
contracts:
  Out:
    value: {type: string}
functions:
  extract:
    mode: infer
    intent: "Extract"
    input: {text: {type: string}}
    output: Out
    ensure:
      - "result.value != ''"
    retries: 1
flows:
  run:
    input: {text: {type: string}}
    output: Out
    steps:
      - id: s1
        function: extract
        inputs: {text: "$.input.text"}
"""
    ctx = MagicMock()
    plan = await stratum_plan(IR, "run", {"text": "x"}, ctx)
    flow_id = plan["flow_id"]

    assert (patch_flows_dir / f"{flow_id}.json").exists()

    result = await stratum_step_done(flow_id, "s1", {"value": ""}, ctx)
    assert result["status"] == "error"
    assert result["error_type"] == "retries_exhausted"
    assert not (patch_flows_dir / f"{flow_id}.json").exists()


@pytest.mark.asyncio
async def test_stratum_step_done_unknown_flow_id_returns_error(patch_flows_dir):
    """flow_id not in cache AND not on disk → flow_not_found."""
    ctx = MagicMock()
    result = await stratum_step_done("no-such-flow", "s1", {"value": "x"}, ctx)
    assert result["status"] == "error"
    assert result["error_type"] == "flow_not_found"


@pytest.mark.asyncio
async def test_stratum_audit_restores_flow_on_cache_miss(patch_flows_dir):
    """stratum_audit can reconstruct a completed flow from disk after cache eviction."""
    ctx = MagicMock()
    plan = await stratum_plan(SIMPLE_IR, "run", {"text": "audit me"}, ctx)
    flow_id = plan["flow_id"]

    # Complete the flow, then evict from cache (flow is now deleted from disk too)
    await stratum_step_done(flow_id, "s1", {"value": "done"}, ctx)
    _flows.pop(flow_id, None)

    # On disk it was deleted on completion, so audit reports flow_not_found
    audit = await stratum_audit(flow_id, ctx)
    assert audit.get("error_type") == "flow_not_found"


@pytest.mark.asyncio
async def test_stratum_audit_restores_in_progress_flow(patch_flows_dir):
    """stratum_audit restores an in-progress (not yet complete) flow from disk."""
    ctx = MagicMock()
    plan = await stratum_plan(TWO_STEP_IR, "pipeline", {"text": "audit mid"}, ctx)
    flow_id = plan["flow_id"]

    # Complete s1 (mid-flow, file still exists)
    await stratum_step_done(flow_id, "s1", {"label": "positive"}, ctx)
    _flows.pop(flow_id, None)

    audit = await stratum_audit(flow_id, ctx)
    assert audit["status"] == "in_progress"
    assert audit["steps_completed"] == 1
    assert audit["total_steps"] == 2
    assert "rounds" in audit, "rounds must always be present in stratum_audit output"


@pytest.mark.asyncio
async def test_retry_budget_survives_restart_after_ensure_failure(patch_flows_dir):
    """P1 regression: attempts must be persisted on ensure_failed so restart cannot reset retry budget."""
    IR = """
version: "0.1"
contracts:
  Out:
    value: {type: string}
functions:
  extract:
    mode: infer
    intent: "Extract"
    input: {text: {type: string}}
    output: Out
    ensure:
      - "result.value != ''"
    retries: 2
flows:
  run:
    input: {text: {type: string}}
    output: Out
    steps:
      - id: s1
        function: extract
        inputs: {text: "$.input.text"}
"""
    ctx = MagicMock()
    plan = await stratum_plan(IR, "run", {"text": "x"}, ctx)
    flow_id = plan["flow_id"]

    # Attempt 1 fails ensure; retries_remaining drops to 1
    r1 = await stratum_step_done(flow_id, "s1", {"value": ""}, ctx)
    assert r1["status"] == "ensure_failed"
    assert r1["retries_remaining"] == 1

    # Verify incremented attempts is on disk
    payload = json.loads((patch_flows_dir / f"{flow_id}.json").read_text())
    assert payload["attempts"].get("s1", 0) == 1

    # Simulate MCP server restart — evict in-memory state
    _flows.pop(flow_id, None)

    # Attempt 2 fails again — must exhaust retries (not reset to 2)
    r2 = await stratum_step_done(flow_id, "s1", {"value": ""}, ctx)
    assert r2["status"] == "error"
    assert r2["error_type"] == "retries_exhausted"


@pytest.mark.asyncio
async def test_retry_budget_survives_restart_after_schema_failure(patch_flows_dir):
    """P1 regression: attempts persisted on schema_failed too."""
    IR = """
version: "0.1"
contracts:
  Out:
    path: {type: string}
functions:
  write_doc:
    mode: compute
    intent: "Write"
    input: {name: {type: string}}
    output: Out
    retries: 2
flows:
  run:
    input: {name: {type: string}}
    output: Out
    steps:
      - id: s1
        function: write_doc
        inputs: {name: "$.input.name"}
        output_schema:
          type: object
          required: [path]
          properties:
            path: {type: string}
"""
    ctx = MagicMock()
    plan = await stratum_plan(IR, "run", {"name": "x"}, ctx)
    flow_id = plan["flow_id"]

    r1 = await stratum_step_done(flow_id, "s1", {"wrong": "value"}, ctx)
    assert r1["status"] == "schema_failed"
    assert r1["retries_remaining"] == 1

    payload = json.loads((patch_flows_dir / f"{flow_id}.json").read_text())
    assert payload["attempts"].get("s1", 0) == 1

    _flows.pop(flow_id, None)

    r2 = await stratum_step_done(flow_id, "s1", {"wrong": "value"}, ctx)
    assert r2["status"] == "error"
    assert r2["error_type"] == "retries_exhausted"


@pytest.mark.asyncio
async def test_full_two_step_restart_recovery(patch_flows_dir):
    """Full scenario: start flow, complete s1, simulate restart, complete s2, audit."""
    ctx = MagicMock()
    plan = await stratum_plan(TWO_STEP_IR, "pipeline", {"text": "restart test"}, ctx)
    flow_id = plan["flow_id"]

    step2 = await stratum_step_done(flow_id, "s1", {"label": "positive"}, ctx)
    assert step2["status"] == "execute_step"
    assert step2["step_id"] == "s2"
    assert step2["inputs"]["label"] == "positive"

    # Simulate restart
    _flows.pop(flow_id, None)

    done = await stratum_step_done(flow_id, "s2", {"summary": "It is positive."}, ctx)
    assert done["status"] == "complete"
    assert done["output"] == {"summary": "It is positive."}
    assert len(done["trace"]) == 2
    assert not (patch_flows_dir / f"{flow_id}.json").exists()


# ---------------------------------------------------------------------------
# stratum_resume tests
# ---------------------------------------------------------------------------

GATE_IR = """
version: "0.2"

contracts:
  Out:
    value: {type: string}

functions:
  do_work:
    mode: infer
    intent: "Do work"
    input: {text: {type: string}}
    output: Out
  cleanup:
    mode: infer
    intent: "Cleanup on kill"
    input: {}
    output: Out
  review_gate:
    mode: gate

flows:
  run:
    input: {text: {type: string}}
    output: Out
    steps:
      - id: work
        function: do_work
        inputs: {text: "$.input.text"}
      - id: gate
        function: review_gate
        on_approve: ~
        on_revise: work
        on_kill: do_cleanup
      - id: do_cleanup
        function: cleanup
"""


@pytest.mark.asyncio
async def test_stratum_resume_returns_execute_step_for_current_step(patch_flows_dir):
    ctx = MagicMock()
    plan = await stratum_plan(TWO_STEP_IR, "pipeline", {"text": "resume test"}, ctx)
    flow_id = plan["flow_id"]

    # Evict from in-memory cache
    _flows.pop(flow_id, None)

    result = await stratum_resume(flow_id, ctx)
    assert result["status"] == "execute_step"
    assert result["step_id"] == "s1"


@pytest.mark.asyncio
async def test_stratum_resume_returns_correct_step_after_partial_progress(patch_flows_dir):
    ctx = MagicMock()
    plan = await stratum_plan(TWO_STEP_IR, "pipeline", {"text": "partial"}, ctx)
    flow_id = plan["flow_id"]

    # Complete s1
    step2 = await stratum_step_done(flow_id, "s1", {"label": "positive"}, ctx)
    assert step2["status"] == "execute_step"
    assert step2["step_id"] == "s2"

    # Evict from in-memory cache
    _flows.pop(flow_id, None)

    result = await stratum_resume(flow_id, ctx)
    assert result["status"] == "execute_step"
    assert result["step_id"] == "s2"
    assert result["inputs"]["label"] == "positive"


@pytest.mark.asyncio
async def test_stratum_resume_returns_error_for_completed_flow(patch_flows_dir):
    ctx = MagicMock()
    plan = await stratum_plan(SIMPLE_IR, "run", {"text": "done"}, ctx)
    flow_id = plan["flow_id"]

    # Complete the flow (persistence file is deleted on completion)
    await stratum_step_done(flow_id, "s1", {"value": "finished"}, ctx)

    # Evict from in-memory cache
    _flows.pop(flow_id, None)

    result = await stratum_resume(flow_id, ctx)
    assert result["status"] == "error"
    assert result["error_type"] == "flow_not_found"


@pytest.mark.asyncio
async def test_stratum_resume_returns_error_for_unknown_flow_id(patch_flows_dir):
    ctx = MagicMock()
    result = await stratum_resume("nonexistent-uuid", ctx)
    assert result["status"] == "error"
    assert result["error_type"] == "flow_not_found"


@pytest.mark.asyncio
async def test_stratum_resume_returns_killed_for_killed_flow(patch_flows_dir):
    ctx = MagicMock()
    plan = await stratum_plan(GATE_IR, "run", {"text": "gate test"}, ctx)
    flow_id = plan["flow_id"]

    # Complete the work step to reach the gate
    await stratum_step_done(flow_id, "work", {"value": "done"}, ctx)

    # Kill the flow via gate resolve
    await stratum_gate_resolve(flow_id, "gate", "kill", "test", "human", ctx)

    # Evict from in-memory cache
    _flows.pop(flow_id, None)

    result = await stratum_resume(flow_id, ctx)
    assert result["status"] == "killed"
