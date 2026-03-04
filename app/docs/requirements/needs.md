# What We Need

**Date:** 2026-02-11
**Parent:** [Requirements](README.md)
**Status:** Foundation — feeds [Core Requirements](core-requirements.md)

---

## Four verbs, one noun

Everything reduces to:

- **See** — visibility into the state of things (the read side)
- **Change** — create, modify, connect, evolve things (the write side)
- **Evaluate** — challenge, pressure test, update confidence (the reasoning side)
- **Execute** — direct agents, assign work, monitor progress, collect results (the doing side)
- **What** — the things being seen, changed, evaluated, and executed

"See where we are" is a cross-cutting need that applies to everything — but it's one facet of See. "Change" is equally fundamental — we don't just observe, we create and evolve. "Evaluate" is the reasoning verb — deliberately testing claims to update certainty. "Execute" is the action verb — Compose doesn't do the work itself, it directs agents who do.

All four verbs force the question: see WHAT? Change WHAT? Evaluate WHAT? Execute WHAT? Which defines the things.

---

## See

What does "see" mean in practice?

1. **See the structure** — things exist and they're connected. Those connections are the thinking. Show them.
2. **See the state** — what's done, what's open, what's shaky. At a glance, not by reading.
3. **See by meaning** — "what connects to this decision" is the real question, not "what's in this folder."
4. **See it live** — the picture must keep up with the conversation. The AI writes files; the visuals reflect it.
5. **See what the AI sees** — the AI can point at things visually, not just as file paths in the terminal.

---

## Change

What does "change" mean in practice?

1. **Create things** — new documents, new decisions, new connections. From the terminal or the visual layer.
2. **Evolve things** — refine status, update confidence, revise content. Things aren't static.
3. **Connect things** — link a decision to the spec it informed. Link a brainstorm to the feature it became. Relationships are first-class.
4. **Synthesize things** — distill many sources into one output. The one-pager workflow: select sources, produce a new thing.
5. **Mark things** — what's solid vs what's in flux. What's superseded. What needs attention.

---

## Evaluate

What does "evaluate" mean in practice?

1. **Challenge claims** — run counterfactuals, generate counter-evidence, test whether something holds under pressure.
2. **Update confidence** — the output of evaluation is a revised confidence level. Up or down.
3. **Detect staleness** — things that were true may no longer be. Evaluation surfaces what needs revisiting.
4. **Compare alternatives** — weigh options against each other. Not just "is this right?" but "is this better than that?"
5. **Crystallize or kill** — evaluation resolves into commitment (crystallize) or rejection (kill/supersede). It's the mechanism that moves items from tentative to fixed.

---

## What (the ontology)

Four concepts. Everything in Compose is made of these.

### Items

The outputs. An item is any discrete piece of knowledge work — an idea, a decision, a question, a gap, a thread, an artifact, an evaluation. All the same fundamental thing with different labels.

An item has:
- Identity (a name)
- Content (the substance)
- A type (what kind of thing it is)
- State (see below)
- Connections (see below)

Types observed so far: idea, decision, question, gap, thread, artifact, evaluation, spec, brainstorm. Extensible — types are labels, not schema.

### Processes

The activities. A process produces, changes, or evaluates items. Discovery is a process. Evaluation is a process. Synthesis is a process. A phase transition is a process.

A process has:
- Identity (a name, a type)
- Inputs and outputs (items go in, items come out)
- State (active, converging, stalled, completed — changing over time)
- A trace (what happened during the process — the meta-trace is an example)
- Duration (when it started, when it changed, when it ended)

The four verbs (see, change, evaluate, execute) apply to processes too. You can see a process in progress, change its direction, evaluate whether it's converging, execute it through agents.

Types observed so far: discovery, evaluation, synthesis, decomposition, phase transition. Extensible.

### Connections

The relationships between things — items, processes, or both. Connections ARE the knowledge structure.

Types observed so far:
- **Parent/child** — hierarchy. A feature contains tasks. A brainstorm contains insights. May be structurally special (scope, inheritance, navigation) — open question from CF7.
- **Informs** — a decision informs a spec. A brainstorm produces questions. The deliberation relationship.
- **Blocks** — can't proceed on X until Y is resolved.
- **Supersedes** — new replaces old. Captures evolution. Implies temporal ordering — needs timestamps (CF6).
- **References** — looser than informs. "See also." No dependency implied.
- **Produces** — a process produces items as outputs.
- **Consumes** — a process takes items as inputs.

### State

Dimensions that change over time. Apply to both items AND processes.

- **Status** — where it stands. Items: open, draft, tentative, crystallized, superseded. Processes: active, converging, stalled, completed.
- **Confidence** — how sure we are: untested, low, moderate, high. On items: how validated is this claim? On processes: how close to resolution?
- **Timestamps** — when created, when last changed. Required for supersedes, staleness detection, and temporal reasoning (CF6).

Fixed vs transitory may be derived from status + confidence rather than independent (CF5). Open question.

Phase (vision, requirements, design...) may be context rather than state — where in the lifecycle something was created or lives. Open question.

---

### Ontology note

The ontology (items, processes, connections, state) is **design, not requirements**. It emerged during requirements work but it describes how to represent things internally. The requirements-level WHAT is the list of things users work with (ideas, decisions, questions, tasks, relationships, state). How those are modeled is a design decision. The ontology is parked as a design thread. See [Ontology Counterfactuals](ontology-counterfactuals.md) for pressure testing.

---

## The things users work with (requirements-level WHAT)

At every phase, the user works with:

1. **What they're thinking about** — ideas, brainstorms, explorations
2. **What they've decided** — committed positions, rationale, rejected alternatives
3. **What they need to figure out** — open questions, gaps, unknowns
4. **What they need to do** — tasks, plans, specs
5. **How those things relate** — this decision shaped that spec, this question blocks that task
6. **Where each thing stands** — how done, how sure, what needs attention
7. **What's been produced** — outputs, artifacts, deliverables (code, docs, designs, test results, deployed services)

These are the same at every phase. The phase is the context, not the content.

---

## Lenses on the system

Nine orthogonal lenses. Each shows a different dimension of the same work.

| Lens | What it shows | Orthogonal? |
|------|-------------|------|
| **Phase** | Where in lifecycle (vision → requirements → design → planning → implementation → verification → release) | The levels themselves |
| **Thing** | What kind (idea, decision, question, task, relationship, state) | Yes — exists at every phase |
| **Verb** | What you're doing (see, change, evaluate, execute) | Yes |
| **Process** | What activity (discovery, evaluation, synthesis, decomposition) | Mostly — see below |
| **Confidence** | How sure (untested → high) | Yes |
| **Scope** | Granularity (project → feature → task → subtask) | Yes |
| **Actor** | Who (human, AI agent, background sub-agent) | Yes |
| **Time** | When (created, changed, superseded) | Yes |
| **Governance** | 3-mode dial (gate, flag, skip) | Yes |

---

## Processes: universal vs phase-associated

**Universal processes** (happen everywhere):
- Discovery (Q&A decomposition)
- Evaluation (pressure testing, counterfactuals)
- Synthesis (distilling many → one)
- Capture (recording knowledge)

**Phase-associated processes** (stronger affinity but not exclusive):
- Decomposition → planning (but you decompose during design too)
- Building → implementation (but you prototype during vision)
- Testing → verification (but you test ideas during discovery)
- Deploying → release (hardest to decouple)

Even the phase-associated processes leak. You test during vision. You build prototypes during discovery. The association is statistical, not structural.

---

## Phases are not a DAG

Phases can loop back to any other phase. The progression is:

- **Macro level:** roughly linear. The project's center of gravity moves forward through vision → requirements → design → planning → implementation → verification → release.
- **Granular level:** non-linear. Items jump between phases constantly. You work on multiple phases simultaneously. No deterministic path.

Like quantum mechanics: at the particle level it's probabilistic and non-linear. At the macro level, classical linearity emerges. Phase isn't a property of a specific item — it's a probability distribution of where activity is concentrated.

"We're in requirements" means most of the work is at the requirements level, not that nothing is happening at vision or design.

### How phase transitions happen

Transitions between phases are overdetermined — multiple signals converge:

- **Artifact-based** — a crystallized output signals readiness (the one-pager triggered vision → requirements)
- **Confidence-based** — enough items at the current phase reach sufficient confidence
- **Behavioral** — the human starts asking different kinds of questions ("what do we build?" instead of "what do we want?")
- **Decided** — the human explicitly says "let's move on"
- **Emergent** — it just happens, recognized after the fact

All five happened in our sessions. The criteria aren't exclusive — they co-occur. Processes are the transition mechanism: you *discover* your way from vision to requirements. The process IS the transition.

### What this means for Compose

Compose can't enforce a linear phase sequence. It needs to:
- Track the macro phase (where is the center of gravity?)
- Allow items to exist at any phase regardless of the macro phase
- Recognize transitions through signals, not declarations
- Support looping back without treating it as failure
