import { useState, useEffect, useRef, useCallback } from 'react';

/**
 * Walk the DOM and produce a compact accessibility-style snapshot.
 * Returns a tree of { tag, role, text, children } nodes.
 * Skips invisible elements and script/style tags.
 */
function collectDOMSnapshot() {
  const SKIP_TAGS = new Set(['SCRIPT', 'STYLE', 'LINK', 'META', 'NOSCRIPT']);
  const MAX_DEPTH = 12;
  const MAX_TEXT = 120;

  function walk(el, depth) {
    if (!el || depth > MAX_DEPTH) return null;
    if (el.nodeType === Node.TEXT_NODE) {
      const text = el.textContent.trim();
      return text ? text.slice(0, MAX_TEXT) : null;
    }
    if (el.nodeType !== Node.ELEMENT_NODE) return null;
    if (SKIP_TAGS.has(el.tagName)) return null;

    // Skip hidden elements
    const style = window.getComputedStyle(el);
    if (style.display === 'none' || style.visibility === 'hidden') return null;

    const node = {};
    const role = el.getAttribute('role') || el.getAttribute('aria-label');
    const tag = el.tagName.toLowerCase();

    // Compact representation
    if (role) node.role = role;
    else node.tag = tag;

    // Capture key attributes
    if (el.className && typeof el.className === 'string') {
      const cls = el.className.trim();
      if (cls.length < 80) node.class = cls;
    }

    // Collect children
    const children = [];
    for (const child of el.childNodes) {
      const c = walk(child, depth + 1);
      if (c) children.push(c);
    }

    // Flatten: if a node has exactly one text child, inline it
    if (children.length === 1 && typeof children[0] === 'string') {
      node.text = children[0];
    } else if (children.length > 0) {
      node.children = children;
    }

    // Skip wrapper divs with no semantic value
    if (!role && (tag === 'div' || tag === 'span') && !node.text && children.length === 1 && typeof children[0] === 'object') {
      return children[0];
    }

    return node;
  }

  // Start from the Vision Tracker root if present, otherwise body
  const root = document.querySelector('[data-snapshot-root]') || document.body;
  return walk(root, 0);
}

/**
 * useVisionStore — WebSocket connection to /ws/vision + REST mutations.
 * Full state replacement on every visionState message (no deltas).
 */
const EMPTY_CHANGES = { newIds: new Set(), changedIds: new Set() };

export function useVisionStore() {
  const [items, setItems] = useState([]);
  const [connections, setConnections] = useState([]);
  const [connected, setConnected] = useState(false);
  const [uiCommand, setUICommand] = useState(null);
  const [recentChanges, setRecentChanges] = useState(EMPTY_CHANGES);
  const [agentActivity, setAgentActivity] = useState([]);
  const [agentErrors, setAgentErrors] = useState([]);
  const [sessionState, setSessionState] = useState(null);
  const wsRef = useRef(null);
  const reconnectTimerRef = useRef(null);
  const snapshotProviderRef = useRef(null);
  const prevItemMapRef = useRef(null);
  const changeTimerRef = useRef(null);
  const sessionEndTimerRef = useRef(null);

  useEffect(() => {
    function connect() {
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const ws = new WebSocket(`${protocol}//${window.location.host}/ws/vision`);
      wsRef.current = ws;

      ws.onopen = () => setConnected(true);

      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          if (msg.type === 'visionState') {
            const incoming = msg.items || [];

            // Diff for animations (skip initial load)
            if (prevItemMapRef.current) {
              const prev = prevItemMapRef.current;
              const added = new Set();
              const changed = new Set();
              for (const item of incoming) {
                const old = prev.get(item.id);
                if (!old) {
                  added.add(item.id);
                } else if (old.status !== item.status || old.confidence !== item.confidence || old.title !== item.title) {
                  changed.add(item.id);
                }
              }
              if (added.size > 0 || changed.size > 0) {
                setRecentChanges({ newIds: added, changedIds: changed });
                if (changeTimerRef.current) clearTimeout(changeTimerRef.current);
                changeTimerRef.current = setTimeout(() => setRecentChanges(EMPTY_CHANGES), 800);
              }
            }
            prevItemMapRef.current = new Map(incoming.map(i => [i.id, i]));

            setItems(incoming);
            setConnections(msg.connections || []);
          } else if (msg.type === 'visionUI') {
            setUICommand(msg);
          } else if (msg.type === 'agentActivity') {
            setAgentActivity(prev => {
              const next = [...prev, {
                tool: msg.tool, category: msg.category || null, detail: msg.detail,
                items: msg.items || [], error: msg.error || null, timestamp: msg.timestamp,
              }];
              return next.length > 20 ? next.slice(-20) : next;
            });
            // Optimistic session tool count increment
            setSessionState(prev => prev?.active ? { ...prev, toolCount: (prev.toolCount || 0) + 1 } : prev);
          } else if (msg.type === 'sessionStart') {
            if (sessionEndTimerRef.current) clearTimeout(sessionEndTimerRef.current);
            setSessionState(prev => {
              // If hydration already set this session, preserve accumulated counts
              if (prev && prev.id === msg.sessionId) return { ...prev, active: true };
              return {
                id: msg.sessionId, active: true, startedAt: msg.timestamp,
                source: msg.source, toolCount: 0, errorCount: 0, summaries: [],
              };
            });
          } else if (msg.type === 'sessionEnd') {
            if (sessionEndTimerRef.current) clearTimeout(sessionEndTimerRef.current);
            setSessionState(prev => prev ? {
              ...prev, active: false, endedAt: msg.timestamp,
              toolCount: msg.toolCount, duration: msg.duration,
              journalSpawned: msg.journalSpawned,
            } : null);
            // Clear ended session display after 15s
            sessionEndTimerRef.current = setTimeout(() => setSessionState(null), 15000);
          } else if (msg.type === 'sessionSummary') {
            setSessionState(prev => prev ? {
              ...prev, summaries: [...(prev.summaries || []), {
                summary: msg.summary, intent: msg.intent, component: msg.component,
                timestamp: msg.timestamp,
              }].slice(-5),
            } : prev);
          } else if (msg.type === 'agentError') {
            setAgentErrors(prev => {
              const next = [...prev, {
                errorType: msg.errorType, severity: msg.severity, message: msg.message,
                tool: msg.tool, detail: msg.detail, items: msg.items || [],
                timestamp: msg.timestamp || new Date().toISOString(),
              }];
              return next.length > 10 ? next.slice(-10) : next;
            });
            // Increment session error count
            setSessionState(prev => prev?.active ? { ...prev, errorCount: (prev.errorCount || 0) + 1 } : prev);
          } else if (msg.type === 'snapshotRequest' && msg.requestId) {
            // Collect UI state from provider and DOM, send back
            const uiState = snapshotProviderRef.current ? snapshotProviderRef.current() : {};
            const domSnapshot = collectDOMSnapshot();
            ws.send(JSON.stringify({
              type: 'snapshotResponse',
              requestId: msg.requestId,
              snapshot: { ...uiState, dom: domSnapshot, timestamp: new Date().toISOString() },
            }));
          }
        } catch {
          // ignore
        }
      };

      ws.onclose = () => {
        setConnected(false);
        reconnectTimerRef.current = setTimeout(connect, 2000);
      };

      ws.onerror = () => {};
    }

    connect();

    return () => {
      if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
      if (changeTimerRef.current) clearTimeout(changeTimerRef.current);
      if (sessionEndTimerRef.current) clearTimeout(sessionEndTimerRef.current);
      if (wsRef.current) wsRef.current.close();
    };
  }, []);

  // Hydrate session state on mount (server may already have an active session)
  useEffect(() => {
    fetch('/api/session/current')
      .then(r => r.json())
      .then(data => {
        if (data.session) {
          // Only hydrate if no WebSocket sessionStart has arrived first
          setSessionState(prev => prev ? prev : {
            id: data.session.id, active: true, startedAt: data.session.startedAt,
            source: data.session.source || 'hydrated', toolCount: data.session.toolCount || 0,
            errorCount: data.session.errorCount || 0, summaries: data.session.summaries || [],
          });
        }
      })
      .catch(() => { console.warn('[vision] Failed to hydrate session state'); });
  }, []);

  const handleResponse = useCallback(async (res) => {
    const data = await res.json();
    if (!res.ok) {
      console.error(`[vision] API error ${res.status}:`, data.error || data);
      return { error: data.error || `HTTP ${res.status}` };
    }
    return data;
  }, []);

  const createItem = useCallback(async (data) => {
    const res = await fetch('/api/vision/items', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    return handleResponse(res);
  }, [handleResponse]);

  const updateItem = useCallback(async (id, data) => {
    const res = await fetch(`/api/vision/items/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    return handleResponse(res);
  }, [handleResponse]);

  const deleteItem = useCallback(async (id) => {
    const res = await fetch(`/api/vision/items/${id}`, { method: 'DELETE' });
    return handleResponse(res);
  }, [handleResponse]);

  const createConnection = useCallback(async (data) => {
    const res = await fetch('/api/vision/connections', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    return handleResponse(res);
  }, [handleResponse]);

  const deleteConnection = useCallback(async (id) => {
    const res = await fetch(`/api/vision/connections/${id}`, { method: 'DELETE' });
    return handleResponse(res);
  }, [handleResponse]);

  // Optimistic position update for drag (local state + debounced REST)
  const updateItemPosition = useCallback((id, position) => {
    setItems(prev => prev.map(item =>
      item.id === id ? { ...item, position } : item
    ));
  }, []);

  const clearUICommand = useCallback(() => setUICommand(null), []);

  const registerSnapshotProvider = useCallback((provider) => {
    snapshotProviderRef.current = provider;
  }, []);

  return {
    items,
    connections,
    connected,
    uiCommand,
    clearUICommand,
    recentChanges,
    createItem,
    updateItem,
    deleteItem,
    createConnection,
    deleteConnection,
    updateItemPosition,
    agentActivity,
    agentErrors,
    sessionState,
    registerSnapshotProvider,
  };
}
