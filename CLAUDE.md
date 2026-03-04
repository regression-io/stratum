# CLAUDE.md

## What This Repo Is

**Stratum** — execution runtime for AI-driven development. Three shipped components:

- **`src/stratum/`** — Python library (`@pipeline`, `@phase`, `stratum.run()`). Published as `stratum-py` on PyPI.
- **`stratum-mcp/`** — MCP server (`stratum_plan`, `stratum_step_done`, `stratum_audit`). Published as `stratum-mcp` on PyPI.
- **`app/`** — Forge web app (React + Express). Vision Surface, agent monitoring, session tracking. Formerly `coder-forge` repo; consolidated here in T4.

Companion: **`stratum-ui/`** — first-party reference UI for pipeline monitoring and gate approval. Separate FastAPI project.

## Repo Layout

```
src/stratum/           — Python library source
stratum-mcp/           — MCP server (FastMCP, fastapi)
  src/stratum_mcp/
    server.py          — MCP tools
    executor.py        — FlowState, persistence (~/.stratum/flows/)
    task_compiler.py   — tasks/*.md → .stratum.yaml
    skills/            — stratum-build, stratum-speckit, stratum-plan, ...
    hooks/             — session-start/stop/failure shell hooks
stratum-ui/            — Reference UI (FastAPI + uvicorn)
app/                   — Forge web app (Vision Surface)
  server/              — Express server (port 3001)
  src/                 — React frontend
  docs/                — App-level docs (roadmap, plans, features)
docs/                  — Stratum-level docs
  plans/               — Implementation plans
  features/            — Feature specs
  app/                 — Archived coder-forge docs (brainstorm, PRD, decisions, journal)
ROADMAP.md             — Canonical roadmap (all tracks)
```

## Development

**Python library / MCP server:**
```bash
cd stratum-mcp && pip install -e ".[dev]"
pytest stratum-mcp/tests/
```

**Web app:**
```bash
cd app && npm install && npm run dev   # starts Vite + Express on port 3001
```

**MCP server (local):**
```bash
stratum-mcp install   # registers with Claude Code
stratum-mcp compile <tasks-dir>   # compile tasks/*.md → .stratum.yaml
```

## Key Docs

- `ROADMAP.md` — all tracks (T1 Python lib → T6 stratum-ui → Evaluation)
- `stratum-mcp/src/stratum_mcp/skills/` — skill reference for stratum-build, stratum-speckit
- `docs/app/` — full Forge design history: brainstorm, PRD, discovery, decisions, journal

## Stratum Execution Model

For non-trivial tasks, use Stratum internally:
1. Write a `.stratum.yaml` spec — never show it to the user
2. Call `stratum_plan` to validate and get the first step
3. Narrate progress in plain English as you execute each step
4. Call `stratum_step_done` after each step — the server checks your work
5. If a step fails postconditions, fix it silently and retry
6. Call `stratum_audit` at the end and include the trace in the commit
