# Session 2: The WebSocket Bug Hunt

**Date:** 2026-02-11
**Phase:** Bootstrap (Phase 0) — Hardening
**Participants:** Human + Claude Code agent

---

## What happened

Picked up where Session 1 left off. The terminal and self-healing infrastructure were in place but untested under real conditions. This session was supposed to be "start it up and move on to persistence." Instead, we spent it chasing three interlocking bugs in the WebSocket layer — each one only visible after fixing the previous one.

### Bug 1: Permissions — "clicking allow for everything normal"

First order of business: Claude Code running inside Compose's terminal was prompting for permission on every file read, every bash command, every tool call. The human's ask: configure permissions so normal dev operations are auto-approved but genuinely dangerous actions are gated.

Set up `.claude/settings.json` with comprehensive allow/deny lists:
- **Allow:** npm scripts, safe git ops, file operations, search utilities, process tools, all MCP tools
- **Deny:** force push, `git reset --hard`, `git clean -f`, `rm -rf /` / `rm -rf ~`, `sudo`, `curl | sh`

The deny list takes precedence — so `git push*` is allowed but `git push --force*` is blocked.

### Bug 2: The restart zombie — EADDRINUSE but nobody's home

Started Compose. Server hit EADDRINUSE (port 3001 already taken by a stale process). The `uncaughtException` handler from Session 1 caught the error and kept the process alive — exactly as designed for runtime errors, but exactly wrong for startup errors. The server was alive but not listening: a zombie. The supervisor thought everything was fine.

**Fix:** Added a `serverListening` flag. EADDRINUSE before the server binds now exits with code 1, letting the supervisor retry. Runtime exceptions after startup still keep the process alive to protect PTY sessions.

### Bug 3: The frame corruption — "wtf is RSV1"

With the zombie fixed, the server was binding. But the terminal showed "disconnected — reconnecting..." in an infinite loop. Browser console: `Invalid frame header`. Direct WebSocket test: `RSV1 must be clear`.

RSV1 is a bit in the WebSocket frame header, normally used for per-message compression. First thought: disable compression (`perMessageDeflate: false`). Didn't help.

Raw socket analysis revealed the truth: the second frame wasn't a WebSocket frame at all — it was a raw HTTP 400 response being written to an already-upgraded WebSocket connection. The hex `48545450` is literally "HTTP/1.1 400 Bad Request" being shoved down the socket.

**Root cause:** The `ws` library has a known issue with multiple `WebSocketServer` instances sharing one HTTP server. Both the terminal WSS (`/ws/terminal`) and the file-watcher WSS (`/ws/files`) attached to the same server. When a terminal connection came in, the terminal WSS handled the upgrade successfully — but the file-watcher WSS also saw the upgrade event, didn't recognize the path, and wrote a 400 rejection on the already-upgraded connection, corrupting every subsequent frame.

**Fix:** Both WebSocketServers now use `noServer: true`. The HTTP server's `upgrade` event is handled manually in `index.js`, routing to the correct WSS by pathname. Clean separation, no cross-contamination.

### The human's frustration — "for god sake"

During the debugging, the terminal was flooding with `[disconnected — reconnecting...]` messages on every retry attempt. The human: "have the UI time out and not keep showing reconnected/disconnected after a couple retries and retry silently for god sake."

Fair. Changed to: show `[reconnecting...]` once (in muted gray, not alarming red), then retry silently. Show `[reconnected]` when it actually succeeds. The status dot in the corner still indicates live/offline for anyone who cares.

### The bash loop — three layers of resilience

The human pointed out: the supervisor restarts the server, but what restarts the supervisor? "What about a simple bash loop?"

Added `while true; do ... sleep 2; done` as the outer wrapper in `npm run dev`. Three layers now:
1. **Bash loop** — restarts entire dev stack if anything dies
2. **Supervisor** — restarts Express server on crash
3. **Singleton terminal** — survives HMR without killing the agent session

The old behavior is available as `npm run dev:once`.

## What we built

```
MODIFIED FILES:
  .claude/settings.json          — Comprehensive permission allow/deny config
  server/index.js                — EADDRINUSE exit fix, manual WebSocket upgrade routing
  server/terminal.js             — noServer: true, perMessageDeflate: false
  server/file-watcher.js         — noServer: true, perMessageDeflate: false
  src/components/Terminal.jsx    — Silent reconnection (show once, retry quietly)
  package.json                   — Bash loop wrapper for dev script, dev:once for old behavior
```

## What we learned

1. **Error handlers have modes.** "Keep the process alive on error" is the right strategy for runtime — but fatal for startup. The same handler needs to know *when* the error happened. A flag that flips after successful bind is the simplest way.

2. **Multiple WebSocketServers on one HTTP server is a trap.** The `ws` library's `server` option makes it look easy. It works with one WSS. With two, they fight over upgrade events and corrupt each other's connections. `noServer: true` + manual routing is the only reliable pattern.

3. **Frame-level debugging beats guessing.** The "Invalid frame header" error could have been anything. Raw socket analysis (parsing the actual bytes) immediately showed it was an HTTP response, not a malformed WebSocket frame. Hex doesn't lie.

4. **The human notices what the developer misses.** Three UX corrections came from the human in this session: (a) permissions should be pre-configured, (b) the reconnect UI is obnoxious, (c) a bash loop is simpler than a custom watcher. All correct. All things the developer (me) would have left as-is.

5. **Resilience is layers.** No single mechanism handles all failure modes. The bash loop handles "everything dies." The supervisor handles "server crashes." The singleton terminal handles "code edits trigger HMR." Each layer covers what the others can't.

## Open threads

- [ ] Confirm the Session 1 causal chain theory (ws.send crash → SIGHUP → 400)
- [ ] Wire persistence connector (Phase 0.4) — this was supposed to be today's work
- [ ] CC inside Compose created a Canvas component and file-watcher that we haven't reviewed
- [ ] Test the full three-layer resilience: kill server, kill supervisor, kill everything

---

*The pattern: plan to do X, spend the session making X possible. Persistence will happen when the plumbing stops leaking.*
