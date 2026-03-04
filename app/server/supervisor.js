/**
 * Process supervisor for Compose.
 * Manages three independent processes:
 *   1. API server (port 3001) — Express + file-watcher + vision
 *   2. Agent server (port 3002) — SDK streaming, structured messages (Tier 1, immortal)
 *   3. Vite dev server (port 5173) — Frontend HMR
 *
 * Each process gets independent restart with exponential backoff.
 * If a process keeps crashing for > 1 minute, the supervisor gives up on it.
 *
 * Singleton enforcement: Uses a PID file to ensure only one supervisor runs.
 * Starting a new supervisor kills the old one and all its children first.
 */

import { fork, spawn, execFileSync } from 'node:child_process';
import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PROJECT_ROOT = path.resolve(__dirname, '..');
const PID_FILE = path.join(PROJECT_ROOT, '.compose-supervisor.pid');

const PROCESSES = [
  {
    name: 'api-server',
    path: path.join(__dirname, 'index.js'),
    port: process.env.PORT || 3001,
    type: 'fork',
  },
  {
    name: 'agent-server',
    path: path.join(__dirname, 'agent-server.js'),
    port: process.env.AGENT_PORT || 3002,
    type: 'fork',
  },
  {
    name: 'vite',
    command: path.join(PROJECT_ROOT, 'node_modules', '.bin', 'vite'),
    port: 5173,
    type: 'spawn',
  },
];

const MIN_BACKOFF = 500;
const MAX_BACKOFF = 10_000;
const HEALTHY_THRESHOLD = 5_000;
const GIVE_UP_AFTER = 60_000; // stop retrying after 1 min of continuous failures

let stopping = false;

function ensureComposeApiToken() {
  if (!process.env.COMPOSE_API_TOKEN) {
    process.env.COMPOSE_API_TOKEN = crypto.randomBytes(24).toString('hex');
    console.log('[supervisor] Generated COMPOSE_API_TOKEN for this session');
  }
  // Expose the same token to Vite client code.
  process.env.VITE_COMPOSE_API_TOKEN = process.env.COMPOSE_API_TOKEN;
  // Expose AGENT_PORT so AgentStream.jsx can reach the right port
  process.env.VITE_AGENT_PORT = process.env.AGENT_PORT || '3002';
}

// --- Singleton enforcement ---

function killExistingSupervisor() {
  try {
    const oldPid = parseInt(fs.readFileSync(PID_FILE, 'utf8').trim(), 10);
    if (oldPid && oldPid !== process.pid) {
      try {
        // Check if process exists
        process.kill(oldPid, 0);
        console.log(`[supervisor] Killing previous supervisor (PID ${oldPid})...`);
        process.kill(oldPid, 'SIGTERM');
        // Give it time to clean up children
        execFileSync('sleep', ['2']);
      } catch {
        // Process doesn't exist — stale PID file
      }
    }
  } catch {
    // No PID file — first run
  }
}

function writePidFile() {
  fs.writeFileSync(PID_FILE, String(process.pid));
}

function removePidFile() {
  try { fs.unlinkSync(PID_FILE); } catch {}
}

// Kill old supervisor before anything else
killExistingSupervisor();
ensureComposeApiToken();

// Kill anything listening on our ports (stale children from old supervisor)
function freePort(port, childPid) {
  try {
    const output = execFileSync('lsof', ['-ti', `:${port}`, '-sTCP:LISTEN'], {
      encoding: 'utf8',
      timeout: 3000,
    }).trim();
    if (!output) return;

    const myPid = process.pid;
    const pids = output.split('\n').map(p => parseInt(p, 10)).filter(Boolean);
    const stale = pids.filter(pid => pid !== myPid && pid !== childPid);

    if (stale.length > 0) {
      console.log(`[supervisor] Killing stale listener(s) on port ${port}: ${stale.join(', ')}`);
      for (const pid of stale) {
        try { process.kill(pid, 'SIGKILL'); } catch {}
      }
      execFileSync('sleep', ['1']);
    }
  } catch {
    // lsof returns non-zero if no matches — port is free
  }
}

// Free all ports before starting (clean slate)
for (const proc of PROCESSES) {
  if (proc.port) freePort(proc.port, null);
}

// Write our PID file
writePidFile();

// --- Process management ---

function startProcess(proc) {
  if (stopping) return;
  if (proc.port) freePort(proc.port, proc.child ? proc.child.pid : null);

  const startTime = Date.now();
  console.log(`[supervisor] Starting ${proc.name}...`);

  if (proc.type === 'fork') {
    proc.child = fork(proc.path, { stdio: 'inherit' });
  } else {
    proc.child = spawn(proc.command, [], {
      stdio: 'inherit',
      cwd: PROJECT_ROOT,
      env: process.env,
    });
  }

  proc.child.on('exit', (code, signal) => {
    if (stopping) return;

    const uptime = Date.now() - startTime;
    console.error(`[supervisor] ${proc.name} exited (code: ${code}, signal: ${signal}, uptime: ${uptime}ms)`);
    proc.child = null;

    if (uptime > HEALTHY_THRESHOLD) {
      proc.backoff = MIN_BACKOFF;
      proc.firstFailTime = null;
    } else {
      proc.backoff = Math.min((proc.backoff || MIN_BACKOFF) * 2, MAX_BACKOFF);
      if (!proc.firstFailTime) proc.firstFailTime = Date.now();

      if (Date.now() - proc.firstFailTime > GIVE_UP_AFTER) {
        console.error(`[supervisor] ${proc.name} has been failing for >1 min — giving up`);
        return;
      }
    }

    console.log(`[supervisor] Restarting ${proc.name} in ${proc.backoff}ms...`);
    setTimeout(() => startProcess(proc), proc.backoff);
  });
}

// Start all processes
for (const proc of PROCESSES) {
  proc.backoff = MIN_BACKOFF;
  proc.child = null;
  proc.firstFailTime = null;
  startProcess(proc);
}

// Forward termination signals to all children, then exit cleanly
for (const sig of ['SIGINT', 'SIGTERM']) {
  process.on(sig, () => {
    stopping = true;
    console.log(`[supervisor] ${sig} received, stopping all processes...`);
    for (const proc of PROCESSES) {
      if (proc.child) proc.child.kill(sig);
    }
    removePidFile();
    setTimeout(() => process.exit(0), 2000);
  });
}
