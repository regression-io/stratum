"""Tests for IR v0.2 STRAT-ENG-1 extensions: workflow, inline steps, flow composition, policy."""
import pytest

from stratum_mcp.errors import IRSemanticError, IRValidationError
from stratum_mcp.spec import parse_and_validate


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Minimal valid v0.2 spec with a function-based step (baseline for mutation tests)
_BASE_V02 = """
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
"""


# ---------------------------------------------------------------------------
# Task 1: IRWorkflowDef + IRSpec.workflow
# ---------------------------------------------------------------------------

def test_spec_without_workflow_has_none():
    spec = parse_and_validate(_BASE_V02)
    assert spec.workflow is None


def test_parse_workflow_populates_irworkflowdef():
    ir = """
version: "0.2"
contracts:
  Out:
    v: {type: string}
functions:
  work:
    mode: infer
    intent: "Do it"
    input: {feature: {type: string}}
    output: Out
workflow:
  name: build
  description: "Execute feature lifecycle"
  input:
    feature: {type: string, required: true}
flows:
  build:
    input: {feature: {type: string}}
    output: Out
    steps:
      - id: s1
        function: work
        inputs: {feature: "$.input.feature"}
"""
    spec = parse_and_validate(ir)
    assert spec.workflow is not None
    assert spec.workflow.name == "build"
    assert spec.workflow.description == "Execute feature lifecycle"
    assert "feature" in spec.workflow.input_schema


# ---------------------------------------------------------------------------
# Task 2: IRStepDef new fields
# ---------------------------------------------------------------------------

def test_step_fields_default_to_none():
    spec = parse_and_validate(_BASE_V02)
    step = spec.flows["main"].steps[0]
    assert step.agent is None
    assert step.intent is None
    assert step.on_fail is None
    assert step.next is None
    assert step.flow_ref is None
    assert step.policy is None
    assert step.policy_fallback is None
    assert step.step_ensure is None
    assert step.step_retries is None
    assert step.output_contract is None


# ---------------------------------------------------------------------------
# Task 3: v0.2 JSON schema accepts new fields
# ---------------------------------------------------------------------------

def test_v02_schema_accepts_inline_step():
    ir = """
version: "0.2"
contracts:
  Out:
    v: {type: string}
flows:
  main:
    input: {}
    steps:
      - id: s1
        intent: "Do the thing"
        agent: claude
        ensure:
          - "result.v != ''"
        retries: 2
"""
    spec = parse_and_validate(ir)
    step = spec.flows["main"].steps[0]
    assert step.intent == "Do the thing"
    assert step.agent == "claude"
    assert step.step_ensure == ["result.v != ''"]
    assert step.step_retries == 2


def test_v02_schema_accepts_workflow_block():
    ir = """
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
workflow:
  name: test-flow
  description: "A test workflow"
  input: {}
flows:
  test-flow:
    input: {}
    output: Out
    steps:
      - id: s1
        function: work
        inputs: {}
"""
    spec = parse_and_validate(ir)
    assert spec.workflow.name == "test-flow"


def test_v02_schema_accepts_flow_ref_step():
    ir = """
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
  sub:
    input: {}
    output: Out
    steps:
      - id: s1
        function: work
        inputs: {}
  main:
    input: {}
    steps:
      - id: s1
        flow: sub
"""
    spec = parse_and_validate(ir)
    step = spec.flows["main"].steps[0]
    assert step.flow_ref == "sub"


def test_v01_schema_rejects_new_fields():
    ir = """
version: "0.1"
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
  main:
    input: {}
    output: Out
    steps:
      - id: s1
        function: work
        inputs: {}
        agent: claude
"""
    with pytest.raises(IRValidationError):
        parse_and_validate(ir)


# ---------------------------------------------------------------------------
# Task 4: Parser populates fields
# ---------------------------------------------------------------------------

def test_parse_inline_step_populates_fields():
    ir = """
version: "0.2"
flows:
  main:
    input: {}
    steps:
      - id: s1
        intent: "Write the design doc"
        agent: codex
        ensure:
          - "file_exists('design.md')"
        retries: 3
        output_contract: DesignResult
        model: claude-opus-4-6
"""
    spec = parse_and_validate(ir)
    step = spec.flows["main"].steps[0]
    assert step.intent == "Write the design doc"
    assert step.agent == "codex"
    assert step.step_ensure == ["file_exists('design.md')"]
    assert step.step_retries == 3
    assert step.output_contract == "DesignResult"
    assert step.step_model == "claude-opus-4-6"


def test_parse_flow_ref_step():
    ir = """
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
  helper:
    input: {}
    output: Out
    steps:
      - id: h1
        function: work
        inputs: {}
  main:
    input: {}
    steps:
      - id: s1
        flow: helper
        ensure:
          - "result.v != ''"
"""
    spec = parse_and_validate(ir)
    step = spec.flows["main"].steps[0]
    assert step.flow_ref == "helper"
    assert step.step_ensure == ["result.v != ''"]


# ---------------------------------------------------------------------------
# Task 5: Semantic validation
# ---------------------------------------------------------------------------

def test_reject_step_with_function_and_intent():
    ir = """
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
  main:
    input: {}
    steps:
      - id: s1
        function: work
        intent: "Also do it"
        inputs: {}
"""
    with pytest.raises(IRSemanticError, match="exactly one"):
        parse_and_validate(ir)


def test_reject_step_with_no_mode():
    ir = """
version: "0.2"
flows:
  main:
    input: {}
    steps:
      - id: s1
"""
    with pytest.raises(IRSemanticError, match="exactly one"):
        parse_and_validate(ir)


def test_reject_function_step_with_step_ensure():
    ir = """
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
  main:
    input: {}
    steps:
      - id: s1
        function: work
        inputs: {}
        ensure:
          - "result.v != ''"
"""
    with pytest.raises(IRSemanticError, match="must be on the function"):
        parse_and_validate(ir)


def test_reject_flow_ref_with_agent():
    ir = """
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
  sub:
    input: {}
    output: Out
    steps:
      - id: h1
        function: work
        inputs: {}
  main:
    input: {}
    steps:
      - id: s1
        flow: sub
        agent: claude
"""
    with pytest.raises(IRSemanticError, match="agent must not be set"):
        parse_and_validate(ir)


def test_reject_flow_ref_to_unknown_flow():
    ir = """
version: "0.2"
flows:
  main:
    input: {}
    steps:
      - id: s1
        flow: nonexistent
"""
    with pytest.raises(IRSemanticError, match="undefined flow"):
        parse_and_validate(ir)


def test_reject_recursive_flow_ref():
    ir = """
version: "0.2"
flows:
  main:
    input: {}
    steps:
      - id: s1
        flow: main
"""
    with pytest.raises(IRSemanticError, match="[Rr]ecursive"):
        parse_and_validate(ir)


def test_on_fail_target_must_exist():
    ir = """
version: "0.2"
flows:
  main:
    input: {}
    steps:
      - id: s1
        intent: "Do thing"
        ensure:
          - "result.ok == true"
        on_fail: nonexistent
"""
    with pytest.raises(IRSemanticError, match="on_fail.*unknown step"):
        parse_and_validate(ir)


def test_on_fail_without_ensure_raises():
    ir = """
version: "0.2"
flows:
  main:
    input: {}
    steps:
      - id: s1
        intent: "Do thing"
        on_fail: s1
"""
    with pytest.raises(IRSemanticError, match="on_fail.*no ensure"):
        parse_and_validate(ir)


def test_on_fail_rejected_on_gate_step():
    ir = """
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
  review:
    mode: gate
flows:
  main:
    input: {}
    steps:
      - id: s1
        function: work
        inputs: {}
      - id: gate
        function: review
        on_approve: ~
        on_revise: s1
        on_kill: ~
        on_fail: s1
        depends_on: [s1]
"""
    with pytest.raises(IRSemanticError, match="on_fail"):
        parse_and_validate(ir)


def test_next_target_must_exist():
    ir = """
version: "0.2"
flows:
  main:
    input: {}
    steps:
      - id: s1
        intent: "Do thing"
        next: nonexistent
"""
    with pytest.raises(IRSemanticError, match="next.*unknown step"):
        parse_and_validate(ir)


def test_policy_rejected_on_non_gate_step():
    ir = """
version: "0.2"
flows:
  main:
    input: {}
    steps:
      - id: s1
        intent: "Do thing"
        policy: gate
"""
    with pytest.raises(IRSemanticError, match="policy.*not a gate"):
        parse_and_validate(ir)


def test_policy_fallback_without_policy_rejected():
    ir = """
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
  review:
    mode: gate
flows:
  main:
    input: {}
    steps:
      - id: s1
        function: work
        inputs: {}
      - id: gate
        function: review
        on_approve: ~
        on_revise: s1
        on_kill: ~
        policy_fallback: skip
        depends_on: [s1]
"""
    with pytest.raises(IRSemanticError, match="policy_fallback.*no policy"):
        parse_and_validate(ir)


def test_workflow_entry_flow_must_exist():
    ir = """
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
workflow:
  name: nonexistent
  description: "Bad workflow"
  input: {}
flows:
  main:
    input: {}
    output: Out
    steps:
      - id: s1
        function: work
        inputs: {}
  other:
    input: {}
    output: Out
    steps:
      - id: s1
        function: work
        inputs: {}
"""
    with pytest.raises(IRSemanticError, match="cannot determine entry flow"):
        parse_and_validate(ir)


def test_workflow_input_mismatch_raises():
    ir = """
version: "0.2"
contracts:
  Out:
    v: {type: string}
functions:
  work:
    mode: infer
    intent: "Do it"
    input: {feature: {type: string}}
    output: Out
workflow:
  name: build
  description: "Build something"
  input:
    wrong_key: {type: string}
flows:
  build:
    input: {feature: {type: string}}
    output: Out
    steps:
      - id: s1
        function: work
        inputs: {feature: "$.input.feature"}
"""
    with pytest.raises(IRSemanticError, match="input keys.*do not match"):
        parse_and_validate(ir)


# ---------------------------------------------------------------------------
# Gate routing on inline/flow steps (common-path invariant)
# ---------------------------------------------------------------------------

def test_inline_step_with_on_approve_raises():
    ir = """
version: "0.2"
flows:
  main:
    input: {}
    steps:
      - id: s1
        intent: "Do thing"
        on_approve: s1
"""
    with pytest.raises(IRSemanticError, match="not a gate step.*on_approve"):
        parse_and_validate(ir)


def test_flow_ref_step_with_on_revise_raises():
    ir = """
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
  sub:
    input: {}
    output: Out
    steps:
      - id: h1
        function: work
        inputs: {}
  main:
    input: {}
    steps:
      - id: s1
        flow: sub
        on_revise: s1
"""
    with pytest.raises(IRSemanticError, match="not a gate step.*on_revise"):
        parse_and_validate(ir)


# ---------------------------------------------------------------------------
# Workflow with subflows (P1 fix: multiple flows allowed)
# ---------------------------------------------------------------------------

def test_workflow_with_subflows_is_valid():
    """A workflow spec can have multiple flows — only one must be the entry flow."""
    ir = """
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
workflow:
  name: build
  description: "Build with sub-workflows"
  input: {}
flows:
  review_fix:
    input: {}
    output: Out
    steps:
      - id: r1
        function: work
        inputs: {}
  build:
    input: {}
    steps:
      - id: s1
        function: work
        inputs: {}
      - id: s2
        flow: review_fix
        depends_on: [s1]
"""
    spec = parse_and_validate(ir)
    assert spec.workflow.name == "build"
    assert len(spec.flows) == 2


def test_workflow_empty_input_vs_nonempty_flow_raises():
    """workflow.input={} but entry flow has input keys → mismatch."""
    ir = """
version: "0.2"
contracts:
  Out:
    v: {type: string}
functions:
  work:
    mode: infer
    intent: "Do it"
    input: {feature: {type: string}}
    output: Out
workflow:
  name: build
  description: "Build it"
  input: {}
flows:
  build:
    input: {feature: {type: string}}
    output: Out
    steps:
      - id: s1
        function: work
        inputs: {feature: "$.input.feature"}
"""
    with pytest.raises(IRSemanticError, match="input keys.*do not match"):
        parse_and_validate(ir)


def test_workflow_nonempty_input_vs_empty_flow_raises():
    """workflow.input has keys but entry flow input={} → mismatch."""
    ir = """
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
workflow:
  name: build
  description: "Build it"
  input:
    feature: {type: string}
flows:
  build:
    input: {}
    output: Out
    steps:
      - id: s1
        function: work
        inputs: {}
"""
    with pytest.raises(IRSemanticError, match="input keys.*do not match"):
        parse_and_validate(ir)


def test_flow_ref_step_on_fail_without_ensure_raises():
    """flow: step with on_fail but no ensure should be rejected."""
    ir = """
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
  sub:
    input: {}
    output: Out
    steps:
      - id: h1
        function: work
        inputs: {}
  main:
    input: {}
    steps:
      - id: s1
        flow: sub
        on_fail: s1
"""
    with pytest.raises(IRSemanticError, match="on_fail.*no ensure"):
        parse_and_validate(ir)


# ---------------------------------------------------------------------------
# STRAT-ENG-4: Per-step iteration fields
# ---------------------------------------------------------------------------

def test_max_iterations_parsed():
    ir = """
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
  main:
    input: {}
    output: Out
    steps:
      - id: s1
        function: work
        inputs: {}
        max_iterations: 10
        exit_criterion: "result.v == 'done'"
"""
    spec = parse_and_validate(ir)
    step = spec.flows["main"].steps[0]
    assert step.max_iterations == 10
    assert step.exit_criterion == "result.v == 'done'"


def test_max_iterations_without_exit_criterion():
    """max_iterations alone (no exit_criterion) is valid."""
    ir = """
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
  main:
    input: {}
    output: Out
    steps:
      - id: s1
        function: work
        inputs: {}
        max_iterations: 5
"""
    spec = parse_and_validate(ir)
    step = spec.flows["main"].steps[0]
    assert step.max_iterations == 5
    assert step.exit_criterion is None


def test_max_iterations_forbidden_on_gate_steps():
    ir = """
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
  gate_fn:
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
        function: gate_fn
        on_approve: ~
        on_revise: s1
        on_kill: ~
        max_iterations: 10
"""
    with pytest.raises(IRSemanticError, match="must not have max_iterations"):
        parse_and_validate(ir)


def test_exit_criterion_requires_max_iterations():
    ir = """
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
  main:
    input: {}
    output: Out
    steps:
      - id: s1
        function: work
        inputs: {}
        exit_criterion: "result.v == 'done'"
"""
    with pytest.raises(IRSemanticError, match="exit_criterion but no max_iterations"):
        parse_and_validate(ir)


def test_exit_criterion_dunder_blocked():
    ir = """
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
  main:
    input: {}
    output: Out
    steps:
      - id: s1
        function: work
        inputs: {}
        max_iterations: 5
        exit_criterion: "result.__class__.__name__ == 'dict'"
"""
    with pytest.raises(IRSemanticError, match="dunder"):
        parse_and_validate(ir)


# ---------------------------------------------------------------------------
# STRAT-ENG-5: on_fail on function steps with function-level ensure
# ---------------------------------------------------------------------------

def test_on_fail_function_step_with_function_ensure_accepted():
    """Function step with on_fail should be accepted when the function has ensure."""
    ir = """
version: "0.2"
contracts:
  Out:
    v: {type: string}
functions:
  checker:
    mode: infer
    intent: "Check something"
    input: {}
    output: Out
    ensure:
      - "result.v != ''"
flows:
  main:
    input: {}
    output: Out
    steps:
      - id: check
        function: checker
        inputs: {}
        on_fail: recover
      - id: recover
        intent: "Recover from failure"
        depends_on: []
"""
    spec = parse_and_validate(ir)
    step = spec.flows["main"].steps[0]
    assert step.on_fail == "recover"


def test_on_fail_function_step_without_any_ensure_rejected():
    """Function step with on_fail but no ensure (step or function) should be rejected."""
    ir = """
version: "0.2"
contracts:
  Out:
    v: {type: string}
functions:
  worker:
    mode: infer
    intent: "Do work"
    input: {}
    output: Out
flows:
  main:
    input: {}
    output: Out
    steps:
      - id: work
        function: worker
        inputs: {}
        on_fail: recover
      - id: recover
        intent: "Recover"
"""
    with pytest.raises(IRSemanticError, match="on_fail.*no ensure"):
        parse_and_validate(ir)
