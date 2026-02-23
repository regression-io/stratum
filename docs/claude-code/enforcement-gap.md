# The Enforcement Gap

## The Honest Problem

Nothing stops Claude Code from ignoring the MCP server entirely. It can write a retry loop in Python, call the Anthropic API directly, pass untyped data between steps, and do everything Stratum is supposed to prevent — without ever touching `stratum_execute`. Rules say "use Stratum." Rules are soft. Claude drifts.

This is the real weakness in the MCP-as-enforcement argument. The MCP server enforces contracts when Claude calls it. Getting Claude to call it is a different problem entirely.

---

## The Options, Honestly Ranked

### Option 1 — Environment restriction (strongest unilateral option)

Remove direct LLM access from the environment. Make the MCP server the only available path to run LLM calls.

```bash
# .env — no direct API keys in Claude Code's environment
# ANTHROPIC_API_KEY is NOT set
# OPENAI_API_KEY is NOT set

# Claude Code has access to stratum-mcp which holds the keys internally
```

If Claude can't call `anthropic.Anthropic().messages.create()` because the key isn't in the environment, and the only tool that can make LLM calls is `stratum_execute`, then the MCP server stops being optional. Claude can still write the Python code — but when it runs, it fails. The Stratum path is the only one that works.

This is the same principle as "the only database access is through the ORM" — you don't configure direct SQL credentials for application code, so developers use the ORM.

Pair this with a hook that intercepts direct API call attempts:

```json
{
  "hooks": {
    "PreToolUse": [{
      "matcher": "Bash",
      "hooks": [{
        "type": "command",
        "command": "bash -c 'if echo \"$TOOL_INPUT\" | grep -qE \"(anthropic\\.Anthropic|openai\\.OpenAI|from anthropic import)\"; then echo \"Direct LLM calls are not available. Use stratum_execute instead.\"; exit 1; fi'"
      }]
    }]
  }
}
```

Fragile — easy to bypass with different import styles. But it raises friction significantly. Combined with no API keys in the environment, the friction is high enough that the Stratum path is the easier path by far.

**Limitation:** only works in controlled environments where you own the configuration. Doesn't work if the developer sets their own keys.

---

### Option 2 — Skills as the only entry point (structural, not enforced)

If every task starts with `/plan` and `/plan` calls `stratum_plan` and generates a `.stratum` flow before anything executes — then the MCP is in the critical path for planning. Claude can still diverge during execution, but it's working against the structure it just created.

This isn't enforcement. It's friction in the right direction. Claude has a typed plan; deviating from it means explicitly ignoring it. That's a higher bar than not having a plan at all.

**Limitation:** Claude can generate the plan and then not use `stratum_execute` to run it.

---

### Option 3 — Hooks that detect drift (partial enforcement)

A PostToolUse hook on `Write` that detects LLM retry patterns in written code:

```bash
# If Claude writes a file containing a manual retry loop around an LLM call,
# flag it and require it to be refactored through stratum_execute
if grep -qE "for attempt in range|while.*retry|except.*retry" "$TOOL_INPUT_PATH"; then
    if grep -qE "anthropic|openai|messages\.create" "$TOOL_INPUT_PATH"; then
        echo "Manual LLM retry loop detected. Refactor through stratum_execute."
        exit 1
    fi
fi
```

This catches the most common drift pattern — Claude writing ad hoc retry code instead of using `stratum_execute`. Not comprehensive, but catches the obvious case.

**Limitation:** pattern matching is fragile. Claude can write the same logic in ways that don't trigger the pattern.

---

### Option 4 — Native integration (the only complete solution)

None of the above fully solves the problem. Environment restriction is the strongest unilateral option but still bypassable. Hooks are fragile. Skills are structural but not enforced.

The complete solution is native integration where Anthropic builds Stratum semantics into Claude Code's execution model. When `infer` is a first-class construct in the language Claude Code speaks, there is no other path. You can't bypass the contract validation because the compiler doesn't emit code without it.

This is the language argument made concrete: a language keyword is categorically different from an MCP server because there's no alternate path. `infer classifySentiment(...)` goes through the Stratum runtime by definition. `await anthropic.messages.create(...)` doesn't.

---

## What This Means for the Architecture

The MCP server is not a prison. It's a wedge.

It provides genuine enforcement for the workflows that flow through it. The question "what forces Claude to use it?" has a real but incomplete answer: environment restriction + hooks + skills + rules get you most of the way there in a controlled environment. In an uncontrolled environment, you're relying on the developer's intent — which is actually the real scenario. A developer who installs the MCP server and writes the rules is opting into the constraints. They want Claude to use it.

The enforcement gap matters most when Claude drifts accidentally — not when the developer is trying to circumvent it. For accidental drift, rules + hooks + skills + environment restriction is genuinely sufficient. Claude doesn't go around the MCP server on purpose; it goes around it when the path of least resistance leads elsewhere. The configuration is designed to make the Stratum path the easier path.

For deliberate circumvention — a developer who wants to bypass the constraints — nothing short of native integration stops them. But that's a different problem.

---

## The Revised Honest Framing

```
                          Enforcement strength
                          ───────────────────▶
Rules alone          │░░░░░░░░░░░░░░░░░░░░░░│
Rules + skills       │██░░░░░░░░░░░░░░░░░░░░│
+ hooks              │████░░░░░░░░░░░░░░░░░░│
+ env restriction    │███████░░░░░░░░░░░░░░░│  ← strongest unilateral option
Native integration   │██████████████████████│  ← complete enforcement
```

The MCP strategy is viable for the target scenario: a developer who wants Stratum-aligned behavior and needs the system to stay on track when Claude drifts. It's not viable as a security boundary or as a guarantee against a developer who wants to bypass it.

Native integration is the destination. The MCP server is the proof of concept that earns the pitch for native integration. Its value isn't that it fully enforces Stratum — it's that it demonstrates what full enforcement would produce.

---

## Updated Build Priorities

Given this gap, the build priority shifts slightly:

1. **Token auditor** — measures drift after the fact. Shows what happened.
2. **Environment restriction tooling** — `stratum init` that sets up the no-direct-API-key environment correctly
3. **The drift detection hook** — catches the most common bypass pattern
4. **MCP server** — enforcement where it's used
5. **Native integration pitch** — made with evidence from the above

The auditor and drift detection turn "Claude went around Stratum" from an invisible problem into a visible one. Once it's visible, it's fixable. Once fixing it repeatedly demonstrates value, the case for native integration makes itself.
