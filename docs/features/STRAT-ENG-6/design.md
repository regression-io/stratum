# STRAT-ENG-6: Contract Freeze

**Date:** 2026-03-07
**Status:** Frozen
**Parent:** [STRAT-1 Design](../../../compose/docs/features/STRAT-1/design.md) (lines 411-421)
**Roadmap:** [Stratum ROADMAP.md](../../ROADMAP.md) item 43

## Purpose

Freeze the Stratum contract before Compose integration. Without this, integration thrashes.

This document is the frozen contract. Compose codes against these shapes. Post-freeze changes
require both sides to update. The contract covers four surfaces:

1. **Spec shape** — the `.stratum.yaml` IR v0.2 schema
2. **MCP tool signatures** — names, parameters, return shapes
3. **Flow state** — the persisted `FlowState` JSON shape
4. **Audit output** — the `stratum_audit` response shape

---

## 1. Spec Shape (IR v0.2)

Source: `stratum-mcp/src/stratum_mcp/spec.py`

### Top-Level Structure

```yaml
version: "0.2"                    # required, const
workflow:                          # optional — declares an invocable workflow
  name: string                    # pattern: ^[a-z][a-z0-9-]*$
  description: string             # minLength: 1
  input:                           # required — typed input schema
    param_name:
      type: string|boolean|integer|number|array|object
      required: true|false         # optional
      default: any                 # optional
contracts:                         # optional
  ContractName:
    field_name:
      type: string                 # required
      values: [...]               # optional
functions:                         # optional
  function_name: <FunctionDef>
flows:                             # required (at least one flow)
  flow_name: <FlowDef>
```

`additionalProperties: false` at top level. Version must be `"0.2"`.

### FlowDef

| Field | Type | Required | Default | Constraints |
|---|---|---|---|---|
| `input` | `object` | yes | — | Parameter schema |
| `output` | `string` | no | `""` | Contract reference |
| `budget` | `BudgetDef` | no | `null` | — |
| `steps` | `list[StepDef]` | yes | — | `minItems: 1` |
| `max_rounds` | `integer` | no | `null` | `minimum: 1` |

### FunctionDef

| Field | Type | Required | Default | Constraints |
|---|---|---|---|---|
| `mode` | `"infer"\|"compute"\|"gate"` | yes | — | — |
| `intent` | `string` | conditional | `""` | Required for non-gate |
| `input` | `object` | conditional | `{}` | Required for non-gate |
| `output` | `string` | conditional | `""` | Contract ref; required for non-gate |
| `ensure` | `list[string]` | no | `[]` | Forbidden on gate |
| `budget` | `BudgetDef` | no | `null` | Forbidden on gate |
| `retries` | `integer` | no | `3` | `minimum: 1`; forbidden on gate |
| `model` | `string` | no | `null` | — |
| `timeout` | `integer` | no | `null` | `minimum: 1`; gate-only (seconds) |

Internal field (not in YAML, not part of contract surface):
- `retries_explicit: bool` — tracks whether `retries` was explicitly present in YAML vs defaulted to `3`

### StepDef

#### Execution mode (exactly one required)

| Field | Type | Notes |
|---|---|---|
| `function` | `string` | Reference to `functions:` block |
| `intent` | `string` | Inline step — prompt text |
| `flow` | `string` | Sub-workflow invocation (IR field: `flow_ref`) |

#### Core fields

| Field | Type | Default | Constraints |
|---|---|---|---|
| `id` | `string` | — | Required, unique within flow |
| `agent` | `string` | `null` | Forbidden on `flow` steps |
| `inputs` | `object` | `{}` | `step_id → expression` |
| `depends_on` | `list[string]` | `[]` | Targets must be known step IDs |
| `output_schema` | `object` | `null` | Forbidden on gate steps |

Internal field (not in YAML, not part of contract surface):
- `declared_routing: frozenset` — tracks which of `on_approve`/`on_revise`/`on_kill` were explicitly present in YAML (distinguishes "absent" from "explicitly null")

#### Gate routing (gate steps only)

| Field | Type | Required | Constraints |
|---|---|---|---|
| `on_approve` | `string\|null` | yes (must be declared) | `null` = terminal; non-null = step ID |
| `on_revise` | `string\|null` | yes (non-null required) | Must target topologically-earlier step; not self |
| `on_kill` | `string\|null` | yes (must be declared) | `null` = terminal; non-null = step ID |

#### Non-gate routing

| Field | Type | Default | Constraints |
|---|---|---|---|
| `on_fail` | `string` | `null` | Requires `ensure` or `output_schema`; target must be known step ID |
| `next` | `string` | `null` | Target must be known step ID |

#### Skip

| Field | Type | Default | Constraints |
|---|---|---|---|
| `skip_if` | `string` | `null` | Forbidden on gate steps |
| `skip_reason` | `string` | `null` | — |

#### Policy (gate steps only)

| Field | Type | Default | Constraints |
|---|---|---|---|
| `policy` | `"gate"\|"flag"\|"skip"` | `null` | Forbidden on non-gate steps |
| `policy_fallback` | `"gate"\|"flag"\|"skip"` | `null` | Requires `policy`; forbidden on non-gate |

#### Iteration (non-gate steps only)

| Field | Type | Default | Constraints |
|---|---|---|---|
| `max_iterations` | `integer` | `null` | `minimum: 1`; forbidden on gate steps |
| `exit_criterion` | `string` | `null` | Requires `max_iterations`; no `__` (dunder guard) |

#### Step-level execution (inline steps only)

| Field | Type | Default | Constraints |
|---|---|---|---|
| `ensure` | `list[string]` | `null` | Also allowed on `flow` steps; forbidden on `function` steps |
| `retries` | `integer` | `null` | `minimum: 1`; forbidden on `function`/`flow` steps |
| `output_contract` | `string` | `null` | Forbidden on `function` steps. **Note:** accepted by schema on inline steps but **not validated at runtime for `flow` steps** — the executor sets `output_schema = None` for flow mode. Only `ensure` expressions are evaluated on flow step results. |
| `model` | `string` | `null` | Forbidden on `function`/`flow` steps |
| `budget` | `BudgetDef` | `null` | Forbidden on `function`/`flow` steps |

### BudgetDef

| Field | Type | Constraints |
|---|---|---|
| `ms` | `integer` | `minimum: 1`; optional |
| `usd` | `float` | `minimum: 0`; optional |

`additionalProperties: false`.

### Semantic Validation Summary

- Exactly one of `function`/`intent`/`flow` per step
- Gate steps: must declare `on_approve`, `on_revise`, `on_kill`; forbid `on_fail`, `next`, `skip_if`, `output_schema`, `max_iterations`
- Non-gate steps: forbid `on_approve`, `on_revise`, `on_kill`, `policy`, `policy_fallback`
- `on_fail` requires ensure (on step or function) or `output_schema`
- `on_fail`/`next` targets must be known step IDs
- `flow` steps: forbid `agent`, `retries`, `model`, `budget`; no recursive refs
- `workflow.input` keys must match entry flow's `input` keys
- `exit_criterion` must not contain `__`

---

## 2. MCP Tool Signatures

Source: `stratum-mcp/src/stratum_mcp/server.py`

### Error Envelope

All tools that return errors use a common shape:

```json
{
  "status": "error",
  "success": false,
  "error_type": "ir_parse_error|ir_validation_error|ir_semantic_error|execution_error|internal_error",
  "message": "string",
  "suggestion": "string (optional)",
  "path": "string (optional, validation/semantic errors)"
}
```

Flow-not-found errors use a simpler shape (no `success` field):

```json
{
  "status": "error",
  "error_type": "flow_not_found",
  "message": "No active flow with id '<flow_id>'"
}
```

### 2.1 `stratum_validate`

Validate a spec without executing.

| Parameter | Type | Required |
|---|---|---|
| `spec` | `string` | yes |

**Returns:**
```json
{ "valid": true, "errors": [] }
// or
{ "valid": false, "errors": [{ "error_type": "...", "message": "...", ... }] }
```

### 2.2 `stratum_plan`

Parse spec, create flow, return first step.

| Parameter | Type | Required | Default |
|---|---|---|---|
| `spec` | `string` | yes | — |
| `flow` | `string` | yes | — |
| `inputs` | `dict` | yes | — |

**Returns one of:**

| Status | Shape |
|---|---|
| `execute_step` | See [Step Dispatch Shape](#step-dispatch-shape) |
| `execute_flow` | See [Flow Dispatch Shape](#flow-dispatch-shape) |
| `await_gate` | See [Gate Dispatch Shape](#gate-dispatch-shape) |
| `complete` | See [Completion Shape](#completion-shape) |
| `error` | Error envelope |

### 2.3 `stratum_step_done`

Report step completion, get next step.

| Parameter | Type | Required |
|---|---|---|
| `flow_id` | `string` | yes |
| `step_id` | `string` | yes |
| `result` | `dict` | yes |

**Returns one of:**

| Status | When | Shape |
|---|---|---|
| `execute_step` | Next step ready | Step dispatch + optional `routed_from`/`violations` |
| `execute_flow` | Next step is flow_ref | Flow dispatch |
| `await_gate` | Next step is gate | Gate dispatch |
| `complete` | Flow finished | Completion shape |
| `ensure_failed` | Postcondition failed, retries remain | Step dispatch with `violations` |
| `schema_failed` | Output schema failed, retries remain | Step dispatch with `violations` |
| `error` | `retries_exhausted`, `flow_not_found`, `gate_step_requires_gate_resolve` | Error envelope |

When `on_fail` routes after retries exhaustion, the response is the next step dispatch
with extra fields `routed_from` (step ID) and `violations` (list of strings).

**Flow step unwrapping:** When `step_done` is called on a parent for a `flow_ref` step,
the server unwraps `result.output` before evaluation. Ensure expressions on the parent
step evaluate against the child's output directly.

### 2.4 `stratum_gate_resolve`

Resolve a pending gate step.

| Parameter | Type | Required | Values |
|---|---|---|---|
| `flow_id` | `string` | yes | — |
| `step_id` | `string` | yes | Must be current gate step |
| `outcome` | `string` | yes | `"approve"`, `"revise"`, `"kill"` |
| `rationale` | `string` | yes | — |
| `resolved_by` | `string` | yes | `"human"`, `"agent"`, `"system"` |

**Returns one of:**

| Status | When | Shape |
|---|---|---|
| `execute_step` | Approved/revised, next step ready | Step dispatch |
| `execute_flow` | Approved/revised, next is flow_ref | Flow dispatch |
| `await_gate` | Approved/revised, next is gate | Gate dispatch |
| `complete` | Approved, no more steps | Completion shape |
| `killed` | Kill outcome | `{ status, flow_id, trace, total_duration_ms }` (no `output`) |
| `error` | Various (see below) | Error envelope with `error_type` field |

**Error types from `resolve_gate()`:**

| `error_type` | When |
|---|---|
| `invalid_outcome` | `outcome` not in `{approve, revise, kill}` |
| `invalid_resolved_by` | `resolved_by` not in `{human, agent, system}` |
| `flow_already_complete` | Flow has no more steps |
| `wrong_step` | `step_id` doesn't match current step |
| `not_a_gate_step` | Current step's function mode is not `gate` |
| `step_not_found` | `on_approve`/`on_revise`/`on_kill` target not found in flow |
| `missing_on_revise` | Revise outcome but no `on_revise` target configured |
| `max_rounds_exceeded` | Revise would exceed `max_rounds` limit |

### 2.5 `stratum_skip_step`

Skip the current step with a recorded reason.

| Parameter | Type | Required |
|---|---|---|
| `flow_id` | `string` | yes |
| `step_id` | `string` | yes |
| `reason` | `string` | yes |

**Returns:** Same dispatch shapes as `stratum_step_done` (`execute_step`, `execute_flow`, `await_gate`, `complete`, `error`).

### 2.6 `stratum_check_timeouts`

Check if current gate has timed out; auto-kill if so.

| Parameter | Type | Required |
|---|---|---|
| `flow_id` | `string` | yes |

**Returns one of:**

| Status | When |
|---|---|
| `no_timeout` | No gate, no timeout configured, not yet elapsed. May include `remaining_seconds`. |
| `killed` | Timeout expired, `on_kill` is terminal. Includes `reason: "timeout"`. |
| `execute_step`/`await_gate`/`complete` | Timeout expired, routed via `on_kill` to another step. |
| `error` | Flow not found or unexpected state. |

### 2.7 `stratum_iteration_start`

Start an iteration loop on the current step.

| Parameter | Type | Required |
|---|---|---|
| `flow_id` | `string` | yes |
| `step_id` | `string` | yes |

**Returns:**
```json
{
  "status": "iteration_started",
  "flow_id": "string",
  "step_id": "string",
  "max_iterations": 10,
  "exit_criterion": "string|null",
  "iteration": 0
}
```

**Errors:** Flow complete, wrong step, gate step, no `max_iterations`, loop already active, pending outcome.

### 2.8 `stratum_iteration_report`

Report one iteration result.

| Parameter | Type | Required |
|---|---|---|
| `flow_id` | `string` | yes |
| `step_id` | `string` | yes |
| `result` | `dict` | yes |

**Returns — continue:**
```json
{
  "status": "iteration_continue",
  "flow_id": "string",
  "step_id": "string",
  "iteration": 1,
  "max_iterations": 10,
  "exit_criterion_met": false,
  "outcome": "continue"
}
```

**Returns — exit:**
```json
{
  "status": "iteration_exit",
  "flow_id": "string",
  "step_id": "string",
  "iteration": 5,
  "max_iterations": 10,
  "exit_criterion_met": true,
  "outcome": "exit_success|exit_max",
  "final_result": {},
  "exit_criterion_error": "string (only if eval failed)"
}
```

### 2.9 `stratum_iteration_abort`

Abort the active iteration loop.

| Parameter | Type | Required |
|---|---|---|
| `flow_id` | `string` | yes |
| `step_id` | `string` | yes |
| `reason` | `string` | yes |

**Returns:**
```json
{
  "status": "iteration_aborted",
  "flow_id": "string",
  "step_id": "string",
  "iteration": 3,
  "reason": "string"
}
```

### 2.10 `stratum_commit`

Create a named checkpoint.

| Parameter | Type | Required |
|---|---|---|
| `flow_id` | `string` | yes |
| `label` | `string` | yes |

**Returns:**
```json
{
  "status": "committed",
  "flow_id": "string",
  "label": "string",
  "step_number": 3,
  "current_step_id": "string|null",
  "checkpoints": ["label1", "label2"]
}
```

### 2.11 `stratum_revert`

Roll back to a named checkpoint.

| Parameter | Type | Required |
|---|---|---|
| `flow_id` | `string` | yes |
| `label` | `string` | yes |

**Returns:** Step dispatch shape with extra `reverted_to` field, or `complete` if checkpoint was post-completion. Error if checkpoint not found (includes `available` list).

### 2.12 `stratum_compile_speckit`

Compile `tasks/*.md` directory into `.stratum.yaml`.

| Parameter | Type | Required | Default |
|---|---|---|---|
| `tasks_dir` | `string` | yes | — |
| `flow_name` | `string` | no | `"tasks"` |

**Returns:**
```json
{
  "status": "ok",
  "yaml": "string",
  "flow_name": "string",
  "steps": [{ "id": "string", "title": "string", "parallel": false, "ensures": [], "judgment": "string|null" }]
}
```

### 2.13 `stratum_draft_pipeline`

Save a pipeline draft for later compilation.

| Parameter | Type | Required | Default |
|---|---|---|---|
| `draft` | `dict` | yes | — |
| `project_dir` | `string` | no | `"."` |

Draft must have `name` (string) and `phases` (list of `{ name, capability: scout|builder|critic, policy: gate|flag|skip }`).

**Returns:** `{ "status": "saved", "path": "string" }`

### 2.14 `stratum_list_workflows`

Discover registered workflow specs.

| Parameter | Type | Required | Default |
|---|---|---|---|
| `workflows_dir` | `string` | no | `"."` |

**Returns:**
```json
{
  "workflows": [{ "name": "string", "description": "string|null", "input": {}, "path": "string" }],
  "errors": ["string"]
}
```

### Common Response Shapes

#### Step Dispatch Shape

```json
{
  "status": "execute_step",
  "flow_id": "string",
  "step_number": 1,
  "total_steps": 5,
  "step_id": "string",
  "step_mode": "function|inline",
  "function": "string (function mode only)",
  "agent": "string|null",
  "mode": "string (function mode only)",
  "intent": "string",
  "inputs": {},
  "output_contract": "string|null",
  "output_fields": {},
  "ensure": [],
  "retries_remaining": 2,
  "model": "string|null (inline mode only)"
}
```

#### Flow Dispatch Shape

```json
{
  "status": "execute_flow",
  "parent_flow_id": "string",
  "parent_step_id": "string",
  "child_flow_id": "string",
  "child_flow_name": "string",
  "child_step": { "...step dispatch or gate dispatch..." },
  "step_number": 1,
  "total_steps": 5
}
```

#### Gate Dispatch Shape

```json
{
  "status": "await_gate",
  "flow_id": "string",
  "step_number": 2,
  "total_steps": 5,
  "step_id": "string",
  "step_mode": "function",
  "function": "string",
  "agent": "string|null",
  "on_approve": "string|null",
  "on_revise": "string|null",
  "on_kill": "string|null",
  "timeout": 3600
}
```

#### Completion Shape

```json
{
  "status": "complete",
  "flow_id": "string",
  "output": {},
  "trace": [],
  "total_duration_ms": 12345
}
```

Note: `status` may be `terminal_status` (e.g. `"killed"`) instead of `"complete"`.
The `trace` contains only the **active round's** records. Use `stratum_audit` for full history.

---

## 3. Flow State (Persisted JSON)

Source: `stratum-mcp/src/stratum_mcp/executor.py`

Persisted to `~/.stratum/flows/{flow_id}.json`.

```json
{
  "flow_id":              "uuid4",
  "flow_name":            "string",
  "raw_spec":             "string (original YAML)",
  "inputs":               {},

  "step_outputs":         { "step_id": {} },
  "attempts":             { "step_id": 1 },
  "current_idx":          0,
  "records":              [],

  "round":                0,
  "rounds":               [[]],
  "round_start_step_id":  "string|null",
  "terminal_status":      "string|null",

  "checkpoints":          { "label": {} },

  "active_iteration":     null,
  "iterations":           { "step_id": [] },
  "archived_iterations":  [{}],
  "iteration_outcome":    { "step_id": "exit_success|exit_max|exit_abort" },

  "parent_flow_id":       "string|null",
  "parent_step_id":       "string|null",
  "active_child_flow_id": "string|null",
  "child_audits":         { "step_id": [] }
}
```

**Not persisted** (reconstructed on restore):
- `spec` — rebuilt from `raw_spec` via `parse_and_validate()`
- `ordered_steps` — rebuilt via `_topological_sort()`
- `dispatched_at` — reset to `{}`
- `flow_start` — reset to `time.monotonic()`

### Record Types

All records have `type` discriminator, `round`, and `round_start_step_id`.

#### StepRecord

```json
{
  "type": "step",
  "step_id": "string",
  "function_name": "string",
  "attempts": 1,
  "duration_ms": 1234,
  "round": 0,
  "round_start_step_id": null,
  "agent": "string|null",
  "step_mode": "function|inline|flow",
  "child_flow_id": "string|null"
}
```

#### GateRecord

```json
{
  "type": "gate",
  "step_id": "string",
  "outcome": "approve|revise|kill",
  "rationale": "string",
  "resolved_by": "human|agent|system",
  "duration_ms": 1234,
  "round": 0,
  "round_start_step_id": null
}
```

#### SkipRecord

```json
{
  "type": "skip",
  "step_id": "string",
  "skip_reason": "string",
  "round": 0,
  "round_start_step_id": null
}
```

#### PolicyRecord

```json
{
  "type": "policy",
  "step_id": "string",
  "effective_policy": "flag|skip",
  "resolved_outcome": "approve",
  "rationale": "policy: {effective_policy} -- auto-approved",
  "round": 0,
  "round_start_step_id": null
}
```

### Iteration Report Shape (within `iterations` lists)

```json
{
  "iteration": 1,
  "round": 0,
  "result": {},
  "exit_criterion_met": false,
  "outcome": "continue|exit_success|exit_max|exit_abort",
  "timestamp": 1234567.89
}
```

### Active Iteration Shape

```json
{
  "step_id": "string",
  "round": 0,
  "max_iterations": 10,
  "exit_criterion": "string|null",
  "count": 0,
  "started_at": 1234567.89,
  "status": "active"
}
```

### Checkpoint Snapshot Shape

Each checkpoint captures the full mutable state:

```json
{
  "step_outputs": {},
  "attempts": {},
  "records": [],
  "current_idx": 0,
  "round": 0,
  "rounds": [],
  "round_start_step_id": null,
  "terminal_status": null,
  "iterations": {},
  "archived_iterations": [],
  "active_iteration": null,
  "iteration_outcome": {},
  "active_child_flow_id": null,
  "child_audits": {}
}
```

---

## 4. Audit Output

Source: `_build_audit_snapshot()` in `server.py`

Used by both `stratum_audit` and stored in `child_audits`.

```json
{
  "flow_id":              "string",
  "flow_name":            "string",
  "status":               "in_progress|complete|killed",
  "steps_completed":      3,
  "total_steps":          5,
  // Note: steps_completed = len(records), which counts ALL record types
  // (step, gate, skip, policy), not just step completions
  "trace":                [],
  "total_duration_ms":    12345,
  "round":                0,
  "rounds":               [{ "round": 0, "steps": [] }],
  "iterations":           { "step_id": [] },
  "archived_iterations":  [{ "step_id": [] }],
  "child_audits":         { "step_id": [] }
}
```

**Status derivation:**
- `"killed"` if `terminal_status == "killed"`
- `"complete"` if `current_idx >= len(ordered_steps)` and not killed
- `"in_progress"` otherwise

**Iteration entries in audit:** The `result` field is **stripped** from iteration reports
in the audit snapshot. Only metadata (`iteration`, `round`, `exit_criterion_met`,
`outcome`, `timestamp`) is included.

**Child audits:** Each entry in `child_audits[step_id]` is a full audit snapshot (same
shape as above), supporting arbitrary nesting for `flow_ref` chains.

---

## 5. Known Inconsistencies

1. **`steps_completed` semantics:** Counts all record types (`len(records)`), not just
   step completions. A flow with 2 steps + 1 gate + 1 policy auto-approve reports
   `steps_completed: 4` with `total_steps: 4`. Treat as "records in active round",
   not "steps finished".

---

## 6. Excluded from Contract

### `stratum_set_policy` — Removed from Scope

The STRAT-1 design (line 197) references `stratum_set_policy` for runtime policy
overrides. This tool does not exist and will not be built for STRAT-1.

**What is frozen:** Policy evaluation uses `step.policy ?? "gate"`. The `policy_fallback`
field is parsed and validated but never evaluated at runtime — it has no effect.

**What is NOT frozen:** Runtime policy overrides. The three-level chain
(`runtime_override ?? step.policy ?? step.policy_fallback ?? "gate"`) from the STRAT-1
design is not implemented. If runtime overrides are needed post-STRAT-1, they will
require a new contract addendum.

**Impact on Compose:** Compose cannot dynamically change a step's policy at runtime.
Policy is static per spec. If Compose needs to override a gate to skip/flag, it must
either:
- Generate a different spec with the desired `policy` values, or
- Use `stratum_skip_step` to bypass individual steps

Compose must NOT code against `stratum_set_policy` — it does not exist.

---

## 7. Backward Compatibility

- IR v0.1 specs are still supported via `SCHEMAS["0.1"]`
- The `functions:` block and `function:` reference on steps remain supported
- `record_type` legacy alias in `_record_from_dict` was removed in pre-release cleanup (R-5)

---

## 8. Contract Rules

1. Compose codes against the shapes in this document
2. Breaking changes to any shape require updating this document first
3. Additive fields (new optional fields with defaults) are non-breaking
4. Removing fields, changing types, or changing required/optional is breaking
5. New MCP tools are non-breaking; changing existing tool signatures is breaking
6. New record types are non-breaking; changing existing record shapes is breaking
