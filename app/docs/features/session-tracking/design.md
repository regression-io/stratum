# Session Tracking — Design

**Roadmap:** Phase 3, Item 14
**Status:** Design
**Date:** 2026-02-15

## Problem

The SessionManager backend is fully built — session lifecycle, per-item accumulation, work blocks, Haiku summaries, persistence, auto-journaling. But none of this is visible in the UI. The user has no way to see:
- That a session is active, how long it's been running, how many tools have been used
- Haiku summaries as they arrive (they're broadcast but no client handler exists)
- Which items the current session has touched
- Past session history

## What Exists (Complete)

| Component | Status |
|-----------|--------|
| SessionManager core (start/end/record/errors/blocks) | Done |
| REST endpoints (/api/session/start, /end, /current) | Done |
| SessionStart/SessionEnd hooks calling endpoints | Done |
| Haiku batch summarization + WebSocket broadcast | Done |
| Auto-journal agent spawning on threshold | Done |
| Persistence to data/sessions.json (75+ sessions) | Done |

## What's Missing (This Feature)

### Gap 1: Client session state
`useVisionStore.js` has no session state. No handler for `sessionSummary` WebSocket messages.

### Gap 2: Session display in sidebar
`AppSidebar.jsx` shows agent activity and errors but no session context — no timer, no tool count, no block progress, no summaries.

### Gap 3: Session lifecycle broadcast
The server broadcasts `sessionSummary` from Haiku, but doesn't broadcast session start/end events. The client can't know when a session starts or ends without polling.

## Design

### Approach: Minimal UI wiring (3 files)

Surface session state in the existing sidebar agent activity panel. No new views, no session history navigation (that's Phase 6 territory — session-lifecycle binding).

### Changes

**1. vision-server.js** — Broadcast session lifecycle events
- On `POST /api/session/start`: broadcast `{ type: 'sessionStart', sessionId, source, timestamp }`
- On `POST /api/session/end`: broadcast `{ type: 'sessionEnd', sessionId, reason, toolCount, duration, journalSpawned, timestamp }`
- Existing `sessionSummary` broadcast already works

**2. useVisionStore.js** — Add session state + handlers
- New state: `sessionState` — `{ id, active, startedAt, toolCount, blockCount, errorCount, summaries[] }`
- Handle `sessionStart` → set active session
- Handle `sessionEnd` → clear active session
- Handle `sessionSummary` → append to summaries list
- Handle `agentActivity` → increment toolCount locally (optimistic, avoids polling)
- On mount: fetch `GET /api/session/current` to hydrate if session already running

**3. AppSidebar.jsx** — Session info in agent panel
- When session active: show elapsed timer, tool count, block count
- When Haiku summary arrives: show latest summary snippet (1 line)
- When session ends: brief flash of session stats before clearing
- When no session: show "No session" (already implied by idle state)

### What This Does NOT Do
- No session history view (Phase 6: session-lifecycle binding)
- No session items in the vision tracker (Phase 6)
- No session picker/navigator
- No changes to hooks (they're complete)
- No changes to SessionManager (it's complete)

### Assumptions & Validations
- The `agentActivity` WebSocket message already increments on every hook-sourced tool use. We can count these client-side instead of polling `/api/session/current`.
- Haiku summaries arrive infrequently (every 4 significant tool uses). The sidebar can display the latest one as a scrolling snippet.

## Files to Modify

| File | Change | Type |
|------|--------|------|
| `server/vision-server.js` (existing) | Add sessionStart/sessionEnd broadcasts | Small |
| `src/components/vision/useVisionStore.js` (existing) | Add session state + 3 message handlers + mount fetch | Medium |
| `src/components/vision/AppSidebar.jsx` (existing) | Session info widget in agent panel | Medium |
