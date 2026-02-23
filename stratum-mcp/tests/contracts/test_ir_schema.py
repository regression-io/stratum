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
