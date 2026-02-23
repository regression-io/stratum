"""Tests for stratum.parallel, race, debate, and quorum."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from typing import Literal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from stratum.concurrency import debate, parallel, race
from pydantic import BaseModel
from stratum.contracts import contract
from stratum.decorators import infer
from stratum.exceptions import ConsensusFailure, ParallelValidationFailed
from stratum.trace import clear as clear_traces


@contract
class Vote(BaseModel):
    label: Literal["yes", "no"]
    confidence: float


def _make_response(data: dict) -> MagicMock:
    tool_call = MagicMock()
    tool_call.function.arguments = json.dumps(data)
    message = MagicMock()
    message.tool_calls = [tool_call]
    choice = MagicMock()
    choice.message = message
    response = MagicMock()
    response.choices = [choice]
    response.usage = MagicMock(prompt_tokens=10, completion_tokens=5)
    return response


# ---------------------------------------------------------------------------
# parallel
# ---------------------------------------------------------------------------

class TestParallelAll:
    @pytest.mark.asyncio
    async def test_returns_tuple_on_success(self):
        async def a(): return 1
        async def b(): return 2
        assert await parallel(a(), b(), require="all") == (1, 2)

    @pytest.mark.asyncio
    async def test_raises_on_any_failure(self):
        async def good(): return 1
        async def bad(): raise ValueError("boom")
        with pytest.raises(Exception):
            await parallel(good(), bad(), require="all")

    @pytest.mark.asyncio
    async def test_validate_true_passes(self):
        async def a(): return 10
        result = await parallel(a(), require="all", validate=lambda rs: rs[0] > 5)
        assert result == (10,)

    @pytest.mark.asyncio
    async def test_validate_false_raises(self):
        async def a(): return 1
        with pytest.raises(ParallelValidationFailed):
            await parallel(a(), require="all", validate=lambda rs: False)


class TestParallelAny:
    @pytest.mark.asyncio
    async def test_returns_first_success(self):
        async def slow():
            await asyncio.sleep(0.05)
            return "slow"
        async def fast(): return "fast"
        result = await parallel(slow(), fast(), require="any")
        assert result == "fast"

    @pytest.mark.asyncio
    async def test_raises_when_all_fail(self):
        async def bad1(): raise ValueError("1")
        async def bad2(): raise ValueError("2")
        with pytest.raises(Exception):
            await parallel(bad1(), bad2(), require="any")


class TestParallelN:
    @pytest.mark.asyncio
    async def test_returns_n_successes(self):
        async def a(): return "a"
        async def b(): return "b"
        async def c(): return "c"
        result = await parallel(a(), b(), c(), require=2)
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_raises_when_fewer_than_n_succeed(self):
        async def ok(): return "ok"
        async def bad(): raise RuntimeError("fail")
        with pytest.raises(Exception):
            await parallel(ok(), bad(), require=2)


class TestParallelZero:
    @pytest.mark.asyncio
    async def test_collects_all_including_failures(self):
        from stratum.types import Success, Failure
        async def ok(): return "ok"
        async def bad(): raise ValueError("fail")
        results = await parallel(ok(), bad(), require=0)
        assert len(results) == 2
        successes = [r for r in results if isinstance(r, Success)]
        failures = [r for r in results if isinstance(r, Failure)]
        assert len(successes) == 1
        assert len(failures) == 1
        assert successes[0].value == "ok"
        assert isinstance(failures[0].exception, ValueError)

    @pytest.mark.asyncio
    async def test_all_succeed_no_failures_in_list(self):
        from stratum.types import Success, Failure
        async def a(): return 1
        async def b(): return 2
        results = await parallel(a(), b(), require=0)
        assert not any(isinstance(r, Failure) for r in results)
        assert all(isinstance(r, Success) for r in results)


# ---------------------------------------------------------------------------
# race
# ---------------------------------------------------------------------------

class TestRace:
    @pytest.mark.asyncio
    async def test_returns_first_success(self):
        async def slow():
            await asyncio.sleep(0.05)
            return "slow"
        async def fast(): return "fast"
        assert await race(slow(), fast()) == "fast"

    @pytest.mark.asyncio
    async def test_raises_when_all_fail(self):
        async def bad1(): raise ValueError("1")
        async def bad2(): raise ValueError("2")
        with pytest.raises(Exception):
            await race(bad1(), bad2())

    @pytest.mark.asyncio
    async def test_skips_failure_picks_subsequent_success(self):
        async def fail_first(): raise ValueError("fail")
        async def succeed(): return "winner"
        assert await race(fail_first(), succeed()) == "winner"


# ---------------------------------------------------------------------------
# debate
# ---------------------------------------------------------------------------

async def _passthrough_synth(topic, arguments, converged):
    """Simple synthesize that returns the history dict directly."""
    return {"arguments": arguments, "converged": converged}


class TestDebate:
    @pytest.mark.asyncio
    async def test_raises_on_empty_agents(self):
        with pytest.raises(ValueError, match="empty"):
            await debate(agents=[], topic="test", synthesize=_passthrough_synth)

    @pytest.mark.asyncio
    async def test_single_round_returns_history_via_synthesize(self):
        async def agent_a(topic, previous_arguments=None): return f"A: {topic}"
        async def agent_b(topic, previous_arguments=None): return f"B: {topic}"
        result = await debate(agents=[agent_a, agent_b], topic="foo", rounds=1, synthesize=_passthrough_synth)
        assert "arguments" in result
        assert "converged" in result
        assert len(result["arguments"]) == 1

    @pytest.mark.asyncio
    async def test_detects_convergence_when_identical(self):
        async def agent(topic, previous_arguments=None): return "same answer"
        result = await debate(agents=[agent, agent], topic="q", rounds=2, synthesize=_passthrough_synth)
        assert result["converged"] is True

    @pytest.mark.asyncio
    async def test_detects_non_convergence_when_different(self):
        call_n = [0]

        async def agent_a(topic, previous_arguments=None):
            call_n[0] += 1
            return f"A-{call_n[0]}"

        async def agent_b(topic, previous_arguments=None):
            return "B-always"

        result = await debate(agents=[agent_a, agent_b], topic="q", rounds=2, synthesize=_passthrough_synth)
        assert result["converged"] is False

    @pytest.mark.asyncio
    async def test_calls_synthesize_and_returns_its_result(self):
        async def agent(topic, previous_arguments=None): return "arg"

        synthesize_kwargs = {}

        async def synth(topic, arguments, converged):
            synthesize_kwargs.update({"topic": topic, "converged": converged})
            return "synthesis_result"

        result = await debate(agents=[agent], topic="t", rounds=1, synthesize=synth)
        assert result == "synthesis_result"
        assert synthesize_kwargs["topic"] == "t"

    @pytest.mark.asyncio
    async def test_passes_previous_arguments_in_rebuttal_rounds(self):
        received_previous = []

        async def agent_a(topic, previous_arguments=None):
            if previous_arguments:
                received_previous.extend(previous_arguments)
            return "A"

        async def agent_b(topic, previous_arguments=None):
            return "B"

        await debate(agents=[agent_a, agent_b], topic="q", rounds=2, synthesize=_passthrough_synth)
        assert "B" in received_previous

    @pytest.mark.asyncio
    async def test_multiple_rounds_accumulate_history(self):
        async def agent(topic, previous_arguments=None): return "arg"
        result = await debate(agents=[agent, agent], topic="t", rounds=3, synthesize=_passthrough_synth)
        assert len(result["arguments"]) == 3


# ---------------------------------------------------------------------------
# quorum (via @infer decorator)
# ---------------------------------------------------------------------------

class TestQuorum:
    @pytest.mark.asyncio
    async def test_quorum_reaches_consensus(self):
        clear_traces()

        @infer(intent="Vote", quorum=3, agree_on="label", threshold=2)
        def vote(question: str) -> Vote: ...

        mock_resp = _make_response({"label": "yes", "confidence": 0.9})

        with patch("litellm.acompletion", new=AsyncMock(return_value=mock_resp)):
            with patch("litellm.completion_cost", return_value=0.0):
                result = await vote(question="Should we do this?")

        assert result.label == "yes"

    @pytest.mark.asyncio
    async def test_quorum_raises_consensus_failure_when_no_agreement(self):
        clear_traces()

        @infer(intent="Vote", quorum=3, agree_on="label", threshold=3)
        def vote_strict(question: str) -> Vote: ...

        call_n = [0]
        responses = [
            _make_response({"label": "yes", "confidence": 0.9}),
            _make_response({"label": "no", "confidence": 0.9}),
            _make_response({"label": "yes", "confidence": 0.9}),
        ]

        async def rotating(**kwargs):
            r = responses[call_n[0] % len(responses)]
            call_n[0] += 1
            return r

        with patch("litellm.acompletion", new=rotating):
            with patch("litellm.completion_cost", return_value=0.0):
                with pytest.raises(ConsensusFailure) as exc_info:
                    await vote_strict(question="Should we?")

        assert exc_info.value.quorum == 3
        assert exc_info.value.threshold == 3

    @pytest.mark.asyncio
    async def test_quorum_returns_highest_confidence_agreeing_result(self):
        clear_traces()

        @infer(intent="Vote", quorum=3, agree_on="label", threshold=2)
        def vote(question: str) -> Vote: ...

        call_n = [0]
        responses = [
            _make_response({"label": "yes", "confidence": 0.7}),
            _make_response({"label": "yes", "confidence": 0.95}),
            _make_response({"label": "yes", "confidence": 0.8}),
        ]

        async def seq(**kwargs):
            r = responses[min(call_n[0], len(responses) - 1)]
            call_n[0] += 1
            return r

        with patch("litellm.acompletion", new=seq):
            with patch("litellm.completion_cost", return_value=0.0):
                result = await vote(question="Best choice?")

        # Should pick the highest-confidence agreeing result
        assert result.confidence == 0.95
