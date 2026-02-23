---
name: stratum-review
description: Run a structured three-pass code review (security, logic, performance) using the Stratum MCP server. Each pass is a focused infer step with its own postconditions.
---

# Stratum Review

Run a structured three-pass code review using Stratum.

## Instructions

1. Read the diff or files being reviewed — understand what changed before writing the spec
2. Write a `.stratum.yaml` spec internally using the template below — **never show it to the user**
3. Call `stratum_plan` with the spec, flow `"review_diff"`, and inputs `{diff, context}`
4. Execute each step using your tools, calling `stratum_step_done` after each
5. Narrate only in plain English — step names, findings, and a final summary

**If a step fails its postcondition:** fix your output and retry silently. Don't mention the YAML expression — say what you corrected ("Adding specific file:line references").

## Spec Template

Adapt `intent` for the specific diff. Keep the three-pass structure and the consolidation step.

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
      Review this diff for security issues only: injection, auth bypass,
      secrets in code, insecure deserialization, missing input validation.
      Format each finding as: SEVERITY file:line — description — fix suggestion.
      If none found, say "No security issues found."
    input:
      diff: {type: string}
      context: {type: string}
    output: SecurityFindings
    ensure:
      - "result.findings is not None"
      - "result.findings != ''"
    retries: 2

  logic_review:
    mode: infer
    intent: >
      Review this diff for logic errors only: off-by-one, null handling,
      incorrect state transitions, race conditions, unhandled edge cases.
      Do not flag security issues. Format each finding as: SEVERITY file:line — description — fix suggestion.
      If none found, say "No logic issues found."
    input:
      diff: {type: string}
      context: {type: string}
    output: LogicFindings
    ensure:
      - "result.findings is not None"
      - "result.findings != ''"
    retries: 2

  performance_review:
    mode: infer
    intent: >
      Review this diff for performance issues only: N+1 queries, unnecessary
      allocations, blocking calls in async context, O(n²) where O(n) is possible.
      Only flag genuine concerns, not theoretical micro-optimizations.
      Format each finding as: SEVERITY file:line — description — fix suggestion.
      If none found, say "No performance issues found."
    input:
      diff: {type: string}
      context: {type: string}
    output: PerformanceFindings
    retries: 2

  consolidate_review:
    mode: infer
    intent: >
      Consolidate security, logic, and performance findings into a review report.
      Deduplicate any findings that appear in multiple passes.
      Rank the top issues by severity. Write a one-sentence summary.
    input:
      security: {type: string}
      logic: {type: string}
      performance: {type: string}
    output: ReviewReport
    ensure:
      - "result.summary != ''"
    retries: 2

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

## Narration Pattern

```
Running security pass...
Running logic pass...
Running performance pass...

**Security:** [findings or "None"]
**Logic:** [findings or "None"]
**Performance:** [findings or "None"]

**Summary:** [one sentence]
```

After completion, call `stratum_audit` and note any steps that required retries.

## Memory

**Before writing the spec:** Read the project's `MEMORY.md` (at `.claude/memory/MEMORY.md` or the root). Find any lines tagged `[stratum-review]`. Incorporate them into the relevant `intent` fields — they encode project-specific patterns discovered in previous review sessions.

**After `stratum_audit`:** For each step with `attempts > 1`, ask: does the retry reason reveal something specific about this codebase (a recurring pattern, a module with known fragility, a class of issue this project tends to have)? If yes, append a one-liner to `MEMORY.md`:

```
[stratum-review] <pattern> — e.g. "auth middleware bypasses rate limiting for /internal routes"
[stratum-review] security: f-string SQL construction in db/queries.py — always check for injection
[stratum-review] logic: budget clone is not deep-copied — concurrent flows can race on token counter
```

Only write entries that would change how you write the spec next time. Skip generic observations like "output was vague" — those aren't project-specific.
