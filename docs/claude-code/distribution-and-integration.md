# Distribution and Integration

## The Key Observation

Claude Code is already a Stratum runtime. It just doesn't formalize it.

```
Claude Code today          Stratum concept
─────────────────────      ───────────────
Bash / Read / Write   →    compute
LLM reasoning step    →    infer
Task execution loop   →    flow
Tool result checking  →    ensure
Context window        →    agent memory
Permission budget     →    budget
```

The integration isn't "add Stratum to Claude Code." It's "recognize that Claude Code already implements the Stratum model and give it a formal language — with the compiler guarantees that come with it."

That's a much stronger pitch than a new language. It's a formalization of something that already exists, with demonstrable improvements in reliability, token efficiency, and auditability.

---

## Three Integration Paths

### Path A — Stratum as MCP Server (available now, no permission needed)

Claude Code supports MCP servers. Stratum can be implemented as an MCP server today, without any changes to Claude Code itself:

```json
// .claude/settings.json
{
  "mcpServers": {
    "stratum": {
      "command": "stratum-mcp",
      "args": ["--spec", "./flows/"]
    }
  }
}
```

The MCP server exposes tools:
- `stratum.execute(spec_file, inputs)` — run a `.stratum` flow with typed inputs/outputs
- `stratum.audit(file)` — token audit on any file with LLM calls
- `stratum.validate(spec_file)` — validate a `.stratum` spec against its contracts
- `stratum.plan(task)` — generate a `.stratum` spec from a natural language task description

Claude Code can call these tools in its normal execution loop. No Anthropic involvement required. The MCP path is the unilateral distribution play.

**What this means in practice:** a developer adds the Stratum MCP server to their Claude Code config. Claude Code now knows how to execute typed, contract-validated LLM flows. The `.stratum` IR is generated and validated entirely internally. What the user sees depends on who they are:
- **Professional developers** see Python with `@infer` decorators — the library surface
- **Vibe coders** see plain-language summaries — "Here's what I'll do. Proceed?" — and a one-line result. The IR, contracts, and retry logic are invisible.

---

### Path B — Stratum as Code Generation Target (available now, no permission needed)

When Claude Code (or Codex) generates LLM orchestration code today, it generates:
- Raw retry loops
- Ad hoc prompt construction
- Manual schema validation
- Untyped inter-step data passing

If Stratum exists as a published spec and Python/TypeScript library, AI coding tools will generate it — because it's the best way to express the problem. You don't need Anthropic or OpenAI's permission for this. You need the library to exist and be documented well enough that the models know about it.

**The Track 1 + Track 2 convergence**: when a vibe coder asks Claude Code to "build X" and the output is persistent code, the plan skill (Track 2) generates `@infer`-annotated Python using the stratum library (Track 1). The vibe coder never wrote a contract or a decorator — they approved a plain-language plan and got professionally structured LLM code as output. Their codebase looks like a professional developer wrote it. They don't need to know what `@infer` means; they just need the code to work reliably.

This is the flywheel: vibe coders get better outputs, their codebases contain Stratum code, professional developers who inherit or review that code encounter the library, adoption spreads in both directions.

The mechanism: publish the library, publish the docs, get it into the training data and context of AI coding tools. Models generate code they've seen. Make Stratum the thing they've seen.

This is the same path that made Zod the default TypeScript validation library — it became so idiomatic that AI coding tools generate it by default, which reinforces its adoption, which makes tools generate it more.

---

### Path C — Native Integration (requires cooperation)

The highest-value path. Anthropic ships Stratum semantics as a first-class construct in Claude Code. OpenAI does the same in Codex CLI.

**The pitch to Anthropic:**
> Claude Code already implements the Stratum model informally. Formalizing it means:
> - Claude Code's own execution is more token-efficient (the prompt compiler applies to Claude's own reasoning)
> - Developers get typed, auditable flows instead of ad hoc scripts
> - Claude Code can statically analyze multi-step tasks before executing them
> - Better LLM orchestration code = better use of the Claude API = better outcomes for Anthropic's customers

This isn't asking Anthropic to adopt an external language. It's asking them to formalize what they already built, using a design that's already worked out. The incentive alignment is strong — Anthropic benefits from their users writing better, more efficient LLM code.

**The pitch to OpenAI:**
Same argument. Codex CLI is a task executor. Stratum formalizes the task execution model with types, contracts, and compiler guarantees. OpenAI's users building on the Assistants API and function calling are already doing this informally.

---

## The Recursive Insight

Stratum doesn't just help developers build LLM systems. It improves how LLM coding agents operate.

A Claude Code that understands Stratum can:
- Plan a multi-step task as a `flow` before executing it — static analysis before running
- Classify each step as `infer` (judgment required) or `compute` (deterministic) — execute each optimally
- Apply `ensure` postconditions to its own tool outputs — catch mistakes before propagating them
- Track token budget across the task — know when to stop and ask rather than continuing expensively
- Produce a typed audit trail of the full task — not just a transcript, but a structured trace

This is the recursive play: **Stratum makes LLM coding agents better at building LLM systems, which are themselves better because they use Stratum.**

The value proposition compounds on itself.

---

## Distribution Implications for the Roadmap

The integration paths change the build priority:

### What to build first (unilateral, immediate)

1. **Token audit tool** — `stratum audit <file>`. Works on any codebase. Zero adoption required. Produces a number ("you're wasting X tokens per call") that justifies everything downstream.

2. **Python library** — `pip install stratum`. The reference implementation and primary developer-facing authoring surface. `@infer`, `@contract`, `@flow` decorators. The `.stratum` IR is what this emits internally.

3. **`.stratum` IR spec** — defined in parallel with the Python library. The interchange format between the library, the MCP server, and any future runtime. Not for hand-authoring — for tooling interop.

4. **MCP server** — `stratum-mcp`. Wraps the Python library, exposes tools to Claude Code. Available to any developer today.

### What follows (builds on traction)

5. **TypeScript library** — second ecosystem.

6. **Stratum LSP** — language server for IDE support. Makes `.stratum` files first-class in VS Code, Cursor, etc. — the editors where developers actually work.

7. **Claude Code skill** — `/stratum` slash command that audits the current project and suggests migrations.

### What requires cooperation (pitch with traction)

8. **Native Claude Code integration** — propose to Anthropic after MCP adoption demonstrates value.

9. **Codex / GitHub Copilot integration** — same path with OpenAI/Microsoft.

10. **Model training** — get Stratum patterns into training data so models generate it natively.

---

## The Minimal Viable Integration

The smallest thing that validates the distribution thesis:

```bash
# Developer adds this to their Claude Code config
pip install stratum-mcp
stratum-mcp install   # registers MCP server with Claude Code

# Now Claude Code can:
# - Execute .stratum specs as typed flows
# - Audit any file for token waste
# - Generate .stratum specs from task descriptions
```

If Claude Code users adopt the MCP server and it demonstrably improves their workflows — better outputs, lower token costs, auditable traces — that's the proof of concept for the native integration pitch.

The MCP server is the Trojan horse. It gets Stratum semantics inside Claude Code today, without any permission, without any rewrite. When it works well enough that developers stop writing raw orchestration code and reach for `@infer` instead — with `.stratum` as the invisible IR underneath — the case for native integration makes itself.

---

## Competitive Positioning in the AI Coding Tool Space

| Tool | Current state | Stratum integration |
|---|---|---|
| Claude Code | Informal flow/tool execution | MCP server today; native path via Anthropic |
| Codex CLI | Task execution loop | MCP-equivalent today; native path via OpenAI |
| Cursor / Copilot | Code generation only | LSP + code generation target |
| Devin / SWE-agent | Autonomous agents | `.stratum` as agent spec format |
| n8n / Temporal | Workflow orchestration | `.stratum` as workflow definition format |

The `.stratum` spec format is the unifying artifact. Every tool in this space needs a way to express "a typed, contract-validated sequence of LLM and deterministic steps." Stratum is that format. The tools are the distribution.

---

## What This Means for the Roadmap

The roadmap now has a clear spine:

```
Token auditor  →  Python library (@infer)  →  MCP server  →  traction  →  native integration
                        ↓
               .stratum IR spec (parallel — defines what the library emits)
```

The Python library is the developer-facing surface. The `.stratum` IR spec is defined in parallel — it's what the library emits and what the MCP server validates. Developers never touch the IR directly. Everything else (TypeScript library, Rust core, full compiler) follows from adoption signal.

The MCP server is the wedge — it gets Stratum semantics inside Claude Code without requiring developers to learn a new language, rewrite their codebase, or wait for a compiler. They `pip install stratum`, add one decorator, add the MCP server, and get typed, auditable, token-efficient LLM flows.
