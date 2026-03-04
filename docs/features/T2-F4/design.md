# T2-F4: Compose + Stratum Integration

**Date:** 2026-02-25
**Status:** Phase 1 — Design

## Problem

The `compose` skill orchestrates a feature lifecycle as a flat prompt sequence with no postcondition enforcement between phases. If the design phase produces a weak doc, or the blueprint misses files, nothing catches it before implementation starts.

## Solution

Add a `## Stratum Integration` section to `~/.claude/skills/compose/SKILL.md`. This adds a Stratum flow as a tracking layer around the existing compose phases, with `ensure` postconditions enforcing that each phase produced a verifiable artifact before advancing.

## File Changed

`~/.claude/skills/compose/SKILL.md` (existing, installed at `/Users/ruze/.claude/skills/compose/SKILL.md`)

## Design

### Stratum Step → Compose Phase Mapping

| Stratum Step | Compose Phases Covered |
|---|---|
| `research` | Phase 1 exploration (compose-explorer agents) |
| `write_design` | Phase 1 design doc + optional Phase 2 PRD + optional Phase 3 Architecture |
| `write_blueprint` | Phase 4 blueprint + Phase 5 verification |
| `implement` | Phase 7 execute + E2E + review loops + coverage sweep |

Phases 6 (Plan), 8 (Report), 9 (Docs), 10 (Ship) remain as sub-activities within their adjacent steps. Stratum doesn't wrap them because they don't produce a verifiable file artifact that `ensure` can check.

### Gate → stratum_step_done Mapping

Gates happen inside Stratum steps, not between them:

- `research`: no human gate — `stratum_step_done` called immediately after exploration
- `write_design`: `stratum_step_done` called **after** human approves at Phase 1 gate
- `write_blueprint`: `stratum_step_done` called **after** human approves at Phase 5 gate
- `implement`: `stratum_step_done` called **after** Phase 7 (including E2E + ralph loops) completes

### .stratum.yaml Template

```yaml
version: "0.1"
contracts:
  ResearchResult:
    findings: {type: array}
    relevant_files: {type: array}
  DesignResult:
    path: {type: string}
    word_count: {type: integer}
  BlueprintResult:
    path: {type: string}
  ImplementResult:
    files_changed: {type: array}
    tests_pass: {type: boolean}

functions:
  research:
    mode: compute
    intent: "Explore the codebase with compose-explorer agents and surface patterns relevant to the feature."
    input: {description: {type: string}}
    output: ResearchResult
    ensure:
      - "len(result.findings) > 0"
    retries: 2

  write_design:
    mode: compute
    intent: "Run Phase 1 (and optional Phases 2-3) — explore, gate, write design.md."
    input: {description: {type: string}}
    output: DesignResult
    ensure:
      - "file_exists(result.path)"
      - "result.word_count > 200"
    retries: 2

  write_blueprint:
    mode: compute
    intent: "Run Phases 4-5 — blueprint, verification. Gate before returning."
    input: {description: {type: string}}
    output: BlueprintResult
    ensure:
      - "file_exists(result.path)"
    retries: 2

  implement:
    mode: compute
    intent: "Run Phase 7 — TDD, E2E, review ralph loop, coverage sweep."
    input: {description: {type: string}}
    output: ImplementResult
    ensure:
      - "result.tests_pass == True"
      - "len(result.files_changed) > 0"
    retries: 2

flows:
  compose_feature:
    input: {description: {type: string}}
    output: ImplementResult
    steps:
      - id: research
        function: research
        inputs: {description: "$.input.description"}
        output_schema:
          type: object
          required: [findings]
          properties:
            findings: {type: array, items: {type: string}}
            relevant_files: {type: array, items: {type: string}}

      - id: write_design
        function: write_design
        inputs: {description: "$.input.description"}
        depends_on: [research]
        output_schema:
          type: object
          required: [path, word_count]
          properties:
            path: {type: string}
            word_count: {type: integer}

      - id: write_blueprint
        function: write_blueprint
        inputs: {description: "$.input.description"}
        depends_on: [write_design]
        output_schema:
          type: object
          required: [path]
          properties:
            path: {type: string}

      - id: implement
        function: implement
        inputs: {description: "$.input.description"}
        depends_on: [write_blueprint]
        output_schema:
          type: object
          required: [files_changed, tests_pass]
          properties:
            files_changed: {type: array, items: {type: string}}
            tests_pass: {type: boolean}
```

### What Gets Added to SKILL.md

A `## Stratum Integration` section (inserted just before `## Entry: Scan First, Then Decide`), containing:

1. Overview — generate spec internally, never show to user
2. The full `.stratum.yaml` template above
3. Execution protocol: when to call `stratum_plan`, `stratum_step_done`, `stratum_audit`
4. Result dict shapes for each step

Phase 10 (Ship) gets one new line: call `stratum_audit` and include trace in commit.

## Assumptions

- Stratum MCP server is configured and available (`stratum_plan`, `stratum_step_done`, `stratum_audit` accessible)
- `file_exists` ensure builtin is available (T2-F2, already complete)
- `output_schema` validation is available (T2-F3, already complete)
- If Stratum is not available, compose falls back to the existing flat prompt chain (graceful degradation — not enforced by code, just by convention)
