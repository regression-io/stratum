import React, { useState, useMemo, useContext } from 'react';
import { ChevronRight, ChevronDown, Plus } from 'lucide-react';
import { cn } from '@/lib/utils.js';
import { Badge } from '@/components/ui/badge.jsx';
import { Button } from '@/components/ui/button.jsx';
import { TYPE_COLORS, STATUS_COLORS, PHASES, PHASE_LABELS, STATUSES } from './constants.js';
import ConfidenceDots from './ConfidenceDots.jsx';
import { VisionChangesContext } from './VisionTracker.jsx';

const STATUS_ORDER = Object.fromEntries(STATUSES.map((s, i) => [s, i]));

function relativeTime(isoString) {
  if (!isoString) return '';
  const diffMs = Date.now() - new Date(isoString).getTime();
  const mins = Math.floor(diffMs / 60000);
  if (mins < 60) return `${mins}m`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h`;
  const days = Math.floor(hrs / 24);
  if (days < 7) return `${days}d`;
  return new Date(isoString).toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

function sortItems(items, sortBy) {
  const sorted = [...items];
  switch (sortBy) {
    case 'confidence':
      sorted.sort((a, b) => (a.confidence || 0) - (b.confidence || 0));
      break;
    case 'updated':
      sorted.sort((a, b) => {
        const ta = a.updatedAt ? new Date(a.updatedAt).getTime() : 0;
        const tb = b.updatedAt ? new Date(b.updatedAt).getTime() : 0;
        return tb - ta;
      });
      break;
    case 'status':
      sorted.sort((a, b) => (STATUS_ORDER[a.status] ?? 99) - (STATUS_ORDER[b.status] ?? 99));
      break;
    case 'alpha':
      sorted.sort((a, b) => (a.title || '').localeCompare(b.title || ''));
      break;
    default:
      sorted.sort((a, b) => (a.confidence || 0) - (b.confidence || 0));
  }
  return sorted;
}

function groupItems(items, groupBy) {
  const map = new Map();
  switch (groupBy) {
    case 'phase':
      for (const phase of PHASES) map.set(phase, []);
      for (const item of items) {
        const key = item.phase || 'vision';
        if (!map.has(key)) map.set(key, []);
        map.get(key).push(item);
      }
      break;
    case 'type':
      for (const item of items) {
        const key = item.type || 'task';
        if (!map.has(key)) map.set(key, []);
        map.get(key).push(item);
      }
      break;
    case 'status':
      for (const s of STATUSES) map.set(s, []);
      for (const item of items) {
        const key = item.status || 'planned';
        if (!map.has(key)) map.set(key, []);
        map.get(key).push(item);
      }
      break;
    case 'none':
      map.set('all', [...items]);
      break;
    default:
      map.set('all', [...items]);
  }
  return map;
}

function groupLabel(groupBy, key) {
  switch (groupBy) {
    case 'phase': return PHASE_LABELS[key] || key;
    case 'type': return key.charAt(0).toUpperCase() + key.slice(1);
    case 'status': return key.replace('_', ' ').replace(/\b\w/g, c => c.toUpperCase());
    case 'none': return 'All Items';
    default: return key;
  }
}

function ItemRow({ item, isSelected, onSelect }) {
  const typeColor = TYPE_COLORS[item.type] || TYPE_COLORS.task;
  const statusColor = STATUS_COLORS[item.status] || STATUS_COLORS.planned;
  const { newIds, changedIds } = useContext(VisionChangesContext);
  const animClass = newIds.has(item.id) ? 'vision-entering' : changedIds.has(item.id) ? 'vision-updated' : '';

  return (
    <button
      onClick={() => onSelect(item.id)}
      className={cn(
        'flex w-full items-center gap-2 px-3 py-2 text-left transition-colors group',
        isSelected
          ? 'bg-accent/10 border-l-2 border-l-accent'
          : 'hover:bg-muted/50 border-l-2 border-l-transparent',
        animClass,
      )}
    >
      {/* Status dot */}
      <div
        className="w-2 h-2 rounded-full shrink-0"
        style={{ background: statusColor }}
        title={item.status}
      />

      {/* Type badge */}
      <span
        className="text-[10px] uppercase tracking-wider shrink-0 w-16 truncate"
        style={{ color: typeColor }}
      >
        {item.type}
      </span>

      {/* Title */}
      <span className={cn(
        'flex-1 text-sm truncate',
        isSelected ? 'text-foreground font-medium' : 'text-foreground',
        item.status === 'killed' && 'line-through opacity-50'
      )}>
        {item.title}
      </span>

      {/* Confidence */}
      <ConfidenceDots level={item.confidence || 0} />

      {/* Updated time */}
      <span className="text-[10px] text-muted-foreground tabular-nums w-8 text-right shrink-0">
        {relativeTime(item.updatedAt)}
      </span>
    </button>
  );
}

function ItemGroup({ groupKey, groupBy, items, selectedItemId, onSelect, defaultOpen }) {
  const [isOpen, setIsOpen] = useState(defaultOpen);
  const stats = useMemo(() => {
    if (items.length === 0) return { avg: -1, questions: 0 };
    const sum = items.reduce((acc, i) => acc + (i.confidence || 0), 0);
    const questions = items.filter(i => i.type === 'question' && (i.confidence || 0) < 2).length;
    return { avg: sum / items.length, questions };
  }, [items]);

  const avgColor = stats.avg >= 3.5 ? 'hsl(var(--success))' : stats.avg >= 2 ? 'hsl(var(--accent))' : 'hsl(var(--destructive))';

  return (
    <div>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex w-full items-center gap-2 px-3 py-2 hover:bg-muted/30 transition-colors"
      >
        {isOpen
          ? <ChevronDown className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
          : <ChevronRight className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
        }
        <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          {groupLabel(groupBy, groupKey)}
        </span>
        <span className="text-[10px] text-muted-foreground">{items.length}</span>

        {/* Confidence bar */}
        {stats.avg >= 0 && (
          <div className="h-1 w-12 rounded-full bg-muted ml-1">
            <div
              className="h-full rounded-full transition-all"
              style={{ width: `${(stats.avg / 4) * 100}%`, background: avgColor }}
            />
          </div>
        )}

        {/* Open questions indicator */}
        {stats.questions > 0 && (
          <Badge variant="outline" className="ml-auto text-[10px] px-1 py-0 h-4 text-destructive border-destructive/30">
            {stats.questions} open
          </Badge>
        )}
      </button>

      {isOpen && (
        <div>
          {items.length === 0 ? (
            <div className="px-3 py-4 text-xs text-muted-foreground text-center">
              No items in {groupLabel(groupBy, groupKey).toLowerCase()}
            </div>
          ) : (
            items.map(item => (
              <ItemRow
                key={item.id}
                item={item}
                isSelected={selectedItemId === item.id}
                onSelect={onSelect}
              />
            ))
          )}
        </div>
      )}
    </div>
  );
}

export default function ItemListView({ items, selectedItemId, onSelect, onCreate }) {
  const [groupBy, setGroupBy] = useState('phase');
  const [sortBy, setSortBy] = useState('confidence');

  const groups = useMemo(() => {
    const grouped = groupItems(items, groupBy);
    // Remove empty groups and sort items within each group
    for (const [key, groupedItems] of grouped) {
      if (groupedItems.length === 0) {
        grouped.delete(key);
      } else {
        grouped.set(key, sortItems(groupedItems, sortBy));
      }
    }
    return grouped;
  }, [items, groupBy, sortBy]);

  return (
    <div className="flex-1 overflow-auto flex flex-col">
      {/* Toolbar */}
      <div className="flex items-center gap-2 px-3 py-2 border-b border-border shrink-0">
        <label className="flex items-center gap-1">
          <span className="text-[10px] text-muted-foreground uppercase tracking-wider">Group</span>
          <select
            className="text-xs px-1.5 py-0.5 rounded bg-muted text-foreground border border-border cursor-pointer"
            value={groupBy}
            onChange={(e) => setGroupBy(e.target.value)}
          >
            <option value="phase">Phase</option>
            <option value="type">Type</option>
            <option value="status">Status</option>
            <option value="none">None</option>
          </select>
        </label>
        <label className="flex items-center gap-1">
          <span className="text-[10px] text-muted-foreground uppercase tracking-wider">Sort</span>
          <select
            className="text-xs px-1.5 py-0.5 rounded bg-muted text-foreground border border-border cursor-pointer"
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value)}
          >
            <option value="confidence">Confidence</option>
            <option value="updated">Updated</option>
            <option value="status">Status</option>
            <option value="alpha">A-Z</option>
          </select>
        </label>
        {onCreate && (
          <Button
            variant="outline"
            size="sm"
            className="h-6 w-6 p-0 ml-auto shrink-0"
            onClick={onCreate}
            title="Create new item"
          >
            <Plus className="h-3.5 w-3.5" />
          </Button>
        )}
      </div>

      {/* Groups */}
      <div className="flex-1 overflow-auto">
        {[...groups.entries()].map(([key, groupedItems]) => (
          groupBy === 'none' ? (
            <div key="all">
              {groupedItems.map(item => (
                <ItemRow
                  key={item.id}
                  item={item}
                  isSelected={selectedItemId === item.id}
                  onSelect={onSelect}
                />
              ))}
            </div>
          ) : (
            <ItemGroup
              key={key}
              groupKey={key}
              groupBy={groupBy}
              items={groupedItems}
              selectedItemId={selectedItemId}
              onSelect={onSelect}
              defaultOpen={groupedItems.length > 0}
            />
          )
        ))}
      </div>
    </div>
  );
}
