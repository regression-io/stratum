"""
T1-11: End-to-end validation against a real LLM.

Uses OPENAI_API_KEY (gpt-4o-mini) if available, falls back to other providers.
Skipped entirely if no supported API key is set.

Validates:
- @infer with a typed @contract return type makes a real LLM call and parses the response
- @flow propagates flow_id to nested @infer calls
- ensure postconditions are enforced; PostconditionFailed raised on exhaustion
- @compute within a @flow is called deterministically (no LLM)
- TraceRecord fields are populated correctly after a real call
- stratum.run() sync shim works from a non-async context
"""

from __future__ import annotations

import os
import pytest
import asyncio
from pydantic import BaseModel

import stratum
from stratum import (
    infer, compute, flow, contract, configure,
    run, all_records, clear_traces,
)
from stratum.exceptions import PostconditionFailed


# ---------------------------------------------------------------------------
# Provider selection — pick the first available key
# ---------------------------------------------------------------------------

def _select_model() -> str | None:
    if os.environ.get("OPENAI_API_KEY"):
        return "gpt-4o-mini"
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "claude-haiku-4-5-20251001"
    if os.environ.get("GEMINI_API_KEY"):
        return "gemini/gemini-1.5-flash"
    if os.environ.get("OPENROUTER_API_KEY"):
        return "openrouter/openai/gpt-4o-mini"
    return None


_MODEL = _select_model()

pytestmark = pytest.mark.skipif(
    _MODEL is None,
    reason="No supported LLM API key set (OPENAI_API_KEY, ANTHROPIC_API_KEY, GEMINI_API_KEY, OPENROUTER_API_KEY)",
)


# ---------------------------------------------------------------------------
# Contracts
# ---------------------------------------------------------------------------

@contract
class Sentiment(BaseModel):
    label: str       # "positive", "negative", or "neutral"
    confidence: float  # 0.0–1.0


@contract
class WordCount(BaseModel):
    count: int
    longest_word: str


# ---------------------------------------------------------------------------
# Annotated functions
# ---------------------------------------------------------------------------

@infer(
    intent=(
        "Classify the sentiment of the text. "
        "label must be exactly 'positive', 'negative', or 'neutral'. "
        "confidence must be between 0.0 and 1.0."
    ),
    ensure=[
        lambda r: r.label in ("positive", "negative", "neutral"),
        lambda r: 0.0 <= r.confidence <= 1.0,
    ],
    retries=2,
)
def classify_sentiment(text: str) -> Sentiment: ...


@infer(
    intent="Return the number of words in the text and the longest word.",
    retries=2,
)
def count_words(text: str) -> WordCount: ...


@infer(
    intent="Write a one-sentence summary of the text.",
    retries=1,
)
def summarize(text: str) -> str: ...


@compute
def is_positive(sentiment: Sentiment) -> bool:
    return sentiment.label == "positive"


@flow()
async def analyze(text: str) -> dict:
    sentiment = await classify_sentiment(text=text)
    positive = is_positive(sentiment)
    summary = await summarize(text=text)
    return {"sentiment": sentiment, "positive": positive, "summary": summary}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestE2E:
    def setup_method(self):
        clear_traces()
        configure(default_model=_MODEL)

    # --- @infer basic call ---

    def test_infer_returns_typed_contract(self):
        result = run(classify_sentiment(text="I love this product!"))
        assert isinstance(result, Sentiment)
        assert result.label in ("positive", "negative", "neutral")
        assert 0.0 <= result.confidence <= 1.0

    def test_infer_positive_text_returns_positive(self):
        result = run(classify_sentiment(text="Absolutely wonderful experience!"))
        assert result.label == "positive"

    def test_infer_negative_text_returns_negative(self):
        result = run(classify_sentiment(text="Terrible. Completely broken and unusable."))
        assert result.label == "negative"

    def test_infer_structured_numeric_fields(self):
        result = run(count_words(text="The quick brown fox"))
        assert isinstance(result, WordCount)
        assert result.count == 4
        assert isinstance(result.longest_word, str)
        assert len(result.longest_word) > 0

    def test_infer_primitive_string_return(self):
        result = run(summarize(text="The quick brown fox jumps over the lazy dog."))
        assert isinstance(result, str)
        assert len(result) > 10

    # --- ensure postconditions ---

    def test_ensure_passes_on_valid_output(self):
        # Should not raise — both ensures are satisfiable
        result = run(classify_sentiment(text="Great!"))
        assert result.label in ("positive", "negative", "neutral")

    def test_postcondition_failed_raised_on_exhaustion(self):
        @infer(
            intent="Classify sentiment.",
            ensure=[lambda r: False],  # always fails
            retries=1,
        )
        def always_fails(text: str) -> Sentiment: ...

        with pytest.raises(PostconditionFailed):
            run(always_fails(text="any text"))

    # --- @compute is deterministic ---

    def test_compute_does_not_call_llm(self):
        before = len(all_records())
        sentiment = Sentiment(label="positive", confidence=0.9)
        result = is_positive(sentiment)
        after = len(all_records())
        assert result is True
        assert after == before  # @compute produces no trace record

    def test_compute_negative_returns_false(self):
        assert is_positive(Sentiment(label="negative", confidence=0.8)) is False

    # --- @flow ---

    def test_flow_returns_combined_result(self):
        result = run(analyze(text="I really enjoyed this!"))
        assert "sentiment" in result
        assert "positive" in result
        assert "summary" in result
        assert isinstance(result["sentiment"], Sentiment)
        assert isinstance(result["positive"], bool)
        assert isinstance(result["summary"], str)

    def test_flow_positive_text_sets_positive_flag(self):
        result = run(analyze(text="Best day ever!"))
        assert result["positive"] is True

    def test_flow_nested_infer_shares_flow_id(self):
        run(analyze(text="Amazing!"))
        records = all_records()
        flow_ids = {r.flow_id for r in records if r.flow_id is not None}
        # All @infer calls within the @flow share the same flow_id
        assert len(flow_ids) == 1

    # --- TraceRecord ---

    def test_trace_record_populated(self):
        run(classify_sentiment(text="This is great."))
        records = all_records()
        assert len(records) == 1
        rec = records[0]
        assert "classify_sentiment" in rec.function
        assert rec.model == _MODEL
        assert rec.duration_ms > 0
        assert rec.attempts >= 1
        assert isinstance(rec.output, Sentiment)
        assert rec.flow_id is None  # called outside a @flow

    def test_trace_records_accumulate(self):
        run(classify_sentiment(text="Good."))
        run(classify_sentiment(text="Bad."))
        assert len(all_records()) == 2

    def test_clear_traces(self):
        run(classify_sentiment(text="Hello."))
        assert len(all_records()) == 1
        clear_traces()
        assert len(all_records()) == 0

    # --- stratum.run() sync shim ---

    def test_run_sync_shim_returns_result(self):
        result = stratum.run(classify_sentiment(text="Lovely day!"))
        assert isinstance(result, Sentiment)

    def test_run_sync_shim_raises_on_running_loop(self):
        async def _inner():
            with pytest.raises(RuntimeError, match="running event loop"):
                stratum.run(classify_sentiment(text="test"))
        asyncio.run(_inner())
