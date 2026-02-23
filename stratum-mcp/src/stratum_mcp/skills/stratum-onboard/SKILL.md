---
name: stratum-onboard
description: Read a codebase cold and write a project-specific MEMORY.md from scratch — architecture patterns, test conventions, module constraints, known fragile areas. Run once after setup on a new project.
---

# Stratum Onboard

Read an unfamiliar codebase and populate `MEMORY.md` with project-specific patterns that improve every future Stratum skill run.

## When to Use

- Right after `stratum-mcp setup` on an existing project
- When joining a new codebase and wanting Stratum skills to be immediately useful
- When `MEMORY.md` is empty or missing and you've already run several sessions

## Instructions

1. Do a broad directory scan before writing the spec — understand what's here
2. Write a `.stratum.yaml` spec internally — **never show it to the user**
3. Call `stratum_plan` with the spec, flow `"onboard_project"`, and directory listing + key file contents as input
4. Execute each step, calling `stratum_step_done` after each
5. Write conclusions to `MEMORY.md` at `.claude/memory/MEMORY.md` (create if missing)
6. Narrate in plain English — what you're mapping, what patterns you're finding

**What to read:**
- Directory structure (top 2 levels)
- `pyproject.toml` / `package.json` / `Cargo.toml` — dependencies and entry points
- Main source files (sample 3–5, prefer files that are imported by many others)
- Test files (sample 2–3 — fixture patterns, test style)
- CI config (`.github/workflows/`, `.circleci/`) — Python version, OS, test command
- Any existing `CLAUDE.md` or `MEMORY.md`

**Do not read everything.** The goal is patterns, not exhaustive coverage.

## Spec Template

```yaml
version: "0.1"
contracts:
  ArchitectureMap:
    module_structure: {type: string}
    entry_points: {type: string}
    key_dependencies: {type: string}
  TestConventions:
    framework: {type: string}
    fixture_pattern: {type: string}
    real_vs_mock: {type: string}
    ci_environment: {type: string}
  CodePatterns:
    error_handling: {type: string}
    naming_conventions: {type: string}
    fragile_areas: {type: string}
    import_style: {type: string}
  MemoryEntries:
    stratum_feature: {type: string}
    stratum_debug: {type: string}
    stratum_refactor: {type: string}
    stratum_review: {type: string}
    stratum_test: {type: string}

functions:
  map_architecture:
    mode: infer
    intent: >
      Read the directory structure and key source files. Identify: how the
      codebase is organized (packages, modules, layers), what the entry points
      are, and which dependencies are central. Note anything that would affect
      how a feature should be structured or where new code should go.
    input:
      directory_listing: {type: string}
      source_samples: {type: string}
    output: ArchitectureMap
    ensure:
      - "result.module_structure != ''"
      - "result.entry_points != ''"
    retries: 2

  read_test_conventions:
    mode: infer
    intent: >
      Read the test files and CI config. Identify: test framework (pytest/jest/etc),
      fixture patterns (factory_boy, fixtures, builders), whether tests use real
      resources or mocks, and what the CI environment looks like (OS, Python version,
      any timing-sensitive setup). These patterns directly affect how tests should
      be written for this project.
    input:
      test_samples: {type: string}
      ci_config: {type: string}
    output: TestConventions
    ensure:
      - "result.framework != ''"
      - "result.fixture_pattern != ''"
    retries: 2

  extract_code_patterns:
    mode: infer
    intent: >
      From the source samples, identify: how errors are handled (exceptions vs
      result types, custom exception classes), naming conventions (snake_case,
      class prefixes, module naming), any known fragile areas (files with many
      TODOs, complex async code, shared mutable state), and import style (relative
      vs absolute, re-exports from __init__). These patterns affect review,
      refactor, and debug work.
    input:
      source_samples: {type: string}
      architecture: {type: string}
    output: CodePatterns
    ensure:
      - "result.error_handling != ''"
      - "result.naming_conventions != ''"
    retries: 2

  write_memory:
    mode: infer
    intent: >
      Synthesize the architecture, test conventions, and code patterns into
      tagged MEMORY.md entries. Each entry must be a specific, actionable
      one-liner that would change how a Stratum skill writes its spec for
      this project. Tag each entry with the skill it applies to.
      Skip generic observations true of all codebases.
    input:
      architecture: {type: string}
      test_conventions: {type: string}
      code_patterns: {type: string}
    output: MemoryEntries
    ensure:
      - "result.stratum_feature != '' or result.stratum_debug != '' or result.stratum_test != ''"
    retries: 2

flows:
  onboard_project:
    input:
      directory_listing: {type: string}
      source_samples: {type: string}
      test_samples: {type: string}
      ci_config: {type: string}
    output: MemoryEntries
    steps:
      - id: s1
        function: map_architecture
        inputs:
          directory_listing: "$.input.directory_listing"
          source_samples: "$.input.source_samples"
      - id: s2
        function: read_test_conventions
        inputs:
          test_samples: "$.input.test_samples"
          ci_config: "$.input.ci_config"
        depends_on: [s1]
      - id: s3
        function: extract_code_patterns
        inputs:
          source_samples: "$.input.source_samples"
          architecture: "$.steps.s1.output.module_structure"
        depends_on: [s1]
      - id: s4
        function: write_memory
        inputs:
          architecture: "$.steps.s1.output.module_structure"
          test_conventions: "$.steps.s2.output.fixture_pattern"
          code_patterns: "$.steps.s3.output.error_handling"
        depends_on: [s2, s3]
```

## Writing MEMORY.md

After the flow completes, write the entries to `.claude/memory/MEMORY.md` (create the directory and file if missing). Format:

```markdown
<!-- stratum-onboard: <date> -->
[stratum-feature] <entry>
[stratum-feature] <entry>
[stratum-debug] <entry>
[stratum-debug] <entry>
[stratum-refactor] <entry>
[stratum-review] <entry>
[stratum-test] <entry>
[stratum-test] <entry>
```

Only write entries that would change what a skill does on this project. Aim for 8–15 entries total.

## Narration Pattern

```
Scanning the codebase...
Mapping architecture: [brief description — e.g. "FastAPI app, 3 layers, src layout"]
Reading tests: [framework, fixture style]
Extracting patterns: [2-3 key findings]

Writing [N] entries to MEMORY.md.

Key findings:
- [most important finding in plain English]
- [second finding]
- [third finding]
```
