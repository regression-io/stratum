# Implementation Plan: Activity Resolution

**Date:** 2026-02-14
**Spec:** [Activity Resolution Spec](../specs/2026-02-14-activity-resolution-spec.md)
**Status:** IN_PROGRESS

---

## Overview

7 steps, 5 files modified, 0 new files. Each step is independently verifiable.

---

## Step 1: Schema — Add `files` and `slug` to VisionStore

**File:** `server/vision-store.js` (existing)

**Changes:**

1. Add `files` to the allowed update fields array (line 112):
   ```javascript
   const allowed = ['type', 'title', 'description', 'confidence', 'status', 'phase', 'position', 'parentId', 'summary', 'files'];
   ```

2. In `createItem()`, accept `files` parameter and generate `slug`:
   ```javascript
   createItem({ type, title, description = '', confidence = 0, status = 'planned', phase, position, parentId, files }) {
     ...
     const item = {
       ...existing fields...
       files: Array.isArray(files) ? files : [],
       slug: slugify(title),
     };
   ```

3. In `updateItem()`, regenerate slug when title changes:
   ```javascript
   if (updates.title !== undefined) {
     item.slug = slugify(updates.title);
   }
   if (updates.files !== undefined) {
     item.files = Array.isArray(updates.files) ? updates.files : [];
   }
   ```

4. Add `slugify()` function at module level:
   ```javascript
   function slugify(title) {
     return title.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
   }
   ```

**Verify:** `node --check server/vision-store.js` passes. Existing items without `files`/`slug` still load (fields are optional, default `[]`/derived).

---

## Step 2: CLI — Add `--files` and `--add-files` flags

**File:** `scripts/vision-track.mjs` (existing)

**Changes:**

1. In `updateItem()`, add handling for `--files` and `--add-files` flags **before** the empty-check guard (`if (Object.keys(updates).length === 0)`):
   ```javascript
   if (parsed.flags.files !== undefined) {
     updates.files = parsed.flags.files ? parsed.flags.files.split(',').map(f => f.trim()) : [];
   }
   if (parsed.flags['add-files']) {
     // Fetch current item first, merge
     const current = await fetch(`${API}/items/${id}`).then(r => r.json());
     const existing = current.files || [];
     const adding = parsed.flags['add-files'].split(',').map(f => f.trim());
     updates.files = [...new Set([...existing, ...adding])];
   }
   ```

2. In the `show` command output (if it exists) or `search` result formatting, display `files` when present.

**Verify:** `node scripts/vision-track.mjs update <test-id> --files "src/foo.js,server/bar.js"` succeeds. `--add-files` merges correctly.

---

## Step 3: Resolution — Path matching in `/api/agent/activity`

**File:** `server/vision-server.js` (existing)

**Changes:**

1. Add a `resolveItems(filePath)` method to `VisionServer` (class method, not inside `attach()`):
   ```javascript
   resolveItems(filePath) {
     // Normalize absolute path to project-relative using PROJECT_ROOT
     const rel = filePath.startsWith(PROJECT_ROOT)
       ? filePath.slice(PROJECT_ROOT.length + 1)
       : filePath.replace(/^\.\//, '');
     const matches = [];
     const matchType = new Map(); // track exact vs prefix for specificity sort

     for (const item of this.store.items.values()) {
       // File match
       if (item.files && item.files.length > 0) {
         for (const pattern of item.files) {
           if (pattern.endsWith('/')) {
             if (rel.startsWith(pattern)) { matches.push(item); matchType.set(item.id, 'prefix'); break; }
           } else {
             if (rel === pattern) { matches.push(item); matchType.set(item.id, 'exact'); break; }
           }
         }
       }

       // Convention match for docs/
       if (rel.startsWith('docs/') && item.slug) {
         const slug = this.extractSlugFromPath(rel);
         if (slug && slug === item.slug) {
           if (!matches.includes(item)) {
             matches.push(item);
             matchType.set(item.id, 'slug');
           }
         }
       }
     }

     // Sort: in_progress first, then exact > prefix > slug, then by updatedAt
     const specificity = { exact: 0, prefix: 1, slug: 2 };
     matches.sort((a, b) => {
       if (a.status === 'in_progress' && b.status !== 'in_progress') return -1;
       if (b.status === 'in_progress' && a.status !== 'in_progress') return 1;
       const sa = specificity[matchType.get(a.id)] ?? 3;
       const sb = specificity[matchType.get(b.id)] ?? 3;
       if (sa !== sb) return sa - sb;
       return new Date(b.updatedAt) - new Date(a.updatedAt);
     });

     return matches;
   }
   ```

2. Add `extractSlugFromPath(filePath)` method:
   ```javascript
   extractSlugFromPath(filePath) {
     const filename = filePath.split('/').pop().replace(/\.md$/, '');
     // Strip date prefix: YYYY-MM-DD-
     const noDate = filename.replace(/^\d{4}-\d{2}-\d{2}-/, '');
     // Strip known suffixes
     const noSuffix = noDate.replace(/-(roadmap|plan|design|spec|eval|review)$/, '');
     return noSuffix || null;
   }
   ```

3. Modify the `POST /api/agent/activity` handler to call resolution:
   ```javascript
   app.post('/api/agent/activity', (req, res) => {
     const { tool, input, timestamp } = req.body || {};
     if (!tool) return res.status(400).json({ error: 'tool is required' });

     let detail = null;
     let filePath = null;
     if (input) {
       filePath = input.file_path || null;
       detail = filePath || input.command || input.pattern || input.query || input.url || input.prompt || null;
       if (detail && detail.length > 120) detail = detail.slice(0, 117) + '...';
     }

     // Resolve file to tracker items
     const items = filePath ? this.resolveItems(filePath) : [];

     this.broadcastMessage({
       type: 'agentActivity',
       tool,
       detail,
       items: items.map(i => ({ id: i.id, title: i.title, status: i.status })),
       timestamp: timestamp || new Date().toISOString(),
     });

     res.json({ ok: true });
   });
   ```

**Verify:** `curl -X POST localhost:3001/api/agent/activity -H 'Content-Type: application/json' -d '{"tool":"Edit","input":{"file_path":"src/components/Terminal.jsx"}}'` returns `{"ok":true}` and the broadcast includes matched items.

---

## Step 4: Auto-status — Write/Edit bumps `planned` → `in_progress`

**File:** `server/vision-server.js` (existing, same endpoint as Step 3)

**Changes:**

Inside the `/api/agent/activity` handler, after resolution, add auto-progression:

```javascript
// Auto-status: Write/Edit on planned items → in_progress
if (['Write', 'Edit'].includes(tool) && filePath) {
  for (const item of items) {
    if (item.status === 'planned') {
      try {
        this.store.updateItem(item.id, { status: 'in_progress' });
        this.scheduleBroadcast(); // broadcast updated state
      } catch { /* ignore */ }
    }
  }
}
```

**Verify:** Create a test item with `--files "src/test.js"` and status `planned`. POST an Edit activity for `src/test.js`. Item status should change to `in_progress`.

---

## Step 5: Sidebar — Display resolved items with 30s fade

**Files:** `src/components/vision/useVisionStore.js` (existing) + `src/components/vision/AppSidebar.jsx` (existing)

**Changes to `useVisionStore.js`:**

1. Update the `agentActivity` message handler to also capture `items`:
   ```javascript
   } else if (msg.type === 'agentActivity') {
     setAgentActivity(prev => {
       const next = [...prev, { tool: msg.tool, detail: msg.detail, items: msg.items || [], timestamp: msg.timestamp }];
       return next.length > 20 ? next.slice(-20) : next;
     });
   }
   ```

**Changes to `AppSidebar.jsx`:**

1. Track resolved items in state with last-seen timestamp:
   ```javascript
   const [resolvedItems, setResolvedItems] = React.useState([]);
   const [resolvedAt, setResolvedAt] = React.useState(0);
   ```

2. Extract resolved items from `agentActivity` prop. When entries have items, update state:

4. Add a 30s fade effect: use a `useEffect` that clears resolved items 30 seconds after the last update.

5. Render the "Working on" section:
   ```jsx
   {resolvedItems.length > 0 && (
     <div className="mt-1.5">
       <p className="text-[10px] font-medium uppercase tracking-wider mb-0.5"
          style={{ color: 'var(--ink-tertiary, var(--color-text-tertiary))' }}>
         Working on
       </p>
       {resolvedItems.map(item => (
         <button key={item.id}
           className="flex items-center gap-1 text-[10px] w-full text-left rounded px-1 py-0.5 hover:bg-sidebar-accent/50"
           style={{ color: 'var(--color-text-secondary)' }}
           onClick={() => { /* navigate to item */ }}>
           <span>{item.status === 'in_progress' ? '◆' : '◇'}</span>
           <span className="truncate">{item.title}</span>
         </button>
       ))}
     </div>
   )}
   ```

**Verify:** Edit a file associated with an item → "Working on: [Item Name]" appears in sidebar. Stop editing → fades after 30s.

---

## Step 6: Plan parser — `POST /api/plan/parse` endpoint

**File:** `server/vision-server.js` (existing)

**Changes:**

First, add `import fs from 'node:fs';` to the file's imports (not currently imported).

Add a new endpoint that parses a plan/spec markdown file for file paths:

```javascript
app.post('/api/plan/parse', (req, res) => {
  const { filePath, itemId } = req.body || {};
  if (!filePath) return res.status(400).json({ error: 'filePath required' });

  // Read the file
  const fullPath = path.resolve(PROJECT_ROOT, filePath);
  let content;
  try {
    content = fs.readFileSync(fullPath, 'utf-8');
  } catch (err) {
    return res.status(404).json({ error: `File not found: ${filePath}` });
  }

  // Extract file paths from markdown
  const extracted = this.extractFilePaths(content);

  // If itemId provided, update the item's files
  if (itemId) {
    const item = this.store.items.get(itemId);
    if (item) {
      const existing = item.files || [];
      const merged = [...new Set([...existing, ...extracted])];
      this.store.updateItem(itemId, { files: merged });
      this.scheduleBroadcast();
    }
  }

  res.json({ files: extracted, itemId: itemId || null });
});
```

Add `extractFilePaths(markdown)` method (class method on `VisionServer`):

**Note:** Spec says "skip code fences unless in a Files section." We simplify to skip all code fences — safer default, avoids false positives from code examples. Documented deviation.

```javascript
extractFilePaths(markdown) {
  const paths = new Set();
  const lines = markdown.split('\n');
  const extRe = /\.(jsx?|tsx?|mjs|css|json|md|sh|py)$/;
  const skipRe = /node_modules|dist\/|\.git\/|example|foo|bar/;

  let inCodeFence = false;
  for (const line of lines) {
    if (line.trim().startsWith('```')) { inCodeFence = !inCodeFence; continue; }
    if (inCodeFence) continue;

    // Match backtick-wrapped paths
    const backtickMatches = line.matchAll(/`([^`]+)`/g);
    for (const m of backtickMatches) {
      const p = m[1].replace(/^\*\*|\*\*$/g, '').trim();
      if (p.includes('/') && extRe.test(p) && !skipRe.test(p)) {
        paths.add(p.replace(/^\.\//, ''));
      }
    }

    // Match bare paths with (new)/(existing) markers
    const markerMatch = line.match(/[-*]\s+`?([^\s`]+)`?\s+\((?:new|existing)\)/);
    if (markerMatch) {
      const p = markerMatch[1].replace(/^\*\*|\*\*$/g, '').trim();
      if (p.includes('/') && !skipRe.test(p)) {
        paths.add(p.replace(/^\.\//, ''));
      }
    }
  }

  return Array.from(paths);
}
```

**Verify:** `curl -X POST localhost:3001/api/plan/parse -H 'Content-Type: application/json' -d '{"filePath":"docs/plans/2026-02-14-activity-resolution-plan.md"}'` returns the file paths listed in this plan.

---

## Step 7: Convention matcher — Slug derivation in resolution

**File:** `server/vision-server.js` (existing, already added in Step 3)

The `extractSlugFromPath()` and slug matching in `resolveItems()` from Step 3 already implement this. Step 7 is verifying it works end-to-end:

**Verify:** `curl -X POST localhost:3001/api/agent/activity -H 'Content-Type: application/json' -d '{"tool":"Edit","input":{"file_path":"docs/specs/2026-02-14-activity-resolution-spec.md"}}'` — should resolve to the "Activity Resolution" item via slug match.

---

## File Summary

| File | Steps | Change type |
|------|-------|-------------|
| `server/vision-store.js` (existing) | 1 | Add `files`, `slug`, `slugify()` |
| `scripts/vision-track.mjs` (existing) | 2 | Add `--files`, `--add-files` flags |
| `server/vision-server.js` (existing) | 3, 4, 6, 7 | Resolution, auto-status, plan parser |
| `src/components/vision/AppSidebar.jsx` (existing) | 5 | "Working on" display, 30s fade |
| `src/components/vision/useVisionStore.js` (existing) | 5 | Pass `items` from agentActivity events |

---

## Verification Checklist

- [ ] Existing items without `files`/`slug` still work (backward compat)
- [ ] `vision-track update <id> --files "path1,path2"` sets files
- [ ] `vision-track update <id> --add-files "path3"` merges
- [ ] Edit a file → sidebar shows "Working on: [matched item]"
- [ ] Write/Edit a file for a `planned` item → auto-bumps to `in_progress`
- [ ] Edit a docs/ file → slug-matched item resolves
- [ ] POST `/api/plan/parse` extracts file paths from plan markdown
- [ ] Resolved items fade from sidebar after 30s of no matching activity
- [ ] `npm run build` passes
- [ ] No regressions in existing Vision Tracker views
