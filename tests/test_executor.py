"""Tests for stratum executor — @infer execution loop with mocked litellm."""

from __future__ import annotations

import asyncio
import json
import sys
import os
from typing import Literal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from pydantic import BaseModel
from stratum.contracts import contract, get_schema, get_hash
from stratum.budget import Budget
from stratum.decorators import infer
from stratum.exceptions import (
    BudgetExceeded,
    ParseFailure,
    PostconditionFailed,
    PreconditionFailed,
)
from stratum.executor import InferSpec, execute_infer
from stratum.trace import clear as clear_traces, all_records


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@contract
class Sentiment(BaseModel):
    label: Literal["positive", "negative", "neutral"]
    confidence: float
    reasoning: str


def _make_response(data: dict) -> MagicMock:
    """Build a fake litellm completion response with a tool call."""
    tool_call = MagicMock()
    tool_call.function.arguments = json.dumps(data)

    message = MagicMock()
    message.tool_calls = [tool_call]

    choice = MagicMock()
    choice.message = message

    response = MagicMock()
    response.choices = [choice]
    response.usage = MagicMock(prompt_tokens=50, completion_tokens=20)

    return response


def _make_spec(
    fn,
    return_type=Sentiment,
    ensure=None,
    given=None,
    retries=3,
    budget=None,
    stable=True,
) -> InferSpec:
    from typing import get_type_hints

    ensure_list = ensure if ensure is not None else []
    given_list = given if given is not None else []

    return InferSpec(
        fn=fn,
        intent="Test intent",
        context=[],
        ensure=ensure_list,
        given=given_list,
        model="claude-sonnet-4-6",
        temperature=None,
        budget=budget,
        retries=retries,
        cache="none",
        stable=stable,
        quorum=None,
        agree_on=None,
        threshold=None,
        return_type=return_type,
        parameters={},
    )


# ---------------------------------------------------------------------------
# 1. Successful @infer call returns typed result
# ---------------------------------------------------------------------------

class TestSuccessfulInfer:
    @pytest.mark.asyncio
    async def test_returns_typed_contract_instance(self):
        clear_traces()

        async def my_fn(text: str) -> Sentiment: ...

        spec = _make_spec(my_fn)
        good_data = {
            "label": "positive",
            "confidence": 0.95,
            "reasoning": "Very positive tone",
        }
        mock_response = _make_response(good_data)

        with patch("litellm.acompletion", new=AsyncMock(return_value=mock_response)):
            with patch("litellm.completion_cost", return_value=0.001):
                result = await execute_infer(spec, {"text": "Great product!"})

        assert result.label == "positive"
        assert result.confidence == 0.95
        assert result.reasoning == "Very positive tone"

    @pytest.mark.asyncio
    async def test_trace_record_written_on_success(self):
        clear_traces()

        async def traced_fn(text: str) -> Sentiment: ...

        spec = _make_spec(traced_fn)
        mock_response = _make_response(
            {"label": "neutral", "confidence": 0.8, "reasoning": "Neutral tone"}
        )

        with patch("litellm.acompletion", new=AsyncMock(return_value=mock_response)):
            with patch("litellm.completion_cost", return_value=0.0):
                await execute_infer(spec, {"text": "Okay product"})

        records = all_records()
        assert len(records) >= 1
        last = records[-1]
        assert last.attempts == 1
        assert last.cache_hit is False

    @pytest.mark.asyncio
    async def test_infer_decorator_wraps_correctly(self):
        clear_traces()

        @infer(
            intent="Classify sentiment",
            context="Be accurate",
        )
        def classify(text: str) -> Sentiment: ...

        mock_response = _make_response(
            {"label": "negative", "confidence": 0.88, "reasoning": "Negative tone"}
        )

        with patch("litellm.acompletion", new=AsyncMock(return_value=mock_response)):
            with patch("litellm.completion_cost", return_value=0.0):
                result = await classify(text="Terrible product!")

        assert result.label == "negative"


# ---------------------------------------------------------------------------
# 2. ensure violation triggers retry
# ---------------------------------------------------------------------------

class TestEnsureViolationRetry:
    @pytest.mark.asyncio
    async def test_ensure_violation_retries(self):
        clear_traces()

        async def high_confidence_fn(text: str) -> Sentiment: ...

        spec = _make_spec(
            high_confidence_fn,
            ensure=[lambda r: r.confidence > 0.9],
            retries=2,
        )

        # First response: low confidence (fails ensure)
        low_confidence = _make_response(
            {"label": "positive", "confidence": 0.5, "reasoning": "Low confidence"}
        )
        # Second response: high confidence (passes ensure)
        high_confidence = _make_response(
            {"label": "positive", "confidence": 0.95, "reasoning": "High confidence"}
        )

        responses = [low_confidence, high_confidence]
        call_count = 0

        async def mock_completion(**kwargs):
            nonlocal call_count
            resp = responses[min(call_count, len(responses) - 1)]
            call_count += 1
            return resp

        with patch("litellm.acompletion", new=mock_completion):
            with patch("litellm.completion_cost", return_value=0.0):
                result = await execute_infer(spec, {"text": "Good product"})

        assert result.confidence == 0.95
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_retry_injects_failure_context(self):
        """Verify that the prompt on retry contains violation info."""
        clear_traces()
        captured_messages = []

        async def strict_fn(text: str) -> Sentiment: ...

        spec = _make_spec(
            strict_fn,
            ensure=[lambda r: r.confidence > 0.9],
            retries=1,
        )

        low = _make_response(
            {"label": "positive", "confidence": 0.3, "reasoning": "Low"}
        )
        high = _make_response(
            {"label": "positive", "confidence": 0.95, "reasoning": "High"}
        )
        responses = [low, high]
        call_count = 0

        async def capturing_completion(**kwargs):
            nonlocal call_count
            captured_messages.append(kwargs.get("messages", []))
            resp = responses[min(call_count, 1)]
            call_count += 1
            return resp

        with patch("litellm.acompletion", new=capturing_completion):
            with patch("litellm.completion_cost", return_value=0.0):
                await execute_infer(spec, {"text": "test"})

        # Second call should have retry context in user message
        assert len(captured_messages) == 2
        raw = next(m["content"] for m in captured_messages[1] if m["role"] == "user")
        second_user_msg = (
            " ".join(b.get("text", "") for b in raw if isinstance(b, dict))
            if isinstance(raw, list) else raw
        )
        assert "Previous attempt failed" in second_user_msg or "failed" in second_user_msg.lower()


# ---------------------------------------------------------------------------
# 3. BudgetExceeded raised when cost exceeded
# ---------------------------------------------------------------------------

class TestBudgetExceeded:
    @pytest.mark.asyncio
    async def test_cost_budget_exceeded_raises(self):
        clear_traces()

        async def expensive_fn(text: str) -> Sentiment: ...

        # Budget of $0.001 — first call charges $0.005, exceeding the budget.
        # The ensure condition always fails so the retry loop runs.
        # On attempt 1, the budget cost check fires before the LLM call.
        budget = Budget(usd=0.001)
        spec = _make_spec(
            expensive_fn,
            budget=budget,
            retries=3,
            ensure=[lambda r: False],  # always fail ensure so we retry
        )

        high_cost_response = _make_response(
            {"label": "positive", "confidence": 0.5, "reasoning": ""}
        )

        async def mock_expensive(**kwargs):
            return high_cost_response

        with patch("litellm.acompletion", new=mock_expensive):
            with patch("litellm.completion_cost", return_value=0.005):  # exceeds $0.001
                with pytest.raises(BudgetExceeded):
                    await execute_infer(spec, {"text": "test"})

    @pytest.mark.asyncio
    async def test_timeout_budget_raises_budget_exceeded(self):
        clear_traces()

        async def slow_fn(text: str) -> Sentiment: ...

        budget = Budget(ms=1)  # 1ms — will expire immediately
        spec = _make_spec(slow_fn, budget=budget, retries=0)

        async def slow_completion(**kwargs):
            await asyncio.sleep(1)  # much longer than 1ms budget
            return _make_response({"label": "positive", "confidence": 0.9, "reasoning": ""})

        with patch("litellm.acompletion", new=slow_completion):
            with pytest.raises(BudgetExceeded):
                await execute_infer(spec, {"text": "test"})


# ---------------------------------------------------------------------------
# 4. PostconditionFailed raised after max retries
# ---------------------------------------------------------------------------

class TestPostconditionFailed:
    @pytest.mark.asyncio
    async def test_postcondition_failed_after_exhausted_retries(self):
        clear_traces()

        async def always_low_fn(text: str) -> Sentiment: ...

        spec = _make_spec(
            always_low_fn,
            ensure=[lambda r: r.confidence > 0.9],
            retries=2,
        )

        # Always returns low confidence — will never pass ensure
        low_response = _make_response(
            {"label": "positive", "confidence": 0.1, "reasoning": "low"}
        )

        with patch("litellm.acompletion", new=AsyncMock(return_value=low_response)):
            with patch("litellm.completion_cost", return_value=0.0):
                with pytest.raises(PostconditionFailed) as exc_info:
                    await execute_infer(spec, {"text": "test"})

        err = exc_info.value
        assert err.function_name == "always_low_fn"
        assert len(err.violations) > 0
        # retries=2 → 3 total attempts, each producing a violation entry
        assert len(err.retry_history) == 3

    @pytest.mark.asyncio
    async def test_postcondition_failed_includes_all_violation_history(self):
        clear_traces()

        async def failing_fn(text: str) -> Sentiment: ...

        spec = _make_spec(
            failing_fn,
            ensure=[lambda r: r.confidence > 0.99],
            retries=1,
        )

        bad_response = _make_response(
            {"label": "neutral", "confidence": 0.5, "reasoning": "meh"}
        )

        with patch("litellm.acompletion", new=AsyncMock(return_value=bad_response)):
            with patch("litellm.completion_cost", return_value=0.0):
                with pytest.raises(PostconditionFailed) as exc_info:
                    await execute_infer(spec, {"text": "test"})

        err = exc_info.value
        # With retries=1, we get 2 attempts total
        assert len(err.retry_history) == 2


# ---------------------------------------------------------------------------
# 5. ParseFailure raised when all retries fail at parse stage
# ---------------------------------------------------------------------------

class TestParseFailure:
    @pytest.mark.asyncio
    async def test_parse_failure_raised_when_llm_returns_no_tool_call(self):
        clear_traces()

        async def parse_fn(text: str) -> Sentiment: ...

        spec = _make_spec(parse_fn, retries=2)

        # Response with no tool calls at all
        bad_response = MagicMock()
        message = MagicMock()
        message.tool_calls = []
        choice = MagicMock()
        choice.message = message
        bad_response.choices = [choice]
        bad_response.usage = MagicMock(prompt_tokens=10, completion_tokens=0)

        with patch("litellm.acompletion", new=AsyncMock(return_value=bad_response)):
            with patch("litellm.completion_cost", return_value=0.0):
                with pytest.raises(ParseFailure) as exc_info:
                    await execute_infer(spec, {"text": "test"})

        assert exc_info.value.function_name == "parse_fn"

    @pytest.mark.asyncio
    async def test_postcondition_raised_when_final_failure_is_ensure_violation(self):
        """Ensure PostconditionFailed (not ParseFailure) when last attempt fails ensure."""
        clear_traces()

        async def mixed_fn(text: str) -> Sentiment: ...

        spec = _make_spec(
            mixed_fn,
            ensure=[lambda r: r.confidence > 0.9],
            retries=1,
        )

        # Always returns low confidence — ensure violation on both attempts
        low_response = _make_response(
            {"label": "positive", "confidence": 0.1, "reasoning": "low"}
        )

        with patch("litellm.acompletion", new=AsyncMock(return_value=low_response)):
            with patch("litellm.completion_cost", return_value=0.0):
                with pytest.raises(PostconditionFailed):
                    await execute_infer(spec, {"text": "test"})


# ---------------------------------------------------------------------------
# 6. Session cache scoped to @flow
# ---------------------------------------------------------------------------

class TestSessionCacheScoping:
    @pytest.mark.asyncio
    async def test_session_cache_isolated_between_flows(self):
        """Two separate @flow executions must not share session cache."""
        from stratum.decorators import flow, infer as infer_decorator
        from stratum.trace import clear as clear_traces

        clear_traces()
        call_count = 0

        @contract
        class CountResult(BaseModel):
            count: int

        good_data = {"count": 1}
        mock_response = _make_response(good_data)

        async def count_fn(x: int) -> CountResult: ...

        spec = InferSpec(
            fn=count_fn,
            intent="count",
            context=[],
            ensure=[],
            given=[],
            model="claude-sonnet-4-6",
            temperature=None,
            budget=None,
            retries=0,
            cache="session",
            stable=True,
            quorum=None,
            agree_on=None,
            threshold=None,
            return_type=CountResult,
            parameters={},
        )

        @flow()
        async def flow_with_two_calls():
            # Same inputs called twice within one flow execution — 2nd should be a cache hit
            r1 = await execute_infer(spec, {"x": 1})
            r2 = await execute_infer(spec, {"x": 1})
            return r1, r2

        @flow()
        async def flow_separate():
            # Separate flow execution — must not inherit cache from above
            return await execute_infer(spec, {"x": 1})

        with patch("litellm.acompletion", new=AsyncMock(return_value=mock_response)) as mock_llm:
            with patch("litellm.completion_cost", return_value=0.0):
                # 1st flow: 2 calls but same inputs → 1 LLM hit + 1 cache hit
                await flow_with_two_calls()
                # 2nd flow: separate context → must call LLM again (no shared cache)
                await flow_separate()

        # Exactly 2 LLM calls: one per flow execution (second call in first flow is cached)
        assert mock_llm.call_count == 2


# ---------------------------------------------------------------------------
# 7. PreconditionFailed raised immediately on given failure
# ---------------------------------------------------------------------------

class TestPreconditionFailed:
    @pytest.mark.asyncio
    async def test_given_false_raises_immediately(self):
        clear_traces()

        async def guarded_fn(text: str) -> Sentiment: ...

        spec = _make_spec(
            guarded_fn,
            given=[lambda text: len(text) > 0],
        )

        llm_called = False

        async def should_not_be_called(**kwargs):
            nonlocal llm_called
            llm_called = True
            return _make_response({"label": "positive", "confidence": 0.9, "reasoning": ""})

        with patch("litellm.acompletion", new=should_not_be_called):
            with pytest.raises(PreconditionFailed) as exc_info:
                await execute_infer(spec, {"text": ""})  # empty text fails len > 0

        assert not llm_called
        assert exc_info.value.function_name == "guarded_fn"

    @pytest.mark.asyncio
    async def test_given_passes_proceeds_to_llm(self):
        clear_traces()

        async def guarded_fn(text: str) -> Sentiment: ...

        spec = _make_spec(
            guarded_fn,
            given=[lambda text: len(text) > 0],
        )

        mock_response = _make_response(
            {"label": "positive", "confidence": 0.9, "reasoning": "good"}
        )

        with patch("litellm.acompletion", new=AsyncMock(return_value=mock_response)):
            with patch("litellm.completion_cost", return_value=0.0):
                result = await execute_infer(spec, {"text": "Hello!"})

        assert result.label == "positive"

    @pytest.mark.asyncio
    async def test_given_exception_wraps_in_precondition_failed(self):
        clear_traces()

        async def guarded_fn(text: str) -> Sentiment: ...

        def bad_given(text: str) -> bool:
            raise ValueError("something went wrong in given")

        spec = _make_spec(guarded_fn, given=[bad_given])

        with patch("litellm.acompletion", new=AsyncMock()):
            with pytest.raises(PreconditionFailed):
                await execute_infer(spec, {"text": "hello"})


# ---------------------------------------------------------------------------
# 6. @infer decorator integration
# ---------------------------------------------------------------------------

class TestInferDecorator:
    def test_infer_decorator_adds_stratum_type(self):
        @infer(intent="Test")
        def my_fn(x: str) -> Sentiment: ...

        assert my_fn._stratum_type == "infer"

    def test_infer_decorator_adds_spec(self):
        @infer(intent="Test intent", retries=2)
        def my_fn2(x: str) -> Sentiment: ...

        assert hasattr(my_fn2, "_stratum_spec")
        assert my_fn2._stratum_spec.intent == "Test intent"
        assert my_fn2._stratum_spec.retries == 2

    def test_infer_quorum_without_agree_on_raises(self):
        from stratum.exceptions import StratumCompileError

        with pytest.raises(StratumCompileError):
            @infer(intent="Test", quorum=3)  # missing agree_on and threshold
            def bad_fn(x: str) -> Sentiment: ...

    @pytest.mark.asyncio
    async def test_infer_with_primitive_return_type(self):
        clear_traces()

        @infer(intent="Return a label")
        def label_fn(text: str) -> str: ...

        # Primitive return types get wrapped in {"value": ...}
        mock_response = _make_response({"value": "positive"})

        with patch("litellm.acompletion", new=AsyncMock(return_value=mock_response)):
            with patch("litellm.completion_cost", return_value=0.0):
                result = await label_fn(text="good day")

        assert result == "positive"


# ---------------------------------------------------------------------------
# Prompt cache injection
# ---------------------------------------------------------------------------

@contract
class _CacheOut(BaseModel):
    value: str


class TestPromptCache:
    @pytest.mark.asyncio
    async def test_anthropic_model_injects_cache_control(self):
        """Claude models should get cache_control on system, tool, and user stable block."""
        clear_traces()
        captured = {}

        @infer(intent="Test intent", context="some context", model="claude-sonnet-4-6")
        def fn_claude(text: str) -> _CacheOut: ...

        async def capture(**kwargs):
            captured["messages"] = kwargs["messages"]
            captured["tools"] = kwargs["tools"]
            return _make_response({"value": "ok"})

        with patch("litellm.acompletion", new=capture):
            with patch("litellm.completion_cost", return_value=0.0):
                await fn_claude(text="hi")

        # System message should be a content list with cache_control
        sys_content = captured["messages"][0]["content"]
        assert isinstance(sys_content, list)
        assert sys_content[0].get("cache_control") == {"type": "ephemeral"}

        # User message should be a list with at least the stable block cached
        user_content = captured["messages"][1]["content"]
        assert isinstance(user_content, list)
        assert user_content[0].get("cache_control") == {"type": "ephemeral"}

        # Tool should have cache_control at the top level
        assert captured["tools"][0].get("cache_control") == {"type": "ephemeral"}

    @pytest.mark.asyncio
    async def test_non_anthropic_model_no_cache_control(self):
        """Non-Anthropic models should use plain string content — no cache_control."""
        clear_traces()
        captured = {}

        @infer(intent="Test", model="gpt-4o")
        def fn_openai(text: str) -> _CacheOut: ...

        async def capture(**kwargs):
            captured["messages"] = kwargs["messages"]
            captured["tools"] = kwargs["tools"]
            return _make_response({"value": "ok"})

        with patch("litellm.acompletion", new=capture):
            with patch("litellm.completion_cost", return_value=0.0):
                await fn_openai(text="hi")

        assert isinstance(captured["messages"][0]["content"], str)
        assert isinstance(captured["messages"][1]["content"], str)
        assert "cache_control" not in captured["tools"][0]
