"""Tests for RunWorkspace — .stratum/runs/{run-id}/ output passing."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import json
import time
import pytest
from pathlib import Path
from stratum import RunWorkspace
from stratum.exceptions import StratumError


# ---------------------------------------------------------------------------
# RunWorkspace.create()
# ---------------------------------------------------------------------------

def test_create_makes_run_directory(tmp_path):
    ws = RunWorkspace.create(tmp_path, "my-pipeline")
    assert ws.run_dir.exists()
    assert ws.run_dir.is_dir()


def test_create_directory_under_stratum_runs(tmp_path):
    ws = RunWorkspace.create(tmp_path, "my-pipeline")
    assert ws.run_dir.parent == tmp_path / ".stratum" / "runs"


def test_create_writes_manifest(tmp_path):
    ws = RunWorkspace.create(tmp_path, "my-pipeline")
    manifest_path = ws.run_dir / "manifest.json"
    assert manifest_path.exists()
    manifest = json.loads(manifest_path.read_text())
    assert manifest["run_id"]   == ws.run_id
    assert manifest["pipeline"] == "my-pipeline"
    assert "created_at" in manifest


def test_create_generates_unique_run_ids(tmp_path):
    ws1 = RunWorkspace.create(tmp_path, "p")
    ws2 = RunWorkspace.create(tmp_path, "p")
    assert ws1.run_id != ws2.run_id


def test_create_exposes_pipeline_name(tmp_path):
    ws = RunWorkspace.create(tmp_path, "feature-lifecycle")
    assert ws.pipeline_name == "feature-lifecycle"


def test_create_run_id_is_non_empty_string(tmp_path):
    ws = RunWorkspace.create(tmp_path, "p")
    assert isinstance(ws.run_id, str)
    assert len(ws.run_id) > 0


# ---------------------------------------------------------------------------
# RunWorkspace.open()
# ---------------------------------------------------------------------------

def test_open_reads_manifest(tmp_path):
    created = RunWorkspace.create(tmp_path, "my-pipeline")
    opened  = RunWorkspace.open(created.run_dir)
    assert opened.run_id        == created.run_id
    assert opened.pipeline_name == created.pipeline_name
    assert opened.run_dir       == created.run_dir


def test_open_missing_directory_raises(tmp_path):
    with pytest.raises(StratumError, match="not found"):
        RunWorkspace.open(tmp_path / ".stratum" / "runs" / "nonexistent")


def test_open_missing_manifest_raises(tmp_path):
    run_dir = tmp_path / ".stratum" / "runs" / "abc123"
    run_dir.mkdir(parents=True)
    with pytest.raises(StratumError, match="manifest not found"):
        RunWorkspace.open(run_dir)


# ---------------------------------------------------------------------------
# result_path / has_result / write_result / read_result
# ---------------------------------------------------------------------------

def test_result_path_convention(tmp_path):
    ws = RunWorkspace.create(tmp_path, "p")
    assert ws.result_path("discovery") == ws.run_dir / "discovery.json"


def test_has_result_false_before_write(tmp_path):
    ws = RunWorkspace.create(tmp_path, "p")
    assert not ws.has_result("discovery")


def test_has_result_true_after_write(tmp_path):
    ws = RunWorkspace.create(tmp_path, "p")
    ws.write_result("discovery", {"files": ["a.py"]})
    assert ws.has_result("discovery")


def test_write_and_read_result_roundtrip(tmp_path):
    ws   = RunWorkspace.create(tmp_path, "p")
    data = {"changed_files": ["src/foo.py"], "tests_pass": True}
    ws.write_result("implement", data)
    assert ws.read_result("implement") == data


def test_write_result_produces_valid_json(tmp_path):
    ws = RunWorkspace.create(tmp_path, "p")
    ws.write_result("discovery", {"risks": ["none"]})
    raw = (ws.run_dir / "discovery.json").read_text()
    assert json.loads(raw) == {"risks": ["none"]}


def test_write_result_is_idempotent(tmp_path):
    ws = RunWorkspace.create(tmp_path, "p")
    ws.write_result("discovery", {"v": 1})
    ws.write_result("discovery", {"v": 2})
    assert ws.read_result("discovery") == {"v": 2}


def test_read_missing_result_raises(tmp_path):
    ws = RunWorkspace.create(tmp_path, "p")
    with pytest.raises(StratumError, match="No result for phase 'discovery'"):
        ws.read_result("discovery")


# ---------------------------------------------------------------------------
# completed_phases()
# ---------------------------------------------------------------------------

def test_completed_phases_empty_initially(tmp_path):
    ws = RunWorkspace.create(tmp_path, "p")
    assert ws.completed_phases() == []


def test_completed_phases_lists_written_phases(tmp_path):
    ws = RunWorkspace.create(tmp_path, "p")
    ws.write_result("discovery", {})
    ws.write_result("implement", {})
    assert set(ws.completed_phases()) == {"discovery", "implement"}


def test_completed_phases_excludes_manifest(tmp_path):
    ws = RunWorkspace.create(tmp_path, "p")
    assert "manifest" not in ws.completed_phases()


# ---------------------------------------------------------------------------
# find_latest()
# ---------------------------------------------------------------------------

def test_find_latest_returns_none_when_no_runs(tmp_path):
    assert RunWorkspace.find_latest(tmp_path, "p") is None


def test_find_latest_returns_none_for_different_pipeline(tmp_path):
    RunWorkspace.create(tmp_path, "other-pipeline")
    assert RunWorkspace.find_latest(tmp_path, "my-pipeline") is None


def test_find_latest_returns_matching_run(tmp_path):
    ws = RunWorkspace.create(tmp_path, "my-pipeline")
    found = RunWorkspace.find_latest(tmp_path, "my-pipeline")
    assert found is not None
    assert found.run_id == ws.run_id


def test_find_latest_returns_most_recent(tmp_path):
    ws1 = RunWorkspace.create(tmp_path, "p")
    time.sleep(0.01)  # ensure distinct mtime
    ws2 = RunWorkspace.create(tmp_path, "p")
    found = RunWorkspace.find_latest(tmp_path, "p")
    assert found is not None
    assert found.run_id == ws2.run_id


# ---------------------------------------------------------------------------
# Path safety
# ---------------------------------------------------------------------------

def test_result_path_traversal_raises(tmp_path):
    ws = RunWorkspace.create(tmp_path, "p")
    with pytest.raises(StratumError, match="escape run directory"):
        ws.result_path("../escape")


def test_result_path_absolute_raises(tmp_path):
    ws = RunWorkspace.create(tmp_path, "p")
    with pytest.raises(StratumError, match="escape run directory"):
        ws.result_path("/etc/passwd")


def test_write_result_traversal_raises(tmp_path):
    ws = RunWorkspace.create(tmp_path, "p")
    with pytest.raises(StratumError, match="escape run directory"):
        ws.write_result("../escape", {"x": 1})


def test_has_result_traversal_raises(tmp_path):
    ws = RunWorkspace.create(tmp_path, "p")
    with pytest.raises(StratumError, match="escape run directory"):
        ws.has_result("../escape")


# ---------------------------------------------------------------------------
# Malformed manifest handling
# ---------------------------------------------------------------------------

def test_open_manifest_missing_run_id_raises(tmp_path):
    run_dir = tmp_path / ".stratum" / "runs" / "abc"
    run_dir.mkdir(parents=True)
    (run_dir / "manifest.json").write_text(json.dumps({"pipeline": "p"}))
    with pytest.raises(StratumError, match="missing field"):
        RunWorkspace.open(run_dir)


def test_open_manifest_missing_pipeline_raises(tmp_path):
    run_dir = tmp_path / ".stratum" / "runs" / "abc"
    run_dir.mkdir(parents=True)
    (run_dir / "manifest.json").write_text(json.dumps({"run_id": "abc"}))
    with pytest.raises(StratumError, match="missing field"):
        RunWorkspace.open(run_dir)


def test_open_corrupt_manifest_raises(tmp_path):
    run_dir = tmp_path / ".stratum" / "runs" / "abc"
    run_dir.mkdir(parents=True)
    (run_dir / "manifest.json").write_text("{ not valid json }")
    with pytest.raises(StratumError, match="not valid JSON"):
        RunWorkspace.open(run_dir)


# ---------------------------------------------------------------------------
# Corrupt result file handling
# ---------------------------------------------------------------------------

def test_read_result_corrupt_json_raises(tmp_path):
    ws = RunWorkspace.create(tmp_path, "p")
    (ws.run_dir / "discovery.json").write_text("{ not valid json }")
    with pytest.raises(StratumError, match="Corrupt result file"):
        ws.read_result("discovery")


def test_find_latest_ignores_directories_without_manifest(tmp_path):
    # Create a stray directory with no manifest
    stray = tmp_path / ".stratum" / "runs" / "stray"
    stray.mkdir(parents=True)
    ws = RunWorkspace.create(tmp_path, "p")
    found = RunWorkspace.find_latest(tmp_path, "p")
    assert found is not None
    assert found.run_id == ws.run_id


# ---------------------------------------------------------------------------
# Gate protocol — write_gate / read_gate
# ---------------------------------------------------------------------------

def test_gate_path_convention(tmp_path):
    ws = RunWorkspace.create(tmp_path, "p")
    assert ws.gate_path("pre_gate") == ws.run_dir / "pre_gate.gate"


def test_write_gate_creates_file(tmp_path):
    ws = RunWorkspace.create(tmp_path, "p")
    ws.write_gate("pre_gate")
    assert (ws.run_dir / "pre_gate.gate").exists()


def test_write_gate_stores_context(tmp_path):
    ws = RunWorkspace.create(tmp_path, "p")
    ws.write_gate("pre_gate", context={"risk": "high"})
    payload = json.loads((ws.run_dir / "pre_gate.gate").read_text())
    assert payload["phase"]          == "pre_gate"
    assert payload["context"]["risk"] == "high"
    assert "created_at" in payload


def test_write_gate_without_context(tmp_path):
    ws = RunWorkspace.create(tmp_path, "p")
    ws.write_gate("pre_gate")
    payload = json.loads((ws.run_dir / "pre_gate.gate").read_text())
    assert payload["context"] == {}


def test_read_gate_returns_payload(tmp_path):
    ws = RunWorkspace.create(tmp_path, "p")
    ws.write_gate("pre_gate", context={"approved": False})
    data = ws.read_gate("pre_gate")
    assert data["phase"] == "pre_gate"


def test_read_gate_missing_raises(tmp_path):
    ws = RunWorkspace.create(tmp_path, "p")
    with pytest.raises(StratumError, match="No gate for phase 'pre_gate'"):
        ws.read_gate("pre_gate")


def test_read_gate_corrupt_raises(tmp_path):
    ws = RunWorkspace.create(tmp_path, "p")
    (ws.run_dir / "pre_gate.gate").write_text("{ bad json }")
    with pytest.raises(StratumError, match="Corrupt gate file"):
        ws.read_gate("pre_gate")


# ---------------------------------------------------------------------------
# Gate protocol — is_gate_pending / approved / rejected
# ---------------------------------------------------------------------------

def test_is_gate_pending_false_before_write(tmp_path):
    ws = RunWorkspace.create(tmp_path, "p")
    assert not ws.is_gate_pending("pre_gate")


def test_is_gate_pending_true_after_write(tmp_path):
    ws = RunWorkspace.create(tmp_path, "p")
    ws.write_gate("pre_gate")
    assert ws.is_gate_pending("pre_gate")


def test_is_gate_pending_false_after_approval(tmp_path):
    ws = RunWorkspace.create(tmp_path, "p")
    ws.write_gate("pre_gate")
    ws.approve_gate("pre_gate")
    assert not ws.is_gate_pending("pre_gate")


def test_is_gate_pending_false_after_rejection(tmp_path):
    ws = RunWorkspace.create(tmp_path, "p")
    ws.write_gate("pre_gate")
    ws.reject_gate("pre_gate")
    assert not ws.is_gate_pending("pre_gate")


def test_is_gate_approved_false_before_approval(tmp_path):
    ws = RunWorkspace.create(tmp_path, "p")
    ws.write_gate("pre_gate")
    assert not ws.is_gate_approved("pre_gate")


def test_is_gate_approved_true_after_approval(tmp_path):
    ws = RunWorkspace.create(tmp_path, "p")
    ws.write_gate("pre_gate")
    ws.approve_gate("pre_gate")
    assert ws.is_gate_approved("pre_gate")


def test_is_gate_rejected_false_before_rejection(tmp_path):
    ws = RunWorkspace.create(tmp_path, "p")
    ws.write_gate("pre_gate")
    assert not ws.is_gate_rejected("pre_gate")


def test_is_gate_rejected_true_after_rejection(tmp_path):
    ws = RunWorkspace.create(tmp_path, "p")
    ws.write_gate("pre_gate")
    ws.reject_gate("pre_gate")
    assert ws.is_gate_rejected("pre_gate")


# ---------------------------------------------------------------------------
# Gate protocol — approve_gate / reject_gate
# ---------------------------------------------------------------------------

def test_approve_gate_writes_file(tmp_path):
    ws = RunWorkspace.create(tmp_path, "p")
    ws.write_gate("pre_gate")
    ws.approve_gate("pre_gate")
    assert (ws.run_dir / "pre_gate.gate.approved").exists()


def test_approve_gate_with_note(tmp_path):
    ws = RunWorkspace.create(tmp_path, "p")
    ws.write_gate("pre_gate")
    ws.approve_gate("pre_gate", note="looks good")
    payload = json.loads((ws.run_dir / "pre_gate.gate.approved").read_text())
    assert payload["note"]        == "looks good"
    assert "approved_at" in payload


def test_approve_gate_without_gate_raises(tmp_path):
    ws = RunWorkspace.create(tmp_path, "p")
    with pytest.raises(StratumError, match="no gate for phase"):
        ws.approve_gate("pre_gate")


def test_reject_gate_writes_file(tmp_path):
    ws = RunWorkspace.create(tmp_path, "p")
    ws.write_gate("pre_gate")
    ws.reject_gate("pre_gate")
    assert (ws.run_dir / "pre_gate.gate.rejected").exists()


def test_reject_gate_with_note(tmp_path):
    ws = RunWorkspace.create(tmp_path, "p")
    ws.write_gate("pre_gate")
    ws.reject_gate("pre_gate", note="needs more work")
    payload = json.loads((ws.run_dir / "pre_gate.gate.rejected").read_text())
    assert payload["note"]        == "needs more work"
    assert "rejected_at" in payload


def test_reject_gate_without_gate_raises(tmp_path):
    ws = RunWorkspace.create(tmp_path, "p")
    with pytest.raises(StratumError, match="no gate for phase"):
        ws.reject_gate("pre_gate")


def test_approve_gate_after_rejection_raises(tmp_path):
    ws = RunWorkspace.create(tmp_path, "p")
    ws.write_gate("pre_gate")
    ws.reject_gate("pre_gate")
    with pytest.raises(StratumError, match="already been rejected"):
        ws.approve_gate("pre_gate")


def test_reject_gate_after_approval_raises(tmp_path):
    ws = RunWorkspace.create(tmp_path, "p")
    ws.write_gate("pre_gate")
    ws.approve_gate("pre_gate")
    with pytest.raises(StratumError, match="already been approved"):
        ws.reject_gate("pre_gate")


def test_write_gate_clears_stale_approval(tmp_path):
    ws = RunWorkspace.create(tmp_path, "p")
    ws.write_gate("pre_gate")
    ws.approve_gate("pre_gate")
    assert ws.is_gate_approved("pre_gate")
    # Re-gate (retry/re-run) — stale approval must be cleared
    ws.write_gate("pre_gate")
    assert ws.is_gate_pending("pre_gate")
    assert not ws.is_gate_approved("pre_gate")


def test_write_gate_clears_stale_rejection(tmp_path):
    ws = RunWorkspace.create(tmp_path, "p")
    ws.write_gate("pre_gate")
    ws.reject_gate("pre_gate")
    assert ws.is_gate_rejected("pre_gate")
    # Re-gate — stale rejection must be cleared
    ws.write_gate("pre_gate")
    assert ws.is_gate_pending("pre_gate")
    assert not ws.is_gate_rejected("pre_gate")


# ---------------------------------------------------------------------------
# Gate protocol — pending_gates
# ---------------------------------------------------------------------------

def test_pending_gates_empty_initially(tmp_path):
    ws = RunWorkspace.create(tmp_path, "p")
    assert ws.pending_gates() == []


def test_pending_gates_lists_pending(tmp_path):
    ws = RunWorkspace.create(tmp_path, "p")
    ws.write_gate("pre_gate")
    ws.write_gate("post_gate")
    assert set(ws.pending_gates()) == {"pre_gate", "post_gate"}


def test_pending_gates_excludes_approved(tmp_path):
    ws = RunWorkspace.create(tmp_path, "p")
    ws.write_gate("pre_gate")
    ws.approve_gate("pre_gate")
    assert "pre_gate" not in ws.pending_gates()


def test_pending_gates_excludes_rejected(tmp_path):
    ws = RunWorkspace.create(tmp_path, "p")
    ws.write_gate("pre_gate")
    ws.reject_gate("pre_gate")
    assert "pre_gate" not in ws.pending_gates()


def test_gate_path_traversal_raises(tmp_path):
    ws = RunWorkspace.create(tmp_path, "p")
    with pytest.raises(StratumError, match="escape run directory"):
        ws.gate_path("../evil")
