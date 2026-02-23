"""Human-in-the-loop primitives: await_human, ReviewSink, ConsoleReviewSink."""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Protocol, runtime_checkable

from .exceptions import HITLTimeoutError
from .types import HumanDecision, HumanReviewContext


# ---------------------------------------------------------------------------
# PendingReview
# ---------------------------------------------------------------------------

@dataclass
class PendingReview:
    """
    Represents an in-flight review request.

    The ReviewSink receives this object and calls resolve() when the reviewer
    has made a decision.
    """

    review_id: str
    context: HumanReviewContext
    options: list[Any] | None
    expires_at: datetime | None
    _future: asyncio.Future = field(default=None, init=False, repr=False)  # type: ignore[assignment]

    async def resolve(self, decision: HumanDecision) -> None:
        """Fulfil the pending future with the human decision."""
        if self._future is not None and not self._future.done():
            self._future.set_result(decision)


# ---------------------------------------------------------------------------
# ReviewSink protocol
# ---------------------------------------------------------------------------

@runtime_checkable
class ReviewSink(Protocol):
    async def emit(self, review: PendingReview) -> None: ...


# ---------------------------------------------------------------------------
# ConsoleReviewSink (v1 default)
# ---------------------------------------------------------------------------

class ConsoleReviewSink:
    """
    Default ReviewSink. Prints the question and options to stdout, reads a
    decision from stdin (wrapped in run_in_executor so it doesn't block the
    event loop).
    """

    async def emit(self, review: PendingReview) -> None:
        print(f"\n[HITL] {review.context.question}")
        if review.options:
            for i, opt in enumerate(review.options):
                print(f"  [{i}] {opt}")

        loop = asyncio.get_event_loop()
        raw = await loop.run_in_executor(None, input, "Decision: ")
        value = self._parse(raw, review)

        decision = HumanDecision(
            value=value,
            reviewer=None,
            rationale=None,
            decided_at=datetime.utcnow(),
            review_id=review.review_id,
        )
        await review.resolve(decision)

    def _parse(self, raw: str, review: PendingReview) -> Any:
        if review.options:
            try:
                return review.options[int(raw.strip())]
            except (ValueError, IndexError):
                return raw.strip()
        return raw.strip()


# ---------------------------------------------------------------------------
# await_human
# ---------------------------------------------------------------------------

async def await_human(
    context: HumanReviewContext,
    decision_type: type,
    options: list | None = None,
    timeout: timedelta | None = None,
    on_timeout: Any = "raise",
) -> HumanDecision:
    """
    Park the calling coroutine until a human resolves the review.

    Parameters
    ----------
    context:       HumanReviewContext describing the question.
    decision_type: The expected type of decision.value (used for validation).
    options:       Optional list of choices presented to the reviewer.
    timeout:       Wall-clock timedelta. Not drawn from budget envelope.
    on_timeout:    "raise" → HITLTimeoutError; any other value → use as fallback.

    Returns
    -------
    HumanDecision[T] with the resolved value and metadata.
    """
    from ._config import get_config

    review_id = str(uuid.uuid4())
    loop = asyncio.get_event_loop()
    future: asyncio.Future = loop.create_future()

    expires_at: datetime | None = None
    if timeout is not None:
        expires_at = datetime.utcnow() + timeout

    review = PendingReview(
        review_id=review_id,
        context=context,
        options=options,
        expires_at=expires_at,
    )
    review._future = future

    sink = get_config().get("review_sink")
    if sink is None:
        sink = ConsoleReviewSink()

    await sink.emit(review)

    try:
        if timeout is not None:
            async with asyncio.timeout(timeout.total_seconds()):
                return await future
        else:
            return await future
    except asyncio.TimeoutError:
        if on_timeout == "raise":
            raise HITLTimeoutError(review_id)
        return HumanDecision(
            value=on_timeout,
            reviewer="auto",
            rationale="timeout",
            decided_at=datetime.utcnow(),
            review_id=review_id,
        )
