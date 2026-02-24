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
async def test_roundtrip_output_schema_passes():
    """Step with output_schema: conforming result advances to complete."""
    IR = """
version: "0.1"
contracts:
  Out:
    path: {type: string}
functions:
  write_doc:
    mode: compute
    intent: "Write a design doc"
    input: {name: {type: string}}
    output: Out
flows:
  run:
    input: {name: {type: string}}
    output: Out
    steps:
      - id: s1
        function: write_doc
        inputs: {name: "$.input.name"}
        output_schema:
          type: object
          required: [path]
          properties:
            path: {type: string}
            word_count: {type: integer}
"""
    ctx = MagicMock()
    plan = await stratum_plan(IR, "run", {"name": "feature-x"}, ctx)
    flow_id = plan["flow_id"]

    done = await stratum_step_done(flow_id, "s1", {"path": "/tmp/design.md", "word_count": 512}, ctx)
    assert done["status"] == "complete"


@pytest.mark.asyncio
async def test_roundtrip_output_schema_missing_required_field():
    """Step with output_schema: missing required field returns schema_failed."""
    IR = """
version: "0.1"
contracts:
  Out:
    path: {type: string}
functions:
  write_doc:
    mode: compute
    intent: "Write a design doc"
    input: {name: {type: string}}
    output: Out
    retries: 3
flows:
  run:
    input: {name: {type: string}}
    output: Out
    steps:
      - id: s1
        function: write_doc
        inputs: {name: "$.input.name"}
        output_schema:
          type: object
          required: [path]
          properties:
            path: {type: string}
"""
    ctx = MagicMock()
    plan = await stratum_plan(IR, "run", {"name": "feature-x"}, ctx)
    flow_id = plan["flow_id"]

    # Result missing required 'path' field
    fail = await stratum_step_done(flow_id, "s1", {"word_count": 100}, ctx)
    assert fail["status"] == "schema_failed"
    assert fail["retries_remaining"] == 2
    assert any("output_schema violation" in v for v in fail["violations"])
    assert any("path" in v for v in fail["violations"])

    # Retry with correct result
    done = await stratum_step_done(flow_id, "s1", {"path": "/tmp/design.md"}, ctx)
    assert done["status"] == "complete"


@pytest.mark.asyncio
async def test_roundtrip_output_schema_exhausts_retries():
    """Step with output_schema: repeated failures exhaust retries."""
    IR = """
version: "0.1"
contracts:
  Out:
    path: {type: string}
functions:
  write_doc:
    mode: compute
    intent: "Write a design doc"
    input: {name: {type: string}}
    output: Out
    retries: 2
flows:
  run:
    input: {name: {type: string}}
    output: Out
    steps:
      - id: s1
        function: write_doc
        inputs: {name: "$.input.name"}
        output_schema:
          type: object
          required: [path]
          properties:
            path: {type: string}
"""
    ctx = MagicMock()
    plan = await stratum_plan(IR, "run", {"name": "feature-x"}, ctx)
    flow_id = plan["flow_id"]

    bad = {"word_count": 0}
    await stratum_step_done(flow_id, "s1", bad, ctx)  # attempt 1 → schema_failed
    result = await stratum_step_done(flow_id, "s1", bad, ctx)  # attempt 2 → retries_exhausted
    assert result["status"] == "error"
    assert result["error_type"] == "retries_exhausted"
    assert any("output_schema violation" in v for v in result["violations"])


@pytest.mark.asyncio
async def test_roundtrip_output_schema_checked_before_ensures():
    """Schema validation runs before ensures — schema error surfaces first."""
    IR = """
version: "0.1"
contracts:
  Out:
    path: {type: string}
functions:
  write_doc:
    mode: compute
    intent: "Write a design doc"
    input: {name: {type: string}}
    output: Out
    ensure:
      - "result.path != ''"
    retries: 3
flows:
  run:
    input: {name: {type: string}}
    output: Out
    steps:
      - id: s1
        function: write_doc
        inputs: {name: "$.input.name"}
        output_schema:
          type: object
          required: [path]
          properties:
            path: {type: string}
"""
    ctx = MagicMock()
    plan = await stratum_plan(IR, "run", {"name": "feature-x"}, ctx)
    flow_id = plan["flow_id"]

    # Missing required field — should get schema_failed, not ensure_failed
    fail = await stratum_step_done(flow_id, "s1", {"wrong_key": "value"}, ctx)
    assert fail["status"] == "schema_failed"


@pytest.mark.asyncio
async def test_roundtrip_output_schema_retries_1_exhausted_on_first_failure():
    """retries=1 means 1 total attempt — schema failure exhausts immediately."""
    IR = """
version: "0.1"
contracts:
  Out:
    path: {type: string}
functions:
  write_doc:
    mode: compute
    intent: "Write a doc"
    input: {name: {type: string}}
    output: Out
    retries: 1
flows:
  run:
    input: {name: {type: string}}
    output: Out
    steps:
      - id: s1
        function: write_doc
        inputs: {name: "$.input.name"}
        output_schema:
          type: object
          required: [path]
          properties:
            path: {type: string}
"""
    ctx = MagicMock()
    plan = await stratum_plan(IR, "run", {"name": "x"}, ctx)
    flow_id = plan["flow_id"]

    result = await stratum_step_done(flow_id, "s1", {"wrong": "value"}, ctx)
    assert result["status"] == "error"
    assert result["error_type"] == "retries_exhausted"


@pytest.mark.asyncio
async def test_roundtrip_schema_fail_then_ensure_fail_then_pass():
    """Mixed retry path: attempt 1 → schema_failed, attempt 2 → ensure_failed, attempt 3 → complete."""
    IR = """
version: "0.1"
contracts:
  Out:
    path: {type: string}
functions:
  write_doc:
    mode: compute
    intent: "Write a doc"
    input: {name: {type: string}}
    output: Out
    ensure:
      - "result.path != ''"
    retries: 3
flows:
  run:
    input: {name: {type: string}}
    output: Out
    steps:
      - id: s1
        function: write_doc
        inputs: {name: "$.input.name"}
        output_schema:
          type: object
          required: [path]
          properties:
            path: {type: string}
"""
    ctx = MagicMock()
    plan = await stratum_plan(IR, "run", {"name": "x"}, ctx)
    flow_id = plan["flow_id"]

    # Attempt 1: missing required field → schema_failed
    r1 = await stratum_step_done(flow_id, "s1", {"wrong": "value"}, ctx)
    assert r1["status"] == "schema_failed"
    assert r1["retries_remaining"] == 2

    # Attempt 2: schema passes, ensure fails (empty path)
    r2 = await stratum_step_done(flow_id, "s1", {"path": ""}, ctx)
    assert r2["status"] == "ensure_failed"
    assert r2["retries_remaining"] == 1

    # Attempt 3: schema and ensure both pass
    r3 = await stratum_step_done(flow_id, "s1", {"path": "/tmp/out.md"}, ctx)
    assert r3["status"] == "complete"
    assert r3["trace"][0]["attempts"] == 3


@pytest.mark.asyncio
async def test_roundtrip_flow_not_found():
    ctx = MagicMock()
    result = await stratum_plan(VALID_IR, "nonexistent_flow", {}, ctx)
    assert result["status"] == "error"
    assert result["error_type"] == "execution_error"
    assert "not found" in result["message"]
