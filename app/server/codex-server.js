/**
 * Codex Server (port 3003)
 *
 * Exposes CodexConnector over HTTP + SSE, mirroring the agent-server.js pattern.
 *
 * Endpoints:
 *   GET  /api/codex/stream         — SSE subscription (typed message stream)
 *   POST /api/codex/session        — start a new execution session
 *   POST /api/codex/message        — follow-up prompt (resumes by re-running)
 *   POST /api/codex/interrupt      — kill the active subprocess
 *   GET  /api/codex/status         — is a session active?
 *   POST /api/codex/review         — one-shot structured review (returns JSON)
 *   GET  /api/health               — liveness check
 */

import http from 'node:http';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import express from 'express';
import cors from 'cors';
import { CodexConnector } from './connectors/codex-connector.js';
import { requireSensitiveToken } from './security.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PROJECT_ROOT = path.resolve(__dirname, '..');
const PORT = process.env.CODEX_PORT || 3003;

const app = express();
app.use(cors({ origin: /^https?:\/\/(localhost|127\.0\.0\.1)(:\d+)?$/ }));
app.use(express.json());

app.get('/api/health', (_req, res) => res.json({ ok: true, agent: 'codex' }));

// ---------------------------------------------------------------------------
// Connector instance
// ---------------------------------------------------------------------------

const connector = new CodexConnector({
  model: process.env.CODEX_MODEL || 'o4-mini',
  reviewModel: process.env.CODEX_REVIEW_MODEL || 'o4-mini',
  cwd: PROJECT_ROOT,
});

// ---------------------------------------------------------------------------
// SSE broadcast
// ---------------------------------------------------------------------------

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
// GET /api/codex/stream — SSE subscription
// ---------------------------------------------------------------------------

app.get('/api/codex/stream', (req, res) => {
  res.setHeader('Content-Type', 'text/event-stream');
  res.setHeader('Cache-Control', 'no-cache');
  res.setHeader('Connection', 'keep-alive');
  res.setHeader('X-Accel-Buffering', 'no');
  res.flushHeaders();

  _sseClients.add(res);

  if (connector.isRunning) {
    res.write(`data: ${JSON.stringify({ type: 'system', subtype: 'connected', agent: 'codex', active: true })}\n\n`);
  }

  req.on('close', () => _sseClients.delete(res));
});

// ---------------------------------------------------------------------------
// POST /api/codex/session — start a new execution session
// ---------------------------------------------------------------------------

app.post('/api/codex/session', requireSensitiveToken, (req, res) => {
  const { prompt = '' } = req.body || {};
  if (!prompt.trim()) return res.status(400).json({ error: 'prompt is required' });

  if (connector.isRunning) connector.interrupt();

  res.json({ ok: true });
  _consumeStream(connector.run(prompt));
});

// ---------------------------------------------------------------------------
// POST /api/codex/message — follow-up prompt
// ---------------------------------------------------------------------------

app.post('/api/codex/message', requireSensitiveToken, (req, res) => {
  const { prompt = '' } = req.body || {};
  if (!prompt.trim()) return res.status(400).json({ error: 'prompt is required' });

  if (connector.isRunning) connector.interrupt();

  res.json({ ok: true });
  _consumeStream(connector.run(prompt));
});

// ---------------------------------------------------------------------------
// POST /api/codex/interrupt
// ---------------------------------------------------------------------------

app.post('/api/codex/interrupt', requireSensitiveToken, (req, res) => {
  connector.interrupt();
  res.json({ ok: true });
});

// ---------------------------------------------------------------------------
// GET /api/codex/status
// ---------------------------------------------------------------------------

app.get('/api/codex/status', (_req, res) => {
  res.json({ active: connector.isRunning, agent: 'codex' });
});

// ---------------------------------------------------------------------------
// POST /api/codex/review — one-shot structured review
// ---------------------------------------------------------------------------

app.post('/api/codex/review', requireSensitiveToken, async (req, res) => {
  const { prompt = '', model } = req.body || {};
  if (!prompt.trim()) return res.status(400).json({ error: 'prompt is required' });

  try {
    const result = await connector.review(prompt, { model });
    res.json(result);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// ---------------------------------------------------------------------------
// Stream consumer — drains the async generator and broadcasts each message
// ---------------------------------------------------------------------------

async function _consumeStream(gen) {
  try {
    for await (const msg of gen) {
      broadcast(msg);
    }
  } catch (err) {
    broadcast({ type: 'error', message: err.message || String(err) });
  }
}

// ---------------------------------------------------------------------------
// Server startup
// ---------------------------------------------------------------------------

let serverListening = false;
const server = http.createServer(app);

server.listen(PORT, '127.0.0.1', () => {
  serverListening = true;
  console.log(`Codex server running on http://127.0.0.1:${PORT}`);
});

function shutdown(sig) {
  console.log(`[codex-server] ${sig}, shutting down`);
  connector.interrupt();
  server.close();
  setTimeout(() => process.exit(0), 1000);
}

process.on('SIGTERM', () => shutdown('SIGTERM'));
process.on('SIGINT', () => shutdown('SIGINT'));

process.on('uncaughtException', (err) => {
  if (!serverListening && err.code === 'EADDRINUSE') {
    console.error(`[codex-server] Port ${PORT} in use, exiting for supervisor retry`);
    process.exit(1);
  }
  console.error('[codex-server] Uncaught exception (kept alive):', err.message);
  console.error(err.stack);
});

process.on('unhandledRejection', (reason) => {
  console.error('[codex-server] Unhandled rejection (kept alive):', reason);
});
