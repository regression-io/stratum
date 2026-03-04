import React, { useState, useCallback, useMemo } from 'react';
import { X, Link2, Pencil, Trash2, ChevronRight, ChevronDown, Search, Zap } from 'lucide-react';
import { cn } from '@/lib/utils.js';
import { Badge } from '@/components/ui/badge.jsx';
import { Button } from '@/components/ui/button.jsx';
import { Separator } from '@/components/ui/separator.jsx';
import { ScrollArea } from '@/components/ui/scroll-area.jsx';
import { TYPE_COLORS, STATUS_COLORS, PHASES, PHASE_LABELS, STATUSES, CONFIDENCE_LABELS } from './constants.js';
import ConnectionGraph from './ConnectionGraph.jsx';

function ConfidenceControl({ level, onChange }) {
  const colors = ['hsl(var(--muted-foreground))', 'hsl(var(--destructive))', 'hsl(var(--accent))', 'hsl(var(--success))', 'hsl(var(--success))'];
  const color = colors[level] || colors[0];

  return (
    <button
      onClick={() => onChange((level + 1) % 5)}
      className="flex items-center gap-2 px-2 py-1 rounded-md bg-muted hover:bg-muted/80 transition-colors"
      title="Click to cycle confidence"
    >
      <span className="text-xs text-muted-foreground">{CONFIDENCE_LABELS[level]}</span>
      <div className="flex items-center gap-0.5">
        {[0, 1, 2, 3].map(i => (
          <div
            key={i}
            className="rounded-full transition-all"
            style={{
              width: 6,
              height: 6,
              background: i < level ? color : 'transparent',
              border: `1.5px solid ${i < level ? color : 'hsl(var(--border))'}`,
            }}
          />
        ))}
      </div>
    </button>
  );
}

function RelatedItems({ item, connections, items, onSelect, onDeleteConnection }) {
  const itemMap = new Map(items.map(i => [i.id, i]));
  const related = [];

  for (const conn of connections) {
    if (conn.type === 'contradicts') continue; // shown in Pressure Test modal
    if (conn.fromId === item.id) {
      const target = itemMap.get(conn.toId);
      if (target) related.push({ item: target, type: conn.type, direction: 'outgoing', connId: conn.id });
    }
    if (conn.toId === item.id) {
      const source = itemMap.get(conn.fromId);
      if (source) related.push({ item: source, type: conn.type, direction: 'incoming', connId: conn.id });
    }
  }

  if (related.length === 0) return null;

  // Group by connection type
  const groups = {};
  for (const r of related) {
    const key = `${r.type}-${r.direction}`;
    if (!groups[key]) groups[key] = { type: r.type, direction: r.direction, items: [] };
    groups[key].items.push({ item: r.item, connId: r.connId });
  }

  return (
    <div className="space-y-2">
      <p className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground">Connections</p>
      {Object.values(groups).map(group => (
        <div key={`${group.type}-${group.direction}`}>
          <p className="text-[10px] text-muted-foreground mb-1">
            {group.direction === 'incoming' ? `${group.type} from` : `${group.type} to`}
          </p>
          <div className="space-y-0.5">
            {group.items.map(({ item: relItem, connId }) => (
              <div
                key={connId}
                className="flex w-full items-center gap-2 px-2 py-1 rounded text-left hover:bg-muted/50 transition-colors group/conn"
              >
                <button
                  onClick={() => onSelect(relItem.id)}
                  className="flex flex-1 items-center gap-2 min-w-0"
                >
                  <div
                    className="w-1.5 h-1.5 rounded-full shrink-0"
                    style={{ background: STATUS_COLORS[relItem.status] || STATUS_COLORS.planned }}
                  />
                  <span className="text-xs text-foreground truncate">{relItem.title}</span>
                  <span className="text-[10px] ml-auto shrink-0" style={{ color: TYPE_COLORS[relItem.type] }}>
                    {relItem.type}
                  </span>
                </button>
                {onDeleteConnection && (
                  <button
                    onClick={() => onDeleteConnection(connId)}
                    className="opacity-0 group-hover/conn:opacity-100 p-0.5 rounded hover:bg-destructive/20 text-muted-foreground hover:text-destructive transition-all shrink-0"
                    title="Remove connection"
                  >
                    <X className="h-3 w-3" />
                  </button>
                )}
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

function formatTimestamp(dateStr) {
  if (!dateStr) return '';
  const d = new Date(dateStr);
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) + ' ' +
    d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false });
}


const CONNECTION_TYPES = ['informs', 'supports', 'blocks', 'contradicts'];

function ConnectPopover({ item, items, onCreateConnection, onDismiss }) {
  const [search, setSearch] = useState('');
  const [connType, setConnType] = useState('informs');

  const candidates = items.filter(i => {
    if (i.id === item.id) return false;
    if (!search) return true;
    return i.title.toLowerCase().includes(search.toLowerCase());
  }).slice(0, 8);

  const handlePick = useCallback(async (targetId) => {
    await onCreateConnection({ fromId: item.id, toId: targetId, type: connType });
    onDismiss();
  }, [item.id, connType, onCreateConnection, onDismiss]);

  return (
    <div className="absolute bottom-full left-0 mb-1 w-64 rounded-md border border-border bg-popover shadow-lg z-50">
      <div className="p-2 space-y-2">
        <div className="flex items-center gap-1.5">
          <select
            className="text-[10px] px-1.5 py-1 rounded bg-muted text-foreground border border-border cursor-pointer"
            value={connType}
            onChange={(e) => setConnType(e.target.value)}
          >
            {CONNECTION_TYPES.map(t => (
              <option key={t} value={t}>{t}</option>
            ))}
          </select>
          <span className="text-[10px] text-muted-foreground">to...</span>
        </div>
        <div className="relative">
          <Search className="absolute left-2 top-1/2 -translate-y-1/2 h-3 w-3 text-muted-foreground" />
          <input
            className="w-full text-xs bg-muted text-foreground pl-7 pr-2 py-1.5 rounded border border-border outline-none"
            placeholder="Search items..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            autoFocus
          />
        </div>
        <div className="max-h-40 overflow-auto space-y-0.5">
          {candidates.length === 0 ? (
            <p className="text-[10px] text-muted-foreground text-center py-2">No items found</p>
          ) : (
            candidates.map(c => (
              <button
                key={c.id}
                onClick={() => handlePick(c.id)}
                className="flex w-full items-center gap-2 px-2 py-1 rounded text-left hover:bg-muted/50 transition-colors"
              >
                <div
                  className="w-1.5 h-1.5 rounded-full shrink-0"
                  style={{ background: STATUS_COLORS[c.status] || STATUS_COLORS.planned }}
                />
                <span className="text-xs text-foreground truncate">{c.title}</span>
                <span className="text-[10px] ml-auto shrink-0" style={{ color: TYPE_COLORS[c.type] }}>
                  {c.type}
                </span>
              </button>
            ))
          )}
        </div>
      </div>
    </div>
  );
}

export default function ItemDetailPanel({ item, items, connections, onUpdate, onDelete, onCreateConnection, onDeleteConnection, onSelect, onClose, onPressureTest }) {
  const [editingTitle, setEditingTitle] = useState(false);
  const [titleDraft, setTitleDraft] = useState('');
  const [editingDesc, setEditingDesc] = useState(false);
  const [descDraft, setDescDraft] = useState('');
  const [connectOpen, setConnectOpen] = useState(false);

  const startEditTitle = useCallback(() => {
    setTitleDraft(item.title);
    setEditingTitle(true);
  }, [item?.title]);

  const commitTitle = useCallback(() => {
    if (titleDraft.trim() && titleDraft !== item.title) {
      onUpdate(item.id, { title: titleDraft.trim() });
    }
    setEditingTitle(false);
  }, [titleDraft, item?.id, item?.title, onUpdate]);

  const startEditDesc = useCallback(() => {
    setDescDraft(item.description || '');
    setEditingDesc(true);
  }, [item?.description]);

  const commitDesc = useCallback(() => {
    if (descDraft !== (item.description || '')) {
      onUpdate(item.id, { description: descDraft });
    }
    setEditingDesc(false);
  }, [descDraft, item?.id, item?.description, onUpdate]);

  const challengeCount = useMemo(() => {
    if (!item) return 0;
    let count = 0;
    for (const conn of connections) {
      if (conn.type === 'contradicts' && (conn.fromId === item.id || conn.toId === item.id)) count++;
    }
    return count;
  }, [item?.id, connections]);

  if (!item) return null;

  const typeColor = TYPE_COLORS[item.type] || TYPE_COLORS.task;

  return (
    <div className="w-80 shrink-0 border-l border-border bg-card flex flex-col h-full">
      {/* Header */}
      <div className="p-3 pb-2 flex items-start gap-2">
        <div className="flex-1 min-w-0">
          {/* Type + Phase badges */}
          <div className="flex items-center gap-1.5 mb-1.5">
            <Badge variant="outline" className="text-[10px] px-1.5 py-0 h-4" style={{ color: typeColor, borderColor: typeColor }}>
              {item.type}
            </Badge>
            {item.phase && (
              <Badge variant="outline" className="text-[10px] px-1.5 py-0 h-4">
                {PHASE_LABELS[item.phase] || item.phase}
              </Badge>
            )}
          </div>

          {/* Title */}
          {editingTitle ? (
            <input
              className="w-full text-sm font-semibold bg-muted text-foreground px-1.5 py-0.5 rounded border border-ring outline-none"
              value={titleDraft}
              onChange={(e) => setTitleDraft(e.target.value)}
              onBlur={commitTitle}
              onKeyDown={(e) => {
                if (e.key === 'Enter') commitTitle();
                if (e.key === 'Escape') setEditingTitle(false);
              }}
              autoFocus
            />
          ) : (
            <h3
              className="text-sm font-semibold text-foreground cursor-pointer hover:text-accent transition-colors"
              onDoubleClick={startEditTitle}
              title="Double-click to edit"
            >
              {item.title}
            </h3>
          )}
        </div>
        <Button variant="ghost" size="icon" className="h-6 w-6 shrink-0" onClick={onClose}>
          <X className="h-3.5 w-3.5" />
        </Button>
      </div>

      <Separator />

      {/* Scrollable body */}
      <ScrollArea className="flex-1">
        <div className="p-3 space-y-4">
          {/* Status + Confidence row */}
          <div className="flex items-center gap-2 flex-wrap">
            <select
              className="text-xs px-2 py-1 rounded-md bg-muted text-foreground border border-border cursor-pointer"
              value={item.status || 'planned'}
              onChange={(e) => onUpdate(item.id, { status: e.target.value })}
            >
              {STATUSES.map(s => (
                <option key={s} value={s}>{s.replace('_', ' ')}</option>
              ))}
            </select>

            <ConfidenceControl
              level={item.confidence || 0}
              onChange={(c) => onUpdate(item.id, { confidence: c })}
            />
          </div>

          {/* Phase selector */}
          <div>
            <p className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground mb-1">Phase</p>
            <select
              className="text-xs px-2 py-1 rounded-md bg-muted text-foreground border border-border cursor-pointer w-full"
              value={item.phase || ''}
              onChange={(e) => onUpdate(item.id, { phase: e.target.value || null })}
            >
              <option value="">No phase</option>
              {PHASES.map(p => (
                <option key={p} value={p}>{PHASE_LABELS[p]}</option>
              ))}
            </select>
          </div>

          {/* Description */}
          <div>
            <p className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground mb-1">Description</p>
            {editingDesc ? (
              <textarea
                className="w-full text-xs bg-muted text-foreground px-2 py-1.5 rounded border border-ring outline-none resize-none"
                rows={4}
                value={descDraft}
                onChange={(e) => setDescDraft(e.target.value)}
                onBlur={commitDesc}
                onKeyDown={(e) => {
                  if (e.key === 'Escape') setEditingDesc(false);
                }}
                autoFocus
              />
            ) : (
              <p
                className={cn(
                  'text-xs leading-relaxed cursor-pointer rounded px-2 py-1.5 hover:bg-muted/50 transition-colors',
                  item.description ? 'text-muted-foreground' : 'text-muted-foreground/50 italic'
                )}
                onClick={startEditDesc}
              >
                {item.description || 'Click to add description...'}
              </p>
            )}
          </div>

          {/* Related items */}
          <RelatedItems
            item={item}
            connections={connections}
            items={items}
            onSelect={onSelect}
            onDeleteConnection={onDeleteConnection}
          />

          {/* Connection sub-graph */}
          <ConnectionGraph
            item={item}
            items={items}
            connections={connections}
            onSelect={onSelect}
          />

          {/* Evidence: Stratum ensure violations (T3-8 blocker evidence) */}
          {item.evidence?.stratumViolations?.length > 0 && (
            <div>
              <p className="text-[10px] font-medium uppercase tracking-wider text-destructive mb-1.5">
                Blocked — Ensure Violations
                {item.evidence.violatedAt && (
                  <span className="ml-2 font-normal normal-case text-muted-foreground">{formatTimestamp(item.evidence.violatedAt)}</span>
                )}
              </p>
              <div className="space-y-0.5">
                {item.evidence.stratumViolations.map((msg, i) => (
                  <div key={i} className="flex items-start gap-2 px-2 py-1 rounded bg-destructive/10">
                    <div className="w-1.5 h-1.5 rounded-full shrink-0 mt-1" style={{ background: 'hsl(var(--destructive))' }} />
                    <span className="text-[10px] text-destructive leading-relaxed">{msg}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Evidence: Stratum audit trace (T3-9) */}
          {item.evidence?.stratumTrace && (
            <div>
              <p className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground mb-1.5">
                Stratum Trace
                {item.evidence.tracedAt && (
                  <span className="ml-2 font-normal normal-case">{formatTimestamp(item.evidence.tracedAt)}</span>
                )}
              </p>
              <div className="space-y-0.5">
                {(item.evidence.stratumTrace.trace || []).map((step) => (
                  <div key={step.step_id} className="flex items-center gap-2 px-2 py-1 rounded bg-muted/30">
                    <div className="w-1.5 h-1.5 rounded-full shrink-0" style={{ background: 'hsl(var(--success))' }} />
                    <span className="text-[10px] font-mono text-foreground truncate flex-1">{step.step_id}</span>
                    {step.attempts > 1 && (
                      <span className="text-[10px] text-amber-400 shrink-0">{step.attempts}x</span>
                    )}
                    {step.duration_ms != null && (
                      <span className="text-[10px] text-muted-foreground shrink-0">
                        {step.duration_ms < 1000 ? `${step.duration_ms}ms` : `${(step.duration_ms / 1000).toFixed(1)}s`}
                      </span>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Timestamps */}
          <div className="space-y-0.5">
            <p className="text-[10px] text-muted-foreground">
              Created {formatTimestamp(item.createdAt)}
            </p>
            <p className="text-[10px] text-muted-foreground">
              Updated {formatTimestamp(item.updatedAt)}
            </p>
          </div>

          {/* Actions */}
          <div className="flex items-center gap-1.5 flex-wrap">
            <div className="relative">
              <Button
                variant="outline"
                size="sm"
                className={cn('h-7 text-xs gap-1', connectOpen && 'bg-accent/10 border-accent')}
                onClick={() => setConnectOpen(!connectOpen)}
              >
                <Link2 className="h-3 w-3" /> Connect
              </Button>
              {connectOpen && (
                <ConnectPopover
                  item={item}
                  items={items}
                  onCreateConnection={onCreateConnection}
                  onDismiss={() => setConnectOpen(false)}
                />
              )}
            </div>
            <Button variant="outline" size="sm" className="h-7 text-xs gap-1" onClick={startEditTitle}>
              <Pencil className="h-3 w-3" /> Rename
            </Button>
            {item.type !== 'question' && (
              <Button
                variant="outline"
                size="sm"
                className="h-7 text-xs gap-1"
                onClick={() => onPressureTest(item.id)}
                title="Challenge this item's assumptions"
              >
                <Zap className="h-3 w-3" /> Pressure Test
                {challengeCount > 0 && (
                  <span className="ml-0.5 text-[10px] px-1 py-0 rounded-full bg-amber-500/20 text-amber-400">{challengeCount}</span>
                )}
              </Button>
            )}
            {item.status !== 'killed' && (
              <Button
                variant="outline"
                size="sm"
                className="h-7 text-xs gap-1 text-destructive border-destructive/30 hover:bg-destructive/10"
                onClick={() => onUpdate(item.id, { status: 'killed' })}
              >
                <Trash2 className="h-3 w-3" /> Kill
              </Button>
            )}
            {onDelete && (
              <Button
                variant="outline"
                size="sm"
                className="h-7 text-xs gap-1 text-destructive border-destructive/30 hover:bg-destructive/10"
                onClick={() => {
                  if (window.confirm(`Delete "${item.title}" permanently? This cannot be undone.`)) {
                    onDelete(item.id);
                  }
                }}
                title="Permanently delete this item"
              >
                <Trash2 className="h-3 w-3" /> Delete
              </Button>
            )}
          </div>
        </div>
      </ScrollArea>
    </div>
  );
}
