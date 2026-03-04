# Architecture Foundation Plan

**Status:** PLANNED
**Date:** 2026-02-26
**Phase:** 4.5 (between Connectors and Standalone)

## Related Documents

- [Agent Connectors Design](../features/agent-connectors/design.md) — the feature this phase implements
- [Agent Connectors Blueprint](../features/agent-connectors/blueprint.md) — implementation details
- [Bootstrap Roadmap (CLAUDE.md)](../../CLAUDE.md) — Phase 4.5, items 18a–18h
- [Lifecycle Engine Roadmap](2026-02-15-lifecycle-engine-roadmap.md) — Phase 4.5 feeds into Layer 7

---

## Goal

Deliver the agent connector layer (ClaudeSDKConnector + CodexConnector) as MCP tools callable
from Claude Code, with Stratum as the process harness. No new UI surface. Clean server
modularization. Verified end-to-end.

**Total estimate:** 17–27 days across 8 sequential steps.

---

## Steps

### 18a — Architecture Alignment (2–3 days)

Delete wrong abstractions and reshape connectors per the class hierarchy in the design doc.

- [ ] Delete `server/codex-server.js`
- [ ] Delete old `server/connectors/codex-connector.js`
- [ ] Create `server/connectors/agent-connector.js` (base interface — duck typing, JS)
- [ ] Create `server/connectors/claude-sdk-connector.js` (wraps `@anthropic-ai/claude-agent-sdk` `query()`)
- [ ] Create `server/connectors/opencode-connector.js` (module-level `_connectPromise` singleton, wraps `@opencode-ai/sdk`)
- [ ] Create `server/connectors/codex-connector.js` (extends OpencodeConnector, locks to CODEX_MODEL_IDS, validates `modelID` at construction and at `run()`)
- [ ] `connector.run(prompt)` yields typed messages for ClaudeSDKConnector and CodexConnector
- [ ] `connector.run(prompt, { schema })` injects schema into prompt text; connector yields text (parsing deferred to MCP layer)
- [ ] `CodexConnector` rejects non-Codex `modelID` at construction time
- [ ] `connector.interrupt()` calls `.interrupt()` (Claude SDK) / `session.abort({ path: { id } })` (OpenCode)

Files (new): `server/connectors/agent-connector.js`, `server/connectors/claude-sdk-connector.js`, `server/connectors/opencode-connector.js`, `server/connectors/codex-connector.js`
Files (delete): `server/codex-server.js`, old `server/connectors/codex-connector.js`

### 18b — Integration Surface Stabilization (2–4 days)

Expose connectors as MCP tools. Zero HTTP/SSE surface added.

- [ ] Create `server/agent-mcp.js` (stdio transport, same pattern as `compose-mcp.js`)
- [ ] Register `claude_run` tool: accepts `prompt`, `schema?`, `modelID?`, `cwd?`; streams via `collectStream()` before returning
- [ ] Register `codex_run` tool: same signature; delegates to `CodexConnector`
- [ ] Both tool definitions total < 200 tokens combined
- [ ] Extend `.mcp.json` with `"agents"` entry pointing to `server/agent-mcp.js`
- [ ] Claude Code can call both tools from within a session
- [ ] `JSON.parse()` of schema-mode output happens in `agent-mcp.js`, not in connectors

Files (new): `server/agent-mcp.js`
Files (edit): `.mcp.json`

### 18c — Stratum Externalization (3–5 days)

Stratum is the process harness. The fix-feedback loop lives in pipeline YAML, not in connector code.

- [ ] Create `pipelines/` directory at project root
- [ ] Create `pipelines/review-fix.stratum.yaml` per design doc Decision 4
- [ ] Pipeline uses single `fix_and_review` step (not split fix + review) so findings always feed back before re-review
- [ ] `retries: 10` is the iteration cap
- [ ] Run end-to-end via `stratum_plan` + `stratum_step_done` on a real feature
- [ ] `stratum_audit` trace shows review+fix iterations
- [ ] `ensure: result.clean == true` correctly gates completion

Files (new): `pipelines/review-fix.stratum.yaml`

### 18d — UI Decoupling (1–2 days)

Confirm zero new UI surface was introduced. Agent connector activity flows through existing VisionServer SSE.

- [ ] No new React components for connector output
- [ ] No new WebSocket or HTTP endpoints on the UI side
- [ ] Confirm `loop-state.json` / VisionServer SSE remain the sole UI channel for agent activity
- [ ] Smoke test: connector runs appear in existing AgentPanel session view without new wiring

### 18e — Server Modularization (3–5 days)

Each file in `server/` has a single responsibility. No god files.

- [ ] Audit `server/vision-server.js` for sections that can move to dedicated modules
- [ ] Audit `server/agent-server.js` — confirm it is UI-session-only (interactive human watching agent run)
- [ ] Define target module list and file responsibilities
- [ ] Refactor without changing external behavior; verify app loads after each file move
- [ ] No file in `server/` exceeds ~300 lines after modularization

### 18f — Test + Observability Hardening (3–4 days)

Golden flow tests for both MCP tools. Stratum audit trace committed with each pipeline run.

- [ ] Golden flow test: `claude_run` with a real prompt, assert typed message stream
- [ ] Golden flow test: `codex_run` with a real prompt, assert typed message stream
- [ ] Golden flow test: schema mode — both connectors inject schema, MCP layer parses JSON
- [ ] `CodexConnector` construction rejects invalid `modelID` (unit test — logic kernel)
- [ ] Stratum audit trace attached to CI output for pipeline runs
- [ ] `isRunning` guard prevents double-run (tested via rapid sequential calls)

### 18g — Cutover + Cleanup (1–2 days)

Remove all dead code and wrong-abstraction artifacts.

- [ ] Remove `openai` from `package.json` dependencies (superseded by `@opencode-ai/sdk`)
- [ ] Confirm `codex-server.js` deleted (step 18a)
- [ ] Confirm no dangling imports to deleted files
- [ ] Remove `CODEX_REVIEW_MODEL` env var references (old review() method gone)
- [ ] `node --check` passes on all server files

### 18h — Acceptance Gate (2–2 days)

End-to-end validation per Phase A–C acceptance criteria in the design doc.

- [ ] Claude Code session: call `claude_run` with a prompt — receives assistant stream
- [ ] Claude Code session: call `codex_run` with a prompt — receives assistant stream
- [ ] Claude Code session: call `codex_run` with `{ schema }` — receives parseable JSON
- [ ] `CodexConnector` rejects `modelID: "gpt-4o"` with a clear error at construction
- [ ] Stratum `review-fix` pipeline completes on a real feature with `result.clean == true`
- [ ] `stratum_audit` trace logged and readable
- [ ] Compose server starts cleanly with no dead-code warnings

---

## Dependencies

- `@anthropic-ai/claude-agent-sdk` already in `package.json`
- `@opencode-ai/sdk` — add pinned version
- `opencode-openai-codex-auth` — one-time setup (not a code dependency): `npx -y opencode-openai-codex-auth@latest && opencode auth login`
- Stratum MCP server must be registered in Claude Code's MCP config
