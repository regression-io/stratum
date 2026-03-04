# Forge: Project Taxonomy

**Date:** 2026-02-11
**Status:** DECIDED
**Related:** [PRD](PRD.md), [UI-BRIEF](UI-BRIEF.md), [Deliberation Decision](decisions/2026-02-11-deliberation-as-work.md)

---

## Principle

Everything in Forge is a Work item. Phases and types are labels, not different systems. The primitive is always the same. What varies is the defaults — what "done" means, what gets produced, who does it, how much trust.

---

## Invariants (same everywhere)

These never change regardless of phase, type, or project:

| Invariant | Description |
|-----------|-------------|
| **Work primitive** | Every trackable thing is a Work item with the same fields |
| **Status lifecycle** | planned → ready → in_progress → review → complete (+ blocked, parked) |
| **Hierarchy** | Arbitrary depth parent-child. A Discovery item can contain Design children. |
| **Dependencies** | blocks (execution), informs (knowledge), relates_to (reference) |
| **Artifacts** | Any Work item can have attached/inline documents |
| **Evidence** | Any Work item can have proof of what happened |
| **Policies** | gate/flag/skip applies to any decision point at any phase |
| **Connectors** | Persistence, agents, UI are phase-agnostic |
| **UI views** | Dashboard, Detail, Graph, Board, Settings — same views for all work |

The invariants are the system. Everything else is configuration.

### Who specifies variants?

Variants are governed by the same 3-mode dial as everything else:

| Mode | Who specifies | Example |
|------|--------------|---------|
| **Gate** | Human defines the variant | Human writes acceptance criteria, chooses artifact types, sets policy levels |
| **Flag** | AI proposes, human reviews | AI suggests acceptance criteria for a Design item, human edits and approves |
| **Skip** | AI decides autonomously | AI auto-fills defaults when creating an Implementation task from a plan |

This means the entire variant table — what "done" means, what gets produced, trust levels — is not hardcoded. It's a starting point that either the human or the AI can adjust, governed by how much autonomy the human has granted at that level of the hierarchy.

A strict project might gate all variant choices (human defines every acceptance criterion). A high-trust project might skip most of them (AI fills in sensible defaults, human only reviews when flagged). The taxonomy provides the vocabulary and defaults. The policy system governs who gets to change them.

---

## Project Lifecycle Phases

Every project, feature, or initiative moves through these phases. Not every item hits every phase — a small task might jump straight to Implementation. But the phases are always available and always in this order when used.

### Vision

**Purpose:** Set direction. Define goals, intent, and the problem space.

| Aspect | Default |
|--------|---------|
| **Acceptance criteria** | Goal articulated, problem understood, direction committed |
| **Artifact types** | Brainstorm notes, research findings, landscape analysis, POC code/demos, vision statements |
| **Dependency pattern** | Vision **informs** Requirements and Design |
| **Session type** | Human + AI collaborative (brainstorming together) |
| **Policy default** | Skip (explore freely, low constraint) |
| **Completion** | "We know what we're trying to do and why" |

**Examples:** brainstorm.md, landscape analysis, proof of concept, user research

> **Note:** Renamed from "Discovery" to "Vision" to avoid collision with the Discovery *primitive*. The primitive is the process mechanism (Q&A decomposition that produces concrete outputs from loose inputs). The phase label is the level of concreteness (vision/goal/direction). Discovery the process operates at every phase boundary, not just here.

### Requirements

**Purpose:** Define what to build. Capture needs, constraints, success criteria.

| Aspect | Default |
|--------|---------|
| **Acceptance criteria** | Stakeholders agree, use cases validated, success criteria testable |
| **Artifact types** | PRD, use cases, user stories, acceptance criteria |
| **Dependency pattern** | Requirements **informs** Design, **blocks** Planning |
| **Session type** | Human-driven, AI assists (generates use cases, finds gaps) |
| **Policy default** | Flag (human reviews AI-generated requirements) |
| **Completion** | "We agree on what to build and how to measure success" |

**Examples:** PRD.md, use-cases.md, success criteria, constraints

### Design

**Purpose:** Decide how to build it. Make structural choices. Record rationale.

| Aspect | Default |
|--------|---------|
| **Acceptance criteria** | Decision made with rationale, alternatives documented, downstream items informed |
| **Artifact types** | Architecture docs, decision records, specs/briefs, data models, interface contracts |
| **Dependency pattern** | Design **blocks** Planning and Implementation, decisions **inform** specs |
| **Session type** | Human decides, AI proposes options and analyzes tradeoffs |
| **Policy default** | Gate on decisions (human must approve structural choices) |
| **Completion** | "We know how to build it and why" |

**Examples:** UI-BRIEF.md, architecture decisions, API contracts, data model

### Planning

**Purpose:** Break work down into executable pieces. Sequence and assign.

| Aspect | Default |
|--------|---------|
| **Acceptance criteria** | Breakdown complete, dependencies identified, all items are actionable |
| **Artifact types** | Implementation plans, task breakdowns, dependency graphs, roadmaps |
| **Dependency pattern** | Planning **blocks** Implementation |
| **Session type** | Human + AI (decomposition proposals, human reviews) |
| **Policy default** | Flag (AI proposes breakdown, human reviews) |
| **Completion** | "Every piece of work is defined, sequenced, and ready to claim" |

**Examples:** integration-roadmap.md, implementation plans, sprint/phase breakdowns

### Implementation

**Purpose:** Build it. Write code, create assets, integrate systems.

| Aspect | Default |
|--------|---------|
| **Acceptance criteria** | Code works, tests pass, acceptance criteria from Requirements met |
| **Artifact types** | Code, tests, configurations, migrations |
| **Dependency pattern** | Implementation **blocks** Verification |
| **Session type** | AI primarily, human reviews. Configurable trust per item. |
| **Policy default** | Configurable — gate for critical/novel, skip for routine |
| **Completion** | "It works and meets the criteria" |

**Examples:** Feature code, test suites, database migrations, API endpoints

### Verification

**Purpose:** Confirm it works. Evaluate against criteria. Identify gaps.

| Aspect | Default |
|--------|---------|
| **Acceptance criteria** | All items classified and actioned, no unresolved structural gaps |
| **Artifact types** | Evaluations, test reports, gap classifications, review notes |
| **Dependency pattern** | Verification **blocks** Release, gaps **inform** new Implementation items |
| **Session type** | Mixed — AI runs tests and classifies, human evaluates and decides |
| **Policy default** | Gate (human must sign off on verification results) |
| **Completion** | "We've confirmed it works and know what's left" |

**Examples:** base44-ui-eval.md, test reports, code reviews, delivery intake

### Release

**Purpose:** Ship it. Deploy, monitor, confirm stability.

| Aspect | Default |
|--------|---------|
| **Acceptance criteria** | Deployed, monitored, stable, documented |
| **Artifact types** | Release notes, deployment configs, changelog entries |
| **Dependency pattern** | Release **informs** next Discovery cycle (feedback, learnings) |
| **Session type** | Automated (CI/CD), human monitors |
| **Policy default** | Gate (human approves release) |
| **Completion** | "It's live and stable" |

**Examples:** Deployment, changelog, release notes, monitoring dashboards

---

## Cross-Cutting Concerns

These happen in any phase, not tied to a specific lifecycle stage:

| Concern | Description | Work Item Pattern |
|---------|-------------|-------------------|
| **Decision** | A question that needs answering. Can arise in Discovery, Design, Implementation, anywhere. | Label: "decision". Name is the question. Artifacts: rationale, rejected alternatives. |
| **Evaluation** | Assessing something against criteria. Can be a delivery, a design, a POC. | Label: "evaluation". Artifacts: gap classification, assessment. |
| **Process** | A reusable pattern learned from doing. | Label: "process". Artifacts: the process doc. |
| **Retrospective** | Reflecting on what worked and what didn't. | Label: "retrospective". Artifacts: learnings, improvements. |

Cross-cutting items attach to the Work item in whatever phase triggered them, via `informs` or `relates_to` dependencies.

---

## The Variant Table

Summary of what changes per phase:

| Phase | Done means | Produces | Who | Trust | Feeds into |
|-------|-----------|----------|-----|-------|-----------|
| Vision | Direction set, problem understood | Notes, POCs, research | Human + AI | High (skip) | Requirements, Design |
| Requirements | Agreement on what | PRD, use cases, criteria | Human, AI assists | Medium (flag) | Design, Planning |
| Design | Decisions made | Specs, decisions, contracts | Human decides, AI proposes | Low (gate) | Planning, Implementation |
| Planning | Work is actionable | Plans, breakdowns, sequences | Human + AI | Medium (flag) | Implementation |
| Implementation | Criteria met | Code, tests, configs | AI builds, human reviews | Configurable | Verification |
| Verification | Gaps classified | Evaluations, reports | Mixed | Low (gate) | Release, or back to Implementation |
| Release | Live and stable | Deployments, docs | Automated + human | Low (gate) | Next Discovery |

---

## Naming Convention

Work items use two label dimensions:

- **Phase label:** vision, requirements, design, planning, implementation, verification, release
- **Type label:** task, decision, evaluation, process, spec, brainstorm, poc, retrospective — or any user-defined type

Phase is where it sits in the lifecycle. Type is what kind of work it is. These are orthogonal — a decision (type) can happen during design (phase) or implementation (phase).

Standard labels are suggested defaults, not enforced. Users can create their own labels. The taxonomy provides a shared vocabulary, not a straitjacket.

---

## How This Maps to Forge UI

The taxonomy doesn't change the UI — it configures it:

- **Dashboard:** Group by phase to see lifecycle progress. Group by type to see all decisions.
- **Filters:** Filter by phase label to see "all Design work". Filter by type to see "all evaluations".
- **Templates:** When creating a Work item, selecting a phase pre-fills default acceptance criteria and artifact types.
- **Dependency graph:** Phase ordering (Vision → Requirements → Design → ...) is visible as a left-to-right flow.

The deterministic UI renders all of it. The taxonomy just gives it a shared vocabulary and sensible defaults.
