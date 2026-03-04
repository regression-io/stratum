"""stratum-mcp HTTP serve subcommand.

JSON-only API server exposing .stratum/runs/ workspace for pipeline monitoring
and gate approval. Ported from stratum-ui.

Usage::

    stratum-mcp serve                          # defaults to ./ on port 7821
    stratum-mcp serve --project-dir ~/myapp --port 8000 --token SECRET
"""

from __future__ import annotations

import datetime
import json
import keyword
import re
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Filesystem helpers — thin wrappers around .stratum/runs/ layout
# ---------------------------------------------------------------------------

def _runs_dir(project_dir: Path) -> Path:
    return project_dir / ".stratum" / "runs"


def _list_runs(project_dir: Path) -> list[dict[str, Any]]:
    """Return a list of run manifests, newest first by creation timestamp."""
    runs_dir = _runs_dir(project_dir)
    if not runs_dir.exists():
        return []

    runs: list[dict[str, Any]] = []
    for run_dir in runs_dir.iterdir():
        if not run_dir.is_dir():
            continue
        manifest_path = run_dir / "manifest.json"
        if not manifest_path.exists():
            continue
        try:
            manifest = json.loads(manifest_path.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        phases = sorted(
            p.stem
            for p in run_dir.glob("*.json")
            if p.name != "manifest.json"
        )
        failed = sorted(p.stem for p in run_dir.glob("*.failed"))
        pending_gates = [
            p.stem
            for p in sorted(run_dir.glob("*.gate"))
            if not (run_dir / f"{p.stem}.gate.approved").exists()
            and not (run_dir / f"{p.stem}.gate.rejected").exists()
        ]
        runs.append({
            **manifest,
            "phases_complete": phases,
            "phases_failed":   failed,
            "gates_pending":   pending_gates,
        })

    runs.sort(key=lambda r: r.get("created_at", ""), reverse=True)
    return runs


def _get_run(project_dir: Path, run_id: str) -> dict[str, Any]:
    """Return a single run's manifest and per-phase detail."""
    run_dir = _runs_dir(project_dir) / run_id
    manifest_path = run_dir / "manifest.json"
    if not run_dir.exists() or not manifest_path.exists():
        raise KeyError(run_id)
    manifest = json.loads(manifest_path.read_text())

    phases: dict[str, Any] = {}
    for result_path in run_dir.glob("*.json"):
        if result_path.name == "manifest.json":
            continue
        try:
            phases[result_path.stem] = {
                "status": "complete",
                "result": json.loads(result_path.read_text()),
            }
        except (json.JSONDecodeError, OSError):
            phases[result_path.stem] = {"status": "corrupt"}

    for failed_path in run_dir.glob("*.failed"):
        try:
            rec = json.loads(failed_path.read_text())
        except (json.JSONDecodeError, OSError):
            rec = {}
        phases[failed_path.stem] = {"status": "failed", "error": rec.get("error")}

    for gate_path in run_dir.glob("*.gate"):
        phase_name = gate_path.stem
        if phase_name in phases:
            continue
        approved = (run_dir / f"{phase_name}.gate.approved").exists()
        rejected = (run_dir / f"{phase_name}.gate.rejected").exists()
        if approved:
            gate_status = "gate_approved"
        elif rejected:
            gate_status = "gate_rejected"
        else:
            gate_status = "gate_pending"
        try:
            context = json.loads(gate_path.read_text())
        except (json.JSONDecodeError, OSError):
            context = {}
        phases[phase_name] = {"status": gate_status, "context": context}

    return {**manifest, "phases": phases}


def _list_pending_gates(project_dir: Path) -> list[dict[str, Any]]:
    """Return all pending gates across all runs, sorted by run creation time."""
    gates: list[dict[str, Any]] = []
    runs_dir = _runs_dir(project_dir)
    if not runs_dir.exists():
        return []

    for run_dir in runs_dir.iterdir():
        if not run_dir.is_dir():
            continue
        manifest_path = run_dir / "manifest.json"
        try:
            manifest = json.loads(manifest_path.read_text())
        except (json.JSONDecodeError, OSError, FileNotFoundError):
            continue

        for gate_path in run_dir.glob("*.gate"):
            phase_name = gate_path.stem
            if (
                (run_dir / f"{phase_name}.gate.approved").exists()
                or (run_dir / f"{phase_name}.gate.rejected").exists()
            ):
                continue
            try:
                context = json.loads(gate_path.read_text())
            except (json.JSONDecodeError, OSError):
                context = {}
            gates.append({
                "run_id":       manifest.get("run_id", run_dir.name),
                "pipeline":     manifest.get("pipeline", ""),
                "created_at":   manifest.get("created_at", ""),
                "phase":        phase_name,
                "gate_context": context,
            })

    gates.sort(key=lambda g: g.get("created_at", ""), reverse=True)
    return gates


def _write_gate_response(
    project_dir: Path,
    run_id: str,
    phase_name: str,
    decision: str,
    note: str | None,
) -> None:
    """Write a gate response file for ``phase_name`` in run ``run_id``."""
    run_dir   = _runs_dir(project_dir) / run_id
    gate_path = run_dir / f"{phase_name}.gate"
    approved  = run_dir / f"{phase_name}.gate.approved"
    rejected  = run_dir / f"{phase_name}.gate.rejected"

    if not gate_path.exists():
        raise KeyError(f"No gate for phase '{phase_name}' in run '{run_id}'")
    if approved.exists() or rejected.exists():
        raise ValueError(f"Gate for '{phase_name}' in run '{run_id}' already resolved")

    payload = {
        f"{decision}_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "note": note,
    }
    (run_dir / f"{phase_name}.gate.{decision}").write_text(
        json.dumps(payload, indent=2)
    )


# ---------------------------------------------------------------------------
# Pipeline draft — persisted at {project_dir}/.stratum/pipeline-draft.json
# ---------------------------------------------------------------------------

_VALID_CAPABILITIES = ("scout", "builder", "critic")
_VALID_POLICIES     = ("gate", "flag", "skip")


def _draft_path(project_dir: Path) -> Path:
    return project_dir / ".stratum" / "pipeline-draft.json"


def _load_draft(project_dir: Path) -> dict[str, Any]:
    path = _draft_path(project_dir)
    if not path.exists():
        return {"name": "my-pipeline", "phases": []}
    try:
        draft = json.loads(path.read_text())
        draft.setdefault("name", "my-pipeline")
        if not isinstance(draft.get("phases"), list):
            draft["phases"] = []
        return draft
    except (json.JSONDecodeError, OSError):
        return {"name": "my-pipeline", "phases": []}


def _save_draft(project_dir: Path, draft: dict[str, Any]) -> None:
    path = _draft_path(project_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(draft, indent=2))


def _blank_phase(name: str) -> dict[str, Any]:
    return {
        "name":       name,
        "capability": "builder",
        "policy":     "skip",
        "connector":  None,
        "ensures":    [],
        "input":      [],
    }


# ---------------------------------------------------------------------------
# Code generators
# ---------------------------------------------------------------------------

def _safe_filename(name: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9._-]", "", name)
    return safe or "pipeline"


def _to_identifier(name: str) -> str:
    ident = re.sub(r"[^A-Za-z0-9_]", "_", name)
    if ident and ident[0].isdigit():
        ident = "_" + ident
    ident = ident or "phase"
    if keyword.iskeyword(ident):
        ident = ident + "_"
    return ident


def _generate_toml(draft: dict[str, Any]) -> str:
    lines: list[str] = []
    policy_phases = [p for p in draft["phases"] if p.get("policy", "skip") != "skip"]
    if policy_phases:
        lines.append("[pipeline.policy]")
        for phase in policy_phases:
            lines.append(f'{phase["name"]} = "{phase["policy"]}"')
        lines.append("")
    connector_phases = [p for p in draft["phases"] if p.get("connector")]
    if connector_phases:
        lines.append("[pipeline.connector]")
        for phase in connector_phases:
            lines.append(f'{phase["name"]} = "{phase["connector"]}"')
        lines.append("")
    return "\n".join(lines).rstrip() or "# No overrides — all phases use defaults.\n"


def _class_name(pipeline_name: str) -> str:
    words = re.split(r"[-_]+", pipeline_name)
    name = "".join(re.sub(r"[^A-Za-z0-9]", "", w).capitalize() for w in words if w)
    if name and name[0].isdigit():
        name = "_" + name
    return name or "Pipeline"


def _generate_python(draft: dict[str, Any]) -> str:
    pipeline_name = draft.get("name", "my-pipeline")
    class_name    = _class_name(pipeline_name)
    lines: list[str] = [
        "from stratum import Capability, Policy, phase, pipeline",
        "",
        "",
        f"@pipeline(name={repr(pipeline_name)})",
        f"class {class_name}:",
    ]

    if not draft["phases"]:
        lines.append("    pass")
    else:
        for i, p in enumerate(draft["phases"]):
            cap     = f'Capability.{p["capability"].upper()}'
            pol     = f'Policy.{p["policy"].upper()}'
            inputs  = p.get("input") or []
            ensures = p.get("ensures") or []

            decorator_args = [f"capability={cap}", f"policy={pol}"]
            if inputs:
                decorator_args.append(f"input={inputs!r}")
            if ensures:
                decorator_args.append(f"ensures={ensures!r}")

            if i > 0:
                lines.append("")
            lines.append(f"    @phase({', '.join(decorator_args)})")

            method_name = _to_identifier(p["name"])
            params = ["self"] + [_to_identifier(inp) for inp in inputs]
            lines.append(f"    async def {method_name}({', '.join(params)}) -> dict:")
            lines.append(f'        """TODO: describe {p["name"]}"""')
            lines.append("        ...")

    return "\n".join(lines) + "\n"


def _generate_yaml(draft: dict[str, Any]) -> str:
    pipeline_name = draft.get("name", "my-pipeline")
    lines: list[str] = [
        'version: "0.1"',
        "",
        "functions:",
    ]

    phases = draft["phases"]
    if not phases:
        lines.append("  # (no phases defined)")
    else:
        for p in phases:
            pname = p["name"]
            lines.append(f"  {pname}:")
            lines.append("    mode: infer")
            lines.append(f'    intent: "TODO: describe {pname}"')
            lines.append("    output: object")

        lines += ["", "flows:", f"  {pipeline_name}:"]

        root_phases = [p for p in phases if not p.get("input")]
        if root_phases:
            lines.append("    input: {feature: {type: string}}")
        else:
            lines.append("    input: {}")

        lines.append("    steps:")
        for p in phases:
            lines.append(f'      - id: {p["name"]}')
            lines.append(f'        function: {p["name"]}')
            inputs = p.get("input") or []
            if inputs:
                input_map = ", ".join(
                    f'{inp}: "$.steps.{inp}.output"' for inp in inputs
                )
                lines.append(f"        inputs: {{{input_map}}}")
                lines.append(f'        depends_on: {inputs!r}')
            else:
                lines.append('        inputs: {feature: "$.input.feature"}')

    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Pipeline templates — predefined starting points
# ---------------------------------------------------------------------------

_TEMPLATES: dict[str, dict] = {
    "feature-dev": {
        "name": "feature-dev",
        "description": "End-to-end feature development: explore, design, blueprint, implement",
        "phases": [
            {"name": "explore",    "capability": "scout",   "policy": "skip"},
            {"name": "design",     "capability": "builder", "policy": "gate"},
            {"name": "blueprint",  "capability": "scout",   "policy": "gate"},
            {"name": "implement",  "capability": "builder", "policy": "gate"},
        ],
    },
    "bug-fix": {
        "name": "bug-fix",
        "description": "Reproduce, diagnose, fix, and verify a bug",
        "phases": [
            {"name": "reproduce", "capability": "scout",   "policy": "skip"},
            {"name": "diagnose",  "capability": "critic",  "policy": "flag"},
            {"name": "fix",       "capability": "builder", "policy": "gate"},
            {"name": "verify",    "capability": "critic",  "policy": "gate"},
        ],
    },
    "refactor": {
        "name": "refactor",
        "description": "Analyze, plan, and safely refactor existing code",
        "phases": [
            {"name": "analyze",  "capability": "scout",   "policy": "skip"},
            {"name": "plan",     "capability": "builder", "policy": "gate"},
            {"name": "refactor", "capability": "builder", "policy": "gate"},
            {"name": "review",   "capability": "critic",  "policy": "gate"},
        ],
    },
    "research": {
        "name": "research",
        "description": "Explore a topic, synthesize findings, and produce a report",
        "phases": [
            {"name": "explore",    "capability": "scout",   "policy": "skip"},
            {"name": "synthesize", "capability": "builder", "policy": "flag"},
            {"name": "report",     "capability": "builder", "policy": "gate"},
        ],
    },
    "content": {
        "name": "content",
        "description": "Draft, review, and publish documentation or content",
        "phases": [
            {"name": "draft",   "capability": "builder", "policy": "flag"},
            {"name": "review",  "capability": "critic",  "policy": "gate"},
            {"name": "publish", "capability": "builder", "policy": "gate"},
        ],
    },
}


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class GateActionBody(BaseModel):
    note: str | None = None


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

def _pkg_version() -> str:
    try:
        from importlib.metadata import version
        return version("stratum-mcp")
    except Exception:
        return "0.0.0"


def create_app(project_dir: Path, token: str | None = None) -> FastAPI:
    """Create the FastAPI application bound to ``project_dir``.

    All API endpoints read from / write to ``project_dir/.stratum/runs/``.
    JSON responses only — no HTML views.
    """
    app = FastAPI(
        title="stratum-mcp serve",
        description="Monitor Stratum pipeline runs and approve gate-blocked phases",
        version=_pkg_version(),
    )

    # CORS — allow all origins (localhost-only server by default)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Token auth middleware
    if token:
        @app.middleware("http")
        async def _check_token(request: Request, call_next):
            auth = request.headers.get("authorization", "")
            if auth != f"Bearer {token}":
                return JSONResponse(status_code=401, content={"detail": "Unauthorized"})
            return await call_next(request)

    # -- Routes --------------------------------------------------------------

    @app.get("/api/status")
    def status() -> dict[str, Any]:
        return {
            "status":      "ok",
            "project_dir": str(project_dir.resolve()),
        }

    @app.get("/api/runs")
    def list_runs() -> list[dict[str, Any]]:
        return _list_runs(project_dir)

    @app.get("/api/runs/{run_id}")
    def get_run(run_id: str) -> dict[str, Any]:
        try:
            return _get_run(project_dir, run_id)
        except KeyError:
            raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")

    @app.get("/api/gates")
    def list_gates() -> list[dict[str, Any]]:
        return _list_pending_gates(project_dir)

    @app.post("/api/gates/{run_id}/{phase_name}/approve")
    def approve_gate(
        run_id: str,
        phase_name: str,
        body: GateActionBody | None = None,
    ) -> dict[str, str]:
        note = body.note if body else None
        try:
            _write_gate_response(project_dir, run_id, phase_name, "approved", note)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc))
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc))
        return {"status": "approved"}

    @app.post("/api/gates/{run_id}/{phase_name}/reject")
    def reject_gate(
        run_id: str,
        phase_name: str,
        body: GateActionBody | None = None,
    ) -> dict[str, str]:
        note = body.note if body else None
        try:
            _write_gate_response(project_dir, run_id, phase_name, "rejected", note)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc))
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc))
        return {"status": "rejected"}

    @app.get("/api/pipeline-draft")
    def get_draft() -> dict[str, Any]:
        return _load_draft(project_dir)

    @app.put("/api/pipeline-draft")
    def put_draft(draft: dict[str, Any]) -> dict[str, str]:
        _save_draft(project_dir, draft)
        return {"status": "saved"}

    @app.get("/api/templates")
    def list_templates() -> list[dict[str, Any]]:
        return [
            {"name": t["name"], "description": t["description"]}
            for t in _TEMPLATES.values()
        ]

    @app.get("/api/templates/{name}")
    def get_template(name: str) -> dict[str, Any]:
        if name not in _TEMPLATES:
            raise HTTPException(status_code=404, detail=f"Template '{name}' not found")
        tmpl = _TEMPLATES[name]
        # Return as a loadable draft (strip description — not part of draft schema)
        return {"name": tmpl["name"], "phases": [dict(p) for p in tmpl["phases"]]}

    return app


# ---------------------------------------------------------------------------
# CLI runner
# ---------------------------------------------------------------------------

def run_serve(
    host: str = "127.0.0.1",
    port: int = 7821,
    token: str | None = None,
    project_dir: Path = Path("."),
    tls_cert: str | None = None,
    tls_key: str | None = None,
) -> None:
    import uvicorn

    app = create_app(project_dir.resolve(), token=token)
    uvicorn.run(
        app,
        host=host,
        port=port,
        ssl_certfile=tls_cert or None,
        ssl_keyfile=tls_key or None,
    )
