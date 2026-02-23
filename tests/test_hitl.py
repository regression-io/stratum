"""Tests for await_human, HITL suspension, timeout, and ReviewSink."""

from __future__ import annotations

import asyncio
import os
import sys
from datetime import datetime, timedelta

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from stratum._config import get_config
from stratum.exceptions import HITLTimeoutError
from stratum.hitl import ConsoleReviewSink, PendingReview, ReviewSink, await_human
from stratum.types import HumanDecision, HumanReviewContext


def _reset_sink():
    """Reset the review_sink config key to None after each test."""
    get_config()["review_sink"] = None


class AutoResolveSink:
    """Immediately resolves with the given value."""

    def __init__(self, value):
        self.value = value

    async def emit(self, review: PendingReview) -> None:
        decision = HumanDecision(
            value=self.value,
            reviewer="bot",
            rationale="automated",
            decided_at=datetime.utcnow(),
            review_id=review.review_id,
        )
        await review.resolve(decision)


class NeverResolveSink:
    """Never calls resolve — used to test timeouts."""

    async def emit(self, review: PendingReview) -> None:
        pass  # intentionally does nothing


# ---------------------------------------------------------------------------
# PendingReview
# ---------------------------------------------------------------------------

class TestPendingReview:
    @pytest.mark.asyncio
    async def test_resolve_fulfills_future(self):
        loop = asyncio.get_event_loop()
        future = loop.create_future()
        review = PendingReview(
            review_id="test-id",
            context=HumanReviewContext(question="Q?"),
            options=None,
            expires_at=None,
        )
        review._future = future

        decision = HumanDecision(
            value="approved",
            reviewer="alice",
            rationale="looks good",
            decided_at=datetime.utcnow(),
            review_id="test-id",
        )
        await review.resolve(decision)

        assert future.result() is decision

    @pytest.mark.asyncio
    async def test_resolve_noop_when_future_already_done(self):
        loop = asyncio.get_event_loop()
        future = loop.create_future()
        future.set_result("already_done")

        review = PendingReview(
            review_id="test-id",
            context=HumanReviewContext(question="Q?"),
            options=None,
            expires_at=None,
        )
        review._future = future

        decision = HumanDecision(
            value="new",
            reviewer=None,
            rationale=None,
            decided_at=datetime.utcnow(),
            review_id="test-id",
        )
        # Should not raise even though future is already resolved
        await review.resolve(decision)
        assert future.result() == "already_done"


# ---------------------------------------------------------------------------
# await_human
# ---------------------------------------------------------------------------

class TestAwaitHuman:
    @pytest.mark.asyncio
    async def test_resolves_via_custom_sink(self):
        get_config()["review_sink"] = AutoResolveSink("auto_approved")
        try:
            ctx = HumanReviewContext(question="Approve?", trigger="explicit")
            result = await await_human(ctx, decision_type=str)
            assert result.value == "auto_approved"
            assert result.reviewer == "bot"
        finally:
            _reset_sink()

    @pytest.mark.asyncio
    async def test_returns_human_decision_type(self):
        get_config()["review_sink"] = AutoResolveSink(42)
        try:
            ctx = HumanReviewContext(question="Pick a number")
            result = await await_human(ctx, decision_type=int)
            assert isinstance(result, HumanDecision)
            assert result.value == 42
        finally:
            _reset_sink()

    @pytest.mark.asyncio
    async def test_review_id_is_stable_on_result(self):
        get_config()["review_sink"] = AutoResolveSink("ok")
        try:
            ctx = HumanReviewContext(question="Q?")
            result = await await_human(ctx, decision_type=str)
            assert result.review_id is not None
            assert len(result.review_id) > 0
        finally:
            _reset_sink()

    @pytest.mark.asyncio
    async def test_timeout_raises_hitl_timeout_error(self):
        get_config()["review_sink"] = NeverResolveSink()
        try:
            ctx = HumanReviewContext(question="Will you answer?")
            with pytest.raises(HITLTimeoutError) as exc_info:
                await await_human(
                    ctx,
                    decision_type=str,
                    timeout=timedelta(milliseconds=50),
                    on_timeout="raise",
                )
            assert exc_info.value.review_id is not None
        finally:
            _reset_sink()

    @pytest.mark.asyncio
    async def test_timeout_returns_fallback_value(self):
        get_config()["review_sink"] = NeverResolveSink()
        try:
            ctx = HumanReviewContext(question="Will you answer?")
            result = await await_human(
                ctx,
                decision_type=str,
                timeout=timedelta(milliseconds=50),
                on_timeout="default_answer",
            )
            assert result.value == "default_answer"
            assert result.reviewer == "auto"
            assert result.rationale == "timeout"
        finally:
            _reset_sink()

    @pytest.mark.asyncio
    async def test_passes_options_to_sink(self):
        received_options = []

        class CapturingSink:
            async def emit(self, review: PendingReview) -> None:
                received_options.extend(review.options or [])
                await review.resolve(
                    HumanDecision(
                        value=review.options[0] if review.options else None,
                        reviewer=None,
                        rationale=None,
                        decided_at=datetime.utcnow(),
                        review_id=review.review_id,
                    )
                )

        get_config()["review_sink"] = CapturingSink()
        try:
            ctx = HumanReviewContext(question="Choose:")
            await await_human(ctx, decision_type=str, options=["yes", "no"])
            assert received_options == ["yes", "no"]
        finally:
            _reset_sink()

    @pytest.mark.asyncio
    async def test_context_fields_forwarded_to_sink(self):
        received_contexts = []

        class CapturingCtxSink:
            async def emit(self, review: PendingReview) -> None:
                received_contexts.append(review.context)
                await review.resolve(
                    HumanDecision(
                        value="ok",
                        reviewer=None,
                        rationale=None,
                        decided_at=datetime.utcnow(),
                        review_id=review.review_id,
                    )
                )

        get_config()["review_sink"] = CapturingCtxSink()
        try:
            ctx = HumanReviewContext(
                question="Is this correct?",
                trigger="debate_disagreement",
                artifacts={"key": "value"},
            )
            await await_human(ctx, decision_type=str)
            assert received_contexts[0].question == "Is this correct?"
            assert received_contexts[0].trigger == "debate_disagreement"
            assert received_contexts[0].artifacts == {"key": "value"}
        finally:
            _reset_sink()


# ---------------------------------------------------------------------------
# ReviewSink protocol
# ---------------------------------------------------------------------------

class TestReviewSinkProtocol:
    def test_console_sink_implements_protocol(self):
        assert isinstance(ConsoleReviewSink(), ReviewSink)

    def test_custom_class_implements_protocol(self):
        class MySink:
            async def emit(self, review: PendingReview) -> None:
                pass

        assert isinstance(MySink(), ReviewSink)

    def test_object_without_emit_does_not_implement_protocol(self):
        class NotASink:
            pass

        assert not isinstance(NotASink(), ReviewSink)
