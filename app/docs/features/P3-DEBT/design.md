# P3-DEBT: Agent Awareness Pipeline Tech Debt Sweep

**Date:** 2026-02-15
**Source:** 3x review of Phase 3 implementation (items 11-14)

## Problem

Five items of tech debt accumulated during the rapid Phase 3 build. None cause user-visible bugs, but they reduce code quality, theme correctness, and maintainability.

## Debt Items

### 1. AppSidebar monolith (456 lines) + stale React.memo

AppSidebar.jsx is 456 lines handling two unrelated concerns: stable navigation (views, phases, search, stats) and volatile agent telemetry (status, activity, errors, session). It's wrapped in `React.memo` that doesn't work — `agentActivity` and `sessionState` props create new references on every tool use.

**Fix:** Extract `AgentPanel.jsx` from lines 219-356 of AppSidebar. Move the agent status listener, tick effect, resolved items logic, and SessionTimer into it. Remove `React.memo` from AppSidebar (honesty over pretense — the memo was always bypassed by volatile props, and sidebar renders are cheap enough that memo isn't needed).

**Extraction boundary:**
- `AgentPanel` receives: `agentActivity`, `agentErrors`, `sessionState`
- `AgentPanel` owns internally: `agentState` (OSC listener), tick effect, `resolvedItems` fade timer, `SessionTimer`
- `AppSidebar` keeps: project header, search, views, phases, stats bar
- Shared constants: `CATEGORY_LABELS`, `CATEGORY_COLORS`, `ERROR_TYPE_LABELS`, `formatElapsed` — move to a shared file or keep inline in AgentPanel

### 2. Hardcoded hex colors in CATEGORY_COLORS

`AppSidebar.jsx:87-95` uses `#fbbf24`, `#f97316`, `#06b6d4`, `#a855f7` directly. These don't adapt to theme changes.

**Fix:** Add `--color-category-*` custom properties to `src/index.css` (after brand colors at line 115). Reference them in CATEGORY_COLORS. Use the same values for dark mode; add lighter variants for light mode if needed.

### 3. Duplicated TOOL_CATEGORIES

Same 10-line map exists in `server/vision-server.js:15-21` and `src/components/vision/Terminal.jsx`. Adding a new tool requires updating both.

**Fix:** Add cross-reference comments in both files: `// NOTE: Duplicated in Terminal.jsx / vision-server.js — keep in sync`. Not worth a shared module for 10 lines that rarely change.

### 4. agentActivity re-render churn

Every `agentActivity` WebSocket message triggers `setAgentActivity` in useVisionStore, which re-renders all consumers. During active work this is 5-20 updates/minute.

**Fix:** This is addressed by item 1. Once AgentPanel is extracted, only the agent panel re-renders on activity — not the entire sidebar. The churn is inherent to real-time telemetry; the fix is isolation, not elimination.

### 5. Haiku summaries lost on page refresh

`GET /api/session/current` doesn't include Haiku summaries at session level. On refresh, `sessionState.summaries` starts empty. The data exists in `sessionManager.currentSession.items[].summaries` but isn't aggregated.

**Fix:** In the `/api/session/current` response, aggregate all per-item summaries into a top-level `summaries` array. Client hydration picks it up automatically.

## Files to Modify

| File | Change | Type |
|------|--------|------|
| `src/components/vision/AgentPanel.jsx` (new) | Extract from AppSidebar: agent status, activity, errors, session info | New |
| `src/components/vision/AppSidebar.jsx` (existing) | Remove agent panel JSX + state, import AgentPanel, remove React.memo | Shrink |
| `src/index.css` (existing) | Add `--color-category-*` CSS custom properties | Small |
| `server/vision-server.js` (existing) | Aggregate summaries in /api/session/current, add TOOL_CATEGORIES comment | Small |
| `src/components/vision/Terminal.jsx` (existing) | Add TOOL_CATEGORIES cross-reference comment | Trivial |

## Phase Selection

- **Skip PRD:** Internal/technical, no user-facing requirements
- **Skip Architecture:** Single-component extraction, obvious approach
- **Skip Blueprint:** All files were read this session, patterns are known
- **Proceed to:** Plan → Execute
