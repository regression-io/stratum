# Forge: Use Cases

**Date:** 2026-02-11
**Status:** LIVING — new use cases added as they're discovered through dogfooding
**Related:** [brainstorm.md](./brainstorm.md), [PRD.md](./PRD.md)

---

## Seed User: Solo developer managing a 10-project monorepo with Claude Code

All use cases below are drawn from real scenarios managing SmartMemory development.

---

### UC-1: Where are we?

**Trigger:** Developer opens a new day or returns after a break.

**Today:** Read session context files, scan ROADMAP.md (660 lines), check gaps.md, grep through 62 plan files, check git status across repos. Takes 10-15 minutes to build a mental model of project state.

**With Forge:** Open the dashboard. See all initiatives, features, and tasks with their status. See what's in progress, what's blocked, what completed since last session. Under 10 seconds.

**Primitives used:** Work (hierarchy + state), visual dashboard

---

### UC-2: What should this session work on?

**Trigger:** Developer starts a new Claude Code session.

**Today:** Manually review what's unblocked, what's highest priority, what has enough context to start. Write a detailed prompt with all relevant state. Takes 5-10 minutes per session.

**With Forge:** View unblocked, unassigned work items sorted by priority. Claim one. Forge generates a context briefing with everything the session needs: what to do, acceptance criteria, scope, what other sessions are doing.

**Primitives used:** Work (state, dependencies), Session (assignment, context)

---

### UC-3: Parallel agents went off the rails

**Trigger:** Developer dispatched 3 parallel Claude Code sessions to write integration tests. All 3 guessed at URL paths and response shapes instead of reading actual routes. Result: 50 failing tests.

**Today:** No way to constrain what agents do. No way to verify work before it lands. Discovery happens only when you run the tests yourself.

**With Forge:** Each task has scope boundaries (which files to read, which routes to test). Acceptance criteria include "pytest passes for new tests." Completion gate policy set to gate mode — agent can't mark done until tests pass. If an agent produces failing tests, it stays in_progress and the dashboard shows it.

**Primitives used:** Work (scope, acceptance criteria), Policy (scope enforcement + completion gate), Session (assignment)

---

### UC-4: Breaking down a big initiative

**Trigger:** Developer decides to build "Reasoning System v2" — a multi-week effort spanning core library, service, SDK, and frontend.

**Today:** Write a design spec manually. Create a plan file with phases and checkbox tasks. Hope you thought of everything. No visual representation of dependencies.

**With Forge:** Create a top-level work item. Request AI decomposition. Forge proposes features, phases, tasks with dependencies and scope boundaries. Developer reviews the breakdown visually — sees the dependency graph, adjusts ordering, adds/removes items, sets policies. Approves. Work items are ready for sessions to claim.

**Primitives used:** Work (hierarchy, dependencies), Policy (decomposition gate), visual dashboard (dependency graph)

---

### UC-5: Cross-project feature tracking

**Trigger:** A feature like "add decisions API" needs changes in smart-memory-service (routes), smart-memory-client (SDK methods), smart-memory-sdk-js (JS SDK), contracts (data shapes), and smart-memory-web (UI).

**Today:** Track this in your head or in a plan file. Easy to forget to update the JS SDK or the contracts. No visibility into which pieces are done and which aren't.

**With Forge:** The feature work item has child tasks scoped to each project. Dependencies enforce ordering (service before SDK, contracts before both). Dashboard shows: service task complete, Python SDK in progress, JS SDK blocked, frontend planned. One glance tells you exactly where the cross-project work stands.

**Primitives used:** Work (hierarchy, scope, dependencies), visual dashboard (cross-project view)

---

### UC-6: Product planning loop

**Trigger:** Developer is brainstorming a new product (like Forge itself). The process is iterative: brainstorm → use cases → PRD → design, with feedback loops between all stages.

**Today:** Create markdown files manually. Track relationships in your head. No visual representation of how brainstorm findings connect to PRD features connect to use cases.

**With Forge:** Create a work item for the product. Attach artifacts (brainstorm doc, PRD, use cases) to work items at appropriate levels. Child work items represent the planning activities themselves. Status shows which planning artifacts are draft vs. reviewed vs. approved. The planning process is itself managed as work.

**Primitives used:** Work (hierarchy, artifacts, state), visual dashboard

---

### UC-7: Resuming after context loss

**Trigger:** A Claude Code session hit its context limit or crashed mid-task. A new session needs to pick up where the old one left off.

**Today:** Read the session context file (if one was written). Try to reconstruct what was done and what remains. Often start over or miss things.

**With Forge:** The previous session's progress was reported in real-time: files changed, tests run, partial completions. The work item shows exactly what's done and what's not. New session claims the same work item and gets a briefing that includes the previous session's evidence. Picks up cleanly.

**Primitives used:** Work (evidence), Session (context briefing), Policy (assignment)

---

### UC-8: Deliberation and decision-making

**Trigger:** A design question arises during planning or development. Needs discussion, arguments for/against, and a recorded decision with rationale.

**Today:** Discussion happens in a Claude Code chat session or a meeting. Reasoning and rejected alternatives live in the transcript. Outcomes are manually extracted into markdown files. The rationale is lost or buried. When someone later asks "why did we decide X?", it takes archaeology to reconstruct.

**With Forge:** The question becomes a Work item (label: "decision"). Discussion is captured as an artifact — inline markdown, not an external file. Arguments for and against are recorded. When the decision lands, the Work item moves to `complete` with the outcome, rationale, and rejected alternatives as artifacts. The decision `informs` downstream Work items (specs, tasks) via dependency relationships. When those downstream items are opened, the decision and its rationale are linked and visible. Conversation distillation extracts any undocumented decisions, open questions, and action items from session transcripts and proposes them as Work items.

**Primitives used:** Work (hierarchy, artifacts, evidence), Dependency (`informs`), Session (transcript as evidence), distillation (transcript → structured outcomes)

---

### UC-9: Session like this one

**Trigger:** A planning session covers multiple topics — brainstorming, evaluation, decisions, process design — in a single conversation. Topics emerge organically, feed into each other, and produce artifacts that need to land in the right places.

**Today:** Everything happens in a chat transcript. Outcomes are manually captured as separate files. Cross-references are added by hand. Easy to miss capturing a decision, lose rationale, or forget to update downstream docs. The session is productive but the outputs are fragile.

**With Forge:** The session is a Work item (label: "planning-session"). As topics emerge, child Work items are created in real-time — each brainstorm, decision, evaluation is a child. Artifacts are written inline on each child. When a decision informs a spec, the `informs` dependency is created immediately. At session end, distillation reviews the transcript against what was captured and proposes any missing items. The session Work item shows everything that was produced, decided, and what still needs follow-up.

**Primitives used:** Work (hierarchy, artifacts, evidence), Dependency (`informs`, `blocks`), Session (transcript, distillation), memory (learnings persisted)

---

## Use Case Validation Matrix

| Use Case | Work | Policy | Session | Dashboard | Phase 1 | Phase 2 | Phase 3 | Phase 4 |
|----------|------|--------|---------|-----------|---------|---------|---------|---------|
| UC-1: Where are we? | hierarchy, state | - | - | overview | x | x | x | x |
| UC-2: Session assignment | state, deps | - | assign, context | available work | - | x | x | x |
| UC-3: Agent guardrails | scope, criteria | scope, completion gate | assignment | status | - | - | x | x |
| UC-4: Decomposition | hierarchy, deps | decomposition gate | - | dependency graph | x | x | x | x |
| UC-5: Cross-project | hierarchy, scope | dependency gate | - | cross-project view | x | x | x | x |
| UC-6: Planning loop | hierarchy, artifacts | - | - | artifact view | x | x | x | x |
| UC-7: Context recovery | evidence | assignment | context briefing | session history | - | x | x | x |
| UC-8: Deliberation | artifacts, deps | - | transcript | artifact view | x | x | x | x |
| UC-9: Planning session | hierarchy, artifacts | - | transcript, distillation | real-time children | x | x | x | x |

**Phase 1 covers:** UC-1, UC-4, UC-5, UC-6, UC-8, UC-9 (planning, visibility, and deliberation)
**Phase 2 adds:** UC-2, UC-7 (session management)
**Phase 3 adds:** UC-3 (policy enforcement)
**Phase 4 adds:** real-time monitoring, parallel coordination

**Note:** UC-8 and UC-9 are Phase 1 because they require only Work items, artifacts, and dependencies — no agent integration or policy enforcement. These are the use cases that validate Forge as a knowledge work tracker, not just a task tracker.
