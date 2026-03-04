# Discovery: Onboarding Inputs

**Date:** 2026-02-11
**Parent:** [Level 2 Brainstorm](level-2-brainstorm.md)
**Status:** Collection point — throw ideas here, structure later

---

## What is this?

Level 1 identified that some inputs are "onboarding context" — things Compose needs to know to be useful, but that aren't working dimensions the user engages with day-to-day. This doc collects those as they surface.

Onboarding isn't a form or a wizard. It's the minimal set of things Compose needs to calibrate itself to the user.

---

## Candidates

### 1. Structured vs. free-flow preference

**Source:** Level 2 discussion on discovery verbs.

Some users want Compose to help structure their thinking during discovery (surface the verbs, prompt for challenges, suggest next moves). Others want free-flow conversation and only want structure when they ask for it.

This is subjective and personal. Compose can't infer it — it has to ask.

Possible spectrum: `structured ←→ free-flow`

Connects to: the 3-mode dial. A structured user might want more gates. A free-flow user might want more skips. This preference could set default policy levels.

### 2. Personal Why / motivation

**Source:** Level 1 dimension debate.

"I'm a founder with a vision" vs. "I'm a dev doing what I was told" vs. "I'm an exec with a mandate." These starting conditions affect how Compose should interact — whether to challenge direction, accept it, or help articulate it.

Privacy-sensitive. Optional. But useful for calibration.

### 3. Who context

**Source:** Level 1 dimension debate.

Solo dev + AI? Team? Role? This affects what features matter (assignees, permissions, collaboration) and what's noise.

### 4. Home turf (depth profile)

**Source:** Level 2 discussion on ICP personas.

Where is the user deep vs. shallow? A dev is deep in implementation and How, shallow in business reasoning and Why. A founder is the opposite. Both enter every mode — but away from home turf, they need more AI support.

This calibrates where the AI leans in (expand, explain, challenge) vs. steps back (the user knows more than the AI here).

Possible spectrum: `technical ←→ business` (or more nuanced — depth per lifecycle phase)

### 5. Starting conditions

**Source:** Level 1.

Greenfield? Existing codebase? Inherited project? Migration? This affects what templates, lifecycle defaults, and AI suggestions are relevant.

---

## Open questions

- What's the onboarding UX? Conversation? Form? Progressive (ask when relevant)?
- How much can Compose infer vs. needs to ask?
- Can onboarding inputs change over time? (User starts solo, grows a team)
- Where do these get stored?
