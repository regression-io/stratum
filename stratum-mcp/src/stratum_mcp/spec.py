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
    # v0.2: function is optional — inline steps use intent, composed steps use flow_ref
    function: str = ""
    inputs: dict[str, str] = field(default_factory=dict)
    depends_on: list[str] = field(default_factory=list)
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
    # v0.2 STRAT-ENG-1: per-step agent assignment
    agent: str | None = None
    # v0.2 STRAT-ENG-1: inline step intent (prompt) — mutually exclusive with function and flow_ref
    intent: str | None = None
    # v0.2 STRAT-ENG-1: non-gate routing
    on_fail: str | None = None
    next: str | None = None
    # v0.2 STRAT-ENG-1: sub-workflow invocation — mutually exclusive with function and intent
    flow_ref: str | None = None
    # v0.2 STRAT-ENG-1: policy enforcement on gate steps
    policy: str | None = None
    policy_fallback: str | None = None
    # v0.2 STRAT-ENG-1: step-level execution fields for inline steps
    # (function steps get these from IRFunctionDef; flow_ref steps only allow ensure)
    step_ensure: list[str] | None = None
    step_retries: int | None = None
    output_contract: str | None = None
    step_model: str | None = None
    step_budget: IRBudgetDef | None = None
    # v0.2 STRAT-ENG-4: per-step iteration
    max_iterations: int | None = None
    exit_criterion: str | None = None


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
class IRWorkflowDef:
    """v0.2 STRAT-ENG-1: self-registering workflow declaration."""
    name: str
    description: str
    input_schema: dict[str, Any]


@dataclass(frozen=True)
class IRSpec:
    version: str
    contracts: dict[str, IRContractDef]
    functions: dict[str, IRFunctionDef]
    flows: dict[str, IRFlowDef]
    # v0.2 STRAT-ENG-1: workflow declaration (None for internal specs)
    workflow: IRWorkflowDef | None = None


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
#        inline steps (agent/intent), flow composition, policy, workflow declaration.
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
        },
        "workflow": {
            "type": "object",
            "required": ["name", "description", "input"],
            "additionalProperties": False,
            "properties": {
                "name": {"type": "string", "pattern": "^[a-z][a-z0-9-]*$"},
                "description": {"type": "string", "minLength": 1},
                "input": {
                    "type": "object",
                    "additionalProperties": {
                        "type": "object",
                        "properties": {
                            "type": {"type": "string", "enum": [
                                "string", "boolean", "integer", "number", "array", "object"
                            ]},
                            "required": {"type": "boolean"},
                            "default": {},
                        },
                        "required": ["type"],
                    }
                },
            }
        },
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
            # v0.2: only "id" is required — steps can use function, intent, or flow
            "type": "object",
            "required": ["id"],
            "additionalProperties": False,
            "properties": {
                "id": {"type": "string"},
                # Step mode: exactly one of function, intent, or flow (semantic validation)
                "function": {"type": "string"},
                "intent": {"type": "string"},
                "flow": {"type": "string"},
                # Agent assignment
                "agent": {"type": "string"},
                # Inputs and dependencies
                "inputs": {"type": "object", "additionalProperties": {"type": "string"}},
                "depends_on": {"type": "array", "items": {"type": "string"}},
                "output_schema": {"type": "object"},
                # Gate routing (null = default terminal behaviour)
                "on_approve": {"type": ["string", "null"]},
                "on_revise":  {"type": ["string", "null"]},
                "on_kill":    {"type": ["string", "null"]},
                # Non-gate routing
                "on_fail": {"type": "string"},
                "next": {"type": "string"},
                # Conditional skip
                "skip_if":     {"type": "string"},
                "skip_reason": {"type": "string"},
                # Policy enforcement (gate steps only)
                "policy": {"type": "string", "enum": ["gate", "flag", "skip"]},
                "policy_fallback": {"type": "string", "enum": ["gate", "flag", "skip"]},
                # Step-level execution fields (inline steps only — semantic validation)
                "ensure": {"type": "array", "items": {"type": "string"}},
                "retries": {"type": "integer", "minimum": 1},
                "output_contract": {"type": "string"},
                "model": {"type": "string"},
                "budget": {"$ref": "#/$defs/BudgetDef"},
                # Per-step iteration (STRAT-ENG-4)
                "max_iterations": {"type": "integer", "minimum": 1},
                "exit_criterion": {"type": "string"},
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
    wf = doc.get("workflow")
    workflow = IRWorkflowDef(
        name=wf["name"],
        description=wf["description"],
        input_schema=wf.get("input", {}),
    ) if wf else None
    return IRSpec(
        version=doc["version"],
        contracts=contracts,
        functions=functions,
        flows=flows,
        workflow=workflow,
    )


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
    steps = [_build_step(s) for s in d.get("steps", [])]
    return IRFlowDef(
        name=name,
        input_schema=d.get("input", {}),
        output_contract=d.get("output", ""),  # empty string when no output declared
        budget=budget,
        steps=steps,
        max_rounds=d.get("max_rounds"),
    )


def _build_step(s: dict) -> IRStepDef:
    sb = s.get("budget")
    step_budget = IRBudgetDef(ms=sb.get("ms"), usd=sb.get("usd")) if sb else None
    return IRStepDef(
        id=s["id"],
        function=s.get("function", ""),
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
        agent=s.get("agent"),
        intent=s.get("intent"),
        on_fail=s.get("on_fail"),
        next=s.get("next"),
        flow_ref=s.get("flow"),  # YAML key "flow" → field "flow_ref"
        policy=s.get("policy"),
        policy_fallback=s.get("policy_fallback"),
        step_ensure=s.get("ensure"),
        step_retries=s.get("retries"),
        output_contract=s.get("output_contract"),
        step_model=s.get("model"),
        step_budget=step_budget,
        max_iterations=s.get("max_iterations"),
        exit_criterion=s.get("exit_criterion"),
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


def _check_recursive_flow_refs(spec: IRSpec, flow_name: str, step_flow_ref: str) -> None:
    """Detect recursive flow references (direct or indirect)."""
    visited = {flow_name}
    queue = [step_flow_ref]
    while queue:
        current = queue.pop(0)
        if current in visited:
            raise IRSemanticError(
                f"Recursive flow reference detected: '{current}' is referenced "
                f"from within its own call chain",
                path=f"flows.{flow_name}"
            )
        visited.add(current)
        flow = spec.flows.get(current)
        if flow:
            for s in flow.steps:
                if s.flow_ref:
                    queue.append(s.flow_ref)


def _validate_semantics(spec: IRSpec) -> None:
    known_contracts = set(spec.contracts)
    known_functions = set(spec.functions)
    known_flow_names = set(spec.flows)

    # --- Function-level validation (unchanged) ---
    for fn_name, fn in spec.functions.items():
        if fn.mode == "gate":
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

    # --- Workflow-level validation ---
    if spec.workflow:
        # Entry flow: must match workflow.name or be the only flow
        entry_flow_name = spec.workflow.name if spec.workflow.name in known_flow_names else None
        if entry_flow_name is None:
            if len(spec.flows) == 1:
                entry_flow_name = next(iter(spec.flows))
            else:
                raise IRSemanticError(
                    f"Workflow '{spec.workflow.name}' has no matching flow and spec "
                    f"has {len(spec.flows)} flows — cannot determine entry flow",
                    path="workflow.name"
                )
        # Input schema keys must match entry flow's input schema keys
        entry_flow = spec.flows[entry_flow_name]
        wf_keys = set(spec.workflow.input_schema.keys())
        flow_keys = set(entry_flow.input_schema.keys())
        if wf_keys != flow_keys:
            raise IRSemanticError(
                f"Workflow input keys {sorted(wf_keys)} do not match "
                f"entry flow '{entry_flow_name}' input keys {sorted(flow_keys)}",
                path="workflow.input"
            )

    # --- Flow-level and step-level validation ---
    for flow_name, flow in spec.flows.items():
        # output_contract is optional for gate flows (empty string = no contract)
        if flow.output_contract and flow.output_contract not in known_contracts:
            raise IRSemanticError(
                f"Flow '{flow_name}' output contract '{flow.output_contract}' not defined",
                path=f"flows.{flow_name}.output"
            )
        known_step_ids = {step.id for step in flow.steps}
        topo_pos = _topo_positions(flow.steps)

        for step in flow.steps:
            # --- 1. Mode exclusion: exactly one of function, intent, flow_ref ---
            modes = [bool(step.function), bool(step.intent), bool(step.flow_ref)]
            if sum(modes) != 1:
                raise IRSemanticError(
                    f"Step '{step.id}' must have exactly one of function, intent, or flow",
                    path=f"flows.{flow_name}.steps.{step.id}"
                )

            # --- 2. depends_on targets exist (common to all modes) ---
            for dep in step.depends_on:
                if dep not in known_step_ids:
                    raise IRSemanticError(
                        f"Step '{step.id}' depends_on unknown step '{dep}'",
                        path=f"flows.{flow_name}.steps.{step.id}.depends_on"
                    )

            # --- 3. Mode-specific validation ---
            is_gate_step = False

            if step.function:
                # Function must exist
                if step.function not in known_functions:
                    raise IRSemanticError(
                        f"Step '{step.id}' references undefined function '{step.function}'",
                        path=f"flows.{flow_name}.steps.{step.id}.function"
                    )
                # Step-level execution fields forbidden on function steps
                for field_name in ("step_ensure", "step_retries", "output_contract", "step_model", "step_budget"):
                    if getattr(step, field_name) is not None:
                        yaml_name = field_name.replace("step_", "")
                        raise IRSemanticError(
                            f"Step '{step.id}' uses function '{step.function}' — "
                            f"'{yaml_name}' must be on the function, not the step",
                            path=f"flows.{flow_name}.steps.{step.id}.{yaml_name}"
                        )
                # Gate-specific checks
                fn_def = spec.functions[step.function]
                if fn_def.mode == "gate":
                    is_gate_step = True
                    if step.output_schema is not None:
                        raise IRSemanticError(
                            f"Gate step '{step.id}' may not have output_schema (gates produce no output)",
                            path=f"flows.{flow_name}.steps.{step.id}.output_schema"
                        )
                    if step.max_iterations is not None:
                        raise IRSemanticError(
                            f"Gate step '{step.id}' must not have max_iterations (gates have their own revise cycle)",
                            path=f"flows.{flow_name}.steps.{step.id}.max_iterations"
                        )
                    if step.skip_if:
                        raise IRSemanticError(
                            f"Gate step '{step.id}' may not have skip_if (gate steps cannot be skipped)",
                            path=f"flows.{flow_name}.steps.{step.id}.skip_if"
                        )
                    for routing_field in ("on_approve", "on_kill"):
                        if routing_field not in step.declared_routing:
                            raise IRSemanticError(
                                f"Gate step '{step.id}' must explicitly declare '{routing_field}' "
                                f"(use null for default terminal behaviour)",
                                path=f"flows.{flow_name}.steps.{step.id}.{routing_field}"
                            )
                    if step.on_revise is None:
                        raise IRSemanticError(
                            f"Gate step '{step.id}' must have on_revise set to a step id",
                            path=f"flows.{flow_name}.steps.{step.id}.on_revise"
                        )
                    if step.on_revise == step.id:
                        raise IRSemanticError(
                            f"Gate step '{step.id}' on_revise may not target itself",
                            path=f"flows.{flow_name}.steps.{step.id}.on_revise"
                        )
                    gate_topo = topo_pos.get(step.id)
                    revise_topo = topo_pos.get(step.on_revise)
                    if gate_topo is not None and revise_topo is not None:
                        if revise_topo >= gate_topo:
                            raise IRSemanticError(
                                f"Gate step '{step.id}' on_revise must target a topologically-earlier "
                                f"step, but '{step.on_revise}' executes at or after '{step.id}'",
                                path=f"flows.{flow_name}.steps.{step.id}.on_revise"
                            )
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

            elif step.intent:
                pass  # Inline step: no additional mode-specific checks

            elif step.flow_ref:
                # Must reference a known flow
                if step.flow_ref not in known_flow_names:
                    raise IRSemanticError(
                        f"Step '{step.id}' references undefined flow '{step.flow_ref}'",
                        path=f"flows.{flow_name}.steps.{step.id}.flow"
                    )
                # Must not have agent (sub-flow steps define their own agents)
                if step.agent:
                    raise IRSemanticError(
                        f"Step '{step.id}' uses flow '{step.flow_ref}' — "
                        f"agent must not be set (sub-flow steps define their own)",
                        path=f"flows.{flow_name}.steps.{step.id}.agent"
                    )
                # Must not have retries, model, budget
                for field_name in ("step_retries", "step_model", "step_budget"):
                    if getattr(step, field_name) is not None:
                        yaml_name = field_name.replace("step_", "")
                        raise IRSemanticError(
                            f"Step '{step.id}' uses flow '{step.flow_ref}' — "
                            f"'{yaml_name}' must not be set on flow steps",
                            path=f"flows.{flow_name}.steps.{step.id}.{yaml_name}"
                        )
                # No recursive references
                _check_recursive_flow_refs(spec, flow_name, step.flow_ref)

            # --- 4. Common checks (all non-gate modes) ---
            if not is_gate_step:
                # Gate routing fields forbidden on non-gate steps
                for field_name in ("on_approve", "on_revise", "on_kill"):
                    if getattr(step, field_name) is not None:
                        raise IRSemanticError(
                            f"Step '{step.id}' is not a gate step but has '{field_name}' set",
                            path=f"flows.{flow_name}.steps.{step.id}.{field_name}"
                        )
                # on_fail requires ensure or output_schema (otherwise it never triggers)
                # For function steps, check the function's ensure; for inline/flow, check step_ensure
                has_ensure = bool(step.step_ensure)
                if not has_ensure and step.function:
                    fn = spec.functions.get(step.function)
                    has_ensure = bool(fn and fn.ensure)
                has_validation = has_ensure or bool(step.output_schema)
                if step.on_fail and not has_validation:
                    raise IRSemanticError(
                        f"Step '{step.id}' has on_fail but no ensure — on_fail can never trigger",
                        path=f"flows.{flow_name}.steps.{step.id}.on_fail"
                    )
                # on_fail target must exist
                if step.on_fail and step.on_fail not in known_step_ids:
                    raise IRSemanticError(
                        f"Step '{step.id}' on_fail references unknown step '{step.on_fail}'",
                        path=f"flows.{flow_name}.steps.{step.id}.on_fail"
                    )
                # next target must exist
                if step.next and step.next not in known_step_ids:
                    raise IRSemanticError(
                        f"Step '{step.id}' next references unknown step '{step.next}'",
                        path=f"flows.{flow_name}.steps.{step.id}.next"
                    )
                # policy only on gate steps
                if step.policy:
                    raise IRSemanticError(
                        f"Step '{step.id}' has policy but is not a gate step",
                        path=f"flows.{flow_name}.steps.{step.id}.policy"
                    )
                if step.policy_fallback:
                    raise IRSemanticError(
                        f"Step '{step.id}' has policy_fallback but is not a gate step",
                        path=f"flows.{flow_name}.steps.{step.id}.policy_fallback"
                    )
                # exit_criterion requires max_iterations
                if step.exit_criterion and not step.max_iterations:
                    raise IRSemanticError(
                        f"Step '{step.id}' has exit_criterion but no max_iterations",
                        path=f"flows.{flow_name}.steps.{step.id}.exit_criterion"
                    )
                # exit_criterion dunder guard
                if step.exit_criterion and "__" in step.exit_criterion:
                    raise IRSemanticError(
                        f"Step '{step.id}' exit_criterion must not contain dunder attributes",
                        path=f"flows.{flow_name}.steps.{step.id}.exit_criterion"
                    )
            else:
                # Gate steps: on_fail and next are gate-incompatible
                if step.on_fail:
                    raise IRSemanticError(
                        f"Gate step '{step.id}' must not have on_fail (use on_revise for gates)",
                        path=f"flows.{flow_name}.steps.{step.id}.on_fail"
                    )
                if step.next:
                    raise IRSemanticError(
                        f"Gate step '{step.id}' must not have next (use on_approve for gates)",
                        path=f"flows.{flow_name}.steps.{step.id}.next"
                    )
                # policy_fallback requires policy
                if step.policy_fallback and not step.policy:
                    raise IRSemanticError(
                        f"Gate step '{step.id}' has policy_fallback but no policy",
                        path=f"flows.{flow_name}.steps.{step.id}.policy_fallback"
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
