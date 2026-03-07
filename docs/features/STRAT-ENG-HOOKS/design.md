# STRAT-ENG-HOOKS: Centralized Hook Installation

**Date:** 2026-03-07
**Status:** Complete
**Parent:** [STRAT-1 Design](../../../compose/docs/features/STRAT-1/design.md)
**Roadmap:** [Compose ROADMAP.md](../../../compose/ROADMAP.md) item 43.1

## Problem

`stratum-mcp install` copies hook scripts into each project's `.claude/hooks/` directory and
registers them with relative paths (`bash .claude/hooks/stratum-session-start.sh`). Two issues:

1. **Duplication** — same 3 scripts copied into every project that runs `stratum-mcp install`
2. **Fragile paths** — Claude Code resolves hook commands from its own cwd, which may not be
   the project root. Relative paths break in this case. Claude Code expects absolute paths.

## Solution

Install hook scripts once to `~/.stratum/hooks/` (the same directory that already hosts
`~/.stratum/flows/` for persistence). Register them in project settings.json with absolute
paths.

### Changes

#### 1. `_install_hooks()` — new behavior

- **Destination:** `~/.stratum/hooks/` (was `{root}/.claude/hooks/`)
- **Path in settings.json:** Absolute path, e.g. `/Users/ruze/.stratum/hooks/stratum-session-start.sh`
  (was `bash .claude/hooks/stratum-session-start.sh`)
- **Command format:** `bash /abs/path/to/script.sh` (absolute)
- **Idempotency:** Same content-comparison logic. If a hook already exists with identical
  content, skip. If content differs (upgrade), overwrite.

#### 2. `_remove_hooks()` — new behavior

- **Script deletion:** Delete from `~/.stratum/hooks/` (was `{root}/.claude/hooks/`)
- **Settings cleanup:** Match on absolute path prefix `~/.stratum/hooks/` when filtering
  entries from settings.json
- **Don't delete `~/.stratum/hooks/` dir itself** — flows dir is a sibling, and user may have
  other files there

#### 3. Migration — handle existing per-project installs

On `_install_hooks()`, after installing to `~/.stratum/hooks/`:
- Check if `{root}/.claude/hooks/stratum-*.sh` files exist (old location)
- If found, delete them (they're superseded)
- Check settings.json for old relative-path entries (`bash .claude/hooks/stratum-*.sh`)
- If found, remove them (new absolute-path entries replace them)
- Print "migrated" status for each cleaned-up hook

On `_remove_hooks()`:
- Clean up both old (`{root}/.claude/hooks/`) and new (`~/.stratum/hooks/`) locations
- Clean up both relative and absolute path entries in settings.json

#### 4. Hook script content — no changes

The 3 hook scripts (`stratum-session-start.sh`, `stratum-session-stop.sh`,
`stratum-post-tool-failure.sh`) are unchanged. They read JSON from stdin, use `jq` to
extract fields, and operate on `$CWD` from the input — they're already location-independent.

### File manifest

| File | Action | What changes |
|------|--------|--------------|
| `stratum-mcp/src/stratum_mcp/server.py` | existing | `_install_hooks()`, `_remove_hooks()` rewritten |
| `stratum-mcp/tests/integration/test_setup.py` | existing | Hook tests updated for `~/.stratum/hooks/` paths |
| `stratum-mcp/tests/integration/test_uninstall.py` | existing | Uninstall tests updated for new paths + migration |

### Edge cases

- **Multiple projects:** Each project's settings.json points to the same scripts in
  `~/.stratum/hooks/`. Uninstalling from one project only removes that project's settings
  entries — does NOT delete the shared scripts (other projects still reference them).
  Scripts are only deleted if no settings.json anywhere references them... but we can't
  scan all projects. **Decision:** `_remove_hooks()` always deletes the scripts from
  `~/.stratum/hooks/`. If another project still has entries pointing there, the next
  `stratum-mcp install` in that project will re-copy them. This matches the current
  behavior (uninstall deletes scripts unconditionally).

- **`~/.stratum/` doesn't exist:** Create it. The persistence layer (`persist_flow`)
  already creates `~/.stratum/flows/`, so this directory usually exists.

- **Upgrade path:** User runs new `stratum-mcp install` in a project that had old-style
  hooks. Migration cleans up old files and entries, installs new ones. Seamless.

## Verification

```bash
cd stratum-mcp && pytest tests/ -x
```

All tests must pass. Specifically:
- `tests/integration/test_setup.py` — hooks installed to `~/.stratum/hooks/`, absolute paths in settings
- `tests/integration/test_uninstall.py` — hooks removed from `~/.stratum/hooks/`, old-style cleaned up
- Existing non-hook tests unaffected
