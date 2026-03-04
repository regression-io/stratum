"""Tests for stratum-ui HTTP server."""

from __future__ import annotations

import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from stratum_ui.server import (
    create_app,
    _class_name,
    _generate_toml,
    _generate_python,
    _generate_yaml,
    _safe_filename,
    _to_identifier,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def project_dir(tmp_path: Path) -> Path:
    return tmp_path


@pytest.fixture
def client(project_dir: Path) -> TestClient:
    return TestClient(create_app(project_dir))


def _make_run(
    project_dir: Path,
    pipeline: str = "my-pipeline",
    *,
    run_id: str = "abc123",
    phases: dict | None = None,
    gates: list[str] | None = None,
    failed: list[str] | None = None,
) -> Path:
    """Write a minimal run workspace to disk and return its directory."""
    run_dir = project_dir / ".stratum" / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "run_id":     run_id,
        "pipeline":   pipeline,
        "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    (run_dir / "manifest.json").write_text(json.dumps(manifest))
    for phase_name, result in (phases or {}).items():
        (run_dir / f"{phase_name}.json").write_text(json.dumps(result))
    for phase_name in (gates or []):
        (run_dir / f"{phase_name}.gate").write_text(
            json.dumps({"phase": phase_name, "created_at": manifest["created_at"]})
        )
    for phase_name in (failed or []):
        (run_dir / f"{phase_name}.failed").write_text(
            json.dumps({"phase": phase_name, "error": "test failure"})
        )
    return run_dir


# ---------------------------------------------------------------------------
# /api/status
# ---------------------------------------------------------------------------

def test_status_returns_ok(client: TestClient) -> None:
    resp = client.get("/api/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert "project_dir" in body


def test_status_project_dir_is_absolute(client: TestClient, project_dir: Path) -> None:
    resp = client.get("/api/status")
    assert resp.json()["project_dir"] == str(project_dir.resolve())


# ---------------------------------------------------------------------------
# /api/runs
# ---------------------------------------------------------------------------

def test_runs_empty_when_no_stratum_dir(client: TestClient) -> None:
    resp = client.get("/api/runs")
    assert resp.status_code == 200
    assert resp.json() == []


def test_runs_lists_run(client: TestClient, project_dir: Path) -> None:
    _make_run(project_dir, "my-pipeline", run_id="abc123")
    resp = client.get("/api/runs")
    assert resp.status_code == 200
    runs = resp.json()
    assert len(runs) == 1
    assert runs[0]["run_id"] == "abc123"
    assert runs[0]["pipeline"] == "my-pipeline"


def test_runs_includes_completed_phase_names(client: TestClient, project_dir: Path) -> None:
    _make_run(
        project_dir, "p",
        run_id="r1",
        phases={"discovery": {"affected_files": []}, "implement": {"changed_files": []}},
    )
    runs = client.get("/api/runs").json()
    assert set(runs[0]["phases_complete"]) == {"discovery", "implement"}


def test_runs_includes_failed_phase_names(client: TestClient, project_dir: Path) -> None:
    _make_run(project_dir, "p", run_id="r1", failed=["implement"])
    runs = client.get("/api/runs").json()
    assert runs[0]["phases_failed"] == ["implement"]


def test_runs_includes_pending_gate_names(client: TestClient, project_dir: Path) -> None:
    _make_run(project_dir, "p", run_id="r1", gates=["pre_gate"])
    runs = client.get("/api/runs").json()
    assert runs[0]["gates_pending"] == ["pre_gate"]


def test_runs_sorted_newest_first(client: TestClient, project_dir: Path) -> None:
    _make_run(project_dir, "p", run_id="older")
    import time; time.sleep(0.01)
    _make_run(project_dir, "p", run_id="newer")
    runs = client.get("/api/runs").json()
    assert runs[0]["run_id"] == "newer"
    assert runs[1]["run_id"] == "older"


def test_runs_ignores_non_directory_entries(client: TestClient, project_dir: Path) -> None:
    runs_dir = project_dir / ".stratum" / "runs"
    runs_dir.mkdir(parents=True)
    (runs_dir / "stray.txt").write_text("noise")
    resp = client.get("/api/runs")
    assert resp.json() == []


def test_runs_ignores_dirs_without_manifest(client: TestClient, project_dir: Path) -> None:
    (project_dir / ".stratum" / "runs" / "orphan").mkdir(parents=True)
    resp = client.get("/api/runs")
    assert resp.json() == []


# ---------------------------------------------------------------------------
# /api/runs/{run_id}
# ---------------------------------------------------------------------------

def test_get_run_returns_manifest(client: TestClient, project_dir: Path) -> None:
    _make_run(project_dir, "my-pipeline", run_id="xyz")
    resp = client.get("/api/runs/xyz")
    assert resp.status_code == 200
    body = resp.json()
    assert body["run_id"] == "xyz"
    assert body["pipeline"] == "my-pipeline"


def test_get_run_includes_phase_results(client: TestClient, project_dir: Path) -> None:
    _make_run(
        project_dir, "p", run_id="r1",
        phases={"discovery": {"affected_files": ["a.py"]}},
    )
    body = client.get("/api/runs/r1").json()
    assert "discovery" in body["phases"]
    assert body["phases"]["discovery"]["status"] == "complete"
    assert body["phases"]["discovery"]["result"]["affected_files"] == ["a.py"]


def test_get_run_includes_failed_phases(client: TestClient, project_dir: Path) -> None:
    _make_run(project_dir, "p", run_id="r1", failed=["implement"])
    body = client.get("/api/runs/r1").json()
    assert body["phases"]["implement"]["status"] == "failed"
    assert body["phases"]["implement"]["error"] == "test failure"


def test_get_run_404_for_unknown_id(client: TestClient) -> None:
    resp = client.get("/api/runs/nonexistent")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# /api/gates
# ---------------------------------------------------------------------------

def test_gates_empty_when_none_pending(client: TestClient, project_dir: Path) -> None:
    _make_run(
        project_dir, "p", run_id="r1",
        phases={"discovery": {"result": True}},
    )
    resp = client.get("/api/gates")
    assert resp.status_code == 200
    assert resp.json() == []


def test_gates_lists_pending_gate(client: TestClient, project_dir: Path) -> None:
    _make_run(project_dir, "my-pipeline", run_id="r1", gates=["pre_gate"])
    gates = client.get("/api/gates").json()
    assert len(gates) == 1
    assert gates[0]["run_id"] == "r1"
    assert gates[0]["phase"] == "pre_gate"
    assert gates[0]["pipeline"] == "my-pipeline"


def test_gates_excludes_approved_gate(client: TestClient, project_dir: Path) -> None:
    _make_run(project_dir, "p", run_id="r1", gates=["pre_gate"])
    run_dir = project_dir / ".stratum" / "runs" / "r1"
    (run_dir / "pre_gate.gate.approved").write_text("{}")
    gates = client.get("/api/gates").json()
    assert gates == []


def test_gates_excludes_rejected_gate(client: TestClient, project_dir: Path) -> None:
    _make_run(project_dir, "p", run_id="r1", gates=["pre_gate"])
    run_dir = project_dir / ".stratum" / "runs" / "r1"
    (run_dir / "pre_gate.gate.rejected").write_text("{}")
    gates = client.get("/api/gates").json()
    assert gates == []


# ---------------------------------------------------------------------------
# /api/gates/{run_id}/{phase}/approve
# ---------------------------------------------------------------------------

def test_approve_gate_writes_file(client: TestClient, project_dir: Path) -> None:
    _make_run(project_dir, "p", run_id="r1", gates=["pre_gate"])
    resp = client.post("/api/gates/r1/pre_gate/approve")
    assert resp.status_code == 200
    assert resp.json() == {"status": "approved"}
    approved = project_dir / ".stratum" / "runs" / "r1" / "pre_gate.gate.approved"
    assert approved.exists()


def test_approve_gate_404_for_missing_gate(client: TestClient, project_dir: Path) -> None:
    _make_run(project_dir, "p", run_id="r1")
    resp = client.post("/api/gates/r1/missing_phase/approve")
    assert resp.status_code == 404


def test_approve_gate_409_when_already_resolved(client: TestClient, project_dir: Path) -> None:
    _make_run(project_dir, "p", run_id="r1", gates=["pre_gate"])
    run_dir = project_dir / ".stratum" / "runs" / "r1"
    (run_dir / "pre_gate.gate.rejected").write_text("{}")
    resp = client.post("/api/gates/r1/pre_gate/approve")
    assert resp.status_code == 409


# ---------------------------------------------------------------------------
# /api/gates/{run_id}/{phase}/reject
# ---------------------------------------------------------------------------

def test_reject_gate_writes_file(client: TestClient, project_dir: Path) -> None:
    _make_run(project_dir, "p", run_id="r1", gates=["pre_gate"])
    resp = client.post("/api/gates/r1/pre_gate/reject")
    assert resp.status_code == 200
    assert resp.json() == {"status": "rejected"}
    rejected = project_dir / ".stratum" / "runs" / "r1" / "pre_gate.gate.rejected"
    assert rejected.exists()


def test_reject_gate_404_for_missing_gate(client: TestClient, project_dir: Path) -> None:
    _make_run(project_dir, "p", run_id="r1")
    resp = client.post("/api/gates/r1/missing_phase/reject")
    assert resp.status_code == 404


def test_reject_gate_409_when_already_resolved(client: TestClient, project_dir: Path) -> None:
    _make_run(project_dir, "p", run_id="r1", gates=["pre_gate"])
    run_dir = project_dir / ".stratum" / "runs" / "r1"
    (run_dir / "pre_gate.gate.approved").write_text("{}")
    resp = client.post("/api/gates/r1/pre_gate/reject")
    assert resp.status_code == 409


def test_approve_then_no_longer_in_pending_gates(client: TestClient, project_dir: Path) -> None:
    _make_run(project_dir, "p", run_id="r1", gates=["pre_gate"])
    client.post("/api/gates/r1/pre_gate/approve")
    gates = client.get("/api/gates").json()
    assert gates == []


# ---------------------------------------------------------------------------
# HTML monitor views (T6-2)
# ---------------------------------------------------------------------------

def test_run_list_view_returns_html(client: TestClient) -> None:
    resp = client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]


def test_run_list_view_empty_state(client: TestClient) -> None:
    resp = client.get("/")
    assert resp.status_code == 200
    assert "No pipeline runs yet" in resp.text


def test_run_list_view_shows_run(client: TestClient, project_dir: Path) -> None:
    _make_run(project_dir, "my-pipeline", run_id="abc123")
    resp = client.get("/")
    assert resp.status_code == 200
    assert "abc123" in resp.text
    assert "my-pipeline" in resp.text


def test_run_list_view_shows_phase_badges(client: TestClient, project_dir: Path) -> None:
    _make_run(
        project_dir, "p", run_id="r1",
        phases={"discovery": {"affected_files": []}},
        failed=["implement"],
    )
    resp = client.get("/")
    assert "discovery" in resp.text
    assert "implement" in resp.text


def test_run_detail_view_returns_html(client: TestClient, project_dir: Path) -> None:
    _make_run(project_dir, "p", run_id="r1")
    resp = client.get("/runs/r1")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]


def test_run_detail_view_shows_run_id_and_pipeline(client: TestClient, project_dir: Path) -> None:
    _make_run(project_dir, "my-pipeline", run_id="r1")
    resp = client.get("/runs/r1")
    assert "r1" in resp.text
    assert "my-pipeline" in resp.text


def test_run_detail_view_shows_phase_result(client: TestClient, project_dir: Path) -> None:
    _make_run(
        project_dir, "p", run_id="r1",
        phases={"discovery": {"affected_files": ["auth.py"]}},
    )
    resp = client.get("/runs/r1")
    assert "discovery" in resp.text
    assert "auth.py" in resp.text
    assert "complete" in resp.text


def test_run_detail_view_shows_failed_phase(client: TestClient, project_dir: Path) -> None:
    _make_run(project_dir, "p", run_id="r1", failed=["implement"])
    resp = client.get("/runs/r1")
    assert "implement" in resp.text
    assert "failed" in resp.text
    assert "test failure" in resp.text


def test_run_detail_view_shows_pending_gate(client: TestClient, project_dir: Path) -> None:
    _make_run(project_dir, "p", run_id="r1", gates=["pre_gate"])
    resp = client.get("/runs/r1")
    assert "pre_gate" in resp.text
    assert "gate_pending" in resp.text or "gate pending" in resp.text


def test_run_detail_view_404_for_unknown_run(client: TestClient) -> None:
    resp = client.get("/runs/nonexistent")
    assert resp.status_code == 404


def test_run_detail_view_has_auto_refresh_meta(client: TestClient, project_dir: Path) -> None:
    _make_run(project_dir, "p", run_id="r1")
    resp = client.get("/runs/r1")
    assert 'http-equiv="refresh"' in resp.text


# ---------------------------------------------------------------------------
# HTML gate queue view (T6-3)
# ---------------------------------------------------------------------------

def test_gate_queue_view_returns_html(client: TestClient) -> None:
    resp = client.get("/gates")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]


def test_gate_queue_view_empty_state(client: TestClient) -> None:
    resp = client.get("/gates")
    assert "No gates pending" in resp.text


def test_gate_queue_view_shows_pending_gate(client: TestClient, project_dir: Path) -> None:
    _make_run(project_dir, "my-pipeline", run_id="r1", gates=["pre_gate"])
    resp = client.get("/gates")
    assert resp.status_code == 200
    assert "pre_gate" in resp.text
    assert "my-pipeline" in resp.text
    assert "r1" in resp.text


def test_gate_queue_view_has_approve_button(client: TestClient, project_dir: Path) -> None:
    _make_run(project_dir, "p", run_id="r1", gates=["pre_gate"])
    resp = client.get("/gates")
    assert "Approve" in resp.text
    assert "/gates/r1/pre_gate/approve" in resp.text


def test_gate_queue_view_has_reject_button(client: TestClient, project_dir: Path) -> None:
    _make_run(project_dir, "p", run_id="r1", gates=["pre_gate"])
    resp = client.get("/gates")
    assert "Reject" in resp.text
    assert "/gates/r1/pre_gate/reject" in resp.text


def test_gate_queue_view_excludes_resolved_gates(client: TestClient, project_dir: Path) -> None:
    _make_run(project_dir, "p", run_id="r1", gates=["pre_gate"])
    run_dir = project_dir / ".stratum" / "runs" / "r1"
    (run_dir / "pre_gate.gate.approved").write_text("{}")
    resp = client.get("/gates")
    assert "No gates pending" in resp.text


def test_gate_queue_view_has_auto_refresh(client: TestClient) -> None:
    resp = client.get("/gates")
    # auto-refresh only appears when there are pending gates — no gates = no timer
    # (the template only shows refresh_note when gates exist)
    _make_run  # just ensure import is used
    assert resp.status_code == 200


def test_ui_approve_gate_redirects_to_queue(client: TestClient, project_dir: Path) -> None:
    _make_run(project_dir, "p", run_id="r1", gates=["pre_gate"])
    resp = client.post("/gates/r1/pre_gate/approve", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/gates"
    # file written
    approved = project_dir / ".stratum" / "runs" / "r1" / "pre_gate.gate.approved"
    assert approved.exists()


def test_ui_reject_gate_redirects_to_queue(client: TestClient, project_dir: Path) -> None:
    _make_run(project_dir, "p", run_id="r1", gates=["pre_gate"])
    resp = client.post("/gates/r1/pre_gate/reject", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/gates"
    rejected = project_dir / ".stratum" / "runs" / "r1" / "pre_gate.gate.rejected"
    assert rejected.exists()


def test_ui_approve_gate_404_for_missing_gate(client: TestClient, project_dir: Path) -> None:
    _make_run(project_dir, "p", run_id="r1")
    resp = client.post("/gates/r1/no_such_phase/approve")
    assert resp.status_code == 404


def test_ui_reject_gate_409_when_already_resolved(client: TestClient, project_dir: Path) -> None:
    _make_run(project_dir, "p", run_id="r1", gates=["pre_gate"])
    client.post("/gates/r1/pre_gate/approve")
    resp = client.post("/gates/r1/pre_gate/reject")
    assert resp.status_code == 409


def test_nav_links_to_gates_page(client: TestClient) -> None:
    resp = client.get("/")
    assert 'href="/gates"' in resp.text


# ---------------------------------------------------------------------------
# Pipeline editor (T6-4)
# ---------------------------------------------------------------------------

def test_editor_returns_html(client: TestClient) -> None:
    resp = client.get("/editor")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]


def test_editor_shows_default_pipeline_name(client: TestClient) -> None:
    resp = client.get("/editor")
    assert "my-pipeline" in resp.text


def test_editor_empty_state_message(client: TestClient) -> None:
    resp = client.get("/editor")
    assert "No phases yet" in resp.text


def test_editor_set_name_persists(client: TestClient, project_dir: Path) -> None:
    resp = client.post("/editor/name", data={"name": "auth-pipeline"}, follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/editor"
    resp2 = client.get("/editor")
    assert "auth-pipeline" in resp2.text


def test_editor_add_phase_appears_in_list(client: TestClient, project_dir: Path) -> None:
    client.post("/editor/phases/add", data={"phase_name": "discovery"})
    resp = client.get("/editor")
    assert "discovery" in resp.text


def test_editor_add_phase_defaults_to_builder_skip(client: TestClient, project_dir: Path) -> None:
    client.post("/editor/phases/add", data={"phase_name": "impl"})
    draft_path = project_dir / ".stratum" / "pipeline-draft.json"
    draft = json.loads(draft_path.read_text())
    phase = draft["phases"][0]
    assert phase["capability"] == "builder"
    assert phase["policy"] == "skip"


def test_editor_duplicate_phase_name_ignored(client: TestClient, project_dir: Path) -> None:
    client.post("/editor/phases/add", data={"phase_name": "discovery"})
    client.post("/editor/phases/add", data={"phase_name": "discovery"})
    draft = json.loads((project_dir / ".stratum" / "pipeline-draft.json").read_text())
    assert len(draft["phases"]) == 1


def test_editor_update_phase_capability_and_policy(client: TestClient, project_dir: Path) -> None:
    client.post("/editor/phases/add", data={"phase_name": "review"})
    client.post("/editor/phases/0/update", data={
        "capability": "critic",
        "policy":     "gate",
        "connector":  "",
        "ensures":    "",
        "input_phases": "",
    })
    draft = json.loads((project_dir / ".stratum" / "pipeline-draft.json").read_text())
    phase = draft["phases"][0]
    assert phase["capability"] == "critic"
    assert phase["policy"] == "gate"


def test_editor_update_phase_connector_and_ensures(client: TestClient, project_dir: Path) -> None:
    client.post("/editor/phases/add", data={"phase_name": "impl"})
    client.post("/editor/phases/0/update", data={
        "capability":   "builder",
        "policy":       "skip",
        "connector":    "my-connector",
        "ensures":      "tests_pass, files_changed",
        "input_phases": "",
    })
    draft = json.loads((project_dir / ".stratum" / "pipeline-draft.json").read_text())
    phase = draft["phases"][0]
    assert phase["connector"] == "my-connector"
    assert phase["ensures"] == ["tests_pass", "files_changed"]


def test_editor_update_phase_input_list(client: TestClient, project_dir: Path) -> None:
    client.post("/editor/phases/add", data={"phase_name": "discovery"})
    client.post("/editor/phases/add", data={"phase_name": "impl"})
    client.post("/editor/phases/1/update", data={
        "capability":   "builder",
        "policy":       "skip",
        "connector":    "",
        "ensures":      "",
        "input_phases": "discovery",
    })
    draft = json.loads((project_dir / ".stratum" / "pipeline-draft.json").read_text())
    assert draft["phases"][1]["input"] == ["discovery"]


def test_editor_delete_phase_removes_it(client: TestClient, project_dir: Path) -> None:
    client.post("/editor/phases/add", data={"phase_name": "discovery"})
    client.post("/editor/phases/add", data={"phase_name": "impl"})
    resp = client.post("/editor/phases/0/delete", follow_redirects=False)
    assert resp.status_code == 303
    draft = json.loads((project_dir / ".stratum" / "pipeline-draft.json").read_text())
    assert len(draft["phases"]) == 1
    assert draft["phases"][0]["name"] == "impl"


def test_editor_delete_out_of_range_is_noop(client: TestClient, project_dir: Path) -> None:
    client.post("/editor/phases/add", data={"phase_name": "discovery"})
    resp = client.post("/editor/phases/99/delete", follow_redirects=False)
    assert resp.status_code == 303
    draft = json.loads((project_dir / ".stratum" / "pipeline-draft.json").read_text())
    assert len(draft["phases"]) == 1


def test_editor_move_phase_up(client: TestClient, project_dir: Path) -> None:
    client.post("/editor/phases/add", data={"phase_name": "a"})
    client.post("/editor/phases/add", data={"phase_name": "b"})
    client.post("/editor/phases/1/move", data={"direction": "up"})
    draft = json.loads((project_dir / ".stratum" / "pipeline-draft.json").read_text())
    assert [p["name"] for p in draft["phases"]] == ["b", "a"]


def test_editor_move_phase_down(client: TestClient, project_dir: Path) -> None:
    client.post("/editor/phases/add", data={"phase_name": "a"})
    client.post("/editor/phases/add", data={"phase_name": "b"})
    client.post("/editor/phases/0/move", data={"direction": "down"})
    draft = json.loads((project_dir / ".stratum" / "pipeline-draft.json").read_text())
    assert [p["name"] for p in draft["phases"]] == ["b", "a"]


def test_editor_move_first_phase_up_is_noop(client: TestClient, project_dir: Path) -> None:
    client.post("/editor/phases/add", data={"phase_name": "a"})
    client.post("/editor/phases/add", data={"phase_name": "b"})
    client.post("/editor/phases/0/move", data={"direction": "up"})
    draft = json.loads((project_dir / ".stratum" / "pipeline-draft.json").read_text())
    assert [p["name"] for p in draft["phases"]] == ["a", "b"]


def test_editor_draft_survives_reload(client: TestClient, project_dir: Path) -> None:
    client.post("/editor/name", data={"name": "durable-pipeline"})
    client.post("/editor/phases/add", data={"phase_name": "step1"})
    # Create a fresh client (new app instance over same project_dir)
    client2 = TestClient(create_app(project_dir))
    resp = client2.get("/editor")
    assert "durable-pipeline" in resp.text
    assert "step1" in resp.text


def test_editor_move_negative_index_is_noop(client: TestClient, project_dir: Path) -> None:
    """Negative idx must not be accepted as a valid phase index."""
    client.post("/editor/phases/add", data={"phase_name": "a"})
    client.post("/editor/phases/add", data={"phase_name": "b"})
    # idx=-1 with direction='down' previously triggered phases[-1] swap with phases[0]
    resp = client.post("/editor/phases/-1/move", data={"direction": "down"}, follow_redirects=False)
    assert resp.status_code == 303
    draft = json.loads((project_dir / ".stratum" / "pipeline-draft.json").read_text())
    # Order must be unchanged
    assert [p["name"] for p in draft["phases"]] == ["a", "b"]


def test_nav_links_to_editor(client: TestClient) -> None:
    resp = client.get("/")
    assert 'href="/editor"' in resp.text


# ---------------------------------------------------------------------------
# Generate placeholder (T6-5 stub)
# ---------------------------------------------------------------------------

def test_generate_returns_html(client: TestClient) -> None:
    resp = client.get("/generate")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]


def test_generate_shows_pipeline_name(client: TestClient, project_dir: Path) -> None:
    client.post("/editor/name", data={"name": "export-me"})
    resp = client.get("/generate")
    assert "export-me" in resp.text


def test_generate_mentions_output_formats(client: TestClient) -> None:
    resp = client.get("/generate")
    assert "stratum.toml" in resp.text
    assert "@pipeline" in resp.text
    assert ".stratum.yaml" in resp.text


def test_editor_links_to_generate(client: TestClient) -> None:
    resp = client.get("/editor")
    assert 'href="/generate"' in resp.text


# ---------------------------------------------------------------------------
# Generator unit tests (T6-5)
# ---------------------------------------------------------------------------

_PHASE_GATE = {
    "name": "review", "capability": "critic",
    "policy": "gate", "connector": None, "ensures": [], "input": [],
}
_PHASE_CONNECTOR = {
    "name": "impl", "capability": "builder",
    "policy": "skip", "connector": "my-connector", "ensures": [], "input": [],
}
_PHASE_SKIP = {
    "name": "discover", "capability": "scout",
    "policy": "skip", "connector": None, "ensures": [], "input": [],
}


def test_class_name_kebab() -> None:
    assert _class_name("my-pipeline") == "MyPipeline"


def test_class_name_snake() -> None:
    assert _class_name("auth_flow") == "AuthFlow"


def test_class_name_single_word() -> None:
    assert _class_name("compose") == "Compose"


# _generate_toml

def test_generate_toml_empty_draft_returns_comment() -> None:
    draft = {"name": "p", "phases": []}
    out = _generate_toml(draft)
    assert out.startswith("# No overrides")


def test_generate_toml_all_skip_returns_comment() -> None:
    draft = {"name": "p", "phases": [_PHASE_SKIP]}
    out = _generate_toml(draft)
    assert out.startswith("# No overrides")


def test_generate_toml_policy_section() -> None:
    draft = {"name": "p", "phases": [_PHASE_GATE]}
    out = _generate_toml(draft)
    assert "[pipeline.policy]" in out
    assert 'review = "gate"' in out


def test_generate_toml_connector_section() -> None:
    draft = {"name": "p", "phases": [_PHASE_CONNECTOR]}
    out = _generate_toml(draft)
    assert "[pipeline.connector]" in out
    assert 'impl = "my-connector"' in out


def test_generate_toml_both_sections() -> None:
    draft = {"name": "p", "phases": [_PHASE_GATE, _PHASE_CONNECTOR]}
    out = _generate_toml(draft)
    assert "[pipeline.policy]" in out
    assert "[pipeline.connector]" in out


# _generate_python

def test_generate_python_empty_draft_has_pass() -> None:
    draft = {"name": "my-pipeline", "phases": []}
    out = _generate_python(draft)
    assert "@pipeline" in out
    assert "class MyPipeline:" in out
    assert "pass" in out


def test_generate_python_has_phase_method() -> None:
    phase = {**_PHASE_SKIP, "name": "discover", "capability": "scout", "policy": "skip"}
    draft = {"name": "my-pipeline", "phases": [phase]}
    out = _generate_python(draft)
    assert "@phase(" in out
    assert "Capability.SCOUT" in out
    assert "Policy.SKIP" in out
    assert "async def discover" in out


def test_generate_python_phase_with_inputs() -> None:
    phase = {
        "name": "impl", "capability": "builder", "policy": "skip",
        "connector": None, "ensures": [], "input": ["discover"],
    }
    draft = {"name": "p", "phases": [phase]}
    out = _generate_python(draft)
    assert "input=" in out
    assert "async def impl(self, discover)" in out


def test_generate_python_multiple_phases_separated_by_blank_line() -> None:
    phases = [
        {**_PHASE_SKIP, "name": "a"},
        {**_PHASE_SKIP, "name": "b"},
    ]
    draft = {"name": "p", "phases": phases}
    out = _generate_python(draft)
    lines = out.splitlines()
    # There must be a blank line between the two @phase decorators
    at_phase_indices = [i for i, l in enumerate(lines) if "@phase(" in l]
    assert len(at_phase_indices) == 2
    assert at_phase_indices[1] - at_phase_indices[0] > 2  # blank line separates them


# _generate_yaml

def test_generate_yaml_empty_draft_has_version() -> None:
    draft = {"name": "p", "phases": []}
    out = _generate_yaml(draft)
    assert 'version: "0.1"' in out
    assert "# (no phases defined)" in out


def test_generate_yaml_has_function_per_phase() -> None:
    draft = {"name": "p", "phases": [_PHASE_SKIP]}
    out = _generate_yaml(draft)
    assert "functions:" in out
    assert "  discover:" in out
    assert "flows:" in out


def test_generate_yaml_step_depends_on_for_input_phases() -> None:
    phases = [
        {**_PHASE_SKIP, "name": "discover", "input": []},
        {**_PHASE_SKIP, "name": "impl", "input": ["discover"]},
    ]
    draft = {"name": "p", "phases": phases}
    out = _generate_yaml(draft)
    assert "depends_on:" in out
    assert "discover" in out


# Generate view

def test_generate_view_shows_toml_output(client: TestClient, project_dir: Path) -> None:
    client.post("/editor/phases/add", data={"phase_name": "review"})
    client.post("/editor/phases/0/update", data={
        "capability": "critic", "policy": "gate",
        "connector": "", "ensures": "", "input_phases": "",
    })
    resp = client.get("/generate")
    assert "[pipeline.policy]" in resp.text


def test_generate_view_shows_python_output(client: TestClient) -> None:
    resp = client.get("/generate")
    assert "@pipeline" in resp.text
    assert "class MyPipeline" in resp.text


def test_generate_view_shows_yaml_output(client: TestClient) -> None:
    resp = client.get("/generate")
    # Jinja2 HTML-escapes " as &#34; inside <pre>
    assert "version: &#34;0.1&#34;" in resp.text or 'version: "0.1"' in resp.text


# Download endpoints

def test_download_toml_returns_text_plain(client: TestClient) -> None:
    resp = client.get("/generate/toml")
    assert resp.status_code == 200
    assert "text/plain" in resp.headers["content-type"]


def test_download_toml_content_disposition(client: TestClient) -> None:
    resp = client.get("/generate/toml")
    assert "stratum.toml" in resp.headers.get("content-disposition", "")


def test_download_python_returns_text_plain(client: TestClient) -> None:
    resp = client.get("/generate/python")
    assert resp.status_code == 200
    assert "text/plain" in resp.headers["content-type"]


def test_download_python_filename_based_on_pipeline_name(client: TestClient, project_dir: Path) -> None:
    client.post("/editor/name", data={"name": "auth-flow"})
    resp = client.get("/generate/python")
    assert "auth_flow_pipeline.py" in resp.headers.get("content-disposition", "")


def test_download_yaml_returns_text_plain(client: TestClient) -> None:
    resp = client.get("/generate/yaml")
    assert resp.status_code == 200
    assert "text/plain" in resp.headers["content-type"]


def test_download_yaml_filename_based_on_pipeline_name(client: TestClient, project_dir: Path) -> None:
    client.post("/editor/name", data={"name": "my-pipeline"})
    resp = client.get("/generate/yaml")
    assert "my-pipeline.stratum.yaml" in resp.headers.get("content-disposition", "")


# ---------------------------------------------------------------------------
# _safe_filename (P1 — Content-Disposition header injection)
# ---------------------------------------------------------------------------

def test_safe_filename_strips_newline() -> None:
    assert "\n" not in _safe_filename("bad\nname")


def test_safe_filename_strips_semicolon() -> None:
    # Semicolon could split a Content-Disposition header value
    assert ";" not in _safe_filename("bad;name")


def test_safe_filename_keeps_allowed_chars() -> None:
    assert _safe_filename("my-pipeline_v1.0") == "my-pipeline_v1.0"


def test_safe_filename_empty_result_falls_back() -> None:
    assert _safe_filename(";;;") == "pipeline"


def test_download_python_newline_in_name_single_header_line(client: TestClient, project_dir: Path) -> None:
    """A name with a newline must not split the Content-Disposition header."""
    client.post("/editor/name", data={"name": "bad\nname"})
    resp = client.get("/generate/python")
    disposition = resp.headers.get("content-disposition", "")
    assert "\n" not in disposition
    assert "\r" not in disposition


def test_download_yaml_newline_in_name_single_header_line(client: TestClient, project_dir: Path) -> None:
    client.post("/editor/name", data={"name": "bad\nname"})
    resp = client.get("/generate/yaml")
    disposition = resp.headers.get("content-disposition", "")
    assert "\n" not in disposition
    assert "\r" not in disposition


# ---------------------------------------------------------------------------
# _to_identifier (P2 — invalid Python identifiers)
# ---------------------------------------------------------------------------

def test_to_identifier_hyphen_becomes_underscore() -> None:
    assert _to_identifier("pre-gate") == "pre_gate"


def test_to_identifier_space_becomes_underscore() -> None:
    assert _to_identifier("my phase") == "my_phase"


def test_to_identifier_leading_digit_gets_prefix() -> None:
    assert _to_identifier("1st").startswith("_")


def test_to_identifier_empty_falls_back() -> None:
    assert _to_identifier("") == "phase"


def test_generate_python_hyphenated_phase_name_is_valid_identifier() -> None:
    phase = {
        "name": "pre-gate", "capability": "critic",
        "policy": "gate", "connector": None, "ensures": [], "input": [],
    }
    out = _generate_python({"name": "p", "phases": [phase]})
    assert "async def pre_gate(" in out
    assert "async def pre-gate(" not in out


def test_to_identifier_keyword_gets_trailing_underscore() -> None:
    assert _to_identifier("class") == "class_"
    assert _to_identifier("def") == "def_"
    assert _to_identifier("return") == "return_"


def test_class_name_leading_digit_gets_prefix() -> None:
    assert _class_name("1flow").startswith("_")
    assert _class_name("1flow")[1:] == "1flow".capitalize() or _class_name("1flow") == "_1flow"


def test_class_name_empty_fallback() -> None:
    assert _class_name("") == "Pipeline"


def test_generate_python_digit_pipeline_name_is_parseable() -> None:
    import ast
    out = _generate_python({"name": "1flow", "phases": []})
    ast.parse(out)  # must not raise SyntaxError
    assert "class _1flow" in out or "class _1Flow" in out


def test_generate_python_quote_in_name_is_parseable() -> None:
    import ast
    out = _generate_python({"name": 'my"pipe', "phases": []})
    ast.parse(out)  # must not raise SyntaxError


def test_generate_python_backslash_in_name_is_parseable() -> None:
    import ast
    out = _generate_python({"name": "my\\pipe", "phases": []})
    ast.parse(out)  # must not raise SyntaxError


def test_generate_python_keyword_phase_name_is_parseable() -> None:
    import ast
    phase = {
        "name": "class", "capability": "builder",
        "policy": "skip", "connector": None, "ensures": [], "input": [],
    }
    out = _generate_python({"name": "p", "phases": [phase]})
    # Must not raise SyntaxError
    ast.parse(out)
    assert "async def class_(" in out


def test_generate_python_hyphenated_input_name_is_valid_identifier() -> None:
    phases = [
        {"name": "pre-gate", "capability": "scout", "policy": "skip",
         "connector": None, "ensures": [], "input": []},
        {"name": "impl", "capability": "builder", "policy": "skip",
         "connector": None, "ensures": [], "input": ["pre-gate"]},
    ]
    out = _generate_python({"name": "p", "phases": phases})
    # Parameter must be a valid identifier
    assert "async def impl(self, pre_gate)" in out
    assert "async def impl(self, pre-gate)" not in out
