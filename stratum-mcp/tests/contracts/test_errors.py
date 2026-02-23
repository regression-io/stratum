"""Tests for IR error types and MCP error translation."""
from stratum_mcp.errors import (
    IRParseError,
    IRValidationError,
    IRSemanticError,
    MCPExecutionError,
    exception_to_mcp_error,
)


def test_ir_parse_error_maps_correctly():
    err = exception_to_mcp_error(IRParseError(raw_error="bad indent"))
    assert err["error_type"] == "ir_parse_error"
    assert "bad indent" in err["message"]
    assert err["success"] is False


def test_ir_validation_error_maps_correctly():
    err = exception_to_mcp_error(IRValidationError(
        path="flows.run.steps",
        message="minItems violation",
        suggestion="Add at least one step",
    ))
    assert err["error_type"] == "ir_validation_error"
    assert err["path"] == "flows.run.steps"
    assert err["message"] == "minItems violation"
    assert err["suggestion"] == "Add at least one step"
    assert err["success"] is False


def test_ir_semantic_error_maps_correctly():
    err = exception_to_mcp_error(IRSemanticError("undefined ref", path="functions.f.output"))
    assert err["error_type"] == "ir_semantic_error"
    assert err["path"] == "functions.f.output"
    assert "undefined ref" in err["message"]
    assert err["success"] is False


def test_mcp_execution_error_maps_correctly():
    err = exception_to_mcp_error(MCPExecutionError("Flow 'run' not found in spec"))
    assert err["error_type"] == "execution_error"
    assert "not found" in err["message"]
    assert err["success"] is False


def test_unknown_exception_maps_to_internal_error():
    err = exception_to_mcp_error(ValueError("boom"))
    assert err["error_type"] == "internal_error"
    assert "boom" not in err["message"]  # must not leak internals
    assert err["success"] is False
