# Changelog

## [Unreleased]

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
- `stratum-mcp setup` — one-command project configuration: writes `.claude/mcp.json` (MCP server registration) and appends execution model block to `CLAUDE.md`; idempotent, finds project root via `.git` or `CLAUDE.md`
- CLI triple-mode: `stratum-mcp setup`, `stratum-mcp validate <file>`, stdio MCP transport
- 62 passing tests across contracts, invariants, and integration suites

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
