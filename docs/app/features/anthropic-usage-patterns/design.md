# Anthropic Internal Usage Patterns — Adoption Decisions

**Status:** PLANNED
**Roadmap items:** Phase 6 (Lifecycle Engine) — items 23–26; Near-term — CLAUDE.md hardening, session hook improvement

## Related Documents

- [MCP Connector + Ecosystem Learnings](../mcp-connector/design.md) ← parallel learning doc
- [Lifecycle Engine Roadmap](../../plans/2026-02-15-lifecycle-engine-roadmap.md) ← this doc informs items 23–26
- [Session Tracking Design](../../plans/2026-02-14-session-tracking-design.md) ← this doc informs session hook

---

## Context

On 2026-02-24 we read Anthropic's internal "How Anthropic teams use Claude Code" report — 10 teams, 22 pages of concrete workflow patterns from Anthropic's own engineers, designers, data scientists, and lawyers. Unlike external benchmark data, this is usage evidence from teams dogfooding the tool at depth across vastly different problem domains.

This doc captures the adoption decisions that bear directly on Forge's architecture, with a focus on three areas: **Phase 6 design assumptions** (ralph loops, policy enforcement, gate UI), **near-term CLAUDE.md hardening**, and **session hook improvements**.

Source: `https://www-cdn.anthropic.com/58284b19e702b49db9302d5b6f135ad8871e7658.pdf`

---

## Adoption Decisions

### Decision 1: Async/sync task classification = Forge's gate/flag/skip dial (validates Phase 6)

**What the report showed:** The Claude Code team (Anthropic's own product team) explicitly articulates a two-mode model: peripheral features and prototyping → "auto-accept mode" (fully autonomous); core business logic and critical fixes → "synchronous supervision" (agent leads, human steers in real-time). They describe "develop task classification intuition" as a skill users must learn.

**Why it matters for Forge:** This is external validation of Forge's core design primitive — the 3-mode dial (gate / flag / skip). Anthropic's own engineers arrived at the same classification independently. The failure mode they identify is identical to what Forge's policy enforcement is designed to prevent: agents making "unexpected changes to the wrong parts of the codebase" when the human hasn't specified supervision level.

**The framing Forge should adopt:** Rather than presenting the dial as a policy configuration, the UI and skill should frame it as "task classification" — a judgment the user makes about this feature's position on the autonomy spectrum. The gate UI (item 24) should surface this as the primary decision when a new feature phase begins.

**Decision:** Phase 6's policy enforcement (item 23) and gate UI (item 24) should use "task classification" as the user-facing language. The dial positions map as:
- **Skip** = "auto-accept" zone (peripheral features, prototyping, refactoring)
- **Flag** = "supervised autonomy" zone (most implementation work)
- **Gate** = "synchronous" zone (core business logic, security-critical changes)

**Acceptance criteria:**
- [ ] Gate UI labels the three modes with user-facing language that matches the async/sync mental model
- [ ] forge skill prompts for task classification at phase-start, not buried in configuration
- [ ] CLAUDE.md documents the classification heuristics so agents can self-classify when policy is "flag"

---

### Decision 2: Ralph loop design — 1/3 first-attempt success rate + correction spiral detection

**What the report showed:** RL Engineering (the team most similar to Forge's ralph loop use case) gives concrete data: autonomous implementation works on first attempt "about one-third of the time." Their strategy: give Claude a quick prompt and let it attempt the full implementation first; if it works, time saved; if not, switch to a more collaborative, guided approach. Data Science adds: "Starting over often has a higher success rate than trying to fix Claude's mistakes."

**Why it matters for Forge:** The current ralph loop schema (`maxIterations: 20`) doesn't distinguish between productive iteration and correction spirals. If an agent spends 8 iterations debugging a mistake it introduced in iteration 2, those aren't productive iterations — they're compounding noise. The slot machine framing from Data Science is important: commit state, attempt, then accept or restart cleanly.

**Decision:** Forge's ralph loop design (item 26) should incorporate:

1. **Two-phase attempt model:** First attempt is one-shot, fully autonomous. If `tasks[0].result` indicates failure or partial, the loop driver signals Phase 2 (collaborative, guided) rather than continuing to iterate on the same approach.

2. **Correction spiral detection:** If the same task has been `in_progress` for more than N iterations without a `complete` result, emit a `spiral_detected` event and pause for human input rather than continuing.

3. **Commit checkpoint before loop start:** The forge skill must commit current state before starting any ralph phase. This is non-negotiable — it's the recovery point.

Updated loop state schema:

```json
{
  "loopId": "loop-<timestamp>",
  "featureId": "tracker-item-id",
  "phase": "implementation",
  "attempt": 1,
  "maxAttempts": 2,
  "tasks": [...],
  "currentTaskIndex": 0,
  "iteration": 1,
  "maxIterations": 20,
  "exitCriteria": "all tasks complete, tests passing",
  "spiralThreshold": 4,
  "startedAt": "...",
  "updatedAt": "...",
  "lastResult": "...",
  "commitCheckpoint": "abc1234"
}
```

**Acceptance criteria:**
- [ ] forge skill creates a git commit checkpoint before starting any ralph phase
- [ ] Loop driver has `spiralThreshold` — if a task has been retried more than N times without completion, pause and emit `spiral_detected`
- [ ] Loop driver supports `maxAttempts` — second attempt switches to collaborative mode (more detailed prompting) rather than identical retry
- [ ] `commitCheckpoint` stored in loop state so the forge skill can run `git reset --hard <checkpoint>` on full loop failure

---

### Decision 3: CLAUDE.md anti-pattern injection — negative instructions beat principles

**What the report showed:** RL Engineering's most concrete tip: add specific wrong behaviors to CLAUDE.md, not just guiding principles. Their example: *"run pytest not run and don't cd unnecessarily — just use the right path."* They report this "significantly improved consistency." This is qualitatively different from positive instructions — you're preventing a specific observed failure mode.

**Why it matters for Forge:** Our current CLAUDE.md is principle-heavy and light on negative constraints. We've seen specific failure patterns in our own sessions (e.g., agents writing to wrong files, using xterm APIs after the migration) that belong as explicit anti-patterns.

**Decision:** Add an `## Anti-Patterns` section to Forge's CLAUDE.md listing specific wrong behaviors observed in sessions. Each entry should be a single line: what not to do and why. This is a living section — agents and humans should add to it when they observe a new failure mode.

**Immediate entries to add:**
- Never use `cd` before a command — use absolute paths instead
- Never modify `vite.config.js` or `server/supervisor.js` without stating the risk
- Never create new components without checking if an equivalent exists in `src/components/`
- Never write to `data/` JSON files directly — use `vision-track.mjs` or the REST API
- Never add `Co-Authored-By` lines in commits (already in code-standards.md but worth mirroring)

**Acceptance criteria:**
- [ ] `## Anti-Patterns` section added to project `CLAUDE.md`
- [ ] At least 5 entries from observed session failure modes
- [ ] Section header instructs agents to add new entries when they observe failure modes

---

### Decision 4: Session end hook → CLAUDE.md improvement suggestions

**What the report showed:** Data Infrastructure's end-of-session loop: ask Claude to summarize completed work sessions AND suggest CLAUDE.md improvements at the end of each task. This creates a continuous improvement cycle — "making subsequent iterations more effective." The CLAUDE.md improves based on actual usage, not just upfront design.

**Why it matters for Forge:** Our session end hook already writes journal entries and triggers haiku summaries. We're one prompt extension away from having the session-end agent also propose CLAUDE.md additions. This closes the loop from "observed failure" → "anti-pattern in CLAUDE.md" without requiring the human to remember to do it.

**Decision:** Extend the session-end hook haiku prompt to include a secondary task: "If this session revealed any repeated mistakes, tool misuse, or workflow anti-patterns, suggest 1-3 additions to the project CLAUDE.md `## Anti-Patterns` section." Output as a separate JSON field `claudeMdSuggestions: string[]`.

The suggestion is advisory — it should surface in the session summary in the UI but not auto-write to CLAUDE.md. The human approves before any anti-pattern is added.

**Acceptance criteria:**
- [ ] Session-end haiku prompt includes CLAUDE.md suggestion task
- [ ] `claudeMdSuggestions` field in session data model (may be empty)
- [ ] Session summary in UI surfaces suggestions as a collapsible "Suggested CLAUDE.md additions" section
- [ ] No auto-write — user approves before anything is written

---

### Decision 5: Checkpoint-heavy commit workflow is a first-class primitive

**What the report showed:** Two independent teams (Data Science and RL Engineering) converge on the same pattern from different angles:
- Data Science: "Treat it like a slot machine — save your state, let it run 30 minutes, accept or start fresh."
- RL Engineering: "Use a checkpoint-heavy workflow — regularly commit your work as Claude makes changes."

Both frame it as *enabling* a more experimental approach, not constraining it. The commit checkpoints reduce the cost of being wrong, which raises the risk tolerance for ambitious autonomous tasks.

**Why it matters for Forge:** The forge skill currently mentions committing but doesn't enforce or automate it. For ralph loops especially, the checkpoint rhythm should be prescribed: commit before phase start (already in Decision 2), and the loop driver should prompt for a commit at each task completion boundary.

**Decision:** The forge skill should emit a structured "checkpoint opportunity" signal at each task completion boundary within a ralph loop. The signal surfaces in the UI as a non-blocking notification: "Task N complete — commit checkpoint?" This is not a gate (which would block the loop) but a flag-mode nudge.

**Acceptance criteria:**
- [ ] forge skill emits `checkpoint_opportunity` event at each ralph task completion
- [ ] AgentPanel or Vision Surface surfaces the opportunity as a non-blocking pill/badge
- [ ] User can dismiss or trigger `git commit` directly from the UI
- [ ] Not a gate — loop continues whether or not user acts on the checkpoint

---

### Decision 6: Sub-agent specialization — narrow scope improves debug-ability

**What the report showed:** Growth Marketing built two separate agents for ad generation — one for headlines, one for descriptions — specifically because it "makes debugging easier and improves output quality when dealing with complex requirements." The specialization is about failure isolation, not just capability.

**Why it matters for Forge:** Phase 5.5's forge-explorer/forge-architect/forge-reviewer split was motivated by quality. This report adds a second motivation: **when a sub-agent fails, you know exactly which capability failed**. A monolithic agent that explores + architects + reviews produces errors that are hard to attribute. Specialized agents produce errors that are easy to route.

**Decision:** Forge's agent architecture (Phase 7) should treat narrow scope as a design constraint, not just a capability grouping. When designing new agents, the primary question is: "If this agent fails, can the human immediately understand why?" If not, the scope is too wide.

**Acceptance criteria:**
- [ ] Agent definition guideline added to `.claude/rules/` documenting scope-narrowness as a design principle
- [ ] Existing forge-explorer/architect/reviewer agent definitions reviewed against this principle before Phase 7

---

### Decision 7: MCP servers as security boundary, not just convenience

**What the report showed:** Data Infrastructure recommends MCP servers *specifically* for sensitive data access because they provide **security control, logging, and access restriction** that direct CLI calls don't. This reframes MCP servers from "convenient abstraction" to "security boundary." Legal adds: "as product lawyers, they immediately identify security implications of deep MCP integrations — conservative security postures will create barriers as AI tools access more sensitive systems."

**Why it matters for Forge:** `forge-mcp.js` currently reads data files with no access control. As Forge grows toward Phase 5 (standalone, multi-user), the MCP server will need to gate what agents can read. The design principle to establish now: the MCP server is the **only** sanctioned way for agents to read Forge tracker state — not direct file reads, not REST API calls from hooks.

**Decision:** Add a note to `forge-mcp.js` and the design doc establishing it as the agent data access boundary. Direct reads of `data/vision-state.json` by agent hooks should be eliminated over time. If an agent needs tracker context, it goes through MCP.

**Acceptance criteria (long-term):**
- [ ] `forge-mcp.js` is documented as the canonical agent data access layer
- [ ] agent-hooks.js does not read vision-state.json directly (it currently doesn't — maintain this)
- [ ] Future MCP tools that write (not just read) go through the same server with authentication

---

## Near-Term Implementation Order

1. **CLAUDE.md anti-patterns section** — 30 minute edit. Immediate consistency improvement. No dependencies.
2. **Session hook CLAUDE.md suggestions** — 2–3 hour change to session-end haiku prompt + data model + UI. Closes the feedback loop.
3. **Ralph loop schema update** — Update `.claude/loop-state.json` schema in `docs/features/mcp-connector/design.md` Decision 3 to include `attempt`, `maxAttempts`, `spiralThreshold`, `commitCheckpoint`. Design-only change before Phase 6 implementation.

## Phase 6 Design Implications Summary

| Phase 6 Item | Implication |
|---|---|
| Item 23 — Policy enforcement | Use "task classification" framing (async/sync) in UX, not dial metaphor |
| Item 24 — Gate UI | Classification prompt at phase-start is the primary UX surface |
| Item 26 — Iteration orchestration | Add two-phase attempt model, spiral detection, commit checkpoint |
| Item 25 — Session-lifecycle binding | Add `claudeMdSuggestions` to session data model now |

---

## What We're Not Adopting

| Pattern | Why not |
|---|---|
| "Planning in Claude.ai, building in Claude Code" as a literal two-app flow | Forge collapses both into one surface — the forge skill runs discovery and implementation in the same session |
| Parallel instances across repos | Forge is single-repository; session isolation is by phase, not worktree |
| GitHub Actions auto-ticketing | Forge manages its own lifecycle internally; GitHub is an output connector, not input |
| Memory systems (Growth Marketing experiment) | Decision 4 from MCP connector doc applies — measure noise vs. signal before shipping |
