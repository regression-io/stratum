# Functionality vs Use Cases: Gap Analysis

**Date:** 2026-02-13
**Status:** Draft
**Related:** [use-cases.md](../use-cases.md), [PRD.md](../PRD.md), [feature-map.md](../discovery/discovery-process/feature-map.md)

---

## What We Have (Inventory)

| Layer | What exists | Numbers |
|-------|------------|---------|
| **Data** | Items with type/phase/status/confidence, connections (5 edge types), JSON file persistence | 100 items, 129 connections |
| **Views** | 6 views: Roadmap (hierarchical drill-down), List, Board, Tree, Graph, Docs | 12 React components |
| **Server** | REST CRUD + WebSocket broadcast, summary/blocked endpoints, snapshot API | 11 endpoints |
| **CLI** | Create/update/delete/connect/search/list/show-status/show-ready/snapshot | 12 commands |
| **Canvas** | Multi-tab doc viewer with live file watching | Open/close API |
| **Terminal** | Embedded PTY with supervisor crash resilience | Singleton pattern |
| **Breadcrumbs** | Intent trail for session recovery | Append-only log |
| **Theme** | Dark/light with CSS token system | Toggle in sidebar |

### Data Model Expressiveness

- **10 item types**: feature, track, idea, decision, question, thread, artifact, task, spec, evaluation
- **8 statuses**: planned, ready, in_progress, review, complete, blocked, parked, killed
- **6 phases**: vision, specification, planning, implementation, verification, release
- **5 connection types**: implements, supports, informs, blocks, contradicts
- **Confidence**: 0-4 scale (untested → crystallized)

---

## ICP: Solo Developer with Claude Code

The seed user from use-cases.md. All analysis below is from their perspective.

### Daily Activities

| Activity | Frequency | Use Cases |
|----------|-----------|-----------|
| Morning orientation | Daily | UC-1 |
| Session setup | Per session (2-5/day) | UC-2 |
| Active development | Continuous | UC-3, UC-7 |
| Planning & decomposition | Weekly | UC-4, UC-6 |
| Decision making | As needed | UC-8 |
| Multi-track coordination | When parallelizing | UC-3, UC-5 |
| End-of-session capture | Per session | UC-9 |
| Recovery from interruption | On crash/context loss | UC-7 |

---

## Use Case Analysis

### UC-1: Where are we?

**Promise:** Open dashboard, see all initiatives/features/tasks with status. Under 10 seconds.

**What works today:**
- Roadmap view shows 4 features → 14 tracks → tasks in hierarchical drill-down
- Phase filter narrows to one lifecycle phase across all views
- Board view shows status distribution (43 planned, 44 complete, 9 in_progress)
- Summary endpoint gives counts by phase/status/type, open questions, blocked items, avg confidence
- Graph view shows connection topology

**What's missing:**
- **No "what changed since last session" view.** The user sees current state but not delta. No way to see "5 items moved to complete since yesterday" or "3 new items were created."
- **No critical path highlighting.** Graph shows connections but doesn't surface "these 3 items are blocking the most downstream work."
- **Blocked items aren't prominent.** The `/api/vision/blocked` endpoint exists but no UI surfaces it. You'd have to know to filter by status=blocked.
- **Confidence isn't actionable.** Dots show confidence level but there's no "low confidence items that need attention" view.

**Verdict: 70% covered.** The "look at the dashboard and understand current state" loop works. The "understand what matters right now" loop doesn't — there's no prioritization, no recency, no urgency signals.

---

### UC-2: What should this session work on?

**Promise:** View unblocked/unassigned work, claim one, get context briefing. 30 seconds.

**What works today:**
- `vision-track show-ready` lists items with status=planned and no blocking dependencies
- CLI can update status to in_progress (manual claim)
- Breadcrumbs provide intent trail for context
- Session context file (.claude/session-context.md) carries forward

**What's missing:**
- **No session concept.** No identity, no assignment, no "who's working on what."
- **No context briefing generation.** The developer manually writes session-context.md. Forge doesn't generate "here's what you need to know about this item."
- **No priority ordering.** `show-ready` lists everything unblocked but doesn't rank. The developer still picks manually.
- **No scope boundaries on items.** Items don't know which files/dirs they affect. Session can't be scoped.

**Verdict: 15% covered.** The data exists to answer "what's available" but the workflow (claim → brief → start) doesn't exist. This is Phase 2 per the PRD and correctly deferred, but the gap is large for the daily ICP activity of "start a new session."

---

### UC-3: Parallel agents went off the rails

**Promise:** Scope boundaries, acceptance criteria, completion gates. Agent stays in bounds.

**What works today:**
- Nothing. No policies, no scope enforcement, no gates.

**What partially helps:**
- Items have descriptions that could contain acceptance criteria (free text)
- The CLI could theoretically be used in a hook to check item status
- Breadcrumbs provide post-hoc audit trail

**Verdict: 5% covered.** Phase 3 per PRD. Correctly deferred. The ICP works around this with manual prompt engineering and hook-based conventions (breadcrumbs, self-preservation rules).

---

### UC-4: Breaking down a big initiative

**Promise:** Create top-level item → AI decomposition → review in UI → approve → work items ready.

**What works today:**
- Hierarchy exists: features → tracks → tasks with implements/supports connections
- Roadmap view provides visual drill-down through the hierarchy
- CLI creates items and connections programmatically
- ItemRow shows children inline with expand/collapse

**What's missing:**
- **No AI decomposition.** All breakdown is manual (human creates items via CLI or future UI).
- **No visual hierarchy editing.** Can't drag items to reorder, can't create children from the UI, can't draw connections visually.
- **No dependency graph editing.** Graph view is read-only.
- **No decomposition workflow.** No "select this item → request breakdown → review proposal → approve" flow.

**Verdict: 40% covered.** The data model handles it. The visualization works. The creation workflow is CLI-only and manual. For the ICP who's already in a Claude Code session, the CLI workflow is actually decent — they ask Claude to decompose and Claude runs `vision-track create` commands. But it's not the "visual decomposition" the PRD describes.

---

### UC-5: Cross-project feature tracking

**Promise:** Feature with child tasks scoped to each project. Dependencies enforce ordering. One-glance status.

**What works today:**
- Nothing cross-project. Single project only.

**What partially helps:**
- The hierarchy model could represent multi-project work (feature → project-scoped tracks)
- Items have no `project` field but could use tags/labels in description

**Verdict: 5% covered.** Phase 1 per PRD claims this is covered, but no project registry exists. The data model could represent it; the UI and CLI don't support it.

---

### UC-6: Product planning loop

**Promise:** Planning artifacts as work items. Status shows draft/reviewed/approved. Planning process managed as work.

**What works today:**
- Items represent specs, decisions, ideas, questions, threads — all planning artifacts
- `informs` connections link thinking to doing
- DocsView shows all docs with tracked/orphaned status
- Decision items have approve/reject actions in the detail panel
- Phase labels (vision, specification, planning) organize planning work
- Confidence levels indicate maturity of thinking

**What's missing:**
- **No inline editing.** Can't write artifact content in the detail panel — description is a text field, not a doc editor.
- **No artifact attachment.** Items reference docs by convention (description text) not by structured link. No "this item has these files attached."
- **No review workflow.** Status goes planned→complete but there's no "draft→reviewed→approved" lifecycle for docs specifically.
- **No visual connection between docs and items.** DocsView shows file existence; Roadmap shows items. The link between them is implicit.

**Verdict: 55% covered.** The ICP can create planning items, connect them, track status and confidence, and see them in multiple views. The loop works conceptually but the "artifact as first-class object" experience is weak — items point to docs by convention, not by structured reference.

---

### UC-7: Resuming after context loss

**Promise:** Previous session's progress visible. New session gets briefing. Picks up cleanly.

**What works today:**
- Breadcrumb trail shows intent history (what the previous session was doing and why)
- Session context file carries forward between sessions
- Snapshot API (just built) captures live UI state on demand
- Items track status, so partially-done work is visible as in_progress

**What's missing:**
- **No evidence log.** Items don't track "files changed", "tests run", or "commits made" per session.
- **No session-to-item linking.** Can't see "session 14 worked on these 5 items."
- **No automatic progress capture.** Status updates are manual (CLI calls).
- **No briefing generation.** The new session reads breadcrumbs and session-context.md manually.

**Verdict: 30% covered.** The building blocks exist (breadcrumbs, snapshot, session-context.md) but they're stitched together manually. The ICP recovers by reading files, not by asking Forge "what was happening."

---

### UC-8: Deliberation and decision-making

**Promise:** Decision as work item. Discussion captured. Arguments recorded. Outcome with rationale. `informs` links to downstream work.

**What works today:**
- Decision items exist (30 of them, most populated type)
- Description field holds rationale and options
- `informs` connections link decisions to specs/tasks
- Approve/reject actions on decision items in the detail panel
- Roadmap drill-down shows decisions within features
- Confidence level indicates certainty

**What's missing:**
- **No structured options.** Options live in description text, not as structured data. Can't "select Option B and record why."
- **No discussion capture.** No way to attach conversation excerpts or arguments for/against.
- **No conversation distillation.** No extraction of undocumented decisions from transcripts.
- **No rejected alternatives.** When a decision is approved, the rejected options aren't separately recorded.

**Verdict: 50% covered.** The ICP creates decisions, writes rationale in descriptions, connects them to downstream work, and approves them. The structured deliberation workflow (arguments → weigh → decide → record) is manual. For a solo dev this may be sufficient — they're both the arguer and the decider.

---

### UC-9: Planning session (session like this one)

**Promise:** Session as work item. Children created in real-time. Distillation at end. Everything captured.

**What works today:**
- CLI creates items during sessions (Claude runs `vision-track create` in terminal)
- Connections made in real-time
- Breadcrumbs capture intent trail
- Journal entries capture session narrative (manual, post-session)

**What's missing:**
- **No session-as-work-item pattern.** Sessions aren't represented on the board.
- **No real-time child creation from conversation.** Claude creates items when told to, not automatically.
- **No distillation.** No "review transcript, propose missing items" workflow.
- **No artifact linking.** Docs written during the session aren't automatically linked to items.

**Verdict: 25% covered.** The ICP uses the CLI during sessions and writes journal entries after. But the "session produces structured output automatically" promise is unmet. This is the F3 (Distill & Decide) gap.

---

## Summary Matrix

| Use Case | Coverage | Phase per PRD | Gap Severity |
|----------|----------|---------------|-------------|
| UC-1: Where are we? | **70%** | Phase 1 | **Medium** — works, needs urgency signals |
| UC-2: Session assignment | **15%** | Phase 2 | Low — correctly deferred |
| UC-3: Agent guardrails | **5%** | Phase 3 | Low — correctly deferred |
| UC-4: Decomposition | **40%** | Phase 1 | **Medium** — CLI works, no visual editing |
| UC-5: Cross-project | **5%** | Phase 1 | **High** — claimed Phase 1 but not built |
| UC-6: Planning loop | **55%** | Phase 1 | **Medium** — works conceptually, weak artifact linking |
| UC-7: Context recovery | **30%** | Phase 2 | Low-Medium — building blocks exist |
| UC-8: Deliberation | **50%** | Phase 1 | **Medium** — works for solo dev, no structured workflow |
| UC-9: Planning session | **25%** | Phase 1 | **High** — manual, no distillation |

### Where the ICP Actually Spends Time

Weighted by daily frequency for the solo-dev-with-Claude-Code ICP:

| Activity | Time/day | Current friction | Highest-impact fix |
|----------|----------|-----------------|-------------------|
| **Morning orientation** (UC-1) | 10-15 min | Opens Roadmap, gets current state. No "what changed" or "what needs attention." | Activity feed / delta view |
| **Session setup** (UC-2) | 5-10 min × 3 sessions | Manual: read breadcrumbs, write session-context.md, pick a task | Context briefing from item |
| **Active development** | 2-4 hours | Fine — terminal + canvas work. Breadcrumbs track intent. | N/A (working) |
| **End-of-session capture** (UC-9) | 10-15 min | Manual: update item statuses, write journal, update session-context.md | Auto-capture from session |
| **Planning & decisions** (UC-6, UC-8) | 30 min/week | CLI-driven: create items, write descriptions, connect. Adequate for solo. | Inline editing on items |
| **Recovery from crash** (UC-7) | 5 min/occurrence | Read breadcrumbs + session-context.md. Snapshot API helps. | Session replay / evidence log |

**The biggest daily time sinks are session setup (UC-2) and end-of-session capture (UC-9).** These are both Phase 2 features (session management). The ICP currently works around them with manual files and conventions.

---

## ICP Activity Walkthrough

### "I'm starting my day. What's the state of things?"

1. Open Forge → Roadmap view loads with 4 features, 14 tracks
2. Scan status colors — mostly planned (gray) and complete (green)
3. Click into a feature → see tracks → see tasks within each phase
4. Filter to "implementation" phase to see what's buildable
5. Check Board view for in_progress items (9 currently)

**Works.** But doesn't answer: "What changed overnight? What's newly unblocked? What's the most important thing right now?"

### "I'm starting a Claude Code session to work on a specific track"

1. `vision-track show-ready` → see planned items with no blockers
2. Pick one manually based on knowledge/judgment
3. `vision-track update <id> --status in_progress` → claim it
4. Read the item's description for context
5. Read related docs manually
6. Start working

**Works but slow.** No briefing, no scope, no "here's what you need to know." The developer carries context in their head.

### "I'm creating a new feature and breaking it down"

1. `vision-track create "Feature Name" --type feature --phase planning`
2. Think about decomposition
3. `vision-track create "Track 1" --type track --phase planning --connects-to <feature-id>:implements`
4. Repeat for each track/task
5. View in Roadmap to verify hierarchy looks right

**Works for solo dev in terminal.** But: no AI assistance, no visual editing, no "here's a suggested breakdown." The ICP talks to Claude in the terminal, Claude runs CLI commands. This is actually a decent workflow given the embedded terminal.

### "I need to make a decision about architecture"

1. `vision-track create "Decision: X vs Y" --type decision --phase design`
2. Write pros/cons in description
3. Think about it (or discuss with Claude in terminal)
4. Open in detail panel → click Approve
5. `vision-track connect <decision-id> <spec-id> --type informs`

**Works.** The solo dev is both the proposer and decider. The workflow is: think → record → decide → connect. For a team this would need discussion threads; for solo it's adequate.

### "My session crashed. I need to pick up where I left off"

1. New session starts, reads `.claude/session-context.md`
2. Read `.forge/breadcrumbs.log` for last intents
3. `vision-track list --status in_progress` to see what was active
4. Look at git diff/status for uncommitted work
5. Piece together what happened

**Works but fragile.** Depends on session-context.md being current. Breadcrumbs help. Snapshot API (once live) adds UI state. But there's no "here's exactly where you were and what to do next."

### "I want to see how my docs connect to my tracked work"

1. Switch to Docs view → see all files in `docs/`
2. Each file shows tracked/orphaned status
3. Switch to Graph view → see connection topology
4. Click an item → detail panel shows connections

**Works partially.** The docs→items link is implicit (same title, manual connection). There's no "click a doc → see all items it relates to" or "click an item → open its doc."

### "I'm running 3 parallel Claude Code sessions"

1. No coordination whatsoever
2. Each session works independently
3. Hope they don't conflict
4. Manually check git for merge conflicts after

**Doesn't work.** This is Phase 3-4 per PRD and correctly deferred. The ICP avoids parallelism or accepts the risk.

---

## Conclusions

### What's working well
1. **Data model is expressive.** 10 types, 5 connection types, 6 phases — captures the full product ontology.
2. **Multiple views serve different activities.** Roadmap for planning, Board for status, Graph for connections, List for filtering.
3. **CLI integration is natural.** An agent in the embedded terminal can create/update items as it works. This is actually a decent proxy for Phase 2 session management.
4. **Real-time sync works.** WebSocket broadcast means all views update instantly when CLI makes changes.
5. **Phase filtering works everywhere.** Sidebar filter narrows all views consistently.

### What's the biggest gap
1. **No "what needs attention" signal.** The dashboard shows state but not urgency. No activity feed, no "newly unblocked," no priority.
2. **No session lifecycle.** Session setup and teardown are manual. This is the biggest daily time cost for the ICP.
3. **No artifact-to-item linking.** Docs and items live in parallel worlds. DocsView and Roadmap don't cross-reference.
4. **No inline editing.** Items are created/edited via CLI or the small detail panel. No rich editing experience.

### What should we build next (for Phase 1 completeness)

Ranked by ICP daily impact:

1. **Activity/attention view** — "What changed? What's unblocked? What's low-confidence?" Answer UC-1's "what matters right now" gap.
2. **Item-to-doc linking** — Structured file references on items. Click item → open doc. Click doc → see items. Bridges DocsView and Roadmap.
3. **Inline item creation from UI** — Add items from within views (not just CLI). The Roadmap view is the natural place for this.
4. **Cross-project support** — The PRD claims this is Phase 1. Currently missing entirely.
