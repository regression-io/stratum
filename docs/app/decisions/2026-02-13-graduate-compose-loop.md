# Decision: Graduate Compose-Loop into Product

**Date:** 2026-02-13
**Status:** APPROVED
**Related:** [Compose-Loop Skill](../../.claude/rules/compose-loop.md), [Breadcrumb Rule](../../.claude/rules/breadcrumbs.md), [Agent Connector (Phase 4)](../plans/2026-02-11-integration-roadmap.md)

---

## Context

While building the Roadmap Drill-Down feature, we used the compose-loop pattern to coordinate multi-file work: main agent reads plans and dispatches scoped subagents, each with constrained scope, explicit deliverables, and build verification. This is the same pattern Compose the product is designed to formalize.

## The Gap

The current compose-loop is **ad-hoc infrastructure** — prompt templates, prose constraints, manual breadcrumbing. Compose the product needs the same pattern as **structured data**:

| Ad-hoc (now) | Formalized (product) |
|---|---|
| Hand-written subagent prompt | Context briefing generated from work item + dependencies + policies |
| "Don't touch these files" in prose | Policy dial: scope constraint (gate/flag/skip) |
| Breadcrumb log line before dispatch | Work item status → in_progress, session claimed |
| "Return: what you changed, build result" | Artifact schema: summary, evidence, verification result |
| Main agent reads summary | Distillation: session output → work item artifacts |
| Build check after each unit | Verification phase with pass/fail criteria |

## Decision

**The compose-loop pattern is the prototype for Compose's agent dispatch system.** Don't redesign from scratch — graduate what works:

1. **Prompt template → Context Briefing format** — The subagent prompt structure (what/scope/constraints/output) becomes the standard briefing schema that Compose generates for any session.
2. **Scope constraints → Policy enforcement** — "Files to read/edit/don't touch" becomes policy dials on the work item.
3. **Breadcrumbs → Status lifecycle** — Writing intent before work maps to claiming a work item and updating status.
4. **Summary capture → Artifact distillation** — The "return what you changed" convention becomes structured artifacts attached to work items.
5. **Build verification → Verification phase** — Post-unit build checks become acceptance criteria on the work item.

## What This Means for the Roadmap

- **Agent Connector (Read-Write)** in Phase 4 should be designed as "compose-loop, but structured." Not a new concept — a formalization of the working prototype.
- **The compose-loop skill stays** as the interim mechanism until the product can do it natively.
- **Breadcrumbs stay** as the intent tracking mechanism until the product's status lifecycle replaces them.
- **The transition is incremental** — each piece graduates independently. Breadcrumbs → status first, then prompt templates → briefings, then prose constraints → policies.

## Evidence

Session 14: Dispatched 4 subagents (research, component build, wiring, data creation) using compose-loop. Each received scoped prompts with explicit constraints and delivered structured summaries. The pattern worked — 1,272 lines of new components built, 18 tracker items created, zero context overflow.
