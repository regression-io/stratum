# Crystallization Review: Session 5 End-State

**Date:** 2026-02-11
**Parent:** [Level 2 Brainstorm](level-2-brainstorm.md)
**Purpose:** Honest assessment of what we've crystallized, what we haven't, and what might break.

---

## Pass 1: What have we crystallized?

| Thing | Status | Confidence | Basis |
|---|---|---|---|
| 4 primitives (Discovery, Work, Policy, Session) | Crystallized | Low | Decided in this session, untested |
| 3 working dimensions (What, How, Why-factual) | Crystallized | Moderate | Discussed across 2 sessions, partially challenged |
| Bayesian confidence model | Crystallized | Low | Elegant on paper, zero use |
| 6 features (Discover, Capture, Distill, Plan, Execute, See) | Crystallized | Low | Just restructured, not tested against use cases in new form |
| Cross-cutting capabilities (tracking, confidence, visibility) | Crystallized | Moderate | Observation held under examination |
| 2 ICPs as modes (dev + founder = depth profiles) | Crystallized | Moderate | Matches real experience of this session |
| 4 discovery modes (brainstorm, research, prototype, integration) | Crystallized | Low | Intuited from one conversation |
| Discovery verbs (orient, steer, gather, etc.) | Crystallized | Very low | Intuited, explicitly flagged as untested |
| 7 model gaps | Crystallized | Moderate | Derived from use case walkthrough |
| False crystallization concept | Crystallized | Moderate | We experienced it firsthand |

Most things are low confidence. We've been productive at generating structure, less productive at testing it.

---

## Pass 2: What's NOT crystallized that should be?

### Untouched Level 2 clusters

Three of the five original clusters from [level-2-brainstorm.md](level-2-brainstorm.md) are completely unexplored:

- **Cluster 2: How** — what does the How dimension look like mechanically? Templates? Approach selection? Relationship to Policy? Zero discussion.
- **Cluster 3: Why-factual** — how does knowledge reasoning manifest? `informs` dependency? Assumption tracking? Evidence chains? Zero discussion beyond naming it.
- **Cluster 4: Knowledge layer** — what is the AI actually doing underneath? Passive index or active monitor? Triggers? Zero discussion.

### Unreconciled architecture

- The original architecture was "3 primitives × 3 sub-constructs." We added a 4th primitive but didn't reconcile with the 3×3 model. Does it become 4×N? Does the sub-construct pattern still hold?
- The Work primitive was flagged tentative in the validation exercise but never revisited. We got pulled into confidence and features.

### Underspecified features

- **F3 (Distill & Decide)** carries 3 gaps and is the conceptually heaviest feature. Its entire design is three words: "extract → assess → decide." No mechanics, no UI concept, no data flow.
- **F1 (Discover)** is defined as "help users explore" but the Discovery primitive's properties (trigger, mode, participants, outputs, trace, confidence, state) haven't been mapped to UI or behavior.

### Missing connections

- How do the 3 dimensions (What, How, Why-factual) map to the 4 primitives? This was Cluster 5 and we never reached it.
- How does the feature flow (F1→F3→F2→F4→F5) relate to the lifecycle phases (discovery→requirements→design→planning→implementation→verification)?

---

## Pass 3: What's fragile — might break under pressure?

### Discovery as a primitive vs. a mode

We said "Discovery isn't Work — it's a 4th primitive." But is it? Alternative: Discovery is a *mode that Sessions enter*. When a session hits a question, it enters discovery mode. When it has answers, it exits. This would make Discovery a property of Session, not a peer primitive.

**What would break if it's a mode, not a primitive?** The process trace would live on Session, not on Discovery. The discovery state (open/converging/closed) would be session state. The 4 discovery modes would be sub-modes of session discovery mode. This might actually be simpler.

**What would break if it IS a primitive?** It needs its own lifecycle, persistence, and UI surface. That's a lot of weight for something that might just be "a session doing exploration."

**Unresolved.** Needs pressure-testing with real examples.

### The feature flow is too linear

```
F1 Discover → F3 Distill → F2 Capture → F4 Plan → F5 Execute
```

Real work is messier. In this session alone we discovered, distilled, captured, and looped back multiple times within minutes. The clean flow might be aspirational, not real. If it's aspirational, it's useful as a mental model. If it's prescriptive (Compose enforces this order), it's wrong.

### Bayesian confidence without teeth

"Qualitative Bayesian" might just mean "vibes with a fancy name." What makes it actually Bayesian vs. just "we track whether things were tested"?

Real Bayesian: prior probability, likelihood ratio from evidence, updated posterior.
What we have: "prior is weak, evidence strengthened it, confidence is moderate."

If we can't define what computation the system does — even qualitatively — then it's false crystallization of the confidence model itself. The model describing its own weakness.

### Use cases UC-10 through UC-18 are invented

The original 9 (UC-1 through UC-9) came from real scenarios. UC-10 through UC-18 were invented in this session to fill persona gaps. They haven't been validated against real users. They might be wrong, missing the actual pain points of founders and researchers.

### The meta-trace is already falling behind

We committed to maintaining the meta-trace as a living document. It has 20 entries. But the later entries are thinner — less detail about what triggered each move. The process of recording the process is itself subject to decay. Ironic, given the session's themes.

---

## Summary

We generated a lot of structure this session. The honest confidence assessment:

- **Solid ground:** False crystallization concept, ICPs as modes, cross-cutting capabilities, the gaps themselves
- **Promising but untested:** 4 primitives, Bayesian confidence, feature map, discovery modes
- **Possibly wrong:** Discovery as primitive (vs. mode), linear feature flow, qualitative Bayesian, invented use cases
- **Completely untouched:** How dimension, Why-factual mechanics, knowledge layer, primitive-dimension mapping

The session was productive for divergent thinking. It needs convergent pressure next — testing these ideas against real work, not just against each other.
