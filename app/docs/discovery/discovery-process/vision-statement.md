# Compose: Product Vision

**Date:** 2026-02-11
**Status:** Crystallized (moderate confidence — pressure-tested with counterfactuals, resolved)
**Parent:** [Level 2 Brainstorm](level-2-brainstorm.md)

---

## Vision

You say "Build me X." Compose takes it from there — decomposing the goal, asking the right questions, making decisions (or prompting you to make them), designing, planning, and directing agents to build exactly what you need. One prompt in, working product out.

The structured process is the product. What, How, Why, and Confidence are the reasoning underneath — how Compose knows what to ask, when to ask, and how sure it is before proceeding.

---

## Variable entry points, one pipeline

Not every interaction is "Build me X." The pipeline handles any starting point by scaling the context phase:

| Entry point | What happens | Context depth |
|---|---|---|
| "Build me X" (greenfield) | Full pipeline from scratch | Zero |
| "Build me X" (existing project) | Full pipeline with codebase awareness | Moderate |
| "Fix this bug" | Diagnosis → design fix → plan → build | Moderate |
| "Add Y to Z" | Understand Z → plan Y → build | Moderate |
| "Refactor this" | Deep understanding → new structure → plan → build | Deep |
| "Continue where I left off" | Recover pipeline state → rejoin mid-stream | Full |
| "I have a fuzzy idea" | F1 Discover → converge to a goal → enter pipeline | On-ramp |

"Build me X" (greenfield) is the longest path. Everything else slots in downstream. The pipeline is one thing — entry points differ in how much context Compose needs before it can decompose.

---

## What this means for priorities

The **structured implementation pipeline** (context → decomposition → Q&A → decisions → design → plan → build) is the core product. It's what differentiates Compose from a task tracker or a chat window.

**F0 (Context)** is the front door. Every entry point passes through it. Autonomous context (code) is gathered by Compose. Opportunistic context (project history, work state, richer intent) is used when available, not required. The pipeline works with just the prompt + code. Everything else makes it better. First use is weakest. Tenth use has accumulated reasoning.

**Discovery/brainstorming** is a feature — valuable, optional, hardest to get right because of inherent ambiguity. Maybe 50% of dev users skip it entirely. Founders/PMs are more likely to use it. Worth building well, but it's an on-ramp to the pipeline, not the pipeline itself.

**The reasoning model** (What/How/Why, Confidence, Discovery primitive) is infrastructure. It powers the pipeline's ability to decompose correctly, ask the right questions, and know when to proceed vs. when to ask. Users don't interact with the model directly — they experience it as "Compose asks good questions and builds the right thing."

---

## Pressure test (Session 6)

Six counterfactuals run against the vision. All landed to some degree. Resolutions:

| Challenge | Resolution |
|---|---|
| "Build me X" is too narrow — most prompts aren't greenfield | Variable entry points. Pipeline handles all starting points via scaled context phase (F0). |
| "Takes it from there" overpromises autonomy | Acknowledged. The tagline is aspirational. Reality is 3-mode dial — human involved at gate points. Tagline still works as north star. |
| Vision describes a process, not a differentiator | The differentiator is the structured process + persistence + accumulated context. Raw AI does the same steps but forgets everything and has no structure. Compose adds rails and memory. |
| No user in the vision — human is passive | Human steers at decision points (3-mode dial). The vision describes the ideal flow, not every interaction. Human involvement is a design principle, not a vision-level concern. |
| "Exactly what you need" is impossible in one shot | Real projects are iterative. The pipeline loops. Each loop has more context (F0 gets better). The vision describes the aspiration, not a single-pass guarantee. |
| Nothing about what persists | F0 and F2 handle persistence. The vision doesn't need to say "and it remembers" — persistence is how the product works, not what it promises. Compose gets better over time because F0 accumulates context. |

**Post-pressure-test confidence:** Moderate. The tagline is directionally right. The unresolved items were addressed by feature design (F0, F2, F6), not by changing the vision. The vision is a north star, not a spec.

---

## The original idea (for the record)

> Put implementation on rails by going through a structured process so you could just provide a single statement prompt, "Build me X" and it would figure out the rest, prompting you to resolve any questions and build you exactly what you need.

Everything we build serves this.
