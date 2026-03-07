"""Integration tests for gate policy evaluation and explicit skip (STRAT-ENG-3)."""
import asyncio
import dataclasses
import textwrap

import pytest

from stratum_mcp.errors import MCPExecutionError
from stratum_mcp.executor import (
    PolicyRecord,
    SkipRecord,
    _record_from_dict,
    create_flow_state,
    get_current_step_info,
    apply_gate_policy,
    skip_step,
    persist_flow,
    restore_flow,
    delete_persisted_flow,
    _flows,
)
from stratum_mcp.server import (
    stratum_plan,
    stratum_step_done,
    stratum_gate_resolve,
    stratum_skip_step,
    stratum_audit,
    _apply_policy_loop,
)
from stratum_mcp.spec import parse_and_validate


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


# ---------------------------------------------------------------------------
# Spec fixtures
# ---------------------------------------------------------------------------

# Work step then gate with policy:skip
_GATE_SKIP_SPEC = textwrap.dedent("""\
    version: "0.2"
    contracts:
      Out:
        v: {type: string}
    functions:
      work:
        mode: infer
        intent: "Produce output"
        input: {}
        output: Out
      review:
        mode: gate
    flows:
      main:
        input: {}
        output: Out
        steps:
          - id: s1
            function: work
            inputs: {}
          - id: gate
            function: review
            policy: skip
            on_approve: ~
            on_revise: s1
            on_kill: ~
            depends_on: [s1]
""")

# Work step then gate with policy:flag
_GATE_FLAG_SPEC = textwrap.dedent("""\
    version: "0.2"
    contracts:
      Out:
        v: {type: string}
    functions:
      work:
        mode: infer
        intent: "Produce output"
        input: {}
        output: Out
      review:
        mode: gate
    flows:
      main:
        input: {}
        output: Out
        steps:
          - id: s1
            function: work
            inputs: {}
          - id: gate
            function: review
            policy: flag
            on_approve: ~
            on_revise: s1
            on_kill: ~
            depends_on: [s1]
""")

# Gate with no policy (defaults to gate behavior)
_GATE_DEFAULT_SPEC = textwrap.dedent("""\
    version: "0.2"
    contracts:
      Out:
        v: {type: string}
    functions:
      work:
        mode: infer
        intent: "Produce output"
        input: {}
        output: Out
      review:
        mode: gate
    flows:
      main:
        input: {}
        output: Out
        steps:
          - id: s1
            function: work
            inputs: {}
          - id: gate
            function: review
            on_approve: ~
            on_revise: s1
            on_kill: ~
            depends_on: [s1]
""")

# Chained policy gates: work → gate_a (skip) → gate_b (flag) → work
_CHAINED_GATES_SPEC = textwrap.dedent("""\
    version: "0.2"
    contracts:
      Out:
        v: {type: string}
    functions:
      work:
        mode: infer
        intent: "Produce output"
        input: {}
        output: Out
      gate_a:
        mode: gate
      gate_b:
        mode: gate
    flows:
      main:
        input: {}
        output: Out
        steps:
          - id: s1
            function: work
            inputs: {}
          - id: g1
            function: gate_a
            policy: skip
            on_approve: g2
            on_revise: s1
            on_kill: ~
            depends_on: [s1]
          - id: g2
            function: gate_b
            policy: flag
            on_approve: s2
            on_revise: s1
            on_kill: ~
            depends_on: [g1]
          - id: s2
            function: work
            inputs: {}
            depends_on: [g2]
""")

# Mixed: gate A (no policy=gate), gate B (policy:skip) — for manual + auto test
_MIXED_GATE_SPEC = textwrap.dedent("""\
    version: "0.2"
    contracts:
      Out:
        v: {type: string}
    functions:
      work:
        mode: infer
        intent: "Produce output"
        input: {}
        output: Out
      gate_a:
        mode: gate
      gate_b:
        mode: gate
    flows:
      main:
        input: {}
        output: Out
        steps:
          - id: s1
            function: work
            inputs: {}
          - id: g1
            function: gate_a
            on_approve: g2
            on_revise: s1
            on_kill: ~
            depends_on: [s1]
          - id: g2
            function: gate_b
            policy: skip
            on_approve: ~
            on_revise: s1
            on_kill: ~
            depends_on: [g1]
""")

# Two-step non-gate flow for explicit skip tests
_TWO_STEP_SPEC = textwrap.dedent("""\
    version: "0.2"
    contracts:
      Out:
        v: {type: string}
    functions:
      work:
        mode: infer
        intent: "Produce output"
        input: {}
        output: Out
    flows:
      main:
        input: {}
        output: Out
        steps:
          - id: s1
            function: work
            inputs: {}
          - id: s2
            function: work
            inputs: {}
            depends_on: [s1]
""")


# ---------------------------------------------------------------------------
# Task 1: PolicyRecord + _record_from_dict
# ---------------------------------------------------------------------------

class TestPolicyRecord:

    def test_policy_record_defaults(self):
        rec = PolicyRecord(
            step_id="gate",
            effective_policy="flag",
            resolved_outcome="approve",
            rationale="policy: flag — auto-approved",
        )
        assert rec.type == "policy"
        assert rec.round == 0
        assert rec.round_start_step_id is None

    def test_policy_record_from_dict(self):
        rec = PolicyRecord(
            step_id="gate",
            effective_policy="skip",
            resolved_outcome="approve",
            rationale="policy: skip — auto-approved",
            round=2,
            round_start_step_id="s1",
        )
        d = dataclasses.asdict(rec)
        restored = _record_from_dict(d)
        assert isinstance(restored, PolicyRecord)
        assert restored.step_id == "gate"
        assert restored.effective_policy == "skip"
        assert restored.resolved_outcome == "approve"
        assert restored.round == 2
        assert restored.round_start_step_id == "s1"

    def test_policy_record_from_dict_backward_compat(self):
        """Old persisted flows without policy records still restore via _record_from_dict."""
        old_step = {"type": "step", "step_id": "s1", "function_name": "work",
                    "attempts": 1, "duration_ms": 100}
        old_gate = {"type": "gate", "step_id": "g1", "outcome": "approve",
                    "rationale": "ok", "resolved_by": "human", "duration_ms": 50}
        old_skip = {"type": "skip", "step_id": "s2", "skip_reason": "not needed"}
        assert _record_from_dict(old_step).step_id == "s1"
        assert _record_from_dict(old_gate).step_id == "g1"
        assert _record_from_dict(old_skip).step_id == "s2"


# ---------------------------------------------------------------------------
# Task 2: apply_gate_policy
# ---------------------------------------------------------------------------

class TestApplyGatePolicy:

    def _make_gate_state(self, spec_yaml, flow="main"):
        spec = parse_and_validate(spec_yaml)
        state = create_flow_state(spec, flow, {}, raw_spec=spec_yaml)
        return state

    def test_gate_returns_none(self):
        """policy=gate (default) returns None — caller should return await_gate."""
        state = self._make_gate_state(_GATE_DEFAULT_SPEC)
        # Advance past s1
        state.step_outputs["s1"] = {"v": "done"}
        state.records = []
        state.current_idx = 1  # gate step
        result = apply_gate_policy(state, "gate")
        assert result is None
        assert len(state.records) == 0  # no PolicyRecord written

    def test_skip_auto_approves(self):
        """policy=skip writes PolicyRecord and auto-approves."""
        state = self._make_gate_state(_GATE_SKIP_SPEC)
        state.step_outputs["s1"] = {"v": "done"}
        state.records = []
        state.current_idx = 1  # gate step
        result = apply_gate_policy(state, "gate")
        assert result is not None
        assert result["status"] == "complete"  # on_approve: ~ → complete
        assert len(state.records) == 1
        assert isinstance(state.records[0], PolicyRecord)
        assert state.records[0].effective_policy == "skip"

    def test_flag_auto_approves(self):
        """policy=flag writes PolicyRecord with effective_policy='flag'."""
        state = self._make_gate_state(_GATE_FLAG_SPEC)
        state.step_outputs["s1"] = {"v": "done"}
        state.records = []
        state.current_idx = 1  # gate step
        result = apply_gate_policy(state, "gate")
        assert result is not None
        assert result["status"] == "complete"
        assert state.records[0].effective_policy == "flag"
        assert state.records[0].resolved_outcome == "approve"

    def test_skip_completes_flow(self):
        """policy=skip with on_approve=None completes the flow."""
        state = self._make_gate_state(_GATE_SKIP_SPEC)
        state.step_outputs["s1"] = {"v": "done"}
        state.records = []
        state.current_idx = 1
        result = apply_gate_policy(state, "gate")
        assert result["status"] == "complete"
        assert state.current_idx == len(state.ordered_steps)

    def test_no_policy_defaults_gate(self):
        """Step with no policy field defaults to 'gate' — returns None."""
        state = self._make_gate_state(_GATE_DEFAULT_SPEC)
        state.step_outputs["s1"] = {"v": "done"}
        state.records = []
        state.current_idx = 1
        result = apply_gate_policy(state, "gate")
        assert result is None

    def test_routes_on_approve(self):
        """policy=skip with on_approve=target advances to that step."""
        state = self._make_gate_state(_CHAINED_GATES_SPEC)
        state.step_outputs["s1"] = {"v": "done"}
        state.records = []
        state.current_idx = 1  # g1 (policy:skip, on_approve: g2)
        result = apply_gate_policy(state, "g1")
        assert result is not None
        # Should have advanced to g2 and returned its step info
        assert state.current_idx == 2  # g2


# ---------------------------------------------------------------------------
# Task 3: skip_step helper
# ---------------------------------------------------------------------------

class TestSkipStep:

    def _make_state(self, spec_yaml, flow="main"):
        spec = parse_and_validate(spec_yaml)
        return create_flow_state(spec, flow, {}, raw_spec=spec_yaml)

    def test_writes_record(self):
        state = self._make_state(_TWO_STEP_SPEC)
        skip_step(state, "s1", "not needed")
        assert state.current_idx == 1
        assert state.step_outputs["s1"] is None
        assert len(state.records) == 1
        assert isinstance(state.records[0], SkipRecord)
        assert state.records[0].skip_reason == "not needed"

    def test_wrong_step_id_raises(self):
        state = self._make_state(_TWO_STEP_SPEC)
        with pytest.raises(MCPExecutionError, match="Expected step 's1'"):
            skip_step(state, "wrong", "reason")

    def test_gate_step_raises(self):
        state = self._make_state(_GATE_DEFAULT_SPEC)
        state.step_outputs["s1"] = {"v": "done"}
        state.current_idx = 1  # gate step
        with pytest.raises(MCPExecutionError, match="gate step"):
            skip_step(state, "gate", "reason")

    def test_skip_if_still_works(self):
        """Regression: skip_if behavior unchanged after refactor to use skip_step."""
        spec_yaml = textwrap.dedent("""\
            version: "0.2"
            contracts:
              Out:
                v: {type: string}
            functions:
              work:
                mode: infer
                intent: "Do work"
                input: {}
                output: Out
            flows:
              main:
                input:
                  do_skip: {type: boolean}
                steps:
                  - id: s1
                    function: work
                    inputs: {}
                    skip_if: "$.input.do_skip == True"
                    skip_reason: "user said skip"
                  - id: s2
                    function: work
                    inputs: {}
                    depends_on: [s1]
        """)
        spec = parse_and_validate(spec_yaml)
        state = create_flow_state(spec, "main", {"do_skip": True}, raw_spec=spec_yaml)
        info = get_current_step_info(state)
        # s1 should be skipped, info should be for s2
        assert info["step_id"] == "s2"
        assert state.step_outputs["s1"] is None
        assert any(isinstance(r, SkipRecord) and r.step_id == "s1" for r in state.records)


# ---------------------------------------------------------------------------
# Task 4: Policy loop wiring in server
# ---------------------------------------------------------------------------

class TestPolicyLoopServer:

    def test_plan_gate_policy_skip_returns_next_step(self):
        """Plan with first step being work + second gate with policy:skip."""
        result = _run(stratum_plan(spec=_GATE_SKIP_SPEC, flow="main", inputs={}, ctx=None))
        assert result["status"] == "execute_step"
        assert result["step_id"] == "s1"
        # Clean up
        delete_persisted_flow(result["flow_id"])

    def test_plan_gate_policy_skip_completes_flow(self):
        """Single gate step with policy:skip as first step after work completes."""
        result = _run(stratum_plan(spec=_GATE_SKIP_SPEC, flow="main", inputs={}, ctx=None))
        flow_id = result["flow_id"]
        # Complete s1
        done = _run(stratum_step_done(flow_id=flow_id, step_id="s1",
                                       result={"v": "output"}, ctx=None))
        # Gate should be auto-approved by policy:skip → flow complete
        assert done["status"] == "complete"

    def test_plan_gate_policy_gate_returns_await(self):
        """Gate with no policy (default=gate) returns await_gate."""
        result = _run(stratum_plan(spec=_GATE_DEFAULT_SPEC, flow="main", inputs={}, ctx=None))
        flow_id = result["flow_id"]
        done = _run(stratum_step_done(flow_id=flow_id, step_id="s1",
                                       result={"v": "output"}, ctx=None))
        assert done["status"] == "await_gate"
        delete_persisted_flow(flow_id)

    def test_step_done_advances_through_policy_gate(self):
        """step_done advancing past work into a flag gate auto-resolves it."""
        result = _run(stratum_plan(spec=_GATE_FLAG_SPEC, flow="main", inputs={}, ctx=None))
        flow_id = result["flow_id"]
        done = _run(stratum_step_done(flow_id=flow_id, step_id="s1",
                                       result={"v": "output"}, ctx=None))
        # Gate with policy:flag should auto-resolve → flow complete (on_approve: ~)
        assert done["status"] == "complete"
        # Verify PolicyRecord in trace
        policy_records = [r for r in done["trace"] if r["type"] == "policy"]
        assert len(policy_records) == 1
        assert policy_records[0]["effective_policy"] == "flag"

    def test_policy_loop_cycle_falls_back_to_gate(self):
        """on_approve cycle with policy:skip breaks loop, returns await_gate."""
        # Build a spec where gate A approves to gate B and gate B approves to gate A
        spec_yaml = textwrap.dedent("""\
            version: "0.2"
            contracts:
              Out:
                v: {type: string}
            functions:
              work:
                mode: infer
                intent: "Do work"
                input: {}
                output: Out
              gate_a:
                mode: gate
              gate_b:
                mode: gate
            flows:
              main:
                input: {}
                output: Out
                steps:
                  - id: s1
                    function: work
                    inputs: {}
                  - id: g1
                    function: gate_a
                    policy: skip
                    on_approve: g2
                    on_revise: s1
                    on_kill: ~
                    depends_on: [s1]
                  - id: g2
                    function: gate_b
                    policy: skip
                    on_approve: g1
                    on_revise: s1
                    on_kill: ~
                    depends_on: [s1]
        """)
        result = _run(stratum_plan(spec=spec_yaml, flow="main", inputs={}, ctx=None))
        flow_id = result["flow_id"]
        done = _run(stratum_step_done(flow_id=flow_id, step_id="s1",
                                       result={"v": "output"}, ctx=None))
        # Should break the cycle and return await_gate for whichever gate it lands on
        assert done["status"] == "await_gate"
        delete_persisted_flow(flow_id)


# ---------------------------------------------------------------------------
# Task 5: stratum_skip_step MCP tool
# ---------------------------------------------------------------------------

class TestStratumSkipStepTool:

    def test_skips_and_advances(self):
        result = _run(stratum_plan(spec=_TWO_STEP_SPEC, flow="main", inputs={}, ctx=None))
        flow_id = result["flow_id"]
        skip_result = _run(stratum_skip_step(flow_id=flow_id, step_id="s1",
                                              reason="not needed", ctx=None))
        assert skip_result["status"] == "execute_step"
        assert skip_result["step_id"] == "s2"
        delete_persisted_flow(flow_id)

    def test_completes_flow(self):
        result = _run(stratum_plan(spec=_TWO_STEP_SPEC, flow="main", inputs={}, ctx=None))
        flow_id = result["flow_id"]
        # Skip s1
        _run(stratum_skip_step(flow_id=flow_id, step_id="s1", reason="skip", ctx=None))
        # Skip s2
        skip_result = _run(stratum_skip_step(flow_id=flow_id, step_id="s2",
                                              reason="skip too", ctx=None))
        assert skip_result["status"] == "complete"

    def test_gate_rejected(self):
        result = _run(stratum_plan(spec=_GATE_DEFAULT_SPEC, flow="main", inputs={}, ctx=None))
        flow_id = result["flow_id"]
        # Complete s1
        _run(stratum_step_done(flow_id=flow_id, step_id="s1",
                                result={"v": "output"}, ctx=None))
        # Try to skip gate step
        skip_result = _run(stratum_skip_step(flow_id=flow_id, step_id="gate",
                                              reason="skip it", ctx=None))
        assert skip_result["status"] == "error"
        assert "gate step" in skip_result["message"]
        delete_persisted_flow(flow_id)

    def test_wrong_step_rejected(self):
        result = _run(stratum_plan(spec=_TWO_STEP_SPEC, flow="main", inputs={}, ctx=None))
        flow_id = result["flow_id"]
        skip_result = _run(stratum_skip_step(flow_id=flow_id, step_id="wrong",
                                              reason="skip", ctx=None))
        assert skip_result["status"] == "error"
        delete_persisted_flow(flow_id)

    def test_flow_not_found(self):
        skip_result = _run(stratum_skip_step(flow_id="nonexistent", step_id="s1",
                                              reason="skip", ctx=None))
        assert skip_result["status"] == "error"
        assert skip_result["error_type"] == "flow_not_found"


# ---------------------------------------------------------------------------
# Task 6: Full roundtrip integration
# ---------------------------------------------------------------------------

class TestRoundtripPolicySkip:

    def test_roundtrip_policy_skip_gate(self):
        """Full roundtrip: work → gate(policy:skip) → auto-approve → complete."""
        result = _run(stratum_plan(spec=_GATE_SKIP_SPEC, flow="main", inputs={}, ctx=None))
        flow_id = result["flow_id"]
        done = _run(stratum_step_done(flow_id=flow_id, step_id="s1",
                                       result={"v": "output"}, ctx=None))
        assert done["status"] == "complete"
        policy_recs = [r for r in done["trace"] if r["type"] == "policy"]
        assert len(policy_recs) == 1
        assert policy_recs[0]["effective_policy"] == "skip"

    def test_roundtrip_policy_flag_gate(self):
        """Full roundtrip: work → gate(policy:flag) → auto-approve with PolicyRecord."""
        result = _run(stratum_plan(spec=_GATE_FLAG_SPEC, flow="main", inputs={}, ctx=None))
        flow_id = result["flow_id"]
        done = _run(stratum_step_done(flow_id=flow_id, step_id="s1",
                                       result={"v": "output"}, ctx=None))
        assert done["status"] == "complete"
        policy_recs = [r for r in done["trace"] if r["type"] == "policy"]
        assert len(policy_recs) == 1
        assert policy_recs[0]["effective_policy"] == "flag"
        assert policy_recs[0]["resolved_outcome"] == "approve"

    def test_roundtrip_chained_policy_gates(self):
        """work → gate_a(skip) → gate_b(flag) → work, both gates auto-resolve."""
        result = _run(stratum_plan(spec=_CHAINED_GATES_SPEC, flow="main", inputs={}, ctx=None))
        flow_id = result["flow_id"]
        # Complete s1
        done = _run(stratum_step_done(flow_id=flow_id, step_id="s1",
                                       result={"v": "output"}, ctx=None))
        # Both gates should auto-resolve, landing on s2
        assert done["status"] == "execute_step"
        assert done["step_id"] == "s2"
        # Complete s2
        done2 = _run(stratum_step_done(flow_id=flow_id, step_id="s2",
                                        result={"v": "final"}, ctx=None))
        assert done2["status"] == "complete"
        # Check trace for two PolicyRecords
        policy_recs = [r for r in done2["trace"] if r["type"] == "policy"]
        assert len(policy_recs) == 2

    def test_roundtrip_mixed_gate_policy(self):
        """gate_a (no policy=gate) → manual resolve → gate_b (skip) → auto-resolve."""
        result = _run(stratum_plan(spec=_MIXED_GATE_SPEC, flow="main", inputs={}, ctx=None))
        flow_id = result["flow_id"]
        # Complete s1
        done = _run(stratum_step_done(flow_id=flow_id, step_id="s1",
                                       result={"v": "output"}, ctx=None))
        assert done["status"] == "await_gate"
        assert done["step_id"] == "g1"
        # Manually resolve g1 → routes to g2
        resolved = _run(stratum_gate_resolve(flow_id=flow_id, step_id="g1",
                                              outcome="approve", rationale="lgtm",
                                              resolved_by="human", ctx=None))
        # g2 has policy:skip → auto-resolves → flow complete (on_approve: ~)
        assert resolved["status"] == "complete"
        policy_recs = [r for r in resolved["trace"] if r["type"] == "policy"]
        assert len(policy_recs) == 1
        assert policy_recs[0]["step_id"] == "g2"

    def test_roundtrip_explicit_skip(self):
        """stratum_skip_step on non-gate step, SkipRecord in trace."""
        result = _run(stratum_plan(spec=_TWO_STEP_SPEC, flow="main", inputs={}, ctx=None))
        flow_id = result["flow_id"]
        skip_result = _run(stratum_skip_step(flow_id=flow_id, step_id="s1",
                                              reason="not relevant", ctx=None))
        assert skip_result["status"] == "execute_step"
        # Complete s2
        done = _run(stratum_step_done(flow_id=flow_id, step_id="s2",
                                       result={"v": "output"}, ctx=None))
        assert done["status"] == "complete"
        skip_recs = [r for r in done["trace"] if r["type"] == "skip"]
        assert len(skip_recs) == 1
        assert skip_recs[0]["skip_reason"] == "not relevant"

    def test_roundtrip_policy_record_persistence(self):
        """Policy gate flow survives persist → cache eviction → restore → audit."""
        result = _run(stratum_plan(spec=_GATE_SKIP_SPEC, flow="main", inputs={}, ctx=None))
        flow_id = result["flow_id"]
        # Complete s1 → gate auto-resolves → complete
        done = _run(stratum_step_done(flow_id=flow_id, step_id="s1",
                                       result={"v": "output"}, ctx=None))
        assert done["status"] == "complete"
        # The flow was deleted on completion. Create a new flow, persist, evict, restore.
        result2 = _run(stratum_plan(spec=_GATE_FLAG_SPEC, flow="main", inputs={}, ctx=None))
        flow_id2 = result2["flow_id"]
        # Complete s1 to trigger policy
        _run(stratum_step_done(flow_id=flow_id2, step_id="s1",
                                result={"v": "out"}, ctx=None))
        # That completed the flow — create another to test persistence of in-progress
        result3 = _run(stratum_plan(spec=_CHAINED_GATES_SPEC, flow="main", inputs={}, ctx=None))
        flow_id3 = result3["flow_id"]
        # Complete s1 — gates auto-resolve, s2 is next
        _run(stratum_step_done(flow_id=flow_id3, step_id="s1",
                                result={"v": "out"}, ctx=None))
        # Evict from cache and restore
        persist_flow(_flows[flow_id3])
        del _flows[flow_id3]
        restored = restore_flow(flow_id3)
        assert restored is not None
        # Check PolicyRecords survived
        policy_recs = [r for r in restored.records if isinstance(r, PolicyRecord)]
        assert len(policy_recs) == 2
        delete_persisted_flow(flow_id3)
