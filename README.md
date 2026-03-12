# Stratum

[![PyPI — stratum-mcp](https://img.shields.io/pypi/v/stratum-mcp?label=stratum-mcp)](https://pypi.org/project/stratum-mcp/)
[![PyPI — stratum-py](https://img.shields.io/pypi/v/stratum-py?label=stratum-py)](https://pypi.org/project/stratum-py/)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue)](LICENSE)

**State machine dispatch server for AI agent workflows.**

Stratum gives AI coding agents (Claude Code, Codex, etc.) a formal execution model. Instead of improvising a plan and retrying blindly, the agent writes a typed spec, the server tracks state, enforces postconditions, and returns structured failure context on retry. Every step produces an auditable trace record.

Two shipped components:

- **`stratum-mcp`** -- MCP server for Claude Code. Validates `.stratum.yaml` specs, manages flow execution state, enforces typed contracts and postconditions. Published on PyPI.
- **`stratum-py`** -- Python library with `@infer`, `@contract`, `@compute`, `@flow` decorators for building production LLM systems. Published on PyPI.

---

## Table of Contents

- [Installation](#installation)
- [Quick Start](#quick-start)
- [Core Concepts](#core-concepts)
- [YAML Spec Reference](#yaml-spec-reference)
- [MCP Tools API](#mcp-tools-api)
- [Step Types](#step-types)
- [Ensures (Postconditions)](#ensures-postconditions)
- [Contracts and Output Validation](#contracts-and-output-validation)
- [Gates (Human-in-the-Loop)](#gates-human-in-the-loop)
- [Flow Composition](#flow-composition)
- [Routing](#routing)
- [Iterations](#iterations)
- [Checkpoints](#checkpoints)
- [Recovery and Retry Logic](#recovery-and-retry-logic)
- [Workflows](#workflows)
- [Task Compiler](#task-compiler)
- [Skills](#skills)
- [CLI Reference](#cli-reference)
- [Configuration](#configuration)
- [Python Library (Track 1)](#python-library-track-1)
- [Examples](#examples)
- [Development](#development)
- [License](#license)

---

## Installation

### MCP Server (for Claude Code)

```bash
pip install stratum-mcp
stratum-mcp install
```

`install` does three things:
1. Writes `.claude/mcp.json` to register the MCP server
2. Appends the Stratum execution model block to `CLAUDE.md`
3. Installs eleven skills to `~/.claude/skills/`
4. Installs session hooks to `~/.stratum/hooks/`

Restart Claude Code to activate.

To remove:
```bash
stratum-mcp uninstall          # removes everything
stratum-mcp uninstall --keep-skills  # keeps user-customized skills
```

### Python Library

```bash
pip install stratum-py
```

Requires Python 3.11+. Dependencies: `litellm>=1.0`, `pydantic>=2.0`.

Set an API key for your LLM provider (`GROQ_API_KEY`, `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, etc.) and specify the model in `model=`.

---

## Quick Start

When Claude Code has Stratum installed, it uses it automatically for non-trivial tasks:

1. Claude writes a `.stratum.yaml` spec internally (never shown to you)
2. Calls `stratum_plan` to validate the spec and get the first step
3. Executes each step using its own tools (reading files, writing code, running tests)
4. Calls `stratum_step_done` after each step -- the server checks postconditions
5. If a postcondition fails, Claude gets back the specific violation and retries
6. Calls `stratum_audit` at the end for a full execution trace

You see plain English narration throughout. The spec, state management, and postcondition enforcement happen behind the scenes.

---

## Core Concepts

### Flows

A **flow** is a directed acyclic graph of steps with typed inputs and an output contract. Flows are defined in `.stratum.yaml` files and executed by the MCP server.

### Steps

A **step** is a single unit of work within a flow. Each step has an ID, an execution mode (function, inline, or flow), inputs that can reference flow-level inputs or prior step outputs, and optional postconditions.

### Functions

**Functions** are reusable definitions that steps reference. A function declares its mode (`infer`, `compute`, or `gate`), intent, input schema, output contract, postconditions, retry count, and optional model/budget.

### Contracts

**Contracts** define the shape of step outputs. They are named schemas with typed fields, validated against step results before postconditions run.

### Ensures

**Ensures** are postcondition expressions evaluated against step results. If any ensure fails, the step is retried with the specific violation. Example: `result.confidence > 0.7`.

### Retries

Each step has a retry budget. When an ensure or schema validation fails, the step is retried up to the declared limit. The agent receives the specific violations, not a blank replay.

### Gates

**Gate** steps pause execution and wait for external resolution (human approval, agent decision, or system timeout). Gates support `approve`, `revise`, and `kill` outcomes with configurable routing.

---

## YAML Spec Reference

A `.stratum.yaml` spec has four top-level sections: `version`, `contracts`, `functions`, and `flows`. An optional `workflow` block declares the spec as a registered workflow.

### Minimal Example (v0.1)

```yaml
version: "0.1"
contracts:
  SentimentResult:
    label: {type: string}
    confidence: {type: number}
functions:
  classify:
    mode: infer
    intent: "Classify the sentiment of this text"
    input: {text: {type: string}}
    output: SentimentResult
    ensure:
      - "result.label != ''"
      - "result.confidence > 0.7"
    retries: 2
flows:
  run:
    input: {text: {type: string}}
    output: SentimentResult
    steps:
      - id: s1
        function: classify
        inputs: {text: "$.input.text"}
```

### Full Example with Gates (v0.2)

```yaml
version: "0.2"
contracts:
  WorkOutput:
    result: {type: string}
    quality_score: {type: number}
functions:
  do_work:
    mode: infer
    intent: "Produce the deliverable"
    input: {text: {type: string}}
    output: WorkOutput
    ensure:
      - "result.quality_score >= 0.8"
    retries: 3
  review_gate:
    mode: gate
    timeout: 3600
flows:
  reviewed_work:
    input: {text: {type: string}}
    output: WorkOutput
    max_rounds: 3
    steps:
      - id: work
        function: do_work
        inputs: {text: "$.input.text"}
      - id: review
        function: review_gate
        on_approve: ~
        on_revise: work
        on_kill: ~
```

### Full Field Reference

#### `version` (required)

```yaml
version: "0.1"   # or "0.2"
```

Version `"0.2"` adds gates, inline steps, flow composition, policies, iterations, skip_if, routing, and workflows.

#### `contracts`

Named output schemas. Each contract is an object whose keys are field names and values are `{type: <type>}` objects.

```yaml
contracts:
  MyContract:
    field_name: {type: string}
    score: {type: number}
    tags: {type: array}
```

Supported types: `string`, `number`, `integer`, `boolean`, `array`, `object`.

#### `functions`

Reusable step definitions referenced by function steps.

```yaml
functions:
  my_function:
    mode: infer | compute | gate    # required
    intent: "What this function does" # required for infer/compute
    input:                            # required for infer/compute
      param_name: {type: string}
    output: ContractName              # required for infer/compute
    ensure:                           # optional (forbidden on gate)
      - "result.field > 0"
    retries: 3                        # optional, default 3 (forbidden on gate)
    budget:                           # optional (forbidden on gate)
      ms: 5000
      usd: 0.01
    model: "gpt-4o"                   # optional
    timeout: 3600                     # optional, gate only — seconds before auto-kill
```

**Gate functions** only require `mode: gate`. They must not have `ensure`, `budget`, or `retries`.

#### `flows`

Flow definitions with input schema, output contract, and ordered steps.

```yaml
flows:
  my_flow:
    input:
      param: {type: string}
    output: ContractName             # optional for gate-only flows
    budget:                          # optional
      ms: 30000
      usd: 0.10
    max_rounds: 5                    # optional (v0.2) — max gate revise cycles
    steps:
      - id: step_id                  # required, unique within flow
        # Execution mode — exactly one of:
        function: my_function        # references a function definition
        intent: "Do something"       # inline step (v0.2)
        flow: sub_flow_name          # sub-flow invocation (v0.2)

        # Common fields:
        inputs:                      # optional
          param: "$.input.param"
          prior: "$.steps.s1.output.field"
        depends_on: [s1, s2]         # optional — explicit dependencies
        output_schema:               # optional — JSON Schema for result validation
          type: object
          required: [done]
          properties:
            done: {type: boolean}

        # Inline step fields (v0.2, only with intent):
        agent: claude                # optional — agent assignment
        ensure:                      # optional
          - "result.done == True"
        retries: 2                   # optional, default 1
        output_contract: MyContract  # optional
        model: "gpt-4o"             # optional
        budget:                      # optional
          ms: 5000

        # Gate step fields (v0.2, only with function referencing a gate):
        on_approve: next_step | ~    # required — step to route to, or null for completion
        on_revise: earlier_step      # required — must target topologically earlier step
        on_kill: cleanup_step | ~    # required — step to route to, or null for termination
        policy: gate | flag | skip   # optional — auto-resolution policy
        policy_fallback: gate        # optional — requires policy

        # Non-gate routing (v0.2):
        on_fail: recovery_step       # optional — route on retry exhaustion (requires ensure)
        next: loop_back_step         # optional — override linear advancement on success

        # Conditional skip (v0.2):
        skip_if: "$.steps.s1.output.skip == True"  # optional (forbidden on gates)
        skip_reason: "Already done"                  # optional

        # Iteration (v0.2):
        max_iterations: 10                           # optional (forbidden on gates)
        exit_criterion: "result.quality >= 0.9"      # optional, requires max_iterations
```

#### `workflow` (v0.2)

Self-registering workflow declaration. Allows `stratum_list_workflows` to discover specs.

```yaml
workflow:
  name: my-workflow              # lowercase, hyphens only
  description: "What this workflow does"
  input:
    param_name:
      type: string
      required: true
      default: "value"
```

Workflow input keys must exactly match the entry flow's input keys.

### Input References

Step inputs use `$` references to chain data through the flow:

| Pattern | Resolves to |
|---|---|
| `$.input.<field>` | Flow-level input value |
| `$.steps.<step_id>.output` | Full output of a prior step |
| `$.steps.<step_id>.output.<field>` | Specific field from a prior step's output |
| `literal_value` | Passed through as-is |

References create implicit dependencies. The server also uses explicit `depends_on` for topological ordering (Kahn's algorithm).

---

## MCP Tools API

All tools are exposed via the MCP protocol. Claude Code calls them as tool invocations.

### `stratum_validate`

Validate a `.stratum.yaml` spec without creating a flow.

**Inputs:** `spec` (str, inline YAML)
**Returns:** `{valid: bool, errors: list}`

### `stratum_plan`

Validate a spec, create execution state, and return the first step to execute.

**Inputs:**
- `spec` (str) -- inline YAML
- `flow` (str) -- flow name
- `inputs` (dict) -- flow-level inputs

**Returns:** Step dispatch object with `status: "execute_step"` or `status: "await_gate"`, including:
- `flow_id` -- unique identifier for this execution
- `step_id`, `step_number`, `total_steps`
- `function`, `intent`, `inputs` (resolved)
- `output_contract`, `output_fields`, `ensure`
- `retries_remaining`
- `agent`, `step_mode`

### `stratum_step_done`

Report a completed step result. The server validates the result against output schemas and ensure expressions.

**Inputs:**
- `flow_id` (str)
- `step_id` (str)
- `result` (dict) -- step output matching the output contract

**Returns one of:**
- Next step to execute (`status: "execute_step"`)
- Ensure failure with retry info (`status: "ensure_failed"`, `violations`, `retries_remaining`)
- Schema validation failure (`status: "schema_failed"`, `violations`)
- Flow completion (`status: "complete"`, `output`, `trace`, `total_duration_ms`)
- Retries exhausted (`status: "error"`, `error_type: "retries_exhausted"`)
- Routed to recovery step (`routed_from`, `violations`)

### `stratum_audit`

Return the full execution trace for a flow.

**Inputs:** `flow_id` (str)

**Returns:**
- `flow_id`, `flow_name`, `status` (`complete`, `in_progress`, `killed`)
- `steps_completed`, `total_steps`
- `trace` -- array of step records (step_id, function_name, attempts, duration_ms, type, round)
- `round`, `rounds` -- round history for gate revise cycles
- `iterations`, `archived_iterations` -- iteration history
- `child_audits` -- audit snapshots from sub-flow executions
- `total_duration_ms`

### `stratum_gate_resolve`

Resolve a gate step with a human/agent/system decision.

**Inputs:**
- `flow_id` (str)
- `step_id` (str) -- must be the current gate step
- `outcome` (str) -- `"approve"`, `"revise"`, or `"kill"`
- `rationale` (str) -- human-readable reason
- `resolved_by` (str) -- `"human"`, `"agent"`, or `"system"`

**Returns:** Next step, flow completion, or flow termination.

### `stratum_check_timeouts`

Check whether a pending gate step has exceeded its configured timeout. Auto-kills with `resolved_by: "system"` if expired.

**Inputs:** `flow_id` (str)

### `stratum_skip_step`

Explicitly skip the current step (cannot skip gate steps).

**Inputs:** `flow_id` (str), `step_id` (str), `reason` (str)

### `stratum_commit`

Save a named checkpoint of the current flow state.

**Inputs:** `flow_id` (str), `label` (str)

### `stratum_revert`

Roll back flow state to a previously committed checkpoint.

**Inputs:** `flow_id` (str), `label` (str)

### `stratum_iteration_start`

Start an iteration loop on the current step (requires `max_iterations` in the spec).

**Inputs:** `flow_id` (str), `step_id` (str)

### `stratum_iteration_report`

Report one iteration result. Evaluates `exit_criterion`, increments count, checks `max_iterations`.

**Inputs:** `flow_id` (str), `step_id` (str), `result` (dict)

**Returns:** `iteration_continue` or `iteration_exit` with outcome.

### `stratum_iteration_abort`

Abort an active iteration loop before completion.

**Inputs:** `flow_id` (str), `step_id` (str), `reason` (str)

### `stratum_compile_speckit`

Compile a spec-kit tasks directory into a `.stratum.yaml` flow.

**Inputs:** `tasks_dir` (str), `flow_name` (str, default `"tasks"`)

**Returns:** `{status, yaml, flow_name, steps}` on success.

### `stratum_list_workflows`

Scan a directory for `*.stratum.yaml` files with `workflow:` blocks. Returns registered workflows with name, description, input schema, and file path. Detects duplicate names.

### `stratum_draft_pipeline`

Push a pipeline draft to the PipelineEditor UI via `.stratum/pipeline-draft.json`.

---

## Step Types

### Function Steps

Reference a named function definition. The function provides the intent, input schema, output contract, ensures, retries, and model.

```yaml
steps:
  - id: classify
    function: classify_sentiment
    inputs: {text: "$.input.text"}
```

### Inline Steps (v0.2)

Self-contained steps with `intent` and optional `agent`. No function reference needed. Execution fields (`ensure`, `retries`, `output_contract`, `model`, `budget`) are declared directly on the step.

```yaml
steps:
  - id: analyze
    intent: "Analyze the codebase for security vulnerabilities"
    agent: claude
    ensure:
      - "result.vulnerabilities_checked == True"
    retries: 2
    output_contract: AnalysisResult
```

### Flow Steps (v0.2)

Invoke a sub-flow defined in the same spec. The child flow runs to completion, and its output is unwrapped into the parent step's result.

```yaml
steps:
  - id: run_tests
    flow: test_suite
    inputs: {project: "$.input.project"}
    ensure:
      - "result.all_passed == True"
    on_fail: fix_tests
```

Flow steps must not have `agent`, `retries`, `model`, or `budget`. They may have `ensure` and `on_fail`.

### Mode Exclusion

Every step must have exactly one of `function`, `intent`, or `flow`. Having zero or more than one is a semantic error caught at parse time.

---

## Ensures (Postconditions)

Ensures are Python expressions evaluated against the step result. The result is available as `result` (dicts are wrapped in `SimpleNamespace` for attribute access).

### Expression Syntax

```yaml
ensure:
  - "result.confidence > 0.7"
  - "result.label != ''"
  - "len(result.items) > 0"
  - "result.status in ('success', 'partial')"
```

### Built-in Functions

| Function | Signature | Description |
|---|---|---|
| `file_exists` | `file_exists(path)` | Returns `True` if the file exists on disk |
| `file_contains` | `file_contains(path, substring)` | Returns `True` if the file contains the substring (10 MB limit) |
| `len` | `len(x)` | Standard Python `len` |
| `bool` | `bool(x)` | Standard Python `bool` |
| `int` | `int(x)` | Standard Python `int` |
| `str` | `str(x)` | Standard Python `str` |

### Safety

- `__builtins__` is always empty -- no access to `os`, `sys`, `import`, etc.
- Dunder attributes (`__`) are blocked at compile time
- Expressions are compiled once and cached

### Failure Behavior

When an ensure expression fails, the server returns:
```json
{
  "status": "ensure_failed",
  "violations": ["ensure 'result.confidence > 0.7' failed"],
  "retries_remaining": 2
}
```

The agent receives the specific violations and can target its fix accordingly.

---

## Contracts and Output Validation

### Contracts in the Spec

Contracts define expected output shapes. Fields specify their type:

```yaml
contracts:
  AnalysisResult:
    summary: {type: string}
    score: {type: number}
    issues: {type: array}
    metadata: {type: object}
    is_valid: {type: boolean}
```

When a function or step references an output contract, the server resolves the contract fields and includes them in the step dispatch so the agent knows what shape to produce.

### Output Schema (Per-Step JSON Schema)

Steps can declare a full JSON Schema for structural validation. This runs **before** ensure expressions:

```yaml
steps:
  - id: s1
    function: do_work
    inputs: {text: "$.input.text"}
    output_schema:
      type: object
      required: [done, tests_pass]
      properties:
        done: {type: boolean}
        tests_pass: {type: boolean}
```

Schema violations are returned as `status: "schema_failed"` with specific error messages.

---

## Gates (Human-in-the-Loop)

Gates are approval checkpoints that pause flow execution until resolved externally.

### Defining a Gate

```yaml
functions:
  approval:
    mode: gate
    timeout: 3600    # optional — auto-kill after 1 hour

flows:
  my_flow:
    max_rounds: 3    # optional — limit revise cycles
    steps:
      - id: work
        function: do_work
        inputs: {text: "$.input.text"}
      - id: review
        function: approval
        on_approve: ~           # null = complete the flow
        on_revise: work         # must target a topologically earlier step
        on_kill: ~              # null = terminate the flow
```

### Gate Constraints

- Gate functions must not have `ensure`, `budget`, or `retries`
- Gate steps must not have `skip_if` or `output_schema`
- Gate steps must explicitly declare `on_approve` and `on_kill` (even if null)
- `on_revise` must be non-null and must target a topologically earlier step
- `on_revise` must not self-reference

### Resolution

Gates are resolved via `stratum_gate_resolve` or the CLI `stratum-mcp gate` command:

- **approve** -- routes to `on_approve` target (or completes flow if null)
- **revise** -- archives the current round, resets state, routes to `on_revise` target
- **kill** -- routes to `on_kill` target (or terminates flow with `status: "killed"` if null)

`resolved_by` is one of `"human"`, `"agent"`, or `"system"`.

### Gate Policies (v0.2)

Gate steps can have an auto-resolution policy:

```yaml
- id: review
  function: approval
  policy: skip          # auto-approve without pausing
  policy_fallback: gate # fall back to manual gate if policy fails
  on_approve: ~
  on_revise: work
  on_kill: ~
```

| Policy | Behavior |
|---|---|
| `gate` | Default -- pause and wait for resolution |
| `flag` | Auto-approve, but log a PolicyRecord in the trace |
| `skip` | Auto-approve silently |

`policy_fallback` requires `policy` to be set.

### Timeout

If a gate function has `timeout` set, `stratum_check_timeouts` will auto-kill the gate with `resolved_by: "system"` when the timeout expires.

### Rounds

When a gate is resolved with `revise`, the current round's trace is archived into `state.rounds`, the active trace is reset, and the round counter increments. `max_rounds` on the flow limits how many revise cycles are allowed.

---

## Flow Composition

Steps with `flow:` invoke a sub-flow defined in the same spec. The parent flow suspends until the child completes.

```yaml
flows:
  integration_tests:
    input: {project: {type: string}}
    output: TestResult
    steps:
      - id: run
        intent: "Run integration tests"
        ensure:
          - "result.all_passed == True"

  deploy:
    input: {project: {type: string}}
    output: DeployResult
    steps:
      - id: test
        flow: integration_tests
        inputs: {project: "$.input.project"}
        on_fail: rollback
      - id: release
        intent: "Deploy to production"
      - id: rollback
        intent: "Roll back deployment"
```

- Child flows get their own `FlowState` and `flow_id`
- Child audit snapshots are accumulated in `child_audits` on the parent
- Recursive flow references are detected and rejected at parse time
- Flow steps must not set `agent`, `retries`, `model`, or `budget`

---

## Routing

### `on_fail` -- Recovery Routing

Routes to a named recovery step when retries are exhausted (requires `ensure` or `output_schema`):

```yaml
- id: generate
  function: generate_code
  inputs: {spec: "$.input.spec"}
  on_fail: manual_fix

- id: manual_fix
  intent: "Fix the generated code manually"
```

The failed step's output is preserved so the recovery step can access it via `$.steps.generate.output`.

### `next` -- Success Routing

Overrides linear step advancement on success. Enables review loops:

```yaml
- id: write
  intent: "Write the code"
  next: review

- id: review
  intent: "Review the code"
  ensure:
    - "result.approved == True"
  on_fail: write
```

When `next` routes to a step, that step's attempts are cleared for fresh execution.

### Conditional Skip

Steps can be conditionally skipped based on prior outputs:

```yaml
- id: deploy
  intent: "Deploy to staging"
  skip_if: "$.steps.tests.output.all_passed == False"
  skip_reason: "Tests failed, skipping deployment"
```

Skipped steps have their output set to `None`. Gate steps cannot have `skip_if`.

`skip_if` expressions support `$` references, Python-style booleans (`True`, `False`, `None`), and YAML-style literals (`true`, `false`, `null`).

---

## Iterations

Steps with `max_iterations` support counted sub-loops. The agent iterates until `exit_criterion` is met or the maximum count is reached.

```yaml
- id: refine
  intent: "Improve the output quality"
  max_iterations: 5
  exit_criterion: "result.quality >= 0.95"
```

**Iteration workflow:**
1. `stratum_iteration_start(flow_id, step_id)` -- begins the loop
2. `stratum_iteration_report(flow_id, step_id, result)` -- reports each iteration; server evaluates `exit_criterion`
3. Returns `iteration_continue` or `iteration_exit`
4. `stratum_iteration_abort(flow_id, step_id, reason)` -- early exit

Gate steps cannot use iterations. `exit_criterion` requires `max_iterations`. Iteration history is preserved across gate revise cycles in `archived_iterations`.

---

## Checkpoints

Named snapshots of flow state for rollback scenarios.

```yaml
# During execution:
stratum_commit(flow_id, "after_analysis")
# ... later steps fail ...
stratum_revert(flow_id, "after_analysis")
```

Checkpoints capture: `step_outputs`, `attempts`, `records`, `current_idx`, round state, iteration state, and child flow state. They survive server restarts (persisted to disk).

---

## Recovery and Retry Logic

### Retry Budget

Each function or inline step declares a retry count (default 3 for functions, 1 for inline steps). The server tracks attempts per step.

### Retry Flow

1. Agent submits result via `stratum_step_done`
2. Server validates against `output_schema` (if declared) -- structural errors first
3. Server evaluates `ensure` expressions
4. If violations exist and retries remain: returns `ensure_failed` or `schema_failed` with violations and remaining retry count
5. If retries exhausted and `on_fail` is set: routes to recovery step
6. If retries exhausted with no `on_fail`: returns `retries_exhausted` error

### Persistence

Flow state is persisted to `~/.stratum/flows/{flow_id}.json` after each state mutation. Flows survive MCP server restarts. Timing fields are reset on restore (step durations may be inaccurate for the resumed step).

### Server Restart Recovery

On any tool call, if the flow is not in memory, the server attempts to restore it from disk. The spec is re-parsed, steps are re-sorted, and execution resumes from the persisted `current_idx`.

---

## Workflows

Workflow declarations make specs discoverable via `stratum_list_workflows`:

```yaml
version: "0.2"
workflow:
  name: code-review
  description: "Three-pass code review: security, logic, performance"
  input:
    files:
      type: array
      required: true
    depth:
      type: string
      required: false
      default: "standard"
```

`stratum_list_workflows` scans a directory for `*.stratum.yaml` files with `workflow:` blocks and returns their metadata. Duplicate workflow names are reported as errors.

---

## Task Compiler

The task compiler converts spec-kit task files (`tasks/*.md`) into `.stratum.yaml` flows.

### Task File Format

```markdown
# Task: [P] Implement authentication

Add JWT-based authentication to the API.

## Acceptance Criteria

- [ ] file src/auth/middleware.ts exists
- [ ] file src/auth/middleware.ts contains "verifyToken"
- [ ] tests pass
- [ ] no lint errors
- [ ] Error messages are user-friendly
```

### Compilation Rules

- `[P]` in the title marks the task as parallelizable
- `file X exists` compiles to `file_exists("X")`
- `file X contains Y` compiles to `file_contains("X", "Y")`
- `tests pass` compiles to `result.tests_pass == True`
- `no lint errors` compiles to `result.lint_clean == True`
- Freeform criteria are incorporated into the step's `intent`

### Dependency Graph

- Sequential tasks depend on the prior task
- Parallel tasks (`[P]`) share the same predecessor with no edges between them
- After a parallel group, the next sequential task depends on all tasks in the group

### Usage

```bash
stratum-mcp compile tasks/ --output flow.stratum.yaml --flow my_flow
```

Or via MCP tool: `stratum_compile_speckit(tasks_dir, flow_name)`.

---

## Skills

Eleven skills are installed by `stratum-mcp install`:

| Skill | Purpose |
|---|---|
| `/stratum-onboard` | Read a new codebase cold, write project-specific `MEMORY.md` |
| `/stratum-plan` | Design a feature, present for review -- no implementation |
| `/stratum-feature` | Full feature build: read patterns, design, implement, test |
| `/stratum-review` | Three-pass code review: security, logic, performance |
| `/stratum-debug` | Hypothesis-driven debugging with elimination |
| `/stratum-refactor` | File splitting with planned extraction order |
| `/stratum-migrate` | Rewrite bare LLM calls as `@infer` + `@contract` |
| `/stratum-test` | Write test suite for untested code (golden flows, error-path harness) |
| `/stratum-learn` | Extract patterns from session transcripts into `MEMORY.md` |
| `/stratum-build` | Compile tasks, drive execution via `stratum_plan` loop |
| `/stratum-speckit` | Bridge skill for spec-kit phase execution |

Each skill reads project-specific patterns from `MEMORY.md` before writing its spec and writes new patterns after `stratum_audit`.

---

## CLI Reference

```
stratum-mcp                        # Start stdio MCP server (for Claude Code)
stratum-mcp install                # Configure Claude Code project for Stratum
stratum-mcp uninstall              # Remove Stratum configuration
stratum-mcp uninstall --keep-skills # Remove config but keep skill files
stratum-mcp validate <file>        # Validate a .stratum.yaml spec
stratum-mcp compile <dir>          # Compile tasks/*.md to .stratum.yaml
  --output <file>                  #   Write to file instead of stdout
  --flow <name>                    #   Flow name (default: "tasks")
stratum-mcp query flows            # List all persisted flows (JSON)
stratum-mcp query flow <id>        # Full state for a single flow (JSON)
stratum-mcp query gates            # List all pending gate steps (JSON)
stratum-mcp gate approve <flow_id> <step_id> [--note "reason"]
stratum-mcp gate reject  <flow_id> <step_id> [--note "reason"]
stratum-mcp gate revise  <flow_id> <step_id> [--note "reason"]
  --resolved-by human|agent|system # Who resolved (default: human)
stratum-mcp help                   # Show help
```

---

## Configuration

### Flow State Storage

Persisted flows are stored in `~/.stratum/flows/{flow_id}.json`. This directory is created automatically.

### Hooks

Hooks are installed to `~/.stratum/hooks/` and registered in `.claude/settings.json`:

| Hook Event | Script | Behavior |
|---|---|---|
| `SessionStart` | `stratum-session-start.sh` | Inject relevant `MEMORY.md` entries |
| `Stop` | `stratum-session-stop.sh` | Append session summary to `MEMORY.md` |
| `PostToolUseFailure` | `stratum-post-tool-failure.sh` | Record ensure failures and tool errors |

### MCP Registration

The MCP server is registered in `.claude/mcp.json`:

```json
{
  "mcpServers": {
    "stratum": {
      "command": "stratum-mcp"
    }
  }
}
```

### CLAUDE.md Block

The execution model block appended to `CLAUDE.md` instructs the agent to use Stratum for non-trivial tasks:

```
## Stratum Execution Model

For non-trivial tasks, use Stratum internally:
1. Write a .stratum.yaml spec -- never show it to the user
2. Call stratum_plan to validate and get the first step
3. Narrate progress in plain English as you execute each step
4. Call stratum_step_done after each step -- the server checks your work
5. If a step fails postconditions, fix it silently and retry
6. Call stratum_audit at the end and include the trace in the commit
```

---

## Python Library (Track 1)

The `stratum-py` library provides decorators for building production LLM systems directly in Python. This is independent of the MCP server.

### Core Decorators

```python
from stratum import contract, infer, compute, flow, Budget

@contract
class SentimentResult(BaseModel):
    label: Literal["positive", "negative", "neutral"]
    confidence: float
    reasoning: str

@infer(
    intent="Classify the emotional tone of customer feedback",
    ensure=lambda r: r.confidence > 0.7,
    model="groq/llama-3.3-70b-versatile",
    budget=Budget(ms=8000, usd=0.01),
    retries=3,
)
def classify_sentiment(text: str) -> SentimentResult: ...

@compute
def format_result(result: SentimentResult) -> str:
    return f"[{result.label}] {result.confidence:.0%}"

@flow(budget=Budget(ms=30000, usd=0.05))
async def analyse_batch(texts: list[str]) -> list[SentimentResult]:
    return [await classify_sentiment(text=t) for t in texts]
```

### Key Features

| Feature | Description |
|---|---|
| `@infer` / `@compute` | Identical type signatures -- swap without downstream changes |
| `@contract` | Pydantic `BaseModel` compiled to JSON Schema with content hash |
| `@flow` | Async flow wrapper with `Budget` and `ContextVar`-scoped flow_id |
| `@refine` | Convergence loop -- iterates until `until(result)` passes |
| `parallel(require=)` | `"all"` / `"any"` / N / `0` modes via `asyncio.TaskGroup` |
| `debate()` | Multi-agent structured argumentation with synthesizer |
| `await_human()` | HITL gate -- suspends flow until `ReviewSink` resolves |
| `quorum=` | N parallel calls with agreement threshold |
| `stable=` | Probabilistic output wrapping (`Probabilistic[T]`) |
| `opaque[T]` | Prompt injection protection -- excluded from tool-call schema |
| `Budget(ms=, usd=, tokens=)` | Hard time + cost + token limits |
| OTLP trace export | Built-in emitter, no OTel SDK dependency |

### Exceptions

| Exception | Trigger |
|---|---|
| `PostconditionFailed` | `ensure` violations after all retries |
| `PreconditionFailed` | `given` condition false before LLM call |
| `ParseFailure` | LLM output cannot be parsed against contract |
| `BudgetExceeded` | Time or cost budget exceeded |
| `ConvergenceFailure` | `@refine` exhausted `max_iterations` |
| `ConsensusFailure` | `quorum` could not reach `threshold` agreement |
| `HITLTimeoutError` | `await_human` wall-clock timeout |
| `StabilityAssertionError` | `Probabilistic[T].assert_stable()` below threshold |
| `StratumCompileError` | Static violations at decoration time |

---

## Examples

Working examples in [`examples/`](https://github.com/regression-io/stratum/tree/main/examples):

| File | What it demonstrates |
|---|---|
| [`01_sentiment.py`](examples/01_sentiment.py) | `@infer` + `@contract` + `@flow` + `@compute` end-to-end |
| [`02_migrate.py`](examples/02_migrate.py) | Migrating `@infer` to `@compute` without changing callers |
| [`03_parallel.py`](examples/03_parallel.py) | Three concurrent `@infer` calls with `parallel(require="all")` |
| [`04_refine.py`](examples/04_refine.py) | `@refine` convergence loop until quality passes |
| [`05_debate.py`](examples/05_debate.py) | `debate()` -- two agents argue, synthesizer resolves |
| [`06_hitl.py`](examples/06_hitl.py) | `await_human` -- human-in-the-loop approval gate |

---

## Development

```bash
git clone https://github.com/regression-io/stratum
cd stratum
git config core.hooksPath .githooks
```

### MCP Server

```bash
cd stratum-mcp
pip install -e ".[dev]"
pytest tests/
```

### Python Library

```bash
pip install -e ".[dev]"
pytest tests/
```

### Test Counts

The MCP server has 418+ tests across contracts, invariants, integration, and end-to-end suites. The Python library has 321+ tests including real LLM integration tests.

### CI/CD

PyPI publishing runs automatically via GitHub Actions when `pyproject.toml` changes on `main`. Required secrets:
- `PYPI_TOKEN_MCP` -- scoped to `stratum-mcp`
- `PYPI_TOKEN_PY` -- scoped to `stratum-py`

---

## License

[Apache 2.0](LICENSE)
