# Decision: Deterministic UI with Dynamic Content

**Date:** 2026-02-11
**Status:** DECIDED
**Context:** Forge UI architecture — should views be fixed or LLM-generated?
**Related:** [UI-BRIEF](../UI-BRIEF.md), [PRD](../PRD.md)

---

## Question

How deterministic should Forge's UI be? Can it be dynamic based on what the LLM produces, or is the fixed view set sufficient?

## Decision

**Deterministic UI, dynamic content.**

- The views, layout, interactions, and navigation are fixed. Fast, predictable, muscle memory.
- The LLM contributes content that flows into existing views: summaries, proposals, analysis, distilled conversations.
- The LLM is an agent connector, not a UI connector. It produces domain objects (Work items, artifacts, evidence, briefings). The UI renders domain objects.

## Rationale

- Core workflows (check status, update work, view dependencies) happen hundreds of times and need sub-second, predictable interaction. Dynamic UI adds latency and breaks "status at a glance in 3 seconds."
- Dynamic questions ("what's at risk?", "why is this stalled?") are answered by smart queries and generated content rendered in existing views — not by generating new views.
- The connector architecture already supports this: the LLM never needs to know about the UI, and the UI never needs to wait for the LLM.

## What This Requires

The dynamic content layer needs three capabilities not yet in the spec:

### 1. Rich Markdown Artifacts (inline editing)

Artifacts aren't just attached files — they're living documents created and edited inside Forge. Discussion summaries, design rationale, brainstorm notes, specs. The UI provides a deterministic editor; the content is dynamic.

This is how the LLM's output surfaces in Forge: as editable markdown artifacts on Work items.

### 2. Conversation Distillation

Sessions (human-AI, human-human) produce long transcripts. Forge distills these into structured outcomes:
- Decisions made → become Work items (label: "decision") or update existing artifacts
- Questions raised → become Work items (label: "decision", status: "planned")
- Action items → become Work items (label: "task")
- Learnings → feed into memory

The raw transcript is evidence. The distillation is what feeds back into the system.

### 3. Memory (persistent cross-session knowledge)

Knowledge that accumulates across sessions:
- Patterns discovered
- Preferences stated
- Corrections made
- Context that informs future work

Memory prevents every new session from starting cold. It's not history (what happened) — it's knowledge (what we know).

## How These Connect

```
Conversation → Transcript (evidence)
           → Distillation → Decisions (Work items)
                          → Questions (Work items)
                          → Action items (Work items)
                          → Learnings (memory)
           → Artifacts updated with outcomes
           → Memory updated with knowledge
```

## Implications for the Data Model

- **Artifacts** need to support inline rich text editing, not just file attachment
- **Evidence** needs a "transcript" type for raw session records
- **Memory** is a new concept — persistent knowledge that isn't attached to a specific Work item but informs all work. Could be project-level or global.
- **Distillation** is a process, not an entity — it takes evidence (transcript) and produces Work items, artifact updates, and memory entries

## Implications for the UI-BRIEF

The UI-BRIEF's design principles hold:
- Information density, hierarchy-first, speed, keyboard-first, dark mode — all unchanged
- The dynamic content lives inside the deterministic structure
- Add to the brief: artifact editor view (markdown, inline, on Work items)

## Rejected Alternatives

- **Dynamic UI generation** — LLM generates or modifies views. Rejected: breaks predictability, adds latency, loses muscle memory. Makes Forge feel like a chatbot, not mission control.
- **Fully static artifacts** — artifacts are only attached files. Rejected: forces content creation outside Forge, which means thinking happens out of band.
