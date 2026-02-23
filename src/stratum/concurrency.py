"""Concurrency primitives: parallel, race, debate."""

from __future__ import annotations

import asyncio
from typing import Any, Callable

from .exceptions import ConsensusFailure, ParallelValidationFailed
from .types import Failure, Success


async def parallel(
    *coros: Any,
    require: str | int = "all",
    validate: Callable[[list], bool] | None = None,
) -> Any:
    """
    Run coroutines concurrently with configurable success semantics.

    require="all"  → all must succeed; any failure cancels rest and re-raises.
                     Returns a tuple matching input order.
    require="any"  → first success wins, rest cancelled. Returns single result.
    require=N: int → at least N must succeed. Returns list of N results.
    require=0      → collect all regardless of failure. Returns list[Success|Failure].

    validate       → optional callable on collected results; False → ParallelValidationFailed.
    """
    if require == "all":
        async with asyncio.TaskGroup() as tg:
            tasks = [tg.create_task(c) for c in coros]
        results = [t.result() for t in tasks]

        if validate is not None and not validate(results):
            raise ParallelValidationFailed()

        return tuple(results)

    if require == "any":
        if not coros:
            raise ValueError("parallel(require='any'): requires at least one coroutine")
        tasks = [asyncio.create_task(c) for c in coros]
        pending: set = set(tasks)
        last_exc: Exception | None = None

        while pending:
            done, pending = await asyncio.wait(
                pending, return_when=asyncio.FIRST_COMPLETED
            )
            winner = None
            for d in done:
                if d.exception() is None:
                    winner = d
                    break
                last_exc = d.exception()

            if winner is not None:
                # Cancel remaining pending tasks
                for p in pending:
                    p.cancel()
                    try:
                        await p
                    except (asyncio.CancelledError, Exception):
                        pass
                # Drain other done tasks so their exceptions are retrieved
                for d in done:
                    if d is not winner:
                        try:
                            d.exception()
                        except (asyncio.CancelledError, Exception):
                            pass
                result = winner.result()
                if validate is not None and not validate([result]):
                    raise ParallelValidationFailed()
                return result

        if last_exc is not None:
            raise last_exc
        raise RuntimeError("parallel: all coroutines failed with no exception recorded")

    if isinstance(require, int) and require == 0:
        # Collect all regardless of failure — wrap in Success/Failure
        raw = await asyncio.gather(*coros, return_exceptions=True)
        results = [
            Success(r) if not isinstance(r, Exception) else Failure(r)
            for r in raw
        ]
        if validate is not None and not validate(results):
            raise ParallelValidationFailed()
        return results

    if isinstance(require, int) and require > 0:
        # At least require many must succeed
        all_results = await asyncio.gather(*coros, return_exceptions=True)
        successes = [r for r in all_results if not isinstance(r, Exception)]
        failures = [r for r in all_results if isinstance(r, Exception)]

        if len(successes) < require:
            if failures:
                raise failures[0]
            raise RuntimeError(
                f"parallel: needed {require} successes, got {len(successes)}"
            )

        results = successes[:require]
        if validate is not None and not validate(results):
            raise ParallelValidationFailed()
        return results

    raise ValueError(f"parallel: invalid require value: {require!r}")


async def race(*coros: Any) -> Any:
    """
    Submit all coroutines concurrently. First to complete without raising wins.
    Remaining coroutines are cancelled. If all raise, re-raises the last error.
    """
    if not coros:
        raise ValueError("race: requires at least one coroutine")
    tasks = [asyncio.create_task(c) for c in coros]
    pending: set = set(tasks)
    last_exc: Exception | None = None

    while pending:
        done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
        winner = None
        for d in done:
            exc = d.exception()
            if exc is None:
                winner = d
                break
            last_exc = exc

        if winner is not None:
            # Cancel the rest
            for p in pending:
                p.cancel()
                try:
                    await p
                except (asyncio.CancelledError, Exception):
                    pass
            # Drain other done tasks so their exceptions are retrieved
            for d in done:
                if d is not winner:
                    try:
                        d.exception()
                    except (asyncio.CancelledError, Exception):
                        pass
            return winner.result()

    if last_exc is not None:
        raise last_exc
    raise RuntimeError("race: all coroutines failed")


async def debate(
    agents: list[Callable],
    topic: Any,
    rounds: int = 2,
    *,
    synthesize: Callable,
) -> Any:
    """
    Multi-agent debate protocol.

    Round 1: all agents invoked concurrently with topic.
    Rounds 2..N: each agent invoked concurrently with topic + other agents' previous arguments.
    After all rounds, convergence is computed and synthesize is called.

    synthesize is required.
    """
    if not agents:
        raise ValueError("debate: agents list must not be empty")

    # Round 1 — initial arguments (concurrent)
    initial_results = await asyncio.gather(*[agent(topic=topic) for agent in agents])
    arguments: list[Any] = list(initial_results)
    history: list[list[Any]] = [arguments]

    # Rebuttal rounds — each round all agents run concurrently
    for _round in range(1, rounds):
        rebuttal_coros = [
            agents[i](
                topic=topic,
                previous_arguments=[arguments[j] for j in range(len(arguments)) if j != i],
            )
            for i in range(len(agents))
        ]
        new_args = list(await asyncio.gather(*rebuttal_coros))
        arguments = new_args
        history.append(list(arguments))

    # Compute convergence — use agree_on field from agents if declared
    last_round = history[-1]
    agree_on_field: str | None = None
    for agent in agents:
        spec = getattr(agent, "_stratum_spec", None)
        if spec is not None and getattr(spec, "agree_on", None):
            agree_on_field = spec.agree_on
            break

    def _get_field(obj: Any, name: str) -> Any:
        if hasattr(obj, name):
            return getattr(obj, name)
        if isinstance(obj, dict):
            return obj.get(name)
        return obj

    if agree_on_field is not None:
        comparison_values = {str(_get_field(a, agree_on_field)) for a in last_round}
    else:
        comparison_values = {str(a) for a in last_round}

    converged = len(comparison_values) == 1

    return await synthesize(topic=topic, arguments=history, converged=converged)
