# STRATUM-2 Implementation Blueprint

**Status:** Phase 4 — Blueprint
**Date:** 2026-02-23
**Related:** [design.md](design.md) · [architecture.md](architecture.md)

---

## Blueprint Verification Summary

All architecture doc claims verified against actual source. Corrections documented below.

### Corrections Table

| Architecture doc claim | Actual finding | Action |
|---|---|---|
| "`return_type=None` → plain dict output" | With `return_type=None`, `_resolve_return_schema` returns `({}, "none")`. The empty schema `{}` hits the **primitive-wrapper branch** (executor.py:175–185): tool schema becomes `{"type": "object", "properties": {"value": {}}, "required": ["value"]}`. LLM returns `{"value": X}` and executor unwraps to `X`. If `X` is a dict (IR output is an object), the caller receives a dict. | `ensure` callables compiled from strings receive a raw dict. `result.confidence` fails on a dict. **G9 fix must happen inside `compile_ensure`**: wrap dict in `SimpleNamespace` before eval. |
| `begin_flow()` / `end_flow()` mentioned as rejected alternative | These functions **do not exist** anywhere in the codebase. The `@flow` decorator calls `_flow_ctx.set()`/`_flow_ctx.reset()` inline. | No impact — `FlowScope` is the correct choice. Do not attempt to call `begin_flow()`/`end_flow()`. |
| `_FlowContext(flow_id, budget)` | `_FlowContext` has three fields: `flow_id: str`, `budget: Budget | None`, `session_cache: dict` (default_factory=dict). decorators.py:22–26. | `FlowScope` must pass `session_cache={}` explicitly or rely on default_factory. Use `_FlowContext(flow_id=flow_id, budget=flow_budget)` — default_factory handles `session_cache`. |
| `FlowScope` exists in `stratum/__init__.py` | `FlowScope` does not exist. `flow_scope.py` does not exist. No `FlowScope` import or `__all__` entry in `__init__.py`. | Build step 1: create `flow_scope.py`, add to `__init__.py`. |
| `from mcp.server.fastmcp import FastMCP, Context` | Confirmed correct for `mcp>=1.0` (official SDK). | No change. |
| `jsonschema.Draft202012Validator` and `jsonschema.exceptions.best_match` | Confirmed: `from jsonschema import Draft202012Validator` and `from jsonschema.exceptions import best_match`. `best.path` is a `collections.deque` — convert with `".".join(str(p) for p in best.path)`. | No change to architecture; note deque conversion in parser.py. |

---

## Critical File References

### `execute_infer` — `src/stratum/executor.py:125–130`

```python
async def execute_infer(
    spec: InferSpec,
    inputs: dict[str, Any],
    flow_budget: Budget | None = None,
    flow_id: str | None = None,
) -> Any:
```

Call site in `stratum_mcp/executor.py`:
```python
output = await execute_infer(spec, resolved_inputs, flow_budget=step_budget, flow_id=flow_id)
```

### `InferSpec` — `src/stratum/executor.py:38–57`

```python
@dataclass
class InferSpec:
    fn: Callable
    intent: str
    context: list[str]
    ensure: list[Callable]
    given: list[Callable]
    model: str | None
    temperature: float | None
    budget: Budget | None
    retries: int
    cache: str
    stable: bool
    quorum: int | None
    agree_on: str | None
    threshold: int | None
    return_type: Any
    parameters: dict[str, Any]
```

`InferSpec` is a plain `@dataclass` (not frozen). All fields are positional — use keyword args when constructing.

### `_FlowContext` — `src/stratum/decorators.py:22–26`

```python
@dataclasses.dataclass
class _FlowContext:
    flow_id: str
    budget: Budget | None
    session_cache: dict = dataclasses.field(default_factory=dict)
```

### `_flow_ctx` ContextVar — `src/stratum/decorators.py:29–31`

```python
_flow_ctx: contextvars.ContextVar[_FlowContext | None] = contextvars.ContextVar(
    "_flow_ctx", default=None
)
```

### `@flow` set/reset pattern — `src/stratum/decorators.py:284–291`

```python
ctx = _FlowContext(flow_id=flow_id, budget=flow_budget)
token = _flow_ctx.set(ctx)
try:
    result = await fn(*args, **kwargs)
finally:
    _flow_ctx.reset(token)
```

`FlowScope` must replicate this pattern exactly.

### `Budget.clone()` — `src/stratum/budget.py:56–61`

```python
def clone(self) -> Budget:
    return Budget(ms=self.ms, usd=self.usd)
```

`Budget.__init__` resets `_start_ms` and `_spent_usd` via `field(default_factory=...)` and `field(default=0.0)`. Clone is always safe to call.

### `stratum/__init__.py` — current `__all__` does NOT include `FlowScope`

Current last import block ends at line 41. Add after `from .concurrency import parallel, debate, race`:
```python
from .flow_scope import FlowScope
```

Add `"FlowScope"` to `__all__` in the `# Configuration` section (near `configure` and `run`).

### Test mock pattern — `tests/test_executor.py:41–56`

```python
def _make_response(data: dict) -> MagicMock:
    tool_call = MagicMock()
    tool_call.function.arguments = json.dumps(data)
    message = MagicMock()
    message.tool_calls = [tool_call]
    choice = MagicMock()
    choice.message = message
    response = MagicMock()
    response.choices = [choice]
    response.usage = MagicMock(prompt_tokens=50, completion_tokens=20)
    return response

# Patch sites:
with patch("litellm.acompletion", new=AsyncMock(return_value=mock_resp)):
    with patch("litellm.completion_cost", return_value=0.001):
        result = await execute_infer(spec, inputs)
```

**Important for `return_type=None`:** The LLM response must wrap the output dict as `{"value": <dict>}` because the primitive-wrapper branch is active. So for an IR step with a `SentimentResult` output, the mock data must be:
```python
# Wrong:
_make_response({"label": "positive", "confidence": 0.9, "reasoning": "..."})
# Correct for return_type=None:
_make_response({"value": {"label": "positive", "confidence": 0.9, "reasoning": "..."}})
```

---

## File-by-File Build Instructions

### `src/stratum/flow_scope.py` (new)

**Path:** `/Users/ruze/reg/my/stratum/src/stratum/flow_scope.py`

```python
"""Public FlowScope — async context manager for establishing flow execution context."""
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
    flow_id, budget, and session cache.

        async with FlowScope(budget=Budget(ms=5000)) as flow_id:
            result = await execute_infer(spec, inputs, flow_budget=budget, flow_id=flow_id)
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

**Edit `src/stratum/__init__.py`:**
- Add `from .flow_scope import FlowScope` after the `from .concurrency import` line (after line 40)
- Add `"FlowScope"` to `__all__` (in the Configuration section, after `"run"`)

**Test:** `tests/test_flow_scope.py`
```python
@pytest.mark.asyncio
async def test_flow_scope_sets_flow_id():
    from stratum.decorators import _flow_ctx
    ctx_inside = None
    async with FlowScope() as flow_id:
        ctx_inside = _flow_ctx.get()
    assert ctx_inside is not None
    assert ctx_inside.flow_id == flow_id
    assert _flow_ctx.get() is None  # reset after exit

@pytest.mark.asyncio
async def test_flow_scope_exception_safe():
    from stratum.decorators import _flow_ctx
    with pytest.raises(RuntimeError):
        async with FlowScope():
            raise RuntimeError("boom")
    assert _flow_ctx.get() is None  # must be reset even after exception

@pytest.mark.asyncio
async def test_flow_scope_with_budget_clones():
    b = Budget(ms=5000, usd=0.01)
    async with FlowScope(budget=b) as _:
        from stratum.decorators import _flow_ctx
        ctx = _flow_ctx.get()
        assert ctx.budget is not b  # cloned, not same object
        assert ctx.budget.ms == 5000
```

---

### `stratum-mcp/pyproject.toml` (new)

**Path:** `/Users/ruze/reg/my/stratum/stratum-mcp/pyproject.toml`

```toml
[project]
name = "stratum-mcp"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "stratum",
    "mcp>=1.0",
    "jsonschema>=4.20",
    "pyyaml>=6.0",
]

[project.scripts]
stratum-mcp = "stratum_mcp.server:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

For development (monorepo), `stratum` is installed as an editable path dep:
```
pip install -e ../src  # or use pyproject with path dep
```

---

### `stratum-mcp/src/stratum_mcp/__init__.py` (new)

Empty. Package marker only.

---

### `stratum-mcp/src/stratum_mcp/errors.py` (new)

**Path:** `/Users/ruze/reg/my/stratum/stratum-mcp/src/stratum_mcp/errors.py`

Three IR error types + MCP error translation. No library imports in the error types themselves.

```python
"""IR error types and MCP error translation."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


# ---------------------------------------------------------------------------
# IR error types
# ---------------------------------------------------------------------------

@dataclass
class IRParseError(Exception):
    """YAML could not be parsed."""
    raw_error: str


@dataclass
class IRValidationError(Exception):
    """Structured schema validation failure."""
    path: str           # dot-notation JSON path, e.g. "flows.process_feedback.steps"
    message: str
    suggestion: str


class IRSemanticError(Exception):
    """Schema-valid but semantically invalid (undefined refs, missing contracts)."""
    def __init__(self, message: str, path: str = "") -> None:
        self.path = path
        super().__init__(message)


class MCPExecutionError(Exception):
    """Runtime error during DAG execution (not a library error)."""


# ---------------------------------------------------------------------------
# MCP error translation
# ---------------------------------------------------------------------------

def exception_to_mcp_error(exc: Exception) -> dict[str, Any]:
    """
    Single translation point. Maps any exception to a structured MCP response dict.
    Never raises. Never exposes internal stack traces.
    """
    from stratum.exceptions import (
        StratumError, BudgetExceeded, PostconditionFailed,
        ParseFailure, PreconditionFailed,
    )

    if isinstance(exc, IRParseError):
        return {
            "success": False,
            "error_type": "ir_parse_error",
            "message": f"YAML syntax error: {exc.raw_error}",
            "suggestion": "Check YAML syntax — indentation, colons, quoting.",
        }
    if isinstance(exc, IRValidationError):
        return {
            "success": False,
            "error_type": "ir_validation_error",
            "path": exc.path,
            "message": exc.message,
            "suggestion": exc.suggestion,
        }
    if isinstance(exc, IRSemanticError):
        return {
            "success": False,
            "error_type": "ir_semantic_error",
            "path": exc.path,
            "message": str(exc),
        }
    if isinstance(exc, BudgetExceeded):
        return {
            "success": False,
            "error_type": "budget_exceeded",
            "message": str(exc),
        }
    if isinstance(exc, PostconditionFailed):
        return {
            "success": False,
            "error_type": "postcondition_failed",
            "function": exc.function_name,
            "violations": exc.violations,
        }
    if isinstance(exc, ParseFailure):
        return {
            "success": False,
            "error_type": "parse_failure",
            "function": exc.function_name,
            "message": exc.error_message,
        }
    if isinstance(exc, PreconditionFailed):
        return {
            "success": False,
            "error_type": "precondition_failed",
            "function": exc.function_name,
            "condition": exc.condition,
        }
    if isinstance(exc, StratumError):
        return {"success": False, "error_type": "stratum_error", "message": str(exc)}
    return {
        "success": False,
        "error_type": "internal_error",
        "message": "An unexpected error occurred.",
    }
```

**Test:** `tests/contracts/test_errors.py`
```python
def test_ir_parse_error_maps_correctly():
    from stratum_mcp.errors import IRParseError, exception_to_mcp_error
    err = exception_to_mcp_error(IRParseError(raw_error="bad indent"))
    assert err["error_type"] == "ir_parse_error"
    assert "bad indent" in err["message"]

def test_ir_validation_error_maps_correctly():
    ...

def test_unknown_exception_maps_to_internal_error():
    from stratum_mcp.errors import exception_to_mcp_error
    err = exception_to_mcp_error(ValueError("boom"))
    assert err["error_type"] == "internal_error"
    assert "boom" not in err["message"]  # must not leak internals
```

---

### `stratum-mcp/src/stratum_mcp/spec.py` (new)

**Path:** `/Users/ruze/reg/my/stratum/stratum-mcp/src/stratum_mcp/spec.py`

IR dataclasses, schema registry, parser, and semantic validator in one file.

```python
"""IR types, JSON Schema registry, parser, and validator for .stratum.yaml v0.1."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

import yaml
from jsonschema import Draft202012Validator
from jsonschema.exceptions import best_match

from .errors import IRParseError, IRValidationError, IRSemanticError


# ---------------------------------------------------------------------------
# IR dataclasses (frozen)
# ---------------------------------------------------------------------------

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
    ensure: list[str]
    budget: IRBudgetDef | None
    retries: int
    model: str | None


@dataclass(frozen=True)
class IRStepDef:
    id: str
    function: str
    inputs: dict[str, str]
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


# ---------------------------------------------------------------------------
# JSON Schema registry
# ---------------------------------------------------------------------------

_IR_SCHEMA_V01: dict = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "required": ["version"],
    "additionalProperties": False,
    "properties": {
        "version": {"type": "string", "const": "0.1"},
        "contracts": {
            "type": "object",
            "additionalProperties": {
                "type": "object",
                "additionalProperties": {
                    "type": "object",
                    "properties": {
                        "type": {"type": "string"},
                        "values": {"type": "array"},
                    },
                    "required": ["type"],
                }
            }
        },
        "functions": {
            "type": "object",
            "additionalProperties": {"$ref": "#/$defs/FunctionDef"}
        },
        "flows": {
            "type": "object",
            "additionalProperties": {"$ref": "#/$defs/FlowDef"}
        }
    },
    "$defs": {
        "BudgetDef": {
            "type": "object",
            "properties": {
                "ms": {"type": "integer", "minimum": 1},
                "usd": {"type": "number", "minimum": 0},
            },
            "additionalProperties": False,
        },
        "FunctionDef": {
            "type": "object",
            "required": ["mode", "intent", "input", "output"],
            "additionalProperties": False,
            "properties": {
                "mode": {"type": "string", "enum": ["infer", "compute"]},
                "intent": {"type": "string", "minLength": 1},
                "input": {"type": "object"},
                "output": {"type": "string"},
                "ensure": {"type": "array", "items": {"type": "string"}},
                "budget": {"$ref": "#/$defs/BudgetDef"},
                "retries": {"type": "integer", "minimum": 0},
                "model": {"type": "string"},
            }
        },
        "StepDef": {
            "type": "object",
            "required": ["id", "function", "inputs"],
            "additionalProperties": False,
            "properties": {
                "id": {"type": "string"},
                "function": {"type": "string"},
                "inputs": {"type": "object", "additionalProperties": {"type": "string"}},
                "depends_on": {"type": "array", "items": {"type": "string"}},
            }
        },
        "FlowDef": {
            "type": "object",
            "required": ["input", "output", "steps"],
            "additionalProperties": False,
            "properties": {
                "input": {"type": "object"},
                "output": {"type": "string"},
                "budget": {"$ref": "#/$defs/BudgetDef"},
                "steps": {"type": "array", "items": {"$ref": "#/$defs/StepDef"}, "minItems": 1}
            }
        }
    }
}

# Version registry — add "0.2": _IR_SCHEMA_V02 when v0.2 lands
SCHEMAS: dict[str, dict] = {"0.1": _IR_SCHEMA_V01}


# ---------------------------------------------------------------------------
# Public parse entry point
# ---------------------------------------------------------------------------

def parse_and_validate(raw_yaml: str) -> IRSpec:
    """
    Parse raw YAML → JSON Schema validation → semantic validation → IRSpec.
    Raises IRParseError, IRValidationError, or IRSemanticError.
    """
    doc = _parse_yaml(raw_yaml)
    version = str(doc.get("version", ""))
    schema = SCHEMAS.get(version)
    if schema is None:
        raise IRValidationError(
            path="version",
            message=f"Unknown IR version: {version!r}",
            suggestion=f"Use version: \"{list(SCHEMAS.keys())[-1]}\"",
        )
    _validate_schema(doc, schema)
    spec = _build_spec(doc)
    _validate_semantics(spec)
    return spec


def _parse_yaml(raw: str) -> dict[str, Any]:
    try:
        return yaml.safe_load(raw) or {}
    except yaml.YAMLError as exc:
        raise IRParseError(raw_error=str(exc)) from exc


def _validate_schema(doc: dict, schema: dict) -> None:
    validator = Draft202012Validator(schema)
    errors = list(validator.iter_errors(doc))
    if not errors:
        return
    worst = best_match(errors)
    path = ".".join(str(p) for p in worst.path) if worst.path else "root"
    suggestion = _suggest_fix(worst)
    raise IRValidationError(path=path, message=worst.message, suggestion=suggestion)


def _build_spec(doc: dict) -> IRSpec:
    contracts = {
        name: IRContractDef(name=name, fields=fields)
        for name, fields in (doc.get("contracts") or {}).items()
    }
    functions = {
        name: _build_function(name, d)
        for name, d in (doc.get("functions") or {}).items()
    }
    flows = {
        name: _build_flow(name, d)
        for name, d in (doc.get("flows") or {}).items()
    }
    return IRSpec(version=doc["version"], contracts=contracts, functions=functions, flows=flows)


def _build_function(name: str, d: dict) -> IRFunctionDef:
    b = d.get("budget")
    budget = IRBudgetDef(ms=b.get("ms"), usd=b.get("usd")) if b else None
    return IRFunctionDef(
        name=name,
        mode=d["mode"],
        intent=d["intent"],
        input_schema=d.get("input", {}),
        output_contract=d["output"],
        ensure=d.get("ensure", []),
        budget=budget,
        retries=d.get("retries", 3),
        model=d.get("model"),
    )


def _build_flow(name: str, d: dict) -> IRFlowDef:
    b = d.get("budget")
    budget = IRBudgetDef(ms=b.get("ms"), usd=b.get("usd")) if b else None
    steps = [
        IRStepDef(
            id=s["id"],
            function=s["function"],
            inputs=s.get("inputs", {}),
            depends_on=s.get("depends_on", []),
        )
        for s in d.get("steps", [])
    ]
    return IRFlowDef(
        name=name,
        input_schema=d.get("input", {}),
        output_contract=d["output"],
        budget=budget,
        steps=steps,
    )


def _validate_semantics(spec: IRSpec) -> None:
    known_contracts = set(spec.contracts)
    known_functions = set(spec.functions)
    for fn_name, fn in spec.functions.items():
        if fn.output_contract not in known_contracts:
            raise IRSemanticError(
                f"Function '{fn_name}' output contract '{fn.output_contract}' not defined",
                path=f"functions.{fn_name}.output"
            )
    for flow_name, flow in spec.flows.items():
        if flow.output_contract not in known_contracts:
            raise IRSemanticError(
                f"Flow '{flow_name}' output contract '{flow.output_contract}' not defined",
                path=f"flows.{flow_name}.output"
            )
        known_step_ids: set[str] = set()
        for step in flow.steps:
            if step.function not in known_functions:
                raise IRSemanticError(
                    f"Step '{step.id}' references undefined function '{step.function}'",
                    path=f"flows.{flow_name}.steps.{step.id}.function"
                )
            for dep in step.depends_on:
                if dep not in known_step_ids:
                    raise IRSemanticError(
                        f"Step '{step.id}' depends_on unknown step '{dep}'",
                        path=f"flows.{flow_name}.steps.{step.id}.depends_on"
                    )
            known_step_ids.add(step.id)


def _suggest_fix(error: Any) -> str:
    if error.validator == "enum":
        return f"Allowed values: {error.validator_value}"
    if error.validator == "required":
        return f"Add required field(s): {error.validator_value}"
    if error.validator == "additionalProperties":
        return "Remove unrecognised fields"
    if error.validator == "const":
        return f"Expected: {error.validator_value!r}"
    return "See IR schema documentation"
```

**Test:** `tests/contracts/test_ir_schema.py`
```python
VALID_IR = """
version: "0.1"
contracts:
  SentimentResult:
    label: {type: string}
    confidence: {type: number}
functions:
  classify:
    mode: infer
    intent: "Classify sentiment"
    input: {text: {type: string}}
    output: SentimentResult
flows:
  run:
    input: {text: {type: string}}
    output: SentimentResult
    steps:
      - id: s1
        function: classify
        inputs: {text: "$.input.text"}
"""

def test_valid_ir_parses():
    spec = parse_and_validate(VALID_IR)
    assert spec.version == "0.1"
    assert "classify" in spec.functions
    assert "run" in spec.flows

def test_invalid_yaml_raises_parse_error():
    with pytest.raises(IRParseError):
        parse_and_validate("version: [\n  bad")

def test_wrong_version_raises_validation_error():
    with pytest.raises(IRValidationError) as exc_info:
        parse_and_validate("version: \"99.0\"\n")
    assert exc_info.value.path == "version"

def test_undefined_function_reference_raises_semantic_error():
    ir = VALID_IR.replace("classify", "nonexistent_fn")
    with pytest.raises(IRSemanticError):
        parse_and_validate(ir)

def test_missing_required_field_raises_validation_error():
    with pytest.raises(IRValidationError) as exc_info:
        parse_and_validate("version: \"0.1\"\nfunctions:\n  f:\n    mode: infer\n    input: {}\n    output: X\n")
    assert "intent" in exc_info.value.suggestion.lower() or "intent" in exc_info.value.message.lower()
```

---

### `stratum-mcp/src/stratum_mcp/executor.py` (new)

**Path:** `/Users/ruze/reg/my/stratum/stratum-mcp/src/stratum_mcp/executor.py`

DAG execution, ref resolution, ensure compilation. Includes G9 fix (SimpleNamespace wrap).

```python
"""DAG execution loop, $ reference resolution, and ensure expression compilation."""
from __future__ import annotations

import time
import types
from typing import Any, Callable

from stratum import FlowScope
from stratum.budget import Budget
from stratum.executor import InferSpec, execute_infer

from .errors import IRSemanticError, MCPExecutionError
from .spec import IRFlowDef, IRFunctionDef, IRSpec, IRStepDef


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

from dataclasses import dataclass


@dataclass
class StepResult:
    step_id: str
    function_name: str
    output: Any
    duration_ms: int
    cost_usd: float | None
    attempts: int


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

    @property
    def trace_records(self) -> list[dict]:
        return [
            {
                "step_id": s.step_id,
                "function": s.function_name,
                "duration_ms": s.duration_ms,
                "cost_usd": s.cost_usd,
                "attempts": s.attempts,
            }
            for s in self.steps
        ]


# ---------------------------------------------------------------------------
# ensure expression compilation (G9 fix included)
# ---------------------------------------------------------------------------

class EnsureCompileError(Exception):
    pass


def compile_ensure(expr: str) -> Callable[[Any], bool]:
    """
    Compile 'result.field > value' string into a callable.

    G9 fix: if the result is a dict, it is wrapped in SimpleNamespace
    so that attribute-style access (result.confidence) works on dict outputs.
    This is necessary because execute_infer with return_type=None returns
    a plain dict after unwrapping the primitive-wrapper branch.

    Safety: __builtins__ is empty. Only `result` is in scope.
    """
    try:
        code = compile(expr, "<ensure_expr>", "eval")
    except SyntaxError as exc:
        raise EnsureCompileError(f"Cannot compile ensure expression {expr!r}: {exc}") from exc

    def evaluator(result: Any) -> bool:
        if isinstance(result, dict):
            result = types.SimpleNamespace(**result)
        try:
            return bool(eval(code, {"__builtins__": {}}, {"result": result}))
        except Exception as exc:
            raise EnsureCompileError(
                f"Ensure expression {expr!r} raised: {exc}"
            ) from exc

    evaluator.__name__ = f"ensure({expr})"
    return evaluator


def compile_ensure_list(exprs: list[str]) -> list[Callable[[Any], bool]]:
    return [compile_ensure(e) for e in exprs]


# ---------------------------------------------------------------------------
# $ reference resolution
# ---------------------------------------------------------------------------

class RefResolutionError(Exception):
    pass


def resolve_ref(ref: str, flow_inputs: dict[str, Any], step_outputs: dict[str, Any]) -> Any:
    """
    Resolve a $ reference or return literal value.

    Supported:
      $.input.<field>                 → flow_inputs[field]
      $.steps.<step_id>.output        → step_outputs[step_id]
      $.steps.<step_id>.output.<f>    → step_outputs[step_id][field]
      <literal>                       → returned as-is
    """
    if not ref.startswith("$"):
        return ref
    parts = ref.lstrip("$.").split(".")
    if not parts:
        raise RefResolutionError(f"Empty $ reference: {ref!r}")
    if parts[0] == "input":
        if len(parts) < 2:
            raise RefResolutionError(f"$.input requires a field name: {ref!r}")
        field = parts[1]
        if field not in flow_inputs:
            raise RefResolutionError(f"$.input.{field} not found in flow inputs")
        return flow_inputs[field]
    if parts[0] == "steps":
        if len(parts) < 3:
            raise RefResolutionError(f"$.steps requires $.steps.<id>.output: {ref!r}")
        step_id = parts[1]
        if step_id not in step_outputs:
            raise RefResolutionError(
                f"$.steps.{step_id} not yet executed — check depends_on ordering"
            )
        output = step_outputs[step_id]
        for key in parts[3:]:  # parts[2] is "output", parts[3:] are field names
            if isinstance(output, dict):
                output = output[key]
            else:
                output = getattr(output, key)
        return output
    raise RefResolutionError(f"Unknown $ prefix '{parts[0]}' in {ref!r}")


def resolve_inputs(
    input_refs: dict[str, str],
    flow_inputs: dict[str, Any],
    step_outputs: dict[str, Any],
) -> dict[str, Any]:
    return {
        param: resolve_ref(ref, flow_inputs, step_outputs)
        for param, ref in input_refs.items()
    }


# ---------------------------------------------------------------------------
# DAG execution
# ---------------------------------------------------------------------------

async def execute_flow(spec: IRSpec, flow_name: str, inputs: dict[str, Any]) -> FlowResult:
    """Execute a named flow from a validated IRSpec."""
    flow_def = spec.flows.get(flow_name)
    if flow_def is None:
        raise MCPExecutionError(f"Flow '{flow_name}' not found in spec")

    flow_budget = _build_budget(flow_def)
    ordered_steps = _topological_sort(flow_def)

    step_outputs: dict[str, Any] = {}
    step_results: list[StepResult] = []
    total_cost = 0.0
    flow_start = time.monotonic()

    async with FlowScope(budget=flow_budget) as flow_id:
        for step in ordered_steps:
            fn_def = spec.functions[step.function]
            infer_spec = _build_infer_spec(fn_def, flow_budget)

            try:
                resolved_inputs = resolve_inputs(step.inputs, inputs, step_outputs)
            except RefResolutionError as exc:
                raise MCPExecutionError(str(exc)) from exc

            step_start = time.monotonic()
            step_budget = _build_step_budget(fn_def, flow_budget)

            # execute_infer with return_type=None returns the unwrapped "value" key
            # — a dict if the LLM sent {"value": {...}}
            output = await execute_infer(
                infer_spec,
                resolved_inputs,
                flow_budget=step_budget,
                flow_id=flow_id,
            )

            step_duration_ms = int((time.monotonic() - step_start) * 1000)
            step_cost = _extract_step_cost(flow_id, fn_def.name)
            total_cost += step_cost or 0.0

            step_outputs[step.id] = output
            step_results.append(StepResult(
                step_id=step.id,
                function_name=fn_def.name,
                output=output,
                duration_ms=step_duration_ms,
                cost_usd=step_cost,
                attempts=_extract_step_attempts(flow_id, fn_def.name),
            ))

    total_duration_ms = int((time.monotonic() - flow_start) * 1000)
    return FlowResult(
        flow_name=flow_name,
        flow_id=flow_id,
        output=step_outputs.get(ordered_steps[-1].id),
        steps=step_results,
        total_cost_usd=total_cost,
        total_duration_ms=total_duration_ms,
        success=True,
    )


def _build_infer_spec(fn_def: IRFunctionDef, flow_budget: Budget | None) -> InferSpec:
    """Build an InferSpec from an IRFunctionDef. return_type=None → plain dict output."""
    def _ir_sentinel() -> None: ...
    _ir_sentinel.__name__ = fn_def.name
    _ir_sentinel.__qualname__ = f"ir::{fn_def.name}"

    _type_map = {"string": str, "number": float, "integer": int, "boolean": bool}
    parameters = {
        name: _type_map.get(spec.get("type", ""), Any)
        for name, spec in fn_def.input_schema.items()
    }

    budget = None
    if fn_def.budget:
        budget = Budget(ms=fn_def.budget.ms, usd=fn_def.budget.usd)

    return InferSpec(
        fn=_ir_sentinel,
        intent=fn_def.intent,
        context=[],
        ensure=compile_ensure_list(fn_def.ensure),
        given=[],
        model=fn_def.model,
        temperature=None,
        budget=budget,
        retries=fn_def.retries,
        cache="none",
        stable=True,
        quorum=None,
        agree_on=None,
        threshold=None,
        return_type=None,   # IR contract outputs → plain dict after primitive-wrapper unwrap
        parameters=parameters,
    )


def _topological_sort(flow_def: IRFlowDef) -> list[IRStepDef]:
    """Kahn's algorithm on explicit depends_on + implicit $ ref dependencies."""
    steps_by_id = {s.id: s for s in flow_def.steps}
    dep_graph: dict[str, set[str]] = {s.id: set(s.depends_on) for s in flow_def.steps}
    for step in flow_def.steps:
        for ref in step.inputs.values():
            if ref.startswith("$.steps."):
                parts = ref.split(".")
                if len(parts) >= 3:
                    dep_graph[step.id].add(parts[2])

    in_degree = {sid: len(deps) for sid, deps in dep_graph.items()}
    ready = [sid for sid, deg in in_degree.items() if deg == 0]
    ordered: list[IRStepDef] = []

    while ready:
        sid = ready.pop(0)
        ordered.append(steps_by_id[sid])
        for other_id, deps in dep_graph.items():
            if sid in deps:
                in_degree[other_id] -= 1
                if in_degree[other_id] == 0:
                    ready.append(other_id)

    if len(ordered) != len(flow_def.steps):
        remaining = [s for s in dep_graph if s not in {o.id for o in ordered}]
        raise MCPExecutionError(f"Cycle detected in step dependencies: {remaining}")
    return ordered


def _build_budget(flow_def: IRFlowDef) -> Budget | None:
    if flow_def.budget is None:
        return None
    return Budget(ms=flow_def.budget.ms, usd=flow_def.budget.usd)


def _build_step_budget(fn_def: IRFunctionDef, flow_budget: Budget | None) -> Budget | None:
    if fn_def.budget:
        return Budget(ms=fn_def.budget.ms, usd=fn_def.budget.usd)
    return flow_budget


def _extract_step_cost(flow_id: str, fn_name: str) -> float | None:
    from stratum.trace import all_records
    records = [r for r in all_records() if r.flow_id == flow_id and r.function.endswith(fn_name)]
    return records[-1].cost_usd if records else None


def _extract_step_attempts(flow_id: str, fn_name: str) -> int:
    from stratum.trace import all_records
    records = [r for r in all_records() if r.flow_id == flow_id and r.function.endswith(fn_name)]
    return records[-1].attempts if records else 1
```

**Test:** `tests/invariants/test_executor.py`
```python
def test_compile_ensure_attribute_style_on_dict():
    """G9 fix: ensure exprs work on dict outputs via SimpleNamespace wrap."""
    from stratum_mcp.executor import compile_ensure
    fn = compile_ensure("result.confidence > 0.7")
    assert fn({"confidence": 0.9}) is True
    assert fn({"confidence": 0.5}) is False

def test_compile_ensure_restricted_builtins():
    from stratum_mcp.executor import compile_ensure, EnsureCompileError
    fn = compile_ensure("__import__('os')")
    with pytest.raises(EnsureCompileError):
        fn({})

def test_resolve_ref_input():
    from stratum_mcp.executor import resolve_ref
    assert resolve_ref("$.input.text", {"text": "hello"}, {}) == "hello"

def test_resolve_ref_step_output():
    from stratum_mcp.executor import resolve_ref
    assert resolve_ref("$.steps.s1.output", {}, {"s1": {"label": "positive"}}) == {"label": "positive"}

def test_resolve_ref_literal():
    from stratum_mcp.executor import resolve_ref
    assert resolve_ref("some literal", {}, {}) == "some literal"

def test_topological_sort_linear():
    # 3-step linear flow: s1 → s2 → s3
    ...

def test_topological_sort_cycle_raises():
    # s1 depends_on s2, s2 depends_on s1
    ...
```

**Integration test** (`tests/integration/test_roundtrip.py`) — uses the same `_make_response` pattern from `tests/test_executor.py` but wraps in `{"value": {...}}` for `return_type=None`:
```python
_make_response({"value": {"label": "positive", "confidence": 0.9, "reasoning": "good"}})
```

---

### `stratum-mcp/src/stratum_mcp/auditor.py` (new)

```python
"""stratum_audit — stub for v0.1."""
from __future__ import annotations
from typing import Any


async def audit(path: str) -> dict[str, Any]:
    return {"message": "audit not yet implemented", "path": path}
```

---

### `stratum-mcp/src/stratum_mcp/server.py` (new)

**Path:** `/Users/ruze/reg/my/stratum/stratum-mcp/src/stratum_mcp/server.py`

```python
"""FastMCP server entry point. Tool registration + CLI dual-mode."""
from __future__ import annotations

import sys
from typing import Any

from mcp.server.fastmcp import FastMCP, Context

from .auditor import audit
from .errors import IRParseError, IRValidationError, IRSemanticError, exception_to_mcp_error
from .executor import execute_flow, FlowResult
from .spec import parse_and_validate

mcp = FastMCP(
    "stratum-mcp",
    description=(
        "Stratum execution runtime for Claude Code. "
        "Validates, plans, and executes .stratum.yaml IR specs."
    ),
)


@mcp.tool(description=(
    "Validate a .stratum.yaml IR spec. "
    "Input: spec (str) — inline YAML only, not a file path. "
    "Returns {valid: bool, errors: list}."
))
async def stratum_validate(spec: str, ctx: Context) -> dict[str, Any]:
    try:
        parse_and_validate(spec)
        return {"valid": True, "errors": []}
    except (IRParseError, IRValidationError, IRSemanticError) as exc:
        return {"valid": False, "errors": [exception_to_mcp_error(exc)]}


@mcp.tool(description=(
    "Plan a multi-step task as a Stratum IR spec. "
    "Validates the spec before execution. Call this BEFORE stratum_execute. "
    "Input: plan (str) — inline YAML."
))
async def stratum_plan(plan: str, ctx: Context) -> dict[str, Any]:
    return await stratum_validate(plan, ctx)


@mcp.tool(description=(
    "Execute a validated Stratum IR flow. "
    "Inputs: spec (str, inline YAML), flow (str, flow name), inputs (dict). "
    "Returns {success, output, trace_records, cost_usd, duration_ms, flow_id}."
))
async def stratum_execute(
    spec: str,
    flow: str,
    inputs: dict[str, Any],
    ctx: Context,
) -> dict[str, Any]:
    try:
        ir_spec = parse_and_validate(spec)
    except (IRParseError, IRValidationError, IRSemanticError) as exc:
        return exception_to_mcp_error(exc)
    try:
        result = await execute_flow(ir_spec, flow, inputs)
    except Exception as exc:
        return exception_to_mcp_error(exc)
    return {
        "success": True,
        "output": result.output,
        "trace_records": result.trace_records,
        "cost_usd": result.total_cost_usd,
        "duration_ms": result.total_duration_ms,
        "flow_id": result.flow_id,
    }


@mcp.tool(description="Audit Stratum trace records. Stub — not yet implemented.")
async def stratum_audit(path: str, ctx: Context) -> dict[str, Any]:
    return await audit(path)


def main() -> None:
    """Entry point: CLI mode if called with 'validate'; stdio server otherwise."""
    import asyncio

    if len(sys.argv) >= 2 and sys.argv[1] == "validate":
        arg = sys.argv[2] if len(sys.argv) > 2 else ""
        yaml_content = arg
        if arg and "\n" not in arg and not arg.lstrip().startswith("version:"):
            try:
                with open(arg) as f:
                    yaml_content = f.read()
            except OSError:
                pass  # treat as inline YAML
        try:
            parse_and_validate(yaml_content)
            print("OK")
            sys.exit(0)
        except Exception as exc:
            err = exception_to_mcp_error(exc)
            print(f"ERROR [{err['error_type']}]: {err['message']}", file=sys.stderr)
            sys.exit(1)

    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
```

---

## What NOT to Do

- Do not import `_flow_ctx` or `_FlowContext` anywhere in `stratum_mcp` — only `FlowScope` (public)
- Do not call `begin_flow()` or `end_flow()` — they do not exist
- Do not pass `{"label": "x"}` as the mock response data when `return_type=None` — must wrap as `{"value": {"label": "x"}}`
- Do not try to do Pydantic instantiation of IR contract outputs — `return_type=None` returns plain dict
- Do not catch bare `Exception` in error translation and expose the message — unknown errors must return generic "internal_error" message

---

## Verification Table

| File:line claim | Verified | Status |
|---|---|---|
| `execute_infer(spec, inputs, flow_budget=None, flow_id=None)` | executor.py:125–130 | ✓ |
| `InferSpec` has 16 fields incl. `parameters` | executor.py:38–57 | ✓ |
| `return_type=None` → primitive wrapper → `{"value": X}` unwrap | executor.py:108–118, 175–185, 367–370 | ✓ |
| `_FlowContext` has `flow_id`, `budget`, `session_cache` | decorators.py:22–26 | ✓ |
| `_flow_ctx.set(ctx)` / `_flow_ctx.reset(token)` pattern | decorators.py:286–290 | ✓ |
| `Budget.clone()` returns fresh Budget with same limits | budget.py:56–61 | ✓ |
| `FlowScope` not in `__init__.py` | __init__.py:70–117 | ✓ (must add) |
| `from mcp.server.fastmcp import FastMCP, Context` | mcp SDK docs | ✓ |
| `from jsonschema import Draft202012Validator` | jsonschema docs | ✓ |
| `from jsonschema.exceptions import best_match` | jsonschema docs | ✓ |
| `best.path` is a deque, convert with `".".join(str(p) for p in best.path)` | jsonschema docs | ✓ |
