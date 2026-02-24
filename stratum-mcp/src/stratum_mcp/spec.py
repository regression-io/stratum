"""IR types, JSON Schema registry, parser, and validator for .stratum.yaml v0.1."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

import yaml
from jsonschema import Draft202012Validator
from jsonschema.exceptions import best_match

from .errors import IRParseError, IRValidationError, IRSemanticError


# ---------------------------------------------------------------------------
# IR dataclasses (frozen)
# ---------------------------------------------------------------------------
# NOTE: frozen=True prevents attribute reassignment but NOT in-place mutation of
# contained list/dict fields (e.g., fn.ensure.append(...) is not blocked).
# No current code path mutates these after construction. If v0.2 adds parallel
# execution or schema extension, convert list fields to tuple and dict fields to
# types.MappingProxyType for true deep immutability.
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class IRBudgetDef:
    ms: int | None = None
    usd: float | None = None


@dataclass(frozen=True)
class IRContractDef:
    name: str
    fields: dict[str, Any]


@dataclass(frozen=True)
class IRFunctionDef:
    name: str
    mode: Literal["infer", "compute"]
    intent: str
    input_schema: dict[str, Any]
    output_contract: str
    ensure: list[str]
    budget: IRBudgetDef | None
    retries: int
    model: str | None


@dataclass(frozen=True)
class IRStepDef:
    id: str
    function: str
    inputs: dict[str, str]
    depends_on: list[str]
    output_schema: dict[str, Any] | None = None


@dataclass(frozen=True)
class IRFlowDef:
    name: str
    input_schema: dict[str, Any]
    output_contract: str
    budget: IRBudgetDef | None
    steps: list[IRStepDef]


@dataclass(frozen=True)
class IRSpec:
    version: str
    contracts: dict[str, IRContractDef]
    functions: dict[str, IRFunctionDef]
    flows: dict[str, IRFlowDef]


# ---------------------------------------------------------------------------
# JSON Schema registry
# ---------------------------------------------------------------------------

_IR_SCHEMA_V01: dict = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "required": ["version"],
    "additionalProperties": False,
    "properties": {
        "version": {"type": "string", "const": "0.1"},
        "contracts": {
            "type": "object",
            "additionalProperties": {
                "type": "object",
                "additionalProperties": {
                    "type": "object",
                    "properties": {
                        "type": {"type": "string"},
                        "values": {"type": "array"},
                    },
                    "required": ["type"],
                }
            }
        },
        "functions": {
            "type": "object",
            "additionalProperties": {"$ref": "#/$defs/FunctionDef"}
        },
        "flows": {
            "type": "object",
            "additionalProperties": {"$ref": "#/$defs/FlowDef"}
        }
    },
    "$defs": {
        "BudgetDef": {
            "type": "object",
            "properties": {
                "ms": {"type": "integer", "minimum": 1},
                "usd": {"type": "number", "minimum": 0},
            },
            "additionalProperties": False,
        },
        "FunctionDef": {
            "type": "object",
            "required": ["mode", "intent", "input", "output"],
            "additionalProperties": False,
            "properties": {
                "mode": {"type": "string", "enum": ["infer", "compute"]},
                "intent": {"type": "string", "minLength": 1},
                "input": {"type": "object"},
                "output": {"type": "string"},
                "ensure": {"type": "array", "items": {"type": "string"}},
                "budget": {"$ref": "#/$defs/BudgetDef"},
                "retries": {"type": "integer", "minimum": 1},
                "model": {"type": "string"},
            }
        },
        "StepDef": {
            "type": "object",
            "required": ["id", "function", "inputs"],
            "additionalProperties": False,
            "properties": {
                "id": {"type": "string"},
                "function": {"type": "string"},
                "inputs": {"type": "object", "additionalProperties": {"type": "string"}},
                "depends_on": {"type": "array", "items": {"type": "string"}},
                "output_schema": {"type": "object"},
            }
        },
        "FlowDef": {
            "type": "object",
            "required": ["input", "output", "steps"],
            "additionalProperties": False,
            "properties": {
                "input": {"type": "object"},
                "output": {"type": "string"},
                "budget": {"$ref": "#/$defs/BudgetDef"},
                "steps": {"type": "array", "items": {"$ref": "#/$defs/StepDef"}, "minItems": 1}
            }
        }
    }
}

# Version registry — add "0.2": _IR_SCHEMA_V02 when v0.2 lands
SCHEMAS: dict[str, dict] = {"0.1": _IR_SCHEMA_V01}


# ---------------------------------------------------------------------------
# Public parse entry point
# ---------------------------------------------------------------------------

def parse_and_validate(raw_yaml: str) -> IRSpec:
    """
    Parse raw YAML → JSON Schema validation → semantic validation → IRSpec.
    Raises IRParseError, IRValidationError, or IRSemanticError.
    """
    doc = _parse_yaml(raw_yaml)
    version = str(doc.get("version", ""))
    schema = SCHEMAS.get(version)
    if schema is None:
        raise IRValidationError(
            path="version",
            message=f"Unknown IR version: {version!r}",
            suggestion=f"Use version: \"{list(SCHEMAS.keys())[-1]}\"",
        )
    _validate_schema(doc, schema)
    spec = _build_spec(doc)
    _validate_semantics(spec)
    return spec


def _parse_yaml(raw: str) -> dict[str, Any]:
    if not raw or not raw.strip():
        raise IRParseError(raw_error="Empty or blank YAML input")
    try:
        return yaml.safe_load(raw) or {}
    except yaml.YAMLError as exc:
        raise IRParseError(raw_error=str(exc)) from exc


def _validate_schema(doc: dict, schema: dict) -> None:
    validator = Draft202012Validator(schema)
    errors = list(validator.iter_errors(doc))
    if not errors:
        return
    worst = best_match(errors)
    path = ".".join(str(p) for p in worst.path) if worst.path else "root"
    suggestion = _suggest_fix(worst)
    raise IRValidationError(path=path, message=worst.message, suggestion=suggestion)


def _build_spec(doc: dict) -> IRSpec:
    contracts = {
        name: IRContractDef(name=name, fields=fields)
        for name, fields in (doc.get("contracts") or {}).items()
    }
    functions = {
        name: _build_function(name, d)
        for name, d in (doc.get("functions") or {}).items()
    }
    flows = {
        name: _build_flow(name, d)
        for name, d in (doc.get("flows") or {}).items()
    }
    return IRSpec(version=doc["version"], contracts=contracts, functions=functions, flows=flows)


def _build_function(name: str, d: dict) -> IRFunctionDef:
    b = d.get("budget")
    budget = IRBudgetDef(ms=b.get("ms"), usd=b.get("usd")) if b else None
    return IRFunctionDef(
        name=name,
        mode=d["mode"],
        intent=d["intent"],
        input_schema=d.get("input", {}),
        output_contract=d["output"],
        ensure=d.get("ensure", []),
        budget=budget,
        retries=d.get("retries", 3),
        model=d.get("model"),
    )


def _build_flow(name: str, d: dict) -> IRFlowDef:
    b = d.get("budget")
    budget = IRBudgetDef(ms=b.get("ms"), usd=b.get("usd")) if b else None
    steps = [
        IRStepDef(
            id=s["id"],
            function=s["function"],
            inputs=s.get("inputs", {}),
            depends_on=s.get("depends_on", []),
            output_schema=s.get("output_schema"),
        )
        for s in d.get("steps", [])
    ]
    return IRFlowDef(
        name=name,
        input_schema=d.get("input", {}),
        output_contract=d["output"],
        budget=budget,
        steps=steps,
    )


def _validate_semantics(spec: IRSpec) -> None:
    known_contracts = set(spec.contracts)
    known_functions = set(spec.functions)
    for fn_name, fn in spec.functions.items():
        if fn.output_contract not in known_contracts:
            raise IRSemanticError(
                f"Function '{fn_name}' output contract '{fn.output_contract}' not defined",
                path=f"functions.{fn_name}.output"
            )
    for flow_name, flow in spec.flows.items():
        if flow.output_contract not in known_contracts:
            raise IRSemanticError(
                f"Flow '{flow_name}' output contract '{flow.output_contract}' not defined",
                path=f"flows.{flow_name}.output"
            )
        # Collect all step IDs first so depends_on can reference steps in any YAML order.
        # Existence is validated here; cycle detection is handled by _topological_sort.
        known_step_ids = {step.id for step in flow.steps}
        for step in flow.steps:
            if step.function not in known_functions:
                raise IRSemanticError(
                    f"Step '{step.id}' references undefined function '{step.function}'",
                    path=f"flows.{flow_name}.steps.{step.id}.function"
                )
            for dep in step.depends_on:
                if dep not in known_step_ids:
                    raise IRSemanticError(
                        f"Step '{step.id}' depends_on unknown step '{dep}'",
                        path=f"flows.{flow_name}.steps.{step.id}.depends_on"
                    )


def _suggest_fix(error: Any) -> str:
    if error.validator == "enum":
        return f"Allowed values: {error.validator_value}"
    if error.validator == "required":
        return f"Add required field(s): {error.validator_value}"
    if error.validator == "additionalProperties":
        return "Remove unrecognised fields"
    if error.validator == "const":
        return f"Expected: {error.validator_value!r}"
    return "See IR schema documentation"
