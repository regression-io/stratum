# Developer Journal

The story of how Compose was built, told as it happened.

Each entry is a dated session log capturing what we tried, what broke, what we learned, and what we decided. Written in the first person plural — the human and the agent, building together.

**Why this exists:** Compose is a tool for tracking knowledge work. The best way to test that thesis is to capture our own. This journal is raw material — the kind of thing Compose's conversation distillation feature (Phase 3.2) would eventually automate.

## Entries

| Date | Entry | Summary |
|------|-------|---------|
| 2026-02-11 | [Session 0: The Planning Marathon](2026-02-11-session-0-planning.md) | Product concept through architecture decision, all in one session |
| 2026-02-11 | [Session 1: First Boot](2026-02-11-session-1-first-boot.md) | First real run, crash, diagnosis, self-healing infrastructure |
| 2026-02-11 | [Session 2: The WebSocket Bug Hunt](2026-02-11-session-2-websocket-bugs.md) | Permissions, restart loop, frame corruption, three-layer resilience |
| 2026-02-11 | [Session 3: The Session That Survives Refresh](2026-02-11-session-3-session-persistence.md) | PTY decoupled from WebSocket, session persistence through browser refresh |
| 2026-02-11 | [Session 5: The Discovery About Discovery](2026-02-11-session-5-level-2-discovery.md) | No code, 14 docs. Expanded to 4 primitives, Bayesian confidence, features restructured. Pure discovery session. |
| 2026-02-11 | [Session 6: The Vision Inversion](2026-02-11-session-6-vision-inversion.md) | Confidence model used for real, 6 counterfactuals, vision statement crystallized. Agent had priorities inverted — human corrected. Pipeline is core, discovery is on-ramp. |
| 2026-02-11 | [Session 7: Requirements Emerge](2026-02-11-session-7-requirements-emergence.md) | Rails are for the AI. Composition model: 7 phases × 7 things × 4 verbs × 8 processes × 5 lenses = CR1-CR7. 30+ counterfactuals across 3 rounds. Agent kept drifting upward, human kept pulling back. |
| 2026-02-11 | [Session 8: Vision Spec → Design → The Jigsaw](2026-02-11-session-8-vision-spec.md) | Spec with provenance. Acid test = improvement + delight. Jigsaw not bridge — pipeline has no build order. Iterative vs waterfall is a false dichotomy; the 3-mode dial controls how it feels. Pipeline is descriptive, not prescriptive. |
| 2026-02-12 | [Session 9: The Glow](2026-02-12-session-9-vision-surface-glow.md) | Vision surface wired up and visible. Glow design iterated from static heat → depth animation → click-to-ripple. Design through conversation, not specification. Filter bug fixed. |
| 2026-02-12 | [Session 10: The Sidebar Rebuild](2026-02-12-session-10-sidebar-rebuild.md) | Previous session broke the app. Wrote incremental builds rule. Rebuilt vision surface with shadcn/ui: sidebar + list view + detail panel. Base44 patterns, Compose color scheme. App never broke. |
| 2026-02-12 | [Session 11: Two-Mode Vision Surface](2026-02-12-session-11-two-mode-surface.md) | Discovery + Execution modes. Vision tracking infrastructure. Triple code review, 16 fixes. Same surface, two faces — one for thinking, one for building. |
| 2026-02-13 | [Session 12: The Ontology Takes Shape](2026-02-13-session-12-ontology-graph.md) | Product realignment: flat items → DAG with 7 entity types, 8 edge types. Graph renderer with Cytoscape. Validated against 25 use cases. Confidence is both derived and explicit. The tree is a view, not the model. |
| 2026-02-13 | [Session 13: The Infrastructure Session](2026-02-13-session-13-infrastructure.md) | Breadcrumbs, compose-loop, vision tracker design, terminal usability, mockup infrastructure. The session that built the rails everything else runs on. |
| 2026-02-13 | [Session 14: The Drill-Down Build](2026-02-13-session-14-drilldown.md) | Two-tier terminal, roadmap drill-down spec + build (849+423 lines), data population, 6 critical bug fixes, taxonomy rename, 66 orphaned items wired. |
| 2026-02-13 | [Session 15: The Pressure Test](2026-02-13-session-15-pressure-test.md) | Agent spawn for hidden Claude subprocesses. Pressure test → discuss → resolve workflow. System tested itself, changed its own mind: options are children, not edges. Resolution sparkle, revision history, CSS token sizing. |
| 2026-02-14 | [Session 16: Agent Awareness](2026-02-14-session-16-agent-awareness.md) | OSC status detection, tool categories, hook-driven activity feed, activity resolution (file-to-item matching), auto-status progression. The tracker now knows what feature you're building. |
| 2026-02-14 | [Session 17: Skill Surgery](2026-02-14-session-17-skill-surgery.md) | Error detection (Phase 3 Step 13), feature-dev v2 rewrite (16 design decisions), redundancy audit killed compose-loop, hooks disabled for context cost. Tools making tools, then pruning tools that were just other tools in disguise. |
| 2026-02-15 | [Session 18: Skill Architecture Upgrade](2026-02-15-session-18-skill-architecture.md) | Anthropic's official feature-dev plugin discovered, compared, ideas adopted. 3 dedicated agents (compose-explorer, compose-architect, compose-reviewer), competing architecture proposals, confidence-scored review, renamed feature-dev → compose. |
