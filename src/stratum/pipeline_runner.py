"""Pipeline runtime — drives a @pipeline class through its phases."""

from __future__ import annotations

import asyncio
import dataclasses
import json
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Literal

from .connector import Connector, RunOpts
from .exceptions import StratumError
from .pipeline import PhaseSpec, PipelineDefinition
from .pipeline_types import Capability, Policy, is_named_assertion
from .project_config import StratumConfig
from .run_workspace import RunWorkspace


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

@dataclasses.dataclass
class PhaseRecord:
    """Execution record for a single phase in a completed pipeline run."""

    name:        str
    status:      Literal["complete", "skipped", "failed", "rejected"]
    duration_ms: int
    result:      dict[str, Any] | None = None
    error:       str | None = None


@dataclasses.dataclass
class PipelineResult:
    """Return value from ``run_pipeline()``."""

    run_id:      str
    status:      Literal["complete", "failed", "rejected"]
    phases:      dict[str, PhaseRecord]
    duration_ms: int
    workspace:   RunWorkspace


# ---------------------------------------------------------------------------
# Ensure evaluation
# ---------------------------------------------------------------------------

def _eval_assertion(
    expr: str,
    result: dict[str, Any],
    working_dir: Path,
) -> bool:
    """
    Evaluate a single ensure expression against a phase result.

    Named assertions are evaluated structurally. Arbitrary expressions are
    evaluated via Python ``eval`` with a restricted set of builtins.
    """
    stripped = expr.strip()

    # -- bare named assertions -----------------------------------------------
    _BARE: dict[str, Any] = {
        "tests_pass":    lambda r: bool(r.get("tests_pass")),
        "lint_clean":    lambda r: bool(r.get("lint_clean")),
        "files_changed": lambda r: bool(r.get("changed_files")),
        "approved":      lambda r: bool(r.get("approved")),
        "no_issues":     lambda r: not r.get("issues"),
    }
    if stripped in _BARE:
        return _BARE[stripped](result)

    # -- builtins available in all expressions (named and arbitrary) ---------
    def _file_exists(path: str) -> bool:
        p = Path(path)
        target = working_dir / p if not p.is_absolute() else p
        return target.exists()

    def _file_contains(path: str, substr: str) -> bool:
        p = Path(path)
        target = working_dir / p if not p.is_absolute() else p
        try:
            return substr in target.read_text()
        except OSError:
            return False

    safe_builtins: dict[str, Any] = {
        "file_exists":   _file_exists,
        "file_contains": _file_contains,
        "len":  len,
        "bool": bool,
        "int":  int,
        "str":  str,
    }

    # Strip envelope fields (underscore-prefixed) for attribute access
    result_ns = SimpleNamespace(
        **{k: v for k, v in result.items() if not k.startswith("_")}
    )

    try:
        return bool(eval(stripped, {"__builtins__": safe_builtins, "result": result_ns}))
    except Exception:
        return False


def _evaluate_ensures(
    ensures: tuple[str, ...],
    result: dict[str, Any],
    working_dir: Path,
) -> list[str]:
    """Return a list of ensure expressions that evaluated to False."""
    return [e for e in ensures if not _eval_assertion(e, result, working_dir)]


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------

def _build_prompt(
    phase:           PhaseSpec,
    pipeline_inputs: dict[str, Any],
    prior_outputs:   dict[str, dict[str, Any]],
) -> str:
    """Construct the agent prompt for a phase."""
    parts: list[str] = [f"## Task: {phase.intent}"]

    if pipeline_inputs:
        parts.append(
            "## Pipeline Inputs\n```json\n"
            + json.dumps(pipeline_inputs, indent=2)
            + "\n```"
        )

    for phase_name, output in prior_outputs.items():
        # Omit envelope fields (underscore-prefixed) from injected context
        user_output = {k: v for k, v in output.items() if not k.startswith("_")}
        parts.append(
            f"## Output from '{phase_name}'\n```json\n"
            + json.dumps(user_output, indent=2)
            + "\n```"
        )

    if phase.ensures:
        parts.append(
            "## Required postconditions\n"
            + "\n".join(f"- {e}" for e in phase.ensures)
        )

    parts.append("## Response format\nReturn a JSON object with your results.")
    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# Gate polling
# ---------------------------------------------------------------------------

async def _wait_for_gate(
    ws:             RunWorkspace,
    phase_name:     str,
    poll_interval_s: float,
) -> None:
    """
    Poll until the gate for ``phase_name`` is explicitly approved or rejected.

    Only an approval (``.gate.approved``) or rejection (``.gate.rejected``)
    file resolves the gate. Deleting the ``.gate`` file without writing either
    response file is treated as a fault, not an implicit approval.

    Raises:
        StratumError: If the gate is rejected or the gate file disappears
                      without an explicit approval or rejection.
    """
    while True:
        if ws.is_gate_approved(phase_name):
            return
        if ws.is_gate_rejected(phase_name):
            raise StratumError(
                f"Phase '{phase_name}' was rejected at the gate"
            )
        if not ws.gate_path(phase_name).exists():
            raise StratumError(
                f"Gate file for phase '{phase_name}' was removed without an "
                f"explicit approval or rejection; call approve_gate() or "
                f"reject_gate() to resolve a gate"
            )
        await asyncio.sleep(poll_interval_s)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

async def run_pipeline(
    pipeline_class: type,
    connector: Connector,
    inputs: dict[str, Any] | None = None,
    *,
    run_id: str | None = None,
    working_dir: Path | str = ".",
    config: StratumConfig | None = None,
    poll_interval_s: float = 2.0,
) -> PipelineResult:
    """
    Drive a ``@pipeline`` class to completion using ``connector``.

    Args:
        pipeline_class:  A class decorated with ``@pipeline``.
        connector:       Agent connector. Must support all capability tiers
                         used by the pipeline's phases.
        inputs:          Pipeline-level inputs (e.g. ``{"feature": "..."}``).
        run_id:          Resume an existing run by ID. ``None`` creates a new run.
        working_dir:     Project root. Used as the ``RunWorkspace`` root and
                         passed to ``RunOpts`` for file-aware operations.
        config:          ``stratum.toml`` config. Loaded from ``./stratum.toml``
                         if ``None``.
        poll_interval_s: Seconds between gate-file polls (default 2s).

    Returns:
        PipelineResult with status, per-phase records, and the run workspace.

    Raises:
        StratumError: On unsupported capability, gate rejection, or phase failure
                      after all retries are exhausted.
        AttributeError: If ``pipeline_class`` is not decorated with ``@pipeline``.
    """
    defn: PipelineDefinition = pipeline_class._pipeline_def
    working_dir = Path(working_dir)
    inputs      = inputs or {}
    config      = config or StratumConfig.load(working_dir / "stratum.toml")

    # -- validate connector capability coverage up front --------------------
    for phase in defn.phases:
        if not connector.supports(phase.capability):
            raise StratumError(
                f"Connector does not support capability '{phase.capability}' "
                f"required by phase '{phase.name}'"
            )

    # -- open or create workspace -------------------------------------------
    if run_id is not None:
        run_dir = working_dir / ".stratum" / "runs" / run_id
        ws = RunWorkspace.open(run_dir)
        if ws.pipeline_name != defn.name:
            raise StratumError(
                f"Cannot resume run '{run_id}': workspace belongs to pipeline "
                f"'{ws.pipeline_name}', not '{defn.name}'"
            )
    else:
        ws = RunWorkspace.create(working_dir, defn.name)

    pipeline_start = time.monotonic()
    phase_records: dict[str, PhaseRecord] = {}

    for phase in defn.phases:
        phase_start = time.monotonic()

        # -- resume: skip already-completed phases --------------------------
        if ws.has_result(phase.name):
            phase_records[phase.name] = PhaseRecord(
                name=phase.name,
                status="skipped",
                duration_ms=0,
                result=ws.read_result(phase.name),
            )
            continue

        # -- halt: phase previously failed (no retries left) ----------------
        if ws.has_failed(phase.name):
            record = ws.read_failed(phase.name)
            phase_records[phase.name] = PhaseRecord(
                name=phase.name,
                status="failed",
                duration_ms=int((time.monotonic() - phase_start) * 1000),
                error=record.get("error", "unknown"),
            )
            total_ms = int((time.monotonic() - pipeline_start) * 1000)
            return PipelineResult(
                run_id=ws.run_id,
                status="failed",
                phases=phase_records,
                duration_ms=total_ms,
                workspace=ws,
            )

        # -- resolve effective policy and connector -------------------------
        effective_policy = config.effective_policy(phase.name, phase.policy)
        effective_connector_name = config.effective_connector(
            phase.name, phase.connector, defn.connector
        )

        # -- gate: write gate file and block until approved -----------------
        if effective_policy == Policy.GATE:
            ws.write_gate(
                phase.name,
                context={
                    "intent":    phase.intent,
                    "connector": effective_connector_name,
                },
            )
            try:
                await _wait_for_gate(ws, phase.name, poll_interval_s)
            except StratumError as exc:
                elapsed = int((time.monotonic() - phase_start) * 1000)
                phase_records[phase.name] = PhaseRecord(
                    name=phase.name,
                    status="rejected",
                    duration_ms=elapsed,
                    error=str(exc),
                )
                total_ms = int((time.monotonic() - pipeline_start) * 1000)
                return PipelineResult(
                    run_id=ws.run_id,
                    status="rejected",
                    phases=phase_records,
                    duration_ms=total_ms,
                    workspace=ws,
                )

        # -- gather prior phase outputs -------------------------------------
        prior_outputs: dict[str, dict[str, Any]] = {}
        for input_name in phase.input:
            prior_outputs[input_name] = ws.read_result(input_name)

        # -- build prompt ---------------------------------------------------
        prompt = _build_prompt(phase, inputs, prior_outputs)
        opts   = RunOpts(
            working_dir=str(working_dir),
            connector_name=effective_connector_name,
            model_hint=config.model_hint(phase.capability.value),
        )

        # -- execute with retries -------------------------------------------
        last_error: str = ""
        for attempt in range(phase.retries):
            try:
                raw = await connector.run(prompt, phase.capability, opts)
            except Exception as exc:
                last_error = str(exc)
                if attempt < phase.retries - 1:
                    continue
                break

            try:
                result_data: dict[str, Any] = json.loads(raw)
            except json.JSONDecodeError:
                last_error = f"connector returned non-JSON output: {raw[:120]}"
                if attempt < phase.retries - 1:
                    continue
                break

            violations = _evaluate_ensures(phase.ensures, result_data, working_dir)
            if not violations:
                # -- success: write result with envelope --------------------
                elapsed = int((time.monotonic() - phase_start) * 1000)
                envelope: dict[str, Any] = {
                    "_phase":       phase.name,
                    "_run_id":      ws.run_id,
                    "_connector":   effective_connector_name,
                    "_duration_ms": elapsed,
                    "_ensures":     list(phase.ensures),
                    "_ensures_result": {e: True for e in phase.ensures},
                }
                ws.write_result(phase.name, {**envelope, **result_data})
                phase_records[phase.name] = PhaseRecord(
                    name=phase.name,
                    status="complete",
                    duration_ms=elapsed,
                    result=result_data,
                )
                break
            else:
                last_error = f"ensure violations: {violations}"
                if attempt < phase.retries - 1:
                    continue
                # fall through to failure path
        else:
            # Loop completed without break — all retries exhausted
            pass

        if phase.name not in phase_records:
            # All retries exhausted without success
            ws.write_failed(phase.name, last_error)
            elapsed = int((time.monotonic() - phase_start) * 1000)
            phase_records[phase.name] = PhaseRecord(
                name=phase.name,
                status="failed",
                duration_ms=elapsed,
                error=last_error,
            )
            total_ms = int((time.monotonic() - pipeline_start) * 1000)
            return PipelineResult(
                run_id=ws.run_id,
                status="failed",
                phases=phase_records,
                duration_ms=total_ms,
                workspace=ws,
            )

        # -- FLAG policy: log the decision (non-blocking) -------------------
        if effective_policy == Policy.FLAG and phase.name in phase_records:
            # Recorded in PhaseRecord; full notification is a stratum-ui concern.
            pass

    total_ms = int((time.monotonic() - pipeline_start) * 1000)
    return PipelineResult(
        run_id=ws.run_id,
        status="complete",
        phases=phase_records,
        duration_ms=total_ms,
        workspace=ws,
    )
