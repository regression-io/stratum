# Session 11: Two-Mode Vision Surface

**Date:** 2026-02-12
**Previous:** [Session 10: The Sidebar Rebuild](2026-02-12-session-10-sidebar-rebuild.md)

## What happened

Session 10 left us with a fully rebuilt Vision Surface — list, board, tree views, sidebar, detail panel, all on shadcn/ui. The human opened this session by pointing out we weren't tracking our own docs on the board. Fair. We built a tracking system: a Node script (`vision-track.mjs`) that creates board items via the API, an agent rule that enforces it, and expanded server types to support task/spec/evaluation items. Then synced the board with reality — 8 items updated to their actual statuses.

Next came a triple code review ("review 3x"). Three independent reviews found 16 issues across 6 categories: duplicated constants, missing server validation, no error handling on API calls, ambiguous killed type, unsorted board items, and more. We fixed all 16 in a single pass — extracted shared constants, added `handleResponse` error handling, fixed the kill button semantics, filtered parked/killed from the board.

Then the human asked the real question: should thinking and building be in the same surface or separate? We explored three options. Full split was too much overhead. Unified surface was the status quo — works but doesn't differentiate the workflows. The third option — same surface, two modes — won. Discovery mode filters to thinking phases (vision, requirements, design), defaults to tree view, shows confidence and open questions. Execution mode filters to building phases (planning through release), defaults to board, shows progress and blockers. Cross-mode references are visible but collapsed.

Implementation was four commits. Mode constants. VisionSurface mode state with per-mode view memory. AppSidebar mode toggle with scoped phases and adapted stats. ItemDetailPanel cross-mode links. Clean builds throughout.

## What we built

| File | Change |
|------|--------|
| `src/components/vision/constants.js` | DISCOVERY_PHASES, EXECUTION_PHASES, MODE_DEFAULTS |
| `src/components/vision/VisionSurface.jsx` | Mode state, viewOverrides, handleModeChange, mode-based filtering |
| `src/components/vision/AppSidebar.jsx` | Mode toggle UI, scoped phases, adapted stats |
| `src/components/vision/ItemDetailPanel.jsx` | CrossModeLinks component — collapsible cross-mode references |
| `src/components/vision/ConfidenceDots.jsx` | Shared confidence indicator (from review fixes) |
| `src/components/vision/useVisionStore.js` | handleResponse error handling (from review fixes) |
| `server/vision-store.js` | Status validation, exported constants, type expansion (from review fixes) |
| `scripts/vision-track.mjs` | Node script for board item CRUD |
| `.claude/rules/vision-tracking.md` | Agent rule: every doc gets a board item |
| `docs/plans/2026-02-12-two-mode-surface-design.md` | Design doc for the two-mode feature |
| `docs/plans/2026-02-12-two-mode-implementation.md` | 5-task implementation plan |

## What we learned

1. **The agent forgets its own rules unless there's infrastructure.** Telling the agent "always add board items" doesn't work. A tracking script + rule + occasional human checkpoints works.

2. **Triple review finds what single review misses.** Each review had a different lens (correctness, design, consistency). The overlap was minimal — they found genuinely different issues.

3. **Mode is a filter, not a restructure.** The two-mode feature required zero data model changes. The mode is purely a UI concern: which phases to show, which view to default to, which stats to display. The data model was already right.

4. **Per-mode view memory is essential.** Without `viewOverrides`, switching between modes would lose your view preference. The user would set Discovery to list, switch to Execution, come back and find it reset to tree. Small detail, big UX difference.

5. **Cross-mode references are the bridge.** The collapsible "Related (execution)" section preserves traceability without cluttering the focused view. You see your mode's items; connections to the other mode are one click away.

## Open threads

- [ ] Visual verification — need to open the app and test mode switching with real data
- [ ] Cross-mode references need items with connections spanning modes to test
- [ ] Mode toggle styling may need refinement once seen live
- [ ] Board item for this session's work needs to be created
- [ ] Keyboard shortcut for mode switching (D/E?)

The surface now has two faces — one for thinking, one for building. Same data, different lenses.
