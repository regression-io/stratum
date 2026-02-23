"""Tests for @compute, @flow, @refine decorators and Probabilistic[T]."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from typing import Literal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from pydantic import BaseModel
from stratum.contracts import contract
from stratum.budget import Budget
from stratum.decorators import compute, flow, infer, refine
from stratum.exceptions import ConvergenceFailure, StabilityAssertionError, StratumCompileError
from stratum.trace import clear as clear_traces, all_records
from stratum.types import Probabilistic


@contract
class Category(BaseModel):
    label: Literal["a", "b", "c"]
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
# @compute
# ---------------------------------------------------------------------------

class TestComputeDecorator:
    def test_marks_function(self):
        @compute
        def add(a: int, b: int) -> int:
            return a + b

        assert add._stratum_type == "compute"

    def test_function_still_executes(self):
        @compute
        def double(x: int) -> int:
            return x * 2

        assert double(3) == 6

    def test_async_compute_executes(self):
        @compute
        async def aget(x: int) -> int:
            return x + 1

        result = asyncio.run(aget(4))
        assert result == 5


# ---------------------------------------------------------------------------
# @flow
# ---------------------------------------------------------------------------

class TestFlowDecorator:
    def test_flow_marks_function(self):
        @flow()
        async def my_flow(): ...

        assert my_flow._stratum_type == "flow"

    @pytest.mark.asyncio
    async def test_flow_returns_result(self):
        @flow()
        async def simple_flow(x: int) -> int:
            return x * 2

        assert await simple_flow(5) == 10

    @pytest.mark.asyncio
    async def test_flow_propagates_flow_id_to_infer(self):
        """@infer calls inside @flow should carry a flow_id in their trace record."""
        clear_traces()

        @infer(intent="Test")
        def classify(text: str) -> Category: ...

        mock_resp = _make_response({"label": "a", "confidence": 0.9})

        @flow()
        async def my_flow(text: str) -> Category:
            return await classify(text=text)

        with patch("litellm.acompletion", new=AsyncMock(return_value=mock_resp)):
            with patch("litellm.completion_cost", return_value=0.0):
                await my_flow(text="hello")

        records = all_records()
        assert records[-1].flow_id is not None

    @pytest.mark.asyncio
    async def test_flow_budget_inherited_by_nested_infer(self):
        """A flow-level budget is cloned and shared with nested @infer calls."""
        clear_traces()

        @infer(intent="Test")
        def classify(text: str) -> Category: ...

        @flow(budget=Budget(usd=100.0))
        async def my_flow(text: str) -> Category:
            return await classify(text=text)

        mock_resp = _make_response({"label": "b", "confidence": 0.8})

        with patch("litellm.acompletion", new=AsyncMock(return_value=mock_resp)):
            with patch("litellm.completion_cost", return_value=0.001):
                result = await my_flow(text="hello")

        assert result.label == "b"

    @pytest.mark.asyncio
    async def test_flow_context_cleared_after_completion(self):
        """Flow context should not leak between separate flow invocations."""
        from stratum.decorators import _flow_ctx

        @flow()
        async def my_flow():
            return 1

        await my_flow()
        assert _flow_ctx.get() is None


# ---------------------------------------------------------------------------
# @refine
# ---------------------------------------------------------------------------

class TestRefineDecorator:
    def test_refine_raises_if_not_stacked_on_infer(self):
        @compute
        def plain(x: str) -> str:
            return x

        with pytest.raises(StratumCompileError):
            refine(until=lambda r: True, feedback=lambda r: "")(plain)

    def test_refine_marks_function(self):
        @infer(intent="Gen")
        def gen(spec: str) -> Category: ...

        refined = refine(
            until=lambda r: r.confidence > 0.9,
            feedback=lambda r: "needs confidence",
        )(gen)

        assert refined._stratum_type == "refine"

    @pytest.mark.asyncio
    async def test_refine_returns_immediately_on_first_passing(self):
        clear_traces()

        @infer(intent="Gen")
        def gen(spec: str) -> Category: ...

        refined = refine(
            until=lambda r: r.confidence > 0.8,
            feedback=lambda r: "low confidence",
        )(gen)

        good_resp = _make_response({"label": "a", "confidence": 0.95})

        with patch("litellm.acompletion", new=AsyncMock(return_value=good_resp)):
            with patch("litellm.completion_cost", return_value=0.0):
                result = await refined(spec="test")

        assert result.confidence == 0.95

    @pytest.mark.asyncio
    async def test_refine_iterates_until_passing(self):
        """Refine calls the LLM multiple times until `until` passes."""
        clear_traces()
        call_count = [0]

        @infer(intent="Gen")
        def gen(spec: str) -> Category: ...

        async def mock_acompletion(**kwargs):
            call_count[0] += 1
            conf = 0.3 if call_count[0] < 3 else 0.95
            return _make_response({"label": "a", "confidence": conf})

        refined = refine(
            until=lambda r: r.confidence > 0.9,
            feedback=lambda r: f"confidence too low: {r.confidence}",
            max_iterations=5,
        )(gen)

        with patch("litellm.acompletion", new=mock_acompletion):
            with patch("litellm.completion_cost", return_value=0.0):
                result = await refined(spec="test")

        assert result.confidence == 0.95
        assert call_count[0] == 3

    @pytest.mark.asyncio
    async def test_refine_raises_convergence_failure_when_exhausted(self):
        clear_traces()

        @infer(intent="Gen", retries=0)
        def gen(spec: str) -> Category: ...

        bad_resp = _make_response({"label": "a", "confidence": 0.1})

        refined = refine(
            until=lambda r: r.confidence > 0.9,
            feedback=lambda r: "still low",
            max_iterations=3,
        )(gen)

        with patch("litellm.acompletion", new=AsyncMock(return_value=bad_resp)):
            with patch("litellm.completion_cost", return_value=0.0):
                with pytest.raises(ConvergenceFailure) as exc_info:
                    await refined(spec="test")

        err = exc_info.value
        assert err.max_iterations == 3
        assert len(err.history) == 3

    @pytest.mark.asyncio
    async def test_refine_injects_feedback_into_subsequent_calls(self):
        """Feedback string should appear in the context for the next iteration."""
        clear_traces()
        call_count = [0]
        captured_contexts = []

        @infer(intent="Gen")
        def gen(spec: str) -> Category: ...

        async def capturing_completion(**kwargs):
            call_count[0] += 1
            msgs = kwargs.get("messages", [])
            # Feedback is injected into the user message via the compiled prompt
            for m in msgs:
                if m["role"] == "user":
                    captured_contexts.append(m["content"])
            conf = 0.3 if call_count[0] == 1 else 0.95
            return _make_response({"label": "a", "confidence": conf})

        refined = refine(
            until=lambda r: r.confidence > 0.9,
            feedback=lambda r: "FEEDBACK_MARKER_XYZ",
            max_iterations=3,
        )(gen)

        with patch("litellm.acompletion", new=capturing_completion):
            with patch("litellm.completion_cost", return_value=0.0):
                await refined(spec="test")

        # The second call's system message should contain the feedback
        assert call_count[0] == 2
        assert any("FEEDBACK_MARKER_XYZ" in c for c in captured_contexts[1:])


# ---------------------------------------------------------------------------
# Probabilistic[T]
# ---------------------------------------------------------------------------

class TestProbabilistic:
    def test_empty_samples_raises(self):
        with pytest.raises(ValueError):
            Probabilistic([])

    def test_single_sample_most_likely(self):
        assert Probabilistic(["hello"]).most_likely() == "hello"

    def test_multi_sample_most_likely_picks_modal(self):
        p = Probabilistic(["a", "b", "a", "a", "b"])
        assert p.most_likely() == "a"

    def test_sample_returns_one_of_the_values(self):
        p = Probabilistic([1, 2, 3])
        assert p.sample() in [1, 2, 3]

    def test_assert_stable_passes_when_unanimous(self):
        p = Probabilistic(["x", "x", "x"])
        assert p.assert_stable() == "x"

    def test_assert_stable_raises_when_agreement_low(self):
        p = Probabilistic(["a", "b", "c", "d"])  # 25% agreement
        with pytest.raises(StabilityAssertionError) as exc_info:
            p.assert_stable(threshold=0.9)
        assert exc_info.value.threshold == 0.9
        assert exc_info.value.actual_agreement < 0.9

    def test_assert_stable_single_sample_always_passes(self):
        p = Probabilistic(["only"])
        assert p.assert_stable(threshold=0.99) == "only"

    @pytest.mark.asyncio
    async def test_stable_false_returns_probabilistic_instance(self):
        clear_traces()

        @infer(intent="Gen", stable=False)
        def gen(text: str) -> Category: ...

        mock_resp = _make_response({"label": "a", "confidence": 0.9})

        with patch("litellm.acompletion", new=AsyncMock(return_value=mock_resp)):
            with patch("litellm.completion_cost", return_value=0.0):
                result = await gen(text="hello")

        assert isinstance(result, Probabilistic)
        val = result.most_likely()
        assert val.label == "a"
