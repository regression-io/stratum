# Connector Interface

**Status:** DESIGN — settled, implementation not started
**Date:** 2026-03-03
**Roadmap:** T5-2 (part of Pipeline Runtime)

## Related Documents

- [Pipeline Authoring Model](design.md) ← parent design
- [Agent Connectors Design](../agent-connectors/design.md) ← class hierarchy this refines
- [Stratum Roadmap](../../ROADMAP.md) ← Track 5

---

## Principle

Connectors are thin. A connector wraps what an agent *can do*, not what a specific
process needs. It has one job: run a prompt against an agent with a given capability
tier and return raw text output.

The harness owns everything else: prompt construction, output parsing, schema validation,
ensure evaluation, state writing. This keeps connector implementations trivial and
makes adding a new agent a one-method exercise.

---

## Interface

```python
from typing import Protocol
from stratum import Capability, Budget

class RunOpts:
    budget:     Budget | None = None   # ms, usd, tokens — from stratum-py Budget
    timeout_ms: int    | None = None
    working_dir: str   | None = None   # project root, for file-aware operations

class Connector(Protocol):
    async def run(
        self,
        prompt:     str,
        capability: Capability,
        opts:       RunOpts | None = None,
    ) -> str:
        """Execute prompt using the agent appropriate for capability. Return raw text."""
        ...

    def supports(self, capability: Capability) -> bool:
        """True if this connector can handle the given capability tier."""
        ...
```

`run()` returns raw text. The harness parses it. The connector never sees the output
schema, the ensures, or the phase definition — those are harness concerns.

`supports()` lets the harness validate capability coverage before execution starts,
fail fast if a connector can't handle a required tier.

---

## Harness Flow

The harness wraps every connector call in the same pipeline:

```
1. Read prior phase outputs from .stratum/runs/{run-id}/
2. Construct prompt:
     - phase intent
     - injected context (prior outputs)
     - output schema instructions ("return JSON matching this schema")
3. connector.run(prompt, capability, opts)
4. Parse raw text → structured result dict
5. Validate result against phase output_schema
6. Evaluate named assertions against result
7. On pass  → write {phase-id}.json, advance state machine
   On fail  → retry up to phase retries limit, then write {phase-id}.failed
```

The connector is step 3. Everything else is harness logic, identical across all connectors.

---

## Capability Resolution

Each connector maps capability tiers to agents/models internally. The harness never
specifies a model — it specifies a capability and trusts the connector to resolve it.

```python
class ClaudeConnector:
    _capability_map = {
        Capability.SCOUT:   {"model": "claude-haiku-4-5"},
        Capability.BUILDER: {"model": "claude-sonnet-4-6"},
        Capability.CRITIC:  {"model": "claude-sonnet-4-6"},
    }

    async def run(self, prompt: str, capability: Capability, opts: RunOpts | None = None) -> str:
        model = self._capability_map[capability]["model"]
        # call Claude SDK with model + prompt + budget from opts
        ...

class CodexConnector:
    _capability_map = {
        Capability.SCOUT:   {"model": "openai/gpt-5.2-codex", "effort": "low"},
        Capability.BUILDER: {"model": "openai/gpt-5.2-codex", "effort": "high"},
        Capability.CRITIC:  {"model": "openai/gpt-5.1-codex-max", "effort": "medium"},
    }
    ...
```

`stratum.toml` overrides this mapping at the project level without touching connector code:

```toml
[pipeline.capabilities]
scout   = "haiku"    # model hint passed to connector
builder = "sonnet"
```

The connector interprets the hint; it is never a hard model ID in the pipeline definition.

---

## Error Handling

Connectors raise on failure — network error, auth failure, agent crash. The harness
catches and decides: retry the phase (within the retry budget) or write
`{phase-id}.failed` and halt the pipeline.

Connectors do not return error results. They either return text or raise. This keeps
the harness error path clean and uniform.

---

## Relationship to stratum-mcp

`stratum_plan` / `stratum_step_done` is Claude Code driving the harness one step at a
time via MCP tool calls. In that model, Claude Code *is* the harness — it constructs
prompts, calls agents (itself), parses output, calls `stratum_step_done` with the result.

In the Python harness model, the harness is a Python process and the connector calls
Claude via the Claude SDK. Same logical flow, different driver.

The `ClaudeSDKConnector` (from the agent-connectors class hierarchy) is the concrete
implementation of `Connector` for the Python harness model.
