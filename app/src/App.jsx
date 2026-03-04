import React, { useState, useCallback, useRef, useEffect } from 'react';
import AgentStream from './components/AgentStream';
import Canvas from './components/Canvas';
import PopoutView from './components/PopoutView';

/*
 * Intent: Minimal chrome, maximum workspace.
 * The header is a thin strip — just enough to ground you.
 * Below: terminal (left) + canvas (right), split by a draggable divider.
 * Terminal is the forge floor. Canvas is the viewing surface.
 *
 * Safe mode: If the canvas/vision surface crashes (e.g. bad HMR from agent edits),
 * an error boundary catches it and expands the terminal to full width.
 * A small banner shows what broke + a retry button.
 */

class PanelErrorBoundary extends React.Component {
  state = { error: null };

  static getDerivedStateFromError(error) {
    return { error };
  }

  render() {
    if (this.state.error) {
      return (
        <div className="w-full h-full flex flex-col items-center justify-center gap-3 p-4"
          style={{ background: 'hsl(var(--background))', color: 'hsl(var(--muted-foreground))' }}>
          <div className="text-xs uppercase tracking-wider font-semibold" style={{ color: 'hsl(var(--destructive))' }}>
            panel crashed
          </div>
          <div className="text-[11px] max-w-[300px] text-center opacity-70 font-mono">
            {this.state.error?.message?.substring(0, 120)}
          </div>
          <button
            className="mt-2 px-3 py-1 text-xs rounded border"
            style={{ borderColor: 'hsl(var(--border))', color: 'hsl(var(--foreground))' }}
            onClick={() => this.setState({ error: null })}
          >
            retry
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

// Top-level safe mode: if the entire app crashes, fall back to full-screen terminal
class SafeModeBoundary extends React.Component {
  state = { error: null };

  static getDerivedStateFromError(error) {
    return { error };
  }

  render() {
    if (this.state.error) {
      return (
        <div className="h-screen w-screen flex flex-col bg-background">
          <div className="h-8 flex items-center justify-between px-3 shrink-0"
            style={{ borderBottom: '1px solid hsl(var(--border))', background: 'hsl(var(--destructive) / 0.1)' }}>
            <span className="text-[10px] uppercase tracking-wider font-semibold"
              style={{ color: 'hsl(var(--destructive))' }}>
              safe mode — UI crashed: {this.state.error?.message?.substring(0, 80)}
            </span>
            <button
              className="px-2 py-0.5 text-[10px] rounded border"
              style={{ borderColor: 'hsl(var(--border))', color: 'hsl(var(--foreground))' }}
              onClick={() => this.setState({ error: null })}
            >
              retry
            </button>
          </div>
          <div className="flex-1 min-h-0">
            <AgentStream />
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

const FONT_SIZE_KEY = 'forge:fontSize';
const THEME_KEY = 'forge:theme';
const SPLIT_KEY = 'forge:splitPercent';
const DEFAULT_FONT_SIZE = 13;
const MIN_FONT_SIZE = 10;
const MAX_FONT_SIZE = 20;

function loadFontSize() {
  try {
    const v = parseInt(localStorage.getItem(FONT_SIZE_KEY), 10);
    return v >= MIN_FONT_SIZE && v <= MAX_FONT_SIZE ? v : DEFAULT_FONT_SIZE;
  } catch { return DEFAULT_FONT_SIZE; }
}

function loadTheme() {
  return document.documentElement.classList.contains('dark') ? 'dark' : 'light';
}

export default function App() {
  return (
    <SafeModeBoundary>
      <AppInner />
    </SafeModeBoundary>
  );
}

function AppInner() {
  // Popout mode: render only the tab content, no chrome
  const popoutPath = new URLSearchParams(window.location.search).get('popout');
  if (popoutPath) {
    return <PopoutView path={popoutPath} />;
  }

  const [splitPercent, setSplitPercent] = useState(() => {
    try {
      const v = parseFloat(localStorage.getItem(SPLIT_KEY));
      return v >= 20 && v <= 80 ? v : 50;
    } catch { return 50; }
  });
  const [isDragging, setIsDragging] = useState(false);
  const [fontSize, setFontSize] = useState(loadFontSize);
  const [theme, setTheme] = useState(loadTheme);
  const containerRef = useRef(null);

  const toggleTheme = useCallback(() => {
    const next = theme === 'dark' ? 'light' : 'dark';
    document.documentElement.classList.toggle('dark', next === 'dark');
    localStorage.setItem(THEME_KEY, next);
    setTheme(next);
  }, [theme]);

  const changeFontSize = useCallback((delta) => {
    setFontSize(prev => {
      const next = Math.min(Math.max(prev + delta, MIN_FONT_SIZE), MAX_FONT_SIZE);
      localStorage.setItem(FONT_SIZE_KEY, next);
      return next;
    });
  }, []);

  const handleMouseDown = useCallback((e) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  useEffect(() => {
    if (!isDragging) return;

    const handleMouseMove = (e) => {
      if (!containerRef.current) return;
      const rect = containerRef.current.getBoundingClientRect();
      const percent = ((e.clientX - rect.left) / rect.width) * 100;
      setSplitPercent(Math.min(Math.max(percent, 20), 80));
    };

    const handleMouseUp = () => {
      setIsDragging(false);
      setSplitPercent(current => {
        localStorage.setItem(SPLIT_KEY, current);
        return current;
      });
    };

    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isDragging]);

  return (
    <div className="h-screen w-screen flex flex-col bg-background">
      {/* Header — thin, grounding, not demanding */}
      <header
        className="h-9 flex items-center px-3 shrink-0 justify-between"
        style={{ borderBottom: '1px solid hsl(var(--border))' }}
      >
        <div className="flex items-center">
          <span className="text-xs font-semibold tracking-widest uppercase text-accent">
            Forge
          </span>
          <span className="text-[10px] ml-3 uppercase tracking-wider text-muted-foreground">
            bootstrap
          </span>
        </div>

        {/* Controls */}
        <div className="flex items-center gap-2">
          <button
            className="forge-btn-icon"
            onClick={toggleTheme}
            title={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
          >
            {theme === 'dark' ? '\u2600' : '\u263E'}
          </button>
          <div className="flex items-center gap-1">
            <button
              className="forge-btn-icon"
              onClick={() => changeFontSize(-1)}
              disabled={fontSize <= MIN_FONT_SIZE}
              title="Decrease font size"
            >
              A&#x2212;
            </button>
            <span className="text-[10px] tabular-nums min-w-[20px] text-center text-muted-foreground">
              {fontSize}
            </span>
            <button
              className="forge-btn-icon"
              onClick={() => changeFontSize(1)}
              disabled={fontSize >= MAX_FONT_SIZE}
              title="Increase font size"
            >
              A+
            </button>
          </div>
          <button
            className="forge-btn-icon"
            onClick={() => {
              setFontSize(DEFAULT_FONT_SIZE);
              localStorage.setItem(FONT_SIZE_KEY, DEFAULT_FONT_SIZE);
            }}
            disabled={fontSize === DEFAULT_FONT_SIZE}
            title="Reset font size"
          >
            1:1
          </button>
        </div>
      </header>

      {/* Main workspace: terminal + canvas, side by side */}
      <main
        ref={containerRef}
        className="flex-1 min-h-0 flex"
        style={{ cursor: isDragging ? 'col-resize' : undefined }}
      >
        {/* Agent stream — left panel */}
        <div className="min-w-0 min-h-0" style={{ width: `${splitPercent}%` }}>
          <AgentStream />
        </div>

        {/* Divider — draggable */}
        <div
          className="shrink-0 flex items-center justify-center"
          style={{
            width: '5px',
            cursor: 'col-resize',
            background: isDragging ? 'hsl(var(--border))' : 'hsl(var(--border) / 0.5)',
            transition: isDragging ? 'none' : 'background 0.15s',
          }}
          onMouseDown={handleMouseDown}
        >
          <div
            className="w-0.5 h-8 rounded-full"
            style={{ background: 'hsl(var(--border))' }}
          />
        </div>

        {/* Canvas — right panel (error boundary = safe mode) */}
        <div className="min-w-0 min-h-0 flex-1">
          <PanelErrorBoundary>
            <Canvas fontSize={fontSize} />
          </PanelErrorBoundary>
        </div>
      </main>
    </div>
  );
}
