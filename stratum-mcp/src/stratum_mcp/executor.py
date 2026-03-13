"""Flow controller: plan state management, $ reference resolution, ensure compilation."""
from __future__ import annotations

import concurrent.futures
import copy
import hashlib
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
# Stagnation detection — default consecutive-duplicate threshold
# ---------------------------------------------------------------------------

_STAGNATION_WINDOW = 3  # halt after N identical consecutive iteration results


# ---------------------------------------------------------------------------
# Guardrail scanning — deterministic, no LLM in the safety path
# ---------------------------------------------------------------------------

_GUARDRAIL_SEARCH_TIMEOUT_S = 1.0  # per-pattern wall-clock timeout

def _scan_guardrails(patterns: list[re.Pattern[str]], text: str) -> list[str]:
    """Run pre-compiled regex patterns against text. Return list of matched pattern strings.

    Each pattern search is bounded by a wall-clock timeout to prevent ReDoS.
    Patterns that timeout or error are treated as matches (fail-closed).
    """
    hits: list[str] = []
    for compiled in patterns:
        pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        try:
            future = pool.submit(compiled.search, text)
            match = future.result(timeout=_GUARDRAIL_SEARCH_TIMEOUT_S)
            if match:
                hits.append(compiled.pattern)
        except concurrent.futures.TimeoutError:
            # ReDoS or slow pattern — fail-closed: treat as match
            hits.append(compiled.pattern)
        except Exception:
            # Any other error — fail-closed
            hits.append(compiled.pattern)
        finally:
            pool.shutdown(wait=False, cancel_futures=True)
    return hits


def compile_guardrails(patterns: list[str]) -> list[re.Pattern[str]]:
    """Compile guardrail regex patterns. Raises re.error on invalid patterns."""
    compiled: list[re.Pattern[str]] = []
    for pat in patterns:
        compiled.append(re.compile(pat, re.IGNORECASE | re.MULTILINE))
    return compiled


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


def _no_file_conflicts(tasks: Any) -> bool:
    """Validate that no two independent tasks share files_owned entries.

    Two tasks are independent if neither depends (directly or transitively)
    on the other.  Read-only overlap (files_read) is allowed; only write
    overlap (files_owned) between independent tasks is a conflict.

    ``tasks`` may be a list of dicts or SimpleNamespace objects.
    """
    # Normalise to dicts
    def _as_dict(t: Any) -> dict:
        if isinstance(t, dict):
            return t
        return vars(t)

    task_list = [_as_dict(t) for t in tasks]

    # Build transitive dependency sets (both directions)
    dep_map: dict[str, set[str]] = {}
    for t in task_list:
        tid = t.get("id", "")
        dep_map[tid] = set(t.get("depends_on", []))

    # Expand transitively
    def _all_deps(tid: str, visited: set[str] | None = None) -> set[str]:
        if visited is None:
            visited = set()
        if tid in visited:
            return set()
        visited.add(tid)
        direct = dep_map.get(tid, set())
        result = set(direct)
        for d in direct:
            result |= _all_deps(d, visited)
        return result

    transitive: dict[str, set[str]] = {tid: _all_deps(tid) for tid in dep_map}

    def _has_dependency(a: str, b: str) -> bool:
        return b in transitive.get(a, set()) or a in transitive.get(b, set())

    # Check pairwise file ownership conflicts
    for i, t1 in enumerate(task_list):
        for t2 in task_list[i + 1:]:
            id1 = t1.get("id", f"task-{i}")
            id2 = t2.get("id", f"task-{i+1}")
            if _has_dependency(id1, id2):
                continue
            owned1 = set(t1.get("files_owned", []))
            owned2 = set(t2.get("files_owned", []))
            overlap = owned1 & owned2
            if overlap:
                raise ValueError(
                    f"File ownership conflict between independent tasks "
                    f"'{id1}' and '{id2}': {sorted(overlap)}"
                )
    return True


_ENSURE_BUILTINS: dict[str, Any] = {
    "file_exists": lambda p: os.path.isfile(p),
    "file_contains": _file_contains,
    "len": len,
    "bool": bool,
    "int": int,
    "str": str,
    "no_file_conflicts": _no_file_conflicts,
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
                try:
                    output = output[key]
                except KeyError:
                    raise RefResolutionError(
                        f"Key '{key}' not found in $.steps.{step_id}.output — "
                        f"available keys: {sorted(output.keys())}"
                    )
            else:
                try:
                    output = getattr(output, key)
                except AttributeError:
                    raise RefResolutionError(
                        f"Attribute '{key}' not found on $.steps.{step_id}.output"
                    )
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
                                "true": True, "false": False, "null": None,
                                **_ENSURE_BUILTINS}))
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


def _step_mode(step) -> str:
    """Return 'function', 'inline', 'flow', 'decompose', or 'parallel_dispatch'."""
    if step.step_type == "decompose":
        return "decompose"
    if step.step_type == "parallel_dispatch":
        return "parallel_dispatch"
    if step.function:
        return "function"
    if step.intent:
        return "inline"
    if step.flow_ref:
        return "flow"
    raise MCPExecutionError(f"Step '{step.id}' has no execution mode")


def _find_step_idx(state: "FlowState", target_id: str) -> int:
    """Find step index by id. Raise MCPExecutionError if not found."""
    idx = next((i for i, s in enumerate(state.ordered_steps) if s.id == target_id), None)
    if idx is None:
        raise MCPExecutionError(f"Step '{target_id}' not found in flow")
    return idx


def _clear_from(state: "FlowState", target_idx: int, preserve: set[str] | None = None) -> None:
    """Clear attempts, outputs, and iteration state from target_idx onward.

    Used by on_fail, next, and resolve_gate (on_revise). This is a within-round
    clear — it does NOT archive rounds or iterations. resolve_gate handles
    archival separately before calling this.

    preserve: step ids to exclude from clearing. Used by on_fail to keep the
    failed step's output accessible to the recovery step even when the target
    is topologically before the failed step.
    """
    steps_to_clear = {s.id for s in state.ordered_steps[target_idx:]}
    if preserve:
        steps_to_clear -= preserve
    for sid in list(state.step_outputs.keys()):
        if sid in steps_to_clear:
            del state.step_outputs[sid]
    for sid in list(state.attempts.keys()):
        if sid in steps_to_clear:
            del state.attempts[sid]
    for sid in steps_to_clear:
        state.iteration_outcome.pop(sid, None)
    # Clear per-step iteration history for affected steps (ENG-4)
    for sid in steps_to_clear:
        state.iterations.pop(sid, None)
    # Clear active_iteration if it belongs to an affected step
    if state.active_iteration and state.active_iteration.get("step_id") in steps_to_clear:
        state.active_iteration = None
    # Clear active child flow if it belongs to an affected flow_ref step
    if hasattr(state, "active_child_flow_id") and state.active_child_flow_id is not None:
        state.active_child_flow_id = None


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
    agent: str | None = None
    step_mode: str = "function"
    child_flow_id: str | None = None


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


@dataclass
class PolicyRecord:
    """Trace entry written when a gate step is auto-resolved by policy (flag or skip)."""
    step_id: str
    effective_policy: str    # "flag" or "skip"
    resolved_outcome: str    # always "approve"
    rationale: str
    type: str = "policy"     # noqa: A003
    round: int = 0
    round_start_step_id: str | None = None


def _record_from_dict(r: dict) -> StepRecord | GateRecord | SkipRecord | PolicyRecord:
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
    if rec_type == "policy":
        return PolicyRecord(
            step_id=r["step_id"],
            effective_policy=r["effective_policy"],
            resolved_outcome=r["resolved_outcome"],
            rationale=r["rationale"],
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
        agent=r.get("agent"),
        step_mode=r.get("step_mode", "function"),
        child_flow_id=r.get("child_flow_id"),
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
    records: list[StepRecord | GateRecord | SkipRecord | PolicyRecord]  # active round's completed records
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
    # v0.2 STRAT-ENG-4: per-step iteration tracking
    iterations: dict[str, list[dict]] = field(default_factory=dict)
    archived_iterations: list[dict[str, list[dict]]] = field(default_factory=list)
    active_iteration: dict[str, Any] | None = None
    iteration_outcome: dict[str, str] = field(default_factory=dict)
    # v0.2 STRAT-ENG-5: flow composition
    parent_flow_id: str | None = None
    parent_step_id: str | None = None
    active_child_flow_id: str | None = None
    child_audits: dict[str, list[dict]] = field(default_factory=dict)


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
        "iterations":         state.iterations,
        "archived_iterations": state.archived_iterations,
        "active_iteration":   state.active_iteration,
        "iteration_outcome":  state.iteration_outcome,
        "parent_flow_id":     state.parent_flow_id,
        "parent_step_id":     state.parent_step_id,
        "active_child_flow_id": state.active_child_flow_id,
        "child_audits":       state.child_audits,
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
        iterations=payload.get("iterations", {}),
        archived_iterations=payload.get("archived_iterations", []),
        active_iteration=payload.get("active_iteration"),
        iteration_outcome=payload.get("iteration_outcome", {}),
        parent_flow_id=payload.get("parent_flow_id"),
        parent_step_id=payload.get("parent_step_id"),
        active_child_flow_id=payload.get("active_child_flow_id"),
        child_audits=payload.get("child_audits", {}),
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
    round_start_step_id, terminal_status, iteration state, and flow
    composition state (active_child_flow_id, child_audits).
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
        "iterations":         copy.deepcopy(state.iterations),
        "archived_iterations": copy.deepcopy(state.archived_iterations),
        "active_iteration":   copy.deepcopy(state.active_iteration),
        "iteration_outcome":  dict(state.iteration_outcome),
        "active_child_flow_id": state.active_child_flow_id,
        "child_audits":       copy.deepcopy(state.child_audits),
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
    state.iterations         = copy.deepcopy(snap.get("iterations", {}))
    state.archived_iterations = copy.deepcopy(snap.get("archived_iterations", []))
    state.active_iteration   = copy.deepcopy(snap.get("active_iteration"))
    state.iteration_outcome  = dict(snap.get("iteration_outcome", {}))
    state.active_child_flow_id = snap.get("active_child_flow_id")
    state.child_audits       = copy.deepcopy(snap.get("child_audits", {}))
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


def skip_step(state: FlowState, step_id: str, reason: str) -> None:
    """Skip the current step: write SkipRecord, set output to None, advance.

    Raises MCPExecutionError if step_id doesn't match current step or if the
    step is a gate step (gates must be resolved via stratum_gate_resolve).
    """
    if state.current_idx >= len(state.ordered_steps):
        raise MCPExecutionError("Flow is already complete")
    step = state.ordered_steps[state.current_idx]
    if step.id != step_id:
        raise MCPExecutionError(f"Expected step '{step.id}', got '{step_id}'")
    # Gate steps cannot be skipped — they must be resolved via gate_resolve or policy.
    fn_def = state.spec.functions.get(step.function) if step.function else None
    if fn_def is not None and fn_def.mode == "gate":
        raise MCPExecutionError(
            f"Step '{step_id}' is a gate step — use stratum_gate_resolve to resolve it"
        )
    state.step_outputs[step.id] = None
    state.records.append(SkipRecord(
        step_id=step.id,
        skip_reason=reason,
        round=state.round,
        round_start_step_id=state.round_start_step_id,
    ))
    state.current_idx += 1


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

    # Gate check: only function steps can be gates.
    fn_def = state.spec.functions.get(step.function) if step.function else None
    is_gate = fn_def is not None and fn_def.mode == "gate"

    # skip_if evaluation: mode-agnostic, runs before dispatch.
    # Gates cannot be skipped (validator rejects skip_if on gate steps).
    if step.skip_if and not is_gate:
        should_skip = evaluate_skip_if(step.skip_if, state.inputs, state.step_outputs)
        if should_skip:
            skip_step(state, step.id, step.skip_reason or f"skip_if: {step.skip_if}")
            return get_current_step_info(state)  # tail-recurse for next step

    # Gate skip_if: gates can now use skip_if (file_exists-based markers).
    # When a gate's skip_if evaluates to true, auto-approve via PolicyRecord.
    if is_gate and step.skip_if:
        should_skip = evaluate_skip_if(step.skip_if, state.inputs, state.step_outputs)
        if should_skip:
            state.records.append(PolicyRecord(
                step_id=step.id,
                effective_policy="skip_if",
                resolved_outcome="approve",
                rationale=step.skip_reason or f"skip_if: {step.skip_if}",
                round=state.round,
                round_start_step_id=state.round_start_step_id,
            ))
            if step.on_approve is not None:
                target_idx = next(
                    (i for i, s in enumerate(state.ordered_steps) if s.id == step.on_approve), None
                )
                state.current_idx = target_idx if target_idx is not None else state.current_idx + 1
            else:
                state.current_idx = len(state.ordered_steps)
            state.step_outputs[step.id] = None
            return get_current_step_info(state)  # tail-recurse for next step

    mode = _step_mode(step)

    if is_gate:
        # Use wall-clock time for gate dispatch so timeout detection works correctly.
        state.dispatched_at[step.id] = time.time()
        return {
            "status": "await_gate",
            "flow_id": state.flow_id,
            "step_number": state.current_idx + 1,
            "total_steps": len(state.ordered_steps),
            "step_id": step.id,
            "step_mode": "function",
            "function": step.function,
            "agent": step.agent,
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

    if mode == "function":
        contract = state.spec.contracts.get(fn_def.output_contract)
        output_fields = {k: v.get("type", "any") for k, v in contract.fields.items()} if contract else {}
        return {
            "status": "execute_step",
            "flow_id": state.flow_id,
            "step_number": state.current_idx + 1,
            "total_steps": len(state.ordered_steps),
            "step_id": step.id,
            "step_mode": "function",
            "function": step.function,
            "agent": step.agent,
            "mode": fn_def.mode,
            "intent": fn_def.intent,
            "inputs": resolved,
            "output_contract": fn_def.output_contract,
            "output_fields": output_fields,
            "ensure": fn_def.ensure,
            "retries_remaining": fn_def.retries - attempts_so_far,
        }

    elif mode == "inline":
        max_retries = step.step_retries or 1
        contract = state.spec.contracts.get(step.output_contract or "")
        output_fields = {k: v.get("type", "any") for k, v in contract.fields.items()} if contract else {}
        return {
            "status": "execute_step",
            "flow_id": state.flow_id,
            "step_number": state.current_idx + 1,
            "total_steps": len(state.ordered_steps),
            "step_id": step.id,
            "step_mode": "inline",
            "intent": step.intent,
            "agent": step.agent,
            "inputs": resolved,
            "output_contract": step.output_contract,
            "output_fields": output_fields,
            "ensure": step.step_ensure or [],
            "retries_remaining": max_retries - attempts_so_far,
            "model": step.step_model,
        }

    elif mode == "decompose":
        max_retries = step.step_retries or 2
        contract = state.spec.contracts.get(step.output_contract or "")
        output_fields = {k: v.get("type", "any") for k, v in contract.fields.items()} if contract else {}
        return {
            "status": "execute_step",
            "flow_id": state.flow_id,
            "step_number": state.current_idx + 1,
            "total_steps": len(state.ordered_steps),
            "step_id": step.id,
            "step_mode": "decompose",
            "intent": step.intent,
            "agent": step.agent,
            "inputs": resolved,
            "output_contract": step.output_contract,
            "output_fields": output_fields,
            "ensure": step.step_ensure or [],
            "retries_remaining": max_retries - attempts_so_far,
        }

    elif mode == "parallel_dispatch":
        # Resolve the source reference to get the task graph
        # source is guaranteed non-None by semantic validation for parallel_dispatch
        assert step.source is not None, "parallel_dispatch step must have source"
        source_tasks = resolve_ref(step.source, state.inputs, state.step_outputs)
        return {
            "status": "parallel_dispatch",
            "flow_id": state.flow_id,
            "step_number": state.current_idx + 1,
            "total_steps": len(state.ordered_steps),
            "step_id": step.id,
            "step_mode": "parallel_dispatch",
            "tasks": source_tasks,
            "agent": step.agent,
            "max_concurrent": step.max_concurrent or 3,
            "isolation": step.isolation or "worktree",
            "require": step.require or "all",
            "merge": step.merge or "sequential_apply",
            "intent_template": step.intent_template,
            "ensure": step.step_ensure or [],
            "retries_remaining": (step.step_retries or 2) - attempts_so_far,
        }

    elif mode == "flow":
        child_state = None

        # Resume: if a child flow is tracked, try to restore it
        if state.active_child_flow_id:
            child_state = _flows.get(state.active_child_flow_id)
            if child_state is None:
                child_state = restore_flow(state.active_child_flow_id)
            if child_state is not None:
                _flows[child_state.flow_id] = child_state
            else:
                # Child is gone (crash between child completion and parent update).
                # Clear stale pointer — a new child will be created below.
                state.active_child_flow_id = None

        # Create: no existing child — resolve inputs and create fresh
        if child_state is None:
            child_state = create_flow_state(
                spec=state.spec,
                flow_name=step.flow_ref or "",
                inputs=resolved,
                raw_spec=state.raw_spec,
            )
            child_state.parent_flow_id = state.flow_id
            child_state.parent_step_id = step.id
            _flows[child_state.flow_id] = child_state
            state.active_child_flow_id = child_state.flow_id
            persist_flow(child_state)
            persist_flow(state)

        # Get child's current step
        child_step = get_current_step_info(child_state)

        return {
            "status": "execute_flow",
            "parent_flow_id": state.flow_id,
            "parent_step_id": step.id,
            "child_flow_id": child_state.flow_id,
            "child_flow_name": step.flow_ref,
            "child_step": child_step,
            "step_number": state.current_idx + 1,
            "total_steps": len(state.ordered_steps),
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

    mode = _step_mode(step)

    if mode == "function":
        fn_def = state.spec.functions[step.function]
        ensure_exprs = fn_def.ensure
        max_retries = fn_def.retries
        output_schema = step.output_schema
        fn_name = fn_def.name
        guardrail_patterns = fn_def.guardrails
    else:  # mode in ("inline", "flow", "decompose", "parallel_dispatch")
        ensure_exprs = step.step_ensure or []
        max_retries = step.step_retries or (2 if mode in ("decompose", "parallel_dispatch") else 1)
        output_schema = None
        fn_name = ""
        guardrail_patterns = step.step_guardrails or []

    state.attempts[step_id] = state.attempts.get(step_id, 0) + 1
    attempt = state.attempts[step_id]

    def _make_record(dur_ms: int) -> StepRecord:
        return StepRecord(
            step_id=step_id,
            function_name=fn_name,
            attempts=attempt,
            duration_ms=dur_ms,
            round=state.round,
            round_start_step_id=state.round_start_step_id,
            agent=step.agent,
            step_mode=mode,
            child_flow_id=state.active_child_flow_id if mode == "flow" else None,
        )

    # Schema validation runs before ensures — structural errors are caught first.
    if output_schema is not None:
        schema_errors = _validate_output_schema(result, output_schema)
        if schema_errors:
            if attempt >= max_retries:
                dispatched = state.dispatched_at.get(step_id, state.flow_start)
                duration_ms = int((time.monotonic() - dispatched) * 1000)
                state.records.append(_make_record(duration_ms))
                if step.on_fail:
                    state.step_outputs[step_id] = result
                    target_idx = _find_step_idx(state, step.on_fail)
                    _clear_from(state, target_idx, preserve={step_id})
                    state.current_idx = target_idx
                    return ("on_fail_routed", schema_errors)
                return ("retries_exhausted", schema_errors)
            return ("schema_failed", schema_errors)

    # Guardrail scan: regex patterns checked against serialized result before acceptance.
    # Runs before ensures — blocks dangerous content before any side effects.
    if guardrail_patterns:
        result_text = json.dumps(result, sort_keys=True, default=str)
        compiled = compile_guardrails(guardrail_patterns)
        guardrail_hits = _scan_guardrails(compiled, result_text)
        if guardrail_hits:
            guardrail_violations = [
                f"guardrail matched: {pat!r}" for pat in guardrail_hits
            ]
            if attempt >= max_retries:
                dispatched = state.dispatched_at.get(step_id, state.flow_start)
                duration_ms = int((time.monotonic() - dispatched) * 1000)
                state.records.append(_make_record(duration_ms))
                if step.on_fail:
                    state.step_outputs[step_id] = result
                    target_idx = _find_step_idx(state, step.on_fail)
                    _clear_from(state, target_idx, preserve={step_id})
                    state.current_idx = target_idx
                    return ("on_fail_routed", guardrail_violations)
                return ("retries_exhausted", guardrail_violations)
            return ("guardrail_blocked", guardrail_violations)

    violations: list[str] = []
    for expr in ensure_exprs:
        try:
            fn = compile_ensure(expr)
            if not fn(result):
                violations.append(f"ensure '{expr}' failed")
        except EnsureCompileError as exc:
            violations.append(str(exc))

    dispatched = state.dispatched_at.get(step_id, state.flow_start)
    duration_ms = int((time.monotonic() - dispatched) * 1000)

    if violations:
        if attempt >= max_retries:
            state.records.append(_make_record(duration_ms))
            if step.on_fail:
                state.step_outputs[step_id] = result
                target_idx = _find_step_idx(state, step.on_fail)
                _clear_from(state, target_idx, preserve={step_id})
                state.current_idx = target_idx
                return ("on_fail_routed", violations)
            return ("retries_exhausted", violations)
        return ("ensure_failed", violations)

    state.step_outputs[step_id] = result
    state.records.append(_make_record(duration_ms))
    if mode == "flow":
        state.active_child_flow_id = None
    if step.next:
        target_idx = _find_step_idx(state, step.next)
        _clear_from(state, target_idx)
        state.current_idx = target_idx
    else:
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
            "error_type": "invalid_outcome",
            "message": f"outcome must be one of {sorted(_VALID_OUTCOMES)}, got {outcome!r}",
        })
    if resolved_by not in _VALID_RESOLVERS:
        return ("error", {
            "error_type": "invalid_resolved_by",
            "message": f"resolved_by must be one of {sorted(_VALID_RESOLVERS)}, got {resolved_by!r}",
        })

    if state.current_idx >= len(state.ordered_steps):
        return ("error", {"error_type": "flow_already_complete", "message": "Flow is already complete"})

    step = state.ordered_steps[state.current_idx]
    if step.id != step_id:
        return ("error", {
            "error_type": "wrong_step",
            "message": f"Expected gate step '{step.id}', got '{step_id}'",
        })

    fn_def = state.spec.functions[step.function]
    if fn_def.mode != "gate":
        return ("error", {
            "error_type": "not_a_gate_step",
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
                "error_type": "step_not_found",
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
                "error_type": "max_rounds_exceeded",
                "message": f"Maximum rounds ({flow_def.max_rounds}) exceeded",
                "round": state.round,
            })

        if step.on_revise is None:
            return ("error", {
                "error_type": "missing_on_revise",
                "message": f"Gate step '{step_id}' has no on_revise target configured",
            })

        target_id = step.on_revise
        try:
            target_idx = _find_step_idx(state, target_id)
        except MCPExecutionError:
            return ("error", {
                "error_type": "step_not_found",
                "message": f"on_revise target '{target_id}' not found in flow",
            })

        # Archive current active records (including the GateRecord just appended)
        state.rounds.append([dataclasses.asdict(r) for r in state.records])

        # Archive current-round iteration data (parallel to rounds[])
        state.archived_iterations.append(state.iterations)
        state.iterations = {}
        state.active_iteration = None

        # Clear active state from on_revise target onward
        _clear_from(state, target_idx)
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
                "error_type": "step_not_found",
                "message": f"on_kill target '{step.on_kill}' not found in flow",
            })
        state.current_idx = target_idx
        state.terminal_status = "killed"  # flow is killed even when routing to a cleanup step
        return ("execute_step", {"target_step_id": step.on_kill})


# ---------------------------------------------------------------------------
# Gate policy evaluation (IR v0.2)
# ---------------------------------------------------------------------------

def apply_gate_policy(
    state: FlowState,
    step_id: str,
) -> dict[str, Any] | None:
    """
    Check policy on the current gate step and auto-resolve if flag or skip.

    Called by the server layer after get_current_step_info returns await_gate.
    Does NOT call resolve_gate (avoids writing a GateRecord).

    Returns:
      None              — policy is "gate" (default); caller returns await_gate as-is
      {"status": ...}   — auto-resolved; dict is complete or next step info
    """
    if state.current_idx >= len(state.ordered_steps):
        return None

    step = state.ordered_steps[state.current_idx]
    if step.id != step_id:
        return None  # defensive — should not happen

    effective_policy = step.policy or "gate"
    if effective_policy == "gate":
        return None

    # Auto-approve: write PolicyRecord, handle on_approve routing.
    state.records.append(PolicyRecord(
        step_id=step_id,
        effective_policy=effective_policy,
        resolved_outcome="approve",
        rationale=f"policy: {effective_policy} — auto-approved",
        round=state.round,
        round_start_step_id=state.round_start_step_id,
    ))

    if step.on_approve is None:
        # Null on_approve → complete the flow
        state.current_idx = len(state.ordered_steps)
        total_ms = int((time.monotonic() - state.flow_start) * 1000)
        output = next(
            (state.step_outputs[s.id] for s in reversed(state.ordered_steps)
             if s.id in state.step_outputs and state.step_outputs[s.id] is not None),
            None,
        )
        return {
            "status": "complete",
            "flow_id": state.flow_id,
            "output": output,
            "trace": [dataclasses.asdict(r) for r in state.records],
            "total_duration_ms": total_ms,
        }

    # Named on_approve → route to that step
    target_idx = next(
        (i for i, s in enumerate(state.ordered_steps) if s.id == step.on_approve), None
    )
    if target_idx is None:
        raise MCPExecutionError(
            f"on_approve target '{step.on_approve}' not found in flow"
        )
    state.current_idx = target_idx
    return get_current_step_info(state)


# ---------------------------------------------------------------------------
# Per-step iteration (STRAT-ENG-4)
# ---------------------------------------------------------------------------

def start_iteration(state: FlowState, step_id: str) -> dict[str, Any]:
    """Start an iteration loop on the current step.

    The step must have max_iterations defined. Only one iteration loop can be
    active at a time. Gate steps cannot have iterations.
    """
    if state.current_idx >= len(state.ordered_steps):
        raise MCPExecutionError("Flow is already complete")

    step = state.ordered_steps[state.current_idx]
    if step.id != step_id:
        raise MCPExecutionError(f"Expected step '{step.id}', got '{step_id}'")

    # Gate check
    fn_def = state.spec.functions.get(step.function) if step.function else None
    if fn_def is not None and fn_def.mode == "gate":
        raise MCPExecutionError(
            f"Step '{step_id}' is a gate step — cannot start iteration loop"
        )

    if step.max_iterations is None:
        raise MCPExecutionError(
            f"Step '{step_id}' does not have max_iterations defined"
        )

    if state.active_iteration is not None:
        raise MCPExecutionError(
            f"Iteration loop already active on step '{state.active_iteration['step_id']}'"
        )

    if step_id in state.iteration_outcome:
        raise MCPExecutionError(
            f"Step '{step_id}' already has a pending iteration outcome "
            f"('{state.iteration_outcome[step_id]}') — call stratum_step_done first"
        )

    state.active_iteration = {
        "step_id": step_id,
        "round": state.round,
        "max_iterations": step.max_iterations,
        "exit_criterion": step.exit_criterion,
        "count": 0,
        "started_at": time.monotonic(),
        "status": "active",
    }

    persist_flow(state)

    return {
        "status": "iteration_started",
        "flow_id": state.flow_id,
        "step_id": step_id,
        "max_iterations": step.max_iterations,
        "exit_criterion": step.exit_criterion,
        "iteration": 0,
    }


def report_iteration(
    state: FlowState,
    step_id: str,
    result: dict[str, Any],
) -> dict[str, Any]:
    """Report one iteration result. Evaluates exit_criterion, enforces max."""
    if state.active_iteration is None:
        raise MCPExecutionError("No active iteration loop")
    if state.active_iteration["step_id"] != step_id:
        raise MCPExecutionError(
            f"Active iteration is on step '{state.active_iteration['step_id']}', "
            f"got report for '{step_id}'"
        )

    ai = state.active_iteration
    ai["count"] += 1
    count = ai["count"]
    max_iter = ai["max_iterations"]

    # Evaluate exit criterion
    exit_met = False
    exit_criterion_error: str | None = None
    if ai["exit_criterion"]:
        try:
            fn = compile_ensure(ai["exit_criterion"])
            exit_met = fn(result)
        except EnsureCompileError as exc:
            exit_met = False
            exit_criterion_error = str(exc)

    # Stagnation detection: fingerprint the result and check for consecutive duplicates
    result_fingerprint = hashlib.sha256(
        json.dumps(result, sort_keys=True, default=str).encode()
    ).hexdigest()

    stagnation_detected = False
    if not exit_met:
        history = state.iterations.get(step_id, [])
        # Check last (_STAGNATION_WINDOW - 1) entries — if all have the same fingerprint
        # as the current result, this is the Nth consecutive duplicate
        window = _STAGNATION_WINDOW - 1  # need (window) prior + current = _STAGNATION_WINDOW
        if len(history) >= window:
            recent = history[-window:]
            if all(r.get("result_fingerprint") == result_fingerprint for r in recent):
                stagnation_detected = True

    # Determine outcome
    if exit_met:
        outcome = "exit_success"
    elif stagnation_detected:
        outcome = "exit_stagnation"
    elif count >= max_iter:
        outcome = "exit_max"
    else:
        outcome = "continue"

    # Append report to history
    report = {
        "iteration": count,
        "round": state.round,
        "result": result,
        "result_fingerprint": result_fingerprint,
        "exit_criterion_met": exit_met,
        "outcome": outcome,
        "timestamp": time.monotonic(),
    }
    state.iterations.setdefault(step_id, []).append(report)

    # On exit: write outcome, clear active
    if outcome != "continue":
        state.iteration_outcome[step_id] = outcome
        state.active_iteration = None

    persist_flow(state)

    response: dict[str, Any] = {
        "status": "iteration_continue" if outcome == "continue" else "iteration_exit",
        "flow_id": state.flow_id,
        "step_id": step_id,
        "iteration": count,
        "max_iterations": max_iter,
        "exit_criterion_met": exit_met,
        "outcome": outcome,
    }
    if exit_criterion_error:
        response["exit_criterion_error"] = exit_criterion_error
    if outcome != "continue":
        response["final_result"] = result
    return response


def abort_iteration(
    state: FlowState,
    step_id: str,
    reason: str,
) -> dict[str, Any]:
    """Abort an active iteration loop before completion."""
    if state.active_iteration is None:
        raise MCPExecutionError("No active iteration loop")
    if state.active_iteration["step_id"] != step_id:
        raise MCPExecutionError(
            f"Active iteration is on step '{state.active_iteration['step_id']}', "
            f"got abort for '{step_id}'"
        )

    count = state.active_iteration["count"]

    # Append abort report — uses count (not count+1) because abort is not a real iteration
    report = {
        "iteration": count,
        "round": state.round,
        "result": {"aborted": True, "reason": reason},
        "exit_criterion_met": False,
        "outcome": "exit_abort",
        "timestamp": time.monotonic(),
    }
    state.iterations.setdefault(step_id, []).append(report)

    state.iteration_outcome[step_id] = "exit_abort"
    state.active_iteration = None

    persist_flow(state)

    return {
        "status": "iteration_aborted",
        "flow_id": state.flow_id,
        "step_id": step_id,
        "iteration": count,
        "reason": reason,
    }
