import React, { useMemo, useContext } from 'react';
import { cn } from '@/lib/utils.js';
import { TYPE_COLORS, STATUS_COLORS } from './constants.js';
import ConfidenceDots from './ConfidenceDots.jsx';
import { VisionChangesContext } from './VisionTracker.jsx';

const TWENTY_FOUR_HOURS = 24 * 60 * 60 * 1000;

function relativeTime(isoString) {
  if (!isoString) return '';
  const diffMs = Date.now() - new Date(isoString).getTime();
  const mins = Math.floor(diffMs / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  return `${days}d ago`;
}

function AttentionRow({ item, reason, onSelect, selectedItemId }) {
  const { newIds, changedIds } = useContext(VisionChangesContext);
  const animClass = newIds.has(item.id) ? 'vision-entering' : changedIds.has(item.id) ? 'vision-updated' : '';
  const typeColor = TYPE_COLORS[item.type] || TYPE_COLORS.task;
  const isSelected = selectedItemId === item.id;

  return (
    <button
      onClick={() => onSelect(item.id)}
      className={cn(
        'flex w-full items-center gap-2 px-3 py-2 text-left transition-colors',
        isSelected
          ? 'bg-accent/10 border-l-2 border-l-accent'
          : 'hover:bg-muted/50 border-l-2 border-l-transparent',
        animClass,
      )}
    >
      {/* Type dot */}
      <div
        className="w-2 h-2 rounded-full shrink-0"
        style={{ background: typeColor }}
      />

      {/* Title */}
      <span className="flex-1 text-sm truncate text-foreground">
        {item.title}
      </span>

      {/* Reason badge */}
      <span className="text-[9px] px-1.5 py-0.5 rounded-full shrink-0" style={{
        background: reason.bg,
        color: reason.color,
      }}>
        {reason.label}
      </span>

      {/* Time */}
      <span className="text-[10px] text-muted-foreground tabular-nums shrink-0">
        {relativeTime(item.updatedAt || item.createdAt)}
      </span>
    </button>
  );
}

const REASONS = {
  decision: { label: 'needs review', bg: 'rgba(251,191,36,0.15)', color: '#fbbf24' },
  blocked: { label: 'blocked', bg: 'rgba(239,68,68,0.12)', color: '#ef4444' },
  lowConfidence: { label: 'low confidence', bg: 'rgba(239,68,68,0.10)', color: '#f87171' },
  newItem: { label: 'new', bg: 'rgba(129,140,248,0.15)', color: '#818cf8' },
  recentChange: { label: 'updated', bg: 'rgba(34,197,94,0.12)', color: '#22c55e' },
};

export default function AttentionView({ items, selectedItemId, onSelect }) {
  const now = Date.now();

  const { pendingDecisions, blockedItems, lowConfidence, recentlyCreated, recentlyChanged } = useMemo(() => {
    const pending = [];
    const blocked = [];
    const lowConf = [];
    const created = [];
    const changed = [];

    for (const item of items) {
      const isTerminal = item.status === 'complete' || item.status === 'killed' || item.status === 'parked';

      // Pending decisions
      if (item.type === 'decision' && !isTerminal) {
        pending.push(item);
      }

      // Blocked items
      if (item.status === 'blocked') {
        blocked.push(item);
      }

      // Low confidence active items (not terminal, confidence 0-1)
      if (!isTerminal && (item.confidence || 0) <= 1 && item.type !== 'thread') {
        lowConf.push(item);
      }

      // Recently created (last 24h)
      if (item.createdAt) {
        const age = now - new Date(item.createdAt).getTime();
        if (age < TWENTY_FOUR_HOURS) {
          created.push(item);
        }
      }

      // Recently changed (last 24h, but not if also recently created)
      if (item.updatedAt && item.createdAt) {
        const updateAge = now - new Date(item.updatedAt).getTime();
        const createAge = now - new Date(item.createdAt).getTime();
        if (updateAge < TWENTY_FOUR_HOURS && createAge > TWENTY_FOUR_HOURS) {
          changed.push(item);
        }
      }
    }

    // Sort all by most recent first
    const byUpdated = (a, b) => {
      const ta = new Date(a.updatedAt || a.createdAt).getTime();
      const tb = new Date(b.updatedAt || b.createdAt).getTime();
      return tb - ta;
    };

    pending.sort(byUpdated);
    blocked.sort(byUpdated);
    lowConf.sort((a, b) => (a.confidence || 0) - (b.confidence || 0));
    created.sort(byUpdated);
    changed.sort(byUpdated);

    return {
      pendingDecisions: pending,
      blockedItems: blocked,
      lowConfidence: lowConf.slice(0, 10), // cap at 10
      recentlyCreated: created,
      recentlyChanged: changed,
    };
  }, [items, now]);

  const totalAttention = pendingDecisions.length + blockedItems.length;

  return (
    <div className="flex-1 overflow-auto flex flex-col">
      {/* Summary bar */}
      <div className="flex items-center gap-3 px-3 py-2 border-b border-border shrink-0">
        <span className="text-xs font-medium text-foreground">Attention</span>
        {totalAttention > 0 ? (
          <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-destructive/15 text-destructive font-medium">
            {totalAttention} need{totalAttention !== 1 ? '' : 's'} action
          </span>
        ) : (
          <span className="text-[10px] text-muted-foreground">All clear</span>
        )}
      </div>

      <div className="flex-1 overflow-auto">
        {/* Pending decisions */}
        {pendingDecisions.length > 0 && (
          <Section title="Pending Decisions" count={pendingDecisions.length} color="#fbbf24">
            {pendingDecisions.map(item => (
              <AttentionRow key={item.id} item={item} reason={REASONS.decision} onSelect={onSelect} selectedItemId={selectedItemId} />
            ))}
          </Section>
        )}

        {/* Blocked items */}
        {blockedItems.length > 0 && (
          <Section title="Blocked" count={blockedItems.length} color="#ef4444">
            {blockedItems.map(item => (
              <AttentionRow key={item.id} item={item} reason={REASONS.blocked} onSelect={onSelect} selectedItemId={selectedItemId} />
            ))}
          </Section>
        )}

        {/* Recently created */}
        {recentlyCreated.length > 0 && (
          <Section title="New (24h)" count={recentlyCreated.length} color="#818cf8">
            {recentlyCreated.map(item => (
              <AttentionRow key={item.id} item={item} reason={REASONS.newItem} onSelect={onSelect} selectedItemId={selectedItemId} />
            ))}
          </Section>
        )}

        {/* Recently changed */}
        {recentlyChanged.length > 0 && (
          <Section title="Updated (24h)" count={recentlyChanged.length} color="#22c55e">
            {recentlyChanged.map(item => (
              <AttentionRow key={item.id} item={item} reason={REASONS.recentChange} onSelect={onSelect} selectedItemId={selectedItemId} />
            ))}
          </Section>
        )}

        {/* Low confidence */}
        {lowConfidence.length > 0 && (
          <Section title="Low Confidence" count={lowConfidence.length} color="#f87171">
            {lowConfidence.map(item => (
              <AttentionRow key={item.id} item={item} reason={REASONS.lowConfidence} onSelect={onSelect} selectedItemId={selectedItemId} />
            ))}
          </Section>
        )}

        {/* Empty state */}
        {pendingDecisions.length === 0 && blockedItems.length === 0 && recentlyCreated.length === 0 && recentlyChanged.length === 0 && lowConfidence.length === 0 && (
          <div className="px-4 py-8 text-center text-sm text-muted-foreground">
            Nothing needs attention right now.
          </div>
        )}
      </div>
    </div>
  );
}

function Section({ title, count, color, children }) {
  return (
    <div>
      <div className="flex items-center gap-2 px-3 py-2">
        <div className="w-2 h-2 rounded-full shrink-0" style={{ background: color }} />
        <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">{title}</span>
        <span className="text-[10px] text-muted-foreground">{count}</span>
      </div>
      {children}
    </div>
  );
}
