# Stratum Roadmap

**Last updated:** 2026-02-25

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
| T1-11 | End-to-end validation against real LLM | PLANNED |
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
| T2-9 | `stratum-mcp setup` CLI command | COMPLETE |
| T2-10 | `stratum-mcp validate <file>` CLI command | COMPLETE |
| T2-11 | Published to PyPI as `stratum-mcp` 0.1.2 | COMPLETE |
| T2-12 | 66 passing tests (contracts, invariants, integration) | COMPLETE |
| T2-13 | `stratum-mcp uninstall` command | COMPLETE |
| T2-14 | FlowState persistence (survive MCP server restart) | PLANNED |
| T2-15 | `ensure` file-aware builtins (`file_exists`, `file_contains`) | COMPLETE |
| T2-16 | Step output contracts (schema validation in `stratum_step_done`) | COMPLETE |
| T2-17 | `stratum_commit` — explicit flow-state checkpoint with label | PLANNED |
| T2-18 | `stratum_revert` — roll back to a named checkpoint, trace records revert | PLANNED |

### Forge Integration

Enable the `forge` skill to use Stratum as its execution backbone. See `docs/plans/2026-02-24-forge-stratum-integration-plan.md`.

| ID | Feature | Status |
|---|---|---|
| T2-F1 | Result schema convention for forge steps | PLANNED |
| T2-F2 | `ensure` file-aware builtins (→ T2-15) | COMPLETE |
| T2-F3 | Step output contracts (→ T2-16) | COMPLETE |
| T2-F4 | Forge skill emits `.stratum.yaml` | COMPLETE |

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
| T2-S10 | `/forge` rewrite — emits `.stratum.yaml`, uses `stratum_plan` loop (→ T2-F4) | COMPLETE |

### Memory & Hooks

Three tiers — default is zero-dependency. Opt-in tiers add semantic retrieval without changing the skill interface.

#### Tier 1 — MEMORY.md (default, zero dependencies)

| ID | Feature | Status |
|---|---|---|
| T2-M1 | `## Memory` sections in all 9 skills — read/write MEMORY.md | COMPLETE |
| T2-M2 | `SessionStart` hook — auto-inject relevant MEMORY.md entries at session open | PLANNED |
| T2-M3 | `Stop` hook — auto-append session summary to MEMORY.md at session close | PLANNED |
| T2-M4 | `PostToolUseFailure` hook — auto-record ensure failures and tool errors | PLANNED |

#### Tier 2 — SmartMemory lite (opt-in, pip only, no Docker)

`pip install smartmemory[lite]` — local SQLite graph + usearch vectors + markdown notes at `~/.smartmemory/`. No network calls, no Docker, no LLM extraction. Uses `lite_context()` / `create_lite_memory()` directly. Replaces MEMORY.md read/write with `memory.search()` / `memory.ingest()`.

| ID | Feature | Status |
|---|---|---|
| T2-SM1 | `SessionStart` hook — `memory.search()` for project-relevant context | PLANNED |
| T2-SM2 | `Stop` hook — `memory.ingest()` session summary as `episodic` memory | PLANNED |
| T2-SM3 | `PostToolUseFailure` hook — `memory.ingest()` failures as `observation` memory | PLANNED |
| T2-SM4 | Skills use `memory.search()` instead of MEMORY.md when lite backend configured | PLANNED |

#### Tier 3 — SmartMemory full (opt-in, requires Docker stack or remote API)

Full SmartMemory service — multi-tenant, LLM entity extraction, Wikidata grounding, REST API. Uses `smartmemory-mcp` HTTP client. Same hook/skill interface as Tier 2 but backed by the remote API.

| ID | Feature | Status |
|---|---|---|
| T2-SM5 | `SessionStart` / `Stop` / `PostToolUseFailure` hooks via `smartmemory-mcp` | PARKED |
| T2-SM6 | Skills use `memory_search` MCP tool when full backend configured | PARKED |

---

## Evaluation & Benchmarks

Answers two questions: (1) is Stratum/Forge better than not using it, and (2) which memory tier is better for a given workload.

### Stratum/Forge vs. baseline

The `stratum_audit` trace is the built-in instrument — attempt counts, step durations, ensure failure reasons. The missing piece is a standardized task battery and comparison harness.

| ID | Item | Status |
|---|---|---|
| E-1 | Task battery — 5-10 representative coding tasks with known-correct outputs | PLANNED |
| E-2 | Automated scorer — `file_exists`, test pass/fail, `forge-reviewer` confidence | PLANNED |
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
| D-6 | Codex integration post (`blog/stratum-in-codex.md`) | PLANNED |

---

## Prioritization Notes

**Highest leverage, shortest path:**
- T2-M2/M3/M4 (hooks) — passive memory capture; one afternoon, no new MCP tools needed
- T2-13 (`uninstall`) — users can't safely remove Stratum right now
- D-4 (MCP registry) — discovery channel with minimal effort

**Real validation needed before broader push:**
- T1-11 (end-to-end test against real LLM) — `stratum-py` is published but nobody has proven it runs outside tests
- D-5 (post to HN) — should happen after T1-11 confirms Track 1 actually works

**Longer horizon:**
- T1-12 (TypeScript) — unlocks Cursor/Windsurf users; significant effort
- T2-14 (FlowState persistence) — needed for long-running flows across sessions
- T2-17/18 (commit/revert) — flow-state checkpoints and rollback; git is one implementation; natural companion to T2-14
- T1-13/14/15 (DSPy, Temporal, Ray) — Phase 3 per original design
