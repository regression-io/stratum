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

    if status in ("ensure_failed", "schema_failed"):
        # current_idx has not advanced — get_current_step_info returns the same step
        # with updated retries_remaining
        step_info = get_current_step_info(state)
        return {
            **step_info,
            "status": status,
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
    import importlib.resources
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

    if removed:
        print("\nDone. Restart Claude Code to deactivate the Stratum MCP server.")
    else:
        print("\nNothing to remove — Stratum was not configured here.")


def _cmd_validate(arg: str) -> None:
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


def main() -> None:
    """Entry point: CLI subcommands or stdio MCP server."""
    if len(sys.argv) >= 2:
        cmd = sys.argv[1]
        if cmd == "setup":
            _cmd_setup()
            return
        if cmd == "uninstall":
            keep = "--keep-skills" in sys.argv[2:]
            _cmd_uninstall(keep_skills=keep)
            return
        if cmd == "validate":
            _cmd_validate(sys.argv[2] if len(sys.argv) > 2 else "")
            return

    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
