# Session 10: The Sidebar Rebuild

**Date:** 2026-02-12
**Session:** 10

## What happened

The previous session broke the app mid-build. White screen crash — something in the CSS or component rewrite caused a React render error. The human reverted partially to fix it. By the time this session started, context was lost.

We recovered from the handoff doc and git state. The previous session had been executing a Vision Surface rebuild — replacing the custom card grid / phase bar / ripple UI with a conventional PM tool layout using shadcn/ui components. It got partway through (shadcn components installed, CSS tokens set up, new view files created) but left the app in a broken state.

The human's frustration was direct: "how about not breaking the app which breaks you?" Fair point. The agent that broke the app killed its own terminal session in the process. We wrote a rule for this — `incremental-builds.md` — codifying the principle: never delete a working component before its replacement is wired in, never rewrite CSS wholesale, one swap at a time, verify after every structural change.

Then we built the new layout correctly:

1. **AppSidebar.jsx** — Navigation sidebar with views (All Items, Board, Tree), phase filters with confidence bars and item counts, search, project stats, disconnection indicator.

2. **ItemListView.jsx** — List view with collapsible phase groups. Items sorted by confidence (lowest first — attention-directing). Each row: status dot, type badge, title, confidence dots, relative timestamp.

3. **ItemDetailPanel.jsx** — Right panel that slides in on item selection. Type and phase badges, inline title editing (double-click), status dropdown, confidence control (click to cycle), phase selector, click-to-edit description, connections grouped by type and direction, timestamps, action buttons (Connect, Pressure Test, Edit, Kill).

4. **VisionSurface.jsx** — Rewritten as a three-column flex layout: sidebar | main content | detail panel. Connects everything to useVisionStore. Phase filtering and search from sidebar propagate to the list view.

All built incrementally — new files created first, VisionSurface swapped last. Build verified before browser check. App never broke.

## What we built

### New files
- `src/components/vision/AppSidebar.jsx` — sidebar navigation + theme toggle (Sun/Moon)
- `src/components/vision/ItemListView.jsx` — list view with phase groups
- `src/components/vision/ItemDetailPanel.jsx` — right detail panel
- `src/components/vision/BoardView.jsx` — kanban board (6 status columns, drag-drop, cards with type/confidence/phase)
- `src/components/vision/TreeView.jsx` — hierarchical tree derived from connections (informs→child, supports→child, blocks→child), expand/collapse
- `.claude/rules/incremental-builds.md` — never break the app mid-build rule
- `docs/discovery/2026-02-12-visibility-as-value.md` — visibility is the product gap (session 10 discovery)
- `docs/discovery/2026-02-12-how-to-build-visibility.md` — three-layer architecture analysis
- `docs/plans/2026-02-12-visibility-prototype-plan.md` — prototype plan (steps 0-11)
- `docs/plans/2026-02-12-vision-surface-rebuild-design.md` — design spec with tokens and layout
- `docs/plans/2026-02-12-user-journey-design.md` — user journey: 6 phases, control surface, what exists vs next pieces

### Modified files
- `src/components/vision/VisionSurface.jsx` — rewritten: sidebar layout replaces card grid, wires all three views
- `src/index.css` — user's design scheme applied (#3B82F6 primary, #111827 bg, #FBBF24 accent), legacy tokens updated
- `tailwind.config.js` — shadcn color/radius/font config
- `server/vision-store.js` — parentId field added to item model (create + update allowed)
- `package.json` — radix, cva, clsx, tailwind-merge, lucide-react, tailwindcss-animate

### Also committed (from previous session)
- 15 shadcn/ui components in `src/components/ui/`
- 6 view components in `src/components/vision/views/` (from prototype plan)
- PhaseBar, ViewContainer, DetailPanel, ConnectionOverlay (evolved from originals)
- `src/lib/utils.js` (cn utility), `src/hooks/use-mobile.jsx`

## What we learned

1. **Breaking the app breaks the agent.** The terminal runs inside the app. If a CSS rewrite or component swap causes a white screen, the agent's session dies. The incremental builds rule isn't just good practice — it's self-preservation.

2. **Build new alongside old, swap last.** Create new files, verify build passes, then update the entry point. One import change, not a cascade.

3. **Base44 patterns are the right reference.** Conventional PM tool layout (sidebar + list + detail panel) is immediately legible. No learning curve. The novel content (confidence, connection tracing, phase awareness) lives inside the conventional container.

4. **Shadcn/ui works in a panel context.** The sidebar component assumes full viewport, but overriding a few classes makes it work inside a canvas tab. The component library earns its keep in consistent spacing, accessible primitives, and dark theme support.

5. **Discovery docs have diminishing returns.** We wrote "Visibility as Value" and "How to Build Visibility" — thoughtful explorations that didn't directly produce code. The design spec and the build itself were the useful artifacts. The discovery was valuable as conversation, not as documents.

6. **Derive hierarchy from connections, don't duplicate it.** The tree view originally needed parentId on every item. The human asked: "shouldn't that be taken directly from relations?" Then: "or modify the tree view logic to use relations directly without parent_id?" Correct on both counts. `informs` A→B means B is child of A. `supports`/`blocks` A→B means A is child of B. Tree builds itself from existing data. No new fields needed.

7. **Design tokens must match the spec.** The original CSS had generic shadcn defaults (pure grays, muted purple primary). The human's design scheme specified blue-tinted darks (#111827), vivid blue primary (#3B82F6), amber accent (#FBBF24). Every token was wrong. Lesson: check the spec before assuming defaults are close enough.

## Open threads

- [x] Board view (kanban by status) — 6 columns, drag-drop, cards with type/confidence/phase
- [x] Tree view — hierarchy derived from connections, no data model changes needed
- [x] Design scheme — user's hex values applied to all CSS tokens
- [x] Theme toggle — Sun/Moon icon in sidebar
- [x] Status model fixed — server aligned with board lifecycle (planned/ready/in_progress/review/complete/blocked/parked/killed)
- [x] Cleaned up 11 unused files: views/ directory (6), PhaseBar, ViewContainer, DetailPanel, ConnectionOverlay, ItemCard
- [x] User journey design doc written — 6 phases, control surface, prioritized next pieces
- [ ] Search should highlight matches in results
- [ ] Quick-add for creating items inline

---

*The tree was always in the connections. We just had to look.*
