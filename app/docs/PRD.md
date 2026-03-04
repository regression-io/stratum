# Compose: Product Requirements Document

**Date:** 2026-02-11
**Status:** LIVING DRAFT — evolves as use cases are collected and the product is built
**Related:** [brainstorm.md](./brainstorm.md), [use-cases.md](./use-cases.md)

---

## Vision

Compose is a mission control system for AI-driven software development. It gives developers a visual command center to plan, track, and direct AI agents building software — replacing scattered markdown files, mental models, and context-switching with structured, visual, policy-driven project management.

## Target User

A developer using AI coding agents (starting with Claude Code) to build software across projects of any scale — from a single feature to a multi-initiative, multi-repo product. They may be solo or working with a team of humans and AI agents in parallel.

## Core Problem

AI coding agents are powerful executors but have no persistent awareness of where a project stands, what to work on next, or what constraints to respect. Developers currently maintain this in their heads, in scattered documents, or not at all — leading to:

- No way to see the big picture across all work
- Significant time spent orienting at the start of each session
- No coordination when multiple agent sessions run in parallel
- Agents going off-rails without structured constraints
- No visual way to track progress across complex, multi-track projects

## Core Axiom

Every decision point in the system is a 3-mode dial:

| Mode | Behavior | Human Role |
|------|----------|------------|
| **Gate** | Blocked until human decides | Decider |
| **Flag** | Agent proceeds, human notified | Reviewer |
| **Skip** | Agent proceeds silently | Delegator |

This single primitive applies to every policy in the system. Modes inherit downward through the work hierarchy with override at any level.

---

## Feature Areas

### 1. Work Hierarchy

Structured, nested representation of everything that needs to get done.

**1.1 Arbitrary-depth nesting**
- Work items can contain other work items to any depth
- Labels are user-defined (initiative, feature, phase, task, or custom)
- Minimum unit is a single work item; hierarchy scales up as needed

**1.2 Work item properties**
- Name, description, labels/tags
- Status lifecycle: `planned → ready → in_progress → review → complete` (plus `blocked`, `parked`)
- Acceptance criteria (list of verifiable conditions for completion)
- Evidence log (what was produced: commits, test results, files changed)

**1.3 Dependencies**
- Work items can block or be blocked by other work items
- Dependencies can cross hierarchy levels (task blocks a feature, feature blocks an initiative)
- System surfaces what's unblocked and ready to start

**1.4 Scope boundaries**
- Work items can define which files, directories, or projects are in scope
- Children inherit parent scope unless overridden

### 2. Policy System

Configurable rules governing how work gets done, enforced at the level the user chooses.

**2.1 Policy types**
- **Start gate**: Can this work item begin? (e.g., dependencies met, human approved)
- **Completion gate**: Can this be marked done? (e.g., tests pass, criteria met, human reviewed)
- **Scope enforcement**: Is the agent working within defined boundaries?
- **Decomposition gate**: Can this work item be broken into sub-items?
- **Assignment gate**: Can an agent claim this work?
- **Budget limit**: Has time, token, or file-change budget been exceeded?

**2.2 Three-mode enforcement**
- Every policy is gate, flag, or skip
- Mode is configurable per policy, per work item
- Defaults can be set at any hierarchy level and inherited downward
- Human can override any inherited mode at any level

**2.3 Project rules**
- Reusable rule sets that can be attached to work items or applied globally
- Capture conventions like "update CHANGELOG with code changes", "prefer integration tests over mocks", "only touch files in X directory"
- Rules are policies with criteria expressed as natural language or verifiable commands

### 3. Session Management

Track and coordinate actors (humans and AI agents) working on the project.

**3.1 Session identity**
- Each Claude Code instance, human in the UI, or other agent is a named session
- Sessions are visible in the dashboard showing what they're working on

**3.2 Assignment**
- Sessions claim work items; the system evaluates policies against the claim
- A work item can be assigned to one session at a time
- Multiple sessions can work in parallel on different work items

**3.3 Context briefing**
- When a session starts, it receives a briefing: assigned work, acceptance criteria, scope boundaries, relevant policies, what other sessions are doing
- The briefing is the "cheat sheet" — everything the agent needs to start working without reading 62 plan files

**3.4 Progress reporting**
- Sessions report what they've done: files changed, tests run, status updates
- Reports feed back into the dashboard and the evidence log on work items

### 4. Visual Dashboard

The mission control UI — the reason this product exists.

**4.1 Project overview**
- At-a-glance view of all initiatives, features, and their status
- Visual hierarchy showing nesting and dependencies
- Color-coded status (planned, in-progress, blocked, complete)
- Progress indicators at every level (% of children complete)

**4.2 Active sessions view**
- See all active agent and human sessions
- What each session is working on
- Real-time progress (files changed, status updates)

**4.3 Dependency graph**
- Visual representation of what blocks what
- Highlight critical path (what must complete to unblock the most work)
- Show what's ready to start now

**4.4 Policy dashboard**
- View all policies on a work item and its ancestors
- See which are gate/flag/skip
- Toggle modes directly from the UI
- See pending approvals (items waiting at gates)

**4.5 Work item detail**
- Full view of a single work item: description, criteria, policies, evidence, history
- Edit properties, criteria, and policies inline
- View child items and their status

**4.6 Notifications and approvals**
- Queue of items waiting for human decisions (gate mode policies)
- Flagged items that proceeded but need attention (flag mode policies)
- Approve, reject, or override from the queue

### 5. Decomposition Workflow

Structured process for breaking high-level goals into executable work.

**5.1 Human-created work**
- Create work items manually at any level
- Add children, set dependencies, attach policies

**5.2 AI-proposed decomposition**
- Select a work item and request decomposition
- AI proposes a breakdown into sub-items with suggested acceptance criteria, scope, and dependencies
- Human reviews, edits, approves, or rejects the proposal in the UI

**5.3 Iterative refinement**
- Decomposition can happen at any time, not just at the start
- A task that turns out to be complex can be decomposed mid-flight
- Controlled by decomposition gate policy (gate: human must approve, flag: AI decomposes and human reviews, skip: AI decomposes autonomously)

### 6. Evidence and Verification

Proof that work was done correctly.

**6.1 Acceptance criteria**
- Each work item has a list of criteria
- Criteria can be human-readable ("code is well-structured") or machine-verifiable ("pytest tests/integration/ passes")
- Machine-verifiable criteria can be auto-checked

**6.2 Evidence collection**
- Sessions attach evidence to work items: git commits, test results, file diffs, logs
- Evidence is linked to specific acceptance criteria where applicable

**6.3 Verification workflow**
- When a session marks work complete, the system evaluates completion gate policies
- Machine-verifiable criteria are auto-checked
- Human-verifiable criteria are queued for review
- Work moves to `review` state until all criteria are satisfied

### 7. Multi-Project Support

Work across multiple repositories and projects.

**7.1 Project registry**
- Register multiple projects/repos in a single Compose instance
- Each project has its own default policies and scope

**7.2 Cross-project work**
- A single work item can span multiple projects (e.g., "add decisions API" touches service, SDK, and frontend)
- Scope boundaries can include or exclude specific projects
- Dependencies can cross project boundaries

**7.3 Cross-project visibility**
- Dashboard shows work across all registered projects
- Filter and group by project, status, assignee, or label

### 8. Connectors

Compose is a hub, not an island. Connectors allow importing from, exporting to, and syncing with external systems. Compose should never require users to abandon existing tools — it orchestrates across them.

**8.1 Source document connectors (import/link)**
- **Markdown files** — Import or link existing plan files, design specs, READMEs as artifacts on work items. Watch for changes.
- **GitHub/GitLab** — Import issues, PRs, and discussions as work items or artifacts. Link commits to evidence.
- **Obsidian** — Import vault notes as artifacts. Respect Obsidian's link structure.
- **Google Docs** — Link documents as artifacts on work items.
- **Confluence** — Import pages as artifacts.
- **Notion** — Import pages/databases as work items or artifacts.
- General: any connector imports into Compose's native Work model. Source format doesn't affect internal structure.

**8.2 PM system connectors (bidirectional sync)**
- **GitHub Issues/Projects** — Sync work items ↔ issues. Status changes propagate both directions. Labels, milestones, assignees map to Compose equivalents.
- **JIRA** — Sync work items ↔ JIRA issues. Map JIRA workflows to Compose status lifecycle.
- **Linear** — Sync work items ↔ Linear issues. Map Linear states and labels.
- **Local filesystem** — Export/import work items as structured files (JSON/YAML) for version control or backup.
- General: Compose is the orchestration layer. External PM systems can be the execution layer for teams that already use them.

**8.3 AI agent connectors**
- **Claude Code** — MCP server + hooks + context injection (primary, Phase 2+)
- **GitHub Copilot Workspace** — Work item sync for Copilot-driven sessions
- **Devin** — Task assignment via Devin's API
- **Cursor** — Context file generation for Cursor sessions
- General: any agent that can read a context file or call an API can be a Compose session.

**8.4 Connector principles**
- Compose's internal model is always the source of truth for structure and policies
- External systems are sources of truth for their own data (content, comments, reactions)
- Sync is configurable: one-way import, one-way export, or bidirectional
- Sync frequency is configurable: on-demand, periodic, or real-time (webhooks)
- Conflicts surface as flagged notifications, never silently resolved
- Connectors are plugins — new connectors can be added without changing core

---

## User Workflows

### Workflow A: Start a new initiative
1. Human creates a high-level work item ("Build reasoning system v2")
2. Human requests AI decomposition
3. AI proposes features, phases, tasks with dependencies
4. Human reviews and edits in the UI
5. Human sets policies: strict gates on architecture decisions, skip on routine implementation
6. Work items become available for sessions to claim

### Workflow B: Start a Claude Code session
1. Developer opens Claude Code
2. Compose presents available work (unblocked, unassigned items)
3. Developer (or Claude) claims a work item
4. Compose generates context briefing: what to do, acceptance criteria, scope, policies
5. Claude works within the boundaries
6. Claude reports progress and evidence
7. On completion, Compose evaluates policies and transitions status

### Workflow C: Monitor parallel work
1. Three Claude sessions are running on different tasks
2. Developer opens Compose dashboard
3. Sees all three sessions, what they're working on, progress
4. One session hits a gate (needs approval to cross a scope boundary)
5. Developer reviews and approves in the UI
6. Session proceeds
7. Another session completes; Compose auto-checks criteria and moves to complete

### Workflow D: Respond to a flagged issue
1. A session proceeds on a task (flag mode for scope)
2. It touches a file outside the defined scope
3. Compose flags this in the notification queue
4. Developer reviews: was this justified or a mistake?
5. Developer either acknowledges (no action) or intervenes (revert, reassign, tighten policy)

### Workflow E: Dogfood — use Compose to build Compose
1. Compose's own development is tracked in Compose
2. Features, phases, tasks for Compose are work items in Compose
3. Policies enforce Compose's own conventions
4. Claude Code sessions building Compose are managed by Compose
5. The product validates itself through use

---

## Success Criteria

- **Orientation time**: Starting a new Claude Code session takes <30 seconds (claim work → get briefing → start)
- **Big picture clarity**: Opening the dashboard answers "where are we" in <10 seconds
- **Parallel safety**: Multiple agent sessions never conflict or duplicate work
- **Policy compliance**: Agents stay within defined boundaries >95% of the time
- **Self-hosting**: Compose is used to manage its own development within 2 weeks of first prototype

---

## Delivery Phases

The full PRD describes the complete product (scope A). Delivery is phased so each increment is usable and dogfoods the next. The data model and API surface are designed for A from day one — phases are additive, not transformative.

### Phase 1: Visual Planning (dogfood: Compose manages its own planning)

**Scope:** Work hierarchy + artifacts + visual dashboard. Policies and Sessions exist in the data model but are not active in the UI.

**Delivers:**
- Create, edit, nest, and reorder work items at any depth
- Attach artifacts (documents, links) to work items
- Set status on work items (planned → ready → in_progress → review → complete)
- Define dependencies between work items
- Define scope boundaries on work items (files, directories, projects)
- Define acceptance criteria on work items
- Project registry (multiple repos in one instance)
- Dashboard: hierarchy view, status overview, dependency graph, cross-project view
- Labels, filtering, grouping

**Use cases covered:** UC-1 (where are we), UC-4 (decomposition — manual only), UC-5 (cross-project tracking), UC-6 (planning loop)

**Dogfood gate:** Compose's own Phase 2 planning is managed inside Compose.

### Phase 2: Session Management (dogfood: Claude Code claims work from Compose)

**Scope:** Session identity, assignment, context briefing. Claude Code integration via MCP server.

**Delivers:**
- Session registry (human + Claude Code sessions)
- Claim/release work items
- Context briefing generation (what to do, criteria, scope, dependencies, what others are doing)
- MCP server exposing: get available work, claim work, report progress, get briefing
- Progress reporting from sessions (files changed, status updates)
- Session view in dashboard (who's working on what)
- Context recovery (new session picks up previous session's evidence)

**Use cases covered:** UC-2 (session assignment), UC-7 (context recovery)

**Dogfood gate:** Claude Code sessions building Compose get their assignments from Compose.

### Phase 3: Policy Enforcement (dogfood: Compose enforces its own conventions)

**Scope:** 3-mode dials go live. Gates, flags, verification.

**Delivers:**
- Policy configuration UI (set gate/flag/skip per decision point per work item)
- Policy inheritance (parent → children with override)
- Start gate enforcement (dependency checks, human approval)
- Completion gate enforcement (acceptance criteria verification, test execution)
- Scope enforcement (flag or block when agent touches out-of-scope files)
- Budget enforcement (token/time/file-change limits)
- Notification queue for flagged items
- Approval queue for gated items

**Use cases covered:** UC-3 (agent guardrails)

**Dogfood gate:** Compose policies enforce scope and verification on its own tasks.

### Phase 4: Live Coordination (dogfood: parallel agents building Compose simultaneously)

**Scope:** Real-time monitoring, parallel session coordination, evidence collection.

**Delivers:**
- Real-time session progress in dashboard (websocket updates)
- Evidence collection (git commits, test results linked to work items)
- AI-proposed decomposition (Claude breaks down work items, human reviews in UI)
- Conflict detection (two sessions assigned overlapping scope)
- Session history and audit trail
- Hooks integration (pre-commit, post-tool enforcement)

**Dogfood gate:** 3+ parallel Claude Code sessions building Compose features simultaneously, managed entirely within Compose.

---

## Out of Scope (for now)

- Time-based scheduling (Gantt charts, deadlines, sprint planning)
- Cost/billing tracking
- Integration with non-Claude agents (Devin, Codex, etc.)
- Public/hosted multi-tenant version
- Mobile UI
- AI-generated project plans from natural language alone (always human-gated)
