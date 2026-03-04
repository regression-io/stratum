# Ontology Counterfactuals

**Date:** 2026-02-11
**Parent:** [Needs](needs.md)
**Status:** Two rounds complete. Open questions preserved.

---

## Round 1: Against the 3-concept ontology (items, connections, state)

The initial ontology had three concepts: items, connections, state.

### CF1: "Items are too flat — some things aren't items"
**Claim tested:** Everything is an item.
**Counter:** Conversations, sessions, phase transitions, and processes are events/happenings, not nouns. Discovery is a process, not an item. The ontology only models outputs, not the processes that produce them.
**Verdict:** Bites hard. Led to adding processes as a fourth concept.

### CF2: "Connections might just be items"
**Claim tested:** Connections are a separate concept from items.
**Counter:** "A informs B" could itself be an item with content, confidence, and state. If connections are rich enough to have their own properties, the distinction is artificial.
**Verdict:** Interesting but may be over-modeling for v1. Open question.

### CF3: "State is too coarse at the item level"
**Claim tested:** State lives on items.
**Counter:** "The vision statement is crystallized" but individual claims within it have different confidence levels. Doc-level state hides internal variance.
**Verdict:** Real. Already scoped out for v1 (doc-level only). Known gap.

### CF4: "Types morph — they're not stable labels"
**Claim tested:** Items have a type (idea, decision, question, spec...).
**Counter:** A question becomes a decision. A brainstorm becomes a spec. If type changes over lifetime, it's state, not identity.
**Verdict:** Bites. Type might be state rather than a fixed label. Open question.

### CF5: "Fixed vs transitory is derived, not independent"
**Claim tested:** Fixed/transitory is a separate state dimension.
**Counter:** High confidence + crystallized = fixed. Low confidence + tentative = transitory. It's computable from status + confidence. Redundant as a third axis.
**Verdict:** Likely true. Removed as independent dimension, noted as possibly derived.

### CF6: "Where's time?"
**Claim tested:** The ontology is complete without temporal dimension.
**Counter:** Supersedes implies temporal ordering. Staleness detection requires timestamps. Without time, supersedes is a claim without evidence.
**Verdict:** Bites. Timestamps added to state in the updated ontology.

### CF7: "Hierarchy is special, not just another connection"
**Claim tested:** Parent/child is listed alongside other connection types.
**Counter:** Hierarchy determines scope, enables policy inheritance, and defines tree navigation. Other connections don't do this. If hierarchy is just a connection, those structural properties are lost.
**Verdict:** Bites. Needs explicit resolution — is hierarchy a structurally special connection or just another type?

### CF8: "Where are the actors?"
**Claim tested:** The ontology is complete with items, connections, state.
**Counter:** Who created this? Who changed it? The Session primitive covers actors but the ontology doesn't. AI-created vs human-created items may need different confidence defaults.
**Verdict:** Moderate. Matters for provenance. Not resolved.

---

## Round 2: Against the 4-concept ontology (items, processes, connections, state)

After adding processes as a fourth concept, pressure-tested again.

### CF1: "Items and processes are the same thing"
**Claim tested:** Items and processes are separate top-level concepts.
**Counter:** Both have identity, state, and connections. A process is just an item whose content is a trace and whose connections are produces/consumes. One concept with different type labels might be simpler.
**Verdict:** Strongest hit. The distinction may not earn its keep for v1. An item with type "process" and trace content might suffice.

### CF2: "Produces/consumes makes processes sound like factories"
**Claim tested:** Processes have inputs and outputs.
**Counter:** Real processes don't have clean inputs/outputs. Our sessions started with "where are we?" and ended with 14 emergent docs. Inputs appeared mid-process. Outputs weren't planned. Input→output modeling imposes false linearity.
**Verdict:** Bites. Processes have participants and emergent outputs, not factory inputs. Connection types need revision.

### CF3: "State is a property, not a concept"
**Claim tested:** State is a top-level ontological concept.
**Counter:** State is just attributes on things — metadata, not an entity. Elevating it is artificial.
**Verdict:** Defensible either way. Status + confidence drive everything in Forge. Elevation may be justified pragmatically even if ontologically impure.

### CF4: "The ontology doesn't account for scope"
**Claim tested:** Four concepts cover everything.
**Counter:** Items exist within context — a project, a phase, a workstream. Scope is not an item, process, connection, or state. It's the container. Currently missing.
**Verdict:** Real. May be implicit in hierarchy (CF7 from round 1). Needs resolution.

### CF5: "This looks like a knowledge graph schema, not a product model"
**Claim tested:** The ontology serves Forge's product needs.
**Counter:** Items, connections, state, processes — this is generic knowledge representation. Forge is a "Build me X" pipeline with specific concepts (goals, tasks, plans, agents, checkpoints). The ontology is domain-agnostic. It doesn't encode what makes Forge Forge.
**Verdict:** Real tension. Flexibility vs specificity. The ontology may need product-specific constraints layered on top of generic concepts.

### CF6: "Process types overlap with the verbs"
**Claim tested:** Processes are distinct from the see/change/evaluate verbs.
**Counter:** Discovery, evaluation, synthesis are the verbs nominalized. The ontology has both verbs and process nouns for the same activities.
**Verdict:** Minor. A process is an instantiation of a verb. Naming overlap, not conceptual overlap.

### CF7: "No priority"
**Claim tested:** State dimensions (status, confidence, timestamps) are sufficient.
**Counter:** Which thing matters most right now? Priority was Gap 1 from the original model. Still unresolved. Is it state? A connection? Derived?
**Verdict:** Known gap. Still missing.

### CF8: "Confidence on processes might be circular"
**Claim tested:** Confidence applies cleanly to processes.
**Counter:** Process confidence = "how close to resolution." Resolution is judged by output confidence. Output confidence comes from the process. Feedback loop.
**Verdict:** Real but manageable. Bayesian updates handle sequential evidence. The circularity is temporal, not logical — process confidence at time T informs output confidence at T+1.

---

## Summary

| Counterfactual | Resolution | Status |
|---|---|---|
| Processes aren't items (R1-CF1) | Added processes to ontology | Resolved |
| Items = processes? (R2-CF1) | May collapse for v1. Open question. | Open |
| Connections = items? (R1-CF2) | Open. May be over-modeling. | Open |
| State too coarse (R1-CF3) | Known. Doc-level for v1. | Scoped |
| Types morph (R1-CF4) | Type might be state. | Open |
| Fixed = derived (R1-CF5) | Likely derived from status + confidence | Tentative resolution |
| Time missing (R1-CF6) | Timestamps added | Resolved |
| Hierarchy special (R1-CF7) | Needs resolution | Open |
| Actors missing (R1-CF8) | Matters for provenance | Open |
| Processes aren't factories (R2-CF2) | Produces/consumes too rigid | Open |
| State = property (R2-CF3) | Pragmatic elevation justified | Tentative resolution |
| Scope missing (R2-CF4) | May be implicit in hierarchy | Open |
| Generic not product-specific (R2-CF5) | Tension between flexibility and specificity | Open |
| No priority (R2-CF7) | Gap 1 still unresolved | Open |
| Circular confidence (R2-CF8) | Temporal not logical. Manageable. | Tentative resolution |
