# Skill Architecture Upgrade: Agent Definitions + Rename

**Status:** Phase 1 — Design
**Roadmap item:** 19a (Phase 5.5)

## Problem

Our `feature-dev` skill (v2) is a monolithic SKILL.md that references superpowers skills indirectly. It works, but has three structural gaps:

1. **No dedicated agents.** Codebase exploration, architecture design, and code review are done inline by the main agent. This means the main context window carries all the exploration noise. Anthropic's official plugin directory demonstrates the pattern of dedicated agent definitions (`.claude/agents/*.md`) with model selection, tool restrictions, and focused prompts.

2. **Single-pass architecture.** Our Phase 3 (Architecture Doc) produces one approach. Anthropic's pattern launches 2-3 architect agents with different mandates (minimal, clean, pragmatic) and presents competing proposals. Better design signal.

3. **No review filtering.** Our ralph loop review surfaces everything. Anthropic's compose-reviewer uses confidence scoring (0-100, only report ≥80) to reduce false positives. Our loops would benefit from this.

4. **Name collision.** Our skill is called `feature-dev`, same as Anthropic's official plugin. Ours is a lifecycle engine; theirs is a session workflow. The name should reflect the distinction.

## Constraints

- **License:** Anthropic's plugin repo has no LICENSE file. We adopt ideas/patterns, not code. All prompts are original.
- **No infrastructure changes.** This is a skill/agent definition change. No server code, no UI, no persistence changes.
- **Backward compatibility.** The lifecycle phases, gate protocol, feature folder convention, ralph loops, and provenance system stay exactly the same. This is additive.
- **Global scope.** Agents and the skill live in `~/.claude/`, not in the Compose project. They're user-level tools.

## Design

### Change 1: Dedicated Agent Definitions

Create three agents in `~/.claude/agents/`:

**`compose-explorer.md`** — Codebase analysis specialist
- Model: sonnet (cost-efficient for exploration)
- Tools: Read-only (Glob, Grep, Read, WebFetch, WebSearch)
- Mission: Trace feature implementations, map architecture layers, document dependencies
- Output: Comprehensive analysis with file:line references + list of 5-10 essential files to read
- Invoked by: Phase 1 (2-3 explorers in parallel with different foci) and Phase 4 (blueprint research)

**`compose-architect.md`** — Architecture design specialist
- Model: sonnet
- Tools: Read-only (same as explorer)
- Mission: Design feature architectures and implementation blueprints
- Output: Patterns found, architecture decision with rationale, component design, implementation map, build sequence
- Invoked by: Phase 3 (2-3 architects with competing mandates)

**`compose-reviewer.md`** — Code review specialist
- Model: sonnet
- Tools: Read-only (same)
- Mission: Review code for bugs, quality, and project conventions
- Output: Issues with confidence scores (0-100), only report ≥80. File:line references. Concrete fixes.
- Invoked by: Phase 7 step 2 (ralph loop review iterations)

**Why sonnet for all three:** These agents do read-only analysis. Sonnet is sufficient for pattern recognition, code tracing, and review. Opus stays on the main orchestrating agent where judgment matters. This cuts agent cost significantly.

**Why read-only tools:** These agents should never edit files. They analyze and report. The main agent acts on their findings.

### Change 2: Competing Architecture Proposals

Phase 3 currently says "Write an Architecture Document." Replace with:

1. Launch 2-3 `compose-architect` agents in parallel with different mandates:
   - **Minimal changes** — smallest change, maximum reuse of existing code
   - **Clean architecture** — maintainability, elegant abstractions, clear boundaries
   - **Pragmatic balance** — speed + quality, the 80/20 approach
2. Each architect returns an independent proposal
3. Main agent reviews all proposals, forms an opinion on best fit for this specific feature
4. Present to human: brief summary of each, trade-offs comparison, recommendation with reasoning
5. Human picks (or asks for a hybrid)

**Skip when:** Feature is small enough that a single architecture pass suffices (single-component changes where Phase 3 would otherwise be skipped entirely).

### Change 3: Confidence-Scored Review

Add confidence scoring to the compose-reviewer agent definition. The scoring rubric:

| Score | Meaning |
|-------|---------|
| 0 | False positive, pre-existing issue, or stylistic nitpick not in project guidelines |
| 25 | Might be real, might be false positive. Low confidence. |
| 50 | Real issue but minor, unlikely to hit in practice. Not critical. |
| 75 | High confidence. Verified real. Will impact functionality or violates project guidelines. |
| 100 | Certain. Confirmed, will happen frequently, evidence directly supports. |

**Reporting threshold: ≥80.** The ralph loop still iterates until clean, but each iteration's review only surfaces high-confidence findings. This reduces noise on early iterations where obvious issues dominate.

The threshold doesn't weaken the review — it focuses it. Low-confidence issues that persist across iterations will get re-evaluated and may cross the threshold as the reviewer gains more context.

### Change 4: Rename to `compose`

Rename the skill from `feature-dev` to `compose`:

1. Move `~/.claude/skills/feature-dev/` → `~/.claude/skills/compose/`
2. Update `name:` in SKILL.md frontmatter
3. Update references in Compose codebase (8 files)
4. Update references in other skills (`bug-fix`)
5. `docs/features/feature-dev-v2/` stays as-is (historical provenance)

**Why `compose`:** Short, branded, unmistakable. The skill IS Compose's core workflow — the structured implementation pipeline. "feature-dev" describes what Anthropic's plugin does (develop a feature in one session). "compose" describes what ours does (the full Compose lifecycle). The rename also eliminates the name collision.

## Integration Points

The three agents integrate into existing lifecycle phases:

| Phase | Before (v2) | After (v3) |
|-------|-------------|------------|
| Phase 1: Explore & Design | Main agent explores inline | Launch 2-3 `compose-explorer` agents, read their findings |
| Phase 3: Architecture Doc | Main agent writes one approach | Launch 2-3 `compose-architect` agents with competing mandates |
| Phase 4: Blueprint | Main agent reads files | Launch `compose-explorer` for targeted research |
| Phase 7 step 2: Review loop | `superpowers:requesting-code-review` | Launch `compose-reviewer` with confidence scoring |

Everything else stays identical: gate protocol, feature folders, ralph loops, TDD, provenance, Phase Selection table.

## What We're NOT Doing

- **Not adopting Anthropic's plugin format.** Their `.claude-plugin/plugin.json` + `commands/` + `agents/` structure is the official plugin packaging format. We may adopt it later, but this upgrade is about the agent definitions and skill content, not the packaging.
- **Not reducing phases.** Anthropic's 7-phase workflow is simpler. Ours has 10 phases for good reasons (blueprint verification, implementation report, doc update, ship). We keep all 10.
- **Not adding clarifying questions as a separate phase.** Anthropic separates this explicitly (Phase 3 in their workflow). Our Phase 1 embeds it via brainstorming skill. We could separate it later, but it's not worth a phase-numbering change right now.

## Assumptions & Validations

- **Claude Code agents directory:** `.claude/agents/*.md` is the documented pattern for user-level agent definitions. Agent frontmatter supports `model`, `tools`, and `name` fields. ← Needs verification against Claude Code docs.
- **Agent model override:** Specifying `model: sonnet` in agent frontmatter actually works to run the agent on Sonnet regardless of the main session's model. ← Needs verification.
- **Agent tool restrictions:** Listing specific tools in frontmatter restricts what the agent can use. ← Needs verification.

## Rename Blast Radius

**Codebase files to update (8):**
1. `CLAUDE.md` — multiple references to "feature-dev" (existing)
2. `docs/plans/2026-02-11-integration-roadmap.md`
3. `docs/features/feature-dev-v2/design.md` — cross-references (keep folder name)
4. `docs/plans/2026-02-15-lifecycle-engine-roadmap.md`
5. `docs/journal/README.md` — session 17 summary
6. `docs/journal/2026-02-14-session-17-skill-surgery.md`
7. `docs/journal/2026-02-13-session-12-ontology-graph.md`
8. `docs/design/2026-02-13-product-realignment.md`

**Skills to update (2):**
1. `~/.claude/skills/feature-dev/SKILL.md` — the skill itself (move + rename)
2. `~/.claude/skills/bug-fix/SKILL.md` — references feature-dev

## Open Questions

None — all four changes are well-scoped and the user has already approved the direction. Proceed to gate.
