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
)
from .decorators import infer, compute, flow, refine
from .trace import TraceRecord, all_records, clear as clear_traces
from ._config import configure
from .types import Probabilistic, HumanDecision, HumanReviewContext
from .hitl import await_human, ReviewSink, ConsoleReviewSink, PendingReview
from .concurrency import parallel, debate, race
from . import exporters


def run(coro: Any) -> Any:
    """
    Synchronous shim for non-async contexts (scripts, notebooks).

    Manages an event loop internally. MUST NOT be called from inside an
    already-running event loop.
    """
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            raise RuntimeError(
                "stratum.run() must not be called from inside a running event loop. "
                "Use 'await' directly instead."
            )
        return loop.run_until_complete(coro)
    except RuntimeError as exc:
        if "no current event loop" in str(exc).lower():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(coro)
            finally:
                loop.close()
        raise


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
    # Configuration
    "configure",
    "run",
    # Trace
    "TraceRecord",
    "all_records",
    "clear_traces",
    # Errors
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
    # Registry
    "is_registered",
    # Exporters
    "exporters",
]
