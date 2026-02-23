"""Prompt compiler — deterministic assembly and SHA-256 hash."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def _format_value(value: Any) -> str:
    """
    Format a value for inline prompt display.

    Contract instances are rendered as a dict of their public attributes.
    """
    if isinstance(value, str):
        return value
    if hasattr(value, "__dict__"):
        public = {k: v for k, v in value.__dict__.items() if not k.startswith("_")}
        return str(public)
    return str(value)


def compile_prompt(
    intent: str,
    context: list[str],
    inputs: dict[str, Any],
    opaque_fields: set[str],
    retry_reasons: list[str],
) -> str:
    """
    Assemble the prompt string sent to the LLM.

    Assembly order (per spec §4.1):
      1. intent
      2. context annotations (in declaration order)
      3. non-opaque input bindings
      4. retry context (only when retry_reasons is non-empty)
      5. opaque data reference (only when opaque_fields is non-empty)

    The output schema is NOT included — it is enforced via the structured
    outputs API (tool_choice).

    Spec §4.2: raises StratumCompileError if an opaque field name appears as
    an inline {field} reference in intent or context strings.
    """
    # Spec §4.2: raise StratumCompileError if an opaque field is referenced
    # inline in intent or context strings.
    if opaque_fields:
        from .exceptions import StratumCompileError
        for text in [intent, *context]:
            for field_name in opaque_fields:
                if f"{{{field_name}}}" in text:
                    raise StratumCompileError(
                        f"opaque field '{field_name}' must not appear in inline "
                        "string interpolation (intent or context). "
                        "Opaque fields are passed as structured attachments only."
                    )
    parts: list[str] = []

    # 1. Intent
    parts.append(intent)

    # 2. Context annotations
    for ctx in context:
        if ctx:
            parts.append(ctx)

    # 3. Non-opaque input bindings
    non_opaque = {k: v for k, v in inputs.items() if k not in opaque_fields}
    if non_opaque:
        parts.append("Inputs:")
        for key, value in non_opaque.items():
            parts.append(f"  {key}: {_format_value(value)}")

    # 4. Retry context — only on retries (attempt > 0)
    if retry_reasons:
        parts.append("Previous attempt failed:")
        for reason in retry_reasons:
            parts.append(f"  - {reason}")
        parts.append("Fix these issues specifically.")

    # 5. Opaque field reference
    if opaque_fields:
        names = ", ".join(sorted(opaque_fields))
        parts.append(f"See attached data for: {names}")

    return "\n".join(parts)


def prompt_hash(prompt: str) -> str:
    """Return the first 12 hex characters of the SHA-256 of the prompt string."""
    return hashlib.sha256(prompt.encode()).hexdigest()[:12]


def build_opaque_attachment(
    inputs: dict[str, Any],
    opaque_fields: set[str],
) -> dict[str, Any] | None:
    """
    Return a dict of {field_name: value} for all opaque fields, or None if
    there are no opaque fields.
    """
    result = {k: v for k, v in inputs.items() if k in opaque_fields}
    return result if result else None
