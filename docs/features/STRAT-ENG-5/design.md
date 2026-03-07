# STRAT-ENG-5: Executor — Routing and Composition

**Date:** 2026-03-07
**Status:** Design
**Parent:** [STRAT-1 Design](../../../compose/docs/features/STRAT-1/design.md) (lines 401-408)
**Roadmap:** [Stratum ROADMAP.md](../../ROADMAP.md) item 42

## Problem

Stratum's executor handles linear step sequences and gate routing, but lacks two
primitives needed for real workflows:

1. **Non-gate routing** — when a step fails its `ensure` postconditions and exhausts
   retries, the flow stops. There's no way to route to a recovery step (`on_fail`) or
   to override the default next-step after success (`next`). Cross-agent loops like
   review→fix→review are impossible without these.

2. **Flow composition** — a step with `flow_ref` raises `MCPExecutionError("requires
   STRAT-ENG-5")`. Sub-workflow invocation doesn't exist, so reusable patterns
   (review-fix, coverage-sweep) can't be composed.

## Goal

Implement `on_fail`, `next`, and `flow:` sub-execution in the executor and server.
After this, Stratum can run the review-fix loop from the STRAT-1 design:

```yaml
steps:
  - id: review
    agent: codex
    intent: "Review implementation. Return {clean, findings}."
    ensure: ["result.clean == true"]
    on_fail: fix

  - id: fix
    agent: claude
    intent: "Fix all findings."
    inputs:
      findings: "$.steps.review.output.findings"
    next: review
```

## What Already Exists

**Spec layer (mostly complete — one validator fix needed):**
- `IRStepDef` fields: `on_fail`, `next`, `flow_ref` — parsed from YAML
- JSON Schema: `on_fail` and `next` as string, `flow` as string
- Semantic validation: `on_fail` requires ensure, targets must exist in flow,
  `next` targets must exist, `flow_ref` must reference known flow, no recursive refs,
  flow_ref steps can't have `agent`/`retries`/`model`/`budget`

**Validator bug (spec.py:732-736):** The `on_fail` check is
`if step.on_fail and not step.step_ensure` — this only checks `step_ensure` (inline
step ensure), not function-level `fn_def.ensure`. A function step with `on_fail` is
rejected even when its function has ensure expressions. Fix: check both
`step.step_ensure` and (for function steps) `fn_def.ensure`.

**Executor (needs changes):**
- `_step_mode()` (executor.py:253-264) — raises for `flow_ref`
- `process_step_result()` (executor.py:692-775) — no `on_fail` or `next` handling
- `get_current_step_info()` (executor.py:595-689) — no `flow_ref` dispatch
- Gate routing in `resolve_gate()` (executor.py:786-937) — reference pattern for step routing

**Server (needs changes):**
- `stratum_step_done` (server.py:120-217) — handles `ok`, `ensure_failed`, `retries_exhausted`
- `stratum_audit` (server.py:218-280) — no nested flow trace support

## Design

### 1. `on_fail` Routing

**Where:** `process_step_result()` at executor.py:766-770

**Current behavior:**
```python
if violations:
    if attempt >= max_retries:
        state.records.append(_make_record(duration_ms))
        return ("retries_exhausted", violations)
    return ("ensure_failed", violations)
```

**New behavior:** When `retries_exhausted` and `step.on_fail` is set, route to the
target step instead of terminating.

```python
if violations:
    if attempt >= max_retries:
        state.records.append(_make_record(duration_ms))
        if step.on_fail:
            # Store partial output so on_fail target can read $.steps.<id>.output
            state.step_outputs[step_id] = result
            target_idx = _find_step_idx(state, step.on_fail)
            _clear_from(state, target_idx, preserve={step_id})
            state.current_idx = target_idx
            return ("on_fail_routed", violations)
        return ("retries_exhausted", violations)
    return ("ensure_failed", violations)
```

**Design decisions:**

- **No round increment.** `on_fail` is within-round recovery, not a revision cycle.
  The flow stays on the same round. Rounds are only incremented by gate `on_revise`.

- **Store the failed step's output.** The `on_fail` target typically needs the failure
  data (e.g., `$.steps.review.output.findings`). The output is stored even though
  `ensure` failed — this is intentional. The step "completed" with a result that
  didn't meet postconditions.

- **Preserve the failed step's output across `_clear_from`.** The `preserve` parameter
  excludes the specified step ids from clearing. This is critical for backward
  `on_fail` routing — if `on_fail` targets a step *before* the failed step (e.g.,
  step C fails and routes to step A), the failed step's output would be in the
  clear range. `preserve={step_id}` keeps it accessible to the `on_fail` target via
  `$.steps.<failed_step>.output`.

- **Clear downstream state.** Steps from `target_idx` onward (minus preserved) get
  their `attempts` and `step_outputs` cleared so they execute fresh. This reuses the
  same pattern as `resolve_gate` on_revise (executor.py:903-911) minus the round
  archival.

- **Return status `"on_fail_routed"`.** Distinct from `"ok"` so the server can include
  the violations in its response for transparency. The server handles it identically
  to `"ok"` — calls `get_current_step_info()` to return the next step.

- **Schema validation failures also route.** If `output_schema` validation fails at
  line 747 and retries are exhausted, the same `on_fail` routing applies.

- **Cascading on_fail.** If the `on_fail` target itself fails, it follows its own
  `on_fail` (if set) or terminates normally. No special handling needed — the existing
  retry+ensure logic applies to every step independently.

**Helper functions to extract:**

```python
def _find_step_idx(state: FlowState, target_id: str) -> int:
    """Find step index by id. Raise MCPExecutionError if not found."""
    idx = next((i for i, s in enumerate(state.ordered_steps) if s.id == target_id), None)
    if idx is None:
        raise MCPExecutionError(f"Step '{target_id}' not found in flow")
    return idx

def _clear_from(state: FlowState, target_idx: int, preserve: set[str] | None = None):
    """Clear attempts, outputs, and iteration state from target_idx onward.

    Used by on_fail, next, and resolve_gate (on_revise). This is a within-round
    clear — it does NOT archive rounds or iterations. resolve_gate handles
    archival separately before calling this.

    preserve: step ids to exclude from clearing. Used by on_fail to keep the
    failed step's output accessible to the recovery step even when the target
    is topologically before the failed step.
    """
    steps_to_clear = {s.id for s in state.ordered_steps[target_idx:]}
    if preserve:
        steps_to_clear -= preserve
    for sid in list(state.step_outputs.keys()):
        if sid in steps_to_clear:
            del state.step_outputs[sid]
    for sid in list(state.attempts.keys()):
        if sid in steps_to_clear:
            del state.attempts[sid]
    for sid in steps_to_clear:
        state.iteration_outcome.pop(sid, None)
    # Clear per-step iteration history for affected steps (ENG-4)
    for sid in steps_to_clear:
        state.iterations.pop(sid, None)
    # Clear active_iteration if it belongs to an affected step
    if state.active_iteration and state.active_iteration.get("step_id") in steps_to_clear:
        state.active_iteration = None
    # Clear active child flow if it belongs to an affected flow_ref step
    if state.active_child_flow_id is not None:
        state.active_child_flow_id = None
```

These helpers also serve `resolve_gate` — refactor the existing code in
`resolve_gate` on_revise (lines 903-911) to use `_clear_from`. The on_revise
path archives iterations into `state.archived_iterations` *before* calling
`_clear_from`, so the archive captures history and the clear provides fresh state.

### 2. `next` Routing

**Where:** `process_step_result()` at executor.py:772-775

**Current behavior:**
```python
state.step_outputs[step_id] = result
state.records.append(_make_record(duration_ms))
state.current_idx += 1
return ("ok", [])
```

**New behavior:** When step has `next`, route to that step instead of linear advance.

```python
state.step_outputs[step_id] = result
state.records.append(_make_record(duration_ms))
if step.next:
    target_idx = _find_step_idx(state, step.next)
    _clear_from(state, target_idx)
    state.current_idx = target_idx
else:
    state.current_idx += 1
return ("ok", [])
```

**Design decisions:**

- **Backward routing is intentional.** `next: review` from a `fix` step creates a
  loop. This is the primary use case (review→fix→review). No cycle prevention here —
  that's what `max_rounds` and step `retries` guard against.

- **Clear downstream state on routing.** When `next` routes backward, the target step
  and everything after it must start fresh (cleared attempts, outputs). Without this,
  the target step would see stale outputs from the previous iteration.

- **No round increment.** Same reasoning as `on_fail` — `next` is within-round
  routing. A review→fix→review loop runs within a single round until the review's
  `ensure` passes or retries exhaust.

- **Return status stays `"ok"`.** The step completed successfully — it just routes
  differently. The server handles this identically to normal advancement.

- **Infinite loop guard.** `next` loops are bounded by the target step's `retries`
  (ensure failures exhaust retries) or `max_iterations` (STRAT-ENG-4). If neither is
  set and `ensure` always fails, the loop runs forever — this is a spec authoring
  error, not an executor concern. The semantic validator could add a warning but this
  is out of scope for ENG-5.

### 3. `flow:` Sub-Execution

**Where:** `_step_mode()`, `get_current_step_info()`, `process_step_result()` in
executor.py; `stratum_step_done`, `stratum_plan`, `stratum_audit` in server.py.

#### Execution Model

When the executor reaches a `flow_ref` step, it creates a child FlowState and tells
Claude Code to drive it. The parent flow pauses. Claude Code executes the child flow
using the same `stratum_step_done` loop it uses for any flow. When the child completes,
Claude Code calls `stratum_step_done` on the parent with the child's result.

```
Parent flow                          Child flow
─────────────────                    ──────────────────
step: implement → ok
step: review_fix (flow_ref)
  ├─ create child flow ──────────→  stratum_plan → first step
  ├─ return execute_flow             step: review → step_done
  │   (parent paused)                step: fix → step_done
  │                                  step: review → step_done (clean)
  │                                  flow complete → audit
  ├─ step_done(parent, result) ←── child result
  └─ advance to next step
```

#### Executor Changes

**`_step_mode`** (executor.py:253-264):
```python
def _step_mode(step) -> str:
    if step.function:
        return "function"
    if step.intent:
        return "inline"
    if step.flow_ref:
        return "flow"
    raise MCPExecutionError(f"Step '{step.id}' has no execution mode")
```

**`get_current_step_info`** (executor.py:595-689):
When mode is `"flow"`, resolve the step's inputs and create the child flow:

```python
if mode == "flow":
    child_state = None

    # Resume: if a child flow is tracked, try to restore it
    if state.active_child_flow_id:
        child_state = _flows.get(state.active_child_flow_id)
        if child_state is None:
            child_state = restore_flow(state.active_child_flow_id)
        if child_state is not None:
            _flows[child_state.flow_id] = child_state
        else:
            # Child is gone (crash between child completion and parent update).
            # Clear stale pointer — a new child will be created below.
            # The lost child's work is not recoverable; the flow re-executes
            # the sub-workflow from scratch. This matches the recovery model
            # for gate on_revise (clear and re-run, not error out).
            state.active_child_flow_id = None

    # Create: no existing child — resolve inputs and create fresh
    if child_state is None:
        resolved = resolve_inputs(step.inputs, state.inputs, state.step_outputs)
        child_state = create_flow_state(
            spec=state.spec,
            flow_name=step.flow_ref,
            inputs=resolved,
            raw_spec=state.raw_spec,
        )
        child_state.parent_flow_id = state.flow_id
        child_state.parent_step_id = step.id
        _flows[child_state.flow_id] = child_state
        state.active_child_flow_id = child_state.flow_id
        persist_flow(child_state)
        persist_flow(state)

    # Get child's current step (first step if new, resumed step if restored)
    child_step = get_current_step_info(child_state)

    return {
        "status": "execute_flow",
        "parent_flow_id": state.flow_id,
        "parent_step_id": step.id,
        "child_flow_id": child_state.flow_id,
        "child_flow_name": step.flow_ref,
        "child_step": child_step,
        "step_number": state.current_idx + 1,
        "total_steps": len(state.ordered_steps),
    }
```

**`process_step_result`** (executor.py:692-775):
When mode is `"flow"`, the result is the child flow's **unwrapped output** (see
server-side unwrap below). The ensure expressions see the child's output directly,
not wrapped in `{"status": "complete", "output": ...}`.

```python
elif mode == "flow":
    ensure_exprs = step.step_ensure or []
    max_retries = step.step_retries or 1
    output_schema = None
    fn_name = ""
```

This is identical to the `inline` branch. The flow_ref step's `step_ensure`
evaluates against the unwrapped child output — e.g., `result.clean == true`
works when the child's last step returned `{"clean": true}`.

On completion, clear `active_child_flow_id`:

```python
# In the success path, after recording the step:
if mode == "flow":
    state.active_child_flow_id = None
```

This is also done in `_clear_from` — if a flow_ref step is being re-driven
(via `on_fail` or `next` routing back), `active_child_flow_id` is cleared
so a fresh child is created on re-dispatch.

#### Server Changes

**`stratum_step_done`** (server.py:120-217):
- When `process_step_result` returns `"on_fail_routed"`: same handling as `"ok"` —
  call `get_current_step_info()`, return the next step. Include `routed_from` and
  `violations` in the response for transparency.

- When `get_current_step_info` returns `{"status": "execute_flow", ...}`: pass through
  to Claude Code. The response tells Claude Code which child flow to drive.

- **Flow step result unwrapping (critical contract):** When Claude Code calls
  `stratum_step_done` on a parent flow for a flow_ref step, the server unwraps
  the child payload before calling `process_step_result`. Two steps:

  **Step 1 — Build full child audit snapshot.** The child completion payload from
  `stratum_step_done` only includes the active-round `trace`. It does NOT include
  `rounds`, `iterations`, or `archived_iterations`. To capture the full child
  audit (including ENG-4 history), the server builds the snapshot from the child's
  FlowState before it is deleted:

  ```python
  step = state.ordered_steps[state.current_idx]
  if _step_mode(step) == "flow":
      child_flow_id = state.active_child_flow_id
      child_state = _flows.get(child_flow_id)
      # Build full audit snapshot (same shape as stratum_audit response)
      child_audit = _build_audit_snapshot(child_state) if child_state else None
  ```

  `_build_audit_snapshot(state)` is a new helper extracted from `stratum_audit`,
  returning:
  ```python
  {
      "flow_id": state.flow_id,
      "flow_name": state.flow_name,
      "status": flow_status,
      "trace": [dataclasses.asdict(r) for r in state.records],
      "rounds": [{"round": i, "steps": r} for i, r in enumerate(state.rounds)],
      "iterations": { ... },           # same shape as stratum_audit
      "archived_iterations": [ ... ],  # same shape as stratum_audit
      "total_duration_ms": total_ms,
  }
  ```

  This snapshot is captured *before* the child flow is deleted, so rounds and
  iteration history are preserved even for multi-round child flows.

  **Step 2 — Unwrap and process.** Extract `output` from the child payload.
  On success the child payload has `output`; on failure it does not. Unwrap rule:
  use `result["output"]` if present, otherwise `None` — never fall back to the
  raw envelope.

  ```python
      actual_result = result.get("output")  # None when child failed
      status, violations = process_step_result(state, step_id, actual_result)
  ```

  This ensures `ensure: ["result.clean == true"]` works when the child's last step
  returned `{"clean": true}` — the parent never sees the `{"status": "complete", ...}`
  wrapper. On child failure, `actual_result` is `None`, so any parent `ensure`
  expression will fail (as expected), triggering `on_fail` or `retries_exhausted`.

- **Child audit attached to parent record.** The full child audit snapshot is not
  stored on individual `StepRecord`s (which may not exist during intermediate retries).
  Instead, it is accumulated on FlowState:

  ```python
  # FlowState addition:
  child_audits: dict[str, list[dict]] = field(default_factory=dict)
  # Maps step_id → list of child audit snapshots (one per attempt)
  ```

  On every flow step completion (success or failure, intermediate or final):
  ```python
  if child_audit is not None:
      state.child_audits.setdefault(step_id, []).append(child_audit)
  ```

  This handles the case where a flow_ref step has retries: each child attempt's
  audit is preserved in the list, regardless of whether a `StepRecord` exists yet.
  On final `StepRecord` creation (success or exhaustion), the record's
  `child_flow_id` points to the last child, and `stratum_audit` includes the full
  `child_audits` from FlowState.

- **Failure path trace capture.** When the child fails (`retries_exhausted` with no
  `on_fail`), the server still builds the full audit snapshot from the child's
  FlowState before deletion. The snapshot is appended to
  `state.child_audits[step_id]`. This ensures the child's audit trail (including
  rounds and iterations) is preserved on both success and failure paths, and across
  intermediate retries of the parent flow_ref step.

**`stratum_plan`** (server.py:85-111):
No changes needed. Child flows are created by `get_current_step_info`, not by
`stratum_plan`. (Alternatively, Claude Code could call `stratum_plan` for the child,
but auto-creation is simpler and doesn't require spec re-parsing.)

**`stratum_audit`** (server.py:218-280):
Extract `_build_audit_snapshot(state)` from the existing `stratum_audit` handler
(both use the same shape). Add `child_audits` to the audit response:

```python
return {
    ...existing fields...,
    "child_audits": state.child_audits,  # step_id → [full audit snapshots]
}
```

Each entry in `child_audits` is a full audit snapshot (same shape as
`stratum_audit` output), preserving rounds, iterations, and archived_iterations
from the child flow.

#### Child Flow Lifecycle

1. Parent reaches flow_ref step → `get_current_step_info` creates child, returns
   `execute_flow`
2. Claude Code drives child via `stratum_step_done(child_flow_id, step_id, result)`
3. Child's last step completes → `get_current_step_info` returns `None` (flow complete)
4. Claude Code calls `stratum_step_done(parent_flow_id, parent_step_id, child_result)`
5. Parent's `process_step_result` validates `step_ensure`, advances

**What is `child_result`?** When the child flow completes, `stratum_step_done`
returns `{"status": "complete", "output": ..., "trace": [...]}` (server.py:208-214).
Claude Code passes this entire payload as the result to `stratum_step_done` on the
parent. The **server** unwraps it: `process_step_result` receives only `output`
(the child's last step output). The full child audit (including rounds, iterations,
archived_iterations) is built from the child's FlowState and accumulated in
`state.child_audits[step_id]`. Ensure expressions on the parent flow_ref step
evaluate against the unwrapped output directly — `result.clean == true` works when
the child returned `{"clean": true}`.

**Child flow gates.** If the child flow contains gate steps, they work normally —
`get_current_step_info` returns `await_gate`, Claude Code calls
`stratum_gate_resolve`. The parent stays paused.

**Child flow failure.** If a child step exhausts retries (and has no `on_fail`),
`stratum_step_done` returns `{"status": "error", "error_type": "retries_exhausted",
...}`. Claude Code passes this payload to `stratum_step_done` on the parent.
The server builds the full child audit snapshot from the child's FlowState (before
deletion) and appends it to `state.child_audits[step_id]`. Then it unwraps the
result and passes only `output` to `process_step_result`. The parent's `step_ensure`
evaluates against the unwrapped result — which will likely fail, triggering `on_fail`
routing or `retries_exhausted` on the parent. The child's complete audit trail
(including rounds and iteration history) is preserved on both success and failure
paths, and across intermediate retries of the parent flow_ref step.

**Persistence and restart recovery.**
- Child flows persist to `~/.stratum/flows/{child_flow_id}.json` while running.
- The parent flow stores `active_child_flow_id` on its FlowState (persisted).
- When a child completes (success or failure), the server builds the full audit
  snapshot via `_build_audit_snapshot(child_state)` and appends it to
  `state.child_audits[step_id]` before deleting the child's persisted flow.
  The parent owns the complete audit trail — no reliance on child persistence.
- On server restart mid-child: the parent restores with `active_child_flow_id` set.
  `get_current_step_info` on the parent checks if that child flow still exists in
  `_flows` or on disk. If yes, returns `execute_flow` pointing to the existing child
  (no duplicate creation). If the child's persisted flow is gone (crash between child
  completion and parent update), the stale pointer is cleared and a new child is
  created from scratch. The lost child's work is not recoverable — the sub-workflow
  re-executes. This matches the recovery model for gate `on_revise` (clear and
  re-run, not error out).

#### StepRecord Addition

```python
@dataclass
class StepRecord:
    ...
    child_flow_id: str | None = None   # last child flow_id (for cross-reference)
```

Child audit data lives on FlowState, not StepRecord. This avoids the problem of
intermediate retries having no StepRecord to attach to.

#### FlowState Additions (complete)

```python
parent_flow_id: str | None = None        # set on child flows
parent_step_id: str | None = None        # which parent step spawned this
active_child_flow_id: str | None = None  # set on parent when child is running
child_audits: dict[str, list[dict]] = field(default_factory=dict)
    # Maps step_id → list of full child audit snapshots (one per attempt).
    # Survives retries — each child attempt is appended regardless of
    # whether the parent step ultimately succeeds or fails.
    # Included in stratum_audit output under "child_audits".
```

## File Change Summary

| File | Change | Scope |
|------|--------|-------|
| `spec.py` | Fix `on_fail` validator: check `fn_def.ensure` for function steps | ~5 lines |
| `executor.py` | `_step_mode`: return `"flow"` for flow_ref | 3 lines |
| `executor.py` | `_find_step_idx` + `_clear_from(preserve=)` helpers (incl. iteration cleanup) | ~30 lines |
| `executor.py` | `process_step_result`: `on_fail` routing | ~15 lines |
| `executor.py` | `process_step_result`: `next` routing | ~5 lines |
| `executor.py` | `process_step_result`: `flow` mode branch | ~5 lines |
| `executor.py` | `get_current_step_info`: `flow` dispatch with idempotency | ~35 lines |
| `executor.py` | `FlowState`: `parent_flow_id`, `parent_step_id`, `active_child_flow_id`, `child_audits` | 4 lines |
| `executor.py` | `StepRecord`: `child_flow_id` | 1 line |
| `executor.py` | `resolve_gate`: refactor to use `_clear_from` | net -5 lines |
| `executor.py` | `persist_flow` / `restore_flow`: new fields | ~10 lines |
| `server.py` | `stratum_step_done`: `on_fail_routed` handling | ~10 lines |
| `server.py` | `stratum_step_done`: `execute_flow` passthrough | ~10 lines |
| `server.py` | `_build_audit_snapshot` helper (extracted from `stratum_audit`) | ~20 lines |
| `server.py` | `stratum_step_done`: flow step unwrap + audit snapshot (success + failure + retries) | ~30 lines |
| `server.py` | `stratum_audit`: include `child_audits` from FlowState | ~5 lines |

**New test files:**
| File | Coverage |
|------|----------|
| `tests/integration/test_routing.py` | `on_fail` and `next` routing |
| `tests/integration/test_flow_composition.py` | `flow_ref` sub-execution |

## Edge Cases

1. **on_fail target also fails** — follows its own retry/on_fail chain. No special handling.
2. **next creates a loop** — bounded by target step's `retries` or `max_iterations`.
3. **Child flow hits a gate** — works normally; parent stays paused.
4. **Child flow fails** — Claude Code propagates failure to parent step.
5. **Nested flow_ref** — child flow can itself have flow_ref steps (grandchild). Recursion is
   prevented by semantic validation (`_check_recursive_flow_refs` in spec.py:517-534).
6. **on_fail + next interaction** — a step can have both. `on_fail` fires on ensure failure;
   `next` fires on success. They're mutually exclusive paths.
7. **Server restart mid-child** — parent persists with `active_child_flow_id` set. Child persists
   separately. On restore, `get_current_step_info` checks `active_child_flow_id` — if the child
   exists on disk, resumes it; if not (crash between child completion and parent update), clears
   the stale pointer and creates a fresh child. Sub-workflow re-executes from scratch.

## Verification

1. Run existing test suite: `cd stratum-mcp && pytest` (378+ tests, all should pass)
2. New routing tests: `on_fail` routes on ensure failure, `next` routes on success,
   loop terminates on retries exhaustion, cascading `on_fail`
3. New composition tests: child flow creation, child step execution, child completion
   propagates to parent, child gate works, child failure propagates
4. Integration: write a review-fix spec (from STRAT-1 design), execute end-to-end
