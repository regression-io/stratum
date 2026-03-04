# Plan: Markdown-in-Folders Persistence Connector

**Date:** 2026-02-11
**Status:** PLANNED
**Blocks:** Everything — Forge can't self-host without persistence
**Related:** [Integration Roadmap](2026-02-11-integration-roadmap.md), [Connectors](../connectors.md)

---

## Why Markdown in Folders

- **Human-readable** — work items are readable/editable without Forge running
- **Git-friendly** — version control for free, diffs are meaningful, history is built in
- **Portable** — copy a folder, you've backed up the project
- **Cross-linkable** — relative paths between markdown files are natural
- **No runtime dependency** — no database server, no SDK, no binary
- **Dogfood alignment** — we're already doing this manually (this repo's docs/ folder). The persistence connector formalizes what we're already doing.

---

## Folder Structure

```
.forge/
├── work/
│   ├── {id}.md                 # One file per Work item
│   └── ...
├── projects/
│   └── {id}.md                 # One file per Project
├── templates/
│   ├── decision.md             # Work item templates
│   ├── evaluation.md
│   ├── brainstorm.md
│   └── ...
└── index.json                  # Computed index for fast queries
```

Dependencies live inside Work item files (frontmatter), not as separate files. Keeps related data together.

---

## Work Item File Format

```markdown
---
id: "w-001"
name: "Rich Artifact Editor"
status: "planned"
parent_id: "w-phase1"
position: 1
phase: "implementation"
type: "task"
labels: ["ui", "editor"]
tags: []
project_id: "proj-forge"
created_at: "2026-02-11T00:00:00Z"
updated_at: "2026-02-11T00:00:00Z"

scope: []

acceptance_criteria:
  - description: "Can write markdown directly in work item detail view"
    verifiable: true
    satisfied: false
  - description: "Can toggle between edit and preview"
    verifiable: true
    satisfied: false

dependencies:
  - type: "blocks"
    target: "w-002"
  - type: "informs"
    target: "w-003"

artifacts:
  - name: "Design Notes"
    type: "document"
    file: "./artifacts/w-001-design-notes.md"
  - name: "Reference Link"
    type: "link"
    url: "https://example.com/markdown-editors"
---

## Description

The Base44 UI has artifacts as attachments only. We need inline markdown editing —
living documents created and edited inside Forge.

## Evidence

<!-- Populated by connectors: git commits, test results, session transcripts -->

## History

- 2026-02-11: Created during bootstrap planning session
```

---

## Index File

`index.json` is a computed cache — rebuilt from the markdown files on startup, updated incrementally on changes. Never the source of truth, always derivable.

```json
{
  "work": {
    "w-001": {
      "name": "Rich Artifact Editor",
      "status": "planned",
      "parent_id": "w-phase1",
      "phase": "implementation",
      "type": "task",
      "labels": ["ui", "editor"],
      "project_id": "proj-forge",
      "updated_at": "2026-02-11T00:00:00Z"
    }
  },
  "hierarchy": {
    "w-phase1": ["w-001", "w-002", "w-003"]
  },
  "dependencies": {
    "blocks": [["w-001", "w-002"]],
    "informs": [["w-001", "w-003"]]
  },
  "rebuilt_at": "2026-02-11T12:00:00Z"
}
```

**Why an index:** Markdown files are great for reading individual items but slow for queries across hundreds of items (filter by status, find all children, traverse dependencies). The index makes queries fast. If the index is missing or stale, rebuild it by scanning the markdown files.

---

## API Interface

The persistence connector exposes these operations. The UI calls these instead of the Base44 SDK.

```
// Work items
list(filters?, sort?, limit?)    → Work[]
get(id)                          → Work
create(data)                     → Work       // creates .md file + updates index
update(id, data)                 → Work       // updates .md file + updates index
delete(id)                       → void       // removes .md file + updates index

// Dependencies (embedded in work items, but need cross-item operations)
addDependency(from_id, to_id, type)
removeDependency(from_id, to_id)
getDependenciesFor(id)           → Dependency[]

// Projects
listProjects()                   → Project[]
createProject(data)              → Project
updateProject(id, data)          → Project
deleteProject(id)                → void

// Artifacts (files linked from work items)
createArtifact(work_id, data)    → Artifact   // creates artifact file + updates work item
updateArtifact(work_id, artifact_id, data)
deleteArtifact(work_id, artifact_id)

// Index
rebuildIndex()                   → void
```

---

## Integration with Base44 UI

The Base44 code calls `base44.entities.Work.list()`, `.create()`, `.update()`, `.delete()`. The swap:

1. Create a module that implements the same call signature as `base44.entities`
2. Point it at the `.forge/` folder instead of the Base44 API
3. Replace the import in `src/api/base44Client.js`
4. Remove Base44 auth (not needed for local files)

The React Query layer above stays unchanged — it doesn't care where the data comes from.

---

## Cross-Linking

Work items link to each other via `dependencies` in frontmatter (by ID).
Artifacts link to files via relative paths (`./artifacts/...`).
Artifact cross-references use Work item IDs: `See [Decision: Deterministic UI](../work/w-decision-ui.md)`.

When rendering in the UI, IDs resolve to names via the index. When reading the raw markdown, the file path is human-navigable.

---

## Git Integration (free)

Because the persistence layer is markdown files:
- Every change is a file change → git tracks it automatically
- `git log .forge/work/w-001.md` shows the full history of a work item
- `git diff` shows what changed in a session
- Branching a project branches the work items too
- Merging a project merges the work items (with conflict resolution)

This is artifact versioning for free, without building it.

---

## Open Questions

- **File naming:** Use IDs (`w-001.md`) or slugs (`rich-artifact-editor.md`)? IDs are stable but opaque. Slugs are readable but break on rename.
- **Artifact storage:** Inline in the work item markdown body, or separate files in `./artifacts/`? Inline is simpler for short content. Separate files are better for large docs.
- **Concurrent access:** If two UI tabs or agent sessions modify the same work item, who wins? File locking? Last-write-wins? Merge?
- **Performance:** At what scale does scanning markdown files become too slow even with an index? (Probably hundreds, not thousands — fine for self-hosting.)
- **Watch mode:** Should the connector watch the filesystem for external changes (e.g., someone edits a .md file in their editor)? Useful for the manual-to-Forge transition.
