# How to Build the Visibility Layer

| | |
|---|---|
| **Date** | 2026-02-12 |
| **Context** | Session 10 — architecture analysis, Base44 re-evaluation |
| **Status** | Needs planning exercise |
| **Related** | [Visibility as Value](2026-02-12-visibility-as-value.md) |

---

## Three layers

### Layer 1: The graph engine (exists, needs hardening)

Items with type, confidence, status, phase. Connections (informs, supports, blocks, contradicts). Persistence across sessions. Real-time sync via WebSocket.

Currently: VisionStore (JSON-file-backed) + VisionServer (REST + WebSocket broadcast). 24 seeded items, 16 connections. CRUD via REST, full state broadcast on mutation.

Needs: robustness, validation, conflict handling, possibly migration to a real store.

### Layer 2: The visual surface (started, needs evolution)

Currently: Vision surface with three layout modes (spatial, dense, timeline), card types with confidence dots, click-to-ripple connection tracing, pipeline bar with phase filtering.

Needs:
- Inline item creation from the surface (not just API)
- Item editing, connection drawing
- Detail panel (Base44's WorkDetailPanel is a good pattern)
- Acceptance criteria, gap analysis (Base44 patterns)
- Tree view and board view as additional lenses

### Layer 3: The conversation bridge (not started — the differentiator)

AI observes its own conversation and extracts decisions, ideas, questions. Posts to the graph engine as items with connections. Phase awareness lives here — the AI recognizes "that was a design decision" and tags it. Confidence tracking lives here — the AI assesses "untested" vs "pressure-tested." The 3-mode dial governs when the AI creates items autonomously vs asks first.

This is the hard part and the unique value.

---

## Base44 re-evaluation

### Context

Base44 UI was evaluated in session 1 against the original UI-BRIEF. Now re-evaluated against the "visibility as value" framing from session 10.

### What Base44 is

A traditional work management UI: tree view, kanban board, dependency graph. Work items with status/type/phase/description. Acceptance criteria. Evaluation gap analysis. Manual creation via dialogs and forms. REST-based, no real-time. Well-built, clean components, dark theme.

### Where it fits the vision

| Fits | Doesn't fit |
|---|---|
| Data model fields (type, phase, status, artifacts, dependencies) | Interaction model (manual creation, forms, dialogs) |
| Three-view concept (tree, board, graph) validates lenses | No real-time / WebSocket |
| Evaluation/gap analysis pattern is genuinely useful | No confidence concept |
| Component patterns (tree nodes, kanban columns, detail panel) | No AI integration path |
| Dark theme, Radix/Tailwind foundation | No connection tracing as primary interaction |
| | No phase awareness as intelligence |
| | No governance model (dial) |

### Verdict (updated)

Base44 is valuable as **pattern reference and data model reference**, not as a foundation to build on. The interaction model is wrong (manual vs conversational emergence). The architecture is wrong (REST vs real-time). But the visual patterns (detail panel, gap analysis, tree nodes) and data model fields are directly reusable as design input.

### Specific patterns to adopt

1. **WorkDetailPanel** — right-side panel showing full item details, inline editing, related items. Adapt for vision surface.
2. **EvaluationGapsPanel** — structured gap analysis with category classification and gap-to-item conversion. This IS pressure testing, already built.
3. **StatusBadge / ConfidenceDots** — visual indicators. We already have confidence dots; Base44's status badges are a good reference.
4. **FilterBar** — multi-axis filtering (status, project, label, tag). Our pipeline bar is simpler; may need to evolve.
5. **DependencyGraph** — SVG canvas with topological sort. Our ConnectionLayer is simpler; this shows where it could go.

---

## What exists today

| Component | State | Notes |
|---|---|---|
| Terminal (xterm.js PTY) | Working | Primary interaction surface |
| Canvas (markdown tabs + vision surface) | Working | Multi-renderer shell |
| VisionStore + VisionServer | Working | REST + WebSocket, JSON persistence |
| Vision surface components | Working | Cards, connections, ripple, 3 layouts, pipeline bar |
| Base44 UI | Reference only | Not integrated, wrong architecture |

---

## Open questions for planning

1. What's the build order? Layer 2 usability first, or Layer 3 (conversation bridge) as the differentiator?
2. How much of Base44 do we port vs rebuild? Component patterns only, or actual code?
3. What does a minimal conversation bridge look like? Full NLP extraction, or simple command-driven ("that's a decision")?
4. Where does the 3-mode dial get implemented? Per-item? Per-phase? Global?
5. How do we test the thesis? What's the smallest thing we can build that proves visibility enables steering?

---

*Analysis complete. Needs a planning exercise to turn into action.*
