# Compose Product Realignment

> Supersedes the flat item model in the Vision Surface prototype.
> Derived from: SmartMemory ROADMAP (battle-tested structure) + feature-development skill (battle-tested lifecycle).

## The Problem

The Vision Surface prototype treats everything as a flat bag of items with types and phases. This breaks at scale — 50+ items across multiple workstreams becomes noise. Grouping by phase or type doesn't help because it doesn't answer "what am I working on right now?"

But the fix isn't to impose a rigid hierarchy. It's to recognize that the underlying structure is a **graph** — entities connected by typed edges — where certain patterns (like Initiative → Feature → Task) emerge naturally but aren't the only shape.

## The Graph, Not the Tree

The data model is a DAG (directed acyclic graph) of entities and typed edges. Not a tree.

### Entity Types

| Type | Role | Has Lifecycle? | Must Belong to Something? |
|------|------|---------------|--------------------------|
| **Initiative** | Strategic container. A goal with scope. | No — status derived from connected entities | No |
| **Feature** | Work unit. The thing that walks through phases. | Yes — design → planning → implementation → verification → release | No (can be standalone, belong to one Initiative, or shared across multiple) |
| **Task** | Atomic work within a Feature's current phase. | No — planned / doing / done | Yes — always belongs to a Feature |
| **Idea** | Unstructured thought. May become anything or nothing. | No | No — can float free |
| **Thread** | Discussion or exploration. Captures deliberation. | No | No — can float free |
| **Decision** | Resolved choice. Records what was decided and why. | No | No — can connect to anything |
| **Question** | Unresolved. May block progress on something. | No | No — can connect to anything or float |

Only Features have a lifecycle. Everything else is either a container (Initiative), atomic work (Task), or a thinking artifact (Idea, Thread, Decision, Question) that connects into the graph wherever it's relevant.

### Edge Types

| Edge | Meaning | Example |
|------|---------|---------|
| `blocks` | Hard dependency. A cannot proceed until B is done. | Feature A `blocks` Feature B |
| `sequencing` | Soft dependency. Better to do A first, not required. | CORE-CODE-1 `sequencing` DOG-T4 |
| `informs` | Provides context or input. Loose coupling. | Thread `informs` Feature |
| `implements` | Task delivers on a Feature. | Task `implements` Feature |
| `belongs_to` | Structural grouping. Many-to-many — an entity can belong to multiple containers. | Feature `belongs_to` Initiative (or two Initiatives) |
| `produces` | Discovery output. | Discovery session `produces` Feature |
| `questions` | Raises an open issue about something. | Question `questions` Feature |
| `resolves` | A Decision answers a Question. | Decision `resolves` Question |

Edges are directed. An Idea can `informs` three Features across two Initiatives. A Thread can `informs` a Decision that `resolves` a Question that `blocks` a Feature. A standalone Idea can have zero edges.

### The Tree is One View

The Initiative → Feature → Task pattern is real and common. It's how you organize execution. But it's one **lens** on the graph, not the graph itself.

Other valid shapes:
- An Idea floating free with no connections (just captured, not yet placed)
- A Thread that `informs` 5 Features across 3 Initiatives
- A Decision that `resolves` Questions in 2 different Initiatives
- A Feature with no Initiative (standalone work, hasn't been grouped yet)
- A Question that `blocks` a Feature and also `questions` an Initiative's scope

The graph holds everything. Views filter and arrange it for different purposes.

---

## Discovery

Discovery is an orthogonal process, not a level in the hierarchy or a phase in the Feature lifecycle. It's the process of turning fuzzy intent into structured entities.

**Discovery can produce any entity type:**
- An Initiative (new strategic goal)
- A Feature (new work unit, may or may not belong to an Initiative)
- An Idea (captured thought, loosely linked or floating free)
- A Thread (exploration that touched several topics)
- A Decision (resolved during brainstorming)
- A Question (surfaced but unresolved)

**Discovery outputs connect to existing entities with varying strength:**
- **Strong link:** "This Discovery session produced DOG-T3" (`produces` edge)
- **Weak link:** "This brainstorm informed the design of STU-EVAL-1" (`informs` edge)
- **No link:** "Here's an Idea we had, not attached to anything yet" (floats in the Ideas bucket)

**Discovery has provenance.** Every entity produced by Discovery traces back to the session/process that created it. "Why does this Feature exist?" → follow the `produces` edge back to the Discovery artifacts (brainstorm records, vision docs, exploration notes).

**Discovery is re-entrant.** It can happen at any time — before Initiatives exist, after Features are in flight, when scope needs rethinking. It always produces entities and edges; it never directly mutates the Feature lifecycle.

---

## The Feature Lifecycle

Only Features have a lifecycle. The lifecycle starts at Design (Discovery already happened) and progresses through gates:

```
Design ──gate──> Planning ──gate──> Implementation ──gate──> Verification ──gate──> Release
```

Mapped from the feature-development skill:

| Phase | Skill Phases | Gate | Artifacts Produced |
|-------|-------------|------|-------------------|
| Design | Design spec + PRD + Architecture | User approves direction | Design spec, PRD, Architecture doc |
| Planning | Blueprint + Plan | Plan approved, no ambiguity | Implementation plan |
| Implementation | Execute + Review 3x | 3 clean review passes | Working code |
| Verification | Tests + Report | Coverage met, report complete | Test suite, Implementation report |
| Release | Docs + Ship | All docs current | Updated docs, changelog |

**Not every Feature needs every phase.** A bug fix starts at Planning. A one-file change starts at Implementation. You can skip forward, you can't reorder.

**Artifacts attach to the Feature at the phase that produced them.** They're evidence of progress, not standalone graph entities.

```
Feature: DOG-T1 (Wire SmartMemory MCP)
  Phase: Implementation
  Artifacts:
    Design     → design-spec.md, PRD.md
    Planning   → implementation-plan.md
    Implementation → (in progress)
```

---

## Buckets and Scoping

The noise problem ("too many things on the board") is solved by **scoping**, not by hierarchy.

### Scoping mechanisms

1. **By Initiative** — "Show me everything related to DOG." Follows `belongs_to` edges from Features to Initiative, plus anything connected to those Features.

2. **By Feature** — "Show me DOG-T1." Its Tasks, Artifacts, connected Questions, Decisions, Threads.

3. **By bucket** — "Show me all unattached Ideas." Entities with no `belongs_to` or `implements` edges. The inbox of unplaced thoughts.

4. **By status/phase** — "Show me everything blocked." "Show me everything in Implementation." Cross-cutting filters that work alongside scoping.

### The buckets

Not everything belongs to an Initiative. Some things live in their own space:

- **Ideas** — Captured thoughts. May eventually get linked to a Feature or Initiative, or may stay forever as raw material. Browsable, searchable.
- **Threads** — Discussions and explorations. Often `informs` multiple things. The deliberation record.
- **Questions** — Open issues. May `blocks` something or may just be tracked for later.
- **Decisions** — Resolved choices. Always valuable as reference even if not linked to active work.

These are first-class citizens, not second-class items waiting to become Features. Some Ideas stay Ideas. Some Threads are valuable without ever producing a Feature.

---

## Data Model

### Entity (base)

Every entity shares:

```
id:          string    (semantic: "DOG", "DOG-T1", or auto-generated for Ideas/Threads)
type:        initiative | feature | task | idea | thread | decision | question
title:       string
description: string
status:      (type-dependent, see below)
confidence:  1-5 | null   (1 = needs attention, 5 = solid. null = not assessed)
created_at:  datetime
updated_at:  datetime
```

Confidence is a cross-cutting lens (CR5). For Features, lifecycle position provides a baseline (later phase = higher implicit confidence) but the explicit field can override — a Feature in Verification with failing tests is still confidence 2. For thinking artifacts, confidence signals strength: a shower-thought Idea is 1, a Decision backed by three Threads is 5. Null means nobody's assessed it yet.

### Initiative

```
extends Entity (type: initiative)
status:      derived from connected Features
```

### Feature

```
extends Entity (type: feature)
phase:       design | planning | implementation | verification | release
status:      planned | in_progress | blocked | complete | parked | killed | superseded
priority:    high | medium | low
effort:      string?
artifacts:   [{ phase, type, path, created_at }]
gates:       [{ phase, status: "pending" | "passed" | "skipped", passed_at? }]
```

### Task

```
extends Entity (type: task)
status:      planned | in_progress | complete
phase:       string    (which Feature phase this task belongs to)
assignee:    string?
```

### Idea / Thread / Decision / Question

```
extends Entity (type: idea | thread | decision | question)
status:      open | resolved | parked    (simple — no lifecycle)
```

### Edge

```
id:          string
from_id:     string    (source entity)
to_id:       string    (target entity)
type:        blocks | sequencing | informs | implements | belongs_to | produces | questions | resolves
created_at:  datetime
```

---

## Semantic IDs

`DOG-T1`, `STU-UX-13a`, `CORE-CODE-1` — not UUIDs.

Format: `PREFIX-CATEGORY-NUMBER` with optional sub-IDs (13a, 13b).

Features and Initiatives get semantic IDs (human-assigned or convention-derived). Tasks can use semantic sub-IDs (`DOG-T1-001`) or auto-generated IDs. Ideas, Threads, Questions, Decisions can use either — semantic if they're significant enough to reference by name, auto if they're ephemeral.

---

## The 3-Mode Dial

Every gate in the Feature lifecycle is a 3-mode dial:

- **Gate:** Feature cannot advance until human approves.
- **Flag:** Agent advances, human is notified.
- **Skip:** Agent advances silently.

Dials can be set per-Feature or inherited from the Initiative. An Initiative set to "Skip" means its Features auto-advance unless overridden. A Feature set to "Gate" always requires approval regardless of Initiative setting.

The dial governs the *feel* of the process — same structure, same phases, different enforcement.

---

## UI Implications

### Views

All views support scoping (by Initiative, by Feature, by bucket, by filter).

**Feature Board (Kanban)** — Columns are lifecycle phases. Cards are Features.
```
| Design    | Planning | Implementation | Verification | Release |
|-----------|----------|----------------|--------------|---------|
| [FEAT-3]  | [FEAT-1] | [DOG-T1]      |              |         |
|           |          | [DOG-T2]       |              |         |
```

**List** — Entities as rows. Columns: type, phase, status, priority. Sortable, filterable, groupable.

**Graph** — Dependency DAG. Nodes are entities, edges are typed relationships. Node shape/color by type, edge style by relationship type (solid = blocks, dotted = sequencing, thin = informs).

**Buckets** — Ideas, Threads, Questions, Decisions in their own browsable space. Unattached items surface here automatically.

### Detail Panel

**Feature detail:** Phase progress bar, gate status, artifacts per phase, tasks in current phase, connected entities (incoming and outgoing edges), activity log.

**Initiative detail:** Connected Features with phase/status, Discovery provenance trail, aggregate progress, option to re-enter Discovery.

**Idea/Thread/Decision/Question detail:** Content, connected entities (what this informs, blocks, resolves, questions), provenance (what Discovery session produced this).

### Scoping Controls

Top-level selector:
- **All** — everything
- **[Initiative Name]** — entities connected to this Initiative
- **Unattached** — entities with no Initiative connection (the inbox)
- **[Custom filter]** — saved filters for specific workflows

---

## What Changes from the Prototype

| Prototype Concept | Becomes | Why |
|---|---|---|
| Item (one type, flat) | Entity (7 types, graph-connected) | Different things have different shapes |
| Item type as a label | Entity type as structural (Feature has lifecycle, Idea doesn't) | Types determine behavior, not just display |
| Item phase (all items have phases) | Phase only on Features; Discovery is separate process | Only Features walk through a lifecycle |
| parentId | Typed edges (belongs_to, implements, informs...) | Relationships are richer than parent-child |
| Connections (informs, blocks) | Edge types in a DAG | Same concept, cleaner model, more types |
| Mode toggle (Discovery/Execution) | Scoping by Initiative + bucket views | Scoping is more precise than mode switching |
| Vision board items for docs | Artifacts on Features + Discovery provenance on Initiatives | Docs are phase receipts or provenance, not standalone entities |
| UUID item IDs | Semantic IDs (DOG-T1) | Human-writable, referenceable in conversation |
| Everything on one board | Scoped views + bucket views for unattached thinking | You see what's relevant to current work |

## What Stays

- **Feature lifecycle** (design → planning → implementation → verification → release) — validated by feature-development skill.
- **The 3-mode dial** (gate/flag/skip) — orthogonal to structure, governs enforcement.
- **The graph view** — now shows the actual DAG instead of arbitrary connections.
- **The detail panel** — adapted per entity type.
- **The agent bridge** (vision-track CLI) — adapted to operate on entity types and edges.
- **The hook-based tracking** — adapted to create artifacts and edges, not standalone items.
- **Layout shell** — sidebar + main view + detail panel structure stays.

---

## Related Documents

- SmartMemory ROADMAP (`smart-memory-docs/docs/ROADMAP.md`) — reference implementation of Initiative → Feature → Phase → Task pattern
- Feature Development Lifecycle (`~/.claude/skills/feature-development`) — reference implementation of the Feature lifecycle
- Core Requirements CR1-CR7 (`docs/requirements/core-requirements.md`) — composition model (nuance: theoretical framework underlying the practical structure)
- Vision Component Design (`docs/design/vision-component-design.md`) — prototype design (superseded)
