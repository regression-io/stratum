# Discovery: Canonical Use Case Matrix

**Date:** 2026-02-11
**Parent:** [Level 2 Brainstorm](level-2-brainstorm.md)
**Related:** [Use Cases (original)](../../use-cases.md)
**Status:** In progress — expanding beyond the seed persona

---

## Purpose

The original use cases (UC-1 through UC-9) are all from one persona: solo dev + AI managing a monorepo. To test whether the model works for different users — and whether different users have different primaries — we need a broader set.

This doc is a living matrix. Rows are use cases. Columns are axes we want to test against. Columns will be added as we identify them.

---

## Personas

| ID | Persona | Context | Primary engagement | ICP? |
|----|---------|---------|-------------------|------|
| P1 | Solo dev + AI | Building with Claude Code, manages own work | What + How | **YES** |
| P2 | Founder / product thinker | Exploring a product idea, pre-team or early team | Why + What | **YES** |
| P3 | Team lead | Coordinating multiple people and/or agents | What + visibility | Guardrail |
| P4 | Executor dev | Received a task, needs to deliver | What + How (narrow) | Guardrail |
| P5 | Researcher / analyst | Pure knowledge work, no code | Why-factual + knowledge layer | Guardrail |
| P6 | Exec / stakeholder | Needs visibility, doesn't build | What (read-only) | Guardrail |

---

## Use Case Matrix

| ID | Use case | Persona | Primary dimension | Discovery mode | Confidence matters? |
|----|----------|---------|-------------------|---------------|-------------------|
| UC-1 | Where are we? (orientation) | P1, P3, P6 | What | — | Yes — need to see soft spots |
| UC-2 | What should this session work on? | P1, P4 | What + How | — | Yes — don't assign low-confidence work blindly |
| UC-3 | Parallel agents went off the rails | P1, P3 | How (constraints) | — | No — execution problem |
| UC-4 | Breaking down a big initiative | P1, P2, P3 | What | Integration | Yes — decomposition quality |
| UC-5 | Cross-project feature tracking | P1, P3 | What | — | Moderate |
| UC-6 | Product planning loop | P1, P2 | What + Why | Brainstorm + Integration | Yes — ideas vs validated |
| UC-7 | Resuming after context loss | P1, P4 | What | — | No — state recovery |
| UC-8 | Deliberation and decision-making | P1, P2, P5 | Why-factual | Brainstorm + Integration | Yes — decision quality |
| UC-9 | Planning session (multi-topic) | P1, P2 | What + Why | All modes | Yes |
| UC-10 | Exploring a new product idea | P2 | Why + What | Brainstorm + Research | Yes — conviction vs evidence |
| UC-11 | Due diligence / research | P5, P2 | Why-factual | Research + Integration | Yes — evidence quality |
| UC-12 | Onboarding to an existing project | P4, P1 | What + How | Research | Yes — understanding vs assumption |
| UC-13 | Status report for stakeholders | P3, P6 | What | — | Yes — report confidence, not just status |
| UC-14 | Pivoting / killing a direction | P2, P1 | Why-factual | Integration | Yes — evidence for/against |
| UC-15 | Prototyping to learn | P1, P2, P5 | How | Prototyping | Yes — prototype result is the update |
| UC-16 | Reviewing someone else's work | P3, P6 | What + Why-factual | — | Yes — is it actually done? |
| UC-17 | Coordinating a team sprint | P3 | What + How | — | Moderate |
| UC-18 | Writing a spec from discovery | P1, P2 | What | Integration | Yes — crystallization point |

---

## ICP focus

**P1 (Solo dev + AI)** and **P2 (Founder/PM)** are the two primary ICPs. Design for them. Other personas are guardrails — check that nothing we decide blocks them later.

### Key insight: P1 and P2 are modes, not people

A solo dev becomes P2 when they enter discovery (brainstorming product direction). A founder becomes P1 when they prototype. They're not different users — they're **different modes of the same person.** The persona shifts when the phase shifts.

The difference is **depth.** Each person has a home turf:

| | Home turf (deep) | Away turf (shallow) |
|---|---|---|
| P1 (Dev) | Implementation, verification, How | Discovery, Why, business reasoning |
| P2 (Founder/PM) | Discovery, requirements, Why | Implementation, How, technical detail |

Both enter every mode. But away from home turf, they need more support from the AI:
- A dev brainstorming product direction needs the AI to help articulate Why and challenge assumptions
- A founder prototyping needs the AI to handle the How and surface technical constraints

**Implication for Forge:** Don't serve two personas — serve one person who moves between modes, and adjust AI support based on where they're deep vs. shallow. This connects to [Onboarding Inputs](onboarding-inputs.md) — Forge needs to know the user's home turf to calibrate.

### P1 + P2 use cases (the active set)

| ID | Use case | Persona |
|----|----------|---------|
| UC-1 | Where are we? (orientation) | P1, P2 |
| UC-2 | What should this session work on? | P1 |
| UC-3 | Parallel agents went off the rails | P1 |
| UC-4 | Breaking down a big initiative | P1, P2 |
| UC-5 | Cross-project feature tracking | P1 |
| UC-6 | Product planning loop | P1, P2 |
| UC-7 | Resuming after context loss | P1 |
| UC-8 | Deliberation and decision-making | P1, P2 |
| UC-9 | Planning session (multi-topic) | P1, P2 |
| UC-10 | Exploring a new product idea | P2 |
| UC-11 | Due diligence / research | P2 |
| UC-12 | Onboarding to an existing project | P1 |
| UC-14 | Pivoting / killing a direction | P2, P1 |
| UC-15 | Prototyping to learn | P1, P2 |
| UC-18 | Writing a spec from discovery | P1, P2 |

15 use cases. Stress-test the model against these.

## Observations so far

*To be filled as we analyze the matrix.*

---

## Open questions

- Are the personas right? Missing any?
- Are the use cases comprehensive enough to test the model?
- What other column axes should we add?
