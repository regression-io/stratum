# Forge: AI Development Mission Control

**Date:** 2026-02-11
**Status:** BRAINSTORM
**Type:** Product concept exploration

---

## Problem Statement

AI-driven development (Claude Code, Devin, etc.) has no visual command center. Developers managing complex projects with multiple initiatives, dependencies, and parallel agent sessions have no way to:

1. **See the big picture** — 62 plan files, a 660-line roadmap, scattered gaps tracker. Impossible to see "where are we" at a glance across all initiatives.
2. **Orient quickly** — Starting a new session requires significant effort to figure out what to work on next, what's blocked, what's in progress.
3. **Coordinate sessions** — Running parallel Claude Code sessions (or switching between tools like Warp) with no shared view of who's working on what.

## What This Is NOT

- Not a wrapper around existing markdown planning files
- Not a JIRA/Linear clone with AI bolted on
- Not a single-tool integration (must be general-purpose)

## What This IS

A **mission control system for AI-driven software development**. The human sets direction and configures trust levels. AI agents decompose, execute, and report. The system enforces structure and constraints. The UI shows what's happening.

---

## Core Axiom

> **Every decision point is a 3-mode dial.**

| Mode | Behavior | Human Role |
|------|----------|------------|
| **Gate** | Blocked until human decides | Decider |
| **Flag** | Agent proceeds, human notified | Reviewer |
| **Skip** | Agent proceeds, no notification | Delegator |

This single primitive applies uniformly to every decision in the system: decomposition, scope boundaries, dependency enforcement, verification, budget limits, project boundaries, and any future concern. The human configures the mode per decision point. Modes inherit downward through the hierarchy with override at any level.

The system never has different mechanisms for different concerns. It has **one mechanism applied everywhere**.

---

## Three Primitives

The entire system is built from three constructs, each decomposing into three sub-constructs.

### 1. Work

A thing that needs to get done. Hierarchical, arbitrarily deep. The labels (initiative, feature, phase, task) are user-defined — the construct is just a node with optional children. A tree.

| Sub-construct | Description |
|---------------|-------------|
| **Structure** | What it is and where it sits. Identity (name, description, labels) + hierarchy (parent, children). The tree. |
| **State** | Where it is in its lifecycle. A finite state machine: `planned → ready → in_progress → review → complete` (plus `blocked`, `parked`). |
| **Evidence** | What it produced. Commits, test results, files changed, logs. Proof that work happened and what the outcomes were. |

The minimum viable unit is a single Work node (a task). The hierarchy scales up as complexity demands — you don't need initiatives and phases for a small project.

### 2. Policy

A 3-mode dial attached to a decision point. Policies govern what's allowed to happen and how strictly.

| Sub-construct | Description |
|---------------|-------------|
| **Trigger** | What decision point activates this policy. "Work starts", "work completes", "scope boundary crossed", "decomposition requested", "session assigned." The *when*. |
| **Mode** | Gate / flag / skip. The enforcement level. The *how strict*. |
| **Criteria** | What's actually evaluated. "Tests pass", "files within directory X", "dependency Y is complete", "budget under N tokens", "human approves." The *what*. |

Policies inherit downward through the Work hierarchy. A policy set on a feature applies to all its phases and tasks unless overridden. Dependencies, scope boundaries, acceptance criteria, budget limits, project rules — all are specific instances of Policy.

### 3. Session

An actor interacting with Work, governed by Policies. Both humans and AI agents are sessions.

| Sub-construct | Description |
|---------------|-------------|
| **Actor** | Who or what this is. Type (human, claude-code), identity, capabilities. |
| **Assignment** | What Work node(s) this session is bound to. A session claims work, the system evaluates policies against the claim. |
| **Context** | What the session knows. Inherited downward from the Work hierarchy + policies. This is what gets injected into a Claude Code session at startup — its briefing. |

---

## Interaction Pattern

Every interaction follows: **propose → present → decide → execute**.

- Claude (or any actor) **proposes** an action (decompose work, start task, mark complete, cross scope boundary)
- The system **presents** the proposal in context (via UI for humans, via MCP/context for agents)
- The relevant policy **decides** the outcome:
  - Gate: blocks until human decides
  - Flag: proceeds with notification
  - Skip: proceeds silently
- The actor **executes** if allowed

The human can always intervene at any level, but the system doesn't require intervention where the mode is set to skip.

---

## Design Principles

1. **One mechanism everywhere** — The 3-mode dial is the only control primitive. No special cases.
2. **Hierarchy with inheritance** — Policies cascade down. Set once at a high level, override where needed.
3. **Team-native, solo-friendly** — Designed for a team of actors (human + multiple Claude sessions). A solo developer is a team of one.
4. **Structure IS the plan** — The Work hierarchy is both the project plan and the constraint system. There's no separate "plan document" and "task tracker."
5. **General purpose** — Works for any project at any scale. Not tied to a specific language, framework, or development methodology.
6. **Mode-agnostic** — Runs locally or in the cloud. Persistence, agents, and deployment are swappable connectors.

---

## Landscape Analysis

### Existing Solutions

| Solution | Approach | Strength | Gap |
|----------|----------|----------|-----|
| [CCPM](https://github.com/automazeio/ccpm) | GitHub Issues + CLI commands + git worktrees | Full traceability, parallel execution, uses existing infra | No UI, no constraint enforcement, no visual dashboard |
| [CC Tasks](https://venturebeat.com/orchestration/claude-codes-tasks-update-lets-agents-work-longer-and-coordinate-across) | Built-in persistent tasks with DAG deps | Zero setup, persistent, multi-session via env var | Flat (no hierarchy), no project-level structure, no visual layer |
| [CC Agent Teams](https://code.claude.com/docs/en/agent-teams) | Lead agent + worker agents | Built-in parallel delegation | Experimental, no visual control plane, no constraint system |
| [Linear + Devin](https://devin.ai/) | SaaS PM + autonomous agent | Familiar JIRA-like UI, assign agents to issues | SaaS, expensive, opaque agent, not Claude-native |
| [claude-flow](https://github.com/ruvnet/claude-flow) | Multi-agent orchestration via MCP | Swarm intelligence, MCP-native | Infrastructure-level, no PM concepts |
| [Agent-MCP](https://github.com/rinadelph/Agent-MCP) | Multi-agent coordination framework | Parallel specialized agents | Framework, not product. No visual layer |

### Best Ideas to Incorporate

| Idea | Source |
|------|--------|
| GitHub Issues as audit trail with full traceability | CCPM |
| Git worktrees for conflict-free parallel execution | CCPM, Mike Mason |
| DAG-based dependency management | CC Tasks |
| Lead agent + worker agent delegation | CC Agent Teams |
| Persistent state across sessions | CC Tasks |
| Shared task list across concurrent sessions | CC Tasks (`CLAUDE_CODE_TASK_LIST_ID`) |
| Context files per epic/feature (prevent context pollution) | CCPM |
| Structural safeguards over autonomous freedom | [Mike Mason](https://mikemason.ca/writing/ai-coding-agents-jan-2026/) |
| Specialized agents per domain (UI, API, test) | CCPM, Agent-MCP |
| JSONL issue storage in git | Beads (Mason) |

### Gaps None of Them Fill

| Gap | Description |
|-----|-------------|
| No visual control plane | No local-first dashboard for AI-driven development |
| No constraint enforcement | No formal hard vs soft vs skip constraint system |
| No project hierarchy | No system models initiative → feature → phase → task with constraints at every level |
| No live progress visualization | No real-time view of parallel agent progress |
| No decomposition workflow | No structured propose → review → approve breakdown flow |
| No cross-project awareness | Repo-scoped only; no monorepo/multi-repo coordination |
| No constraint inheritance | No cascading of policies through hierarchy |
| No verification-as-first-class | "Done" is self-reported; no machine-verifiable gates |
| No session-to-task binding | No system brokers assignment and injects context at session start |

---

## Open Questions

### Resolved

| Question | Answer |
|----------|--------|
| Solo or team? | Team-native, solo-friendly. Solo = team of one. |
| Who does decomposition? | All modes available (human, AI-proposed, autonomous). Gated by human decision. |
| What counts as "done"? | Configurable via policy: gate (must pass checks), flag (checks run, human reviews), skip (trust agent). |
| Single or multi-project? | Configurable via policy. Project boundaries are just another policy. |
| How does CC connect? | All integration mechanisms available (MCP, hooks, context injection). Which is used is governed by policies. |
| Read-only UI or read-write? | New structured system (option 3). Not a markdown overlay. Own data store. |
| How strict are constraints? | 3-mode dial. Human configures trust level per decision point. |

### Resolved (2026-02-11 planning session)

| Question | Answer | Reference |
|----------|--------|-----------|
| What does the UI look like? | 5 views: Dashboard, Work Detail, Dependency Graph, Board, Settings | [UI-BRIEF](UI-BRIEF.md) |
| What's the MVP scope? | Phase 1 visual planning + persistence connector = usable for self-management | [Integration Roadmap](plans/2026-02-11-integration-roadmap.md) |
| Storage mechanism? | Connector-based — mode-agnostic, swappable (local DB, cloud, hybrid) | [Deterministic UI Decision](decisions/2026-02-11-deterministic-ui.md) |
| Deterministic or dynamic UI? | Deterministic UI, dynamic content. LLM contributes content, not layout. | [Deterministic UI Decision](decisions/2026-02-11-deterministic-ui.md) |
| How does deliberation fit? | Deliberation is Work. Brainstorms, discussions, decisions are Work items with labels. | [Deliberation Decision](decisions/2026-02-11-deliberation-as-work.md) |

### Still Unresolved

- How does the MCP server API surface look? (Phase 2)
- Naming: "Forge" is a working name. Keep it?
- How does this relate to Claude Code's built-in Tasks? (Replace, complement, wrap?)
- Conversation distillation: how exactly does transcript → structured Work items work?
- Memory system: where does persistent cross-session knowledge live in the data model?

---

## Next Steps

1. ~~Design the UI: what views does the dashboard need?~~ → [UI-BRIEF](UI-BRIEF.md)
2. ~~Scope the MVP: what's the minimum viable Forge?~~ → [Integration Roadmap](plans/2026-02-11-integration-roadmap.md)
3. **Persistence connector** — replace Base44 SDK, make Forge self-hosting
4. Define the integration surface: MCP tools, hooks, context injection format (Phase 2)
5. Design conversation distillation and memory system
