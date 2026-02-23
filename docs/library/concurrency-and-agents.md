# Concurrency, Distribution, and Agent Coordination

Parallel execution, distributed processes, and sub-agent management are **top-level language concerns** in Stratum — not library features or operational afterthoughts. They are first-class constructs with the same formal guarantees as `compute` and `infer`.

---

## Primitives vs. Patterns

The constructs in this document are **language primitives** — the smallest composable units the runtime understands. Higher-level multi-agent patterns (actor-critic, constitutional AI, ensemble, reflexion, plan-and-execute) are built as a **library layer** on top of these primitives, not as language constructs. See [`patterns.md`](patterns.md).

The one exception: `debate` earned a first-class construct because its termination semantics (rounds, convergence detection, full argument history to synthesizer) are genuinely awkward to compose correctly from primitives. Everything else is library territory.

---

## Concurrency Substrate

`parallel`, `race`, and budget timeouts are implemented using Python's standard **asyncio** (3.11+):

- `parallel` → `asyncio.TaskGroup` — structured cancellation on branch failure, clean error propagation
- `race` → `asyncio.TaskGroup` + first-result short-circuit with `asyncio.timeout()`
- `delegate` → `asyncio.create_task()` (fire-and-forget)
- Budget timeouts → `asyncio.timeout()` — `TimeoutError` caught and re-raised as `BudgetExceeded`

Requires Python 3.11+. No additional concurrency dependency.

The runtime is async-first. `@infer` and `@flow` are async natively. A sync shim (`stratum.run()`) is provided for non-async contexts — it manages the event loop internally. Do not call from inside an already-running event loop.

```python
# async — native
result = await classify_sentiment(text)

# sync shim — for scripts and notebooks
result = stratum.run(classify_sentiment(text))
```

---

## Why This Is Different From Conventional Concurrency

In traditional distributed systems, parallel workers are **interchangeable** — they execute the same logic on different data. In Stratum, parallel agents are **reasoning entities** that can:

- Hold different context and specialization
- Produce conflicting outputs that require synthesis
- Disagree in ways that are semantically meaningful
- Spawn further sub-agents with delegated scope
- Debate, vote, or converge to a consensus

This changes the model fundamentally. You're not parallelizing computation — you're coordinating judgment.

---

## New Top-Level Constructs

### `parallel` — Concurrent Independent Execution

Run multiple steps concurrently within a `flow`. Results are collected and typed. Execution is concurrent; the `flow` waits for all branches unless `race` or `quorum` semantics are specified.

```stratum
flow analyzeDocument(doc: Document) -> DocumentAnalysis {
  parallel {
    let summary   = infer summarize(doc)
    let sentiment = infer classifySentiment(doc.text)
    let entities  = infer extractEntities(doc.text)
    let topics    = infer classifyTopics(doc.text)
  }
  return compute merge(summary, sentiment, entities, topics)
}
```

All four `infer` calls execute concurrently. The `parallel` block resolves when all branches complete (or any branch raises, by default). The cost envelope is the max of concurrent costs, not the sum of sequential costs.

#### Isolation model: git worktrees

The mental model for `parallel` isolation is **git worktrees**:

| Git worktrees | `parallel` branches |
|---|---|
| Shared git history — read-only to all worktrees | Outer `let` bindings — readable by all branches |
| Isolated working directory per worktree | Branch-scoped agent instances and local bindings |
| Changes in worktree A don't affect worktree B | Branch A's agent state is invisible to branch B |
| Explicit merge back to main | Typed result collection at the parallel boundary |
| Merge conflict resolution | `validate:` / `synthesize:` over collected results |

Concretely:
- **Outer bindings are read-only inside `parallel`.** Any `let` binding declared before the block is readable by all branches. Reassigning it inside a branch is a compile error.
- **Agent instances are branch-scoped.** A `spawn Analyst` inside a branch creates an instance that lives and dies with that branch. The same agent instance cannot be passed into two branches — the type system disallows it.
- **`compute` functions called from `parallel` must be pure or idempotent.** External side effects (database writes, file writes) are outside what the type system can enforce — developer responsibility.

The key difference from git: worktrees *can* write to the same files (it's just a conflict at merge time). `parallel` closes this off at the compiler level — outer binding immutability is structural, not conventional. The conflict cannot happen.

#### Partial failure: `require:` and `validate:`

By default, any branch failure cancels all branches and raises. Override with:

```stratum
parallel require: any {          // at least one branch must succeed
  ...
}

parallel require: 3 {            // at least 3 of N branches must succeed
  ...
}

parallel require: 0 {            // collect all results regardless of failure
  ...                            // return type is Result<T>[] not T[]
}
```

Add semantic quality validation on top of the structural floor:

```stratum
parallel require: any, validate: compute sufficientCoverage(results) {
  ...
}

// In orchestrate, the LLM can choose both:
parallel require: 3, validate: infer assessQuality(results) -> bool {
  ...
}
```

`require:` is enforced by the runtime — structural, non-negotiable. `validate:` is a postcondition on the collected results — same `ensure` mechanism applied at the block level.

---

### `race` — First Valid Result Wins

Run multiple strategies concurrently; take the first result that satisfies its `ensure` conditions. Cancel the rest.

```stratum
flow classify(text: string) -> Category {
  race {
    infer classifyFast(text)    // cheap, less accurate
    infer classifyBest(text)    // expensive, more accurate
    compute classifyRules(text) // deterministic, limited coverage
  }
}
```

Use case: latency-sensitive paths where you want to hedge across approaches. Also useful for model failover without explicit fallback logic.

---

### `quorum` — Multi-Agent Consensus

Run the same `infer` call N times (or across N specialized agents) and require a majority to agree before returning. Disagreement above a threshold raises `ConsensusFailure`.

```stratum
infer classifySentiment(text: string) -> SentimentResult {
  quorum: 3          // run 3 times
  agree_on: label    // consensus field
  threshold: 2       // at least 2 must agree
}
```

The runtime:
1. Invokes the function 3 times concurrently
2. Compares the `label` field across all 3 results
3. Returns the result from a majority-agreeing invocation (with the highest confidence)
4. If no majority exists, raises `ConsensusFailure` with all three outputs

`quorum` is the language-level answer to "how do you reduce LLM non-determinism for high-stakes decisions?"

---

### `debate` — Adversarial Multi-Agent Synthesis

A structured multi-round process where multiple agents argue different positions and a synthesizer produces a final output. Not just voting — actual dialectical reasoning.

```stratum
flow evaluateProposal(proposal: Proposal) -> Evaluation {
  debate {
    agents: [
      infer ArgueFor(proposal)    -> Argument { stance: "support" }
      infer ArgueAgainst(proposal) -> Argument { stance: "oppose" }
    ]
    rounds: 2                    // each agent sees the other's argument and responds
    synthesize: infer synthesizeDebate(proposal, arguments, converged) -> Evaluation
  }
}
```

Round structure:
1. All agents produce their initial `Argument`
2. Each agent receives the other agents' arguments and produces a rebuttal (repeated for `rounds`)
3. The runtime computes `converged: bool` from round-over-round semantic similarity
4. The `synthesize` function receives the full argument history plus `converged` and produces the final typed output

The synthesizer's output contract should include `resolution_type: "consensus" | "disagreement" | "partial"`. When `converged: false` and `resolution_type: "disagreement"`, the flow triggers a **HITL pause** rather than forcing a synthesized middle ground — the argument history is surfaced for human resolution before the flow resumes.

`debate` is particularly valuable for: risk assessment, document review, adversarial red-teaming, complex decisions with genuine trade-offs.

---

## `agent` — Stateful Named Entities

An `agent` is a persistent, stateful entity with its own context, memory, model, and lifecycle. Unlike `infer` functions (which are stateless invocations), agents accumulate context across multiple calls.

```stratum
agent Researcher {
  model: "claude-opus-4-6"
  memory: session               // context accumulates within session
  context: "You are a research specialist. Build on prior findings across calls."

  infer search(query: string) -> SearchResult { ... }
  infer synthesize(findings: SearchResult[]) -> Report { ... }
  infer followUp(report: Report, question: string) -> Clarification { ... }
}
```

Agents are spawned, used, and terminated explicitly:

```stratum
flow deepResearch(topic: string) -> Report {
  let researcher = spawn Researcher
  let initial    = researcher.search(topic)
  let expanded   = researcher.search(initial.relatedTopics.join(", "))
  let report     = researcher.synthesize([initial, expanded])
  terminate researcher
  return report
}
```

Agent state (accumulated context) is scoped to the agent instance. Two spawned `Researcher` agents are independent.

---

### `spawn` — Create a Sub-Agent

`spawn` creates an agent instance. Agents can spawn sub-agents.

```stratum
let agent = spawn Researcher                    // default config
let agent = spawn Researcher with {             // override config
  model: "claude-haiku-4-5-20251001"
  context: "Focus only on peer-reviewed sources."
}
```

Sub-agents spawned within an `infer` block inherit the parent's context annotations unless explicitly isolated:

```stratum
infer orchestrate(task: Task) -> Result {
  let sub = spawn Worker isolated  // no context inheritance
  let sub = spawn Worker           // inherits parent context
}
```

---

### `delegate` — Hand Off a Task

`delegate` sends a task to an agent and optionally waits for the result. Enables fire-and-forget patterns and long-running background work.

```stratum
flow processQueue(items: Item[]) -> Summary {
  // Fire off all items in parallel, don't wait
  let workers = items.map(item => {
    let w = spawn Worker
    delegate w.process(item)   // non-blocking
    return w
  })

  // Wait for all results
  let results = await workers.map(w => w.result)
  terminate workers
  return compute aggregate(results)
}
```

---

### `supervise` — Agent Lifecycle and Failure Management

A `supervise` block manages a pool of agents with restart policies, analogous to Erlang OTP supervisors.

```stratum
supervise WorkerPool {
  agent: Worker
  count: 5                          // pool size
  restart: on_failure               // or: always, never
  max_restarts: 3
  strategy: one_for_one             // or: one_for_all, rest_for_one
}

flow processWithSupervision(items: Item[]) -> Result[] {
  let pool = spawn WorkerPool
  let results = pool.map(item => pool.process(item))
  return results
}
```

Failure semantics:
- `one_for_one`: restart only the failed agent
- `one_for_all`: restart the entire pool on any failure
- `rest_for_one`: restart the failed agent and all agents spawned after it

---

## Context Propagation in Distributed Execution

When agents execute in parallel or across processes, context must be explicitly scoped.

### What Propagates Automatically
- The calling `flow`'s contract schemas (type validation applies everywhere)
- Budget: child agents draw from the parent's budget envelope
- Trace ID: all agents in a flow share a trace ID for unified observability

### What Must Be Explicitly Passed
- `intent` annotations (agents don't inherit parent intent by default)
- `context` annotations (unless agent is spawned without `isolated`)
- Input data (agents receive explicit typed arguments, not ambient state)

### What Is Isolated
- Agent memory (`memory: session` is per-agent-instance, not per-flow)
- Model configuration (each agent has its own)
- Retry state (an agent's retry budget is independent)

---

## Distribution Model

Stratum's execution model is location-transparent. An `infer` call or `agent` invocation may execute:
- In-process (same runtime)
- In a remote worker process
- On a different machine
- Via an external API

The calling code is identical in all cases. Distribution is a runtime/deployment concern, not a language concern.

The contract layer is the serialization boundary. Because all `infer` inputs and outputs are typed contracts that compile to JSON schemas, they are inherently wire-serializable. No manual serialization code.

### Distribution Substrate

**v1 — asyncio** (`asyncio.TaskGroup`): in-process concurrency. Correct for 5-20 concurrent LLM calls. No operational overhead.

**v2+ — Ray**: the right substrate when distribution across machines becomes necessary. Ray actors map directly onto Stratum agents — both are persistent stateful entities with typed methods. Ray remote tasks map onto `delegate`. Ray's fault tolerance and restart semantics map onto `supervise`.

```python
# Stratum agent → Ray actor (conceptual mapping)
@ray.remote
class Researcher:
    async def search(self, query: str) -> SearchResult: ...
    async def synthesize(self, findings: list[SearchResult]) -> Report: ...
```

The gap: Ray actors don't know about `@infer`, contracts, or budget. Stratum wraps the Ray actor in its execution loop; typed contracts handle serialization at the boundary (JSON schemas are inherently wire-serializable).

Design the `agent` abstraction in v1 so it can be Ray-backed without requiring it. Ray is the upgrade path, not the starting point — operational complexity is real.

```stratum
// This works regardless of where classify() executes
flow process(docs: Document[]) -> Summary {
  parallel {
    let results = docs.map(doc => infer classify(doc))
  }
  return compute aggregate(results)
}
```

The runtime may distribute the `parallel` branches across workers automatically based on the deployment configuration. The language doesn't need to know.

---

## Coordination Patterns Reference

| Pattern | Construct | Use case |
|---|---|---|
| Parallel independent work | `parallel { }` | Multiple analyses on the same input |
| First valid result | `race { }` | Latency hedging, model failover |
| Majority vote | `quorum:` on `infer` | High-stakes classification, reducing non-determinism |
| Adversarial synthesis | `debate { }` | Risk assessment, complex decisions |
| Stateful multi-step agent | `agent` + `spawn` | Research, long-running tasks, accumulating context |
| Delegated background work | `delegate` | Fire-and-forget, queue processing |
| Fault-tolerant pool | `supervise` | Production workloads, reliability requirements |
| Scatter-gather | `parallel` + `compute aggregate()` | MapReduce-style batch processing |
| Pipeline | Sequential `flow` steps with `stream` | Streaming partial results downstream |

---

## `stream` — Streaming Results Between Agents

For long-running `infer` operations where partial results are useful before completion.

```stratum
infer generateReport(data: DataSet) -> stream<ReportSection> {
  // yields sections as they are generated
}

flow buildReport(data: DataSet) -> Report {
  let sections: ReportSection[] = []
  for section in stream generateReport(data) {
    compute validateSection(section)  // validate each section as it arrives
    sections.append(section)
    compute updateProgressUI(sections.length)
  }
  return compute assembleReport(sections)
}
```

`stream<T>` is a typed async iterator. Each yielded value is validated against the contract `T`. The consuming `flow` can process, validate, or forward each item before the full result is complete.

---

## Budget Propagation Across Agents

The parent flow's budget is an envelope shared across all child agents and parallel branches.

```stratum
flow orchestrate(task: Task) -> Result {
  budget: 10s, $0.05   // total envelope for this flow

  parallel {
    let a = infer analyze(task)    // draws from shared envelope
    let b = infer summarize(task)  // draws from shared envelope
  }
  // if a + b cost > $0.05, BudgetExceeded is raised
}
```

Spawned agents inherit a slice of the parent budget unless overridden:

```stratum
let worker = spawn Worker with { budget: $0.01 }  // hard cap for this agent
```

---

## Observability Across Distributed Execution

All agents in a flow share a **trace ID**. The distributed trace captures:

- The full agent tree (parent → children → grandchildren)
- Each `infer` call with its compiled prompt, input, output, retries
- Inter-agent context propagation
- Timing and cost per agent and per flow
- `parallel` branch concurrency timelines
- `quorum` vote distributions
- `debate` round history

This is the audit log for the entire distributed execution. It answers: what happened, which agent did it, in what order, at what cost, with what inputs and outputs.

---

## Design Decisions for Concurrency

Key decisions recorded here; full rationale in [`open-problems.md`](open-problems.md):

- **Shared mutable state**: git worktree model — outer bindings are read-only inside `parallel`, compiler-enforced. Agent instances are branch-scoped.
- **Partial failure**: `require: all | any | N | 0` is the structural floor. `validate: compute | infer` adds semantic quality checks.
- **Debate termination**: runtime computes `converged: bool`, synthesizer receives it explicitly, HITL pause on unresolvable disagreement.
- **Budget contention in parallel**: deferred to v2. Not acute at v1 scale.
- **Agent trust / string injection**: resolved via `opaque[T]` field modifier in v1. See `type-system.md`.
- **Python API forms**: `stratum.parallel(*coros, require=...)` returns tuple; `quorum`/`agree_on`/`threshold` as kwargs on `@infer`; `stratum.debate(agents, topic, rounds, synthesize)`. See `how-to-build.md`.
