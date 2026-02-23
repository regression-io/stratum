---
name: stratum-learn
description: Review recent Claude Code session transcripts for this project and write Stratum-relevant conclusions to MEMORY.md — what spec patterns worked, what ensure expressions fired, what tasks struggled without Stratum.
---

# Stratum Learn

Review recent session transcripts and extract patterns worth remembering.

## When to Use

- After a few sessions on a project — enough transcript data to find patterns
- When `/stratum-review`, `/stratum-feature`, or `/stratum-debug` keep hitting the same retries
- When you want to improve the quality of future specs for this project

## Instructions

### 1. Find transcripts

The project hash is derived from the project root path: replace `/` with `-` (leading `/` becomes leading `-`). For example, `/Users/alice/work/myapp` → `-Users-alice-work-myapp`.

Transcripts are `.jsonl` files at:
```
~/.claude/projects/<project-hash>/*.jsonl
```

List them sorted by modification time and read the most recent 3–5. If the project hash is unknown, run:
```bash
ls -lt ~/.claude/projects/ | head -20
```
and identify the directory matching this project's path.

### 2. Extract Stratum signal

For each transcript, find:

**Tool calls to parse:**
- `stratum_plan` calls — what flow names were used, what inputs
- `stratum_step_done` calls — step results and any `ensure_failed` responses
- `stratum_audit` responses — final traces showing attempts and durations

**Patterns to identify:**
- Steps with `attempts > 1` and the violations that caused retries
- Ensure expressions that never fired (potentially useless for this project)
- Ensure expressions that fired on almost every run (important signal — make them defaults)
- Flow structures that completed cleanly vs. those that struggled
- Multi-step tasks where Stratum was NOT used but should have been (Claude went in circles, re-read files multiple times, produced inconsistent intermediate results)

### 3. Write conclusions

Read the existing `MEMORY.md` (`.claude/memory/MEMORY.md` or root) to avoid duplicates.

Append conclusions organized by tag:

```markdown
<!-- stratum-learn: <date> -->
[stratum-review] <project-specific security pattern to always check>
[stratum-review] <logic pattern that recurs in this codebase>
[stratum-feature] <test convention or module constraint>
[stratum-feature] <design decision that prevents a recurring mistake>
[stratum-debug] <confirmed root cause class — e.g. "timing assumptions fail on Linux CI">
[stratum-debug] <ruled-out hypothesis — e.g. "budget clone is not the issue here">
[stratum-refactor] <import constraint or extraction ordering rule>
[stratum-learn] <task type that benefits from Stratum but wasn't using it>
[stratum-learn] <ensure expression that fires every run — make it a default>
[stratum-learn] <ensure expression that never fires — probably remove it>
```

**Quality bar:** Only write entries that would change what you do next session. Skip:
- Observations true of all codebases ("output was vague")
- One-off flukes that won't recur
- Anything already in MEMORY.md

### 4. Report

Tell the user:
- How many sessions were reviewed
- How many new memory entries were written
- The most actionable 2–3 entries in plain English

## Narration Pattern

```
Reviewing [N] recent sessions...

Found [X] Stratum flows across [N] sessions.
[Y] steps needed retries — [Z] reveal project-specific patterns.
[W] tasks ran without Stratum but showed signs of struggling.

Writing [M] new memory entries.

Most actionable findings:
- [finding 1 in plain English]
- [finding 2 in plain English]
- [finding 3 in plain English]
```
