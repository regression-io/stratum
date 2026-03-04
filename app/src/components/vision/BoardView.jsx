import React, { useCallback, useContext } from 'react';
import { cn } from '@/lib/utils.js';
import { Badge } from '@/components/ui/badge.jsx';
import { ScrollArea } from '@/components/ui/scroll-area.jsx';
import { TYPE_COLORS, STATUS_COLORS } from './constants.js';
import ConfidenceDots from './ConfidenceDots.jsx';
import { VisionChangesContext } from './VisionTracker.jsx';

const COLUMNS = [
  { key: 'planned', label: 'Planned' },
  { key: 'ready', label: 'Ready' },
  { key: 'in_progress', label: 'In Progress' },
  { key: 'review', label: 'Review' },
  { key: 'complete', label: 'Complete' },
  { key: 'blocked', label: 'Blocked' },
];

function BoardCard({ item, isSelected, onSelect, onDragStart }) {
  const typeColor = TYPE_COLORS[item.type] || TYPE_COLORS.task;
  const { newIds, changedIds } = useContext(VisionChangesContext);
  const animClass = newIds.has(item.id) ? 'vision-entering' : changedIds.has(item.id) ? 'vision-updated' : '';

  return (
    <div
      draggable
      onDragStart={(e) => {
        e.dataTransfer.setData('text/plain', item.id);
        e.dataTransfer.effectAllowed = 'move';
        onDragStart(item.id);
      }}
      onClick={() => onSelect(item.id)}
      className={cn(
        'rounded-lg p-2.5 cursor-pointer transition-all select-none',
        'border hover:border-border/80',
        isSelected
          ? 'bg-accent/10 border-accent shadow-sm'
          : 'bg-card border-border/50 hover:bg-card/80',
        animClass,
      )}
    >
      {/* Title */}
      <p className={cn(
        'text-sm text-foreground leading-tight mb-1.5',
        item.status === 'killed' && 'line-through opacity-50'
      )}>
        {item.title}
      </p>

      {/* Type + confidence row */}
      <div className="flex items-center justify-between">
        <span className="text-[10px] uppercase tracking-wider" style={{ color: typeColor }}>
          {item.type}
        </span>
        <ConfidenceDots level={item.confidence || 0} />
      </div>

      {/* Phase badge if present */}
      {item.phase && (
        <Badge variant="outline" className="text-[9px] px-1 py-0 h-3.5 mt-1.5">
          {item.phase}
        </Badge>
      )}
    </div>
  );
}

function BoardColumn({ column, items, selectedItemId, onSelect, onDragStart, onDrop }) {
  const handleDragOver = useCallback((e) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
  }, []);

  const handleDrop = useCallback((e) => {
    e.preventDefault();
    const itemId = e.dataTransfer.getData('text/plain');
    if (itemId) onDrop(itemId, column.key);
  }, [column.key, onDrop]);

  const color = STATUS_COLORS[column.key];

  return (
    <div
      className="flex flex-col min-w-[200px] w-[200px] shrink-0"
      onDragOver={handleDragOver}
      onDrop={handleDrop}
    >
      {/* Column header */}
      <div className="flex items-center gap-2 px-2 py-2 mb-1">
        <div className="w-2 h-2 rounded-full shrink-0" style={{ background: color }} />
        <span className="text-xs font-medium text-foreground">{column.label}</span>
        <span className="text-[10px] text-muted-foreground">{items.length}</span>
      </div>

      {/* Cards */}
      <ScrollArea className="flex-1">
        <div className="space-y-1.5 px-1 pb-2">
          {items.map(item => (
            <BoardCard
              key={item.id}
              item={item}
              isSelected={selectedItemId === item.id}
              onSelect={onSelect}
              onDragStart={onDragStart}
            />
          ))}
          {items.length === 0 && (
            <div className="rounded-lg border border-dashed border-border/30 p-3 text-center">
              <span className="text-[10px] text-muted-foreground">No items</span>
            </div>
          )}
        </div>
      </ScrollArea>
    </div>
  );
}

export default function BoardView({ items, selectedItemId, onSelect, onUpdateStatus }) {
  const [draggingId, setDraggingId] = React.useState(null);

  const handleDrop = useCallback((itemId, newStatus) => {
    setDraggingId(null);
    onUpdateStatus(itemId, newStatus);
  }, [onUpdateStatus]);

  // Group items by status, filtering out parked/killed
  const { columnItems, hiddenCount } = React.useMemo(() => {
    const map = {};
    let hidden = 0;
    for (const col of COLUMNS) map[col.key] = [];
    for (const item of items) {
      const status = item.status || 'planned';
      if (status === 'parked' || status === 'killed') {
        hidden++;
      } else if (map[status]) {
        map[status].push(item);
      } else {
        map.planned.push(item);
      }
    }
    return { columnItems: map, hiddenCount: hidden };
  }, [items]);

  return (
    <div className="flex-1 flex flex-col min-h-0">
      <div className="flex-1 flex overflow-x-auto gap-2 p-3 min-h-0">
        {COLUMNS.map(column => (
          <BoardColumn
            key={column.key}
            column={column}
            items={columnItems[column.key] || []}
            selectedItemId={selectedItemId}
            onSelect={onSelect}
            onDragStart={setDraggingId}
            onDrop={handleDrop}
          />
        ))}
      </div>
      {hiddenCount > 0 && (
        <div className="px-3 pb-2 text-[10px] text-muted-foreground">
          {hiddenCount} parked/killed item{hiddenCount !== 1 ? 's' : ''} hidden
        </div>
      )}
    </div>
  );
}
