---
name: stratum-speckit
description: Drive the full spec-kit lifecycle through Stratum — generate spec.md → plan.md → tasks/, gate human review at each boundary, compile tasks into a .stratum.yaml flow, and execute it step-by-step. The bridge between the specification layer and the execution layer.
---

# Stratum Speckit

Drive the full spec-kit lifecycle for a feature: specify → plan → decompose → execute.

## When to Use

- Starting a non-trivial feature that needs design and task decomposition before implementation
- You already have a `tasks/` directory and want to execute it via Stratum
- When you want human review gates between design phases before implementation begins
- As the orchestration layer when forge skill hands off to execution

## Artifact Locations

All artifacts land in `.specify/{feature-name}/`:
- `.specify/{feature-name}/spec.md` — WHAT and WHY (requirements)
- `.specify/{feature-name}/plan.md` — HOW (architecture and approach)
- `.specify/{feature-name}/tasks/` — self-contained work units with acceptance criteria
- `.specify/{feature-name}/.stratum.yaml` — compiled IR (never shown to user)

## Phase 1 — Specify (generate spec.md)

**Goal:** Capture WHAT and WHY before touching architecture or implementation.

Write a `.stratum.yaml` spec internally. **Never show it to the user.**

```yaml
version: "0.1"
contracts:
  SpecResult:
    spec_path: {type: string}
    open_questions: {type: string}

functions:
  write_spec:
    mode: compute
    intent: >
      Read the existing codebase to understand current state, then write
      .specify/{feature_name}/spec.md capturing:
      - Problem statement: what is broken or missing and why it matters
      - Goals: what success looks like (measurable where possible)
      - Non-goals: what is explicitly out of scope
      - Constraints: technical, time, or compatibility limits
      - Open questions: anything that would materially change the design if answered
      Follow existing conventions in the project. Keep the spec concise.
    input:
      feature_name: {type: string}
      feature_description: {type: string}
    output: SpecResult
    ensure:
      - "file_exists(\".specify/\" + result.spec_path.split('/')[1] + \"/spec.md\") or file_exists(result.spec_path)"
      - "result.spec_path != ''"
    retries: 2

flows:
  specify:
    input:
      feature_name: {type: string}
      feature_description: {type: string}
    output: SpecResult
    steps:
      - id: s1
        function: write_spec
        inputs:
          feature_name: "$.input.feature_name"
          feature_description: "$.input.feature_description"
```

**After `stratum_step_done` returns complete:**

1. Show the user the contents of `spec.md`
2. Stop. Say: "Spec is ready — review it and tell me when you're satisfied to proceed to planning."
3. Wait for user approval before Phase 2.

## Phase 2 — Plan (generate plan.md)

**Goal:** Define HOW before implementation starts.

Write a new `.stratum.yaml` spec internally:

```yaml
version: "0.1"
contracts:
  PlanResult:
    plan_path: {type: string}
    phases: {type: string}

functions:
  write_plan:
    mode: compute
    intent: >
      Read the spec at .specify/{feature_name}/spec.md and write
      .specify/{feature_name}/plan.md capturing:
      - Architecture: what components change and why
      - Sequence: the order of changes and their dependencies
      - Key decisions: alternatives considered and rejected
      - Risk areas: what could go wrong and mitigation strategies
      - File-level scope: which files get created, modified, or deleted
      The plan should be detailed enough for a developer to implement
      without re-reading the spec.
    input:
      feature_name: {type: string}
      spec_path: {type: string}
    output: PlanResult
    ensure:
      - "result.plan_path != ''"
      - "result.phases != ''"
    retries: 2

flows:
  plan:
    input:
      feature_name: {type: string}
      spec_path: {type: string}
    output: PlanResult
    steps:
      - id: s1
        function: write_plan
        inputs:
          feature_name: "$.input.feature_name"
          spec_path: "$.input.spec_path"
```

**After complete:**

1. Show the user the contents of `plan.md`
2. Stop. Say: "Plan is ready — review it and tell me when you're ready to decompose into tasks."

## Phase 3 — Tasks (generate tasks/)

**Goal:** Decompose the plan into self-contained work units.

Write a new `.stratum.yaml` spec internally:

```yaml
version: "0.1"
contracts:
  TasksResult:
    tasks_dir: {type: string}
    task_count: {type: string}

functions:
  write_tasks:
    mode: compute
    intent: >
      Read .specify/{feature_name}/plan.md and decompose the work into
      task files under .specify/{feature_name}/tasks/.

      Each task file is named with a numeric prefix for ordering:
        01-descriptive-name.md
        02a-parallel-task.md    ← [P] marker for parallel tasks
        02b-parallel-task.md    ← [P] marker for parallel tasks
        03-next-sequential.md

      Each task file format:

        # Task: [P] Title  ← [P] only if parallel with sibling tasks

        One paragraph description of what this task accomplishes.

        ## Acceptance Criteria

        - [ ] file path/to/expected/file.ext exists
        - [ ] file path/to/file.ext contains expected_symbol
        - [ ] tests pass
        - [ ] no lint errors
        - [ ] Freeform criterion that Claude evaluates with judgment

      Rules:
      - Tasks must be self-contained — each should make sense without reading others
      - File-check criteria are preferred — they are machine-verifiable
      - Mark parallel tasks with [P] only when they truly have no dependencies between them
      - Keep tasks small: 1-4 acceptance criteria each
      - Sequential order must be causal: each task should build on what prior tasks produced
    input:
      feature_name: {type: string}
      plan_path: {type: string}
    output: TasksResult
    ensure:
      - "result.tasks_dir != ''"
      - "int(result.task_count) >= 1"
    retries: 2

flows:
  decompose:
    input:
      feature_name: {type: string}
      plan_path: {type: string}
    output: TasksResult
    steps:
      - id: s1
        function: write_tasks
        inputs:
          feature_name: "$.input.feature_name"
          plan_path: "$.input.plan_path"
```

**After complete:**

1. List the generated task files with their titles and criteria counts
2. Stop. Say: "Tasks are ready — review them and tell me when you're ready to execute."

## Phase 4 — Execute

**Goal:** Compile tasks and run the execution loop.

After user approval:

1. Call `stratum_compile_speckit` with `tasks_dir` = `.specify/{feature_name}/tasks/`
2. On success, call `stratum_plan` with the returned `yaml` and flow `"tasks"`, passing `project_context` = feature description
3. Execute each step using your tools (edit files, run tests, etc.)
4. Call `stratum_step_done` after each step with the actual result
5. On `schema_failed` or `ensure_failed`: fix the issue and retry the same step
6. On `complete`: call `stratum_audit` and include the trace

**What to report per step:**

- What you did (plain English — no step IDs, no YAML)
- Which files changed
- What the acceptance criteria showed

**When a step has `tests_pass` in the output schema:** run the tests and record the result. Report `tests_pass: true` only if they actually pass.

**When a step has `lint_clean` in the output schema:** run the linter and record the result.

## Shortcut — Execute Existing Tasks

If the user points you to an existing `tasks/` directory:

1. Skip Phases 1–3
2. Call `stratum_compile_speckit` on the directory
3. Proceed with Phase 4 directly

## Narration Pattern

```
Phase 1: Writing spec...

[show spec.md contents]

Spec is ready — review it and tell me when you're ready to proceed to planning.
---
Phase 2: Writing plan...

[show plan.md contents]

Plan is ready — review it and tell me when you're ready to decompose into tasks.
---
Phase 3: Decomposing into tasks...

Generated 5 tasks:
  01-setup.md — Initialize project structure (2 criteria)
  02a-backend.md — [parallel] Implement API routes (3 criteria)
  02b-frontend.md — [parallel] Build UI components (2 criteria)
  03-tests.md — Write integration tests (2 criteria)
  04-docs.md — Update documentation (1 criterion)

Tasks are ready — review them and tell me when you're ready to execute.
---
Phase 4: Executing...

Setting up project structure...
Building API routes and UI components in parallel...
Running integration tests...
Updating docs...

Done. [brief summary of what was built and what the audit trace shows]
```

## If Execution Fails

If a step fails `ensure` expressions after all retries:

1. Report what the violation was and what you tried
2. Ask the user: "Should I revert to a checkpoint and try a different approach, or do you want to adjust the task criteria?"
3. If reverting: use `stratum_commit` before the failed step and `stratum_revert` if needed
4. If adjusting: the user edits the task file and re-runs `/stratum-speckit` from Phase 4

## Memory

**Before Phase 1:** Read `MEMORY.md` for entries tagged `[stratum-speckit]`. Incorporate known constraints into the spec template's intent fields.

**After Phase 4 `stratum_audit`:** For each step with `attempts > 1`, ask: does the retry reveal a project-specific pattern worth capturing? Append one-liners to `MEMORY.md`:

```
[stratum-speckit] auth module requires JWT_SECRET in env — add to spec.md constraints section
[stratum-speckit] tasks/ files must use kebab-case with 2-digit prefix — 01-, 02a-, 02b- etc.
[stratum-speckit] test suite requires docker-compose up before running — capture in acceptance criteria
```

Only write entries that would change how you write specs, plans, or task criteria next time.
