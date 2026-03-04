# Confidence Evaluation: Process, Timing, and Inference

**Date:** 2026-02-11
**Parent:** [Level 2 Brainstorm](level-2-brainstorm.md)
**Source:** Observed in practice during Session 6 — the first real use of the confidence model.

---

## 1. The evaluation process

What actually happens when confidence is evaluated. Derived from what we did, not what we theorized.

### The pattern

```
Claim exists (with implicit or explicit prior)
    ↓
Challenge applied (counterfactual, test, comparison, real use)
    ↓
Claim either survives, weakens, strengthens, or splits
    ↓
Posterior assigned (revised confidence)
    ↓
New claims or questions may emerge from the challenge
```

### What moves confidence UP

| Evidence type | What it looks like | Strength |
|---|---|---|
| **Survived challenge** | Counterfactual was generated but didn't land | Moderate |
| **Used in practice** | The thing was applied and produced useful results | Strong |
| **Independent arrival** | Two separate lines of reasoning converge on same conclusion | Strong |
| **Predicted correctly** | The model predicted something that turned out true | Strong |
| **Withstood edge case** | Tested against an unusual scenario and held | Moderate |

### What moves confidence DOWN

| Evidence type | What it looks like | Strength |
|---|---|---|
| **Counterfactual landed** | A plausible alternative undermines the claim | Moderate-Strong |
| **Failed in practice** | Tried to use it and it didn't work or didn't fit | Strong |
| **Scope violation** | Claim assumed one scope, reality requires another | Moderate |
| **Missing dimension** | Something important was unaccounted for | Moderate |
| **Dissolves on examination** | Closer inspection reveals the claim is two different things, or nothing | Strong |

### What we observed

In Session 6, we claimed "dimensions are facets of one interaction on a Work item." We ran 6 counterfactuals:

- CF1 (dimensions exist at multiple scopes) — **landed**. Lowered confidence on "facets of one interaction." Dimensions operate at item, parent, project, and cross-project scope. Not always tied to a specific Work item.
- CF2 (knowledge layer is a surface) — **landed**. Lowered confidence on "infrastructure, not a surface." Founder/PM mode queries the knowledge layer directly.
- CF3 (Discovery needs to be an object) — **landed**. Created a paradox: if tracking is cross-cutting and Discovery is a primitive, Discovery must be trackable. But we said it's a process, not an object.
- CF4 (How dissolves into What + Why) — **landed partially**. Approach decisions are decision-type Work items with `informs` dependencies. But policy dials are still their own thing.
- CF5 (Why is just graph traversal) — **partially landed**. Simple Why queries are just graph traversal. But staleness detection and assumption tracking need inference beyond traversal.
- CF6 (When is a missing dimension) — **landed**. Temporal context is real and unaccounted for.

Result: original claim revised from "validated" to "partially holds at item level, breaks at broader scope." Several new questions surfaced. Net confidence on the interaction surface analysis: **lowered**, but the analysis became more precise.

---

## 2. When to evaluate (triggers and timing)

The confidence model exists. When do you actually use it?

### Observed triggers

From our own sessions — when did evaluation actually happen?

| Trigger | Example | What it produced |
|---|---|---|
| **Human challenge** | "Can we be sure?" | False crystallization insight |
| **Attempt to use** | Trying to model this session as a Work item | Discovery-as-primitive |
| **Explicit review** | "Review crystallization 3x" | Crystallization review doc |
| **Counterfactual exercise** | "Think of counterfactuals" | 6 challenges, 4+ landed |
| **Scope expansion** | "Does this work for other users?" | Use case matrix, 7 gaps |
| **Phase boundary** | Moving from analysis to capture | "That's a goal, not requirements" |

### When evaluation SHOULD happen (inferred)

- **Before crystallizing** — before writing a conclusion into a doc, test it. We didn't always do this (false crystallization).
- **After crystallizing** — review what you wrote with fresh eyes. Did structure add false confidence?
- **When building on a claim** — if claim B depends on claim A, check A's confidence first. Weak foundations compound.
- **When context shifts** — new information, new scope, new use case. Does the claim still hold?
- **At natural pauses** — end of a topic thread, end of a session, before switching focus.

### When evaluation should NOT happen

- **Mid-flow in divergent thinking** — challenging every claim as it emerges kills brainstorming. Let ideas accumulate, then evaluate.
- **On things that don't matter yet** — evaluating low-stakes claims wastes energy. Focus evaluation on load-bearing claims.
- **Prematurely** — some things need to exist loosely before they can be evaluated. Don't demand confidence on a 5-minute-old idea.

### The timing insight

Evaluation has its own rhythm. It's not continuous. It pulses:

```
Diverge (generate, don't evaluate)
    → Pause (notice you have claims)
    → Converge (evaluate, challenge, revise)
    → Diverge again (with revised model)
```

The human's role in our sessions has been to trigger the pauses. "Can we be sure?" "Think of counterfactuals." "Re-evaluate." The AI's default is to keep generating. The human's value is knowing when to stop and test.

---

## 3. How to infer processes

We didn't plan to run the confidence model. We just did it. The human asked for counterfactuals, we generated them, confidence moved. Only afterward did we recognize: "that was the Bayesian process."

This is process inference — recognizing a process from its trace, not from its plan.

### What makes a process inferable?

A process is recognizable when it has:
- **Recurring structure** — the same pattern of moves appears in different contexts
- **Identifiable inputs and outputs** — something goes in, something different comes out
- **Named moves** — even if the names come after the fact, the moves are distinct

### Processes we've inferred from this project

| Process | How we discovered it | Moves |
|---|---|---|
| **Confidence evaluation** | Did it, then recognized it | Claim → challenge → survive/weaken/split → revise |
| **False crystallization detection** | Caught ourselves | Write structure → assume confidence → human challenges → realize gap |
| **Discovery decomposition** | Realized discovery operates at every phase boundary | Loose input → Q&A → decisions along the way → concrete output |
| **Insight emergence** | Noticed pattern in meta-trace | Side question → unexpected connection → new concept → capture |

### The meta-question: can the AI do this?

If the AI can recognize process patterns as they happen (not just after the fact), it can:
- **Name the move** — "that looks like a confidence evaluation"
- **Support the move** — "want me to generate counterfactuals?"
- **Track the move** — add to the meta-trace automatically
- **Suggest the next move** — "we've been diverging for a while, want to evaluate?"

This is what the Discovery Verbs doc was trying to get at — orient, steer, challenge, crystallize. But verbs are vocabulary. Process inference is recognizing *which verb is happening* from context, without being told.

### How and When as process dimensions

The user flagged "when" as a dimension of process. Combined with "how":

- **How** a process runs — the moves, the sequence, the participants
- **When** a process runs — the triggers, the timing, the rhythm

These aren't the same as the How and Why dimensions of Work items. They're meta-dimensions — properties of the discovery process itself. The product's How dimension (policies, configuration) governs work. The process's how/when govern how we *do* discovery.

This is a level confusion to watch for: product dimensions vs. process dimensions. They use the same words but operate at different levels.

---

## What this tells us

1. **The confidence model works as a reasoning pattern.** First real use confirmed it produces useful results (counterfactuals that reshaped the model). Confidence on the confidence model: bumped from low to low-moderate.

2. **Timing matters.** Evaluate too early and you kill divergence. Evaluate too late and false crystallization sets in. The human's challenge instinct is the current timing mechanism. Can it be supported by the AI?

3. **Processes are inferred, not designed.** We didn't plan the confidence evaluation process. We did it, then recognized it. This suggests Compose's process support should be recognition-first, not template-first. Watch what people do, name it, then support it.

4. **Product dimensions ≠ process dimensions.** How/When for Work items is different from How/When for the discovery process. Same words, different levels. The product tracks work. The process produces the work that gets tracked. Don't conflate them.

5. **The AI's role in process is recognition + support.** Not orchestration. The human drives. The AI notices patterns, names moves, suggests timing. The discovery verbs are the vocabulary for this. But the verbs need to be inferred from behavior, not imposed.

---

*First use of the confidence model on itself. Recursive, but it worked.*
