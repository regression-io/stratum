# Prior Art

Where the gap is, and what exists today.

---

## The Gap

No existing system treats formal contracts, natural language intent, and LLM inference as **co-equal first-class citizens in a single unified execution model** with static analysis of inter-step type compatibility.

Most existing tools fall into one of four categories:
1. **Code that calls LLMs** — LLM is a library call, not a language-level concept (LangChain, LlamaIndex)
2. **Typed LLM wrappers** — function signatures as contracts, but no flow orchestration (instructor, Marvin, DSPy)
3. **Constrained generation** — LLM output is shaped, but no program structure (LMQL, Guidance, Outlines)
4. **Visual workflow tools** — orchestration without types or semantic contracts (n8n, Zapier)

---

## Systems Compared

### instructor (Python)

**What it gets right:** The closest thing to `@infer` that exists. Pydantic models as output contracts. Structured outputs API for schema enforcement at the token level. `max_retries` with validation error feedback sent back to the LLM. Wide model support. Production-ready and widely adopted.

**Where it's close to Stratum:** For a single typed LLM call with validation and retry, instructor covers ~80% of what `@infer` delivers. This is a strong competitor on its home turf.

**What's missing:**
- No `flow` — no typed composition of multiple calls, no inter-step type verification
- No `compute` vs `infer` distinction — runtime doesn't know what's deterministic
- No static analysis — type mismatches discovered at runtime, not write time
- No `orchestrate` — structure is always fixed
- No `parallel` with partial failure semantics
- No hard budget enforcement
- Retry sends the validation error but doesn't inject structured failure feedback at the semantic level

**Verdict:** The natural predecessor to Stratum's `@infer`. The adoption path runs: instructor for single calls → Stratum when flows get complex enough to need static guarantees. Not a replacement — a graduation.

---

### DSPy (Stanford)

**What it gets right:** The most sophisticated existing approach to typed LLM programs. Signatures as typed contracts. Composable modules that feel like `@flow`. `dspy.Assert`/`dspy.Suggest` as rough postconditions. For a basic linear flow, DSPy covers ~60% of Stratum's value.

**Where DSPy is genuinely ahead:** Prompt optimization. DSPy can automatically tune prompt programs against a metric — it learns better prompts from examples and labeled data. This capability doesn't exist in Stratum's design. For teams with stable task definitions and evaluation sets, this is a real DSPy advantage.

**What's missing:**
- No static inter-step type checking — modules compose but output/input compatibility isn't verified before running
- No `compute` vs `infer` semantic distinction — everything is a module
- No `orchestrate` with typed plan validation
- No `parallel` with partial failure semantics
- No hard budget enforcement
- No language-agnostic IR
- `dspy.Assert` is weaker than `ensure` — triggers retry but without structured failure injection

**The composable substrate insight:** DSPy and Stratum solve adjacent layers. DSPy optimizes *what to say* to the LLM. Stratum enforces *what the LLM must produce and what happens when it doesn't*. These compose:

- v1: Stratum's `compile_prompt()` assembles intent + context + inputs deterministically
- v2: `compile_prompt()` is DSPy-backed — a DSPy-optimized program tuned against real examples, with `ensure`, retry, budget, and trace still owned by Stratum

The `@infer` decorator's `context:` becomes optionally DSPy-backed. Same interface, learned internals. DSPy is the right substrate for teams with labeled data who want optimized prompts inside Stratum's contract envelope.

**Verdict:** The right comparison for ML practitioners and a v2 integration target, not just a competitor. DSPy users who hit the limits of `dspy.Assert` and need stronger inter-step type guarantees are warm Stratum adopters. DSPy users who want to keep prompt optimization can bring it with them.

---

### Marvin (Prefect)

**What it gets right:** `@ai_fn` decorator turns Python function signatures into LLM calls. Simple, pragmatic, low friction. The direct conceptual ancestor of `@infer`.

**What's missing:** No `ensure` postconditions. No structured retry with failure feedback. Python type annotations don't compile to prompt-level schemas. No flow orchestration. No static analysis.

**Verdict:** `@infer` is Marvin with a formal type system, `ensure`, and execution guarantees.

---

### n8n

**What it gets right:** Visual workflow builder. 400+ integrations. Non-developers can build LLM workflows without code. Fast time-to-first-working-thing. Observable in a UI stakeholders can understand.

**The "good enough" dynamic:** n8n captures teams early with low friction and the stickiness is real. A workflow that's 80% reliable gets patched rather than replaced. The ceiling gets tolerated because switching cost is real even when the workflow is frustrating to maintain.

**The ceiling:** When LLM output needs to feed directly into another system without human review, when untyped JSON propagation causes cascading failures across steps, when volume is high enough that silent quality degradation has dollar cost, when the team wants to test programmatically — n8n can't get there. There are no typed inter-node contracts, no semantic postconditions, no structured retry, no budget caps.

**The migration path opportunity:** n8n users who hit the ceiling are warm Stratum adopters. They know what the workflow should do. They've seen it work unreliably. A tool that imports an n8n workflow, generates `.stratum` IR, and flags every untyped inter-node boundary as a typed contract gap is the conversion product.

**Verdict:** Different audience from Stratum's primary target (developers building production-grade LLM systems). The overlap is developers who reached for n8n for speed and hit the reliability ceiling. Complementary tool for getting started; Stratum is the graduation path.

---

### LangChain / LlamaIndex

**What it gets right:** Composable pipeline abstractions. Rich integration ecosystem. Large communities.

**What's missing:** LLM calls are library calls with no type safety. Orchestration logic is entangled with invocation. No `ensure` semantics. No formal contracts. "Chain" is a metaphor, not a typed construct. These are the frameworks developers are already trying to escape when they reach for instructor or DSPy.

**Verdict:** The thing developers used before instructor. Not the primary competitive comparison — they're already being superseded in their own ecosystem.

---

### LMQL (ETH Zurich)

**What it gets right:** Constrained generation — LLM output shaped by query structure. SQL-like syntax for LLM queries. Strong academic foundation.

**What's missing:** Not general-purpose. No `compute`/`infer` composability. No flow orchestration. Constraints apply to generation mechanics, not to semantic content or inter-step types.

**Verdict:** Solves a narrow, well-defined problem (structured text generation) well. Not a competitor at the system orchestration level.

---

### Guidance (Microsoft)

**What it gets right:** Interleaves template structure with generation, forcing conformance to patterns. Low token waste for structured outputs.

**What's missing:** Prompt-centric, not contract-centric. No typed return values. No composability with deterministic code. Generation constraints, not semantic postconditions.

**Verdict:** A better prompt template engine. Not a language.

---

### Outlines

**What it gets right:** Constrained decoding at the token level — physically forces LLM output to conform to a schema. Zero prompt tokens for structural invariants.

**What's missing:** Constraint is at the decoding level, not the semantic level. No postconditions. No orchestration. No flow. The right primitive, not the right system.

**Verdict:** The right constrained decoding backend for self-hosted deployments. Integration path: LiteLLM → vLLM → Outlines. For API-based models (Anthropic, OpenAI), the structured outputs API handles schema enforcement instead — Outlines requires logit access. Not a v1 concern; document as the recommended upgrade path for teams moving to self-hosted inference.

---

### Temporal (Temporal.io)

**What it gets right:** Durable workflow execution. Activities and workflows as distinct concepts. Replay, fault tolerance, exactly-once semantics. The right mental model for deterministic orchestration.

**What's missing:** No LLM-native constructs. Activities are just async functions. No intent layer, no contracts, no typed LLM output.

**The integration design:** Temporal and Stratum are different layers — they don't overlap, they compose.

- Temporal handles: durability, resume-on-crash, exactly-once, long timeouts, infrastructure retry
- Stratum handles: contract validation, `ensure` postconditions, semantic retry on LLM failure, budget, trace

```python
# Temporal activity wrapping a Stratum @infer call
@activity.defn
async def classify_sentiment_activity(text: str) -> dict:
    result = await classify_sentiment(text)  # Stratum @infer — semantic retry here
    return result.model_dump()

# Temporal workflow — durability envelope around Stratum activities
@workflow.defn
class ProcessTicketWorkflow:
    @workflow.run
    async def run(self, ticket: dict) -> dict:
        sentiment = await workflow.execute_activity(
            classify_sentiment_activity,
            ticket["body"],
            schedule_to_close_timeout=timedelta(seconds=30)
        )
        ...
```

`@flow` in v1 is designed to not preclude Temporal wrapping — contracts are JSON-serializable by construction, so flow state crosses the Temporal activity boundary without manual serialization.

**Verdict:** Phase 3 enterprise integration. Trigger: flows longer than minutes, or where partial execution is expensive. Not a v1 concern — Temporal adds significant operational overhead (server, worker processes, versioning). Build when the pain is observed.

---

### Dafny (Microsoft Research)

**What it gets right:** Executable pre/postconditions. Formal proofs of program correctness. The right formal apparatus.

**What's missing:** No LLM execution mode. Purely deterministic. The formal apparatus exists; the hybrid execution model doesn't.

**Verdict:** Stratum's `given`/`ensure` semantics are inspired by Dafny. Not a competitor — a source.

---

### SQL as an Unexpected Benchmark

SQL is arguably the most LLM-legible language that exists for its domain:
- Clause-based, self-delimiting
- English keywords (`SELECT`, `FROM`, `WHERE`, `GROUP BY`)
- Declarative — express *what*, not *how*
- LLMs generate SQL remarkably well compared to general code

Stratum's keyword-delimiter syntax is partially inspired by SQL's clause structure: structure through named clauses rather than bracket nesting.

---

## Competitive Summary

| Tool | Typed outputs | Ensure/retry | Flow typing | Parallel | Orchestrate | Budget | IR |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| instructor | ✓ | partial | ✗ | ✗ | ✗ | ✗ | ✗ |
| DSPy | ✓ | partial | partial | ✗ | ✗ | ✗ | ✗ |
| Marvin | ✓ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ |
| LangChain | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ |
| n8n | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ |
| Temporal | n/a | n/a | ✓ | ✓ | ✗ | ✗ | ✗ |
| Outlines | ✓ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ |
| **Stratum** | **✓** | **✓** | **✓** | **✓** | **✓** | **✓** | **✓** |

**DSPy advantage not in table:** prompt optimization. Stratum has no equivalent. Real advantage for teams with labeled data and stable task definitions.

---

## What Must Be Built New

There is no existing system that provides all of:

1. `infer` as a first-class construct composing identically with `compute`
2. Contracts that are simultaneously type definitions, constrained decoding grammars, and runtime validators — one artifact, not three
3. `ensure` postconditions that drive structured retry with injected failure context, statically verified against the declared return type
4. `flow` as a deterministic typed orchestration layer with static inter-step type checking
5. `orchestrate` — dynamic structure with typed plan validation before execution, closed available-agent set
6. `parallel` with `require:` + `validate:` partial failure semantics
7. Hard budget enforcement as a runtime constraint, not a soft hint
8. `.stratum` IR as a language-agnostic interchange format between authoring surfaces and execution backends

The v1 Python library approximates items 1–4 via decorators without full static analysis. Items 5–8 require the runtime to be stable before they're worth building. The full compiler (static analysis, prompt compiler, constrained decoding grammar generation) is the v3 thesis — if the runtime proves the value, the compiler makes it categorical.
