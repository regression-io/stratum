"""
Stratum — LLM calls that behave like the rest of your code.

Public API surface (v1):

    Decorators:   @contract, @infer, @compute, @flow, @refine
    Types:        Budget, opaque, Probabilistic, HumanDecision, HumanReviewContext
    HITL:         await_human
    Concurrency:  parallel, debate, race
    Utilities:    configure, run
    Errors:       StratumError and all subclasses
    Trace:        TraceRecord, all_records, clear_traces
"""

from __future__ import annotations

import asyncio
from typing import Any

from .contracts import contract, opaque, is_registered
from .budget import Budget
from .exceptions import (
    StratumError,
    StratumCompileError,
    PreconditionFailed,
    PostconditionFailed,
    ParseFailure,
    BudgetExceeded,
    ConvergenceFailure,
    ConsensusFailure,
    ParallelValidationFailed,
    HITLTimeoutError,
    StabilityAssertionError,
    StratumWarning,
)
from .pipeline_types import (
    Capability,
    Policy,
    NAMED_ASSERTIONS,
    BARE_ASSERTIONS,
    PARAMETERISED_ASSERTIONS,
    is_named_assertion,
)
from .pipeline import (
    PhaseSpec,
    PipelineDefinition,
    phase,
    pipeline,
)
from .project_config import (
    PipelineConfig,
    StratumConfig,
)
from .run_workspace import RunWorkspace
from .connector import Connector, RunOpts
from .pipeline_runner import PhaseRecord, PipelineResult, run_pipeline
from .decorators import infer, compute, flow, refine
from .trace import TraceRecord, all_records, clear as clear_traces
from ._config import configure
from .types import Probabilistic, HumanDecision, HumanReviewContext, Success, Failure
from .hitl import await_human, ReviewSink, ConsoleReviewSink, PendingReview
from .concurrency import parallel, debate, race
from .flow_scope import FlowScope
from . import exporters


def run(coro: Any) -> Any:
    """
    Synchronous shim for non-async contexts (scripts, notebooks).

    Manages an event loop internally. MUST NOT be called from inside an
    already-running event loop.
    """
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = None

    if loop is not None and loop.is_running():
        coro.close()
        raise RuntimeError(
            "stratum.run() must not be called from inside a running event loop. "
            "Use 'await' directly instead."
        )

    if loop is None or loop.is_closed():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


__all__ = [
    # Decorators
    "contract",
    "infer",
    "compute",
    "flow",
    "refine",
    # Types
    "Budget",
    "opaque",
    "Probabilistic",
    "Success",
    "Failure",
    "HumanDecision",
    "HumanReviewContext",
    # HITL
    "await_human",
    "ReviewSink",
    "ConsoleReviewSink",
    "PendingReview",
    # Concurrency
    "parallel",
    "debate",
    "race",
    # Flow context
    "FlowScope",
    # Configuration
    "configure",
    "run",
    # Trace
    "TraceRecord",
    "all_records",
    "clear_traces",
    # Errors and warnings
    "StratumError",
    "StratumCompileError",
    "PreconditionFailed",
    "PostconditionFailed",
    "ParseFailure",
    "BudgetExceeded",
    "ConvergenceFailure",
    "ConsensusFailure",
    "ParallelValidationFailed",
    "HITLTimeoutError",
    "StabilityAssertionError",
    "StratumWarning",
    # Pipeline primitives
    "Capability",
    "Policy",
    "NAMED_ASSERTIONS",
    "BARE_ASSERTIONS",
    "PARAMETERISED_ASSERTIONS",
    "is_named_assertion",
    # Pipeline decorators
    "PhaseSpec",
    "PipelineDefinition",
    "phase",
    "pipeline",
    # Project config
    "PipelineConfig",
    "StratumConfig",
    # Run workspace
    "RunWorkspace",
    # Connector protocol
    "Connector",
    "RunOpts",
    # Pipeline runner
    "PhaseRecord",
    "PipelineResult",
    "run_pipeline",
    # Registry
    "is_registered",
    # Exporters
    "exporters",
]
