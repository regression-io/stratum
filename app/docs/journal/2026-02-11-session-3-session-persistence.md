# Session 3: The Session That Survives Refresh

**Date:** 2026-02-11
**Phase:** Bootstrap (Phase 0) — Terminal hardening
**Participants:** Human + Claude Code agent

---

## What happened

One question from the human: "can we keep the claude session connected through a refresh?"

The answer was no. Every browser refresh killed the Claude Code session — wiped the conversation, killed the process, started fresh. The problem was architectural: the PTY lifecycle was coupled to the WebSocket lifecycle. When the WebSocket closed (which happens on every page refresh), the server killed the PTY. Simple, wrong, and load-bearing.

### The coupling

In `terminal.js`, the `ws.on('close')` handler:

```js
ws.on('close', () => {
  const session = this.sessions.get(sessionId);
  if (session) {
    session.pty.kill();        // <- This is the problem
    this.sessions.delete(sessionId);
  }
});
```

Every WebSocket disconnect = dead PTY = dead Claude Code session. This was fine when the only disconnect scenario was "user closed the tab." It was catastrophic for refreshes, HMR-induced reconnects, and network blips.

### The fix: decouple PTY from WebSocket

Three changes, all working together:

**1. Server keeps PTY alive on disconnect** (`server/terminal.js`)

When a WebSocket closes, the server no longer kills the PTY. Instead:
- Detaches the WebSocket reference (sets it to `null`)
- Starts a 60-second orphan timer
- Buffers PTY output (up to 128KB) while no client is connected
- If nobody reconnects within 60 seconds, then the PTY gets killed

New connections can pass `?sessionId=<id>` to reconnect to an existing PTY instead of spawning a new one. On reconnect: cancel the orphan timer, replay the buffered output, attach the new WebSocket.

**2. Client remembers its session** (`src/components/Terminal.jsx`)

The session ID from the server is stored in `sessionStorage` (survives refresh, cleared on tab close — the right lifecycle). On connect:
- Check `sessionStorage` for an existing session ID
- If found, connect with `?sessionId=<id>` — no `cmd` param, no new shell, no new Claude session
- If not found (or session is dead server-side), fall through to create a new session

On PTY exit, the stored session ID is cleared so the next connection starts fresh.

**3. Sessions endpoint** (`GET /api/terminal/sessions`)

Added for introspection — lists active PTY sessions with PID and client attachment status. Useful for debugging, and eventually for a UI that shows running sessions.

### What the user sees

Before: refresh = blank terminal, fresh shell, Claude Code gone.

After: refresh = brief disconnect, `[session restored]` message, buffered output replayed, Claude Code still running mid-thought.

## What we built

```
MODIFIED FILES:
  server/terminal.js            — PTY lifecycle decoupled from WebSocket, orphan timer,
                                   output buffering, session reconnection, sessions REST endpoint
  server/index.js               — Pass app to terminalServer.attach() for REST endpoint
  src/components/Terminal.jsx   — sessionStorage persistence, reconnect-to-existing-session flow
```

## What we learned

1. **Lifecycle coupling is the root of most session fragility.** The PTY didn't need to die when the WebSocket died. They have different lifecycles — the PTY's lifecycle is "until the user is done or nobody cares for 60 seconds." The WebSocket's lifecycle is "until the browser feels like disconnecting." Binding the first to the second was a design error, not a requirement.

2. **The buffer bridges the gap.** Without buffering, even a successful reconnect would lose whatever Claude output happened during the ~100ms disconnect window. The 128KB circular buffer means nothing is lost unless the PTY produces >128KB of output while nobody's watching (unlikely in a refresh scenario, possible in a prolonged network outage — acceptable trade-off).

3. **`sessionStorage` has exactly the right lifecycle.** Survives refresh, dies on tab close. `localStorage` would have leaked stale session IDs across tabs. A URL parameter would have been visible and ugly. `sessionStorage` is the invisible persistence layer that matches "this browser tab's session."

4. **Small questions, structural answers.** "Can we keep the session through a refresh?" sounds like a small UX ask. The answer required restructuring the server's session management model. The best questions are the ones that expose a coupling that shouldn't be there.

## Open threads

- [ ] Test under real conditions: start Claude session, refresh mid-conversation, verify continuity
- [ ] Test orphan timeout: disconnect, wait >60s, verify PTY is cleaned up
- [ ] Test edge case: refresh during high-throughput output (extended thinking)
- [ ] Consider: should the orphan timeout be configurable? Longer for Claude sessions that might be mid-operation?
- [ ] Wire persistence connector (Phase 0.4) — still the next real milestone

---

*The terminal is getting harder to kill. Each session hardens another failure mode: crash resilience, WebSocket corruption, now refresh survival. The PTY is becoming a cockroach.*
