"""Tests for run_pipeline() — the pipeline runtime loop."""

# NOTE: Do NOT add `from __future__ import annotations` here.

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import asyncio
import json
import pytest
from dataclasses import dataclass
from pathlib import Path

from stratum import (
    Capability, Policy,
    PipelineResult, PhaseRecord,
    RunWorkspace,
    phase, pipeline,
    run_pipeline,
)
from stratum.connector import Connector, RunOpts
from stratum.pipeline_types import Capability
from stratum.exceptions import StratumError


# ---------------------------------------------------------------------------
# Shared fixtures — pipeline contracts
# ---------------------------------------------------------------------------

@dataclass
class DiscoveryResult:
    affected_files: list[str]
    risks: list[str]

@dataclass
class ImplResult:
    changed_files: list[str]
    tests_pass: bool


# ---------------------------------------------------------------------------
# MockConnector
# ---------------------------------------------------------------------------

class MockConnector:
    """Returns pre-configured JSON responses in sequence."""

    def __init__(self, responses: list[dict], supported: set[Capability] | None = None):
        self._queue    = list(responses)
        self._supported = supported or set(Capability)
        self.call_count = 0
        self.prompts: list[str] = []

    async def run(self, prompt: str, capability: Capability, opts: RunOpts | None = None) -> str:
        self.call_count += 1
        self.prompts.append(prompt)
        if not self._queue:
            raise RuntimeError("MockConnector queue exhausted")
        return json.dumps(self._queue.pop(0))

    def supports(self, capability: Capability) -> bool:
        return capability in self._supported


# ---------------------------------------------------------------------------
# Pipelines under test
# ---------------------------------------------------------------------------

@pipeline(name="single-phase")
class SinglePhasePipeline:
    @phase(capability=Capability.SCOUT, policy=Policy.SKIP)
    async def discovery(self, feature: str) -> DiscoveryResult:
        """Explore codebase"""
        ...


@pipeline(name="two-phase")
class TwoPhasePipeline:
    @phase(capability=Capability.SCOUT, policy=Policy.SKIP)
    async def discovery(self, feature: str) -> DiscoveryResult:
        """Explore codebase"""
        ...

    @phase(capability=Capability.BUILDER, policy=Policy.SKIP, input=["discovery"])
    async def implement(self, discovery: DiscoveryResult) -> ImplResult:
        """Implement the feature"""
        ...


@pipeline(name="gate-pipeline")
class GatePipeline:
    @phase(capability=Capability.CRITIC, policy=Policy.GATE)
    async def pre_gate(self, feature: str) -> dict:
        """Review before implementation"""
        ...

    @phase(capability=Capability.BUILDER, policy=Policy.SKIP, input=["pre_gate"])
    async def implement(self, pre_gate: dict) -> ImplResult:
        """Implement"""
        ...


@pipeline(name="ensures-pipeline")
class EnsuresPipeline:
    @phase(
        capability=Capability.BUILDER,
        policy=Policy.SKIP,
        ensures=["tests_pass", "files_changed"],
        retries=2,
    )
    async def implement(self, feature: str) -> ImplResult:
        """Implement with postconditions"""
        ...


# ---------------------------------------------------------------------------
# Basic execution
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_single_phase_runs_to_completion(tmp_path):
    connector = MockConnector([{"affected_files": ["a.py"], "risks": []}])
    result = await run_pipeline(
        SinglePhasePipeline, connector,
        inputs={"feature": "dark mode"},
        working_dir=tmp_path,
    )
    assert result.status == "complete"
    assert "discovery" in result.phases
    assert result.phases["discovery"].status == "complete"


@pytest.mark.asyncio
async def test_result_is_pipeline_result_type(tmp_path):
    connector = MockConnector([{"affected_files": [], "risks": []}])
    result = await run_pipeline(
        SinglePhasePipeline, connector,
        inputs={"feature": "x"},
        working_dir=tmp_path,
    )
    assert isinstance(result, PipelineResult)
    assert isinstance(result.workspace, RunWorkspace)
    assert result.run_id == result.workspace.run_id


@pytest.mark.asyncio
async def test_connector_called_once_per_phase(tmp_path):
    connector = MockConnector([
        {"affected_files": ["a.py"], "risks": []},
        {"changed_files": ["a.py"], "tests_pass": True},
    ])
    await run_pipeline(
        TwoPhasePipeline, connector,
        inputs={"feature": "x"},
        working_dir=tmp_path,
    )
    assert connector.call_count == 2


@pytest.mark.asyncio
async def test_phase_result_written_to_workspace(tmp_path):
    connector = MockConnector([{"affected_files": ["src/foo.py"], "risks": []}])
    result = await run_pipeline(
        SinglePhasePipeline, connector,
        inputs={"feature": "x"},
        working_dir=tmp_path,
    )
    assert result.workspace.has_result("discovery")


@pytest.mark.asyncio
async def test_phase_duration_is_non_negative(tmp_path):
    connector = MockConnector([{"affected_files": [], "risks": []}])
    result = await run_pipeline(
        SinglePhasePipeline, connector,
        inputs={"feature": "x"},
        working_dir=tmp_path,
    )
    assert result.phases["discovery"].duration_ms >= 0
    assert result.duration_ms >= 0


# ---------------------------------------------------------------------------
# Multi-phase and input passing
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_prior_output_injected_into_next_prompt(tmp_path):
    connector = MockConnector([
        {"affected_files": ["auth.py"], "risks": ["touches auth"]},
        {"changed_files": ["auth.py"], "tests_pass": True},
    ])
    await run_pipeline(
        TwoPhasePipeline, connector,
        inputs={"feature": "x"},
        working_dir=tmp_path,
    )
    # Second prompt must reference the first phase's output
    assert "discovery" in connector.prompts[1]
    assert "auth.py" in connector.prompts[1]


# ---------------------------------------------------------------------------
# Resume from existing results
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_resume_skips_completed_phases(tmp_path):
    # Simulate a run where discovery completed but implement was never reached
    # (e.g., the process was killed between phases).
    ws = RunWorkspace.create(tmp_path, "two-phase")
    ws.write_result("discovery", {"affected_files": ["a.py"], "risks": []})

    # Resume: discovery should be skipped (has result), implement should run
    connector = MockConnector([
        {"changed_files": ["a.py"], "tests_pass": True},
    ])
    result = await run_pipeline(
        TwoPhasePipeline, connector,
        inputs={"feature": "x"},
        run_id=ws.run_id,
        working_dir=tmp_path,
    )
    assert result.status == "complete"
    assert result.phases["discovery"].status == "skipped"
    assert result.phases["implement"].status == "complete"
    assert connector.call_count == 1   # only implement called


# ---------------------------------------------------------------------------
# Unsupported capability
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_unsupported_capability_raises_before_execution(tmp_path):
    connector = MockConnector([], supported={Capability.BUILDER})  # no SCOUT
    with pytest.raises(StratumError, match="does not support capability"):
        await run_pipeline(
            SinglePhasePipeline, connector,
            inputs={"feature": "x"},
            working_dir=tmp_path,
        )
    assert connector.call_count == 0


# ---------------------------------------------------------------------------
# Ensures
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_ensures_pass_when_satisfied(tmp_path):
    connector = MockConnector([
        {"changed_files": ["a.py"], "tests_pass": True},
    ])
    result = await run_pipeline(
        EnsuresPipeline, connector,
        inputs={"feature": "x"},
        working_dir=tmp_path,
    )
    assert result.status == "complete"


@pytest.mark.asyncio
async def test_ensures_fail_exhausts_retries(tmp_path):
    # Both retries return a result that fails tests_pass + files_changed
    connector = MockConnector([
        {"changed_files": [], "tests_pass": False},
        {"changed_files": [], "tests_pass": False},
    ])
    result = await run_pipeline(
        EnsuresPipeline, connector,
        inputs={"feature": "x"},
        working_dir=tmp_path,
    )
    assert result.status == "failed"
    assert result.phases["implement"].status == "failed"
    assert connector.call_count == 2   # retries=2


@pytest.mark.asyncio
async def test_ensures_retry_succeeds_on_second_attempt(tmp_path):
    connector = MockConnector([
        {"changed_files": [], "tests_pass": False},          # attempt 1 fails
        {"changed_files": ["a.py"], "tests_pass": True},     # attempt 2 passes
    ])
    result = await run_pipeline(
        EnsuresPipeline, connector,
        inputs={"feature": "x"},
        working_dir=tmp_path,
    )
    assert result.status == "complete"
    assert connector.call_count == 2


# ---------------------------------------------------------------------------
# Gate protocol — blocking and polling
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_gate_blocks_and_approves(tmp_path):
    connector = MockConnector([
        {"approved": True},                                   # pre_gate
        {"changed_files": ["a.py"], "tests_pass": True},     # implement
    ])

    async def approve_gate_soon():
        # Wait briefly for the gate file to be written, then approve
        for _ in range(50):
            ws = RunWorkspace.find_latest(tmp_path, "gate-pipeline")
            if ws and ws.is_gate_pending("pre_gate"):
                ws.approve_gate("pre_gate", note="looks good")
                return
            await asyncio.sleep(0.01)

    approve_task = asyncio.create_task(approve_gate_soon())
    result = await run_pipeline(
        GatePipeline, connector,
        inputs={"feature": "x"},
        working_dir=tmp_path,
        poll_interval_s=0.02,
    )
    await approve_task

    assert result.status == "complete"
    assert result.phases["pre_gate"].status == "complete"
    assert result.phases["implement"].status == "complete"


@pytest.mark.asyncio
async def test_gate_rejection_returns_rejected_status(tmp_path):
    connector = MockConnector([])   # no responses needed — gate is rejected

    async def reject_gate_soon():
        for _ in range(50):
            ws = RunWorkspace.find_latest(tmp_path, "gate-pipeline")
            if ws and ws.is_gate_pending("pre_gate"):
                ws.reject_gate("pre_gate", note="not ready")
                return
            await asyncio.sleep(0.01)

    reject_task = asyncio.create_task(reject_gate_soon())
    result = await run_pipeline(
        GatePipeline, connector,
        inputs={"feature": "x"},
        working_dir=tmp_path,
        poll_interval_s=0.02,
    )
    await reject_task

    assert result.status == "rejected"
    assert result.phases["pre_gate"].status == "rejected"
    assert connector.call_count == 0   # connector never called after rejection


@pytest.mark.asyncio
async def test_gate_file_written_to_workspace(tmp_path):
    connector = MockConnector([])

    async def reject_immediately():
        for _ in range(100):
            ws = RunWorkspace.find_latest(tmp_path, "gate-pipeline")
            if ws and ws.gate_path("pre_gate").exists():
                ws.reject_gate("pre_gate")
                return
            await asyncio.sleep(0.005)

    asyncio.create_task(reject_immediately())
    result = await run_pipeline(
        GatePipeline, connector,
        inputs={"feature": "x"},
        working_dir=tmp_path,
        poll_interval_s=0.01,
    )
    assert result.workspace.gate_path("pre_gate").exists()


# ---------------------------------------------------------------------------
# Gate file deletion does not bypass gate
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_gate_file_deletion_raises_not_bypasses(tmp_path):
    """Deleting the .gate file without approving/rejecting must not let the
    pipeline proceed as if approved; it must surface a StratumError."""
    connector = MockConnector([])

    async def delete_gate_soon():
        for _ in range(100):
            ws = RunWorkspace.find_latest(tmp_path, "gate-pipeline")
            if ws and ws.gate_path("pre_gate").exists():
                ws.gate_path("pre_gate").unlink()   # delete without approve/reject
                return
            await asyncio.sleep(0.005)

    asyncio.create_task(delete_gate_soon())
    result = await run_pipeline(
        GatePipeline, connector,
        inputs={"feature": "x"},
        working_dir=tmp_path,
        poll_interval_s=0.01,
    )
    # Gate-file deletion must not proceed as approved — must surface as rejected
    assert result.status == "rejected"
    assert result.phases["pre_gate"].status == "rejected"
    assert "removed without an explicit approval or rejection" in result.phases["pre_gate"].error
    assert connector.call_count == 0   # connector never called


# ---------------------------------------------------------------------------
# Resume pipeline-name mismatch
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_resume_wrong_pipeline_raises(tmp_path):
    """Resuming a run_id that belongs to a different pipeline must raise."""
    # Create a workspace for single-phase, then try to resume it as two-phase
    ws = RunWorkspace.create(tmp_path, "single-phase")
    connector = MockConnector([])
    with pytest.raises(StratumError, match="belongs to pipeline 'single-phase'"):
        await run_pipeline(
            TwoPhasePipeline, connector,
            inputs={"feature": "x"},
            run_id=ws.run_id,
            working_dir=tmp_path,
        )
    assert connector.call_count == 0


# ---------------------------------------------------------------------------
# Connector routing name threaded through RunOpts
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_connector_name_passed_in_opts(tmp_path):
    """effective_connector_name from config must be visible in RunOpts.connector_name."""
    from stratum.connector import RunOpts

    received_opts: list[RunOpts] = []

    class CapturingConnector:
        call_count = 0
        def supports(self, capability): return True
        async def run(self, prompt, capability, opts=None):
            self.call_count += 1
            received_opts.append(opts)
            return json.dumps({"affected_files": [], "risks": []})

    connector = CapturingConnector()
    await run_pipeline(
        SinglePhasePipeline, connector,
        inputs={"feature": "x"},
        working_dir=tmp_path,
    )
    assert len(received_opts) == 1
    # connector_name is None when no stratum.toml routing is configured
    assert received_opts[0].connector_name is None
    # model_hint is None when no stratum.toml capability mapping is configured
    assert received_opts[0].model_hint is None


@pytest.mark.asyncio
async def test_model_hint_passed_in_opts(tmp_path):
    """Capability mapping from stratum.toml must be visible in RunOpts.model_hint."""
    import tomllib
    from stratum.connector import RunOpts
    from stratum.project_config import StratumConfig

    # Write a stratum.toml that maps the scout capability to a model hint
    (tmp_path / "stratum.toml").write_bytes(
        b'[pipeline.capabilities]\nscout = "claude-haiku-4-5"\n'
    )
    config = StratumConfig.load(tmp_path / "stratum.toml")

    received_opts: list[RunOpts] = []

    class CapturingConnector:
        def supports(self, capability): return True
        async def run(self, prompt, capability, opts=None):
            received_opts.append(opts)
            return json.dumps({"affected_files": [], "risks": []})

    await run_pipeline(
        SinglePhasePipeline, CapturingConnector(),
        inputs={"feature": "x"},
        working_dir=tmp_path,
        config=config,
    )
    assert len(received_opts) == 1
    assert received_opts[0].model_hint == "claude-haiku-4-5"
