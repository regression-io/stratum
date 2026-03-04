# `.compose.yaml` — Agent-Agnostic Process Spec

**Status:** DESIGN — schema sketch and open questions, not yet buildable spec
**Date:** 2026-03-03

## Related Documents

- [Lifecycle Engine Roadmap](2026-02-15-lifecycle-engine-roadmap.md) ← Layer 3 (Policy Runtime), Layer 7 (Agent Abstraction)
- [Agent Connectors Design](../features/agent-connectors/design.md) ← connector class hierarchy this spec compiles to
- [Architecture Foundation Plan](2026-02-26-architecture-foundation-plan.md) ← Phase 4.5 lays connector substrate
- [Bootstrap Roadmap (CLAUDE.md)](../../CLAUDE.md) ← Phase 6 (Lifecycle Engine), Phase 7 (Agent Abstraction)

---

## Problem

Every Compose pipeline today is Claude Code-specific. Phase ordering, model selection, gate behavior,
and postconditions are all encoded in skill markdown that Claude Code interprets on trust. There is
no portable spec. Swapping agents (Claude → Codex → Gemini) requires rewriting the process.

`.compose.yaml` separates the process from the executor. The spec describes what must happen. A
connector translates that to agent-specific primitives.

---

## Core Idea

```
.compose.yaml (what)           ← this document defines this
      ↓ compile
connector (how)
  claude-code: Stratum flows + Team/Task wiring + model routing
  codex:       Codex task primitives + review protocol
  gemini:      Gemini equivalent
```

The spec is the source of truth. Connectors are compilation targets.

---

## Schema

### Top Level

```yaml
version: "1.0"
process: compose-feature
description: "Structured feature implementation lifecycle"
```

---

### Capability Tiers

Abstract agent roles. Never reference models, providers, or agent implementations here.
Connectors map these to concrete agents.

```yaml
capabilities:
  scout:    "Fast, read-only exploration — identify files, context, risks"
  builder:  "Full capability — writes code, edits files, runs tests"
  critic:   "Review and assessment — reads output, evaluates quality"
```

Three tiers covers the lifecycle. Additional tiers (e.g. `planner`, `coordinator`) can be
added if the distinction carries weight.

---

### Phases

Each phase is a named unit of work with a capability requirement, a policy mode, optional
input/output contracts, and postcondition ensures.

```yaml
phases:
  discovery:
    intent: "Explore codebase, identify affected files and dependencies"
    capability: scout
    policy: skip
    output:
      affected_files: {type: array}
      risks:          {type: array}
    ensures:
      - "len(result.affected_files) > 0"

  pre_gate:
    intent: "Assess readiness — conflicts, blockers, unclear requirements"
    capability: critic
    policy: gate
    input:  {from: discovery}
    output:
      ready:    {type: boolean}
      blockers: {type: array}
    ensures:
      - "result.ready == true"

  implement:
    intent: "Implement the feature using discovery context"
    capability: builder
    policy: skip
    input:  {from: [discovery, pre_gate]}
    output:
      changed_files: {type: array}
      tests_pass:    {type: boolean}
    ensures:
      - "result.tests_pass == true"
      - "len(result.changed_files) > 0"

  post_gate:
    intent: "Review implementation quality, surface issues"
    capability: critic
    policy: flag
    input:  {from: implement}
    output:
      approved: {type: boolean}
      issues:   {type: array}
    ensures:
      - "result.approved == true"

  checkpoint:
    intent: "Confirm phase complete, capture learnings, advance pipeline"
    capability: builder
    policy: gate
    input:  {from: [implement, post_gate]}
```

**Policy modes** (Compose's gate/flag/skip model, unchanged):
- `gate` — block until human explicitly approves
- `flag` — proceed, notify human, log decision
- `skip` — proceed silently, record for audit

---

### Per-Step Connector Override

Capabilities route through the default connector unless overridden at the step level.
This is how you interleave agents within a single pipeline.

```yaml
phases:
  discovery:
    capability: scout
    connector: claude-code   # force Claude Code for this step

  implement:
    capability: builder
    connector: codex         # use Codex for this step

  post_gate:
    capability: critic
    # no override — uses pipeline default connector
```

This means a single feature can route each phase to the best available agent:
Claude Code for design-heavy phases, Codex for implementation, a specialized
reviewer for post-gate. The process spec remains unchanged.

---

### Flow

```yaml
flow:
  sequence: [discovery, pre_gate, implement, post_gate, checkpoint]
```

Phases execute in sequence. Future: `parallel` grouping for phases with no data dependency.

---

### Pipeline

Controls multi-feature behavior. A pipeline is one process spec applied to N features.

```yaml
pipeline:
  features: sequential      # one feature at a time (default)
  gate_between: checkpoint  # phase that must complete before next feature begins
  default_connector: claude-code
```

`gate_between` is the cross-feature gate. The checkpoint of feature N must pass before
feature N+1's discovery starts.

---

## Connector Mapping (Separate File)

The process spec has no knowledge of agents, models, or execution infrastructure.
Each connector defines the mapping independently.

```yaml
# connectors/claude-code.yaml
connector: claude-code

capability_map:
  scout:    {agent_type: Explore,          model: haiku}
  builder:  {agent_type: general-purpose,  model: sonnet}
  critic:   {agent_type: compose-reviewer,   model: sonnet}

phase_execution:
  default:  stratum_flow      # wrap in Stratum flow, enforce ensures as postconditions
  gate:     task_with_approval # create blocking task, wait for human approval via SendMessage
  flag:     stratum_flow      # run through Stratum, emit notification on completion
```

```yaml
# connectors/codex.yaml
connector: codex

capability_map:
  scout:    {model: "openai/gpt-5.2-codex", effort: low}
  builder:  {model: "openai/gpt-5.2-codex", effort: high}
  critic:   {model: "openai/gpt-5.1-codex-max", effort: medium}

phase_execution:
  default:  codex_task
  gate:     codex_task_with_pause
```

The connector file is the only place that knows about Haiku, Sonnet, Codex models, or
Stratum. Swapping agents means swapping connector files.

---

## Agent Interleaving

Because capability is declared per-step and resolved by the connector at runtime,
any step in a pipeline can use a different agent. The spec expresses intent; the
connector decides execution.

**Example: hybrid Claude/Codex pipeline**

```yaml
phases:
  discovery:
    capability: scout
    connector: claude-code   # Claude's Explore agent is strong at codebase mapping

  pre_gate:
    capability: critic
    connector: claude-code   # Claude for reasoning about readiness

  implement:
    capability: builder
    connector: codex         # Codex for code generation

  post_gate:
    capability: critic
    connector: claude-code   # Claude's reviewer for quality assessment

  checkpoint:
    capability: builder
    # uses pipeline default
```

This is not multi-agent in the sense of parallel coordination — it is sequential steps
each delegated to the best available executor. The pipeline doesn't change. The
connector routing changes.

The capability tier is the abstraction that makes this safe. `implement` doesn't say
"use Codex" — it says "I need a builder." The connector decides what builder means.
You can change the connector mapping without touching the spec.

---

## Relationship to Stratum

Stratum is one compilation target for the Claude Code connector, not a foundational
dependency of `.compose.yaml`.

When the Claude Code connector encounters a `default` phase, it wraps it in a
Stratum flow with:
- The phase's `intent` as the step intent
- The phase's `ensures` as Stratum postcondition expressions
- The phase's output contract as `output_schema`

When the connector encounters a `gate` phase, it creates a blocking task in the
Team/Task system and waits for human approval via SendMessage before advancing.

Other connectors have no Stratum dependency.

---

## Relationship to Compose Roadmap

| Roadmap Item | How `.compose.yaml` relates |
|---|---|
| Phase 6, Layer 3: Policy Runtime | `policy: gate/flag/skip` per phase IS the policy dial |
| Phase 6, Layer 1: Lifecycle State Machine | Pipeline tracks which phase each feature is in |
| Phase 7, Items 27–28: Agent Abstraction | Connector mapping is the adapter pattern |
| Phase 4.5: Architecture Foundation | Lays connector substrate this compiles to |

The spec resolves the "process is separately definable from connectors" principle from the
[Agent Connectors Design](../features/agent-connectors/design.md) — the spec IS the separate
process definition.

---

## Open Questions

These are deferred for deeper discussion. Each has meaningful design implications and should
not be decided without examining the connector runtime in more detail.

### OQ-1: Output passing between phases

How does a phase receive the output of a previous phase?

Options:
- **File on disk** — each phase writes a structured output file to the feature workspace;
  the next phase reads it. Simple, agent-agnostic, survives session boundaries.
- **Task metadata** — output passed through the Team/Task system as task result payload.
  Requires the task system to be the bus. Only works for Claude Code connector.
- **Stratum reference resolution** — `$.steps.<id>.output.<field>` syntax already exists
  in Stratum. But this only works inside a Stratum flow; cross-flow passing is undefined.

Implications: file-on-disk is the only truly agent-agnostic option. But it requires the
feature workspace convention to be stable and formalized.

### OQ-2: Gate approval channel

`policy: gate` means "block until human approves." This is clear as behavior. It is
unclear as a portable primitive.

In Claude Code: `SendMessage` to the user + blocking TaskUpdate.
In Codex: unknown — does Codex have a pause/approval primitive?
In Gemini: unknown.

Options:
- **Each connector implements gate natively** — no portable protocol, connector decides.
  Clean but means gate UX differs per agent.
- **Compose server as gate broker** — all connectors emit a gate event to the Compose server
  (SSE/WebSocket); the Gate UI in Vision Surface handles approval; server signals back to
  connector. Agent-agnostic, but requires the Compose server to be in the loop.
- **File-based gate** — connector writes a `.gate` file to the feature workspace; an
  external process (Compose server, CLI) watches for it and writes `.gate.approved` when
  the human approves. Maximally simple, survives any agent.

The Compose-server-as-gate-broker option aligns with the Gate UI (Layer 4) in the
lifecycle engine and is likely the right answer, but it introduces a runtime dependency.

### OQ-3: Ensures portability

Stratum's `ensure` expressions are Python evaluated server-side with a constrained
builtins set (`file_exists`, `file_contains`, `len`, `bool`, `int`, `str`).

If `.compose.yaml` adopts the same syntax, non-Claude Code connectors must either:
1. Run the same Python evaluator (Stratum becomes a shared library, not a Claude Code tool)
2. Implement their own evaluator with the same expression language
3. Ignore ensures (weakening the postcondition guarantee)

A simpler alternative: ensures in `.compose.yaml` are expressed as named assertions
(`tests_pass`, `files_changed`, `no_issues`) and each connector defines what those
assertions mean in its native execution model.

This loses the flexibility of arbitrary expressions but gains portability.
