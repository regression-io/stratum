import React, { useState } from 'react';

/**
 * MessageCard — renders a single SDK message in the stream.
 *
 * Handled types:
 *   system/init       → session metadata header
 *   system/connected  → reconnect notice
 *   assistant         → text + tool_use content blocks
 *   user              → user prompt echo
 *   result            → completion summary (cost, turns, duration)
 *   error             → error banner
 *   tool_progress     → live tool execution ticker (collapsed by default)
 *   stream_event      → skipped (partial streaming events, too noisy)
 */

const TOOL_CATEGORY_COLORS = {
  reading:   'hsl(210 70% 60%)',
  writing:   'hsl(142 60% 50%)',
  executing: 'hsl(38 90% 60%)',
  searching: 'hsl(270 60% 65%)',
  fetching:  'hsl(190 70% 55%)',
  delegating:'hsl(330 60% 65%)',
  thinking:  'hsl(240 30% 70%)',
};

const TOOL_CATEGORIES = {
  Read: 'reading', Glob: 'searching', Grep: 'searching',
  Write: 'writing', Edit: 'writing', NotebookEdit: 'writing',
  Bash: 'executing', Task: 'delegating', Skill: 'delegating',
  WebFetch: 'fetching', WebSearch: 'searching',
  TodoRead: 'reading', TodoWrite: 'writing',
};

function toolColor(name) {
  return TOOL_CATEGORY_COLORS[TOOL_CATEGORIES[name] || 'thinking'];
}

function formatMs(ms) {
  if (!ms) return '';
  if (ms < 1000) return `${ms}ms`;
  const s = (ms / 1000).toFixed(1);
  return `${s}s`;
}

function formatCost(usd) {
  if (usd == null) return '';
  if (usd < 0.001) return '<$0.001';
  return `$${usd.toFixed(3)}`;
}

/** Collapsible JSON viewer for tool inputs */
function ToolInput({ input }) {
  const [open, setOpen] = useState(false);
  if (!input || Object.keys(input).length === 0) return null;

  // Show a short preview: first key's value truncated
  const firstKey = Object.keys(input)[0];
  const firstVal = String(input[firstKey] ?? '');
  const preview = firstVal.length > 60 ? firstVal.slice(0, 57) + '…' : firstVal;

  return (
    <div className="mt-1">
      <button
        onClick={() => setOpen(o => !o)}
        className="text-[10px] font-mono flex items-center gap-1"
        style={{ color: 'hsl(var(--muted-foreground))', background: 'none', border: 'none', cursor: 'pointer', padding: 0 }}
      >
        <span style={{ opacity: 0.6 }}>{open ? '▾' : '▸'}</span>
        {!open && <span style={{ opacity: 0.6 }}>{firstKey}: {preview}</span>}
        {open && <span style={{ opacity: 0.6 }}>collapse</span>}
      </button>
      {open && (
        <pre
          className="mt-1 text-[10px] font-mono rounded p-2 overflow-x-auto"
          style={{
            background: 'hsl(var(--muted) / 0.4)',
            color: 'hsl(var(--muted-foreground))',
            maxHeight: '200px',
            overflowY: 'auto',
          }}
        >
          {JSON.stringify(input, null, 2)}
        </pre>
      )}
    </div>
  );
}

/** Renders a tool_use content block */
function ToolUseBlock({ block }) {
  const color = toolColor(block.name);
  return (
    <div
      className="rounded px-2 py-1.5 my-1"
      style={{ background: 'hsl(var(--muted) / 0.3)', borderLeft: `2px solid ${color}` }}
    >
      <div className="flex items-center gap-1.5">
        <span className="text-[11px] font-semibold font-mono" style={{ color }}>
          {block.name}
        </span>
      </div>
      <ToolInput input={block.input} />
    </div>
  );
}

/** Renders an assistant message (text + tool_use blocks) */
function AssistantCard({ msg }) {
  const content = msg.message?.content ?? [];

  return (
    <div className="flex flex-col gap-1 py-1">
      {content.map((block, i) => {
        if (block.type === 'text') {
          return (
            <p key={i} className="text-sm leading-relaxed whitespace-pre-wrap" style={{ color: 'hsl(var(--foreground))' }}>
              {block.text}
            </p>
          );
        }
        if (block.type === 'tool_use') {
          return <ToolUseBlock key={i} block={block} />;
        }
        return null;
      })}
    </div>
  );
}

/** Renders the result/completion message */
function ResultCard({ msg }) {
  const isError = msg.subtype !== 'success';
  const color = isError ? 'hsl(var(--destructive))' : 'hsl(var(--success, 142 60% 50%))';

  return (
    <div
      className="rounded px-3 py-2 text-xs font-mono flex items-center gap-3 flex-wrap"
      style={{ background: 'hsl(var(--muted) / 0.4)', borderLeft: `2px solid ${color}`, color }}
    >
      <span>{isError ? '✗ error' : '✓ done'}</span>
      {!isError && msg.num_turns != null && (
        <span style={{ color: 'hsl(var(--muted-foreground))' }}>{msg.num_turns} turn{msg.num_turns !== 1 ? 's' : ''}</span>
      )}
      {msg.duration_ms != null && (
        <span style={{ color: 'hsl(var(--muted-foreground))' }}>{formatMs(msg.duration_ms)}</span>
      )}
      {msg.total_cost_usd != null && (
        <span style={{ color: 'hsl(var(--muted-foreground))' }}>{formatCost(msg.total_cost_usd)}</span>
      )}
      {isError && msg.errors && (
        <span style={{ color: 'hsl(var(--destructive))' }}>{msg.errors.join('; ')}</span>
      )}
    </div>
  );
}

/** Renders a user message echo */
function UserCard({ msg }) {
  const text = typeof msg.message?.content === 'string'
    ? msg.message.content
    : msg.message?.content?.[0]?.text ?? '';

  if (!text || msg.isSynthetic) return null;

  return (
    <div className="flex justify-end py-1">
      <div
        className="rounded-lg px-3 py-2 text-sm max-w-[80%] whitespace-pre-wrap"
        style={{
          background: 'hsl(var(--accent) / 0.15)',
          color: 'hsl(var(--foreground))',
          border: '1px solid hsl(var(--accent) / 0.3)',
        }}
      >
        {text}
      </div>
    </div>
  );
}

/** Main message card dispatcher */
export default function MessageCard({ msg }) {
  // Skip noisy partial/streaming events
  if (msg.type === 'stream_event') return null;
  if (msg.type === 'tool_progress') return null;
  if (msg.type === 'tool_use_summary') return null;

  if (msg.type === 'system' && msg.subtype === 'init') {
    return (
      <div className="text-[10px] uppercase tracking-wider py-1 flex gap-3 flex-wrap"
        style={{ color: 'hsl(var(--muted-foreground))', opacity: 0.6 }}>
        <span>session {msg.session_id?.slice(0, 8)}</span>
        <span>{msg.model}</span>
        <span>{msg.permissionMode}</span>
      </div>
    );
  }

  if (msg.type === 'system' && msg.subtype === 'connected') {
    return (
      <div className="text-[10px] py-0.5" style={{ color: 'hsl(var(--muted-foreground))', opacity: 0.5 }}>
        reconnected · session {msg.sessionId?.slice(0, 8)}
      </div>
    );
  }

  if (msg.type === 'assistant') {
    return <AssistantCard msg={msg} />;
  }

  if (msg.type === 'user') {
    return <UserCard msg={msg} />;
  }

  if (msg.type === 'result') {
    return <ResultCard msg={msg} />;
  }

  if (msg.type === 'error') {
    return (
      <div className="text-xs rounded px-2 py-1.5 font-mono"
        style={{ background: 'hsl(var(--destructive) / 0.1)', color: 'hsl(var(--destructive))', borderLeft: '2px solid hsl(var(--destructive))' }}>
        {msg.message}
      </div>
    );
  }

  // Unhandled message types — render as collapsed JSON in dev
  return null;
}
