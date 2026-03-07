"""Integration tests for flow composition (STRAT-ENG-5, Tasks 6-10)."""
import asyncio
import textwrap

from stratum_mcp.executor import (
    FlowState,
    StepRecord,
    _step_mode,
    create_flow_state,
    get_current_step_info,
    process_step_result,
    persist_flow,
    restore_flow,
    delete_persisted_flow,
    commit_checkpoint,
    revert_checkpoint,
    _flows,
)
from stratum_mcp.server import stratum_audit, stratum_plan, stratum_step_done, _build_audit_snapshot
from stratum_mcp.spec import parse_and_validate


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


# ---------------------------------------------------------------------------
# Spec fixtures
# ---------------------------------------------------------------------------

_COMPOSED_SPEC = textwrap.dedent("""\
    version: "0.2"
    contracts:
      Out:
        v: {type: string}
    functions:
      work:
        mode: infer
        intent: "Do it"
        input: {}
        output: Out
    flows:
      child:
        input: {}
        output: Out
        steps:
          - id: c1
            function: work
            inputs: {}
      main:
        input: {}
        steps:
          - id: s1
            function: work
            inputs: {}
          - id: s2
            flow: child
            depends_on: [s1]
""")


# ---------------------------------------------------------------------------
# Task 6: FlowState and StepRecord fields, _step_mode, persistence
# ---------------------------------------------------------------------------

def test_flow_state_new_fields_default():
    """New FlowState fields have correct defaults."""
    spec = parse_and_validate(_COMPOSED_SPEC)
    state = create_flow_state(spec, "main", {})
    assert state.parent_flow_id is None
    assert state.parent_step_id is None
    assert state.active_child_flow_id is None
    assert state.child_audits == {}


def test_step_record_child_flow_id_default():
    """StepRecord.child_flow_id defaults to None."""
    rec = StepRecord(step_id="s1", function_name="work", attempts=1, duration_ms=100)
    assert rec.child_flow_id is None


def test_new_fields_persist_and_restore():
    """New FlowState fields survive persist/restore roundtrip."""
    spec = parse_and_validate(_COMPOSED_SPEC)
    state = create_flow_state(spec, "main", {}, raw_spec=_COMPOSED_SPEC)
    state.parent_flow_id = "parent-123"
    state.parent_step_id = "ps1"
    state.active_child_flow_id = "child-456"
    state.child_audits = {"s2": [{"trace": []}]}

    persist_flow(state)
    try:
        restored = restore_flow(state.flow_id)
        assert restored is not None
        assert restored.parent_flow_id == "parent-123"
        assert restored.parent_step_id == "ps1"
        assert restored.active_child_flow_id == "child-456"
        assert restored.child_audits == {"s2": [{"trace": []}]}
    finally:
        delete_persisted_flow(state.flow_id)


def test_step_mode_returns_flow_for_flow_ref():
    """_step_mode returns 'flow' for flow_ref steps."""
    spec = parse_and_validate(_COMPOSED_SPEC)
    step = spec.flows["main"].steps[1]  # s2 is flow_ref
    assert _step_mode(step) == "flow"


# ---------------------------------------------------------------------------
# Task 7: _build_audit_snapshot helper
# ---------------------------------------------------------------------------

def test_audit_includes_child_audits_key():
    """stratum_audit response includes child_audits key (empty dict when no flow_ref steps)."""
    spec = parse_and_validate(_COMPOSED_SPEC)
    state = create_flow_state(spec, "main", {}, raw_spec=_COMPOSED_SPEC)
    _flows[state.flow_id] = state
    try:
        result = _run(stratum_audit(state.flow_id, ctx=None))
        assert "child_audits" in result
        assert result["child_audits"] == {}
    finally:
        _flows.pop(state.flow_id, None)
        delete_persisted_flow(state.flow_id)


def test_build_audit_snapshot_shape():
    """_build_audit_snapshot returns same shape as stratum_audit (trace, rounds, iterations)."""
    spec = parse_and_validate(_COMPOSED_SPEC)
    state = create_flow_state(spec, "main", {})

    snapshot = _build_audit_snapshot(state)
    assert "trace" in snapshot
    assert "rounds" in snapshot
    assert "iterations" in snapshot
    assert "archived_iterations" in snapshot
    assert "child_audits" in snapshot
    assert isinstance(snapshot["trace"], list)
    assert isinstance(snapshot["rounds"], list)
    assert isinstance(snapshot["iterations"], dict)


# ---------------------------------------------------------------------------
# Task 8: flow: dispatch in get_current_step_info
# ---------------------------------------------------------------------------

def test_flow_ref_step_creates_child_flow():
    """flow_ref step creates child flow and returns execute_flow status."""
    spec = parse_and_validate(_COMPOSED_SPEC)
    state = create_flow_state(spec, "main", {}, raw_spec=_COMPOSED_SPEC)

    # Complete s1 first
    process_step_result(state, "s1", {"v": "done"})

    # s2 is flow_ref — should create child flow
    step_info = get_current_step_info(state)
    assert step_info["status"] == "execute_flow"
    assert step_info["parent_flow_id"] == state.flow_id
    assert step_info["parent_step_id"] == "s2"
    assert step_info["child_flow_name"] == "child"
    assert "child_flow_id" in step_info
    assert step_info["child_step"] is not None

    # Child flow should be in _flows
    child_id = step_info["child_flow_id"]
    assert child_id in _flows

    # Cleanup
    _flows.pop(child_id, None)
    delete_persisted_flow(child_id)


def test_flow_ref_child_inputs_resolved():
    """Child flow inputs resolved from parent step's inputs dict."""
    spec_with_inputs = textwrap.dedent("""\
        version: "0.2"
        contracts:
          Out:
            v: {type: string}
        functions:
          work:
            mode: infer
            intent: "Do it"
            input: {}
            output: Out
        flows:
          child:
            input:
              data: {type: string}
            output: Out
            steps:
              - id: c1
                function: work
                inputs: {}
          main:
            input: {}
            steps:
              - id: s1
                function: work
                inputs: {}
              - id: s2
                flow: child
                inputs:
                  data: "$.steps.s1.output.v"
                depends_on: [s1]
    """)
    spec = parse_and_validate(spec_with_inputs)
    state = create_flow_state(spec, "main", {}, raw_spec=spec_with_inputs)

    process_step_result(state, "s1", {"v": "hello"})
    step_info = get_current_step_info(state)

    assert step_info["status"] == "execute_flow"
    child_id = step_info["child_flow_id"]
    child_state = _flows[child_id]
    assert child_state.inputs == {"data": "hello"}

    # Cleanup
    _flows.pop(child_id, None)
    delete_persisted_flow(child_id)


def test_flow_ref_idempotent():
    """Calling get_current_step_info again returns same child (no duplicate)."""
    spec = parse_and_validate(_COMPOSED_SPEC)
    state = create_flow_state(spec, "main", {}, raw_spec=_COMPOSED_SPEC)

    process_step_result(state, "s1", {"v": "done"})

    info1 = get_current_step_info(state)
    child_id_1 = info1["child_flow_id"]

    info2 = get_current_step_info(state)
    child_id_2 = info2["child_flow_id"]

    assert child_id_1 == child_id_2

    # Cleanup
    _flows.pop(child_id_1, None)
    delete_persisted_flow(child_id_1)


def test_flow_ref_stale_child_cleared():
    """Stale active_child_flow_id cleared on missing child, new child created."""
    spec = parse_and_validate(_COMPOSED_SPEC)
    state = create_flow_state(spec, "main", {}, raw_spec=_COMPOSED_SPEC)

    process_step_result(state, "s1", {"v": "done"})

    # Create first child
    info1 = get_current_step_info(state)
    old_child_id = info1["child_flow_id"]

    # Simulate crash: remove child from _flows and disk
    _flows.pop(old_child_id, None)
    delete_persisted_flow(old_child_id)

    # active_child_flow_id is still set but child is gone
    assert state.active_child_flow_id == old_child_id

    # Should clear stale pointer and create new child
    info2 = get_current_step_info(state)
    new_child_id = info2["child_flow_id"]
    assert new_child_id != old_child_id
    assert state.active_child_flow_id == new_child_id

    # Cleanup
    _flows.pop(new_child_id, None)
    delete_persisted_flow(new_child_id)


# ---------------------------------------------------------------------------
# Task 9: Flow step unwrap + audit in server
# ---------------------------------------------------------------------------

def test_child_success_parent_receives_output():
    """Child success — parent receives unwrapped output, advances."""
    spec = parse_and_validate(_COMPOSED_SPEC)
    state = create_flow_state(spec, "main", {}, raw_spec=_COMPOSED_SPEC)
    _flows[state.flow_id] = state

    try:
        # Complete s1
        process_step_result(state, "s1", {"v": "done"})

        # Get child flow info
        step_info = get_current_step_info(state)
        child_id = step_info["child_flow_id"]

        # Complete child's step c1
        child_state = _flows[child_id]
        process_step_result(child_state, "c1", {"v": "child_result"})

        # Report child result to parent (as stratum_step_done would format it)
        child_result = {"status": "complete", "output": {"v": "child_result"}}
        # Call stratum_step_done on parent with child result
        r = _run(stratum_step_done(state.flow_id, "s2", child_result, ctx=None))

        # Parent should complete (s2 was the last step)
        assert r["status"] == "complete"
        assert r["output"] == {"v": "child_result"}

        # P1: child flow must be cleaned up from _flows and disk after success
        assert child_id not in _flows
        assert state.active_child_flow_id is None
    finally:
        _flows.pop(state.flow_id, None)
        delete_persisted_flow(state.flow_id)


def test_child_flow_id_on_step_record():
    """StepRecord.child_flow_id is set for flow_ref steps and survives restore."""
    spec = parse_and_validate(_COMPOSED_SPEC)
    state = create_flow_state(spec, "main", {}, raw_spec=_COMPOSED_SPEC)
    _flows[state.flow_id] = state

    try:
        process_step_result(state, "s1", {"v": "done"})
        step_info = get_current_step_info(state)
        child_id = step_info["child_flow_id"]
        child_state = _flows[child_id]
        process_step_result(child_state, "c1", {"v": "ok"})

        child_result = {"status": "complete", "output": {"v": "ok"}}
        _run(stratum_step_done(state.flow_id, "s2", child_result, ctx=None))

        # The s2 step record should have child_flow_id set
        flow_records = [r for r in state.records if hasattr(r, "child_flow_id")]
        s2_records = [r for r in flow_records if r.step_id == "s2"]
        assert len(s2_records) == 1
        assert s2_records[0].child_flow_id == child_id

        # Verify it survives persist/restore roundtrip
        persist_flow(state)
        restored = restore_flow(state.flow_id)
        assert restored is not None
        restored_s2 = [r for r in restored.records if hasattr(r, "child_flow_id") and r.step_id == "s2"]
        assert len(restored_s2) == 1
        assert restored_s2[0].child_flow_id == child_id
    finally:
        _flows.pop(state.flow_id, None)
        delete_persisted_flow(state.flow_id)


def test_child_failure_parent_receives_none():
    """Child failure — parent receives None, ensure fails as expected."""
    spec_with_ensure = textwrap.dedent("""\
        version: "0.2"
        contracts:
          Out:
            v: {type: string}
        functions:
          work:
            mode: infer
            intent: "Do it"
            input: {}
            output: Out
        flows:
          child:
            input: {}
            output: Out
            steps:
              - id: c1
                function: work
                inputs: {}
          main:
            input: {}
            steps:
              - id: s1
                function: work
                inputs: {}
              - id: s2
                flow: child
                depends_on: [s1]
                ensure:
                  - "result.v != ''"
    """)
    spec = parse_and_validate(spec_with_ensure)
    state = create_flow_state(spec, "main", {}, raw_spec=spec_with_ensure)
    _flows[state.flow_id] = state

    try:
        process_step_result(state, "s1", {"v": "done"})
        step_info = get_current_step_info(state)
        child_id = step_info["child_flow_id"]
        child_state = _flows[child_id]
        process_step_result(child_state, "c1", {"v": "ok"})

        # Child failed (no output key in result)
        child_result = {"status": "error", "message": "child failed"}
        r = _run(stratum_step_done(state.flow_id, "s2", child_result, ctx=None))

        # Parent should see retries_exhausted (result is None, ensure fails, retries=1)
        assert r["status"] == "error"
        assert r["error_type"] == "retries_exhausted"
    finally:
        _flows.pop(state.flow_id, None)
        delete_persisted_flow(state.flow_id)
        _flows.pop(child_id, None)
        delete_persisted_flow(child_id)


def test_child_audit_snapshot_preserved():
    """Child audit snapshot includes trace and is preserved in parent's child_audits."""
    spec = parse_and_validate(_COMPOSED_SPEC)
    state = create_flow_state(spec, "main", {}, raw_spec=_COMPOSED_SPEC)
    _flows[state.flow_id] = state

    try:
        process_step_result(state, "s1", {"v": "done"})
        step_info = get_current_step_info(state)
        child_id = step_info["child_flow_id"]
        child_state = _flows[child_id]
        process_step_result(child_state, "c1", {"v": "child_out"})

        child_result = {"status": "complete", "output": {"v": "child_out"}}
        _run(stratum_step_done(state.flow_id, "s2", child_result, ctx=None))

        # Parent should have child audit in child_audits
        assert "s2" in state.child_audits
        assert len(state.child_audits["s2"]) == 1
        audit = state.child_audits["s2"][0]
        assert "trace" in audit
        assert "rounds" in audit
        assert "iterations" in audit
    finally:
        _flows.pop(state.flow_id, None)
        delete_persisted_flow(state.flow_id)


def test_on_fail_routed_on_flow_ref_cleans_up_child():
    """on_fail_routed on flow_ref step — child cleaned up, parent routes to recovery."""
    spec_with_on_fail = textwrap.dedent("""\
        version: "0.2"
        contracts:
          Out:
            v: {type: string}
        functions:
          work:
            mode: infer
            intent: "Do it"
            input: {}
            output: Out
          recover:
            mode: infer
            intent: "Recover"
            input: {}
            output: Out
        flows:
          child:
            input: {}
            output: Out
            steps:
              - id: c1
                function: work
                inputs: {}
          main:
            input: {}
            steps:
              - id: s1
                function: work
                inputs: {}
              - id: s2
                flow: child
                depends_on: [s1]
                ensure:
                  - "result.v == 'good'"
                on_fail: s3
              - id: s3
                function: recover
                inputs: {}
                depends_on: [s2]
    """)
    spec = parse_and_validate(spec_with_on_fail)
    state = create_flow_state(spec, "main", {}, raw_spec=spec_with_on_fail)
    _flows[state.flow_id] = state

    try:
        process_step_result(state, "s1", {"v": "done"})
        step_info = get_current_step_info(state)
        child_id = step_info["child_flow_id"]
        child_state = _flows[child_id]
        process_step_result(child_state, "c1", {"v": "bad"})

        child_result = {"status": "complete", "output": {"v": "bad"}}
        r = _run(stratum_step_done(state.flow_id, "s2", child_result, ctx=None))

        # Should route to s3 via on_fail
        assert r.get("step_id") == "s3" or r.get("routed_from") == "s2"
        # Child should be cleaned up
        assert child_id not in _flows
        assert state.active_child_flow_id is None
    finally:
        _flows.pop(state.flow_id, None)
        delete_persisted_flow(state.flow_id)


def test_execute_flow_passed_through():
    """execute_flow response passed through from get_current_step_info."""
    result = _run(stratum_plan(spec=_COMPOSED_SPEC, flow="main", inputs={}, ctx=None))
    flow_id = result["flow_id"]
    try:
        # Complete s1
        r = _run(stratum_step_done(flow_id, "s1", {"v": "ok"}, ctx=None))
        # Next step is flow_ref — should get execute_flow
        assert r["status"] == "execute_flow"
        assert "child_flow_id" in r
        assert "child_step" in r

        # Cleanup child
        child_id = r["child_flow_id"]
        _flows.pop(child_id, None)
        delete_persisted_flow(child_id)
    finally:
        _flows.pop(flow_id, None)
        delete_persisted_flow(flow_id)


# ---------------------------------------------------------------------------
# Task 10: End-to-end review-fix loop test
# ---------------------------------------------------------------------------

_REVIEW_FIX_SPEC = textwrap.dedent("""\
    version: "0.2"
    contracts:
      ReviewOut:
        clean: {type: boolean}
        findings: {type: string}
      FixOut:
        fixed: {type: boolean}
    functions:
      review:
        mode: infer
        intent: "Review code"
        input: {}
        output: ReviewOut
        ensure:
          - "result.clean == True"
        retries: 3
      fix:
        mode: infer
        intent: "Fix issues"
        input: {}
        output: FixOut
    flows:
      review_fix:
        input: {}
        output: ReviewOut
        steps:
          - id: review
            function: review
            inputs: {}
            on_fail: fix
          - id: fix
            function: fix
            inputs:
              findings: "$.steps.review.output.findings"
            next: review
            depends_on: [review]
      main:
        input: {}
        steps:
          - id: impl
            function: fix
            inputs: {}
          - id: review_fix_step
            flow: review_fix
            depends_on: [impl]
""")


def test_review_fix_loop_e2e():
    """review→fix→review pattern: first fails, fix runs, second passes."""
    spec = parse_and_validate(_REVIEW_FIX_SPEC)
    state = create_flow_state(spec, "review_fix", {})

    # Step 1: review — ensure fails (3 retries to exhaust)
    info = get_current_step_info(state)
    assert info["step_id"] == "review"

    process_step_result(state, "review", {"clean": False, "findings": "bug1"})
    process_step_result(state, "review", {"clean": False, "findings": "bug2"})
    status, _ = process_step_result(state, "review", {"clean": False, "findings": "bug3"})
    assert status == "on_fail_routed"

    # Step 2: fix — succeeds, routes back to review via next
    info = get_current_step_info(state)
    assert info["step_id"] == "fix"
    assert info["inputs"]["findings"] == "bug3"
    status, _ = process_step_result(state, "fix", {"fixed": True})
    assert status == "ok"

    # Step 3: review (second attempt) — passes ensure
    info = get_current_step_info(state)
    assert info["step_id"] == "review"
    status, _ = process_step_result(state, "review", {"clean": True, "findings": ""})
    assert status == "ok"

    # Verify audit trail
    assert len(state.records) == 3  # 2 review records + 1 fix record
    step_ids = [r.step_id for r in state.records]
    assert step_ids.count("review") == 2
    assert step_ids.count("fix") == 1


def test_composed_flow_e2e():
    """Parent with flow: review_fix step — child created, driven, result propagated."""
    spec = parse_and_validate(_REVIEW_FIX_SPEC)
    state = create_flow_state(spec, "main", {}, raw_spec=_REVIEW_FIX_SPEC)
    _flows[state.flow_id] = state

    try:
        # Step 1: impl
        info = get_current_step_info(state)
        assert info["step_id"] == "impl"
        process_step_result(state, "impl", {"fixed": True})

        # Step 2: review_fix_step (flow_ref) — creates child
        info = get_current_step_info(state)
        assert info["status"] == "execute_flow"
        child_id = info["child_flow_id"]
        child_state = _flows[child_id]

        # Drive child: review fails → fix → review passes
        process_step_result(child_state, "review", {"clean": False, "findings": "bug"})
        process_step_result(child_state, "review", {"clean": False, "findings": "bug"})
        process_step_result(child_state, "review", {"clean": False, "findings": "bug"})
        process_step_result(child_state, "fix", {"fixed": True})
        process_step_result(child_state, "review", {"clean": True, "findings": ""})

        # Child is complete — report to parent
        child_result = {"status": "complete", "output": {"clean": True, "findings": ""}}
        r = _run(stratum_step_done(state.flow_id, "review_fix_step", child_result, ctx=None))

        # Parent completes
        assert r["status"] == "complete"
        assert r["output"] == {"clean": True, "findings": ""}

        # Verify parent has child_audits
        assert "review_fix_step" in state.child_audits
        child_audit = state.child_audits["review_fix_step"][0]
        assert "trace" in child_audit
        assert len(child_audit["trace"]) == 3  # 2 review + 1 fix records
    finally:
        _flows.pop(state.flow_id, None)
        delete_persisted_flow(state.flow_id)
        _flows.pop(child_id, None)
        delete_persisted_flow(child_id)


def test_composed_flow_audit_includes_child_audits():
    """stratum_audit on parent includes child_audits with full snapshot."""
    spec = parse_and_validate(_REVIEW_FIX_SPEC)
    state = create_flow_state(spec, "main", {}, raw_spec=_REVIEW_FIX_SPEC)
    _flows[state.flow_id] = state

    try:
        # Drive parent through impl
        process_step_result(state, "impl", {"fixed": True})

        # Get child flow info and drive child to completion
        info = get_current_step_info(state)
        child_id = info["child_flow_id"]
        child_state = _flows[child_id]

        # Quick child completion (review passes first try)
        process_step_result(child_state, "review", {"clean": True, "findings": ""})

        # Report child result to parent
        child_result = {"status": "complete", "output": {"clean": True, "findings": ""}}
        _run(stratum_step_done(state.flow_id, "review_fix_step", child_result, ctx=None))

        # Check stratum_audit
        audit = _run(stratum_audit(state.flow_id, ctx=None))
        assert "child_audits" in audit
        assert "review_fix_step" in audit["child_audits"]
        snapshot = audit["child_audits"]["review_fix_step"][0]
        assert snapshot["flow_name"] == "review_fix"
        assert "trace" in snapshot
        assert "rounds" in snapshot
        assert "iterations" in snapshot
    finally:
        _flows.pop(state.flow_id, None)
        delete_persisted_flow(state.flow_id)
        _flows.pop(child_id, None)
        delete_persisted_flow(child_id)


# ---------------------------------------------------------------------------
# Checkpoint roundtrip for flow-composition state
# ---------------------------------------------------------------------------

def test_checkpoint_preserves_composition_state():
    """commit/revert checkpoint preserves active_child_flow_id and child_audits."""
    spec = parse_and_validate(_COMPOSED_SPEC)
    state = create_flow_state(spec, "main", {}, raw_spec=_COMPOSED_SPEC)

    # Simulate mid-composition state
    state.active_child_flow_id = "child-abc"
    state.child_audits = {"s2": [{"trace": [{"step_id": "c1"}]}]}

    commit_checkpoint(state, "mid")

    # Mutate after checkpoint
    state.active_child_flow_id = "child-xyz"
    state.child_audits = {}

    assert revert_checkpoint(state, "mid")
    assert state.active_child_flow_id == "child-abc"
    assert state.child_audits == {"s2": [{"trace": [{"step_id": "c1"}]}]}

    delete_persisted_flow(state.flow_id)
