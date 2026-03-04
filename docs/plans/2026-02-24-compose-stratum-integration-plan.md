# Compose + Stratum Integration Plan

**Date:** 2026-02-24
**Status:** PLANNED
**Roadmap:** T2-F1 → T2-F4 (see ROADMAP.md § Compose Integration)

## Related Documents

- Forward: none yet
- Backward: ROADMAP.md

---

## Problem

The `compose` skill orchestrates a feature lifecycle (research → design → blueprint → implementation) as a flat prompt sequence. There is no postcondition enforcement between phases, no audit trail, and no way to know which phase failed or why.

Stratum already solves this for arbitrary multi-step tasks. The goal is to make `compose` a first-class Stratum flow so that every phase has enforced exit conditions and produces a trace.

---

## Target State

`compose` emits a `.stratum.yaml` spec and drives itself through the `stratum_plan` / `stratum_step_done` loop. Claude Code remains the executor for every step (file reads, writes, edits, shell commands). Stratum enforces that each phase produced a verifiable artifact before advancing.

Example flow:

```yaml
flow: compose_feature
inputs:
  description: { type: string }

steps:
  - id: research
    intent: "Read the codebase and surface relevant patterns for the feature."
    output_schema:
      type: object
      required: [findings]
      properties:
        findings: { type: array, items: { type: string } }
        relevant_files: { type: array, items: { type: string } }
    ensures:
      - "len(result.findings) > 0"

  - id: write_design
    depends_on: [research]
    intent: "Write a design doc to docs/plans/."
    output_schema:
      type: object
      required: [path]
      properties:
        path: { type: string }
        word_count: { type: integer }
    ensures:
      - "file_exists(result.path)"
      - "result.word_count > 200"

  - id: write_blueprint
    depends_on: [write_design]
    intent: "Write an implementation blueprint with file paths annotated (new) or (existing)."
    output_schema:
      type: object
      required: [path]
      properties:
        path: { type: string }
    ensures:
      - "file_exists(result.path)"

  - id: implement
    depends_on: [write_blueprint]
    intent: "Implement the feature per the blueprint."
    output_schema:
      type: object
      required: [files_changed, tests_pass]
      properties:
        files_changed: { type: array, items: { type: string } }
        tests_pass: { type: boolean }
    ensures:
      - "result.tests_pass == True"
      - "len(result.files_changed) > 0"
```

---

## Phases

### Phase 1 — Convention (T2-F1)

**No code changes required.**

Establish the result schema convention for compose steps. Claude Code must return a structured dict from every `stratum_step_done` call, not just implicit file changes. Document the expected shapes for each compose step type (research, design, blueprint, implement).

Acceptance criteria:
- [ ] Convention documented in this plan (see Target State above)
- [ ] Compose skill updated to include result shape instructions in step prompts

---

### Phase 2 — File-aware builtins in `ensure` eval (T2-F2 → T2-15)

**Change: `stratum-mcp/src/stratum_mcp/executor.py`** (existing)

Extend `compile_ensure` to expose safe file-system builtins in the eval context.

```python
import os

_ENSURE_BUILTINS = {
    "file_exists": lambda p: os.path.isfile(p),
    "file_contains": lambda p, s: os.path.isfile(p) and s in open(p).read(),
    "len": len,
    "bool": bool,
    "int": int,
    "str": str,
}
```

`compile_ensure` currently passes `{"result": result}` as locals. Merge `_ENSURE_BUILTINS` into the eval globals instead of locals so they're available without `result.` prefix.

Acceptance criteria:
- [x] `file_exists(path)` available in `ensure` expressions
- [x] `file_contains(path, substring)` available in `ensure` expressions
- [x] Dunder-block still applies to all expressions
- [x] No external process execution exposed (no `subprocess`, `os.system`, etc.)
- [x] Existing ensure tests still pass
- [x] New invariant tests cover: `file_exists` true/false, `file_contains` true/false/missing

---

### Phase 3 — Step output contracts (T2-F3 → T2-16)

**Changes:**
- `stratum-mcp/src/stratum_mcp/spec.py` (existing) — add `output_schema` field to step dataclass
- `stratum-mcp/src/stratum_mcp/executor.py` (existing) — validate result against `output_schema` in `process_step_result`
- IR JSON Schema — add `output_schema` as optional object property on each step

When `output_schema` is present on a step and `stratum_step_done` is called, validate the result dict against the schema before evaluating `ensures`. If validation fails, return a step failure with a schema error message rather than a runtime `ensure` error.

Acceptance criteria:
- [x] `output_schema` is an optional field in the step IR dataclass
- [x] `process_step_result` validates result against `output_schema` when present
- [x] Schema mismatch returns `{"status": "schema_failed", "violations": [...]}`
- [x] `ensures` are only evaluated after schema validation passes
- [x] IR JSON Schema updated — `output_schema` valid but not required
- [x] New integration tests: conforms → passes; missing required field → schema_failed with retry; retries exhausted; schema checked before ensures

---

### Phase 4 — Compose skill emits `.stratum.yaml` (T2-F4 → T2-S10)

**Change: compose skill file** (existing)

Rewrite the `compose` skill so that instead of a flat prompt sequence, it:

1. Generates a `.stratum.yaml` spec for the feature (never shown to user)
2. Calls `stratum_plan(spec, "compose_feature", {description: <feature>})` to get the first step
3. Executes each step using Claude Code's own tools
4. Calls `stratum_step_done` with a structured result dict after each step
5. Calls `stratum_audit` at completion and includes the trace ID in the commit

The generated spec follows the template in the Target State section above, with `intent` strings tailored to the specific feature being built.

Acceptance criteria:
- [ ] Compose emits a `.stratum.yaml` (written to a temp path, not shown to user)
- [ ] Compose uses `stratum_plan` → `stratum_step_done` loop, not a flat prompt chain
- [ ] Each step result is a structured dict matching the step's `output_schema`
- [ ] `stratum_audit` trace ID appears in commit message
- [ ] If a step's `ensures` fail, compose retries the step silently before surfacing a failure
- [ ] Compose still produces the same user-visible artifacts (design doc, blueprint, implementation)

---

## Dependencies

```
T2-F1 (convention)
  └── T2-F2 (file builtins)        ← unblocks file_exists ensures
        └── T2-F3 (output contracts) ← unblocks schema enforcement
              └── T2-F4 (compose rewrite) ← depends on all prior phases
```

T2-F1 and T2-F2 can start immediately. T2-F3 requires T2-F2 to be merged and tested first. T2-F4 requires T2-F3.

---

## Out of Scope

- Shell/process execution in `ensure` (e.g., `tests_pass` via subprocess) — Claude Code reports `tests_pass` as a boolean in its result dict; Stratum trusts it
- Parallel compose phases — deferred to Phase 3 (Agent SDK)
- Compose-specific IR schema — reuses the standard Stratum IR; no new schema
