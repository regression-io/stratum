# Discovery Insight: Confidence as Bayesian Update

**Date:** 2026-02-11
**Parent:** [Level 2 Brainstorm](level-2-brainstorm.md)
**Related:** [False Crystallization](false-crystallization.md), [Discovery Modes](discovery-modes.md)
**Status:** Tentative

---

## The core idea

Confidence is orthogonal to status. Every Work item at every phase has it. It's not a field you set — it's **computed from evidence**.

The model is qualitative Bayesian: prior belief, updated by evidence, producing a posterior. No exact probabilities — but the reasoning pattern is principled.

---

## The Bayesian frame

### Prior

Every item starts with a prior — initial confidence based on how it was created:

| Origin | Prior |
|--------|-------|
| Brainstormed in conversation | Weak — an idea, nothing more |
| Based on research / prior art | Moderate — evidence exists but hasn't been applied here |
| Derived from a prototype | Strong — we built something and saw what happened |
| Copied from a working system | Strong — proven elsewhere, untested here |
| Assigned without context | Unknown — no basis to judge |

The prior is never zero (we thought of it for a reason) and never certain (nothing is until tested).

### Evidence updates

Each piece of evidence shifts confidence up or down:

| Evidence type | Direction | Strength |
|---------------|-----------|----------|
| Challenge with no answer | ↓ weakens | Mild — exposed a gap |
| Challenge with satisfying answer | ↑ strengthens | Moderate — survived pressure |
| Research supports it | ↑ strengthens | Moderate — external validation |
| Research contradicts it | ↓ weakens | Moderate to strong |
| Prototype confirms | ↑ strengthens | Strong — built and held |
| Prototype breaks | ↓ weakens | Strong — built and failed |
| Downstream item fails because of it | ↓ weakens | Strong — real-world failure traced back |
| Used in practice without issues | ↑ strengthens | Strong — time-tested |
| Context changed (new info, pivot) | ↓ weakens | Variable — may invalidate prior evidence |

### Posterior

Current confidence = prior + all evidence updates. It's the system's best guess right now, always provisional, always updatable.

Key properties:
- **Never final.** New evidence can always arrive. "Validated" is just "high posterior, lots of supporting evidence."
- **Conflicting evidence is natural.** One test passes, another fails. The posterior reflects the net.
- **Regression is just a negative update.** Not a special state — just new evidence that lowers confidence.

---

## What confidence means by phase

The *kind* of evidence that matters shifts, but the mechanic is the same:

| Phase | Key evidence that raises confidence |
|-------|-------------------------------------|
| Discovery | Idea challenged and answer held. Research supports it. |
| Requirements | Stakeholders agreed. Use cases survived review. |
| Design | Decision tested against implementation constraints. |
| Planning | Breakdown matched actual work when attempted. |
| Implementation | Tests pass. Code works. |
| Verification | Edge cases covered. Acceptance criteria met. |

Same question everywhere: **did this survive pressure from below?**

---

## Roll-up

A parent's confidence is derived from its children's posteriors. Not a simple min — a distribution:

```
Initiative: "Forge bootstrap"              posterior: low
├── Feature: "Terminal embed"              posterior: high
│   prior: moderate (known patterns)
│   evidence: +built, +works, +survives crashes
│
├── Feature: "Discovery model"             posterior: low
│   prior: weak (brainstormed)
│   evidence: +challenged, +partially held, -gaps found in validation exercise
│   ├── "Work primitive definition"        posterior: low (written, untested)
│   ├── "Working dimensions"               posterior: moderate (discussed, challenged, partially held)
│   └── "Confidence model"                 posterior: weak (meta — defining itself)
│
└── Feature: "Persistence"                 posterior: very low
    prior: weak (plan written from brainstorm)
    evidence: none
```

The parent's posterior aggregates children. One very-low child pulls the whole thing down. You see at a glance where the soft spots are.

### Aggregation

Not settled, but candidates:
- **Weighted min** — weakest child dominates, but strong children provide some lift
- **Distribution summary** — show the spread, not just a single number (3 high, 1 low, 1 unknown)
- **Human override** — "I know this is solid" sets a floor, but the system shows the computed value alongside

---

## How discovery modes feed the model

Each [discovery mode](discovery-modes.md) contributes different evidence:

| Mode | Evidence produced | Typical update strength |
|------|------------------|------------------------|
| Brainstorming | Ideas, framings, questions | Creates items at weak prior. No update — just genesis. |
| Research | Facts, prior art, external data | Moderate updates — supports or contradicts |
| Prototyping | What worked, what broke | Strong updates — hardest evidence |
| Integration | Synthesis, coherence assessment | Variable — may raise or lower based on fit |

Brainstorming generates. Research and prototyping update. Integration assesses.

---

## Connection to false crystallization

[False crystallization](false-crystallization.md) is the Bayesian version of: **high-structure, low-posterior.** Something that looks done (clean doc, tables, consistent wording) but has a weak prior and no evidence updates. The formatting creates an illusion of confidence.

The Bayesian frame makes this detectable: if an item has no evidence updates, its posterior equals its prior — which for brainstormed items is weak, regardless of how polished the doc looks.

---

## Open questions

- How is this surfaced in the UI? A number? A color? A sparkline of evidence over time?
- Does the AI auto-attach evidence updates, or does someone have to log them?
- Can the AI compute posteriors from the evidence trail, or is it always qualitative?
- How granular? Per Work item? Per artifact? Per claim within an artifact?
- Does the user ever see the word "Bayesian"? (Probably not — the logic is invisible, the output is a confidence indicator.)
