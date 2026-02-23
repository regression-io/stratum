# Claude Code Integration

## Two Audiences

Track 2 has two distinct users with different mental models:

**Professional developers** — they know what a contract is, they're writing `@infer` decorators or reviewing typed execution plans, they want to understand the step graph. They're a secondary audience for the MCP integration; their primary surface is the Python library (Track 1).

**Vibe coders** — they're prompting Claude to build things. They don't write `@infer`. They don't want to see `.stratum` YAML, contracts, or step modes. They want the result and a one-line summary of what happened. The IR is the engine; the conversation is the interface.

**The design principle for vibe coders**: the plan, the contracts, and the execution are entirely invisible. What surfaces is:
- A plain-language description of what's about to happen, before it does
- A single approval step ("Proceed?")
- The result, plus a one-line cost/status summary
- Escalations as natural conversation ("Two analyses disagreed — here are both views. Which should I use?")

The HITL mechanism for vibe coders isn't a technical escalation — it's just the chat. `converged: false` on a `debate` becomes "I got conflicting answers. Here are both. Which do you want?" That's already the conversation they're in.

---

## The Workflow Improvements

When Claude Code solves a task today, six failure modes are endemic. Stratum addresses each computationally, not through guidance.

### 1. Loops on failure

**Today:** Claude writes code → tests fail → Claude reads error and retries with the full conversation history as context. Each loop re-sends everything. No structure on what changed. Converges slowly or not at all.

**With Stratum:**
```stratum
infer refine writeAuthMiddleware(spec: Spec) -> Code {
  until: compute runTests(result).allPass
  max_iterations: 4
  feedback: compute runTests(result).failures
}
```
Each retry injects only the structured test failures — not the full history. The retry prompt is a diff, not a replay. Iteration count is bounded. When it hits `max_iterations` it surfaces a structured failure instead of silently degrading.

**Measurable:** fewer attempts, lower tokens per attempt, explicit termination.

---

### 2. Plans exist only in Claude's head

**Today:** Claude forms a plan internally and starts executing. The plan is invisible. You discover it's wrong when step 4 fails because step 2 produced the wrong output shape.

**With Stratum:** `stratum.plan()` generates a typed `.stratum` flow before a single file is touched. The compiler verifies that step 3 produces what step 4 expects. Dependencies are explicit. Budget is estimated. The plan is reviewable and approvable before execution.

**Measurable:** type errors caught pre-execution, cost known upfront.

---

### 3. Token waste in Claude's own prompts

Claude re-sends large context on every step in a loop — full file contents, full error history, full conversation. Most is structural and doesn't change the reasoning.

The token audit tool measures this exactly: "of the 2,400 tokens in this prompt, 940 are structural constraints that constrained decoding could enforce for free."

**Measurable:** token cost per step, before and after.

---

### 4. No budget awareness

**Today:** complex task starts, $2.40 is spent, you find out at the end. No mechanism for Claude to know it's burning budget or to adjust.

**With Stratum:** `budget: $0.50, 120s` is a hard cap enforced by the runtime, not a suggestion in a prompt. When 80% is consumed, the flow surfaces a checkpoint. Claude can switch strategies or stop and report partial results rather than overrunning.

**Measurable:** predictable cost, no surprise bills.

---

### 5. Untyped inter-step data

**Today:** Claude passes results between steps as free text or unstructured JSON. If step 3's output format shifts, step 4 fails confusingly.

**With Stratum:** every inter-step result is typed against a `contract`. The compiler verifies that `designTokenSchema → writeMiddleware` type-checks before execution starts.

**Measurable:** class of failures eliminated before they occur.

---

### 6. Audit trail is a transcript

**Today:** a session produces a long conversation. Understanding what happened means reading all of it.

**With Stratum:** every execution produces a structured trace — per-step inputs, outputs, retry reasons, token cost, timing. Comparable across runs. Debuggable.

**Measurable:** time to diagnose a failed run.

---

## Comparison With Skills and Rules

Claude Code already has mechanisms for shaping behavior. Understanding what they do — and don't — do is essential to understanding why Stratum is different in kind, not just degree.

### Rules (CLAUDE.md)

Rules are natural language instructions that persist across sessions:

```markdown
# CLAUDE.md
- Always validate LLM outputs before using them downstream
- Use structured retry when an operation fails
- Track token cost across multi-step tasks
```

**What rules do:** They guide Claude's behavior. Claude reads them, understands the intent, and tries to follow them. A well-written rule improves the probability of correct behavior.

**What rules don't do:**
- They don't enforce anything computationally
- Claude can interpret them loosely or inconsistently
- "Validate outputs" means something different to Claude on a Friday afternoon than it does in a Stratum `ensure` condition
- There is no machine check. The rule either influences the generation or it doesn't.
- Rules compound poorly — 20 rules interact in unpredictable ways
- Rules drift — they describe intent but don't capture the full semantics

A rule that says "use Stratum patterns" is still a rule. It guides. It doesn't enforce.

### Skills (Slash Commands)

Skills are predefined workflows invoked as slash commands:

```
/forge   → multi-step feature implementation
/commit  → structured commit message generation
/review-pr → pull request review
```

**What skills do:** They're prompt templates with sequenced steps. They make complex workflows repeatable and consistent. A good skill is significantly better than ad hoc prompting for a known task shape.

**What skills don't do:**
- They don't type-check inter-step data
- They don't enforce budget limits
- They don't provide structured retry with failure feedback — they retry by re-prompting the whole skill
- They don't produce typed audit traces
- Quality is bounded by the quality of the prompt, not by a runtime
- They can't be composed with static analysis — there's no compiler that checks two skills are compatible

A skill like `/forge` is a well-structured prompt. Stratum `flow` is a typed, statically-analyzed execution plan. The distinction is: one guides generation, the other constrains it.

### Hooks

Hooks are shell commands that execute in response to events:

```json
{
  "hooks": {
    "PostToolUse": [
      { "matcher": "Write", "hooks": [{ "type": "command", "command": "run-tests.sh" }] }
    ]
  }
}
```

**What hooks do:** They provide real computational enforcement at specific event boundaries. A post-tool hook that runs tests after every file write is genuine enforcement — not guidance.

**What hooks don't do:**
- They operate at tool-call granularity, not at the semantic level of a flow
- They don't type-check inter-step data
- They don't provide structured retry with failure context injected into the next prompt
- They're imperative shell commands — not typed, not composable, not statically analyzable

Hooks are the closest existing mechanism to real enforcement. Stratum builds on the same principle — computational enforcement rather than guidance — but at a higher level of abstraction with types and structured contracts.

### The Gap

| Mechanism | Enforcement | Types | Structured retry | Budget | Audit |
|---|---|---|---|---|---|
| Rules | Guidance only | No | No | No | No |
| Skills | Guidance only | No | No | No | No |
| Hooks | Computational | No | No | No | No |
| Stratum MCP | Computational | Yes | Yes | Yes | Yes |

Rules and skills are better than nothing. Hooks are meaningfully different. Stratum via MCP is different again — it adds types, structured retry, and budget enforcement to computational enforcement.

---

## What Actually Bounds Claude Code to Stratum Semantics?

The wrong question is "will Claude follow Stratum's rules?" LLMs don't follow rules reliably — anyone who has written enough CLAUDE.md knows this. The right question is: **can the workflow be structured so that Stratum is what the workflow IS, not a rule Claude is asked to follow?**

The answer is yes. Here's why.

### The key insight: outputs are what matter, not reasoning

Claude's internal reasoning between checkpoints doesn't need to be constrained. What matters is whether the outputs at each checkpoint are valid. TypeScript doesn't constrain your thinking — it constrains your output. That's enough. The same principle applies here.

Every meaningful output in the workflow passes through one of four enforcement layers. At each layer, invalid output is blocked — not discouraged, blocked.

### Layer 4 — MCP: categorical enforcement at execution time

When Claude calls `stratum.execute(spec, inputs)`, there is no code path that returns invalid output. The runtime either:
- Returns validated, typed output
- Raises a typed exception
- Retries with structured failure feedback until `max_iterations`

The contract says `confidence: float[0.0..1.0]`. The LLM returns `1.7`. It fails. Claude cannot argue its way around it, reinterpret it, or try a different approach — the runtime rejects and retries with the specific violation as structured context. This isn't guidance. It's categorical.

This is why the MCP path is the core of the argument. For every execution that flows through `stratum.execute()`, Stratum semantics aren't optional.

### Layer 3 — Hooks: gate enforcement on artifacts

Hooks intercept tool calls before they complete. A PostToolUse hook on `Write` that validates any `.stratum` file written against the spec validator means Claude Code **physically cannot write an invalid `.stratum` file**. The hook rejects it. Claude has to fix it. The invalid artifact never persists.

This closes the gap between MCP calls. Claude can reason however it wants — what it cannot do is write an invalid plan artifact past the hook.

### Layer 2 — Skills: structural embedding, not optional guidance

When a developer invokes `/plan`, the skill calls `stratum.plan()`. Claude doesn't decide to use Stratum — the skill IS Stratum. The question "will Claude use Stratum?" doesn't arise when the skill invocation directly calls the MCP server.

If the key developer workflows — planning, implementation, review — are skills that embed Stratum calls, then Stratum gets used whenever those workflows are invoked. Not because Claude chose it. Because the workflow is built that way.

```
/plan   → calls stratum.plan()    → typed .stratum flow
/forge  → executes stratum flow   → contract-validated steps
/audit  → calls stratum.audit()   → token waste measurement
```

### Layer 1 — Rules: framing the gaps

Rules handle the space between the other three layers — where Claude is making decisions before a skill is invoked or a tool is called. A well-written rule doesn't say "use Stratum" in the abstract. It says:

```markdown
Before beginning any task with more than two steps, call stratum.plan()
and present the typed flow for approval before executing anything.
```

This is specific enough to be consistently followed because it's a concrete action at a concrete trigger point, not a principle Claude has to interpret.

### Trace a real workflow

**Professional developer** runs `/plan "add JWT authentication"`:

```
Skill invoked
  → calls stratum.plan() [MCP]
  → MCP generates typed .stratum flow
  → Hook validates the flow artifact on write
  → Developer reviews and approves
  → stratum.execute() runs the flow [MCP]
      → each step output validated against contract
      → failures trigger structured retry
      → budget tracked against hard cap
  → Audit trail written with per-step cost and timing
```

**Vibe coder** says "add JWT auth to my Express app":

```
Claude generates .stratum IR internally [invisible]
  → stratum_plan validates it [invisible]
  → Claude presents to user:

    "Here's what I'll do:
     1. Design a token schema for your existing user model
     2. Write the JWT middleware with expiry handling
     3. Add the auth routes

     Estimated cost: ~$0.03. Proceed?"

  → User says yes
  → stratum_execute runs the flow [invisible]
      → contracts enforced, retries handled internally
  → Claude presents result:

    "Done. Auth middleware added to middleware/auth.js,
     routes added to routes/auth.js.
     3 steps, $0.021, 1 retry on the middleware (fixed automatically)."
```

The IR, contracts, step modes, and retry logic are never surfaced. The vibe coder sees a plain-language plan, approves it, and gets a result with a one-line summary. At no point does "will Claude decide to use Stratum?" enter the picture — the skill calls Stratum directly, the MCP enforces contracts, and the hook gates artifacts regardless of how Claude got there.

### The analogy that actually holds

Not TypeScript + ESLint + CI. That analogy is too optimistic — it implies each layer independently adds coverage.

The better analogy: **a production API with authentication, rate limiting, and input validation.**

No single layer makes the API secure. Authentication without input validation still has SQL injection. But together, each layer closes a specific class of vulnerabilities. A request that gets past authentication still hits input validation. A request that passes input validation still hits rate limiting.

The point isn't that the API is perfectly secure. The point is that the attack surface is bounded at every layer, and the combination makes exploiting the system hard in practice even if it's not impossible in theory.

Stratum + skills + hooks + rules works the same way. The question isn't whether Claude can produce non-Stratum output — it can, in the gaps between layers. The question is whether those gaps are consequential. When planning flows through `stratum.plan()`, execution flows through `stratum.execute()`, artifacts are gated by hooks, and the token audit measures what actually happened — the gaps are small and their consequences are visible in the audit trail.

**That's enough. Not perfect. Demonstrably better.**
