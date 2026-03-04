/**
 * Shared confidence indicator — 4 dots showing 0-4 confidence level.
 * Size prop controls dot diameter (default 4px for inline use).
 */
export default function ConfidenceDots({ level, size = 4 }) {
  return (
    <div className="flex items-center gap-px">
      {[0, 1, 2, 3].map(i => (
        <div
          key={i}
          className="rounded-full"
          style={{
            width: size,
            height: size,
            background: i < level
              ? (level >= 3 ? 'hsl(var(--success))' : level >= 2 ? 'hsl(var(--accent))' : 'hsl(var(--destructive))')
              : 'transparent',
            border: `1px solid ${
              i < level
                ? (level >= 3 ? 'hsl(var(--success))' : level >= 2 ? 'hsl(var(--accent))' : 'hsl(var(--destructive))')
                : 'hsl(var(--border))'
            }`,
          }}
        />
      ))}
    </div>
  );
}
