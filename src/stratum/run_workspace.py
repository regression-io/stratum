"""Run workspace — .stratum/runs/{run-id}/ output passing between phases."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .exceptions import StratumError


class RunWorkspace:
    """
    Manages a single pipeline run's workspace directory.

    Layout::

        {project-root}/
          .stratum/
            runs/
              {run-id}/
                manifest.json               — run metadata (run_id, pipeline, created_at)
                {phase-name}.json           — phase output, written after completion
                {phase-name}.gate           — gate request written by connector (policy=GATE)
                {phase-name}.gate.approved  — approval written by viewer / human
                {phase-name}.gate.rejected  — rejection written by viewer / human

    RunWorkspace is the persistence layer for output passing between phases and
    for the file-based gate protocol. The harness writes results here after each
    phase completes; the next phase reads prior outputs from here before
    constructing the agent's prompt.

    Session-death safe: completed phase outputs persist on disk. The next session
    resumes by calling RunWorkspace.open() with the existing run directory.
    """

    def __init__(self, run_dir: Path, run_id: str, pipeline_name: str) -> None:
        self._run_dir       = run_dir
        self._run_id        = run_id
        self._pipeline_name = pipeline_name

    # -----------------------------------------------------------------------
    # Properties
    # -----------------------------------------------------------------------

    @property
    def run_id(self) -> str:
        """Unique identifier for this run."""
        return self._run_id

    @property
    def run_dir(self) -> Path:
        """Absolute path to this run's workspace directory."""
        return self._run_dir

    @property
    def pipeline_name(self) -> str:
        """Name of the pipeline this run belongs to."""
        return self._pipeline_name

    # -----------------------------------------------------------------------
    # Construction
    # -----------------------------------------------------------------------

    @classmethod
    def create(cls, root: Path | str, pipeline_name: str) -> RunWorkspace:
        """
        Create a new run workspace at ``root/.stratum/runs/{run-id}/``.

        Args:
            root:          Project root directory. The ``.stratum/`` subtree is
                           created here, not inside it.
            pipeline_name: Name of the pipeline (from ``@pipeline(name=...)``).

        Returns:
            A RunWorkspace for the new run.
        """
        root    = Path(root)
        run_id  = uuid.uuid4().hex[:12]
        run_dir = root / ".stratum" / "runs" / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        manifest: dict[str, Any] = {
            "run_id":     run_id,
            "pipeline":   pipeline_name,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))
        return cls(run_dir, run_id, pipeline_name)

    @classmethod
    def open(cls, run_dir: Path | str) -> RunWorkspace:
        """
        Open an existing run workspace by directory path.

        Raises:
            StratumError: If the directory or manifest does not exist, the
                          manifest is not valid JSON, or required fields are missing.
        """
        run_dir = Path(run_dir)
        if not run_dir.exists():
            raise StratumError(f"Run workspace not found: {run_dir}")
        manifest_path = run_dir / "manifest.json"
        if not manifest_path.exists():
            raise StratumError(f"Run workspace manifest not found: {manifest_path}")
        try:
            manifest = json.loads(manifest_path.read_text())
        except json.JSONDecodeError as exc:
            raise StratumError(
                f"Run workspace manifest is not valid JSON: {manifest_path}: {exc}"
            ) from exc
        try:
            run_id        = manifest["run_id"]
            pipeline_name = manifest["pipeline"]
        except KeyError as exc:
            raise StratumError(
                f"Run workspace manifest is missing field {exc}: {manifest_path}"
            ) from exc
        return cls(run_dir, run_id, pipeline_name)

    @classmethod
    def find_latest(cls, root: Path | str, pipeline_name: str) -> RunWorkspace | None:
        """
        Return the most recently created run workspace for a pipeline, or
        ``None`` if no matching runs exist under ``root/.stratum/runs/``.

        "Most recently created" is determined by the manifest file's mtime,
        which reflects the wall-clock time of ``create()``.
        """
        runs_dir = Path(root) / ".stratum" / "runs"
        if not runs_dir.exists():
            return None

        candidates: list[tuple[float, Path]] = []
        for run_dir in runs_dir.iterdir():
            if not run_dir.is_dir():
                continue
            manifest_path = run_dir / "manifest.json"
            if not manifest_path.exists():
                continue
            try:
                manifest = json.loads(manifest_path.read_text())
            except (json.JSONDecodeError, OSError):
                continue
            if manifest.get("pipeline") == pipeline_name:
                candidates.append((manifest_path.stat().st_mtime, run_dir))

        if not candidates:
            return None
        _, latest_dir = max(candidates, key=lambda t: t[0])
        return cls.open(latest_dir)

    # -----------------------------------------------------------------------
    # Internal path helper
    # -----------------------------------------------------------------------

    def _safe_path(self, phase_name: str, suffix: str) -> Path:
        """
        Resolve ``{phase_name}{suffix}`` within the run directory.

        Raises:
            StratumError: If the resolved path escapes the run directory
                          (path traversal guard).
        """
        candidate = self._run_dir / f"{phase_name}{suffix}"
        if not candidate.resolve().is_relative_to(self._run_dir.resolve()):
            raise StratumError(
                f"Invalid phase name '{phase_name}': would escape run directory"
            )
        return candidate

    # -----------------------------------------------------------------------
    # Phase result I/O
    # -----------------------------------------------------------------------

    def result_path(self, phase_name: str) -> Path:
        """Return the path where ``phase_name``'s result JSON is stored."""
        return self._safe_path(phase_name, ".json")

    def has_result(self, phase_name: str) -> bool:
        """Return ``True`` if a result file exists for ``phase_name``."""
        return self.result_path(phase_name).exists()

    def write_result(self, phase_name: str, data: dict[str, Any]) -> None:
        """
        Persist ``phase_name``'s output to disk as JSON.

        Overwrites any existing result file. Idempotent for retries.
        """
        self.result_path(phase_name).write_text(json.dumps(data, indent=2))

    def read_result(self, phase_name: str) -> dict[str, Any]:
        """
        Read and return ``phase_name``'s output.

        Raises:
            StratumError: If no result exists for ``phase_name``, or the file
                          is not valid JSON.
        """
        path = self.result_path(phase_name)
        if not path.exists():
            raise StratumError(
                f"No result for phase '{phase_name}' in run '{self._run_id}'"
            )
        try:
            return json.loads(path.read_text())
        except json.JSONDecodeError as exc:
            raise StratumError(
                f"Corrupt result file for phase '{phase_name}' in run "
                f"'{self._run_id}': {exc}"
            ) from exc

    def completed_phases(self) -> list[str]:
        """
        Return the names of phases that have a result on disk.

        Results are returned in lexicographic order by filename. Use the
        pipeline's phase list to enforce pipeline-definition order.
        """
        return [
            p.stem
            for p in sorted(self._run_dir.glob("*.json"))
            if p.name != "manifest.json"
        ]

    # -----------------------------------------------------------------------
    # Failed-phase record
    #
    # File convention:
    #   {phase}.failed  — written by harness when a phase exhausts all retries
    # -----------------------------------------------------------------------

    def failed_path(self, phase_name: str) -> Path:
        """Path to the failed-phase record: ``{phase_name}.failed``."""
        return self._safe_path(phase_name, ".failed")

    def has_failed(self, phase_name: str) -> bool:
        """Return ``True`` if a failed record exists for ``phase_name``."""
        return self.failed_path(phase_name).exists()

    def write_failed(self, phase_name: str, error: str) -> None:
        """Persist a failure record for ``phase_name``."""
        payload: dict[str, Any] = {
            "phase":      phase_name,
            "error":      error,
            "failed_at":  datetime.now(timezone.utc).isoformat(),
        }
        self.failed_path(phase_name).write_text(json.dumps(payload, indent=2))

    def read_failed(self, phase_name: str) -> dict[str, Any]:
        """Read and return the failure record for ``phase_name``."""
        path = self.failed_path(phase_name)
        if not path.exists():
            raise StratumError(
                f"No failure record for phase '{phase_name}' in run '{self._run_id}'"
            )
        try:
            return json.loads(path.read_text())
        except json.JSONDecodeError as exc:
            raise StratumError(
                f"Corrupt failure record for phase '{phase_name}': {exc}"
            ) from exc

    # -----------------------------------------------------------------------
    # Gate protocol
    #
    # File convention:
    #   {phase}.gate           — connector writes when policy=GATE blocks
    #   {phase}.gate.approved  — viewer / human writes to unblock (approve)
    #   {phase}.gate.rejected  — viewer / human writes to unblock (reject)
    # -----------------------------------------------------------------------

    def gate_path(self, phase_name: str) -> Path:
        """Path to the gate request file: ``{phase_name}.gate``."""
        return self._safe_path(phase_name, ".gate")

    def _gate_approved_path(self, phase_name: str) -> Path:
        return self._safe_path(phase_name, ".gate.approved")

    def _gate_rejected_path(self, phase_name: str) -> Path:
        return self._safe_path(phase_name, ".gate.rejected")

    def write_gate(
        self,
        phase_name: str,
        context: dict[str, Any] | None = None,
    ) -> None:
        """
        Write a gate request file, signalling that this phase is blocked
        pending human approval. Called by the connector when ``policy=GATE``.

        Clears any stale ``.gate.approved`` / ``.gate.rejected`` files from a
        prior gate cycle so that ``is_gate_pending()`` correctly reflects the
        new gate rather than the old response.
        """
        # Clear stale response files before writing the new gate request.
        for stale in (
            self._gate_approved_path(phase_name),
            self._gate_rejected_path(phase_name),
        ):
            if stale.exists():
                stale.unlink()
        payload: dict[str, Any] = {
            "phase":      phase_name,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "context":    context or {},
        }
        self.gate_path(phase_name).write_text(json.dumps(payload, indent=2))

    def read_gate(self, phase_name: str) -> dict[str, Any]:
        """
        Read and return the gate context written by ``write_gate()``.

        Raises:
            StratumError: If no gate exists for ``phase_name``, or the file
                          is not valid JSON.
        """
        path = self.gate_path(phase_name)
        if not path.exists():
            raise StratumError(
                f"No gate for phase '{phase_name}' in run '{self._run_id}'"
            )
        try:
            return json.loads(path.read_text())
        except json.JSONDecodeError as exc:
            raise StratumError(
                f"Corrupt gate file for phase '{phase_name}' in run "
                f"'{self._run_id}': {exc}"
            ) from exc

    def is_gate_pending(self, phase_name: str) -> bool:
        """
        Return ``True`` if a gate request exists and has not yet been
        approved or rejected.
        """
        return (
            self.gate_path(phase_name).exists()
            and not self._gate_approved_path(phase_name).exists()
            and not self._gate_rejected_path(phase_name).exists()
        )

    def is_gate_approved(self, phase_name: str) -> bool:
        """Return ``True`` if the gate has been approved."""
        return self._gate_approved_path(phase_name).exists()

    def is_gate_rejected(self, phase_name: str) -> bool:
        """Return ``True`` if the gate has been rejected."""
        return self._gate_rejected_path(phase_name).exists()

    def approve_gate(self, phase_name: str, note: str | None = None) -> None:
        """
        Write a gate approval file, unblocking the pipeline.
        Called by stratum-ui or any watcher acting on human input.

        Raises:
            StratumError: If no gate request exists for ``phase_name``, or the
                          gate has already been rejected (conflicting terminal state).
        """
        if not self.gate_path(phase_name).exists():
            raise StratumError(
                f"Cannot approve: no gate for phase '{phase_name}' "
                f"in run '{self._run_id}'"
            )
        if self._gate_rejected_path(phase_name).exists():
            raise StratumError(
                f"Cannot approve: phase '{phase_name}' has already been rejected"
            )
        payload: dict[str, Any] = {
            "approved_at": datetime.now(timezone.utc).isoformat(),
            "note":        note,
        }
        self._gate_approved_path(phase_name).write_text(
            json.dumps(payload, indent=2)
        )

    def reject_gate(self, phase_name: str, note: str | None = None) -> None:
        """
        Write a gate rejection file, unblocking the pipeline with a rejection.
        Called by stratum-ui or any watcher acting on human input.

        Raises:
            StratumError: If no gate request exists for ``phase_name``, or the
                          gate has already been approved (conflicting terminal state).
        """
        if not self.gate_path(phase_name).exists():
            raise StratumError(
                f"Cannot reject: no gate for phase '{phase_name}' "
                f"in run '{self._run_id}'"
            )
        if self._gate_approved_path(phase_name).exists():
            raise StratumError(
                f"Cannot reject: phase '{phase_name}' has already been approved"
            )
        payload: dict[str, Any] = {
            "rejected_at": datetime.now(timezone.utc).isoformat(),
            "note":        note,
        }
        self._gate_rejected_path(phase_name).write_text(
            json.dumps(payload, indent=2)
        )

    def pending_gates(self) -> list[str]:
        """
        Return phase names that have an unanswered gate request
        (no ``.gate.approved`` or ``.gate.rejected`` response file).

        Results are in lexicographic order by phase name.
        """
        return [
            p.stem
            for p in sorted(self._run_dir.glob("*.gate"))
            if not (self._run_dir / f"{p.stem}.gate.approved").exists()
            and not (self._run_dir / f"{p.stem}.gate.rejected").exists()
        ]
