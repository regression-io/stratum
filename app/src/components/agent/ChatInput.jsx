import React, { useRef, useEffect } from 'react';

/**
 * ChatInput — single-line text input with Enter-to-send.
 *
 * Shift+Enter inserts a newline (auto-grows to multiline).
 * Enter sends the message if not blank.
 * Disabled while the agent is processing to prevent message queuing confusion.
 */
export default function ChatInput({ onSend, disabled = false, placeholder = 'Message Claude…' }) {
  const ref = useRef(null);

  // Auto-focus when not disabled
  useEffect(() => {
    if (!disabled && ref.current) {
      ref.current.focus();
    }
  }, [disabled]);

  // Auto-resize textarea to content
  function resize() {
    const el = ref.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
  }

  function handleKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  }

  function submit() {
    const el = ref.current;
    if (!el) return;
    const text = el.value.trim();
    if (!text) return;
    onSend(text);
    el.value = '';
    resize();
  }

  return (
    <div
      className="flex items-end gap-2 px-3 py-2"
      style={{ borderTop: '1px solid hsl(var(--border))' }}
    >
      <textarea
        ref={ref}
        rows={1}
        disabled={disabled}
        placeholder={placeholder}
        onKeyDown={handleKeyDown}
        onInput={resize}
        className="flex-1 resize-none bg-transparent text-sm outline-none font-mono leading-relaxed"
        style={{
          color: 'hsl(var(--foreground))',
          caretColor: 'hsl(var(--accent))',
          maxHeight: '160px',
          overflowY: 'auto',
          opacity: disabled ? 0.4 : 1,
          transition: 'opacity 0.15s',
        }}
      />
      <button
        onClick={submit}
        disabled={disabled}
        title="Send (Enter)"
        className="shrink-0 rounded px-2 py-1 text-xs font-mono"
        style={{
          background: 'hsl(var(--accent) / 0.15)',
          color: 'hsl(var(--accent))',
          border: '1px solid hsl(var(--accent) / 0.3)',
          cursor: disabled ? 'not-allowed' : 'pointer',
          opacity: disabled ? 0.4 : 1,
          transition: 'opacity 0.15s',
        }}
      >
        ↵
      </button>
    </div>
  );
}
