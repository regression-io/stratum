"""Tests for @pipeline and @phase decorators."""

# NOTE: Do NOT add `from __future__ import annotations` here.
# It makes all annotations into strings, breaking annotation introspection.

import sys
import os
import warnings

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest
from dataclasses import dataclass
from stratum import (
    Capability, Policy,
    PhaseSpec, PipelineDefinition,
    phase, pipeline,
    StratumWarning,
)
from stratum.exceptions import StratumCompileError


# ---------------------------------------------------------------------------
# Fixtures — shared contracts
# ---------------------------------------------------------------------------

@dataclass
class DiscoveryResult:
    affected_files: list[str]
    risks: list[str]

@dataclass
class GateResult:
    ready: bool
    blockers: list[str]

@dataclass
class ImplResult:
    changed_files: list[str]
    tests_pass: bool


# ---------------------------------------------------------------------------
# @phase — basic metadata capture
# ---------------------------------------------------------------------------

def test_phase_stores_spec():
    @phase(capability=Capability.SCOUT, policy=Policy.SKIP)
    async def discovery(self, feature: str) -> DiscoveryResult:
        """Explore the codebase"""
        ...

    assert hasattr(discovery, "_phase_spec")
    assert hasattr(discovery, "_stratum_type")
    assert discovery._stratum_type == "phase"


def test_phase_spec_fields():
    @phase(
        capability=Capability.BUILDER,
        policy=Policy.GATE,
        input=["discovery"],
        ensures=["tests_pass", "files_changed"],
        connector="codex",
        retries=2,
    )
    async def implement(self, discovery: DiscoveryResult) -> ImplResult:
        """Implement the feature"""
        ...

    spec = implement._phase_spec
    assert spec.name        == "implement"
    assert spec.capability  == Capability.BUILDER
    assert spec.policy      == Policy.GATE
    assert spec.input       == ("discovery",)
    assert spec.ensures     == ("tests_pass", "files_changed")
    assert spec.connector   == "codex"
    assert spec.retries     == 2
    assert spec.return_hint is ImplResult


def test_phase_intent_from_docstring():
    @phase(capability=Capability.CRITIC, policy=Policy.FLAG)
    async def post_gate(self) -> None:
        """Review implementation quality"""
        ...

    assert post_gate._phase_spec.intent == "Review implementation quality"


def test_phase_intent_explicit_overrides_docstring():
    @phase(capability=Capability.CRITIC, policy=Policy.FLAG, intent="Custom intent")
    async def post_gate(self) -> None:
        """This docstring should be ignored"""
        ...

    assert post_gate._phase_spec.intent == "Custom intent"


def test_phase_intent_fallback_to_name():
    @phase(capability=Capability.SCOUT, policy=Policy.SKIP)
    async def discovery(self) -> None:
        ...

    assert discovery._phase_spec.intent == "discovery"


def test_phase_defaults():
    @phase(capability=Capability.SCOUT, policy=Policy.SKIP)
    async def discovery(self) -> None:
        ...

    spec = discovery._phase_spec
    assert spec.input     == ()
    assert spec.ensures   == ()
    assert spec.connector is None
    assert spec.retries   == 3


def test_phase_body_not_replaced():
    """@phase must not wrap the function — body stays as-is (never executed)."""
    @phase(capability=Capability.SCOUT, policy=Policy.SKIP)
    async def discovery(self) -> None:
        ...

    # The original function object is returned unchanged (not wrapped)
    assert discovery.__name__ == "discovery"


# ---------------------------------------------------------------------------
# @pipeline — basic construction
# ---------------------------------------------------------------------------

def test_pipeline_collects_phases():
    @pipeline(name="test-pipeline")
    class P:
        @phase(capability=Capability.SCOUT, policy=Policy.SKIP)
        async def discovery(self, feature: str) -> DiscoveryResult:
            """Explore"""
            ...

        @phase(capability=Capability.BUILDER, policy=Policy.SKIP, input=["discovery"])
        async def implement(self, discovery: DiscoveryResult) -> ImplResult:
            """Implement"""
            ...

    defn = P._pipeline_def
    assert isinstance(defn, PipelineDefinition)
    assert defn.name == "test-pipeline"
    assert len(defn.phases) == 2
    assert defn.phases[0].name == "discovery"
    assert defn.phases[1].name == "implement"


def test_pipeline_builds_phase_map():
    @pipeline(name="test-pipeline")
    class P:
        @phase(capability=Capability.SCOUT, policy=Policy.SKIP)
        async def discovery(self) -> None:
            ...

        @phase(capability=Capability.BUILDER, policy=Policy.SKIP)
        async def implement(self) -> None:
            ...

    assert "discovery" in P._pipeline_def.phase_map
    assert "implement" in P._pipeline_def.phase_map


def test_pipeline_default_connector():
    @pipeline(name="test-pipeline", connector="codex")
    class P:
        @phase(capability=Capability.SCOUT, policy=Policy.SKIP)
        async def discovery(self) -> None:
            ...

    assert P._pipeline_def.connector == "codex"


def test_pipeline_stratum_type():
    @pipeline(name="test-pipeline")
    class P:
        @phase(capability=Capability.SCOUT, policy=Policy.SKIP)
        async def discovery(self) -> None:
            ...

    assert P._stratum_type == "pipeline"


# ---------------------------------------------------------------------------
# @pipeline — validation errors
# ---------------------------------------------------------------------------

def test_pipeline_no_phases_raises():
    with pytest.raises(StratumCompileError, match="no @phase methods"):
        @pipeline(name="empty")
        class P:
            pass


def test_pipeline_unknown_input_raises():
    with pytest.raises(StratumCompileError, match="unknown input 'missing'"):
        @pipeline(name="test-pipeline")
        class P:
            @phase(capability=Capability.BUILDER, policy=Policy.SKIP, input=["missing"])
            async def implement(self) -> None:
                ...


def test_pipeline_valid_input_reference():
    @pipeline(name="test-pipeline")
    class P:
        @phase(capability=Capability.SCOUT, policy=Policy.SKIP)
        async def discovery(self) -> None:
            ...

        @phase(capability=Capability.BUILDER, policy=Policy.SKIP, input=["discovery"])
        async def implement(self) -> None:
            ...

    # no error raised — input reference is valid


def test_pipeline_forward_reference_raises():
    with pytest.raises(StratumCompileError, match="not an earlier phase"):
        @pipeline(name="test-pipeline")
        class P:
            @phase(capability=Capability.SCOUT, policy=Policy.SKIP, input=["implement"])
            async def discovery(self) -> None:
                ...

            @phase(capability=Capability.BUILDER, policy=Policy.SKIP)
            async def implement(self) -> None:
                ...


def test_pipeline_self_reference_raises():
    with pytest.raises(StratumCompileError, match="references itself"):
        @pipeline(name="test-pipeline")
        class P:
            @phase(capability=Capability.SCOUT, policy=Policy.SKIP, input=["discovery"])
            async def discovery(self) -> None:
                ...


def test_pipeline_cycle_raises():
    # A→B and B→A: B references A (valid ordering), A references B (forward ref)
    with pytest.raises(StratumCompileError, match="not an earlier phase"):
        @pipeline(name="test-pipeline")
        class P:
            @phase(capability=Capability.SCOUT, policy=Policy.SKIP, input=["implement"])
            async def discovery(self) -> None:
                ...

            @phase(capability=Capability.BUILDER, policy=Policy.SKIP, input=["discovery"])
            async def implement(self) -> None:
                ...


# ---------------------------------------------------------------------------
# @phase — retries validation
# ---------------------------------------------------------------------------

def test_phase_retries_zero_raises():
    with pytest.raises(StratumCompileError, match="retries must be >= 1"):
        @phase(capability=Capability.SCOUT, policy=Policy.SKIP, retries=0)
        async def discovery(self) -> None:
            ...


def test_phase_retries_negative_raises():
    with pytest.raises(StratumCompileError, match="retries must be >= 1"):
        @phase(capability=Capability.SCOUT, policy=Policy.SKIP, retries=-1)
        async def discovery(self) -> None:
            ...


def test_phase_retries_one_is_valid():
    @phase(capability=Capability.SCOUT, policy=Policy.SKIP, retries=1)
    async def discovery(self) -> None:
        ...

    assert discovery._phase_spec.retries == 1


# ---------------------------------------------------------------------------
# @pipeline — StratumWarning for non-portable ensures
# ---------------------------------------------------------------------------

def test_non_portable_ensure_warns_on_non_claude_connector():
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")

        @pipeline(name="test-pipeline", connector="codex")
        class P:
            @phase(
                capability=Capability.BUILDER,
                policy=Policy.SKIP,
                ensures=["result.coverage > 0.8"],  # arbitrary — not portable
            )
            async def implement(self) -> None:
                ...

    stratum_warns = [w for w in caught if issubclass(w.category, StratumWarning)]
    assert len(stratum_warns) == 1
    assert "result.coverage > 0.8" in str(stratum_warns[0].message)
    assert "codex" in str(stratum_warns[0].message)


def test_named_assertion_no_warning_on_non_claude_connector():
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")

        @pipeline(name="test-pipeline", connector="codex")
        class P:
            @phase(
                capability=Capability.BUILDER,
                policy=Policy.SKIP,
                ensures=["tests_pass", "files_changed"],  # portable
            )
            async def implement(self) -> None:
                ...

    stratum_warns = [w for w in caught if issubclass(w.category, StratumWarning)]
    assert len(stratum_warns) == 0


def test_no_warning_for_claude_code_connector():
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")

        @pipeline(name="test-pipeline", connector="claude-code")
        class P:
            @phase(
                capability=Capability.BUILDER,
                policy=Policy.SKIP,
                ensures=["result.coverage > 0.8"],  # arbitrary — Claude only
            )
            async def implement(self) -> None:
                ...

    stratum_warns = [w for w in caught if issubclass(w.category, StratumWarning)]
    assert len(stratum_warns) == 0


def test_non_portable_ensure_warns_when_phase_connector_set_no_pipeline_default():
    """Phase-level non-Claude connector must warn even when pipeline default is None."""
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")

        @pipeline(name="test-pipeline")  # no connector= default
        class P:
            @phase(
                capability=Capability.BUILDER,
                policy=Policy.SKIP,
                ensures=["result.coverage > 0.8"],
                connector="codex",  # phase-level non-Claude connector
            )
            async def implement(self) -> None:
                ...

    stratum_warns = [w for w in caught if issubclass(w.category, StratumWarning)]
    assert len(stratum_warns) == 1
    assert "codex" in str(stratum_warns[0].message)


def test_phase_connector_override_suppresses_warning():
    """Per-phase claude-code override silences warning even with non-Claude pipeline default."""
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")

        @pipeline(name="test-pipeline", connector="codex")
        class P:
            @phase(
                capability=Capability.BUILDER,
                policy=Policy.SKIP,
                ensures=["result.coverage > 0.8"],
                connector="claude-code",  # per-phase override
            )
            async def implement(self) -> None:
                ...

    stratum_warns = [w for w in caught if issubclass(w.category, StratumWarning)]
    assert len(stratum_warns) == 0


# ---------------------------------------------------------------------------
# Full pipeline — integration shape
# ---------------------------------------------------------------------------

def test_full_lifecycle_pipeline():
    @pipeline(name="feature-lifecycle", connector="claude-code")
    class FeaturePipeline:

        @phase(capability=Capability.SCOUT, policy=Policy.SKIP)
        async def discovery(self, feature: str) -> DiscoveryResult:
            """Explore codebase, identify affected files and dependencies"""
            ...

        @phase(capability=Capability.CRITIC, policy=Policy.GATE, input=["discovery"],
               ensures=["approved"])
        async def pre_gate(self, discovery: DiscoveryResult) -> GateResult:
            """Assess readiness"""
            ...

        @phase(capability=Capability.BUILDER, policy=Policy.SKIP,
               input=["discovery", "pre_gate"], ensures=["tests_pass", "files_changed"])
        async def implement(self, discovery: DiscoveryResult, gate: GateResult) -> ImplResult:
            """Implement the feature"""
            ...

        @phase(capability=Capability.CRITIC, policy=Policy.FLAG, input=["implement"],
               ensures=["approved"])
        async def post_gate(self, impl: ImplResult) -> GateResult:
            """Review implementation quality"""
            ...

        @phase(capability=Capability.BUILDER, policy=Policy.GATE,
               input=["implement", "post_gate"])
        async def checkpoint(self, impl: ImplResult, review: GateResult) -> None:
            """Confirm complete"""
            ...

    defn = FeaturePipeline._pipeline_def
    assert len(defn.phases) == 5
    names = [p.name for p in defn.phases]
    assert names == ["discovery", "pre_gate", "implement", "post_gate", "checkpoint"]
    assert defn.phase_map["implement"].input == ("discovery", "pre_gate")
