# Stratum Roadmap

**Last updated:** 2026-03-05

---

## Track 1 — Python Library (`stratum-py`)

| ID | Feature | Status |
|---|---|---|
| T1-1 | `@infer`, `@contract`, `@flow`, `@compute` decorators | COMPLETE |
| T1-2 | `@refine` convergence loop | COMPLETE |
| T1-3 | `parallel()`, `race()`, `debate()` | COMPLETE |
| T1-4 | `await_human()` HITL gate | COMPLETE |
| T1-5 | `quorum=` on `@infer` | COMPLETE |
| T1-6 | `stable=False` → `Probabilistic[T]` | COMPLETE |
| T1-7 | `Budget(ms=, usd=, tokens=)` enforcement | COMPLETE |
| T1-8 | OTLP trace export (no OTel SDK) | COMPLETE |
| T1-9 | `opaque[T]` annotation | COMPLETE |
| T1-10 | Published to PyPI as `stratum-py` 0.1.1 | COMPLETE |
| T1-11 | End-to-end validation against real LLM | COMPLETE |
| T1-12 | TypeScript library (`stratum-ts`) | PLANNED |
| T1-13 | DSPy prompt optimization integration | PLANNED |
| T1-14 | Temporal durable execution integration | PLANNED |
| T1-15 | Ray distributed agents integration | PLANNED |

---

## Track 2 — MCP Server + Claude Code (`stratum-mcp`)

### Core Server

| ID | Feature | Status |
|---|---|---|
| T2-1 | `stratum_plan` MCP tool | COMPLETE |
| T2-2 | `stratum_step_done` MCP tool | COMPLETE |
| T2-3 | `stratum_audit` MCP tool | COMPLETE |
| T2-4 | `stratum_validate` MCP tool | COMPLETE |
| T2-5 | `FlowState` in-memory execution state | COMPLETE |
| T2-6 | `ensure` expression evaluation (Python, dunder-blocked) | COMPLETE |
| T2-7 | `$.input` / `$.steps` reference resolution | COMPLETE |
| T2-8 | Kahn's topological sort on `depends_on` + implicit refs | COMPLETE |
| T2-9 | `stratum-mcp install` CLI command | COMPLETE |
| T2-10 | `stratum-mcp validate <file>` CLI command | COMPLETE |
| T2-11 | Published to PyPI as `stratum-mcp` 0.1.2 | COMPLETE |
| T2-12 | 202 passing tests (contracts, invariants, integration) | COMPLETE |
| T2-13 | `stratum-mcp uninstall` command | COMPLETE |
| T2-14 | FlowState persistence (survive MCP server restart) | COMPLETE |
| T2-15 | `ensure` file-aware builtins (`file_exists`, `file_contains`) | COMPLETE |
| T2-16 | Step output contracts (schema validation in `stratum_step_done`) | COMPLETE |
| T2-17 | `stratum_commit` — explicit flow-state checkpoint with label | COMPLETE |
| T2-18 | `stratum_revert` — roll back to a named checkpoint, trace records revert | COMPLETE |
| T2-19 | IR v0.2 — `mode: gate`, `on_approve/on_revise/on_kill` routing, round archiving, `max_rounds`, `skip_if/skip_reason`, `terminal_status` | COMPLETE |
| T2-20 | `stratum_gate_resolve` MCP tool — approve/revise/kill with `resolved_by`; GateRecord in trace | COMPLETE |
| T2-21 | `stratum_check_timeouts` MCP tool — auto-kill gate steps that exceed `timeout`; `resolved_by: system` | COMPLETE |
| T2-22 | IR v0.2 semantic validation — gate function/step invariants, `on_revise` topological ordering, `declared_routing`, `retries_explicit` | COMPLETE |
| T2-23 | 305 passing tests; `test_gate_api.py`, `test_gate_revise.py`, v0.2 invariant tests in `test_ir_schema.py` | COMPLETE |

### Compose Integration

Enable the `compose` skill to use Stratum as its execution backbone. See `docs/plans/2026-02-24-compose-stratum-integration-plan.md`.

| ID | Feature | Status |
|---|---|---|
| T2-F1 | Result schema convention for compose steps | COMPLETE |
| T2-F2 | `ensure` file-aware builtins (→ T2-15) | COMPLETE |
| T2-F3 | Step output contracts (→ T2-16) | COMPLETE |
| T2-F4 | Compose skill emits `.stratum.yaml` | COMPLETE |

### Skills

| ID | Skill | Status |
|---|---|---|
| T2-S1 | `/stratum-onboard` — read codebase cold, write MEMORY.md | COMPLETE |
| T2-S2 | `/stratum-plan` — design feature, gate before implementation | COMPLETE |
| T2-S3 | `/stratum-feature` — read → design → implement → tests | COMPLETE |
| T2-S4 | `/stratum-review` — three-pass code review | COMPLETE |
| T2-S5 | `/stratum-debug` — hypothesis formation and elimination | COMPLETE |
| T2-S6 | `/stratum-refactor` — extraction order planning | COMPLETE |
| T2-S7 | `/stratum-migrate` — rewrite bare LLM calls as `@infer` | COMPLETE |
| T2-S8 | `/stratum-test` — write test suite for existing code | COMPLETE |
| T2-S9 | `/stratum-learn` — extract patterns from session transcripts | COMPLETE |
| T2-S10 | `/compose` rewrite — emits `.stratum.yaml`, uses `stratum_plan` loop (→ T2-F4) | COMPLETE |

### Memory & Hooks

Three tiers — default is zero-dependency. Opt-in tiers add semantic retrieval without changing the skill interface.

#### Tier 1 — MEMORY.md (default, zero dependencies)

| ID | Feature | Status |
|---|---|---|
| T2-M1 | `## Memory` sections in all 9 skills — read/write MEMORY.md | COMPLETE |
| T2-M2 | `SessionStart` hook — auto-inject relevant MEMORY.md entries at session open | COMPLETE |
| T2-M3 | `Stop` hook — auto-append session summary to MEMORY.md at session close | COMPLETE |
| T2-M4 | `PostToolUseFailure` hook — auto-record ensure failures and tool errors | COMPLETE |

#### Tier 2 — SmartMemory lite (opt-in, pip only, no Docker)

`pip install smartmemory[lite]` — local SQLite graph + usearch vectors + markdown notes at `~/.smartmemory/`. No network calls, no Docker, no LLM extraction. Uses `lite_context()` / `create_lite_memory()` directly. Replaces MEMORY.md read/write with `memory.search()` / `memory.ingest()`.

| ID | Feature | Status |
|---|---|---|
| T2-SM1 | `SessionStart` hook — `memory.search()` for project-relevant context | COMPLETE |
| T2-SM2 | `Stop` hook — `memory.ingest()` session summary as `episodic` memory | COMPLETE |
| T2-SM3 | `PostToolUseFailure` hook — `memory.ingest()` failures as `observation` memory | COMPLETE |
| T2-SM4 | Skills use `memory.search()` instead of MEMORY.md when lite backend configured | COMPLETE |

#### Tier 3 — SmartMemory full (opt-in, requires Docker stack or remote API)

Full SmartMemory service — multi-tenant, LLM entity extraction, Wikidata grounding, REST API. Uses `smartmemory-mcp` HTTP client. Same hook/skill interface as Tier 2 but backed by the remote API.

| ID | Feature | Status |
|---|---|---|
| T2-SM5 | `SessionStart` / `Stop` / `PostToolUseFailure` hooks via `smartmemory-mcp` | PARKED |
| T2-SM6 | Skills use `memory_search` MCP tool when full backend configured | PARKED |

---

## Track 3 — Compose + Stratum + spec-kit Substrate

Refactor Compose to use Stratum as its execution backbone and spec-kit as its specification layer. The result is a clean three-layer stack:

```
spec-kit  →  specification layer   (spec.md, plan.md, tasks/)
stratum   →  execution layer       (.stratum.yaml, postconditions, audit)
compose     →  orchestration layer   (UI, Vision Surface, agent coordination)
```

See `docs/features/compose-speckit-substrate/design.md` for full architecture.

### Pipeline Authoring Model

Users do not write `.stratum.yaml` — it is IR. Three user interfaces replace it: Python
decorators (`@pipeline`/`@phase`) for library users, skill invocation for Claude Code users,
and `stratum.toml` for policy overrides. See `docs/features/pipeline-authoring/design.md`.

| ID | Feature | Status |
|---|---|---|
| T3-A1 | Pipeline authoring model design | COMPLETE |
| T3-A2 | `@pipeline` / `@phase` Python decorators in `stratum-py` | COMPLETE |
| T3-A3 | Capability tiers (`Capability`, `Policy` enums) in `stratum-py` | COMPLETE |
| T3-A4 | `stratum.toml` project config — policy overrides, capability mapping | COMPLETE |
| T3-A5 | Run workspace convention — `.stratum/runs/` output passing | COMPLETE |
| T3-A6 | Skill-driven pipeline execution — no YAML visible to user | COMPLETE |
| T3-A7 | File-based gate protocol — `.gate` / `.gate.approved` convention | COMPLETE |
| T3-A8 | `stratum-ui` — monitor, gate, edit, generate (separate project) | COMPLETE |

### Bridge: Task→Step Compiler

| ID | Feature | Status |
|---|---|---|
| T3-1 | Architecture design: three-layer stack | COMPLETE |
| T3-2 | Task→step compiler: `tasks/*.md` → `.stratum.yaml` (acceptance criteria → `ensure` expressions) | COMPLETE |
| T3-3 | `/stratum-speckit` bridge skill — drives spec-kit phases through stratum, emits compiled flow | COMPLETE |

### Compose Skill Refactor

| ID | Feature | Status |
|---|---|---|
| T3-4 | Adopt spec-kit artifact format: design phases produce `spec.md`, `plan.md`, `tasks/` under `.specify/` | COMPLETE |
| T3-5 | Replace custom phase artifacts with spec-kit canonical structure | COMPLETE |
| T3-6 | `stratum-build` skill compiles `tasks/` → `.stratum.yaml`, drives execution via `stratum_plan` loop | COMPLETE |

### Compose Web App Integration

| ID | Feature | Status |
|---|---|---|
| T3-7 | Vision Surface seeds work items from `.specify/` directory on load | COMPLETE |
| T3-8 | Vision Surface reflects live stratum flow state (step status, `ensure` violations = blockers) | COMPLETE |
| T3-9 | Audit trace from `stratum_audit` surfaces in session log / item evidence | COMPLETE |

---

## Track 4 — Consolidation

Merge `coder-compose` into this repo. Restructure developer configuration (`CLAUDE.md`, rules,
skills, memory) from monolithic files into pointed sub-docs.

| ID | Item | Status |
|---|---|---|
| T4-1 | Fresh copy of `coder-compose` content into `app/` — no git history carry-over | COMPLETE |
| T4-2 | Merge `coder-compose/docs/` into `docs/app/` — plans, features, decisions, journal | COMPLETE |
| T4-3 | `CLAUDE.md` restructure — unified pointer doc covering Python lib + MCP + web app | COMPLETE |
| T4-4 | Archive `coder-compose` repo — canonical location is now `app/` in this repo | COMPLETE |
| T4-5 | Extract `app/` to standalone compose project at `/Users/ruze/reg/my/forge/compose/` | COMPLETE |

---

## Track 5 — Pipeline Runtime

Implement the pipeline authoring model. Users define pipelines via Python decorators or skills,
never by writing `.stratum.yaml` by hand. See `docs/features/pipeline-authoring/design.md`.

| ID | Item | Status |
|---|---|---|
| T5-1 | `Capability` and `Policy` enums in `stratum-py` | COMPLETE |
| T5-2 | `@pipeline` / `@phase` decorators — metadata capture and validation (IR compilation is separate; needed for MCP execution mode, not Python harness) | COMPLETE |
| T5-3 | Named assertion vocabulary — `tests_pass`, `files_changed`, `approved`, `file_exists`, etc. | COMPLETE |
| T5-4 | `stratum.toml` project config — policy overrides, capability mapping, connector routing | COMPLETE |
| T5-5 | Run workspace convention — `.stratum/runs/{run-id}/{phase-id}.json` output passing | COMPLETE |
| T5-6 | File-based gate protocol — `.gate` / `.gate.approved` / `.gate.rejected` | COMPLETE |
| T5-7 | Pipeline runtime loop — `run_pipeline()` drives `@pipeline` classes through phases via `Connector` | COMPLETE |

---

## Track 6 — stratum-ui

Separate project. First-party reference UI for Stratum. Four responsibilities: monitor pipeline
runs, approve/reject gate-blocked phases, edit pipeline definitions visually, generate output
(`stratum.toml`, `@pipeline` Python, or `.stratum.yaml` IR). Talks directly to the filesystem
via a thin local HTTP server — not an MCP client.

| ID | Item | Status |
|---|---|---|
| T6-1 | Project scaffold — FastAPI + uvicorn, src layout, `/api/status` `/api/runs` `/api/gates` endpoints | COMPLETE |
| T6-2 | Monitor view — `GET /` run list, `GET /runs/{id}` phase detail with auto-refresh | COMPLETE |
| T6-3 | Gate queue — `GET /gates` view with approve/reject forms, `POST /gates/{id}/{phase}/approve|reject` | COMPLETE |
| T6-4 | Pipeline editor — `GET /editor` form UI, phase CRUD + reorder, draft persisted to `.stratum/pipeline-draft.json` | COMPLETE |
| T6-5 | Generate — export to `stratum.toml`, `@pipeline` Python, `.stratum.yaml` IR | COMPLETE |

---

## Evaluation & Benchmarks

Answers two questions: (1) is Stratum/Compose better than not using it, and (2) which memory tier is better for a given workload.

### Stratum/Compose vs. baseline

The `stratum_audit` trace is the built-in instrument — attempt counts, step durations, ensure failure reasons. The missing piece is a standardized task battery and comparison harness.

| ID | Item | Status |
|---|---|---|
| E-0 | Difficulty taxonomy — collect empirically difficult tasks from session transcripts; classify by failure dimension (cascading incorrectness, ambiguous spec, stale blueprint, self-reporting temptation, multi-file coordination, non-obvious constraint, cross-session dependency, noisy memory) | PLANNED |
| E-1 | Task battery — 5-10 tasks selected from E-0 taxonomy, covering each difficulty dimension, with known-correct outputs | PLANNED |
| E-2 | Automated scorer — `file_exists`, test pass/fail, `compose-reviewer` confidence | PLANNED |
| E-3 | Comparison harness — run task with Stratum vs. without, collect audit traces | PLANNED |
| E-4 | Metrics report — artifact completeness, retry rate, recovery rate, abandonment rate | PLANNED |

### Memory tier comparison

Retrieval precision benchmark: pre-load known patterns into each backend, run tasks that require applying those patterns without being told explicitly, score whether the agent applied them.

| ID | Item | Status |
|---|---|---|
| E-5 | Pattern fixture set — known project-specific patterns to pre-load into each backend | PLANNED |
| E-6 | Retrieval precision test — did agent apply the right pattern without explicit prompting? | PLANNED |
| E-7 | Context efficiency metric — tokens injected vs. tokens actually used per session | PLANNED |
| E-8 | Tier comparison report — Tier 1 vs. Tier 2 on precision, token cost, task outcome | PLANNED |

---

## Distribution & Discovery

| ID | Item | Status |
|---|---|---|
| D-1 | PyPI publish `stratum-py` | COMPLETE |
| D-2 | PyPI publish `stratum-mcp` | COMPLETE |
| D-3 | PyPI metadata (description, readme, license, authors, URLs) | COMPLETE |
| D-4 | Submit `stratum-mcp` to MCP server registry | PLANNED |
| D-5 | Post tutorial to Hacker News / r/ClaudeAI | PLANNED |
| D-6 | Codex integration post (`blog/stratum-in-codex.md`) | COMPLETE |

---

## Pre-release Debt (stratum-mcp 0.2.0)

Must be resolved before publishing 0.2.0 to PyPI.

### Must Fix

| ID | Item | Location | Status |
|---|---|---|---|
| R-1 | `stratum-mcp serve` without `[serve]` extra raises raw `ModuleNotFoundError`; catch `ImportError` and print install hint | `server.py:909` | COMPLETE |
| R-2 | `test_serve.py` imports `fastapi.testclient` unconditionally — breaks `pytest` on base install; guard with `pytest.importorskip` or optional marker | `tests/test_serve.py:11` | COMPLETE |
| R-3 | `_cmd_validate` swallows `OSError` silently — permission-denied on a path is treated as inline YAML; surface file errors explicitly | `server.py:897` | COMPLETE |

### Should Fix

| ID | Item | Location | Status |
|---|---|---|---|
| R-4 | CORS `allow_origins=["*"]` hardcoded — make configurable via `create_app()` parameter | `serve.py:450` | COMPLETE |
| R-5 | `"record_type"` legacy alias in `_record_from_dict` — dead compat shim; 0.2.0 is a clean break | `executor.py:294` | COMPLETE |
| R-6 | `pydantic` not declared in `[serve]` extras — undeclared transitive dependency | `pyproject.toml:29` | COMPLETE |
| R-7 | `stratum_gate_resolve` complete path returns no `output` field; `stratum_step_done` complete path does — decide canonical shape and align | `server.py:259`, `server.py:151` | COMPLETE |
| R-8 | No tests for `stratum_draft_pipeline` MCP tool | `server.py:518` | COMPLETE |

### Cleanup (low risk, do while here)

| ID | Item | Location | Status |
|---|---|---|---|
| R-9 | `first_step_id` computed but never used after `round_start_step_id=None` change | `executor.py:492` | COMPLETE |
| R-10 | `import importlib.resources` dead import inside `_cmd_setup` | `server.py:731` | COMPLETE |

---

## Prioritization Notes

**Next up (as of 2026-03-05):**
- R-1 through R-10 complete — pre-release debt resolved
- Publish `stratum-mcp` 0.2.0 to PyPI (bump version, tag, push)
- D-4 (MCP registry), D-5 (HN/r/ClaudeAI post)

**Longer horizon:**
- T1-12 (TypeScript) — unlocks Cursor/Windsurf users; significant effort
- E-0 → E-8 (Evaluation & Benchmarks) — difficulty taxonomy, task battery, comparison harness
- T1-13/14/15 (DSPy, Temporal, Ray) — Phase 3 per original design
