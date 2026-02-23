# How to Build the Python Library

The primary product. No MCP, no Claude Code, no enforcement machinery. A Python developer does `pip install stratum`, adds `@infer`, and gets typed structured retry. That's the whole story for this track.

For the Claude Code MCP integration (a separate deployment context), see [`../claude-code/how-to-build.md`](../claude-code/how-to-build.md).

---

## Project Structure

```
stratum/
├── pyproject.toml
├── src/stratum/
│   ├── __init__.py          # public API: @contract, @infer, @compute, @flow, Budget
│   ├── decorators.py        # @infer, @compute, @flow, @contract implementations
│   ├── executor.py          # infer execution: prompt compile → LLM call → validate → retry
│   ├── contracts.py         # contract validation + constrained decoding grammar
│   ├── compiler.py          # prompt compiler: intent + context + inputs → minimal prompt
│   ├── budget.py            # Budget type + enforcement
│   ├── hitl.py              # await_human, HumanDecision, ReviewSink protocol, ConsoleReviewSink
│   ├── trace.py             # trace record per invocation (always written, in-memory)
│   └── exporters/
│       └── otlp.py          # built-in OTLP emitter — HTTP/JSON, no SDK dependency
```

---

## The Core: `@infer`

```python
from stratum import contract, infer, compute, flow, Budget
from pydantic import BaseModel
from typing import Literal

@contract
class SentimentResult(BaseModel):
    label: Literal["positive", "negative", "neutral"]
    confidence: float  # validated as 0.0..1.0 by field constraints
    reasoning: str

@infer(
    intent="Classify the emotional tone of customer feedback",
    context="Sarcasm → negative. Ambiguous → neutral.",
    ensure=lambda r: r.confidence > 0.7,
    budget=Budget(ms=500, usd=0.001),
    retries=3
)
def classify_sentiment(text: str) -> SentimentResult: ...

@compute
def rule_check(response: str, category: str) -> bool:
    return not any(word in response for word in BANNED_WORDS)

@flow(budget=Budget(ms=10000, usd=0.05))
def process_ticket(ticket: SupportTicket) -> Resolution:
    category  = classify(ticket.body)
    sentiment = classify_sentiment(ticket.body)
    response  = draft_response(ticket, category, sentiment)
    approved  = rule_check(response, category)
    return response if approved else escalate(ticket)
```

The `@infer` decorator:
- Compiles a minimal prompt from `intent`, `context`, and input bindings
- Calls the configured LLM using the structured outputs API (constrained to the return type schema)
- Evaluates `ensure` conditions post-parse
- On failure, retries with structured violation feedback injected
- Enforces `budget` as a hard cap — raises `BudgetExceeded` if exceeded
- Writes a typed trace record for every invocation

The `@contract` decorator marks a class as a Stratum contract — registered for schema compilation and constrained decoding grammar generation. Works on plain annotated classes; Pydantic `BaseModel` is an optional enhanced backend, not a requirement:

```python
# Plain annotated class — Stratum generates JSON Schema from type annotations
@contract
class SentimentResult:
    label: Literal["positive", "negative", "neutral"]
    confidence: Annotated[float, Field(ge=0.0, le=1.0)]
    reasoning: str

# Pydantic BaseModel — uses Pydantic's schema generation when detected
@contract
class SentimentResult(BaseModel):
    label: Literal["positive", "negative", "neutral"]
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str
```

Stratum detects which variant is used and calls the appropriate schema generation path internally. Developer code has no forced Pydantic dependency. Pydantic is recommended for richer field validation and better error messages but is not required.

`@compute` marks a deterministic function. The runtime knows it's pure — can cache, parallelize safely, and never routes it to an LLM.

`@flow` composes `@infer` and `@compute` calls with typed inter-step data and flow-level budget tracking.

---

## executor.py

```python
import time
from dataclasses import dataclass, field
from .contracts import validate_output, build_constrained_grammar
from .compiler import compile_prompt
from .budget import Budget, BudgetExceeded
from .trace import TraceRecord

@dataclass
class InferResult:
    output: any
    attempts: int
    tokens_used: int
    duration_ms: int
    retry_reasons: list[str] = field(default_factory=list)

async def execute_infer(fn_spec, inputs: dict, budget: Budget) -> InferResult:
    start = time.monotonic()
    retry_reasons = []

    for attempt in range(fn_spec.retries + 1):
        try:
            async with asyncio.timeout(budget.remaining_seconds()):
                prompt = compile_prompt(fn_spec, inputs, retry_reasons)
                grammar = build_constrained_grammar(fn_spec.output_contract)
                raw = await llm_call(prompt, grammar=grammar, budget=budget)
        except TimeoutError:
            raise BudgetExceeded(fn_spec.name, budget)

        parsed = parse_output(raw, fn_spec.output_contract)
        violations = evaluate_ensure(parsed, fn_spec.ensure)

        if not violations:
            return InferResult(
                output=parsed,
                attempts=attempt + 1,
                tokens_used=budget.tokens_since_checkpoint(),
                duration_ms=int((time.monotonic() - start) * 1000),
                retry_reasons=retry_reasons,
            )

        retry_reasons = violations

    raise PostconditionFailed(fn_spec.name, retry_reasons)
```

No MCP, no spec files, no YAML parsing — just the execution loop.

---

## compiler.py

```python
def compile_prompt(fn_spec, inputs: dict, retry_reasons: list[str]) -> str:
    parts = []

    if fn_spec.intent:
        parts.append(fn_spec.intent)

    for ctx in fn_spec.context:
        parts.append(ctx)

    parts.append("Inputs:")
    for key, value in inputs.items():
        parts.append(f"  {key}: {format_value(value)}")

    if retry_reasons:
        parts.append("Previous attempt failed:")
        for reason in retry_reasons:
            parts.append(f"  - {reason}")
        parts.append("Fix these issues specifically.")

    # Output schema is NOT in the prompt.
    # Enforced via constrained decoding grammar (structured outputs API).

    return "\n".join(parts)
```

---

## Installation

```toml
# pyproject.toml
[project]
name = "stratum"
version = "0.1.0"
dependencies = [
    "litellm>=1.0",        # LLM client — multi-model, fallback, cost tracking
]

[project.requires-python]
python = ">=3.11"          # asyncio.TaskGroup and asyncio.timeout required

[project.optional-dependencies]
pydantic = ["pydantic>=2.0"]   # enhanced @contract validation and error messages
all      = ["stratum[pydantic]"]

# No OTel SDK dependency — Stratum ships a built-in OTLP emitter (stratum/exporters/otlp.py)
# POST HTTP/JSON to any OTLP endpoint — zero extra dependencies
# v2+ — MCP server only, not the library
# jsonschema>=4.0   IR spec validation
# pyyaml>=6.0       IR spec parsing
```
```

No MCP dependency. The library is a standalone Python package.

---

## Build Sequence

```
Day 1-5:   @infer + ensure + structured retry
             - compile_prompt: intent + context + inputs
             - opaque[T] field handling in prompt compiler (data channel, not inline)
             - StratumCompileError on opaque[T] inline reference
             - structured outputs API for schema enforcement
             - post-parse ensure evaluation
             - retry with targeted failure feedback
             - budget hard cap per call
             - trace record per invocation

Day 6-10:  @flow + @compute + await_human
             - await_human: ReviewSink protocol, ConsoleReviewSink, asyncio.Future suspension
             - HumanDecision[T] return type, HITLTimeoutError
             - typed composition of infer + compute
             - sequential execution with typed inter-step data
             - flow-level budget tracking
             - parallel block with require: semantics

Week 2:    @agent + spawn
             - stateful agent with session memory
             - branch-scoped instances in parallel

Week 3:    patterns library (stratum.patterns)
             - actor_critic, constitutional, ensemble, reflexion

Week 4+:   .stratum IR emission
             - library emits .stratum.yaml as a side effect of execution
             - enables MCP server integration for Claude Code users
             - token audit tool (needs real workload data)
```

The `.stratum` IR and MCP server are week 4+ — they're the bridge to the Claude Code deployment context, not a prerequisite for library value. The library works without them.

---

## Python API Reference

### `@refine`

Stacked on `@infer`. Adds a convergence loop driven by `compute` expressions.

```python
@refine(
    until=lambda r: compute_tests(r).all_pass,
    feedback=lambda r: compute_tests(r).failures,
    max_iterations=5
)
@infer(
    intent="Generate code that passes all tests",
    budget=Budget(ms=10000)
)
def generate_code(spec: Spec) -> Code: ...
```

`until` and `feedback` are called with the current `infer` result after each attempt. Both must be deterministic (no LLM calls). `max_iterations` exhausted → raises `ConvergenceFailure` with full history.

---

### `stratum.parallel`

```python
summary, sentiment, entities = await stratum.parallel(
    summarize(doc),
    classify_sentiment(doc.text),
    extract_entities(doc.text),
    require="all"   # "all" (default) | "any" | int | 0
)
```

Returns a tuple matching input order. Semantics by `require`:
- `"all"` — all must succeed; any failure cancels remaining and raises
- `"any"` — first success wins, rest cancelled; returns that single result
- `N: int` — at least N must succeed; returns list of successful results
- `0` — collect all regardless; returns `list[Result[T]]`

---

### `quorum` on `@infer`

```python
@infer(
    intent="Classify the emotional tone of customer feedback",
    quorum=3,          # run this many times concurrently
    agree_on="label",  # field to check for consensus
    threshold=2        # minimum agreeing invocations required
)
def classify_sentiment(text: str) -> SentimentResult: ...
```

The runtime invokes the function `quorum` times concurrently, compares `agree_on` field across results, returns the result from a majority-agreeing invocation (highest confidence among agreers). If no majority, raises `ConsensusFailure` with all outputs.

---

### `stratum.debate`

```python
result = await stratum.debate(
    agents=[argue_for, argue_against],
    topic=proposal,
    rounds=2,
    synthesize=synthesize_debate
)
```

`agents` is a list of `@infer` functions. `synthesize` is an `@infer` function that receives `(topic, arguments, converged: bool)` and returns the final typed output. `converged` is computed by the runtime from round-over-round semantic similarity. When `converged=False` and the synthesizer returns `resolution_type="disagreement"`, the caller should route to `await_human`.
