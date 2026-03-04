# Session 0: The Planning Marathon

**Date:** 2026-02-11
**Duration:** One long session
**Phase:** Bootstrap (Phase 0)
**Participants:** Human + Claude Code agent

---

## What happened

Started with a question: what would a mission control system for AI-driven development look like? Not just task tracking — something that captures the *thinking* alongside the doing.

### Finding the fundamentals: 3 x 3

Before writing any spec or requirements doc, we spent significant time searching for the irreducible core. What are the fewest concepts from which everything else follows?

The answer: **three primitives, each with three sub-constructs.**

**Work** — a thing that needs to get done. A tree node with optional children.
- *Structure* — what it is and where it sits (identity + hierarchy)
- *State* — where it is in its lifecycle (planned → ready → in_progress → review → complete)
- *Evidence* — what it produced (commits, test results, files changed)

**Policy** — a 3-mode dial attached to a decision point.
- *Trigger* — what decision point activates this policy (the *when*)
- *Mode* — gate / flag / skip (the *how strict*)
- *Criteria* — what's evaluated: tests pass, files in scope, budget under limit (the *what*)

**Session** — an actor interacting with Work, governed by Policies.
- *Actor* — who or what (human, claude-code, team)
- *Assignment* — what Work the session is bound to
- *Context* — what the session knows (inherited from Work hierarchy + policies = the briefing)

The core axiom: **every decision point is a 3-mode dial.** Gate (blocked until human decides), flag (agent proceeds, human notified), skip (agent proceeds silently). One mechanism everywhere. Dependencies, scope boundaries, acceptance criteria, budget limits, decomposition approval — all are specific instances of Policy with different triggers and criteria.

Everything else in the system — the UI views, the status lifecycle, the dependency types, the artifact model — derives from these nine building blocks. The taxonomy doc later formalized this as the invariant/variant split: the three primitives are invariant (same everywhere), while phases, templates, and workflows are variants (configuration, not code).

This was the intellectual foundation that made the rest of the design session productive. Every time a new concern arose ("how do we handle evaluations?" "what about parallel agent coordination?"), the answer was: which primitive, which sub-construct, which policy mode?

### The document chain

With the fundamentals in place, produced the full design stack in sequence:

1. **Brainstorm** — explored the product space, landscape analysis, found the 3x3 structure
2. **Use cases** — 9 scenarios spanning solo dev through team coordination. The deliberation use case (brainstorm → decision → spec → build → evaluate) became the backbone.
3. **PRD** — full requirements built on the three primitives. Feature areas map to primitives: Work Hierarchy, Policy System, Session Management, UI Views.
4. **Taxonomy** — the invariant/variant split. Formalized: the system is one mechanism everywhere. Phases differ only in defaults, not in structure.
5. **UI-BRIEF** — behavioral spec for an external builder. Described what users can do, not which libraries to use.
6. **Process docs** — delivery-intake and spec-writing. Meta: processes for the process of building Compose.

### Key decisions

- **Deterministic UI, dynamic content** — fixed layout, LLM contributes content that renders in existing views
- **Deliberation is Work** — no special entity types. Brainstorms, decisions, evaluations are all Work items with labels.
- **Three-mode policy dial** — gate (blocked until human decides), flag (agent proceeds, human notified), skip (agent proceeds silently)
- **Connector architecture** — persistence, agents, UI are all swappable connectors

### The POC: building the UI first

After the design stack was complete, the instinct was: build the UI. Sent the UI-BRIEF to Base44 as a behavioral spec. Got a working delivery back — dashboard, tree view, board view, dependency graph, work item detail panel. A real app you could click around in.

Evaluated it using our own delivery-intake process. The gap analysis was thorough: 2 structural gaps (Base44 SDK dependency, hardcoded data shapes), 10 functional gaps (no keyboard nav, no `informs` deps, no artifact editor, no grouping), 5 expected omissions, 5 surplus features we didn't ask for.

Then started the integration work — coding a persistence layer (Express + markdown-in-folders), writing a composeClient to replace the Base44 SDK. Everything was progressing linearly: design → spec → build → wire.

### The step back: "we're building this wrong"

Midway through integration, stopped. The realization: we were building Compose the traditional way — infrastructure piece by piece, features one at a time, agent interaction deferred to "Phase 4." But Compose's entire thesis is that an AI agent is a co-builder. Why was the agent the last thing we'd add?

The POC was useful as validation — it proved the UI concepts worked, the data model was sound, the behavioral spec produced a reasonable delivery. But the POC was also a trap. It created a gravity well: "we have a working UI, let's just keep building on it." The risk was building a task tracker that works fine but doesn't embody the agent-primary architecture that makes Compose different from every other project management tool.

**The pivot:** Instead of building up to the agent, start with the agent. Embed Claude Code in the UI immediately. Two prerequisites only: persistence (so data survives) and the terminal (so the agent can work). Everything else — onboarding, templates, evaluation workflows, new views — gets built from inside Compose by the agent itself.

This became the [Agent-Primary Architecture Decision](../decisions/2026-02-11-agent-primary-architecture.md). The POC wasn't wasted — it validated the design and gave us a UI shell to embed the terminal into. But the build order flipped: agent first, features second.

### Gate failures

Two process violations caught by human attention:
1. Started wiring UI before the external delivery arrived (dependency not checked)
2. Skipped delivery evaluation to jump straight to integration (process doc not followed)

Both would have produced code that needed rewriting. Both caught manually. Both are exactly what Compose's policy system would automate.

### The architecture pivot

Late in the session, realized the bootstrap was backwards. Original plan: build infrastructure, then agent connector as Phase 4. New plan: embed the agent first, use it to build everything else.

**Agent-primary architecture:** The terminal is the primary write interface. The structured UI is the primary read interface. Both backed by `.compose/` persistence.

### What was produced

```
docs/
  brainstorm.md, PRD.md, use-cases.md, taxonomy.md, connectors.md
  specs/UI-BRIEF.md, specs/2026-02-11-ui-additions-brief.md
  decisions/deterministic-ui.md, deliberation-as-work.md, agent-primary-architecture.md
  process/delivery-intake.md, spec-writing.md
  evaluations/base44-ui-eval.md, session-meta-review.md, bootstrap-progress.md
  plans/integration-roadmap.md, persistence-connector-plan.md, bootstrap-questions.md

coder-compose/server/     — Express + persistence layer (coded, not tested)
coder-compose/src/api/    — composeClient.js (coded, not wired)
```

## What we learned

1. **The document chain works.** When each doc feeds the next, quality compounds. Skipping a step (like delivery evaluation) is immediately felt downstream.
2. **Process docs are agent instructions.** delivery-intake.md worked perfectly as an evaluation protocol — followed step by step, produced structured output.
3. **Gates catch real problems.** Both failures were "let me just skip ahead" moments. The system needs friction at exactly those points.
4. **POCs validate but also create gravity.** The Base44 UI proved the design was sound. It also created pressure to "just keep building on it" instead of questioning the build order. Validation and commitment are different things.
5. **Build order matters more than build quality.** The persistence layer and composeClient were well-coded. But coding them before the agent was embedded meant building Compose the way you'd build any app — linearly, feature by feature. The agent-first pivot changed *what we build next*, not *what we'd eventually build*.
6. **Self-hosting is the test.** The session itself was the use case. Every pain point ("I can't track this decision," "where did we leave off?") maps directly to a Compose feature.

## Mood

Exhausting but generative. Produced more structured design work in one session than most projects get in a week. The meta-awareness — building the tool while experiencing the need for it — kept the design honest.

---

*This entry reconstructed from [bootstrap-progress.md](../evaluations/2026-02-11-bootstrap-progress.md) and related docs. Future entries written in real time.*
