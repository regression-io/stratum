# Vision Component: Design

| | |
|---|---|
| **Date** | 2026-02-11 |
| **Source** | [Vision Component Spec](../specs/2026-02-11-vision-component-spec.md) |
| **Phase** | Design (active) |
| **Status** | Build strategy decided — falsework replacement toward Minimum Viable Pipeline |

---

## Build strategy: the jigsaw

> Can you iteratively build a tool whose value proposition requires the whole pipeline to exist?

### The wrong analogy: a bridge

A bridge has structural dependencies — you can't have the middle without the sides. This framing makes iteration seem impossible because each piece depends on adjacent pieces existing first. We initially thought in bridge terms: falsework, towers first, both sides toward the middle.

### The right analogy: a jigsaw puzzle

A jigsaw has no required order. Any piece can drop in at any time. Pieces connect to adjacent pieces, but there's no sequence. The picture emerges from whatever order the pieces drop. What matters isn't the order — it's which gaps remain and what the picture looks like so far.

The pipeline phases are jigsaw pieces, not bridge spans. Vision, Requirements, Design, Planning, Implementation, Verification, Release — any can be worked on in any order. The AI tracks which pieces are placed and which gaps remain.

### The dial controls the feel, not the pipeline

"Iterative vs waterfall" is a **false dichotomy.** It's the same pipeline, same jigsaw. The 3-mode dial controls how it feels:

| Mode | How it feels | What happens |
|---|---|---|
| **Gate** | Waterfall — every decision discussed | AI enforces at every point. "Here's what I think — approve?" Maximum human involvement. |
| **Flag** | Balanced iteration | AI acts and notifies. "I did X, here's why. Override if you disagree." |
| **Skip** | "Go! Don't bother me, just build it" | Fully autonomous. AI fills jigsaw pieces on its own. User sees the picture forming. Most iterative. |

What WE'VE been doing (sessions 5-8) is gate mode. Every decision point discussed. That's why it felt like waterfall. Same pipeline underneath — we chose maximum involvement.

### The pipeline is descriptive, not prescriptive

Every user approaches building differently. Some start with a sketch. Some start coding. Some brainstorm for weeks. Some say "build me X" and walk away. There is no universal order. Enforcing one kills the product.

The pipeline is the AI's mental model, not the user's workflow:

- AI recognizes what just happened ("that looks like design work")
- Updates its model of where things stand ("Vision crystallized, Requirements partial, Design just started")
- Knows what's been covered and what's missing
- Surfaces gaps when relevant ("you're building, but requirements were never tested — want to?")
- Enforcement level is configurable (gate/flag/skip + knobs)

The user never has to think about the pipeline. The AI uses it to understand.

### Falsework is still real

The bridge analogy was wrong for ordering, but right about one thing: **we already have temporary scaffolding.** Markdown files, terminal, canvas, chat transcripts — sessions 0-8 of real work on this scaffolding. The pain points are known:

- Scattered docs, no connections visible
- No confidence tracking
- No evolution trail
- No "where are we?" view
- No pipeline orchestration
- Each phase needs specialized agents we haven't built

The scaffolding was never waste — it's what let us do real work while figuring out what the permanent structure needs to be. Permanent pieces replace scaffolding when the pain justifies it, not in pipeline order.

### Minimum Viable Pipeline

Not Minimum Viable Product — **Minimum Viable Pipeline.** The thinnest possible jigsaw that shows the picture: all phases represented (even if most are still scaffolded), the AI tracking pipeline state, the worst gaps replaced with permanent pieces first.

The first permanent piece is **the AI's ability to observe and track pipeline state** — regardless of what order the user works in. That's the backbone. Individual phase pieces drop in around it.

---

## Design approaches

Six approaches identified. Not mutually exclusive — a palette, not a menu.

| # | Approach | How it works | Strength | Risk |
|---|---|---|---|---|
| 1 | **Scenario walkthrough** | Replay sessions 5-7 as if Compose existed. "I just had an idea" → what happens? "Connect this to that" → what do I see? Design emerges from concrete use. | Grounded in reality — we have lived data | May not generalize beyond the scenarios we walked |
| 2 | **Interaction model first** | Start with the terminal/visual split. What does the terminal handle vs the visual surface? When does information flow between them? Design the seam first, then each side. | Nails the core architectural question — everything depends on this split | Abstract before concrete — might not know the right split without trying things |
| 3 | **Visual language first** | Define the vocabulary: what does an idea look like vs a decision? What does confidence look like? What does a connection look like? Then compose into layouts. | Consistency from day one — visual primitives compose predictably | Might design atoms before knowing the molecule — premature optimization of aesthetics |
| 4 | **Reference-driven** | Survey tools that do parts of this (Obsidian Canvas, Miro, Linear, Notion, etc.), pull patterns that work, adapt to Compose's needs. | Builds on proven patterns — don't reinvent what works | Cargo culting — none of these tools do exactly what Compose does, borrowed patterns may not fit |
| 5 | **Prototype-first** | Skip detailed design, build something rough, use it, iterate. Learn by doing. | Fastest to tangible — real feedback over theoretical design | Might cement bad patterns before thinking them through — refactoring costs |
| 6 | **Slice-driven** | Pick one verb (e.g., See) and design it end-to-end: interaction model, visual language, terminal integration. Then the next verb. | Depth before breadth — buildable after each slice | Verbs might not compose well if designed independently |

### How to use these

These aren't a menu — they're a palette. Designers don't pick one approach and follow it linearly. They reach for whatever fits the moment: scenario walkthrough when grounding is needed, visual language when consistency matters, reference survey when stuck, prototype when you need to feel it.

The structure (knowing six tools exist and what each is good for) is for the AI — so it can recognize what's happening and suggest the right tool. The designer just works. Same pattern as "rails are for the AI, not the human" (session 7), applied to design.

### Industrializing the pipeline

If Compose's thesis is a structured pipeline with specialized agents per phase, then we should model it: treat each phase as having its own agent, tools, and process. A design agent uses design tools. A coding agent writes code. This is lived data for the Execute verb — directing different agents to do different work at different phases.

The practical tension: we don't have specialized agents wired up yet. The falsework for "agent orchestration" is the human + one AI doing everything. That's the next scaffolding to replace — but not until the first permanent pieces are in place.

---

## Design principles (provisional)

Inherited from CLAUDE.md project-level direction. Starting points, not fixed constraints. Each should be evaluated during design.

1. **Information density.** Mission control, not marketing. Every item, connection, and confidence level should be scannable.
2. **Hierarchy + connections.** Items nest AND connect laterally. Tree view is the backbone; connections are the nervous system.
3. **Speed over ceremony.** Creating an item: 2 seconds. Connecting items: 2 seconds. No setup, no configuration.
4. **Keyboard-first.** Navigate, create, connect, evaluate from the keyboard.
5. **Dark mode default.** Developer tool.
6. **Terminal + visual.** The terminal (Claude Code) is the primary interaction surface. The visual component augments it.

---

## Competitive insight: Base44 and the iteration problem

Base44 does remarkably well on complex apps in a single shot. It works because it constrains the space — fixed component library, frontend-focused, simple entity model on the backend. The constraints ARE the rails. The AI focuses on design within a known space rather than making infinite architectural choices.

Where it falls apart: **iteration.** Small changes, tuning, refinement after the first shot. "Move this button." "Change this flow." "Make this feel different." The incremental work that turns a generated app into a good app.

**What this means for Compose:**

| | Base44 | Compose |
|---|---|---|
| **First shot** | Excellent (constrained space) | Should match — skip mode = one prompt in, product out |
| **Iteration** | Breaks down | This is the value — evaluate → adjust → re-evaluate |
| **Memory** | None across sessions | Accumulated context (F0) gets better over time |
| **Decomposition** | None — one-shot | Pipeline breaks complex goals into manageable steps |
| **Evaluation** | None — human eyeballs it | Counterfactuals, confidence, pressure testing |
| **Constraints** | Component library (design rails) | Composition model CR1-CR7 (process rails) |

Compose's differentiation isn't the first shot — it's everything after. The pipeline is iteration infrastructure. Base44 generates. Compose generates AND iterates AND remembers AND evaluates.

**Beyond single constraints:** Base44 has one fixed constraint set (its component library). Compose has a general backbone — the composition model (CR1-CR7) — onto which domain-specific constraints get mapped. Frontend app? Map component libraries and design patterns. Backend service? Map API patterns and deployment. Any development space gets its own constraint set, but the backbone is the same: phases × things × verbs × processes × lenses. This is the invariant/variant split applied to the entire product. Not one constrained space — a framework for defining constrained spaces.

**Caveat: this is a thesis, not a proven fact.** We haven't built it yet. The iteration advantage and the generalizable constraint framework are theoretical until proven. Proving this is the goal.

---

## Visual language (emerging)

### Dynamic decision chips

Contextual UI elements that surface when the AI needs human input — at the moment of decision, not upfront in settings.

Examples:
- AI is about to run counterfactuals → `Light` `Moderate` `Aggressive`
- AI wants to proceed autonomously → `Gate` `Flag` `Skip`
- AI detected a phase transition → `Acknowledge` `Override` `Discuss`
- AI has a suggestion → `Accept` `Modify` `Reject`

Chips are the knobs and dial made tangible. They appear in context, the user taps one and keeps working. Two seconds, no ceremony. Not a settings page — a decision surface that shows up when relevant and disappears when resolved.

This is the first concrete piece of visual language. More will emerge as design continues.

---

## Vision Surface: Layout

The right panel transforms from a markdown viewer into an interactive vision surface. Terminal stays left (Claude Code, primary interaction). Vision surface is right (visual augmentation).

### Three zones

```
┌──────────────────────────────────────┐
│  STATUS BAR                          │
│  Vision · 12 items · 4 decided ·     │
│  3 questions · 2 low confidence      │
├──────────────────────────────────────┤
│                                      │
│  ITEM MAP                            │
│                                      │
│  [idea]──→[idea]                     │
│              │                       │
│           [decision]                 │
│              │                       │
│           [question]                 │
│                                      │
│                                      │
├──────────────────────────────────────┤
│  DETAIL / CHIPS                      │
│  "human-AI pairs" · low confidence   │
│  [Pressure test] [Connect] [Kill]    │
└──────────────────────────────────────┘
```

**Status bar** — answers "where are we?" in 2 seconds. One line: phase, item counts by type, confidence distribution, anything that needs attention highlighted. Always visible.

**Item map** — the main area. Items as cards, connections as lines. Can be arranged spatially (free-form) or auto-laid-out. Zoomable, pannable. This is the "see the whole picture" view.

**Detail / chips zone** — bottom strip. Shows selected item detail OR decision chips when the AI needs input. Contextual — changes based on what's happening.

### Interaction flow

| Direction | What happens |
|---|---|
| **Terminal → Surface** | User talks in terminal. AI creates/updates items. Surface updates live. "That's an idea" → new idea card appears. "Let's connect those" → connection line drawn. |
| **Surface → Terminal** | User clicks item on surface. Terminal shows detail and offers actions. Double-click → edit inline. |
| **Decision chips** | Appear in bottom zone when AI needs input. User taps a chip → answer sent to terminal → chip disappears. Two seconds. |
| **Direct manipulation** | Drag items to rearrange. Drag between items to connect. Click to select. Keyboard shortcuts for power users. Terminal is always primary — visual is augmentation, not replacement. |

---

## Visual language

### Item types

| Type | Indicator | Card style |
|---|---|---|
| **Idea** (thinking about) | 💡 amber dot | Rounded corners, light border |
| **Decision** (decided) | ✓ green dot | Solid border, slightly bolder |
| **Question** (need to figure out) | ? blue dot | Dashed border |
| **Thread** (need to do) | → gray dot | Minimal, subdued |
| **Killed** | ✗ red dot | Dimmed, strikethrough title |
| **Produced** (artifact) | 📄 purple dot | Attached to parent item, smaller |

### Confidence as fill level

```
○○○○  untested
●○○○  low
●●○○  moderate
●●●○  high
●●●●  crystallized
```

Four dots on every card. Glanceable — no text needed. Color shifts from gray (untested) through amber (low/moderate) to green (high/crystallized).

### Connections

| Relationship | Line style |
|---|---|
| **informs** (idea → decision) | Solid arrow, neutral color |
| **blocks** (gap → crystallization) | Dashed, red-tinted |
| **supports** (evidence → claim) | Dotted, green-tinted |
| **contradicts** | Dotted, red, with ✗ marker |

Lines are subtle by default, highlighted when either connected item is selected.

### Dynamic decision chips

Contextual UI elements in the bottom zone:

- AI about to run counterfactuals → `Light` `Moderate` `Aggressive`
- AI wants to proceed → `Gate` `Flag` `Skip`
- AI detected phase transition → `Acknowledge` `Override` `Discuss`
- AI has a suggestion → `Accept` `Modify` `Reject`

Chips appear when relevant, disappear when resolved. Not a settings page — a decision surface.

### Phase-specific knobs

Each phase has configurable parameters beyond the 3-mode dial. Discovered by living through the process — every time the AI asks the user for a decision, that's a signal that the product needs to present options at that point.

**Design phase knob: design fidelity**

| Setting | What happens |
|---|---|
| ASCII wireframes | Fast, structural, inline |
| POC HTML pages | Visual, throwaway, compare layouts in browser |
| Design system + tokens | Rigorous, establishes consistency first |
| Build directly in framework | Skip fidelity, go real, iterate on live code |
| Skip design | Straight to code, no design step |

Composes with the 3-mode dial:
- Gate + high fidelity = formal design review with mockups before code
- Skip + no fidelity = AI builds directly, user sees the result
- Flag + POC = AI builds a throwaway prototype, flags for review

**Design heuristic: every AI question = a decision chip.** Whenever the AI asks the user for a decision, that's a point where the product should surface options as chips. Mine session transcripts for every question the AI asked → each becomes a candidate decision surface. This is how we discover knobs: by being the user.

**Lived process (Session 9):** Our actual design process was: conversation → ASCII wireframes in design doc → standalone HTML POC → compare layout variations in browser → iterate with human feedback. This maps to the **conversation + ASCII + POC HTML** settings on the fidelity knob. No design tools needed at this stage — the conversation IS the design tool, the POC is the validation surface.

---

## Scenario walkthrough: Session 5 revisited

Concrete example of the Vision surface in action, based on lived data.

```
┌─────────────────────────────────┬──────────────────────────────────┐
│         TERMINAL                │         VISION SURFACE           │
│                                 │ Vision · 0 items                 │
│ > I have a fuzzy idea for a     │──────────────────────────────────│
│   knowledge work tracker        │                                  │
│                                 │  ┌─────────────────────┐         │
│ What problem does it solve?     │  │ 💡 knowledge work   │         │
│                                 │  │    tracker           │         │
│                                 │  │    ○○○○ untested     │         │
│ > AI agents build software      │  └─────────┬───────────┘         │
│   but there's no way to track   │            │                     │
│   the thinking                  │  ┌─────────┴───────────┐         │
│                                 │  │ 💡 tracking thinking │         │
│ Interesting — just AI agents,   │  │    for AI agents     │         │
│ or human-AI pairs?              │  │    ○○○○ untested     │         │
│                                 │  └─────────┬───────────┘         │
│ > Human-AI pairs, definitely    │            │                     │
│                                 │  ┌─────────┴───────────┐         │
│ That's a decision.              │  │ ✓  human-AI pairs    │         │
│                                 │  │    not just AI-only  │         │
│                                 │  │    ●○○○ low          │         │
│ I see 2 ideas and 1 decision.  │  └─────────────────────┘         │
│ What's the core value prop?     │──────────────────────────────────│
│                                 │ Vision · 3 items · 1 decided ·   │
│                                 │ 0 tested · 2 untested            │
│                                 │──────────────────────────────────│
│                                 │ [Pressure test] [What's missing?]│
└─────────────────────────────────┴──────────────────────────────────┘
```

The AI created 3 items from conversation. The surface shows them connected. Status bar updated. Decision chips offer next actions. The user never had to "create an item" — the AI inferred it from conversation. The user can override, restructure, or ignore the surface entirely.

---

## Implementation decisions (Session 9)

### Layout is a knob, not a design choice

The POC variations (spatial, dense, timeline) are the **same construct with different layout modes**. One knob, user switches. Not a design decision — a user preference.

| Mode | What it shows |
|---|---|
| **Spatial** | Free-form card positioning, connection lines, the "big picture" view |
| **Dense** | Smaller cards, tighter spacing, more items visible at once |
| **Timeline** | Chronological left-to-right, timestamps, "when did thinking happen?" |

### Inline conversation cards — parked

Variation D (inline cards in terminal conversation) is not feasible with a PTY-based terminal. xterm.js renders raw terminal output — we can't inject React components into a PTY stream. Parked until/unless we build a custom chat interface. The vision surface is the right place for structured items.

### Obsidian: borrow patterns, build our own

Obsidian Canvas is great for manual canvas work. Compose's canvas is AI-driven — cards created by AI from conversation, live confidence updates, decision chips, terminal sync. Different animal. Borrow spatial UX patterns, build custom renderers.

### Canvas renderers as React components

The POC HTML maps directly to components:

| Component | What it renders |
|---|---|
| `<ItemCard />` | Type dot, title, confidence dots, selection state, border style by type |
| `<ConnectionLayer />` | SVG overlay for lines between items (informs, blocks, supports) |
| `<StatusBar />` | Phase, item counts, attention flags |
| `<DetailZone />` | Selected item detail + decision chips |
| `<VisionSurface />` | Composes the above, manages layout mode knob |

### CanvasUX: multi-renderer shell

The current `Canvas.jsx` (markdown tab viewer) evolves into a multi-renderer shell:

```
CanvasUX
├── MarkdownRenderer (existing — docs, specs, journals)
├── VisionSurface (new — item map from POC)
├── ZoomedOutView (future — all items across all phases)
└── [future renderers]
```

Tabs switch between open artifacts. Each artifact has a renderer type. Markdown files open in MarkdownRenderer. The vision surface is a special tab. "Zoomed out" aggregates everything (future).

---

## Open design questions (remaining)

- How does the item map scale to 50+ items? Clustering? Zoom levels? Filter by type/confidence?
- How does synthesis work as an interaction? Select multiple items → AI produces consolidated artifact?
- What's the animation/transition feel? Items appearing, connections drawing, confidence updating?
- What does the AI's proactive behavior look like? A notification badge? A chip that pulses? An item that appears with a different border?
- Stale items — how are they visually flagged? Dimming? Badge? Timestamp?

---

*The spec says what. This doc says how. Terminal is primary, vision surface augments. Items appear from conversation. Decision chips surface when needed. Four dots for confidence. The picture builds itself.*
