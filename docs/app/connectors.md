# Forge: Connector Architecture

**Date:** 2026-02-11
**Status:** SKELETON — to be expanded as connectors are designed and built
**Related:** [Taxonomy](taxonomy.md), [PRD](PRD.md) (Section 8: Connectors), [Integration Roadmap](plans/2026-02-11-integration-roadmap.md)

---

## Principle

Forge's core knows about domain objects: Work, Policy, Session, dependencies, artifacts, evidence. Connectors translate between domain objects and external systems. No connector has special access to internals. All connectors consume the same interface.

---

## Connector Types

### Persistence Connector

**Direction:** Bidirectional (read/write domain objects)

**Forge domain → Storage:**
- CRUD for Work, Dependency, Project, Policy, Session
- Query: filter, sort, search across entities
- History: track changes over time

**Possible implementations:** Local DB, cloud DB, hybrid, file-based

**Status:** Next to build (bootstrap 0.3)

---

### Agent Connector

**Direction:** Bidirectional

**Forge → Agent (outbound):**

| Domain Object | What the agent receives |
|---------------|----------------------|
| Context briefing | What to work on, acceptance criteria, scope, what others are doing |
| Policies | Constraints — what's gated, flagged, skipped |
| Scope | Which files/directories/projects are in play |
| Acceptance criteria | What "done" looks like, verifiable conditions |
| Memory | Persistent knowledge relevant to this work |

**Agent → Forge (inbound):**

| Agent activity | What Forge receives |
|---------------|-------------------|
| Progress | Files changed, status updates, partial completions |
| Evidence | Commits, test results, logs |
| Session transcript | Raw conversation for distillation |
| Completion | Work item done, criteria self-assessed |

**The connector's job:** Translate Forge domain objects into the agent's native format, and translate agent activity back into Forge domain objects.

#### Claude Code connector (specific)

| Forge concept | Claude Code native format |
|---------------|--------------------------|
| Briefing | CLAUDE.md, memory files, context injection |
| Policies | Hooks (pre-commit, post-tool), scope rules |
| Scope | File patterns in session context |
| Criteria | Verifiable commands in briefing |
| Skills | Generated from Work item templates / process docs |
| Progress (inbound) | Hook events (tool use, file changes) |
| Evidence (inbound) | Git commits, test output |
| Transcript (inbound) | Session conversation for distillation |

#### Other agents (future)

| Agent | Outbound format | Inbound format |
|-------|----------------|----------------|
| Cursor | .cursorrules, context files | File changes, session events |
| Devin | API calls (task assignment) | API callbacks (progress, completion) |
| Copilot Workspace | Work item sync | PR/commit events |
| Generic | Structured context file (JSON/YAML) | Webhook / file watch |

---

### UI Connector

**Direction:** Bidirectional (read domain objects, write user actions)

**Forge → UI:** Render Work items, hierarchy, dependencies, artifacts, status
**UI → Forge:** Create, update, delete Work items, change status, add artifacts

The current Base44 React app is a UI connector. It could be replaced by a CLI, a TUI, a different web framework, or a mobile app — all consuming the same domain interface.

---

### Source Connector (import/link external content)

**Direction:** Primarily inbound

| Source | What it produces in Forge |
|--------|--------------------------|
| Markdown files | Artifacts on Work items |
| GitHub Issues/PRs | Work items or artifacts, evidence from commits |
| Git repository | Evidence (commits, diffs, branches) |
| Google Docs / Notion / Confluence | Artifacts (linked or imported) |

---

### Sync Connector (bidirectional with external PM systems)

**Direction:** Bidirectional

| System | Forge → External | External → Forge |
|--------|------------------|------------------|
| GitHub Issues/Projects | Work items → Issues, status → labels | Issues → Work items, comments → artifacts |
| Linear | Work items → Issues, status → state | Issues → Work items |
| JIRA | Work items → Issues, status → workflow | Issues → Work items |

**Conflict resolution:** Conflicts surface as flagged notifications, never silently resolved.

---

## Connector Interface (TBD)

All connectors implement a common contract. The specifics are TBD, but the shape is:

```
Connector {
  // Identity
  name        string
  type        persistence | agent | ui | source | sync
  direction   inbound | outbound | bidirectional

  // Lifecycle
  connect()
  disconnect()
  health()

  // Data flow
  push(domain_objects)    // Forge → external
  pull()                  // external → Forge
  subscribe(event_type)   // real-time updates
}
```

This is a skeleton. The actual interface will be designed when the first non-persistence connector is built.

---

## Open Questions

- How does the connector discover what's changed since last sync? (Polling, webhooks, event log?)
- How granular is the push/pull? (Whole entities? Deltas? Field-level?)
- How does auth work per connector? (Stored in Project settings? Environment variables?)
- Should connectors be plugins (dynamic loading) or compiled-in?
- How does the Claude Code connector handle multiple concurrent sessions against the same Forge instance?
