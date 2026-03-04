# Core Requirements Counterfactuals

**Date:** 2026-02-11
**Parent:** [Core Requirements](core-requirements.md)
**Status:** Complete — decisions made, requirements updated

---

## CF1: "Seven phases assumes software delivery"

**Claim tested:** CR1 phase list is the right set.
**Counter:** Research or strategy projects don't need implementation/release. Phases assume software.
**Decision:** Not an issue. Users use what applies. Phases are available, not mandatory. Updated CR1.

## CF2: "The things list is missing actual outputs"

**Claim tested:** CR2 six things cover what users work with.
**Counter:** All six are thinking artifacts. No "what's been delivered" — code, test results, deployed services.
**Decision:** Add 7th thing: "what's been produced." Updated CR2.

## CF3: "Three verbs isn't enough — where's DO?"

**Claim tested:** CR3 three verbs cover all user actions.
**Counter:** See/change/evaluate are about managing things in Compose. "Build me X" requires execution — directing agents, assigning work, monitoring.
**Decision:** Add 4th verb: "Execute." Updated CR3.

## CF4: "The composition is too abstract to build from"

**Claim tested:** The composition model is actionable.
**Counter:** Thousands of combinations. An engineer can't build from this.
**Decision:** Not an issue. The composition is a requirements framework that constrains design space, not an engineering spec. Engineers get prioritized slices. No change needed.

## CF5: "The processes aren't truly orthogonal"

**Claim tested:** CR4 processes are independent.
**Counter:** Discovery involves evaluation. Evaluation involves synthesis. They interleave deeply.
**Decision:** Rename from "orthogonal" to "universal." How processes relate to each other is ontology/design, not requirements. The requirement is: they're supported everywhere. Updated CR4.

## CF6: "Phase transitions — recognized by whom?"

**Claim tested:** CR7 says transitions are recognized but doesn't say by whom.
**Counter:** Needs a mechanism and an actor.
**Decision:** The AI does the recognizing. This surfaced a bigger gap: the AI must be proactive — reach out, ask questions, surface observations, not just respond when prompted. New CR6 added.

## CF7: "Governance at every decision point is overwhelming"

**Claim tested:** CR5 (was CR6) governance at every decision point.
**Counter:** Hundreds of dials per session is unusable.
**Decision:** Already resolved by inheritance model. Project defaults cascade down, phases override, items are exceptions. How specific = design question. Updated CR5.

## CF8: "No human-AI interaction model"

**Claim tested:** CR1-CR7 cover the product.
**Counter:** No description of how human and AI collaborate — who initiates, how AI surfaces things, how human steers.
**Decision:** Follow Claude Code model + proactivity. Folded into new CR6.

## CF9: "Phase affinity is descriptive, not prescriptive"

**Claim tested:** CR5 (old) phase affinity is a requirement.
**Counter:** The system doesn't behave differently based on affinity. It's descriptive.
**Decision:** Phase affinity is LLM guidance context, not a system behavior. Dropped as standalone requirement, noted in CR4 as context.

## CF10: "The pipeline isn't in the requirements"

**Claim tested:** CR1-CR7 capture the product.
**Counter:** The vision is "Build me X" — a specific pipeline. These requirements describe the space but not the path through it.
**Decision:** Not missing, just not reached yet. We went deep into the structural model. The pipeline (how things flow) is the next layer. Noted in "Not yet addressed" section.

---

## Summary

| CF | Action taken |
|---|---|
| CF1 (software phases) | Noted — phases are available, not mandatory |
| CF2 (missing outputs) | Added 7th thing: what's been produced |
| CF3 (missing DO) | Added 4th verb: Execute |
| CF4 (too abstract) | No change — framework by design |
| CF5 (not orthogonal) | Renamed to "universal," relationships are design |
| CF6 (recognized by whom) | New CR6: AI must be proactive |
| CF7 (governance granularity) | Updated CR5: inheritance model |
| CF8 (interaction model) | Folded into CR6: Claude Code model + proactivity |
| CF9 (phase affinity) | Dropped as requirement, kept as LLM context in CR4 |
| CF10 (no pipeline) | Next layer, noted as "not yet addressed" |
