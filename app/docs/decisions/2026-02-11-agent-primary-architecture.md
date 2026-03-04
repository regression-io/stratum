# Decision: Agent-Primary Architecture

**Date:** 2026-02-11
**Status:** DECIDED
**Context:** Determining the minimum bootstrap configuration for Compose
**Related:** [Integration Roadmap](../plans/2026-02-11-integration-roadmap.md), [Bootstrap Progress](../evaluations/2026-02-11-bootstrap-progress.md)

---

## Question

What is the minimum bootstrap configuration to make Compose usable for its own development?

## Previous Answer (superseded)

Build persistence infrastructure first (REST API, markdown connector, auth stub), then wire it to the UI, then use the UI to track work. Agent interaction comes later as a Phase 4 connector.

## Decision

**Agent-primary architecture.** The embedded agent panel is the primary write interface. The structured UI (tree, board, graph, detail) is the primary read interface with quick-write for simple interactions. Both backed by the same `.compose/` persistence.

The bootstrap reduces to two hard prerequisites:
1. Wire persistence (UI ↔ `.compose/`)
2. Embed agent panel in the UI

Everything after that is built FROM INSIDE Compose using those two capabilities.

## Rationale

1. **The mechanism compounds.** Every feature Compose needs — onboarding, evaluation templates, policy engine, new views, new connectors — can be built by the agent through the agent panel. Investing in the mechanism has unbounded ROI vs fixed ROI per feature.

2. **Self-modification is the product.** Compose with an embedded agent can extend its own UI, build its own connectors, create other apps. The distinction between "manage the work" and "do the work" is artificial — the same environment hosts both.

3. **Process docs become executable.** delivery-intake.md, spec-writing.md are already agent instructions. The agent follows them when asked. No process engine to build — the agent IS the process engine.

4. **Policy ≈ agent permissions.** The gate/flag/skip Policy primitive maps directly to agent permission models (approve/notify/autonomous). Same concept, already implemented in Claude Code.

5. **The invariant/variant split is the platform/app split.** Invariants (Work, Policy, Session, hierarchy, dependencies) are the platform. Variants (views, templates, workflows) are apps the agent builds on the platform.

6. **We're already doing it.** This brainstorming session happened in Claude Code modifying the Compose codebase. The only gap is that the terminal is beside the browser, not inside it.

## What This Changes

| Concern | Before | After |
|---------|--------|-------|
| Onboarding | Build onboarding UI | Agent conversation |
| Complex creation | Build form wizards | Agent conversation |
| Process enforcement | Build policy engine | Agent follows process docs |
| New features | Spec → build → evaluate → wire | Tell the agent, it builds in-place |
| New views | Manual development | Agent creates, Vite reloads |
| Other apps | Out of scope | Agent builds them too |

## What This Doesn't Change

- The Compose UI design is still valid (invariant analysis, 5 views, dark theme, information density)
- The persistence layer (markdown-in-folders) is still the right storage
- The process docs are still the process layer
- The taxonomy (phase, type, status lifecycle) is still the domain model

## Rejected Alternatives

1. **Infrastructure-first bootstrap** — Build persistence → onboarding → templates → policy engine → then use. Rejected because: linear, slow, no compounding. Each feature is a fixed investment.

2. **Agent-only, no structured UI** — Just a terminal that writes files. Rejected because: the invariant analysis produced genuinely useful visualization (tree, graph, board). The UI is the cockpit, the agent is the copilot. Neither replaces the other.
