# Agent Connectors: Design

**Status:** DESIGN — decisions captured, not yet implemented
**Date:** 2026-02-26

## Related Documents

- [Connectors Architecture](../../connectors.md) ← this doc refines
- [MCP Connector Design](../mcp-connector/design.md) ← compose-mcp.js patterns adopted here
- [Lifecycle Engine Roadmap](../../plans/2026-02-15-lifecycle-engine-roadmap.md) ← Layer 7 (Agent Abstraction)
- [Bootstrap Roadmap (CLAUDE.md)](../../../CLAUDE.md) ← Phase 4.5 items 18a–18h, Phase 7 items 27–28
- [Architecture Foundation Plan](../../plans/2026-02-26-architecture-foundation-plan.md) ← implementation steps for this design
- [Feature-Dev v2 Design](../feature-dev-v2/design.md) ← ralph loop context

---

## Context

During a design session on 2026-02-26, we started building a Codex connector by adding a `codex-server.js` (HTTP/SSE server) alongside the existing `agent-server.js`. After review, this approach violated three principles that should govern the entire connector layer. This document records those principles as decisions and specifies the correct architecture.

The existing `server/codex-server.js` is **to be deleted**. The existing `server/connectors/codex-connector.js` is **to be replaced** per the class hierarchy in Decision 1.

---

## Design Principles

Three constraints that govern every decision below:

1. **UI is orthogonal to process.** The UI (React app, VisionServer SSE) must never connect directly to a connector. Connectors are not HTTP servers. The UI observes loop state and session events — both of which are already handled by VisionServer and `loop-state.json`. Adding new connectors adds zero UI surface.

2. **Process is separately definable from connectors.** Review-fix loops, phase gates, discovery flows — none of this logic lives in connector code or in a server. Process is declared as a Stratum pipeline (`.stratum.yaml`). Connectors supply capabilities; pipelines compose them.

3. **Connectors are generic.** A connector wraps what an agent can do, not what a specific process needs. There is no `review()` method, no `execute()` method. There is `run(prompt, opts)`. The caller decides output format. Stratum pipelines decide what to do with the output.

---

## Decision 1: Connector Class Hierarchy

Three tiers:

```
AgentConnector          (interface / base class)
├── ClaudeSDKConnector  (concrete — exposed as MCP tool)
├── OpencodeConnector   (concrete base — NOT exposed as MCP tool, foundation for future models)
│   └── CodexConnector  (subclass — exposed as MCP tool, locked to Codex via opencode-openai-codex-auth)
└── ...deferred API connectors
```

**`ClaudeSDKConnector`** — wraps `@anthropic-ai/claude-agent-sdk` `query()`. All Anthropic model usage goes through this exclusively. Not usable via OpenCode.

**`OpencodeConnector`** — wraps `@opencode-ai/sdk` (`sst/opencode`). Model-agnostic base for any non-Anthropic agent running through OpenCode. **Not exposed as an MCP tool yet** — it is the foundation that future model-specific subclasses extend. Uses a module-level async singleton for `createOpencode()` — the SDK launches a managed `opencode serve` subprocess; multiple instantiations would conflict on `127.0.0.1`. Model is passed to `session.prompt()` as `{ providerID, modelID }` (not to `session.create()`, which only accepts `{ parentID?, title? }`).

**`CodexConnector extends OpencodeConnector`** — constrains `OpencodeConnector` to Codex models only, authenticated via the `opencode-openai-codex-auth` plugin (ChatGPT Plus/Pro/Business subscription, OAuth). This is the only OpenCode-based connector exposed now.

Supported Codex models (via `opencode-openai-codex-auth`):

| Model | Variants |
|-------|----------|
| `openai/gpt-5.2-codex` | low / medium / high / xhigh |
| `openai/gpt-5.1-codex-max` | low / medium / high / xhigh |
| `openai/gpt-5.1-codex` | low / medium / high |
| `openai/gpt-5.1-codex-mini` | medium / high |

Default model ID: `gpt-5.2-codex`. Configurable via `CODEX_MODEL` (modelID). Variant selection, if used, is handled by OpenCode/provider config rather than connector call parameters.

**Auth: ChatGPT subscription, not an API key.** Setup is a one-time operation:
```bash
npx -y opencode-openai-codex-auth@latest   # install plugin + config
opencode auth login                         # OAuth browser flow
```
The connector assumes auth is already established. Token refresh is handled automatically by OpenCode.

**Deferred (interface accommodates, not implemented):**

| Connector | Transport | Deferred reason |
|-----------|-----------|-----------------|
| `AnthropicAPIConnector` | `@anthropic-ai/sdk` Messages API | Not needed until stateless inference use cases arise |
| `OpenAIAPIConnector` | `openai` npm chat completions | Not needed until stateless inference use cases arise |
| Other `OpencodeConnector` subclasses | `@opencode-ai/sdk` + provider auth | When non-Codex OpenCode models are needed |

---

## Decision 2: The Connector Interface

```js
class AgentConnector {
  /**
   * Run a prompt against the agent.
   *
   * Streaming mode (default): yields typed message objects.
   *   { type: 'assistant', content: string }
   *   { type: 'tool_use', tool: string, input: object }
   *   { type: 'system', subtype: 'init' | 'complete' }
   *   { type: 'error', message: string }
   *
   * Schema mode (schema provided): connector still yields text output.
   *   Connector injects schema instructions into the prompt; caller parses.
   *
   * @param {string} prompt
   * @param {object} [opts]
   * @param {object}   [opts.schema]   — JSON Schema → structured output mode
   * @param {string}   [opts.modelID]    — override model for this call
   * @param {string}   [opts.providerID] — provider ID (OpenCode subclasses only)
   * @param {string}   [opts.cwd]      — working directory
   * @param {string[]} [opts.tools]    — restrict available tools
   * @returns {AsyncGenerator|Promise<string>}
   */
  run(prompt, opts = {}) { throw new Error('not implemented'); }

  /** Kill active session or in-flight request. */
  interrupt() {}

  /** Whether a run is currently active. */
  get isRunning() { return false; }
}
```

`CodexConnector` validates that `opts.modelID`, if provided, is within the allowed Codex model list and rejects anything else at construction time.

Structured output mechanism per connector:

| Connector | Streaming | Structured output |
|-----------|-----------|-------------------|
| `ClaudeSDKConnector` | Async generator from `query()` | Prompt-for-JSON: schema injected into prompt text; caller parses collected output |
| `OpencodeConnector` / `CodexConnector` | `client.event.subscribe()` SSE (`message.part.updated`, `session.idle`, `session.error`) | Prompt-for-JSON: `SessionPromptData` has no `format` field; schema injected into prompt text |
| `AnthropicAPIConnector` *(deferred)* | Streaming Messages API | Tool_use with input_schema |
| `OpenAIAPIConnector` *(deferred)* | Promise | `response_format: json_schema` |

**Schema mode contract:** Both in-scope connectors use prompt-for-JSON. The connector injects the schema into the prompt and always yields text. `JSON.parse()` of the collected output happens at the MCP tool layer (`agent-mcp.js`), not inside the connector. This keeps the connector return type uniform (always text) and the schema parsing in one place.

---

## Decision 3: MCP Tools — Two Now, More Deferred

Connectors are exposed as MCP tools in a new `server/agent-mcp.js` (stdio transport, same pattern as `compose-mcp.js`). `OpencodeConnector` itself is **not** exposed — only named subclasses ship as tools.

**In scope now:**

| MCP Tool | Connector | What it does |
|----------|-----------|-------------|
| `claude_run` | `ClaudeSDKConnector` | Agentic Claude Code session, full tool use, streaming |
| `codex_run` | `CodexConnector` | Agentic Codex session (gpt-5.2-codex default), streaming |

**Deferred:**

| MCP Tool | Connector | Deferred reason |
|----------|-----------|-----------------|
| `opencode_run` | `OpencodeConnector` | Not exposed until a concrete non-Codex use case exists |
| `claude_infer` | `AnthropicAPIConnector` | Stateless inference use case not yet needed |
| `openai_infer` | `OpenAIAPIConnector` | Stateless inference use case not yet needed |

Each tool accepts `prompt`, optionally `schema` (structured output), `modelID` (or connector-specific model override), and `cwd`.

Token budget: 2 tools at ~50–80 tokens each = ~160 tokens. Well within the 2,000-token soft cap.

---

## Decision 4: Process Lives in Stratum Pipelines

Review-fix loops, phase gates, and any other multi-step process are `.stratum.yaml` files in a new `pipelines/` directory at project root. Stratum is the execution harness. Claude Code calls Stratum tools; Stratum steps call MCP tools.

Example review-fix pipeline using the two in-scope tools:

```yaml
version: "0.1"
contracts:
  ExecuteResult:
    summary:  { type: string }
    findings: { type: array }
  ReviewResult:
    clean:    { type: boolean }
    summary:  { type: string }
    findings: { type: array }

functions:
  execute_task:
    mode: compute
    intent: "Call claude_run MCP tool with the task prompt. Return { summary, findings: [] }."
    input:
      task: { type: string }
    output: ExecuteResult
    retries: 1

  fix_and_review:
    mode: compute
    intent: >
      Implement one full fix-then-review cycle:
      1. If this is a retry (previous ensure failed with findings), call claude_run
         with the task and previous findings to fix them first.
      2. Call codex_run with a review prompt and a JSON schema for ReviewResult
         to get structured output. Review against the blueprint for correctness,
         patterns, and integration.
      3. Return the parsed codex_run result as ReviewResult.
      On retry: fix first, then review. Never re-review without fixing first.
    input:
      task:            { type: string }
      execute_summary: { type: string }
      blueprint:       { type: string }
    output: ReviewResult
    ensure:
      - "result.clean == true"
    retries: 10

flows:
  review_fix:
    input:
      task:      { type: string }
      blueprint: { type: string }
    output: ReviewResult
    steps:
      - id: execute
        function: execute_task
        inputs:
          task: "$.input.task"

      - id: review
        function: fix_and_review
        inputs:
          task:            "$.input.task"
          execute_summary: "$.steps.execute.output.summary"
          blueprint:       "$.input.blueprint"
        depends_on: [execute]
```

On `ensure_failed`, Stratum returns the step to Claude Code with the previous findings visible. The step's intent instructs it to fix the findings (via `claude_run`) before re-reviewing (via `codex_run`). Fix and review are a single `fix_and_review` step — not split across two — ensuring findings always feed back into a fix pass before re-review runs. The retry budget (`retries: 10`) is the iteration cap, replacing the max-iterations safety valve from `feature-dev-v2/design.md` Decision 3.

Pipelines live in `pipelines/` and are versioned in git.

---

## Decision 5: What Changes to Existing Files

| File | Action | Reason |
|------|--------|--------|
| `server/codex-server.js` | **Delete** | Wrong abstraction — HTTP server for a connector |
| `server/connectors/codex-connector.js` | **Replace** with `opencode-connector.js` + `codex-connector.js` | Reshape into base + subclass per Decision 1 |
| `server/agent-server.js` | **No change** | Still the right home for the Claude SDK interactive session |
| `server/compose-mcp.js` | **No change** | Tracker tools stay separate; agent tools get their own MCP server |
| `server/agent-mcp.js` | **Create** | New MCP server exposing `claude_run` and `codex_run` |
| `pipelines/` | **Create** | Home for Stratum pipeline specs |
| `.mcp.json` | **Extend** | Register `agent-mcp.js` alongside `compose-mcp.js` |

`agent-server.js` stays because it serves the interactive UI session. That is a UI concern — a human watching an agent run live. The MCP tools serve autonomous pipeline execution, a different concern.

---

## Decision 6: Agentic vs API Connector Contracts

**Agentic connectors** (`ClaudeSDKConnector`, `OpencodeConnector` and subclasses) — in scope now:
- Maintain session state, run tool use loops, stream output
- `run()` returns an async generator
- `interrupt()` kills the active session

**API connectors** (`AnthropicAPIConnector`, `OpenAIAPIConnector`) — deferred:
- Stateless: prompt in, response out. No tool loop, no session state.
- `run()` returns a promise
- `interrupt()` cancels the in-flight HTTP request

The interface is identical. The async generator vs promise distinction is handled by the caller (`for await` vs `await`). No special casing in callers or MCP tools.

---

## Decision 7: Configuration

| Connector | Auth | Default model | Env overrides | Status |
|-----------|------|---------------|---------------|--------|
| `ClaudeSDKConnector` | Claude Code session | `claude-sonnet-4-6` | `CLAUDE_MODEL` | In scope |
| `CodexConnector` | ChatGPT OAuth via `opencode-openai-codex-auth` | `providerID: openai`, `modelID: gpt-5.2-codex` | `CODEX_MODEL` (modelID only) | In scope |
| `OpencodeConnector` | Provider-specific via OpenCode | — | `OPENCODE_MODEL` (modelID) | Base only, not exposed |
| `AnthropicAPIConnector` | `ANTHROPIC_API_KEY` | `claude-haiku-4-5-20251001` | `ANTHROPIC_INFER_MODEL` | Deferred |
| `OpenAIAPIConnector` | `OPENAI_API_KEY` | `o4-mini` | `OPENAI_INFER_MODEL` | Deferred |

---

## Phase Plan

### Phase A — Connector Class Hierarchy
- Define `AgentConnector` base (JS duck typing, not abstract class)
- Implement `ClaudeSDKConnector` wrapping `query()` from `@anthropic-ai/claude-agent-sdk`
- Implement `OpencodeConnector` wrapping `@opencode-ai/sdk`
- Implement `CodexConnector extends OpencodeConnector` locked to Codex model list
- Delete `server/codex-server.js`
- Acceptance:
  - [ ] `connector.run(prompt)` yields typed messages for both `ClaudeSDKConnector` and `CodexConnector`
  - [ ] `connector.run(prompt, { schema })` yields text with JSON schema injected into prompt (parsing happens in MCP layer, not connector)
  - [ ] `CodexConnector` rejects non-Codex `modelID` values at construction and at `run()` call time
  - [ ] `connector.interrupt()` stops the active run cleanly (`.interrupt()` for Claude SDK; `session.abort()` for OpenCode)

### Phase B — MCP Tool Registration
- Create `server/agent-mcp.js` (stdio transport)
- Register `claude_run` and `codex_run`
- Extend `.mcp.json`
- Acceptance:
  - [ ] Claude Code can call both tools from within a session
  - [ ] Tool definitions total < 200 tokens combined

### Phase C — First Stratum Pipeline
- Create `pipelines/review-fix.stratum.yaml`
- Run end-to-end via `stratum_plan` + `stratum_step_done`
- Acceptance:
  - [ ] Pipeline completes on a real feature
  - [ ] `stratum_audit` trace shows review+fix iterations
  - [ ] `ensure: result.clean == true` correctly gates completion

### Phase D — Future Connectors (Deferred)
- Additional `OpencodeConnector` subclasses as non-Codex OpenCode use cases arise
- `opencode_run` MCP tool exposed when a concrete use case justifies it
- API connectors (`AnthropicAPIConnector`, `OpenAIAPIConnector`) when stateless inference is needed
- No interface changes to existing connectors, tools, or pipelines required

---

## What This Is Not

- **Not a replacement for `agent-server.js`.** The interactive session server stays. This feature is about autonomous pipeline execution.
- **Not a multi-tenant agent platform.** Single developer, single machine.
- **Not a new UI surface.** Zero new UI components required.
