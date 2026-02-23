"""IR error types and MCP error translation."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


# ---------------------------------------------------------------------------
# IR error types
# ---------------------------------------------------------------------------

@dataclass
class IRParseError(Exception):
    """YAML could not be parsed."""
    raw_error: str

    def __post_init__(self) -> None:
        super().__init__(self.raw_error)


@dataclass
class IRValidationError(Exception):
    """Structured schema validation failure."""
    path: str           # dot-notation JSON path, e.g. "flows.process_feedback.steps"
    message: str
    suggestion: str

    def __post_init__(self) -> None:
        super().__init__(self.message)


class IRSemanticError(Exception):
    """Schema-valid but semantically invalid (undefined refs, missing contracts)."""
    def __init__(self, message: str, path: str = "") -> None:
        self.path = path
        super().__init__(message)


class MCPExecutionError(Exception):
    """Runtime error during flow controller execution."""


# ---------------------------------------------------------------------------
# MCP error translation
# ---------------------------------------------------------------------------

def exception_to_mcp_error(exc: Exception) -> dict[str, Any]:
    """
    Single translation point. Maps any exception to a structured MCP response dict.
    Never raises. Never exposes internal stack traces.
    """
    if isinstance(exc, IRParseError):
        return {
            "success": False,
            "error_type": "ir_parse_error",
            "message": f"YAML syntax error: {exc.raw_error}",
            "suggestion": "Check YAML syntax — indentation, colons, quoting.",
        }
    if isinstance(exc, IRValidationError):
        return {
            "success": False,
            "error_type": "ir_validation_error",
            "path": exc.path,
            "message": exc.message,
            "suggestion": exc.suggestion,
        }
    if isinstance(exc, IRSemanticError):
        return {
            "success": False,
            "error_type": "ir_semantic_error",
            "path": exc.path,
            "message": str(exc),
        }
    if isinstance(exc, MCPExecutionError):
        return {
            "success": False,
            "error_type": "execution_error",
            "message": str(exc),
        }
    return {
        "success": False,
        "error_type": "internal_error",
        "message": "An unexpected error occurred.",
    }
