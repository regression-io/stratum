"""Budget dataclass — time and cost envelope for @infer and @flow calls."""

from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class Budget:
    """
    Declares a time and/or cost budget for an @infer or @flow invocation.

    Either or both of `ms` and `usd` may be specified. Unspecified axes are
    unbounded.
    """

    ms: int | None = None       # wall-clock milliseconds
    usd: float | None = None    # cost ceiling in USD

    # Runtime tracking — not part of the public API, not shown in repr
    _start_ms: float = field(
        default_factory=lambda: time.monotonic() * 1000,
        init=False,
        repr=False,
        compare=False,
    )
    _spent_usd: float = field(
        default=0.0,
        init=False,
        repr=False,
        compare=False,
    )

    def remaining_seconds(self) -> float | None:
        """
        Return remaining wall-clock time in seconds, or None if no ms limit.
        Returns 0.0 if the budget is already exhausted.
        """
        if self.ms is None:
            return None
        elapsed_ms = (time.monotonic() * 1000) - self._start_ms
        remaining_ms = self.ms - elapsed_ms
        return max(0.0, remaining_ms / 1000.0)

    def record_cost(self, usd: float) -> None:
        """Accumulate a cost charge against this budget."""
        self._spent_usd += usd

    def is_cost_exceeded(self) -> bool:
        """Return True if cumulative cost has reached or exceeded the usd ceiling."""
        if self.usd is None:
            return False
        return self._spent_usd >= self.usd

    def clone(self) -> Budget:
        """
        Create a fresh budget with the same limits, resetting the elapsed clock
        and spent cost to zero. Used by @flow to create a per-execution envelope.
        """
        return Budget(ms=self.ms, usd=self.usd)
