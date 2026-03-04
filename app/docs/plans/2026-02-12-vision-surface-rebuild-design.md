# Vision Surface Rebuild — Design Spec

**Date:** 2026-02-12
**Phase:** Design (Feature Development Lifecycle Phase 1)
**Status:** COMPLETE (design tokens and view names below are from the original spec; actual implementation uses the user's design scheme — see `src/index.css` for current tokens)

## Related Documents

- [Core Requirements](../requirements/core-requirements.md) — CR1-CR7
- [Vision Component Design](../design/vision-component-design.md) — prior design (superseded by this)
- [Base44 UI Eval](../evaluations/2026-02-11-base44-ui-eval.md) — reference patterns
- [Vision Component Spec](../specs/2026-02-11-vision-component-spec.md) — behavioral spec (data model still relevant)

## Problem Statement

The current Vision Surface UX is unintuitive and poorly laid out. Custom layout patterns (phase bar, card grid, custom view modes) require learning before use. The hand-rolled CSS lacks the polish and consistency of a component library. Users prefer the Base44 version which uses conventional PM tool patterns.

## Decision

Full adoption of shadcn/ui component library. Fresh build using Base44 as visual/interaction reference. Conventional layout (sidebar + main content + detail panel) with Compose's novel content model (confidence, types, phases, connections).

## Design Tokens

```css
.dark {
  /* Surfaces */
  --background: 0 0% 9%;            /* #181818 */
  --foreground: 0 0% 88%;           /* #E0E0E0 */
  --card: 0 0% 15%;                 /* #262626 */
  --card-foreground: 0 0% 88%;
  --popover: 0 0% 15%;
  --popover-foreground: 0 0% 88%;

  /* Brand */
  --primary: 238 30% 50%;           /* #5B5EA6 */
  --primary-foreground: 0 0% 98%;
  --secondary: 240 28% 77%;         /* #B3B3D8 */
  --secondary-foreground: 0 0% 9%;
  --accent: 36 100% 65%;            /* #FFB74D */
  --accent-foreground: 0 0% 9%;

  /* Semantic */
  --destructive: 4 90% 58%;         /* #F44336 */
  --destructive-foreground: 0 0% 98%;
  --muted: 0 0% 15%;
  --muted-foreground: 0 0% 63%;     /* #A0A0A0 */

  /* Chrome */
  --border: 0 0% 20%;
  --input: 0 0% 20%;
  --ring: 238 30% 50%;

  /* Sidebar */
  --sidebar-background: 0 0% 9%;
  --sidebar-foreground: 0 0% 88%;
  --sidebar-primary: 238 30% 50%;
  --sidebar-primary-foreground: 0 0% 98%;
  --sidebar-accent: 0 0% 15%;
  --sidebar-accent-foreground: 0 0% 88%;
  --sidebar-border: 0 0% 18%;
  --sidebar-ring: 238 30% 50%;

  /* Radius */
  --radius: 0.75rem;

  /* Compose-specific */
  --success: 122 39% 49%;           /* #4CAF50 */
  --warning: 36 100% 50%;           /* #FF9800 */
}
```

Typography: Inter, 16px base, 1.5 line-height.
Shapes: 12px card radius, 8px button radius, 4px input radius.
Shadow: `0 2px 10px rgba(0, 0, 0, 0.2)` for cards.

## Layout Architecture

### Three layout modes (user-switchable)

**Split (default):** Terminal left (50%), Vision surface right (50%). Draggable divider.

**Vision primary:** Vision surface full width. Terminal collapses to bottom drawer.

**Terminal primary:** Terminal full width. Vision surface hidden or collapsed to right drawer.

### Vision surface internal layout

```
┌──────────┬────────────────────────────────────┐
│ Sidebar  │  Toolbar (filters, search, views)   │
│          ├────────────────────────────────────┤
│ Nav      │  Main Content                       │
│ - Views  │  (list / board / tree / canvas)     │
│ - Phases │                                     │
│          │                                     │
│          ├────────────────────────────────────┤
│          │  Detail Sheet (on item select)      │
└──────────┴────────────────────────────────────┘
```

Sidebar: shadcn `Sidebar` component, collapsible. Auto-collapses to icons in split mode.

## Sidebar Navigation

### Project section (top)
- Project name
- Quick stats (total items, open questions)
- Global search input

### Views section (middle)
- All Items — default list view
- Board — kanban by status
- By Phase — grouped by phase
- Decisions — decisions + questions only
- Activity — timeline of recent changes

Each view: Lucide icon + label + count badge.

### Phases section (bottom)
- Vision, Requirements, Design, Planning, Implementation, Verification, Release
- Item count per phase
- Confidence indicator (progress bar or dot)
- Click to filter

## Main Content Views

### List view (default)
Rows grouped by phase, collapsible headers. Each row:
```
[status dot] [type icon] Title              [phase badge] [confidence dots] [updated]
```
Sort by confidence (lowest first) or date.

### Board view
Kanban columns by status: planned → ready → in_progress → review → complete → blocked.
Cards show title, type badge, confidence. Drag to change status.

### Tree view
Hierarchical parent-child display. Expand/collapse. Indented rows.
Shows initiative → feature → task structure.

### Detail panel
Sheet slides in from right (vision-primary) or up from bottom (split mode).
- Editable title and description
- Type, phase, status selectors
- Confidence control
- Connected items list
- Action buttons (Connect, Pressure Test, Kill)
- Timestamps

## Data Model (Merged)

```js
{
  id,
  title,
  description,

  // Work item backbone
  parentId,          // null = top-level
  status,            // planned | ready | in_progress | review | complete | blocked | parked | killed

  // Vision enrichments
  type,              // task | decision | question | idea | thread | artifact | spec | evaluation
  phase,             // vision | requirements | design | planning | implementation | verification | release
  confidence,        // 0-4

  // Metadata
  tags: [],
  position,          // for spatial view
  createdAt,
  updatedAt,
}
```

Connections: `{ id, fromId, toId, type }` — blocks | informs | supports.

Key addition: `parentId` enables tree view and roadmap hierarchy.

## Component Mapping

| UI Element | shadcn Component |
|---|---|
| Sidebar | `Sidebar` |
| Detail panel | `Sheet` |
| Selectors | `Select` |
| Badges | `Badge` |
| Buttons | `Button` |
| Search | `Input` |
| Filters | `DropdownMenu` |
| Tooltips | `Tooltip` |
| Kanban cards | `Card` |
| Collapsible groups | `Collapsible` |
| Separators | `Separator` |
| Scroll areas | `ScrollArea` |

## Implementation Sequence

1. Install shadcn/ui foundation (CSS variables, cn() utility, tailwind config)
2. Copy core components from coder-config (Button, Card, Badge, Input, Sheet, Select, Sidebar, etc.)
3. Build layout shell (sidebar + main content area + header with mode toggle)
4. Build list view (default, most important)
5. Build detail panel (Sheet)
6. Build board view
7. Build tree view
8. Wire to existing WebSocket store (useVisionStore)
9. Add parentId to data model and server
10. Connect layout mode switching
