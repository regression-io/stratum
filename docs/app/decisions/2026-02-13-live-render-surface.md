# Decision: Vision Surface Is a Live Render Surface, Not a Tracker

**Date:** 2026-02-13
**Status:** Approved
**Related:** [PRD](../PRD.md), [functionality-vs-usecases](../evaluations/2026-02-13-functionality-vs-usecases.md), [feature-map](../discovery/discovery-process/feature-map.md)

---

## Context

After building 6 views (Roadmap, List, Board, Tree, Graph, Docs), 100 items, 129 connections, and a full REST+WebSocket server, the question arose: are we reinventing JIRA? Most of what we'd built — item CRUD, status lifecycles, hierarchy, kanban board, filtering — is commodity project tracking. A JIRA/Linear connector could provide it.

## Decision

The Vision Surface is not a project tracker. It is a **live render surface for agent activity**. Owning the UI is justified by capabilities no connector model can provide:

### Why we own the UI

1. **Sub-second latency.** Agent creates item → WebSocket broadcast → surface updates in ~100ms. JIRA API round-trips take 2-5 seconds plus sync delays. The difference is "watching things happen" vs "refreshing to check."

2. **Real-time animation.** Items slide into view when created. Status changes animate across columns. Connections draw between nodes. Progress rolls up as children complete. This is mission control — you observe the work happening, not review a snapshot of it.

3. **Tight bidirectional feedback loop.** Agent acts → user sees in 100ms → user approves/rejects → agent sees in 100ms. The 3-mode dial (gate/flag/skip) becomes a real-time conversation at sub-second latency, not an async workflow.

4. **UI as context.** The snapshot API captures what the user is looking at — active view, selected phase, filtered items, selected item. This feeds back to the agent as context. JIRA cannot tell an agent "the user is currently reviewing the implementation phase of Feature 3."

5. **Custom interaction patterns.** Roadmap drill-down with inline approve/decline. Graph view animating as connections form. Terminal creating items that appear on the surface beside it. These are integration points between agent execution and human oversight that don't exist in any connector model.

### What this means for build priorities

- **CRUD, filtering, status management** are commodity. Build them, but don't over-invest. They're the substrate, not the product.
- **Animation, real-time updates, visual feedback** are the product. Every agent action should have a visible, immediate, animated response on the surface.
- **The feedback loop** (agent → surface → human → agent) at sub-second latency is the core differentiator. Every feature should tighten this loop.
- **Connectors to JIRA/Linear** remain valid for teams that want external tracking. Compose is the live view; the external tool is the record of truth for non-agent stakeholders.

### What this means for type proliferation

Stop adding item types. The PRD says Work is one primitive with user-defined labels. Ten types (feature, track, idea, decision, question, thread, artifact, task, spec, evaluation) is already too many for the data model — the surface should handle any label, not bake in specific ones. The visual language (colors, icons, layout) can vary by label without the data model caring.

## Rejected Alternative

**Use JIRA as the tracker, build Compose only as an agent-native overlay.** Rejected because the latency and animation capabilities require owning the render pipeline. A connector-based approach caps the feedback loop at JIRA's API speed and UI conventions.

## Consequences

- Animations and real-time visual feedback become first-class concerns, not polish
- Every new feature is evaluated against "does this tighten the agent↔human feedback loop?"
- The snapshot API (UI state introspection) becomes a core capability, not a utility
- JIRA/Linear connectors are additive (export/sync), not foundational
