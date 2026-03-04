# Spec: Roadmap Drill-Down Views

**Date:** 2026-02-13
**Status:** DRAFT
**Scope:** Add hierarchical drill-down navigation to the Vision Surface
**Mockup:** [drill-down-v2.html](../mockups/drill-down-v2.html)
**Related:** [Vision Tracker Design](../plans/2026-02-13-vision-tracker-design.md), [Product Realignment](../design/2026-02-13-product-realignment.md)

---

## What is this?

A new view mode for the Vision Surface that lets users navigate the work hierarchy top-down: roadmap → initiative → phase → items. Users expand items inline to see children, options, connections, and actions — then drill deeper via breadcrumb navigation. Same visual pattern at every depth.

This replaces the current flat list/board/graph as the primary way to understand "where are we and what's next."

---

## What are we building?

A **Roadmap view** added to the existing view switcher (alongside List, Board, Tree, Graph). The view renders work items as expandable rows organized hierarchically. Navigation happens two ways: inline expansion (accordion) and drill-in (breadcrumb push).

**In scope:**
- Roadmap view with initiative-level overview
- Inline expansion of any item (accordion pattern)
- Drill-in navigation with breadcrumb trail
- Decision items show options with pros/cons
- Approve/Discuss/Decline actions on decisions
- Dependency links as clickable navigation
- Progress rollup (X/Y done, progress bar) on parent items

**Out of scope:**
- Editing item content inline (use existing detail panel)
- Creating new items from this view
- Drag-and-drop reordering
- Filtering/search within the view (add later)
- Graph or board sub-views within drill-down

---

## Data Model Assumptions

This spec assumes the Vision Tracker data model from the [design doc](../plans/2026-02-13-vision-tracker-design.md). Specifically:

- Items have `type` including `initiative` and `feature`
- Connections have `type`: `blocks`, `informs`, `implements`, `supports`
- Items have `status`, `phase`, `confidence`, `description`
- Items can be organized hierarchically via `implements` edges (child implements parent)

If these fields don't exist yet, they must be added before or alongside this build. The view degrades gracefully — items without children simply don't expand, items without typed edges show connections without edge labels.

---

## View: Roadmap

### Top Level — Initiatives

When the user switches to Roadmap view, they see all `initiative`-type items as expandable rows. Each row shows:

- **Color dot** — matches initiative's status color
- **Title** — initiative name, bold
- **Progress** — "X/Y done" count + thin progress bar
- **Status badge** — planned / in progress / complete
- **Chevron** — expand/collapse indicator

Initiatives are sorted: in_progress first, then planned, then complete (dimmed).

### Expanded Initiative — Phases

Expanding an initiative shows its phases as sub-rows. Phases are derived from the `phase` field of the initiative's children: group children by phase, show each phase as a row with:

- **Phase dot** — green (complete), yellow (in progress), gray (planned)
- **Phase name** — Planning, Specification, Architecture, Implementation, etc.
- **Summary** — item count or notable stat ("7 decisions, 2 approved")
- **Status** — rolled up from children

Clicking a phase row **drills in** — pushes onto the breadcrumb and shows that phase's children as the new list.

### Drilled-In — Phase Children

After drilling into a phase, the user sees:

- **Breadcrumb bar** — Roadmap > Initiative Name > Phase Name. Each segment is clickable to jump back.
- **Header** — Phase badge, title ("Vision Tracker — Specification Phase"), rolled-up status
- **Description** — One-line summary with link to source doc (if `planLink` exists)
- **Children section** — "Children (N)" label, then expandable rows for each item

Each child row follows the **uniform item row** pattern (below).

---

## Pattern: Uniform Item Row

Every item at every depth uses the same row pattern. This is the atomic unit of the view.

### Collapsed state

A single-line row showing:
- **Color dot** — by type (decision=green, task=gray, spec=indigo, idea=yellow)
- **Title** — with optional semantic ID prefix in bold ("**D1:** Tracker is primary")
- **Status badge** — planned / in_progress / complete / approved
- **Chevron** — expand/collapse

Completed/approved items render at reduced opacity (0.6).

### Expanded state

Clicking the row toggles expansion. The expanded body shows (all optional — only render sections that have content):

1. **Rationale/description** — item's description text
2. **Action bar** — contextual buttons (see Actions below)
3. **Linked items** — connections to other items, clickable
4. **Options** — for decision-type items only (see Decisions below)
5. **Children** — nested item rows if the item has `implements` children

### Linked Items

Each connection renders as a clickable row:
- **Small dot** — colored by target item's type
- **Target title** — the connected item's name
- **Edge type label** — right-aligned: "informs", "blocked by", "implements", etc.

Clicking a linked item **drills in** — pushes onto the breadcrumb and renders that item as the focused view with its own connections, children, and actions.

---

## Pattern: Decision Options

Items with `type: decision` get special treatment when expanded.

### Options list

Below the rationale and action bar, render an "OPTIONS" section. Each option is a nested expandable row:

- **Letter prefix** — A, B, C, D (bold, dimmed for non-recommended)
- **Option title** — short name
- **Verdict badge** — "recommended" (indigo) or nothing
- **Chevron** — expand/collapse

The recommended option has a left border accent and its letter is highlighted.

### Option expanded

- **Description** — what this option means
- **Pros/Cons** — two-column layout. Pros prefixed with "+", cons with "-". Pro headers green, con headers red.

### Where options come from

Options are separate items connected to the decision via `informs` edges. Each option is a first-class tracker item with its own title, description, and pros/cons in the description field. The LLM creates as many options as it sees fit — not limited to A-D. One option can be marked as recommended (via a convention like `status: recommended` or a field). The letter prefix (A, B, C...) is derived from display order, not stored.

---

## Actions

Actions appear in expanded item bodies. Which actions appear depends on context:

### Decision items (not yet approved)
- **Approve** (green) — marks the decision as `status: complete` with a convention noting which option was chosen
- **Discuss** (indigo) — opens the item in the detail panel for editing/discussion
- **Decline** (red) — marks as `status: killed` or flags for rework

### Decision items (already approved)
- **Approved** (green, disabled) — shows the decision is settled

### Non-decision items
- **Discuss** (indigo) — opens in detail panel

### Action behavior

Approve and Decline trigger a `PATCH /api/vision/items/:id` updating status. The view updates via WebSocket (existing pattern). No confirmation dialog needed — the action is visible and reversible.

---

## Navigation

### Breadcrumb bar

Persistent bar below the view header. Shows the navigation path:

> Roadmap > Vision Tracker > Specification > D8: Markdown Export

Each segment except the last is a clickable link. Clicking any segment jumps back to that level — the breadcrumb truncates and the view re-renders at that scope.

### Drill-in triggers

These actions push a new segment onto the breadcrumb:
- Clicking a **phase row** inside an expanded initiative
- Clicking a **linked item** inside an expanded item body
- (Future: clicking an item title could drill in vs. expand inline — but for v1, clicking expands, linked items drill)

### Back navigation

- Click any breadcrumb segment to jump there
- Browser back/forward buttons work — breadcrumb state synced to URL hash (`#roadmap/id1/id2`), `popstate` listener updates view

---

## Progress Rollup

Parent items (initiatives, features) show rolled-up progress:

- **Count** — "X/Y done" where Y = total descendant items, X = those with status `complete`
- **Progress bar** — thin (4px), colored by the initiative's accent color, width = X/Y percentage
- **Phase summary** — when expanded, each phase row shows its own completion state

Rollup counts traverse `implements` edges downward. An item counts as "done" if `status === 'complete'`.

---

## Visual Design

Follow the existing Vision Surface dark theme. Key specs from the mockup:

- **Background:** `#0b0b14` (body), `#0e0e19` (cards/items)
- **Borders:** `rgba(255,255,255,0.06)` — subtle separation
- **Text:** `#e2e8f0` (primary), `#94a3b8` (secondary), `#64748b` (tertiary)
- **Accent:** `#818cf8` (indigo — links, active states, recommended)
- **Status colors:** green `#22c55e` (complete), yellow `#fbbf24` (in progress), gray `#64748b` (planned), red `#ef4444` (declined)
- **Type colors:** decision=`#22c55e`, task=`#94a3b8`, spec=`#818cf8`, idea=`#fbbf24`
- **Font sizes:** 15px (titles), 12px (body/items), 11px (descriptions), 10px (labels/badges), 9px (edge types/counts)
- **Hover:** items get `rgba(129,140,248,0.04)` background
- **Expanded:** items get `#10101f` header background + bottom border

Light mode: inherit from existing theme system. No special treatment needed — the token system handles it.

---

## What NOT to Build

- **Inline editing** — don't add edit capabilities to item rows. The detail panel handles editing.
- **Item creation** — no "add item" buttons in this view. Use existing creation flows.
- **Filtering** — no filter bar in v1. The view's hierarchy IS the filter.
- **Drag-and-drop** — no reordering items by dragging.
- **Keyboard navigation** — nice to have but not required for v1. Mouse-driven is fine.
- **Animations** — no transition animations on expand/collapse. Instant toggle.
- **Mobile layout** — desktop only. No responsive breakpoints.
- **Separate route** — this is a view mode within VisionSurface, not a new page.

---

## Success Criteria

1. User can see all initiatives with progress at a glance from the Roadmap view
2. User can drill from initiative → phase → individual decisions in under 3 clicks
3. User can expand a decision, compare options (pros/cons), and approve one without leaving the view
4. User can follow a dependency link from one item to another and navigate back via breadcrumb
5. Approving a decision updates its status immediately (via existing WebSocket)
6. Progress counts update when child items are completed
7. The view loads with no perceptible delay for 50 items
8. Breadcrumb navigation works — user never gets lost or stuck

---

## Design Decisions

- [x] **D1: Roadmap is a new view mode** — Added to view switcher alongside List, Board, Tree, Graph. Not a replacement.
- [x] **D2: Inline expand + drill-in are separate gestures** — Click row = expand accordion. Click linked item = drill in. Two distinct navigation modes.
- [x] **D3: Phases are derived, not stored** — Phase groupings come from children's `phase` field, not from a separate "phase" entity. No new data model needed. **Addendum:** Only phases with children are shown by default. But there must be a way to add a phase (create a child in that phase) and to flag that intermediate phases are needed (e.g. an initiative jumps from requirements to implementation — the user or agent can indicate design/planning phases are missing and need work).
- [x] **D4: Decision options are child items** — Each option is a separate item connected to the decision via `informs` edge. Options are first-class: independently linkable, can have their own descriptions/pros/cons, and the LLM can create as many as needed. The decision item tracks which option was chosen (if any) via a `chosenOption` field or status convention.
- [x] **D5: Actions dispatch to existing API** — Approve = PATCH status. No new endpoints. Detail panel handles rich editing.
- [x] **D6: Breadcrumb state synced to URL hash** — Breadcrumb path stored in `window.location.hash` (`#roadmap/id1/id2`). Browser back/forward works via `popstate`. Stale links (deleted items) fall back to root. Trivial to implement alongside breadcrumb array.
