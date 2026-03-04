import React from 'react';
import { List, Columns3, GitBranch, Network, Map, FileText, Search, CircleDot, Sun, Moon, Bell } from 'lucide-react';
import { cn } from '@/lib/utils.js';
import { Badge } from '@/components/ui/badge.jsx';
import { Input } from '@/components/ui/input.jsx';
import { ScrollArea } from '@/components/ui/scroll-area.jsx';
import { Separator } from '@/components/ui/separator.jsx';
import { STATUS_COLORS, PHASE_LABELS, PHASES } from './constants.js';
import AgentPanel from './AgentPanel.jsx';

const VIEWS = [
  { key: 'attention', label: 'Attention', icon: Bell },
  { key: 'roadmap', label: 'Roadmap', icon: Map },
  { key: 'list', label: 'All Items', icon: List },
  { key: 'board', label: 'Board', icon: Columns3 },
  { key: 'tree', label: 'Tree', icon: GitBranch },
  { key: 'graph', label: 'Graph', icon: Network },
  { key: 'docs', label: 'Docs', icon: FileText },
];

function phaseStats(items, phaseKey) {
  const phaseItems = items.filter(i => i.phase === phaseKey);
  if (phaseItems.length === 0) return { count: 0, avgConfidence: -1 };
  const sum = phaseItems.reduce((acc, i) => acc + (i.confidence || 0), 0);
  return { count: phaseItems.length, avgConfidence: sum / phaseItems.length };
}

function ConfidenceBar({ avg }) {
  if (avg < 0) return null;
  const pct = (avg / 4) * 100;
  const color = avg >= 3.5 ? 'var(--color-success)' : avg >= 2 ? 'var(--color-primary)' : 'var(--color-error)';
  return (
    <div className="h-1 w-8 rounded-full bg-muted">
      <div className="h-full rounded-full transition-all" style={{ width: `${pct}%`, background: color }} />
    </div>
  );
}

// Explicit status order: complete first (green), then active, then the rest
const STATUS_ORDER = ['complete', 'in_progress', 'review', 'ready', 'planned', 'blocked', 'parked', 'killed'];

function StatsBar({ items }) {
  const total = items.length;
  if (total === 0) return null;

  const counts = {};
  for (const item of items) {
    counts[item.status] = (counts[item.status] || 0) + 1;
  }

  const ordered = STATUS_ORDER.filter(s => counts[s]);

  return (
    <div className="flex h-1.5 w-full rounded-full overflow-hidden bg-muted">
      {ordered.map(status => (
        <div
          key={status}
          style={{
            width: `${(counts[status] / total) * 100}%`,
            background: STATUS_COLORS[status] || STATUS_COLORS.planned,
          }}
        />
      ))}
    </div>
  );
}

function AppSidebar({
  items,
  activeView,
  onViewChange,
  selectedPhase,
  onPhaseSelect,
  searchQuery,
  onSearchChange,
  connected,
  agentActivity,
  agentErrors,
  sessionState,
}) {
  const total = items.length;
  const inProgressCount = items.filter(i => i.status === 'in_progress').length;
  const completeCount = items.filter(i => i.status === 'complete').length;
  const blockedCount = items.filter(i => i.status === 'blocked').length;
  const attentionCount = React.useMemo(() => {
    let count = 0;
    for (const item of items) {
      if (item.type === 'decision' && item.status !== 'complete' && item.status !== 'killed' && item.status !== 'parked') count++;
      if (item.status === 'blocked') count++;
    }
    return count;
  }, [items]);
  const [isDark, setIsDark] = React.useState(() => document.documentElement.classList.contains('dark'));

  const toggleTheme = React.useCallback(() => {
    const next = !isDark;
    document.documentElement.classList.toggle('dark', next);
    localStorage.setItem('forge:theme', next ? 'dark' : 'light');
    setIsDark(next);
  }, [isDark]);

  return (
    <aside className="w-52 shrink-0 flex flex-col bg-sidebar border-r border-sidebar-border">
      {/* Project header */}
      <div className="p-3 pb-2">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-sidebar-foreground">Forge</h2>
          <div className="flex items-center gap-1.5">
            {!connected && (
              <span className="text-[10px] text-destructive">disconnected</span>
            )}
            <button
              onClick={toggleTheme}
              className="p-1 rounded-md text-muted-foreground hover:text-foreground hover:bg-sidebar-accent transition-colors"
              title={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
            >
              {isDark ? <Sun className="h-3.5 w-3.5" /> : <Moon className="h-3.5 w-3.5" />}
            </button>
          </div>
        </div>
        <div className="flex items-center gap-2 mt-1 flex-wrap">
          <span className="text-xs text-muted-foreground">{total} items</span>
          {inProgressCount > 0 && (
            <span className="text-xs text-accent">{inProgressCount} active</span>
          )}
          {completeCount > 0 && (
            <span className="text-xs text-success">{completeCount} done</span>
          )}
          {blockedCount > 0 && (
            <span className="text-xs text-destructive">{blockedCount} blocked</span>
          )}
        </div>
        <StatsBar items={items} />
      </div>

      {/* Agent telemetry — extracted to isolate high-frequency re-renders */}
      <AgentPanel
        agentActivity={agentActivity}
        agentErrors={agentErrors}
        sessionState={sessionState}
      />

      {/* Search */}
      <div className="px-3 pb-2">
        <div className="relative">
          <Search className="absolute left-2 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
          <Input
            placeholder="Search..."
            value={searchQuery}
            onChange={(e) => onSearchChange(e.target.value)}
            className="h-7 pl-7 text-xs bg-sidebar"
          />
        </div>
      </div>

      <Separator className="bg-sidebar-border" />

      {/* Views */}
      <div className="p-2">
        <p className="text-[10px] font-medium uppercase tracking-wider px-2 mb-1" style={{ color: 'var(--color-text-tertiary)' }}>Views</p>
        {VIEWS.map(view => {
          const Icon = view.icon;
          const isActive = activeView === view.key;
          return (
            <button
              key={view.key}
              onClick={() => onViewChange(view.key)}
              className={cn(
                'flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-sm transition-colors',
                isActive
                  ? 'bg-sidebar-accent text-sidebar-accent-foreground font-medium'
                  : 'text-sidebar-foreground hover:bg-sidebar-accent/50'
              )}
            >
              <Icon className="h-4 w-4 shrink-0" />
              <span>{view.label}</span>
              {view.key === 'attention' && attentionCount > 0 ? (
                <Badge variant="outline" className="ml-auto text-[10px] px-1.5 py-0 h-4 text-destructive border-destructive/30">
                  {attentionCount}
                </Badge>
              ) : view.key === 'list' ? (
                <Badge variant="outline" className="ml-auto text-[10px] px-1.5 py-0 h-4">
                  {items.length}
                </Badge>
              ) : (
                <span />
              )}
            </button>
          );
        })}
      </div>

      <Separator className="bg-sidebar-border" />

      {/* Phases */}
      <ScrollArea className="flex-1">
        <div className="p-2">
          <p className="text-[10px] font-medium uppercase tracking-wider px-2 mb-1" style={{ color: 'var(--color-text-tertiary)' }}>Phases</p>
          <button
            onClick={() => onPhaseSelect(null)}
            className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-sm transition-colors"
            style={{
              color: !selectedPhase ? 'var(--color-text-primary)' : 'var(--color-text-secondary)',
              fontWeight: !selectedPhase ? 500 : 400,
              background: !selectedPhase ? 'var(--color-surface-overlay)' : 'transparent',
            }}
          >
            <CircleDot className="h-3.5 w-3.5 shrink-0" />
            <span>All phases</span>
          </button>
          {PHASES.map(phaseKey => {
            const stats = phaseStats(items, phaseKey);
            const isActive = selectedPhase === phaseKey;
            return (
              <button
                key={phaseKey}
                onClick={() => onPhaseSelect(isActive ? null : phaseKey)}
                className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-sm transition-colors"
                style={{
                  color: isActive ? 'var(--color-text-primary)' : 'var(--color-text-secondary)',
                  fontWeight: isActive ? 500 : 400,
                  background: isActive ? 'var(--color-surface-overlay)' : 'transparent',
                }}
              >
                <span className="truncate">{PHASE_LABELS[phaseKey] || phaseKey}</span>
                <div className="ml-auto flex items-center gap-1.5">
                  <ConfidenceBar avg={stats.avgConfidence} />
                  {stats.count > 0 && (
                    <span className="text-[10px] tabular-nums" style={{ color: 'var(--color-text-tertiary)' }}>{stats.count}</span>
                  )}
                </div>
              </button>
            );
          })}
        </div>
      </ScrollArea>
    </aside>
  );
}

export default AppSidebar;
