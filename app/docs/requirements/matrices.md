# Pipeline Matrices

**Date:** 2026-02-11
**Parent:** [Core Requirements](core-requirements.md)
**Status:** Vision row filled. Design row partial (from lived experience). Others to be defined as we go.
**Purpose:** Define the pipeline by filling in what happens at each crossing of the composition model. Phases are the dominant axis (first column).

---

## Matrix 1: Phases × Verbs

What do you see, change, evaluate, and execute at each phase?

| Phase | See | Change | Evaluate | Execute |
|---|---|---|---|---|
| **Vision** | See the emerging picture — ideas, connections, gaps, "where are we?" at a glance. The graph of knowledge. Status and confidence on everything. | Create ideas, capture decisions, connect concepts, synthesize into consolidated artifacts (one-pager, vision statement). | Pressure test claims (counterfactuals), update confidence dynamically via logic and discovery, crystallize or kill directions. | Research — web search, reference gathering. Prototyping/spiking if needed. Minimal. |
| **Requirements** | | | | |
| **Design** | See the design options, trade-offs, what's been decided vs open. See how design choices map to spec requirements. | Propose approaches, combine them, refine based on feedback. Define visual language, interaction models, layouts. | Pressure test approaches against constraints — does it scale? compose? delight? Reference survey as input. | Prototype, spike, reference survey, try things. Build rough versions to validate design choices. |
| **Planning** | | | | |
| **Implementation** | | | | |
| **Verification** | | | | |
| **Release** | | | | |


---

## Matrix 2: Phases × Things

What types of things dominate at each phase?

| Phase | Thinking about | Decided | Need to figure out | Need to do | Relationships | State | Produced |
|---|---|---|---|---|---|---|---|
| **Vision** | Ideas, directions, product concepts, brainstorms | Vision statement, product direction, what's in/out, kill decisions | Open questions, gaps in understanding, unknowns to explore | Threads to file, docs to write, counterfactuals to run | Concepts inform each other, ideas connect to decisions, gaps block crystallization | Tentative → crystallized (or killed). Confidence shifting dynamically based on evidence. | Vision docs, one-pager, feature map, brainstorm artifacts |
| **Requirements** | | | | | | | |
| **Design** | Approaches, patterns, trade-offs, reference examples | Architecture, visual language, interaction model, component choices. Rationale for each. | What to figure out: which approach works? How do components compose? What does delight look like? | Prototypes to build, spikes to run, references to survey | Spec items trace to design choices. Approaches compete until one wins. Rejected approaches inform. | Proposed → prototyped → validated (or rejected). Confidence via prototype feedback. | Specs (behavioral + visual), prototypes, component designs, interaction flows |
| **Planning** | | | | | | | |
| **Implementation** | | | | | | | |
| **Verification** | | | | | | | |
| **Release** | | | | | | | |

---

## Matrix 3: Phases × Processes

Which processes are active at each phase? (All universal processes apply everywhere; this captures intensity and phase-associated processes.)

| Phase | Discovery | Evaluation | Synthesis | Capture | Decomposition | Building | Testing | Deploying |
|---|---|---|---|---|---|---|---|---|
| **Vision** | Dominant — exploring the space, Q&A, brainstorming | High — counterfactuals, confidence checks, pressure testing. Background sub-agent runs these continuously. | High — distilling scattered ideas into consolidated docs | Continuous — recording decisions, rationale, rejected alternatives | Light — breaking big concepts into sub-topics, not executable tasks | Minimal — maybe a prototype or spike | Minimal — testing ideas conceptually, not code | None |
| **Requirements** | | | | | | | | |
| **Design** | High — exploring approaches, surveying references, asking "how should this work?" | High — evaluating approaches against constraints, pressure testing design choices | High — combining reference patterns into coherent design, distilling options into decisions | Continuous — recording design rationale, rejected approaches, why | Moderate — breaking spec into designable components | Moderate — prototypes and spikes to validate | Light — testing prototypes against spec criteria | None |
| **Planning** | | | | | | | | |
| **Implementation** | | | | | | | | |
| **Verification** | | | | | | | | |
| **Release** | | | | | | | | |

---

## Matrix 4: Phases × Lenses

Which lenses are most relevant at each phase?

| Phase | Confidence | Governance | Scope | Actor | Time |
|---|---|---|---|---|---|
| **Vision** | Central — dynamic, driven by logic and discovery via search. Evidence updates confidence continuously, not just at checkpoints. | Mostly gate/flag — human steers heavily, AI proposes. AI should be proactive about challenges and counterfactuals, subject to human knobs. Knobs control: challenge aggressiveness, proactivity frequency, escalation thresholds. | Project-level and feature-level. Not task-level yet. | Human-AI pair. Human steers, AI expands AND challenges. Background sub-agent evaluates continuously. | When ideas emerged, when they changed. Evolution trail matters for tracking how thinking developed. |
| **Requirements** | | | | | |
| **Design** | Growing — design choices gain confidence through prototyping and evaluation. Less dynamic than Vision, more binary (this approach works or it doesn't). | Mixed gate/flag — human decides on approach, AI proposes options and generates alternatives. AI useful for reference surveys and trade-off analysis. | Component-level and interaction-level. Breaking spec requirements into designable pieces. | Human-AI pair. AI generates options, surveys references, proposes. Human selects, steers aesthetics and feel. | When approaches were proposed, evaluated, selected. Which came first matters for understanding design evolution. |
| **Planning** | | | | | |
| **Implementation** | | | | | |
| **Verification** | | | | | |
| **Release** | | | | | |

---

## How to use these

The pipeline is the path that lights up across these grids. Not every cell is equally important. The active cells define the core flow. Filling these in turns the abstract composition model into a concrete pipeline definition.

Phase affinity (which cells are "hot" vs "warm" vs "cool") is LLM guidance context — it tells the AI what to expect and propose at each phase. The system doesn't behave differently per cell, but the AI's reasoning should.

### From matrices to building

The Vision row is the first buildable slice — we have lived data for it. Each additional row adds requirements for the next slice.
