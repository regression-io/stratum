# Building Software with Claude Code + Stratum: A Tutorial

Claude Code is good at the individual moves. It reads files fluently, writes clean code, catches obvious bugs. Where it struggles is the composed task — anything where getting to a correct answer requires multiple rounds of reasoning, careful budgeting of attention, and a clear record of what was tried.

This tutorial shows how Stratum changes that. Not theoretically — with concrete session transcripts for the tasks you actually do when building software: understanding a codebase, reviewing code, adding features, debugging failures, and refactoring. In each case the comparison is the same: what Claude Code does on its own versus what it does with Stratum behind it.

The setup is Phase 2: Stratum's MCP server registered in Claude Code, giving Claude access to `stratum_plan`, `stratum_execute`, `stratum_review`, and `stratum_audit`. The library itself is the codebase we're working on — there's no better test than dogfooding.

---

## Setup

Install the library and start the MCP server:

```bash
pip install stratum
stratum mcp serve --port 7700
```

Register it in your Claude Code MCP config (`.claude/mcp.json`):

```json
{
  "mcpServers": {
    "stratum": {
      "url": "http://localhost:7700"
    }
  }
}
```

Add to your project's `CLAUDE.md`:

```markdown
## Execution Model

Non-trivial tasks use the Stratum MCP server. Before writing or modifying any code:
1. Call `stratum_plan` to generate a typed execution plan
2. Present the plan for approval
3. Execute via `stratum_execute` with the approved plan ID

For code review: use `stratum_review` with parallel passes.
For post-task audit: call `stratum_audit` and commit the output alongside the code.
```

That's all the configuration. The MCP server exposes the Stratum runtime as Claude Code tools. Claude Code calls them the way it calls any other tool — reads files, runs commands, writes code — but now with typed plans, budget enforcement, and structured traces.

---

## Workflow 1: Understanding an Unfamiliar Codebase

The most common first task: someone hands you a codebase and says "figure out how the authentication works."

**Without Stratum:**

Claude reads files in whatever order seems right. It builds up a mental model. It gives you a summary. You can't tell whether it missed something, read something out of order, or conflated two modules. The summary is confident regardless of whether the confidence is earned.

**With Stratum:**

Claude calls `stratum_plan` with the task:

```
> Understand the authentication flow in this codebase.
  What are the entry points, what does token validation actually do,
  and where are the failure modes?
```

The plan it generates:

```
ExecutionPlan {
  id: "plan_a1b2c3",
  task: "Understand authentication flow",
  steps: [
    {
      id: "1",
      fn: "discover_auth_entrypoints",
      description: "Find all files matching auth*, middleware, routes/auth",
      output: FileList,
      cost_estimate: "4 tool calls"
    },
    {
      id: "2",
      fn: "read_middleware_chain",
      description: "Read middleware files in execution order",
      output: MiddlewareAnalysis,
      depends_on: ["1"],
      cost_estimate: "3-6 tool calls"
    },
    {
      id: "3a",
      fn: "trace_token_validation",
      description: "Follow token validation from header extraction to claims",
      output: ValidationTrace,
      depends_on: ["2"],
      parallel_with: ["3b", "3c"]
    },
    {
      id: "3b",
      fn: "trace_session_handling",
      description: "Follow session creation, storage, and expiry",
      output: SessionTrace,
      depends_on: ["2"],
      parallel_with: ["3a", "3c"]
    },
    {
      id: "3c",
      fn: "find_failure_modes",
      description: "Find error handling, expired tokens, revocation",
      output: FailureModeList,
      depends_on: ["2"],
      parallel_with: ["3a", "3b"]
    },
    {
      id: "4",
      fn: "synthesize_findings",
      description: "Compile traces into coherent understanding",
      output: AuthFlowSummary,
      depends_on: ["3a", "3b", "3c"],
      ensure: "summary references specific file:line locations for each claim"
    }
  ],
  budget: "~14 tool calls, estimated 90 seconds"
}
```

Two things stand out. First, the parallel steps: token validation, session handling, and failure mode discovery happen concurrently. Wall time drops by roughly a third. Second, the `ensure` on step 4: the summary must reference specific `file:line` locations for every claim. Claude can't produce a plausible-but-vague summary and call it done — the postcondition fails and it gets told exactly what's missing.

The resulting `AuthFlowSummary` contract:

```python
@contract
class AuthFlowSummary(BaseModel):
    entry_points: list[CodeLocation]      # file, line, function
    middleware_chain: list[MiddlewareStep] # ordered
    token_validation: ValidationSummary   # with specific code refs
    session_flow: SessionSummary
    failure_modes: list[FailureMode]      # each with a triggering condition
    gaps: list[str]                       # things that couldn't be determined
```

The `gaps` field matters. The ensure postcondition doesn't just require confidence — it requires explicit acknowledgment of what wasn't resolved. An honest summary beats a confident one.

The trace after execution:

```
stratum_audit plan_a1b2c3

Step 1: discover_auth_entrypoints  —  1 attempt  4 tool calls   0.8s
Step 2: read_middleware_chain       —  1 attempt  5 tool calls   2.1s
Steps 3a+3b+3c (parallel)          —  1 attempt  11 tool calls  3.4s
Step 4: synthesize_findings         —  2 attempts 2 tool calls   1.2s
  Retry reason: 3 claims lacked file:line references

Total: 22 tool calls  7.5s
```

Step 4 retried once. The retry message was specific: "3 claims lacked file:line references." Claude got that, added the references, passed. You see exactly what had to be fixed and that only one targeted retry was needed.

---

## Workflow 2: Code Review

The standard Claude Code approach to code review: you paste in a diff or point at a file and ask "does this look right?" Claude reads it and responds. The response is sequential — it walks through the code top to bottom, catching what it catches.

The problem: sequential review has sequential blind spots. Security review requires a different mental model than logic review. Performance review requires a different model than both. One pass over the code can't hold all three simultaneously without losing fidelity.

**With Stratum:**

```python
@contract
class Finding(BaseModel):
    severity: Literal["critical", "high", "medium", "low", "info"]
    category: Literal["security", "logic", "performance", "style"]
    file: str
    line: int
    description: str
    suggestion: str
    confidence: Annotated[float, Field(ge=0.0, le=1.0)]

@infer(
    intent="Review this code for security vulnerabilities",
    context=[
        "Focus: injection, auth bypass, insecure deserialization, secrets in code",
        "Ignore style issues — security only",
        "Flag anything suspicious even if not definitely a vulnerability",
    ],
    ensure=lambda findings: all(f.confidence > 0.6 for f in findings),
    model="claude-opus-4-6",
    budget=Budget(ms=30000, usd=0.05),
    retries=2,
)
def security_review(diff: str, context_files: list[str]) -> list[Finding]: ...

@infer(
    intent="Review this code for logic errors and correctness issues",
    context=[
        "Focus: off-by-one errors, null handling, race conditions, incorrect state transitions",
        "Flag edge cases that aren't covered",
        "Note: security issues should be ignored here — assume another pass handles them",
    ],
    ensure=lambda findings: all(f.category == "logic" for f in findings),
    model="claude-opus-4-6",
    budget=Budget(ms=30000, usd=0.05),
    retries=2,
)
def logic_review(diff: str, context_files: list[str]) -> list[Finding]: ...

@infer(
    intent="Review this code for performance issues",
    context=[
        "Focus: N+1 queries, unnecessary allocations, blocking calls in async context",
        "Note expected call frequency when assessing severity",
        "Only flag genuine performance concerns — not theoretical micro-optimizations",
    ],
    ensure=lambda findings: all(f.category == "performance" for f in findings),
    model="claude-opus-4-6",
    budget=Budget(ms=20000, usd=0.04),
    retries=2,
)
def performance_review(diff: str, context_files: list[str]) -> list[Finding]: ...
```

These three run concurrently via `stratum_review`:

```python
@flow(budget=Budget(ms=60000, usd=0.15))
async def review_diff(diff: str, context_files: list[str]) -> ReviewReport:
    security_findings, logic_findings, perf_findings = await stratum.parallel(
        security_review(diff=diff, context_files=context_files),
        logic_review(diff=diff, context_files=context_files),
        performance_review(diff=diff, context_files=context_files),
        require="all",
    )

    all_findings = security_findings + logic_findings + perf_findings

    # For anything high-severity where passes disagree: debate it
    contested = [f for f in all_findings if f.severity in ("critical", "high")]
    if contested:
        resolution = await stratum.debate(
            agents=[security_review, logic_review],
            subject=contested,
            rounds=2,
            agree_on="severity",
        )
        return ReviewReport(findings=resolution.resolved, raw=all_findings)

    return ReviewReport(findings=all_findings)
```

What you get from `stratum_review` on a PR:

```
Code Review — executor.py (47 lines changed)

CRITICAL  security  executor.py:183
  Retry context from previous attempt is interpolated directly into the prompt
  without sanitization. If prior LLM output contains instruction-override text,
  it propagates to the next attempt.
  Suggestion: use opaque[str] for retry_context field in the prompt assembly.
  Confidence: 0.91

HIGH      logic     executor.py:241
  Budget clone at flow entry doesn't deep-copy the token counter. Two concurrent
  @infer calls in parallel() can race on the same counter, underreporting usage
  and potentially bypassing the budget limit.
  Suggestion: use copy.deepcopy(budget) not budget.clone() which shares the counter.
  Confidence: 0.87

MEDIUM    performance  executor.py:156
  all_records() is called on every retry attempt to build context. If a long
  flow has many prior steps, this builds an O(n) list per retry. Consider
  passing the relevant records as a parameter instead.
  Confidence: 0.74

---
3 findings | 1 critical, 1 high, 1 medium
Security pass: 1 finding  |  Logic pass: 1 finding  |  Performance pass: 1 finding
Parallel passes took 18.4s combined (6.1s wall time)
```

Three things are different here versus the native Claude Code review:

**Separation of concerns.** Each pass looks for exactly one category. The security reviewer isn't distracted by style. The logic reviewer isn't looking at import ordering. The signal-to-noise ratio is higher because the focus is narrower.

**Parallel execution.** Three independent reviews in the time it takes to run one. The `Finding` contract enforces category purity — the `ensure` postcondition on `logic_review` verifies every finding is actually a logic finding, not security dressed up as logic.

**Debate for contested severity.** When the security and logic passes both flag the same line but disagree on severity, `stratum.debate` runs them adversarially. The security pass argues `critical`, the logic pass argues `high`. A synthesizer gets the argument history and the `converged` flag. The output is a reasoned severity, not a coin flip.

The CRITICAL finding above — prompt injection via unsanitized retry context — is exactly the kind of issue a single pass misses. The security reviewer finds it by specifically looking for injection vectors. The logic reviewer, scanning for correctness issues, might note it's a string concat but not flag the security implication. Parallel focused passes catch what composite passes drop.

---

## Workflow 3: Adding a Feature

The task: add a `session_cache` to the Stratum executor so identical inputs within a flow produce one LLM call, not N.

**Without Stratum:**

Claude reads `executor.py`, understands the execution loop, designs the cache. Makes changes. Runs tests. Some tests fail because the cache interacts with budget accounting in a non-obvious way. Claude retries — re-reading the executor, re-establishing context, building up to the failing test again. The retry is bigger than the fix.

**With Stratum:**

```
> Add a session_cache to the executor.
  Identical (function, inputs) pairs within the same @flow
  should return the cached result without calling the LLM.
  Budget accounting must still apply to the first call.
  Write tests.
```

The plan:

```
ExecutionPlan {
  id: "plan_d4e5f6",
  task: "Add session_cache to executor",
  steps: [
    {
      id: "1",
      fn: "read_executor_flow",
      description: "Read executor.py and understand the @flow/_FlowContext lifecycle",
      output: ExecutorAnalysis,
      cost_estimate: "2 tool calls"
    },
    {
      id: "2",
      fn: "read_test_suite",
      description: "Read tests/test_executor.py to understand existing test structure",
      output: TestAnalysis,
      depends_on: ["1"],
      cost_estimate: "1 tool call"
    },
    {
      id: "3",
      fn: "design_cache_interface",
      description: "Design the session_cache: key type, storage location in _FlowContext, hit/miss behavior",
      output: CacheDesign,
      depends_on: ["1", "2"],
      ensure: "design addresses budget accounting on cache hit"
    },
    {
      id: "4",
      fn: "implement_cache",
      description: "Add session_cache to _FlowContext and hit/miss logic in executor loop",
      output: ImplementedFiles,
      depends_on: ["3"],
      ensure: "no new imports beyond stdlib, existing tests still pass"
    },
    {
      id: "5",
      fn: "write_tests",
      description: "Write tests: cache hit returns same object, LLM not called twice, budget charged once, ensure still runs on hit",
      output: TestFile,
      depends_on: ["4"],
      ensure: "pytest passes with zero failures, tests cover cache hit, miss, and budget-on-hit scenarios"
    }
  ],
  budget: "~12 tool calls, estimated $0.06"
}
```

You review it. A few things stand out:

- Step 3 has an `ensure` that the design explicitly addresses budget accounting on cache hits. That's the subtle interaction that trips up naive implementations. The ensure means Claude can't skip it.
- Step 5's ensure requires pytest to actually pass before the step is considered done. Not "write tests that look right" — pass the test runner.

You approve the plan. Steps 1–3 run cleanly. Step 4 runs. Step 5 fails:

```
Step 5: write_tests — attempt 1 failed
  ensure: pytest passes with zero failures
  Actual: 2 failures
    FAILED tests/test_executor.py::test_cache_hit_ensure_still_runs
      AssertionError: ensure callback not invoked on cache hit
    FAILED tests/test_executor.py::test_cache_budget_charged_once
      AssertionError: budget charged twice — once on first call, once on cache hit
```

Claude's retry is not "run the whole task again." It gets exactly those two failure messages. It goes back to step 4's implementation, finds the two bugs — the cache was bypassing the ensure check on hits, and the budget deduction was in the wrong branch — and fixes them. Tests pass.

```
stratum_audit plan_d4e5f6

Step 1: read_executor_flow     —  1 attempt  2 tool calls   1.1s
Step 2: read_test_suite        —  1 attempt  1 tool call    0.4s
Step 3: design_cache_interface —  1 attempt  1 tool call    2.3s
Step 4: implement_cache        —  1 attempt  4 tool calls   3.8s
Step 5: write_tests            —  2 attempts 3 tool calls   4.1s
  Retry reason: ensure not run on hit; budget charged twice

Total: 11 tool calls  $0.051  11.7s  1 retry
```

The audit goes in the commit message. "11 tool calls, 1 retry on ensure/budget bug" tells the next person exactly what was non-trivial.

---

## Workflow 4: Debugging a Failing Test

The test `test_budget_exceeded_on_retry` is failing in CI. It passes locally. You don't know why.

**Without Stratum:**

Claude reads the test, reads the executor, reads the budget module. Has a theory. Makes a change. Runs the test — still failing. Makes another change. Eventually produces a fix that passes but you're not sure what the actual root cause was.

**With Stratum:**

```
> test_budget_exceeded_on_retry is failing in CI but not locally.
  Here's the failure:

  FAILED tests/test_executor.py::test_budget_exceeded_on_retry
    stratum.errors.BudgetExceeded not raised

  Diagnose the root cause and fix it.
  Do not change the test assertion.
```

The plan:

```
ExecutionPlan {
  id: "plan_g7h8i9",
  task: "Debug test_budget_exceeded_on_retry CI failure",
  steps: [
    {
      id: "1",
      fn: "read_failing_test",
      description: "Read the test: what inputs, what it expects, what mock it uses",
      output: TestSpec
    },
    {
      id: "2a",
      fn: "read_budget_enforcement",
      description: "Read Budget class and all enforcement points in executor.py",
      output: BudgetCodeAnalysis,
      depends_on: ["1"],
      parallel_with: ["2b"]
    },
    {
      id: "2b",
      fn: "check_ci_differences",
      description: "Read CI config. Check: Python version, environment variables, test isolation",
      output: CIAnalysis,
      depends_on: ["1"],
      parallel_with: ["2a"]
    },
    {
      id: "3",
      fn: "form_hypotheses",
      description: "List candidate root causes. Rank by likelihood.",
      output: HypothesisList,
      depends_on: ["2a", "2b"],
      ensure: "at least one hypothesis addresses the local-vs-CI discrepancy specifically"
    },
    {
      id: "4",
      fn: "test_hypotheses",
      description: "For each hypothesis: identify the code path, read it, rule in or out",
      output: DiagnosisReport,
      depends_on: ["3"],
      ensure: "exactly one hypothesis is confirmed; all others explicitly ruled out"
    },
    {
      id: "5",
      fn: "implement_fix",
      description: "Fix the confirmed root cause. Do not change the test.",
      output: FixedFiles,
      depends_on: ["4"],
      ensure: "pytest test_budget_exceeded_on_retry passes"
    }
  ],
  budget: "~10 tool calls"
}
```

Step 3's ensure matters: Claude must produce a hypothesis that specifically addresses why the test fails in CI but not locally. This rules out "the test is wrong" as a response (the test assertion is unchanged by instruction) and forces engagement with the environment difference.

The diagnosis that comes back from step 4:

```
DiagnosisReport {
  confirmed: {
    hypothesis: "Budget.clone() uses time.monotonic() at clone time, not at call time",
    evidence: "executor.py:198 — budget_copy = budget.clone() called at flow entry.
               CI runners have higher base latency. By the time the @infer call runs,
               some of the ms budget has already been consumed by setup.
               Local: 12ms setup overhead. CI: 140ms setup overhead.",
    code_location: "executor.py:198, budget.py:47"
  },
  ruled_out: [
    "Mock timing: the mock is synchronous, no latency difference",
    "Python version: CI uses 3.11.8, local 3.11.9 — no relevant stdlib changes",
    "Environment variable: GROQ_API_KEY not set in CI — but test mocks LiteLLM entirely"
  ]
}
```

Step 5 implements the fix: budget time measurement starts at call time, not at clone time. The test passes. The diagnosis is committed alongside the fix.

This is the part that's hard to get from unstructured Claude Code sessions: "all others explicitly ruled out." The `ensure` on step 4 requires Claude to disconfirm its other theories, not just state the one it likes. Debugging traces in production are useful only if they tell you what the problem wasn't, not just what it was.

---

## Workflow 5: Refactoring a Large File

`executor.py` is 600 lines. It handles the execution loop, budget accounting, retry logic, cache management, and trace recording. It needs to be split.

**Without Stratum:**

Claude reads the file, proposes a split, starts making changes. Halfway through, it modifies `executor.py` to import from `budget_enforcer.py` — which it hasn't written yet. Tests break. It backtracks. The intermediate state is a broken codebase.

**With Stratum:**

```
> Refactor executor.py (600 lines) into focused modules.
  It currently does too many things.
  Keep the public API unchanged.
  All existing tests must pass.
```

The plan:

```
ExecutionPlan {
  id: "plan_j1k2l3",
  task: "Refactor executor.py into focused modules",
  steps: [
    {
      id: "1",
      fn: "analyze_responsibilities",
      description: "Map the current responsibilities: what does each section of executor.py do?",
      output: ResponsibilityMap,
      ensure: "every function in executor.py is assigned to exactly one responsibility"
    },
    {
      id: "2",
      fn: "design_module_split",
      description: "Propose module names, file paths, and public APIs for each responsibility",
      output: ModuleDesign,
      depends_on: ["1"],
      ensure: "no circular imports in proposed design; public API of executor.py unchanged"
    },
    {
      id: "3",
      fn: "identify_extraction_order",
      description: "Order the extractions so each step leaves tests passing",
      output: ExtractionSequence,
      depends_on: ["2"],
      ensure: "at no intermediate step does an import reference a file that doesn't exist yet"
    },
    {
      id: "4",
      fn: "extract_budget_module",
      description: "Extract Budget, BudgetEnforcer to budget.py",
      output: BudgetModule,
      depends_on: ["3"],
      ensure: "pytest passes after this step alone"
    },
    {
      id: "5",
      fn: "extract_trace_module",
      description: "Extract TraceRecord, trace collection to trace.py",
      output: TraceModule,
      depends_on: ["4"],
      ensure: "pytest passes after this step alone"
    },
    {
      id: "6",
      fn: "extract_retry_module",
      description: "Extract retry loop, ensure evaluation to retry.py",
      output: RetryModule,
      depends_on: ["5"],
      ensure: "pytest passes after this step alone"
    },
    {
      id: "7",
      fn: "clean_executor",
      description: "executor.py becomes the orchestrator — thin imports, no logic",
      output: FinalExecutor,
      depends_on: ["6"],
      ensure: "executor.py < 150 lines; pytest passes; public API unchanged"
    }
  ],
  budget: "~25 tool calls, estimated $0.12"
}
```

Step 3's ensure is the critical one: at no intermediate step does an import reference a file that doesn't exist. This is the constraint that prevents the "wrote an import for a module I haven't written yet" failure. Claude plans the extraction order specifically to satisfy this, which means writing the depended-on modules first and the depending modules second.

Each of steps 4–7 has `ensure: pytest passes after this step alone`. The refactor is a sequence of small, test-passing steps. If step 5 breaks something, the retry happens at step 5 with the specific test failure — not at step 7 after three other things have changed.

The audit:

```
stratum_audit plan_j1k2l3

Step 1: analyze_responsibilities  —  1 attempt  2 tool calls   2.1s
Step 2: design_module_split       —  1 attempt  1 tool call    3.4s
Step 3: identify_extraction_order —  2 attempts 1 tool call    2.8s
  Retry: initial order had executor.py importing retry.py before it existed
Step 4: extract_budget_module     —  1 attempt  5 tool calls   4.2s
Step 5: extract_trace_module      —  1 attempt  4 tool calls   3.1s
Step 6: extract_retry_module      —  2 attempts 5 tool calls   5.8s
  Retry: _run_ensure() reference to budget context missed in extraction
Step 7: clean_executor            —  1 attempt  3 tool calls   2.9s

Total: 21 tool calls  $0.098  24.3s  2 retries
```

Two retries. Step 3: Claude tried to write the extraction order with a forward import — caught before any code was written and replanned. Step 6: one missed reference to `budget context` in the retry module — caught by the pytest ensure, fixed surgically.

The codebase was never in a broken state. Every intermediate step passed tests. You can check out any commit in the sequence and `pytest` passes.

---

## Workflow 6: Writing Tests for Existing Code

You've just shipped the `await_human` HITL primitive. It has no tests. Write them.

```
> Write tests for stratum/hitl.py.
  Tests should cover: suspension, timeout behavior, auto-approve, rejection.
  Use real asyncio — no mocking the event loop.
  Follow the testing conventions in tests/.
```

The plan:

```
ExecutionPlan {
  id: "plan_m4n5o6",
  task: "Write tests for stratum/hitl.py",
  steps: [
    {
      id: "1",
      fn: "read_hitl_implementation",
      description: "Read hitl.py: PendingReview, ReviewSink, await_human signature",
      output: HitlAnalysis
    },
    {
      id: "2",
      fn: "read_existing_tests",
      description: "Read tests/ directory: understand conventions, fixtures, patterns",
      output: TestConventions,
      depends_on: ["1"]
    },
    {
      id: "3",
      fn: "identify_test_cases",
      description: "List the behaviors to test: what are the success paths? the failure paths? the edge cases?",
      output: TestCaseList,
      depends_on: ["1", "2"],
      ensure: "suspension, timeout (both raise and approve), auto-approve via sink, rejection, and decision_type validation are all covered"
    },
    {
      id: "4",
      fn: "write_tests",
      description: "Write tests/test_hitl.py following the conventions identified in step 2",
      output: TestFile,
      depends_on: ["3"],
      ensure: "pytest tests/test_hitl.py passes; no mocking of asyncio internals"
    }
  ],
  budget: "~8 tool calls, estimated $0.04"
}
```

Step 3's ensure specifies the behaviors by name. This is the difference between "write some tests" and "write tests that cover these specific behaviors." Claude can't write three tests that all check the happy path and call it done — the ensure checks for suspension, both timeout modes, auto-approve, rejection, and type validation. If any are missing, it gets told exactly which are absent.

The test file that comes out:

```python
# tests/test_hitl.py

import asyncio
import pytest
from datetime import timedelta
from stratum.hitl import await_human, PendingReview
from stratum.types import HumanDecision


class AutoSink:
    """Sink that resolves immediately with a preset decision."""
    def __init__(self, value, *, reject: bool = False):
        self.value = value
        self.reject = reject

    async def on_review(self, review: PendingReview) -> None:
        if self.reject:
            review.reject("test rejection")
        else:
            review.resolve(self.value)


@pytest.mark.asyncio
async def test_await_human_suspends_and_resumes():
    """Flow genuinely suspends until sink resolves."""
    resolved = []

    async def flow():
        decision = await await_human(
            context="approve this",
            decision_type=str,
            options=["yes", "no"],
            sink=AutoSink("yes"),
        )
        resolved.append(decision.value)

    await flow()
    assert resolved == ["yes"]


@pytest.mark.asyncio
async def test_timeout_raises():
    """on_timeout='raise' produces TimeoutError after deadline."""
    with pytest.raises(asyncio.TimeoutError):
        await await_human(
            context="approve this",
            decision_type=str,
            options=["yes", "no"],
            timeout=timedelta(milliseconds=50),
            on_timeout="raise",
            sink=_never_resolves_sink(),
        )


@pytest.mark.asyncio
async def test_timeout_approve():
    """on_timeout='approve' resolves with first option after deadline."""
    decision = await await_human(
        context="approve this",
        decision_type=str,
        options=["yes", "no"],
        timeout=timedelta(milliseconds=50),
        on_timeout="approve",
        sink=_never_resolves_sink(),
    )
    assert decision.value == "yes"
    assert decision.decided_by == "timeout"


@pytest.mark.asyncio
async def test_rejection_propagates():
    """Rejected review raises HumanRejected with the rejection reason."""
    from stratum.errors import HumanRejected
    with pytest.raises(HumanRejected, match="test rejection"):
        await await_human(
            context="approve this",
            decision_type=str,
            options=["yes", "no"],
            sink=AutoSink("yes", reject=True),
        )


@pytest.mark.asyncio
async def test_decision_carries_metadata():
    """HumanDecision carries value, decided_by, and timestamp."""
    decision = await await_human(
        context="approve this",
        decision_type=str,
        options=["yes"],
        sink=AutoSink("yes"),
    )
    assert decision.value == "yes"
    assert decision.decided_by is not None
    assert decision.decided_at is not None
```

The tests cover the five behaviors specified in step 3's `ensure`. They use real asyncio — `pytest.mark.asyncio`, actual `asyncio.TimeoutError` for timeout, actual `asyncio.Future` suspension under the hood. No mock of the event loop.

---

## The Audit Trail

After any non-trivial Claude Code session, `stratum_audit` produces a structured record:

```
stratum_audit --session current

SESSION SUMMARY
───────────────
Duration:       47 minutes
Plans executed: 3
Total steps:    24
Total retries:  5
Total cost:     $0.31

PLANS
─────
plan_d4e5f6  Add session_cache to executor
  Steps 1-4: clean  |  Step 5: 1 retry (2 tests failing)
  Cost: $0.051

plan_g7h8i9  Debug test_budget_exceeded_on_retry
  Steps 1-3: clean  |  Step 4: 1 retry (hypothesis not addressing CI discrepancy)
  Cost: $0.089

plan_j1k2l3  Refactor executor.py
  Steps 1-2: clean  |  Step 3: 1 retry (circular import in extraction order)
  Steps 4-5: clean  |  Step 6: 1 retry (missed budget context reference)
  Step 7: clean
  Cost: $0.098

RETRY LOG
─────────
plan_d4e5f6 step 5:   ensure not run on cache hit; budget charged twice
plan_g7h8i9 step 4:   hypothesis list didn't address local-vs-CI discrepancy
plan_j1k2l3 step 3:   executor.py would import retry.py before it was created
plan_j1k2l3 step 6:   _run_ensure() referenced budget context not in retry module

CONTRACT HASHES
───────────────
Finding (review): 3a7b91c2d4e5
TicketRoute:      8f2e04b1c7d3
SentimentResult:  1d4f72a9b8c0
  (no hash changes — prompt behavior stable)
```

This goes in the commit description. It's a precise accounting of what the session actually did — not a summary Claude wrote about what it thinks it did. The retry log tells you what was legitimately hard. The contract hashes tell you whether LLM behavior may have drifted.

---

## What This Changes

The individual moves Claude Code makes don't change: it still reads files, writes code, runs tests, makes changes. What changes is the structure around those moves.

**Before Stratum:**
- Task decomposition happens in Claude's head, invisible
- Retry is full-prompt replay, attention-wasteful
- Failures are diagnosed by reading transcripts
- Budget is whatever you accept before ending the session
- Review is serial, one mental model at a time

**After Stratum:**
- Task decomposition is explicit, reviewable, committable
- Retry is targeted — the specific failure, nothing else
- Failures are diagnosed from structured trace records with confirmed/ruled-out structure
- Budget is a hard limit, enforced as an exception
- Review is parallel, each pass focused on one category

The tradeoff is real: Stratum adds overhead. Every task starts with a planning step. The MCP round-trips add latency. For a two-file change, the overhead is not worth it.

The threshold is roughly: "would I want a diff of what Claude attempted?" If yes, use Stratum. If it's a single targeted edit, don't.

---

## Reference

**MCP tools available to Claude Code:**

| Tool | What it does |
|---|---|
| `stratum_plan` | Generate a typed execution plan for a task |
| `stratum_execute` | Execute an approved plan |
| `stratum_review` | Run parallel review passes on a diff or file |
| `stratum_audit` | Structured audit of completed plans and traces |
| `stratum_checkpoint` | Save current execution state (for long sessions) |

**Useful patterns:**

```python
# Ensure postconditions are Python lambdas — testable, not magic
ensure=lambda r: r.confidence > 0.7

# Multiple ensures: all must pass
ensure=[
    lambda r: r.confidence > 0.7,
    lambda r: len(r.findings) > 0,
]

# ensure can call external validators
ensure=lambda result: run_pytest(result.test_file).returncode == 0
```

**Session configuration:**

```markdown
# CLAUDE.md (project level)

## Stratum

For tasks touching more than 2 files:
- Call stratum_plan first, present plan before proceeding
- Call stratum_audit at end of session, include in commit

For code review:
- Use stratum_review with parallel=True
- Minimum: security + logic passes
- For high-severity findings: run debate pass

Budget defaults:
- Per @infer call: 30s, $0.05
- Per @flow: 5min, $0.30
- Override per task as needed
```

---

The full specification is at [SPEC.md](../SPEC.md). Working examples at [examples/](../examples/). The library design walkthrough is at [introducing-stratum.md](introducing-stratum.md).

Phase 2 (MCP server) ships after Phase 1 stabilizes. Track progress and drop questions in [Discussions](https://github.com/regression-io/stratum/discussions).
