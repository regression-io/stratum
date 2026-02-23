# Design Tensions

A map of orthogonal concerns that compete for the same design space. For each pair: what optimizing one costs the other, whether the tension is fundamental or resolvable, and where the language cursor should sit.

---

## Tension Matrix

|  | Token Efficiency | Parallelization | Formal Guarantees | Consensus Quality | Composability | Latency | Auditability | Context Richness | Determinism | Security | Fault Tolerance | Testability |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **Token Efficiency**  | — | H | ~ | H | + | ~ | ~ | H | ~ | ~ | H | ~ |
| **Parallelization**   | H | — | H | ~ | ~ | + | ~ | H | ~ | H | + | S |
| **Formal Guarantees** | ~ | H | — | ~ | + | S | + | ~ | H | + | ~ | + |
| **Consensus Quality** | H | ~ | ~ | — | ~ | H | + | + | ~ | ~ | + | H |
| **Composability**     | + | ~ | + | ~ | — | ~ | + | H | + | H | ~ | + |
| **Latency**           | ~ | + | S | H | ~ | — | S | H | + | S | H | ~ |
| **Auditability**      | ~ | ~ | + | + | + | S | — | ~ | + | + | + | + |
| **Context Richness**  | H | H | ~ | + | H | H | ~ | — | ~ | H | ~ | S |
| **Determinism**       | ~ | ~ | H | ~ | + | + | + | ~ | — | + | S | + |
| **Security**          | ~ | H | + | ~ | H | S | + | H | + | — | ~ | ~ |
| **Fault Tolerance**   | H | + | ~ | + | ~ | H | + | ~ | S | ~ | — | S |
| **Testability**       | ~ | S | + | H | + | ~ | + | S | + | ~ | S | — |

**✗ hard** = fundamental, irreducible trade-off
**✗ soft** = tension resolvable with good engineering
**~** = context-dependent, tunable
**✓** = these concerns reinforce each other

---

## 1. Token Efficiency vs. Parallelization

**The tension**: Parallel agents need context to reason well. Sending full context to N agents multiplies token cost by N. The more you parallelize, the more tokens you spend.

```
sequential: 1 × context_tokens
parallel N: N × context_tokens     (naive)
parallel N: 1 × context_tokens + N × delta_tokens   (ideal)
```

`race` and `quorum` are worst case — they intentionally run redundant work. `quorum: 3` triples token cost by design.

**Why it's fundamental**: You can't give an agent less context without risking worse decisions. You can't give agents shared context without either serializing them or paying for duplication.

**Where the cursor should sit**:
- Use `DocRef` + semantic retrieval so each agent fetches only what it needs, not the full document
- Shared invariants (contracts, global context) are injected once at the `flow` level, not per agent
- `quorum` and `race` are explicitly opt-in — the developer accepts the cost trade-off consciously
- The token audit tool surfaces parallelization cost so the developer can make informed choices

**What the language should NOT do**: silently duplicate context across parallel branches. It must be explicit when you're paying for parallelism.

---

## 2. Parallelization vs. Formal Guarantees

**The tension**: Static analysis requires knowing the structure of a program before it runs. Dynamic orchestration (`orchestrate`, `adapt`) determines structure at runtime. You cannot statically type-check a flow whose shape is determined by an LLM.

```stratum
// Statically verifiable — type checker knows the shape
flow f(x: Input) -> Output {
  let a = infer stepA(x)    // type: IntermediateA
  let b = infer stepB(a)    // type: Output — checked
  return b
}

// Not statically verifiable — shape unknown until runtime
orchestrate f(x: Input) -> Output {
  // LLM decides how many steps, which agents, what order
}
```

For `orchestrate`, the type checker can only verify:
- The input type
- The output contract (fixed)
- That the declared `available` agents exist and have valid signatures
- That the `ExecutionPlan` contract is valid

It cannot verify inter-step type compatibility at compile time.

**Why it's fundamental**: Static analysis and dynamic structure are definitionally incompatible. A fully dynamic program is not statically analyzable.

**Where the cursor should sit**:
- `flow` = fully static, fully typed, full static analysis
- `orchestrate` = dynamically structured, typed boundaries only (input + output contracts)
- The language makes this distinction explicit — you choose static or dynamic per entry point
- `orchestrate` is not a replacement for `flow`. It's an escape hatch for genuinely open-ended problems. If you know the structure, use `flow`.
- Static-first: prefer `flow`, reach for `orchestrate` only when the structure cannot be known at write time

---

## 3. Token Efficiency + Composability (reinforcing)

These concerns point in the same direction. Composability enforces narrow function inputs — each `infer` call receives only what it declared, never irrelevant data. That *is* the minimal prompt principle applied to function signatures. The prompt compiler can be maximally aggressive about stripping non-essential content when contracts are tight.

Additional reinforcement:
- Caching operates at function boundaries — a composed step that hits cache costs zero tokens for that call
- Reusable composed functions amortize their prompt overhead across all callers
- Narrow contracts make constrained decoding easier — smaller output space, fewer tokens needed to reach a valid result

**The real conflict is composability vs. context richness**, not composability vs. token efficiency. Function boundaries lose ambient context — the sub-function doesn't know why it's being called, what the broader goal is, or what the caller already knows. You either accept that quality loss, or you compensate by threading extra context through — and that compensation costs tokens.

That cost belongs to the context richness axis, not the token efficiency axis. The confusion: compensating for boundary context loss looks like a token efficiency problem, but it's actually a design quality problem. Well-designed composable systems don't need to compensate because the contracts are scoped correctly from the start.

**Where the cursor should sit**:
- Flow-level `context` annotations inherited by all child `infer` calls — propagates intent without coupling function signatures or inflating individual call prompts
- If a composed function keeps needing extra ambient context, that's a signal the decomposition is wrong, not that composability is expensive

```stratum
// Flow-level context inherited by all child infer calls — zero extra tokens per call
flow analyzeForReport(doc: Document) -> Report {
  context: "Executive summary. Prioritize clarity over completeness."

  let summary   = infer summarize(doc)
  let sentiment = infer classifySentiment(doc)
  let report    = infer synthesize(summary, sentiment)
}
```

---

## 4. Consensus Quality vs. Latency

**The tension**: `quorum`, `debate`, and `refine` all improve output quality by running multiple passes. They are inherently serial (debate rounds) or redundantly parallel (quorum). Either way, they cost time.

```
single infer:    1 LLM call, minimum latency
quorum(3):       3 parallel LLM calls, latency = max(3 calls)
debate(2 rounds): 4+ serial LLM calls, latency = sum(rounds)
refine(n iters):  n serial LLM calls, latency = sum(iterations)
```

`debate` is the worst case — each round must complete before the next begins. You cannot parallelize it without losing the dialectical structure.

**Why it's fundamental**: Convergence requires iteration. Iteration requires time. There is no way to run multiple deliberate rounds faster than one round.

**Where the cursor should sit**:
- `quorum` and `debate` are opt-in, never default
- `debate` is reserved for genuinely contested or high-stakes decisions — not routine classification
- Provide a `fast` mode annotation that substitutes single `infer` for `quorum`/`debate` when latency matters more than confidence
- Make the latency cost visible: the token audit includes latency estimates per coordination pattern

```stratum
infer classify(text: string) -> Category {
  quorum: 3
  fast_mode: single   // override to single call when flow has latency budget
}
```

---

## 5. Constrained Decoding vs. Reasoning Flexibility

**The tension**: Constrained decoding enforces schema at token generation time — great for token efficiency, zero schema tokens in prompt. But it physically restricts which tokens the LLM can produce, which can interfere with chain-of-thought reasoning and complex judgment.

If the LLM needs to "think out loud" before committing to a structured answer, constrained decoding cuts off that thinking. The quality of structured output often depends on unstructured reasoning that precedes it.

**Why it's fundamental**: Constraining token space restricts what the model can say, including useful intermediate reasoning.

**Where the cursor should sit**:
- Two-phase generation: unconstrained scratchpad → constrained output
- The scratchpad is generated freely (chain-of-thought), then discarded
- The final output is constrained
- Scratchpad tokens cost money but buy quality for complex judgments
- Simple classifications (low reasoning demand) → pure constrained decoding, no scratchpad
- Complex judgments (high reasoning demand) → scratchpad + constrained output

```stratum
infer classifySentiment(text: string) -> SentimentResult {
  reasoning_mode: direct        // simple: constrained decoding only
}

infer evaluateRisk(scenario: Scenario) -> RiskAssessment {
  reasoning_mode: scratchpad    // complex: think freely, then produce structured output
  scratchpad_budget: 500 tokens
}
```

The runtime discards the scratchpad. It never appears in the output. But it was worth the token cost for complex reasoning tasks.

---

## 6. Dynamic Orchestration vs. Budget Predictability

**The tension**: `orchestrate` and `adapt` let the LLM decide how many agents to spawn and how many iterations to run. This makes total token cost fundamentally unpredictable — you can set `max_agents` and `max_replans` as ceilings, but the actual cost is determined at runtime.

A `flow` has predictable cost: you can compute exactly how many `infer` calls execute. An `orchestrate` can cost anywhere from 1 to `max_agents × max_depth` `infer` calls.

**Why it's fundamental**: Adaptability requires runtime decisions. Runtime decisions produce runtime costs.

**Where the cursor should sit**:
- `budget` is a hard cap, not a soft hint — the runtime enforces it, not the LLM
- Add `budget_reserve: X%` — the orchestrator sees a reduced apparent budget, holding back a reserve for unexpected complexity
- Cost estimation mode: run `orchestrate` in planning-only mode to get an execution plan and cost estimate before committing
- For cost-sensitive applications, require human approval of the plan before execution

```stratum
orchestrate solve(problem: Problem) -> Solution {
  budget: $1.00
  budget_reserve: 20%       // orchestrator sees $0.80, runtime holds $0.20 in reserve
  plan_approval: required   // print plan + estimated cost, wait for approval
}
```

---

## 7. Caching vs. Non-Determinism

**The tension**: Caching `infer` results saves tokens and latency. But LLM outputs are non-deterministic — the same input may produce different valid outputs on different calls. Caching collapses this distribution to a single point, which may not represent what you'd want.

Worse: cached results bypass `ensure` validation on cache hit. The cached result passed validation when it was generated, but subsequent contract changes may mean it no longer should.

**Why it's fundamental**: Deterministic caching and non-deterministic generation are in direct conflict. You can't have "always fetch a fresh result" and "never pay for the same computation twice" simultaneously.

**Where the cursor should sit**:
- Cache keyed on `(input_hash, contract_version, context_hash)` — contract or context changes invalidate cache
- `ensure` conditions are re-evaluated on cache hits — a cached result that passes the old contract but fails an updated `ensure` is re-generated
- Probabilistic cache: cache N results, return randomly sampled on hit (preserves some non-determinism)
- `cache: none` is the safe default for high-stakes outputs; `cache: session` is opt-in for performance

---

## 8. Auditability vs. Latency

**The tension**: Full trace records (compiled prompts, inputs, outputs, retry history, inter-agent messages) are essential for debugging, cost analysis, and generating training data. But writing traces is I/O, and detailed traces are large.

Synchronous trace writing adds latency to every `infer` call. Async trace writing is fast but can lose traces on crash.

**Why it's soft**: This is an implementation concern, not a design conflict. The tension is real but manageable.

**Where the cursor should sit**:
- Async trace writing by default — don't block `infer` execution on trace persistence
- Structured trace format so it can be compressed and streamed
- Trace sampling for high-volume, low-stakes flows (e.g., trace 10% of calls in production)
- Full traces in dev/test, sampled in production — configurable per deployment target

---

## 9. Agent Specialization vs. Coordination Overhead

**The tension**: More specialized agents produce better outputs on their narrow tasks. But more agents means more coordination — more inter-agent context passing, more orchestration tokens, more latency from scheduling.

Fine-grained decomposition has diminishing returns: at some point, the coordination cost exceeds the quality gain from specialization.

**Why it's fundamental**: Coordination cost grows with agent count. There is no free lunch.

**Where the cursor should sit**:
- Agent types should be coarse-grained, not nano-specialized
- Specialization via `role` annotation on `spawn`, not by creating dozens of agent types
- The `orchestrate` LLM should learn (via capability declarations and production traces) which decompositions produce quality gains vs. which just add overhead
- Default: fewer agents, broader scope. Reach for more agents when a single agent is demonstrably insufficient.

---

---

## Determinism

Non-determinism is a property of `infer` calls by definition — same input, different output across runs. Every design decision that touches caching, testing, formal verification, or debugging is affected.

### Determinism × Token Efficiency (~)
Non-determinism doesn't directly affect token count — a deterministic and non-deterministic call consume identical tokens. The indirect cost: non-deterministic outputs produce cache misses even for identical inputs, forcing re-computation that costs tokens. But this only matters when caching is in use. Tunable: cache-heavy workloads feel this; no-cache workloads don't.

### Determinism × Parallelization (~)
Parallelization doesn't affect whether individual calls are deterministic. You can parallelize deterministic or non-deterministic functions identically. The outputs may vary across parallel branches if non-deterministic, but `quorum` treats this as a feature not a bug. Orthogonal.

### Determinism × Formal Guarantees (H)
Static analysis assumes functions are pure: same input → same output. `infer` violates this at the language level. You can statically verify that a function *conforms to a contract* — the output type is correct — but you cannot statically verify that it always *satisfies postconditions*, because the output varies. An `ensure: result.confidence > 0.7` may pass on one run and fail on another with identical inputs. The type system says the output is `SentimentResult`; it cannot say it will always be a *good* `SentimentResult`. Hard conflict — formal guarantees and non-determinism are definitionally incompatible beyond structural type conformance.

**Cursor**: The type system covers structure (always enforced via constrained decoding). Postconditions cover semantics (enforced at runtime with retry). Accept that semantic guarantees are statistical, not absolute.

### Determinism × Consensus Quality (~)
`quorum` *uses* non-determinism productively — it runs the same call N times expecting variation and takes the majority. If the function were perfectly deterministic, quorum would return the same value N times (no benefit, just cost). Non-determinism is a precondition for consensus to add value. These aren't in tension; they're complementary. Neutral.

### Determinism × Composability (+)
Deterministic functions compose cleanly — if `f` and `g` are deterministic, `f(g(x))` is deterministic and the composed behavior is statically reasonably. Non-deterministic functions composed together produce compound non-determinism that's hard to reason about: which call introduced variance? Determinism simplifies compositional reasoning and makes the call graph analyzable.

### Determinism × Latency (+)
Deterministic outputs are cacheable without qualification — same input always produces same output, cache hit rate is maximized. Non-deterministic outputs either miss cache on identical inputs or serve stale results that may not reflect the current output distribution. More cache hits = lower effective latency. These reinforce.

### Determinism × Auditability (+)
Deterministic systems produce reproducible traces — you can re-run the same inputs and get the same outputs, making audit trails actionable. With non-deterministic systems, the trace records *what happened* but you can't reproduce it to investigate. Determinism makes "replay" debugging possible. Reinforcing.

### Determinism × Context Richness (~)
Richer context may *reduce* non-determinism by constraining the output space — more context gives the LLM less room to wander. But it doesn't eliminate non-determinism, and non-determinism doesn't require thin context. Largely orthogonal.

---

## Security

Prompt injection, agent trust, and data isolation are entirely absent from the original matrix. In a multi-agent system where agent outputs feed other agents' inputs, security is load-bearing.

### Security × Token Efficiency (~)
Security measures — input sanitization, output filtering, context isolation enforcement — add processing overhead but minimal token overhead. The main token cost would be injecting security-framing into prompts ("never reveal...") but well-designed systems express these as structural constraints, not prompt text. Mostly orthogonal.

### Security × Parallelization (H)
Each additional agent is an additional attack surface. An agent that receives user-controlled input and passes results downstream can be a prompt injection vector that propagates through the system — the injected instruction travels as typed output from one agent to the next. The more agents and communication channels, the larger the injection surface and the harder it is to contain or audit. Hard conflict: more parallelization = more propagation paths for injected content.

**Cursor**: The contract layer is the primary mitigation — typed outputs can't contain raw instructions if the contract doesn't have an unconstrained `string` field. Minimize unconstrained string fields in inter-agent contracts.

### Security × Formal Guarantees (+)
Formal contracts as trust boundaries: if an agent's output must conform to `SentimentResult { label: "pos"|"neg"|"neu", confidence: float[0..1], reasoning: string }`, a prompt injection that tries to make the agent output a command string fails at the schema validator. The contract is not just a type — it's a filter on what can propagate. Formal guarantees and security reinforce each other: tighter contracts = smaller injection surface.

### Security × Consensus Quality (~)
Running multiple agents (quorum, debate) doesn't make the system clearly more or less secure. If one agent is compromised by injection, `quorum` may dilute the malicious output (majority vote) or the injected content may be persuasive enough to influence multiple agents if they all receive the same injected input. Roughly neutral — the injection surface is upstream of consensus.

### Security × Composability (H)
Every function boundary where one agent's output becomes another agent's input is a potential injection point. The more composed the system, the more these boundaries exist. A deeply composed pipeline — each step's output feeds the next step's `context` — creates a chain of injection opportunities. The contract layer mitigates this but string fields remain injectable. Hard conflict: composability and security want opposite things at every boundary.

**Cursor**: Prefer `DocRef` over passing raw strings between agents. Minimize unconstrained string fields in contracts used for inter-agent communication. Treat every inter-agent boundary as untrusted input.

### Security × Latency (S)
Security checks are deterministic `compute` operations — input validation, output scanning, context isolation enforcement. These add latency, but it's bounded and fast. Resolvable with engineering — security checks run in microseconds, not milliseconds.

### Security × Auditability (+)
You need traces to detect and investigate security incidents. Without auditability, you can't know if injection occurred, where it entered, or what it affected. Auditable systems are securable systems. Strong reinforcement.

### Security × Context Richness (H)
Richer context = larger injection surface. Every additional piece of information passed to an agent is potentially user-controlled content. The maximum-context ideal (give the LLM everything it needs to reason well) and the minimum-injection-surface ideal (give the LLM only what it needs) are the same statement pulling in opposite directions. This is the core security/quality trade-off in all LLM systems — not unique to Stratum but unavoidable.

**Cursor**: Distinguish between developer-controlled context (safe, can be rich) and user-supplied content (untrusted, must be structurally isolated). Flow-level `context` annotations are developer-controlled. User inputs are typed, bounded, and never interpolated into system context.

---

## Fault Tolerance

Retry, fallback, graceful degradation. Distinct from latency: you can have high reliability *and* high latency (aggressive retry), or low reliability and low latency (fail fast). Both dimensions matter independently.

### Fault Tolerance × Token Efficiency (H)
Every retry costs tokens. A system designed for fault tolerance — aggressive retry, multiple fallbacks, circuit-breaker recovery — multiplies token consumption by the retry factor. If an `ensure` condition fails 3 times before succeeding, you've paid 4× the token cost. `refine` loops are bounded retries by design. Hard conflict: retries are the primary fault tolerance mechanism and they directly multiply token cost.

**Cursor**: `ensure` retries should be cheap and targeted — minimal retry prompts, not full context re-sends. Retries inject only the failure reason, not the full original context.

### Fault Tolerance × Parallelization (+)
Parallelization provides natural redundancy. If one branch of a `parallel` block fails, others can still succeed. `race` is fault tolerance by design — multiple parallel attempts, first success wins. Redundant parallel execution is a primary fault tolerance strategy that costs latency (max of branches) but not extra sequential time. Reinforcing.

### Fault Tolerance × Formal Guarantees (~)
Retry and fallback behavior is complex to specify formally — a `flow` that retries on failure has more complex state than one that doesn't. But the `ensure`/retry mechanism is *itself* a formal construct with defined semantics. Formal guarantees about the happy path don't preclude fault tolerance in the failure path. Largely orthogonal.

### Fault Tolerance × Consensus Quality (+)
`quorum` is fault-tolerant by definition — N−1 agents can produce wrong or failed outputs and the majority still wins. Debate with synthesis is resilient to a single poor argument. Consensus mechanisms inherently provide fault tolerance against individual agent failures or poor individual outputs. Reinforcing.

### Fault Tolerance × Composability (~)
Fault tolerance in composed systems means each composed step needs its own failure handling, or the whole flow needs top-level recovery. Neither requires or precludes the other — you can have composable fault-intolerant systems or monolithic fault-tolerant ones. Orthogonal.

### Fault Tolerance × Latency (H)
Retries add latency. Timeouts add latency (you wait for timeout before retrying). Circuit breakers add latency (wait for reset). Every fault tolerance mechanism except "fail fast and propagate" adds time. Hard conflict: reliability and speed pull in opposite directions.

**Cursor**: `budget: Xms` as a hard timeout per call, not per retry chain. Set the retry budget separately from the call budget. Make the latency cost of fault tolerance explicit and bounded.

### Fault Tolerance × Auditability (+)
Fault events — failures, retries, fallbacks, circuit-breaker trips — are exactly what you need in audit trails for debugging and reliability analysis. A system that records every retry attempt with its input, output, and failure reason is dramatically easier to improve than one that silently retries. Auditability makes fault tolerance diagnosable and improvable. Reinforcing.

### Fault Tolerance × Context Richness (~)
Context richness doesn't affect whether the system handles failures well. A context-rich system can be fault-tolerant or not. Orthogonal.

---

## Testability

Can you write reliable automated tests? Related to but distinct from composability (structure) and determinism (reproducibility). A system can be composable and non-deterministic; testable systems need to be *both* composable and sufficiently deterministic.

### Testability × Token Efficiency (~)
Testing doesn't affect production token consumption. Mock `infer` calls in tests have zero token cost — they don't invoke LLMs. Running integration tests against real LLMs is a testing cost, not a production cost. Orthogonal.

### Testability × Parallelization (S)
Parallel systems are harder to test deterministically — timing, ordering, and interleaving interact. But distributed systems testing has mature solutions: deterministic test schedulers, controlled timeouts, stub coordination layers. The challenge is engineering, not fundamental. Resolvable.

### Testability × Formal Guarantees (+)
Formal contracts are executable test specifications. An `ensure` condition IS a test oracle — property-based testing, fuzzing, and conformance testing can all be driven from contract definitions. The contract is the spec; the test validates the spec is met. Strong reinforcement: better contracts = better automated test coverage for free.

### Testability × Consensus Quality (H)
Testing consensus mechanisms requires running N LLM calls and asserting on majority agreement. This is expensive, slow, and non-deterministic — you can't reliably assert "this quorum produces label=positive" across all runs without statistical machinery (run 100 times, assert majority in >95% of runs). Even then it's probabilistic, slow, and expensive. Hard conflict: consensus mechanisms are inherently difficult to test reliably and cheaply.

**Cursor**: Mock `infer` calls in unit tests to simulate specific vote distributions. Reserve statistical consensus testing for CI with real LLMs. Accept that consensus behavior is validated in production via audit traces, not purely in pre-production tests.

### Testability × Composability (+)
Composable functions can be tested in isolation — mock the dependencies, test the unit. Classical unit testing made possible by function boundaries. The more composable the system, the more independently testable each piece is. This is one of the strongest arguments for composability: it makes the system testable without full integration. Reinforcing.

### Testability × Latency (~)
Testing doesn't impose production latency constraints. Tests can be slow (full integration against real LLMs) or fast (mock `infer` calls). Test latency is a developer experience concern, not a production design decision. Orthogonal.

### Testability × Auditability (+)
Audit trails produced during test runs are the best debugging tool when a test fails. When a test fails, the trace shows exactly what the LLM received, what it returned, which `ensure` failed, and the full retry history. Auditability makes test failures diagnosable rather than mysterious. Reinforcing.

### Testability × Context Richness (S)
Richer context requires richer test fixtures. If an `infer` function receives a large `DocRef`, flow-level context, and agent memory, creating the correct fixture for each test scenario is complex. But fixture management is an engineering problem with known solutions — factory patterns, fixture generators, golden files. Resolvable.

---

## Cross-Pairs Between New Axes

### Determinism × Security (+)
Deterministic behavior limits an attacker's ability to learn from output distributions. If a system always produces the same output for the same input, probing attacks (send the same prompt repeatedly, observe variance to extract information or find exploitable edge cases) yield no information. Non-deterministic systems leak information through output distributions. Determinism is a security property.

### Determinism × Fault Tolerance (S)
Non-determinism complicates retry semantics. If a function fails and you retry, a successful retry may produce a different valid output than would have succeeded the first time — you can't know if you "got the same answer." Deterministic functions make retry = replay: clean, predictable. But the contract validates the retry output regardless, so correctness is maintained even if the retry produces a different valid result. The tension is conceptual more than practical. Resolvable.

### Determinism × Testability (+)
Deterministic functions are directly unit-testable: same input, same output, assertion is a point check. Non-deterministic functions require statistical tests, property-based approaches, or acceptance of probabilistic assertions. Determinism collapses a distribution to a point and makes testing dramatically simpler. Strong reinforcement.

### Security × Fault Tolerance (~)
Largely orthogonal. Retry doesn't expand injection surface — the same prompt is re-sent to the same function, re-validated against the same contract. Circuit breakers don't affect security properties. One edge case: if a security check (output scanning) is what's *causing* failures and triggering retries, fault tolerance (retry) may mask the security signal rather than surfacing it. Worth monitoring in trace records but not a fundamental tension.

### Security × Testability (~)
Security testing (red-team tests, injection tests, adversarial inputs) is a distinct discipline from functional testing. It sits alongside functional tests, not in direct tension. The same composable structure that makes functional testing easy also makes security testing tractable — you can inject adversarial inputs at each function boundary independently. Roughly orthogonal.

### Fault Tolerance × Testability (S)
Fault tolerance mechanisms — retry logic, fallback chains, circuit breakers — need test coverage. But they're deterministic `compute` logic: you can inject specific failures via test fixtures and assert on recovery behavior. The non-determinism of what *causes* failures in production (LLM output variance) is the challenge, but controlled failure injection in tests makes retry and fallback behavior verifiable. Resolvable with engineering.

---

## Second-Order Interactions

Some tensions compound when combined:

### Token Efficiency + Parallelization + Constrained Decoding
Constrained decoding eliminates schema tokens per agent. But parallelizing N agents still multiplies input tokens by N. The combination gives you the best possible per-agent efficiency, but doesn't change the parallelization multiplier. Token efficiency and parallelization are independent axes.

### Dynamic Orchestration + Formal Guarantees + Token Efficiency
`orchestrate` produces an `ExecutionPlan` which is itself an `infer` call. That call has a schema (token-efficient via constrained decoding) and `ensure` conditions (validated post-parse). The orchestrator's reasoning quality may require a scratchpad. So dynamic orchestration costs: `orchestrator_tokens + plan_validation_tokens + execution_tokens`. The meta-level always adds overhead.

### Consensus Quality + Composability + Context Richness
Running `quorum: 3` on a composed `infer` function means 3 agents each receive the context-impoverished composed input. If the quality problem is at the composition boundary (information loss), quorum doesn't help — you get 3 unanimous wrong answers. Fix the composition first; add quorum only when the individual call is sound.

---

## Design Cursor Summary

**Priority note:** v1 optimizes for determinism, typed contracts, and structured retry. Token efficiency is a v2 concern — it's the optimization layer applied once the runtime works and real workloads exist to measure. Rows marked (v2) below describe the correct long-term position but should not drive v1 implementation decisions.

| Tension | Default position | Override when |
|---|---|---|
| Token efficiency vs. parallelization | (v2) Shared prefix caching; explicit opt-in for parallelism | v1: send full context, optimize later |
| Parallelization vs. formal guarantees | Static `flow` by default; `orchestrate` is escape hatch | Structure genuinely cannot be known at write time |
| Token efficiency vs. composability | (v2) Flow-level context inheritance | v1: accept full context at boundaries |
| Consensus vs. latency | Single `infer` by default | High-stakes, tolerance for latency, budget available |
| Constrained decoding vs. reasoning | `direct` for simple, `scratchpad` for complex | Task complexity determines reasoning mode |
| Dynamic orchestration vs. budget | Hard budget cap always; `budget_reserve` for safety | Never relax the hard cap |
| Caching vs. non-determinism | `cache: none` for high-stakes; `session` for performance | Low-stakes, same context, idempotent result expected |
| Auditability vs. latency | Async traces always on; sample rate tunable | Never disable traces entirely |
| Specialization vs. coordination | Coarse agents, role-based specialization | Narrow task with proven quality gap |
| Determinism vs. formal guarantees | Accept semantic guarantees are statistical; structural guarantees are absolute | Never — this is fundamental |
| Security vs. context richness | Isolate user-supplied content from developer-controlled context | Developer context can be rich; user content must be bounded |
| Security vs. composability | Treat every inter-agent boundary as untrusted; minimize unconstrained string fields | Never relax — every boundary is an injection point |
| Security vs. parallelization | (v2) `DocRef` over raw strings in inter-agent contracts | v1: typed contracts as boundary; DocRef deferred |
| Fault tolerance vs. token efficiency | (v2) Inject failure reason only, not full context | v1: full context on retry is fine; optimize when cost matters |
| Fault tolerance vs. latency | Hard timeout per call + separate retry budget; make cost explicit | Never hide retry latency from the caller |
| Testability vs. consensus quality | Mock `infer` for unit tests; real LLMs for statistical CI | Don't rely on statistical consensus tests as the primary correctness signal |
