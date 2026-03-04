import React, { useEffect, useState, useRef, useCallback } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { ArrowDownToLine } from 'lucide-react';
import VisionTracker from './vision/VisionTracker.jsx';
import ProductGraph from './ProductGraph.jsx';

/*
 * PopoutView — renders a single tab's content in a standalone browser window.
 * Detected via ?popout=<path> query param. No terminal, no tab bar.
 * Thin title bar with pop-in button to dock back into main canvas.
 * Communicates with the main window via BroadcastChannel.
 */

const CHANNEL_NAME = 'forge-popout';

function displayName(path) {
  if (path === 'vision://surface') return 'Vision Tracker';
  if (path.startsWith('graph://')) {
    const name = path.replace('graph://', '');
    return name.charAt(0).toUpperCase() + name.slice(1) + ' Graph';
  }
  const parts = path.split('/');
  return parts.length > 1 ? parts.slice(-2).join('/') : parts[parts.length - 1];
}

function PopoutBar({ path, onDock }) {
  return (
    <div
      className="flex items-center justify-between px-3 shrink-0"
      style={{
        height: '28px',
        borderBottom: '1px solid hsl(var(--border))',
        background: 'hsl(var(--background))',
      }}
    >
      <span className="text-[11px] text-muted-foreground truncate">
        {displayName(path)}
      </span>
      <button
        onClick={onDock}
        className="flex items-center gap-1 px-2 py-0.5 rounded text-[10px] uppercase tracking-wider"
        style={{
          color: 'var(--ember, hsl(var(--primary)))',
          background: 'none',
          border: 'none',
          cursor: 'pointer',
        }}
        title="Pop back into main window"
      >
        <ArrowDownToLine style={{ width: 11, height: 11 }} />
        pop in
      </button>
    </div>
  );
}

export default function PopoutView({ path }) {
  const [content, setContent] = useState(null);
  const [loading, setLoading] = useState(true);
  const channelRef = useRef(null);
  const wsRef = useRef(null);

  // Determine renderer type
  const rendererType = path.startsWith('vision://') ? 'vision'
    : path.startsWith('graph://') ? 'graph'
    : path.endsWith('.html') || path.endsWith('.htm') ? 'html'
    : 'markdown';

  // Set document title
  useEffect(() => {
    document.title = displayName(path) + ' — Forge';
  }, [path]);

  // BroadcastChannel: announce mount/unmount, listen for dock-back
  useEffect(() => {
    const channel = new BroadcastChannel(CHANNEL_NAME);
    channelRef.current = channel;
    channel.postMessage({ type: 'popout-mounted', path });

    const handleBeforeUnload = () => {
      channel.postMessage({ type: 'popout-closed', path });
    };
    window.addEventListener('beforeunload', handleBeforeUnload);

    return () => {
      handleBeforeUnload();
      channel.close();
      window.removeEventListener('beforeunload', handleBeforeUnload);
    };
  }, [path]);

  // Pop-in: tell main window to dock, then close this window
  const handleDock = useCallback(() => {
    channelRef.current?.postMessage({ type: 'popout-dock', path });
    window.close();
  }, [path]);

  // Fetch initial content for file-based tabs
  useEffect(() => {
    if (rendererType === 'vision' || rendererType === 'graph') {
      setLoading(false);
      return;
    }

    fetch(`/api/file?path=${encodeURIComponent(path)}`)
      .then(r => r.json())
      .then(data => {
        if (data.content !== undefined) setContent(data.content);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, [path, rendererType]);

  // WebSocket for live file updates
  useEffect(() => {
    if (rendererType === 'vision' || rendererType === 'graph') return;

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const ws = new WebSocket(`${protocol}//${window.location.host}/ws/files`);
    wsRef.current = ws;

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        if (msg.type === 'fileChanged' && msg.path === path) {
          setContent(msg.content);
        }
      } catch { /* ignore */ }
    };

    return () => ws.close();
  }, [path, rendererType]);

  if (loading) {
    return (
      <div className="h-screen w-screen flex items-center justify-center bg-background">
        <span className="text-sm text-muted-foreground">Loading...</span>
      </div>
    );
  }

  if (rendererType === 'vision') {
    return (
      <div className="h-screen w-screen flex flex-col bg-background">
        <PopoutBar path={path} onDock={handleDock} />
        <div className="flex-1 min-h-0">
          <VisionTracker />
        </div>
      </div>
    );
  }

  if (rendererType === 'graph') {
    return (
      <div className="h-screen w-screen flex flex-col bg-background">
        <PopoutBar path={path} onDock={handleDock} />
        <div className="flex-1 min-h-0">
          <ProductGraph />
        </div>
      </div>
    );
  }

  if (rendererType === 'html') {
    return (
      <div className="h-screen w-screen flex flex-col bg-background">
        <PopoutBar path={path} onDock={handleDock} />
        <div className="flex-1 min-h-0">
          <iframe
            srcDoc={content}
            className="w-full h-full border-0"
            sandbox="allow-scripts allow-same-origin"
            title={path}
          />
        </div>
      </div>
    );
  }

  // Markdown
  return (
    <div className="h-screen w-screen flex flex-col bg-background">
      <PopoutBar path={path} onDock={handleDock} />
      <div className="flex-1 overflow-y-auto px-8 py-6">
        <div className="canvas-markdown max-w-4xl mx-auto">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>
            {content || ''}
          </ReactMarkdown>
        </div>
      </div>
    </div>
  );
}
