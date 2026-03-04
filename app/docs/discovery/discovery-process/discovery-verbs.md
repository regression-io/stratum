# Discovery Insight: Discovery Verbs

**Date:** 2026-02-11
**Parent:** [Level 2 Brainstorm](level-2-brainstorm.md)
**Status:** Tentative

---

## The verbs

Moves observed during discovery conversations:

| Verb | What it does | Example from this session |
|------|-------------|--------------------------|
| **Orient** | Establish where we are | "where are we?" |
| **Steer** | Change direction, focus, park | "park 0.4, focus on discovery" |
| **Gather** | Pull together existing knowledge | "what's all the wording around What?" |
| **Challenge** | Test whether something holds | "can we be sure?" |
| **Qualify** | Mark confidence level | "mark it tentative" |
| **Reflect** | Meta-observation about the process | "did we learn something just now?" |
| **Gate** | Pull back, redirect, limit depth | "you're beyond my depth, pull back" |
| **Test** | Try an idea against reality | "model real work against the primitive" |
| **Crystallize** | Write it down, make it an artifact | "create a doc with this" |

## Who are these for?

**Not the user.** A skilled human already does these naturally. Naming them doesn't improve the doing — like naming muscles doesn't improve walking.

**For the AI.** This is where the verbs change outcomes. If the AI can recognize the current mode of the conversation, it can be a better partner:
- Noticed we've been gathering without challenging → prompt: "should we pressure-test this?"
- Noticed we crystallized without testing → flag: "this is untested, mark tentative?"
- Noticed the human is gating → back off, simplify, don't push deeper
- Noticed we've been in free-flow too long → suggest: "worth capturing this in a doc?"

The verbs are the AI's **vocabulary for reading the room** during discovery. Not something to surface to the user or track as data — internal intelligence for the agent.

## Connection to onboarding

Whether the AI *uses* these actively depends on user preference. A structured user might want the AI to prompt for missing verbs. A free-flow user might want the AI to stay quiet and only crystallize when asked. See [Onboarding Inputs](onboarding-inputs.md).

## Open questions

- Are these the right verbs, or are we missing some?
- How does the AI actually detect these in real-time? Pattern matching on conversation? Explicit signals?
- Is this Phase 3.2 (conversation distillation) territory, or is it earlier — part of the agent connector?
