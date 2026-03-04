# Vision Surface Implementation Plan

## Context

Forge has a two-panel layout: Terminal (xterm.js PTY) left, Canvas (markdown tab viewer) right. The Canvas needs to evolve into a multi-renderer shell so it can display the Vision Surface — an interactive card-based visualization showing ideas, decisions, questions, and their connections as they emerge from conversation.

This is the first permanent piece of the jigsaw: a visual surface where the AI (and human) can see, create, and evaluate work items. The POC HTML (`poc/vision-surface.html`, `poc/vision-surface-variations.html`) proved the feel. Now we build it in React.

**Key design decisions already made (Session 9):**
- Layout mode is a user knob (spatial/dense/timeline), not a design choice
- Inline conversation cards (Variation D) parked — not feasible with PTY
- Borrow Obsidian patterns, build our own renderers
- Canvas becomes CanvasUX: multi-renderer shell
- FileTreeRenderer noted as future renderer, out of scope

## Scope

**In:**
- Server: in-memory VisionStore + VisionServer (REST + WebSocket)
- Canvas.jsx evolution to multi-renderer shell
- VisionSurface with StatusBar, ItemMap, ItemCard, ConnectionLayer, DetailZone
- Layout mode knob (spatial/dense/timeline)
- Decision chips in DetailZone (visual only, no terminal integration yet)
- Openable via existing `/api/canvas/open` mechanism

**Out (deferred):**
- Terminal-to-vision AI item creation (needs agent connector)
- Persistence to disk (needs persistence connector)
- FileTreeRenderer, ZoomedOutView
- Decision chip → terminal integration
- Animations/transitions, keyboard nav, clustering/zoom
- Synthesis workflow (multi-select → merge)

## Data Model

```javascript
// VisionItem
{
  id: string,           // UUID
  type: 'idea' | 'decision' | 'question' | 'thread' | 'killed' | 'artifact',
  title: string,
  description: string,
  confidence: 0-4,      // untested, low, moderate, high, crystallized
  status: 'active' | 'crystallized' | 'killed',
  position: { x, y },   // spatial layout
  createdAt: ISO8601,
  updatedAt: ISO8601,
}

// VisionConnection
{
  id: string,
  fromId: string,
  toId: string,
  type: 'informs' | 'blocks' | 'supports' | 'contradicts',
  createdAt: ISO8601,
}
```

## API

**REST (registered by VisionServer):**

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/vision/items` | Full state (items + connections) |
| POST | `/api/vision/items` | Create item |
| PATCH | `/api/vision/items/:id` | Update item |
| DELETE | `/api/vision/items/:id` | Delete item + its connections |
| POST | `/api/vision/connections` | Create connection |
| DELETE | `/api/vision/connections/:id` | Delete connection |

**WebSocket (`/ws/vision`):** Broadcast-only. Sends full `visionState` snapshot on connect and after every mutation.

**Canvas open:** `POST /api/canvas/open` with `{"path": "vision://surface"}` opens the vision tab. Uses `vision://` scheme to distinguish from file paths.

## File Manifest

| # | File | Status | Purpose |
|---|---|---|---|
| 1 | `server/vision-store.js` | NEW | In-memory Map store for items + connections |
| 2 | `server/vision-server.js` | NEW | REST endpoints + WebSocket broadcast |
| 3 | `server/index.js` | MODIFIED | Wire store + server, add `/ws/vision` upgrade route |
| 4 | `server/file-watcher.js` | MODIFIED | Add `vision://surface` special path in `/api/canvas/open` |
| 5 | `src/components/Canvas.jsx` | MODIFIED | Multi-renderer shell: rendererType switching |
| 6 | `src/components/vision/useVisionStore.js` | NEW | Hook: WebSocket + REST state management |
| 7 | `src/components/vision/VisionSurface.jsx` | NEW | Composition root |
| 8 | `src/components/vision/StatusBar.jsx` | NEW | Phase, counts, attention, layout knob |
| 9 | `src/components/vision/ItemMap.jsx` | NEW | Container: cards + connections + layout modes |
| 10 | `src/components/vision/ItemCard.jsx` | NEW | Card: type dot, title, confidence, selection, drag |
| 11 | `src/components/vision/ConnectionLayer.jsx` | NEW | SVG overlay for relationship lines |
| 12 | `src/components/vision/DetailZone.jsx` | NEW | Selected item detail + action chips |
| 13 | `src/index.css` | MODIFIED | Add `--magenta` variable |

## Implementation Steps

### Step 1: Server — VisionStore + VisionServer + wiring
- `server/vision-store.js`: Class with Map-based storage, CRUD methods, getState()
- `server/vision-server.js`: Express routes + WebSocketServer, follows FileWatcherServer pattern
- `server/index.js`: Import, instantiate, attach, add upgrade route for `/ws/vision`
- **Verify:** curl CRUD against REST endpoints, wscat receives visionState on connect

### Step 2: Canvas.jsx → multi-renderer shell
- Add `rendererType` field to tab data structure (default `'markdown'`)
- Handle `vision://surface` in openFile WebSocket handler → sets rendererType to `'vision'`
- Content area: switch on rendererType (markdown → existing ReactMarkdown, vision → VisionSurface)
- Tab display: `vision://surface` shows as "Vision Surface"
- `server/file-watcher.js`: Add special path check in `/api/canvas/open` before file read
- **Verify:** Existing markdown tabs work. `curl /api/canvas/open {"path":"vision://surface"}` opens vision tab

### Step 3: useVisionStore hook
- WebSocket connection to `/ws/vision` with reconnect (same pattern as Canvas.jsx)
- State: items[], connections[], connected
- Mutation functions: createItem, updateItem, deleteItem, createConnection, deleteConnection (REST calls)
- Full state replacement on visionState messages
- **Verify:** Hook connects, receives state, mutations round-trip through REST → WebSocket

### Step 4: VisionSurface shell + StatusBar
- VisionSurface: composes StatusBar + ItemMap placeholder + DetailZone placeholder
- StatusBar: phase label, item counts by type, attention flags, layout mode buttons
- State: selectedItemId, layoutMode
- **Verify:** Vision tab shows StatusBar with "0 items". Create items via curl → counts update live

### Step 5: ItemCard
- Type dot with color (ember=idea, success=decision, indigo=question, etc.)
- Border styles per type (left accent, dashed for questions, dimmed for killed)
- Confidence dots (4 circles, filled color shifts amber→green)
- Selection state (ember border + shadow)
- Click handler, drag handler (spatial mode)
- **Verify:** Cards render with correct visuals per type. Click selects. Drag repositions

### Step 6: ItemMap + ConnectionLayer
- ItemMap: container with layout mode rendering (spatial=absolute, dense=grid, timeline=flex horizontal)
- ConnectionLayer: SVG overlay, line styles per connection type, highlight on selection
- Background click deselects
- Drag: optimistic local update, debounced REST PATCH
- **Verify:** Cards + lines render. Selection highlights connections. Layout modes switch correctly

### Step 7: DetailZone
- Selected item: title, type badge, description, confidence (clickable to update), action chips
- Chips: Pressure test, Connect, Edit, Kill (styled: neutral/primary/danger)
- Kill chip sets status='killed', type='killed'
- No selection: placeholder text
- **Verify:** Select card → detail shows. Click confidence → updates. Kill → card dims

### Step 8: Polish + CSS
- Add `--magenta: #a87cb8` and `--magenta-glow` to index.css
- Visual review: all colors match design system (--forge-*, --ember, --ink-*, --border-*)
- Ensure existing markdown canvas still renders correctly

## Key Decisions

- **Separate WebSocket (`/ws/vision`)** not extending `/ws/files` — different data model, clean separation
- **REST mutations + WebSocket broadcast** — standard HTTP semantics for writes, real-time push for reads
- **Full state broadcast** on every mutation — simpler than deltas, under 100 items expected
- **`vision://surface` scheme** — reuses existing canvas open mechanism, no new API for agent to learn
- **No new npm deps** — SVG for connections, CSS Grid for dense layout, uuid already available
- **Design system colors from index.css** (--forge-*, --ember, etc.) — NOT the POC palette

## Verification

1. **Existing behavior preserved**: Open markdown files, tabs work, file watcher broadcasts
2. **Vision tab opens**: curl `/api/canvas/open` with vision://surface
3. **CRUD**: Create 5 items (different types), 3 connections. All render. Update confidence. Kill one. Delete connection
4. **Real-time sync**: Two browser windows, create item via API, both update
5. **Layout modes**: Toggle spatial/dense/timeline, cards re-layout, connections follow
6. **Selection flow**: Click card → detail. Click background → deselect. Switch cards
7. **Tab switching**: Markdown tab ↔ Vision tab, both preserve state
8. **Server restart**: WebSocket reconnects cleanly, state lost (expected, in-memory)
