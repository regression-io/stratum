# Detailed Requirements: First Buildable Piece

**Date:** 2026-02-11
**Parent:** [Scope](scope.md)
**Status:** First pass — needs discussion and refinement

---

## R1: Visualize documents and their relationships

### R1.1: Document discovery
The system must find and read all markdown documents in a project folder and its subfolders.

### R1.2: Relationship extraction
The system must identify relationships between documents — links, parent references, and any declared dependencies — and represent them as a navigable graph.

### R1.3: Visual graph
The system must display documents and their relationships as a visual graph, not a file list. The structure of the knowledge should be visible at a glance.

### R1.4: Document metadata
Each node in the graph must show key metadata: title, status, and confidence level. **Why:** These are the dimensions we actually needed when reviewing our docs — "what is this, how done is it, how sure are we."

### R1.5: Incremental updates
When documents change, are created, or are deleted, the graph must update without requiring a manual refresh. **Why:** Claude Code writes files constantly. The visual must keep up.

---

## R2: Navigate by relationship

### R2.1: Open from graph
Clicking a document in the graph must open it for reading. **Why:** The graph is the entry point to content, not just a map.

### R2.2: See connections
For any selected document, the system must show what it links to and what links to it. **Why:** "What depends on this decision?" and "What informed this spec?" are the questions we actually ask.

### R2.3: Filter and find
The user must be able to filter the graph by status, confidence, type, or folder — and search for documents by name or content. **Why:** With 20+ docs, "show me everything tentative" or "find the confidence model" must be fast.

### R2.4: Non-destructive filtering
Filtering should reduce visual noise without destroying spatial context. Filtered-out nodes should fade, not disappear. **Why:** Spatial memory matters. If nodes jump around, you lose your mental map.

---

## R3: Show the state of knowledge

### R3.1: Status at a glance
The graph must visually distinguish documents by status (crystallized, draft, tentative, open, superseded) without requiring hover or click. **Why:** "Where are we?" should be answerable by looking, not reading.

### R3.2: Confidence at a glance
The graph must visually indicate confidence level as a secondary dimension. Unknown confidence must look different from low confidence. **Why:** "How sure are we about this?" is a different question from "how done is it?" Both matter.

### R3.3: Coverage gaps
The system must make it visible where documentation is dense vs sparse — which areas are well-covered, which have gaps. **Why:** We manually built a crystallization review doc. The system should show this automatically.

### R3.4: Orphan detection
Documents with no connections to other documents should be visually flagged. **Why:** An isolated doc is either missing links or doesn't belong. Either way, it needs attention.

---

## R4: Support the terminal-driven workflow

### R4.1: Terminal remains primary
The terminal (Claude Code) must remain the primary input interface. The visual layer augments it — it does not replace it. **Why:** The conversation happens in the terminal. The visuals show what the conversation produces.

### R4.2: AI can update visuals
Claude Code must be able to programmatically highlight nodes, focus the graph on a specific area, and open documents — without the user leaving the terminal. **Why:** When the AI says "let's look at the confidence model and its connections," the visual should respond.

### R4.3: Real-time reflection
File system changes must appear in the visual layer within seconds. **Why:** Claude Code writes files as part of the conversation. The lag between writing and seeing must be imperceptible.

### R4.4: Ambient, not interruptive
Visual updates must never steal focus from the terminal, produce modals, or require acknowledgment. **Why:** The visual layer is a peripheral display, like a second monitor. You glance at it; it doesn't demand attention.

---

## R5: Produce consolidated outputs

### R5.1: Multi-source selection
The user must be able to select multiple documents as source material for synthesis. **Why:** The one-pager was distilled from 18+ docs. Selecting sources is the first step of that workflow.

### R5.2: Synthesis initiation
With sources selected, the user must be able to trigger a synthesis action that feeds those documents to Claude Code. **Why:** "Read these 5 docs and produce a summary" should be a supported workflow, not a manual copy-paste exercise.

### R5.3: Result integration
The synthesized output must appear in the graph as a new document, with visible connections to its source documents. **Why:** The output of synthesis is a new node in the knowledge structure, not a floating artifact.

---

## R6: Maintain structural awareness

### R6.1: Track what's fixed vs transitory
The system must distinguish between crystallized/committed content and in-flight/exploratory content. **Why:** The AI needs to know what it can build on (fixed) vs what might change (transitory). The user needs to see this distinction too.

### R6.2: Phase awareness
The system must be able to represent where the project stands across lifecycle phases (vision, requirements, design, etc.) based on the state of documents. **Why:** "Where are we overall?" should have an answer. Not a human declaration — an inference from what exists and how confident it is.

### R6.3: Stale reference detection
When a document references a decision or direction that has been superseded, the system should flag the stale reference. **Why:** Drift happens silently. Old docs pointing to dead decisions is how confusion accumulates.

---

## Priority ordering

If we can't build everything at once:

1. **R1** — Parse and visualize. The foundation.
2. **R2.1 + R2.2** — Click to open, see connections. Makes the graph useful.
3. **R3.1** — Status at a glance. Makes the graph informative.
4. **R4.3 + R4.4** — Real-time, ambient. Makes the graph alive.
5. **R2.3 + R2.4** — Filtering and search.
6. **R3.2 + R3.3 + R3.4** — Confidence, coverage, orphans.
7. **R4.2** — AI controls the visual layer.
8. **R5** — Synthesis workflow.
9. **R6** — Structural awareness.
