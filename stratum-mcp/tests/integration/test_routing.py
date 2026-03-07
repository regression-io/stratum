"""Integration tests for on_fail and next routing (STRAT-ENG-5, Tasks 3-5)."""
import asyncio
import textwrap

from stratum_mcp.executor import (
    create_flow_state,
    get_current_step_info,
    process_step_result,
    _flows,
    delete_persisted_flow,
)
from stratum_mcp.server import stratum_plan, stratum_step_done
from stratum_mcp.spec import parse_and_validate


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


# ---------------------------------------------------------------------------
# Spec fixtures
# ---------------------------------------------------------------------------

_ON_FAIL_SPEC = textwrap.dedent("""\
    version: "0.2"
    contracts:
      ReviewOut:
        clean: {type: boolean}
        findings: {type: string}
    functions:
      review:
        mode: infer
        intent: "Review code"
        input: {}
        output: ReviewOut
        ensure:
          - "result.clean == True"
        retries: 2
      fix:
        mode: infer
        intent: "Fix issues"
        input: {}
        output: ReviewOut
    flows:
      main:
        input: {}
        steps:
          - id: review
            function: review
            inputs: {}
            on_fail: fix
          - id: fix
            function: fix
            inputs:
              findings: "$.steps.review.output.findings"
""")

_ON_FAIL_BACKWARD_SPEC = textwrap.dedent("""\
    version: "0.2"
    contracts:
      Out:
        ok: {type: boolean}
        data: {type: string}
    functions:
      step_a:
        mode: infer
        intent: "First step"
        input: {}
        output: Out
      step_b:
        mode: infer
        intent: "Second step"
        input: {}
        output: Out
      step_c:
        mode: infer
        intent: "Third step"
        input: {}
        output: Out
        ensure:
          - "result.ok == True"
        retries: 2
    flows:
      main:
        input: {}
        steps:
          - id: a
            function: step_a
            inputs: {}
          - id: b
            function: step_b
            inputs: {}
            depends_on: [a]
          - id: c
            function: step_c
            inputs: {}
            depends_on: [b]
            on_fail: a
""")

_CASCADE_SPEC = textwrap.dedent("""\
    version: "0.2"
    contracts:
      Out:
        ok: {type: boolean}
    functions:
      s1_fn:
        mode: infer
        intent: "Step 1"
        input: {}
        output: Out
        ensure:
          - "result.ok == True"
        retries: 2
      s2_fn:
        mode: infer
        intent: "Step 2"
        input: {}
        output: Out
        ensure:
          - "result.ok == True"
        retries: 2
      s3_fn:
        mode: infer
        intent: "Step 3"
        input: {}
        output: Out
    flows:
      main:
        input: {}
        steps:
          - id: s1
            function: s1_fn
            inputs: {}
            on_fail: s2
          - id: s2
            function: s2_fn
            inputs: {}
            on_fail: s3
          - id: s3
            function: s3_fn
            inputs: {}
""")

_NO_ON_FAIL_SPEC = textwrap.dedent("""\
    version: "0.2"
    contracts:
      Out:
        ok: {type: boolean}
    functions:
      work:
        mode: infer
        intent: "Do work"
        input: {}
        output: Out
        ensure:
          - "result.ok == True"
        retries: 2
    flows:
      main:
        input: {}
        steps:
          - id: s1
            function: work
            inputs: {}
""")

_SCHEMA_ON_FAIL_SPEC = textwrap.dedent("""\
    version: "0.2"
    contracts:
      Out:
        value: {type: integer}
    functions:
      produce:
        mode: infer
        intent: "Produce output"
        input: {}
        output: Out
        retries: 2
      recover:
        mode: infer
        intent: "Recover"
        input: {}
        output: Out
    flows:
      main:
        input: {}
        steps:
          - id: s1
            function: produce
            inputs: {}
            on_fail: s2
            output_schema:
              type: object
              properties:
                value:
                  type: integer
              required: [value]
          - id: s2
            function: recover
            inputs: {}
""")


# ---------------------------------------------------------------------------
# Task 3: on_fail routing tests
# ---------------------------------------------------------------------------

def test_on_fail_routes_on_ensure_failure():
    """Step with on_fail routes to target when ensure fails after retries exhausted."""
    spec = parse_and_validate(_ON_FAIL_SPEC)
    state = create_flow_state(spec, "main", {})

    # First attempt: ensure fails (clean != True), retries remain
    status, violations = process_step_result(state, "review", {"clean": False, "findings": "bug"})
    assert status == "ensure_failed"

    # Second attempt: ensure still fails, retries exhausted, on_fail fires
    status, violations = process_step_result(state, "review", {"clean": False, "findings": "bug"})
    assert status == "on_fail_routed"
    assert len(violations) > 0

    # current_idx should now point to "fix" step
    fix_step = state.ordered_steps[state.current_idx]
    assert fix_step.id == "fix"


def test_on_fail_failed_output_accessible():
    """Failed step's output is accessible via $.steps.<id>.output on the target."""
    spec = parse_and_validate(_ON_FAIL_SPEC)
    state = create_flow_state(spec, "main", {})

    # Exhaust retries to trigger on_fail
    process_step_result(state, "review", {"clean": False, "findings": "bug found"})
    process_step_result(state, "review", {"clean": False, "findings": "bug found"})

    # The failed step's output should be stored
    assert "review" in state.step_outputs
    assert state.step_outputs["review"]["findings"] == "bug found"

    # The fix step should be able to resolve its inputs from the failed output
    step_info = get_current_step_info(state)
    assert step_info["step_id"] == "fix"
    assert step_info["inputs"]["findings"] == "bug found"


def test_on_fail_backward_preserves_failed_output():
    """Backward on_fail (target before failed step) preserves failed step's output."""
    spec = parse_and_validate(_ON_FAIL_BACKWARD_SPEC)
    state = create_flow_state(spec, "main", {})

    # Complete steps a and b normally
    process_step_result(state, "a", {"ok": True, "data": "a_data"})
    process_step_result(state, "b", {"ok": True, "data": "b_data"})

    # Step c fails ensure, exhausts retries, on_fail routes back to a
    process_step_result(state, "c", {"ok": False, "data": "c_data"})
    status, _ = process_step_result(state, "c", {"ok": False, "data": "c_data"})
    assert status == "on_fail_routed"

    # current_idx should point to step a
    assert state.ordered_steps[state.current_idx].id == "a"

    # Step c's output should still be accessible (preserved by _clear_from)
    assert "c" in state.step_outputs
    assert state.step_outputs["c"]["data"] == "c_data"

    # Steps a and b outputs should be cleared (they're in the clear range)
    assert "a" not in state.step_outputs
    assert "b" not in state.step_outputs


def test_cascading_on_fail():
    """Cascading on_fail — target step also has on_fail, both fire sequentially."""
    spec = parse_and_validate(_CASCADE_SPEC)
    state = create_flow_state(spec, "main", {})

    # s1 fails ensure, routes to s2
    process_step_result(state, "s1", {"ok": False})
    status, _ = process_step_result(state, "s1", {"ok": False})
    assert status == "on_fail_routed"
    assert state.ordered_steps[state.current_idx].id == "s2"

    # s2 also fails ensure, routes to s3
    process_step_result(state, "s2", {"ok": False})
    status, _ = process_step_result(state, "s2", {"ok": False})
    assert status == "on_fail_routed"
    assert state.ordered_steps[state.current_idx].id == "s3"


def test_no_on_fail_still_returns_retries_exhausted():
    """Step without on_fail still returns retries_exhausted (unchanged behavior)."""
    spec = parse_and_validate(_NO_ON_FAIL_SPEC)
    state = create_flow_state(spec, "main", {})

    process_step_result(state, "s1", {"ok": False})
    status, violations = process_step_result(state, "s1", {"ok": False})
    assert status == "retries_exhausted"
    assert len(violations) > 0


def test_schema_failure_with_on_fail_routes():
    """Schema validation failure with on_fail routes correctly."""
    spec = parse_and_validate(_SCHEMA_ON_FAIL_SPEC)
    state = create_flow_state(spec, "main", {})

    # First attempt: schema fails (wrong type), retries remain
    status, errors = process_step_result(state, "s1", {"value": "not_an_int"})
    assert status == "schema_failed"

    # Second attempt: schema still fails, retries exhausted, on_fail fires
    status, errors = process_step_result(state, "s1", {"value": "still_not_int"})
    assert status == "on_fail_routed"
    assert state.ordered_steps[state.current_idx].id == "s2"


# ---------------------------------------------------------------------------
# Task 4: on_fail_routed handling in server (stratum_step_done)
# ---------------------------------------------------------------------------

def test_step_done_on_fail_returns_next_step():
    """stratum_step_done returns next step info when on_fail fires."""
    result = _run(stratum_plan(spec=_ON_FAIL_SPEC, flow="main", inputs={}, ctx=None))
    flow_id = result["flow_id"]
    try:
        # First attempt: ensure fails, retries remain
        r = _run(stratum_step_done(flow_id, "review", {"clean": False, "findings": "bug"}, ctx=None))
        assert r["status"] == "ensure_failed"

        # Second attempt: retries exhausted, on_fail routes to fix
        r = _run(stratum_step_done(flow_id, "review", {"clean": False, "findings": "bug"}, ctx=None))
        assert r["step_id"] == "fix"
        assert r["routed_from"] == "review"
        assert "violations" in r
        assert len(r["violations"]) > 0
    finally:
        _flows.pop(flow_id, None)
        delete_persisted_flow(flow_id)


def test_step_done_on_fail_response_includes_routed_from_and_violations():
    """Response includes routed_from step_id and violations for transparency."""
    result = _run(stratum_plan(spec=_ON_FAIL_SPEC, flow="main", inputs={}, ctx=None))
    flow_id = result["flow_id"]
    try:
        # Exhaust retries
        _run(stratum_step_done(flow_id, "review", {"clean": False, "findings": "x"}, ctx=None))
        r = _run(stratum_step_done(flow_id, "review", {"clean": False, "findings": "x"}, ctx=None))

        # Verify routing metadata
        assert r["routed_from"] == "review"
        assert isinstance(r["violations"], list)
        assert any("clean" in v for v in r["violations"])
    finally:
        _flows.pop(flow_id, None)
        delete_persisted_flow(flow_id)


# ---------------------------------------------------------------------------
# Task 5: `next` routing tests
# ---------------------------------------------------------------------------

_NEXT_FORWARD_SPEC = textwrap.dedent("""\
    version: "0.2"
    contracts:
      Out:
        v: {type: string}
    functions:
      s1_fn:
        mode: infer
        intent: "Step 1"
        input: {}
        output: Out
      s2_fn:
        mode: infer
        intent: "Step 2"
        input: {}
        output: Out
      s3_fn:
        mode: infer
        intent: "Step 3"
        input: {}
        output: Out
    flows:
      main:
        input: {}
        steps:
          - id: s1
            function: s1_fn
            inputs: {}
            next: s3
          - id: s2
            function: s2_fn
            inputs: {}
          - id: s3
            function: s3_fn
            inputs: {}
""")

_REVIEW_FIX_LOOP_SPEC = textwrap.dedent("""\
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
      main:
        input: {}
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
""")


def test_next_routes_to_target_on_success():
    """Step with next routes to target step instead of linear advance."""
    spec = parse_and_validate(_NEXT_FORWARD_SPEC)
    state = create_flow_state(spec, "main", {})

    # s1 succeeds, next: s3 skips s2
    status, _ = process_step_result(state, "s1", {"v": "done"})
    assert status == "ok"
    assert state.ordered_steps[state.current_idx].id == "s3"


def test_next_backward_creates_loop():
    """Backward next re-executes target with fresh attempts."""
    spec = parse_and_validate(_REVIEW_FIX_LOOP_SPEC)
    state = create_flow_state(spec, "main", {})

    # Review fails ensure, routes to fix via on_fail
    process_step_result(state, "review", {"clean": False, "findings": "bug"})
    process_step_result(state, "review", {"clean": False, "findings": "bug"})
    process_step_result(state, "review", {"clean": False, "findings": "bug"})
    assert state.ordered_steps[state.current_idx].id == "fix"

    # Fix succeeds, next: review routes back to review
    status, _ = process_step_result(state, "fix", {"fixed": True})
    assert status == "ok"
    assert state.ordered_steps[state.current_idx].id == "review"

    # Review's attempts should be cleared (fresh start)
    assert state.attempts.get("review", 0) == 0


def test_next_loop_terminates_when_ensure_passes():
    """Review→fix→review loop terminates when review's ensure passes."""
    spec = parse_and_validate(_REVIEW_FIX_LOOP_SPEC)
    state = create_flow_state(spec, "main", {})

    # First review fails, routes to fix
    process_step_result(state, "review", {"clean": False, "findings": "bug"})
    process_step_result(state, "review", {"clean": False, "findings": "bug"})
    process_step_result(state, "review", {"clean": False, "findings": "bug"})

    # Fix succeeds, routes back to review
    process_step_result(state, "fix", {"fixed": True})

    # Second review passes ensure — no `next` on review, so linear advance
    status, _ = process_step_result(state, "review", {"clean": True, "findings": ""})
    assert status == "ok"

    # Review passed, current_idx advances to fix (next step after review)
    assert state.ordered_steps[state.current_idx].id == "fix"


def test_review_fix_review_end_to_end():
    """Combined on_fail + next: review→fix→review loop works end-to-end."""
    spec = parse_and_validate(_REVIEW_FIX_LOOP_SPEC)
    state = create_flow_state(spec, "main", {})

    # 1. Review fails (3 retries exhausted) → routes to fix
    process_step_result(state, "review", {"clean": False, "findings": "bug1"})
    process_step_result(state, "review", {"clean": False, "findings": "bug2"})
    status, violations = process_step_result(state, "review", {"clean": False, "findings": "bug3"})
    assert status == "on_fail_routed"
    assert state.ordered_steps[state.current_idx].id == "fix"

    # 2. Fix succeeds → routes back to review
    status, _ = process_step_result(state, "fix", {"fixed": True})
    assert status == "ok"
    assert state.ordered_steps[state.current_idx].id == "review"

    # 3. Second review passes → flow advances
    status, _ = process_step_result(state, "review", {"clean": True, "findings": ""})
    assert status == "ok"

    # Review's output is stored
    assert state.step_outputs["review"]["clean"] is True


def test_step_without_next_advances_linearly():
    """Step without next still advances to the next step linearly (unchanged)."""
    spec2 = parse_and_validate(_NO_ON_FAIL_SPEC)
    state2 = create_flow_state(spec2, "main", {})

    status, _ = process_step_result(state2, "s1", {"ok": True})
    assert status == "ok"
    # Only one step, so current_idx should be past the end
    assert state2.current_idx == 1
