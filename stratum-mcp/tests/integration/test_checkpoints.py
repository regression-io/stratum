"""Tests for stratum_commit / stratum_revert checkpoint tools."""
import json
import pytest
from unittest.mock import MagicMock

import stratum_mcp.executor as executor_mod
from stratum_mcp.executor import (
    commit_checkpoint,
    revert_checkpoint,
    create_flow_state,
    persist_flow,
)
from stratum_mcp.server import stratum_plan, stratum_step_done, stratum_commit, stratum_revert, _flows
from stratum_mcp.spec import parse_and_validate


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
    retries: 3
  summarize:
    mode: infer
    intent: "Summarize"
    input: {label: {type: string}}
    output: Step2Out
    ensure:
      - "result.summary != ''"
    retries: 3
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

SIMPLE_IR = """
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
    retries: 3
flows:
  run:
    input: {text: {type: string}}
    output: Out
    steps:
      - id: s1
        function: extract
        inputs: {text: "$.input.text"}
"""


@pytest.fixture(autouse=True)
def patch_flows_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(executor_mod, "_FLOWS_DIR", tmp_path / "flows")
    yield tmp_path / "flows"


# ---------------------------------------------------------------------------
# Unit-level: commit_checkpoint / revert_checkpoint
# ---------------------------------------------------------------------------

def test_commit_stores_snapshot():
    spec = parse_and_validate(SIMPLE_IR)
    state = create_flow_state(spec, "run", {"text": "hi"}, raw_spec=SIMPLE_IR)
    state.step_outputs["s1"] = {"value": "found"}
    state.attempts["s1"] = 1
    state.current_idx = 1

    commit_checkpoint(state, "after_s1")

    assert "after_s1" in state.checkpoints
    snap = state.checkpoints["after_s1"]
    assert snap["step_outputs"] == {"s1": {"value": "found"}}
    assert snap["attempts"] == {"s1": 1}
    assert snap["current_idx"] == 1


def test_commit_snapshot_is_deep_copy():
    """P2 regression: mutating nested output after commit must not alter the snapshot."""
    spec = parse_and_validate(SIMPLE_IR)
    state = create_flow_state(spec, "run", {"text": "hi"}, raw_spec=SIMPLE_IR)

    state.step_outputs["s1"] = {"nested": {"x": 1}}
    commit_checkpoint(state, "cp")

    # Mutate nested object in live state after commit
    state.step_outputs["s1"]["nested"]["x"] = 999

    # Snapshot must still hold the original value
    assert state.checkpoints["cp"]["step_outputs"]["s1"]["nested"]["x"] == 1


def test_revert_snapshot_is_deep_copy():
    """P2 regression: after revert, mutating live state must not alter the checkpoint."""
    spec = parse_and_validate(SIMPLE_IR)
    state = create_flow_state(spec, "run", {"text": "hi"}, raw_spec=SIMPLE_IR)

    state.step_outputs["s1"] = {"nested": {"x": 1}}
    commit_checkpoint(state, "cp")

    state.step_outputs["s1"]["nested"]["x"] = 999
    revert_checkpoint(state, "cp")

    # Reverted value must be the original 1, not the mutated 999
    assert state.step_outputs["s1"]["nested"]["x"] == 1

    # And subsequent mutation of live state must not corrupt the checkpoint
    state.step_outputs["s1"]["nested"]["x"] = 42
    assert state.checkpoints["cp"]["step_outputs"]["s1"]["nested"]["x"] == 1


def test_commit_overwrites_existing_label():
    spec = parse_and_validate(SIMPLE_IR)
    state = create_flow_state(spec, "run", {"text": "hi"}, raw_spec=SIMPLE_IR)

    state.step_outputs["s1"] = {"value": "v1"}
    commit_checkpoint(state, "cp")

    state.step_outputs["s1"] = {"value": "v2"}
    commit_checkpoint(state, "cp")

    assert state.checkpoints["cp"]["step_outputs"]["s1"] == {"value": "v2"}


def test_revert_restores_snapshot():
    spec = parse_and_validate(SIMPLE_IR)
    state = create_flow_state(spec, "run", {"text": "hi"}, raw_spec=SIMPLE_IR)

    # Checkpoint at initial state
    commit_checkpoint(state, "start")

    # Advance state
    state.step_outputs["s1"] = {"value": "found"}
    state.attempts["s1"] = 2
    state.current_idx = 1

    result = revert_checkpoint(state, "start")

    assert result is True
    assert state.step_outputs == {}
    assert state.attempts == {}
    assert state.current_idx == 0
    assert state.records == []


def test_revert_returns_false_for_unknown_label():
    spec = parse_and_validate(SIMPLE_IR)
    state = create_flow_state(spec, "run", {"text": "hi"}, raw_spec=SIMPLE_IR)
    assert revert_checkpoint(state, "nonexistent") is False


def test_commit_persists_checkpoints_to_disk(patch_flows_dir):
    spec = parse_and_validate(SIMPLE_IR)
    state = create_flow_state(spec, "run", {"text": "hi"}, raw_spec=SIMPLE_IR)
    commit_checkpoint(state, "cp1")

    from stratum_mcp.executor import restore_flow
    restored = restore_flow(state.flow_id)
    assert restored is not None
    assert "cp1" in restored.checkpoints


def test_revert_persists_reverted_state_to_disk(patch_flows_dir):
    spec = parse_and_validate(SIMPLE_IR)
    state = create_flow_state(spec, "run", {"text": "hi"}, raw_spec=SIMPLE_IR)
    commit_checkpoint(state, "start")

    state.step_outputs["s1"] = {"value": "x"}
    state.current_idx = 1
    persist_flow(state)

    revert_checkpoint(state, "start")

    from stratum_mcp.executor import restore_flow
    restored = restore_flow(state.flow_id)
    assert restored is not None
    assert restored.current_idx == 0
    assert restored.step_outputs == {}


# ---------------------------------------------------------------------------
# P2 regression: label normalization
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_commit_with_padded_label_is_revertable_with_trimmed_label():
    """P2 regression: ' cp ' stored as 'cp'; stratum_revert('cp') must find it."""
    ctx = MagicMock()
    plan = await stratum_plan(SIMPLE_IR, "run", {"text": "hi"}, ctx)
    flow_id = plan["flow_id"]

    commit_result = await stratum_commit(flow_id, "  cp  ", ctx)
    assert commit_result["status"] == "committed"
    assert commit_result["label"] == "cp"          # normalized in response
    assert "cp" in commit_result["checkpoints"]    # stored as trimmed key

    revert_result = await stratum_revert(flow_id, "cp", ctx)
    assert revert_result["status"] == "execute_step"


@pytest.mark.asyncio
async def test_revert_with_padded_label_finds_trimmed_checkpoint():
    """P2 regression: stratum_revert(' cp ') must find a checkpoint stored as 'cp'."""
    ctx = MagicMock()
    plan = await stratum_plan(SIMPLE_IR, "run", {"text": "hi"}, ctx)
    flow_id = plan["flow_id"]

    await stratum_commit(flow_id, "cp", ctx)

    revert_result = await stratum_revert(flow_id, "  cp  ", ctx)
    assert revert_result["status"] == "execute_step"


# ---------------------------------------------------------------------------
# Server-level: stratum_commit / stratum_revert MCP tools
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_stratum_commit_returns_committed_status():
    ctx = MagicMock()
    plan = await stratum_plan(SIMPLE_IR, "run", {"text": "hi"}, ctx)
    flow_id = plan["flow_id"]

    result = await stratum_commit(flow_id, "initial", ctx)
    assert result["status"] == "committed"
    assert result["flow_id"] == flow_id
    assert result["label"] == "initial"
    assert "initial" in result["checkpoints"]


@pytest.mark.asyncio
async def test_stratum_commit_unknown_flow_returns_error():
    ctx = MagicMock()
    result = await stratum_commit("no-such-flow", "cp", ctx)
    assert result["status"] == "error"
    assert result["error_type"] == "flow_not_found"


@pytest.mark.asyncio
async def test_stratum_commit_empty_label_returns_error():
    ctx = MagicMock()
    plan = await stratum_plan(SIMPLE_IR, "run", {"text": "hi"}, ctx)
    result = await stratum_commit(plan["flow_id"], "  ", ctx)
    assert result["status"] == "error"
    assert result["error_type"] == "invalid_label"


@pytest.mark.asyncio
async def test_stratum_revert_rolls_back_and_returns_step():
    ctx = MagicMock()
    plan = await stratum_plan(TWO_STEP_IR, "pipeline", {"text": "test"}, ctx)
    flow_id = plan["flow_id"]

    # Commit before s1
    await stratum_commit(flow_id, "before_s1", ctx)

    # Complete s1
    step2 = await stratum_step_done(flow_id, "s1", {"label": "positive"}, ctx)
    assert step2["step_id"] == "s2"

    # Revert to before s1 — should get s1 again
    reverted = await stratum_revert(flow_id, "before_s1", ctx)
    assert reverted["status"] == "execute_step"
    assert reverted["step_id"] == "s1"
    assert reverted["reverted_to"] == "before_s1"
    assert reverted["inputs"] == {"text": "test"}


@pytest.mark.asyncio
async def test_stratum_revert_clears_step_outputs():
    ctx = MagicMock()
    plan = await stratum_plan(TWO_STEP_IR, "pipeline", {"text": "test"}, ctx)
    flow_id = plan["flow_id"]

    await stratum_commit(flow_id, "empty", ctx)
    await stratum_step_done(flow_id, "s1", {"label": "positive"}, ctx)

    await stratum_revert(flow_id, "empty", ctx)

    state = _flows[flow_id]
    assert state.step_outputs == {}
    assert state.current_idx == 0


@pytest.mark.asyncio
async def test_stratum_revert_unknown_label_returns_error():
    ctx = MagicMock()
    plan = await stratum_plan(SIMPLE_IR, "run", {"text": "hi"}, ctx)
    flow_id = plan["flow_id"]
    await stratum_commit(flow_id, "real", ctx)

    result = await stratum_revert(flow_id, "ghost", ctx)
    assert result["status"] == "error"
    assert result["error_type"] == "checkpoint_not_found"
    assert "real" in result["available"]


@pytest.mark.asyncio
async def test_stratum_revert_unknown_flow_returns_error():
    ctx = MagicMock()
    result = await stratum_revert("no-such-flow", "cp", ctx)
    assert result["status"] == "error"
    assert result["error_type"] == "flow_not_found"


@pytest.mark.asyncio
async def test_stratum_commit_restores_after_cache_eviction(patch_flows_dir):
    """Checkpoint survives MCP restart: commit → evict → revert still works."""
    ctx = MagicMock()
    plan = await stratum_plan(TWO_STEP_IR, "pipeline", {"text": "restart"}, ctx)
    flow_id = plan["flow_id"]

    await stratum_commit(flow_id, "pre_s1", ctx)
    await stratum_step_done(flow_id, "s1", {"label": "negative"}, ctx)

    # Simulate restart
    _flows.pop(flow_id, None)

    # Revert restores from disk — should land back on s1
    reverted = await stratum_revert(flow_id, "pre_s1", ctx)
    assert reverted["status"] == "execute_step"
    assert reverted["step_id"] == "s1"


@pytest.mark.asyncio
async def test_full_commit_revert_retry_flow(patch_flows_dir):
    """Full scenario: commit before s2, s2 fails ensure, revert, retry s2 with better result."""
    ctx = MagicMock()
    plan = await stratum_plan(TWO_STEP_IR, "pipeline", {"text": "hello"}, ctx)
    flow_id = plan["flow_id"]

    # Complete s1
    await stratum_step_done(flow_id, "s1", {"label": "positive"}, ctx)

    # Commit before attempting s2
    commit_result = await stratum_commit(flow_id, "pre_s2", ctx)
    assert commit_result["status"] == "committed"
    assert commit_result["current_step_id"] == "s2"

    # s2 fails ensure (empty summary)
    fail = await stratum_step_done(flow_id, "s2", {"summary": ""}, ctx)
    assert fail["status"] == "ensure_failed"

    # Revert to pre_s2 — attempts counter reset, fresh retry
    reverted = await stratum_revert(flow_id, "pre_s2", ctx)
    assert reverted["step_id"] == "s2"

    # Check attempts were rolled back
    state = _flows[flow_id]
    assert state.attempts.get("s2", 0) == 0

    # Now succeed
    done = await stratum_step_done(flow_id, "s2", {"summary": "It is positive."}, ctx)
    assert done["status"] == "complete"
    assert done["output"] == {"summary": "It is positive."}


@pytest.mark.asyncio
async def test_multiple_checkpoints_independent():
    """Two checkpoints at different points are independently restorable."""
    ctx = MagicMock()
    plan = await stratum_plan(TWO_STEP_IR, "pipeline", {"text": "x"}, ctx)
    flow_id = plan["flow_id"]

    cp1 = await stratum_commit(flow_id, "cp1", ctx)
    assert cp1["step_number"] == 1

    await stratum_step_done(flow_id, "s1", {"label": "positive"}, ctx)

    cp2 = await stratum_commit(flow_id, "cp2", ctx)
    assert cp2["step_number"] == 2
    assert set(cp2["checkpoints"]) == {"cp1", "cp2"}

    # Revert to cp1
    r = await stratum_revert(flow_id, "cp1", ctx)
    assert r["step_id"] == "s1"

    # Revert to cp2 (re-advance past cp1)
    await stratum_step_done(flow_id, "s1", {"label": "negative"}, ctx)
    r2 = await stratum_revert(flow_id, "cp2", ctx)
    assert r2["step_id"] == "s2"
    state = _flows[flow_id]
    # s1 output from original run is preserved in cp2
    assert state.step_outputs.get("s1") == {"label": "positive"}
