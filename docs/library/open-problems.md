# Open Problems

These are unresolved design questions. Some are hard; some are just underspecified. Record them here to avoid re-litigating them blindly later.

Status labels: **Resolved** | **Partially resolved** | **Deferred (v2)** | **Unresolved**

---

## 1. Prompt Stability Under Contract Evolution

**Problem**: If you change a `contract`, the schema injected into LLM prompts changes. This silently changes LLM behavior — not a bug, not a type error, just drift.

A field rename in a contract changes the prompt. LLM behavior may shift. No test will catch this unless you explicitly test LLM output distributions.

**Options**:
- Require explicit version bumps on contracts (`contract SentimentResult v2 { ... }`)
- Generate a content hash automatically and embed it in all trace records
- Provide a `contract diff` tool that shows prompt-level impact of schema changes

**Status**: Resolved. Auto-generated content hash on every contract, embedded in all trace records. Behavioral regression detection via hash comparison across deployment boundaries is the mechanism — prevention is out of scope. `contract diff` tool deferred to v2.

---

## 2. Non-Determinism in a Typed System

**Problem**: The type system assumes functions are deterministic — same input, same output. `infer` functions are not. The type system currently papers over this.

Consequences:
- You cannot reliably cache `infer` results without accepting staleness
- Callers that expect pure functions may be surprised by non-determinism
- Two calls to the same `infer` function with the same input may produce different typed results, both of which pass `ensure`

**Options**:
- `Probabilistic<T>` wrapper type — makes non-determinism explicit, forces callers to handle it
- `Stable<T>` annotation — assert that this `infer` function has been tested for output stability, runtime samples N times and warns if distribution is wide
- Ignore it and treat non-determinism as an operational concern (current position)

**Status**: Resolved. Hybrid model:
- `stable=True` (default) — developer assertion; runtime samples in test mode and warns if distribution is wide; production trusts the assertion; return type is `T`
- `stable=False` — return type is `Probabilistic[T]`; caller must explicitly unwrap via `.most_likely()`, `.sample()`, or `.assert_stable()`; correct for generative/open-ended tasks where variance is expected
- The binary is intentional — it forces a visible decision at the `@infer` site without burdening every caller by default
- Formalism (probability distributions, confidence intervals, type-level variance bounds) deferred — the shape is open to it later without breaking the surface API

---

## 3. Debugging When the Failure Is Inside an LLM

**Problem**: What does a stack trace look like when the failure occurred inside an `infer` block?

With `compute`, a stack trace points to source lines. With `infer`, the failure is inside the LLM — there is no source line. The trace record tells you the input, output, and which `ensure` failed, but not *why the LLM produced that output*.

**What we have**:
- Structured trace: input → compiled prompt → raw LLM output → parse result → ensure result
- Full retry history as a first-class artifact
- v1 retries send full context (not just failure delta) — richer debugging information at the cost of token efficiency

**Status**: Partially resolved. The trace record structure addresses what's addressable. The "why the LLM produced that output" is not answerable with current LLM technology — this is a ceiling of the field, not a gap in the design.

---

## 4. Cost and Latency as First-Class Concerns

**Problem**: `infer` calls have real dollar costs and latency that `compute` calls don't. The language needs to treat this as a first-class concern, not an afterthought.

**Current design**:
- `budget` annotations per `infer` function — hard cap enforced by runtime
- `flow`-level budget as a total envelope for the whole flow
- Budget tracked in every trace record

**Remaining gaps**:
- Retries multiply cost unpredictably — a `refine` loop's cost is `infer_cost × iterations` where iterations aren't known in advance
- Cost estimation before execution (not just measurement after) is undesigned

**Status**: Resolved for v1. Per-call and per-flow budget enforcement is the hard cap. Pre-flight estimation is deferred — it's a data product built on observed cost/latency distributions from trace records, not a static analysis problem. Accurate metrics must come before estimation; building estimators on thin data produces worse outcomes than no estimation. Revisit when the telemetry layer has real workload data.

---

## 5. Versioning and Backward Compatibility

**Problem**: How do you evolve an `infer` function signature without breaking callers?

For `compute`, this is standard software engineering — semver, deprecation, migration.

For `infer`, it's more complex:
- Changing the `contract` changes LLM behavior (see Problem 1)
- Changing `context` annotations changes LLM behavior (no type error)
- Changing `ensure` conditions changes which outputs are accepted (type-safe but semantically breaking)
- Changing `model` changes everything (no type-level representation)

**Status**: Deferred. Content hash (Problem 1) is the detection primitive — a hash change is an implicit behavioral version bump. Formal behavioral versioning (pinning, opt-in upgrades, downstream consumer notification) is v2+, designed from real contract evolution data. Cannot be designed correctly without observing what actually breaks in production.

---

## 6. Multi-Model Orchestration

**Problem**: Different `infer` functions may want to run on different models. A `flow` may need to route different steps to different providers.

**Current design**: `model` annotation per `infer` function.

**Remaining gaps**:
- Provider failover and fallback are not represented
- Model selection based on runtime conditions (input length, budget remaining) is undesigned

**Options**:
- `model: fast | balanced | best` aliases that resolve at runtime
- First-class `fallback` syntax: `model: "claude-opus-4-6" fallback: "claude-sonnet-4-6"`

**Status**: Resolved. Multi-model routing and provider failover is a solved layer — LiteLLM (most widely used, explicit fallback lists, 100+ models) and OpenRouter (unified API, drop-in OpenAI-compatible endpoint) cover this well. Stratum's runtime accepts a configurable LLM client; `model:` annotations are hints passed through to the configured gateway. Dynamic routing, failover, and cost-based model selection are delegated to the gateway layer, not built natively. Document LiteLLM and OpenRouter as the recommended integration path.

---

## 7. Testing `infer` Functions

**Problem**: How do you test an `infer` function? The output is non-deterministic and depends on an external LLM.

**Designed approaches**:
1. **Mock mode**: Replace `infer` with a `compute` stub. Test `flow` orchestration logic without LLM involvement.
2. **Contract testing**: Assert `ensure` conditions hold across N samples from production. Catch behavioral regressions.
3. **Snapshot testing**: Record outputs for canonical inputs, alert on significant divergence.

**Note**: v1 retries send full context — test harnesses are simpler because behavior is more consistent with less context optimization complexity.

**Status**: Deferred. The designed approaches (mock mode, contract testing, snapshot testing) are directionally correct but not a v1 priority. The field hasn't converged on how to test LLM functions well. Build the runtime first, observe real usage, design the test harness from actual pain points.

---

## 8. Isomorphism to Natural Language

**Stretch goal**: Can the formal and intent layers be unified into a single artifact that non-programmers can read?

**Status**: Aspirational. Not a v1 or v2 constraint. The IR framing is the practical step in this direction — natural language in, typed execution plan out, human-readable summary for review.

---

## 17. `@adaptive` with `infer` Dispatch Predicate

**Problem**: `@adaptive` v1 accepts only deterministic dispatch predicates (`lambda` or `compute` function). A natural extension is allowing an `infer` function as the dispatch predicate — an LLM decides which path to take. Valid use case: routing based on input ambiguity or semantic complexity, where a rule-based predicate cannot make a reliable determination.

**The core tension**: If dispatch is `infer`, routing becomes non-deterministic. The same input could take different paths on different runs, making traces non-reproducible and costs unpredictable.

**Options**:
- Require `stable=True` on the `infer` dispatch function — developer asserts the routing decision is stable; runtime samples in test mode and warns if routing varies
- Propagate `Probabilistic` to the whole `@adaptive` output when dispatch is `infer` — caller must unwrap, making non-determinism explicit
- Disallow entirely; multi-way or LLM-routed dispatch belongs in `flow` + `orchestrate`

**Status**: Deferred (v2). v1 raises `StratumCompileError` if `dispatch` is an `@infer` function. Design from real use cases once `@adaptive` is in production.

---

## 16. Transpiler Layer

**Two directions**:

**Inbound** (other formats → .stratum IR): migration and acquisition tool. n8n workflows are the first target (already in go-to-market). LangChain chains and DSPy modules are natural next targets — import existing workflows, flag untyped inter-step boundaries as contract gaps. This is a developer onboarding tool, not a core language feature.

**Outbound** (.stratum IR → Python/TypeScript): architectural inversion of the current model. Today: Python decorators emit IR as a side effect. Inverted: IR is the source of truth, Python/TypeScript are codegen targets. Consequences:
- Claude generates `.stratum`, developer receives editable Python/TypeScript
- Single spec, multiple language targets
- Libraries become views over the IR rather than primary authoring surfaces

The outbound direction is where the IR framing leads naturally if the project matures. It's a different product — bigger bet, cleaner architecture long-term.

**Status**: Inbound transpilers (n8n first) are v2 acquisition tools — build when the runtime is solid and there's a warm audience to migrate. Outbound transpiler is a long-term architectural direction, not a v1 or v2 commitment. Note it now, revisit when the IR spec is stable.

---

## 9. Shared Mutable State Between Parallel Agents

**Problem**: Agents running in a `parallel` block must not share mutable state — but the language doesn't currently enforce this. Race conditions in non-deterministic agents are harder to debug than in deterministic code.

**Options**:
- Static analysis: disallow mutation of shared bindings inside `parallel`
- Runtime isolation: each branch runs in isolated memory context; results merged at boundary
- Message passing only: agents communicate via typed messages (Erlang model)

**Status**: Resolved for v1. The isolation model is **git worktrees**: outer bindings are read-only inside `parallel` (compiler-enforced, not conventional), agent instances are branch-scoped (type system prevents sharing), `compute` functions must be pure or idempotent (developer responsibility). This closes the common cases without a message protocol. Message-passing is the right v2 concurrency model for inter-agent communication beyond parallel blocks.

---

## 10. Partial Failure in `parallel`

**Problem**: If one branch of a `parallel` block fails, what happens to the others? Cancel-all is safe but usually wrong.

**Options**:
- `parallel { } on_partial_failure: collect` — gather succeeded results, attach failures as metadata
- `parallel { } require: all | any | N` — specify minimum success count
- Per-branch `?` suffix: `let result = infer call(x)?` — treat failure as null

**Status**: Resolved. `require: all | any | N | 0` is the structural floor — enforced by the runtime, non-negotiable. `validate: compute | infer` adds semantic quality checks on top. In `orchestrate`, the LLM chooses both values when generating the plan; once committed, both are enforced as contracts. `require: 0` changes the return type to `Result<T>[]` — the plan validator propagates this to downstream step input types.

---

## 11. Budget Contention in Parallel Execution

**Problem**: Multiple parallel branches competing for a shared budget limit creates non-deterministic preemption.

**Status**: Deferred (v2). v1 accepts full context and doesn't aggressively optimize parallel token cost, so contention is less acute. Revisit when the token efficiency layer is built and parallel workloads are real.

---

## 12. Debate Termination and Unresolvable Disagreement

**Problem**: A `debate` with `rounds: N` terminates at N regardless of convergence. Genuine disagreement is a signal the synthesizer should receive, not an artifact it has to infer.

**Resolution**:
- Runtime computes `converged: bool` from round-over-round semantic similarity and passes it explicitly to the synthesizer
- Synthesizer output contract includes `resolution_type: "consensus" | "disagreement" | "partial"`
- When `converged: false` and `resolution_type: "disagreement"`, the flow triggers a HITL pause rather than forcing a synthesized middle ground — the argument history is surfaced for human resolution before the flow resumes
- `agree_threshold` for early exit is deferred (v2)

**Status**: Resolved. See also Problem 15 (HITL as a first-class mechanism).

---

## 13. Agent Identity and Trust

**Problem**: In a multi-agent flow, one agent's typed output becomes another agent's input. Prompt injection within the semantic content of string fields is not blocked by contract validation.

**Current design**: Typed contracts as the trust boundary — agent outputs are always parsed and validated before being passed downstream. Agents cannot see each other's compiled prompts, only their typed outputs.

**Remaining gap**: String fields in contracts are still injectable. A `reasoning: string` field can contain adversarial content that influences the next agent.

**Status**: Resolved. `opaque[T]` is a v1 field-level type modifier. Fields marked `opaque[T]` are passed to the LLM as structured JSON attachments, never interpolated inline into prompt instruction text. The prompt compiler raises `StratumCompileError` at compile time if an `opaque[T]` field is referenced in an inline string interpolation — structural enforcement, not a lint warning. This is the parameterized query pattern applied to prompt construction: the LLM still sees the data, but its instructions cannot be overwritten by it. `opaque[str]` is assignable to `str` and transparent to the type system otherwise; the restriction is in the prompt compiler only. See `type-system.md` for the `opaque[T]` spec and `execution-model.md` for prompt compiler handling.

---

## 15. Human-in-the-Loop (HITL)

**Problem**: Some flows cannot resolve autonomously. Debate non-convergence is the clearest case, but HITL applies more broadly:
- `debate` produces `resolution_type: "disagreement"` → human decides
- `infer` fails `ensure` after max retries → human reviews failure + retry history
- `infer` produces a result below a confidence threshold → human approves before flow continues

**Design shape**:
- `await_human(context, options) -> HumanDecision` — a first-class `compute` primitive that suspends the flow
- The flow serializes its state, emits a review event, and resumes when a decision arrives
- Timeouts on HITL steps need budget treatment (clock time, not token cost)
- Escalation is an output path, not an exception — the downstream type system must account for the `HumanDecision` result

**Status**: Resolved. `await_human` is a first-class `compute` primitive that genuinely suspends flow execution via `asyncio.Future`. Returns `HumanDecision[T]` — a typed wrapper preserving reviewer identity, rationale, and timestamp — so downstream code knows whether a value came from a human or an LLM. Timeout is wall-clock time (`timedelta`), not token budget. The runtime emits review requests to a `ReviewSink` protocol; the default v1 sink is a console sink with blocking `input()`. Webhook/queue sinks are v2. Implicit triggers (debate disagreement auto-escalation, retry exhaustion, confidence thresholds) are v2 — v1 requires explicit `await_human` calls in the flow. See `type-system.md` for `HumanDecision[T]` and `HITLTimeoutError`. See `execution-model.md` for suspension mechanics and the `ReviewSink` protocol.

---

## 14. What Is the Hosting Language?

**Problem**: Stratum needs to interop with existing code. What is it embedded in?

**Status**: **Resolved.** The IR framing settles this. Stratum is not a standalone language developers write. It is:
- Authored via Python `@infer`, `@contract`, `@flow` decorators (primary surface)
- Authored via TypeScript equivalents (secondary surface)
- Generated by Claude from natural language (via MCP server / plan skill)
- Represented internally as `.stratum.yaml` IR — the interchange format between authoring surfaces and the runtime

The standalone language is the correct long-term design if Stratum gets native integration. The embedded library is the v1 and v2 reality. This is no longer an open question.
