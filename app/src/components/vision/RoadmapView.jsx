import React, { useState, useMemo, useEffect, useCallback } from 'react';
import { ChevronRight, ChevronDown } from 'lucide-react';
import { PHASE_LABELS, TYPE_COLORS } from './constants.js';
import ItemRow from './ItemRow.jsx';
import { withComposeToken } from '@/lib/compose-api.js';

/**
 * Canonical phase order for grouping children under features.
 * This is the full lifecycle sequence. Phases without children are omitted from display.
 */
const PHASE_SEQUENCE = [
  'vision', 'specification', 'planning', 'implementation', 'verification', 'release',
];

const PHASE_DISPLAY_LABELS = {
  ...PHASE_LABELS,
};

/** Status sort order: in_progress first, then planned, then complete */
const STATUS_SORT_ORDER = {
  in_progress: 0,
  review: 1,
  ready: 2,
  planned: 3,
  blocked: 4,
  complete: 5,
  approved: 5,
  parked: 6,
  killed: 7,
};

function getStatusOrder(status) {
  return STATUS_SORT_ORDER[status] ?? 3;
}

/** Status color for phase dot */
function phaseStatusColor(status) {
  switch (status) {
    case 'complete': return '#22c55e';
    case 'in_progress': case 'review': case 'ready': return '#fbbf24';
    default: return 'var(--color-text-tertiary)';
  }
}

/** Compute rolled-up status for a set of items */
function rollupStatus(items) {
  if (items.length === 0) return 'planned';
  const complete = items.filter(i => i.status === 'complete' || i.status === 'approved').length;
  if (complete === items.length) return 'complete';
  const active = items.some(i =>
    i.status === 'in_progress' || i.status === 'review' || i.status === 'ready'
  );
  if (active || complete > 0) return 'in_progress';
  return 'planned';
}

/** Format status text */
function formatStatus(status) {
  if (!status) return 'planned';
  return status.replace(/_/g, ' ');
}

/**
 * Parse breadcrumb path from URL hash.
 * Hash format: #roadmap/id1/id2/...
 * Returns array of id strings.
 */
function parseBreadcrumbFromHash() {
  const hash = window.location.hash;
  if (!hash || !hash.startsWith('#roadmap')) return [];
  const parts = hash.replace('#roadmap', '').split('/').filter(Boolean);
  return parts;
}

/**
 * Write breadcrumb path to URL hash.
 * @param {Array} breadcrumb
 * @param {boolean} push - If true, use pushState (creates history entry). Otherwise replaceState.
 */
function writeBreadcrumbToHash(breadcrumb, push = false) {
  const newHash = breadcrumb.length === 0
    ? '#roadmap'
    : `#roadmap/${breadcrumb.map(b => b.id).join('/')}`;
  if (window.location.hash === newHash) return;
  if (push) {
    window.history.pushState(null, '', newHash);
  } else {
    window.history.replaceState(null, '', newHash);
  }
}

/**
 * Find all children of an item via `implements`/`supports` connections or `parentId` field.
 */
const CHILD_EDGE_TYPES = new Set(['implements', 'supports', 'contradicts']);

function getChildren(parentId, items, connections) {
  const childIds = new Set();

  // Children via parentId field
  for (const item of items) {
    if (item.parentId === parentId) {
      childIds.add(item.id);
    }
  }

  // Children via implements/supports edges: child → parent
  for (const conn of connections) {
    if (conn.toId === parentId && CHILD_EDGE_TYPES.has(conn.type)) {
      childIds.add(conn.fromId);
    }
  }

  const itemsById = new Map(items.map(i => [i.id, i]));
  return [...childIds].map(id => itemsById.get(id)).filter(Boolean);
}

/**
 * Count complete descendants (recursive, with cycle guard).
 */
function countDescendants(parentId, items, connections, visited = new Set()) {
  if (visited.has(parentId)) return { total: 0, done: 0 };
  visited.add(parentId);

  const children = getChildren(parentId, items, connections);
  let total = children.length;
  let done = children.filter(c => c.status === 'complete' || c.status === 'approved').length;

  for (const child of children) {
    const sub = countDescendants(child.id, items, connections, visited);
    total += sub.total;
    done += sub.done;
  }

  return { total, done };
}

/**
 * RoadmapView - Hierarchical view for the Vision Tracker.
 *
 * Initiatives expand inline to show phase groups. Phase groups expand inline
 * to show ItemRow children. Drill-in (breadcrumb push) only happens when
 * clicking a linked item inside an expanded ItemRow body.
 *
 * Props:
 *   items       - All items from the vision store
 *   connections - All connections from the vision store
 *   onAction    - Callback for item actions: (itemId, action)
 */
function RoadmapView({ items, connections, selectedPhase, onAction }) {
  // Read the saved current item ID from hash or sessionStorage
  const getSavedItemId = () => {
    const hashIds = parseBreadcrumbFromHash();
    if (hashIds.length > 0) return hashIds[hashIds.length - 1]; // last ID is the current item
    const stored = sessionStorage.getItem('vision-currentItemId');
    return stored || null;
  };

  const [currentItemId, setCurrentItemId] = useState(getSavedItemId);

  // Derive breadcrumb path from hierarchy (Explorer-style: always root → ... → current)
  const buildPathTo = useCallback((targetId) => {
    if (!targetId) return [];
    const itemMap = new Map(items.map(i => [i.id, i]));
    if (!itemMap.has(targetId)) return [];
    const getParentId = (id) => {
      const i = itemMap.get(id);
      if (i?.parentId) return i.parentId;
      for (const conn of connections) {
        if (conn.fromId === id && CHILD_EDGE_TYPES.has(conn.type)) return conn.toId;
      }
      return null;
    };

    const path = [];
    let walkId = targetId;
    const visited = new Set();
    while (walkId && !visited.has(walkId)) {
      visited.add(walkId);
      const item = itemMap.get(walkId);
      if (item) path.unshift({ id: item.id, title: item.title });
      walkId = getParentId(walkId);
    }
    return path;
  }, [items, connections]);

  const breadcrumb = useMemo(() => buildPathTo(currentItemId), [currentItemId, buildPathTo]);

  // Persist current item ID to sessionStorage + URL hash
  useEffect(() => {
    if (currentItemId === null && items.length === 0) return; // don't overwrite before items load
    const hashPath = breadcrumb.length === 0 ? [] : breadcrumb;
    writeBreadcrumbToHash(hashPath);
    if (currentItemId) {
      sessionStorage.setItem('vision-currentItemId', currentItemId);
    } else {
      sessionStorage.removeItem('vision-currentItemId');
    }
  }, [currentItemId, breadcrumb, items.length]);

  // Restore from hash on items load
  useEffect(() => {
    if (items.length === 0 || currentItemId) return;
    const savedId = getSavedItemId();
    if (savedId && items.find(i => i.id === savedId)) {
      setCurrentItemId(savedId);
    }
  }, [items]);

  // Browser back/forward
  useEffect(() => {
    const handlePopState = () => {
      const ids = parseBreadcrumbFromHash();
      setCurrentItemId(ids.length > 0 ? ids[ids.length - 1] : null);
    };
    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  }, []);

  const handleDrillIn = useCallback((item) => {
    setCurrentItemId(item.id);
    // Push history so browser back works
    const next = buildPathTo(item.id);
    if (next.length === 0) next.push({ id: item.id, title: item.title });
    writeBreadcrumbToHash(next, true);
  }, [buildPathTo]);

  const handleBreadcrumbClick = useCallback((index) => {
    if (index < 0) {
      setCurrentItemId(null);
      writeBreadcrumbToHash([], true);
    } else {
      const targetId = breadcrumb[index]?.id || null;
      setCurrentItemId(targetId);
      writeBreadcrumbToHash(breadcrumb.slice(0, index + 1), true);
    }
  }, [breadcrumb]);

  const currentItem = currentItemId ? items.find(i => i.id === currentItemId) : null;
  const isRoot = !currentItemId;

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0, overflow: 'auto' }}>
      {/* Breadcrumb bar — always visible */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: '8px', fontSize: '14px',
        margin: '12px 16px 0', padding: '10px 16px',
        background: 'var(--color-surface)', borderRadius: '8px',
        border: '1px solid var(--border-standard)',
      }}>
        {breadcrumb.length === 0 ? (
          <span style={{ color: 'var(--color-text-primary)', fontWeight: 500 }}>Roadmap</span>
        ) : (
          <>
            <a
              onClick={() => handleBreadcrumbClick(-1)}
              style={{ color: '#818cf8', cursor: 'pointer', textDecoration: 'none' }}
            >
              Roadmap
            </a>
            {breadcrumb.map((crumb, i) => (
              <React.Fragment key={crumb.id}>
                <span style={{ color: 'var(--color-text-muted)' }}>&rsaquo;</span>
                {i < breadcrumb.length - 1 ? (
                  <a
                    onClick={() => handleBreadcrumbClick(i)}
                    style={{ color: '#818cf8', cursor: 'pointer', textDecoration: 'none' }}
                  >
                    {crumb.title}
                  </a>
                ) : (
                  <span style={{ color: 'var(--color-text-primary)', fontWeight: 500 }}>{crumb.title}</span>
                )}
              </React.Fragment>
            ))}
          </>
        )}
      </div>

      {/* Content area */}
      <div style={{ flex: 1, overflow: 'auto', padding: '16px' }}>
        {isRoot && (
          <RoadmapRoot
            items={items}
            connections={connections}
            selectedPhase={selectedPhase}
            onDrillIn={handleDrillIn}
            onAction={onAction}
          />
        )}

        {!isRoot && currentItem && (
          <ItemFocusView
            item={currentItem}
            items={items}
            connections={connections}
            onDrillIn={handleDrillIn}
            onAction={onAction}
          />
        )}

        {!isRoot && !currentItem && (
          <StaleHashRedirect setCurrentItemId={setCurrentItemId} />
        )}
      </div>
    </div>
  );
}

export default React.memo(RoadmapView);

/**
 * Auto-reset to root when breadcrumb points to a deleted/missing item.
 */
function StaleHashRedirect({ setCurrentItemId }) {
  useEffect(() => {
    writeBreadcrumbToHash([], false);
    setCurrentItemId(null);
  }, [setCurrentItemId]);
  return null;
}

/**
 * Root level: show all initiatives as expandable rows with progress.
 */
function RoadmapRoot({ items, connections, selectedPhase, onDrillIn, onAction }) {
  const initiatives = useMemo(() => {
    let feats = items.filter(i => i.type === 'feature');
    // When phase filter is active, only show features that have children in that phase
    if (selectedPhase) {
      feats = feats.filter(feat => {
        const children = getChildren(feat.id, items, connections);
        return children.some(c => c.phase === selectedPhase);
      });
    }
    // Sort: in_progress first, then planned, then complete
    feats.sort((a, b) => getStatusOrder(a.status) - getStatusOrder(b.status));
    return feats;
  }, [items, connections, selectedPhase]);

  if (initiatives.length === 0) {
    return (
      <div style={{ color: 'var(--color-text-tertiary)', fontSize: '12px', textAlign: 'center', padding: '24px' }}>
        No features found. Create items with type &quot;feature&quot; to see them here.
      </div>
    );
  }

  return (
    <div>
      {initiatives.map(init => (
        <InitiativeRow
          key={init.id}
          item={init}
          items={items}
          connections={connections}
          selectedPhase={selectedPhase}
          onDrillIn={onDrillIn}
          onAction={onAction}
        />
      ))}
    </div>
  );
}

/**
 * Initiative row with inline phase expansion.
 * Clicking the initiative header toggles phase groups.
 * Clicking a phase group toggles its children (ItemRows) inline.
 */
function InitiativeRow({ item, items, connections, selectedPhase, onDrillIn, onAction }) {
  const storageKey = `roadmap-init-${item.id}`;
  const [expanded, setExpanded] = useState(() => {
    const stored = sessionStorage.getItem(storageKey);
    return stored !== null ? stored === 'true' : false; // collapsed by default
  });
  const toggleExpanded = () => setExpanded(prev => {
    const next = !prev;
    sessionStorage.setItem(storageKey, String(next));
    return next;
  });

  const { total, done } = useMemo(
    () => countDescendants(item.id, items, connections),
    [item.id, items, connections]
  );

  const children = useMemo(
    () => getChildren(item.id, items, connections),
    [item.id, items, connections]
  );

  // Group children by phase
  const phaseGroups = useMemo(() => {
    const groups = new Map();
    for (const child of children) {
      const phase = child.phase || 'planning';
      if (!groups.has(phase)) groups.set(phase, []);
      groups.get(phase).push(child);
    }
    // Return in canonical order, only populated phases (filtered by selectedPhase if set)
    return PHASE_SEQUENCE
      .filter(p => groups.has(p) && (!selectedPhase || p === selectedPhase))
      .map(p => ({ phase: p, items: groups.get(p) }));
  }, [children, selectedPhase]);

  // Group children by status for structured summary
  const statusGroups = useMemo(() => {
    const doneItems = children.filter(c => c.status === 'complete' || c.status === 'approved');
    const activeItems = children.filter(c => c.status === 'in_progress' || c.status === 'review');
    const blockedItems = children.filter(c => c.status === 'blocked');
    const plannedItems = children.filter(c => c.status === 'planned' || c.status === 'ready' || c.status === 'parked');
    return { doneItems, activeItems, blockedItems, plannedItems };
  }, [children]);

  // On-demand AI insight (not status — the chips handle that)
  const [aiInsight, setAiInsight] = useState(item.summary || null);
  const [insightLoading, setInsightLoading] = useState(false);

  const generateInsight = useCallback(async () => {
    if (insightLoading || children.length === 0) return;
    setInsightLoading(true);
    try {
      const childLines = children.map(c => `- ${c.title} (${c.status}${c.description ? ': ' + c.description.slice(0, 80) : ''})`).join('\n');
      const prompt = [
        `You are a project advisor. For "${item.title}", identify 1-2 notable risks, dependencies, or insights that aren't obvious from status alone.`,
        `Don't restate what's done/active/planned. Focus on what someone should KNOW — bottlenecks, dependencies between items, decisions needed, or strategic observations.`,
        `Children:\n${childLines}`,
        `Respond in 1-2 short sentences. No bullet points. No status recaps.`,
      ].join('\n');
      const res = await fetch('http://localhost:3001/api/agent/spawn', {
        method: 'POST',
        headers: withComposeToken({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({ prompt }),
      });
      if (res.ok) {
        const data = await res.json();
        const poll = setInterval(async () => {
          try {
            const r = await fetch(`http://localhost:3001/api/agent/${data.agentId}`);
            if (!r.ok) return;
            const d = await r.json();
            if (d.status !== 'running') {
              clearInterval(poll);
              const insight = (d.output || '').trim().split('\n').pop()?.trim() || '';
              if (insight) {
                setAiInsight(insight);
                fetch(`http://localhost:3001/api/vision/items/${item.id}`, {
                  method: 'PATCH',
                  headers: { 'Content-Type': 'application/json' },
                  body: JSON.stringify({ summary: insight }),
                }).catch(() => {});
              }
              setInsightLoading(false);
            }
          } catch { clearInterval(poll); setInsightLoading(false); }
        }, 1500);
      } else { setInsightLoading(false); }
    } catch { setInsightLoading(false); }
  }, [item.id, item.title, children, insightLoading]);

  const pct = total > 0 ? Math.round((done / total) * 100) : 0;
  const statusColor = item.status === 'in_progress' || item.status === 'review'
    ? '#fbbf24' : item.status === 'complete' ? '#22c55e' : 'var(--color-text-tertiary)';
  const isComplete = item.status === 'complete';

  return (
    <div style={{
      border: '1px solid var(--border-standard)',
      borderRadius: '8px',
      marginBottom: '8px',
      background: 'var(--color-surface)',
      overflow: 'hidden',
      opacity: isComplete ? 0.6 : 1,
    }}>
      {/* Initiative header */}
      <div
        onClick={toggleExpanded}
        style={{
          display: 'flex', alignItems: 'center', gap: '10px',
          padding: '12px 16px', cursor: 'pointer', fontSize: '14px',
          background: expanded ? 'var(--color-surface-overlay)' : 'transparent',
          borderBottom: expanded ? '1px solid var(--border-soft)' : 'none',
        }}
        onMouseEnter={(e) => { if (!expanded) e.currentTarget.style.background = 'var(--primary-glow)'; }}
        onMouseLeave={(e) => { if (!expanded) e.currentTarget.style.background = expanded ? 'var(--color-surface-overlay)' : 'transparent'; }}
      >
        <span style={{
          width: '10px', height: '10px', borderRadius: '50%', flexShrink: 0,
          background: '#818cf8',
        }} />
        <span style={{ fontWeight: 600, flex: 1, color: 'var(--color-text-primary)' }}>{item.title}</span>

        {/* Progress count */}
        {total > 0 && (
          <span style={{ fontSize: '12px', color: 'var(--color-text-secondary)', marginLeft: 'auto' }}>
            {done}/{total} done
          </span>
        )}

        {/* Progress bar */}
        {total > 0 && (
          <div style={{
            width: '80px', height: '5px', borderRadius: '3px',
            background: 'var(--color-surface-overlay)', margin: '0 4px',
          }}>
            <div style={{
              width: `${pct}%`, height: '100%', borderRadius: '3px',
              background: '#818cf8',
            }} />
          </div>
        )}

        {/* Status badge */}
        <span style={{
          fontSize: '11px', padding: '2px 8px', borderRadius: '10px', flexShrink: 0,
          background: item.status === 'in_progress' ? 'rgba(251,191,36,0.15)'
            : item.status === 'complete' ? 'rgba(34,197,94,0.15)'
            : 'rgba(100,116,139,0.2)',
          color: statusColor,
        }}>
          {formatStatus(item.status)}
        </span>

        {/* Chevron */}
        {expanded
          ? <ChevronDown style={{ color: '#818cf8', flexShrink: 0, width: 16, height: 16 }} />
          : <ChevronRight style={{ color: 'var(--color-text-muted)', flexShrink: 0, width: 16, height: 16 }} />
        }
      </div>

      {/* Collapsed summary — chip rows by status */}
      {!expanded && (
        <div style={{
          padding: '6px 16px 10px 36px', display: 'flex', flexDirection: 'column', gap: '5px',
        }}>
          {[
            { items: statusGroups.doneItems, color: '#22c55e', label: 'done' },
            { items: statusGroups.activeItems, color: '#fbbf24', label: 'active' },
            { items: statusGroups.blockedItems, color: '#ef4444', label: 'blocked' },
            { items: statusGroups.plannedItems, color: '#64748b', label: 'planned' },
          ].filter(g => g.items.length > 0).map(g => (
            <div key={g.label} style={{ display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap' }}>
              <span style={{
                fontSize: '11px', fontWeight: 600, color: g.color, minWidth: '52px',
              }}>
                {g.items.length} {g.label}
              </span>
              {g.items.map(c => (
                <span key={c.id} onClick={(e) => { e.stopPropagation(); onDrillIn(c); }} style={{
                  display: 'inline-block', fontSize: '12px', cursor: 'pointer',
                  padding: '2px 10px', borderRadius: '4px',
                  background: `${g.color}15`, color: g.color, border: `1px solid ${g.color}30`,
                  transition: 'background 0.15s',
                }}
                onMouseEnter={(e) => { e.currentTarget.style.background = `${g.color}30`; }}
                onMouseLeave={(e) => { e.currentTarget.style.background = `${g.color}15`; }}
                >
                  {c.title}
                </span>
              ))}
            </div>
          ))}
          {/* AI insight — on demand */}
          {aiInsight && !insightLoading && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginTop: '2px' }}>
              <span style={{ color: 'var(--color-text-secondary)', fontStyle: 'italic', fontSize: '12px', flex: 1 }}>
                {aiInsight}
              </span>
              <button
                onClick={(e) => { e.stopPropagation(); generateInsight(); }}
                style={{
                  background: 'none', border: 'none', cursor: 'pointer', padding: '2px',
                  color: 'var(--color-text-muted)', opacity: 0.4, fontSize: '13px',
                }}
                onMouseEnter={(e) => { e.currentTarget.style.opacity = '1'; }}
                onMouseLeave={(e) => { e.currentTarget.style.opacity = '0.4'; }}
                title="Regenerate insight"
              >
                ↻
              </button>
            </div>
          )}
          {!aiInsight && !insightLoading && (
            <button
              onClick={(e) => { e.stopPropagation(); generateInsight(); }}
              style={{
                background: 'none', border: '1px solid var(--border-soft)', cursor: 'pointer',
                padding: '3px 10px', borderRadius: '4px', marginTop: '2px',
                color: 'var(--color-text-muted)', fontSize: '11px', opacity: 0.6,
              }}
              onMouseEnter={(e) => { e.currentTarget.style.opacity = '1'; }}
              onMouseLeave={(e) => { e.currentTarget.style.opacity = '0.6'; }}
            >
              Generate insight
            </button>
          )}
          {insightLoading && (
            <div style={{ color: 'var(--color-text-muted)', fontStyle: 'italic', fontSize: '12px', opacity: 0.5, marginTop: '2px' }}>
              Generating insight...
            </div>
          )}
        </div>
      )}

      {/* Expanded: phase rows as mini-accordions */}
      {expanded && (
        <div style={{ padding: '4px 12px 8px' }}>
          {phaseGroups.length === 0 ? (
            <div style={{ fontSize: '11px', color: 'var(--color-text-muted)', padding: '8px', textAlign: 'center' }}>
              No children yet
            </div>
          ) : (
            phaseGroups.map(({ phase, items: phaseItems }) => (
              <PhaseAccordion
                key={phase}
                phase={phase}
                phaseItems={phaseItems}
                allItems={items}
                connections={connections}
                onDrillIn={onDrillIn}
                onAction={onAction}
                parentId={item.id}
              />
            ))
          )}
        </div>
      )}
    </div>
  );
}

/**
 * PhaseAccordion - A phase row that expands inline to show ItemRow children.
 * Replaces the old drill-in phase behavior.
 */
function PhaseAccordion({ phase, phaseItems, allItems, connections, onDrillIn, onAction, parentId }) {
  const storageKey = `roadmap-phase-${parentId}-${phase}`;
  const [expanded, setExpanded] = useState(() => {
    const stored = sessionStorage.getItem(storageKey);
    return stored !== null ? stored === 'true' : true; // expanded by default
  });
  const toggleExpanded = () => setExpanded(prev => {
    const next = !prev;
    sessionStorage.setItem(storageKey, String(next));
    return next;
  });

  const phaseStatus = rollupStatus(phaseItems);
  const phaseColor = phaseStatusColor(phaseStatus);
  const isPhaseActive = phaseStatus === 'in_progress';

  // Filter to root items: exclude items that are children of another item in this group
  const rootItems = useMemo(() => {
    const groupIds = new Set(phaseItems.map(i => i.id));
    const childIds = new Set();
    for (const conn of connections) {
      if (CHILD_EDGE_TYPES.has(conn.type) && groupIds.has(conn.fromId) && groupIds.has(conn.toId)) {
        childIds.add(conn.fromId);
      }
    }
    for (const item of phaseItems) {
      if (item.parentId && groupIds.has(item.parentId)) {
        childIds.add(item.id);
      }
    }
    return phaseItems.filter(i => !childIds.has(i.id));
  }, [phaseItems, connections]);

  // Sort: in_progress first, then planned, then complete
  const sortedItems = useMemo(() => {
    return [...rootItems].sort((a, b) => getStatusOrder(a.status) - getStatusOrder(b.status));
  }, [rootItems]);

  return (
    <div style={{ marginBottom: '2px' }}>
      {/* Phase row header */}
      <div
        onClick={toggleExpanded}
        style={{
          display: 'flex', alignItems: 'center', gap: '8px',
          padding: '5px 8px', borderRadius: '4px', cursor: 'pointer',
          fontSize: '11px',
          border: isPhaseActive ? '1px solid rgba(251,191,36,0.2)' : '1px solid transparent',
          background: expanded
            ? 'rgba(129,140,248,0.06)'
            : isPhaseActive ? 'rgba(251,191,36,0.04)'
            : phaseStatus === 'complete' ? 'rgba(34,197,94,0.04)'
            : 'transparent',
        }}
        onMouseEnter={(e) => { e.currentTarget.style.background = 'rgba(129,140,248,0.06)'; }}
        onMouseLeave={(e) => {
          e.currentTarget.style.background = expanded
            ? 'rgba(129,140,248,0.06)'
            : isPhaseActive ? 'rgba(251,191,36,0.04)'
            : phaseStatus === 'complete' ? 'rgba(34,197,94,0.04)' : 'transparent';
        }}
      >
        <span style={{ color: phaseColor, fontSize: '9px' }}>&bull;</span>
        <span style={{
          color: isPhaseActive ? 'var(--color-text-primary)' : 'var(--color-text-secondary)',
          fontWeight: isPhaseActive ? 500 : 400,
        }}>
          {PHASE_DISPLAY_LABELS[phase] || phase}
        </span>
        <span style={{ fontSize: '10px', color: 'var(--color-text-tertiary)' }}>
          {rootItems.length} item{rootItems.length !== 1 ? 's' : ''}
        </span>
        <span style={{ fontSize: '10px', color: phaseColor, marginLeft: 'auto' }}>
          {formatStatus(phaseStatus)}
        </span>
        {expanded
          ? <ChevronDown style={{ color: '#818cf8', flexShrink: 0, width: 12, height: 12 }} />
          : <ChevronRight style={{ color: 'var(--color-text-muted)', flexShrink: 0, width: 12, height: 12 }} />
        }
      </div>

      {/* Expanded: ItemRow children indented beneath the phase row */}
      {expanded && (
        <div style={{ paddingLeft: '16px', paddingTop: '4px' }}>
          {sortedItems.map(child => (
            <ItemRow
              key={child.id}
              item={child}
              items={allItems}
              connections={connections}
              onDrillIn={onDrillIn}
              onAction={onAction}
            />
          ))}
        </div>
      )}
    </div>
  );
}

/**
 * Item focus view: shows a single item with full detail when drilled into via a linked item.
 */
function ItemFocusView({ item, items, connections, onDrillIn, onAction }) {
  return (
    <div>
      <ItemRow
        item={item}
        items={items}
        connections={connections}
        onDrillIn={onDrillIn}
        onAction={onAction}
        defaultExpanded
      />
    </div>
  );
}
