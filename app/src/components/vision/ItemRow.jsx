import React, { useState, useMemo, useContext, useCallback } from 'react';
import { ChevronRight, ChevronDown } from 'lucide-react';
import { TYPE_COLORS } from './constants.js';
import { VisionChangesContext } from './VisionTracker.jsx';
import { withForgeToken } from '@/lib/forge-api.js';

const STATUS_BG = {
  planned: 'rgba(100,116,139,0.2)',
  ready: 'rgba(129,140,248,0.15)',
  in_progress: 'rgba(251,191,36,0.15)',
  review: 'rgba(245,158,11,0.15)',
  complete: 'rgba(34,197,94,0.15)',
  approved: 'rgba(34,197,94,0.15)',
  blocked: 'rgba(239,68,68,0.15)',
  parked: 'rgba(100,116,139,0.2)',
  killed: 'rgba(100,116,139,0.1)',
  recommended: 'rgba(129,140,248,0.15)',
};

const STATUS_TEXT = {
  planned: '#94a3b8',
  ready: '#818cf8',
  in_progress: '#fbbf24',
  review: '#f59e0b',
  complete: '#22c55e',
  approved: '#22c55e',
  blocked: '#ef4444',
  parked: '#94a3b8',
  killed: '#64748b',
  recommended: '#818cf8',
};

function getTypeColor(type) {
  return TYPE_COLORS[type] || 'var(--color-text-secondary)';
}

function getStatusBadgeStyle(status) {
  return {
    fontSize: 'var(--row-label)',
    padding: 'var(--row-badge-pad)',
    borderRadius: '10px',
    flexShrink: 0,
    background: STATUS_BG[status] || STATUS_BG.planned,
    color: STATUS_TEXT[status] || STATUS_TEXT.planned,
  };
}

function formatStatus(status, type) {
  if (!status) return 'planned';
  if (type === 'question' && status === 'complete') return 'resolved';
  if (type === 'question' && status === 'killed') return 'dismissed';
  return status.replace(/_/g, ' ');
}

function isCompletedOrApproved(status) {
  return status === 'complete' || status === 'approved';
}

/**
 * ItemRow — Uniform expandable row for the Roadmap view.
 *
 * Props:
 *   item        — The item object ({ id, type, title, description, status, ... })
 *   items       — All items (for resolving connections)
 *   connections — All connections
 *   onDrillIn   — Callback when a linked item is clicked (triggers breadcrumb push)
 *   onAction    — Callback for approve/discuss/decline: (itemId, action)
 *   depth       — Nesting level for indentation (default 0)
 */
function ItemRow({ item, items, connections, onDrillIn, onAction, depth = 0, defaultExpanded = false }) {
  const storageKey = `roadmap-item-${item.id}`;
  const [expanded, setExpanded] = useState(() => {
    if (defaultExpanded) return true;
    const stored = sessionStorage.getItem(storageKey);
    return stored !== null ? stored === 'true' : false; // collapsed by default
  });
  const toggleExpanded = () => setExpanded(prev => {
    const next = !prev;
    sessionStorage.setItem(storageKey, String(next));
    return next;
  });

  // Find decision options: items connected via `informs` edges TO this decision
  const options = useMemo(() => {
    if (item.type !== 'decision' || !connections || !items) return [];
    const itemsById = new Map(items.map(i => [i.id, i]));
    const opts = [];

    for (const conn of connections) {
      // Items that inform this decision are options
      if (conn.toId === item.id && conn.type === 'informs') {
        const opt = itemsById.get(conn.fromId);
        if (opt) opts.push(opt);
      }
    }
    return opts;
  }, [item.id, item.type, connections, items]);

  // Build a set of option IDs for filtering duplicates from linkedItems
  const optionIds = useMemo(() => new Set(options.map(o => o.id)), [options]);

  // Find children: items that implement/support this item (or have parentId pointing here)
  const CHILD_EDGES = new Set(['implements', 'supports', 'contradicts']);
  const children = useMemo(() => {
    if (!connections || !items) return [];
    const childIds = new Set();
    const itemsById = new Map(items.map(i => [i.id, i]));
    for (const it of items) {
      if (it.parentId === item.id) childIds.add(it.id);
    }
    for (const conn of connections) {
      if (conn.toId === item.id && CHILD_EDGES.has(conn.type)) {
        childIds.add(conn.fromId);
      }
    }
    return [...childIds].map(id => itemsById.get(id)).filter(Boolean);
  }, [item.id, connections, items]);

  const childIds = useMemo(() => new Set(children.map(c => c.id)), [children]);

  // Find connections involving this item, split into blocking, questions (contradicts), and other linked
  const { blockingItems, questionItems, linkedItems } = useMemo(() => {
    if (!connections || !items) return { blockingItems: [], questionItems: [], linkedItems: [] };
    const blocking = [];
    const questions = [];
    const linked = [];
    const itemsById = new Map(items.map(i => [i.id, i]));

    for (const conn of connections) {
      if (conn.fromId === item.id) {
        const target = itemsById.get(conn.toId);
        if (target) {
          const entry = { item: target, edgeType: conn.type || 'related', direction: 'outgoing' };
          if (conn.type === 'blocks') {
            blocking.push(entry);
          } else if (conn.type === 'contradicts' && target.type === 'question') {
            questions.push(entry);
          } else if (!optionIds.has(target.id) && !childIds.has(target.id)) {
            linked.push(entry);
          }
        }
      } else if (conn.toId === item.id) {
        const source = itemsById.get(conn.fromId);
        if (source) {
          const entry = { item: source, edgeType: conn.type || 'related', direction: 'incoming' };
          if (conn.type === 'blocks') {
            blocking.push(entry);
          } else if (conn.type === 'contradicts' && source.type === 'question') {
            questions.push(entry);
          } else if (!optionIds.has(source.id) && !childIds.has(source.id)) {
            linked.push(entry);
          }
        }
      }
    }
    return { blockingItems: blocking, questionItems: questions, linkedItems: linked };
  }, [item.id, connections, items, optionIds, childIds]);

  // Rollup stats for collapsed summary
  const rollup = useMemo(() => {
    if (children.length === 0) return null;
    const total = children.length;
    const complete = children.filter(c => c.status === 'complete' || c.status === 'approved').length;
    const inProgress = children.filter(c => c.status === 'in_progress').length;
    const blocked = children.filter(c => c.status === 'blocked').length;
    const activeItems = children.filter(c => c.status === 'in_progress');
    return { total, complete, inProgress, blocked, activeItems };
  }, [children]);

  const { newIds, changedIds } = useContext(VisionChangesContext);
  const animClass = newIds.has(item.id) ? 'vision-entering' : changedIds.has(item.id) ? 'vision-updated' : '';

  const [resolveOpen, setResolveOpen] = useState(false);
  const [resolveText, setResolveText] = useState('');

  const handleDiscuss = useCallback(async () => {
    const desc = item.description || item.title;
    const text = `Be brief. Summarize, give your recommendation, refine the decision wording based on the resolution if needed: ${desc}\n`;
    try {
      await fetch('http://localhost:3002/api/terminal/inject', {
        method: 'POST',
        headers: withForgeToken({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({ text }),
      });
      // Focus the terminal
      const xtermTextarea = document.querySelector('.xterm-helper-textarea');
      if (xtermTextarea) xtermTextarea.focus();
    } catch (err) {
      console.error('Failed to inject into terminal:', err);
    }
  }, [item]);

  const handleResolve = useCallback(() => {
    const desc = resolveText.trim()
      ? `${item.description || ''}\n\n---\nResolution: ${resolveText.trim()}`
      : undefined;
    onAction?.(item.id, 'resolve', desc);
    setResolveOpen(false);
    setResolveText('');
  }, [item.id, item.description, resolveText, onAction]);

  const isDecision = item.type === 'decision';
  const isQuestion = item.type === 'question';
  const isApproved = isCompletedOrApproved(item.status);
  const isTerminal = isApproved || item.status === 'killed';
  const isResolvedQuestion = isQuestion && isTerminal;
  const hasOpenQuestions = questionItems.length > 0 && questionItems.some(q => q.item.status !== 'complete' && q.item.status !== 'killed');
  const dotColor = isResolvedQuestion
    ? (item.status === 'complete' ? '#22c55e' : '#64748b')
    : hasOpenQuestions ? '#fbbf24' : getTypeColor(item.type);

  const edgeLabel = (edgeType, direction) => {
    if (direction === 'incoming') {
      switch (edgeType) {
        case 'blocks': return 'blocked by';
        case 'informs': return 'informed by';
        case 'implements': return 'implemented by';
        case 'supports': return 'supported by';
        default: return edgeType;
      }
    }
    return edgeType;
  };

  return (
    <div
      className={animClass || undefined}
      style={{
        border: '1px solid var(--border-standard)',
        borderRadius: 'var(--row-radius)',
        marginBottom: 'var(--row-gap)',
        background: 'var(--color-surface)',
        overflow: 'hidden',
      }}
    >
      {/* Collapsed header — always visible */}
      <div
        onClick={toggleExpanded}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '10px',
          padding: 'var(--row-pad-v) var(--row-pad-h)',
          paddingLeft: `calc(var(--row-pad-h) + ${depth * 16}px)`,
          cursor: 'pointer',
          fontSize: 'var(--row-font)',
          background: expanded ? 'var(--color-surface-overlay)' : 'transparent',
          borderBottom: expanded ? '1px solid var(--border-soft)' : 'none',
        }}
        onMouseEnter={(e) => { if (!expanded) e.currentTarget.style.background = 'var(--primary-glow)'; }}
        onMouseLeave={(e) => { if (!expanded) e.currentTarget.style.background = expanded ? 'var(--color-surface-overlay)' : 'transparent'; }}
      >
        {/* Color dot */}
        <span
          style={{
            width: 'var(--row-dot)',
            height: 'var(--row-dot)',
            borderRadius: '50%',
            flexShrink: 0,
            background: dotColor,
          }}
        />

        {/* Semantic ID label */}
        {item.semanticId && (
          <span style={{
            fontSize: 'var(--row-label)',
            fontWeight: 600,
            color: dotColor,
            flexShrink: 0,
            fontFamily: 'monospace',
          }}>
            {item.semanticId}
          </span>
        )}

        {/* Title */}
        <span style={{ flex: 1, color: 'var(--color-text-primary)' }}>
          {item.title}
        </span>

        {/* Type badge */}
        <span style={{
          fontSize: 'var(--row-label)',
          padding: 'var(--row-badge-pad)',
          borderRadius: '4px',
          flexShrink: 0,
          background: `${dotColor}20`,
          color: dotColor,
          textTransform: 'uppercase',
          letterSpacing: '0.03em',
        }}>
          {item.type}
        </span>

        {/* Status badge */}
        <span style={getStatusBadgeStyle(item.status)}>
          {formatStatus(item.status, item.type)}
        </span>

        {/* Collapsed hints: connection count + needs-review for decisions */}
        {!expanded && (children.length + linkedItems.length + questionItems.length + blockingItems.length) > 0 && (
          <span style={{
            fontSize: 'var(--row-label)', color: 'var(--color-text-muted)', flexShrink: 0,
          }}>
            {children.length + linkedItems.length + questionItems.length + blockingItems.length} links
          </span>
        )}
        {!expanded && isDecision && !isApproved && (
          <span style={{
            fontSize: 'var(--row-label)', padding: 'var(--row-badge-pad)', borderRadius: '10px', flexShrink: 0,
            background: 'rgba(251,191,36,0.15)', color: '#fbbf24',
          }}>
            needs review
          </span>
        )}
        {!expanded && hasOpenQuestions && (
          <span style={{
            fontSize: 'var(--row-label)', padding: 'var(--row-badge-pad)', borderRadius: '10px', flexShrink: 0,
            background: 'rgba(251,191,36,0.15)', color: '#fbbf24',
          }}>
            {questionItems.filter(q => q.item.status !== 'complete' && q.item.status !== 'killed').length} open ?
          </span>
        )}

        {/* Chevron */}
        {expanded
          ? <ChevronDown className="row-chevron" style={{ color: '#818cf8', flexShrink: 0 }} />
          : <ChevronRight className="row-chevron" style={{ color: 'var(--color-text-muted)', flexShrink: 0 }} />
        }
      </div>

      {/* Collapsed summary — rollup + AI summary */}
      {!expanded && rollup && (
        <div style={{
          padding: `4px var(--row-body-pad-h)`, paddingLeft: `calc(var(--row-body-pad-h) + ${depth * 16}px + 20px)`,
          fontSize: '11px', lineHeight: 1.5, color: 'var(--color-text-muted)',
          display: 'flex', flexDirection: 'column', gap: '2px',
        }}>
          {/* Rollup stats */}
          <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
            <span>
              <span style={{ color: '#22c55e', fontWeight: 500 }}>{rollup.complete}</span>
              <span style={{ opacity: 0.5 }}>/{rollup.total}</span>
              {' done'}
            </span>
            {rollup.inProgress > 0 && (
              <span style={{ color: '#fbbf24' }}>{rollup.inProgress} active</span>
            )}
            {rollup.blocked > 0 && (
              <span style={{ color: '#ef4444' }}>{rollup.blocked} blocked</span>
            )}
            {rollup.activeItems.length > 0 && (
              <span style={{ opacity: 0.6 }}>
                {'· '}
                {rollup.activeItems.map(a => a.title).join(', ')}
              </span>
            )}
          </div>
        </div>
      )}

      {/* Expanded body */}
      {expanded && (
        <div style={{ padding: 'var(--row-body-pad-v) var(--row-body-pad-h)', paddingLeft: `calc(var(--row-body-pad-h) + ${depth * 16}px)`, fontSize: 'var(--row-body-font)', lineHeight: 1.6 }}>

          {/* Blocking dependencies — FIRST */}
          {blockingItems.length > 0 && (
            <div style={{ marginBottom: '10px' }}>
              {/* Blocked by: items that block this one (incoming blocks edges) */}
              {blockingItems.filter(b => b.direction === 'incoming').length > 0 && (
                <div style={{ marginBottom: '6px' }}>
                  <div style={{
                    fontSize: 'var(--row-section-label)', textTransform: 'uppercase', letterSpacing: '0.08em',
                    color: '#ef4444', marginBottom: '4px',
                  }}>
                    Blocked by
                  </div>
                  {blockingItems.filter(b => b.direction === 'incoming').map((link, i) => (
                    <div
                      key={`blocked-by-${link.item.id}-${i}`}
                      onClick={(e) => { e.stopPropagation(); onDrillIn?.(link.item); }}
                      style={{
                        display: 'flex', alignItems: 'center', gap: '6px',
                        padding: 'var(--row-link-pad)', fontSize: 'var(--row-link-font)', color: '#ef4444',
                        cursor: 'pointer', borderRadius: '3px',
                        background: 'rgba(239,68,68,0.06)',
                      }}
                      onMouseEnter={(e) => { e.currentTarget.style.background = 'rgba(239,68,68,0.12)'; }}
                      onMouseLeave={(e) => { e.currentTarget.style.background = 'rgba(239,68,68,0.06)'; }}
                    >
                      <span style={{
                        width: '6px', height: '6px', borderRadius: '50%', flexShrink: 0,
                        background: getTypeColor(link.item.type),
                      }} />
                      <span style={{ flex: 1 }}>{link.item.title}</span>
                      <span style={{ fontSize: 'var(--row-section-label)', color: '#ef4444', marginLeft: 'auto' }}>
                        blocked by
                      </span>
                      <ChevronRight style={{ color: '#ef4444', flexShrink: 0, width: 12, height: 12, opacity: 0.5 }} />
                    </div>
                  ))}
                </div>
              )}
              {/* Blocks: items this one blocks (outgoing blocks edges) */}
              {blockingItems.filter(b => b.direction === 'outgoing').length > 0 && (
                <div>
                  <div style={{
                    fontSize: 'var(--row-section-label)', textTransform: 'uppercase', letterSpacing: '0.08em',
                    color: '#f59e0b', marginBottom: '4px',
                  }}>
                    Blocks
                  </div>
                  {blockingItems.filter(b => b.direction === 'outgoing').map((link, i) => (
                    <div
                      key={`blocks-${link.item.id}-${i}`}
                      onClick={(e) => { e.stopPropagation(); onDrillIn?.(link.item); }}
                      style={{
                        display: 'flex', alignItems: 'center', gap: '6px',
                        padding: 'var(--row-link-pad)', fontSize: 'var(--row-link-font)', color: '#f59e0b',
                        cursor: 'pointer', borderRadius: '3px',
                      }}
                      onMouseEnter={(e) => { e.currentTarget.style.background = 'rgba(245,158,11,0.08)'; }}
                      onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent'; }}
                    >
                      <span style={{
                        width: '6px', height: '6px', borderRadius: '50%', flexShrink: 0,
                        background: getTypeColor(link.item.type),
                      }} />
                      <span style={{ flex: 1 }}>{link.item.title}</span>
                      <span style={{ fontSize: 'var(--row-section-label)', color: '#f59e0b', marginLeft: 'auto' }}>
                        blocks
                      </span>
                      <ChevronRight style={{ color: '#f59e0b', flexShrink: 0, width: 12, height: 12, opacity: 0.5 }} />
                    </div>
                  ))}
                </div>
              )}
              {/* Separator after blocking section */}
              <div style={{ height: '1px', background: 'var(--border-standard)', margin: '8px 0' }} />
            </div>
          )}

          {/* Description — parse resolution + history sections */}
          {item.description && (() => {
            let remaining = item.description;
            let resolution = '';
            let history = '';

            const resMarker = '\n\n---\nResolution:';
            const histMarker = '\n\n---\nHistory:';

            const resIdx = remaining.indexOf(resMarker);
            if (resIdx !== -1) {
              const after = remaining.slice(resIdx + resMarker.length);
              remaining = remaining.slice(0, resIdx).trim();
              const histInRes = after.indexOf(histMarker);
              if (histInRes !== -1) {
                resolution = after.slice(0, histInRes).trim();
                history = after.slice(histInRes + histMarker.length).trim();
              } else {
                resolution = after.trim();
              }
            }

            if (!history) {
              const histIdx = remaining.indexOf(histMarker);
              if (histIdx !== -1) {
                history = remaining.slice(histIdx + histMarker.length).trim();
                remaining = remaining.slice(0, histIdx).trim();
              }
            }

            const baseDesc = remaining;

            return (
              <>
                {baseDesc && (
                  <div style={{ color: 'var(--color-text-secondary)', marginBottom: (resolution || history) ? '6px' : '10px' }}>
                    {baseDesc}
                  </div>
                )}
                {resolution && (
                  <div
                    className={changedIds.has(item.id) ? 'resolution-sparkle' : undefined}
                    style={{
                      marginLeft: '0', paddingLeft: '10px', marginBottom: '10px',
                      borderLeft: '2px solid rgba(34,197,94,0.4)', paddingTop: '2px', paddingBottom: '2px',
                    }}
                  >
                    <div style={{ fontSize: 'var(--row-section-label)', textTransform: 'uppercase', letterSpacing: '0.08em', color: '#22c55e', marginBottom: '2px' }}>
                      Resolution
                    </div>
                    <div style={{ fontSize: 'var(--row-body-font)', color: 'var(--color-text-primary)', lineHeight: 1.5 }}>
                      {resolution}
                    </div>
                  </div>
                )}
                {history && <HistorySection history={history} />}
              </>
            );
          })()}

          {/* Children (items that implement this one) */}
          {children.length > 0 && (
            <div style={{ marginBottom: '10px' }}>
              <div style={{
                fontSize: 'var(--row-section-label)', textTransform: 'uppercase', letterSpacing: '0.08em',
                color: 'var(--color-text-tertiary)', marginBottom: '4px',
              }}>
                Children ({children.length})
              </div>
              {children.map(child => (
                <ItemRow
                  key={child.id}
                  item={child}
                  items={items}
                  connections={connections}
                  onDrillIn={onDrillIn}
                  onAction={onAction}
                  depth={depth + 1}
                />
              ))}
            </div>
          )}

          {/* Linked items (non-blocking, non-question) */}
          {linkedItems.length > 0 && (
            <div style={{ marginBottom: options.length > 0 ? '10px' : '0' }}>
              <div style={{
                fontSize: 'var(--row-section-label)', textTransform: 'uppercase', letterSpacing: '0.08em',
                color: 'var(--color-text-tertiary)', marginBottom: '4px',
              }}>
                Linked items
              </div>
              {linkedItems.map((link, i) => (
                <div
                  key={`${link.item.id}-${i}`}
                  onClick={(e) => { e.stopPropagation(); onDrillIn?.(link.item); }}
                  style={{
                    display: 'flex', alignItems: 'center', gap: '6px',
                    padding: 'var(--row-link-pad)', fontSize: 'var(--row-link-font)', color: '#818cf8',
                    cursor: 'pointer', borderRadius: '3px',
                  }}
                  onMouseEnter={(e) => { e.currentTarget.style.background = 'rgba(129,140,248,0.08)'; }}
                  onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent'; }}
                >
                  <span style={{
                    width: '6px', height: '6px', borderRadius: '50%', flexShrink: 0,
                    background: getTypeColor(link.item.type),
                  }} />
                  <span style={{ flex: 1 }}>{link.item.title}</span>
                  <span style={{ fontSize: 'var(--row-section-label)', color: 'var(--color-text-muted)', marginLeft: 'auto' }}>
                    {edgeLabel(link.edgeType, link.direction)}
                  </span>
                  <ChevronRight style={{ color: 'var(--color-text-muted)', flexShrink: 0, width: 12, height: 12 }} />
                </div>
              ))}
            </div>
          )}

          {/* Decision options */}
          {isDecision && options.length > 0 && (
            <div>
              <div style={{
                fontSize: 'var(--row-btn-font)', color: 'var(--color-text-tertiary)', marginBottom: '6px',
                textTransform: 'uppercase', letterSpacing: '0.05em',
              }}>
                Options
              </div>
              <OptionsList options={options} />
            </div>
          )}

          {/* Resolve text box */}
          {resolveOpen && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginTop: '8px' }}>
              <input
                style={{
                  flex: 1, fontSize: 'var(--row-body-font)', padding: 'var(--row-link-pad)', borderRadius: '4px',
                  border: '1px solid var(--border-standard)', background: 'var(--color-surface)',
                  color: 'var(--color-text-primary)', outline: 'none',
                }}
                placeholder="Resolution note (optional, Enter to submit)..."
                value={resolveText}
                onChange={(e) => setResolveText(e.target.value)}
                onKeyDown={(e) => {
                  e.stopPropagation();
                  if (e.key === 'Enter') handleResolve();
                  if (e.key === 'Escape') setResolveOpen(false);
                }}
                onClick={(e) => e.stopPropagation()}
                autoFocus
              />
              <button
                onClick={(e) => { e.stopPropagation(); handleResolve(); }}
                style={{
                  fontSize: 'var(--row-btn-font)', padding: 'var(--row-btn-pad)', borderRadius: '4px', cursor: 'pointer',
                  border: '1px solid rgba(34,197,94,0.3)', background: 'rgba(34,197,94,0.1)', color: '#22c55e',
                }}
              >
                Submit
              </button>
              <button
                onClick={(e) => { e.stopPropagation(); setResolveOpen(false); }}
                style={{
                  fontSize: 'var(--row-btn-font)', padding: 'var(--row-btn-pad)', borderRadius: '4px', cursor: 'pointer',
                  border: '1px solid var(--border-standard)', background: 'transparent', color: 'var(--color-text-muted)',
                }}
              >
                Cancel
              </button>
            </div>
          )}

          {/* Separator + Action buttons — at the bottom */}
          <div style={{
            display: 'flex',
            gap: '6px',
            marginTop: '10px',
            paddingTop: '8px',
            borderTop: '1px solid var(--border-soft)',
          }}>
            {/* Decision actions */}
            {isDecision && !isApproved && (
              <>
                <button
                  onClick={(e) => { e.stopPropagation(); onAction?.(item.id, 'approve'); }}
                  style={{
                    fontSize: 'var(--row-btn-font)', padding: 'var(--row-btn-pad)', borderRadius: '4px', cursor: 'pointer',
                    border: '1px solid rgba(34,197,94,0.3)', background: 'rgba(34,197,94,0.1)', color: '#22c55e',
                  }}
                >
                  Approve
                </button>
                <button
                  onClick={(e) => { e.stopPropagation(); onAction?.(item.id, 'pressure-test'); }}
                  style={{
                    fontSize: 'var(--row-btn-font)', padding: 'var(--row-btn-pad)', borderRadius: '4px', cursor: 'pointer',
                    border: '1px solid rgba(251,191,36,0.3)', background: 'rgba(251,191,36,0.1)', color: '#fbbf24',
                  }}
                >
                  Pressure Test
                </button>
                <button
                  onClick={(e) => { e.stopPropagation(); onAction?.(item.id, 'decline'); }}
                  style={{
                    fontSize: 'var(--row-btn-font)', padding: 'var(--row-btn-pad)', borderRadius: '4px', cursor: 'pointer',
                    border: '1px solid rgba(239,68,68,0.3)', background: 'rgba(239,68,68,0.1)', color: '#ef4444',
                  }}
                >
                  Decline
                </button>
              </>
            )}
            {isDecision && isApproved && (
              <button
                disabled
                style={{
                  fontSize: 'var(--row-btn-font)', padding: 'var(--row-btn-pad)', borderRadius: '4px',
                  border: '1px solid rgba(34,197,94,0.3)', background: 'rgba(34,197,94,0.15)', color: '#22c55e',
                  cursor: 'default',
                }}
              >
                Approved
              </button>
            )}

            {/* Question actions */}
            {isQuestion && !isTerminal && (
              <>
                <button
                  onClick={(e) => { e.stopPropagation(); handleDiscuss(); }}
                  style={{
                    fontSize: 'var(--row-btn-font)', padding: 'var(--row-btn-pad)', borderRadius: '4px', cursor: 'pointer',
                    border: '1px solid rgba(129,140,248,0.3)', background: 'rgba(129,140,248,0.1)', color: '#818cf8',
                  }}
                >
                  Discuss
                </button>
                <button
                  onClick={(e) => { e.stopPropagation(); setResolveOpen(true); }}
                  style={{
                    fontSize: 'var(--row-btn-font)', padding: 'var(--row-btn-pad)', borderRadius: '4px', cursor: 'pointer',
                    border: '1px solid rgba(34,197,94,0.3)', background: 'rgba(34,197,94,0.1)', color: '#22c55e',
                  }}
                >
                  Resolve
                </button>
                <button
                  onClick={(e) => { e.stopPropagation(); onAction?.(item.id, 'dismiss'); }}
                  style={{
                    fontSize: 'var(--row-btn-font)', padding: 'var(--row-btn-pad)', borderRadius: '4px', cursor: 'pointer',
                    border: '1px solid rgba(239,68,68,0.3)', background: 'rgba(239,68,68,0.1)', color: '#ef4444',
                  }}
                >
                  Dismiss
                </button>
              </>
            )}
            {isQuestion && isTerminal && (
              <span style={{
                fontSize: 'var(--row-btn-font)', padding: 'var(--row-btn-pad)', borderRadius: '4px',
                border: '1px solid var(--border-standard)',
                color: item.status === 'complete' ? '#22c55e' : 'var(--color-text-muted)',
              }}>
                {item.status === 'complete' ? 'Resolved' : 'Dismissed'}
              </span>
            )}

            {/* Generic actions for other types */}
            {!isDecision && !isQuestion && (
              <button
                onClick={(e) => { e.stopPropagation(); onAction?.(item.id, 'discuss'); }}
                style={{
                  fontSize: 'var(--row-btn-font)', padding: 'var(--row-btn-pad)', borderRadius: '4px', cursor: 'pointer',
                  border: '1px solid rgba(129,140,248,0.3)', background: 'rgba(129,140,248,0.1)', color: '#818cf8',
                }}
              >
                Discuss
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

/**
 * HistorySection — Collapsible revision history parsed from description.
 * Each line starting with [date] is a revision entry.
 */
function HistorySection({ history }) {
  const [open, setOpen] = useState(false);

  const entries = useMemo(() => {
    return history.split('\n').filter(l => l.trim()).map(line => {
      const match = line.match(/^\[([^\]]+)\]\s*(.*)$/);
      if (match) return { date: match[1], text: match[2] };
      return { date: '', text: line.trim() };
    });
  }, [history]);

  if (entries.length === 0) return null;

  return (
    <div style={{ marginBottom: '10px' }}>
      <div
        onClick={(e) => { e.stopPropagation(); setOpen(!open); }}
        style={{
          display: 'flex', alignItems: 'center', gap: '6px', cursor: 'pointer',
          fontSize: 'var(--row-section-label)', textTransform: 'uppercase', letterSpacing: '0.08em',
          color: 'var(--color-text-muted)', marginBottom: open ? '6px' : '0',
        }}
      >
        {open
          ? <ChevronDown style={{ width: 12, height: 12, flexShrink: 0 }} />
          : <ChevronRight style={{ width: 12, height: 12, flexShrink: 0 }} />
        }
        History
        <span style={{ opacity: 0.6 }}>({entries.length})</span>
      </div>
      {open && (
        <div style={{
          marginLeft: '0', paddingLeft: '10px',
          borderLeft: '2px solid var(--border-standard)',
        }}>
          {entries.map((entry, i) => (
            <div key={i} style={{
              padding: '4px 0', fontSize: 'var(--row-body-font)', lineHeight: 1.5,
              color: 'var(--color-text-secondary)',
              borderBottom: i < entries.length - 1 ? '1px solid var(--border-soft)' : 'none',
            }}>
              {entry.date && (
                <span style={{
                  fontSize: 'var(--row-section-label)', color: 'var(--color-text-muted)',
                  fontFamily: 'monospace', marginRight: '8px',
                }}>
                  {entry.date}
                </span>
              )}
              {entry.text}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default React.memo(ItemRow);

/**
 * OptionsList — Renders decision option items as nested expandable rows.
 */
function OptionsList({ options }) {
  return (
    <div>
      {options.map((opt, i) => (
        <OptionRow key={opt.id} option={opt} letter={String.fromCharCode(65 + i)} />
      ))}
    </div>
  );
}

/**
 * Parse pros/cons from description text.
 * Lines starting with `+ ` are pros, lines starting with `- ` are cons.
 * Remaining lines are the body text rendered above pros/cons.
 */
function parseProsCons(description) {
  if (!description) return { body: '', pros: [], cons: [] };
  const lines = description.split('\n');
  const pros = [];
  const cons = [];
  const bodyLines = [];

  for (const line of lines) {
    const trimmed = line.trim();
    if (trimmed.startsWith('+ ')) {
      pros.push(trimmed.slice(2));
    } else if (trimmed.startsWith('- ')) {
      cons.push(trimmed.slice(2));
    } else {
      bodyLines.push(line);
    }
  }

  return {
    body: bodyLines.join('\n').trim(),
    pros,
    cons,
  };
}

function OptionRow({ option, letter }) {
  const [expanded, setExpanded] = useState(false);
  const isRecommended = option.status === 'recommended';
  const { body, pros, cons } = useMemo(() => parseProsCons(option.description), [option.description]);
  const hasProsCons = pros.length > 0 || cons.length > 0;

  return (
    <div
      style={{
        border: '1px solid var(--border-standard)',
        borderRadius: 'var(--row-radius)',
        marginBottom: '6px',
        background: 'var(--color-surface)',
        overflow: 'hidden',
      }}
    >
      {/* Option header */}
      <div
        onClick={() => setExpanded(!expanded)}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '10px',
          padding: 'var(--row-pad-v) var(--row-pad-h)',
          cursor: 'pointer',
          fontSize: 'var(--row-body-font)',
          background: expanded ? 'var(--primary-glow)' : 'transparent',
          borderBottom: expanded ? '1px solid var(--border-soft)' : 'none',
          borderLeft: isRecommended ? '2px solid #818cf8' : '2px solid transparent',
        }}
        onMouseEnter={(e) => { if (!expanded) e.currentTarget.style.background = 'var(--primary-glow)'; }}
        onMouseLeave={(e) => { if (!expanded) e.currentTarget.style.background = expanded ? 'var(--primary-glow)' : 'transparent'; }}
      >
        {/* Letter prefix */}
        <span style={{
          fontWeight: 700,
          color: isRecommended ? '#818cf8' : 'var(--color-text-tertiary)',
          width: '16px',
          flexShrink: 0,
        }}>
          {letter}
        </span>

        {/* Option title */}
        <span style={{
          flex: 1,
          color: isRecommended ? 'var(--color-text-primary)' : 'var(--color-text-secondary)',
        }}>
          {isRecommended ? <b>{option.title}</b> : option.title}
        </span>

        {/* Recommended badge */}
        {isRecommended && (
          <span style={{
            fontSize: 'var(--row-btn-font)', padding: 'var(--row-badge-pad)', borderRadius: '10px', flexShrink: 0,
            background: 'rgba(129,140,248,0.15)', color: '#818cf8',
          }}>
            recommended
          </span>
        )}

        {/* Chevron */}
        {expanded
          ? <ChevronDown className="row-chevron" style={{ color: '#818cf8', flexShrink: 0 }} />
          : <ChevronRight className="row-chevron" style={{ color: 'var(--color-text-muted)', flexShrink: 0 }} />
        }
      </div>

      {/* Option body */}
      {expanded && (
        <div style={{ padding: 'var(--row-body-pad-v) var(--row-body-pad-h)', fontSize: 'var(--row-body-font)', lineHeight: 1.5 }}>
          {/* Body text (non-pros/cons lines) */}
          {body && (
            <div style={{ color: 'var(--color-text-secondary)', marginBottom: hasProsCons ? '8px' : '0' }}>
              {body}
            </div>
          )}

          {/* Pros/Cons two-column layout */}
          {hasProsCons && (
            <div style={{ display: 'flex', gap: '12px' }}>
              {/* Pros column */}
              <div style={{ flex: 1 }}>
                <div style={{
                  fontSize: 'var(--row-btn-font)', textTransform: 'uppercase', letterSpacing: '0.05em',
                  color: '#22c55e', marginBottom: '4px',
                }}>
                  Pros
                </div>
                <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
                  {pros.map((pro, i) => (
                    <li key={i} style={{ color: 'var(--color-text-secondary)', padding: '1px 0' }}>
                      <span style={{ color: '#22c55e' }}>+ </span>{pro}
                    </li>
                  ))}
                </ul>
              </div>
              {/* Cons column */}
              <div style={{ flex: 1 }}>
                <div style={{
                  fontSize: 'var(--row-btn-font)', textTransform: 'uppercase', letterSpacing: '0.05em',
                  color: '#ef4444', marginBottom: '4px',
                }}>
                  Cons
                </div>
                <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
                  {cons.map((con, i) => (
                    <li key={i} style={{ color: 'var(--color-text-secondary)', padding: '1px 0' }}>
                      <span style={{ color: '#ef4444' }}>- </span>{con}
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          )}

          {/* Fallback: no pros/cons lines, no body, but description exists */}
          {!body && !hasProsCons && option.description && (
            <div style={{ color: 'var(--color-text-secondary)' }}>
              {option.description}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
