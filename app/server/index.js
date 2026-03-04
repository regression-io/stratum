import express from 'express';
import cors from 'cors';
import http from 'node:http';
import { FileWatcherServer } from './file-watcher.js';
import { VisionStore } from './vision-store.js';
import { VisionServer } from './vision-server.js';
import { SessionManager } from './session-manager.js';

// Handle unexpected errors — fatal startup errors exit (supervisor retries),
// runtime errors keep the process alive to preserve PTY sessions
let serverListening = false;
process.on('uncaughtException', (err) => {
  if (!serverListening && err.code === 'EADDRINUSE') {
    console.error(`[compose] Port in use, exiting for supervisor retry: ${err.message}`);
    process.exit(1);
  }
  console.error('[compose] Uncaught exception (process kept alive):', err.message);
  console.error(err.stack);
});
process.on('unhandledRejection', (reason) => {
  console.error('[compose] Unhandled rejection (process kept alive):', reason);
});
process.on('SIGTERM', () => {
  console.log('[compose] SIGTERM received, shutting down gracefully');
  process.exit(0);
});

const PORT = process.env.PORT || 3001;
const app = express();
app.use(cors({ origin: /^https?:\/\/(localhost|127\.0\.0\.1)(:\d+)?$/ }));
app.use(express.json());

app.get('/api/health', (_req, res) => res.json({ ok: true }));
app.get('/api/status', (_req, res) => res.json({ session: 2, phase: '0.4-brainstorm', upSince: new Date().toISOString() }));

const server = http.createServer(app);
const fileWatcher = new FileWatcherServer();
fileWatcher.attach(server, app);
const visionStore = new VisionStore();
const sessionManager = new SessionManager();
const visionServer = new VisionServer(visionStore, sessionManager);
visionServer.attach(server, app);

// Seed .specify/ into vision store on startup
try {
  const features = visionServer._scanSpeckit();
  if (features.length > 0) visionServer._seedSpeckit(features);
} catch (err) {
  console.error('[compose] Speckit startup seed error:', err.message);
}

// Wire .specify/ file changes → auto-reseed vision store
fileWatcher.onSpeckitChanged = (_relativePath) => {
  try {
    const features = visionServer._scanSpeckit();
    visionServer._seedSpeckit(features);
    visionServer.scheduleBroadcast();
  } catch (err) {
    console.error('[compose] Speckit reseed error:', err.message);
  }
};

// Manual WebSocket upgrade routing — avoids the ws library bug where multiple
// WebSocketServers on the same HTTP server write 400 on each other's connections
server.on('upgrade', (req, socket, head) => {
  const { pathname } = new URL(req.url, 'http://localhost');
  if (pathname === '/ws/files' && fileWatcher.wss) {
    fileWatcher.wss.handleUpgrade(req, socket, head, (ws) => {
      fileWatcher.wss.emit('connection', ws, req);
    });
  } else if (pathname === '/ws/vision' && visionServer.wss) {
    visionServer.wss.handleUpgrade(req, socket, head, (ws) => {
      visionServer.wss.emit('connection', ws, req);
    });
  } else {
    socket.destroy();
  }
});

server.listen(PORT, '127.0.0.1', () => {
  serverListening = true;
  console.log(`Compose server running on http://127.0.0.1:${PORT}`);
  console.log(`File watcher WebSocket: ws://localhost:${PORT}/ws/files`);
  console.log(`Vision WebSocket: ws://localhost:${PORT}/ws/vision`);
});
