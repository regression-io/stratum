# Session Tracking Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Turn tool-use events into per-item semantic narratives via a session accumulator with batched Haiku interpretation.

**Architecture:** SessionManager class accumulates tool events per resolved item. Every 3-5 significant events, spawns `claude -p --model haiku` for a structured JSON summary. SessionStart/SessionEnd hooks bracket the lifecycle. Session log persists to `data/sessions.json`. Auto-journal at session end if threshold met.

**Tech Stack:** Node.js ESM, Claude CLI (haiku model), existing vision-server infrastructure, shell hooks.

---

## Task 1: Create SessionManager Core

**Files:**
- Create: `server/session-manager.js`

**Step 1: Create the module with session state and lifecycle methods**

```javascript
/**
 * SessionManager — Accumulates tool-use events per session and per item.
 * Not a tracker entity. An execution observer that drives item state.
 */
import { spawn } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PROJECT_ROOT = path.resolve(__dirname, '..');
const SESSIONS_FILE = path.join(PROJECT_ROOT, 'data', 'sessions.json');

// Only summarize tools that change or execute things
const SIGNIFICANT_TOOLS = new Set(['Write', 'Edit', 'Bash', 'NotebookEdit']);
const BATCH_SIZE = 4;

export class SessionManager {
  constructor() {
    this.current = null;
    this._pendingEvents = [];
    this._summaryInFlight = false;
  }

  /** Start a new session */
  startSession(source = 'startup') {
    if (this.current) this._closeSession('replaced');
    this.current = {
      id: `session-${Date.now()}`,
      startedAt: new Date().toISOString(),
      source,
      toolCount: 0,
      items: new Map(),
      currentBlock: null,
      blocks: [],
      commits: [],
    };
    console.log(`[session] Started ${this.current.id} (${source})`);
    return this.current;
  }

  /** End the current session */
  endSession(reason = 'exit', transcriptPath = null) {
    if (!this.current) return null;
    this._closeCurrentBlock();
    const session = this.current;
    session.endedAt = new Date().toISOString();
    session.reason = reason;
    session.duration = Math.floor(
      (new Date(session.endedAt) - new Date(session.startedAt)) / 1000
    );
    // Serialize items Map for persistence
    session.itemsSerialized = {};
    for (const [id, data] of session.items) {
      session.itemsSerialized[id] = { ...data, summaries: [...data.summaries] };
    }
    this._persist(session);
    const result = { ...session, transcriptPath };
    this.current = null;
    this._pendingEvents = [];
    console.log(`[session] Ended ${session.id} (${reason}, ${session.toolCount} tools, ${session.duration}s)`);
    return result;
  }

  /** Record a tool-use event. Called from /api/agent/activity handler. */
  recordActivity(tool, filePath, input, resolvedItems) {
    if (!this.current) return;
    this.current.toolCount++;

    // Update per-item accumulators
    const now = new Date().toISOString();
    const isWrite = ['Write', 'Edit', 'NotebookEdit'].includes(tool);
    for (const item of resolvedItems) {
      let acc = this.current.items.get(item.id);
      if (!acc) {
        acc = {
          title: item.title,
          summaries: [],
          reads: 0,
          writes: 0,
          firstTouched: now,
          lastTouched: now,
        };
        this.current.items.set(item.id, acc);
      }
      acc.lastTouched = now;
      if (isWrite) acc.writes++;
      else acc.reads++;
    }

    // Detect work block boundaries
    this._updateBlock(resolvedItems, now);

    // Buffer significant events for batched Haiku summary
    if (SIGNIFICANT_TOOLS.has(tool)) {
      this._pendingEvents.push({
        tool,
        file: filePath,
        input: this._truncateInput(input),
        items: resolvedItems.map(i => i.title),
        ts: now,
      });
      if (this._pendingEvents.length >= BATCH_SIZE && !this._summaryInFlight) {
        this._flushSummary();
      }
    }
  }

  /** Detect work block boundaries based on resolved item set changes */
  _updateBlock(resolvedItems, now) {
    const currentIds = new Set(resolvedItems.map(i => i.id));
    if (!this.current.currentBlock) {
      if (currentIds.size > 0) {
        this.current.currentBlock = {
          itemIds: currentIds,
          startedAt: now,
          toolCount: 0,
        };
      }
      return;
    }
    // Check if item set changed
    const prev = this.current.currentBlock.itemIds;
    const same = currentIds.size === prev.size && [...currentIds].every(id => prev.has(id));
    this.current.currentBlock.toolCount++;
    if (!same && currentIds.size > 0) {
      this._closeCurrentBlock();
      this.current.currentBlock = {
        itemIds: currentIds,
        startedAt: now,
        toolCount: 0,
      };
    }
  }

  _closeCurrentBlock() {
    if (this.current?.currentBlock) {
      this.current.blocks.push({
        itemIds: [...this.current.currentBlock.itemIds],
        startedAt: this.current.currentBlock.startedAt,
        endedAt: new Date().toISOString(),
        toolCount: this.current.currentBlock.toolCount,
      });
      this.current.currentBlock = null;
    }
  }

  /** Truncate tool input for Haiku context */
  _truncateInput(input) {
    if (!input) return '';
    const content = input.content || input.new_string || input.command || input.pattern || '';
    if (typeof content !== 'string') return '';
    return content.length > 200 ? content.slice(0, 200) + '...' : content;
  }

  /** Persist completed session to data/sessions.json */
  _persist(session) {
    try {
      const dir = path.dirname(SESSIONS_FILE);
      fs.mkdirSync(dir, { recursive: true });
      let sessions = [];
      try {
        sessions = JSON.parse(fs.readFileSync(SESSIONS_FILE, 'utf-8'));
      } catch { /* file doesn't exist yet */ }
      sessions.push({
        id: session.id,
        startedAt: session.startedAt,
        endedAt: session.endedAt,
        source: session.source,
        reason: session.reason,
        toolCount: session.toolCount,
        duration: session.duration,
        items: session.itemsSerialized,
        blocks: session.blocks,
        commits: session.commits,
      });
      fs.writeFileSync(SESSIONS_FILE, JSON.stringify(sessions, null, 2), 'utf-8');
      console.log(`[session] Persisted to ${SESSIONS_FILE}`);
    } catch (err) {
      console.error(`[session] Failed to persist:`, err.message);
    }
  }

  /** Get context for SessionStart hook output (recent sessions, open items) */
  getContext() {
    try {
      const raw = fs.readFileSync(SESSIONS_FILE, 'utf-8');
      const sessions = JSON.parse(raw);
      const last = sessions[sessions.length - 1];
      if (!last) return { lastSession: null };
      return {
        lastSession: {
          id: last.id,
          endedAt: last.endedAt,
          duration: last.duration,
          toolCount: last.toolCount,
          items: last.items,
        },
      };
    } catch {
      return { lastSession: null };
    }
  }

  /** Check if session meets auto-journal threshold */
  meetsJournalThreshold() {
    if (!this.current) return false;
    if (this.current.toolCount > 20) return true;
    const elapsed = (Date.now() - new Date(this.current.startedAt).getTime()) / 1000;
    return elapsed > 600; // 10 minutes
  }

  /** Flush pending events to Haiku for batch summary */
  _flushSummary() {
    if (this._pendingEvents.length === 0 || this._summaryInFlight) return;
    const batch = this._pendingEvents.splice(0);
    this._summaryInFlight = true;

    const prompt = this._buildHaikuPrompt(batch);
    this._callHaiku(prompt).then(result => {
      this._summaryInFlight = false;
      if (result && this.current) {
        // Store summaries in per-item accumulators
        this._distributeSummary(result, batch);
        // Broadcast enriched summary
        if (this._onSummary) this._onSummary(result);
      }
      // Flush again if more events accumulated while we were waiting
      if (this._pendingEvents.length >= BATCH_SIZE) this._flushSummary();
    }).catch(err => {
      this._summaryInFlight = false;
      console.error('[session] Haiku summary failed:', err.message);
    });
  }

  /** Register callback for when summaries are produced */
  onSummary(fn) {
    this._onSummary = fn;
  }

  /** Force flush remaining events (e.g. at session end) */
  async flush() {
    if (this._pendingEvents.length > 0) {
      const batch = this._pendingEvents.splice(0);
      const prompt = this._buildHaikuPrompt(batch);
      try {
        const result = await this._callHaiku(prompt);
        if (result && this.current) this._distributeSummary(result, batch);
      } catch { /* best effort */ }
    }
  }

  _buildHaikuPrompt(batch) {
    const events = batch.map(e =>
      `- ${e.tool} on ${e.file || '(no file)'}${e.items.length ? ` [${e.items.join(', ')}]` : ''}${e.input ? `: ${e.input}` : ''}`
    ).join('\n');
    return `Summarize these developer tool actions as a JSON object. Return ONLY valid JSON, no markdown.\n\nEvents:\n${events}\n\nJSON schema:\n{\n  "summary": "one sentence describing what these actions accomplish together",\n  "intent": "feature|bugfix|refactor|test|docs|config|debug",\n  "component": "which part of the system (derived from file paths)",\n  "complexity": "trivial|low|medium|high",\n  "signals": ["string tags like new_file, error_handling, api_change, test_added"],\n  "status_hint": "review_ready|needs_test|blocked|null"\n}`;
  }

  /** Call claude CLI with haiku model */
  _callHaiku(prompt) {
    return new Promise((resolve, reject) => {
      const env = { ...process.env, NO_COLOR: '1' };
      delete env.CLAUDECODE;
      const proc = spawn('claude', ['-p', prompt, '--model', 'haiku', '--max-turns', '1'], {
        cwd: PROJECT_ROOT,
        env,
        stdio: ['ignore', 'pipe', 'pipe'],
        timeout: 15000,
      });
      let stdout = '';
      let stderr = '';
      proc.stdout.on('data', c => { stdout += c; });
      proc.stderr.on('data', c => { stderr += c; });
      proc.on('close', code => {
        if (code !== 0) return reject(new Error(`haiku exit ${code}: ${stderr}`));
        try {
          // Extract JSON from response (haiku may wrap in markdown)
          const jsonMatch = stdout.match(/\{[\s\S]*\}/);
          if (!jsonMatch) return reject(new Error('No JSON in haiku response'));
          resolve(JSON.parse(jsonMatch[0]));
        } catch (err) {
          reject(new Error(`JSON parse failed: ${err.message}`));
        }
      });
      proc.on('error', reject);
    });
  }

  /** Distribute a structured summary to per-item accumulators */
  _distributeSummary(result, batch) {
    if (!this.current) return;
    const touchedItems = new Set(batch.flatMap(e => e.items));
    for (const [id, acc] of this.current.items) {
      if (touchedItems.has(acc.title)) {
        acc.summaries.push({
          ...result,
          ts: new Date().toISOString(),
        });
      }
    }
  }
}
```

**Step 2: Verify syntax**

Run: `node --check server/session-manager.js`
Expected: No output (clean)

**Step 3: Commit**

```bash
git add server/session-manager.js
git commit -m "Add SessionManager: session lifecycle, per-item accumulator, batched Haiku summaries"
```

---

## Task 2: Wire SessionManager into Vision Server

**Files:**
- Modify: `server/index.js` (lines 38-40)
- Modify: `server/vision-server.js` (constructor, attach, activity endpoint)

**Step 1: Create and pass SessionManager in index.js**

In `server/index.js`, after VisionStore creation (line 38), add:

```javascript
import { SessionManager } from './session-manager.js';
// ... after const visionStore = new VisionStore();
const sessionManager = new SessionManager();
const visionServer = new VisionServer(visionStore, sessionManager);
```

**Step 2: Accept SessionManager in VisionServer constructor**

In `server/vision-server.js`, update constructor (line 16):

```javascript
constructor(store, sessionManager = null) {
  this.store = store;
  this.sessionManager = sessionManager;
  // ... rest unchanged
}
```

**Step 3: Add session start/end endpoints in attach()**

After the plan parser endpoint (~line 246), add:

```javascript
// REST: POST /api/session/start — hook calls this on SessionStart
app.post('/api/session/start', (req, res) => {
  const { source } = req.body || {};
  if (!this.sessionManager) return res.status(503).json({ error: 'No session manager' });
  const session = this.sessionManager.startSession(source || 'startup');
  const context = this.sessionManager.getContext();
  res.json({ sessionId: session.id, context });
});

// REST: POST /api/session/end — hook calls this on SessionEnd
app.post('/api/session/end', (req, res) => {
  const { reason, transcriptPath } = req.body || {};
  if (!this.sessionManager) return res.status(503).json({ error: 'No session manager' });

  const meetsThreshold = this.sessionManager.meetsJournalThreshold();

  // Flush any pending Haiku summaries before closing
  this.sessionManager.flush().then(() => {
    const session = this.sessionManager.endSession(reason, transcriptPath);
    if (!session) return res.json({ sessionId: null, persisted: false });

    let journalSpawned = false;
    if (meetsThreshold && transcriptPath) {
      this._spawnJournalAgent(session, transcriptPath);
      journalSpawned = true;
    }

    res.json({ sessionId: session.id, persisted: true, journalSpawned });
  });
});

// REST: GET /api/session/current — current session state
app.get('/api/session/current', (_req, res) => {
  if (!this.sessionManager?.current) return res.json({ session: null });
  const s = this.sessionManager.current;
  const items = {};
  for (const [id, acc] of s.items) {
    items[id] = { title: acc.title, reads: acc.reads, writes: acc.writes, summaries: acc.summaries };
  }
  res.json({
    session: { id: s.id, startedAt: s.startedAt, toolCount: s.toolCount, blockCount: s.blocks.length, items },
  });
});
```

**Step 4: Wire recordActivity into the existing activity endpoint**

In the existing `POST /api/agent/activity` handler (line 178), after item resolution and auto-status, before the broadcast, add:

```javascript
// Feed session accumulator
if (this.sessionManager) {
  this.sessionManager.recordActivity(tool, filePath, input, items);
}
```

**Step 5: Wire Haiku summary broadcast**

In `attach()`, after wiring the session manager, register the summary callback:

```javascript
if (this.sessionManager) {
  this.sessionManager.onSummary((summary) => {
    this.broadcastMessage({ type: 'sessionSummary', ...summary, timestamp: new Date().toISOString() });
  });
}
```

**Step 6: Add _spawnJournalAgent method to VisionServer**

After the `extractFilePaths` method, add:

```javascript
/** Spawn a hidden agent to write a journal entry from session data */
_spawnJournalAgent(session, transcriptPath) {
  const itemSummaries = Object.entries(session.itemsSerialized || {})
    .map(([id, data]) => `- ${data.title}: ${data.writes} writes, ${data.reads} reads. ${data.summaries.map(s => s.summary).join('. ')}`)
    .join('\n');
  const blockSummaries = (session.blocks || [])
    .map((b, i) => `- Block ${i + 1}: ${b.itemIds.length} items, ${b.toolCount} tool uses`)
    .join('\n');

  // Determine session number
  const today = new Date().toISOString().slice(0, 10);
  let sessionNum = 0;
  try {
    const entries = fs.readdirSync(path.join(PROJECT_ROOT, 'docs', 'journal'));
    for (const f of entries) {
      const m = f.match(new RegExp(`^${today}-session-(\\d+)`));
      if (m) sessionNum = Math.max(sessionNum, parseInt(m[1]) + 1);
    }
  } catch { /* journal dir might not exist */ }

  const prompt = `You are writing a developer journal entry for the Compose project.

Read the transcript at: ${transcriptPath}

Write a journal entry at docs/journal/${today}-session-${sessionNum}-<slug>.md following the exact format of existing entries in docs/journal/. Use first person plural ("we"). Be honest about failures.

Session data:
- Duration: ${session.duration}s (${Math.round(session.duration / 60)} minutes)
- Tool uses: ${session.toolCount}
- Items worked on:
${itemSummaries || '(none resolved)'}
- Work blocks:
${blockSummaries || '(single block)'}
- Commits: ${(session.commits || []).join(', ') || '(none)'}

After writing the entry, update docs/journal/README.md with the new entry row.
Then commit both files with message: "Journal entry: Session ${sessionNum} — <one line summary>"`;

  // Use existing agent spawn infrastructure
  const cleanEnv = { ...process.env, NO_COLOR: '1' };
  delete cleanEnv.CLAUDECODE;
  const proc = spawn('claude', ['-p', prompt, '--dangerously-skip-permissions'], {
    cwd: PROJECT_ROOT,
    env: cleanEnv,
    stdio: ['ignore', 'pipe', 'pipe'],
  });
  proc.on('close', (code) => {
    console.log(`[session] Journal agent exited (code ${code})`);
  });
  proc.on('error', (err) => {
    console.error(`[session] Journal agent spawn error:`, err.message);
  });
  console.log(`[session] Journal agent spawned (PID ${proc.pid})`);
}
```

**Step 7: Verify syntax**

Run: `node --check server/vision-server.js && node --check server/index.js`
Expected: No output (clean)

**Step 8: Commit**

```bash
git add server/vision-server.js server/index.js
git commit -m "Wire SessionManager into vision server: endpoints, activity recording, journal agent"
```

---

## Task 3: Create Hook Scripts

**Files:**
- Create: `scripts/session-start-hook.sh`
- Create: `scripts/session-end-hook.sh`
- Modify: `scripts/agent-activity-hook.sh`

**Step 1: Create SessionStart hook**

```bash
#!/bin/bash
# session-start-hook.sh — SessionStart hook. Creates a session on the Compose server.
# Receives JSON on stdin: { source, model, agent_type }
# Outputs context to stdout (becomes Claude's session context).

INPUT=$(cat)
SOURCE=$(echo "$INPUT" | jq -r '.source // "startup"')

RESPONSE=$(curl -s -m 2 -X POST http://localhost:3001/api/session/start \
  -H 'Content-Type: application/json' \
  -d "{\"source\": \"$SOURCE\"}" 2>/dev/null)

[ -z "$RESPONSE" ] && exit 0

# Extract context for Claude
LAST_SESSION=$(echo "$RESPONSE" | jq -r '.context.lastSession // empty')
if [ -n "$LAST_SESSION" ]; then
  LAST_ITEMS=$(echo "$LAST_SESSION" | jq -r '.items | to_entries[] | "- \(.value.title): \(.value.writes) writes, \(.value.reads) reads"' 2>/dev/null)
  LAST_DURATION=$(echo "$LAST_SESSION" | jq -r '.duration // 0')
  LAST_TOOLS=$(echo "$LAST_SESSION" | jq -r '.toolCount // 0')
  echo "Last session: ${LAST_DURATION}s, ${LAST_TOOLS} tool uses."
  if [ -n "$LAST_ITEMS" ]; then
    echo "Items worked on:"
    echo "$LAST_ITEMS"
  fi
fi

exit 0
```

**Step 2: Create SessionEnd hook**

```bash
#!/bin/bash
# session-end-hook.sh — SessionEnd hook. Closes session, triggers journal if threshold met.
# Receives JSON on stdin: { reason, transcript_path }
# Cannot block termination — fire and forget.

INPUT=$(cat)
REASON=$(echo "$INPUT" | jq -r '.reason // "exit"')
TRANSCRIPT=$(echo "$INPUT" | jq -r '.transcript_path // empty')

BODY="{\"reason\": \"$REASON\""
[ -n "$TRANSCRIPT" ] && BODY="$BODY, \"transcriptPath\": \"$TRANSCRIPT\""
BODY="$BODY}"

# Fire and forget — session end cannot block
curl -s -m 5 -X POST http://localhost:3001/api/session/end \
  -H 'Content-Type: application/json' \
  -d "$BODY" > /dev/null 2>&1 &

exit 0
```

**Step 3: Make both executable**

Run: `chmod +x scripts/session-start-hook.sh scripts/session-end-hook.sh`

**Step 4: Enrich agent-activity-hook.sh with truncated content**

Modify the existing hook to include a `content_snippet` field for richer Haiku context. Replace the curl line:

```bash
#!/bin/bash
# agent-activity-hook.sh — PostToolUse hook that forwards tool activity to Compose server.
#
# Receives JSON on stdin from Claude Code with tool_name and tool_input.
# POSTs a compact summary to the Compose server which broadcasts it via WebSocket
# to the Vision Tracker's agent activity feed.
#
# Runs quickly — curl with 1s timeout, backgrounded, non-blocking.

INPUT=$(cat)

TOOL=$(echo "$INPUT" | jq -r '.tool_name // empty')
[ -z "$TOOL" ] && exit 0

# Extract tool_input as compact JSON (jq -c)
TOOL_INPUT=$(echo "$INPUT" | jq -c '.tool_input // {}')

# Extract a content snippet for semantic interpretation (first 200 chars)
SNIPPET=$(echo "$INPUT" | jq -r '(.tool_input.content // .tool_input.new_string // .tool_input.command // "") | tostring | .[0:200]')

# Fire and forget — don't block the agent
curl -s -m 1 -X POST http://localhost:3001/api/agent/activity \
  -H 'Content-Type: application/json' \
  -d "{\"tool\": \"$TOOL\", \"input\": $TOOL_INPUT, \"snippet\": \"$(echo "$SNIPPET" | sed 's/"/\\"/g' | tr '\n' ' ')\"}" \
  > /dev/null 2>&1 &

exit 0
```

**Step 5: Verify all scripts have correct syntax**

Run: `bash -n scripts/session-start-hook.sh && bash -n scripts/session-end-hook.sh && bash -n scripts/agent-activity-hook.sh && echo "All OK"`
Expected: "All OK"

**Step 6: Commit**

```bash
git add scripts/session-start-hook.sh scripts/session-end-hook.sh scripts/agent-activity-hook.sh
git commit -m "Session hooks: start, end, enriched activity payload with content snippet"
```

---

## Task 4: Register Hooks in Settings

**Files:**
- Modify: `.claude/settings.json`

**Step 1: Add SessionStart and SessionEnd hooks**

Replace the full settings.json content:

```json
{
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "/Users/ruze/reg/my/compose/coder-compose/scripts/session-start-hook.sh"
          }
        ]
      }
    ],
    "SessionEnd": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "/Users/ruze/reg/my/compose/coder-compose/scripts/session-end-hook.sh"
          }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [
          {
            "type": "command",
            "command": "/Users/ruze/reg/my/compose/coder-compose/scripts/vision-hook.sh"
          }
        ]
      },
      {
        "hooks": [
          {
            "type": "command",
            "command": "/Users/ruze/reg/my/compose/coder-compose/scripts/agent-activity-hook.sh"
          }
        ]
      }
    ]
  }
}
```

**Step 2: Commit**

```bash
git add .claude/settings.json
git commit -m "Register SessionStart and SessionEnd hooks"
```

---

## Task 5: Integration Verification

**Step 1: Syntax check all modified server files**

Run: `node --check server/session-manager.js && node --check server/vision-server.js && node --check server/index.js && echo "All server files OK"`
Expected: "All server files OK"

**Step 2: Build check**

Run: `npx vite build`
Expected: Build succeeds (session-manager is server-only, no client changes)

**Step 3: Restart server and verify session start endpoint**

Kill the server PID so supervisor respawns with new code. Then test:

```bash
curl -s http://localhost:3001/api/session/start -X POST -H 'Content-Type: application/json' -d '{"source":"startup"}' | python3 -m json.tool
```

Expected: `{ "sessionId": "session-...", "context": { "lastSession": null } }`

**Step 4: Test activity recording with session accumulation**

```bash
# Simulate a Write to a file with known item
curl -s http://localhost:3001/api/agent/activity -X POST -H 'Content-Type: application/json' \
  -d '{"tool":"Edit","input":{"file_path":"/Users/ruze/reg/my/compose/coder-compose/server/vision-store.js"}}'
# Check session state
curl -s http://localhost:3001/api/session/current | python3 -m json.tool
```

Expected: Session shows `toolCount: 1`, items map contains "Activity Resolution" with `writes: 1`

**Step 5: Test session end and persistence**

```bash
curl -s http://localhost:3001/api/session/end -X POST -H 'Content-Type: application/json' \
  -d '{"reason":"test"}' | python3 -m json.tool
# Check persistence
cat data/sessions.json | python3 -m json.tool | head -20
```

Expected: Session persisted with duration, toolCount, items

**Step 6: Test Haiku batch summary**

```bash
# Start a new session
curl -s http://localhost:3001/api/session/start -X POST -H 'Content-Type: application/json' -d '{"source":"test"}'
# Send 4 significant events to trigger batch
for i in 1 2 3 4; do
  curl -s http://localhost:3001/api/agent/activity -X POST -H 'Content-Type: application/json' \
    -d '{"tool":"Edit","input":{"file_path":"/Users/ruze/reg/my/compose/coder-compose/server/vision-server.js","new_string":"// change '$i'"}}'
  sleep 0.5
done
# Wait for Haiku and check
sleep 5
curl -s http://localhost:3001/api/session/current | python3 -c "import sys,json; d=json.load(sys.stdin); items=d.get('session',{}).get('items',{}); [print(v.get('title','?'), ':', v.get('summaries',[])) for v in items.values()]"
```

Expected: Item accumulator contains a structured Haiku summary object

**Step 7: Final commit**

```bash
git add -A
git commit -m "Session tracking: accumulator, Haiku summaries, lifecycle hooks, auto-journal"
```

---

## Verification Checklist

- [ ] SessionStart hook fires on new session, server creates accumulator
- [ ] PostToolUse events accumulate per-item (reads, writes, lastTouched)
- [ ] Work block boundaries detected when resolved items change
- [ ] Every 4 significant events triggers batched Haiku call
- [ ] Haiku returns structured JSON (summary, intent, component, complexity, signals, status_hint)
- [ ] Structured summary stored in per-item accumulator and broadcast via WebSocket
- [ ] SessionEnd persists session to `data/sessions.json`
- [ ] Auto-journal agent spawned when threshold met (>20 tools OR >10 min)
- [ ] Existing activity resolution, auto-status, and sidebar display unchanged
- [ ] `npm run build` passes
- [ ] Server syntax checks pass

## Risk Notes

- **Haiku CLI spawn overhead**: Each batch spawns a `claude` process. If this is too slow (>5s), consider adding a timeout and falling back to raw tool data.
- **JSON parsing from Haiku**: Haiku may wrap JSON in markdown fences. The `jsonMatch` regex handles this. If it still fails, graceful degradation — summary is `null`, raw data preserved.
- **SessionEnd timing**: The hook fires on exit. The curl is backgrounded so it doesn't block. But if the server is down, the session is lost. The in-memory state is gone. Acceptable tradeoff — the session log is best-effort.
- **Nested session guard**: Haiku spawn uses `CLAUDECODE=` to bypass the nested session check. Same pattern as existing agent spawn.
