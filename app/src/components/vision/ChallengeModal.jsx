import React, { useState, useCallback, useContext, useMemo, useEffect, useRef } from 'react';
import { X, Zap, Loader2, Check, XCircle, MessageSquare, Send } from 'lucide-react';
import { cn } from '@/lib/utils.js';
import { withForgeToken } from '@/lib/forge-api.js';
import { Button } from '@/components/ui/button.jsx';
import { TYPE_COLORS } from './constants.js';
import { VisionChangesContext } from './VisionTracker.jsx';

function ChallengeRow({ item, onUpdate }) {
  const { newIds, changedIds } = useContext(VisionChangesContext);
  const animClass = newIds.has(item.id) ? 'vision-entering' : changedIds.has(item.id) ? 'vision-updated' : '';

  const [resolving, setResolving] = useState(false);
  const [resolveText, setResolveText] = useState('');

  const isResolved = item.status === 'complete' || item.status === 'killed';

  // Parse resolution note from description (after "---\nResolution:")
  const { baseDesc, resolution } = useMemo(() => {
    if (!item.description) return { baseDesc: '', resolution: '' };
    const marker = '\n\n---\nResolution:';
    const idx = item.description.indexOf(marker);
    if (idx === -1) return { baseDesc: item.description, resolution: '' };
    return {
      baseDesc: item.description.slice(0, idx).trim(),
      resolution: item.description.slice(idx + marker.length).trim(),
    };
  }, [item.description]);

  const handleDiscuss = useCallback(async () => {
    const desc = item.description || item.title;
    const text = `Be brief. Summarize, give your recommendation, refine the decision wording based on the resolution if needed: ${desc}\n`;
    try {
      await fetch('http://localhost:3002/api/terminal/inject', {
        method: 'POST',
        headers: withForgeToken({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({ text }),
      });
      const xtermTextarea = document.querySelector('.xterm-helper-textarea');
      if (xtermTextarea) xtermTextarea.focus();
    } catch (err) {
      console.error('Failed to inject into terminal:', err);
    }
  }, [item]);

  const handleResolve = useCallback(() => {
    const desc = resolveText.trim()
      ? `${item.description || ''}\n\n---\nResolution: ${resolveText.trim()}`
      : item.description;
    onUpdate(item.id, { status: 'complete', description: desc });
    setResolving(false);
    setResolveText('');
  }, [item.id, item.description, resolveText, onUpdate]);

  const handleDismiss = useCallback(() => {
    onUpdate(item.id, { status: 'killed' });
  }, [item.id, onUpdate]);

  return (
    <div className={cn(
      'rounded-lg border p-3 space-y-2 transition-all',
      isResolved
        ? 'border-border/50 bg-muted/20 opacity-60'
        : 'border-border bg-muted/30',
      animClass,
    )}>
      {/* Question title */}
      <div className="flex items-start gap-2">
        <div
          className="w-2 h-2 rounded-full shrink-0 mt-1.5"
          style={{ background: isResolved ? 'var(--color-text-tertiary)' : TYPE_COLORS.question }}
        />
        <p className={cn(
          'text-sm font-medium leading-snug flex-1',
          isResolved ? 'text-muted-foreground line-through' : 'text-foreground',
        )}>
          {item.title}
        </p>
      </div>

      {/* Description */}
      {baseDesc && (
        <p className="text-xs text-muted-foreground leading-relaxed pl-4">
          {baseDesc}
        </p>
      )}

      {/* Resolution note */}
      {resolution && (
        <div className={cn('ml-4 pl-3 border-l-2 border-success/40 py-1', changedIds.has(item.id) && 'resolution-sparkle')}>
          <p className="text-[10px] font-medium uppercase tracking-wider text-success mb-0.5">Resolution</p>
          <p className="text-xs text-foreground leading-relaxed">{resolution}</p>
        </div>
      )}

      {/* Resolve text box */}
      {resolving && (
        <div className="ml-4 flex items-center gap-1.5">
          <input
            className="flex-1 text-xs bg-muted text-foreground px-2 py-1.5 rounded border border-border outline-none focus:border-ring"
            placeholder="Resolution note (optional)..."
            value={resolveText}
            onChange={(e) => setResolveText(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') handleResolve();
              if (e.key === 'Escape') setResolving(false);
            }}
            autoFocus
          />
          <Button variant="ghost" size="icon" className="h-7 w-7 text-success" onClick={handleResolve}>
            <Send className="h-3 w-3" />
          </Button>
          <Button variant="ghost" size="icon" className="h-7 w-7 text-muted-foreground" onClick={() => setResolving(false)}>
            <X className="h-3 w-3" />
          </Button>
        </div>
      )}

      {/* Actions */}
      {!isResolved && !resolving && (
        <div className="flex items-center gap-1.5 pl-4">
          <button
            onClick={handleDiscuss}
            className="text-[10px] px-2 py-0.5 rounded-md text-accent hover:bg-accent/10 flex items-center gap-1 transition-colors"
          >
            <MessageSquare className="h-2.5 w-2.5" /> Discuss
          </button>
          <button
            onClick={() => setResolving(true)}
            className="text-[10px] px-2 py-0.5 rounded-md text-success hover:bg-success/10 flex items-center gap-1 transition-colors"
          >
            <Check className="h-2.5 w-2.5" /> Resolve
          </button>
          <button
            onClick={handleDismiss}
            className="text-[10px] px-2 py-0.5 rounded-md text-muted-foreground hover:text-destructive hover:bg-destructive/10 flex items-center gap-1 transition-colors"
          >
            <XCircle className="h-2.5 w-2.5" /> Dismiss
          </button>
        </div>
      )}

      {/* Resolved status */}
      {isResolved && (
        <div className="pl-4">
          <span className={cn(
            'text-[10px] px-1.5 py-0.5 rounded-full',
            item.status === 'complete'
              ? 'bg-success/10 text-success'
              : 'bg-muted text-muted-foreground',
          )}>
            {item.status === 'complete' ? 'Resolved' : 'Dismissed'}
          </span>
        </div>
      )}
    </div>
  );
}

export default function ChallengeModal({ item, items, connections, onUpdate, onClose }) {
  const [agentId, setAgentId] = useState(null);
  const [agentStatus, setAgentStatus] = useState(null);
  const [agentOutput, setAgentOutput] = useState('');
  const pollRef = useRef(null);

  const challenges = useMemo(() => {
    const itemMap = new Map(items.map(i => [i.id, i]));
    const result = [];
    for (const conn of connections) {
      if (conn.type !== 'contradicts') continue;
      if (conn.toId === item.id) {
        const source = itemMap.get(conn.fromId);
        if (source) result.push(source);
      }
      if (conn.fromId === item.id) {
        const target = itemMap.get(conn.toId);
        if (target) result.push(target);
      }
    }
    result.sort((a, b) => {
      const ta = new Date(a.createdAt || 0).getTime();
      const tb = new Date(b.createdAt || 0).getTime();
      return tb - ta;
    });
    return result;
  }, [item.id, items, connections]);

  const openCount = challenges.filter(c => c.status !== 'complete' && c.status !== 'killed').length;

  useEffect(() => {
    if (!agentId || agentStatus !== 'running') return;
    pollRef.current = setInterval(async () => {
      try {
        const res = await fetch(`http://localhost:3001/api/agent/${agentId}`);
        if (!res.ok) return;
        const data = await res.json();
        if (data.status !== 'running') {
          setAgentStatus(data.status);
          clearInterval(pollRef.current);
        }
      } catch { /* ignore */ }
    }, 1500);
    return () => clearInterval(pollRef.current);
  }, [agentId, agentStatus]);

  const handleRun = useCallback(async () => {
    if (agentStatus === 'running') return;

    const desc = item.description ? `\nDescription: ${item.description}` : '';
    const prompt = [
      `Challenge the assumptions of this item and create counter-questions.`,
      ``,
      `Item: "${item.title}" (type: ${item.type}, status: ${item.status})${desc}`,
      ``,
      `Create 2-3 challenging questions that probe weaknesses, missing considerations, or alternative approaches. For each question, run:`,
      `node scripts/vision-track.mjs create "<your question>" --type question --phase ${item.phase || 'vision'} --description "<why this matters>" --connects-to ${item.id}:contradicts`,
      ``,
      `Be specific and constructive. Challenge the idea, not the person.`,
      `Only run the vision-track.mjs commands above. Do not do anything else.`,
    ].join('\n');

    setAgentStatus('running');

    try {
      const res = await fetch('http://localhost:3001/api/agent/spawn', {
        method: 'POST',
        headers: withForgeToken({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({ prompt }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        setAgentStatus('failed');
        setAgentOutput(err.error || 'Failed to spawn agent');
        return;
      }
      const data = await res.json();
      setAgentId(data.agentId);
    } catch (err) {
      setAgentStatus('failed');
      setAgentOutput(err.message);
    }
  }, [item, agentStatus]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/50" onClick={onClose} />

      <div className="relative w-full max-w-lg max-h-[80vh] flex flex-col rounded-xl border border-border bg-card shadow-2xl mx-4">
        {/* Header */}
        <div className="flex items-start gap-3 p-4 pb-3 border-b border-border shrink-0">
          <Zap className="h-5 w-5 text-amber-400 shrink-0 mt-0.5" />
          <div className="flex-1 min-w-0">
            <h2 className="text-sm font-semibold text-foreground">Pressure Test</h2>
            <p className="text-xs text-muted-foreground truncate mt-0.5">{item.title}</p>
          </div>
          <Button variant="ghost" size="icon" className="h-6 w-6 shrink-0" onClick={onClose}>
            <X className="h-3.5 w-3.5" />
          </Button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-auto p-4 space-y-3">
          {agentStatus === 'running' && (
            <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-accent/10 border border-accent/20">
              <Loader2 className="h-3.5 w-3.5 text-accent animate-spin" />
              <span className="text-xs text-accent">Generating challenges...</span>
            </div>
          )}

          {agentStatus === 'failed' && (
            <div className="px-3 py-2 rounded-lg bg-destructive/10 border border-destructive/20">
              <span className="text-xs text-destructive">Failed: {agentOutput}</span>
            </div>
          )}

          {challenges.length === 0 && !agentStatus ? (
            <div className="text-center py-8">
              <p className="text-sm text-muted-foreground">No challenges yet.</p>
              <p className="text-xs text-muted-foreground mt-1">Run a pressure test to generate counter-questions.</p>
            </div>
          ) : (
            challenges.map(c => (
              <ChallengeRow key={c.id} item={c} onUpdate={onUpdate} />
            ))
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between p-4 pt-3 border-t border-border shrink-0">
          <span className="text-[10px] text-muted-foreground">
            {openCount > 0
              ? `${openCount} open / ${challenges.length} total`
              : challenges.length > 0
                ? `${challenges.length} resolved`
                : 'No challenges'
            }
          </span>
          <Button
            size="sm"
            className={cn('h-8 text-xs gap-1.5', agentStatus === 'running' && 'opacity-50 pointer-events-none')}
            onClick={handleRun}
          >
            <Zap className="h-3.5 w-3.5" />
            {agentStatus === 'running' ? 'Generating...' : 'Run Pressure Test'}
          </Button>
        </div>
      </div>
    </div>
  );
}
