# Compose Roadmap

**Project:** Compose — structured implementation pipeline for AI-driven development
**Last updated:** 2026-02-26

## Related Documents

- [Lifecycle Engine Roadmap](plans/2026-02-15-lifecycle-engine-roadmap.md) — Phase 6 layer detail
- [Architecture Foundation Plan](plans/2026-02-26-architecture-foundation-plan.md) — Phase 4.5 step-by-step plan
- [Agent Connectors Design](features/agent-connectors/design.md) — Phase 4.5 design decisions
- [Original Integration Roadmap](plans/2026-02-11-integration-roadmap.md) — **SUPERSEDED** — preserved for history

---

## Phase 1: Foundation — COMPLETE

Bootstrap: receive and adapt the Base44 UI, achieve first self-hosting milestone.

| # | Item | Status |
|---|------|--------|
| 1 | Receive and evaluate Base44 UI code | COMPLETE |
| 2 | Terminal embed + first boot — crash resilience, supervisor, tmux session persistence | COMPLETE |
| 3 | Discovery Level 2 — vision crystallized, ontology explored, feature map complete | COMPLETE |
| 4 | Core Requirements — Composition model (CR1-CR7), 8 decisions approved | COMPLETE |

---

## Phase 2: Vision Surface — COMPLETE

Five live views, WebSocket updates, drill-down navigation, pressure testing, theme system.

| # | Item | Status |
|---|------|--------|
| 5 | Vision Surface — 5 views (roadmap, list, board, tree, graph), WebSocket live updates | COMPLETE |
| 6 | Roadmap drill-down — explorer breadcrumbs, initiative summaries, status chips, AI insight | COMPLETE |
| 7 | Pressure test system — agent spawn, question workflow, discuss/resolve/dismiss | COMPLETE |
| 8 | Product ontology graph — 10 entity types, 6-phase pipeline visualization | COMPLETE |
| 9 | Theme system — light/dark, CSS tokens, terminal sync | COMPLETE |
| 10 | CLI tooling — vision-track.mjs (create/update/search/connect) | COMPLETE |

---

## Phase 3: Agent Awareness — COMPLETE

Real-time visibility into what the agent is doing, errors it hits, and session lifecycle.

| # | Item | Status |
|---|------|--------|
| 11 | Agent status detection — OSC title parsing, working/idle indicator | COMPLETE |
| 12 | Activity classification — tool tracking, thinking vs executing vs waiting (7 categories) | COMPLETE |
| 13 | Error/outcome detection — pattern-match failures, surface in UI | COMPLETE |
| 14 | Session tracking — start/stop detection, Haiku summaries, auto-journaling hooks | COMPLETE |

---

## Phase 4: Integration & UI Extensions — PLANNED

Connectors to code and agents, persistence evolution, and UI window management. Items 15/17/18
are connector work; item 16 (tab popout) is a UI extension grouped here because it shares
the same dependency window and delivery milestone as the connector work, not because it is a connector.

| # | Item | Status |
|---|------|--------|
| 15 | Git/file connector — link work items to code changes, diff awareness | PLANNED |
| 16 | Tab popout — dockable/undockable tabs to separate monitors *(UI extension)* | PLANNED |
| 17 | Persistence evolution — event-sourced, markdown generation from tracker | PLANNED |
| 18 | Agent connector (read-write) — direct sessions from Compose | **SUPERSEDED by 18a–18h** |

Item 18 is fully replaced by Phase 4.5. It is not independently actionable. 18a–18h are the
complete decomposition of what "agent connector (read-write)" meant at planning time.

---

## Phase 4.5: Architecture Foundation — PLANNED

**Scope boundary:** Delivers the connector *infrastructure* — class hierarchy, MCP tools, Stratum
harness. This is the engineering substrate. Phase 7 builds on this to make the lifecycle itself
agent-agnostic (swap Claude Code for Codex end-to-end). Phase 4.5 wires two specific connectors;
Phase 7 defines the protocol that makes connectors interchangeable.

Deliver the agent connector layer (ClaudeSDKConnector + CodexConnector as MCP tools) with
Stratum as the process harness. No new UI surface. Clean server modularization. Verified end-to-end.

See: [Architecture Foundation Plan](plans/2026-02-26-architecture-foundation-plan.md) for acceptance criteria on all 8 steps.

| # | Item | Status |
|---|------|--------|
| 18a | Architecture alignment — connector class hierarchy, delete codex-server.js, reshape connectors | PLANNED |
| 18b | Integration surface stabilization — agent-mcp.js, claude_run + codex_run MCP tools, .mcp.json | PLANNED |
| 18c | Stratum externalization — pipelines/ directory, review-fix.stratum.yaml, end-to-end run | PLANNED |
| 18d | UI decoupling — verify zero new UI surface; VisionServer SSE stays sole UI channel | PLANNED |
| 18e | Server modularization — split server/ into domain modules, single responsibility per file | PLANNED |
| 18f | Test + observability hardening — golden flow tests for both MCP tools, Stratum audit trace | PLANNED |
| 18g | Cutover + cleanup — remove openai dep, dead code, dangling imports | PLANNED |
| 18h | Acceptance gate — both tools callable; Stratum pipeline completes on a real feature | PLANNED |

---

## Phase 5: Standalone — PLANNED

Compose as an installable tool: LaunchAgent, version-aware restart, CLI + npm distribution.

| # | Item | Status |
|---|------|--------|
| 19 | Standalone app — LaunchAgent, version-aware restart, CLI + npm distribution | PLANNED |

---

## Phase 5.5: Skill Architecture Upgrade — COMPLETE

**Note on ordering:** Phase 5.5 completed before Phase 5 because it was a skill-layer concern
(agent definitions, review protocol) with no dependency on the standalone app. Half-phases are
parallel tracks that surface when significant work fits between two sequential phases. Completion
of 5.5 does not imply completion of 5; 19a (skill arch) and 19 (standalone) are independent.

| # | Item | Status |
|---|------|--------|
| 19a | Agent-based skill architecture — compose-explorer, compose-architect, compose-reviewer agents; competing architecture proposals; confidence-scored review; rename feature-dev → compose | COMPLETE |

---

## Phase 6: Lifecycle Engine — PLANNED

The `/compose` skill becomes the product. Seven layers from user preferences through iteration
orchestration. See: [Lifecycle Engine Roadmap](plans/2026-02-15-lifecycle-engine-roadmap.md).

| # | Item | Status |
|---|------|--------|
| 20 | User preferences inventory — config surface for feature toggles, policy defaults, agent settings | PLANNED |
| 21 | Feature lifecycle state machine — explicit phase tracking per feature, event-driven transitions | PLANNED |
| 22 | Artifact awareness — feature folder management, presence detection, templates, quality signals | PLANNED |
| 23 | Policy enforcement runtime — gate/flag/skip dials as structural enforcement, not prose | PLANNED |
| 24 | Gate UI — interactive approve/revise/kill in Vision Surface, gate queue, trade-offs display | PLANNED |
| 25 | Session-lifecycle binding — sessions tagged to features and phases, contextualized activity | PLANNED |
| 26 | Iteration orchestration — ralph loops as Compose primitive, completion promise monitoring, exit criteria enforcement | PLANNED |

---

## Phase 7: Agent Abstraction — PLANNED (Post-V1)

**Scope boundary:** Phase 4.5 wires concrete connectors (Claude SDK + Codex via OpenCode) as
MCP tools. Phase 7 is distinct: it makes the *lifecycle itself* agent-agnostic — phases, gates,
and artifacts remain identical regardless of which agent runs them. Phase 4.5 is prerequisite
infrastructure; Phase 7 is the abstraction layer built on top of it.

Agent-agnostic lifecycle with agent-specific connectors. Claude Code, Codex, others run the
same pipeline via adapter pattern.

| # | Item | Status |
|---|------|--------|
| 27 | Agent connector interface — capability negotiation, lifecycle-agnostic protocol | PLANNED |
| 28 | Multi-agent connectors — Codex, Gemini, others via adapter pattern | PLANNED |

---

## Dogfooding Milestones

These milestones use sequential labels (D0–D3) that are independent of roadmap phase numbers.

| Milestone | Description | Status |
|-----------|-------------|--------|
| D0: Bootstrap | Manual, out-of-band. Markdown files and chat transcripts. | COMPLETE |
| D1: Self-tracking | Compose tracks its own work via Vision Surface (114+ items, 136+ connections). | COMPLETE |
| D2: Self-aware | Agent monitoring feeds session activity into the tracker automatically. | ACTIVE |
| D3: Self-directing | Lifecycle engine enforces the compose process structurally. All work happens in Compose. | PLANNED |
