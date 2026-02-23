# Stratum as a Codex Execution Runtime

If you've used Codex for anything beyond a single-file task, you've run into the same problem everyone runs into.

You describe what you want. Codex makes a plan — in its head, not on paper. It starts writing. Something fails. It retries. The retry is bigger than the failure: it re-reads things it already read, re-reasons about things it already reasoned about, inflates the context, and sometimes introduces new problems while fixing old ones. By the time it's done, you have code that may or may not work, and no clear record of what it actually did.

This isn't a criticism of Codex. It's a description of what happens when a capable agent operates without a formal execution model.

Stratum is that execution model.

---

## What Codex Actually Does

Codex is OpenAI's autonomous coding agent. You give it a task in natural language — "refactor the payment module," "add OAuth support," "write integration tests for the API" — and it uses tools to do it: reading files, running commands, writing and editing code, running tests.

It's genuinely capable. It can handle multi-step tasks that would take a developer an hour. What it can't do natively is:

- Show you the execution plan before touching anything
- Retry failures with surgical precision instead of brute force
- Stop at a hard budget limit instead of degrading silently
- Produce a structured, queryable audit trail of what it did

Those aren't flaws in the model — they're missing infrastructure. Stratum provides it.

---

## What Stratum Is

Stratum is a Python library (and an MCP server that sits behind coding agents) built around two ideas.

**First:** `@infer` (an LLM call) and `@compute` (a normal function) have identical type signatures. You can't tell them apart at the call site. This means you can compose them freely, test orchestration without touching an LLM, and swap inference for deterministic logic when patterns emerge — without changing anything downstream.

**Second:** Every `@infer` call has declared contracts (what it must return), postconditions (what the output must satisfy), and a hard budget. The runtime handles retry automatically, injecting only the specific failure on each retry rather than replaying the full context. Budgets are enforced as exceptions, not suggestions.

The result is LLM calls that behave like the rest of your code: typed, bounded, retryable on specific failures, and fully observable.

---

## The OpenAI Advantage

There's a reason Stratum fits particularly well in the Codex ecosystem: OpenAI's structured outputs API is native and reliable.

When Stratum calls an `@infer` function, it enforces the output contract via a tool definition — the JSON Schema for the return type becomes the tool's parameter schema. The LLM's output is structurally valid before your code ever sees it. Not post-hoc filtering. Not "respond with JSON that looks like this." Constrained generation.

With OpenAI models:

```python
@contract
class RiskAssessment:
    level: Literal["low", "medium", "high", "critical"]
    confidence: Annotated[float, Field(ge=0.0, le=1.0)]
    factors: list[str]
    recommendation: str
```

That contract compiles to a JSON Schema. The schema becomes a tool parameter definition. The model's output is guaranteed to conform to it. `level` will always be one of the four values. `confidence` will always be in `[0.0, 1.0]`. The `factors` list will always exist. Your code never has to defensively check.

OpenAI's tool use for structured outputs is the most reliable implementation of this pattern across any major provider. Building on it is the right call.

---

## The Specific Problems Stratum Solves

### The context-eating retry

A test fails. Codex retries. The retry includes re-reading all the context it already has — the codebase, the task description, the previous attempts. Token usage balloons. Attention degrades. By the third retry, Codex is making changes that fix the test symptom while introducing a different problem.

Stratum's retry is targeted. The `ensure` postcondition tells the runtime exactly what a valid output looks like. On failure, the LLM gets only the specific violation:

```
Previous attempt failed:
  - ensure: all_tests_pass(result) (3 tests still failing: test_auth_refresh, test_token_expiry, test_logout_cascade)
Fix these issues specifically.
```

Not "retry the whole thing." The failure, and nothing else.

### No plan, no review, no rollback

Codex has a plan. You just can't see it. It exists in the model's context, implicit in the sequence of tool calls. When something goes wrong partway through a multi-step task, you often can't tell which step produced the bad state, what the intended sequence was, or which prior steps completed cleanly.

With Stratum, Codex calls `stratum_plan` before touching anything. The result is a typed execution DAG — steps, dependencies, inputs, outputs — presented for your review:

```
ExecutionPlan {
  steps: [
    { id: "1", fn: "read_payment_module", output: SourceAnalysis },
    { id: "2", fn: "identify_refactor_targets", output: RefactorPlan, depends_on: ["1"] },
    { id: "3", fn: "apply_refactors", output: RefactoredCode, depends_on: ["2"] },
    { id: "4", fn: "update_tests", output: TestSuite, depends_on: ["3"] },
    { id: "5", fn: "validate", output: ValidationResult, depends_on: ["4"],
      ensure: "all tests pass, no type errors" },
  ]
}
```

You see it. You approve it. Codex executes it. If step 4 fails, you know steps 1–3 completed successfully and exactly what they produced.

### Silent budget exhaustion

OpenAI API calls cost money. Multi-step Codex sessions on large codebases can rack up surprising costs — especially when retry loops spiral. There's no native mechanism to say "stop if this task costs more than $0.50."

Stratum's budget enforcement is hard:

```python
@flow(budget=Budget(ms=120000, usd=0.50))
async def refactor_payment_module(codebase: Codebase) -> RefactoredCode:
    analysis = await analyze_structure(codebase)
    plan = await generate_refactor_plan(analysis)
    result = await apply_refactors(codebase, plan)
    return result
```

When the envelope is exhausted, `BudgetExceeded` is raised. Not a warning — a stop. The session surfaces remaining work cleanly rather than burning money on degraded output.

### No audit trail

What did Codex actually do? Which files did it read, in what order? Which tool calls succeeded on the first try and which ones required retries? What was the total token cost of the test-writing step versus the implementation step?

You have the terminal output. That's it.

Stratum writes a structured `TraceRecord` for every `@infer` call:

```json
{
  "function": "apply_refactors",
  "model": "gpt-4o",
  "inputs": {"codebase": "...", "plan": "..."},
  "compiled_prompt_hash": "abc123def456",
  "contract_hash": "def456abc123",
  "attempts": 2,
  "output": {...},
  "duration_ms": 3420,
  "cost_usd": 0.0087,
  "retry_reasons": ["ensure: no_type_errors(result) — 4 type errors in auth.py"]
}
```

Queryable. Committable alongside the code. The audit trail is structured data, not a transcript.

---

## What It Looks Like in Practice

A developer asks Codex: "Add rate limiting to the API. Token bucket algorithm. Exclude health checks. Tests required."

**Without Stratum:**

Codex reads files. Has an implicit plan. Writes middleware. Writes tests. Tests fail — the middleware applies to the wrong route prefix. Codex retries, re-reads the routing configuration, makes a broader change that fixes the tested routes but breaks an edge case. Another retry. Eventually: code that passes the tests it wrote but has a subtle gap you'll find in production.

**With Stratum:**

Codex calls `stratum_plan`:

```
ExecutionPlan {
  steps: [
    { id: "1", fn: "read_routing_config", output: RouteMap },
    { id: "2", fn: "design_middleware", output: MiddlewareSpec, depends_on: ["1"] },
    { id: "3", fn: "implement_middleware", output: MiddlewareCode, depends_on: ["2"] },
    { id: "4", fn: "write_tests", output: TestSuite, depends_on: ["3"],
      ensure: "all routes covered, health checks excluded" },
  ],
  budget: "~6 tool calls, estimated $0.04"
}
```

Developer approves. Step 3 completes. Step 4's ensure fails: "middleware not applied to `/api/v2/` prefix." Step 3 retries with exactly that failure. Fixed. Tests pass.

`stratum_audit`:
```
Step 1: 1 attempt, 0.002 USD
Step 2: 1 attempt, 0.006 USD
Step 3: 2 attempts, 0.011 USD — retry: middleware not applied to /api/v2/ prefix
Step 4: 1 attempt, 0.018 USD
Total: 0.037 USD, 2 retries, all passing
```

The code Codex writes is annotated:

```python
@infer(
    intent="Implement token bucket rate limiting middleware",
    context="Apply to all /api/ routes. Exclude /api/health and /api/metrics.",
    ensure=lambda r: validate_coverage(r, routes),
    budget=Budget(ms=3000, usd=0.02),
    retries=3,
)
def implement_rate_limiter(spec: MiddlewareSpec, routes: RouteMap) -> MiddlewareCode: ...
```

The annotation is the intent, the constraints, and the validation — committed to the repo and readable by whoever touches this code next.

---

## For Vibe Coders

If you're using Codex to build things you couldn't build without it, and you're not reviewing typed execution plans, Stratum's value is different but just as real.

Right now, when Codex writes code that calls an LLM, it writes something like:

```python
response = openai.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": f"Classify this: {text}"}]
)
result = response.choices[0].message.content
```

Fragile. No contract on the output. No retry on failure. No budget. When it breaks three months later you're reading a string and guessing what the model was supposed to return.

With Stratum, Codex writes:

```python
@contract
class ContentClassification:
    category: Literal["safe", "review_needed", "blocked"]
    confidence: Annotated[float, Field(ge=0.0, le=1.0)]
    reason: str

@infer(
    intent="Classify whether this content is safe to publish",
    ensure=lambda r: r.confidence > 0.75,
    budget=Budget(ms=500, usd=0.001),
    retries=3,
)
def classify_content(text: str) -> ContentClassification: ...
```

That code validates its own output, retries on low confidence, stops at budget, and tells you exactly what went wrong when it fails. Codex generated it — you didn't have to write it. The spec told Codex what good LLM code looks like.

---

## The Recursive Part

Stratum makes Codex better at building LLM systems — which are themselves better because they use Stratum.

Every time Codex produces Stratum-annotated code, it creates a codebase that's more reliable, more debuggable, and more maintainable. When the next Codex session picks up that codebase, it has typed contracts and trace records to work from instead of raw strings and guesswork. The quality compounds.

At some point OpenAI models see enough `@infer` and `@contract` patterns in training that they generate them naturally. The annotation becomes the default, not the exception.

The short version: Codex stops surprising you.

---

## The Honest Limitation

Codex can ignore the MCP server. Nothing forces it to use `stratum_plan` or `stratum_execute`. This is worth being direct about.

What the MCP server actually provides is a structural default — a path that Codex takes naturally because it's the right tool for the job, not because it's forced. Three things reinforce it:

- **Environment configuration**: Register the Stratum MCP server in your Codex settings. Make it the available tool for structured execution.
- **System prompt framing**: Tell Codex to use `stratum_plan` for non-trivial tasks. It will.
- **Drift detection**: Flag generated code that contains manual retry loops or untyped LLM calls. These are signals that Codex bypassed the runtime.

This is an alignment model, not a security model. It works because Stratum-aligned behavior produces better outcomes, and Codex knows it.

---

## Status

The Stratum MCP server ships with Phase 2 of the library. The Python library (Phase 1, the core runtime) is the prerequisite.

The complete normative specification is at [SPEC.md](../SPEC.md). The library design walkthrough is at [introducing-stratum.md](introducing-stratum.md). For the Claude Code equivalent of this post, see [stratum-in-claude-code.md](stratum-in-claude-code.md).

Questions and feedback: [GitHub Discussions](https://github.com/regression-io/stratum/discussions).
