"""FastMCP server entry point. MCP controller: plan management, step tracking, audit."""
from __future__ import annotations

import dataclasses
import sys
import time
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP, Context

from .errors import IRParseError, IRValidationError, IRSemanticError, MCPExecutionError, exception_to_mcp_error
from .executor import (
    FlowState,
    create_flow_state,
    get_current_step_info,
    process_step_result,
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
        state = create_flow_state(ir_spec, flow, inputs, raw_spec=spec)
    except MCPExecutionError as exc:
        return {"status": "error", **exception_to_mcp_error(exc)}

    _flows[state.flow_id] = state
    persist_flow(state)
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
        state = restore_flow(flow_id)
        if state is None:
            return {
                "status": "error",
                "error_type": "flow_not_found",
                "message": f"No active flow with id '{flow_id}'",
            }
        _flows[flow_id] = state

    try:
        status, violations = process_step_result(state, step_id, result)
    except MCPExecutionError as exc:
        return {"status": "error", **exception_to_mcp_error(exc)}

    if status == "retries_exhausted":
        delete_persisted_flow(flow_id)
        return {
            "status": "error",
            "error_type": "retries_exhausted",
            "flow_id": flow_id,
            "step_id": step_id,
            "message": f"Step '{step_id}' exhausted all retries",
            "violations": violations,
        }

    if status in ("ensure_failed", "schema_failed"):
        # Persist incremented attempts so retry budget survives an MCP server restart.
        # current_idx has not advanced — get_current_step_info returns the same step
        # with updated retries_remaining.
        persist_flow(state)
        step_info = get_current_step_info(state)
        return {
            **step_info,
            "status": status,
            "violations": violations,
        }

    # "ok" — current_idx was advanced by process_step_result
    next_step = get_current_step_info(state)
    if next_step is None:
        # Flow complete — clean up persistence
        delete_persisted_flow(flow_id)
        last_step = state.ordered_steps[-1]
        total_ms = int((time.monotonic() - state.flow_start) * 1000)
        return {
            "status": "complete",
            "flow_id": state.flow_id,
            "output": state.step_outputs.get(last_step.id),
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

    return {
        "flow_id": state.flow_id,
        "flow_name": state.flow_name,
        "status": "complete" if is_complete else "in_progress",
        "steps_completed": len(state.records),
        "total_steps": len(state.ordered_steps),
        "trace": [dataclasses.asdict(r) for r in state.records],
        "total_duration_ms": total_ms,
    }


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

    next_step = get_current_step_info(state)
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


def _cmd_serve(args: list[str]) -> None:
    import argparse
    from .serve import run_serve

    parser = argparse.ArgumentParser(prog="stratum-mcp serve")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=7821)
    parser.add_argument("--token", default=None)
    parser.add_argument("--project-dir", default=".")
    parser.add_argument("--tls-cert", default=None, metavar="PATH", help="TLS certificate file (PEM)")
    parser.add_argument("--tls-key", default=None, metavar="PATH", help="TLS private key file (PEM)")
    parsed = parser.parse_args(args)

    host = parsed.host
    token = parsed.token
    # Security invariant: refuse non-loopback without token
    loopback = {"127.0.0.1", "localhost", "::1"}
    if host not in loopback and not token:
        print("ERROR: non-loopback --host requires --token. Refusing to start.", file=sys.stderr)
        sys.exit(1)

    run_serve(
        host=host,
        port=parsed.port,
        token=token,
        project_dir=Path(parsed.project_dir),
        tls_cert=parsed.tls_cert,
        tls_key=parsed.tls_key,
    )


def _cmd_help() -> None:
    print("Usage: stratum-mcp <command> [options]")
    print()
    print("Commands:")
    print("  install              Register MCP server and skills with Claude Code")
    print("  uninstall            Remove MCP server registration and skills")
    print("  serve                Start the JSON API server (stratum-mcp serve --help)")
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
        if cmd == "serve":
            _cmd_serve(sys.argv[2:])
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
        print(f"Unknown command: {cmd}", file=sys.stderr)
        print("Run 'stratum-mcp --help' for usage.", file=sys.stderr)
        sys.exit(1)

    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
