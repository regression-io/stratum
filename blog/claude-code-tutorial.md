# Building Software with Claude Code + Stratum: A Tutorial

Claude Code is good at the individual moves. It reads files fluently, writes clean code, catches obvious bugs. Where it struggles is the composed task — anything where getting to a correct answer requires multiple rounds of reasoning, careful budgeting of attention, and a clear record of what was tried.

This tutorial shows how Stratum changes that. Not theoretically — with concrete session transcripts for the tasks you actually do when building software: understanding a codebase, reviewing code, adding features, debugging failures, and refactoring. In each case the comparison is the same: what Claude Code does on its own versus what it does with Stratum behind it.

The setup is Phase 2: Stratum's MCP server registered in Claude Code, giving Claude access to `stratum_validate`, `stratum_plan`, `stratum_step_done`, and `stratum_audit`. Claude Code is the executor throughout — the MCP server manages plan state and checks postconditions. No sub-LLM calls, no separate API billing.

---

## Setup

Install the MCP server:

```bash
pip install stratum-mcp
```

Register it in Claude Code's MCP config (`.claude/mcp.json`):

```json
{
  "mcpServers": {
    "stratum": {
      "command": "stratum-mcp"
    }
  }
}
```

The server runs over stdio — Claude Code starts and manages it.

Add to your project's `CLAUDE.md`:

```markdown
## Execution Model

Non-trivial tasks use the Stratum MCP server:
1. Write the task as a `.stratum.yaml` spec — contracts, functions, and a flow
2. Call `stratum_plan` to validate the spec, create execution state, and get the first step
3. Execute each step using your own tools (Read, Bash, Edit, etc.)
4. Call `stratum_step_done` with the result — get the next step, a retry request, or completion
5. Call `stratum_audit` at the end and include the trace in the commit

For code review: write a review flow with separate infer steps for security, logic, and performance.
```

That's all the configuration. Claude Code calls the tools the same way it calls any other tool. The difference: task decomposition is written down as a YAML spec before a single file is touched, postconditions are checked by the server against what Claude actually produced, and every retry is targeted rather than a full replay.

---

## Workflow 1: Understanding an Unfamiliar Codebase

The most common first task: someone hands you a codebase and says "figure out how the authentication works."

**Without Stratum:**

Claude reads files in whatever order seems right. It builds up a mental model. It gives you a summary. You can't tell whether it missed something, read something out of order, or conflated two modules. The summary is confident regardless of whether the confidence is earned.

**With Stratum:**

Claude reads the directory listing, then writes a spec and presents it for your review:

```yaml
version: "0.1"
contracts:
  EntrypointList:
    files: {type: string}
  MiddlewareAnalysis:
    chain: {type: string}
    entry_points: {type: string}
  AuthFlowSummary:
    entry_points: {type: string}
    middleware_chain: {type: string}
    token_validation: {type: string}
    failure_modes: {type: string}
    gaps: {type: string}

functions:
  discover_entrypoints:
    mode: infer
    intent: "Find all authentication entry points — routes, middleware, decorators — from the file listing"
    input:
      file_listing: {type: string}
    output: EntrypointList
    ensure:
      - "result.files != ''"

  analyze_middleware:
    mode: infer
    intent: "Read the middleware files and map the chain: what runs, in what order, what it validates"
    input:
      entry_files: {type: string}
      file_contents: {type: string}
    output: MiddlewareAnalysis

  synthesize_summary:
    mode: infer
    intent: >
      Synthesize the middleware analysis and entry points into a coherent auth flow summary.
      Every claim must include a specific file:line reference.
      Record anything that could not be determined in the gaps field.
    input:
      entrypoints: {type: string}
      middleware: {type: string}
    output: AuthFlowSummary
    ensure:
      - "result.entry_points != ''"
      - "result.gaps is not None"
    retries: 2

flows:
  analyze_auth:
    input:
      file_listing: {type: string}
      file_contents: {type: string}
    output: AuthFlowSummary
    steps:
      - id: s1
        function: discover_entrypoints
        inputs:
          file_listing: "$.input.file_listing"
      - id: s2
        function: analyze_middleware
        inputs:
          entry_files: "$.steps.s1.output.files"
          file_contents: "$.input.file_contents"
        depends_on: [s1]
      - id: s3
        function: synthesize_summary
        inputs:
          entrypoints: "$.steps.s1.output.files"
          middleware: "$.steps.s2.output.chain"
        depends_on: [s2]
```

You review the spec. Looks right. Claude calls `stratum_plan`:

```
stratum_plan(spec=<above YAML>, flow="analyze_auth", inputs={...})
→ {
    "status": "execute_step",
    "flow_id": "a1b2c3...",
    "step_id": "s1",
    "function": "discover_entrypoints",
    "intent": "Find all authentication entry points...",
    "inputs": {"file_listing": "src/\n  routes/\n    auth.py\n..."},
    "output_contract": "EntrypointList",
    "output_fields": {"files": "string"},
    "ensure": ["result.files != ''"],
    "retries_remaining": 3
  }
```

Claude executes step `s1` — reads the directory listing, identifies auth-related files — and reports:

```
stratum_step_done(flow_id="a1b2c3...", step_id="s1",
    result={"files": "routes/auth.py, middleware/jwt.py, middleware/session.py"})
→ {"status": "execute_step", "step_id": "s2", "inputs": {"entry_files": "routes/auth.py...", ...}}
```

Steps `s2` and `s3` run the same way. On `s3`, the ensure fires on the first attempt — `result.entry_points` was empty because Claude summarized instead of citing. The server returns:

```json
{
  "status": "ensure_failed",
  "step_id": "s3",
  "violations": ["ensure 'result.entry_points != \"\"' failed"],
  "retries_remaining": 1
}
```

Claude re-executes `s3` with file:line citations. The ensure passes. The `complete` response:

```json
{
  "status": "complete",
  "output": {
    "entry_points": "routes/auth.py:14 (login), routes/auth.py:31 (logout), middleware/jwt.py:8 (validate_token)",
    "middleware_chain": "jwt.py:8 → session.py:22 → rbac.py:41",
    "token_validation": "jwt.py:47 — decode via PyJWT, exp claim checked at :52",
    "failure_modes": "Expired token: jwt.py:55 raises TokenExpired. Missing header: :19 returns 401.",
    "gaps": "Token revocation list not found — either not implemented or outside this repo"
  },
  "trace": [
    {"step_id": "s1", "function_name": "discover_entrypoints", "attempts": 1, "duration_ms": 840},
    {"step_id": "s2", "function_name": "analyze_middleware",   "attempts": 1, "duration_ms": 2100},
    {"step_id": "s3", "function_name": "synthesize_summary",   "attempts": 2, "duration_ms": 1900}
  ]
}
```

Two things stand out. First, `synthesize_summary` needed two attempts — the ensure caught a vague first output and forced Claude to add file:line references. Second, the `gaps` field: the ensure requires it to be non-null, so Claude must explicitly record what it couldn't determine. An honest summary beats a confident one.

---

## Workflow 2: Code Review

The standard Claude Code approach to code review: you paste in a diff or point at a file and ask "does this look right?" Claude reads it and responds. The response is sequential — it walks through the code top to bottom, catching what it catches.

The problem: sequential review has sequential blind spots. Security review requires a different mental model than logic review. Performance review requires a different model than both.

**With Stratum:**

```yaml
version: "0.1"
contracts:
  SecurityFindings:
    findings: {type: string}
  LogicFindings:
    findings: {type: string}
  PerformanceFindings:
    findings: {type: string}
  ReviewReport:
    security: {type: string}
    logic: {type: string}
    performance: {type: string}
    summary: {type: string}

functions:
  security_review:
    mode: infer
    intent: >
      Review this code diff for security vulnerabilities only.
      Focus: injection, auth bypass, insecure deserialization, secrets in code.
      Ignore style issues. Flag anything suspicious even if not definitely a vulnerability.
      Format each finding as: SEVERITY file:line — description — suggestion
    input:
      diff: {type: string}
      context: {type: string}
    output: SecurityFindings
    ensure:
      - "result.findings is not None"
    retries: 2

  logic_review:
    mode: infer
    intent: >
      Review this code diff for logic errors and correctness issues only.
      Focus: off-by-one errors, null handling, race conditions, incorrect state transitions.
      Flag edge cases that aren't covered. Do not flag security issues.
    input:
      diff: {type: string}
      context: {type: string}
    output: LogicFindings
    ensure:
      - "result.findings is not None"
    retries: 2

  performance_review:
    mode: infer
    intent: >
      Review this code diff for performance issues only.
      Focus: N+1 queries, unnecessary allocations, blocking calls in async context.
      Only flag genuine concerns — not theoretical micro-optimizations.
    input:
      diff: {type: string}
      context: {type: string}
    output: PerformanceFindings
    retries: 2

  consolidate_review:
    mode: infer
    intent: >
      Consolidate security, logic, and performance findings into a review report.
      Deduplicate findings that appear in multiple passes. Rank the top issues by severity.
    input:
      security: {type: string}
      logic: {type: string}
      performance: {type: string}
    output: ReviewReport

flows:
  review_diff:
    input:
      diff: {type: string}
      context: {type: string}
    output: ReviewReport
    steps:
      - id: sec
        function: security_review
        inputs:
          diff: "$.input.diff"
          context: "$.input.context"
      - id: logic
        function: logic_review
        inputs:
          diff: "$.input.diff"
          context: "$.input.context"
        depends_on: [sec]
      - id: perf
        function: performance_review
        inputs:
          diff: "$.input.diff"
          context: "$.input.context"
        depends_on: [logic]
      - id: report
        function: consolidate_review
        inputs:
          security: "$.steps.sec.output.findings"
          logic: "$.steps.logic.output.findings"
          performance: "$.steps.perf.output.findings"
        depends_on: [perf]
```

Claude executes each step in order, reporting results via `stratum_step_done`. The final `complete` response:

```json
{
  "status": "complete",
  "output": {
    "security": "CRITICAL executor.py:183 — Retry context interpolated directly into prompt without sanitization. Prior LLM output containing instruction-override text will propagate. Suggestion: use opaque field for retry_context.",
    "logic": "HIGH executor.py:241 — Budget clone at flow entry doesn't deep-copy the token counter. Concurrent @infer calls in parallel() can race. Suggestion: use copy.deepcopy(budget).",
    "performance": "MEDIUM executor.py:156 — all_records() called on every retry. O(n) per retry for long flows. Suggestion: pass relevant records as parameter.",
    "summary": "3 findings: 1 critical (security), 1 high (logic), 1 medium (performance). Critical requires immediate attention before merge."
  },
  "trace": [
    {"step_id": "sec",   "function_name": "security_review",    "attempts": 1, "duration_ms": 6200},
    {"step_id": "logic", "function_name": "logic_review",       "attempts": 1, "duration_ms": 5800},
    {"step_id": "perf",  "function_name": "performance_review", "attempts": 1, "duration_ms": 4100},
    {"step_id": "report","function_name": "consolidate_review", "attempts": 1, "duration_ms": 1900}
  ]
}
```

Two things are different here versus the native Claude Code review:

**Separation of concerns.** Each pass looks for exactly one category. The security reviewer isn't distracted by style. The logic reviewer isn't looking at import ordering. The signal-to-noise ratio is higher because the focus is narrower.

**Structured output.** The `ReviewReport` contract forces each finding to be a discrete, attributable statement. Claude can't produce a paragraph of hedged observations and call it a review — the output contract is checked on every attempt.

> **Note:** Steps run sequentially in the current implementation. True parallel execution across the three review passes is planned for a future release.

---

## Workflow 3: Adding a Feature

The task: add a `session_cache` to the Stratum executor so identical inputs within a flow produce one LLM call, not N.

**Without Stratum:**

Claude reads `executor.py`, designs the cache. Makes changes. Runs tests. Some tests fail because the cache interacts with budget accounting in a non-obvious way. Claude retries — re-reading the executor, re-establishing context, building up to the failing test again. The retry is bigger than the fix.

**With Stratum:**

```
> Add a session_cache to the executor.
  Identical (function, inputs) pairs within the same @flow
  should return the cached result without calling the LLM.
  Budget accounting must still apply to the first call.
  Write tests.
```

Claude writes and presents the spec:

```yaml
version: "0.1"
contracts:
  ExecutorAnalysis:
    flow_lifecycle: {type: string}
    execution_loop: {type: string}
    budget_integration: {type: string}
  CacheDesign:
    key_type: {type: string}
    storage: {type: string}
    hit_behavior: {type: string}
    budget_on_hit: {type: string}
  ImplementationResult:
    files_changed: {type: string}
    summary: {type: string}
  TestResult:
    passed: {type: string}
    failures: {type: string}

functions:
  read_executor:
    mode: infer
    intent: "Read executor.py and understand the @flow/_FlowContext lifecycle and execution loop"
    input:
      executor_content: {type: string}
    output: ExecutorAnalysis

  read_tests:
    mode: infer
    intent: "Read the test suite and identify fixture patterns, existing cache-adjacent tests"
    input:
      test_content: {type: string}
    output: ExecutorAnalysis

  design_cache:
    mode: infer
    intent: >
      Design the session_cache: key type, where it lives in _FlowContext, hit/miss behavior,
      and how budget accounting applies on cache hit (charged on first call only).
    input:
      executor_analysis: {type: string}
      test_analysis: {type: string}
    output: CacheDesign
    ensure:
      - "result.budget_on_hit != ''"
      - "result.key_type != ''"
    retries: 2

  implement_cache:
    mode: infer
    intent: "Implement the session_cache in _FlowContext and hit/miss logic in the executor loop. No new imports beyond stdlib."
    input:
      design: {type: string}
      executor_content: {type: string}
    output: ImplementationResult
    ensure:
      - "result.files_changed != ''"
    retries: 3

  write_tests:
    mode: infer
    intent: >
      Write tests: cache hit returns same object (LLM not called twice),
      budget charged on first call not on hits, ensure still runs on cache hit.
      All tests must pass.
    input:
      implementation: {type: string}
      test_patterns: {type: string}
    output: TestResult
    ensure:
      - "result.failures == '' or result.failures == 'none'"
    retries: 3

flows:
  add_session_cache:
    input:
      executor_content: {type: string}
      test_content: {type: string}
    output: TestResult
    steps:
      - id: s1
        function: read_executor
        inputs:
          executor_content: "$.input.executor_content"
      - id: s2
        function: read_tests
        inputs:
          test_content: "$.input.test_content"
        depends_on: [s1]
      - id: s3
        function: design_cache
        inputs:
          executor_analysis: "$.steps.s1.output.flow_lifecycle"
          test_analysis: "$.steps.s2.output.execution_loop"
        depends_on: [s2]
      - id: s4
        function: implement_cache
        inputs:
          design: "$.steps.s3.output.key_type"
          executor_content: "$.input.executor_content"
        depends_on: [s3]
      - id: s5
        function: write_tests
        inputs:
          implementation: "$.steps.s4.output.summary"
          test_patterns: "$.steps.s2.output.budget_integration"
        depends_on: [s4]
```

You review it. Step `s3`'s ensures require `budget_on_hit` and `key_type` to be non-empty — the subtle interaction that trips up naive implementations. Step `s5`'s ensure requires `failures` to be empty. Not "write tests that look right" — they must actually pass.

You approve. Claude calls `stratum_plan`, executes steps `s1`–`s4` cleanly, then reports step `s5` results. The ensure fires — two tests are failing. The server responds:

```json
{
  "status": "ensure_failed",
  "step_id": "s5",
  "violations": ["ensure 'result.failures == \"\" or result.failures == \"none\"' failed"],
  "retries_remaining": 2
}
```

Claude re-reads its implementation, finds the two bugs — the cache was bypassing the ensure check on hits, and the budget deduction was in the wrong branch — and fixes them. Reports again. The ensure passes.

The `complete` trace:

```json
{
  "trace": [
    {"step_id": "s1", "function_name": "read_executor",   "attempts": 1, "duration_ms": 1100},
    {"step_id": "s2", "function_name": "read_tests",      "attempts": 1, "duration_ms": 400},
    {"step_id": "s3", "function_name": "design_cache",    "attempts": 1, "duration_ms": 2300},
    {"step_id": "s4", "function_name": "implement_cache", "attempts": 1, "duration_ms": 3800},
    {"step_id": "s5", "function_name": "write_tests",     "attempts": 2, "duration_ms": 4100}
  ]
}
```

The trace goes in the commit description. "1 retry on `write_tests` — ensure not run on hit; budget charged twice" tells the next person exactly what was non-trivial.

---

## Workflow 4: Debugging a Failing Test

The test `test_budget_exceeded_on_retry` is failing in CI. It passes locally. You don't know why.

**With Stratum:**

```
> test_budget_exceeded_on_retry is failing in CI but not locally.
  stratum.errors.BudgetExceeded not raised.
  Diagnose the root cause and fix it.
  Do not change the test assertion.
```

The spec Claude writes:

```yaml
version: "0.1"
contracts:
  TestSpec:
    inputs: {type: string}
    expectation: {type: string}
    mock: {type: string}
  BudgetCodeAnalysis:
    enforcement_points: {type: string}
    clone_behavior: {type: string}
  CIAnalysis:
    environment_differences: {type: string}
  HypothesisList:
    hypotheses: {type: string}
    ci_discrepancy_addressed: {type: string}
  DiagnosisReport:
    confirmed: {type: string}
    evidence: {type: string}
    code_location: {type: string}
    ruled_out: {type: string}
  FixResult:
    files_changed: {type: string}
    explanation: {type: string}

functions:
  read_failing_test:
    mode: infer
    intent: "Read the test: what inputs, what it expects, what mock it uses"
    input: {test_content: {type: string}}
    output: TestSpec

  read_budget_enforcement:
    mode: infer
    intent: "Read the Budget class and all enforcement points in executor.py"
    input:
      budget_content: {type: string}
      executor_content: {type: string}
    output: BudgetCodeAnalysis

  check_ci_differences:
    mode: infer
    intent: "Read CI config. Check Python version, env vars, test isolation, timing assumptions"
    input: {ci_config: {type: string}}
    output: CIAnalysis

  form_hypotheses:
    mode: infer
    intent: "List candidate root causes ranked by likelihood. One must specifically address the local-vs-CI discrepancy."
    input:
      test_spec: {type: string}
      budget_analysis: {type: string}
      ci_analysis: {type: string}
    output: HypothesisList
    ensure:
      - "result.ci_discrepancy_addressed != ''"
      - "result.hypotheses != ''"
    retries: 2

  test_hypotheses:
    mode: infer
    intent: >
      For each hypothesis: identify the code path, evaluate it, rule in or out.
      Exactly one hypothesis confirmed; all others explicitly ruled out.
    input:
      hypotheses: {type: string}
      budget_analysis: {type: string}
    output: DiagnosisReport
    ensure:
      - "result.confirmed != ''"
      - "result.ruled_out != ''"
    retries: 2

  implement_fix:
    mode: infer
    intent: "Fix the confirmed root cause. Do not change the test."
    input:
      diagnosis: {type: string}
      code_location: {type: string}
      executor_content: {type: string}
    output: FixResult
    retries: 3

flows:
  debug_ci_failure:
    input:
      test_content: {type: string}
      budget_content: {type: string}
      executor_content: {type: string}
      ci_config: {type: string}
    output: FixResult
    steps:
      - id: s1
        function: read_failing_test
        inputs: {test_content: "$.input.test_content"}
      - id: s2
        function: read_budget_enforcement
        inputs:
          budget_content: "$.input.budget_content"
          executor_content: "$.input.executor_content"
        depends_on: [s1]
      - id: s3
        function: check_ci_differences
        inputs: {ci_config: "$.input.ci_config"}
        depends_on: [s1]
      - id: s4
        function: form_hypotheses
        inputs:
          test_spec: "$.steps.s1.output.expectation"
          budget_analysis: "$.steps.s2.output.enforcement_points"
          ci_analysis: "$.steps.s3.output.environment_differences"
        depends_on: [s2, s3]
      - id: s5
        function: test_hypotheses
        inputs:
          hypotheses: "$.steps.s4.output.hypotheses"
          budget_analysis: "$.steps.s2.output.clone_behavior"
        depends_on: [s4]
      - id: s6
        function: implement_fix
        inputs:
          diagnosis: "$.steps.s5.output.confirmed"
          code_location: "$.steps.s5.output.code_location"
          executor_content: "$.input.executor_content"
        depends_on: [s5]
```

Step `s4`'s ensure matters: the hypothesis list must specifically address why the test fails in CI but not locally. Step `s5`'s ensures require exactly one confirmed hypothesis and explicit ruled-out entries for the rest. Debugging traces in production are useful only if they tell you what the problem wasn't, not just what it was.

---

## Workflow 5: Refactoring a Large File

`executor.py` is 600 lines. It needs to be split.

The spec Claude writes enforces a critical constraint at step `s3`:

```yaml
  identify_extraction_order:
    mode: infer
    intent: >
      Order the extractions so each step leaves a passing codebase.
      At no intermediate step should an import reference a file that doesn't exist yet.
    input:
      module_design: {type: string}
    output: ExtractionSequence
    ensure:
      - "result.ordered_steps != ''"
    retries: 3
```

And each extraction step:

```yaml
  extract_module:
    mode: infer
    intent: "Extract the specified module. After this step alone, all existing tests must pass."
    input:
      module_name: {type: string}
      extraction_order: {type: string}
      executor_content: {type: string}
    output: ExtractionResult
    ensure:
      - "result.test_status == 'passing'"
    retries: 3
```

The ensure on `identify_extraction_order` — at no intermediate step does an import reference a file that doesn't exist — is the constraint that prevents the "wrote an import for a module I haven't written yet" failure. Claude plans the extraction order specifically to satisfy this. When it doesn't on the first attempt, the server rejects it and Claude replans.

Each extraction step's ensure requires tests to pass before the flow continues. The codebase is never in a broken intermediate state. If step `s5` breaks something, the retry happens at `s5` with the specific test failure — not at `s6` after something else has changed.

---

## Workflow 6: Writing Tests for Existing Code

```yaml
  identify_cases:
    mode: infer
    intent: >
      List the behaviors to test. Must cover all of:
      suspension-and-resume, timeout-raise, timeout-approve,
      auto-approve via sink, rejection, and decision metadata.
    input:
      hitl_analysis: {type: string}
      conventions: {type: string}
    output: TestCaseList
    ensure:
      - "'suspension' in result.cases"
      - "'timeout' in result.cases"
      - "'rejection' in result.cases"
    retries: 2

  write_tests:
    mode: infer
    intent: "Write tests/test_hitl.py. Use real asyncio — no mocking of asyncio internals. All tests must pass."
    input:
      cases: {type: string}
      conventions: {type: string}
      hitl_content: {type: string}
    output: TestFile
    ensure:
      - "result.failures == '' or result.failures == 'none'"
      - "int(result.test_count) >= 5"
    retries: 3
```

Step `identify_cases`'s ensures specify the behaviors by name. Claude can't write three tests that all check the happy path and call it done — the server checks for `suspension`, `timeout`, and `rejection` in the output. If any are missing, it gets told exactly which ones. `write_tests` requires both zero failures and at least 5 tests.

---

## The Execution Trace

Every `stratum_step_done` that returns `"status": "complete"` includes a `trace` array:

```json
{
  "status": "complete",
  "output": {...},
  "trace": [
    {"step_id": "s1", "function_name": "read_executor",   "attempts": 1, "duration_ms": 1100},
    {"step_id": "s2", "function_name": "design_cache",    "attempts": 1, "duration_ms": 2300},
    {"step_id": "s3", "function_name": "implement_cache", "attempts": 1, "duration_ms": 3800},
    {"step_id": "s4", "function_name": "write_tests",     "attempts": 2, "duration_ms": 4100}
  ],
  "total_duration_ms": 11300
}
```

This goes in the commit description. "1 retry on `write_tests` — ensure not run on hit" tells the next person exactly what was non-trivial. Call `stratum_audit(flow_id)` at any point to get the same trace for a flow in progress.

---

## What This Changes

The individual moves Claude Code makes don't change: it still reads files, writes code, runs tests. What changes is the structure around those moves.

**Before Stratum:**
- Task decomposition happens in Claude's head, invisible
- Retry is full-context replay, attention-wasteful
- Failures diagnosed by reading transcript
- Review is serial, one mental model at a time

**After Stratum:**
- Task decomposition is a `.stratum.yaml` spec — reviewable before execution starts
- Retry is targeted — the server returns the specific ensure violation, nothing else
- Failures are structured trace records with attempt counts
- Review uses separate focused functions per category

The tradeoff is real: Stratum adds overhead. Writing the YAML spec takes time. The threshold is roughly: "would I want a record of what Claude attempted?" If yes, use Stratum. For a single targeted edit, don't.

---

## Reference

**MCP tools available to Claude Code:**

| Tool | What it does |
|---|---|
| `stratum_validate` | Validate a `.stratum.yaml` spec. Returns `{valid, errors}`. |
| `stratum_plan` | Validate + create execution state + return first step. Takes `spec` (YAML string), `flow` (name), `inputs` (dict). |
| `stratum_step_done` | Report a completed step. Takes `flow_id`, `step_id`, `result` (dict). Returns next step, ensure failure with retry instructions, or flow completion. |
| `stratum_audit` | Return execution trace for a flow by `flow_id`. |

**CLI usage:**

```bash
# Validate a spec file offline (exits 0 on success, 1 on error)
stratum-mcp validate path/to/spec.yaml
```

**`ensure` expressions:**

```yaml
# Python expressions — 'result' is the step's output (dict fields accessible as attributes)
ensure:
  - "result.confidence > 0.7"
  - "result.label in ['positive', 'negative', 'neutral']"
  - "result.failures == '' or result.failures == 'none'"
  - "int(result.test_count) >= 5"

# Dunder attributes blocked: "result.__class__" raises a compile error at plan time
```

**IR spec structure:**

```yaml
version: "0.1"

contracts:
  MyContract:
    field_name: {type: string}    # type: string | number | integer | boolean
    another_field: {type: number}

functions:
  my_function:
    mode: infer           # or "compute" (deterministic, no LLM)
    intent: "..."         # what Claude Code should do for this step
    input:
      param_name: {type: string}
    output: MyContract    # must reference a defined contract
    ensure:               # Python expressions; all must pass or step is retried
      - "result.field_name != ''"
    retries: 3            # total attempts (default: 3)

flows:
  my_flow:
    input:
      input_param: {type: string}
    output: MyContract
    steps:
      - id: s1
        function: my_function
        inputs:
          param_name: "$.input.input_param"       # $ ref to flow input
      - id: s2
        function: another_function
        inputs:
          param: "$.steps.s1.output.field_name"   # $ ref to prior step output field
        depends_on: [s1]
```

**Session configuration:**

```markdown
# CLAUDE.md (project level)

## Stratum

For tasks touching more than 2 files:
- Write a `.stratum.yaml` spec first and present it for approval
- Call `stratum_plan` to start execution
- For each step: execute using your tools, then call `stratum_step_done`
- Include the execution trace in the commit

For code review:
- Write a review flow with separate infer functions for security, logic, and performance
- Each function's intent should explicitly exclude other categories
```

---

The full specification is at [SPEC.md](../SPEC.md). Working examples at [examples/](../examples/). The library design walkthrough is at [introducing-stratum.md](introducing-stratum.md).

Phase 2 (MCP server) ships after Phase 1 stabilizes. Track progress and drop questions in [Discussions](https://github.com/regression-io/stratum/discussions).
