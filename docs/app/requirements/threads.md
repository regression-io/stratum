# Implementation Threads

**Parent:** [Requirements](README.md)
**Purpose:** Threads raised during requirements that belong in design/implementation. Parked here, not forgotten.

---

## T1: "Ghetto" knowledge graph vs graph DB

**Raised:** Session 7
**Question:** Should we build and maintain a lightweight knowledge graph using basics (markdown files, parsed links, in-memory graph) rather than a proper graph database?

**Current direction:** Yes, start simple. Markdown files on disk are the source of truth. In-memory graph built from parsing frontmatter + links. File watcher for incremental updates. Connector architecture allows swapping later.

**Sub-questions for design:**
- How to index? Parse on startup + file watcher for incremental updates?
- How to query? Simple traversal (neighbors, paths) vs complex queries (filter by status AND confidence)?
- How to handle derived data? (bidirectional link maps — A links to B implies B is linked-from A)
- At what scale does this break? 50 docs? 200? 1000?

**Connects to:** [Scope](scope.md) architecture constraints, [Needs](needs.md) ontology (the KG implements the ontology)
