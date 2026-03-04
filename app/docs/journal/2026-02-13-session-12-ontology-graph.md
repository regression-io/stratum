# Session 12: The Ontology Takes Shape

> 2026-02-13 · Product realignment, graph renderer, ontology validation

## What happened

We stepped back from the Vision Surface UI and went structural. The flat item model in the prototype was always going to break at scale — 50 items across multiple workstreams is noise. The question was: what replaces it?

The answer: a DAG. Not a tree, not a hierarchy — a directed acyclic graph of 7 entity types connected by 8 edge types. We wrote the product realignment doc that supersedes the flat item model, mapping everything from the SmartMemory ROADMAP (battle-tested structure) and the feature-development skill (battle-tested lifecycle).

The key insight was that the Initiative → Feature → Task tree is one *view* of the graph, not the graph itself. Ideas can float free. Threads can inform 5 Features across 3 Initiatives. A Question can block a Feature and also question an Initiative's scope. The graph holds everything; views filter it.

Then we built a way to see it. GraphRenderer.jsx is a general-purpose Cytoscape DAG renderer styled like Compose — dark cards with colored borders, monospace fonts, the whole token palette. ProductGraph.jsx feeds it the ontology data. Six layout algorithms, zoom controls, a legend with entity toggles and edge style explanations. It lives in a `graph://` Canvas tab alongside markdown and Vision Surface.

We validated the ontology against 25 use cases — everything from "developer starts a new project" to "AI agent proposes killing a blocked feature" — and built 4 matrices: entity coverage, edge coverage, CR1-CR7 alignment, and completeness. Found 5 gaps, fixed 2 in-session: `belongs_to` needed to be explicitly many-to-many, and every entity needed a `confidence` field that's both lifecycle-derived and explicitly overridable. The user's "why not both?" killed a false dichotomy we were constructing.

Meanwhile, the Vision Surface got sort/group controls in list view and a connection sub-graph in the detail panel showing neighborhood topology. The graph view renders the full DAG with Cytoscape.

## What we built

### New files
- `docs/design/2026-02-13-product-realignment.md` — The graph-based data model (7 entities, 8 edges, DAG structure, Feature lifecycle, 3-mode dial, semantic IDs)
- `docs/design/2026-02-13-ontology-validation.md` — 25 use cases, 4 matrices, 5 gaps analyzed
- `src/components/GraphRenderer.jsx` — General-purpose Cytoscape DAG renderer with Compose styling
- `src/components/ProductGraph.jsx` — Ontology data feeding GraphRenderer
- `src/components/vision/ConnectionGraph.jsx` — Detail panel neighborhood sub-graph
- `src/components/vision/GraphView.jsx` — Full DAG view in Vision Surface
- `scripts/vision-hook.sh` — Hook for auto-tracking vision items

### Modified files
- `src/components/Canvas.jsx` — `graph://` tab support (import, displayName, content rendering)
- `server/file-watcher.js` — `graph://` scheme handler in canvas open API
- `server/vision-server.js` — CRUD API endpoints for vision items
- `src/components/vision/ItemListView.jsx` — Sort/group controls (phase/type/status/none × confidence/updated/status/A-Z)
- `src/components/vision/ItemDetailPanel.jsx` — Connection sub-graph, enhanced detail
- `src/components/vision/VisionSurface.jsx` — Graph view integration
- `scripts/vision-track.mjs` — Expanded CLI for vision tracking
- `package.json` — Added cytoscape, cytoscape-dagre, layout-base dependencies

## What we learned

1. **The tree is a view, not the model.** The graph holds Ideas floating free, Threads informing multiple Features, Decisions resolving Questions across Initiatives. The Initiative → Feature → Task tree is one lens, not the structure.

2. **Confidence is both derived and explicit.** A Feature in Verification has high implicit confidence, but if the tests are shaky, the explicit override can say 2. "Why not both?" killed a false dichotomy.

3. **Edge style carries meaning.** Solid = structural/hard dependency (blocks, implements, belongs_to). Dashed = informational/weak coupling (informs, produces). Dotted = soft dependency (sequencing). The visual encoding communicates relationship strength.

4. **Validation before building.** Testing the ontology against 25 use cases before implementing it as data structures caught real gaps (many-to-many belongs_to, missing confidence field) that would have been harder to fix later.

5. **Server process hygiene matters.** Multiple stale supervisor processes from different sessions caused 404s. Had to `lsof` the actual port, kill the right PID, and wait for supervisor restart.

## Open threads

- [ ] Implement the DAG data model in the actual persistence layer (currently vision-state.json is flat items)
- [ ] Migrate Vision Surface from flat items to entity+edge model
- [ ] G1: `supersedes` edge type (low priority, handle with status + comment)
- [ ] G4: Session entity (deferred — track as metadata on artifacts)
- [ ] Wire ProductGraph to show actual project data, not just the ontology schema
- [ ] Keyboard shortcuts for graph navigation

---

*The ontology is the map. Now we need the territory.*
