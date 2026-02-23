"""Core @infer execution loop."""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field
from typing import Any, Callable, get_type_hints

import litellm

from ._config import get_config
from .budget import Budget
from .compiler import build_opaque_attachment, compile_prompt, prompt_hash
from .contracts import (
    get_hash,
    get_opaque_fields,
    get_schema,
    instantiate,
    is_opaque,
    is_registered,
    _annotation_to_schema,
)
from .exceptions import (
    BudgetExceeded,
    ParseFailure,
    PostconditionFailed,
    PreconditionFailed,
)
from .trace import TraceRecord, record


# ---------------------------------------------------------------------------
# InferSpec
# ---------------------------------------------------------------------------

@dataclass
class InferSpec:
    """All metadata from the @infer decorator plus resolved type info."""

    fn: Callable
    intent: str
    context: list[str]
    ensure: list[Callable]
    given: list[Callable]
    model: str | None
    temperature: float | None
    budget: Budget | None
    retries: int
    cache: str
    stable: bool
    quorum: int | None
    agree_on: str | None
    threshold: int | None
    return_type: Any
    parameters: dict[str, Any]


# ---------------------------------------------------------------------------
# Cache stores
# ---------------------------------------------------------------------------

# session cache: scoped to the current @flow execution via _FlowContext.session_cache.
# Falls back to a process-level dict for @infer calls made outside a @flow.
_process_session_cache: dict[str, Any] = {}
# global cache: keyed by (fn_qualname, inputs_hash, contract_hash)
_global_cache: dict[str, Any] = {}


def _get_session_cache() -> dict[str, Any]:
    """Return the session cache scoped to the current @flow, or a process-level fallback."""
    from .decorators import _flow_ctx  # lazy import avoids circular dependency
    ctx = _flow_ctx.get()
    if ctx is not None:
        return ctx.session_cache
    return _process_session_cache


def _inputs_hash(inputs: dict[str, Any]) -> str:
    """Stable hash of inputs dict for cache keying."""
    import hashlib

    try:
        canonical = json.dumps(inputs, sort_keys=True, default=str)
    except Exception:
        canonical = str(sorted(inputs.items()))
    return hashlib.sha256(canonical.encode()).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Opaque field detection
# ---------------------------------------------------------------------------

def _detect_opaque_params(spec: InferSpec) -> set[str]:
    """Return set of parameter names whose type annotations are opaque[T]."""
    opaque_set: set[str] = set()
    for param_name, annotation in spec.parameters.items():
        if is_opaque(annotation):
            opaque_set.add(param_name)
    return opaque_set


# ---------------------------------------------------------------------------
# Schema resolution for return type
# ---------------------------------------------------------------------------

def _resolve_return_schema(return_type: Any) -> tuple[dict, str]:
    """Return (json_schema, contract_hash_str) for the return type."""
    if return_type is None:
        return {}, "none"

    if is_registered(return_type):
        return get_schema(return_type), get_hash(return_type)

    # Primitive or inline type — compile inline
    schema = _annotation_to_schema(return_type)
    return schema, "none"


# ---------------------------------------------------------------------------
# Main execution loop
# ---------------------------------------------------------------------------

async def execute_infer(
    spec: InferSpec,
    inputs: dict[str, Any],
    flow_budget: Budget | None = None,
    flow_id: str | None = None,
) -> Any:
    """
    Full @infer execution loop per spec §3.1.

    1. Evaluate given conditions (preconditions)
    2. Compile prompt
    3. Loop up to retries+1 times:
       a. Check budget
       b. LLM call (wrapped in asyncio.timeout)
       c. Parse output
       d. Evaluate ensure conditions
       e. On success: write trace, return
       f. On violation: accumulate retry reasons, continue
    4. Retries exhausted → PostconditionFailed
    """
    fn_name = spec.fn.__name__
    fn_qualname = getattr(spec.fn, "__qualname__", fn_name)

    # ------------------------------------------------------------------
    # 1. Evaluate given (preconditions)
    # ------------------------------------------------------------------
    for given_fn in spec.given:
        try:
            result_ok = given_fn(**inputs)
        except Exception as exc:
            raise PreconditionFailed(fn_name, str(exc)) from exc
        if not result_ok:
            cond_name = getattr(given_fn, "__name__", repr(given_fn))
            raise PreconditionFailed(fn_name, cond_name)

    # ------------------------------------------------------------------
    # Effective budget: per-call overrides flow budget.
    # Clone spec.budget so each invocation gets a fresh clock and cost counter —
    # Budget._start_ms is set at Budget() creation time (decoration time), so
    # without cloning the time window shrinks across calls.
    # ------------------------------------------------------------------
    budget: Budget | None = spec.budget.clone() if spec.budget is not None else flow_budget

    # ------------------------------------------------------------------
    # Resolve return schema and hash
    # ------------------------------------------------------------------
    schema, c_hash = _resolve_return_schema(spec.return_type)

    # Ensure schema is an object schema (wrap primitive schemas if needed)
    # Tool function parameters must be an object schema
    if schema.get("type") != "object" and "$ref" not in schema:
        # Wrap primitive return types in an object with a single "value" field
        tool_schema = {
            "type": "object",
            "properties": {"value": schema},
            "required": ["value"],
        }
        wrap_primitive = True
    else:
        tool_schema = schema
        wrap_primitive = False

    # ------------------------------------------------------------------
    # Detect opaque parameters
    # ------------------------------------------------------------------
    opaque_params = _detect_opaque_params(spec)

    # ------------------------------------------------------------------
    # Cache check (session / global)
    # ------------------------------------------------------------------
    ih = _inputs_hash(inputs)
    if spec.cache == "session":
        cache_key = f"{fn_qualname}:{ih}"
        if cache_key in _get_session_cache():
            cached = _get_session_cache()[cache_key]
            # Spec §8.3: cached results still pass through ensure validation.
            _run_ensure(spec.ensure, cached, fn_name)
            _write_trace(
                fn_qualname=fn_qualname,
                model=spec.model or get_config()["default_model"],
                inputs=inputs,
                c_hash=c_hash,
                attempts=0,
                output=cached,
                duration_ms=0,
                total_cost=None,
                all_retry_reasons=[],
                cache_hit=True,
                flow_id=flow_id,
                last_prompt="",
            )
            return cached
    elif spec.cache == "global":
        cache_key = f"{fn_qualname}:{ih}:{c_hash}"
        if cache_key in _global_cache:
            cached = _global_cache[cache_key]
            # Spec §8.3: cached results still pass through ensure validation.
            _run_ensure(spec.ensure, cached, fn_name)
            _write_trace(
                fn_qualname=fn_qualname,
                model=spec.model or get_config()["default_model"],
                inputs=inputs,
                c_hash=c_hash,
                attempts=0,
                output=cached,
                duration_ms=0,
                total_cost=None,
                all_retry_reasons=[],
                cache_hit=True,
                flow_id=flow_id,
                last_prompt="",
            )
            return cached

    # ------------------------------------------------------------------
    # Retry loop
    # ------------------------------------------------------------------
    retry_reasons: list[str] = []
    all_retry_reasons: list[str] = []
    retry_history: list[list[str]] = []
    start = time.monotonic()
    total_cost: float = 0.0
    model = spec.model or get_config()["default_model"]
    last_prompt = ""
    last_failure_was_parse = True  # updated each attempt; True → parse/extract, False → ensure

    for attempt in range(spec.retries + 1):
        # a. Check budgets before each attempt
        if budget is not None and budget.is_cost_exceeded():
            raise BudgetExceeded(fn_name, budget)
        if budget is not None:
            remaining = budget.remaining_seconds()
            if remaining is not None and remaining <= 0:
                raise BudgetExceeded(fn_name, budget)

        # b. Compile prompt
        prompt = compile_prompt(
            intent=spec.intent,
            context=spec.context,
            inputs=inputs,
            opaque_fields=opaque_params,
            retry_reasons=retry_reasons,
        )
        last_prompt = prompt

        # Build messages
        system_msg = (
            "You are executing a typed function. "
            "Your output must conform to the specified contract."
        )
        user_content = prompt

        # Attach opaque data
        attachment = build_opaque_attachment(inputs, opaque_params)
        if attachment is not None:
            user_content = user_content + f"\n\nData:\n{json.dumps(attachment)}"

        messages = [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_content},
        ]

        # c. Build tool definition for structured output
        tool = {
            "type": "function",
            "function": {
                "name": "output",
                "description": "Return the structured output",
                "parameters": tool_schema,
            },
        }

        # d. LLM call
        timeout_secs = budget.remaining_seconds() if budget is not None else None

        call_kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "tools": [tool],
            "tool_choice": {"type": "function", "function": {"name": "output"}},
        }
        if spec.temperature is not None:
            call_kwargs["temperature"] = spec.temperature

        try:
            if timeout_secs is not None:
                async with asyncio.timeout(timeout_secs):
                    response = await litellm.acompletion(**call_kwargs)
            else:
                response = await litellm.acompletion(**call_kwargs)
        except asyncio.TimeoutError:
            raise BudgetExceeded(fn_name, budget)

        # e. Track cost
        try:
            cost = litellm.completion_cost(completion_response=response)
            if cost and budget is not None:
                budget.record_cost(cost)
            if cost:
                total_cost += cost
        except Exception:
            cost = 0.0

        # f. Extract tool call result
        try:
            tool_calls = response.choices[0].message.tool_calls
            if not tool_calls:
                raise ValueError("No tool call in response")
            raw_args = tool_calls[0].function.arguments
        except (AttributeError, IndexError, TypeError, ValueError) as exc:
            parse_reason = f"Failed to extract tool call: {exc}"
            retry_reasons = [parse_reason]
            all_retry_reasons.append(parse_reason)
            retry_history.append([parse_reason])
            last_failure_was_parse = True
            continue

        # g. Parse JSON
        try:
            parsed_dict = json.loads(raw_args)
        except json.JSONDecodeError as exc:
            parse_reason = f"JSON parse error: {exc}"
            retry_reasons = [parse_reason]
            all_retry_reasons.append(parse_reason)
            retry_history.append([parse_reason])
            last_failure_was_parse = True
            continue

        # h. Unwrap primitive wrapper if needed
        if wrap_primitive:
            if isinstance(parsed_dict, dict) and "value" in parsed_dict:
                parsed_dict = parsed_dict["value"]

        # i. Instantiate return type
        if is_registered(spec.return_type):
            try:
                parsed = instantiate(spec.return_type, parsed_dict)
            except Exception as exc:
                parse_reason = f"Instantiation error: {exc}"
                retry_reasons = [parse_reason]
                all_retry_reasons.append(parse_reason)
                retry_history.append([parse_reason])
                last_failure_was_parse = True
                continue
        else:
            parsed = parsed_dict

        # j. Evaluate ensure conditions
        violations: list[str] = []
        for i, ensure_fn in enumerate(spec.ensure):
            try:
                ok = ensure_fn(parsed)
            except Exception as exc:
                violations.append(f"ensure condition {i + 1} raised: {exc}")
                continue
            if not ok:
                # Try to get a meaningful name
                fn_repr = getattr(ensure_fn, "__name__", None)
                if fn_repr and fn_repr != "<lambda>":
                    violations.append(f"ensure: {fn_repr}(result) was False")
                else:
                    violations.append(f"ensure condition {i + 1} failed")

        if not violations:
            # Success — write trace and return
            duration_ms = int((time.monotonic() - start) * 1000)
            cost_usd: float | None = total_cost if total_cost > 0 else None
            _write_trace(
                fn_qualname=fn_qualname,
                model=model,
                inputs=inputs,
                c_hash=c_hash,
                attempts=attempt + 1,
                output=parsed,
                duration_ms=duration_ms,
                total_cost=cost_usd,
                all_retry_reasons=all_retry_reasons,
                cache_hit=False,
                flow_id=flow_id,
                last_prompt=last_prompt,
            )

            # Store in cache if requested
            if spec.cache == "session":
                _get_session_cache()[f"{fn_qualname}:{ih}"] = parsed
            elif spec.cache == "global":
                _global_cache[f"{fn_qualname}:{ih}:{c_hash}"] = parsed

            # Export via tracer if configured
            _export_trace_if_configured(
                fn_qualname=fn_qualname,
                model=model,
                c_hash=c_hash,
                attempts=attempt + 1,
                cost_usd=cost_usd,
                cache_hit=False,
                flow_id=flow_id,
                duration_ms=duration_ms,
                response=response,
            )

            return parsed

        # Violations found — accumulate and retry
        last_failure_was_parse = False
        retry_history.append(list(violations))
        all_retry_reasons.extend(violations)
        retry_reasons = violations

    # ------------------------------------------------------------------
    # Retries exhausted
    # ------------------------------------------------------------------
    # Raise based on the *final* attempt's failure type, not a cumulative flag.
    # last_failure_was_parse tracks the most recent failure path.
    if last_failure_was_parse and retry_reasons:
        raise ParseFailure(fn_name, "", "; ".join(retry_reasons))
    raise PostconditionFailed(fn_name, retry_reasons, retry_history)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run_ensure(ensure_fns: list[Callable], value: Any, fn_name: str) -> None:
    """Evaluate ensure conditions against value; raise PostconditionFailed on first violation."""
    violations: list[str] = []
    for i, ensure_fn in enumerate(ensure_fns):
        try:
            ok = ensure_fn(value)
        except Exception as exc:
            violations.append(f"ensure condition {i + 1} raised: {exc}")
            continue
        if not ok:
            fn_repr = getattr(ensure_fn, "__name__", None)
            if fn_repr and fn_repr != "<lambda>":
                violations.append(f"ensure: {fn_repr}(result) was False")
            else:
                violations.append(f"ensure condition {i + 1} failed")
    if violations:
        raise PostconditionFailed(fn_name, violations, [violations])


def _write_trace(
    fn_qualname: str,
    model: str,
    inputs: dict[str, Any],
    c_hash: str,
    attempts: int,
    output: Any,
    duration_ms: int,
    total_cost: float | None,
    all_retry_reasons: list[str],
    cache_hit: bool,
    flow_id: str | None,
    last_prompt: str,
) -> None:
    p_hash = prompt_hash(last_prompt) if last_prompt else "none"
    trace = TraceRecord(
        function=fn_qualname,
        model=model,
        inputs=inputs,
        compiled_prompt_hash=p_hash,
        contract_hash=c_hash,
        attempts=attempts,
        output=output,
        duration_ms=duration_ms,
        cost_usd=total_cost,
        cache_hit=cache_hit,
        retry_reasons=all_retry_reasons,
        flow_id=flow_id,
        review_id=None,
    )
    record(trace)


def _derive_gen_ai_system(model: str) -> str:
    m = model.lower()
    if "claude" in m:
        return "anthropic"
    if "gemini" in m:
        return "google"
    # Strip provider prefix (e.g. "openai/gpt-4") before matching OpenAI model names
    bare = m.split("/")[-1]
    if bare.startswith(("gpt-", "o1", "o3", "o4")):
        return "openai"
    return m.split("/")[0] if "/" in m else "unknown"


def _export_trace_if_configured(
    fn_qualname: str,
    model: str,
    c_hash: str,
    attempts: int,
    cost_usd: float | None,
    cache_hit: bool,
    flow_id: str | None,
    duration_ms: int,
    response: Any,
) -> None:
    """Emit to OTel tracer if one is configured."""
    tracer = get_config().get("tracer")
    if tracer is None:
        return

    try:
        # Extract token usage if available
        usage = getattr(response, "usage", None)
        input_tokens = getattr(usage, "prompt_tokens", None)
        output_tokens = getattr(usage, "completion_tokens", None)

        span_attrs = {
            "gen_ai.system": _derive_gen_ai_system(model),
            "gen_ai.request.model": model,
            "stratum.function": fn_qualname,
            "stratum.contract_hash": c_hash,
            "stratum.attempts": attempts,
            "stratum.cost_usd": cost_usd,
            "stratum.cache_hit": cache_hit,
            "stratum.flow_id": flow_id,
            "stratum.duration_ms": duration_ms,
        }
        if input_tokens is not None:
            span_attrs["gen_ai.usage.input_tokens"] = input_tokens
        if output_tokens is not None:
            span_attrs["gen_ai.usage.output_tokens"] = output_tokens

        tracer(span_attrs)
    except Exception:
        pass  # Tracer errors must not affect execution
