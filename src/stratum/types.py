"""Public type definitions: Probabilistic[T], HumanDecision[T], HumanReviewContext."""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Generic, TypeVar

T = TypeVar("T")


class Probabilistic(Generic[T]):
    """
    Return type for @infer functions declared with stable=False.

    In production mode, _samples = [single_output]; all three methods behave
    correctly with no sampling overhead.

    In test_mode, the runtime samples sample_n times and populates _samples.
    """

    def __init__(self, samples: list[T]) -> None:
        if not samples:
            raise ValueError("Probabilistic requires at least one sample")
        self._samples: list[T] = samples

    def most_likely(self) -> T:
        """
        Return the modal value across samples.

        For a single sample, returns that sample. Never raises.
        """
        if len(self._samples) == 1:
            return self._samples[0]

        from collections import Counter

        counts: Counter[str] = Counter(str(s) for s in self._samples)
        modal_str = counts.most_common(1)[0][0]
        for s in self._samples:
            if str(s) == modal_str:
                return s
        return self._samples[0]  # unreachable, satisfies type checker

    def sample(self) -> T:
        """Return a random draw from collected samples."""
        return random.choice(self._samples)

    def assert_stable(self, threshold: float = 0.9) -> T:
        """
        Raise StabilityAssertionError if sample agreement is below threshold.

        Agreement = fraction of samples that match the modal value (by str repr).
        Returns the modal value if stable.
        """
        from .exceptions import StabilityAssertionError

        if len(self._samples) <= 1:
            return self._samples[0]

        modal = self.most_likely()
        modal_str = str(modal)
        agreement = sum(1 for s in self._samples if str(s) == modal_str) / len(
            self._samples
        )
        if agreement < threshold:
            raise StabilityAssertionError(threshold, agreement)
        return modal

    def __repr__(self) -> str:
        return f"Probabilistic(samples={self._samples!r})"


@dataclass
class HumanDecision(Generic[T]):
    """
    Wraps a typed human decision with provenance metadata.

    Returned by await_human. `.value` extracts T.
    """

    value: T
    reviewer: str | None        # identity of reviewer, if provided
    rationale: str | None       # optional human note
    decided_at: datetime
    review_id: str              # stable UUID; correlates with trace record


@dataclass
class HumanReviewContext:
    """Input to await_human describing the review request."""

    question: str
    trigger: str = "explicit"           # "explicit" | "debate_disagreement" | any string
    artifacts: dict[str, Any] = field(default_factory=dict)
