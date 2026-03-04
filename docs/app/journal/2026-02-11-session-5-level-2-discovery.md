# Session 5: The Discovery About Discovery

**Date:** 2026-02-11
**Phase:** Discovery Level 2 (Phase 0.3.5)
**Participants:** Human + Claude Code agent

---

## What happened

No code was written. No bugs were fixed. No features were built. This was the first pure discovery session — a conversation about what Forge's conceptual model actually is, tested against real work we've done.

We came in with Level 1 settled: three working dimensions (What, How, Why-factual) and a knowledge layer underneath. The task was to go one level deeper. What we got was a series of insights that reshaped the model.

### The false crystallization moment

It started with a simple question: "what is all the wording around the What dimension?" We compiled every reference across all docs. The Work primitive had clean sub-constructs, tables, consistent definitions. It looked solid.

The human asked: "can we be sure?"

No. We couldn't. The definition was written, not validated. Clean tables don't mean tested assumptions. This was the first real insight of the session: **structure ≠ confidence**. We coined "false crystallization" — something that looks hardened because it's formatted, not because it's survived pressure.

### Confidence became its own model

That led to a cascade. If something can be "complete but untested," then confidence is separate from status. The human pushed further: confidence isn't discovery-specific. "Built but not tested" (implementation) is the same pattern as "written but not validated" (discovery). Confidence is orthogonal to status. It applies everywhere.

Then: confidence rolls up. A parent can't be more confident than its least-confident child. Each level is provisional — you only get hard confidence at the bottom, where a test either passed or didn't.

The human suggested Bayesian framing. Prior (based on how something was created) + evidence updates (challenges, research, prototypes, failures) = posterior (current confidence). Qualitative, not quantitative — no exact probabilities, but the reasoning pattern is principled. We rewrote the confidence model around this.

### Personas collapsed into modes

We needed broader use cases to test the model, so we expanded from 9 (all solo-dev) to 18 across 6 personas. Then the human asked about the two primary ICPs — solo dev and founder/PM. What are their differences?

The analysis revealed they're not different people. They're different modes of the same person. A developer brainstorming product direction is operating as a founder. A founder prototyping is operating as a developer. The difference is depth — each has a home turf where they're deep, and away turf where they need more AI support.

### Discovery became a primitive

The biggest structural change came from trying to answer: "what is the Work item for this session?"

We couldn't answer it. This discovery session didn't fit the Work primitive. Status lifecycle assumes known endpoints. Children were emergent, not planned. The unit of work wasn't identifiable until after the fact.

The resolution: discovery isn't Work. Discovery is the process that produces Work. You go in with a question, you come out with trackable items. The process itself isn't a Work item — what it produces becomes Work items.

So we expanded from 3 primitives to 4: Discovery, Work, Policy, Session. Discovery sits upstream of Work. Distillation is the bridge — the crystallization machine that turns discovery outputs into Work items.

### Features restructured around verbs

With tracking recognized as cross-cutting (it applies to all 4 primitives, not just Work), we restructured the feature map around what the user *does*: Discover, Capture Knowledge, Distill & Decide, Plan & Decompose, Execute with Agents, See Everything.

F3 (Distill & Decide) turned out to be bigger than extraction. Decisions are the output of distillation — you distill enough evidence into a committed position. Kill decisions are what you get when counter-evidence wins. The full arc: extract → assess → decide.

### The meta-trace

Midway through the session, the human noticed we weren't capturing the process itself. We were tracking outputs (docs, insights) but not the sequence of moves that produced them. Since this conversation IS the process we're trying to define, losing it meant losing our best test data.

We started a meta-trace — a real-time record of each move (orient, steer, gather, challenge, qualify, reflect, gate, test, crystallize). 20 moves recorded by session end. The trace itself became evidence about how discovery works: challenges and crystallization dominated, side branches produced the deepest insights, and every time the human slowed things down, something valuable emerged.

## What we built

No code. 14 discovery documents:

| File | What it captures |
|------|-----------------|
| `level-2-brainstorm.md` | Level 2 index — 5 clusters, insights linked |
| `false-crystallization.md` | Structure ≠ confidence |
| `confidence-model.md` | Bayesian confidence: prior + evidence = posterior |
| `discovery-verbs.md` | AI-internal vocabulary (orient, steer, challenge, etc.) |
| `discovery-modes.md` | 4 modes: brainstorm, research, prototype, integration |
| `onboarding-inputs.md` | Calibration inputs bucket (5 candidates) |
| `validation-exercise.md` | Model tested against terminal embed, crash resilience, this session |
| `use-case-matrix.md` | 18 use cases, 6 personas, 2 ICPs |
| `use-case-walkthrough.md` | 15 ICP use cases tested against model, 7 gaps |
| `model-gaps.md` | 7 gaps with options and triage |
| `feature-map.md` | 6 features, 4 primitives, cross-cutting capabilities |
| `discovery-as-primitive.md` | 4th primitive definition |
| `session-5-meta-trace.md` | 20-move process trace |
| `crystallization-review.md` | 3-pass honest confidence assessment |

Plus: updated roadmap, updated discovery-process README, new canvas rule.

## What we learned

1. **False crystallization is real and pervasive.** Clean docs ≠ tested ideas. We caught ourselves assuming the Work primitive was solid because it had tables. Most of our definitions are written but unvalidated.

2. **Confidence and status are independent axes.** "Complete" doesn't mean "confident." This applies at every phase — discovery through release. A universal property, not a phase-specific one.

3. **The Bayesian framing earns its keep.** Not for exact numbers, but for the reasoning pattern: every item has a prior, every piece of evidence updates it, the posterior is always provisional. It makes false crystallization detectable: no evidence updates = posterior equals prior = low, regardless of formatting.

4. **Discovery isn't Work — it's upstream of Work.** You can't identify the unit of work during discovery. It only becomes clear after the fact. Discovery produces Work items; it isn't one.

5. **ICPs are modes, not people.** A solo dev in discovery mode is a product thinker. A founder prototyping is a developer. The difference is depth, not identity. Design for one person who shifts modes.

6. **Side branches produce the best insights.** The confidence model came from a "side question." The Bayesian frame was an aside. The deepest ideas arrived sideways, not from the planned clusters.

7. **Human slowdowns are the most productive moments.** "Can we be sure?" "You're beyond my depth, pull back." "Simpler." Every time the human slowed the pace, something valuable crystallized.

## Open threads

- [ ] Three Level 2 clusters untouched: How, Why-factual, Knowledge layer
- [ ] Discovery as primitive vs. mode of Session — unresolved, needs pressure
- [ ] F3 (Distill & Decide) has 3 gaps and no design beyond "extract → assess → decide"
- [ ] CLAUDE.md still says 3 primitives — needs update
- [ ] Bayesian confidence may be "vibes with a fancy name" — needs teeth
- [ ] Use cases UC-10 through UC-18 are invented, not from real experience
- [ ] Feature flow might be too linear for how work actually happens

---

*The session that produced no code and changed everything. Discovery is the process that produces work — and this session proved it by being one.*
