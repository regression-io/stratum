# Stratum as a Claude Code Execution Runtime

If you've used Claude Code for anything non-trivial, you've hit the wall.

You give it a task. It starts confidently. It reads files, writes code, runs tests. Then something fails. It retries. The retry fails differently. It retries again, this time re-reading files it already read, re-explaining the task to itself, gradually consuming context it can't get back. Eventually it either produces something broken, something that works for the wrong reasons, or it just gives up in a way that leaves you unsure what it actually tried.

The problem isn't Claude. The problem is that Claude Code has no execution model. It's a very capable agent improvising in a loop.

This post is about giving it one.

---

## What Claude Code Actually Does

Claude Code is Anthropic's command-line tool for coding with Claude. You describe what you want, it uses tools — reading files, running commands, writing code — to do it. It can handle surprisingly complex tasks: refactoring modules, writing tests, debugging failures, building features from scratch.

What it can't do natively: guarantee that what it just did is what you asked, explain exactly what it tried and why, stop when it's about to exceed your budget, or hand off cleanly to a human when it genuinely can't figure something out.

Those aren't criticism — they're missing primitives. Claude Code is a great agent without a runtime. Stratum is the runtime.

---

## What Stratum Is

Stratum is a Python library (spec only for now, implementation coming) with two core ideas:

**First:** `@infer` (an LLM call) and `@compute` (a normal function) have identical type signatures. A caller cannot tell them apart. This means you can compose them freely, swap one for the other, test the orchestration without touching an LLM, and migrate from expensive inference to fast rules when patterns emerge.

**Second:** Every `@infer` call has declared contracts (what it must return), postconditions (what the return must satisfy), and a hard budget (time and cost). The runtime handles retry automatically, injecting only the specific failure on each attempt — not replaying the full context.

The result: LLM calls that behave like the rest of your code. When they fail, you know exactly why. When they retry, the retry is targeted. When the budget runs out, you get an exception.

The library is the primary product. But there's a second deployment context that's available now, before the library ships: Stratum as an MCP server running behind Claude Code.

---

## Claude Code Already Has an Execution Model. It Just Isn't Exposed.

Here's the thing: when you give Claude Code a task, it's already doing exactly what Stratum formalizes.

It decomposes the task into steps. It calls tools (read file, run command, write code). It checks the result. It retries on failure. It tracks something like attention or context budget. It produces typed artifacts — files, test results, diffs.

That's a `@flow` of `@infer` and `@compute` calls. It's just implicit. There's no spec for it. Claude is making it up as it goes, constrained only by your CLAUDE.md file and whatever conventions you've established.

Stratum makes it explicit. Instead of Claude improvising a plan, it generates a typed execution plan before touching anything. Instead of blind retry, it retries with structured failure context. Instead of a transcript, you get a trace record you can actually read.

---

## The Specific Problems

Let me be concrete about what goes wrong without this.

### The retry spiral

You ask Claude to add authentication to an API. It writes the code. Tests fail. It retries. The retry includes re-reading all the files it already read, re-establishing context it already had, burning tokens on orientation instead of the actual fix. By the third retry, it's so deep in context that it's making changes to fix the test symptoms rather than the underlying cause.

With structured retry, the failure is explicit: "test `test_token_expiry` failed with `401 Unauthorized` — token validation middleware not applied to `/api/refresh`." Claude retries with that. One targeted fix, not a spiral.

### The plan that exists only in Claude's head

Claude starts a refactor. It reads ten files. It has a plan. It starts making changes. Halfway through, it gets something wrong and has to backtrack. The plan was never written down, never reviewed, never committed. You have no idea what it intended to do versus what it actually did.

With Stratum, the plan is generated first as a typed DAG — steps, dependencies, inputs, outputs — and presented for your review before a single file is touched. You either approve it or you don't. If you approve it and something goes wrong at step 4, you know steps 1–3 completed successfully and exactly what state they left the codebase in.

### Context window degradation

Claude Code sessions can run for a long time on complex tasks. Context windows are finite. As the session grows, Claude's attention degrades — it starts forgetting constraints it established early on, re-reading things it already processed, making inconsistent choices.

There's no signal. Nothing tells you "this session is 80% through its effective context." You find out when the output quality drops.

With Stratum, each step declares a budget that draws from a shared flow envelope. As the envelope depletes, the signal is explicit. Claude can compress context, checkpoint state, or surface remaining work for the next session — instead of quietly degrading.

### The unauditable transcript

Something goes wrong in a Claude Code session. The output is wrong. Why? You scroll through the terminal output — a mix of thinking, tool calls, partial results, corrections, and final outputs. There's no structured way to ask "what did step 3 actually return?" or "how many times did it retry?" or "what was the token cost of the auth module refactor versus the test writing?"

Every Stratum step produces a structured trace record: inputs, outputs, retry count, token cost, duration. `stratum_audit` at the end gives you a queryable record of everything that happened.

---

## What It Looks Like in Practice

A developer asks Claude Code: "Add rate limiting to all API endpoints. Exclude health checks. Use token bucket. Write tests."

**Without Stratum:**

Claude reads files. Has a plan in its head. Writes middleware. Writes tests. Tests fail — the middleware isn't applying to one route family. Claude retries, re-reads three files, re-establishes context, fixes the wrong thing. Tests partially pass. Claude tries again. Eventually you get code that passes tests with a lingering feeling that you're not sure why the third retry worked when the second didn't.

**With Stratum:**

Claude calls `stratum_plan`:

```
ExecutionPlan {
  steps: [
    { id: "1", fn: "read_routes", output: RouteList },
    { id: "2", fn: "design_middleware", output: MiddlewareSpec,
      depends_on: ["1"] },
    { id: "3", fn: "implement_middleware", output: MiddlewareCode,
      depends_on: ["2"] },
    { id: "4", fn: "write_tests", output: TestSuite,
      depends_on: ["3"],
      ensure: "all tests pass" },
  ],
  budget: "~8 tool calls, ~3 minutes"
}
```

You review it. Looks right. You approve.

Step 3 completes. Step 4's tests fail: "middleware not applied to `/api/v2/` prefix — only `/api/` covered." That specific failure goes back to step 3 as the retry context. Claude fixes the prefix pattern. Tests pass.

`stratum_audit` at the end:

```
Step 1: read_routes — 1 attempt, 312 tokens
Step 2: design_middleware — 1 attempt, 891 tokens
Step 3: implement_middleware — 2 attempts, 1,204 tokens
  Retry reason: middleware not applied to /api/v2/ prefix
Step 4: write_tests — 1 attempt, 2,108 tokens
Total: 4,515 tokens, 2 retries, all passing
```

That's the audit trail. Committed alongside the code.

---

## For Vibe Coders Specifically

If you're using Claude Code to build things you couldn't build otherwise — and you're not necessarily reviewing typed execution plans — Stratum's value is different, but it's real.

The code Claude generates is `@infer`-annotated.

Right now, when Claude writes code that calls an LLM, it writes something like:

```python
response = openai.chat.completions.create(
    model="gpt-4",
    messages=[{"role": "user", "content": f"Classify this: {text}"}]
)
label = response.choices[0].message.content.strip()
```

That code is fragile. There's no contract on what `label` should look like. There's no retry if the model returns something unexpected. There's no budget. There's no trace. When it breaks in production three months later, you're debugging a string.

With Stratum, Claude writes:

```python
@contract
class Classification:
    label: Literal["spam", "not_spam", "uncertain"]
    confidence: Annotated[float, Field(ge=0.0, le=1.0)]
    reasoning: str

@infer(
    intent="Classify whether this email is spam",
    ensure=lambda r: r.confidence > 0.7,
    budget=Budget(ms=500, usd=0.001),
    retries=3,
)
def classify_email(text: str) -> Classification: ...
```

That code tells you what it expects, validates what it gets, retries when it fails, and stops when it's spent too much. When it breaks in production three months later, the trace record tells you exactly what input produced what output, how many times it tried, and what postcondition failed.

You didn't have to set any of that up. Claude did it because that's how Stratum code is written.

---

## Two Kinds of Output From the Same Claude Session

This is the part worth sitting with.

When Claude Code generates a feature for you today, it produces code that works (hopefully) but doesn't explain itself. The LLM calls inside it are black boxes. The retry logic (if any) is improvised. The observability is whatever you thought to add.

When Claude Code generates a feature through Stratum, it produces code with declared intent, typed contracts, structured retry, and built-in trace records. The LLM calls are no longer black boxes — they have specifications. The retry is no longer improvised — it's targeted. The observability is automatic.

Same Claude. Same session. Completely different code.

The difference is that Claude is generating against a spec it knows. It knows what `@infer` means. It knows what `@contract` enforces. It knows what `ensure` does. The spec tells it exactly what well-formed LLM code looks like, and it writes that.

---

## The Recursive Part

Stratum makes Claude Code better at building LLM systems. Which are themselves better because they use Stratum.

A vibe coder builds something with Claude Code + Stratum. The code has `@infer` annotations. The code gets shared. A developer encounters it. They look up `@infer`. They find the spec. They start using it deliberately. Their code gets shared. The pattern spreads — not because anyone is evangelizing it, but because Stratum-annotated code is visibly more reliable than the alternative.

At some point Claude models see enough Stratum-annotated code in training that they generate it naturally, without needing the spec as a prompt. At that point the flywheel is self-sustaining.

That's the long bet. The short bet is just: Claude Code stops surprising you.

---

## The Honest Limitation

Nothing forces Claude Code to use the MCP server. Claude can ignore it entirely if it wants to. This is worth being direct about.

What the MCP server actually is: a structured substrate that eliminates *accidental* drift. The kind where Claude pattern-matches on your CLAUDE.md instead of following a formal spec. The kind where retry logic gets improvised because there's no other option. The kind where context degrades silently because there's no signal.

Four things together make it robust:
- **Environment restriction** — configure Claude Code to route LLM calls through Stratum. One path in, not an optional detour.
- **Hooks** — detect when Claude writes ad-hoc retry loops or uncontracted LLM calls. Flag them.
- **Skills** — make the planning skill the entry point for non-trivial tasks, not an option.
- **Rules** — fill the gaps with explicit conventions for what Stratum can't structurally enforce.

This isn't a security model. It's an alignment model. And it works — not because Claude is forced into it, but because Stratum-aligned behavior is just better, and Claude knows it.

---

## Status

The MCP server ships with Phase 2 of the Stratum library. The Python library (Phase 1) is the prerequisite — the MCP server is a thin wrapper over it.

The spec for exactly what the runtime enforces is at [SPEC.md](../SPEC.md). The detailed walkthrough of the library design is at [introducing-stratum.md](introducing-stratum.md).

If you're using Claude Code and want to track where this goes: [watch the repo](https://github.com/regression-io/stratum) and drop questions in [Discussions](https://github.com/regression-io/stratum/discussions). The spec is a draft — it gets better from people who've actually hit these problems.
