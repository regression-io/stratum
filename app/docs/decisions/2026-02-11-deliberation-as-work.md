# Decision: Deliberation Is Work

**Date:** 2026-02-11
**Status:** DECIDED
**Context:** How does Forge support brainstorming, discussions, and decisions — not just task execution?
**Related:** [Deterministic UI Decision](2026-02-11-deterministic-ui.md), [PRD](../PRD.md)

---

## Question

How do brainstorming, discussions, and decision-making fit into Forge's model? Do we need new entity types, or can the existing model handle it?

## Decision

**Deliberation is Work.** Brainstorming sessions, discussions, and decisions are all Work items with different labels. No new entity types needed.

## How It Maps

| Activity | Work Item Pattern |
|----------|------------------|
| Brainstorm | Label: "brainstorm". Artifacts: notes, ideas. Status: planned → in_progress → complete. Children: decisions and questions that emerge. |
| Discussion | Label: "discussion". Artifacts: transcript, arguments for/against. Status: in_progress while active. Children: decisions reached. |
| Decision | Label: "decision". Name is the question. Artifacts: rationale, rejected alternatives. Status: planned (raised) → in_progress (discussing) → review (proposed) → complete (decided). |
| Spec | Label: "spec". Artifact: the spec document. Status: follows review cycle. Children: work items derived from the spec. |

## Cross-Feeding via Dependencies

The `informs` dependency type connects deliberation to execution:

- A brainstorm **informs** decisions
- A decision **informs** specs and work items
- A decision **blocks** work items that depend on it
- A spec **informs** the work items derived from it

`informs` is the deliberation relationship. `blocks` is the execution relationship. Both are already in the data model.

## The Hierarchy

```
Initiative: Forge Phase 1
  Feature: UI Architecture
    Brainstorm: UI approach exploration
      artifacts: [brainstorm notes]
      informs → Decision: Deterministic vs. dynamic UI
    Decision: Deterministic vs. dynamic UI
      artifacts: [discussion summary, rationale]
      evidence: [session transcript]
      blocks → Task: Update UI-BRIEF with artifact editor
      informs → Decision: LLM integration pattern
    Decision: Deliberation model
      artifacts: [this document]
      informs → Task: Update data model for rich artifacts
```

## Implications

1. **Forge is a knowledge work tracker, not just a task tracker.** Thinking is work. Decisions are deliverables. If we only track tasks, we'll always do the thinking somewhere else.

2. **The `informs` dependency type is critical.** It's how deliberation feeds execution. Without it, the knowledge graph is disconnected — decisions float without linking to the work they influence.

3. **Conversation distillation is the bridge.** Raw conversations produce transcripts (evidence). Distillation extracts decisions, questions, and action items (Work items) and learnings (memory). This is how ad-hoc thinking enters the structured system.

4. **Labels are the taxonomy, not entity types.** "brainstorm", "discussion", "decision", "task", "feature" — all Work items, differentiated by label. This keeps the model simple and extensible. Users can create their own labels without schema changes.

## Rejected Alternatives

- **New entity types for Discussion/Decision** — adds complexity, requires schema changes, and the existing Work model already handles it. Labels are cheaper than entities.
- **Discussions outside Forge** — the current state. Thinking happens in chat transcripts, meetings, docs — then outcomes are manually entered into Forge. This is the problem we're solving.
