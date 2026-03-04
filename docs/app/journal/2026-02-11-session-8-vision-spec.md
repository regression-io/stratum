# Session 8: Vision Spec → Design → The Jigsaw

| | |
|---|---|
| **Date** | 2026-02-11 |
| **Previous** | [Session 7: Requirements Emerge](2026-02-11-session-7-requirements-emergence.md) |

---

## What happened

### Part 1: Vision component spec

Committed the remaining Session 7 work (matrices, CR6 sub-agent/knobs updates), then moved from requirements to spec. The human asked: do we need the Requirements row in the matrices to build out Vision? Answer: no. The Vision row + CR1-CR7 is self-contained. So we wrote the spec.

Every spec item traces to its source — matrix cell or core requirement. The human caught two things: graph visualization was a random idea that had crept into the matrices as if it were a requirement (removed), and the acid test isn't parity but improvement — would sessions 5-7 have been *better* in this component? And delight counts as better.

Design principles were initially in the spec. The human called it: those are design decisions, not spec constraints. Moved to a new design doc.

### Part 2: Design approaches

Identified six design approaches (scenario walkthrough, interaction model first, visual language first, reference-driven, prototype-first, slice-driven). The human's correction: designers aren't structured. They want a palette of tools, not a process to follow. The approaches aren't a menu — they're a palette. Same pattern as "rails are for the AI, not the human."

Then the question of whether to use design tools (Figma, etc.) or just prototype. The human raised: if we want to build on rails, we need to treat different agents for different phases as team members. A design agent uses design tools. A coding agent writes code. The pipeline should model this.

### Part 3: The jigsaw

The session hit the core strategic question: **can you iteratively build a tool whose value requires the whole pipeline?**

The agent proposed a bridge analogy — falsework, towers first, replace scaffolding piece by piece. The human corrected: **it's a jigsaw, not a bridge.** A bridge has structural dependencies (can't have the middle without the sides). A jigsaw has no order — any piece can drop in at any time. The picture emerges from whatever order the pieces fall.

Then the human connected it to the 3-mode dial: **"iterative vs waterfall" is a false dichotomy.** It's the same pipeline. The dial controls how it feels:

- **Gate** = feels like waterfall (every decision discussed)
- **Flag** = balanced iteration
- **Skip** = "Go! Don't bother me, just build it" — fully autonomous, most iterative

What we've been doing (sessions 5-8) is gate mode. That's why it felt like waterfall. Same pipeline underneath.

The pipeline is descriptive, not prescriptive. Every user works differently — some sketch, some code, some brainstorm, some say "build me X" and walk away. The AI tracks where pieces are, what gaps remain, and surfaces observations. The user never thinks about the pipeline. The AI uses it to understand.

### New files
- `docs/specs/2026-02-11-vision-component-spec.md` — Vision component behavioral spec with full provenance
- `docs/design/vision-component-design.md` — Design doc with build strategy, approaches palette, jigsaw model

### Modified files
- `docs/requirements/matrices.md` — Removed graph viz note, filled Design row across all 4 matrices
- `docs/journal/README.md` — Session 8 entry added
- `src/components/Canvas.jsx` — Tab headings enlarged, close button visible, default font 14px

---

## What we learned

1. **The acid test is improvement, not parity.** "Can it be done?" is table stakes. "Is it better?" is the bar. Delight is an improved outcome.

2. **Provenance makes specs auditable.** Every spec item traces to a matrix cell or CR. Nothing is invented. If it can't trace back, it shouldn't be in the spec.

3. **Design approaches are a palette, not a process.** Designers reach for whatever tool fits the moment. The structure is for the AI to know what's available. The human just works.

4. **Jigsaw, not bridge.** The pipeline has no required build order. Any piece can drop in at any time. The picture emerges. Bridges have structural dependencies; jigsaws don't.

5. **"Iterative vs waterfall" is a false dichotomy.** It's the same pipeline. The 3-mode dial controls how it feels. Gate = waterfall. Skip = fully iterative. We've been in gate mode — that's why it felt like waterfall.

6. **The pipeline is descriptive, not prescriptive.** The AI's mental model, not the user's workflow. Users never think about the pipeline. The AI uses it to track state, surface gaps, and steer when configured to.

7. **Falsework was never waste.** 8 sessions of real work on markdown + terminal + chat. The scaffolding let us figure out what the permanent structure needs to be.

8. **Fill matrix rows on the fly.** Don't wait for a dedicated session — capture lived data as it emerges. Design row partially filled from this session's actual design work.

9. **Specialized agents per phase.** If Compose's thesis is a structured pipeline, each phase should be handled by a specialized agent with appropriate tools. Design agent uses design tools. This is the industrialized version.

---

## Open threads

- [ ] First permanent piece — the AI's ability to observe and track pipeline state, regardless of user's work order
- [ ] Design the See verb — what does "where are we?" actually look like?
- [ ] Pipeline skeleton — how do jigsaw pieces connect? What's the interface between them?
- [ ] Specialized agents — how does a design agent differ from a coding agent in practice?
- [ ] Fill remaining matrix rows as we go

---

*Jigsaw, not bridge. The dial controls whether it feels like waterfall or iteration. The pipeline is the AI's model, not the user's process. Delight is an improved outcome. Eight sessions on falsework — never waste.*
