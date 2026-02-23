# Stratum

[![Specification](https://img.shields.io/badge/Specification-SPEC.md-blue)](https://github.com/regression-io/stratum-spec/blob/main/SPEC.md)

The language specification is at **[regression-io/stratum-spec → SPEC.md](https://github.com/regression-io/stratum-spec/blob/main/SPEC.md)**.

A hybrid language where formal structure and LLM inference are co-equal first-class citizens.

## Core Premise

The optimal combination of structured programming and LLM is not a split language — it's a single language where **formal contracts bound the space within which LLM inference operates**. The formal layer doesn't replace LLM reasoning. It constrains, validates, and retries it.

The primary value is **correctness and determinism**: typed inter-step contracts, machine-checked postconditions, structured retry on failure, and orchestration flows whose shape is known before any LLM call runs. Token efficiency is a real benefit that compounds at scale — it's a v2 optimization layer, not the adoption driver.

```
┌─────────────────────────────────────────┐
│            Formal Contract Layer        │  ← types, schemas, invariants, I/O
│  ┌─────────────────────────────────┐    │
│  │        Intent Layer             │    │  ← natural language goals
│  │  ┌───────────────────────┐      │    │
│  │  │   LLM Inference Zone  │      │    │  ← generation within the envelope
│  │  └───────────────────────┘      │    │
│  └─────────────────────────────────┘    │
└─────────────────────────────────────────┘
```

## What This Is Not

- Not a prompt templating system (Jinja, Handlebars)
- Not a framework for calling LLMs from code (LangChain, LlamaIndex)
- Not a constrained generation system (Guidance, LMQL)
- Not a purely formal language with LLM bolted on

## What This Is

A language where:

- `compute` blocks execute deterministically (compiled/interpreted as normal code)
- `infer` blocks execute via LLM inference, but produce **typed, contract-validated results**
- Both compose identically — callers are type-safe regardless of implementation mode
- Orchestration (`flow`) is always deterministic even when individual steps use LLM
- Pre/postconditions are executable and drive structured retry on failure
- Non-determinism is explicit in the type system: `stable=True` returns `T`; `stable=False` returns `Probabilistic[T]` and forces callers to handle variance
- Every contract carries a content hash in trace records — behavioral drift across deployments is detectable, not silent

## Authoring Surfaces

Developers don't write Stratum syntax directly. There are three ways in:

**1. Python library** — the primary authoring surface for professional developers:

```python
@contract
class SentimentResult(BaseModel):
    label: Literal["positive", "negative", "neutral"]
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str

@infer(
    intent="Classify the emotional tone of customer feedback",
    context="Sarcasm → negative. Ambiguous → neutral.",
    ensure=lambda r: r.confidence > 0.7,
    budget=Budget(ms=500, usd=0.001),
    retries=3
)
def classify_sentiment(text: str) -> SentimentResult: ...

@flow
def process_ticket(ticket: SupportTicket) -> Resolution:
    sentiment = classify_sentiment(ticket.body)
    response  = draft_response(ticket, sentiment)
    return response if rule_check(response) else escalate(ticket)
```

**2. Claude Code + MCP** — the surface for vibe coders:

The vibe coder never sees contracts, step types, or YAML. They see:

```
Claude: "I'll analyze the sentiment of each review, draft a response for
         negative ones, and flag anything below 70% confidence for your
         review. Estimated cost: ~$0.02. Proceed?"

User:   "yes"

Claude: "Done. 847 reviews processed, 134 flagged, $0.019, 2 retries
         (resolved automatically)."
```

The `.stratum` IR is generated, validated, and executed entirely behind the scenes. When the output is persistent code, Claude generates `@infer`-annotated Python using the stratum library — the vibe coder gets professionally structured LLM code without knowing what `@infer` means.

**The flywheel**: vibe coder gets better output → their codebase contains `@infer`-annotated code → professional developer inherits or reviews it → encounters the library → adopts it directly.

**3. TypeScript library** — same design. Zod for contracts, Anthropic TypeScript SDK for LLM calls. Vercel AI SDK is an integration target for Next.js users, not the substrate.

## The IR

The `.stratum.yaml` format is what the libraries and Claude emit — not what developers write. It's the interchange format between authoring surfaces and the runtime, the same way LLVM IR sits between source languages and machine code.

```yaml
# generated — not hand-authored
functions:
  classifySentiment:
    mode: infer
    intent: "Classify the emotional tone of customer feedback"
    input: { text: string }
    output: SentimentResult
    ensure: ["result.confidence > 0.7"]
    budget: { ms: 500, usd: 0.001 }
    retries: 3
```

## Conceptual Model

The semantic distinction that the IR captures — and that authoring surfaces make explicit:

```stratum
contract SentimentResult {
  label: "positive" | "negative" | "neutral"
  confidence: float[0.0..1.0]
  reasoning: string
}

infer classifySentiment(text: string) -> SentimentResult {
  ensure: result.confidence > 0.7
  context: "Sarcasm → negative. Ambiguous → neutral."
}

flow processDocuments(docs: Document[]) -> Report {
  parallel require: any, validate: compute sufficientCoverage(results) {
    let analyses = docs.map(doc => spawn Analyst.review(doc))
  }
  debate {
    agents: [infer ArgueFor(analyses), infer ArgueAgainst(analyses)]
    rounds: 2
    synthesize: infer synthesize(analyses, arguments, converged) -> Report
  }
}
```

When `converged: false` and the debate doesn't resolve, the flow escalates to a human rather than synthesizing a forced middle ground.

This notation describes the semantics. The Python and TypeScript libraries are how those semantics are authored in practice.

## Two Deployment Contexts

Stratum has two distinct deployment contexts with different users, constraints, and docs.

**Track 1 — Python library** (`pip install stratum`): a professional developer uses `@infer`, `@contract`, `@flow` directly in their code. No enforcement gap. No MCP. No Claude Code. The library always goes through the Stratum runtime because the developer opted in by using it.

**Track 2 — Claude Code integration**: an operator configures Claude Code to use Stratum as its execution runtime via an MCP server. Two distinct audiences:

- **Professional developers** — review typed execution plans, understand the step graph, tune contracts. The MCP enforces what the library would have enforced if they'd written the code themselves.
- **Vibe coders** — prompt Claude Code to build things. The IR is invisible. They see plain-language plans, approve them, and get reliable results (and, when the output is code, `@infer`-annotated Python they can keep).

The enforcement gap is real in Track 2 — Claude Code is an AI agent that can route around constraints. Different machinery required.

## Integrations

### Python v1 — one required dependency

| Dependency | Role |
|---|---|
| `litellm` | LLM client — multi-model routing, fallback, cost tracking |
| Python 3.11+ stdlib | Concurrency — `asyncio.TaskGroup`, `asyncio.timeout` |

Required: `pydantic>=2.0` (`@contract` requires `BaseModel`).

Trace export to any OTLP-compatible backend (Jaeger, Honeycomb, Datadog, Langfuse) via a built-in OTLP emitter — no OTel SDK dependency. Configure an endpoint and Stratum POSTs spans over HTTP/JSON.

### TypeScript v1

| Dependency | Role |
|---|---|
| `zod` | `@contract` schemas + TypeScript type inference |
| `@anthropic-ai/sdk` | LLM calls — direct, minimal, stable |

Multi-provider path: LiteLLM's OpenAI-compatible endpoint + `openai` TypeScript SDK.

### Phase 3 — enterprise integrations (build from observed pain)

| Integration | Trigger |
|---|---|
| **Temporal** | Flows longer than minutes, or partial execution is expensive |
| **Ray** | In-process asyncio concurrency hits real limits (100+ parallel branches) |
| **Outlines** | Teams moving to self-hosted inference (vLLM + Outlines via LiteLLM) |
| **DSPy** | Teams with labeled data who want learned prompts inside Stratum's contract envelope |

### Not substrates

| Tool | Relationship |
|---|---|
| instructor | Prior art — natural predecessor to `@infer`. Migration audience. |
| Vercel AI SDK | Integration target for Next.js users. Not the TypeScript substrate. |
| n8n | Migration path and acquisition channel. Different audience. |
| LangChain / LlamaIndex | What developers are trying to escape. Not a comparison point. |

---

## Examples

Working examples are in [`examples/`](examples/):

| File | What it shows |
|---|---|
| [`01_sentiment.py`](examples/01_sentiment.py) | `@infer` + `@contract` + `@flow` + `@compute` end-to-end |
| [`02_migrate.py`](examples/02_migrate.py) | Migrating an `@infer` step to `@compute` without changing callers |
| [`03_parallel.py`](examples/03_parallel.py) | Three concurrent `@infer` calls with `parallel(require="all")` |
| [`04_refine.py`](examples/04_refine.py) | `@refine` convergence loop — iterates until quality passes |
| [`05_debate.py`](examples/05_debate.py) | `debate()` — two agents argue, synthesizer resolves |
| [`06_hitl.py`](examples/06_hitl.py) | `await_human` — human-in-the-loop approval gate |

---

## Status

Track 1 (Python library) is implemented and tested. Docs reflect the implemented design.
