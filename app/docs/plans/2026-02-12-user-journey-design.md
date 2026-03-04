# User Journey Design

**Date:** 2026-02-12
**Status:** PLANNED
**Related:** [Vision Component Spec](../specs/2026-02-11-vision-component-spec.md), [Core Requirements](../requirements/core-requirements.md), [Vision Surface Rebuild](2026-02-12-vision-surface-rebuild-design.md)

## The Intended Experience

User says "Build me X." Forge decomposes, asks the right questions, makes decisions (or prompts the user to make them), designs, plans, and directs agents to build it. One prompt in, working product out.

The user's primary interaction is **steering**, not driving. They see what's happening, intervene when they want to, and let the pipeline run when they don't.

## Journey Phases

### 1. Entry: User States Intent

The user types a prompt in the terminal. This is the only required input.

```
> Build me a task management app with Google auth and real-time sync
```

Forge intercepts this (or the agent reads it) and begins decomposition. The Vision Surface opens automatically.

**What the user sees:** Terminal shows the agent thinking. Vision Surface shows items appearing in real time as the agent decomposes the goal.

### 2. Discovery: Forge Asks, User Steers

The agent identifies ambiguities and surfaces them as **decision chips** — contextual UI elements that appear at the moment a decision is needed.

Decision chips follow the 3-mode dial:
- **Gate:** Agent stops. Chip appears. User must choose before work continues.
- **Flag:** Agent picks a default and proceeds. Chip appears as a notification. User can override.
- **Skip:** Agent decides silently. Decision recorded on Vision Surface but no chip shown.

Example gate decisions:
```
[Web app] [Mobile app] [Both]          — Platform
[OAuth only] [Email + OAuth] [Magic link] — Auth method
[PostgreSQL] [SQLite] [MongoDB]          — Database
```

Example flag decisions (agent proceeds with default, user notified):
```
Using React for frontend [OK] [Change]
Using Tailwind for styling [OK] [Change]
```

**What the user sees:** Vision Surface populates with decisions (green dots for crystallized, amber for pending). Tree view shows the decomposition hierarchy forming. Board shows items moving from planned → ready as decisions land.

### 3. Structuring: Requirements Through Planning

The agent works through the pipeline phases. Each phase produces items on the Vision Surface:

| Phase | Produces | User sees |
|-------|----------|-----------|
| Requirements | Feature specs, constraints, acceptance criteria | Items with type "spec", connected to the original decisions |
| Design | Architecture decisions, component breakdown | Items with type "decision", confidence updating as designs solidify |
| Planning | Task breakdown, dependency graph, build order | Items with type "task", connections showing `blocks` relationships |

The user can intervene at any point:
- **Change a decision:** Click item in Vision Surface, edit, agent re-plans downstream work
- **Kill an idea:** Mark as killed, agent drops it and anything it blocks
- **Reprioritize:** Drag items on the board, agent adjusts execution order
- **Add a constraint:** Create a new item, agent incorporates it

**What the user sees:** The tree deepens. The board fills with tasks. Confidence bars in the sidebar rise as things get validated. The list view shows low-confidence items at the top (things that need attention).

### 4. Building: Agents Execute

The agent (or multiple agents) executes the plan in the terminal. The Vision Surface tracks execution:

- Task starts → status moves to `in_progress`, terminal shows work
- Task completes → status moves to `review` or `complete`
- Task fails → status moves to `blocked`, error surfaces as a low-confidence item
- Agent needs a decision → decision chip appears (gate/flag/skip per policy)

**What the user sees:** Board view is the primary view during building. Tasks flow left to right: planned → ready → in_progress → review → complete. Blocked column catches problems. The user reviews the review column and either approves (→ complete) or sends back (→ in_progress with notes).

### 5. Verification: AI Tests Its Own Output

The agent generates and runs tests. Results feed back into the Vision Surface:

- Passing tests → items marked complete, confidence rises
- Failing tests → items created with low confidence, linked to the failing component
- The user reviews **failures**, not successes

**What the user sees:** A verification phase group appears in the list view. Red items (low confidence, blocked status) surface at the top. The user can investigate, ask the agent to fix, or mark as acceptable.

### 6. Delivery: Working Product

The pipeline converges. All items complete or explicitly parked/killed. The user has:
- Working code in the terminal/filesystem
- Complete decision history on the Vision Surface
- Artifact trail: specs, designs, plans, test results — all as items with connections

## The Control Surface

### 3-Mode Dial

The user's primary control. Sets the default for how much autonomy the agent has:

| Mode | Behavior | When to use |
|------|----------|-------------|
| **Gate** | Agent stops at every decision point. User approves each step. | Exploring unfamiliar territory. Learning what Forge does. |
| **Flag** | Agent proceeds with reasonable defaults. User gets notifications. | Normal operation. Trust the agent, review the output. |
| **Skip** | Agent proceeds silently. Decisions logged but not surfaced. | Well-understood domains. "Just build it." |

The dial can be set globally or per-phase. Gate mode for design, skip mode for implementation = "I want to approve the architecture but let the agent code freely."

### Vision Surface Views

Each view answers a specific question:

| View | Question | When to use |
|------|----------|-------------|
| **List** | What exists? What needs attention? | Browsing, reviewing, finding low-confidence items |
| **Board** | What's the status of everything? | During building — watching flow, unblocking |
| **Tree** | How do things connect? What depends on what? | Understanding structure, tracing decisions to implementation |

### Detail Panel

The user's editing surface. Click any item to:
- Read its full description and history
- Change status, confidence, phase
- See what it connects to (informs, blocks, supports)
- Trigger actions (pressure test, kill, connect to another item)

## What Exists Today

### Built (Session 10)
- Vision Surface with all three views (list, board, tree)
- Tree hierarchy derived from connections
- Detail panel with full item editing
- Sidebar with phase filters, search, confidence bars
- Theme toggle
- Design scheme applied
- Status model aligned with board lifecycle
- Server with CRUD API + WebSocket real-time sync

### Not Built Yet

Listed in priority order (highest value, lowest effort first):

#### 1. Agent Monitoring (read-only visibility)
**Value:** User sees what the agent is doing without switching to terminal.
**Mechanism:** Pattern-match PTY output for key events (file created, test run, error encountered). Create/update items on Vision Surface automatically.
**Effort:** Medium. Needs PTY output parsing + Vision API calls.

#### 2. Bidirectional Status Sync
**Value:** User drags item to "blocked" → agent stops. Drags to "ready" → agent picks it up.
**Mechanism:** Vision Surface status changes emit events. Agent subscribes and adjusts behavior.
**Effort:** Medium. Needs event system between Vision Surface and agent.

#### 3. Decision Chips
**Value:** The core UX of the 3-mode dial. Agent surfaces choices, user responds inline.
**Mechanism:** Agent creates items with type "decision" and status "planned". Vision Surface renders them as interactive chips. User response updates the item and unblocks the agent.
**Effort:** High. Needs agent-side protocol + UI rendering + response flow.

#### 4. Auto-Connection Creation
**Value:** Agent discovers dependencies and creates `informs`/`blocks` connections automatically.
**Mechanism:** Agent analyzes item content, code structure, and conversation context to infer connections.
**Effort:** High. Needs semantic analysis.

#### 5. Quick-Add
**Value:** User creates items from the keyboard without opening a dialog.
**Mechanism:** `/` key in Vision Surface opens an inline input. Type, hit enter, item created with defaults.
**Effort:** Low.

## Design Principles (Inherited)

1. **Information density over whitespace** — Mission control, not marketing.
2. **Hierarchy is primary navigation** — Tree view is the backbone.
3. **Speed over ceremony** — Creating an item: 2 seconds. No wizards.
4. **Keyboard-first** — Arrow keys, enter, `/` to search.
5. **Dark mode default** — Developer tool.
6. **Pipeline is descriptive, not prescriptive** — The AI's mental model, not the user's workflow.
7. **The 3-mode dial controls feel** — Same pipeline, different levels of human involvement.
