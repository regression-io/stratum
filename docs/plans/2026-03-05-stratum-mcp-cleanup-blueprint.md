# Blueprint: Stratum as Execution Kernel

**Date:** 2026-03-05
**Status:** COMPLETE (stratum-ui deletion pending manual `rm -rf`)

## Goal

Stratum is a headless execution kernel. Compose is a product shell that consumes it.
No UI, no HTTP endpoints, and no app-specific concepts in stratum.
Compose talks to stratum via a stable contract — not stratum's internal files.

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                       stratum                           │
│                                                         │
│  Execution Kernel                                       │
│    spec.py      — IR parsing, validation, semantics     │
│    executor.py  — flow lifecycle, gates, retries        │
│    errors.py    — typed error hierarchy                 │
│    task_compiler.py — tasks/*.md → .stratum.yaml        │
│                                                         │
│  Storage Contract (versioned JSON schemas)              │
│    ~/.stratum/flows/{id}.json  — v1 schema, guaranteed  │
│    contracts/flow-state.v1.schema.json                  │
│    contracts/audit-record.v1.schema.json                │
│    contracts/step-result.v1.schema.json                 │
│                                                         │
│  MCP Control Plane (primary integration)                │
│    server.py — stratum_plan, stratum_step_done,         │
│                stratum_gate_resolve, stratum_audit,     │
│                stratum_draft_pipeline, ...              │
│                                                         │
│  Query CLI (read-side contract for non-MCP consumers)   │
│    stratum-mcp query flows                              │
│    stratum-mcp query flow <id>                          │
│    stratum-mcp query gates                              │
│                                                         │
│  skills/, hooks/                                        │
└───────────────────────────┬─────────────────────────────┘
                            │ stable contracts only
                            │ (MCP tools + query CLI + storage schema)
                            ▼
┌─────────────────────────────────────────────────────────┐
│                      compose                            │
│                                                         │
│  stratum-sync.js — calls `stratum-mcp query`            │
│                    (not direct file reads)              │
│  stratum-api.js  — Express routes for StratumPanel      │
│                    (thin transport adapter, no logic)   │
│  StratumPanel.jsx — view models, UX, optimistic updates │
│  stratum/ components — RunList, GateQueue, etc.         │
└─────────────────────────────────────────────────────────┘
```

---

## What Changes

### Gap 1: Compose reads stratum internals directly

**Current:** `stratum-sync.js` reads `~/.stratum/flows/` raw JSON.
**Problem:** compose is coupled to stratum's internal persistence format, not a contract.

**Fix:** Add a `stratum-mcp query` CLI subcommand as the read-side contract.

```bash
stratum-mcp query flows              # → JSON array of flow summaries
stratum-mcp query flow <id>          # → JSON flow state
stratum-mcp query gates              # → JSON array of pending gates
```

- Output is machine-readable JSON to stdout, structured per the storage contract schemas.
- `stratum-sync.js` replaces direct file reads with `execFile('stratum-mcp', ['query', 'flows'])`.
- Storage schemas are guaranteed stable and versioned — if the internal format changes, the query output does not.
- This is not an HTTP server. It is a CLI query interface, the same pattern as `git` or `docker inspect`.

### Gap 2: No explicit Stratum public contract

**Fix:** Add `contracts/` directory to stratum-mcp with versioned JSON schemas.

```
stratum-mcp/contracts/
  flow-state.v1.schema.json     — FlowState output shape
  audit-record.v1.schema.json   — audit trace record shape
  step-result.v1.schema.json    — step completion result shape
  gate-event.v1.schema.json     — gate request/resolution shape
  query-flows.v1.schema.json    — output of `stratum-mcp query flows`
  query-gates.v1.schema.json    — output of `stratum-mcp query gates`
```

Rules:
- Schema version is in the filename and in each document as `"_schema_version"`.
- Breaking changes require a new version number.
- Old versions are supported for one release cycle.
- `stratum-mcp/CHANGELOG.md` tracks schema changes explicitly.

### Gap 3: Risk of domain logic duplication in compose

**Problem:** Moving `serve.py` to `compose/server/stratum-api.js` risks copying gate semantics, state interpretation logic, etc. into compose.

**Fix:** `stratum-api.js` is a pure transport adapter — it calls `stratum-mcp query` and reformats for HTTP. Zero domain logic.

```js
// stratum-api.js — ONLY does this:
router.get('/api/stratum/flows', async (req, res) => {
  const flows = await stratumQuery('flows')   // calls CLI, gets structured JSON
  res.json(flows)                             // pass through or reshape for UX
})

router.post('/api/stratum/gates/:flowId/:stepId/approve', async (req, res) => {
  const result = await stratumClient.gateApprove(req.params.flowId, req.params.stepId, req.body.note)
  // map result → HTTP via standard error policy
})
```

Gate approval is a mutation. Compose is not the mutation authority — stratum is.

**Pattern:**
1. Compose calls `stratum-mcp gate approve <flow_id> <step_id> [--note "..."]`
2. Stratum applies `stratum_gate_resolve` internally and persists state
3. Compose calls `stratum-mcp query flow <flow_id>` to get updated state
4. Compose updates its read model from the query result

All of this is routed through one module in compose: `stratum-client.js`.
No other file in compose calls `stratum-mcp` subprocesses directly.

**`stratum-client.js` contract (compose):**

```js
// The single mutation adapter. All stratum CLI calls go through here.
// No other compose module spawns stratum-mcp processes.

export async function queryFlows()                        // → FlowSummary[]
export async function queryFlow(flowId)                   // → FlowState
export async function queryGates()                        // → GateEvent[]
export async function gateApprove(flowId, stepId, note)  // → { ok, conflict, error }
export async function gateReject(flowId, stepId, note)   // → { ok, conflict, error }
```

**Constraints enforced in `stratum-client.js`:**

1. **Single adapter** — only module in compose that spawns `stratum-mcp`. Enforced by lint rule or code review gate.

2. **Exit code mapping** — all calls check exit code:
   - `0` → parse stdout as JSON, return result
   - `2` → idempotency conflict (already approved/rejected), return `{ conflict: true }`
   - non-zero → log stderr internally, return `{ error: { code, message, detail } }`
   stderr is never forwarded to callers or HTTP responses.

3. **Idempotency** — stratum-mcp gate commands return exit code `2` for double-approve/reject.
   Stratum owns the idempotency check (flow state is authoritative). Compose surfaces it as a
   deterministic conflict response without retrying.

4. **Timeout + retry policy:**
   - Query calls: 5s timeout, 1 retry on timeout, no retry on error
   - Mutation calls: 10s timeout, no retry (mutations are not safe to retry blindly)
   - On timeout: return `{ error: { code: 'TIMEOUT' } }`

5. **Structured error body** — all error responses from `stratum-client.js` follow:
   ```json
   { "error": { "code": "CONFLICT|TIMEOUT|NOT_FOUND|INVALID|UNKNOWN", "message": "...", "detail": "..." } }
   ```
   `stratum-client.js` logs stderr to its own internal logger. `stratum-api.js` maps error codes
   to HTTP status codes. stderr never appears in any outbound response.

### Gap 4: No boundary contract tests

**In stratum-mcp** (`tests/contracts/test_query_contract.py`):
```python
def test_query_flows_output_matches_schema()   # spawn CLI, validate JSON vs schema
def test_query_gates_output_matches_schema()   # spawn CLI, validate JSON vs schema
def test_gate_approve_persists_state()         # approve via CLI, query flow, assert resolved
def test_gate_reject_persists_state()          # reject via CLI, query flow, assert rejected
def test_gate_double_approve_returns_conflict()# approve twice, assert exit code 2
def test_gate_approve_nonexistent_flow_errors()# assert structured error, non-zero exit
```

**In compose** (`test/stratum-client.test.js`):
```js
test('gateApprove calls stratum-mcp gate approve with correct args')
test('gateApprove returns conflict on exit code 2')
test('gateApprove returns timeout error on timeout')
test('queryFlows returns parsed JSON on success')
test('queryFlows retries once on timeout then errors')
test('no other module besides stratum-client spawns stratum-mcp')  // static analysis
```

**In compose** (`test/stratum-api.test.js`):
```js
test('POST /api/stratum/gates/:flowId/:stepId/approve → 200 on success')
test('POST /api/stratum/gates/:flowId/:stepId/approve → 409 on conflict')
test('POST /api/stratum/gates/:flowId/:stepId/approve → 504 on timeout')
test('GET /api/stratum/flows returns view model shape')
```

### Gap 5: App-builder support story

**Fix:** Document the stable API surface in `stratum-mcp/README.md`:

> **Building on Stratum**
>
> Stratum exposes four stable integration points:
> 1. **MCP tools** — control plane, used by Claude Code agents
> 2. **Query CLI** — read-side, use from any process via `stratum-mcp query`
> 3. **Gate CLI** — write-side, approve/reject gates from any process via `stratum-mcp gate`
> 4. **Storage schemas** — in `contracts/`, for apps that need direct file access

---

## Remove from stratum

| What | Action |
|---|---|
| `serve.py` | Delete |
| `tests/test_serve.py` | Delete |
| `pyproject.toml` `[serve]` extras | Remove |
| `_cmd_serve` in `server.py` | Remove |
| `stratum-ui/` directory | Delete entirely |

## Add to stratum

| What | Where |
|---|---|
| `stratum-mcp query` subcommand | `server.py` `_cmd_query()` |
| `stratum-mcp gate approve/reject` subcommand | `server.py` `_cmd_gate()` |
| JSON schema contracts | `stratum-mcp/contracts/` |
| Query contract tests | `tests/contracts/test_query_contract.py` |

## Changes in compose

| What | Action |
|---|---|
| `server/stratum-client.js` | New: **single mutation adapter** — all `stratum-mcp` subprocess calls |
| `stratum-sync.js` | Replace file reads with `stratum-client.queryFlows()` |
| `server/stratum-api.js` | New: thin Express router — calls `stratum-client`, maps to HTTP |
| `src/components/stratum/` | New: React components moved from stratum-ui |
| `src/components/StratumPanel.jsx` | Update imports + apiBase |
| `package.json` | Remove `@stratum/ui` dep |

---

## Implementation Order

**Phase A — Stratum contract (no compose changes yet)** ✅
1. Define JSON schemas in `stratum-mcp/contracts/`
2. Add `stratum-mcp query flows|flow <id>|gates` CLI — read-side
3. Add `stratum-mcp gate approve <flow_id> <step_id>` / `reject` CLI — write-side, exit code 2 on conflict
4. Add contract tests in `stratum-mcp/tests/contracts/test_query_contract.py`
5. All existing 314 tests still pass

**Phase B — Compose adapter (stratum unchanged)** ✅
6. Add `compose/server/stratum-client.js` — single adapter, timeout/retry/error mapping
7. Add `compose/server/stratum-api.js` — Express router calling stratum-client
8. Add `compose/test/stratum-client.test.js` and `stratum-api.test.js`
9. Update `stratum-sync.js` to use `stratum-client.queryFlows()`
10. Update `StratumPanel.jsx` apiBase to compose server port

**Phase C — Move UI, remove serve** ✅
11. Move stratum-ui React components to `compose/src/components/stratum/`
12. Remove `@stratum/ui` from compose `package.json`
13. Delete `stratum-mcp/src/stratum_mcp/serve.py`
14. Delete `stratum-mcp/tests/test_serve.py`
15. Remove `_cmd_serve`, `[serve]` extras from stratum-mcp
16. Delete `stratum/stratum-ui/`

**Phase D — Verify** ✅
17. `python -m pytest stratum-mcp/tests/ -q` — all pass
18. Compose starts, StratumPanel renders against compose server
19. Gate approve/reject end-to-end: browser → stratum-api → stratum-client → stratum-mcp gate → stratum query → response

---

## Out of scope

- Merging or removing `stratum-py` — separate decision
- Publishing to PyPI — after cleanup
- Refactoring executor internals — not required for this boundary change
