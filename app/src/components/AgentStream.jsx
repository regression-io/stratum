import React, { useEffect, useRef, useState, useCallback } from 'react';
import MessageCard from './agent/MessageCard.jsx';
import ChatInput from './agent/ChatInput.jsx';

/**
 * AgentStream — structured SDK message stream + chat input.
 *
 * Replaces Terminal.jsx. Connects to agent-server via SSE (port 3002/3003),
 * renders typed SDK messages, and dispatches the same compose:agent-status
 * CustomEvent that AgentPanel.jsx listens for — so the sidebar needs zero changes.
 *
 * Singleton pattern (module-level _state) mirrors Terminal.jsx so that Vite HMR
 * unmount/remount cycles don't reset the message history or close the SSE stream.
 */

const AGENT_PORT = parseInt(import.meta.env.VITE_AGENT_PORT || '3002', 10);
const SESSION_STORAGE_KEY = 'compose-agent-session';
const MAX_MESSAGES = 500;
const MAX_ACTIVITY_LOG = 8;
const IDLE_DEBOUNCE_MS = 2000;

// Tool category mapping — matches agent-hooks.js (single source in prod,
// duplicated here so the client is self-contained at dev time)
const TOOL_CATEGORIES = {
  Read: 'reading', Glob: 'searching', Grep: 'searching',
  Write: 'writing', Edit: 'writing', NotebookEdit: 'writing',
  Bash: 'executing', Task: 'delegating', Skill: 'delegating',
  WebFetch: 'fetching', WebSearch: 'searching',
  TodoRead: 'reading', TodoWrite: 'writing',
};

const CATEGORY_LABELS = {
  reading: 'Reading', writing: 'Writing', executing: 'Running',
  searching: 'Searching', fetching: 'Fetching', delegating: 'Delegating',
  thinking: 'Thinking',
};

// ---------------------------------------------------------------------------
// Module-level singleton — survives Vite HMR remounts
// ---------------------------------------------------------------------------

const _state = {
  es: null,             // EventSource
  connected: false,
  connecting: false,
  reconnectTimer: null,
  reconnectAttempts: 0,
  sessionId: null,      // captured from system/init
  messages: [],         // SDKMessage[]
  agentStatus: 'idle',
  agentTool: null,
  agentCategory: null,
  currentActivity: null,
  activityLog: [],
  _idleTimer: null,
  // React setState callbacks — reattached on each mount
  onConnectedChange: null,
  onMessagesChange: null,
  onAgentStatusChange: null,
};

// ---------------------------------------------------------------------------
// Status derivation — replaces OSC title parsing
// ---------------------------------------------------------------------------

function deriveStatus(msg) {
  if (msg.type === 'assistant') {
    const content = msg.message?.content ?? [];
    for (const block of content) {
      if (block.type === 'tool_use') {
        const category = TOOL_CATEGORIES[block.name] || 'thinking';
        return { status: 'working', tool: block.name, category };
      }
    }
    // Text-only turn = thinking
    if (content.some(b => b.type === 'text')) {
      return { status: 'working', tool: null, category: 'thinking' };
    }
  }
  if (msg.type === 'result') {
    return { status: 'idle', tool: null, category: null };
  }
  return null; // no status change for this message type
}

function setAgentStatus(status, tool, category) {
  const now = Date.now();
  const prev = _state.agentStatus;
  const prevTool = _state.agentTool;

  if (_state._idleTimer) { clearTimeout(_state._idleTimer); _state._idleTimer = null; }

  // Log completed activities
  if (prev === 'working' && (status === 'idle' || tool !== prevTool)) {
    const entry = _state.currentActivity;
    if (entry) {
      entry.endTime = now;
      entry.duration = now - entry.startTime;
      _state.activityLog.push(entry);
      if (_state.activityLog.length > MAX_ACTIVITY_LOG) _state.activityLog.shift();
    }
  }

  // Start new activity
  if (status === 'working' && tool !== prevTool) {
    _state.currentActivity = { tool, category, startTime: now, endTime: null, duration: null };
  } else if (status === 'idle') {
    _state.currentActivity = null;
  }

  _state.agentStatus = status;
  _state.agentTool = tool;
  _state.agentCategory = category;

  const payload = {
    status, tool, category,
    activityLog: _state.activityLog,
    currentActivity: _state.currentActivity,
  };

  if (_state.onAgentStatusChange) _state.onAgentStatusChange({ ...payload });
  window.dispatchEvent(new CustomEvent('compose:agent-status', { detail: payload }));
}

function processMessage(msg) {
  // Derive and apply agent status before appending to list
  const derived = deriveStatus(msg);
  if (derived) {
    if (derived.status === 'idle') {
      // Debounce idle — result message arrives, wait briefly before going idle
      _state._idleTimer = setTimeout(() => {
        _state._idleTimer = null;
        setAgentStatus('idle', null, null);
      }, IDLE_DEBOUNCE_MS);
    } else {
      setAgentStatus(derived.status, derived.tool, derived.category);
    }
  }

  // Capture session ID from init
  if (msg.type === 'system' && msg.subtype === 'init' && msg.session_id) {
    _state.sessionId = msg.session_id;
    sessionStorage.setItem(SESSION_STORAGE_KEY, msg.session_id);
  }

  // Append message (skip stream_event noise)
  if (msg.type === 'stream_event' || msg.type === 'tool_progress' || msg.type === 'tool_use_summary') {
    return; // don't render these
  }

  _state.messages = [..._state.messages, msg];
  if (_state.messages.length > MAX_MESSAGES) {
    _state.messages = _state.messages.slice(-MAX_MESSAGES);
  }

  if (_state.onMessagesChange) _state.onMessagesChange(_state.messages);
}

// ---------------------------------------------------------------------------
// SSE connection management
// ---------------------------------------------------------------------------

function connect() {
  if (_state.connecting || (_state.es && _state.es.readyState === EventSource.OPEN)) return;
  _state.connecting = true;

  const sessionId = _state.sessionId || sessionStorage.getItem(SESSION_STORAGE_KEY);
  const url = `${window.location.protocol}//${window.location.hostname}:${AGENT_PORT}/api/agent/stream`;

  const es = new EventSource(url);
  _state.es = es;

  es.onopen = () => {
    _state.connecting = false;
    _state.reconnectAttempts = 0;
    _state.connected = true;
    if (_state.onConnectedChange) _state.onConnectedChange(true);
  };

  es.onmessage = (event) => {
    try {
      const msg = JSON.parse(event.data);
      processMessage(msg);
    } catch {
      // ignore parse errors
    }
  };

  es.onerror = () => {
    _state.connecting = false;
    _state.connected = false;
    if (_state.onConnectedChange) _state.onConnectedChange(false);
    es.close();
    if (_state.es === es) {
      _state.es = null;
      scheduleReconnect();
    }
  };
}

function scheduleReconnect() {
  if (_state.reconnectTimer) return;
  _state.reconnectAttempts = (_state.reconnectAttempts || 0) + 1;
  const delay = Math.min(1000 * Math.pow(2, _state.reconnectAttempts - 1), 8000);

  _state.reconnectTimer = setTimeout(() => {
    _state.reconnectTimer = null;
    // Health-check first
    fetch(`${window.location.protocol}//${window.location.hostname}:${AGENT_PORT}/api/health`)
      .then(r => { if (r.ok) connect(); else scheduleReconnect(); })
      .catch(() => scheduleReconnect());
  }, delay);
}

// ---------------------------------------------------------------------------
// REST helpers — send to agent-server
// ---------------------------------------------------------------------------

const COMPOSE_TOKEN = import.meta.env.VITE_COMPOSE_API_TOKEN;

async function postAgent(path, body) {
  const res = await fetch(
    `${window.location.protocol}//${window.location.hostname}:${AGENT_PORT}${path}`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-compose-token': COMPOSE_TOKEN || '',
      },
      body: JSON.stringify(body),
    }
  );
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: res.statusText }));
    throw new Error(err.error || res.statusText);
  }
  return res.json();
}

// ---------------------------------------------------------------------------
// AgentStream component
// ---------------------------------------------------------------------------

function formatElapsed(ms) {
  if (!ms) return '';
  if (ms < 1000) return '<1s';
  const s = Math.floor(ms / 1000);
  if (s < 60) return `${s}s`;
  return `${Math.floor(s / 60)}m ${s % 60}s`;
}

export default function AgentStream() {
  const [connected, setConnected] = useState(_state.connected);
  const [messages, setMessages] = useState(_state.messages);
  const [agentStatus, setAgentStatusState] = useState({
    status: _state.agentStatus,
    tool: _state.agentTool,
    category: _state.agentCategory,
    activityLog: _state.activityLog,
    currentActivity: _state.currentActivity,
  });
  const [sending, setSending] = useState(false);
  const [elapsed, setElapsed] = useState(null);
  const bottomRef = useRef(null);
  const isFirstMessage = messages.length === 0 || messages.every(
    m => m.type === 'system' && (m.subtype === 'init' || m.subtype === 'connected')
  );

  // Wire React state setters into singleton
  useEffect(() => {
    _state.onConnectedChange = setConnected;
    _state.onMessagesChange = setMessages;
    _state.onAgentStatusChange = setAgentStatusState;
    return () => {
      _state.onConnectedChange = null;
      _state.onMessagesChange = null;
      _state.onAgentStatusChange = null;
    };
  }, []);

  // Start SSE connection
  useEffect(() => {
    connect();
    // No cleanup: SSE survives HMR, same as old WebSocket pattern
  }, []);

  // Auto-scroll to bottom as messages arrive
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages.length]);

  // Tick elapsed time while working
  useEffect(() => {
    if (agentStatus.status !== 'working' || !agentStatus.currentActivity) {
      setElapsed(null);
      return;
    }
    const start = agentStatus.currentActivity.startTime;
    const tick = () => setElapsed(Date.now() - start);
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [agentStatus.status, agentStatus.currentActivity?.startTime]);

  const handleSend = useCallback(async (text) => {
    setSending(true);

    try {
      if (isFirstMessage || !_state.sessionId) {
        // First message — create a new session
        await postAgent('/api/agent/session', { prompt: text });
      } else {
        // Follow-up — resume existing session
        await postAgent('/api/agent/message', { prompt: text });
      }
    } catch (err) {
      // Inject an error message into the stream
      processMessage({ type: 'error', message: `Failed to send: ${err.message}` });
    } finally {
      setSending(false);
    }
  }, [isFirstMessage]);

  const handleInterrupt = useCallback(async () => {
    try {
      await postAgent('/api/agent/interrupt', {});
    } catch { /* ignore */ }
  }, []);

  const isWorking = connected && (agentStatus.status === 'working' || sending);
  const statusColor = !connected ? 'hsl(var(--destructive))' : isWorking ? '#fbbf24' : 'hsl(var(--success, 142 60% 50%))';
  const categoryLabel = agentStatus.category ? CATEGORY_LABELS[agentStatus.category] : null;
  const statusLabel = !connected ? 'offline' : isWorking ? (categoryLabel || 'working') : 'idle';
  const recentLog = agentStatus.activityLog || [];

  return (
    <div className="relative w-full h-full flex flex-col" style={{ background: 'hsl(var(--background))' }}>

      {/* Status bar */}
      <div
        className="shrink-0 flex items-center justify-between px-3 py-1.5"
        style={{ borderBottom: '1px solid hsl(var(--border) / 0.5)' }}
      >
        {/* Activity pills */}
        <div className="flex items-center gap-0.5">
          {connected && recentLog.length > 0 && recentLog.slice(-5).map((entry, i) => (
            <div
              key={i}
              className="h-1 rounded-full"
              title={`${entry.tool || 'thinking'} — ${formatElapsed(entry.duration)}`}
              style={{
                width: Math.max(6, Math.min(20, (entry.duration || 0) / 1000 * 2)),
                background: 'hsl(var(--muted-foreground))',
                opacity: 0.25 + (i / 5) * 0.5,
              }}
            />
          ))}
        </div>

        {/* Status dot + label */}
        <div className="flex items-center gap-1.5">
          {isWorking && (
            <button
              onClick={handleInterrupt}
              title="Interrupt"
              className="text-[10px] px-1.5 py-0.5 rounded"
              style={{
                background: 'hsl(var(--destructive) / 0.15)',
                color: 'hsl(var(--destructive))',
                border: '1px solid hsl(var(--destructive) / 0.3)',
                cursor: 'pointer',
              }}
            >
              stop
            </button>
          )}
          <div
            className="w-1.5 h-1.5 rounded-full flex-shrink-0"
            style={{ background: statusColor, animation: isWorking ? 'pulse 1.5s ease-in-out infinite' : 'none' }}
          />
          <span className="text-[10px] uppercase tracking-wider" style={{ color: isWorking ? '#fbbf24' : 'hsl(var(--muted-foreground))' }}>
            {statusLabel}
          </span>
          {isWorking && agentStatus.tool && (
            <span className="text-[10px] font-mono" style={{ color: 'hsl(var(--muted-foreground))' }}>
              {agentStatus.tool}
            </span>
          )}
          {isWorking && elapsed != null && (
            <span className="text-[10px] tabular-nums" style={{ color: 'hsl(var(--muted-foreground))', opacity: 0.6 }}>
              {formatElapsed(elapsed)}
            </span>
          )}
        </div>
      </div>

      {/* Message stream */}
      <div className="flex-1 min-h-0 overflow-y-auto px-3 py-2" style={{ scrollBehavior: 'smooth' }}>
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full gap-3 opacity-40">
            <span className="text-2xl">⬡</span>
            <span className="text-xs uppercase tracking-widest" style={{ color: 'hsl(var(--muted-foreground))' }}>
              {connected ? 'ready' : 'connecting…'}
            </span>
          </div>
        )}
        {messages.map((msg, i) => (
          <MessageCard key={msg.uuid || i} msg={msg} />
        ))}
        <div ref={bottomRef} />
      </div>

      {/* Disconnected overlay */}
      {!connected && (
        <div
          className="absolute inset-0 z-20 flex items-center justify-center pointer-events-none"
          style={{ background: 'hsl(var(--background) / 0.7)', backdropFilter: 'blur(2px)' }}
        >
          <div className="flex flex-col items-center gap-3">
            <div
              className="w-5 h-5 rounded-full animate-spin"
              style={{ border: '2px solid hsl(var(--accent) / 0.2)', borderTopColor: 'hsl(var(--accent))' }}
            />
            <span className="text-xs" style={{ color: 'hsl(var(--muted-foreground))' }}>
              connecting to agent server…
            </span>
          </div>
        </div>
      )}

      {/* Chat input */}
      <ChatInput
        onSend={handleSend}
        disabled={isWorking || !connected}
        placeholder={isWorking ? 'Working…' : 'Message Claude…'}
      />
    </div>
  );
}
