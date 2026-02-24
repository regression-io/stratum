"""Flow controller: plan state management, $ reference resolution, ensure compilation."""
from __future__ import annotations

import os
import time
import types
import uuid
import dataclasses
from dataclasses import dataclass, field
from typing import Any, Callable

from jsonschema import Draft202012Validator

from .errors import MCPExecutionError
from .spec import IRSpec, IRFlowDef, IRStepDef


# ---------------------------------------------------------------------------
# ensure expression compilation
# ---------------------------------------------------------------------------

class EnsureCompileError(Exception):
    pass


# Safe builtins available in all ensure expressions.
# __builtins__ is always empty — only these specific names are exposed.

_FILE_CONTAINS_SIZE_LIMIT = 10 * 1024 * 1024  # 10 MB


def _file_contains(path: str, substring: str) -> bool:
    """Return True if path exists, is under the size limit, and contains substring."""
    try:
        if not os.path.isfile(path):
            return False
        if os.path.getsize(path) > _FILE_CONTAINS_SIZE_LIMIT:
            return False
        with open(path, encoding="utf-8", errors="replace") as f:
            return substring in f.read()
    except OSError:
        return False


_ENSURE_BUILTINS: dict[str, Any] = {
    "file_exists": lambda p: os.path.isfile(p),
    "file_contains": _file_contains,
    "len": len,
    "bool": bool,
    "int": int,
    "str": str,
}


def compile_ensure(expr: str) -> Callable[[Any], bool]:
    """
    Compile 'result.field > value' string into a callable.

    If the result is a dict, it is wrapped in SimpleNamespace so that
    attribute-style access (result.confidence) works on dict outputs.

    Safety: __builtins__ is empty. Dunder attributes are blocked at compile time.
    """
    if "__" in expr:
        raise EnsureCompileError(
            f"Ensure expression may not contain dunder attributes: {expr!r}"
        )
    try:
        code = compile(expr, "<ensure_expr>", "eval")
    except SyntaxError as exc:
        raise EnsureCompileError(f"Cannot compile ensure expression {expr!r}: {exc}") from exc

    def evaluator(result: Any) -> bool:
        if isinstance(result, dict):
            result = types.SimpleNamespace(**result)
        try:
            return bool(eval(code, {"__builtins__": {}, **_ENSURE_BUILTINS}, {"result": result}))
        except Exception as exc:
            raise EnsureCompileError(
                f"Ensure expression {expr!r} raised: {exc}"
            ) from exc

    evaluator.__name__ = f"ensure({expr})"
    return evaluator


def compile_ensure_list(exprs: list[str]) -> list[Callable[[Any], bool]]:
    return [compile_ensure(e) for e in exprs]


def _validate_output_schema(result: dict[str, Any], schema: dict[str, Any]) -> list[str]:
    """Validate result dict against a JSON Schema. Returns list of violation strings."""
    validator = Draft202012Validator(schema)
    try:
        return [
            f"output_schema violation: {e.message}"
            for e in validator.iter_errors(result)
        ]
    except Exception as exc:
        return [f"output_schema violation: schema error — {exc}"]


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
    # Use ref[2:] to strip the literal "$." prefix, not lstrip which strips a char set.
    parts = ref[2:].split(".")
    if not parts or parts == [""]:
        raise RefResolutionError(f"Empty $ reference: {ref!r}")
    if parts[0] == "input":
        if len(parts) < 2:
            raise RefResolutionError(f"$.input requires a field name: {ref!r}")
        field_name = parts[1]
        if field_name not in flow_inputs:
            raise RefResolutionError(f"$.input.{field_name} not found in flow inputs")
        return flow_inputs[field_name]
    if parts[0] == "steps":
        if len(parts) < 3:
            raise RefResolutionError(f"$.steps requires $.steps.<id>.output: {ref!r}")
        step_id = parts[1]
        if step_id not in step_outputs:
            raise RefResolutionError(
                f"$.steps.{step_id} not yet executed — check depends_on ordering"
            )
        output = step_outputs[step_id]
        if parts[2] != "output":
            raise RefResolutionError(
                f"Expected '$.steps.<id>.output[.<field>]', got {ref!r}"
            )
        for key in parts[3:]:
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
# Topological sort
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Flow controller state
# ---------------------------------------------------------------------------

@dataclass
class StepRecord:
    step_id: str
    function_name: str
    attempts: int
    duration_ms: int


@dataclass
class FlowState:
    flow_id: str
    flow_name: str
    spec: IRSpec
    ordered_steps: list[IRStepDef]
    inputs: dict[str, Any]           # flow-level inputs
    step_outputs: dict[str, Any]     # accumulated: step_id → output
    records: list[StepRecord]        # completed step records
    attempts: dict[str, int]         # current attempt count per step_id
    dispatched_at: dict[str, float]  # when each step was sent to Claude Code
    flow_start: float
    current_idx: int = 0


def create_flow_state(spec: IRSpec, flow_name: str, inputs: dict[str, Any]) -> FlowState:
    """Create flow execution state. Raises MCPExecutionError if flow not found."""
    flow_def = spec.flows.get(flow_name)
    if flow_def is None:
        raise MCPExecutionError(f"Flow '{flow_name}' not found in spec")
    ordered = _topological_sort(flow_def)
    return FlowState(
        flow_id=str(uuid.uuid4()),
        flow_name=flow_name,
        spec=spec,
        ordered_steps=ordered,
        inputs=inputs,
        step_outputs={},
        records=[],
        attempts={},
        dispatched_at={},
        flow_start=time.monotonic(),
        current_idx=0,
    )


def get_current_step_info(state: FlowState) -> dict[str, Any] | None:
    """
    Return the current step as a dict Claude Code can act on, with resolved inputs.
    Records dispatch time for duration tracking. Returns None if the flow is complete.
    """
    if state.current_idx >= len(state.ordered_steps):
        return None

    step = state.ordered_steps[state.current_idx]
    fn_def = state.spec.functions[step.function]

    try:
        resolved = resolve_inputs(step.inputs, state.inputs, state.step_outputs)
    except RefResolutionError as exc:
        raise MCPExecutionError(str(exc)) from exc

    state.dispatched_at[step.id] = time.monotonic()
    attempts_so_far = state.attempts.get(step.id, 0)

    contract = state.spec.contracts.get(fn_def.output_contract)
    output_fields = {k: v.get("type", "any") for k, v in contract.fields.items()} if contract else {}

    return {
        "status": "execute_step",
        "flow_id": state.flow_id,
        "step_number": state.current_idx + 1,
        "total_steps": len(state.ordered_steps),
        "step_id": step.id,
        "function": step.function,
        "mode": fn_def.mode,
        "intent": fn_def.intent,
        "inputs": resolved,
        "output_contract": fn_def.output_contract,
        "output_fields": output_fields,
        "ensure": fn_def.ensure,
        "retries_remaining": fn_def.retries - attempts_so_far,
    }


def process_step_result(
    state: FlowState,
    step_id: str,
    result: dict[str, Any],
) -> tuple[str, list[str]]:
    """
    Record a completed step result and check ensure expressions.

    Returns:
      ("ok", [])                        — ensures passed, current_idx advanced
      ("ensure_failed", [violations])   — ensures failed, retries remain
      ("retries_exhausted", [violations]) — ensures failed, no retries left
    """
    if state.current_idx >= len(state.ordered_steps):
        raise MCPExecutionError("Flow is already complete")

    step = state.ordered_steps[state.current_idx]
    if step.id != step_id:
        raise MCPExecutionError(
            f"Expected step '{step.id}', got '{step_id}'"
        )

    fn_def = state.spec.functions[step.function]
    state.attempts[step_id] = state.attempts.get(step_id, 0) + 1
    attempt = state.attempts[step_id]

    # Schema validation runs before ensures — structural errors are caught first.
    if step.output_schema is not None:
        schema_errors = _validate_output_schema(result, step.output_schema)
        if schema_errors:
            if attempt >= fn_def.retries:
                dispatched = state.dispatched_at.get(step_id, state.flow_start)
                duration_ms = int((time.monotonic() - dispatched) * 1000)
                state.records.append(StepRecord(
                    step_id=step_id,
                    function_name=fn_def.name,
                    attempts=attempt,
                    duration_ms=duration_ms,
                ))
                return ("retries_exhausted", schema_errors)
            return ("schema_failed", schema_errors)

    violations: list[str] = []
    for expr in fn_def.ensure:
        try:
            fn = compile_ensure(expr)
            if not fn(result):
                violations.append(f"ensure '{expr}' failed")
        except EnsureCompileError as exc:
            violations.append(str(exc))

    dispatched = state.dispatched_at.get(step_id, state.flow_start)
    duration_ms = int((time.monotonic() - dispatched) * 1000)

    if violations:
        if attempt >= fn_def.retries:
            state.records.append(StepRecord(
                step_id=step_id,
                function_name=fn_def.name,
                attempts=attempt,
                duration_ms=duration_ms,
            ))
            return ("retries_exhausted", violations)
        return ("ensure_failed", violations)

    state.step_outputs[step_id] = result
    state.records.append(StepRecord(
        step_id=step_id,
        function_name=fn_def.name,
        attempts=attempt,
        duration_ms=duration_ms,
    ))
    state.current_idx += 1
    return ("ok", [])
