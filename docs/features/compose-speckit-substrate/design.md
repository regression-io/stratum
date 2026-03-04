# Compose + Stratum + spec-kit Substrate

**Date:** 2026-02-25
**Status:** DESIGN — architecture settled, implementation not started
**Roadmap:** T3-1 through T3-9 (`stratum/ROADMAP.md`)
**Related:** `docs/plans/2026-02-24-compose-stratum-integration-plan.md`, `T2-F4/design.md`

---

## Problem

The current compose+stratum integration (T2-F4, COMPLETE) is **surface-level**: the compose skill generates a `.stratum.yaml` internally and runs the plan/step-done loop, but:

1. Compose's artifact format (design.md, blueprint.md, etc.) is its own convention — not interoperable with other tools or agent environments
2. The compose web app has zero awareness of Stratum — it cannot show live step state, blockers, or audit traces
3. Each compose phase re-invents what spec-kit already standardizes: requirements, plan, task decomposition

The result is three good tools with no clean boundary between them.

---

## The Stack

These three tools compose without overlap when assigned their natural layer:

```
┌─────────────────────────────────────────────────┐
│  compose (orchestration + visualization layer)    │
│  coder-compose web app: Vision Surface, AgentStream│
│  drives the stack, shows live state             │
├─────────────────────────────────────────────────┤
│  stratum (execution layer)                      │
│  .stratum.yaml IR, postcondition enforcement,   │
│  step-by-step flow control, audit traces        │
├─────────────────────────────────────────────────┤
│  spec-kit (specification layer)                 │
│  spec.md (WHAT/WHY), plan.md (HOW),             │
│  tasks/ (self-contained work units)             │
└─────────────────────────────────────────────────┘
```

**Key insight:** A spec-kit task and a stratum step are the same concept. A task is a self-contained work unit with acceptance criteria. A step is a self-contained work unit with `ensure` postconditions. The bridge between them is a compiler.

---

## Components

### 1. Task→Step Compiler (T3-2)

Converts `tasks/*.md` into a `.stratum.yaml` flow.

**Input:** A directory of spec-kit task files. Each task has:
- Title and description
- Acceptance criteria (checkbox list)
- Optional parallel markers (`[P]`)
- Optional file path annotations

**Output:** A `.stratum.yaml` flow where each task becomes a step:
- Task description → step `intent`
- Acceptance criteria → `ensure` expressions (compiled from natural language where possible; file path checks → `file_exists()`; test pass criteria → convention)
- Parallel markers → tasks with the same marker get no `depends_on` between them
- Sequential tasks → `depends_on` the prior step

**Compilation rules for `ensure` expressions:**

| Acceptance criterion pattern | `ensure` expression |
|---|---|
| `file X exists` | `file_exists("X")` |
| `file X contains Y` | `file_contains("X", "Y")` |
| `tests pass` | `result.tests_pass == True` |
| `no lint errors` | `result.lint_clean == True` |
| Freeform text | Kept as a comment; Claude evaluates judgment criterion |

**Output contract per step:**
```yaml
output_schema:
  type: object
  properties:
    done: {type: boolean}
    tests_pass: {type: boolean}   # when applicable
    lint_clean: {type: boolean}   # when applicable
    artifact_path: {type: string} # when task produces a file
  required: [done]
```

### 2. `/stratum-speckit` Bridge Skill (T3-3)

A new stratum skill that drives the full spec-kit lifecycle through stratum:

1. Run spec-kit phases: generate `spec.md` → `plan.md` → `tasks/`
2. Gate human review at each artifact boundary
3. Compile `tasks/` → `.stratum.yaml` via the task→step compiler
4. Drive execution via `stratum_plan` → `stratum_step_done` loop
5. Call `stratum_audit` at completion

This skill is the glue between the specification layer and the execution layer. The compose skill calls it rather than managing spec-kit phases itself.

### 3. Compose Skill Refactor (T3-4, T3-5, T3-6)

**Before:** Compose skill produces its own artifacts (design.md, blueprint.md) and drives a custom phase chain.

**After:** Compose skill's design phases produce spec-kit canonical artifacts:
- Phase 1 (research) → feeds into `spec.md`
- Phase 2 (requirements/PRD) → `spec.md`
- Phase 3 (architecture) → `plan.md`
- Phase 4 (blueprint/tasks) → `tasks/` directory

All artifacts land in `.specify/<feature-name>/` following spec-kit conventions. The compose skill then calls `/stratum-speckit` (or its internal equivalent) to compile and execute.

**What stays the same:**
- Gate protocol (human approves design before implementation)
- Explorer, architect, reviewer agents (compose-explorer, compose-architect, compose-reviewer)
- Stratum execution loop (already in place from T2-F4)
- Audit trace in commit message

**What changes:**
- Artifact format and location (→ spec-kit conventions)
- Phase-to-artifact mapping (above)
- Task decomposition uses spec-kit `/tasks` command pattern

### 4. Vision Surface Integration (T3-7, T3-8, T3-9)

**Seed from spec-kit (T3-7):** On load or file-watch event, coder-compose reads `.specify/` and populates Vision Surface work items from tasks. Each `tasks/*.md` file becomes a work item. Hierarchy follows spec-kit folder structure.

**Live stratum state (T3-8):** The compose web app connects to a Stratum state endpoint (new addition to stratum-mcp server — a `/state` SSE or polling endpoint). Vision Surface reflects:
- Current step → item status `in_progress`
- `ensure` violation → item status `blocked` with violation message
- Step complete → item status `complete`
- Flow complete → feature status `complete`

**Audit trace (T3-9):** `stratum_audit` trace is surfaced in the item's evidence panel (already planned in the Vision Surface spec as "Evidence: commits, test results, files changed"). Step records → evidence entries.

---

## Data Flow (end-to-end)

```
User runs /compose feature-name
    │
    ▼
compose-explorer reads codebase
    │
    ▼
compose skill generates spec.md → gate → approved
    │
    ▼
compose skill generates plan.md → gate → approved
    │
    ▼
compose skill generates tasks/*.md → gate → approved
    │
    ▼
task→step compiler produces .stratum.yaml
    │
    ▼
stratum_plan → returns first step
    │
    ▼ (loop)
Claude executes step (edit files, run tests, etc.)
stratum_step_done → validates schema + ensure expressions
    ├── ensure_failed → fix and retry
    └── ok → next step
    │
    ▼
stratum_audit → trace → commit message + Vision Surface evidence
    │
    ▼
Vision Surface shows: all tasks complete, audit trace, session log
```

---

## Open Questions

**Q1: Task→step compiler location.** Does the compiler live in stratum (as a new MCP tool `stratum_compile_speckit`), or does the compose skill do the conversion inline? Recommendation: MCP tool — keeps the compiler testable, versioned, and usable outside compose.

**Q2: Vision Surface↔stratum bridge.** Polling vs. SSE. Stratum-mcp is currently stateless between tool calls. Options:
- Add a `/state` polling endpoint to stratum-mcp (lightweight, works with existing architecture)
- Keep Vision Surface state in the compose vision-server, updated via a stratum post-step hook
- Recommendation: polling endpoint on stratum-mcp; compose polls it alongside existing WebSocket

**Q3: Compose skill boundary with spec-kit CLI.** Does the compose skill shell out to the `specify` CLI, or does it implement the artifact format inline? Recommendation: implement the format inline (Claude generates the files directly following spec-kit conventions) — avoids a hard runtime dependency on spec-kit being installed.

**Q4: `.specify/` vs. existing feature folder convention.** Compose currently uses `docs/features/<name>/`. Migration path: for new features, create under `.specify/`. Existing features stay as-is. No forced migration.

---

## Phasing

**Phase 1 (bridge):** Build the task→step compiler + `/stratum-speckit` skill. This can be built and validated independently of the compose skill refactor. Delivers value immediately — any spec-kit project can use stratum as its execution runtime.

**Phase 2 (compose skill):** Refactor the compose skill to produce spec-kit artifacts. Gate protocol and agent structure unchanged. Implementation phases now go through stratum via the bridge skill.

**Phase 3 (web app):** Wire Vision Surface to spec-kit file-watch and stratum state. This is the highest-effort phase and has the most UI dependencies — sequence it after Phase 1 and 2 are validated.
