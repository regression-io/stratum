# Vision Component Spec

| | |
|---|---|
| **Date** | 2026-02-11 |
| **Source** | [Core Requirements](../requirements/core-requirements.md) CR1-CR7, [Pipeline Matrices](../requirements/matrices.md) Vision row |
| **Audience** | Builder (us) |
| **Scope** | The Vision phase of Forge — the first buildable piece |

---

## What is this?

> Source: [Vision Statement](../discovery/discovery-process/vision-statement.md) — variable entry points, "I have a fuzzy idea" on-ramp

The Vision component supports the first phase of knowledge work in Forge: taking a fuzzy idea and turning it into a crystallized direction. Users create ideas, make connections, identify gaps, run evaluations, and arrive at decisions about what to build and why.

This is the on-ramp to the pipeline. Some users start here ("I have a fuzzy idea"), some skip it ("Build me X"). When used, it produces: a vision statement, feature map, key decisions, and enough clarity to enter requirements.

---

## What are we building?

The smallest piece that lets a user do Vision-phase work inside Forge instead of scattered markdown files and chat transcripts.

**In scope:**

| Capability | Source |
|---|---|
| Create and evolve the 7 types of things within the Vision phase | CR2, Matrix 2 Vision row |
| See the emerging picture: items, connections, gaps, confidence, status | CR3/See, Matrix 1 Vision/See |
| Change items: create, connect, synthesize, mark decisions | CR3/Change, Matrix 1 Vision/Change |
| Evaluate items: run counterfactuals, update confidence, crystallize or kill | CR3/Evaluate, Matrix 1 Vision/Evaluate |
| Execute minimally: trigger research, capture results | CR3/Execute, Matrix 1 Vision/Execute |
| AI proactivity: surfaces observations, challenges claims, runs evaluations in background | CR6, Matrix 4 Vision/Actor, Vision/Governance |
| Track evolution: when items were created, changed, what confidence was and is now | CR5/Time, Matrix 4 Vision/Time |

**Out of scope:**
- Other phases (Requirements, Design, etc.) — those are future slices (CR1: phases available, not mandatory)
- Pipeline flow mechanics (how work moves between phases) — next layer of requirements (CR7: transitions recognized, not enforced)
- Detailed task management, scheduling, assignment
- Code, builds, deploys, testing
- Auth, pricing, multi-user

---

## What the user works with

> Source: CR2, Matrix 2 Vision row

At the Vision phase, these are the 7 types of things (CR2) and what they look like:

| Thing | At Vision | Matrix 2 cell |
|---|---|---|
| **Thinking about** | Ideas, directions, product concepts, brainstorms. The raw material. | Vision/Thinking about |
| **Decided** | Vision statement, product direction, what's in/out, kill decisions. Committed positions with rationale and rejected alternatives. | Vision/Decided |
| **Need to figure out** | Open questions, gaps in understanding, unknowns to explore. | Vision/Need to figure out |
| **Need to do** | Threads to file, docs to write, counterfactuals to run. Light — not implementation tasks. | Vision/Need to do |
| **Relationships** | Concepts inform each other, ideas connect to decisions, gaps block crystallization. | Vision/Relationships |
| **State** | Tentative → crystallized (or killed). Confidence shifting dynamically based on evidence. | Vision/State |
| **Produced** | Vision docs, one-pager, feature map, brainstorm artifacts. | Vision/Produced |

Items can be any of the first four types. Relationships connect items. State is a property of items. Produced items are artifacts attached to items.

---

## What the user can do

### See

> Source: CR3/See, Matrix 1 Vision/See — "See the emerging picture — ideas, connections, gaps, 'where are we?' at a glance. Status and confidence on everything."

The user can see:

- All items in the current project's Vision work, with their types, states, and confidence
- How items relate to each other — what informs what, what blocks what, what's connected
- Where the gaps are — open questions without answers, low-confidence items, stale items
- The overall picture — is the vision crystallizing or still scattered?
- Evolution — how items and their confidence changed over time (CR5/Time, Matrix 4 Vision/Time)

The system must answer "where are we?" in under 10 seconds for a project with 50+ items.

### Change

> Source: CR3/Change, Matrix 1 Vision/Change — "Create ideas, capture decisions, connect concepts, synthesize into consolidated artifacts."

The user can:

- Create items of any type (idea, decision, question, thread)
- Connect items to each other (this idea informs that decision, this gap blocks that direction)
- Edit items: change content, type, confidence, status
- Synthesize: consolidate multiple items into a single artifact (e.g., scattered ideas → vision statement) — also Matrix 3 Vision/Synthesis
- Mark decisions: crystallize (committed) or kill (rejected, with rationale)
- Capture rejected alternatives alongside decisions — also Matrix 3 Vision/Capture

Creating an item takes under 3 seconds. No wizards. Type and go.

### Evaluate

> Source: CR3/Evaluate, Matrix 1 Vision/Evaluate — "Pressure test claims (counterfactuals), update confidence dynamically via logic and discovery, crystallize or kill directions."

The user can:

- Run counterfactuals against any item or cluster of items ("what if this isn't true?") — also Matrix 3 Vision/Evaluation
- Update confidence on any item (untested → low → moderate → high, or back down) — also CR5/Confidence, Matrix 4 Vision/Confidence
- See which items have been pressure-tested and which haven't
- Crystallize items (mark as committed, high confidence)
- Kill items (mark as rejected, with evidence/rationale)

The AI participates in evaluation proactively (CR6 — see below).

### Execute

> Source: CR3/Execute, Matrix 1 Vision/Execute — "Research — web search, reference gathering. Prototyping/spiking if needed. Minimal."

Minimal at Vision. The user can:

- Trigger research: web search, reference gathering
- Capture research results as items or artifacts
- Request a prototype or spike (rare — flags as "need to do")

---

## How the AI behaves

> Source: CR6 (proactive AI, background sub-agent, knobs), Matrix 4 Vision/Actor — "Human steers, AI expands AND challenges. Background sub-agent evaluates continuously." Matrix 4 Vision/Governance — "AI should be proactive about challenges and counterfactuals, subject to human knobs."

The AI is a participant, not just a tool. At the Vision phase:

- **Expands:** Proposes connections the user hasn't made, suggests related ideas, fills in gaps
- **Challenges:** Runs counterfactuals unprompted, questions weak confidence, pushes back on assumptions — CR6/Challenging
- **Surfaces:** Flags stale items (haven't been touched or tested), notices drift, raises observations — CR6/Background sub-agent
- **Synthesizes:** Offers to consolidate scattered items into coherent artifacts — Matrix 3 Vision/Synthesis
- **Recognizes transitions:** Detects when the vision is crystallizing enough to move toward requirements — CR7 (artifact-based, confidence-based, behavioral, decided, emergent signals)

Proactivity is governed by:
- **3-mode dial** (gate/flag/skip) — controls human involvement per AI action — CR5/Governance, Matrix 4 Vision/Governance
- **Knobs** — control AI behavior parameters: challenge aggressiveness, proactivity frequency, escalation thresholds — CR6/Knobs

The background sub-agent observes continuously and surfaces findings through the flag mechanism. The user is notified, not blocked. — CR6/Background sub-agent

---

## Processes at Vision

> Source: CR4, Matrix 3 Vision row

| Process | Behavior | Matrix 3 cell |
|---|---|---|
| **Discovery** | Dominant. Exploring the space, Q&A, brainstorming. The system supports asking and answering questions. | Vision/Discovery: "Dominant — exploring the space, Q&A, brainstorming" |
| **Evaluation** | High. Counterfactuals, confidence checks, pressure testing. Background sub-agent runs these continuously. | Vision/Evaluation: "High — counterfactuals, confidence checks, pressure testing" |
| **Synthesis** | High. Distilling scattered ideas into consolidated docs. The system supports selecting multiple items and producing a synthesis. | Vision/Synthesis: "High — distilling scattered ideas into consolidated docs" |
| **Capture** | Continuous. Recording decisions, rationale, rejected alternatives as they happen. Should be as low-friction as possible. | Vision/Capture: "Continuous — recording decisions, rationale, rejected alternatives" |
| **Decomposition** | Light. Breaking big concepts into sub-topics, not executable tasks. | Vision/Decomposition: "Light — breaking big concepts into sub-topics" |

---

## Cross-cutting lenses

> Source: CR5, Matrix 4 Vision row

| Lens | At Vision | Matrix 4 cell |
|---|---|---|
| **Confidence** | Visible on every item. Dynamic — updates based on evidence. Central to the evaluation process. | Vision/Confidence: "Central — dynamic, driven by logic and discovery via search" |
| **Governance** | Human steers heavily at Vision. Gate is the default for decisions. AI proposes, human approves. Knobs control challenge behavior. | Vision/Governance: "Mostly gate/flag — human steers heavily, AI proposes. Knobs control challenge aggressiveness, proactivity frequency, escalation thresholds" |
| **Scope** | Project-level and feature-level. Not task-level. | Vision/Scope: "Project-level and feature-level. Not task-level yet." |
| **Actor** | Human-AI pair. Both create items. AI's contributions are marked. | Vision/Actor: "Human steers, AI expands AND challenges. Background sub-agent evaluates continuously." |
| **Time** | When items were created, changed, evaluated. Evolution trail visible. | Vision/Time: "When ideas emerged, when they changed. Evolution trail matters." |

---

## What NOT to build

- Phase-specific behavior for Requirements, Design, Planning, etc. — CR1: phases are future slices
- Pipeline mechanics (how things flow between phases) — not yet defined as requirements
- Task assignment, scheduling, due dates — Matrix 3 Vision/Building: "Minimal"
- Code integration, git, file watching — Matrix 3 Vision/Deploying: "None"
- Multi-user, auth, permissions
- Policy configuration UI (policies exist, UI comes later) — CR5/Governance: governance exists, surface comes later
- Session management UI
- Import/export
- Templates or wizards

---

## Success criteria

| Criterion | Source |
|---|---|
| Can create items of all 4 active types (idea, decision, question, thread) in under 3 seconds each | CR2, CR3/Change, Matrix 1 Vision/Change |
| Can connect any two items and see the connection visually | CR2 thing #5 (Relationships), Matrix 2 Vision/Relationships |
| Can see all items with their type, confidence, and status at a glance | CR3/See, Matrix 1 Vision/See |
| Can update confidence on any item | CR5/Confidence, Matrix 4 Vision/Confidence |
| Can crystallize or kill an item with rationale captured | CR3/Evaluate, Matrix 1 Vision/Evaluate, Matrix 2 Vision/State |
| Can synthesize multiple items into a consolidated artifact | CR3/Change, Matrix 1 Vision/Change, Matrix 3 Vision/Synthesis |
| Can run a counterfactual against an item and capture the result | CR3/Evaluate, Matrix 3 Vision/Evaluation |
| AI proactively surfaces at least one observation or challenge per 5 minutes of active work | CR6, Matrix 4 Vision/Actor |
| Can see the evolution trail of any item (what changed, when, confidence history) | CR5/Time, Matrix 4 Vision/Time |
| System answers "where are we?" for a 50-item project in under 10 seconds | CR3/See, Matrix 1 Vision/See |
| A Vision session done inside Forge produces better outcomes than the same session in scattered markdown + chat — fewer missed connections, faster drift detection, confidence tracked instead of forgotten, gaps surfaced that would have been invisible, and the experience is delightful enough that you'd choose it over the alternative | Acid test — all of the above |
| Forge's own Vision work (sessions 5-7) would have been improved by this component — the agent's drift to design (session 7) caught earlier, the phase transition (session 6) recognized sooner, the missing verb (Execute) surfaced before round 10 of counterfactuals | Acid test — real data validation |
