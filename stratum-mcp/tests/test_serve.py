"""Tests for stratum-mcp serve — JSON API server."""

from __future__ import annotations

import ast
import datetime
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from stratum_mcp.serve import (
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


def test_approve_gate_with_note(client: TestClient, project_dir: Path) -> None:
    _make_run(project_dir, "p", run_id="r1", gates=["pre_gate"])
    resp = client.post("/api/gates/r1/pre_gate/approve", json={"note": "looks good"})
    assert resp.status_code == 200


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


def test_reject_gate_with_note(client: TestClient, project_dir: Path) -> None:
    _make_run(project_dir, "p", run_id="r1", gates=["pre_gate"])
    resp = client.post("/api/gates/r1/pre_gate/reject", json={"note": "not ready"})
    assert resp.status_code == 200


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
# /api/pipeline-draft
# ---------------------------------------------------------------------------

def test_get_draft_returns_default_when_none_exists(client: TestClient) -> None:
    resp = client.get("/api/pipeline-draft")
    assert resp.status_code == 200
    body = resp.json()
    assert "name" in body
    assert "phases" in body
    assert isinstance(body["phases"], list)


def test_put_draft_persists_and_get_returns_it(client: TestClient, project_dir: Path) -> None:
    draft = {"name": "auth-pipeline", "phases": [
        {"name": "research", "capability": "scout", "policy": "skip",
         "connector": None, "ensures": [], "input": []}
    ]}
    put_resp = client.put("/api/pipeline-draft", json=draft)
    assert put_resp.status_code == 200
    assert put_resp.json() == {"status": "saved"}

    get_resp = client.get("/api/pipeline-draft")
    body = get_resp.json()
    assert body["name"] == "auth-pipeline"
    assert len(body["phases"]) == 1
    assert body["phases"][0]["name"] == "research"


def test_draft_survives_fresh_client(project_dir: Path) -> None:
    draft = {"name": "durable", "phases": []}
    client1 = TestClient(create_app(project_dir))
    client1.put("/api/pipeline-draft", json=draft)

    client2 = TestClient(create_app(project_dir))
    body = client2.get("/api/pipeline-draft").json()
    assert body["name"] == "durable"


# ---------------------------------------------------------------------------
# Token auth middleware
# ---------------------------------------------------------------------------

def test_no_token_set_allows_all_requests(project_dir: Path) -> None:
    client = TestClient(create_app(project_dir, token=None))
    resp = client.get("/api/status")
    assert resp.status_code == 200


def test_token_set_rejects_missing_auth(project_dir: Path) -> None:
    client = TestClient(create_app(project_dir, token="secret"))
    resp = client.get("/api/status")
    assert resp.status_code == 401


def test_token_set_rejects_wrong_token(project_dir: Path) -> None:
    client = TestClient(create_app(project_dir, token="secret"))
    resp = client.get("/api/status", headers={"Authorization": "Bearer wrong"})
    assert resp.status_code == 401


def test_token_set_allows_correct_token(project_dir: Path) -> None:
    client = TestClient(create_app(project_dir, token="secret"))
    resp = client.get("/api/status", headers={"Authorization": "Bearer secret"})
    assert resp.status_code == 200


def test_token_applies_to_all_routes(project_dir: Path) -> None:
    client = TestClient(create_app(project_dir, token="tok"))
    for path in ["/api/runs", "/api/gates", "/api/pipeline-draft"]:
        assert client.get(path).status_code == 401
        assert client.get(path, headers={"Authorization": "Bearer tok"}).status_code == 200


# ---------------------------------------------------------------------------
# Generator unit tests — _generate_toml
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


# ---------------------------------------------------------------------------
# Generator unit tests — _generate_python
# ---------------------------------------------------------------------------

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
    at_phase_indices = [i for i, ln in enumerate(lines) if "@phase(" in ln]
    assert len(at_phase_indices) == 2
    assert at_phase_indices[1] - at_phase_indices[0] > 2


# ---------------------------------------------------------------------------
# Generator unit tests — _generate_yaml
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# _class_name
# ---------------------------------------------------------------------------

def test_class_name_kebab() -> None:
    assert _class_name("my-pipeline") == "MyPipeline"


def test_class_name_snake() -> None:
    assert _class_name("auth_flow") == "AuthFlow"


def test_class_name_single_word() -> None:
    assert _class_name("compose") == "Compose"


def test_class_name_leading_digit_gets_prefix() -> None:
    result = _class_name("1flow")
    assert result.startswith("_")


def test_class_name_empty_fallback() -> None:
    assert _class_name("") == "Pipeline"


# ---------------------------------------------------------------------------
# _safe_filename
# ---------------------------------------------------------------------------

def test_safe_filename_strips_newline() -> None:
    assert "\n" not in _safe_filename("bad\nname")


def test_safe_filename_strips_semicolon() -> None:
    assert ";" not in _safe_filename("bad;name")


def test_safe_filename_keeps_allowed_chars() -> None:
    assert _safe_filename("my-pipeline_v1.0") == "my-pipeline_v1.0"


def test_safe_filename_empty_result_falls_back() -> None:
    assert _safe_filename(";;;") == "pipeline"


# ---------------------------------------------------------------------------
# _to_identifier
# ---------------------------------------------------------------------------

def test_to_identifier_hyphen_becomes_underscore() -> None:
    assert _to_identifier("pre-gate") == "pre_gate"


def test_to_identifier_space_becomes_underscore() -> None:
    assert _to_identifier("my phase") == "my_phase"


def test_to_identifier_leading_digit_gets_prefix() -> None:
    assert _to_identifier("1st").startswith("_")


def test_to_identifier_empty_falls_back() -> None:
    assert _to_identifier("") == "phase"


def test_to_identifier_keyword_gets_trailing_underscore() -> None:
    assert _to_identifier("class") == "class_"
    assert _to_identifier("def") == "def_"
    assert _to_identifier("return") == "return_"


def test_generate_python_hyphenated_phase_name_is_valid_identifier() -> None:
    phase = {
        "name": "pre-gate", "capability": "critic",
        "policy": "gate", "connector": None, "ensures": [], "input": [],
    }
    out = _generate_python({"name": "p", "phases": [phase]})
    assert "async def pre_gate(" in out
    assert "async def pre-gate(" not in out


def test_generate_python_digit_pipeline_name_is_parseable() -> None:
    out = _generate_python({"name": "1flow", "phases": []})
    ast.parse(out)
    assert "class _1flow" in out or "class _1Flow" in out


def test_generate_python_quote_in_name_is_parseable() -> None:
    out = _generate_python({"name": 'my"pipe', "phases": []})
    ast.parse(out)


def test_generate_python_backslash_in_name_is_parseable() -> None:
    out = _generate_python({"name": "my\\pipe", "phases": []})
    ast.parse(out)


def test_generate_python_keyword_phase_name_is_parseable() -> None:
    phase = {
        "name": "class", "capability": "builder",
        "policy": "skip", "connector": None, "ensures": [], "input": [],
    }
    out = _generate_python({"name": "p", "phases": [phase]})
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
    assert "async def impl(self, pre_gate)" in out
    assert "async def impl(self, pre-gate)" not in out
