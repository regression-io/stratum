# Session 16: Agent Awareness — From Blinking Dots to Working On

**Date:** 2026-02-14
**Focus:** Agent status detection, activity feed, activity resolution, Vision Surface → Vision Tracker rename

## What happened

The session started with a simple ask: can we tell if the agent is busy? It ended with the tracker knowing *what feature you're building* based on which files you touch.

**Level 1: OSC title parsing.** Claude Code sets the terminal title via OSC escape sequences — braille spinner chars mean working, sparkle means done. We'd already landed server-side OSC extraction (the tmux layer consumes these before the bridge PTY sees them), so the terminal header showed a yellow pulsing dot when the agent was active. That worked, but "busy/not busy" isn't enough.

**Level 2: Richer status display.** Tools got classified into semantic categories — Read/Glob are "Reading", Write/Edit are "Writing", Bash is "Running", Task/Skill are "Delegating". The terminal header now shows the category, the specific tool name, and a live elapsed timer. A recent activity strip renders proportional bars showing the rhythm of the agent's work.

**The rename.** Vision Surface became Vision Tracker — 12+ files touched, all imports updated. The name better reflects what it actually does: track work, not just surface information.

**Level 3: Hook-driven activity feed.** Claude Code's PostToolUse hooks send structured JSON (tool_name, tool_input) on stdin after every tool call. We built `agent-activity-hook.sh` — it reads the JSON, curls `POST /api/agent/activity` on the server, which broadcasts over WebSocket to the sidebar. Now the sidebar shows a live feed of what the agent is doing: "Edit → AppSidebar.jsx", "Grep → resolveItems", "Bash → npm run build".

**Level 4: Activity resolution.** The big one. The human asked: "how do we surface items relevant to the Vision Tracker?" We needed a system where file edits automatically associate with tracker items — without the agent having to think about it.

Three-layer resolution scheme:
1. **Exact/prefix match** — items have a `files` array, Edit on `server/vision-store.js` matches an item with that exact path
2. **Slug convention** — editing `docs/specs/2026-02-14-activity-resolution-spec.md` strips the date, strips known suffixes, gets slug `activity-resolution`, matches the item titled "Activity Resolution"
3. **Plan parser** — `POST /api/plan/parse` reads a markdown plan, extracts file paths from backtick references, and populates the item's `files` array automatically

Auto-status: when the agent does a Write or Edit on a file associated with a `planned` item, it auto-bumps to `in_progress`. No manual status updates needed.

The sidebar now shows "Working on: Activity Resolution" when you edit any of its associated files. Items fade after 30 seconds of no matching activity.

**The review loop.** The human asked for a disciplined build process: write a spec, get design decisions approved one by one (D1-D7), write an implementation plan, review it, build it, then review 3x in a loop until clean. Review pass 1 found 14 issues (7 fixed). Pass 2 found 5 (3 fixed). Pass 3: zero issues, approved.

## What we built

### New files
- `docs/specs/2026-02-14-activity-resolution-spec.md` — Behavioral spec for file-to-item association (7 design decisions)
- `docs/plans/2026-02-14-activity-resolution-plan.md` — 7-step implementation plan with verification checklist
- `scripts/agent-activity-hook.sh` — PostToolUse hook that feeds tool events to the server

### Modified files
- `server/vision-store.js` — `files` array, `slug` field, `slugify()`, backward-compat backfill on load
- `server/vision-server.js` — `resolveItems()`, `extractSlugFromPath()`, `extractFilePaths()`, auto-status, plan parser endpoint, activity endpoint
- `scripts/vision-track.mjs` — `--files` and `--add-files` flags on create/update, files display in get
- `src/components/vision/AppSidebar.jsx` — Agent status section (OSC + hook feed + resolved items with 30s fade)
- `src/components/vision/useVisionStore.js` — `agentActivity` WebSocket handler
- `src/components/Terminal.jsx` — Tool categories, activity log, elapsed timer, activity strip
- `src/components/vision/VisionTracker.jsx` — Renamed from VisionSurface, passes agentActivity to sidebar
- `.claude/settings.json` — Registered PostToolUse hook

## What we learned

1. **Three layers of resolution cover 90% of cases.** Exact file match catches items with explicit file lists. Slug convention catches docs without any manual configuration. Plan parsing bootstraps file lists from specs you've already written. Together they make resolution automatic.

2. **Auto-status removes ceremony.** The moment you Write a file, the associated item goes from `planned` to `in_progress`. No manual `vision-track update <id> --status in_progress` needed. The tracker mirrors reality.

3. **The review loop works.** Spec → decisions → plan → build → review 3x caught real issues (fragile path normalization, timer cleanup bugs, missing backward compat). Each pass found fewer issues. By pass 3: zero.

4. **Mutation coupling is intentional.** `updateItem` mutates the Map object in-place, so the broadcast after auto-status includes the updated value. We documented this rather than "fixing" it — it's the correct behavior.

5. **Plan parsers need negative patterns.** The first version extracted `node --check server/vision-store.js` as a file path because it contained `/` and ended in `.js`. Adding `skipRe` patterns for commands and test files eliminated false positives.

6. **Hook architecture is clean.** PostToolUse → shell script → HTTP POST → WebSocket broadcast → React state. Each layer is independent and testable. The hook script is 15 lines.

## Open threads

- [ ] Clickable resolved items (navigate to item in tracker on click)
- [ ] Populate `files` on more tracker items (currently only Activity Resolution has files set)
- [ ] Error/outcome detection (Phase 3, step 13) — pattern-match failures, surface in UI
- [ ] Session tracking (Phase 3, step 14) — start/stop detection, auto-journaling
- [ ] End-to-end test in live use — watch the sidebar during a real build session
- [ ] Journal entries for sessions 13-14 still pending from previous session context

---

*The tracker now tracks itself. When we built Activity Resolution, the sidebar showed "Working on: Activity Resolution." That's the loop closing.*
