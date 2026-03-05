"""Flow controller: plan state management, $ reference resolution, ensure compilation."""
from __future__ import annotations

import copy
import json
import os
import re
import time
import types
import uuid
import dataclasses
from dataclasses import dataclass, field
from pathlib import Path
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

    Skipped steps have output=None. Any field access on a None output propagates None
    rather than raising, matching the "skipped output resolves to null" contract.
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
        # None propagation: skipped steps have output=None; any field access returns None.
        if output is None:
            return None
        for key in parts[3:]:
            if output is None:
                return None
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
# skip_if evaluation
# ---------------------------------------------------------------------------

def evaluate_skip_if(
    expr: str,
    flow_inputs: dict[str, Any],
    step_outputs: dict[str, Any],
) -> bool:
    """
    Evaluate a skip_if expression against current flow state.

    $ references ($.steps.X.output.field, $.input.field) are resolved first;
    unresolvable or null references evaluate to None rather than raising.
    The substituted expression is then evaluated as a Python boolean.

    Returns False on any compilation or evaluation error (conservative: don't skip).
    """
    if "__" in expr:
        return False  # dunder guard

    def replace_ref(m: re.Match) -> str:
        ref_str = m.group(0)
        try:
            value = resolve_ref(ref_str, flow_inputs, step_outputs)
            return repr(value)
        except (RefResolutionError, Exception):
            return repr(None)

    # Replace all $.xxx.yyy references with their Python repr
    processed = re.sub(r'\$\.[A-Za-z0-9_.]+', replace_ref, expr)

    try:
        code = compile(processed, "<skip_if>", "eval")
        return bool(eval(code, {"__builtins__": {}, "None": None, "True": True, "False": False,
                                "true": True, "false": False, "null": None}))
    except Exception:
        return False


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
    # "type" field matches the documented trace contract ("step" | "gate" | "skip")
    type: str = "step"  # noqa: A003 — shadows builtin intentionally for API contract
    round: int = 0
    round_start_step_id: str | None = None


@dataclass
class GateRecord:
    """Trace entry written when a gate step is resolved via stratum_gate_resolve."""
    step_id: str
    outcome: str          # "approve" | "revise" | "kill"
    rationale: str
    resolved_by: str      # "human" | "agent" | "system"
    duration_ms: int
    type: str = "gate"    # noqa: A003
    round: int = 0
    round_start_step_id: str | None = None


@dataclass
class SkipRecord:
    """Trace entry written when a step is skipped due to skip_if evaluating to True."""
    step_id: str
    skip_reason: str
    type: str = "skip"    # noqa: A003
    round: int = 0
    round_start_step_id: str | None = None


def _record_from_dict(r: dict) -> StepRecord | GateRecord | SkipRecord:
    """Reconstruct a StepRecord, GateRecord, or SkipRecord from a persisted dict."""
    rec_type = r.get("type", "step")
    if rec_type == "gate":
        return GateRecord(
            step_id=r["step_id"],
            outcome=r["outcome"],
            rationale=r["rationale"],
            resolved_by=r["resolved_by"],
            duration_ms=r["duration_ms"],
            round=r.get("round", 0),
            round_start_step_id=r.get("round_start_step_id"),
        )
    if rec_type == "skip":
        return SkipRecord(
            step_id=r["step_id"],
            skip_reason=r["skip_reason"],
            round=r.get("round", 0),
            round_start_step_id=r.get("round_start_step_id"),
        )
    return StepRecord(
        step_id=r["step_id"],
        function_name=r["function_name"],
        attempts=r["attempts"],
        duration_ms=r["duration_ms"],
        round=r.get("round", 0),
        round_start_step_id=r.get("round_start_step_id"),
    )


@dataclass
class FlowState:
    flow_id: str
    flow_name: str
    raw_spec: str                    # original YAML — used to reconstruct state after restart
    spec: IRSpec
    ordered_steps: list[IRStepDef]
    inputs: dict[str, Any]           # flow-level inputs
    step_outputs: dict[str, Any]     # accumulated: step_id → output (None for skipped)
    records: list[StepRecord | GateRecord | SkipRecord]  # active round's completed records
    attempts: dict[str, int]         # current attempt count per step_id
    dispatched_at: dict[str, float]  # when each step was sent to Claude Code
    flow_start: float
    current_idx: int = 0
    checkpoints: dict[str, Any] = field(default_factory=dict)  # label → snapshot
    # v0.2: round tracking
    round: int = 0
    rounds: list[list[dict]] = field(default_factory=list)  # archived rounds (record-dicts)
    round_start_step_id: str | None = None  # first step id of the current round
    # v0.2: terminal status — set to "killed" when gate kill fires with null on_kill
    terminal_status: str | None = None


# ---------------------------------------------------------------------------
# In-memory flow state for the session lifetime.
# Declared here (not in server.py) so tests can inspect via executor_mod._flows.
# ---------------------------------------------------------------------------

_flows: dict[str, FlowState] = {}


# ---------------------------------------------------------------------------
# Flow persistence — ~/.stratum/flows/{flow_id}.json
# ---------------------------------------------------------------------------

_FLOWS_DIR = Path.home() / ".stratum" / "flows"


def persist_flow(state: FlowState) -> None:
    """Write flow state to ~/.stratum/flows/{flow_id}.json."""
    _FLOWS_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "flow_id":            state.flow_id,
        "flow_name":          state.flow_name,
        "raw_spec":           state.raw_spec,
        "inputs":             state.inputs,
        "step_outputs":       state.step_outputs,
        "records":            [dataclasses.asdict(r) for r in state.records],
        "attempts":           state.attempts,
        "current_idx":        state.current_idx,
        "checkpoints":        state.checkpoints,
        "round":              state.round,
        "rounds":             state.rounds,
        "round_start_step_id": state.round_start_step_id,
        "terminal_status":    state.terminal_status,
    }
    (_FLOWS_DIR / f"{state.flow_id}.json").write_text(json.dumps(payload, indent=2))


def restore_flow(flow_id: str) -> "FlowState | None":
    """
    Reconstruct a FlowState from disk after an MCP server restart.

    Returns ``None`` if no persistence file exists or if it cannot be parsed.
    Timing fields (``flow_start``, ``dispatched_at``) are reset to the current
    monotonic time — step durations will be inaccurate for the resumed step but
    all other state is faithfully restored.
    """
    from .spec import parse_and_validate  # local import avoids circular at module level

    path = _FLOWS_DIR / f"{flow_id}.json"
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return None
    try:
        spec = parse_and_validate(payload["raw_spec"])
    except Exception:
        return None
    flow_def = spec.flows.get(payload["flow_name"])
    if flow_def is None:
        return None
    ordered = _topological_sort(flow_def)
    records = [_record_from_dict(r) for r in payload.get("records", [])]
    return FlowState(
        flow_id=payload["flow_id"],
        flow_name=payload["flow_name"],
        raw_spec=payload["raw_spec"],
        spec=spec,
        ordered_steps=ordered,
        inputs=payload["inputs"],
        step_outputs=payload["step_outputs"],
        records=records,
        attempts=payload.get("attempts", {}),
        dispatched_at={},           # timing reset after restart
        flow_start=time.monotonic(),
        current_idx=payload["current_idx"],
        checkpoints=payload.get("checkpoints", {}),
        round=payload.get("round", 0),
        rounds=payload.get("rounds", []),
        round_start_step_id=payload.get("round_start_step_id"),
        terminal_status=payload.get("terminal_status"),
    )


def delete_persisted_flow(flow_id: str) -> None:
    """Remove the persistence file for a completed flow."""
    try:
        (_FLOWS_DIR / f"{flow_id}.json").unlink(missing_ok=True)
    except OSError:
        pass


# ---------------------------------------------------------------------------
# Checkpoints — named snapshots of mutable flow state
# ---------------------------------------------------------------------------

def commit_checkpoint(state: FlowState, label: str) -> None:
    """
    Snapshot current mutable state under ``label``.

    Stores step_outputs, attempts, records, current_idx, round, rounds,
    round_start_step_id, and terminal_status.
    Overwrites any existing checkpoint with the same label.
    Persists the updated flow to disk.
    """
    state.checkpoints[label] = {
        "step_outputs":       copy.deepcopy(state.step_outputs),
        "attempts":           dict(state.attempts),
        "records":            [dataclasses.asdict(r) for r in state.records],
        "current_idx":        state.current_idx,
        "round":              state.round,
        "rounds":             copy.deepcopy(state.rounds),
        "round_start_step_id": state.round_start_step_id,
        "terminal_status":    state.terminal_status,
    }
    persist_flow(state)


def revert_checkpoint(state: FlowState, label: str) -> bool:
    """
    Roll back mutable state to the snapshot stored under ``label``.

    Returns True on success, False if the label does not exist.
    Persists the reverted flow to disk on success.
    """
    snap = state.checkpoints.get(label)
    if snap is None:
        return False
    state.step_outputs       = copy.deepcopy(snap["step_outputs"])
    state.attempts           = dict(snap["attempts"])
    state.records            = [_record_from_dict(r) for r in snap["records"]]
    state.current_idx        = snap["current_idx"]
    state.round              = snap.get("round", 0)
    state.rounds             = copy.deepcopy(snap.get("rounds", []))
    state.round_start_step_id = snap.get("round_start_step_id")
    state.terminal_status    = snap.get("terminal_status")
    persist_flow(state)
    return True


def create_flow_state(spec: IRSpec, flow_name: str, inputs: dict[str, Any], raw_spec: str = "") -> FlowState:
    """Create flow execution state. Raises MCPExecutionError if flow not found."""
    flow_def = spec.flows.get(flow_name)
    if flow_def is None:
        raise MCPExecutionError(f"Flow '{flow_name}' not found in spec")
    ordered = _topological_sort(flow_def)
    return FlowState(
        flow_id=str(uuid.uuid4()),
        flow_name=flow_name,
        raw_spec=raw_spec,
        spec=spec,
        ordered_steps=ordered,
        inputs=inputs,
        step_outputs={},
        records=[],
        attempts={},
        dispatched_at={},
        flow_start=time.monotonic(),
        current_idx=0,
        round_start_step_id=None,  # round-0 records carry None per contract
    )


def get_current_step_info(state: FlowState) -> dict[str, Any] | None:
    """
    Return the current step as a dict Claude Code can act on, with resolved inputs.
    Records dispatch time for duration tracking. Returns None if the flow is complete.

    skip_if is evaluated before dispatch: if the expression is true the step is
    skipped (SkipRecord written, output set to None) and the next step is returned.
    Gate steps return status: "await_gate" instead of "execute_step".
    """
    if state.current_idx >= len(state.ordered_steps):
        return None

    step = state.ordered_steps[state.current_idx]
    fn_def = state.spec.functions[step.function]

    # Evaluate skip_if before dispatching (non-gate steps only; gates cannot be skipped).
    if step.skip_if and fn_def.mode != "gate":
        should_skip = evaluate_skip_if(step.skip_if, state.inputs, state.step_outputs)
        if should_skip:
            state.step_outputs[step.id] = None
            state.records.append(SkipRecord(
                step_id=step.id,
                skip_reason=step.skip_reason or f"skip_if: {step.skip_if}",
                round=state.round,
                round_start_step_id=state.round_start_step_id,
            ))
            state.current_idx += 1
            return get_current_step_info(state)  # tail-recurse for next step

    if fn_def.mode == "gate":
        # Use wall-clock time for gate dispatch so timeout detection works correctly.
        state.dispatched_at[step.id] = time.time()
        return {
            "status": "await_gate",
            "flow_id": state.flow_id,
            "step_number": state.current_idx + 1,
            "total_steps": len(state.ordered_steps),
            "step_id": step.id,
            "function": step.function,
            "on_approve": step.on_approve,
            "on_revise": step.on_revise,
            "on_kill": step.on_kill,
            "timeout": fn_def.timeout,
        }

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
      ("ok", [])                          — ensures passed, current_idx advanced
      ("ensure_failed", [violations])     — ensures failed, retries remain
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
                    round=state.round,
                    round_start_step_id=state.round_start_step_id,
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
                round=state.round,
                round_start_step_id=state.round_start_step_id,
            ))
            return ("retries_exhausted", violations)
        return ("ensure_failed", violations)

    state.step_outputs[step_id] = result
    state.records.append(StepRecord(
        step_id=step_id,
        function_name=fn_def.name,
        attempts=attempt,
        duration_ms=duration_ms,
        round=state.round,
        round_start_step_id=state.round_start_step_id,
    ))
    state.current_idx += 1
    return ("ok", [])


# ---------------------------------------------------------------------------
# Gate resolution (IR v0.2)
# ---------------------------------------------------------------------------

_VALID_OUTCOMES   = frozenset({"approve", "revise", "kill"})
_VALID_RESOLVERS  = frozenset({"human", "agent", "system"})


def resolve_gate(
    state: FlowState,
    step_id: str,
    outcome: str,
    rationale: str,
    resolved_by: str,
) -> tuple[str, dict[str, Any]]:
    """
    Resolve a gate step with the given outcome.

    Returns (status, extra) where status is one of:
      "complete"             — flow finished (approve with null on_approve)
      "killed"               — flow terminated (kill with null on_kill)
      "execute_step"         — routing to a named step
      "max_rounds_exceeded"  — revise refused; GateRecord written but not archived
      "error"                — bad call (wrong step, invalid outcome/resolver, etc.)

    extra contains additional context for the server to include in its response.
    """
    if outcome not in _VALID_OUTCOMES:
        return ("error", {
            "code": "invalid_outcome",
            "message": f"outcome must be one of {sorted(_VALID_OUTCOMES)}, got {outcome!r}",
        })
    if resolved_by not in _VALID_RESOLVERS:
        return ("error", {
            "code": "invalid_resolved_by",
            "message": f"resolved_by must be one of {sorted(_VALID_RESOLVERS)}, got {resolved_by!r}",
        })

    if state.current_idx >= len(state.ordered_steps):
        return ("error", {"code": "flow_already_complete", "message": "Flow is already complete"})

    step = state.ordered_steps[state.current_idx]
    if step.id != step_id:
        return ("error", {
            "code": "wrong_step",
            "message": f"Expected gate step '{step.id}', got '{step_id}'",
        })

    fn_def = state.spec.functions[step.function]
    if fn_def.mode != "gate":
        return ("error", {
            "code": "not_a_gate_step",
            "message": f"Step '{step_id}' is not a gate step (mode={fn_def.mode!r})",
        })

    # Gate steps use wall-clock time for dispatch; duration may be inaccurate after restart.
    dispatched = state.dispatched_at.get(step_id)
    duration_ms = int((time.time() - dispatched) * 1000) if dispatched is not None else 0

    gate_record = GateRecord(
        step_id=step_id,
        outcome=outcome,
        rationale=rationale,
        resolved_by=resolved_by,
        duration_ms=duration_ms,
        round=state.round,
        round_start_step_id=state.round_start_step_id,
    )

    if outcome == "approve":
        state.records.append(gate_record)
        if step.on_approve is None:
            # Null on_approve → complete the flow
            state.current_idx = len(state.ordered_steps)
            return ("complete", {})
        # Named on_approve → route to that step
        target_idx = next(
            (i for i, s in enumerate(state.ordered_steps) if s.id == step.on_approve), None
        )
        if target_idx is None:
            return ("error", {
                "code": "step_not_found",
                "message": f"on_approve target '{step.on_approve}' not found in flow",
            })
        state.current_idx = target_idx
        return ("execute_step", {"target_step_id": step.on_approve})

    elif outcome == "revise":
        # Two-phase operation: GateRecord written first, then max_rounds checked.
        # If max_rounds exceeded, GateRecord stays in state.records but is NOT archived.
        state.records.append(gate_record)

        flow_def = state.spec.flows[state.flow_name]
        if flow_def.max_rounds is not None and state.round >= flow_def.max_rounds:
            return ("max_rounds_exceeded", {
                "code": "max_rounds_exceeded",
                "message": f"Maximum rounds ({flow_def.max_rounds}) exceeded",
                "round": state.round,
            })

        if step.on_revise is None:
            return ("error", {
                "code": "missing_on_revise",
                "message": f"Gate step '{step_id}' has no on_revise target configured",
            })

        target_id = step.on_revise
        target_idx = next(
            (i for i, s in enumerate(state.ordered_steps) if s.id == target_id), None
        )
        if target_idx is None:
            return ("error", {
                "code": "step_not_found",
                "message": f"on_revise target '{target_id}' not found in flow",
            })

        # Archive current active records (including the GateRecord just appended)
        state.rounds.append([dataclasses.asdict(r) for r in state.records])

        # Clear active state from on_revise target onward
        steps_to_clear = {s.id for s in state.ordered_steps[target_idx:]}
        for sid in list(state.step_outputs.keys()):
            if sid in steps_to_clear:
                del state.step_outputs[sid]
        for sid in list(state.attempts.keys()):
            if sid in steps_to_clear:
                del state.attempts[sid]
        state.records = []
        state.current_idx = target_idx
        state.round += 1
        state.round_start_step_id = target_id

        return ("execute_step", {"target_step_id": target_id})

    else:  # outcome == "kill"
        state.records.append(gate_record)
        if step.on_kill is None:
            # Null on_kill → terminate the flow immediately
            state.current_idx = len(state.ordered_steps)
            state.terminal_status = "killed"
            return ("killed", {})
        # Named on_kill → route to terminal step (same branch semantics as approve)
        target_idx = next(
            (i for i, s in enumerate(state.ordered_steps) if s.id == step.on_kill), None
        )
        if target_idx is None:
            return ("error", {
                "code": "step_not_found",
                "message": f"on_kill target '{step.on_kill}' not found in flow",
            })
        state.current_idx = target_idx
        state.terminal_status = "killed"  # flow is killed even when routing to a cleanup step
        return ("execute_step", {"target_step_id": step.on_kill})
