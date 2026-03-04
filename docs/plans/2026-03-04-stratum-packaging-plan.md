# Stratum Packaging Restructure Plan

**Date:** 2026-03-04
**Status:** PLANNED

## Related Documents

- Backward: ROADMAP.md (Track 6 — stratum-ui, Track 4 — Consolidation)
- Forward: none yet

---

## Problem

Three packaging issues:

1. **stratum-ui is a pip package** but it's a UI — it has no business on PyPI. A frontend belongs on npm.
2. **stratum-ui frontend is Jinja2 templates** — not componentizable, not embeddable in other apps.
3. **Compose app lives inside the stratum repo** (`stratum/app/`) with no clean install story. Users can't get it without cloning the whole stratum repo.

---

## Target State

```
pip install stratum          # Python library + MCP server (one command)
npm install @stratum/ui      # React component library + standalone UI

compose  (separate repo)     # Separate project, uses @stratum/ui components
```

---

## Package Responsibilities

### `stratum` (PyPI) — consolidates stratum-py + stratum-mcp

Currently two pip installs. There's no reason to split them — stratum-mcp is worthless without stratum-py and vice versa for Claude Code users.

```
pip install stratum
  → stratum-py   (Python library: @pipeline, @phase, stratum.run())
  → stratum-mcp  (MCP server: stratum_plan, stratum_step_done, stratum_audit)

stratum-mcp install   # still works — registers MCP server with Claude Code
stratum-mcp compile   # still works
```

`stratum-py` and `stratum-mcp` remain as separate sub-packages internally but `stratum` is the single user-facing install. Existing `pip install stratum-py` and `pip install stratum-mcp` continue to work (no breaking change).

### Command Matrix

One canonical binary per concern. No duplicated wrappers.

| Command | Binary | Purpose | Notes |
|---|---|---|---|
| `stratum install` | `stratum` (PyPI) | Register MCP + install `@stratum/ui` via npm internally | Canonical first-run setup |
| `stratum serve` | `stratum` (PyPI) | Start API server (:7821, loopback) + serve UI | Delegates to `stratum-mcp serve` |
| `stratum-mcp install` | `stratum-mcp` (PyPI) | Register MCP with Claude Code only | Still works, no UI |
| `stratum-mcp compile` | `stratum-mcp` (PyPI) | Compile tasks/*.md → .stratum.yaml | Unchanged |
| `stratum-mcp serve` | `stratum-mcp` (PyPI) | JSON API server only, no UI | Called by `stratum serve`; also usable standalone |
| `npx @stratum/ui serve` | `@stratum/ui` (npm) | UI only, expects API already running | Developer path; not the default |
| `compose install` | `compose` (npm) | Register compose-mcp in .mcp.json | Separate project |
| `compose start` | `compose` (npm) | Start compose app servers | Separate project |

`stratum serve` is the single user-facing command. Everything else is a building block or a developer escape hatch.

---

### `@stratum/ui` (npm) — React component library + standalone app

The stratum-ui FastAPI backend moves into `stratum-mcp` as an opt-in HTTP server — it already reads the same `.stratum/runs/` files that stratum-mcp writes.

```
stratum-mcp serve     # NEW: JSON API server on 127.0.0.1:7821 (loopback only by default)
                      # reads .stratum/runs/, .stratum/flows/, .stratum/pipeline-draft.json
                      # JSON API only — no HTML, no Jinja2
```

**Security posture — `stratum-mcp serve`:**
- Binds `127.0.0.1` by default. Never `0.0.0.0` without opt-in.
- Remote bind (`--host 0.0.0.0`) requires `--token <secret>` — requests without the token get 401.
- TLS (`--tls-cert`, `--tls-key`) available for remote use over untrusted networks.
- `.stratum/*` data (flow state, pipeline drafts, run outputs) is never exposed without explicit remote opt-in.

```bash
stratum serve                          # loopback only, no auth required
stratum serve --host 0.0.0.0 --token sk-xxx   # remote, token required
```

The frontend becomes a React component library published to npm:

```
@stratum/ui
  components/
    RunList         props: { runs: Run[], onSelect: (id) => void, apiBase?: string }
    RunDetail       props: { runId: string, apiBase?: string }
    GateQueue       props: { onApprove: (runId, phase) => void, onReject: (runId, phase) => void, apiBase?: string }
    PipelineEditor  props: { draft: Draft, onChange: (draft) => void, onSave: () => void, apiBase?: string }
    GeneratePanel   props: { draft: Draft, formats: Format[], apiBase?: string }
  app/
    main.jsx        standalone app — wires components to /api/* endpoints
  dist/             built assets bundled into stratum for `stratum serve`
```

`apiBase` defaults to `http://localhost:7821` on all components. Override to point at a remote server.

**Standalone use — the stratum CLI handles npm behind the scenes:**
```bash
pip install stratum
stratum install       # registers MCP server with Claude Code
                      # + runs `npm install -g @stratum/ui` internally
stratum serve         # starts API on 127.0.0.1:7821 + serves UI — user never touches npm
```

Users who don't build UIs never see npm. The Python CLI owns the install story end to end.

**For developers embedding in their own app:**
```jsx
import { GateQueue, RunList } from '@stratum/ui'

// defaults to localhost:7821
<GateQueue onApprove={handleApprove} onReject={handleReject} />

// point at a remote server
<GateQueue apiBase="https://myserver:7821" onApprove={handleApprove} onReject={handleReject} />
```

### `compose` (separate repo, separate npm package)

Moves out of `stratum/app/` into its own repository. Uses `@stratum/ui` components.

```
compose/
  src/
    components/
      Canvas.jsx              vision board
      AgentStream.jsx         live agent output
      SessionTracker.jsx      session history
      StratumPanel.jsx        ← imports RunDetail, GateQueue from @stratum/ui
  server/
    index.js                  Express :3001
    compose-mcp.js            stdio MCP server
    vision-server.js
    session-manager.js
  skill/
    SKILL.md                  /compose Claude Code skill
  data/                       vision-state.json, sessions.json
  package.json                { "dependencies": { "@stratum/ui": "^1.0" } }
```

Install story:
```bash
npx compose-app install       # registers compose-mcp in .mcp.json, starts on login
# or
npm install -g compose-app
compose install
compose start
```

---

## stratum/examples/ (stays in stratum repo)

Small, focused examples of building on stratum:

```
stratum/examples/
  nextjs/           how to embed RunList + GateQueue in a Next.js app
  custom-tracker/   minimal project tracker pattern (compose-mcp style)
```

A vanilla-js example requires web components, which is deferred (see Open Questions). Add if/when web components ship.

---

## Migration Steps

### Phase 1 — stratum-mcp: add `serve` command
- [ ] Add `stratum-mcp serve` subcommand: FastAPI app on :7821
- [ ] Move stratum-ui server logic into stratum-mcp (`serve.py`)
- [ ] API routes:
  - `GET  /api/runs` — list all runs, newest first
  - `GET  /api/runs/{run_id}` — single run with per-phase detail
  - `GET  /api/gates` — all pending gates across all runs
  - `POST /api/gates/{run_id}/{phase}/approve` — body: `{ note?: string }`
  - `POST /api/gates/{run_id}/{phase}/reject`  — body: `{ note?: string }`
  - `GET  /api/pipeline-draft` — current draft
  - `PUT  /api/pipeline-draft` — replace draft; body: Draft object
- [ ] Bind `127.0.0.1` by default; **refuse to start** if `--host` is non-loopback and `--token` is absent — non-loopback without a token is a startup error, not a runtime 401
- [ ] Remove HTML/Jinja2 — JSON responses only
- [ ] Tests: port stratum-ui tests to stratum-mcp/tests/

### Phase 2 — @stratum/ui: React component library
- [ ] Scaffold `stratum-ui/` as npm package (`@stratum/ui`)
- [ ] Rewrite each Jinja2 template as a React component
- [ ] Build standalone app in `stratum-ui/app/main.jsx` that calls `stratum-mcp serve` API
- [ ] Publish to npm as `@stratum/ui`
- [ ] `npx @stratum/ui serve` serves the built React assets only — it does not start or manage `stratum-mcp serve`. It expects the API to already be running and accepts `--api-base` to override the default `http://localhost:7821`. Starting the API is the user's responsibility (or `stratum serve` does both).

### Phase 3 — stratum pip consolidation
- [ ] Create top-level `stratum` PyPI package that depends on `stratum-py` + `stratum-mcp`
- [ ] `stratum` meta-package: single `pyproject.toml` with both as dependencies
- [ ] Deprecation notice on `stratum-py` and `stratum-mcp` standalone installs (keep them working)

### Phase 4 — compose: separate repo
- [ ] Create new `compose` repository
- [ ] Move `stratum/app/` contents → compose repo
- [ ] Add `@stratum/ui` as dependency, replace stratum-ui panel code with `<RunDetail>` / `<GateQueue>` components
- [ ] Write `compose install` CLI command (registers compose-mcp in `.mcp.json`)
- [ ] Update stratum CLAUDE.md and ROADMAP.md to reference compose as external project
- [ ] Archive `stratum/app/` (or remove)
- [ ] Add compose link to stratum README

### Phase 5 — stratum/examples/
- [ ] Write `examples/nextjs/` — Next.js app embedding `@stratum/ui` components
- [ ] Write `examples/custom-tracker/` — minimal compose-mcp style tracker
- [ ] Remove old stratum-ui PyPI package (or redirect to deprecation notice)
- [ ] `examples/vanilla-js/` blocked on web components decision (Open Questions)

---

## What stratum-ui (PyPI) becomes

`pip install stratum-ui` becomes a shim that prints:

```
stratum-ui has moved to npm. Install with:
  npm install -g @stratum/ui

Or run without installing:
  npx @stratum/ui serve
```

---

## Open Questions

- Should `compose` be published to npm as `@stratum/compose`? Aligns with the `@stratum/*` namespace but implies Stratum owns the compose UI. Alternatively just `compose-app`.
- Should `@stratum/ui` components also ship as web components (custom elements) for non-React apps?
