# Feature Map: What Compose Does

**Date:** 2026-02-11
**Parent:** [Level 2 Brainstorm](level-2-brainstorm.md)
**Status:** Draft — high-level feature definitions, not specs

---

## Purpose

This maps what Compose does for the user at a high level. Constructs (primitives, dimensions, confidence, modes) are the internals. Features are what the user experiences. Gaps belong in feature context, not floating.

## Vision alignment

See [Vision Statement](vision-statement.md). The core product is the **structured implementation pipeline**: goal → decomposition → Q&A → decisions → design → plan → build. Features F3, F4, and F5 ARE the pipeline. F1 (Discover) is an optional on-ramp for when the goal is fuzzy. F2 and F6 support the pipeline.

| Feature | Role in vision | Priority |
|---------|---------------|----------|
| **F0: Context** | Core pipeline — gather what Compose needs to reason | **Core** |
| **F4: Plan & Decompose** | Core pipeline — decomposes goal into executable work | **Core** |
| **F5: Execute with Agents** | Core pipeline — agents build what was planned | **Core** |
| **F3: Distill & Decide** | Core pipeline — convergence engine, decision points | **Core** |
| **F6: See Everything** | Pipeline support — visibility into pipeline state | **Core support** |
| **F2: Capture Knowledge** | Pipeline support — preserves reasoning for context | **Core support** |
| **F1: Discover** | Optional on-ramp — explore when goal is fuzzy | **On-ramp** |

The pipeline features (F0, F3, F4, F5) have the least design attention and need the most. F1 has had the most attention (because it's the hardest, most ambiguous feature) but serves the smallest slice of user needs.

## Primitives (expanded)

Previously 3, now 4. See [Discovery as Primitive](discovery-as-primitive.md).

| Primitive | Role |
|-----------|------|
| **Discovery** | The process that produces Work — questions, modes, evidence, process trace |
| **Work** | The outputs — things to track and do |
| **Policy** | Constraints on decisions — gate/flag/skip |
| **Session** | Actors doing the work — human or AI, context |

## Cross-cutting capabilities

These apply to ALL primitives and ALL features, not owned by any single one:

| Capability | What it does | Applies to | Confidence |
|-----------|-------------|------------|------------|
| **Tracking** | State, status, lifecycle | Discovery (open/converging/closed), Work (status lifecycle), Session (active/done), Policy (current mode) | Moderate |
| **Confidence** | Bayesian prior + evidence → posterior, rolls up | Discovery (how tested are outputs?), Work (how validated?), anything with children | Low-moderate (used once) |
| **Visibility** | See state at a glance — dashboards, views | Everything — the read layer (F6) | Moderate |
| **Knowledge capture & linking** | Every pipeline step produces knowledge (decisions, rationale, approaches tried/rejected). Capture automatically, link into the graph so F0 can retrieve it next time. | All features — pipeline produces knowledge as byproduct of running | Low (identified, not designed) |
| **3-mode dial** | Gate/flag/skip governs every decision point | All features, all primitives — the universal governance mechanism | Moderate |
| **Persistence** | How/where things are stored. Connector-based — core doesn't care about backend (graph DB, vector store, markdown files) | Everything that needs to survive across sessions | Low (connector architecture exists, no implementation) |
| **Audit/history** | What changed, when, why. Temporal trail. Evidence needs timestamps. | All primitives — supports staleness detection, context recovery, Why queries | Tentative (surfaced from CF6, not yet designed) |
| **Permissions/scope** | Who can see/do what. Matters for team use. | All features | Tentative (may not be needed for solo v1) |

Tracking is not a feature. It's a property of every primitive. Features are what the user *does*. Cross-cutting capabilities are what the *system* does across all features.

**Background sub-agent thread:** Meta-tracking, confidence evaluation, and knowledge capture may need a background sub-agent that observes the conversation and acts transparently — without interrupting flow. See [Rails Architecture: Background sub-agent](rails-architecture.md#background-sub-agent-for-meta-tracking). This is cross-cutting across all capabilities and all features.

### Knowledge management note

Everything is based on context (F0). Context implies knowledge management. Knowledge base, knowledge graph — these are storage/retrieval backends. They're connectors: the core needs "give me relevant context for this prompt," the connector decides how to store and retrieve it. The bigger question is the capture mechanism: how does knowledge get captured and linked *as the pipeline runs*, without requiring manual effort? This connects to F2 (Capture Knowledge), F3 (Distill & Decide), and Gap 3 (extraction mechanism). Governed by the 3-mode dial: gate (user captures manually), flag (AI proposes, user approves), skip (AI captures automatically).

---

## Features (what the user does)

### F0: Context

**What it does:** Gather what Compose needs before it can decompose. The front door of every pipeline run. Scales from zero (greenfield) to deep (resume, refactor).

**Autonomous** (Compose gathers itself):
- Code context: codebase structure, tech stack, patterns, conventions. Read the code.

**Opportunistic** (use if available, work without it):
- Project context: prior decisions, directions, history. Available if Compose has been used before.
- Work context: pipeline state, what's in progress/blocked/done. Available if Compose is tracking work.
- Problem context beyond the prompt: richer intent. Available if the user elaborates.

The pipeline works with just the prompt + code. Everything else makes it better. First use is weakest. Tenth use has accumulated reasoning. This is the persistence payoff — a bonus, not a gate.

**Primitives used:** All (reads from everything that exists)

**Constructs used:** Knowledge layer (retrieval + filtering + summarization), persistence

**Use cases served:** UC-1 (orientation), UC-7 (context recovery), UC-12 (onboarding to existing project)

**Entry point scaling:**

| Entry point | Code | Project | Work | Depth |
|---|---|---|---|---|
| Build me X (greenfield) | No | No | No | Zero |
| Build me X (existing) | Yes | Yes | Maybe | Moderate |
| Fix this bug | Yes (deep) | Maybe | No | Moderate |
| Add Y to Z | Yes (Z) | Maybe | No | Moderate |
| Refactor this | Yes (deep) | Yes | No | Deep |
| Continue where I left off | Yes | Yes | Yes | Full |

**Open questions:**
- How does F0 know what's *relevant*? All context isn't useful context. Retrieval + filtering + summarization — what's the mechanism?
- F0 reads. But who writes? Knowledge capture (cross-cutting) feeds F0. If capture doesn't happen, F0 has nothing to read on the next run.

**Resolved:**
- Retrieval backend is a connector. F0 defines the interface ("give me relevant context for this step + this prompt"). The backend is the user's choice. Floor: markdown files + Claude Code patterns (proven, zero infrastructure). Ceiling: vector store, knowledge graph, semantic search. Connector architecture lets users swap without changing core. Most solo devs stay at the floor.

---

### F1: Discover

**What it does:** Explore questions, brainstorm, research, prototype, integrate findings. Four modes with different AI behaviors. Structure when wanted, free-flow when not. Produces Work items as outputs.

**Primitives used:** Discovery (primary), Session, Policy (structured vs free-flow preference)

**Constructs used:** Discovery modes (brainstorm, research, prototype, integration), discovery verbs (AI-internal), onboarding (structured vs free-flow preference), process trace

**Use cases served:** UC-6 (planning loop), UC-9 (multi-topic session), UC-10 (new idea), UC-11 (research), UC-15 (prototyping)

**Known gaps:**
- Phase transition triggers (Gap 5) — when is discovery "done"?
- Direction as concept (Gap 6) — what are we exploring, and when do we stop?

---

### F2: Capture Knowledge

**What it does:** Record the Why behind work. Decisions with rationale, rejected alternatives, evidence trails. Artifacts attached to Work items. `informs` dependencies connecting thinking to doing. Bridge between Discovery and Work — what was learned gets attached to what was decided.

**Primitives used:** Work (artifacts, evidence), Discovery (outputs)

**Constructs used:** Why-factual dimension, `informs` dependency, artifacts, evidence

**Use cases served:** UC-8 (deliberation), UC-12 (onboarding), UC-18 (spec from discovery)

**Known gaps:**
- Evidence granularity (Gap 4) — per-item, per-artifact, or per-claim?
- Distillation (Gap 3) — most knowledge lives in conversations, not yet captured

---

### F3: Distill & Decide

**What it does:** The convergence engine. Not just extraction — the full arc from raw conversation to committed decisions.

1. **Extract** — pull structured items from conversation (insights, questions, options, action items)
2. **Assess** — weigh evidence, sort confidence, flag conflicts and gaps
3. **Decide** — crystallize into a committed position, a kill decision, or an explicit "not enough evidence yet"

Decisions are the output of distillation. A decision is what happens when you distill enough evidence into a committed position. Kill decisions are what happens when you distill enough counter-evidence.

Bridges Discovery → Work. The outputs become Work items: decisions with rationale, specs, tasks, direction changes.

**Primitives used:** Discovery (process trace, evidence), Session (transcripts), Work (outputs), Policy (gate/flag/skip on decisions)

**Constructs used:** AI extraction, confidence assessment, human review (flag mode), meta-trace, `informs` dependencies

**Use cases served:** UC-8 (deliberation and decisions), UC-9 (session review), UC-10 (idea → go/kill), UC-12 (accumulated knowledge), UC-14 (pivot decisions)

**Known gaps:**
- Extraction mechanism (Gap 3) — real-time vs post-session vs human-triggered
- Kill/pivot mechanics (Gap 2) — how a decision to kill manifests
- Phase transition triggers (Gap 5) — when has enough been distilled to move on?

---

### F4: Plan & Decompose

**What it does:** Break high-level goals into executable pieces. AI-proposed decomposition. Dependency graphs. Sequencing. Crystallize discovery outputs into actionable work.

**Primitives used:** Work (hierarchy, dependencies), Policy (decomposition gate)

**Constructs used:** How dimension, dependency types (blocks, informs), hierarchy

**Use cases served:** UC-4 (decomposition), UC-5 (cross-project), UC-18 (spec from discovery)

**Known gaps:**
- Phase transition triggers (Gap 5) — when to move from planning to implementation?
- Priority (Gap 1) — what matters most among unblocked items?

---

### F5: Execute with Agents

**What it does:** Embed Claude Code. Assign work to sessions. Provide context briefings. Monitor what agents are doing. Enforce guardrails.

**Primitives used:** Session (primary), Work (assignment), Policy (scope, gates)

**Constructs used:** Scope boundaries, acceptance criteria, agent monitoring

**Use cases served:** UC-2 (session assignment), UC-3 (guardrails), UC-7 (context recovery)

**Known gaps:**
- Distillation (Gap 3) — agent sessions produce transcripts, need extraction

---

### F6: See Everything

**What it does:** See the state of all primitives at a glance. Status, hierarchy, dependencies, confidence heat map, what changed. Multiple views: tree, board, graph. The read layer over everything.

**Primitives used:** All

**Constructs used:** Tracking (cross-cutting), Confidence (cross-cutting), all dimensions

**Use cases served:** UC-1 (orientation), UC-5 (cross-project), UC-13 (stakeholder reports)

**Known gaps:**
- How to visualize confidence (color? sparkline? distribution?)
- How to visualize kill/pivot decisions (Gap 2 lives in F3, but F6 needs to show the result)

---

## Feature flow

### The pipeline (core)

```
Any prompt ("Build me X", "Fix this", "Continue where I left off")
    ↓
F0 Context — gather what's needed (scales from zero to full)
    ↓
F4 Plan & Decompose — decompose goal, Q&A to fill gaps, sequence
    ↓
F3 Distill & Decide — resolve decision points along the way
    ↓
F5 Execute with Agents — agents build what was planned
    ↓
(loop: questions arise → F3 decides or escalates → F5 continues)
```

Variable entry points slot into the pipeline at different depths. "Build me X" runs the full pipeline. "Fix this bug" enters at context with diagnosis. "Continue where I left off" enters at context with state recovery.

### The on-ramp (optional)

```
"I have a fuzzy idea"
    ↓
F1 Discover — explore, brainstorm, converge
    ↓
F3 Distill & Decide — crystallize into a goal
    ↓
→ enters the pipeline at F0
```

### Support (always on)

```
F2 Capture Knowledge — records why decisions were made, evidence, rationale
F6 See Everything — visibility into pipeline state, confidence, status
```

The pipeline IS the product. F0 is the front door — every entry point passes through it. Discovery is how you get to a goal when you don't have one. F2 and F6 make the pipeline transparent and recoverable. F0 gets better over time as Compose accumulates project context.

---

## Gaps in feature context

| Gap | Lives in | Impact |
|-----|----------|--------|
| 1. Priority | F4 (Plan & Decompose), F6 (See Everything) | Medium — workaround exists |
| 2. Kill/pivot | F3 (Distill & Decide) | High — P2 core workflow |
| 3. Extraction mechanism | F3 (Distill & Decide) | High — can phase |
| 4. Evidence granularity | F2 (Capture Knowledge) | Low for v1 |
| 5. Phase transitions | F1 (Discover), F3 (Distill) | High — crystallization model |
| 6. Direction | F1 (Discover) | Medium — may be solved already |
| 7. Prototype vs impl | F1 (Discover), F5 (Execute) | Low — label + phase |
