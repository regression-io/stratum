# Use Case Walkthrough: Model Stress Test

**Date:** 2026-02-11
**Parent:** [Use Case Matrix](use-case-matrix.md)
**Purpose:** Walk each ICP use case through the model. Does it fit? What breaks?

**Model under test:** Work primitive + 3 dimensions (What/How/Why-factual) + Bayesian confidence + discovery modes

---

## UC-1: Where are we? (P1, P2)

**The scenario:** Open Forge after a break. Need project state in seconds.

**What the model needs to show:**
- Work hierarchy with status
- What changed since last session
- Where the soft spots are

**Does it fit?** Yes — this is pure What (hierarchy + state). The confidence model adds value here: not just "what's the status" but "how confident are we in each piece." A dashboard showing status + confidence heat map gives you orientation *and* tells you where to worry.

**Gap?** None for the model. This is a UI/dashboard problem, not a data model problem.

---

## UC-2: What should this session work on? (P1)

**The scenario:** Starting a Claude Code session. Need to pick a task and get context.

**What the model needs to show:**
- Unblocked work items
- Priority / readiness
- Context briefing for the chosen item

**Does it fit?** Yes. What (state, dependencies) + How (scope, approach) + Session (assignment). Confidence adds: don't assign work whose upstream has low confidence — you might be building on sand.

**Gap?** Priority isn't in the model. Work items have status and dependencies, but not explicit priority. Is priority a property of What, or is it computed (unblocked + high confidence + human says "this matters")?

---

## UC-3: Parallel agents went off the rails (P1)

**The scenario:** Multiple agents guessed instead of reading. Need guardrails.

**What the model needs:**
- Scope boundaries (what files to read/touch)
- Acceptance criteria (tests must pass)
- Completion gate (can't mark done until criteria met)

**Does it fit?** Yes. This is How (constraints, scope) + Policy (gate on completion). Confidence is less relevant here — this is about enforcement, not belief.

**Gap?** None for the model. This is a Policy + Session execution problem.

---

## UC-4: Breaking down a big initiative (P1, P2)

**The scenario:** Multi-week effort, needs decomposition into features and tasks.

**What the model needs:**
- Hierarchy (parent → children)
- Dependencies between children
- AI-proposed breakdown, human-reviewed

**Does it fit?** Yes for the structure. But decomposition is interesting — the AI proposes children, each with a confidence level. A fresh decomposition is all untested. The human reviewing it is the first challenge (moving items from unexamined to challenged).

**P2 difference:** A founder decomposing a product idea decomposes differently — into discovery/research items, not implementation tasks. The hierarchy is the same, but the *type* of children differs. Model handles this via labels (type: brainstorm vs type: task).

**Gap?** None structural. But the AI needs to know depth profile (P1 vs P2 mode) to propose the right kind of decomposition.

---

## UC-5: Cross-project feature tracking (P1)

**The scenario:** One feature spans 5 repos. Need to see progress across all of them.

**What the model needs:**
- Hierarchy (feature → per-project tasks)
- Scope (each task scoped to a project)
- Dependencies (ordering between projects)

**Does it fit?** Yes. Pure What — hierarchy, scope, dependencies, status. Confidence adds: is the API contract task "complete + validated" or "complete + untested"? If untested, the downstream SDK task is building on shaky ground.

**Gap?** Scope as "which project" needs to be concrete — file paths, repo references. The model says "scope boundaries" but doesn't specify format. Minor — design detail, not model problem.

---

## UC-6: Product planning loop (P1, P2)

**The scenario:** Brainstorm → use cases → PRD → design, with feedback loops.

**What the model needs:**
- Work items for each planning activity
- Artifacts attached to each
- `informs` dependencies between them (brainstorm informs PRD, PRD informs design)
- Loopback when a decision changes upstream

**Does it fit?** Mostly. The forward flow works — hierarchy + artifacts + `informs`. But the feedback loop is the hard part. When a design decision invalidates part of the PRD, what happens mechanically?

With confidence model: the PRD's confidence gets a negative update ("downstream design work contradicted assumption X"). The system surfaces it. The human decides whether to loop back.

**P2 focus:** This is P2's core use case. A founder lives here. The model needs to be *good* at this, not just adequate.

**Gap?** Loopback mechanics are still underspecified. The `informs` dependency tells you the relationship exists. The confidence model tells you something changed. But the "surface it and prompt for action" part is AI behavior, not data model.

---

## UC-7: Resuming after context loss (P1)

**The scenario:** Session crashed or hit context limit. Need to pick up cleanly.

**What the model needs:**
- Evidence log (what was done before the crash)
- Work item state (what's finished, what's not)
- Context briefing for new session

**Does it fit?** Yes. What (state, evidence) + Session (context). Confidence is minor here — this is about state recovery.

**Gap?** Evidence granularity. "Files changed" is coarse. "Step 3 of 7 in the implementation plan was completed, step 4 was in progress" is useful. The model supports evidence but doesn't specify grain.

---

## UC-8: Deliberation and decision-making (P1, P2)

**The scenario:** Design question arises. Need to discuss, record, decide, and link.

**What the model needs:**
- Decision as a Work item (label: decision)
- Artifacts: question, arguments, rationale, rejected alternatives
- `informs` dependency to downstream items
- Conversation distillation to catch undocumented decisions

**Does it fit?** Yes — this is where `informs` and Why-factual earn their keep. The decision Work item IS a Why-factual artifact. Its confidence starts at unexamined (question raised), moves through challenged (discussed), evidenced (arguments weighed), validated (decided and downstream work confirms it held).

**P2 focus:** Founders make big decisions with less evidence. The confidence model is especially useful here — "we decided X, but our confidence is low because we had no prototype." That's real and useful to see.

**Gap?** Conversation distillation (extracting decisions from transcripts) is a later-phase feature. Without it, decisions only exist if someone manually creates the Work item. In practice, many decisions happen in conversation and never get captured.

---

## UC-9: Planning session — multi-topic (P1, P2)

**The scenario:** Session covers brainstorming, evaluation, decisions — topics emerge organically.

**What the model needs:**
- Session as a container
- Child Work items created in real-time as topics emerge
- Artifacts on each child
- Cross-references (`informs`) between them
- Distillation at the end to catch what was missed

**Does it fit?** This is the hardest use case for the model. Topics emerge non-linearly. Some things said early connect to things said later. The tree structure imposes hierarchy on something that was actually a web.

Confidence model helps: everything produced in this session starts as unexamined. Some items got challenged during the session itself (our "can we be sure?" moment). Most didn't.

**Gap?** Real-time Work item creation during a conversation is aspirational. Right now, artifacts are created manually (we write docs). The gap isn't the data model — it's the *extraction* problem. Who creates the Work items during a fast-moving conversation?

---

## UC-10: Exploring a new product idea (P2)

**The scenario:** Founder has a hunch. Wants to explore whether it's real.

**What the model needs:**
- A loose container (Work item, label: brainstorm or discovery)
- Artifacts accumulate as exploration progresses
- Confidence starts very low, updates as evidence comes in
- At some point, either crystallizes into a direction or gets killed

**Does it fit?** The container fits. The confidence model is especially valuable here — the founder can SEE their idea going from "hunch" to "researched" to "prototyped." Or see it staying at "hunch" after weeks, which is a signal.

**Gap?** Kill decisions. How does "this idea is dead" work? Status → parked? A new Work item (type: decision, outcome: kill)? The model supports both but hasn't specified which. Also — how does Forge distinguish "parked because we got busy" from "killed because the evidence says no"?

---

## UC-11: Due diligence / research (P2)

**The scenario:** Founder researching a market, technology, or competitive landscape before committing.

**What the model needs:**
- Research as a Work item (label: research or evaluation)
- Artifacts: findings, data, analysis
- Confidence on claims (this competitor has X market share — how sure?)
- Synthesis that rolls findings into a decision

**Does it fit?** Yes. This is the research discovery mode feeding the confidence model. Each finding is evidence. The synthesis is integration mode. The output is either "proceed" or "kill/pivot" — which is a decision Work item.

**Gap?** Granularity of evidence. Research produces many small claims, not one big artifact. "Competitor X raised $50M" is one data point. "The market is growing 20% YoY" is another. Are these separate Work items? Artifacts? Evidence entries? The model doesn't specify how fine-grained evidence goes.

---

## UC-12: Onboarding to an existing project (P1)

**The scenario:** Dev joins (or returns to) a project. Needs to understand what exists and why.

**What the model needs:**
- Work hierarchy showing what's been done and what's in progress
- Why-factual: why were things decided this way?
- Confidence: which parts of the architecture are solid vs. provisional?
- How: what's the approach, what are the constraints?

**Does it fit?** Yes — this is a read-heavy use case. The model's value is that all three dimensions are visible: What (the work), How (the approach), Why (the reasoning). Without Why-factual, onboarding is "here's the code, figure it out." With it, onboarding is "here's the code, here's why it's this way, here's what we're unsure about."

**Gap?** This assumes Why-factual was captured during development. If decisions happened in conversations and were never extracted, the Why layer is empty. Same distillation gap as UC-8 and UC-9.

---

## UC-14: Pivoting / killing a direction (P2, P1)

**The scenario:** Evidence accumulates that the current direction is wrong. Need to pivot or kill.

**What the model needs:**
- Confidence on the current direction (and it's dropping)
- Evidence trail showing what changed
- Kill decision as a Work item with rationale
- Downstream impact: what goes stale if we pivot?

**Does it fit?** This is where the Bayesian model shines. The direction's posterior has been declining — research contradicts, prototype broke, assumption invalidated. The evidence trail makes the pivot *justified*, not emotional. And `informs` dependencies show what downstream work is affected.

**Gap?** "Direction" isn't a first-class concept. It's an implicit property of a cluster of Work items. You can't point at a single item and say "this is the direction" — it's the parent initiative, or a decision, or just a shared assumption. How does Forge represent "the thing we're pivoting away from"?

---

## UC-15: Prototyping to learn (P1, P2)

**The scenario:** Build a throwaway to answer a question. Not shipping it — learning from it.

**What the model needs:**
- Prototype as a Work item (label: poc or prototype)
- The question it's answering (linked via `informs` to the parent decision/brainstorm)
- Evidence: what we learned (not the code — the insight)
- Confidence update on the parent question

**Does it fit?** Yes. Prototyping is a discovery mode that produces strong evidence. The Work item is the container. The evidence (what we learned) is the artifact. The confidence update flows up via `informs` to whatever question the prototype was answering.

**Gap?** The throwaway nature. How does Forge distinguish "this is a prototype, don't ship it" from "this is implementation"? Label alone? Or is there something structural?

---

## UC-18: Writing a spec from discovery (P1, P2)

**The scenario:** Discovery produced enough understanding. Time to crystallize into a spec.

**What the model needs:**
- Discovery Work items as inputs (brainstorms, research, decisions)
- Spec as a new Work item (label: spec)
- `informs` links from discovery items to spec
- Confidence on the spec derived from confidence on its inputs

**Does it fit?** Yes. This IS crystallization — the phase transition the model describes. The spec's initial confidence is derived from its inputs' confidence. If the discovery items are well-evidenced, the spec starts with moderate confidence. If they're unexamined, the spec inherits that weakness.

**Gap?** The transition itself. What triggers "time to write a spec"? Is it the human saying "enough discovery"? The AI noticing confidence has plateaued? The model doesn't describe transition triggers.

---

## Summary: what works and what doesn't

### Works well
- Hierarchy, status, dependencies — solid for all 15 use cases
- `informs` dependency — earns its keep in UC-6, UC-8, UC-9, UC-14, UC-18
- Confidence model — adds value in 12 of 15 use cases
- Labels (type + phase) — enough to differentiate brainstorms from tasks from decisions
- Everything-is-Work — holds up, even for deliberation and research

### Recurring gaps

| Gap | Use cases affected | Nature |
|-----|-------------------|--------|
| **Distillation** — extracting decisions/insights from conversations | UC-8, UC-9, UC-12 | Feature gap, not model gap. The model supports it; the extraction doesn't exist yet. |
| **Priority** — what's most important, not just what's unblocked | UC-2 | Missing property. Computed or explicit? |
| **Kill/pivot mechanics** — representing "this direction is dead" | UC-10, UC-14 | Underspecified. Status parked? Decision Work item? Both? |
| **Evidence granularity** — how fine-grained is evidence? | UC-7, UC-11 | Design detail. Per-item? Per-claim? |
| **Phase transition triggers** — what signals "move from discovery to spec"? | UC-18 | Unresolved. Human decision? AI suggestion? Confidence threshold? |
| **Direction as concept** — a cluster of work sharing an assumption | UC-14 | Not first-class. Implicit in hierarchy but not explicit. |
| **Prototype vs implementation** — structural difference or just a label? | UC-15 | Design detail. |
