# Changelog

## [Unreleased]

### stratum-py

- `@pipeline` / `@phase` decorators — pipeline authoring model; metadata capture and IR compilation separate from MCP execution mode
- `Capability` and `Policy` enums — capability tiers for connector routing and policy overrides
- `stratum.toml` project config — policy overrides, capability mapping, connector routing
- Run workspace convention — `.stratum/runs/{run-id}/{phase-id}.json` output passing between phases
- File-based gate protocol — `.gate` / `.gate.approved` / `.gate.rejected` files for human approval checkpoints
- Pipeline runtime loop — `run_pipeline()` drives `@pipeline` classes through phases via `Connector`

**Bug fixes**

- `run()` now detects closed event loops and creates a fresh one instead of raising `RuntimeError: Event loop is closed` — resolves e2e test failures after first loop close
- `run()` closes the passed coroutine before raising on a running-loop path — eliminates "coroutine never awaited" warning
- `run()` drains pending async tasks (both on normal return and exception paths) before closing the loop — prevents dropped telemetry callbacks (e.g. litellm `async_success_handler`)
- Anthropic (claude-*) models now receive `cache_control: {type: ephemeral}` blocks on system message, user message, and tool definition — restores prompt caching behavior that reduces cost and latency
- `datetime.utcnow()` replaced with `datetime.now(timezone.utc)` throughout — clears Python 3.12 deprecation warnings

**Testing**

- T1-11: 17-test end-to-end suite (`tests/test_e2e.py`) runs against a real LLM (gpt-4o-mini via OpenAI) — validates `@infer`, `@compute`, `@flow`, `ensure` postconditions, `PostconditionFailed`, `TraceRecord` fields, trace accumulation, `clear_traces`, and `stratum.run()` sync shim

### stratum-mcp

**New MCP tools**

- `stratum_commit` — checkpoint the current flow state under a named label; label recorded in audit trace
- `stratum_revert` — roll back flow state to a named checkpoint; revert event recorded in trace

**MCP server improvements**

- FlowState persistence — flows survive MCP server restarts; state written to `~/.stratum/flows/{flow_id}.json` after each step
- `output_schema` validation in `stratum_step_done` — JSON Schema checked before `ensure` expressions; returns `schema_failed` with violations if invalid
- `ensure` file-aware builtins — `file_exists(path)` and `file_contains(path, substring)` available in postcondition expressions
- `stratum-mcp validate <file>` CLI — validates a `.stratum.yaml` file from the command line
- `stratum-mcp compile <tasks-dir>` CLI — compiles `tasks/*.md` acceptance criteria into `.stratum.yaml` IR (task compiler)

**Skills (ten total)**

- `/compose` — full feature lifecycle skill; emits `.stratum.yaml`, drives spec-kit phases through `stratum_plan` loop
- `/stratum-speckit` — bridge skill; drives spec-kit phases through Stratum, emits compiled flow
- `/stratum-build` — compiles `tasks/` → `.stratum.yaml` and drives execution via `stratum_plan` loop
- Memory sections added to all skills — read project `MEMORY.md` before writing spec; write new patterns after `stratum_audit`

**Memory & Hooks (Tier 1 — MEMORY.md)**

- `SessionStart` hook — auto-injects relevant `MEMORY.md` entries at session open
- `Stop` hook — auto-appends session summary to `MEMORY.md` at session close
- `PostToolUseFailure` hook — auto-records `ensure` failures and tool errors

**Memory (Tier 2 — SmartMemory lite, opt-in)**

- `SessionStart` hook — `memory.search()` for project-relevant context
- `Stop` hook — `memory.ingest()` session summary as episodic memory
- `PostToolUseFailure` hook — `memory.ingest()` failures as observation memory
- Skills use `memory.search()` instead of `MEMORY.md` when lite backend configured (`pip install smartmemory[lite]`)

**Track 3 — Compose + Stratum + spec-kit**

- Task→step compiler — `tasks/*.md` acceptance criteria → `.stratum.yaml` `ensure` expressions
- Compose skill adopts spec-kit artifact format — design phases produce `spec.md`, `plan.md`, `tasks/` under `.specify/`
- Compose web app (Vision Surface) integration:
  - Startup seed from `.specify/` — work items created from spec-kit directories on load, updated on file change
  - Live stratum flow sync — 15s poller maps bound flows to Vision items; detects `running`, `blocked` (retries exhausted = ensure violations), `paused`; clears stale violation evidence on recovery
  - Audit trace surfaced in item evidence panel — `stratum_audit` trace stored in `evidence.stratumTrace`; item transitions to `complete` on flow completion

**Testing:** 211 tests passing (up from 79 at 0.1.3)

**IR v0.2 — Gate / Round / Skip primitives**

- `mode: gate` on functions — gate steps return `await_gate` instead of `execute_step`; `stratum_step_done` rejects gate steps; `stratum_gate_resolve` required
- `stratum_gate_resolve` MCP tool — resolves gate steps with `approve | revise | kill`; `resolved_by: human | agent | system`; GateRecord written to trace
- `stratum_check_timeouts` MCP tool — auto-kills gate steps that exceed their `timeout` (seconds); fires with `resolved_by: system`
- Round archiving — `revise` archives the active round into `state.rounds`; resets active trace; increments `state.round`; `stratum_audit` returns `rounds: [{round, steps}]` unconditionally
- `max_rounds` on flow definitions — `resolve_gate` returns `max_rounds_exceeded` error when round limit reached; GateRecord written but not archived
- `skip_if` / `skip_reason` on steps — Boolean expression evaluated before dispatch; `$.steps.X.output.field` refs resolved inline; SkipRecord written, output set to None; downstream refs propagate None
- `on_approve` / `on_revise` / `on_kill` routing — null = default terminal behaviour; named = route to that step; kill routing sets `terminal_status = "killed"` regardless of named cleanup step
- `terminal_status` on FlowState — `stratum_audit` returns `status: killed` when set; `stratum_step_done` complete path uses `terminal_status or "complete"`

**IR v0.2 semantic validation (enforced at parse time)**

- Gate functions: `ensure`, `budget`, `retries` forbidden
- Gate steps: `skip_if` forbidden; `on_approve` and `on_kill` must be explicitly declared (even if null); `on_revise` must be non-null, must not self-reference, must target a topologically-earlier step
- Non-gate steps: `on_approve`, `on_revise`, `on_kill` forbidden
- `declared_routing: frozenset` tracks which routing fields were explicitly present in YAML (distinguishes absent from null)
- `retries_explicit: bool` tracks whether `retries` was explicitly declared
- `_topo_positions()` computes topological execution order for `on_revise` ordering invariant
- YAML `true` / `false` / `null` recognised in `skip_if` expressions in addition to Python-style literals
- All server tool paths call `get_current_step_info()` before `persist_flow()` — skip mutations durable across restarts

**Testing:** 305 tests passing (+94); new files: `test_gate_api.py` (9 contract tests), `test_gate_revise.py` (6 integration tests); `test_ir_schema.py` +12 v0.2 semantic invariant tests

**STRAT-ENG-1: IR v0.2 inline steps, workflow declarations, flow composition**

- `workflow:` block — self-registering workflow declaration with name, description, input schema
- `stratum_list_workflows` MCP tool — scans a directory for `*.stratum.yaml` files with `workflow:` blocks; returns name/description/input/path; detects duplicate names
- Inline steps — `intent:` + `agent:` on steps (mutually exclusive with `function:` and `flow:`); step-level `ensure`, `retries`, `output_contract`, `model`, `budget`
- `flow:` composition — `flow_ref` on steps for sub-workflow invocation (parsed and validated; execution deferred to STRAT-ENG-5)
- `on_fail` / `next` routing on non-gate steps — `on_fail` requires `ensure`; `on_fail` without `ensure` rejected on both inline and flow_ref steps
- `policy` / `policy_fallback` on gate steps — parsed and validated (`policy_fallback` requires `policy`); evaluation deferred to STRAT-ENG-3
- Mode exclusion validation — exactly one of `function`, `intent`, `flow` required per step
- Workflow input validation — `workflow.input` keys must exactly match entry flow input keys

**Testing:** +33 tests; new files: `test_ir_v02_extensions.py` (29 tests), `test_list_workflows.py` (4 tests)

**STRAT-ENG-2: Executor — state model, agent passthrough, inline step execution**

- `_step_mode()` helper — returns `"function"` or `"inline"`; raises `MCPExecutionError` for `flow_ref` (deferred to STRAT-ENG-5)
- `StepRecord` extended — `agent: str | None` and `step_mode: str` fields with backward-compatible defaults
- `get_current_step_info` restructured — mode-branched dispatch; function steps use `fn_def.ensure/retries`, inline steps use `step.step_ensure/step_retries`; `fn_def` lookup moved after `skip_if` evaluation
- `process_step_result` restructured — mode-branched for ensure/retries/output_schema; `_make_record()` helper for StepRecord creation
- `stratum_step_done` gate guard updated — handles inline steps (`function=""`)
- `MCPExecutionError` handling — all `get_current_step_info` call sites wrapped in server.py (3 locations)
- `retries_exhausted` response enriched — includes `step_mode` and `agent` fields

**Testing:** +27 tests; new file: `test_inline_steps.py` (27 tests)

**STRAT-ENG-3: Executor — gate policy evaluation, explicit skip**

- `PolicyRecord` — new audit trace type (`type: "policy"`) for auto-resolved gates; `_record_from_dict` updated for persistence
- `apply_gate_policy()` — evaluates `step.policy ?? "gate"`; `skip`/`flag` auto-approve with PolicyRecord and on_approve routing; does NOT call `resolve_gate` (no GateRecord for auto-approved gates)
- `_apply_policy_loop()` — server-layer loop handling chained auto-approved gates with visited-set cycle detection
- `skip_step()` — extracted helper from `get_current_step_info` skip_if path; gate steps rejected
- `stratum_skip_step` MCP tool — explicit step skipping with reason; gate steps return error
- Policy loop wired into `stratum_plan`, `stratum_step_done`, `stratum_gate_resolve`, `stratum_check_timeouts`

**Testing:** 349 tests passing (+44 from ENG-1/2/3); new file: `test_policy_skip.py` (29 tests)

---

## [0.1.3] — 2026-02-23

### Added

- `stratum-mcp uninstall` CLI command — removes Stratum config from a project: deletes `stratum` entry from `.claude/mcp.json` (removes file if empty), strips `## Stratum Execution Model` block from `CLAUDE.md` (removes file if empty), removes installed skills from `~/.claude/skills/`; `--keep-skills` flag preserves user-customized skill files
- 13 new tests for `uninstall` (mcp.json removal, CLAUDE.md removal, skill removal, `--keep-skills`, roundtrip setup→uninstall→setup, idempotency messaging) — 79 total passing

### Added

**MCP server (Track 2) — `stratum-mcp`**

- `stratum_validate` — validates a `.stratum.yaml` IR spec; returns `{valid, errors}`
- `stratum_plan` — validates a spec, creates in-memory flow execution state, returns the first step to execute with resolved inputs and output contract details
- `stratum_step_done` — accepts a completed step result from Claude Code, checks `ensure` postconditions, returns next step or flow completion; handles retries and exhaustion
- `stratum_audit` — returns per-step execution trace (attempts, duration) for an active or completed flow
- MCP controller model: Claude Code is the executor; the server manages plan state and enforces contracts — no sub-LLM calls, no separate API billing
- `FlowState` — in-memory execution state per flow: ordered steps, accumulated outputs, attempt counts, dispatch timestamps, step records
- `ensure` expressions evaluated by the server against Claude Code's reported output (Python expressions, dunder-blocked, SimpleNamespace-wrapped for dict access)
- `$.input.<field>` and `$.steps.<id>.output[.<field>]` reference resolution for chaining step outputs
- Kahn's topological sort on explicit `depends_on` + implicit `$.steps.*` ref dependencies
- `stratum-mcp install` — one-command project configuration: writes `.claude/mcp.json` (MCP server registration), appends execution model block to `CLAUDE.md`, and installs seven Claude Code skills to `~/.claude/skills/`; idempotent, finds project root via `.git` or `CLAUDE.md`
- Nine Claude Code skills installed by `setup`: `stratum-onboard` (read codebase cold, write `MEMORY.md` from scratch), `stratum-plan` (design feature, present for review — no implementation), `stratum-review` (three-pass code review), `stratum-feature` (read → design → implement → test), `stratum-debug` (hypothesis formation and elimination), `stratum-refactor` (extraction order planning, no broken intermediate states), `stratum-migrate` (rewrite bare LLM calls as `@infer` + `@contract`), `stratum-test` (write test suite for existing code — golden flows, error-path harness), `stratum-learn` (extract patterns from session transcripts into `MEMORY.md`)
- Each skill contains a spec template Claude adapts internally — YAML never shown to the user; Claude narrates in plain English
- All skills include a `## Memory` section: read project `MEMORY.md` before writing spec (incorporate `[stratum-<skill>]` tagged patterns); write new patterns after `stratum_audit`
- CLI triple-mode: `stratum-mcp install`, `stratum-mcp validate <file>`, stdio MCP transport
- 66 passing tests across contracts, invariants, and integration suites

**Dependencies:** `mcp>=1.0`, `jsonschema>=4.20`, `pyyaml>=6.0` — no stratum library dependency

### Architecture decision

The MCP server does not use the Track 1 stratum library at runtime. Executing infer steps via the library (litellm) would spawn separate billed API calls outside the Claude Code subscription. The MCP controller model keeps all execution inside the running Claude Code session: Claude Code writes the spec, reports step results, and the server tracks state and enforces contracts.

---

## [0.1.0] — 2026-02-23

### Added

**Core library (Track 1)**

- `@contract` — registers a pydantic `BaseModel` subclass as a typed contract; generates JSON Schema via `model_json_schema()`, stores a 12-char content hash for drift detection
- `@infer` — LLM-backed inference step; async-first, typed return, structured retry on `ensure` failure, budget enforcement, session cache, OTLP trace records
- `@compute` — deterministic step marker; function executes normally, composes identically with `@infer` at call sites
- `@flow` — async flow wrapper; injects `flow_id` + `Budget` clone into a `ContextVar` so nested `@infer` calls inherit them without explicit passing; session cache scoped per flow execution
- `@refine` — convergence loop stacked on `@infer`; iterates with feedback context until `until(result)` passes or `max_iterations` exhausted → `ConvergenceFailure`
- `parallel(require=)` — `"all"` / `"any"` / N / `0` modes using `asyncio.TaskGroup`; `require=0` returns `list[Success | Failure]`
- `race()` — alias for `parallel(require="any")`
- `debate()` — multi-agent structured argumentation with rebuttal rounds and a synthesizer step
- `await_human()` — HITL gate; suspends flow until a `ReviewSink` resolves a `PendingReview`; supports `timeout` and `on_timeout`
- `quorum=` on `@infer` — runs N parallel calls, asserts `threshold` agreement on `agree_on` field, returns highest-confidence agreeing result
- `stable=False` on `@infer` — return type becomes `Probabilistic[T]`; caller must call `.most_likely()`, `.sample()`, or `.assert_stable()`
- `stable=True` test mode — when `stratum.configure(test_mode=True)` is set, samples `sample_n` times and raises `StabilityAssertionError` if outputs are not unanimous
- `Probabilistic[T]` — wraps a sample of LLM outputs; `.most_likely()`, `.sample()`, `.assert_stable(threshold)`
- `Budget(ms=, usd=, tokens=)` — time + cost + token envelope; enforced via `asyncio.timeout` and LiteLLM cost tracking
- OTLP trace export — built-in emitter posts spans over HTTP/JSON to any OTLP endpoint; no OTel SDK dependency; `traceId` derived from `flow_id` so all `@infer` spans in a flow share a trace
- `opaque[T]` annotation — marks fields excluded from the tool-call schema (present in output but not constrained)

**Exceptions**

- `StratumCompileError` — static violations at decoration time
- `PreconditionFailed` — `given` condition false before LLM call
- `PostconditionFailed` — `ensure` violations after all retries
- `ParseFailure` — LLM output cannot be parsed against contract schema
- `BudgetExceeded` — time or cost budget exceeded
- `ConvergenceFailure` — `@refine` exhausted `max_iterations`
- `ConsensusFailure` — `quorum` could not reach `threshold` agreement
- `ParallelValidationFailed` — `parallel` `validate` callback returned False
- `HITLTimeoutError` — `await_human` wall-clock timeout with `on_timeout="raise"`
- `StabilityAssertionError` — `Probabilistic[T].assert_stable()` below threshold

### Dependencies

- `litellm>=1.0` — LLM client, multi-model routing, cost tracking
- `pydantic>=2.0` — required; `@contract` requires `BaseModel`
- Python 3.11+ — `asyncio.TaskGroup`, `asyncio.timeout`
