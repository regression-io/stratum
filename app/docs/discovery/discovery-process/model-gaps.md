# Model Gaps: Surfaced from Use Case Walkthrough

**Date:** 2026-02-11
**Parent:** [Level 2 Brainstorm](level-2-brainstorm.md)
**Source:** [Use Case Walkthrough](use-case-walkthrough.md)
**Status:** Open — needs resolution or conscious deferral

---

## Gap 1: Priority

**Affected use cases:** UC-2 (what should this session work on?)

**The problem:** Work items have status and dependencies, but not priority. When multiple items are unblocked, how does the user (or AI) know what matters most?

**Options:**
- A. Explicit priority field (high/medium/low, or numeric)
- B. Computed from signals (confidence, dependencies, age, human attention)
- C. Human sets it, AI suggests it
- D. Not needed — unblocked + dependency order is enough

**Considerations:**
- Priority is subjective and changes constantly
- Explicit priority fields rot (everything becomes "high")
- Computed priority might be more useful but harder to trust
- The 3-mode dial applies: gate (human sets), flag (AI suggests), skip (AI decides)

**Resolution:** *unresolved*

---

## Gap 2: Kill / Pivot Mechanics

**Affected use cases:** UC-10 (exploring a new idea), UC-14 (pivoting/killing a direction)

**The problem:** How does Compose represent "this direction is dead"? And how does it distinguish "parked because we got busy" from "killed because the evidence says no"?

**Options:**
- A. Status: killed (new status alongside parked, blocked, complete)
- B. A decision Work item (type: decision, outcome: kill) with rationale and evidence
- C. Both — status marks it dead, decision captures why
- D. Just use parked + a label or tag

**Considerations:**
- A kill has a reason. Parking doesn't necessarily. They're different.
- A kill decision is itself a piece of Why-factual — it's evidence about what doesn't work
- Downstream items need to know: "this was killed" ≠ "this is paused"
- The confidence model: a killed direction's confidence dropped to zero (or near). The kill is the final negative update.

**Resolution:** *unresolved*

---

## Gap 3: Distillation (extracting from conversations)

**Affected use cases:** UC-8 (deliberation), UC-9 (planning session), UC-12 (onboarding)

**The problem:** Decisions, insights, and action items happen in conversations but only exist in Compose if someone manually creates Work items. Most get lost.

**Options:**
- A. Real-time extraction during conversation (AI creates Work items as you talk)
- B. Post-session review (AI proposes items after session ends, human approves)
- C. Human-triggered ("capture this as a decision")
- D. All three, progressive — C now, B next, A later

**Considerations:**
- This is a feature gap, not a model gap. The data model supports it; the extraction doesn't exist yet.
- Real-time extraction (A) is intrusive and error-prone
- Post-session review (B) misses context but is safer
- Human-triggered (C) is lowest effort to build but highest effort to use
- The 3-mode dial applies: gate (human captures manually), flag (AI proposes, human approves), skip (AI captures autonomously)

**Resolution:** *unresolved — likely phased (D), but needs design*

---

## Gap 4: Evidence Granularity

**Affected use cases:** UC-7 (context recovery), UC-11 (due diligence/research)

**The problem:** How fine-grained is evidence? A research session produces many small claims ("competitor X raised $50M", "market growing 20% YoY"). An implementation session produces partial progress ("step 3 of 7 done"). What level does evidence live at?

**Options:**
- A. Per Work item only (coarse — "this item has evidence")
- B. Per artifact (medium — evidence lives in documents)
- C. Per claim (fine — individual assertions with confidence)
- D. Flexible — the system supports all three, user picks grain

**Considerations:**
- Fine grain (C) is most useful but highest overhead
- Coarse grain (A) is easiest but loses detail
- Research needs finer grain than implementation
- The Bayesian model works at any grain — each claim can have its own posterior
- But tracking confidence per-claim is probably too much for v1

**Resolution:** *unresolved — likely B (per artifact) for v1, with C as aspiration*

---

## Gap 5: Phase Transition Triggers

**Affected use cases:** UC-18 (writing a spec from discovery)

**The problem:** What signals "time to move from discovery to requirements" or "time to write a spec"? The crystallization model describes what happens at transitions but not what triggers them.

**Reframe (from Session 5 continued):** The premise may be wrong. Phases aren't sequential stages you pass through — they're levels of concreteness. A "vision" like "we need to track things" isn't requirements. Requirements emerge from Q&A decomposition of the goal, with decisions along the way. That decomposition IS discovery. So the question isn't "what triggers the transition from discovery to requirements" — it's "what triggers the discovery process that produces requirements from a goal?"

This makes the gap both simpler and deeper:
- **Simpler:** transitions aren't discrete events to trigger. They're gradual crystallization as discovery does its work.
- **Deeper:** the real question is what signals that a discovery process at a given level has produced enough concrete output to be useful.

**Options:**
- A. Human decision only ("I'm done exploring")
- B. AI suggests based on signals (confidence plateau, questions answered, loop producing diminishing returns)
- C. Explicit gate — user must mark a phase as "ready to transition"
- D. No formal transition — it just happens when someone starts doing the next phase's work
- E. Reframe entirely: transitions aren't events, they're the natural output of discovery. The question is confidence — "are the outputs concrete enough to act on?"

**Considerations:**
- In practice, transitions are messy. You don't finish discovery and start requirements — they overlap.
- Option D reflects reality but gives no visibility
- Option B is useful but hard to define "confidence plateau"
- Option E connects directly to the Bayesian confidence model — the posterior on discovery outputs is the transition signal
- The 3-mode dial applies: gate (human decides when), flag (AI suggests transition), skip (AI transitions autonomously)
- We experienced this in this session: "let's stop brainstorming and validate" was a human-triggered transition

**Resolution:** *partially resolved — reframed as confidence on discovery outputs, not discrete trigger events. Needs mechanics.*

---

## Gap 6: Direction as a Concept

**Affected use cases:** UC-14 (pivoting/killing)

**The problem:** A "direction" is a cluster of Work items sharing an assumption. "We're building a CLI tool" is a direction. "We're building a web app" is a different direction. But "direction" isn't a first-class concept in the model. It's implicit in the hierarchy (the parent initiative) or in a decision — but you can't point at it directly.

**Options:**
- A. Direction = parent Work item (initiative or feature level)
- B. Direction = a decision Work item whose outcome sets the course
- C. Direction = a tag/label that groups related items
- D. Not needed — hierarchy + decisions cover it

**Considerations:**
- A pivot kills a direction, not a single item. You need to be able to say "all of this is invalidated."
- Option A works if the hierarchy maps to directions cleanly. But sometimes a direction spans multiple branches.
- Option B captures the "why" (the decision that set the direction) but not the "what" (all the items following it)
- Maybe it's A + B: the decision `informs` the initiative, and killing the decision invalidates the initiative
- This might be a non-issue in practice — you just kill the parent and its children go stale

**Resolution:** *unresolved — possibly already handled by hierarchy + decision + `informs`*

---

## Gap 7: Prototype vs Implementation

**Affected use cases:** UC-15 (prototyping to learn)

**The problem:** A prototype is throwaway. Implementation ships. Both involve building. How does Compose distinguish them?

**Options:**
- A. Label only (type: poc vs type: task)
- B. Structural — prototypes live in a discovery-phase parent, implementation in an implementation-phase parent
- C. A flag on the Work item ("throwaway: true")
- D. Not needed — the user knows, the label is enough

**Considerations:**
- The distinction matters for confidence: prototype evidence is "we learned X" not "this code is ready"
- Prototype artifacts (code) should not be confused with production artifacts
- In practice, prototypes sometimes become implementation ("it worked, let's keep it"). The boundary is fuzzy.
- Option B is the most natural — the phase of the parent tells you the intent

**Resolution:** *unresolved — likely B (phase inheritance) + A (label) is sufficient*

---

## Triage

Rough priority based on how much they affect the two ICPs:

| Gap | Impact | Urgency |
|-----|--------|---------|
| 2. Kill/pivot | High — P2 core workflow | Resolve before spec |
| 5. Phase transitions | High — affects crystallization model | Resolve before spec |
| 3. Distillation | High — but it's a feature, can phase it | Design approach, defer build |
| 1. Priority | Medium — workaround exists (human picks) | Can defer |
| 6. Direction | Medium — may already be solved by hierarchy | Test with examples |
| 4. Evidence granularity | Low for v1 — per-artifact is fine | Defer |
| 7. Prototype vs implementation | Low — label + phase is probably enough | Defer |
