# Session 7: Requirements Emerge

**Date:** 2026-02-11
**Previous:** [Session 6: The Vision Inversion](2026-02-11-session-6-vision-inversion.md)

---

## What happened

Picked up from Session 6's vision crystallization and moved into requirements. The session produced a composition model (CR1-CR7) through a series of corrections, expansions, and pressure tests. The human kept pulling the agent back from solving to defining.

### Part 1: Rails and dogfooding

The human raised a thread: people don't follow structured processes linearly. They jump back and forth across levels. Compose needs to maintain structure in the background and steer back. Then two refinements:

1. **The rails are for the AI, not the human.** The AI uses them to know what's fixed vs transitory. The human works fluidly.
2. **Phase transitions are amorphous.** Not sharp events — the AI should recognize when the bridge has been crossed, by output artifacts or confidence shifts.

We acknowledged we're building with hindsight, not dogfooding. The human's take: "dogfooding is nice to have, having requirements from lived experience is better."

### Part 2: Three corrections on level

The agent's first attempt at requirements included APIs, layouts, schemas. All HOW. The human corrected: "requirements are purely what, and some why."

Second attempt: 25 sub-requirements without framing. The human corrected: "start with 1 thing and expand."

Third attempt: "see where we are" as the one thing. The human corrected: that's one cross-cutting feature. The real decomposition is verbs + noun.

### Part 3: Verbs, things, and the ontology

Three verbs emerged: see, change, evaluate. The WHAT led to defining items, connections, and state. The human recognized this as a basic ontology. Pressure-tested twice (8 counterfactuals each round). Processes added as fourth concept. Then the human corrected: the ontology is design, not requirements. The requirements-level WHAT is the things users work with, not the internal data model.

### Part 4: Lenses and phase dynamics

The human asked about the full scope of things — what about building, testing, deploying, auth, pricing? This led to classifying levels. The agent's first attempt separated "Think & Decide" as a level. The human corrected: that's the orthogonal process applied at each level. The levels are the taxonomy phases we already have.

Nine orthogonal lenses emerged: phase, thing, verb, process, confidence, scope, actor, time, governance. Phase dynamics clarified: not a DAG, more like quantum mechanics — macro linear, granular non-linear. Phase is a probability distribution, not a property of individual items.

### Part 5: Core requirements

The composition model became the requirements themselves: phases × things × verbs × processes × lenses. Seven core requirements (CR1-CR7). Pressure-tested with 10 counterfactuals:

- Added 4th verb: **Execute** (direct agents, assign work, monitor, collect results)
- Added 7th thing: **What's been produced** (outputs, artifacts, deliverables)
- Added CR6: **AI must be proactive** (initiate, not just respond)
- Renamed "orthogonal" to "universal" processes
- Dropped phase affinity as a requirement (it's LLM context)
- Clarified governance inheritance (project defaults cascade down)
- Noted pipeline as next layer of requirements

---

## What we built

### New files
- `docs/requirements/core-requirements.md` — CR1-CR7: the composition model
- `docs/requirements/core-requirements-counterfactuals.md` — 10 counterfactuals with decisions
- `docs/requirements/needs.md` — Foundation: four verbs, seven things, nine lenses, phase dynamics
- `docs/requirements/ontology-counterfactuals.md` — Two rounds against the ontology
- `docs/requirements/detailed-requirements.md` — Early thread (premature, parked)
- `docs/requirements/threads.md` — Implementation threads parked for later
- `docs/requirements/scope.md` — Early thread (premature, parked)

### Modified files
- `docs/requirements/README.md` — Index with status markers
- `docs/discovery/discovery-process/rails-architecture.md` — "Rails are for the AI" section, phase transition recognition, background sub-agent updated
- `CLAUDE.md` — Current state updated to requirements phase, 4 primitives, doc structure expanded
- `docs/journal/README.md` — This entry

---

## What we learned

1. **Requirements are what + why, never how.** The agent kept slipping into implementation details. The instinct to solve is the enemy of the instinct to define.

2. **Start from one thing, not twenty-five.** Top-down decomposition: one need → core verbs → the nouns → then granularity.

3. **The ontology is design, not requirements.** Items/processes/connections/state describe internal representation. Requirements describe what users work with. The agent kept crossing the boundary.

4. **The composition model IS the requirement.** Phases × things × verbs × processes × lenses. The framework constrains the design space. Features are slices through it.

5. **"Orthogonal" means "universal," not "independent."** Processes interleave. They're universal across phases, not independent of each other.

6. **Execute is a verb.** The core promise is "Build me X." See/change/evaluate are about managing — execute is about doing. Compose directs agents; the agents do.

7. **Phase affinity is LLM context, not a system behavior.** "You're in planning, so decomposition is likely" is guidance for the AI, not a product requirement.

8. **The AI must be proactive.** Not just respond when asked — reach out, surface observations, ask questions. This is a core behavioral requirement.

9. **Pressure testing works.** Three rounds of counterfactuals (ontology twice, core requirements once) caught real gaps: missing verb, missing thing type, missing interaction model, naming confusion, premature requirements.

10. **The agent drifts upward.** Repeatedly jumped from requirements to design/implementation (ontology, scope, architecture threads). The human had to steer back each time. This is exactly the behavior R6 is designed to catch.

### Part 6: Matrices and the waterfall check

11. **Matrices make the pipeline concrete.** Four matrices (phases × verbs/things/processes/lenses) with phases as the dominant axis. Filling in one row at a time turns abstract composition into specific requirements. The Vision row was first because we have lived data.

12. **The agent was doing waterfall.** Three sessions of pure definition, zero building since session 3. The human caught it: "what would we do differently if we wanted to define/build and iterate?" The answer: pick a slice, build it, use it, iterate. We don't need the full pipeline defined to build a graph visualization.

13. **Graph visualization comes from the See column.** Matrix 1 / See across all phases IS the graph visualization requirement. Vision row is the first slice.

14. **Confidence is dynamic, not just "tentative."** Driven by logic and discovery via search. Evidence updates confidence continuously, not at checkpoints.

15. **Knobs are a separate control surface.** The human raised that governance needs more than conversation steering and the 3-mode dial. Configurable parameters: proactivity frequency, challenge aggressiveness, escalation thresholds. Knobs govern AI behavior across decisions; the dial governs human involvement per decision.

16. **The sub-agent chain.** Proactive AI (CR6) → challenging as behavioral mode → background sub-agent as mechanism → knobs as control surface. Three layers that connect requirements to architecture.

17. **The AI should challenge, not just expand.** At the Vision phase, the actor isn't just "human steers, AI expands." It's "human steers, AI expands AND challenges." The challenging role requires the sub-agent to run continuously in the background.

---

## Open threads

- [ ] Pipeline requirements — fill in remaining matrix rows (requirements, design, planning, implementation, verification, release)
- [ ] Waterfall vs iterative — do we fill all rows before building, or build after enough rows are defined?
- [ ] Graph visualization slice — the See column is the first buildable piece. Define it explicitly?
- [ ] Ontology → design — items/processes/connections/state parked for design phase
- [ ] Implementation threads — "ghetto" KG, etc. parked for design/implementation
- [ ] Knobs design — what parameters, what ranges, what UI surface?
- [ ] Sub-agent architecture — how does it observe, what does it run, how does it surface findings?

---

*Ten counterfactuals, four verbs, seven things, nine lenses, seven core requirements. Four matrices, Vision row filled. The agent did waterfall for three sessions. The human caught it. Knobs control the AI. The sub-agent challenges in the background. Rails are for the AI.*
