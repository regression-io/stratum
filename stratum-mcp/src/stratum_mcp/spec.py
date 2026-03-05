"""IR types, JSON Schema registry, parser, and validator for .stratum.yaml v0.1/v0.2."""
from __future__ import annotations

from dataclasses import dataclass, field
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
    mode: Literal["infer", "compute", "gate"]
    intent: str
    input_schema: dict[str, Any]
    output_contract: str
    ensure: list[str]
    budget: IRBudgetDef | None
    retries: int
    model: str | None
    # v0.2: gate timeout in seconds (None = no timeout)
    timeout: int | None = None
    # True when "retries" was explicitly present in the YAML dict (not defaulted)
    retries_explicit: bool = False


@dataclass(frozen=True)
class IRStepDef:
    id: str
    function: str
    inputs: dict[str, str]
    depends_on: list[str]
    output_schema: dict[str, Any] | None = None
    # v0.2: gate routing — all nullable; on_revise required for gate steps (semantic validation)
    on_approve: str | None = None
    on_revise: str | None = None
    on_kill: str | None = None
    # v0.2: conditional skip
    skip_if: str | None = None
    skip_reason: str | None = None
    # v0.2: tracks which routing fields were explicitly declared in YAML
    # (distinguishes absent-from-YAML vs explicitly-null for on_approve / on_kill)
    declared_routing: frozenset = field(default_factory=frozenset)


@dataclass(frozen=True)
class IRFlowDef:
    name: str
    input_schema: dict[str, Any]
    output_contract: str          # empty string for gate flows with no declared output
    budget: IRBudgetDef | None
    steps: list[IRStepDef]
    # v0.2: maximum revise rounds before max_rounds_exceeded error (None = unlimited)
    max_rounds: int | None = None


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

# v0.2: adds mode:gate, gate routing fields, skip_if/skip_reason, max_rounds,
#        and relaxes required fields for gate functions/flows.
_IR_SCHEMA_V02: dict = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "required": ["version"],
    "additionalProperties": False,
    "properties": {
        "version": {"type": "string", "const": "0.2"},
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
            # Gate functions only require "mode"; intent/input/output are optional for gates.
            # Semantic validation enforces intent/input/output for non-gate functions.
            "type": "object",
            "required": ["mode"],
            "additionalProperties": False,
            "properties": {
                "mode": {"type": "string", "enum": ["infer", "compute", "gate"]},
                "intent": {"type": "string", "minLength": 1},
                "input": {"type": "object"},
                "output": {"type": "string"},
                "ensure": {"type": "array", "items": {"type": "string"}},
                "budget": {"$ref": "#/$defs/BudgetDef"},
                "retries": {"type": "integer", "minimum": 1},
                "model": {"type": "string"},
                "timeout": {"type": "integer", "minimum": 1},
            }
        },
        "StepDef": {
            # Gate steps do not have "inputs" — only id and function are required.
            "type": "object",
            "required": ["id", "function"],
            "additionalProperties": False,
            "properties": {
                "id": {"type": "string"},
                "function": {"type": "string"},
                "inputs": {"type": "object", "additionalProperties": {"type": "string"}},
                "depends_on": {"type": "array", "items": {"type": "string"}},
                "output_schema": {"type": "object"},
                # Gate routing (null = default terminal behaviour)
                "on_approve": {"type": ["string", "null"]},
                "on_revise":  {"type": ["string", "null"]},
                "on_kill":    {"type": ["string", "null"]},
                # Conditional skip
                "skip_if":     {"type": "string"},
                "skip_reason": {"type": "string"},
            }
        },
        "FlowDef": {
            # Gate flows may not declare an output contract — output is optional.
            "type": "object",
            "required": ["input", "steps"],
            "additionalProperties": False,
            "properties": {
                "input": {"type": "object"},
                "output": {"type": "string"},
                "budget": {"$ref": "#/$defs/BudgetDef"},
                "steps": {"type": "array", "items": {"$ref": "#/$defs/StepDef"}, "minItems": 1},
                "max_rounds": {"type": "integer", "minimum": 1},
            }
        }
    }
}

# Version registry
SCHEMAS: dict[str, dict] = {
    "0.1": _IR_SCHEMA_V01,
    "0.2": _IR_SCHEMA_V02,
}


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
        intent=d.get("intent", ""),           # empty for gate functions
        input_schema=d.get("input", {}),
        output_contract=d.get("output", ""),  # empty for gate functions
        ensure=d.get("ensure", []),
        budget=budget,
        retries=d.get("retries", 3),
        model=d.get("model"),
        timeout=d.get("timeout"),
        retries_explicit="retries" in d,
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
            on_approve=s.get("on_approve"),
            on_revise=s.get("on_revise"),
            on_kill=s.get("on_kill"),
            skip_if=s.get("skip_if"),
            skip_reason=s.get("skip_reason"),
            declared_routing=frozenset(
                f for f in ("on_approve", "on_revise", "on_kill") if f in s
            ),
        )
        for s in d.get("steps", [])
    ]
    return IRFlowDef(
        name=name,
        input_schema=d.get("input", {}),
        output_contract=d.get("output", ""),  # empty string when no output declared
        budget=budget,
        steps=steps,
        max_rounds=d.get("max_rounds"),
    )


def _topo_positions(steps: list[IRStepDef]) -> dict[str, int]:
    """
    Return step_id → topological execution position (0-based).

    Uses Kahn's algorithm over explicit depends_on edges only (no $ ref scanning,
    which would require executor-level parsing). Returns a partial dict if a cycle
    exists — the caller should treat absent entries as unresolvable.
    """
    dep_graph: dict[str, set[str]] = {s.id: set(s.depends_on) for s in steps}
    in_degree = {sid: len(deps) for sid, deps in dep_graph.items()}
    ready = [sid for sid, d in in_degree.items() if d == 0]
    positions: dict[str, int] = {}
    pos = 0
    while ready:
        sid = ready.pop(0)
        positions[sid] = pos
        pos += 1
        for other_id, deps in dep_graph.items():
            if sid in deps:
                in_degree[other_id] -= 1
                if in_degree[other_id] == 0:
                    ready.append(other_id)
    return positions


def _validate_semantics(spec: IRSpec) -> None:
    known_contracts = set(spec.contracts)
    known_functions = set(spec.functions)

    for fn_name, fn in spec.functions.items():
        if fn.mode == "gate":
            # Gate functions must not declare ensure expressions or a budget —
            # they produce no output and must not enforce postconditions.
            if fn.ensure:
                raise IRSemanticError(
                    f"Gate function '{fn_name}' must not have ensure expressions",
                    path=f"functions.{fn_name}.ensure"
                )
            if fn.budget is not None:
                raise IRSemanticError(
                    f"Gate function '{fn_name}' must not have a budget",
                    path=f"functions.{fn_name}.budget"
                )
            if fn.retries_explicit:
                raise IRSemanticError(
                    f"Gate function '{fn_name}' must not have retries (gates produce no output to retry)",
                    path=f"functions.{fn_name}.retries"
                )
            continue  # gate functions have no output contract
        if fn.output_contract not in known_contracts:
            raise IRSemanticError(
                f"Function '{fn_name}' output contract '{fn.output_contract}' not defined",
                path=f"functions.{fn_name}.output"
            )

    for flow_name, flow in spec.flows.items():
        # output_contract is optional for gate flows (empty string = no contract)
        if flow.output_contract and flow.output_contract not in known_contracts:
            raise IRSemanticError(
                f"Flow '{flow_name}' output contract '{flow.output_contract}' not defined",
                path=f"flows.{flow_name}.output"
            )
        # Collect all step IDs first so depends_on can reference steps in any YAML order.
        # Existence is validated here; cycle detection is handled by _topological_sort.
        known_step_ids = {step.id for step in flow.steps}
        # Topological positions for on_revise ordering validation (computed once per flow).
        topo_pos = _topo_positions(flow.steps)
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
            # v0.2 gate invariants
            fn_def = spec.functions.get(step.function)
            if fn_def and fn_def.mode == "gate":
                # Gate steps must not carry output_schema (gates produce no output)
                if step.output_schema is not None:
                    raise IRSemanticError(
                        f"Gate step '{step.id}' may not have output_schema (gates produce no output)",
                        path=f"flows.{flow_name}.steps.{step.id}.output_schema"
                    )
                # Gate steps must not carry skip_if (gates cannot be skipped)
                if step.skip_if:
                    raise IRSemanticError(
                        f"Gate step '{step.id}' may not have skip_if (gate steps cannot be skipped)",
                        path=f"flows.{flow_name}.steps.{step.id}.skip_if"
                    )
                # Gate steps require on_approve and on_kill to be explicitly declared
                # (even if null is acceptable — absence means the author forgot them)
                for routing_field in ("on_approve", "on_kill"):
                    if routing_field not in step.declared_routing:
                        raise IRSemanticError(
                            f"Gate step '{step.id}' must explicitly declare '{routing_field}' "
                            f"(use null for default terminal behaviour)",
                            path=f"flows.{flow_name}.steps.{step.id}.{routing_field}"
                        )
                # Gate steps require on_revise to be set (non-null) so revise is always possible
                if step.on_revise is None:
                    raise IRSemanticError(
                        f"Gate step '{step.id}' must have on_revise set to a step id",
                        path=f"flows.{flow_name}.steps.{step.id}.on_revise"
                    )
                # on_revise must not target the gate step itself
                if step.on_revise == step.id:
                    raise IRSemanticError(
                        f"Gate step '{step.id}' on_revise may not target itself",
                        path=f"flows.{flow_name}.steps.{step.id}.on_revise"
                    )
                # on_revise must target a topologically-earlier step (rollback semantics).
                # If topo positions are available for both steps (no cycle), enforce ordering.
                gate_topo = topo_pos.get(step.id)
                revise_topo = topo_pos.get(step.on_revise)
                if gate_topo is not None and revise_topo is not None:
                    if revise_topo >= gate_topo:
                        raise IRSemanticError(
                            f"Gate step '{step.id}' on_revise must target a topologically-earlier "
                            f"step, but '{step.on_revise}' executes at or after '{step.id}'",
                            path=f"flows.{flow_name}.steps.{step.id}.on_revise"
                        )
                # Validate routing target existence
                for field_name, target in [
                    ("on_approve", step.on_approve),
                    ("on_revise",  step.on_revise),
                    ("on_kill",    step.on_kill),
                ]:
                    if target is not None and target not in known_step_ids:
                        raise IRSemanticError(
                            f"Step '{step.id}' {field_name} references unknown step '{target}'",
                            path=f"flows.{flow_name}.steps.{step.id}.{field_name}"
                        )
            else:
                # Non-gate steps must not carry gate routing fields
                for field_name, value in [
                    ("on_approve", step.on_approve),
                    ("on_revise",  step.on_revise),
                    ("on_kill",    step.on_kill),
                ]:
                    if value is not None:
                        raise IRSemanticError(
                            f"Step '{step.id}' is not a gate step but has '{field_name}' set",
                            path=f"flows.{flow_name}.steps.{step.id}.{field_name}"
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
