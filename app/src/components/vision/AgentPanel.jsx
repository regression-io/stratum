import React from 'react';

const CATEGORY_LABELS = {
  reading: 'Reading', writing: 'Writing', executing: 'Running',
  searching: 'Searching', fetching: 'Fetching', delegating: 'Delegating',
  thinking: 'Thinking',
};

const CATEGORY_COLORS = {
  reading: 'var(--color-category-reading)',
  writing: 'var(--color-category-writing)',
  executing: 'var(--color-category-executing)',
  searching: 'var(--color-category-searching)',
  fetching: 'var(--color-category-fetching)',
  delegating: 'var(--color-category-delegating)',
  thinking: 'var(--ink-tertiary)',
};

const ERROR_TYPE_LABELS = {
  build_error: 'Build', test_failure: 'Test', lint_error: 'Lint',
  git_conflict: 'Conflict', permission_error: 'Permission', not_found: 'Not Found',
  runtime_error: 'Error',
};

function formatElapsed(ms) {
  if (!ms || ms < 1000) return '<1s';
  const s = Math.floor(ms / 1000);
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  return `${m}m ${s % 60}s`;
}

const SessionTimer = React.memo(function SessionTimer({ startedAt, active, duration }) {
  const [, tick] = React.useState(0);
  React.useEffect(() => {
    if (!active) return;
    const id = setInterval(() => tick(n => n + 1), 1000);
    return () => clearInterval(id);
  }, [active]);

  const elapsed = active
    ? Math.floor((Date.now() - new Date(startedAt).getTime()) / 1000)
    : (duration || 0);
  const m = Math.floor(elapsed / 60);
  const s = elapsed % 60;
  return <span className="tabular-nums">{m}m {String(s).padStart(2, '0')}s</span>;
});

/**
 * AgentPanel — volatile telemetry display for agent status, activity, errors, and session info.
 * Extracted from AppSidebar to isolate high-frequency re-renders from stable navigation.
 */
function AgentPanel({ agentActivity, agentErrors, sessionState }) {
  const [agentState, setAgentState] = React.useState({
    status: 'idle', tool: null, category: null, activityLog: [], currentActivity: null,
  });
  const [, tick] = React.useState(0);
  const [resolvedItems, setResolvedItems] = React.useState([]);
  const resolvedTimerRef = React.useRef(null);

  // Listen for OSC-sourced agent status from Terminal
  React.useEffect(() => {
    const handler = (e) => setAgentState(e.detail);
    window.addEventListener('forge:agent-status', handler);
    return () => window.removeEventListener('forge:agent-status', handler);
  }, []);

  // Tick elapsed time while agent is working
  React.useEffect(() => {
    if (agentState.status !== 'working') return;
    const id = setInterval(() => tick(n => n + 1), 1000);
    return () => clearInterval(id);
  }, [agentState.status]);

  // Extract resolved items from hook-sourced activity and fade after 30s
  React.useEffect(() => {
    if (!agentActivity || agentActivity.length === 0) return;
    const latest = agentActivity[agentActivity.length - 1];
    if (Array.isArray(latest.items) && latest.items.length > 0) {
      setResolvedItems(latest.items);
      if (resolvedTimerRef.current) clearTimeout(resolvedTimerRef.current);
      resolvedTimerRef.current = setTimeout(() => setResolvedItems([]), 30000);
    }
  }, [agentActivity]);

  // Cleanup timer on unmount
  React.useEffect(() => {
    return () => {
      if (resolvedTimerRef.current) clearTimeout(resolvedTimerRef.current);
    };
  }, []);

  return (
    <>
      {/* Session info */}
      {sessionState && (
        <div className="px-3 pb-1">
          <div className="flex items-center gap-1.5 text-[10px]" style={{ color: 'var(--ink-tertiary, var(--color-text-tertiary))' }}>
            <span className="w-1.5 h-1.5 rounded-full shrink-0" style={{
              background: sessionState.active ? 'var(--color-primary)' : 'var(--color-success)',
            }} />
            <SessionTimer startedAt={sessionState.startedAt} active={sessionState.active} duration={sessionState.duration} />
            <span className="tabular-nums">{sessionState.toolCount || 0} tools</span>
            {sessionState.errorCount > 0 && (
              <span style={{ color: 'var(--color-error, #ef4444)' }}>{sessionState.errorCount} err</span>
            )}
            {!sessionState.active && sessionState.journalSpawned && (
              <span style={{ color: 'var(--color-primary)' }}>journal</span>
            )}
          </div>
          {sessionState.summaries?.length > 0 && (
            <p className="text-[10px] mt-0.5 truncate" style={{ color: 'var(--ink-tertiary, var(--color-text-tertiary))', opacity: 0.7 }}
              title={sessionState.summaries[sessionState.summaries.length - 1]?.summary}>
              {sessionState.summaries[sessionState.summaries.length - 1]?.summary}
            </p>
          )}
        </div>
      )}

      {/* Agent activity */}
      <div className="px-3 pb-2">
        <div className="rounded-md p-2" style={{ background: 'var(--color-surface-overlay)' }}>
          <div className="flex items-center gap-1.5 mb-1">
            <div
              className="w-1.5 h-1.5 rounded-full flex-shrink-0"
              style={{
                background: agentState.status === 'working' ? 'var(--color-category-writing)' : 'var(--color-success)',
                animation: agentState.status === 'working' ? 'pulse 1.5s ease-in-out infinite' : 'none',
              }}
            />
            <span className="text-[10px] font-medium uppercase tracking-wider" style={{
              color: agentState.status === 'working' ? 'var(--color-category-writing)' : 'var(--ink-tertiary, var(--color-text-tertiary))',
            }}>
              {agentState.status === 'working'
                ? (CATEGORY_LABELS[agentState.category] || 'Working')
                : 'Idle'}
            </span>
            {agentState.status === 'working' && agentState.tool && (
              <span className="text-[10px] tracking-wider" style={{ color: 'var(--ink-tertiary, var(--color-text-tertiary))' }}>
                {agentState.tool}
              </span>
            )}
            {agentState.status === 'working' && agentState.currentActivity && (
              <span className="text-[10px] tabular-nums ml-auto" style={{ color: 'var(--ink-tertiary, var(--color-text-tertiary))', opacity: 0.6 }}>
                {formatElapsed(Date.now() - agentState.currentActivity.startTime)}
              </span>
            )}
          </div>
          {/* Recent activity strip */}
          {agentState.activityLog && agentState.activityLog.length > 0 && (
            <div className="flex items-center gap-0.5 mt-1">
              {agentState.activityLog.slice(-6).map((entry, i, arr) => (
                <div
                  key={i}
                  className="h-1 rounded-full"
                  title={`${entry.tool || 'thinking'} — ${formatElapsed(entry.duration)}`}
                  style={{
                    width: Math.max(4, Math.min(16, (entry.duration || 0) / 1000 * 2)),
                    background: CATEGORY_COLORS[entry.category] || (agentState.status === 'working' ? 'var(--color-category-writing)' : 'var(--color-success)'),
                    opacity: 0.2 + (i / arr.length) * 0.6,
                  }}
                />
              ))}
            </div>
          )}
          {/* Hook-sourced activity feed */}
          {agentActivity && agentActivity.length > 0 && (
            <div className="mt-1.5 space-y-0.5">
              {agentActivity.slice(-4).map((entry, i) => (
                <div key={i} className="flex items-center gap-1 text-[10px]" style={{ color: entry.error ? 'var(--color-error, #ef4444)' : 'var(--ink-tertiary, var(--color-text-tertiary))' }}>
                  {entry.error && (
                    <span className="w-1.5 h-1.5 rounded-full shrink-0" style={{ background: 'var(--color-error, #ef4444)' }} />
                  )}
                  <span className="font-medium shrink-0">{entry.tool}</span>
                  {entry.category && !entry.error && (
                    <span className="shrink-0 opacity-50"
                      style={{ color: CATEGORY_COLORS[entry.category] }}>
                      {entry.category}
                    </span>
                  )}
                  {entry.error ? (
                    <span className="truncate" title={entry.error.type}>
                      {ERROR_TYPE_LABELS[entry.error.type] || entry.error.type}
                    </span>
                  ) : entry.detail ? (
                    <span className="truncate opacity-60" title={entry.detail}>
                      {entry.detail.split('/').pop()}
                    </span>
                  ) : null}
                </div>
              ))}
            </div>
          )}
          {/* Resolved tracker items */}
          {resolvedItems.length > 0 && (
            <div className="mt-1.5">
              <p className="text-[10px] font-medium uppercase tracking-wider mb-0.5"
                 style={{ color: 'var(--ink-tertiary, var(--color-text-tertiary))' }}>
                Working on
              </p>
              {resolvedItems.slice(0, 3).map(item => (
                <div key={item.id}
                  className="flex items-center gap-1 text-[10px] py-0.5"
                  style={{ color: 'var(--color-text-secondary)' }}>
                  <span>{item.status === 'in_progress' ? '◆' : '◇'}</span>
                  <span className="truncate">{item.title}</span>
                </div>
              ))}
            </div>
          )}
          {/* Recent errors */}
          {agentErrors && agentErrors.length > 0 && (
            <div className="mt-1.5">
              <p className="text-[10px] font-medium uppercase tracking-wider mb-0.5"
                 style={{ color: 'var(--color-error, #ef4444)' }}>
                Errors
              </p>
              {agentErrors.slice(-3).map((err, i) => (
                <div key={i} className="flex items-center gap-1 text-[10px] py-0.5"
                  style={{ color: 'var(--color-error, #ef4444)' }}>
                  <span className="font-medium shrink-0">
                    {ERROR_TYPE_LABELS[err.errorType] || err.errorType}
                  </span>
                  <span className="truncate opacity-70" title={err.message}>
                    {err.message}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </>
  );
}

export default React.memo(AgentPanel);
