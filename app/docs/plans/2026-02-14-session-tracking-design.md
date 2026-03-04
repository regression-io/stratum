# Session Tracking Design

**Date:** 2026-02-14
**Status:** Approved
**Related:** [Activity Resolution Spec](../specs/2026-02-14-activity-resolution-spec.md), [CLAUDE.md Phase 3 Roadmap](../../CLAUDE.md)

## Overview

Session tracking turns tool-use events into meaningful, per-item narratives about what work is happening. A session is not an entity — it's an execution accumulator that provides granular updates to existing tracker items.

Two interpretation layers:
- **Live**: Haiku (no thinking) summarizes each tool call as it happens. Per-item semantic activity log builds in real time.
- **Batch**: At session end, a hidden agent reads the transcript + accumulated summaries and writes a journal entry.

## Core Model

A session accumulates tool-use signals per tracker item and translates them into:
1. **Semantic summaries** — "Added three-layer file resolution to server" not "Edit vision-server.js"
2. **Status effects** — Write/Edit bumps planned → in_progress (exists). Test/build signals logged for future transitions.
3. **Work blocks** — When the set of resolved items changes, a new block starts. Blocks segment the session into focused work units.
4. **Durable narrative** — At session end, accumulated signals feed auto-journaling.

Sessions are orthogonal to the work graph. They operate ON items, they don't become items.

## Design Decisions

### D1: Sessions are not tracker entities
Sessions drive item state but are not items themselves. They live in a separate log (`data/sessions.json`). The tracker's job is to model work; the session's job is to observe execution.

### D2: Live interpretation via Haiku
Every tool call gets an async Haiku summary (no extended thinking). The server makes this call after receiving hook data — the hook stays dumb and fast. ~200ms latency, negligible cost. Result is stored in the per-item accumulator and broadcast via WebSocket.

### D3: Work blocks are item-based
A work block boundary is when the set of resolved items changes. If you're editing files for "Activity Resolution" and then switch to files for "Theme System", that's a new block. Blocks are recorded with start/end times and tool counts.

### D4: Auto-journal threshold
Session end spawns a journal agent only if the session had >20 tool uses OR lasted >10 minutes. Trivial sessions (quick lookups, single-file edits) don't generate journal entries.

### D5: Item state effects
Only `planned → in_progress` is automatic (on Write/Edit). All other signals (test pass, build success, commit) are logged in the accumulator for the journal agent or future UI to interpret. No forced transitions to `review` or `complete`.

### D6: Hook stays lightweight
The PostToolUse hook posts raw data to the server. The server owns interpretation (Haiku call, item resolution, accumulation). Hook execution time stays minimal to avoid blocking Claude's next action.

### D7: SessionStart outputs context
The SessionStart hook outputs recent session context to Claude's stdin (last session summary, open in_progress items). This gives Claude awareness of what was happening before.

## Components

### SessionManager (`server/session-manager.js`)

New class. Manages session lifecycle and per-item accumulation.

**State:**
```
currentSession: {
  id: string,
  startedAt: ISO,
  source: 'startup' | 'resume' | 'clear' | 'compact',
  toolCount: number,
  items: Map<itemId, {
    summaries: [{ tool, summary, file, ts }],
    reads: number,
    writes: number,
    firstTouched: ISO,
    lastTouched: ISO,
  }>,
  currentBlock: { itemIds: Set, startedAt: ISO, toolCount: number },
  blocks: [{ itemIds: string[], startedAt: ISO, endedAt: ISO, toolCount: number }],
  commits: string[],
}
```

**Methods:**
- `startSession(source)` — Init state, load recent context from sessions.json
- `endSession(transcriptPath)` — Close blocks, persist to sessions.json, spawn journal if threshold met
- `recordActivity(tool, filePath, input, resolvedItems)` — Accumulate per-item, detect block boundaries, trigger Haiku summary
- `summarizeWithHaiku(tool, file, inputSnippet, resolvedItems)` — Async Haiku call, returns one-line summary
- `getContext()` — Return recent session summary for SessionStart hook output
- `getCurrentSession()` — Return current session state for API/WebSocket

### Hooks

**SessionStart** (`scripts/session-start-hook.sh`):
- Receives: `{ source, model, agent_type }` on stdin
- POSTs to `POST /api/session/start`
- Outputs server response to stdout (becomes context for Claude)

**SessionEnd** (`scripts/session-end-hook.sh`):
- Receives: `{ reason, transcript_path }` on stdin
- POSTs to `POST /api/session/end` with transcript_path
- Cannot block termination — fire and forget

**PostToolUse** (`scripts/agent-activity-hook.sh` — modify existing):
- Currently sends: `{ tool, input: { file_path, command, ... } }`
- Enrich: also send truncated `tool_input` for richer Haiku context (first 200 chars of content fields)

### Server Endpoints

**`POST /api/session/start`**
- Body: `{ source }`
- Creates session in SessionManager
- Returns: `{ sessionId, context: { lastSession, openItems } }`

**`POST /api/session/end`**
- Body: `{ reason, transcriptPath }`
- Persists session to data/sessions.json
- If threshold met (>20 tools OR >10 min): spawns journal agent via existing `/api/agent/spawn`
- Returns: `{ sessionId, persisted: true, journalSpawned: boolean }`

**`POST /api/agent/activity` (existing, enhanced)**
- After item resolution (existing), also calls `sessionManager.recordActivity()`
- Haiku summary async — doesn't block response
- Enriched WebSocket broadcast adds `summary` field to `agentActivity` messages

### Haiku Integration

```
Model: claude-haiku-4-5-20251001
No extended thinking
Max tokens: 60

System: "You summarize developer tool actions in one sentence."

User: "Tool: {tool}. File: {file}. Items: {resolved item titles}. Input: {truncated input}. What is this doing?"
```

Called async after each activity event. Result stored in accumulator, broadcast when ready. If call fails, accumulator stores the raw tool/file info without summary — graceful degradation.

### Session Log (`data/sessions.json`)

Append-only array of completed session summaries:
```json
[
  {
    "id": "session-1739...",
    "startedAt": "2026-02-14T10:00:00Z",
    "endedAt": "2026-02-14T11:30:00Z",
    "source": "startup",
    "reason": "prompt_input_exit",
    "toolCount": 87,
    "duration": 5400,
    "items": {
      "0a3d2cf7-...": {
        "title": "Activity Resolution",
        "summaries": ["Added resolveItems method", "Fixed plan parser false positives", "..."],
        "reads": 12,
        "writes": 8
      }
    },
    "blocks": [
      { "itemIds": ["0a3d2cf7-..."], "startedAt": "...", "endedAt": "...", "toolCount": 45 },
      { "itemIds": ["cb3b05b5-..."], "startedAt": "...", "endedAt": "...", "toolCount": 22 }
    ],
    "commits": ["4b9d953", "8ece2b1"],
    "journalGenerated": true
  }
]
```

### Auto-Journal Agent

Spawned at session end if threshold met. Receives prompt:

```
Read the transcript at {transcriptPath}. Write a journal entry following the format
in docs/journal/. Use session number {N} for today.

Session summary:
- Duration: {duration}
- Items worked on: {per-item summaries}
- Work blocks: {block summaries}
- Commits: {commit list}

Write the entry, update docs/journal/README.md, and commit both files.
Follow the voice/format of existing entries (first person plural, honest about failures).
```

### Item State Effects

Handled in `recordActivity()`:

| Signal | Effect |
|--------|--------|
| Write/Edit on planned item | Auto-bump to `in_progress` (exists) |
| Bash with test-like command + exit 0 | Log `review-ready` signal in accumulator |
| Bash with nonzero exit | Log `failure` signal (feeds error detection) |
| Commit touching item files | Record hash in accumulator |
| Sustained Reads, no Writes | Log `researching` signal |

Only `planned → in_progress` is automatic. All others are signals for downstream consumers.

## What We're NOT Building

- No session entity type in the tracker
- No session view in the UI (deferred — data layer first)
- No forced status transitions beyond `in_progress`
- No cross-session analytics
- No real-time transcript parsing (batch only at session end)
- No session controls (start/stop are hook-driven, not user-initiated)

## Success Criteria

1. SessionStart hook fires, server creates session, Claude receives context about recent work
2. Each tool call produces a Haiku summary within ~500ms, visible in WebSocket broadcast
3. Work block boundaries detected when resolved item set changes
4. Session persisted to `data/sessions.json` on SessionEnd
5. Auto-journal generated for sessions exceeding threshold
6. Existing activity resolution, auto-status, and sidebar display continue working unchanged

## Files

| File | Action |
|------|--------|
| `server/session-manager.js` | New |
| `server/vision-server.js` | Modify — wire SessionManager, add endpoints |
| `scripts/session-start-hook.sh` | New |
| `scripts/session-end-hook.sh` | New |
| `scripts/agent-activity-hook.sh` | Modify — richer payload |
| `.claude/settings.json` | Modify — register new hooks |
