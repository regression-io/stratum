# Ontology Validation Against Use Cases

> Validates that the 7 entity types and 8 edge types from `2026-02-13-product-realignment.md` can represent every scenario the product must support.

**Ontology under test:**
- Entity types: Initiative, Feature, Task, Idea, Thread, Decision, Question
- Edge types: blocks, sequencing, informs, implements, belongs_to, produces, questions, resolves

---

## Use Cases

### UC-1: Where are we? (returning after a break)

Developer opens Forge after being away. Needs project state in <10 seconds.

**Entities:** Initiative (DOG), Features (DOG-T1..T5) with phase/status, Tasks within active Features
**Edges:** Features `belongs_to` Initiative, Tasks `implements` Features
**Scoping:** By Initiative shows all connected Features with status. Phase column shows pipeline position.
**Verdict:** Covered.

### UC-2: What should this session work on?

Session needs context: what's unblocked, highest priority, has enough context.

**Entities:** Features (unblocked, in_progress), Tasks (planned) within those Features
**Edges:** `blocks` edges identify what's actually unblocked. `implements` identifies available Tasks.
**Query:** Features where no incoming `blocks` edges are from incomplete entities, sorted by priority.
**Verdict:** Covered.

### UC-3: Parallel agents went off the rails

3 agents dispatched to write tests. All guessed wrong. Need scope constraints and completion gates.

**Entities:** Feature (integration-tests), Tasks (one per agent session), each with scope/criteria
**Edges:** Tasks `implements` Feature. Feature has gate (3-mode dial) on verification phase.
**Policy:** Task scope is part of description. Completion gate prevents marking done until tests pass.
**Verdict:** Covered. Scope lives in Task description + Feature gate policy.

### UC-4: Breaking down a big initiative

"Build Reasoning System v2" — multi-week, multi-component.

**Entities:** Initiative (RSv2), Features (core-lib, service, SDK, frontend), Tasks per Feature per phase
**Edges:** Features `belongs_to` Initiative. Features `blocks`/`sequencing` each other. Tasks `implements` Features.
**Discovery:** Session `produces` Initiative and initial Features.
**Verdict:** Covered.

### UC-5: Cross-project feature tracking

"Add decisions API" needs changes across 5 repos.

**Entities:** Feature (decisions-api), Tasks per repo (service, client, SDK, contracts, web)
**Edges:** Tasks `implements` Feature. Tasks `blocks`/`sequencing` each other (contracts before service, service before SDK).
**Verdict:** Covered. Cross-project is modeled as Tasks with repo-scoped descriptions under one Feature.

### UC-6: Product planning loop

Brainstorm → use cases → PRD → design with feedback loops.

**Entities:** Initiative (Forge-v1), Features for each planning output. Ideas from brainstorming. Threads capturing deliberation. Decisions recording choices. Questions tracking unknowns.
**Edges:** Ideas `informs` Features. Threads `informs` Decisions. Decisions `resolves` Questions. Discovery sessions `produces` everything.
**Artifacts:** Attach to Features at their producing phase (brainstorm.md at design, PRD.md at design).
**Verdict:** Covered. Planning is work; thinking artifacts are first-class.

### UC-7: Resuming after context loss

Session crashed mid-task. New session needs to pick up cleanly.

**Entities:** Task (assigned to crashed session), Feature (parent context)
**Edges:** Task `implements` Feature. Task stays in_progress.
**Recovery:** New session claims same Task. Feature's artifacts + Task description provide full context.
**Verdict:** Covered. Session state is external; the graph shows what's done vs not.

### UC-8: Deliberation and decision-making

Design question arises. Needs discussion, arguments, recorded decision.

**Entities:** Question (raised), Thread (discussion), Decision (outcome)
**Edges:** Thread `informs` Decision. Decision `resolves` Question. Question `questions` Feature or Initiative. Decision `informs` downstream Features/Tasks.
**Verdict:** Covered. Full deliberation chain is first-class.

### UC-9: Planning session producing multiple artifacts

Single session covers brainstorming, evaluation, decisions, process.

**Entities:** Thread (the session itself), Ideas/Decisions/Questions produced during it
**Edges:** Thread `produces` each entity created. Ideas `informs` Features. Decisions `resolves` Questions. Questions `questions` Features.
**Verdict:** Covered. A Thread can be the provenance container for a session's outputs.

### UC-10: Feature blocked by unresolved question

Feature can't proceed because a design question hasn't been answered.

**Entities:** Feature (blocked), Question (open)
**Edges:** Question `questions` Feature. Feature status: blocked.
**Resolution:** Decision `resolves` Question. Feature unblocks.
**Verdict:** Covered. The `questions`/`resolves` pair models this directly.

### UC-11: Idea that eventually becomes a Feature

Shower thought captured. Months later, it becomes real work.

**Entities:** Idea (floating), then later: Feature (created from it)
**Edges:** Initially none (Idea floats in bucket). Later: Idea `informs` Feature.
**Verdict:** Covered. Ideas can float free then get connected whenever.

### UC-12: Thread informing multiple Features across Initiatives

Architecture discussion that affects decisions in 3 workstreams.

**Entities:** Thread, Features in Initiative A, B, C
**Edges:** Thread `informs` Feature-A, Thread `informs` Feature-B, Thread `informs` Feature-C
**Verdict:** Covered. Edges are not constrained to within an Initiative.

### UC-13: Feature killed mid-lifecycle

Work started but scope changed. Feature no longer needed.

**Entities:** Feature (status: killed), Tasks within it
**Edges:** Tasks `implements` Feature. Any `blocks` edges from this Feature to others become irrelevant.
**Status:** Feature status → killed. Dependent Features check: if all `blocks` sources are killed or complete, they unblock.
**Verdict:** Covered. Status `killed` + `superseded` handle this.

### UC-14: Feature superseded by another

Original approach replaced by a better one after discovery.

**Entities:** Feature-A (superseded), Feature-B (replacement)
**Edges:** Need to record that B supersedes A. Could use `informs` (B was informed by A) but doesn't capture "replaces."
**Gap?** No explicit `supersedes` edge type. Status `superseded` on Feature-A records the fact, but not *what* superseded it.
**Mitigation:** Add a note in Feature-A's description referencing Feature-B. Or: `informs` is close enough ("A informed the creation of B").
**Verdict:** Mostly covered. Minor gap — no edge type for supersession. Acceptable for v1.

### UC-15: Discovery session re-entering mid-flight

Features are in implementation. Scope needs rethinking. New discovery session.

**Entities:** Discovery session (Thread), existing Initiative with Features
**Edges:** Thread `produces` new Questions, Decisions, possibly new Features. Thread `informs` existing Features.
**Verdict:** Covered. Discovery is re-entrant by design.

### UC-16: Bug report (unplanned work)

Production bug. Needs immediate fix, not the full feature lifecycle.

**Entities:** Feature (bug fix, starting at Implementation phase). Or: Task under existing Feature.
**Edges:** If standalone: Feature with no Initiative. If under existing: Task `implements` Feature.
**Lifecycle:** Starts at Implementation, skips Design/Planning.
**Verdict:** Covered. Features can skip phases and exist without Initiatives.

### UC-17: Dependency chain across Features

Feature A blocks Feature B which blocks Feature C. A completes — B should unblock.

**Entities:** Features A, B, C
**Edges:** A `blocks` B, B `blocks` C
**Query:** B is blocked until A.status === complete. C is blocked until B.status === complete.
**Verdict:** Covered. Transitive blocking via edge traversal.

### UC-18: Soft sequencing preference

"Better to do auth before payments, but not required."

**Entities:** Feature (auth), Feature (payments)
**Edges:** auth `sequencing` payments
**Behavior:** Dashboard shows the preference. Agent considers it when picking work. Not enforced.
**Verdict:** Covered. `sequencing` edge exists for this purpose.

### UC-19: Decision that resolves multiple questions

Architecture decision that settles 3 open questions at once.

**Entities:** Decision, Question-1, Question-2, Question-3
**Edges:** Decision `resolves` Question-1, Decision `resolves` Question-2, Decision `resolves` Question-3
**Verdict:** Covered. Edges are many-to-many.

### UC-20: Initiative status derived from Features

Initiative DOG has 5 Features. 3 complete, 1 in_progress, 1 planned. What's the Initiative's status?

**Entities:** Initiative (DOG), Features x5
**Edges:** Features `belongs_to` Initiative
**Derivation:** Initiative status = f(connected Features). If any in_progress → in_progress. If all complete → complete. If any blocked → partially blocked.
**Verdict:** Covered. Initiative has no independent status — it's derived.

### UC-21: Evaluation / audit of an existing Feature

"Is DOG-T1's design still valid after the architecture change?"

**Entities:** Question ("Is design still valid?"), Thread (the evaluation discussion), possibly Decision (outcome)
**Edges:** Question `questions` Feature. Thread `informs` Decision. Decision `resolves` Question.
**Verdict:** Covered. Evaluation is modeled as Question → Thread → Decision.

### UC-22: Artifact provenance ("why does this Feature exist?")

Tracing back from a Feature to the thinking that created it.

**Entities:** Feature, Discovery Thread/session that created it
**Edges:** Thread `produces` Feature
**Traversal:** From Feature, follow incoming `produces` edges to find origin.
**Verdict:** Covered. Provenance is explicit via `produces`.

### UC-23: Orphan cleanup (what's floating unattached?)

"Show me everything that isn't connected to active work."

**Entities:** Ideas, Threads, Questions, Decisions with no edges to any Initiative or Feature
**Query:** Entities where no outgoing `belongs_to`, `implements`, `informs`, `questions`, `resolves` edges exist.
**Verdict:** Covered. Bucket view filters for unattached entities.

### UC-24: Multiple Initiatives sharing a Feature

Shared infrastructure Feature needed by two Initiatives.

**Entities:** Feature (shared-auth), Initiative-A, Initiative-B
**Edges:** Feature `belongs_to` Initiative-A, Feature `belongs_to` Initiative-B
**Gap?** `belongs_to` is many-to-many? The ontology says "can belong to an Initiative" — singular.
**Mitigation:** Allow multiple `belongs_to` edges. The Feature shows up in both Initiative scopes.
**Verdict:** Covered if `belongs_to` allows multiple targets. Should be explicit in the data model.

### UC-25: Task reassignment between phases

Feature moves from Planning to Implementation. Planning tasks are done. New implementation tasks needed.

**Entities:** Feature (phase: implementation), old Tasks (complete, phase: planning), new Tasks (planned, phase: implementation)
**Edges:** All Tasks `implements` Feature. Each Task has a `phase` field.
**Verdict:** Covered. Tasks are scoped to a Feature phase. Phase transition creates new Tasks, old ones remain as history.

---

## Matrix 1: Entity Type Coverage

Each use case needs certain entity types. Does the ontology provide them?

| Use Case | Initiative | Feature | Task | Idea | Thread | Decision | Question | Covered? |
|----------|:---------:|:-------:|:----:|:----:|:------:|:--------:|:--------:|:--------:|
| UC-1: Where are we? | x | x | x | | | | | Yes |
| UC-2: Session assignment | | x | x | | | | | Yes |
| UC-3: Agent guardrails | | x | x | | | | | Yes |
| UC-4: Big decomposition | x | x | x | | | | | Yes |
| UC-5: Cross-project | | x | x | | | | | Yes |
| UC-6: Planning loop | x | x | | x | x | x | x | Yes |
| UC-7: Context recovery | | x | x | | | | | Yes |
| UC-8: Deliberation | | x | | | x | x | x | Yes |
| UC-9: Session artifacts | | x | | x | x | x | x | Yes |
| UC-10: Blocked by question | | x | | | | x | x | Yes |
| UC-11: Idea → Feature | | x | | x | | | | Yes |
| UC-12: Cross-initiative thread | x | x | | | x | | | Yes |
| UC-13: Feature killed | | x | x | | | | | Yes |
| UC-14: Feature superseded | | x | | | | | | Yes* |
| UC-15: Re-enter discovery | x | x | | | x | x | x | Yes |
| UC-16: Bug report | | x | x | | | | | Yes |
| UC-17: Dependency chain | | x | | | | | | Yes |
| UC-18: Soft sequencing | | x | | | | | | Yes |
| UC-19: Multi-question decision | | | | | | x | x | Yes |
| UC-20: Derived initiative status | x | x | | | | | | Yes |
| UC-21: Evaluation/audit | | x | | | x | x | x | Yes |
| UC-22: Artifact provenance | | x | | | x | | | Yes |
| UC-23: Orphan cleanup | | | | x | x | x | x | Yes |
| UC-24: Shared Feature | x | x | | | | | | Yes** |
| UC-25: Task phase transition | | x | x | | | | | Yes |

`*` No explicit `supersedes` edge. Status field + description reference suffice for v1.
`**` Requires `belongs_to` to allow multiple targets. Should be documented.

**Entity type usage frequency:**

| Entity Type | Used in N use cases | % |
|-------------|:------------------:|:--:|
| Feature | 23/25 | 92% |
| Task | 12/25 | 48% |
| Initiative | 8/25 | 32% |
| Question | 8/25 | 32% |
| Decision | 7/25 | 28% |
| Thread | 7/25 | 28% |
| Idea | 4/25 | 16% |

Feature is the workhorse. Thinking artifacts (Question, Decision, Thread) appear together. Ideas are low frequency but essential for capture-without-structure.

---

## Matrix 2: Edge Type Coverage

Each use case needs certain edge types. Does the ontology provide them?

| Use Case | blocks | sequencing | informs | implements | belongs_to | produces | questions | resolves | Covered? |
|----------|:------:|:---------:|:-------:|:----------:|:---------:|:--------:|:---------:|:--------:|:--------:|
| UC-1: Where are we? | | | | | x | | | | Yes |
| UC-2: Session assignment | x | | | x | | | | | Yes |
| UC-3: Agent guardrails | | | | x | | | | | Yes |
| UC-4: Big decomposition | x | x | | x | x | x | | | Yes |
| UC-5: Cross-project | x | x | | x | | | | | Yes |
| UC-6: Planning loop | | | x | | x | x | | | Yes |
| UC-7: Context recovery | | | | x | | | | | Yes |
| UC-8: Deliberation | | | x | | | | x | x | Yes |
| UC-9: Session artifacts | | | x | | | x | x | x | Yes |
| UC-10: Blocked by question | | | | | | | x | x | Yes |
| UC-11: Idea → Feature | | | x | | | | | | Yes |
| UC-12: Cross-initiative thread | | | x | | x | | | | Yes |
| UC-13: Feature killed | x | | | x | | | | | Yes |
| UC-14: Feature superseded | | | x | | | | | | Yes* |
| UC-15: Re-enter discovery | | | x | | | x | | | Yes |
| UC-16: Bug report | | | | x | | | | | Yes |
| UC-17: Dependency chain | x | | | | | | | | Yes |
| UC-18: Soft sequencing | | x | | | | | | | Yes |
| UC-19: Multi-question decision | | | | | | | | x | Yes |
| UC-20: Derived status | | | | | x | | | | Yes |
| UC-21: Evaluation/audit | | | x | | | | x | x | Yes |
| UC-22: Provenance | | | | | | x | | | Yes |
| UC-23: Orphan cleanup | | | | | | | | | Yes*** |
| UC-24: Shared Feature | | | | | x | | | | Yes** |
| UC-25: Task phases | | | | x | | | | | Yes |

`*` `informs` used as proxy for supersession.
`**` Requires `belongs_to` → multiple targets.
`***` Orphan detection = absence of edges, not presence.

**Edge type usage frequency:**

| Edge Type | Used in N use cases | % |
|-----------|:------------------:|:--:|
| implements | 10/25 | 40% |
| belongs_to | 7/25 | 28% |
| informs | 8/25 | 32% |
| blocks | 5/25 | 20% |
| produces | 4/25 | 16% |
| questions | 4/25 | 16% |
| resolves | 5/25 | 20% |
| sequencing | 3/25 | 12% |

`implements` and `informs` are the most used. `sequencing` is the least — it's a nice-to-have soft signal.

---

## Matrix 3: CR1-CR7 Alignment

How the ontology maps to the core requirements composition model.

| Core Requirement | Ontology Mechanism | Gaps |
|-----------------|-------------------|------|
| **CR1: Lifecycle phases** | Feature.phase (design → release). Only Features have phases. | None — other types don't need phases. |
| **CR2: Same things at every phase** | Idea/Thread/Decision/Question exist at any phase. Tasks exist within a Feature phase. | None — thinking artifacts are phase-independent. |
| **CR3: Four verbs (See/Change/Evaluate/Execute)** | See = scoped views + graph. Change = CRUD on entities + edges. Evaluate = Question/Decision/Thread cycle. Execute = Task assignment + Feature gates. | None — verbs map to operations on the graph. |
| **CR4: Universal processes** | Discovery = produces edges. Evaluation = questions/resolves cycle. Synthesis = Thread informs Decision. Capture = entity creation. | None — processes are edge patterns, not separate types. |
| **CR5: Cross-cutting lenses** | Confidence = on Feature (gates). Governance = 3-mode dial on gates. Scope = Initiative/Feature/Task nesting. Actor = Task.assignee. Time = created_at/updated_at. | Confidence is less granular — only gate-level, not per-entity. May need a confidence field on all entities later. |
| **CR6: AI proactive** | Orthogonal to data model. AI operates on the graph. | Not a data model concern — behavioral. |
| **CR7: Phase transitions recognized** | Feature.phase tracks position. Artifacts per phase provide evidence. Gates provide transition mechanism. | None — the 3-mode dial governs transition feel. |

---

## Matrix 4: Ontology Completeness — Are Any Entity/Edge Types Unused?

| Component | Used By | Unused? |
|-----------|---------|---------|
| Initiative | UC-1,4,6,12,15,20,24 | No |
| Feature | UC-1-7,10-18,20-22,24,25 | No |
| Task | UC-1-5,7,13,16,25 | No |
| Idea | UC-6,9,11,23 | No |
| Thread | UC-6,8,9,12,15,21,22 | No |
| Decision | UC-6,8-10,15,19,21 | No |
| Question | UC-6,8-10,15,19,21,23 | No |
| blocks | UC-2,4,5,13,17 | No |
| sequencing | UC-4,5,18 | No |
| informs | UC-6,8,9,11,12,14,15,21 | No |
| implements | UC-1-5,7,13,16,25 | No |
| belongs_to | UC-1,4,6,12,20,24 | No |
| produces | UC-4,6,9,15,22 | No |
| questions | UC-8-10,21 | No |
| resolves | UC-8-10,19,21 | No |

All 7 entity types and all 8 edge types are exercised by at least 3 use cases. No dead weight.

---

## Identified Gaps

| # | Gap | Severity | Mitigation |
|---|-----|----------|------------|
| G1 | No `supersedes` edge type | Low | Use `informs` + status `superseded` + description reference for v1. Add edge type later if needed. |
| G2 | `belongs_to` cardinality not explicit | ~~Low~~ Fixed | Documented as many-to-many in product realignment. |
| G3 | No per-entity confidence field | ~~Medium~~ Fixed | Added `confidence: 1-5 | null` to Entity base. Features get both lifecycle-derived baseline and explicit override. Thinking artifacts use it as attention signal. |
| G4 | No explicit session/actor entity | Low | Sessions are external. Task.assignee covers assignment. If session tracking becomes a requirement, add a Session entity type later. |
| G5 | No `depends_on` (generic dependency) | None | `blocks` and `sequencing` cover hard and soft dependencies. No need for a generic version. |

---

## Verdict

The ontology handles 25/25 use cases. G2 and G3 have been fixed in the product realignment doc. G1 (supersession) is acceptable for v1. No entity type or edge type is unused. The model is tight — nothing to add, nothing to remove.

---

## Related Documents

- [Product Realignment](2026-02-13-product-realignment.md) — the ontology under test
- [Use Cases](../use-cases.md) — original 9 use cases (UC-1 through UC-9)
- [Core Requirements](../requirements/core-requirements.md) — CR1-CR7
- [Product Graph](../../src/components/ProductGraph.jsx) — visual rendering of the ontology
