# Skill Script Extraction: Implementation Plan

**Date:** 2026-02-17
**Status:** PLANNED
**Design doc:** [2026-02-17-skill-script-extraction-design.md](./2026-02-17-skill-script-extraction-design.md)
**Estimated phases:** 4 waves, each independently shippable

---

## Wave 1: Entry Scripts + Roadmap (highest frequency)

These scripts run on every `/forge` and `/roadmap` invocation. Highest token savings per session.

### Task 1.1: Create `scripts/forge/` directory and shared helpers

**Files:** `scripts/forge/common.sh` (new)

- [ ] Create `scripts/forge/` directory
- [ ] Write `common.sh` with shared functions:
  - `json_string()` — safely escape a string for JSON output
  - `json_bool()` — convert test result to `true`/`false`
  - `require_jq()` — check `jq` is available, print install hint if not
  - `die()` — print error to stderr and exit 1
- [ ] `chmod +x` all scripts
- [ ] Shebang: `#!/usr/bin/env bash`, `set -euo pipefail`

### Task 1.2: Build `scan-feature.sh`

**Files:** `scripts/forge/scan-feature.sh` (new)

**Input:** `scan-feature.sh <feature-code> [--consume]`

- [ ] Accept `<feature-code>` as first positional arg
- [ ] Resolve path: `docs/features/<feature-code>/`
- [ ] Check folder existence → set `exists` bool
- [ ] If exists, scan for known artifacts:
  - `design.md`, `prd.md`, `architecture.md`, `blueprint.md`, `plan.md`, `report.md`, `killed.md`
  - For each: `exists`, `lines` (via `wc -l`), quick content flags:
    - `design.md`: `has_open_questions` (grep for `?` or `Open Question` or `TBD`)
    - `blueprint.md`: `file_refs_count` (grep for pattern `path/to/file:N` or backtick-quoted paths)
- [ ] Scan for phase subdirectories (`phase-*-*/`), list files in each
- [ ] Scan for `sessions/` directory, count `.jsonl` files, find latest
- [ ] Parse `status.md` if present:
  - Extract `next_phase` (grep for `Next phase:`)
  - Extract `through` (grep for `Through:`)
  - Extract `reason` and `date`
- [ ] If `--consume` flag and `status.md` found → delete it after reading
- [ ] Compute `suggested_start` and `rationale` based on:
  - No folder → "Phase 1: Explore & Design"
  - status.md → use its `next_phase`
  - Otherwise → earliest phase whose artifact is missing
- [ ] Output JSON to stdout
- [ ] Diagnostics to stderr (e.g., "Scanning docs/features/FEAT-1/...")

### Task 1.3: Build `roadmap-status.sh`

**Files:** `scripts/forge/roadmap-status.sh` (new)

**Input:** `roadmap-status.sh [--source <path>]`

- [ ] Implement source discovery chain:
  1. `--source <path>` if provided
  2. Check CLAUDE.md for `## Roadmap Config` → extract `Roadmap:` path
  3. Check `ROADMAP.md` in project root
  4. Check `docs/ROADMAP.md`
  5. Check CLAUDE.md for `## Roadmap` or `## Bootstrap Roadmap` section
  6. Glob for `docs/plans/*roadmap*`
- [ ] Parse the roadmap source for status markers:
  - `DONE` / `COMPLETE` (also `~~strikethrough~~` with DONE)
  - `IN_PROGRESS` / `ACTIVE` / `PARTIAL` (also `← DONE` inline markers)
  - `PLANNED` (default for items with no marker)
  - `BLOCKED`, `PARKED`, `SUPERSEDED`
- [ ] Count items per status
- [ ] Extract active items with title and context
- [ ] Compute `next_recommended`: first unblocked PLANNED item
- [ ] Output JSON to stdout

### Task 1.4: Rewrite forge skill entry section

**Files:** `~/.claude/skills/forge/SKILL.md` (existing)

- [ ] Replace "Entry: Scan First, Then Decide" section (~25 lines) with script invocation (~10 lines)
- [ ] Replace "Phase Selection" table (~15 lines) with "interpret JSON output" guidance (~5 lines)
- [ ] Keep all gate protocol prose unchanged
- [ ] Keep all phase descriptions unchanged (those shrink in Wave 2)

### Task 1.5: Rewrite roadmap skill

**Files:** `~/.claude/skills/roadmap/SKILL.md` (existing)

- [ ] Replace "Finding the Roadmap" section (~25 lines of discovery chain) with script invocation (~3 lines)
- [ ] Replace "Presenting the Roadmap" status counting with "format the JSON output" (~5 lines)
- [ ] Keep "Recommendations" interpretation prose
- [ ] Keep "What NOT to do" section

### Task 1.6: Test Wave 1

**Files:** `test/scripts/` (new directory)

- [ ] Create `test/scripts/fixtures/feature-empty/` — empty feature folder
- [ ] Create `test/scripts/fixtures/feature-partial/` — design.md + blueprint.md, no plan
- [ ] Create `test/scripts/fixtures/feature-paused/` — status.md with resume state
- [ ] Create `test/scripts/fixtures/feature-complete/` — all artifacts present
- [ ] Write `test/scripts/test-scan-feature.sh`:
  - Assert JSON output matches expected for each fixture
  - Assert `--consume` deletes status.md
  - Assert non-existent feature returns `exists: false`
- [ ] Write `test/scripts/test-roadmap-status.sh`:
  - Assert counts match known roadmap state
  - Assert source discovery finds CLAUDE.md roadmap section
- [ ] All tests use `jq` to validate JSON structure

**Acceptance:** `scan-feature.sh` and `roadmap-status.sh` produce correct JSON for all fixtures. Forge and roadmap skills are shorter. No behavioral regression.

---

## Wave 2: Blueprint Pipeline (Phase 4-5 scripts)

These scripts support the blueprint creation and verification phases — the most verbose prose in the forge skill.

### Task 2.1: Build `extract-spec-refs.sh`

**Files:** `scripts/forge/extract-spec-refs.sh` (new)

**Input:** `extract-spec-refs.sh <markdown-path>`

- [ ] Parse the markdown file for file path references:
  - Backtick-quoted paths: `` `src/foo.js` ``, `` `src/foo.js:42` ``
  - Bold paths: `**File: src/foo.js**`
  - Inline code with line refs: `foo.js:42-58`
- [ ] Deduplicate and categorize:
  - `modify` — paths mentioned with EDIT/modify/change context
  - `reference` — paths mentioned with pattern/follow/like context
  - `create` — paths mentioned with NEW/create context
  - `unknown` — paths without clear context
- [ ] Check which paths actually exist on disk
- [ ] Output JSON array: `[{path, line, category, exists}]`

### Task 2.2: Build `verify-refs.sh`

**Files:** `scripts/forge/verify-refs.sh` (new)

**Input:** `verify-refs.sh <markdown-path>`

- [ ] Extract all `file:line` patterns (reuse logic from 2.1 or call it)
- [ ] For each reference with a line number:
  - Read the actual file at that line (`sed -n "${line}p"`)
  - Compare to any inline context quoted in the markdown (if the markdown quotes the expected content)
  - Status: `valid` (file exists, line in range), `stale` (file exists, content differs from quoted), `missing` (file not found), `out_of_range` (line exceeds file length)
- [ ] For references without line numbers: just check file existence
- [ ] Produce summary counts: `total_refs`, `verified`, `stale`, `missing`
- [ ] Output JSON with per-ref detail

### Task 2.3: Build `check-overlaps.sh`

**Files:** `scripts/forge/check-overlaps.sh` (new)

**Input:** `check-overlaps.sh <feature-code>`

- [ ] Find the feature's `blueprint.md`
- [ ] Extract file paths referenced in it (via `extract-spec-refs.sh`)
- [ ] Scan all other `docs/features/*/blueprint.md` files
- [ ] Extract file paths from each
- [ ] Compute intersection per other feature
- [ ] Output JSON: `{overlaps: [{feature, shared_files, shared_count}]}`
- [ ] Empty `overlaps` array if no conflicts

### Task 2.4: Rewrite forge Phases 4-5

**Files:** `~/.claude/skills/forge/SKILL.md` (existing)

- [ ] Phase 4: Replace "Check for overlapping in-flight features" prose with `check-overlaps.sh` call
- [ ] Phase 4: Replace "identify critical source files" prose with `extract-spec-refs.sh` call
- [ ] Phase 5: Replace the entire 15-line verification procedure with `verify-refs.sh` call + "if any stale/missing, loop back to Phase 4"
- [ ] Keep agent orchestration prose (forge-explorer launch, forge-architect mandates)
- [ ] Keep gate descriptions

### Task 2.5: Rewrite implement-blueprint skill

**Files:** `~/.claude/skills/implement-blueprint/SKILL.md` (existing)

- [ ] Step 1 (Identify Critical Files): Replace ~15 lines with `extract-spec-refs.sh` call
- [ ] Step 2 (Read and Note Actual Patterns): Keep — this is LLM-essential judgment
- [ ] Step 3 (Build Corrections Table): Replace procedure with `spec-reality-diff.sh` call (Task 3.2) — or keep as-is until Wave 3
- [ ] Step 4-5: Keep — blueprint writing and spec updating are judgment work

### Task 2.6: Test Wave 2

**Files:** `test/scripts/` (extend)

- [ ] Create `test/scripts/fixtures/blueprint-valid.md` — all refs point to real fixture files
- [ ] Create `test/scripts/fixtures/blueprint-stale.md` — some refs to non-existent files
- [ ] Create fixture source files that the blueprints reference
- [ ] Write `test/scripts/test-verify-refs.sh`
- [ ] Write `test/scripts/test-extract-spec-refs.sh`
- [ ] Write `test/scripts/test-check-overlaps.sh`

**Acceptance:** `verify-refs.sh` correctly identifies stale references in fixture. `check-overlaps.sh` detects shared files between fixture blueprints. Forge skill Phases 4-5 are shorter. No behavioral regression.

---

## Wave 3: Bug-Fix Pipeline + Corrections

### Task 3.1: Build `gather-triage.sh`

**Files:** `scripts/forge/gather-triage.sh` (new)

**Input:** `gather-triage.sh [--test <test-path>] [--error <error-message>] [--file <suspect-file>]`

- [ ] If `--test` provided: run the test, capture output (stdout + stderr), extract failure summary
- [ ] If `--error` provided: search codebase for the error string, return matching files + line numbers
- [ ] If `--file` provided: run `git log --oneline -10 <file>` for recent changes, `git blame` on relevant lines
- [ ] Always: check `git diff --stat HEAD~5` for recent changes that might correlate
- [ ] Output JSON: `{failing_tests, error_matches, recent_changes, blame_info, related_files}`

### Task 3.2: Build `spec-reality-diff.sh`

**Files:** `scripts/forge/spec-reality-diff.sh` (new)

**Input:** `spec-reality-diff.sh <spec-path>`

- [ ] Extract file references from the spec (reuse `extract-spec-refs.sh`)
- [ ] For each referenced file that exists:
  - Check for common spec assumptions vs reality:
    - Async/sync: grep for `async` keyword
    - Base classes: grep for `extends`/`class` declarations
    - Registration patterns: grep for `register`/`decorator` patterns
    - Export patterns: grep for `module.exports`/`export`
  - Produce per-file summary of actual patterns found
- [ ] Output JSON: corrections table with `{file, spec_context, actual_patterns}`

### Task 3.3: Rewrite bug-fix skill Phase 1

**Files:** `~/.claude/skills/bug-fix/SKILL.md` (existing)

- [ ] Replace triage data-gathering prose (~10 lines) with `gather-triage.sh` call
- [ ] Keep severity/scope/path judgment prose
- [ ] Keep gate protocol

### Task 3.4: Test Wave 3

- [ ] Write `test/scripts/test-gather-triage.sh` with a known failing test fixture
- [ ] Write `test/scripts/test-spec-reality-diff.sh` with a spec that makes wrong assumptions
- [ ] Validate JSON output schema

**Acceptance:** `gather-triage.sh` returns structured triage data. `spec-reality-diff.sh` catches intentional mismatches. Bug-fix skill is shorter.

---

## Wave 4: Test Suite + Cleanup

### Task 4.1: Create test runner

**Files:** `test/scripts/run-all.sh` (new)

- [ ] Discover and run all `test/scripts/test-*.sh`
- [ ] Report pass/fail per script
- [ ] Exit non-zero if any test fails
- [ ] Add to `package.json` scripts: `"test:scripts": "bash test/scripts/run-all.sh"`

### Task 4.2: Validate JSON schemas

**Files:** `test/scripts/validate-schemas.sh` (new)

- [ ] For each script, define expected top-level keys
- [ ] Run each script against fixtures, pipe output to `jq` schema validation
- [ ] Ensure all scripts produce parseable JSON (no trailing commas, no stderr pollution in stdout)

### Task 4.3: Final skill audit

- [ ] Re-count lines in all modified skills
- [ ] Verify forge skill is under 200 lines
- [ ] Verify no procedure prose remains that should be a script
- [ ] Verify all scripts referenced in skills actually exist
- [ ] Run full `/forge` lifecycle on a test feature to confirm no regression

### Task 4.4: Update documentation

- [ ] Add "Script Architecture" section to CLAUDE.md describing the `scripts/forge/` convention
- [ ] Update CHANGELOG.md with the script extraction work
- [ ] Add `scripts/forge/README.md` with usage examples for each script

**Acceptance:** All tests pass. All skills under target line counts. `/forge` lifecycle works end-to-end. Documentation updated.

---

## Dependencies Between Waves

```
Wave 1 (entry + roadmap) ─── independent, ship first
Wave 2 (blueprint) ───────── depends on Wave 1 (common.sh)
Wave 3 (bug-fix) ─────────── depends on Wave 2 (extract-spec-refs.sh reused)
Wave 4 (test + cleanup) ──── depends on all waves
```

Waves 1-3 are each independently shippable. Each wave produces working scripts + updated skills + tests for that wave.

## Open Decisions

| Decision | Options | Recommendation |
|---|---|---|
| Script language | Bash vs Node.js | **Bash** for file operations (lighter, no startup cost). Node only if JSON assembly gets complex enough to warrant it. |
| `jq` requirement | Hard require vs fallback to `node -e` | **Hard require** with install hint. `jq` is the standard tool for JSON in shell. |
| Script location | `scripts/forge/` (project) vs `~/.claude/scripts/` (global) | **Project** (`scripts/forge/`). Scripts reference project-specific paths. |
| Test framework | Plain bash assertions vs bats-core | **Plain bash**. No external dependency. `[ "$actual" = "$expected" ] || fail` is sufficient. |
