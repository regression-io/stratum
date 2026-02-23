# STRATUM-2 Architecture

**Status:** Phase 3 — Architecture
**Date:** 2026-02-23
**Related:** [design.md](design.md)

---

## Architecture Decision

**Chosen approach: Pragmatic hybrid** — flat 5-file package with frozen IR dataclasses, `FlowScope` context manager, and structured error types. Rejects sub-package decomposition as over-engineering for v0.1 while adopting the clean architecture's best structural ideas.

Three competing proposals were evaluated:

| Dimension | Minimal | Pragmatic | Clean |
|---|---|---|---|
| Files in `stratum_mcp` | 4 | 5 | 13 |
| Track 1 changes | `begin_flow()` / `end_flow()` functions | `begin_flow()` / `end_flow()` functions | `FlowScope` context manager |
| IR representation | raw dicts | raw dicts | frozen dataclasses |
| Error types | single class | `IRValidationError` only | 3 distinct classes |
| Schema location | inline in `spec.py` | external JSON file | Python dict + version registry |
| DAG output type | dict | `ExecutionResult` dataclass | `FlowResult` dataclass |

**Why not Minimal:** No typed IR representation means every v0.2 schema addition requires hunting through `spec.py` and `executor.py` simultaneously. No structured error types means Claude gets generic string errors, not actionable path + suggestion feedback.

**Why not Clean:** The `ir/` and `dag/` sub-packages are correct for a mature, multi-version codebase. For v0.1 they add 8 files before any logic is written. The anti-corruption `adapter.py` is the right pattern at scale; at this scale it is ceremony without payoff.

**What the hybrid takes from Clean:**
- `FlowScope` async context manager instead of `begin_flow()`/`end_flow()` — exception-safe, cannot be misused
- Frozen IR dataclasses in `spec.py` — typed parsing with clear IR/execution boundary
- `SCHEMAS` version registry — 2 lines that make v0.2 a drop-in
- Three error types — structured path + message + suggestion feedback

---

## System Context

```
┌─────────────────────────────────────────────────────────┐
│  Claude Code (consumer)                                 │
│    generates .stratum.yaml IR                           │
│    calls stratum_validate / stratum_plan / stratum_execute │
└────────────────┬────────────────────────────────────────┘
                 │ MCP (stdio)
┌────────────────▼────────────────────────────────────────┐
│  stratum-mcp (this package)                             │
│    spec.py     — parse + validate IR                    │
│    executor.py — DAG execution loop                     │
│    errors.py   — error types + MCP translation          │
│    auditor.py  — stub                                   │
│    server.py   — FastMCP tools + CLI mode               │
└────────────────┬────────────────────────────────────────┘
                 │ Python imports (public API only)
┌────────────────▼────────────────────────────────────────┐
│  stratum (Track 1 library)                              │
│    FlowScope      — flow context management             │
│    execute_infer  — LLM call + retry + trace            │
│    Budget         — budget envelope                     │
│    TraceRecord    — structured trace output             │
└─────────────────────────────────────────────────────────┘
```

---

## Track 1 Change: `FlowScope`

**File:** `src/stratum/flow_scope.py` (new)

One addition to the Track 1 library. The `begin_flow()` / `end_flow()` pair proposed in the design doc is correct in intent but incorrect in form — callers must remember `end_flow()` in all exception paths. `FlowScope` is the idiomatic Python solution.

```python
"""Public FlowScope — the MCP server's only entry point into flow context."""
from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from .budget import Budget
from .decorators import _FlowContext, _flow_ctx


@asynccontextmanager
async def FlowScope(budget: Budget | None = None) -> AsyncGenerator[str, None]:
    """
    Async context manager. Establishes a flow context for the duration of the block.
    Yields the flow_id. All execute_infer calls within the block inherit this
    flow_id and budget.

        async with FlowScope(budget=Budget(ms=5000)) as flow_id:
            result = await execute_infer(spec, inputs, flow_budget=budget)
    """
    flow_id = str(uuid.uuid4())
    flow_budget = budget.clone() if budget is not None else None
    ctx = _FlowContext(flow_id=flow_id, budget=flow_budget)
    token = _flow_ctx.set(ctx)
    try:
        yield flow_id
    finally:
        _flow_ctx.reset(token)
```

`FlowScope` is added to `stratum/__init__.py` exports and `__all__`. No other Track 1 changes.

---

## Package Structure

```
stratum-mcp/
  pyproject.toml
  src/stratum_mcp/
    __init__.py      (empty)
    server.py        FastMCP entry point, tool registration, CLI dual-mode
    spec.py          IR types, schema registry, parser, semantic validator
    executor.py      DAG execution, ref resolution, ensure eval, FlowResult
    errors.py        IRParseError / IRValidationError / IRSemanticError + MCP translation
    auditor.py       stub

  tests/
    integration/
      test_roundtrip.py      full round-trip: YAML in → execute → trace out
      test_cli.py            stratum-mcp validate exits 0/1
    contracts/
      test_ir_schema.py      valid/invalid IR against schema
    invariants/
      test_dag.py            topo sort, ref resolution, ensure eval
```

---

## Component Design

### `spec.py`

Three responsibilities, deliberately colocated: IR type definitions, schema registry, and parsing/validation. They change together when the IR schema evolves — separating them would require editing two files for every schema change.

**IR types (frozen dataclasses):**

```python
@dataclass(frozen=True)
class IRBudgetDef:
    ms: int | None = None
    usd: float | None = None

@dataclass(frozen=True)
class IRContractDef:
    name: str
    fields: dict[str, Any]

@dataclass(frozen=True)
class IRFunctionDef:
    name: str
    mode: Literal["infer", "compute"]
    intent: str
    input_schema: dict[str, Any]
    output_contract: str
    ensure: list[str]           # string expressions — compiled at execution time
    budget: IRBudgetDef | None
    retries: int
    model: str | None

@dataclass(frozen=True)
class IRStepDef:
    id: str
    function: str
    inputs: dict[str, str]      # {param: "$-reference or literal"}
    depends_on: list[str]

@dataclass(frozen=True)
class IRFlowDef:
    name: str
    input_schema: dict[str, Any]
    output_contract: str
    budget: IRBudgetDef | None
    steps: list[IRStepDef]

@dataclass(frozen=True)
class IRSpec:
    version: str
    contracts: dict[str, IRContractDef]
    functions: dict[str, IRFunctionDef]
    flows: dict[str, IRFlowDef]
```

**Schema registry:**

```python
# SCHEMAS maps IR version string → JSON Schema dict.
# Adding v0.2: SCHEMAS["0.2"] = IR_SCHEMA_V02. Nothing else changes.
SCHEMAS: dict[str, dict] = {
    "0.1": IR_SCHEMA_V01,
}
```

The JSON Schema is inlined as a Python dict (not a `.json` file) — no asset management required, ships with the package automatically.

**Public function:**

```python
def parse_and_validate(raw_yaml: str) -> IRSpec:
    """
    Parse raw YAML → validate schema → validate semantics → return IRSpec.
    Raises IRParseError, IRValidationError, or IRSemanticError.
    """
```

Three validation stages:
1. YAML parse (`yaml.safe_load`) → `IRParseError` on syntax failure
2. JSON Schema validation (`jsonschema.Draft202012Validator`) → `IRValidationError` with path + suggestion
3. Semantic validation (reference integrity) → `IRSemanticError` — catches what JSON Schema cannot: undefined function refs, undefined contract refs, undefined `depends_on` step ids

---

### `errors.py`

Three IR error types and a single MCP translation function.

```python
@dataclass
class IRParseError(Exception):
    raw_error: str          # YAML syntax error from pyyaml

@dataclass
class IRValidationError(Exception):
    path: str               # JSON path to failing node, e.g. "flows.process_feedback.steps[0]"
    message: str            # human-readable violation
    suggestion: str         # actionable fix hint for Claude

class IRSemanticError(Exception):
    def __init__(self, message: str, path: str = "") -> None: ...
```

Three distinct types because they have distinct remediation paths. `IRValidationError.suggestion` is what Claude uses to fix its generated YAML. `IRSemanticError` catches reference integrity failures that JSON Schema cannot express.

**MCP translation:**

```python
def exception_to_mcp_error(exc: Exception) -> dict[str, Any]:
    """
    Single translation point. Maps any exception to a structured MCP error response.
    Never raises. Never exposes internal tracebacks.
    Maps: IRParseError, IRValidationError, IRSemanticError, BudgetExceeded,
          PostconditionFailed, ParseFailure, PreconditionFailed, StratumError, unknown.
    """
```

All error translation happens here and only here. `server.py` never catches `Exception` directly.

---

### `executor.py`

Three responsibilities colocated for the same reason as `spec.py` — they change together:

1. **`ensure` expression evaluation** — string `"result.confidence > 0.7"` → `Callable`
2. **`$` reference resolution** — `"$.input.text"` → concrete value
3. **DAG execution loop** — topological sort → step dispatch → `FlowResult`

**`ensure` evaluation:**

```python
def compile_ensure(expr: str) -> Callable[[Any], bool]:
    """
    Compile a string expression into a callable.
    Restricted namespace: {__builtins__: {}, result: <output>}.
    Only `result` is in scope. No imports, no exec.
    """
    code = compile(expr, "<ensure_expr>", "eval")
    def evaluator(result: Any) -> bool:
        return bool(eval(code, {"__builtins__": {}}, {"result": result}))
    return evaluator
```

Isolated in a function — the evaluation strategy can be replaced without touching anything else. Restricted namespace eliminates meaningful attack surface for Claude-generated expressions.

**`$` reference resolution:**

```python
def resolve_ref(ref: str, flow_inputs: dict, step_outputs: dict) -> Any:
    """
    Supported:
      $.input.<field>               → flow_inputs[field]
      $.steps.<id>.output           → step_outputs[id]
      $.steps.<id>.output.<field>   → step_outputs[id][field]
      <literal>                     → returned as-is
    """
```

Non-`$` strings are returned as literals — allows passing static values without quoting.

**DAG execution:**

```python
@dataclass
class FlowResult:
    flow_name: str
    flow_id: str
    output: Any
    steps: list[StepResult]
    total_cost_usd: float
    total_duration_ms: int
    success: bool
    error: str | None = None

async def execute_flow(spec: IRSpec, flow_name: str, inputs: dict) -> FlowResult:
    """
    1. Look up flow definition
    2. Establish FlowScope (sets flow_id + budget on _flow_ctx)
    3. Topological sort: Kahn's algorithm on depends_on + implicit $ ref dependencies
    4. For each step in order:
       a. Build InferSpec from IRFunctionDef
       b. Resolve $ references in step inputs
       c. Call execute_infer(spec, inputs, flow_budget, flow_id)
       d. Accumulate StepResult
    5. Return FlowResult
    """
```

`InferSpec` is built inline — `return_type=None` so `execute_infer` returns a plain `dict` (no Pydantic registry lookup). `ensure` constraints are compiled from string expressions and passed as `InferSpec.ensure` callables. Step cost and attempt counts are extracted from the library's trace store by `flow_id` (read-only, no coupling to execution internals).

**Library imports in `executor.py`** (all public API):
- `stratum.executor.execute_infer`, `stratum.executor.InferSpec`
- `stratum.budget.Budget`
- `stratum.FlowScope`
- `stratum.trace.all_records` (read-only, cost extraction)

---

### `server.py`

FastMCP entry point with CLI dual-mode.

```python
mcp = FastMCP("stratum-mcp", description="...")

@mcp.tool(...)
async def stratum_validate(spec: str, ctx: Context) -> dict: ...

@mcp.tool(...)
async def stratum_plan(plan: str, ctx: Context) -> dict: ...   # delegates to stratum_validate

@mcp.tool(...)
async def stratum_execute(spec: str, flow: str, inputs: dict, ctx: Context) -> dict: ...

@mcp.tool(...)
async def stratum_audit(path: str, ctx: Context) -> dict: ...  # stub

def main() -> None:
    # CLI mode: stratum-mcp validate <yaml_string_or_file_path>
    # Server mode: mcp.run(transport="stdio")
```

`stratum_plan` is identical to `stratum_validate` in code. The distinction is semantic — `stratum_plan` is called before execution to confirm a spec is valid, `stratum_validate` is called as a general-purpose checker. The skill instructions enforce the calling convention; the code is the same.

CLI mode (`sys.argv` check in `main()`) handles the PostToolUse hook use case without a separate entry point.

---

### `auditor.py`

```python
async def audit(path: str) -> dict:
    return {"message": "audit not yet implemented", "path": path}
```

Stub for v0.1. Full implementation deferred pending real usage data.

---

## Data Flows

**Validation path:**

```
Claude generates YAML
  → stratum_validate(spec: str)
    → spec.py: parse_and_validate()
      → yaml.safe_load()        [IRParseError on failure]
      → jsonschema.validate()   [IRValidationError with path + suggestion on failure]
      → _validate_semantics()   [IRSemanticError on reference integrity failure]
      ← IRSpec (frozen)
    → errors.py: exception_to_mcp_error()   [on any failure]
  ← {valid: bool, errors: list[dict]}
```

**Execution path:**

```
Claude calls stratum_execute(spec, flow_name, inputs)
  → spec.py: parse_and_validate()   [re-validate — never trust unvalidated IR]
  → executor.py: execute_flow(IRSpec, flow_name, inputs)
    → FlowScope(budget=flow_budget) as flow_id
      → _topological_sort()            [Kahn's on depends_on + implicit $ refs]
      → for each step:
          → compile_ensure(exprs)      [str → Callable list]
          → InferSpec(...)             [return_type=None]
          → resolve_inputs()           [$ refs → concrete values]
          → execute_infer(spec, inputs, flow_budget, flow_id)
            [library: prompt compile, cache injection, LLM call, retry, trace write]
          ← Any (plain dict — no Pydantic instantiation)
      ← step_outputs dict
    ← FlowResult
  ← {success, output, trace_records, cost_usd, duration_ms, flow_id}
```

---

## Interfaces & Contracts

### Library boundary

The MCP package imports exactly these symbols from `stratum` (all public API, no `_` imports):

| Symbol | From | Used in |
|---|---|---|
| `execute_infer` | `stratum.executor` | `executor.py` |
| `InferSpec` | `stratum.executor` | `executor.py` |
| `Budget` | `stratum.budget` | `executor.py` |
| `FlowScope` | `stratum` | `executor.py` |
| `all_records` | `stratum.trace` | `executor.py` (read-only) |
| `StratumError` et al. | `stratum.exceptions` | `errors.py` (translation only) |

Any import of a `_`-prefixed name anywhere in `stratum_mcp` is an architecture violation.

### `execute_infer` call contract

`execute_infer` is called with `return_type=None`. This means:
- The library skips Pydantic instantiation
- The LLM response is parsed as a raw dict (tool call arguments parsed via `json.loads`)
- `ensure` callables receive a `dict`, not a model instance — `result.confidence` becomes `result["confidence"]` unless the dict allows attribute access

**Implementation note:** The `ensure` string expressions from IR assume attribute-style access (`result.confidence`), not dict-style (`result["confidence"]`). The adapter must wrap the dict in a `SimpleNamespace` or equivalent before passing to `ensure` evaluators. This is a known gap not called out in the design doc.

### IR tool input contract

`spec` parameters in all tools accept **inline YAML only** — not file paths. If Claude wants to persist a spec as a file, it does so separately via `Write`. The tool always takes the YAML string directly. This eliminates filesystem coupling from the MCP layer.

Exception: the CLI mode (`stratum-mcp validate <arg>`) accepts both — it heuristically detects file paths by attempting `open()` and falling back to inline.

---

## Dependencies

```toml
[project]
name = "stratum-mcp"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "stratum",          # monorepo sibling — path dep in development, tag in release
    "mcp>=1.0",         # official Anthropic MCP SDK
    "jsonschema>=4.20", # IR schema validation
    "pyyaml>=6.0",      # YAML parsing
]
```

`jsonschema` and `pyyaml` are MCP-server-only. They are not added to the Track 1 library's dependencies.

---

## Security Considerations

**`ensure` expression evaluation:** `eval()` with `{"__builtins__": {}}` restricts the execution namespace. Only `result` is in scope. The expressions are Claude-generated (not user-provided), and the restricted namespace prevents meaningful exploitation. This is documented as a v0.1 decision — a proper expression DSL is a v0.2 concern if the attack surface changes (e.g., if user-provided IR is ever accepted).

**`PreToolUse` hook on `Bash`:** Intercepts direct LLM client instantiation. This is advisory, not preventive, unless API keys are withheld from the environment. Document clearly in the hook implementation.

**Inline YAML spec:** Claude generates the YAML; it is never loaded from user-controlled paths in MCP mode. The CLI mode reads files but only outputs structured validation results — no execution.

---

## Build Sequence

```
1. Track 1: src/stratum/flow_scope.py — FlowScope context manager
   src/stratum/__init__.py — add FlowScope to exports and __all__
   test: FlowScope sets flow_id, resets on exit, exception-safe

2. stratum-mcp/pyproject.toml

3. spec.py — IR dataclasses, SCHEMAS registry, parse_and_validate()
   test (contracts/): valid v0.1 YAML → correct IRSpec; invalid YAML → correct error type

4. errors.py — three IR error types + exception_to_mcp_error()
   test (contracts/): each error type maps to correct MCP response shape

5. executor.py — compile_ensure(), resolve_ref(), execute_flow()
   test (invariants/): topological sort; ref resolution; ensure eval; ensure builtins blocked

6. auditor.py — stub

7. server.py — FastMCP tools, CLI mode

8. Integration test (integration/): full round-trip YAML → execute → FlowResult
   Integration test: invalid YAML → structured error with path + suggestion
   Integration test: stratum-mcp validate exits 0/1

9. Claude Code wiring:
   ~/.claude/skills/plan.md
   PostToolUse hook on Write (.stratum.yaml files)
   PreToolUse hook on Bash (advisory LLM client interception)
   CLAUDE.md rules block
```

---

## Known Gaps & Deferred Work

| Gap | Description | Resolution |
|---|---|---|
| G9 | `ensure` attribute vs dict access mismatch | Wrap dict in `SimpleNamespace` before eval in executor.py |
| G4 | IR contracts bypass Pydantic registry | `return_type=None` → plain dict output. IR contracts enforced via `ensure` callables only. |
| G7 | `_global_cache` shared across MCP sessions | Acceptable for v0.1. Session isolation in v0.2. |
| G5 | No IR encoding for `parallel`, `debate`, `race` | Defer to v0.2. `SCHEMAS["0.2"]` drop-in path established. |
| G6 | No IR encoding for `stable=False` | Defer to v0.2. |

---

## Trade-offs vs Alternatives

**vs Minimal (4 files flat):** Minimal has no typed IR representation — every change to the execution loop requires reading raw dicts with no type checking. When v0.2 adds `parallel` steps, there is no clear place to add the new type and no compile-time guarantee that the executor handles all step types. The frozen dataclasses add ~30 lines upfront and pay off on the first schema extension.

**vs Clean (13+ files, sub-packages):** The clean architecture's `ir/` and `dag/` sub-packages encode the same separation as this design's `spec.py` and `executor.py`, with more files. The anti-corruption `adapter.py` is the right long-term pattern but adds ceremony at v0.1 scale. The `FlowScope` context manager and three-error-type system from the clean proposal are taken directly — these are the decisions that compound well regardless of file layout.
