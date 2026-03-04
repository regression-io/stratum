# Meta-Trace: Session 5 Discovery Process

**Date:** 2026-02-11
**Parent:** [Level 2 Brainstorm](level-2-brainstorm.md)
**Purpose:** Record the actual process of this discovery session as it happens. This is both the story and the test data for how discovery works.

---

## Why this matters

We're doing discovery about discovery. This conversation IS the process we're trying to define. If we don't capture the meta layer — what moves were made, what triggered what, how insights emerged — we lose the best test case we have.

This is the distillation problem (Gap 3) in action: knowledge generated in conversation, only partially captured as artifacts, process itself evaporating.

---

## The trace

### 1. Orient
**Move:** "where are we?"
**What happened:** Reviewed handoff doc and journal. Established current state — Level 1 dimensions resolved, persistence parked, discovery active.
**Output:** Shared understanding of starting point.

### 2. Steer
**Move:** "park 0.4, flag discovery level 2 in roadmap"
**What happened:** Human redirected focus. Persistence deferred, discovery elevated to active focus.
**Output:** Roadmap updated, CLAUDE.md updated.

### 3. Frame the territory
**Move:** "what do we need to think about to flesh this out?"
**What happened:** Agent proposed 5 clusters (What, How, Why-factual, knowledge layer, primitives mapping). Written to Level 2 brainstorm doc.
**Output:** [level-2-brainstorm.md](level-2-brainstorm.md)

### 4. Gather
**Move:** "what is all the wording around What?"
**What happened:** Agent searched all docs, compiled every reference to the What dimension. Presented comprehensive inventory.
**Output:** Full inventory of What across all docs.
**Human feedback:** "too long, simpler and more direct." → Agent learned to be more concise.

### 5. Challenge → Insight (false crystallization)
**Move:** "can we be sure? mark it tentative"
**What happened:** Human challenged the assumption that Work is well-defined. Just because it's written in tables doesn't mean it's validated.
**Trigger:** Agent presented the definition confidently. Human tested the confidence.
**Output:** [false-crystallization.md](false-crystallization.md) — structure ≠ confidence.

### 6. Reflect
**Move:** "did we learn something just now about the process?"
**What happened:** Human prompted meta-reflection. The false crystallization moment was itself evidence about how discovery works — you need validation pressure to distinguish real from cosmetic crystallization.
**Output:** Validation pressure concept added to false crystallization doc.

### 7. Side branch → Insight (confidence is universal)
**Move:** "is it really not possible to use 'tentative' for implementation?"
**What happened:** Human saw that tentative isn't discovery-specific. "Built but not tested" is the same pattern. Confidence is orthogonal to status at every phase.
**Output:** Confidence qualifier recognized as universal, not phase-specific.

### 8. Deepen (confidence roll-up)
**Move:** "confidence should roll up from the bottom"
**What happened:** Human defined the roll-up mechanic: parent can't exceed least-confident child. Each level is provisional until the nuts and bolts are tested. Confidence is computed, not set.
**Output:** [confidence-model.md](confidence-model.md)

### 9. Reframe (Bayesian)
**Move:** "maybe adapt a Bayesian logic flow?"
**What happened:** Human suggested the framing. Agent mapped it: prior (origin) + evidence updates = posterior. Qualitative, not quantitative.
**Output:** Confidence model rewritten with Bayesian frame.

### 10. Question (different primaries?)
**Move:** "can there be different primaries for different users?"
**What happened:** Asked whether the model works for different user types. Led to reviewing use case coverage.
**Output:** Recognized the use case set was too narrow (solo dev only).

### 11. Expand (canonical use cases)
**Move:** "we need a canonical use case list now"
**What happened:** Created use case matrix with 6 personas and 18 use cases.
**Output:** [use-case-matrix.md](use-case-matrix.md)

### 12. Focus (ICPs)
**Move:** "focus on solo dev + AI first... wait, also founder/PM"
**What happened:** Human narrowed to two ICPs. Then broadened slightly to include P2.
**Output:** P1 + P2 as primary ICPs, others as guardrails.

### 13. Insight (personas are modes, not people)
**Move:** "what are the commonalities/differences?"
**What happened:** Analysis revealed P1 and P2 aren't different users — they're modes of the same person. The difference is depth (home turf vs away turf).
**Output:** ICP insight added to matrix, home turf added to onboarding inputs.

### 14. Test (use case walkthrough)
**Move:** "walk me through the 15 use cases"
**What happened:** Agent walked all 15 through the model. Model held structurally. 7 gaps surfaced.
**Output:** [use-case-walkthrough.md](use-case-walkthrough.md)

### 15. Contextualize
**Move:** "gaps should be in context of features"
**What happened:** Human pointed out gaps floating in isolation don't land. Need feature definitions first.
**Output:** [feature-map.md](feature-map.md) — 8 features, gaps mapped to features.

### 16. Reflect (meta-trace)
**Move:** "have we been collecting what we're doing as a meta layer?"
**What happened:** Human noticed we're not capturing the process itself — only the outputs. The conversation IS the test case for discovery, and the process is evaporating.
**Output:** This document.

### 17. Challenge (what is the Work item?)
**Move:** "what is the Work item?" / "Discovery leads to work yes?"
**What happened:** Tried to model this session as a Work item — didn't fit. Status lifecycle wrong, units only identifiable retrospectively. Realized discovery isn't Work — it's the process that produces Work.
**Output:** [discovery-as-primitive.md](discovery-as-primitive.md) — 4th primitive added.

### 18. Crystallize (expand primitives)
**Move:** "expand our primitives, it's fine"
**What happened:** Human approved expanding from 3 primitives to 4. Discovery joins Work, Policy, Session.
**Output:** Feature map updated, primitive table expanded.

### 19. Challenge (tracking is orthogonal)
**Move:** "tracking is orthogonal to primitives isn't it"
**What happened:** Human saw that tracking, confidence, and visibility are cross-cutting — they apply to all primitives, not just Work. Features reorganized around verbs (what the user does), not primitives.
**Output:** Feature map restructured: F1 Discover, F2 Capture Knowledge, F3 Distill, F4 Plan & Decompose, F5 Execute with Agents, F6 See Everything. Cross-cutting capabilities pulled out.

### 20. Deepen (distill includes decisions)
**Move:** "distill includes decision making yes?"
**What happened:** F3 expanded from "extract from transcripts" to the full convergence engine: extract → assess → decide. Decisions are the output of distillation. Kill decisions are counter-evidence distilled into a committed kill.
**Output:** F3 renamed to "Distill & Decide." Kill/pivot gap (Gap 2) moved into F3.

### 21b. Interaction surface analysis
**Move:** "what does the user actually touch?"
**What happened:** Approached the untouched clusters (How, Why, Knowledge) from the user's perspective. Found primitives split into objects (Work, Policy) and processes (Discovery, Session). Dimensions are facets of one interaction on a Work item. Clusters 2-4 are layers: configuration → queryable knowledge → indexing engine.
**Output:** Level 2 brainstorm updated with interaction surface section.

### 22. Challenge (counterfactuals against interaction surface analysis)
**Move:** "re-evaluate with critical lenses, think of counterfactuals"
**What happened:** Generated 6 counterfactuals against the interaction surface conclusions. Several bit hard: dimensions exist independently of Work items (scope levels), Discovery needs to be an object not just a process (tracking paradox), How might dissolve into What + Why, temporal dimension missing. Lowered confidence on "facets of one interaction" claim. Raised new questions.
**Output:** Level 2 brainstorm updated. Counterfactuals surfaced. Confidence model used for the first time in practice — prior → challenge → revised posterior.
**Meta:** Human pointed out that the counterfactual exercise itself was the Bayesian confidence process in action. First real use of the confidence model. Evidence update on the model itself.

### 23. Crystallize (confidence evaluation process)
**Move:** "write out clean analyses"
**What happened:** Wrote confidence-evaluation-process.md covering evaluation mechanics, timing triggers, and process inference. Also captured counterfactuals as standalone doc.
**Output:** Two docs: confidence-evaluation-process.md, counterfactuals-session-6.md

### 24. Reframe (vision statement)
**Move:** "do we have our product vision statement?"
**What happened:** Agent proposed vision centered on "making direction durable." Human corrected: the original idea was "Build me X and it figures out the rest." The structured implementation pipeline is the core product. Discovery/brainstorming is an optional on-ramp. What/How/Why/Confidence are reasoning infrastructure, not user-facing goals. Vision statement written. Feature map rebalanced: F3/F4/F5 are core pipeline, F1 is on-ramp.
**Output:** vision-statement.md, feature-map.md updated, CLAUDE.md updated.
**Meta:** Agent had the vision inverted — centered on knowledge capture instead of implementation pipeline. Human correction reshaped the entire priority structure.

### 25. Pressure test (vision counterfactuals)
**Move:** "the vision statement hasn't been pressure-tested"
**What happened:** Ran 6 counterfactuals against the vision tagline. All landed to some degree. Resolved through feature design (F0, variable entry points) rather than changing the vision. Vision statement updated with pressure test results.
**Output:** vision-statement.md updated with counterfactuals and resolutions.

### 26. Gather (loose threads)
**Move:** "there are a lot of loose threads, put them in the right places"
**What happened:** Human surfaced threads: knowledge management as connectors, knowledge capture as cross-cutting, orthogonal capabilities inventory, rails as core design question, Claude Code as precedent, hard/soft limits, constraint weight classes, memory/retrieval as connector choice.
**Output:** rails-architecture.md (new), feature-map.md cross-cutting capabilities expanded to 8, F0 open questions updated.

### 27. Crystallize (one-pager)
**Move:** "do we have our product vision statement?" → "write a one-pager"
**What happened:** The scattered discovery docs needed consolidation. Wrote compose-one-pager.md — the full vision on one page: what it is, the problem, how it works, features, architecture, who it's for, what it's NOT.
**Output:** docs/compose-one-pager.md

### 28. Phase transition (vision → requirements)
**Move:** "how do we get there from here? is the vision enough?"
**What happened:** Human asked if the vision is enough to move forward. Agent proposed options for formalization. Human chose one-pager (already done). Then asked: "what do we need right now?" — a UI to do what we've been doing but visually. The discussion shifted from abstract model to concrete buildable piece.
**Trigger:** The one-pager's existence. Having a crystallized vision doc made it obvious that the next step isn't more vision refinement — it's requirements for the first thing to build.
**Output:** docs/requirements/ created. scope.md drafted with R1-R5.
**Meta:** This is the phase transition we've been theorizing about (Gap 5). It wasn't triggered by a signal or threshold. It was triggered by having a crystallized artifact — the one-pager made the vision feel "done enough." The human's instinct said "stop refining, start building."

### 29. Process inference (we forgot to track)
**Move:** "are we tracking this transition and capturing process inferences?"
**What happened:** We weren't. We went through the exact phase transition we'd been theorizing about — vision → requirements — and didn't notice or record it. The human caught the gap.
**Meta:** Evidence for the confidence-evaluation-process doc's finding that "processes are inferred, not designed." We designed the transition tracking in theory. In practice, we forgot to do it when the transition actually happened. This is exactly why capture needs to be automatic, not manual.

---

## Process inferences from the phase transition

The vision → requirements transition happened naturally. What can we observe?

1. **The trigger was a crystallized artifact.** Not a confidence threshold. Not a checklist. The one-pager's existence made it feel like the vision was "done enough." Crystallization IS the trigger — when you can write a clean summary, the phase is ready to transition.

2. **The human initiated it, not the AI.** The agent would have kept refining. The human said "ok, what do we build?" Every phase transition so far has been human-initiated. The AI's default is to keep going.

3. **The transition was gradual, not discrete.** We were already asking requirements-like questions ("what does the UI need?") before formally entering the requirements phase. The boundary is fuzzy.

4. **We immediately forgot our own process.** Despite spending hours designing the meta-trace and the confidence evaluation process, we didn't track the most important process event of the session — the phase transition itself. Manual tracking fails at the moment it matters most. This is the strongest argument yet for automated capture.

5. **"Is the vision enough?" is the wrong question.** The right question is "can I write a one-pager?" If yes, you have enough to move on. If not, you're still in vision. The one-pager is the transition test.

---

## Discovery verbs used in this session

| Verb | Count | Key moments |
|------|-------|-------------|
| Orient | 1 | Start of session |
| Steer | 3 | Park 0.4, focus ICPs, "pull back" |
| Gather | 3 | What wording, use cases, feature inventory |
| Challenge | 4 | "Can we be sure?", "is tentative universal?", "different primaries?", "gaps need context" |
| Qualify | 2 | Mark tentative, mark untested |
| Reflect | 3 | "Did we learn something?", personas insight, meta-trace |
| Gate | 2 | "Beyond my depth", "simpler" |
| Test | 2 | Validation exercise, use case walkthrough |
| Crystallize | 8+ | Every doc write |

Challenge and crystallize dominate. This session was about testing ideas and capturing them.

### 21. Challenge (lifecycle phases aren't sequential stages)
**Move:** "we need to track things => not requirements yet. it's a vision or directive or goal."
**What happened:** Agent assumed "where are we" feature could start at requirements. Human corrected twice: first that design exists at every level, then that "we need to track things" is a vision/goal, not requirements. Requirements emerge from Q&A decomposition with decisions along the way. That decomposition process IS discovery.
**Output:** Discovery reframed as the mechanism between ALL phases, not just a first phase. Phases reframed as levels of concreteness, not sequential stages. Gap 5 partially resolved. [discovery-as-primitive.md](discovery-as-primitive.md) updated.

---

## Patterns observed

- **Human steers, agent expands.** Human sets direction, challenges, gates. Agent gathers, structures, writes.
- **Insights emerge from challenges.** False crystallization came from "can we be sure?" Confidence roll-up came from "is tentative universal?" Personas-as-modes came from "what are the differences?" Discovery-as-connective-tissue came from "that's a goal, not requirements."
- **Side branches produce the best insights.** The confidence model came from a "side question." The Bayesian frame was an aside. The deepest ideas arrived sideways.
- **The human slows things down.** "Too deep, pull back." "Simpler." "Can we be sure?" "That's not requirements yet." Every slowdown produced something valuable.
- **Corrections reshape the model.** Move 21 came from the human correcting a wrong assumption about lifecycle phases. The correction didn't just fix the mistake — it deepened the entire primitive definition.
- **Docs accumulate as crystallization points.** Each insight gets its own doc. The Level 2 brainstorm is the index. The hierarchy grows naturally.
- **The process is non-linear but progressive.** We zigzagged, but each zig added something. No wasted moves — even the too-deep detour taught us about gating.

---

*Living document — updated as the session continues.*
