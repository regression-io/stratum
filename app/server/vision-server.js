/**
 * Vision Server — REST endpoints + WebSocket broadcast for the vision surface.
 * Follows the same attach() pattern as FileWatcherServer.
 */

import { WebSocketServer } from 'ws';
import { spawn } from 'node:child_process';
import path from 'node:path';
import fs from 'node:fs';
import { fileURLToPath } from 'node:url';
import { requireSensitiveToken } from './security.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PROJECT_ROOT = path.resolve(__dirname, '..');

// NOTE: Duplicated in src/components/Terminal.jsx — keep in sync
const TOOL_CATEGORIES = {
  Read: 'reading', Glob: 'searching', Grep: 'searching',
  Write: 'writing', Edit: 'writing', NotebookEdit: 'writing',
  Bash: 'executing', Task: 'delegating', Skill: 'delegating',
  WebFetch: 'fetching', WebSearch: 'searching',
  TodoRead: 'reading', TodoWrite: 'writing',
};

export class VisionServer {
  constructor(store, sessionManager = null) {
    this.store = store;
    this.sessionManager = sessionManager;
    this.clients = new Set();
    this.wss = null;
    this._broadcastTimer = null;
    this._pendingSnapshots = new Map();
  }

  attach(httpServer, app) {
    // REST: GET /api/vision/items — full state
    app.get('/api/vision/items', (_req, res) => {
      res.json(this.store.getState());
    });

    // REST: POST /api/vision/items — create item
    app.post('/api/vision/items', (req, res) => {
      try {
        const item = this.store.createItem(req.body);
        this.scheduleBroadcast();
        res.status(201).json(item);
      } catch (err) {
        res.status(400).json({ error: err.message });
      }
    });

    // REST: PATCH /api/vision/items/:id — update item
    app.patch('/api/vision/items/:id', (req, res) => {
      try {
        const item = this.store.updateItem(req.params.id, req.body);
        this.scheduleBroadcast();
        res.json(item);
      } catch (err) {
        const status = err.message.includes('not found') ? 404 : 400;
        res.status(status).json({ error: err.message });
      }
    });

    // REST: DELETE /api/vision/items/:id — delete item + connections
    app.delete('/api/vision/items/:id', (req, res) => {
      try {
        this.store.deleteItem(req.params.id);
        this.scheduleBroadcast();
        res.json({ ok: true });
      } catch (err) {
        res.status(404).json({ error: err.message });
      }
    });

    // REST: POST /api/vision/connections — create connection
    app.post('/api/vision/connections', (req, res) => {
      try {
        const conn = this.store.createConnection(req.body);
        this.scheduleBroadcast();
        res.status(201).json(conn);
      } catch (err) {
        res.status(400).json({ error: err.message });
      }
    });

    // REST: DELETE /api/vision/connections/:id — delete connection
    app.delete('/api/vision/connections/:id', (req, res) => {
      try {
        this.store.deleteConnection(req.params.id);
        this.scheduleBroadcast();
        res.json({ ok: true });
      } catch (err) {
        res.status(404).json({ error: err.message });
      }
    });

    // REST: GET /api/vision/items/:id — get single item by ID
    app.get('/api/vision/items/:id', (req, res) => {
      const items = this.store.getState().items;
      const item = items.find(i => i.id === req.params.id);
      if (!item) {
        return res.status(404).json({ error: `Item not found: ${req.params.id}` });
      }
      // Include connections involving this item
      const connections = this.store.getState().connections.filter(
        c => c.fromId === req.params.id || c.toId === req.params.id
      );
      res.json({ ...item, connections });
    });

    // REST: GET /api/vision/summary — structured board summary
    app.get('/api/vision/summary', (_req, res) => {
      const { items, connections } = this.store.getState();
      const byPhase = {};
      const byStatus = {};
      const byType = {};
      let totalConfidence = 0;
      let confidenceCount = 0;
      let openQuestions = 0;
      let blockedItems = 0;

      for (const item of items) {
        const phase = item.phase || 'unassigned';
        byPhase[phase] = (byPhase[phase] || 0) + 1;

        const status = item.status || 'planned';
        byStatus[status] = (byStatus[status] || 0) + 1;

        const type = item.type || 'artifact';
        byType[type] = (byType[type] || 0) + 1;

        if (typeof item.confidence === 'number') {
          totalConfidence += item.confidence;
          confidenceCount++;
        }

        if (item.type === 'question' && item.status !== 'complete' && item.status !== 'killed') {
          openQuestions++;
        }

        if (item.status === 'blocked') {
          blockedItems++;
        }
      }

      res.json({
        totalItems: items.length,
        totalConnections: connections.length,
        byPhase,
        byStatus,
        byType,
        openQuestions,
        blockedItems,
        avgConfidence: confidenceCount > 0 ? Math.round((totalConfidence / confidenceCount) * 100) / 100 : 0,
      });
    });

    // REST: GET /api/vision/blocked — items blocked by non-complete items
    app.get('/api/vision/blocked', (_req, res) => {
      const { items, connections } = this.store.getState();
      const itemMap = new Map(items.map(i => [i.id, i]));

      // Find items that have incoming 'blocks' connections from non-complete items
      const blocked = [];
      for (const conn of connections) {
        if (conn.type === 'blocks') {
          const blocker = itemMap.get(conn.fromId);
          const target = itemMap.get(conn.toId);
          if (blocker && target && blocker.status !== 'complete' && blocker.status !== 'killed') {
            blocked.push({
              item: target,
              blockedBy: blocker,
              connectionId: conn.id,
            });
          }
        }
      }

      res.json({ blocked, count: blocked.length });
    });

    // REST: POST /api/vision/ui — push UI commands (lens, layout, phase)
    app.post('/api/vision/ui', (req, res) => {
      this.broadcastMessage({ type: 'visionUI', ...req.body });
      res.json({ ok: true });
    });

    // REST: POST /api/agent/activity — receive tool use events from hooks
    app.post('/api/agent/activity', (req, res) => {
      const { tool, input, response, timestamp } = req.body || {};
      if (!tool) return res.status(400).json({ error: 'tool is required' });

      let detail = null;
      let filePath = null;
      if (input) {
        filePath = input.file_path || null;
        detail = filePath || input.command || input.pattern || input.query || input.url || input.prompt || null;
        if (detail && detail.length > 120) detail = detail.slice(0, 117) + '...';
      }

      // Resolve file to tracker items
      const items = filePath ? this.resolveItems(filePath) : [];

      // Auto-status: Write/Edit on planned items → in_progress
      if (['Write', 'Edit'].includes(tool) && filePath) {
        for (const item of items) {
          if (item.status === 'planned') {
            try {
              this.store.updateItem(item.id, { status: 'in_progress' });
              this.scheduleBroadcast();
            } catch { /* ignore */ }
          }
        }
      }

      const category = TOOL_CATEGORIES[tool] || 'thinking';

      // Feed session accumulator
      if (this.sessionManager) {
        this.sessionManager.recordActivity(tool, category, filePath, input, items);
      }

      // Check response for error patterns (Bash tool responses, primarily)
      let error = null;
      if (response && typeof response === 'string') {
        error = this._detectError(tool, input, response);
      }

      // If error detected, record it and broadcast separately
      if (error) {
        if (this.sessionManager) {
          this.sessionManager.recordError(tool, filePath, error.type, error.severity, error.message, items);
        }
        this.broadcastMessage({
          type: 'agentError',
          errorType: error.type,
          severity: error.severity,
          message: error.message,
          tool,
          detail,
          items: items.map(i => ({ id: i.id, title: i.title })),
          timestamp: timestamp || new Date().toISOString(),
        });
      }

      this.broadcastMessage({
        type: 'agentActivity',
        tool,
        category,
        detail,
        error: error ? { type: error.type, severity: error.severity } : null,
        items: items.map(i => ({ id: i.id, title: i.title, status: i.status })),
        timestamp: timestamp || new Date().toISOString(),
      });

      res.json({ ok: true });
    });

    // REST: POST /api/agent/error — receive PostToolUseFailure events from hooks
    app.post('/api/agent/error', (req, res) => {
      const { tool, input, error: errorMsg } = req.body || {};
      if (!tool) return res.status(400).json({ error: 'tool is required' });

      const filePath = input?.file_path || null;
      const items = filePath ? this.resolveItems(filePath) : [];

      // Classify the error
      const detected = this._detectError(tool, input, errorMsg || '') || {
        type: 'runtime_error',
        severity: 'error',
        message: errorMsg || 'Tool use failed',
      };

      if (this.sessionManager) {
        this.sessionManager.recordError(tool, filePath, detected.type, detected.severity, detected.message, items);
      }

      this.broadcastMessage({
        type: 'agentError',
        errorType: detected.type,
        severity: detected.severity,
        message: detected.message,
        tool,
        detail: filePath || input?.command || null,
        items: items.map(i => ({ id: i.id, title: i.title })),
        timestamp: new Date().toISOString(),
      });

      console.log(`[vision] Error detected: ${detected.type} (${detected.severity}) from ${tool}: ${detected.message.slice(0, 80)}`);
      res.json({ ok: true, detected });
    });

    // REST: POST /api/plan/parse — extract file paths from plan/spec markdown
    app.post('/api/plan/parse', (req, res) => {
      const { filePath, itemId } = req.body || {};
      if (!filePath) return res.status(400).json({ error: 'filePath required' });

      const fullPath = path.resolve(PROJECT_ROOT, filePath);
      if (!fullPath.startsWith(PROJECT_ROOT)) {
        return res.status(400).json({ error: 'Path must be within project' });
      }
      let content;
      try {
        content = fs.readFileSync(fullPath, 'utf-8');
      } catch (err) {
        return res.status(404).json({ error: `File not found: ${filePath}` });
      }

      const extracted = this.extractFilePaths(content);

      if (itemId) {
        const item = this.store.items.get(itemId);
        if (item) {
          const existing = item.files || [];
          const merged = [...new Set([...existing, ...extracted])];
          this.store.updateItem(itemId, { files: merged });
          this.scheduleBroadcast();
        }
      }

      res.json({ files: extracted, itemId: itemId || null });
    });

    // REST: POST /api/session/start — hook calls this on SessionStart
    app.post('/api/session/start', (req, res) => {
      const { source } = req.body || {};
      if (!this.sessionManager) return res.status(503).json({ error: 'No session manager' });
      const session = this.sessionManager.startSession(source || 'startup');
      const context = this.sessionManager.getContext();

      this.broadcastMessage({
        type: 'sessionStart',
        sessionId: session.id,
        source: source || 'startup',
        timestamp: new Date().toISOString(),
      });

      res.json({ sessionId: session.id, context });
    });

    // REST: POST /api/session/end — hook calls this on SessionEnd
    app.post('/api/session/end', async (req, res) => {
      const { reason, transcriptPath } = req.body || {};
      if (!this.sessionManager) return res.status(503).json({ error: 'No session manager' });
      const meetsThreshold = this.sessionManager.meetsJournalThreshold();
      const session = await this.sessionManager.endSession(reason, transcriptPath);
      if (!session) return res.json({ sessionId: null, persisted: false });
      let journalSpawned = false;
      if (meetsThreshold && transcriptPath) {
        this._spawnJournalAgent(session, transcriptPath);
        journalSpawned = true;
      }

      this.broadcastMessage({
        type: 'sessionEnd',
        sessionId: session.id,
        reason,
        toolCount: session.toolCount,
        duration: Math.round((new Date(session.endedAt) - new Date(session.startedAt)) / 1000),
        journalSpawned,
        timestamp: new Date().toISOString(),
      });

      res.json({ sessionId: session.id, persisted: true, journalSpawned });
    });

    // REST: GET /api/session/current — current session state
    app.get('/api/session/current', (_req, res) => {
      if (!this.sessionManager?.currentSession) return res.json({ session: null });
      const s = this.sessionManager.currentSession;
      const items = {};
      const allSummaries = [];
      for (const [id, acc] of s.items) {
        items[id] = { title: acc.title, reads: acc.reads, writes: acc.writes, summaries: acc.summaries };
        for (const summary of (acc.summaries || [])) {
          if (!summary) continue;
          allSummaries.push(typeof summary === 'string' ? { summary } : summary);
        }
      }
      res.json({
        session: {
          id: s.id, startedAt: s.startedAt, source: s.source, toolCount: s.toolCount,
          blockCount: s.blocks.length, errorCount: (s.errors || []).length, items,
          summaries: allSummaries,
        },
      });
    });

    // REST: GET /api/snapshot — request UI snapshot from connected client
    app.get('/api/snapshot', (req, res) => {
      const requestId = `snap-${Date.now()}`;
      const timeout = parseInt(req.query.timeout) || 3000;

      // Find a connected client to ask
      let target = null;
      for (const client of this.clients) {
        if (client.readyState === 1) { target = client; break; }
      }
      if (!target) {
        return res.status(503).json({ error: 'No connected clients' });
      }

      // Register pending request
      const timer = setTimeout(() => {
        this._pendingSnapshots.delete(requestId);
        res.status(504).json({ error: 'Snapshot timeout' });
      }, timeout);

      this._pendingSnapshots.set(requestId, { res, timer });

      // Ask the client for a snapshot
      try {
        target.send(JSON.stringify({ type: 'snapshotRequest', requestId }));
      } catch (err) {
        clearTimeout(timer);
        this._pendingSnapshots.delete(requestId);
        res.status(500).json({ error: err.message });
      }
    });

    // --- Hidden agent spawning ---
    // Tracks running agents: Map<id, { process, output, status, prompt }>
    this._agents = new Map();

    // POST /api/agent/spawn — spawn a hidden Claude subagent
    app.post('/api/agent/spawn', requireSensitiveToken, (req, res) => {
      const { prompt, id } = req.body || {};
      if (!prompt) return res.status(400).json({ error: 'prompt is required' });

      const agentId = id || `agent-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`;

      if (this._agents.has(agentId)) {
        return res.status(409).json({ error: `Agent ${agentId} already running` });
      }

      const cleanEnv = { ...process.env, NO_COLOR: '1' };
      delete cleanEnv.CLAUDECODE;

      const proc = spawn('claude', [
        '-p', prompt,
        '--dangerously-skip-permissions',
      ], {
        cwd: PROJECT_ROOT,
        env: cleanEnv,
        stdio: ['ignore', 'pipe', 'pipe'],
      });

      const agent = {
        process: proc,
        output: '',
        stderr: '',
        status: 'running',
        prompt,
        startedAt: new Date().toISOString(),
      };
      this._agents.set(agentId, agent);

      proc.stdout.on('data', (chunk) => {
        agent.output += chunk.toString();
      });

      proc.stderr.on('data', (chunk) => {
        agent.stderr += chunk.toString();
      });

      proc.on('close', (code) => {
        agent.status = code === 0 ? 'complete' : 'failed';
        agent.exitCode = code;
        // Broadcast agent completion to vision clients
        this.broadcastMessage({
          type: 'agentComplete',
          agentId,
          status: agent.status,
          output: agent.output,
        });
        // Clean up after 5 minutes
        setTimeout(() => this._agents.delete(agentId), 300_000);
      });

      proc.on('error', (err) => {
        agent.status = 'failed';
        agent.stderr += err.message;
        console.error(`[vision] Agent ${agentId} spawn error:`, err.message);
      });

      console.log(`[vision] Agent ${agentId} spawned (PID ${proc.pid})`);
      res.status(201).json({ agentId, pid: proc.pid, status: 'running' });
    });

    // GET /api/agent/:id — poll agent status + output
    app.get('/api/agent/:id', (req, res) => {
      const agent = this._agents.get(req.params.id);
      if (!agent) return res.status(404).json({ error: 'Agent not found' });
      res.json({
        agentId: req.params.id,
        status: agent.status,
        output: agent.output,
        stderr: agent.stderr,
        exitCode: agent.exitCode,
        startedAt: agent.startedAt,
      });
    });

    // GET /api/agents — list all agents
    app.get('/api/agents', (_req, res) => {
      const agents = [];
      for (const [id, agent] of this._agents) {
        agents.push({
          agentId: id,
          status: agent.status,
          startedAt: agent.startedAt,
          outputLength: agent.output.length,
        });
      }
      res.json({ agents });
    });

    // ─── Speckit routes (T3-7) ────────────────────────────────────────────────

    // REST: GET /api/speckit/scan — scan .specify/ and return features + tasks
    app.get('/api/speckit/scan', (_req, res) => {
      try {
        const features = this._scanSpeckit();
        res.json({ features, count: features.length });
      } catch (err) {
        res.status(500).json({ error: err.message });
      }
    });

    // REST: POST /api/speckit/seed — upsert .specify/ features + tasks into vision store
    app.post('/api/speckit/seed', (_req, res) => {
      try {
        const features = this._scanSpeckit();
        const seeded = this._seedSpeckit(features);
        this.scheduleBroadcast();
        res.json({ ok: true, ...seeded });
      } catch (err) {
        res.status(500).json({ error: err.message });
      }
    });

    // ─── Stratum routes (T3-8, T3-9) ─────────────────────────────────────────

    // REST: GET /api/stratum/flows — list persisted flow states from ~/.stratum/flows/
    app.get('/api/stratum/flows', (_req, res) => {
      try {
        const flows = this._readStratumFlows();
        res.json({ flows, count: flows.length });
      } catch (err) {
        res.status(500).json({ error: err.message });
      }
    });

    // REST: POST /api/stratum/bind — link a stratum flow_id to a vision item
    // Body: { flowId, itemId }
    app.post('/api/stratum/bind', (req, res) => {
      const { flowId, itemId } = req.body || {};
      if (!flowId || !itemId) return res.status(400).json({ error: 'flowId and itemId required' });
      try {
        const item = this.store.updateItem(itemId, { stratumFlowId: flowId });
        this.scheduleBroadcast();
        res.json({ ok: true, itemId, flowId, item });
      } catch (err) {
        const status = err.message.includes('not found') ? 404 : 400;
        res.status(status).json({ error: err.message });
      }
    });

    // REST: POST /api/stratum/audit/:itemId — store audit trace in item evidence + emit session log event
    // Body: { trace } — output from stratum_audit tool (shape: {flow_id, flow_name, status, trace, total_duration_ms, ...})
    app.post('/api/stratum/audit/:itemId', (req, res) => {
      const { trace } = req.body || {};
      if (!trace) return res.status(400).json({ error: 'trace required' });
      try {
        const item = this.store.items.get(req.params.itemId);
        if (!item) return res.status(404).json({ error: `Item not found: ${req.params.itemId}` });
        // eslint-disable-next-line no-unused-vars
        const { stratumViolations: _v, violatedAt: _va, ...existingEvidence } = item.evidence || {};
        const evidence = { ...existingEvidence, stratumTrace: trace, tracedAt: new Date().toISOString() };
        const updates = { evidence };
        // Audit is the authoritative signal for flow completion — drive the status transition here
        if (trace.status === 'complete' && item.status !== 'complete') {
          updates.status = 'complete';
        }
        const updatedItem = this.store.updateItem(req.params.itemId, updates);
        this.scheduleBroadcast();

        // Emit session-log event so audit trace surfaces in the AgentPanel log
        const stepsCompleted = Array.isArray(trace.trace) ? trace.trace.length : 0;
        const totalMs = trace.total_duration_ms || null;
        this.broadcastMessage({
          type: 'agentActivity',
          tool: 'stratum_audit',
          category: 'delegating',
          detail: `${trace.flow_name || trace.flow_id}: ${stepsCompleted} steps${totalMs != null ? `, ${(totalMs / 1000).toFixed(1)}s` : ''}`,
          error: null,
          items: [{ id: updatedItem.id, title: updatedItem.title, status: updatedItem.status }],
          timestamp: new Date().toISOString(),
        });

        res.json({ ok: true, itemId: req.params.itemId });
      } catch (err) {
        res.status(500).json({ error: err.message });
      }
    });

    // Start stratum flow state poller (every 15s)
    this._startStratumPoller();

    // Wire Haiku summary broadcast
    if (this.sessionManager) {
      this.sessionManager.onSummary((summary) => {
        this.broadcastMessage({ type: 'sessionSummary', ...summary, timestamp: new Date().toISOString() });
      });
    }

    // WebSocket
    this.wss = new WebSocketServer({ noServer: true, perMessageDeflate: false });

    this.wss.on('connection', (ws) => {
      this.clients.add(ws);
      console.log(`[vision] Client connected (${this.clients.size} total)`);

      // Send full state on connect
      try {
        ws.send(JSON.stringify({ type: 'visionState', ...this.store.getState() }));
      } catch (err) {
        console.error('[vision] Error sending initial state:', err.message);
      }

      ws.on('message', (data) => {
        try {
          const msg = JSON.parse(data);
          if (msg.type === 'snapshotResponse' && msg.requestId) {
            const pending = this._pendingSnapshots.get(msg.requestId);
            if (pending) {
              clearTimeout(pending.timer);
              this._pendingSnapshots.delete(msg.requestId);
              pending.res.json(msg.snapshot);
            }
          }
        } catch {
          // ignore malformed messages
        }
      });

      ws.on('close', () => {
        this.clients.delete(ws);
        console.log(`[vision] Client disconnected (${this.clients.size} total)`);
      });

      ws.on('error', (err) => {
        console.error('[vision] WebSocket error:', err.message);
        this.clients.delete(ws);
      });
    });

    console.log('Vision server attached (REST + WebSocket at /ws/vision)');
  }

  /** Schedule a debounced broadcast (100ms) to coalesce rapid mutations */
  scheduleBroadcast() {
    if (this._broadcastTimer) clearTimeout(this._broadcastTimer);
    this._broadcastTimer = setTimeout(() => {
      this._broadcastTimer = null;
      this.broadcastState();
    }, 100);
  }

  /** Broadcast full state to all connected clients */
  broadcastState() {
    this.broadcastMessage({ type: 'visionState', ...this.store.getState() });
  }

  /** Broadcast any message to all connected clients */
  broadcastMessage(msg) {
    const data = JSON.stringify(msg);
    for (const client of this.clients) {
      if (client.readyState === 1) {
        try {
          client.send(data);
        } catch (err) {
          console.error('[vision] Broadcast error:', err.message);
        }
      }
    }
  }

  /**
   * Pattern-match known error signatures in tool responses or error strings.
   * Returns { type, severity, message } or null.
   */
  _detectError(tool, input, responseText) {
    if (!responseText || typeof responseText !== 'string') return null;

    const text = responseText;

    // Only check Bash responses and explicit error strings (PostToolUseFailure)
    // Read/Write/Edit failures come through PostToolUseFailure with an error field
    const ERROR_PATTERNS = [
      { type: 'build_error', severity: 'error', patterns: [/SyntaxError/i, /TypeError/i, /Cannot find module/i, /Build failed/i, /npm ERR!/i, /error TS\d/i, /ReferenceError/i] },
      { type: 'test_failure', severity: 'error', patterns: [/FAIL /,  /failures?:/i, /AssertionError/i, /AssertionError/i, /tests? failed/i, /\u2715/, /\u2717/] },
      { type: 'git_conflict', severity: 'error', patterns: [/CONFLICT/i, /merge conflict/i, /rebase failed/i] },
      { type: 'permission_error', severity: 'error', patterns: [/EACCES/i, /EPERM/i, /permission denied/i] },
      { type: 'not_found', severity: 'warning', patterns: [/ENOENT/i, /No such file/i, /command not found/i] },
      { type: 'lint_error', severity: 'warning', patterns: [/eslint.*error/i, /prettier.*error/i] },
      { type: 'runtime_error', severity: 'error', patterns: [/Unhandled/i, /FATAL/i, /panic:/i, /Traceback/i] },
    ];

    for (const { type, severity, patterns } of ERROR_PATTERNS) {
      for (const pattern of patterns) {
        const match = text.match(pattern);
        if (match) {
          // Extract a meaningful message: the line containing the match
          const idx = text.indexOf(match[0]);
          const lineStart = text.lastIndexOf('\n', idx) + 1;
          const lineEnd = text.indexOf('\n', idx);
          const line = text.slice(lineStart, lineEnd === -1 ? undefined : lineEnd).trim();
          const message = line.length > 150 ? line.slice(0, 147) + '...' : line;
          return { type, severity, message };
        }
      }
    }

    return null;
  }

  // ─── Speckit helpers (T3-7) ─────────────────────────────────────────────────

  /** Scan .specify/ directory and return structured feature + task data */
  _scanSpeckit() {
    const specDir = path.join(PROJECT_ROOT, '.specify');
    if (!fs.existsSync(specDir)) return [];

    const features = [];
    let entries;
    try {
      entries = fs.readdirSync(specDir, { withFileTypes: true });
    } catch {
      return [];
    }

    for (const entry of entries) {
      if (!entry.isDirectory()) continue;
      const featureDir = path.join(specDir, entry.name);
      const feature = { name: entry.name, tasks: [] };

      // Read spec.md for description
      const specPath = path.join(featureDir, 'spec.md');
      if (fs.existsSync(specPath)) {
        try {
          const raw = fs.readFileSync(specPath, 'utf-8');
          // Extract first non-heading paragraph as description
          const lines = raw.split('\n');
          const descLines = [];
          let pastHeading = false;
          for (const line of lines) {
            if (!pastHeading && line.startsWith('#')) { pastHeading = true; continue; }
            if (pastHeading && line.trim()) { descLines.push(line.trim()); }
            if (descLines.length >= 3) break;
          }
          feature.description = descLines.join(' ');
        } catch { /* skip */ }
      }

      // Read tasks/*.md
      const tasksDir = path.join(featureDir, 'tasks');
      if (fs.existsSync(tasksDir)) {
        let taskFiles;
        try {
          taskFiles = fs.readdirSync(tasksDir).filter(f => f.endsWith('.md')).sort();
        } catch { taskFiles = []; }

        for (const taskFile of taskFiles) {
          try {
            const taskContent = fs.readFileSync(path.join(tasksDir, taskFile), 'utf-8');
            const titleMatch = taskContent.match(/^#\s+(.+)$/m);
            feature.tasks.push({
              filename: taskFile,
              title: titleMatch ? titleMatch[1].trim() : taskFile.replace(/\.md$/, ''),
            });
          } catch { /* skip */ }
        }
      }

      features.push(feature);
    }

    return features;
  }

  /** Upsert .specify/ features and tasks into the vision store */
  _seedSpeckit(features) {
    const seeded = { features: 0, tasks: 0, updated: 0 };

    for (const feature of features) {
      const featureKey = `speckit:feature:${feature.name}`;

      // Find existing item or create new one
      let featureItem = Array.from(this.store.items.values()).find(i => i.speckitKey === featureKey);

      if (!featureItem) {
        featureItem = this.store.createItem({
          type: 'feature',
          title: feature.name,
          description: feature.description || '',
          status: 'planned',
          phase: 'planning',
          files: [`.specify/${feature.name}/`],
        });
        this.store.updateItem(featureItem.id, { speckitKey: featureKey });
        featureItem = this.store.items.get(featureItem.id);
        seeded.features++;
      } else if (feature.description && featureItem.description !== feature.description) {
        this.store.updateItem(featureItem.id, { description: feature.description });
        seeded.updated++;
      }

      // Seed tasks
      for (const task of feature.tasks) {
        const taskKey = `speckit:task:${feature.name}:${task.filename}`;
        let taskItem = Array.from(this.store.items.values()).find(i => i.speckitKey === taskKey);

        if (!taskItem) {
          taskItem = this.store.createItem({
            type: 'task',
            title: task.title,
            description: '',
            status: 'planned',
            phase: 'implementation',
            parentId: featureItem.id,
            files: [`.specify/${feature.name}/tasks/${task.filename}`],
          });
          this.store.updateItem(taskItem.id, { speckitKey: taskKey });
          taskItem = this.store.items.get(taskItem.id);
          seeded.tasks++;

          // Connect task → feature (implements)
          try {
            this.store.createConnection({ fromId: taskItem.id, toId: featureItem.id, type: 'implements' });
          } catch { /* connection may already exist */ }
        } else if (taskItem.title !== task.title) {
          this.store.updateItem(taskItem.id, { title: task.title });
          seeded.updated++;
        }
      }
    }

    console.log(`[vision] Speckit seed: ${seeded.features} new features, ${seeded.tasks} new tasks, ${seeded.updated} updated`);
    return seeded;
  }

  // ─── Stratum helpers (T3-8) ──────────────────────────────────────────────────

  /** Read all persisted flow states from ~/.stratum/flows/ */
  _readStratumFlows() {
    const flowsDir = path.join(process.env.HOME || process.env.USERPROFILE || '', '.stratum', 'flows');
    if (!fs.existsSync(flowsDir)) return [];

    const flows = [];
    let files;
    try {
      files = fs.readdirSync(flowsDir).filter(f => f.endsWith('.json'));
    } catch { return []; }

    for (const file of files) {
      try {
        const raw = fs.readFileSync(path.join(flowsDir, file), 'utf-8');
        const state = JSON.parse(raw);
        // Persisted shape: { flow_id, flow_name, records: [{step_id, function_name, attempts, duration_ms}],
        //                    attempts: {step_id: N}, current_idx: N, step_outputs: {...} }
        const records = Array.isArray(state.records) ? state.records : [];
        const attempts = state.attempts || {};
        const stepOutputIds = new Set(Object.keys(state.step_outputs || {}));
        const completedIds = new Set(records.map(r => r.step_id));

        // In-flight: step has an attempt count but no record yet (ensure_failed retry pending)
        const hasInFlight = Object.keys(attempts).some(sid => !completedIds.has(sid));

        // Exhausted: step is in records but NOT in step_outputs → retries_exhausted
        // (successful completion adds to both records AND step_outputs; exhaustion adds only to records)
        const exhaustedSteps = records.filter(r => !stepOutputIds.has(r.step_id));
        const hasExhausted = exhaustedSteps.length > 0;

        // Status hierarchy: running > blocked > paused
        // NOTE: 'complete' is NOT detectable via polling (requires knowing total step count).
        // Complete transitions are driven by the /api/stratum/audit endpoint instead.
        const status = hasInFlight ? 'running' : hasExhausted ? 'blocked' : 'paused';

        flows.push({
          flowId: state.flow_id,
          flowName: state.flow_name || state.flow_id,
          status,
          stepsCompleted: stepOutputIds.size,  // only count steps that actually passed
          currentIdx: state.current_idx || 0,
          exhaustedSteps: exhaustedSteps.map(r => ({ stepId: r.step_id, attempts: r.attempts })),
          steps: records.map(r => ({
            id: r.step_id,
            status: stepOutputIds.has(r.step_id) ? 'complete' : 'failed',
            attempts: r.attempts,
            duration_ms: r.duration_ms,
          })),
        });
      } catch { /* skip malformed files */ }
    }

    return flows;
  }

  /** Poll stratum flow states and update bound vision items */
  _startStratumPoller() {
    this._stratumPollTimer = setInterval(() => {
      try {
        this._syncStratumFlows();
      } catch (err) {
        console.error('[vision] Stratum poll error:', err.message);
      }
    }, 15_000);
  }

  /** Sync stratum flow states → vision item statuses + violation evidence */
  _syncStratumFlows() {
    const flows = this._readStratumFlows();
    if (flows.length === 0) return;

    const flowMap = new Map(flows.map(f => [f.flowId, f]));
    let changed = false;

    for (const item of this.store.items.values()) {
      if (!item.stratumFlowId) continue;
      const flow = flowMap.get(item.stratumFlowId);
      if (!flow) continue;

      // running → in_progress; blocked → blocked; paused → no regression
      // complete is NOT set here — driven by /api/stratum/audit endpoint instead
      const targetStatus = flow.status === 'running' ? 'in_progress'
        : flow.status === 'blocked' ? 'blocked'
        : null; // paused: don't regress

      if (targetStatus && targetStatus !== item.status) {
        try {
          this.store.updateItem(item.id, { status: targetStatus });
          changed = true;
        } catch { /* ignore */ }
      }

      // P2: surface exhausted steps as blocker evidence; clear when flow is no longer blocked
      const existing = item.evidence || {};
      if (flow.status === 'blocked' && flow.exhaustedSteps.length > 0) {
        const violations = flow.exhaustedSteps.map(s =>
          `Step '${s.stepId}' exhausted retries after ${s.attempts} attempt${s.attempts !== 1 ? 's' : ''}`
        );
        const needsUpdate = JSON.stringify(existing.stratumViolations) !== JSON.stringify(violations);
        if (needsUpdate) {
          try {
            this.store.updateItem(item.id, {
              evidence: { ...existing, stratumViolations: violations, violatedAt: new Date().toISOString() },
            });
            changed = true;
          } catch { /* ignore */ }
        }
      } else if (existing.stratumViolations) {
        // Flow recovered or completed — clear stale violation evidence
        try {
          const { stratumViolations: _, violatedAt: __, ...rest } = existing;
          this.store.updateItem(item.id, { evidence: rest });
          changed = true;
        } catch { /* ignore */ }
      }
    }

    if (changed) this.scheduleBroadcast();
  }

  close() {
    if (this._stratumPollTimer) clearInterval(this._stratumPollTimer);
    for (const client of this.clients) {
      client.close();
    }
    this.clients.clear();
    if (this.wss) this.wss.close();
  }

  /** Resolve a file path to matching tracker items */
  resolveItems(filePath) {
    const rel = filePath.startsWith(PROJECT_ROOT)
      ? filePath.slice(PROJECT_ROOT.length + 1)
      : filePath.replace(/^\.\//, '');
    const matches = [];
    const matchType = new Map();

    for (const item of this.store.items.values()) {
      if (item.files && item.files.length > 0) {
        for (const pattern of item.files) {
          if (pattern.endsWith('/')) {
            if (rel.startsWith(pattern)) { matches.push(item); matchType.set(item.id, 'prefix'); break; }
          } else {
            if (rel === pattern) { matches.push(item); matchType.set(item.id, 'exact'); break; }
          }
        }
      }
      if (rel.startsWith('docs/') && item.slug) {
        const slug = this.extractSlugFromPath(rel);
        if (slug && slug === item.slug) {
          if (!matches.find(m => m.id === item.id)) {
            matches.push(item);
            matchType.set(item.id, 'slug');
          }
        }
      }
    }

    const specificity = { exact: 0, prefix: 1, slug: 2 };
    matches.sort((a, b) => {
      if (a.status === 'in_progress' && b.status !== 'in_progress') return -1;
      if (b.status === 'in_progress' && a.status !== 'in_progress') return 1;
      const sa = specificity[matchType.get(a.id)] ?? 3;
      const sb = specificity[matchType.get(b.id)] ?? 3;
      if (sa !== sb) return sa - sb;
      return new Date(b.updatedAt) - new Date(a.updatedAt);
    });

    return matches;
  }

  /** Extract slug from a docs/ file path */
  extractSlugFromPath(filePath) {
    const filename = filePath.split('/').pop().replace(/\.md$/, '');
    const noDate = filename.replace(/^\d{4}-\d{2}-\d{2}-/, '');
    const noSession = noDate.replace(/^session-\d+-/, '');
    const noSuffix = noSession.replace(/-(roadmap|plan|design|spec|eval|review)$/, '');
    return noSuffix || null;
  }

  /** Extract file paths from plan/spec markdown content */
  extractFilePaths(markdown) {
    const paths = new Set();
    const lines = markdown.split('\n');
    const extRe = /\.(jsx?|tsx?|mjs|css|json|md|sh|py)$/;
    const skipRe = /node_modules|dist\/|\.git\/|example|foo|bar|^node |^npm |^npx |test\.\w+$/;

    let inCodeFence = false;
    for (const line of lines) {
      if (line.trim().startsWith('```')) { inCodeFence = !inCodeFence; continue; }
      if (inCodeFence) continue;

      const backtickMatches = line.matchAll(/`([^`]+)`/g);
      for (const m of backtickMatches) {
        const p = m[1].replace(/^\*\*|\*\*$/g, '').trim();
        if (p.includes('/') && extRe.test(p) && !skipRe.test(p)) {
          paths.add(p.replace(/^\.\//, ''));
        }
      }

      const markerMatch = line.match(/[-*]\s+`?([^\s`]+)`?\s+\((?:new|existing)\)/);
      if (markerMatch) {
        const p = markerMatch[1].replace(/^\*\*|\*\*$/g, '').trim();
        if (p.includes('/') && !skipRe.test(p)) {
          paths.add(p.replace(/^\.\//, ''));
        }
      }
    }

    return Array.from(paths);
  }

  /** Spawn a hidden agent to write a journal entry from session data */
  _spawnJournalAgent(session, transcriptPath) {
    const itemSummaries = Object.entries(session.items || {})
      .map(([_id, data]) => `- ${data.title}: ${data.writes} writes, ${data.reads} reads. ${(data.summaries || []).map(s => s.summary || '').filter(Boolean).join('. ')}`)
      .join('\n');
    const blockSummaries = (session.blocks || [])
      .map((b, i) => `- Block ${i + 1}: ${b.itemIds.length} items, ${b.toolCount} tool uses`)
      .join('\n');

    // Compute duration from timestamps
    const startMs = new Date(session.startedAt).getTime();
    const endMs = session.endedAt ? new Date(session.endedAt).getTime() : Date.now();
    const durationSec = Math.round((endMs - startMs) / 1000);

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
- Duration: ${durationSec}s (${Math.round(durationSec / 60)} minutes)
- Tool uses: ${session.toolCount}
- Items worked on:\n${itemSummaries || '(none resolved)'}
- Work blocks:\n${blockSummaries || '(single block)'}
- Commits: ${(session.commits || []).join(', ') || '(none)'}
After writing the entry, update docs/journal/README.md with the new entry row.
Then commit both files.`;

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
}
