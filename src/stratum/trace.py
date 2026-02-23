"""In-memory trace record store for @infer invocations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class TraceRecord:
    """
    Immutable record produced by every @infer invocation.

    Always written to the in-memory store regardless of export configuration.
    """

    function: str                   # qualified function name (__qualname__)
    model: str
    inputs: dict[str, Any]          # all input bindings; opaque fields included
    compiled_prompt_hash: str       # 12-char SHA-256 of compiled prompt text
    contract_hash: str              # 12-char SHA-256 of contract JSON Schema
    attempts: int                   # total attempts including retries
    output: Any                     # final typed output
    duration_ms: int
    cost_usd: float | None          # None if not reported by the LLM client
    cache_hit: bool
    retry_reasons: list[str]        # violation messages per failed attempt
    flow_id: str | None = None      # parent flow trace ID if called within @flow
    review_id: str | None = None    # set if await_human was involved in this flow step


# ---------------------------------------------------------------------------
# In-memory store
# ---------------------------------------------------------------------------

_records: list[TraceRecord] = []


def record(trace: TraceRecord) -> None:
    """Append a trace record to the in-memory store."""
    _records.append(trace)


def all_records() -> list[TraceRecord]:
    """Return a snapshot of all trace records."""
    return list(_records)


def clear() -> None:
    """Clear all in-memory trace records (useful in tests)."""
    _records.clear()
