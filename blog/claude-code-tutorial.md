# Building Software with Claude Code + Stratum

Claude Code is good at the individual moves. It reads files, writes code, runs tests. Where it loses you is the composed task — anything requiring multiple rounds of reasoning, careful sequencing, and a clear record of what was tried.

This tutorial shows what changes when Stratum is running behind it. Every example is a real task: understanding a codebase, reviewing code, adding a feature, debugging a failure, refactoring. In each case the transcript shows what you type and what you see. The YAML spec Claude writes internally is never visible — that's the point.

---

## Setup

```bash
pip install stratum-mcp
stratum-mcp setup
```

That's it. `setup` finds your project root, writes the MCP config, and adds the execution model instructions to your `CLAUDE.md`. Restart Claude Code and Stratum is active.

---

## Workflow 1: Understanding an Unfamiliar Codebase

**You:**
> figure out how authentication works in this codebase

**Claude:**

> I'll work through this systematically — first mapping the entry points, then tracing the middleware, then pulling it together.
>
> **Step 1 of 3 — Finding auth entry points**
> Reading the directory structure... Found three relevant files: `routes/auth.py`, `middleware/jwt.py`, `middleware/session.py`.
>
> **Step 2 of 3 — Tracing the middleware chain**
> Reading all three files... The chain is: `jwt.py:8` validates the token → `session.py:22` attaches the user → `rbac.py:41` checks permissions. Entry points are `POST /login` at `routes/auth.py:14` and `POST /logout` at `:31`.
>
> **Step 3 of 3 — Synthesizing**
> *(My first pass was too vague — retrying with specific file references.)*
>
> Here's how authentication works:
>
> **Entry points:** Login at `routes/auth.py:14`, logout at `:31`.
>
> **Middleware chain:** Every request hits `middleware/jwt.py:8` first — decodes the JWT, checks the `exp` claim at `:52`. If valid, `session.py:22` attaches the user object. `rbac.py:41` checks permissions last.
>
> **Token validation:** PyJWT decode at `jwt.py:47`. Expired token → `TokenExpired` at `:55`. Missing header → 401 at `:19`.
>
> **One gap:** Token revocation. There's no revocation list in this repo — either not implemented or in a separate service.

---

*What's happening internally: Claude wrote a three-step spec, called `stratum_plan`, and executed each step sequentially. On step 3, the postcondition `result.entry_points != ""` failed because Claude produced a paragraph summary instead of citing file:line references. The server sent back the failure; Claude fixed it and resubmitted. You saw "retrying with specific file references" — not a YAML violation string.*

---

## Workflow 2: Code Review

**You:**
> review this PR diff for the payment module refactor

**Claude:**

> Running three focused review passes — security, logic, and performance separately.
>
> **Security pass**
> One issue: `executor.py:183` — retry context is interpolated directly into the prompt. If prior LLM output contains instruction-override text, it propagates to the next attempt. Use an opaque field for retry context.
>
> **Logic pass**
> One issue: `executor.py:241` — the budget clone at flow entry doesn't deep-copy the token counter. Concurrent `@infer` calls in `parallel()` can race. Use `copy.deepcopy(budget)`.
>
> **Performance pass**
> One issue: `executor.py:156` — `all_records()` is called on every retry. O(n) per retry for long flows. Pass relevant records as a parameter instead.
>
> **Summary**
> Three findings: one critical (security), one high (logic), one medium (performance). The security issue needs to be addressed before merge — prompt injection via retry context is a real attack surface.

---

*What's happening internally: Three separate review functions, each with a focused intent. The security reviewer isn't distracted by performance. Each pass's output feeds the consolidation step.*

---

## Workflow 3: Adding a Feature

**You:**
> add a session cache to the executor — identical inputs within the same flow should hit the cache instead of calling the LLM again. budget still applies to the first call. write tests.

**Claude:**

> This touches budget accounting in a non-obvious way. Let me work through it carefully.
>
> **Step 1 of 5 — Reading the executor**
> Understanding the `@flow`/`_FlowContext` lifecycle and execution loop...
>
> **Step 2 of 5 — Reading the test suite**
> Mapping existing fixture patterns and anything cache-adjacent...
>
> **Step 3 of 5 — Designing the cache**
> Key type: `(function_qualname, frozen_inputs_hash)`. Lives on `_FlowContext` — created at flow entry, scoped to the flow lifetime. On hit: return cached result, skip LLM call, budget charged on first call only. On miss: execute normally, store result.
>
> **Step 4 of 5 — Implementing**
> Writing changes to `executor.py` and `decorators.py`...
>
> **Step 5 of 5 — Writing tests**
> *(Tests were failing on first attempt — the cache was skipping the `ensure` check on hits, and budget was being double-charged. Fixed both.)*
>
> Done. Three tests added: cache hit returns same object (LLM not called twice), budget charged on first call only, `ensure` still runs on hits. All passing.

---

*What's happening internally: The design step had postconditions requiring `budget_on_hit` and `key_type` to be non-empty — specifically to force the non-obvious budget interaction to be thought through at design time, not discovered during implementation. Step 5's postcondition required `result.failures` to be empty. It wasn't on the first attempt — two bugs caught. Claude fixed them before reporting success.*

---

## Workflow 4: Debugging a Failing Test

**You:**
> `test_budget_exceeded_on_retry` is failing in CI but not locally. `BudgetExceeded` isn't being raised. don't change the test assertion.

**Claude:**

> Investigating — I need to understand the test, the budget enforcement code, and why the CI environment might behave differently.
>
> **Step 1 of 6 — Reading the test**
> The test mocks `asyncio.sleep` and expects `BudgetExceeded` after a short timeout. Tight timing assumption.
>
> **Step 2 of 6 — Reading budget enforcement**
> `asyncio.timeout` is used for the ms budget. The enforcement point is in `execute_infer` at `:89`.
>
> **Step 3 of 6 — Checking CI config**
> CI runs on Ubuntu with Python 3.11. Local is macOS 3.12. Different `asyncio` event loop implementations.
>
> **Step 4 of 6 — Forming hypotheses**
> Three candidates: (1) event loop clock resolution differs between macOS and Linux, (2) mock of `asyncio.sleep` doesn't affect `asyncio.timeout` deadline tracking, (3) budget clone shares state across retries. The local-vs-CI discrepancy points to (1) or (2).
>
> **Step 5 of 6 — Testing hypotheses**
> (2) confirmed: `asyncio.sleep` mock doesn't advance the event loop clock. `asyncio.timeout` uses monotonic time internally — mocking `sleep` has no effect on when it fires. On macOS the timing is loose enough that it doesn't matter; Linux's tighter scheduler surfaces the race.
>
> (1) and (3) ruled out: clock resolution is irrelevant once (2) is confirmed; budget clone is a separate path.
>
> **Step 6 of 6 — Fixing**
> Replaced `asyncio.sleep` mock with `asyncio.timeout` mock at the enforcement point. Test passes in both environments.

---

*What's happening internally: Step 4 had a postcondition requiring the hypothesis list to specifically address the local-vs-CI discrepancy — forcing a genuine theory about the environmental difference, not just a generic list of guesses. Step 5 required exactly one confirmed hypothesis and explicit ruled-out entries for the rest.*

---

## Workflow 5: Refactoring a Large File

**You:**
> executor.py is 600 lines. split it up.

**Claude:**

> I'll plan the extraction order carefully — each step needs to leave a passing codebase. No broken intermediate states.
>
> **Reading executor.py**
> Identifying natural module boundaries: ref resolution, ensure compilation, flow state, the execution loop itself.
>
> **Designing the split**
> Four modules: `executor/refs.py` (ref resolution), `executor/contracts.py` (ensure compilation), `executor/state.py` (FlowContext, Budget), `executor/runner.py` (execution loop). Extraction order: refs first (no dependencies), then contracts (depends on refs), then state (depends on both), then runner last.
>
> **Extracting `refs.py`**
> Moving `resolve_ref`, `resolve_inputs`. All tests passing.
>
> **Extracting `contracts.py`**
> Moving `compile_ensure`, `compile_ensure_list`. All tests passing.
>
> **Extracting `state.py`**
> Moving `_FlowContext`, `FlowScope`, `Budget`. All tests passing.
>
> **Extracting `runner.py`**
> Moving `execute_infer`, `execute_flow`. All tests passing.
>
> Done. `executor.py` now re-exports from all four modules for backwards compatibility. Each module is under 150 lines.

---

*What's happening internally: The extraction order step had a postcondition requiring `ordered_steps` to be non-empty and coherent. Each extraction step had a postcondition requiring `test_status == "passing"` — the codebase cannot be in a broken state between steps. When an extraction attempt failed the postcondition, Claude fixed it before the flow continued.*

---

## Workflow 6: Writing Tests for Existing Code

**You:**
> write tests for the await_human feature. it needs to cover suspension-and-resume, timeouts, and rejections.

**Claude:**

> **Identifying test cases**
> *(First pass was missing rejection coverage — adding it.)*
>
> Six cases: suspension and resume, timeout with `on_timeout="raise"`, timeout with `on_timeout="approve"`, auto-approve via sink, rejection, and decision metadata on the returned value.
>
> **Writing tests**
> Using real asyncio throughout — no mocking of asyncio internals.
>
> *(First attempt: 4 tests failing — suspension test wasn't releasing the future correctly, timeout test had a race condition. Fixed both.)*
>
> Done. 6 tests, all passing.

---

*What's happening internally: The test case identification step had postconditions checking for `suspension`, `timeout`, and `rejection` by name — Claude can't write three happy-path tests and call it done. The writing step required zero failures and at least 5 tests.*

---

## Workflow 7: Learning From Past Sessions

After a few sessions, patterns accumulate: which `ensure` expressions fire every time, which steps consistently need retries, which tasks ran without Stratum and visibly struggled.

**You:**
> review the last few sessions and update the memory

**Claude:**

> Reviewing 4 recent sessions...
>
> Found 9 Stratum flows across 4 sessions.
> 12 steps needed retries — 3 reveal project-specific patterns.
> 2 tasks ran without Stratum and showed signs of going in circles.
>
> Writing 5 new memory entries.
>
> Most actionable findings:
> - Budget clone is shallow-copied in three separate flows that hit race conditions. Adding this as a pattern to check at design time.
> - The `test_status == "passing"` ensure fires on every refactor extraction that touches `executor.py` — something about that file's imports triggers test failures on first attempt. Worth noting for extraction order planning.
> - One debug session spent four tool calls re-reading files it had already read, spiraling without a hypothesis. Future debug tasks should route through `/stratum-debug`.

---

*What's happening internally: Claude reads `.jsonl` transcripts from `~/.claude/projects/<project-hash>/`, parses `stratum_plan` and `stratum_step_done` calls to find retry patterns, identifies non-Stratum tasks that showed signs of struggling, and appends tagged one-liners to `MEMORY.md`. The next time `/stratum-feature` or `/stratum-debug` runs, it reads those tags and incorporates them into its spec.*

---

## What's Consistent Across All of These

Claude Code is doing the same thing it always does: reading files, writing code, running tests. What's different:

**Task decomposition is written down.** Before Claude touches anything on a non-trivial task, it has a spec — ordered steps, typed outputs, postconditions. You don't see it, but it exists, and it's what the server is enforcing.

**Retry is targeted.** When something fails a postcondition, Claude knows exactly what failed and why. "My first pass was too vague — retrying with specific file references" is the natural language version of a specific ensure expression failing. The retry is surgical, not a full replay.

**Failures are explicit.** If Claude can't satisfy a postcondition after all its retries, the flow stops and it tells you. There's no "completed" result that's actually wrong and just passed a surface check.

**You get a trace.** At the end of any task you can ask "what did you actually do?" and get a structured answer: which steps ran, how many attempts each took, how long each took. The trace goes in the commit description.

---

## Reference

**MCP tools available to Claude:**

| Tool | What it does |
|---|---|
| `stratum_validate` | Validate a `.stratum.yaml` spec. Returns `{valid, errors}`. |
| `stratum_plan` | Validate + create execution state + return first step. |
| `stratum_step_done` | Report a completed step. Checks postconditions. Returns next step, retry request, or completion. |
| `stratum_audit` | Return the execution trace for a flow by `flow_id`. |

**Skills:**

| Skill | Invoke when |
|---|---|
| `/stratum-onboard` | First run on a new project — writes `MEMORY.md` from scratch |
| `/stratum-plan` | Designing a feature before coding starts — presents plan for review |
| `/stratum-feature` | Adding a feature |
| `/stratum-review` | Reviewing a PR or diff |
| `/stratum-debug` | Debugging a test failure or CI discrepancy |
| `/stratum-refactor` | Splitting a large file |
| `/stratum-migrate` | Rewriting bare LLM calls as `@infer` + `@contract` |
| `/stratum-test` | Writing a test suite for existing untested code |
| `/stratum-learn` | After 3–5 sessions — extract patterns into memory |

**Memory:** Each skill reads `MEMORY.md` (`.claude/memory/MEMORY.md`) before writing its spec and appends project-specific patterns after `stratum_audit`. Tagged entries like `[stratum-debug]` or `[stratum-refactor]` are picked up by the matching skill. `/stratum-learn` populates this file automatically from session transcripts.

**CLI:**

```bash
stratum-mcp setup           # configure Claude Code (run once per project)
stratum-mcp validate <file> # validate a spec file offline
```

**The spec format** (what Claude writes internally):

```yaml
version: "0.1"

contracts:
  MyOutput:
    field_name: {type: string}
    score: {type: number}

functions:
  my_step:
    mode: infer              # or "compute" for deterministic steps
    intent: "..."            # what Claude should do
    input:
      param: {type: string}
    output: MyOutput
    ensure:
      - "result.field_name != ''"
      - "result.score > 0.5"
    retries: 3               # total attempts (default: 3)

flows:
  my_flow:
    input:
      param: {type: string}
    output: MyOutput
    steps:
      - id: s1
        function: my_step
        inputs:
          param: "$.input.param"
      - id: s2
        function: next_step
        inputs:
          data: "$.steps.s1.output.field_name"
        depends_on: [s1]
```

**`ensure` expressions** are Python — `result` is the step's output with dict fields accessible as attributes:

```yaml
ensure:
  - "result.confidence > 0.7"
  - "result.label in ['positive', 'negative', 'neutral']"
  - "result.failures == '' or result.failures == 'none'"
  - "int(result.test_count) >= 5"
```

---

The full specification is at [SPEC.md](https://github.com/regression-io/stratum/blob/main/SPEC.md). The library design walkthrough is at [introducing-stratum.md](https://github.com/regression-io/stratum/blob/main/blog/introducing-stratum.md). Questions in [Discussions](https://github.com/regression-io/stratum/discussions).
