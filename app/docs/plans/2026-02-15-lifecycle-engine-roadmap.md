# Lifecycle Engine: From Skill to Product

**Date:** 2026-02-15
**Status:** SKETCH — gap analysis and layer inventory, not a buildable spec
**Related:** [Forge Skill](~/.claude/skills/forge/SKILL.md), [Feature-Dev v2 Design](../features/feature-dev-v2/design.md), [Skill Arch Upgrade Design](../features/skill-arch-upgrade/design.md), [Canonical Roadmap](../ROADMAP.md) ← Phase 6 entries, [Bootstrap Roadmap (CLAUDE.md)](../../CLAUDE.md), [Integration Roadmap (superseded)](2026-02-11-integration-roadmap.md), [PRD](../PRD.md)

---

## The Gap

Feature-dev encodes a 10-phase lifecycle for building features: explore, design, blueprint, plan, execute (with review and coverage loops), document, ship. Today it's a skill file — markdown instructions an agent follows on trust. The agent can rationalize past any "REQUIRED" or "never skip" instruction.

The product is Forge as the runtime that enforces this lifecycle structurally. Gates that actually block. Phases that are tracked. Artifacts that are managed. Iterations that are orchestrated. Preferences that control what's gated and what's autonomous.

## Current State → Target State

| Today (Skill) | Target (Product) |
|---|---|
| Prose says "REQUIRED" | Policy dial structurally blocks phase transition |
| Agent scans feature folder on entry | Forge tracks phase state per feature, derives from artifacts |
| Agent creates folders manually | Forge manages feature workspaces with templates |
| "Present options, human decides" | Gate UI: approve/revise/kill rendered in sidebar |
| Ralph loop is a plugin | Forge dispatches iterations, monitors completion promises |
| Claude Code primitives hardcoded | Agent-agnostic lifecycle, agent-specific connectors |
| Agent remembers preferences (or doesn't) | User preferences inventory controls defaults system-wide |
| No enforcement across sessions | Session-lifecycle binding tracks what each session works on |

---

## Layers

Ordered by dependency. Each layer builds on the ones above it.

### Layer 0: User Preferences Inventory

**What:** A structured inventory of everything configurable in Forge — features, defaults, policies, UI, agent settings. The config surface that controls everything downstream.

**Why first:** Before building enforcement, we need to know what's enforceable. Before building gates, we need to know what's gatable. This inventory is the input to every other layer.

**Includes:**

- **Feature toggles** — enable/disable Forge features (e.g., auto-journaling on/off, blueprint verification on/off)
- **Default policy modes** — per-phase gate/flag/skip defaults (e.g., "design phase: gate, implementation phase: flag")
- **Artifact preferences** — versioning strategy (verbose/clean), template selection
- **Agent preferences** — which agent, model, temperature, context budget
- **UI preferences** — theme, information density, default view, notification style
- **Lifecycle preferences** — which phases to include by default, skip conditions, review depth

**Shape:** A config file (`.forge/preferences.json` or similar) with sensible defaults and override at project, feature, and phase levels. Same inheritance pattern as policies.

**Can start:** Now — this is a design exercise + simple config system. No infrastructure dependency.

### Layer 1: Feature Lifecycle State Machine

**What:** Forge explicitly tracks which phase each feature is in. Today this is implicit (which files exist in the folder). Needs to become explicit state with events.

**Includes:**

- Feature entity in tracker with `currentPhase` field
- Phase transitions as explicit events (not just "agent moved on")
- Phase history — when did it enter each phase, how long did it spend
- Reconciliation — derive/verify phase from folder artifacts (the scan-first pattern, but as runtime)
- Phase completion criteria — what must exist/pass before transitioning

**Depends on:** Tracker evolution (persistence, Phase 4 item 17)

### Layer 2: Artifact Awareness

**What:** Forge understands feature folders. Creates them, knows what's in them, infers phase from contents, provides templates.

**Includes:**

- Feature folder creation and lifecycle management
- Artifact presence detection (which files exist, which are populated vs empty)
- Artifact quality signals (has content, has been reviewed, word count, last modified)
- Template system — phase-appropriate templates for design.md, prd.md, blueprint.md, etc.
- Artifact ↔ tracker item linking — the bridge between files on disk and items in the graph
- Phase subfolder management — implementation phases get their own workspace

**Depends on:** Layer 1 (state machine provides phase context)

### Layer 3: Policy Enforcement Runtime

**What:** Gate/flag/skip dials that structurally enforce behavior, not just advise it. The core axiom as runtime infrastructure.

**Includes:**

- Policy configuration per phase transition (from Layer 0 preferences)
- **Gate** blocks progression — the system will not advance the phase until UI approval received
- **Flag** logs the decision with rationale and notifies the human
- **Skip** proceeds silently but records the skip for audit trail
- Policy inheritance through work hierarchy (initiative → feature → phase → task)
- Override at any level — a feature can gate what its parent initiative skips
- Policy evaluation engine — given a transition and context, which mode applies?

**Depends on:** Layer 0 (preferences define policy defaults) + Layer 1 (state machine provides transitions to enforce)

**This is the most important layer.** It's the difference between "the skill says gate" and "Forge won't let you proceed without approval."

### Layer 4: Gate UI

**What:** Interactive gate surfaces in the Vision Surface. When a phase transition is proposed, the human sees it and acts on it.

**Includes:**

- Gate notification appears in sidebar when agent proposes a phase transition
- Shows: current artifact (design.md, blueprint.md), proposed next phase, agent's recommendation
- Trade-offs displayed inline (from skill's "propose options" protocol)
- Three actions: Approve (proceed), Revise (loop back), Kill (write killed.md)
- Gate history — what was approved/rejected when, by whom
- Gate queue — multiple features can have pending gates simultaneously

**Depends on:** Layer 3 (policy runtime determines when gates fire) + Vision Surface (rendering infrastructure)

### Layer 5: Session-Lifecycle Binding

**What:** Agent sessions are associated with specific features and phases. Activity, errors, and artifacts are contextualized to the lifecycle.

**Includes:**

- Session tagged with feature code + current phase on start
- Activity feed grouped by feature (not just chronological)
- Errors contextualized — a build error during Phase 7 means something different than during Phase 5 verification
- Session transcripts auto-filed to feature folder's `sessions/` directory
- Multi-session features — Forge knows sessions 3, 7, and 12 all worked on feature INS-SPAN-1
- Handoff context — when a new session starts on a feature, Forge provides lifecycle context automatically

**Depends on:** Phase 3 Agent Awareness (items 11-14) + Layer 1 (state machine provides feature-phase context)

### Layer 6: Iteration Orchestration

**What:** Ralph loops as a Forge primitive, not a plugin. Forge dispatches iterations, monitors for completion, enforces exit criteria.

**Includes:**

- Forge dispatches iteration to agent with prompt and completion promise
- Monitors agent output for promise tag
- Tracks iteration count per loop
- Surfaces when max iterations hit (the "problem is in the spec" signal)
- Phase 7's three-step exit criteria enforced by Forge:
  1. All tasks executed (tests pass, lint passes)
  2. Review loop clean (completion promise detected)
  3. Coverage sweep clean (completion promise detected)
- Agent cannot self-report "done" without Forge confirming promises were met

**Depends on:** Layer 5 (session binding) + Phase 4 Agent Connector (read-write, item 18)

### Layer 7: Agent Abstraction

**What:** The lifecycle is agent-agnostic. Agent-specific connectors handle translation.

**Includes:**

- Connector interface defining agent capabilities (plan, execute, review, iterate)
- Claude Code connector: maps to EnterPlanMode, TaskCreate, superpowers skills, hooks
- Codex connector: maps to Codex's task/execution model
- Gemini connector: maps to Gemini's tool use and planning capabilities
- Feature-dev lifecycle stays the same regardless of agent — phases, gates, artifacts don't change
- Agent capability negotiation — if an agent can't do X, Forge adapts (e.g., no native plan mode → Forge manages plan state)

**Depends on:** All previous layers stable. This is post-V1.

---

## Dependency Graph

```
Layer 0 (User Prefs) ──────────────────────────┐
    │                                           │
    ▼                                           ▼
Layer 1 (State Machine) ──────────────→ Layer 3 (Policy Runtime)
    │                                           │
    ▼                                           ▼
Layer 2 (Artifacts) ──────────────────→ Layer 4 (Gate UI)
                                                │
Phase 3 (Agent Awareness) ──────────→ Layer 5 (Session Binding)
                                                │
Phase 4 (Agent Connector) ──────────→ Layer 6 (Iteration)
                                                │
                                        Layer 7 (Agent Abstraction)
```

---

## Mapping to Bootstrap Roadmap

| Layer | Bootstrap Phase | Relationship |
|-------|----------------|--------------|
| Layer 0 (User Prefs) | New — can start now | Design exercise, no infrastructure dependency |
| Layer 1 (State Machine) | Phase 4: Persistence evolution | Feature state is a persistence concern |
| Layer 2 (Artifacts) | Phase 4: Git/file connector | Folder awareness is a file connector concern |
| Layer 3 (Policy Runtime) | **New — the core product** | The enforcement engine. Nothing in Phases 3-5 covers this. |
| Layer 4 (Gate UI) | Phase 2 extension | New views/interactions in Vision Surface |
| Layer 5 (Session Binding) | Phase 3 extension | Adds feature context to agent awareness |
| Layer 6 (Iteration) | Phase 4: Agent connector | Iteration is a form of agent direction |
| Layer 7 (Agent Abstraction) | Phase 4 extension / Phase 6 | Multi-agent is post-V1 |

**Key insight:** Layer 3 (Policy Enforcement Runtime) is the only layer that is entirely new. Everything else extends existing planned work. Layer 3 is also the most important — it's what makes Forge a product rather than a dashboard.

---

## Sequencing

**Now (during Phase 3):**
- Layer 0: User Preferences Inventory — design the config surface, implement basic preferences
- Layer 5 (partial): Tag sessions with feature context when session tracking lands

**Phase 4 (Connectors):**
- Layer 1: Feature lifecycle state in persistence
- Layer 2: Artifact awareness in file connector
- Layer 3: Policy enforcement runtime — **the big new build**
- Layer 4: Gate UI in Vision Surface
- Layer 5 (complete): Full session-lifecycle binding
- Layer 6: Iteration orchestration via agent connector

**Post-V1:**
- Layer 7: Agent abstraction and multi-agent connectors

---

## What V1 Looks Like

With Layers 0-6 complete, Forge can:

1. **Track lifecycle state** — you see which phase each feature is in across the Vision Surface
2. **Enforce gates** — the system blocks phase transitions until you approve, with trade-offs displayed
3. **Manage artifacts** — feature folders created and populated with templates, artifact presence drives phase inference
4. **Bind sessions** — you see which sessions worked on which features, activity feeds grouped by feature
5. **Orchestrate iterations** — review and coverage loops run as Forge primitives, exit criteria enforced
6. **Respect preferences** — your config controls what's gated, what's flagged, what's autonomous

This is the distance between "Forge shows you what's happening" (today — Vision Surface + agent awareness) and "Forge runs the process" (target — lifecycle engine).

---

## Open Questions

1. **Persistence model for lifecycle state** — extend current JSON tracker? Event-sourced? New entity type?
2. **Policy config UX** — how does a user set gate/flag/skip per phase? Settings panel? Per-feature override in detail view?
3. **Gate notification mechanism** — sidebar badge? Modal? Toast? Blocking overlay?
4. **Iteration dispatch protocol** — how does Forge tell an agent "run this prompt again"? Hook? API? New session?
5. **Preference inheritance resolution** — when project says "gate" and feature says "skip", who wins? (Likely: most restrictive, with explicit override.)
