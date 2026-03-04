# Discovery Insight: Discovery as a Primitive

**Date:** 2026-02-11
**Parent:** [Level 2 Brainstorm](level-2-brainstorm.md)
**Status:** Tentative — just crystallized

---

## The realization

We tried to model this discovery session as a Work item. It didn't fit. The status lifecycle assumes known endpoints. Children are emergent, not planned. The unit of work isn't identifiable until after the fact.

The resolution: **Discovery isn't Work. Discovery is the process that produces Work.**

You go in with a question or a hunch. You come out with items you can track — decisions, specs, tasks, directions, kill decisions. The process itself isn't a Work item. What it produces becomes Work items.

---

## The expanded primitives

Previously 3. Now 4:

| Primitive | What it is | What it tracks |
|-----------|-----------|----------------|
| **Discovery** | The process that produces Work | Questions, modes, evidence, process trace |
| **Work** | The outputs — things to track and do | Status, hierarchy, artifacts, dependencies |
| **Policy** | Constraints on decisions | Gate/flag/skip dials at decision points |
| **Session** | Actors doing the work | Human or AI, assignment, context |

### How they relate

```
Discovery → produces → Work items
Work items → governed by → Policies
Work items → worked on by → Sessions
Sessions → can trigger → Discovery (when something breaks or a question surfaces)
Discovery → happens within → Sessions (the conversation is a session)
```

Discovery and Session are intertwined but distinct:
- **Session** = who's doing it, when, with what context
- **Discovery** = the exploratory process happening within a session (or across sessions)

Not every session involves discovery. An implementation session might be pure execution. But when a session hits a question, it enters discovery mode.

---

## What Discovery looks like as a primitive

| Property | Description |
|----------|-------------|
| **Trigger** | What started it — question, hunch, friction, opportunity, assignment |
| **Mode** | Current mode — brainstorm, research, prototype, integration (can shift) |
| **Participants** | Human, AI, or both |
| **Outputs** | Work items produced (decisions, insights, specs, directions, kill decisions) |
| **Process trace** | The meta-record of what happened — moves, triggers, sequence |
| **Confidence** | Bayesian posterior on the outputs — how tested are they? |
| **State** | Open (exploring), converging (integrating), closed (outputs crystallized) |

### State is simpler than Work status

Discovery doesn't need planned → ready → in_progress → review → complete. It needs:
- **Open** — exploring, divergent, questions active
- **Converging** — integrating findings, narrowing
- **Closed** — outputs produced, process complete (or abandoned)

---

## What this changes

### F1 (Work Tracking) stays clean
Work items are discrete, trackable, have status lifecycles. Discovery's messy outputs get crystallized into Work items before entering F1. F1 doesn't need to handle fuzziness.

### F4 (Discovery Support) becomes more central
It's not just a feature — it's support for a primitive. Discovery support = helping the process that produces all the Work items.

### F6 (Distillation) bridges Discovery → Work
Distillation is the mechanism that extracts Work items from discovery. It's the crystallization machine. Without it, discovery outputs stay in conversation and never become trackable.

### The meta-trace has a home
The process trace is a property of Discovery, not of Work. It records how the discovery process ran — which is exactly what we've been doing in [session-5-meta-trace.md](session-5-meta-trace.md).

---

## Discovery operates at every phase boundary

A goal like "we need to track things" is not requirements. It's a vision or directive. Requirements emerge from the Q&A process of decomposing that goal into steps — with decisions made along the way. That decomposition process IS discovery.

This means Discovery isn't just "the first phase." It's the mechanism that operates between any two levels of granularity:

```
Vision/Goal  →  [discovery: decompose, decide]  →  Requirements
Requirements →  [discovery: design, decide]      →  Design
Design       →  [discovery: plan, decide]        →  Implementation steps
```

Each arrow is a discovery process. Each involves questions, evidence, and decisions. Each produces more concrete outputs from looser inputs.

**Implication:** Discovery as a primitive isn't "the exploration phase" — it's the *connective tissue between all phases*. Whenever you take something vague and make it concrete through Q&A and decisions, you're running a Discovery process. That's why it can't be a Work item — it's the process that produces Work items at every level.

This also reframes the taxonomy phases. They're not sequential stages you pass through. They're *levels of concreteness*. Discovery is how you move between levels.

---

## Open questions

- Does this break the "3 primitives × 3 sub-constructs" architecture from the brainstorm doc?
- Is Discovery really a 4th primitive, or is it a mode that Sessions enter?
- ~~How does Discovery relate to the taxonomy phases?~~ → Answered: Discovery is the mechanism between phases, not a phase itself. Phases are levels of concreteness.
- Where does the process trace persist? With the session? As its own entity?
- ~~If Discovery operates at every boundary, does the "discovery phase" label in the taxonomy still make sense?~~ → Resolved: phase renamed to "Vision." Discovery = primitive (process mechanism). Vision = phase label (level of concreteness).
