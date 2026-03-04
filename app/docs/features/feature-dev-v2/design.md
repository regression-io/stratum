# Feature-Dev v2: Design Decisions

**Status:** Complete — all 16 issues resolved.
**Note:** The `feature-dev` skill was renamed to `forge` in v3 ([design](../skill-arch-upgrade/design.md)). This doc preserves the original naming for historical accuracy.

## Context

Review of the `feature-dev` skill (12-phase feature development lifecycle) identified 15 gaps. A 16th was added during discussion (roadmap integration). This doc captures all design decisions.

## Decision 1: Feature-Centric Subfolders

**Problem:** Phases 2 and 3 write `PRD.md` and `ARCHITECTURE.md` to project root. Running the lifecycle twice for different features overwrites the first.

**Decision:** All feature artifacts live in `docs/features/<slug>/`. The folder name is the slug — no dates in filenames. Chronology comes from git history. Which files exist tells you which phases were completed vs skipped:

```
docs/features/error-detection/
  design.md              # Phase 1 output
  blueprint.md           # Phase 4 output (Phases 2-3 skipped)
  plan.md                # Phase 6 output (= Claude Code's plan file)
  report.md              # Phase 10 output
  sessions/              # Copied conversation transcripts
    session-1739512800.jsonl
```

The absence of `prd.md` or `architecture.md` *is* the documentation that those phases were skipped.

**Naming:** Slugs will use feature code names once roadmap and naming are stable. Until then, descriptive kebab-case (`error-detection`, `session-tracking`).

## Decision 2: Claude Code Integration (Not Duplication)

**Problem:** Feature-dev duplicates several Claude Code native capabilities — plan mode, task tracking, session management.

**Decision:** Feature-dev is the *cross-session* lifecycle layer. Claude Code's native tools are the *within-session* execution layer. They combine, not compete:

| Concern | Owner | Mechanism |
|---------|-------|-----------|
| Lifecycle state (which phase are we in?) | Feature-dev | Which files exist in `docs/features/<slug>/` |
| Skip logic (do we need a PRD?) | Feature-dev | Phase Selection table + per-phase skip conditions |
| Plan writing & approval | Claude Code | `EnterPlanMode` writes to `docs/features/<slug>/plan.md` |
| In-flight task tracking | Claude Code | `TaskCreate`/`TaskUpdate` (ephemeral, per-session) |
| Raw session events | Claude Code | Session hooks → SessionManager |
| Event accumulation & summaries | Forge | SessionManager, Haiku batches |

**Provenance preservation:** Claude Code's ephemeral artifacts get copied into the feature folder:

- **Plan file:** Written directly to `docs/features/<slug>/plan.md` (not Claude Code's default temp location).
- **Session transcripts:** SessionEnd hook copies `.jsonl` transcript to `docs/features/<slug>/sessions/`.
- **Task snapshots:** Optional — dump TaskList state to `tasks-snapshot.md` before session end. Lowest priority since plan.md and report.md already capture planned vs actual.

## Decision 3: Review Gates — Ralph Loop for Code, 1x for Docs

**Problem:** The 3x review at Phase 8 is expensive and the pass differentiation (correctness → patterns → integration) doesn't match how reviewers actually work. Meanwhile, doc phases have no review gates at all.

**Decision:** Every phase transition gets a review gate. Code phases use ralph loop (iterate until clean). Doc phases get a single review pass.

```
Phase 1 → Design     ─── 1x review ──→ Phase 4
Phase 4 → Blueprint  ─── 1x review ──→ Phase 6
Phase 6 → Plan       ─── 1x review ──→ Phase 7
Phase 7 → Execute    ─── ralph loop ──→ Phase 8 (review till clean)
Phase 8 → Tests      ─── ralph loop ──→ Phase 9 (coverage & integration sweep till passing)
Phase 9 → Report     ─── 1x review ──→ Phase 11
```

**Ralph loop prompts:**

Phase 8 (Review):
```
/ralph-loop "Review implementation against docs/features/<slug>/blueprint.md
and docs/features/<slug>/plan.md. Fix all issues found.
Output <promise>REVIEW CLEAN</promise> when no actionable findings remain."
--completion-promise "REVIEW CLEAN" --max-iterations 10
```

Phase 9 (Coverage & Integration Sweep):
```
/ralph-loop "Write and run tests for the implementation in docs/features/<slug>/plan.md.
Fix failing tests. Output <promise>TESTS PASSING</promise> when all tests pass
and coverage targets are met."
--completion-promise "TESTS PASSING" --max-iterations 15
```

**Safety valve:** Max iterations cap prevents infinite loops. If review can't get clean in 10 passes, the problem is in the spec, not the code — surface to the human.

## Decision 4: Gate Semantics — Always Propose

**Problem:** "Gate" mode was ambiguous — could be read as "agent waits silently for human to initiate."

**Decision:** All three dial modes involve the agent proposing options with trade-offs. The difference is who has final say:

- **Gate:** Agent proposes options, human decides
- **Flag:** Agent decides, human gets notified with rationale
- **Skip:** Agent decides silently

The agent always does the thinking. Gates are not "block until human talks" — they're "block until human approves, but agent proposes."

## Decision 5: Kill is a Revise Outcome, Not a Separate Gate

**Problem (#4):** No abort/kill path at gates.

**Decision:** Kill isn't a separate gate outcome — it's what happens when a revise conversation concludes "this isn't worth doing." The human says "let's not" during revise, and the agent writes `killed.md` to the feature folder with the reason and phase. No new mechanism needed. The feature folder persists for provenance — it records *why* the feature was abandoned.

## Decision 6: No Hotfix Phase — Tracked via Roadmap

**Problem (#15):** Production bugs can't run 12 phases.

**Decision:** A hotfix isn't a feature — it's a task on the roadmap. It gets tracked as a work item (status, commits, session transcript). The existing tracking infrastructure (activity resolution, SessionManager, journal agent) already handles provenance. No feature-dev change needed.

## Decision 7: Blueprint and Blueprint Review Stay Separate

**Problem (#8):** Phase 4 (Blueprint) and Phase 5 (Blueprint Code Review) seem redundant.

**Decision:** Keep them separate. When the blueprint comes from a different context (prior session, different agent, human-written spec), its claims about the codebase are unverified. Phase 5 catches stale assumptions. Phase 5's skip condition remains: "skip when blueprint was written in the same session by someone who just read the files."

## Decision 8: Ralph Loops Self-Terminate — Not Skippable

**Problem (#1):** Phase Selection table implied Phases 8-9 could be skipped, but cross-cutting section said they're mandatory.

**Decision:** Remove Phase 8-9 skip rows from the Phase Selection table. Ralph loops self-terminate on clean input — if code is already reviewed and tested, the loop exits on iteration 1. No need to skip them; running them on clean code is cheap.

## Decision 9: Spikes at Phase 1 Gate, Not a Separate Phase

**Problem (#11):** No spike/POC phase for unproven technical assumptions.

**Decision:** No new phase. Add a checkpoint question to the Phase 1 → Phase 4 gate: "Does this design depend on unproven technical assumptions? If yes, list them." The human decides which need spikes (at gate mode, agent proposes which to spike). Spikes happen as roadmap tasks. Results go into the design doc under an "Assumptions & Validations" section. Then proceed to blueprint.

## Decision 10: Implementation Report Skip Condition

**Problem (#2):** Phase 10 has no "Skip when" clause.

**Decision:** Skip when the feature folder contains no `prd.md` or `architecture.md` — meaning the feature was small enough to skip formal requirements and architecture, so it's small enough to skip the report. Git history and session transcripts are sufficient provenance. Agent proposes skipping at the gate; human approves.

## Decision 11: Phase 9 Renamed — Coverage & Integration Sweep

**Problem (#5):** Phase 7 TDD and Phase 9 testing had unclear boundaries.

**Decision:** Phase 7 keeps inline TDD (write test, see fail, implement, see pass — per task). Phase 9 renamed to "Coverage & Integration Sweep" — specifically targets gaps TDD doesn't naturally produce: edge cases, error paths, cross-component integration, coverage targets. Ralph loop runs until coverage thresholds are met.

## Decision 12: Execution Skill Guidance — Needs Own Discussion

**Problem (#7):** Three execution skills (forge-loop, subagent-driven-development, executing-plans) with overlapping scope.

**Decision:** Add a decision table to Phase 7 as interim guidance:

| Condition | Use |
|---|---|
| Inside Forge, touching 3+ files | `forge-loop` |
| Independent tasks, parallelizable | `subagent-driven-development` |
| Sequential tasks with dependencies | `executing-plans` |

**Parked for deeper discussion:** The execution skill overlap may warrant a redesign rather than just guidance. Potentially consolidate into fewer skills or make forge-loop the Forge-aware wrapper around the generic skills.

## Decision 13: Artifact Versioning via Policy Setting

**Problem (#9):** Pre-implementation revisions overwrite artifacts without history.

**Decision:** Versioning strategy is a project-level or feature-level policy setting:

- **Verbose:** Commit on every save (full revision trail, noisy git history)
- **Clean:** Commit at gate boundaries only (one commit per phase)
- **Default:** Commit at gate boundaries; agent proposes verbose if the revision is significant

Implementation detail parked — the decision is that versioning is configurable behavior, not hardcoded.

## Decision 14: External Blockers — Prompt Guidance

**Problem (#12):** Lifecycle assumes self-contained work. No guidance for external blockers.

**Decision:** Add prompt guidance to the skill: when an agent hits an external blocker, it must:

1. Record the blocker reason in the feature folder (append to design doc or write `blocked.md`)
2. Set the roadmap item to `blocked` status with reason
3. Surface the blocker to the human with options (wait, workaround, descope)

No new mechanism — just explicit instructions so the agent doesn't silently stall.

## Decision 15: Multi-Feature Overlap Awareness

**Problem (#13):** No guidance for parallel features touching shared files.

**Decision:** At Phase 4 (Blueprint) entry, check for overlapping in-flight features. Scan other feature folders' blueprints for file references, or check the tracker for in-progress items with overlapping `files` arrays. If overlap found, flag to the human.

This is an awareness check, not a coordination system.

**Parked for deeper discussion:** Parallel track strategy needs its own design conversation. Options include git worktrees (branch-per-feature), sequential feature locks, or explicit dependency ordering. The awareness check is the minimum viable version.

## Decision 16: Roadmap Integration at Phase Boundaries — Needs Own Discussion

**Problem (#16):** Roadmap doesn't get updated when brainstorming starts or phases complete. The vision-tracking rule says "every artifact gets a board item" but relies on the agent remembering. In practice this gets forgotten.

**What we know so far:**

Tracker updates should happen at phase boundaries — the same points where gates fire:

| Moment | Tracker action |
|---|---|
| Phase 1 starts | Create item, status `planned`, phase `vision` |
| Phase 1 gate passes | Update phase to `design` |
| Phase 4 completes | Update phase to `planning` |
| Phase 7 starts | Update status to `in_progress`, phase to `implementation` |
| Phase 8-9 (ralph loops) | Update phase to `verification` |
| Phase 11 (docs) | Update status to `review` |
| Phase 12 (ship) | Update status to `complete` |

**Four layers identified** — not mutually exclusive, each covers different failure modes:

1. **Skill prompt (intent)** — skill tells the agent "update the tracker now." Happy path. Fails when agent forgets or session dies.
2. **Gate hook (enforcement)** — gate fires, tracker updates automatically. Catches what agent misses. Fails for work outside gates (hotfixes, informal work).
3. **File watcher (reconciliation)** — watches `docs/features/*/` for changes, reconciles tracker state. Safety net. Catches everything layers 1-2 miss.
4. **Session hooks (provenance)** — SessionStart/SessionEnd check for in-progress features, reconcile tracker on session boundaries. Catches cross-session gaps.

```
Agent writes artifact
  ↓
Skill prompt says "update tracker"     ← Layer 1 (best effort)
  ↓
Gate fires → hook updates tracker      ← Layer 2 (enforcement)
  ↓
File watcher sees new file → reconcile ← Layer 3 (safety net)
  ↓
Next session starts → reconcile        ← Layer 4 (cross-session)
```

**Parked for deeper discussion:** Which layers to build, in what order, and how much infrastructure each needs. Layer 1 is just prompt text. Layers 2-4 need varying degrees of automation.

## Open Design Discussions

These were identified but need their own conversations:

1. **Execution skill redesign** (Decision 12) — forge-loop killed (was just a wrapper around superpowers skills). Remaining question: do subagent-driven-development and executing-plans overlap enough to consolidate?
2. **Parallel track strategy** (Decision 15) — git worktrees? Branch-per-feature? How do parallel features coordinate?
3. **Feature naming** (Decision 1) — code names once roadmap and naming are stable.
4. **Roadmap integration layers** (Decision 16) — which of the 4 layers to build, in what order, infrastructure needed. → Now addressed in [Lifecycle Engine Roadmap](../../plans/2026-02-15-lifecycle-engine-roadmap.md) Layers 1-2.
5. **Hook context cost** — PostToolUse/PostToolUseFailure hooks each inject a `<system-reminder>` into context per tool call. Disabled for now. Need to evaluate: async hooks that don't return to context? Batch instead of per-call? Only fire on specific tools?
6. **Multi-agent support** — The lifecycle is agent-agnostic; agent-specific adapters map to each agent's native tools. → Now addressed in [Lifecycle Engine Roadmap](../../plans/2026-02-15-lifecycle-engine-roadmap.md) Layer 7.
7. **User preferences inventory** — What's configurable, where prefs come from, what they control. Feature toggles, policy defaults, agent settings, UI preferences. → Now addressed in [Lifecycle Engine Roadmap](../../plans/2026-02-15-lifecycle-engine-roadmap.md) Layer 0.

## Productization

The `/forge` skill (formerly `feature-dev`) is the process specification for Forge's lifecycle engine. The gap between skill (advisory) and product (structural enforcement) is documented in the [Lifecycle Engine Roadmap](../../plans/2026-02-15-lifecycle-engine-roadmap.md). Seven layers: user prefs → state machine → artifact awareness → policy runtime → gate UI → session binding → iteration orchestration → agent abstraction.
