# Compose: UI Development Brief

**Date:** 2026-02-11
**Audience:** UI development team
**Scope:** Phase 1 — Visual Planning Layer
**Supporting docs:** [PRD.md](./PRD.md), [brainstorm.md](./brainstorm.md), [use-cases.md](./use-cases.md)

---

## What is Compose?

Compose is a mission control system for AI-driven software development. It gives a developer a visual dashboard to plan, track, and eventually direct AI coding agents across projects of any scale.

Think of it as: **a project management tool where the workers are AI agents**. The developer is the flight director. The dashboard is mission control.

## What are we building in Phase 1?

Phase 1 is the **visual planning layer only**. No AI agent integration, no real-time monitoring, no policy enforcement. Just the ability to:

- See the big picture of a project at a glance
- Create and organize work into a nested hierarchy
- Track status and dependencies
- Attach documents/artifacts to work items
- View a dependency graph
- Work across multiple projects/repos

Phase 1 replaces: scattered markdown files, mental models, and manual status tracking.

---

## Core Data Model

The data model is designed for the full product (4 phases). Phase 1 only exposes **Work** in the UI, but the schema must include all three entities from day one. Do not omit Policy or Session from the schema — they will be activated in later phases without schema changes.

### Entity: Work

A thing that needs to get done. Hierarchical — can contain other Work items to any depth.

```
Work {
  id              unique identifier
  parent_id       nullable (null = top-level)
  position        ordering among siblings

  name            string, required
  description     rich text, optional
  labels          list of strings (user-defined: "initiative", "feature", "task", etc.)
  tags            list of strings (free-form)

  status          enum: planned | ready | in_progress | review | complete | blocked | parked

  scope           list of file/directory/project patterns (e.g., "smart-memory-service/**")
  acceptance_criteria   list of { description: string, verifiable: bool, satisfied: bool }

  artifacts       list of { name, type, url_or_path, content }
  evidence        list of { type, content, timestamp, session_id }

  project_id      which registered project this belongs to (nullable = cross-project)

  created_at      timestamp
  updated_at      timestamp
}
```

### Entity: Dependency

A directed relationship between two Work items.

```
Dependency {
  id
  blocker_id      the Work item that must complete first
  blocked_id      the Work item that cannot start until blocker completes
  type            enum: blocks | relates_to | informs
}
```

### Entity: Project

A registered repository or codebase.

```
Project {
  id
  name            display name
  path            local filesystem path
  repo_url        optional git remote URL
  default_labels  default label set for new Work items
}
```

### Entity: Policy (Phase 2+ — include in schema, not in UI)

```
Policy {
  id
  work_id         the Work item this policy is attached to
  trigger         enum: on_start | on_complete | on_scope_cross | on_decompose | on_assign | on_budget
  mode            enum: gate | flag | skip
  criteria        string (natural language or executable command)
  inherited       bool (true if cascaded from parent, false if set directly)
}
```

### Entity: Session (Phase 2+ — include in schema, not in UI)

```
Session {
  id
  name            display name
  type            enum: human | claude_code | other
  status          enum: active | idle | disconnected
  current_work_id nullable (what this session is working on)
  started_at      timestamp
  last_active_at  timestamp
}
```

---

## Phase 1 UI Views

### View 1: Project Dashboard (home)

The first thing the user sees. Answers "where are we?" in under 10 seconds.

**Layout:**
- Left sidebar: registered projects, global filters
- Main area: work hierarchy as a tree/outline view
- Each node shows: name, label badge, status indicator (color), progress (% children complete), dependency count

**Interactions:**
- Expand/collapse hierarchy levels
- Filter by: status, label, project, tag
- Group by: project, label, status
- Click a work item → opens detail panel
- Quick-add work item at any level (inline)

**Status colors:**
- `planned` — gray
- `ready` — blue
- `in_progress` — yellow
- `review` — purple
- `complete` — green
- `blocked` — red
- `parked` — muted/dimmed

### View 2: Work Item Detail

Full view of a single work item. Slide-out panel or dedicated page.

**Sections:**

**Header:** Name (editable inline), label badges, status dropdown, parent breadcrumb

**Description:** Rich text editor (markdown support)

**Acceptance Criteria:** Ordered list of criteria. Each has:
- Description text
- Checkbox (satisfied/not)
- Badge indicating if verifiable or human-judgment
- Add/remove/reorder

**Scope:** List of file/directory patterns. Editable. Shows which project each pattern belongs to.

**Dependencies:**
- "Blocked by" list (links to other work items)
- "Blocks" list (links to other work items)
- Add dependency by searching work items

**Artifacts:** List of attached documents/links.
- Type: document, link, design, spec, brainstorm, contract, other
- Can be: uploaded file, external URL, or inline rich text
- Add/remove artifacts

**Children:** Inline list of child work items with status. Can expand into mini-tree.

**Evidence:** (Read-only in Phase 1, populated in Phase 2+) List of commits, test results, file changes.

**History:** Activity log — who changed what, when. Status transitions, edits, artifact additions.

### View 3: Dependency Graph

Visual directed graph showing work items as nodes and dependencies as edges.

**Layout:**
- Nodes are work items (sized by depth or importance)
- Edges show "blocks" relationships (arrow from blocker to blocked)
- Color-coded by status
- Highlight critical path (longest chain of incomplete dependencies)
- Highlight "ready now" items (all dependencies met, status = ready)

**Interactions:**
- Click node → opens work item detail
- Zoom, pan
- Filter by project, label, status (same filters as dashboard)
- Toggle: show all levels or collapse to features/initiatives only

### View 4: Board View (optional, nice-to-have)

Kanban-style columns by status: planned → ready → in_progress → review → complete

- Cards are work items
- Drag to change status
- Filter by project, label, depth level
- Swimlanes by project or label

### View 5: Project Settings

Manage registered projects and global defaults.

- Add/remove projects (name, path, repo URL)
- Set default labels per project
- (Phase 2+) Set default policies per project

---

## Key Interactions

### Creating work items
- Quick-add inline (type name, press enter, created as child of current context)
- Full create dialog (name, description, labels, parent, dependencies)
- Drag-and-drop to rearrange hierarchy (change parent, reorder siblings)

### Changing status
- Dropdown on work item (planned → ready → in_progress → etc.)
- Status transitions should be unrestricted in Phase 1 (no gates yet — that's Phase 3)
- Status change logs to history

### Adding dependencies
- From work item detail: search and link
- From dependency graph: draw edges between nodes (if feasible)
- System should warn (not block) about circular dependencies

### Attaching artifacts
- Upload file, paste URL, or create inline document
- Artifacts support markdown preview
- Artifacts are typed (document, link, design, brainstorm, contract, spec, other)

### Filtering and search
- Global search across all work items (name, description, tags)
- Filter bar: status, label, project, tag (combinable)
- Saved filter presets

---

## Design Principles

1. **Information density over whitespace.** This is mission control, not a marketing site. Dense, scannable, data-rich. Every pixel should convey state.

2. **Hierarchy is the primary navigation.** The tree/outline view is the backbone. Everything else (graph, board, detail) is a secondary lens on the same data.

3. **Speed over ceremony.** Creating a work item should take 2 seconds (type and enter). No wizards, no multi-step flows. Progressive disclosure — start minimal, add detail as needed.

4. **Status at a glance.** Color, icons, and progress indicators should make status scannable without reading text. A user should understand the state of 50 items in 3 seconds.

5. **Keyboard-first.** Power users live in the keyboard. Arrow keys to navigate the tree, enter to open, quick-add with a shortcut, search with `/`. Mouse is supported but not required.

6. **Dark mode default.** Developer tool. Dark theme is primary. Light theme is supported but secondary.

7. **Everything outside core is a connector.** The core is pure domain logic (Work, Policy, Session). The UI is a connector. Claude Code is a connector. GitHub sync is a connector. File import is a connector. All connectors consume the same API. No connector has special access to internals.

---

## What NOT to Build (Phase 2+ features — schema only, no UI)

- Session management (who's working on what) — Phase 2
- Context briefing generation — Phase 2
- MCP server for Claude Code — Phase 2
- Policy configuration (gate/flag/skip dials) — Phase 3
- Policy enforcement and notifications — Phase 3
- Approval/notification queues — Phase 3
- Real-time session monitoring — Phase 4
- Evidence collection from git/tests — Phase 4
- AI-proposed decomposition — Phase 4
- Connector/sync with external systems (GitHub, JIRA, etc.) — after Phase 1, on demand

These features are in the PRD and the schema supports them. Do not build UI for them yet. Phase 1 is the planning layer only.

---

## Success Criteria for Phase 1

- [ ] Can create a project with nested work items 4+ levels deep
- [ ] Can set status on any work item and see color-coded status across the tree
- [ ] Can define dependencies and see them in the dependency graph
- [ ] Can attach artifacts (markdown docs, links) to work items
- [ ] Can filter/search across all work items by status, label, project, tag
- [ ] Dashboard answers "where are we" in <10 seconds for a project with 50+ work items
- [ ] Creating a work item takes <3 seconds
- [ ] Data model includes Policy and Session entities (empty, not exposed in UI)
- [ ] Compose's own Phase 2 development can be planned and tracked inside Compose
