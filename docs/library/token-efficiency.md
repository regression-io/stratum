# Token Efficiency

## Priority

Token efficiency is a **v2 concern**. The v1 goal is correctness: typed contracts, deterministic orchestration, structured retry. Token efficiency is the upgrade layer applied once the runtime works and real workloads exist to measure.

This matters for sequencing. Don't build the optimization layer before you have users. Build the thing that makes workflows correct first. The cost savings are real but they're not the adoption driver — reliability is.

That said, one principle applies from day one because it costs nothing to follow:

## The Principle (v1)

> **If a constraint can be enforced by code, it doesn't belong in the prompt.**

This isn't about token counting. It's about where logic lives. `ensure: result.confidence > 0.7` is a postcondition checked by the runtime, not a sentence in the prompt. `compute` handles deterministic transformations, not `infer`. Structural schema enforcement belongs in constrained decoding or post-parse validation, not in prose instructions.

Following this principle in v1 produces a cleaner design. The token savings are a side effect, not the goal.

## The Optimization Layer (v2)

The rest of this document describes the full token efficiency implementation — three-tier classification, shared context caching for parallel blocks, DocRef, prompt diffing in adapt cycles. This is real and valuable work. It belongs after the runtime is working and there are real workloads to optimize against.

Building it before that is premature infrastructure.

---

---

## What This Means in Practice

Every piece of information in a prompt has a cost and a function. Classify them:

| Information type | Enforce how | Prompt tokens |
|---|---|---|
| Enum constraints (`"pos" \| "neg" \| "neu"`) | Constrained decoding | 0 |
| Range constraints (`float[0.0..1.0]`) | Constrained decoding or post-parse | 0 |
| Required fields | Structural enforcement | 0 |
| String length limits | Constrained decoding | 0 |
| Output format ("return JSON") | Constrained decoding | 0 |
| Postconditions (`ensure`) | Post-parse validation + retry | 0 (unless retry) |
| Deterministic business rules | `compute` + `given` | 0 |
| Semantic intent | Must be in prompt | minimum necessary |
| Judgment context | Must be in prompt | minimum necessary |
| Input data | Must be in prompt | exactly what's needed |

The goal: drive the first column to zero. What remains in the prompt is irreducible — the genuine semantic payload.

---

## Constrained Decoding as the Primary Schema Mechanism

The single highest-leverage change: enforce the contract schema at the **token generation level**, not in the prompt.

With constrained decoding (grammar-based generation):
- The LLM's output tokens are physically constrained to conform to the schema
- The output is valid by construction — no post-parse validation needed for structural correctness
- The schema does not need to appear in the prompt at all

**Before** (traditional, schema-in-prompt):
```
Analyze the text and return a JSON object with:
- "label": must be exactly one of "positive", "negative", or "neutral"
- "confidence": a float between 0.0 and 1.0
- "reasoning": a short explanation

Return only valid JSON. No text outside the JSON.

Text: "Great product but shipping was slow"
```
~65 instruction tokens

**After** (Stratum, constrained decoding):
```
Classify emotional tone. Sarcasm → negative. Ambiguous → neutral.

text: "Great product but shipping was slow"
```
~18 instruction tokens

The schema is enforced by the decoder. The prompt contains only what the LLM needs to make the right call. **~72% reduction in instruction tokens.**

The `contract` declaration compiles to two targets:
1. A constrained decoding grammar (enforced at generation time)
2. A semantic summary injected into the prompt only when it aids judgment (e.g., field descriptions that carry meaning the LLM needs)

---

## The Minimal Information Principle

The prompt compiler operates on a single rule:

> The prompt is the **sufficient statistic** for the LLM to produce a valid output. No more.

A sufficient statistic contains exactly the information needed — removing any part degrades output quality; adding anything is waste.

For each element the prompt compiler considers:

```
Is this information needed for the LLM to make the right judgment?
  YES → include it
  NO  → enforce it externally, exclude from prompt
```

Applied to a typical `infer` block:

```stratum
intent "Classify the emotional tone of customer feedback"
infer classifySentiment(text: string) -> SentimentResult {
  given: text.length > 0
  ensure: result.confidence > 0.7 or raise LowConfidence
  context: "Sarcasm → negative. Ambiguous → neutral."
}
```

Prompt compiler decisions:

| Element | Decision | Reason |
|---|---|---|
| `intent` | Include (compressed) | Carries semantic framing |
| `given: text.length > 0` | Exclude | Enforced before invocation; LLM doesn't need to know |
| `ensure: confidence > 0.7` | Exclude | Checked post-parse; injected only on retry |
| `context: "Sarcasm → negative..."` | Include | Genuine judgment guidance |
| Schema field names | Include only if semantically meaningful | LLM needs to know what "confidence" means |
| Schema field types/ranges | Exclude | Constrained decoding handles it |
| "Return valid JSON" | Exclude | Constrained decoding handles it |
| Input binding `text: "..."` | Include | LLM needs the data |

Resulting prompt:

```
Classify emotional tone of customer feedback. Sarcasm → negative. Ambiguous → neutral.

text: "Great product but shipping was slow"
```

---

## Invariant Classification

Every constraint in a `contract` or `ensure` can be classified by enforcement mechanism:

### Tier 1 — Structural (0 prompt tokens, enforced at generation)
Constrained decoding handles these with no prompt overhead:
- Enum fields: `"pos" | "neg" | "neu"`
- Numeric ranges: `float[0.0..1.0]`, `int[1..100]`
- String length: `string[1..500]`
- Required vs optional fields
- Array constraints: `string[](min: 1, max: 10)`
- Output structure: object shape, nesting

### Tier 2 — Semantic (0 prompt tokens, enforced post-parse)
Post-parse `ensure` checks with structured retry on failure:
- Cross-field constraints: `result.end > result.start`
- Aggregate constraints: `result.items.sum() == 100`
- Reference integrity: `result.category in known_categories`
- Confidence thresholds: `result.confidence > 0.7`

Retry prompt is minimal and targeted:
```
Postcondition failed: result.confidence = 0.42, required > 0.7.
Reclassify or explain why the text is genuinely ambiguous.
```

### Tier 3 — Judgment (irreducible prompt tokens)
Only these belong in the prompt:
- Semantic intent: what is this function trying to accomplish
- Disambiguation rules: how to handle edge cases that aren't structural
- Domain context: what the LLM needs to know about the world
- Input data: the actual content to reason about

The language statically classifies every constraint into one of these tiers and routes it to the appropriate enforcement mechanism. No manual annotation required.

---

## Compute Offloading

The principle extends beyond schema enforcement. Any deterministic transformation or check should be `compute`, not `infer`.

**Anti-pattern** — asking the LLM to do arithmetic, formatting, or rule application:
```stratum
// BAD: LLM shouldn't be counting words or formatting dates
infer summarize(doc: Document) -> Summary {
  context: "Keep summary under 100 words. Format the date as YYYY-MM-DD."
}
```

**Correct** — offload invariants to compute:
```stratum
infer summarize(doc: Document) -> RawSummary { ... }

compute finalize(raw: RawSummary) -> Summary {
  text: raw.text.truncateWords(100)
  date: raw.date.format("YYYY-MM-DD")
}
```

The LLM does the judgment (summarization). The runtime does the invariants (word count, date format). Zero tokens spent on mechanical constraints.

**Rule**: If a constraint can be expressed as a pure function, it is `compute`. It never enters the prompt.

---

## Reference-Based Inputs

Sending the same large document to multiple `infer` calls in a `parallel` block is a token multiplier. Instead, use references.

```stratum
// BAD: document sent to each agent separately (3x token cost)
parallel {
  let a = infer analyzeTheme(document: full_doc)
  let b = infer analyzeTone(document: full_doc)
  let c = infer analyzeStructure(document: full_doc)
}

// GOOD: document indexed once, agents receive a reference
let doc_ref = compute index(full_doc)   // chunked, embedded, stored

parallel {
  let a = infer analyzeTheme(doc: doc_ref)      // retrieves relevant chunks
  let b = infer analyzeTone(doc: doc_ref)       // retrieves relevant chunks
  let c = infer analyzeStructure(doc: doc_ref)  // retrieves relevant chunks
}
```

`index()` is a `compute` operation that chunks the document and creates a reference. Each `infer` call retrieves only the chunks relevant to its task via semantic search — not the full document.

The language supports `DocRef` as a first-class type:

```stratum
contract DocRef {
  id: string
  chunk_strategy: "semantic" | "fixed" | "structural"
  metadata: Map<string, string>
}
```

`infer` functions that accept `DocRef` parameters get relevant chunks auto-retrieved based on their `intent` annotation. The intent drives retrieval — the function's semantic goal determines which parts of the document are fetched.

---

## Context Compression for Agents

Agents with `memory: session` accumulate context. Without compression, this grows unboundedly and dominates token cost.

The language provides a `compress` hook on agents:

```stratum
agent Researcher {
  memory: session
  compress: compute summarizeMemory(full_history) -> CompressedMemory {
    trigger: memory_tokens > 2000
    keep_last: 3            // always keep the last 3 exchanges verbatim
  }
}
```

`compress` is a `compute` function — deterministic, no LLM involvement. It runs when memory exceeds the threshold. The result replaces the raw history. The agent continues with compressed context.

For cases where compression requires judgment:

```stratum
compress: infer distillInsights(full_history) -> CompressedMemory {
  budget: 500ms, $0.001   // compression itself has a tight budget
  trigger: memory_tokens > 2000
}
```

Either way, compression is explicit and budgeted — not silent token accumulation.

---

## Prompt Diffing in `adapt` and `reflect`

In `adapt` re-planning cycles, naive re-planning resends the full problem context each time. This compounds token cost across iterations.

Stratum's prompt compiler maintains a **context delta** between iterations:

```
Iteration 1 prompt: [full problem context] + [plan request]
Iteration 2 prompt: [delta: what changed] + [what failed] + [replan request]
Iteration 3 prompt: [delta: what changed] + [what failed] + [replan request]
```

The full context is only sent once. Subsequent iterations send only the diff — new results, failures, and remaining budget. This makes `adapt` token cost roughly linear in the number of new facts per iteration, not in the total problem size.

---

## Token Budget as a First-Class Signal

The LLM should know how much budget it has left — this affects how verbose it should be.

```stratum
orchestrate solve(problem: Problem) -> Solution {
  budget: $1.00
  // budget_awareness: true  ← default
}
```

With `budget_awareness` enabled (default), the prompt compiler injects the remaining budget as a compact signal:

```
[budget remaining: $0.34, 18s]
```

The LLM uses this to calibrate: with plenty of budget, elaborate; with little budget, be concise and decisive. This prevents expensive multi-step reasoning when the budget is nearly exhausted.

---

## Measuring Token Efficiency

The runtime tracks token cost per layer for every `infer` call:

```json
{
  "function": "classifySentiment",
  "tokens": {
    "intent": 8,
    "context_annotations": 12,
    "input_bindings": 9,
    "schema_instructions": 0,
    "retry_feedback": 0,
    "total_input": 29,
    "total_output": 47
  }
}
```

`schema_instructions: 0` is the target. If this is non-zero, the prompt compiler is failing — some schema constraint is being expressed in prose rather than enforced by the runtime.

A `token_audit` tool analyzes a flow and reports:
- What's in each prompt and why
- Which tokens are structural (should be 0)
- Which tokens are semantic (irreducible)
- Efficiency ratio: `semantic_tokens / total_tokens` (higher is better)
- Suggestions: "Field `reasoning` description adds 8 tokens but may not aid judgment — consider removing"

---

## The Efficiency Hierarchy

From most to least token-efficient:

```
1. compute          — 0 LLM tokens
2. constrained infer — schema enforced at decode time, prompt = pure semantics
3. validated infer   — schema enforced post-parse, prompt still minimal
4. retry             — postcondition failed, targeted feedback injected
5. orchestrate       — meta-level planning, highest token cost per invocation
```

Design for level 1. Use level 2 when you need LLM. Fall through only when necessary.

The guiding question for every `infer` block: **what is the irreducible semantic payload here?** Strip everything else.
