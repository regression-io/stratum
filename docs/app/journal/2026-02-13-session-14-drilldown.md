# Session 14: The Drill-Down Build

**Date:** 2026-02-13
**Focus:** Two-tier terminal, roadmap drill-down spec + build, data population, bug marathon

## What happened

The biggest build session yet. Started with architecture, ended with a working hierarchical roadmap view and 40+ items organized into features and tracks.

**Two-tier terminal architecture.** Separated the terminal server into its own process on port 3002 (`server/terminal-server.js`). The main vision server on 3001 no longer handles PTY sessions. This was necessary for the pressure test feature that came in Session 15 — but at the time, the motivation was reliability. Terminal crashes shouldn't take down the vision API.

**Drill-down spec.** Wrote `docs/specs/2026-02-13-roadmap-drilldown-spec.md` from the v2 mockup's 6-step walkthrough. Core patterns: uniform item rows at every depth, inline expand vs drill-in navigation (separate gestures), decision options with pros/cons, approve/discuss/decline actions. Six design decisions, D1 pre-approved.

**The build.** Two new components: `RoadmapView.jsx` (849 lines) and `ItemRow.jsx` (423 lines). RoadmapView renders features as expandable rows, with phase groups inside. ItemRow is the atomic unit — one component pattern at every depth. Wired into VisionSurface with a new sidebar view option.

**Data population.** Read all docs to build the roadmap hierarchy. Created 4 features, ~15 tracks, wired connections. Hit server validation limits (initiative/feature types and implements edges weren't in the allowed lists). Wrote a standalone Node script to populate directly via VisionStore, bypassing the running server.

**Bug marathon.** Six critical fixes in rapid succession:
- `filteredItems` was being passed instead of `items` to RoadmapView (items were disappearing)
- `pushState` loop in breadcrumb sync (URL kept rewriting itself)
- Missing cycle guard in descendant counting (infinite recursion on circular connections)
- `supports` edges not recognized as hierarchy (items orphaned from their parents)
- Stale hash fallback when items hadn't loaded yet
- Keystroke lag from vision broadcasts on every keypress (debounced + React.memo)

**Navigation rethink.** Originally phases drilled in (breadcrumb push). Changed to inline accordion — click a phase, it expands in place. Drill-in only happens when clicking a linked item. This matches the spec's "two navigation modes" principle.

**Taxonomy cleanup.** Renamed initiative→feature, feature→track. Assigned semantic IDs to all items (FORGE-FTR-1, FORGE-TRK-7, etc.). Normalized "specification" phase to the canonical PHASES list.

**Task cleanup.** Created tasks under FORGE-TRK-7 for review findings. Wired 66 orphaned items into the hierarchy. Replaced hardcoded rgba colors with theme tokens. Added sessionStorage persistence for expanded state.

## What we built

### New files
- `server/terminal-server.js` — Standalone terminal WebSocket server on port 3002
- `src/components/vision/RoadmapView.jsx` — Hierarchical drill-down view (849 lines)
- `src/components/vision/ItemRow.jsx` — Uniform expandable item row (423 lines)
- `docs/specs/2026-02-13-roadmap-drilldown-spec.md` — Behavioral spec
- `scripts/wire-orphans.mjs` — Bulk-wire orphaned items into hierarchy

### Modified files
- `server/index.js` — Supervisor updates for two-tier architecture
- `src/components/vision/VisionSurface.jsx` — RoadmapView integration, mode removal
- `src/components/vision/AppSidebar.jsx` — Roadmap view option, mode toggle removed
- `src/components/vision/constants.js` — New types, removed mode constants
- `data/vision-state.json` — 40+ items organized into hierarchy

## What we learned

1. **Spec-driven builds are faster.** The drill-down spec made the build mechanical. Every decision was pre-made. No mid-build design pivots.
2. **Data population is harder than the UI.** Building the components took hours. Populating them with real data took just as long — reading docs, deciding hierarchy, assigning IDs, wiring connections.
3. **Bug density peaks at integration.** Six critical bugs hit the moment real data met real UI. Each was obvious in hindsight, invisible in isolation.
4. **Inline expand > drill-in for hierarchy.** Drill-in makes sense for linked items (lateral navigation). For parent→child, inline accordion keeps context visible.
5. **The taxonomy rename was necessary.** "Initiative" and "feature" meant different things to different people. "Feature" and "track" map cleanly to what the hierarchy actually represents.

## Open threads

- [ ] Approve spec decisions D2-D6
- [ ] Commit orphaned work from Sessions 12-13
- [ ] Codify the full roadmap doc
- [ ] Docs view for browsing tracked vs orphaned documents

---

*849 lines of new UI, 6 critical bugs, 66 orphaned items. The roadmap now tracks itself.*
