/**
 * File Watcher Server
 * Watches docs/ for changes and broadcasts file content over WebSocket.
 * Also serves file content via REST for initial loads.
 */

import { WebSocketServer } from 'ws';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PROJECT_ROOT = path.resolve(__dirname, '..');

export class FileWatcherServer {
  constructor() {
    this.clients = new Set();
    this.wss = null;
    this.watchers = [];
  }

  /** Resolve and validate a relative path stays within project root */
  safePath(relativePath) {
    const resolved = path.resolve(PROJECT_ROOT, relativePath);
    if (!resolved.startsWith(PROJECT_ROOT + path.sep) && resolved !== PROJECT_ROOT) {
      return null;
    }
    return resolved;
  }

  attach(httpServer, app) {
    // REST endpoint: GET /api/file?path=docs/brainstorm.md
    app.get('/api/file', (req, res) => {
      const filePath = req.query.path;
      if (!filePath) return res.status(400).json({ error: 'path required' });

      const resolved = this.safePath(filePath);
      if (!resolved) return res.status(403).json({ error: 'path outside project' });

      try {
        const content = fs.readFileSync(resolved, 'utf-8');
        res.json({ path: filePath, content });
      } catch (err) {
        if (err.code === 'ENOENT') return res.status(404).json({ error: 'file not found' });
        res.status(500).json({ error: err.message });
      }
    });

    // REST endpoint: GET /api/files — list markdown files in docs/
    app.get('/api/files', (_req, res) => {
      const docsDir = path.join(PROJECT_ROOT, 'docs');
      try {
        const files = this.listMarkdownFiles(docsDir, 'docs');
        res.json({ files });
      } catch (err) {
        res.status(500).json({ error: err.message });
      }
    });

    // REST endpoint: POST /api/canvas/open — agent can tell the canvas to load a file
    // Optional: { path, anchor } — anchor scrolls to a heading after opening
    // Special: vision://surface opens the vision surface tab
    app.post('/api/canvas/open', (req, res) => {
      const filePath = req.body.path;
      const anchor = req.body.anchor;
      if (!filePath) return res.status(400).json({ error: 'path required' });

      // Handle vision:// scheme — no file read, just broadcast open
      if (filePath.startsWith('vision://')) {
        this.broadcast({ type: 'openFile', path: filePath, content: null, rendererType: 'vision' });
        return res.json({ ok: true, path: filePath });
      }

      // Handle graph:// scheme — opens a named graph in the GraphRenderer
      if (filePath.startsWith('graph://')) {
        this.broadcast({ type: 'openFile', path: filePath, content: null, rendererType: 'graph' });
        return res.json({ ok: true, path: filePath });
      }

      const resolved = this.safePath(filePath);
      if (!resolved) return res.status(403).json({ error: 'path outside project' });

      try {
        const content = fs.readFileSync(resolved, 'utf-8');
        this.broadcast({ type: 'openFile', path: filePath, content, anchor });
        res.json({ ok: true, path: filePath, anchor });
      } catch (err) {
        if (err.code === 'ENOENT') return res.status(404).json({ error: 'file not found' });
        res.status(500).json({ error: err.message });
      }
    });

    // REST endpoint: POST /api/canvas/scroll — scroll to a heading in an open tab
    // { anchor, path? } — path switches tab first (file must already be open)
    app.post('/api/canvas/scroll', (req, res) => {
      const { anchor, path: filePath } = req.body;
      if (!anchor) return res.status(400).json({ error: 'anchor required' });
      this.broadcast({ type: 'scrollTo', anchor, path: filePath });
      res.json({ ok: true, anchor, path: filePath });
    });

    // REST endpoint: POST /api/canvas/close — close a tab (or all tabs)
    // { path? } — close specific tab, or omit to close all
    app.post('/api/canvas/close', (req, res) => {
      const filePath = req.body.path;
      this.broadcast({ type: 'closeFile', path: filePath || null });
      res.json({ ok: true, path: filePath || 'all' });
    });

    // WebSocket endpoint: /ws/files
    this.wss = new WebSocketServer({ noServer: true, perMessageDeflate: false });

    this.wss.on('connection', (ws) => {
      this.clients.add(ws);
      console.log(`[file-watcher] Client connected (${this.clients.size} total)`);

      ws.on('close', () => {
        this.clients.delete(ws);
        console.log(`[file-watcher] Client disconnected (${this.clients.size} total)`);
      });

      ws.on('error', (err) => {
        console.error('[file-watcher] WebSocket error:', err.message);
        this.clients.delete(ws);
      });
    });

    // Watch docs/ directory
    this.startWatching();
    console.log('File watcher WebSocket server attached at /ws/files');
  }

  startWatching() {
    const debounceMap = new Map();

    const watchDir = (dir, prefix, onChanged) => {
      if (!fs.existsSync(dir)) {
        console.warn(`[file-watcher] ${prefix}/ directory not found, skipping watch`);
        return;
      }
      try {
        const watcher = fs.watch(dir, { recursive: true }, (eventType, filename) => {
          if (!filename || !filename.endsWith('.md')) return;

          const relativePath = path.join(prefix, filename);
          const fullPath = path.join(PROJECT_ROOT, relativePath);

          // Debounce: ignore events within 100ms of each other for the same file
          const now = Date.now();
          const lastEvent = debounceMap.get(relativePath);
          if (lastEvent && now - lastEvent < 100) return;
          debounceMap.set(relativePath, now);

          onChanged(relativePath, fullPath);
        });
        this.watchers.push(watcher);
      } catch (err) {
        console.error(`[file-watcher] Failed to watch ${prefix}/:`, err.message);
      }
    };

    // Watch docs/ — broadcast fileChanged events
    watchDir(path.join(PROJECT_ROOT, 'docs'), 'docs', (relativePath, fullPath) => {
      try {
        if (!fs.existsSync(fullPath)) return;
        const content = fs.readFileSync(fullPath, 'utf-8');
        this.broadcast({ type: 'fileChanged', path: relativePath, content });
      } catch (err) {
        console.error(`[file-watcher] Error reading ${relativePath}:`, err.message);
      }
    });

    // Watch .specify/ — broadcast speckitChanged events (vision server will reseed)
    watchDir(path.join(PROJECT_ROOT, '.specify'), '.specify', (relativePath) => {
      this.broadcast({ type: 'speckitChanged', path: relativePath });
      // Notify registered speckit callback (set by VisionServer.attachSpeckitWatch)
      if (typeof this.onSpeckitChanged === 'function') {
        this.onSpeckitChanged(relativePath);
      }
    });
  }

  broadcast(message) {
    const data = JSON.stringify(message);
    for (const client of this.clients) {
      if (client.readyState === 1) {
        try {
          client.send(data);
        } catch (err) {
          console.error('[file-watcher] Broadcast error:', err.message);
        }
      }
    }
  }

  listMarkdownFiles(dir, prefix) {
    const results = [];
    try {
      const entries = fs.readdirSync(dir, { withFileTypes: true });
      for (const entry of entries) {
        const relativePath = path.join(prefix, entry.name);
        if (entry.isDirectory()) {
          results.push(...this.listMarkdownFiles(path.join(dir, entry.name), relativePath));
        } else if (entry.name.endsWith('.md')) {
          results.push(relativePath);
        }
      }
    } catch {
      // Directory might not exist or be readable
    }
    return results;
  }

  close() {
    for (const watcher of this.watchers) {
      watcher.close();
    }
    this.watchers = [];
    for (const client of this.clients) {
      client.close();
    }
    this.clients.clear();
    if (this.wss) this.wss.close();
  }
}
