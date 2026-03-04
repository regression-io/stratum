# Core Requirements

**Date:** 2026-02-11
**Parent:** [Requirements](README.md)
**Source:** [Needs](needs.md) — verbs, things, lenses, phase dynamics
**Status:** Pressure-tested, revised. See [Core Requirements Counterfactuals](core-requirements-counterfactuals.md).

---

## CR1: The system must support lifecycle phases

The system must support these phases of knowledge work:

**Vision → Requirements → Design → Planning → Implementation → Verification → Release**

Phases are not enforced as a linear sequence. Any phase can loop back to any other. The system tracks the macro phase (where the center of gravity is) while allowing items to exist at any phase regardless.

Users use what applies. A research project may stop at vision. A full build goes to release. The phases are available, not mandatory.

---

## CR2: At each phase, users work with the same types of things

The system must support these at every phase:

1. **What they're thinking about** — ideas, brainstorms, explorations
2. **What they've decided** — committed positions, rationale, rejected alternatives
3. **What they need to figure out** — open questions, gaps, unknowns
4. **What they need to do** — tasks, plans, specs
5. **How those things relate** — connections between items
6. **Where each thing stands** — status, confidence, what needs attention
7. **What's been produced** — outputs, artifacts, deliverables (code, docs, designs, test results, deployed services)

The things are the same everywhere. The phase is context, not content.

---

## CR3: Four verbs operate on all things at all phases

The system must enable:

- **See** — visibility into the structure, state, and meaning of things
- **Change** — create, evolve, connect, synthesize, and mark things
- **Evaluate** — challenge claims, update confidence, detect staleness, crystallize or kill
- **Execute** — direct agents, assign work, monitor progress, collect results

These verbs are orthogonal to phase. You see, change, evaluate, and execute at every phase.

---

## CR4: Universal processes apply at every phase

The system must support these processes across all phases:

- **Discovery** — Q&A decomposition, exploring unknowns, converging on answers
- **Evaluation** — pressure testing, counterfactuals, confidence assessment
- **Synthesis** — distilling multiple sources into consolidated outputs
- **Capture** — recording knowledge, decisions, rationale as they happen

These processes are the connective tissue between phases. You discover your way from one phase to the next. They interleave — discovery involves evaluation, evaluation involves synthesis. How they relate to each other is a design question; the requirement is that all are supported everywhere.

Phase-associated processes also exist (decomposition, building, testing, deploying) with stronger affinity to specific phases but not exclusive to them. Phase affinity is LLM guidance context, not a system behavior — the system does not behave differently based on affinity.

---

## CR5: Cross-cutting lenses apply to everything

The system must support viewing and operating through these dimensions:

- **Confidence** — how sure we are (untested, low, moderate, high). Applies to items and processes.
- **Governance** — the 3-mode dial (gate, flag, skip). Inherits downward: project sets defaults, phases can override, items can be exceptions. The system does not present a dial per micro-decision — governance cascades.
- **Scope** — level of granularity (project → feature → task → subtask). Items nest.
- **Actor** — who is doing the work (human, AI agent, background sub-agent).
- **Time** — when things were created, changed, superseded. Required for staleness and evolution.

These lenses are orthogonal to phase, things, and verbs. They overlay everything.

---

## CR6: The AI must be proactive

The system must support an AI that:

- Initiates, not just responds — reaches out to ask questions, surface observations, flag concerns
- **Challenges actively** — runs counterfactuals, tests claims, pushes back on weak confidence. Challenging is a behavioral mode, not just a response to prompts.
- Recognizes phase transitions through converging signals without requiring the human to declare them
- Maintains structural awareness in the background (R6 from scope: rails are for the AI)
- Follows the Claude Code interaction model: conversational, terminal-driven, augmented with visuals

The human works fluidly. The AI maintains the backbone. Proactivity is governed by the 3-mode dial — at gate: AI proposes, human decides. At flag: AI acts, human is notified. At skip: AI acts silently.

### Background sub-agent

Proactive behavior — especially continuous challenging, confidence checking, and staleness detection — requires a background sub-agent. The sub-agent:

- Observes the conversation in real time without interrupting
- Runs evaluation processes in parallel (counterfactuals, confidence checks, drift detection)
- Surfaces findings through the flag mechanism (human notified, not blocked)
- Maintains the structural model (what's fixed vs transitory, where the macro phase is)

The sub-agent is the mechanism for CR6. Without it, proactivity depends on the main conversation thread remembering to self-check — which we proved doesn't work (Session 5: we forgot to track the phase transition we were theorizing about).

### Knobs

The human must have configurable controls over AI behavior — not just conversational steering, but persistent parameters:

- How proactive should the AI be? (frequency of unsolicited observations)
- How aggressively should it challenge? (threshold for running counterfactuals)
- What confidence level triggers escalation? (skip → flag → gate)
- Which processes should the sub-agent run automatically vs on demand?

Knobs are a control surface distinct from the 3-mode dial. The dial governs human involvement per decision. Knobs govern AI behavior parameters across decisions. Both are needed.

---

## CR7: Phase transitions are recognized, not enforced

The system must:

- Not enforce a linear phase sequence
- Recognize transitions through converging signals:
  - **Artifact-based** — a crystallized output indicates phase readiness
  - **Confidence-based** — sufficient items reach sufficient confidence
  - **Behavioral** — the nature of questions and work shifts
  - **Decided** — the human explicitly declares a transition
  - **Emergent** — recognized after the fact
- Track the macro phase (project center of gravity) while allowing granular non-linearity
- Support looping back to earlier phases without treating it as failure

The AI does the recognizing (CR6). The human can override at any time.

---

## Not yet addressed

- **The pipeline** — the specific path through this space (goal → decompose → Q&A → decide → plan → build → verify). This is the product's core flow. We went deep into the structural model (what the system is made of) but haven't yet defined how things flow through it. Next layer of requirements.

---

## How these compose

The core requirements define a composition model:

```
Phase (7) × Things (7) × Verbs (4) × Processes (4 universal + 4 phase-associated) × Lenses (5 cross-cutting)
```

This is a requirements framework that constrains the design space. Not every combination is equally important. Specific features are prioritized slices through this space. The space itself is the structural requirement.
