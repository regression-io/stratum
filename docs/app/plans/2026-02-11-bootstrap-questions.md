# Open Questions: Bootstrap Implementation

**Date:** 2026-02-11
**Status:** OPEN — answers needed before first implementation point
**Depends on:** [Agent-Primary Architecture Decision](../decisions/2026-02-11-agent-primary-architecture.md)
**Feeds into:** Revised bootstrap plan

---

## Q1: Terminal embed or chat UI?

**Options:**

A. **xterm.js terminal** running Claude Code CLI via WebSocket to shell process
   - Fastest to build (solved problem, libraries exist)
   - Full Claude Code capability immediately (tools, permissions, MCP servers)
   - Ugly — monospace text, no structured rendering
   - No options/buttons, no inline cards, no visual diffs

B. **Custom chat UI** talking to Anthropic API with tool use
   - Chat + options/buttons (the "structured choices" interaction)
   - Work item previews inline, visual diffs, rich rendering
   - More to build (streaming, tool execution backend, context management)
   - Need to replicate Claude Code's tool access (file system, bash, etc.)

C. **Terminal first, chat UI later**
   - Ship the terminal embed to unblock everything
   - Build the chat UI as a replacement/overlay when we know the interaction patterns
   - Risk: the terminal becomes permanent because it works "well enough"

D. **Chat UI that can drop to terminal**
   - Primary interaction is chat + options
   - "Advanced" or "terminal" mode for raw CLI access
   - Best UX but most work upfront

**Depends on:** How important is the "chat + options" onboarding interaction for the first session?

---

## Q2: How does the agent connect to the backend?

**Options:**

A. **Shell process via WebSocket** — Backend spawns `claude` CLI, pipes stdin/stdout over WebSocket to the browser. Terminal emulator (xterm.js) renders it.

B. **Anthropic API direct** — Backend calls Claude API with tool definitions. Custom tool execution layer for file access, bash, etc. Chat UI renders responses.

C. **Claude Code SDK/API** — If Claude Code exposes a programmatic interface (Agent SDK), use that. Gets Claude Code's full tool set without reimplementing.

**Depends on:** What Claude Code exposes programmatically. Need to investigate.

---

## Q3: What happens to the Base44 SDK dependency?

The UI currently won't load without `@base44/sdk` and `@base44/vite-plugin`. Before anything else works, this needs to be replaced.

**Options:**

A. **Wire the persistence connector now** — The server code exists, the composeClient exists. Do the trivial wiring (import swap, AuthContext stub, vite proxy, package.json). ~30 min of work.

B. **Stub everything to no-ops** — Make the UI load with empty data. Minimal changes. Then the agent panel can be added to a working (empty) UI.

C. **Both** — Wire persistence so the UI shows real data from `.compose/`, then add the agent panel.

**Leans toward:** C — the persistence wiring is trivial and gives us a working UI that displays real data.

---

## Q4: Agent panel placement in the UI

Where does the agent panel live?

**Options:**

A. **Right sidebar** (like WorkDetailPanel) — Collapsible, same pattern as existing detail panel
B. **Bottom panel** (like VS Code terminal) — Horizontal split, resizable
C. **Separate route/page** — `/agent` as a full-screen chat view
D. **Overlay/drawer** — Slides in from right or bottom, overlays the current view
E. **Always visible split** — Left: views, Right: agent. Fixed layout.

**Depends on:** How much screen space the agent conversation needs vs the views.

---

## Q5: Context awareness — does the agent know what you're looking at?

When you're viewing a specific work item in the detail panel and type in the agent panel, does the agent know which item you're looking at?

**Options:**

A. **Yes, automatically** — UI sends current view context (selected item, active filters, current page) to the agent as system context.
B. **Yes, on request** — Agent can query "what is the user looking at?" but doesn't get it automatically.
C. **No** — Agent and UI are independent. User explicitly references items by name/ID.

**Leans toward:** A — this is what makes the split-screen model powerful. "Update the status of this" should work without specifying which item.

---

## Q6: Conversation persistence

When you close Compose and reopen it, is the conversation still there?

**Options:**

A. **Yes, stored in `.compose/`** — Conversations are artifacts, stored as markdown. Git tracks them.
B. **Yes, stored separately** — Conversation state in a local database or file outside `.compose/`.
C. **No** — Each session starts fresh. Agent reads `.compose/` for context but conversation history is ephemeral.
D. **Hybrid** — Conversation is ephemeral, but the agent distills key outputs into `.compose/` work items/artifacts before session ends.

**Leans toward:** D — conversations are messy. The valuable outputs (decisions, work items, findings) should be extracted and stored. The raw transcript is less valuable.

---

## Q7: What does the agent panel need to do in the FIRST session?

If we build the minimum agent panel and open Compose for the first time, what should the interaction be?

Scenario: Empty `.compose/` directory. User opens Compose. Sees empty dashboard + agent panel.

What should the agent say/do?
- Greet and ask what we're building?
- Offer to import existing docs (we have a whole `coder-compose/docs/` folder)?
- Create the first project and work items from conversation?
- Offer structured options: "New project", "Import existing", "Continue from docs"?

**This is the onboarding question.** The answer shapes the first implementation.

---

## Q8: Scope of agent modifications

Can the agent modify the Compose UI code itself during a session?

**Options:**

A. **Yes, always** — Agent has full codebase access. Self-modification is a feature.
B. **Yes, with approval** — Agent proposes changes, user approves (gate mode). This is Claude Code's default behavior.
C. **No, only `.compose/` data** — Agent can create/edit work items but can't change the UI code. Self-modification is a separate mode.

**Leans toward:** B — this is already how Claude Code works. The permission model is built.

---

## Decisions Made

```
Q1 → DECIDED: Terminal (xterm.js) now, chat UI later.
     Terminal has self-extension capability — Compose can build
     the chat UI from inside itself using the terminal.

Q2 → DECIDED: Claude Code CLI via shell process + WebSocket.
     Best self-modification capability available. Full file
     system access, bash, tools, permission model — all built in.

Q3 → DECIDED: Just do it. Wire persistence, remove Base44.

Q4-Q8 → DEFERRED: Answer by using it. Build the terminal,
         iterate on placement/context/persistence from experience.
```

## Implementation Plan

```
Step 1: Wire persistence (remove Base44 SDK, connect composeClient)
        - Import swap, AuthContext stub, vite proxy, package.json
        - Audit + update connector for new UI fields (type, phase, etc.)
        - Gate: UI loads, shows empty dashboard, no errors

Step 2: Embed terminal in UI
        - Backend: WebSocket server (on Express), spawn shell with PTY
        - Frontend: xterm.js terminal component, panel in UI layout
        - Gate: Can type `claude` in the embedded terminal,
                agent can modify .compose/ files, UI reflects changes

Step 3: Self-bootstrap
        - Use the terminal to build everything else
        - First task: the agent imports existing docs into .compose/
        - Second task: the agent builds the chat UI replacement
```
