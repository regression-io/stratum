# Session Tracking — Implementation Plan

**Feature:** Phase 3, Item 14
**Date:** 2026-02-15

## Task Order

### Task 1: Server — Broadcast session lifecycle events
**File:** `server/vision-server.js` (existing)

1a. In `POST /api/session/start` handler (line ~322), after `startSession()`, broadcast:
```js
this.broadcastMessage({
  type: 'sessionStart',
  sessionId: session.id,
  source: source || 'startup',
  timestamp: new Date().toISOString(),
});
```

1b. In `POST /api/session/end` handler (line ~331), after `endSession()`, broadcast:
```js
if (session) {
  this.broadcastMessage({
    type: 'sessionEnd',
    sessionId: session.id,
    reason,
    toolCount: session.toolCount,
    duration: Math.round((new Date(session.endedAt) - new Date(session.startedAt)) / 1000),
    journalSpawned,
    timestamp: new Date().toISOString(),
  });
}
```

### Task 2: Client store — Add session state + handlers
**File:** `src/components/vision/useVisionStore.js` (existing)

2a. Add `sessionState` to state variables:
```js
const [sessionState, setSessionState] = useState(null);
```

2b. Add WebSocket handlers for `sessionStart`, `sessionEnd`, `sessionSummary`:
- `sessionStart` → set `{ id, active: true, startedAt, source, toolCount: 0, errorCount: 0, summaries: [] }`
- `sessionEnd` → set to `{ ...prev, active: false, endedAt, duration, toolCount, journalSpawned }`, then clear after 10s
- `sessionSummary` → append summary to `sessionState.summaries`

2c. Increment session toolCount on each `agentActivity` message (optimistic local counter).

2d. On mount: fetch `GET /api/session/current` to hydrate session state if server already has an active session.

2e. Return `sessionState` from the hook.

### Task 3: Sidebar UI — Session info widget
**File:** `src/components/vision/AppSidebar.jsx` (existing)

3a. Accept `sessionState` prop.

3b. In the agent activity panel (the `rounded-md p-2` div), add session context above the agent status:
- Active session: elapsed timer (auto-updating), tool count badge, error count if > 0
- Latest Haiku summary: one-line snippet below session stats
- Session ended: brief "Session ended — N tools, Mm Ss" flash, then fade

3c. Wire `sessionState` prop from `VisionSurface.jsx` (or wherever AppSidebar is rendered).

### Task 4: Wire prop through parent
**File:** Need to check where AppSidebar is rendered to pass `sessionState`.

## Commit Plan

1. **Commit 1:** Tasks 1 + 2 — server broadcasts + client state (vision-server.js, useVisionStore.js)
2. **Commit 2:** Tasks 3 + 4 — sidebar UI + prop wiring (AppSidebar.jsx, parent component)
