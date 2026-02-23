# Language Design

## What This Document Is

This document describes the Stratum semantic model — the concepts, keywords, and invariants that the runtime enforces.

**Developers don't write this syntax directly.** The authoring surfaces are:
- Python `@infer`, `@contract`, `@flow` decorators
- TypeScript equivalents (Zod-based)
- Natural language → Claude generates a validated `.stratum` IR

The `.stratum.yaml` format is the IR that sits between those surfaces and the runtime. It's what the Python library compiles to internally, what Claude emits when planning a task, what the MCP server validates and executes. Like LLVM IR: the compiler targets it, nobody writes it by hand.

This document describes what that IR represents — the semantics the compiler enforces regardless of which authoring surface produced it.

---

## The Two Axes

Every unit of work has two orthogonal axes that can be set independently:

| | Formal | Intent |
|---|---|---|
| **What** | Type signatures, schemas, invariants | Natural language goal description |
| **How** | Deterministic computation | LLM inference |

This gives four combinations, all valid:

| What × How | Mode | Use case |
|---|---|---|
| Formal + Formal | Pure code | Parsing, math, I/O |
| Formal + Intent | Typed LLM | Classify, summarize, generate within a schema |
| Intent + Formal | Interpreted execution | LLM decides what to do, code does it |
| Intent + Intent | Full LLM | Escape hatch — truly fuzzy, unstructured work |

The language makes the combination explicit rather than burying it.

---

## Keywords

### `contract`

Defines a named data shape. Compiles to:
- A type used by the static analyzer
- A JSON schema injected into the LLM prompt context for `infer` blocks that return this type
- A runtime validator that checks LLM output against the schema

```stratum
contract SentimentResult {
  label: "positive" | "negative" | "neutral"
  confidence: float[0.0..1.0]
  reasoning: string
}
```

Contracts are not just types — they are prompt artifacts. When an `infer` block returns `SentimentResult`, the LLM is told "your output must conform to this schema" without the developer writing that instruction manually.

---

### `compute`

Marks a deterministic function. Compiled and executed as normal code. No LLM involvement.

```stratum
compute parseDate(raw: string) -> Date {
  // deterministic implementation
}
```

---

### `infer`

Marks an LLM-executed function. Has a type signature identical to `compute`. Callers cannot tell the difference.

```stratum
infer classifySentiment(text: string) -> SentimentResult {
  given: text.length > 0
  ensure: result.confidence > 0.7 or raise LowConfidence
  context: "Treat sarcasm as negative. When genuinely ambiguous, use neutral."
}
```

The body of an `infer` block contains:
- `given` — preconditions checked before invocation (synchronous, deterministic)
- `ensure` — postconditions checked against the LLM output; failure triggers retry
- `context` — plain-text prompt annotation injected as system context
- Optionally: `model`, `temperature`, `budget` annotations

---

### `intent`

A free-text description of the function's goal, placed before a function declaration. Becomes part of the prompt context for `infer` blocks. Ignored for `compute` blocks (treated as a comment).

```stratum
intent "Classify the emotional tone of customer feedback text"
infer classifySentiment(text: string) -> SentimentResult { ... }
```

---

### `flow`

A deterministic orchestration block. Always compiled to normal control flow — no LLM inference in the `flow` block itself. Calls to `infer` functions inside a `flow` are well-defined invocations with typed inputs and outputs.

```stratum
flow processTicket(ticket: SupportTicket) -> Resolution {
  let category  = infer classify(ticket.body)
  let sentiment = infer classifySentiment(ticket.body)
  let response  = infer draftResponse(ticket, category, sentiment)
  let approved  = compute ruleCheck(response, category)
  return approved ? response : escalate(ticket)
}
```

`flow` is the key to auditability. You can always read a flow and know the sequence of operations, even when individual steps are opaque LLM calls.

---

### `adaptive`

Runtime dispatch between a `compute` path and an `infer` path. The function has a single signature; the runtime selects the implementation based on a dispatch predicate.

```python
@adaptive(
    dispatch=lambda text: len(text) < 50   # compute fn, lambda, or flow-level condition
)
def classify(text: str) -> Category:
    @compute
    def _fast(text: str) -> Category:
        if "urgent" in text: return Category(label="urgent", confidence=1.0)
        raise Unhandled

    @infer(intent="Classify the category of this text", ensure=lambda r: r.confidence > 0.7)
    def _deep(text: str) -> Category: ...
```

**Semantics:**
- `dispatch` is evaluated first. If it returns `True`, the `compute` path runs. If `False`, the `infer` path runs.
- `ensure` conditions apply to both paths — they are behavioral contracts on the output, not on how it was produced.
- If `dispatch` is omitted, the `compute` path is tried first. On `Unhandled`, execution falls through to `infer`.
- Callers see the same typed return value regardless of which path ran.

**Trace:** Records `dispatch_type` (`lambda` | `compute` | `infer`), `dispatch_result` (boolean), `path_taken` (`compute` | `infer`), and any `ensure` violations.

**v1 scope:** Binary dispatch only (compute vs infer). Multi-way routing belongs in `flow` + `orchestrate`. `infer` as a dispatch predicate is deferred to v2 — see open-problems.md.

---

### `refine`

An iterative convergence loop for multi-pass LLM work. The formal layer provides the convergence signal; the LLM does the creative iteration.

```stratum
infer refine generateCode(spec: Spec) -> Code {
  until: compute tests(result).allPass
  max_iterations: 5
  feedback: compute tests(result).failures
}
```

On each failed iteration, `feedback` is evaluated and injected into the next LLM prompt as structured error context. The loop terminates when `until` returns true or `max_iterations` is exceeded.

---

### `given` / `ensure`

Preconditions and postconditions. Both are executable expressions evaluated by the runtime.

- `given` — checked before LLM invocation; failure raises immediately, no retry
- `ensure` — checked after LLM output is parsed; failure triggers structured retry

On `ensure` violation, the runtime constructs a retry prompt:

```
Your previous response violated the postcondition:
  ensure: result.confidence > 0.7
  actual: result.confidence = 0.42

Retry with a higher-confidence classification, or explain why the text is genuinely ambiguous.
```

---

### `context`

A plain-text annotation injected as system-level prompt context for `infer` blocks. Appears after the type signature is injected but before the input. Multiple `context` blocks stack.

---

### `await_human`

A first-class `compute` primitive that suspends a flow and waits for a human decision. Composes identically with `infer` and `compute` — callers receive a typed `HumanDecision[T]` result.

```stratum
flow review_pipeline(input: Document) -> Resolution {
  let debate_result = debate(participants=[critic, defender], topic=input, rounds=3)

  if debate_result.resolution_type == "disagreement" {
    let decision = await_human(
      context: HumanReviewContext {
        trigger: "debate_disagreement",
        question: "Which position is correct?",
        artifacts: { debate_history: debate_result.history }
      },
      decision_type: Resolution,
      options: [debate_result.position_a, debate_result.position_b],
      timeout: 24h,
      on_timeout: raise
    )
    return decision.value
  }

  return debate_result.resolution
}
```

`await_human` uses wall-clock `timeout` — not token budget. The runtime emits the review request to a `ReviewSink`; the default v1 sink is a console prompt. The flow coroutine is genuinely parked until the decision arrives. See `execution-model.md` for the full suspension mechanics.

---

## Function Annotations

Beyond `given`/`ensure`/`context`, `infer` blocks support:

```stratum
infer classify(text: string) -> Category {
  model: "claude-sonnet-4-6"     // pin to a specific model, or: fast | balanced | best
  temperature: 0.2               // lower = more deterministic
  budget: 500ms, $0.001          // hard limits; raise BudgetExceeded if hit
  retries: 3                     // max ensure-retry attempts
  cache: session                 // memoize within session (or: none, global)
  stable: true                   // assert output stability; false → return type is Probabilistic<T>
}
```

---

## Composability

`infer` and `compute` functions compose identically. This is a core invariant of the language.

```stratum
// This works regardless of whether classify is infer or compute
let category = classify(ticket.body)
let response = draftResponse(ticket, category)
```

You can replace an `infer` with a `compute` (or vice versa) without changing the calling code. This enables:
- Testing: mock `infer` blocks with deterministic stubs
- Migration: start with LLM, replace with rules as patterns emerge
- Cost control: swap expensive `infer` calls for fast `compute` when coverage allows

---

## Type System Overview

See [`type-system.md`](type-system.md) for full detail.

- Contracts define named types with literal unions, ranges, and nested structures
- `infer` return types must be contracts or primitives (no anonymous objects)
- The type checker enforces that `ensure` conditions reference the declared return type
- `stable: true` (default) → return type is `T`; `stable: false` → return type is `Probabilistic<T>`, caller must unwrap
- Every contract carries a content hash embedded in trace records — hash changes signal behavioral drift across deployments
- `opaque[T]` is a field-level modifier: fields marked `opaque[T]` are passed as structured JSON attachments in the LLM user turn, never interpolated inline into instruction text. Prevents prompt injection across agent boundaries. `opaque[str]` is assignable to `str`; the restriction is in the prompt compiler only.
- `await_human` returns `HumanDecision[T]` — a typed wrapper with reviewer identity, rationale, and timestamp. Wall-clock timeout via `timedelta`, not token budget.

---

## What This Language Is Optimized For

- Expressing systems where some logic is formal and some is judgment-based
- Making the formal/LLM boundary visible and auditable
- Enabling composition across both modes without leaking implementation details
- Structured retry and convergence — not fire-and-forget LLM calls
- Testability — the orchestration logic is deterministic and unit-testable independently of LLM behavior
