# Patterns Library

## Design Principle

Multi-agent patterns are a **library layer over primitives**, not language constructs. The language provides `infer`, `compute`, `flow`, `refine`, `parallel`, `race`, `quorum`, `debate`, `agent`, `spawn`, `supervise`. Patterns are reusable compositions of these primitives.

This keeps the language minimal. Patterns can evolve, be versioned, and be contributed by the community without touching the core. Domain-specific pattern libraries (code review patterns, legal reasoning patterns, medical triage patterns) can be built and distributed independently.

The one exception: `debate` earned a first-class language construct because its termination semantics — rounds, convergence detection, full history to synthesizer — are genuinely awkward to compose correctly from primitives and appear frequently enough to justify it. Everything else is library territory.

---

## Why Primitives Are Sufficient

The key insight: multi-agent feedback routing is just typed function calls. Actor-critic looks complex but is a loop with two agents and typed inter-call data:

```python
@flow
def actor_critic(task: Task, max_rounds: int = 5) -> Solution:
    actor = spawn(Actor)
    critic = spawn(Critic)
    proposal = actor.generate(task)
    for _ in range(max_rounds):
        evaluation = critic.evaluate(proposal)   # critic output is typed EvaluationResult
        if evaluation.approved:
            return proposal
        proposal = actor.refine(task, proposal, evaluation.critique)  # critique flows back typed
    raise MaxRoundsExceeded(f"No approved proposal after {max_rounds} rounds")
```

No new language construct. The feedback routing is `evaluation.critique` — a typed field on a typed return value, passed as input to the next actor call. The loop termination is `evaluation.approved` — a typed postcondition. The language already has everything needed.

---

## Core Patterns

### `actor_critic`

Generator produces a proposal. Evaluator critiques it. Generator refines. Loop until approved or max rounds.

```python
from stratum.patterns import actor_critic

@contract
class Proposal(BaseModel):
    solution: str
    reasoning: str

@contract
class Evaluation(BaseModel):
    approved: bool
    critique: str
    specific_issues: list[str]

@agent(context="Generate solutions to the given task. Be creative but practical.")
class Actor:
    @infer(intent="Generate a solution proposal", ensure=lambda r: len(r.solution) > 0)
    def generate(self, task: Task) -> Proposal: ...

    @infer(intent="Refine the proposal based on critique")
    def refine(self, task: Task, proposal: Proposal, critique: str) -> Proposal: ...

@agent(context="Evaluate proposals critically. Approve only if correct and safe.")
class Critic:
    @infer(intent="Evaluate this proposal against the task requirements")
    def evaluate(self, proposal: Proposal) -> Evaluation: ...

result = actor_critic(Actor, Critic, task, max_rounds=5)
```

**When to use:** iterative refinement where an external evaluator is more reliable than self-critique. Code generation + test runner as critic. Writing + style guide evaluator.

---

### `constitutional`

Generator produces output. Evaluator checks it against a fixed rubric or constitution. Generator revises. The critic is stateless — same rubric every time.

```python
from stratum.patterns import constitutional

RUBRIC = """
Evaluate the response against these principles:
1. Factually accurate — no unsupported claims
2. Balanced — presents multiple perspectives where relevant
3. Safe — no harmful content
"""

result = constitutional(
    generator=AnalystAgent,
    rubric=RUBRIC,
    task=task,
    max_rounds=3
)
```

Structurally identical to actor-critic but the critic is a single `@infer` call with the rubric injected as context, not a stateful agent.

---

### `ensemble`

Run the same task across N agents with different prompts, models, or temperatures. Aggregate results by voting, averaging, or synthesis.

```python
from stratum.patterns import ensemble

result = ensemble(
    agents=[
        FastAnalyst(model="claude-haiku-4-5"),
        DeepAnalyst(model="claude-opus-4-6"),
        BalancedAnalyst(model="claude-sonnet-4-6"),
    ],
    task=task,
    aggregate="vote"      # or: "synthesize", "best_confidence", "merge"
)
```

Different from `quorum` (which runs the same agent N times). Ensemble agents are intentionally different — different expertise, different prompts, different models. The diversity is the point.

---

### `plan_and_execute`

Planner agent produces a typed step list. Executor agents run each step. Separation of concerns: the planner reasons about what to do, executors reason about how to do each step.

```python
from stratum.patterns import plan_and_execute

@contract
class Step(BaseModel):
    id: str
    description: str
    executor: Literal["researcher", "writer", "reviewer"]
    depends_on: list[str]

@contract
class Plan(BaseModel):
    steps: list[Step]
    rationale: str

result = plan_and_execute(
    planner=PlannerAgent,
    executors={"researcher": ResearchAgent, "writer": WriterAgent, "reviewer": ReviewAgent},
    task=task
)
```

The planner's output (`Plan`) is a typed contract. The pattern validates the plan before executing — checks that all `executor` values reference declared agents, that `depends_on` references form a valid DAG. Then executes each step in dependency order, routing to the right executor.

This is `orchestrate` with an explicit planner/executor split. Use this when you want the planner to be a specific agent with a specific prompt rather than the implicit LLM that runs `orchestrate`.

---

### `reflexion`

Agent attempts a task. Reflects on its output. Builds a typed memory of past failures and strategies. Applies accumulated memory to the next attempt.

```python
from stratum.patterns import reflexion

@contract
class Reflection(BaseModel):
    what_failed: str
    why_it_failed: str
    strategy_for_next: str

result = reflexion(
    agent=SolverAgent,
    task=task,
    max_attempts=4,
    memory_type=Reflection   # typed reflection accumulated across attempts
)
```

Different from `refine` (which injects the runtime's `ensure` violation) and actor-critic (which uses an external evaluator). Reflexion is the agent evaluating its own output and building an explicit memory of strategies. The memory is typed — each reflection is a `Reflection` contract, not free text.

---

### `multi_persona`

Run the same task through agents with different personas or expertise. Compare or synthesize results. Useful for getting diverse perspectives or reducing single-model bias.

```python
from stratum.patterns import multi_persona

result = multi_persona(
    personas={
        "optimist": "Focus on opportunities and positive outcomes.",
        "pessimist": "Focus on risks, failure modes, and what could go wrong.",
        "pragmatist": "Focus on practical constraints and implementation challenges.",
    },
    base_agent=AnalystAgent,
    task=task,
    synthesize=True    # or: return all perspectives separately
)
```

The pattern spawns one instance of `base_agent` per persona, injects the persona description as additional context, runs them in parallel, and optionally synthesizes.

---

## Building Custom Patterns

Any composition of primitives can be packaged as a pattern. The requirements:

1. **Typed inputs and outputs** — the pattern function accepts typed contracts, returns typed contracts
2. **Budget-aware** — the pattern accepts a `budget` parameter and propagates it to all internal `infer` calls
3. **Trace-preserving** — all internal executions produce trace records; the pattern surfaces them

```python
from stratum import flow, infer, spawn, Budget
from stratum.patterns import Pattern

class MyPattern(Pattern):
    @flow(budget=Budget(ms=30000, usd=0.10))
    def run(self, task: MyTask) -> MyResult:
        # compose primitives here
        ...
```

Patterns are just `@flow` functions with documented semantics. The library provides common ones. Domain-specific ones live in separate packages.

---

## What Belongs in the Language vs. the Library

| Construct | Level | Reason |
|---|---|---|
| `infer` | Language | Fundamental semantic distinction |
| `compute` | Language | Fundamental semantic distinction |
| `flow` | Language | Deterministic orchestration semantics |
| `refine` | Language | Convergence loop with `until:` semantics |
| `parallel` | Language | Concurrent execution with isolation model |
| `race` | Language | First-valid-result semantics |
| `quorum` | Language | Consensus with threshold semantics |
| `debate` | Language | Adversarial multi-agent with convergence — awkward from primitives |
| `adaptive` | Language | Runtime dispatch with shared contract and `ensure` semantics — requires runtime coordination |
| `agent` / `spawn` | Language | Stateful entity lifecycle |
| `actor_critic` | Library | Loop + two agents + typed feedback — clean from primitives |
| `constitutional` | Library | Stateless critic variant of actor-critic |
| `ensemble` | Library | Parallel + aggregation — clean from primitives |
| `plan_and_execute` | Library | `orchestrate` with explicit planner agent |
| `reflexion` | Library | Self-critique with typed memory |
| `multi_persona` | Library | Parallel + context injection |
