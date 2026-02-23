# Stratum

[![Specification](https://img.shields.io/badge/Specification-SPEC.md-blue)](https://github.com/regression-io/stratum/blob/main/SPEC.md)
[![PyPI](https://img.shields.io/badge/PyPI-stratum-orange)](https://pypi.org/project/stratum/)

**Stop babysitting your LLM calls.**

Stratum is a Python library where `@infer` (LLM calls) and `@compute` (normal functions) compose identically. Typed contracts flow between steps. The runtime handles retry, budget enforcement, and observability — so you don't have to wire them up yourself.

```python
@contract
class SentimentResult(BaseModel):
    label: Literal["positive", "negative", "neutral"]
    confidence: float
    reasoning: str

@infer(
    intent="Classify the emotional tone of customer feedback",
    ensure=lambda r: r.confidence > 0.7,
    budget=Budget(ms=500, usd=0.001),
    retries=3,
)
def classify_sentiment(text: str) -> SentimentResult: ...
```

If the LLM returns low confidence, it gets told exactly what failed and retries with that context — not a blank replay. If it hits the budget, it stops. Every call produces a structured trace record you can query.

---

## Two Tracks

**Track 1 — Python library** (`stratum`): `@infer`, `@contract`, `@flow` decorators for building production LLM systems. Requires Python 3.11+, `litellm`, `pydantic`.

**Track 2 — Claude Code MCP server** (`stratum-mcp`): Stratum as an execution runtime for Claude Code. Claude writes `.stratum.yaml` specs, the MCP server enforces typed contracts and postconditions, Claude narrates progress in plain English. No sub-LLM calls — all execution stays within the Claude Code session.

---

## Track 2: Claude Code + Stratum

```bash
pip install stratum-mcp
stratum-mcp setup
```

`setup` configures Claude Code in one command: writes `.claude/mcp.json`, appends the execution model block to `CLAUDE.md`, and installs seven skills to `~/.claude/skills/`. Restart Claude Code and it's active.

**Seven skills installed automatically:**

| Skill | What it structures |
|---|---|
| `/stratum-review` | Three-pass code review: security → logic → performance → consolidate |
| `/stratum-feature` | Feature build: read existing patterns → design → implement → tests pass |
| `/stratum-debug` | Debug: read test → read code → check env → form hypotheses → confirm/rule out → fix |
| `/stratum-refactor` | File split: analyze → design modules → plan extraction order → extract one at a time |
| `/stratum-migrate` | Find bare LLM calls and rewrite as `@infer` + `@contract` with typed contracts and postconditions |
| `/stratum-test` | Write a test suite for existing untested code — golden flows, error-path harness, passing on first report |
| `/stratum-learn` | Review recent session transcripts — extract retry patterns, write project-specific conclusions to `MEMORY.md` |

Claude writes the `.stratum.yaml` spec internally — you never see it. You see plain English narration and the result. The MCP server enforces postconditions on every step; if a step's output fails a check, Claude fixes it and retries before reporting success.

Each skill reads project-specific patterns from `MEMORY.md` before writing its spec, and writes new patterns after `stratum_audit` — retry reasons, confirmed root causes, extraction order constraints. Run `/stratum-learn` periodically to extract conclusions from recent session transcripts and feed them back into future specs.

**MCP tools exposed:**

| Tool | What it does |
|---|---|
| `stratum_validate` | Validate a `.stratum.yaml` spec offline |
| `stratum_plan` | Validate + create execution state + return first step |
| `stratum_step_done` | Report a completed step; check postconditions; return next step or completion |
| `stratum_audit` | Return per-step trace (attempts, duration) for any flow |

---

## Blog

**[Introducing Stratum: LLM Calls That Behave Like the Rest of Your Code](https://github.com/regression-io/stratum/blob/main/blog/introducing-stratum.md)**
The design rationale — why `@infer` and `@compute` share a type, how structured retry works, and what contracts actually buy you.

**[Stratum as a Claude Code Execution Runtime](https://github.com/regression-io/stratum/blob/main/blog/stratum-in-claude-code.md)**
Claude Code is a capable agent improvising in a loop. This post is about giving it a formal execution model — typed plans, postcondition enforcement, auditable traces.

**[Building Software with Claude Code + Stratum: A Tutorial](https://github.com/regression-io/stratum/blob/main/blog/claude-code-tutorial.md)**
Real session transcripts: understanding a codebase, reviewing code, adding features, debugging CI failures, refactoring large files. Claude narrates in plain English throughout.

---

## Why

LLM calls in production share a few recurring failure modes:

- **Retry is brute force.** Most frameworks replay the full prompt on failure. Stratum injects only the specific postcondition that failed.
- **Budget is an afterthought.** Soft hints don't stop a runaway `refine` loop. Stratum enforces hard limits — `BudgetExceeded` is an exception, not a bill.
- **Flows are opaque.** When a multi-step pipeline fails, you want to know which step, with what input, after how many retries, at what cost. Stratum traces every call structurally.
- **LLM steps and regular functions don't compose.** Stratum makes `@infer` and `@compute` indistinguishable by type — swap one for the other and nothing downstream changes.
- **Agent outputs can hijack downstream agents.** `opaque[T]` fields are passed as structured data, never inlined into instruction text.
- **Human-in-the-loop is a custom build every time.** `await_human` genuinely suspends execution and returns a typed `HumanDecision[T]`.

---

## Core Concepts

### `@infer` and `@compute` are the same type

```python
# Phase 1: LLM classifies tickets
@infer(intent="Route this support ticket", model="groq/llama-3.3-70b-versatile")
def route_ticket(text: str) -> TicketRoute: ...

# Phase 2: patterns emerged — swap to rules, zero other changes
@compute
async def route_ticket(text: str) -> TicketRoute:
    return TicketRoute(team=keyword_match(text), ...)
```

These have identical signatures. The `@flow` that calls `route_ticket` doesn't change. This means:

- **Testing:** Replace `@infer` calls with `@compute` stubs for deterministic tests.
- **Migration:** Start with LLM, replace with rules as patterns emerge. No downstream changes.
- **Cost control:** Swap expensive inference for fast lookup when coverage allows.

### Contracts are typed boundaries

```python
@contract
class SentimentResult(BaseModel):
    label: Literal["positive", "negative", "neutral"]
    confidence: Annotated[float, Field(ge=0.0, le=1.0)]
    reasoning: str
```

A `@contract` class compiles to JSON Schema injected into the structured outputs API. The LLM's output is validated against it before your code sees it. Every contract carries a content hash — a hash change means the compiled prompt changed and LLM behavior may have drifted.

### Retry is structured

On failure the LLM receives:

```
Previous attempt failed:
  - ensure condition 1 failed
Fix these issues specifically.
```

Not a full prompt replay. The specific violation, nothing else.

### Flows are deterministic

```python
@flow(budget=Budget(ms=5000, usd=0.01))
async def process_ticket(text: str) -> Resolution:
    sentiment = await classify_sentiment(text=text)
    response  = await draft_response(text=text, sentiment=sentiment)
    return response if rule_check(response) else escalate(text)
```

`@flow` is normal Python control flow. You can read it, test it, and trace it. The orchestration shape is known before any LLM call runs.

---

## Features

| Feature | Description |
|---|---|
| Structured retry | `ensure` postconditions drive retry with targeted failure feedback |
| Hard budget limits | Per-call and per-flow — `BudgetExceeded`, not a soft hint |
| `opaque[T]` | Field-level prompt injection protection |
| `await_human` | HITL as a first-class typed primitive — genuine suspension |
| `stratum.parallel` | Concurrent execution with `require: all/any/N/0` semantics |
| `quorum` | Run N times, require majority agreement |
| `stratum.debate` | Adversarial multi-agent synthesis with convergence detection |
| Full observability | Structured trace record on every call, OTLP export built-in |
| Two dependencies | `litellm` + `pydantic`. No OTel SDK. |

---

## Examples

Working examples in [`examples/`](https://github.com/regression-io/stratum/tree/main/examples):

| File | What it shows |
|---|---|
| [`01_sentiment.py`](https://github.com/regression-io/stratum/blob/main/examples/01_sentiment.py) | `@infer` + `@contract` + `@flow` + `@compute` end-to-end |
| [`02_migrate.py`](https://github.com/regression-io/stratum/blob/main/examples/02_migrate.py) | Migrating `@infer` → `@compute` without changing callers |
| [`03_parallel.py`](https://github.com/regression-io/stratum/blob/main/examples/03_parallel.py) | Three concurrent `@infer` calls with `parallel(require="all")` |
| [`04_refine.py`](https://github.com/regression-io/stratum/blob/main/examples/04_refine.py) | `@refine` convergence loop — iterates until quality passes |
| [`05_debate.py`](https://github.com/regression-io/stratum/blob/main/examples/05_debate.py) | `debate()` — two agents argue, synthesizer resolves |
| [`06_hitl.py`](https://github.com/regression-io/stratum/blob/main/examples/06_hitl.py) | `await_human` — human-in-the-loop approval gate |

---

## Install

**Track 1 — Python library:**
```bash
pip install stratum-py
```
Requires Python 3.11+. Set `GROQ_API_KEY`, `ANTHROPIC_API_KEY`, or any key LiteLLM supports, then specify it in `model=`.

**Track 2 — Claude Code MCP server:**
```bash
pip install stratum-mcp
stratum-mcp setup
```
Requires Claude Code. `setup` configures everything — restart Claude Code to activate.

---

## Specification

[`SPEC.md`](https://github.com/regression-io/stratum/blob/main/SPEC.md) is the normative specification covering the full type system, decorator signatures, execution loop, prompt compiler, concurrency semantics, HITL protocol, budget rules, trace record schema, and error types.

---

## Status

**Track 1** (Python library): implemented and tested.

**Track 2** (stratum-mcp): MCP controller server implemented — `stratum_plan`, `stratum_step_done`, `stratum_audit`, `stratum_validate`. One-command setup with seven bundled skills and a memory system for project-specific pattern capture. 66 tests passing.

Questions and feedback: [GitHub Discussions](https://github.com/regression-io/stratum/discussions)

---

## License

[Apache 2.0](https://github.com/regression-io/stratum/blob/main/LICENSE)
