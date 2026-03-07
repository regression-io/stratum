# STRAT-ENG-5: Implementation Plan

**Date:** 2026-03-07
**Design:** [design.md](design.md)
**Codebase:** `/Users/ruze/reg/my/forge/stratum/stratum-mcp/`

## Task Order

Tasks are sequential — each builds on the previous. TDD: write test first, watch
fail, implement, watch pass.

---

### Task 1: Fix `on_fail` validator for function steps

**File:** `src/stratum_mcp/spec.py` (existing)

The validator at line 732 rejects `on_fail` on function steps because it only checks
`step.step_ensure`, not the function's `fn_def.ensure`.

- [ ] Change the `on_fail` requires-ensure check (line 732-736) to also accept
      function steps whose `fn_def` has non-empty `ensure`
- [ ] Add test: function step with `on_fail` + function-level ensure passes validation
- [ ] Add test: function step with `on_fail` but no ensure (step or function) still rejected
- [ ] Existing tests pass

**Pattern:** Follow existing semantic validation structure in `_validate_semantics()`.
The function step branch (line 622) already resolves `fn_def = spec.functions[step.function]`
for gate checks — the `on_fail` check in the common section (line 732) needs to be
aware of the step mode.

**Test file:** `tests/contracts/test_ir_schema.py` (existing) or
`tests/contracts/test_ir_v02_extensions.py` (existing)

---

### Task 2: Extract `_find_step_idx` and `_clear_from` helpers

**File:** `src/stratum_mcp/executor.py` (existing)

Extract reusable routing helpers, then refactor `resolve_gate` on_revise to use them.

- [ ] Add `_find_step_idx(state, target_id) -> int` — find step index by id, raise
      `MCPExecutionError` if not found
- [ ] Add `_clear_from(state, target_idx, preserve=None)` — clear `step_outputs`,
      `attempts`, `iteration_outcome`, `iterations`, `active_iteration`,
      `active_child_flow_id` for steps at `target_idx` onward, minus `preserve` set
- [ ] Refactor `resolve_gate` on_revise (lines 903-911) to use `_clear_from` —
      archive rounds/iterations first, then call `_clear_from`, then clear `records`
      and increment round
- [ ] All existing tests pass (378+) — this is a pure refactor

**Test:** No new tests needed — existing gate_revise tests cover the refactored path.
Run full suite to verify.

---

### Task 3: Implement `on_fail` routing in `process_step_result`

**File:** `src/stratum_mcp/executor.py` (existing)

- [ ] In the `retries_exhausted` branch (line 766-770): when `step.on_fail` is set,
      store output, call `_clear_from(target_idx, preserve={step_id})`, set
      `current_idx`, return `("on_fail_routed", violations)`
- [ ] Same routing for schema validation exhaustion (line 747-752)
- [ ] Test: step with `on_fail` routes on ensure failure after retries exhausted
- [ ] Test: failed step's output is accessible via `$.steps.<id>.output` on the target
- [ ] Test: backward `on_fail` (target before failed step) preserves failed output
- [ ] Test: cascading `on_fail` — target step also has `on_fail`, both fire
- [ ] Test: step without `on_fail` still returns `retries_exhausted` (unchanged)
- [ ] Test: schema validation failure with `on_fail` routes correctly

**Test file:** `tests/integration/test_routing.py` (new)

---

### Task 4: Implement `on_fail_routed` handling in server

**File:** `src/stratum_mcp/server.py` (existing)

- [ ] In `stratum_step_done` (line 157): add `on_fail_routed` branch — same as `"ok"`
      path (call `get_current_step_info`, apply policy loop, persist, return next step)
- [ ] Include `routed_from` step_id and `violations` in the response for transparency
- [ ] Test: `stratum_step_done` returns next step info when `on_fail` fires
- [ ] Test: response includes `routed_from` and `violations`

**Test file:** `tests/integration/test_routing.py` (existing from task 3)

---

### Task 5: Implement `next` routing in `process_step_result`

**File:** `src/stratum_mcp/executor.py` (existing)

- [ ] In the success path (line 772-775): when `step.next` is set, call
      `_find_step_idx`, `_clear_from(target_idx)`, set `current_idx` instead of `+= 1`
- [ ] Test: step with `next` routes to target on success
- [ ] Test: backward `next` creates a loop — re-executes target with fresh attempts
- [ ] Test: `next` loop terminates when target step's ensure passes (no more routing)
- [ ] Test: review→fix→review loop (combined `on_fail` + `next`) works end-to-end
- [ ] Test: step without `next` still advances linearly (unchanged)

**Test file:** `tests/integration/test_routing.py` (existing from task 3)

---

### Task 6: Add FlowState and StepRecord fields for flow composition

**File:** `src/stratum_mcp/executor.py` (existing)

- [ ] Add `parent_flow_id: str | None = None` to `FlowState`
- [ ] Add `parent_step_id: str | None = None` to `FlowState`
- [ ] Add `active_child_flow_id: str | None = None` to `FlowState`
- [ ] Add `child_audits: dict[str, list[dict]] = field(default_factory=dict)` to
      `FlowState`
- [ ] Add `child_flow_id: str | None = None` to `StepRecord`
- [ ] Update `persist_flow` to serialize new fields
- [ ] Update `restore_flow` to deserialize new fields
- [ ] Update `_step_mode` to return `"flow"` for `flow_ref` steps (remove error)
- [ ] Test: new fields are persisted and restored correctly
- [ ] Test: `_step_mode` returns `"flow"` for flow_ref step

**Test file:** `tests/integration/test_flow_composition.py` (new)

---

### Task 7: Extract `_build_audit_snapshot` helper

**File:** `src/stratum_mcp/server.py` (existing)

- [ ] Extract the audit-building logic from `stratum_audit` (lines 246-275) into
      `_build_audit_snapshot(state) -> dict` — returns full audit shape including
      `trace`, `rounds`, `iterations`, `archived_iterations`
- [ ] Refactor `stratum_audit` to call `_build_audit_snapshot`
- [ ] Add `child_audits` field to the audit response: `state.child_audits`
- [ ] All existing tests pass
- [ ] Test: `stratum_audit` response includes `child_audits` key (empty dict when no
      flow_ref steps)
- [ ] Test: `_build_audit_snapshot` returns same shape as `stratum_audit` response
      (trace, rounds, iterations, archived_iterations all present)

**Test file:** `tests/integration/test_flow_composition.py` (existing from task 6)

---

### Task 8: Implement `flow:` dispatch in `get_current_step_info`

**File:** `src/stratum_mcp/executor.py` (existing)

- [ ] In `get_current_step_info`, when `mode == "flow"`:
  - Check `active_child_flow_id` — try `_flows` then `restore_flow`
  - If child exists: reuse it
  - If `active_child_flow_id` set but child gone: clear pointer (stale crash recovery)
  - If no child: resolve inputs, create child FlowState, set `active_child_flow_id`,
    persist both
  - Get child's current step via `get_current_step_info(child_state)`
  - Return `{"status": "execute_flow", "parent_flow_id", "parent_step_id",
    "child_flow_id", "child_flow_name", "child_step", ...}`
- [ ] Test: flow_ref step creates child flow and returns `execute_flow` status
- [ ] Test: child flow inputs resolved from parent step's `inputs` dict
- [ ] Test: idempotent — calling again returns same child (no duplicate)
- [ ] Test: stale `active_child_flow_id` cleared on missing child, new child created

**Test file:** `tests/integration/test_flow_composition.py` (existing from task 6)

---

### Task 9: Implement flow step unwrap + audit in server

**File:** `src/stratum_mcp/server.py` (existing)

- [ ] In `stratum_step_done`, detect flow_ref step (`_step_mode(step) == "flow"`):
  - Build child audit snapshot via `_build_audit_snapshot(child_state)` before deletion
  - Append snapshot to `state.child_audits[step_id]`
  - Unwrap: `actual_result = result.get("output")` — `None` when child failed
  - Call `process_step_result(state, step_id, actual_result)`
  - On success: clear `active_child_flow_id`, delete child from `_flows` and disk
  - On ensure_failed (retries remain): delete child from `_flows` and disk (next
    retry creates a new child)
  - On `on_fail_routed`: clear `active_child_flow_id`, delete child from `_flows`
    and disk before routing to recovery step (child is consumed, parent moves on)
  - Handle `execute_flow` response from `get_current_step_info` (pass through)
- [ ] Test: child success — parent receives unwrapped output, advances
- [ ] Test: child failure — parent receives `None`, ensure fails as expected
- [ ] Test: child audit snapshot includes rounds and iterations
- [ ] Test: intermediate retry — child audit preserved in `child_audits` accumulator
- [ ] Test: `on_fail_routed` on flow_ref step — child cleaned up, parent routes to recovery
- [ ] Test: `execute_flow` response passed through from `get_current_step_info`

**Test file:** `tests/integration/test_flow_composition.py` (existing from task 6)

---

### Task 10: End-to-end review-fix loop test

**Files:** `tests/integration/test_flow_composition.py` (existing from task 6)

- [ ] Write a spec with the review→fix→review pattern from the design doc:
      review (ensure: clean==true, on_fail: fix), fix (next: review)
- [ ] Drive it through `create_flow_state` + `get_current_step_info` +
      `process_step_result` loop
- [ ] First review fails → routes to fix → fix completes → routes to review →
      second review passes → flow completes
- [ ] Verify audit trail includes both review attempts and the fix
- [ ] Write a composed flow spec: parent with `flow: review_fix` step
- [ ] Drive parent through, verify child flow created, driven, result propagated
- [ ] Verify `stratum_audit` on parent includes `child_audits` with full snapshot

---

## Verification

After all tasks:

```bash
cd /Users/ruze/reg/my/forge/stratum/stratum-mcp
pytest                           # all tests pass (378+ existing + ~30 new)
pytest tests/integration/test_routing.py -v          # routing tests
pytest tests/integration/test_flow_composition.py -v # composition tests
```
