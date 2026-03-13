"""Tests for IR spec parsing and validation."""
import pytest

from stratum_mcp.errors import IRParseError, IRSemanticError, IRValidationError
from stratum_mcp.spec import parse_and_validate


VALID_IR = """
version: "0.1"
contracts:
  SentimentResult:
    label: {type: string}
    confidence: {type: number}
functions:
  classify:
    mode: infer
    intent: "Classify sentiment"
    input: {text: {type: string}}
    output: SentimentResult
flows:
  run:
    input: {text: {type: string}}
    output: SentimentResult
    steps:
      - id: s1
        function: classify
        inputs: {text: "$.input.text"}
"""


def test_valid_ir_parses():
    spec = parse_and_validate(VALID_IR)
    assert spec.version == "0.1"
    assert "classify" in spec.functions
    assert "run" in spec.flows
    assert "SentimentResult" in spec.contracts


def test_valid_ir_function_fields():
    spec = parse_and_validate(VALID_IR)
    fn = spec.functions["classify"]
    assert fn.mode == "infer"
    assert fn.intent == "Classify sentiment"
    assert fn.output_contract == "SentimentResult"
    assert fn.retries == 3  # default


def test_valid_ir_flow_steps():
    spec = parse_and_validate(VALID_IR)
    flow = spec.flows["run"]
    assert len(flow.steps) == 1
    step = flow.steps[0]
    assert step.id == "s1"
    assert step.function == "classify"
    assert step.inputs == {"text": "$.input.text"}


def test_invalid_yaml_raises_parse_error():
    with pytest.raises(IRParseError):
        parse_and_validate("version: [\n  bad")


def test_wrong_version_raises_validation_error():
    with pytest.raises(IRValidationError) as exc_info:
        parse_and_validate('version: "99.0"\n')
    assert exc_info.value.path == "version"


def test_undefined_contract_ref_in_function_raises_semantic_error():
    bad_ir = """
version: "0.1"
contracts:
  SentimentResult:
    label: {type: string}
functions:
  classify:
    mode: infer
    intent: "Classify"
    input: {text: {type: string}}
    output: NonExistentContract
flows:
  run:
    input: {text: {type: string}}
    output: SentimentResult
    steps:
      - id: s1
        function: classify
        inputs: {text: "$.input.text"}
"""
    with pytest.raises(IRSemanticError):
        parse_and_validate(bad_ir)


def test_undefined_function_reference_raises_semantic_error():
    bad_ir = """
version: "0.1"
contracts:
  SentimentResult:
    label: {type: string}
functions:
  classify:
    mode: infer
    intent: "Classify"
    input: {text: {type: string}}
    output: SentimentResult
flows:
  run:
    input: {text: {type: string}}
    output: SentimentResult
    steps:
      - id: s1
        function: nonexistent_fn
        inputs: {text: "$.input.text"}
"""
    with pytest.raises(IRSemanticError):
        parse_and_validate(bad_ir)


def test_missing_required_field_raises_validation_error():
    # Missing 'intent' from function
    bad_ir = """
version: "0.1"
functions:
  f:
    mode: infer
    input: {}
    output: X
"""
    with pytest.raises(IRValidationError) as exc_info:
        parse_and_validate(bad_ir)
    combined = (exc_info.value.suggestion or "") + (exc_info.value.message or "")
    assert "intent" in combined.lower()


def test_forward_depends_on_is_valid():
    """Steps may reference a step declared later in YAML — order is irrelevant for existence checks."""
    ir = """
version: "0.1"
contracts:
  Out:
    x: {type: string}
functions:
  f:
    mode: infer
    intent: "do thing"
    input: {text: {type: string}}
    output: Out
flows:
  run:
    input: {text: {type: string}}
    output: Out
    steps:
      - id: s2
        function: f
        inputs: {text: "$.steps.s1.output"}
        depends_on: [s1]
      - id: s1
        function: f
        inputs: {text: "$.input.text"}
"""
    spec = parse_and_validate(ir)
    assert len(spec.flows["run"].steps) == 2


def test_empty_yaml_raises_parse_error():
    with pytest.raises(IRParseError) as exc_info:
        parse_and_validate("")
    assert "empty" in exc_info.value.raw_error.lower()


def test_blank_yaml_raises_parse_error():
    with pytest.raises(IRParseError):
        parse_and_validate("   \n  ")


def test_empty_steps_raises_validation_error():
    bad_ir = """
version: "0.1"
contracts:
  Out:
    x: {type: string}
functions:
  f:
    mode: infer
    intent: "do thing"
    input: {}
    output: Out
flows:
  run:
    input: {}
    output: Out
    steps: []
"""
    with pytest.raises(IRValidationError):
        parse_and_validate(bad_ir)


# ---------------------------------------------------------------------------
# IR v0.2 gate semantic invariants
# ---------------------------------------------------------------------------

# Minimal valid v0.2 spec with one work step then a gate step. Used as the
# baseline; individual tests mutate specific fields to provoke errors.
_VALID_GATE_IR = """
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
  f:
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
"""


def test_valid_v02_gate_spec_parses():
    """Baseline: a well-formed v0.2 spec with a gate step must parse without error."""
    spec = parse_and_validate(_VALID_GATE_IR)
    assert spec.version == "0.2"
    assert spec.functions["review"].mode == "gate"
    gate_step = next(s for s in spec.flows["f"].steps if s.id == "gate")
    assert gate_step.on_revise == "s1"


# --- Gate function constraints ---

def test_gate_function_with_ensure_raises():
    ir = _VALID_GATE_IR.replace(
        "  review:\n    mode: gate",
        "  review:\n    mode: gate\n    ensure: [\"true\"]",
    )
    with pytest.raises(IRSemanticError, match="ensure"):
        parse_and_validate(ir)


def test_gate_function_with_budget_raises():
    ir = _VALID_GATE_IR.replace(
        "  review:\n    mode: gate",
        "  review:\n    mode: gate\n    budget:\n      ms: 5000",
    )
    with pytest.raises(IRSemanticError, match="budget"):
        parse_and_validate(ir)


def test_gate_function_with_retries_raises():
    ir = _VALID_GATE_IR.replace(
        "  review:\n    mode: gate",
        "  review:\n    mode: gate\n    retries: 2",
    )
    with pytest.raises(IRSemanticError, match="retries"):
        parse_and_validate(ir)


# --- Gate step constraints ---

def test_gate_step_with_skip_if_allowed():
    """Gate steps CAN have skip_if (e.g., file_exists-based .approved markers)."""
    ir = _VALID_GATE_IR.replace(
        "        on_kill: ~",
        "        on_kill: ~\n        skip_if: \"true\"\n        skip_reason: \"already approved\"",
    )
    spec = parse_and_validate(ir)
    assert spec is not None


def test_gate_step_missing_on_approve_raises():
    """on_approve must be explicitly declared (even if null)."""
    ir = _VALID_GATE_IR.replace("        on_approve: ~\n", "")
    with pytest.raises(IRSemanticError, match="on_approve"):
        parse_and_validate(ir)


def test_gate_step_missing_on_kill_raises():
    """on_kill must be explicitly declared (even if null)."""
    ir = _VALID_GATE_IR.replace("        on_kill: ~\n", "")
    with pytest.raises(IRSemanticError, match="on_kill"):
        parse_and_validate(ir)


def test_gate_step_null_on_revise_raises():
    """on_revise must be a non-null step id — null means no rollback target."""
    ir = _VALID_GATE_IR.replace("        on_revise: s1", "        on_revise: ~")
    with pytest.raises(IRSemanticError, match="on_revise"):
        parse_and_validate(ir)


def test_gate_step_self_referential_on_revise_raises():
    """on_revise must not target the gate step itself."""
    ir = _VALID_GATE_IR.replace("        on_revise: s1", "        on_revise: gate")
    with pytest.raises(IRSemanticError, match="on_revise"):
        parse_and_validate(ir)


def test_gate_step_on_revise_forward_target_raises():
    """on_revise must target a topologically-earlier step, not a later one."""
    ir = """
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
  f:
    input: {}
    output: Out
    steps:
      - id: s1
        function: work
        inputs: {}
      - id: gate
        function: review
        on_approve: ~
        on_revise: s2
        on_kill: ~
        depends_on: [s1]
      - id: s2
        function: work
        inputs: {}
        depends_on: [gate]
"""
    with pytest.raises(IRSemanticError, match="topologically-earlier"):
        parse_and_validate(ir)


def test_gate_step_on_revise_backward_target_is_valid():
    """on_revise targeting a prior step is accepted (the normal rollback pattern)."""
    spec = parse_and_validate(_VALID_GATE_IR)
    gate_step = next(s for s in spec.flows["f"].steps if s.id == "gate")
    assert gate_step.on_revise == "s1"


def test_non_gate_step_with_on_approve_raises():
    """Routing fields on non-gate steps are forbidden."""
    ir = _VALID_GATE_IR.replace(
        "      - id: s1\n        function: work\n        inputs: {}",
        "      - id: s1\n        function: work\n        inputs: {}\n        on_approve: gate",
    )
    with pytest.raises(IRSemanticError, match="on_approve"):
        parse_and_validate(ir)
