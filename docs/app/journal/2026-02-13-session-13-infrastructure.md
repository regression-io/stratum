# Session 13: The Infrastructure Session

**Date:** 2026-02-13
**Focus:** Breadcrumbs, forge-loop, vision tracker design, terminal usability, design decisions

## What happened

This was a housekeeping session — the kind that doesn't produce flashy features but makes everything after it possible.

**Breadcrumb system.** We built the intent-tracking protocol: before each logical batch of edits, write a one-line breadcrumb to `.forge/breadcrumbs.log` with a timestamp and why. If the session dies mid-edit, the trail survives. Created the hookify rule to enforce it automatically.

**Forge-loop skill.** When implementation touches 3+ files or large files, delegate to subagents instead of reading everything into context. The pattern: stay lean, decompose, breadcrumb, dispatch, integrate, checkpoint. Your context is finite; the files survive on disk.

**Vision Tracker design doc.** Wrote `docs/plans/2026-02-13-vision-tracker-design.md` — the end-to-end design for structured tracking replacing ROADMAP.md. REST + WebSocket server, CLI tool, file-backed JSON store, Vision Surface views.

**Terminal usability fixes.** History was merging across reconnects (confusing). Tool use output from Claude Code was visible and noisy. Fixed: added reconnect separators, investigated PTY spawn env for verbosity detection, sent Ctrl+O on terminal start to toggle verbose mode off.

**Design decisions on the board.** Created D1-D9 decision items on the Vision Tracker for design doc approval. Added approve/reject action buttons to the detail panel. This was the first time the tracker tracked its own design decisions.

**Mockup infrastructure.** Added HTML/iframe view to the canvas so static mockups could be viewed inline. Created four drill-down mockup HTMLs exploring navigation patterns.

**Light mode fixes.** Item colors in light theme were too washed out — bumped to blue/purple range that reads in both themes.

## What we built

- `.claude/rules/breadcrumbs.md` — Breadcrumb intent tracking protocol
- `.claude/rules/forge-loop.md` — Coordinate-don't-execute delegation rule
- `docs/plans/2026-02-13-vision-tracker-design.md` — Vision Tracker design doc
- `docs/mockups/drill-down-*.html` — 4 drill-down navigation mockups
- Terminal usability fixes (reconnect separator, verbose mode toggle)
- Approve/reject buttons on detail panel
- HTML/iframe canvas view
- Light theme color fixes

## What we learned

1. **Breadcrumbs are cheap insurance.** One line before each batch of edits. If the session dies, the next agent knows what was in progress.
2. **Agent context is the bottleneck, not agent capability.** The forge-loop exists because filling context with source code kills the session. Delegation is a survival strategy.
3. **Design decisions need their own items.** When D1-D9 went on the board, the tracker started tracking its own evolution. First sign of dogfooding.
4. **Static mockups are conversation accelerators.** The four drill-down HTMLs let the human see and compare options faster than any text description could.

## Open threads

- [ ] Sessions 13-14 journal entries (this is one of them)
- [ ] Codify the roadmap as a proper doc
- [ ] ~16 modified files from Sessions 12-13 still uncommitted

---

*The session that built the rails everything else runs on.*
