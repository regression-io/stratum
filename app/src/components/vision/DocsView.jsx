import React, { useState, useEffect, useMemo } from 'react';
import { ChevronRight, ChevronDown, FileText, ExternalLink, CircleDot } from 'lucide-react';
import { ScrollArea } from '@/components/ui/scroll-area.jsx';

/*
 * DocsView — browse all docs/ files, see which are tracked on the board vs orphaned.
 * Groups by directory. Click to open in canvas. Shows linked board item if any.
 */

function groupByDirectory(files) {
  const groups = new Map();
  for (const file of files) {
    const parts = file.split('/');
    // Group key: first two segments (e.g. "docs/discovery") or just "docs" for top-level
    const dir = parts.length > 2 ? parts.slice(0, 2).join('/') : parts[0];
    if (!groups.has(dir)) groups.set(dir, []);
    groups.get(dir).push(file);
  }
  return groups;
}

function dirLabel(dir) {
  const name = dir.replace('docs/', '').replace('docs', '');
  if (!name) return 'Top-level';
  return name.charAt(0).toUpperCase() + name.slice(1);
}

function fileName(path) {
  return path.split('/').pop();
}

function DocGroup({ dir, files, trackedPaths, onOpenFile }) {
  const [open, setOpen] = useState(true);
  const orphanCount = files.filter(f => !trackedPaths.has(f)).length;

  return (
    <div className="mb-1">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1.5 w-full px-3 py-1.5 text-left hover:bg-muted/30 transition-colors"
      >
        {open
          ? <ChevronDown className="h-3 w-3 shrink-0 text-muted-foreground" />
          : <ChevronRight className="h-3 w-3 shrink-0 text-muted-foreground" />
        }
        <span className="text-xs font-medium text-foreground">{dirLabel(dir)}</span>
        <span className="text-[10px] text-muted-foreground ml-auto tabular-nums">
          {files.length}
        </span>
        {orphanCount > 0 && (
          <span className="text-[10px] px-1 py-0.5 rounded"
            style={{ color: 'var(--color-warning, hsl(var(--accent)))', background: 'var(--color-warning, hsl(var(--accent))) / 0.1)' }}>
            {orphanCount} untracked
          </span>
        )}
      </button>
      {open && (
        <div className="ml-3">
          {files.map(file => {
            const tracked = trackedPaths.has(file);
            return (
              <button
                key={file}
                onClick={() => onOpenFile(file)}
                className="flex items-center gap-2 w-full px-3 py-1 text-left hover:bg-muted/30 transition-colors group"
              >
                <FileText className="h-3 w-3 shrink-0" style={{ color: tracked ? 'var(--color-success, hsl(var(--primary)))' : 'var(--color-text-tertiary, hsl(var(--muted-foreground)))' }} />
                <span className="text-xs truncate" style={{ color: tracked ? 'hsl(var(--foreground))' : 'hsl(var(--muted-foreground))' }}>
                  {fileName(file)}
                </span>
                {tracked && (
                  <CircleDot className="h-2.5 w-2.5 shrink-0 ml-auto" style={{ color: 'var(--color-success, hsl(var(--primary)))' }} />
                )}
                <ExternalLink className="h-3 w-3 shrink-0 opacity-0 group-hover:opacity-50 ml-auto" />
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

export default function DocsView({ items }) {
  const [files, setFiles] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch('/api/files')
      .then(r => r.json())
      .then(data => { setFiles(data.files || []); setLoading(false); })
      .catch(() => setLoading(false));
  }, []);

  // Build set of doc paths that are referenced by any board item (in description or title)
  const trackedPaths = useMemo(() => {
    const paths = new Set();
    for (const item of items) {
      const text = `${item.title || ''} ${item.description || ''} ${item.planLink || ''}`.toLowerCase();
      for (const file of files) {
        if (text.includes(file.toLowerCase()) || text.includes(fileName(file).replace('.md', '').toLowerCase())) {
          paths.add(file);
        }
      }
    }
    return paths;
  }, [items, files]);

  const groups = useMemo(() => groupByDirectory(files), [files]);

  const totalOrphans = files.filter(f => !trackedPaths.has(f)).length;

  const openInCanvas = (path) => {
    fetch('/api/canvas/open', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path }),
    }).catch(() => {});
  };

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <span className="text-sm text-muted-foreground">Loading docs...</span>
      </div>
    );
  }

  return (
    <div className="flex-1 flex flex-col min-h-0">
      {/* Header */}
      <div className="px-4 py-2 shrink-0" style={{ borderBottom: '1px solid hsl(var(--border))' }}>
        <div className="flex items-center justify-between">
          <span className="text-xs font-medium text-foreground">{files.length} docs</span>
          <span className="text-[10px] text-muted-foreground">
            {totalOrphans} untracked
          </span>
        </div>
      </div>

      {/* File list */}
      <ScrollArea className="flex-1">
        <div className="py-1">
          {[...groups.entries()].map(([dir, dirFiles]) => (
            <DocGroup
              key={dir}
              dir={dir}
              files={dirFiles}
              trackedPaths={trackedPaths}
              onOpenFile={openInCanvas}
            />
          ))}
        </div>
      </ScrollArea>
    </div>
  );
}
