"""Global Stratum configuration."""

from __future__ import annotations

from typing import Any


_config: dict[str, Any] = {
    "client": None,           # uses litellm directly if None
    "review_sink": None,      # ConsoleReviewSink if None
    "tracer": None,           # None = no OTel export
    "default_model": "claude-sonnet-4-6",
    "test_mode": False,       # True → sample sample_n times for Probabilistic[T]
    "sample_n": 5,            # samples per @infer call in test_mode
}


def configure(
    client: Any = None,
    review_sink: Any = None,
    tracer: Any = None,
    default_model: str | None = None,
    test_mode: bool | None = None,
    sample_n: int | None = None,
) -> None:
    """
    Set global Stratum configuration.

    Configuration is global and set once at startup. Per-function decorator
    annotations take precedence over global defaults.
    """
    if client is not None:
        _config["client"] = client
    if review_sink is not None:
        _config["review_sink"] = review_sink
    if tracer is not None:
        _config["tracer"] = tracer
    if default_model is not None:
        _config["default_model"] = default_model
    if test_mode is not None:
        _config["test_mode"] = test_mode
    if sample_n is not None:
        _config["sample_n"] = sample_n


def get_config() -> dict[str, Any]:
    """Return the current configuration dict (mutable reference)."""
    return _config
