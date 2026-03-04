import React, { useEffect, useRef, useState, useCallback } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { ExternalLink, FolderOpen } from 'lucide-react';
import VisionTracker from './vision/VisionTracker.jsx';
import ProductGraph from './ProductGraph.jsx';

const POPOUT_CHANNEL = 'compose-popout';

/*
 * Canvas — the right panel. Multi-renderer shell.
 *
 * Tabs: each open file/surface gets a tab. Tabs persist until closed.
 * rendererType per tab: 'markdown' (default) or 'vision'.
 * Agent can open files via POST /api/canvas/open → openFile WS message.
 * Agent can open vision surface via POST /api/canvas/open with path=vision://surface.
 * Agent can scroll to headings via POST /api/canvas/scroll → scrollTo WS message.
 * File watcher pushes fileChanged → updates content of any matching open tab.
 */

// Generate a GitHub-style slug from heading text
function slugify(text) {
  return text
    .toLowerCase()
    .replace(/[^\w\s-]/g, '')
    .replace(/\s+/g, '-')
    .replace(/-+/g, '-')
    .replace(/^-|-$/g, '');
}

// Extract plain text from React children (handles nested elements)
function extractText(children) {
  return React.Children.toArray(children)
    .map(child => {
      if (typeof child === 'string') return child;
      if (child?.props?.children) return extractText(child.props.children);
      return '';
    })
    .join('');
}

// Custom heading components that generate anchor IDs
function makeHeading(Tag) {
  return function Heading({ children, ...props }) {
    const text = extractText(children);
    const id = slugify(text);
    return <Tag id={id} {...props}>{children}</Tag>;
  };
}

const headingComponents = {
  h1: makeHeading('h1'),
  h2: makeHeading('h2'),
  h3: makeHeading('h3'),
  h4: makeHeading('h4'),
  h5: makeHeading('h5'),
  h6: makeHeading('h6'),
};

// Persist open tab paths, active index, and pinned state to localStorage
const STORAGE_KEY = 'compose:canvasState';

function saveCanvasState(tabs, activeIndex, pinned) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({
      paths: tabs.map(t => t.path),
      activeIndex,
      pinned,
    }));
  } catch { /* quota exceeded or private browsing */ }
}

function loadCanvasState() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const state = JSON.parse(raw);
    if (Array.isArray(state.paths)) return state;
  } catch { /* corrupt data */ }
  return null;
}

export default function Canvas({ fontSize = 14 }) {
  const [tabs, setTabs] = useState([]);
  const [activeIndex, setActiveIndex] = useState(-1);
  const [pinned, setPinned] = useState(false);
  const [connected, setConnected] = useState(false);
  const [fileList, setFileList] = useState([]);
  const [showFilePicker, setShowFilePicker] = useState(false);
  const [highlightId, setHighlightId] = useState(null);
  const [restoring, setRestoring] = useState(true);
  const [undocked, setUndocked] = useState(new Set());
  const wsRef = useRef(null);
  const reconnectTimerRef = useRef(null);
  const contentRef = useRef(null);
  const popoutWindowsRef = useRef(new Map());

  const tabsRef = useRef(tabs);
  const activeIndexRef = useRef(activeIndex);
  const pinnedRef = useRef(pinned);
  tabsRef.current = tabs;
  activeIndexRef.current = activeIndex;
  pinnedRef.current = pinned;

  // BroadcastChannel: listen for popout mount/close
  useEffect(() => {
    const channel = new BroadcastChannel(POPOUT_CHANNEL);
    channel.onmessage = (event) => {
      const { type, path } = event.data || {};
      if (type === 'popout-mounted') {
        setUndocked(prev => new Set(prev).add(path));
      } else if (type === 'popout-closed' || type === 'popout-dock') {
        setUndocked(prev => {
          const next = new Set(prev);
          next.delete(path);
          return next;
        });
        popoutWindowsRef.current.delete(path);
        // On dock, switch to that tab
        if (type === 'popout-dock') {
          const idx = tabsRef.current.findIndex(t => t.path === path);
          if (idx !== -1) setActiveIndex(idx);
        }
      }
    };
    return () => channel.close();
  }, []);

  // Undock a tab into its own window
  const undockTab = useCallback((path) => {
    // If already undocked, focus the existing window
    const existing = popoutWindowsRef.current.get(path);
    if (existing && !existing.closed) {
      existing.focus();
      return;
    }

    const url = `/?popout=${encodeURIComponent(path)}`;
    const win = window.open(url, `compose-popout-${path}`, 'popup,width=900,height=700');
    if (win) {
      popoutWindowsRef.current.set(path, win);
      setUndocked(prev => new Set(prev).add(path));
    }
  }, []);

  // Dock a tab back — close popout window, remove from undocked set
  const dockTab = useCallback((path) => {
    const win = popoutWindowsRef.current.get(path);
    if (win && !win.closed) win.close();
    popoutWindowsRef.current.delete(path);
    setUndocked(prev => {
      const next = new Set(prev);
      next.delete(path);
      return next;
    });
  }, []);

  // Persist canvas state to localStorage whenever it changes
  useEffect(() => {
    if (restoring) return; // don't overwrite saved state during restore
    saveCanvasState(tabs, activeIndex, pinned);
  }, [tabs, activeIndex, pinned, restoring]);

  // Restore previously open tabs on mount
  useEffect(() => {
    const saved = loadCanvasState();
    if (!saved || saved.paths.length === 0) {
      setRestoring(false);
      return;
    }
    setPinned(!!saved.pinned);
    Promise.all(
      saved.paths.map(path => {
        // Special scheme tabs don't need file fetch
        if (path.startsWith('vision://')) {
          return Promise.resolve({ path, content: null, rendererType: 'vision' });
        }
        if (path.startsWith('graph://')) {
          return Promise.resolve({ path, content: null, rendererType: 'graph' });
        }
        return fetch(`/api/file?path=${encodeURIComponent(path)}`)
          .then(r => r.json())
          .then(data => data.content !== undefined ? { path, content: data.content } : null)
          .catch(() => null);
      })
    ).then(results => {
      const restored = results.filter(Boolean);
      if (restored.length > 0) {
        setTabs(restored);
        const idx = saved.activeIndex ?? 0;
        setActiveIndex(Math.min(idx, restored.length - 1));
      }
      setRestoring(false);
    });
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Scroll to an element by ID and flash-highlight it
  const scrollToAnchor = useCallback((anchor) => {
    // Small delay to let React render if content just changed
    setTimeout(() => {
      const el = document.getElementById(anchor);
      if (!el) return;
      el.scrollIntoView({ behavior: 'smooth', block: 'start' });
      setHighlightId(anchor);
      setTimeout(() => setHighlightId(null), 2000);
    }, 100);
  }, []);

  const openTab = useCallback((path, content, anchor, rendererType) => {
    // Auto-detect renderer from file extension if not specified
    if (!rendererType) {
      rendererType = path.endsWith('.html') || path.endsWith('.htm') ? 'html' : 'markdown';
    }
    setTabs(prev => {
      const existing = prev.findIndex(t => t.path === path);
      if (existing !== -1) {
        const updated = [...prev];
        updated[existing] = { ...updated[existing], content, rendererType };
        setActiveIndex(existing);
        return updated;
      }
      const next = [...prev, { path, content, rendererType }];
      setActiveIndex(next.length - 1);
      return next;
    });
    if (anchor) {
      // Scroll after tab switch + render
      setTimeout(() => scrollToAnchor(anchor), 150);
    }
  }, [scrollToAnchor]);

  const closeTab = useCallback((index, e) => {
    if (e) e.stopPropagation();
    setTabs(prev => {
      const next = prev.filter((_, i) => i !== index);
      setActiveIndex(current => {
        if (next.length === 0) return -1;
        if (current === index) return Math.min(index, next.length - 1);
        if (current > index) return current - 1;
        return current;
      });
      return next;
    });
  }, []);

  const loadFileList = useCallback(() => {
    fetch('/api/files')
      .then(r => r.json())
      .then(data => setFileList(data.files || []))
      .catch(() => {});
  }, []);

  const loadFile = useCallback((path) => {
    fetch(`/api/file?path=${encodeURIComponent(path)}`)
      .then(r => r.json())
      .then(data => {
        if (data.content !== undefined) {
          openTab(data.path || path, data.content);
        }
      })
      .catch(() => {});
  }, [openTab]);

  // WebSocket connection
  useEffect(() => {
    function connect() {
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const ws = new WebSocket(`${protocol}//${window.location.host}/ws/files`);
      wsRef.current = ws;

      ws.onopen = () => setConnected(true);

      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);

          if (msg.type === 'openFile') {
            openTab(msg.path, msg.content, msg.anchor, msg.rendererType);
          } else if (msg.type === 'closeFile') {
            if (msg.path) {
              // Close specific tab
              const currentTabs = tabsRef.current;
              const idx = currentTabs.findIndex(t => t.path === msg.path);
              if (idx !== -1) closeTab(idx);
            } else {
              // Close all tabs
              setTabs([]);
              setActiveIndex(-1);
            }
          } else if (msg.type === 'scrollTo') {
            // Scroll within current tab, or switch tab first if path specified
            if (msg.path) {
              const currentTabs = tabsRef.current;
              const idx = currentTabs.findIndex(t => t.path === msg.path);
              if (idx !== -1) {
                setActiveIndex(idx);
                setTimeout(() => scrollToAnchor(msg.anchor), 150);
              }
              // If file not open, ignore — agent should open it first
            } else {
              scrollToAnchor(msg.anchor);
            }
          } else if (msg.type === 'fileChanged') {
            const currentTabs = tabsRef.current;
            const existingIdx = currentTabs.findIndex(t => t.path === msg.path);

            if (existingIdx !== -1) {
              setTabs(prev => {
                const updated = [...prev];
                updated[existingIdx] = { ...updated[existingIdx], content: msg.content };
                return updated;
              });
            } else if (!pinnedRef.current) {
              openTab(msg.path, msg.content);
            }
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
      if (wsRef.current) wsRef.current.close();
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const handleFilePick = (path) => {
    loadFile(path);
    setPinned(true);
    setShowFilePicker(false);
  };

  // If active tab is undocked, fall back to the nearest docked tab
  const activeTab = (() => {
    const raw = activeIndex >= 0 && activeIndex < tabs.length ? tabs[activeIndex] : null;
    if (raw && !undocked.has(raw.path)) return raw;
    // Search forward then backward for a docked tab
    for (let i = activeIndex + 1; i < tabs.length; i++) {
      if (!undocked.has(tabs[i].path)) return tabs[i];
    }
    for (let i = activeIndex - 1; i >= 0; i--) {
      if (!undocked.has(tabs[i].path)) return tabs[i];
    }
    return null;
  })();
  // Resolve renderer: special schemes use explicit rendererType, file paths derive from extension
  const activeRenderer = activeTab?.path?.startsWith('vision://') ? 'vision'
    : activeTab?.path?.startsWith('graph://') ? 'graph'
    : activeTab?.path?.endsWith('.html') || activeTab?.path?.endsWith('.htm') ? 'html'
    : 'markdown';

  const displayName = (path) => {
    if (path === 'vision://surface') return 'Vision Tracker';
    if (path.startsWith('graph://')) {
      const name = path.replace('graph://', '');
      return name.charAt(0).toUpperCase() + name.slice(1) + ' Graph';
    }
    const parts = path.split('/');
    return parts.length > 1 ? parts.slice(-2).join('/') : parts[parts.length - 1];
  };

  return (
    <div className="h-full flex flex-col" style={{ background: 'var(--compose-raised)' }}>
      {/* Header bar */}
      <div
        className="flex items-center px-2 shrink-0 gap-1"
        style={{ borderBottom: '1px solid var(--border-standard)', minHeight: '32px' }}
      >
        <div
          className="w-1.5 h-1.5 rounded-full shrink-0"
          style={{ background: connected ? 'var(--success)' : 'var(--error)' }}
        />

        <div className="flex-1 flex items-center gap-0 overflow-x-auto min-w-0" style={{ scrollbarWidth: 'none' }}>
          {tabs.map((tab, i) => {
            if (undocked.has(tab.path)) return null;
            return (
              <button
                key={tab.path}
                className="flex items-center gap-1.5 px-2.5 py-1 text-[13px] shrink-0 border-none cursor-pointer group"
                style={{
                  color: i === activeIndex ? 'var(--ink-primary)' : 'var(--ink-tertiary)',
                  background: i === activeIndex ? 'var(--compose-overlay)' : 'transparent',
                  borderBottom: i === activeIndex ? '2px solid var(--ember)' : '2px solid transparent',
                }}
                onClick={() => setActiveIndex(i)}
                title={tab.path}
              >
                <span className="truncate max-w-[140px]">{displayName(tab.path)}</span>
                <span
                  className="text-[11px] opacity-0 group-hover:opacity-80 hover:text-[var(--ember)]"
                  style={{ color: 'var(--ink-secondary)', transition: 'opacity 0.15s', cursor: 'pointer', padding: '0 2px' }}
                  onClick={(e) => { e.stopPropagation(); undockTab(tab.path); }}
                  title="Pop out to window"
                >
                  <ExternalLink style={{ width: 11, height: 11, display: 'inline' }} />
                </span>
                <span
                  className="text-[11px] opacity-40 group-hover:opacity-100 hover:text-[var(--error)]"
                  style={{ color: 'var(--ink-secondary)', transition: 'opacity 0.15s', cursor: 'pointer', padding: '0 2px' }}
                  onClick={(e) => closeTab(i, e)}
                >
                  ✕
                </span>
              </button>
            );
          })}
        </div>

        <button
          className="flex items-center gap-1 px-1.5 py-0.5 shrink-0 rounded"
          style={{
            color: showFilePicker ? 'var(--ember)' : 'var(--ink-tertiary)',
            background: showFilePicker ? 'var(--compose-overlay)' : 'none',
            border: 'none',
            cursor: 'pointer',
          }}
          onClick={() => { loadFileList(); setShowFilePicker(!showFilePicker); }}
          title="Browse files"
        >
          <FolderOpen style={{ width: 13, height: 13 }} />
        </button>

        <button
          className="text-[10px] uppercase tracking-wider px-1.5 py-0.5 rounded shrink-0"
          style={{
            color: pinned ? 'var(--ember)' : 'var(--ink-tertiary)',
            background: pinned ? 'var(--ember-glow)' : 'transparent',
            border: 'none',
            cursor: 'pointer',
          }}
          onClick={() => setPinned(!pinned)}
          title={pinned ? 'Pinned — file changes won\'t auto-open new tabs' : 'Auto — file changes open new tabs'}
        >
          {pinned ? 'pinned' : 'auto'}
        </button>
      </div>

      {/* File picker dropdown */}
      {showFilePicker && (
        <div
          className="overflow-y-auto"
          style={{
            background: 'var(--compose-overlay)',
            borderBottom: '1px solid var(--border-standard)',
            maxHeight: '240px',
          }}
        >
          {fileList.length === 0 ? (
            <div className="px-3 py-2 text-xs" style={{ color: 'var(--ink-tertiary)' }}>
              No markdown files found in docs/
            </div>
          ) : (
            fileList.map((f) => {
              const isOpen = tabs.some(t => t.path === f);
              return (
                <button
                  key={f}
                  className="block w-full text-left px-3 py-1.5 text-xs hover:bg-white/5 truncate"
                  style={{
                    color: isOpen ? 'var(--ember)' : 'var(--ink-secondary)',
                    background: 'none',
                    border: 'none',
                    cursor: 'pointer',
                  }}
                  onClick={() => handleFilePick(f)}
                >
                  {f}
                </button>
              );
            })
          )}
        </div>
      )}

      {/* Content area */}
      {activeRenderer === 'vision' ? (
        <div className="flex-1 min-h-0">
          <VisionTracker />
        </div>
      ) : activeRenderer === 'graph' ? (
        <div className="flex-1 min-h-0">
          <ProductGraph />
        </div>
      ) : activeRenderer === 'html' ? (
        <div className="flex-1 min-h-0">
          <iframe
            srcDoc={activeTab.content}
            className="w-full h-full border-0"
            sandbox="allow-scripts allow-same-origin"
            title={displayName(activeTab.path)}
          />
        </div>
      ) : (
        <div ref={contentRef} className="flex-1 overflow-y-auto min-h-0 px-5 py-4">
          {activeTab ? (
            <div className="canvas-markdown max-w-none" style={{ fontSize: `${fontSize}px` }}>
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={headingComponents}
              >
                {activeTab.content}
              </ReactMarkdown>
            </div>
          ) : (
            <div className="h-full flex items-center justify-center">
              <div className="text-center">
                <p className="text-sm mb-1" style={{ color: 'var(--ink-tertiary)' }}>
                  Canvas
                </p>
                <p className="text-xs" style={{ color: 'var(--ink-muted)' }}>
                  Edit a markdown file in docs/ to see it here
                </p>
                <button
                  className="text-xs mt-3 underline"
                  style={{ color: 'var(--ink-tertiary)', background: 'none', border: 'none', cursor: 'pointer' }}
                  onClick={() => { loadFileList(); setShowFilePicker(true); }}
                >
                  or browse files
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Highlight style — injected once */}
      <style>{`
        .canvas-markdown [id="${highlightId}"] {
          background: var(--ember-glow);
          margin-left: -8px;
          padding-left: 8px;
          margin-right: -8px;
          padding-right: 8px;
          border-radius: 4px;
          transition: background 0.3s ease;
        }
      `}</style>
    </div>
  );
}
