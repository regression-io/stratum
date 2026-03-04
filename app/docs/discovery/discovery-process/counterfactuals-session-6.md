# Counterfactuals: Interaction Surface Analysis

**Date:** 2026-02-11
**Parent:** [Level 2 Brainstorm](level-2-brainstorm.md)
**Target claim:** "Dimensions (What, How, Why) are facets of one interaction on a Work item. Clusters 2-4 are layers of the same thing."

---

## CF1: Dimensions exist independently of Work items

**Challenge:** A user asking "why did we choose React?" isn't touching a Work item. They're querying the knowledge graph directly. A project-level policy ("all PRs need review") isn't attached to a specific Work item — it floats above the hierarchy.

**Implication:** Dimensions aren't just lenses on Work items. They have independent existence at different scopes: item-level, parent-level, project-level, cross-project.

**Verdict:** Landed. The "facets of one interaction" framing holds at item level but breaks at broader scope. Dimensions need to work at multiple levels of the hierarchy, including above it.

**What this changes:** The three-lens model needs scope awareness. What/How/Why exist at every level of the tree, not just on leaf nodes.

---

## CF2: Knowledge layer IS a user surface

**Challenge:** "Show me everything we know about authentication." "What assumptions are we relying on?" "What's changed since last week?" These are queries to the knowledge layer, not to a Work item's Why facet. If users interact with it directly, it's a surface — maybe a primary one for founder/PM mode.

**Implication:** The knowledge layer isn't just infrastructure. For the PM/founder mode, it might be the *primary* interface. They don't care about individual Work items — they care about the state of knowledge across the project.

**Verdict:** Landed. The knowledge layer has two faces: infrastructure (powering Why queries on items) and surface (answering project-level knowledge questions directly).

**What this changes:** F6 (See Everything) might need to include knowledge-layer queries, not just dashboards of Work items. The "See" feature is broader than status visibility.

---

## CF3: Discovery needs to be an object, not just a process

**Challenge:** If tracking is cross-cutting and applies to all primitives, and Discovery is a primitive, then Discovery must be trackable. "Show me all open discoveries." "What questions are we still exploring?" But we defined Discovery as a process you participate in, not an object you manipulate. You can't track what you can't point at.

**Implication:** The objects-vs-processes split is a false dichotomy. Discovery needs both: a process you participate in AND a trackable entity you can see in a dashboard.

**Verdict:** Landed. Creates a design question: what is the trackable unit of Discovery? A question? A thread? An exploration? It can't be as structured as a Work item (that's the whole point of separating them) but it needs *some* handle for tracking.

**What this changes:** Discovery as a primitive needs a minimal trackable shape — lighter than Work, but visible. Maybe: trigger (the question), state (open/converging/closed), outputs (what it produced). That's it. No status lifecycle, no hierarchy. Just enough to track.

---

## CF4: How dissolves into What + Why

**Challenge:** When a developer says "we're doing TDD" — that's a decision (a What: decision-type Work item) with rationale (a Why: evidence and reasoning) that constrains future work via `informs` dependencies. The approach IS a decision. Policies (gate/flag/skip) are the only part of How that isn't already covered by What + Why.

**Implication:** How might not be a separate dimension. It might be a category of decisions (What) with governing effects (Why → `informs`). The Policy primitive is the only distinct How mechanism.

**Verdict:** Partially landed. Approach decisions are What + Why. But the 3-mode dial, templates, variant defaults — these are configuration, not decisions. They govern behavior without being Work items. How has a "decision" part (dissolves into What + Why) and a "configuration" part (stays as Policy).

**What this changes:** How is thinner than we thought. It's mostly Policy (configuration) plus approach decisions (which are regular Work items). Not a separate surface — a mix of existing surfaces.

---

## CF5: Why is just graph traversal, not AI reasoning

**Challenge:** If `informs` links are maintained and decision records are written, "why is it this way?" is just: follow the `informs` chain. That's a database query, not intelligence. The Knowledge layer might be as simple as a graph query engine.

**Implication:** We might be over-engineering the Knowledge layer. Simple Why = graph traversal. No AI needed.

**Verdict:** Partially landed. Simple Why queries ("what decision led to this?") are graph traversal. But harder queries need inference:
- "What assumptions are we relying on?" — requires identifying implicit assumptions, not just explicit links.
- "Is this stale?" — requires comparing current state against the state when a decision was made.
- "What would break if we changed X?" — requires impact analysis across the graph.

**What this changes:** The Knowledge layer has a gradient: simple queries (graph traversal, no AI) → moderate queries (staleness, impact, inference from structure) → hard queries (implicit assumptions, cross-cutting patterns). Build simple first. AI earns its keep on the moderate-to-hard range.

---

## CF6: When is a missing dimension

**Challenge:** Where's temporal context? What was true at the time of a decision? What's changed since? What's stale now? This is neither What, How, nor Why. Staleness detection, assumption decay, context drift — all temporal.

**Implication:** The Bayesian confidence model implicitly encodes time (evidence updates are temporal). But we haven't called out temporal context as a dimension. The "when" of evaluation timing (section 2 of the confidence evaluation doc) is process-level When. But there's also data-level When: the temporal state of knowledge.

**Verdict:** Landed — but may not need a new dimension. Time might be a property of evidence (each evidence update has a timestamp and context) rather than a separate axis. The confidence model already handles temporal decay through evidence updates. The question is whether "time since last evidence update" is a sufficient proxy for staleness, or whether temporal context needs explicit representation.

**What this changes:** Evidence needs timestamps at minimum. Ideally, evidence captures "what was true when this was decided" so staleness can be computed. This is metadata on existing structures, not a new dimension. But it's a requirement we hadn't articulated.

---

## Summary: what survived, what didn't

| Claim | Before | After | Movement |
|---|---|---|---|
| Dimensions are facets of one Work item interaction | Moderate | Low | Holds at item level, breaks at broader scope |
| Knowledge layer is infrastructure, not a surface | Moderate | Low | It's both — infrastructure AND a direct query surface |
| Objects vs. processes is a clean split | Moderate | Low | Discovery needs to be both — trackable and participatory |
| How is a separate dimension | Moderate | Low-Moderate | Partially dissolves into What + Why, residue is Policy |
| Why needs AI reasoning | Moderate | Moderate | Gradient: simple = graph, moderate/hard = AI |
| Three dimensions are sufficient | Moderate | Low-Moderate | Temporal context unaccounted for, possibly metadata not dimension |

**Net effect:** The model is less clean but more honest. Several claims were over-simplified. The revised picture is messier and probably closer to reality.
