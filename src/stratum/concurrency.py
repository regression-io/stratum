"""Concurrency primitives: parallel, race, debate."""

from __future__ import annotations

import asyncio
from typing import Any, Callable

from .exceptions import ConsensusFailure, ParallelValidationFailed


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
    require=0      → collect all regardless of failure. Returns list of Result objects.

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
        tasks = [asyncio.create_task(c) for c in coros]
        try:
            done, pending = await asyncio.wait(
                tasks, return_when=asyncio.FIRST_COMPLETED
            )
            for p in pending:
                p.cancel()
                try:
                    await p
                except (asyncio.CancelledError, Exception):
                    pass

            # Find first non-exception result
            for d in done:
                if d.exception() is None:
                    result = d.result()
                    if validate is not None and not validate([result]):
                        raise ParallelValidationFailed()
                    return result

            # All failed — raise the first exception
            for d in done:
                raise d.exception()  # type: ignore[misc]
        except Exception:
            for t in tasks:
                if not t.done():
                    t.cancel()
            raise

    if isinstance(require, int) and require == 0:
        # Collect all regardless of failure
        raw = await asyncio.gather(*coros, return_exceptions=True)
        results = list(raw)
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
    tasks = [asyncio.create_task(c) for c in coros]
    last_exc: Exception | None = None

    try:
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)

        # Check if the first done succeeded
        for d in done:
            exc = d.exception()
            if exc is None:
                # Winner — cancel the rest
                for p in pending:
                    p.cancel()
                    try:
                        await p
                    except (asyncio.CancelledError, Exception):
                        pass
                return d.result()
            last_exc = exc

        # First done raised — wait for others
        if pending:
            done2, _ = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
            for d in done2:
                exc = d.exception()
                if exc is None:
                    # Cancel remaining
                    remaining = [t for t in tasks if not t.done()]
                    for r in remaining:
                        r.cancel()
                    return d.result()
                last_exc = exc

    except Exception as exc:
        last_exc = exc

    # All failed — cancel anything still running and re-raise
    for t in tasks:
        if not t.done():
            t.cancel()
            try:
                await t
            except (asyncio.CancelledError, Exception):
                pass

    if last_exc is not None:
        raise last_exc
    raise RuntimeError("race: all coroutines failed")


async def debate(
    agents: list[Callable],
    topic: Any,
    rounds: int = 2,
    synthesize: Callable | None = None,
) -> Any:
    """
    Multi-agent debate protocol.

    Round 1: all agents invoked concurrently with topic.
    Rounds 2..N: each agent invoked with topic + other agents' previous arguments.
    After all rounds, convergence is computed and synthesize is called.
    """
    if not agents:
        raise ValueError("debate: agents list must not be empty")

    # Round 1 — initial arguments
    initial_results = await asyncio.gather(*[agent(topic=topic) for agent in agents])
    arguments: list[Any] = list(initial_results)
    history: list[list[Any]] = [arguments]

    # Rebuttal rounds
    for _round in range(1, rounds):
        new_args: list[Any] = []
        for i, agent in enumerate(agents):
            others = [arguments[j] for j in range(len(arguments)) if j != i]
            new_arg = await agent(topic=topic, previous_arguments=others)
            new_args.append(new_arg)
        arguments = new_args
        history.append(list(arguments))

    # Compute convergence: check if last round outputs are all identical by repr
    last_round = history[-1]
    converged = len({str(a) for a in last_round}) == 1

    if synthesize is not None:
        return await synthesize(
            topic=topic, arguments=history, converged=converged
        )

    return {"arguments": history, "converged": converged}
