# Session 18: Skill Architecture Upgrade

**Date:** 2026-02-15
**Focus:** Agent definitions, competing architecture proposals, confidence-scored review, feature-dev → compose rename

## What happened

The human spotted Anthropic's official `feature-dev` plugin in their `claude-plugins-official` repo (7.5k stars, published Nov 2025). The name collision with our own `feature-dev` skill prompted a comparison and then an upgrade.

**The comparison.** Anthropic's plugin is a 7-phase single-session workflow: discovery, codebase exploration, clarifying questions, architecture design, implementation, quality review, summary. Three dedicated agents (code-explorer, code-architect, code-reviewer) run on Sonnet for cost efficiency. Good ideas: competing architecture proposals (2-3 architects with different mandates), confidence-scored code review (0-100, only report ≥80), dedicated read-only agents that don't pollute the main context window.

Our skill was a 10-phase cross-session lifecycle with gates, ralph loops, blueprint verification, and provenance tracking. More rigorous, but monolithic — everything ran in the main agent's context, and references to superpowers skills were indirect.

**The license problem.** No LICENSE file in Anthropic's repo. Under copyright law, public + no license = all rights reserved. We couldn't copy their prompt text. But ideas aren't copyrightable, so we adopted their patterns and wrote our own implementations.

**The build.** Four changes, all additive:

1. **Three agent definitions** in `~/.claude/agents/`: `compose-explorer` (codebase analysis), `compose-architect` (architecture proposals), `compose-reviewer` (confidence-scored review). All run on Sonnet with read-only tool restrictions. The `compose-` prefix was a late addition — superpowers already ships a `code-reviewer` agent, so `code-reviewer` would have collided. The human caught this by asking us to check superpowers for conflicts.

2. **Competing architecture proposals** in Phase 3. Instead of one architecture pass, launch 2-3 `compose-architect` agents with different mandates (minimal changes, clean architecture, pragmatic balance). Each returns an independent proposal. The main agent reviews all three, forms a recommendation, and presents the comparison to the human.

3. **Confidence-scored review** in Phase 7's ralph loop. The `compose-reviewer` agent rates every potential finding 0-100 and only reports findings ≥80. This filters noise on early loop iterations where obvious issues dominate.

4. **Rename from `feature-dev` to `compose`.** Short, branded, no collision with Anthropic's plugin. Updated all references in the codebase (CLAUDE.md, plans, design docs) and in the bug-fix skill. Journal entries kept their original naming (historical provenance).

**Prior session recovery.** The session before this one (session 0 on 2026-02-15) was a ghost — 116 minutes, 0 tool uses, no commits. The transcript showed the same "Implement the following plan" queue operation repeated ~100+ times without the agent being able to process it. A stuck ralph loop or queue, never diagnosed.

## What we built

### New files
- `~/.claude/agents/compose-explorer.md` — Codebase analysis agent (Sonnet, read-only)
- `~/.claude/agents/compose-architect.md` — Architecture proposal agent (Sonnet, read-only)
- `~/.claude/agents/compose-reviewer.md` — Confidence-scored review agent (Sonnet, read-only)
- `~/.claude/skills/compose/SKILL.md` — Compose Lifecycle v3 (renamed from feature-dev)
- `docs/features/skill-arch-upgrade/design.md` — Design decisions for this upgrade

### Modified files
- `CLAUDE.md` — Added Phase 5.5, renamed Phase 6 header, marked 19a complete
- `~/.claude/skills/bug-fix/SKILL.md` — Updated feature-dev references to `/compose`
- `docs/features/feature-dev-v2/design.md` — Added rename note, updated productization reference
- `docs/plans/2026-02-15-lifecycle-engine-roadmap.md` — Updated skill path reference
- `docs/plans/2026-02-11-integration-roadmap.md` — Updated feature-dev references to `/compose`

### Deleted files
- `~/.claude/skills/feature-dev/SKILL.md` — Replaced by `~/.claude/skills/compose/SKILL.md`

## What we learned

1. **Check plugin namespaces before naming agents.** superpowers ships a `code-reviewer` agent. We almost created a `code-reviewer.md` in `~/.claude/agents/` that would have collided. User-level agents and plugin agents share the same namespace. Prefix everything.

2. **No license ≠ open source.** A public GitHub repo with no LICENSE file means all rights reserved under copyright law. GitHub TOS allows viewing and forking, but not copying/modifying/redistributing. You can adopt ideas (not copyrightable), but you must write your own implementations.

3. **Dedicated agents reduce context pollution.** Running codebase exploration and review as separate Sonnet agents means the main Opus context doesn't accumulate hundreds of lines of code trace output. The main agent gets the summary; the agent does the grunt work. Cost-efficient and context-efficient.

4. **Competing proposals produce better architecture decisions.** When one architect proposes, you evaluate that proposal. When three architects propose, you evaluate the *space* of solutions. The contrast between "minimal changes" and "clean architecture" reveals trade-offs that a single pass can't surface.

5. **Ghost sessions leave transcripts.** The prior session's stuck queue produced 5,039 JSONL lines — mostly the same prompt repeated. Worth investigating why the queue-to-agent pipeline got stuck, but the transcript proves the queue was trying.

## Open threads

- [ ] Investigate the ghost session (session 0) — why did the queue repeat the same prompt ~100 times without the agent processing it?
- [ ] Test the agents in practice — launch `compose-explorer`, `compose-architect`, `compose-reviewer` in a real `/compose` lifecycle to verify they work as expected
- [ ] Consider adopting Anthropic's `.claude-plugin` packaging format for distributing compose as a plugin
- [ ] Evaluate whether to separate "clarifying questions" as an explicit phase (Anthropic's Phase 3 pattern)

---

*We taught the compose to delegate its thinking, then realized we'd almost given its delegates someone else's name.*
