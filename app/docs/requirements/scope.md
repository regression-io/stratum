# Scope: First Buildable Piece

**Date:** 2026-02-11
**Parent:** [Requirements](README.md)
**Source:** Session 6 discussion — dogfooding, "what do we need right now?"
**Status:** Draft — needs discussion

---

## Context

We've been building Compose's vision using Claude Code in a terminal + a basic markdown canvas. It works but the value is in the conversation, not the UI. The UI adds almost nothing beyond file viewing.

The first buildable piece should provide **visual value that the terminal can't** — specifically, the visual structure needed to do what we've been doing (discovery, synthesis, tracking) but better.

---

## What must the first buildable piece support?

### R1: Visualize documents and their relationships

The system must:
- Read a folder of markdown documents
- Parse relationships between documents (markdown links, parent references in frontmatter, `informs` links)
- Display the graph of relationships visually (not just a file list)
- Show document metadata: date, status, confidence level (from frontmatter)

**Why:** We have 20+ discovery docs with cross-references. Navigating them by filename is unusable. The relationships ARE the knowledge structure — you need to see them.

### R2: Navigate by relationship, not just file path

The system must:
- Allow clicking a node in the graph to open the document
- Show what a document links to and what links to it (bidirectional)
- Support filtering or highlighting by status, confidence, type, or date

**Why:** "What does the confidence model connect to?" is a relationship question. Today we grep for links. The UI should answer this visually.

### R3: Show the state of knowledge

The system must:
- Surface status and confidence from document frontmatter
- Visually distinguish crystallized vs open vs tentative items
- Show coverage — which areas have documents, which are empty or thin

**Why:** We built a crystallization review doc manually. The UI should show this at a glance. "Where are we?" should be answerable by looking at the map, not reading 5 docs.

### R4: Support the terminal-driven workflow

The system must:
- Keep the terminal as the primary input (Claude Code stays the engine)
- Allow Claude Code to update visual state via API (open docs, update metadata, create docs)
- Reflect file system changes in real time (file watcher already exists)
- Not require the user to leave the terminal to interact with the visual layer

**Why:** We're not replacing Claude Code. We're augmenting it with a visual layer. The conversation happens in the terminal. The visual layer shows what the conversation produces.

### R5: Produce consolidated outputs from multiple sources

The system must:
- Support selecting multiple source documents
- Allow Claude Code to synthesize them into a new document
- Display the new document in the canvas and update the map

**Why:** The one-pager was produced by reading 18+ docs and distilling them. That synthesis process should be supported, not manual.

### R6: Maintain structural awareness as the user works non-linearly

The system must:
- Track where work stands across all levels (vision, requirements, design, etc.) in the background
- Recognize when a phase transition has occurred — not as a sharp event, but by recognizing when the bridge has been crossed (output artifacts produced, confidence levels shifted based on conversation and tasks)
- Know what's fixed (crystallized decisions, committed direction) vs what's transitory (in-flight exploration, tentative claims)
- Be able to steer back to structure when the user has drifted or jumped across levels
- Not force the user to follow a linear process — the structure is for the AI, not the human

**Why:** People don't stick to structured processes. They jump back and forth across levels — refining vision while writing requirements, discovering design constraints while planning. The AI needs to maintain the structural backbone regardless, so it can keep its own reasoning on rails and gently guide the user when coherence is at risk. The rails are for the AI. The human works fluidly.

**Connects to:** [Rails Architecture](../discovery/discovery-process/rails-architecture.md) (enforcement mechanism, background sub-agent), [Phase transitions](../discovery/discovery-process/model-gaps.md) (Gap 5)

---

## What's OUT for v1?

- Confidence visualization beyond simple color/label (no sparklines, no Bayesian computation)
- Claim-level tracking within documents (doc-level only)
- Pipeline visualization (no Kanban, no status flow)
- Multi-user / permissions
- External connectors (GitHub, CI/CD)
- Agent orchestration beyond the existing terminal embed
- Formal knowledge graph database (markdown files are the store)
- Mobile or responsive design (desktop only)

---

## Architecture constraints

- Must work with what we have: React frontend, Express server, WebSocket, file watcher
- Documents are markdown files on disk — no separate database for v1
- Claude Code is the AI engine — no separate AI integration needed
- The graph/map visualization is new UI — needs a library choice (D3? React Flow? Something else?)

---

## Open questions

- What frontmatter schema do we need? Status and confidence at minimum. What else?
- How much of the graph is auto-derived from markdown links vs explicitly declared?
- Does the map replace the current canvas tabs, or sit alongside them?
- How does "select multiple docs for synthesis" work in the UI?
- What's the layout? Terminal left, map center, canvas right? Or something else?

---

## Success criteria

**The first buildable piece is successful if:**
1. We can open Compose and see the discovery-process folder as a visual graph
2. We can click a node and read the document
3. We can see at a glance which docs are crystallized vs tentative vs open
4. Claude Code can create/update docs and the map updates in real time
5. We use Compose instead of raw terminal + file browser for the next session
