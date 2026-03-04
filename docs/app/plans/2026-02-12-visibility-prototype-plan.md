# Visibility Prototype Plan

| | |
|---|---|
| **Date** | 2026-02-12 |
| **Context** | Session 10 — visibility as value, motion + views prototype |
| **Status** | Planned |
| **Related** | [Visibility as Value](../discovery/2026-02-12-visibility-as-value.md), [How to Build](../discovery/2026-02-12-how-to-build-visibility.md) |

---

## Purpose

The rails aren't about constraining how the AI codes. They're about making sure granular tasks are captured visually so the human can steer. This prototype nails the visual experience with mock data before wiring real data. The visual surface IS the product.

## Approach

Replace generic layout modes (dense/spatial/timeline) with purpose-built views that answer specific questions. Add motion as an information channel. Evolve existing components. All client-side, zero server changes.

---

## Step 0: Mock data enrichment

**Status:** Pending
**File:** `data/vision-state.json`

- [ ] Distribute `updatedAt` across 3 mock sessions:
  - Session A (~10 items): `2026-02-11T22:00:00Z`
  - Session B (~10 items): `2026-02-12T00:00:00Z`
  - Session C (~6 items): `2026-02-12T02:00:00Z`
- [ ] Add 4 decisions forming a reasoning chain connected via `informs`:
  1. "User personas: solo dev vs team" (vision, confidence 2)
  2. "Solo dev is primary persona" (vision, confidence 3, crystallized)
  3. "Terminal-first matches solo dev workflow" (design, confidence 3, crystallized)
  4. "Cloud sync deferred" (planning, confidence 2)
- [ ] Add 3 orphaned/low-confidence items for Risk view:
  1. "What happens with 500+ items?" (question, confidence 0, no connections)
  2. "Agent token costs at scale" (idea, confidence 0, no connections)
  3. "Real-time sync over flaky connections" (question, confidence 1, no connections)
- [ ] Update "Vision: Build me X" to have very recent `updatedAt`

**Result:** ~35 items, ~20 connections, varied timestamps, decision chain, risk items.

---

## Step 1: PhaseBar (view tabs replace layout modes)

**Status:** Pending
**Files:**
- `src/components/vision/PipelineBar.jsx` → rename to `PhaseBar.jsx`
- `src/components/vision/VisionSurface.jsx` — update imports, rename state

### Tasks
- [ ] Rename `PipelineBar.jsx` → `PhaseBar.jsx`
- [ ] Replace `LAYOUT_MODES` constant with `VIEWS`:
  ```
  Overview, Activity, Decisions, Risk, Spatial
  ```
- [ ] Change props: `layoutMode` → `activeView`, `onLayoutChange` → `onViewChange`
- [ ] View tabs replace layout mode buttons (right side of bar)
- [ ] Phase filters + lens toggle stay unchanged
- [ ] In `VisionSurface.jsx`: rename `layoutMode` state → `activeView`, default `'overview'`
- [ ] Update all downstream prop passing
- [ ] Existing layouts keep working: dense→overview, timeline→activity, spatial→spatial

**Verify:** View tabs render. Clicking tabs changes view. Existing phase filters still work. Nothing broken.

---

## Step 2: OverviewView (landing view)

**Status:** Pending
**Files:**
- `src/components/vision/views/OverviewView.jsx` (new)
- Create `src/components/vision/views/` directory

### Tasks
- [ ] Create `views/` directory
- [ ] Build `PhaseGroup` sub-component:
  - Collapsible header with phase name + item count
  - Confidence mini-bar (stacked colored segments proportional to confidence levels)
  - Gap warning dot (amber if avg confidence < 2 or unresolved questions)
  - Collapse/expand toggle (chevron)
- [ ] Build `OverviewView`:
  - Groups items by phase using `PhaseGroup`
  - Cards sorted by confidence within each phase (lowest first — attention-directing)
  - Grid layout per group: `repeat(auto-fill, minmax(200px, 1fr))`
  - Empty phase placeholders (subtle "No items" text for phases with 0 items)
- [ ] Wire into VisionSurface: when `activeView === 'overview'`, render OverviewView
- [ ] Pass through: items, connections, selectedItemId, onSelect, ripple props

**Verify:** Overview is default view. Phase groups render with health indicators. Collapsing works. Card selection and DetailZone integration unbroken.

---

## Step 3: ActivityView (temporal view)

**Status:** Pending
**File:** `src/components/vision/views/ActivityView.jsx` (new)

### Tasks
- [ ] Build `relativeTime(isoString)` utility (pure function, no library):
  - `<60m` → "Nm ago", `<24h` → "Nh ago", `<7d` → "Nd ago", else date
- [ ] Build `ActivityView`:
  - Groups items into "Recent" / "Earlier" / "Older" by `updatedAt` clustering
  - Sorted by `updatedAt` descending within each group
  - Section headers with count
- [ ] Add timestamp badge to cards in this view (relative time below confidence dots)
- [ ] Add recency glow: cards in "Recent" section get a one-shot CSS animation on render
- [ ] Wire into VisionSurface alongside OverviewView

**Verify:** Activity view groups items by recency. Recent items have subtle glow. Timestamps render. Card selection works.

---

## Step 4: Evaluate animation needs (decision point)

**Status:** Pending

### Tasks
- [ ] With Overview and Activity both working, test switching between them
- [ ] Assess: do cards teleport jarringly, or is a simple crossfade acceptable?
- [ ] If jarring → implement CSS FLIP transitions:
  - Before switch: record `getBoundingClientRect()` of all visible cards by `data-item-id`
  - Switch view (React re-renders)
  - After render: apply inverse transform, animate to `transform(0,0)`
- [ ] If acceptable → simple opacity crossfade (200ms)
- [ ] If CSS FLIP insufficient → add Framer Motion (`layoutId` on cards, `AnimatePresence`)
- [ ] Document decision

**Verify:** Switching between views feels smooth, not jarring.

---

## Step 5: DecisionsView

**Status:** Pending
**File:** `src/components/vision/views/DecisionsView.jsx` (new)

### Tasks
- [ ] Build chain detection: find sequences of decisions connected by `informs`
  - Build adjacency from connections where both endpoints are decisions
  - Find roots (no inbound `informs` from another decision)
  - Walk chains, return ordered arrays of decision IDs
- [ ] Build chain rendering:
  - Full-width cards (~400px max) with full description (not truncated)
  - Vertical connecting line between chained decisions (CSS border-left or SVG)
  - Phase badge + confidence dots on each card
  - Connected non-decision items shown as smaller chips below each decision
- [ ] Standalone decisions (not in a chain) render in secondary section
- [ ] Wire into VisionSurface

**Verify:** Decisions view shows only decisions. Mock decision chain from Step 0 renders as connected flow. Standalone decisions appear separately.

---

## Step 6: RiskView

**Status:** Pending
**File:** `src/components/vision/views/RiskView.jsx` (new)

### Tasks
- [ ] Compute risk categories from items + connections:
  - Orphaned: zero connections (inbound or outbound)
  - Low confidence: confidence 0 or 1
  - Unresolved blockers: items with outgoing `blocks` connections
  - Untested ideas: type=idea, confidence < 2
- [ ] Build sections with headers + count badges:
  - "Orphaned" (most alarming, listed first)
  - "Low Confidence"
  - "Unresolved Blockers"
  - "Untested Ideas"
- [ ] Risk badge on each card: short text explaining why it appears ("No connections", "Untested", "Blocks N items")
  - Implement as `riskReason` prop on ItemCard, or a wrapper component
- [ ] Subtle tint on risk cards (faint red/amber background)
- [ ] Wire into VisionSurface

**Verify:** Risk view surfaces orphaned items from Step 0. Badges explain why each item is there. Sections have correct counts.

---

## Step 7: SpatialView extraction + ViewContainer

**Status:** Pending
**Files:**
- `src/components/vision/views/SpatialView.jsx` (new, extracted)
- `src/components/vision/ViewContainer.jsx` (new)
- `src/components/vision/ItemMap.jsx` (delete)

### Tasks
- [ ] Extract spatial rendering code from `ItemMap.jsx` into `SpatialView.jsx`:
  - Absolute positioning from `item.position`
  - Drag handling
  - ConnectionLayer rendering
  - Background click to deselect
- [ ] Build `ViewContainer.jsx`:
  - Switch on `activeView`, render the right view component
  - Pass through all needed props (items, connections, selectedItemId, onSelect, ripple, etc.)
- [ ] Update `VisionSurface.jsx`: replace `ItemMap` with `ViewContainer`
- [ ] Delete `ItemMap.jsx`
- [ ] Delete `StatusBar.jsx` (unused, functionality in PhaseBar)

**Verify:** All five views render correctly. Spatial mode drag/connect works exactly as before. No regressions.

---

## Step 8: ItemCard evolution (recency + session diff)

**Status:** Pending
**Files:**
- `src/components/vision/ItemCard.jsx`
- `src/components/vision/VisionSurface.jsx`
- `src/index.css`

### Tasks
- [ ] Session diff logic in `VisionSurface.jsx`:
  - Read `forge:visionLastSeen` from localStorage on mount
  - Compute `newItemIds` set: items where `updatedAt > lastSeen`
  - Update `lastSeen` to `Date.now()` after a 3s delay (let animations play)
  - Pass `newItemIds` through ViewContainer to views to ItemCard
- [ ] Add `isNew` prop to ItemCard:
  - When true, render with `session-diff-glow` CSS animation (one-shot, 2s, ember box-shadow)
- [ ] Add recency dot:
  - Small ember dot, top-right corner of card
  - Only on items updated within recent threshold
  - CSS `recency-fade` animation: starts bright, fades to dim over 3s
- [ ] Confidence dot transitions:
  - Add `transition: background 0.3s ease, border-color 0.3s ease` to dot styles
- [ ] Add CSS keyframes to `index.css`:
  - `@keyframes session-diff-glow` (box-shadow pulse, one-shot)
  - `@keyframes recency-fade` (opacity 1 → 0.4, 3s)

**Verify:** On first load, recently changed items glow. Glow doesn't repeat on reload. Confidence changes animate smoothly. Recency dots visible on recent items.

---

## Step 9: ConnectionOverlay evolution

**Status:** Pending
**Files:**
- `src/components/vision/ConnectionLayer.jsx` → rename to `ConnectionOverlay.jsx`
- `src/index.css`

### Tasks
- [ ] Rename file + update imports
- [ ] Add SVG stroke-dashoffset animation:
  - On selection, connections to/from selected item animate `stroke-dashoffset` from full to 0
  - CSS: `@keyframes draw-line { to { stroke-dashoffset: 0; } }` (0.6s ease)
- [ ] DOM-position-based rendering for Overview view:
  - Cards get `data-item-id` attribute
  - ConnectionOverlay queries DOM for card positions via `getBoundingClientRect()`
  - Recalculates on layout change (ResizeObserver or useLayoutEffect)
- [ ] Fallback: if DOM positioning is fragile, connections only render in Spatial view
  - Other views show connections via DetailPanel's related items section instead

**Verify:** Connections render in Overview (not just Spatial). Selecting a card animates connections drawing in. Lines reposition on resize.

---

## Step 10: DetailPanel evolution

**Status:** Pending
**File:** `src/components/vision/DetailZone.jsx` → rename to `DetailPanel.jsx`

### Tasks
- [ ] Rename file + update imports
- [ ] Add related items section:
  - List items connected to selected item with connection type label
  - Each related item clickable (selects that item)
  - Format: `[informs] → "Item title" (type)`
- [ ] Inline title editing:
  - Double-click title to edit
  - `contentEditable` span, blur commits via onUpdate
- [ ] Richer confidence display:
  - Show label alongside dots: "Untested", "Low", "Moderate", "High", "Crystallized"
- [ ] Timestamps: show created and last updated
- [ ] Better chip layout:
  - Primary: "Connect" (ember)
  - Secondary: "Pressure test", "Edit"
  - Destructive: "Kill" (danger, separated by gap)

**Verify:** Related items render and are clickable. Title editing works. Confidence has labels. Timestamps show.

---

## Step 11: CSS polish + animation tuning

**Status:** Pending
**File:** `src/index.css`

### Tasks
- [ ] Add all new keyframes (if not already added in prior steps):
  - `recency-fade`, `session-diff-glow`, `draw-line`
- [ ] Add risk card styles (faint red/amber tint)
- [ ] Add view transition classes (crossfade or FLIP, per Step 4 decision)
- [ ] Audit all new components against design system tokens:
  - Surfaces: `--forge-base`, `--forge-raised`, `--forge-overlay`
  - Text: `--ink-primary` through `--ink-muted`
  - Borders: `--border-standard`, `--border-emphasis`
  - Accents: `--ember`, `--indigo`, `--magenta`
- [ ] Remove unused pipeline glow CSS (noted as housekeeping from Session 9)
- [ ] Visual consistency review

**Verify:** All components look consistent. No jarring color mismatches. Animations feel right (not too fast, not too slow, not too noisy).

---

## Minimum viable prototype

Steps 0 → 1 → 2 → 3 → 8 get us: enriched mock data + PhaseBar with view tabs + OverviewView + ActivityView + session diff/recency indicators. This demonstrates the core feel: named views answering specific questions, motion as information.

## Constraints

- **Server files: ZERO changes.** All client-side + mock data. No risk of killing the terminal session.
- **No new npm packages** unless Step 4 determines Framer Motion is necessary.
- **Dark theme, information-dense.** Existing design tokens are correct.
- **Don't break existing functionality.** Selection, ripple, filtering, detail zone all preserved.
