# Execution Model

## Two Compilers, One Language

Stratum compiles to two targets simultaneously:

1. **Runtime executor** — handles `compute` blocks, `flow` orchestration, `given`/`ensure` evaluation, retry loops
2. **Prompt compiler** — assembles LLM context from contracts, intents, inputs, annotations, and failure history

These are not separate tools or pipelines. They operate on the same AST and produce a unified execution artifact.

---

## The Prompt Compiler

The prompt compiler is what distinguishes Stratum from "calling an LLM from code." It maintains a structured intermediate representation — the **context object** — that accumulates formal artifacts and natural language annotations and composes them deterministically.

For each `infer` call, the prompt compiler assembles:

```
[system context]
  You are executing a typed function. Your output must conform to the specified contract.

[contract schema — from the return type declaration]
  {
    "label": "positive" | "negative" | "neutral",
    "confidence": float between 0.0 and 1.0,
    "reasoning": string
  }

[intent — from the intent annotation]
  Classify the emotional tone of customer feedback text.

[context annotations — from context blocks, stacked in order]
  Treat sarcasm as negative. When genuinely ambiguous, use neutral.

[input bindings — typed]
  text: "Great product but shipping was slow"

[postconditions — so LLM knows what it must satisfy]
  Your response must satisfy:
  - result.confidence > 0.7

[output format instruction — auto-generated from contract]
  Respond with valid JSON conforming to the schema above. No prose outside the JSON object.
```

**`opaque[T]` fields** are never placed in the inline instruction text above. They are passed as a separate structured JSON attachment in the user turn. The prompt instruction references them by name only:

```
[system context + intent + context annotations + postconditions — as above]

[input bindings — non-opaque fields only, inline]
  text: "Great product but shipping was slow"

[opaque data attachment — separate JSON block, never in instruction text]
  {"reasoning": "<...value from previous agent...>"}
```

The LLM receives both, but its instruction text cannot be overwritten by opaque field content. If an `opaque[T]` field appears in an inline interpolation in compiler input, `StratumCompileError` is raised before any LLM call.

This assembly is deterministic and inspectable. You can print the compiled prompt for any `infer` call.

**v2 — DSPy-backed prompt optimization**: `compile_prompt()` can optionally delegate to a DSPy-optimized program tuned against real examples and a developer-supplied metric. The interface is identical — the optimization is internal. DSPy owns *what to say*; Stratum still owns `ensure`, retry, budget, and trace. This is the right path for teams with labeled data who want learned prompts inside Stratum's contract envelope. Requires a dataset and evaluation metric — not a v1 concern.

### Constrained Decoding Backend

The execution loop calls the LLM and validates the response against the contract schema. Two deployment contexts:

**API-based models** (Anthropic, OpenAI, etc.) — structured outputs API handles schema enforcement at the generation level. Parse failures are rare but possible; caught at step 4 and retried with structured feedback.

**Self-hosted models** (vLLM, llama.cpp) — [Outlines](https://github.com/outlines-dev/outlines) is the correct constrained decoding backend. Outlines manipulates token sampling logits to make invalid output impossible at generation time — not filtered after, blocked before. Parse failures become structurally impossible.

Integration path: LiteLLM → vLLM → Outlines. LiteLLM already supports vLLM as a provider; Outlines integrates with vLLM natively. No Stratum code changes required — configure LiteLLM to route to a vLLM+Outlines endpoint and constrained decoding is automatic.

Not a v1 dependency. Document as the recommended upgrade path for teams moving to self-hosted inference.

---

## Execution Flow for `infer`

```
call classifySentiment("Great product but shipping was slow")
  │
  ├─ 1. evaluate given conditions
  │       text.length > 0  →  true  →  proceed
  │       (false → raise immediately, no retry)
  │
  ├─ 2. compile prompt
  │       [contract schema] + [intent] + [context] + [input] + [ensure as constraints]
  │
  ├─ 3. invoke LLM
  │       model, temperature, budget from annotations (or defaults)
  │
  ├─ 4. parse output against contract schema
  │       success → proceed to step 5
  │       failure → inject parse error, retry from step 3 (counts against retries limit)
  │
  ├─ 5. evaluate ensure conditions
  │       result.confidence > 0.7  →  true  →  return typed result
  │       false → inject structured failure, retry from step 3
  │             "Your previous response had confidence=0.4.
  │              Retry with a higher-confidence classification,
  │              or explain why the text is genuinely ambiguous."
  │
  └─ typed SentimentResult returned to caller
```

If all retries are exhausted, the exception includes:
- The final LLM output
- The `ensure` condition that failed
- The full retry history (inputs, outputs, failure reasons)

---

## Execution Flow for `flow`

`flow` compiles to a normal deterministic function. Each step executes in sequence. `infer` calls within the flow invoke the full infer execution model above.

```stratum
flow processTicket(ticket: SupportTicket) -> Resolution {
  let category  = infer classify(ticket.body)        // infer execution model
  let sentiment = infer classifySentiment(ticket.body) // infer execution model
  let response  = infer draftResponse(ticket, category, sentiment) // infer
  let approved  = compute ruleCheck(response, category)  // direct compute call
  return approved ? response : escalate(ticket)
}
```

The `flow` itself has no LLM involvement. This is critical — it means:
- Flows are deterministically testable (mock the `infer` calls)
- Flows can be traced, debugged, and profiled without LLM involvement
- Flows produce audit logs with typed inputs/outputs at each step

---

## Execution Flow for `refine`

`refine` adds a convergence loop around the standard `infer` model:

```
call generateCode(spec)
  │
  loop (iteration 1..max_iterations):
  │
  ├─ execute infer model → result
  │
  ├─ evaluate until: compute tests(result).allPass
  │       true  → return result (done)
  │       false → evaluate feedback: compute tests(result).failures
  │
  └─ inject feedback into next prompt:
         "The previous output failed the following tests:
          [structured test failure list]
          Fix these issues and regenerate."
  │
  max_iterations exceeded → raise ConvergenceFailure with full history
```

Key design choice: `until` and `feedback` are `compute` expressions — deterministic. The LLM doesn't decide when it's done; the formal layer does.

---

## Execution Flow for `await_human`

`await_human` is a `compute` primitive that genuinely suspends a flow — the coroutine is parked on an `asyncio.Future` until a human decision arrives.

```
call await_human(context=..., decision_type=Resolution, timeout=timedelta(hours=24))
  │
  ├─ 1. generate review_id (stable UUID)
  │
  ├─ 2. build PendingReview
  │       review_id, context, options, expires_at
  │
  ├─ 3. emit to ReviewSink
  │       default v1 sink: print to console, call input() — blocks until response
  │       v2 sinks: webhook POST, message queue publish, etc.
  │
  ├─ 4. park coroutine on asyncio.Future
  │       flow execution is suspended; event loop continues serving other tasks
  │
  ├─ 5. reviewer provides decision (via sink's resolve path)
  │       decision validated against decision_type contract
  │
  ├─ 6. Future resolves → flow resumes
  │
  └─ returns HumanDecision[Resolution]
         .value         — the typed decision
         .reviewer      — identity, if provided
         .rationale     — optional note
         .decided_at    — wall-clock timestamp
         .review_id     — correlates with trace record
```

If `timeout` is set and expires before resolution, the runtime raises `HITLTimeoutError` (includes `review_id` so the decision can be replayed if it arrives late). `on_timeout=fallback_value` returns a `HumanDecision` with `reviewer="auto"` instead of raising.

**`ReviewSink` protocol:**

```python
class ReviewSink(Protocol):
    async def emit(self, review: PendingReview) -> None: ...

@dataclass
class PendingReview:
    review_id: str
    context: HumanReviewContext
    options: list[Any] | None     # structured choices, or None for freeform
    expires_at: datetime | None

    async def resolve(self, decision: HumanDecision) -> None: ...
```

**v1 default — `ConsoleReviewSink`:**

```python
class ConsoleReviewSink:
    async def emit(self, review: PendingReview) -> None:
        print(f"\n[HITL] Review required: {review.context.question}")
        if review.options:
            for i, opt in enumerate(review.options):
                print(f"  [{i}] {opt}")
        raw = input("Decision: ")
        decision = HumanDecision(
            value=parse_decision(raw, review),
            reviewer=None,
            rationale=None,
            decided_at=datetime.utcnow(),
            review_id=review.review_id,
        )
        await review.resolve(decision)
```

The `ConsoleReviewSink` blocks the thread via `input()`. In async context this is wrapped in `asyncio.get_event_loop().run_in_executor(None, input, ...)` so it doesn't block the event loop.

---

## The Context Object (Intermediate Representation)

Between prompt compilation and LLM invocation, the runtime holds a **context object**:

```
ContextObject {
  function_name: string
  intent: string?
  contract_schema: JSONSchema
  context_annotations: string[]
  postconditions: string[]         // human-readable form
  input_bindings: Map<string, typed_value>
  retry_history: RetryRecord[]
  model: ModelSpec
  budget: BudgetSpec
}
```

This IR is:
- Inspectable at runtime (`debug infer` flag dumps it)
- Serializable — can be stored as part of audit logs
- Versionable — the contract schema version is embedded
- Composable — child `infer` calls within a `flow` inherit parent context annotations

---

## Caching

`infer` calls support caching at multiple scopes:

| Scope | Behavior |
|---|---|
| `none` | No caching (default) |
| `session` | Memoize within a single flow execution |
| `global` | Persist across executions (keyed by input hash + contract version) |

Cache invalidation is automatic on contract version change. Cached results still pass through `ensure` validation.

---

## Async Execution Model

The runtime is async-first. All LLM calls are I/O-bound; asyncio is the right substrate. Requires Python 3.11+.

```python
# parallel branches — asyncio.TaskGroup (Python 3.11+)
async with asyncio.TaskGroup() as tg:
    for branch in branches:
        tg.create_task(branch.execute())
# clean cancellation on failure; results collected at boundary

# budget timeout — asyncio.timeout (Python 3.11+)
try:
    async with asyncio.timeout(budget.remaining_seconds()):
        result = await llm_call(prompt)
except TimeoutError:
    raise BudgetExceeded()
```

For synchronous contexts, use the `stratum.run()` helper — it manages the event loop internally. Do not call from inside an already-running event loop.

```python
# async — native
result = await classify_sentiment(text)

# sync shim — for scripts and notebooks
result = stratum.run(classify_sentiment(text))
```

---

## LLM Client Configuration

The runtime wraps a configurable LLM client — not a hard dependency on any specific provider SDK. Recommended integrations:

- **LiteLLM** — unified interface across 100+ models, explicit fallback lists, load balancing, cost tracking. The recommended default.
- **OpenRouter** — unified API endpoint with provider failover and cost-based routing. Drop-in OpenAI-compatible.
- **Anthropic SDK / OpenAI SDK directly** — for single-provider deployments.

The `model:` annotation on an `infer` function is a hint passed to the configured client. Provider failover, model aliases (`fast | balanced | best`), and dynamic routing are the client's responsibility, not the runtime's.

```python
# Configure at startup
stratum.configure(client=litellm)

# Or per-function via annotation
@infer(model="claude-opus-4-6")  # passed through to configured client
```

---

## Budget Enforcement

Budget annotations are hard limits enforced by the runtime, not soft hints:

```stratum
infer classify(text: string) -> Category {
  budget: 300ms, $0.0005
}
```

If the LLM call exceeds the time or cost budget, the runtime raises `BudgetExceeded` immediately. Retry attempts count against the same budget envelope.

---

## Observability

Every `infer` call produces a structured trace record. The runtime always writes these internally regardless of export configuration.

```json
{
  "function": "classifySentiment",
  "model": "claude-sonnet-4-6",
  "input": { "text": "Great product but..." },
  "compiled_prompt_hash": "abc123",
  "contract_hash": "def456",
  "attempts": 1,
  "output": { "label": "positive", "confidence": 0.87, "reasoning": "..." },
  "duration_ms": 210,
  "cost_usd": 0.00034,
  "cache_hit": false
}
```

`contract_hash` is the content hash of the contract schema at execution time. A hash change across deployments means the compiled prompt changed — LLM behavior may have drifted even without a code change. Compare hashes across deployment boundaries to detect behavioral regressions.

This enables:
- Cost tracking per function and per flow
- Latency profiling
- Debugging retry cascades
- Behavioral regression detection via contract hash comparison
- Generating training data from production traces
- Pre-flight cost estimation (v2) — built from observed distributions in trace records, not static analysis

### OpenTelemetry export (optional)

Trace records are exported as OTel spans conforming to the [OpenTelemetry Semantic Conventions for AI](https://opentelemetry.io/docs/specs/semconv/gen-ai/). Standard attributes:

```python
{
    "gen_ai.system":            "anthropic",
    "gen_ai.request.model":     "claude-sonnet-4-6",
    "gen_ai.usage.input_tokens":  312,
    "gen_ai.usage.output_tokens": 48,
    "stratum.function":          "classify_sentiment",
    "stratum.contract_hash":     "def456",
    "stratum.compiled_prompt_hash": "abc123",
    "stratum.attempts":          1,
    "stratum.cost_usd":          0.00034,
    "stratum.cache_hit":         False,
}
# each retry → span event with structured failure reason
```

Span hierarchy: `@flow` invocation → root span. Each `@infer` call → child span. `parallel` branches → concurrent child spans. The full execution tree is visible in any OTel-compatible backend.

Configure at startup:

```python
stratum.configure(
    tracer=stratum.exporters.otel(endpoint="http://localhost:4317")
)
```

Works with any OTLP-compatible backend: Jaeger, Honeycomb, Datadog, Grafana, and **Langfuse** (via its OTLP endpoint — no separate Langfuse exporter needed).

**No SDK dependency.** Stratum ships a minimal built-in OTLP emitter (`stratum/exporters/otlp.py`) — a small HTTP client that POSTs span data to any OTLP endpoint. The OTLP protocol is HTTP/JSON with a well-specified schema. No `opentelemetry-sdk`, no `opentelemetry-exporter-otlp`, no protobuf compiler.

The emitter handles:
- W3C-compliant trace/span ID generation (16/8 random bytes, hex-encoded)
- Span batching (flush on interval or buffer size)
- Export retry with exponential backoff on POST failure

~50 lines total. Zero new dependencies beyond what `litellm` already pulls in.
