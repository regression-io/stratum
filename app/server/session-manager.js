/**
 * SessionManager — session lifecycle, per-item accumulator, batched Haiku summaries.
 *
 * Sessions are NOT tracker entities — they're execution context that accumulates
 * tool-use events, groups them into work blocks by resolved tracker item, and
 * periodically summarises batches via Haiku.
 */

import { spawn } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PROJECT_ROOT = path.resolve(__dirname, '..');
const SESSIONS_FILE = path.join(PROJECT_ROOT, 'data', 'sessions.json');

/** Tools whose events count toward the Haiku summary batch threshold */
const SIGNIFICANT_TOOLS = new Set(['Write', 'Edit', 'Bash', 'NotebookEdit']);

/** Number of significant events before triggering a Haiku summary call */
const BATCH_SIZE = 4;

export class SessionManager {
  constructor() {
    /** @type {object|null} Current active session */
    this.currentSession = null;

    /** @type {Array<{tool,filePath,input,itemIds,timestamp}>} Buffered significant events */
    this._pendingBatch = [];

    /** @type {boolean} Whether a Haiku flush is currently in-flight */
    this._flushing = false;

    /** @type {Promise|null} In-flight flush promise for awaiting */
    this._flushPromise = null;

    /** @type {Array<function>} Callbacks for when summaries arrive */
    this._summaryListeners = [];
  }

  // ---------------------------------------------------------------------------
  // Public API
  // ---------------------------------------------------------------------------

  /**
   * Start a new session.
   * @param {'startup'|'resume'|'clear'|'compact'} source — what triggered the session
   */
  startSession(source = 'startup') {
    // Close any lingering session synchronously (skip Haiku flush to avoid async race)
    if (this.currentSession) {
      this._closeCurrentBlock();
      const old = this.currentSession;
      old.endedAt = new Date().toISOString();
      old.endReason = 'replaced';
      this._persist(this._serialize(old));
      console.log(`[session] Ended ${old.id} (reason: replaced, tools: ${old.toolCount})`);
      this.currentSession = null;
    }

    const now = new Date().toISOString();
    this.currentSession = {
      id: `session-${Date.now()}`,
      startedAt: now,
      source,
      toolCount: 0,
      items: new Map(),          // itemId → { title, summaries[], reads, writes, firstTouched, lastTouched }
      currentBlock: null,        // { itemIds: Set, startedAt, toolCount } | null
      blocks: [],                // closed blocks: { itemIds[], startedAt, endedAt, toolCount }
      commits: [],
      errors: [],                // { type, severity, tool, message, itemIds, timestamp }
    };

    this._pendingBatch = [];
    this._flushing = false;
    this._flushPromise = null;

    console.log(`[session] Started ${this.currentSession.id} (source: ${source})`);
    return this.currentSession;
  }

  /**
   * End the current session, persist it, return session data.
   * @param {string} reason — why the session ended
   * @param {string} [transcriptPath] — optional path to conversation transcript
   * @returns {object|null} The completed session data, or null if no session active
   */
  async endSession(reason = 'manual', transcriptPath = null) {
    if (!this.currentSession) return null;

    // Flush any pending Haiku batch
    await this.flush();

    // Close any open block
    this._closeCurrentBlock();

    const session = this.currentSession;
    session.endedAt = new Date().toISOString();
    session.endReason = reason;
    if (transcriptPath) session.transcriptPath = transcriptPath;

    // Convert Maps/Sets to plain objects for serialization
    const serializable = this._serialize(session);

    this._persist(serializable);

    console.log(`[session] Ended ${session.id} (reason: ${reason}, tools: ${session.toolCount})`);

    this.currentSession = null;
    this._pendingBatch = [];
    return serializable;
  }

  /**
   * Record a tool-use event. Accumulates per-item stats, detects block boundaries,
   * and buffers significant events for Haiku summarization.
   *
   * @param {string} tool — tool name (Read, Write, Edit, Bash, etc.)
   * @param {string|null} filePath — file path if applicable
   * @param {object} input — raw tool input
   * @param {Array<{id,title,status}>} resolvedItems — tracker items this event maps to
   */
  recordActivity(tool, category, filePath, input, resolvedItems = []) {
    if (!this.currentSession) return;

    const now = new Date().toISOString();
    const session = this.currentSession;
    session.toolCount++;

    // Accumulate per-item stats
    const isWrite = ['Write', 'Edit', 'NotebookEdit'].includes(tool);
    const isRead = tool === 'Read';

    for (const item of resolvedItems) {
      let acc = session.items.get(item.id);
      if (!acc) {
        acc = {
          title: item.title,
          summaries: [],
          reads: 0,
          writes: 0,
          firstTouched: now,
          lastTouched: now,
        };
        session.items.set(item.id, acc);
      }
      acc.lastTouched = now;
      if (isRead) acc.reads++;
      if (isWrite) acc.writes++;
    }

    // Detect work block boundaries
    const itemIds = resolvedItems.map(i => i.id);
    if (itemIds.length > 0) {
      this._updateBlock(itemIds, now, category);
    }

    // Buffer significant events for Haiku summarization
    if (SIGNIFICANT_TOOLS.has(tool)) {
      this._pendingBatch.push({
        tool,
        category,
        filePath,
        input: this._truncateInput(input),
        itemIds,
        itemTitles: resolvedItems.map(i => i.title),
        timestamp: now,
      });

      if (this._pendingBatch.length >= BATCH_SIZE && !this._flushing) {
        // Fire-and-forget — don't block the activity endpoint
        this._flushPromise = this._flushSummary().catch(err => {
          console.error('[session] Background flush failed:', err.message);
        });
      }
    }
  }

  /**
   * Record a detected error. Stored in session for persistence and included in
   * Haiku batch context so summaries can mention failures.
   *
   * @param {string} tool — tool name
   * @param {string|null} filePath — file path if applicable
   * @param {string} errorType — classified error type (build_error, test_failure, etc.)
   * @param {string} severity — 'error' or 'warning'
   * @param {string} message — truncated error message
   * @param {Array<{id,title}>} resolvedItems — tracker items this error maps to
   */
  recordError(tool, filePath, errorType, severity, message, resolvedItems = []) {
    if (!this.currentSession) return;

    this.currentSession.errors.push({
      type: errorType,
      severity,
      tool,
      filePath: filePath || null,
      message: message.length > 200 ? message.slice(0, 197) + '...' : message,
      itemIds: resolvedItems.map(i => i.id),
      timestamp: new Date().toISOString(),
    });
  }

  /**
   * Force-flush any pending events to Haiku. Awaitable.
   */
  async flush() {
    // Wait for any in-flight flush to complete first
    if (this._flushPromise) {
      await this._flushPromise;
    }
    // Then flush any remaining events
    if (this._pendingBatch.length > 0) {
      await this._flushSummary();
    }
  }

  /**
   * Register a callback for when Haiku summaries arrive.
   * @param {function} fn — receives (summaryResult, batchEvents)
   */
  onSummary(fn) {
    this._summaryListeners.push(fn);
  }

  /**
   * Return the most recent session summary from sessions.json for the SessionStart hook.
   * @returns {object|null} Last session data, or null
   */
  getContext() {
    try {
      const raw = fs.readFileSync(SESSIONS_FILE, 'utf-8');
      const sessions = JSON.parse(raw);
      if (Array.isArray(sessions) && sessions.length > 0) {
        return sessions[sessions.length - 1];
      }
    } catch {
      // No sessions file yet — that's fine
    }
    return null;
  }

  /**
   * True if the current session crosses the journal-worthiness threshold:
   * more than 20 tool uses OR more than 10 minutes duration.
   * @returns {boolean}
   */
  meetsJournalThreshold() {
    if (!this.currentSession) return false;

    if (this.currentSession.toolCount > 20) return true;

    const elapsed = Date.now() - new Date(this.currentSession.startedAt).getTime();
    const tenMinutes = 10 * 60 * 1000;
    return elapsed > tenMinutes;
  }

  // ---------------------------------------------------------------------------
  // Internal: Haiku summarization pipeline
  // ---------------------------------------------------------------------------

  /**
   * Build a Haiku prompt from the pending batch, spawn the CLI, parse the JSON,
   * and distribute the result to per-item accumulators.
   */
  async _flushSummary() {
    if (this._pendingBatch.length === 0) return;
    this._flushing = true;

    // Take the current batch and reset
    const batch = this._pendingBatch.splice(0);

    try {
      const prompt = this._buildHaikuPrompt(batch);
      const result = await this._callHaiku(prompt);
      if (result) {
        this._distributeSummary(result, batch);
        // Notify listeners
        for (const fn of this._summaryListeners) {
          try { fn(result, batch); } catch { /* listener errors don't propagate */ }
        }
      }
    } catch (err) {
      console.error('[session] Haiku summary failed, raw data preserved:', err.message);
      // Graceful degradation: the per-item reads/writes/timestamps remain.
      // Summaries just won't have this batch's contribution.
    } finally {
      this._flushing = false;
      this._flushPromise = null;
    }
  }

  /**
   * Spawn `claude -p <prompt> --model haiku --max-turns 1` with CLAUDECODE unset.
   * Parse JSON from output. Returns parsed object or null on failure.
   *
   * @param {string} prompt
   * @returns {Promise<object|null>}
   */
  _callHaiku(prompt) {
    return new Promise((resolve) => {
      const cleanEnv = { ...process.env, NO_COLOR: '1' };
      delete cleanEnv.CLAUDECODE;

      const proc = spawn('claude', [
        '-p', prompt,
        '--model', 'haiku',
        '--max-turns', '1',
      ], {
        cwd: PROJECT_ROOT,
        env: cleanEnv,
        stdio: ['ignore', 'pipe', 'pipe'],
      });

      let stdout = '';
      let stderr = '';

      proc.stdout.on('data', (chunk) => { stdout += chunk.toString(); });
      proc.stderr.on('data', (chunk) => { stderr += chunk.toString(); });

      proc.on('error', (err) => {
        console.error('[session] Haiku spawn error:', err.message);
        resolve(null);
      });

      proc.on('close', (code) => {
        if (code !== 0) {
          console.error(`[session] Haiku exited with code ${code}:`, stderr.slice(0, 200));
          resolve(null);
          return;
        }

        // Extract JSON from output — Haiku might wrap it in markdown fences
        try {
          const json = this._extractJSON(stdout);
          resolve(json);
        } catch (err) {
          console.error('[session] Haiku JSON parse failed:', err.message, 'raw:', stdout.slice(0, 300));
          resolve(null);
        }
      });
    });
  }

  /**
   * Format batch events into a prompt asking Haiku for structured JSON.
   * @param {Array} batch
   * @returns {string}
   */
  _buildHaikuPrompt(batch) {
    const eventLines = batch.map(evt => {
      const itemLabel = evt.itemTitles.length > 0
        ? ` [${evt.itemTitles.join(', ')}]`
        : '';
      const fileLabel = evt.filePath
        ? ` on ${path.relative(PROJECT_ROOT, evt.filePath) || evt.filePath}`
        : ' on (no file)';
      return `- ${evt.tool}${fileLabel}${itemLabel}: ${evt.input}`;
    }).join('\n');

    return `Summarize these developer tool actions as a JSON object. Return ONLY valid JSON, no markdown.

Events:
${eventLines}

JSON schema:
{
  "summary": "one sentence describing what these actions accomplish together",
  "intent": "feature|bugfix|refactor|test|docs|config|debug",
  "component": "which part of the system (derived from file paths)",
  "complexity": "trivial|low|medium|high",
  "signals": ["string tags like new_file, error_handling, api_change, test_added"],
  "status_hint": "review_ready|needs_test|blocked|null"
}`;
  }

  /**
   * Store the Haiku result in per-item accumulators for all items touched by the batch.
   * @param {object} result — parsed Haiku JSON
   * @param {Array} batch — the events that produced this summary
   */
  _distributeSummary(result, batch) {
    if (!this.currentSession) return;

    // Collect all unique item IDs from the batch
    const itemIds = new Set();
    for (const evt of batch) {
      for (const id of evt.itemIds) {
        itemIds.add(id);
      }
    }

    const summary = {
      ...result,
      batchSize: batch.length,
      timestamp: new Date().toISOString(),
    };

    for (const id of itemIds) {
      const acc = this.currentSession.items.get(id);
      if (acc) {
        acc.summaries.push(summary);
      }
    }

    console.log(`[session] Haiku summary distributed to ${itemIds.size} items: "${result.summary}"`);
  }

  // ---------------------------------------------------------------------------
  // Internal: Block detection
  // ---------------------------------------------------------------------------

  /**
   * Detect block boundaries: a new block starts when the set of resolved items changes.
   * @param {string[]} itemIds — current resolved item IDs
   * @param {string} now — ISO timestamp
   */
  _updateBlock(itemIds, now, category) {
    if (!this.currentSession) return;

    const session = this.currentSession;
    const currentSet = session.currentBlock?.itemIds;

    // Check if the item set has changed
    const sameBlock = currentSet
      && itemIds.length === currentSet.size
      && itemIds.every(id => currentSet.has(id));

    if (sameBlock) {
      // Same block — just increment tool count
      session.currentBlock.toolCount++;
      if (category) session.currentBlock.categories.add(category);
      return;
    }

    // Different set → close current block, start new one
    this._closeCurrentBlock();

    session.currentBlock = {
      itemIds: new Set(itemIds),
      startedAt: now,
      toolCount: 1,
      categories: new Set(category ? [category] : []),
    };
  }

  /**
   * Close the current block and push it to the blocks array.
   */
  _closeCurrentBlock() {
    if (!this.currentSession?.currentBlock) return;

    const block = this.currentSession.currentBlock;
    this.currentSession.blocks.push({
      itemIds: Array.from(block.itemIds),
      startedAt: block.startedAt,
      endedAt: new Date().toISOString(),
      toolCount: block.toolCount,
      categories: Array.from(block.categories || []),
      intent: this._classifyBlockIntent(block),
    });

    this.currentSession.currentBlock = null;
  }

  /**
   * Classify a work block's intent from the categories of tools used.
   * @param {object} block — current block with categories Set
   * @returns {string} — building|debugging|testing|exploring|thinking|mixed
   */
  _classifyBlockIntent(block) {
    const cats = block.categories || new Set();
    const hasWriting = cats.has('writing');
    const hasExecuting = cats.has('executing');
    const hasReading = cats.has('reading') || cats.has('searching');
    if (hasWriting && !hasExecuting) return 'building';
    if (hasWriting && hasExecuting) return 'debugging';
    if (hasExecuting && !hasWriting) return 'testing';
    if (hasReading && !hasWriting && !hasExecuting) return 'exploring';
    if (cats.size === 0) return 'thinking';
    return 'mixed';
  }

  // ---------------------------------------------------------------------------
  // Internal: Utilities
  // ---------------------------------------------------------------------------

  /**
   * Extract the meaningful content from tool input, truncated to 200 chars.
   * @param {object} input — raw tool input
   * @returns {string}
   */
  _truncateInput(input) {
    if (!input) return '(no input)';

    // Prefer the most descriptive field
    const raw = input.content
      || input.new_string
      || input.command
      || input.new_source
      || input.old_string
      || input.pattern
      || input.query
      || (typeof input === 'string' ? input : JSON.stringify(input));

    const str = typeof raw === 'string' ? raw : JSON.stringify(raw);
    return str.length > 200 ? str.slice(0, 197) + '...' : str;
  }

  /**
   * Extract JSON from Haiku output, handling possible markdown fences.
   * @param {string} text — raw stdout from Haiku
   * @returns {object}
   */
  _extractJSON(text) {
    // Try direct parse first
    const trimmed = text.trim();
    try {
      return JSON.parse(trimmed);
    } catch {
      // Try extracting from markdown code fence
      const fenceMatch = trimmed.match(/```(?:json)?\s*\n?([\s\S]*?)\n?\s*```/);
      if (fenceMatch) {
        return JSON.parse(fenceMatch[1].trim());
      }
      // Try finding first { ... } block
      const braceMatch = trimmed.match(/\{[\s\S]*\}/);
      if (braceMatch) {
        return JSON.parse(braceMatch[0]);
      }
      throw new Error('No JSON found in output');
    }
  }

  /**
   * Convert session state (with Maps/Sets) to a plain serializable object.
   * @param {object} session
   * @returns {object}
   */
  _serialize(session) {
    const items = {};
    for (const [id, acc] of session.items) {
      items[id] = { ...acc };
    }

    return {
      id: session.id,
      startedAt: session.startedAt,
      endedAt: session.endedAt || null,
      endReason: session.endReason || null,
      source: session.source,
      toolCount: session.toolCount,
      items,
      blocks: session.blocks,
      commits: session.commits,
      errors: session.errors || [],
      transcriptPath: session.transcriptPath || null,
    };
  }

  /**
   * Append a completed session to data/sessions.json.
   * @param {object} session — serialized session data
   */
  _persist(session) {
    try {
      const dir = path.dirname(SESSIONS_FILE);
      fs.mkdirSync(dir, { recursive: true });

      let sessions = [];
      try {
        const raw = fs.readFileSync(SESSIONS_FILE, 'utf-8');
        sessions = JSON.parse(raw);
        if (!Array.isArray(sessions)) sessions = [];
      } catch (parseErr) {
        if (parseErr.code !== 'ENOENT') {
          // Corrupted file — back up before overwriting
          const backup = SESSIONS_FILE + '.bak';
          try { fs.copyFileSync(SESSIONS_FILE, backup); } catch { /* best effort */ }
          console.warn(`[session] Corrupted sessions.json backed up to ${backup}`);
        }
      }

      sessions.push(session);
      fs.writeFileSync(SESSIONS_FILE, JSON.stringify(sessions, null, 2), 'utf-8');
      console.log(`[session] Persisted to ${SESSIONS_FILE} (${sessions.length} total sessions)`);
    } catch (err) {
      console.error('[session] Failed to persist session:', err.message);
    }
  }
}
