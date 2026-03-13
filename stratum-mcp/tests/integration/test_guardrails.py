"""Integration tests for pre-execution guardrails.

Guardrails are regex patterns declared on functions or inline steps that are
checked against the serialized step result before acceptance. If any pattern
matches, the result is blocked (like an ensure failure) and the step retries
or exhausts.
"""
import asyncio
import textwrap

import pytest

from stratum_mcp.executor import (
    _flows,
    _scan_guardrails,
    compile_guardrails,
    create_flow_state,
    get_current_step_info,
    process_step_result,
)
from stratum_mcp.server import stratum_plan, stratum_step_done
from stratum_mcp.spec import parse_and_validate, IRSemanticError


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


# ---------------------------------------------------------------------------
# Spec fixtures
# ---------------------------------------------------------------------------

_FUNC_GUARDRAIL_SPEC = textwrap.dedent("""\
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
        guardrails:
          - "password|secret|api_key"
          - "rm\\\\s+-rf"
    flows:
      main:
        input: {}
        output: Out
        steps:
          - id: s1
            function: work
            inputs: {}
""")

_INLINE_GUARDRAIL_SPEC = textwrap.dedent("""\
    version: "0.2"
    flows:
      main:
        input: {}
        steps:
          - id: s1
            agent: claude
            intent: "Do work"
            retries: 3
            guardrails:
              - "DROP\\\\s+TABLE"
              - "eval\\\\("
""")


@pytest.fixture(autouse=True)
def _cleanup():
    _flows.clear()
    yield
    _flows.clear()


# ---------------------------------------------------------------------------
# Unit: _scan_guardrails
# ---------------------------------------------------------------------------

def test_scan_guardrails_match():
    pats = compile_guardrails(["password", "secret"])
    hits = _scan_guardrails(pats, "my password is 123")
    assert hits == ["password"]


def test_scan_guardrails_no_match():
    pats = compile_guardrails(["password", "secret"])
    hits = _scan_guardrails(pats, "hello world")
    assert hits == []


def test_scan_guardrails_multiple_matches():
    pats = compile_guardrails(["foo", "bar"])
    hits = _scan_guardrails(pats, "foo and bar")
    assert hits == ["foo", "bar"]


def test_scan_guardrails_case_insensitive():
    pats = compile_guardrails(["password"])
    hits = _scan_guardrails(pats, "My PASSWORD is safe")
    assert hits == ["password"]


def test_compile_guardrails_rejects_bad_regex():
    """Malformed regex is caught at compile time, not silently skipped."""
    import re as re_mod
    with pytest.raises(re_mod.error):
        compile_guardrails(["[invalid"])


# ---------------------------------------------------------------------------
# Function-level guardrails
# ---------------------------------------------------------------------------

def test_guardrail_blocks_result():
    """Result containing guardrail pattern is blocked."""
    spec = parse_and_validate(_FUNC_GUARDRAIL_SPEC)
    state = create_flow_state(spec, "main", {}, raw_spec=_FUNC_GUARDRAIL_SPEC)
    get_current_step_info(state)

    status, violations = process_step_result(state, "s1", {"v": "my password is 123"})
    assert status == "guardrail_blocked"
    assert any("password" in v for v in violations)


def test_guardrail_allows_clean_result():
    """Result without guardrail patterns passes through."""
    spec = parse_and_validate(_FUNC_GUARDRAIL_SPEC)
    state = create_flow_state(spec, "main", {}, raw_spec=_FUNC_GUARDRAIL_SPEC)
    get_current_step_info(state)

    status, violations = process_step_result(state, "s1", {"v": "hello world"})
    assert status == "ok"
    assert violations == []


def test_guardrail_exhausts_retries():
    """Guardrail violations count against retry budget."""
    spec = parse_and_validate(_FUNC_GUARDRAIL_SPEC)
    state = create_flow_state(spec, "main", {}, raw_spec=_FUNC_GUARDRAIL_SPEC)
    get_current_step_info(state)

    # Burn all 3 retries
    for _ in range(2):
        status, _ = process_step_result(state, "s1", {"v": "has secret in it"})
        assert status == "guardrail_blocked"

    # 3rd attempt exhausts
    status, violations = process_step_result(state, "s1", {"v": "has secret in it"})
    assert status == "retries_exhausted"
    assert any("secret" in v for v in violations)


def test_guardrail_runs_before_ensure():
    """Guardrails run before ensure — a result that would pass ensure but fail
    guardrails should be blocked by guardrails."""
    spec_with_both = textwrap.dedent("""\
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
            ensure:
              - "result.v != ''"
            guardrails:
              - "forbidden_word"
        flows:
          main:
            input: {}
            output: Out
            steps:
              - id: s1
                function: work
                inputs: {}
    """)
    spec = parse_and_validate(spec_with_both)
    state = create_flow_state(spec, "main", {}, raw_spec=spec_with_both)
    get_current_step_info(state)

    # Would pass ensure (v is not empty) but should fail guardrails
    status, violations = process_step_result(state, "s1", {"v": "forbidden_word here"})
    assert status == "guardrail_blocked"


# ---------------------------------------------------------------------------
# Inline step guardrails
# ---------------------------------------------------------------------------

def test_inline_guardrail_blocks():
    spec = parse_and_validate(_INLINE_GUARDRAIL_SPEC)
    state = create_flow_state(spec, "main", {}, raw_spec=_INLINE_GUARDRAIL_SPEC)
    get_current_step_info(state)

    status, violations = process_step_result(state, "s1", {"code": "eval('bad')"})
    assert status == "guardrail_blocked"
    assert any("eval" in v for v in violations)


# ---------------------------------------------------------------------------
# MCP tool integration
# ---------------------------------------------------------------------------

def test_mcp_guardrail_blocked_response():
    """stratum_step_done returns guardrail_blocked status with retry info."""
    plan = _run(stratum_plan(_FUNC_GUARDRAIL_SPEC, "main", {}, None))
    flow_id = plan["flow_id"]

    result = _run(stratum_step_done(flow_id, "s1", {"v": "my api_key is XYZ"}, None))
    assert result["status"] == "guardrail_blocked"
    assert "violations" in result
    assert "retries_remaining" in result or "step_id" in result


# ---------------------------------------------------------------------------
# Semantic validation
# ---------------------------------------------------------------------------

def test_guardrails_forbidden_on_gate_function():
    gate_spec = textwrap.dedent("""\
        version: "0.2"
        functions:
          gate_fn:
            mode: gate
            guardrails:
              - "pattern"
        flows:
          main:
            input: {}
            steps:
              - id: g1
                function: gate_fn
                on_approve: ~
                on_revise: g1
                on_kill: ~
    """)
    with pytest.raises(IRSemanticError, match="guardrails"):
        parse_and_validate(gate_spec)


def test_guardrails_forbidden_on_function_step():
    """Step-level guardrails forbidden when step uses a function (must be on function)."""
    step_guard_spec = textwrap.dedent("""\
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
                guardrails:
                  - "pattern"
    """)
    with pytest.raises(IRSemanticError, match="guardrails.*must be on the function"):
        parse_and_validate(step_guard_spec)


def test_on_fail_routes_on_guardrail_exhaustion():
    """When guardrails exhaust retries with on_fail, route to recovery step."""
    spec = textwrap.dedent("""\
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
            retries: 1
            guardrails:
              - "blocked_word"
            ensure:
              - "result.v != ''"
        flows:
          main:
            input: {}
            output: Out
            steps:
              - id: s1
                function: work
                inputs: {}
                on_fail: s2
              - id: s2
                agent: claude
                intent: "Recover"
    """)
    parsed = parse_and_validate(spec)
    state = create_flow_state(parsed, "main", {}, raw_spec=spec)
    get_current_step_info(state)

    status, _ = process_step_result(state, "s1", {"v": "blocked_word"})
    assert status == "on_fail_routed"


def test_guardrails_only_on_fail_accepted():
    """Step with guardrails + on_fail but NO ensure should be valid (guardrails can trigger on_fail)."""
    spec = textwrap.dedent("""\
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
            retries: 1
            guardrails:
              - "blocked"
        flows:
          main:
            input: {}
            output: Out
            steps:
              - id: s1
                function: work
                inputs: {}
                on_fail: s2
              - id: s2
                agent: claude
                intent: "Recover"
    """)
    # Should NOT raise — guardrails make on_fail reachable
    parsed = parse_and_validate(spec)
    state = create_flow_state(parsed, "main", {}, raw_spec=spec)
    get_current_step_info(state)

    # Verify it actually routes
    status, _ = process_step_result(state, "s1", {"v": "blocked content"})
    assert status == "on_fail_routed"


def test_invalid_regex_rejected_at_parse_time():
    """Malformed guardrail regex is caught at parse time, not silently skipped."""
    spec = textwrap.dedent("""\
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
            guardrails:
              - "[invalid"
        flows:
          main:
            input: {}
            output: Out
            steps:
              - id: s1
                function: work
                inputs: {}
    """)
    with pytest.raises(IRSemanticError, match="not a valid regex"):
        parse_and_validate(spec)


def test_empty_guardrail_pattern_rejected():
    """Empty string guardrail pattern is rejected by schema."""
    spec = textwrap.dedent("""\
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
            guardrails:
              - ""
        flows:
          main:
            input: {}
            output: Out
            steps:
              - id: s1
                function: work
                inputs: {}
    """)
    from stratum_mcp.errors import IRValidationError
    with pytest.raises(IRValidationError):
        parse_and_validate(spec)
