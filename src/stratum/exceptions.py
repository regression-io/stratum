"""Stratum exception hierarchy."""

from typing import Any


class StratumError(Exception):
    """Base class for all Stratum errors."""


class StratumCompileError(StratumError):
    """Raised for static analysis violations detected at decoration or invocation time."""


class PreconditionFailed(StratumError):
    """Raised when a `given` condition evaluates to False before the LLM is invoked."""

    def __init__(self, function_name: str, condition: str) -> None:
        self.function_name = function_name
        self.condition = condition
        super().__init__(
            f"Precondition failed in '{function_name}': {condition}"
        )


class PostconditionFailed(StratumError):
    """Raised when all retries are exhausted with unresolved `ensure` violations."""

    def __init__(
        self,
        function_name: str,
        violations: list[str],
        retry_history: list[list[str]],
    ) -> None:
        self.function_name = function_name
        self.violations = violations
        self.retry_history = retry_history
        super().__init__(
            f"Postcondition failed in '{function_name}' after {len(retry_history)} attempts: "
            + "; ".join(violations)
        )


class ParseFailure(StratumError):
    """Raised when the LLM output cannot be parsed against the contract schema."""

    def __init__(self, function_name: str, raw_output: str, error_message: str) -> None:
        self.function_name = function_name
        self.raw_output = raw_output
        self.error_message = error_message
        super().__init__(
            f"Parse failure in '{function_name}': {error_message}"
        )


class BudgetExceeded(StratumError):
    """Raised when a time or cost budget is exceeded."""

    def __init__(self, function_name: str, budget: Any) -> None:
        self.function_name = function_name
        self.budget = budget
        super().__init__(
            f"Budget exceeded in '{function_name}': {budget!r}"
        )


class ConvergenceFailure(StratumError):
    """Raised when `@refine` exhausts `max_iterations` without `until` returning True."""

    def __init__(
        self,
        function_name: str,
        max_iterations: int,
        history: list[Any],
    ) -> None:
        self.function_name = function_name
        self.max_iterations = max_iterations
        self.history = history
        super().__init__(
            f"Convergence failure in '{function_name}': did not converge after {max_iterations} iterations"
        )


class ConsensusFailure(StratumError):
    """Raised when `quorum` cannot reach `threshold` agreement."""

    def __init__(
        self,
        function_name: str,
        quorum: int,
        threshold: int,
        all_outputs: list[Any],
    ) -> None:
        self.function_name = function_name
        self.quorum = quorum
        self.threshold = threshold
        self.all_outputs = all_outputs
        super().__init__(
            f"Consensus failure in '{function_name}': {quorum} invocations, "
            f"needed {threshold} agreeing, got insufficient agreement"
        )


class ParallelValidationFailed(StratumError):
    """Raised when `stratum.parallel` `validate` callback returns False."""

    def __init__(self, message: str = "Parallel validation failed") -> None:
        super().__init__(message)


class HITLTimeoutError(StratumError):
    """Raised when `await_human` wall-clock timeout expires and on_timeout='raise'."""

    def __init__(self, review_id: str) -> None:
        self.review_id = review_id
        super().__init__(f"HITL timeout for review_id={review_id!r}")


class StabilityAssertionError(StratumError):
    """Raised when `Probabilistic[T].assert_stable()` is below threshold."""

    def __init__(self, threshold: float, actual_agreement: float) -> None:
        self.threshold = threshold
        self.actual_agreement = actual_agreement
        super().__init__(
            f"Stability assertion failed: required {threshold:.0%}, got {actual_agreement:.0%}"
        )
