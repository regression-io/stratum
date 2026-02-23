"""@infer, @compute, @flow, @refine decorators."""

from __future__ import annotations

import asyncio
import contextvars
import dataclasses
import functools
import inspect
import uuid
from typing import Any, Callable, get_type_hints

from .budget import Budget
from .exceptions import ConvergenceFailure, StratumCompileError
from .executor import InferSpec, execute_infer


# ---------------------------------------------------------------------------
# Flow context — propagated to nested @infer calls via ContextVar
# ---------------------------------------------------------------------------

@dataclasses.dataclass
class _FlowContext:
    flow_id: str
    budget: Budget | None
    session_cache: dict = dataclasses.field(default_factory=dict)


_flow_ctx: contextvars.ContextVar[_FlowContext | None] = contextvars.ContextVar(
    "_flow_ctx", default=None
)


# ---------------------------------------------------------------------------
# @infer
# ---------------------------------------------------------------------------

def infer(
    intent: str,
    context: str | list[str] | None = None,
    ensure: Callable | list[Callable] | None = None,
    given: Callable | list[Callable] | None = None,
    model: str | None = None,
    temperature: float | None = None,
    budget: Budget | None = None,
    retries: int = 3,
    cache: str = "none",
    stable: bool = True,
    quorum: int | None = None,
    agree_on: str | None = None,
    threshold: int | None = None,
) -> Callable:
    """
    Decorator that marks a function as an LLM-backed inference step.

    The decorated function body MUST be `...`. It is never executed.
    """
    # Validate quorum parameters at decoration time
    if quorum is not None and (agree_on is None or threshold is None):
        raise StratumCompileError(
            "quorum requires both agree_on and threshold to be specified"
        )

    # Normalise None defaults here so each decorator call gets its own list
    if context is None:
        context = []
    if ensure is None:
        ensure = []
    if given is None:
        given = []

    def decorator(fn: Callable) -> Callable:
        # Note: Python 3.12+ optimises `def f(): ...` such that Ellipsis is no
        # longer stored in co_consts, so a static body check is unreliable.
        # The spec §2.3 intent (body is never executed) is enforced implicitly
        # — the wrapper replaces the function body entirely.

        hints = get_type_hints(fn, include_extras=True)
        return_type = hints.get("return")
        params = {k: v for k, v in hints.items() if k != "return"}

        # Normalise to lists
        ensure_list: list[Callable] = (
            ensure if isinstance(ensure, list) else [ensure]
        )
        given_list: list[Callable] = (
            given if isinstance(given, list) else [given]
        )
        context_list: list[str] = (
            context if isinstance(context, list) else [context]
        )

        spec = InferSpec(
            fn=fn,
            intent=intent,
            context=context_list,
            ensure=ensure_list,
            given=given_list,
            model=model,
            temperature=temperature,
            budget=budget,
            retries=retries,
            cache=cache,
            stable=stable,
            quorum=quorum,
            agree_on=agree_on,
            threshold=threshold,
            return_type=return_type,
            parameters=params,
        )

        @functools.wraps(fn)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Bind positional args to parameter names
            if args:
                sig = inspect.signature(fn)
                bound = sig.bind(*args, **kwargs)
                bound.apply_defaults()
                kwargs = dict(bound.arguments)

            # Pick up flow context if present
            ctx = _flow_ctx.get()
            flow_id = ctx.flow_id if ctx is not None else None
            flow_budget = ctx.budget if ctx is not None else None

            if quorum is not None:
                return await _execute_quorum(spec, kwargs, flow_budget, flow_id)

            if not stable:
                return await _execute_stable_false(spec, kwargs, flow_budget, flow_id)

            # stable=True: in test_mode, sample N times and assert stability
            from ._config import get_config
            cfg = get_config()
            if cfg["test_mode"]:
                return await _execute_stable_true_test(spec, kwargs, flow_budget, flow_id)

            return await execute_infer(spec, kwargs, flow_budget, flow_id)

        wrapper._stratum_spec = spec  # type: ignore[attr-defined]
        wrapper._stratum_type = "infer"  # type: ignore[attr-defined]
        return wrapper

    return decorator


# ---------------------------------------------------------------------------
# Quorum execution
# ---------------------------------------------------------------------------

async def _execute_quorum(
    spec: InferSpec,
    inputs: dict[str, Any],
    flow_budget: Budget | None,
    flow_id: str | None,
) -> Any:
    """Run spec.quorum parallel calls and check agreement on spec.agree_on."""
    from .exceptions import ConsensusFailure

    n = spec.quorum
    tasks = [
        asyncio.create_task(execute_infer(spec, inputs, flow_budget, flow_id))
        for _ in range(n)
    ]
    all_outputs = await asyncio.gather(*tasks, return_exceptions=True)

    # Filter successes
    successes = [o for o in all_outputs if not isinstance(o, Exception)]
    if not successes:
        first_err = next(e for e in all_outputs if isinstance(e, Exception))
        raise first_err  # type: ignore[misc]

    # Check agreement on agree_on field
    field_name = spec.agree_on
    threshold_n = spec.threshold

    def _get_field(obj: Any, name: str) -> Any:
        if hasattr(obj, name):
            return getattr(obj, name)
        if isinstance(obj, dict):
            return obj.get(name)
        return obj

    from collections import Counter

    field_values = [_get_field(o, field_name) for o in successes]
    counts: Counter = Counter(str(v) for v in field_values)
    modal_str, modal_count = counts.most_common(1)[0]

    if modal_count < threshold_n:
        raise ConsensusFailure(spec.fn.__name__, n, threshold_n, list(all_outputs))

    # Return the agreeing result with highest confidence (if available), else first
    agreers = [
        o for o in successes if str(_get_field(o, field_name)) == modal_str
    ]
    best = agreers[0]
    if hasattr(best, "confidence"):
        best = max(agreers, key=lambda o: getattr(o, "confidence", 0))
    return best


# ---------------------------------------------------------------------------
# stable=True test-mode execution
# ---------------------------------------------------------------------------

async def _execute_stable_true_test(
    spec: InferSpec,
    inputs: dict[str, Any],
    flow_budget: Budget | None,
    flow_id: str | None,
) -> Any:
    """In test_mode, sample N times and assert unanimous stability before returning."""
    from ._config import get_config
    from .types import Probabilistic

    cfg = get_config()
    n = cfg["sample_n"]
    tasks = [
        asyncio.create_task(execute_infer(spec, inputs, flow_budget, flow_id))
        for _ in range(n)
    ]
    results = await asyncio.gather(*tasks)
    return Probabilistic(list(results)).assert_stable()


# ---------------------------------------------------------------------------
# stable=False execution
# ---------------------------------------------------------------------------

async def _execute_stable_false(
    spec: InferSpec,
    inputs: dict[str, Any],
    flow_budget: Budget | None,
    flow_id: str | None,
) -> Any:
    """Run once (or sample_n times in test_mode) and wrap in Probabilistic."""
    from ._config import get_config
    from .types import Probabilistic

    cfg = get_config()
    if cfg["test_mode"]:
        n = cfg["sample_n"]
        tasks = [
            asyncio.create_task(execute_infer(spec, inputs, flow_budget, flow_id))
            for _ in range(n)
        ]
        results = await asyncio.gather(*tasks)
        return Probabilistic(list(results))
    else:
        result = await execute_infer(spec, inputs, flow_budget, flow_id)
        return Probabilistic([result])


# ---------------------------------------------------------------------------
# @compute
# ---------------------------------------------------------------------------

def compute(fn: Callable) -> Callable:
    """
    Marks a function as deterministic. Never routed to an LLM.
    The function is returned unchanged with metadata attributes added.
    """
    fn._stratum_type = "compute"  # type: ignore[attr-defined]
    return fn


# ---------------------------------------------------------------------------
# @flow
# ---------------------------------------------------------------------------

def flow(budget: Budget | None = None) -> Callable:
    """
    Marks an async def function as a Stratum flow.

    Injects a flow_id and budget envelope into the ContextVar so nested
    @infer calls can inherit them without explicit passing.
    """

    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            flow_id = str(uuid.uuid4())
            flow_budget = budget.clone() if budget is not None else None
            ctx = _FlowContext(flow_id=flow_id, budget=flow_budget)
            token = _flow_ctx.set(ctx)
            try:
                return await fn(*args, **kwargs)
            finally:
                _flow_ctx.reset(token)

        wrapper._stratum_type = "flow"  # type: ignore[attr-defined]
        return wrapper

    return decorator


# ---------------------------------------------------------------------------
# @refine
# ---------------------------------------------------------------------------

def refine(
    until: Callable,
    feedback: Callable,
    max_iterations: int = 5,
) -> Callable:
    """
    Stacked on @infer. Adds an outer convergence loop.

    `until` and `feedback` MUST NOT call @infer functions.
    max_iterations exhausted → raises ConvergenceFailure.
    """

    def decorator(fn: Callable) -> Callable:
        if not hasattr(fn, "_stratum_spec"):
            raise StratumCompileError(
                "@refine must be stacked on an @infer-decorated function"
            )

        base_spec: InferSpec = fn._stratum_spec

        @functools.wraps(fn)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            if args:
                sig = inspect.signature(base_spec.fn)
                bound = sig.bind(*args, **kwargs)
                bound.apply_defaults()
                kwargs = dict(bound.arguments)

            ctx = _flow_ctx.get()
            flow_id = ctx.flow_id if ctx is not None else None
            flow_budget = ctx.budget if ctx is not None else None

            history: list[Any] = []
            extra_context: list[str] = []

            for iteration in range(max_iterations):
                # Build a modified spec with feedback context appended
                current_spec = InferSpec(
                    fn=base_spec.fn,
                    intent=base_spec.intent,
                    context=base_spec.context + extra_context,
                    ensure=base_spec.ensure,
                    given=base_spec.given,
                    model=base_spec.model,
                    temperature=base_spec.temperature,
                    budget=base_spec.budget,
                    retries=base_spec.retries,
                    cache=base_spec.cache,
                    stable=base_spec.stable,
                    quorum=base_spec.quorum,
                    agree_on=base_spec.agree_on,
                    threshold=base_spec.threshold,
                    return_type=base_spec.return_type,
                    parameters=base_spec.parameters,
                )

                result = await execute_infer(current_spec, kwargs, flow_budget, flow_id)
                history.append(result)

                if until(result):
                    return result

                # Build feedback context for the next iteration
                fb = feedback(result)
                extra_context = [
                    f"Previous output had the following issues: {fb}. "
                    "Fix these and regenerate."
                ]

            raise ConvergenceFailure(base_spec.fn.__name__, max_iterations, history)

        wrapper._stratum_type = "refine"  # type: ignore[attr-defined]
        wrapper._stratum_spec = base_spec  # type: ignore[attr-defined]
        return wrapper

    return decorator
