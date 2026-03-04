import React, { useState, useMemo, useCallback } from 'react';
import { cn } from '@/lib/utils.js';
import { Badge } from '@/components/ui/badge.jsx';
import { ScrollArea } from '@/components/ui/scroll-area.jsx';
import { ChevronRight, ChevronDown } from 'lucide-react';
import { TYPE_COLORS, STATUS_COLORS } from './constants.js';
import ConfidenceDots from './ConfidenceDots.jsx';

function TreeItem({ item, children, depth, selectedItemId, onSelect, onToggle, expandedIds }) {
  const hasChildren = children.length > 0;
  const isExpanded = expandedIds.has(item.id);
  const isSelected = selectedItemId === item.id;
  const typeColor = TYPE_COLORS[item.type] || TYPE_COLORS.task;
  const statusColor = STATUS_COLORS[item.status] || STATUS_COLORS.planned;

  return (
    <div>
      <div
        onClick={() => onSelect(item.id)}
        className={cn(
          'flex items-center gap-1.5 py-1 px-2 cursor-pointer transition-colors rounded-md',
          'hover:bg-accent/5',
          isSelected && 'bg-accent/10'
        )}
        style={{ paddingLeft: `${depth * 20 + 8}px` }}
      >
        {/* Expand toggle */}
        <button
          onClick={(e) => {
            e.stopPropagation();
            if (hasChildren) onToggle(item.id);
          }}
          className={cn(
            'shrink-0 w-4 h-4 flex items-center justify-center rounded',
            hasChildren ? 'text-muted-foreground hover:text-foreground' : 'invisible'
          )}
        >
          {hasChildren && (
            isExpanded
              ? <ChevronDown className="h-3.5 w-3.5" />
              : <ChevronRight className="h-3.5 w-3.5" />
          )}
        </button>

        {/* Status dot */}
        <div
          className="w-2 h-2 rounded-full shrink-0"
          style={{ background: statusColor }}
        />

        {/* Type badge */}
        <span
          className="text-[9px] uppercase tracking-wider shrink-0 w-12"
          style={{ color: typeColor }}
        >
          {item.type}
        </span>

        {/* Title */}
        <span className={cn(
          'text-sm text-foreground truncate flex-1',
          item.status === 'killed' && 'line-through opacity-50'
        )}>
          {item.title}
        </span>

        {/* Confidence */}
        <ConfidenceDots level={item.confidence || 0} />

        {/* Phase badge */}
        {item.phase && (
          <Badge variant="outline" className="text-[9px] px-1 py-0 h-3.5 shrink-0">
            {item.phase}
          </Badge>
        )}
      </div>

      {/* Children */}
      {hasChildren && isExpanded && (
        <div>
          {children.map(child => (
            <TreeItem
              key={child.id}
              item={child}
              children={child._children || []}
              depth={depth + 1}
              selectedItemId={selectedItemId}
              onSelect={onSelect}
              onToggle={onToggle}
              expandedIds={expandedIds}
            />
          ))}
        </div>
      )}
    </div>
  );
}

export default function TreeView({ items, connections, selectedItemId, onSelect }) {
  const [expandedIds, setExpandedIds] = useState(() => new Set());

  const onToggle = useCallback((id) => {
    setExpandedIds(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  // Build tree from connections:
  //   informs:  A informs B  → B.parent = A  (child consumes parent's output)
  //   supports: A supports B → A.parent = B  (evidence sits under what it supports)
  //   blocks:   A blocks B   → A.parent = B  (blocker is sub-problem of the blocked)
  const tree = useMemo(() => {
    const itemIds = new Set(items.map(i => i.id));
    const byId = new Map();
    for (const item of items) {
      byId.set(item.id, { ...item, _children: [] });
    }

    // Derive parentId from connections (first match wins)
    const parentOf = new Map();
    for (const conn of connections) {
      if (!itemIds.has(conn.fromId) || !itemIds.has(conn.toId)) continue;

      if (conn.type === 'informs') {
        // A informs B → B is child of A
        if (!parentOf.has(conn.toId)) parentOf.set(conn.toId, conn.fromId);
      } else if (conn.type === 'supports') {
        // A supports B → A is child of B
        if (!parentOf.has(conn.fromId)) parentOf.set(conn.fromId, conn.toId);
      } else if (conn.type === 'blocks') {
        // A blocks B → A is child of B
        if (!parentOf.has(conn.fromId)) parentOf.set(conn.fromId, conn.toId);
      }
    }

    // Also use parentId field if present (explicit hierarchy takes priority)
    for (const item of items) {
      if (item.parentId && byId.has(item.parentId)) {
        parentOf.set(item.id, item.parentId);
      }
    }

    // Detect cycles: walk up from each node, if we revisit → break it
    for (const [childId] of parentOf) {
      const visited = new Set();
      let cur = childId;
      while (cur && parentOf.has(cur)) {
        if (visited.has(cur)) { parentOf.delete(cur); break; }
        visited.add(cur);
        cur = parentOf.get(cur);
      }
    }

    // Build tree
    const roots = [];
    for (const item of byId.values()) {
      const pid = parentOf.get(item.id);
      if (pid && byId.has(pid)) {
        byId.get(pid)._children.push(item);
      } else {
        roots.push(item);
      }
    }

    // Sort children by confidence ascending (lowest first = needs attention)
    const sortChildren = (nodes) => {
      nodes.sort((a, b) => (a.confidence || 0) - (b.confidence || 0));
      for (const node of nodes) {
        if (node._children.length > 0) sortChildren(node._children);
      }
    };
    sortChildren(roots);

    return roots;
  }, [items, connections]);

  // Auto-expand roots on first render
  React.useEffect(() => {
    if (expandedIds.size === 0 && tree.length > 0) {
      setExpandedIds(new Set(tree.map(r => r.id)));
    }
  }, [tree]);

  const expandAll = useCallback(() => {
    const all = new Set();
    const walk = (nodes) => {
      for (const n of nodes) {
        if (n._children.length > 0) {
          all.add(n.id);
          walk(n._children);
        }
      }
    };
    walk(tree);
    setExpandedIds(all);
  }, [tree]);

  const collapseAll = useCallback(() => {
    setExpandedIds(new Set());
  }, []);

  // Count items with children vs orphans
  const withChildren = tree.filter(r => r._children.length > 0).length;

  return (
    <div className="flex-1 flex flex-col min-h-0">
      {/* Toolbar */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-border">
        <div className="flex items-center gap-2">
          <span className="text-xs text-muted-foreground">
            {items.length} items
            {withChildren > 0 && ` \u00B7 ${withChildren} with children`}
          </span>
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={expandAll}
            className="text-[10px] px-1.5 py-0.5 rounded text-muted-foreground hover:text-foreground hover:bg-accent/10 transition-colors"
          >
            Expand all
          </button>
          <button
            onClick={collapseAll}
            className="text-[10px] px-1.5 py-0.5 rounded text-muted-foreground hover:text-foreground hover:bg-accent/10 transition-colors"
          >
            Collapse all
          </button>
        </div>
      </div>

      {/* Tree */}
      <ScrollArea className="flex-1">
        <div className="py-1">
          {tree.length === 0 ? (
            <div className="flex items-center justify-center py-8 text-sm text-muted-foreground">
              No items to display
            </div>
          ) : (
            tree.map(item => (
              <TreeItem
                key={item.id}
                item={item}
                children={item._children}
                depth={0}
                selectedItemId={selectedItemId}
                onSelect={onSelect}
                onToggle={onToggle}
                expandedIds={expandedIds}
              />
            ))
          )}
        </div>
      </ScrollArea>
    </div>
  );
}
