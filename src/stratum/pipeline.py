"""@pipeline and @phase decorators for declaring agent-agnostic pipelines."""

from __future__ import annotations

import dataclasses
import inspect
import warnings
from typing import Any, Callable

from .exceptions import StratumCompileError, StratumWarning
from .pipeline_types import Capability, Policy, is_named_assertion


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclasses.dataclass(frozen=True)
class PhaseSpec:
    """Captured metadata for a single @phase-decorated method."""

    name:        str
    intent:      str
    capability:  Capability
    policy:      Policy
    input:       tuple[str, ...]   # prior phase names whose outputs are injected
    ensures:     tuple[str, ...]   # named assertions or arbitrary expressions
    connector:   str | None        # per-phase connector override; None = use pipeline default
    retries:     int
    return_hint: Any               # raw annotation from fn.__annotations__["return"]


@dataclasses.dataclass(frozen=True)
class PipelineDefinition:
    """Compiled pipeline — attached to the class as _pipeline_def."""

    name:      str
    connector: str | None          # default connector for all phases
    phases:    tuple[PhaseSpec, ...]
    phase_map: dict[str, PhaseSpec] = dataclasses.field(compare=False)


# ---------------------------------------------------------------------------
# @phase
# ---------------------------------------------------------------------------

def phase(
    capability: Capability,
    policy:     Policy,
    input:      list[str] | None = None,
    ensures:    list[str] | None = None,
    connector:  str | None = None,
    retries:    int = 3,
    intent:     str | None = None,
) -> Callable:
    """
    Declare a method as a pipeline phase.

    The decorated method body MUST be `...`. It is never executed — the decorator
    captures metadata only. The docstring is used as the phase intent unless
    an explicit `intent=` is provided.

    Args:
        capability: Agent tier required (SCOUT / BUILDER / CRITIC).
        policy:     Gate/flag/skip mode for this phase transition.
        input:      Names of prior phases whose outputs are injected as context.
        ensures:    Postcondition assertions. Named assertions are portable across
                    all connectors. Arbitrary Python expressions only evaluate on
                    Claude Code — a StratumWarning is emitted at @pipeline time.
        connector:  Override the pipeline default connector for this phase.
        retries:    Total execution attempts before the phase is marked failed.
        intent:     Explicit phase description. Falls back to the docstring.
    """
    def decorator(fn: Callable) -> Callable:
        if not callable(fn):
            raise StratumCompileError(
                f"@phase must decorate a callable, got {type(fn)!r}"
            )

        if retries < 1:
            raise StratumCompileError(
                f"@phase retries must be >= 1, got {retries}"
            )

        phase_intent = intent or inspect.getdoc(fn) or fn.__name__
        return_hint  = fn.__annotations__.get("return")

        spec = PhaseSpec(
            name        = fn.__name__,
            intent      = phase_intent,
            capability  = Capability(capability),
            policy      = Policy(policy),
            input       = tuple(input or []),
            ensures     = tuple(ensures or []),
            connector   = connector,
            retries     = retries,
            return_hint = return_hint,
        )

        fn._phase_spec    = spec        # type: ignore[attr-defined]
        fn._stratum_type  = "phase"     # type: ignore[attr-defined]
        return fn                       # body is never executed; no wrapper needed

    return decorator


# ---------------------------------------------------------------------------
# @pipeline
# ---------------------------------------------------------------------------

def pipeline(
    name:      str,
    connector: str | None = None,
) -> Callable:
    """
    Declare a class as a Stratum pipeline.

    Collects all @phase-decorated methods in definition order, validates
    the phase graph, and attaches a PipelineDefinition to the class.

    Args:
        name:      Identifier for this pipeline. Used as the run workspace prefix.
        connector: Default connector for all phases. Overridable per-phase.
    """
    def decorator(cls: type) -> type:
        # Collect @phase methods in class definition order (dict-ordered, Python 3.7+)
        phases: list[PhaseSpec] = [
            val._phase_spec
            for val in cls.__dict__.values()
            if callable(val) and hasattr(val, "_phase_spec")
        ]

        if not phases:
            raise StratumCompileError(
                f"@pipeline '{name}' has no @phase methods"
            )

        phase_map: dict[str, PhaseSpec] = {p.name: p for p in phases}

        # Validate input references — inputs must refer to existing, earlier phases only
        phase_index: dict[str, int] = {p.name: i for i, p in enumerate(phases)}

        for i, p in enumerate(phases):
            for ref in p.input:
                if ref not in phase_map:
                    raise StratumCompileError(
                        f"Phase '{p.name}' references unknown input '{ref}'. "
                        f"Available phases: {list(phase_map)}"
                    )
                if ref == p.name:
                    raise StratumCompileError(
                        f"Phase '{p.name}' references itself as input"
                    )
                if phase_index[ref] >= i:
                    raise StratumCompileError(
                        f"Phase '{p.name}' references '{ref}' which is not an earlier "
                        f"phase. Inputs must refer only to phases defined before this one."
                    )

        # Warn on non-portable ensures when a non-Claude connector is configured
        _warn_non_portable_ensures(phases, connector, stacklevel=3)

        defn = PipelineDefinition(
            name      = name,
            connector = connector,
            phases    = tuple(phases),
            phase_map = phase_map,
        )

        cls._pipeline_def  = defn       # type: ignore[attr-defined]
        cls._stratum_type  = "pipeline" # type: ignore[attr-defined]
        return cls

    return decorator


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _warn_non_portable_ensures(
    phases:     list[PhaseSpec],
    connector:  str | None,
    stacklevel: int = 2,
) -> None:
    """
    Emit StratumWarning for any arbitrary ensure expressions when a non-Claude
    connector is the effective connector for a phase. Checks per-phase connector
    first, falls back to pipeline default. Named assertions are always portable.
    """
    for p in phases:
        effective = p.connector or connector
        if effective is None or effective == "claude-code":
            continue
        phase_connector = effective
        for expr in p.ensures:
            if not is_named_assertion(expr):
                warnings.warn(
                    f"Phase '{p.name}': ensure expression '{expr}' is not a named "
                    f"assertion and will not be evaluated by connector "
                    f"'{phase_connector}'. Use named assertions for portability.",
                    StratumWarning,
                    stacklevel=stacklevel,
                )
