# Stratum v1 — Language and Runtime Specification

**Version:** 1.0.0-draft
**Date:** 2026-02-23
**Status:** Draft — reference implementation available
**Repository:** https://github.com/regression-io/stratum

---

## Table of Contents

1. [Type System](#1-type-system)
   - 1.1 [Primitive Types](#11-primitive-types)
   - 1.2 [Contract Types](#12-contract-types)
   - 1.3 [Schema Compilation](#13-schema-compilation)
   - 1.4 [Content Hash](#14-content-hash)
   - 1.5 [`opaque[T]`](#15-opaquet)
   - 1.6 [`Probabilistic[T]`](#16-probabilistict)
   - 1.7 [`HumanDecision[T]`](#17-humandecisiont)
   - 1.8 [`HumanReviewContext`](#18-humanreviewcontext)
2. [Decorators](#2-decorators)
   - 2.1 [`@contract`](#21-contract)
   - 2.2 [`@compute`](#22-compute)
   - 2.3 [`@infer`](#23-infer)
   - 2.4 [`@refine`](#24-refine)
   - 2.5 [`@flow`](#25-flow)
3. [Execution Semantics](#3-execution-semantics)
   - 3.1 [`@infer` Execution Loop](#31-infer-execution-loop)
   - 3.2 [Retry Context Injection](#32-retry-context-injection)
   - 3.3 [`@refine` Execution Loop](#33-refine-execution-loop)
   - 3.4 [`@flow` Execution](#34-flow-execution)
4. [Prompt Compiler](#4-prompt-compiler)
   - 4.1 [Assembly Order](#41-assembly-order)
   - 4.2 [`opaque[T]` Handling](#42-opaquet-handling)
   - 4.3 [Compiled Prompt Hash](#43-compiled-prompt-hash)
5. [Concurrency Primitives](#5-concurrency-primitives)
   - 5.1 [`stratum.parallel`](#51-stratumparallel)
   - 5.2 [`quorum` on `@infer`](#52-quorum-on-infer)
   - 5.3 [`stratum.debate`](#53-stratumdebate)
   - 5.4 [`stratum.race`](#54-stratumrace)
6. [HITL](#6-hitl)
   - 6.1 [`await_human`](#61-await_human)
   - 6.2 [`ReviewSink` Protocol](#62-reviewsink-protocol)
   - 6.3 [`ConsoleReviewSink`](#63-consolereviewsink-v1-default)
7. [Budget](#7-budget)
   - 7.1 [`Budget`](#71-budget)
   - 7.2 [Per-Call Enforcement](#72-per-call-enforcement)
   - 7.3 [Per-Flow Enforcement](#73-per-flow-enforcement)
   - 7.4 [Inheritance](#74-inheritance)
8. [Trace Records](#8-trace-records)
   - 8.1 [Schema](#81-schema)
   - 8.2 [OTel Export](#82-otel-export)
   - 8.3 [Caching](#83-caching)
9. [Static Analysis](#9-static-analysis)
10. [Error Types](#10-error-types)
11. [Configuration](#11-configuration)
12. [Module Structure](#12-module-structure)
13. [Minimal Complete Example](#13-minimal-complete-example)

---

## Conformance

Conformance language follows [RFC 2119](https://www.rfc-editor.org/rfc/rfc2119): MUST, MUST NOT, SHALL, SHOULD, MAY.

**Runtime requirements:**
- Python 3.11+ (`asyncio.TaskGroup`, `asyncio.timeout`)
- `litellm>=1.0` (hard dependency — LLM client substrate)
- `pydantic>=2.0` (optional — enhanced `@contract` validation and error messages)

**Out of scope for v1:**
- `.stratum.yaml` IR format (Phase 2)
- MCP server integration (Phase 2)
- TypeScript library (Phase 2)
- `@agent`, `spawn`, `supervise`, `delegate`, `stream[T]` (Phase 2)
- Decoration-time static analysis via bytecode/AST introspection (Phase 2.5):
  - `ensure`/`given` field validation — `LOAD_ATTR` bytecode checked against contract schema at `@infer` decoration time
  - Sequential independence warning — `@flow` AST walk detects independent `await` chains that could be `parallel()`
  - Budget sufficiency warning — sum of visible per-`@infer` budgets compared to `@flow` envelope
- `orchestrate`, `adapt`, `reflect` (Phase 3)
- DSPy prompt optimization, Ray distribution substrate (Phase 3)

---

## 1. Type System

### 1.1 Primitive Types

| Python type | Notes |
|---|---|
| `str` | UTF-8 |
| `int` | 64-bit signed |
| `float` | 64-bit IEEE 754 |
| `bool` | |
| `None` / `type[None]` | explicit null |
| `datetime.date` | ISO 8601 |
| `datetime.datetime` | ISO 8601 with timezone |
| `bytes` | base64 in JSON |

Constrained primitives via `Annotated`:

```python
Annotated[float, Field(ge=0.0, le=1.0)]            # float in [0.0, 1.0] inclusive
Annotated[int, Field(ge=1, le=100)]                 # int in [1, 100]
Annotated[str, Field(min_length=1, max_length=500)] # string of length 1–500
```

Constraints are enforced by the runtime validator at output parse time and checked by the static analyzer against `ensure` expressions.

### 1.2 Contract Types

A contract is a named structured type registered with the Stratum runtime. It is the unit of schema compilation.

```python
@contract
class SentimentResult:
    label: Literal["positive", "negative", "neutral"]
    confidence: Annotated[float, Field(ge=0.0, le=1.0)]
    reasoning: str
```

**Registration:** `@contract` registers the class in the global contract registry at decoration time, keyed by class identity. Schema and content hash are computed once at registration.

**Pydantic interop:** If the decorated class inherits from `pydantic.BaseModel`, Stratum uses Pydantic's schema generation. Otherwise, Stratum generates JSON Schema from `typing.get_type_hints()` directly. Pydantic is not required.

**Nested contracts:**

```python
@contract
class Address:
    city: str
    country: Annotated[str, Field(min_length=2, max_length=2)]

@contract
class UserProfile:
    name: str
    address: Address        # nested — Address must already be registered
    tags: list[str]
    nickname: str | None    # optional
```

**Literal unions** compile to `{"enum": [...]}`. The LLM is constrained to the declared values via the structured outputs API.

### 1.3 Schema Compilation

Every registered `@contract` compiles to a JSON Schema (draft 2020-12).

| Python annotation | JSON Schema |
|---|---|
| `str` | `{"type": "string"}` |
| `Annotated[str, Field(min_length=1, max_length=500)]` | `{"type": "string", "minLength": 1, "maxLength": 500}` |
| `float` | `{"type": "number"}` |
| `Annotated[float, Field(ge=0.0, le=1.0)]` | `{"type": "number", "minimum": 0.0, "maximum": 1.0}` |
| `int` | `{"type": "integer"}` |
| `bool` | `{"type": "boolean"}` |
| `Literal["a", "b"]` | `{"enum": ["a", "b"]}` |
| `T \| None` | `{"anyOf": [schema(T), {"type": "null"}]}` |
| `list[T]` | `{"type": "array", "items": schema(T)}` |
| `@contract` class | `{"type": "object", "properties": {...}, "required": [...]}` |

All fields without `None` in their type annotation are included in `required`.

### 1.4 Content Hash

Every registered `@contract` MUST have a content hash computed at registration time:

```python
import hashlib, json

def contract_hash(json_schema: dict) -> str:
    canonical = json.dumps(json_schema, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(canonical.encode()).hexdigest()[:12]
```

The hash is:
- Embedded in every trace record that uses the contract
- Part of the cache key for `cache="global"` scope
- A behavioral version signal — a hash change means the compiled prompt changed and LLM behavior may differ

### 1.5 `opaque[T]`

`opaque` is a class with `__class_getitem__` that returns `Annotated[T, _OpaqueMarker()]`:

```python
@contract
class AgentOutput:
    summary: str              # interpolated inline into the next prompt
    reasoning: opaque[str]   # Annotated[str, _OpaqueMarker()] at runtime
    entities: list[str]
```

**Semantics:** Fields annotated `opaque[T]` MUST be passed to the LLM as a structured JSON attachment in the user turn. They MUST NOT appear inline in prompt instruction text.

The parameterized query pattern applied to prompt construction: the LLM still receives the data, but its instructions cannot be overwritten by adversarial content in `opaque` fields.

**Enforcement:** The prompt compiler MUST raise `StratumCompileError` if an `opaque[T]` field is detected in an inline string interpolation. This is structural enforcement, not a warning.

**Type transparency:** `opaque[str]` is assignable to `str`. It serializes normally. `_OpaqueMarker` has no effect outside the prompt compiler.

**Python annotation syntax:**

```python
class opaque:
    def __class_getitem__(cls, item):
        return Annotated[item, _OpaqueMarker()]

class _OpaqueMarker:
    pass
```

Type checkers treat `opaque[str]` as `str`. The prompt compiler detects `_OpaqueMarker` in annotation metadata.

### 1.6 `Probabilistic[T]`

Return type for `@infer` functions declared with `stable=False`.

```python
class Probabilistic(Generic[T]):
    def most_likely(self) -> T:
        """Modal value across samples. In production (single sample), returns that
        sample. Never raises."""

    def sample(self) -> T:
        """Random draw from collected samples. In production, returns the single
        sample."""

    def assert_stable(self, threshold: float = 0.9) -> T:
        """Raises StabilityAssertionError if sample agreement is below threshold.
        Agreement = fraction of samples matching the modal value on key fields.
        Returns the modal value if stable."""
```

In production, `_samples = [single_output]`. All three methods behave correctly with no sampling overhead.

In test/CI mode (`stratum.configure(test_mode=True)`), the runtime samples `sample_n` times (default: 5) and populates `_samples`.

### 1.7 `HumanDecision[T]`

Return type of `await_human`. Wraps a typed decision with provenance metadata.

```python
@dataclass
class HumanDecision(Generic[T]):
    value: T
    reviewer: str | None      # identity of reviewer, if provided
    rationale: str | None     # optional human note
    decided_at: datetime
    review_id: str            # stable UUID; correlates with trace record
```

`.value` extracts `T`. `HumanDecision[T]` propagates through `@flow` steps like any other typed value.

### 1.8 `HumanReviewContext`

Input to `await_human` describing the review request.

```python
@dataclass
class HumanReviewContext:
    question: str
    trigger: str = "explicit"    # "explicit" | "debate_disagreement" | any string
    artifacts: dict[str, Any] = field(default_factory=dict)
```

`artifacts` is untyped in v1 — pass anything the reviewer needs (debate history, retry trace, raw outputs). Typed artifact contracts are v2.

---

## 2. Decorators

### 2.1 `@contract`

No arguments. Registers a class as a Stratum contract and computes its JSON Schema and content hash at decoration time.

**Rules:**
- The decorated class MUST have at least one annotated field
- Field types MUST be from the supported type set (§1.1–§1.2)
- Circular contract references are a `StratumCompileError`

### 2.2 `@compute`

No arguments. Marks a function as deterministic. The runtime never routes it to an LLM, may parallelize it safely, and excludes it from cost tracking.

`@compute` functions with external side effects (database writes, file I/O) are the developer's responsibility. Purity is not enforced.

### 2.3 `@infer`

```python
@infer(
    intent: str,                                      # required
    context: str | list[str] = [],
    ensure: Callable[[T], bool]
          | list[Callable[[T], bool]] = [],
    given: Callable[..., bool]
         | list[Callable[..., bool]] = [],
    model: str = configured_default,
    temperature: float | None = None,
    budget: Budget | None = None,                     # inherits flow budget if None
    retries: int = 3,
    cache: Literal["none", "session", "global"] = "none",
    stable: bool = True,                              # False → return Probabilistic[T]
    quorum: int | None = None,
    agree_on: str | None = None,
    threshold: int | None = None,
)
```

The decorated function body MUST be `...`. It is never executed.

The return type annotation MUST be a registered `@contract` class or a primitive. Do not annotate `Probabilistic[T]` manually — it is inferred from `stable=False`.

`quorum` requires both `agree_on` and `threshold`. Specifying `quorum` without either is a `StratumCompileError`.

### 2.4 `@refine`

Stacked on `@infer`. Adds an outer convergence loop driven by deterministic expressions.

```python
@refine(
    until: Callable[[T], bool],     # convergence signal — MUST be deterministic
    feedback: Callable[[T], Any],   # failure context injected into the next prompt
    max_iterations: int = 5,
)
```

`until` and `feedback` MUST NOT call `@infer` functions. Doing so is a `StratumCompileError`.

```python
@refine(
    until=lambda r: run_tests(r).all_pass,
    feedback=lambda r: run_tests(r).failures,
    max_iterations=5
)
@infer(intent="Generate code that passes all tests", budget=Budget(ms=10000))
def generate_code(spec: Spec) -> Code: ...
```

`max_iterations` exhausted → raises `ConvergenceFailure` with full iteration history.

### 2.5 `@flow`

```python
@flow(
    budget: Budget | None = None,
)
```

Marks an `async def` function as a Stratum flow. The body is normal Python — calls to `@infer`, `@compute`, `stratum.parallel`, `await_human`, etc.

`@flow` functions MUST be `async def`. The runtime tracks cumulative cost and time against the `budget` envelope across all `@infer` calls within the flow.

---

## 3. Execution Semantics

### 3.1 `@infer` Execution Loop

```
call infer_function(**inputs)
  │
  ├─ 1. Evaluate given conditions
  │       Each given(inputs) → bool
  │       Any False → raise PreconditionFailed (no retry)
  │
  ├─ 2. Compile prompt  [see §4]
  │
  ├─ loop (attempt in range(retries + 1)):
  │   │
  │   ├─ 3. Check budget
  │   │       budget.remaining() ≤ 0 → raise BudgetExceeded
  │   │
  │   ├─ 4. Invoke LLM
  │   │       async with asyncio.timeout(budget.remaining_seconds()):
  │   │           raw = await llm_client.complete(prompt, schema=contract_schema)
  │   │       TimeoutError → raise BudgetExceeded
  │   │
  │   ├─ 5. Parse output
  │   │       parsed = parse_against_schema(raw, contract_schema)
  │   │       ParseFailure → inject error message, continue loop
  │   │
  │   ├─ 6. Evaluate ensure conditions
  │   │       violations = [msg for fn in ensures if not fn(parsed)]
  │   │       violations empty → write trace record, return parsed
  │   │       violations non-empty → inject violations, continue loop
  │   │
  │   └─ (next attempt)
  │
  └─ retries exhausted → raise PostconditionFailed(violations, retry_history)
```

### 3.2 Retry Context Injection

On each failed attempt, only the specific violations are injected — not a replay of the full prompt:

```
Previous attempt failed:
  - ensure: result.confidence > 0.7 (actual: 0.42)
  - ensure: result.label in ["positive", "negative", "neutral"] (actual: "mixed")
Fix these issues specifically.
```

Parse failures inject a structured parse error describing the schema mismatch.

### 3.3 `@refine` Execution Loop

Wraps the `@infer` loop with an outer convergence loop:

```
loop (iteration in range(1, max_iterations + 1)):
  │
  ├─ execute @infer loop → result
  │
  ├─ evaluate until(result)
  │       True  → return result
  │       False → evaluate feedback(result)
  │
  └─ inject into next iteration prompt:
         "Previous output had the following issues: [feedback(result)]
          Fix these and regenerate."

max_iterations exceeded → raise ConvergenceFailure(history)
```

`until` and `feedback` execute in the host process and are never sent to the LLM.

### 3.4 `@flow` Execution

A `@flow` function is a normal async Python function. Each `@infer` call within it invokes the full `@infer` execution loop. The flow tracks cumulative cost and time against its `budget` envelope. When exhausted, the next `@infer` call raises `BudgetExceeded` before the LLM is invoked.

---

## 4. Prompt Compiler

The prompt compiler assembles the string sent to the LLM for each `@infer` invocation. Assembly is deterministic — identical inputs produce identical prompts.

### 4.1 Assembly Order

```
[1. intent]
    The natural language goal from the @infer annotation.

[2. context annotations]
    Each string from context=, in declaration order.

[3. non-opaque input bindings]
    For each parameter where the type is NOT opaque[T]:
      "{name}: {formatted_value}"

[4. retry context — only when attempt > 0]
    "Previous attempt failed:
      - {violation_message}
    Fix these issues specifically."

[5. opaque data reference — only when opaque[T] fields are present]
    Instruction text: "See attached data for: {comma-separated field names}"
    Structured JSON attachment (separate from instruction text):
      {"field_name": value, ...}
```

The output schema is NOT included in the prompt text. It is enforced via the structured outputs API (or a constrained decoding backend for self-hosted models). The LLM does not need schema instructions — generation is constrained at the token level.

### 4.2 `opaque[T]` Handling

Fields with `_OpaqueMarker` in their `Annotated` metadata MUST be excluded from section 3 of the assembly and placed in the structured JSON attachment of section 5.

The prompt compiler MUST raise `StratumCompileError` if an `opaque[T]` field appears in an inline string interpolation anywhere in the compilation pipeline.

### 4.3 Compiled Prompt Hash

After assembly, the compiler computes SHA-256 of the assembled prompt string (12 hex chars). This is embedded in the trace record as `compiled_prompt_hash`. It is distinct from the contract hash — it captures the full compiled text including intent and context.

---

## 5. Concurrency Primitives

### 5.1 `stratum.parallel`

```python
results = await stratum.parallel(
    *coros: Coroutine,
    require: Literal["all", "any"] | int = "all",
    validate: Callable[[list], bool] | None = None,
)
```

All coroutines are submitted to `asyncio.TaskGroup` concurrently.

| `require` value | Behavior | Return type |
|---|---|---|
| `"all"` (default) | All must succeed; any failure cancels rest and raises | Tuple matching input order |
| `"any"` | First success wins, rest cancelled | Single result |
| `N: int` | At least N must succeed | `list` of N successful results |
| `0` | Collect all regardless of failure | `list[Result[T]]` (`Success` or `Failure`) |

`validate` — if provided, called with collected results after `require` is satisfied. Returns `False` → raises `ParallelValidationFailed`.

**Isolation:** Variables defined before the `stratum.parallel` call are readable by all branches. Mutation inside a branch is the developer's responsibility in v1. Compiler enforcement is v2.

### 5.2 `quorum` on `@infer`

When `quorum=N` is specified on `@infer`:

1. The runtime invokes the function `N` times concurrently via `asyncio.TaskGroup`
2. Compares the `agree_on` field across all results
3. If `threshold` or more invocations agree: returns the result from among the agreers with the highest `confidence` field value (or the first agreeing result if no `confidence` field exists)
4. If fewer than `threshold` agree: raises `ConsensusFailure` with all N outputs

`quorum` draws from the same `budget` envelope as a single invocation. The budget must be sufficient for N parallel LLM calls.

### 5.3 `stratum.debate`

```python
result = await stratum.debate(
    agents: list[Callable],     # @infer functions — the debating agents
    topic: Any,                 # typed input passed to all agents
    rounds: int = 2,
    synthesize: Callable,       # @infer fn receiving (topic, arguments, converged)
)
```

**Execution:**

1. All `agents` are invoked concurrently with `topic`. Each returns a typed `Argument`.
2. For `rounds - 1` additional rounds: each agent is invoked with `topic` and all other agents' previous arguments (rebuttal round).
3. After all rounds, the runtime computes `converged: bool` from round-over-round semantic similarity (field-level hash comparison on the `agree_on` field if declared, otherwise full output hash comparison).
4. `synthesize` is called with `(topic, full_argument_history, converged)` and returns the final typed result.

The synthesizer's return contract SHOULD include `resolution_type: Literal["consensus", "disagreement", "partial"]`. When `converged=False` and `resolution_type="disagreement"`, the caller SHOULD route to `await_human`.

### 5.4 `stratum.race`

```python
result = await stratum.race(*coros: Coroutine)
```

All coroutines submitted concurrently. First to complete without raising wins; remaining are cancelled. If all raise, re-raises the last error.

---

## 6. HITL

### 6.1 `await_human`

```python
decision = await await_human(
    context: HumanReviewContext,
    decision_type: type[T],
    options: list[T] | None = None,
    timeout: timedelta | None = None,
    on_timeout: T | Literal["raise"] = "raise",
) -> HumanDecision[T]
```

**Execution:**

1. Generate `review_id` (UUID4)
2. Build `PendingReview(review_id, context, options, expires_at=now+timeout)`
3. `await sink.emit(review)` — emits to the configured `ReviewSink`
4. Park the calling coroutine on `asyncio.Future`
5. If `timeout` is set, schedule cancellation via `asyncio.timeout(timeout.total_seconds())`
6. When `sink.resolve(decision)` is called, validate `decision.value` against `decision_type`, resolve the `Future`
7. Return `HumanDecision[T]`

**Timeout semantics:**

- `on_timeout="raise"` → raises `HITLTimeoutError(review_id=review_id)`
- `on_timeout=fallback_value` → returns `HumanDecision(value=fallback_value, reviewer="auto", rationale="timeout", decided_at=now, review_id=review_id)`

Timeout is wall-clock `timedelta`. It does NOT draw from the `budget` envelope.

### 6.2 `ReviewSink` Protocol

```python
class ReviewSink(Protocol):
    async def emit(self, review: PendingReview) -> None: ...

@dataclass
class PendingReview:
    review_id: str
    context: HumanReviewContext
    options: list[Any] | None
    expires_at: datetime | None

    async def resolve(self, decision: HumanDecision) -> None: ...
```

`resolve` validates `decision.value` against the declared `decision_type` before fulfilling the `Future`. Type mismatch raises `TypeError`.

### 6.3 `ConsoleReviewSink` (v1 default)

```python
class ConsoleReviewSink:
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
            return review.options[int(raw.strip())]  # index selection
        return raw.strip()                            # freeform; cast at resolve
```

`input()` is wrapped in `run_in_executor` to avoid blocking the event loop.

---

## 7. Budget

### 7.1 `Budget`

```python
@dataclass
class Budget:
    ms: int | None = None       # wall-clock milliseconds
    usd: float | None = None    # cost in USD
```

Either or both may be specified. Unspecified axes are unbounded.

### 7.2 Per-Call Enforcement

Each `@infer` call wraps the LLM invocation in `asyncio.timeout(budget.remaining_seconds())`. `TimeoutError` is caught and re-raised as `BudgetExceeded`. Cost is checked after each LLM response — if cumulative cost exceeds `budget.usd`, `BudgetExceeded` is raised before the next attempt.

### 7.3 Per-Flow Enforcement

`@flow(budget=Budget(...))` creates a shared budget envelope. Each `@infer` call within the flow draws from it. When exhausted, the next `@infer` call raises `BudgetExceeded` before invoking the LLM.

### 7.4 Inheritance

If an `@infer` call has no `budget` annotation and is invoked within a `@flow` that has a budget, it inherits the flow's remaining envelope. If neither has a budget, the call is unbounded.

---

## 8. Trace Records

Every `@infer` invocation MUST produce a trace record regardless of export configuration. Records are always written to an in-memory store.

### 8.1 Schema

```python
@dataclass
class TraceRecord:
    function: str                  # qualified function name
    model: str
    inputs: dict[str, Any]         # all input bindings; opaque fields included, flagged
    compiled_prompt_hash: str      # 12-char SHA-256 of compiled prompt
    contract_hash: str             # 12-char SHA-256 of contract JSON Schema
    attempts: int                  # total attempts including retries
    output: Any                    # final typed output
    duration_ms: int
    cost_usd: float | None         # None if not reported by LLM client
    cache_hit: bool
    retry_reasons: list[str]       # violation messages per failed attempt
    flow_id: str | None            # parent flow trace ID if called within @flow
    review_id: str | None          # set if await_human was involved in this flow step
```

### 8.2 OTel Export

Optional. Configure via:

```python
stratum.configure(tracer=stratum.exporters.otel(endpoint="http://localhost:4317"))
```

Span attributes conform to [OpenTelemetry Semantic Conventions for AI](https://opentelemetry.io/docs/specs/semconv/gen-ai/):

```python
{
    "gen_ai.system":                "anthropic",
    "gen_ai.request.model":         "claude-sonnet-4-6",
    "gen_ai.usage.input_tokens":    312,
    "gen_ai.usage.output_tokens":   48,
    "stratum.function":             "classify_sentiment",
    "stratum.contract_hash":        "def456abc123",
    "stratum.compiled_prompt_hash": "abc123def456",
    "stratum.attempts":             1,
    "stratum.cost_usd":             0.00034,
    "stratum.cache_hit":            False,
    "stratum.flow_id":              "uuid...",
}
```

Each retry is a span event with structured failure reason. `@flow` is the root span. Each `@infer` is a child span. `stratum.parallel` branches are concurrent child spans.

The built-in emitter (`stratum/exporters/otlp.py`) POSTs HTTP/JSON to any OTLP endpoint. No `opentelemetry-sdk` dependency required.

### 8.3 Caching

```python
cache: Literal["none", "session", "global"] = "none"
```

| Scope | Cache key | Lifetime |
|---|---|---|
| `"none"` | — | No caching |
| `"session"` | `hash(inputs)` | Single `@flow` execution |
| `"global"` | `hash(inputs) + contract_hash` | Persistent (in-memory in v1; external store is v2) |

Cached results still pass through `ensure` validation. Cache is invalidated automatically when `contract_hash` changes.

---

## 9. Static Analysis

The following are `StratumCompileError` (raised at decoration time, or at first invocation if deferred):

- `@infer` return type is not a registered `@contract` or primitive
- `ensure` expression references a field not present in the declared return type
- `given` expression references a name not in the function signature
- `opaque[T]` field detected in an inline string interpolation
- `@refine.until` or `@refine.feedback` call an `@infer` function
- `@contract` class contains a circular reference
- `quorum` specified without `agree_on` or `threshold`

The following are `StratumWarning`:

- `stable=True` on an `@infer` function that has not been sampled in test mode
- `cache="global"` without a configured persistent store (in-memory fallback used)

---

## 10. Error Types

| Error | Trigger |
|---|---|
| `PreconditionFailed` | `given` condition is `False` |
| `PostconditionFailed` | `ensure` condition `False` after all retries exhausted |
| `ParseFailure` | LLM output could not be parsed against contract schema |
| `BudgetExceeded` | Time or cost budget exceeded |
| `ConvergenceFailure` | `@refine` hit `max_iterations` without `until` returning `True` |
| `ConsensusFailure` | `quorum` could not reach `threshold` agreement |
| `ParallelValidationFailed` | `stratum.parallel` `validate` returned `False` |
| `HITLTimeoutError` | `await_human` wall-clock timeout exceeded; includes `review_id` |
| `StabilityAssertionError` | `Probabilistic[T].assert_stable()` below threshold |
| `StratumCompileError` | Static analysis violation |

---

## 11. Configuration

```python
stratum.configure(
    client: LLMClient | None = None,          # LiteLLM default
    review_sink: ReviewSink | None = None,    # ConsoleReviewSink default
    tracer: OTLPEmitter | None = None,        # None = no export
    default_model: str = "claude-sonnet-4-6",
    test_mode: bool = False,                  # enables sampling for Probabilistic[T]
    sample_n: int = 5,                        # samples per @infer call in test mode
)
```

Configuration is global, set once at startup. Per-function decorator annotations take precedence over global defaults.

**Sync shim:**

```python
# For non-async contexts (scripts, notebooks)
result = stratum.run(classify_sentiment(text))
```

`stratum.run()` manages an event loop internally. MUST NOT be called from inside an already-running event loop.

---

## 12. Module Structure

```
stratum/
├── __init__.py          # public API: contract, infer, compute, flow, refine,
│                        #   Budget, opaque, Probabilistic, HumanDecision,
│                        #   HumanReviewContext, await_human, parallel, debate,
│                        #   race, configure, run
├── decorators.py        # @infer, @compute, @flow, @contract, @refine
├── executor.py          # @infer execution loop
├── compiler.py          # prompt compiler: assembly, opaque handling, hash
├── contracts.py         # contract registry, JSON Schema compilation, content hash,
│                        #   opaque[T] class and _OpaqueMarker
├── budget.py            # Budget dataclass, enforcement
├── hitl.py              # await_human, HumanDecision, HumanReviewContext,
│                        #   ReviewSink protocol, ConsoleReviewSink, PendingReview
├── concurrency.py       # stratum.parallel, stratum.debate, stratum.race
├── trace.py             # TraceRecord, in-memory store
└── exporters/
    └── otlp.py          # built-in OTLP emitter — HTTP/JSON, no SDK dependency
```

---

## 13. Minimal Complete Example

```python
from stratum import contract, infer, compute, flow, Budget
from typing import Literal, Annotated
from pydantic import Field

@contract
class SentimentResult:
    label: Literal["positive", "negative", "neutral"]
    confidence: Annotated[float, Field(ge=0.0, le=1.0)]
    reasoning: str

@contract
class Resolution:
    response: str
    escalate: bool

@infer(
    intent="Classify the emotional tone of customer feedback",
    context="Treat sarcasm as negative. When genuinely ambiguous, use neutral.",
    ensure=lambda r: r.confidence > 0.7,
    budget=Budget(ms=500, usd=0.001),
    retries=3,
)
def classify_sentiment(text: str) -> SentimentResult: ...

@compute
def needs_escalation(sentiment: SentimentResult, category: str) -> bool:
    return sentiment.label == "negative" and sentiment.confidence > 0.9

@infer(
    intent="Draft a helpful response to a support ticket",
    ensure=lambda r: len(r.response) > 0,
    budget=Budget(ms=1000, usd=0.002),
)
def draft_response(text: str, category: str, sentiment: SentimentResult) -> Resolution: ...

@flow(budget=Budget(ms=5000, usd=0.01))
async def process_ticket(text: str, category: str) -> Resolution:
    sentiment = await classify_sentiment(text=text)
    if needs_escalation(sentiment, category):
        return Resolution(response="Escalated to senior support.", escalate=True)
    return await draft_response(text=text, category=category, sentiment=sentiment)
```
