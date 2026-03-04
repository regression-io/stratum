---
name: stratum-build
description: Use when starting a non-trivial feature that will span multiple files or phases - orchestrates the full lifecycle from idea through spec, plan, tasks, and implementation using existing skills and agents at each stage.
---

# Stratum Build

## Overview

Orchestrates the full feature development lifecycle through the spec-kit layer: spec → plan → tasks → execute. Uses the three-layer stack: spec-kit for specification artifacts, stratum for execution control, stratum-build for orchestration. Each layer does exactly one thing.

## When to Use

- New feature spanning 3+ files or 2+ phases
- Feature touching multiple components (core lib + service + UI)
- Any work that needs a design spec before implementation

**Skip this for:** single-file changes, bug fixes, hotfixes, refactors with obvious approach.

## Partial Execution: `--through <phase>`

By default, `/stratum-build` runs the full lifecycle. Use `--through` to stop after a specific phase:

```
/stratum-build FEAT-1 --through spec       # Stop after Phase 2 gate
/stratum-build FEAT-1 --through plan       # Stop after Phase 3 gate
/stratum-build FEAT-1 --through tasks      # Stop after Phase 4 gate
/stratum-build FEAT-1 --through execute    # Stop after Phase 5 gate (includes review + sweep)
/stratum-build FEAT-1 --through report     # Stop after Phase 6 gate
/stratum-build FEAT-1 --through docs       # Stop after Phase 7 gate
```

When `--through` is active:
1. Run phases normally up to and including the target phase
2. After the target phase's gate is approved, write `status.md` to the feature folder
3. Commit all artifacts and exit — do NOT propose the next phase
4. On next `/stratum-build` invocation, `status.md` is read during entry scan

## Feature Folder

Every feature gets a folder at `.specify/<feature-name>/`. The feature name is a short kebab-case slug (e.g., `auth-middleware`, `payment-retry`, `bulk-export`). The human-readable title lives in `spec.md`, not the folder name.

```
.specify/<feature-name>/
  spec.md                # WHAT and WHY — requirements and goals
  plan.md                # HOW — architecture, approach, file-level scope
  tasks/                 # Self-contained work units with acceptance criteria
    01-<slug>.md
    02a-<slug>.md        # [P] parallel tasks
    02b-<slug>.md        # [P] parallel tasks
    03-<slug>.md
  .stratum.yaml          # Compiled from tasks/ — never shown to user
  report.md              # Implementation report (optional)
  killed.md              # Present only if feature was abandoned
  sessions/              # Session transcripts
```

The absence of a file is the documentation that the step was skipped. Create the folder at Phase 1 start.

## Gate Protocol

Every phase transition is a gate. Three outcomes:
- **Approve** — artifact accepted, proceed
- **Revise** — loop back, improve, re-gate
- **Kill** — write `killed.md` with reason and phase, folder persists for provenance

## Lifecycle

```
Phase 1:  Explore ──────────────────────────────── (no gate — feeds into spec)
Phase 2:  Spec ────── 1x doc review ──────────────→ Gate
Phase 3:  Plan ────── 1x doc review ──────────────→ Gate
Phase 4:  Tasks ───── 1x doc review ──────────────→ Gate
Phase 5:  Execute + E2E + Review + Sweep ──────────→ Gate
            ├─ Step 1: Compile tasks → .stratum.yaml
            ├─ Step 2: Drive stratum_plan loop (TDD per step)
            ├─ Step 3: E2E smoke test (Playwright)
            ├─ Step 4: Review ralph loop (till clean)
            └─ Step 5: Coverage ralph loop (till clean)
Phase 6:  Report (skippable) ── 1x doc review ────→ Gate
Phase 7:  Update Docs ─── 1x doc review ──────────→ Gate
Phase 8:  Review & Ship ───────────────────────────→ Done
```

Phase 5 is NOT done until all five steps complete. Phase 5 steps 3-5 self-terminate on clean input.

## Phases

### Phase 1: Explore

**Agent:** `forge-explorer` (2-3 instances in parallel for codebase understanding)

- Create `.specify/<feature-name>/` folder
- Launch 2-3 `forge-explorer` agents in parallel, each targeting a different aspect:
  - "Find features similar to [feature] and trace their implementation"
  - "Map the architecture and abstractions for [area]"
  - "Analyze the current implementation of [related feature]"
- Understand the idea through one-question-at-a-time dialogue
- Read all essential files identified by explorers

**No gate.** Exploration feeds directly into Phase 2.

### Phase 2: Write Spec

Write `.specify/<feature-name>/spec.md` capturing:

- **Problem statement** — what is broken or missing and why it matters
- **Goals** — what success looks like (measurable where possible)
- **Non-goals** — what is explicitly out of scope
- **Requirements** — MUST/SHOULD/MAY
- **Constraints** — technical, compatibility, or scope limits
- **Open questions** — anything that would materially change the design if answered

Target 300-500 words — enough to be useful, not so long it's ignored.

**Gate checkpoint:** Before proceeding, verify: "Does this spec depend on unproven technical assumptions? If yes, list them." Spikes go into roadmap tasks; results come back into spec under "Assumptions & Validations."

**Gate:** User approves spec. All open questions resolved or deferred with rationale.

**Skip when:** `spec.md` already exists in the feature folder. Review for completeness first.

### Phase 3: Write Plan

**Agent:** `forge-architect` (2-3 instances with competing mandates)

Launch 2-3 `forge-architect` agents in parallel:
- **Minimal changes** — smallest possible change, maximum reuse
- **Clean architecture** — maintainability first, clear boundaries
- **Pragmatic balance** — 80/20 approach

Review proposals, form your own opinion, present trade-offs to user. Write the chosen approach to `.specify/<feature-name>/plan.md`.

Plan sections:
- **Architecture** — what components change and why
- **Key decisions** — alternatives considered and rejected
- **File-level scope** — which files get created, modified, or deleted (with exact paths)
- **Risk areas** — what could go wrong and mitigation
- **Dependencies** — external packages or internal modules required

**Check for overlapping features:** Scan other `.specify/*/tasks/` directories for shared file references. Flag any overlap before proceeding.

**Gate:** User approves plan. Component boundaries and file-level scope are clear enough for task decomposition.

**Skip when:** `plan.md` already exists. Verify it against current code state before accepting.

### Phase 4: Write Tasks

Decompose the plan into `.specify/<feature-name>/tasks/*.md` files.

Task file format:
```markdown
# Task: [P] Title  ← [P] only if parallel with sibling tasks

One paragraph description of what this task accomplishes.
Reference specific files from plan.md.

## Acceptance Criteria

- [ ] file path/to/expected/file.ext exists
- [ ] file path/to/file.ext contains expected_symbol_or_string
- [ ] tests pass
- [ ] no lint errors
- [ ] Freeform criterion Claude evaluates with judgment
```

Naming convention: `01-slug.md`, `02a-slug.md`, `02b-slug.md`, `03-slug.md`.

Rules:
- Tasks must be self-contained — each should make sense without reading others
- File-check criteria are preferred — they are machine-verifiable
- Mark parallel tasks with `[P]` only when they truly have no dependencies between them
- Keep tasks small: 1-4 acceptance criteria each
- Sequential order must be causal
- Every task that changes code should have at least one `file_exists` or `file_contains` criterion

**Gate:** User reviews the task list. Count and order are reasonable. Criteria are specific enough to be verifiable.

**Skip when:** `tasks/` already exists and contains `.md` files. Review for completeness.

### Phase 5: Execute

**Step 1: Compile tasks → .stratum.yaml**

Call `stratum_compile_speckit`:
- `tasks_dir` = `.specify/<feature-name>/tasks`
- `flow_name` = `"tasks"` (default)

On success, write `.specify/<feature-name>/.stratum.yaml` for provenance (never show it to the user).

If `stratum_compile_speckit` returns an error, fix the tasks/ files first. Common causes: step ID collision (rename a file), empty tasks directory, malformed task file.

**Step 2: Drive stratum_plan loop**

Call `stratum_plan(yaml, "tasks", {project_context: "<feature description>"})` → first step.

For each step:
- Execute using your tools: edit files, run commands, read/write as needed
- **Apply TDD:** write the test first (watch it fail), then implement (watch it pass)
- Call `stratum_step_done(flow_id, step_id, result)` with the actual result dict
- On `schema_failed` or `ensure_failed`: fix the issue and retry the same step
- On `complete`: call `stratum_audit(flow_id)` — save the trace for the commit message

When a step's `output_schema` includes `tests_pass: boolean` — run the tests, report `true` only if they actually pass. Same for `lint_clean`.

Use `stratum_commit` before any risky step. Use `stratum_revert` if a step fails ensure after retries.

**Step 3: E2E smoke test**

When the feature involves UI (frontend components, layout changes, cross-service connections):
1. Start the dev server(s) for affected projects
2. Run `npx playwright test` headlessly for the affected project
3. If tests fail → fix before entering the review loop

Skip for backend-only changes with no UI surface.

**Step 4: Review ralph loop**

**Agent:** `forge-reviewer` (confidence-scored review, only report findings >= 80)

```
/ralph-loop "Launch forge-reviewer agent to review implementation against
.specify/<feature-name>/plan.md and .specify/<feature-name>/tasks/.
Fix all issues with confidence >= 80.
Output <promise>REVIEW CLEAN</promise> when no actionable findings remain."
--completion-promise "REVIEW CLEAN" --max-iterations 10
```

Use `superpowers:receiving-code-review` to process feedback — verify technically before implementing, don't blindly agree. If review identifies large files, invoke `refactor` to split them.

**Step 5: Coverage & integration sweep ralph loop**

```
/ralph-loop "Write and run tests for the implementation in .specify/<feature-name>/plan.md.
Focus on edge cases, error paths, and cross-component integration.
Fix failing tests. Output <promise>TESTS PASSING</promise> when all tests pass."
--completion-promise "TESTS PASSING" --max-iterations 15
```

**Gate:** All five steps complete. Tests pass, lint passes, review clean, coverage sweep clean.

### Phase 6: Implementation Report

Write `.specify/<feature-name>/report.md`:

1. **Summary** — One paragraph of what was built
2. **Delivered vs Planned** — Table comparing tasks to what was implemented
3. **Architecture Deviations** — Where implementation diverged from plan.md and why
4. **Key Implementation Decisions** — Decisions made during coding not in the original plan
5. **Test Coverage** — Coverage numbers, what's tested, known gaps with rationale
6. **Files Changed** — New/modified/deleted files grouped by component
7. **Known Issues & Tech Debt** — Deferred work, shortcuts, follow-up needed
8. **Stratum Audit** — Include the `stratum_audit` trace from Phase 5

**Gate:** Report is complete and honest.

**Skip when:** Feature had no `spec.md` or `plan.md` (too small to need a report).

### Phase 7: Update All Docs

Use `update-docs` skill. Update:
- `CHANGELOG.md` — entry for this feature
- `README.md` — if setup, usage, or capabilities changed
- `CLAUDE.md` — if new commands, conventions, or architecture changed
- Project-specific docs — as defined by the project

**Do NOT update** pre-implementation intent documents (spec.md, plan.md). They preserve what was planned.

**Gate:** All doc surfaces reviewed and updated. No stale references.

### Phase 8: Review & Ship

- Final review against spec.md and plan.md
- `superpowers:verification-before-completion` one final time
- Include `stratum_audit` trace in the commit description
- Present options: merge, PR, or cleanup

## Stratum Integration

Stratum Build uses two Stratum flows: a **build flow** that tracks the design phases, and a **task flow** compiled from `tasks/` that tracks implementation steps. The build flow wraps the task flow — the `execute` step in the build flow completes only after the compiled task flow is complete.

**Never mention `.stratum.yaml`, step IDs, `stratum_plan`, or flow IDs to the user.** Narrate in plain English.

### Build-Level Spec

Generate at invocation. The five-step structure is fixed.

```yaml
version: "0.1"
contracts:
  ExploreResult:
    findings: {type: array}
    relevant_files: {type: array}
  SpecResult:
    path: {type: string}
    word_count: {type: integer}
  PlanResult:
    path: {type: string}
  TasksResult:
    tasks_dir: {type: string}
    task_count: {type: string}
  ExecuteResult:
    files_changed: {type: array}
    tests_pass: {type: boolean}

functions:
  explore:
    mode: compute
    intent: "Explore the codebase with forge-explorer agents and surface patterns relevant to the feature."
    input: {description: {type: string}}
    output: ExploreResult
    ensure:
      - "len(result.findings) > 0"
    retries: 2

  write_spec:
    mode: compute
    intent: "Write .specify/{feature_name}/spec.md — problem statement, goals, non-goals, requirements, constraints, open questions."
    input: {description: {type: string}}
    output: SpecResult
    ensure:
      - "file_exists(result.path)"
      - "result.word_count > 200"
    retries: 2

  write_plan:
    mode: compute
    intent: "Write .specify/{feature_name}/plan.md — architecture, file-level scope, key decisions, risk areas."
    input: {description: {type: string}}
    output: PlanResult
    ensure:
      - "file_exists(result.path)"
    retries: 2

  write_tasks:
    mode: compute
    intent: "Decompose plan.md into .specify/{feature_name}/tasks/*.md — one file per implementation unit with acceptance criteria."
    input: {description: {type: string}}
    output: TasksResult
    ensure:
      - "result.tasks_dir != ''"
      - "int(result.task_count) >= 1"
    retries: 2

  execute:
    mode: compute
    intent: "Compile tasks/ → .stratum.yaml, drive the task execution loop, run E2E, review loop, coverage sweep."
    input: {description: {type: string}}
    output: ExecuteResult
    ensure:
      - "result.tests_pass == True"
      - "len(result.files_changed) > 0"
    retries: 2

flows:
  build_feature:
    input: {description: {type: string}}
    output: ExecuteResult
    steps:
      - id: explore
        function: explore
        inputs: {description: "$.input.description"}
        output_schema:
          type: object
          required: [findings]
          properties:
            findings: {type: array, items: {type: string}}
            relevant_files: {type: array, items: {type: string}}

      - id: write_spec
        function: write_spec
        inputs: {description: "$.input.description"}
        depends_on: [explore]
        output_schema:
          type: object
          required: [path, word_count]
          properties:
            path: {type: string}
            word_count: {type: integer}

      - id: write_plan
        function: write_plan
        inputs: {description: "$.input.description"}
        depends_on: [write_spec]
        output_schema:
          type: object
          required: [path]
          properties:
            path: {type: string}

      - id: write_tasks
        function: write_tasks
        inputs: {description: "$.input.description"}
        depends_on: [write_plan]
        output_schema:
          type: object
          required: [tasks_dir, task_count]
          properties:
            tasks_dir: {type: string}
            task_count: {type: string}

      - id: execute
        function: execute
        inputs: {description: "$.input.description"}
        depends_on: [write_tasks]
        output_schema:
          type: object
          required: [files_changed, tests_pass]
          properties:
            files_changed: {type: array, items: {type: string}}
            tests_pass: {type: boolean}
```

### Result Dict Shapes

```python
# explore
{"findings": ["pattern A", "pattern B"], "relevant_files": ["src/foo.py"]}

# write_spec
{"path": ".specify/auth-middleware/spec.md", "word_count": 420}

# write_plan
{"path": ".specify/auth-middleware/plan.md"}

# write_tasks
{"tasks_dir": ".specify/auth-middleware/tasks", "task_count": "5"}

# execute — after task flow completes and all loops clean
{"files_changed": ["src/middleware/auth.ts", "tests/test_auth.ts"], "tests_pass": True}
```

### Narration Pattern

```
Exploring the codebase...
Writing spec...

[show spec.md contents]
Spec is ready — review and approve to proceed.

Writing plan...
[competing architect proposals, present trade-offs]

[show plan.md contents]
Plan is ready — review and approve to proceed.

Decomposing into tasks...

Generated 5 tasks:
  01-setup.md — Initialize structure (2 criteria)
  02a-backend.md — [parallel] API routes (3 criteria)
  02b-frontend.md — [parallel] UI components (2 criteria)
  03-tests.md — Integration tests (2 criteria)
  04-docs.md — Update docs (1 criterion)

Tasks are ready — review and approve to proceed.

Implementing...
[task by task, TDD, E2E, review loop, coverage sweep]

Done. [summary + stratum_audit trace]
```

## Entry: Scan First, Then Decide

When `/stratum-build` is invoked, **always scan `.specify/<feature-name>/` first**:

1. Check if the folder exists. If not, start at Phase 1.
2. If it exists, read every file in it. Summarize what's covered and what's missing.
3. If `status.md` exists, read it — it tells you where the last session stopped. Delete it after reading.
4. Integrate existing content — don't redo work that's already there.
5. Propose the starting phase with rationale. The human approves.

| Folder State | Action |
|---|---|
| No folder or empty | Start at Phase 1 |
| `status.md` exists | Read for resume point, delete it, start there |
| `spec.md` exists | Review for completeness. Fill gaps, then gate. |
| `plan.md` exists | Review against current code state. If solid, move to Phase 4. |
| `tasks/` exists | Review tasks for quality. Compile and execute (Phase 5). |
| `tasks/` + code done | E2E, review, sweep (Phase 5 steps 3-5), then docs. |

**Phase 5 loops are never skipped.** They self-terminate on clean input.

## Cross-Cutting Agents & Skills

| Agent/Skill | When to Invoke |
|---|---|
| **`forge-explorer`** | Phase 1 (2-3 in parallel), Phase 3 (targeted research for plan accuracy) |
| **`forge-architect`** | Phase 3 (2-3 with competing mandates: minimal, clean, pragmatic) |
| **`forge-reviewer`** | Phase 5 step 4 (confidence-scored review, only report >= 80) |
| `superpowers:test-driven-development` | Phase 5 step 2 (inline TDD per task) |
| `superpowers:receiving-code-review` | Phase 5 step 4 (process review feedback) |
| `superpowers:dispatching-parallel-agents` | Phase 5 step 2 (when parallel tasks can run concurrently) |
| `superpowers:verification-before-completion` | Before claiming any task/phase done |
| `superpowers:systematic-debugging` | Any unexpected failure or bug |
| `interface-design:init` | Phase 5 step 2 — new UI components |
| `interface-design:critique` | Phase 5 step 2-3 — after building UI |
| `interface-design:audit` | Phase 5 step 3 — check UI against design system |
| `refactor` | Phase 5 step 4 — when review identifies large files |
| `update-docs` | Phase 7 dedicated pass |

## Memory

After completing a feature lifecycle, update project memory with:
- Architecture decisions made
- Patterns discovered during plan phase
- Corrections that apply broadly
- Task criteria patterns that worked well (file_contains patterns, test conventions)
