# Session 15: The Pressure Test

**Date:** 2026-02-13
**Focus:** Agent-driven challenge system, question workflow, revision history

## What happened

The human wanted a way to stress-test decisions — click a button, have an AI generate counter-questions, then work through them systematically. Simple idea. Three pivots to get there.

**Pivot 1: Terminal injection doesn't work.** First attempt was injecting a challenge prompt into the embedded terminal PTY. Problem: that's the same session we're running in. The prompt went to *us*. Human said: "you need a new terminal which is hidden."

**Pivot 2: Hidden agent subprocess.** Built `POST /api/agent/spawn` on the vision server — spawns `claude -p --dangerously-skip-permissions` as a detached child process. Hit the nested session guard (`CLAUDECODE` env var inherited). Fixed by stripping it from the spawn environment. Agents now run silently, create question items via `vision-track.mjs`, and results appear on the board via WebSocket.

**Pivot 3: The UI kept breaking.** Contradicts connections in the detail panel pushed it off screen. Moved to a dedicated ChallengeModal popup. Then question items showed the Pressure Test button (recursive). Then Discuss spawned inline agent text nobody wanted. Each fix was a scope correction — the human kept saying "no, simpler than that."

The real design emerged through the question workflow: **Discuss** injects context into the terminal for a real conversation. **Resolve** takes a text note and marks it complete. **Dismiss** kills it. No extra agents needed for discussion — the terminal is already an agent.

Then the human asked the right question: "shouldn't resolved questions show green in the parent view?" This led to questions getting their own section in ItemRow with green/yellow status indicators, the parent dot turning yellow while questions are open, and a resolution sparkle animation on the green left-border.

We used the system on itself — ran a pressure test on "Distinguish decision options from general informs edges", got three counter-questions, discussed one ("Why solve this in the graph edge at all?"), and the answer reframed the entire decision: options aren't edges, they're children. Updated the decision item and realized we needed revision history. Mocked it up as a collapsible History section parsed from description markers, created a roadmap item for the real implementation.

Final polish: centralized all ItemRow sizing into CSS custom properties (`--row-*` tokens), removed grey-out opacity on completed items, persisted UI state (activeView, breadcrumb, selectedItem) to sessionStorage so refresh doesn't kick you back to root.

**Breadcrumb rethink.** The breadcrumb was a click-trail — every drill-in pushed onto a stack, and navigating "back" via a link would push duplicates instead of popping. The human said: "make it like Windows Explorer — just show the path to here." Rewrote breadcrumbs as derived state: store only `currentItemId`, walk up the hierarchy via `parentId`/`implements`/`supports`/`contradicts` edges to build the path. No accumulation, no push/pop — always the true hierarchy path. Also added `contradicts` to `CHILD_EDGE_TYPES` so pressure test questions appear as children of their parent decision, not just linked items.

## What we built

### New files
- `src/components/vision/ChallengeModal.jsx` — Pressure test popup modal with challenge rows

### Modified files
- `server/vision-server.js` — Agent spawn infrastructure (spawn, poll, list endpoints)
- `server/terminal-server.js` — Terminal inject endpoint for Discuss
- `src/components/vision/ItemRow.jsx` — Question workflow, questions section, history section, CSS token sizing
- `src/components/vision/ItemDetailPanel.jsx` — Pressure test button, filtered contradicts
- `src/components/vision/VisionSurface.jsx` — Challenge modal state, action routing, sessionStorage persistence
- `src/components/vision/RoadmapView.jsx` — Simplified ItemFocusView, breadcrumb persistence fix
- `src/index.css` — Row sizing tokens, resolution sparkle animation

## What we learned

1. **Injecting into your own PTY is a no-op.** The terminal is already an active agent session. A separate subprocess is the right pattern for background AI work.
2. **Strip `CLAUDECODE` to nest Claude sessions.** The env var prevents accidental nesting — delete it from the spawn env to run intentional child agents.
3. **Three solutions to one problem means the problem is wrong.** The edge disambiguation question had three proposals. The pressure test question that killed it: "are options even edges?" The answer was hierarchy, not more edge types.
4. **The system tested itself.** We used pressure test → discuss → resolve to make an actual architectural decision. The feature proved itself in the session that built it.
5. **Discuss = terminal, not hidden agent.** The human's instinct: discussion is a conversation, not a throwaway text blob. The terminal is already the conversation surface.
6. **UI state must survive refresh.** SessionStorage for component state, URL hash + sessionStorage backup for breadcrumb. The race condition (hash cleared before items load) was the non-obvious bug.
7. **Centralize sizing in CSS, not inline styles.** One set of `--row-*` tokens controls the entire ItemRow scale. Change once, everything updates.
8. **Breadcrumbs should be derived, not accumulated.** A click-trail grows unbounded and breaks on back-navigation. Storing just the current item ID and walking up the hierarchy gives you the true path every time — like an address bar, not a history log.
9. **Questions are children, not just links.** `contradicts` edges belong in `CHILD_EDGE_TYPES`. Pressure test questions live under their parent decision in the hierarchy, not floating as linked items.

## Open threads

- [ ] Resolve remaining 1 open pressure test question (optionFor invariant)
- [ ] Build real revision history (roadmap item created, mock UI in place)
- [ ] Agent spawn needs cleanup: timeout handling, concurrent limit, error recovery
- [ ] Discuss prompt could be configurable per item type
- [ ] Resolution sparkle could be more dramatic — particles? confetti burst?

---

*The system pressure-tested itself and changed its own mind. That's either dogfooding or recursion.*
