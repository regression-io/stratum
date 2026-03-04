import React, { useRef, useEffect, useState, useCallback, useMemo } from 'react';
import cytoscape from 'cytoscape';
import cytoscapeDagre from 'cytoscape-dagre';
import { TYPE_COLORS, PHASE_LABELS, CONFIDENCE_LABELS } from './constants.js';

// Register dagre layout (idempotent in recent cytoscape versions)
try { cytoscape.use(cytoscapeDagre); } catch (e) { /* already registered */ }

// ─── Constants ──────────────────────────────────────────────────────────────

// Cytoscape can't resolve CSS custom properties — hardcode hex
const STATUS_HEX = {
  planned:     '#64748b',
  ready:       '#3b82f6',
  in_progress: '#fbbf24',
  review:      '#f59e0b',
  complete:    '#22c55e',
  blocked:     '#ef4444',
  parked:      '#6b7280',
  killed:      '#475569',
};

// Dark background tints for each type (15% type color mixed with #0f172a)
const TYPE_BG = Object.fromEntries(
  Object.entries(TYPE_COLORS).map(([k, hex]) => {
    const r = parseInt(hex.slice(1, 3), 16);
    const g = parseInt(hex.slice(3, 5), 16);
    const b = parseInt(hex.slice(5, 7), 16);
    const bg = [15, 23, 42]; // #0f172a
    const mix = 0.15;
    const c = [
      Math.round(bg[0] * (1 - mix) + r * mix),
      Math.round(bg[1] * (1 - mix) + g * mix),
      Math.round(bg[2] * (1 - mix) + b * mix),
    ];
    return [k, `#${c.map(v => v.toString(16).padStart(2, '0')).join('')}`];
  })
);

// Confidence (0-4) → border width
const CONF_BORDER = [1, 1.5, 2, 2.5, 3];

// Edge type config
const EDGE_CONFIG = {
  informs:     { color: '#64748b', style: 'solid' },
  supports:    { color: '#22c55e', style: 'solid' },
  blocks:      { color: '#ef4444', style: 'solid' },
  contradicts: { color: '#f472b6', style: 'dashed' },
  implements:  { color: '#a78bfa', style: 'solid' },
};

const STATUS_FILTERS = [
  { key: 'all',      label: 'All',     statuses: null },
  { key: 'active',   label: 'Active',  statuses: ['planned', 'ready', 'in_progress', 'review'] },
  { key: 'complete', label: 'Done',    statuses: ['complete'] },
  { key: 'blocked',  label: 'Blocked', statuses: ['blocked', 'parked'] },
];

// ─── Helpers ────────────────────────────────────────────────────────────────

function buildElements(items, connections, grouped) {
  const elements = [];
  const itemIds = new Set(items.map(i => i.id));

  // Compound parent nodes by type
  if (grouped) {
    const types = [...new Set(items.map(i => i.type).filter(Boolean))];
    for (const type of types) {
      elements.push({
        data: {
          id: `type-${type}`,
          label: type.charAt(0).toUpperCase() + type.slice(1),
          isGroup: true,
          groupType: type,
        },
      });
    }
  }

  // Item nodes
  for (const item of items) {
    const slug = item.slug || item.id.slice(0, 8);
    const title = (item.title || '').length > 22
      ? item.title.slice(0, 22) + '\u2026'
      : item.title || '';

    elements.push({
      data: {
        id: item.id,
        label: `${slug}\n${title}`,
        itemType: item.type || 'task',
        status: item.status || 'planned',
        phase: item.phase || 'vision',
        confidence: item.confidence ?? 0,
        title: item.title,
        description: item.description,
        slug,
        ...(grouped && item.type ? { parent: `type-${item.type}` } : {}),
      },
    });
  }

  // Edges
  for (const conn of connections) {
    if (!itemIds.has(conn.fromId) || !itemIds.has(conn.toId)) continue;

    // Direction depends on connection type
    let source, target;
    if (conn.type === 'supports' || conn.type === 'blocks') {
      source = conn.toId;
      target = conn.fromId;
    } else {
      source = conn.fromId;
      target = conn.toId;
    }

    const cfg = EDGE_CONFIG[conn.type] || EDGE_CONFIG.informs;
    elements.push({
      data: {
        id: conn.id || `${conn.fromId}-${conn.toId}`,
        source,
        target,
        edgeType: conn.type,
        edgeColor: cfg.color,
        edgeStyle: cfg.style,
      },
    });
  }

  return elements;
}

function buildStylesheet() {
  return [
    // Group compound nodes
    {
      selector: '[?isGroup]',
      style: {
        'label': 'data(label)',
        'text-valign': 'top',
        'text-halign': 'center',
        'font-size': '10px',
        'font-weight': 600,
        'color': '#64748b',
        'text-transform': 'uppercase',
        'letter-spacing': '0.08em',
        'background-color': '#1a2537',
        'border-width': 1,
        'border-color': '#283548',
        'border-style': 'solid',
        'padding': '18px',
        'text-margin-y': 0,
      },
    },
    // Item nodes
    {
      selector: 'node[status]',
      style: {
        'label': 'data(label)',
        'text-valign': 'center',
        'text-halign': 'center',
        'font-size': '9px',
        'font-family': '-apple-system, BlinkMacSystemFont, "Segoe UI", monospace',
        'font-weight': 500,
        'color': '#e2e8f0',
        'text-wrap': 'wrap',
        'text-max-width': '100px',
        'width': '120px',
        'height': '48px',
        'shape': 'round-rectangle',
        'background-color': '#1e293b',
        'border-style': 'solid',
        'border-width': 2,
        'border-color': '#3b82f6',
      },
    },
    // Status border colors
    ...Object.entries(STATUS_HEX).map(([status, color]) => ({
      selector: `node[status="${status}"]`,
      style: {
        'border-color': color,
        ...(status === 'parked' || status === 'killed' ? { opacity: 0.7 } : {}),
      },
    })),
    // Type background tints
    ...Object.entries(TYPE_BG).map(([type, bg]) => ({
      selector: `node[itemType="${type}"]`,
      style: { 'background-color': bg },
    })),
    // Confidence border weight
    ...CONF_BORDER.map((w, i) => ({
      selector: `node[confidence=${i}]`,
      style: { 'border-width': w },
    })),
    // Selected node
    {
      selector: 'node:selected',
      style: {
        'background-color': '#1e3a5f',
        'border-width': 3,
        'border-color': '#60a5fa',
      },
    },
    // Edges
    {
      selector: 'edge',
      style: {
        'width': 1.5,
        'line-color': 'data(edgeColor)',
        'target-arrow-color': 'data(edgeColor)',
        'target-arrow-shape': 'triangle',
        'arrow-scale': 0.8,
        'curve-style': 'bezier',
        'opacity': 0.6,
      },
    },
    // Dashed edges (contradicts)
    {
      selector: 'edge[edgeStyle="dashed"]',
      style: {
        'line-style': 'dashed',
        'line-dash-pattern': [6, 3],
        'target-arrow-shape': 'diamond',
      },
    },
    // Blocks edges use tee arrow
    {
      selector: 'edge[edgeType="blocks"]',
      style: { 'target-arrow-shape': 'tee' },
    },
    // Dimmed (for dependency chain highlighting)
    {
      selector: '.dimmed',
      style: { opacity: 0.12 },
    },
    // Highlighted
    {
      selector: '.highlighted',
      style: { 'border-width': 3, 'border-color': '#60a5fa' },
    },
  ];
}

// ─── Tooltip component ──────────────────────────────────────────────────────

function Tooltip({ data }) {
  if (!data) return null;
  const { x, y, item } = data;
  const statusColor = STATUS_HEX[item.status] || STATUS_HEX.planned;
  const typeColor = TYPE_COLORS[item.itemType] || '#94a3b8';

  // Keep tooltip on screen
  const left = x + 300 > window.innerWidth ? x - 294 : x + 14;
  const top = Math.min(y - 10, window.innerHeight - 200);

  return (
    <div
      style={{
        position: 'fixed', left, top, zIndex: 9999,
        pointerEvents: 'none', maxWidth: 280,
        background: '#1e293b', border: '1px solid #475569',
        borderRadius: 8, padding: '10px 13px', fontSize: 12,
        boxShadow: '0 8px 24px rgba(0,0,0,0.5)',
      }}
    >
      <div style={{ fontWeight: 700, fontSize: 13, color: '#f8fafc', marginBottom: 3 }}>
        {item.slug}
      </div>
      <div style={{ color: '#94a3b8', marginBottom: 6, lineHeight: 1.4 }}>
        {item.title}
      </div>
      <div style={{ display: 'flex', gap: 6, alignItems: 'center', flexWrap: 'wrap' }}>
        <Badge color={statusColor}>{(item.status || 'planned').replace('_', ' ')}</Badge>
        <Badge color={typeColor}>{item.itemType}</Badge>
        {item.phase && <Badge color="#94a3b8">{PHASE_LABELS[item.phase] || item.phase}</Badge>}
      </div>
      {item.description && (
        <div style={{ marginTop: 8, color: '#94a3b8', fontSize: 11, lineHeight: 1.4 }}>
          {item.description.length > 140 ? item.description.slice(0, 140) + '\u2026' : item.description}
        </div>
      )}
      <div style={{ marginTop: 6, color: '#64748b', fontSize: 10 }}>
        {CONFIDENCE_LABELS[item.confidence || 0]} confidence
      </div>
    </div>
  );
}

function Badge({ color, children }) {
  return (
    <span style={{
      fontSize: 10, padding: '1px 6px', borderRadius: 3, fontWeight: 600,
      background: `${color}20`, color, border: `1px solid ${color}40`,
      textTransform: 'uppercase', letterSpacing: '0.03em',
    }}>
      {children}
    </span>
  );
}

// ─── Toolbar button ─────────────────────────────────────────────────────────

const btnBase = {
  fontSize: 11, padding: '3px 9px', borderRadius: 4, cursor: 'pointer',
  transition: 'all 0.15s',
};

function FilterBtn({ active, onClick, children }) {
  return (
    <button onClick={onClick} style={{
      ...btnBase,
      border: `1px solid ${active ? '#3b82f6' : '#334155'}`,
      background: active ? '#3b82f6' : '#1e293b',
      color: active ? '#fff' : '#94a3b8',
    }}>
      {children}
    </button>
  );
}

function CtrlBtn({ onClick, children, title }) {
  return (
    <button onClick={onClick} title={title} style={{
      ...btnBase,
      border: '1px solid #334155', background: '#1e293b', color: '#94a3b8',
    }}>
      {children}
    </button>
  );
}

// ─── Main component ─────────────────────────────────────────────────────────

export default function GraphView({ items, connections, selectedItemId, onSelect }) {
  const containerRef = useRef(null);
  const cyRef = useRef(null);
  const [tooltip, setTooltip] = useState(null);
  const [statusFilter, setStatusFilter] = useState('all');
  const [grouped, setGrouped] = useState(true);
  const [rankDir, setRankDir] = useState('LR');
  const [showLegend, setShowLegend] = useState(true);

  // Filter items by status
  const filteredItems = useMemo(() => {
    const preset = STATUS_FILTERS.find(f => f.key === statusFilter);
    if (!preset?.statuses) return items;
    return items.filter(i => preset.statuses.includes(i.status || 'planned'));
  }, [items, statusFilter]);

  // Filter connections to visible items
  const filteredConnections = useMemo(() => {
    const ids = new Set(filteredItems.map(i => i.id));
    return connections.filter(c => ids.has(c.fromId) && ids.has(c.toId));
  }, [connections, filteredItems]);

  const elements = useMemo(
    () => buildElements(filteredItems, filteredConnections, grouped),
    [filteredItems, filteredConnections, grouped],
  );

  const stylesheet = useMemo(() => buildStylesheet(), []);

  // ─── Cytoscape lifecycle ────────────────────────────────────────────────

  useEffect(() => {
    if (!containerRef.current) return;

    const cy = cytoscape({
      container: containerRef.current,
      elements,
      style: stylesheet,
      layout: {
        name: 'dagre',
        rankDir,
        nodeSep: 30,
        rankSep: 70,
        edgeSep: 10,
        padding: 20,
        animate: false,
        fit: true,
      },
      minZoom: 0.1,
      maxZoom: 4,
      wheelSensitivity: 0.3,
      boxSelectionEnabled: false,
    });
    cyRef.current = cy;

    // Highlight initially selected item
    if (selectedItemId) {
      const node = cy.$id(selectedItemId);
      if (node.length) {
        highlightChain(cy, node);
        setTimeout(() => cy.animate({ center: { eles: node }, duration: 300 }), 100);
      }
    }

    // Tooltip on hover
    cy.on('mouseover', 'node[status]', (evt) => {
      const pos = evt.renderedPosition || evt.position;
      const rect = cy.container().getBoundingClientRect();
      setTooltip({ x: rect.left + pos.x, y: rect.top + pos.y, item: evt.target.data() });
    });

    cy.on('mousemove', 'node[status]', (evt) => {
      const pos = evt.renderedPosition || evt.position;
      const rect = cy.container().getBoundingClientRect();
      setTooltip(prev => prev ? { x: rect.left + pos.x, y: rect.top + pos.y, item: prev.item } : null);
    });

    cy.on('mouseout', 'node[status]', () => setTooltip(null));

    // Click: highlight dependency chain + select
    cy.on('tap', 'node[status]', (evt) => {
      highlightChain(cy, evt.target);
      onSelect(evt.target.id());
    });

    // Tap background: clear highlighting
    cy.on('tap', (evt) => {
      if (evt.target === cy) {
        cy.elements().removeClass('dimmed highlighted');
      }
    });

    return () => { cy.destroy(); cyRef.current = null; };
  }, [elements, stylesheet, rankDir]); // eslint-disable-line react-hooks/exhaustive-deps

  // ─── Actions ────────────────────────────────────────────────────────────

  const handleFit = useCallback(() => cyRef.current?.fit(undefined, 40), []);
  const handleZoomIn = useCallback(() => {
    const cy = cyRef.current;
    if (cy) cy.zoom({ level: cy.zoom() * 1.3, renderedPosition: { x: cy.width() / 2, y: cy.height() / 2 } });
  }, []);
  const handleZoomOut = useCallback(() => {
    const cy = cyRef.current;
    if (cy) cy.zoom({ level: cy.zoom() / 1.3, renderedPosition: { x: cy.width() / 2, y: cy.height() / 2 } });
  }, []);

  // ─── Render ─────────────────────────────────────────────────────────────

  return (
    <div className="flex-1 flex flex-col min-h-0" style={{ background: '#0f172a' }}>
      {/* Toolbar */}
      <div className="flex items-center justify-between px-3 py-2 shrink-0"
        style={{ background: '#1e293b', borderBottom: '1px solid #334155' }}>
        <div className="flex items-center gap-2">
          <span style={{ fontSize: 11, color: '#64748b' }}>Status:</span>
          {STATUS_FILTERS.map(f => (
            <FilterBtn key={f.key} active={statusFilter === f.key} onClick={() => setStatusFilter(f.key)}>
              {f.label}
            </FilterBtn>
          ))}
          <Sep />
          <span style={{ fontSize: 10, color: '#475569' }}>
            {filteredItems.length} items &middot; {filteredConnections.length} edges
          </span>
        </div>
        <div className="flex items-center gap-1">
          <FilterBtn active={grouped} onClick={() => setGrouped(!grouped)}>Group</FilterBtn>
          <CtrlBtn onClick={() => setRankDir(d => d === 'LR' ? 'TB' : 'LR')} title="Toggle direction">
            {rankDir === 'LR' ? '\u2192' : '\u2193'}
          </CtrlBtn>
          <Sep />
          <CtrlBtn onClick={handleZoomOut} title="Zoom out">&minus;</CtrlBtn>
          <CtrlBtn onClick={handleFit} title="Fit to view">Fit</CtrlBtn>
          <CtrlBtn onClick={handleZoomIn} title="Zoom in">+</CtrlBtn>
          <Sep />
          <FilterBtn active={showLegend} onClick={() => setShowLegend(!showLegend)}>Legend</FilterBtn>
        </div>
      </div>

      {/* Graph + overlays */}
      <div className="flex-1 relative min-h-0">
        <div ref={containerRef} className="w-full h-full" />

        {/* Legend */}
        {showLegend && (
          <div style={{
            position: 'absolute', bottom: 16, left: 16, zIndex: 10,
            background: '#1e293b', border: '1px solid #334155',
            borderRadius: 8, padding: '10px 13px', fontSize: 11,
            maxHeight: 'calc(100% - 32px)', overflowY: 'auto',
          }}>
            <LegendSection title="Types">
              {Object.entries(TYPE_COLORS).map(([type, color]) => (
                <LegendRow key={type}>
                  <LegendDot color={color} />
                  {type}
                </LegendRow>
              ))}
            </LegendSection>
            <LegendSep />
            <LegendSection title="Status">
              {Object.entries(STATUS_HEX).map(([status, color]) => (
                <LegendRow key={status}>
                  <LegendDot color={color} />
                  {status.replace('_', ' ')}
                </LegendRow>
              ))}
            </LegendSection>
            <LegendSep />
            <LegendSection title="Edges">
              {Object.entries(EDGE_CONFIG).map(([type, cfg]) => (
                <LegendRow key={type}>
                  <svg width="22" height="6" style={{ flexShrink: 0 }}>
                    <line x1="0" y1="3" x2="22" y2="3" stroke={cfg.color} strokeWidth="1.5"
                      strokeDasharray={cfg.style === 'dashed' ? '6,3' : 'none'} />
                  </svg>
                  {type}
                </LegendRow>
              ))}
            </LegendSection>
            <LegendSep />
            <div style={{ fontSize: 10, color: '#475569' }}>
              Border weight = confidence<br />
              Click node to trace deps
            </div>
          </div>
        )}

        <Tooltip data={tooltip} />
      </div>
    </div>
  );
}

// ─── Graph helpers ──────────────────────────────────────────────────────────

function highlightChain(cy, node) {
  cy.elements().removeClass('dimmed highlighted');
  const connected = node
    .union(node.predecessors('node[status]'))
    .union(node.successors('node[status]'));
  const connectedEdges = connected.edgesWith(connected);
  // Dim only item nodes, not compound parents (which would hide children)
  cy.nodes('[status]').not(connected).addClass('dimmed');
  cy.edges().not(connectedEdges).addClass('dimmed');
  node.addClass('highlighted');
}

// ─── Small layout components ────────────────────────────────────────────────

function Sep() {
  return <div style={{ width: 1, height: 20, background: '#334155', margin: '0 2px' }} />;
}

function LegendSection({ title, children }) {
  return (
    <>
      <div style={{
        fontSize: 10, color: '#64748b', textTransform: 'uppercase',
        letterSpacing: '0.08em', marginBottom: 5, fontWeight: 700,
      }}>
        {title}
      </div>
      {children}
    </>
  );
}

function LegendSep() {
  return <div style={{ height: 1, background: '#334155', margin: '6px 0' }} />;
}

function LegendRow({ children }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 7, marginBottom: 3, color: '#94a3b8' }}>
      {children}
    </div>
  );
}

function LegendDot({ color }) {
  return <div style={{ width: 10, height: 10, borderRadius: 2, background: color, flexShrink: 0 }} />;
}

// Force full remount on Vite HMR
if (import.meta.hot) import.meta.hot.accept();
