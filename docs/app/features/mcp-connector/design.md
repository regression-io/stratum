# MCP Connector + Ecosystem Learnings

**Status:** PLANNED
**Roadmap items:** Phase 4 (Connectors) — items 15–18; Phase 6 (Lifecycle Engine) — items 20–26

## Related Documents

- [Lifecycle Engine Roadmap](../plans/2026-02-15-lifecycle-engine-roadmap.md) ← this doc informs
- [Bootstrap Roadmap](../plans/2026-02-11-integration-roadmap.md) ← this doc informs
- [Skill Architecture Upgrade](../skill-arch-upgrade/design.md) ← parallel work, no dependency

---

## Context

On 2026-02-22 we did a deep read of [tatargabor/wt-tools](https://github.com/tatargabor/wt-tools), a real-world solo-developer toolkit for parallel AI agent management. It's the most complete reference implementation in this space — native GUI, worktree isolation, autonomous loops, team sync, and MCP server in one project. The read surfaced four concrete adoption decisions and meaningful ecosystem intelligence.

This doc captures those decisions formally so they don't live only in chat history.

---

## Adoption Decisions

### Decision 1: Add a FastMCP server for Forge tracker state (Phase 4)

**What wt-tools showed:** Their `wt_mcp_server.py` uses [FastMCP](https://github.com/jlowin/fastmcp) — a high-level Python wrapper over the MCP JSON-RPC protocol — to expose agent state as MCP tools. The server reads from local JSON files (`.claude/loop-state.json`, `.claude/activity.json`) with no daemon, no database, no external service.

**The key tools they expose:**

| Tool | Description |
|------|-------------|
| `list_worktrees` | All git worktrees with branch + status |
| `get_worktree_tasks` | Task list for a worktree |
| `get_ralph_status` | Autonomous loop state (current task, iteration, exit criteria) |
| `get_team_status` | Cross-machine agent activity via git-branch sync |

**Forge's equivalent:** We have richer tracker state than wt-tools — 123+ items, 141 connections, phase/status/confidence metadata, session accumulator. None of it is currently accessible to agents via MCP. Agents have to read raw markdown or make REST calls (which requires knowing the API).

**Decision:** Build a Forge MCP server (`server/forge-mcp.js` or a Python sidecar) that exposes:

| Tool | What it returns |
|------|-----------------|
| `get_vision_items` | Items filtered by phase/status/type/keyword |
| `get_item_connections` | Connections for a specific item |
| `get_current_session` | Active session: tool count, items touched, summaries |
| `get_phase_summary` | Item counts by status for a given phase |
| `get_blocked_items` | Items blocked by non-complete dependencies |

This makes Forge's tracker a first-class context source for any agent running in this project — not just agents that know to call `GET /api/vision/items`.

**What we're NOT adopting from wt-tools:**
- Git-branch team sync — Forge is single-machine, single-developer
- Cross-worktree agent messaging — Forge manages a single worktree's lifecycle
- Activity JSON files — we have SDK hooks + SSE; no need for file-based polling

**Acceptance criteria:**
- [x] MCP server starts on-demand via Claude Code stdio (registered in `.mcp.json`)
- [x] `get_vision_items(phase?, status?, type?, keyword?)` returns matching items with id, title, phase, status, type, confidence, description
- [x] `get_current_session()` returns active session tool count, items touched, latest summaries
- [x] `get_phase_summary(phase)` returns status distribution for that phase
- [x] `get_blocked_items()` returns items with their blockers
- [x] MCP server reads from existing VisionStore JSON (no new data format)
- [x] Agent running in this repo can call the tools without configuration

---

### Decision 2: Add throttling to `agent-hooks.js` (Phase 4, near-term)

**What wt-tools showed:** Their `activity-track.sh` hook skips execution if the target file was updated less than 10 seconds ago. This is because Bash loops fire `PreToolUse` for every iteration — without throttling, you get hundreds of hook calls per session.

**Forge's current state:** `agent-hooks.js` POSTs to api-server (3001) on every `PostToolUse` event with no coalescing. A Bash loop running 50 iterations generates 50 individual HTTP requests to api-server. Each triggers vision broadcast, SessionManager accumulation, and potentially a Haiku batch flush.

**Decision:** Add a per-tool coalesce window in `agent-hooks.js`. If the same tool fires again within 5 seconds and the file path / command is identical, skip the POST. Distinct tool uses (different files, different commands) still POST immediately.

**Acceptance criteria:**
- [ ] `postToolUseHook` skips POST if same `tool_name` + `file_path/command` fired within 5s
- [ ] First occurrence always fires (no delayed-first-post behavior)
- [ ] Different file paths / commands are never coalesced
- [ ] Unit test: 10 identical Bash calls → 1-2 POSTs, not 10

---

### Decision 3: Use `.claude/loop-state.json` as the Ralph Loop primitive (Phase 6)

**What wt-tools showed:** Their Ralph Loop stores its state in a flat JSON file at `.claude/loop-state.json`. The schema is minimal: task list, current index, iteration count, exit criteria, last result, started/updated timestamps. No external process, no database. The agent reads it on startup, updates it after each task, and the loop driver just checks it.

**Forge's planned Ralph loops** (roadmap item 23, iteration orchestration) have been under-specified architecturally. wt-tools proves the file-based approach works reliably in production — they ran 12-change benchmarks with 24+ productive iterations using this pattern.

**Decision:** Adopt `.claude/loop-state.json` as Forge's Ralph Loop primitive. Schema:

```json
{
  "loopId": "loop-<timestamp>",
  "featureId": "tracker-item-id",
  "phase": "implementation",
  "tasks": [
    { "id": "t1", "title": "Write tests", "status": "complete", "result": "passed" },
    { "id": "t2", "title": "Implement auth", "status": "in_progress", "result": null },
    { "id": "t3", "title": "Review", "status": "pending", "result": null }
  ],
  "currentTaskIndex": 1,
  "iteration": 4,
  "maxIterations": 20,
  "exitCriteria": "all tasks complete, tests passing",
  "startedAt": "2026-02-22T10:00:00Z",
  "updatedAt": "2026-02-22T10:45:00Z",
  "lastResult": "implemented login endpoint, 3 tests passing"
}
```

The SDK's `resume` option (which we now have wired in agent-server) handles session continuity between iterations without additional infrastructure.

**What we're NOT adopting:**
- wt-tools' `wt-loop` CLI — Forge's loop will be driven by the forge skill, not a separate binary
- Their per-worktree isolation (git worktrees) — Forge uses session tracking, not branch isolation

**Acceptance criteria:**
- [ ] Forge skill creates `.claude/loop-state.json` when starting a Ralph loop phase
- [ ] Agent reads state on session start (via SessionStart hook or system prompt injection)
- [ ] Agent updates state after each task via a Write tool call or hook
- [ ] Loop driver detects completion by reading `tasks[*].status === 'complete'` or iteration limit
- [ ] VisionServer broadcasts a `ralphLoopUpdate` event when state file changes (file watcher)
- [ ] AgentPanel shows loop progress when `.claude/loop-state.json` exists

---

### Decision 4: Measure memory noise separately from memory signal (long-term)

**What wt-tools showed:** Their v6 benchmark results are the most honest data in this space. Despite +34% synthetic benchmark claims, the real-world CraftBazaar benchmark showed Run A (no memory) outperformed Run B (memory) on:

- C12 bug score: **11/12 vs 9/12** (A wins by 2)
- Drift trap score: **2/2 vs 1.5/2** (A wins by 0.5)

Run B reduced memory noise from 37% to 0% (good), but code map coverage regressed (4/12 → 2/12, bad). Net: memory helps with convention compliance (conventions traps: 5/5 both), hurts on nuanced contextual reasoning.

**The failure mode:** Memories are injected as system-reminder context. When memory is wrong or stale, the agent confidently reproduces the wrong behavior. This is worse than starting from zero.

**Decision for Forge:** When Forge adds memory features (Phase 5 or later), track two distinct metrics separately:

| Metric | Measures |
|--------|----------|
| **Signal rate** | % of recalled memories that were actually applied correctly |
| **Noise rate** | % of recalled memories that were irrelevant or led to wrong behavior |
| **Convention compliance delta** | % improvement vs no-memory baseline on known conventions |

Don't ship memory features without a benchmark harness. wt-tools ran 6 versions of their benchmark before they had trustworthy numbers. Budget for that.

**Acceptance criteria (for when we get there):**
- [ ] Memory measurement harness exists before memory feature ships
- [ ] Noise rate tracked separately from recall rate
- [ ] Baseline (no-memory) run established for every benchmark version
- [ ] Real-world benchmark, not just synthetic

---

## Ecosystem Intelligence

From wt-tools' Related Projects table, updated with star counts and relevance to Forge:

### Closest competitors (worktree + agent management)

| Project | Stars | Overlap with Forge | Notes |
|---------|-------|--------------------|-------|
| [claude-squad](https://github.com/smtg-ai/claude-squad) | 6k | High — tmux+worktree, multi-agent TUI | What Forge was before today's SDK migration. Go. |
| [ccpm](https://github.com/automazeio/ccpm) | 7k | Medium — GitHub Issues as PM + agent swarm | Lifecycle-adjacent. External task source vs. internal tracker. |
| [automaker](https://github.com/AutoMaker-Org/automaker) | 3k | Medium — Electron Kanban + worktree agents | GUI + workflow, Electron (not native web) |
| [wt-tools](https://github.com/tatargabor/wt-tools) | — | High — full stack reference | Solo dev, well-maintained, Python GUI |

### Multi-agent orchestration (relevant to Phase 7)

| Project | Stars | Relevance |
|---------|-------|-----------|
| [wshobson/agents](https://github.com/wshobson/agents) | 28k | Community plugin ecosystem — 112 agents, 146 skills. Forge's skill architecture should stay compatible. |
| [claude-flow](https://github.com/ruvnet/claude-flow) | 14k | Enterprise agent swarm, 87+ MCP tools. Reference for MCP tool design. |
| [ralph-orchestrator](https://github.com/mikeyobrien/ralph-orchestrator) | 2k | Rust autonomous loop. Reference for Ralph Loop primitives. |

### Monitoring / desktop apps

| Project | Stars | Relevance |
|---------|-------|-----------|
| [crystal](https://github.com/stravu/crystal) | — | Desktop app for Claude/Codex. Track for competitive awareness. |
| [ccmanager](https://github.com/kbwo/ccmanager) | — | Multi-agent session manager. |
| [ClaudeBar](https://github.com/tddworks/ClaudeBar) | 570 | macOS menu bar API usage. Usage bar idea for Forge header. |

### Key observation

**`wshobson/agents` at 28k stars** is the gravity center of the community ecosystem. When Forge gets to Phase 5 (Standalone / Plugin packaging), compatibility with that agent/skill format will matter for adoption. Worth understanding their packaging format before designing Forge's own.

---

## What We're Not Adopting

| wt-tools feature | Why not |
|------------------|---------|
| Shell-script hooks | Replaced by SDK in-process hooks (cleaner, typed, no jq) |
| Python GUI (PySide6) | Forge's web UI is better — real-time SSE, richer data, no desktop process |
| Git-branch team sync | Single developer, single machine |
| Per-worktree activity.json | We have SDK hooks + VisionServer SSE broadcast |
| OpenSpec skill hierarchy | Forge's lifecycle phases serve the same purpose; no duplication needed |

---

## Implementation Order

Phase 4 items (near-term, before Phase 6):

1. **Hook throttling** — 1–2 hour change in `agent-hooks.js`. Low risk, measurable improvement.
2. ~~**MCP server**~~ — **Done.** `server/forge-mcp.js`, stdio transport, registered in `.mcp.json`.
3. **MCP query expressiveness** — add `fields` and `statuses[]` parameters to `get_vision_items`. See Decision 5.

Phase 6 items (lifecycle engine):

4. **Ralph Loop state** — `.claude/loop-state.json` schema agreed here. Implement when iteration orchestration phase begins.
5. **Memory measurement** — Harness before feature, not after.
6. **MCP filesystem evolution** — if tool count exceeds ~20, restructure as `server/mcp/<category>/tool-name.ts` modules. See Decision 5.

---

## Decision 5: Query expressiveness > tool proliferation (from Anthropic code execution article)

**Source:** Anthropic engineering blog, "Code execution with MCP" (2025-11-04)

**What the article showed:** Standard MCP pattern passes all intermediate results through the model's context window. For large payloads, this is O(n·m) token cost per multi-step workflow. The fix: filter and transform data in the execution environment before returning it to the model. Example: 150,000 tokens → 2,000 tokens (98.7% reduction) by filtering a meeting transcript in code rather than passing it raw.

The structural recommendation: expose MCP tools as a **filesystem of composable TypeScript modules** agents can read on-demand, rather than a monolithic switch-statement server that loads all definitions upfront.

**The scale at which this bites Forge:** Not yet — 5 tools, structured JSON payloads, single-developer localhost. But the design principle applies now: **make existing tools more expressive rather than adding narrowly-scoped tools**. Each new tool that could instead be a parameter on an existing tool avoids a proliferation problem.

**Decisions:**

1. **`get_vision_items` query expressiveness** — add `fields` parameter (array of field names to return) and support `status` as a proper array. An agent that only needs `id` and `title` shouldn't receive `description`, `confidence`, `files`, etc. for all 30 results. This is the primary near-term change.

2. **No new tools for pre-aggregated queries** — if a future use case calls for "items in phase X that are blocked and have confidence < 2," that's a filter combination, not a new tool. Extend `get_vision_items` filter logic instead.

3. **Filesystem-of-modules as Phase 5 target** — if tool count grows past ~20, restructure `forge-mcp.js` as individual files in `server/mcp/<category>/`. The switch statement doesn't scale, and the discovery pattern (agents `ls` the directory) is intrinsically more extensible.

4. **Orchestration-as-skill** — when a ralph loop runs successfully, the sequence of MCP calls + transforms is a reusable pattern. Phase 5 skill packaging should consider capturing successful loop traces as generatable skills. (Long-term, no immediate action.)

**Acceptance criteria for `get_vision_items` expressiveness:**
- [ ] `fields?: string[]` parameter — if provided, only return the named fields per item
- [ ] `status` accepts either a comma-string (backwards-compatible) or an array
- [ ] Default behavior unchanged when neither `fields` nor array `status` is passed
- [ ] Existing callers continue to work without modification

---

## Decision 6: Two-tool endgame + token budget cap (from Cloudflare Code Mode article)

**Source:** Cloudflare blog, "Code Mode: Give Agents an Entire API in 1,000 Tokens" (2026)

**What the article showed:** Cloudflare's 2,500-endpoint API would cost 1.17M tokens as conventional MCP tools — exceeding the context window of any current model. Their fix: expose exactly **two tools** regardless of how many operations exist:
- `search(jsCode)` — agent writes JS to query the OpenAPI spec; returns only matching endpoints
- `execute(jsCode)` — agent writes JS to call the API; runs in a V8 sandbox isolate

Fixed token footprint: ~1,000 tokens. The agent discovers and composes operations in code rather than selecting from pre-defined tools.

The article names three competing MCP tiers:

| Tier | Pattern | Token cost model |
|---|---|---|
| 1 | Dynamic Tool Search (Claude Code, forge-mcp.js) | Medium — filtered subset per task |
| 2 | Code Mode — server-side sandbox | Fixed — 2 tools regardless of API size |
| 3 | CLI passthrough | Variable — self-documenting, broader attack surface |

**Where forge-mcp.js currently sits:** Tier 1. Correct for 5 tools and a 124-item tracker.

**Decisions:**

1. **Token budget cap: 2,000 tokens for all tool definitions combined.** Baseline measured 2026-02-24: ~519 tokens for 5 tools. Measure before adding any new tool. If a new capability can be expressed as a parameter on an existing tool (Decision 5), prefer that. Budget is the guard rail against proliferation.

2. **Write operations via typed tools, not sandboxed code execution.** Cloudflare's `execute(jsCode)` approach is justified by multi-tenancy and 2,500+ endpoints — neither applies to Forge. When write operations are needed, add simple typed tools: `update_item(id, fields)`, `create_connection(fromId, toId, type)`. 2-3 tools, typed inputs, no sandbox. Agents that already have Bash access can also use `vision-track.mjs` directly — there is no write gap right now.

3. **The two-tool endgame is not Forge's target.** The correct takeaway from Cloudflare is the budget cap principle, not the architecture. Forge's write surface is small enough that typed tools are always the right answer.

**Acceptance criteria for token budget cap:**
- [x] Baseline token count for current 5-tool `tools/list` response recorded in `forge-mcp.js` (~519 tokens)
- [ ] 2,000-token soft cap documented — new tools require justification
- [ ] Write tools (`update_item`, `create_connection`) added as typed tools when needed, not as code execution

**Not applicable to Forge:** OAuth 2.1, V8 Worker isolates, sandboxed `execute()`, multi-tenant MCP portals. Single-user, localhost, small write surface.

---

## Open Questions

- ~~**MCP server language:** Python (FastMCP) vs. Node.js?~~ **Resolved:** Node.js with `@modelcontextprotocol/sdk` — keeps stack homogeneous, comparable ergonomics to FastMCP.
- ~~**MCP server port:** Dedicated port or stdio?~~ **Resolved:** stdio transport. Claude Code launches `server/forge-mcp.js` on-demand; registered in `.mcp.json`. No port management, no supervisor changes.
- **wshobson/agents format:** Before Phase 5 packaging, understand their skill format to assess compatibility cost.
