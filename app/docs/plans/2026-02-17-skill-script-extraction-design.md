# Skill Script Extraction: Reduce Token Count, Increase Determinism

**Date:** 2026-02-17
**Status:** PLANNED
**Phase:** design
**Related:** CLAUDE.md (Bootstrap Roadmap), `~/.claude/skills/forge/SKILL.md`, `~/.claude/skills/implement-blueprint/SKILL.md`, `~/.claude/skills/bug-fix/SKILL.md`, `~/.claude/skills/roadmap/SKILL.md`

## Problem

Skills are markdown prose injected into the LLM context window as input tokens. Every line of a skill is paid for on every invocation. Today, the forge skill stack is **1,303 lines across 5 skills** plus **194 lines across 3 agents** — nearly 1,500 lines of context consumed before the agent does any actual work.

Much of that prose describes **deterministic procedures**: "scan the feature folder," "check if status.md exists," "read every file in it," "verify all file:line references in the blueprint." These are algorithms masquerading as natural language instructions. The LLM interprets them probabilistically when they should execute mechanically.

This creates two problems:

1. **Token waste** — deterministic procedures described in prose cost tokens but gain nothing from LLM reasoning
2. **Non-determinism** — the LLM might skip steps, hallucinate file existence, or approximate counts that should be exact

## Prior Art

The `plugin-dev` plugin from Anthropic's official plugin directory already demonstrates the pattern. Its `hook-development` skill has companion scripts:

| Script | What It Does |
|--------|-------------|
| `hook-linter.sh` | Checks hook scripts for common issues (shebang, pipefail, variable quoting, exit codes) |
| `validate-hook-schema.sh` | Validates `hooks.json` structure, required fields, event names, timeout ranges |
| `test-hook.sh` | Tests individual hook scripts with sample input, measures execution time, validates output |
| `validate-agent.sh` | Validates agent markdown frontmatter, required fields, system prompt presence |

The skill's markdown says *when* to run the script and *how to interpret* results. The actual checking logic lives in bash. Zero tokens spent describing "check if the file starts with `---`" — the script just does it and returns pass/fail.

## Design

### Three Categories of Skill Content

#### Category 1: Script-Extractable (deterministic, mechanical)

Work that follows a fixed algorithm — no judgment needed, just execution. The output is structured data (JSON) that the LLM consumes to make decisions.

| Current Prose in Skills | Proposed Script | Output |
|---|---|---|
| "Scan `docs/features/<code>/` for existing artifacts, read whatever exists" (forge Phase Entry, ~20 lines) | `scan-feature.sh <feature-code>` | JSON: `{exists: bool, artifacts: {design: bool, prd: bool, blueprint: bool, plan: bool, ...}, status_md: {found: bool, next_phase: int, reason: str}}` |
| "Check if `status.md` exists, read resume point, delete it" (forge Phase Entry, ~8 lines) | Folded into `scan-feature.sh` | Included in scan output; deletion is a flag `--consume` |
| "For every file:line reference in the blueprint, verify it exists and matches" (forge Phase 5, ~15 lines) | `verify-refs.sh <blueprint-path>` | JSON array: `[{ref: "src/foo.js:42", status: "valid"|"stale"|"missing", actual: "..."}, ...]` |
| "Check for overlapping in-flight features: scan other blueprint files for shared file references" (forge Phase 4, ~5 lines) | `check-overlaps.sh <feature-code>` | JSON: `{overlaps: [{feature: "OTHER-1", shared_files: ["src/x.js", ...]}]}` |
| "Read the project's roadmap, count items by status" (roadmap skill, ~30 lines of discovery + counting) | `roadmap-status.sh [path]` | JSON: `{source: "CLAUDE.md", counts: {complete: N, active: N, planned: N, blocked: N, parked: N}, active_items: [...], recommendations: [...]}` |
| "List every file that will be modified, contains patterns to follow, defines types/schemas" (implement-blueprint Step 1, ~15 lines) | `extract-spec-refs.sh <spec-path>` | JSON array of file paths referenced in the spec, with categories |
| "Compare every spec assumption against reality" (implement-blueprint Step 3, ~10 lines) | `spec-reality-diff.sh <spec-path>` | JSON: corrections table with `{spec_says: "...", actual: "...", file: "...", line: N}` |
| "Gather test output, git blame, related files for triage" (bug-fix Phase 1, ~10 lines) | `gather-triage.sh [test-path] [error-msg]` | JSON: `{failing_tests: [...], recent_changes: [...], related_files: [...], blame: {...}}` |

#### Category 2: Judgment-Reducible (prose shrinks, script preps data)

The skill tells the LLM *what to decide*, but the mechanical prep work is scripted. The skill prose transforms from procedure descriptions to decision instructions.

**Before (forge Phase Entry, ~25 lines):**
> When `/forge` is invoked, always scan `docs/features/<feature-code>/` first before choosing a starting phase. Read whatever exists — design notes, partial specs, rough plans... Check if the folder exists. If not, start at Phase 1. If it exists, read every file in it. Summarize what's covered and what's missing. If `status.md` exists, read it — it tells you exactly where the last session stopped... [15-row decision table]

**After (~8 lines):**
> When `/forge` is invoked, run `scripts/forge/scan-feature.sh <feature-code>`. Use the JSON output to determine the starting phase:
> - `exists: false` → Phase 1
> - `status_md.found: true` → Start at `status_md.next_phase`, delete status.md with `--consume`
> - Otherwise, review the artifact booleans and propose the earliest incomplete phase

The decision table collapses because the script already resolved the mechanical question ("what exists?"). The LLM only handles the judgment question ("given what exists, where do we start?").

**Other judgment-reducible areas:**

- **Phase selection** — script returns structured state, skill shrinks from decision table to "interpret these fields"
- **Bug triage** — script collects test output + git blame + related files, skill focuses on severity/path judgment
- **Blueprint corrections** — script extracts file refs and reads actuals, skill focuses on "how to handle mismatches"

#### Category 3: LLM-Essential (must stay as prose)

Creative judgment, dialogue design, gate protocol, quality standards. These are the reason we use an LLM at all:

- How to explore 2-3 approaches with trade-offs
- How to present designs in 200-300 word sections for incremental validation
- Gate protocol (approve/revise/kill decisions and when to propose each)
- When to skip a phase and why
- Cross-cutting agent orchestration decisions (which agents to launch, with what mandates)
- The "what NOT to do" guardrails
- Ralph loop configuration and exit criteria interpretation

These stay as skill prose. They're the actual intelligence layer.

## Token Savings Estimate

| Skill | Current Lines | After Extraction | Reduction | Notes |
|---|---|---|---|---|
| `forge` | 381 | ~180 | ~53% | Scan, resume, overlap check, blueprint verification all become script calls |
| `implement-blueprint` | 136 | ~60 | ~56% | File identification + corrections table become scripts |
| `bug-fix` | 141 | ~90 | ~36% | Triage data gathering becomes script; investigation/fix judgment stays |
| `roadmap` | 96 | ~40 | ~58% | File discovery + counting + status parsing all become script |
| `nlm-skill` | 549 | ~549 | 0% | External tool reference — no extractable procedures |
| **Total** | **1,303** | **~919** | **~29%** | Excluding nlm-skill: **754 → ~370 (~51%)** |

The forge skill specifically — invoked on every feature lifecycle — drops from ~381 lines of context to ~180. That's ~200 lines saved per invocation. At ~4 tokens/line, that's ~800 input tokens saved each time `/forge` runs.

## Determinism Benefits

Beyond token savings, scripts are **deterministic and testable**:

| Property | Prose Instructions | Script |
|---|---|---|
| File existence check | LLM might hallucinate | `[ -f "$path" ]` — binary |
| Line counting | LLM approximates | `wc -l` — exact |
| File:line verification | LLM may skip or misread | `sed -n "${line}p"` — exact content |
| Overlap detection | LLM may miss features | `grep -r` across all blueprints — exhaustive |
| Roadmap counting | LLM loses count | `grep -c` — exact |
| JSON output | LLM may format inconsistently | `jq` — schema-guaranteed |

Scripts are also **independently testable** without burning API tokens. You can write `test/scripts/` fixtures and CI them.

## Proposed Scripts

```
scripts/forge/
  scan-feature.sh        # Scan docs/features/<code>/, return artifact inventory as JSON
  verify-refs.sh         # Verify all file:line references in a markdown document
  check-overlaps.sh      # Compare blueprint file refs across in-flight features
  roadmap-status.sh      # Parse roadmap source, count by status, return structured data
  gather-triage.sh       # Collect test output, git blame, related files for bug triage
  extract-spec-refs.sh   # Extract file path references from a spec/design doc
  spec-reality-diff.sh   # Read spec refs, compare to actual files, produce corrections table
```

### Script Interface Convention

All scripts:
- Accept positional args for required inputs
- Output **JSON to stdout** (parseable by the LLM or by `jq` in other scripts)
- Output diagnostics to **stderr** (visible in terminal but not mixed with JSON)
- Exit 0 on success, 1 on error, 2 on "success with warnings"
- Are executable (`chmod +x`), have shebangs, use `set -euo pipefail`
- Live under `scripts/forge/` in the coder-forge repo (not in `~/.claude/` — they're project-specific)

### Script Detail: `scan-feature.sh`

The highest-value extraction. Called on every `/forge` invocation.

**Input:** `scan-feature.sh <feature-code> [--consume]`

**Output:**
```json
{
  "feature_code": "FEAT-1",
  "path": "docs/features/FEAT-1",
  "exists": true,
  "artifacts": {
    "design": { "exists": true, "lines": 142, "has_open_questions": true },
    "prd": { "exists": false },
    "architecture": { "exists": false },
    "blueprint": { "exists": true, "lines": 280, "file_refs_count": 14 },
    "plan": { "exists": false },
    "report": { "exists": false },
    "killed": { "exists": false }
  },
  "phases": [
    { "name": "phase-1-core-model", "files": ["blueprint.md", "plan.md"] },
    { "name": "phase-2-ui", "files": ["blueprint.md"] }
  ],
  "sessions": { "count": 2, "latest": "session-2026-02-15T14:30:00.jsonl" },
  "status_md": {
    "found": true,
    "next_phase": 4,
    "through": "architecture",
    "reason": "Intentional partial execution (--through architecture)",
    "date": "2026-02-16"
  },
  "suggested_start": "Phase 4: Implementation Blueprint",
  "rationale": "design.md and architecture.md exist; blueprint.md missing; status.md indicates resume at Phase 4"
}
```

With `--consume`: deletes `status.md` after reading it (it served its purpose).

### Script Detail: `verify-refs.sh`

Second highest value. Eliminates the most verbose Phase 5 prose.

**Input:** `verify-refs.sh <markdown-path>`

**Behavior:** Extracts all `file:line` patterns from the markdown, reads each actual file at that line, compares.

**Output:**
```json
{
  "document": "docs/features/FEAT-1/blueprint.md",
  "total_refs": 14,
  "verified": 12,
  "stale": 1,
  "missing": 1,
  "refs": [
    { "ref": "src/models/work.js:42", "status": "valid", "context": "class Work extends Base {" },
    { "ref": "src/api/routes.js:108", "status": "stale", "expected_context": "router.post('/work'", "actual": "router.put('/work'" },
    { "ref": "src/lib/gone.js:5", "status": "missing", "reason": "file not found" }
  ]
}
```

### Script Detail: `roadmap-status.sh`

**Input:** `roadmap-status.sh [--source <path>]`

Falls back to the same discovery chain the roadmap skill currently describes in prose: CLAUDE.md config → convention paths → search.

**Output:**
```json
{
  "sources": ["CLAUDE.md#bootstrap-roadmap"],
  "counts": {
    "complete": 14,
    "in_progress": 2,
    "partial": 1,
    "planned": 11,
    "blocked": 0,
    "parked": 0
  },
  "active": [
    { "id": "15", "title": "Git/file connector", "status": "IN_PROGRESS", "phase": "Phase 4" },
    { "id": "16", "title": "Tab popout", "status": "PLANNED", "phase": "Phase 4" }
  ],
  "next_recommended": { "id": "15", "title": "Git/file connector", "reason": "First unblocked item in Phase 4" }
}
```

## Skill Rewrite Pattern

Each skill transforms from "procedure manual" to "orchestration brief." Example for the forge skill's entry section:

### Before (~25 lines)

```markdown
## Entry: Scan First, Then Decide

When `/forge` is invoked, **always scan `docs/features/<feature-code>/` first** before choosing a starting phase. Read whatever exists — design notes, partial specs, rough plans, anything a prior session or agent left behind. Those artifacts are inputs, not decoration.

1. Check if the folder exists. If not, start at Phase 1.
2. If it exists, read every file in it. Summarize what's covered and what's missing.
3. If `status.md` exists, read it — it tells you exactly where the last session stopped and what phase comes next. Delete `status.md` after reading (it served its purpose; the artifacts themselves are the durable state).
4. Integrate existing content — don't redo work that's already there. A rough `design.md` from a prior brainstorm means Phase 1 is partially done, not that it needs to start from scratch.
5. Propose the starting phase with rationale. The human approves.

[15-row Phase Selection table]
```

### After (~10 lines)

```markdown
## Entry: Scan First, Then Decide

Run `scripts/forge/scan-feature.sh <feature-code> --consume` and read the JSON output.

- If `exists: false` → start at Phase 1, create the feature folder
- If `status_md.found: true` → start at `status_md.next_phase` (status.md was consumed)
- Otherwise → review `artifacts` and `suggested_start`, propose the earliest incomplete phase

Existing artifacts are inputs, not decoration. A rough `design.md` means Phase 1 is partially done — review and fill gaps, don't redo. Default to reviewing and filling gaps over skipping.

**Gate:** Propose the starting phase with rationale. The human approves.
```

## Implementation Sequence

### Wave 1: Highest-frequency, highest-savings

- [ ] `scan-feature.sh` — called on every `/forge` invocation
- [ ] `roadmap-status.sh` — called on every `/roadmap` invocation
- [ ] Rewrite forge entry section and roadmap skill to use scripts

### Wave 2: Blueprint pipeline

- [ ] `verify-refs.sh` — called in Phase 5 (blueprint verification)
- [ ] `extract-spec-refs.sh` — called in Phase 4 (blueprint creation)
- [ ] `check-overlaps.sh` — called in Phase 4 (overlap detection)
- [ ] Rewrite forge Phases 4-5 and implement-blueprint to use scripts

### Wave 3: Bug-fix pipeline

- [ ] `gather-triage.sh` — called in bug-fix Phase 1 (triage)
- [ ] `spec-reality-diff.sh` — called in implement-blueprint Step 3
- [ ] Rewrite bug-fix triage and implement-blueprint corrections to use scripts

### Wave 4: Testing

- [ ] Create `test/scripts/` with fixture data (sample feature folders, sample blueprints)
- [ ] Test each script against fixtures
- [ ] Verify JSON output schema consistency

## Risks and Mitigations

| Risk | Mitigation |
|---|---|
| Scripts break when folder structure changes | Scripts live in the same repo as the folder structure — changes are co-committed |
| LLM ignores script output and hallucinates anyway | Skill prose explicitly says "use the JSON output" not "check the folder" |
| Scripts become their own maintenance burden | Keep scripts small and focused (one concern each, <150 lines) |
| `jq` dependency | macOS ships with `jq` via Homebrew; add a check at script top |
| Markdown parsing is fragile in bash | Use `grep`/`sed` for simple patterns; don't try to parse complex markdown — extract only file:line refs and status markers |

## Success Criteria

- [ ] Forge skill under 200 lines (down from 381)
- [ ] All scripts return valid JSON (tested with fixtures)
- [ ] `scan-feature.sh` output matches manual folder inspection for 3+ existing feature folders
- [ ] `verify-refs.sh` catches intentionally stale references in test fixtures
- [ ] No regression in forge lifecycle behavior (same phases execute, same gates fire)
- [ ] Scripts independently testable without API tokens

## Open Questions

1. **Where do scripts live?** `scripts/forge/` in coder-forge (proposed) vs `~/.claude/scripts/` (global). Project-specific feels right since the scripts reference project-specific paths (`docs/features/`).
2. **Should scripts be a plugin?** A `forge-scripts` plugin could make them portable. But they're tightly coupled to the forge project structure, so standalone scripts may be simpler.
3. **Node.js vs bash?** The existing `vision-track.mjs` is Node. Bash is lighter for file operations. Could go either way — bash for pure file checks, node for anything needing complex JSON assembly.
