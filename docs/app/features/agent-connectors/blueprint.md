# Agent Connectors: Implementation Blueprint

**Status:** READY TO BUILD
**Updated:** 2026-02-26 — post design review + SDK contract corrections
**Design doc:** [design.md](./design.md)

---

## Corrections Table

All findings from design review + SDK contract verification.

| Source | Design/Blueprint Assumption | Reality | Correction |
|--------|----------------------------|---------|------------|
| Source code | MCP tools can stream output | MCP is request/response (`forge-mcp.js:299–331`) | `collectStream()` helper; return single text blob |
| Source code | `agent-mcp.js` needs `requireSensitiveToken` | stdio MCP has no HTTP request object | No auth in MCP server |
| Source code | `interrupt()` uses `.return()` | SDK has `.interrupt()` abort signal; `.return()` only closes generator, not request | Use `.interrupt()` in `ClaudeSDKConnector` |
| SDK types `SessionCreateData` | `session.create({ model, variant })` | `session.create()` only accepts `{ parentID?, title? }` | Model goes in `session.prompt()`, not `session.create()` |
| SDK types `SessionPromptData` | `model: "openai/gpt-5.2-codex"` string | `model: { providerID: string, modelID: string }` — split object | Use `{ providerID: 'openai', modelID: 'gpt-5.2-codex' }` |
| SDK types `SessionPromptData` | `format: { type: 'json_schema', schema }` field | No `format` field in `SessionPromptData` | Schema mode = prompt-for-JSON: inject schema into prompt text, `JSON.parse()` collected output |
| SDK source `server.ts` | `createOpencode()` is safe to call multiple times | Launches a managed `opencode serve` subprocess on `127.0.0.1`; multiple calls = multiple conflicting servers | Module-level async singleton (promise-based, TOCTOU-safe) |
| SDK source | Event names: `'message'`, `'done'`, `'tool_use'` | Actual events: `message.part.updated`, `session.idle`, `session.error` | Use correct event names |
| SDK source | `client.session.abort()` — name uncertain | Confirmed: `client.session.abort({ path: { id } })` — method exists | Use as specified |
| Design/Blueprint inconsistency | `ClaudeSDKConnector` throws on schema mode; `codex_run` branches for schema | Design says both support `run(prompt, { schema })` | Both connectors use prompt-for-JSON; no branching in MCP tools — always `collectStream()` + optional `JSON.parse()` |
| Pipeline data flow bug | `review` step uses `context: "$.input.blueprint"` | Reviews the spec, not what Claude produced | Wire to execution output; make fix-feedback loop explicit in step intent |
| Concurrency | Singleton connectors assumed safe | Concurrent MCP calls will clobber `#queryIter`/`#sessionId` | Guard `run()` with `isRunning` check; throw if already active |

---

## File Map

```
server/connectors/
  agent-connector.js        NEW     — AgentConnector base class
  opencode-connector.js     NEW     — OpencodeConnector (base, not exposed as MCP tool)
  codex-connector.js        REPLACE — CodexConnector extends OpencodeConnector
  claude-sdk-connector.js   NEW     — ClaudeSDKConnector
server/
  agent-mcp.js              NEW     — MCP server: claude_run + codex_run
  codex-server.js           DELETE
.mcp.json                   EDIT    — add agents entry
package.json                EDIT    — add @opencode-ai/sdk (pinned), remove openai
pipelines/
  review-fix.stratum.yaml   NEW     — first pipeline (Phase C)
```

---

## Phase A — Connector Class Hierarchy

### `server/connectors/agent-connector.js` (NEW)

Base class. JS duck typing — no abstract enforcement, just contract documentation.

```
Pattern ref: forge-mcp.js (structural), agent-server.js:176–195 (async generator consumption)

Class: AgentConnector
Fields:
  #cwd = process.cwd()

Methods:
  run(prompt, opts = {})   → async generator (streaming) OR Promise<string> (API connectors, deferred)
  interrupt()              → void
  get isRunning()          → boolean

Message envelope (same as agent-server.js broadcast format):
  { type: 'system',    subtype: 'init',     agent: string, model: string }
  { type: 'assistant', content: string }
  { type: 'tool_use',  tool: string, input: object }
  { type: 'system',    subtype: 'complete', agent: string }
  { type: 'error',     message: string }
```

No imports. Pure base with throw-not-implemented stubs.

---

### `server/connectors/claude-sdk-connector.js` (NEW)

Pattern: `agent-server.js:153–195` — extract `query()` call and `for await` loop verbatim.

```
Import: { query } from '@anthropic-ai/claude-agent-sdk'
Import: { HOOK_OPTIONS } from '../agent-hooks.js'

Class: ClaudeSDKConnector extends AgentConnector
Private fields:
  #model     = process.env.CLAUDE_MODEL || 'claude-sonnet-4-6'
  #queryIter = null

Constructor({ model, cwd } = {}):
  super(); store overrides

run(prompt, { model, cwd, schema } = {}):
  — GUARD: if isRunning → throw Error('ClaudeSDKConnector already has an active session')
  — resolve effectiveModel = model ?? #model
  — if schema: inject schema into prompt:
      prompt = `${prompt}\n\nRespond with valid JSON only, matching this schema:\n${JSON.stringify(schema, null, 2)}`
  — yield { type: 'system', subtype: 'init', agent: 'claude', model: effectiveModel }
  — queryIter = query({ prompt, options: {
        cwd: cwd ?? #cwd,
        model: effectiveModel,
        permissionMode: 'acceptEdits',
        settingSources: ['project'],
        tools: { type: 'preset', preset: 'claude_code' },
        hooks: HOOK_OPTIONS,
      }})
  — #queryIter = queryIter
  — for await (const msg of queryIter): yield msg
  — yield { type: 'system', subtype: 'complete', agent: 'claude' }
  — finally: #queryIter = null

interrupt():
  — if #queryIter: call #queryIter.interrupt()   ← SDK abort signal, NOT .return()
  — #queryIter = null

get isRunning():
  — return #queryIter !== null
```

**Key detail:** `.interrupt()` is the SDK abort method (see `agent-server.js:132`). `.return()` only closes the JS generator iterator — it does not cancel the underlying request, leaking a running session.

**Schema mode:** Prompt-for-JSON injection. The MCP tool's `collectStream()` collects all output; the MCP handler then `JSON.parse()`s it when schema was provided. The connector itself always yields text — it does not parse internally.

---

### `server/connectors/opencode-connector.js` (NEW)

Base for all OpenCode-backed connectors. **Not exposed as MCP tool.**

**Singleton lifecycle:** `createOpencode()` launches a managed `opencode serve` subprocess. Module-level singleton is required. Multiple instances = multiple conflicting servers on `127.0.0.1`.

```
Import: { createOpencode } from '@opencode-ai/sdk'

// Module-level singleton — one opencode server per process
let _connectPromise = null
async function getClient() {
  if (!_connectPromise) {
    _connectPromise = createOpencode().then(({ client }) => client)
  }
  return _connectPromise   // all callers await same promise — TOCTOU-safe
}

Class: OpencodeConnector extends AgentConnector
Private fields:
  #providerID = 'openai'                      — overridable
  #modelID    = process.env.OPENCODE_MODEL || 'gpt-5.2-codex'
  #sessionId  = null

Constructor({ providerID, modelID, cwd } = {}):
  super(); store overrides

run(prompt, { providerID, modelID, schema, cwd } = {}):
  — GUARD: if isRunning → throw Error('OpencodeConnector already has an active session')
  — resolve effectiveProvider = providerID ?? #providerID
  — resolve effectiveModel    = modelID ?? #modelID
  — if schema: inject schema into prompt:
      prompt = `${prompt}\n\nRespond with valid JSON only, matching this schema:\n${JSON.stringify(schema, null, 2)}`
  — client = await getClient()
  — session = await client.session.create({ title: `forge-${Date.now()}` })
      ↑ session.create only accepts { parentID?, title? } — NO model here
  — #sessionId = session.id
  — yield { type: 'system', subtype: 'init', agent: 'opencode', model: effectiveModel }
  — send prompt:
      await client.session.prompt({
        path: { id: #sessionId },
        body: {
          parts: [{ type: 'text', text: prompt }],
          model: { providerID: effectiveProvider, modelID: effectiveModel },
        },
      })
      ↑ model is { providerID, modelID } object — NOT a string
      ↑ NO format/variant field in SessionPromptData
  — subscribe to events:
      client.event.subscribe((event) => {
        if (event.type === 'message.part.updated') → yield { type: 'assistant', content: event.part.content }
        if (event.type === 'session.idle')         → yield { type: 'system', subtype: 'complete', agent: 'opencode' }; resolve
        if (event.type === 'session.error')        → yield { type: 'error', message: event.error }; resolve
      })
  — await completion (promise resolved by idle/error event)
  — finally: #sessionId = null

interrupt():
  — if #sessionId:
      client = await getClient()
      await client.session.abort({ path: { id: #sessionId } })
      #sessionId = null

get isRunning():
  — return #sessionId !== null
```

**event.subscribe() note:** The subscription returns an unsubscribe function. Store it and call it in `finally` to avoid leaking listeners.

**Schema mode:** Prompt-for-JSON, same as `ClaudeSDKConnector`. No native `format` field. The connector always yields text chunks. `JSON.parse()` happens in the MCP tool handler, not here.

**Variant:** Dropped. `SessionPromptData.model` accepts `{ providerID, modelID }` only. If variants map to distinct model IDs in the OpenCode config (e.g., via `opencode-openai-codex-auth` model presets), they are expressed as `modelID` values, not a separate field.

---

### `server/connectors/codex-connector.js` (REPLACE)

Subclass of `OpencodeConnector`. Constrains to Codex model IDs. Auth assumed via `opencode auth login`.

```
Import: { OpencodeConnector } from './opencode-connector.js'

// Codex model IDs as known to OpenCode (via opencode-openai-codex-auth)
// providerID is always 'openai' for CodexConnector
const CODEX_MODEL_IDS = new Set([
  'gpt-5.2-codex',
  'gpt-5.1-codex-max',
  'gpt-5.1-codex',
  'gpt-5.1-codex-mini',
])

Class: CodexConnector extends OpencodeConnector
Constructor({ modelID, cwd } = {}):
  — modelID = modelID ?? process.env.CODEX_MODEL ?? 'gpt-5.2-codex'
  — if !CODEX_MODEL_IDS.has(modelID) → throw Error(`Unknown Codex model: ${modelID}. Valid: ${[...CODEX_MODEL_IDS]}`)
  — super({ providerID: 'openai', modelID, cwd })

run(prompt, opts = {}):
  — if opts.modelID && !CODEX_MODEL_IDS.has(opts.modelID):
      throw Error(`Unknown Codex model: ${opts.modelID}`)
  — return super.run(prompt, { ...opts, providerID: 'openai' })
```

No other overrides. Auth is a setup precondition (`opencode auth login`), not a runtime check.

---

## Phase B — MCP Server

### `server/agent-mcp.js` (NEW)

Pattern: `server/forge-mcp.js` exactly. Same imports, Server + StdioServerTransport, same handler structure, same return format.

**Unified schema handling:** Both `claude_run` and `codex_run` always call `collectStream()` → get text → optionally `JSON.parse()` if `args.schema` was provided. No branching between streaming and structured modes at the MCP layer.

```
Import: Server, StdioServerTransport, CallToolRequestSchema, ListToolsRequestSchema from @modelcontextprotocol/sdk
Import: path, fileURLToPath from node:*
Import: ClaudeSDKConnector from './connectors/claude-sdk-connector.js'
Import: CodexConnector from './connectors/codex-connector.js'

const PROJECT_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')

// Singletons — one connector per process
const claude = new ClaudeSDKConnector({ cwd: PROJECT_ROOT })
const codex  = new CodexConnector({ cwd: PROJECT_ROOT })

// Collect all assistant text from an async generator
// Throws on error messages; returns joined content string
async function collectStream(gen) {
  const parts = []
  for await (const msg of gen) {
    if (msg.type === 'error') throw new Error(msg.message)
    if (msg.type === 'assistant') parts.push(msg.content)
  }
  return parts.join('')
}

TOOLS array — 2 entries:
  claude_run:
    description: 'Run a prompt via Claude Code (Anthropic Agent SDK). Agentic, full tool use. Returns text output.'
    inputSchema.properties: prompt (required), model, cwd
    No schema property — Claude output is always text; parse it yourself if needed

  codex_run:
    description: 'Run a prompt via OpenAI Codex (via OpenCode). Agentic, full tool use. Returns text output, or JSON string if schema provided.'
    inputSchema.properties: prompt (required), schema (object), modelID, cwd

CallToolRequestSchema handler (async):
  case 'claude_run':
    output = await collectStream(claude.run(args.prompt, { model: args.model, cwd: args.cwd }))
    return { content: [{ type: 'text', text: output }] }

  case 'codex_run':
    output = await collectStream(codex.run(args.prompt, {
      schema: args.schema,     ← injected into prompt by connector; output is still text
      modelID: args.modelID,
      cwd: args.cwd,
    }))
    if (args.schema) {
      parsed = JSON.parse(output)   ← parse here, after full text is collected
      return { content: [{ type: 'text', text: JSON.stringify(parsed, null, 2) }] }
    }
    return { content: [{ type: 'text', text: output }] }

Startup: same as forge-mcp.js:337–338 — StdioServerTransport, await server.connect(transport)
```

Token budget: 2 tools, concise descriptions ≈ 130 tokens. Within 2,000-token cap.

---

### `.mcp.json` (EDIT)

Add after the `"forge"` entry:
```json
"agents": {
  "command": "node",
  "args": ["server/agent-mcp.js"],
  "description": "Agent connectors — claude_run (Claude SDK) and codex_run (Codex via OpenCode)"
}
```

---

### `package.json` (EDIT)

```
Add:    "@opencode-ai/sdk": "<pin to installed version immediately after npm install>"
Remove: "openai": "^4.98.0"   — no longer used once old codex-connector.js is deleted
```

Do not use `"latest"`. After `npm install @opencode-ai/sdk`, pin to the exact version installed. The SDK is pre-1.0 and event names / session API are the specific things that change between minors.

---

### `server/codex-server.js` (DELETE)

No content to migrate. Replaced entirely by connector classes + agent-mcp.js.

---

## Phase C — Stratum Pipeline

### `pipelines/review-fix.stratum.yaml` (NEW)

The fix-feedback loop is encoded in a single `fix_and_review` step. On `ensure_failed`, Stratum returns the step to Claude Code, which sees the previous findings and the intent instructs it to fix them before re-reviewing. This is how findings route back into the fix pass — the retry budget is the iteration cap.

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
    intent: >
      Call the claude_run MCP tool with the task prompt to implement the work.
      Return { summary: "<description of what was done>", findings: [] }.
    input:
      task: { type: string }
    output: ExecuteResult
    retries: 1

  fix_and_review:
    mode: compute
    intent: >
      Implement one full fix-then-review cycle:
      1. If this is a retry (previous ensure failed with findings), call claude_run
         with the task and the previous findings to fix the issues first.
      2. Call codex_run to review the current state of the code. Pass schema so
         the output is structured JSON with clean, summary, and findings fields.
         The review prompt should reference the blueprint and check correctness,
         patterns, and integration.
      3. Return the parsed codex_run result as ReviewResult.
      On retry: fix first, then review. Do not re-review without fixing.
    input:
      task:             { type: string }
      execute_summary:  { type: string }
      blueprint:        { type: string }
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

**Why single step for fix+review:** Stratum's retry mechanism returns the step to Claude Code with the previous result visible. The intent tells Claude Code to fix the findings before re-reviewing. This is structurally simpler than two separate steps and ensures findings always feed into the fix pass before re-review runs.

---

## Build Order

1. Delete `server/codex-server.js`
2. Write `server/connectors/agent-connector.js`
3. Write `server/connectors/claude-sdk-connector.js`
4. `npm install @opencode-ai/sdk` — pin exact version in `package.json`; remove `openai`
5. Inspect `node_modules/@opencode-ai/sdk/` to confirm:
   - `message.part.updated` event field path for content (`event.part.content`?)
   - `session.idle` as the completion signal
   - `event.subscribe()` returns unsubscribe function
6. Write `server/connectors/opencode-connector.js` using confirmed field names
7. Replace `server/connectors/codex-connector.js`
8. `node --check` all four connector files
9. Write `server/agent-mcp.js`
10. Edit `.mcp.json`
11. Smoke test: `echo '{"jsonrpc":"2.0","method":"tools/list","id":1}' | node server/agent-mcp.js`
12. Write `pipelines/review-fix.stratum.yaml`
