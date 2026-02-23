# Dynamic Orchestration

## The Core Question

Different problems require different configurations: some need parallel independent analysis, some need adversarial debate, some need a single focused agent, some need recursive decomposition. Can the system decide this dynamically rather than having a developer hard-code the pattern?

Yes — but with a critical constraint:

> **The LLM's orchestration decision must produce a typed, contract-validated execution plan before anything executes. The LLM has autonomy within a formally bounded envelope.**

This preserves formal guarantees while enabling adaptive behavior.

---

## Two Levels of LLM Involvement

| Level | Construct | What LLM does |
|---|---|---|
| **Object** | `infer` | Executes a task, returns a typed result |
| **Meta** | `orchestrate` | Decides *how* to execute, produces a typed plan |

The meta level is new. The plan it produces is itself a contract — validated before execution. The runtime executes the plan, not the LLM.

```
problem arrives
    │
    ▼
[orchestrate] ── LLM reasons about the problem ──► ExecutionPlan (typed, validated)
                                                         │
                                                         ▼
                                               [runtime executes plan]
                                               ├── spawn agents
                                               ├── apply coordination pattern
                                               ├── collect typed results
                                               └── return to caller
```

---

## `orchestrate` — Meta-Level Planning

```stratum
orchestrate solve(problem: Problem) -> Solution {
  budget: $1.00, 60s
  max_agents: 8
  max_depth: 3                          // max sub-orchestration levels
  available: [Researcher, Analyst, Critic, Synthesizer]
  patterns: [parallel, debate, quorum, sequential]
}
```

The LLM receives:
- The problem (typed input)
- The available agent types and their declared capabilities
- The available coordination patterns
- The hard constraints (budget, agent count, depth)
- The required output contract (`Solution`)

It produces an `ExecutionPlan` — a typed DAG of steps. The runtime validates the plan against the declared constraints before executing a single step.

If the plan violates constraints (requests 12 agents when `max_agents: 8`, uses a pattern not in `patterns`, exceeds budget estimates), the runtime rejects it and retries with the violation as structured feedback — exactly like `ensure` on a regular `infer`.

---

## The `ExecutionPlan` Contract

The orchestrator's output is itself a typed contract:

```stratum
contract AgentSpec {
  type: string                           // must match a declared available agent
  role: string                           // specialization context for this instance
  inputs: Map<string, any>
}

contract Step {
  id: string
  agent: AgentSpec
  depends_on: string[]                   // DAG edges (other step IDs)
  coordination: "sequential" | "parallel" | "debate" | "quorum" | "race"
  quorum_threshold: int?
  debate_rounds: int?
}

contract ExecutionPlan {
  steps: Step[]
  rationale: string                      // why this plan for this problem
  estimated_cost: float
  estimated_duration_ms: int
}
```

This is inspectable before execution. You can print the plan, review it, even require human approval for high-stakes orchestrations.

---

## `adapt` — Reactive Re-Planning

`orchestrate` plans upfront. `adapt` allows the plan to change based on intermediate results.

```stratum
adapt solve(problem: Problem) -> Solution {
  budget: $2.00, 120s
  max_replans: 3
  available: [Researcher, Analyst, Critic, Synthesizer]

  reflect: infer assessProgress(results_so_far, original_problem) -> Assessment {
    ensure: result.should_continue or result.has_conclusion
  }
}
```

Execution loop:
1. LLM produces initial `ExecutionPlan`
2. Runtime executes phase 1 of the plan
3. `reflect` is called with results so far — a `compute`-or-`infer` that evaluates progress
4. If `reflect` returns `should_continue: true`, LLM produces an updated plan for the next phase
5. Repeat until `reflect` returns `has_conclusion: true` or `max_replans` is exhausted

The `reflect` function is the formal convergence signal — the LLM doesn't decide when it's done, the reflect contract does. Same principle as `refine`.

Key constraint: each re-plan draws from the same total budget envelope. The orchestrator can see how much budget remains before planning the next phase.

---

## `reflect` — Self-Monitoring Hook

A `reflect` block can be attached to any `flow` or `orchestrate` to give the system a formal self-evaluation point:

```stratum
flow analyze(corpus: Document[]) -> Analysis {
  budget: $0.50

  reflect after_each_step: infer evaluateApproach(
    step_results: StepResult[],
    remaining_budget: Budget,
    original_goal: string
  ) -> ReflectionDecision {
    ensure: result.action in ["continue", "replan", "abort", "conclude"]
  }

  // ... rest of flow
}
```

`reflect` decisions:
- `continue` — proceed with current plan
- `replan` — trigger re-orchestration with current results as context
- `abort` — raise `OrchestrationFailed` with explanation
- `conclude` — current results are sufficient, return early

`reflect` is the language's answer to "what if the approach is wrong?" — rather than running to completion and failing, the system can course-correct mid-execution.

---

## What the LLM Can Decide Dynamically

Within declared constraints, the orchestrator LLM can choose:

| Decision | Example |
|---|---|
| Decomposition strategy | Split problem into 3 sub-problems vs. treat as whole |
| Number of agents | Spawn 2 analysts vs. 5 depending on corpus size |
| Coordination pattern | Use `debate` for ambiguous problem, `parallel` for independent facets |
| Agent specialization | Give each Analyst a different domain focus |
| Step dependencies | Which steps can run in parallel vs. must be sequential |
| Iteration depth | Whether a sub-problem needs its own sub-orchestration |
| Early termination | Whether intermediate results are already sufficient |

---

## What Remains Formally Fixed

The LLM cannot dynamically change:

| Constraint | Why |
|---|---|
| Hard budget cap | Prevents runaway cost |
| Available agent types | Can't spawn agents not declared |
| Max agent count | Prevents combinatorial explosion |
| Max orchestration depth | Prevents infinite recursion |
| Output contract | The final result type is always fixed |
| Plan validation | Runtime always validates before executing |
| `reflect` termination logic | LLM doesn't decide when it's done — the contract does |

---

## Problem-to-Pattern Recognition

The orchestrator LLM naturally learns to recognize when to apply each pattern. Roughly:

| Problem characteristic | Likely pattern |
|---|---|
| Independent sub-questions | `parallel` decomposition |
| Genuine ambiguity / multiple valid answers | `debate` with synthesis |
| High-stakes / low tolerance for error | `quorum` consensus |
| Unknown complexity / open-ended research | `adapt` with `reflect` |
| Simple, well-defined task | Single `infer`, no orchestration |
| Latency-sensitive with fallback options | `race` |
| Recursive structure | Sub-`orchestrate` with `max_depth` guard |

The developer doesn't hard-code which pattern to use — they declare the constraints and available tools, and the orchestrator chooses. The `rationale` field in `ExecutionPlan` exposes the reasoning.

---

## Capability Declaration

For the orchestrator to make good decisions, agent types must declare their capabilities formally:

```stratum
agent Researcher {
  model: "claude-opus-4-6"
  memory: session
  capability: "Deep research, synthesis of multiple sources, fact verification"
  best_for: ["open-ended investigation", "unknown territory", "multi-source synthesis"]
  cost_profile: high
  latency_profile: high

  infer search(query: string) -> SearchResult { ... }
  infer synthesize(findings: SearchResult[]) -> Report { ... }
}

agent Analyst {
  model: "claude-sonnet-4-6"
  capability: "Structured analysis of provided data, pattern recognition"
  best_for: ["structured data", "known frameworks", "comparative analysis"]
  cost_profile: medium
  latency_profile: medium

  infer analyze(data: any, framework: string) -> AnalysisResult { ... }
}
```

`capability`, `best_for`, and `cost_profile` are injected into the orchestrator's prompt. The orchestrator uses these to select and configure agents. This is the language's equivalent of a tool registry — but typed and formally bounded.

---

## Full Example: Dynamic Research System

```stratum
agent Researcher { ... }
agent Analyst { ... }
agent Critic { ... }
agent Synthesizer { ... }

contract ResearchReport {
  findings: string[]
  confidence: float[0.0..1.0]
  dissenting_views: string[]
  recommendation: string
}

orchestrate research(question: string) -> ResearchReport {
  budget: $2.00, 180s
  max_agents: 6
  max_depth: 2
  available: [Researcher, Analyst, Critic, Synthesizer]
  patterns: [parallel, debate, sequential]

  reflect after_each_step: infer checkSufficiency(
    results: StepResult[],
    question: string
  ) -> { sufficient: bool, gaps: string[] }
}
```

For a simple factual question, the orchestrator might produce:
```json
{
  "steps": [
    { "id": "1", "agent": { "type": "Researcher" }, "coordination": "sequential" },
    { "id": "2", "agent": { "type": "Synthesizer" }, "depends_on": ["1"], "coordination": "sequential" }
  ],
  "rationale": "Simple factual question. Single research pass followed by synthesis is sufficient."
}
```

For a contested policy question, the same `orchestrate` call might produce:
```json
{
  "steps": [
    { "id": "1a", "agent": { "type": "Researcher", "role": "Find supporting evidence" }, "coordination": "parallel" },
    { "id": "1b", "agent": { "type": "Researcher", "role": "Find opposing evidence" }, "coordination": "parallel" },
    { "id": "2", "coordination": "debate", "debate_rounds": 2, "depends_on": ["1a", "1b"],
      "agents": [{ "type": "Analyst", "role": "Pro" }, { "type": "Critic", "role": "Con" }] },
    { "id": "3", "agent": { "type": "Synthesizer" }, "depends_on": ["2"], "coordination": "sequential" }
  ],
  "rationale": "Contested topic with genuine expert disagreement. Parallel research followed by structured debate surfaces trade-offs better than single-pass analysis."
}
```

Same function signature. Radically different execution. The LLM matched the pattern to the problem.

---

## Open Problems

1. **Plan quality guarantees** — how do you know the orchestrator chose a *good* plan, not just a *valid* one? The plan is structurally valid (passes contract validation) but may be strategically poor. No formal mechanism for this yet.

2. **Orchestrator self-reference** — can an `orchestrate` block spawn another `orchestrate` block? `max_depth` prevents infinite recursion, but the interaction between nested orchestrators and shared budgets needs careful design.

3. **Plan observability** — the `rationale` field exposes reasoning, but when a plan fails you need to understand *why the orchestrator chose that plan*, not just what the plan was. This requires tracing the orchestrator's own inference, not just the plan execution.

4. **Capability drift** — `best_for` annotations are written by developers and may not match actual agent performance in production. There's no mechanism for the runtime to learn that `Researcher` is actually poor at "multi-source synthesis" and update the capability declaration accordingly. This is the self-improving system problem.

5. **The meta-orchestrator problem** — who orchestrates the orchestrator? If `adapt` can re-plan, and `reflect` can trigger re-planning, at some point you need a termination guarantee that's independent of LLM judgment. `max_replans` and `budget` provide this, but the interaction between them and `reflect` logic needs formal specification.
