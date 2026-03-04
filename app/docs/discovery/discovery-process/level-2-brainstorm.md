# Discovery Level 2: Fleshing Out the Dimensions

**Date:** 2026-02-11
**Phase:** Discovery (active)
**Parent:** [Discovery Process](README.md)
**Depends on:** Level 1 resolution — 3 working dimensions (What, How, Why-factual) + knowledge layer

---

## What is this?

Level 1 defined the high-level constructs: three working dimensions (What, How, Why-factual), a knowledge layer underneath, and onboarding inputs (personal why, who, starting conditions).

Level 2 goes one layer deeper: how do these dimensions manifest mechanically in Forge? What does the user touch? What does the AI reason about? How do the dimensions connect to the existing primitives (Work, Policy, Session)?

---

## Cluster 1: What does "What" actually look like?

The Work primitive already exists in the design. But the dimension framing raises questions the original design didn't ask.

**Key questions:**
- Is "What" just the Work item itself (title, status, hierarchy, artifacts)? Or is there more to it?
- How does What's *shape* change across lifecycle phases? A brainstorm-phase What is loose prose. An implementation-phase What is a structured task with acceptance criteria. Same primitive, different surface.
- The crystallization model says structure hardens as you go down the lifecycle. What mechanically hardens? Fields becoming required? Artifact types narrowing? Something else?
- What is the relationship between What and hierarchy? Is hierarchy a property of What, or a separate structural concept?

**What we've written down (tentative — not validated through use):**
- Work = a node in a tree: identity, status, children, dependencies, artifacts, evidence, acceptance criteria, scope
- Status lifecycle: planned → ready → in_progress → review → complete (+ blocked, parked)
- Everything is the same node shape — brainstorms, decisions, specs, tasks
- Labels (phase + type) differentiate kinds of work

The Work primitive *looks* well-defined on paper. But we haven't built anything against it or tracked real work with it. The definition may have gaps, redundancies, or wrong assumptions we can't see yet.

**What we don't know:**
- Whether the Work primitive actually covers the "What" dimension, or whether real use reveals missing pieces
- How crystallization works mechanically — is it just convention, or does the system enforce/guide it?
- Whether the node shape is right — do all those fields pull their weight, or are some theoretical?

---

## Cluster 2: What does "How" actually look like?

How was elevated late in Level 1 and hasn't been designed at all. It covers approach, method, constraints — and is where Forge tailors itself to the user's actual work.

**Key questions:**
- Is How a property of a Work item? A separate entity? A label? A template selection?
- How relates to approach, method, constraints. Are constraints just How, or are they their own thing?
- How is where Forge *tailors* — a React project gets React patterns. What's the tailoring mechanism?
- How overlaps with Policies (gate/flag/skip are *how* decisions get made). Is the 3-mode dial part of How, or is it orthogonal?
- When a user picks an approach (e.g., "we'll use markdown-in-folders for persistence"), where does that live? On the Work item? As a decision Work item that `informs` the implementation?

**What we already know:**
- Policies exist: 3-mode dial (gate/flag/skip) attached to decision points, inheriting downward
- Templates exist in the design: type-specific defaults (decision template, brainstorm template, etc.)
- Variants (from taxonomy) differ by phase — defaults for acceptance criteria, artifact types, etc.

**What we don't know:**
- Whether How is Policy, or broader than Policy
- Whether approach/method decisions are tracked as How-metadata on Work items, or as separate decision-type Work items
- What tailoring means concretely — project-level config? Work-item-level? Both?

---

## Cluster 3: What does "Why-factual" actually look like?

The biggest unknown. Level 1 defined it as "knowledge reasoning, evidence chains, traceable justification." But the mechanics are wide open.

**Key questions:**
- Is it the `informs` dependency? (A decision informs a spec = the why chain)
- Is it artifact versioning? (The old spec vs. the new spec = the why of the change)
- Is it explicit assumption tracking? ("This design assumes X. If X changes, these items are stale.")
- Is it all three? Something else entirely?
- When the user asks "why is it this way?" — where does the answer come from mechanically?
- How much is explicit (user/agent writes it down) vs. implicit (derived from the graph of relationships)?

**What we already know:**
- `informs` dependency type exists in the design — connects thinking to doing
- Artifacts capture rationale (decision records have: question, context, decision, rationale, alternatives)
- Loopback carries evidence (what triggered it, what the previous state was, what goes stale)
- The crystallization model implies Why is captured at transition points

**What we don't know:**
- Whether Why-factual needs its own data structure or emerges from existing constructs
- Whether assumption tracking is a first-class feature or just good artifact hygiene
- How the AI identifies when a Why chain is broken or stale

---

## Cluster 4: The knowledge layer — what is the AI actually doing?

Level 1 said there's a knowledge layer underneath the working surface. The AI uses who/what/how/why as reasoning facets, tracks evidence and assumptions, and surfaces insights when reasoning breaks down or context changes.

**Key questions:**
- What *triggers* the AI to surface something? (Stale assumption? Conflicting decisions? Missing evidence? Phase transition?)
- What does the AI have access to? (All artifacts? The graph of `informs` links? Session transcripts? Git history?)
- Is this a passive index (AI answers when asked) or an active monitor (AI flags proactively)?
- How does this connect to the 3-mode dial? (Gate = AI can't act without asking. Flag = AI acts and notifies. Skip = AI acts silently.)
- Is the knowledge layer persistent state, or something that exists only during sessions?
- What's the minimum viable version of this? What's the simplest thing that would be useful?

**What we already know:**
- Agent monitoring (Phase 0.5) pattern-matches PTY output — that's surface-level observability
- Session context (handoff docs) already captures "what the AI knows" in a crude way
- The `informs` graph is a knowledge structure — it encodes reasoning relationships
- Conversation distillation (Phase 3.2) extracts structured outcomes from transcripts

**What we don't know:**
- Whether the knowledge layer is a feature we build or an emergent property of good data structures
- What the AI needs to be useful vs. what's aspirational
- How much of this is "Claude Code is smart and has context" vs. "Forge provides structured knowledge the AI couldn't derive alone"

---

## Cluster 5: How do the dimensions connect to existing primitives?

Work, Policy, Session are already defined as the three core primitives. The dimensions need to map.

**Key questions:**
- **What ↔ Work** — seems direct. But is What literally the Work primitive, or is Work the *container* that holds What + How + Why?
- **How ↔ Policy?** — Policies govern *how* decisions are made (gate/flag/skip). Is How broader than Policy, or does Policy cover all of How?
- **Why-factual ↔ ???** — There's no existing primitive for this. Is it a new primitive? Or does it emerge from the relationship between existing ones (artifacts, `informs` deps, session transcripts)?
- **Knowledge layer ↔ Session?** — The AI reasons during sessions. Is the knowledge layer just what happens during sessions, or is it persistent state that outlives any session?
- Do the dimensions *replace* the primitives, *refine* them, or *layer on top* of them?

**What we already know:**
- Three primitives: Work (structure, state, evidence), Policy (trigger, mode, criteria), Session (actor, assignment, context)
- Core axiom: every decision point is a 3-mode dial
- Everything derives from these three

**What we don't know:**
- Whether the dimension model changes the primitive model, or just describes a different facet of it
- Whether we need a 4th primitive (Knowledge? Evidence? Reasoning?) or whether the existing three are sufficient

---

## Interaction surface analysis (Session 6)

Approached Clusters 2-5 from the user's perspective: what does the user actually touch?

### Primitives split into two interaction patterns

- **Objects you manipulate** — Work items (create, edit, navigate, connect), Policies (set dials, configure)
- **Processes you participate in** — Discovery (enter a mode, ask questions, decompose), Sessions (start, direct, end)

### Dimensions are facets of one interaction, not separate surfaces

When a user touches a Work item, all three dimensions are present:
- **What** — the item itself. Name, status, children, artifacts.
- **How** — the configuration around it. Policies, templates, approach.
- **Why** — the reasoning behind it. What informs it, what decisions led here, what evidence supports it.

One object, three lenses. This validates the Level 1 framing.

### Clusters 2-4 are layers, not independent gaps

From the interaction surface:
- **How (Cluster 2)** = Policy + templates + adaptation. Already partially designed. The gap is: how does the user *experience* it?
- **Why-factual (Cluster 3)** = `informs` graph + decision records + evidence. Data structures exist. The gap is: how does the AI *assemble and present* a Why answer?
- **Knowledge layer (Cluster 4)** = the engine that powers Why queries. Not a user surface — it's infrastructure. The gap is: what does it need to *index*, and when does it surface things proactively vs. on demand?

These are three layers of the same thing: configuration (How) → queryable knowledge (Why) → indexing engine (Knowledge layer).

### The Knowledge layer isn't a fourth lens

What and How can be shown from the data model alone. Why requires computation — tracing connections, reconstructing reasoning chains, identifying staleness. The Knowledge layer is what makes the Why lens *work*. It's infrastructure, not a dimension.

**Confidence:** Low-moderate. This analysis is inferred from the model, not tested against real interaction. Counterfactuals needed.

---

## How these clusters relate

They're tangled. Answering one informs the others:

```
Cluster 1 (What) ←→ Cluster 5 (primitives mapping)
    ↕                       ↕
Cluster 2 (How)  ←→ Cluster 3 (Why-factual)
    ↕                       ↕
         Cluster 4 (knowledge layer)
```

- Cluster 5 is the integration point — it connects everything back to the existing design
- Cluster 4 is the most abstract and depends on 1-3 being clearer
- Clusters 1-3 can be explored somewhat independently but will cross-reference each other

---

## Where to start?

Suggested order (concrete → abstract):
1. **Cluster 1 (What)** — most concrete, closest to existing design, grounds the discussion
2. **Cluster 2 (How)** — next most concrete, has the Policy overlap question
3. **Cluster 3 (Why-factual)** — the big unknown, but informed by 1 and 2
4. **Cluster 5 (primitives mapping)** — integration, needs 1-3 to be clearer
5. **Cluster 4 (knowledge layer)** — most abstract, depends on everything else

Or go wherever the conversation pulls.

---

---

## Insights surfaced during Level 2

- [False Crystallization](false-crystallization.md) — Structure ≠ confidence. Writing a definition down doesn't validate it. Forge needs a concept of **validation pressure** to distinguish tested from untested crystallization.
- [Confidence Model](confidence-model.md) — Qualitative Bayesian: prior (how it was created) + evidence updates (challenges, research, prototypes, failures) = posterior (current confidence). Rolls up from children. Orthogonal to status, applies everywhere.
- [Discovery Modes](discovery-modes.md) — Discovery has three modes: conversational brainstorming, external knowledge discovery, and integration. They interleave, not sequential. Each contributes to confidence differently.
- [Discovery Verbs](discovery-verbs.md) — The micro-moves within discovery modes (orient, steer, gather, challenge, etc.). Not useful to surface to the user — but the AI can use them to read the room and be a better partner. Intuited, not validated.
- [Use Case Matrix](use-case-matrix.md) — Canonical use cases across personas. P1 + P2 are ICPs (modes, not people). Living matrix.
- [Use Case Walkthrough](use-case-walkthrough.md) — All 15 ICP use cases tested against the model. 7 recurring gaps identified.
- [Feature Map](feature-map.md) — 8 features, dependency map, gaps in feature context.
- [Model Gaps](model-gaps.md) — The 7 gaps with options, considerations, and triage. Now contextualized in features.
- [Discovery as Primitive](discovery-as-primitive.md) — Discovery isn't Work. It's the process that produces Work. 4th primitive alongside Work, Policy, Session. **Updated:** Discovery operates at every phase boundary — the connective tissue between levels of concreteness, not just a first phase.
- [Crystallization Review](crystallization-review.md) — Honest 3-pass assessment of session 5 end-state. What's solid, what's untested, what's fragile.
- [Session 5 Meta-Trace](session-5-meta-trace.md) — The process of this session itself, recorded as test data for how discovery works. Living doc.
- [Onboarding Inputs](onboarding-inputs.md) — Collection point for things Forge needs to ask/know to calibrate itself. First candidate: structured vs. free-flow preference for discovery.
- [Counterfactuals: Session 6](counterfactuals-session-6.md) — 6 counterfactuals against the interaction surface analysis. 4+ landed. Model is less clean, more honest.
- [Confidence Evaluation Process](confidence-evaluation-process.md) — How confidence scoring works in practice: the evaluation pattern, triggers/timing, process inference. First real use of the confidence model on itself.
- [Vision Statement](vision-statement.md) — "Build me X" → Forge handles the rest. The structured implementation pipeline is the core product. Discovery is an optional on-ramp. What/How/Why/Confidence are reasoning infrastructure.
- [Rails Architecture](rails-architecture.md) — The core design question: how to keep AI implementation on track. Human process patterns + Claude Code patterns (CLAUDE.md, rules, skills, hooks, memory) → toward enforcement at every pipeline step.

---

*This is a Level 2 discovery artifact. It maps the territory to be explored, not the conclusions.*
