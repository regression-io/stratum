# Discovery: Work Tracking Meta-Structure

**Date:** 2026-02-11
**Phase:** Discovery (active)
**Work area:** How Forge tracks its own work — and by extension, how it tracks all work
**Participants:** Human + Claude Code agent
**Source conversation:** Session 3 (this session)

---

## The Problem

The integration roadmap (`docs/plans/2026-02-11-integration-roadmap.md`) tracks the **build sequence** — what to implement in what order. But it doesn't track where we are in the **thinking** about each item. Implementation is the last step. Everything before it — brainstorming, discussing, designing, deciding — is invisible in the roadmap.

The roadmap said "Phase 0.4: Persistence Connector — NEXT" which implied "go build it." But the actual state was: we're still in brainstorming and design. The roadmap is not the primary source of truth for where we are.

**Core insight:** The thinking IS the work. Implementation is the easy part once the thinking is done. Forge exists to track knowledge work — deliberation, decisions, design — not just tasks. The project's own tracking should model that.

---

## What We Discovered

### 1. Every work area has its own lifecycle

Each significant piece of work progresses through the taxonomy phases:

```
discovery → requirements → design → planning → implementation → verification → release
```

The roadmap collapses everything before implementation into a single bullet. What's needed is a **master plan** that tracks each work area against its current phase in this lifecycle.

### 2. Work areas are hierarchical

Not flat. A work area can contain work areas:

- **Product Vision** contains brainstorm, PRD, use cases
- **Infrastructure** contains terminal embed, crash resilience, supervisor
- **Persistence** might contain schema design, migration, API layer

The hierarchy IS the navigation. Same principle as Forge's tree view. Arbitrary depth, just like the Work primitive.

### 3. Three persistence layers, not one

Different consumers need different representations of the same data:

| Layer | Serves | Format | Source of truth for |
|-------|--------|--------|-------------------|
| **Schema layer** | UI, queries, tracking | DB/JSON/structured frontmatter | State (phase, status, dependencies, hierarchy) |
| **Content layer** | LLM reasoning, human understanding | Markdown prose, artifacts | Understanding (the "why" and "how") |
| **Graph layer** | Discovery, navigation, impact analysis | Relationships between entities | Connections (blocks, informs, relates_to) |

Obsidian = layers 2+3 without layer 1. A database = layer 1 without 2+3. Forge needs all three.

### 4. Structure crystallizes as you move down the lifecycle

Early phases are prose-heavy, late phases are structure-heavy:

```
discovery       → mostly prose, loose, exploratory
requirements    → prose with structure emerging (use cases, criteria)
design          → decisions lock in, rationale captured, specs get shape
planning        → structured breakdown, dependencies, sequence
implementation  → fully constrained, schema-driven, code
verification    → structured evaluation against locked criteria
release         → pure process, checklist
```

Each phase transition **crystallizes** — what was fluid becomes fixed. A brainstorm becomes a decision. A decision becomes a spec. A spec becomes a plan. A plan becomes code.

The 3-mode dial governs **who** crystallizes at each transition:
- **Gate:** Human locks it in
- **Flag:** AI proposes the crystallization, human approves
- **Skip:** AI locks it in autonomously

### 5. Loopback is essential — and must carry evidence

The lifecycle isn't just downward. Verification can loop back to design. Implementation can loop back to requirements. Release can reopen discovery.

When looping back, the system must capture:
- **What triggered the loopback** — a failed verification? A new insight? A constraint change?
- **What the previous state was** — the old decision shouldn't vanish. "We decided X, then learned Y, now we decide Z."
- **What goes stale** — downstream artifacts based on the changed item are potentially invalid. The `informs` dependency models this; the system surfaces it.

### 6. Forge facilitates transitions AND loopbacks

Forge's core job: help knowledge move through the lifecycle — crystallizing at each transition, preserving evidence, enabling loopback with context. Not just tracking where things are, but actively supporting the transformation from loose thought to locked artifact to running code... and back again when reality intervenes.

### 7. The master plan shows where everything is

The master plan is the index of all work areas against their lifecycle phases. It replaces the roadmap as the primary source of truth for "where are we."

The roadmap becomes a derived view — the implementation sequence extracted from the master plan.

Open design questions for the master plan:
- What does each node show? (Phase marker, summary, artifact links, full lifecycle ribbon?)
- Where do artifacts live? (Stay where they are, linked from master plan? Per-work-area directories?)
- One document or a directory structure?

### 8. Multiple work areas at different phases simultaneously

This is always true: persistence might be in planning while UI design is in discovery while terminal embed is in verification. The master plan tracks parallel, unsynchronized lifecycles.

### 9. The meta-level is recursive

This very discussion — designing how Forge tracks work — is itself work at the discovery phase. It will crystallize into decisions, then specs, then code. Forge should be able to represent this recursion: the tool tracking the design of the tool.

---

## What's Been Resolved Since This Doc

- **Discovery process** — explored in [Discovery Process](discovery-process/README.md). Produced the working dimensions and knowledge layer model.
- **Working dimensions** — resolved to 3: What, How, Why-factual. Who and personal-Why are onboarding context, not working dimensions. See discovery-process doc, "Current position (revised)."

## What's Still Open

- ~~How does discovery actually work as a process?~~ → Explored, dimensions resolved. Level 2 brainstorming now needed.
- **Level 2: How do the dimensions manifest mechanically?** — What does What/How/Why-factual look like in the UI, in the data model, in the AI's reasoning?
- Master plan format and structure
- Persistence layer architecture (the three-layer model needs design)
- How do transitions between phases work mechanically?
- How does loopback work mechanically?
- How does the 3-mode dial interact with phase transitions?
- How do we bootstrap this structure for existing work areas that are already mid-lifecycle?

---

## Existing Work Areas (snapshot)

Current state of all significant work areas, as identified during this session:

| Work area | Current phase | Key artifacts |
|-----------|--------------|---------------|
| Product vision | Requirements (done) | brainstorm.md, PRD.md, use-cases.md |
| Architecture decisions | Design (done) | decisions/*.md, taxonomy.md, connectors.md |
| UI design | Design (active) | UI-BRIEF.md, specs/, .interface-design/system.md |
| Process definitions | Design (done) | process/delivery-intake.md, process/spec-writing.md |
| Base44 evaluation | Verification (done) | evaluations/base44-ui-eval.md, bootstrap-progress.md |
| Terminal embed | Implementation (done) | server/terminal.js, components/Terminal.jsx |
| Crash resilience | Implementation (done) | server/supervisor.js |
| Persistence connector | Design (plan written, not validated) | plans/persistence-connector-plan.md |
| Agent monitoring | Discovery (barely started) | One paragraph in roadmap |
| Interface design system | Discovery (active) | .interface-design/system.md |
| Session handoff | Design (proven by use) | .claude/handoff.md, session context pattern |
| Work tracking meta-structure | Discovery (THIS DOCUMENT) | This file |

---

*This is a discovery artifact. It captures what we've explored and what questions remain. Nothing here is decided — it's the raw material for decisions that come next.*
