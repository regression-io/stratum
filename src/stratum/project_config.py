"""stratum.toml project config — policy overrides, capability mapping, connector routing."""

from __future__ import annotations

import dataclasses
import tomllib
import types
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .exceptions import StratumCompileError
from .pipeline_types import Capability, Policy


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclasses.dataclass(frozen=True)
class PipelineConfig:
    """
    Parsed [pipeline.*] sections from stratum.toml.

    policy:       phase-name → Policy override
    capabilities: capability-tier-name → model hint string
    connector:    "default" key + phase-name keys → connector name

    All mapping fields are read-only (MappingProxyType) after construction.
    """
    policy:       Mapping[str, Policy]
    capabilities: Mapping[str, str]
    connector:    Mapping[str, str]

    def __post_init__(self) -> None:
        object.__setattr__(self, "policy",       types.MappingProxyType(dict(self.policy)))
        object.__setattr__(self, "capabilities", types.MappingProxyType(dict(self.capabilities)))
        object.__setattr__(self, "connector",    types.MappingProxyType(dict(self.connector)))


@dataclasses.dataclass(frozen=True)
class StratumConfig:
    """
    Loaded stratum.toml project config.

    Optional. Sensible defaults exist without it. Teams use it to override
    policy dials, map capability tiers to models, and route phases to
    specific connectors without touching the pipeline definition.
    """
    pipeline: PipelineConfig

    # -----------------------------------------------------------------------
    # Construction
    # -----------------------------------------------------------------------

    @classmethod
    def load(cls, path: Path | str | None = None) -> StratumConfig:
        """
        Load config from stratum.toml. Returns empty config if the file does
        not exist. Raises StratumCompileError on parse or validation errors.

        Args:
            path: Path to stratum.toml. Defaults to ./stratum.toml.
        """
        resolved = Path(path) if path is not None else Path("stratum.toml")
        if not resolved.exists():
            return cls.empty()
        with open(resolved, "rb") as fh:
            try:
                raw = tomllib.load(fh)
            except tomllib.TOMLDecodeError as exc:
                raise StratumCompileError(
                    f"stratum.toml: TOML parse error — {exc}"
                ) from exc
        return cls._parse(raw)

    @classmethod
    def empty(cls) -> StratumConfig:
        """Return a config with no overrides (all defaults)."""
        return cls(
            pipeline=PipelineConfig(policy={}, capabilities={}, connector={})
        )

    @classmethod
    def _parse(cls, raw: dict[str, Any]) -> StratumConfig:
        pipeline_raw = raw.get("pipeline", {})
        if not isinstance(pipeline_raw, dict):
            raise StratumCompileError(
                "stratum.toml: [pipeline] must be a table"
            )

        # -- policy overrides ------------------------------------------------
        policy_raw = pipeline_raw.get("policy", {})
        if not isinstance(policy_raw, dict):
            raise StratumCompileError(
                "stratum.toml: [pipeline.policy] must be a table"
            )
        policy: dict[str, Policy] = {}
        for phase_name, value in policy_raw.items():
            if not isinstance(phase_name, str):
                raise StratumCompileError(
                    f"stratum.toml: [pipeline.policy] keys must be strings, "
                    f"got {type(phase_name).__name__!r}"
                )
            try:
                policy[phase_name] = Policy(value)
            except ValueError:
                valid = [p.value for p in Policy]
                raise StratumCompileError(
                    f"stratum.toml: invalid policy '{value}' for phase "
                    f"'{phase_name}'. Valid values: {valid}"
                )

        # -- capability → model hints ----------------------------------------
        capabilities_raw = pipeline_raw.get("capabilities", {})
        if not isinstance(capabilities_raw, dict):
            raise StratumCompileError(
                "stratum.toml: [pipeline.capabilities] must be a table"
            )
        valid_tiers = {c.value for c in Capability}
        capabilities: dict[str, str] = {}
        for tier, hint in capabilities_raw.items():
            if tier not in valid_tiers:
                raise StratumCompileError(
                    f"stratum.toml: unknown capability tier '{tier}'. "
                    f"Valid tiers: {sorted(valid_tiers)}"
                )
            if not isinstance(hint, str):
                raise StratumCompileError(
                    f"stratum.toml: capability hint for '{tier}' must be a string"
                )
            capabilities[tier] = hint

        # -- connector routing -----------------------------------------------
        connector_raw = pipeline_raw.get("connector", {})
        if not isinstance(connector_raw, dict):
            raise StratumCompileError(
                "stratum.toml: [pipeline.connector] must be a table"
            )
        connector: dict[str, str] = {}
        for key, value in connector_raw.items():
            if not isinstance(key, str):
                raise StratumCompileError(
                    f"stratum.toml: [pipeline.connector] keys must be strings, "
                    f"got {type(key).__name__!r}"
                )
            if not isinstance(value, str):
                raise StratumCompileError(
                    f"stratum.toml: connector value for '{key}' must be a string"
                )
            connector[key] = value

        return cls(
            pipeline=PipelineConfig(
                policy=policy,
                capabilities=capabilities,
                connector=connector,
            )
        )

    # -----------------------------------------------------------------------
    # Resolution helpers — used by the harness when executing a pipeline
    # -----------------------------------------------------------------------

    def effective_policy(self, phase_name: str, phase_policy: Policy) -> Policy:
        """
        Return the effective policy for a phase.

        Priority (highest first):
        1. stratum.toml [pipeline.policy] override
        2. @phase policy= argument
        """
        return self.pipeline.policy.get(phase_name, phase_policy)

    def effective_connector(
        self,
        phase_name: str,
        phase_connector: str | None,
        pipeline_default: str | None,
    ) -> str | None:
        """
        Resolve the effective connector for a phase.

        Priority (highest first):
        1. @phase connector= argument
        2. stratum.toml [pipeline.connector] phase-specific key
        3. stratum.toml [pipeline.connector] "default" key
        4. @pipeline connector= argument
        """
        if phase_connector is not None:
            return phase_connector
        toml_phase = self.pipeline.connector.get(phase_name)
        if toml_phase is not None:
            return toml_phase
        toml_default = self.pipeline.connector.get("default")
        if toml_default is not None:
            return toml_default
        return pipeline_default

    def model_hint(self, capability: str) -> str | None:
        """
        Return the model hint for a capability tier, or None if not configured.

        The hint is a suggestion — connectors are free to ignore it. It maps
        abstract tiers to concrete model identifiers for connectors that support
        model selection (e.g. "haiku", "sonnet", "claude-sonnet-4-6").
        """
        return self.pipeline.capabilities.get(capability)
