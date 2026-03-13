# stratum-mcp

Stratum MCP server for Claude Code. Structured execution, typed contracts, postcondition enforcement — no sub-LLM calls.

## Install

```bash
pip install stratum-mcp
stratum-mcp install
```

`setup` configures Claude Code in one command: writes `.claude/mcp.json`, appends the execution model block to `CLAUDE.md`, and installs nine skills to `~/.claude/skills/`. Restart Claude Code and it's active.

## Skills

| Skill | What it structures |
|---|---|
| `/stratum-onboard` | Read a new codebase cold and write project-specific `MEMORY.md` — run once after setup |
| `/stratum-plan` | Design a feature and present it for review — no implementation until approved |
| `/stratum-feature` | Feature build: read existing patterns → design → implement → tests pass |
| `/stratum-review` | Three-pass code review: security → logic → performance → consolidate |
| `/stratum-debug` | Debug: read test → read code → check env → form hypotheses → confirm/rule out → fix |
| `/stratum-refactor` | File split: analyze → design modules → plan extraction order → extract one at a time |
| `/stratum-migrate` | Find bare LLM calls and rewrite as `@infer` + `@contract` |
| `/stratum-test` | Write a test suite for existing untested code |
| `/stratum-learn` | Review session transcripts — extract retry patterns, write conclusions to `MEMORY.md` |

## MCP Tools

| Tool | What it does |
|---|---|
| `stratum_validate` | Validate a `.stratum.yaml` spec |
| `stratum_plan` | Validate + create execution state + return first step |
| `stratum_step_done` | Report a completed step; check postconditions; return next step or completion |
| `stratum_audit` | Return per-step trace (attempts, duration) for any flow |

## Building on Stratum

Stratum exposes four stable integration points for apps and tooling:

### 1. MCP tools (Claude Code agents)
The primary control plane — `stratum_plan`, `stratum_step_done`, `stratum_audit`. Used by agents running inside Claude Code.

### 2. Query CLI (read-side, any process)
```bash
stratum-mcp query flows              # → JSON array of FlowSummary
stratum-mcp query flow <id>          # → JSON FlowState
stratum-mcp query gates              # → JSON array of pending gates
```
Exit 0, JSON to stdout. Use from shell scripts, background services, or UI backends.

### 3. Gate CLI (write-side, any process)
```bash
stratum-mcp gate approve <flow_id> <step_id> [--note "..."] [--resolved-by agent]
stratum-mcp gate reject  <flow_id> <step_id> [--note "..."]
stratum-mcp gate revise  <flow_id> <step_id> [--note "..."]
```
Exit codes: `0` success · `1` error (JSON on stdout) · `2` conflict (already resolved).

### 4. Storage schemas (`contracts/`)
Versioned JSON schemas for the flow state and audit record formats. Stable across internal refactors.

```
stratum-mcp/contracts/
  flow-state.v1.schema.json
  query-flows.v1.schema.json
  query-gates.v1.schema.json
  gate-mutation.v1.schema.json
  audit-record.v1.schema.json
```

## How It Works

Claude writes `.stratum.yaml` specs internally — you never see them. You see plain English narration. The MCP server enforces postconditions on every step; if a step's output fails a check, Claude fixes it and retries before reporting success.

Full documentation: [stratum-in-claude-code.md](https://github.com/regression-io/stratum/blob/main/blog/stratum-in-claude-code.md)

Tutorial: [claude-code-tutorial.md](https://github.com/regression-io/stratum/blob/main/blog/claude-code-tutorial.md)

## License

Apache 2.0

<!-- mcp-name: io.github.ruze00/stratum-mcp -->
