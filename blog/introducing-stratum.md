# Introducing Stratum: LLM Calls That Behave Like the Rest of Your Code

Every team building production LLM systems hits the same wall.

They start with a few `openai.chat.completions.create()` calls. Those calls get wrapped in retry loops. The retry loops get budget checks bolted on. The budget checks get logging attached. The logging gets inconsistent. Somewhere in there, a multi-step pipeline grows up around it all — and now debugging a failure means reading a transcript, not a stack trace.

Stratum is an attempt to fix the architecture, not just the symptoms.

---

## The Core Idea

Two decorators: `@infer` and `@compute`.

`@infer` marks an LLM-executed function. `@compute` marks a deterministic function. They have identical type signatures. A caller cannot tell the difference.

```python
# These are interchangeable at the call site
@infer(intent="Classify document topic", ensure=lambda r: r.confidence > 0.8)
def classify(doc: Document) -> Category: ...

@compute
def classify(doc: Document) -> Category:
    return rule_based_classifier(doc)
```

This one property — composability — is what makes everything else work. You can test orchestration logic by swapping `@infer` calls for `@compute` stubs. You can migrate from LLM to rules when patterns emerge. You can reduce costs by replacing expensive inference with fast lookup. None of these changes touch the calling code.

---

## Contracts: Typing the Boundary

`@contract` defines a named type that compiles to a JSON Schema.

```python
@contract
class SentimentResult:
    label: Literal["positive", "negative", "neutral"]
    confidence: Annotated[float, Field(ge=0.0, le=1.0)]
    reasoning: str
```

When an `@infer` function returns `SentimentResult`, the schema is enforced via the structured outputs API — at the token level, not as post-hoc filtering. The LLM cannot produce a `label` outside the declared enum. A `confidence` outside `[0.0, 1.0]` is impossible to generate.

Every contract also gets a **content hash**: SHA-256 of its compiled JSON Schema, truncated to 12 hex chars. If you rename a field or add a constraint, the hash changes. Every trace record carries this hash. A hash change across deployment boundaries means the compiled prompt changed — LLM behavior may have drifted. This is how you detect behavioral regression without running evals.

---

## Retry Is Not What You Think

Most retry logic is dumb. It replays the full prompt and hopes the LLM does something different.

Stratum's retry is structural. `ensure` postconditions are evaluated against the LLM output. On failure, only the specific violation is injected back:

```
Previous attempt failed:
  - ensure: result.confidence > 0.7 (actual: 0.42)
Fix this issue specifically.
```

The LLM gets targeted feedback, not noise. Three structured retries beat ten brute-force ones — because the LLM knows what it got wrong.

This also means the retry loop is deterministic and testable. The conditions are Python lambdas. You can unit test them. They're not magic inside a prompt.

---

## Budget Is a Hard Constraint

```python
@infer(
    intent="Classify sentiment",
    ensure=lambda r: r.confidence > 0.7,
    budget=Budget(ms=500, usd=0.001),
    retries=3,
)
def classify_sentiment(text: str) -> SentimentResult: ...
```

`Budget(ms=500, usd=0.001)` means: if the LLM call takes more than 500ms or costs more than $0.001, raise `BudgetExceeded`. Not a soft hint — an exception.

Retry attempts count against the same budget. A `@refine` loop's total cost is bounded by the flow budget. There are no surprises.

Budget propagates through flows:

```python
@flow(budget=Budget(ms=5000, usd=0.01))
async def process_ticket(ticket: SupportTicket) -> Resolution:
    category  = await classify(ticket.body)          # draws from flow budget
    sentiment = await classify_sentiment(ticket.body) # draws from flow budget
    response  = await draft_response(...)             # draws from flow budget
    ...
```

If the flow budget is exhausted mid-execution, the next `@infer` call raises before touching the LLM.

---

## Flows Are Deterministic

```python
@flow(budget=Budget(ms=10000, usd=0.05))
async def process_ticket(ticket: SupportTicket) -> Resolution:
    category  = await classify(ticket.body)
    sentiment = await classify_sentiment(ticket.body)
    response  = await draft_response(ticket, category, sentiment)
    if not rule_check(response, category):
        return escalate(ticket)
    return response
```

`@flow` compiles to a normal async Python function. There is no LLM involvement in the orchestration itself — only in the individual `@infer` calls. This means:

- You can read the flow and know the execution sequence
- You can test orchestration logic by mocking the `@infer` calls with `@compute` stubs
- You can debug a failure with a structured trace, not a conversation transcript

The formal/LLM boundary is visible and explicit. You always know which parts are deterministic.

---

## The Prompt Compiler

What makes Stratum different from "calling an LLM with some retry logic" is the prompt compiler.

For each `@infer` call, the compiler assembles a prompt deterministically from:
1. The `intent` (natural language goal)
2. `context` annotations (stacked in order)
3. Input bindings (typed, named)
4. Retry context (only the specific violations, only on retry)

The output schema is NOT in the prompt text. It's enforced via the structured outputs API. The LLM doesn't need to be told "respond with JSON conforming to this schema" — the token generation is constrained to valid outputs.

Two things follow from this:

**Every prompt is inspectable.** You can print the compiled prompt for any `@infer` call. The prompt hash in the trace record tells you if it changed across deployments.

**Retry is targeted.** The compiler knows exactly which postcondition failed and injects only that. The base prompt never changes between retries.

---

## Concurrency

`stratum.parallel` runs multiple coroutines concurrently via `asyncio.TaskGroup` with explicit failure semantics:

```python
summary, sentiment, entities = await stratum.parallel(
    summarize(doc),
    classify_sentiment(doc.text),
    extract_entities(doc.text),
    require="all"   # "all" | "any" | N | 0
)
```

`require="all"` is the default — any failure cancels the rest and raises. `require="any"` returns the first success. `require=N` requires at least N successes. `require=0` collects everything including failures.

For high-stakes decisions: `quorum` runs the same function N times and requires majority agreement on a specific field before returning.

```python
@infer(
    intent="Classify this legal document's risk level",
    quorum=5,
    agree_on="risk_level",
    threshold=3,
)
def classify_risk(doc: Document) -> RiskAssessment: ...
```

For adversarial synthesis: `stratum.debate` runs agents against each other for N rounds, detects convergence, and passes the full argument history plus a `converged` flag to a synthesizer.

---

## Prompt Injection Protection

When one agent's output becomes another agent's input, `reasoning: str` fields can contain adversarial content that influences the downstream agent's behavior. This is the prompt injection problem in multi-agent systems, and no major framework solves it.

Stratum's solution: `opaque[T]`.

```python
@contract
class AgentOutput:
    summary: str              # interpolated inline into the next prompt — normal
    reasoning: opaque[str]   # passed as structured data, never inlined
```

`opaque[T]` is the parameterized query pattern applied to prompt construction. The field value goes to the LLM as a structured JSON attachment, separate from the instruction text. The LLM still sees it — it just can't override its instructions with it.

The prompt compiler raises `StratumCompileError` at compile time if an `opaque[T]` field appears in an inline string interpolation. Structural enforcement, not a lint warning.

---

## Human-in-the-Loop

`await_human` genuinely suspends flow execution and waits for a typed decision:

```python
@flow
async def review_controversial_content(doc: Document) -> ModerationDecision:
    result = await classify_content(doc)

    if result.confidence < 0.6:
        decision = await await_human(
            context=HumanReviewContext(
                question="Is this content acceptable?",
                trigger="low_confidence",
                artifacts={"classification": result, "document": doc}
            ),
            decision_type=ModerationDecision,
            options=[ModerationDecision.APPROVE, ModerationDecision.REJECT],
            timeout=timedelta(hours=4),
            on_timeout="raise",
        )
        return decision.value

    return result.decision
```

The flow parks on an `asyncio.Future`. In v1, a console sink with `input()` handles resolution. The `ReviewSink` protocol means you can drop in a webhook, a Slack bot, or a task queue without changing the flow code.

The return type is `HumanDecision[T]` — it carries who made the decision, when, and why. The audit trail is complete.

---

## Observability

Every `@infer` call produces a structured trace record:

```json
{
  "function": "classify_sentiment",
  "model": "claude-sonnet-4-6",
  "inputs": {"text": "Great product but shipping was slow"},
  "compiled_prompt_hash": "abc123def456",
  "contract_hash": "def456abc123",
  "attempts": 2,
  "output": {"label": "mixed", "confidence": 0.73, "reasoning": "..."},
  "duration_ms": 420,
  "cost_usd": 0.00041,
  "cache_hit": false,
  "retry_reasons": ["ensure: result.confidence > 0.7 (actual: 0.51)"]
}
```

Always, regardless of export configuration. OTel export to any OTLP endpoint ships built-in — no OTel SDK dependency. The span hierarchy mirrors the execution tree: `@flow` as root, `@infer` calls as children, `stratum.parallel` branches as concurrent siblings.

`compiled_prompt_hash` and `contract_hash` are the behavioral version signals. Compare them across deployment boundaries — a hash change means the prompt changed, and LLM behavior may have drifted, even without a code change.

---

## What's Shipped

**Track 1 — Python library:** `@infer`, `@compute`, `@contract`, `@flow`, `@refine`, `opaque[T]`, `await_human`, `stratum.parallel`, `quorum`, `stratum.debate`, `stratum.race`, full budget enforcement, structured retry, and OTel export.

**Track 2 — Claude Code MCP server (`stratum-mcp`):** `.stratum.yaml` IR format, `stratum_plan` / `stratum_step_done` / `stratum_audit` / `stratum_validate`, one-command setup (`stratum-mcp setup`), four bundled Claude Code skills. Standalone package — no Track 1 library dependency.

## What's Next

Track 2: session continuity (interrupted flows survive context resets), parallel step execution, memory integration for project-specific spec patterns.

Track 3: TypeScript library, `@agent`/`spawn`/`supervise`, `orchestrate`/`adapt`/`reflect` (LLM-driven dynamic orchestration), Temporal integration (durable execution), Ray distribution, DSPy prompt optimization.

The specification is at [SPEC.md](https://github.com/regression-io/stratum/blob/main/SPEC.md). Questions and feedback welcome in [Discussions](https://github.com/regression-io/stratum/discussions).
