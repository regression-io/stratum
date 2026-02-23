# STRATUM-2: MCP Server + Claude Code Integration

**Status:** Design — Phase 1
**Date:** 2026-02-23
**Roadmap:** Phase 2 — MCP Server + TypeScript Library

---

## What This Is

STRATUM-2 gives Claude Code a formal execution model. Instead of improvising retry loops and ad hoc LLM calls, Claude generates a `.stratum.yaml` IR spec, validates it via MCP, executes it through the Stratum runtime, and returns structured trace records. The result: typed plans, budget enforcement, contract-validated outputs, and auditable traces — applied to Claude's own orchestration.

Two audiences:
- **Developers** — see typed plans before execution, can review what will run
- **Vibe coders** — see a plain-language numbered list and a cost estimate, click "yes"

Neither audience sees `.stratum.yaml`. It is generated, validated, and executed behind the scenes.

---

## Scope

**In STRATUM-2:**
- `.stratum.yaml` IR schema (v0.1) — linear step DAGs, infer/compute functions, contracts
- MCP server (`stratum-mcp`) — 4 tools: validate, execute, plan, audit
- Claude Code wiring — settings, skill, hooks, CLAUDE.md rules
- One required library change: expose `begin_flow()` / `end_flow()` publicly (see Gap 1 below)

**Deferred:**
- TypeScript library — separate feature, not a prerequisite for the MCP server
- IR encoding for `parallel`, `debate`, `race`, `@refine`, HITL, `stable=False` — v0.2+
- `stratum_audit` implementation — needs real usage data, placeholder only in v0.1
- Native Anthropic/Claude Code integration — requires external cooperation

---

## Three Components

### 1. The IR (`.stratum.yaml`)

The interchange format between Claude (generator) and the MCP server (enforcer). Claude never shows it to the user. It is validated before any execution.

**v0.1 schema — what it encodes:**

```yaml
version: "0.1"

contracts:
  SentimentResult:
    label:
      type: enum
      values: ["positive", "negative", "neutral"]
    confidence:
      type: number
    reasoning:
      type: string

functions:
  classify_sentiment:
    mode: infer
    intent: "Classify the emotional tone of customer feedback"
    input:
      text: { type: string }
    output: SentimentResult
    ensure:
      - "result.confidence > 0.7"
    budget: { ms: 500, usd: 0.001 }
    retries: 3

flows:
  process_feedback:
    input:
      text: { type: string }
    output: SentimentResult
    budget: { ms: 5000, usd: 0.01 }
    steps:
      - id: classify
        function: classify_sentiment
        inputs:
          text: "$.input.text"
```

**What the IR does NOT encode in v0.1:** `parallel`, `debate`, `race`, `@refine`, HITL, `quorum`, `stable=False`. These are library-only for now.

**Validation:** `jsonschema` against a JSON Schema meta-schema. The validator is a separate `spec.py` module, not a Python class in the library — the library's `@contract` system uses Pydantic classes, not YAML.

---

### 2. MCP Server (`stratum-mcp`)

A separate package that wraps the Track 1 library and exposes it as MCP tools.

**Package structure:**
```
stratum-mcp/
  pyproject.toml
  src/stratum_mcp/
    server.py      # FastMCP entry point, tool registration, lifespan
    spec.py        # IR parser + jsonschema validator
    executor.py    # DAG execution loop — topological sort, $ reference interpolation
    auditor.py     # stub for v0.1; full implementation deferred
```

**SDK:** `mcp` (official Anthropic package, not the `fastmcp` standalone fork). Import path: `from mcp.server.fastmcp import FastMCP, Context`. Transport: stdio.

**Four tools:**

| Tool | Input | What it does |
|---|---|---|
| `stratum_validate` | `spec: str` (inline YAML or file path) | Parses + validates against IR schema. Returns `{valid, errors}` |
| `stratum_plan` | `plan: str` (inline YAML) | Same code path as `stratum_validate` — semantic distinction only, enforced by skill instructions |
| `stratum_execute` | `spec: str`, `flow: str`, `inputs: dict` | Runs a flow, returns `{output, trace_records, cost_usd, duration_ms}` |
| `stratum_audit` | `path: str` | Stub in v0.1. Returns `{message: "audit not yet implemented"}` |

**The DAG executor** (`executor.py`) is the core new code in this package. It:
1. Parses the spec
2. Topologically sorts steps by `depends_on`
3. Resolves `$.input.*` and `$.steps.<id>.output` references
4. Calls `execute_infer` (from the library) for each `infer` step
5. Evaluates `ensure` string expressions against the result (see design decision below)
6. Returns all step outputs and a trace summary

**CLI sub-command for the hook:** The PostToolUse hook uses `stratum-mcp validate <file>` as a shell command, but the MCP server is a stdio server. Solution: `server.py:main()` checks `sys.argv` — if called with `validate <path>`, it runs validation and exits; otherwise it starts the stdio server. One entry point, two modes.

---

### 3. Claude Code Wiring

Four files create the enforcement stack, weakest to strongest:

**`CLAUDE.md` rules** — prose instructions: use `stratum_plan` before multi-step tasks, route through `stratum_execute`, call `stratum_audit` on generated LLM code.

**`~/.claude/skills/plan.md`** — the `/plan` skill. Generates `.stratum.yaml` internally, calls `stratum_plan` to validate it (loops until valid), presents a plain-language numbered list + estimated cost to the user, asks "Proceed?", then calls `stratum_execute`. The YAML is never shown to the user. When output is persistent code, annotates LLM-touching functions with `@infer`, `@compute`, `@contract`, `@flow`.

**PostToolUse hook on `Write`** — validates any `.stratum.yaml` file as it's written. Blocks invalid specs from persisting.

**PreToolUse hook on `Bash` (environment restriction)** — intercepts direct LLM API client instantiation (`anthropic.Anthropic(...)`, `openai.OpenAI(...)`). Only meaningful if API keys are not in environment; otherwise advisory. Best deployed in controlled environments where the MCP server holds the keys.

---

## Design Decisions

### Decision 1: Same repo or separate package?

The design doc shows `stratum-mcp/` as a separate package with `pip install stratum-mcp`. Two options:

**A) Monorepo** — `stratum-mcp/` lives in the same git repo as `stratum/`. Simpler cross-package development, single CI, single version bump story.

**B) Separate repo** — `github.com/regression-io/stratum-mcp`. Clean separation, independent release cycles, MCP server can bump without touching the library.

Recommendation: **monorepo** for v0.1. The MCP server has a hard dependency on the library at a specific internal API. Developing them together in one repo avoids the coordination overhead while the interface is still settling.

---

### Decision 2: How to expose flow context to the MCP server

The library's `_flow_ctx` ContextVar is private. The MCP server needs to set it so that nested `execute_infer` calls inherit `flow_id` and session cache.

**A) Import private names** — `from stratum.decorators import _flow_ctx, _FlowContext`. Works now, brittle.

**B) Add public API to Track 1** — `stratum.begin_flow(budget) -> FlowToken` and `stratum.end_flow(token)`. Clean contract, requires one Track 1 change.

Recommendation: **Option B**. The Track 1 change is small (two public wrapper functions) and makes the boundary explicit. This is the only required Track 1 change for STRATUM-2.

---

### Decision 3: `ensure` expression evaluation in IR

`InferSpec.ensure` takes `list[Callable]`. The IR schema shows `ensure: ["result.confidence > 0.7"]` — string expressions. The MCP server must evaluate these.

**A) `eval()` with restricted `result` namespace** — `eval(expr, {"__builtins__": {}}, {"result": output})`. Simple, covers the common cases, carries eval's risks (mitigated by the restricted namespace and the fact that Claude generates the YAML).

**B) Restrict to `result.<field> <op> <literal>` only** — parse with a tiny regex-based DSL. Safer, covers ~90% of use cases, fails on nested field access.

**C) Disallow `ensure` in IR v0.1** — omit the key from the JSON Schema. Claude can still use `ensure` when calling the Python library directly.

Recommendation: **Option A** with restricted namespace for v0.1. The YAML is generated by Claude under constraints (not user-provided), and the restricted namespace eliminates the meaningful attack surface. Revisit with a proper DSL in v0.2.

---

### Decision 4: `spec` field as file path vs inline YAML

`stratum_execute` and `stratum_validate` both accept `spec: str`. Ambiguous.

**A) Inline YAML only** — simpler, no file system access, Claude embeds the full spec in the tool call.

**B) File path or inline** — detect by checking if the string is a valid file path and the file exists; otherwise treat as inline YAML.

Recommendation: **Inline YAML only for v0.1**. Avoids filesystem coupling. If Claude wants to save a spec file, it does so separately; the tool always takes inline YAML. Document this clearly in the tool description.

---

### Decision 5: TypeScript library — in scope or separate?

The roadmap bundles TypeScript library with Phase 2. The MCP server does not depend on it. The TypeScript library targets a different audience (Next.js/frontend developers).

Recommendation: **Separate feature**. STRATUM-2 ships with the MCP server and IR spec. TypeScript library is STRATUM-3 or a parallel track. Bundling them creates scope risk for the MCP server.

---

## Gaps Requiring Attention Before Build

These are known issues surfaced by reading the Track 1 implementation:

| Gap | Description | Resolution |
|---|---|---|
| G1 | No public `execute_flow()` — MCP must implement DAG executor | Build in `executor.py` |
| G2 | `_flow_ctx` not exported | Add `begin_flow()` / `end_flow()` to Track 1 (Decision 2) |
| G3 | `ensure` string eval | Use restricted `eval()` (Decision 3) |
| G4 | IR contracts bypass Pydantic registry | Use `jsonschema.validate()` + return plain dict — no `instantiate()` |
| G5 | No IR encoding for concurrency primitives | Defer to v0.2 |
| G6 | No IR encoding for `stable=False` | Defer to v0.2 |
| G7 | `_global_cache` shared across MCP sessions | Acceptable for v0.1; add session isolation in v0.2 |
| G8 | `stratum-mcp validate` CLI mode | Handle in `main()` via `sys.argv` check |

---

## Build Order

```
1. Track 1 change: add begin_flow() / end_flow() public API
2. IR JSON Schema (meta-schema for .stratum.yaml)
3. spec.py — YAML parser + jsonschema validator
4. executor.py — DAG executor (topological sort, $ references, execute_infer calls)
5. server.py — FastMCP server, tool registration, lifespan, CLI mode
6. Claude Code wiring — settings, skill, hooks, CLAUDE.md
7. Integration test: full round-trip (Claude generates spec → validate → execute → trace)
8. stratum_audit stub
```

---

## Open Questions for Gate

1. **Monorepo vs separate repo** — confirmed above as monorepo recommendation. Do you agree?
2. **TypeScript library** — confirmed above as separate feature. Do you agree?
3. **`ensure` evaluation** — restricted `eval()` for v0.1 acceptable?
4. **v0.1 IR scope** — comfortable shipping without `parallel`, `refine`, HITL encoding?
5. **`stratum_audit` stub** — acceptable to ship as a stub that returns "not yet implemented"?
