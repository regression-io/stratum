"""FastMCP server entry point. MCP controller: plan management, step tracking, audit."""
from __future__ import annotations

import dataclasses
import sys
import time
from typing import Any

from mcp.server.fastmcp import FastMCP, Context

from .errors import IRParseError, IRValidationError, IRSemanticError, MCPExecutionError, exception_to_mcp_error
from .executor import FlowState, create_flow_state, get_current_step_info, process_step_result
from .spec import parse_and_validate

mcp = FastMCP(
    "stratum-mcp",
    instructions=(
        "Stratum execution controller for Claude Code. "
        "Validates .stratum.yaml IR specs, manages flow execution state, "
        "and tracks step results with ensure postcondition enforcement."
    ),
)

# In-memory flow state for the session lifetime.
_flows: dict[str, FlowState] = {}


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
        state = create_flow_state(ir_spec, flow, inputs)
    except MCPExecutionError as exc:
        return {"status": "error", **exception_to_mcp_error(exc)}

    _flows[state.flow_id] = state
    return get_current_step_info(state)  # always non-None: schema enforces minItems: 1


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
        return {
            "status": "error",
            "error_type": "flow_not_found",
            "message": f"No active flow with id '{flow_id}'",
        }

    try:
        status, violations = process_step_result(state, step_id, result)
    except MCPExecutionError as exc:
        return {"status": "error", **exception_to_mcp_error(exc)}

    if status == "retries_exhausted":
        return {
            "status": "error",
            "error_type": "retries_exhausted",
            "flow_id": flow_id,
            "step_id": step_id,
            "message": f"Step '{step_id}' exhausted all retries",
            "violations": violations,
        }

    if status == "ensure_failed":
        # current_idx has not advanced — get_current_step_info returns the same step
        # with updated retries_remaining
        step_info = get_current_step_info(state)
        return {
            **step_info,
            "status": "ensure_failed",
            "violations": violations,
        }

    # "ok" — current_idx was advanced by process_step_result
    next_step = get_current_step_info(state)
    if next_step is None:
        # Flow complete
        last_step = state.ordered_steps[-1]
        total_ms = int((time.monotonic() - state.flow_start) * 1000)
        return {
            "status": "complete",
            "flow_id": state.flow_id,
            "output": state.step_outputs.get(last_step.id),
            "trace": [dataclasses.asdict(r) for r in state.records],
            "total_duration_ms": total_ms,
        }

    return next_step


@mcp.tool(description=(
    "Return execution trace for a flow. "
    "Input: flow_id (str) from stratum_plan. "
    "Returns step-by-step trace with attempt counts and durations."
))
async def stratum_audit(flow_id: str, ctx: Context) -> dict[str, Any]:
    state = _flows.get(flow_id)
    if state is None:
        return {
            "error_type": "flow_not_found",
            "message": f"No active flow with id '{flow_id}'",
        }

    total_ms = int((time.monotonic() - state.flow_start) * 1000)
    is_complete = state.current_idx >= len(state.ordered_steps)

    return {
        "flow_id": state.flow_id,
        "flow_name": state.flow_name,
        "status": "complete" if is_complete else "in_progress",
        "steps_completed": len(state.records),
        "total_steps": len(state.ordered_steps),
        "trace": [dataclasses.asdict(r) for r in state.records],
        "total_duration_ms": total_ms,
    }


def main() -> None:
    """Entry point: CLI mode if called with 'validate'; stdio MCP server otherwise."""
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
