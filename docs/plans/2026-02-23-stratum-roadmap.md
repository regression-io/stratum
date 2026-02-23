# Stratum Roadmap

## Phase 1 — Python Library (v1) `IN_PROGRESS`

Core constructs, execution model, LiteLLM integration.

- `@contract`, `@infer`, `@compute`, `@flow` decorators
- `given` / `ensure` preconditions and postconditions
- Structured retry with auto-generated feedback prompt
- `refine` convergence loop
- `parallel` with `require:` semantics
- `await_human` suspension primitive
- `Probabilistic[T]` / `stable` flag
- Hard budget enforcement (`asyncio.timeout`)
- In-memory trace; OTLP export via `stratum/exporters/otlp.py`
- LiteLLM as required substrate (one dependency)
- Pydantic as optional enhanced backend

See `docs/library/how-to-build.md` for build sequence.

---

## Phase 2 — MCP Server + TypeScript Library `PLANNED`

- `.stratum.yaml` IR parsing and validation (jsonschema + pyyaml)
- MCP server: Claude Code integration, typed plan emission
- TypeScript library: Zod contracts, `@anthropic-ai/sdk` substrate
- IR round-trip: Python library → IR → MCP execution

---

## Phase 3 — Integrations (build from observed pain) `PLANNED`

- **DSPy-backed prompt optimization** — `context:` becomes optionally DSPy-backed; same `@infer` interface, learned internals. Target: teams with labeled data and stable task definitions.
- **Temporal** — durable execution for long-running flows
- **Ray** — distributed agent execution
- **Outlines** — self-hosted constrained decoding via LiteLLM → vLLM → Outlines

---

## Open Design Items

### `@adaptive` — runtime dispatch between `compute` and `infer` `PLANNED`

A single function that routes to either a `compute` or `infer` implementation at runtime.

**Settled:**
- Dispatch can be a `compute` function, a lambda, or a `flow`-level condition
- `ensure` applies to both paths (behavioral contract on output, not on path)
- Trace records: `dispatch_type`, `dispatch_result`, `path_taken`, `ensure_violations`
- v1 scope: binary dispatch (compute vs infer); multi-way routing handled by `flow` + `orchestrate`

**Deferred to v2: `infer` as dispatch function**

The dispatch predicate itself could be an `infer` — an LLM decides which path to take. Valid use case: routing based on input ambiguity or semantic complexity. Open question: if dispatch is `infer`, routing becomes non-deterministic; the same input could take different paths on different runs. Possible constraint: require `stable: true` on the dispatch function, or propagate `Probabilistic` to the whole `@adaptive`. Needs more thought before committing to semantics.
