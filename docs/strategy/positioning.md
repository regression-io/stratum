# Positioning

## What Stratum Is Not

- A prompt templating system (Jinja, Handlebars)
- A framework for calling LLMs from code (LangChain, LlamaIndex, AutoGen)
- A constrained generation system (Guidance, LMQL, Outlines)
- A workflow orchestration tool (n8n, Temporal, Prefect, Zapier)
- A typed LLM wrapper (instructor, Marvin)

All of these solve part of the problem. None treat formal contracts, LLM inference, and typed inter-step communication as co-equal first-class citizens with a shared execution model.

---

## Where the Differentiation Actually Opens

This is worth stating honestly before making the case, because the honest version is more credible than the inflated one.

**`@infer` alone is close to instructor.** Pydantic model = contract. Structured outputs API = constrained decoding. `model_validator` = postcondition. `max_retries` = retry loop. For a single typed LLM call, instructor covers roughly 80% of what a standalone `@infer` delivers. Instructor is in production at scale. This is not a weak competitor.

**`@flow` is where the gap opens.** The moment you compose multiple `infer` calls with typed inter-step data — and need to know at write time that step 3's output type matches step 4's input — instructor has nothing. DSPy composes modules but doesn't statically verify inter-step type compatibility. No existing library has a compiler that checks this before the program runs.

**The adoption curve:** developers reach for instructor first. It's the right tool for one or a few typed LLM calls. They outgrow it when:
- Multi-step flows fail at step N because step N-1's output shape shifted
- Retry loops run forever because there's no structure on what failed
- They need hard budget caps, not just cost visibility
- Parallel branches need partial failure semantics

That outgrowth moment is the Stratum entry point. The pitch isn't "better instructor." It's "when instructor stops being enough, here's what you reach for next."

---

## The Compiler Advantage

Developers author Stratum through Python decorators or TypeScript — not a new syntax. The `.stratum.yaml` IR is what those libraries emit internally. The compiler advantage doesn't require learning a new language — it comes from the fact that `@infer` and `@contract` carry enough semantic information for static analysis.

**The primary differentiator is determinism and typed contracts — not token efficiency.** The thing that makes developers reach for Stratum is that LLM workflows stop failing in confusing ways: `ensure` postconditions catch bad outputs before they propagate, inter-step types are verified, and the orchestration structure is auditable. Token efficiency is a real benefit at scale — it's the v2 story, not the adoption story.

### 1. Static analysis before execution

Libraries validate types at runtime. You discover step 3's output doesn't match step 4's input when the flow crashes in production.

Stratum catches this before the program runs. In n8n, inter-node communication is untyped JSON — the engine has no idea what shape the data is. In DSPy, modules compose but output/input type compatibility isn't verified at write time. In Stratum, the compiler verifies the entire `flow` is type-consistent before a single call runs.

### 2. One artifact: type + prompt + validator

In a library, these are three separate things you write and keep in sync manually:

```python
class SentimentResult(BaseModel):    # type
    label: Literal["pos", "neg"]
    confidence: float

SYSTEM_PROMPT = "Return JSON with label and confidence"  # drifts from type
def validate(r): assert r.confidence > 0               # duplicates type
```

In Stratum, there is one artifact. The compiler derives prompt instructions, constrained decoding grammar, and runtime validator from the `contract`. They cannot drift because they don't exist separately.

### 3. `infer`/`compute` as a semantic distinction the runtime understands

In every existing library and framework, the difference between an LLM call and a deterministic function is informal. The runtime doesn't know or care. In Stratum, the runtime knows which parts of the program are non-deterministic and:

- Warns when an `infer` result is used where determinism is required
- Refuses `infer` inside convergence conditions (`until:` in `refine`)
- Routes each to different execution backends

n8n has "AI node" vs "code node" as a UI distinction. DSPy has no equivalent distinction. Neither carries semantic weight the runtime enforces.

### 4. `ensure` as a machine-checked postcondition

Every existing library has retry — but it's glue code you write. You construct the retry loop, the error message, decide what to inject. None of it is verifiable.

In Stratum, `ensure: result.confidence > 0.7` is statically checked: the compiler verifies `result.confidence` is a valid field on the declared return type. The retry prompt is auto-generated from the failed condition. Machine-checked. Not glue code.

### 5. `orchestrate` with typed plan validation

n8n graphs are fixed at design time. DSPy programs are fixed at write time. Neither lets the LLM decide the execution structure at runtime.

Stratum's `orchestrate` lets the LLM design the execution graph at runtime — but the plan is a typed contract validated before any step executes. The LLM cannot reference undeclared agents, produce inter-step type mismatches, or exceed declared budgets. Dynamic structure with formal guarantees at the boundary.

### 6. `parallel` with `require:` + `validate:` semantics

No existing library or workflow tool has typed parallel execution with declared partial failure semantics. `require: all | any | N` sets the structural floor. `validate:` adds semantic quality checks on the collected results — either `compute` (deterministic) in static flows or `infer` (LLM judgment) in `orchestrate`. The LLM can choose both when generating a plan.

---

## vs. Specific Tools — Honest Assessment

### vs. instructor

**Where it's close:** Instructor is the best single-function typed LLM wrapper that exists. Pydantic models as contracts, structured outputs API for schema enforcement, `max_retries` with validation error feedback, wide model support. For a single `@infer` call, instructor covers ~80% of the value. It's not a weak competitor — it's a strong one with real traction.

**Where Stratum diverges:**
- No `flow` — no typed composition of multiple calls, no inter-step type verification
- No `compute` vs `infer` distinction — the runtime treats everything as an LLM call
- No static analysis — inter-step type mismatches discovered at runtime, not write time
- No `orchestrate` — structure is fixed, can't be LLM-generated with validation
- No `parallel` with partial failure semantics
- No hard budget enforcement — cost tracking, not hard caps
- No language-agnostic IR — can't be consumed by other tools or agents

**Verdict:** The natural upgrade path from instructor. Not a replacement for it — the same developer will use instructor for simple cases and Stratum when composition gets complex enough to need static guarantees.

---

### vs. DSPy

**Where it's close:** DSPy is the most sophisticated existing approach to typed LLM programs. Signatures as typed contracts, composable modules that feel like `@flow`, `dspy.Assert`/`dspy.Suggest` as rough postconditions. For a basic linear flow with typed steps, DSPy covers ~60% of the value.

**Where DSPy is ahead of Stratum:** Prompt optimization. DSPy can automatically tune prompt programs against a metric — it learns better prompts from examples and labeled data. This is a genuine DSPy advantage for teams with stable task definitions and evaluation sets. Stratum's `context:` annotations are hand-written and static; DSPy's are learned.

**Where Stratum diverges:**
- No static inter-step type checking — DSPy modules compose but output/input compatibility isn't verified before running
- No `compute` vs `infer` semantic distinction — everything is a module, the runtime doesn't know what's deterministic
- No `orchestrate` with typed plan validation
- No `parallel` with partial failure semantics
- No hard budget enforcement
- No language-agnostic IR
- `ensure` semantics are weaker — `dspy.Assert` triggers retry but without the structured feedback injection Stratum provides

**The composable substrate insight:** DSPy and Stratum are not pure competitors — they solve different layers. DSPy optimizes *what to say* to the LLM. Stratum enforces *what the LLM must produce and what happens when it doesn't*. These compose cleanly:

- v1: Stratum's `compile_prompt()` assembles intent + context + inputs deterministically (hand-written)
- v2: `compile_prompt()` is DSPy-backed — the prompt is a DSPy-optimized program tuned against real examples, but `ensure`, retry, budget, and trace are still Stratum's responsibility

The `@infer` decorator's `context:` becomes optionally DSPy-backed. Same interface, learned internals. DSPy provides the optimization; Stratum provides the contract envelope around it.

**Verdict:** DSPy is the right comparison for ML practitioners. The prompt optimization capability is a real v2 integration target, not just a competitive threat. Position DSPy as a composable substrate for teams who want optimized prompts inside Stratum's contract guarantees.

---

### vs. LangChain / LlamaIndex

Frameworks. LLM calls are library calls with no type safety. Orchestration is entangled with invocation. No `ensure` semantics, no formal contracts. These are the thing developers are already trying to escape when they reach for instructor or DSPy. Not the primary comparison point.

---

### vs. LMQL / Guidance / Outlines

Constrained generation — LLM output is shaped at the token level. Useful for structured text generation. Not general-purpose orchestration frameworks. No `compute`/`infer` composability, no flow orchestration, no semantic postconditions. These solve a narrow problem well. Not competitors at the system level.

---

### vs. n8n

**The honest framing:** n8n is not competing on technical depth. It competes on a completely different axis: getting something working without writing code. Visual node graph, 400+ integrations, non-developers can build it, runs today.

**What n8n gives you:** Fast. Visual. Observable to stakeholders. No code required for basic flows. Time to first working thing: hours.

**What n8n costs you:** Nodes pass untyped JSON. No schema validation between nodes — output shape changes break downstream nodes silently at runtime. Retry is re-running the node with the same inputs, no structured failure feedback. No postconditions, no budget caps, no static analysis. Quality is whatever the LLM returns.

**The "good enough" trap:** n8n captures attention early and stickiness is real. A workflow that's 80% reliable gets tuned and patched rather than replaced. The ceiling gets tolerated because switching cost is real even when the current thing is frustrating. Teams that punt to n8n early often spend months maintaining increasingly brittle workflows before the pain of the ceiling exceeds the cost of the switch.

**The ceiling hits when:**
- LLM output needs to feed directly into another system without human review
- The flow has enough steps that untyped JSON propagation causes cascading failures
- Volume is high enough that silent quality degradation is a real cost
- The team wants to test the workflow programmatically

**The migration path is a product feature:** n8n users who hit the ceiling are warm Stratum adopters — they know what the workflow should do, they've seen it work unreliably, they're ready for code and guarantees. A tool that imports an n8n workflow, generates the equivalent `.stratum` IR, and flags every untyped inter-node boundary as a typed contract gap is the conversion moment. Not "n8n is bad" — "here's the path from here."

**vs. Temporal:** Temporal solves durable workflow execution — deterministic orchestration with replay, fault tolerance, exactly-once semantics. No LLM-native constructs. Activities are just async functions. No intent layer, no contracts, no typed LLM output. Complementary rather than competitive — a Stratum flow could run inside a Temporal workflow for the durable execution guarantees.

---

## The Compiler Advantage Compounds

A 3-step LLM flow works fine with instructor. A 30-step multi-agent flow with parallel branches, dynamic orchestration, retry budgets, and cross-agent type safety is essentially unmanageable without a compiler. As systems get more complex — and they will — the gap between library and language widens.

The irreducible value: **analysis of programs that don't exist yet**. A library can only observe programs that are running. That's the gap.

---

## Honest Limitations

- `@infer` alone fights instructor on instructor's home turf — the differentiation requires `@flow`
- DSPy's prompt optimization is a real capability Stratum doesn't have
- n8n has a working product with a large community; Stratum doesn't exist yet
- A compiler requires years of engineering; the v1 Python library approximates the semantics without the full static analysis
- Stratum as a standalone language is unlikely to become the standard without organizational backing

Stratum's ideas becoming the standard — absorbed into whatever wins — is likely regardless. The question is whether they arrive as a coherent, principled system or get reassembled piecemeal across competing libraries.
