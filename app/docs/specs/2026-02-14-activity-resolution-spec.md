# Spec: Activity Resolution — File-to-Item Association

**Date:** 2026-02-14
**Status:** APPROVED
**Scope:** Connect agent tool use to tracked work items via file path matching
**Related:** [Integration Roadmap](../plans/2026-02-11-integration-roadmap.md), [Vision Tracker Design](../plans/2026-02-13-vision-tracker-design.md)

---

## What is this?

A structured system that maps file paths to Vision Tracker items, so when the agent edits a file, the tracker knows *which feature* is being worked on. No AI inference, no agent reasoning — pure data lookup against associations declared at plan time and derived from naming conventions.

---

## What are we building?

A three-layer association system:

1. **Plan-sourced file manifests** — Implementation plans already list files as `(new)` or `(existing)`. When a plan is linked to a feature item, those file paths populate the item's `files` field automatically.

2. **Convention-based artifact association** — Docs, specs, plans, and journal entries follow standardized naming (`docs/plans/YYYY-MM-DD-<slug>-plan.md`). Items associate with artifacts by slug matching against the item's title.

3. **Activity resolution** — When the agent touches a file, the server matches the path against all items' `files` arrays and broadcasts which item(s) are active. The sidebar shows "Working on: [Feature Name]."

**In scope:**
- `files` field on tracker items (array of path prefixes and exact paths)
- Plan parser that extracts file paths from implementation plan markdown
- Server-side path matching in the `/api/agent/activity` endpoint
- Sidebar display of resolved item context
- CLI support: `vision-track update <id> --files "path1,path2"`
- Convention matcher for doc artifacts

**Out of scope:**
- Git blame or commit history analysis
- AI-powered intent inference
- Automatic plan creation
- Bidirectional sync (item changes don't modify plans)
- File-level dependency tracking

---

## Data Model Changes

### Item schema: add `files` field

```json
{
  "id": "abc-123",
  "type": "feature",
  "title": "Agent Awareness",
  "files": [
    "src/components/Terminal.jsx",
    "server/terminal.js",
    "scripts/agent-activity-hook.sh",
    "src/components/vision/AppSidebar.jsx"
  ],
  "slug": "agent-awareness",
  ...existing fields...
}
```

**`files`** — Array of strings. Each entry is either:
- An exact file path relative to project root: `"server/terminal.js"`
- A directory prefix (trailing `/`): `"src/components/vision/"` — matches all files under that directory

**`slug`** — Derived from title: lowercase, spaces to hyphens, strip non-alphanumeric. Used for convention-based artifact matching. Generated on create, updated on title change. Not user-editable directly.

### Resolution rules

Given an incoming file path from the activity hook:

1. **Exact match**: `filePath === item.files[i]`
2. **Prefix match**: `filePath.startsWith(item.files[i])` where the entry ends with `/`
3. **Convention match**: For files in `docs/`, extract slug from filename, match against item slugs

All matches return. A file can belong to multiple items (e.g., `AppSidebar.jsx` belongs to both "Vision Tracker" and "Agent Awareness" if both list it).

### Priority

When multiple items match, display priority:
1. Items with status `in_progress` (most likely the active work)
2. Items with more specific paths (exact > prefix)
3. Most recently updated item

---

## Source 1: Plan-Sourced File Manifests

### How plans list files

Implementation plans follow the documentation standard of marking file paths as `(new)` or `(existing)`:

```markdown
### Files
- `src/components/Terminal.jsx` (existing) — Add agent status detection
- `scripts/agent-activity-hook.sh` (new) — PostToolUse hook for activity feed
- `server/vision-server.js` (existing) — Add /api/agent/activity endpoint
```

Alternate formats that must also parse:
```markdown
- **`src/components/Terminal.jsx`** (existing)
- `src/components/Terminal.jsx` — existing, add status detection
- Files: src/components/Terminal.jsx, server/terminal.js
```

### Extraction behavior

When a plan doc is written or updated (detected by the existing `vision-hook.sh` PostToolUse hook on Write|Edit):

1. Parse the markdown for file path patterns:
   - Lines containing backtick-wrapped paths: `` `path/to/file.ext` ``
   - Lines containing paths with common extensions: `.js`, `.jsx`, `.ts`, `.tsx`, `.mjs`, `.css`, `.json`, `.md`, `.sh`
   - Must look like relative paths (contain `/`, no `http`, not inside code blocks that are clearly code examples)

2. Filter out noise:
   - Skip paths inside code fence blocks (``` ``` ```) unless in a "Files" section
   - Skip paths that are clearly examples (contain `example`, `foo`, `bar`)
   - Skip node_modules, dist, .git paths

3. Find the linked tracker item:
   - Check if the plan doc already has a tracker item (vision-hook would have created one)
   - Check if the plan has a front-matter or heading linking to a feature item
   - If no link found, log and skip — don't guess

4. Update the linked item's `files` field:
   - Merge extracted paths with existing `files` (don't overwrite manual entries)
   - Deduplicate
   - Normalize to project-relative paths (strip leading `/`, `./`)

### When this runs

- Agent or hook calls `POST /api/plan/parse` after writing/updating a plan or spec doc
- Server-side Node.js parsing — proper string handling, can evolve to markdown AST
- Idempotent — re-parsing the same plan produces the same result

---

## Source 2: Convention-Based Artifact Association

### Naming conventions

| Directory | Pattern | Example |
|-----------|---------|---------|
| `docs/plans/` | `YYYY-MM-DD-<slug>-{roadmap,plan,design}.md` | `2026-02-14-agent-awareness-plan.md` |
| `docs/specs/` | `YYYY-MM-DD-<slug>-spec.md` | `2026-02-14-activity-resolution-spec.md` |
| `docs/journal/` | `YYYY-MM-DD-session-N-<slug>.md` | `2026-02-14-session-16-agent-awareness.md` |
| `docs/decisions/` | `YYYY-MM-DD-<slug>.md` | `2026-02-14-file-association-scheme.md` |
| `docs/evaluations/` | `YYYY-MM-DD-<slug>-eval.md` | `2026-02-14-agent-tracking-eval.md` |
| `docs/discovery/` | `<slug>.md` or subdirectories | `feature-map.md` |

### Slug matching

1. Extract slug from filename: strip date prefix, strip suffix (`-plan`, `-spec`, `-roadmap`, `-design`, `-eval`), strip `.md`
2. Match against item slugs (derived from title)
3. Fuzzy: `agent-awareness` matches item titled "Agent Awareness" (slug: `agent-awareness`)
4. Partial: `agent-awareness-plan` extracts `agent-awareness` after stripping `-plan` suffix

### When this runs

- At activity resolution time (when `/api/agent/activity` receives a file in `docs/`)
- No pre-computation needed — slug derivation is cheap string manipulation
- Falls back gracefully — if no slug match, the activity still shows the raw file path

---

## Source 3: Activity Resolution

### Server endpoint changes

The existing `POST /api/agent/activity` endpoint gains resolution logic:

```
Input:  {tool: "Edit", input: {file_path: "src/components/Terminal.jsx"}}
Output: broadcast {
  type: "agentActivity",
  tool: "Edit",
  detail: "Terminal.jsx",
  items: [
    {id: "abc-123", title: "Agent Awareness", status: "in_progress"}
  ],
  timestamp: "..."
}
```

### Resolution algorithm

```
resolve(filePath):
  matches = []
  normalizedPath = stripProjectRoot(filePath)

  for each item in store.items:
    if item.files exists:
      for each pattern in item.files:
        if pattern ends with '/':
          if normalizedPath.startsWith(pattern): matches.push(item)
        else:
          if normalizedPath === pattern: matches.push(item)

    if normalizedPath starts with 'docs/':
      slug = extractSlugFromFilename(normalizedPath)
      if slug && item.slug === slug: matches.push(item)

  deduplicate matches
  sort by: in_progress first, then specificity, then updatedAt
  return matches
```

### Performance

- Linear scan over items is fine — Vision Tracker has ~100-200 items
- Resolution runs once per hook call (once per tool use)
- No caching needed at this scale

---

## Sidebar Display

### Current state (already built)

The AppSidebar agent activity section shows:
- Status dot (working/idle)
- Category label (Reading, Writing, Running, etc.)
- Tool name
- Elapsed time
- Recent activity strip (proportional bars)
- Hook-sourced activity feed (last 4 tool uses with filenames)

### New: Item context

When activity resolves to one or more items, show below the activity feed:

```
┌─────────────────────────────────────┐
│ ● WRITING Edit  AppSidebar.jsx  3s  │
│ ▃▅▇█                                │
│ Grep  agentActivity                  │
│ Read  VisionTracker.jsx              │
│ Edit  AppSidebar.jsx                 │
│                                      │
│ Working on                           │
│  ◆ Agent Awareness          ▓▓▓░ 3/4│
│  ◇ Vision Tracker                    │
└─────────────────────────────────────┘
```

- **"Working on"** header appears only when items are resolved
- Primary item (in_progress) gets a filled diamond ◆ and optional progress
- Secondary items get an outlined diamond ◇
- Clicking an item name navigates to it (selects it, switches to roadmap view if needed)
- Items fade out 30 seconds after the last matching activity

---

## CLI Changes

### `vision-track update <id> --files`

```bash
# Set files (replaces existing)
node scripts/vision-track.mjs update abc-123 --files "src/components/Terminal.jsx,server/terminal.js"

# Add to existing files
node scripts/vision-track.mjs update abc-123 --add-files "scripts/agent-activity-hook.sh"

# Clear files
node scripts/vision-track.mjs update abc-123 --files ""
```

### `vision-track show <id>`

Add `files` to the item display:
```
Agent Awareness (feature, in_progress, phase: implementation)
  Files: src/components/Terminal.jsx, server/terminal.js, scripts/agent-activity-hook.sh
  Connections: 3 informs, 1 blocks
```

---

## What NOT to build

- **No automatic plan generation** — Plans are written by humans/agents. This system reads them, doesn't create them.
- **No git integration** — No parsing commit messages, blame, or diff history. That's a separate feature (Phase 4).
- **No file watching** — We don't watch files for changes. The hook fires on tool use, which is sufficient.
- **No reverse navigation** — "Show me all files for this item" is useful but out of scope for v1. The CLI `show` command covers it.
- **No enforcement** — Items without `files` work fine. The system degrades gracefully.
- **No glob patterns** — Only exact paths and directory prefixes. Globs add complexity without proportional value at our scale.

---

## Success Criteria

1. Agent edits `src/components/Terminal.jsx` → sidebar shows "Working on: Agent Awareness" within 1 second
2. Agent writes a new plan doc → file paths from the plan auto-populate the linked item's `files` field
3. Agent edits `docs/specs/2026-02-14-activity-resolution-spec.md` → sidebar associates with "Activity Resolution" item by slug match
4. Items without `files` field work exactly as before — no regressions
5. `vision-track update <id> --files` works from CLI
6. Multiple items can match the same file — all are displayed
7. Resolution handles 200 items in <10ms

---

## Design Decisions

- [x] **D1: Files as flat array, not glob patterns** — Exact paths and directory prefixes are sufficient at our scale (~200 items). Avoids glob library dependency. Can upgrade later if needed.
- [x] **D2: Slug derived from title, not a separate field** — `slugify(title)` runs on create/update. No manual slug entry. Keeps the data model simpler but means title changes affect matching.
- [x] **D3: Plan parser as a server endpoint, not in the hook** — Shell-based markdown parsing is fragile. `POST /api/plan/parse` does parsing in Node.js with proper string handling. Hook or agent calls it after writing a plan doc.
- [x] **D4: Activity resolution is server-side, not client-side** — The server has the items in memory. Doing resolution there means the broadcast already includes resolved items — no client-side scanning needed. The client is a dumb display.
- [x] **D5: Convention matching at resolution time, not at item creation** — Don't pre-compute artifact associations. Derive them when a docs/ file is touched. Simpler, no stale mappings.
- [x] **D6: Resolved items fade after 30 seconds of inactivity** — Prevents stale "Working on" display when the agent moves to unrelated work. 30 seconds accommodates normal thinking gaps between edits. The timeout is client-side, not server-side.
- [x] **D7: Auto-status progression on Write/Edit only** — When the agent first writes/edits a file belonging to a `planned` item, auto-bump it to `in_progress`. Read/Grep/Glob don't trigger progression — reading is research, writing is work.

---

## Implementation Order

1. **Schema**: Add `files` and `slug` to item creation/update in `vision-store.js`
2. **CLI**: Add `--files` and `--add-files` flags to `vision-track.mjs update`
3. **Resolution**: Add path matching logic to `/api/agent/activity` endpoint
4. **Auto-status**: On Write/Edit resolution, bump matched `planned` items to `in_progress`
5. **Sidebar**: Display resolved items in AppSidebar with 30s fade
6. **Plan parser**: `POST /api/plan/parse` endpoint to extract file paths from plan docs
7. **Convention matcher**: Add slug derivation and matching to resolution
