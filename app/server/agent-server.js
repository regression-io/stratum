/**
 * Agent Server (Tier 1 — immortal, port 3003 during migration, then 3002)
 *
 * Replaces terminal-server.js. Uses @anthropic-ai/claude-agent-sdk instead of
 * node-pty + tmux. Streams typed SDK messages via SSE to the browser.
 * User input arrives via POST — SSE is the right transport for a unidirectional
 * async iterator.
 *
 * Process isolation: this server only talks to api-server (3001) via SDK hooks.
 * SessionManager and VisionServer require zero changes.
 */

import http from 'node:http';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import express from 'express';
import cors from 'cors';
import { query } from '@anthropic-ai/claude-agent-sdk';
import { requireSensitiveToken } from './security.js';
import { HOOK_OPTIONS } from './agent-hooks.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PROJECT_ROOT = path.resolve(__dirname, '..');

const PORT = process.env.AGENT_PORT || 3002;

const app = express();
app.use(cors({ origin: /^https?:\/\/(localhost|127\.0\.0\.1)(:\d+)?$/ }));
app.use(express.json());

app.get('/api/health', (_req, res) => res.json({ ok: true }));

// ---------------------------------------------------------------------------
// Session state — one active SDK session at a time
// ---------------------------------------------------------------------------

/**
 * Active session state:
 *   id: string|null        — SDK session_id captured from init message
 *   queryIter: Query|null  — SDK async iterator, has .interrupt() method
 */
let _session = { id: null, queryIter: null };

/** SSE clients waiting for messages */
const _sseClients = new Set();

function broadcast(msg) {
  const line = `data: ${JSON.stringify(msg)}\n\n`;
  for (const client of _sseClients) {
    try {
      client.write(line);
    } catch {
      _sseClients.delete(client);
    }
  }
}

// ---------------------------------------------------------------------------
// GET /api/agent/stream — SSE subscription
// ---------------------------------------------------------------------------

app.get('/api/agent/stream', (req, res) => {
  res.setHeader('Content-Type', 'text/event-stream');
  res.setHeader('Cache-Control', 'no-cache');
  res.setHeader('Connection', 'keep-alive');
  res.setHeader('X-Accel-Buffering', 'no'); // disable nginx buffering if proxied
  res.flushHeaders();

  _sseClients.add(res);

  // Immediately tell the new client whether a session exists
  if (_session.id) {
    res.write(`data: ${JSON.stringify({
      type: 'system', subtype: 'connected', sessionId: _session.id,
    })}\n\n`);
  }

  req.on('close', () => _sseClients.delete(res));
});

// ---------------------------------------------------------------------------
// POST /api/agent/session — create a fresh session
// ---------------------------------------------------------------------------

app.post('/api/agent/session', requireSensitiveToken, (req, res) => {
  const { prompt = '' } = req.body || {};
  if (!prompt.trim()) return res.status(400).json({ error: 'prompt is required' });

  _killCurrentSession();

  try {
    const q = _startQuery(prompt, null);
    _session = { id: null, queryIter: q };
    _consumeStream(q);
    res.json({ ok: true });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// ---------------------------------------------------------------------------
// POST /api/agent/message — send a follow-up message (resumes session)
// ---------------------------------------------------------------------------

app.post('/api/agent/message', requireSensitiveToken, (req, res) => {
  const { prompt } = req.body || {};
  if (!prompt?.trim()) return res.status(400).json({ error: 'prompt is required' });

  const resumeId = _session.id;
  _killCurrentSession();

  try {
    const q = _startQuery(prompt, resumeId);
    _session = { id: resumeId, queryIter: q };
    _consumeStream(q);
    res.json({ ok: true, resumeSessionId: resumeId });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// ---------------------------------------------------------------------------
// POST /api/agent/interrupt — interrupt current query
// ---------------------------------------------------------------------------

app.post('/api/agent/interrupt', requireSensitiveToken, (req, res) => {
  if (!_session.queryIter) {
    return res.status(404).json({ error: 'No active query' });
  }
  try {
    _session.queryIter.interrupt();
    res.json({ ok: true });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// ---------------------------------------------------------------------------
// GET /api/agent/session/status
// ---------------------------------------------------------------------------

app.get('/api/agent/session/status', (_req, res) => {
  res.json({
    active: !!_session.queryIter,
    sessionId: _session.id || null,
  });
});

// ---------------------------------------------------------------------------
// Internals
// ---------------------------------------------------------------------------

function _buildOptions(prompt, resumeId) {
  return {
    cwd: PROJECT_ROOT,
    model: 'claude-sonnet-4-6',
    permissionMode: 'acceptEdits',
    settingSources: ['project'],
    tools: { type: 'preset', preset: 'claude_code' },
    hooks: HOOK_OPTIONS,
    ...(resumeId ? { resume: resumeId } : {}),
  };
}

function _startQuery(prompt, resumeId) {
  return query({ prompt, options: _buildOptions(prompt, resumeId) });
}

function _killCurrentSession() {
  if (_session.queryIter) {
    try { _session.queryIter.return(); } catch { /* ignore */ }
  }
  _session = { id: null, queryIter: null };
}

async function _consumeStream(q) {
  try {
    for await (const msg of q) {
      // Capture session_id from the init message so we can resume
      if (msg.type === 'system' && msg.subtype === 'init') {
        _session.id = msg.session_id;
      }
      broadcast(msg);
    }
  } catch (err) {
    if (err?.name !== 'AbortError') {
      broadcast({ type: 'error', message: err.message || String(err) });
    }
  } finally {
    // Signal completion to clients regardless of success/error
    if (_session.queryIter === q) {
      _session.queryIter = null;
    }
  }
}

// ---------------------------------------------------------------------------
// Server startup
// ---------------------------------------------------------------------------

let serverListening = false;
const server = http.createServer(app);

server.listen(PORT, '127.0.0.1', () => {
  serverListening = true;
  console.log(`Agent server running on http://127.0.0.1:${PORT}`);
});

function shutdown(sig) {
  console.log(`[agent-server] ${sig}, shutting down`);
  _killCurrentSession();
  server.close();
  setTimeout(() => process.exit(0), 1000);
}

process.on('SIGTERM', () => shutdown('SIGTERM'));
process.on('SIGINT', () => shutdown('SIGINT'));

process.on('uncaughtException', (err) => {
  if (!serverListening && err.code === 'EADDRINUSE') {
    console.error(`[agent-server] Port ${PORT} in use, exiting for supervisor retry`);
    process.exit(1);
  }
  console.error('[agent-server] Uncaught exception (kept alive):', err.message);
  console.error(err.stack);
});

process.on('unhandledRejection', (reason) => {
  console.error('[agent-server] Unhandled rejection (kept alive):', reason);
});
