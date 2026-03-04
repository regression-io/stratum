import React, { useRef, useEffect, useCallback, useState, useMemo } from 'react';
import cytoscape from 'cytoscape';
import cytoscapeDagre from 'cytoscape-dagre';

cytoscape.use(cytoscapeDagre);

/**
 * GraphRenderer — Cytoscape-based graph for the canvas.
 *
 * Props:
 *   nodes: [{ id, label, sublabel?, color?, parent?, shape? }]
 *   edges: [{ from, to, label?, color?, style?, type? }]
 *   elements: cytoscape elements array (alternative to nodes/edges)
 *   layout: cytoscape layout options (default: dagre TB)
 *   style: cytoscape stylesheet array (default: Compose design tokens)
 *   title?: string
 *   subtitle?: string
 *   graphKey?: string (for localStorage persistence)
 *   onNodeClick?: (id) => void
 */

// Cytoscape can't resolve CSS custom properties — hex mirrors per theme.
// Keep in sync with :root / .dark vars in index.css.
const CY_DARK = {
  background: '#0b0b14', surface: '#0e0e19', overlay: '#161625',
  textPrimary: '#f1f5f9', textSecondary: '#94a3b8',
  textTertiary: '#64748b', textMuted: '#475569', accent: '#FBBF24',
};
const CY_LIGHT = {
  background: '#FFFFFF', surface: '#FAFAFA', overlay: '#F5F5F5',
  textPrimary: '#0a0a0a', textSecondary: '#404040',
  textTertiary: '#737373', textMuted: '#a3a3a3', accent: '#FBBF24',
};

function buildDefaultStyle(c) {
  return [
    {
      selector: 'node',
      style: {
        'label': 'data(label)', 'text-valign': 'center', 'text-halign': 'center',
        'font-size': '11px', 'font-weight': 600,
        'font-family': 'ui-monospace, SFMono-Regular, "SF Mono", Menlo, monospace',
        'color': c.textPrimary, 'text-wrap': 'wrap', 'text-max-width': '110px',
        'background-color': c.overlay, 'border-width': 1,
        'border-color': 'data(color)', 'border-opacity': 0.5,
        'width': 140, 'height': 52, 'shape': 'round-rectangle',
        'text-outline-width': 0, 'overlay-padding': 4, 'overlay-opacity': 0,
      },
    },
    { selector: 'node[shape = "diamond"]', style: { 'shape': 'diamond', 'width': 160, 'height': 80, 'font-size': '10px' } },
    { selector: 'node:selected', style: { 'border-width': 2, 'border-opacity': 1, 'border-color': c.accent } },
    {
      selector: 'edge',
      style: {
        'width': 1, 'line-color': c.textMuted, 'target-arrow-color': c.textMuted,
        'target-arrow-shape': 'triangle', 'curve-style': 'bezier', 'arrow-scale': 0.7, 'opacity': 0.5,
      },
    },
    {
      selector: 'edge[label]',
      style: {
        'label': 'data(label)', 'font-size': '10px',
        'font-family': 'ui-monospace, SFMono-Regular, "SF Mono", Menlo, monospace',
        'color': c.textSecondary, 'text-rotation': 'autorotate', 'text-margin-y': -8,
        'text-outline-width': 3, 'text-outline-color': c.background,
      },
    },
    { selector: 'edge[color]', style: { 'line-color': 'data(color)', 'target-arrow-color': 'data(color)' } },
    { selector: 'edge[lineStyle = "dashed"]', style: { 'line-style': 'dashed' } },
    { selector: 'edge[lineStyle = "dotted"]', style: { 'line-style': 'dotted' } },
    {
      selector: ':parent',
      style: {
        'background-color': c.overlay, 'background-opacity': 0.3,
        'border-width': 1, 'border-color': 'data(color)', 'border-opacity': 0.3,
        'text-valign': 'top', 'text-halign': 'center', 'font-size': '10px',
        'color': c.textTertiary, 'padding': '16px',
      },
    },
  ];
}

// Hook: observe .dark class on <html> to detect theme changes
function useTheme() {
  const [isDark, setIsDark] = useState(() => document.documentElement.classList.contains('dark'));
  useEffect(() => {
    const obs = new MutationObserver(() => setIsDark(document.documentElement.classList.contains('dark')));
    obs.observe(document.documentElement, { attributes: true, attributeFilter: ['class'] });
    return () => obs.disconnect();
  }, []);
  return isDark;
}

const LAYOUTS = {
  'dagre-tb': { name: 'dagre', rankDir: 'LR', rankSep: 80, nodeSep: 50, padding: 40 },
  'dagre-lr': { name: 'dagre', rankDir: 'TB', rankSep: 100, nodeSep: 40, padding: 40 },
  'circle': { name: 'circle', padding: 40 },
  'grid': { name: 'grid', padding: 40, rows: 3 },
  'concentric': { name: 'concentric', padding: 40, minNodeSpacing: 60 },
  'breadthfirst': { name: 'breadthfirst', padding: 40, spacingFactor: 1.2 },
};

const LAYOUT_LABELS = {
  'dagre-tb': 'Top \u2192 Down',
  'dagre-lr': 'Left \u2192 Right',
  'circle': 'Circle',
  'grid': 'Grid',
  'concentric': 'Concentric',
  'breadthfirst': 'Breadthfirst',
};

function toElements(nodes, edges) {
  const elements = [];
  for (const n of nodes) {
    elements.push({
      data: {
        id: n.id,
        label: n.label,
        sublabel: n.sublabel || undefined,
        color: n.color || CY.textMuted,
        parent: n.parent || undefined,
        shape: n.shape || undefined,
      },
      ...(n.position ? { position: n.position } : {}),
    });
  }
  for (const e of edges) {
    elements.push({
      data: {
        id: e.id || `${e.from}-${e.to}-${e.label || ''}`,
        source: e.from,
        target: e.to,
        label: e.label || undefined,
        color: e.color || undefined,
        lineStyle: e.style || 'solid',
        edgeType: e.type || undefined,
      },
    });
  }
  return elements;
}

const GRAPH_STATE_PREFIX = 'compose:graph:';

function loadGraphState(key) {
  try {
    const raw = localStorage.getItem(GRAPH_STATE_PREFIX + key);
    return raw ? JSON.parse(raw) : null;
  } catch { return null; }
}

function saveGraphState(key, state) {
  try { localStorage.setItem(GRAPH_STATE_PREFIX + key, JSON.stringify(state)); }
  catch { /* quota */ }
}

const EDGE_LEGEND = [
  { style: 'solid', label: 'Structural / hard', dash: null },
  { style: 'dashed', label: 'Informational / weak', dash: '4,3' },
  { style: 'dotted', label: 'Soft dependency', dash: '1.5,3' },
];

// --- Shared small components ---

function ToolbarButton({ onClick, active, children, title }) {
  return (
    <button
      onClick={onClick}
      title={title}
      className="text-xs rounded cursor-pointer transition-colors font-semibold"
      style={{
        padding: 'var(--spacing-xs) var(--spacing-sm)',
        borderRadius: 'var(--button-border-radius)',
        border: '1px solid',
        borderColor: active ? 'var(--accent-glow)' : 'var(--border-standard)',
        background: active ? 'var(--accent-glow)' : 'var(--color-surface-overlay)',
        color: active ? 'var(--color-accent)' : 'var(--color-text-secondary)',
      }}
    >
      {children}
    </button>
  );
}

function ViewTab({ mode, active, onClick }) {
  return (
    <button
      onClick={onClick}
      className="text-xs rounded cursor-pointer capitalize transition-colors font-semibold"
      style={{
        padding: 'var(--spacing-xs) var(--spacing-sm)',
        borderRadius: 'var(--button-border-radius)',
        border: '1px solid',
        borderColor: active ? 'var(--accent-glow)' : 'var(--border-standard)',
        background: active ? 'var(--accent-glow)' : 'var(--color-surface-overlay)',
        color: active ? 'var(--color-accent)' : 'var(--color-text-muted)',
      }}
    >
      {mode}
    </button>
  );
}

function Separator() {
  return <div className="w-px h-4 mx-0.5" style={{ background: 'var(--border-standard)' }} />;
}

function EdgeRow({ arrow, label, edgeStyle, color, targetLabel, targetColor, suffix }) {
  return (
    <div
      className="flex items-center gap-2 text-xs"
      style={{ padding: 'var(--spacing-xs) var(--spacing-sm)', color: 'var(--color-text-secondary)' }}
    >
      <span style={{ color: 'var(--color-text-muted)' }}>{arrow}</span>
      <span style={{
        color: color || 'var(--color-text-secondary)',
        fontStyle: edgeStyle === 'dashed' ? 'italic' : 'normal',
      }}>
        {label || 'connects'}
      </span>
      {targetLabel ? (
        <>
          <span style={{ color: 'var(--color-text-muted)' }}>&rarr;</span>
          <span className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-sm shrink-0" style={{ background: targetColor || 'var(--color-text-muted)' }} />
            <span style={{ color: 'var(--color-text-primary)' }}>{targetLabel}</span>
          </span>
        </>
      ) : suffix ? (
        <span style={{ color: 'var(--color-text-muted)' }}>{suffix}</span>
      ) : null}
      {edgeStyle && edgeStyle !== 'solid' && (
        <span className="text-[10px]" style={{ color: 'var(--color-text-muted)' }}>({edgeStyle})</span>
      )}
    </div>
  );
}

// --- Tree View ---

function TreeView({ nodes, edges, graphKey }) {
  const [collapsed, setCollapsed] = useState(() => {
    try {
      const raw = localStorage.getItem(GRAPH_STATE_PREFIX + graphKey + ':tree-collapsed');
      return raw ? new Set(JSON.parse(raw)) : new Set();
    } catch { return new Set(); }
  });

  useEffect(() => {
    try { localStorage.setItem(GRAPH_STATE_PREFIX + graphKey + ':tree-collapsed', JSON.stringify([...collapsed])); }
    catch { /* quota */ }
  }, [collapsed, graphKey]);

  const nodeMap = useMemo(() => {
    const m = {};
    for (const n of nodes) m[n.id] = n;
    return m;
  }, [nodes]);

  const adj = useMemo(() => {
    const out = {};
    const inc = {};
    for (const n of nodes) { out[n.id] = []; inc[n.id] = []; }
    for (const e of edges) { out[e.from]?.push(e); inc[e.to]?.push(e); }
    return { out, inc };
  }, [nodes, edges]);

  const toggle = (id) => setCollapsed(prev => {
    const next = new Set(prev);
    if (next.has(id)) next.delete(id); else next.add(id);
    return next;
  });

  return (
    <div
      className="w-full h-full overflow-y-auto"
      style={{ background: 'var(--color-background)', padding: 'var(--card-padding)' }}
    >
      {/* Controls */}
      <div className="flex items-center mb-4" style={{ gap: 'var(--spacing-sm)' }}>
        <ToolbarButton onClick={() => setCollapsed(new Set())}>Expand all</ToolbarButton>
        <ToolbarButton onClick={() => setCollapsed(new Set(nodes.map(n => n.id)))}>Collapse all</ToolbarButton>
        <span className="text-xs ml-auto" style={{ color: 'var(--color-text-tertiary)' }}>
          {nodes.length} entities &middot; {edges.length} relations
        </span>
      </div>

      {nodes.map(node => {
        const isCollapsed = collapsed.has(node.id);
        const outgoing = adj.out[node.id] || [];
        const incoming = adj.inc[node.id] || [];
        const selfEdges = outgoing.filter(e => e.from === e.to);
        const outNonSelf = outgoing.filter(e => e.from !== e.to);
        const incNonSelf = incoming.filter(e => e.from !== e.to);
        const totalRelations = outNonSelf.length + incNonSelf.length + selfEdges.length;

        return (
          <div key={node.id} className="mb-0.5">
            <button
              onClick={() => toggle(node.id)}
              className="flex items-center w-full text-left bg-transparent border-none cursor-pointer rounded-md transition-colors hover:bg-[var(--color-surface-overlay)]"
              style={{ gap: 'var(--spacing-sm)', padding: 'var(--spacing-sm)' }}
            >
              <span
                className="text-xs w-4 text-center inline-block transition-transform"
                style={{
                  color: 'var(--color-text-tertiary)',
                  transform: isCollapsed ? 'rotate(-90deg)' : 'rotate(0deg)',
                }}
              >
                ▼
              </span>
              <span
                className="w-3 h-3 shrink-0"
                style={{
                  borderRadius: node.shape === 'diamond' ? 0 : 3,
                  background: node.color,
                  transform: node.shape === 'diamond' ? 'rotate(45deg) scale(0.8)' : 'none',
                }}
              />
              <span className="text-sm font-semibold" style={{ color: 'var(--color-text-primary)' }}>
                {node.label}
              </span>
              {node.sublabel && (
                <span className="text-xs" style={{ color: 'var(--color-text-tertiary)' }}>
                  &mdash; {node.sublabel}
                </span>
              )}
              <span className="text-xs ml-auto" style={{ color: 'var(--color-text-muted)' }}>
                {totalRelations}
              </span>
            </button>

            {!isCollapsed && (
              <div style={{ paddingLeft: 'var(--spacing-xl)', paddingBottom: 'var(--spacing-xs)' }}>
                {outNonSelf.map((e, i) => (
                  <EdgeRow
                    key={`out-${i}`}
                    arrow="&rarr;"
                    label={e.label}
                    edgeStyle={e.style}
                    color={e.color}
                    targetLabel={nodeMap[e.to]?.label || e.to}
                    targetColor={nodeMap[e.to]?.color}
                  />
                ))}
                {selfEdges.map((e, i) => (
                  <EdgeRow key={`self-${i}`} arrow="↻" label={e.label} edgeStyle={e.style} color={e.color} suffix="(self)" />
                ))}
                {incNonSelf.map((e, i) => (
                  <div
                    key={`in-${i}`}
                    className="flex items-center gap-2 text-xs"
                    style={{ padding: 'var(--spacing-xs) var(--spacing-sm)', color: 'var(--color-text-secondary)' }}
                  >
                    <span className="flex items-center gap-1.5">
                      <span className="w-2 h-2 rounded-sm shrink-0" style={{ background: nodeMap[e.from]?.color || 'var(--color-text-muted)' }} />
                      <span style={{ color: 'var(--color-text-primary)' }}>
                        {nodeMap[e.from]?.label || e.from}
                      </span>
                    </span>
                    <span style={{ color: 'var(--color-text-muted)' }}>&rarr;</span>
                    <span style={{
                      color: e.color || 'var(--color-text-secondary)',
                      fontStyle: e.style === 'dashed' ? 'italic' : 'normal',
                    }}>
                      {e.label || 'connects'}
                    </span>
                    <span style={{ color: 'var(--color-text-muted)' }}>&rarr; this</span>
                    {e.style && e.style !== 'solid' && (
                      <span className="text-[10px]" style={{ color: 'var(--color-text-muted)' }}>({e.style})</span>
                    )}
                  </div>
                ))}
                {totalRelations === 0 && (
                  <div className="text-xs italic" style={{ padding: 'var(--spacing-xs) var(--spacing-sm)', color: 'var(--color-text-muted)' }}>
                    no relations
                  </div>
                )}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

// --- Main component ---

export default function GraphRenderer({
  elements: elementsProp,
  nodes: nodesProp,
  edges: edgesProp,
  layout: layoutProp,
  style: styleProp,
  title,
  subtitle,
  graphKey = 'default',
  onNodeClick,
}) {
  const containerRef = useRef(null);
  const cyRef = useRef(null);
  const [tooltip, setTooltip] = useState(null);
  const isDark = useTheme();
  const cyColors = isDark ? CY_DARK : CY_LIGHT;

  const saved = useMemo(() => loadGraphState(graphKey), [graphKey]);
  const [layoutKey, setLayoutKey] = useState(saved?.layoutKey || 'dagre-tb');
  const [showEdgeLabels, setShowEdgeLabels] = useState(saved?.showEdgeLabels ?? true);
  const [hiddenNodes, setHiddenNodes] = useState(() => new Set(saved?.hiddenNodes || []));
  const [showLegend, setShowLegend] = useState(saved?.showLegend ?? true);
  const [viewMode, setViewMode] = useState(saved?.viewMode || 'graph');

  useEffect(() => {
    saveGraphState(graphKey, { layoutKey, showEdgeLabels, hiddenNodes: [...hiddenNodes], showLegend, viewMode });
  }, [graphKey, layoutKey, showEdgeLabels, hiddenNodes, showLegend, viewMode]);

  const elements = elementsProp || (nodesProp && edgesProp ? toElements(nodesProp, edgesProp) : []);
  const graphStyle = useMemo(() => styleProp || buildDefaultStyle(cyColors), [styleProp, isDark]);
  const activeLayout = layoutProp || LAYOUTS[layoutKey];

  const nodeList = useMemo(() => {
    return elements.filter(el => !el.data.source).map(el => ({ id: el.data.id, label: el.data.label, color: el.data.color }));
  }, [JSON.stringify(elements)]);

  const visibleElements = useMemo(() => {
    if (hiddenNodes.size === 0) return elements;
    return elements.filter(el => {
      if (el.data.source) return !hiddenNodes.has(el.data.source) && !hiddenNodes.has(el.data.target);
      return !hiddenNodes.has(el.data.id);
    });
  }, [elements, hiddenNodes]);

  // Cytoscape lifecycle
  useEffect(() => {
    if (!containerRef.current) return;
    const cy = cytoscape({
      container: containerRef.current,
      elements: visibleElements,
      style: graphStyle,
      layout: activeLayout,
      minZoom: 0.2,
      maxZoom: 4,
      wheelSensitivity: 0.3,
      boxSelectionEnabled: false,
    });
    cyRef.current = cy;

    cy.on('mouseover', 'node', (evt) => {
      const node = evt.target;
      node.style('border-width', 2);
      node.style('border-opacity', 1);
      const pos = node.renderedPosition();
      setTooltip({
        x: pos.x,
        y: pos.y - (node.renderedHeight() / 2) - 12,
        label: node.data('label'),
        sublabel: node.data('sublabel'),
        id: node.id(),
        color: node.data('color'),
      });
    });
    cy.on('mouseout', 'node', (evt) => {
      evt.target.style('border-width', 1);
      evt.target.style('border-opacity', 0.5);
      setTooltip(null);
    });
    if (onNodeClick) cy.on('tap', 'node', (evt) => onNodeClick(evt.target.id()));
    cy.on('layoutstop', () => cy.fit(undefined, 40));

    return () => { cy.destroy(); cyRef.current = null; };
  }, [JSON.stringify(visibleElements), JSON.stringify(activeLayout), isDark, viewMode]);

  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;
    cy.edges().forEach(edge => {
      if (edge.data('label')) edge.style('label', showEdgeLabels ? edge.data('label') : '');
    });
  }, [showEdgeLabels]);

  const handleFit = useCallback(() => cyRef.current?.fit(undefined, 40), []);
  const handleZoomIn = useCallback(() => {
    const cy = cyRef.current;
    if (cy) cy.zoom({ level: cy.zoom() * 1.3, renderedPosition: { x: cy.width() / 2, y: cy.height() / 2 } });
  }, []);
  const handleZoomOut = useCallback(() => {
    const cy = cyRef.current;
    if (cy) cy.zoom({ level: cy.zoom() / 1.3, renderedPosition: { x: cy.width() / 2, y: cy.height() / 2 } });
  }, []);

  const toggleNode = useCallback((nodeId) => {
    setHiddenNodes(prev => {
      const next = new Set(prev);
      if (next.has(nodeId)) next.delete(nodeId); else next.add(nodeId);
      return next;
    });
  }, []);
  const showAll = useCallback(() => setHiddenNodes(new Set()), []);

  // --- Tree view ---
  if (viewMode === 'tree') {
    return (
      <div className="w-full h-full flex flex-col" style={{ background: 'var(--color-background)' }}>
        <div
          className="flex items-center justify-between shrink-0"
          style={{ padding: 'var(--spacing-sm) var(--spacing-md)', borderBottom: '1px solid var(--border-standard)' }}
        >
          <div className="flex items-center" style={{ gap: 'var(--spacing-sm)' }}>
            {title && <span className="text-sm font-semibold" style={{ color: 'var(--color-text-primary)' }}>{title}</span>}
            {subtitle && <span className="text-xs" style={{ color: 'var(--color-text-tertiary)' }}>{subtitle}</span>}
          </div>
          <div className="flex" style={{ gap: 'var(--spacing-xs)' }}>
            <ViewTab mode="graph" active={viewMode === 'graph'} onClick={() => setViewMode('graph')} />
            <ViewTab mode="tree" active={viewMode === 'tree'} onClick={() => setViewMode('tree')} />
          </div>
        </div>
        <div className="flex-1 min-h-0">
          <TreeView nodes={nodesProp || []} edges={edgesProp || []} graphKey={graphKey} />
        </div>
      </div>
    );
  }

  // --- Graph view ---
  return (
    <div className="w-full h-full relative" style={{ background: 'var(--color-background)' }}>
      {/* Header */}
      {(title || subtitle) && (
        <div
          className="absolute top-0 left-0 right-0 z-[2] pointer-events-none"
          style={{
            padding: 'var(--spacing-sm) var(--spacing-md)',
            background: 'linear-gradient(to bottom, var(--color-background) 0%, transparent 100%)',
          }}
        >
          {title && <div className="text-sm font-semibold" style={{ color: 'var(--color-text-primary)' }}>{title}</div>}
          {subtitle && <div className="text-[10px] mt-0.5" style={{ color: 'var(--color-text-tertiary)' }}>{subtitle}</div>}
        </div>
      )}

      {/* Controls toolbar */}
      <div className="absolute top-2 right-3 z-[2] flex items-center" style={{ gap: 'var(--spacing-xs)' }}>
        <select
          value={layoutKey}
          onChange={(e) => setLayoutKey(e.target.value)}
          className="text-xs rounded cursor-pointer appearance-none"
          style={{
            padding: 'var(--spacing-xs) var(--spacing-sm)',
            borderRadius: 'var(--button-border-radius)',
            background: 'var(--color-surface-overlay)',
            border: '1px solid var(--border-standard)',
            color: 'var(--color-text-secondary)',
          }}
          title="Graph layout"
        >
          {Object.entries(LAYOUT_LABELS).map(([key, label]) => (
            <option key={key} value={key} style={{ background: 'var(--color-surface-overlay)', color: 'var(--color-text-primary)' }}>
              {label}
            </option>
          ))}
        </select>

        <Separator />
        <ToolbarButton onClick={handleZoomOut} title="Zoom out">&minus;</ToolbarButton>
        <ToolbarButton onClick={handleFit} title="Fit to view">Fit</ToolbarButton>
        <ToolbarButton onClick={handleZoomIn} title="Zoom in">+</ToolbarButton>
        <Separator />
        <ToolbarButton onClick={() => setShowLegend(!showLegend)} active={showLegend} title={showLegend ? 'Hide legend' : 'Show legend'}>
          Legend
        </ToolbarButton>
        <Separator />
        <ViewTab mode="graph" active={viewMode === 'graph'} onClick={() => setViewMode('graph')} />
        <ViewTab mode="tree" active={viewMode === 'tree'} onClick={() => setViewMode('tree')} />
      </div>

      {/* Legend panel */}
      {showLegend && (
        <div
          className="absolute bottom-3 left-3 z-[2]"
          style={{
            background: 'var(--color-surface)',
            border: '1px solid var(--border-standard)',
            borderRadius: 'var(--card-border-radius)',
            padding: 'var(--spacing-sm) var(--spacing-md)',
            boxShadow: 'var(--card-shadow)',
            minWidth: 150,
            maxWidth: 210,
          }}
        >
          <div className="flex justify-between items-center mb-1.5">
            <span className="text-[10px] font-semibold uppercase tracking-wider" style={{ color: 'var(--color-text-tertiary)' }}>
              Entities
            </span>
            {hiddenNodes.size > 0 && (
              <button
                onClick={showAll}
                className="text-[10px] bg-transparent border-none cursor-pointer p-0"
                style={{ color: 'var(--color-accent)' }}
              >
                Show all
              </button>
            )}
          </div>
          <div className="flex flex-col gap-1">
            {nodeList.map(n => {
              const isHidden = hiddenNodes.has(n.id);
              return (
                <button
                  key={n.id}
                  onClick={() => toggleNode(n.id)}
                  className="flex items-center gap-1.5 bg-transparent border-none py-0.5 cursor-pointer transition-opacity"
                  style={{ opacity: isHidden ? 0.35 : 1 }}
                  title={isHidden ? `Show ${n.label}` : `Hide ${n.label}`}
                >
                  <span
                    className="w-2 h-2 rounded-sm shrink-0 transition-colors"
                    style={{ background: isHidden ? 'transparent' : n.color, border: `1.5px solid ${n.color}` }}
                  />
                  <span
                    className="text-xs"
                    style={{
                      color: isHidden ? 'var(--color-text-muted)' : 'var(--color-text-secondary)',
                      textDecoration: isHidden ? 'line-through' : 'none',
                    }}
                  >
                    {n.label}
                  </span>
                </button>
              );
            })}
          </div>

          <div className="flex justify-between items-center mt-2.5 mb-1.5">
            <span className="text-[10px] font-semibold uppercase tracking-wider" style={{ color: 'var(--color-text-tertiary)' }}>
              Edges
            </span>
            <button
              onClick={() => setShowEdgeLabels(!showEdgeLabels)}
              className="text-[10px] bg-transparent border-none cursor-pointer p-0"
              style={{ color: showEdgeLabels ? 'var(--color-accent)' : 'var(--color-text-muted)' }}
            >
              {showEdgeLabels ? 'Hide labels' : 'Show labels'}
            </button>
          </div>
          <div className="flex flex-col gap-1">
            {EDGE_LEGEND.map(e => (
              <div key={e.style} className="flex items-center gap-1.5">
                <svg width="20" height="6" className="shrink-0">
                  <line x1="0" y1="3" x2="20" y2="3" stroke="var(--color-text-tertiary)" strokeWidth="1.5" strokeDasharray={e.dash || 'none'} />
                </svg>
                <span className="text-[10px]" style={{ color: 'var(--color-text-muted)' }}>{e.label}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Tooltip */}
      {tooltip && (
        <div
          className="absolute z-10 text-center pointer-events-none backdrop-blur-sm"
          style={{
            left: tooltip.x,
            top: tooltip.y,
            transform: 'translate(-50%, -100%)',
            background: 'var(--color-surface-overlay)',
            border: '1px solid var(--border-standard)',
            borderRadius: 'var(--card-border-radius)',
            padding: 'var(--spacing-xs) var(--spacing-sm)',
            boxShadow: 'var(--card-shadow)',
            minWidth: 110,
            maxWidth: 200,
          }}
        >
          <div className="text-sm font-semibold" style={{ color: tooltip.color || 'var(--color-text-primary)' }}>
            {tooltip.label}
          </div>
          {tooltip.sublabel && (
            <div className="text-xs mt-0.5" style={{ color: 'var(--color-text-secondary)' }}>{tooltip.sublabel}</div>
          )}
          <div className="text-[10px] mt-1 font-mono" style={{ color: 'var(--color-text-muted)' }}>{tooltip.id}</div>
        </div>
      )}

      <div ref={containerRef} className="w-full h-full" />
    </div>
  );
}

// Cytoscape doesn't survive Vite HMR — force full remount on edit
if (import.meta.hot) import.meta.hot.accept();
