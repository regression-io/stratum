"""Connector interface — thin wrapper around agent execution."""

from __future__ import annotations

import dataclasses
from typing import Protocol, runtime_checkable

from .budget import Budget
from .pipeline_types import Capability


@dataclasses.dataclass
class RunOpts:
    """
    Options passed to the connector for a single phase execution.

    All fields are optional. Connectors are free to ignore hints they
    cannot act on (e.g. a connector with no budget support ignores ``budget``).
    """

    budget:         Budget | None = None   # ms / usd / tokens limit
    timeout_ms:     int    | None = None   # wall-clock cap on a single connector call
    working_dir:    str    | None = None   # project root, for file-aware operations
    connector_name: str    | None = None   # resolved connector name from stratum.toml
    model_hint:     str    | None = None   # capability mapping from stratum.toml


@runtime_checkable
class Connector(Protocol):
    """
    Thin wrapper around an agent's execution capability.

    Connectors have one job: run a prompt against an agent with a given
    capability tier and return raw text output. The harness owns everything
    else: prompt construction, output parsing, schema validation, ensure
    evaluation, and state writing.

    Connectors raise on failure (network error, auth failure, agent crash).
    They never return error results — either raw text comes back or an
    exception is raised.
    """

    async def run(
        self,
        prompt:     str,
        capability: Capability,
        opts:       RunOpts | None = None,
    ) -> str:
        """
        Execute ``prompt`` using the agent appropriate for ``capability``.

        Returns:
            Raw text output from the agent. The harness parses this.

        Raises:
            Any exception on failure. The harness catches and retries.
        """
        ...

    def supports(self, capability: Capability) -> bool:
        """
        Return ``True`` if this connector can handle ``capability``.

        The harness calls this before execution starts and fails fast if
        a required capability tier is not supported.
        """
        ...
