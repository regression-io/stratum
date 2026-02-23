---
name: stratum-plan
description: Plan a feature using the Stratum MCP server — read existing patterns, design an approach, present it for review. No implementation. Use when you want a design validated before coding starts.
---

# Stratum Plan

Design a feature and present the plan for review before touching any code.

## When to Use

- Before starting a non-trivial feature — get the design reviewed first
- When scope is unclear and you want to surface trade-offs before committing
- As the first half of `/stratum-feature` when you want a gate before implementation
- When another developer or reviewer should approve the approach

## Instructions

1. Understand the request — ask one clarifying question if scope is ambiguous
2. Read the relevant files before writing the spec
3. Write a `.stratum.yaml` spec internally — **never show it to the user**
4. Call `stratum_plan` with the spec, flow `"plan_feature"`, and file contents as input
5. Execute each step, calling `stratum_step_done` after each
6. Present the design clearly — what will change, where, why, what the edge cases are
7. **Stop.** Do not implement. Wait for the user to approve or redirect.

**The output is a design for human review, not a starting gun.**

## Spec Template

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
    trade_offs: {type: string}
    open_questions: {type: string}

functions:
  read_codebase:
    mode: infer
    intent: >
      Read the relevant files and understand existing patterns:
      naming conventions, error handling style, how similar features are structured,
      what modules already exist that could be reused or extended.
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
      Design the implementation approach. Propose what to change, where, and how.
      Follow the patterns identified in the analysis.
      List every file that will change and why.
      Identify edge cases that must be handled.
      State trade-offs honestly — if there are two reasonable approaches, describe both.
      List any open questions that would change the design if answered differently.
    input:
      analysis: {type: string}
      feature_description: {type: string}
    output: FeatureDesign
    ensure:
      - "result.approach != ''"
      - "result.files_to_change != ''"
      - "result.trade_offs != ''"
    retries: 2

flows:
  plan_feature:
    input:
      file_contents: {type: string}
      feature_description: {type: string}
    output: FeatureDesign
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
```

## Narration Pattern

```
Reading the codebase...
Designing the approach...

Here's the plan:

**What changes:**
[files and why, in plain English]

**Approach:**
[the design in 3-5 sentences]

**Edge cases to handle:**
[list]

**Trade-offs:**
[honest description of alternatives considered]

**Open questions:**
[anything that would change the design if answered differently — or "none"]

Ready to implement when you are. Or redirect me if the approach isn't right.
```

## Memory

**Before writing the spec:** Read the project's `MEMORY.md`. Find any lines tagged `[stratum-feature]`. These encode patterns like module boundaries, test conventions, or constraints that prior sessions discovered — incorporate them into the design step's context.

**After the plan is approved and implemented** (via `/stratum-feature`): If the design step surfaced a non-obvious constraint or trade-off, append to `MEMORY.md`:

```
[stratum-feature] rate limiting belongs in middleware, not route handlers — existing pattern at routes/auth.py
[stratum-feature] new modules must be registered in app/registry.py or they won't be discovered
```
