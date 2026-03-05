"""Contract tests for stratum-mcp query and gate CLI subcommands.

These tests verify that:
- query output conforms to the versioned JSON schemas in contracts/
- gate mutations persist correctly and are idempotent
- conflict and error exits use the documented codes
"""
from __future__ import annotations

import json
import sys
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import pytest
from jsonschema import Draft202012Validator

from stratum_mcp.server import _cmd_query, _cmd_gate
from stratum_mcp.executor import (
    create_flow_state, persist_flow, restore_flow, _FLOWS_DIR,
)
from stratum_mcp.spec import parse_and_validate


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_GATE_SPEC = """\
version: "0.2"
functions:
  impl:
    mode: infer
    intent: Implement the feature
    input: {}
    output: ImplResult
  review:
    mode: gate
    intent: Review the work
contracts:
  ImplResult:
    output: {type: string}
flows:
  main:
    input: {}
    output: ImplResult
    steps:
      - id: impl_step
        function: impl
        inputs: {}
      - id: review_gate
        function: review
        on_approve: null
        on_revise: impl_step
        on_kill: null
"""

_SIMPLE_SPEC = """\
version: "0.1"
functions:
  build:
    mode: infer
    intent: Build the project
    input: {}
    output: BuildResult
contracts:
  BuildResult:
    output: {type: string}
flows:
  main:
    input: {}
    output: BuildResult
    steps:
      - id: build_step
        function: build
        inputs: {}
"""

_CONTRACTS_DIR = Path(__file__).parent.parent.parent / "contracts"


def _load_schema(name: str) -> dict:
    return json.loads((_CONTRACTS_DIR / name).read_text())


def _make_flow(spec_yaml: str, tmp_path: Path) -> str:
    """Create and persist a flow, returning its flow_id."""
    spec = parse_and_validate(spec_yaml)
    state = create_flow_state(spec, "main", {}, raw_spec=spec_yaml)
    with patch("stratum_mcp.executor._FLOWS_DIR", tmp_path / ".stratum" / "flows"):
        persist_flow(state)
    return state.flow_id


def _advance_to_gate(spec_yaml: str, tmp_path: Path) -> str:
    """Create a flow, complete the first step, leaving it at the gate."""
    from stratum_mcp.executor import process_step_result
    spec = parse_and_validate(spec_yaml)
    state = create_flow_state(spec, "main", {}, raw_spec=spec_yaml)
    # Complete the impl step
    process_step_result(state, "impl_step", {"output": "done"})
    flows_dir = tmp_path / ".stratum" / "flows"
    with patch("stratum_mcp.executor._FLOWS_DIR", flows_dir):
        persist_flow(state)
    return state.flow_id


def _capture_query(args: list[str], flows_dir: Path) -> tuple[str, int]:
    """Run _cmd_query, return (stdout, exit_code)."""
    buf = StringIO()
    with patch("stratum_mcp.executor._FLOWS_DIR", flows_dir):
        with patch("sys.stdout", buf):
            try:
                _cmd_query(args)
                return buf.getvalue(), 0
            except SystemExit as e:
                return buf.getvalue(), int(e.code or 0)


def _capture_gate(args: list[str], flows_dir: Path) -> tuple[str, int]:
    """Run _cmd_gate, return (stdout, exit_code)."""
    buf = StringIO()
    with patch("stratum_mcp.executor._FLOWS_DIR", flows_dir):
        with patch("sys.stdout", buf):
            try:
                _cmd_gate(args)
                return buf.getvalue(), 0
            except SystemExit as e:
                return buf.getvalue(), int(e.code or 0)


# ---------------------------------------------------------------------------
# query flows — schema conformance
# ---------------------------------------------------------------------------

def test_query_flows_empty(tmp_path):
    stdout, code = _capture_query(["flows"], tmp_path / ".stratum" / "flows")
    assert code == 0
    data = json.loads(stdout)
    assert data == []


def test_query_flows_output_matches_schema(tmp_path):
    flows_dir = tmp_path / ".stratum" / "flows"
    _make_flow(_SIMPLE_SPEC, tmp_path)
    stdout, code = _capture_query(["flows"], flows_dir)
    assert code == 0
    data = json.loads(stdout)
    schema = _load_schema("query-flows.v1.schema.json")
    Draft202012Validator(schema).validate(data)


def test_query_flows_status_running(tmp_path):
    flows_dir = tmp_path / ".stratum" / "flows"
    _make_flow(_SIMPLE_SPEC, tmp_path)
    stdout, _ = _capture_query(["flows"], flows_dir)
    data = json.loads(stdout)
    assert data[0]["status"] == "running"
    assert data[0]["_schema_version"] == "1"


def test_query_flows_status_awaiting_gate(tmp_path):
    flows_dir = tmp_path / ".stratum" / "flows"
    _advance_to_gate(_GATE_SPEC, tmp_path)
    stdout, _ = _capture_query(["flows"], flows_dir)
    data = json.loads(stdout)
    assert data[0]["status"] == "awaiting_gate"


# ---------------------------------------------------------------------------
# query flow <id> — schema conformance
# ---------------------------------------------------------------------------

def test_query_flow_output_matches_schema(tmp_path):
    flows_dir = tmp_path / ".stratum" / "flows"
    flow_id = _make_flow(_SIMPLE_SPEC, tmp_path)
    stdout, code = _capture_query(["flow", flow_id], flows_dir)
    assert code == 0
    data = json.loads(stdout)
    schema = _load_schema("flow-state.v1.schema.json")
    Draft202012Validator(schema).validate(data)


def test_query_flow_not_found_exits_1(tmp_path):
    flows_dir = tmp_path / ".stratum" / "flows"
    stdout, code = _capture_query(["flow", "nonexistent-id"], flows_dir)
    assert code == 1
    data = json.loads(stdout)
    assert data["error"]["code"] == "NOT_FOUND"


# ---------------------------------------------------------------------------
# query gates — schema conformance
# ---------------------------------------------------------------------------

def test_query_gates_empty_when_no_flows(tmp_path):
    stdout, code = _capture_query(["gates"], tmp_path / ".stratum" / "flows")
    assert code == 0
    assert json.loads(stdout) == []


def test_query_gates_output_matches_schema(tmp_path):
    flows_dir = tmp_path / ".stratum" / "flows"
    _advance_to_gate(_GATE_SPEC, tmp_path)
    stdout, code = _capture_query(["gates"], flows_dir)
    assert code == 0
    data = json.loads(stdout)
    schema = _load_schema("query-gates.v1.schema.json")
    Draft202012Validator(schema).validate(data)
    assert len(data) == 1
    assert data[0]["step_id"] == "review_gate"


def test_query_gates_empty_when_no_gate_pending(tmp_path):
    flows_dir = tmp_path / ".stratum" / "flows"
    _make_flow(_SIMPLE_SPEC, tmp_path)
    stdout, _ = _capture_query(["gates"], flows_dir)
    assert json.loads(stdout) == []


# ---------------------------------------------------------------------------
# gate approve — persists state
# ---------------------------------------------------------------------------

def test_gate_approve_persists_state(tmp_path):
    flows_dir = tmp_path / ".stratum" / "flows"
    flow_id = _advance_to_gate(_GATE_SPEC, tmp_path)
    stdout, code = _capture_gate(
        ["approve", flow_id, "review_gate", "--note", "LGTM"],
        flows_dir,
    )
    assert code == 0
    result = json.loads(stdout)
    assert result["ok"] is True
    assert result["outcome"] == "approve"
    assert result["result"] == "complete"

    # Verify state persisted: flow is now complete
    with patch("stratum_mcp.executor._FLOWS_DIR", flows_dir):
        state = restore_flow(flow_id)
    assert state.current_idx >= len(state.ordered_steps)


def test_gate_approve_output_matches_schema(tmp_path):
    flows_dir = tmp_path / ".stratum" / "flows"
    flow_id = _advance_to_gate(_GATE_SPEC, tmp_path)
    stdout, code = _capture_gate(["approve", flow_id, "review_gate"], flows_dir)
    assert code == 0
    schema = _load_schema("gate-mutation.v1.schema.json")
    Draft202012Validator(schema).validate(json.loads(stdout))


# ---------------------------------------------------------------------------
# gate reject — persists state
# ---------------------------------------------------------------------------

def test_gate_reject_persists_state(tmp_path):
    flows_dir = tmp_path / ".stratum" / "flows"
    flow_id = _advance_to_gate(_GATE_SPEC, tmp_path)
    stdout, code = _capture_gate(
        ["reject", flow_id, "review_gate", "--note", "not ready"],
        flows_dir,
    )
    assert code == 0
    result = json.loads(stdout)
    assert result["ok"] is True
    assert result["outcome"] == "kill"
    assert result["result"] == "killed"

    with patch("stratum_mcp.executor._FLOWS_DIR", flows_dir):
        state = restore_flow(flow_id)
    assert state.terminal_status == "killed"


# ---------------------------------------------------------------------------
# idempotency — double-approve returns exit code 2
# ---------------------------------------------------------------------------

def test_gate_double_approve_returns_conflict(tmp_path):
    flows_dir = tmp_path / ".stratum" / "flows"
    flow_id = _advance_to_gate(_GATE_SPEC, tmp_path)
    _capture_gate(["approve", flow_id, "review_gate"], flows_dir)
    stdout, code = _capture_gate(["approve", flow_id, "review_gate"], flows_dir)
    assert code == 2
    data = json.loads(stdout)
    assert data["conflict"] is True


def test_gate_double_reject_returns_conflict(tmp_path):
    flows_dir = tmp_path / ".stratum" / "flows"
    flow_id = _advance_to_gate(_GATE_SPEC, tmp_path)
    _capture_gate(["reject", flow_id, "review_gate"], flows_dir)
    stdout, code = _capture_gate(["reject", flow_id, "review_gate"], flows_dir)
    assert code == 2
    assert json.loads(stdout)["conflict"] is True


# ---------------------------------------------------------------------------
# error cases
# ---------------------------------------------------------------------------

def test_gate_approve_nonexistent_flow_exits_1(tmp_path):
    flows_dir = tmp_path / ".stratum" / "flows"
    stdout, code = _capture_gate(["approve", "no-such-flow", "step_id"], flows_dir)
    assert code == 1
    assert json.loads(stdout)["error"]["code"] == "NOT_FOUND"


def test_gate_approve_wrong_step_id_exits_2(tmp_path):
    """Wrong step_id means gate already advanced — conflict, not error."""
    flows_dir = tmp_path / ".stratum" / "flows"
    flow_id = _advance_to_gate(_GATE_SPEC, tmp_path)
    stdout, code = _capture_gate(["approve", flow_id, "impl_step"], flows_dir)
    assert code == 2
    assert json.loads(stdout)["conflict"] is True
