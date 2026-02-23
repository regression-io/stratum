---
name: stratum-feature
description: Implement a feature using the Stratum MCP server — read existing patterns, design, implement, write passing tests. Each phase is a postcondition-checked step.
---

# Stratum Feature

Implement a feature using Stratum: read → design → implement → test.

## Instructions

1. Understand the request — ask one clarifying question if the scope is ambiguous
2. Read the relevant files before writing the spec (you need real file contents for the `read` steps)
3. Write a `.stratum.yaml` spec internally using the template below — **never show it to the user**
4. Call `stratum_plan` with the spec, flow `"add_feature"`, and inputs containing the file contents
5. Execute each step using your tools, calling `stratum_step_done` after each
6. Narrate progress in plain English — what you're doing, what you found, what you built

**If a step fails its postcondition:** fix your output and retry silently. Don't mention YAML — say what you corrected.

**The `implement` step's ensure requires `result.files_changed != ""`** — you cannot report implementation done without listing what changed.

**The `test` step's ensure requires `result.failures == "" or result.failures == "none"`** — tests must actually pass before the step is accepted.

## Spec Template

Adapt `intent` fields and contract fields for the specific feature. The four-step structure (read → design → implement → test) is fixed.

```yaml
version: "0.1"
contracts:
  CodebaseAnalysis:
    patterns: {type: string}
    relevant_files: {type: string}
    constraints: {type: string}
  FeatureDesign:
    approach: {type: string}
    files_to_change: {type: string}
    edge_cases: {type: string}
  ImplementationResult:
    files_changed: {type: string}
    summary: {type: string}
  TestResult:
    test_file: {type: string}
    test_count: {type: string}
    failures: {type: string}

functions:
  read_codebase:
    mode: infer
    intent: >
      Read the relevant files and understand existing patterns:
      naming conventions, error handling style, how similar features are structured.
      Record the files that will need to change and any constraints.
    input:
      file_contents: {type: string}
      feature_description: {type: string}
    output: CodebaseAnalysis
    ensure:
      - "result.relevant_files != ''"
      - "result.patterns != ''"
    retries: 2

  design_feature:
    mode: infer
    intent: >
      Design the implementation: what to change, where, and how.
      Follow the patterns identified in the analysis.
      List every file that will change and why.
      Identify edge cases that must be handled.
    input:
      analysis: {type: string}
      feature_description: {type: string}
    output: FeatureDesign
    ensure:
      - "result.approach != ''"
      - "result.files_to_change != ''"
    retries: 2

  implement_feature:
    mode: infer
    intent: >
      Implement the feature following the design exactly.
      Use the existing code patterns. No new dependencies unless necessary.
      List every file changed.
    input:
      design: {type: string}
      file_contents: {type: string}
    output: ImplementationResult
    ensure:
      - "result.files_changed != ''"
      - "result.summary != ''"
    retries: 3

  write_tests:
    mode: infer
    intent: >
      Write tests for the feature. Cover the happy path and the edge cases
      identified in the design. All tests must pass.
      Record the number of tests and any failures.
    input:
      implementation: {type: string}
      edge_cases: {type: string}
    output: TestResult
    ensure:
      - "result.failures == '' or result.failures == 'none'"
      - "int(result.test_count) >= 1"
    retries: 3

flows:
  add_feature:
    input:
      file_contents: {type: string}
      feature_description: {type: string}
    output: TestResult
    steps:
      - id: s1
        function: read_codebase
        inputs:
          file_contents: "$.input.file_contents"
          feature_description: "$.input.feature_description"
      - id: s2
        function: design_feature
        inputs:
          analysis: "$.steps.s1.output.patterns"
          feature_description: "$.input.feature_description"
        depends_on: [s1]
      - id: s3
        function: implement_feature
        inputs:
          design: "$.steps.s2.output.approach"
          file_contents: "$.input.file_contents"
        depends_on: [s2]
      - id: s4
        function: write_tests
        inputs:
          implementation: "$.steps.s3.output.summary"
          edge_cases: "$.steps.s2.output.edge_cases"
        depends_on: [s3]
```

## Narration Pattern

```
Reading the codebase...
Designing the approach...
Implementing...
Writing tests...

Done. [brief summary of what was built and what tests cover]
```

After completion, call `stratum_audit` and include the trace in the commit description.

## Memory

**Before writing the spec:** Read the project's `MEMORY.md` (at `.claude/memory/MEMORY.md` or the root). Find any lines tagged `[stratum-feature]`. Incorporate them into the `intent` fields — they encode patterns like test conventions, module boundaries, or constraints that prior sessions discovered.

**After `stratum_audit`:** For each step with `attempts > 1`, ask: does the retry reveal a project-specific constraint (a non-obvious coupling, a test convention, an invariant that must be preserved)? If yes, append a one-liner to `MEMORY.md`:

```
[stratum-feature] tests use factory_boy fixtures, not pytest fixtures — match this pattern
[stratum-feature] budget.clone() must use copy.deepcopy — shallow copy races in parallel flows
[stratum-feature] all new modules must re-export from __init__.py — existing callers expect flat imports
```

Also write patterns from the **design step** that prevented problems — design decisions that led to a clean first-attempt implementation are worth capturing.

Only write entries that would change how you write the spec or implement next time.
