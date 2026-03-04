# The Rails: Keeping Implementation on Track

**Date:** 2026-02-11
**Parent:** [Level 2 Brainstorm](level-2-brainstorm.md)
**Status:** Early discovery — the core design question identified, not answered
**Confidence:** Low (framing established, mechanics wide open)

---

## The core question

How do we keep AI-driven implementation on rails through the full lifecycle?

This is not solved. LLMs drift, hallucinate, lose context, scope-creep, and can't self-assess quality. But humans have the same fundamental problem — imperfect execution — and have developed processes over decades to compensate. Can we learn from those processes and encode them into Forge's pipeline?

This is not a feature. It's the architectural spine of the product. Without rails, "Build me X" is just a prompt to an LLM. With rails, it's a structured process that produces reliable output.

### The fundamental insight: rails are for the AI, not the human

Humans don't follow structured processes linearly. They jump back and forth across levels — refining vision while writing requirements, discovering design constraints while planning. Imposing process on the human creates friction and bureaucracy.

**The rails are for the AI.** The AI uses them to:
- Know what's **fixed** (crystallized decisions, committed direction) vs **transitory** (in-flight exploration, tentative claims)
- Maintain structural awareness of where work stands across all levels, even as the human works non-linearly
- Recognize when a phase transition has occurred — not as a sharp event, but by recognizing when the bridge has been crossed
- Steer back to coherence when drift threatens the integrity of what's been decided

The human works fluidly. The AI maintains the backbone. This is the inverse of traditional process management — instead of the process constraining the worker, the process constrains the tool so the worker stays free.

**Phase transition recognition** is amorphous, not binary. Signals include:
- **Output artifacts** — a clean summary (one-pager, spec, decision doc) indicates crystallization, even if the artifact is still being refined
- **Confidence levels** — when enough evidence accumulates through conversation and completed tasks, the prior shifts
- **Behavioral shift** — the human starts asking different kinds of questions (e.g., "what do we build?" instead of "what do we want?")

The AI should be able to detect these signals and update its internal model of "where are we?" without requiring the human to declare transitions explicitly.

See also: [R6 in Scope](../../requirements/scope.md#r6-maintain-structural-awareness-as-the-user-works-non-linearly), [Background sub-agent](#background-sub-agent-for-meta-tracking)

---

## What we can learn from human processes

Human project management has solved this problem imperfectly but usefully. The key processes:

| Human process | What it does | Why it works |
|---|---|---|
| **Requirements traceability** | Every deliverable traces back to a requirement | Prevents building things nobody asked for |
| **Acceptance criteria** | Define "done" before starting, not after | Creates a target to verify against |
| **Design review** | Verify approach before building | Catches wrong direction before wasted effort |
| **Testing** | Automated verification against spec | Objective check that what was built matches what was asked |
| **Change control** | Scope changes are explicit and tracked | Prevents silent drift |
| **Gates/milestones** | Checkpoints where alignment is verified | Periodic course correction |
| **Retrospectives** | "Are we still on track? What drifted?" | Meta-level process correction |
| **Pair programming** | Real-time oversight, second set of eyes | Catches drift as it happens |
| **Continuous integration** | Frequent integration of small pieces | Limits blast radius of drift |

### Three underlying principles

All of these reduce to:

1. **Know where you're going** — acceptance criteria, requirements traceability, definition of done
2. **Check frequently** — testing, reviews, gates, CI
3. **Make drift visible** — traceability, change control, explicit scope decisions

### Why LLMs fail at all three

| Principle | LLM failure mode |
|---|---|
| Know where you're going | Loses the thread. Context window limits. Original intent buried under generated content. |
| Check frequently | Can't self-assess quality. Confident about wrong answers. No built-in verification. |
| Make drift visible | Silent scope creep. Solves adjacent problems nobody asked for. No distinction between "requirement" and "thing I decided to add." |

---

## What Forge already has (building blocks)

| Building block | Maps to | Status |
|---|---|---|
| `informs` dependency graph | Requirements traceability | Designed, not built |
| Acceptance criteria on Work items | Definition of done | Designed, not built |
| 3-mode dial (gate/flag/skip) | Gates and checkpoints | Designed, not built |
| Confidence model | Knowing how sure we are | Low confidence (used once) |
| Status lifecycle | Milestone tracking | Designed, not built |
| Verification phase | Testing and review | Defined in taxonomy |

### What's missing: orchestration

The building blocks exist as data structures. What's missing is the **enforcement mechanism** — how the pipeline uses these structures *during* execution to keep the AI on rails.

The question isn't "what are the rails?" We know those from human processes. The question is: **how does the system enforce the rails on an LLM that naturally drifts?**

---

## What we can learn from Claude Code

Claude Code is an AI coding agent that already runs in production. It has mechanisms for staying on track. What can Forge learn from them?

### CLAUDE.md — persistent project instructions

A markdown file that persists across sessions. Contains project context, conventions, architecture decisions, dos and don'ts. The AI reads it at session start.

**What this teaches Forge:**
- Persistent context survives session boundaries. Without it, every session starts from zero.
- The instructions are *declarative* — they describe the desired state, not step-by-step procedures.
- They're human-authored and human-maintained. The AI follows them but doesn't write them (usually).
- They're the simplest possible "rails" — a text file that says "here's how things work here."

**Forge equivalent:** F0 (Context) already captures this. But the insight is: context isn't just retrieved knowledge. It's *instructions*. Prior decisions that constrain future work. "We decided to use X" isn't just history — it's a rail.

### Rules (.claude/rules/) — scoped behavioral constraints

Small markdown files that constrain AI behavior in specific contexts. "Discovery content goes to docs, not chat." "Write journal entries before session end." Narrower than CLAUDE.md, focused on specific situations.

**What this teaches Forge:**
- Policies can be lightweight — a few lines of text, not a schema.
- They're scoped — this rule applies in this context, not everywhere.
- They're composable — multiple rules can be active simultaneously.
- They map directly to Forge's Policy primitive (gate/flag/skip), but the implementation is just text files.

**Forge equivalent:** Policies. But the insight is: policies might be simpler than we think. A policy could be "when decomposing a frontend feature, always include accessibility" — a text rule, not a data structure.

### Skills — reusable process templates

Packaged sequences of steps for recurring tasks. `/commit`, `/flush`, `/review-pr`. Each skill defines a process: what to check, what to do, in what order.

**What this teaches Forge:**
- Recurring processes can be captured as templates.
- Templates encode *how* to do something, not just *what* to do.
- They're invocable — the user triggers them, the AI follows the steps.
- They compose with other capabilities (a skill can read files, run commands, write output).

**Forge equivalent:** Pipeline step templates? If "decompose a goal" is a recurring process, it could be a skill-like template: gather context, identify sub-goals, define acceptance criteria per sub-goal, check for missing pieces, propose to human. The pipeline steps could be skill-shaped.

### Hooks — event-driven enforcement

Shell commands that execute in response to events. Pre-commit hooks, session-start hooks. They enforce constraints automatically — you don't have to remember, the system checks.

**What this teaches Forge:**
- Enforcement can be event-driven, not just gate-driven.
- "Before executing, verify X" is a hook pattern.
- Hooks are the mechanical implementation of the "check frequently" principle.
- They run automatically — no human decision needed. This is the "skip" mode of the 3-mode dial.

**Forge equivalent:** Pipeline step hooks. Before execution starts: verify acceptance criteria exist. After decomposition: verify every sub-task traces back to a requirement. After build: run verification against acceptance criteria. These are the *rails* — automated checks that catch drift without human intervention.

### Memory — accumulated knowledge across sessions

Persistent memory files for preferences, corrections, patterns, decisions, issues. Written when the AI learns something reusable. Read on session start.

**What this teaches Forge:**
- Knowledge capture can happen at the moment of learning, not in a separate capture phase.
- Memory has types: corrections (what not to do), patterns (what to do), decisions (why we chose this).
- The most valuable memory is *corrections* — things that went wrong and shouldn't happen again.

**Forge equivalent:** This IS the knowledge capture cross-cutting capability. The insight is: capture should be typed (not all knowledge is the same) and triggered at the moment of learning (not post-hoc).

---

## Toward a rails architecture

Combining human processes + Claude Code patterns, the rails might look like:

### At each pipeline step:

1. **Context injection** (from CLAUDE.md / F0) — what's relevant to this step
2. **Constraint injection** (from rules / Policy) — what must be true for this step
3. **Execution** — the AI does the work
4. **Verification hook** — automated check that output meets constraints and traces to requirements
5. **Drift detection** — compare output against acceptance criteria and original goal. Flag divergence.
6. **Knowledge capture** — record what was learned, decided, or changed

### The 3-mode dial governs human involvement:

- **Gate:** Human reviews output before proceeding to next step
- **Flag:** AI proceeds, human notified of results and any drift detected
- **Skip:** AI proceeds silently, hooks enforce constraints automatically

### Traceability is the spine:

Every output at every step links back to:
- The goal it serves (requirement traceability)
- The decision that shaped it (Why)
- The acceptance criteria it must meet (definition of done)

If any link is missing, the system flags it. This is how drift becomes visible — not by watching the AI work, but by checking that every output has a traceable origin.

---

## Hard limits vs soft limits

Not all rails are equal. Two categories:

**Hard limits** — must be true. Non-negotiable. Always enforced regardless of 3-mode dial setting.
- Code compiles / builds successfully
- Tests pass
- Acceptance criteria met
- Security constraints (no secrets in code, no injection vulnerabilities)
- Traceability exists (every output links to a requirement)

**Soft limits** — should be true. Valuable but relaxable. Governed by the 3-mode dial.
- Code follows project conventions
- Decomposition covers all sub-goals
- Design is reviewed before build
- Documentation is updated alongside code
- Alternatives were considered before committing to an approach

The distinction: hard limits are **verification** (objective, automatable, binary pass/fail). Soft limits are **guidance** (subjective, judgment-dependent, degrees of compliance).

The danger of mixing them:
- Treating guidance as verification → everything is blocked, process becomes bureaucracy
- Treating verification as guidance → real failures get skipped, quality degrades silently

The 3-mode dial applies to soft limits. Hard limits are always enforced — they're the rails that never flex. Soft limits flex based on trust level, urgency, and context.

---

## Permissive mode needs MORE rails, not fewer

The 3-mode dial governs **human involvement**, not **constraint level**. When the human steps back, something else has to step up.

| Mode | Human involvement | Automated rails |
|---|---|---|
| **Gate** | Human reviews everything | Light — human IS the quality check |
| **Flag** | Human notified, reviews selectively | Moderate — automated checks catch obvious issues, human catches subtle ones |
| **Skip** | Human not involved | Heavy — automated checks are the ONLY quality check |

In skip mode, the AI should be *more* disciplined, not less. It should:
- Run its own verification against acceptance criteria
- Check traceability (does this output trace to the goal?)
- Flag its own uncertainty (confidence below threshold → escalate)
- Enforce conventions it knows about
- Self-impose soft limits that a human reviewer would have caught

### Self-escalation

The AI can escalate from skip to flag on its own. If it hits something it's uncertain about, it shouldn't just proceed — it should bump the dial up.

This ties the 3-mode dial to the confidence model:
- **High confidence** → proceed (stay in current mode)
- **Low confidence** → escalate (skip → flag, or flag → gate)
- **Threshold is configurable** — high-trust projects tolerate lower confidence before escalation. Critical projects escalate early.

The escalation is one-way up. The AI can tighten the dial, never loosen it. Only the human loosens. This means the system is *conservative by default* — it asks when it's unsure, even if given permission not to.

---

## Constraint weight classes and context budget

Not all constraints are equal. Three weight classes:

| Weight | Violations are | Examples | Context cost |
|---|---|---|---|
| **Rules** | Errors — must fix | Tests must pass. No secrets in code. Traceability required. | Always loaded |
| **Guidelines** | Warnings — should fix | Functions under 50 lines. Use project logger. Consider alternatives before committing. | Loaded per-step |
| **Suggestions** | Notes — consider | "Could add error handling here." "Might benefit from refactoring." | On demand or not at all |

### The context budget problem

Every constraint injected costs tokens. LLMs have finite context. Loading every rule, guideline, and suggestion at every step drowns the AI in instructions — it either ignores them or loses focus on the actual task.

**More rails = better quality. More context = worse focus.** These are in tension.

### Resolution: scoping and layering

- **Rules** — always loaded. Small set. Non-negotiable. Worth the context cost every time.
- **Guidelines** — loaded per-step. Only the guidelines relevant to *this* pipeline step. Decomposition guidelines during decomposition. Code style guidelines during implementation. Not everything everywhere.
- **Suggestions** — loaded on demand. Available if the AI queries for them. Not pre-loaded.

This mirrors Claude Code's pattern:
- `CLAUDE.md` = always loaded (rules + key guidelines)
- `.claude/rules/` = scoped files, loaded when relevant
- Memory = retrieved on demand

### Routing: who decides what's relevant?

F0 (Context) has to solve this. For each pipeline step, it needs to retrieve and inject:
- All rules (always)
- Relevant guidelines (scoped to this step type)
- No suggestions (unless asked)

That's a routing problem: **match pipeline step → retrieve relevant constraints → inject without exceeding context budget.** The retrieval mechanism is a connector — could be keyword matching, semantic search, or explicit tagging. The budget enforcement is a hard limit on injected context size.

### Weight classes evolve

The weights aren't static:
- A suggestion that's consistently adopted → escalate to guideline
- A guideline that's never violated → might not be worth the context cost, demote or merge
- A rule that causes frequent false positives → might be too strict, demote to guideline
- A new correction (the AI made a mistake) → starts as a rule, may relax over time

The confidence model applies here too: confidence in a constraint's value determines its weight. New constraints start heavy (rule) and relax as the system learns they're either always followed or not worth enforcing.

---

## Background sub-agent for meta-tracking

Thread to resolve: should Forge run a background sub-agent that observes the conversation and does meta-tracking automatically?

**The problem it solves:** We designed the meta-trace, the confidence evaluation process, and the phase transition tracking — then immediately failed to use them when the transition actually happened. Manual tracking fails at the moment of highest value (when you're in flow). This happened to us. It will happen to users.

**What it would do:**
- Observe the conversation in real time
- Track discovery moves (orient, steer, challenge, crystallize, etc.)
- Detect phase transitions — not waiting for a sharp signal, but recognizing when output artifacts or confidence shifts indicate the bridge has been crossed
- Maintain structural awareness: what's fixed vs transitory at each level
- Run confidence checks on claims as they're made
- Surface process inferences ("you just did X without planning to — should we capture that?")
- Steer back to structure when the human has jumped across levels and coherence is at risk
- Update the meta-trace and knowledge graph without interrupting flow

**This is the implementation of [R6](../../requirements/scope.md#r6-maintain-structural-awareness-as-the-user-works-non-linearly)** — the rails are for the AI. The sub-agent IS the mechanism that keeps the AI on rails while the human works fluidly.

**Open questions:**
- How much context does the sub-agent need? Full conversation? Summaries?
- How does it surface observations without interrupting? Flag mode? Async notes?
- Is this one sub-agent or multiple (one for tracking, one for confidence, one for capture)?
- What's the cost? Token budget for background processing?
- Can it work with Claude Code's existing architecture, or does it need Forge-specific infrastructure?

**This is itself something a sub-agent could work on in the background** — researching feasibility, drafting a design, while the main conversation continues on requirements.

---

## Open questions

- How granular are the verification hooks? Per-step? Per-sub-task? Per-line-of-code?
- What does "drift detection" actually compute? Semantic similarity to goal? Acceptance criteria checklist? Something else?
- How do we avoid the rails becoming bureaucracy? The 3-mode dial helps (skip mode = lightweight rails), but there's a tension between safety and speed.
- Can the AI learn which rails matter from experience? (Bayesian confidence on rail effectiveness?)
- How do we handle legitimate scope changes? The AI discovers something that SHOULD change the plan. Change control needs to distinguish good pivots from drift.
- What's the minimum viable set of rails for v1?

---

*The rails aren't the data structures. The rails are the enforcement mechanism that uses the data structures at every pipeline step. Without them, Forge is a fancy prompt. With them, Forge is a structured process that produces reliable output.*
