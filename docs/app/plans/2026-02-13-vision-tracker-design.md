# Design: Vision Tracker as Primary Roadmap

**Date:** 2026-02-13
**Status:** DRAFT
**Related:** [User Journey Design](../plans/2026-02-12-user-journey-design.md), [Product Realignment](../design/2026-02-13-product-realignment.md), [Core Requirements](../requirements/core-requirements.md)
**Vision Tracker:** 4b8c6dd8-cfb3-4d60-92b6-d745d7a4d4ce

---

## Problem

Forge has no single source of truth for its roadmap. Work is scattered across:

- CLAUDE.md (bootstrap list — stale)
- User journey design doc (priorities — narrative only)
- Handoff.md (session-scoped — ephemeral)
- Vision Tracker (items — understructured)

The deeper problem: whatever format the roadmap takes, it must stay current. Every tracking system that relies on manual updates drifts within hours. The format question is secondary to the enforcement question.

## Options Evaluated

### Option A: ROADMAP.md only (SmartMemory pattern)

The agent reads and writes natural language. No impedance mismatch — update means "append a sentence." The format conventions (status emojis, feature blocks, IDs) give enough structure for scanning. Battle-tested in SmartMemory.

**Strengths:** Git-diffable, grep-able, portable, rich narrative, accessible when app is broken, agent reads/writes it naturally.

**Weaknesses:** Manual maintenance will drift. Not interactive — can't filter, drag, connect. Not programmatically queryable. The SmartMemory ROADMAP.md is structured data wearing a markdown costume (status, priority, effort, depends-on are fields, not prose).

### Option B: Vision Tracker only (structured data)

Items with typed fields: status, priority, phase, connections. Views render them (list, board, tree, graph). Agent updates via API. Same pattern as Jira/Linear — massively adopted, nobody complains about lack of prose.

**Strengths:** Queryable, filterable, interactive, visual dependency graphs, programmatic access. Jira/Linear prove the model works at scale.

**Weaknesses:** Not git-diffable, not portable, not readable offline or when app is broken. Rich context ("why this decision", "what we tried") doesn't fit in a description field — lives in linked docs instead.

### Option C: Both, kept in sync

Markdown for narrative/portability, tracker for interactivity/querying.

**Strengths:** Best of both worlds in theory.

**Weaknesses:** Manual sync will fail. It always does. Two sources of truth means zero sources of truth when they diverge.

### Option D: Tracker primary, markdown generated

Tracker holds the structured data. A CLI command generates a markdown snapshot on demand. The generated doc is a view, not a source of truth — like how the board view and tree view are both views of the same items.

**Strengths:** Single source of truth (tracker). Git-diffable snapshots when needed. No manual sync. Rich context lives in linked docs (already the pattern). Agent can use tracker as work queue — stale tracker means wrong work, which is self-correcting.

**Weaknesses:** Requires enriching the tracker's data model (currently too thin). Generated markdown is less rich than hand-written narrative. If the app is broken, the live tracker is inaccessible (but the last generated snapshot survives in git).

### Assessment

Option A fails on enforcement — SmartMemory's ROADMAP.md works because one human keeps it updated, not because the format self-enforces. Option C is the worst — double maintenance. Option B works if the data model is rich enough. Option D adds the portability/git-history escape hatch on top of B.

The key insight: if the tracker is the agent's **work queue** (forge-loop reads it to pick the next task), the agent has self-interest in keeping it current. That's enforcement through usage, not discipline.

## Design Decisions

Approve each independently. Rejected items get reworked, not dropped.

- [ ] **D1: Tracker is primary, markdown is generated** — Based on Options analysis above. No manually maintained ROADMAP.md.
- [ ] **D2: New fields** — priority, effort, planLink, successMetric, semanticId on every item.
- [ ] **D3: New entity types** — `feature` and `initiative` added to valid types.
- [ ] **D4: Typed edges** — `blocks`, `informs`, `implements`, `supports` replace untyped connections.
- [ ] **D5: Forge-loop reads tracker as work queue** — Agent queries API for next unblocked high-priority item.
- [ ] **D6: Default sort** — Discovery: most recent first. Execution: priority descending.
- [ ] **D7: Semantic IDs** — `FORGE-VT-1` style human-readable IDs alongside UUIDs.
- [ ] **D8: Markdown export** — `vision-track.mjs export --format roadmap` generates SmartMemory-style roadmap.
- [ ] **D9: Migration is backward compatible** — Existing items get defaults, nothing breaks.

---

## Design Detail

### Data Model: New Fields

Add to every tracker item:

| Field | Type | Default | Purpose |
|---|---|---|---|
| `semanticId` | string | auto-generated | Human-readable ID: `FORGE-VT-1` |
| `priority` | enum: `high`, `medium`, `low` | `medium` | Work ordering |
| `effort` | string | `""` | Freeform estimate: "3-5 days", "2h" |
| `planLink` | string (file path) | `""` | Path to design/plan doc |
| `successMetric` | string | `""` | How we know it's done |

Semantic ID format: `{PROJECT}-{ABBREV}-{N}`. Generated on create from title abbreviation. Stored as a field, used in exports and cross-references.

### Data Model: Entity Types

Current valid types: `idea`, `decision`, `question`, `thread`, `artifact`, `task`, `spec`, `evaluation`.

Add:

| Type | Purpose | Example |
|---|---|---|
| `feature` | Deliverable unit of work with phases | "Enrich Vision Tracker data model" |
| `initiative` | Container grouping related features | "Agent Visibility" initiative |

Hierarchy: initiative → feature → task/spec/decision. Same as SmartMemory ROADMAP pattern. Connected via `implements` edges, rendered as tree view.

### Data Model: Typed Edges

Current connections are untyped. Add edge types:

| Edge type | Style | Meaning |
|---|---|---|
| `blocks` | Solid red | Hard dependency — B can't start until A completes |
| `informs` | Dashed blue | Soft — A's output feeds B's thinking |
| `implements` | Solid green | A is the execution of B |
| `supports` | Dotted gray | Loose association |

Edge type stored on connection objects. Existing untyped connections default to `informs`. Views render edges with distinct visual styles (already designed in Session 12 ontology).

### Forge-Loop Integration

The forge-loop skill updates to use the tracker as its work queue:

```
1. Query:   GET /api/vision/items?status=planned&priority=high
2. Filter:  Exclude items where any `blocks` dependency is incomplete
3. Pick:    Highest priority unblocked item
4. Claim:   PATCH status → in_progress
5. Work:    Feature-development lifecycle (breadcrumbs track intent)
6. Done:    PATCH status → complete, confidence → updated
7. Repeat:  Query again
```

The handoff.md becomes lightweight: "See tracker for current state." Session context is: what the tracker says + breadcrumbs for in-flight intent.

### API Extensions

**New query parameters** on `GET /api/vision/items`:

| Param | Type | Behavior |
|---|---|---|
| `priority` | string | Filter by priority level |
| `unblocked` | boolean | Exclude items with incomplete `blocks` dependencies |
| `type` | string | Filter by entity type |
| `sort` | string | `recency` (default in Discovery), `priority`, `status`, `confidence` |

**Item create/update** accepts new fields. Backward compatible — existing items get defaults.

**New endpoint** `GET /api/vision/export?format=roadmap`:

Returns generated markdown in SmartMemory ROADMAP format. Groups items by status (active → planned → parked → complete). Each feature block includes all fields. Dependency graph rendered as mermaid.

### Default Sort by Mode

| Mode | Default sort | Rationale |
|---|---|---|
| Discovery | Most recent first | Fresh thinking surfaces first |
| Execution | Priority (high → low) | Work queue ordering |

User can override. Sort preference remembered per mode (session state, same as current view overrides).

### Markdown Export Format

`vision-track.mjs export --format roadmap` generates:

```markdown
# Forge Roadmap
**Generated:** 2026-02-13  **Items:** 45  **Active:** 3  **Blocked:** 1

---

## Active Development

### Feature: Vision Tracker as Primary Roadmap (FORGE-VT-1)
**Status:** 🚧 IN_PROGRESS  **Priority:** ⚡ HIGH  **Effort:** 3-5 days
**Depends On:** —
**Blocks:** FORGE-BRD-1 (Breadcrumbs-to-Vision bridge)
**Plan:** docs/plans/2026-02-13-vision-tracker-design.md
**Success Metric:** Agent reads tracker as work queue; no manual ROADMAP.md

Enrich tracker data model, make it the work queue for forge-loop,
generate ROADMAP.md as a view.

---

## Planned Features
...

## Dependency Graph

(mermaid diagram of blocks/implements edges)
```

Not maintained. Regenerated on demand. Committed as a snapshot when useful (releases, handoffs to humans who prefer markdown).

### What This Does NOT Change

- **UI views** — List, board, tree, graph remain deterministic. They render richer data but the layout is fixed.
- **Breadcrumbs** — Intent tracking is orthogonal. Breadcrumbs capture in-flight activity; tracker captures planned/completed work.
- **Detail panel** — Shows new fields inline. Plan link is clickable (opens in canvas).
- **Vision-track.mjs CLI** — Same commands, extended with `--priority`, `--effort`, `--plan-link`, `--success-metric`, `--semantic-id` flags. New `export` subcommand.
- **Server architecture** — Same Express endpoints, extended schema. No new services.

### What This Enables Downstream

| Feature | How this unblocks it |
|---|---|
| Breadcrumbs-to-vision bridge | Bridge creates tracker items from live intent. Richer model means richer items. |
| Auto-unblocking | Completing an item with `blocks` edges surfaces dependents as ready. Agent picks them up. |
| Agent monitoring | Breadcrumbs + tracker status = full visibility of what's happening and what's planned. |
| Decision chips | Decision items with `blocks` edges naturally surface as "things that need resolving." The 3-mode dial governs whether they gate, flag, or skip. |
| Roadmap snapshots | `export` command generates markdown for git history, sharing, offline reading. |

### Migration

Existing 40+ items keep their UUIDs. New fields get defaults:
- `semanticId`: generated from title on first export (or manual assignment)
- `priority`: `medium`
- `effort`: `""`
- `planLink`: `""` (can be backfilled for items that already have linked docs)
- `successMetric`: `""`
- Existing connections: typed as `informs` (the most common current usage)

No breaking changes. All existing views, API calls, and CLI commands continue working.

---

## Gaps Between Here and There

| Gap | Current State | After This Design |
|---|---|---|
| No priority on items | All items equal weight | `high`/`medium`/`low` drives ordering |
| Untyped connections | All edges look the same | `blocks`/`informs`/`implements`/`supports` with visual styles |
| No feature/initiative types | Flat hierarchy | Tree: initiative → feature → task |
| Agent reads handoff for next work | Manual, stale | Agent queries tracker API for unblocked high-priority items |
| No roadmap doc | CLAUDE.md bootstrap list | Generated from tracker on demand |
| No semantic IDs | UUIDs only | `FORGE-VT-1` style IDs for humans |
| Discovery sort | Alphabetical/manual | Most recent first by default |

---

## Success Metric

The agent uses the tracker as its work queue. No one manually maintains a ROADMAP.md. Completing an item auto-surfaces what's next. The tracker is always current because using it IS the work, not a reporting step after the work.
