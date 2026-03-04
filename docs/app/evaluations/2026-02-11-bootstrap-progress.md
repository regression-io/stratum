# Bootstrap Progress: Manual Process Simulation

**Date:** 2026-02-11
**Type:** Progress tracking + process gap analysis
**Purpose:** Simulate what Forge would track, done manually. Identify where our actual process diverges from what Forge would enforce.
**Related:** [Integration Roadmap](../plans/2026-02-11-integration-roadmap.md), [Persistence Connector Plan](../plans/2026-02-11-persistence-connector-plan.md), [UI Additions Brief](../specs/2026-02-11-ui-additions-brief.md)

---

## Work Item Hierarchy (as Forge would track it)

```
w-bootstrap: Bootstrap Phase 0                              [IN_PROGRESS]
│
├── w-0.1: Discovery + Requirements + Design                [COMPLETE]
│   Output: brainstorm.md, PRD.md, use-cases.md, taxonomy.md,
│           decisions/*, process/*, CLAUDE.md
│   Gate: ✅ Core concepts defined, decisions documented
│
├── w-0.2: External Build + Verification                    [COMPLETE]
│   ├── w-0.2a: Write UI-BRIEF spec                        [COMPLETE]
│   ├── w-0.2b: Send to Base44 builder                     [COMPLETE]
│   ├── w-0.2c: Receive delivery                           [COMPLETE]
│   ├── w-0.2d: Evaluate delivery (delivery-intake process) [COMPLETE]
│   │   Output: evaluations/2026-02-11-base44-ui-eval.md
│   │   Gaps: 2 structural, 10 functional, 5 expected, 5 surplus
│   └── w-0.2e: Session meta-review                        [COMPLETE]
│       Output: evaluations/2026-02-11-session-meta-review.md
│   Gate: ✅ Gaps classified, integration path clear
│
├── w-0.3: Persistence Connector                            [IN_PROGRESS]
│   │
│   ├── w-0.3.1: Design persistence connector              [COMPLETE]
│   │   Output: plans/2026-02-11-persistence-connector-plan.md
│   │   informs → w-0.3.3 (server implementation)
│   │   informs → w-0.3.7 (UI wiring)
│   │
│   ├── w-0.3.2: Write UI additions spec                   [COMPLETE]
│   │   Output: specs/2026-02-11-ui-additions-brief.md
│   │   8 additions specified (artifact editor, dep types, etc.)
│   │   informs → w-0.3.4 (UI additions build)
│   │
│   ├── w-0.3.3: Implement server + persistence layer      [COMPLETE]
│   │   Output: server/ directory (7 files)
│   │   Acceptance criteria:
│   │     [?] Server starts without errors
│   │     [?] CRUD operations work via curl
│   │     [?] .forge/ files are human-readable markdown
│   │   ⚠️ NOT VERIFIED — written but never tested
│   │
│   ├── w-0.3.4: UI additions delivery                     [COMPLETE]
│   │   Delivered by: external builder / user edits
│   │   Files changed: WorkDetailPanel, CreateWorkDialog,
│   │     DependencyGraph, Dashboard + new components
│   │   New: ArtifactEditor, EvaluationGapsPanel
│   │   New fields: type, phase, gaps, propagation_reviewed
│   │   New dep types: informs, relates_to
│   │
│   ├── w-0.3.5: Evaluate UI additions delivery            [NOT DONE] ← SKIPPED
│   │   Should follow: delivery-intake process
│   │   Should produce: gap classification against spec
│   │   Should produce: shape audit (what fields exist now?)
│   │   blocks → w-0.3.6
│   │
│   ├── w-0.3.6: Audit connector vs actual UI data shape   [NOT DONE]
│   │   The plan was written against old UI. UI has evolved.
│   │   Need: diff of what connector handles vs what UI sends
│   │   blocks → w-0.3.7
│   │
│   ├── w-0.3.7: Update connector to match UI              [NOT DONE]
│   │   blocks → w-0.3.8
│   │
│   └── w-0.3.8: Wire connector to UI                      [NOT DONE]
│       Import swap, AuthContext stub, vite proxy, package.json
│       Gate: Can we create Work items and see them after restart?
│
└── ── EARLY HANDOFF: Forge tracks its own work from here ──
```

---

## What Actually Happened (chronological)

| # | Action | Forge Phase | Process Followed? |
|---|--------|-------------|-------------------|
| 1 | Plan written and approved | Design → Planning | ✅ Yes |
| 2 | Server + persistence layer coded | Implementation | ⚠️ Partial — written but not tested |
| 3 | forgeClient.js coded | Implementation | ✅ Yes |
| 4 | Started swapping UI imports | Implementation | ❌ **Gate failure** — UI wasn't ready |
| 5 | User caught it, reverted | — | ✅ Recovery |
| 6 | UI additions delivered externally | External delivery | ✅ Happened |
| 7 | Agent proposed jumping straight to wiring | Implementation | ❌ **Gate failure (caught)** — no eval of delivery |
| 8 | User caught it again: "follow the process" | — | ✅ Recovery |
| 9 | This document | Evaluation | ✅ Doing it now |

---

## Gate Failures

### Failure 1: Wiring before UI was ready

**What happened:** Plan was approved. Agent immediately started implementing everything — including the UI wiring (import swaps, AuthContext, vite config) — without checking whether the UI it was wiring to was the final version.

**What Forge would enforce:** `w-0.3.8: Wire connector to UI` would have `blocked_by: w-0.3.4 (UI delivery)`. The status of w-0.3.4 was not `complete`, so w-0.3.8 should not have started.

**Root cause:** Plan approval was treated as execution trigger for ALL steps. No per-step dependency check.

**Process gap:** Need a state between `planned` and `in_progress` — or more precisely, need dependency checking before any item moves to `in_progress`.

### Failure 2: Skipping delivery evaluation

**What happened:** UI additions were delivered. Agent proposed immediately auditing shape + updating connector + wiring — skipping the delivery-intake evaluation that our own process doc defines.

**What Forge would enforce:** `w-0.3.5: Evaluate UI additions` would be `blocked_by: w-0.3.4` and would `block: w-0.3.6`. The evaluation step is mandatory before integration work begins.

**Root cause:** Implementation bias. The agent sees code changes and wants to write code. The evaluation step feels like overhead when you can "just look at the diffs."

**Process gap:** Delivery intake should be a gate, not optional. When a delivery arrives, evaluation happens before any integration work. This is exactly what the delivery-intake process doc says — we just didn't follow it.

---

## Shape Drift (known but unquantified)

The persistence connector plan was designed against the **original** Base44 UI shape. The UI has since been updated with:

| New Field/Concept | In Plan? | In Server? | In forgeClient? |
|-------------------|----------|------------|-----------------|
| `type` (task/decision/evaluation/...) | ✅ In connector plan | ❌ Not in create/update | ❌ Not handled |
| `phase` (discovery/requirements/...) | ✅ In connector plan | ❌ Not in create/update | ❌ Not handled |
| `gaps` array (for evaluations) | ❌ | ❌ | ❌ |
| `propagation_reviewed` flag | ❌ | ❌ | ❌ |
| Dependency type: `informs` | ✅ In connector plan | ❌ Only `blocks` | ❌ Not exposed |
| Dependency type: `relates_to` | ✅ In connector plan | ❌ Only `blocks` | ❌ Not exposed |
| `ArtifactEditor` component | N/A (UI only) | N/A | N/A |
| `EvaluationGapsPanel` component | N/A (UI only) | N/A | N/A |

This table is incomplete — it's based on what we know from the diff notifications, not from a proper delivery evaluation. That's the point of w-0.3.5.

---

## Critical Gap: No Beginning

### The problem

The current UI has no onboarding. Open Forge → empty Dashboard → "Create Work Item." This assumes you already know:
- What you're building
- How you want to work (which gates, which policies)
- What phase you're in
- What your project structure looks like

But Forge's entire thesis is that **thinking precedes doing.** The tool that structures thinking can't skip its own first-thinking moment.

### What should happen instead

The first experience should be a **guided conversation** — part chat, part structured options:

1. **"What are you building?"** — Describe the project. Freeform input + structured prompts (name, domain, scope).

2. **"How do you want to work?"** — Choose process defaults. This is where gate preferences get set:
   - How much autonomy do agents get? (conservative/balanced/autonomous → maps to gate/flag/skip defaults)
   - Which phases matter? (discovery-heavy vs implementation-heavy)
   - Solo or team? (affects review gates)
   - What does "done" mean for this project? (acceptance criteria templates)

3. **"What do you know so far?"** — Capture existing context. Import docs, paste brainstorm notes, describe decisions already made. This bootstraps the knowledge graph instead of starting empty.

4. **Transition into brainstorming** — The onboarding conversation naturally IS the first brainstorming session. The answers to "what are you building" and "how do you want to work" become the first Work items (type: brainstorm, type: decision).

### Why this is fundamental, not cosmetic

Without onboarding, the "early handoff" moment from the roadmap doesn't work. The gate says: "Can we create Work items and see them after restart?" But the real question is: **can Forge host a planning session from the beginning?** Not "can it store data" but "can it guide the thinking that produces the data."

The current UI answers the storage question. It doesn't answer the thinking question.

### What this means for the connector work

The connector (server + persistence) is infrastructure — needed regardless of UI flow. But the **wiring** (connecting UI to connector) should wait until we know what the first-run experience looks like, because:
- The onboarding flow will produce Work items and Projects with specific shapes
- The gate/policy defaults chosen during onboarding affect how everything downstream behaves
- The first thing the connector stores should be the output of onboarding, not an empty project created from a blank form

### Forge concepts this maps to

- **Project templates** — Onboarding produces a project scaffold with phase structure, default policies, initial work items
- **Conversational intake** — Chat-style interaction that produces structured data (this is a connector pattern: conversation → domain objects)
- **Policy defaults** — The gate/flag/skip dials get initial positions during onboarding, not after-the-fact
- **Brainstorming as first phase** — Onboarding IS the discovery/brainstorming phase. The tool shouldn't separate "setup" from "work" — setup is work.

---

## Process Observations for Forge

### What worked

1. **The document chain exists and is useful.** Brainstorm → PRD → Spec → Build → Evaluate — we followed this in Phase 0.1 and 0.2 and it produced good results.

2. **The delivery-intake process is well-defined.** When we used it (Base44 eval), it caught structural issues and produced actionable gaps. The process doc is solid.

3. **Gates catch real problems.** Both failures above were caught by human gates. The agent would have proceeded without them.

### What's missing

1. **Dependency enforcement before execution.** A plan's approval doesn't mean all items are unblocked. Each item needs its own readiness check.

2. **Delivery evaluation is not optional.** Every external delivery — whether from Base44, an AI agent, or a user's manual edits — should trigger the delivery-intake process before integration work begins. This should be a gate-mode policy.

3. **Shape drift tracking.** When a plan references a data model and the data model evolves, the plan becomes stale. Forge should surface "plan references stale schema" as a propagation indicator (the `informs` dependency pattern).

4. **Implementation bias mitigation.** Agents (and humans) want to write code. The process needs friction at the right points — not to slow things down, but to prevent wasted work. The two failures above both would have resulted in code that needed rewriting.

5. **"Plan approved" ≠ "Start everything."** Multi-step plans need per-step gating. This is what the `blocks`/`blocked_by` dependency system is for — but we weren't using it even manually.

---

## Architecture Pivot

During this session, the bootstrap approach was fundamentally reframed. See [Agent-Primary Architecture Decision](../decisions/2026-02-11-agent-primary-architecture.md).

**Key insight:** The minimum bootstrap isn't "build infrastructure, then use it." It's "embed an agent that can build anything, then use that." The agent panel + persistence wiring are the only two hard prerequisites. Everything else is built from inside Forge using those two capabilities.

**Product framing:** Forge is the first truly agentic IDE — planning to deployment covered agentically. The structured UI is the cockpit (read + quick-write). The agent panel is the copilot (conversation + complex creation + self-modification).

---

## Current State

```
DONE                                    NEXT
──────────────────────                  ──────────────────────
✅ Discovery + design                   ① Remove Base44 SDK, wire persistence
✅ Base44 delivery + evaluation            (trivial — code exists, just connect)
✅ UI additions spec + delivery
✅ Server + persistence coded           ② Embed agent panel in UI
✅ forgeClient coded                       (the real design question)
✅ Agent-primary decision                  See: bootstrap-questions.md
                                           Blocked by: Q1 + Q2

                                        ③ Everything else — built from
                                           inside Forge using ① + ②
```

**Open questions before ②:** [bootstrap-questions.md](../plans/2026-02-11-bootstrap-questions.md)

---

## The Meta Point (third time)

We've now experienced three levels of what Forge automates:

1. **Process enforcement** — Gate failures caught by human attention, not by system structure.
2. **Decision capture** — Architectural pivots happening in chat, manually written to docs after the fact.
3. **Brainstorming → action** — This conversation produced a decision, open questions, and a revised plan. All manually extracted and filed.

The agent panel solves all three. The conversation IS the brainstorm. The agent captures decisions as they're made. The process docs ARE the enforcement mechanism. And the agent can build whatever Forge needs next — including improving how it does all of this.
