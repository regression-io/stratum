"""FastMCP server entry point. MCP controller: plan management, step tracking, audit."""
from __future__ import annotations

import dataclasses
import json
import sys
import time
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP, Context

from .errors import IRParseError, IRValidationError, IRSemanticError, MCPExecutionError, exception_to_mcp_error
from .executor import (
    FlowState,
    _flows,
    create_flow_state,
    get_current_step_info,
    process_step_result,
    resolve_gate,
    apply_gate_policy,
    skip_step,
    start_iteration,
    report_iteration,
    abort_iteration,
    persist_flow,
    restore_flow,
    delete_persisted_flow,
    commit_checkpoint,
    revert_checkpoint,
)
from .spec import parse_and_validate

mcp = FastMCP(
    "stratum-mcp",
    instructions=(
        "Stratum execution controller for Claude Code. "
        "Validates .stratum.yaml IR specs, manages flow execution state, "
        "and tracks step results with ensure postcondition enforcement."
    ),
)


def _apply_policy_loop(
    state: FlowState,
    step_info: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Apply gate policy in a loop until a non-auto-resolvable state is reached.

    Handles chained flag/skip gates. Bounded by visited-set to prevent
    on_approve routing cycles from hanging.
    """
    visited: set[str] = set()
    while step_info is not None and step_info.get("status") == "await_gate":
        gate_step_id = step_info["step_id"]
        if gate_step_id in visited:
            break  # cycle detected — treat as gate (require manual resolution)
        visited.add(gate_step_id)
        policy_result = apply_gate_policy(state, gate_step_id)
        if policy_result is None:
            break  # policy is "gate" — return await_gate to caller
        step_info = policy_result
    return step_info


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
    "Create an execution plan from a validated .stratum.yaml spec. "
    "Inputs: spec (str, inline YAML), flow (str, flow name), inputs (dict, flow-level inputs). "
    "Returns the first step to execute with resolved inputs and output contract details. "
    "Call stratum_step_done when each step is complete."
))
async def stratum_plan(
    spec: str,
    flow: str,
    inputs: dict[str, Any],
    ctx: Context,
) -> dict[str, Any]:
    try:
        ir_spec = parse_and_validate(spec)
    except (IRParseError, IRValidationError, IRSemanticError) as exc:
        return {"status": "error", **exception_to_mcp_error(exc)}

    try:
        state = create_flow_state(ir_spec, flow, inputs, raw_spec=spec)
    except MCPExecutionError as exc:
        return {"status": "error", **exception_to_mcp_error(exc)}

    _flows[state.flow_id] = state
    try:
        step_info = get_current_step_info(state)  # may skip steps, mutating state
        step_info = _apply_policy_loop(state, step_info)
    except MCPExecutionError as exc:
        return {"status": "error", **exception_to_mcp_error(exc)}
    if step_info is not None and step_info.get("status") == "complete":
        delete_persisted_flow(state.flow_id)
        return step_info
    persist_flow(state)                        # persist AFTER skip/policy mutations
    return step_info  # always non-None: schema enforces minItems: 1


@mcp.tool(description=(
    "Report a completed step result. "
    "Inputs: flow_id (str), step_id (str), result (dict matching the step's output contract). "
    "Checks ensure postconditions. Returns next step to execute, ensure failure with retry "
    "instructions, or flow completion with final output and trace."
))
async def stratum_step_done(
    flow_id: str,
    step_id: str,
    result: dict[str, Any],
    ctx: Context,
) -> dict[str, Any]:
    state = _flows.get(flow_id)
    if state is None:
        state = restore_flow(flow_id)
        if state is None:
            return {
                "status": "error",
                "error_type": "flow_not_found",
                "message": f"No active flow with id '{flow_id}'",
            }
        _flows[flow_id] = state

    # Gate step rejection: must not process gate steps through stratum_step_done.
    # This check fires before process_step_result so no state is mutated on rejection.
    if state.current_idx < len(state.ordered_steps):
        _cur = state.ordered_steps[state.current_idx]
        _fn = state.spec.functions.get(_cur.function) if _cur.function else None
        if _fn and _fn.mode == "gate":
            return {
                "status": "error",
                "code": "gate_step_requires_gate_resolve",
                "message": (
                    f"Step '{_cur.id}' is a gate step. "
                    "Use stratum_gate_resolve to resolve it."
                ),
            }

    try:
        status, violations = process_step_result(state, step_id, result)
    except MCPExecutionError as exc:
        return {"status": "error", **exception_to_mcp_error(exc)}

    if status == "retries_exhausted":
        delete_persisted_flow(flow_id)
        _step = state.ordered_steps[state.current_idx]
        return {
            "status": "error",
            "error_type": "retries_exhausted",
            "flow_id": flow_id,
            "step_id": step_id,
            "step_mode": "inline" if _step.intent else "function",
            "agent": _step.agent,
            "message": f"Step '{step_id}' exhausted all retries",
            "violations": violations,
        }

    if status in ("ensure_failed", "schema_failed"):
        # Persist incremented attempts so retry budget survives an MCP server restart.
        # current_idx has not advanced — get_current_step_info returns the same step
        # with updated retries_remaining. Persist AFTER get_current_step_info in case
        # skip mutations occur on subsequent steps (consistent with stratum_plan ordering).
        try:
            step_info = get_current_step_info(state)
        except MCPExecutionError as exc:
            return {"status": "error", **exception_to_mcp_error(exc)}
        persist_flow(state)
        return {
            **step_info,
            "status": status,
            "violations": violations,
        }

    # "ok" — current_idx was advanced by process_step_result
    # Consume iteration outcome (ENG-5 will read before clearing)
    state.iteration_outcome.pop(step_id, None)
    try:
        next_step = get_current_step_info(state)
        next_step = _apply_policy_loop(state, next_step)
    except MCPExecutionError as exc:
        return {"status": "error", **exception_to_mcp_error(exc)}
    if next_step is not None and next_step.get("status") == "complete":
        delete_persisted_flow(flow_id)
        return next_step
    if next_step is None:
        # Flow complete — clean up persistence
        delete_persisted_flow(flow_id)
        total_ms = int((time.monotonic() - state.flow_start) * 1000)
        # Gate steps write no output; find the last step that actually produced one.
        output = next(
            (state.step_outputs[s.id] for s in reversed(state.ordered_steps)
             if s.id in state.step_outputs and state.step_outputs[s.id] is not None),
            None,
        )
        return {
            "status": state.terminal_status or "complete",
            "flow_id": state.flow_id,
            "output": output,
            "trace": [dataclasses.asdict(r) for r in state.records],
            "total_duration_ms": total_ms,
        }

    persist_flow(state)
    return next_step


@mcp.tool(description=(
    "Return execution trace for a flow. "
    "Input: flow_id (str) from stratum_plan. "
    "Returns step-by-step trace with attempt counts and durations."
))
async def stratum_audit(flow_id: str, ctx: Context) -> dict[str, Any]:
    state = _flows.get(flow_id)
    if state is None:
        state = restore_flow(flow_id)
        if state is None:
            return {
                "error_type": "flow_not_found",
                "message": f"No active flow with id '{flow_id}'",
            }
        _flows[flow_id] = state

    total_ms = int((time.monotonic() - state.flow_start) * 1000)
    is_complete = state.current_idx >= len(state.ordered_steps)

    if state.terminal_status == "killed":
        flow_status = "killed"
    elif is_complete:
        flow_status = "complete"
    else:
        flow_status = "in_progress"

    return {
        "flow_id": state.flow_id,
        "flow_name": state.flow_name,
        "status": flow_status,
        "steps_completed": len(state.records),
        "total_steps": len(state.ordered_steps),
        "trace": [dataclasses.asdict(r) for r in state.records],
        "total_duration_ms": total_ms,
        "round": state.round,
        # rounds: always present; each element is {"round": N, "steps": [...record dicts]}
        "rounds": [{"round": i, "steps": r} for i, r in enumerate(state.rounds)],
        # STRAT-ENG-4: per-step iteration history
        "iterations": state.iterations,
        "archived_iterations": state.archived_iterations,
    }


@mcp.tool(description=(
    "Resolve a gate step in a flow (IR v0.2). "
    "Inputs: flow_id (str), step_id (str, must be the current gate step), "
    "outcome (str: 'approve' | 'revise' | 'kill'), "
    "rationale (str, human-readable reason), "
    "resolved_by (str: 'human' | 'agent' | 'system'). "
    "approve routes to on_approve target (or completes the flow if null). "
    "revise archives the current round and routes to on_revise target. "
    "kill routes to on_kill target (or terminates the flow if null). "
    "Returns next step to execute, status: complete, or status: killed."
))
async def stratum_gate_resolve(
    flow_id: str,
    step_id: str,
    outcome: str,
    rationale: str,
    resolved_by: str,
    ctx: Context,
) -> dict[str, Any]:
    state = _flows.get(flow_id)
    if state is None:
        state = restore_flow(flow_id)
        if state is None:
            return {
                "status": "error",
                "error_type": "flow_not_found",
                "message": f"No active flow with id '{flow_id}'",
            }
        _flows[flow_id] = state

    # Reject if current step is not a gate step (before resolve_gate mutates state)
    if state.current_idx >= len(state.ordered_steps):
        return {
            "status": "error",
            "code": "flow_already_complete",
            "message": "Flow is already complete",
        }
    current_step = state.ordered_steps[state.current_idx]
    current_fn = state.spec.functions.get(current_step.function)
    if current_fn is None or current_fn.mode != "gate":
        return {
            "status": "error",
            "code": "not_a_gate_step",
            "message": f"Step '{current_step.id}' is not a gate step",
        }

    result_status, extra = resolve_gate(state, step_id, outcome, rationale, resolved_by)

    if result_status == "error":
        return {"status": "error", **extra}

    if result_status == "complete":
        delete_persisted_flow(flow_id)
        total_ms = int((time.monotonic() - state.flow_start) * 1000)
        output = next(
            (state.step_outputs[s.id] for s in reversed(state.ordered_steps)
             if s.id in state.step_outputs and state.step_outputs[s.id] is not None),
            None,
        )
        return {
            "status": "complete",
            "flow_id": flow_id,
            "output": output,
            "trace": [dataclasses.asdict(r) for r in state.records],
            "total_duration_ms": total_ms,
        }

    if result_status == "killed":
        delete_persisted_flow(flow_id)
        total_ms = int((time.monotonic() - state.flow_start) * 1000)
        return {
            "status": "killed",
            "flow_id": flow_id,
            "trace": [dataclasses.asdict(r) for r in state.records],
            "total_duration_ms": total_ms,
        }

    if result_status == "max_rounds_exceeded":
        # GateRecord was written to state.records but not archived; persist the updated state.
        persist_flow(state)
        return {"status": "error", **extra}

    # "execute_step" — route to the target step; persist AFTER get_current_step_info
    # in case the routed-to step has skip_if that fires (mutating state).
    next_step = get_current_step_info(state)
    next_step = _apply_policy_loop(state, next_step)
    if next_step is not None and next_step.get("status") == "complete":
        delete_persisted_flow(flow_id)
        return next_step
    persist_flow(state)
    return next_step


@mcp.tool(description=(
    "Check whether any pending gate step in a flow has exceeded its timeout (IR v0.2). "
    "Input: flow_id (str). "
    "If the current gate step has a timeout configured and the timeout has expired, "
    "fires an auto-kill with resolved_by: system following the same on_kill routing "
    "as an explicit kill outcome. "
    "Returns the same response shapes as stratum_gate_resolve: execute_step, killed, or "
    "status: no_timeout when no gate is pending or the timeout has not expired."
))
async def stratum_check_timeouts(flow_id: str, ctx: Context) -> dict[str, Any]:
    state = _flows.get(flow_id)
    if state is None:
        state = restore_flow(flow_id)
        if state is None:
            return {
                "status": "error",
                "error_type": "flow_not_found",
                "message": f"No active flow with id '{flow_id}'",
            }
        _flows[flow_id] = state

    if state.current_idx >= len(state.ordered_steps):
        return {"status": "no_timeout", "message": "Flow is already complete"}

    current_step = state.ordered_steps[state.current_idx]
    fn_def = state.spec.functions.get(current_step.function)

    if fn_def is None or fn_def.mode != "gate":
        return {"status": "no_timeout", "message": "Current step is not a gate step"}

    if fn_def.timeout is None:
        return {"status": "no_timeout", "message": "Gate has no timeout configured"}

    dispatched = state.dispatched_at.get(current_step.id)
    if dispatched is None:
        return {"status": "no_timeout", "message": "Gate not yet dispatched"}

    elapsed = time.time() - dispatched
    if elapsed < fn_def.timeout:
        return {
            "status": "no_timeout",
            "remaining_seconds": fn_def.timeout - elapsed,
        }

    # Timeout expired — auto-kill with resolved_by=system
    result_status, extra = resolve_gate(
        state, current_step.id, "kill", "timeout", "system"
    )

    if result_status == "error":
        return {"status": "error", **extra}

    if result_status == "killed":
        delete_persisted_flow(flow_id)
        total_ms = int((time.monotonic() - state.flow_start) * 1000)
        return {
            "status": "killed",
            "flow_id": flow_id,
            "reason": "timeout",
            "trace": [dataclasses.asdict(r) for r in state.records],
            "total_duration_ms": total_ms,
        }

    if result_status == "execute_step":
        next_step = get_current_step_info(state)  # may skip; persist after
        next_step = _apply_policy_loop(state, next_step)
        if next_step is not None and next_step.get("status") == "complete":
            delete_persisted_flow(flow_id)
            return next_step
        persist_flow(state)
        return next_step

    return {"status": "error", "message": f"Unexpected gate result: {result_status}"}


@mcp.tool(description=(
    "Explicitly skip the current step in a flow. "
    "Inputs: flow_id (str), step_id (str, must be the current step), "
    "reason (str, recorded in audit trail). "
    "Cannot skip gate steps — use stratum_gate_resolve instead. "
    "Returns next step to execute or flow completion."
))
async def stratum_skip_step(
    flow_id: str,
    step_id: str,
    reason: str,
    ctx: Context,
) -> dict[str, Any]:
    state = _flows.get(flow_id)
    if state is None:
        state = restore_flow(flow_id)
        if state is None:
            return {
                "status": "error",
                "error_type": "flow_not_found",
                "message": f"No active flow with id '{flow_id}'",
            }
        _flows[flow_id] = state

    try:
        skip_step(state, step_id, reason)
    except MCPExecutionError as exc:
        return {"status": "error", **exception_to_mcp_error(exc)}

    try:
        next_info = get_current_step_info(state)
        next_info = _apply_policy_loop(state, next_info)
    except MCPExecutionError as exc:
        return {"status": "error", **exception_to_mcp_error(exc)}

    if next_info is not None and next_info.get("status") == "complete":
        delete_persisted_flow(flow_id)
        return next_info
    if next_info is None:
        delete_persisted_flow(flow_id)
        total_ms = int((time.monotonic() - state.flow_start) * 1000)
        output = next(
            (state.step_outputs[s.id] for s in reversed(state.ordered_steps)
             if s.id in state.step_outputs and state.step_outputs[s.id] is not None),
            None,
        )
        return {
            "status": state.terminal_status or "complete",
            "flow_id": state.flow_id,
            "output": output,
            "trace": [dataclasses.asdict(r) for r in state.records],
            "total_duration_ms": total_ms,
        }

    persist_flow(state)
    return next_info


# ---------------------------------------------------------------------------
# Per-step iteration tools (STRAT-ENG-4)
# ---------------------------------------------------------------------------

@mcp.tool(description=(
    "Start an iteration loop on the current step. "
    "Inputs: flow_id (str), step_id (str, must be the current step). "
    "The step must have max_iterations defined in the spec. "
    "Returns iteration_started with max_iterations and exit_criterion."
))
async def stratum_iteration_start(
    flow_id: str,
    step_id: str,
    ctx: Context,
) -> dict[str, Any]:
    state = _flows.get(flow_id)
    if state is None:
        state = restore_flow(flow_id)
        if state is None:
            return {
                "status": "error",
                "error_type": "flow_not_found",
                "message": f"No active flow with id '{flow_id}'",
            }
        _flows[flow_id] = state

    try:
        result = start_iteration(state, step_id)
    except MCPExecutionError as exc:
        return {"status": "error", **exception_to_mcp_error(exc)}

    return result


@mcp.tool(description=(
    "Report one iteration result. Evaluates exit_criterion, increments count, "
    "checks max_iterations. "
    "Inputs: flow_id (str), step_id (str), result (dict). "
    "Returns iteration_continue or iteration_exit with outcome."
))
async def stratum_iteration_report(
    flow_id: str,
    step_id: str,
    result: dict[str, Any],
    ctx: Context,
) -> dict[str, Any]:
    state = _flows.get(flow_id)
    if state is None:
        state = restore_flow(flow_id)
        if state is None:
            return {
                "status": "error",
                "error_type": "flow_not_found",
                "message": f"No active flow with id '{flow_id}'",
            }
        _flows[flow_id] = state

    try:
        response = report_iteration(state, step_id, result)
    except MCPExecutionError as exc:
        return {"status": "error", **exception_to_mcp_error(exc)}

    return response


@mcp.tool(description=(
    "Abort an active iteration loop before completion. "
    "Inputs: flow_id (str), step_id (str), reason (str). "
    "Returns iteration_aborted with the current count."
))
async def stratum_iteration_abort(
    flow_id: str,
    step_id: str,
    reason: str,
    ctx: Context,
) -> dict[str, Any]:
    state = _flows.get(flow_id)
    if state is None:
        state = restore_flow(flow_id)
        if state is None:
            return {
                "status": "error",
                "error_type": "flow_not_found",
                "message": f"No active flow with id '{flow_id}'",
            }
        _flows[flow_id] = state

    try:
        response = abort_iteration(state, step_id, reason)
    except MCPExecutionError as exc:
        return {"status": "error", **exception_to_mcp_error(exc)}

    return response


@mcp.tool(description=(
    "Save a named checkpoint of the current flow state. "
    "Inputs: flow_id (str), label (str, e.g. 'after_analysis'). "
    "Snapshots step_outputs, attempts, records, and current_idx under the label. "
    "Call stratum_revert to roll back to this point if a later step fails."
))
async def stratum_commit(flow_id: str, label: str, ctx: Context) -> dict[str, Any]:
    state = _flows.get(flow_id)
    if state is None:
        state = restore_flow(flow_id)
        if state is None:
            return {
                "status": "error",
                "error_type": "flow_not_found",
                "message": f"No active flow with id '{flow_id}'",
            }
        _flows[flow_id] = state

    label = label.strip()
    if not label:
        return {
            "status": "error",
            "error_type": "invalid_label",
            "message": "label must be a non-empty string",
        }

    commit_checkpoint(state, label)
    is_complete = state.current_idx >= len(state.ordered_steps)
    current_step_id = (
        state.ordered_steps[state.current_idx].id
        if not is_complete
        else None
    )
    return {
        "status": "committed",
        "flow_id": flow_id,
        "label": label,
        "step_number": state.current_idx + 1,
        "current_step_id": current_step_id,
        "checkpoints": list(state.checkpoints.keys()),
    }


@mcp.tool(description=(
    "Roll back flow state to a previously committed checkpoint. "
    "Inputs: flow_id (str), label (str, must match a prior stratum_commit label). "
    "Restores step_outputs, attempts, records, and current_idx to the checkpoint. "
    "Returns the step to re-execute next, as if stratum_plan had just returned it."
))
async def stratum_revert(flow_id: str, label: str, ctx: Context) -> dict[str, Any]:
    label = label.strip()
    state = _flows.get(flow_id)
    if state is None:
        state = restore_flow(flow_id)
        if state is None:
            return {
                "status": "error",
                "error_type": "flow_not_found",
                "message": f"No active flow with id '{flow_id}'",
            }
        _flows[flow_id] = state

    if not revert_checkpoint(state, label):
        return {
            "status": "error",
            "error_type": "checkpoint_not_found",
            "message": f"No checkpoint '{label}' on flow '{flow_id}'",
            "available": list(state.checkpoints.keys()),
        }

    next_step = get_current_step_info(state)  # may skip steps, mutating state
    persist_flow(state)                        # persist AFTER skip mutations

    if next_step is None:
        # Reverted to a post-completion checkpoint — unusual but valid
        last_step = state.ordered_steps[-1]
        total_ms = int((time.monotonic() - state.flow_start) * 1000)
        return {
            "status": "complete",
            "flow_id": state.flow_id,
            "output": state.step_outputs.get(last_step.id),
            "trace": [dataclasses.asdict(r) for r in state.records],
            "total_duration_ms": total_ms,
        }

    return {**next_step, "reverted_to": label}


@mcp.tool(description=(
    "Compile a spec-kit tasks directory into a .stratum.yaml flow. "
    "Input: tasks_dir (str, path to a directory containing *.md task files), "
    "flow_name (str, optional, name for the generated flow, default 'tasks'). "
    "Returns {status, yaml, flow_name, steps} on success or {status, error_type, message} on error. "
    "Pass the returned yaml directly to stratum_plan to start execution."
))
async def stratum_compile_speckit(
    tasks_dir: str,
    ctx: Context,
    flow_name: str = "tasks",
) -> dict[str, Any]:
    from pathlib import Path as _Path
    from .task_compiler import parse_task_file, compile_tasks

    path = _Path(tasks_dir)
    if not path.is_dir():
        return {
            "status": "error",
            "error_type": "directory_not_found",
            "message": f"tasks_dir '{tasks_dir}' is not a directory",
        }

    try:
        # compile_tasks() discovers files, checks for step-ID collisions, and emits YAML.
        # Parse tasks separately so we can return the steps summary.
        task_files = sorted(path.glob("*.md"))
        tasks = [parse_task_file(f) for f in task_files]
        yaml_str = compile_tasks(path, flow_name)
    except ValueError as exc:
        # Covers: no task files found, step-ID collision
        error_type = "no_tasks" if "No task files" in str(exc) else "step_id_collision"
        return {
            "status": "error",
            "error_type": error_type,
            "message": str(exc),
        }
    except Exception as exc:
        return {
            "status": "error",
            "error_type": "compile_error",
            "message": str(exc),
        }

    return {
        "status": "ok",
        "yaml": yaml_str,
        "flow_name": flow_name,
        "steps": [
            {
                "id": t.step_id,
                "title": t.title,
                "parallel": t.is_parallel,
                "ensures": t.ensures,
                "judgment": t.judgment,
            }
            for t in tasks
        ],
    }


@mcp.tool(description=(
    "Push a pipeline draft to the PipelineEditor UI. "
    "The draft is written to {project_dir}/.stratum/pipeline-draft.json, "
    "which the PipelineEditor polls and will display automatically. "
    "Inputs: draft (dict) — pipeline draft with 'name' (str) and 'phases' (list of "
    "{name, capability, policy} objects where capability is scout|builder|critic and "
    "policy is gate|flag|skip). "
    "Optional: project_dir (str) — project root, defaults to CWD. "
    "Returns {status: 'saved', path: str} on success."
))
async def stratum_draft_pipeline(
    draft: dict[str, Any],
    ctx: Context,
    project_dir: str = ".",
) -> dict[str, Any]:
    from pathlib import Path as _Path

    path = _Path(project_dir).resolve()
    draft_path = path / ".stratum" / "pipeline-draft.json"
    draft_path.parent.mkdir(parents=True, exist_ok=True)

    # Ensure required fields are present
    if not isinstance(draft.get("name"), str) or not draft["name"]:
        draft["name"] = "my-pipeline"
    if not isinstance(draft.get("phases"), list):
        draft["phases"] = []

    import json as _json
    draft_path.write_text(_json.dumps(draft, indent=2))
    return {"status": "saved", "path": str(draft_path)}


@mcp.tool(description=(
    "List registered workflow specs from a directory. "
    "Scans for *.stratum.yaml files with a workflow: block. "
    "Returns {workflows: [{name, description, input, path}], errors: [str]}."
))
async def stratum_list_workflows(
    workflows_dir: str = ".",
    ctx: Context = None,
) -> dict[str, Any]:
    from pathlib import Path as _Path
    import yaml as _yaml

    root = _Path(workflows_dir).resolve()
    workflows: list[dict[str, Any]] = []
    errors: list[str] = []
    seen_names: dict[str, str] = {}  # name → first path

    for yaml_path in sorted(root.glob("*.stratum.yaml")):
        try:
            raw = yaml_path.read_text()
            spec = parse_and_validate(raw)
        except Exception as exc:
            errors.append(f"{yaml_path.name}: {exc}")
            continue

        if spec.workflow is None:
            continue

        name = spec.workflow.name
        path_str = str(yaml_path)

        if name in seen_names:
            errors.append(
                f"Duplicate workflow name '{name}': "
                f"{seen_names[name]} and {path_str}"
            )
            continue

        seen_names[name] = path_str
        workflows.append({
            "name": name,
            "description": spec.workflow.description,
            "input": spec.workflow.input_schema,
            "path": path_str,
        })

    return {"workflows": workflows, "errors": errors}


_CLAUDE_MD_MARKER = "## Stratum Execution Model"

_CLAUDE_MD_BLOCK = """
## Stratum Execution Model

For non-trivial tasks, use Stratum internally:
1. Write a `.stratum.yaml` spec — never show it to the user
2. Call `stratum_plan` to validate and get the first step
3. Narrate progress in plain English as you execute each step
4. Call `stratum_step_done` after each step — the server checks your work
5. If a step fails postconditions, fix it silently and retry
6. Call `stratum_audit` at the end and include the trace in the commit
"""


_HOOKS_DIR = Path(__file__).parent / "hooks"

# Maps Claude Code hook event → the stratum script that handles it.
_HOOK_SCRIPTS: dict[str, str] = {
    "SessionStart":       "stratum-session-start.sh",
    "Stop":               "stratum-session-stop.sh",
    "PostToolUseFailure": "stratum-post-tool-failure.sh",
}


def _install_hooks(root: Path, changed: list[str]) -> None:
    """Copy hook scripts to {root}/.claude/hooks/ and register them in settings.json."""
    import json

    hooks_dest = root / ".claude" / "hooks"
    hooks_dest.mkdir(parents=True, exist_ok=True)

    # Copy each script file, make executable
    for script_name in _HOOK_SCRIPTS.values():
        src = _HOOKS_DIR / script_name
        dst = hooks_dest / script_name
        if not src.exists():
            continue
        content = src.read_text()
        if dst.exists() and dst.read_text() == content:
            print(f"  .claude/hooks/{script_name}: already up to date — skipped")
        else:
            verb = "updated" if dst.exists() else "installed"
            dst.write_text(content)
            dst.chmod(0o755)
            print(f"  .claude/hooks/{script_name}: {verb}")
            changed.append(f".claude/hooks/{script_name}")

    # Register in .claude/settings.json
    settings_file = root / ".claude" / "settings.json"
    try:
        settings = json.loads(settings_file.read_text()) if settings_file.exists() else {}
    except (json.JSONDecodeError, OSError):
        settings = {}

    hooks_cfg: dict = settings.setdefault("hooks", {})
    registered_any = False

    for event, script_name in _HOOK_SCRIPTS.items():
        command = f"bash .claude/hooks/{script_name}"
        event_hooks: list = hooks_cfg.setdefault(event, [])
        # Check if our command is already present under this event
        already = any(
            any(h.get("command") == command for h in entry.get("hooks", []))
            for entry in event_hooks
        )
        if already:
            print(f"  settings.json hooks.{event}: stratum entry already present — skipped")
        else:
            event_hooks.append({"hooks": [{"type": "command", "command": command}]})
            registered_any = True

    if registered_any:
        settings_file.write_text(json.dumps(settings, indent=2) + "\n")
        print("  .claude/settings.json: registered Stratum hooks")
        changed.append(".claude/settings.json")
    else:
        print("  .claude/settings.json: Stratum hooks already registered — skipped")


def _remove_hooks(root: Path, removed: list[str]) -> None:
    """Remove hook scripts and their settings.json entries written by setup."""
    import json

    # Remove script files
    hooks_dest = root / ".claude" / "hooks"
    for script_name in _HOOK_SCRIPTS.values():
        dst = hooks_dest / script_name
        if dst.exists():
            dst.unlink()
            print(f"  .claude/hooks/{script_name}: removed")
            removed.append(f".claude/hooks/{script_name}")
        else:
            print(f"  .claude/hooks/{script_name}: not found — skipped")

    # Remove entries from .claude/settings.json
    settings_file = root / ".claude" / "settings.json"
    if not settings_file.exists():
        print("  .claude/settings.json: not found — skipped")
        return
    try:
        settings = json.loads(settings_file.read_text())
    except (json.JSONDecodeError, OSError):
        print("  .claude/settings.json: could not parse — skipped")
        return

    hooks_cfg = settings.get("hooks", {})
    changed = False
    for event, script_name in _HOOK_SCRIPTS.items():
        command = f"bash .claude/hooks/{script_name}"
        if event not in hooks_cfg:
            continue
        before = len(hooks_cfg[event])
        hooks_cfg[event] = [
            entry for entry in hooks_cfg[event]
            if not any(h.get("command") == command for h in entry.get("hooks", []))
        ]
        if len(hooks_cfg[event]) < before:
            changed = True
        if not hooks_cfg[event]:
            del hooks_cfg[event]

    if not hooks_cfg:
        settings.pop("hooks", None)

    if changed:
        if settings:
            settings_file.write_text(json.dumps(settings, indent=2) + "\n")
        else:
            settings_file.unlink()
        print("  .claude/settings.json: removed Stratum hook entries")
        removed.append(".claude/settings.json")
    else:
        print("  .claude/settings.json: no Stratum hook entries found — skipped")


def _cmd_setup() -> None:
    """Write .claude/mcp.json and append Stratum block to CLAUDE.md."""
    import json
    from pathlib import Path

    # Walk up from cwd to find project root (nearest .git or CLAUDE.md)
    root = Path.cwd()
    for candidate in [root, *root.parents]:
        if (candidate / ".git").exists() or (candidate / "CLAUDE.md").exists():
            root = candidate
            break

    changed: list[str] = []

    # --- .claude/mcp.json ---
    mcp_dir = root / ".claude"
    mcp_file = mcp_dir / "mcp.json"

    if mcp_file.exists():
        try:
            config = json.loads(mcp_file.read_text())
        except (json.JSONDecodeError, OSError):
            config = {}
        servers = config.setdefault("mcpServers", {})
        if "stratum" in servers:
            print(f"  {mcp_file.relative_to(root)}: stratum already present — skipped")
        else:
            servers["stratum"] = {"command": "stratum-mcp"}
            mcp_file.write_text(json.dumps(config, indent=2) + "\n")
            print(f"  {mcp_file.relative_to(root)}: added stratum server")
            changed.append(str(mcp_file.relative_to(root)))
    else:
        mcp_dir.mkdir(parents=True, exist_ok=True)
        config = {"mcpServers": {"stratum": {"command": "stratum-mcp"}}}
        mcp_file.write_text(json.dumps(config, indent=2) + "\n")
        print(f"  {mcp_file.relative_to(root)}: created")
        changed.append(str(mcp_file.relative_to(root)))

    # --- CLAUDE.md ---
    claude_md = root / "CLAUDE.md"

    if claude_md.exists():
        content = claude_md.read_text()
        if _CLAUDE_MD_MARKER in content:
            print("  CLAUDE.md: Stratum section already present — skipped")
        else:
            claude_md.write_text(content.rstrip() + "\n" + _CLAUDE_MD_BLOCK)
            print("  CLAUDE.md: added Stratum section")
            changed.append("CLAUDE.md")
    else:
        claude_md.write_text(_CLAUDE_MD_BLOCK.lstrip())
        print("  CLAUDE.md: created")
        changed.append("CLAUDE.md")

    # --- Skills ---
    skills_home = Path.home() / ".claude" / "skills"
    pkg_skills = Path(__file__).parent / "skills"
    if pkg_skills.is_dir():
        for skill_dir in sorted(pkg_skills.iterdir()):
            if not skill_dir.is_dir():
                continue
            src = skill_dir / "SKILL.md"
            if not src.exists():
                continue
            dest_dir = skills_home / skill_dir.name
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest = dest_dir / "SKILL.md"
            content = src.read_text()
            if dest.exists() and dest.read_text() == content:
                print(f"  ~/.claude/skills/{skill_dir.name}: already up to date — skipped")
            else:
                dest.write_text(content)
                verb = "updated" if dest.exists() else "installed"
                print(f"  ~/.claude/skills/{skill_dir.name}: {verb}")
                changed.append(f"skills/{skill_dir.name}")

    # --- Hooks ---
    _install_hooks(root, changed)

    if changed:
        print("\nDone. Restart Claude Code to activate the Stratum MCP server.")
    else:
        print("\nAlready configured — nothing to do.")


def _cmd_uninstall(keep_skills: bool = False) -> None:
    """Remove Stratum config from the project and optionally from ~/.claude/skills/."""
    import json
    from pathlib import Path

    root = Path.cwd()
    for candidate in [root, *root.parents]:
        if (candidate / ".git").exists() or (candidate / "CLAUDE.md").exists():
            root = candidate
            break

    removed: list[str] = []

    # --- .claude/mcp.json ---
    mcp_file = root / ".claude" / "mcp.json"
    if mcp_file.exists():
        try:
            config = json.loads(mcp_file.read_text())
            servers = config.get("mcpServers", {})
            if "stratum" in servers:
                del servers["stratum"]
                if servers:
                    mcp_file.write_text(json.dumps(config, indent=2) + "\n")
                else:
                    # No servers left — remove the file entirely
                    mcp_file.unlink()
                print(f"  {mcp_file.relative_to(root)}: removed stratum server")
                removed.append(str(mcp_file.relative_to(root)))
            else:
                print(f"  {mcp_file.relative_to(root)}: stratum not present — skipped")
        except (json.JSONDecodeError, OSError):
            print(f"  {mcp_file.relative_to(root)}: could not parse — skipped")
    else:
        print("  .claude/mcp.json: not found — skipped")

    # --- CLAUDE.md ---
    claude_md = root / "CLAUDE.md"
    if claude_md.exists():
        content = claude_md.read_text()
        if _CLAUDE_MD_MARKER in content:
            # Remove the marker line and everything after it that belongs to our block
            idx = content.find(_CLAUDE_MD_MARKER)
            new_content = content[:idx].rstrip()
            if new_content:
                claude_md.write_text(new_content + "\n")
            else:
                claude_md.unlink()
            print("  CLAUDE.md: removed Stratum section")
            removed.append("CLAUDE.md")
        else:
            print("  CLAUDE.md: Stratum section not present — skipped")
    else:
        print("  CLAUDE.md: not found — skipped")

    # --- Skills ---
    if keep_skills:
        print("  ~/.claude/skills/stratum-*: kept (--keep-skills)")
    else:
        skills_home = Path.home() / ".claude" / "skills"
        pkg_skills = Path(__file__).parent / "skills"
        if pkg_skills.is_dir():
            for skill_dir in sorted(pkg_skills.iterdir()):
                if not skill_dir.is_dir():
                    continue
                dest = skills_home / skill_dir.name / "SKILL.md"
                dest_dir = skills_home / skill_dir.name
                if dest.exists():
                    dest.unlink()
                    # Remove the directory if now empty
                    try:
                        dest_dir.rmdir()
                    except OSError:
                        pass
                    print(f"  ~/.claude/skills/{skill_dir.name}: removed")
                    removed.append(f"skills/{skill_dir.name}")
                else:
                    print(f"  ~/.claude/skills/{skill_dir.name}: not found — skipped")

    # --- Hooks ---
    _remove_hooks(root, removed)

    if removed:
        print("\nDone. Restart Claude Code to deactivate the Stratum MCP server.")
    else:
        print("\nNothing to remove — Stratum was not configured here.")


def _cmd_compile(tasks_dir: str, args: list[str]) -> None:
    """Compile tasks/*.md into .stratum.yaml and write to stdout or file."""
    from .task_compiler import compile_tasks

    if not tasks_dir:
        print(
            "Usage: stratum-mcp compile <tasks_dir> [--output <file>] [--flow <name>]",
            file=sys.stderr,
        )
        sys.exit(1)

    path = Path(tasks_dir)
    if not path.is_dir():
        print(f"ERROR: '{tasks_dir}' is not a directory", file=sys.stderr)
        sys.exit(1)

    output_file: str | None = None
    flow_name = "tasks"
    i = 0
    while i < len(args):
        if args[i] == "--output" and i + 1 < len(args):
            output_file = args[i + 1]
            i += 2
        elif args[i] == "--flow" and i + 1 < len(args):
            flow_name = args[i + 1]
            i += 2
        else:
            i += 1

    try:
        yaml_content = compile_tasks(path, flow_name)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    if output_file:
        Path(output_file).write_text(yaml_content)
        print(f"Written to {output_file}")
    else:
        print(yaml_content, end="")


def _cmd_validate(arg: str) -> None:
    yaml_content = arg
    if arg and "\n" not in arg and not arg.lstrip().startswith("version:"):
        try:
            with open(arg) as f:
                yaml_content = f.read()
        except FileNotFoundError:
            pass  # no file at that path — treat the string as inline YAML
        except OSError as exc:
            print(f"ERROR: cannot open '{arg}': {exc}", file=sys.stderr)
            sys.exit(1)
    try:
        parse_and_validate(yaml_content)
        print("OK")
        sys.exit(0)
    except Exception as exc:
        err = exception_to_mcp_error(exc)
        print(f"ERROR [{err['error_type']}]: {err['message']}", file=sys.stderr)
        sys.exit(1)



# ---------------------------------------------------------------------------
# query / gate helpers
# ---------------------------------------------------------------------------

def _flow_status(state: Any) -> str:
    """Derive a human-readable status string from a FlowState."""
    if state.terminal_status == "killed":
        return "killed"
    if state.current_idx >= len(state.ordered_steps):
        return "complete"
    step = state.ordered_steps[state.current_idx]
    fn_def = state.spec.functions.get(step.function)
    if fn_def and fn_def.mode == "gate":
        return "awaiting_gate"
    return "running"


def _query_flows() -> list[dict]:
    from .executor import _FLOWS_DIR, restore_flow
    if not _FLOWS_DIR.exists():
        return []
    results = []
    for path in sorted(_FLOWS_DIR.glob("*.json")):
        state = restore_flow(path.stem)
        if state is None:
            continue
        current = state.ordered_steps[state.current_idx] if state.current_idx < len(state.ordered_steps) else None
        results.append({
            "_schema_version": "1",
            "flow_id":         state.flow_id,
            "flow_name":       state.flow_name,
            "status":          _flow_status(state),
            "current_step_id": current.id if current else None,
            "round":           state.round,
            "step_count":      len(state.ordered_steps),
            "completed_steps": state.current_idx,
            "terminal_status": state.terminal_status,
        })
    return results


def _query_flow(flow_id: str) -> dict:
    from .executor import restore_flow
    state = restore_flow(flow_id)
    if state is None:
        print(json.dumps({"error": {"code": "NOT_FOUND", "message": f"Flow '{flow_id}' not found"}}))
        sys.exit(1)
    current = state.ordered_steps[state.current_idx] if state.current_idx < len(state.ordered_steps) else None
    return {
        "_schema_version": "1",
        "flow_id":          state.flow_id,
        "flow_name":        state.flow_name,
        "status":           _flow_status(state),
        "current_step_id":  current.id if current else None,
        "current_idx":      state.current_idx,
        "round":            state.round,
        "rounds_count":     len(state.rounds),
        "step_count":       len(state.ordered_steps),
        "terminal_status":  state.terminal_status,
        "step_outputs":     state.step_outputs,
        "records":          [dataclasses.asdict(r) for r in state.records],
        "rounds":           state.rounds,
        "ordered_steps":    [
            {
                "id":       s.id,
                "function": s.function,
                # Normalize: consumers only need gate vs. non-gate
                "mode":     "gate"
                            if s.function in state.spec.functions
                               and state.spec.functions[s.function].mode == "gate"
                            else "step",
            }
            for s in state.ordered_steps
        ],
    }


def _query_gates() -> list[dict]:
    from .executor import _FLOWS_DIR, restore_flow
    if not _FLOWS_DIR.exists():
        return []
    gates = []
    for path in sorted(_FLOWS_DIR.glob("*.json")):
        state = restore_flow(path.stem)
        if state is None or state.current_idx >= len(state.ordered_steps):
            continue
        step = state.ordered_steps[state.current_idx]
        fn_def = state.spec.functions.get(step.function)
        if not fn_def or fn_def.mode != "gate":
            continue
        gates.append({
            "_schema_version": "1",
            "flow_id":    state.flow_id,
            "flow_name":  state.flow_name,
            "step_id":    step.id,
            "function":   step.function,
            "on_approve": step.on_approve,
            "on_revise":  step.on_revise,
            "on_kill":    step.on_kill,
            "timeout":    fn_def.timeout,
        })
    return gates


# ---------------------------------------------------------------------------
# CLI subcommands: query, gate
# ---------------------------------------------------------------------------

def _cmd_query(args: list[str]) -> None:
    import argparse
    parser = argparse.ArgumentParser(prog="stratum-mcp query")
    sub = parser.add_subparsers(dest="resource", required=True)
    sub.add_parser("flows", help="List all persisted flows")
    flow_p = sub.add_parser("flow", help="Full state for a single flow")
    flow_p.add_argument("flow_id")
    sub.add_parser("gates", help="List all pending gate steps")
    parsed = parser.parse_args(args)

    if parsed.resource == "flows":
        result = _query_flows()
    elif parsed.resource == "flow":
        result = _query_flow(parsed.flow_id)   # exits on NOT_FOUND
    else:
        result = _query_gates()

    print(json.dumps(result, indent=2))


def _cmd_gate(args: list[str]) -> None:
    import argparse
    from .executor import restore_flow, persist_flow, resolve_gate

    parser = argparse.ArgumentParser(prog="stratum-mcp gate")
    sub = parser.add_subparsers(dest="action", required=True)
    for action in ("approve", "reject", "revise"):
        p = sub.add_parser(action)
        p.add_argument("flow_id")
        p.add_argument("step_id")
        p.add_argument("--note", default="", help="Rationale or review note")
        p.add_argument(
            "--resolved-by", default="human",
            choices=["human", "agent", "system"],
            dest="resolved_by",
        )
    parsed = parser.parse_args(args)

    # Map CLI actions to stratum gate outcomes
    outcome_map = {"approve": "approve", "reject": "kill", "revise": "revise"}
    outcome = outcome_map[parsed.action]

    state = restore_flow(parsed.flow_id)
    if state is None:
        print(json.dumps({
            "error": {"code": "NOT_FOUND", "message": f"Flow '{parsed.flow_id}' not found"},
        }))
        sys.exit(1)

    status, extra = resolve_gate(
        state,
        step_id=parsed.step_id,
        outcome=outcome,
        rationale=parsed.note,
        resolved_by=parsed.resolved_by,
    )

    if status == "error":
        # Idempotency conflicts: gate already resolved (flow moved past it)
        conflict_codes = {"flow_already_complete", "wrong_step"}
        if extra.get("code") in conflict_codes:
            print(json.dumps({
                "conflict": True,
                "flow_id":  parsed.flow_id,
                "step_id":  parsed.step_id,
                "detail":   extra.get("message", ""),
            }))
            sys.exit(2)
        # Other domain errors (bad step id, invalid state, etc.)
        print(json.dumps({
            "error": {"code": extra.get("code", "INVALID"), "message": extra.get("message", "")},
        }))
        sys.exit(1)

    # All non-error outcomes (complete, killed, execute_step, max_rounds_exceeded) persist state
    persist_flow(state)
    print(json.dumps({
        "_schema_version": "1",
        "ok":      True,
        "flow_id": parsed.flow_id,
        "step_id": parsed.step_id,
        "outcome": outcome,
        "result":  status,
    }))


def _cmd_help() -> None:
    print("Usage: stratum-mcp <command> [options]")
    print()
    print("Commands:")
    print("  install              Register MCP server and skills with Claude Code")
    print("  uninstall            Remove MCP server registration and skills")
    print("  query flows          List all persisted flows (JSON)")
    print("  query flow <id>      Full state for a single flow (JSON)")
    print("  query gates          List all pending gate steps (JSON)")
    print("  gate approve <flow_id> <step_id>   Approve a gate")
    print("  gate reject  <flow_id> <step_id>   Reject (kill) a gate")
    print("  gate revise  <flow_id> <step_id>   Send back for revision")
    print("  validate <file>      Validate a .stratum.yaml spec file")
    print("  compile <dir>        Compile tasks/*.md files to .stratum.yaml")
    print()
    print("Run with no arguments to start the stdio MCP server (for Claude Code).")


def main() -> None:
    """Entry point: CLI subcommands or stdio MCP server."""
    if len(sys.argv) >= 2:
        cmd = sys.argv[1]
        if cmd in ("-h", "--help", "help"):
            _cmd_help()
            return
        if cmd == "install":
            _cmd_setup()
            return
        if cmd == "uninstall":
            keep = "--keep-skills" in sys.argv[2:]
            _cmd_uninstall(keep_skills=keep)
            return
        if cmd == "validate":
            _cmd_validate(sys.argv[2] if len(sys.argv) > 2 else "")
            return
        if cmd == "compile":
            _cmd_compile(sys.argv[2] if len(sys.argv) > 2 else "", sys.argv[3:])
            return
        if cmd == "query":
            _cmd_query(sys.argv[2:])
            return
        if cmd == "gate":
            _cmd_gate(sys.argv[2:])
            return
        print(f"Unknown command: {cmd}", file=sys.stderr)
        print("Run 'stratum-mcp --help' for usage.", file=sys.stderr)
        sys.exit(1)

    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
