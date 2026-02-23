"""End-to-end round-trip tests: plan → step_done loop → complete."""
import pytest
from unittest.mock import MagicMock

from stratum_mcp.server import stratum_plan, stratum_step_done, stratum_audit


VALID_IR = """
version: "0.1"
contracts:
  SentimentResult:
    label: {type: string}
    confidence: {type: number}
    reasoning: {type: string}
functions:
  classify:
    mode: infer
    intent: "Classify the sentiment of the given text"
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


@pytest.mark.asyncio
async def test_roundtrip_single_step_flow():
    """Full round-trip: plan → step_done → complete with expected output."""
    ctx = MagicMock()
    plan = await stratum_plan(VALID_IR, "run", {"text": "I love this!"}, ctx)

    assert plan["status"] == "execute_step"
    assert plan["step_id"] == "s1"
    assert plan["function"] == "classify"
    assert plan["inputs"] == {"text": "I love this!"}
    assert plan["output_contract"] == "SentimentResult"
    flow_id = plan["flow_id"]

    result = await stratum_step_done(
        flow_id, "s1",
        {"label": "positive", "confidence": 0.9, "reasoning": "tone is positive"},
        ctx,
    )

    assert result["status"] == "complete"
    assert result["output"] == {"label": "positive", "confidence": 0.9, "reasoning": "tone is positive"}
    assert len(result["trace"]) == 1
    assert result["trace"][0]["step_id"] == "s1"
    assert result["trace"][0]["function_name"] == "classify"
    assert result["trace"][0]["attempts"] == 1
    assert isinstance(result["trace"][0]["duration_ms"], int)

    # flow_id is a valid UUID
    import uuid
    uuid.UUID(flow_id)


@pytest.mark.asyncio
async def test_roundtrip_audit_after_completion():
    ctx = MagicMock()
    plan = await stratum_plan(VALID_IR, "run", {"text": "This is awful"}, ctx)
    flow_id = plan["flow_id"]

    await stratum_step_done(
        flow_id, "s1",
        {"label": "negative", "confidence": 0.8, "reasoning": "tone is negative"},
        ctx,
    )

    audit = await stratum_audit(flow_id, ctx)
    assert audit["status"] == "complete"
    assert audit["steps_completed"] == 1
    assert audit["trace"][0]["step_id"] == "s1"
    assert isinstance(audit["total_duration_ms"], int)


@pytest.mark.asyncio
async def test_roundtrip_two_step_chained_refs():
    """Two-step flow: s2 reads a field from s1's output via $.steps.s1.output.label."""
    TWO_STEP_IR = """
version: "0.1"
contracts:
  SentimentResult:
    label: {type: string}
    confidence: {type: number}
  SummaryResult:
    summary: {type: string}
functions:
  classify:
    mode: infer
    intent: "Classify sentiment"
    input: {text: {type: string}}
    output: SentimentResult
    retries: 1
  summarize:
    mode: infer
    intent: "Summarize the sentiment label"
    input: {label: {type: string}}
    output: SummaryResult
    retries: 1
flows:
  pipeline:
    input: {text: {type: string}}
    output: SummaryResult
    steps:
      - id: s1
        function: classify
        inputs: {text: "$.input.text"}
      - id: s2
        function: summarize
        inputs: {label: "$.steps.s1.output.label"}
        depends_on: [s1]
"""
    ctx = MagicMock()
    plan = await stratum_plan(TWO_STEP_IR, "pipeline", {"text": "Great product!"}, ctx)
    flow_id = plan["flow_id"]

    assert plan["step_id"] == "s1"
    assert plan["step_number"] == 1
    assert plan["total_steps"] == 2

    step2 = await stratum_step_done(
        flow_id, "s1", {"label": "positive", "confidence": 0.9}, ctx
    )
    assert step2["status"] == "execute_step"
    assert step2["step_id"] == "s2"
    assert step2["step_number"] == 2
    assert step2["inputs"]["label"] == "positive"  # resolved from s1's output

    done = await stratum_step_done(
        flow_id, "s2", {"summary": "The text is positive."}, ctx
    )
    assert done["status"] == "complete"
    assert done["output"] == {"summary": "The text is positive."}
    assert len(done["trace"]) == 2
    assert done["trace"][0]["step_id"] == "s1"
    assert done["trace"][1]["step_id"] == "s2"


@pytest.mark.asyncio
async def test_roundtrip_ensure_failure_then_success():
    """Ensure failure on first attempt, success on retry."""
    IR_WITH_ENSURE = """
version: "0.1"
contracts:
  Result:
    value: {type: string}
functions:
  extract:
    mode: infer
    intent: "Extract a non-empty value"
    input: {text: {type: string}}
    output: Result
    ensure:
      - "result.value != ''"
    retries: 3
flows:
  run:
    input: {text: {type: string}}
    output: Result
    steps:
      - id: s1
        function: extract
        inputs: {text: "$.input.text"}
"""
    ctx = MagicMock()
    plan = await stratum_plan(IR_WITH_ENSURE, "run", {"text": "hello"}, ctx)
    flow_id = plan["flow_id"]

    # First attempt fails ensure
    fail = await stratum_step_done(flow_id, "s1", {"value": ""}, ctx)
    assert fail["status"] == "ensure_failed"
    assert fail["retries_remaining"] == 2
    assert any("result.value != ''" in v for v in fail["violations"])

    # Second attempt passes
    done = await stratum_step_done(flow_id, "s1", {"value": "extracted"}, ctx)
    assert done["status"] == "complete"
    assert done["output"] == {"value": "extracted"}
    assert done["trace"][0]["attempts"] == 2


@pytest.mark.asyncio
async def test_roundtrip_flow_not_found():
    ctx = MagicMock()
    result = await stratum_plan(VALID_IR, "nonexistent_flow", {}, ctx)
    assert result["status"] == "error"
    assert result["error_type"] == "execution_error"
    assert "not found" in result["message"]
