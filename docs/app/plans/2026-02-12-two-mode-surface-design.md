# Two-Mode Vision Surface Design

**Date:** 2026-02-12
**Status:** COMPLETE
**Related:** [User Journey Design](2026-02-12-user-journey-design.md), [Vision Surface Rebuild](2026-02-12-vision-surface-rebuild-design.md)

## Problem

The Vision Surface treats all items uniformly. Thinking artifacts (ideas, decisions, questions) and building artifacts (tasks, specs) have different workflows, different key metrics, and different natural views. Phase filters exist but require manual switching and don't change the surface's behavior.

## Decision

Same surface, two modes. Discovery mode and Execution mode. Each mode filters to its phases, defaults to its best view, and adapts the sidebar stats. Cross-references between modes are visible but collapsed.

## Mode Switch

Toggle in the sidebar header:

```
[Discovery] [Execution]
```

- **Discovery** filters to: vision, requirements, design
- **Execution** filters to: planning, implementation, verification, release
- Phase sub-filters still exist within each mode, scoped to that mode's phases
- Mode stored in component state (not persisted — defaults on reload)
- Switching modes clears item selection, preserves search query

## Default Views

| Mode | Default view | Rationale |
|------|-------------|-----------|
| Discovery | Tree | Hierarchy is how you navigate thinking |
| Execution | Board | Tasks flow through status columns |

View switcher (List / Board / Tree) still available in both modes. View choice within a mode is remembered for the session.

## Sidebar Adaptation

### Discovery mode sidebar
- Phases: Vision, Requirements, Design
- Stats: average confidence bar, open questions count, decision count
- Emphasis: "What's uncertain? What needs decisions?"

### Execution mode sidebar
- Phases: Planning, Implementation, Verification, Release
- Stats: complete/total progress, blocked count, in-progress count
- Emphasis: "What's done? What's stuck?"

## Cross-References in Detail Panel

When viewing an item, connections to items in the other mode appear in a collapsible section:

- **In Discovery mode:** "Related (Execution)" — tasks informed by this decision
- **In Execution mode:** "Related (Discovery)" — decisions that informed this task
- Collapsed by default
- Clicking a cross-reference switches modes and selects the linked item

## Data Model

No changes. Same items, connections, phases, types, statuses. The mode is purely a UI concern — a filter + default view preference.

## Components Affected

| Component | Change |
|-----------|--------|
| `AppSidebar.jsx` | Mode toggle, phase list scoped to mode, adapted stats |
| `VisionSurface.jsx` | Mode state, default view per mode, pass mode to children |
| `ItemDetailPanel.jsx` | Cross-reference section with collapsible other-mode connections |
| `constants.js` | `DISCOVERY_PHASES`, `EXECUTION_PHASES` arrays |

## What This Enables

- Discovery mode becomes the natural surface for brainstorming sessions — thinking visible, building hidden
- Execution mode becomes the natural surface during implementation — tasks visible, decisions behind a click
- The bridge between them (cross-references) preserves Compose's differentiator: traceability from why to what
