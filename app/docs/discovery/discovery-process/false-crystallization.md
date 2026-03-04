# Discovery Insight: False Crystallization

**Date:** 2026-02-11
**Parent:** [Level 2 Brainstorm](level-2-brainstorm.md)
**Status:** Tentative — just surfaced, needs pressure-testing

---

## What happened

We reviewed the Work primitive definition. It has clean sub-constructs, tables, properties — it *looks* crystallized. When asked "is What well-defined?" the answer was "yes, here's all the wording." When challenged with "can we be sure?" — no, we can't. We wrote it, we haven't used it.

## The insight

**Structure ≠ confidence.** A thing can look crystallized — clean definition, tables, consistent wording across docs — while still being untested. Writing it down isn't the test. Using it is.

The crystallization model says "each phase transition crystallizes — what was fluid becomes fixed." But it's missing the concept of what *tests* the crystallization. Without that test, you get **false crystallization** — docs that look solid but aren't.

## What this means for Compose

Discovery needs a concept we're tentatively calling **validation pressure** — the thing that distinguishes "we wrote it down" from "we tried it and it held."

Examples of validation pressure:
- Building against the definition and finding it doesn't fit
- Tracking real work with the primitives and hitting friction
- Someone (human or AI) challenging an assumption and finding it hollow
- A downstream phase discovering the upstream definition was incomplete

Without validation pressure, crystallization is cosmetic. The definition looks done because it's formatted, not because it's true.

## Implications for the crystallization model

The original model:
```
discovery → requirements → design → planning → implementation → verification → release
```

Each transition "crystallizes." But now we see two kinds:
- **Tested crystallization** — the definition survived pressure. It held when used.
- **Untested crystallization** — the definition was written but not challenged. It might be right, might not.

Compose should be able to distinguish these. A Work item's status might say "complete" but its crystallization might be untested. That's a different kind of confidence than "complete and validated."

## Update: tentative is universal, not discovery-specific

"Built but not tested" (implementation) is the same pattern as "written but not validated" (discovery). Tentative is a **confidence qualifier on any status**, not a phase-specific concept.

Examples across phases:
- Discovery: insight surfaced but unchallenged
- Design: decision made but untested against implementation
- Implementation: built but not tested
- Verification: tests pass but edge cases unexplored

This means the status lifecycle has a gap. "Complete" doesn't distinguish between "finished" and "finished and pressure-tested." The model needs a confidence dimension alongside status.

## Open questions

- Is validation pressure something Compose tracks explicitly, or is it just good practice?
- Does this map to the existing verification phase, or is it something that happens *within* every phase?
- How does the AI know the difference between tested and untested crystallization?
- Is this related to Why-factual? (The evidence chain that justifies a definition.)
- What does the confidence qualifier look like? A separate field? A tag? An evidence threshold?
