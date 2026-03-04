# Integration Roadmap: Bootstrap to Self-Hosting

**Date:** 2026-02-11
**Status:** SUPERSEDED — see [docs/ROADMAP.md](../ROADMAP.md) for the live roadmap
**Preserved for:** history, narrative context, Phase 0 detail not in the canonical roadmap
**Related docs:** [Taxonomy](../taxonomy.md), [UI-BRIEF](../UI-BRIEF.md), [PRD](../PRD.md), [Base44 Evaluation](../evaluations/2026-02-11-base44-ui-eval.md)

---

## Guiding Principle

Compose must be able to manage its own development. The concrete goal: **a planning session like the one that produced these docs happens entirely inside Compose.**

Every step is measured against: can we stop doing out-of-band coordination after this?

---

## Phase 0: Bootstrap

Manual, out-of-band work. None of this is tracked in Compose.

### 0.1 Discovery + Requirements + Design — DONE

- Brainstorm, use cases, PRD, UI-BRIEF produced
- Decisions made: deterministic UI, deliberation-as-work, connector architecture, taxonomy
- Process docs: delivery intake, spec writing

### 0.2 External Build + Verification — DONE

- UI-BRIEF sent to Base44 as behavioral spec
- Delivery received and evaluated
- Gaps classified: 2 structural, 10 functional, 5 expected, 5 surplus
- Full evaluation: [Base44 Evaluation](../evaluations/2026-02-11-base44-ui-eval.md)

### 0.3 Terminal Embed + First Boot — DONE

Embedded Claude Code in the UI via xterm.js + WebSocket + node-pty. First real boot exposed crash resilience gaps.

- Terminal component with PTY backend: WebSocket JSON protocol
- First boot crashed: unprotected `ws.send()` + no process error handlers + backgrounded server hid evidence
- **Fixes:** Process supervisor with auto-restart, client WebSocket reconnection with health check, try/catch on all WebSocket sends, server log capture
- **Decision:** Terminal first, chat UI later (Q1 answered)
- **Decision:** Claude Code CLI via shell+WebSocket (Q2 answered)
- Journal: [Session 1: First Boot](../journal/2026-02-11-session-1-first-boot.md)
- **Gate:** ✅ Can type `claude` in embedded terminal, survives server restart

### 0.3.5 Discovery Level 2 — IN_PROGRESS

**Deeper brainstorming below the high-level constructs.** Level 1 defined the working dimensions (What, How, Why-factual) and the knowledge layer. Level 2 goes one layer deeper — how these dimensions manifest mechanically, what the user actually touches, how the AI reasons underneath.

- Active focus until explicitly moved on
- See: [Discovery Process](../discovery/discovery-process/README.md)
- See: [Work Tracking Meta-Structure](../discovery/2026-02-11-work-tracking-meta-structure.md)

### 0.4 Persistence Connector — PARKED

**Unblocks everything.** Without durable storage, nothing works. Parked while discovery continues.

- Define persistence interface (CRUD for all entities)
- Implement as markdown-in-folders with frontmatter (human-readable, git-friendly, portable)
- Cross-linking via relative paths between markdown files
- Replace `src/api/base44Client.js` and Base44 auth
- Design: [Persistence Connector Plan](2026-02-11-persistence-connector-plan.md)
- **Gate:** Can we create Work items and see them after restart?

### 0.5 Agent Monitoring (Level 1) — PLANNED

The terminal is a black box. Compose can't see what the agent is doing, what errors it's hitting, or what state it's in. Minimum observability before self-hosting.

- Pattern-match PTY output for known error signatures (API errors, stack traces, process exits)
- Surface agent health status in the UI (beyond the connection dot)
- Log agent events to `.compose/sessions/` for post-mortem analysis
- **Gate:** When Claude Code hits an API error inside the terminal, Compose logs it and surfaces it

### --- EARLY HANDOFF: Compose tracks its own work from here ---

---

## Phase 1: Discovery Support (make thinking capturable)

**Goal:** Compose can host a planning/brainstorming session. This is the most urgent gap — it's what we can't do today.

### 1.1 Rich Artifact Editor

The Base44 UI has artifacts as attachments only. We need inline markdown editing — living documents created and edited inside Compose.

- Markdown editor in Work item detail view (edit + preview toggle)
- Create, edit, preview artifacts inline — not just file attachments
- **Gate:** Can we write a brainstorm doc directly in a Compose Work item?

### 1.2 Artifact Versioning

Artifacts evolve. Specs get revised, decisions get amended. Changes need to be visible.

- Change history on artifacts (who changed what, when)
- Diff view between artifact versions
- **Gate:** Can we see how the UI-BRIEF changed over the course of a session?

### 1.3 Cross-Artifact Linking

A decision references the spec it changed. An evaluation references the spec it evaluated against. Artifacts need to link to each other, not just to their parent Work item.

- Link artifacts across Work items (bidirectional)
- Links visible in artifact view and in Work item detail
- **Gate:** A decision artifact links to the spec artifact it modified

### 1.4 `informs` Dependency Type

Base44 only implements `blocks`. Deliberation needs `informs` — the knowledge relationship that connects thinking to doing.

- Add `informs` and `relates_to` to dependency UI
- Show `informs` links in Work item detail
- Show `informs` edges in dependency graph (visually distinct from `blocks`)
- **Gate:** Can we link a Decision to the Spec it informed?

### 1.5 Propagation Awareness

When a decision completes or an artifact changes, downstream items may be stale. Surface this.

- When a Work item with `informs` dependencies completes, flag downstream items for review
- Show "last updated before dependency completed" indicator
- **Gate:** Completing a decision highlights which specs may need updating

### 1.6 Phase and Type Labels

The taxonomy defines two label dimensions (phase + type). The UI needs to support this as a first-class concept.

- Default label sets: phase labels (discovery, requirements, design, planning, implementation, verification, release) and type labels (task, decision, evaluation, brainstorm, spec, poc, process)
- Group-by-phase in dashboard
- Filter by phase and type independently
- **Gate:** Can we group the dashboard by phase and see lifecycle progress?

### 1.7 Work Item Templates

Selecting a type pre-fills sensible defaults. Reduces ceremony for common patterns.

- Template per cross-cutting type (decision, evaluation, brainstorm, spec)
- Template per phase with default acceptance criteria
- Templates are suggestions, not enforced
- **Gate:** Creating a "decision" Work item pre-fills: question, rationale, rejected alternatives

### 1.8 Evaluation Templates

Gap classification (structural/functional/expected/surplus) should be a structured interaction, not free text.

- Evaluation view with gap categories
- Each gap row can become a child Work item with one click
- **Gate:** Doing a delivery intake produces classified gaps that convert to Work items

**Phase 1 exit:** We can run a planning session inside Compose — write docs inline, record decisions with rationale, link decisions to specs via `informs`, see what's stale when decisions change, classify gaps into work items.

---

## Phase 2: Requirements + Design Support (make defining and deciding structured)

### 2.1 Acceptance Criteria Linking

Criteria defined in Requirements should trace forward to Verification. When evaluating a delivery, criteria from the spec are the checklist.

- Link acceptance criteria across Work items
- Verification items can reference the criteria they evaluate
- **Gate:** Evaluating a delivery shows the spec's criteria as a checklist

### 2.2 Decision Workflow

Decisions follow: raised → discussing → proposed → decided. The outcome should propagate to downstream items.

- Status transitions for decision-type Work items
- When a decision completes, surface downstream `informs` items that may need updating
- Decision record template: question, context, decision, rationale, alternatives, implications
- **Gate:** Completing a decision flags "these specs may need updating"

### 2.3 Spec ↔ Delivery Traceability

Specs produce deliveries. Deliveries are evaluated against specs. The chain should be visible.

- Spec artifact → linked to Build work item → linked to Evaluation work item
- Gap classification (structural/functional/expected/surplus) as evaluation template
- Gaps auto-generate child Work items
- **Gate:** Can we do a delivery intake entirely inside Compose?

**Phase 2 exit:** The full cycle — spec → build → evaluate → gaps → new work items — is tracked and linked inside Compose.

---

## Phase 3: Planning + Implementation Support (make building trackable)

### 3.1 Functional Gaps from Base44 Evaluation

These become Work items tracked inside Compose (after Phase 1 enables that):

- Keyboard navigation (command palette, tree nav, shortcuts)
- Scope field UI
- Tags field UI
- History/activity log
- Group-by in dashboard
- Saved filter presets
- Drag-to-reorder hierarchy
- Circular dependency warning
- Error boundaries and user feedback
- Hardcoded strings → constants

### 3.2 Conversation Distillation

Sessions produce transcripts. Distillation extracts structured outcomes.

- Transcript → decisions, questions, action items, learnings
- Propose extracted items as draft Work items for human review
- **Gate:** End a session, see proposed Work items extracted from the conversation

### 3.3 Memory System

Persistent knowledge that accumulates across sessions.

- Project-level and global memory
- Surfaced in context briefings
- Updated from distillation and explicit user action
- **Gate:** A new session knows what was learned in previous sessions without re-reading everything

**Phase 3 exit:** Implementation work is fully trackable. Conversations feed back into the system automatically.

---

## Phase 4: Connectors (make the system pluggable)

### 4.1 Git/File Connector

Link Work items to real code changes without manual entry.

- Commits, branches, file changes → evidence on Work items
- Auto-detect activity in registered projects
- **Gate:** Compose's own git activity surfaces on its Work items

### 4.2 Agent Connector (Read-Only)

See what sessions are doing.

- Expose Claude Code session activity to Compose
- Map sessions to Work items
- **Gate:** See active sessions and what they're working on

### 4.3 Agent Connector (Read-Write)

Direct sessions from Compose.

- Assign work to agents
- Context briefings from Compose
- Policy enforcement (gate/flag/skip)
- **Gate:** Direct a Claude Code session from inside Compose

**Phase 4 exit:** Full bootstrap complete. All work — thinking, deciding, building, evaluating — happens in Compose. No more out-of-band coordination.

---

## Phase 5: Standalone App (make it installable)

Compose becomes a standalone tool you install and run, not a dev project you `npm run dev`.

Reference implementation: coder-config's deployment architecture.

### 5.1 macOS LaunchAgent

Run Compose as a background service that starts on login and survives crashes.

- Generate `.plist` for `~/Library/LaunchAgents/` with `KeepAlive: true`, `RunAtLoad: true`
- `compose ui install` / `compose ui uninstall` commands
- Logs to `~/.compose/compose.log`
- `process.exit(0)` triggers launchd restart with new code
- **Gate:** `compose ui install` → Compose runs on login, restarts on crash, no terminal needed

### 5.2 Version-Aware Restart

Detect when Compose's code has been updated and restart to pick up changes.

- Server stores startup version, `/api/version` compares against on-disk version
- `needsRestart` flag when versions diverge
- UI shows update banner, user clicks to restart
- `/api/restart` → `process.exit(0)` → supervisor/launchd restarts with new code
- **Gate:** Update Compose code, UI shows "restart to update", one click picks up changes

### 5.3 Suspend/Resume Watchdog

Detect system sleep and restart cleanly on wake.

- Heartbeat interval (5s), detect gaps > 30s as suspend
- On resume: exit and restart to reset WebSocket state, reconnect terminals
- Prevents stale connections and zombie PTY sessions after laptop sleep
- **Gate:** Close laptop, open it, Compose recovers automatically

### 5.4 CLI + Package Distribution

Ship as an installable package (`npm install -g compose` or similar).

- CLI entry point: `compose ui`, `compose ui status`, `compose ui stop`
- Pre-built UI assets (no Vite in production)
- Serve static dist/ instead of proxying to Vite
- npm/Homebrew distribution
- **Gate:** `npm install -g compose && compose ui` → working app, no clone needed

**Phase 5 exit:** Compose is a standalone tool anyone can install, run, and forget about. It starts on login, survives crashes and sleep, updates itself, and needs no dev environment.

---

## Phase 6: Lifecycle Engine

The `/compose` skill becomes the product. Seven layers: user preferences → lifecycle state machine → artifact awareness → policy enforcement runtime → gate UI → session-lifecycle binding → iteration orchestration. Layer 3 (policy runtime) is the core new build — everything else extends Phases 3-5 infrastructure.

See: **[Lifecycle Engine Roadmap](2026-02-15-lifecycle-engine-roadmap.md)**

**Phase 6 exit:** Compose enforces the `/compose` lifecycle structurally. Gates block, policies inherit, iterations are orchestrated, artifacts are managed. The process runs through Compose, not alongside it.

---

## Phase 7: Agent Abstraction (Post-V1)

Agent-agnostic lifecycle with agent-specific connectors. Claude Code, Codex, Gemini run the same pipeline through adapter pattern.

See: **[Lifecycle Engine Roadmap](2026-02-15-lifecycle-engine-roadmap.md)** Layer 7.

---

## Invariants (hold true across all phases)

- Every item is a Work item with the same fields and status lifecycle
- Hierarchy, dependencies, artifacts, evidence — always available
- Policies (gate/flag/skip) — always applicable
- The 5 UI views — same views for all work types
- Connectors are swappable — persistence, agents, UI

See [Taxonomy](../taxonomy.md) for the full invariant/variant breakdown.

---

## Process Docs (produced during bootstrap)

- [Delivery Intake](../process/delivery-intake.md) — evaluate external deliveries
- [Spec Writing](../process/spec-writing.md) — write behavioral specs
- [Taxonomy](../taxonomy.md) — project lifecycle phases, invariants, variants
