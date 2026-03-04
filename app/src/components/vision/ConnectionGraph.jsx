import React, { useMemo, useState, useCallback } from 'react';
import { TYPE_COLORS, STATUS_COLORS, CONFIDENCE_LABELS } from './constants.js';

const NODE_W = 60;
const NODE_H = 24;
const SELECTED_W = 80;
const SELECTED_H = 28;
const ROW_GAP = 48;
const NODE_GAP = 8;
const MAX_PER_ROW = 5;
const FONT_SIZE = 9;

function truncate(str, len) {
  if (!str) return '';
  return str.length > len ? str.slice(0, len) + '\u2026' : str;
}

function buildNeighborhood(item, items, connections) {
  const itemMap = new Map(items.map(i => [i.id, i]));
  const parents = [];
  const children = [];
  const grandchildren = new Map(); // childId -> grandchild items

  for (const conn of connections) {
    if (conn.toId === item.id) {
      const parent = itemMap.get(conn.fromId);
      if (parent) parents.push(parent);
    }
    if (conn.fromId === item.id) {
      const child = itemMap.get(conn.toId);
      if (child) children.push(child);
    }
  }

  // Grandchildren: one more level down from children
  for (const child of children) {
    const gc = [];
    for (const conn of connections) {
      if (conn.fromId === child.id && conn.toId !== item.id) {
        const grandchild = itemMap.get(conn.toId);
        if (grandchild) gc.push(grandchild);
      }
    }
    if (gc.length > 0) grandchildren.set(child.id, gc);
  }

  return { parents, children, grandchildren };
}

function layoutRow(count, y, svgWidth, nodeW, nodeH) {
  const capped = Math.min(count, MAX_PER_ROW);
  const totalW = capped * nodeW + (capped - 1) * NODE_GAP;
  const startX = (svgWidth - totalW) / 2;
  const positions = [];
  for (let i = 0; i < capped; i++) {
    positions.push({ x: startX + i * (nodeW + NODE_GAP), y, w: nodeW, h: nodeH });
  }
  return { positions, overflow: count > MAX_PER_ROW ? count - MAX_PER_ROW + 1 : 0 };
}

function NodeRect({ item, x, y, w, h, isSelected, isDashed, onSelect, onHover, onLeave }) {
  const typeColor = TYPE_COLORS[item.type] || TYPE_COLORS.task;
  const fillOpacity = isSelected ? 0.2 : 0.08;

  return (
    <g
      style={{ cursor: 'pointer' }}
      onClick={() => onSelect(item.id)}
      onMouseEnter={(e) => onHover(item, e)}
      onMouseLeave={onLeave}
    >
      <rect
        x={x}
        y={y}
        width={w}
        height={h}
        rx={4}
        fill={typeColor}
        fillOpacity={fillOpacity}
        stroke={typeColor}
        strokeWidth={isSelected ? 2 : 1.5}
        strokeDasharray={isDashed ? '4 2' : undefined}
      />
      <text
        x={x + w / 2}
        y={y + h / 2}
        textAnchor="middle"
        dominantBaseline="central"
        fontSize={isSelected ? FONT_SIZE + 1 : FONT_SIZE}
        fontWeight={isSelected ? 600 : 400}
        fill="hsl(var(--foreground))"
      >
        {truncate(item.title, isSelected ? 10 : 8)}
      </text>
    </g>
  );
}

function Tooltip({ item, pos }) {
  if (!item || !pos) return null;
  const typeColor = TYPE_COLORS[item.type] || TYPE_COLORS.task;
  const statusColor = STATUS_COLORS[item.status] || STATUS_COLORS.planned;

  return (
    <div
      className="absolute z-50 pointer-events-none px-2 py-1.5 rounded bg-popover border border-border shadow-md"
      style={{ left: pos.x, top: pos.y, transform: 'translate(-50%, -100%)' }}
    >
      <p className="text-xs font-medium text-foreground whitespace-nowrap">{item.title}</p>
      <div className="flex items-center gap-2 mt-0.5">
        <span className="text-[10px]" style={{ color: typeColor }}>{item.type}</span>
        <span className="text-[10px] flex items-center gap-1">
          <span className="inline-block w-1.5 h-1.5 rounded-full" style={{ background: statusColor }} />
          {item.status}
        </span>
        <span className="text-[10px] text-muted-foreground">
          {CONFIDENCE_LABELS[item.confidence || 0]}
        </span>
      </div>
    </div>
  );
}

export default function ConnectionGraph({ item, items, connections, onSelect }) {
  const [hovered, setHovered] = useState(null);
  const [tooltipPos, setTooltipPos] = useState(null);

  const { parents, children, grandchildren } = useMemo(
    () => buildNeighborhood(item, items, connections),
    [item, items, connections]
  );

  const handleHover = useCallback((hovItem, e) => {
    const rect = e.currentTarget.closest('.connection-graph-wrap').getBoundingClientRect();
    const svgRect = e.currentTarget.getBoundingClientRect();
    setHovered(hovItem);
    setTooltipPos({
      x: svgRect.x + svgRect.width / 2 - rect.x,
      y: svgRect.y - rect.y - 4,
    });
  }, []);

  const handleLeave = useCallback(() => {
    setHovered(null);
    setTooltipPos(null);
  }, []);

  const hasConnections = parents.length > 0 || children.length > 0;
  if (!hasConnections) return null;

  // Compute layout
  const svgWidth = 288;
  const rows = [];
  const lines = [];

  // Parent row
  let currentY = 12;
  let parentPositions = [];
  let parentOverflow = 0;
  if (parents.length > 0) {
    const layout = layoutRow(parents.length, currentY, svgWidth, NODE_W, NODE_H);
    parentPositions = layout.positions;
    parentOverflow = layout.overflow;
    currentY += NODE_H + ROW_GAP;
  }

  // Selected item row
  const selX = (svgWidth - SELECTED_W) / 2;
  const selY = currentY;
  currentY += SELECTED_H + ROW_GAP;

  // Children row
  let childPositions = [];
  let childOverflow = 0;
  if (children.length > 0) {
    const layout = layoutRow(children.length, currentY, svgWidth, NODE_W, NODE_H);
    childPositions = layout.positions;
    childOverflow = layout.overflow;
    currentY += NODE_H;
  }

  // Grandchildren row
  let gcPositions = new Map();
  let gcOverflows = new Map();
  const allGc = [...grandchildren.entries()];
  let gcFlatItems = [];
  if (allGc.length > 0) {
    currentY += ROW_GAP;
    for (const [childId, gcs] of allGc) {
      for (const gc of gcs) gcFlatItems.push({ ...gc, _parentChildId: childId });
    }
    const layout = layoutRow(gcFlatItems.length, currentY, svgWidth, NODE_W, NODE_H);
    // Map positions back
    let idx = 0;
    for (const [childId, gcs] of allGc) {
      const positions = [];
      for (let i = 0; i < gcs.length && idx < layout.positions.length; i++, idx++) {
        positions.push(layout.positions[idx]);
      }
      gcPositions.set(childId, positions);
    }
    if (layout.overflow > 0) gcOverflows.set('all', layout.overflow);
    currentY += NODE_H;
  }

  const svgHeight = currentY + 12;

  // Lines: parents -> selected
  for (let i = 0; i < parentPositions.length; i++) {
    const pp = parentPositions[i];
    lines.push({
      x1: pp.x + pp.w / 2, y1: pp.y + pp.h,
      x2: selX + SELECTED_W / 2, y2: selY,
    });
  }

  // Lines: selected -> children
  for (let i = 0; i < childPositions.length; i++) {
    const cp = childPositions[i];
    lines.push({
      x1: selX + SELECTED_W / 2, y1: selY + SELECTED_H,
      x2: cp.x + cp.w / 2, y2: cp.y,
    });
  }

  // Lines: children -> grandchildren
  for (const [childId, gcPos] of gcPositions) {
    const childIdx = children.findIndex(c => c.id === childId);
    if (childIdx >= 0 && childIdx < childPositions.length) {
      const cp = childPositions[childIdx];
      for (const gp of gcPos) {
        lines.push({
          x1: cp.x + cp.w / 2, y1: cp.y + cp.h,
          x2: gp.x + gp.w / 2, y2: gp.y,
        });
      }
    }
  }

  const displayedParents = parents.slice(0, MAX_PER_ROW - (parentOverflow > 0 ? 1 : 0));
  const displayedChildren = children.slice(0, MAX_PER_ROW - (childOverflow > 0 ? 1 : 0));
  const displayedGc = gcFlatItems.slice(0, MAX_PER_ROW - (gcOverflows.size > 0 ? 1 : 0));

  return (
    <div className="space-y-1">
      <p className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground">Graph</p>
      <div className="relative connection-graph-wrap">
        <svg width={svgWidth} height={svgHeight} className="w-full" viewBox={`0 0 ${svgWidth} ${svgHeight}`}>
          {/* Connection lines */}
          {lines.map((l, i) => (
            <line
              key={i}
              x1={l.x1} y1={l.y1} x2={l.x2} y2={l.y2}
              stroke="hsl(var(--muted-foreground))"
              strokeOpacity={0.3}
              strokeWidth={1}
            />
          ))}

          {/* Parent nodes */}
          {displayedParents.map((p, i) => (
            <NodeRect
              key={p.id}
              item={p}
              x={parentPositions[i].x}
              y={parentPositions[i].y}
              w={NODE_W}
              h={NODE_H}
              isSelected={false}
              isDashed={true}
              onSelect={onSelect}
              onHover={handleHover}
              onLeave={handleLeave}
            />
          ))}
          {parentOverflow > 0 && (
            <text
              x={parentPositions[parentPositions.length - 1].x + NODE_W / 2}
              y={parentPositions[0].y + NODE_H / 2}
              textAnchor="middle"
              dominantBaseline="central"
              fontSize={FONT_SIZE}
              fill="hsl(var(--muted-foreground))"
            >
              +{parentOverflow} more
            </text>
          )}

          {/* Selected node */}
          <NodeRect
            item={item}
            x={selX}
            y={selY}
            w={SELECTED_W}
            h={SELECTED_H}
            isSelected={true}
            isDashed={false}
            onSelect={onSelect}
            onHover={handleHover}
            onLeave={handleLeave}
          />

          {/* Child nodes */}
          {displayedChildren.map((c, i) => (
            <NodeRect
              key={c.id}
              item={c}
              x={childPositions[i].x}
              y={childPositions[i].y}
              w={NODE_W}
              h={NODE_H}
              isSelected={false}
              isDashed={false}
              onSelect={onSelect}
              onHover={handleHover}
              onLeave={handleLeave}
            />
          ))}
          {childOverflow > 0 && (
            <text
              x={childPositions[childPositions.length - 1].x + NODE_W / 2}
              y={childPositions[0].y + NODE_H / 2}
              textAnchor="middle"
              dominantBaseline="central"
              fontSize={FONT_SIZE}
              fill="hsl(var(--muted-foreground))"
            >
              +{childOverflow} more
            </text>
          )}

          {/* Grandchild nodes */}
          {displayedGc.map((gc, i) => {
            // Find position from the flat layout
            const gcAllPositions = [...gcPositions.values()].flat();
            const pos = gcAllPositions[i];
            if (!pos) return null;
            return (
              <NodeRect
                key={gc.id}
                item={gc}
                x={pos.x}
                y={pos.y}
                w={NODE_W}
                h={NODE_H}
                isSelected={false}
                isDashed={false}
                onSelect={onSelect}
                onHover={handleHover}
                onLeave={handleLeave}
              />
            );
          })}
        </svg>

        <Tooltip item={hovered} pos={tooltipPos} />
      </div>
    </div>
  );
}
