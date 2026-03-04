# Session 17: Skill Surgery

**Date:** 2026-02-14
**Focus:** Error/outcome detection (Phase 3 Step 13), feature-dev v2 rewrite, skill/rule redundancy audit

## What happened

Two distinct threads in one session. The first was building: error detection for the agent activity system. The second was pruning: a deep review of the feature-dev skill that turned into a 16-issue design discussion, a complete rewrite, and a redundancy audit that killed a skill.

**Error detection landed.** Three-layer architecture: hooks capture tool responses and failures, server pattern-matches 7 error types (build errors, test failures, git conflicts, permission errors, etc.), UI surfaces errors in the sidebar with red badges. The PostToolUseFailure hook was new — Claude Code fires it when tools error, providing the error string directly. We also enhanced the existing activity hook to forward `tool_response` (truncated to 500 chars) so the server can pattern-match errors in successful tool outputs too (a Bash command that exits 0 but prints "SyntaxError" is still an error).

**Then the skill review.** The human asked to review feature-dev 3x for gaps. Three passes found 15 issues. A 16th emerged during discussion (roadmap integration). We discussed each one-by-one — the human pushed back when we tried to drop issues too quickly, insisted agents should always propose options even at gates, and caught a miscount ("what is all 16? we never talked about it").

The discussion produced 16 design decisions, captured in `docs/features/feature-dev-v2/design.md` — the first file using the new feature-centric subfolder pattern (dogfooding the decision we just made). Key decisions: feature-centric subfolders, Claude Code integration not duplication, ralph loops for code reviews, gate semantics (agent always proposes), kill as a revise outcome.

**The rewrite.** Feature-dev SKILL.md went from v1 to v2: 12 phases with clear skip conditions, ralph loop prompts for Phases 8-9, execution skill decision table, blocker protocol, cross-cutting skills table expanded with all superpowers and interface-design skills.

**Then the audit.** Checked all skills and rules for redundancy with feature-dev v2. Found one: `forge-loop`. The human asked "why is this not universal instead of forge-loop specific?" and then "isn't it already part of claude's operating instructions?" — both correct. The core pattern (decompose, dispatch subagents, integrate) was already in superpowers skills. forge-loop was just a Forge-branded wrapper. Killed the skill, replaced the rule with a 3-line pointer to the superpowers skills.

**Finally, hooks.** The human noticed PostToolUse hooks inject `<system-reminder>` tags into context on every tool call. The activity hook had no matcher filter — it fired on Read, Grep, Glob, everything. That's hundreds of small context injections per session. Disabled all PostToolUse and PostToolUseFailure hooks pending a discussion on async hooks or batching strategies.

## What we built

### New files
- `docs/features/feature-dev-v2/design.md` — 16 design decisions from feature-dev review
- `scripts/agent-error-hook.sh` — PostToolUseFailure hook for error detection

### Modified files
- `~/.claude/skills/feature-dev/SKILL.md` — Complete v2 rewrite (12 phases, gates, ralph loops, cross-cutting skills)
- `scripts/agent-activity-hook.sh` — Added `tool_response` capture, fixed JSON injection vulnerability
- `.claude/settings.json` — Added then disabled PostToolUse/PostToolUseFailure hooks
- `server/vision-server.js` — `_detectError()` pattern matcher, `/api/agent/error` endpoint, error broadcasts
- `server/session-manager.js` — Error accumulator, `recordError()` method
- `src/components/vision/useVisionStore.js` — `agentError` WebSocket handler, `agentErrors` state
- `src/components/vision/AppSidebar.jsx` — Error display section, `StatsBar` ordering fix
- `src/components/vision/VisionTracker.jsx` — Pass `agentErrors` through to sidebar
- `.claude/rules/forge-loop.md` — Replaced with pointer to superpowers subagent skills

### Deleted files
- `~/.claude/skills/forge-loop/SKILL.md` — Redundant with superpowers skills

## What we learned

1. **Skills should be capabilities, not branded wrappers.** forge-loop was just "use subagents" with a Forge-specific name. The capability was already in superpowers. When you find yourself writing a skill that's mostly "invoke these other skills," it's probably not a skill — it's a trigger rule.

2. **Hooks have a hidden context cost.** Every hook execution generates a `<system-reminder>` in the conversation, even if the hook produces no stdout. An unfiltered PostToolUse hook fires hundreds of times per session. The context cost is invisible until you notice your sessions dying faster.

3. **The human catches what you rush past.** Three times in this session: dropping issue #13 too fast ("hold on, don't be too quick to drop #13"), miscounting resolved issues ("what is all 16?"), and removing the handoff artifacts table ("wait a second, are handoff artifacts really redundant?"). The pattern: slow down at gates.

4. **Design decisions need a home.** Writing the 16 decisions to `docs/features/feature-dev-v2/design.md` during the discussion — not after — prevented us from losing context across session boundaries. The design doc is the cross-session memory the skill page can't be.

5. **Pattern-matching errors in successful outputs catches more than failures.** A Bash command can exit 0 but print "SyntaxError" or "FAIL" in its output. PostToolUseFailure only fires on tool-level errors. Checking `tool_response` content catches the semantic failures that tools don't report as failures.

## Open threads

- [ ] Hook context cost discussion — async hooks? Batching? Matcher filters? (design doc discussion #5)
- [ ] Execution skill overlap — do subagent-driven-development and executing-plans need consolidation? (design doc discussion #1)
- [ ] Parallel track strategy — git worktrees for feature isolation (design doc discussion #2)
- [ ] Roadmap integration layers — which of the 4 layers to build first (design doc discussion #4)
- [ ] Feature naming convention — code names once roadmap is stable (design doc discussion #3)
- [ ] Re-enable hooks with matchers after context cost discussion

---

*We spent a session making tools for making tools, then decided some tools were just other tools wearing costumes.*
