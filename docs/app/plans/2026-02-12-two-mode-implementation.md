# Two-Mode Vision Surface Implementation Plan

**Status:** COMPLETE

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add Discovery/Execution mode toggle to the Vision Surface so thinking and building have distinct default views, scoped phases, and adapted sidebar stats.

**Architecture:** Pure UI change. A `mode` state in VisionSurface.jsx drives phase filtering, default view selection, and sidebar adaptation. No data model or server changes. Constants define which phases belong to each mode.

**Tech Stack:** React, shadcn/ui, Tailwind CSS, existing useVisionStore hook

---

### Task 1: Add mode constants

**Files:**
- Modify: `src/components/vision/constants.js`

**Step 1: Add mode phase arrays to constants.js**

Add after the existing `PHASES` array:

```js
export const DISCOVERY_PHASES = ['vision', 'requirements', 'design'];
export const EXECUTION_PHASES = ['planning', 'implementation', 'verification', 'release'];

export const MODE_DEFAULTS = {
  discovery: { view: 'tree', phases: DISCOVERY_PHASES },
  execution: { view: 'board', phases: EXECUTION_PHASES },
};
```

**Step 2: Verify build**

Run: `npx vite build 2>&1 | tail -3`
Expected: `built in` with no errors

**Step 3: Commit**

```bash
git add src/components/vision/constants.js
git commit -m "Add mode constants: DISCOVERY_PHASES, EXECUTION_PHASES, MODE_DEFAULTS"
```

---

### Task 2: Add mode state to VisionSurface

**Files:**
- Modify: `src/components/vision/VisionSurface.jsx`

**Step 1: Import mode constants**

Add to imports:
```js
import { MODE_DEFAULTS } from './constants.js';
```

**Step 2: Add mode state and derive filtering from it**

Replace the existing state declarations (lines 15-18) with:

```jsx
const [mode, setMode] = useState('discovery');
const [selectedItemId, setSelectedItemId] = useState(null);
const [viewOverrides, setViewOverrides] = useState({});
const [selectedPhase, setSelectedPhase] = useState(null);
const [searchQuery, setSearchQuery] = useState('');

// Active view: use override if set, otherwise mode default
const activeView = viewOverrides[mode] || MODE_DEFAULTS[mode].view;
const setActiveView = useCallback((view) => {
  setViewOverrides(prev => ({ ...prev, [mode]: view }));
}, [mode]);

// Mode switch handler
const handleModeChange = useCallback((newMode) => {
  setMode(newMode);
  setSelectedPhase(null);
  setSelectedItemId(null);
}, []);
```

**Step 3: Update the filtering logic**

Replace the existing `filteredItems` useMemo (lines 30-41) with:

```jsx
const filteredItems = useMemo(() => {
  const modePhases = MODE_DEFAULTS[mode].phases;
  let result = items.filter(i => modePhases.includes(i.phase));
  if (selectedPhase) result = result.filter(i => i.phase === selectedPhase);
  if (searchQuery) {
    const q = searchQuery.toLowerCase();
    result = result.filter(i =>
      i.title.toLowerCase().includes(q) ||
      (i.description || '').toLowerCase().includes(q)
    );
  }
  return result;
}, [items, mode, selectedPhase, searchQuery]);
```

**Step 4: Pass mode and handler to AppSidebar**

Update the AppSidebar JSX to add:
```jsx
<AppSidebar
  items={items}
  activeView={activeView}
  onViewChange={setActiveView}
  selectedPhase={selectedPhase}
  onPhaseSelect={setSelectedPhase}
  searchQuery={searchQuery}
  onSearchChange={setSearchQuery}
  connected={connected}
  mode={mode}
  onModeChange={handleModeChange}
/>
```

**Step 5: Pass mode to ItemDetailPanel**

Update the ItemDetailPanel JSX to add:
```jsx
<ItemDetailPanel
  item={selectedItem}
  items={items}
  connections={connections}
  onUpdate={handleUpdate}
  onSelect={handleSelect}
  onClose={() => setSelectedItemId(null)}
  mode={mode}
  onModeChange={handleModeChange}
/>
```

**Step 6: Verify build**

Run: `npx vite build 2>&1 | tail -3`
Expected: `built in` with no errors (AppSidebar/DetailPanel will ignore unknown props for now)

**Step 7: Commit**

```bash
git add src/components/vision/VisionSurface.jsx
git commit -m "Add mode state to VisionSurface, derive view/filter from mode"
```

---

### Task 3: Add mode toggle and adapted phases to AppSidebar

**Files:**
- Modify: `src/components/vision/AppSidebar.jsx`

**Step 1: Import mode constants**

Add to existing imports from constants.js:
```js
import { STATUS_COLORS, PHASES, PHASE_LABELS, MODE_DEFAULTS } from './constants.js';
```

**Step 2: Add mode and onModeChange to props**

Update the component signature:
```jsx
export default function AppSidebar({
  items,
  activeView,
  onViewChange,
  selectedPhase,
  onPhaseSelect,
  searchQuery,
  onSearchChange,
  connected,
  mode,
  onModeChange,
}) {
```

**Step 3: Add mode toggle in the header**

After the theme toggle button (around line 113), add a mode toggle between the project header and search. Insert after the closing `</div>` of the stats bar (after `<StatsBar>`) and before the search section:

```jsx
{/* Mode toggle */}
<div className="px-3 pb-2">
  <div className="flex rounded-md bg-muted p-0.5">
    {['discovery', 'execution'].map(m => (
      <button
        key={m}
        onClick={() => onModeChange(m)}
        className={cn(
          'flex-1 text-[10px] font-medium py-1 rounded transition-colors capitalize',
          mode === m
            ? 'bg-background text-foreground shadow-sm'
            : 'text-muted-foreground hover:text-foreground'
        )}
      >
        {m}
      </button>
    ))}
  </div>
</div>
```

**Step 4: Scope the phase list to the active mode**

Replace the existing `PHASES.map` loop in the Phases section. Change:
```jsx
{PHASES.map(phaseKey => {
```
to:
```jsx
{MODE_DEFAULTS[mode].phases.map(phaseKey => {
```

**Step 5: Adapt the stats to mode**

Replace the `StatsBar` component call and the item count / open questions display with mode-aware stats. Update the stats section (the area showing item count and open questions):

For **discovery mode**, show: item count, open questions count, avg confidence.
For **execution mode**, show: item count, complete count, blocked count.

Replace the stats display (the `<div>` with items.length and openQuestions) with:

```jsx
<div className="flex items-center gap-2 mt-1 flex-wrap">
  <span className="text-xs text-muted-foreground">
    {modeItems.length} items
  </span>
  {mode === 'discovery' ? (
    <>
      {openQuestions > 0 && (
        <span className="text-xs text-destructive">{openQuestions} open</span>
      )}
    </>
  ) : (
    <>
      {completeCount > 0 && (
        <span className="text-xs text-success">{completeCount} done</span>
      )}
      {blockedCount > 0 && (
        <span className="text-xs text-destructive">{blockedCount} blocked</span>
      )}
    </>
  )}
</div>
```

And compute the mode-scoped items and stats at the top of the component:

```jsx
const modePhases = MODE_DEFAULTS[mode]?.phases || PHASES;
const modeItems = items.filter(i => modePhases.includes(i.phase));
const openQuestions = modeItems.filter(i => i.type === 'question' && (i.confidence || 0) < 2).length;
const completeCount = modeItems.filter(i => i.status === 'complete').length;
const blockedCount = modeItems.filter(i => i.status === 'blocked').length;
```

Pass `modeItems` to StatsBar instead of `items`.

**Step 6: Verify build**

Run: `npx vite build 2>&1 | tail -3`
Expected: `built in` with no errors

**Step 7: Commit**

```bash
git add src/components/vision/AppSidebar.jsx
git commit -m "AppSidebar: mode toggle, scoped phases, adapted stats"
```

---

### Task 4: Add cross-references to ItemDetailPanel

**Files:**
- Modify: `src/components/vision/ItemDetailPanel.jsx`

**Step 1: Import mode constants**

Add to existing imports from constants.js:
```js
import { TYPE_COLORS, STATUS_COLORS, PHASES, PHASE_LABELS, STATUSES, CONFIDENCE_LABELS, MODE_DEFAULTS } from './constants.js';
```

Import ChevronRight and ChevronDown:
```js
import { X, Link2, Zap, Pencil, Trash2, ChevronRight, ChevronDown } from 'lucide-react';
```

**Step 2: Add mode and onModeChange to props**

Update the component signature:
```jsx
export default function ItemDetailPanel({ item, items, connections, onUpdate, onSelect, onClose, mode, onModeChange }) {
```

**Step 3: Add a CrossModeLinks component**

Add before the main component:

```jsx
function CrossModeLinks({ item, items, connections, mode, onSelect, onModeChange }) {
  const [isOpen, setIsOpen] = useState(false);
  const otherMode = mode === 'discovery' ? 'execution' : 'discovery';
  const otherPhases = MODE_DEFAULTS[otherMode].phases;

  // Find connections to items in the other mode
  const crossLinks = [];
  for (const conn of connections) {
    if (conn.fromId === item.id) {
      const target = items.find(i => i.id === conn.toId);
      if (target && otherPhases.includes(target.phase)) {
        crossLinks.push({ item: target, type: conn.type, direction: 'outgoing' });
      }
    }
    if (conn.toId === item.id) {
      const source = items.find(i => i.id === conn.fromId);
      if (source && otherPhases.includes(source.phase)) {
        crossLinks.push({ item: source, type: conn.type, direction: 'incoming' });
      }
    }
  }

  if (crossLinks.length === 0) return null;

  const handleCrossSelect = (targetId) => {
    onModeChange(otherMode);
    onSelect(targetId);
  };

  return (
    <div>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-1 text-[10px] font-medium uppercase tracking-wider text-muted-foreground hover:text-foreground transition-colors"
      >
        {isOpen ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
        Related ({otherMode}) ({crossLinks.length})
      </button>
      {isOpen && (
        <div className="mt-1 space-y-0.5">
          {crossLinks.map((link, idx) => (
            <button
              key={idx}
              onClick={() => handleCrossSelect(link.item.id)}
              className="flex w-full items-center gap-2 px-2 py-1 rounded text-left hover:bg-muted/50 transition-colors"
            >
              <div
                className="w-1.5 h-1.5 rounded-full shrink-0"
                style={{ background: STATUS_COLORS[link.item.status] || STATUS_COLORS.planned }}
              />
              <span className="text-xs text-foreground truncate">{link.item.title}</span>
              <span className="text-[10px] ml-auto shrink-0 text-muted-foreground">
                {link.direction === 'incoming' ? `${link.type} from` : `${link.type} to`}
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
```

**Step 4: Add CrossModeLinks to the detail panel body**

In the main component's scrollable body, after the `<RelatedItems>` section and before the timestamps, add:

```jsx
{/* Cross-mode references */}
<CrossModeLinks
  item={item}
  items={items}
  connections={connections}
  mode={mode}
  onSelect={onSelect}
  onModeChange={onModeChange}
/>
```

**Step 5: Verify build**

Run: `npx vite build 2>&1 | tail -3`
Expected: `built in` with no errors

**Step 6: Commit**

```bash
git add src/components/vision/ItemDetailPanel.jsx
git commit -m "ItemDetailPanel: collapsible cross-mode references"
```

---

### Task 5: Verify and polish

**Step 1: Full build verification**

Run: `npx vite build 2>&1 | tail -5`
Expected: Clean build

**Step 2: Manual verification checklist**

Open the app and verify:
- [ ] Mode toggle visible in sidebar
- [ ] Clicking Discovery shows tree view with vision/requirements/design phases
- [ ] Clicking Execution shows board view with planning/implementation/verification/release phases
- [ ] Phase filters scoped to current mode
- [ ] Stats adapted (questions count in Discovery, done/blocked in Execution)
- [ ] Clicking an item with cross-mode connections shows the collapsible section
- [ ] Clicking a cross-reference switches modes and selects the item
- [ ] View choice remembered per mode (switch to list in Discovery, switch to Execution and back — Discovery shows list)
- [ ] Search works across mode switch

**Step 3: Update handoff and journal**

Update `.claude/handoff.md` with the new mode feature.
Update the journal entry.

**Step 4: Final commit**

```bash
git add .claude/handoff.md docs/journal/
git commit -m "Session 11: two-mode Vision Surface (Discovery + Execution)"
```
