# Session 9: The Glow

| | |
|---|---|
| **Date** | 2026-02-12 |
| **Previous** | [Session 8: Vision Spec](2026-02-11-session-8-vision-spec.md) |

## What happened

### "Where's the glow?"

The session started with a simple question. Session 8 had designed the vision surface components and built out a full design system with warm ember tones, glow tokens (`--ember-glow`, `--indigo-glow`, `--magenta-glow`), and a pipeline breathing animation. But none of it was visible. The components existed in `src/components/vision/` — VisionSurface, PipelineBar, ItemMap, ItemCard, DetailZone, ConnectionLayer, StatusBar — all fully written, all backstage. App.jsx rendered exactly two things: Terminal and Canvas. The glow was written but never on screen.

### Wiring it up

The infrastructure was already there. Canvas.jsx already imported VisionSurface and handled `vision://` tab types. The server had VisionStore (JSON persistence), VisionServer (REST + WebSocket), and the upgrade routing for `/ws/vision`. Everything was connected except nobody opened the tab.

One `POST /api/canvas/open` with `path: "vision://surface"` and the whole thing lit up. 24 items across Vision, Requirements, and Design phases. 16 connections. The pipeline bar showing phase states. Dense layout with type-colored borders and confidence dots.

### The glow conversation

With the surface visible, we went through several design iterations on what "glow" should mean:

**First attempt: static heat.** Confidence as base heat (0-4 mapped to 0-1), propagated through `informs`/`supports` connections with 0.55 decay per hop. Each card got a type-colored box-shadow scaled by its heat value. Crystallized decisions glowed green, untested questions stayed dark. It worked but the user pointed out two problems: too subtle, and everything glows at the same time — no information progression.

**Second attempt: animated ripple.** We computed graph depth (BFS from roots) and staggered a CSS animation by depth tier. The idea: a pulse that sweeps through the connection graph like a wave. But the always-on animation was noisy — everything pulsing all the time conveyed no signal.

**Final design: click-to-ripple.** The user pushed to the clean version. No static glow. Cards are dark by default. Click a card and its downstream connection tree lights up in sequence — depth 0 (the clicked card) pulses first, depth 1 next, depth 2 next. Each tier delayed by 0.7s. The animation plays twice then settles. You see "where does this decision flow?" as a wave of type-colored light.

The mechanism: VisionSurface computes a `rippleTree` (BFS from selected card through downstream connections), passes depth to each ItemCard via ItemMap. A `rippleKey` counter increments on each click to force CSS animation restart via a keyed overlay div.

### Filter bug fix

The pipeline phase filters had a bug: clicking "All" only cleared the lens (all vs plan), not the phase selection. So if you filtered to "Design" (14 items), then clicked "All", you'd still see 14 items instead of 24. Fix: "All" now clears both lens and selectedPhase.

Also removed the glow animations from the pipeline bar phase buttons — the user decided cards own the glow, not the filter tabs.

## What we built

### New files
- `src/components/vision/VisionSurface.jsx` — Main surface: ripple tree computation, downstream BFS, selection state
- `src/components/vision/PipelineBar.jsx` — Phase filter bar with item counts and layout mode selector
- `src/components/vision/ItemMap.jsx` — Three layout modes (spatial, dense, timeline), groups items by phase
- `src/components/vision/ItemCard.jsx` — Card with type border, confidence dots, click-to-ripple overlay
- `src/components/vision/DetailZone.jsx` — Bottom panel showing selected item details with action chips
- `src/components/vision/ConnectionLayer.jsx` — SVG connection lines for spatial layout
- `src/components/vision/StatusBar.jsx` — Item count summary bar
- `src/components/vision/useVisionStore.js` — WebSocket hook for `/ws/vision` + REST mutations
- `server/vision-server.js` — REST endpoints + WebSocket broadcast for vision state
- `server/vision-store.js` — JSON-file-backed storage for items and connections
- `docs/plans/2026-02-11-vision-surface-implementation-plan.md` — Implementation plan
- `.claude/rules/self-preservation.md` — Rule: don't kill your own session

### Modified files
- `server/index.js` — Wired VisionStore + VisionServer, added `/ws/vision` upgrade
- `src/components/Canvas.jsx` — Added VisionSurface import, `vision://` tab handling
- `src/index.css` — Design tokens (magenta), pipeline phase styles, card ripple animation
- `server/file-watcher.js` — Added `vision://` scheme handling for canvas open
- `index.html` — Updated
- `package.json` — Dependencies
- `server/terminal.js` — Session persistence improvements

## What we learned

1. **Infrastructure without activation is invisible.** Everything was built and wired — components, server, WebSocket, persistence — but the user couldn't see any of it because nothing opened the tab. The gap between "built" and "visible" is one API call.

2. **Glow needs to carry information, not just look nice.** The first static glow attempt was decorative — everything lit up, nothing communicated. The user's pushback ("what's the point of them glowing?") forced the design to evolve from decoration to information.

3. **Progressive disclosure through animation.** The ripple-on-click is a form of progressive disclosure: the board is clean until you ask a question ("where does this connect?"), then the answer appears as motion. The animation IS the answer.

4. **Design through conversation, not specification.** The glow design went through four iterations in real-time conversation — static heat → depth-staggered animation → always-on ripple → click-triggered ripple. Each version was the user seeing and reacting, not planning in the abstract.

5. **Filter state bugs hide in multi-axis filtering.** Lens (all/plan) and phase (vision/requirements/design/...) are independent filter axes. Clearing one without clearing the other leaves the user stuck. All reset paths need to clear all filter state.

6. **CSS animation restart requires DOM remount.** You can't restart a CSS animation by toggling a class — the browser doesn't re-trigger it. The solution: a keyed overlay div where the key changes each click, forcing React to unmount and remount.

7. **"Sleep on it" is a valid design decision.** The user saw the ripple mechanism work, said "it has potential," and chose to pause. Not every feature needs to be finished in one session.

## Open threads

- [ ] Ripple tuning — timing (0.7s per tier), intensity, number of cycles
- [ ] Should ripple also trace upstream (what informed this)?
- [ ] Pipeline bar glow CSS is still in index.css but unused — clean up?
- [ ] Vision surface needs a way to open without manual API call
- [ ] Connection lines only show in spatial mode — should dense mode hint at connections?
- [ ] The 24 seed items were created in a previous session — need a way to add items from the UI
- [ ] `data/vision-state.json` is not gitignored — should it be?

*The glow was always there. It just needed someone to open the tab.*
