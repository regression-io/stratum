# Session 1: First Boot

**Date:** 2026-02-11
**Phase:** Bootstrap (Phase 0) — Terminal embed
**Participants:** Human + Claude Code agent

---

## What happened

Forge ran for the first time. The terminal embedded in the UI, Claude Code launched inside it. It worked — briefly. Then everything broke.

### The crash

Running Claude Code inside the forge terminal produced a 400 error from the Anthropic API:

```
API Error: 400 {"type":"error","error":{"type":"invalid_request_error",
"message":"messages.7.content.8: `thinking` or `redacted_thinking` blocks
in the latest assistant message cannot be modified."}}
```

Then the app died completely.

### Diagnosis

Two separate failures, likely causally linked:

**1. The server had no crash resilience.**
- No `process.on('uncaughtException')` handler
- No `process.on('unhandledRejection')` handler
- A single thrown error in any code path killed the entire Node process
- The WebSocket `ws.send()` in the PTY output handler had no try/catch — a failed send during high-throughput Claude output would be an uncaught exception

**2. The dev script hid the evidence.**
- `"dev": "node server/index.js & vite"` — server backgrounded with `&`
- Server output mixed with Vite output and was easy to miss
- If the server crashed, you'd barely see it

**Causal chain theory:**
1. `ws.send()` throws during heavy Claude Code output (extended thinking produces high throughput)
2. Uncaught exception starts killing the Node process
3. node-pty cleanup sends SIGHUP to the child process group
4. Claude Code receives the signal, enters degraded shutdown state
5. Mid-shutdown, makes an API call with truncated conversation history
6. API rejects it: thinking blocks were mangled in the truncation
7. 400 error appears in terminal, then everything dies

### Fixes applied

**Server crash resilience** (`server/index.js`):
- Added `process.on('uncaughtException')` — logs but keeps process alive
- Added `process.on('unhandledRejection')` — same
- Added stack traces to error output

**WebSocket safety** (`server/terminal.js`):
- Wrapped all `ws.send()` calls in try/catch
- PTY output handler, PTY exit handler — both protected
- A failed WebSocket write is now logged, not fatal

**Observability** (`package.json`):
- Server output tees to `/tmp/forge-server.log`
- Can `tail -f /tmp/forge-server.log` in a separate terminal
- Added `dev:server` and `dev:client` as separate scripts for debugging

**Process supervisor** (`server/supervisor.js`):
- Parent process that spawns the server via `fork()`
- If the server exits, supervisor restarts it with exponential backoff
- Backoff resets if server was healthy for >5 seconds
- Forwards SIGINT/SIGTERM to child for clean shutdown
- `npm run dev` now runs through the supervisor

**Client reconnection** (`src/components/Terminal.jsx`):
- WebSocket disconnect triggers automatic reconnection with backoff
- Health check (`/api/health`) before reconnecting to confirm server is alive
- Reconnect doesn't re-run the initial command (prevents duplicate `claude` launches)
- Previous xterm.js event listeners properly disposed before rebinding
- Visual feedback: `[disconnected — reconnecting...]` and `[reconnected — new session]`

### The self-monitoring question

Raised the question: can Forge monitor itself? This maps to the roadmap:

- **Level 1 — PTY output monitoring.** The server already sees all terminal output. Pattern-match for known error signatures (`API Error:`, stack traces) and surface them in the UI or logs.
- **Level 2 — Claude Code structured output.** Use `--output-format stream-json` to get structured events (errors, tool use, thinking) instead of opaque terminal output.
- **Level 3 — Agent SDK connector.** Host the agent directly via the Anthropic Agent SDK, bypassing the PTY. Forge becomes the orchestrator, not just a terminal wrapper.

These map to Phase 4 of the roadmap (Agent Connector), but Level 1 could be done immediately.

### The developer journal decision

Decided to capture the build process as a journal — the story of how Forge was built. This is raw material for the narrative, and also a test case for the kind of knowledge capture Forge is designed to automate.

Journal entries are written in real time from this point forward. Session 0 was reconstructed from existing docs.

## What we built

```
NEW FILES:
  server/supervisor.js          — Process supervisor with restart + backoff

MODIFIED FILES:
  server/index.js               — Crash resilience (uncaughtException, unhandledRejection, SIGTERM)
  server/terminal.js            — try/catch on all ws.send() calls
  src/components/Terminal.jsx   — WebSocket reconnection with health check + backoff
  package.json                  — Supervisor in dev script, server log tee, split dev scripts

NEW DOCS:
  docs/journal/README.md        — Journal index
  docs/journal/session-0.md     — Reconstructed planning session
  docs/journal/session-1.md     — This entry
```

## What we learned

1. **First run always breaks.** The planning marathon produced clean designs. Reality produced a crash in the first minute. The gap between "coded" and "working" is where trust lives.

2. **Invisible failures are the worst kind.** The backgrounded server hid every clue. Fix observability before fixing functionality — you can't fix what you can't see.

3. **Self-healing > error prevention.** We can't prevent every crash. But we can make the system restart itself and reconnect. The supervisor + client reconnection pattern means a crash becomes a 2-second blip instead of "the app died."

4. **The agent connector question is urgent.** Right now Claude Code inside the PTY is a black box. Forge can't see what the agent is doing, what errors it's hitting, or what state it's in. The agent connector (Phase 4 in the roadmap) needs to move earlier — at least the read-only version.

5. **Dogfooding pressure is real.** We're experiencing exactly what Forge is designed to solve: the crash, diagnosis, and fix happened across a conversation that produced decisions, code changes, and architectural insights — none of which are captured in a structured way. The journal is a manual approximation of what Forge's conversation distillation would automate.

## Open threads

- [ ] Reproduce the crash with logging enabled to confirm the causal chain
- [ ] Level 1 agent monitoring: pattern-match PTY output for errors
- [ ] Test the supervisor restart + client reconnection end-to-end
- [ ] Consider moving Agent Connector (read-only) earlier in the roadmap

---

*Next session: wire persistence, get the UI showing real data from `.forge/`.*
