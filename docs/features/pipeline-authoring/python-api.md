# Python API — `@pipeline`, `@phase`, `stratum.run()`

**Status:** DESIGN — settled, implementation not started
**Date:** 2026-03-03
**Roadmap:** T5-2, T5-3

## Related Documents

- [Pipeline Authoring Model](design.md) ← parent design
- [Connector Interface](connector-interface.md) ← how connectors plug into the harness

---

## `@pipeline`

Declares a pipeline class. Captures name, default connector, and assembles the phase
sequence from decorated methods at class definition time.

```python
@pipeline(
    name="feature-lifecycle",   # required — identifies this pipeline in run workspace
    connector="claude-code",    # default connector for all phases; overridable per-phase
)
class FeaturePipeline:
    ...
```

At decoration time:
- Collects all `@phase`-decorated methods in definition order
- Validates `input` references (every named input must be a phase in this pipeline)
- Validates `ensures` (named assertions checked against vocabulary; warns on arbitrary expressions)
- Compiles to `.stratum.yaml` IR (stored on the class, never shown to the user)

---

## `@phase`

Declares a single phase. The method body is a declaration, not executed logic — it is
`...` by convention. The docstring is the phase intent if no explicit `intent=` is given.
The return type annotation is the output schema.

```python
@phase(
    capability=Capability.SCOUT,    # required
    policy=Policy.SKIP,             # required
    input=[],                       # prior phase names whose outputs are injected as context
    ensures=["files_identified"],   # named assertions evaluated after phase completes
    connector=None,                 # override pipeline default; None = use pipeline default
    retries=2,                      # total attempts before failing (default 3)
)
async def discovery(self, feature: str) -> DiscoveryResult:
    """Explore codebase, identify affected files and dependencies"""
    ...
```

### Return type as output schema

The return type annotation drives output schema generation. stratum-py already
generates JSON Schema from type hints via `typing.get_type_hints()`. `@phase` reuses
this — the harness instructs the agent to return JSON matching the schema, then
validates the response against it.

```python
@dataclass
class DiscoveryResult:
    affected_files: list[str]
    risks:          list[str]
    summary:        str
```

### Input injection

Phases listed in `input` have their `{phase-id}.json` outputs read from
`.stratum/runs/{run-id}/` and injected into the prompt as structured context before
the connector is called. Order matches the list order.

### Arbitrary expression warning

Named assertions are portable. Arbitrary Python expression strings compile to
`.stratum.yaml` ensures directly but only evaluate correctly on Claude Code. At
decoration time, a `StratumWarning` is emitted if arbitrary expressions are used
alongside a non-Claude connector config.

```python
# portable — works on any connector
ensures=["tests_pass", "files_changed"]

# Claude Code only — emits StratumWarning if connector != "claude-code"
ensures=["result.coverage > 0.8"]
```

---

## `stratum.run()`

Entry point for the Python harness. Drives the state machine loop until the pipeline
completes, fails, or is interrupted.

```python
result = await stratum.run(
    pipeline=FeaturePipeline,       # @pipeline class
    connector=ClaudeConnector(),    # connector instance
    inputs={"feature": "..."},      # pipeline-level inputs
    run_id=None,                    # None = new run, str = resume existing run
    working_dir=".",                # project root; written to RunOpts.working_dir
    run_dir=".stratum/runs",        # where run workspaces live
)
```

### State machine loop

```
resolve run_id (generate or resume)
for each phase in sequence:
    if {phase-id}.json exists → skip (already complete)
    if {phase-id}.failed exists → halt with error
    if {phase-id}.gate exists and no .gate.approved → block (poll)
    construct prompt from phase definition + injected inputs
    connector.run(prompt, capability, opts)
    parse → validate schema → evaluate ensures
    on pass  → write {phase-id}.json
    on fail  → retry or write {phase-id}.failed
return PipelineResult
```

### Resume

If `run_id` is provided and `.stratum/runs/{run-id}/` exists, completed phases
(those with a `{phase-id}.json`) are skipped. The run resumes from the first
incomplete phase. No re-execution of work that already passed.

If `run_id` is None, a new UUID is generated and a fresh run directory is created.

### Gate blocking

When a `policy=GATE` phase is reached, `stratum.run()` writes the `.gate` file and
polls for `.gate.approved` or `.gate.rejected`. Poll interval is configurable
(default 2s). stratum-ui watches for `.gate` files and surfaces the approval UI.
CLI users can approve manually: `stratum gate approve {run-id} {phase-id}`.

### Return value

```python
@dataclass
class PipelineResult:
    run_id:     str
    status:     Literal["complete", "failed", "rejected"]
    phases:     dict[str, PhaseRecord]   # phase-id → result + metadata
    duration_ms: int
```

---

## Phase Result Schema

Every `{phase-id}.json` written to the run workspace has a standard envelope plus
phase-specific output fields.

```json
{
  "_phase":          "discovery",
  "_run_id":         "abc123",
  "_connector":      "claude-code",
  "_duration_ms":    45000,
  "_timestamp":      "2026-03-03T12:00:00Z",
  "_ensures":        ["files_identified"],
  "_ensures_result": {"files_identified": true},

  "affected_files":  ["src/auth.py", "tests/test_auth.py"],
  "risks":           ["touches auth layer"],
  "summary":         "..."
}
```

`_` prefixed fields are the envelope — written by the harness, not the agent.
Phase-specific fields are parsed from the connector's raw text output.
Named assertions are evaluated against the full object (envelope + phase fields).

The harness writes this file. The agent never writes directly to the run workspace.

---

## Relationship to stratum-mcp

T2-14 (FlowState persistence) in the Track 2 roadmap and the run workspace
convention are the same thing. When stratum-mcp gains file persistence, it writes
to `.stratum/runs/` in the same format. A flow driven by Claude Code via MCP and a
flow driven by the Python harness produce identical run workspaces. They are
interchangeable and can resume each other's runs.
