---
name: stratum-refactor
description: Refactor a large file into smaller modules using the Stratum MCP server. Extraction order is planned so the codebase is never in a broken state between steps.
---

# Stratum Refactor

Split a large file using Stratum: analyze → design modules → order extractions → extract one at a time.

## Instructions

1. Read the file being split before writing the spec
2. Write a `.stratum.yaml` spec internally — **never show it to the user**
3. Call `stratum_plan` with the spec, flow `"split_file"`, and the file content as input
4. Execute each step, calling `stratum_step_done` after each
5. Narrate in plain English — what you're identifying, what the modules will be, progress on each extraction

**Critical postconditions:**
- Extraction order step: must produce an explicit ordered list where no step imports a file that doesn't exist yet
- Each extraction step: tests must pass before the flow advances — the codebase cannot be in a broken intermediate state

**If test failures occur after an extraction:** fix them before calling `stratum_step_done`. The ensure rejects partial results.

## Spec Template

Adapt the number of `extract_module` steps to the actual number of modules being created.

```yaml
version: "0.1"
contracts:
  FileAnalysis:
    logical_groups: {type: string}
    dependency_graph: {type: string}
    public_surface: {type: string}
  ModuleDesign:
    modules: {type: string}
    responsibilities: {type: string}
  ExtractionSequence:
    ordered_steps: {type: string}
    rationale: {type: string}
  ExtractionResult:
    module_name: {type: string}
    files_created: {type: string}
    test_status: {type: string}

functions:
  analyze_file:
    mode: infer
    intent: >
      Read the file and identify logical groupings: which functions/classes
      belong together, what the dependency relationships are, what the public
      surface is. Don't propose module names yet — just map the structure.
    input:
      file_content: {type: string}
    output: FileAnalysis
    ensure:
      - "result.logical_groups != ''"
      - "result.dependency_graph != ''"
    retries: 2

  design_modules:
    mode: infer
    intent: >
      Propose module names and responsibilities based on the analysis.
      Each module should have a single clear responsibility.
      The original file should re-export everything for backwards compatibility.
    input:
      analysis: {type: string}
    output: ModuleDesign
    ensure:
      - "result.modules != ''"
      - "result.responsibilities != ''"
    retries: 2

  plan_extraction_order:
    mode: infer
    intent: >
      Order the module extractions so that at every intermediate step,
      all imports resolve. A module can only be extracted after all modules
      it imports have already been extracted. No step should leave the
      codebase in a state where an import references a file that doesn't exist yet.
    input:
      module_design: {type: string}
      dependency_graph: {type: string}
    output: ExtractionSequence
    ensure:
      - "result.ordered_steps != ''"
      - "result.rationale != ''"
    retries: 3

  extract_module:
    mode: infer
    intent: >
      Extract the specified module. After this extraction and nothing else,
      all existing tests must pass. Update the original file to re-export
      anything that was moved. Do not change any behavior.
    input:
      module_name: {type: string}
      extraction_order: {type: string}
      file_content: {type: string}
    output: ExtractionResult
    ensure:
      - "result.files_created != ''"
      - "result.test_status == 'passing'"
    retries: 3

flows:
  split_file:
    input:
      file_content: {type: string}
    output: ExtractionResult
    steps:
      - id: s1
        function: analyze_file
        inputs:
          file_content: "$.input.file_content"
      - id: s2
        function: design_modules
        inputs:
          analysis: "$.steps.s1.output.logical_groups"
        depends_on: [s1]
      - id: s3
        function: plan_extraction_order
        inputs:
          module_design: "$.steps.s2.output.modules"
          dependency_graph: "$.steps.s1.output.dependency_graph"
        depends_on: [s2]
      - id: s4
        function: extract_module
        inputs:
          module_name: "$.steps.s2.output.modules"
          extraction_order: "$.steps.s3.output.ordered_steps"
          file_content: "$.input.file_content"
        depends_on: [s3]
```

## Note on Multiple Extractions

For files splitting into 3+ modules, add one `extract_module` step per module, each with `depends_on` pointing to the previous extraction. The `module_name` input should reference a specific step's output field identifying that module.

## Narration Pattern

```
Reading the file...
Designing module structure: [list modules briefly]
Planning extraction order...
Extracting [module 1]... tests passing.
Extracting [module 2]... tests passing.
...

Done. [N] modules created. Original file re-exports everything — no callers need to change.
```

## Memory

**Before writing the spec:** Read the project's `MEMORY.md` (at `.claude/memory/MEMORY.md` or the root). Find any lines tagged `[stratum-refactor]`. These encode known dependency constraints, module patterns, or import conventions that previous refactor sessions discovered.

**After each extraction:** If a step needed retries because of an unexpected dependency or import constraint, append to `MEMORY.md`:

```
[stratum-refactor] executor imports from decorators at module level — extract decorators before executor
[stratum-refactor] all internal modules import from stratum.__init__ not direct paths — update __init__ first
[stratum-refactor] circular import between flow_scope and decorators — flow_scope must not import decorators
```

These entries directly improve future extraction order planning — the `plan_extraction_order` step can use them to avoid the same sequencing mistakes.
