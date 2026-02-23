"""Integration tests for MCP server tool registration and controller behavior."""
import pytest
from unittest.mock import MagicMock


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
    ensure:
      - "result.label != ''"
    retries: 2
flows:
  run:
    input: {text: {type: string}}
    output: SentimentResult
    steps:
      - id: s1
        function: classify
        inputs: {text: "$.input.text"}
"""

TWO_STEP_IR = """
version: "0.1"
contracts:
  SentimentResult:
    label: {type: string}
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
    intent: "Summarize the label"
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


@pytest.mark.asyncio
async def test_four_tools_registered():
    from stratum_mcp.server import mcp
    tool_names = {t.name for t in await mcp.list_tools()}
    assert "stratum_validate" in tool_names
    assert "stratum_plan" in tool_names
    assert "stratum_step_done" in tool_names
    assert "stratum_audit" in tool_names


@pytest.mark.asyncio
async def test_validate_accepts_valid_ir():
    from stratum_mcp.server import stratum_validate
    ctx = MagicMock()
    result = await stratum_validate(VALID_IR, ctx)
    assert result["valid"] is True
    assert result["errors"] == []


@pytest.mark.asyncio
async def test_validate_rejects_invalid_yaml():
    from stratum_mcp.server import stratum_validate
    ctx = MagicMock()
    result = await stratum_validate("version: [\n  bad", ctx)
    assert result["valid"] is False
    assert result["errors"][0]["error_type"] == "ir_parse_error"


@pytest.mark.asyncio
async def test_validate_rejects_wrong_version():
    from stratum_mcp.server import stratum_validate
    ctx = MagicMock()
    result = await stratum_validate('version: "99.0"\n', ctx)
    assert result["valid"] is False
    assert result["errors"][0]["error_type"] == "ir_validation_error"


@pytest.mark.asyncio
async def test_plan_returns_first_step():
    from stratum_mcp.server import stratum_plan
    ctx = MagicMock()
    result = await stratum_plan(VALID_IR, "run", {"text": "hello"}, ctx)
    assert result["status"] == "execute_step"
    assert result["step_id"] == "s1"
    assert result["function"] == "classify"
    assert result["mode"] == "infer"
    assert result["inputs"] == {"text": "hello"}
    assert result["output_contract"] == "SentimentResult"
    assert result["step_number"] == 1
    assert result["total_steps"] == 1
    assert "flow_id" in result


@pytest.mark.asyncio
async def test_plan_flow_not_found_returns_error():
    from stratum_mcp.server import stratum_plan
    ctx = MagicMock()
    result = await stratum_plan(VALID_IR, "nonexistent", {}, ctx)
    assert result["status"] == "error"
    assert result["error_type"] == "execution_error"


@pytest.mark.asyncio
async def test_step_done_completes_single_step_flow():
    from stratum_mcp.server import stratum_plan, stratum_step_done
    ctx = MagicMock()
    plan = await stratum_plan(VALID_IR, "run", {"text": "hello"}, ctx)
    flow_id = plan["flow_id"]

    result = await stratum_step_done(
        flow_id, "s1", {"label": "positive", "confidence": 0.9}, ctx
    )
    assert result["status"] == "complete"
    assert result["output"] == {"label": "positive", "confidence": 0.9}
    assert len(result["trace"]) == 1
    assert result["trace"][0]["step_id"] == "s1"
    assert result["trace"][0]["attempts"] == 1


@pytest.mark.asyncio
async def test_step_done_ensure_failure_returns_retry():
    from stratum_mcp.server import stratum_plan, stratum_step_done
    ctx = MagicMock()
    plan = await stratum_plan(VALID_IR, "run", {"text": "hello"}, ctx)
    flow_id = plan["flow_id"]

    # label is empty — fails ensure "result.label != ''"
    result = await stratum_step_done(flow_id, "s1", {"label": "", "confidence": 0.0}, ctx)
    assert result["status"] == "ensure_failed"
    assert len(result["violations"]) > 0
    assert result["retries_remaining"] == 1  # retries=2, used 1 attempt


@pytest.mark.asyncio
async def test_step_done_retries_exhausted():
    from stratum_mcp.server import stratum_plan, stratum_step_done
    ctx = MagicMock()
    plan = await stratum_plan(VALID_IR, "run", {"text": "hello"}, ctx)
    flow_id = plan["flow_id"]

    bad = {"label": "", "confidence": 0.0}
    await stratum_step_done(flow_id, "s1", bad, ctx)  # attempt 1 — ensure_failed
    result = await stratum_step_done(flow_id, "s1", bad, ctx)  # attempt 2 — exhausted
    assert result["status"] == "error"
    assert result["error_type"] == "retries_exhausted"


@pytest.mark.asyncio
async def test_step_done_advances_two_step_flow():
    from stratum_mcp.server import stratum_plan, stratum_step_done
    ctx = MagicMock()
    plan = await stratum_plan(TWO_STEP_IR, "pipeline", {"text": "great!"}, ctx)
    flow_id = plan["flow_id"]
    assert plan["step_id"] == "s1"

    # Complete s1
    step2 = await stratum_step_done(flow_id, "s1", {"label": "positive"}, ctx)
    assert step2["status"] == "execute_step"
    assert step2["step_id"] == "s2"
    # s2 input is resolved from s1's output
    assert step2["inputs"]["label"] == "positive"

    # Complete s2
    done = await stratum_step_done(flow_id, "s2", {"summary": "The text is positive."}, ctx)
    assert done["status"] == "complete"
    assert done["output"] == {"summary": "The text is positive."}
    assert len(done["trace"]) == 2


@pytest.mark.asyncio
async def test_step_done_unknown_flow_id():
    from stratum_mcp.server import stratum_step_done
    ctx = MagicMock()
    result = await stratum_step_done("no-such-id", "s1", {}, ctx)
    assert result["status"] == "error"
    assert result["error_type"] == "flow_not_found"


@pytest.mark.asyncio
async def test_audit_returns_trace():
    from stratum_mcp.server import stratum_plan, stratum_step_done, stratum_audit
    ctx = MagicMock()
    plan = await stratum_plan(VALID_IR, "run", {"text": "hello"}, ctx)
    flow_id = plan["flow_id"]
    await stratum_step_done(flow_id, "s1", {"label": "positive", "confidence": 0.9}, ctx)

    audit = await stratum_audit(flow_id, ctx)
    assert audit["flow_id"] == flow_id
    assert audit["status"] == "complete"
    assert audit["steps_completed"] == 1
    assert audit["total_steps"] == 1
    assert len(audit["trace"]) == 1


@pytest.mark.asyncio
async def test_audit_unknown_flow_id():
    from stratum_mcp.server import stratum_audit
    ctx = MagicMock()
    result = await stratum_audit("no-such-id", ctx)
    assert result["error_type"] == "flow_not_found"
